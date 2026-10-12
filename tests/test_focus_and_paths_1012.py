"""Two live reports of 2026-10-12 (el 1.62.0).

1. A note 8 over the pocket limit, an artifact's path in it, asked for a wider limit. Measured the same day: 108 live notes,
   none at 150, the longest 147; the polygon's note refusals were mostly a paragraph pushed into a pocket. The limit stays;
   the refusal names a bare path with its size — as a link `[short name](path)` only the name counts.
2. One open item stood between done ones of 7–12 lines each (results, proofs, signatures) and the reader hunted for it. The
   file keeps every block — results and proof versions live there; a bare `el todo` says first what is left: open items
   of each running phase, then the held ones.
3. The maintainer's own report the same day: `el --case x todo` printed an item stored as «el todo …» as
   «el --case x todo …» — the --case carry of 1.61.0 rewrote the case's own words. The case is printed as stored.
"""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    KEYS = ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_CASE")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="focus1012", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "engine", "--goal", "x")
        run("phase", "open", "1", "Work", "--goal", "x")
        for k in (1, 2, 3):
            run("todo", "add", "1", f"step {k}")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class ABarePathIsNamed(Base):
    PATH = "docs/review/2026-10-12-session-guard-findings.md"

    def setUp(self):
        super().setUp()
        case = next(Path(self.tmp.name, ".cases").glob("*-engine"))
        (case / self.PATH).parent.mkdir(parents=True)
        (case / self.PATH).write_text("# findings\n", encoding="utf-8")

    def refusal(self, words):
        note = f"artifact: {words} — " + "w" * 150
        code, _, err = run("todo", "note", "1.1", note)
        self.assertEqual(code, 3)
        return err

    def test_a_path_is_named_by_the_file_it_names(self):  # Codex round 1: shapes — the file decides, not a pattern
        self.assertIn(f"«{self.PATH}#two» is a bare path", self.refusal(f"{self.PATH}#two"))
        self.assertNotIn("bare path", self.refusal("https://example.com/?path=docs/review/a.md"))
        self.assertNotIn("bare path", self.refusal("docs/review/missing.md"))
        case = next(Path(self.tmp.name, ".cases").glob("*-engine"))
        (case / "docs" / "LICENSE").write_text("x", encoding="utf-8")
        (case / "LICENSE").write_text("x", encoding="utf-8")
        self.assertIn("«docs/LICENSE» is a bare path", self.refusal("docs/LICENSE"))  # round 2: no extension, a slash
        self.assertNotIn("bare path", self.refusal("LICENSE"))  # a lone word is a word (the declared boundary)
        (case / "docs" / "report).md").write_text("x", encoding="utf-8")
        (case / "docs" / "report.md.").write_text("x", encoding="utf-8")
        err = self.refusal("docs/report).md")
        self.assertIn("«docs/report).md» is a bare path", err)  # round 3: no link template to break
        self.assertNotIn("[short name]", err)
        self.assertIn("«docs/report.md.» is a bare path", self.refusal("docs/report.md."))  # as written first
        (case / "docs" / "review#draft.md").write_text("x", encoding="utf-8")
        self.assertIn("«docs/review#draft.md» is a bare path", self.refusal("docs/review#draft.md"))  # round 4: # in a name
        self.assertIn("«docs/review#draft.md#section» is a bare path", self.refusal("docs/review#draft.md#section"))  # round 5
        absolute = str(Path(self.tmp.name, "abs.md"))
        Path(absolute).write_text("x", encoding="utf-8")
        self.assertIn(f"«{absolute}» is a bare path", self.refusal(absolute))

    def test_the_refusal_names_the_bare_path_and_the_link_that_costs_its_name(self):
        note = f"review artifact: {self.PATH} — three P2 findings closed in the commit, one P3 moved to the bug list, waits for review"
        self.assertGreater(len(note), 150)
        code, _, err = run("todo", "note", "1.1", note)
        self.assertEqual(code, 3)
        self.assertIn(f"«{self.PATH}» is a bare path, {len(self.PATH)} of them: written as a markdown link, only its "
                      f"name counts", err)

    def test_a_link_and_a_url_are_not_bare_paths(self):
        note = ("review artifact: [findings](" + self.PATH + ") and https://example.com/a/b/report.html — "
                + "w" * 130)
        code, _, err = run("todo", "note", "1.1", note)
        self.assertEqual(code, 3)
        self.assertNotIn("is a bare path", err)
        self.assertIn("of them are link names", err)

    def test_the_limit_stays(self):
        code, _, _ = run("todo", "note", "1.1", "w" * 151)
        self.assertEqual(code, 3)
        code, _, err = run("todo", "note", "1.1", "w" * 150)
        self.assertEqual(code, 0, err)


class TheBareTodoSaysWhatIsLeft(Base):
    def test_open_and_held_items_come_first(self):
        run("todo", "done", "1.1", "run:t → ok", "one")
        run("todo", "hold", "1.2", "waiting for: a key")
        code, out, err = run("todo")
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertEqual(lines[0], "open now — phase 1: 1.3 «step 3» · on hold: 1.2 «step 2»")
        self.assertTrue(lines[-1].startswith("write: el todo add"))

    def test_nothing_running_no_line(self):
        for k in (1, 2, 3):
            run("todo", "done", f"1.{k}", "run:t → ok", "x")
        _, out, _ = run("todo")
        self.assertNotIn("open now", out)

    def test_sub_items_are_named_and_a_paused_phase_is_not(self):  # Codex round 1
        run("todo", "add", "1.1", "probe one")
        run("todo", "add", "1.1", "probe two")
        run("todo", "hold", "1.1.2", "waiting for: a key")
        _, out, _ = run("todo")
        first = out.splitlines()[0]
        self.assertIn("1.1.1 «probe one»", first)
        self.assertIn("on hold: 1.1.2 «probe two»", first)
        run("phase", "open", "2", "Detour", "--goal", "y", "--why", "a blocker came up")
        run("todo", "add", "2", "fix the blocker")
        _, out, _ = run("todo")
        first = out.splitlines()[0]
        self.assertIn("phase 2: 2.1 «fix the blocker»", first)
        self.assertNotIn("phase 1:", first)

    def test_the_line_keeps_nested_quotes_of_an_item(self):  # round 3: «a «b» el todo c» under --case
        run("todo", "add", "1", "a «b» el todo c")
        name = next(Path(self.tmp.name, ".cases").glob("*-engine")).name
        _, out, _ = run("--case", name, "todo")
        self.assertIn("a «b» el todo c", out.splitlines()[0])

    def test_a_planned_phase_is_not_named(self):
        run("phase", "plan", "2", "Next", "--goal", "later work")
        run("todo", "add", "2", "parked step")
        _, out, _ = run("todo")
        self.assertIn("open now — phase 1: 1.1 «step 1», 1.2 «step 2», 1.3 «step 3»", out.splitlines()[0])
        self.assertNotIn("phase 2:", out.splitlines()[0])


class TheCaseIsPrintedAsStored(Base):
    def setUp(self):
        super().setUp()
        self.name = next(Path(self.tmp.name, ".cases").glob("*-engine")).name
        run("todo", "add", "1", "el todo names the open items first")
        run("todo", "note", "1.4", "el todo show 1.4 is the card")
        run("readme", "set", "next", "el todo add 1 for the next step")

    def test_bare_todo_entry_card_and_readme_keep_the_words(self):
        for call in (("todo",), (), ("todo", "show", "1.4"), ("todo", "show", "1"), ("readme",)):
            code, out, err = run("--case", self.name, *call)
            self.assertEqual(code, 0, err)
            self.assertNotIn(f"el --case {self.name} todo names the open items", out, call)
            self.assertNotIn(f"el --case {self.name} todo show 1.4 is the card", out, call)
            self.assertNotIn(f"el --case {self.name} todo add 1 for the next step", out, call)

    def test_the_card_keeps_a_phase_name_and_an_input_proof(self):  # Codex round 1
        run("todo", "done", "1.1", "run:el todo list → three items", "listed")
        run("todo", "after", "1.4", "1.1")
        _, out, _ = run("--case", self.name, "todo", "show", "1.4")
        self.assertIn("run el todo list → three items", out)
        self.assertNotIn(f"el --case {self.name} todo list", out)
        run("case", "new", "other", "--goal", "y")
        other = next(Path(self.tmp.name, ".cases").glob("*-other")).name
        run("--case", other, "phase", "open", "1", "el todo name", "--goal", "x")
        run("--case", other, "todo", "add", "1", "a step")
        _, out, _ = run("--case", other, "todo", "show", "1.1")
        self.assertIn("phase 1 el todo name (open)", out)
        run("--case", other, "todo", "done", "1.1", "run:t → ok", "x")
        run("--case", other, "phase", "close", "1", "done", "--reflect", "a", "--align", "b")
        _, out, _ = run("--case", other, "todo", "show", "1.1")
        self.assertIn("phase 1 el todo name (closed — history", out)  # round 2: the closed card too

    def test_el_s_own_doors_still_carry_the_case(self):
        _, out, _ = run("--case", self.name, "todo")
        self.assertIn(f"write: el --case {self.name} todo add N", out)
        code, _, err = run("--case", self.name, "todo", "done", "9.9", "run:x → y", "z")
        self.assertNotEqual(code, 0)
        self.assertIn(f"el --case {self.name} ", err)


if __name__ == "__main__":
    unittest.main()
