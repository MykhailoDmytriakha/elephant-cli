"""The owner's word, 2026-10-06 — a detour (F26), and with it the reverse-order wall of L4 (Codex, 2026-10-05).

Life goes sideways: in the middle of a phase something comes up that has to be done first («the furniture arrives, sign
the lease»), or a step five back has to be redone («the bolt must be longer»). Phases run one at a time, so a phase
planned «before» the one in flight could neither open (another is in flight) nor close from the plan (nothing unfinished
before it): `done` passed, then `close` and `open` refused each other. The owner: «allow adding a phase that goes before
this one — and put the next on hold until we finish». `el phase open K --why "what came up"` now pauses the phase in
flight — `[~]`, `hold: phase K Name — why`, ⏸ in progress — and when K closes or is cancelled el resumes it by itself:
the detour has a return address. Work in the paused phase stays legal; one phase stays in flight."""
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
        os.environ.update(EL_HINTS="0", EL_SESSION="detour1006", EL_TWO_HANDS="0")
        run("case", "new", "move", "--goal", "the office moved")
        run("phase", "open", "5", "Furniture", "--goal", "furniture ordered [owner]")
        run("todo", "add", "5", "choose the furniture", "--expect", "[owner]")
        run("todo", "add", "5", "order the delivery", "--expect", "[owner]")
        run("todo", "done", "5.1", "owner", "chosen")

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

    def phase_line(self, n: int) -> str:
        return next(ln for ln in self.read("TODO.md").split("\n") if ln.startswith(("- [ ] %d " % n, "- [~] %d " % n, "- [x] %d " % n)))

    def progress(self) -> str:
        return next(ln for ln in self.read("README.md").split("\n") if ln.startswith("- progress:"))

    def detour(self, n=6, name="Lease", why="the furniture arrives on 10.10, no lease no entry"):
        code, out, err = run("phase", "open", str(n), name, "--goal", "the lease signed [owner]", "--why", why)
        self.assertEqual(code, 0, err)
        return out

    def finish(self, n: int, what="done"):
        run("todo", "add", str(n), what, "--expect", "[owner]")
        ref = next(ln.split()[3] for ln in self.read("TODO.md").split("\n") if ln.startswith(f"  - [ ] {n}."))
        run("todo", "done", ref, "owner", what)
        code, out, err = run("phase", "close", str(n), what, "--reflect", "a detour went first", "--align", "back to the plan")
        self.assertEqual(code, 0, err)
        return out


class TheGrammar(unittest.TestCase):
    TODO = ("# TODO — t\n\n"
            "- [~] 5 Furniture — ordered [owner] · [phases/5-furniture.md](phases/5-furniture.md) — hold: phase 6 Lease — no lease no entry\n"
            "  - [ ] 5.2 order the delivery\n"
            "- [ ] 6 Lease — signed · [phases/6-lease.md](phases/6-lease.md)\n")

    def test_a_paused_phase_is_read_with_what_it_waits_for(self):
        r = grammar.parse_todo(self.TODO)
        self.assertTrue(r.ok, r.errors)
        p = r.phases[0]
        self.assertTrue(p.held)
        self.assertEqual(p.held_for(), 6)
        self.assertEqual(p.summary, "ordered [owner] · [phases/5-furniture.md](phases/5-furniture.md)")

    def test_a_hold_needs_its_mark_and_a_mark_needs_its_hold(self):
        r = grammar.parse_todo(self.TODO.replace("- [~] 5", "- [ ] 5"))
        self.assertTrue(any(f.rule == "F26" for f in r.errors), r.errors)
        r = grammar.parse_todo(self.TODO.replace(" — hold: phase 6 Lease — no lease no entry", ""))
        self.assertTrue(any(f.rule == "F26" and "no reason" in f.message for f in r.errors), r.errors)


class ADetour(Base):
    def test_without_a_reason_the_refusal_names_the_pause(self):
        code, _, err = run("phase", "open", "6", "Lease", "--goal", "the lease signed [owner]")
        self.assertEqual(code, 4)
        self.assertIn('pause it for this one: el phase open 6 --why "what came up" (5 resumes when 6 ends)', err)

    def test_the_phase_in_flight_pauses_with_the_reason(self):
        out = self.detour()
        self.assertIn("phase 5 Furniture paused", out)
        self.assertIn("— hold: phase 6 Lease — the furniture arrives on 10.10, no lease no entry", self.phase_line(5))
        self.assertTrue(self.phase_line(5).startswith("- [~] 5 Furniture"))
        self.assertIn("5 Furniture ⏸ · 6 Lease ▶", self.progress())
        self.assertIn("фаза 5 Furniture на паузе ради фазы 6 Lease — the furniture arrives", self.read("JOURNAL.md"))
        code, out, _ = run()
        thread = next(ln for ln in out.split("\n") if ln.startswith("thread: "))
        self.assertIn("phase 6 Lease", thread)
        self.assertIn("a detour: 5 Furniture paused for it", thread)

    def test_closing_the_detour_resumes_the_paused_phase(self):
        self.detour()
        out = self.finish(6, "sign the lease")
        self.assertIn("phase 5 Furniture resumed — the detour 6 is over; next: 5.2 order the delivery", out)
        self.assertTrue(self.phase_line(5).startswith("- [ ] 5 Furniture"))
        self.assertNotIn("hold:", self.phase_line(5))
        self.assertIn("5 Furniture ▶ · 6 Lease ✓", self.progress())

    def test_cancelling_the_detour_resumes_it_too(self):
        self.detour()
        code, out, err = run("phase", "cancel", "6", "the landlord let us in without it")
        self.assertEqual(code, 0, err)
        self.assertIn("phase 5 Furniture resumed — the detour 6 is over", out)

    def test_detours_inside_detours_unwind_one_at_a_time(self):
        self.detour(6, "Bolt", "the bracket needs 10 mm more thread")
        code, out, err = run("phase", "open", "7", "Parts", "--goal", "a longer bolt bought [owner]", "--why", "none in stock")
        self.assertEqual(code, 0, err)
        self.assertIn("5 Furniture ⏸ · 6 Bolt ⏸ · 7 Parts ▶", self.progress())
        out = self.finish(7, "buy the bolt")
        self.assertIn("phase 6 Bolt resumed", out)
        self.assertIn("5 Furniture ⏸ · 6 Bolt ▶", self.progress())
        out = self.finish(6, "replace the bolt")
        self.assertIn("phase 5 Furniture resumed", out)

    def test_work_in_the_paused_phase_stays_legal(self):
        self.detour()
        code, _, err = run("todo", "done", "5.2", "owner", "ordered")
        self.assertEqual(code, 0, err)

    def test_resume_by_hand_waits_for_the_phase_in_flight(self):
        self.detour()
        code, _, err = run("phase", "resume", "5")
        self.assertEqual(code, 4)
        self.assertIn("5 resumes by itself when 6 closes", err)
        code, out, _ = run("phase", "resume", "6")
        self.assertIn("not on hold — nothing changed", out)


class TheReverseOrderWall(Base):
    """L4, the Codex case: a phase planned below the one in flight, its work done — close and open refused each other."""
    def test_the_planned_phase_below_closes_through_a_detour(self):
        run("phase", "plan", "4", "Lease", "--goal", "the lease signed [owner]")
        run("todo", "add", "4", "sign the lease", "--expect", "[owner]")
        self.assertEqual(run("todo", "done", "4.1", "owner", "signed")[0], 0)
        code, _, err = run("phase", "close", "4", "signed", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn('pause it for this one: el phase open 4 --why "what came up"', err, "the refusal names a command that runs")
        code, out, _ = run()
        self.assertIn('phase 4 Lease: every item ended, planned and never opened while 5 Furniture is in flight → pause it '
                      'for this one: el phase open 4 --why', out)
        code, _, err = run("phase", "open", "4", "--why", "the lease had to come first")
        self.assertEqual(code, 0, err)
        code, out, err = run("phase", "close", "4", "signed", "--reflect", "a detour went first", "--align", "back to the furniture")
        self.assertEqual(code, 0, err)
        self.assertIn("phase 5 Furniture resumed — the detour 4 is over", out)


if __name__ == "__main__":
    unittest.main()
