"""Storage layer: find `.cases/`, pick the case in hand, read and write the three files safely.

Rules touched: L1–L3 (layout), S1–S4 (stamp on every write, rebuild on mismatch), C7–C9.
The case "in hand": `--case` flag > EL_CASE env > the case this session holds > the open case whose JOURNAL.md changed
most recently (and the session holds it from then on). The one thing kept between commands is which case a session
holds — outside the project, keyed by the session id the harness gives (see `hold`).
"""
import datetime
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

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

    def __init__(self, message: str, code: int = 1, recovery: str = ""):
        super().__init__(message)
        self.code = code
        self.recovery = recovery


@dataclass
class WriteReport:
    path: Path
    warnings: List[grammar.Finding] = field(default_factory=list)
    recovered: Optional[Path] = None  # set when a mismatched file was rebuilt (S4)
    recovered_lines: int = 0
    bypassed: bool = False  # the file had been written bypassing `el` (stamp mismatch)


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
    return p.is_dir() and CASE_NAME_RE.match(p.name) is not None


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
            if not child.is_dir() or child.name.startswith(".") or child.name in ("node_modules", "phases"):
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
    return p.read_text(encoding="utf-8")


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
    body, _ = stamp.split(read(case, name))
    return body, report


def _rel(case: Path, root: Path) -> str:
    return case.relative_to(root).as_posix() if case.is_relative_to(root) else case.name  # the project case sits above .cases/


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
    raise StoreError(f"no case named `{name}` under {root}", 4, recovery="el case list")


# ---- the hand of a session --------------------------------------------------------------------------
# Feedback 2026-09-27: two sessions in one working tree, each with its own case — session B wrote case b, session A then
# opened case a, and B's bare `todo done` landed in a: the hand followed the freshest journal, which in a shared tree is
# another agent's. Many agents on one tree is the model (each writes its own leaf), so the hand belongs to the session:
# the case it last wrote to, or took (`case new` · `spawn` · `case use`), or first picked up. Kept outside the project,
# in a temp folder, one line per session and project — not a config, nothing in git, gone with the machine's temp.
# A harness that gives no session id (EL_SESSION sets one by hand) keeps the old rule: the freshest journal.
SESSION_ENVS = ("EL_SESSION", "CODEX_SESSION_ID", "CLAUDE_CODE_SESSION_ID")  # the innermost harness first: Codex run from Claude Code
# who is writing, as the harness says it (measured 2026-10-05: Claude Code sets CLAUDECODE and CLAUDE_CODE_SESSION_ID,
# Codex sets CODEX_VERSION and CODEX_SESSION_ID; neither names the model — the agent says it once: `el sign "<model>"`)
# VS Code sets COPILOT_AGENT=1 in the terminals its Copilot agent runs commands in (microsoft/vscode PR #316267, VS Code
# 1.121, 2026-05-13) and gives no session id (the owner's word 2026-10-06: an item done in Copilot was signed
# `harness ? · model ? · session ?`); last in the list — the outer harness, should a Claude Code or Codex run inside it
HARNESSES = (("CODEX_SESSION_ID", "OpenAI Codex"), ("CODEX_VERSION", "OpenAI Codex"),
             ("CLAUDE_CODE_SESSION_ID", "Anthropic Claude Code"), ("CLAUDECODE", "Anthropic Claude Code"),
             ("COPILOT_AGENT", "GitHub Copilot"))


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
    """The session this command runs in, as the agent's harness says it (EL_SESSION first; Claude Code sets
    CLAUDE_CODE_SESSION_ID) — 8 chars, or "" when nothing says. Provenance, not proof: a subagent shares its
    parent's session, and a variable can be set by hand — so the record says what el saw, never more."""
    for key in SESSION_ENVS:
        val = re.sub(r"[^A-Za-z0-9]", "", os.environ.get(key) or "")
        if val:
            return val[:8]
    return ""


def harness() -> str:
    """«Provider Tool» of the agent running this command, from the harness's own variables; "" when nothing says."""
    return next((name for key, name in HARNESSES if os.environ.get(key)), "")


def _sign_file() -> Optional[Path]:
    """The session's signature lives by the session, not by the project: one session is one model wherever it works."""
    key = next((f"{k}={os.environ[k]}" for k in SESSION_ENVS if re.sub(r"[^A-Za-z0-9]", "", os.environ.get(k) or "")), "")
    if not key:  # the exact id, hashed: `shared01-A` and `shared01-B`, `abc-def01` and `abcdef01` are two sessions (Codex, 2026-10-05)
        return None
    base = os.environ.get("EL_HANDS_DIR") or os.path.join(tempfile.gettempdir(), "elephant-hands")
    return Path(base) / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}-sign"


def _walls_file() -> Optional[Path]:
    """The session's refusals, kept by the session like its signature: el sees its own walls only here."""
    f = _sign_file()
    return f.with_name(f.name[:-len("-sign")] + "-walls.jsonl") if f is not None else None


WALL_TEXT_LINES = 200  # a refusal is kept whole for the report; a bound only against a runaway output


def wall_key(text: str) -> str:
    """One wall, whatever its numbers, quoted words and paths: `phase 2 is missing` and `phase 5 is missing` are the same
    wall, so are two missing files; a refusal whose first line only announces a list (`cannot close phase N:`) is keyed
    by the list's first line too, so two different blockers are two walls (Codex review, 2026-10-07)."""
    lines = [ln for ln in (text or "").split("\n") if ln.strip()]
    first = lines[0] if lines else ""
    if first.rstrip().endswith(":") and len(lines) > 1:
        first = first + " " + lines[1].strip()
    line = re.sub(r"`[^`]*`|«[^»]*»|\"[^\"]*\"|'[^']*'", "…", first)
    line = re.sub(r"[\w.-]*/[\w./-]*|\b[\w-]+\.(?:md|pdf|png|jpe?g|txt|json|csv|py|sh)\b", "PATH", line)
    return re.sub(r"\d+", "N", line)[:160]


def _locked(fh) -> None:
    """An exclusive lock on the walls file while a record is appended and counted: two el processes of one session (a
    subagent beside its parent) would otherwise interleave or both count twice. POSIX only; elsewhere unlocked."""
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
    except (ImportError, OSError):
        pass


def record_wall(argv: List[str], code: int, text: str) -> int:
    """Keep one refusal of this session (the polygon, 2026-10-07: thirty-odd walls in nineteen sessions, not one
    `el feedback` — the agents told the owner instead, and el, which printed every refusal, kept none of them).
    Returns how many times this session has met the same wall, this one included; 0 when no session is known.
    Never raises: a damaged walls file must not mask the refusal it was meant to keep."""
    try:
        f = _walls_file()
        if f is None:
            return 0
        lines = (text or "").split("\n")
        rec = {"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "argv": [str(a) for a in argv], "code": code,
               "text": "\n".join(lines[:WALL_TEXT_LINES]), "key": wall_key(text)}
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
            return sum(1 for w in session_walls() if w.get("key") == rec["key"])
    except Exception:  # noqa: BLE001 — the refusal comes first, the record is a convenience
        return 0


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
            f.with_name(f.name + ".asked").write_text(str(n))
    except OSError:
        pass


def sign(model: str, who: str = "") -> None:
    """This session says what it is (L8, the owner's word 2026-10-05: «provider, model and number»): the model always — no
    harness names it — and «Provider Tool» only where the harness is one el does not know. Kept by the session id."""
    f = _sign_file()
    if f is None:
        raise StoreError("el keeps a signature per session and sees no session here — name it once in the terminal you keep: "
                         "export EL_SESSION=<8 letters or digits> && el sign \"…\" (Claude Code and Codex give theirs on their own)", 4)
    f.parent.mkdir(parents=True, exist_ok=True)
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


def _hand_file(root: Path) -> Optional[Path]:
    sid = session_id()
    if not sid:
        return None
    base = os.environ.get("EL_HANDS_DIR") or os.path.join(tempfile.gettempdir(), "elephant-hands")
    key = hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:12]
    return Path(base) / f"{sid}-{key}"


def hold(root: Path, case: Path):
    """This session takes `case` in hand: its next bare command acts on it, whatever another session writes."""
    f = _hand_file(root)
    if f is None:
        return
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(os.path.relpath(case.resolve(), root.resolve().parent), encoding="utf-8")
    except (OSError, ValueError):
        pass  # a hand that cannot be kept falls back to the freshest journal, as before


def held(root: Path) -> Optional[Path]:
    """The case this session holds, while it is still an open case here."""
    f = _hand_file(root)
    if f is None or not f.is_file():
        return None
    try:
        target = (root.resolve().parent / f.read_text(encoding="utf-8").strip()).resolve()
    except OSError:
        return None
    return next((c for c in all_cases(root) if c.resolve() == target and is_open(c)), None)


def hand(root: Path, explicit: Optional[str] = None) -> Path:
    """The case in hand: flag > EL_CASE > the case this session holds > open case with the freshest JOURNAL.md,
    which the session then holds (P2, C9; feedback 2026-09-27)."""
    name = explicit or os.environ.get("EL_CASE")
    if name:
        return resolve_case(root, name)
    cases = all_cases(root)
    if not cases:  # zero cases is not "all of them are closed": an empty space must say so (2026-09-14)
        raise StoreError("no case here yet — nothing to pick up", 4,
                         recovery="el case new \"name\" --goal \"what done looks like, in the owner's words\"")
    open_cases = [c for c in cases if is_open(c)]
    if not open_cases:
        raise StoreError(f"every case here is closed ({len(cases)}) — nothing to pick up", 4,
                         recovery="el case list · el case new \"name\" --goal \"…\"")
    def freshness(c: Path):
        j = file_path(c, "JOURNAL.md")
        return j.stat().st_mtime if j.exists() else 0

    mine = held(root)
    if mine is not None:
        return mine
    picked = max(open_cases, key=freshness)
    hold(root, picked)  # picked up once: another session's write no longer moves it
    return picked


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


# ---- one command, one change: all or nothing --------------------------------------------------------
# A refusal says «nothing was written», so nothing may stay written (feedback 2026-09-27: `todo reopen` with a reason
# too long for the journal answered exit 3 «nothing was written» after TODO had already lost the item's result and
# proofs — twelve commands wrote a file before they logged). Every file a command touches is remembered as it was
# before the first touch; a refusal or a crash puts each one back, so a write through two files — or two cases —
# lands whole or not at all.
_UNDO: Optional[dict] = None


def begin():
    global _UNDO
    _UNDO = {}


def commit():
    global _UNDO
    _UNDO = None


def touched() -> bool:
    """This command has written something so far."""
    return bool(_UNDO)


def remember(path: Path):
    """Keep the bytes `path` had before this command first touched it (None — it did not exist)."""
    if _UNDO is None:
        return
    path = Path(path)
    if path not in _UNDO:
        _UNDO[path] = path.read_bytes() if path.exists() else None


def rollback() -> List[Path]:
    """Put every file this command touched back as it was; returns the files that changed back."""
    global _UNDO
    saved, _UNDO = _UNDO or {}, None
    restored = []
    for path, data in saved.items():
        try:
            if data is None:
                if path.exists():
                    path.unlink()
                    restored.append(path)
            elif not path.exists() or path.read_bytes() != data:
                path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, path)
                restored.append(path)
        except OSError:
            pass
    return restored


def write_file(path: Path, text: str):
    """A file of the case other than the three (a phase file, a recover file, a document whose links follow a move)."""
    remember(path)
    path.write_text(text, encoding="utf-8")


# ---- writing with stamp discipline ---------------------------------------------------------------
def _atomic_write(path: Path, text: str):
    remember(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


def check_stamp(case: Path, name: str) -> WriteReport:
    """S3/S4: verify the stamp before writing. Mismatch → rebuild by grammar, move the rest out."""
    path = file_path(case, name)
    report = WriteReport(path)
    text = read(case, name)
    ok, state = stamp.verify(text)
    if ok or state == "missing":  # S2: no stamp yet → it will be set by this write
        return report
    report.bypassed = True
    rebuilt, removed, fatal = recover.rebuild(name, text)
    if rebuilt is None:
        details = "; ".join(str(f) for f in fatal)
        raise StoreError(f"{name}: stamp {state} and the file cannot be rebuilt — {details}", 3)
    _atomic_write(path, rebuilt)
    if removed:
        rec = case / f"{path.name}.recover.md"
        write_file(rec, "\n".join(removed) + "\n")
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
