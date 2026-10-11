"""A goal kept by either side (a live errand, 2026-10-08: «the parcel in hand [file: photo] or a claim filed [ref: number]» —
el read two promises and the close asked for both; the agent's way out was to narrow the goal after the fact). The owner's
word, 2026-10-09: take the fork `[a] | [b]`, and «A or B always has a point where it is decided — hold that point»: the
moment one side is proved, el names the other side's items; ending one with its reason records the point in the journal."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="fork1009", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"), EL_TWO_HANDS="0")
        run("case", "new", "errand", "--goal", "the parcel is in hand")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-errand"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def forked(self):
        run("phase", "open", "1", "Find", "--goal", "in hand or a claim filed [run: found] | [ref: claim]; shoes move [ref: tracking]")
        run("todo", "add", "1", "walk the doors", "--expect", "[run: found]")
        run("todo", "add", "1", "file the claim", "--expect", "[ref: claim]")
        run("todo", "add", "1", "watch the shoes", "--expect", "[ref: tracking]")
        run("todo", "done", "1.3", "ref:moved", "the shoes move")

    def journal(self):
        return (self.case / "JOURNAL.md").read_text(encoding="utf-8")


class TheGrammarReadsAFork(Base):
    def test_slots_joined_by_a_bar_are_one_promise(self):
        self.assertEqual(grammar.promise_groups("x [run: a] | [ref: b]; y [ref: c]"),
                         [[("run", "a"), ("ref", "b")], [("ref", "c")]])

    def test_words_between_slots_keep_them_apart(self):
        self.assertEqual(len(grammar.promise_groups("[run: a] or then [ref: b]")), 2)


class EitherSideClosesThePhase(Base):
    def test_one_side_proved_the_other_cancelled_closes_and_the_digest_says_which(self):
        self.forked()
        run("todo", "done", "1.1", "run:doors → found", "found at the neighbours")
        run("todo", "cancel", "1.2", "the parcel is in hand")
        code, out, err = run("phase", "close", "1", "parcel in hand", "--reflect", "r", "--align", "a", "--howto", "none: t")
        self.assertEqual(code, 0, err)
        digest = (self.case / "phases" / "1-find.md").read_text(encoding="utf-8")
        self.assertIn("phase promise: 2 of 2 proved — the fork [run: found] | [ref: claim] — [run: found] by 1.1", digest)

    def test_neither_side_proved_refuses_naming_the_fork(self):
        self.forked()
        run("todo", "cancel", "1.1", "nobody home")
        run("todo", "cancel", "1.2", "the shop answered nothing")
        code, _, err = run("phase", "close", "1", "x", "--reflect", "r", "--align", "a", "--howto", "none: t")
        self.assertEqual(code, 4)
        self.assertIn("promised the fork [run: found] | [ref: claim] and neither side is proved", err)


class ThePointIsHeld(Base):
    def test_done_on_one_side_names_the_other_sides_items(self):
        self.forked()
        code, out, err = run("todo", "done", "1.1", "run:doors → found", "found at the neighbours")
        self.assertEqual(code, 0, err)
        self.assertIn("the fork [run: found] | [ref: claim] is decided — [run: found] by 1.1; the other side's 1.2 still open", out)
        self.assertIn('el todo cancel 1.2 "why it is no longer needed"', out)

    def test_order_holds_it_until_the_other_side_ends_and_the_journal_keeps_the_point(self):
        self.forked()
        run("todo", "done", "1.1", "run:doors → found", "found at the neighbours")
        self.assertIn("the point has passed → el todo cancel 1.2", run()[1])
        code, _, err = run("phase", "close", "1", "x", "--reflect", "r", "--align", "a", "--howto", "none: t")
        self.assertEqual(code, 4)
        self.assertIn("1.2 is the other side of the fork [run: found] | [ref: claim], decided — [run: found] by 1.1", err)
        run("todo", "cancel", "1.2", "the parcel is in hand")
        self.assertNotIn("the point has passed", run()[1])
        self.assertIn("развилка [run: found] | [ref: claim] решена: [run: found] by 1.1", self.journal())


class TheWriteDoorSaysTheForm(Base):
    def test_or_in_words_between_two_slots_offers_the_fork(self):
        code, out, _ = run("phase", "plan", "1", "Find", "--goal", "in hand [run: found] or a claim [ref: claim]")
        self.assertEqual(code, 0)
        self.assertIn("fork? [run: found] … or … [ref: claim]", out)
        self.assertIn("[run: found] | [ref: claim]", out)

    def test_a_written_fork_is_not_asked_again(self):
        _, out, _ = run("phase", "plan", "1", "Find", "--goal", "in hand or a claim [run: found] | [ref: claim]")
        self.assertNotIn("fork?", out)

    def test_the_open_hint_names_one_item_per_branch(self):
        os.environ["EL_HINTS"] = "1"
        _, out, _ = run("phase", "open", "1", "Find", "--goal", "in hand or a claim [run: found] | [ref: claim]")
        hint = next(ln for ln in out.split("\n") if ln.startswith("hint:"))
        self.assertIn('el todo add 1 "…" --expect "[run: found]" · el todo add 1 "…" --expect "[ref: claim]"', hint)

    def test_order_names_an_untouched_fork_with_both_branches(self):
        run("phase", "open", "1", "Find", "--goal", "in hand or a claim [run: found] | [ref: claim]")
        line = next(ln for ln in run()[1].split("\n") if "no item promises either side" in ln)
        self.assertIn('--expect "[run: found]"', line)
        self.assertIn('--expect "[ref: claim]"', line)


class TheCaseMayPromiseAForkToo(Base):
    def setUp(self):
        super().setUp()
        run("readme", "add", "context", "promise: in hand or refunded [run: found] | [ref: refund]")

    def test_one_side_proved_in_a_phase_closes_the_case(self):
        run("phase", "open", "1", "Refund", "--goal", "refunded [ref: refund]")
        run("todo", "add", "1", "ask the shop", "--expect", "[ref: refund]")
        run("todo", "done", "1.1", "ref:refund-42", "refunded")
        run("phase", "close", "1", "refunded", "--reflect", "r", "--align", "a", "--howto", "none: t")
        code, out, err = run("done", "the money came back")
        self.assertEqual(code, 0, err)
        self.assertIn("the fork [run: found] | [ref: refund] — [ref: refund] by phase 1", out)

    def test_neither_side_refuses_the_case_close(self):
        code, _, err = run("done", "gave up")
        self.assertEqual(code, 4)
        self.assertIn("promised the fork [run: found] | [ref: refund] in Context and neither side is proved", err)


if __name__ == "__main__":
    unittest.main()
