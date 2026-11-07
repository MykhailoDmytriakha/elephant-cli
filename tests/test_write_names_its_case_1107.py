"""A report from the pool, 2026-11-07: `el case use A | tail && el log PROBLEM …` — A was closed, the refusal went by
behind the pipe (tail's exit 0 let the chain go on), and the event went into B, the case still in hand. el said
«logged: PROBLEM → JOURNAL.md (…)» — a file every case has; the misplaced event was seen only in git diff.

A write whose case el chose (the hand, not --case or EL_CASE) names the case on its first line while another case here
is open; the refusal of `case use` says where the hand stays."""
import os
import unittest
from pathlib import Path

from elephant import store
from tests.test_commands import run
from tests.test_long_case_1105 import Base


class AWriteNamesTheCaseItWentInto(Base):
    def setUp(self):
        super().setUp()  # the shop, open
        self.ok("case", "new", "till", "--goal", "the till counts")
        self.ok("case", "new", "shed", "--goal", "the shed stands")
        self.ok("--case", "shed", "done", "nothing left", "--howto", "none: a test")
        self.ok("case", "use", "till")

    def journal(self, tail: str) -> str:
        return store.read(next(Path(".cases").glob(f"*-{tail}")), "JOURNAL.md")

    def test_the_chain_of_the_report_names_the_case_the_event_went_into(self):
        code, out, err = run("case", "use", "shed")
        self.assertEqual(code, 4, out + err)
        till = next(Path(".cases").glob("*-till")).name
        self.assertIn(f"shed is closed — the hand only holds open cases and stays on {till}", out + err)
        out, _ = self.ok("log", "PROBLEM", "the scale drifts")
        self.assertTrue(out.startswith(f"[{till}] logged: PROBLEM → JOURNAL.md"), out)
        self.assertIn("the scale drifts", self.journal("till"))
        self.assertNotIn("the scale drifts", self.journal("shed"))

    def test_every_write_through_the_hand_names_it_not_only_the_log(self):
        till = next(Path(".cases").glob("*-till")).name
        for argv in (("todo", "add", "later", "count the coins"), ("readme", "touch"),
                     ("readme", "set", "next", "count the coins")):
            out, _ = self.ok(*argv)
            self.assertTrue(out.startswith(f"[{till}] "), f"{argv}: {out}")

    def test_a_call_that_names_its_case_is_not_told_its_name(self):
        out, _ = self.ok("--case", "till", "log", "DECISION", "count by hand · instead of a scale · it drifts")
        self.assertTrue(out.startswith("logged: DECISION"), out)
        os.environ["EL_CASE"] = "till"
        try:
            out, _ = self.ok("log", "DECISION", "weigh twice · instead of once · it drifts")
        finally:
            os.environ.pop("EL_CASE")
        self.assertTrue(out.startswith("logged: DECISION"), out)

    def test_a_look_is_not_a_write(self):
        out, _ = self.ok("todo")
        self.assertNotIn("[", out.splitlines()[0])

    def test_one_open_case_has_nothing_to_tell_apart(self):
        self.ok("--case", "shop", "done", "nothing left", "--howto", "none: a test")
        out, _ = self.ok("log", "PROBLEM", "the scale drifts")
        self.assertTrue(out.startswith("logged: PROBLEM → JOURNAL.md"), out)

    def test_case_new_says_the_case_it_created_itself(self):
        out, _ = self.ok("case", "new", "barn", "--goal", "the barn holds")
        first = out.splitlines()[0]
        self.assertIn("barn", first)
        self.assertFalse(first.startswith("["), out)

    def test_a_case_cancelled_or_reopened_through_the_hand_is_named(self):  # Codex, 2026-11-07: the case branch never
        till = next(Path(".cases").glob("*-till")).name  # reached the write block
        out, _ = self.ok("case", "cancel", "not needed")
        self.assertTrue(out.startswith(f"[{till}] "), out)
        self.assertIn("not needed", self.journal("till"))
        self.ok("case", "use", "shop")
        out, _ = self.ok("--case", "till", "case", "reopen", "needed after all")
        self.assertFalse(out.startswith("["), out)  # named by the call

    def test_spawn_names_the_parent_its_first_line_went_into(self):  # Codex, 2026-11-07
        till = next(Path(".cases").glob("*-till")).name
        self.ok("phase", "open", "1", "Count", "--goal", "the coins are counted")
        out, _ = self.ok("spawn", "drawer", "--goal", "the drawer opens")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith(f"[{till}] "), out)
        self.assertIn("spawned:", out)

    def test_the_recital_above_a_one_line_write_names_the_case_too(self):  # Codex, 2026-11-07: on the tenth call
        till = next(Path(".cases").glob("*-till")).name  # two recital lines went above «[till] logged: …» — head -1
        os.environ["EL_RECITE"] = "1"  # lost the case
        recited = 0
        for k in range(14):
            out, _ = self.ok("log", "PROBLEM", f"the scale drifts by {k + 1} grams")
            lines = [ln for ln in out.splitlines() if ln.strip()]
            self.assertTrue(lines[0].startswith(f"[{till}] "), out)
            self.assertTrue(any(ln.startswith(f"[{till}] logged: PROBLEM") for ln in lines), out)
            recited += any("recite" in ln for ln in lines)
        self.assertGreater(recited, 0)

    def test_words_never_take_the_tag_away(self):  # Codex, 2026-11-07: a child sharing a top case's name, whose TODO
        # text cites the top case's path, lost its tag — the check read the line's words as routing
        till = next(Path(".cases").glob("*-till")).name
        self.ok("phase", "open", "1", "Count", "--goal", "the coins are counted")
        self.ok("spawn", "shop", "--goal", "the inner shop opens")  # a nested case named as the top one
        inner = f"{till}/" + next(Path(".cases", till).glob("*-shop")).name
        shop = next(p.name for p in Path(".cases").iterdir() if p.name.endswith("-shop"))
        out, _ = self.ok("todo", "add", "later", f"compare with .cases/{shop}")
        self.assertTrue(out.startswith(f"[{inner}] "), out)
        out, _ = self.ok("log", "PROBLEM", f"{inner} drifts")
        self.assertTrue(out.startswith(f"[{inner}] logged: PROBLEM"), out)

    def test_the_door_the_refusal_prints_runs_as_printed(self):
        import shlex
        code, out, err = run("case", "use", "shed")
        door = (out + err).split("it goes on? ", 1)[1].split(", then ", 1)[0].strip()
        self.ok(*shlex.split(door)[1:])
        out, _ = self.ok("case", "use", "shed")
        self.assertIn("current case:", out)


if __name__ == "__main__":
    unittest.main()
