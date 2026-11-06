"""The polygon run of 2026-11-06 (pm-haiku-14: Haiku, five fresh sessions, el 1.75.0) — what the agents met, and no one
reported.

1. An acceptor checked a file proof at version A and returned its verdict as text; the doer edited the file per the remark
   (version B); `accept` was refused «changed since done», its door said «the doer records it»; the doer recorded B and
   sent the same words in the same second — «accepted» for bytes no acceptor saw. A verdict holds for the version it was
   given for: the refusal says so, and el, which keeps the session's refused verdicts, refuses the same words for the item.
2. `readme add context "knowledge: [x](.cases/<case>/docs/x.md)"` — a link from the project root — answered «line added»,
   and the next `el check` called it a broken link. The write door reads a link as README does: from the case; a path from
   the project root is rewritten and said, a dead one is refused.
3. `readme drop context "knowledge:"` was refused «a position» with no positions; the agent counted by hand and dropped the
   good line. Words where a position goes: the section's lines with their numbers, and the command for the one they begin.
4. Order said «8 summary lines over 150 — four names … +4»; nothing named the other four, nor that two proofs were left out
   on purpose — the agent cut every summary by a script and changed two accepted proofs. `el order` names each file; the
   line says the proofs left out and why.
5. Four phases closed without the owner's agreed scope, with no trace; two later sessions read «waits for the owner: your
   scope» as a lock and told the owner «el will not let me close». No lock — a mark on the closed phase, an honest line.
6. Smaller walls: `el help case-new`, `el help topics`; «cannot close phase N:» with no reason on its line; `done 2.1` on an
   empty phase sent to `todo show`; the `added:` echo under `--case` rewrote «el order» in the item's words."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

ENVS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_THREAD_ID", "COPILOT_AGENT",
        "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "EL_MODEL", "EL_SESSION", "EL_HANDS_DIR", "EL_HINTS", "EL_TWO_HANDS",
        "EL_CASE", "EL_RECITE")
DOER = "doer1106"


class Base(unittest.TestCase):
    two_hands = "1"

    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS=self.two_hands, EL_RECITE="0", CLAUDECODE="1", EL_SESSION=DOER,
                          EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        self.ok("case", "new", "notes", "--goal", "the notes are written")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def ok(self, *argv):
        code, out, err = run(*argv)
        self.assertEqual(code, 0, f"{argv}: {out}{err}")
        return out, err

    def no(self, code, *argv):
        got, out, err = run(*argv)
        self.assertEqual(got, code, f"{argv}: {out}{err}")
        return out + err

    def case(self) -> Path:
        return next(Path(self.tmp.name, ".cases").glob("*-notes"))

    def read(self, name: str) -> str:
        return (self.case() / name).read_text(encoding="utf-8")

    def write(self, rel: str, text: str):
        p = self.case() / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


class AVerdictHoldsForItsVersion(Base):
    def setUp(self):
        super().setUp()
        self.ok("phase", "plan", "1", "Questions", "--goal", "the owner's questions [file: docs/questions.md]")
        self.ok("phase", "agree", "1", "write the questions")
        self.ok("phase", "open", "1")
        self.ok("todo", "add", "1", "write the owner's questions", "--expect", "[file: docs/questions.md]")
        self.write("docs/questions.md", "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n")
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "questions written")
        # the acceptor read version A and returned a remark; the doer edits the file by it — version B
        self.write("docs/questions.md", "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n"
                                        "2. keep the old archive?\n")

    VERDICT = "read the questions: both are open, each with its source"

    def test_the_refusal_says_the_verdict_does_not_carry(self):
        out = self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.assertIn("a verdict holds only for the version it was given for — it does not carry to the next", out)
        self.assertIn("then the acceptor checks #", out)
        self.assertIn("el todo brief 1.1", out)

    def test_the_same_words_for_the_next_version_are_refused(self):
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        out, _ = self.ok("todo", "done", "1.1", "file:docs/questions.md", "the second question added by the remark")
        self.assertIn("a verdict given for the old version does not carry to this one", out)
        out = self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.assertIn("1.1: these words were refused at", out)
        self.assertIn("the acceptor checks this version and says what it compared in it — el todo brief 1.1", out)
        self.assertNotIn("accepted:", self.read("TODO.md"), "nothing was accepted")
        self.assertRegex(out.strip().split("\n")[-1], r"el todo accept 1\.1 --by subagent")

    def test_words_about_this_version_pass(self):
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "the second question added by the remark")
        self.ok("todo", "accept", "1.1", "--by", "subagent", "re-read this version: two questions, the second one new")
        self.assertIn("accepted:", self.read("TODO.md"))

    def test_a_refused_range_is_kept_for_every_item(self):  # Codex, acceptance of 1.76.0: only the first was kept
        self.ok("todo", "add", "1", "write the second note", "--expect", "[file: docs/second.md]")
        self.write("docs/second.md", "# Second\nsummary: the second note\n\nA\n")
        self.ok("todo", "done", "1.2", "file:docs/second.md", "second written")
        self.write("docs/second.md", "# Second\nsummary: the second note\n\nB\n")
        words = "read both notes: each matches the question"
        self.no(4, "todo", "accept", "1.1-1.2", "--by", "subagent", words)
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "version B")
        self.ok("todo", "done", "1.2", "file:docs/second.md", "version B")
        out = self.no(4, "todo", "accept", "1.2", "--by", "subagent", words)
        self.assertIn("1.2: these words were refused at", out)

    def test_an_unchanged_item_of_a_refused_range_keeps_its_version(self):  # Codex, round 2: a mixed range
        self.ok("todo", "add", "1", "write the second note", "--expect", "[file: docs/second.md]")
        self.write("docs/second.md", "# Second\nsummary: the second note\n\nA\n")
        self.ok("todo", "done", "1.2", "file:docs/second.md", "second written")
        words = "read both notes: each matches the question"
        self.no(4, "todo", "accept", "1.1-1.2", "--by", "subagent", words)  # 1.1 changed, 1.2 stood on its version A
        self.write("docs/second.md", "# Second\nsummary: the second note\n\nB\n")
        self.ok("todo", "done", "1.2", "file:docs/second.md", "version B")
        out = self.no(4, "todo", "accept", "1.2", "--by", "subagent", words)
        self.assertIn("when it stood on docs/second.md #", out)

    def test_the_same_words_on_the_same_version_pass(self):  # the file put back to what was claimed: nothing carried
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.write("docs/questions.md", "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n")
        self.ok("todo", "accept", "1.1", "--by", "subagent", self.VERDICT)

    def test_two_files_that_swap_contents_are_another_version(self):  # Codex, round 3 of the acceptance of 1.76.0
        self.write("docs/questions.md", "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n")
        self.write("docs/other.md", "# Other\nsummary: the other note\n\nO\n")
        self.ok("todo", "done", "1.1", "file:docs/other.md", "the other note too")
        a, o = (self.case() / "docs/questions.md").read_text(), (self.case() / "docs/other.md").read_text()
        (self.case() / "docs/questions.md").write_text(a + "x\n")  # changed: the accept is refused on A, O
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        (self.case() / "docs/questions.md").write_text(o)
        (self.case() / "docs/other.md").write_text(a)
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "swapped")
        self.ok("todo", "done", "1.1", "file:docs/other.md", "swapped")
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)

    def test_a_file_put_back_after_two_refusals_passes(self):  # Codex, round 3: refused on A, then again on B, A restored
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "version B")
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)  # the old words on B: carried, not recorded
        self.write("docs/questions.md", "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n")
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "back to version A")
        self.ok("todo", "accept", "1.1", "--by", "subagent", self.VERDICT)

    def test_the_copy_door_keeps_the_verdict(self):  # the door the refusal offers: the proof moves to a copy of A
        a = "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n"
        self.write("docs/questions-v1.md", a)
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.ok("todo", "done", "1.1", "file:docs/questions-v1.md", "the version claimed, kept")
        self.ok("todo", "accept", "1.1", "--by", "subagent", self.VERDICT)

    def test_a_repeated_version_is_not_folded(self):  # Codex, round 4: A,A,B and A,B,B were one version
        a = "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n"
        self.write("docs/questions.md", a)
        self.write("docs/same.md", a)
        self.write("docs/b.md", "# B\nsummary: b\n\nB\n")
        self.ok("todo", "done", "1.1", "file:docs/same.md", "same text")
        self.ok("todo", "done", "1.1", "file:docs/b.md", "and b")
        (self.case() / "docs/b.md").write_text("# B\nsummary: b\n\nB2\n")
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)  # refused on A, A, B
        self.write("docs/same.md", "# B\nsummary: b\n\nB2\n")
        self.ok("todo", "done", "1.1", "file:docs/same.md", "now B2")
        self.ok("todo", "done", "1.1", "file:docs/b.md", "now B2")
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)  # A, B2, B2: same.md holds other bytes

    def test_el_mv_keeps_the_verdict(self):
        a = "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n"
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.write("docs/questions.md", a)
        self.ok("mv", "docs/questions.md", "docs/asked.md")
        self.ok("todo", "accept", "1.1", "--by", "subagent", self.VERDICT)

    def test_a_change_after_the_carry_does_not_make_the_old_words_new(self):  # Codex, round 5: A → B → C → B
        b = "# Questions\nsummary: what waits for the owner\n\n1. which model is the default?\n2. keep the old archive?\n"
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)  # given on A, the file is B
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "version B")
        self.write("docs/questions.md", b + "3. one more?\n")  # C, not recorded
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.write("docs/questions.md", b)  # back to B, the claim
        out = self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.assertIn("these words were refused at", out)

    def test_a_carried_range_keeps_the_words_for_its_fresh_item(self):  # Codex, round 6
        self.ok("todo", "add", "1", "write the second note", "--expect", "[file: docs/second.md]")
        self.write("docs/second.md", "# Second\nsummary: the second note\n\nA\n")
        self.ok("todo", "done", "1.2", "file:docs/second.md", "second written")
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)  # 1.1: given on A, the file is B
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "version B")
        self.no(4, "todo", "accept", "1.1-1.2", "--by", "subagent", self.VERDICT)  # carried for 1.1; new to 1.2 on its A
        self.write("docs/second.md", "# Second\nsummary: the second note\n\nB\n")
        self.ok("todo", "done", "1.2", "file:docs/second.md", "version B")
        self.no(4, "todo", "accept", "1.2", "--by", "subagent", self.VERDICT)

    def test_another_session_keeps_its_own_record(self):
        self.no(4, "todo", "accept", "1.1", "--by", "subagent", self.VERDICT)
        self.ok("todo", "done", "1.1", "file:docs/questions.md", "the second question added by the remark")
        os.environ["EL_SESSION"] = "fresh1106"  # a fresh session read the file as it is now: its verdict is its own
        self.ok("todo", "accept", "1.1", "--by", "codex", self.VERDICT)


class ReadmeReadsALinkFromTheCase(Base):
    two_hands = "0"

    def test_a_link_from_the_project_root_is_rewritten_to_the_case(self):
        self.write("docs/doors.md", "# Doors\nsummary: the closed paths\n")
        out, _ = self.ok("readme", "add", "context", f"knowledge: [doors.md](.cases/{self.case().name}/docs/doors.md)")
        self.assertIn(f"link .cases/{self.case().name}/docs/doors.md → docs/doors.md", out)
        self.assertIn("- knowledge: [doors.md](docs/doors.md)", self.read("README.md"))
        out, _ = self.ok("check")
        self.assertNotIn("F16", out)

    def test_a_project_file_from_the_root_is_written_from_the_case(self):
        Path(self.tmp.name, "src").mkdir()
        Path(self.tmp.name, "src", "app.py").write_text("x = 1\n", encoding="utf-8")
        self.ok("readme", "add", "decisions", "the parser lives in [app.py](src/app.py)")
        self.assertIn("[app.py](../../src/app.py)", self.read("README.md"))

    def test_a_dead_link_is_refused_and_nothing_is_written(self):
        before = self.read("README.md")
        out = self.no(4, "readme", "add", "context", "knowledge: [gone.md](docs/gone.md)")
        self.assertIn("README Context: the link → docs/gone.md leads nowhere", out)
        self.assertEqual(self.read("README.md"), before)
        self.no(4, "readme", "set", "next", "read [gone.md](docs/gone.md)")

    def test_a_dead_link_on_the_path_is_refused_too(self):  # Codex, acceptance of 1.76.0
        self.ok("readme", "add", "path", "Notes — note available")
        out = self.no(4, "readme", "edit", "path", "1", "Notes — read [gone](docs/gone.md)")
        self.assertIn("the link → docs/gone.md leads nowhere", out)
        self.no(4, "readme", "add", "path", "More — see [gone](docs/gone.md)")

    def test_a_path_line_named_by_its_words_gets_its_command(self):
        self.ok("readme", "add", "path", "Notes — note available")
        out = self.no(2, "readme", "edit", "path", "Notes", "Notes — corrected")
        self.assertEqual(out.strip().split("\n")[-1].strip(), 'el readme edit path 1 "Notes — corrected"')

    def test_a_name_in_backticks_is_still_a_link(self):  # Codex, round 2 of the acceptance of 1.76.0
        self.no(4, "readme", "add", "decisions", "see [`gone`](docs/gone.md)")
        self.write("docs/doors.md", "# Doors\nsummary: the closed paths\n")
        self.ok("readme", "add", "decisions", f"see [`doors`](.cases/{self.case().name}/docs/doors.md)")
        self.assertIn("see [`doors`](docs/doors.md)", self.read("README.md"))
        out, _ = self.ok("check")
        self.assertNotIn("F16", out)

    def test_relink_none_retires_a_link_whose_name_is_in_backticks(self):  # found on this case's own journal, 2026-11-06
        self.ok("log", "DECISION", "the example: [`gone`](docs/gone.md) was refused")
        out, _ = self.ok("order")
        self.assertIn("broken link(s): JOURNAL.md → docs/gone.md", out)
        out, _ = self.ok("relink", "docs/gone.md", "none")
        self.assertIn("1 link(s) now literal text", out)
        out, _ = self.ok("order")
        self.assertNotIn("broken link", out)

    def test_a_link_in_backticks_is_an_example(self):
        self.ok("readme", "add", "decisions", "links are written `[name](docs/x.md)`, from the case")


class WordsWhereAPositionGoes(Base):
    two_hands = "0"

    def setUp(self):
        super().setUp()
        self.write("docs/doors.md", "# Doors\nsummary: the closed paths\n")
        self.ok("readme", "add", "context", "rule: answers are cited")
        self.ok("readme", "add", "context", "knowledge: [doors.md](docs/doors.md)")

    def test_drop_by_words_lists_the_lines_and_names_the_one(self):
        out = self.no(2, "readme", "drop", "context", "knowledge:")
        self.assertIn("«knowledge:» begins line 2:", out)
        self.assertIn("  1 rule: answers are cited", out)
        self.assertEqual(out.strip().split("\n")[-1].strip(), "el readme drop context 2")
        self.assertIn("knowledge:", self.read("README.md"), "nothing dropped")

    def test_edit_by_words_carries_the_new_text(self):
        out = self.no(2, "readme", "edit", "context", "rule", "rule: every answer is cited")
        self.assertIn('el readme edit context 1 "rule: every answer is cited"', out)

    def test_words_that_begin_no_line_list_them_all(self):
        out = self.no(2, "readme", "drop", "decisions", "nothing")
        self.assertIn("el readme drop decisions <k>", out)


class OrderNamesEachFile(Base):
    two_hands = "0"

    def test_el_order_names_every_long_summary_and_the_entry_counts(self):
        long = "x" * 170
        for k in range(6):
            self.write(f"docs/d{k}.md", f"# d{k}\nsummary: {long}\n")
        self.ok("readme", "add", "links", "docs/ — the documents")
        out, _ = self.ok("order")
        line = next(ln for ln in out.split("\n") if "`summary:` line(s) over" in ln)
        self.assertTrue(all(f"docs/d{k}.md" in line for k in range(6)), line)
        self.assertIn("one by one", line)
        out, _ = self.ok()
        self.assertIn("… +2 (each named: el order)", out)

    def test_el_order_names_every_file_of_the_pairs(self):  # Codex, acceptance of 1.76.0: d4, d5 hid behind «+12»
        body = " ".join(f"word{i}" for i in range(80))
        for k in range(6):
            self.write(f"docs/d{k}.md", f"# d{k}\nsummary: the same report\n\n{body}\n")
        self.ok("readme", "add", "links", "docs/ — the documents")
        out, _ = self.ok("order")
        line = next(ln for ln in out.split("\n") if "pair(s) of files share text verbatim" in ln)
        self.assertTrue(all(f"docs/d{k}.md" in line for k in range(6)), line)
        self.assertIn("every file named with its strongest pair (6 files)", line)
        out, _ = self.ok()
        self.assertIn("(each file named: el order)", out)

    def test_a_proof_left_out_is_said(self):
        long = "y" * 170
        self.write("docs/a.md", f"# a\nsummary: {long}\n")
        self.write("docs/b.md", f"# b\nsummary: {long}\n")
        self.ok("readme", "add", "links", "docs/ — the documents")
        self.ok("phase", "open", "1", "Docs", "--goal", "the docs [file: docs/a.md]")
        self.ok("todo", "add", "1", "write a", "--expect", "[file: docs/a.md]")
        self.ok("todo", "done", "1.1", "file:docs/a.md", "a written")
        out, _ = self.ok("order")
        line = next(ln for ln in out.split("\n") if "`summary:` line(s) over" in ln)
        self.assertIn("docs/b.md", line)
        self.assertNotIn("docs/a.md", line)
        self.assertIn("1 more is a proof of done items with their version, left out on purpose — leave it", line)


class ScopeIsATraceNotALock(Base):
    def close_one(self, agree: bool):
        self.ok("phase", "plan", "1", "Work", "--goal", "the note [file: docs/n.md]")
        if agree:
            self.ok("phase", "agree", "1", "write it")
        self.ok("phase", "open", "1")
        self.ok("todo", "add", "1", "write the note", "--expect", "[file: docs/n.md]")
        self.write("docs/n.md", "# n\nsummary: the note\n")
        self.ok("todo", "done", "1.1", "file:docs/n.md", "written")
        os.environ["EL_SESSION"] = "fresh1106"
        self.ok("todo", "accept", "1.1", "--by", "codex", "opened the note: it is there")
        os.environ["EL_SESSION"] = DOER
        return self.ok("phase", "close", "1", "the note is written", "--reflect", "a lesson", "--align", "next")[0]

    def test_the_order_line_and_the_owner_line_say_no_lock(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the note [file: docs/n.md]")
        out, _ = self.ok("order")
        self.assertIn("no lock: the work goes on, and a close without it is marked «scope not agreed by the owner»", out)
        self.assertIn("(the work does not stop for it; a close without it is marked)", self.read("README.md"))

    def test_a_close_without_the_owners_scope_is_marked(self):
        out = self.close_one(agree=False)
        self.assertIn("scope not agreed by the owner — the line says it", out)
        line = next(ln for ln in self.read("TODO.md").split("\n") if ln.startswith("- [x] 1 "))
        self.assertIn("scope not agreed by the owner", line)

    def test_a_close_with_it_is_not(self):
        self.close_one(agree=True)
        self.assertNotIn("scope not agreed", self.read("TODO.md"))

    def test_the_ready_line_names_the_phases_closed_without_it(self):
        self.close_one(agree=False)
        self.ok("done", "the note is written", "--howto", "none: a single note")
        waits = next(ln for ln in self.read("README.md").split("\n") if ln.startswith("- waits for the owner:"))
        self.assertIn("phase 1 closed without your scope", waits)


class SmallerWalls(Base):
    two_hands = "0"

    def test_the_parent_brief_keeps_a_sub_items_fact(self):  # Codex, round 7: `el order works` became `el --case x order works`
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "does el order work?")
        self.ok("todo", "add", "1.1", "probe it")
        self.ok("--case", "notes", "todo", "done", "1.1.1", "run:el order → works", "works", "--fact", "el order works")
        self.ok("--case", "notes", "todo", "done", "1.1", "run:el order → works", "it works")
        out, _ = self.ok("--case", "notes", "todo", "brief", "1.1")
        self.assertIn("fact: el order works", out)
        self.assertNotIn("el --case notes order", out)

    def test_no_door_rewrites_the_agents_words_under_case(self):  # the class, after seven rounds of Codex finding one door each
        os.environ["EL_TWO_HANDS"] = "1"
        run_ = lambda *a: run("--case", "notes", *a)
        outs = []
        for argv in (("phase", "plan", "1", "Work", "--goal", "el order works [run: el order → ok]"),
                     ("phase", "agree", "1", "el order is the scope"), ("phase", "open", "1"),
                     ("todo", "add", "1", "el order names each", "--why", "el order why", "--expect", "[run: el order → ok]",
                      "--note", "el order note", "--fact", "el order fact"),
                     ("todo", "add", "1", "el order twice", "--expect", "[run: el order one] [run: el order two] [file: x.md]"),
                     ("todo", "done", "1.2", "run:el order one → ok", "run:el order two → ok", "two runs, no file"),
                     ("todo", "add", "1.1", "el order sub"), ("todo", "note", "1.1", "el order second note"),
                     ("todo", "done", "1.1.1", "run:el order → ok", "el order sub done", "--fact", "el order sub fact"),
                     ("todo", "done", "1.1", "run:el order → ok", "el order result"),
                     ("todo", "done", "1.1", "run:el order → ok", "el order result", "--fact", "el order fact"),
                     ("todo", "show", "1.1"), ("todo",), ("todo", "brief", "1.1"), ("facts",), (), ("order",), ("readme",),
                     ("todo", "add", "later", "el order later"), ("todo", "move", "L1", "1"),
                     ("todo", "hold", "1.3", "el order wait", "--check", "el order"), (), ("todo", "resume", "1.3"),
                     ("phase", "plan", "2", "Next", "--goal", "el order works later"),
                     ("phase", "plan", "2", "Next", "--goal", "el order works later, again"),  # round 9: the re-plan echo
                     ("todo", "add", "1", "el order third", "--due", "2030-01-01"), ("todo", "cancel", "1.4", "el order not needed"),
                     ("log", "DECISION", "el order decision"), ("readme", "add", "decisions", "el order line"),
                     ("readme", "set", "next", "el order next"), ()):
            code, out, err = run_(*argv)
            outs.append(f"{argv}: {out}{err}")
        os.environ["EL_SESSION"] = "fresh1106"
        for argv in (("todo", "reopen", "1.1", "--by", "codex", "--run", "el order → ok", "el order returned"),):
            code, out, err = run_(*argv)
            outs.append(f"{argv}: {out}{err}")
        os.environ["EL_SESSION"] = DOER
        code, out, err = run_("todo", "done", "1.1", "run:el order → ok", "el order again", "--fact", "confirmed")
        outs.append(out + err)
        os.environ["EL_SESSION"] = "fresh1106"
        code, out, err = run_("todo", "accept", "1.1", "--by", "codex", "--run", "el order → ok", "el order accepted")
        outs.append(out + err)
        bad = [o for o in outs if "el --case notes order" in o]
        self.assertEqual(bad, [], "\n\n".join(bad)[:3000])

    def test_a_door_el_composes_keeps_its_case_whatever_the_case_holds(self):  # Codex, round 10: the hint resumed case y
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "wait for the build", "--note", "after the wait: el todo resume 1.1")
        out, _ = self.ok("--case", "notes", "todo", "hold", "1.1", "the build runs")
        self.assertIn("el --case notes todo resume 1.1", out)
        out, _ = self.ok("--case", "notes")
        self.assertIn("el --case notes todo resume 1.1", out)

    def test_a_field_that_is_the_head_of_a_door_does_not_hold_it(self):  # Codex, round 11
        self.ok("phase", "open", "1", "Work", "--goal", "el order says 'yes'")
        self.ok("todo", "add", "1", "wait for the build", "--note", "el todo resume")
        out, _ = self.ok("--case", "notes", "todo", "hold", "1.1", "the build runs")
        self.assertIn("el --case notes todo resume 1.1", out)
        out, _ = self.ok("--case", "notes", "phase", "plan", "2", "Next", "--goal", "el order says 'yes', again")
        self.assertNotIn("el --case notes order says", out)
        self.ok("todo", "add", "1", "wait again", "--note", "it came → el todo resume 1.2")  # round 12: el's own hint, copied
        out, _ = self.ok("--case", "notes", "todo", "hold", "1.2", "waits")
        self.assertIn("it came → el --case notes todo resume 1.2", out)
        self.ok("todo", "add", "1", "and again", "--note",
                "el todo hold 1.3 \"…\" --check '…'; the entry's thread names the wait; it came → el todo resume 1.3")  # round 13
        out, _ = self.ok("--case", "notes", "todo", "hold", "1.3", "build runs")
        self.assertIn("el --case notes todo hold 1.3", out)
        self.assertIn("el --case notes todo resume 1.3", out)
        from elephant.main import _is_command
        self.assertTrue(_is_command("el todo resume 1.1"))
        self.assertFalse(_is_command("el order works"))

    def test_help_with_a_dashed_command_and_help_topics(self):
        out, _ = self.ok("help", "case-new")
        self.assertIn("el case new", out)
        out, _ = self.ok("help", "topics")
        self.assertIn("doses: ", out)

    def test_the_close_refusal_says_its_first_reason_on_the_first_line(self):
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "a step")
        out = self.no(4, "phase", "close", "1", "done")
        first = out.split("\n")[0]
        self.assertRegex(first, r"cannot close phase 1: \S")
        self.assertIn("more below", first)

    def test_done_on_an_empty_phase_points_to_add(self):
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        out = self.no(4, "todo", "done", "1.1", "run:\"x → ok\"", "done")
        self.assertIn("phase 1 has no items yet", out)
        self.assertIn("el todo add 1", out)

    def test_the_added_echo_keeps_the_words_under_case(self):
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        out, _ = self.ok("--case", "notes", "todo", "add", "1", "el order names each file")
        self.assertIn("added: 1.1 el order names each file", out)
        self.assertNotIn("el --case", out.split("\n")[0])
        out, _ = self.ok("--case", "notes", "todo", "done", "1.1", "run:el order → each file named", "el order lists them")
        self.assertIn("done: 1.1 el order names each file", out)
        self.assertIn("evidence: run el order → each file named", out)
        out, _ = self.ok("--case", "notes", "todo", "brief", "1.1")
        self.assertIn("item 1.1: el order names each file", out)
        self.assertIn("the doer says came out: el order lists them", out)
        self.assertIn("    - run: el order → each file named", out)  # the proof as recorded (Codex, acceptance of 1.76.0)
        self.ok("--case", "notes", "todo", "add", "1", "el order again")
        out, _ = self.ok("--case", "notes", "todo", "done", "1.1-1.2", "run:el order → every file", "both")
        self.assertIn("evidence: run el order → every file", out)  # a range's echo too (Codex, round 2)
        self.ok("--case", "notes", "todo", "add", "1", "a question")
        out, _ = self.ok("--case", "notes", "todo", "add", "1.3", "check «x» then el order")  # «» inside the words (round 3)
        self.assertIn("«check «x» then el order»", out)
        out, _ = self.ok("--case", "notes", "todo", "add", "later", "check «x» then el order")
        self.assertIn("«check «x» then el order»", out)
        self.assertIn("el --case notes todo move L1 N", out)  # the door el composed carries the case
        self.ok("--case", "notes", "todo", "done", "1.3.1", "run:el order → checked", "checked")
        out, _ = self.ok("--case", "notes", "todo", "brief", "1.3.1")
        self.assertNotIn("el --case notes order", out)  # the parent's and the sub-item's words as stored (round 4)
        self.ok("--case", "notes", "todo", "add", "1.3", "then el order «again»")
        out, _ = self.ok("--case", "notes", "todo", "cancel", "L1", "not needed")
        self.assertIn("«check «x» then el order»", out)
        self.ok("--case", "notes", "todo", "add", "later", "check «x «y»» then el order")  # two levels (round 5)
        out, _ = self.ok("--case", "notes", "todo", "cancel", "L2", "not needed")
        self.assertIn("«check «x «y»» then el order»", out)
        self.ok("--case", "notes", "todo", "add", "1.3", "probe el order", "--fact", "el order works")  # round 7
        self.ok("--case", "notes", "todo", "done", "1.3.3", "run:el order → works", "works", "--fact", "el order works")
        out, _ = self.ok("--case", "notes", "todo", "brief", "1.3.3")
        self.assertNotIn("el --case notes order works", out)
        out, _ = self.ok("--case", "notes", "facts")
        self.assertIn("el order works", out)
        self.assertNotIn("el --case notes order", out)
        from elephant.commands import carry_case
        self.assertEqual(carry_case("see «a «b «c»» el order» then el todo", "x"), "see «a «b «c»» el order» then el --case x todo")
        self.assertEqual(carry_case("an open « then el todo", "x"), "an open « then el --case x todo")
        self.assertEqual(carry_case('el todo add 1 "check «x» then el order"', "x"),
                         'el --case x todo add 1 "check «x» then el order"')  # whichever quote opens first (round 6)
        self.assertEqual(carry_case("«say \"el order\" here» el todo", "x"), "«say \"el order\" here» el --case x todo")


if __name__ == "__main__":
    unittest.main()
