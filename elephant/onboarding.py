"""The onboarding block — what an agent's instruction file carries so that any agent starts the Elephant way.

The owner's word, 2026-09-25: «bake the onboarding into el; if Elephant updated, the onboarding must update too; el
decides where to write it — where the current onboarding is, it writes there; where there is none, it finds the place».
A pasted copy goes stale silently (the block changed three times in three days, and every project kept the version of
the day it was pasted), so the copy el writes sits between two marks with a fingerprint of its own text:

    <!-- elephant onboarding 1.24.0 · 3f2a9c1b7d20 — … -->
    ## Elephant — память работы в `.cases/`
    …
    <!-- /elephant onboarding -->

The fingerprint is of the text, not the version: a release that leaves the block as it was changes nothing. The entry
compares the copy with the block el ships and refreshes a stale copy itself (like the Links of README); a copy whose
text no longer matches its own mark was edited by hand and is named, not overwritten; a block pasted by hand (the
heading without marks) is named with the command that takes it under marks. Only the lines between the marks are
ever written — the rest of the file stays byte for byte. `EL_ONBOARDING=0` switches the automatic part off.
"""
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from . import __version__, knowledge

END = "<!-- /elephant onboarding -->"
BEGIN_RE = re.compile(r"^<!-- elephant onboarding (\S+) · ([0-9a-f]{12})\b.*-->$")
LEGACY_HEAD_RE = re.compile(r"^## Elephant — память работы")
# the instruction files agents read, in the order el looks: Claude Code · the open AGENTS.md (Codex, Cursor, Copilot, …) · Gemini
FILES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md")


def enabled() -> bool:
    return os.environ.get("EL_ONBOARDING", "1") != "0"


def block() -> str:
    return knowledge.ONBOARDING_BLOCK.strip("\n")


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip("\n").encode("utf-8")).hexdigest()[:12]


def marked() -> List[str]:
    b = block()
    head = (f"<!-- elephant onboarding {__version__} · {fingerprint(b)} — written by el: `el onboarding` refreshes it, "
            f"your own lines go outside these marks -->")
    return [head, *b.split("\n"), END]


@dataclass
class Found:
    path: Path      # the file as the project names it (CLAUDE.md may be a link to AGENTS.md)
    state: str      # current · stale · edited · pasted · broken
    start: int      # the first line of the block (0-based)
    end: int        # one past its last line
    version: str    # the el version in the mark, "" for a pasted block


def _locate(lines: List[str]) -> Optional[Tuple[str, int, int, str]]:
    for i, ln in enumerate(lines):
        m = BEGIN_RE.match(ln.strip())
        if not m:
            continue
        j = next((k for k in range(i + 1, len(lines)) if lines[k].strip() == END), None)
        if j is None:
            return "broken", i, i + 1, m.group(1)
        body = "\n".join(lines[i + 1:j])
        if fingerprint(body) != m.group(2):
            state = "edited"
        elif fingerprint(body) != fingerprint(block()):
            state = "stale"
        else:
            state = "current"
        return state, i, j + 1, m.group(1)
    for i, ln in enumerate(lines):
        if LEGACY_HEAD_RE.match(ln):  # the block pasted by hand from ONBOARDING.md: it runs to the next heading or rule
            j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(("# ", "## ")) or lines[k].strip() == "---"),
                     len(lines))
            while j > i + 1 and not lines[j - 1].strip():
                j -= 1
            return "pasted", i, j, ""
    return None


def scan(project: Path) -> List[Found]:
    """Every instruction file of the project that carries the block (marked or pasted); a link counts once."""
    found, seen = [], set()
    for name in FILES:
        p = project / name
        if not p.is_file():
            continue
        real = p.resolve()
        if real in seen:
            continue
        seen.add(real)
        where = _locate(p.read_text(encoding="utf-8").split("\n"))
        if where:
            found.append(Found(p, *where))
    return found


def harness_file() -> Optional[str]:
    """The instruction file the agent running el reads — told by the variables its harness sets."""
    agent = (os.environ.get("AI_AGENT") or "").lower()
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT") or agent.startswith("claude"):
        return "CLAUDE.md"
    if agent.startswith("gemini") or os.environ.get("GEMINI_CLI"):
        return "GEMINI.md"
    if agent.startswith("codex") or any(k.startswith("CODEX_") for k in os.environ):
        return "AGENTS.md"
    return None


def choose(project: Path) -> str:
    """Where a project with no block gets one: the file the running agent reads; else an instruction file that
    exists; else AGENTS.md — the open file most agents read."""
    return harness_file() or next((n for n in FILES if (project / n).is_file()), "AGENTS.md")


def _write(path: Path, text: str):
    real = path.resolve()  # a link stays a link: the file it points at is written
    fd, tmp = tempfile.mkstemp(dir=real.parent, prefix=f".{real.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, real)


def _replace(f: Found):
    lines = f.path.read_text(encoding="utf-8").split("\n")
    _write(f.path, "\n".join(lines[:f.start] + marked() + lines[f.end:]))


def write(project: Path) -> List[str]:
    """`el onboarding` — where the block is, it is refreshed there (edited, stale, pasted or broken — all rewritten from el,
    the explicit command is the owner's say-so); where it is nowhere, el finds the place and adds it at the end."""
    said = []
    found = scan(project)
    for f in found:
        if f.state == "current":
            said.append(f"{f.path.name}: the Elephant block is current — nothing written")
            continue
        what = {"stale": f"refreshed ({f.version} → {__version__}: the block el ships changed)",
                "edited": "rewritten from el (it had been edited by hand — keep your own lines outside the marks)",
                "pasted": f"a block pasted by hand, lines {f.start + 1}–{f.end}, now under marks — el keeps it current from here",
                "broken": "the begin mark had no end — rewritten whole"}[f.state]
        _replace(f)
        said.append(f"onboarding → {f.path.name}: {what}; the rest of the file untouched")
    if found:
        return said
    name = choose(project)
    path = project / name
    if path.exists():
        text = path.read_text(encoding="utf-8").rstrip("\n")
        _write(path, text + "\n\n" + "\n".join(marked()) + "\n")
        said.append(f"onboarding → {name}: the Elephant block added at the end, between marks (your text above untouched) — "
                    f"outside .cases/; `el` keeps it current")
    else:
        _write(path, "\n".join(marked()) + "\n")
        said.append(f"onboarding → {name}: created with the Elephant block between marks — outside .cases/; `el` keeps it current")
    return said


def refresh(project: Path) -> List[str]:
    """On entry: a stale copy el wrote is refreshed in place — said once, like README's Links. Never raises."""
    if not enabled():
        return []
    said = []
    try:
        for f in scan(project):
            if f.state == "stale":
                _replace(f)
                said.append(f"onboarding refreshed in {f.path.name}: the block el ships changed ({f.version} → {__version__}) — "
                            f"only the lines between the marks")
    except OSError as e:
        said.append(f"onboarding not refreshed — {e}")
    return said


def order_lines(project: Path) -> List[str]:
    """Order: a copy el cannot keep current — edited by hand, pasted by hand, or broken — with the command. Reads only."""
    if not enabled():
        return []
    lines = []
    try:
        for f in scan(project):
            if f.state == "edited":
                lines.append(f"the Elephant block in {f.path.name} was edited by hand — el cannot keep it current: el onboarding "
                             f"rewrites it from el (your own lines go outside the marks)")
            elif f.state == "pasted":
                lines.append(f"{f.path.name}:{f.start + 1} carries an Elephant block pasted by hand — el cannot keep it current: "
                             f"el onboarding puts it under marks in place")
            elif f.state == "broken":
                lines.append(f"the Elephant block in {f.path.name} has a begin mark and no end — el onboarding rewrites it whole")
    except OSError:
        pass
    return lines
