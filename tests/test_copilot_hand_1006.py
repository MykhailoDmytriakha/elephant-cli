"""The owner's word, 2026-10-06 (el 1.40.0): an item done by an agent in VS Code Copilot was signed `harness ? · model ? ·
session ?`, and the agent's `el sign 'Gemini 3.8 Flash'` was refused. el knew two harnesses by their variables (Claude
Code, Codex); VS Code marks its Copilot agent terminals with COPILOT_AGENT=1 (microsoft/vscode PR #316267, VS Code 1.121)
and gives no session id. el's hint at done sent the agent to `el sign`, `el sign` refused for want of a session, and the
refusal's advice — `EL_SESSION=<name> el sign` — set the session for that one command only, so the next `done` could not
find the signature. Now Copilot is named, and every line that sends an agent to sign carries the command that works where
the harness gives no session: `export EL_SESSION=<8 hex> && el sign '<model>'` — Copilot keeps its terminal."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

ENVS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_THREAD_ID", "COPILOT_AGENT",
        "EL_MODEL", "EL_SESSION", "EL_HANDS_DIR", "EL_HINTS", "EL_TWO_HANDS")


class InCopilot(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS="0", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"), COPILOT_AGENT="1")
        run("case", "new", "login", "--goal", "g")
        run("phase", "open", "1", "Fix", "--goal", "g")
        run("todo", "add", "1", "fix the login", "--expect", "[run: tests → OK]")
        run("todo", "add", "1", "test the login", "--expect", "[run: e2e → OK]")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def todo(self) -> str:
        return next((Path(self.tmp.name) / ".cases").iterdir()).joinpath("TODO.md").read_text()

    def test_copilot_is_named(self):
        code, _, err = run("todo", "done", "1.1", "run:tests → OK", "fixed")
        self.assertEqual(code, 0, err)
        self.assertIn("    - done: GitHub Copilot · model ? · session ? · ", self.todo())

    def test_sign_without_a_session_names_the_command_that_works(self):
        code, _, err = run("sign", "Gemini 3.8 Flash")
        self.assertEqual(code, 4)
        self.assertIn("GitHub Copilot gives el no session id", err)
        self.assertRegex(err, r"export EL_SESSION=[0-9a-f]{8} && el sign 'Gemini 3\.8 Flash'")
        self.assertNotIn("EL_SESSION=<name> el sign", err, "a variable for one command is gone by the next done")

    def test_the_named_session_signs_every_done_after_it(self):
        _, _, err = run("sign", "Gemini 3.8 Flash")
        os.environ["EL_SESSION"] = re.search(r"export EL_SESSION=([0-9a-f]{8})", err).group(1)  # the terminal keeps the export
        code, out, err = run("sign", "Gemini 3.8 Flash")
        self.assertEqual(code, 0, err)
        self.assertIn("signed: GitHub Copilot · Gemini 3.8 Flash · session ", out)
        run("todo", "done", "1.1", "run:tests → OK", "fixed")
        run("todo", "done", "1.2", "run:e2e → OK", "tested")
        self.assertEqual(self.todo().count("    - done: GitHub Copilot · Gemini 3.8 Flash · session "), 2)

    def test_the_hint_at_done_carries_the_export_where_no_session_is_given(self):
        os.environ["EL_HINTS"] = "1"
        code, out, _ = run("todo", "done", "1.1", "run:tests → OK", "fixed")
        self.assertRegex(out, r"say it once per session: export EL_SESSION=[0-9a-f]{8} && el sign '<your model>'")
        os.environ["EL_SESSION"] = "copilot1"
        code, out, _ = run("todo", "done", "1.2", "run:e2e → OK", "tested")
        self.assertIn("say it once per session: el sign '<your model>'", out, "a session given: no export to teach")

    def test_a_harness_run_inside_copilot_is_the_one_named(self):
        os.environ.update(CLAUDECODE="1", CLAUDE_CODE_SESSION_ID="inner001")
        run("todo", "done", "1.1", "run:tests → OK", "fixed")
        self.assertIn("    - done: Anthropic Claude Code · model ? · session inner001 · ", self.todo())


if __name__ == "__main__":
    unittest.main()
