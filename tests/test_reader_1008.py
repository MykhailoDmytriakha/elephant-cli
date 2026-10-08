"""The owner, 2026-10-08, after a big task on another machine: «I opened the README and could not find what I started
with; I went to Context and saw rules and other things». A cold reader measured it the same day — a fresh model given a
finished case's README alone, the owner's five questions, eight live cases, two readers each: «what did you ask for, and
when» was «not in the README» for eleven of sixteen, and six took el's own instructions in Links («summary: missing →
add …», «describe this folder: el readme add links …») for an unfinished template. With the start drawn first in State
and no instruction in the owner's page: two of sixteen, and two."""
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

README = """# probe

## Context
{context}

## State
- next: go

## Decisions

## Problems

## Links
{links}
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="reader1008", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        self.today = dt.date.today().isoformat()

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def readme(self):
        return next(Path(self.tmp.name, ".cases").glob("*/README.md")).read_text(encoding="utf-8")

    def state(self, text):
        return text.split("## State\n", 1)[1].split("\n## ", 1)[0].strip().split("\n")

    def write(self, context, links=""):
        src = Path(self.tmp.name) / "readme-in.md"
        src.write_text(README.format(context=context, links=links), encoding="utf-8")
        return run("readme", "--file", str(src))


class TheStartIsTheFirstLineOfState(Base):
    def test_a_new_case_says_when_it_opened(self):
        run("case", "new", "probe", "--goal", "the probe answers in one call")
        self.assertEqual(self.state(self.readme())[0], f"- opened: {self.today} — with the goal above")

    def test_a_readme_written_whole_without_it_gets_it_back(self):
        run("case", "new", "probe", "--goal", "the probe answers in one call")
        code, out, err = self.write("the probe answers in one call")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.state(self.readme())[0], f"- opened: {self.today} — with the goal above")

    def test_a_rewritten_goal_keeps_the_one_the_case_opened_with(self):
        run("case", "new", "probe", "--goal", "the probe answers in one call")
        self.write("the probe answers in one call and logs it")
        self.write("A different goal now: the whole service is measured.")
        self.assertEqual(self.state(self.readme())[0],
                         f"- opened: {self.today} — the goal then: «the probe answers in one call»")

    def test_the_line_is_els_not_the_agents(self):
        run("case", "new", "probe", "--goal", "g")
        code, _, err = run("readme", "set", "opened", "yesterday")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.state(self.readme())[0], f"- opened: {self.today} — with the goal above")

    def test_the_case_stays_in_order(self):
        run("case", "new", "probe", "--goal", "g")
        self.write("g")
        code, out, err = run("check")
        self.assertEqual(code, 0, out + err)
        self.assertIn("violations: 0", out)

    def test_root_mode_opens_the_same_way(self):
        run("case", "new", "--root", "app", "--goal", "the app ships")
        text = Path(self.tmp.name, "README.md").read_text(encoding="utf-8")
        self.assertEqual(self.state(text)[0], f"- opened: {self.today} — with the goal above")
        run("readme", "touch")
        text = Path(self.tmp.name, "README.md").read_text(encoding="utf-8")
        self.assertEqual(self.state(text)[0], f"- opened: {self.today} — with the goal above")


class NoInstructionInTheOwnersPage(Base):
    def setUp(self):
        super().setUp()
        run("case", "new", "probe", "--goal", "g")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-probe"))
        (self.case / "data").mkdir()
        (self.case / "data" / "notes.md").write_text("# notes\n\nno summary line\n", encoding="utf-8")

    def test_a_file_without_summary_is_its_link_alone_and_order_names_it(self):
        code, out, err = run("order")
        r = self.readme()
        self.assertIn("- data/\n  - [notes.md](data/notes.md)\n", r)
        self.assertNotIn("summary: missing", r)
        self.assertNotIn("describe this folder", r)
        self.assertIn("1 file(s) without `summary:` — data/notes.md", out)
        self.assertIn("folder data/ has no description", out)

    def test_the_old_placeholder_lines_render_clean(self):
        old = ('- data/ — (describe this folder: el readme add links "data/ — …")\n'
               "  - [notes.md](data/notes.md) — summary: missing → add `summary: …` as line 2")
        code, out, err = self.write("g", old)
        self.assertEqual(code, 0, err)
        r = self.readme()
        self.assertIn("- data/\n  - [notes.md](data/notes.md)\n", r)
        self.assertNotIn("summary: missing", r)
        self.assertNotIn("describe this folder", r)

    def test_a_description_given_is_drawn_as_before(self):
        run("readme", "add", "links", "data/ — what the probe saw")
        (self.case / "data" / "notes.md").write_text("# notes\nsummary: the probe's log\n", encoding="utf-8")
        run("order")
        self.assertIn("- data/ — what the probe saw\n  - [notes.md](data/notes.md) — the probe's log", self.readme())


if __name__ == "__main__":
    unittest.main()
