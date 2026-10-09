"""The cold reader, 2026-10-08: agents decide in the journal and leave README Decisions empty (six of eight big live cases);
given the README alone, «which decisions were taken» was «not in the README» 10 times of 16. The owner said yes to drawing
them: the five newest agent decisions, dated, under a line that says they are history, not the case's rules — 0 of 16."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp
from tests.test_commands import run

HEAD = "- from the journal, newest first — history, not the case's rules:"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="dec1008", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "probe", "--goal", "g")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-probe"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def decisions(self):
        run()  # the entry redraws README from the journal, as it draws `last:`
        text = (self.case / "README.md").read_text(encoding="utf-8")
        return text.split("## Decisions\n", 1)[1].split("\n## ", 1)[0].rstrip("\n").split("\n")


class TheNewestDecisionsAreDrawn(Base):
    def test_five_newest_dated_under_the_history_line(self):
        for k in range(7):
            run("log", "DECISION", f"choice {k} · instead of the other · because of the measure")
        lines = self.decisions()
        self.assertEqual(lines[0], HEAD)
        drawn = [ln for ln in lines[1:] if ln.startswith("  - ")]
        self.assertEqual(len(drawn), 5)
        self.assertTrue(drawn[0].endswith("choice 6 · instead of the other · because of the measure"), drawn[0])
        self.assertRegex(drawn[0], r"^  - \d{4}-\d{2}-\d{2} · ")

    def test_els_own_bookkeeping_is_not_a_decision(self):
        run("phase", "open", "1", "Work", "--goal", "w")
        run("phase", "agree", "1", "the owner agreed")
        run("todo", "add", "1", "step")
        run("todo", "done", "1.1", "run:x → ok", "ok")
        run("todo", "accept", "1.1", "--by", "owner", "ok")
        run("log", "DECISION", "the real choice of the work")
        run("phase", "close", "1", "closed", "--reflect", "a lesson", "--align", "a change")
        text = "\n".join(self.decisions())
        self.assertIn("the real choice of the work", text)
        for bookkeeping in ("принято", "объём фазы", "reflect:", "align:"):
            self.assertNotIn(bookkeeping, text)

    def test_the_agents_own_lines_stay_first_and_are_not_drawn_twice(self):
        run("readme", "add", "decisions", "2026-10-08 · the rule we keep from now on")
        run("log", "DECISION", "the rule we keep from now on")
        run("log", "DECISION", "another choice")
        lines = self.decisions()
        self.assertEqual(lines[0], "- 2026-10-08 · the rule we keep from now on")
        self.assertEqual(lines[1], HEAD)
        self.assertEqual(sum("the rule we keep" in ln for ln in lines), 1)

    def test_a_link_of_the_journal_comes_as_its_name(self):
        run("log", "DECISION", "chose the plan in [plan.md](docs/plan.md), the file is gone since")
        self.assertIn("chose the plan in plan.md, the file is gone since", "\n".join(self.decisions()))
        code, out, _ = run("check")
        self.assertIn("violations: 0", out)

    def test_redrawn_not_doubled_and_outside_the_limit(self):
        run("log", "DECISION", "one choice")
        run("readme", "touch")
        run("readme", "touch")
        self.assertEqual(self.decisions().count(HEAD), 1)
        body, _ = stamp.split((self.case / "README.md").read_text(encoding="utf-8"))
        parsed = grammar.parse_readme(body)
        self.assertGreaterEqual(parsed.rendered_lines, 2, "the head and the drawn line are el's, not counted")

    def test_the_drawn_head_is_not_a_position_of_yours(self):
        run("log", "DECISION", "journal choice one")
        run()
        run("readme", "add", "decisions", "2026-10-08 · my rule")
        code, _, err = run("readme", "drop", "decisions", "2")
        self.assertEqual(code, 4)
        self.assertIn("1 line(s) of yours, nothing at position 2 — the decisions from the journal", err)
        self.assertIn(HEAD, self.decisions())

    def test_no_decision_no_block(self):
        run("readme", "touch")
        self.assertNotIn(HEAD, self.decisions())


if __name__ == "__main__":
    unittest.main()
