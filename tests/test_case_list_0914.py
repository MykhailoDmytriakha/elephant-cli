"""The owner's question of 2026-09-14: is there a command that shows which cases are still open?
`el case list` existed but mixed open and closed in one column, said `phases 0/1` instead of where
the case stands, and drew the case differently from the `cases:` block at its parent. Now one
description per case node (order.case_desc) wherever it is seen from outside: open first with
progress · next · due, closed as a count plus the latest few (`--all` for every one). Two things
found on the way: a closed case kept `next: open phase 1 …` (a lie), and the child's line at its
parent was a tick the tool wrote without a kind of evidence (its own F20)."""
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
        self.root = Path(self.tmp.name) / ".cases"

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def case(self, part: str) -> Path:
        return next(p for p in self.root.iterdir() if p.is_dir() and part in p.name)

    def read(self, part: str, name: str) -> str:
        return (self.case(part) / name).read_text(encoding="utf-8")


class WhereEveryCaseStands(Base):
    def test_open_first_rendered_like_at_the_parent_closed_as_a_count(self):
        for i in range(1, 8):
            run("case", "new", f"old {i}", "--goal", "g")
            run("done", f"finished {i}")
        run("case", "new", "live one", "--goal", "g")
        run("phase", "open", "1", "Build", "--goal", "b")
        run("readme", "set", "next", "call the bank")
        run("readme", "set", "due", "2099-01-01 · decision meeting")
        code, out, err = run("case", "list")
        self.assertEqual(code, 0, err)
        lines = out.splitlines()
        self.assertIn("live-one — 1 Build ▶ · next: call the bank · due 2099-01-01 (in ", lines[0])
        closed = [l for l in lines if l.strip().startswith("closed: ")]
        self.assertEqual(len(closed), 5, "the latest few, not all seven")
        self.assertIn("old-7", closed[0])
        self.assertIn("… +2 closed earlier — el case list --all", out)
        self.assertIn("cases: 8 · 1 open · 7 closed", out)
        code, out, err = run("case", "list", "--all")
        self.assertEqual(len([l for l in out.splitlines() if l.strip().startswith("closed: ")]), 7)
        self.assertNotIn("closed earlier", out)

    def test_a_closed_case_has_no_next_step_line(self):
        run("case", "new", "done soon", "--goal", "g")
        self.assertIn("- next: ", self.read("done-soon", "README.md"))
        run("done", "finished")
        readme = self.read("done-soon", "README.md")
        self.assertNotIn("- next: ", readme, "a closed case that still says «open phase 1» lies")
        self.assertIn("- closed: ", readme)
        run("case", "new", "dropped", "--goal", "g")
        run("case", "cancel", "not needed")
        self.assertNotIn("- next: ", self.read("dropped", "README.md"))
        self.assertEqual(run("check", "--all")[0], 0)

    def test_the_child_reports_to_its_parent_with_the_kind_of_evidence(self):
        run("case", "new", "parent", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "w")
        run("spawn", "child", "--goal", "c")
        run("done", "child finished")
        todo = self.read("parent", "TODO.md")
        self.assertRegex(todo, r"  - \[x\] 1\.1 child finished · [\d-]+-child/\n    - file: \[[\d-]+-child\]\([\d-]+-child/README\.md\)\n",
                         "the child's proof is a line under the item (F22, 1.10.0)")
        self.assertIn("evidence: 1 done · file 1", run()[1], "the tool keeps its own F20")
        self.assertEqual(run("check")[0], 0, "the link resolves from the parent")

    def test_the_parent_block_and_the_list_say_the_same(self):
        run("case", "new", "parent", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "w")
        run("spawn", "child", "--goal", "c")
        run("phase", "open", "1", "Dig", "--goal", "d")
        run("readme", "set", "next", "read the logs")
        run("readme", "set", "due", "2099-02-02 · court")
        run("case", "use", "parent")
        readme = run()[1]
        self.assertIn("— 1 Dig ▶ · next: read the logs · due 2099-02-02", readme, "the cases block at the parent")
        listing = run("case", "list")[1]
        self.assertIn("child — 1 Dig ▶ · next: read the logs · due 2099-02-02 (in ", listing)


if __name__ == "__main__":
    unittest.main()
