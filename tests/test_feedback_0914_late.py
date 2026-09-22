"""Four reports of 2026-09-14 23:56 from a live coding case (el 1.6.0):
(1) bare `el` with no .cases/ printed the same refusal twice — once on stderr, once on stdout —
    and a terminal with 2>&1 showed two failures;
(2) root mode: the refusal on a present README.md did not offer the ordinary form, and a clean
    start did not say that the three files lie outside .cases/ where git sees them (the report's
    «writes without checking» was checked on the live repo: the refusal had fired — nothing was
    written; both halves about the messages stand);
(3) `el log` flattened an author's line breaks into one sentence and nothing said so;
(4) `file:` evidence resolved inside the case only — for software work the proof is the source
    file in the project, and forcing it into `ref` made ref mean «a path we could not check»."""
import os
import subprocess
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
        self.project = Path(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def case(self) -> Path:
        return next(p for p in (self.project / ".cases").iterdir() if p.is_dir())

    def read(self, name: str) -> str:
        return (self.case() / name).read_text(encoding="utf-8")


class OneVoice(Base):
    def test_bare_el_without_cases_prints_the_refusal_once(self):
        code, out, err = run()
        self.assertEqual(code, 4)
        self.assertEqual((out + err).count("no `.cases/` directory found"), 1)
        self.assertIn("start here", out)
        self.assertEqual(err, "", "the entry speaks on stdout; stderr stays for the other commands")

    def test_other_commands_still_refuse_on_stderr(self):
        code, out, err = run("case", "list")
        self.assertEqual(code, 4)
        self.assertIn("no `.cases/`", err)
        self.assertEqual(out, "")


class RootMode(Base):
    def test_a_present_readme_refuses_and_offers_the_ordinary_form(self):
        (self.project / "README.md").write_text("# the app\n", encoding="utf-8")
        code, out, err = run("case", "new", "--root", "my app", "--goal", "g")
        self.assertEqual(code, 4)
        self.assertIn("README.md already exists", err)
        self.assertIn('el case new "my app" --goal', err, "the ordinary form is offered")
        self.assertFalse((self.project / "TODO.md").exists())
        self.assertFalse((self.project / "JOURNAL.md").exists())
        self.assertEqual((self.project / "README.md").read_text(encoding="utf-8"), "# the app\n")

    def test_a_clean_start_names_the_files_outside_cases(self):
        code, out, err = run("case", "new", "--root", "my app", "--goal", "g")
        self.assertEqual(code, 0, err)
        self.assertIn("outside .cases/", out)
        self.assertIn(".gitignore", out)


class LineBreaks(Base):
    def setUp(self):
        super().setUp()
        run("case", "new", "demo", "--goal", "g")

    def test_an_author_line_break_is_a_body_line(self):
        code, out, err = run("log", "RESULT", "closed BUG-1\nroot: a\nfix: b")
        self.assertEqual(code, 0, err)
        self.assertIn("your line breaks are kept", err)
        self.assertIn("  RESULT · closed BUG-1 …\n    root: a\n    fix: b\n", self.read("JOURNAL.md"))
        self.assertIn("F7", err)

    def test_a_long_first_line_still_splits_and_the_rest_follow(self):
        code, out, err = run("log", "RESULT", ("long result " * 30) + "\nsecond field")
        self.assertEqual(code, 0, err)
        j = self.read("JOURNAL.md")
        self.assertIn("    second field\n", j)
        self.assertEqual(run("check")[0], 0)

    def test_more_than_five_lines_is_refused_with_the_phase_file_hint(self):
        code, out, err = run("log", "RESULT", "\n".join(f"l{i}" for i in range(1, 8)))
        self.assertEqual(code, 3)
        self.assertIn("phase file", err)
        self.assertNotIn("l1", self.read("JOURNAL.md"))

    def test_a_single_line_text_is_unchanged(self):
        code, out, err = run("log", "RESULT", "one line, no body")
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        self.assertIn("  RESULT · one line, no body\n", self.read("JOURNAL.md"))


class FileInTheProject(Base):
    def setUp(self):
        super().setUp()
        run("case", "new", "demo", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "w")
        (self.project / "src" / "app").mkdir(parents=True)
        (self.project / "src" / "app" / "parser.ts").write_text("export {}\n", encoding="utf-8")
        run("todo", "add", "1", "reuse the parser")
        run("todo", "add", "1", "another")

    def test_a_source_file_under_the_project_root_is_file_evidence(self):
        code, out, err = run("todo", "done", "1.1", "file:src/app/parser.ts", "reused the existing parser")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [x] 1.1 reuse the parser\n    - result: reused the existing parser\n      - file: [parser.ts](../../src/app/parser.ts)\n", self.read("TODO.md"))
        self.assertIn("RESULT · 1.1: file [parser.ts](../../src/app/parser.ts) — reused", self.read("JOURNAL.md"))
        self.assertEqual(run("check")[0], 0, "the link resolves from the case folder")

    def test_the_case_folder_still_wins_and_outside_still_refuses(self):
        (self.case() / "src").mkdir()
        (self.case() / "src" / "note.md").write_text("summary: x\n", encoding="utf-8")
        code, out, err = run("todo", "done", "1.1", "file:src/note.md", "case first")
        self.assertEqual(code, 0, err)
        self.assertIn("      - file: [note.md](src/note.md)", self.read("TODO.md"))
        self.assertEqual(run("todo", "done", "1.2", "file:../outside.ts", "x")[0], 2)
        self.assertEqual(run("todo", "done", "1.2", "file:src/app/missing.ts", "x")[0], 3)

    def test_a_ref_that_is_a_file_in_reach_gets_a_warning(self):
        code, out, err = run("todo", "done", "1.1", "ref:src/app/parser.ts", "hm")
        self.assertEqual(code, 0, err)
        self.assertIn("is a file in reach — file:src/app/parser.ts", err)
        code, out, err = run("todo", "done", "1.2", "ref:R000123-000001", "filed")
        self.assertEqual(err, "", "a real trace outside gets no warning")


if __name__ == "__main__":
    unittest.main()
