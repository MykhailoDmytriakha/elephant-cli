"""The polygon of 2026-10-07: the self-repair loop did not run.

Thirty-odd refusals in nineteen sessions of fresh agents (Haiku 5.5, Sonnet 5.5), and not one `el feedback`: the agents
told the owner what blocked them — in Problems, in their last message — and el, which printed every refusal, kept none.
A report cost a title, the verbatim output, the exit code and a word on the block, mid-task. The owner's word: «not one
report means the self-repair loop does not work». el keeps the session's refusals; at the moments it sees a wall itself —
the same refusal again, the end of a session with refusals — it asks for one line; `el feedback --wall --expected "…"`
writes the rest from el's own record."""
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
        os.environ["EL_SESSION"] = "loop1007"
        os.environ["EL_HANDS_DIR"] = str(Path(self.tmp.name) / "hands")
        os.environ["EL_FEEDBACK_DIR"] = str(Path(self.tmp.name) / "fb")
        run("case", "new", "loop test", "--goal", "g")
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION", "EL_FEEDBACK_DIR"):
            os.environ.pop(k, None)
        os.environ["EL_HANDS_DIR"] = self.hands_default
        self.tmp.cleanup()

    @classmethod
    def setUpClass(cls):
        cls.hands_default = os.environ.get("EL_HANDS_DIR", "")

    def reports(self):
        d = Path(self.tmp.name) / "fb"
        return sorted(d.glob("*.md")) if d.exists() else []


class TheSameWallTwiceAsks(Base):
    def test_the_first_refusal_is_quiet_the_second_asks_for_one_line(self):
        code, _, err = run("todo", "add", "3", "an item for a phase I meant to plan")
        self.assertEqual(code, 4)
        self.assertNotIn("the same wall", err)
        code, _, err = run("todo", "add", "3", "another item for it")
        self.assertEqual(code, 4)
        self.assertIn("the same wall 2 times this session", err)
        self.assertIn("did this refusal tell you how to get through?", err)
        self.assertIn("el feedback --wall --expected", err)

    def test_a_refused_report_is_not_kept_as_a_wall(self):
        run("feedback", "a title only")  # refused: the full form needs --actual, --expected, --onboarding
        code, out, err = run("feedback", "--wall")
        self.assertEqual(code, 4)
        self.assertIn("no refusal kept in this session", err)


class TheWallReportIsOneLine(Base):
    def setUp(self):
        super().setUp()
        run("todo", "add", "3", "an item for a phase I meant to plan")

    def test_bare_wall_lists_the_kept_refusals(self):
        code, out, err = run("feedback", "--wall")
        self.assertEqual(code, 0, err)
        self.assertIn("walls el kept this session (1):", out)
        self.assertIn("1 [exit 4] phase 3 does not exist yet", out)
        self.assertEqual(self.reports(), [], "a question writes nothing")

    def test_one_line_writes_a_whole_report_from_els_record(self):
        code, out, err = run("feedback", "--wall", "--expected", "the refusal names the plan command")
        self.assertEqual(code, 0, err)
        [path] = self.reports()
        text = path.read_text(encoding="utf-8")
        self.assertIn("# refused: phase 3 does not exist yet", text)
        self.assertIn("## Actual\nel todo add 3 'an item for a phase I meant to plan'", text, "argument boundaries kept")
        self.assertIn("el: ERROR [exit 4] phase 3 does not exist yet", text, "the refusal verbatim")
        self.assertIn("## Expected\nthe refusal names the plan command", text)
        self.assertIn("## Onboarding\nnot said — a quick wall report", text, "said as not said, never silent")
        self.assertIn("## Reproduction", text)

    def test_a_wall_number_out_of_range_lists_them(self):
        code, _, err = run("feedback", "--wall", "5", "--expected", "x")
        self.assertEqual(code, 2)
        self.assertIn("this session kept 1 wall(s)", err)

    def test_the_bare_report_still_teaches_the_form(self):
        code, _, err = run("feedback")
        self.assertEqual(code, 2)
        self.assertIn("feedback — telling Elephant it is wrong", err)
        self.assertIn("el feedback --wall --expected", err, "the dose names the one-line report first")


class TheEndOfASessionAsksOnce(Base):
    def test_set_next_names_the_walls_once(self):
        run("todo", "add", "3", "an item for a phase I meant to plan")
        run("log", "QUESTION", "keep the rule?")
        code, out, err = run("readme", "set", "next", "plan phase 3")
        self.assertEqual(code, 0, err)
        self.assertIn("this session el refused you 2 time(s)", out)
        self.assertIn("did any leave you guessing the next step, or make you try again?", out)
        code, out, _ = run("readme", "touch")
        self.assertNotIn("this session el refused you", out, "asked once per wall, not on every write")
        run("todo", "add", "4", "one more")
        code, out, _ = run("readme", "touch")
        self.assertIn("since el last asked el refused you 1 time(s)", out, "a new wall asks again, alone")

    def test_a_session_without_walls_is_not_asked(self):
        code, out, _ = run("readme", "set", "next", "go on")
        self.assertNotIn("el refused you", out)


class TheFirstReportItBrought(Base):
    """The first report a polygon agent wrote through `el feedback --wall` (pm-haiku-6, 2026-10-07): it re-checked 2.5 of
    a closed phase, wanted to add the proof, and read «no item 2.5 in TODO.md» about an item it could see in the phase
    file — twice. A closed item is history, and the refusal says so, with the door: new work where work runs now."""

    def test_an_item_of_a_closed_phase_is_named_as_history_with_the_door(self):
        run("todo", "add", "1", "count the sources", "--expect", "[run: probe → ok]")
        code, _, err = run("phase", "cancel", "1", "the layout came from elsewhere")
        self.assertEqual(code, 0, err)
        run("phase", "open", "2", "Recheck", "--goal", "the counts hold [run: probe → ok]")
        code, _, err = run("todo", "done", "1.1", "run:probe → ok", "re-checked")
        self.assertEqual(code, 4)
        self.assertNotIn("no item 1.1", err)
        self.assertIn("1.1 points into phase 1 Probe, cancelled — the items of a cancelled phase are history", err)
        self.assertIn('el todo add 2 "re-check 1.1: …" (phase 2 Recheck is the one in flight', err)


class TheSecondReportItBrought(Base):
    """pm-haiku-7, 2026-10-07, through `el feedback --wall`: `el todo done 1.2 run:"…"` without the outcome; the refusal
    echoed the proof with its spaces unquoted, and the agent read a quoting error. The missing argument is named, and
    the printed command can be pasted as it is."""

    def test_a_done_without_its_words_names_the_missing_argument_and_quotes_the_proof(self):
        run("todo", "add", "1", "count the folders", "--expect", "[run: probe → ok]")
        code, _, err = run("todo", "done", "1.1", "run:comm folders with the index → 52 outside")
        self.assertEqual(code, 2)
        self.assertIn("the proof is here, the words are not", err)
        self.assertIn("el todo done 1.1 'run:comm folders with the index → 52 outside' \"what came out\"", err)


class TheWallNobodyReported(Base):
    """pm-haiku-6, 2026-10-07: «invalid choice: '--case 2026-…'» nineteen times in one run, no report — the agent kept
    `el --case x` in a zsh variable, which stays one word; the maintainer's own session met it twice the same day. Found
    by the polygon report's grouping of refusals, not by a report: el names the shell trap."""

    def test_a_glued_case_option_is_named_as_the_shell_trap(self):
        code, _, err = run("--case loop-test", "phase", "note", "1", "x")
        self.assertEqual(code, 2)
        self.assertIn("reached el as one argument", err)
        self.assertIn("el --case loop-test …", err)
        self.assertNotIn("invalid choice", err)


class TheCodexReviewOfTheLoop(Base):
    """A Codex peer review of the loop before commit (2026-10-07): the log of walls must never mask a refusal, the report
    must stay verbatim and replayable, and the shell-trap check must not judge text."""

    def walls_file(self):
        hands = Path(os.environ["EL_HANDS_DIR"])
        return next(hands.glob("*-walls.jsonl"))

    def test_a_damaged_walls_file_never_masks_the_refusal(self):
        run("todo", "add", "3", "x")
        f = self.walls_file()
        f.write_text(f.read_text(encoding="utf-8") + "null\n[]\n42\n{\"cut off", encoding="utf-8")
        code, _, err = run("todo", "add", "3", "y")
        self.assertEqual(code, 4)
        self.assertIn("phase 3 does not exist yet", err)
        code, out, _ = run("feedback", "--wall")
        self.assertIn("walls el kept this session (2):", out, "the record after a cut-off line is not swallowed")

    def test_a_non_ascii_digit_wall_number_is_refused_not_crashed(self):
        run("todo", "add", "3", "x")
        code, _, err = run("feedback", "--wall", "²", "--expected", "x")
        self.assertEqual(code, 2)
        self.assertIn("this session kept 1 wall(s)", err)

    def test_case_as_item_text_is_not_a_shell_trap(self):
        run("todo", "add", "1", "count", "--expect", "[run: probe → ok]")
        code, out, err = run("todo", "add", "1", "--", "--case is the flag under review")
        self.assertNotIn("reached el as one argument", err)

    def test_a_refused_feedback_call_is_not_kept_as_a_wall(self):
        run("feedback", "--unknown-flag")
        code, _, err = run("feedback", "--wall")
        self.assertEqual(code, 4)
        self.assertIn("no refusal kept in this session", err)

    def test_the_report_lists_every_refusal_and_marks_the_reported_one(self):
        run("todo", "add", "3", "first")
        run("log", "QUESTION", "second")
        code, _, err = run("feedback", "--wall", "1", "--expected", "x")
        self.assertEqual(code, 0, err)
        [path] = self.reports()
        text = path.read_text(encoding="utf-8")
        self.assertIn("1. el todo add 3 first  → exit 4   ← reported", text)
        self.assertIn("2. el log QUESTION second  → exit 2", text)

    def test_two_missing_files_are_one_wall(self):
        from elephant import store
        a = store.wall_key("el: ERROR [exit 3] file:docs/a.pdf — no such file in the case")
        b = store.wall_key("el: ERROR [exit 3] file:docs/b.pdf — no such file in the case")
        self.assertEqual(a, b)
        c = store.wall_key("el: ERROR [exit 4] cannot close phase 1:\n  phase 1: open items 1.2")
        d = store.wall_key("el: ERROR [exit 4] cannot close phase 1:\n  phase 1: done items not accepted — 1.1")
        self.assertNotEqual(c, d, "two different blockers of a close are two walls")

    def test_an_item_number_glued_to_a_cyrillic_word_still_holds_its_number(self):
        run("log", "DECISION", "1.3проверен, запись остаётся")
        code, out, _ = run("todo", "add", "1", "the next step")
        self.assertIn("added: 1.4 ", out)


class NoSessionNoRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        for k in ("EL_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "EL_CASE"):
            os.environ.pop(k, None)
        run("case", "new", "no session", "--goal", "g")

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_without_a_session_the_wall_report_names_the_full_form(self):
        run("todo", "add", "3", "x")
        code, _, err = run("feedback", "--wall", "--expected", "x")
        self.assertEqual(code, 4)
        self.assertIn("sees no session here — the full form", err)


if __name__ == "__main__":
    unittest.main()
