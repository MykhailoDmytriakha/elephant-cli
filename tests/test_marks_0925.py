"""A report from a live case and the owner's word, 2026-09-25: a binary checkbox lied at a glance — `[x]` on an item done
by one hand read as «checked» to the owner, to the agent, to Order. In a case that asks two hands the mark is now rendered
from the item: `[/]` — done, awaiting acceptance (half of an x: one hand of two), `[x]` — finished; a legend line under the
title says so. A case without the rule keeps `[x]` for done. The second hand re-runs every `run:` proof and says what came
out now (`--run`); el itself runs nothing (the owner's word, 2026-09-22)."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp
from tests.test_commands import run

LEGEND = "> marks: [ ] open · [/] done, awaiting acceptance — el todo brief N.M · [x] finished · [~] on hold"


class Base(unittest.TestCase):
    rule = "1"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_TWO_HANDS"] = self.rule
        run("case", "new", "api", "--goal", "g")
        os.environ["EL_TWO_HANDS"] = "0"
        run("phase", "open", "1", "Work", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "out.txt").write_text("ok\n", encoding="utf-8")
        run("todo", "add", "1", "build it", "--expect", "[run: make test → 12 OK]")
        run("todo", "add", "1", "write the note")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def todo(self) -> str:
        return (self.case / "TODO.md").read_text(encoding="utf-8")

    def done_both(self):
        os.environ["EL_SESSION"] = "doer1"
        self.assertEqual(run("todo", "done", "1.1", "run:make test -> 12 OK", "built")[0], 0)
        self.assertEqual(run("todo", "done", "1.2", "file:out.txt", "noted")[0], 0)
        os.environ["EL_SESSION"] = "second2"


class HalfAnX(Base):
    def test_done_by_one_hand_is_half_a_mark_with_a_legend(self):
        self.done_both()
        todo = self.todo()
        self.assertIn("  - [/] 1.1 build it", todo)
        self.assertIn("  - [/] 1.2 write the note", todo)
        self.assertIn(LEGEND, todo)
        parsed = grammar.parse_todo(stamp.split(todo)[0])
        self.assertEqual(parsed.errors, [])
        self.assertTrue(all(it.done for it in parsed.phase(1).items), "[/] is done — only its acceptance is owed")

    def test_the_second_hand_makes_it_a_full_mark_and_the_legend_goes(self):
        self.done_both()
        code, out, err = run("todo", "accept", "1.2", "--by", "codex", "opened out.txt")
        self.assertEqual(code, 0, err)
        code, out, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test -> 12 OK", "re-ran the tests")
        self.assertEqual(code, 0, err)
        todo = self.todo()
        self.assertIn("  - [x] 1.1 build it", todo)
        self.assertIn("  - [x] 1.2 write the note", todo)
        self.assertNotIn(LEGEND, todo, "nothing awaits acceptance: no legend")

    def test_reopen_takes_it_back_to_open(self):
        self.done_both()
        run("todo", "reopen", "1.1", "--by", "codex", "the tests fail now")
        self.assertIn("  - [ ] 1.1 build it", self.todo())

    def test_the_entry_shows_the_marks_too(self):
        self.done_both()
        out = run()[1]
        self.assertIn("  - [/] 1.1 build it", out)
        self.assertIn(LEGEND, out)


class RerunByTheSecondHand(Base):
    def test_accept_asks_to_rerun_each_run_proof(self):
        self.done_both()
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "looked at it")
        self.assertEqual(code, 2)
        self.assertIn("make test → 12 OK", err, "the refusal names the command to re-run")
        self.assertIn("--run", err)

    def test_the_rerun_is_recorded_with_the_acceptance(self):
        self.done_both()
        code, out, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test -> 12 OK", "re-ran it")
        self.assertEqual(code, 0, err)
        self.assertIn("    - accepted: codex · another session", self.todo())
        self.assertIn("re-ran 1 of 1", self.todo())
        journal = (self.case / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn("re-run: make test → 12 OK", journal)

    def test_a_run_the_second_hand_could_not_repeat_is_said_not_hidden(self):
        self.done_both()
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test -> not run: no build tools here", "read the log")
        self.assertEqual(code, 0, err)
        self.assertIn("re-ran 0 of 1 (1 not run)", self.todo())

    def test_a_rerun_that_came_out_otherwise_is_shown_next_to_the_doer_s(self):
        self.done_both()
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test -> 11 OK, 1 FAIL", "re-ran it")
        self.assertEqual(code, 0, err)  # the meaning is the acceptor's: shown, not refused
        self.assertIn("«12 OK»", err)
        self.assertIn("«11 OK, 1 FAIL»", err)
        self.assertIn("el todo reopen 1.1 --by codex", err)
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test -> 12 ok", "again")
        self.assertNotIn("differs", err, "the same outcome is no warning")

    def test_a_range_counts_each_item_s_own_reruns(self):
        self.done_both()
        code, _, err = run("todo", "accept", "1.1-1.2", "--by", "codex", "--run", "make test -> 12 OK", "both checked")
        self.assertEqual(code, 0, err)
        lines = [ln for ln in self.todo().splitlines() if ln.startswith("    - accepted:")]
        self.assertIn("re-ran 1 of 1", lines[0])
        self.assertNotIn("re-ran", lines[1], "1.2 stands on a file, nothing to re-run")

    def test_a_rerun_without_an_arrow_is_refused(self):
        self.done_both()
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test", "ok")
        self.assertEqual(code, 2)
        self.assertIn("→", err)

    def test_the_owner_word_needs_no_rerun(self):
        self.done_both()
        code, _, err = run("todo", "accept", "1.1", "--by", "owner", "the owner saw it build")
        self.assertEqual(code, 0, err)

    def test_the_brief_names_the_commands_and_the_verdict_form(self):
        self.done_both()
        out = run("todo", "brief", "1.1")[1]
        self.assertIn('--run "make test → <what came out now>"', out)


class NoRuleNoHalfMark(Base):
    rule = "0"

    def test_a_case_without_two_hands_keeps_x_for_done(self):
        self.done_both()
        todo = self.todo()
        self.assertIn("  - [x] 1.1 build it", todo)
        self.assertNotIn("[/]", todo)
        self.assertNotIn("> marks:", todo)

    def test_taking_the_rule_later_shows_what_is_owed(self):
        self.done_both()
        run("readme", "add", "context", "rule: two hands — the owner agrees each phase's scope, a fresh session accepts each done item")
        run("todo", "add", "1", "one more")  # any write renders the marks again
        self.assertIn("  - [/] 1.1 build it", self.todo())


if __name__ == "__main__":
    unittest.main()
