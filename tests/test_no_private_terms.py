"""The owner's word 2026-09-22: business data of live cases never goes into files git carries (CLAUDE.md, the
doses, RULES, tests, code) — examples there are neutral. The terms themselves cannot be listed here, a list in
git would be the leak: they live in the section `## Private terms` of CLAUDE.md, which is local and gitignored, and this test
reads it where it exists. Absent file (a fresh clone) → skipped."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TERMS = ROOT / "CLAUDE.md"


def _terms():
    """The lines of the `## Private terms` section: one term each, `#` comments and blank lines skipped."""
    lines = TERMS.read_text(encoding="utf-8").splitlines()
    if "## Private terms" not in lines:
        return []
    block = lines[lines.index("## Private terms") + 1:]
    return [ln.strip().lower() for ln in block
            if ln.strip() and not ln.lstrip().startswith("#") and not ln.startswith("One per line")]


class NoPrivateTerms(unittest.TestCase):
    @unittest.skipUnless(TERMS.is_file(), "no local CLAUDE.md on this machine")
    def test_tracked_files_carry_no_private_term(self):
        try:
            listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                                    capture_output=True, check=True).stdout.decode("utf-8").split("\0")
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        terms, found = _terms(), []
        for rel in filter(None, listed):
            path = ROOT / rel
            if not path.is_file() or rel.startswith("feedback/"):  # the pool is read and deleted, never kept
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
            except UnicodeDecodeError:
                continue
            found += [f"{rel}: «{t}»" for t in terms if t in text]
        self.assertEqual(found, [], "business data in files git carries — rephrase with a neutral example")


if __name__ == "__main__":
    unittest.main()
