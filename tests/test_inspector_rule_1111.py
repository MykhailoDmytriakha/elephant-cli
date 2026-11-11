"""The inspector rule (the owner's word, 2026-11-09: «like building a house: we built what we could; the inspector came and
said do this and this; a crew was sent, finished it, and we moved on»; «go», 2026-11-11). A phase promises what it can
prove now and closes on it; a check that comes later is an item of the phase where it happens, and one made elsewhere —
or a repeat that may come — returns as a new phase when it comes.

The form of the failure (the radio with Codex, measured 2026-11-09 on a copy of his long case): twenty phases stood
paused; in eleven every item was done and accepted, the phase «waited for the acceptance in main»; one was paused 29
times in a day for a repeat that might come. el's doors led into the wait: an item after an item of a phase that had not
run was told «finish that first», and a hold, a pause and the return from a detour named only `resume`. Each printed
door is executed here as printed."""
import re
import shlex
import unittest

from elephant import stamp
from tests.test_commands import run
from tests.test_long_case_1105 import Base


def door(text: str, verb: str) -> list:
    """The first printed `el <verb> …` command in TEXT, as argv (without `el`); quoted words kept whole."""
    m = re.search(rf"el {verb} [^·()—\n]*?(?=\s+(?:·|\(|—|$)|\n|$)", text)
    assert m, f"no `el {verb}` in: {text}"
    return shlex.split(m.group(0))[1:]


class Probe(Base):
    """Phase 1 running with the fix done; phase 4 planned with the check on deploy."""

    def setUp(self):
        super().setUp()
        self.ok("phase", "plan", "1", "Fix", "--goal", "fix in, tests green [run: tests → OK]")
        self.ok("phase", "plan", "2", "Next bug", "--goal", "next [run: t → OK]")
        self.ok("phase", "plan", "4", "Deploy", "--goal", "works on deploy [run: smoke → OK]")
        self.ok("phase", "open", "1")
        self.ok("todo", "add", "1", "fix the parser", "--expect", "[run: tests → OK]")
        self.ok("todo", "add", "1", "works on deploy", "--expect", "[run: smoke → OK]")
        self.ok("todo", "add", "4", "smoke on deploy", "--expect", "[run: smoke → OK]")
        self.ok("todo", "done", "1.1", "run:tests → OK", "parser fixed")

    def closes(self):
        code, out, err = run("phase", "close", "1", "parser fixed", "--reflect", "a check is its own phase",
                             "--align", "deploy checks go to phase 4")
        self.assertEqual(code, 0, out + err)
        self.assertRegex(self.read("TODO.md"), r"(?m)^- \[x\] 1 Fix")


class AnAfterIntoAPhaseThatHasNotRun(Probe):
    def test_after_names_the_move_and_the_move_closes_the_phase(self):
        out, _ = self.ok("todo", "after", "1.2", "4.1")
        self.assertIn("phase 4, which has not run", out)
        self.ok(*door(out, "todo move"))
        self.assertIn("4.2 works on deploy — after: 4.1", self.read("TODO.md"))
        self.closes()

    def test_the_thread_no_longer_says_finish_that_first(self):
        self.ok("todo", "after", "1.2", "4.1")
        out, _ = self.ok()
        thread = next(ln for ln in out.splitlines() if ln.startswith("thread:"))
        self.assertNotIn("finish that first", thread)
        self.assertIn("el todo move 1.2 4", thread)

    def test_an_after_inside_the_running_phase_still_says_finish_it(self):
        self.ok("todo", "reopen", "1.1", "the parser fix is not in yet")
        self.ok("todo", "after", "1.2", "1.1")
        self.ok("todo", "hold", "1.1", "waiting for: the review")
        out, _ = self.ok()
        thread = next(ln for ln in out.splitlines() if ln.startswith("thread:"))
        self.assertIn("waiting: 1.1", thread)
        out, _ = self.ok("todo", "after", "1.2", "1.1")
        self.assertNotIn("has not run", out)

    def test_the_close_refusal_names_the_move(self):
        self.ok("todo", "after", "1.2", "4.1")
        code, out, err = run("phase", "close", "1", "parser fixed")
        self.assertEqual(code, 4)
        self.assertIn("el todo move 1.2 4", err)


class AHoldThatLeavesThePhaseNothingElse(Probe):
    def test_the_hold_names_the_doors_and_the_printed_cancel_closes(self):
        out, _ = self.ok("todo", "hold", "1.2", "waiting for: the deploy")
        self.assertIn("the inspector rule: phase 1 has nothing left but waiting (1.2)", out)
        self.ok(*door(out, "todo cancel"))
        self.closes()

    def test_a_hold_beside_open_work_says_nothing_of_it(self):
        self.ok("todo", "add", "1", "write the changelog", "--expect", "[run: tests → OK]")
        out, _ = self.ok("todo", "hold", "1.2", "waiting for: the deploy")
        self.assertNotIn("inspector", out)

    def test_the_thread_of_a_phase_that_only_waits_names_the_way(self):
        self.ok("todo", "hold", "1.2", "waiting for: the deploy")
        out, _ = self.ok()
        thread = next(ln for ln in out.splitlines() if ln.startswith("thread:"))
        self.assertIn("it came: el todo resume 1.2", thread)
        self.assertIn("el todo cancel 1.2", thread)


class APauseOverAPhaseWithNothingToResume(Probe):
    def test_a_pause_over_a_wait_names_the_doors(self):
        self.ok("todo", "hold", "1.2", "waiting for: a repeat of the bug")
        out, _ = self.ok("phase", "open", "2", "--why", "the next bug while 1 waits")
        self.assertIn("paused", out)
        self.assertIn("the inspector rule: phase 1 has nothing left but waiting", out)

    def test_a_pause_over_ended_work_prints_a_close_that_passes(self):
        self.ok("todo", "cancel", "1.2", "the deploy check is phase 4")
        out, _ = self.ok("phase", "open", "2", "--why", "awaits the acceptance in main")
        self.assertIn("every item of phase 1 ended", out)
        code, o, e = run(*door(out, "phase close"))
        self.assertEqual(code, 0, o + e)
        self.assertRegex(self.read("TODO.md"), r"(?m)^- \[x\] 1 ")

    def test_the_return_from_the_detour_names_the_way(self):
        self.ok("todo", "hold", "1.2", "waiting for: a repeat of the bug")
        self.ok("phase", "open", "2", "--why", "the next bug while 1 waits")
        self.ok("todo", "add", "2", "the next bug", "--expect", "[run: t → OK]")
        self.ok("todo", "done", "2.1", "run:t → OK", "fixed")
        out, _ = self.ok("phase", "close", "2", "fixed")
        self.assertIn("phase 1 Fix resumed", out)
        self.assertIn("the inspector rule: phase 1 has nothing left but waiting", out)


class TheGeneralListAndTheDose(Base):
    def test_a_later_line_through_three_closes_names_the_inspector(self):
        self.ok("todo", "add", "later", "check the returns once the fix is in main")
        body, _ = stamp.split(self.read("TODO.md"))  # the line lies since long ago: today's closes pass it by
        (self.case() / "TODO.md").write_text(stamp.apply(re.sub(r"since: \d{4}-\d{2}-\d{2}", "since: 2026-01-01", body)),
                                             encoding="utf-8")
        for n in (1, 2, 3):
            self.ok("phase", "open", str(n), f"P{n}", "--goal", "x [run: t → OK]")
            self.ok("todo", "add", str(n), "work", "--expect", "[run: t → OK]")
            self.ok("todo", "done", f"{n}.1", "run:t → OK", "done")
            self.ok("phase", "close", str(n), "done")
        out, _ = self.ok("order")
        line = next(ln for ln in out.splitlines() if "L1" in ln and "phase closes" in ln)
        self.assertIn("returns as a new phase", line)

    def test_the_dose_carries_the_rule(self):
        out, _ = self.ok("help", "phases")
        self.assertIn("the inspector rule", out)
        out, _ = self.ok("help", "later")
        self.assertIn("the inspector rule", out)


if __name__ == "__main__":
    unittest.main()
