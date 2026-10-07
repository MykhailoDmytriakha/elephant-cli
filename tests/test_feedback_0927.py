"""The owner's word, 2026-09-27: a report speaks not only of how el was used but of the onboarding block — does it need a
line added, changed, dropped, or is it enough. The block is the first dose, read before el says anything, and the
reporting agent is the only one who lives with it: every rewrite so far followed the owner's eye or a rule change, none
came from an agent telling what the block did to its start, and the last one was never checked by a cold agent. Since
1.28.0 `--onboarding` is required («enough» is a full answer) and lands as `## Onboarding` in the report."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge, main
from tests.test_commands import run


class OnboardingWord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.pool = Path(self.tmp.name) / "pool"
        os.environ["EL_FEEDBACK_DIR"] = str(self.pool)

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_FEEDBACK_DIR", None)
        self.tmp.cleanup()

    def test_a_report_without_a_word_on_the_block_is_refused_with_the_fix(self):
        code, out, err = run("feedback", "done refuses a path", "--actual", "exit 2: …", "--expected", "accepted")
        self.assertEqual(code, 2)
        self.assertIn("feedback needs --onboarding", err, "the missing field is named, not the whole list")
        self.assertIn("«enough»", err, "the honest short answer is offered — the refusal always has a fix")
        self.assertIn("el onboarding --show", err, "where to read the block the word is about")
        self.assertIn("recovery: el help feedback", err)
        self.assertFalse(self.pool.exists(), "nothing was written")

    def test_a_blank_word_is_silence_too(self):
        code, _, err = run("feedback", "t", "--actual", "a", "--expected", "e", "--onboarding", "  ")
        self.assertEqual(code, 2)
        self.assertIn("--onboarding", err)

    def test_every_missing_field_is_named_at_once(self):
        code, _, err = run("feedback", "t", "--actual", "a")
        self.assertEqual(code, 2)
        self.assertIn("feedback needs --expected, --onboarding", err, "one refusal, not one per retry")

    def test_the_word_lands_as_its_own_section(self):
        word = "the line «tick at once» was right; missing: how to see the block el ships — `el onboarding --show`"
        code, out, err = run("feedback", "t", "--actual", "a", "--expected", "e", "--acceptance", "a test",
                             "--onboarding", word)
        self.assertEqual(code, 0, err)
        text = Path(out.split("feedback written: ", 1)[1].split("\n", 1)[0].strip()).read_text()
        self.assertIn(f"## Onboarding\n{word}\n", text)
        self.assertLess(text.index("## Acceptance"), text.index("## Onboarding"), "the block last, after the wall itself")

    def test_enough_is_a_full_answer(self):
        code, out, err = run("feedback", "t", "--actual", "a", "--expected", "e", "--onboarding", "enough")
        self.assertEqual(code, 0, err)
        self.assertIn("## Onboarding\nenough\n", Path(out.split("feedback written: ", 1)[1].split("\n", 1)[0].strip()).read_text())


class Doses(unittest.TestCase):
    def test_the_feedback_dose_asks_for_the_block_and_weighs_a_line_in_it(self):
        dose = " ".join(knowledge.resolve("feedback").split())  # read as prose: a phrase may wrap
        self.assertIn('--onboarding "…"', dose, "in the form line, not only in the table")
        self.assertIn("Title, --actual, --expected and --onboarding are required", dose)
        self.assertIn("el onboarding --show", dose)
        self.assertIn("«enough» is a full answer", dose)
        self.assertIn("a habit needed before el speaks", dose, "the block earns a line only for what el cannot say itself")
        self.assertIn("a report of depth 2, not a line in the block", dose, "what el can say in the moment goes to its output")

    def test_every_door_to_feedback_shows_the_required_word(self):
        self.assertTrue(any("--onboarding" in ln for ln in main.examples_for("feedback")), "`el --help` example")
        self.assertIn("--onboarding", knowledge.resolve("where"), "el help where names the whole form")
        self.assertIn("el feedback", knowledge.resolve("onboarding"), "the onboarding dose names the channel back")

    def test_the_block_itself_did_not_grow(self):
        # the word travels through the report, not through the block every agent reads at every start; the block
        # names the reflex (the owner's word, 2026-10-06), never the report's form — that is the dose's
        for flag in ("--onboarding", "--actual", "--expected"):
            self.assertNotIn(flag, knowledge.ONBOARDING_BLOCK)


if __name__ == "__main__":
    unittest.main()
