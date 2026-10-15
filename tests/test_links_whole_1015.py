"""Five reports of 2026-10-15, all from live cases.

1. `done` with an 85-char file name: the journal wrapped the event body at 160 chars inside the link's target —
   `(evidence/…_zoom` on one line, `.pdf)` on the next; the link died, README `last:` drew it with a space inside, and
   later `mv` and `relink` could no longer see it. El never cuts a link: it stands whole on a body line of its own, and a
   link el once cut is sewn back — read whole by Order and the readers, written whole at the next write.
2. `relink` of a moved file was refused, «event line is 201 chars, limit 200», by the path el itself writes: the line
   el's own rewrite pushes past F7 sends the tail of its headline into the body.
3. `mv` rewrote a link's target and left its name — `[old-long.pdf](evidence/short.pdf)`: a name that spells the file
   (its file name, as `done` writes it, or its path as written) follows the file; a name in other words stays.
4. After `el done --by owner` the bare `el` — «the end: el again» — met ERROR exit 4 «every case here is closed»: the
   session that held the case sees it closed, with what came out and the door on; a fresh session meets the door as before.
5. `phase close --reflect "reflect: …"` was refused, exit 2, though its meaning was plain: el writes the prefix once."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp
from tests.test_commands import run

NAME = "2026-10-15_hearing-notice-on-paper_X0000000_2026-12-04_video-call-link-and-room-number.pdf"  # 89 chars
P1 = "benchmarks/evolution/experiments/2026-10-15-1005-harvest/teacher"
P2 = "training-data/2026-10-15-1136-full-harvest/cycle-artifacts/teacher"  # 3 chars longer


class Base(unittest.TestCase):
    KEYS = ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS", "EL_CASE")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.pop("EL_CASE", None)
        os.environ.pop("EL_TWO_HANDS", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="link1015", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        self.ok("case", "new", "court", "--goal", "the hearing is known")
        self.ok("phase", "open", "1", "Notice", "--goal", "the notice is kept [file]")
        self.ok("todo", "add", "1", "the notice arrives", "--expect", "[file: the paper notice]")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-court"))
        (self.case / "evidence").mkdir()
        (self.case / "evidence" / NAME).write_bytes(b"%PDF-1.4\n")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def ok(self, *argv):
        code, out, err = run(*argv)
        self.assertEqual(code, 0, f"{argv}: {out}{err}")
        return out, err

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")

    def done(self):
        self.ok("todo", "done", "1.1", f"file:evidence/{NAME}", "the notice of the hearing arrived on paper")

    def whole_link_lines(self, text: str, target: str):
        return [ln for ln in text.split("\n") if f"]({target})" in ln]


class LinkWhole(Base):
    def test_done_with_a_long_file_name_keeps_the_link_whole(self):
        self.done()
        link = f"[{NAME}](evidence/{NAME})"
        self.assertEqual(len([ln for ln in self.read("JOURNAL.md").split("\n") if link in ln]), 1, self.read("JOURNAL.md"))
        last = next(ln for ln in self.read("README.md").split("\n") if ln.startswith("- last: "))
        self.assertIn(link, last)  # drawn from the journal: no space inside the target
        code, out, err = run("check")
        self.assertNotIn("broken link", out + err)

    def test_a_link_with_spaces_in_its_name_is_one_word(self):
        words = "the notice came and was read twice over with the clerk on the phone to be sure of the date and the room " * 2
        self.ok("log", "RESULT", f"{words}[the paper notice of the hearing](evidence/{NAME}) kept")
        link = f"[the paper notice of the hearing](evidence/{NAME})"
        self.assertTrue(any(link in ln for ln in self.read("JOURNAL.md").split("\n")), self.read("JOURNAL.md"))

    def test_a_plain_word_too_long_for_an_event_is_still_refused(self):
        self.assertEqual(run("log", "RESULT", "x" * 2000)[0], 3)  # a link stands whole; a word that points nowhere is cut

    def cut_by_old_el(self):
        """The journal as el ≤ 1.67.0 wrote it: the body line hard-cut at 160 chars inside the link's target."""
        self.done()
        body, _ = stamp.split(self.read("JOURNAL.md"))
        line = next(ln for ln in body.split("\n") if ln.startswith("    ") and f"(evidence/{NAME})" in ln)
        piece = line[4:]
        self.assertGreater(len(piece), 160)
        cut = f"    {piece[:160]}\n    {piece[160:]}"
        (self.case / "JOURNAL.md").write_text(stamp.apply(body.replace(line, cut)), encoding="utf-8")
        return cut

    def test_a_link_el_once_cut_is_read_whole_and_relinked(self):
        self.cut_by_old_el()
        (self.case / "evidence" / NAME).rename(self.case / "evidence" / "notice.pdf")
        out, _ = self.ok()
        self.assertRegex(out, r"broken link\(s\):.*JOURNAL\.md →")  # Order sees the journal's link again
        out, _ = self.ok("relink", f"evidence/{NAME}", "evidence/notice.pdf")
        self.assertIn("JOURNAL.md (1)", out)
        self.assertEqual(len(self.whole_link_lines(self.read("JOURNAL.md"), "evidence/notice.pdf")), 1)
        self.assertNotIn(NAME, self.read("JOURNAL.md"))
        last = next(ln for ln in self.read("README.md").split("\n") if ln.startswith("- last: "))
        self.assertIn("[notice.pdf](evidence/notice.pdf)", last)
        code, out, err = run("check")
        self.assertNotIn("broken link", out + err)

    def test_the_next_write_sews_the_cut_link(self):
        cut = self.cut_by_old_el()
        self.ok("log", "DECISION", "the notice is the proof of the date")
        journal = self.read("JOURNAL.md")
        self.assertNotIn(cut, journal)
        self.assertEqual(len(self.whole_link_lines(journal, f"evidence/{NAME}")), 1, journal)


class RelinkFits(Base):
    def setUp(self):
        super().setUp()
        (self.case / P1).mkdir(parents=True)
        (self.case / P1 / "teacher.md").write_text("# teacher\nsummary: the teacher prompt\n", encoding="utf-8")

    def test_a_headline_el_pushes_past_the_limit_wraps(self):
        text = (f"teacher prompt and harvest notes kept for the next cycle of this run: [teacher.md]({P1}/teacher.md) "
                f"— the cycle reads it all again")
        self.assertEqual(len(f"RESULT · {text}"), 199)
        self.ok("log", "RESULT", text)
        (self.case / P2).mkdir(parents=True)
        (self.case / P1 / "teacher.md").rename(self.case / P2 / "teacher.md")
        out, err = self.ok("relink", f"{P1}/teacher.md", f"{P2}/teacher.md")
        self.assertIn("JOURNAL.md (1)", out)
        journal = self.read("JOURNAL.md")
        head = next(ln for ln in journal.split("\n") if "teacher prompt" in ln)
        self.assertLessEqual(len(head.strip()), grammar.EVENT_CHARS)
        self.assertTrue(head.endswith(" …"), head)
        self.assertIn(f"[teacher.md]({P2}/teacher.md)", journal)
        ev = next(ev for e in grammar.parse_journal(journal).entries for ev in e.events if "teacher prompt" in ev.text)
        self.assertTrue(" ".join([ev.text[:-2], *ev.body]).endswith("the cycle reads it all again"), ev)
        code, out, err = run("check")
        self.assertIn("violations: 0", out)

    def test_a_name_that_spells_the_file_follows_it(self):
        self.done()
        (self.case / "docs").mkdir()
        (self.case / "docs" / "hearing.md").write_text(
            f"# Hearing\nsummary: what the notice says\n\n[the notice](../evidence/{NAME}) · [{NAME}](../evidence/{NAME})\n",
            encoding="utf-8")
        self.ok("readme", "add", "links", "[hearing.md](docs/hearing.md) — what the notice says")
        self.ok("mv", f"evidence/{NAME}", "evidence/notice.pdf")
        self.assertIn("- file: [notice.pdf](evidence/notice.pdf)", self.read("TODO.md"))
        self.assertIn("[notice.pdf](evidence/notice.pdf)", self.read("JOURNAL.md"))
        self.assertIn("[notice.pdf](evidence/notice.pdf)", self.read("README.md"))
        doc = (self.case / "docs" / "hearing.md").read_text(encoding="utf-8")
        self.assertIn("[the notice](../evidence/notice.pdf)", doc)  # the writer's own words stay
        self.assertIn("[notice.pdf](../evidence/notice.pdf)", doc)
        for f in ("TODO.md", "JOURNAL.md", "README.md"):
            self.assertNotIn(NAME, self.read(f), f)

    def test_a_name_spelled_as_the_path_follows_it(self):
        (self.case / "docs").mkdir()
        (self.case / "docs" / "a.md").write_text("# A\nsummary: a\n", encoding="utf-8")
        self.ok("readme", "add", "context", "the map: [docs/a.md](docs/a.md)")
        self.ok("mv", "docs/a.md", "docs/b.md")
        self.assertIn("the map: [docs/b.md](docs/b.md)", self.read("README.md"))

    def test_a_name_that_would_break_an_item_stays_the_path_follows(self):
        (self.case / "docs").mkdir()
        (self.case / "docs" / "a.md").write_text("# A\nsummary: a\n", encoding="utf-8")
        item = "read the clerk's letter [a.md](docs/a.md) and write down the date, the room and the judge's name ok"
        self.assertLessEqual(grammar.visible_len(item), 100)
        self.ok("todo", "add", "1", item)
        new = "the-clerks-letter-of-october-with-the-room.md"
        out, err = self.ok("mv", "docs/a.md", f"docs/{new}")
        self.assertIn(f"[a.md](docs/{new})", self.read("TODO.md"))
        self.assertIn("link names kept as they were", err)


class ClosedEntry(Base):
    def close_the_case(self):
        self.done()
        self.ok("todo", "accept", "1.1", "--by", "owner", "seen the paper")
        self.ok("phase", "close", "1", "the notice is kept", "--reflect", "read the mail first", "--align", "nothing next")
        self.ok("done", "the hearing date is known")
        self.ok("done", "--by", "owner", "thanks, closed")

    def test_the_session_that_closed_it_sees_it_closed(self):
        self.close_the_case()
        code, out, err = run()
        self.assertEqual(code, 0, out + err)
        lines = out.split("\n")
        self.assertTrue(lines[0].startswith("el · closed case: "), lines[0])
        thread = next(ln for ln in lines if ln.startswith("thread: "))
        self.assertIn("closed «the hearing date is known", thread)
        self.assertIn(f"el --case {self.case.name} case reopen", thread)
        self.assertNotIn("el done", thread)
        self.assertNotIn("acceptance: 0 of 0", out)
        self.assertIn("- closed: ", out)

    def test_a_fresh_session_meets_the_door(self):
        self.close_the_case()
        os.environ["EL_HANDS_DIR"] = str(Path(self.tmp.name) / "hands-fresh")
        code, out, err = run()
        self.assertEqual(code, 4)
        self.assertIn("every case here is closed", out)

    def test_a_write_does_not_reach_the_closed_case_through_the_hand(self):
        self.close_the_case()
        code, out, err = run("log", "DECISION", "one more thought")
        self.assertEqual(code, 4)
        self.assertIn("every case here is closed", err)

    def test_an_add_in_a_closed_case_opens_the_case_first(self):
        self.close_the_case()
        code, out, err = run("--case", "court", "todo", "add", "1", "one more")
        self.assertEqual(code, 4)
        self.assertRegex(err, r"case reopen \"why it goes on\", then el --case court phase plan 2")


class OwnPrefix(Base):
    def test_the_flags_own_name_is_taken_once(self):
        self.done()
        self.ok("todo", "accept", "1.1", "--by", "owner", "seen")
        self.ok("log", "PROBLEM", "the notice came late")
        self.ok("phase", "close", "1", "kept", "--reflect", "reflect: read the mail first", "--align", "align: nothing next",
                "--howto", "howto: none: a late letter is not a recipe")
        journal = self.read("JOURNAL.md")
        for line in ("DECISION · reflect: read the mail first", "DECISION · align: nothing next",
                     "DECISION · howto: none: a late letter is not a recipe"):
            self.assertIn(line, journal)
        self.assertIsNone(re.search(r"(reflect|align|howto): \1:", journal), journal)


if __name__ == "__main__":
    unittest.main()
