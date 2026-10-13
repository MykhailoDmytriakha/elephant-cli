"""Two reports of 2026-10-12, one hole — el said what it could not know.

1. A done item folded out of TODO by `phase close` read «gone (cancelled or dropped)» to the item that waited for it
   (moved out of the phase before the close): Order offered to cancel the live item, the thread called it blocked,
   `todo show` said gone, `todo after` said «no item», `done` said «still open». The close folds the view; the item
   stays done — read back from its phase file.
2. `accept` laid the re-runs against the doer's run proofs by position whatever their numbers: a doer's one line
   «A · B · C» re-run as three --run A, B, C printed «differs», and the acceptor could not tell what was kept. el now
   compares only a pair it knows — as many re-runs as proofs, one command → one outcome on both sides — says when it
   did not compare, and prints every re-run it kept."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    KEYS = ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_CASE")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="doer1012", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "engine", "--goal", "x")
        run("phase", "open", "1", "Work", "--goal", "x")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def ok(self, *argv):
        code, out, err = run(*argv)
        self.assertEqual(code, 0, f"{argv}: {err}")
        return out, err


class AfterADoneItemOfAClosedPhase(Base):
    def setUp(self):
        super().setUp()
        for k in ("one", "two", "three", "four"):
            self.ok("todo", "add", "1", f"step {k}")
        self.ok("todo", "after", "1.4", "1.3")
        self.ok("phase", "plan", "2", "Next", "--goal", "y")
        for k in (1, 2, 3):
            self.ok("todo", "done", f"1.{k}", "run:make test → 12 OK", f"step {k} works")
        self.ok("todo", "move", "1.4", "2")  # → 2.1, still after 1.3
        self.ok("phase", "close", "1", "steps work", "--reflect", "r", "--align", "a")
        self.ok("phase", "open", "2")

    def test_the_reports_acceptance(self):  # Order names nothing about the edge to a done item of a closed phase
        _, out, _ = run("order")
        self.assertNotIn("gone", out)
        self.assertNotIn("is after 1.3", out)
        _, out, _ = run()
        thread = next(ln for ln in out.split("\n") if ln.startswith("thread:"))
        self.assertNotIn("blocked", thread)
        self.assertIn("item 2.1", thread)

    def test_every_voice_sees_the_done_input(self):
        out, _ = self.ok("todo", "show", "2.1")
        self.assertIn("← 1.3 ✓ «step three» — run make test → 12 OK", out)
        self.ok("todo", "after", "2.1", "1.3")  # an input already there is a legal edge, not «no item 1.3»
        code, _, err = run("todo", "after", "2.1", "1.9")
        self.assertEqual(code, 4, "an item that never was is still no item")
        self.assertIn("no item 1.9", err)
        _, err = self.ok("todo", "done", "2.1", "run:make test → 12 OK", "four")
        self.assertNotIn("was after", err)


class RerunsAgainstProofs(Base):
    def setUp(self):
        super().setUp()
        self.ok("todo", "add", "1", "bundle")

    def done(self, *proofs):
        self.ok("todo", "done", "1.1", *proofs, "bundle builds")
        os.environ["EL_SESSION"] = "accept12"

    def test_the_reports_acceptance(self):  # 'A · B · C' accepted with --run A, B, C: no «differs», the three listed
        self.done("run:git status → clean · make bundle → built · fp → abc")
        out, err = self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "git status → clean",
                           "--run", "make bundle → built", "--run", "fp → abc", "re-ran the three")
        self.assertNotIn("differs", err)
        self.assertNotIn("not compared", out)
        self.assertIn("kept in the DECISION, every one — 3 re-run(s):\n    git status → clean\n    make bundle → built\n"
                      "    fp → abc", out)
        self.assertIn("counted on the item(s): 1.1 re-ran 1 of 1", out)

    def test_more_reruns_than_proofs_are_not_compared_and_say_so(self):
        self.done("run:git status → clean · fp → abc")
        out, err = self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "git status → clean",
                           "--run", "fp → xyz", "re-ran both")
        self.assertNotIn("differs", err)
        self.assertIn("1.1: not compared — the doer recorded 1 run proof(s), you brought 2", out)
        self.assertIn("«git status → clean · fp → abc»", out)

    def test_a_not_run_between_shifts_no_pair(self):  # the old zip laid «lint → clean» against «make test → 12 OK»
        self.done("run:make test → 12 OK", "run:lint → clean")
        out, err = self.ok("todo", "accept", "1.1", "--by", "codex", "--run", "make test → not run: no tools here",
                           "--run", "lint → clean", "read the log")
        self.assertNotIn("differs", err)
        self.assertIn("1.1 re-ran 1 of 2 (1 not run)", out)

    def test_one_to_one_still_compares(self):
        self.done("run:make test → 12 OK")
        _, err = self.ok("todo", "accept", "1.1", "--by", "codex", "--run", "make test → 11 OK, 1 FAIL", "re-ran")
        self.assertIn("1.1: the doer's run came out «12 OK», yours «11 OK, 1 FAIL»", err)

    def test_the_brief_does_not_offer_the_first_command_as_the_proof(self):
        self.done("run:git status → clean · fp → abc")
        out, _ = self.ok("todo", "brief", "1.1")
        self.assertNotIn('--run "git status → <what came out now>"', out)
        self.assertIn('--run "<each command it holds> → <what came out now>"', out)
        self.assertIn("several runs in one line — re-run each, one --run per command", out)

    def test_the_refusal_keeps_the_rerun_given(self):  # printed without it, the command met the same refusal again
        self.done("run:make test → 12 OK", "run:lint → clean")
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test → 12 OK", "re-ran")
        self.assertEqual(code, 2)
        self.assertIn('--run "make test → 12 OK" --run "lint → <what came out now>"', err)
        self.assertIn("«make test → 12 OK» · «lint → clean»", err)


if __name__ == "__main__":
    unittest.main()
