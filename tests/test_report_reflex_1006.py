"""The owner's word, 2026-10-06: the growth loop of el ran on the owner — a report came only when the owner asked for one.
The block every agent reads at every start said nothing of `el feedback`, and a test held that silence. el cannot see
its own defect, so it cannot say so in the moment; the agent that hits the wall is the only sensor. Since 1.42.0 the
block carries the reflex (el let you down → report at once, unasked, go on, tell the owner at the end), the dose and
the command's own output say the same, and the one moment el does see a workaround — a hand edit past the stamp —
names the report too."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import commands, knowledge, store
from tests.test_commands import run


def prose(text: str) -> str:
    return " ".join(text.split())  # read as prose: a phrase may wrap


class TheBlockCarriesTheReflex(unittest.TestCase):
    def test_the_block_names_the_report_unasked_and_the_way_on(self):
        block = prose(knowledge.ONBOARDING_BLOCK)
        self.assertIn('`el feedback "…"`', block)
        self.assertIn("не спрашивая", block, "the permission is given before el speaks")
        self.assertIn("работай дальше обходом", block, "a report is a pause, not the end of the work")
        self.assertIn("в конце скажи владельцу", block, "the owner learns of it at the end")

    def test_the_block_names_the_reflex_not_the_form(self):
        for flag in ("--onboarding", "--actual", "--expected"):
            self.assertNotIn(flag, knowledge.ONBOARDING_BLOCK, "the form is the dose's, the block carries the habit")

    def test_the_doses_say_the_same(self):
        self.assertIn("No asking (the owner's word, 2026-10-06)", prose(knowledge.resolve("feedback")))
        self.assertIn("at the end tell the owner the report is there", prose(knowledge.resolve("feedback")))
        self.assertIn("the report reflex", prose(knowledge.resolve("onboarding")))
        self.assertIn("writes the report itself, at once and unasked", prose(knowledge.resolve("philosophy")))


class TheCommandSaysGoOn(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_FEEDBACK_DIR"] = str(Path(self.tmp.name) / "pool")

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_FEEDBACK_DIR", None)
        self.tmp.cleanup()

    def test_a_written_report_sends_the_agent_back_to_work(self):
        code, out, err = run("feedback", "done refuses a path", "--actual", "exit 2", "--expected", "accepted",
                             "--onboarding", "enough")
        self.assertEqual(code, 0, err)
        first, rest = out.split("feedback written: ", 1)[1].split("\n", 1)
        self.assertTrue(Path(first.strip()).is_file(), "the first line stays the path, whole")
        self.assertIn("go on by your workaround", rest)
        self.assertIn('el log PROBLEM "el: done refuses a path — workaround: …"', rest, "the next agent in the case is warned")
        self.assertIn("at the end tell the owner the report is there", rest)


class TheHandEditNamesTheReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_a_write_over_a_hand_edit_names_the_report(self):
        run("case", "new", "demo case", "--goal", "g")
        run("phase", "open", "1", "Start", "--goal", "g")
        case = next(Path(".cases").glob("*/"))
        todo = case / "TODO.md"
        todo.write_text(todo.read_text().replace("\n", " edited\n", 1))
        code, out, err = run("todo", "add", "1", "a step", "--expect", "[run: t → ok]")
        self.assertEqual(code, 0, err)
        self.assertIn("bypassing Elephant", err)
        self.assertIn('el feedback "…" — unasked, then go on', err, "the one moment el sees a workaround")

    def test_once_per_command_however_many_files_were_edited(self):
        out = commands.Outcome()
        for name in ("README.md", "TODO.md"):
            report = store.WriteReport(Path(name))
            report.bypassed = True
            out.absorb(report)
        self.assertEqual(out.warnings.count(commands.HAND_EDIT_REPORT), 1)

    def test_a_clean_write_says_nothing_of_it(self):
        run("case", "new", "demo case", "--goal", "g")
        code, out, err = run("phase", "open", "1", "Start", "--goal", "g")
        self.assertEqual(code, 0, err)
        self.assertNotIn("el feedback", err)


if __name__ == "__main__":
    unittest.main()
