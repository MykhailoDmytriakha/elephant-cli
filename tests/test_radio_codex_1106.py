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
