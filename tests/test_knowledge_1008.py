"""The owner, 2026-10-08: «why not record links to these documents?». Agents keep what they found in a document — a
table of closed paths, a source on every row — never one fact per item (0 facts in 371 done; asked seven times, answered
zero). Measured the same day on the polygon: planning in a new case while the knowledge lay in a sibling case, a fresh
agent never opened it (0 of 2) and proposed closed paths again; with a line on the entry naming the document, it read it
at its third call (2 of 2). A `- knowledge: [name](path)` line in Context; the entry of every case names it."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="know1008", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "research", "--goal", "what was tried, in one place")
        self.research = next(Path(self.tmp.name, ".cases").glob("*-research"))
        (self.research / "docs").mkdir()
        (self.research / "docs" / "doors.md").write_text(
            "# Closed doors\nsummary: 12 closed paths, each with its source and when to reopen\n\n- beam search: slower\n",
            encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def mark(self):
        return run("--case", "research", "readme", "add", "context",
                   "knowledge: [doors.md](docs/doors.md) — closed paths with their sources")

    def head(self, out):
        return out.split("— the case on disk")[0]


class TheEntryOfEveryCaseNamesIt(Base):
    def test_a_new_case_sees_the_sibling_cases_document_with_the_read_command(self):
        code, _, err = self.mark()
        self.assertEqual(code, 0, err)
        run("case", "new", "speed", "--goal", "faster")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        line = next(ln for ln in self.head(out).split("\n") if ln.startswith("knowledge:"))
        self.assertIn("doors.md (", line)
        self.assertIn("closed paths with their sources", line)  # the case's words first, since 1.52.0
        self.assertTrue(line.endswith("read it: cat .cases/" + self.research.name + "/docs/doors.md"), line)

    def test_case_new_says_it_at_the_moment_the_task_starts(self):
        self.mark()
        code, out, _ = run("case", "new", "speed", "--goal", "faster")
        self.assertIn("knowledge: 1 document(s) of what this project already knows", out)

    def test_without_the_line_the_entry_is_silent(self):
        code, out, _ = run()
        self.assertNotIn("knowledge:", self.head(out))

    def test_a_closed_case_still_lends_its_knowledge(self):
        self.mark()
        run("--case", "research", "done", "every path written down")
        run("case", "new", "speed", "--goal", "faster")
        code, out, _ = run()
        self.assertIn("knowledge: 1 document(s)", self.head(out))

    def test_a_finished_project_names_its_knowledge_above_the_door(self):
        """pm-haiku-12: the case closed, three fresh sessions met «every case here is closed» — the entry refused before
        its head, and the knowledge line with it."""
        self.mark()
        run("--case", "research", "done", "every path written down")
        code, out, _ = run()
        self.assertEqual(code, 4)
        lines = out.rstrip("\n").split("\n")
        self.assertTrue(any(ln.strip().startswith("knowledge: 1 document(s)") for ln in lines), out)
        self.assertIn("recovery: el case list", lines[-1])

    def test_many_documents_name_three_and_count_the_rest(self):
        for i in range(4):
            (self.research / "docs" / f"k{i}.md").write_text(f"# k{i}\nsummary: part {i}\n", encoding="utf-8")
        links = " · ".join(f"[k{i}.md](docs/k{i}.md)" for i in range(4))
        run("--case", "research", "readme", "add", "context", f"knowledge: {links}")
        code, out, _ = run()
        line = next(ln for ln in self.head(out).split("\n") if ln.startswith("knowledge:"))
        self.assertIn("knowledge: 4 document(s)", line)
        self.assertIn("+1 more — el facts", line)

    def test_a_dead_link_is_an_order_line_and_never_named_as_knowledge(self):
        run("--case", "research", "readme", "add", "context", "knowledge: [gone.md](docs/gone.md)")
        code, out, _ = run()
        self.assertIn("broken link(s): README.md → docs/gone.md", out)  # like every README link (F16)
        self.assertNotIn("knowledge:", self.head(out).split("## Order")[0])


class FactsListsThem(Base):
    def test_el_facts_names_every_document(self):
        self.mark()
        run("case", "new", "speed", "--goal", "faster")
        code, out, err = run("facts")
        self.assertEqual(code, 0, err)
        self.assertIn("knowledge documents of the project (1)", out)
        self.assertIn("doors.md (" + self.research.name + ") — closed paths with their sources", out)  # the case's words, 1.52.0
        self.assertNotIn("no fact lines yet", out)


class ThePhaseCloseNamesTheDoor(Base):
    def close_a_phase(self):
        run("--case", "research", "phase", "open", "1", "Collect", "--goal", "paths written down")
        run("--case", "research", "todo", "add", "1", "write the doors", "--expect", "[file: docs/doors.md]")
        run("--case", "research", "todo", "done", "1.1", "file:docs/doors.md", "twelve paths written")
        run("--case", "research", "todo", "accept", "1.1", "--by", "owner", "good")
        return run("--case", "research", "phase", "close", "1", "written", "--reflect", "r", "--align", "a",
                   "--howto", "none: nothing caught")

    def test_documents_and_no_line_name_the_door_with_the_candidates(self):
        code, out, err = self.close_a_phase()
        self.assertEqual(code, 0, err)
        line = next(ln for ln in out.split("\n") if ln.startswith("knowledge: does a document"))
        self.assertIn('el readme add context "knowledge: [name](path) — what it holds"', line)
        self.assertIn("docs/doors.md", line)

    def test_a_case_that_named_its_knowledge_is_not_asked(self):
        self.mark()
        code, out, _ = self.close_a_phase()
        self.assertNotIn("knowledge: does a document", out)


if __name__ == "__main__":
    unittest.main()
