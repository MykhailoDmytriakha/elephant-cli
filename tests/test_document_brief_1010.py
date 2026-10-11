"""The brief for a document of the case (the polygon, 2026-10-09, accept-arms-1009): a live digest wrote a parked result
up as a shipped feature, and the brief that judged by the item's words caught it 1 time of 3 under a weakly worded item;
an acceptor that first wrote down from the sources what was closed caught it 3 of 3. «Re-run every run» on a document
sent acceptors re-running the sources' experiments. A markdown inside the case is now judged by deriving first."""
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
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="doer1010", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)
        run("case", "new", "overlap", "--goal", "hide the wait behind speech. Source: features/overlap/GOAL.md")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-overlap"))
        (self.case / "docs").mkdir()
        (self.case / "docs" / "digest.md").write_text("# Digest\nsummary: what was tried and closed\n", encoding="utf-8")
        run("phase", "open", "1", "Digest", "--goal", "the case's outcome [file: docs/digest.md]")
        run("phase", "agree", "1", "the owner agreed")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def brief(self, ref):
        os.environ["EL_SESSION"] = "accp1010"
        code, out, err = run("todo", "brief", ref)
        self.assertEqual(code, 0, err)
        return out


class ADocumentIsDerivedFirst(Base):
    def test_a_case_markdown_proof_brings_the_protocol(self):
        run("todo", "add", "1", "sum up the harness and the flag", "--expect", "[file: docs/digest.md]")
        run("todo", "done", "1.1", "file:docs/digest.md", "summed up")
        out = self.brief("1.1")
        self.assertIn("is a document written in the case: what it says is held to its sources", out)
        self.assertIn("BEFORE you open it, open its sources", out)
        self.assertIn("do not re-run their experiments", out)
        self.assertIn("«sources: N closed paths · document: M · missing: …»", out)
        self.assertNotIn("re-run every run you safely can", out)

    def test_other_proofs_beside_the_document_are_still_opened_and_re_run(self):
        run("todo", "add", "1", "sum up and test", "--expect", "[file: docs/digest.md] [run: tests]")
        run("todo", "done", "1.1", "file:docs/digest.md", "run:make test → 12 OK", "summed up")
        out = self.brief("1.1")
        self.assertIn("BEFORE you open it, open its sources", out)
        self.assertIn("5. The other proofs: open every file, re-run every run you safely can", out)
        self.assertIn('--run "make test → <what came out now>"', out)


class AThingIsJudgedAsBefore(Base):
    def test_a_run_proof_keeps_the_brief_it_had(self):
        run("todo", "add", "1", "make the parser pass", "--expect", "[run: tests]")
        run("todo", "done", "1.1", "run:make test → 12 OK", "passes")
        out = self.brief("1.1")
        self.assertIn("1. Open every file, re-run every run you safely can", out)
        self.assertNotIn("BEFORE you open it", out)

    def test_a_file_outside_the_case_is_a_thing_not_a_document(self):
        Path(self.tmp.name, "spec.md").write_text("# Spec\n", encoding="utf-8")
        run("todo", "add", "1", "write the spec", "--expect", "[file: spec]")
        run("todo", "done", "1.1", "file:../../spec.md", "written")
        out = self.brief("1.1")
        self.assertNotIn("BEFORE you open it", out)


class TheReview(Base):
    """The Codex review of batch 26, 2026-10-10."""

    def test_1_an_uppercase_md_is_a_document_too(self):
        (self.case / "docs" / "A.MD").write_text("# A\n", encoding="utf-8")
        run("todo", "add", "1", "sum up", "--expect", "[file: docs/A.MD]")
        run("todo", "done", "1.1", "file:docs/A.MD", "summed up")
        self.assertIn("BEFORE you open it, open its sources", self.brief("1.1"))

    def test_2_a_range_judges_each_item_by_its_own_kind_of_proof(self):
        run("todo", "add", "1", "sum up", "--expect", "[file: docs/digest.md]")
        run("todo", "add", "1", "make it fast", "--why", "p95 under 900 ms", "--expect", "[run: k6]")
        run("todo", "done", "1.1", "file:docs/digest.md", "summed up")
        run("todo", "done", "1.2", "run:k6 → p95 810 ms", "fast")
        out = self.brief("1.1-1.2")
        self.assertIn("How to judge 1.1 — ", out)
        self.assertIn("How to judge 1.2:", out)
        self.assertIn("2. Hold the result to `why`", out)


if __name__ == "__main__":
    unittest.main()
