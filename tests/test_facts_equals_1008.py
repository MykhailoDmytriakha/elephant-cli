"""`el todo fact N.M =` keeps the result's words as the fact — one symbol (2026-10-08). The two questions that pointed at it
— at `done` when the words carried a number, and at the end of a session — were taken out the same day: the polygon
answered 0 of 7; agents keep many facts in a document, and the knowledge line on entry is what the next agent reads
(tests/test_knowledge_1008.py)."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class TheResultBecomesTheFact(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="done1008", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "probe", "--goal", "g")
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")
        for text in ("count the folders", "write the map"):
            run("todo", "add", "1", text, "--expect", "[run: probe → ok]")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_one_symbol_keeps_the_result_as_the_fact(self):
        run("todo", "done", "1.1", "run:ls → 114", "114 folders, 63 in the index")
        code, out, err = run("todo", "fact", "1.1", "=")
        self.assertEqual(code, 0, err)
        self.assertIn("fact 1.1 (established): «114 folders, 63 in the index»", out)

    def test_done_asks_no_question(self):
        code, out, _ = run("todo", "done", "1.1", "run:ls → 114", "114 folders, 63 in the index")
        self.assertNotIn("fact?", out)

    def test_the_end_of_a_session_asks_no_question(self):
        run("todo", "done", "1.1", "run:ls → 114", "114 folders")
        code, out, _ = run("readme", "set", "next", "go on")
        self.assertNotIn("without a fact", out)

    def test_equals_on_an_open_item_names_what_is_missing(self):
        code, _, err = run("todo", "fact", "1.2", "=")
        self.assertEqual(code, 4)
        self.assertIn("1.2 has no result yet", err)


if __name__ == "__main__":
    unittest.main()
