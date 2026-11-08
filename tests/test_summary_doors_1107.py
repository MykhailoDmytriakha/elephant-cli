"""A report from the pool, 2026-11-07: Order said «evidence/root-cause.md without summary → add summary line 2, or order
--adopt»; `el order --adopt` answered «nothing to adopt: every described file already carries its own summary», and Order
still named the file. --adopt writes only what README Links describes — the line offered it to a file Links never
described. And the other door of the same line asked a proof of a done item with its version to edit line 2 by hand:
the edit changes the version an acceptance stands on.

Each file of the line gets the door that fixes it; --adopt says what it skipped and why."""
import shlex
import unittest
from pathlib import Path

from tests.test_commands import run
from tests.test_long_case_1105 import Base


class EachFileGetsTheDoorThatFixesIt(Base):
    def setUp(self):
        super().setUp()
        for rel, title in (("evidence/root-cause.md", "Root cause"), ("notes/plan.md", "Plan"), ("notes/log.md", "Log")):
            p = self.case() / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {title}\n\nThe body.\n", encoding="utf-8")

    def summary_line(self, out: str) -> str:
        return next(ln for ln in out.splitlines() if "without `summary:`" in ln and ln.startswith("- "))

    def test_the_report_adopt_is_not_offered_to_a_file_links_never_described(self):
        out, _ = self.ok("order")
        line = self.summary_line(out)
        self.assertIn("evidence/root-cause.md", line)
        self.assertNotIn("--adopt", line)
        out, _ = self.ok("order", "--adopt")
        self.assertIn("nothing to adopt: README Links has no description for the 3 file(s)", out)
        self.assertNotIn("every described file already carries", out)

    def test_adopt_is_offered_only_for_what_links_describes(self):
        self.ok("readme", "add", "links", "notes/plan.md — how the coins are counted")
        line = self.summary_line(self.ok("order")[0])
        self.assertIn("notes/plan.md → el order --adopt", line)
        self.assertIn("notes/log.md", line.split("→ el order --adopt")[0])  # the other files: line 2 by hand
        out, _ = self.ok("order", "--adopt")
        self.assertIn("summary written into notes/plan.md", out)
        self.assertIn("still without `summary:` — evidence/root-cause.md, notes/log.md", out)
        self.assertNotIn("--adopt", self.summary_line(out))  # what is left has no description to adopt

    def test_a_proof_with_its_version_is_not_asked_to_edit_line_2_by_hand(self):
        self.ok("phase", "open", "1", "Count", "--goal", "the drift is found [file: root cause]")
        self.ok("todo", "add", "1", "find why the scale drifts", "--expect", "[file: root cause]")
        self.ok("todo", "done", "1.1", "file:evidence/root-cause.md", "the scale drifts by heat")
        line = self.summary_line(self.ok("order")[0])
        proof = line.split("; ")[-1]
        self.assertTrue(proof.startswith("evidence/root-cause.md — a proof of a done item with its version"), line)
        door = proof.split("keeps the version: ", 1)[1]
        argv = shlex.split(door)
        self.assertEqual(argv[:4], ["el", "readme", "add", "links"])
        self.ok(*argv[1:4], "evidence/root-cause.md — why the scale drifts")  # the printed door, with the agent's words
        out, _ = self.ok("order", "--adopt")
        self.assertIn("summary written into evidence/root-cause.md", out)
        self.assertEqual(self.read("evidence/root-cause.md").split("\n")[1], "summary: why the scale drifts")
        self.assertNotIn("changed since done", self.ok("todo", "show", "1.1")[0])  # the version moved with el's own line
        self.assertNotIn("evidence/root-cause.md", self.summary_line(out))

    def test_a_proof_of_a_closed_phase_is_history_adopt_leaves_it(self):  # Codex, 2026-11-07: --adopt wrote line 2 into
        # a closed phase's proof, the phase file kept the old version, Order went quiet and check said nothing
        self.ok("phase", "open", "1", "Count", "--goal", "the drift is found [file: root cause]")
        self.ok("todo", "add", "1", "find why the scale drifts", "--expect", "[file: root cause]")
        self.ok("todo", "done", "1.1", "file:evidence/root-cause.md", "the scale drifts by heat")
        self.ok("phase", "close", "1", "the drift is found", "--howto", "none: a test")
        before = self.read("evidence/root-cause.md")
        line = self.summary_line(self.ok("order")[0])
        self.assertTrue(line.startswith("- 2 file(s) without `summary:`"), line)  # the two notes; the proof is not counted
        self.assertIn("1 more is a proof of a closed phase with its version, left out on purpose", line)
        self.assertNotIn("evidence/root-cause.md", line)
        self.ok("readme", "add", "links", "evidence/root-cause.md — why the scale drifts")
        self.assertNotIn("evidence/root-cause.md", self.summary_line(self.ok("order")[0]))  # no --adopt door for it
        out, _ = self.ok("order", "--adopt")
        self.assertIn("nothing to adopt: left as it is: evidence/root-cause.md — a proof of a closed phase", out)
        self.assertEqual(self.read("evidence/root-cause.md"), before)  # the bytes its acceptance stood on
        self.ok("--case", "shop", "check")
        for rel in ("notes/plan.md", "notes/log.md"):
            p = self.case() / rel
            p.write_text(p.read_text().replace("\n\n", "\nsummary: a line\n\n", 1))
        self.assertNotIn("without `summary:`", self.ok("order")[0])  # history alone puts no line in Order
        out, _ = self.ok("order", "--adopt")
        self.assertNotIn("every file carries its own summary", out)  # it does not: the proof has none, said as kept
        self.assertIn("left as it is: evidence/root-cause.md", out)

    def test_a_running_proof_inside_a_nested_case_is_held_for_the_parent_too(self):
        self.ok("phase", "open", "1", "Count", "--goal", "the side report is read [file: report]")
        self.ok("spawn", "side", "--goal", "a side branch")
        child = next(d for d in self.case().iterdir() if d.is_dir() and d.name.endswith("-side"))
        (child / "docs").mkdir()
        (child / "docs" / "report.md").write_text("# Report\n\nThe body.\n", encoding="utf-8")
        shop = self.case().name
        self.ok("--case", shop, "todo", "add", "1", "read the side report", "--expect", "[file: report]")
        self.ok("--case", shop, "todo", "done", "1.1", f"file:{child.name}/docs/report.md", "the side report read")
        line = self.summary_line(self.ok("--case", "side", "order")[0])
        self.assertIn("docs/report.md — a proof of a done item with its version", line)  # the parent's proof, not «by hand»
        self.ok("--case", "side", "readme", "add", "links", "docs/report.md — what the side found")
        out, _ = self.ok("--case", "side", "order", "--adopt")
        self.assertIn("summary written into docs/report.md", out)
        self.assertNotIn("changed since done", self.ok("--case", shop, "todo", "show", "1.1")[0])

    def test_a_door_for_a_name_with_quotes_runs_as_printed(self):  # Codex, 2026-11-07, round 2: `evidence/scale "heat".md`
        # in a door printed in double quotes came back from the shell as another path — Links described nothing real
        names = ('evidence/scale "heat".md', "evidence/it's (x).md", "evidence/a b.md")
        for rel in names:
            (self.case() / rel).write_text("# T\n\nThe body.\n", encoding="utf-8")
        weird = self.case() / "it's (old)"
        weird.mkdir()
        (weird / "n.md").write_text("# N\nsummary: a line\n", encoding="utf-8")
        self.ok("phase", "open", "1", "Count", "--goal", "the drift is found [file: root cause]")
        self.ok("todo", "add", "1", "find why the scale drifts", "--expect", "[file: root cause]")
        self.ok("todo", "done", "1.1", *(f"file:{rel}" for rel in names), "the scale drifts by heat")
        out, _ = self.ok("order")
        unref = next(ln for ln in out.splitlines() if "nothing in the work points at" in ln)
        for rel in names:
            self.assertNotIn(rel, unref)  # el's own proof links are references (F21)
        folder = next(ln for ln in out.splitlines() if ln.startswith("- folder it's (old)/"))
        self.ok(*shlex.split(folder.split(" → ", 1)[1])[1:])
        self.assertNotIn("folder it's (old)/", self.ok("order")[0])
        for _ in names:
            line = self.summary_line(self.ok("order")[0])
            door = line.split("keeps the version: ", 1)[1]
            self.ok(*shlex.split(door)[1:])  # as an agent runs it
        self.assertNotIn("keeps the version", self.summary_line(self.ok("order")[0]))  # each one is described in Links now
        out, _ = self.ok("order", "--adopt")
        for rel in names:
            self.assertIn(f"summary written into {rel}", out)
            self.assertEqual(self.read(rel).split("\n")[1], "summary: что это")
        self.assertNotIn("changed since done", self.ok("todo", "show", "1.1")[0])

    def test_a_folder_no_links_line_can_name_gets_no_door_that_fails(self):  # Codex, 2026-11-07, round 3: `two  spaces/`
        # — the printed door was refused by the write door (a double space reads as a trace of a shell substitution)
        weird = self.case() / "two  spaces"
        weird.mkdir()
        (weird / "n.md").write_text("# N\nsummary: a line\n", encoding="utf-8")
        line = next(ln for ln in self.ok("order")[0].splitlines() if ln.startswith("- folder two  spaces/"))
        self.assertNotIn("el readme add links", line)
        self.assertIn("rename the folder to a plain name", line)
        code, out, err = run("readme", "add", "links", "two  spaces/ — что здесь")
        self.assertEqual(code, 2, out + err)  # why no door is printed: the write door refuses every line naming it

    def test_a_proof_no_links_line_can_name_is_left_aside_not_sent_to_a_breaking_door(self):  # Codex, 2026-11-07, round 4:
        # «el mv it to a plain name first» lost the proof — mv from such a name did not find el's own link to it
        self.ok("phase", "open", "1", "Count", "--goal", "the drift is found [file: root cause]")
        odd = ("evidence/a .72.md", "evidence/a  b.md", "evidence/a\tb.md")  # a TAB: round 6 — the Links door wrote a space
        for k, name in enumerate(odd, 1):  # each made from a plain name, as el mv makes it — done refuses such a name
            (self.case() / f"evidence/p{k}.md").write_text(f"# P{k}\n\nThe body {k}.\n", encoding="utf-8")
            self.ok("todo", "add", "1", f"find drift {k}", "--expect", "[file: root cause]")
            self.ok("todo", "done", f"1.{k}", f"file:evidence/p{k}.md", f"drift {k} found")
            self.ok("mv", f"evidence/p{k}.md", name)
        self.ok("check")
        line = self.summary_line(self.ok("order")[0])
        self.assertNotIn("el mv", line)
        self.assertIn("3 more are proofs of done items whose name no Links line el takes can carry (", line)
        for name in odd:
            self.assertIn(name, line)
        self.assertTrue(line.startswith("- 3 file(s) without `summary:` — evidence/root-cause.md, notes/"), line)  # not counted
        out, _ = self.ok("order", "--adopt")
        kept = next(ln for ln in out.splitlines() if "left as they are: " in ln)
        self.assertIn("— proofs of done items whose name no Links line el takes", kept)
        for name in odd:
            self.assertIn(name, kept)
        self.assertNotIn("evidence/a ", out.split("README Links has no description", 1)[1].split("\n", 1)[0])
        self.ok("check")  # nothing printed here broke the record

    def test_adopt_writes_where_the_reader_looks(self):  # Codex, 2026-11-07, round 5: a title on line 5 got its summary
        # on line 6, outside the five lines read — Order stayed, and each --adopt added one more
        (self.case() / "notes/plan.md").write_text("<!-- kept -->\n\nfront words\n\n# Plan\n\nThe body.\n", encoding="utf-8")
        self.ok("phase", "open", "1", "Count", "--goal", "the plan holds [file: plan]")
        self.ok("todo", "add", "1", "write the plan", "--expect", "[file: plan]")
        self.ok("todo", "done", "1.1", "file:notes/plan.md", "the plan written")
        door = self.summary_line(self.ok("order")[0]).split("keeps the version: ", 1)[1]
        self.ok(*shlex.split(door)[1:])
        out, _ = self.ok("order", "--adopt")
        self.assertIn("summary written into notes/plan.md", out)
        lines = self.read("notes/plan.md").split("\n")
        self.assertEqual(lines[4], "summary: что это")  # line 5, the title under it
        self.assertEqual(lines[5], "# Plan")
        self.assertNotIn("notes/plan.md", self.summary_line(out))
        out, _ = self.ok("order", "--adopt")
        self.assertEqual(self.read("notes/plan.md").count("summary:"), 1)  # a repeat adds nothing
        self.assertNotIn("changed since done", self.ok("todo", "show", "1.1")[0])

    def test_a_dash_inside_a_name_is_not_a_description(self):  # Codex, 2026-11-07, round 7: el drew `[a — b.md](docs/a —
        # b.md)` for a file without a summary, read « — » inside the name as a description, and --adopt wrote the link's tail
        (self.case() / "docs").mkdir()
        (self.case() / "docs/a — b.md").write_text("# A\n\nThe body.\n", encoding="utf-8")
        self.ok("phase", "open", "1", "Count", "--goal", "the drift is found [file: root cause]")
        self.ok("todo", "add", "1", "find why the scale drifts", "--expect", "[file: root cause]")
        self.ok("todo", "done", "1.1", "file:docs/a — b.md", "the scale drifts by heat")
        line = self.summary_line(self.ok("order")[0])
        self.assertNotIn("docs/a — b.md → el order --adopt", line)  # Links does not describe it
        door = line.split("keeps the version: ", 1)[1]
        self.ok(*shlex.split(door)[1:])
        out, _ = self.ok("order", "--adopt")
        self.assertIn("summary written into docs/a — b.md", out)
        self.assertEqual(self.read("docs/a — b.md").split("\n")[1], "summary: что это")
        self.assertNotIn("changed since done", self.ok("todo", "show", "1.1")[0])

    def test_a_links_line_is_read_around_its_pointers(self):  # Codex, 2026-11-07, round 8: a « — » inside a second link
        # was read as the first one's description; a link in a description was adopted as it was — docs/docs/source.md
        (self.case() / "docs").mkdir()
        for name in ("two.md", "second — name.md", "linkdesc.md", "source.md"):
            (self.case() / "docs" / name).write_text("# R\n\nThe body.\n", encoding="utf-8")
        self.ok("readme", "add", "links", "[two](docs/two.md) [second — name](docs/second — name.md)")
        self.ok("readme", "add", "links", "docs/linkdesc.md — see [source](docs/source.md)")
        line = self.summary_line(self.ok("order")[0])
        self.assertIn("docs/linkdesc.md → el order --adopt", line)
        self.assertNotIn("docs/two.md → el order --adopt", line)  # two names on one line, no description of its own
        out, _ = self.ok("order", "--adopt")
        self.assertNotIn("summary written into docs/two.md", out)
        self.assertEqual(self.read("docs/linkdesc.md").split("\n")[1], "summary: see [source](source.md)")  # from its folder
        self.assertIn("[source](docs/source.md)", self.read("README.md"))  # README draws it from the case root
        self.ok("check")

    def test_every_file_has_a_summary_says_so(self):
        for rel in ("evidence/root-cause.md", "notes/plan.md", "notes/log.md"):
            p = self.case() / rel
            p.write_text(p.read_text().replace("\n\n", "\nsummary: a line\n\n", 1))
        out, _ = self.ok("order", "--adopt")
        self.assertIn("nothing to adopt: every file carries its own summary", out)
        code, out, err = run("order")
        self.assertNotIn("without `summary:`", out + err)


if __name__ == "__main__":
    unittest.main()
