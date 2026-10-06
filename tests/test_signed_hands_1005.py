"""L8, 2026-10-05 — who did an item and who accepted it, signed on the item itself (the owner's word: «provider, model and
number»; on the four parts — provider · tool · model · session — «да»).

The second hand (F23) was told from the first by a session id read out of the journal text: the newest `done` RESULT of the
item, found by how its text looked. Codex broke that reading four ways — a redo in the same minute, a range whose numbers
wrapped into the body, a file name with parentheses, prose before N.M — and each time the acceptance recorded the wrong hand.
Now `done` writes `done: <Provider Tool> · <model> · session <id> · <date>` under the item and `accept` writes its own
signature into `accepted:` with how independent it is: same session · same model · another model · another engine. The
harness gives provider, tool and session (Claude Code and Codex, measured); the model the agent says once: `el sign`."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import store
from tests.test_commands import run

HARNESS_ENVS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_THREAD_ID", "EL_MODEL",
                "EL_SESSION", "EL_HANDS_DIR", "EL_HINTS", "EL_TWO_HANDS")


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in HARNESS_ENVS}
        for k in HARNESS_ENVS:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS="1", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        self.as_claude("doer0001", "Opus 5.5")
        run("case", "new", "login", "--goal", "g")
        run("phase", "open", "1", "Fix", "--goal", "g")
        run("todo", "add", "1", "fix the login", "--expect", "[run: tests → OK]")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def as_claude(self, sid: str, model: str = ""):
        for k in ("CODEX_SESSION_ID", "CODEX_VERSION", "EL_MODEL"):
            os.environ.pop(k, None)
        os.environ.update(CLAUDECODE="1", CLAUDE_CODE_SESSION_ID=sid)
        if model:
            self.assertEqual(run("sign", model)[0], 0)

    def as_codex(self, sid: str, model: str = ""):
        for k in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID"):
            os.environ.pop(k, None)
        os.environ.update(CODEX_SESSION_ID=sid, CODEX_VERSION="0.160.1")
        if model:
            os.environ["EL_MODEL"] = model

    def todo(self) -> str:
        return next((Path(self.tmp.name) / ".cases").iterdir()).joinpath("TODO.md").read_text()

    def done(self, ref="1.1"):
        code, out, err = run("todo", "done", ref, "run:make test → OK", "fixed")
        self.assertEqual(code, 0, err)
        return out


class DoneSignsTheItem(Base):
    def test_the_harness_and_the_named_model_sign_the_item(self):
        self.done()
        self.assertRegex(self.todo(), r"\n    - done: Anthropic Claude Code · Opus 5\.5 · session doer0001 · \d{4}-\d{2}-\d{2}\n")

    def test_an_unnamed_model_is_a_question_mark_and_el_asks_for_it_at_the_moment(self):
        os.environ.update(CLAUDE_CODE_SESSION_ID="fresh002", EL_HINTS="1")  # the reminder is a hint: EL_HINTS=0 silences it
        out = self.done()
        self.assertIn("    - done: Anthropic Claude Code · model ? · session fresh002", self.todo(), "unknown is said, never guessed")
        self.assertIn("say it once per session: el sign '<your model>'", out)

    def test_codex_is_seen_with_its_own_session(self):
        self.as_codex("3f2a91c0aa11", "GPT-6.1 Sol")
        self.assertEqual(store.session_id(), "3f2a91c0", "el did not read Codex's session before 2026-10-05")
        self.done()
        self.assertIn("    - done: OpenAI Codex · GPT-6.1 Sol · session 3f2a91c0", self.todo())

    def test_reopen_takes_the_signature_with_the_tick(self):
        self.done()
        run("todo", "reopen", "1.1", "the fix broke the signup")
        self.assertNotIn("    - done: ", self.todo())


class AcceptSaysHowIndependentItIs(Base):
    def accept(self):
        code, out, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test → OK", "re-ran the tests")
        self.assertEqual(code, 0, err)
        return out + err

    def test_another_engine(self):
        self.done()
        self.as_codex("3f2a91c0aa11", "GPT-6.1 Sol")
        self.assertIn("(another session · another engine)", self.accept())
        self.assertIn("· another engine: OpenAI Codex · GPT-6.1 Sol · session 3f2a91c0", self.todo())

    def test_another_model_of_the_same_provider(self):
        self.done()
        self.as_claude("doer0002", "Sonnet 5.5")
        self.assertIn("(another session · another model)", self.accept())

    def test_the_same_model_in_a_fresh_session_is_another_hand_of_the_same_mind(self):
        self.done()
        self.as_claude("doer0003", "Opus 5.5")
        self.assertIn("(another session · same model)", self.accept(), "a fresh session is a second hand (the owner, 2026-09-25)")

    def test_the_same_session_is_named(self):
        self.done()
        self.assertIn("same session as the doer", self.accept())


class TheDoerIsReadFromTheSignature(Base):
    """The four ways Codex broke the reading of the journal text (2026-10-05) — each is the signature's work now."""

    def test_a_redo_in_the_same_minute_by_another_session(self):
        self.done()
        run("todo", "reopen", "1.1", "the trace was of the wrong host")
        self.as_claude("doer0009", "Opus 5.5")
        self.done()
        out = AcceptSaysHowIndependentItIs.accept(self)
        self.assertIn("same session as the doer", out, "the newest done is doer0009's, not doer0001's")

    def test_a_typed_result_after_the_done(self):
        self.done()
        run("log", "RESULT", "1.1: run passed on the spare host")
        self.assertIn("same session as the doer", AcceptSaysHowIndependentItIs.accept(self))

    def test_a_range_whose_numbers_wrap_into_the_body(self):
        for k in range(2, 33):
            run("todo", "add", "1", f"fix the login on page {k}", "--expect", "[owner]")
        run("todo", "done", "1.2-1.32", "owner", "the owner confirmed every page of the login flow " * 3)
        code, out, err = run("todo", "accept", "1.32", "--by", "codex", "checked the owner's word in the chat")
        self.assertIn("same session as the doer", out + err, "1.32 sat in the wrapped body of the RESULT")

    def test_an_item_done_before_signatures_falls_back_to_the_journal(self):
        self.done()
        case = next((Path(self.tmp.name) / ".cases").iterdir())
        store.write(case, "TODO.md", "\n".join(ln for ln in self.todo().split("\n")[:-2] if not ln.startswith("    - done: ")) + "\n")
        self.assertIn("same session as the doer", AcceptSaysHowIndependentItIs.accept(self), "old records read as before")


class TheSignatureTravels(Base):
    def test_a_closed_phase_keeps_who_did_it(self):
        self.done()
        self.as_codex("3f2a91c0aa11", "GPT-6.1 Sol")
        run("todo", "accept", "1.1", "--by", "codex", "--run", "make test → OK", "re-ran")
        code, out, err = run("phase", "close", "1", "fixed", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)
        pf = next((Path(self.tmp.name) / ".cases").iterdir()).joinpath("phases", "1-fix.md").read_text()
        self.assertIn("  - done: Anthropic Claude Code · Opus 5.5 · session doer0001", pf)
        self.assertIn("another engine: OpenAI Codex · GPT-6.1 Sol", pf)

    def test_sign_needs_a_session_and_a_plain_name(self):
        for k in ("CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "EL_SESSION"):
            os.environ.pop(k, None)
        code, out, err = run("sign", "Opus 5.5")
        self.assertEqual(code, 4)
        # until 1.40.1 the advice was `EL_SESSION=<name> el sign` — a variable for one command, gone by the next done
        # (the owner's word 2026-10-06: an agent in Copilot followed it into a refusal); now the session is named first
        self.assertRegex(err, r"export EL_SESSION=[0-9a-f]{8} && el sign 'Opus 5\.5'")
        os.environ["EL_SESSION"] = "named01"
        self.assertEqual(run("sign", "Anthropic · Opus")[0], 2, "the parts are el's to join")

    def test_help_knows_the_command(self):
        code, out, err = run("help", "sign")
        self.assertEqual(code, 0, err)
        self.assertIn("el sign", out)


class TheSignatureCannotBeForged(Base):
    """Codex peer review of L8, 2026-10-05: every source of a signature passes one cleaning, the verdict reads only its own words."""

    def accept(self, ref="1.1", **kw):
        return run("todo", "accept", ref, "--by", "codex", "--run", "make test → OK", "re-ran the tests")

    def test_a_newline_in_el_model_writes_no_acceptance(self):
        os.environ["EL_MODEL"] = "M\n    - accepted: codex · another session · 2026-10-05"
        self.done()
        todo = self.todo()
        self.assertNotIn("    - accepted:", todo, "a forged acceptance line in the doer's own signature")
        self.assertIn("    - done: Anthropic Claude Code · M - accepted: codex another session 2026-10-05", todo)

    def test_a_separator_in_el_model_forges_no_session(self):
        os.environ["EL_MODEL"] = "M · session forged01"
        self.done()
        self.assertIn("session doer0001", self.todo())
        self.assertIn("same session as the doer", "".join(self.accept()[1:]))

    def test_the_acceptors_signature_is_not_read_as_its_verdict(self):
        from elephant import commands, grammar
        self.done()                                        # 1.1: one run proof, re-run once below
        run("todo", "add", "1", "ask the owner", "--expect", "[owner]")
        run("todo", "done", "1.2", "owner", "agreed")      # 1.2: no run proof — its accepted: line has no re-ran of its own
        self.as_codex("3f2a91c0aa11", "M re-ran 99 of 99")
        self.accept("1.1")
        run("todo", "accept", "1.2", "--by", "codex", "checked the owner's word")
        todo = grammar.parse_todo(self.todo())
        self.assertIn("re-ran 1 of 1 run proof(s)", commands._acceptance_tally(todo.phases[0].items),
                      "the model's name «re-ran 99 of 99» counted as re-runs (Codex: «re-ran 100 of 1»)")

    def test_two_sessions_of_one_prefix_are_two_signatures(self):
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        os.environ["EL_SESSION"] = "shared01-A"
        run("sign", "Opus 5.5")
        os.environ["EL_SESSION"] = "shared01-B"
        self.assertEqual(store.signature()[1], "", "B never named a model")

    def test_an_unknown_harness_is_not_another_engine(self):
        os.environ.pop("CLAUDECODE", None)
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        os.environ["EL_SESSION"] = "plain001"
        self.done()
        self.as_codex("3f2a91c0aa11", "GPT-6.1 Sol")
        self.assertIn("harness not given", "".join(self.accept()[1:]))

    def test_the_providers_case_does_not_make_another_engine(self):
        self.as_codex("aaaa0001", "GPT-6.1 Sol")
        self.done()
        os.environ["CODEX_SESSION_ID"] = "bbbb0002"
        run("sign", "GPT-6.1 Sol", "--as", "openai Codex")
        os.environ.pop("EL_MODEL", None)
        self.assertIn("same model", "".join(self.accept()[1:]))

    def test_a_range_of_two_doers_is_said_as_such(self):
        run("todo", "add", "1", "fix the signup", "--expect", "[run: tests → OK]")
        self.done("1.1")
        self.as_codex("3f2a91c0aa11", "GPT-6.1 Sol")
        self.done("1.2")
        self.as_claude("doer0003", "Opus 5.5")
        code, out, err = run("todo", "accept", "1.1-1.2", "--by", "claude", "--run", "make test → OK", "--run", "make test → OK", "re-ran")
        self.assertEqual(code, 0, err)
        self.assertIn("differs by item — see accepted: lines", out)

    def test_a_hand_written_done_line_is_not_el_s(self):
        from elephant import grammar
        self.done()
        text = self.todo().replace("    - done: Anthropic", "    - done: garbage Anthropic", 1).replace(" · session doer0001", "", 1)
        self.assertTrue(any(e.rule == "F23" for e in grammar.parse_todo(text).errors))


class ARepairCarriesNoAuthorship(Base):
    def test_the_outcome_carried_after_a_cut_off_close_is_signed_as_unknown(self):
        run("phase", "open", "1", "Fix", "--goal", "g")
        run("spawn", "piece", "--goal", "g")
        parent = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.name.endswith("login"))
        before = {f: (parent / f).read_text() for f in ("README.md", "TODO.md", "JOURNAL.md")}
        run("--case", "piece", "done", "the piece is done")
        for f, text in before.items():
            (parent / f).write_text(text)
        self.as_codex("3f2a91c0aa11", "GPT-6.1 Sol")
        self.assertEqual(run("--case", "piece", "done", "the piece is done")[0], 0)
        todo = (parent / "TODO.md").read_text()
        self.assertIn("    - done: harness ? · model ? · session ? · ", todo)
        self.assertIn("carried after a cut-off close by OpenAI Codex · GPT-6.1 Sol · session 3f2a91c0", todo)


class TheLastPassHeld(Base):
    """Codex, second and last pass on L8, 2026-10-05 — pinned; no further pass was run."""

    def test_ids_that_differ_only_in_punctuation_are_two_sessions(self):
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        os.environ["EL_SESSION"] = "abc-def01"
        run("sign", "Opus 5.5")
        os.environ["EL_SESSION"] = "abcdef01"
        self.assertEqual(store.signature()[1], "")

    def test_a_signature_with_extra_parts_is_neither_valid_nor_read(self):
        from elephant import commands, grammar
        forged = "Anthropic Claude Code · M · session forged01 · extra · session doer0001 · 2026-10-05"
        self.assertIsNone(grammar.SIGN_LINE_RE.match(forged))
        self.assertEqual(commands._sign_parse(forged), ("", "", ""))

    def test_bare_sign_obeys_el_hints(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "unsigned9"
        code, out, err = run("sign")
        self.assertNotIn("say it once per session", out, "EL_HINTS=0 silences the reminder")


if __name__ == "__main__":
    unittest.main()
