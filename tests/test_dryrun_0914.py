"""Dry run 2026-09-14, an empty project set up from AGENT.md alone — two lies the tool told a
fresh agent:

1. `el case new "договор с подрядчиком"` died with «`2026-09-14-` is not a valid case name: date
   prefix + words of letters/digits» — the slug dropped every Cyrillic letter, and the message
   spoke of letters while the agent had typed letters. The owner names cases in the words he says;
   the folder stays latin for paths, links and git, so the name is transliterated, and the human
   name survives as the README title.
2. In a workspace with no cases at all, `el` answered «every case here is closed» — nothing had
   ever been opened. Zero is not "all of them"; an empty space must say it is empty."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import commands, store
from tests.test_commands import run


class CaseNamedInTheOwnersWords(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_a_cyrillic_name_becomes_a_latin_folder(self):
        code, out, err = run("case", "new", "договор с подрядчиком", "--goal", "подписать до конца месяца")
        self.assertEqual(code, 0, err)
        case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        self.assertTrue(case.name.endswith("-dogovor-s-podryadchikom"), case.name)
        self.assertIn("# договор с подрядчиком", (case / "README.md").read_text(encoding="utf-8"),
                      "the human name stays as the title — only the folder is transliterated")

    def test_ukrainian_letters_too(self):
        self.assertTrue(commands._slug("звіт за вересень").endswith("zvit-za-veresen"))
        self.assertEqual(commands._slug("Їжак ґанок"), "yizhak-ganok")

    def test_a_name_with_no_letters_at_all_is_refused_with_a_way_out(self):
        code, out, err = run("case", "new", "!!! ???", "--goal", "x")
        self.assertEqual(code, 2)
        self.assertIn("leaves no folder name", err)
        self.assertIn("el case new", err, "a refusal carries the command that works")


class EmptySpaceSaysItIsEmpty(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".cases"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_case_at_all_is_not_every_case_closed(self):
        with self.assertRaises(store.StoreError) as cm:
            store.hand(self.root)
        self.assertIn("no case here yet", str(cm.exception))
        self.assertNotIn("closed", str(cm.exception))

    def test_a_closed_case_still_reports_as_closed(self):
        os.chdir(self.tmp.name)
        try:
            run("case", "new", "demo", "--goal", "g")
            run("done", "finished")
            with self.assertRaises(store.StoreError) as cm:
                store.hand(self.root)
            self.assertIn("closed", str(cm.exception))
        finally:
            os.chdir(Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    unittest.main()
