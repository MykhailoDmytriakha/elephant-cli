#!/usr/bin/env python3
"""Scan what goes to git for the owner's private terms — the section `## Private terms` of the local CLAUDE.md.

The owner's word, 2026-09-22 and 2026-09-25: business data of live cases never goes into files git carries — code, tests,
the help doses, RULES, ONBOARDING, commit messages; examples there are neutral. The terms themselves live only in the local,
gitignored CLAUDE.md (a list in git would be the leak); this script carries the rule of the search, never a term.

  python3 scripts/check_private_terms.py            the working tree: tracked files + new files git does not ignore
  python3 scripts/check_private_terms.py --staged   what the next commit carries (the index)
  installed as .git/hooks/pre-commit (a link to this file) it checks the index by itself and stops a commit with a hit
  every mode also reads the messages of the commits not pushed yet (@{u}..HEAD)

A term is found as a substring, case-insensitive; `<term>` — as a whole word, for a short term that sits inside ordinary
words. Exit 0 clean · 1 a term found (file:line printed) · 2 nothing to check against — an empty list is not a clean result.
"""
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
TERMS_FILE = ROOT / "CLAUDE.md"
SECTION = "## Private terms"
SKIP_PREFIXES = ("feedback/",)  # the pool is read and deleted, never kept


def load_terms(path: Path = TERMS_FILE) -> Optional[List[str]]:
    """The lines of `## Private terms`: one term each, `#` comments, blank lines and the header line skipped.
    None when there is no file or no section — nothing to check against."""
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if SECTION not in lines:
        return None
    block = lines[lines.index(SECTION) + 1:]
    terms = []
    for ln in block:
        if ln.startswith("## "):
            break
        t = ln.strip().lower()
        if t and not t.startswith("#") and not ln.startswith("One per line"):
            terms.append(t)
    return terms


def found(term: str, text: str) -> bool:
    """`text` is lowercased. `<abc>` catches `abc`, `abc-prod`, `/v3/abc` and not `xyzabcdef`; any other term — a substring."""
    if term.startswith("<") and term.endswith(">") and len(term) > 2:
        return re.search(rf"(?<![a-z0-9]){re.escape(term[1:-1])}(?![a-z0-9])", text) is not None
    return term in text


def hits(text: str, terms: List[str]) -> List[Tuple[int, str, str]]:
    """(line number, term, the line) for every term on every line of `text`."""
    out = []
    for n, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for t in terms:
            if found(t, low):
                out.append((n, t, line.strip()))
    return out


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def files(staged: bool) -> List[str]:
    if staged:
        names = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode("utf-8").split("\0")
    else:
        names = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode("utf-8").split("\0")
    return [n for n in names if n and not n.startswith(SKIP_PREFIXES)]


def read(rel: str, staged: bool) -> Optional[str]:
    try:
        data = _git("show", f":{rel}") if staged else (ROOT / rel).read_bytes()
    except (OSError, subprocess.CalledProcessError):
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None  # a binary file: nothing a reader copies from


def unpushed_messages() -> Optional[List[Tuple[str, str]]]:
    """(short hash, message) of the commits not pushed yet; None when the branch has no upstream."""
    try:
        _git("rev-parse", "--abbrev-ref", "@{u}")
    except subprocess.CalledProcessError:
        return None
    raw = _git("log", "--format=%h%x00%B%x1e", "@{u}..HEAD").decode("utf-8")
    out = []
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if rec:
            h, _, msg = rec.partition("\0")
            out.append((h, msg))
    return out


def main(argv: List[str]) -> int:
    staged = "--staged" in argv or Path(sys.argv[0]).name == "pre-commit"
    terms = load_terms()
    if not terms:
        print(f"nothing checked: no `{SECTION}` list in {TERMS_FILE.name} on this machine — an empty list is not a clean result")
        return 2
    found_any, n_files = [], 0
    for rel in files(staged):
        text = read(rel, staged)
        if text is None:
            continue
        n_files += 1
        found_any += [f"{rel}:{n}: «{t}» — {line[:120]}" for n, t, line in hits(text, terms)]
    messages = unpushed_messages()
    for h, msg in messages or []:
        found_any += [f"commit {h} message:{n}: «{t}» — {line[:120]}" for n, t, line in hits(msg, terms)]
    what = "the index (the next commit)" if staged else "the working tree"
    msgs = f" and {len(messages)} unpushed commit message(s)" if messages is not None else " (no upstream: commit messages not read)"
    if found_any:
        print(*found_any, sep="\n")
        print(f"{len(found_any)} hit(s) — {what}{msgs}: rephrase with a neutral example of the same form "
              f"(CLAUDE.md: «Бизнес-данные не едут в git»)")
        return 1
    print(f"clean: {n_files} file(s) of {what}{msgs} checked against {len(terms)} term(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
