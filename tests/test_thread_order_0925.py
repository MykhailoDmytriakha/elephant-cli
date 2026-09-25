"""A live report, 2026-09-25 («move B»): the entry had two directions — the thread led to the item and to State `next:`,
while Order below asked to put a debt back first; the agent read both and followed the one on top. The principle the owner
took in 1.26.0 — a hint never leads past a gate — now holds for the thread as a whole: the first Order line it has not
named yet is a step of the thread, before `next:`. One vector on the screen."""
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
        run("case", "new", "api", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g [owner]")
        run("todo", "add", "1", "build it", "--expect", "[owner]")
        run("readme", "set", "next", "build it, then open phase 2")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def thread(self) -> str:
        return next(ln for ln in run()[1].splitlines() if ln.startswith("thread: "))


class OneVector(Base):
    def test_a_debt_in_order_is_a_step_of_the_thread_before_next(self):
        (self.case / "notes.md").write_text("# Notes\n\nno summary line here\n", encoding="utf-8")
        out = run()[1]
        self.assertIn("## Order — ", out)
        thread = self.thread()
        self.assertIn("first: Order «", thread)
        self.assertIn("notes.md", thread, "the thread names the debt itself, not only that there is one")
        self.assertLess(thread.index("first: Order"), thread.index("next: «"), "the debt first, then the plan")

    def test_a_clean_order_leaves_the_thread_as_it_was(self):
        self.assertIn("## Order\n- ✓", run()[1])
        self.assertNotIn("first: Order", self.thread())

    def test_a_gate_the_thread_already_names_is_not_named_twice(self):
        os.environ["EL_TWO_HANDS"] = "1"
        run("readme", "add", "context", "rule: two hands — the owner agrees each phase's scope, a fresh session accepts each done item")
        run("phase", "agree", "1", "one item")
        run("todo", "done", "1.1", "owner", "built")
        thread = self.thread()
        self.assertEqual(thread.count("el todo brief 1.1"), 1, thread)
        self.assertNotIn("first: Order «phase 1", thread)


if __name__ == "__main__":
    unittest.main()
