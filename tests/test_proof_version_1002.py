"""L8 — a file proof of the case carries the version it was done against (feedback 2026-10-02; the owner's word the same
day: «only the files of the case · a gate»).

A note was written, done with `file:docs/note.txt`, accepted by a fresh session — then its bytes were replaced by another
version. `todo show`, the entry, Order and `check` said nothing, and the phase was invited to close on content nobody
reviewed: the proof was a path, and a path is not the thing that was checked. `done` now writes a fingerprint of the
content on el's proof line (`· #1a2b3c4d`) for a file inside the case; in a phase not closed a proof whose file changed since
is said everywhere it is read, `accept` and `phase close` refuse over it, and two honest moves end it: a second `done`
records the new version (acceptance starts over) · `reopen`. el's own rewrites (`mv`, `relink`) carry the version along.
Files of the project (source code), el's own files and closed phases are left as they are."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from elephant import grammar
from tests.test_commands import run

DOER, REVIEWER = "doer1002", "reviewer1002"
FP_RE = re.compile(r"- file: \[note\.txt\]\(docs/note\.txt\) · #([0-9a-f]{8})$", re.M)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_TWO_HANDS"] = "1"
        self.as_(DOER)
        run("case", "new", "sample", "--goal", "Prepare a note")
        run("phase", "plan", "1", "Draft", "--goal", "Prepare a note [file: docs/note.txt]")
        run("phase", "agree", "1", "Prepare a note")
        run("phase", "open", "1", "Draft", "--goal", "Prepare a note [file: docs/note.txt]")
        run("todo", "add", "1", "Write the note", "--expect", "[file: docs/note.txt]")
        (self.case() / "docs").mkdir()
        self.write("Version A: approved content.\n")
        code, _, err = run("todo", "done", "1.1", "file:docs/note.txt", "Note written")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def as_(self, session: str):
        os.environ["EL_SESSION"] = session

    def case(self) -> Path:
        return next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def write(self, text: str, name: str = "docs/note.txt"):
        (self.case() / name).write_bytes(text.encode("utf-8"))

    def todo(self) -> str:
        return (self.case() / "TODO.md").read_text(encoding="utf-8")

    def accept(self):
        self.as_(REVIEWER)
        code, _, err = run("todo", "accept", "1.1", "--by", "subagent", "Read version A")
        self.as_(DOER)
        return code, err

    def entry(self) -> str:
        code, out, err = run()
        self.assertEqual(code, 0, err)
        return out


class DoneRecordsTheVersion(Base):
    def test_a_case_file_proof_carries_its_fingerprint(self):
        self.assertEqual(len(FP_RE.findall(self.todo())), 1, self.todo())
        item = grammar.parse_todo(self.todo()).phase(1).items[0]
        self.assertEqual(item.evidence[0][0], "file")

    def test_reading_changes_nothing(self):
        self.accept()
        before = self.todo()
        run("todo", "show", "1.1")
        run()
        run("check")
        self.assertEqual(self.todo(), before)
        self.assertNotIn("changed since done", self.entry())

    def test_a_project_file_carries_no_fingerprint(self):
        run("todo", "add", "1", "Patch the parser", "--expect", "[file: src/parser.py]")
        (Path(self.tmp.name) / "src").mkdir()
        (Path(self.tmp.name) / "src" / "parser.py").write_text("x = 1\n")
        code, _, err = run("todo", "done", "1.2", "file:src/parser.py", "parser patched")
        self.assertEqual(code, 0, err)
        line = next(ln for ln in self.todo().split("\n") if "parser.py" in ln and "- file:" in ln)
        self.assertNotIn(" · #", line, "source code lives on: its fixed version is a commit, its truth a run")

    def test_files_el_writes_itself_carry_no_version(self):
        # a phase file and the README of a nested case are rewritten by el on its own writes: a version on them would
        # read every write of el as a change of content (found by breaking `_versioned` on purpose, 2026-10-02)
        run("todo", "add", "1", "Draft the plan", "--expect", "[file: phases/1-draft.md]")
        code, _, err = run("todo", "done", "1.2", "file:phases/1-draft.md", "plan drafted")
        self.assertEqual(code, 0, err)
        run("spawn", "side", "--goal", "a side branch")
        code, _, err = run("--case", "side", "done", "the side branch ended")
        self.assertEqual(code, 0, err)
        lines = [ln for ln in self.todo().split("\n") if "- file:" in ln and ("1-draft.md" in ln or "README.md" in ln)]
        self.assertEqual(len(lines), 2, self.todo())
        self.assertFalse(any(" · #" in ln for ln in lines), lines)

    def test_line_endings_do_not_count_as_a_change(self):
        self.write("Version A: approved content.\r\n")
        self.assertNotIn("changed since done", self.entry())


class AChangedProofIsSaidEverywhere(Base):
    def setUp(self):
        super().setUp()
        code, err = self.accept()
        self.assertEqual(code, 0, err)
        self.write("Version B: different unreviewed content.\n")

    def test_show_names_the_change(self):
        code, out, err = run("todo", "show", "1.1")
        self.assertEqual(code, 0, err)
        self.assertRegex(out, r"docs/note\.txt changed since done \(#[0-9a-f]{8} → now #[0-9a-f]{8}\)")

    def test_the_entry_counts_it_and_order_names_both_moves(self):
        out = self.entry()
        acceptance = next(ln for ln in out.split("\n") if ln.startswith("acceptance: "))
        self.assertIn("1 on a version since changed", acceptance)
        order = out[out.index("## Order"):]
        self.assertIn("1.1 docs/note.txt changed since done", order)
        self.assertIn('el todo done 1.1 file:docs/note.txt "', order)
        self.assertIn('el todo reopen 1.1 "', order)

    def test_check_counts_it_in_the_running_phase(self):
        code, out, err = run("check")
        self.assertEqual(code, 3)
        self.assertIn("1.1 proof docs/note.txt changed since done", out + err)
        self.assertRegex(out + err, r"violations: [1-9]")

    def test_the_phase_does_not_close_on_it(self):
        code, _, err = run("phase", "close", "1", "note ready", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("1.1 proof docs/note.txt changed since done", err)

    def test_accept_refuses_a_version_the_doer_never_claimed(self):
        run("todo", "reopen", "1.1", "--by", "subagent", "B is not what was reviewed")
        self.write("Version A: approved content.\n")
        run("todo", "done", "1.1", "file:docs/note.txt", "Note written")
        self.write("Version C: changed after done.\n")
        code, err = self.accept()
        self.assertEqual(code, 4)
        self.assertIn("changed since done", err)

    def test_a_fact_on_it_is_under_question(self):
        run("todo", "fact", "1.1", "the note says A")
        code, out, _ = run("facts")
        self.assertIn("? 1.1", out)

    def test_a_new_done_records_the_version_and_acceptance_starts_over(self):
        code, out, err = run("todo", "done", "1.1", "file:docs/note.txt", "Version B: the note reworded")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(FP_RE.findall(self.todo())), 1, "one proof line for one file, with the new version")
        self.assertIn("[/] 1.1", self.todo(), "the acceptance was of the old bytes")
        self.assertIn("acceptance starts over", out)
        journal = (self.case() / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn("1.1: file [note.txt](docs/note.txt) · #", journal)
        self.assertIn("принято 1.1", journal, "the old verdict stays as history")
        self.assertNotIn("changed since done", self.entry())
        code, err = self.accept()
        self.assertEqual(code, 0, err)
        self.assertEqual(run("phase", "close", "1", "note ready", "--reflect", "r", "--align", "a")[0], 0)

    def test_a_new_done_needs_the_words_of_the_new_version(self):
        code, _, err = run("todo", "done", "1.1", "file:docs/note.txt")
        self.assertEqual(code, 2)
        self.assertIn("a new version of docs/note.txt", err)

    def test_reopen_ends_it_too(self):
        run("todo", "reopen", "1.1", "--by", "subagent", "B is not what was reviewed")
        self.assertNotIn("changed since done", self.entry())

    def test_deleted_and_recreated_with_other_bytes_is_still_changed(self):
        (self.case() / "docs" / "note.txt").unlink()
        self.write("Version D\n")
        self.assertIn("changed since done", self.entry())


class ElsOwnRewritesKeepTheVersion(Base):
    def setUp(self):
        super().setUp()
        self.accept()

    def test_mv_with_the_same_bytes_keeps_the_acceptance(self):
        code, _, err = run("mv", "docs/note.txt", "final/")
        self.assertEqual(code, 0, err)
        self.assertNotIn("changed since done", self.entry())
        self.assertIn("[x] 1.1", self.todo())

    def test_mv_rebasing_the_links_inside_a_document_keeps_its_version(self):
        self.write("See [the brief](brief.md) first.\n", "docs/report.md")
        self.write("brief\n", "docs/brief.md")
        run("todo", "add", "1", "Write the report", "--expect", "[file: docs/report.md]")
        run("todo", "done", "1.2", "file:docs/report.md", "Report written")
        self.accept_ref("1.2")
        code, _, err = run("mv", "docs/report.md", "final/report.md")  # its own link to brief.md is rebased
        self.assertEqual(code, 0, err)
        self.assertIn("../docs/brief.md", (self.case() / "final" / "report.md").read_text())
        self.assertNotIn("changed since done", self.entry())

    def test_an_author_change_before_mv_is_not_laundered(self):
        self.write("Version B\n")
        run("mv", "docs/note.txt", "final/")
        self.assertIn("changed since done", self.entry())

    def accept_ref(self, ref: str):
        self.as_(REVIEWER)
        code, _, err = run("todo", "accept", ref, "--by", "subagent", "read it")
        self.as_(DOER)
        self.assertEqual(code, 0, err)


class RootMode(unittest.TestCase):
    """The project folder is the case: «inside the case» is everywhere, so the line is the one el already draws there
    (L4): folders of a known kind and the folders Links lists are case content; source code is not."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_SESSION"] = DOER
        code, _, err = run("case", "new", "sample", "--goal", "g", "--root")
        self.assertEqual(code, 0, err)
        run("phase", "open", "1", "Draft", "--goal", "g [run: t → OK]")
        for d, name in (("docs", "note.txt"), ("src", "app.py"), ("drafts", "plan.txt")):
            (Path(self.tmp.name) / d).mkdir()
            (Path(self.tmp.name) / d / name).write_text("v1\n")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def proof_line(self, name: str) -> str:
        text = (Path(self.tmp.name) / "TODO.md").read_text(encoding="utf-8")
        return next(ln for ln in text.split("\n") if "- file:" in ln and name in ln)

    def test_content_folders_carry_a_version_code_does_not(self):
        run("readme", "add", "links", "drafts/ — the drafts of the plan")
        for k, path in enumerate(("docs/note.txt", "src/app.py", "drafts/plan.txt"), start=1):
            run("todo", "add", "1", f"step {k}", "--expect", "[run: t → OK]")
            code, _, err = run("todo", "done", f"1.{k}", f"file:{path}", "written")
            self.assertEqual(code, 0, err)
        self.assertIn(" · #", self.proof_line("note.txt"), "docs/ is a known kind of case content")
        self.assertNotIn(" · #", self.proof_line("app.py"), "source code is not case content")
        self.assertIn(" · #", self.proof_line("plan.txt"), "a folder Links lists is case content")


class HistoryIsLeftAsItIs(Base):
    def test_a_proof_without_a_fingerprint_is_read_as_before(self):
        text = self.todo()
        old = re.sub(r" · #[0-9a-f]{8}$", "", text.split("\nstamp:")[0], flags=re.M)
        from elephant import store
        store.write(self.case(), "TODO.md", old + "\n")  # a proof written before 1.35.0
        self.write("Version B\n")
        self.assertNotIn("changed since done", self.entry())
        self.assertEqual(run("check")[0], 0)

    def test_a_closed_phase_is_history(self):
        self.as_(REVIEWER)
        run("todo", "accept", "1.1", "--by", "subagent", "Read version A")
        self.as_(DOER)
        self.assertEqual(run("phase", "close", "1", "note ready", "--reflect", "r", "--align", "a")[0], 0)
        self.write("Version B\n")
        self.assertNotIn("changed since done", self.entry())


if __name__ == "__main__":
    unittest.main()


class BreaksFromAnotherEngine(Base):
    """Each test is a hole Codex found in the first version of L8 (an independent review, 2026-10-02)."""

    def setUp(self):
        super().setUp()
        self.accept()

    def test_a_range_mixing_open_and_done_items_renews_through_the_same_door(self):
        run("todo", "add", "1", "Send the note", "--expect", "[file: docs/note.txt]")
        self.write("Version B\n")
        code, out, err = run("todo", "done", "1.1-1.2", "file:docs/note.txt", "Version B sent")
        self.assertEqual(code, 0, err)
        item = grammar.parse_todo(self.todo()).phase(1).items[0]
        self.assertEqual(sum(1 for k, _ in item.evidence if k == "file"), 1, "one line per file, not A beside B")
        self.assertIn("[/] 1.1", self.todo(), "the acceptance was of A")
        self.assertIn("acceptance starts over", out)
        self.assertNotIn("changed since done", self.entry())

    def test_a_proof_without_a_version_never_erases_one(self):
        from elephant import commands
        case = self.case()
        todo = grammar.parse_todo(self.todo())
        item = todo.phase(1).items[0]
        self.write("Version B\n")
        renewed = commands._merge_proofs(case, item, [("file", "[note.txt](docs/note.txt)")])
        self.assertIsNotNone(renewed, "B is a new version even when the new proof came without one")
        self.assertRegex(item.evidence[0][1], r" · #[0-9a-f]{8}$")

    def test_el_s_own_files_are_found_by_place_not_by_name(self):
        from elephant import commands
        case = self.case()
        (case / "docs" / "README.md").write_text("a document called README\n")
        self.assertFalse(commands._el_writes(case, case / "docs" / "README.md"), "an author's README in docs/ is tracked")
        self.assertTrue(commands._el_writes(case, case / "journal.md"), "a legacy spelling is still el's file")
        run("spawn", "side", "--goal", "g")
        child = next(d for d in case.iterdir() if d.is_dir() and d.name.endswith("side"))
        self.assertTrue(commands._el_writes(case, child / "README.md"))
        self.assertTrue(commands._el_writes(case, child / "phases" / "1-build.md"), "a nested case's phase file is el's")

    def test_relink_carries_the_version_of_a_file_renamed_outside_el(self):
        # relink rewrites links in markdown only: a report that links to itself is the case it must carry
        self.write("# Report\n\nSee [this report](report.md).\n", "docs/report.md")
        run("todo", "add", "1", "Write the report", "--expect", "[file: docs/report.md]")
        run("todo", "done", "1.2", "file:docs/report.md", "the report links itself")
        self.as_(REVIEWER)
        run("todo", "accept", "1.2", "--by", "subagent", "read it")
        self.as_(DOER)
        (self.case() / "docs" / "report.md").rename(self.case() / "docs" / "final.md")
        code, _, err = run("relink", "docs/report.md", "docs/final.md")
        self.assertEqual(code, 0, err)
        self.assertIn("(final.md)", (self.case() / "docs" / "final.md").read_text(), "el rewrote the bytes itself")
        self.assertNotIn("changed since done", self.entry())

    def test_a_rewrite_inside_a_nested_case_carries_the_parent_s_version(self):
        run("spawn", "side", "--goal", "a side branch")
        child = next(d for d in self.case().iterdir() if d.is_dir() and d.name.endswith("side"))
        (child / "docs").mkdir()
        (child / "docs" / "a.txt").write_text("annex\n")
        (child / "docs" / "report.md").write_text("# Report\n\nSee [the annex](a.txt).\n")
        parent = self.case().name  # spawn handed the session to the child
        run("--case", parent, "todo", "add", "1", "Read the side report", "--expect", f"[file: {child.name}/docs/report.md]")
        code, _, err = run("--case", parent, "todo", "done", "1.2", f"file:{child.name}/docs/report.md", "the side report read")
        self.assertEqual(code, 0, err)
        code, _, err = run("--case", "side", "mv", "docs/a.txt", "docs/b.txt")  # rebases the report's link
        self.assertEqual(code, 0, err)
        self.assertIn("(b.txt)", (child / "docs" / "report.md").read_text())
        self.assertRegex(self.todo(), r"report\.md\) · #[0-9a-f]{8}")
        self.assertNotIn("changed since done", run("--case", parent)[1])

    def test_order_adopt_writing_a_summary_is_not_a_change(self):
        self.write("# Report\n\nThe body.\n", "docs/report.md")
        run("readme", "add", "links", "docs/report.md — what the report says")
        run("todo", "add", "1", "Write the report", "--expect", "[file: docs/report.md]")
        run("todo", "done", "1.2", "file:docs/report.md", "report written")
        code, _, err = run("order", "--adopt")
        self.assertEqual(code, 0, err)
        self.assertIn("summary:", (self.case() / "docs" / "report.md").read_text())
        self.assertNotIn("changed since done", self.entry())

    def test_an_unreadable_proof_is_said_not_crashed(self):
        f = self.case() / "docs" / "note.txt"
        f.chmod(0)
        try:
            code, out, err = run()
            self.assertEqual(code, 0, err)
            self.assertIn("now unreadable", out)
        finally:
            f.chmod(0o644)

    def test_the_tally_counts_items_not_files(self):
        self.write("annex v1\n", "docs/annex.txt")
        run("todo", "done", "1.1", "file:docs/annex.txt", "the annex joins")
        self.accept()
        self.write("Version B\n")
        self.write("annex v2\n", "docs/annex.txt")
        line = next(ln for ln in self.entry().split("\n") if ln.startswith("acceptance: "))
        self.assertIn("1 on a version since changed", line)

    def test_a_planned_phase_is_read_by_every_reader_alike(self):
        run("phase", "plan", "2", "Later work", "--goal", "g [file: docs/plan.txt]")
        run("todo", "add", "2", "Draft the plan", "--expect", "[file: docs/plan.txt]")
        self.write("plan v1\n", "docs/plan.txt")
        run("todo", "done", "2.1", "file:docs/plan.txt", "plan drafted ahead of turn")
        self.write("plan v2\n", "docs/plan.txt")
        self.assertIn("2.1 docs/plan.txt changed since done", self.entry(), "the entry sees what show and accept see")


class DigestKeepsOtherKinds(unittest.TestCase):
    def test_only_a_file_proof_loses_its_version_in_the_count(self):
        from elephant import commands
        self.assertEqual(grammar.split_fingerprint("verify → result · #12345678"), ("verify → result", "12345678"))
        src = open(commands.__file__, encoding="utf-8").read()
        self.assertIn('grammar.split_fingerprint(pr)[0] if k == "file" else pr', src)
