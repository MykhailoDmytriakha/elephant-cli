"""A live work project of 2026-09-25 (the owner's machine, read-only output): 33 case folders — 27 old folders from before
el with no README at all (a journal.md and materials), 2 cases from before el with their own README, 4 el cases. `el case
list` said «28 open» and drew 27 lines «BROKEN: README unparsable» (there was no README to parse), the entry counted the
same folders as closed — two rules for one question. The case in hand was the one touched last — a case from before el —
and the entry poured its raw files onto the screen (27 KB) while Order said «migrate». A case named with a date got it
twice: `<date>-<date>-…`. One rule for what a case is, a short screen for a case el cannot read yet, one date."""
import os
import tempfile
import time
import unittest
from pathlib import Path

from elephant import order, stamp
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        self.root = Path(self.tmp.name).resolve() / ".cases"
        run("case", "new", "finished work", "--goal", "g")
        run("done", "finished")
        run("case", "new", "release check", "--goal", "the release is verified")
        run("phase", "open", "1", "Redis Check", "--goal", "redis owned")
        for name in ("2026-02-13-invoice-import-investigation", "2026-03-04-login-retry-fix", "2026-08-20-certificate-rotation"):
            d = self.root / name
            d.mkdir()
            (d / "journal.md").write_text("# Journal\n\n- worked on it\n", encoding="utf-8")
            (d / "notes.md").write_text("notes\n", encoding="utf-8")
        self.legacy = self.root / "2026-08-27-ABCD-12345-migration-validation"
        self.legacy.mkdir()
        (self.legacy / "readme.md").write_text("# ABCD-12345 migration validation\n\n## Current state\n- in progress\n\n"
                                               "## Objective\n- compare two regions\n", encoding="utf-8")
        (self.legacy / "todo.md").write_text("# Todo\n\n## Open Tasks\n- [ ] confirm the datasource\n", encoding="utf-8")
        (self.legacy / "journal.md").write_text("# Journal\n\n## 2026-09-25\n- rerun planned\n", encoding="utf-8")
        now = time.time()
        os.utime(self.legacy / "journal.md", (now, now))  # touched last: this is where the owner works

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()


class OneRuleForWhatACaseIs(Base):
    def test_a_folder_with_no_readme_and_nothing_el_stamped_is_from_before_el(self):
        self.assertEqual(order.child_status(self.root / "2026-03-04-login-retry-fix")[0], "legacy")

    def test_case_list_counts_them_and_draws_no_broken_lines(self):
        code, out, err = run("case", "list")
        self.assertEqual(code, 0, err)
        self.assertNotIn("BROKEN", out)
        self.assertNotIn("login-retry-fix", out, "counted, not listed — `--all` names them")
        self.assertIn("1 open", out)
        self.assertIn("1 closed", out)
        self.assertIn("4 legacy", out)
        self.assertIn("login-retry-fix", run("case", "list", "--all")[1])

    def test_a_case_el_wrote_that_lost_its_readme_is_still_broken(self):
        live = next(p for p in self.root.iterdir() if p.name.endswith("release-check"))
        (live / "README.md").unlink()
        self.assertEqual(order.child_status(live)[0], "broken")
        self.assertIn("BROKEN", run("case", "list")[1])


class ACaseElCannotReadYet(Base):
    def test_the_entry_names_it_and_does_not_pour_its_files(self):
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn(f"case in hand: {self.legacy.name} — from before el", out)
        self.assertIn("el migrate", out)
        self.assertNotIn("## Current state", out, "the raw files stay on disk")
        self.assertNotIn("confirm the datasource", out)
        self.assertIn("release-check", out, "el's own open case is named with the switch")
        self.assertIn("el case use", out)

    def test_bare_migrate_still_finds_it(self):
        code, out, err = run("migrate")
        self.assertEqual(code, 0, err)
        self.assertIn(self.legacy.name, out + err)

    def test_switching_to_an_el_case_shows_it_whole(self):
        run("case", "use", "release-check")
        out = run()[1]
        self.assertIn("# release check", out)
        self.assertNotIn("from before el", out.split("\n")[0])


class OneDate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_a_name_that_starts_with_a_date_keeps_one_date(self):
        code, out, err = run("case", "new", "2026-08-31 prod release notes", "--goal", "g")
        self.assertEqual(code, 0, err)
        names = [p.name for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir()]
        self.assertEqual(len(names), 1)
        self.assertRegex(names[0], r"^\d{4}-\d{2}-\d{2}-prod-release-notes$")


if __name__ == "__main__":
    unittest.main()
