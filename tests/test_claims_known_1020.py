"""The pool of 2026-10-15…20: el said more than it knew, and hid what it knew.

1. `done 2.11 ref:<commit> ref:<canvas>` under `expect: … [ref: the design on the canvas]` printed «[ref: the design on the
   canvas] ← ref <commit>» — the first ref of two, paired by order. A pair el knows is one promise and one proof of a kind;
   more of either side and the promises stand beside the proofs, the reader pairs them.
2. Three reports: a subagent with EL_MODEL='model not exposed by harness' or 'inherited-default' was recorded «another
   model»; one with EL_MODEL=gpt-6-luna beside an unsigned doer read «model not given: … gpt-6-luna». Words that say the
   model is not known are no model, and the label says whose model is missing.
3. Two reports, 24 refusals in two sessions: `accept --run 'own focused run 25 suites/399 tests; compile 0'` — what came
   out, without the command — met a refusal that glued «→ <outcome now>» to it. el knows the doer's command: the refusal
   prints it before the acceptor's words, and the command reading beside it.
4. Four dones in a planned phase beside one in flight passed in silence; the close then refused twice — the phase was
   only planned, and its promise [owner] no item carried. The first done says it, with what the close will ask.
5. The owner's word, 2026-10-20: the second hand needs the context of a run, not only its line — a fresh checker timed
   out until told the doer's proxy and TLS settings. A done with a run asks for a `to re-run:` note; the brief carries it
   and says a run that does not repeat from what is written is a finding.
6. GitHub Copilot CLI runs each command in a fresh shell with COPILOT_CLI=1 and COPILOT_AGENT_SESSION_ID (a live report
   2026-10-20; the CLI's runtime builds that env): el knew neither, signed `harness ? · session ?`, and its advice —
   `export EL_SESSION=…` — is gone by the next command there. Now the CLI is named with its session; where a harness
   names none, the advice is one name before every el command.
7. Five reports, fifteen refusals in one session: the brief promised «about 950 chars for the words and every --run
   together», and beside four re-runs 236 fit. The brief counts each item's budget beside its own re-runs.
8. Two reports: an event of four lines refused as «6 body lines, 5 fit» — the writer guessed twice which line grew. The
   refusal names each line that takes more than one body line, and the width el wraps at.
9. A phase goal of 129 chars, 49 of them `[file: artifacts/…-verification.json]` — a promise of a file not there yet, so
   the bare-path door (which goes by the file) was silent; sixteen such refusals in one session.
10. Habits of three live agents, about thirty refusals: `el todo list` / `status` (the bare `el todo`), `el help todo done`,
    `el todo brief15.1`, a case name a letter off the one el transliterated, `el log FINDING` / `PROGRESS` / `REFLECT` /
    `PLAN` — each unambiguous, each refused with a list.
11. `el log RESULT 'headline' 'body'` — eight times in one session, refused «words after an option» with no option
    given. The owner's «yes», 2026-10-20: quoted phrases are the event's lines; a lone unquoted word stays refused.
12. The maintainer's own wall, 2026-10-20: `phase plan 40 'Old Python and links' --goal '…'` was refused with a ready
    command that put the name into --goal — taken as printed, the goal was gone. The goal given stays.
13. A live report on 1.70.0 itself: done warned «summary over 150 — rephrase line 2 now, then the same done records that
    version»; the re-record asked for words, the agent wrote «summary shortened», and that note became the item's result and
    its RESULT. Both doors now print the command with the result's own words; the dose says a new version writes a RESULT."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

ENVS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_THREAD_ID", "COPILOT_AGENT",
        "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "EL_MODEL", "EL_SESSION", "EL_HANDS_DIR", "EL_HINTS", "EL_TWO_HANDS",
        "EL_CASE", "EL_RECITE")
DOER, OTHER = "doer1020", "othr1020"


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS="0", EL_RECITE="0", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          CLAUDECODE="1", EL_SESSION=DOER)
        self.ok("case", "new", "shop", "--goal", "the shop works")
        self.ok("phase", "open", "1", "Ship", "--goal", "the shop ships [run: jest]")
        self.ok("todo", "add", "1", "ship the design", "--expect", "tests [run: jest] · design [ref: the design on the canvas]")

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
        self.assertEqual(code, 0, f"{argv}: {out}{err}")
        return out, err

    def case(self) -> Path:
        return next(Path(self.tmp.name, ".cases").glob("*-shop"))

    def line(self, ref: str, pocket: str) -> str:
        text = (self.case() / "TODO.md").read_text(encoding="utf-8")
        block = text.split(f" {ref} ", 1)[1]
        return next(ln for ln in block.split("\n") if ln.strip().startswith(f"- {pocket}:"))


class ExpectPairs(Base):
    def test_a_kind_with_two_proofs_is_not_paired_by_order(self):
        out, _ = self.ok("todo", "done", "1.1", "run:jest → green", "ref:08d5b522", "ref:https://canvas.example/abc", "shipped")
        self.assertIn("[run: jest] ← run jest → green  — does it show that?", out, "one promise, one proof: a pair el knows")
        self.assertNotIn("[ref: the design on the canvas] ← ref 08d5b522  — does it show that?", out)
        self.assertIn("[ref: the design on the canvas] ← ref 08d5b522 · ref https://canvas.example/abc  — which proof shows "
                      "which?", out)
        self.assertIn("expect 1.1: 2 of 2 filled", out)


class ModelWords(Base):
    def accept_as_subagent(self, model: str):
        os.environ["EL_MODEL"] = model
        try:
            return run("todo", "accept", "1.1", "--by", "subagent", "--run", "jest → green", "opened the canvas too")
        finally:
            os.environ.pop("EL_MODEL", None)

    def done(self):
        self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")

    def test_a_placeholder_is_no_model(self):
        self.ok("sign", "Opus 5.5")
        self.done()
        for said in ("model not exposed by harness", "inherited-default"):
            with self.subTest(said=said):
                code, out, err = self.accept_as_subagent(said)
                self.assertEqual(code, 0, err)
                self.assertNotIn("another model", out + self.line("1.1", "accepted"))
                self.assertIn("acceptor's model not given: Anthropic Claude Code · model ? · session", self.line("1.1", "accepted"))
                self.assertIn(f"EL_MODEL «{said}» does not read as a model's name", out)
                self.ok("todo", "reopen", "1.1", "--by", "subagent", "--run", "jest → green", "next round")
                self.done()

    def test_whose_model_is_missing_is_said(self):
        self.done()  # the doer never signed its model
        code, out, err = self.accept_as_subagent("gpt-6-luna")
        self.assertEqual(code, 0, err)
        self.assertIn("doer's model not given: Anthropic Claude Code · gpt-6-luna · session", self.line("1.1", "accepted"))
        self.assertIn("(clean-context subagent · doer's model not given)", out)

    def test_two_named_models_still_differ(self):
        self.ok("sign", "Opus 5.5")
        self.done()
        code, out, err = self.accept_as_subagent("Sonnet 5.5")
        self.assertEqual(code, 0, err)
        self.assertIn("another model: Anthropic Claude Code · Sonnet 5.5", self.line("1.1", "accepted"))

    def test_a_placeholder_is_not_signed(self):
        code, _, err = run("sign", "unknown")
        self.assertEqual(code, 2)
        self.assertIn("does not read as a model's name (with its version, up to 6 words, none saying it is not known: el sign "
                      "'Opus 5.5') — nothing signed: done: and accepted: lines say `model ?`", err)
        self.ok("sign", "Opus 5.5")
        code, _, err = run("sign", "unknown")  # what the session said before stays, and the refusal says so (Codex, round 2)
        self.assertIn("nothing signed: this session's signature stays «Opus 5.5»", err)


class RunWithoutCommand(Base):
    def test_the_doers_command_goes_before_what_came_out(self):
        self.ok("todo", "done", "1.1", "run:npm test -- --runInBand → 25 suites OK", "ref:https://canvas.example/abc", "shipped")
        os.environ["EL_SESSION"] = OTHER
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "own focused run 25 suites/399 tests; compile 0", "ok")
        self.assertEqual(code, 2)
        printed = '--run "npm test -- --runInBand → own focused run 25 suites/399 tests; compile 0"'
        self.assertIn(printed, err)
        self.assertIn('the command? what came out goes after it: --run "own focused run 25 suites/399 tests; compile 0 → <what '
                      'came out now>"', err)
        self.ok("todo", "accept", "1.1", "--by", "codex", "--run", printed[7:-1], "ok")  # the printed form works as printed

    def test_several_commands_each_get_their_run(self):
        self.ok("todo", "done", "1.1", "run:npm test → OK", "run:npx tsc --noEmit → exit 0", "ref:https://canvas.example/abc",
                "shipped")
        os.environ["EL_SESSION"] = OTHER
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "all green", "ok")
        self.assertEqual(code, 2)
        self.assertIn('2 commands, one --run each with what came out now: --run "npm test → <what came out now>" --run "npx '
                      'tsc --noEmit → <what came out now>"', err)


class PlannedPhaseDone(Base):
    def test_done_beside_a_running_phase_says_it_closes_from_the_plan(self):
        self.ok("phase", "plan", "2", "Fix", "--goal", "fixed and shipped [run: test:fast] [owner]")
        self.ok("todo", "add", "2", "fix the outage line", "--expect", "[run: jest → green]")
        out, _ = self.ok("todo", "done", "2.1", "run:jest → green", "one line now")
        self.assertIn("note: phase 2 Fix is planned, not open — phase 1 Ship is in flight: this work closes from the plan, "
                      "el phase close 2 \"what came out\" once every item ended; its close asks for [run: test:fast] · [owner], "
                      "none proved yet; no item carries [run: test:fast]: el todo add 2 \"…\" --expect \"[run: test:fast]\"", out)
        self.ok("todo", "add", "2", "fix the hang", "--expect", "[run: jest → green]")
        out, _ = self.ok("todo", "done", "2.2", "run:jest → green", "no hang")
        self.assertNotIn("is planned, not open", out, "said at the first done of the phase, not at each (Codex, 2026-10-20)")

    def test_a_decided_fork_and_a_carried_bare_kind_are_not_asked_again(self):  # Codex, 2026-10-20
        self.ok("phase", "plan", "2", "Fix", "--goal", "shipped [run: left] | [ref: right] · signed [owner]")
        self.ok("todo", "add", "2", "the left way", "--expect", "[run: left]")
        self.ok("todo", "add", "2", "the owner signs", "--expect", "[owner]")
        out, _ = self.ok("todo", "done", "2.1", "run:left → ok", "left done")
        self.assertIn("its close asks for [owner], none proved yet", out)
        self.assertNotIn("no item carries", out, "the fork is decided, the bare kind has its carrier")

    def test_done_in_the_open_phase_says_nothing_of_the_kind(self):
        out, _ = self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")
        self.assertNotIn("is planned, not open", out)


class RerunContext(Base):
    def test_a_run_proof_asks_for_what_the_command_does_not_say(self):
        out, _ = self.ok("todo", "done", "1.1", "run:curl -s https://api.example/x → 200", "ref:https://canvas.example/abc", "ok")
        self.assertIn("a fresh hand re-runs it from the brief alone", out)
        self.assertIn("el todo note 1.1 'to re-run: …'", out)
        self.ok("todo", "note", "1.1", "to re-run: from the repo root, NO_PROXY=api.example, the internal CA bundle")
        out, _ = self.ok("todo", "done", "1.1", "run:curl -s https://api.example/x → 200", "ok")
        self.assertNotIn("a fresh hand re-runs it", out, "asked once the note is there")
        brief, _ = self.ok("todo", "brief", "1.1")
        self.assertIn("note: to re-run: from the repo root, NO_PROXY=api.example", brief)
        self.assertIn("A run that does not repeat from what is written here", brief)

    def test_no_run_no_question(self):
        out, _ = self.ok("todo", "done", "1.1", "ref:https://canvas.example/abc", "drawn")
        self.assertNotIn("a fresh hand re-runs it", out)


class CopilotCli(Base):
    def setUp(self):
        super().setUp()
        for k in ("CLAUDECODE", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ.update(COPILOT_CLI="1", COPILOT_AGENT_SESSION_ID="3f2a9c1e-7b4d-4e8a-9f00-1234567890ab")

    def test_the_cli_and_its_session_are_named_without_an_export(self):
        self.ok("sign", "GPT-6")
        self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")
        self.assertIn("- done: GitHub Copilot CLI · GPT-6 · session 3f2a9c1e · ", self.line("1.1", "done"))
        os.environ["COPILOT_AGENT_SESSION_ID"] = "9d8c7b6a-0000-4000-8000-000000000000"  # another Copilot CLI session
        out, _ = self.ok("todo", "accept", "1.1", "--by", "copilot", "--run", "jest → green", "re-ran the tests")
        self.assertIn("another session", out)

    def test_where_no_harness_names_a_session_the_advice_is_one_name_per_command(self):
        os.environ.pop("COPILOT_CLI")
        os.environ.pop("COPILOT_AGENT_SESSION_ID")
        code, _, err = run("sign", "GPT-6")
        self.assertEqual(code, 4)
        self.assertIn("where each command opens a new shell, the same name goes before every el command: EL_SESSION=<the "
                      "same name> el sign 'GPT-6'", err)


class VerdictBudget(Base):
    def test_the_brief_budget_is_what_accept_takes(self):
        runs = [f"run:check{k} --all → passed" for k in range(4)]
        self.ok("todo", "done", "1.1", *runs, "ref:https://canvas.example/abc", "shipped")
        brief, _ = self.ok("todo", "brief", "1.1")
        budget = int(re.search(r"1\.1 up to (\d+) chars", brief).group(1))
        self.assertLess(budget, 400, "four re-runs leave far less than the old «about 950»")
        self.assertNotIn("for the words and every --run together", brief)
        os.environ["EL_SESSION"] = OTHER
        reruns = [a for k in range(4) for a in ("--run", f"check{k} --all → passed: " + "n" * 120)]  # one body line each
        words = ("checked " * 100)[:budget].rstrip()
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", *reruns, words)
        self.assertEqual(code, 0, err)


class WrapVoice(Base):
    def test_the_refusal_names_the_lines_that_grew(self):
        long = "слово " * 45
        code, _, err = run("log", "PROBLEM", f"the banner holds\nsymptom: {long}\nroot: {long}\nfields: short\nclass: short")
        self.assertEqual(code, 3)
        self.assertRegex(err, r"6 body lines, 5 fit — el wraps a line at 160 chars: line 2 \(\d+ chars\) takes 2 · line 3 "
                              r"\(\d+ chars\) takes 2 —")


class SlotPath(Base):
    def test_a_promised_path_is_named_with_its_door(self):
        code, _, err = run("phase", "plan", "2", "LateLanguage", "--goal", "Verify and fix delayed language updates without "
                           "changing offline shell behavior [file: artifacts/late-language-verification.json]")
        self.assertEqual(code, 3)
        self.assertIn("«[file: artifacts/late-language-verification.json]» promises a path, 49 of them: the promise names the "
                      "thing, its path comes with done — [file: <a short name>]", err)
        self.ok("phase", "plan", "2", "LateLanguage", "--goal", "Fix delayed language updates, offline shell unchanged "
                "[file: verification json]")  # the door taken: the thing named, its path comes with done


class Habits(Base):
    def test_todo_list_is_the_plan(self):
        bare, _ = self.ok("todo")
        for word in ("list", "status", "ls"):
            with self.subTest(word=word):
                out, _ = self.ok("todo", word)
                self.assertEqual(out, bare)
        out, _ = self.ok("todo", "list", "1")
        self.assertIn("- [ ] 1 Ship", out)

    def test_help_takes_a_command_and_its_action(self):
        out, _ = self.ok("help", "todo", "done")
        self.assertIn("`done` is an action, not a knowledge dose — el todo done:", out)
        out, _ = self.ok("help", "phase", "close")
        self.assertIn("el phase close", out)

    def test_an_action_glued_to_its_number_is_split(self):
        self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")
        out, _ = self.ok("todo", "brief1.1")
        self.assertIn("brief · acceptance of 1.1", out)

    def test_a_case_name_a_letter_off_names_the_nearest_and_takes_nothing(self):
        name = self.case().name
        code, _, err = run("--case", name.replace("shop", "shp"), "todo")
        self.assertEqual(code, 4)
        self.assertIn(f"the nearest: `{name}`", err)
        self.assertIn(f"recovery: el --case {name} …", err)

    def test_habitual_event_types_get_their_door(self):
        for typ, door in (("FINDING", "is a RESULT: el log RESULT"), ("PROGRESS", "is a RESULT"),
                          ("REFLECT", "el log DECISION \"reflect: …\""), ("PLAN", "a plan is not an event")):
            with self.subTest(typ=typ):
                code, _, err = run("log", typ, "something")
                self.assertEqual(code, 2)
                self.assertIn(door, err)


class LogLines(Base):
    def test_quoted_phrases_are_the_events_lines(self):
        self.ok("log", "RESULT", "the banner is gone", "root: the cache kept the old error", "fix: one line for the outage")
        journal = (self.case() / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn("  RESULT · the banner is gone …\n    root: the cache kept the old error\n    fix: one line for the outage",
                      journal)

    def test_lone_words_stay_refused_and_the_refusal_says_why(self):
        code, _, err = run("log", "RESULT", "done", "the", "parser")
        self.assertEqual(code, 2)
        self.assertIn("the text is one argument: put it in one pair of quotes", err)
        self.assertNotIn("words after an option", err, "no option was given")


class PhaseNameGoal(Base):
    def test_the_goal_given_stays_in_the_printed_command(self):
        code, _, err = run("phase", "plan", "2", "Old Python and links", "--goal", "el runs on 3.9 [run: unittest → OK]")
        self.assertEqual(code, 2)
        self.assertIn("4 words, 1–3 fit", err)
        self.assertIn("el phase plan 2 '<English name>' --goal 'el runs on 3.9 [run: unittest → OK]'", err)

    def test_without_a_goal_the_words_of_the_name_become_it(self):
        code, _, err = run("phase", "plan", "2", "Старый питон")
        self.assertEqual(code, 2)
        self.assertIn("the words in your language go into the goal: el phase plan 2 '<English name>' --goal 'Старый питон'", err)


class CodexRound1(Base):
    """Codex's break of the batch, 2026-10-20 (gpt-6.1-sol, 67 probes under 3.14 and 3.9): fifteen confirmed holes."""

    def todo_text(self) -> str:
        return (self.case() / "TODO.md").read_text(encoding="utf-8")

    def test_an_alias_is_only_ever_a_read(self):
        before = self.todo_text()
        code, _, _ = run("todo", "list", "done", "1.1", "owner", "finished through a list")
        self.assertEqual(code, 2)
        self.assertEqual(self.todo_text(), before)
        out, _ = self.ok("todo", "list", "--case", self.case().name)
        self.assertIn("1.1 ship the design", out)

    def test_a_glued_number_is_split_only_for_todo_and_phase(self):
        code, _, _ = run("case", "cancel2")
        self.assertEqual(code, 2)
        self.assertNotIn("closed:", (self.case() / "README.md").read_text(encoding="utf-8"))

    def test_a_name_with_a_word_of_its_own_is_a_name(self):
        for name in ("Sonnet 5.5 (default thinking)", "None-X 2", "Nova 2 Pro"):  # a name carries its version (round 5)
            with self.subTest(name=name):
                self.ok("sign", name)
        self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")
        for said in ("not provided", "модель не указана", "same as parent"):
            with self.subTest(said=said):
                os.environ["EL_MODEL"] = said
                try:
                    self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "jest → green", "checked")
                finally:
                    os.environ.pop("EL_MODEL")
                self.assertIn("acceptor's model not given", self.line("1.1", "accepted"))
                self.ok("todo", "reopen", "1.1", "--by", "subagent", "--run", "jest → green", "again")
                self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")

    def test_the_sign_advice_quotes_the_name_and_keeps_as(self):
        for k in ("CLAUDECODE", "EL_SESSION"):
            os.environ.pop(k, None)
        code, _, err = run("sign", "Opus 5.5 it's $150", "--as", "Example Harness")  # a name with its version, `'` and `$`
        self.assertEqual(code, 4)
        self.assertIn("EL_SESSION=<the same name> el sign 'Opus 5.5 it'\\''s $150' --as 'Example Harness'", err)
        self.assertIn("el sign 'Opus 5.5 it'\\''s $150' --as 'Example Harness'", err.split("export EL_SESSION=")[1])

    def test_the_verdict_budget_holds_at_its_number(self):  # Codex, rounds 1–2: a sample and a margin did not hold
        import random
        for n_runs in range(6):
            for seed in range(6):
                rnd = random.Random(seed * 10 + n_runs)
                with self.subTest(n_runs=n_runs, seed=seed):
                    runs = [f"run:check{k} → passed" for k in range(n_runs)] or ["owner"]
                    self.ok("todo", "done", "1.1", *runs, "ref:https://canvas.example/abc", "ok")
                    brief, _ = self.ok("todo", "brief", "1.1")
                    budget = int(re.search(r"1\.1 up to (\d+) chars", brief).group(1))
                    words = ""
                    while len(words) < budget + 30:
                        words += "w" * rnd.randint(1, 24) + " "  # the brief's condition: words up to 24 chars
                    words = words[:budget].rstrip()
                    os.environ["EL_SESSION"] = OTHER
                    # and each re-run on one line (≤ 152 chars)
                    reruns = [a for k in range(n_runs) for a in ("--run", f"check{k} → passed " + "n" * (134 - rnd.randint(0, 30)))]
                    code, _, err = run("todo", "accept", "1.1", "--by", "codex", *reruns, words)
                    self.assertEqual(code, 0, f"budget {budget}: {err}")
                    self.ok("todo", "reopen", "1.1", "--by", "codex", *reruns, "next round")
                    os.environ["EL_SESSION"] = DOER

    def test_more_re_runs_than_lines_are_said_as_such(self):
        self.ok("todo", "done", "1.1", *[f"run:check{k} → passed" for k in range(6)], "ref:https://canvas.example/abc", "ok")
        brief, _ = self.ok("todo", "brief", "1.1")
        self.assertIn("1.1: its 6 run proofs take more lines than one event has — short re-runs share a line", brief)

    def test_a_run_attached_later_and_each_item_of_a_range_are_asked(self):
        self.ok("todo", "add", "1", "ship the copy", "--expect", "[owner]")
        self.ok("todo", "done", "1.2", "owner", "agreed")
        out, _ = self.ok("todo", "done", "1.2", "run:check → pass", "and checked")
        self.assertIn("el todo note 1.2 'to re-run: …'", out)
        self.ok("todo", "note", "1.2", "to re-run: from the repo root")
        self.ok("todo", "reopen", "1.2", "range next")
        out, _ = self.ok("todo", "done", "1.1-1.2", "run:check → pass", "both")
        self.assertIn("el todo note 1.1 'to re-run: …'", out, "1.2's note does not answer for 1.1")

    def test_phrases_after_a_double_dash_may_start_with_a_dash(self):
        self.ok("log", "RESULT", "--", "headline words", "- bullet words")
        self.assertIn("    - bullet words", (self.case() / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_help_says_an_action_lives_in_another_command(self):
        out, _ = self.ok("help", "todo", "plan")
        self.assertIn("`plan` is not an action of el todo — it is el phase plan", out)

    def test_readme_show_takes_the_case(self):
        out, _ = self.ok("readme", "show", "--case", self.case().name)
        self.assertIn("## State", out)

    def test_an_unnamed_slot_stays_in_its_group(self):
        self.ok("todo", "add", "1", "two runs", "--expect", "[run] [run: b]")
        out, _ = self.ok("todo", "done", "1.2", "run:a → ok", "run:b → ok", "both ran")
        self.assertIn("[run] · [run: b] ← run a → ok · run b → ok", out)

    def test_line_numbers_are_the_writers_own(self):
        long = "слово " * 45
        code, _, err = run("log", "PROBLEM", f"head\n\nsymptom: {long}\n\nroot: {long}\nfields: short\nclass: short")
        self.assertEqual(code, 3)
        self.assertRegex(err, r"line 3 \(\d+ chars\) takes 2 · line 5 \(\d+ chars\) takes 2")

    def test_a_double_dash_before_the_command_is_read_as_before(self):
        code, _, _ = run("--", "todo", "list")
        self.assertEqual(code, 2, "both pythons refuse it, as HEAD did")


class FileVersionWords(Base):
    def test_a_summary_fix_is_recorded_with_the_same_words(self):
        docs = self.case() / "docs"
        docs.mkdir()
        letter = docs / "letter.md"
        letter.write_text("# Letter\nsummary: " + "long summary words " * 9 + "\n\nbody\n", encoding="utf-8")
        _, err = self.ok("todo", "done", "1.1", "file:docs/letter.md", "the letter shipped")
        self.assertIn('record that version with the same words: el todo done 1.1 file:docs/letter.md "the letter shipped"', err)
        letter.write_text("# Letter\nsummary: a short summary now\n\nbody\n", encoding="utf-8")
        code, _, err = run("todo", "done", "1.1", "file:docs/letter.md")
        self.assertEqual(code, 2)
        self.assertIn('the same words — el todo done 1.1 file:docs/letter.md "the letter shipped"', err)
        self.ok("todo", "done", "1.1", "file:docs/letter.md", "the letter shipped")  # as printed
        self.assertIn("- result: the letter shipped", (self.case() / "TODO.md").read_text(encoding="utf-8"))

    def test_the_dose_says_a_new_version_writes_a_result(self):
        out, _ = self.ok("help", "evidence")
        self.assertIn("a file of the case in a new\nversion is a new claim: it asks for words and writes a RESULT", out)


class CodexRound2(Base):
    """Codex's second round, 2026-10-20: fourteen of fifteen fixed, six new — one of them in HEAD as well."""

    def test_readme_show_never_writes(self):
        import io
        from unittest import mock as m
        before = (self.case() / "README.md").read_text(encoding="utf-8")
        fake = io.StringIO("# x\n\n## Context\nreplaced\n")
        with m.patch("elephant.main._piped_text", lambda: fake.read()):
            out, _ = self.ok("readme", "show")
        self.assertEqual((self.case() / "README.md").read_text(encoding="utf-8"), before)
        self.assertNotIn("written:", out)

    def test_more_not_known_phrases(self):
        self.ok("sign", "Opus 5.5")
        self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")
        for said in ("model not exposed by this harness", "not disclosed", "unknown model (not exposed to me)",
                     "модель мне неизвестна"):
            with self.subTest(said=said):
                os.environ["EL_MODEL"] = said
                try:
                    self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "jest → green", "checked")
                finally:
                    os.environ.pop("EL_MODEL")
                self.assertIn("acceptor's model not given", self.line("1.1", "accepted"))
                self.ok("todo", "reopen", "1.1", "--by", "subagent", "--run", "jest → green", "again")
                self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")

    def test_help_knows_the_aliases(self):
        out, _ = self.ok("help", "todo", "list")
        self.assertIn("`el todo list` is the bare `el todo` — it shows the plan", out)
        out, _ = self.ok("help", "readme", "show")
        self.assertIn("it shows the README, never writes", out)

    def test_a_range_with_a_done_item_is_not_the_first_done(self):
        self.ok("phase", "plan", "2", "Fix", "--goal", "fixed [owner]")
        self.ok("todo", "add", "2", "fix A", "--expect", "[owner]")
        self.ok("todo", "add", "2", "fix B", "--expect", "[owner]")
        self.ok("todo", "done", "2.1", "owner", "agreed A")
        out, _ = self.ok("todo", "done", "2.1-2.2", "owner", "agreed both")
        self.assertNotIn("is planned, not open", out)

    def test_a_partly_filled_kind_proves_no_promise_of_it_at_the_gate(self):  # in HEAD as well
        self.ok("phase", "plan", "2", "Gate", "--goal", "alpha holds [run: alpha]")
        self.ok("todo", "add", "2", "both runs", "--expect", "[run: alpha] [run: beta]")
        self.ok("todo", "done", "2.1", "run:beta → pass", "beta only")
        code, _, err = run("phase", "close", "2", "closed", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4, err)
        self.assertIn("phase 2 promised [run: alpha] — 2.1 promises it and is not proved with a run", err)
        self.ok("todo", "done", "2.1", "run:alpha → pass", "alpha too")  # the whole kind filled: the promise holds
        self.ok("phase", "close", "2", "closed", "--reflect", "r", "--align", "a")


class CodexRound3(Base):
    """Codex's third round, 2026-10-20: C6 and N1–N6 fixed; four new P2, three of them in the re-record of 41.14."""

    def letter(self, summary: str):
        docs = self.case() / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "letter.md").write_text(f"# Letter\nsummary: {summary}\n\nbody\n", encoding="utf-8")

    def test_words_that_start_with_a_dash_are_printed_after_a_double_dash(self):
        self.letter("long summary words " * 9)
        _, err = self.ok("todo", "done", "1.1", "file:docs/letter.md", "--", "--case=other")
        self.assertIn('el todo done 1.1 file:docs/letter.md -- "--case=other"', err)
        self.letter("short now")
        self.ok("todo", "done", "1.1", "file:docs/letter.md", "--", "--case=other")  # as printed: the words, not an option
        self.assertIn("- result: --case=other", (self.case() / "TODO.md").read_text(encoding="utf-8"))

    def test_a_done_without_words_prints_the_items_own(self):
        self.ok("todo", "done", "1.1", "owner", "the letter shipped")
        self.letter("long summary words " * 9)
        _, err = self.ok("todo", "done", "1.1", "file:docs/letter.md")
        self.assertIn('record that version with the same words: el todo done 1.1 file:docs/letter.md "the letter shipped"', err)

    def test_a_long_result_can_be_re_recorded(self):  # in HEAD as well
        words = ("word " * 174).strip()  # 869 chars: room for the words, not for the version tail too
        self.letter("short summary")
        self.ok("todo", "done", "1.1", "file:docs/letter.md", words)
        self.letter("a shorter summary")
        self.ok("todo", "done", "1.1", "file:docs/letter.md", words)
        self.assertIn("1.1: file [letter.md](docs/letter.md)", (self.case() / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_a_sentence_saying_not_known_is_no_model(self):
        self.ok("sign", "Opus 5.5")
        self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")
        # and round 4: a sentence is no name, a digit in it changes nothing — judged by form, not by a word list
        for said in ("not exposed by this runtime", "not disclosed in the system prompt", "модель не раскрыта",
                     "model not specified in instructions", "мне неизвестна точная модель",
                     "not exposed by this runtime (Python 3.9)", "I do not know which model is running",
                     "model identity is unavailable to me", "model name withheld by the system", "модель не раскрыта в сессии 123",
                     "I don't know", "not yet disclosed", "I cannot tell", "model isn't exposed", "пока не определена",  # round 5
                     "I don't know 2", "not yet disclosed 2", "model isn't exposed 2", "model identity pending 2", "2026-10-20",
                     "123", "v2"):  # round 6: a digit alone is no version of a name
            with self.subTest(said=said):
                os.environ["EL_MODEL"] = said
                try:
                    self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "jest → green", "checked")
                finally:
                    os.environ.pop("EL_MODEL")
                self.assertIn("acceptor's model not given", self.line("1.1", "accepted"))
                self.ok("todo", "reopen", "1.1", "--by", "subagent", "--run", "jest → green", "again")
                self.ok("todo", "done", "1.1", "run:jest → green", "ref:https://canvas.example/abc", "shipped")
        for name in ("Sonnet 5.5 (default thinking)", "None-X 2", "gpt-6-luna", "Meta Llama 3.3 70B Instruct", "o4-mini-high",
                     "o3", "claude-opus-5-5", "gpt4o"):
            with self.subTest(name=name):
                self.ok("sign", name)


if __name__ == "__main__":
    unittest.main()
