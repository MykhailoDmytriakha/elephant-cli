"""Feedback of 2026-09-14 14:17 (a court case in root mode): a planned phase that ran alongside
phase 1 and finished first had no honest end — `open` refused (phases run in order), `close`
refused (never opened), `cancel` would call finished work «not needed»; and a phase whose every
item ended stood open while `order` said everything was in place."""
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
        run("case", "new", "demo case", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class PhaseOutOfTurn(Base):
    """First report: phase 4 (an old matter of 2024) depended on nothing, ran next to phase 1 and
    ended first; every legal command was refused."""

    def plan_side_branch(self):
        run("todo", "add", "1", "answer the court")
        run("phase", "plan", "2", "Data", "--goal", "collect")
        run("phase", "plan", "3", "Hearing", "--goal", "defer")
        run("phase", "plan", "4", "Old case", "--goal", "debt or no debt")
        run("todo", "add", "4", "open the portal, read the status")
        run("todo", "add", "4", "if a debt: the bank statement")
        run("todo", "add", "4", "letter to the court")
        code, out, err = run("todo", "done", "4.1", "closed 2024-07-22, no debt")
        self.assertEqual(code, 0, err)
        code, out, err = run("todo", "cancel", "4.2, 4.3", "no debt — nothing to show, nobody to write")
        self.assertEqual(code, 0, err)

    def test_open_out_of_turn_names_the_nested_case(self):
        self.plan_side_branch()
        code, out, err = run("phase", "open", "4")
        self.assertEqual(code, 4)
        self.assertIn("phases run in order", err)
        self.assertIn("el spawn", err)

    def test_a_finished_side_branch_closes_from_the_plan(self):
        self.plan_side_branch()
        code, out, err = run("phase", "close", "4", "no debt: the court closed it 2024-07-22")
        self.assertEqual(code, 4, "the gates still apply")
        self.assertIn('el log --phase 4 DECISION "reflect:', err)
        self.assertNotIn("never opened", err)
        self.assertFalse((self.case / "phases" / "4-old-case.md").exists(), "a refused close writes nothing")
        run("log", "--phase", "4", "DECISION", "reflect: check the portal before writing letters")
        run("log", "--phase", "4", "DECISION", "align: phase 2 loses the 2024 items")
        code, out, err = run("phase", "close", "4", "no debt: the court closed it 2024-07-22")
        self.assertEqual(code, 0, err)
        self.assertIn("out of turn", out)
        self.assertIn("el spawn", out)
        todo = self.read("TODO.md")
        self.assertIn("- [x] 4 Old case — no debt: the court closed it 2024-07-22 ·", todo)
        self.assertIn("- [ ] 1 Work", todo)
        self.assertIn("- [ ] 2 Data — collect", todo)
        pf = self.read("phases/4-old-case.md")
        self.assertIn("goal: debt or no debt", pf)
        self.assertIn("result: no debt: the court closed it 2024-07-22", pf)
        self.assertIn("- 4.1 ✓ open the portal", pf)
        self.assertIn("шла параллельно фазе 1", self.read("JOURNAL.md"))
        self.assertIn("progress: 1 Work ▶ · 2 Data · 3 Hearing · 4 Old case ✓", self.read("README.md"))
        self.assertEqual(run("check")[0], 0)
        # the pipeline is intact: phase 2 still opens only after phase 1 closed
        code, out, err = run("phase", "open", "2")
        self.assertEqual(code, 4)
        self.assertIn("phase 1 Work is still open", err)

    def test_a_planned_phase_with_open_items_still_has_no_close(self):
        run("phase", "plan", "2", "Data", "--goal", "collect")
        run("todo", "add", "2", "ask the police")
        code, out, err = run("phase", "close", "2", "done")
        self.assertEqual(code, 4)
        self.assertIn("out of turn", err)
        self.assertIn("open items 2.1", err)
        self.assertFalse((self.case / "phases" / "2-data.md").exists())

    def test_the_pipeline_path_stays_open_first(self):
        """Feedback 2026-09-09 holds: when the phase COULD open, it opens first, then closes."""
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")
        run("phase", "close", "1", "done")
        run("phase", "plan", "2", "UAT", "--goal", "rollout")
        run("todo", "add", "2", "migrate")
        run("todo", "done", "2.1", "12 tables")
        code, out, err = run("phase", "close", "2", "rolled out")
        self.assertEqual(code, 4)
        self.assertIn("was planned and never opened", err)
        self.assertIn("el phase open 2", err)


class OrderSeesEndedItems(Base):
    """Second report: every item of phase 4 ended, the phase stood open, `order` said ✓."""

    def test_every_item_ended_is_named_with_the_close_and_what_it_needs(self):
        run("todo", "add", "1", "answer the court")
        run("todo", "add", "1", "ask the police")
        self.assertNotIn("every item ended", run("order")[1])
        run("todo", "done", "1.1", "answered")
        self.assertNotIn("every item ended", run("order")[1], "1.2 is still open")
        run("todo", "cancel", "1.2", "not needed")
        out = run("order")[1]
        self.assertIn("phase 1 Work: every item ended (1 done) → close it: el phase close 1", out)
        self.assertIn('first: el log --phase 1 DECISION "reflect: …" · el log --phase 1 DECISION "align: …"', out)
        self.assertIn("or add what is missing: el todo add 1", out)
        self.assertIn("every item ended", run()[1], "the entry screen shows it too")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")
        out = run("order")[1]
        self.assertIn('every item ended (1 done) → close it: el phase close 1 "what came out" · or add', out)
        code, o, err = run("phase", "close", "1", "answered")
        self.assertEqual(code, 0, err)
        self.assertNotIn("every item ended", run("order")[1])

    def test_a_planned_phase_out_of_turn_gets_the_same_line(self):
        run("todo", "add", "1", "answer the court")
        run("phase", "plan", "2", "Old case", "--goal", "debt or no debt")
        run("todo", "add", "2", "open the portal")
        run("todo", "done", "2.1", "no debt")
        run("log", "--phase", "2", "DECISION", "reflect: x")
        run("log", "--phase", "2", "DECISION", "align: y")
        out = run("order")[1]
        self.assertIn('phase 2 Old case: every item ended (1 done) → close it: el phase close 2 "what came out" · or add', out)
        code, o, err = run("phase", "close", "2", "no debt")
        self.assertEqual(code, 0, err)
        self.assertNotIn("every item ended", run("order")[1])

    def test_a_phase_with_no_items_says_nothing(self):
        self.assertNotIn("every item ended", run("order")[1])


if __name__ == "__main__":
    unittest.main()
