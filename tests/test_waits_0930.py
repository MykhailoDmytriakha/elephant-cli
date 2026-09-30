"""A report of 2026-09-30 11:58 (el 1.31.0): emergent decomposition and a wait on the outside.

The agent opened a phase whose goal promised a probe, read the Order line «the criterion nobody works towards» as «decompose
everything now», added the probe item, then found the way to it (an access request) and put it before. The probe then waited
for another team's ticket and stayed `[ ]` — «do me now» — because `hold` read to it as «broken» and the thread said «held
or blocked: see unblocked:», a pointer to a line that lists neither. Nothing was refused (the report feared a refusal at open;
checked: open passes, check counts no violation, the close holds the promise). Since 1.32.0: the Order line and the open
hint teach the beacon — the criterion item last, the steps before it as they are found; a hold names what it waits for
(required, like cancel's and reopen's reason); with no free item the thread names the wait and the move that ends it."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_SESSION"] = "doer0930"  # EL_TWO_HANDS=0 comes from tests/__init__.py
        run("case", "new", "net access", "--goal", "g")
        run("phase", "open", "1", "Setup", "--goal", "base [run: t]")
        run("todo", "add", "1", "base", "--expect", "[run: t]")
        run("todo", "done", "1.1", "run:t → ok", "ok")
        run("phase", "close", "1", "ok", "--reflect", "a lesson about the work", "--align", "the next plan")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def todo_text(self) -> str:
        case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        return (case / "TODO.md").read_text(encoding="utf-8")

    def thread(self) -> str:
        code, out, err = run()
        self.assertEqual(code, 0, err)
        return next(ln for ln in out.split("\n") if ln.startswith("thread: "))


class TheBeaconAndTheFrontier(Base):
    def test_a_promise_opens_without_its_item_and_order_teaches_the_beacon(self):
        code, _, err = run("phase", "open", "2", "Access", "--goal", "port accessible [run: check-port.sh]")
        self.assertEqual(code, 0, err)
        code, out, err = run("todo", "add", "2", "submit the access request", "--expect", "[ref: REQ-1]")
        self.assertEqual(code, 0, err)
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)
        self.assertIn("violations: 0", out + err)
        _, out, _ = run()
        line = next(ln for ln in out.split("\n") if "promises [run: check-port.sh]" in ln)
        self.assertIn("the phase's last item now", line)
        self.assertIn("--before 2.K", line)

    def test_the_close_still_holds_the_promise(self):
        run("phase", "open", "2", "Access", "--goal", "port accessible [run: check-port.sh]")
        run("todo", "add", "2", "submit the access request", "--expect", "[ref: REQ-1]")
        run("todo", "done", "2.1", "ref:REQ-1", "submitted")
        code, out, err = run("phase", "close", "2", "done", "--reflect", "a lesson about the work", "--align", "the next plan")
        self.assertEqual(code, 4)
        self.assertIn("[run: check-port.sh]", err)


class AWaitOnTheOutside(Base):
    def setUp(self):
        super().setUp()
        run("phase", "open", "2", "Access", "--goal", "port accessible [run: check-port.sh]")
        run("todo", "add", "2", "check the port", "--expect", "[run: check-port.sh]")
        run("todo", "add", "2", "submit the access request", "--before", "2.1", "--expect", "[ref: REQ-1]")
        run("todo", "done", "2.2", "ref:REQ-1", "submitted")

    def test_a_held_wait_is_named_by_the_thread_with_the_move_that_ends_it(self):
        code, out, err = run("todo", "hold", "2.1", "waiting for: ticket REQ-1, network team's queue")
        self.assertEqual(code, 0, err)
        self.assertIn("[~] 2.1 check the port — hold: waiting for: ticket REQ-1, network team's queue", self.todo_text())
        thread = self.thread()
        self.assertIn("waiting: 2.1 «waiting for: ticket REQ-1, network team's queue» — it came: el todo resume 2.1", thread)
        self.assertNotIn("see unblocked:", thread)  # 1.31.0 pointed at a line that never lists a held item

    def test_a_hold_without_its_reason_is_refused_and_writes_nothing(self):
        before = self.todo_text()
        code, out, err = run("todo", "hold", "2.1")
        self.assertEqual(code, 2)
        self.assertIn("hold needs what the item waits for", err)
        self.assertEqual(self.todo_text(), before)

    def test_the_root_of_the_wait_is_named_first_the_held_item_not_its_dependant(self):
        run("todo", "add", "2", "get the approval")
        run("todo", "after", "2.1", "2.3")
        run("todo", "hold", "2.3", "waiting for: the approver's answer")
        self.assertIn("waiting: 2.3 «waiting for: the approver's answer»", self.thread())

    def test_a_wait_on_an_item_elsewhere_is_named_as_blocked(self):
        run("phase", "plan", "3", "Rollout", "--goal", "g")
        run("todo", "add", "3", "announce the window")
        code, _, err = run("todo", "after", "2.1", "3.1")
        self.assertEqual(code, 0, err)
        self.assertIn("blocked: 2.1 after 3.1", self.thread())


if __name__ == "__main__":
    unittest.main()
