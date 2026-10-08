"""The polygon of 2026-10-07: what to do now comes first on entry.

Fresh agents (Haiku 5.5, Sonnet 5.5) read the entry as `el 2>&1 | head -60`. On a case of 63 files the entry was 21K
chars, and Order and the hint — printed last, because a model weighs the last line most — were never on the screen
they read. The owner's word: «turn it over». The thread, the counts, Order and the hint stand first; a mark line says
where the case on disk begins; an overflow cuts the body, never the head."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from elephant import commands
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "1"
        os.environ["EL_SESSION"] = "entry1007"
        run("case", "new", "research move", "--goal", "g")
        run("phase", "open", "1", "Inventory", "--goal", "the sources are counted [run: make count → 4]")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def entry(self):
        code, out, err = run()
        self.assertEqual(code, 0, err)
        return out.split("\n")


class EntryFirst(Base):
    def test_order_and_the_hint_stand_above_the_case_body(self):
        lines = self.entry()
        mark = lines.index(commands.ENTRY_BODY_MARK)
        order = next(i for i, ln in enumerate(lines) if ln.startswith("## Order"))
        hint = next(i for i, ln in enumerate(lines) if ln.startswith("hint: "))
        readme = next(i for i, ln in enumerate(lines) if ln.startswith("# research move"))
        self.assertLess(order, mark)
        self.assertLess(hint, mark)
        self.assertLess(mark, readme, "README follows the mark")

    def test_a_big_case_still_shows_order_in_the_first_60_lines(self):
        for k in range(30):  # a case the size the polygon met: many decisions, many items
            run("readme", "add", "decisions", f"2026-10-07 · decision {k} about the layout of the research archive, with its reason")
            run("todo", "add", "1", f"digest of source group {k}", "--expect", "[file: research/x.md]")
        head = self.entry()[:60]
        self.assertTrue(any(ln.startswith("## Order") for ln in head), "Order within `head -60`")
        self.assertTrue(any(ln.startswith("hint: ") for ln in head), "the hint within `head -60`")

    def test_an_overflow_cuts_the_body_and_keeps_the_head(self):
        old = commands.MAX_SCREEN
        commands.MAX_SCREEN = 1500
        try:
            for k in range(20):
                run("readme", "add", "decisions", f"2026-10-07 · decision {k} about the layout of the research archive")
            out = "\n".join(self.entry())
        finally:
            commands.MAX_SCREEN = old
        self.assertIn("## Order", out)
        self.assertIn("[body truncated at", out)
        self.assertLess(out.index("## Order"), out.index("[body truncated at"))
        self.assertTrue(out.rstrip().split("\n")[-1].startswith("how to work:"), "the footer stays")


class ReadmeIsALighterEntry(Base):
    """Two re-entries of four came in through `el readme | head -60` (pm-haiku-4): the head goes with it."""

    def test_bare_readme_shows_the_head_above_the_readme(self):
        code, out, err = run("readme")
        self.assertEqual(code, 0, err)
        lines = out.split("\n")
        order = next(i for i, ln in enumerate(lines) if ln.startswith("## Order"))
        readme = next(i for i, ln in enumerate(lines) if ln.startswith("# research move"))
        self.assertLess(order, readme)
        self.assertTrue(any(ln.startswith("thread: ") for ln in lines[:order]))

    def test_bare_readme_does_not_wait_on_an_open_empty_stdin(self):
        # a harness ran commands with a stdin that stays open and empty; `el readme` read it and hung for good
        script = Path(__file__).resolve().parent.parent / "elephant.py"
        p = subprocess.Popen([sys.executable, str(script), "readme"], stdin=subprocess.PIPE,  # stdin stays open
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            self.fail("el readme waited on an open stdin")
        finally:
            p.stdin.close()
        self.assertIn("# research move", p.stdout.read())


class ASumIsNotAnItem(Base):
    def test_a_cost_or_a_version_in_the_journal_does_not_move_the_next_number(self):
        # the polygon's own case, 2026-10-07: «$1.27» in a RESULT made the next item 1.28
        run("log", "DECISION", "Haiku run cost $1.27, el v1.42 kept, 1.5% of the limit")
        code, out, err = run("todo", "add", "1", "the next step")
        self.assertEqual(code, 0, err)
        self.assertIn("added: 1.1 ", out)

    def test_a_time_or_a_measure_in_the_journal_does_not_move_the_next_number(self):
        # reported through `el feedback --wall` by the maintainer's own session, 2026-10-07: «сбой 16.09» (a time) in a
        # headline made the next item of phase 16 «16.10»; «16.639s» is a test run's duration
        run("log", "DECISION", "the run failed at 1.09, the suite took 1.639s")
        code, out, err = run("todo", "add", "1", "the next step")
        self.assertIn("added: 1.1 ", out)

    def test_an_item_the_journal_speaks_of_still_keeps_its_number(self):
        run("log", "DECISION", "1.3 was dropped earlier — the number stays taken")
        code, out, err = run("todo", "add", "1", "the next step")
        self.assertIn("added: 1.4 ", out)


if __name__ == "__main__":
    unittest.main()
