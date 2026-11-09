"""The radio with Codex, #139 (2026-11-08): `el log --phase 356.3.2 RESULT …` — the number of the sub-item in work — was
refused with exit 2 and a list of all 356 phases, cut in the middle by the agent's output tool; `--phase p356` went
through. Phase numbers are whole, so an item or sub-item number names its phase: el files the event there and says so.
Before, `--phase 356.3` made a tag `p356.3` no phase ever counted — the phase's close never saw that RESULT. A refusal
names a few phases near the one asked, never the whole list of a long case."""
import unittest

from tests.test_long_case_1105 import Base


class AnItemNumberNamesItsPhase(Base):
    def setUp(self):
        super().setUp()
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")
        self.ok("todo", "add", "1", "check the shop")

    def journal(self) -> str:
        case = next(p for p in (__import__("pathlib").Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        return (case / "JOURNAL.md").read_text(encoding="utf-8")

    def test_a_sub_item_number_files_the_event_under_its_phase(self):
        out, _ = self.ok("log", "--phase", "1.1.2", "RESULT", "1.1: the door holds")
        self.assertIn("filed under p1: 1.1.2 is an item of phase 1", out)
        self.assertNotIn("· p1.1", self.journal())

    def test_an_item_number_no_longer_makes_a_tag_no_phase_counts(self):
        self.ok("log", "--phase", "1.1", "DECISION", "keep the shop open")
        self.assertNotIn("· p1.1", self.journal())

    def test_a_refusal_names_nearby_phases_not_all_of_them(self):
        for n in range(2, 12):
            self.ok("phase", "plan", str(n), f"Step{n}", "--goal", f"step {n} works")
        from tests.test_commands import run
        code, out, err = run("log", "--phase", "40.1", "RESULT", "x")
        self.assertEqual(code, 2, out + err)
        self.assertIn("no phase 40", err)
        self.assertIn("more — the plan: el todo", err)
        self.assertLessEqual(err.count(" · p"), 8, err)


    def test_a_phase_that_does_not_exist_is_refused_with_the_door_to_plan_it(self):
        """The acceptance of 62.1: `--phase 999` made a tag of a phase that never was."""
        from tests.test_commands import run
        code, out, err = run("log", "--phase", "999", "DECISION", "x")
        self.assertEqual(code, 2, out + err)
        self.assertIn("no phase 999", err)
        self.assertIn("el phase plan 999", err)
        self.assertNotIn("· p999", self.journal())

    def test_leading_zeros_name_the_same_phase(self):
        """The acceptance of 62.1: `--phase 002` made a tag `p002` the phase's Digest never read."""
        self.ok("phase", "plan", "2", "Next", "--goal", "the next works")
        self.ok("log", "--phase", "002", "DECISION", "keep it")
        self.assertIn("· p2\n", self.journal())
        self.assertNotIn("p002", self.journal())

    def test_the_phase_in_flight_comes_first_not_a_paused_one(self):
        """The acceptance of 62.1: the refusal skipped the phase in flight and showed a paused one."""
        for n in range(2, 12):
            self.ok("phase", "plan", str(n), f"Step{n}", "--goal", f"step {n} works")
        self.ok("phase", "open", "3", "--why", "the roof leaks first")  # phase 1 pauses for this detour
        from tests.test_commands import run
        code, out, err = run("log", "--phase", "40.1", "RESULT", "x")
        self.assertEqual(code, 2, out + err)
        self.assertIn("phases: p3 Step3 (in flight) · ", err)


    def test_an_item_of_phase_0_needs_a_phase_0(self):
        """Round 2: `--phase 0.1` was taken as an item of a phase 0 that did not exist. Phase 0 is a real phase (batch 24):
        without it the item is refused with the door to plan it; with it, the door ran as printed and `0.1` names it."""
        import shlex
        from tests.test_commands import run
        code, out, err = run("log", "--phase", "0.1", "DECISION", "x")
        self.assertEqual(code, 2, out + err)
        self.assertIn("no phase 0", err)
        door = err.split("a phase to come: ", 1)[1].splitlines()[0].replace("\"Name\"", "Proof").replace("\"…\"", "'proved'")
        code, out, err = run(*shlex.split(door)[1:])
        self.assertEqual(code, 0, f"{door}: {out}{err}")
        out, _ = self.ok("log", "--phase", "0.1", "DECISION", "y")
        self.assertIn("filed under p0", out)

    def test_the_example_in_the_refusal_runs_as_printed(self):
        """Round 2: with only phase 3 left in sight the refusal printed `--phase p1`, which failed as printed."""
        import re
        import shlex
        from tests.test_commands import run
        self.ok("case", "new", "garden", "--goal", "the garden grows")
        self.ok("--case", "garden", "phase", "plan", "3", "Water", "--goal", "the soil stays moist")  # its only phase
        code, out, err = run("--case", "garden", "log", "--phase", "nosuch", "DECISION", "x")
        self.assertEqual(code, 2, out + err)
        example = re.search(r"`(el (?:--case \S+ )?log --phase \S+ DECISION) \"…\"`", err).group(1)
        self.assertIn("p3", example, err)
        code, out, err = run(*shlex.split(example)[1:], "an example")
        self.assertEqual(code, 0, f"{example}: {out}{err}")


    def test_an_empty_phase_named_on_the_call_is_refused(self):
        """Round 3: `--phase ""` went past the check and filed the event in the default phase."""
        from tests.test_commands import run
        before = self.journal()
        code, out, err = run("log", "--phase", "", "DECISION", "x")
        self.assertEqual(code, 2, out + err)
        self.assertEqual(self.journal(), before)


if __name__ == "__main__":
    unittest.main()
