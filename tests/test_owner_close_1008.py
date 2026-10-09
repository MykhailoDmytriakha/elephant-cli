"""The owner, 2026-10-08, after a live run: a fresh Sonnet accepted forty-five items of the owner's research map through
subagents and closed the whole case in eight minutes — every line true, the whole saying more than anyone had checked, and
no door asked the owner. Items are accepted by a second hand, a phase's scope by the owner; the case closed by one agent
command. «Truth is the owner's»: a top case that asks two hands ends like an item — the agents' `el done` makes it ready,
the owner's word closes it. A nested case is accepted by its parent, as before."""
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
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="owner1008", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def finished(self, name="probe"):
        run("case", "new", name, "--goal", "the probe answers")
        run("phase", "open", "1", "Probe", "--goal", "probe")
        run("todo", "add", "1", "step")
        run("todo", "done", "1.1", "run:x → ok", "ok")
        run("todo", "accept", "1.1", "--by", "owner", "ok")
        run("phase", "close", "1", "closed", "--reflect", "r", "--align", "a")
        return next(Path(self.tmp.name, ".cases").glob(f"*-{name}"))

    def readme(self, case):
        return (case / "README.md").read_text(encoding="utf-8")


class TheAgentsMakeItReady(Base):
    def test_done_makes_a_top_case_ready_not_closed(self):
        case = self.finished()
        code, out, err = run("done", "the probe answers in one call")
        self.assertEqual(code, 0, err)
        self.assertIn("ready: ", out)
        self.assertIn('el done --by owner "his words"', out.rstrip("\n").split("\n")[-1])
        text = self.readme(case)
        self.assertIn("- ready: ", text)
        self.assertNotIn("- closed: ", text)
        self.assertIn("дело готово, ждёт слова владельца → the probe answers in one call",
                      (case / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_the_entry_names_the_owners_word_and_state_is_current(self):
        self.finished()
        run("done", "the probe answers")
        os.environ["EL_SESSION"] = "owner1008-fresh"
        code, out, _ = run()
        self.assertEqual(code, 0)
        self.assertIn("awaits the owner's word: el done --by owner", out.split("\n")[2])
        self.assertIn("- ✓ everything in place", out)

    def test_case_list_shows_it_waiting(self):
        self.finished()
        run("done", "the probe answers")
        code, out, _ = run("case", "list")
        self.assertIn("awaits the owner's word", out)

    def test_done_again_names_the_door(self):
        self.finished()
        run("done", "the probe answers")
        code, _, err = run("done", "once more")
        self.assertEqual(code, 4)
        self.assertIn('his word said to you: el done --by owner "his words"', err)


class TheThreadSaysDoneIsHonest(Base):
    """pm-haiku-13, 2026-10-08: every phase closed, four sessions wrote «awaits the owner» into next: and never ran
    `el done` — the thread said «el done», read as a close behind the owner's back."""

    def test_the_thread_says_done_makes_it_ready(self):
        self.finished()
        thread = next(ln for ln in run()[1].split("\n") if ln.startswith("thread:"))
        self.assertIn('every phase ended: el done "what came out" makes it ready — the owner\'s word closes it', thread)


class OrderNamesTheMoment(Base):
    """pm-haiku-13 and two more runs, 2026-10-08: every phase closed, «awaits the owner» in next: as prose, Order ✓ —
    the case hung open, never said ready."""

    def test_every_phase_ended_names_done_and_more_work(self):
        self.finished()
        code, out, _ = run()
        line = next(ln for ln in out.split("\n") if "is not said ready" in ln)
        self.assertIn('el done "what came out"', line)
        self.assertIn('el phase plan 2 "Name"', line)

    def test_ready_or_a_phase_in_flight_is_silent(self):
        self.finished()
        run("done", "outcome")
        self.assertNotIn("is not said ready", run()[1])

    def test_a_case_without_the_rule_is_not_asked(self):
        os.environ["EL_TWO_HANDS"] = "0"
        self.finished()
        self.assertNotIn("is not said ready", run()[1])


class TheOwnersWordCloses(Base):
    def test_the_owners_words_are_quoted_and_the_agents_outcome_kept(self):
        case = self.finished()
        run("done", "the probe answers in one call")
        code, out, err = run("done", "--by", "owner", "принимаю")
        self.assertEqual(code, 0, err)
        text = self.readme(case)
        self.assertIn("- closed: ", text)
        self.assertIn("the probe answers in one call", text)
        self.assertIn("closed by the owner: «принимаю»", text)
        self.assertNotIn("- ready: ", text)
        self.assertIn("слово владельца: «принимаю»", (case / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_the_owners_word_before_the_agents_part_is_refused(self):
        self.finished()
        code, _, err = run("done", "--by", "owner", "закрывай")
        self.assertEqual(code, 4)
        self.assertIn('the agents\' part comes first — el done "what came out"', err)

    def test_no_one_else_closes_it(self):
        self.finished()
        run("done", "the probe answers")
        code, _, err = run("done", "--by", "subagent", "checked")
        self.assertEqual(code, 2)
        self.assertIn("closed by the owner's word alone", err)


class ResumedWorkTakesTheReadyLineAway(Base):
    def test_a_new_phase_drops_ready(self):
        case = self.finished()
        run("done", "the probe answers")
        run("phase", "open", "2", "More", "--goal", "more")
        self.assertNotIn("- ready: ", self.readme(case))


class OtherCasesCloseAsBefore(Base):
    def test_a_nested_case_closes_by_its_own_done(self):
        run("case", "new", "parent", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "w")
        code, out, err = run("--case", "parent", "spawn", "child", "--goal", "a branch")
        self.assertEqual(code, 0, err)
        child = next(Path(self.tmp.name, ".cases").glob("*-parent/*-child"))
        self.assertIn("rule: two hands", self.readme(child))
        code, out, err = run("--case", "child", "done", "the branch ended")
        self.assertEqual(code, 0, err)
        self.assertIn("- closed: ", self.readme(child))

    def test_a_case_without_the_rule_closes_at_once(self):
        os.environ["EL_TWO_HANDS"] = "0"
        case = self.finished()
        code, out, err = run("done", "the probe answers")
        self.assertEqual(code, 0, err)
        self.assertIn("- closed: ", self.readme(case))
        code, _, err = run("done", "--by", "owner", "ok")
        self.assertEqual(code, 4)  # closed already


if __name__ == "__main__":
    unittest.main()
