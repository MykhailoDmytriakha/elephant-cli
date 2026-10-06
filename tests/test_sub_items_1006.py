"""A report of 2026-10-06 11:31 (el 1.39.0) and the owner's word the same day — sub-items N.M.K (F25).

An agent ran a spike under one item: three probes (the code, a permission probe, a rewritten query), two of them dead
ends proved by a run. TODO kept one generic `[ ]` line; the probes and the negative proofs stayed in the chat, because
adding each probe as a peer item of the phase cluttered the plan — and the next agent would walk the same dead ends.
The agent asked for sub-steps N.M.K. Shown the shapes el already had (probes as items before the question, notes, a
nested case per probe), the owner looked at TODO as its reader — the question at the bottom, the probes above it, a
dropped probe gone — and chose the mockup: the question first, its probes under it in the order taken, a dropped one in
sight with its reason, el's tally on the item line, the item ending only when each probe has. One level only: deeper is
a nested case. Until 1.40.0 the third level was refused (F13)."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from elephant import grammar
from tests.test_commands import run


class Base(unittest.TestCase):
    two_hands = "0"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="doer1006", EL_TWO_HANDS=self.two_hands)
        run("case", "new", "metric", "--goal", "the metric tells the truth")
        run("phase", "open", "1", "Root cause", "--goal", "the cause named [run: repro]")
        run("todo", "add", "1", "find why the metric drops at 02:00", "--expect", "cause reproduced [run: repro]")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def case(self) -> Path:
        return next((Path(self.tmp.name) / ".cases").iterdir())

    def read(self, name: str) -> str:
        return (self.case() / name).read_text()

    def probes(self):
        """The spike of the report: four paths under the question."""
        run("todo", "add", "1.1", "probe: the code drops late events", "--expect", "[run: grep]", "--fact", "the code drops them")
        run("todo", "add", "1.1", "probe: read the raw events directly", "--expect", "[run: select]")
        run("todo", "add", "1.1", "probe: rewrite the query without the window", "--expect", "[run: query]")
        run("todo", "add", "1.1", "probe: the time zone of the aggregation", "--expect", "[run: tz]", "--fact", "a zone shift")


class TheGrammar(unittest.TestCase):
    TODO = ("# TODO — t\n\n"
            "- [ ] 1 Root — g · [phases/1-root.md](phases/1-root.md)\n"
            "  - [ ] 1.1 find the cause — sub-items: 1 done · 1 cancelled · 1 on hold\n"
            "    - expect: [run: repro]\n"
            "    - [x] 1.1.1 probe a\n"
            "      - result: no filter\n"
            "        - run: grep → none\n"
            "      - fact: the code does not drop them\n"
            "    - [~] 1.1.2 probe b — hold: waiting for: read access\n"
            "    - [-] 1.1.3 probe c — cancelled: the cause was found first\n")

    def test_a_sub_item_is_read_with_its_pockets_its_proof_and_its_end(self):
        r = grammar.parse_todo(self.TODO)
        self.assertTrue(r.ok, r.errors)
        it = r.phases[0].items[0]
        self.assertEqual([s.ref for s in it.subs], ["1.1.1", "1.1.2", "1.1.3"])
        a, b, c = it.subs
        self.assertTrue(a.done and a.result == "no filter" and a.evidence == [("run", "grep → none")])
        self.assertEqual(a.fact, "the code does not drop them")
        self.assertTrue(b.held and b.hold_reason == "waiting for: read access")
        self.assertTrue(c.cancelled and c.cancel_reason == "the cause was found first")
        self.assertEqual(it.text, "find the cause", "the tally is el's drawing, not the item's words")

    def test_a_fourth_level_is_refused(self):
        r = grammar.parse_todo(self.TODO + "      - [ ] 1.1.3.1 deeper\n")
        self.assertTrue(any(f.rule == "F25" and "nested case" in f.message for f in r.errors), r.errors)

    def test_a_cancelled_sub_item_needs_its_reason(self):
        r = grammar.parse_todo(self.TODO.replace(" — cancelled: the cause was found first", ""))
        self.assertTrue(any(f.rule == "F25" and "no reason" in f.message for f in r.errors), r.errors)

    def test_an_item_is_never_done_over_an_open_sub_item(self):
        r = grammar.parse_todo(self.TODO.replace("  - [ ] 1.1 find", "  - [x] 1.1 find"))
        self.assertTrue(any(f.rule == "F25" and "done over open sub-item(s) 1.1.2" in f.message for f in r.errors), r.errors)

    def test_a_sub_item_under_another_item_is_refused(self):
        r = grammar.parse_todo(self.TODO.replace("    - [x] 1.1.1 probe a", "    - [x] 1.2.1 probe a"))
        self.assertTrue(any(f.rule == "F25" and "listed under item 1.1" in f.message for f in r.errors), r.errors)


class AddingAndEnding(Base):
    def test_add_under_an_item_makes_the_next_sub_item_under_it(self):
        code, out, err = run("todo", "add", "1.1", "probe: the code drops late events", "--fact", "the code drops them")
        self.assertEqual(code, 0, err)
        self.assertIn("added: 1.1.1 probe: the code drops late events — under 1.1", out)
        todo = self.read("TODO.md")
        self.assertIn("    - [ ] 1.1.1 probe: the code drops late events\n      - fact: the code drops them", todo)
        self.assertIn("  - [ ] 1.1 find why the metric drops at 02:00 — sub-items: 1 open", todo)

    def test_one_level_only_deeper_is_a_nested_case(self):
        run("todo", "add", "1.1", "probe a")
        code, _, err = run("todo", "add", "1.1.1", "deeper")
        self.assertEqual(code, 4)
        self.assertIn("el spawn", err)

    def test_the_item_is_not_done_while_a_sub_item_is_open(self):
        self.probes()
        before = self.read("TODO.md")
        code, _, err = run("todo", "done", "1.1", "run:repro → drop at 02:00", "the cause")
        self.assertEqual(code, 4)
        self.assertIn("1.1 rests on its sub-items — 1.1.1 (open), 1.1.2 (open)", err)
        self.assertIn("el todo done 1.1.1 <kind>", err)
        self.assertIn('el todo cancel 1.1.1 "why', err)
        self.assertEqual(self.read("TODO.md"), before, "a refusal writes nothing")

    def test_a_refuted_path_is_done_with_what_it_proved_a_dropped_one_stays_in_sight(self):
        self.probes()
        code, out, err = run("todo", "done", "1.1.1", "run:grep -rn late src → no filter", "no filter in the code",
                             "--fact", "the code does not drop late events")
        self.assertEqual(code, 0, err)
        code, out, err = run("todo", "cancel", "1.1.3", "not needed: the zone explained the drop")
        self.assertEqual(code, 0, err)
        self.assertIn("stays in sight under 1.1", out)
        todo = self.read("TODO.md")
        self.assertIn("    - [-] 1.1.3 probe: rewrite the query without the window — cancelled: not needed: the zone explained the drop", todo)
        self.assertIn("      - fact: the code does not drop late events", todo)
        self.assertIn("— sub-items: 1 done · 1 cancelled · 2 open", todo)
        journal = self.read("JOURNAL.md")
        self.assertIn("RESULT · 1.1.1: run grep -rn late src → no filter", journal)
        self.assertIn("снято 1.1.3 «probe: rewrite the query without the window» — not needed", journal)
        code, out, _ = run("facts")
        self.assertIn("✓ 1.1.1 the code does not drop late events", out)
        self.assertIn("✗ 1.1.3 probe: rewrite the query without the window", out)

    def test_the_item_ends_once_each_path_has(self):
        self.probes()
        run("todo", "done", "1.1.1", "run:grep → none", "no filter", "--fact", "-")
        run("todo", "cancel", "1.1.2, 1.1.3", "not needed")
        run("todo", "done", "1.1.4", "run:tz UTC → no drop", "the day is cut by local time", "--fact", "confirmed")
        code, out, err = run("todo", "done", "1.1", "run:repro by local time → drop at 02:00", "the aggregation cuts the day locally")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [x] 1.1 find why the metric drops at 02:00 — sub-items: 2 done · 2 cancelled", self.read("TODO.md"))

    def test_cancelling_the_item_ends_its_open_sub_items_with_the_reason(self):
        self.probes()
        run("todo", "done", "1.1.1", "run:grep → none", "no filter", "--fact", "-")
        code, out, err = run("todo", "cancel", "1.1", "the dashboard is retired")
        self.assertEqual(code, 0, err)
        self.assertIn("its open sub-item(s) ended with it: 1.1.2, 1.1.3, 1.1.4", out)
        self.assertNotIn("1.1 find why", self.read("TODO.md"))
        self.assertRegex(self.read("JOURNAL.md"), r"снято 1\.1 «[^»]+», 1\.1\.2 «[^»]+», 1\.1\.3 «[^»]+», 1\.1\.4 «[^»]+» — the dashboard")

    def test_a_sub_item_changes_its_end_only_under_an_open_item(self):
        run("todo", "add", "1.1", "probe a")
        run("todo", "done", "1.1.1", "run:a → b", "found")
        run("todo", "done", "1.1", "run:repro → ok", "the cause")
        code, _, err = run("todo", "reopen", "1.1.1", "the grep missed a folder")
        self.assertEqual(code, 4)
        self.assertIn('el todo reopen 1.1 "why the answer no longer holds"', err)
        code, _, err = run("todo", "add", "1.1", "probe b")
        self.assertEqual(code, 4)
        self.assertIn("el todo reopen 1.1", err)

    def test_a_cancelled_sub_item_comes_back_by_reopen(self):
        run("todo", "add", "1.1", "probe a")
        run("todo", "cancel", "1.1.1", "looked unneeded")
        code, out, err = run("todo", "reopen", "1.1.1", "the other path failed")
        self.assertEqual(code, 0, err)
        self.assertIn("    - [ ] 1.1.1 probe a\n", self.read("TODO.md"))

    def test_a_held_sub_item_is_what_the_thread_says_the_item_waits_for(self):
        run("todo", "add", "1.1", "probe: read the raw events")
        run("todo", "hold", "1.1.1", "waiting for: read access from the owner")
        code, out, _ = run()
        thread = next(ln for ln in out.split("\n") if ln.startswith("thread: "))
        self.assertIn("item 1.1", thread)
        self.assertIn("waiting: 1.1.1 «waiting for: read access from the owner»", thread)

    def test_the_thread_names_the_sub_item_in_hand(self):
        self.probes()
        run("todo", "done", "1.1.1", "run:grep → none", "no filter", "--fact", "-")
        code, out, _ = run()
        thread = next(ln for ln in out.split("\n") if ln.startswith("thread: "))
        self.assertIn("→ sub-item 1.1.2 «probe: read the raw events directly»", thread)


class Moving(Base):
    def test_a_sub_item_moves_among_its_siblings_and_out_from_under_its_item(self):
        self.probes()
        run("todo", "add", "1", "other", "--expect", "[run: y]")
        run("todo", "after", "1.2", "1.1.2")
        code, out, err = run("todo", "move", "1.1.4", "1.1.1")
        self.assertEqual(code, 0, err)
        todo = self.read("TODO.md")
        self.assertLess(todo.index("1.1.4 probe"), todo.index("1.1.1 probe"), "before 1.1.1, numbers kept")
        code, out, err = run("todo", "move", "1.1.2", "1")
        self.assertEqual(code, 0, err)
        self.assertIn("moved: 1.1.2 → 1.3", out)
        self.assertIn("  - [ ] 1.2 other — after: 1.3", self.read("TODO.md"), "the after-reference follows it")

    def test_an_item_moves_to_another_phase_with_its_sub_items(self):
        run("phase", "plan", "2", "Fix", "--goal", "g2")
        self.probes()
        code, out, err = run("todo", "move", "1.1", "2")
        self.assertEqual(code, 0, err)
        todo = self.read("TODO.md")
        self.assertIn("  - [ ] 2.1 find why", todo)
        self.assertIn("    - [ ] 2.1.4 probe: the time zone of the aggregation", todo)

    def test_an_item_with_sub_items_is_not_a_single_thought_for_later(self):
        run("todo", "add", "1.1", "probe a")
        code, _, err = run("todo", "move", "1.1", "later")
        self.assertEqual(code, 4)
        self.assertIn("carries sub-items", err)

    def test_drop_says_nothing_about_sub_items(self):
        run("todo", "add", "1.1", "probe a")
        code, _, err = run("todo", "drop", "1.1")
        self.assertEqual(code, 4)
        self.assertIn('el todo cancel 1.1 "why"', err)


class TwoHandsAndTheClose(Base):
    two_hands = "1"

    def test_sub_items_are_accepted_closed_into_the_phase_file_and_counted(self):
        run("phase", "agree", "1", "the owner's scope")
        self.probes()
        run("todo", "done", "1.1.1", "run:grep → none", "no filter", "--fact", "the code does not drop late events")
        run("todo", "cancel", "1.1.2, 1.1.3", "not needed")
        run("todo", "done", "1.1.4", "run:tz UTC → no drop", "cut by local time", "--fact", "confirmed")
        run("todo", "done", "1.1", "run:repro → drop at 02:00", "the aggregation cuts the day by local time")
        self.assertIn("    - [/] 1.1.1 probe", self.read("TODO.md"), "a done sub-item awaits its acceptance")
        run("todo", "accept", "1.1", "--by", "owner", "checked")
        code, _, err = run("phase", "close", "1", "the cause named", "--reflect", "probes read top down", "--align", "fix it")
        self.assertEqual(code, 4)
        self.assertIn("done items not accepted — 1.1.1, 1.1.4", err)
        run("todo", "accept", "1.1.1, 1.1.4", "--by", "owner", "checked")
        code, out, err = run("phase", "close", "1", "the cause named", "--reflect", "probes read top down", "--align", "fix it")
        self.assertEqual(code, 0, err)
        self.assertIn("acceptance: 3 of 3 done accepted", out)
        pf = self.read("phases/1-root-cause.md")
        self.assertIn("- items: 1 done · sub-items: 2 done · 2 cancelled", pf)
        self.assertIn("- closed paths (2):", pf)
        self.assertIn("  - 1.1.1 ✓ probe: the code drops late events", pf)
        self.assertIn("  - 1.1.3 ✗ probe: rewrite the query without the window — cancelled: not needed", pf)
        code, out, _ = run("facts")
        self.assertIn("✓ 1.1.1 the code does not drop late events", out, "the closed phase file is read back with its sub-items")
        self.assertIn("✓ 1.1.4 a zone shift", out)
        code, out, _ = run("check")
        self.assertIn("violations: 0", out)


class KnowledgeAtTheMoment(Base):
    def test_a_free_result_points_at_a_sub_item(self):
        os.environ["EL_HINTS"] = "1"
        code, out, _ = run("log", "RESULT", "the permission probe failed")
        self.assertIn('el todo add 1.1 "…", a sub-item 1.1.K, then done it', out)

    def test_help_answers_the_words_of_a_spike(self):
        for word in ("spike", "probe", "sub-item", "hypothesis"):
            code, out, _ = run("help", word)
            self.assertEqual(code, 0, word)
            self.assertIn("sub-items N.M.K (F25", out, word)


if __name__ == "__main__":
    unittest.main()
