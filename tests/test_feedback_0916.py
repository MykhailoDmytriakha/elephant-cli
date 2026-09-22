"""Four reports of 2026-09-16 12:15 from a live coding case (el 1.10.0):
(1) `el help phase` — a wall: the topic is `phases`; the door now takes singular forms and the common
    words of the craft, the list of doses stays closed;
(2) `el mv .cases/<case>/file.png evidence/` — tab completion from the repo root spells the case folder
    out and mv refused a valid file; paths are normalised to the case (repo-relative, absolute);
(3) `phase close` took three round trips: `--reflect` / `--align` log the two DECISIONs in the same
    command — same events, same gates, nothing logged if another gate refuses;
(4) a 151-char outcome aborted a chain with exit 3: the `result:` line is el's and is shortened like
    `closed:`, the journal keeps the words whole; the 100 on the item text stands (the owner's word)."""
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
        self.root = Path(self.tmp.name) / ".cases"
        run("case", "new", "api", "--goal", "g")
        run("phase", "open", "1", "Analysis", "--goal", "a")
        self.case = next(p for p in self.root.iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class HelpTakesTheWordsInTheHead(Base):
    def test_singular_and_common_words_resolve_unknown_still_refused(self):
        for word, topic in (("phase", "phases"), ("case", "cases"), ("file", "files"), ("limit", "limits"), ("item", "todo"),
                            ("proof", "evidence"), ("hint", "practice"), ("PHASE", "phases"), ("problem", "journal")):
            code, out, err = run("help", word)
            self.assertEqual(code, 0, f"{word}: {err}")
            self.assertEqual(out.strip(), knowledge.TOPICS[topic].strip(), word)
        code, out, err = run("help", "nope")
        self.assertEqual(code, 2)
        self.assertIn("no topic `nope`", err)
        code, out, _ = run("help")
        self.assertIn("singular forms and common words work too", out)


class MvTakesRepoRelativePaths(Base):
    def setUp(self):
        super().setUp()
        (self.case / "image.png").write_bytes(b"\x89PNG")
        (self.case / "docs").mkdir()
        (self.case / "docs" / "a.md").write_text("# A\nsummary: a\n", encoding="utf-8")
        run("readme", "add", "links", "[a](docs/a.md) — the doc")

    def test_case_folder_spelled_out_and_absolute_paths(self):
        code, out, err = run("mv", f".cases/{self.case.name}/image.png", "evidence/image.png")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.case / "evidence" / "image.png").is_file())
        code, out, err = run("mv", str(self.case / "docs" / "a.md"), f".cases/{self.case.name}/docs/notes/")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.case / "docs" / "notes" / "a.md").is_file())
        readme = self.read("README.md")
        self.assertIn("(docs/notes/a.md)", readme, "the link followed")
        self.assertNotIn("(docs/a.md)", readme)
        code, out, err = run("mv", "nope.png", "evidence/")
        self.assertEqual(code, 4)
        self.assertIn(".cases/<case>/… and absolute paths inside the case are accepted too", err)
        (self.case / "docs" / "notes" / "a.md").rename(self.case / "docs" / "b.md")
        code, out, err = run("relink", f".cases/{self.case.name}/docs/notes/a.md", f".cases/{self.case.name}/docs/b.md")
        self.assertEqual(code, 0, err)
        self.assertIn("(docs/b.md)", self.read("README.md"), "relink took the repo-relative forms too")


class PhaseCloseInOneCommand(Base):
    def setUp(self):
        super().setUp()
        run("todo", "add", "1", "read the repo")
        run("todo", "add", "1", "map the endpoints")

    def test_flags_log_the_two_decisions_and_close(self):
        run("todo", "done", "1.1", "owner", "read")
        run("todo", "done", "1.2", "owner", "mapped")
        code, out, err = run("phase", "close", "1", "mapped", "--reflect", "read the README first", "--align", "phase 2 starts from the endpoints")
        self.assertEqual(code, 0, err)
        j = self.read("JOURNAL.md")
        self.assertIn("DECISION · reflect: read the README first", j)
        self.assertIn("DECISION · align: phase 2 starts from the endpoints", j)
        self.assertIn("PHASE · Analysis закрыта → mapped", j)
        self.assertIn("- [x] 1 Analysis — mapped ·", self.read("TODO.md"))
        self.assertIn("- reflect: read the README first\n- align: phase 2 starts from the endpoints\n", self.read("phases/1-analysis.md"))

    def test_nothing_is_logged_when_another_gate_refuses(self):
        run("todo", "done", "1.1", "owner", "read")
        code, out, err = run("phase", "close", "1", "mapped", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("open items 1.2", err)
        self.assertNotIn("reflect: r", self.read("JOURNAL.md"), "atomic: a refused close logs nothing")
        run("todo", "done", "1.2", "owner", "mapped")
        code, out, err = run("phase", "close", "1", "mapped", "--reflect", "r")
        self.assertEqual(code, 4, "align is still a gate")
        self.assertIn("no `DECISION · align:", err)
        self.assertIn("--align", err, "the refusal names the one-command form")
        self.assertNotIn("reflect: r", self.read("JOURNAL.md"))
        code, out, err = run("phase", "close", "1", "mapped", "--reflect", "reflect: r", "--align", "a")
        self.assertEqual(code, 2)
        self.assertIn("el writes the `reflect:` prefix", err)


class LongOutcomeIsShortenedNotRefused(Base):
    def test_result_line_shortened_journal_whole_item_limit_stands(self):
        run("todo", "add", "1", "x")
        long = "о" * 151
        code, out, err = run("todo", "done", "1.1", "owner", long)
        self.assertEqual(code, 0, err)
        self.assertIn("result: line shortened to 150 chars in TODO (F22, el's line) — the whole outcome is in the journal RESULT", out)
        todo = self.read("TODO.md")
        self.assertIn("    - result: " + "о" * 149 + "…\n", todo)
        self.assertIn(long, self.read("JOURNAL.md"))
        self.assertEqual(run("check")[0], 0)
        code, out, err = run("todo", "add", "1", "Identify Partner Pricing Disc API APP00000001 architecture, endpoints, repos, ownership, and contracts")
        self.assertEqual(code, 3, "102 chars: the item text is the agent's — rephrased, not trimmed by el (the owner's word)")
        self.assertIn("rephrase, do not truncate", err)


if __name__ == "__main__":
    unittest.main()
