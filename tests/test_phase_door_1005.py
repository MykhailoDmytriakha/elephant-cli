"""Three reports of 2026-10-05 23:11 (el 1.37.0) — the phase's door and the phase's line.

1. A closed phase's line in TODO carried only the closer's words — «delivered — accepted by a second hand» — while el's
   own count, «same session 8 of 8», sat one file deeper in the Digest. el's count stands beside the words now wherever
   the phase is read in one line: the TODO line, the phase file's `result:` (which README Links draws), the output.
2. The way of a Later thought into a phase cost three refusals, each revealing one more rule (plan it · the name is
   English · open it — this one only at close). The first refusal names the whole way; the name rule says where words
   in another language go (the goal).
3. Work was done and accepted in a phase that was planned and never opened; only `phase close` refused — the fix taught
   after the work. `done` now refuses while `el phase open N` would let the phase in — the printed command runs. Work in
   a phase out of turn (another phase running, or a planned phase below that would need a reason) stays legal: it
   closes from the plan (the owner's exit, 2026-09-14). Adding items to a plan stays open."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    two_hands = "0"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="doer2311", EL_TWO_HANDS=self.two_hands)
        run("case", "new", "probe", "--goal", "g")

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


class TheCountStandsBesideTheWords(Base):
    two_hands = "1"

    def close_accepted(self, acceptor_session: str):
        (Path(self.tmp.name) / "notes.md").write_text("x\n")
        run("phase", "open", "1", "Probe", "--goal", "g1")
        run("phase", "agree", "1", "the owner's scope")
        run("todo", "add", "1", "first item", "--expect", "a file [file: notes.md]")
        run("todo", "done", "1.1", "file:notes.md", "wrote the note")
        os.environ["EL_SESSION"] = acceptor_session
        run("todo", "accept", "1.1", "--by", "fresh-session", "checked the note")
        run("log", "RESULT", "r")
        code, out, err = run("phase", "close", "1", "delivered the note — accepted by a second hand", "--reflect", "-", "--align", "-")
        self.assertEqual(code, 0, err)
        return out

    def test_a_same_session_acceptance_is_said_in_the_line_people_read(self):
        out = self.close_accepted("doer2311")
        line = next(ln for ln in self.read("TODO.md").split("\n") if ln.startswith("- [x] 1 Probe"))
        self.assertIn("delivered the note — accepted by a second hand · acceptance: 1 of 1 done accepted — same session 1", line,
                      "the closer's words stay; el's count stands beside them")
        self.assertIn("· acceptance: 1 of 1 done accepted — same session 1", out)
        self.assertIn("result: delivered the note — accepted by a second hand · acceptance: 1 of 1 done accepted — same session 1",
                      (self.case() / "phases" / "1-probe.md").read_text())
        self.assertIn("acceptance: 1 of 1 done accepted — same session 1", self.read("README.md"), "Links draws the result line")

    def test_a_fresh_session_acceptance_is_said_as_such(self):
        self.close_accepted("fresh0002")
        self.assertIn("acceptance: 1 of 1 done accepted — another session 1", self.read("TODO.md"))


class ACaseWithoutAcceptanceLivesAsBefore(Base):
    def test_no_count_where_nothing_was_accepted_and_one_hand_is_the_rule(self):
        run("phase", "open", "1", "Probe", "--goal", "g1")
        run("todo", "add", "1", "first item", "--expect", "[owner]")
        run("todo", "done", "1.1", "owner", "done")
        run("log", "RESULT", "r")
        run("phase", "close", "1", "delivered", "--reflect", "-", "--align", "-")
        self.assertNotIn("acceptance:", next(ln for ln in self.read("TODO.md").split("\n") if ln.startswith("- [x] 1 ")))


class TheWholeWayInOneRefusal(Base):
    def test_a_later_thought_into_a_phase_that_is_not_there(self):
        run("todo", "add", "later", "fix the export label")
        code, out, err = run("todo", "move", "L1", "2")
        self.assertEqual(code, 4)
        for part in ("English, 1–3 words", "--goal", "el todo move L1 2", "el phase open 2"):
            self.assertIn(part, err, part)

    def test_an_item_into_a_phase_that_is_not_there(self):
        run("phase", "open", "1", "Probe", "--goal", "g1")
        run("todo", "add", "1", "first item")
        code, out, err = run("todo", "move", "1.1", "2")
        self.assertEqual(code, 4)
        self.assertIn("el phase open 2", err)

    def test_the_name_rule_says_where_the_words_go(self):
        code, out, err = run("phase", "plan", "2", "Добить хвосты")
        self.assertEqual(code, 2)
        self.assertIn("--goal 'Добить хвосты'", err, "the words in your language go into the goal")


class TheDoorStandsBeforeTheWork(Base):
    def test_done_in_a_planned_phase_that_could_open(self):
        run("phase", "plan", "1", "Probe", "--goal", "g1")
        self.assertEqual(run("todo", "add", "1", "first item")[0], 0, "planning ahead stays open")
        before = self.read("TODO.md")
        code, out, err = run("todo", "done", "1.1", "run:echo ok → ok", "done")
        self.assertEqual(code, 4)
        self.assertIn("phase 1 Probe is planned, not open — it can open now: el phase open 1", err)
        self.assertEqual(self.read("TODO.md"), before, "nothing was written")
        self.assertEqual(run("phase", "open", "1")[0], 0, "the printed command runs")
        self.assertEqual(run("todo", "done", "1.1", "run:echo ok → ok", "done")[0], 0)

    def test_out_of_turn_beside_a_running_phase_stays_legal(self):
        run("phase", "open", "1", "Run", "--goal", "g1")
        run("phase", "plan", "2", "Beside", "--goal", "g2")
        run("todo", "add", "2", "a step that ends early")
        code, out, err = run("todo", "done", "2.1", "run:echo ok → ok", "done")
        self.assertEqual(code, 0, "phase 1 is running: phase 2 cannot open, its work closes from the plan")

    def test_a_phase_that_would_need_a_reason_to_open_is_not_called_openable(self):
        run("phase", "plan", "1", "First", "--goal", "g1")
        run("phase", "plan", "2", "Second", "--goal", "g2")
        run("todo", "add", "2", "a step")
        code, out, err = run("todo", "done", "2.1", "run:echo ok → ok", "done")
        self.assertEqual(code, 0, "`el phase open 2` would ask --why for the planned phase 1 — no plain command to print")

    def test_the_close_example_names_the_phase_asked(self):
        code, out, err = run("phase", "close", "1")
        self.assertEqual(code, 2)
        self.assertIn('el phase close 1 "what it delivered"', err)


class TheFirstPassHeld(Base):
    """Codex on this batch, 2026-10-05: the printed way must run — pinned."""

    def test_a_plan_without_a_goal_is_opened_with_one(self):
        run("phase", "plan", "1", "Probe")
        run("todo", "add", "1", "first item")
        code, out, err = run("todo", "done", "1.1", "owner", "delivered")
        self.assertEqual(code, 4)
        self.assertIn("el phase open 1 --goal '<what it delivers>'", err, "a bare `el phase open 1` would ask for --goal")

    def test_quotes_in_rejected_words_reach_the_goal_whole(self):
        import re
        import shlex
        code, out, err = run("phase", "plan", "2", 'Fix "export" label')
        goal = re.search(r"--goal ('(?:[^']|'\\'')*')", err).group(1)
        self.assertEqual(shlex.split(goal), ['Fix "export" label'])

    def test_a_closed_phase_points_to_the_next_free_number(self):
        run("phase", "open", "1", "Probe", "--goal", "g1")
        run("log", "RESULT", "r")
        run("phase", "close", "1", "done", "--reflect", "-", "--align", "-")
        run("todo", "add", "later", "fix the export label")
        code, out, err = run("todo", "move", "L1", "1")
        self.assertEqual(code, 4)
        self.assertIn("phase 1 is closed — it takes no more work", err)
        self.assertIn("el phase plan 2 '<English, 1–3 words>'", err, "planning 1 again would be refused: its number is taken")


if __name__ == "__main__":
    unittest.main()
