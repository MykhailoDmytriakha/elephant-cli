"""The owner's word, 2026-09-15, over a live transcript: an agent typed `el feedback` to learn the form
and got argparse's voice — `usage: el feedback [-h] … title` / `error: the following arguments are
required: title` — nothing about what to write, how, or what is valuable to the reader. The same
foreign voice answered eight of twelve commands on a bare call, while four (`readme set`, `case new`,
`phase close`, `todo edit`) spoke in el's voice: two voices for one class of failure.
Since 1.8.0 a wrong call is a StoreError(2) like every refusal: what is missing, the command's examples
from `el --help` (for `feedback` its whole dose), `el help <topic>`; stdout stays empty."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge, main
from tests.test_commands import run


class UsageVoice(unittest.TestCase):
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

    def test_bare_feedback_prints_the_whole_dose_not_argparse(self):
        code, out, err = run("feedback")
        self.assertEqual(code, 2)
        self.assertEqual(out, "", "a usage error is not the entry: nothing on stdout")
        self.assertIn("ERROR [exit 2]", err)
        self.assertIn("required: title", err, "what is missing is still named")
        self.assertFalse(err.startswith("usage:"), "the library's bare usage line is never the answer")
        for field in ("--actual", "--expected", "--repro", "--why", "--acceptance"):
            self.assertIn(field, err, f"the dose names {field} and what goes into it")
        self.assertIn("Valuable to the reader", err)
        self.assertIn("verbatim, with the exit code", err)
        self.assertIn("feedback/", err, "where the file lands")
        self.assertIn("travels with git", err, "how it reaches the owner")
        self.assertIn("recovery: el help feedback", err)
        self.assertIn("el help errors", err)
        self.assertFalse(self.pool.exists(), "nothing was written")

    def test_bare_log_shows_its_examples_and_topic(self):
        code, out, err = run("log")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ERROR [exit 2] el log: the following arguments are required: type, text", err)
        self.assertIn("examples:", err)
        self.assertIn('el log DECISION "chose X over Y because Z"', err)
        self.assertIn("recovery: el help journal · el log -h", err)

    def test_invalid_subaction_speaks_the_same_voice(self):
        code, out, err = run("todo", "bogus", "1.1")
        self.assertEqual(code, 2)
        self.assertIn("ERROR [exit 2] el todo: argument action: invalid choice: 'bogus'", err)
        self.assertIn("el todo done 2.4 file:evidence/receipt.pdf", err, "the todo examples follow")
        self.assertIn("recovery: el help todo · el todo -h", err)

    def test_every_command_with_a_topic_has_examples_or_a_dose(self):
        for cmd, topic in main.HELP_TOPIC.items():
            if cmd in ("status", "order", "check", "migrate"):  # no required arguments: a bare call runs
                continue
            self.assertIn(topic, knowledge.TOPICS, f"{cmd} points at a topic that exists")
            if cmd not in main.INLINE_DOSE:
                self.assertTrue(main.examples_for(cmd), f"`el --help` shows at least one `el {cmd}` example")

    def test_examples_for_done_does_not_catch_todo_done(self):
        lines = main.examples_for("done")
        self.assertTrue(lines)
        self.assertTrue(all("el done" in ln and not ln.startswith("el todo done") for ln in lines))

    def test_bad_int_and_unknown_topic_are_usage_errors_too(self):
        code, _, err = run("phase", "open", "x")
        self.assertEqual(code, 2)
        self.assertIn("ERROR [exit 2] el phase: argument n: invalid int value: 'x'", err)
        code, _, err = run("help", "nope")
        self.assertEqual(code, 2)
        self.assertIn("ERROR [exit 2] no topic `nope`", err)
        self.assertIn("journal", err, "the topics are listed")

    def test_help_and_version_are_untouched(self):
        with self.assertRaises(SystemExit) as ctx:
            run("feedback", "-h")
        self.assertEqual(ctx.exception.code, 0)
        with self.assertRaises(SystemExit) as ctx:
            run("--version")
        self.assertEqual(ctx.exception.code, 0)

    def test_help_topics_tell_the_truth(self):
        fb = knowledge.TOPICS["feedback"]
        self.assertIn("not even the case name", fb, "the header carries no case name (2026-09-22) — the help says so")
        self.assertNotIn("nothing from your environment is included", fb)
        self.assertIn("commit and", fb, "the file travels with git, the agent is told")
        self.assertIn("el log PROBLEM", fb, "the wall is recorded in the agent's own case")
        errors = knowledge.TOPICS["errors"]
        self.assertNotIn("mirrors them to stdout", errors, "since 1.7.0 the entry prints once, on stdout")
        self.assertIn("prints its refusal on stdout instead, once", errors)

    def test_a_well_formed_feedback_still_writes(self):
        code, out, err = run("feedback", "title here", "--actual", "a", "--expected", "b")
        self.assertEqual(code, 0, err)
        self.assertIn("feedback written:", out)
        self.assertEqual(len(list(self.pool.glob("*.md"))), 1)


if __name__ == "__main__":
    unittest.main()
