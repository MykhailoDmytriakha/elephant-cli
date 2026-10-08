"""The polygon of 2026-10-07: agents read el's output from one end. Of 1587 el calls in the runs, 22 % went through
`tail -1` and 22 % through `head -N`; 84 of 190 refusals reached the agent as the legend line alone — `exit 2 = wrong
usage — el help errors` — the reason and the door cut off. A refusal reads from both ends now: the first line says what
is wrong, the last line is the door; whatever el adds goes between them."""
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
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="ends1007", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "ends test", "--goal", "g")
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")
        run("todo", "add", "1", "a step", "--expect", "[run: probe → ok]")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    @staticmethod
    def lines(text):
        return [ln for ln in text.rstrip("\n").split("\n") if ln.strip()]


class TheLastLineIsTheDoor(Base):
    def test_a_list_refusal_ends_with_a_blocker_and_its_command_not_the_legend(self):
        code, _, err = run("phase", "close", "1", "s")
        self.assertEqual(code, 4)
        lines = self.lines(err)
        self.assertTrue(lines[0].startswith("el: ERROR [exit 4] cannot close phase 1:"), lines[0])
        self.assertIn("exit 4 = precondition not met, nothing was written", lines[1], "the legend under the reason")
        self.assertNotIn("exit 4 =", lines[-1], "tail -1 is never the legend alone")
        self.assertIn("el todo done", lines[-1], "tail -1 names a command")

    def test_a_refusal_with_a_recovery_ends_with_it(self):
        code, _, err = run("feedback")
        self.assertEqual(code, 2)
        self.assertTrue(self.lines(err)[-1].startswith("  recovery: el help feedback"), self.lines(err)[-1])

    def test_a_one_line_refusal_is_the_reason_and_the_door_at_once(self):
        code, _, err = run("todo", "add", "3", "x")
        self.assertEqual(code, 4)
        [line] = self.lines(err)
        self.assertIn("phase 3 does not exist yet", line)
        self.assertIn("el phase plan 2", line)

    def test_what_el_adds_goes_above_the_door(self):
        run("todo", "add", "3", "x")
        code, _, err = run("todo", "add", "3", "y")
        lines = self.lines(err)  # pm-haiku-9: a question set above the line was all a `head -1` reader saw
        self.assertTrue(lines[0].startswith("el: ERROR [exit 4] phase 3 does not exist yet"), lines[0])
        self.assertIn("el phase plan 2", lines[0], "the reason and the door, first")
        self.assertIn("the same wall 2 times this session", lines[-1], "the second hit asks the question")
        run("phase", "close", "1", "s")
        code, _, err = run("phase", "close", "1", "s")
        lines = self.lines(err)
        self.assertIn("the same wall 2 times this session", err)
        self.assertNotIn("the same wall", lines[-1])
        self.assertIn("el todo done", lines[-1])

    def test_the_wall_record_keeps_the_reason_first(self):
        run("todo", "add", "3", "x")
        run("todo", "add", "3", "y")
        code, out, _ = run("feedback", "--wall")
        self.assertIn("1 [exit 4] phase 3 does not exist yet", out)
        self.assertIn("2 [exit 4] phase 3 does not exist yet", out, "the question el added is not the wall")

    def test_the_entry_refusal_ends_with_its_recovery(self):
        bare = tempfile.TemporaryDirectory()
        self.addCleanup(bare.cleanup)
        os.chdir(bare.name)  # no `.cases/` upwards
        code, out, _ = run()
        self.assertEqual(code, 4)
        lines = self.lines(out.split("start here")[0])
        self.assertTrue(lines[0].startswith("el: ERROR [exit 4] no `.cases/`"), lines[0])
        self.assertTrue(lines[-1].startswith("  recovery: "), lines[-1])


class TwoBlockersStayTwoWalls(unittest.TestCase):
    def test_the_legend_under_a_list_head_does_not_merge_walls(self):
        from elephant import store
        c = store.wall_key("el: ERROR [exit 4] cannot close phase 1:\n  exit 4 = precondition not met\n  phase 1: open items 1.2")
        d = store.wall_key("el: ERROR [exit 4] cannot close phase 1:\n  exit 4 = precondition not met\n  phase 1: no RESULT")
        self.assertNotEqual(c, d)


if __name__ == "__main__":
    unittest.main()
