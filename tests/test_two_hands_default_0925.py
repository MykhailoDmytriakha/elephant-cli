"""Feedback 2026-09-25 (el 1.25.3), hole «the tool keeps the order»: two hands were opt-in by a Context line nobody writes,
so in a new case the agent ticked every item, Order said «every item ended → close it», and the phase closed by one hand.
Now a new case carries the rule from `case new` (a Context line the owner may drop), Order on a finished phase says
«a fresh session accepts first», and the close keeps refusing an unaccepted item. An old case without the line is left
as it is — the rule lives at the write door, never on the history."""
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
        os.environ["EL_TWO_HANDS"] = "1"
        self.project = Path(self.tmp.name).resolve()
        (self.project / "a.txt").write_text("a\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def case(self) -> Path:
        return next(p for p in (self.project / ".cases").iterdir() if p.is_dir())

    def finish_phase(self):
        run("phase", "open", "1", "Work", "--goal", "done [file: a.txt]")
        run("phase", "agree", "1", "one item, the file a.txt")
        run("todo", "add", "1", "item", "--expect", "[file: a.txt]")
        code, _, err = run("todo", "done", "1.1", "file:a.txt", "done")
        self.assertEqual(code, 0, err)
        run("log", "RESULT", "a.txt written")


class NewCase(Base):
    def test_case_new_writes_the_rule_into_context(self):
        run("case", "new", "demo", "--goal", "test")
        readme = (self.case() / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Context\ntest\n- rule: two hands", readme)

    def test_order_on_a_finished_phase_asks_for_acceptance_before_the_close(self):
        run("case", "new", "demo", "--goal", "test")
        self.finish_phase()
        out = run()[1]
        line = next(ln for ln in out.splitlines() if ln.startswith("- phase 1") and "every item ended" in ln)
        thread = next(ln for ln in out.splitlines() if ln.startswith("thread: "))
        self.assertIn("not accepted: el todo brief 1.1", thread, "the thread does not send the agent past the acceptance")
        self.assertIn("not accepted", line)
        self.assertIn("el todo brief 1.1", line)
        self.assertLess(line.index("el todo brief 1.1"), line.index("el phase close 1"), "accept first, then close")
        self.assertNotIn("done item(s) not accepted", out, "one line says it, not two")

    def test_the_close_refuses_one_hand_then_passes_after_acceptance(self):
        run("case", "new", "demo", "--goal", "test")
        self.finish_phase()
        code, _, err = run("phase", "close", "1", "outcome", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("not accepted", err)
        os.environ["EL_SESSION"] = "other1"
        run("todo", "accept", "1.1", "--by", "codex", "opened a.txt")
        os.environ.pop("EL_SESSION")
        code, _, err = run("phase", "close", "1", "outcome", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)

    def test_the_owner_may_drop_the_rule(self):
        run("case", "new", "demo", "--goal", "test")
        code, _, err = run("readme", "drop", "context", "1")  # the rule is the one list line of Context (the goal is prose)
        self.assertEqual(code, 0, err)
        self.finish_phase()
        code, _, err = run("phase", "close", "1", "outcome", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)

    def test_a_nested_case_carries_it_too(self):
        run("case", "new", "demo", "--goal", "test")
        run("phase", "open", "1", "Work", "--goal", "g")
        run("spawn", "side", "--goal", "s")
        child = next(p for p in self.case().iterdir() if p.is_dir() and p.name.endswith("side"))
        self.assertIn("- rule: two hands", (child / "README.md").read_text(encoding="utf-8"))


class OldCase(Base):
    def test_a_case_without_the_line_is_left_as_it_was(self):
        os.environ["EL_TWO_HANDS"] = "0"
        run("case", "new", "legacy habit", "--goal", "test")
        os.environ["EL_TWO_HANDS"] = "1"
        self.finish_phase()
        out = run()[1]
        self.assertIn("every item ended (1 done) → close it", out)
        code, _, err = run("phase", "close", "1", "outcome", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
