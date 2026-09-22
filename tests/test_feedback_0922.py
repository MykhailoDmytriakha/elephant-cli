"""Six reports of 2026-09-22 from a live case (el 1.20.0): a line el wrote in 1.5.0–1.9.0
(`… — due: D — file: [x](p)`) made the whole TODO unwritable and hid the dates; kinds attached to old ticks
wrote six RESULTs; two Cyrillic feedback titles in one minute overwrote each other; bare `el readme` read
as a broken README; an event about items 2.x landed under p1; a long item's suggestion cut mid-phrase."""
import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        run("case", "new", "demo case", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")
        run("phase", "plan", "2", "Data", "--goal", "g2")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "evidence").mkdir()
        (self.case / "evidence" / "a.jpg").write_bytes(b"jpg")
        run("todo", "add", "1", "file the form")
        run("todo", "add", "2", "ask the police for the report")

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class OldTail(Base):
    def write_old_form(self, due: str):
        body, _ = stamp.split(self.read("TODO.md"))
        body = body.replace("  - [ ] 1.1 file the form",
                            f"  - [x] 1.1 file the form — due: {due} — file: [a.jpg](evidence/a.jpg)\n"
                            f"  - [ ] 1.2 call back — due: {due}")
        (self.case / "TODO.md").write_text(stamp.apply(body), encoding="utf-8")

    def test_a_line_el_wrote_is_a_line_el_reads(self):
        self.write_old_form("2026-09-16")
        todo = grammar.parse_todo(stamp.split(self.read("TODO.md"))[0])
        self.assertEqual(todo.errors, [])
        it = todo.phase(1).items[0]
        self.assertEqual((it.text, it.due, it.evidence), ("file the form", "2026-09-16", [("file", "[a.jpg](evidence/a.jpg)")]))
        code, out, err = run("todo", "add", "1", "next step")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [x] 1.1 file the form — due: 2026-09-16\n    - file: [a.jpg](evidence/a.jpg)\n", self.read("TODO.md"),
                      "the next write renders the current form")

    def test_overdue_is_named_first_on_entry(self):
        yesterday = dt.date.today() - dt.timedelta(days=1)
        self.write_old_form(yesterday.isoformat())
        out = run()[1]
        self.assertIn(f"OVERDUE: 1.2 ({yesterday.isoformat()[5:]}, 1 day ago)", out)

    def test_an_unparsable_todo_says_the_dates_were_not_counted(self):
        body, _ = stamp.split(self.read("TODO.md"))
        (self.case / "TODO.md").write_text(stamp.apply(body.replace("1.1 file the form", "1.1 file the form — due: someday")),
                                           encoding="utf-8")
        self.assertIn("dates · unblocked · evidence NOT counted — TODO.md is not parsable", run()[1])


class AttachIsNotAnEvent(Base):
    def test_proof_for_an_old_tick_writes_no_result_and_keeps_last(self):
        run("todo", "done", "1.1", "owner", "form filed")
        journal, readme = self.read("JOURNAL.md"), self.read("README.md")
        code, out, err = run("todo", "done", "1.1", "file:evidence/a.jpg")
        self.assertEqual(code, 0, f"words kept when not given: {err}")
        self.assertIn("no journal event", out)
        self.assertEqual(self.read("JOURNAL.md"), journal)
        self.assertEqual(self.read("README.md"), readme, "last: does not move")
        self.assertIn("    - result: form filed\n      - owner\n      - file: [a.jpg](evidence/a.jpg)\n", self.read("TODO.md"))


class FeedbackNeverOverwrites(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["EL_FEEDBACK_DIR"] = str(Path(self.tmp.name) / "pool")

    def tearDown(self):
        del os.environ["EL_FEEDBACK_DIR"]
        self.tmp.cleanup()

    def test_three_calls_in_one_minute_three_files(self):
        for title in ("лимит длины", "журнал засорён", "лимит длины"):
            self.assertEqual(run("feedback", title, "--actual", "a", "--expected", "e")[0], 0)
        names = sorted(p.name for p in (Path(self.tmp.name) / "pool").iterdir())
        self.assertEqual(len(names), 3, names)
        self.assertTrue(any(n.endswith("-limit-dliny.md") for n in names), names)
        self.assertTrue(any(n.endswith("-zhurnal-zasoren.md") for n in names), names)
        self.assertTrue(any(n.endswith("-limit-dliny-2.md") for n in names), names)


class BareReadme(Base):
    def test_bare_readme_shows_it_not_a_false_alarm(self):
        before = self.read("README.md")
        stdin, sys.stdin = sys.stdin, io.StringIO("")
        try:
            code, out, err = run("readme")
        finally:
            sys.stdin = stdin
        self.assertEqual(code, 0, err)
        self.assertIn("## State", out)
        self.assertIn("el readme set", out)
        self.assertNotIn("F1", out + err)
        self.assertEqual(self.read("README.md"), before)


class LogFollowsTheItems(Base):
    def test_event_about_items_of_another_phase_is_filed_there(self):
        code, out, err = run("log", "RESULT", "2.1: the request is registered")
        self.assertEqual(code, 0, err)
        self.assertIn("filed under p2", out)
        entry = next(e for e in grammar.parse_journal(self.read("JOURNAL.md")).entries if any("2.1:" in ev.text for ev in e.events))
        self.assertEqual(entry.phase, "p2")

    def test_no_refs_or_a_version_stays_in_flight(self):
        run("log", "DECISION", "el 2.1.0 is fine here")
        entry = grammar.parse_journal(self.read("JOURNAL.md")).entries[0]
        self.assertEqual(entry.phase, "p1")


class LongItem(Base):
    def test_suggestion_cuts_at_meaning_and_keeps_the_rest_as_note(self):
        text = ("Declaration сверить с CAD: «My fault» на месте, непреднамеренно, накат — "
                "не «следил за скоростью», а честно про спуск и инерцию машины")
        code, _, err = run("todo", "add", "1", text)
        self.assertEqual(code, 3)
        self.assertIn("el todo add 1 'Declaration сверить с CAD: «My fault» на месте, непреднамеренно, накат' "
                      "--note 'не «следил за скоростью», а честно про спуск и инерцию машины'", err)


class ReportedIsNotVerified(Base):
    """Feedback 2026-09-22 12:47 (a code case): a run nobody repeated looked verified next to «check 0»;
    25 done items and 0 facts left the facts line silent."""

    def test_check_and_entry_say_what_el_checked(self):
        run("todo", "done", "1.1", "run:make test -> 12 OK", "tests pass")
        self.assertIn("structure and form, not what the proofs prove", run("check")[1])
        self.assertIn("el checked: file exists · run, ref, owner: as reported", run()[1])

    def test_zero_facts_over_done_work_is_said(self):
        run("todo", "add", "1", "b")
        run("todo", "add", "1", "c")
        self.assertNotIn("facts:", run()[1])
        run("todo", "done", "1.1-1.3", "owner", "ok")
        self.assertIn("facts: 0 established over 3 done items", run()[1])


class BoundedFacts(unittest.TestCase):
    """Feedback 2026-09-22 12:52: the practice example turned three traces into «never» — the dose taught the
    overclaim it should prevent; and the doses shipped names from a live case."""

    def test_the_doses_teach_a_bounded_fact_in_neutral_words(self):
        from elephant import knowledge
        # names from live cases: tests/test_no_private_terms.py, against the local list
        self.assertIn("not proved absent", knowledge.TOPICS["practice"])
        self.assertIn("Not seen is not absent", knowledge.TOPICS["facts"])
        self.assertIn("el never runs a check itself", knowledge.TOPICS["evidence"])


if __name__ == "__main__":
    unittest.main()
