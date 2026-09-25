"""The owner's word, 2026-09-17: «el check returns warnings everywhere — do we need them, or errors only?».
Measured on the tool's own case: 66 check warnings — 46 old journal lines near the soft limit, 19 Decisions
lines over 150, 1 README size — and 21 stderr lines on a plain `readme touch` about old README lines; the agent
had learned to filter them out. Warnings stay (they show content the tool may not refuse) but: a write warns only
about what it introduced; the pointer limit applies to Links and State, not to Decisions; the soft F7 threshold
is said once at `el log`; `check` groups the soft layer once per rule with the line numbers."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "quiet", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "w [owner]")

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()


class WarningsAreAboutThisWrite(Base):
    def test_a_long_decisions_line_is_text_not_a_pointer_and_old_lines_never_echo(self):
        long = "2026-09-17 · " + "решение " * 25
        code, out, err = run("readme", "add", "decisions", long)
        self.assertEqual(code, 0)
        self.assertNotIn("pointer line", err, "Decisions is text: the byte limit bounds it, not the pointer limit")
        code, out, err = run("readme", "add", "links", "- " + "o" * 160)
        self.assertIn("pointer line is", err, "a long LINKS line is a pointer and warns — once, at this write")
        code, out, err = run("readme", "touch")
        self.assertEqual(err, "", f"an unrelated write echoes nothing about old lines: {err}")
        code, out, err = run("readme", "set", "next", "go on")
        self.assertNotIn("pointer line", err)

    def test_the_readme_size_warning_fires_once_when_crossed(self):
        for i in range(40):
            run("readme", "add", "context", f"строка контекста номер {i} " + "текст " * 30)
        code, out, err = run("readme", "add", "context", "ещё одна строка " + "текст " * 30)
        crossed = "of your text, over" in err
        # after the crossing, further writes are silent about the size — check names it
        code, out, err = run("readme", "touch")
        self.assertNotIn("of your text, over", err)
        code, out, err = run("check")
        self.assertIn("of your text, over", err, "history is check's business")
        self.assertTrue(crossed or "of your text, over" in run("check")[2])


class CheckGroupsTheSoftLayer(Base):
    def test_many_long_pointer_lines_are_one_line_per_rule(self):
        for i in range(5):
            run("readme", "add", "links", f"- long pointer number {i} " + "x" * (150 + i))
        code, out, err = run("check")
        self.assertEqual(err.count("pointer line"), 1, "one line per rule, not one per long line")
        self.assertIn("F2 · pointer line is N visible chars, over 150 — lines", err)  # 2026-09-25: the shared limit stays
        self.assertIn("(5 lines)", err)
        run("log", "RESULT", "х" * 190)
        code, out, err = run("check")
        self.assertNotIn("close to the limit", err, "the soft F7 threshold is not history")

    def test_a_single_line_keeps_its_own_numbers(self):
        # found on the tool's own case, 2026-09-25: «F2 · line 58 · pointer line is N visible chars, over N»
        run("readme", "add", "links", "- one long pointer " + "x" * 150)
        code, out, err = run("check")
        self.assertRegex(err, r"F2 · line \d+ · pointer line is \d+ visible chars, over 150")
        self.assertNotIn("over N", err)


if __name__ == "__main__":
    unittest.main()
