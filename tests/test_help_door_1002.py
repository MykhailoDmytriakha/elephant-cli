"""Feedback of 2026-10-02 — help for an existing command does not route to its usage.

`el --help` lists `mv`; `el help mv` answered «no topic `mv`» with a recovery back to the topic list, while `el mv -h`
had the answer. A command with no dose of its own name now answers with its usage and the dose it lives in; a dose
wins over a usage (`el help todo` is still the dose); a name that is neither stays an error with the valid choices."""
import unittest

from elephant import knowledge, main
from tests.test_commands import run


class HelpForACommand(unittest.TestCase):
    def test_a_command_without_a_dose_answers_with_its_usage(self):
        code, out, err = run("help", "mv")
        self.assertEqual(code, 0, err)
        self.assertIn("usage: el mv [-h] old new", out)
        self.assertIn("`mv` is a command, not a knowledge dose — above is its usage (el mv -h); the dose it lives in: el help order", out)

    def test_every_command_name_resolves(self):
        parser = main.build_parser()
        subs = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
        for name in subs.choices:
            if name == "help":
                continue
            code, out, err = run("help", name)
            self.assertEqual(code, 0, f"el help {name}: {err}")
            self.assertTrue(out.strip(), name)

    def test_a_dose_wins_over_a_usage(self):
        code, out, _ = run("help", "todo")
        self.assertEqual(out.strip(), knowledge.TOPICS["todo"].strip())

    def test_an_unknown_name_stays_an_error_with_the_choices(self):
        code, _, err = run("help", "nosuch")
        self.assertEqual(code, 2)
        self.assertIn("no topic `nosuch` — topics: acceptance", err)

    def test_why_opens_the_philosophy(self):
        self.assertEqual(knowledge.resolve("why"), knowledge.TOPICS["philosophy"], "one alias, one dose")


if __name__ == "__main__":
    unittest.main()
