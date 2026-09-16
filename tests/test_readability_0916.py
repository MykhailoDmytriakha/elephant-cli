"""Two reports of 2026-09-16 15:18 from a live coding case (el 1.14.0), both about the reader who was not
in the session: (1) agents write omnibus files — two questions in one, a vague `summary:`, the answer
buried under the breakdown; (2) `todo done` accepted «Commit f3277f8149 removed marketSegment == HA check
and gutted update()» — a code trace where the owner wanted a plain answer. The tool cannot judge meaning;
it can teach at the moment of writing and it can see a token class: a commit hash or a call in the words
of `done` is a trace, and a trace is proof (ref: · file:), not the words."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "api", "--goal", "g")
        run("phase", "open", "1", "Analysis", "--goal", "a")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "docs").mkdir()
        (self.case / "docs" / "x.md").write_text("# X\nsummary: x\n", encoding="utf-8")
        run("todo", "add", "1", "why was the router disconnected")

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()


class OutcomeIsForTheOwner(Base):
    def test_a_code_trace_in_the_words_is_named_not_refused(self):
        code, out, err = run("todo", "done", "1.1", "file:docs/x.md", "Commit f3277f8149 (CSH merge) removed marketSegment == HA check and gutted update()")
        self.assertEqual(code, 0, err)
        self.assertIn("the words of done read like a code trace", err)
        self.assertIn("ref:f3277f8149", err, "the hash is a trace — it is proof, not the words")
        self.assertIn("what came out for the item, in the owner's words", err)
        self.assertIn("el help practice", err)

    def test_plain_words_pass_in_silence(self):
        code, out, err = run("todo", "done", "1.1", "ref:f3277f8149", "the router was disconnected on purpose in the CSH merge: the HA check is gone")
        self.assertEqual(code, 0, err)
        self.assertNotIn("code trace", err)
        code, out, err = run("todo", "add", "1", "count the 2024 items")
        code, out, err = run("todo", "done", "1.2", "owner", "12 items in 2024, 3 of them still open")
        self.assertNotIn("code trace", err, "numbers are not hashes")


class DosesTeachTheReader(Base):
    def test_files_where_todo_and_practice_carry_the_rule(self):
        files = knowledge.TOPICS["files"]
        self.assertIn("one question per file", files)
        self.assertIn("the answer first", files)
        self.assertIn("one question per file", knowledge.TOPICS["where"])
        todo = knowledge.TOPICS["todo"]
        self.assertIn("for the owner who was not in the session", todo)
        self.assertIn("commit hash", todo)
        practice = knowledge.TOPICS["practice"]
        self.assertIn("A DOCUMENT", practice)
        self.assertIn("gutted update()", practice, "the weak example is the one from the live case")


if __name__ == "__main__":
    unittest.main()
