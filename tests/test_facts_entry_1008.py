"""The owner's word, 2026-10-07: «with a million of context, 3–6 thousand on entry is nothing — what matters is that it
reads all of it». The entry said «facts: 2 established — el facts», a count to be opened; the next agent stands on what
is known only if it sees it before its first command. The facts themselves go into the head of the entry."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run
from elephant import commands


class TheEntryShowsWhatIsKnown(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_HINTS="0", EL_SESSION="entry108", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "probe", "--goal", "g")
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def add_done(self, n, fact):
        run("todo", "add", "1", f"step {n}", "--expect", "[run: probe → ok]")
        run("todo", "done", f"1.{n}", "run:probe → ok", f"step {n} done", "--fact", fact)

    def test_the_facts_stand_in_the_head_newest_first(self):
        self.add_done(1, "the index covers 61 of 114 folders")
        self.add_done(2, "decode floor on this machine is 66 tok/s")
        out = run()[1]
        head = out.split("— the case on disk")[0]
        self.assertIn("facts: 2 established — el facts\n  ✓ 1.2 decode floor on this machine is 66 tok/s\n"
                      "  ✓ 1.1 the index covers 61 of 114 folders", head)

    def test_many_facts_show_the_newest_and_count_the_rest(self):
        for n in range(1, commands.FACTS_SHOWN + 3):
            self.add_done(n, f"fact number {n}")
        head = run()[1].split("— the case on disk")[0]
        self.assertIn(f"✓ 1.{commands.FACTS_SHOWN + 2} fact number {commands.FACTS_SHOWN + 2}", head)
        self.assertNotIn("✓ 1.1 fact number 1\n", head)
        self.assertIn("… 2 more — el facts", head)


if __name__ == "__main__":
    unittest.main()
