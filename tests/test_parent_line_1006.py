"""L5, measured 2026-10-06 (el 1.40.0): a nested case had three phases while its line in the parent's README still said
«(no phases yet) · next: open phase 1». The parent draws the line from the child's README, but drew it only when the
parent itself was written — the owner, who reads README files and not el's output, read a state that was gone.
Every write of a child's README now redraws its parents; the hand stays on the child; a parent README el cannot vouch
for (a hand edit) is left to its own next write."""
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
        os.environ.update(EL_HINTS="0", EL_SESSION="parentline1006", EL_TWO_HANDS="0")
        run("case", "new", "dashboard", "--goal", "the dashboard tells the truth")
        run("phase", "open", "1", "Metrics", "--goal", "every metric checked")
        run("todo", "add", "1", "check the order metric")
        run("spawn", "metric-drop", "--goal", "the cause of the night drop named")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def parent(self) -> Path:
        return next((Path(self.tmp.name) / ".cases").iterdir())

    def child_line(self, parent: Path) -> str:
        text = (parent / "README.md").read_text()
        return next(ln for ln in text.split("\n") if "metric-drop/README.md)" in ln and ln.startswith("  - ["))


class TheParentReadsTheChildNow(Base):
    def test_a_phase_opened_in_the_child_shows_at_the_parent(self):
        self.assertIn("(no phases yet)", self.child_line(self.parent()))
        code, _, err = run("phase", "open", "1", "Code", "--goal", "the code read")
        self.assertEqual(code, 0, err)
        run("phase", "plan", "2", "Raw", "--goal", "the raw events read")
        line = self.child_line(self.parent())
        self.assertIn("1 Code ▶ · 2 Raw", line)
        self.assertNotIn("no phases yet", line)

    def test_the_childs_next_shows_at_the_parent(self):
        run("phase", "open", "1", "Code", "--goal", "the code read")
        run("readme", "set", "next", "probe the raw table")
        self.assertIn("next: probe the raw table", self.child_line(self.parent()))

    def test_the_hand_stays_on_the_child(self):
        run("phase", "open", "1", "Code", "--goal", "the code read")
        code, out, _ = run()
        self.assertIn("case in hand: ", out)
        self.assertIn("› 2026-", out.split("\n")[0], "the child is in hand, not the parent el redrew")
        self.assertIn("metric-drop", out.split("\n")[0])

    def test_a_grandchild_redraws_its_own_parent(self):
        run("phase", "open", "1", "Code", "--goal", "the code read")
        run("spawn", "raw-read", "--goal", "the raw events read")
        run("phase", "open", "1", "Access", "--goal", "read access granted")
        child = next(p for p in self.parent().iterdir() if p.is_dir() and p.name.endswith("metric-drop"))
        text = (child / "README.md").read_text()
        line = next(ln for ln in text.split("\n") if "raw-read/README.md)" in ln and ln.startswith("  - ["))
        self.assertIn("1 Access ▶", line)

    def test_a_hand_edited_parent_is_left_to_its_own_next_write(self):
        readme = self.parent() / "README.md"
        readme.write_text(readme.read_text().replace("the dashboard tells the truth", "the dashboard tells the truth (edited)"))
        before = readme.read_text()
        code, _, err = run("phase", "open", "1", "Code", "--goal", "the code read")
        self.assertEqual(code, 0, err)
        self.assertEqual(readme.read_text(), before, "a command in the child never rebuilds a file in another case")
        self.assertFalse(list(self.parent().glob("*.recover.md")))


if __name__ == "__main__":
    unittest.main()
