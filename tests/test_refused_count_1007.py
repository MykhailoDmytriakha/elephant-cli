"""The live migration of 2026-10-07: el refused 31 commands of one session — a README rewrite, twenty-four ticks on
items of closed phases — and a helper script sent every refusal to /dev/null. The agent verified its work with
`el check --all | tail -1`, read «violations: 0 · warnings: 0» and reported the migration done and clean. The files were
whole — a refusal writes nothing — but the work the agent believed it did was not there. The line read to verify names
what never landed."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class TheVerifyingLineNamesTheRefusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="refused1007", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "probe", "--goal", "g")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_a_clean_session_says_nothing_more(self):
        code, out, _ = run("check")
        self.assertEqual(code, 0)
        self.assertNotIn("refused this session", out)
        self.assertNotIn("refused this session", run("order")[1])

    def test_check_and_order_name_what_never_landed(self):
        run("todo", "add", "3", "an item for a phase that does not exist")
        run("todo", "add", "3", "another one")
        code, out, _ = run("check")
        self.assertEqual(code, 0, "the files are whole: check stays green")
        last = out.rstrip("\n").split("\n")[-1]
        self.assertIn("violations: 0 · warnings: 0 · refused this session: 2 command(s) — el feedback --wall lists them", last)
        self.assertLess(last.index("refused this session"), 140, "inside what `| cut -c1-140` keeps")
        self.assertIn("order: ✓ everything in place · refused this session: 2 command(s)", run("order")[1])


if __name__ == "__main__":
    unittest.main()
