"""The live migration of 2026-10-07: a map case and forty-one nested cases. The first session filled every child,
confirmed the map's State last (`readme touch` — no journal line) and stopped; three items of the map waited for a
second hand. The next session had no hand of its own, followed the freshest journal into a finished child, read
«other open cases» as forty-two equal names, and asked the owner what to do. Two sessions later the run stopped with
the map's acceptance never done. The hand of a fresh session is the case written last, by any of its three files; the
entry names a tree by its top."""
import os
import tempfile
import time
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
        os.environ.update(EL_HINTS="0", EL_SESSION="tree-first", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "research map", "--goal", "every research in one place")
        run("phase", "open", "1", "Structure", "--goal", "one research, one case")
        for name in ("speed", "quality", "memory"):
            run("--case", "research-map", "spawn", name, "--goal", f"what was tried for {name}")
        time.sleep(0.02)
        run("--case", "speed", "log", "DECISION", "a correction in the child's journal")
        time.sleep(0.02)
        run("--case", "research-map", "readme", "touch")  # the last write: the map's README, no journal line

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class AFreshSessionLandsWhereTheLastAgentStopped(Base):
    def test_the_case_written_last_is_in_hand_not_the_freshest_journal(self):
        os.environ["EL_SESSION"] = "tree-second"
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn("el · case in hand: ", out)
        head = out.split("\n")[0]
        self.assertTrue(head.endswith("research-map"), head)


class TheEntryNamesATreeByItsTop(Base):
    def test_children_are_counted_under_their_parent(self):
        os.environ["EL_SESSION"] = "tree-third"
        run("case", "new", "side errand", "--goal", "a case of its own")
        run("case", "use", "research-map")
        code, out, _ = run()
        line = next(ln for ln in out.split("\n") if ln.startswith("other open cases:"))
        self.assertIn("side-errand", line)
        self.assertNotIn("speed", line, "a child is reached through its parent")

    def test_in_a_child_the_parent_carries_the_siblings(self):
        os.environ["EL_SESSION"] = "tree-fourth"
        run("case", "use", "speed")
        code, out, _ = run()
        line = next(ln for ln in out.split("\n") if ln.startswith("other open cases:"))
        self.assertIn("research-map (+2 open nested — el case list)", line)
        self.assertNotIn("quality", line)


if __name__ == "__main__":
    unittest.main()
