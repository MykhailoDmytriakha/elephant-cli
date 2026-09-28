"""Two reports of 2026-09-27 (el 1.28.0).

1. A bare write landed in another session's case: two sessions in one working tree, each with its own case — the hand
   followed the freshest journal, which in a shared tree is another agent's, and B's RESULT and tick went into A, exit 0.
   Since 1.29.0 the hand belongs to the session: the case it last wrote to, or took (case new · spawn · case use), or
   first picked up; a harness without a session id keeps the old rule.
2. `todo reopen` with a reason too long for the journal answered exit 3 «nothing was written» after TODO had lost the
   item's result and proofs. Since 1.29.0 a command is one change: whatever it wrote before a refusal is put back."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

LONG = " ".join(["word"] * 230)  # beyond a headline plus five body lines (F7)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        for k in ("EL_CASE", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_HINTS"] = "0"

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def as_(self, session, *args):
        os.environ["EL_SESSION"] = session
        return run(*args)

    def case(self, suffix):
        return next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.name.endswith(suffix))

    def new(self, session, name):
        self.as_(session, "case", "new", name, "--goal", "g")
        self.as_(session, "phase", "open", "1", "Work", "--goal", "g")
        self.as_(session, "todo", "add", "1", f"item of {name}", "--expect", "[run: c]")


class TheHandBelongsToTheSession(Base):
    def test_the_report_repro_lands_in_the_session_case(self):
        self.new("sessone1", "bee")
        self.as_("sessone1", "log", "RESULT", "x")
        self.new("sesstwo2", "ant")
        self.as_("sesstwo2", "log", "RESULT", "y")
        code, out, err = self.as_("sessone1", "todo", "done", "1.1", "run:c → o", "z")
        self.assertEqual(code, 0, err)
        self.assertIn("[x] 1.1 item of bee", (self.case("bee") / "TODO.md").read_text())
        self.assertIn("[ ] 1.1 item of ant", (self.case("ant") / "TODO.md").read_text(), "the other session's case untouched")
        self.assertNotIn("RESULT · 1.1", (self.case("ant") / "JOURNAL.md").read_text())

    def test_an_explicit_write_moves_the_hand_a_read_does_not(self):
        self.new("s1", "bee")
        self.new("s2", "ant")
        self.as_("s1", "--case", "ant", "status")  # a look at another case is not taking it
        code, out, _ = self.as_("s1", "status")
        self.assertIn("case in hand: ", out)
        self.assertIn("bee", out.splitlines()[0])
        self.as_("s1", "--case", "ant", "log", "DECISION", "chose x")  # a write is: the case it last wrote to
        code, out, _ = self.as_("s1", "status")
        self.assertIn("ant", out.splitlines()[0])

    def test_case_use_and_spawn_take_the_hand(self):
        self.new("s1", "bee")
        self.new("s2", "ant")
        self.as_("s1", "case", "use", "ant")
        self.assertIn("ant", self.as_("s1", "status")[1].splitlines()[0])
        self.as_("s1", "spawn", "cause", "--goal", "g")
        self.assertIn("cause", self.as_("s1", "status")[1].splitlines()[0], "the child, not the parent written first")
        self.as_("s2", "log", "DECISION", "elsewhere")  # another session writing does not move it back
        self.assertIn("cause", self.as_("s1", "status")[1].splitlines()[0])

    def test_a_closed_held_case_hands_over_to_the_freshest(self):
        self.new("s1", "bee")
        self.as_("s1", "case", "cancel", "not needed")
        self.new("s2", "ant")
        self.assertIn("ant", self.as_("s1", "status")[1].splitlines()[0])

    def test_without_a_session_id_the_old_rule_holds(self):
        self.new("s1", "bee")
        self.new("s2", "ant")
        os.environ.pop("EL_SESSION")
        self.assertIn("ant", run("status")[1].splitlines()[0], "the freshest journal, as before")


class ARefusalIsWhole(Base):
    def setUp(self):
        super().setUp()
        self.new("doer1", "api")
        self.as_("doer1", "todo", "done", "1.1", "run:c → o", "done")
        self.todo = self.case("api") / "TODO.md"
        self.journal = self.case("api") / "JOURNAL.md"

    def test_reopen_refused_leaves_every_file_as_it_was(self):
        before, jbefore = self.todo.read_bytes(), self.journal.read_bytes()
        code, out, err = self.as_("second2", "todo", "reopen", "1.1", "--by", "subagent", LONG)
        self.assertEqual(code, 3)
        self.assertIn("put back as it was:", err)
        self.assertIn("TODO.md", err)
        self.assertEqual(self.todo.read_bytes(), before, "«nothing was written» is true byte for byte")
        self.assertEqual(self.journal.read_bytes(), jbefore)
        code, out, err = self.as_("second2", "todo", "reopen", "1.1", "--by", "subagent", "short reason")
        self.assertEqual(code, 0, err)
        self.assertIn("reopened: 1.1", out, "not «open already»: the refused reopen left nothing half-done")
        self.assertIn("short reason", self.journal.read_text())

    def test_cancel_refused_leaves_todo_as_it_was(self):
        self.as_("doer1", "todo", "add", "1", "second", "--expect", "[run: c]")
        before = self.todo.read_bytes()
        code, _, err = self.as_("doer1", "todo", "cancel", "1.2", LONG)
        self.assertEqual(code, 3)
        self.assertEqual(self.todo.read_bytes(), before)

    def test_a_refusal_before_any_write_says_nothing_about_putting_back(self):
        code, _, err = self.as_("doer1", "todo", "done", "1.9", "run:c → o", "x")
        self.assertNotEqual(code, 0)
        self.assertNotIn("put back", err)


if __name__ == "__main__":
    unittest.main()
