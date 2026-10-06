"""Feedback of 2026-10-02 — work beside the plan, and the doses that were half said.

1. An agent worked one coarse item for hours: DECISIONs, free RESULTs, `next:` moved step by step — and TODO kept one
   `[ ] N.M` line, Order silent. The RESULTs named no item: a proof without a statement rises nowhere. The same agent
   logged a RESULT and then `done` the item, and the journal said it twice. At the moment a typed RESULT names no item of
   a running phase with open items, el names the item in hand and the three doors (done writes the RESULT · note · add).
2. «The owner said it in the chat — is that enough, or must I brief a subagent for form's sake?» The entry's
   `acceptance:` line named the brief only. It names both doors, numbered.
3. `fact:` stayed empty: «a detailed result reads as the fact already». The zero line says the difference.
4. An item 8 chars over with no boundary of meaning: the refusal printed the cut as `suggestion:` and «rephrase, do not
   truncate» under it; the agent took the cut and lost a word. The cut is not offered; the words it drops are named."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import commands
from tests.test_commands import run

PROOF = "[run: make test → OK]"


class Base(unittest.TestCase):
    hints = "1"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = self.hints
        os.environ["EL_SESSION"] = "doer1002"
        run("case", "new", "signup form", "--goal", "g")
        run("phase", "open", "1", "Repair", "--goal", f"the form saves again {PROOF}")
        run("todo", "add", "1", "find the field names", "--expect", PROOF)
        run("todo", "add", "1", "rename the form fields", "--expect", PROOF)

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def case(self) -> Path:
        return next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def entry_line(self, prefix: str) -> str:
        code, out, err = run()
        self.assertEqual(code, 0, err)
        return next((ln for ln in out.split("\n") if ln.startswith(prefix)), "")


class AResultBesideThePlanIsNamed(Base):
    def test_a_free_result_names_the_item_in_hand_and_the_three_doors(self):
        code, out, err = run("log", "RESULT", "the names come from the old schema")
        self.assertEqual(code, 0, err)
        hint = next(ln for ln in out.split("\n") if ln.startswith("hint: "))
        self.assertIn("this RESULT names no item — TODO, where the owner looks, does not move", hint)
        self.assertIn('el todo done 1.1 <kind> "…" writes the RESULT itself', hint, "done writes it: no second log")
        self.assertIn('el todo note 1.1 "…"', hint)
        # since 1.40.0 (feedback 2026-10-06, F25) a step with its own proof is a sub-item under the item, not a peer before it
        self.assertIn('el todo add 1.1 "…", a sub-item 1.1.K, then done it', hint)

    def test_the_item_in_hand_is_the_first_one_that_can_be_taken(self):
        run("todo", "hold", "1.1", "waiting for: access to the staging site")
        code, out, _ = run("log", "RESULT", "fields listed")
        self.assertIn("el todo done 1.2 <kind>", out, "a held item is not the one in hand")

    def test_a_result_that_names_its_item_is_not_named(self):
        code, out, err = run("log", "RESULT", "1.1: the names come from the old schema")
        self.assertEqual(code, 0, err)
        self.assertNotIn("names no item", out)

    def test_a_phase_result_after_every_item_ended_is_not_named(self):
        run("todo", "done", "1.1-1.2", "run:make test → OK", "ok")
        code, out, err = run("log", "RESULT", "the form saves again")
        self.assertEqual(code, 0, err)
        self.assertNotIn("names no item", out)

    def test_a_result_with_no_phase_running_is_not_named(self):
        run("case", "new", "another", "--goal", "g")
        code, out, err = run("log", "RESULT", "talked it over")
        self.assertEqual(code, 0, err)
        self.assertNotIn("names no item", out)

    def test_a_result_el_writes_on_its_own_is_not_named(self):
        out = commands.log(self.case(), "RESULT", "дело закрыто → done · child/")
        self.assertFalse(any("names no item" in ln for ln in out.lines), "only what the agent typed is named")

    def test_the_hint_is_silenced_like_every_hint(self):
        os.environ["EL_HINTS"] = "0"
        code, out, _ = run("log", "RESULT", "the names come from the old schema")
        self.assertNotIn("names no item", out)

    def test_the_help_says_the_plan_moves_with_the_work(self):
        self.assertIn("the plan moves with the work", run("help", "todo")[1])
        self.assertIn("a step of an item ended", run("help", "where")[1])


class AcceptanceNamesBothDoors(Base):
    hints = "0"

    def setUp(self):
        os.environ["EL_TWO_HANDS"] = "1"
        super().setUp()
        run("todo", "add", "1", "check the form", "--expect", PROOF)

    def test_with_nothing_owed_the_doors_are_generic(self):
        line = self.entry_line("acceptance: ")
        self.assertIn("a fresh session: el todo brief N.M", line)
        self.assertIn("the owner's word said to you: el todo accept N.M --by owner", line)

    def test_owed_items_side_by_side_take_a_range(self):
        run("todo", "done", "1.1-1.2", "run:make test → OK", "ok")
        line = self.entry_line("acceptance: ")
        self.assertIn("a fresh session: el todo brief 1.1", line)
        self.assertIn('el todo accept 1.1-1.2 --by owner "…"', line)

    def test_an_open_item_between_them_makes_it_a_list(self):
        run("todo", "done", "1.1", "run:make test → OK", "ok")
        run("todo", "done", "1.3", "run:make test → OK", "ok")
        line = self.entry_line("acceptance: ")
        self.assertIn('el todo accept 1.1, 1.3 --by owner "…"', line, "a range over the open 1.2 would be refused")
        code, _, err = run("todo", "accept", "1.1, 1.3", "--by", "owner", "all good")
        self.assertEqual(code, 0, err)


class FactsZeroSaysTheDifference(Base):
    hints = "0"

    def test_the_zero_line_tells_a_result_from_a_fact(self):
        run("todo", "add", "1", "third", "--expect", PROOF)
        run("todo", "done", "1.1-1.3", "run:make test → OK", "ok")
        line = self.entry_line("facts: ")
        self.assertIn("a result says what the work did, a fact what is now true that the next step stands on", line)


class TheRefusalDoesNotOfferTheCut(Base):
    hints = "0"
    # the live form, invented words of the same shape: 108 chars, no boundary of meaning, the last word lost by a cut
    LONG = "Prove the auth service is live and its call path /v9/app/signin-post runs through the edge proxy and its log"

    def test_the_words_a_cut_drops_are_named_and_no_cut_is_suggested(self):
        code, _, err = run("todo", "add", "1", self.LONG)
        self.assertEqual(code, 3)
        self.assertNotIn('suggestion: "', err, "a cut shown as a suggestion is taken literally")
        self.assertIn("over and no boundary of meaning to split at — a cut at 100 would lose «and its log»", err)
        self.assertIn("rephrase, do not truncate", err)
        self.assertIn("an opaque id (a hash, a generated entity id) is a trace, not words", err)

    def test_a_boundary_of_meaning_still_keeps_the_rest_as_a_note(self):
        text = "Rename the fields in the four forms of the signup page — the ready file lies in docs, the ids in the note"
        code, _, err = run("todo", "add", "1", text)
        self.assertEqual(code, 3)
        self.assertIn("suggestion — the item, the rest as its note", err)


if __name__ == "__main__":
    unittest.main()
