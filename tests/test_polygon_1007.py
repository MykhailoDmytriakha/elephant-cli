"""The polygon of 2026-10-07 — fresh agents (Haiku 5.5, Sonnet 5.5) moved a real project's research into .cases/, session
after session with no memory between them; the walls both models hit, as forms of failure.

1. The second hand did not know itself. Sixteen items done by one session waited four more: each fresh session read
   «a fresh session accepts», took the doer for itself («I did these items, I cannot accept them») and asked the owner to
   drop the rule. Sonnet accepted through subagents and el called it «same session» beside the agent's «fresh subagents».
   The owner's word, 2026-10-07: «a subagent from the same session with a clean context, that knows nothing — that is a
   clean hand». el knows the doer's session and its own: the entry and the close say which hand the reader is; `--by
   subagent` in the doer's session is its own kind; the block no longer says «the next agent is you».
2. Refusals without a door: `todo add 2` before phase 2 was planned read «phase 2 is missing or closed» — two states,
   no way out; both models retried it three times. `el log QUESTION` (the owner had said «put your questions in the
   case») was refused with the type list alone, and the question landed in Decisions. The first `el` in a project with
   its own README.md advised `case new --root`, which that README refuses."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge
from tests.test_commands import run

PROOF = "[run: make test → OK]"


class Base(unittest.TestCase):
    two_hands = "1"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_TWO_HANDS"] = self.two_hands
        os.environ["EL_SESSION"] = "doer1007"
        run("case", "new", "research move", "--goal", "g")
        run("phase", "open", "1", "Inventory", "--goal", f"the sources are counted {PROOF}")
        run("todo", "add", "1", "count the sources", "--expect", PROOF)
        run("todo", "add", "1", "choose the layout", "--expect", PROOF)

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def case(self) -> Path:
        return next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def entry_line(self, prefix: str) -> str:
        code, out, err = run()
        self.assertEqual(code, 0, err)
        return next((ln for ln in out.split("\n") if ln.startswith(prefix)), "")


class TheSecondHandKnowsItself(Base):
    def setUp(self):
        super().setUp()
        code, _, err = run("todo", "done", "1.1-1.2", "run:make test → OK", "counted and chosen")
        self.assertEqual(code, 0, err)

    def test_a_fresh_session_is_told_it_is_the_second_hand(self):
        os.environ["EL_SESSION"] = "fresh1007"
        line = self.entry_line("acceptance: ")
        self.assertIn("done in session doer1007, you are another — you are the second hand", line)
        self.assertIn('el todo accept 1.1-1.2 --by <you> --run "<command> → what came out now>"', line)

    def test_the_doer_is_sent_to_a_clean_context_subagent(self):
        line = self.entry_line("acceptance: ")
        self.assertIn("done in this session, so not yours to accept", line)
        self.assertIn("a subagent with a clean context — hand it el todo brief 1.1 as its prompt", line)
        self.assertIn("--by subagent", line)

    def test_the_brief_tells_a_fresh_session_the_task_is_its_own(self):
        # a second Haiku run, 2026-10-07: the fresh session read the brief, not the entry, and left the items to «a
        # separate session» — the brief's header is where the second hand learns it is one
        os.environ["EL_SESSION"] = "fresh1007"
        code, out, err = run("todo", "brief", "1.1")
        self.assertEqual(code, 0, err)
        self.assertIn("done in session doer1007, you are another — this brief is YOUR task", out.split("\n")[0])
        os.environ["EL_SESSION"] = "doer1007"
        code, out, err = run("todo", "brief", "1.1")
        self.assertIn("done in this session — not yours to judge", out.split("\n")[0])

    def test_the_close_refusal_names_the_hand_too(self):
        os.environ["EL_SESSION"] = "fresh1007"
        code, _, err = run("phase", "close", "1", "counted", "--reflect", "r", "--align", "a", "--howto", "none: nothing new")
        self.assertEqual(code, 4)
        self.assertIn("done items not accepted — 1.1, 1.2", err)
        self.assertIn("you are the second hand", err)

    def test_a_subagent_of_the_doers_session_is_its_own_kind(self):
        code, out, err = run("todo", "accept", "1.1", "--by", "subagent", "--run", "make test → OK", "re-ran it from the brief")
        self.assertEqual(code, 0, err)
        todo = (self.case() / "TODO.md").read_text(encoding="utf-8")
        accepted = next(ln for ln in todo.split("\n") if ln.strip().startswith("- accepted: subagent"))
        self.assertIn("clean-context subagent", accepted)
        self.assertNotIn("same session", accepted)
        self.assertNotIn("same session as the doer", err, "a subagent is not warned as the doer checking itself")
        self.assertIn("clean-context subagent 1", self.entry_line("acceptance: "))

    def test_the_doer_checking_itself_is_still_named(self):
        code, _, err = run("todo", "accept", "1.2", "--by", "claude", "--run", "make test → OK", "looked again")
        self.assertEqual(code, 0, err)
        self.assertIn("same session as the doer, and not said to be a subagent", err)
        self.assertIn("--by subagent", err)

    def test_the_block_no_longer_makes_the_next_agent_the_doer(self):
        self.assertNotIn("следующий агент — тоже ты", knowledge.ONBOARDING_BLOCK)
        self.assertIn("субагент с чистым контекстом", knowledge.ONBOARDING_BLOCK)
        self.assertIn("`[/]` прошлой сессии принимаешь ты", knowledge.ONBOARDING_BLOCK)


class EveryRefusalHasADoor(Base):
    two_hands = "0"

    def test_a_phase_not_planned_yet_is_named_with_the_plan_command(self):
        code, _, err = run("todo", "add", "2", "index the experiments")
        self.assertEqual(code, 4)
        self.assertIn("phase 2 does not exist yet — plan it first", err)
        self.assertIn('el phase plan 2 "Name" --goal "…", then this add', err)
        self.assertNotIn("missing or closed", err)

    def test_a_phase_far_ahead_names_the_next_free_number(self):
        code, _, err = run("todo", "add", "5", "write the map")
        self.assertEqual(code, 4)
        self.assertIn("the next free number is 2", err)

    def test_a_closed_phase_sends_the_work_elsewhere(self):
        code, _, err = run("phase", "cancel", "1", "the layout came from elsewhere")
        self.assertEqual(code, 0, err)
        run("phase", "open", "2", "Experiments", "--goal", f"the index is whole {PROOF}")
        code, _, err = run("todo", "add", "1", "one more source")
        self.assertEqual(code, 4)
        self.assertIn("phase 1 Inventory is closed — its items are history", err)
        self.assertIn('el todo add 2 "…" (phase 2 Experiments is the one in flight)', err)

    def test_a_question_to_the_owner_is_told_where_it_lives(self):
        code, _, err = run("log", "QUESTION", "keep the two-hands rule?")
        self.assertEqual(code, 2)
        self.assertIn("a question to the owner is not an event until it is answered", err)
        self.assertIn("el todo hold N.M", err)
        self.assertIn("el readme add problems", err)

    def test_a_note_type_names_the_note_doors(self):
        code, _, err = run("log", "NOTE", "x")
        self.assertEqual(code, 2)
        self.assertIn("el todo note N.M", err)


class TheRootAdviceOnlyWhereItCanWork(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_a_project_with_its_readme_is_not_advised_root_mode(self):
        Path("README.md").write_text("# a project\n", encoding="utf-8")
        code, out, err = run()
        self.assertEqual(code, 4)
        self.assertIn('el case new "name" --goal', out + err)
        self.assertNotIn("--root", out + err)

    def test_an_empty_folder_still_hears_of_root_mode(self):
        code, out, err = run()
        self.assertEqual(code, 4)
        self.assertIn("--root", out + err)


if __name__ == "__main__":
    unittest.main()
