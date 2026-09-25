"""Feedback 2026-09-25 (el 1.25.1) and the owner's word the same day: README Links and State were cut by el with «…» —
a phase goal with its proof slots became `… [file:…` in Links (a broken link), `last:` lost its end mid-sentence. «In README
nothing is to be cut: a limit means rephrase, not cut — the part cut off is lost to the one who reads; an agent may dig it
back up in half an hour, the owner cannot.» So every line el renders into a file the owner reads — README, TODO, the phase
files — is rendered whole; those lines are not counted in any limit. A limit on the source (a file's `summary:`) is an
Order line asking to rephrase the source. The screen keeps its one-line pointers short, and never cuts inside a link."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, order, stamp
from tests.test_commands import run

GOAL = ("the service answers in under a second on both regions, with the config diff recorded "
        "[file: src/config.yml] [file: src/app.properties]")
OUTCOME = ("price lookup cached: p95 dropped from 2400 ms to 820 ms on the NORTH route and to 910 ms on the SOUTH route, "
           "cold cache still 1400 ms — see [k6 report](evidence/k6.txt) for every run")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "api", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "evidence").mkdir()
        (self.case / "evidence" / "k6.txt").write_text("runs\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class NothingCutInTheFiles(Base):
    def test_a_long_goal_with_its_proof_slots_stays_whole_in_links_and_todo(self):
        code, _, err = run("phase", "open", "1", "Speed", "--goal", GOAL)
        self.assertEqual(code, 0, err)
        readme, todo = self.read("README.md"), self.read("TODO.md")
        self.assertIn(GOAL, readme, "the phases/ line in Links carries the whole goal")
        self.assertIn(GOAL, todo, "the phase line in TODO carries the whole goal")
        self.assertNotIn("[file:…", readme + todo)

    def test_last_carries_the_whole_result(self):
        run("phase", "open", "1", "Speed", "--goal", "fast")
        run("log", "RESULT", OUTCOME)
        state = [ln for ln in self.read("README.md").splitlines() if ln.startswith("- last: ")][0]
        self.assertEqual(state, f"- last: {OUTCOME}")

    def test_the_result_line_of_an_item_is_whole(self):
        run("phase", "open", "1", "Speed", "--goal", "fast")
        run("todo", "add", "1", "cache the price lookup")
        code, out, err = run("todo", "done", "1.1", "file:evidence/k6.txt", OUTCOME)
        self.assertEqual(code, 0, err)
        self.assertIn(f"    - result: {OUTCOME}\n", self.read("TODO.md"))
        self.assertNotIn("shortened", out + err)
        self.assertEqual(grammar.parse_todo(stamp.split(self.read("TODO.md"))[0]).errors, [])

    def test_closed_is_whole_and_warns_nothing(self):
        summary = OUTCOME + " — and the release went out on both regions the same day, the owner signed it off"
        code, out, err = run("done", summary)
        self.assertEqual(code, 0, err)
        self.assertIn(f"- closed: ", self.read("README.md"))
        self.assertIn(summary, self.read("README.md"))
        self.assertNotIn("shortened", out + err)
        self.assertNotIn("pointer line", err)

    def test_the_digest_keeps_a_long_decision_whole(self):
        run("phase", "open", "1", "Speed", "--goal", "fast")
        run("todo", "add", "1", "x")
        run("todo", "done", "1.1", "owner", "ok")
        run("log", "DECISION", OUTCOME)
        run("log", "RESULT", "r")
        run("phase", "close", "1", "done", "--reflect", "measure first", "--align", "next: errors")
        self.assertIn("price lookup cached", self.read("phases/1-speed.md"))
        self.assertIn("for every run", self.read("phases/1-speed.md"))


class APromiseIsNotALink(Base):
    def test_a_goal_that_promises_a_future_phase_file_leaves_no_dead_link(self):
        # found on the tool's own case right after the cut was removed: the whole goal now reached TODO, and the rule
        # that makes a bare `phases/N-name.md` clickable (0.18) turned the promise `[file: phases/5-…]` into a dead link
        code, _, err = run("phase", "open", "1", "Speed", "--goal", "fast, and the next phase gets its plan [file: phases/5-live-trial.md]")
        self.assertEqual(code, 0, err)
        todo = self.read("TODO.md")
        self.assertIn("[file: phases/5-live-trial.md] · [phases/1-speed.md](phases/1-speed.md)", todo)
        self.assertEqual(run("check")[0], 0, "a promise of a file not yet written is not a broken link")


class ALimitAsksToRephraseTheSource(Base):
    def test_a_long_summary_is_shown_whole_and_named_in_order(self):
        long_summary = ("what the two regions do differently: manifests, replicas, CPU, memory, routes and the database "
                        "each one talks to, with the timing of every smoke call")
        (self.case / "research").mkdir()
        (self.case / "research" / "regions.md").write_text(f"# Regions\nsummary: {long_summary}\n\nbody\n", encoding="utf-8")
        out = run()[1]
        self.assertIn(long_summary, self.read("README.md"))
        self.assertIn("research/regions.md", out)
        self.assertIn("rephrase", out)


class TheScreenNeverCutsALink(unittest.TestCase):
    def test_short_stops_before_a_bracket_it_would_cut(self):
        text = "compare the regions [file: src/config.yml] and more words after it"
        cut = order._short(text, 30)
        self.assertTrue(cut.endswith("…"))
        self.assertNotIn("[file", cut)
        self.assertEqual(cut, "compare the regions…")

    def test_short_keeps_a_whole_link(self):
        text = "see [k6 report](evidence/k6.txt) for the runs and the cold cache numbers of both routes"
        cut = order._short(text, 40)
        self.assertIn("[k6 report](evidence/k6.txt)", cut)



class ThePhilosophyTravelsWithEl(unittest.TestCase):
    """The owner's question of 2026-09-25: an agent on another machine — how does it know our philosophy, to write a report
    the way we weigh it? CLAUDE.md is local and gitignored; what travels is what el prints."""

    def test_the_dose_answers_under_the_words_an_agent_has(self):
        from elephant import knowledge
        for word in ("philosophy", "why", "principles", "holes"):
            dose = knowledge.resolve(word)
            self.assertIsNotNone(dose, word)
            for hole in ("proof from the bottom up", "the tool keeps the order", "the record does not lie", "knowledge in doses"):
                self.assertIn(hole, dose)

    def test_the_feedback_dose_asks_for_the_hole_in_those_words(self):
        from elephant import knowledge
        dose = knowledge.resolve("feedback")
        self.assertIn("el help philosophy", dose)
        self.assertIn("the record does not lie", dose)

if __name__ == "__main__":
    unittest.main()
