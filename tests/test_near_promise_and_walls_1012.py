"""Two live wall reports of one case (2026-10-11 and 2026-10-12, el 1.61.0).

1. `phase close` refused «promised [run: x] and no done item proves it» while a done, accepted item expected
   [run: x red on HEAD]; Order named that item, the close did not — its only door was a new item, a ritual over finished
   work. The close names the item in other words with the same door as Order, and where the goal is corrected; el does not
   count it by a shared prefix — «red on HEAD» may not be the promise «x passes».
2. `el feedback --wall --expected "…"` attached the last wall of a cascade while the words were about the wall that caused
   it; the success says which wall went in, and a refusal that only announces a list («cannot close phase 1:») is titled
   by its first reason.
3. `el log DECISION "…" --note "…"` — `--note` is `todo add`'s — answered «unrecognized arguments» with the note echoed;
   the refusal names where the option is read and where an event's details go: into its text.
4. The maintainer's own wall report, 2026-10-12: `el help cancel` — «no topic», and a grep through `el help todo` by hand;
   `el help mv` answered a command, an action of a command was a dead end.
"""
import os
import re
import shlex
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    KEYS = ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_CASE", "EL_FEEDBACK_DIR")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="doer1012", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          EL_FEEDBACK_DIR=str(Path(self.tmp.name) / "fb"))
        run("case", "new", "engine", "--goal", "x")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-engine"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def accept(self, ref):
        os.environ["EL_SESSION"] = "check1012"
        try:
            return run("todo", "accept", ref, "--by", "subagent", "--run", "suite → 1 red", "re-ran, red as said")
        finally:
            os.environ["EL_SESSION"] = "doer1012"


class CloseNamesTheItemInOtherWords(Base):
    def setUp(self):
        super().setUp()
        run("phase", "open", "1", "Guard", "--goal", "the guard holds [run: suite]")
        run("todo", "add", "1", "red test for the guard", "--expect", "[run: suite red on HEAD]")
        code, _, err = run("todo", "done", "1.1", "run:suite → 1 red on HEAD", "the test is red on HEAD")
        self.assertEqual(code, 0, err)
        code, _, err = self.accept("1.1")
        self.assertEqual(code, 0, err)

    def close(self):
        return run("phase", "close", "1", "guard holds", "--reflect", "learned one thing", "--align", "next: the other")

    def test_the_close_names_the_item_and_the_doors(self):
        code, _, err = self.close()
        self.assertEqual(code, 4)
        self.assertIn("1.1 expects [run: suite red on HEAD]: one promise in other words?", err)
        self.assertIn("el todo expect 1.1 '[run: suite]'", err)
        self.assertIn("or the goal in the item's words: the goal line in phases/1-guard.md", err)
        self.assertIn('a promise of its own: el todo add 1 "…" --expect "[run: suite]"', err)

    def test_the_printed_door_closes_the_phase(self):
        code, _, err = run("todo", "expect", "1.1", "[run: suite]")
        self.assertEqual(code, 0, err)
        code, _, err = self.close()
        self.assertEqual(code, 0, err)

    def test_a_shared_prefix_is_not_counted_as_the_promise(self):
        code, _, _ = self.close()
        self.assertEqual(code, 4)  # «red on HEAD» is not «the suite passes» by itself: the agent says which

    def test_order_names_where_the_goal_is_corrected(self):
        _, out, _ = run()
        self.assertIn("1.1 expects [run: suite red on HEAD]", out)
        self.assertIn("or the goal in the item's words: the goal line in phases/1-guard.md", out)


class CloseWithoutANearItemKeepsItsDoor(Base):
    def test_no_item_in_other_words(self):
        run("phase", "open", "1", "Guard", "--goal", "the guard holds [run: suite]")
        run("todo", "add", "1", "write the notes", "--expect", "[run: lint → clean]")
        run("todo", "done", "1.1", "run:lint → clean", "notes written")
        self.accept("1.1")
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 4)
        self.assertIn("no done item proves it — name the criterion as an item", err)
        self.assertNotIn("in other words", err)


class WallReportSaysWhichWall(Base):
    def reports(self):
        d = Path(self.tmp.name) / "fb"
        return sorted(d.glob("*.md")) if d.exists() else []

    def test_the_attached_wall_is_named_and_a_list_refusal_titled_by_its_reason(self):
        run("phase", "open", "1", "Guard", "--goal", "the guard holds [run: suite]")
        run("todo", "add", "1", "red test", "--expect", "[run: suite red on HEAD]")
        run("todo", "done", "1.1", "run:suite → red", "red")
        self.accept("1.1")
        run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")        # wall 1: the cause
        run("todo", "add", "9", "a step of the next phase")                      # wall 2: what followed
        code, out, err = run("feedback", "--wall", "--expected", "name the item in other words at the close")
        self.assertEqual(code, 0, err)
        self.assertIn("attached: wall 2 of 2 — «phase 9 does not exist yet", out)
        self.assertIn('el feedback --wall 1 --expected "…"', out)  # a number that runs, not a placeholder (Codex)
        code, out, err = run("feedback", "--wall", "1", "--expected", "name the item in other words at the close")
        self.assertEqual(code, 0, err)
        self.assertIn("attached: wall 1 of 2 — «cannot close phase 1: phase 1 promised [run: suite]", out)
        newest = max(self.reports(), key=lambda p: p.stat().st_mtime_ns)
        self.assertIn("cannot close phase 1: phase 1 promised", newest.read_text(encoding="utf-8").splitlines()[0])

    def test_one_wall_needs_no_naming(self):
        run("todo", "add", "9", "a step")
        code, out, err = run("feedback", "--wall", "--expected", "x")
        self.assertEqual(code, 0, err)
        self.assertNotIn("attached:", out)


class AnOptionOfAnotherCommand(Base):
    def journal(self):
        return (self.case / "JOURNAL.md").read_text(encoding="utf-8")

    def test_log_note_names_where_it_is_read_and_where_the_words_go(self):
        before = self.journal()
        code, out, err = run("log", "DECISION", "chose the queue over polling", "--note", "polling missed late writes")
        self.assertEqual(code, 2)
        self.assertIn("el log: does not take --note — nothing was written; --note is read by el todo add", err)
        self.assertIn("past 200 chars el wraps it into a headline and body lines", err)
        self.assertIn("a line break in the text starts a body line", err)
        self.assertNotIn("polling missed late writes", err)  # the words are not echoed back as «unrecognized»
        self.assertIn('el log DECISION "chose X over Y because Z"', err)  # the voice of the command called, its examples
        self.assertEqual(before, self.journal())

    def test_an_option_of_log_on_todo(self):
        run("phase", "open", "1", "Guard", "--goal", "x")
        code, _, err = run("todo", "add", "1", "a step", "--phase", "2")
        self.assertEqual(code, 2)
        self.assertIn("el todo: does not take --phase — nothing was written; --phase is read by el log", err)

    def test_an_option_no_command_knows_keeps_the_usage_voice(self):
        code, _, err = run("log", "DECISION", "x", "--colour", "red")
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments: --colour red", err)


class TheSecondHandsEdges(Base):
    """Codex's return of 33.1–33.3 and 33.5, 2026-10-12: each printed command runs as printed; a fork is named like one slot;
    an unknown option beside another command's is named, not echoed; a dose names the other homes of its word."""

    def printed(self, text, head):
        m = re.search(re.escape(head) + r"""('(?:[^']|'\\'')*'|"[^"]*")""", text)
        self.assertIsNotNone(m, text)
        return shlex.split(head + m.group(1))[1:]

    def test_the_add_door_quotes_a_slot_with_quotes(self):
        run("phase", "open", "1", "Guard", "--goal", 'the guard holds [run: suite "a b"]')
        run("todo", "add", "1", "notes", "--expect", "[run: lint → clean]")
        run("todo", "done", "1.1", "run:lint → clean", "notes")
        self.accept("1.1")
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 4)
        self.assertIn("""--expect '[run: suite "a b"]'""", err)
        args = self.printed(err, 'el todo add 1 "…" --expect ')
        code, _, err2 = run(*args)
        self.assertEqual(code, 0, err2)

    def test_a_fork_names_the_side_an_item_promises_in_other_words(self):
        run("phase", "open", "1", "Guard", "--goal", "the guard holds [run: suite] | [ref: claim]")
        run("todo", "add", "1", "red test", "--expect", "[run: suite red on HEAD]")
        run("todo", "done", "1.1", "run:suite → red", "red on HEAD")
        self.accept("1.1")
        _, out, _ = run()
        self.assertIn("promises the fork [run: suite] | [ref: claim] and no item promises either side in these words — "
                      "1.1 expects [run: suite red on HEAD]", out)
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 4)
        self.assertIn("neither side is proved in these words — 1.1 expects [run: suite red on HEAD]", err)
        code, _, err = run(*self.printed(err, "el todo expect 1.1 "))
        self.assertEqual(code, 0, err)
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 0, err)

    def test_an_unknown_option_beside_another_commands_is_named_not_echoed(self):
        code, _, err = run("log", "DECISION", "x", "--note", "SECRET", "--colour", "red")
        self.assertEqual(code, 2)
        self.assertIn("does not take --note · --colour", err)
        self.assertIn("--note is read by el todo add; --colour is no el command's option", err)
        self.assertNotIn("SECRET", err)

    def test_the_printed_problem_command_runs_with_quotes_in_the_title(self):
        run("phase", "open", "1", "Guard", "--goal", 'the guard holds [run: suite "a b"]')
        run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        code, out, err = run("feedback", 'the close says "a b"', "--wall", "--expected", "name it")
        self.assertEqual(code, 0, err)
        args = self.printed(out, "el log PROBLEM ")
        self.assertIn('"a b"', args[-1])
        code, _, err = run(*args)
        self.assertEqual(code, 0, err)

    def test_a_dose_names_the_other_homes_of_its_word(self):
        _, out, _ = run("help", "note")
        self.assertEqual(out.rstrip().splitlines()[-1], "`note` also names el phase note — el help phases")
        _, out, _ = run("help", "done")
        self.assertIn("`done` also names el done · el todo done — el help cases · el help todo", out)
        _, out, _ = run("help", "todo")
        self.assertNotIn("also names", out)


class TheSecondRoundEdges(Base):
    """Codex's second return, 2026-10-12: a printed command run as printed does what it says — the long expect door keeps a
    quoted slot whole; «minus the flag» names its value too; a word after `--` is not a flag; the PROBLEM line of a wall
    report names the case the wall was met in."""

    printed = TheSecondHandsEdges.printed

    def test_the_long_expect_door_keeps_a_quoted_slot(self):
        from elephant import grammar
        goal_slot = '[run: suite "a b" stays green on every device]'
        run("phase", "open", "1", "Guard", "--goal", f"the guard holds {goal_slot}")
        item_slot = "[run: suite red]"
        filler = "w" * (grammar.POCKET_CHARS - len(item_slot) - 1)
        code, _, err = run("todo", "add", "1", "red test", "--expect", f"{filler} {item_slot}")
        self.assertEqual(code, 0, err)
        run("todo", "done", "1.1", "run:suite → red", "red")
        self.accept("1.1")
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 4)
        args = self.printed(err, "el todo expect 1.1 ")
        self.assertIn(goal_slot, args[-1])
        code, _, err = run(*args)
        self.assertEqual(code, 0, err)
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 0, err)

    def test_no_minus_door_is_guessed(self):  # rounds 2–8: what is a flag's value is a guess — named, not removed
        run("phase", "open", "1", "Guard", "--goal", "x")
        code, _, err = run("todo", "add", "1", "a step", "--phase", "2")
        self.assertEqual(code, 2)
        self.assertIn("el todo: does not take --phase — nothing was written; --phase is read by el log", err)
        self.assertNotIn("the same call minus", err)
    def test_a_word_after_the_double_dash_is_not_a_flag(self):
        code, _, err = run("log", "DECISION", "x", "--", "--note")
        self.assertEqual(code, 2)
        self.assertNotIn("does not take", err)

    def test_the_problem_line_acts_on_the_hand_when_the_call_names_no_case(self):
        # the declared boundary (Codex rounds 4–5): the case the wall was met in is not guessed — from argv or a kept name it
        # was ambiguous for nested cases and suffixes; the line acts on the call's --case or on the case in hand
        run("case", "new", "other", "--goal", "y")
        engine = self.case.name
        run("--case", engine, "phase", "close", "7", "x")
        code, out, err = run("feedback", "--wall", "--expected", "name it")
        self.assertEqual(code, 0, err)
        self.assertIn("in your case: el log PROBLEM", out)

class TheThirdRoundEdges(Base):
    """Codex's third return, 2026-10-12: the loose expect door is printed only when it fits the pocket; a negative number is
    not an option; the call's --case reaches the PROBLEM line of a report; `--case` after `--` is the text, not the case."""

    printed = TheSecondHandsEdges.printed

    def test_a_goal_slot_near_the_pocket_limit_gets_a_door_that_passes(self):
        from elephant import grammar
        words = "suite " + "g" * (grammar.POCKET_CHARS - len("[run: suite ]") - 2)
        goal_slot = f"[run: {words}]"
        self.assertLessEqual(len(goal_slot), grammar.POCKET_CHARS)
        run("phase", "open", "1", "Guard", "--goal", f"the guard holds {goal_slot}")
        filler = "w" * (grammar.POCKET_CHARS - len("[run: suite red]") - 1)
        run("todo", "add", "1", "red test", "--expect", f"{filler} [run: suite red]")
        run("todo", "done", "1.1", "run:suite → red", "red")
        self.accept("1.1")
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 4)
        code, _, err2 = run(*self.printed(err, "el todo expect 1.1 "))
        self.assertEqual(code, 0, err2)
        code, _, err3 = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 0, err3)

    def test_a_negative_number_is_not_named_as_an_option(self):
        run("phase", "open", "1", "Guard", "--goal", "x")
        code, _, err = run("todo", "add", "1", "a step", "--phase", "-2")
        self.assertEqual(code, 2)
        self.assertIn("does not take --phase — nothing was written", err)
        self.assertNotIn("-2 is no", err)
    def test_the_calls_case_reaches_the_problem_line(self):
        engine = self.case.name
        run("case", "use", engine)
        run("phase", "close", "7", "x")                                       # the wall, met in engine by the hand
        run("case", "new", "other", "--goal", "y")
        other = next(Path(self.tmp.name, ".cases").glob("*-other")).name
        run("case", "use", other)
        for call in (("--case", engine, "feedback", "--wall", "--expected", "x"),
                     ("feedback", "--wall", "--expected", "x", "--case", engine)):
            code, out, err = run(*call)
            self.assertEqual(code, 0, err)
            self.assertIn(f"el --case {engine} log PROBLEM", out)

    def test_a_case_after_the_double_dash_is_not_the_walls_case(self):
        run("todo", "add", "9", "--", "--case", "elsewhere")                  # refused: no phase 9
        code, out, err = run("feedback", "--wall", "--expected", "x")
        self.assertEqual(code, 0, err)
        self.assertNotIn("--case elsewhere", out)


class TheFourthRoundEdges(Base):
    """Codex's returns of rounds 4–8, 2026-10-12: a promise longer than an item's expect gets no add door — at the close
    and in Order; a value is never named as an option; no «minus …» door is guessed, with `--` or without."""

    printed = TheSecondHandsEdges.printed

    def test_a_promise_longer_than_an_expect_gets_no_add_door(self):
        from elephant import grammar
        slot = "[run: " + "s" * (grammar.POCKET_CHARS - len("[run: ]") + 1) + "]"
        self.assertEqual(len(slot), grammar.POCKET_CHARS + 1)
        run("phase", "open", "1", "Guard", "--goal", f"the guard holds {slot}")
        code, _, err = run("phase", "close", "1", "x", "--reflect", "a", "--align", "b")
        self.assertEqual(code, 4)
        self.assertNotIn("el todo add 1", err)
        self.assertIn(f"longer than an item's expect holds ({grammar.POCKET_CHARS + 1} > {grammar.POCKET_CHARS})", err)

    def test_a_dot_number_or_a_dash_is_not_named_as_an_option(self):
        run("phase", "open", "1", "Guard", "--goal", "x")
        for value in ("-.2", "-"):
            code, _, err = run("todo", "add", "1", "step", "--reflect", value)
            self.assertEqual(code, 2)
            self.assertIn("does not take --reflect — nothing was written; --reflect is read by el phase close", err)
            self.assertNotIn("no el command's option", err)
    def test_a_repeated_flag_is_named_once_and_a_short_unknown_too(self):
        run("phase", "open", "1", "Guard", "--goal", "x")
        code, _, err = run("todo", "add", "1", "step", "--phase", "2", "--phase", "3")
        self.assertEqual(code, 2)
        self.assertIn("does not take --phase — nothing was written", err)
        code, _, err = run("todo", "add", "1", "mixed", "--phase", "2", "-z", "SECRET")
        self.assertEqual(code, 2)
        self.assertIn("does not take --phase · -z — nothing was written; --phase is read by el log; -z is no el command's option", err)
        self.assertNotIn("SECRET", err)
    def test_with_a_double_dash_no_minus_door_is_guessed(self):  # rounds 6–7: which extra stood where is not knowable
        run("phase", "open", "1", "Guard", "--goal", "x")
        for call in (["step", "--phase", "2", "--", "--phase", "3"], ["step", "--phase=2", "--", "--phase", "3"],
                     ["--note", "real", "step", "--phase", "2", "--", "--note", "literal"]):
            code, _, err = run("todo", "add", "1", *call)
            self.assertEqual(code, 2)
            self.assertNotIn("the same call minus", err)
            self.assertIn("unrecognized arguments", err)

    def test_order_prints_no_add_door_for_a_fork_side_longer_than_an_expect(self):  # round 5
        from elephant import grammar
        long_side = "[run: " + "s" * (grammar.POCKET_CHARS - len("[run: ]") + 1) + "]"
        run("phase", "open", "1", "Guard", "--goal", f"the guard holds {long_side} | [ref: claim]")
        _, out, _ = run()
        line = next(ln for ln in out.splitlines() if "promises the fork" in ln)
        self.assertNotIn("--expect '[run: sss", line)
        self.assertNotIn('--expect "[run: sss', line)
        self.assertIn("el todo add 1 \"…\" --expect \"[ref: claim]\"", line)

class AnActionIsANameTheHelpDoorKnows(Base):
    def test_an_action_answers_with_its_homes_examples_and_doses(self):
        code, out, err = run("help", "cancel")
        self.assertEqual(code, 0, err)
        self.assertIn("`cancel` is an action, not a knowledge dose — el todo cancel · el phase cancel · el case cancel", out)
        self.assertIn('el todo cancel 3.5 "no longer needed"', out)
        self.assertIn("el help todo · el help phases · el help cases", out)
        self.assertEqual(len(out.splitlines()), len(set(out.splitlines())))  # a line that shows two homes, once

    def test_a_name_that_is_neither_stays_an_error(self):
        code, _, err = run("help", "frobnicate")
        self.assertEqual(code, 2)
        self.assertIn("no topic `frobnicate`", err)


if __name__ == "__main__":
    unittest.main()
