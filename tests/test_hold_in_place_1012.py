"""A hold is a state, not a move (the owner's word, 2026-10-12, on a live report): held items were drawn last in their
phase, the file kept the drawn order, and an item held for a day and resumed stayed after the others for good — 5.2 done,
5.3 open, 5.1 done. A held item now stays where it stands, `[~]` in its place, in TODO, at the entry and in `move`."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class HoldKeepsThePlace(unittest.TestCase):
    KEYS = ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_CASE")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="hold1012", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "engine", "--goal", "x")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-engine"))
        run("phase", "open", "1", "Work", "--goal", "x")
        for k in (1, 2, 3):
            run("todo", "add", "1", f"step {k}")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def order(self, text=None):
        text = text if text is not None else (self.case / "TODO.md").read_text(encoding="utf-8")
        return [m.group(1) for m in re.finditer(r"^  - \[.\] (\d+\.\d+) ", text, re.M)]

    def test_the_reports_acceptance(self):  # hold 1.1, done 1.2, resume 1.1, done 1.1 → 1.1, 1.2, 1.3
        run("todo", "hold", "1.1", "waiting for: a key")
        self.assertEqual(self.order(), ["1.1", "1.2", "1.3"])
        self.assertIn("  - [~] 1.1 step 1 — hold: waiting for: a key", (self.case / "TODO.md").read_text(encoding="utf-8"))
        run("todo", "done", "1.2", "run:t → ok", "two")
        run("todo", "resume", "1.1")
        run("todo", "done", "1.1", "run:t → ok", "one")
        self.assertEqual(self.order(), ["1.1", "1.2", "1.3"])

    def test_the_entry_and_move_keep_the_place(self):
        run("todo", "hold", "1.2", "waiting for: a reply")
        _, out, _ = run()
        self.assertEqual(self.order(out), ["1.1", "1.2", "1.3"])
        code, out, err = run("todo", "move", "1.3", "1.1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.order(out), ["1.3", "1.1", "1.2"])


if __name__ == "__main__":
    unittest.main()
