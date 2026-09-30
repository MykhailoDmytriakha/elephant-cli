"""A report of 2026-09-30 (el 1.30.0): parent and child did not click through to each other.

`el spawn` wrote the parent's `waits: <child>` (TODO), `ждёт: <child>` (State) and the child's `parent: <parent> · фаза N`
(Links) as bare folder names — the editor opened none of them. The root was one rule broken: a line about a node at
another node is drawn, not written. Written once, the State line was also patched away at the child's close — and the
patch removed every `ждёт:` line: the agent's own and the one of a second child the phase still waited for. Since 1.31.0
the link to a case is one form everywhere (`[<case>](<case>/README.md)`), `ждёт:` is drawn from `waits:` on every README
write, and what el wrote before is read and drawn as a link on the next write."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, order, stamp
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_SESSION"] = "doer0930"  # EL_TWO_HANDS=0 comes from tests/__init__.py
        run("case", "new", "parent", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def parent(self) -> Path:
        return next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.name.endswith("-parent"))

    def child(self, tail: str) -> Path:
        return next(p for p in self.parent().iterdir() if p.is_dir() and p.name.endswith(tail))

    def read(self, case: Path, name: str) -> str:
        return (case / name).read_text(encoding="utf-8")

    def waits_lines(self) -> list:
        return [ln for ln in self.read(self.parent(), "README.md").split("\n") if ln.startswith("- ждёт: ")]

    def broken(self, case: Path) -> list:
        readme, _ = stamp.split(self.read(case, "README.md"))
        todo, _ = stamp.split(self.read(case, "TODO.md"))
        return order.broken_links(case, [], readme, todo)


class SpawnLinksBothWays(Base):
    def test_parent_and_child_point_at_each_other_with_links_that_resolve(self):
        code, _, err = run("spawn", "sub task", "--goal", "resolve blocker")
        self.assertEqual(code, 0, err)
        parent, child = self.parent(), self.child("sub-task")
        link = f"[{child.name}]({child.name}/README.md)"
        self.assertIn(f"  - waits: {link}", self.read(parent, "TODO.md"))
        self.assertEqual(self.waits_lines(), [f"- ждёт: {link}"])
        self.assertIn(f"- parent: [{parent.name}](../README.md) · фаза 1", self.read(child, "README.md"))
        # the cases block of Links draws the child at once, not on the parent's next write
        self.assertIn(f"  - {link} — ", self.read(parent, "README.md"))
        self.assertEqual(self.broken(parent), [])
        self.assertEqual(self.broken(child), [])
        self.assertEqual(run("--case", parent.name, "check")[0], 0)
        self.assertEqual(run("--case", child.name, "check")[0], 0)
        self.assertEqual(grammar.parse_todo(self.read(parent, "TODO.md")).phase(1).waits, [child.name])

    def test_the_drawn_line_is_not_counted_as_the_agents_text(self):
        run("spawn", "sub task", "--goal", "g")
        body, _ = stamp.split(self.read(self.parent(), "README.md"))
        parsed = grammar.parse_readme(body)
        # fill Decisions so that the README holds one line over the limit if the drawn line counted
        filler = grammar.README_MAX_LINES + 1 - (parsed.lines - parsed.rendered_lines)
        full = body.replace("## Decisions\n", "## Decisions\n" + "".join(f"- d{k}\n" for k in range(filler)), 1)
        self.assertEqual([f for f in grammar.parse_readme(full).errors if f.rule == "F2"], [])
        typed = full.replace("\n- ждёт: [", "\n- x: [")  # the same line, typed by the agent: counted
        self.assertTrue([f for f in grammar.parse_readme(typed).errors if f.rule == "F2"])


class ClosingOneChildKeepsTheRest(Base):
    def test_done_of_one_child_leaves_the_agents_line_and_the_other_child(self):
        run("readme", "set", "ждёт", "слово владельца")
        parent = self.parent().name
        run("--case", parent, "spawn", "child one", "--goal", "a")
        run("--case", parent, "spawn", "child two", "--goal", "b")
        one, two = self.child("child-one"), self.child("child-two")
        self.assertEqual(len(self.waits_lines()), 3)
        code, _, err = run("--case", one.name, "done", "first child finished")
        self.assertEqual(code, 0, err)
        # 1.30.0 removed all three here while TODO still waited for child two
        self.assertEqual(self.waits_lines(), ["- ждёт: слово владельца", f"- ждёт: [{two.name}]({two.name}/README.md)"])
        code, _, err = run("--case", two.name, "case", "cancel", "not needed any more")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.waits_lines(), ["- ждёт: слово владельца"])

    def test_set_and_drop_work_on_the_agents_line_and_refuse_the_drawn_one(self):
        parent = self.parent().name
        run("--case", parent, "spawn", "child one", "--goal", "a")
        one = self.child("child-one")
        drawn = f"- ждёт: [{one.name}]({one.name}/README.md)"
        self.assertEqual(run("--case", parent, "readme", "set", "ждёт", "ответ банка")[0], 0)
        self.assertEqual(self.waits_lines(), [drawn, "- ждёт: ответ банка"])
        self.assertEqual(run("--case", parent, "readme", "set", "ждёт", "ответ суда")[0], 0)
        self.assertEqual(self.waits_lines(), [drawn, "- ждёт: ответ суда"])
        self.assertEqual(run("--case", parent, "readme", "drop", "state", "ждёт")[0], 0)
        self.assertEqual(self.waits_lines(), [drawn])
        code, out, err = run("--case", parent, "readme", "drop", "state", "ждёт")
        self.assertEqual(code, 4)
        self.assertIn("drawn by el", out + err)
        self.assertIn(f"el --case {one.name} done", out + err)
        state = [ln for ln in stamp.split(self.read(self.parent(), "README.md"))[0].split("\n") if ln.startswith("- ")]
        k = next(i for i, ln in enumerate([ln for ln in state if ln.startswith("- ")], 1) if ln == drawn)
        self.assertEqual(run("--case", parent, "readme", "drop", "state", str(k))[0], 4)
        self.assertEqual(self.waits_lines(), [drawn])


class WhatElWroteBeforeIsDrawnAsALink(Base):
    def old_forms(self):
        """The three lines as 1.30.0 wrote them — stamped, so they are el's own writing, not a hand edit."""
        run("spawn", "sub task", "--goal", "g")
        parent, child = self.parent(), self.child("sub-task")
        link = f"[{child.name}]({child.name}/README.md)"
        for case, name, new, old in ((parent, "TODO.md", f"  - waits: {link}", f"  - waits: {child.name}"),
                                     (parent, "README.md", f"- ждёт: {link}", f"- ждёт: {child.name}"),
                                     (child, "README.md", f"- parent: [{parent.name}](../README.md)", f"- parent: {parent.name}")):
            body, _ = stamp.split(self.read(case, name))
            self.assertIn(new, body)
            (case / name).write_text(stamp.apply(body.replace(new, old)), encoding="utf-8")
        return parent, child, link

    def test_old_waits_parse_and_come_back_as_links(self):
        parent, child, link = self.old_forms()
        self.assertEqual(grammar.parse_todo(self.read(parent, "TODO.md")).phase(1).waits, [child.name])
        code, _, err = run("--case", parent.name)  # the entry refreshes README and TODO
        self.assertEqual(code, 0, err)
        self.assertIn(f"  - waits: {link}", self.read(parent, "TODO.md"))
        self.assertEqual(self.waits_lines(), [f"- ждёт: {link}"])
        self.assertEqual(run("--case", child.name, "readme", "touch")[0], 0)
        self.assertIn(f"- parent: [{parent.name}](../README.md) · фаза 1", self.read(child, "README.md"))

    def test_an_old_bare_line_about_a_closed_child_goes_and_a_bare_agents_line_stays(self):
        parent, child, _ = self.old_forms()
        self.assertEqual(run("--case", child.name, "done", "finished")[0], 0)
        self.assertEqual(self.waits_lines(), [])
        # a dated word the agent typed, which names no case of this one, is the agent's line
        run("--case", parent.name, "readme", "set", "ждёт", "2026-10-01-reply")
        run("--case", parent.name, "readme", "touch")
        self.assertEqual(self.waits_lines(), ["- ждёт: 2026-10-01-reply"])


if __name__ == "__main__":
    unittest.main()
