"""Formalization of work (concept 2026-09-04, research/work-graph.md): F18 the law of the collapsed
node — the parent's line is rendered from the child's own header, never typed."""
import os
import tempfile
import unittest
from pathlib import Path

from mike import commands, grammar, store
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("MIKE_CASE", None)
        run("case", "new", "demo case", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class PhaseLines(Base):
    def test_open_phase_line_carries_goal_and_path_and_follows_the_file(self):
        run("phase", "open", "1", "Build", "--goal", "ship the build")
        self.assertIn("- [ ] 1 Build — ship the build · [phases/1-build.md](phases/1-build.md)", self.read("TODO.md"))
        pf = self.case / "phases" / "1-build.md"
        pf.write_text(pf.read_text(encoding="utf-8").replace("goal: ship the build", "goal: ship the build to five users"), encoding="utf-8")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn("TODO refreshed", out)
        self.assertIn("- [ ] 1 Build — ship the build to five users · [phases/1-build.md](phases/1-build.md)", self.read("TODO.md"))
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)

    def test_planned_phase_keeps_its_intent_until_opened(self):
        run("phase", "open", "1", "Build", "--goal", "g")
        run("phase", "plan", "2", "Rollout", "--goal", "first users")
        self.assertIn("- [ ] 2 Rollout — first users\n", self.read("TODO.md"))
        run()
        self.assertIn("- [ ] 2 Rollout — first users\n", self.read("TODO.md"), "no file, no derived tail")
        self.assertIn("- [ ] 1 Build — g · [phases/1-build.md](phases/1-build.md)", self.read("TODO.md"))


class CaseMap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("MIKE_CASE", None)
        run("case", "new", "--root", "my app", "--goal", "g")
        self.project = Path(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def child(self, part: str) -> str:
        return next(p.name for p in (self.project / ".cases").iterdir() if p.is_dir() and part in p.name)

    def test_root_readme_maps_children_from_their_readmes(self):
        run("case", "new", "connect database", "--goal", "app talks to the database")
        run("case", "new", "onboarding", "--goal", "first users")
        db, ob = self.child("connect-database"), self.child("onboarding")
        run("--case", db, "phase", "open", "1", "Build", "--goal", "wire the client")
        run("--case", db, "readme", "set", "next", "write the client")
        code, out, err = run("--case", ob, "done", "closed early: not needed")
        self.assertEqual(code, 0, err)
        code, out, err = run("--case", self.project.name)
        self.assertEqual(code, 0, err)
        r = (self.project / "README.md").read_text(encoding="utf-8")
        self.assertIn("- cases: 1 open · 1 closed — every case: mike case list", r)
        self.assertIn(f"  - [{db}](.cases/{db}/README.md) — 1 Build ▶ · next: write the client", r)
        self.assertIn(f"  - closed: [{ob}](.cases/{ob}/README.md) — ", r)
        self.assertIn("closed early: not needed", r)
        j = (self.project / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn(f"RESULT · дело закрыто → closed early: not needed · {ob}/", j, "a child reports to its parent however it was created")
        run("--case", self.project.name)
        r2 = (self.project / "README.md").read_text(encoding="utf-8")
        self.assertEqual(r2.count("- cases:"), 1, "rendered lines are re-rendered, never duplicated")
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)

    def test_broken_child_is_named_and_holds_the_parent_open(self):
        run("case", "new", "broken one", "--goal", "g")
        name = self.child("broken-one")
        (self.project / ".cases" / name / "README.md").write_text("garbage\n", encoding="utf-8")
        code, out, err = run("--case", self.project.name)
        self.assertEqual(code, 0, err)
        self.assertIn(f"[{name}](.cases/{name}/README.md) — BROKEN", (self.project / "README.md").read_text(encoding="utf-8"))
        self.assertIn(f"nested case {name}: README unparsable", out)
        code, out, err = run("--case", self.project.name, "done", "x")
        self.assertEqual(code, 4)
        self.assertIn("nested cases still open", err)


class Dependencies(Base):
    """F19 — `after` edges: checked, cycle-free, numbers never reused while referenced, references follow moves."""

    def setUp(self):
        super().setUp()
        run("phase", "open", "1", "Build", "--goal", "g")

    def test_after_suffix_is_parsed_checked_and_shown_on_entry(self):
        run("todo", "add", "1", "write the parser")
        run("todo", "add", "1", "write the tests — after: 1.1")
        run("todo", "add", "1", "ship — after: 1.1, 1.2 — due: 2030-01-01")
        t = self.read("TODO.md")
        self.assertIn("  - [ ] 1.2 write the tests — after: 1.1\n", t)
        self.assertIn("  - [ ] 1.3 ship — after: 1.1, 1.2 — due: 2030-01-01\n", t)
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn("unblocked: 1.1 «write the parser» · blocked: 1.2 (after 1.1), 1.3 (after 1.1, 1.2)", out)
        code, out, err = run("todo", "done", "1.1", "parser passes 12 tests")
        self.assertEqual(code, 0, err)
        self.assertIn("RESULT · 1.1: parser passes 12 tests", self.read("JOURNAL.md"))
        self.assertIn("unblocked: 1.2 «write the tests» · blocked: 1.3 (after 1.2)", run()[1])
        self.assertEqual(run("todo", "after", "1.2", "9.9")[0], 4, "unknown target")
        self.assertEqual(run("todo", "after", "1.2", "1.2")[0], 2, "after itself")
        code, out, err = run("todo", "after", "1.1", "1.3")
        self.assertEqual(code, 3)
        self.assertIn("cycle", err)
        self.assertIn("1.1 → 1.3 → 1.1", err)
        code, out, err = run("todo", "after", "1.3", "none")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [ ] 1.3 ship — due: 2030-01-01\n", self.read("TODO.md"))
        self.assertIn("unblocked: 1.3 «ship», 1.2 «write the tests»", run()[1], "1.2 still waits for 1.1 (done): both unblocked, the dated one first")

    def test_done_needs_an_outcome_and_warns_when_still_blocked(self):
        run("todo", "add", "1", "a")
        run("todo", "add", "1", "b — after: 1.1")
        code, out, err = run("todo", "done", "1.1")
        self.assertEqual(code, 2)
        self.assertIn("what came out", err)
        self.assertIn("mike todo cancel 1.1", err)
        code, out, err = run("todo", "done", "1.2", "did it anyway")
        self.assertEqual(code, 0, err)
        self.assertIn("1.2 was after 1.1, still open", err)

    def test_numbers_are_not_reused_while_referenced_and_references_follow_moves(self):
        for t in ("a", "b", "c — after: 1.2"):
            run("todo", "add", "1", t)
        run("phase", "plan", "2", "Rollout", "--goal", "g")
        code, out, err = run("todo", "move", "1.2", "2")
        self.assertEqual(code, 0, err)
        self.assertIn("after-references rewritten in 1.3", out)
        self.assertIn("  - [ ] 1.3 c — after: 2.1", self.read("TODO.md"))
        code, out, err = run("todo", "drop", "2.1")
        self.assertEqual(code, 4)
        self.assertIn("dependency of 1.3", err)
        code, out, err = run("todo", "cancel", "2.1", "not needed")
        self.assertEqual(code, 0, err)
        code, out, err = run()
        self.assertIn("1.3 is after 2.1, which is gone (cancelled or dropped) → mike todo after 1.3 <refs|none>", out)
        self.assertIn("blocked: 1.3 (after 2.1)", out)
        self.assertIn("added: 2.2 e", run("todo", "add", "2", "e")[1], "a cancelled number lives in the journal and is not reused")
        self.assertIn("added: 1.4 d", run("todo", "add", "1", "d")[1])


class TwoEnds(Base):
    """F20 — done with evidence or cancelled with a reason, at every size."""

    def setUp(self):
        super().setUp()
        run("phase", "open", "1", "Build", "--goal", "g")

    def test_phase_close_refuses_open_items_and_cancel_is_the_other_exit(self):
        run("todo", "add", "1", "a")
        run("todo", "add", "1", "b")
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")
        code, out, err = run("phase", "close", "1", "done")
        self.assertEqual(code, 4)
        self.assertIn("open items 1.1, 1.2", err)
        run("todo", "done", "1.1", "ok")
        run("todo", "cancel", "1.2", "dropped scope")
        code, out, err = run("phase", "close", "1", "done")
        self.assertEqual(code, 0, err)

    def test_phase_cancel_collapses_the_branch_with_a_reason(self):
        run("todo", "add", "1", "a")
        run("phase", "plan", "2", "Rollout", "--goal", "first users")
        code, out, err = run("phase", "cancel", "1", "venue fell through")
        self.assertEqual(code, 0, err)
        t = self.read("TODO.md")
        self.assertIn("- [x] 1 Build — снято: venue fell through · ", t)
        self.assertIn("phases/1-build.md", t)
        self.assertNotIn("1.1 a", t)
        pf = (self.case / "phases" / "1-build.md").read_text(encoding="utf-8")
        self.assertIn("result: снято: venue fell through", pf)
        self.assertIn("- 1.1 ✗ a", pf)
        self.assertIn("DECISION · снята фаза 1 Build — venue fell through (пункты сняты: 1.1)", self.read("JOURNAL.md"))
        self.assertIn("progress: 1 Build ✗ · 2 Rollout", self.read("README.md"))
        code, out, err = run("phase", "cancel", "2", "no rollout this year")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.case / "phases" / "2-rollout.md").exists(), "a planned phase's file is born closed")
        self.assertEqual(run("phase", "cancel", "2", "again")[0], 4)
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)


class Unreferenced(Base):
    """F21 — nothing in the work points at it: roots are the hand-written README, TODO, phase files
    and RESULT/DECISION evidence; the rendered index is not a reference; archive/ is never named."""

    def doc(self, rel: str, text: str):
        p = self.case / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def test_reachability_from_the_roots_names_what_nothing_uses(self):
        run("phase", "open", "1", "Build", "--goal", "g")
        self.doc("docs/a.md", "# A\nsummary: a\nsee [b](b.md)\n")
        self.doc("docs/b.md", "# B\nsummary: b\n")
        self.doc("docs/c.md", "# C\nsummary: c\n")
        self.doc("docs/d.md", "# D\nsummary: d\n")
        self.doc("docs/e.md", "# E\nsummary: e\n")
        run("readme", "add", "links", "docs/ — документы")
        run("todo", "add", "1", "read [a](docs/a.md)")          # a is used by the work, b through a
        run("log", "RESULT", "measured, see [c](docs/c.md)")     # evidence keeps c alive
        run("readme", "add", "problems", "open · see [e](docs/e.md)")  # a hand-written README line
        self.doc("docs/f.md", "# F\nsummary: f\n")
        (self.case / "phases" / "1-build.md").write_text((self.case / "phases" / "1-build.md").read_text(encoding="utf-8") + "\nsources: `docs/f.md` cited bare\n", encoding="utf-8")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn("1 file(s) nothing in the work points at — docs/d.md → link it from an item, a phase file or a decision · park it: mike mv <file> archive/", out)
        self.assertNotIn("docs/b.md", out.split("nothing in the work")[1].split("\n")[0])
        run("log", "PROBLEM", "mentioned [d](docs/d.md) in passing")  # a PROBLEM is not evidence
        self.assertIn("docs/d.md → link it", run()[1])
        code, out, err = run("mv", "docs/d.md", "archive/")
        self.assertEqual(code, 0, err)
        self.assertNotIn("nothing in the work points at", run()[1])

    def test_the_rendered_index_is_not_a_reference(self):
        run("phase", "open", "1", "Build", "--goal", "g")
        self.doc("docs/only-indexed.md", "# O\nsummary: только в указателе\n")
        run("readme", "add", "links", "docs/ — документы")
        run()  # Links now lists the file
        self.assertIn("[only-indexed.md](docs/only-indexed.md)", self.read("README.md"))
        self.assertIn("docs/only-indexed.md → link it", run()[1])


class CaseCancel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("MIKE_CASE", None)
        run("case", "new", "--root", "my app", "--goal", "g")
        self.project = Path(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_case_cancel_collapses_open_phases_and_reports_to_the_parent(self):
        run("case", "new", "side quest", "--goal", "g")
        name = next(p.name for p in (self.project / ".cases").iterdir() if p.is_dir())
        run("--case", name, "phase", "open", "1", "Build", "--goal", "g")
        run("--case", name, "todo", "add", "1", "x")
        code, out, err = run("--case", name, "case", "cancel", "merged elsewhere")
        self.assertEqual(code, 0, err)
        child = self.project / ".cases" / name
        self.assertIn("снято: merged elsewhere", (child / "README.md").read_text(encoding="utf-8"))
        j = (child / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn("снята фаза 1 Build — merged elsewhere", j)
        self.assertIn("DECISION · дело снято → merged elsewhere", j)
        self.assertIn(f"DECISION · снято → merged elsewhere · {name}/", (self.project / "JOURNAL.md").read_text(encoding="utf-8"))
        run("--case", self.project.name)
        self.assertIn(f"closed: [{name}]", (self.project / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(run("--case", name, "case", "cancel", "again")[0], 4)
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)


if __name__ == "__main__":
    unittest.main()


class PhaseLinks(Base):
    """Feedback 2026-09-08 (BibleTruck): to the editor a bare `phases/2-calls.md` in a TODO line is text
    while `[x](docs/y.md)` beside it is a link; and `phase close` copied item lines verbatim into
    phases/, so every `[x](docs/y.md)` broke one folder down and `check` reported broken links."""

    def setUp(self):
        super().setUp()
        (self.case / "docs" / "calls").mkdir(parents=True)
        (self.case / "docs" / "calls" / "2026-09-01-sergey.md").write_text("summary: the call\n", encoding="utf-8")
        run("phase", "open", "1", "Calls", "--goal", "g")
        run("todo", "add", "1", "Sergey: did he name the window — [sergey](docs/calls/2026-09-01-sergey.md)")
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")

    def test_phase_close_rebases_item_links_into_the_phase_file(self):
        run("todo", "done", "1.1", "yes")
        code, out, err = run("phase", "close", "1", "window confirmed")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-calls.md")
        self.assertIn("- 1.1 ✓ Sergey: did he name the window — [sergey](../docs/calls/2026-09-01-sergey.md)", pf)
        self.assertNotIn("](docs/", pf)
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)
        self.assertNotIn("broken link", err + out)

    def test_phase_cancel_rebases_item_links_too(self):
        code, out, err = run("phase", "cancel", "1", "no calls")
        self.assertEqual(code, 0, err)
        self.assertIn("- 1.1 ✗ Sergey: did he name the window — [sergey](../docs/calls/2026-09-01-sergey.md)",
                      self.read("phases/1-calls.md"))
        code, out, err = run("check")
        self.assertNotIn("broken link", err + out)

    def test_closed_phase_line_links_its_file(self):
        run("todo", "done", "1.1", "yes")
        run("phase", "close", "1", "window confirmed")
        self.assertRegex(self.read("TODO.md"),
                         r"- \[x\] 1 Calls — window confirmed · \d{4}-\d{2}-\d{2} · \[phases/1-calls\.md\]\(phases/1-calls\.md\)\n")
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)

    def test_a_bare_phase_path_from_an_older_mike_becomes_a_link_on_the_next_write(self):
        run("todo", "done", "1.1", "yes")
        run("phase", "close", "1", "window confirmed")
        older = self.read("TODO.md").replace("[phases/1-calls.md](phases/1-calls.md)", "phases/1-calls.md")
        store.write(self.case, "TODO.md", older)  # the form every mike before 0.18 wrote
        self.assertIn("· phases/1-calls.md\n", self.read("TODO.md"))
        self.assertEqual(run("check")[0], 0, "the old form is still valid grammar")
        run("phase", "plan", "2", "Rollout", "--goal", "first users")  # any write through the door
        t = self.read("TODO.md")
        self.assertIn("· [phases/1-calls.md](phases/1-calls.md)\n", t)
        self.assertNotIn("· phases/1-calls.md\n", t)

    def test_link_normalisation_is_idempotent_and_leaves_code_alone(self):
        link = "[phases/1-calls.md](phases/1-calls.md)"
        self.assertEqual(commands._link_phase_paths(f"r · 2026-09-08 · {link}"), f"r · 2026-09-08 · {link}")
        self.assertEqual(commands._link_phase_paths("see `phases/1-calls.md` here"), "see `phases/1-calls.md` here")
        self.assertEqual(commands._link_phase_paths("r · phases/1-calls.md"), f"r · {link}")
