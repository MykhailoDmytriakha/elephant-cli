"""The owner's word 2026-09-22: business data of live cases never goes into files git carries (CLAUDE.md, the
doses, RULES, tests, code) — examples there are neutral. The terms themselves cannot be listed here, a list in
git would be the leak: they live in the section `## Private terms` of CLAUDE.md, which is local and gitignored.
The search itself lives in scripts/check_private_terms.py (2026-09-25: a script the owner runs before a commit, or a
pre-commit hook); this test runs the same search over the working tree. Absent list (a fresh clone) → skipped."""
import importlib.util
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_private_terms", ROOT / "scripts" / "check_private_terms.py")
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


class NoPrivateTerms(unittest.TestCase):
    @unittest.skipUnless(check.load_terms(), "no local `## Private terms` list on this machine")
    def test_tracked_files_carry_no_private_term(self):
        try:
            listed = check.files(staged=False)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        terms, found = check.load_terms(), []
        for rel in listed:
            text = check.read(rel, staged=False)
            if text is not None:
                found += [f"{rel}:{n}: «{t}»" for n, t, _ in check.hits(text, terms)]
        self.assertEqual(found, [], "business data in files git carries — rephrase with a neutral example")


class TheSearch(unittest.TestCase):
    """The rule of the search on invented terms — never a real one here."""

    def test_a_substring_term_is_found_inside_a_word_case_insensitive(self):
        self.assertEqual(check.hits("see Zorblax-v2 notes\nnothing\n", ["zorblax"]), [(1, "zorblax", "see Zorblax-v2 notes")])

    def test_a_whole_word_term_skips_ordinary_words(self):
        terms = ["<qx>"]
        self.assertTrue(check.hits("the QX release", terms))
        self.assertTrue(check.hits("path /v3/qx and qx-prod", terms))
        self.assertEqual(check.hits("class ItemQxLength is fine: aqxb", terms), [])

    def test_the_list_is_read_from_its_section_only(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "CLAUDE.md"
            p.write_text("# x\n\nzorblax is mentioned above the list\n\n## Private terms\nOne per line, case-insensitive.\n"
                         "# a comment\nzorblax\n<qx>\n", encoding="utf-8")
            self.assertEqual(check.load_terms(p), ["zorblax", "<qx>"])
            p.write_text("# x\n", encoding="utf-8")
            self.assertIsNone(check.load_terms(p), "no section: nothing to check against, not «clean»")


if __name__ == "__main__":
    unittest.main()
