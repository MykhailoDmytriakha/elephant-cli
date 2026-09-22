"""The owner's word, 2026-09-17: a legacy case and its closed phases stay as they are, but the phase you WORK in
is the write door itself and is held to the current form — strictly. Order names what the running phase lacks
(a promise in the goal, expect on open items, a kind on every tick); `check` counts a tick without a kind in the
running phase as a violation; closed phases and planned phases are never asked."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import store
from tests.test_commands import run


class RunningPhaseIsStrict(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "old", "--goal", "g")
        run("phase", "open", "1", "Before", "--goal", "an old goal without a promise")
        run("todo", "add", "1", "a")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")

    def tick_without_kind(self, ref: str):
        body = self.read("TODO.md")
        body = body[: body.rindex("\nstamp: ")] + "\n"
        n, m = ref.split(".")
        body = body.replace(f"  - [ ] {ref} ", f"  - [x] {ref} ")
        store.write(self.case, "TODO.md", body)

    def test_the_running_phase_is_named_and_checked_the_closed_one_is_history(self):
        self.tick_without_kind("1.1")  # an old tick, as before 1.5.0
        code, out, err = run()
        order = out.split("## Order")[1]
        self.assertIn("phase 1 Before (running): its goal promises no proof — what must be true when it closes?", order)
        self.assertIn("1 tick(s) without a kind of evidence in the running phase — 1.1 → el todo done N.M <kind>", order)
        code, out, err = run("check")
        self.assertEqual(code, 3, "a tick without a kind where the work is: F20 broken, not history")
        self.assertIn("x 2026-", err + out)
        self.assertIn("F20 · 1.1 is done without a kind of evidence in the running phase", err + out)
        run("todo", "done", "1.1", "owner", "attached")
        self.assertNotIn("without a kind", run()[1])
        self.assertEqual(run("check")[0], 0)
        # close it the old way (no promise in the goal) — allowed: the goal promised nothing
        run("log", "RESULT", "r")
        code, out, err = run("phase", "close", "1", "closed", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)
        # a new phase opens: the closed one is history and says nothing more
        run("phase", "open", "2", "Now", "--goal", "the real thing [run: it works]")
        order = run()[1].split("## Order")[1]
        self.assertNotIn("phase 1 Before", order)
        self.assertIn("phase 2 Now promises [run: it works] and no item promises it", order, "the running phase is held to its promise")
        run("phase", "plan", "3", "Later", "--goal", "later without a promise")
        run("todo", "add", "3", "parked")
        self.assertNotIn("phase 3 Later (running)", run()[1], "a planned phase is not running: nothing asked yet")
        self.assertEqual(run("check")[0], 0)


if __name__ == "__main__":
    unittest.main()
