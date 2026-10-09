"""A Codex peer review of batch 21 before commit (2026-10-08): four findings, each a form of failure kept here."""
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
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="codex21", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          EL_TWO_HANDS="0")
        run("case", "new", "probe", "--goal", "g")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-probe"))
        run("phase", "open", "1", "First", "--goal", "first done")
        run("todo", "add", "1", "step one")
        run("todo", "add", "1.1", "probe: a path")
        run("todo", "add", "1.1", "probe: another path")
        run("todo", "cancel", "1.1.2", "not needed")
        run("todo", "done", "1.1.1", "run:a → ok", "a")
        run("todo", "done", "1.1", "run:one → ok", "one")
        run("phase", "close", "1", "first done", "--reflect", "r", "--align", "a")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class ThreeDigitTraces(Base):
    def test_a_swallowed_dollar_with_three_decimals_is_refused(self):
        run("phase", "open", "2", "Second", "--goal", "g")
        code, _, err = run("todo", "add", "2", "pay .345 to vendor")  # what zsh leaves of "pay $12.345 to vendor"
        self.assertEqual(code, 2)
        self.assertIn("orphan decimal", err)


class HistoryIsShownWhole(Base):
    def test_a_cancelled_sub_item_of_a_closed_phase(self):
        code, out, err = run("todo", "show", "1.1.2")
        self.assertEqual(code, 0, err)
        self.assertIn("another path", out)

    def test_a_padded_reference(self):
        code, out, err = run("todo", "show", "01.01")
        self.assertEqual(code, 0, err)
        self.assertIn("step one", out)

    def test_a_closed_phase_without_its_file_names_the_journal(self):
        (self.case / "phases" / "1-first.md").unlink()
        code, out, err = run("todo", "show", "1")
        last = out.rstrip("\n").split("\n")[-1]
        self.assertIn("phases/1-first.md is missing", last)
        self.assertIn("grep -n -A3 '· p1$'", last)
        self.assertNotIn("el todo add 1", out)


if __name__ == "__main__":
    unittest.main()
