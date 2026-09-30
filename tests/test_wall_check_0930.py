"""L4, the wall with a way out (move D of the report of 2026-09-25; the live wall came 2026-09-30).

An item waited for another team's ticket. The hold said what it waited for, but the next agent — without memory — could
only guess whether the wait was over, or ask the owner. `el todo hold N.M "…" --check '<command>'` records the command that
tells: `— check: …` after the hold reason; the entry's thread names it; el never runs it (the owner's word, 2026-09-22);
a hold again keeps it, `--check none` takes it away, `resume` ends it with the hold."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar
from tests.test_commands import run

HOLD = "waiting for: ticket REQ-1, network team's queue"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_SESSION"] = "doer0930"  # EL_TWO_HANDS=0 comes from tests/__init__.py
        run("case", "new", "net access", "--goal", "g")
        run("phase", "open", "1", "Access", "--goal", "port accessible [run: check-port.sh]")
        run("todo", "add", "1", "check the port", "--expect", "[run: check-port.sh]")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def todo_text(self) -> str:
        case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        return (case / "TODO.md").read_text(encoding="utf-8")

    def item(self) -> grammar.Item:
        return grammar.parse_todo(self.todo_text()).phase(1).items[0]

    def thread(self) -> str:
        code, out, err = run()
        self.assertEqual(code, 0, err)
        return next(ln for ln in out.split("\n") if ln.startswith("thread: "))


class TheWallHasAWayOut(Base):
    def test_the_check_is_recorded_named_on_entry_and_never_run(self):
        code, out, err = run("todo", "hold", "1.1", HOLD, "--check", "touch ran.txt && ./check-port.sh")
        self.assertEqual(code, 0, err)
        self.assertIn(f"[~] 1.1 check the port — hold: {HOLD} — check: touch ran.txt && ./check-port.sh", self.todo_text())
        self.assertEqual((self.item().hold_reason, self.item().hold_check), (HOLD, "touch ran.txt && ./check-port.sh"))
        self.assertIn("is it over? `touch ran.txt && ./check-port.sh` — it came: el todo resume 1.1", self.thread())
        self.assertFalse(Path("ran.txt").exists(), "el never runs a check — the agent does")
        self.assertEqual(run("check")[0], 0)

    def test_a_hold_again_keeps_the_check_and_none_takes_it_away(self):
        run("todo", "hold", "1.1", HOLD, "--check", "./check-port.sh")
        run("todo", "hold", "1.1", HOLD + ", day 2")
        self.assertEqual(self.item().hold_check, "./check-port.sh")
        self.assertEqual(self.item().hold_reason, HOLD + ", day 2")
        run("todo", "hold", "1.1", HOLD, "--check", "none")
        self.assertEqual(self.item().hold_check, "")
        self.assertNotIn("— check:", self.todo_text())

    def test_resume_ends_the_check_with_the_hold_and_says_it(self):
        run("todo", "hold", "1.1", HOLD, "--check", "./check-port.sh")
        code, out, err = run("todo", "resume", "1.1")
        self.assertEqual(code, 0, err)
        self.assertIn("the wait had its check: `./check-port.sh`", out)
        self.assertIn("  - [ ] 1.1 check the port\n", self.todo_text())
        self.assertNotIn("check:", self.todo_text().split("expect:")[0])

    def test_done_ends_the_check_with_the_hold(self):
        run("todo", "hold", "1.1", HOLD, "--check", "./check-port.sh")
        code, _, err = run("todo", "done", "1.1", "run:./check-port.sh → open", "the port answers")
        self.assertEqual(code, 0, err)
        self.assertNotIn("— check:", self.todo_text())

    def test_an_empty_check_and_a_shell_trace_are_refused(self):
        run("todo", "hold", "1.1", HOLD)
        before = self.todo_text()
        self.assertEqual(run("todo", "hold", "1.1", HOLD, "--check", " ")[0], 2)
        self.assertEqual(run("todo", "hold", "1.1", HOLD, "--check", "curl -s  /health")[0], 2)  # `$HOST` eaten in "…"
        self.assertEqual(self.todo_text(), before)

    def test_an_empty_check_line_is_a_grammar_error(self):
        text = "# TODO — t\n\n- [ ] 1 Access\n  - [~] 1.1 check the port — hold: waiting — check: \n"
        self.assertTrue(any("check:" in str(e) for e in grammar.parse_todo(text).errors))


if __name__ == "__main__":
    unittest.main()
