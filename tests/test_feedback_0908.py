"""Feedback of 2026-09-08 (BibleTruck, case-6A0396998): README list lines edited in place, `set`
that stays in State, `touch` for a State that is still true, re-planning a planned phase,
`todo add --before`, the new text shown by `edit`, a shell-swallowed `$150` refused instead of
recorded, dead journal links seen by Order and mended by `relink`."""
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
        os.environ.pop("MIKE_CASE", None)
        run("case", "new", "demo case", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")

    def doc(self, rel: str, text: str = "# A\nsummary: a\n"):
        p = self.case / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


class ReadmeLines(Base):
    def test_edit_replaces_a_list_line_in_place(self):
        for t in ("a", "b", "c"):
            run("readme", "add", "decisions", f"2026-09-08 · {t}")
        code, out, err = run("readme", "edit", "decisions", "2", "2026-09-08 · b fixed")
        self.assertEqual(code, 0, err)
        self.assertIn("line 2 edited → «2026-09-08 · b fixed» (was: «2026-09-08 · b»)", out)
        r = self.read("README.md")
        self.assertLess(r.index("· a"), r.index("· b fixed"))
        self.assertLess(r.index("· b fixed"), r.index("· c"))
        self.assertNotIn("2026-09-08 · b\n", r)
        code, out, err = run("readme", "edit", "decisions", "9", "x")
        self.assertEqual(code, 4)
        self.assertIn("3 line(s), nothing at position 9", err)
        code, out, err = run("readme", "edit", "state", "next", "call them")
        self.assertEqual(code, 0, err)
        self.assertIn("- next: call them", self.read("README.md"))
        self.assertEqual(run("check")[0], 0)

    def test_set_refuses_a_prefix_that_lives_in_another_section(self):
        run("readme", "add", "decisions", "1 Реклама — вилка 1000-3500")
        code, out, err = run("readme", "set", "1 Реклама", "1 Реклама — вилка 1850-7300")
        self.assertEqual(code, 4)
        self.assertIn("is Decisions line 1", err)
        self.assertIn('mike readme edit decisions 1 "…"', err)
        r = self.read("README.md")
        self.assertNotIn("- 1 Реклама:", r, "no doubled line quietly opened in State")
        self.assertIn("- 1 Реклама — вилка 1000-3500", r)
        self.assertEqual(run("readme", "set", "next", "a new State line is still fine")[0], 0)

    def test_set_refuses_the_lines_mike_derives(self):
        code, out, err = run("readme", "set", "last", "x")
        self.assertEqual(code, 2)
        self.assertIn("mike readme touch", err)

    def test_touch_confirms_state_without_rewriting_it(self):
        run("readme", "set", "next", "second measurement")
        run("log", "RESULT", "first measurement: 48 ms")
        code, out, err = run()
        self.assertIn("State is behind", out)
        self.assertIn("mike readme touch", out)
        code, out, err = run("readme", "touch")
        self.assertEqual(code, 0, err)
        self.assertIn("confirmed current", out)
        code, out, err = run()
        self.assertNotIn("State is behind", out)
        self.assertIn("- next: second measurement", self.read("README.md"))
        self.assertEqual(run("check")[0], 0)


class PhasePlan(Base):
    def test_a_planned_phase_is_re_planned_by_the_same_command(self):
        run("phase", "plan", "2", "Rollout", "--goal", "заплатить административных издержек")
        code, out, err = run("phase", "plan", "2", "Rollout", "--goal", "заплатить $150 административных издержек")
        self.assertEqual(code, 0, err)
        self.assertIn("re-planned: phase 2 Rollout — заплатить $150 административных издержек (goal)", out)
        self.assertIn("- [ ] 2 Rollout — заплатить $150 административных издержек\n", self.read("TODO.md"))
        code, out, err = run("phase", "plan", "2", "Launch")
        self.assertEqual(code, 0, err)
        self.assertIn("name Rollout → Launch", out)
        self.assertIn("- [ ] 2 Launch — заплатить $150", self.read("TODO.md"))
        self.assertIn("nothing changed", run("phase", "plan", "2", "Launch")[1])
        code, out, err = run("phase", "plan", "1", "Work", "--goal", "new")
        self.assertEqual(code, 4, "an open phase keeps its goal in its file")
        self.assertIn("phases/1-work.md", err)
        self.assertIn("goal:", err)
        self.assertEqual(run("check")[0], 0)


class TodoAdd(Base):
    def test_before_puts_the_item_in_place(self):
        run("todo", "add", "1", "a")
        run("todo", "add", "1", "c")
        code, out, err = run("todo", "add", "1", "b", "--before", "1.2")
        self.assertEqual(code, 0, err)
        self.assertIn("added: 1.3 b (before 1.2)", out)
        t = self.read("TODO.md")
        self.assertLess(t.index("1.1 a"), t.index("1.3 b"))
        self.assertLess(t.index("1.3 b"), t.index("1.2 c"))
        code, out, err = run("todo", "add", "1", "d", "--before", "1.9")
        self.assertEqual(code, 4)
        self.assertIn("--before 1.9: no such item", err)
        code, out, err = run("todo", "add", "1", "слово " * 20)
        self.assertEqual(code, 3)
        self.assertIn("suggestion: \"", err)
        self.assertIn("--before 1.K", err, "the refusal names how a re-added item keeps its place")

    def test_edit_shows_the_new_text(self):
        run("todo", "add", "1", "Name Search")
        code, out, err = run("todo", "edit", "1.1", "Name search done right")
        self.assertEqual(code, 0, err)
        self.assertIn("edited: 1.1 → «Name search done right» (was: «Name Search»)", out)


class ShellTrace(Base):
    def test_a_swallowed_dollar_is_refused_not_recorded(self):
        before = self.read("TODO.md")
        code, out, err = run("todo", "add", "1", "заплатить  административных издержек")  # zsh ate `$150`
        self.assertEqual(code, 2)
        self.assertIn("double space", err)
        self.assertIn("SINGLE quotes", err)
        self.assertEqual(self.read("TODO.md"), before)
        journal = self.read("JOURNAL.md")
        self.assertEqual(run("log", "RESULT", "издержки .72 вместо прикидки")[0], 2)  # `$127.72` → `.72`
        self.assertEqual(run("log", "RESULT", " for the permit")[0], 2)              # `$150 for the permit`
        self.assertEqual(run("log", "RESULT", "a trailing space is innocent ")[0], 0)  # `"x " * n` happens everywhere
        self.assertEqual(run("phase", "plan", "2", "Rollout", "--goal", "goal  with a hole")[0], 2)
        code, out, err = run("log", "RESULT", "заплатить $150 административных издержек")
        self.assertEqual(code, 0, err)
        self.assertIn("заплатить $150 административных издержек", self.read("JOURNAL.md"))


class JournalLinks(Base):
    def test_dead_journal_links_are_named_and_relinked_through_the_stamp_door(self):
        self.doc("docs/a.md")
        run("readme", "add", "links", "docs/ — документы")
        run("log", "RESULT", "call done — [a](docs/a.md); an example [name](path) stays an example")
        self.assertNotIn("broken link", run()[1])
        (self.case / "docs" / "calls").mkdir()
        os.rename(self.case / "docs" / "a.md", self.case / "docs" / "calls" / "a.md")  # moved without mike
        code, out, err = run()
        self.assertIn("JOURNAL.md → docs/a.md", out)
        self.assertIn("mike relink old new", out)
        code, out, err = run("relink", "docs/a.md", "docs/calls/a.md")
        self.assertEqual(code, 0, err)
        self.assertIn("relinked: docs/a.md → docs/calls/a.md · links rewritten: JOURNAL.md (1)", out)
        self.assertIn("[a](docs/calls/a.md)", self.read("JOURNAL.md"))
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertNotIn("broken link", out)
        self.assertEqual(self.read("README.md").count("[a.md](docs/calls/a.md)"), 1, "the stale rendered line is absorbed, not doubled")
        self.assertNotIn("bypassing mike", err, "relink writes through the stamp door")
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)

    def test_a_gone_or_example_link_is_retired_into_literal_text(self):
        run("log", "DECISION", "every item links its material like [x](docs/y.md)")  # an example, no backticks
        code, out, err = run()
        self.assertIn("JOURNAL.md → docs/y.md", out)
        self.assertIn("mike relink old none", out)
        code, out, err = run("relink", "docs/y.md", "none")
        self.assertEqual(code, 0, err)
        self.assertIn("retired: docs/y.md — 1 link(s) now literal text `[name](docs/y.md)`: JOURNAL.md (1)", out)
        self.assertIn("like `[x](docs/y.md)`", self.read("JOURNAL.md"))
        self.assertNotIn("broken link", run()[1])
        self.assertEqual(run("check")[0], 0, "the journal was rewritten through the stamp door")
        self.doc("docs/z.md")
        self.assertEqual(run("relink", "docs/z.md", "none")[0], 4, "a link to a file that exists is not dead")

    def test_relink_refuses_what_mv_should_do_and_a_missing_target(self):
        self.doc("docs/a.md")
        code, out, err = run("relink", "docs/a.md", "docs/b.md")
        self.assertEqual(code, 4)
        self.assertIn("mike mv docs/a.md docs/b.md", err)
        code, out, err = run("relink", "docs/gone.md", "docs/nowhere.md")
        self.assertEqual(code, 4)
        self.assertIn("not a file in the case", err)
