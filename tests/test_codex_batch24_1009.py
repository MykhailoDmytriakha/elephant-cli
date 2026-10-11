"""A Codex review of batch 24 (the fork) before commit, 2026-10-09: twelve findings, each a form of failure kept here."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

CLOSE = ("phase", "close", "1", "ok", "--reflect", "r", "--align", "a", "--howto", "none: t")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="codex24", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"), EL_TWO_HANDS="0")
        run("case", "new", "review", "--goal", "x")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-review"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def items(self, *specs):
        for text, expect in specs:
            run("todo", "add", "1", text, "--expect", expect)

    def journal(self):
        return (self.case / "JOURNAL.md").read_text(encoding="utf-8")


class AnUnusedSideTakesNothing(Base):
    """2: the flat count gave both proofs to the fork, and the independent [ref: b] was left unproved."""

    def test_the_phase_closes_with_the_fork_by_a_and_b_by_its_own(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]; [ref: b]")
        self.items(("a", "[ref: a]"), ("b", "[ref: b]"))
        run("todo", "done", "1.1", "ref:a", "a")
        run("todo", "done", "1.2", "ref:b", "b")
        code, _, err = run(*CLOSE)
        self.assertEqual(code, 0, err)

    def test_the_case_closes_too(self):
        run("readme", "edit", "context", "goal", "[ref: a] | [ref: b]; [ref: b]")
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] [ref: b]")
        self.items(("a", "[ref: a]"), ("b", "[ref: b]"))
        run("todo", "done", "1.1", "ref:a", "a")
        run("todo", "done", "1.2", "ref:b", "b")
        run(*CLOSE)
        code, _, err = run("done", "ok")
        self.assertEqual(code, 0, err)


class TheAdviceDoesNotEndWorkAnotherPromiseNeeds(Base):
    """3: «cancel 1.2» was printed for the only carrier of a mandatory [run: required]."""

    def test_an_item_carrying_another_open_promise_is_not_named(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]; [run: required]")
        self.items(("a", "[ref: a]"), ("b", "[ref: b] [run: required]"))
        code, out, _ = run("todo", "done", "1.1", "ref:a", "a")
        self.assertNotIn("el todo cancel 1.2", out)
        self.assertNotIn("the point has passed", run()[1])


class TheCancelRecordsOnlyATruePoint(Base):
    def setUp(self):
        super().setUp()
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]")
        self.items(("a", "[ref: a]"), ("b", "[ref: b]"))
        run("todo", "done", "1.1", "ref:a", "a")

    def test_4_cancelling_the_winner_too_decides_nothing(self):
        run("todo", "cancel", "1.1-1.2", "neither wanted")
        self.assertNotIn("развилка", self.journal())


class SweptSubItemsAndManyForks(Base):
    def test_9_a_swept_sub_item_records_the_point(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]")
        self.items(("a", "[ref: a]"), ("parent", "[owner]"))
        run("todo", "add", "1.2", "b", "--expect", "[ref: b]")
        run("todo", "done", "1.1", "ref:a", "a")
        run("todo", "cancel", "1.2", "a wins")
        self.assertIn("развилка [ref: a] | [ref: b] решена", self.journal())

    def test_9_two_forks_in_one_cancel_record_both(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]; [run: c] | [run: d]")
        self.items(("a", "[ref: a]"), ("c", "[run: c]"), ("b", "[ref: b]"), ("d", "[run: d]"))
        run("todo", "done", "1.1", "ref:a", "a")
        run("todo", "done", "1.2", "run:c → ok", "c")
        run("todo", "cancel", "1.3-1.4", "chosen")
        self.assertIn("развилка [ref: a] | [ref: b] решена", self.journal())
        self.assertIn("развилка [run: c] | [run: d] решена", self.journal())


class TheHintReadsStructureNotText(Base):
    def setUp(self):
        super().setUp()
        os.environ["EL_HINTS"] = "1"

    def hint(self, out):
        return next(ln for ln in out.split("\n") if ln.startswith("hint:"))

    def test_1_identical_forks_do_not_crash_the_open(self):
        run("phase", "open", "1", "First", "--goal", "x")
        run("phase", "plan", "2", "Proof", "--goal", "[owner] | [ref: a]; [owner] | [ref: a]")
        run("todo", "add", "2", "ask owner", "--expect", "[owner]")
        run("todo", "done", "2.1", "owner", "approved")
        code, _, err = run("phase", "open", "2", "--why", "independent")
        self.assertEqual(code, 0, err)

    def test_6_a_bar_inside_one_slot_is_one_criterion(self):
        _, out, _ = run("phase", "open", "1", "Proof", "--goal", "[ref: a | b]")
        self.assertIn('--expect "[ref: a | b]"', self.hint(out))

    def test_7_the_near_path_names_fork_branches_apart(self):
        run("phase", "plan", "1", "Proof", "--goal", "[ref: x] | [ref: y]; [run: test]")
        run("todo", "add", "1", "tests", "--expect", "[run: test all]")
        _, out, _ = run("phase", "open", "1")
        hint = self.hint(out)
        self.assertNotIn('--expect "[ref: x] | [ref: y]"', hint)
        self.assertIn('--expect "[ref: x]"', hint)

    def test_5_a_quote_inside_a_slot_survives_the_printed_command(self):
        run("phase", "open", "1", "Proof", "--goal", '[ref: "a"] | [ref: b]')
        line = next(ln for ln in run()[1].split("\n") if "no item promises either side" in ln)
        self.assertIn("""--expect '[ref: "a"]'""", line)


class ABareSideIsASide(Base):
    """8: an [owner] carrier left the fork «no item promises either side», and its proof named no item."""

    def test_the_owner_side_is_carried_and_named_when_proved(self):
        run("phase", "open", "1", "Proof", "--goal", "[owner] | [ref: b]")
        self.items(("ask owner", "[owner]"))
        self.assertNotIn("no item promises either side", run()[1])
        self.items(("b", "[ref: b]"))
        code, out, _ = run("todo", "done", "1.1", "owner", "approved")
        self.assertIn("is decided — [owner] by 1.1; the other side's 1.2 still open", out)


class AnIdenticalSideIsHeldByPosition(Base):
    def test_10_the_second_item_of_a_same_slot_fork_is_named(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: a]")
        self.items(("first", "[ref: a]"), ("second", "[ref: a]"))
        _, out, _ = run("todo", "done", "1.1", "ref:a", "a")
        self.assertIn("the other side's 1.2 still open", out)


class ARealPhaseZero(Base):
    def test_11_phase_zero_says_the_point_and_records_it(self):
        run("phase", "open", "0", "Proof", "--goal", "[ref: a] | [ref: b]")
        run("todo", "add", "0", "a", "--expect", "[ref: a]")
        run("todo", "add", "0", "b", "--expect", "[ref: b]")
        _, out, _ = run("todo", "done", "0.1", "ref:a", "a")
        self.assertIn("the other side's 0.2 still open", out)
        run("todo", "cancel", "0.2", "a wins")
        self.assertIn("развилка [ref: a] | [ref: b] решена", self.journal())


class TheWordHintSpeaksOfPromisesOnly(Base):
    def test_12_quoted_examples_and_rules_are_not_promises(self):
        _, out, _ = run("readme", "add", "context", "example: `[ref: a] or [ref: b]`")
        self.assertNotIn("fork?", out)
        _, out, _ = run("readme", "add", "context", "rule: [ref: a] or [ref: b]")
        self.assertNotIn("fork?", out)

    def test_12_an_unchanged_plan_does_not_repeat_it(self):
        run("phase", "plan", "1", "Proof", "--goal", "[ref: a] or [ref: b]")
        _, out, _ = run("phase", "plan", "1", "Proof", "--goal", "[ref: a] or [ref: b]")
        self.assertNotIn("fork?", out)


class TheSecondRound(Base):
    """The second review of batch 24, 2026-10-09: six edges the first fixes left."""

    def test_1_a_standalone_bare_promise_comes_before_a_fork(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [owner]; [ref]")
        self.items(("a", "[ref: a]"), ("sign", "[owner]"))
        run("todo", "done", "1.1", "ref:a", "a")
        run("todo", "done", "1.2", "owner", "approved")
        code, _, err = run(*CLOSE)
        self.assertEqual(code, 0, err)

    def test_2_one_proof_is_not_counted_twice_by_the_case(self):
        run("readme", "edit", "context", "goal", "[owner]; [owner: a] | [ref: b]")
        run("phase", "open", "1", "Proof", "--goal", "[owner: a]")
        self.items(("a", "[owner: a]"))
        run("todo", "done", "1.1", "owner", "approved")
        run(*CLOSE)
        code, _, err = run("done", "ok")
        self.assertEqual(code, 4, err)

    def test_3_a_parent_whose_sub_item_carries_a_mandatory_promise_is_not_named(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]; [run: required]")
        self.items(("a", "[ref: a]"), ("b", "[ref: b]"))
        run("todo", "add", "1.2", "required", "--expect", "[run: required]")
        _, out, _ = run("todo", "done", "1.1", "ref:a", "a")
        self.assertNotIn("el todo cancel 1.2", out)

    def test_4_the_parent_of_the_winner_is_not_named_and_its_cancel_decides_nothing(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]")
        self.items(("parent", "[ref: b]"))
        run("todo", "add", "1.1", "a", "--expect", "[ref: a]")
        _, out, _ = run("todo", "done", "1.1.1", "ref:a", "a")
        self.assertNotIn("el todo cancel 1.1", out)
        run("todo", "cancel", "1.1", "a wins")
        self.assertNotIn("развилка", self.journal())

    def test_5_a_winner_that_loses_its_proof_after_the_cancel_decides_nothing(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]; [ref: a]")
        self.items(("first", "[ref: a]"), ("second", "[ref: a]"), ("b", "[ref: b]"))
        run("todo", "done", "1.1", "ref:first", "first")
        run("todo", "done", "1.2", "ref:second", "second")
        run("todo", "cancel", "1.1,1.3", "changed")
        self.assertNotIn("развилка", self.journal())

    def test_6_the_printed_command_names_the_kind(self):
        run("phase", "open", "1", "Proof", "--goal", "[ref: a] | [ref: b]")
        self.items(("a", "[ref: a]"))
        _, _, err = run(*CLOSE)
        fork = next(ln for ln in err.split("\n") if "promised the fork" in ln)
        self.assertIn("el todo done 1.1 ref:… ", fork)
        self.assertNotIn("<kind>", fork)


if __name__ == "__main__":
    unittest.main()
