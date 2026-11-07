"""The radio with a Codex long case, 2026-11-06 (messages 2–9) and three of its reports from the pool.

1. A phase whose every item is done and only the second hand is due — the bug fixed and committed, its acceptance comes
   with a transfer hours later — could not close (two hands) and could not let the next bug start: `phase open` asked for
   `--why`, and the record said «paused for 306, resumes when it ends». Nothing was left to resume; twelve phases stood
   «paused» with every item done. Such a phase now waits for the second hand: the next phase opens, the record says what
   is due, the acceptance names the close, and nothing resumes it into flight."""
import os
import re
import shlex
import unittest
from unittest import mock
from pathlib import Path

from elephant import commands, store
from tests.test_long_case_1105 import Base


class TwoHands(Base):
    def setUp(self):
        super().setUp()
        os.environ["EL_TWO_HANDS"] = "1"
        self.ok("case", "new", "till", "--goal", "the till counts")
        self.ok("case", "use", "till")
        self.ok("phase", "open", "1", "Build", "--goal", "the till builds [run: build]")
        self.ok("todo", "add", "1", "Wire the till", "--expect", "[run: build]")
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        self.ok("phase", "plan", "2", "Ledger", "--goal", "the ledger balances")

    def case(self) -> Path:
        return Path(".cases") / next(p.name for p in Path(".cases").iterdir() if p.name.endswith("-till"))


class APhaseWhoseWorkEndedWaitsForTheSecondHand(TwoHands):
    def test_the_next_phase_opens_and_the_record_says_what_is_due(self):
        out, _ = self.ok("phase", "open", "2")
        self.assertIn("waits for the second hand, not a pause", out)
        self.assertIn("el todo brief 1.1", out)
        todo = store.read(self.case(), "TODO.md")
        self.assertIn("- [~] 1 Build", todo)
        self.assertIn(f"hold: {commands.AWAITS_HAND}", todo)
        self.assertNotIn("resumes when", out)
        journal = store.read(self.case(), "JOURNAL.md")
        self.assertIn("фаза 1 Build ждёт второй руки: все пункты сделаны, не принято 1", journal)
        self.assertNotIn("на паузе ради фазы 2", journal)

    def test_an_open_item_still_holds_the_pipeline(self):
        self.ok("todo", "add", "1", "Print the receipt")
        from tests.test_commands import run
        code, out, err = run("phase", "open", "2")
        self.assertEqual(code, 4, out + err)
        self.assertIn("phase 1 Build is still open", out + err)

    def test_the_acceptance_names_the_close_and_the_close_works(self):
        self.ok("phase", "open", "2")
        os.environ["EL_SESSION"] = "acceptor1106"
        out, _ = self.ok("todo", "accept", "1.1", "--by", "owner", "принимаю")
        self.assertIn("phase 1 Build: every item accepted — it waited for this; close it: el phase close 1", out)
        os.environ["EL_SESSION"] = "doer1105"
        self.ok("phase", "close", "1", "the till builds", "--reflect", "the work ended before its hand came",
                "--align", "on to the ledger")
        self.assertIn("- [x] 1 Build", store.read(self.case(), "TODO.md"))

    def test_nothing_resumes_it_into_flight(self):
        self.ok("phase", "open", "2")
        self.ok("todo", "add", "2", "Balance the ledger", "--expect", "[run: balance]")
        self.ok("todo", "done", "2.1", "run:balance → ok", "the ledger balances")
        os.environ["EL_SESSION"] = "acceptor1106"
        self.ok("todo", "accept", "2.1", "--by", "owner", "принимаю")
        os.environ["EL_SESSION"] = "doer1105"
        self.ok("phase", "close", "2", "the ledger balances", "--reflect", "a ledger is a till's shadow",
                "--align", "back to the till's acceptance")
        line = next(ln for ln in store.read(self.case(), "TODO.md").split("\n") if ln.startswith("- [~] 1 "))
        self.assertIn(commands.AWAITS_HAND, line)                 # still waiting for its hand, not back in flight
        out, _ = self.ok()
        thread = next(ln for ln in out.split("\n") if ln.startswith("thread:"))
        self.assertIn("waits for the second hand: el todo brief 1.1", thread)
        self.assertNotIn("el phase resume 1", thread)


class TheWaitKeepsOnePhaseInFlight(TwoHands):
    # the second hand, 2026-11-06: phase 1 paused for 2, 2 waits for its hand while 3 runs — closing or cancelling 2
    # resumed 1: two phases in flight, and `el check` said nothing
    def chain(self):
        self.ok("phase", "plan", "3", "Receipt", "--goal", "the receipt prints")
        # rebuild the chain: 1 paused for 2, 2 done and waiting, 3 in flight
        self.ok("todo", "add", "1", "Print the receipt")              # 1 has open work: a real pause
        self.ok("phase", "open", "2", "--why", "the ledger goes first")
        self.ok("todo", "add", "2", "Balance", "--expect", "[run: balance]")
        self.ok("todo", "done", "2.1", "run:balance → ok", "the ledger balances")
        self.ok("phase", "open", "3")                                  # 2 waits for its hand, 3 runs

    def flying(self):
        todo = store.todo_of(self.case())
        return [p.n for p in todo.phases if not p.done and not p.held and (self.case() / "phases").glob(f"{p.n}-*.md")
                and any((self.case() / "phases").glob(f"{p.n}-*.md"))]

    def test_closing_the_waiting_phase_does_not_put_a_second_in_flight(self):
        self.chain()
        os.environ["EL_SESSION"] = "acceptor1106"
        out, _ = self.ok("todo", "accept", "2.1", "--by", "owner", "принимаю")
        os.environ["EL_SESSION"] = "doer1105"
        closing = re.search(r"close it: (el phase close 2 .*)$", out, re.M).group(1)
        self.ok(*shlex.split(closing)[1:])                              # the printed close runs as printed
        self.assertEqual(self.flying(), [3])
        self.assertIn("hold: phase 3 Receipt", store.read(self.case(), "TODO.md"))

    def test_cancelling_the_waiting_phase_does_not_either(self):
        self.chain()
        self.ok("phase", "cancel", "2", "the ledger is not needed after all")
        self.assertEqual(self.flying(), [3])

    def test_resuming_a_waiting_phase_says_what_it_waits_for(self):
        self.ok("phase", "open", "2")
        from tests.test_commands import run
        code, out, err = run("phase", "resume", "1")
        self.assertEqual(code, 4, out + err)
        self.assertIn("waits for its second hand, not for a detour", out + err)
        self.assertNotIn("resumes by itself", out + err)

    def test_work_that_comes_back_ends_the_wait(self):
        self.ok("phase", "open", "2")
        out, err = self.ok("todo", "reopen", "1.1", "the first run missed a bug")
        line = next(ln for ln in store.read(self.case(), "TODO.md").split("\n") if ln.startswith("- [~] 1 "))
        self.assertNotIn(commands.AWAITS_HAND, line)
        self.assertIn("hold: phase 2 Ledger — work came back", line)
        self.assertIn("work came back to it while it waited for its second hand", err)

    def test_an_item_added_to_a_waiting_phase_is_not_accepted_away(self):
        self.ok("phase", "open", "2")
        self.ok("todo", "add", "1", "Print the receipt")
        os.environ["EL_SESSION"] = "acceptor1106"
        out, _ = self.ok("todo", "accept", "1.1", "--by", "owner", "принимаю")
        self.assertNotIn("every item accepted", out)

    def test_a_phase_not_planned_gets_a_door_that_runs(self):
        self.ok("todo", "add", "1", "Print the receipt")               # 1 has open work: it blocks the next
        from tests.test_commands import run
        code, out, err = run("phase", "open", "7", "Receipt", "--goal", "the receipt prints")
        self.assertEqual(code, 4, out + err)
        door = re.search(r"pause it for this one: (el phase open 7 .*?) \(1 resumes", out + err).group(1)
        self.assertEqual(door, 'el phase open 7 "Receipt" --goal "the receipt prints" --why "what came up"')
        self.ok(*shlex.split(door)[1:])                                  # it runs as printed


class TheHoldStaysTrueAsItemsChange(TwoHands):
    # the second hand, 2026-11-06, round 2
    def flying(self):
        todo = store.todo_of(self.case())
        return [p.n for p in todo.phases if not p.done and not p.held
                and any((self.case() / "phases").glob(f"{p.n}-*.md"))]

    def line(self, n: int) -> str:
        return next(ln for ln in store.read(self.case(), "TODO.md").split("\n") if re.match(rf"^- \[.\] {n} ", ln))

    def two_waiting(self):
        self.ok("phase", "open", "2")                                       # 1 waits for its hand
        self.ok("todo", "add", "2", "Balance", "--expect", "[run: balance]")
        self.ok("todo", "done", "2.1", "run:balance → ok", "the ledger balances")
        self.ok("phase", "plan", "3", "Receipt", "--goal", "the receipt prints")
        self.ok("phase", "open", "3")                                       # 2 waits too; 3 runs

    def test_two_phases_whose_work_came_back_do_not_both_fly(self):
        self.two_waiting()
        self.ok("todo", "reopen", "1.1", "the first run missed a bug")
        self.ok("todo", "reopen", "2.1", "the balance was off by one")
        self.ok("phase", "cancel", "3", "the receipt is not needed")
        self.assertEqual(self.flying(), [1])                                 # one in flight, the other waits for it
        self.assertIn("hold: phase 1 Build", self.line(2))

    def test_finished_again_it_waits_for_its_hand_not_for_flight(self):
        self.ok("phase", "open", "2")
        self.ok("todo", "reopen", "1.1", "the first run missed a bug")
        self.ok("todo", "done", "1.1", "run:build → ok again", "the till builds, the bug fixed")
        self.assertIn(commands.AWAITS_HAND, self.line(1))
        self.ok("phase", "cancel", "2", "the ledger is not needed")
        self.assertEqual(self.flying(), [])
        self.assertIn(commands.AWAITS_HAND, self.line(1))

    def test_resume_refuses_with_nothing_in_flight_too(self):
        self.ok("phase", "open", "2")
        self.ok("phase", "cancel", "2", "the ledger is not needed")
        from tests.test_commands import run
        code, out, err = run("phase", "resume", "1")
        self.assertEqual(code, 4, out + err)
        self.assertIn("waits for its second hand, not for a detour", out + err)
        self.assertEqual(self.flying(), [])

    def test_its_last_item_gone_is_not_work_coming_back(self):
        self.ok("phase", "open", "2")
        _, err = self.ok("todo", "cancel", "1.1", "the result is no longer needed")
        self.assertIn("its last item went while it waited for its second hand", err)
        self.assertNotIn("work came back", err)
        self.assertEqual(self.flying(), [2])

    def test_the_printed_close_runs_with_a_problem_unanswered(self):
        self.ok("log", "--phase", "1", "PROBLEM", "the till drifted by a cent")
        self.ok("phase", "open", "2")
        os.environ["EL_SESSION"] = "acceptor1106"
        out, _ = self.ok("todo", "accept", "1.1", "--by", "owner", "принимаю")
        os.environ["EL_SESSION"] = "doer1105"
        closing = re.search(r"close it: (el phase close 1 .*)$", out, re.M).group(1)
        self.assertIn('--howto "none: why"', closing)
        self.ok(*shlex.split(closing)[1:])
        self.assertIn("- [x] 1 Build", store.read(self.case(), "TODO.md"))

    def test_the_order_line_close_runs_as_printed(self):
        # the second hand, 2026-11-06, round 3: Order's one-command close carried --howto "…" → exit 2
        self.ok("log", "--phase", "1", "PROBLEM", "the till drifted by a cent")
        os.environ["EL_SESSION"] = "acceptor1106"
        self.ok("todo", "accept", "1.1", "--by", "owner", "принимаю")
        os.environ["EL_SESSION"] = "doer1105"
        out, _ = self.ok("order")
        closing = re.search(r"or in one command: (el phase close 1 .*?) · or add what is missing", out).group(1)
        self.assertNotIn('"…" --howto "…"', closing)
        self.ok(*shlex.split(closing)[1:])
        self.assertIn("- [x] 1 Build", store.read(self.case(), "TODO.md"))


class TheHowtoRefusalRepeatsTheCall(Base):
    # the second hand, 2026-11-06, round 4: `phase close 1 "…" --reflect "…" --align "…"` refused for the recipe question
    # printed `el phase close 1 "…" --howto "none: why"` — run as printed, refused again: reflect and align were lost
    def test_the_phase_close_door_keeps_the_given_words(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        self.ok("log", "--phase", "1", "PROBLEM", "the till drifted by a cent")
        from tests.test_commands import run
        code, out, err = run("phase", "close", "1", "the till works", "--reflect", "a cent is a symptom",
                             "--align", "next: the ledger")
        self.assertEqual(code, 4, out + err)
        door = re.search(r"(el phase close 1 .*?--howto \"none: why\")", out + err).group(1)
        self.assertIn('--reflect "a cent is a symptom" --align "next: the ledger"', door)
        self.ok(*shlex.split(door)[1:])

    def test_the_case_close_door_keeps_the_given_words(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        self.ok("phase", "close", "1", "the till works", "--reflect", "a till first", "--align", "the case ends")
        self.ok("log", "PROBLEM", "the shop door sticks")
        from tests.test_commands import run
        code, out, err = run("done", "the shop works, the door fixed later")
        self.assertEqual(code, 4, out + err)
        door = re.search(r"(el done .*?--howto \"none: why\")", out + err)
        self.assertIsNotNone(door, out + err)
        self.assertIn('"the shop works, the door fixed later"', door.group(1))
        self.ok(*shlex.split(door.group(1))[1:])


class TheOwnerWordBeforeReadyIsSaidFirst(TwoHands):
    def test_not_ready_comes_before_the_recipe_question(self):
        # the second hand, round 5: `el done '…' --by owner` before ready printed the recipe door first, and running it
        # was refused «the agents' part comes first» — the door that would not open came before the one that would
        os.environ["EL_SESSION"] = "acceptor1106"
        self.ok("todo", "accept", "1.1", "--by", "owner", "принимаю")
        os.environ["EL_SESSION"] = "doer1105"
        self.ok("phase", "close", "1", "the till works", "--reflect", "a till first", "--align", "the case ends")
        self.ok("phase", "cancel", "2", "the ledger is another case")
        self.ok("log", "PROBLEM", "the shop door sticks")
        from tests.test_commands import run
        code, out, err = run("done", "--by", "owner", "закрывайте")
        self.assertEqual(code, 4, out + err)
        self.assertIn("the agents' part comes first", out + err)
        self.assertNotIn("--howto", out + err)


class TheHowtoDoorAnswersEveryFlagGate(Base):
    def test_a_bare_close_gets_the_reflect_and_align_it_lacks(self):
        # the second hand, round 5: `phase close 1 "the till works"` → the door added only --howto, then exit 4
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        self.ok("log", "--phase", "1", "PROBLEM", "the till drifted by a cent")
        from tests.test_commands import run
        code, out, err = run("phase", "close", "1", "the till works")
        self.assertEqual(code, 4, out + err)
        door = re.search(r"(el phase close 1 .*?--howto \"none: why\")", out + err).group(1)
        self.assertIn('--reflect "…" --align "…"', door)
        self.ok(*shlex.split(door)[1:])


class TheWallRecoveryCarriesANumber(Base):
    def test_a_wall_number_out_of_range_prints_one_that_runs(self):
        # the second hand, 2026-11-06, round 2: «el feedback --wall K --expected "…"» — K ran as K, exit 2
        from tests.test_commands import run
        os.environ["EL_FEEDBACK_DIR"] = str(Path(self.tmp.name) / "pool")
        try:
            run("phase", "close", "90", "x")
            code, out, err = run("feedback", "--wall", "999", "--expected", "a door")
            self.assertNotEqual(code, 0)
            door = re.search(r"(el feedback --wall \d+ --expected \"…\")", out + err).group(1)
            self.ok(*shlex.split(door)[1:])
        finally:
            os.environ.pop("EL_FEEDBACK_DIR", None)


class AnEndedPhaseIsNotAskedForAPromise(Base):
    def test_the_line_asks_while_work_is_open_and_not_after(self):
        # a live report, 2026-11-06: Order on a phase whose items were all done said «its goal promises no proof — add
        # [run: …] [file: …] [owner]»; the agent added [owner] and the close refused it: «promised [owner] and no done item
        # proves it». A promise written after the work is not a promise.
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        out, _ = self.ok("order")
        self.assertIn("its goal promises no proof", out)
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        out, _ = self.ok("order")
        self.assertNotIn("its goal promises no proof", out)
        self.assertIn("phase 1 Build: every item ended", out)


class OneHandStillCloses(Base):
    def test_without_two_hands_an_ended_phase_is_closed_not_waited_on(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        self.ok("phase", "plan", "2", "Ledger", "--goal", "the ledger balances")
        from tests.test_commands import run
        code, out, err = run("phase", "open", "2")
        self.assertEqual(code, 4, out + err)                    # nothing to accept: the honest step is the close
        self.assertIn("close it first", out + err)


if __name__ == "__main__":
    unittest.main()


class TheRecitationNamesThePhaseInFlight(Base):
    def test_a_phase_paused_long_ago_is_not_the_step_in_hand(self):
        # the radio, Codex #10, 2026-11-06: the recitation said «open in phase 279: 279.4 · finished one? el todo done 279.4»
        # while the work was in phase 307 — 279 had been paused for a detour weeks before
        self.ok("phase", "open", "1", "Old", "--goal", "an old thread")
        self.ok("todo", "add", "1", "The old step")
        self.ok("phase", "plan", "2", "Now", "--goal", "the bug of today")
        self.ok("phase", "open", "2", "--why", "a bug came first")
        self.ok("todo", "add", "2", "Fix the bug of today")
        lines = commands.recitation(Path(".").resolve(), Path(".cases") / next(
            p.name for p in Path(".cases").iterdir() if p.is_dir() and (p / "README.md").exists()), 10, 0)
        said = "\n".join(lines)
        self.assertIn("open in phase 2: 2.1", said)
        self.assertNotIn("1.1", said.split("\n", 1)[1])


class ALongRunCommandHasADoor(Base):
    def test_the_refusal_names_the_command_and_keeps_it_whole(self):
        # a Codex report, 2026-11-06: `done … 'run:node … jest.js --runTestsByPath <eight paths> --json --outputFile=<path>'`
        # — 1 189 chars — got «put the story into the phase file», a door for a story, not for a command
        self.ok("phase", "open", "1", "Build", "--goal", "the till builds")
        self.ok("todo", "add", "1", "Wire the till")
        cmd = "node node_modules/jest/bin/jest.js --runInBand --runTestsByPath " + " ".join(
            f"__tests__/components/ui/till/part{k}.test.tsx" for k in range(24)) + " --json --outputFile=artifacts/till-run.json"
        from tests.test_commands import run
        code, out, err = run("todo", "done", "1.1", f"run:{cmd} → 24 passed", "the till builds")
        self.assertEqual(code, 3, out + err)
        said = out + err
        self.assertIn(f"the run command alone is {len(cmd)} chars", said)
        script = re.search(r'run:"sh (\S+-run\.sh) → what came out"', said).group(1)
        self.assertNotIn("[x] 1.1", store.read(next(p for p in Path(".cases").iterdir() if p.is_dir()
                                                     and (p / "TODO.md").exists()), "TODO.md"))  # nothing was written
        Path(script).parent.mkdir(parents=True, exist_ok=True)
        Path(script).write_text(cmd + "\n", encoding="utf-8")       # the door as printed, from where el ran
        self.assertTrue(Path(script).is_file())
        self.ok("todo", "done", "1.1", f"run:sh {script} → 24 passed", "the till builds")

    def test_long_words_get_the_words_door_not_the_script_one(self):
        # the second hand, 2026-11-06: a 331-char command with long words — the script door was printed, and the retry
        # with a short run was refused again: the words were what overflowed
        self.ok("phase", "open", "1", "Build", "--goal", "the till builds")
        self.ok("todo", "add", "1", "Wire the till")
        cmd = "node run.js " + "x" * 320
        from tests.test_commands import run
        code, out, err = run("todo", "done", "1.1", f"run:{cmd} → ok", "long word " * 140)
        self.assertEqual(code, 3, out + err)
        self.assertNotIn("the run command alone", out + err)


class AWallReportCarriesTheNewestRefusals(Base):
    def test_a_long_session_reports_the_twenty_before_the_wall_and_counts_the_rest(self):
        # a Codex report, 2026-11-06: 224 refusals of one session went into the report — 62 KB, the reported one at the end
        from tests.test_commands import run
        os.environ["EL_FEEDBACK_DIR"] = str(Path(self.tmp.name) / "pool")
        try:
            for k in range(30):
                code, _, _ = run("phase", "close", str(90 + k), "x")
                self.assertNotEqual(code, 0)
            out, _ = self.ok("feedback", "--wall")                          # the listing: the newest and a count
            self.assertIn("… 10 earlier (1–10) — name one by its number: el feedback --wall 1 --expected", out)
            self.assertNotIn("\n  1 [exit", out)
            self.ok("feedback", "--wall", "--expected", "a door")
            report = next((Path(self.tmp.name) / "pool").glob("*.md")).read_text(encoding="utf-8")
            repro = report.split("## Reproduction", 1)[1].split("\n## ", 1)[0]
            self.assertIn("the reported one is 30 — 9 earlier left out", repro)
            self.assertEqual(len([ln for ln in repro.split("\n") if ln[:1].isdigit()]), 21)
            self.assertIn("30. el phase close 119 x  → exit", repro)
        finally:
            os.environ.pop("EL_FEEDBACK_DIR", None)


class AOneItemPhaseClosesByItsResult(TwoHands):
    # the owner's word, 2026-11-06 22:25 («Беру твою рекомендацию» — (в)): a phase of one item, done and accepted, with no
    # PROBLEM left without a recipe, closes by its result alone; reflect and align are written when there is a lesson
    def accept(self, ref):
        os.environ["EL_SESSION"] = "acceptor1106"
        self.ok("todo", "accept", ref, "--by", "owner", "принимаю")
        os.environ["EL_SESSION"] = "doer1105"

    def test_the_result_alone_closes_it_and_the_next_phase_opens(self):
        self.accept("1.1")
        out, _ = self.ok("phase", "close", "1", "the till builds")
        self.assertIn("closed by its result alone", out)
        self.assertIn("- [x] 1 Build", store.read(self.case(), "TODO.md"))
        self.assertIn(f"Build закрыта ({commands.SHORT_CLOSE}) →", store.read(self.case(), "JOURNAL.md"))
        self.ok("phase", "open", "2")                                   # the next gate reads the mark, asks no reflect

    def test_order_offers_the_short_close(self):
        self.accept("1.1")
        out, _ = self.ok("order")
        line = next(ln for ln in out.split("\n") if "phase 1 Build: every item ended" in ln)
        self.assertNotIn("reflect", line)

    def test_a_lesson_is_still_taken(self):
        self.accept("1.1")
        self.ok("phase", "close", "1", "the till builds", "--reflect", "wire before you count", "--align", "the ledger next")
        journal = store.read(self.case(), "JOURNAL.md")
        self.assertIn("reflect: wire before you count", journal)
        self.assertNotIn(commands.SHORT_CLOSE, journal)

    def test_not_accepted_two_items_or_an_open_problem_ask_the_full_close(self):
        from tests.test_commands import run
        code, out, err = run("phase", "close", "1", "the till builds")    # not accepted yet
        self.assertEqual(code, 4, out + err)
        self.accept("1.1")
        self.ok("log", "--phase", "1", "PROBLEM", "the till drifted by a cent")
        code, out, err = run("phase", "close", "1", "the till builds")    # a PROBLEM without a recipe: the lesson is due
        self.assertEqual(code, 4, out + err)
        self.assertIn("reflect", out + err)

    def test_a_problem_answered_in_the_same_close_closes_short(self):
        # the second hand, 2026-11-06: one accepted item + a PROBLEM + `--howto <recipe>` in the close → «reflect missing»,
        # while the same recipe logged beforehand closed short
        self.accept("1.1")
        self.ok("log", "--phase", "1", "PROBLEM", "the till drifted by a cent")
        Path(".howto").mkdir(exist_ok=True)
        Path(".howto/round-the-till.md").write_text("when: the till drifted by a cent\n\n# Round the till\n", encoding="utf-8")
        out, _ = self.ok("phase", "close", "1", "the till builds", "--howto", ".howto/round-the-till.md")
        self.assertIn("closed by its result alone", out)

    def test_two_items_ask_the_full_close(self):
        self.ok("todo", "add", "1", "Print the receipt")
        self.ok("todo", "done", "1.2", "run:print → ok", "the receipt prints")
        self.accept("1.1-1.2")
        from tests.test_commands import run
        code, out, err = run("phase", "close", "1", "the till builds")
        self.assertEqual(code, 4, out + err)
        self.assertIn("reflect", out + err)


class ACancelledItemMeansTheFullClose(Base):
    def test_one_item_left_after_a_cancel_is_not_a_one_item_phase(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        self.ok("todo", "add", "1", "Wire the scale")
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        self.ok("todo", "cancel", "1.2", "the shop sells no weighed goods")
        from tests.test_commands import run
        code, out, err = run("phase", "close", "1", "the till builds")
        self.assertEqual(code, 4, out + err)
        self.assertIn("reflect", out + err)


class OneHandOneItem(Base):
    def test_one_hand_a_done_item_is_enough(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        self.ok("todo", "done", "1.1", "run:build → ok", "the till builds")
        out, _ = self.ok("phase", "close", "1", "the till builds")
        self.assertIn("closed by its result alone", out)


class TheEntryWalksTheFoldersOnce(Base):
    def walks(self, folder: str, *argv):
        from elephant import order
        calls = []
        real = order._scan_folder
        with mock.patch.object(order, "_scan_folder",
                               side_effect=lambda d, rel: calls.append(rel) or real(d, rel)):
            out, _ = self.ok(*argv)
        return [c for c in calls if c == folder], out

    def test_one_walk_for_the_links_and_for_order(self):
        # Later L12, 2026-11-06: the entry walked a long case's folders twice — the README's Links, then Order
        from elephant import order
        case = next(p for p in Path(".cases").iterdir() if p.is_dir() and (p / "README.md").exists())
        (case / "docs").mkdir()
        (case / "docs" / "brief.md").write_text("# Brief\nsummary: what the owner asked\n", encoding="utf-8")
        walks, out = self.walks("docs")
        self.assertEqual(len(walks), 1, walks)
        self.assertIn("docs/brief.md", out)
        self.assertIsNone(order._SCAN)                              # the memo lives inside the entry only
        (case / "docs" / "late.md").write_text("# Late\nno summary\n", encoding="utf-8")
        full, _ = self.ok("order")                                   # a later command sees the new file
        self.assertIn("docs/late.md", full)

    def test_a_project_case_walks_once_too(self):
        # the second hand, 2026-11-06: in a project case the Links and Order read the folders by two lists — a memo per
        # call missed, two walks remained
        self.ok("case", "new", "--root", "app", "--goal", "the app")
        Path("docs").mkdir(exist_ok=True)
        Path("docs/a.md").write_text("# A\nsummary: the first note\n", encoding="utf-8")
        walks, out = self.walks("docs")                               # the hand is on the project case now
        self.assertIn("docs/a.md", out)
        self.assertLessEqual(len(walks), 1, walks)

    def test_a_document_linked_to_the_readme_is_read_after_the_readme_grows(self):
        # the second hand, 2026-11-06: docs/index.md → ../README.md; the refresh grew the README past 24 KB and the
        # cached size hid the line HEAD prints
        case = next(p for p in Path(".cases").iterdir() if p.is_dir() and (p / "README.md").exists())
        (case / "docs").mkdir()
        (case / "docs" / "index.md").symlink_to(Path("..") / "README.md")
        for k in range(400):
            (case / "docs" / f"note-{k:03d}.md").write_text(
                f"# Note {k}\nsummary: what visit {k} showed, kept with the raw answer beside it for the audit\n",
                encoding="utf-8")
        out, _ = self.ok()
        self.assertGreater((case / "README.md").stat().st_size, 24 * 1024)
        self.assertRegex(out, r"docs/index\.md is \d+ KB \(limit 24\)")

class AListMixesRangesAndNumbers(Base):
    def test_a_range_inside_a_list(self):
        # Later L10, the maintainer 2026-11-06: `49.1-49.4,49.6` refused — a range passed, a list passed, their mix did not
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        for t in "abcdef":
            self.ok("todo", "add", "1", f"Wire part {t}")
        out, _ = self.ok("todo", "done", "1.1-1.3,1.5", "run:build → ok", "the parts are wired")
        self.assertIn("1.1, 1.2, 1.3, 1.5", out)
        out, _ = self.ok("todo", "done", "1.4,", "1.6", "run:build → ok", "the rest wired")   # typed with a space
        self.assertIn("1.4, 1.6", out)

    def test_a_spaced_part_that_is_a_list_itself_is_gathered(self):
        # the second hand: `todo cancel 1.1, 1.2-1.3,1.4 "obsolete"` cancelled 1.1 only — the rest became the reason
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        for t in "abcde":
            self.ok("todo", "add", "1", f"Wire part {t}")
        out, _ = self.ok("todo", "cancel", "1.1,", "1.2-1.3,1.4", "obsolete")
        self.assertIn("cancelled: 1.1 «Wire part a», 1.2 «Wire part b», 1.3 «Wire part c», 1.4 «Wire part d»", out)
        from tests.test_commands import run
        code, out, err = run("todo", "note", ",,", "no writes")
        self.assertEqual(code, 2, out + err)                            # names nothing: a usage refusal, not a crash

    def test_typed_with_spaces_a_range_is_gathered_too(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        for t in "abcd":
            self.ok("todo", "add", "1", f"Wire part {t}")
        out, _ = self.ok("todo", "done", "1.1,", "1.2-1.3", "run:build → ok", "three wired")
        self.assertIn("1.1, 1.2, 1.3", out)
        self.assertNotIn("1.4", out.split("→")[0])


class TheSameEventTwiceIsARepeat(Base):
    def test_the_repeat_is_refused_and_says_the_first_went_in(self):
        # Later L9, the maintainer 2026-11-06: a repeat of `el log PROBLEM` wrote the same PROBLEM twice, silently
        self.ok("log", "PROBLEM", "the till drifted by a cent")
        from tests.test_commands import run
        code, out, err = run("log", "PROBLEM", "the till drifted by a cent")
        self.assertEqual(code, 4, out + err)
        self.assertIn("the newest journal entry holds this PROBLEM already", out + err)
        case = next(p for p in Path(".cases").iterdir() if p.is_dir() and (p / "JOURNAL.md").exists())
        self.assertEqual(store.read(case, "JOURNAL.md").count("the till drifted by a cent"), 1)
        self.ok("log", "PROBLEM", "the till drifted by a cent again after the fix")   # what differs goes in

    def test_both_ends_of_the_output_say_it_was_logged(self):
        # Later L9: `2>&1 | head -1` showed a warning, the event looked unwritten; the second hand: answer-first made
        # `tail -1` a warning — the write's own warning now says it went in, and the answer stays last
        import subprocess
        el = Path(__file__).resolve().parents[1] / "bin" / "el"
        long = "a decision about the till " * 12                        # over the warn length: a split warning
        r = subprocess.run(f"{el} log DECISION '{long}' 2>&1", shell=True, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stdout)
        lines = [ln for ln in r.stdout.split("\n") if ln.strip()]
        self.assertTrue(lines[0].startswith("warning: logged — "), lines[0])
        self.assertTrue(lines[-1].startswith("logged: DECISION"), lines[-1])

    def test_an_event_that_only_starts_like_the_last_is_not_a_repeat(self):
        # the second hand: «h / a» after «h / a / b» was refused as a repeat
        self.ok("log", "DECISION", "the till is wired\nwith the old cable\nand a new plug")
        self.ok("log", "DECISION", "the till is wired\nwith the old cable")


class ANextLineWhoseStepsAreOver(Base):
    def test_a_close_that_resumes_another_phase_names_the_stale_next(self):
        # the radio, Codex #29, 2026-11-06: `phase close 318` resumed 315; the thread showed 315, `next:` offered 318.1, done
        self.ok("phase", "open", "1", "Old", "--goal", "an old thread")
        self.ok("todo", "add", "1", "The old step")
        self.ok("phase", "plan", "2", "Bug", "--goal", "the bug of today")
        self.ok("phase", "open", "2", "--why", "a bug came first")
        self.ok("todo", "add", "2", "Fix the bug")
        self.ok("readme", "set", "next", "finish 2.1, then close 2")
        self.ok("todo", "done", "2.1", "run:fix → ok", "the bug is fixed")
        out, _ = self.ok("phase", "close", "2", "the bug is fixed")
        self.assertIn("next: names 2.1 — over", out)
        self.assertIn("(in flight: 1.1 «The old step»)", out)
        order_out, _ = self.ok("order")
        self.assertIn("next: names 2.1 — over", order_out)
        self.ok("readme", "set", "next", "back to 1.1")
        order_out, _ = self.ok("order")
        self.assertNotIn("next: names", order_out)

    def test_a_version_number_is_not_a_step(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        self.ok("todo", "done", "1.1", "run:build → ok", "wired")
        self.ok("readme", "set", "next", "ship 1.78.0 to the shop")
        out, _ = self.ok("order")
        self.assertNotIn("next: names", out)

    def test_a_full_stop_and_a_range_are_read_as_a_sentence_writes_them(self):
        # the second hand, round 2: «finish 1.1.» was missed; «finish 1.1-1.3» with 1.2 open was named «over»
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        for t in "abc":
            self.ok("todo", "add", "1", f"Wire part {t}")
        self.ok("todo", "done", "1.1", "run:build → ok", "wired a")
        self.ok("readme", "set", "next", "finish 1.1.")
        self.assertIn("next: names 1.1 — over", self.ok("order")[0])
        self.ok("todo", "done", "1.3", "run:build → ok", "wired c")
        self.ok("readme", "set", "next", "finish 1.1-1.3")
        self.assertNotIn("next: names", self.ok("order")[0])       # 1.2 is open inside the range
        self.ok("todo", "done", "1.2", "run:build → ok", "wired b")
        self.assertIn("next: names 1.1-1.3 — over", self.ok("order")[0])
