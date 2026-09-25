"""Report of 2026-09-16 18:47 from a live coding case (el 1.16.0): phase 4 closed after a CART baseline and a
manual computation; 5.5 closed on HTTP 200 with benefits; the DEV trace then showed no PartnerPricing call and
zero discount fields; `el check` said 0 violations while the acceptance was open. Structure was whole, the
phase's promise was never written, and four criteria of one kind were satisfied by one run.
Now: acceptance is items — a criterion with words in `goal:` is covered by an item whose `expect:` carries the
same slot and proved by that item's `done`; Order names a criterion nobody works towards; `phase close` refuses
over an unproved promise; the Digest says which item proved which; `done` prints the promise next to the proof."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

GOAL = ("discount applied end to end [run: trace shows outbound PartnerPricingDiscLookup] "
        "[run: discount fields non-zero] [run: rerun shows the changed rate]")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ.pop("EL_HINTS", None)
        run("case", "new", "api", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")

    def gates_ok(self):
        run("log", "RESULT", "baseline: HTTP 200 with benefits and five cost rows")
        run("log", "DECISION", "reflect: name the criteria first")
        run("log", "DECISION", "align: phase 2 re-enables")


class AcceptanceIsItems(Base):
    def test_open_hints_the_criteria_and_order_names_the_uncovered_one(self):
        code, out, _ = run("phase", "open", "1", "Discount", "--goal", GOAL)
        self.assertIn("hint: the goal promises 3 proof(s) and 0 have an item — name each criterion as an item with the same slot", out)
        self.assertIn('--expect "[run: trace shows outbound PartnerPricingDiscLookup]"', out)
        run("todo", "add", "1", "see the outbound call in the trace", "--expect", "[run: trace shows outbound PartnerPricingDiscLookup]")
        order = run()[1].split("## Order")[1]
        self.assertNotIn("[run: trace shows outbound PartnerPricingDiscLookup] and no item", order)
        self.assertIn("phase 1 Discount promises [run: discount fields non-zero] and no item promises it — the criterion nobody works towards", order)
        self.assertIn('el todo add 1 "…" --expect "[run: discount fields non-zero]"', order)
        code, out, _ = run("phase", "open", "1")
        self.assertIn("already open", out)

    def test_close_refuses_over_an_unproved_promise_and_a_baseline_does_not_count(self):
        run("phase", "open", "1", "Discount", "--goal", GOAL)
        run("todo", "add", "1", "see the outbound call", "--expect", "[run: trace shows outbound PartnerPricingDiscLookup]")
        run("todo", "add", "1", "discount fields", "--expect", "[run: discount fields non-zero]")
        run("todo", "add", "1", "build the CART baseline")  # a step, no criterion
        run("todo", "done", "1.3", "run:curl router -> HTTP 200, five cost rows", "baseline found")
        run("todo", "done", "1.1", "run:grep trace -> outbound PartnerPricingDiscLookup groupId=0000000042", "the call is there")
        self.gates_ok()
        code, out, err = run("phase", "close", "1", "done")
        self.assertEqual(code, 4, "an unproved promise holds the phase, like an open item")
        self.assertIn("open items 1.2", err)
        self.assertIn("phase 1 promised [run: discount fields non-zero] — 1.2 promises it and is not proved with a run", err)
        self.assertIn("phase 1 promised [run: rerun shows the changed rate] and no done item proves it — name the criterion as an item", err)
        self.assertIn("or correct the promise: the goal line in phases/1-discount.md", err)
        # the baseline run on 1.3 proved nothing of the promise: three runs exist, one criterion is proved
        run("todo", "done", "1.2", "run:curl router -> discountAmount 12.40, discountPercentage 22.0", "non-zero")
        run("todo", "add", "1", "rerun", "--expect", "[run: rerun shows the changed rate]")
        run("todo", "done", "1.4", "run:curl router again -> totalDueAmount 43.60 (was 56.00)", "changed")
        code, out, err = run("phase", "close", "1", "discount applied")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-discount.md")
        self.assertIn("- phase promise: 3 of 3 proved — [run: trace shows outbound PartnerPricingDiscLookup] by 1.1 · "
                      "[run: discount fields non-zero] by 1.2 · [run: rerun shows the changed rate] by 1.4\n", pf)
        self.assertEqual(run("check")[0], 0)

    def test_done_prints_the_promise_next_to_the_proof(self):
        run("phase", "open", "1", "Discount", "--goal", "g")
        run("todo", "add", "1", "discount fields", "--expect", "[run: discount fields non-zero]")
        code, out, _ = run("todo", "done", "1.1", "run:curl router -> HTTP 200 with benefits", "got a 200")
        self.assertIn("expect 1.1: 1 of 1 filled — run", out)
        self.assertIn("  [run: discount fields non-zero] ← run curl router → HTTP 200 with benefits  — does it show that?", out)

    def test_a_goal_without_slots_is_untouched_and_a_planned_phase_promise_points_at_plan(self):
        run("phase", "open", "1", "Work", "--goal", "w")
        run("todo", "add", "1", "a")
        run("todo", "done", "1.1", "owner", "ok")
        self.gates_ok()
        self.assertEqual(run("phase", "close", "1", "closed")[0], 0)
        run("phase", "plan", "2", "Next", "--goal", "n [run: it works]")
        run("phase", "plan", "3", "Side", "--goal", "s [file: docs/x.md]")
        run("todo", "add", "3", "x", "--expect", "[file: docs/x.md]")
        (self.case / "docs").mkdir()
        (self.case / "docs" / "x.md").write_text("# x\nsummary: x\n", encoding="utf-8")
        run("todo", "done", "3.1", "file:docs/x.md", "written")
        run("log", "--phase", "3", "RESULT", "r")
        run("log", "--phase", "3", "DECISION", "reflect: r")
        run("log", "--phase", "3", "DECISION", "align: a")
        code, out, err = run("phase", "close", "3", "side done")
        self.assertEqual(code, 0, f"out of turn, promise proved by 3.1: {err}")
        self.assertIn("phase promise: 1 of 1 proved — [file: docs/x.md] by 3.1", self.read("phases/3-side.md"))


if __name__ == "__main__":
    unittest.main()
