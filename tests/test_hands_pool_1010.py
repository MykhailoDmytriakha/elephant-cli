"""The hand and the pool of 2026-10-10: a harness that names its session is the hand, whatever EL_SESSION says (Codex set
it and its own acceptance read «another session»); a fresh session that lands where another session works is told;
and four walls the Codex agents reported from the polygon."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

HARNESS_KEYS = ("CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CLAUDECODE", "CODEX_VERSION")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS", *HARNESS_KEYS)}
        for k in HARNESS_KEYS:
            os.environ.pop(k, None)
        os.environ.update(EL_HINTS="0", EL_SESSION="pool1010", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)
        run("case", "new", "work", "--goal", "x")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-work"))
        run("phase", "open", "1", "Work", "--goal", "x")
        run("phase", "agree", "1", "the owner agreed")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class TheHarnessNamesTheHand(Base):
    def test_el_session_inside_a_harness_that_names_one_is_the_same_hand(self):
        os.environ["CODEX_SESSION_ID"] = "codexaaa-1111"
        run("todo", "add", "1", "rewrite the digest")
        os.environ["EL_SESSION"] = "rootpose"
        run("todo", "done", "1.1", "owner", "rewritten")
        os.environ["EL_SESSION"] = "checkpos"
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "holds")
        self.assertEqual(code, 0, err)
        self.assertIn("same session as the doer", err)
        self.assertIn("session codexaaa", (self.case / "TODO.md").read_text(encoding="utf-8"))

    def test_without_a_harness_id_el_session_still_names_it(self):
        run("todo", "add", "1", "a")
        run("todo", "done", "1.1", "owner", "done")
        os.environ["EL_SESSION"] = "another1"
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "holds")
        self.assertEqual(code, 0, err)
        self.assertNotIn("same session as the doer", err)


class AFreshSessionIsToldWhoHoldsItsCase(Base):
    def test_the_entry_names_the_other_session(self):
        run("case", "use", self.case.name)  # this session holds it
        run("todo", "add", "1", "a")
        os.environ["EL_SESSION"] = "fresh222"
        out = run()[1]
        self.assertIn("note: this session had no case in hand and took", out)
        self.assertIn("another session (pool1010) holds it", out)
        self.assertNotIn("another session", run()[1].split("\n")[2] if len(run()[1].split("\n")) > 2 else "")


class TheWordsAfterAnOptionAreTheText(Base):
    def test_a_spaced_list_with_its_reason_after_by(self):
        for t in ("a", "b"):
            run("todo", "add", "1", t)
        run("todo", "done", "1.1-1.2", "owner", "done")
        os.environ["EL_SESSION"] = "accept33"
        code, _, err = run("todo", "reopen", "1.1,", "1.2", "--by", "codex", "lost doors")
        self.assertEqual(code, 0, err)
        self.assertIn("lost doors", (self.case / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_an_items_words_are_never_guessed(self):
        code, _, err = run("todo", "add", "1", "the item", "--note", "a note", "more words")
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments: more words", err)
        self.assertNotIn("more words", (self.case / "TODO.md").read_text(encoding="utf-8"))

    def test_another_command_still_refuses_extra_words_in_its_own_voice(self):
        code, _, err = run("done", "x", "--reflect", "r")
        self.assertEqual(code, 2)
        self.assertIn("el done: does not take --reflect", err)  # 2026-10-12: another command's option is named, in done's voice


class ANumberMeantAsWrittenHasItsDoor(Base):
    def test_the_refusal_names_the_leading_zero(self):
        run("todo", "add", "1", "a")
        code, _, err = run("todo", "note", "1.1", "WER .172 against 0.05")
        self.assertEqual(code, 2)
        self.assertIn("write it whole: 0.172", err)
        self.assertEqual(run("todo", "note", "1.1", "WER 0.172 against 0.05")[0], 0)


class ARecipeInsideTheCaseIsFound(Base):
    def test_howto_takes_the_path_as_given(self):
        (self.case / ".howto").mkdir()
        (self.case / ".howto" / "re-check.md").write_text("when: a digest to re-check\n# Re-check\n", encoding="utf-8")
        run("todo", "add", "1", "a")
        run("todo", "done", "1.1", "owner", "done")
        run("todo", "accept", "1.1", "--by", "owner", "fine")
        rel = f".cases/{self.case.name}/.howto/re-check.md"
        code, _, err = run("phase", "close", "1", "done", "--reflect", "r", "--align", "a", "--howto", rel)
        self.assertEqual(code, 0, err)


class TheReview(Base):
    """The Codex review of batch 30, 2026-10-11."""

    def test_1_every_command_says_the_other_holder_once(self):
        run("case", "use", self.case.name)
        os.environ["EL_SESSION"] = "fresh333"
        code, _, err = run("check")
        self.assertIn("another session (pool1010) holds it", err)
        self.assertNotIn("another session (pool1010)", run()[1])  # said once: the hand is this session's now

    def test_2_a_recipe_outside_the_project_is_refused(self):
        outside = Path(self.tmp.name).parent / f"outside-{os.getpid()}" / ".howto"
        outside.mkdir(parents=True, exist_ok=True)
        (outside / "a.md").write_text("when: x broke\n", encoding="utf-8")
        run("todo", "add", "1", "a")
        run("todo", "done", "1.1", "owner", "done")
        run("todo", "accept", "1.1", "--by", "owner", "fine")
        try:
            code, _, err = run("phase", "close", "1", "done", "--reflect", "r", "--align", "a", "--howto", str(outside / "a.md"))
        finally:
            (outside / "a.md").unlink()
            outside.rmdir()
            outside.parent.rmdir()
        self.assertEqual(code, 4)
        self.assertIn("is outside this project", err)

    def test_3_two_recipe_paths_keep_their_own_links(self):
        (Path(self.tmp.name) / ".howto").mkdir()
        (Path(self.tmp.name) / ".howto" / "a.md").write_text("when: project\n", encoding="utf-8")
        (self.case / ".howto").mkdir()
        (self.case / ".howto" / "a.md").write_text("when: case\n", encoding="utf-8")
        run("todo", "add", "1", "a")
        run("todo", "done", "1.1", "owner", "done")
        run("todo", "accept", "1.1", "--by", "owner", "fine")
        inner = f".cases/{self.case.name}/.howto/a.md"
        code, _, err = run("phase", "close", "1", "done", "--reflect", "r", "--align", "a", "--howto", f"{inner} .howto/a.md")
        self.assertEqual(code, 0, err)
        text = next((self.case / "phases").glob("1-*.md")).read_text(encoding="utf-8")
        self.assertIn("howto: [a.md](../.howto/a.md) [a.md](../../../.howto/a.md)", text)  # the case's, then the project's


if __name__ == "__main__":
    unittest.main()
