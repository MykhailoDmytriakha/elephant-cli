"""Storage layer: find `.cases/`, pick the case in hand, read and write the three files safely.

Rules touched: L1–L3 (layout), S1–S4 (stamp on every write, rebuild on mismatch), C7–C9.
The case "in hand": `--case` flag > EL_CASE env > the case this session holds > the open case whose JOURNAL.md changed
most recently (and the session holds it from then on). The one thing kept between commands is which case a session
holds — outside the project, keyed by the session id the harness gives (see `hold`).
"""
import datetime
import difflib
import errno
import hashlib
import json
import math
import os
import re
import shlex
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, NamedTuple

from . import grammar, recover, stamp

CASES_DIR = ".cases"
FILES = ("README.md", "TODO.md", "JOURNAL.md")
# L10 — people cards: one markdown per person the cases deal with, `summary:` as line 2 (role · what they own ·
# how to reach). Inside .cases/ on purpose: a card is personal data and hides with the cases (the owner's word,
# 2026-09-16). Not a case, never scanned as one; cases link to a card like to any file.
PEOPLE_DIR = "people"
# L2 naming policy: a case dir is `YYYY-MM-DD-<slug>`. Detection is case-INsensitive and imposes no
# word count: the invariant is the date prefix plus a non-empty portable slug (letters, digits,
# hyphens). `case new` normalizes NEW names to lowercase; existing dirs are never renamed.
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
CASE_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")


def reject_reason(name: str):
    """Why a directory name is not a case name — None when it is one (used for diagnostics)."""
    if CASE_NAME_RE.match(name):
        return None
    if not DATE_PREFIX_RE.match(name):
        return "no YYYY-MM-DD- date prefix"
    rest = name[11:]
    if not rest:
        return "empty name after the date"
    return f"invalid characters in `{rest}` — allowed: letters, digits, hyphen-separated words"


EXIT_MEANING = {1: "internal error", 2: "wrong usage", 3: "rule violation, nothing was written",
                4: "precondition not met, nothing was written"}


class StoreError(Exception):
    """A refusal: message, exit code naming the failure class (C5), and a safe recovery command."""

    def __init__(self, message: str, code: int = 1, recovery: str = "", meaning: str = ""):
        super().__init__(message)
        self.code = code
        self.recovery = recovery
        self.meaning = meaning  # the legend's words where the class's own would mislead (check: «nothing was written»)


@dataclass
class WriteReport:
    path: Path
    warnings: List[grammar.Finding] = field(default_factory=list)
    recovered: Optional[Path] = None  # set when a mismatched file was rebuilt (S4)
    recovered_lines: int = 0
    bypassed: bool = False  # the file had been written bypassing `el` (stamp mismatch)
    rebuilt: Optional[str] = None  # the rebuild the system did not let el write: what a read takes instead of the file


# ---- root and cases ------------------------------------------------------------------------------
def find_root(start: Optional[Path] = None) -> Path:
    """Walk up from `start` (cwd) until a `.cases/` directory is found (C9)."""
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        if (d / CASES_DIR).is_dir():
            return d / CASES_DIR
    # root mode writes README.md here, so it is named only where none is (the polygon, 2026-10-07: Haiku took the
    # --root advice in a project with its own README.md and walked into the next refusal)
    root = ("" if (here / "README.md").exists() else
            " — or, if THIS folder is the project itself: el case new --root \"name\" --goal \"…\"")
    raise StoreError(f"no `{CASES_DIR}/` directory found from {here} upwards", 4,
                     recovery=f"cd to the project root, or start: el case new \"name\" --goal \"…\"{root}")


def is_case_dir(p: Path) -> bool:
    """A case folder: a real folder with a case name — a link to a folder is an artifact, never a case (Codex, 2026-11-05:
    a link named like a case held its parent open as a «nested case» no command could reach)."""
    return p.is_dir() and not p.is_symlink() and CASE_NAME_RE.match(p.name) is not None


DEPENDENCY_DIRS = ("node_modules", "site-packages", "__pycache__")  # a tree someone else wrote: material, never the case's prose


def case_files(top: Path, suffix: Optional[str] = None, skip: Tuple[str, ...] = ("legacy",)) -> List[Path]:
    """Every file under `top` that el reads as the case's own, by one walk: no hidden folder, no dependency tree, no
    nested case, never through a link to a folder. A link to a folder is one artifact, not a tree (two live reports,
    2026-11-01: an artifact folder linked to node_modules under another name — el walked it, the README inventoried
    33 000 lines of a dependency tree and the entry printed 22 000 Order lines). `os.walk` does not follow folder
    links on any Python; the walk says so, not the version (rglob changed its mind in 3.13)."""
    found: List[Path] = []
    if top.is_symlink():
        return found  # a link to a folder given as the start: os.walk would enter it (Codex, 2026-11-05)
    for dirpath, dirnames, filenames in os.walk(top, followlinks=False):
        here = Path(dirpath)
        dirnames[:] = sorted(n for n in dirnames if not n.startswith(".") and n not in DEPENDENCY_DIRS and n not in skip
                             and not (here / n).is_symlink() and not CASE_NAME_RE.match(n))
        found += [here / n for n in sorted(filenames) if not suffix or n.lower().endswith(suffix)]
    return found


def scan(root: Path):
    """Every case folder under root plus the case-LIKE directories that were rejected, with reasons.

    Rejected means: at the root level — any visible directory that is not a valid case name; inside
    a case — a directory with a date prefix but an invalid tail (content folders like `docs/` are
    not case-like and are not reported). Nothing is ever silently ignored (bug report 2026-08-31).
    """
    found: List[Path] = []
    rejected: List[tuple] = []

    def walk(d: Path, top: bool):
        for child in sorted(d.iterdir()):
            if (not child.is_dir() or child.is_symlink() or child.name.startswith(".")
                    or child.name in ("node_modules", "phases")):  # a link to a folder is an artifact, never a case
                continue
            if top and child.name == PEOPLE_DIR:
                continue  # L10: the people cards — a known folder, not a case-like one
            if is_case_dir(child):
                found.append(child)
                walk(child, False)
            elif top or DATE_PREFIX_RE.match(child.name):
                rejected.append((child, reject_reason(child.name)))

    walk(root, True)
    return found, rejected


def people_cards(root: Path) -> List[Path]:
    """The people cards of this workspace (L10): `.cases/people/*.md`, sorted."""
    d = root / PEOPLE_DIR
    return sorted(p for p in d.glob("*.md")) if d.is_dir() else []


def project_case(root: Path):
    """Root mode: the project folder itself is the top case when all three files live beside `.cases/`."""
    parent = root.parent
    if all(file_path(parent, n).exists() for n in FILES):
        return parent
    return None


def all_cases(root: Path) -> List[Path]:
    project = project_case(root)
    return ([project] if project else []) + scan(root)[0]


def file_path(case: Path, name: str) -> Path:
    """The single resolver for the three case files: canonical name first, any-case legacy second.

    Legacy cases may hold `todo.md` / `journal.md`; those are read and written in place, never
    renamed. When the file does not exist at all, the canonical path is returned for creation.
    """
    # Real stored names via iterdir, not `.exists()`: on case-insensitive filesystems (macOS APFS)
    # `(case / "JOURNAL.md").exists()` is true for `journal.md` too, and writing through the
    # canonical spelling would silently rename the user's file.
    if case.is_dir():
        insensitive = None
        for child in case.iterdir():
            if not child.is_file():
                continue
            if child.name == name:
                return child
            if child.name.lower() == name.lower():
                insensitive = child
        if insensitive is not None:
            return insensitive
    return case / name


def read(case: Path, name: str) -> str:
    p = file_path(case, name)
    if not p.exists():
        raise StoreError(f"{p} is missing (L3)", 4, recovery="el doctor")
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:  # a refusal with its door, never a traceback on every entry (Codex, 2026-10-08)
        raise StoreError(f"{p} is not UTF-8 text (byte {e.start}) — el writes UTF-8 only, so something else wrote it", 4,
                         recovery=f"iconv -f latin1 -t utf-8 {shlex.quote(str(p))} > {shlex.quote(str(p) + '.utf8')} && "
                                  f"mv {shlex.quote(str(p) + '.utf8')} {shlex.quote(str(p))} && el check")


def todo_of(case: Path) -> grammar.Todo:
    return grammar.parse_todo(read(case, "TODO.md"))


def is_open(case: Path) -> bool:
    """A case is open until `el done` writes `- closed: …` into README State."""
    try:
        text = read(case, "README.md")
    except StoreError:
        return False
    return not grammar.is_closed(text)


def load(case: Path, name: str):
    """Read one of the three files through the stamp door: verify (rebuild on mismatch), return (body, report)."""
    report = check_stamp(case, name)
    body, _ = stamp.split(report.rebuilt if report.rebuilt is not None else read(case, name))
    return body, report


def _rel(case: Path, root: Path) -> str:
    return case.relative_to(root).as_posix() if case.is_relative_to(root) else case.name  # the project case sits above .cases/


def case_arg(case: Path, root: Path) -> str:
    """How a printed command names this case so that it runs as printed: the folder name when it resolves to this very case,
    else its path from .cases/ (Codex, 2026-10-14: two nested cases of one name — the printed `--case <name>` was refused)."""
    try:
        if resolve_case(root, case.name).resolve() == case.resolve():
            return case.name
    except StoreError:
        pass
    rel = _rel(case, root)
    return rel if "/" in rel else f".cases/{rel}"  # a top case shares its name with a nested one: a path, not a name


def resolve_case(root: Path, name: Optional[str]) -> Path:
    """Find a case by name (exact folder name, nested allowed) or by unique suffix."""
    cases = all_cases(root)
    project = project_case(root)
    if project is not None and name in (".", "root", project.name):
        return project
    if name and "/" in name:  # a path from .cases/ names a nested case exactly, whatever its siblings are called
        want = name.strip("/").removeprefix(".cases/")
        hit = [c for c in cases if c.is_relative_to(root) and c.relative_to(root).as_posix() == want]
        if hit:
            return hit[0]
    exact = [c for c in cases if c.name == name] or [c for c in cases if name and c.name.lower() == name.lower()]
    if len(exact) > 1:  # two cases of one name in different parents: a silent first pick wrote into the wrong one (Codex, 2026-10-05)
        raise StoreError(f"`{name}` names several cases: {', '.join(_rel(c, root) for c in exact)} — "
                         f"name one by its path: el --case <path> …", 2)
    if exact:
        return exact[0]
    partial = [c for c in cases if name and c.name.lower().endswith(name.lower())]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise StoreError(f"`{name}` names several cases: {', '.join(_rel(c, root) for c in partial)} — "
                         f"name one by its path: el --case <path> …", 2)
    # a name typed by hand from a transliterated one drifts by a letter (a live Codex session, 2026-10-19: `vsekh` for the
    # `vseh` el wrote — eight such refusals): the nearest name is said, never taken — a wrong case is a write elsewhere
    near = difflib.get_close_matches(name or "", [_rel(c, root) for c in cases], n=1, cutoff=0.85)
    word = ("." if project is not None and near and near[0] == _rel(project, root) else shlex.quote(near[0])) if near else ""
    raise StoreError(f"no case named `{name}` under {root}" + (f" — the nearest: `{near[0]}`" if near else ""), 4,
                     recovery=(f"el --case {word} … · every case: el case list" if near else "el case list"))


# ---- the hand of a session --------------------------------------------------------------------------
# Feedback 2026-09-27: two sessions in one working tree, each with its own case — session B wrote case b, session A then
# opened case a, and B's bare `todo done` landed in a: the hand followed the freshest journal, which in a shared tree is
# another agent's. Many agents on one tree is the model (each writes its own leaf), so the hand belongs to the session:
# the case it last wrote to, or took (`case new` · `spawn` · `case use`), or first picked up. Kept outside the project,
# in a temp folder, one line per session and project — not a config, nothing in git, gone with the machine's temp.
# A harness that gives no session id (EL_SESSION sets one by hand) keeps the old rule: the case a write was last aimed at.
# the harness's own id first, the innermost harness first (Codex run from Claude Code); EL_SESSION only where the harness
# names no session (VS Code Copilot, a terminal by hand) — an agent that sets it inside a harness that names one is the
# same hand still (the polygon, 2026-10-10: Codex set EL_SESSION, and its own acceptance read «another session»)
# GitHub Copilot CLI runs each command in a fresh shell with COPILOT_CLI=1 and COPILOT_AGENT_SESSION_ID=<uuid> (a live
# report 2026-10-20, and @github/copilot 1.0.73: its runtime builds the shell env with both — the docs name neither)
SESSION_ENVS = ("CODEX_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "COPILOT_AGENT_SESSION_ID", "EL_SESSION")
# who is writing, as the harness says it (measured 2026-10-05: Claude Code sets CLAUDECODE and CLAUDE_CODE_SESSION_ID,
# Codex sets CODEX_VERSION and CODEX_SESSION_ID; neither names the model — the agent says it once: `el sign "<model>"`)
# VS Code sets COPILOT_AGENT=1 in the terminals its Copilot agent runs commands in (microsoft/vscode PR #316267, VS Code
# 1.121, 2026-05-13) and gives no session id (the owner's word 2026-10-06: an item done in Copilot was signed
# `harness ? · model ? · session ?`); last in the list — the outer harness, should a Claude Code or Codex run inside it
HARNESSES = (("CODEX_SESSION_ID", "OpenAI Codex"), ("CODEX_VERSION", "OpenAI Codex"),
             ("CLAUDE_CODE_SESSION_ID", "Anthropic Claude Code"), ("CLAUDECODE", "Anthropic Claude Code"),
             ("COPILOT_CLI", "GitHub Copilot CLI"), ("COPILOT_AGENT", "GitHub Copilot"))


def _session_raw() -> str:
    for key in SESSION_ENVS:
        val = re.sub(r"[^A-Za-z0-9]", "", os.environ.get(key) or "")
        if val:
            return val
    return ""


def clean_part(value: str, limit: int = 60) -> str:
    """One part of a signature as el will write it: one line, no `·` (el joins the parts with it and reads them back by it),
    at most `limit` chars. Every source — `el sign`, EL_MODEL, the file — passes here (Codex, 2026-10-05: a newline in
    EL_MODEL wrote an `accepted:` line into TODO; `M · session x` forged the doer's session)."""
    return " ".join((value or "").replace("·", " ").split())[:limit].strip()


def session_id() -> str:
    """The session this command runs in, as the agent's harness says it (Codex sets CODEX_SESSION_ID, Claude Code
    CLAUDE_CODE_SESSION_ID; EL_SESSION names one where the harness does not) — 8 chars, or "" when nothing says.
    Provenance, not proof: a subagent shares its parent's session — so the record says what el saw, never more."""
    for key in SESSION_ENVS:
        val = re.sub(r"[^A-Za-z0-9]", "", os.environ.get(key) or "")
        if val:
            return val[:8]
    return ""


def harness() -> str:
    """«Provider Tool» of the agent running this command, from the harness's own variables; "" when nothing says."""
    return next((name for key, name in HARNESSES if os.environ.get(key)), "")


def _hands_base() -> Optional[Path]:
    """The folder of the session's own memory — hand, signature, walls, asks: EL_HANDS_DIR or the temp folder; None where
    no temp folder can be written (a read-only sandbox — Codex, 2026-11-08: the entry died in `tempfile` before it read a
    line). Memory that cannot be kept is not kept: the hand falls back to the case a write was last aimed at."""
    env = os.environ.get("EL_HANDS_DIR")
    if env:
        return Path(env)
    try:
        return Path(tempfile.gettempdir()) / "elephant-hands"
    except OSError:
        return None


def _sign_file() -> Optional[Path]:
    """The session's signature lives by the session, not by the project: one session is one model wherever it works."""
    key = next((f"{k}={os.environ[k]}" for k in SESSION_ENVS if re.sub(r"[^A-Za-z0-9]", "", os.environ.get(k) or "")), "")
    if not key:  # the exact id, hashed: `shared01-A` and `shared01-B`, `abc-def01` and `abcdef01` are two sessions (Codex, 2026-10-05)
        return None
    base = _hands_base()
    return base / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}-sign" if base is not None else None


def _walls_file() -> Optional[Path]:
    """The session's refusals, kept by the session like its signature: el sees its own walls only here."""
    f = _sign_file()
    return f.with_name(f.name[:-len("-sign")] + "-walls.jsonl") if f is not None else None


WALL_TEXT_LINES = 200  # a refusal is kept whole for the report; a bound only against a runaway output


def wall_key(text: str, numbers: bool = False) -> str:
    """One wall, whatever its numbers, quoted words and paths: `phase 2 is missing` and `phase 5 is missing` are the same
    wall, so are two missing files; a refusal whose first line only announces a list (`cannot close phase N:`) is keyed
    by the list's first line too, so two different blockers are two walls (Codex review, 2026-10-07). `numbers` asks
    for the same refusal, not its kind: the first line as printed, its quotes and paths too — a number lives in them as
    often as outside (the second hand, 2026-11-07: «`el todo done 4.1 …`» and «`… 9.3 …`» read as one with quotes blanked)."""
    lines = [ln for ln in (text or "").split("\n") if ln.strip() and not re.match(r"\s*exit \d = ", ln)]  # not the legend
    first = lines[0] if lines else ""
    if first.rstrip().endswith(":") and len(lines) > 1:
        first = first + " " + lines[1].strip()
    first = " ".join(first.split())  # spaces are no part of a wall, in either key (the second hand, round 2, 2026-11-07)
    if numbers:
        return first
    line = re.sub(r"`[^`]*`|«[^»]*»|\"[^\"]*\"|'[^']*'", "…", first)
    line = re.sub(r"[\w.-]*/[\w./-]*|\b[\w-]+\.(?:md|pdf|png|jpe?g|txt|json|csv|py|sh)\b", "PATH", line)
    # a number is one N, its fraction and its dots too: a lock held 0 s and 0.01 s is one wall (the second hand, round 3)
    return re.sub(r"\d+(?:[.,]\d+)*", "N", line)[:160]


def wall_kinds(w: dict, numbers: bool = False) -> Optional[str]:
    """A kept wall's key, from its own text — the key it was stored with was made by the rules of the el that kept it
    (spaces kept, `N.N` for a fraction); a record without text falls back to that key, spaces aside, and is never the
    same refusal (its first line is unknown). One reader for both counts: the question and the maintainer's report."""
    if isinstance(w.get("text"), str):
        return wall_key(w["text"], numbers)
    k = w.get("key")
    return None if numbers or not isinstance(k, str) else re.sub(r"N(?:[.,]N)*", "N", " ".join(k.split()))


# When does a wall come again? Measured 2026-11-07 on 306 repeats of one kind of wall in 146 sessions (17 on this machine,
# 129 of the polygon): 67 came within 5 minutes — an agent circling on one refusal — and 229 an hour and more apart — the
# same kind of refusal on the next item of a long session (a Codex session of twelve days had met «N.N is open — a brief is
# for accepting done work» 31 times, once per item, and el asked «the same wall 31 times» on the first brief of 330.9);
# between 5 and 30 minutes, 10. The question goes to the circling: the same refusal with its own numbers, or its kind again
# within this many minutes. The kind's count over the session stays — the maintainer's signal (el feedback --wall).
WALL_RECENT_MIN = 10


class WallCount(NamedTuple):
    again: int   # this refusal met again: with the same numbers this session, or its kind within WALL_RECENT_MIN — 0 unknown
    exact: bool  # `again` counts the same numbers (else the kind, lately)
    total: int   # its kind over the whole session


def _locked(fh) -> None:
    """An exclusive lock on the walls file while a record is appended and counted: two el processes of one session (a
    subagent beside its parent) would otherwise interleave or both count twice. POSIX only; elsewhere unlocked."""
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    except (ImportError, OSError):
        pass


def record_wall(argv: List[str], code: int, text: str, case: Optional[Path] = None, call: Optional[dict] = None) -> WallCount:
    """Keep one refusal of this session (the polygon, 2026-10-07: thirty-odd walls in nineteen sessions, not one
    `el feedback` — the agents told the owner instead, and el, which printed every refusal, kept none of them).
    Returns how often it came again — this one included — and its kind over the session (WallCount); zeros when no
    session is known. Never raises: a damaged walls file must not mask the refusal it was meant to keep."""
    none = WallCount(0, False, 0)
    try:
        f = _walls_file()
        if f is None:
            return none
        lines = (text or "").split("\n")
        rec = {"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "argv": [str(a) for a in argv], "code": code,
               "text": "\n".join(lines[:WALL_TEXT_LINES]), "key": wall_key(text)}
        if case is not None:  # the case the call was for and what it asked, as el resolved and parsed them — not read back
            rec["case"] = str(case.resolve())  # from argv later: a suffix, `--case` after the command, `01` (Codex, 2026-11-12)
        rec.update({k: str(v) for k, v in (call or {}).items() if v is not None})
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a+", encoding="utf-8") as fh:
            _locked(fh)
            fh.seek(0, 2)
            if fh.tell():  # a record cut off by a killed process must not swallow this one
                fh.seek(fh.tell() - 1)
                last = fh.read(1)
                fh.seek(0, 2)
                if last != "\n":
                    fh.write("\n")
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
        kind = [w for w in session_walls() if wall_kinds(w) == wall_key(text)]
        exact = wall_key(text, numbers=True)
        same = sum(1 for w in kind if wall_kinds(w, True) == exact)
        now = datetime.datetime.strptime(rec["ts"], "%Y-%m-%d %H:%M")

        def lately(w) -> bool:
            try:
                gap = (now - datetime.datetime.strptime(str(w.get("ts")), "%Y-%m-%d %H:%M")).total_seconds()
                return 0 <= gap <= WALL_RECENT_MIN * 60  # a record from a clock set ahead is not «lately» (round 3)
            except ValueError:
                return False
        recent = sum(1 for w in kind if lately(w))
        return WallCount(same, True, len(kind)) if same >= recent else WallCount(recent, False, len(kind))
    except Exception:  # noqa: BLE001 — the refusal comes first, the record is a convenience
        return none


def session_walls() -> List[dict]:
    """The session's walls as records — lines that are not a JSON object of a wall are skipped, never raised."""
    try:
        f = _walls_file()
        if f is None or not f.is_file():
            return []
        raw = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in raw.splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and isinstance(rec.get("text", ""), str) and isinstance(rec.get("argv", []), list):
            out.append(rec)
    return out


def walls_asked() -> int:
    """How many of the session's walls the end-of-session question has already named — it asks once per new wall."""
    try:
        f = _walls_file()
        a = f.with_name(f.name + ".asked") if f is not None else None
        return int(a.read_text().strip()) if a is not None and a.is_file() else 0
    except (OSError, ValueError):
        return 0


def mark_walls_asked(n: int) -> None:
    """Never backwards: two questions racing must not make an answered wall new again (Codex review, 2026-10-07)."""
    try:
        f = _walls_file()
        if f is not None and n > walls_asked():
            a = f.with_name(f.name + ".asked")
            remember(a)  # asked in the output of a command that went through — a refused one gives the question back
            a.write_text(str(n))
    except OSError:
        pass


def _verdicts_file() -> Optional[Path]:
    f = _walls_file()
    return f.with_name(f.name[:-len("-walls.jsonl")] + "-verdicts.jsonl") if f is not None else None


def _verdict_key(case: Path, ref: str, words: str) -> str:
    raw = f"{case.resolve()}\n{ref}\n{' '.join(words.split())}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def record_refused_verdict(case: Path, ref: str, words: str, claim: list) -> None:
    """A refused verdict, kept by the session like its walls, with the versions the item stood on (the polygon, 2026-11-06:
    an acceptor checked #A, the doer edited it to #B, the accept was refused; the doer recorded #B and sent the same words
    in the same second — «accepted» for bytes no acceptor saw). Only a key: the words stay with the agent. Never raises."""
    try:
        f = _verdicts_file()
        if f is None:
            return
        rec = {"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "key": _verdict_key(case, ref, words), "claim": claim}
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            _locked(fh)
            fh.write(json.dumps(rec) + "\n")
    except Exception:  # noqa: BLE001 — the refusal comes first
        pass


def refused_verdicts(case: Path, ref: str, words: str) -> List[dict]:
    """This session's refused verdicts with the same words for this item, oldest first — [] when none or no session."""
    try:
        f = _verdicts_file()
        if f is None or not f.is_file():
            return []
        key = _verdict_key(case, ref, words)
        found = []
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("key") == key:
                found.append(rec)
        return found
    except OSError:
        return []


def _calls_file() -> Optional[Path]:
    f = _walls_file()
    return f.with_name(f.name[:-len("-walls.jsonl")] + "-calls.json") if f is not None else None


def _calls_update(change) -> Optional[dict]:
    """Read, change and write the session's call state under one lock (Codex review, 2026-10-07: 144 parallel calls of one
    session stored 142 — a subagent beside its parent reads the same count). None when no session is known."""
    c = _calls_file()
    if c is None:
        return None
    c.parent.mkdir(parents=True, exist_ok=True)
    with c.open("a+", encoding="utf-8") as fh:
        _locked(fh)
        fh.seek(0)
        try:
            st = json.loads(fh.read() or "{}")
        except ValueError:
            st = {}
        if not isinstance(st, dict):
            st = {}
        change(st)
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(st))
        fh.flush()
        return st


def count_call() -> Tuple[int, int, int]:
    """Count this session's el calls, every call (the polygon, 2026-10-07: in 17 of 35 sessions an agent made ten and
    more el calls in a row without ticking anything, and 14 sessions ended without State). Returns (calls, the call of
    the last successful `done`, the call el last recited at); (0, 0, 0) when no session is known. Never raises."""
    try:
        st = _calls_update(lambda st: st.__setitem__("n", int(st.get("n", 0)) + 1))
        if st is None:
            return 0, 0, 0
        return int(st["n"]), int(st.get("last_done", 0)), int(st.get("recited", 0))
    except Exception:  # noqa: BLE001 — counting must never break a command
        return 0, 0, 0


def mark_done(n: int) -> None:
    try:
        _calls_update(lambda st: st.__setitem__("last_done", max(n, int(st.get("last_done", 0)))))
    except Exception:  # noqa: BLE001
        pass


def claim_recital(n: int, every: int) -> bool:
    """Take the recitation due at call n — once: two processes that both reach it recite once (Codex, 2026-10-07)."""
    claimed = []

    def change(st):
        if n - int(st.get("recited", 0)) >= every:
            st["recited"] = n
            claimed.append(True)
    try:
        _calls_update(change)
    except Exception:  # noqa: BLE001
        return False
    return bool(claimed)


def sign(model: str, who: str = "") -> None:
    """This session says what it is (L8, the owner's word 2026-10-05: «provider, model and number»): the model always — no
    harness names it — and «Provider Tool» only where the harness is one el does not know. Kept by the session id."""
    f = _sign_file()
    if f is None:
        raise StoreError("el keeps a signature per session and sees no session here — name it once in the terminal you keep: "
                         "export EL_SESSION=<8 letters or digits> && el sign \"…\" (Claude Code and Codex give theirs on their own)", 4)
    make_dirs(f.parent)
    remember(f)  # the command's own write: a refused `el sign` (a fill denied on the way) keeps the old one (round 11)
    f.write_text(clean_part(model) + "\n" + clean_part(who) + "\n", encoding="utf-8")


def signature() -> Tuple[str, str, str]:
    """(«Provider Tool», model, session) of the hand writing now: the harness's words, the model as the agent said it
    (`el sign`, or EL_MODEL), the session from the harness — each "" when nothing says. Provenance, not proof."""
    model, who = clean_part(os.environ.get("EL_MODEL", "")), ""
    f = _sign_file()
    if f is not None and f.is_file():
        try:
            lines = f.read_text(encoding="utf-8").split("\n")
        except OSError:
            lines = []
        model = model or (clean_part(lines[0]) if lines else "")
        who = clean_part(lines[1]) if len(lines) > 1 else ""
    return (who or harness()), model, session_id()


def take_ask(case: Path, sign: Tuple[str, str, str], limit: int) -> int:
    """One ask of a hand el does not fully know: counted per case and exact signature (provider tool · model · session) in
    the hands folder, beside the session's other memory — never in the case's files (Codex, 2026-10-20: counting the
    record's own lines never stopped on a renewed line, restarted when a phase closed, never started on a range, and let
    session `abc` spend the asks of `abcdefgh`). Returns the number of this ask, 1…limit, or 0 once the limit is spent;
    a folder el cannot write asks once more rather than never."""
    try:
        base = _hands_base()
        if base is None:
            return 1
        key = hashlib.sha256(json.dumps([str(case.resolve()), *sign]).encode("utf-8")).hexdigest()[:24]
        f = base / f"{key}-asks"
        n = int(f.read_text(encoding="utf-8") or 0) if f.is_file() else 0
        if n >= limit:
            return 0
        make_dirs(f.parent)
        remember(f)  # an ask shown only by a command that went through: a refused one gives it back (round 13)
        f.write_text(str(n + 1), encoding="utf-8")
        return n + 1
    except (OSError, ValueError):
        return 1


def _session_key() -> str:
    """The exact session, as the harness names it — the key a session's own files are kept under (the 8 chars of
    `session_id` are for reading: `shared01-A` and `shared01-B` are two sessions; Codex, 2026-10-05 for the signature,
    2026-10-29 for the hand: two sessions shared one hand file and a write landed in the other's case)."""
    return next((f"{k}={os.environ[k]}" for k in SESSION_ENVS if re.sub(r"[^A-Za-z0-9]", "", os.environ.get(k) or "")), "")


def _hand_file(root: Path, legacy: bool = False) -> Optional[Path]:
    """The session's bookmark in this space — private: it says where the session's next bare command goes, never who
    works where (the live run of 2026-10-29: a session that only listed the cases was announced to the next one as
    «another session holds it»). `legacy` — the file el kept before 1.74.0, named by the 8 chars of the session."""
    full = _session_key()
    if not full:
        return None
    base = _hands_base()
    if base is None:
        return None
    key = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    if legacy:
        return Path(base) / f"{session_id()}-{key}"
    return Path(base) / f"{hashlib.sha256(full.encode('utf-8')).hexdigest()[:24]}-{key}"


def hold(root: Path, case: Path) -> Optional[OSError]:
    """This session takes `case` in hand: its next bare command acts on it, whatever another session writes. Returns the
    error of a hand the system would not let el keep — a command that announces the hand says so (case use refuses; spawn
    and case new name the old hand; the second hand, round 16: `case use beta` said beta, the next `log` wrote to alpha)."""
    f = _hand_file(root)
    if f is None:
        return None
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        remember(f)  # a command refused after it — a spawn whose child was put back — gives the old hand back (round 22)
        f.write_text(os.path.relpath(case.resolve(), root.resolve().parent), encoding="utf-8")
    except (OSError, ValueError) as e:
        return e if isinstance(e, OSError) else None  # unkept: the hand falls back to where a write was last aimed
    return None


def bare_reaches(root: Path, case: Path) -> bool:
    """Does this session's next bare command act on `case`? Read without moving anything: EL_CASE, else the hand it holds,
    else where a write was last aimed (after a create, the case just made). An EL_CASE that no longer picks one case is
    not «here» (the second hand, round 20: a new case made the name ambiguous, and the printed door failed exit 2)."""
    name = os.environ.get("EL_CASE")
    if name:
        try:
            return resolve_case(root, name).resolve() == case.resolve()
        except StoreError:
            return False
    was = held(root) or last_aimed(root)  # the same pick as `hand` — never an assumption (round 25: a journal with a
    return was is not None and was.resolve() == case.resolve()  # clock ahead was «last aimed», not the new case)


def last_aimed(root: Path) -> Optional[Path]:
    """The open case a write was last aimed at — its JOURNAL.md mtime, as `hand` picks it for a session with no hand."""
    def freshness(c: Path):
        j = file_path(c, "JOURNAL.md")
        return j.stat().st_mtime if j.exists() else 0
    try:
        open_cases = [c for c in all_cases(root) if is_open(c)]
    except (StoreError, OSError):
        return None
    return max(open_cases, key=freshness) if open_cases else None


def env_case_said(case: Path) -> List[str]:
    """EL_CASE holds this shell's bare commands elsewhere: said where a new case is made, with the doors that reach it."""
    name = os.environ.get("EL_CASE")
    if not name:
        return []
    return [f"EL_CASE={name} is set in this shell: bare commands go to {name}, not {case.name} — the doors here name it"]


def hold_said(root: Path, case: Path) -> List[str]:
    """`hold` for a command that creates work and moves the hand with it: the work stands, an unkept hand is said."""
    e = hold(root, case)
    if e is None:
        return []
    was = held(root)
    if was is None or was.resolve() == case.resolve():  # no hand of its own: bare commands go where a write was last aimed
        return []                                         # — this very case (the second hand, round 17)
    return [f"hand not kept ({e.strerror or e}) — this session's bare commands still go to {was.name}, not {case.name}; "
            f"name it on each call: el --case {case_arg(case, root)} …"]


def mark_aimed(case: Path):
    """The case a write command was aimed at bumps its JOURNAL.md mtime, no content change — what `case use` does (the
    live migration of 2026-10-07: the last agent's last write was `readme touch` on a map — no journal line — and the
    next session, following the freshest journal, landed in a finished child while three items of the map waited for
    its hand; by README mtime instead, a child's write that redraws its parent's README would move the hand up)."""
    try:
        j = file_path(case, "JOURNAL.md")
        if j.exists():
            os.utime(j)
    except OSError:
        pass


def held(root: Path, closed_too: bool = False) -> Optional[Path]:
    """The case this session holds, while it is still an open case here — or, `closed_too`, the one it held last, closed.
    A session that took its hand under el before 1.74.0 keeps it: its old file is read until the next hold writes the new."""
    f = _hand_file(root)
    legacy = f is not None and not f.is_file()
    if legacy:
        f = _hand_file(root, legacy=True)
    if f is None or not f.is_file():
        return None
    try:
        target = (root.resolve().parent / f.read_text(encoding="utf-8").strip()).resolve()
    except OSError:
        return None
    found = next((c for c in all_cases(root) if c.resolve() == target and (closed_too or is_open(c))), None)
    if legacy and found is not None:  # the old file is shared by every session with the same 8 chars, and an older el may
        hold(root, found)  # move it: what this session read becomes its own at once (Codex, 2026-10-30)
    return found


def hand(root: Path, explicit: Optional[str] = None, look: bool = False) -> Path:
    """The case in hand: flag > EL_CASE > the case this session holds > the open case a write was last aimed at (its
    JOURNAL.md mtime, `mark_aimed`), which the session then holds (P2, C9; feedback 2026-09-27). `look` — the entry, a
    read: when every case is closed, the one this session held last is shown closed, not refused (feedback 2026-10-15:
    «Конец — снова el» after `el done --by owner` met ERROR exit 4 — the session had done everything right)."""
    name = explicit or os.environ.get("EL_CASE")
    if name:
        return resolve_case(root, name)
    cases = all_cases(root)
    if not cases:  # zero cases is not "all of them are closed": an empty space must say so (2026-09-14)
        raise StoreError("no case here yet — nothing to pick up", 4,
                         recovery="el case new \"name\" --goal \"what done looks like, in the owner's words\"")
    open_cases = [c for c in cases if is_open(c)]
    last = held(root, closed_too=True) if look and not open_cases else None
    if last is not None:
        return last  # read only: no write reaches a closed case through the hand
    if not open_cases:  # a closed case takes new work once opened again (the polygon, 2026-10-10: eight calls to find the door;
        # the owner's word, 2026-10-14: a new phase in a closed case is refused until the case is opened)
        tops = [c for c in cases if not any(c != o and o in c.parents for o in cases)]
        top = case_arg(tops[0], root) if len(tops) == 1 else "<name>"
        raise StoreError(f"every case here is closed ({len(cases)}) — nothing to pick up on its own; new work goes into a case "
                         f"opened again, as a new phase", 4,
                         recovery=f"continue one: el --case {top} case reopen \"why it goes on\", then el --case {top} phase plan N "
                                  f"\"Name\" --goal \"…\" · the cases: el case list · a new one: el case new \"name\" --goal \"…\"")
    mine = held(root)
    if mine is not None:
        return mine
    picked = last_aimed(root) or open_cases[0]  # the journal's mtime marks the case a command was last aimed at (`mark_aimed`)
    global HAND_NOTE
    # a harness with no session id cannot tell this session from another: every writer looks «other», and the door the
    # note gives (`el case use`) cannot hold here (a report, 2026-11-05: six writes in one VS Code Copilot terminal, the
    # same note after `case use` each time) — the case a write was last aimed at is the hand, and el says no more
    other = _other_writer(root, picked) if session_id() else None
    if other:  # a fresh session lands where another session wrote lately — said, not silent (feedback 2026-10-10), in what
        sid, when = other  # el knows: that session wrote here then. A bookmark is not work — a session that only listed the
        # cases was announced as «another session holds it» (the live run of 2026-10-29), so a look leaves no mark
        HAND_NOTE = (f"this session had no case in hand and took {picked.name}, where the last write went — session {sid} "
                     f"wrote here at {when}; if it works here now, take your own: el case use <name> · cases: el case list")
    hold(root, picked)  # picked up once: another session's write no longer moves it
    return picked


HAND_NOTE = ""  # said once by main when a fresh session took a case another session wrote to lately
HAND_FRESH = 12 * 3600  # seconds: a write older than this is a session that has ended — a first guess, kept from 1.59.0


def _wrote_file(root: Path) -> Optional[Path]:
    hand = _hand_file(root)
    return hand.with_name(hand.name + ".wrote") if hand is not None else None


def mark_wrote(root: Path, case: Path):
    """This session wrote to `case` — the only fact the note to another session stands on (a look writes no mark)."""
    f = _wrote_file(root)
    if f is None:
        return
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        remember(f)  # a mark of a write: a command refused after it gives the old mark back (the second hand, round 22)
        shown = re.sub(r"[^A-Za-z0-9-]", "", _session_key().partition("=")[2])[:16]  # 8 chars read as one session for two
        f.write_text(f"{os.path.relpath(case.resolve(), root.resolve().parent)}\n{shown}", encoding="utf-8")
    except (OSError, ValueError):
        pass


def _other_writer(root: Path, case: Path) -> Optional[Tuple[str, str]]:
    """Another session that wrote to `case` in this space lately: (its id, «HH:MM» of its last write) — the newest one."""
    mine = _wrote_file(root)
    base = _hands_base()
    if base is None:
        return None
    key = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    best = None
    try:
        files = list(base.glob(f"*-{key}.wrote"))
    except OSError:
        return None
    for f in files:
        if mine is not None and f == mine:
            continue
        try:
            st = f.stat()
            if datetime.datetime.now().timestamp() - st.st_mtime > HAND_FRESH:
                continue
            rel, _, sid = f.read_text(encoding="utf-8").partition("\n")
            target = (root.resolve().parent / rel.strip()).resolve()
        except (OSError, ValueError):
            continue
        if target == case.resolve() and (best is None or st.st_mtime > best[2]):
            best = (sid.strip() or "?", datetime.datetime.fromtimestamp(st.st_mtime).strftime("%H:%M"), st.st_mtime)
    return (best[0], best[1]) if best else None


def stray_files(case: Path) -> List[Path]:
    """Files in the case root that are not the three case files (any spelling) or *.recover.md (L3/L4)."""
    allowed = {n.lower() for n in FILES}
    stray = []
    for child in sorted(case.iterdir()):
        if not child.is_file() or child.name.startswith("."):
            continue
        if child.name.lower() in allowed or child.name.endswith(".recover.md"):
            continue
        stray.append(child)
    return stray


def chain(case: Path, root: Path) -> List[str]:
    """Names from the top down to `case`; in root mode the project name comes first."""
    project = project_case(root)
    if project is not None and case == project:
        return [project.name]
    names = []
    p = case
    while p != root and is_case_dir(p):
        names.append(p.name)
        p = p.parent
    if project is not None:
        names.append(project.name)
    return list(reversed(names))


def parent_case(case: Path, root: Path):
    """The case a nested case reports back to: its folder parent, or the project case for
    top-level cases in root mode, or None."""
    if is_case_dir(case.parent):
        return case.parent
    if case.parent == root:
        return project_case(root)
    return None


# ---- one writer in the space at a time -----------------------------------------------------------------
# A command reads a case file, changes it, writes it back whole. Two el processes in one space both read the old TODO,
# and the later write drops the earlier one's change while each says «done» (L7, 2026-10-10: two concurrent `todo add`
# lost an item 6 times in 30 — the memory many agents share lied without a word). A command holds the space's lock from
# its first read to its last write. One lock for the space, not one per case: a command may write a child and its
# parent, and two locks taken in two orders would wait on each other. The lock file lives outside the project — nothing
# for git or the case map to see — and the lock goes with the process: a killed command leaves none behind.
LOCK_WAIT = 30.0  # seconds; a command takes milliseconds — this long a wait means something holds it, and it is said
_SPACE_LOCK = None


def space_lock_path(root: Path) -> Path:
    """Where the lock of the space at `root` (the `.cases/` folder) lives: the temp folder, keyed by the real path."""
    key = hashlib.sha1(str(Path(root).resolve()).encode("utf-8")).hexdigest()[:16]
    base = os.environ.get("EL_LOCK_DIR") or os.path.join(tempfile.gettempdir(), "elephant-locks")
    return Path(base) / f"{key}.lock"


def lock_space() -> None:
    """Take the space's lock for this command — waiting while another el command holds it, up to EL_LOCK_WAIT seconds,
    then a refusal that wrote nothing. No space yet (`case new` in a new project), no POSIX locks, or a lock file el
    cannot make: the command runs as before — a lock is a guard, never a reason to refuse the work."""
    global _SPACE_LOCK
    if _SPACE_LOCK is not None:
        return
    try:
        import fcntl
        root = find_root()
        path = space_lock_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, "a+")
    except (ImportError, StoreError, OSError):
        return
    try:
        wait = float(os.environ.get("EL_LOCK_WAIT", LOCK_WAIT))
    except ValueError:
        wait = LOCK_WAIT
    wait = max(0.0, wait) if math.isfinite(wait) else LOCK_WAIT  # `inf` or `nan` would wait forever or not at all (Codex)
    deadline = time.monotonic() + wait
    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _SPACE_LOCK = fh
            _say_holder(fh)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                holder = _read_holder(path)
                fh.close()
                raise StoreError(f"another el command has been writing in this case space for {wait:g} s (another session, a "
                                 f"subagent, a script) — nothing was written: run the same command again; a lock no live "
                                 f"process holds is gone by itself (to wait longer: EL_LOCK_WAIT=<seconds>)\n"
                                 f"  held by: {holder or 'not said (an el older than 1.75.0)'} · lock: {path}"
                                 + (f" · still running? ps -p {holder.split()[1]}" if holder.startswith("pid ") else "")
                                 + "\n  a file el writes may already show the change while the writer still redraws the rest: "
                                 "wait for its command to end, then run yours", 4)
            time.sleep(0.05)
        except OSError:  # a file system without locks: run as before
            fh.close()
            return


def _say_holder(fh) -> None:
    """The holder writes who it is into the lock file — read only by a command that waits, so a refusal names it (a report,
    2026-11-02: three overlapping commands refused with no lock path and no holder). Best effort: the lock stands without it."""
    try:
        argv = " ".join(sys.argv[1:])[:120]
        fh.seek(0)
        fh.truncate()
        fh.write(f"pid {os.getpid()} · el {argv} · since {datetime.datetime.now().strftime('%H:%M:%S')}\n")
        fh.flush()
    except OSError:
        pass


def _read_holder(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip().split("\n")[0][:200]
    except OSError:
        return ""


def unlock_space() -> None:
    global _SPACE_LOCK
    fh, _SPACE_LOCK = _SPACE_LOCK, None
    if fh is not None:
        try:
            fh.close()  # closing the file lets the lock go
        except OSError:
            pass


# ---- one command, one change: all or nothing --------------------------------------------------------
# A refusal says «nothing was written», so nothing may stay written (feedback 2026-09-27: `todo reopen` with a reason
# too long for the journal answered exit 3 «nothing was written» after TODO had already lost the item's result and
# proofs — twelve commands wrote a file before they logged). Every file a command touches is remembered as it was
# before the first touch; a refusal or a crash puts each one back, so a write through two files — or two cases —
# lands whole or not at all.
_UNDO: Optional[dict] = None


class _Link(NamedTuple):
    target: str  # what a link pointed at before the command: a refusal makes it that link again


_TIMES: dict = {}  # the (atime, mtime) of each remembered file, put back with its bytes
_MODES: dict = {}  # its permission bits, put back with them
_MADE: List[Path] = []  # folders this command created — a refusal takes them away again, deepest first
STUCK: List[Path] = []  # files a rollback could not put back — the refusal names them instead of «nothing was written»


def begin():
    global _UNDO, READ_ONLY
    _UNDO = {}
    _TIMES.clear()
    _MODES.clear()
    _MADE.clear()
    STUCK.clear()
    READ_ONLY = ""  # a denied write is said by the command that met it
    READ_ONLY_FILES.clear()
    global LAST_DENIED
    LAST_DENIED = None


def commit():
    global _UNDO
    _UNDO = None
    _TIMES.clear()
    _MODES.clear()
    _MADE.clear()


def make_dirs(path: Path):
    """`mkdir -p` that a refusal undoes: every folder created here is taken away again if the command is refused (the
    second hand, 2026-11-08: a refused `mv` left `target/new/deep/` behind under «nothing was written»)."""
    missing, p = [], Path(path)
    while not p.exists():
        missing.append(p)
        p = p.parent
    for d in reversed(missing):
        d.mkdir()
        if _UNDO is not None:
            _MADE.append(d)


def touched() -> bool:
    """This command has written something so far."""
    return bool(_UNDO)


def remember_created(path: Path):
    """A file this command has just created itself (an exclusive open): a refusal takes it away. Said after the creation,
    never before — a name taken by someone else is not this command's to remove (the second hand, round 15: a refused
    `el feedback` left its empty report behind)."""
    if _UNDO is not None and Path(path) not in _UNDO:
        _UNDO[Path(path)] = None


def remember(path: Path):
    """Keep the bytes `path` had before this command first touched it (None — it did not exist). A link is remembered
    as the file it points at — what a write through it changes, and what a refusal puts back (the second hand,
    2026-11-08: a phase file that was a link was «put back» as a plain file, its target left changed)."""
    if _UNDO is None:
        return
    path = Path(path)
    if path.is_symlink():  # the link itself — a move takes the link, not its target — and then the file it points at
        if path not in _UNDO:
            _UNDO[path] = _Link(os.readlink(path))
        path = path.resolve()
    if path not in _UNDO:
        _UNDO[path] = path.read_bytes() if path.exists() else None
        if path.exists():  # the time too: a journal's mtime says where a write was last aimed (the second hand, round 23)
            st = path.stat()
            _TIMES[path] = (st.st_atime_ns, st.st_mtime_ns)
            _MODES[path] = st.st_mode & 0o7777  # and the mode: a script put back must still run (round 24)


def rollback() -> List[Path]:
    """Put every file this command touched back as it was; returns the files that changed back. A file el could rewrite
    in place in a folder it may not write (the second hand, 2026-11-08: a phase file rewritten, then TODO denied) is
    put back in place the same way; one that cannot be put back at all is kept in STUCK for the refusal to name."""
    global _UNDO
    saved, _UNDO = _UNDO or {}, None
    made = list(_MADE)
    _MADE.clear()
    times_kept, modes_kept = dict(_TIMES), dict(_MODES)
    _TIMES.clear()
    _MODES.clear()
    restored = []
    for path, data in saved.items():
        try:
            if isinstance(data, _Link):
                if not (path.is_symlink() and os.readlink(path) == data.target):
                    if path.is_symlink() or path.exists():
                        path.unlink()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(data.target, path)
                    restored.append(path)
            elif data is None:
                if path.is_symlink() or path.exists():
                    path.unlink()
                    restored.append(path)
            else:
                if not path.exists() or path.read_bytes() != data:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    _put_back(path, data)
                    restored.append(path)
                mode = modes_kept.get(path)
                if mode is not None and (path.stat().st_mode & 0o7777) != mode:
                    try:
                        os.chmod(path, mode)
                    except OSError:
                        pass
                times = times_kept.get(path)
                if times is not None and path.stat().st_mtime_ns != times[1]:
                    try:
                        os.utime(path, ns=times)  # as it was: «nothing was written» holds for the clock el reads too
                    except OSError:
                        pass  # the bytes are back; a clock el may not set is not a write left behind
        except OSError:
            STUCK.append(path)
    for d in reversed(made):  # the folders this command created, deepest first — only if nothing else lives there now
        try:
            d.rmdir()
        except OSError:
            pass
    return restored


def _keep_mode(real: Path, tmp: str):
    """A file el rewrites through a temp file keeps its permission bits — a temp file is born 0600 (round 24: an
    executable put back by a rollback no longer ran; every README el wrote turned 0600)."""
    try:
        os.chmod(tmp, real.stat().st_mode & 0o7777)
    except OSError:
        pass


def _put_back(path: Path, data: bytes):
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        _keep_mode(path, tmp)
        os.replace(tmp, path)
    except OSError:
        if tmp is not None and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        with open(path, "wb") as fh:  # a folder el may not write, a file it may: in place, as it was written
            fh.write(data)


# A write the system does not allow — a read-only sandbox, a folder without write access (Codex, 2026-11-08: the entry, a
# look, died in a Python traceback when it went to redraw README). Said as el's own refusal at the door every write
# passes; the entry, a read, shows the case anyway and says once what it could not refresh.
DENIED = (errno.EPERM, errno.EACCES, errno.EROFS)
READ_ONLY = ""  # what the system said, once a write of this process was denied — the entry names it in one line
READ_ONLY_FILES: List[str] = []  # the files it was denied for, by name
LAST_DENIED: Optional["StoreError"] = None  # the refusal of the last denied write — a write command that went on past it
                                             # (a handler on the way swallowed it) is refused with it at its end


def denied(path: Optional[Path], e: OSError, to: Optional[Path] = None) -> StoreError:
    """The refusal of a write the system did not allow: what, why, and the doors that need no write. `to` — a move:
    which side the system refused is not said by a rename, so both are named (the second hand, 2026-11-08: a binary
    `mv` into a protected folder was refused naming only the source)."""
    global READ_ONLY
    READ_ONLY = e.strerror or "write not permitted"
    if path is not None and Path(path).name not in READ_ONLY_FILES:
        READ_ONLY_FILES.append(Path(path).name)
    what = (f"move {_shown_from_cwd(Path(path))} → {_shown_from_cwd(Path(to))}" if path and to
            else f"write {_shown_from_cwd(Path(path))}" if path else "write a file")
    look = ("a look needs no write: el status · el todo · el order — each shows the case without refreshing its files; "
            if _a_case_to_look_at() else "")  # no case yet: those doors would refuse (the second hand, 2026-11-08)
    err = StoreError(f"cannot {what}: {READ_ONLY} — this session may not write here (a read-only sandbox, or a "
                     f"folder without write access); nothing was written\n"
                     f"  {look}the write itself: the same command where this session may write", 4)
    err.denied = True  # a look shows the case anyway; a write is refused whole
    global LAST_DENIED
    LAST_DENIED = err
    return err


def _a_case_to_look_at() -> bool:
    """A case a bare look reaches — over none (a first case refused, every case closed, an EL_CASE that picks no single
    case: the second hand, round 21) the look doors refuse too, so they are not printed."""
    try:
        root = find_root()
        name = os.environ.get("EL_CASE")
        if name:
            return is_open(resolve_case(root, name))
        return any(is_open(c) for c in all_cases(root))
    except Exception:  # noqa: BLE001 — a half-made case mid-refusal: no door is promised
        return False


def _shown_from_cwd(path: Path) -> str:
    try:
        return os.path.relpath(path, Path.cwd())
    except ValueError:
        return str(path)


def write_file(path: Path, text: str):
    """A file of the case other than the three (a phase file, a recover file, a document whose links follow a move)."""
    remember(path)
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as e:
        if e.errno in DENIED:
            raise denied(path, e) from None
        raise


def _append_file(path: Path, text: str):
    """Lines added after what a file holds (a recover file: lines a rebuild moved out wait there until re-entered)."""
    remember(path)
    try:
        before = path.read_bytes() if path.exists() else b""
        with open(path, "ab") as fh:
            fh.write((b"" if not before or before.endswith(b"\n") else b"\n") + text.encode("utf-8"))
    except OSError as e:
        if e.errno in DENIED:
            raise denied(path, e) from None
        raise


# ---- writing with stamp discipline ---------------------------------------------------------------
def _real(path: Path) -> Path:
    """A link stays a link: el writes, and puts back, the file it points at."""
    return path.resolve() if path.is_symlink() else path


def _atomic_write(path: Path, text: str):
    remember(path)
    real = _real(path)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=real.parent, prefix=f".{real.name}.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        _keep_mode(real, tmp)
        os.replace(tmp, real)
    except OSError as e:
        if tmp is not None and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
        if e.errno in DENIED:
            raise denied(path, e) from None
        raise


HAND_EDITED: set = set()  # files this process found written past el (stamp mismatch) — before the rebuild renewed the stamp


def check_stamp(case: Path, name: str) -> WriteReport:
    """S3/S4: verify the stamp before writing. Mismatch → rebuild by grammar, move the rest out."""
    path = file_path(case, name)
    report = WriteReport(path)
    text = read(case, name)
    ok, state = stamp.verify(text)
    if ok or state == "missing":  # S2: no stamp yet → it will be set by this write
        return report
    report.bypassed = True
    HAND_EDITED.add(str(path.resolve()))  # a file written past el in this process: a drawn line that differs is a hand edit
    rebuilt, removed, fatal = recover.rebuild(name, text)
    if rebuilt is None:
        details = "; ".join(str(f) for f in fatal)
        raise StoreError(f"{name}: stamp {state} and the file cannot be rebuilt — {details}", 3)
    rec = case / f"{path.name}.recover.md"
    rec_before = rec.read_bytes() if rec.exists() else None
    rec_stat = rec.stat() if rec.exists() else None
    try:
        if removed:  # the lines moved out are kept first — a rebuild written before them would lose them; added after
            _append_file(rec, "\n".join(removed) + "\n")  # lines a rebuild before moved there, never over them (r10)
        _atomic_write(path, rebuilt)
    except StoreError as e:  # the system lets nothing be written here (the second hand, round 9: a hand-edited TODO
        if not getattr(e, "denied", False):  # made `todo show`, `facts` refuse) — a read takes the rebuild in memory;
            raise                            # a write meets the denial at its own write or at the end of the command
        if removed:  # the recover file as it was: a look leaves no trace (round 10: an older recover file was lost)
            try:
                if rec_before is None:
                    if rec.exists():
                        rec.unlink()
                elif rec.read_bytes() != rec_before:
                    rec.write_bytes(rec_before)
                    os.utime(rec, ns=(rec_stat.st_atime_ns, rec_stat.st_mtime_ns))  # a look leaves no trace (round 24)
            except OSError:
                STUCK.append(rec)
        report.rebuilt = rebuilt
        return report
    if removed:
        report.recovered, report.recovered_lines = rec, len(removed)
    return report


def _introduced_warnings(name: str, body: str, current_text: str, warnings):
    """Only the warnings THIS write introduces (the owner's word, 2026-09-17: 21 stderr lines about old README
    lines on every `readme touch` taught the agent to filter warnings out — 46 of 66 in `check` were history).
    A line warning stays when its line is new; a file warning (line 0, e.g. README over 8 KB) stays when the
    file did not already carry that rule's warning. History is `check`'s business, shown there once per rule."""
    if not current_text:
        return warnings
    cur_body, _ = stamp.split(current_text)
    cur = recover.PARSERS[name](cur_body)
    cur_lines = set(cur_body.split("\n"))
    cur_rules0 = {f.rule for f in cur.warnings if f.line == 0}
    new_lines = body.rstrip("\n").split("\n")
    kept = []
    for f in warnings:
        if f.line == 0:
            if f.rule not in cur_rules0:
                kept.append(f)
        elif f.line > len(new_lines) or new_lines[f.line - 1] not in cur_lines:
            kept.append(f)
    return kept


def write(case: Path, name: str, body: str) -> WriteReport:
    """Validate `body` by its grammar, then write it with a fresh stamp (C8: nothing is touched on refusal).

    A violation the command did NOT introduce (the broken line already sits in the current file —
    e.g. left by an older el version) must not deadlock every future write: the file is rebuilt,
    the broken lines go to `<FILE>.recover.md`, the write proceeds with a warning (S4 semantics).
    """
    current_text = read(case, name) if file_path(case, name).exists() else ""
    _, current_state = stamp.verify(current_text) if current_text else (False, "missing")
    if current_text and current_state == "missing" and recover.PARSERS[name](current_text).errors:
        # A legacy file: never stamped by Elephant and outside the grammar. Rebuilding it (S4) would
        # move most of it into .recover.md — that is not migration (feedback 2026-09-02).
        raise StoreError(f"{name} is outside Elephant's grammar and was never stamped by Elephant — a legacy file; "
                         f"nothing is written into it until the case is migrated", 3, recovery=MIGRATE_HINT)
    report = check_stamp(case, name)
    result = recover.PARSERS[name](body)
    result.warnings = _introduced_warnings(name, body, current_text, result.warnings)
    if result.errors:
        current, _ = stamp.split(read(case, name)) if file_path(case, name).exists() else ("", None)
        current_lines = set(current.split("\n"))
        new_lines = body.rstrip("\n").split("\n")
        introduced = [f for f in result.errors
                      if f.line == 0 or f.line > len(new_lines) or new_lines[f.line - 1] not in current_lines]
        if introduced:
            details = "\n".join(f"  {f}" for f in introduced)
            raise StoreError(f"{name}: refused, {len(introduced)} rule violation(s):\n{details}", 3)
        rebuilt, removed, fatal = recover.rebuild(name, body)
        if rebuilt is None:
            details = "; ".join(str(f) for f in fatal)
            raise StoreError(f"{name}: pre-existing violations and the file cannot be rebuilt — {details}", 3)
        _atomic_write(file_path(case, name), rebuilt)
        if removed:
            rec = case / f"{file_path(case, name).name}.recover.md"
            write_file(rec, "\n".join(removed) + "\n")
            report.recovered, report.recovered_lines = rec, len(removed)
        report.warnings = result.warnings
        return report
    report.warnings = result.warnings
    _atomic_write(file_path(case, name), stamp.apply(body))
    return report


def recover_files(case: Path) -> List[Path]:
    return sorted(case.glob("*.recover.md"))


def legacy_files(case: Path) -> List[tuple]:
    """Files among the three that the grammar rejects AND that carry no valid el stamp — a case
    written before el or by hand since. Nothing is written into them: `el migrate` first."""
    from . import migrate  # local import: migrate imports store
    out = []
    for name in FILES:
        why = migrate.legacy_reason(case, name)
        if why:
            out.append((name, why))
    return out


MIGRATE_HINT = "el migrate   (dry run, changes nothing) · then: el migrate --apply"
