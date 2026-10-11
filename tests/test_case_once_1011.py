"""`--case` acts on one call (a live report, 2026-10-10: `el --case <nested> log RESULT …` moved the session's hand to the
nested case, the same flag on a top case did not, and the next plain `el todo done` landed in the nested case; the
owner's word, 2026-10-11: «maybe they are right — switching the hand should work explicitly, another way»)."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class ACaseFlagIsOneCall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="once1011", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "engine", "--goal", "x")
        self.top = next(Path(self.tmp.name, ".cases").glob("*-engine"))
        run("phase", "open", "1", "Find", "--goal", "x")
        run("spawn", "storage", "--goal", "y")  # the session now holds the nested case it spawned
        self.nested = next(self.top.glob("*-storage"))
        run("case", "use", self.top.name)  # and takes the top back, explicitly

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_a_write_named_by_case_on_a_nested_case_leaves_the_hand(self):
        code, out, err = run("--case", self.nested.name, "log", "RESULT", "found the cause")
        self.assertEqual(code, 0, err)
        self.assertIn(f"hand: stays on {self.top.name}", out)
        self.assertTrue(run()[1].split("\n")[0].endswith(self.top.name))

    def test_case_use_is_the_explicit_switch(self):
        run("case", "use", self.nested.name)
        self.assertIn(self.nested.name, run()[1].split("\n")[0])


if __name__ == "__main__":
    unittest.main()
