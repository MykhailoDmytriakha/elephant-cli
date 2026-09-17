"""The ten commands of `el` — every write to the three files goes through here (P3).

Each function takes the case folder (already resolved by main), does its preconditions (exit 4),
validates through the grammar (exit 3) and writes with a fresh stamp. Functions return the lines
to print on success; warnings are collected in `Outcome.warnings` and printed to stderr by main.
"""
import datetime as dt
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import grammar, hints, migrate, order, stamp, store
from .store import StoreError

MAX_SCREEN = 24_000  # chars: Claude Code truncates tool output around 30K (owner's measurement 2026-08-22)
ENTRY_LIMIT = 10  # P1: last 10 journal entries on entry


@dataclass
class Outcome:
    lines: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def say(self, *ls):
        self.lines.extend(ls)

    def warn(self, *ws):
        self.warnings.extend(ws)

    def absorb(self, report: store.WriteReport):
        for f in report.warnings:
            self.warnings.append(f"{report.path.name}: {f}")
        if report.recovered:
            self.warnings.append(
                f"{report.path.name}: written bypassing Elephant — rebuilt by grammar, {report.recovered_lines} line(s) moved to "
                f"{report.recovered.name}: re-enter them with el, then run: rm '{report.recovered}' (S4)")
        elif report.bypassed:
            self.warnings.append(f"{report.path.name}: written bypassing Elephant — content was valid, stamp renewed (S4)")


def _now():
    t = dt.datetime.now()
    return t.strftime("%Y-%m-%d"), t.strftime("%H:%M")


def _phase_of(todo: grammar.Todo) -> str:
    cur = todo.current()
    return f"p{cur.n}" if cur else "p0"


# ---- TODO rendering (machine-owned text) ---------------------------------------------------------
BARE_PHASE_PATH_RE = re.compile(r"(?<![\w/(\[`])(phases/\d+-[a-z0-9-]+\.md)(?![\w)`])")


def _phase_link(file_name: str) -> str:
    """The phase file cited from TODO — a markdown link, so the editor opens it (feedback 2026-09-08:
    a bare `phases/2-calls.md` is text to the reader, `[…](…)` next to it is a link)."""
    return f"[phases/{file_name}](phases/{file_name})"


def _link_phase_paths(summary: str) -> str:
    """A phase line written before 0.18 cites its file as a bare path; every write renders it as a link."""
    return BARE_PHASE_PATH_RE.sub(lambda m: f"[{m.group(1)}]({m.group(1)})", summary)


def _item_block(it: grammar.Item) -> List[str]:
    """The item as TODO renders it (F4 · F20 · F22): its line with the suffixes el keeps outside the F13
    count (after · due · hold), then the pockets in one fixed order — `why:` · `note:`… · `result:` with
    one proof line under it per kind (file · ref · run · owner). A done item without result words (ticked
    before 1.10.0, or a child case at its parent) lists its proof lines directly under the item. Written
    by el, read by the owner: the tick, the words and the proof are three lines, not one (the owner's
    word, 2026-09-15 — «результат в одну строку неудобно»)."""
    mark = "x" if it.done else ("~" if it.held else " ")
    suffix = ((f" — after: {', '.join(it.after)}" if it.after else "") + (f" — due: {it.due}" if it.due else "")
              + (f" — hold: {it.hold_reason}" if it.held and it.hold_reason else ""))
    lines = [f"  - [{mark}] {it.n}.{it.m} {it.text}{suffix}"]
    if it.why:
        lines.append(f"    - why: {it.why}")
    lines += [f"    - note: {n}" for n in it.notes]
    if it.expect:
        lines.append(f"    - expect: {it.expect}")
    if it.done and (it.result or it.evidence):
        deeper = "      " if it.result else "    "
        if it.result:
            lines.append(f"    - result: {it.result}")
        lines += [f"{deeper}- {k}: {pr}" if pr else f"{deeper}- {k}" for k, pr in it.evidence]
    return lines


def render_todo(todo: grammar.Todo) -> str:
    out = [f"# {todo.title}", ""]
    for p in sorted(todo.phases, key=lambda x: x.n):
        mark = "x" if p.done else " "
        head = f"- [{mark}] {p.n} {p.name}"
        if p.summary:
            head += f" — {_link_phase_paths(p.summary)}"
        out.append(head)
        out += [f"  - note: {n}" for n in p.notes]  # F22: what the phase has to know, parked until it runs
        for it in [i for i in p.items if not i.held] + [i for i in p.items if i.held]:
            out += _item_block(it)
        for w in p.waits:
            out.append(f"  - waits: {w}")
    return "\n".join(out) + "\n"


def _derive_todo(case: Path, todo: grammar.Todo) -> bool:
    """F18: the line of an open phase carries its `goal:` and the path to its file — rendered from
    the file, never typed; a planned phase (no file yet) keeps its intent. Returns True on change."""
    changed = False
    for p in todo.phases:
        if p.done:
            continue
        pf = _phase_file(case, p.n, p.name)
        if not pf.exists():
            continue
        try:
            parsed = grammar.parse_phase_file(pf.read_text(encoding="utf-8"))
        except OSError:
            continue
        if parsed.errors or not parsed.goal:
            continue
        tail = f"{order._short(parsed.goal, 110)} · {_phase_link(pf.name)}"
        if p.summary != tail:
            p.summary, changed = tail, True
    return changed


def _write_todo(case: Path, todo: grammar.Todo):
    """The one door for TODO writes: derived lines first (F18), then the stamp door."""
    _derive_todo(case, todo)
    return store.write(case, "TODO.md", render_todo(todo))


def _unparsable(case: Path, name: str) -> StoreError:
    """The precise blocker: a legacy file (never stamped, outside the grammar) names `el migrate`;
    a file el wrote that broke since names `el check` (S4 rebuilds it on the next write)."""
    why = migrate.legacy_reason(case, name)
    if why:
        return StoreError(f"{name} is outside Elephant's grammar and was never stamped by Elephant ({why}) — a legacy case; "
                          f"nothing is written until it is migrated", 3, recovery=store.MIGRATE_HINT)
    return StoreError(f"{name} is not parsable — see the violations: el check", 3, recovery="el check")


def _todo(case: Path, out: Optional[Outcome] = None) -> grammar.Todo:
    if migrate.legacy_reason(case, "TODO.md"):
        raise _unparsable(case, "TODO.md")  # before store.load: a legacy file is never rebuilt
    body, report = store.load(case, "TODO.md")
    if out is not None:
        out.absorb(report)
    todo = grammar.parse_todo(body)
    if todo.errors:
        raise _unparsable(case, "TODO.md")
    return todo


# ---- README helpers -----------------------------------------------------------------------------
def _readme_text(case: Path, out: Optional[Outcome] = None) -> str:
    body, report = store.load(case, "README.md")
    if out is not None:
        out.absorb(report)
    return body


def _set_state_line(readme: str, prefix: str, value: Optional[str]) -> str:
    """Replace (or add / remove when value is None) the `- <prefix>` line inside `## State`.
    A new line goes at the end of the section's text, before the blank line that precedes the
    next heading."""
    lines = readme.rstrip("\n").split("\n")
    out, in_state, done = [], False, False

    def add_line():
        k = len(out)
        while k > 0 and out[k - 1] == "":
            k -= 1
        out.insert(k, f"- {prefix}{value}")

    for ln in lines:
        if ln.startswith("## "):
            if in_state and not done and value is not None:
                add_line()
                done = True
            in_state = ln == "## State"
        if in_state and ln.startswith(f"- {prefix}"):
            if value is not None and not done:
                out.append(f"- {prefix}{value}")
            done = True  # replaced or removed
            continue
        out.append(ln)
    if in_state and not done and value is not None:
        add_line()
    return "\n".join(out) + "\n"


def progress_line(todo: grammar.Todo, case: Optional[Path] = None) -> str:
    """`✓` closed · `▶` opened (its phase file exists) · no mark = planned (F3)."""
    parts = []
    for p in sorted(todo.phases, key=lambda x: x.n):
        opened = case is not None and _phase_file(case, p.n, p.name).exists()
        cancelled = p.done and (p.summary or "").startswith("снято")
        mark = (" ✗" if cancelled else " ✓") if p.done else (" ▶" if opened else "")
        parts.append(f"{p.n} {p.name}{mark}")
    return " · ".join(parts) if parts else "(no phases yet)"


def _is_project(case: Path) -> bool:
    """Root mode: the case folder is the project folder itself (it holds `.cases/`)."""
    return (case / store.CASES_DIR).is_dir()


def _replace_section(body: str, name: str, new_lines: List[str]) -> str:
    """Replace the lines of `## <name>` in place, leaving every other byte of the README as it is."""
    lines = body.rstrip("\n").split("\n")
    start = next((i for i, ln in enumerate(lines) if ln == f"## {name}"), None)
    if start is None:
        return body
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[: start + 1] + new_lines + ([""] if end < len(lines) else []) + lines[end:]) + "\n"


def _derive_readme(case: Path, body: str) -> str:
    """Refresh what el owns inside README: `progress:` (from TODO), `last:` (newest RESULT in the
    journal), and the folder/file lines of Links (from the files' own `summary:` lines, F14).
    What the agent wrote stays; only the derived parts move. Unparsable input is returned as is."""
    parsed = grammar.parse_readme(body)
    if parsed.errors:
        return body
    links, _ = order.render_links(case, _is_project(case), parsed.sections.get("Links", []))
    text = _replace_section(body, "Links", links)
    try:
        todo = grammar.parse_todo(store.read(case, "TODO.md"))
        if not todo.errors:
            text = _set_state_line(text, "progress: ", progress_line(todo, case))
    except StoreError:
        pass
    try:
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
        last = next((ev.text for e in journal.entries for ev in e.events if ev.type == "RESULT"), None)
        if last:
            text = _set_state_line(text, "last: ", order._short(last, grammar.README_POINTER_CHARS - 10))
    except StoreError:
        pass
    return _blank_before_headings(text)


def _blank_before_headings(text: str) -> str:
    """Exactly one blank line before every `## ` heading — the shape a reader expects, whatever
    the agent's draft looked like."""
    out: List[str] = []
    for ln in text.rstrip("\n").split("\n"):
        if ln.startswith("## "):
            while out and out[-1] == "":
                out.pop()
            if out:
                out.append("")
        out.append(ln)
    return "\n".join(out) + "\n"


def _write_readme(case: Path, body: str, out: Outcome, anchor: bool = False):
    """Every README write goes through here: derived parts refreshed, `as of` anchored when the
    agent rewrote State (S5), then the stamp door."""
    if anchor:
        try:
            header = order.newest_header(grammar.parse_journal(store.read(case, "JOURNAL.md")))
        except StoreError:
            header = None
        if header:
            body = _set_state_line(body, "as of: ", header)
    out.absorb(store.write(case, "README.md", _derive_readme(case, body)))


def _sync_progress(case: Path, todo: grammar.Todo, out: Outcome):
    _write_readme(case, _readme_text(case, out), out)


# ---- journal ------------------------------------------------------------------------------------
BODY_WRAP = 160


def _render_event(typ: str, text: str):
    """Turn text into journal lines: `  TYPE · headline` + up to 5 wrapped body lines (F7).

    A long text is split at word boundaries instead of being refused — the limit shapes the
    record, it must not block the write (live feedback 2026-08-31). An author's line break is kept
    as a body line of its own: fields written one per line stay one per line (feedback 2026-09-14:
    `closed BUG-1 / root: a / fix: b` came out as one run-on sentence, and nothing said so).
    """
    paras = [" ".join(p.split()) for p in text.split("\n") if p.strip()]
    text, extra = (paras[0] if paras else ""), paras[1:]
    if extra:
        lines, _ = _render_event(typ, text)  # the first line is the headline (split by length if it must)
        if not lines[0].endswith(" …"):
            lines[0] += " …"  # a headline with a body says so — the entry shows headlines only
        body = [ln[4:] for ln in lines[1:]]
        for para in extra:
            while len(para) > BODY_WRAP:
                cut = para.rfind(" ", 0, BODY_WRAP)
                cut = cut if cut > 0 else BODY_WRAP
                body.append(para[:cut])
                para = para[cut:].strip()
            body.append(para)
        if len(body) > grammar.EVENT_BODY_LINES:
            raise StoreError(f"event text is too long even for a headline plus {grammar.EVENT_BODY_LINES} body lines (F7) — "
                             f"put the story into the phase file and log a short line with a path", 3)
        return [lines[0]] + [f"    {b}" for b in body], True
    if len(f"{typ} · {text}") <= grammar.EVENT_CHARS:
        return [f"  {typ} · {text}"], False
    # split under the SOFT threshold, so a split line never triggers "close to the limit" later
    head_budget = grammar.EVENT_WARN_CHARS - len(typ) - 3
    words = text.split(" ")
    head, i = "", 0
    while i < len(words) and len(head) + len(words[i]) + 1 <= head_budget - 2:
        head += (" " if head else "") + words[i]
        i += 1
    if not head:  # a single word longer than the whole headline — hard cut
        head, words[0] = words[0][: head_budget - 2], words[0][head_budget - 2:]
        i = 0
    rest, body = " ".join(words[i:]), []
    while rest and len(body) < grammar.EVENT_BODY_LINES:
        if len(rest) <= BODY_WRAP:
            body.append(rest)
            rest = ""
        else:
            cut = rest.rfind(" ", 0, BODY_WRAP)
            cut = cut if cut > 0 else BODY_WRAP
            body.append(rest[:cut])
            rest = rest[cut:].strip()
    if rest:
        raise StoreError(f"event text is too long even for a headline plus {grammar.EVENT_BODY_LINES} body lines (F7) — "
                         f"put the story into the phase file and log a short line with a path", 3)
    return [f"  {typ} · {head} …"] + [f"    {b}" for b in body], True


def _resolve_phase(todo: grammar.Todo, ref: str) -> str:
    """Accept what the user sees — `p1`, `1`, `4.1` or a unique phase name — and return canonical `pN`."""
    ref = ref.strip()
    if re.fullmatch(r"p\d+(\.\d+)?", ref):
        return ref
    if re.fullmatch(r"\d+(\.\d+)?", ref):
        return f"p{ref}"
    named = [p for p in todo.phases if p.name.lower() == ref.lower()]
    if len(named) == 1:
        return f"p{named[0].n}"
    known = " · ".join(f"p{p.n} {p.name}" for p in sorted(todo.phases, key=lambda x: x.n)) or "none yet"
    raise StoreError(f"cannot resolve phase `{ref}` — use the canonical form, e.g. `el log --phase p1 DECISION \"…\"`; "
                     f"phases here: {known}", 2)


def log(case: Path, typ: str, text: str, phase: Optional[str] = None) -> Outcome:
    out = Outcome()
    typ = typ.upper()
    if typ not in grammar.JOURNAL_TYPES:
        raise StoreError(f"unknown type `{typ}` — allowed: PHASE · DECISION · PROBLEM · RESULT (F8)", 2)
    event_lines, split = _render_event(typ, text)
    if split and "\n" in text.strip():
        out.warn(f"event written as a headline + {len(event_lines) - 1} body line(s): your line breaks are kept (F7)")
    elif split:
        out.warn(f"event longer than {grammar.EVENT_CHARS} chars — split into headline + {len(event_lines) - 1} body line(s) (F7)")
    todo = _todo(case, out)
    phase = _resolve_phase(todo, phase) if phase else _phase_of(todo)
    date, time = _now()
    if migrate.legacy_reason(case, "JOURNAL.md"):
        raise _unparsable(case, "JOURNAL.md")
    body, report = store.load(case, "JOURNAL.md")
    out.absorb(report)
    lines = body.rstrip("\n").split("\n")
    header = f"- {date} {time} · {phase}"
    first = next((i for i, ln in enumerate(lines) if grammar.ENTRY_RE.match(ln)), None)
    if first is not None and lines[first] == header:
        j = first + 1
        while j < len(lines) and lines[j].startswith("  "):
            j += 1
        lines[j:j] = event_lines
    else:
        at = first if first is not None else len(lines)
        block = [header] + event_lines
        if at < len(lines) and first is not None:
            lines[at:at] = block
        else:
            if lines and lines[-1] != "":
                lines.append("")
            lines.extend(block)
    report = store.write(case, "JOURNAL.md", "\n".join(lines) + "\n")
    inserted = set()
    for idx, ln in enumerate(lines, start=1):
        if ln == header or ln in event_lines:
            inserted.add(idx)
    report.warnings = [w for w in report.warnings if w.line == 0 or w.line in inserted]
    out.absorb(report)
    out.say(f"logged: {typ} → JOURNAL.md ({header[2:]})")
    if typ == "RESULT":  # README `last:` follows the newest RESULT (derived, never hand-written)
        try:
            _write_readme(case, _readme_text(case), out)
        except StoreError as e:
            out.warn(f"README `last:` not refreshed — {e}")
    if typ == "PROBLEM":
        hints.attach(out, "log", typ=typ, project=_project_root(case))
    return out


def _events_for_phase(journal: grammar.Journal, phase: str):
    return [ev for e in journal.entries if e.phase == phase for ev in e.events]


def _journal(case: Path, out: Optional[Outcome] = None) -> grammar.Journal:
    if migrate.legacy_reason(case, "JOURNAL.md"):
        raise _unparsable(case, "JOURNAL.md")
    body, report = store.load(case, "JOURNAL.md")
    if out is not None:
        out.absorb(report)
    j = grammar.parse_journal(body)
    if j.errors:
        raise _unparsable(case, "JOURNAL.md")
    return j


def _trim_suggestion(text: str, limit: int) -> str:
    cut = text.rfind(" ", 0, limit)
    return text[: cut if cut > limit // 2 else limit].rstrip()


# ---- todo ---------------------------------------------------------------------------------------
EVIDENCE_KINDS_HELP = ("file:<path in the case or the project> (a photo, pdf, receipt, letter, screenshot, transcript, a source file) · "
                       "ref:<trace outside the case> (a request number, a URL, a letter in the mailbox) · "
                       "run:\"<command -> outcome>\" (a machine check; → or ->) · owner (the owner's word — the only word that counts)")


def _parse_evidence(case: Path, ref: str, token: str):
    """`file:evidence/x.jpg` → ("file", "[x.jpg](evidence/x.jpg)") · `ref:D005532` → ("ref", "D005532") ·
    `run:"cmd → out"` → ("run", "cmd → out") · `owner` → ("owner", ""). Anything else is refused with
    the four kinds: the list is closed on purpose (the owner's word, 2026-09-14) — a kind that is
    missing arrives through `el feedback`, not through a fifth spelling. The tool checks what it can:
    a file exists in the case, a run has its arrow, owner carries no value; the truth is the owner's."""
    token = token.strip()
    if not token:
        raise StoreError(f"done takes the kind of evidence first (F20): el todo done {ref} <kind> \"what came out\" — "
                         f"four kinds: {EVIDENCE_KINDS_HELP}; a kind that is missing: el feedback \"…\" · el help evidence", 2)
    kind, _, value = token.partition(":")
    kind, value = kind.strip().lower(), value.strip()
    if kind not in grammar.EVIDENCE_KINDS:
        raise StoreError(f"`{token}` is not a kind of evidence — done takes the kind first: el todo done {ref} <kind> \"what came out\"; "
                         f"four kinds, closed on purpose: {EVIDENCE_KINDS_HELP}; need another: el feedback \"…\" · el help evidence", 2)
    if kind == "owner":
        if value:
            raise StoreError(f"owner takes no value — the outcome IS the owner's word: el todo done {ref} owner \"what the owner confirmed\"", 2)
        return kind, ""
    if not value:
        example = {"file": "file:evidence/receipt.pdf", "ref": "ref:D005532-091426",
                   "run": "run:\"python3 -m unittest → 12 OK\""}[kind]
        raise StoreError(f"{kind}: needs a value — e.g. el todo done {ref} {example} \"what came out\"", 2)
    if kind == "file":
        m = re.fullmatch(r"\[[^\]]*\]\(([^)]+)\)", value)  # a link pasted whole is accepted; the path is what counts
        if m:
            value = m.group(1)
        if value.startswith(("/", "~")) or ".." in Path(value).parts:
            raise StoreError(f"file: takes a path inside the case or the project, e.g. file:evidence/receipt.pdf or "
                             f"file:src/app/parser.ts — not `{value}`", 2)
        target = _evidence_file(case, value)
        if target is None:
            raise StoreError(f"file:{value} — no such file in the case or the project (paths are read from the case folder, "
                             f"then from the project root); put it there or name what you have: ref:<trace> · owner", 3)
        return kind, f"[{target.name}]({os.path.relpath(target, case)})"
    if kind == "run":
        value = value.replace("->", "→")  # ASCII is accepted, the record keeps one arrow
        if "→" not in value:
            # feedback 2026-09-15: `run:curl x -> UP` typed WITHOUT quotes reached el as `run:curl x -` — the shell took
            # `>` as a redirection and wrote the outcome into a file; the refusal named only → and the agent
            # concluded that -> is rejected. A trailing `-` is the trace; it is named, like a swallowed `$150`.
            trace = (" — the value ends with `-`: a `->` cut by the shell? unquoted, `>` redirects the rest into a file "
                     "named like the outcome (remove it); quote the value" if value.rstrip().endswith("-") else "")
            raise StoreError(f"run: needs the command and what came out, joined by → or ->: "
                             f"el todo done {ref} run:\"python3 -m unittest -> 12 OK\" \"…\"{trace}", 2)
        return kind, value
    return kind, value


def _expect_check(phase: grammar.Phase, items: List[grammar.Item]):
    """Hold `done` to the item's own `expect:` (F22): which promised proofs arrived, which did not. Shown, never
    refused — the expectation may have been wrong, and the honest move is to say so, not to forge a proof.
    Returns (the note the RESULT carries when something is short — "" when every promise is kept, the lines to say)."""
    notes, lines = [], []
    out = Outcome()
    for it in items:
        slots = grammar.expected_kinds(it.expect)
        if not slots:
            continue
        have = {k for k, _ in it.evidence}
        filled = [(k, w) for k, w in slots if k in have]
        missing = [(k, w) for k, w in slots if k not in have]
        ref = f"{phase.n}.{it.m}"
        if missing:
            gap = " ".join(f"[{k}: {w}]" if w else f"[{k}]" for k, w in missing)
            out.say(f"expect {ref}: {len(filled)} of {len(slots)} filled — missing {gap}: the proof is short, or the expectation "
                    f"was wrong — say which: el todo done {ref} <kind> \"…\" adds a proof · el todo expect {ref} \"…\" corrects the promise")
            notes.append(f"{ref} expected {' · '.join(k for k, _ in slots)}, got {' · '.join(sorted(have)) or 'nothing'}")
        else:
            out.say(f"expect {ref}: {len(slots)} of {len(slots)} filled — {' · '.join(k for k, _ in slots)}")
        # the promise next to what arrived, in words — the tool matches kinds, the reader matches meaning
        # (feedback 2026-09-16: «HTTP 200 with benefits» filled a run slot that meant «discount applied»)
        for k, w in filled:
            if w:
                brought = next((pr for kk, pr in it.evidence if kk == k), "")
                out.say(f"  {_slot(k, w)} ← {k} {brought}".rstrip() + "  — does it show that?")
    return "; ".join(notes), out.lines


def _link_path(proof: str) -> str:
    m = re.fullmatch(r"\[[^\]]*\]\(([^)]+)\)", proof)
    return m.group(1) if m else proof


def _proof_warnings(phase: grammar.Phase, items: List[grammar.Item], proofs: List[Tuple[str, str]], out: Outcome):
    """What the tool can see about a proof without judging its truth (the owner's eye, 2026-09-16: a closed
    phase whose four items all pointed at one markdown the agent had written — the link resolved, the proof was
    hollow). Shown at the moment of writing, never refused: sometimes a case document IS the deliverable, and
    two items may honestly share one receipt."""
    named = ", ".join(f"{phase.n}.{it.m}" for it in items)
    for kind, proof in proofs:
        if kind != "file":
            continue
        path = _link_path(proof)
        if path.endswith(".md") and not path.startswith("../"):
            out.warn(f"file:{path} is a markdown inside the case — your own text, not the thing it describes. The proof is "
                     f"what stands behind it: run:\"<command → outcome>\" for a call or a test, file:<source or spec in the "
                     f"project> for code, file:<saved response, log, screenshot> for a result; keep the document as material")
        others = [f"{phase.n}.{it.m}" for it in phase.items if it.done and it not in items
                  and any(k == "file" and _link_path(pr) == path for k, pr in it.evidence)]
        if others:
            out.warn(f"file:{path} already proves {', '.join(others)} — one file for {len(others) + len(items)} items: "
                     f"is it the artifact of each, or one report about all of them? items are cut by what they leave behind — "
                     f"one outcome with its own proof each; two items with one artifact were one item with steps in its notes")
    for it in items:
        for k, note in enumerate(it.notes, start=1):
            if _note_repeats_proof(note, proofs + list(it.evidence)):
                out.warn(f"{phase.n}.{it.m} note {k} only points at the proof file — a note carries a constraint or context, the proof "
                         f"line carries the file: el todo note {phase.n}.{it.m} --drop {k}")
    if not named:
        return


def _note_repeats_proof(note: str, proofs: List[Tuple[str, str]]) -> bool:
    """A note that is nothing but a link to a file already standing as the item's proof (2026-09-16: «Documented
    in [x](…)» above `- file: [x](…)`)."""
    links = re.findall(r"\]\(([^)]+)\)", note)
    if not links:
        return False
    paths = {_link_path(pr) for k, pr in proofs if k == "file"}
    stripped = re.sub(r"\[[^\]]*\]\([^)]+\)", "", note)
    return all(ln in paths for ln in links) and len(stripped.split()) <= 3


def _project_root(case: Path) -> Path:
    """The folder that holds `.cases/` — the project the case works on. In root mode the case IS the
    project; a nested case walks up to the `.cases/` above it."""
    if (case / store.CASES_DIR).is_dir():
        return case
    for d in case.parents:
        if d.name == store.CASES_DIR:
            return d.parent
    return case


def _evidence_file(case: Path, value: str) -> Optional[Path]:
    """`file:` evidence resolves in the case first, then in the project (feedback 2026-09-14: for
    software work the proof IS the source file, `frontend/app/utils/x.ts` — forcing it into `ref`
    made ref mean «a path we could not check»). Outside the project → None."""
    for base in (case, _project_root(case)):
        target = (base / value)
        if target.is_file():
            resolved = target.resolve()
            try:
                resolved.relative_to(_project_root(case).resolve())
            except ValueError:
                return None
            return resolved
    return None


CODE_TRACE_RES = (re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b"),  # a commit hash — hex with at least one letter
                  re.compile(r"\b\w+\(\)"),                                 # a call: update()
                  re.compile(r"[!=]=|::|->\s*\w+\("))                          # code operators


def _outcome_warning(outcome: str, out: Outcome) -> None:
    """The words of `done` are for the owner who was not in the session (feedback 2026-09-16: «Commit f3277f8149
    removed marketSegment == HA check and gutted update()» — a code trace where the owner wanted «why was it
    disconnected»). The tool cannot judge meaning; it can see a token class: a commit hash, a call, an operator.
    A trace is proof — `ref:<hash>`, `file:<source>` — not the words. Shown, never refused."""
    found = [m.group(0) for rx in CODE_TRACE_RES for m in rx.finditer(outcome)]
    if not found:
        return
    hashes = [t for t in found if re.fullmatch(r"[0-9a-f]{7,40}", t)]
    proof = f"ref:{hashes[0]}" if hashes else "ref:<trace>"
    out.warn(f"the words of done read like a code trace ({', '.join(found[:3])}) — the owner reads TODO and JOURNAL: say what "
             f"came out for the item, in the owner's words; the trace is proof, not the words: {proof} · file:<the source file> "
             f"(el help practice)")


def _is_kind_token(token: str) -> bool:
    """A leading argument of `done` that names evidence: `file:…` · `ref:…` · `run:…` · `owner`."""
    return bool(re.fullmatch(r"(file|ref|run):.+", token, re.S)) or token.strip() == "owner"


def todo_done(case: Path, ref: str, tokens: List[str], outcome: str = "") -> Outcome:
    """Done with evidence (F20): `el todo done N.M <kind> [<kind> …] "what came out"` — the kinds come
    first (file:<path> · ref:<trace> · run:"<command → outcome>" · owner), several when the proof is several
    things; the outcome goes to the journal as `RESULT · N.M: <kinds> — …` and under the TODO line as
    `result: …` with one proof line per kind (F22). The tick, the words and the proofs are one write.
    Nothing to say? Then it was not done: `el todo cancel N.M "why"`. A second `done` on a done item ADDS
    evidence and renews the words (the owner's word, 2026-09-15: several artifacts per item) — the door for
    items ticked before 1.5.0, which carry no kind and are never nagged: the rule lives at the write."""
    out = Outcome()
    if not re.fullmatch(r"[\d.,\s–-]+", ref) or "." not in ref:
        raise StoreError("use `el todo done N.M <kind> \"what came out\"` (or a range N.A-N.B, a list N.A, N.B) for items, "
                         "`el phase close N` for a phase", 2)
    if not tokens:
        _parse_evidence(case, ref, "")  # raises the four-kinds refusal
    proofs: List[Tuple[str, str]] = []
    for token in tokens:
        kind, proof = _parse_evidence(case, ref, token)
        if kind == "ref" and not re.match(r"^[a-z][a-z0-9+.-]*:", proof) and _evidence_file(case, proof.split(" ")[0]) is not None:
            out.warn(f"ref:{proof} is a file in reach — file:{proof.split(' ')[0]} would be checked (it exists) and linked; "
                     f"ref is for a trace outside the case a person checks elsewhere")
        if (kind, proof) not in proofs:
            proofs.append((kind, proof))
    outcome = " ".join(outcome.split())
    _outcome_warning(outcome, out)
    if not outcome:
        raise StoreError(f"done needs what came out (F20): el todo done {ref} {' '.join(tokens)} \"what came out\" — "
                         f"nothing came out? then it was not done: el todo cancel {ref} \"why\"", 2)
    # the `result:` line is el's (rendered from done): it obeys el's own pointer limit by shaping, like `closed:`
    # and `last:` — the journal RESULT keeps the whole outcome (feedback 2026-09-16: a 151-char outcome aborted a chain)
    shown_outcome = order._short(outcome, grammar.POCKET_CHARS)
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)
    _proof_warnings(phase, items, proofs, out)
    already = [it for it in items if it.done]
    fresh = [it for it in items if not it.done]
    blocking = _blocking(case, todo)
    done_now = {f"{phase.n}.{it.m}" for it in fresh}
    was = {f"{phase.n}.{it.m}": (list(it.evidence), it.result) for it in already}
    for it in fresh:
        it.done, it.held, it.hold_reason = True, False, ""
        it.evidence = list(proofs)
    for it in already:
        it.evidence += [pr for pr in proofs if pr not in it.evidence]
    for it in items:
        it.result = shown_outcome
    out.absorb(_write_todo(case, todo))
    refs = _refs(phase, items)
    shown = " · ".join(f"{k} {pr}".strip() for k, pr in proofs)
    short, expect_lines = _expect_check(phase, items)
    out.lines += log(case, "RESULT", f"{refs}: {shown} — {outcome}" + (f" ({short})" if short else ""), f"p{phase.n}").lines
    for it in fresh:
        left = [r for r, _ in blocking.get(f"{phase.n}.{it.m}", []) if r not in done_now]
        if left:
            out.warn(f"{phase.n}.{it.m} was after {', '.join(left)}, still open — was the dependency wrong, or the order?")
    if len(fresh) == 1:
        out.say(f"done: {_refs(phase, fresh)} {fresh[0].text} → TODO.md (result + {len(proofs)} proof line(s)) · RESULT in the journal · evidence: {shown}")
    elif fresh:
        out.say(f"done: {_refs(phase, fresh)} ({len(fresh)} items) → TODO.md · one RESULT in the journal · evidence: {shown}")
    if shown_outcome != outcome:
        out.say(f"result: line shortened to {grammar.POCKET_CHARS} chars in TODO (F22, el's line) — the whole outcome is in the journal RESULT")
    out.say(*expect_lines)  # after `done:` — the promise, then what arrived
    hints.attach(out, "todo_done", items=items, proofs=proofs)
    for it in already:
        ev0, words0 = was[f"{phase.n}.{it.m}"]
        before = " · ".join(f"{k} {pr}".strip() for k, pr in ev0) or "untyped"
        renewed = f"result renewed (was: «{words0}»)" if words0 and words0 != outcome else "result kept"
        out.say(f"{phase.n}.{it.m} was already done — evidence now: "
                f"{' · '.join(f'{k} {pr}'.strip() for k, pr in it.evidence)} (was: {before}) · {renewed} · RESULT in the journal")
    return out


def _split_suffixes(text: str):
    """`text — after: N.M, case — due: YYYY-MM-DD` → (text, due, after); either suffix may be absent.
    A date the tool can parse is a date it can count (feedback 2026-09-03); a dependency the tool
    can parse is a dependency it can check (F19)."""
    text = " ".join(text.split())
    due, after = "", []
    if " — due: " in text:
        text, d = text.rsplit(" — due: ", 1)
        due = _valid_date(d.strip())
    if " — after: " in text:
        text, refs = text.rsplit(" — after: ", 1)
        after = [x.strip() for x in refs.split(",") if x.strip()]
    return text.strip(), due, after


def _all_items(todo: grammar.Todo) -> List[grammar.Item]:
    return [it for p in todo.phases for it in p.items]


def _find_cycle(todo: grammar.Todo) -> Optional[List[str]]:
    """A cycle among `after` edges between items, as a path; None when the graph is a DAG."""
    graph = {f"{it.n}.{it.m}": [r for r in it.after if re.fullmatch(r"\d+\.\d+", r)] for it in _all_items(todo)}
    color = {k: 0 for k in graph}
    stack: List[str] = []

    def visit(u: str):
        color[u] = 1
        stack.append(u)
        for v in graph.get(u, []):
            if v not in graph:
                continue
            if color[v] == 1:
                return stack[stack.index(v):] + [v]
            if color[v] == 0:
                found = visit(v)
                if found:
                    return found
        stack.pop()
        color[u] = 2
        return None

    for k in graph:
        if color[k] == 0:
            found = visit(k)
            if found:
                return found
    return None


def _set_after(case: Path, todo: grammar.Todo, item: grammar.Item, refs: List[str]):
    """Validate and set `after` (F19): every N.M exists (any phase) and is not the item itself, a
    name is a nested case; no cycle appears. Raises before anything is written."""
    kids = {k.name for k in order.child_cases(case, _is_project(case))}
    items = {f"{it.n}.{it.m}" for it in _all_items(todo)}
    me = f"{item.n}.{item.m}"
    clean: List[str] = []
    for ref in refs:
        if not grammar.AFTER_REF_RE.fullmatch(ref):
            raise StoreError(f"`{ref}` — after expects N.M or a nested case name (F19)", 2)
        if re.fullmatch(r"\d+\.\d+", ref):
            if ref == me:
                raise StoreError(f"{me} cannot be after itself", 2)
            if ref not in items:
                raise StoreError(f"no item {ref} to be after — check the number or add it first (el todo add N \"…\")", 4)
        elif ref not in kids:
            raise StoreError(f"`{ref}` is neither an item N.M nor a nested case here" + (f" (cases: {', '.join(sorted(kids))})" if kids else ""), 4)
        if ref not in clean:
            clean.append(ref)
    old, item.after = item.after, clean
    cycle = _find_cycle(todo)
    if cycle:
        item.after = old
        raise StoreError(f"after would close a cycle: {' → '.join(cycle)} (F19)", 3)


def _next_number(case: Path, todo: grammar.Todo, phase: grammar.Phase) -> int:
    """The next free number in a phase: above every item present, every `after` reference and every
    number the journal already speaks of — a number someone still refers to is never reused (F19,
    the Codex finding: a moved item freed its number and `after` would have pointed at a stranger)."""
    used = {it.m for it in phase.items}
    for it in _all_items(todo):
        for r in it.after:
            m = re.fullmatch(rf"{phase.n}\.(\d+)", r)
            if m:
                used.add(int(m.group(1)))
    try:
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
    except StoreError:
        journal = None
    if journal is not None:
        pat = re.compile(rf"(?<![\d.]){phase.n}\.(\d+)(?![\d.])")
        for e in journal.entries:
            for ev in e.events:
                for m in pat.finditer(ev.text):
                    used.add(int(m.group(1)))
    return max(used, default=0) + 1


def _blocking(case: Path, todo: grammar.Todo) -> Dict[str, List[Tuple[str, str]]]:
    """item key → [(ref, 'open' | 'case open' | 'gone')] for open items with unsatisfied `after`."""
    items = {f"{it.n}.{it.m}": it for it in _all_items(todo)}
    kids = {k.name: order.child_status(k)[0] for k in order.child_cases(case, _is_project(case))}
    out: Dict[str, List[Tuple[str, str]]] = {}
    for it in _all_items(todo):
        if it.done or not it.after:
            continue
        blockers = []
        for r in it.after:
            if r in items:
                if not items[r].done:
                    blockers.append((r, "open"))
            elif r in kids:
                if kids[r] != "closed":
                    blockers.append((r, "case open"))
            else:
                blockers.append((r, "gone"))
        if blockers:
            out[f"{it.n}.{it.m}"] = blockers
    return out


def _unblocked_line(case: Path, todo: grammar.Todo) -> Optional[str]:
    """Printed on entry only when the case declares dependencies: open items whose blockers are all
    done, ordered by due date then position — candidates, not the owner's `next:` (Codex: ready ≠
    what should happen next; never persisted into README)."""
    if not any(it.after for it in _all_items(todo)):
        return None
    blocking = _blocking(case, todo)
    open_items = [it for p in todo.phases if not p.done for it in p.items if not it.done and not it.held]
    ready = sorted((it for it in open_items if f"{it.n}.{it.m}" not in blocking), key=lambda it: (it.due or "9999-99-99", it.n, it.m))
    blocked = [(it, blocking[f"{it.n}.{it.m}"]) for it in open_items if f"{it.n}.{it.m}" in blocking]
    shown = ", ".join(f"{it.n}.{it.m} «{order._short(it.text, 40)}»" for it in ready[:6]) + (f" … +{len(ready) - 6}" if len(ready) > 6 else "")
    parts = [f"unblocked: {shown or 'none'}"]
    if blocked:
        parts.append("blocked: " + ", ".join(f"{it.n}.{it.m} (after {', '.join(r for r, _ in bl)})" for it, bl in blocked[:6])
                     + (f" … +{len(blocked) - 6}" if len(blocked) > 6 else ""))
    return " · ".join(parts)


def _gone_lines(case: Path, todo: grammar.Todo) -> List[str]:
    """Order: an item waiting for something that no longer exists (cancelled or dropped) has two exits."""
    out = []
    for key, blockers in _blocking(case, todo).items():
        gone = [r for r, st in blockers if st == "gone"]
        if gone:
            out.append(f"{key} is after {', '.join(gone)}, which is gone (cancelled or dropped) → el todo after {key} <refs|none> · or el todo cancel {key} \"why\"")
    return out


def todo_after(case: Path, ref: str, refs: str) -> Outcome:
    """Set (or clear with `none`) what item N.M waits for: `el todo after 2.5 "2.3, 1.7, case-name"`."""
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    if refs.strip().lower() in ("", "none", "-", "clear"):
        item.after = []
        out.absorb(_write_todo(case, todo))
        out.say(f"after cleared: {ref} waits for nothing")
        return out
    _set_after(case, todo, item, [x.strip() for x in refs.split(",") if x.strip()])
    out.absorb(_write_todo(case, todo))
    out.say(f"after: {ref} waits for {', '.join(item.after)} → TODO.md")
    return out


def _valid_date(due: str) -> str:
    if not grammar.DATE_RE.fullmatch(due):
        raise StoreError(f"`due:` must be YYYY-MM-DD, got `{due}` — e.g. `— due: 2026-09-13`", 2)
    try:
        dt.date.fromisoformat(due)
    except ValueError:
        raise StoreError(f"`{due}` is not a calendar date", 2)
    return due


def _pocket_text(label: str, text: str, ref: str) -> str:
    """A pocket line (F22) at the write door: one line, non-empty, within the pointer limit."""
    text = " ".join(text.split())
    if not text:
        raise StoreError(f"{label} needs a text: el todo {label} {ref} \"…\"", 2)
    if grammar.visible_len(text) > grammar.POCKET_CHARS:
        raise StoreError(f"{label}: is {grammar.visible_len(text)} visible chars, limit {grammar.POCKET_CHARS} (F22) — a pocket points at "
                         f"context, the context itself goes to a file in the case, linked [name](docs/file.md)\n"
                         f"  suggestion: \"{_trim_suggestion(text, grammar.POCKET_CHARS)}\"", 3)
    return text


REPHRASE_HINT = ("  rephrase, do not truncate: verb first, the path or flag stays, the filler goes — "
                 "«Trigger /v3/x, confirm FLAG=false in pod logs» is one action with its checkable outcome")


def _item_context(it: grammar.Item) -> str:
    return " ".join([it.text, it.why, *it.notes, it.expect])


def _expect_text(text: str, ref: str) -> str:
    """`expect:` at the write door (F22): a pocket line whose bracketed placeholders name proofs from the
    closed list — `[file: docs/x.md] [run: k6 → p95] [owner]`; a fifth word in brackets is refused with the
    four, like a fifth kind at `done`."""
    text = _pocket_text("expect", text, ref)
    for m in grammar.ANY_SLOT_RE.finditer(text):
        if m.group(1) not in grammar.EVIDENCE_KINDS:
            raise StoreError(f"`[{m.group(1)}…]` is not a kind of proof — placeholders in expect are [file: what] · [ref: what] · "
                             f"[run: what] · [owner]; a kind that is missing: el feedback \"…\" · el help evidence", 2)
    return text


def _slot_key(kind: str, what: str) -> Tuple[str, str]:
    return kind, " ".join(what.lower().split())


def _goal_coverage(phase: grammar.Phase, goal: str) -> List[Tuple[Tuple[str, str], str, str]]:
    """Each proof the phase promised in its `goal:` (F12), against the items (feedback 2026-09-16: a phase closed
    on a baseline — HTTP 200 with benefits — while its goal was a discount applied; `check` said 0 violations
    because four criteria of one kind were satisfied by one run). A promise with words is covered by an ITEM
    whose `expect:` carries the same slot — the phase's statement decomposes into its items' statements — and
    is proved when that item is done with a proof of that kind. A bare kind (`[owner]`) is proved by any done
    item of that kind. Returns [(slot, status, ref)]: status ∈ proved · promised (item open) · uncovered."""
    out = []
    done_kinds = {k for it in phase.items if it.done for k, _ in it.evidence}
    for kind, what in grammar.expected_kinds(goal):
        key = _slot_key(kind, what)
        if not key[1]:
            out.append(((kind, what), "proved" if kind in done_kinds else "uncovered", ""))
            continue
        carriers = [it for it in phase.items if key in {_slot_key(k, w) for k, w in grammar.expected_kinds(it.expect)}]
        proved = [it for it in carriers if it.done and any(k == kind for k, _ in it.evidence)]
        if proved:
            out.append(((kind, what), "proved", f"{phase.n}.{proved[0].m}"))
        elif carriers:
            out.append(((kind, what), "promised", ", ".join(f"{phase.n}.{it.m}" for it in carriers)))
        else:
            out.append(((kind, what), "uncovered", ""))
    return out


def _slot(kind: str, what: str) -> str:
    return f"[{kind}: {what}]" if what else f"[{kind}]"


def _phase_goal(case: Path, phase: grammar.Phase) -> str:
    """The goal of a phase where it lives: the phase file once open, the TODO intent while planned."""
    pf = _phase_file(case, phase.n, phase.name)
    if pf.exists():
        parsed = grammar.parse_phase_file(pf.read_text(encoding="utf-8"))
        if not parsed.errors:
            return parsed.goal
    return phase.summary or ""


def _promise_lines(case: Path, todo: grammar.Todo) -> List[str]:
    """Order (F12): a proof the open phase promised in its goal that no item promises — the acceptance criterion
    nobody is working towards. Shown while the phase runs; the close refuses over it."""
    lines = []
    for p in todo.phases:
        if p.done or not _phase_file(case, p.n, p.name).exists():
            continue
        for (kind, what), status, ref in _goal_coverage(p, _phase_goal(case, p)):
            if status == "uncovered" and what:
                lines.append(f"phase {p.n} {p.name} promises {_slot(kind, what)} and no item promises it — the criterion nobody works towards: "
                             f"el todo add {p.n} \"…\" --expect \"{_slot(kind, what)}\" · or correct the goal line in phases/{_phase_file(case, p.n, p.name).name}")
    return lines


def _goal_text(goal: str) -> str:
    """A phase `goal:` may promise what the phase leaves behind, in the same brackets as an item's `expect:` —
    `[file: research/answer.md] [run: curl → 200]` — and the Digest holds the phase to it at close (the owner's
    word, 2026-09-16: the expectation lives at every size of the node). Unknown kinds are refused like at done."""
    goal = " ".join(goal.split())
    for m in grammar.ANY_SLOT_RE.finditer(goal):
        if m.group(1) not in grammar.EVIDENCE_KINDS:
            raise StoreError(f"`[{m.group(1)}…]` is not a kind of proof — placeholders in a goal are [file: what] · [ref: what] · "
                             f"[run: what] · [owner]; el help evidence", 2)
    return goal


def todo_show(case: Path, ref: str) -> Outcome:
    """`el todo show N.M` — the item's card at the moment of picking it up: its pockets, and the inputs a chain
    hands it — the proofs of the items it comes after (F19) — and what it feeds in turn (the owner's sketch,
    2026-09-16: «сделал одно, пошёл к следующему»; Prove2Me: a proof imports the proved statements). Read-only."""
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    state = "planned" if not _phase_file(case, phase.n, phase.name).exists() else "open"
    out.say(f"phase {phase.n} {phase.name} ({state})", *_item_block(item))
    by_ref = {f"{it.n}.{it.m}": it for it in _all_items(todo)}
    kids = {k.name for k in order.child_cases(case, _is_project(case))}
    for r in item.after:
        pre = by_ref.get(r)
        if pre is None:
            what = "nested case" if r in kids else "gone"
            out.say(f"  ← {r} ({what})" + (f" — its README is the input: el --case {r} status" if r in kids else " — el todo after " + ref + " <refs|none>"))
            continue
        proofs = " · ".join(f"{k} {pr}".strip() for k, pr in pre.evidence) or (pre.result or "")
        mark = "✓" if pre.done else "open"
        out.say(f"  ← {r} {mark} «{order._short(pre.text, 50)}»" + (f" — {proofs}" if proofs else ("" if pre.done else " — nothing to hand over yet")))
    feeds = [f"{it.n}.{it.m}" for it in _all_items(todo) if ref in it.after]
    if feeds:
        out.say(f"  → feeds {', '.join(feeds)}")
    if not item.after and not feeds:
        out.say("  no after-edges: el todo after N.M \"…\" links a chain (el help todo)")
    return out


def todo_expect(case: Path, ref: str, text: str) -> Outcome:
    """`el todo expect N.M "…"` — what done will look like, written BEFORE the work (the owner's word, 2026-09-16:
    «пиши placeholder, куда потом заполнишь»): the proofs it will take stand in brackets, and `done` holds the
    record to them — pre-registration, or Lean's type of a theorem. One per item; "" removes it."""
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    text = " ".join(text.split())
    old = item.expect
    item.expect = _expect_text(text, ref) if text else ""
    out.absorb(_write_todo(case, todo))
    slots = grammar.expected_kinds(item.expect)
    if item.expect:
        named = " · ".join(k for k, _ in slots) or "no proof placeholders — add [file: …] [run: …] [owner] so done can check"
        out.say(f"expect {ref}: «{item.expect}»" + (f" (was: «{old}»)" if old else "") + f" → TODO.md · proofs promised: {named}")
        hints.attach(out, "todo_expect", item=item, phase=phase)
    else:
        out.say(f"expect {ref} removed" + (f" (was: «{old}»)" if old else " — there was none") + " → TODO.md")
    return out


def todo_add(case: Path, ref: str, text: str, before: Optional[str] = None, why: str = "", notes: Optional[List[str]] = None,
             expect: str = "") -> Outcome:
    """Add item N.M (M = next free) to an open or planned phase N; `ref` is the phase number.
    The text may end with `— due: YYYY-MM-DD`. `before` = N.K puts it in place instead of at the
    end (feedback 2026-09-08: an item refused for length and re-added later landed last, and a
    batch of four cost four `move`s — the number is for life, the position is not)."""
    out = Outcome()
    if not ref.isdigit():
        raise StoreError("use `el todo add N \"text\"` — N is the phase number", 2)
    todo = _todo(case, out)
    phase = todo.phase(int(ref))
    if phase is None or phase.done:
        raise StoreError(f"phase {ref} is missing or closed", 4)
    text, due, after = _split_suffixes(text)
    at = len(phase.items)
    if before:
        bm = re.fullmatch(r"(\d+)\.(\d+)", before.strip())
        target = next((it for it in phase.items if it.m == int(bm.group(2))), None) if bm and int(bm.group(1)) == phase.n else None
        if target is None:
            raise StoreError(f"--before {before}: no such item in phase {phase.n} (items: {_number_ranges(phase)}) — "
                             f"drop --before to add at the end", 4)
        at = phase.items.index(target)
    if grammar.visible_len(text) > grammar.TODO_ITEM_CHARS:
        raise StoreError(f"item text is {grammar.visible_len(text)} visible chars, limit {grammar.TODO_ITEM_CHARS} (F13); "
                         f"markdown links count as their name\n"
                         f"  suggestion: \"{_trim_suggestion(text, grammar.TODO_ITEM_CHARS)}\"\n{REPHRASE_HINT}\n"
                         f"  (a re-added item takes the next free number at the END of the list — "
                         f"`el todo add {ref} \"…\" --before {phase.n}.K` puts it in place)", 3)
    m = _next_number(case, todo, phase)
    item = grammar.Item(phase.n, m, False, text, 0, due=due)
    if why:
        item.why = _pocket_text("why", why, f"{phase.n}.{m}")
    item.notes = [_pocket_text("note", n, f"{phase.n}.{m}") for n in (notes or [])]
    if expect:
        item.expect = _expect_text(expect, f"{phase.n}.{m}")
    phase.items.insert(at, item)
    if after:
        _set_after(case, todo, item, after)
    out.absorb(_write_todo(case, todo))
    pockets = (" · why" if item.why else "") + (f" · {len(item.notes)} note(s)" if item.notes else "") + (" · expect" if item.expect else "")
    out.say(f"added: {phase.n}.{m} {text}{f' — after: {chr(44).join(item.after)}' if item.after else ''}{f' — due: {due}' if due else ''}"
            f"{f' (before {before})' if before else ''}{pockets} → TODO.md")
    _remind_link(case, f"{phase.n}.{m}", _item_context(item), out)
    if item.expect:
        hints.attach(out, "todo_expect", item=item, phase=phase)
    else:
        hints.attach(out, "todo_add", item=item)
    return out


def todo_why(case: Path, ref: str, text: str) -> Outcome:
    """`el todo why N.M "…"` — what the item is for, in the owner's words (F22): the line the agent reads
    before going, so it knows what to ask when it gets there (the owner's word, 2026-09-15: went to the
    court, read the item, did not understand why). One per item; "" removes it."""
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    text = " ".join(text.split())
    old = item.why
    item.why = _pocket_text("why", text, ref) if text else ""
    out.absorb(_write_todo(case, todo))
    if item.why:
        out.say(f"why {ref}: «{item.why}»" + (f" (was: «{old}»)" if old else "") + " → TODO.md")
    else:
        out.say(f"why {ref} removed" + (f" (was: «{old}»)" if old else " — there was none") + " → TODO.md")
    _remind_link(case, ref, _item_context(item), out)
    return out


def todo_note(case: Path, ref: str, text: str, edit: Optional[int] = None, drop: Optional[int] = None) -> Outcome:
    """`el todo note N.M "…"` adds a note under the item — a constraint, who to call, what to bring, a link
    to the document (F22); a list `N.M, N.K` puts the same note under several items (a problem seen in one
    environment is expected at the same step of the next ones). `--edit k "…"` rewrites note k in place,
    `--drop k` removes it: every list has add · edit · drop."""
    out = Outcome()
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)
    if drop is not None or edit is not None:
        if len(items) != 1:
            raise StoreError("--edit / --drop work on one item: el todo note N.M --drop k", 2)
        it, k = items[0], (drop if drop is not None else edit)
        if not 1 <= k <= len(it.notes):
            raise StoreError(f"{ref} has {len(it.notes)} note(s) — k is 1..{len(it.notes)}" if it.notes else f"{ref} has no notes", 4)
        if drop is not None:
            gone = it.notes.pop(k - 1)
            out.absorb(_write_todo(case, todo))
            out.say(f"note {k} dropped from {ref}: «{gone}» → TODO.md")
            return out
        new = _pocket_text("note", text, ref)
        old, it.notes[k - 1] = it.notes[k - 1], new
        out.absorb(_write_todo(case, todo))
        out.say(f"note {k} of {ref}: «{new}» (was: «{old}») → TODO.md")
        return out
    text = _pocket_text("note", text, ref)
    for it in items:
        it.notes.append(text)
        if it.done and _note_repeats_proof(text, it.evidence):
            out.warn(f"{phase.n}.{it.m}: this note only points at the item's proof file — a note carries a constraint or context; "
                     f"the proof line already carries the file: el todo note {phase.n}.{it.m} --drop {len(it.notes)}")
    out.absorb(_write_todo(case, todo))
    refs = _refs(phase, items)
    out.say(f"note added under {refs}: «{text}» → TODO.md" + (f" (note {len(items[0].notes)} of {ref})" if len(items) == 1 else ""))
    for it in items:
        _remind_link(case, f"{phase.n}.{it.m}", _item_context(it), out)
    return out


def _remind_link(case: Path, ref: str, text: str, out: Outcome):
    """At the moment of writing, not at the next entry: the rule was forgotten twenty times in one
    session while every item looked fine on its own line (feedback 2026-09-03)."""
    try:
        body = _readme_text(case)
    except StoreError:
        return
    if _items_link_rule(body) and "](" not in text:
        out.warn(f"{ref} has no link to its material — this case's rule: items link their material; "
                 f"el todo edit {ref} \"{text} — [name](docs/file.md)\"")


def _find_item(todo: grammar.Todo, ref: str):
    m = re.fullmatch(r"(\d+)\.(\d+)", ref)
    if not m:
        raise StoreError(f"`{ref}` — use N.M, e.g. 2.3", 2)
    phase = todo.phase(int(m.group(1)))
    item = next((it for it in phase.items if it.m == int(m.group(2))), None) if phase else None
    if item is None:
        raise StoreError(f"no item {ref} in TODO.md", 4)
    if phase.done:
        raise StoreError(f"phase {phase.n} is closed — its items live in the phase file now", 4)
    return phase, item


def _select_items(todo: grammar.Todo, ref: str):
    """`N.M` · a range `N.A-N.B` (or `N.A-B`) · a list `N.A, N.B, …` → (phase, items in list order),
    one phase per call. A range takes the items that exist between A and B — numbers have gaps.
    Feedback 2026-09-09: rolling back a Pre-flight block meant six identical shell calls."""
    ref = ref.strip()
    m = re.fullmatch(r"(\d+)\.(\d+)\s*[-–]\s*(?:(\d+)\.)?(\d+)", ref)
    if m:
        n, a, n2, b = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
        if n2 is not None and int(n2) != n:
            raise StoreError(f"a range stays inside one phase: `{n}.{a}-{n}.{b}`, not `{ref}`", 2)
        phase = todo.phase(n)
        if phase is None:
            raise StoreError(f"no phase {n} in TODO.md", 4)
        if phase.done:
            raise StoreError(f"phase {n} is closed — its items live in the phase file now", 4)
        items = [it for it in phase.items if a <= it.m <= b]
        if not items:
            raise StoreError(f"no items {n}.{a}–{n}.{b} in phase {n} (items: {_number_ranges(phase)})", 4)
        return phase, items
    if "," in ref:
        pairs = [_find_item(todo, r.strip()) for r in ref.split(",") if r.strip()]
        if len({p.n for p, _ in pairs}) > 1:
            raise StoreError("one phase per call: `el todo done 3.1, 3.4, 3.5` — items of another phase go in a second call", 2)
        seen, items = set(), []
        for _, it in pairs:
            if it.m not in seen:
                seen.add(it.m)
                items.append(it)
        return pairs[0][0], items
    phase, item = _find_item(todo, ref)
    return phase, [item]


def _refs(phase: grammar.Phase, items) -> str:
    return ", ".join(f"{phase.n}.{it.m}" for it in items)


def todo_edit(case: Path, ref: str, text: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    text, due, after = _split_suffixes(text)  # a date or dependency kept in the item stays unless the new text carries one
    if after:
        _set_after(case, todo, item, after)
    if grammar.visible_len(text) > grammar.TODO_ITEM_CHARS:
        raise StoreError(f"item text is {grammar.visible_len(text)} visible chars, limit {grammar.TODO_ITEM_CHARS} (F13)\n"
                         f"  suggestion: \"{_trim_suggestion(text, grammar.TODO_ITEM_CHARS)}\"\n{REPHRASE_HINT}", 3)
    old_text, item.text = item.text, text
    if due:
        item.due = due
    out.absorb(_write_todo(case, todo))
    out.say(f"edited: {ref} → «{item.text}» (was: «{old_text}») → TODO.md")  # the new text is shown: an edit aimed at the wrong number is seen at once (feedback 2026-09-08)
    _remind_link(case, ref, _item_context(item), out)
    return out


def _list_lines(phase: grammar.Phase) -> List[str]:
    """The phase as TODO renders it — active items in order, held ones last."""
    items = [i for i in phase.items if not i.held] + [i for i in phase.items if i.held]
    return [ln for it in items for ln in _item_block(it)]


def _number_ranges(phase: grammar.Phase) -> str:
    """`2.1–2.6, 2.8, 2.17` — which numbers the phase holds now (gaps are normal: numbers are kept)."""
    ms = sorted(it.m for it in phase.items)
    parts, i = [], 0
    while i < len(ms):
        j = i
        while j + 1 < len(ms) and ms[j + 1] == ms[j] + 1:
            j += 1
        parts.append(f"{phase.n}.{ms[i]}" if i == j else f"{phase.n}.{ms[i]}–{phase.n}.{ms[j]}")
        i = j + 1
    return ", ".join(parts) or "(empty)"


def todo_move(case: Path, ref: str, to: str) -> Outcome:
    """Put item N.M before item N.K, or `last`. Numbers never change: N.M is the item's number for
    life and the list order is a separate thing, so a batch aimed at numbers read a moment ago stays
    correct (feedback 2026-09-03: move renumbered while drop did not — two rules for one list, and
    an edit landed on the wrong item). No clamping either: an unknown target is refused."""
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    if to.strip().isdigit():
        # to another phase: the item joins its end under the next free number there — the one time a
        # number changes, said aloud (feedback 2026-09-03: re-cutting a phase meant drop + add × 15)
        dest = todo.phase(int(to))
        if dest is None or dest.done:
            raise StoreError(f"phase {to} is missing or closed — plan it first: el phase plan {to} \"Name\"", 4)
        if dest is phase:
            out.say(f"{ref} is already in phase {to} — nothing changed")
            return out
        phase.items.remove(item)
        item.n, item.m = dest.n, _next_number(case, todo, dest)
        dest.items.append(item)
        new = f"{item.n}.{item.m}"
        followers = []
        for it in _all_items(todo):  # references follow the item, like links follow a moved file (F19)
            if ref in it.after:
                it.after = [new if r == ref else r for r in it.after]
                followers.append(f"{it.n}.{it.m}")
        out.absorb(_write_todo(case, todo))
        out.say(f"moved: {ref} → {new} «{item.text}» (end of phase {dest.n}; the number changes with the phase)"
                + (f" · after-references rewritten in {', '.join(followers)}" if followers else ""))
        return out
    if to.strip().lower() in ("last", "end"):
        target = None
    else:
        m = re.fullmatch(r"(\d+)\.(\d+)", to)
        if not m or int(m.group(1)) != phase.n:
            raise StoreError(f"move works inside one phase: `el todo move {phase.n}.M {phase.n}.K` (before K) "
                             f"or `el todo move {phase.n}.M last`; to another phase — drop and add", 2)
        target = next((it for it in phase.items if it.m == int(m.group(2))), None)
        if target is None:
            raise StoreError(f"no item {to} in phase {phase.n} (items: {_number_ranges(phase)}); "
                             f"to put it last: el todo move {ref} last", 4)
        if target is item:
            out.say(f"{ref} is already there — nothing changed")
            return out
    phase.items.remove(item)
    phase.items.insert(len(phase.items) if target is None else phase.items.index(target), item)
    out.absorb(_write_todo(case, todo))
    where = "last" if target is None else f"before {phase.n}.{target.m}"
    out.say(f"moved: {ref} now {where} — numbers never change; the phase list:", *_list_lines(phase))
    return out


def todo_hold(case: Path, ref: str, reason: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    if item.done:
        raise StoreError(f"item {ref} is done — nothing to hold", 4)
    item.held, item.hold_reason = True, " ".join(reason.split())
    out.absorb(_write_todo(case, todo))
    out.say(f"on hold: {ref} (held items sit at the end of the phase; `el todo resume {ref}` brings it back)")
    return out


def todo_reopen(case: Path, ref: str, why: str) -> Outcome:
    """A tick taken back with a reason (feedback 2026-09-09: a database drift found at 22.2 sent
    22.1–22.6 back to open; `resume` only lifts a hold, so the agent edited the file and met the
    stamp). The RESULT logged at `done` stays — it is history — and a DECISION says it no longer
    holds. The item is open again: the phase cannot close over it, its dependents are blocked again."""
    out = Outcome()
    why = " ".join(why.split())
    if not why:
        raise StoreError(f"reopen needs the reason: el todo reopen {ref} \"why the result no longer holds\"", 2)
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)  # a closed phase refuses: its items live in the phase file
    open_ = [it for it in items if not it.done]
    items = [it for it in items if it.done]
    if open_:
        out.say(f"open already, nothing changed: {_refs(phase, open_)}"
                + (" (on hold — el todo resume)" if any(it.held for it in open_) else ""))
    if not items:
        return out
    for it in items:
        it.done, it.result, it.evidence = False, "", []  # the result and its proofs go with the tick; why/notes stay; the RESULT stays in the journal
    out.absorb(_write_todo(case, todo))
    refs = _refs(phase, items)
    verb = "возвращён" if len(items) == 1 else "возвращены"
    out.lines += log(case, "DECISION", f"{refs} {verb} в работу — {why}", f"p{phase.n}").lines
    what = f"{items[0].text}" if len(items) == 1 else f"({len(items)} items)"
    out.say(f"reopened: {refs} {what} → TODO.md · DECISION in the journal (the RESULTs stay as history)")
    return out


def todo_resume(case: Path, ref: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    if not item.held:
        out.say(f"item {ref} is not on hold — nothing changed")
        return out
    item.held, item.hold_reason = False, ""
    out.absorb(_write_todo(case, todo))
    out.say(f"resumed: {ref} {item.text} → TODO.md")
    return out


def todo_drop(case: Path, ref: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    ref_by = [f"{it.n}.{it.m}" for it in _all_items(todo) if ref in it.after]
    if ref_by:  # F19: an item others wait for does not vanish silently
        raise StoreError(f"{ref} is a dependency of {', '.join(ref_by)} — rewire them first (el todo after N.M <refs|none>) "
                         f"or cancel {ref} with a reason (el todo cancel {ref} \"why\")", 4)
    phase.items.remove(item)
    out.absorb(_write_todo(case, todo))
    # the numbers of the others are kept (N.M is for life) — and said aloud, so the next command in a
    # batch is aimed at a number the caller has just been shown (feedback 2026-09-03)
    out.say(f"dropped: {ref} «{item.text}» — numbers kept, phase {phase.n} now reads {_number_ranges(phase)} "
            f"(git keeps the history; a decision behind it → el log DECISION)")
    return out


def todo_cancel(case: Path, ref: str, why: str) -> Outcome:
    """The item stopped being needed (not done, not dropped by mistake): it leaves TODO — the list is
    what remains to do (P4) — and the reason goes to the journal as a DECISION, so the record stays
    honest (feedback 2026-09-03: `edit` + `done` wrote "completed" over work that was cancelled)."""
    out = Outcome()
    why = " ".join(why.split())
    if not why:
        raise StoreError("cancel needs a reason: `el todo cancel N.M \"why it is no longer needed\"`", 2)
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)
    for it in items:
        phase.items.remove(it)
    out.absorb(_write_todo(case, todo))
    named = ", ".join(f"{phase.n}.{it.m} «{it.text}»" for it in items)
    out.lines += log(case, "DECISION", f"снято {named} — {why}", f"p{phase.n}").lines
    out.say(f"cancelled: {named} — out of TODO, the reason is in the journal; phase {phase.n} now reads {_number_ranges(phase)}")
    return out


def todo_due(case: Path, ref: str, date: str) -> Outcome:
    """Set or clear (`none`) the date of an item: `— due: YYYY-MM-DD` — the tool counts it on entry."""
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    date = date.strip().lower()
    if date in ("", "none", "-", "clear"):
        item.due = ""
        out.absorb(_write_todo(case, todo))
        out.say(f"due cleared: {ref} {item.text}")
        return out
    item.due = _valid_date(date)
    out.absorb(_write_todo(case, todo))
    out.say(f"due: {ref} {item.text} — {item.due} → TODO.md")
    return out


# ---- phases -------------------------------------------------------------------------------------
def _phase_file(case: Path, n: int, name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return case / "phases" / f"{n}-{slug}.md"


# Phases are the stages of ONE pipeline: in order, one in flight (P8). Work that runs alongside on its
# own clock is a nested case (P11) — its own phases, its own agent, one rendered line at the parent.
# Said at the moment the model is stretched (feedback 2026-09-14: a 2024 matter was planned as phase 4,
# ran next to phase 1 and finished first — open refused, close refused, cancel a lie).
ALONGSIDE_HINT = ("phases are one pipeline, in order, one in flight; work that runs alongside on its own clock is a "
                  "nested case: el spawn \"name\" --goal \"…\" (P11) — its own phases, one line at the parent when it closes")


def _closing_checks(case: Path, prev: grammar.Phase, journal: grammar.Journal) -> List[str]:
    """What P8 demands from a phase before the next one may open."""
    missing = []
    if (prev.summary or "").startswith("снято"):
        return []  # cancelled (F20): the phase never ran — no RESULT, reflect or align to ask for (feedback 2026-09-09)
    pf0 = _phase_file(case, prev.n, prev.name)
    if pf0.exists():
        parsed0 = grammar.parse_phase_file(pf0.read_text(encoding="utf-8"))
        if not parsed0.errors and parsed0.goal.startswith("migrated from legacy"):
            return []  # closed by `el migrate`: its RESULT/reflect/align live in the legacy archive
    evs = _events_for_phase(journal, f"p{prev.n}")
    # each gate names its command under `--phase N`: a phase that ends out of turn is not the current
    # one, and a bare `el log` would file its reflect/align under the wrong phase (feedback 2026-09-14)
    if not any(ev.type == "RESULT" for ev in evs):
        missing.append(f"phase {prev.n}: no RESULT in the journal (F9) → el log --phase {prev.n} RESULT \"what came out\"")
    if not any(ev.text.startswith("reflect:") for ev in evs):
        missing.append(f"phase {prev.n}: no `DECISION · reflect: …` (P8) → el log --phase {prev.n} DECISION \"reflect: …\" "
                       f"· or close with it: el phase close {prev.n} \"…\" --reflect \"the lesson\" --align \"what changes next\"")
    if not any(ev.text.startswith("align:") for ev in evs):
        missing.append(f"phase {prev.n}: no `DECISION · align: …` (P8) → el log --phase {prev.n} DECISION \"align: …\" "
                       f"· or: el phase close {prev.n} \"…\" --align \"what changes in the next plan\"")
    pf = _phase_file(case, prev.n, prev.name)
    if not pf.exists():
        missing.append(f"phase {prev.n}: {pf.relative_to(case)} is missing (F12)")
    else:
        parsed = grammar.parse_phase_file(pf.read_text(encoding="utf-8"))
        if not parsed.result:
            missing.append(f"phase {prev.n}: `result:` is empty in {pf.relative_to(case)} (F12)")
    if prev.waits:
        missing.append(f"phase {prev.n}: still waits for {', '.join(prev.waits)}")
    return missing


def phase_plan(case: Path, n: int, name: str, goal: Optional[str]) -> Outcome:
    """Name the next phase now, open it later: `- [ ] N Name — <intent>` in TODO, no phase file, no
    journal event (a plan is not an event, P5). Items may be parked under it (`todo add N`); it
    opens with `el phase open N` once the previous phase is closed — P8 stays: planned ≠ open.
    Feedback 2026-09-03: a dated deadline outside the current phase had nowhere to live in TODO."""
    out = Outcome()
    if not grammar.PHASE_NAME_RE.match(name):
        raise StoreError(f"phase name `{name}` must be English, 1–3 words (F13)", 2)
    todo = _todo(case, out)
    existing = todo.phase(n)
    intent = _goal_text(goal) if goal else None
    if intent and grammar.visible_len(intent) > grammar.TODO_ITEM_CHARS:
        raise StoreError(f"intent is {grammar.visible_len(intent)} visible chars, limit {grammar.TODO_ITEM_CHARS} — one line in TODO (F13); "
                         f"the story goes into the phase file once it opens\n"
                         f"  suggestion: \"{_trim_suggestion(intent, grammar.TODO_ITEM_CHARS)}\"", 3)
    if existing is not None:
        free = max(p.n for p in todo.phases) + 1
        if existing.done and (existing.summary or "").startswith("снято"):
            return _replan_cancelled(case, todo, existing, name, intent, free, out)
        if existing.done:
            raise StoreError(f"phase {n} {existing.name} is closed — pick the next number: el phase plan {free} \"{name}\"", 4)
        pf = _phase_file(case, n, existing.name)
        if pf.exists():
            raise StoreError(f"phase {n} {existing.name} is open — its goal lives in {pf.relative_to(case)} (line `goal:`): "
                             f"edit it there, the TODO line follows (F18); a new phase: el phase plan {free} \"{name}\"", 4)
        # planned, not open: a plan is rough when made and sharpens until it opens — the same command
        # re-plans it (feedback 2026-09-08: a goal with a hole in it was frozen by «already planned»)
        changes = []
        if name != existing.name:
            changes.append(f"name {existing.name} → {name}")
            existing.name = name
        if intent is not None and intent != existing.summary:
            changes.append("goal")
            existing.summary = intent
        if not changes:
            out.say(f"phase {n} {name} is already planned with this goal — nothing changed")
            return out
        out.absorb(_write_todo(case, todo))
        _sync_progress(case, todo, out)
        out.say(f"re-planned: phase {n} {name} — {existing.summary or '(no goal)'} ({', '.join(changes)}) → TODO.md")
        return out
    todo.phases.append(grammar.Phase(n, name, False, 0, intent))
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    out.say(f"planned: phase {n} {name} → TODO.md (no phase file until it opens) · items now: el todo add {n} \"…\" · "
            f"open once the previous phase is closed: el phase open {n}")
    return out


def _replan_cancelled(case: Path, todo: grammar.Todo, phase: grammar.Phase, name: str, intent: Optional[str],
                      free: int, out: Outcome) -> Outcome:
    """A phase cancelled while still planned comes back as a plan (feedback 2026-09-09: phase 26 was
    cancelled to fit the old 100-line TODO; with 200 the plan is wanted again). Its items return
    from `## Items at cancel` under their old numbers; the born-closed file goes (it held nothing but
    the header and that list). A phase that RAN before it was cancelled has a story in its file and
    PHASE events in the journal — that is not a plan any more: it gets a new number."""
    n = phase.n
    journal = _journal(case, out)
    if any(ev.type == "PHASE" and "открыта" in ev.text for ev in _events_for_phase(journal, f"p{n}")):
        raise StoreError(f"phase {n} {phase.name} ran before it was cancelled — its file and journal hold its story; "
                         f"plan the work again under the next number: el phase plan {free} \"{name}\"", 4)
    pf = _phase_file(case, n, phase.name)
    old_goal, items, extra, phase_notes = "", [], [], []
    if pf.exists():
        lines = pf.read_text(encoding="utf-8").split("\n")
        section = ""
        for ln in lines[3:]:
            if ln.startswith("## "):
                section = ln[3:].strip()
                continue
            if not ln.strip():
                continue
            m = re.fullmatch(rf"- {n}\.(\d+) [✓✗] (.*)", ln)
            pocket = re.fullmatch(r"  - (why|note|expect): (.+)", ln)
            if section == "Items at cancel" and m:
                text, _ = _rewrite_links(m.group(2), pf.parent, new_base=case)  # links come back up to the case root
                text, _, _ = grammar.split_evidence(text)  # an item comes back open: its evidence, if any, stays in the journal
                items.append(grammar.Item(n, int(m.group(1)), False, text, 0))
            elif section == "Items at cancel" and items and pocket:  # F22: the pockets come back with their item
                val, _ = _rewrite_links(pocket.group(2), pf.parent, new_base=case)
                if pocket.group(1) == "why":
                    items[-1].why = val
                elif pocket.group(1) == "expect":
                    items[-1].expect = val
                else:
                    items[-1].notes.append(val)
            elif section == "Items at cancel" and items and re.fullmatch(r"\s+- (file|ref|run|owner)\b.*", ln):
                continue  # evidence of a done item: the item comes back open, the RESULT stays in the journal
            elif section == "Notes at cancel" and ln.startswith("- note: "):
                phase_notes.append(_rewrite_links(ln[len("- note: "):], pf.parent, new_base=case)[0])
            else:
                extra.append(ln)
        if extra:
            raise StoreError(f"{pf.relative_to(case)} holds more than the header and the cancelled items — "
                             f"not a born-closed file; plan the work under the next number: el phase plan {free} \"{name}\"", 4)
        parsed = grammar.parse_phase_file("\n".join(lines))
        old_goal = "" if parsed.errors or parsed.goal == "—" else parsed.goal
    was = phase.summary or ""
    phase.done, phase.name, phase.items, phase.notes = False, name, items, phase_notes
    phase.summary = intent if intent is not None else (old_goal or None)
    if pf.exists():
        pf.unlink()  # born closed at cancel, nothing of its own inside (checked above)
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    out.lines = log(case, "DECISION", f"фаза {n} {name} возвращена в план ({was.split(' · ')[0]})", f"p{n}").lines + out.lines
    out.say(f"re-planned: phase {n} {name} — {phase.summary or '(no goal)'} → TODO.md (was cancelled)"
            + (f" · items back: {_refs(phase, items)}" if items else "") + f" · open it later: el phase open {n}")
    return out


def phase_note(case: Path, n: int, text: str, edit: Optional[int] = None, drop: Optional[int] = None) -> Outcome:
    """`el phase note N "…"` — what the phase has to know before and while it runs (F22): a permit that
    expires, a service to call, a problem seen one stage earlier. Parked under a planned phase it waits in
    TODO under the phase line and travels into the phase file at close. `--edit k` · `--drop k`."""
    out = Outcome()
    todo = _todo(case, out)
    phase = todo.phase(n)
    if phase is None:
        raise StoreError(f"no phase {n} in TODO.md — plan it first: el phase plan {n} \"Name\" --goal \"…\"", 4)
    if phase.done:
        raise StoreError(f"phase {n} {phase.name} is closed — its notes live in its file: phases/{_phase_file(case, n, phase.name).name}", 4)
    k = drop if drop is not None else edit
    if k is not None:
        if not 1 <= k <= len(phase.notes):
            raise StoreError(f"phase {n} has {len(phase.notes)} note(s) — k is 1..{len(phase.notes)}" if phase.notes else f"phase {n} has no notes", 4)
        if drop is not None:
            gone = phase.notes.pop(k - 1)
            out.absorb(_write_todo(case, todo))
            out.say(f"note {k} dropped from phase {n}: «{gone}» → TODO.md")
            return out
        new = _pocket_text("note", text, str(n))
        old, phase.notes[k - 1] = phase.notes[k - 1], new
        out.absorb(_write_todo(case, todo))
        out.say(f"note {k} of phase {n}: «{new}» (was: «{old}») → TODO.md")
        return out
    text = _pocket_text("note", text, str(n))
    phase.notes.append(text)
    out.absorb(_write_todo(case, todo))
    state = "open" if _phase_file(case, n, phase.name).exists() else "planned"
    out.say(f"note {len(phase.notes)} under phase {n} {phase.name} ({state}): «{text}» → TODO.md"
            + (" — it waits there until the phase runs and moves into the phase file at close" if state == "planned" else ""))
    return out


def _parked_events(journal: grammar.Journal, n: int) -> List[grammar.Event]:
    """Journal events logged against phase N (`el log --phase N …`) — parked knowledge for a phase that
    has not opened yet: a decision made early, a problem expected here (the owner's word, 2026-09-15)."""
    return _events_for_phase(journal, f"p{n}")


def _parked_line(case: Path, todo: grammar.Todo, journal: Optional[grammar.Journal]) -> Optional[str]:
    """`parked: phase 5 Roof — 1 item · 2 notes · 1 journal event` for every planned phase that already holds
    something: parked knowledge has a moment of return (the phase opens) and is counted until then."""
    parts = []
    for p in sorted(todo.phases, key=lambda x: x.n):
        if p.done or _phase_file(case, p.n, p.name).exists():
            continue
        evs = _parked_events(journal, p.n) if journal is not None else []
        bits = ([f"{len(p.items)} item(s)"] if p.items else []) + ([f"{len(p.notes)} note(s)"] if p.notes else []) \
            + ([f"{len(evs)} journal event(s)"] if evs else [])
        if bits:
            parts.append(f"phase {p.n} {p.name} — {' · '.join(bits)}")
    return ("parked: " + " · ".join(parts) + " (surfaces when the phase opens)") if parts else None


def phase_open(case: Path, n: int, name: str, goal: Optional[str]) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    existing = todo.phase(n)
    if not name and existing is not None and not existing.done:
        name = existing.name  # `el phase open N` opens the planned phase under its planned name
    if not name:
        raise StoreError(f"phase open needs a name: `el phase open {n} \"CLI core\" --goal …` — no planned phase {n} to take it from", 2)
    if not grammar.PHASE_NAME_RE.match(name):
        raise StoreError(f"phase name `{name}` must be English, 1–3 words (F13)", 2)
    if existing and existing.done:
        raise StoreError(f"phase {n} is already closed", 4)
    pf = _phase_file(case, n, existing.name if existing else name)
    if existing and not existing.done and pf.exists():
        out.say(f"phase {n} {existing.name} is already open — nothing changed")
        return out
    prev = max((p for p in todo.phases if p.n < n), key=lambda p: p.n, default=None)
    if prev is not None:
        journal = _journal(case, out)
        if prev.done:
            missing = _closing_checks(case, prev, journal)
        elif _phase_file(case, prev.n, prev.name).exists():
            missing = [f"phase {prev.n} {prev.name} is still open — close it first (P8): el phase close {prev.n} \"…\" "
                       f"· or cancel it: el phase cancel {prev.n} \"why\"", ALONGSIDE_HINT]
        else:  # planned, never opened: phases run in order — the plan below has to open or go
            missing = [f"phase {prev.n} {prev.name} is planned and not opened — phases run in order: "
                       f"el phase open {prev.n} · or, if it is not needed: el phase cancel {prev.n} \"why\"", ALONGSIDE_HINT]
        if missing:
            raise StoreError("cannot open phase %d:\n  " % n + "\n  ".join(missing), 4)
    renamed = None
    if existing is not None and not pf.exists() and name != existing.name:
        # a planned phase may be re-planned at opening (P8 align): the name follows the owner's word
        renamed, existing.name = existing.name, name
        pf = _phase_file(case, n, name)
    if not pf.exists():
        goal = _goal_text(goal) if goal else (existing.summary if existing else None)  # a planned phase carries its intent
        if not goal:
            raise StoreError("a new phase needs `--goal \"one line\"` (F12)", 2)
        pf.parent.mkdir(exist_ok=True)
        parked = _parked_events(_journal(case, out), n)  # what was said about this phase before it opened
        before = ""
        if parked:
            before = "\n## Before opening\n" + "\n".join(
                f"- {ev.type} · {_rewrite_links(ev.text, case, new_base=pf.parent)[0]}" for ev in parked) + "\n"
        pf.write_text(f"# Phase {n} — {name}\ngoal: {' '.join(goal.split())}\nresult:\n{before}\n## Notes\n", encoding="utf-8")
        out.say(f"created: {pf.relative_to(case)}" + (f" — {len(parked)} journal event(s) parked here before opening are in it" if parked else ""))
        if existing is not None and existing.notes:
            out.say(f"phase {n} carries {len(existing.notes)} note(s) in TODO — read them; they move into the phase file at close")
    if existing is None:
        todo.phases.append(grammar.Phase(n, name, False, 0))
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    opened = f"{name} открыта" + (f" (запланирована была как «{renamed}»)" if renamed else "")
    out.lines = log(case, "PHASE", opened, f"p{n}").lines + out.lines
    out.say(f"phase {n} {name} is open → TODO.md, README.md State")
    hints.attach(out, "phase_open", rel=f"phases/{pf.name}", n=n,
                 promised=[_slot(k, w) for k, w in grammar.expected_kinds(_phase_goal(case, todo.phase(n)))],
                 covered=[_slot(k, w) for (k, w), st, _ in _goal_coverage(todo.phase(n), _phase_goal(case, todo.phase(n))) if st != "uncovered"])
    return out


def phase_close(case: Path, n: int, summary: str, reflect: Optional[str] = None, align: Optional[str] = None) -> Outcome:
    """Close a phase. `--reflect "…"` and `--align "…"` log the two DECISION events P8 asks for in the same
    command (feedback 2026-09-16: three shell round trips for one close added friction, not rigour) — the
    record is identical, the gates are the same, and nothing is logged if another gate refuses the close."""
    out = Outcome()
    todo = _todo(case, out)
    phase = todo.phase(n)
    if phase is None:
        raise StoreError(f"no phase {n} in TODO.md", 4)
    if phase.done:
        out.say(f"phase {n} {phase.name} is already closed — nothing changed")
        return out
    pf = _phase_file(case, n, phase.name)
    open_items = [f"{it.n}.{it.m}" for it in phase.items if not it.done]
    alongside = None  # (the earlier phase, its state) when this planned phase ended out of turn
    if not pf.exists():
        prev = max((p for p in todo.phases if p.n < n), key=lambda p: p.n, default=None)
        if prev is None or prev.done:
            # planned, never opened, and it COULD open: the pipeline is intact, so walk it (feedback
            # 2026-09-09: `close` died with «phases/22-….md is missing (F12)» and the agent wrote the file
            # by hand). Opening is the one place the gates on the previous phase run and PHASE is logged.
            raise StoreError(f"phase {n} {phase.name} was planned and never opened — nothing to close yet: "
                             f"el phase open {n} (creates phases/{pf.name} from the plan), "
                             f"then el phase close {n} \"…\"", 4)
        # out of turn: an earlier phase is not done, so `open` is refused (phases run in order) — yet the
        # work parked under this plan may have ended already: it ran alongside (feedback 2026-09-14:
        # phase 4 ran next to phase 1 and finished first; open refused, cancel would call finished work
        # «not needed», so the branch had no honest end). A finished branch closes from the plan.
        state = "open" if _phase_file(case, prev.n, prev.name).exists() else "planned"
        if not phase.items or open_items:
            what = f"open items {', '.join(open_items)}" if open_items else "no items"
            raise StoreError(f"phase {n} {phase.name} is planned and out of turn (phase {prev.n} {prev.name} is still {state}) — "
                             f"it closes from the plan once every item ended, and it has {what}: "
                             f"el todo done N.M <kind> \"what came out\" · el todo cancel N.M \"why\" · not needed at all: "
                             f"el phase cancel {n} \"why\"\n  {ALONGSIDE_HINT}", 4)
        cur = todo.current()  # the phase in flight, if any — that is what this one ran alongside
        running = cur if cur is not None and cur.n != n and _phase_file(case, cur.n, cur.name).exists() else None
        alongside = (prev, state, running)
    journal = _journal(case, out)
    reflect = " ".join((reflect or "").split())
    align = " ".join((align or "").split())
    for tag, val in (("reflect", reflect), ("align", align)):
        if val.lower().startswith(f"{tag}:"):
            raise StoreError(f"--{tag} takes the words only, el writes the `{tag}:` prefix: --{tag} \"{val[len(tag) + 1:].strip()}\"", 2)
    def gates(j: grammar.Journal) -> List[str]:
        found = [m for m in _closing_checks(case, phase, j) if "result:" not in m and not (alongside and "is missing (F12)" in m)]
        # a flag stands in for the event it is about to log — everything else must already hold
        return [m for m in found if not (reflect and "reflect:" in m) and not (align and "align:" in m)]
    missing = gates(journal)
    goal_now = _phase_goal(case, phase)
    for (kind, what), status, ref in _goal_coverage(phase, goal_now):  # F12: the phase's own promise holds its close
        if status == "proved":
            continue
        where = (f"the goal line in phases/{pf.name}" if pf.exists() else f"el phase plan {n} \"{phase.name}\" --goal \"…\"")
        if status == "promised":
            missing.append(f"phase {n} promised {_slot(kind, what)} — {ref} promises it and is not proved with a {kind}: "
                           f"el todo done {ref} {kind}:… \"…\" · or correct the promise: {where}")
        else:
            missing.append(f"phase {n} promised {_slot(kind, what)} and no done item proves it — name the criterion as an item: "
                           f"el todo add {n} \"…\" --expect \"{_slot(kind, what)}\" and prove it · or correct the promise: {where}")
    if open_items:  # F20: a phase closes only when every item ended — done with evidence, or cancelled with a reason
        missing.append(f"phase {n}: open items {', '.join(open_items)} — each must end one of two ways: "
                       f"el todo done N.M <kind> \"what came out\" · el todo cancel N.M \"why\" (or cancel the phase: el phase cancel {n} \"why\")")
    if missing:
        raise StoreError("cannot close phase %d:\n  " % n + "\n  ".join(missing), 4)
    for tag, val in (("reflect", reflect), ("align", align)):
        if val:  # every other gate held: the two events are written now, then the close proceeds on them
            out.lines += log(case, "DECISION", f"{tag}: {val}", f"p{n}").lines
    if reflect or align:
        journal = _journal(case, out)
    summary = " ".join(summary.split())
    date, _ = _now()
    evs_here = _events_for_phase(journal, f"p{n}")
    for tag in ("reflect", "align"):  # a result dressed as a lesson (the owner's eye, 2026-09-16)
        for ev in evs_here:
            if ev.type != "DECISION" or not ev.text.startswith(f"{tag}:"):
                continue
            for res in (r for r in evs_here if r.type == "RESULT"):
                share = _verbatim_share(ev.text[len(tag) + 1:], res.text)
                if share >= order.DUP_SHARE:
                    out.warn(f"{tag}: repeats RESULT · {order._short(res.text, 60)} ({int(share * 100)} % verbatim) — "
                             f"{'reflect is a lesson about how you worked' if tag == 'reflect' else 'align is what changes in the next plan'}, "
                             f"not the result again (el help practice)")
                    break
    if alongside:  # every gate passed — only now is the file born (a refused close writes nothing)
        pf.parent.mkdir(exist_ok=True)
        pf.write_text(f"# Phase {n} — {phase.name}\ngoal: {phase.summary or '—'}\nresult:\n\n## Notes\n", encoding="utf-8")
        out.say(f"created: {pf.relative_to(case)} (from the plan)")
    text = pf.read_text(encoding="utf-8").split("\n")
    text[2] = f"result: {summary}"
    goal_line = grammar.parse_phase_file("\n".join(text)).goal
    text = text[:3] + ["", "## Digest", *_digest(case, pf, phase, evs_here, goal_line)] + text[3:]
    if phase.items:
        text.append("")
        text.append("## Items at close")
        for it in phase.items:
            text.extend(_item_block_for_phase_file(case, pf, it))
    pf.write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(text)).rstrip("\n") + "\n", encoding="utf-8")
    rel = f"phases/{pf.name}"
    phase.done, phase.items, phase.notes = True, [], []
    phase.summary = f"{summary} · {date} · {_phase_link(pf.name)}" if rel not in summary else summary
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    ran = ""
    if alongside:  # the journal names the phase that was running; nothing in flight = closed before its turn
        ran = (f" (шла параллельно фазе {alongside[2].n}, без открытия)" if alongside[2]
               else " (закрыта до своей очереди, без открытия)")
    out.lines = log(case, "PHASE", f"{phase.name} закрыта{ran} → {summary}", f"p{n}").lines + out.lines
    out.say(f"closed: phase {n} {phase.name} → TODO.md (collapsed), {rel} (result), README.md State")
    hints.attach(out, "phase_close", n=n, events=evs_here)
    if alongside:
        out.say(f"closed from the plan, out of turn — phase {alongside[0].n} {alongside[0].name} is still {alongside[1]}, "
                f"the pipeline stays in order. {ALONGSIDE_HINT}")
    return out


def _item_block_for_phase_file(case: Path, pf: Path, it: grammar.Item) -> List[str]:
    """An item copied from TODO into the phase file — its line and its pockets (F22) — keeps pointing at the
    same files: TODO lives in the case root, the phase file in phases/, so every relative link is re-based
    (`docs/x.md` → `../docs/x.md`). Feedback 2026-09-08: verbatim copies left `el check` with broken links."""
    block = _item_block(it)
    prefix = f"  - [{'x' if it.done else ('~' if it.held else ' ')}] {it.n}.{it.m} "
    rest = block[0][len(prefix):] if block[0].startswith(prefix) else it.text  # `  - [x] N.M text…` → `- N.M ✓ text…`
    lines = [f"- {it.n}.{it.m} {'✓' if it.done else '✗'} {rest}".rstrip()]
    lines += [ln[2:] for ln in block[1:]]  # pockets one level up: the item is the bullet here
    return [_rewrite_links(ln, case, new_base=pf.parent)[0] for ln in lines]


ITEM_RESULT_RE = re.compile(r"^\d+\.\d+(?:[,\s–-]+\d+\.\d+)*:")  # `RESULT · 2.1: …` · `2.1, 2.3: …` · `2.1-2.4: …`


def _verbatim_share(a: str, b: str) -> float:
    """Share of a's word 3-grams found verbatim in b (the duplicate detector of F15, on two texts)."""
    return order.text_share(a, b)


def _digest(case: Path, pf: Path, phase: grammar.Phase, evs: List[grammar.Event], goal: str = "") -> List[str]:
    """The `## Digest` of a closed phase — rendered, never typed (the owner's word, 2026-09-15: «клацаешь на
    ссылку, а там список; хочется выжимку»): what the phase held (items, notes), what came out (RESULT),
    what bit and what was decided (PROBLEM, DECISION), reflect and align — all from the journal events of
    this phase and its items. Poor journal, poor digest: it shows the record as it is."""
    def rel(text: str) -> str:
        return _rewrite_links(order._short(text, 160), case, new_base=pf.parent)[0]

    def bucket(label: str, texts: List[str]) -> List[str]:
        return [f"- {label} ({len(texts)}):", *(f"  - {t}" for t in texts)] if texts else []

    done_n = sum(1 for it in phase.items if it.done)
    head = f"- items: {done_n} done" + (f" · {len(phase.items) - done_n} open" if len(phase.items) > done_n else "")
    proofs = [pr for it in phase.items if it.done for _, pr in it.evidence]
    distinct = len(set(proofs))
    if proofs and distinct < done_n:  # the owner's eye, 2026-09-16: four items, one self-written file eight times
        shared = max(set(proofs), key=proofs.count)
        head += f" · proofs: {distinct} distinct for {done_n} items ({rel(shared)} ×{proofs.count(shared)})"
    lines = [head]
    coverage = _goal_coverage(phase, goal)
    if coverage:  # the phase's own promise (its goal), decomposed into its items and their proofs
        proved = [(sl, ref) for sl, st, ref in coverage if st == "proved"]
        lines.append(f"- phase promise: {len(proved)} of {len(coverage)} proved"
                     + (" — " + " · ".join(f"{_slot(*sl)} by {ref}" if ref else _slot(*sl) for sl, ref in proved) if proved else "")
                     + (" — not proved: " + " ".join(_slot(*sl) for sl, st, _ in coverage if st != "proved") if len(proved) < len(coverage) else ""))
    promised = [it for it in phase.items if grammar.expected_kinds(it.expect)]
    if promised:  # F22: the record held to its own promises — met, or short and said so
        met = [it for it in promised if {k for k, _ in grammar.expected_kinds(it.expect)} <= {k for k, _ in it.evidence}]
        short = [it for it in promised if it not in met]
        line = f"- expectations: {len(met)} met"
        if short:
            line += f" · {len(short)} short (" + "; ".join(
                f"{it.n}.{it.m} expected {' · '.join(k for k, _ in grammar.expected_kinds(it.expect))}, "
                f"got {' · '.join(sorted({k for k, _ in it.evidence})) or 'nothing'}" for it in short) + ")"
        lines.append(line)
    lines += bucket("notes", [rel(n) for n in phase.notes])
    # item results (`RESULT · N.M: …`) live under their items below; the digest keeps the phase-level ones
    lines += bucket("results", [rel(ev.text) for ev in evs if ev.type == "RESULT" and not ITEM_RESULT_RE.match(ev.text)])
    lines += bucket("problems", [rel(ev.text) for ev in evs if ev.type == "PROBLEM"])
    lines += bucket("decisions", [rel(ev.text) for ev in evs if ev.type == "DECISION"
                                  and not ev.text.startswith(("reflect:", "align:"))])
    for tag in ("reflect", "align"):
        for ev in evs:
            if ev.type == "DECISION" and ev.text.startswith(f"{tag}:"):
                lines.append(f"- {tag}: {rel(ev.text[len(tag) + 1:].strip())}")
    return lines


def _cancel_phase(case: Path, todo: grammar.Todo, phase: grammar.Phase, why: str, out: Outcome) -> str:
    """Collapse a phase with a reason (F20): its file gets `result: снято: …`, its items are listed there
    as cancelled, the TODO line becomes one closed line marked «снято». Returns the journal text."""
    date, _ = _now()
    pf = _phase_file(case, phase.n, phase.name)
    if not pf.exists():  # a planned phase: the file is born closed, so the collapsed line has somewhere to point
        pf.parent.mkdir(exist_ok=True)
        pf.write_text(f"# Phase {phase.n} — {phase.name}\ngoal: {phase.summary or '—'}\nresult:\n\n## Notes\n", encoding="utf-8")
    lines = pf.read_text(encoding="utf-8").split("\n")
    lines[2] = f"result: снято: {why}"
    if phase.notes:
        lines += ["", "## Notes at cancel", *(f"- note: {_rewrite_links(n, case, new_base=pf.parent)[0]}" for n in phase.notes)]
    if phase.items:
        lines += ["", "## Items at cancel", *(ln for it in phase.items for ln in _item_block_for_phase_file(case, pf, it))]
    pf.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")
    items = ", ".join(f"{it.n}.{it.m}" for it in phase.items if not it.done)
    waits = ", ".join(phase.waits)
    phase.done, phase.items, phase.waits, phase.notes = True, [], [], []
    phase.summary = f"снято: {why} · {date} · {_phase_link(pf.name)}"
    text = f"снята фаза {phase.n} {phase.name} — {why}"
    if items:
        text += f" (пункты сняты: {items})"
    if waits:
        out.warn(f"phase {phase.n} waited for {waits} — the nested case stays open on its own; close or cancel it separately")
    return text


def phase_cancel(case: Path, n: int, why: str) -> Outcome:
    """The branch is not needed: `el phase cancel N "why"` — the second honest end of a node (F20)."""
    out = Outcome()
    why = " ".join(why.split())
    if not why:
        raise StoreError(f"cancel needs a reason: el phase cancel {n} \"why the phase is no longer needed\"", 2)
    todo = _todo(case, out)
    phase = todo.phase(n)
    if phase is None:
        raise StoreError(f"no phase {n} in TODO.md", 4)
    if phase.done:
        raise StoreError(f"phase {n} {phase.name} is already closed", 4)
    text = _cancel_phase(case, todo, phase, why, out)
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    out.lines = log(case, "DECISION", text, f"p{n}").lines + out.lines
    out.say(f"cancelled: phase {n} {phase.name} → one line in TODO («снято»), reason in the journal, phases/{_phase_file(case, n, phase.name).name}")
    return out


# ---- readme -------------------------------------------------------------------------------------
def readme(case: Path, text: str) -> Outcome:
    out = Outcome()
    body, _ = stamp.split(text)
    try:
        todo = _todo(case, out)
        if not re.search(r"^- progress:", body, re.M):
            body = _set_state_line(body, "progress: ", progress_line(todo, case))
    except StoreError as e:  # readme-only mode: the README is written, progress: is not synced
        out.warn(f"progress: not synced — {e} (recovery: {e.recovery})")
    _write_readme(case, body, out, anchor=True)
    out.say("written: README.md (State anchored `as of` the newest journal entry; Links rendered from the files)")
    return out


SECTION_NAMES = {n.lower(): n for n in grammar.README_SECTIONS}


def _readme_sections(case: Path, out: Outcome):
    body = _readme_text(case, out)
    parsed = grammar.parse_readme(body)
    if parsed.errors:
        raise _unparsable(case, "README.md")
    return parsed


def _render_readme(parsed) -> str:
    lines = [f"# {parsed.title}"]
    for name in grammar.README_SECTIONS:
        lines += ["", f"## {name}"] + parsed.sections.get(name, [])
    return "\n".join(lines) + "\n"


def _line_elsewhere(parsed, prefix: str):
    """(section, k, text) of the first bullet outside State that starts with `prefix` as a whole word."""
    for name in grammar.README_SECTIONS:
        if name == "State":
            continue
        bullets = [ln[2:] for ln in parsed.sections.get(name, []) if ln.startswith("- ")]
        for k, body in enumerate(bullets, 1):
            if body.startswith(prefix) and (len(body) == len(prefix) or not body[len(prefix)].isalnum()):
                return name, k, body
    return None


def readme_set(case: Path, prefix: str, text: str) -> Outcome:
    """Replace (or create) the `- <prefix>: …` line in State — one line instead of a full rewrite.
    State only: a prefix that names a line of another section is refused with that line's edit
    command (feedback 2026-09-08: `set "1 Реклама" …` on a Decisions line quietly opened a second,
    doubled line in State); Elephant's own lines are not set by hand (F3)."""
    out = Outcome()
    parsed = _readme_sections(case, out)  # ensures the file parses before we touch it
    prefix = prefix.rstrip(":")
    text = " ".join(text.split())
    if prefix.lower() == "closed":
        raise StoreError("`- closed:` is written by `el done \"outcome\"` or `el case cancel \"why\"` — the case closes through "
                         "its gates (every phase and nested case ended), not by a State line (F20)", 2)
    if prefix.lower() in STATE_OWNED:
        raise StoreError(f"`- {prefix}:` is held by el (derived on every write) — it is not set by hand (F3); "
                         f"State is still true and only its anchor is behind: el readme touch", 2)
    if not text:  # an empty value removes the line — what the caller tries first (feedback 2026-09-03)
        return readme_drop(case, "state", prefix)
    if not any(ln.startswith(f"- {prefix}:") for ln in parsed.sections.get("State", [])):
        hit = _line_elsewhere(parsed, prefix)
        if hit:
            name, k, line = hit
            raise StoreError(f"`{prefix}` is not a State line — it is {name} line {k}: «{order._short(line, 60)}»; "
                             f"set writes State only → el readme edit {name.lower()} {k} \"…\"", 4)
    body = _set_state_line(_readme_text(case, out), f"{prefix}: ", text)
    _write_readme(case, body, out, anchor=True)
    out.say(f"README State: `- {prefix}: …` set (as of the newest journal entry)")
    return out


STATE_OWNED = grammar.STATE_OWNED  # lines el derives on every write — not yours to remove


def readme_add(case: Path, section: str, line: str) -> Outcome:
    out = Outcome()
    name = SECTION_NAMES.get(section.lower())
    if name is None:
        raise StoreError(f"no section `{section}` — sections: {' · '.join(grammar.README_SECTIONS)}", 2)
    parsed = _readme_sections(case, out)
    parsed.sections.setdefault(name, []).append(f"- {' '.join(line.split())}")
    _write_readme(case, _render_readme(parsed), out, anchor=name == "State")
    out.say(f"README {name}: line added")
    return out


def readme_edit(case: Path, section: str, ref: str, text: str) -> Outcome:
    """Replace line k of a section in place — the order is kept (feedback 2026-09-08: fixing two of
    six Decisions lines meant dump README, patch it with python, `--file`). State goes by prefix (`set`)."""
    out = Outcome()
    name = SECTION_NAMES.get(section.lower())
    if name is None:
        raise StoreError(f"no section `{section}` — sections: {' · '.join(grammar.README_SECTIONS)}", 2)
    text = " ".join(text.split())
    if not text:
        raise StoreError(f"usage: el readme edit {name.lower()} <k> \"new text\" — to remove a line: el readme drop {name.lower()} <k>", 2)
    if name == "State":
        return readme_set(case, ref, text)
    parsed = _readme_sections(case, out)
    ref = str(ref).strip()
    if not ref.isdigit():
        raise StoreError(f"usage: el readme edit {name.lower()} <k> \"new text\" — k is the line's position (1 = first bullet)", 2)
    k = int(ref)
    bullets = [i for i, ln in enumerate(parsed.sections.get(name, [])) if ln.startswith("- ")]
    if not 1 <= k <= len(bullets):
        raise StoreError(f"{name} has {len(bullets)} line(s), nothing at position {k}", 4)
    old = parsed.sections[name][bullets[k - 1]]
    parsed.sections[name][bullets[k - 1]] = f"- {text}"
    _write_readme(case, _render_readme(parsed), out)
    out.say(f"README {name}: line {k} edited → «{text}» (was: «{old[2:]}»)")
    return out


def readme_touch(case: Path) -> Outcome:
    """State was read and is still true: move the `as of` anchor to the newest journal entry and
    change nothing else (feedback 2026-09-08: after every `todo done` the agent re-set `last:` with
    the same text just to move the date — four times a session). Saying it is cheap; so is `set next`
    with the old text — the named command is the honest form of the same confirmation (S5)."""
    out = Outcome()
    _readme_sections(case, out)
    _write_readme(case, _readme_text(case, out), out, anchor=True)
    out.say("README State: confirmed current — `as of` anchored to the newest journal entry, nothing else changed")
    return out


def readme_drop(case: Path, section: str, ref: str) -> Outcome:
    """Drop line k of a section; in State a line is addressed by its prefix (`el readme drop
    state пауза`) — State lines were one-way before (feedback 2026-09-03)."""
    out = Outcome()
    name = SECTION_NAMES.get(section.lower())
    if name is None:
        raise StoreError(f"no section `{section}` — sections: {' · '.join(grammar.README_SECTIONS)}", 2)
    parsed = _readme_sections(case, out)
    ref = str(ref).strip()
    if not ref.isdigit():
        if name != "State":
            raise StoreError(f"usage: el readme drop {name.lower()} <k> — a position; only State lines go by prefix", 2)
        prefix = ref.rstrip(":")
        if prefix.lower() in STATE_OWNED:
            raise StoreError(f"`- {prefix}:` is held by el (derived on every write) — it does not get removed (F3)", 2)
        at = next((i for i, ln in enumerate(parsed.sections.get("State", [])) if ln.startswith(f"- {prefix}:")), None)
        if at is None:
            have = ", ".join(ln[2:].split(":")[0] for ln in parsed.sections.get("State", []) if ln.startswith("- "))
            raise StoreError(f"no `- {prefix}:` line in State (lines: {have})", 4)
        removed = parsed.sections["State"].pop(at)
        _write_readme(case, _render_readme(parsed), out, anchor=True)
        out.say(f"README State: `- {prefix}: …` removed")
        return out
    k = int(ref)
    bullets = [i for i, ln in enumerate(parsed.sections.get(name, [])) if ln.startswith("- ")]
    if not 1 <= k <= len(bullets):
        raise StoreError(f"{name} has {len(bullets)} line(s), nothing at position {k}", 4)
    removed = parsed.sections[name].pop(bullets[k - 1])
    _write_readme(case, _render_readme(parsed), out, anchor=name == "State")
    out.say(f"README {name}: dropped «{removed[2:]}»")
    return out


# ---- cases --------------------------------------------------------------------------------------
# A case is named in the words the owner says — often Cyrillic. The folder name stays latin (paths,
# links and git behave), so the name is transliterated instead of refused: the human name survives
# as the README title (dry run 2026-09-14 — `case new "договор с подрядчиком"` died on L2, and the
# message spoke of "letters/digits" while the agent had typed letters).
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "ё": "e", "є": "ye",
    "ж": "zh", "з": "z", "и": "i", "і": "i", "ї": "yi", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h",
    "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def _slug(name: str) -> str:
    latin = "".join(_TRANSLIT.get(ch, ch) for ch in name.lower())
    return re.sub(r"[^a-z0-9]+", "-", latin).strip("-")


def _case_folder(name: str) -> str:
    """`YYYY-MM-DD-<slug>`. A date already present in the name is used, not doubled (feedback 2026-08-31)."""
    m = store.DATE_PREFIX_RE.match(name.strip())
    if m:
        date, name = name.strip()[:10], name.strip()[11:]
    else:
        date, _ = _now()
    folder = f"{date}-{_slug(name)}"
    if not store.CASE_NAME_RE.match(folder):
        raise StoreError(f"`{name.strip()}` leaves no folder name: a case is `YYYY-MM-DD-<words>`, and nothing in "
                         f"this name became letters or digits (L2)", 2,
                         recovery='name it in words, e.g. el case new "contract with the builder" --goal "…"')
    return folder


def case_new(root: Path, name: str, goal: str, parent: Optional[Path] = None) -> Path:
    folder = _case_folder(name)
    case = (parent or root) / folder
    if case.exists():
        raise StoreError(f"{case} already exists", 4)
    case.mkdir()
    title = name.strip()
    goal = " ".join(goal.split())
    links = [f"- parent: {parent.name} · фаза {_phase_of(store.todo_of(parent))[1:]}"] if parent else []
    d, t = _now()
    readme_text = "\n".join([
        f"# {title}", "", "## Context", goal, "", "## State", "- progress: (no phases yet)",
        "- next: open phase 1 — `el phase open 1 <Name> --goal \"…\"`", f"- as of: {d} {t} · p0 (1 event)", "",
        "## Decisions", "", "## Problems", "", "## Links", *links, ""])
    store_write_fresh(case, "README.md", readme_text)
    store_write_fresh(case, "TODO.md", f"# TODO — {title}\n")
    event_lines, _ = _render_event("PHASE", f"дело открыто: {goal}")
    store_write_fresh(case, "JOURNAL.md", "\n".join([f"# JOURNAL — {title}", "", f"- {d} {t} · p0", *event_lines]) + "\n")
    return case


def store_write_fresh(case: Path, name: str, body: str):
    (case / name).write_text(stamp.apply(body), encoding="utf-8")


def case_list(root: Path, everything: bool = False) -> Outcome:
    """Where every case stands (the owner's question of 2026-09-14: which cases are still open?).
    Open cases first, each on the same line it shows at its parent — rendered from its own README
    (progress · next · due) plus the live days to its deadline and what it waits for; closed ones
    as a count plus the latest few (`--all` for every one), so thirty finished matters never drown
    the two live ones. One rule for the node line wherever it is seen from outside (F18)."""
    out = Outcome()
    cases = store.all_cases(root)  # the project case first in root mode
    rejected0 = store.scan(root)[1]
    if not cases:
        for path, reason in rejected0:
            out.warn(f"not a case, ignored: {path.relative_to(root)} — {reason}")
        out.say("no cases yet — `el case new <name> --goal \"…\"`")
        return out
    try:
        current = store.hand(root)
    except StoreError:
        current = None
    for path, reason in store.scan(root)[1]:
        out.warn(f"not a case, ignored: {path.relative_to(root)} — {reason}")
    today = dt.date.today()
    rows = []
    for case in cases:
        depth = max(len(store.chain(case, root)) - 1, 0)
        status = order.child_status(case)
        waits: List[str] = []
        try:
            todo = grammar.parse_todo(store.read(case, "TODO.md"))
            waits = [w for p in todo.phases for w in p.waits]
        except StoreError:
            pass
        rows.append((case, depth, status, waits))
    live = [r for r in rows if r[2][0] not in ("closed", "legacy")]
    legacy = [r for r in rows if r[2][0] == "legacy"]
    closed = sorted((r for r in rows if r[2][0] == "closed"), key=lambda r: r[2][3], reverse=True)
    for case, depth, status, waits in live:
        mark = "*" if case == current else " "
        line = f"{mark} {'  ' * depth}{case.name} — {order.case_desc(status)}"
        if status[0] == "broken":
            line += f" → el --case {case.name} check"
        elif status[4]:
            try:
                line += f" ({_when((dt.date.fromisoformat(status[4]) - today).days)})"
            except ValueError:
                pass
        if waits:
            line += " · waits: " + ", ".join(waits)
        out.say(line)
    shown = closed if everything else closed[:order.CASES_SHOWN_CLOSED]
    for case, depth, status, _ in shown:
        out.say(f"  {'  ' * depth}closed: {case.name} — {order.case_desc(status)}")
    if len(closed) > len(shown):
        out.say(f"  … +{len(closed) - len(shown)} closed earlier — el case list --all")
    # cases from before el (README outside the grammar, never stamped): one count line by default —
    # 28 of them drew 28 BROKEN lines and pushed the two live cases off the screen (feedback 2026-09-15);
    # `--all` names each with its fix, and the case in hand is never hidden in the count
    named = legacy if everything else [r for r in legacy if r[0] == current]
    for case, depth, status, _ in named:
        mark = "*" if case == current else " "
        out.say(f"{mark} {'  ' * depth}legacy: {case.name} — {order.case_desc(status)} → el --case {case.name} migrate")
    if len(legacy) > len(named):
        out.say(f"  legacy (before el): {len(legacy) - len(named)} case(s) el cannot read until migrated — "
                f"el case list --all names them · el --case <name> migrate")
    tail = f" · {len(legacy)} legacy" if legacy else ""
    out.say("", f"cases: {len(rows)} · {len(live)} open · {len(closed)} closed{tail} · current is marked *; switch: `el case use <name>`")
    return out


def case_use(root: Path, name: str) -> Outcome:
    """Switch the hand like `cf target`: bump the target's JOURNAL.md mtime — no state file, no content change."""
    import os as _os

    out = Outcome()
    case = store.resolve_case(root, name)
    if not store.is_open(case):
        raise StoreError(f"{case.name} is closed — the hand only holds open cases", 4)
    _os.utime(case / "JOURNAL.md")
    out.say(f"current case: {' › '.join(store.chain(case, root))}")
    return out


def project_new(root: Path, name: str, goal: str) -> Outcome:
    """Root mode on: the project folder itself becomes the top case (its children live in .cases/)."""
    out = Outcome()
    project = root.parent
    for fname in store.FILES:
        f = store.file_path(project, fname)
        if f.exists():
            raise StoreError(f"{f.name} already exists in {project} — it may be your public readme or docs, and el will not "
                             f"overwrite it. Keep it and run the ordinary form instead: el case new \"{name}\" --goal \"…\" "
                             f"(the case lives in .cases/); root mode only after you move that file aside", 4)
    title = name.strip()
    goal = " ".join(goal.split())
    d, t = _now()
    store_write_fresh(project, "README.md", "\n".join([
        f"# {title}", "", "## Context", goal, "", "## State", "- progress: (no phases yet)",
        "- next: open phase 1 — `el phase open 1 <Name> --goal \"…\"`", f"- as of: {d} {t} · p0 (1 event)", "",
        "## Decisions", "", "## Problems", "", "## Links", ""]))
    store_write_fresh(project, "TODO.md", f"# TODO — {title}\n")
    event_lines, _ = _render_event("PHASE", f"проект открыт: {goal}")
    store_write_fresh(project, "JOURNAL.md", "\n".join([f"# JOURNAL — {title}", "", f"- {d} {t} · p0", *event_lines]) + "\n")
    out.say(f"root mode on: {project.name} is now the top case (README/TODO/JOURNAL in the project root); "
            f"feature cases live in .cases/ — `el case new \"…\" --goal \"…\"`")
    out.say("note: README.md, TODO.md and JOURNAL.md now lie in the project root, outside .cases/ — a .gitignore rule "
            "for .cases/ does not cover them: ignore them there too, or commit them on purpose")
    return out


def spawn(root: Path, parent: Path, name: str, goal: str) -> Outcome:
    out = Outcome()
    todo = _todo(parent, out)
    cur = todo.current()
    if cur is None:
        raise StoreError("parent has no open phase — spawn happens inside a phase (P11)", 4)
    into = root if parent == store.project_case(root) else parent
    child_name = _case_folder(name)
    if (into / child_name).exists():
        raise StoreError(f"{into / child_name} already exists", 4)
    # Parent first, child last: the hand follows the freshest JOURNAL.md, so the child must be written last.
    cur.waits.append(child_name)
    out.absorb(_write_todo(parent, todo))
    text = _readme_text(parent, out)
    lines = text.rstrip("\n").split("\n")
    idx = next(i for i, ln in enumerate(lines) if ln == "## State")
    j = idx + 1
    while j < len(lines) and not lines[j].startswith("## "):
        j += 1
    while j > idx + 1 and lines[j - 1] == "":
        j -= 1
    lines.insert(j, f"- ждёт: {child_name}")
    _write_readme(parent, "\n".join(lines) + "\n", out)
    out.lines = log(parent, "PROBLEM", f"{goal} · open → {child_name}/").lines + out.lines
    child = case_new(root, name, goal, parent=None if into == root else parent)
    out.say(f"spawned: {child.relative_to(root)} — hand moves to the child; parent waits in phase {cur.n}")
    hints.attach(out, "case_new", root=root)
    return out


def _closed_line(value: str):
    """The `- closed:` State line is el's (written by `done` / `case cancel`, never typed): it obeys el's own
    pointer limit like `last:` does — the summary is shortened with «…», the whole text lives in the journal.
    Feedback 2026-09-15: a 140-char summary made el warn about a 192-char line it had written itself."""
    return value, order._short(value, grammar.README_POINTER_CHARS - len("- closed: "))


def done(root: Path, case: Path, summary: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    open_phases = [p for p in todo.phases if not p.done]
    if open_phases:
        raise StoreError("cannot close the case: open phases " + ", ".join(f"{p.n} {p.name}" for p in open_phases), 4)
    live = [(k.name, order.child_status(k)[0]) for k in order.child_cases(case, _is_project(case))]
    live = [f"{n} ({st})" for n, st in live if st != "closed"]
    if live:  # F20: a parent closes only when every child is done or cancelled; BROKEN holds it open (F18)
        raise StoreError("cannot close the case: nested cases still open — " + ", ".join(live) +
                         " → close each (el --case <name> done \"…\") or cancel it with a reason", 4)
    summary = " ".join(summary.split())
    date, _ = _now()
    closed, shown = _closed_line(f"{date} · {summary}")
    text = _set_state_line(_readme_text(case, out), "closed: ", shown)
    text = _set_state_line(text, "next: ", None)  # a closed case has no next step — the line would be a lie (2026-09-14)
    _write_readme(case, text, out, anchor=True)
    out.lines = log(case, "PHASE", f"дело закрыто → {summary}").lines + out.lines
    if shown != closed:
        out.say(f"closed: shortened to the pointer limit ({grammar.README_POINTER_CHARS} chars, F2) — the whole summary is in the journal (PHASE)")
    parent = store.parent_case(case, root)
    if parent is not None:
        ptodo = _todo(parent, out)
        awaited = False
        for p in ptodo.phases:
            if case.name in p.waits:
                awaited = True
                p.waits.remove(case.name)
                m = _next_number(parent, ptodo, p)
                # the child's outcome lands at the parent as a done item whose evidence is the child itself
                # (F20: the tool does not write a tick without a kind): file → the child's README
                p.items.append(grammar.Item(p.n, m, True, f"{summary} · {case.name}/", 0,
                                            evidence=[("file", _child_readme_link(parent, case))]))
        out.absorb(_write_todo(parent, ptodo))
        _write_readme(parent, _set_state_line(_readme_text(parent, out), "ждёт: ", None), out)
        # the child always reports to its parent, however it was created (F18): an awaited child
        # closes the PROBLEM that spawned it, any other child lands as a RESULT
        out.lines += log(parent, "PROBLEM" if awaited else "RESULT",
                         (f"закрыто → {summary} · {case.name}/" if awaited else f"дело закрыто → {summary} · {case.name}/")).lines
        out.say(f"parent updated: {parent.name} — hand returns to the parent")
    out.say(f"closed: {case.name}")
    return out


def case_cancel(root: Path, case: Path, why: str) -> Outcome:
    """The whole case is not needed (F20): open phases collapse with the reason, the case closes as
    «снято», the parent gets one line. Nested cases must already be closed or cancelled."""
    out = Outcome()
    why = " ".join(why.split())
    if not why:
        raise StoreError("cancel needs a reason: el case cancel \"why the case is no longer needed\"", 2)
    todo = _todo(case, out)
    if re.search(r"^- closed: ", _readme_text(case, out), re.M):
        raise StoreError(f"{case.name} is already closed", 4)
    live = [f"{k.name} ({order.child_status(k)[0]})" for k in order.child_cases(case, _is_project(case)) if order.child_status(k)[0] != "closed"]
    if live:
        raise StoreError("cannot cancel the case: nested cases still open — " + ", ".join(live) + " → close or cancel each first", 4)
    for p in todo.phases:
        if not p.done:
            out.lines += log(case, "DECISION", _cancel_phase(case, todo, p, why, out), f"p{p.n}").lines
    out.absorb(_write_todo(case, todo))
    date, _ = _now()
    text = _set_state_line(_readme_text(case, out), "closed: ", _closed_line(f"{date} · снято: {why}")[1])
    text = _set_state_line(text, "next: ", None)  # nothing is next for a cancelled case
    _write_readme(case, text, out, anchor=True)
    out.lines = log(case, "DECISION", f"дело снято → {why}").lines + out.lines
    parent = store.parent_case(case, root)
    if parent is not None:
        ptodo = _todo(parent, out)
        for p in ptodo.phases:
            if case.name in p.waits:
                p.waits.remove(case.name)
                m = _next_number(parent, ptodo, p)
                p.items.append(grammar.Item(p.n, m, True, f"снято: {why} · {case.name}/", 0,
                                            evidence=[("file", _child_readme_link(parent, case))]))
        out.absorb(_write_todo(parent, ptodo))
        _write_readme(parent, _set_state_line(_readme_text(parent, out), "ждёт: ", None), out)
        out.lines += log(parent, "DECISION", f"снято → {why} · {case.name}/").lines
        out.say(f"parent updated: {parent.name}")
    out.say(f"cancelled: {case.name} — closed as «снято», reason in the journal")
    return out


# ---- doctor -------------------------------------------------------------------------------------
def doctor() -> Outcome:
    """Read-only diagnostics: what el sees from here. Never writes, never rebuilds (feedback #4)."""
    from . import __version__

    out = Outcome()
    out.say(f"el {__version__} · python OK · cwd: {Path.cwd()} (el never changes your cwd)")
    try:
        root = store.find_root()
    except StoreError as e:
        out.say(f"root: NOT FOUND — {e}", f"  recovery: {e.recovery}")
        return out
    out.say(f"root: {root}")
    cases = store.all_cases(root)
    rejected = store.scan(root)[1]
    out.say(f"cases: {len(cases)} ({sum(store.is_open(c) for c in cases)} open)")
    for path, reason in rejected:
        out.say(f"  ! not a case, ignored: {path.relative_to(root)} — {reason}")
    try:
        case = store.hand(root)
        out.say(f"hand: {' › '.join(store.chain(case, root))}")
        for name in store.FILES:
            f = store.file_path(case, name)
            if not f.exists():
                out.say(f"  ! {name}: MISSING (L3)")
                continue
            _, state = stamp.verify(f.read_text(encoding="utf-8"))
            note = {"ok": "stamp ok", "missing": "no stamp yet (set on first el write)",
                    "mismatch": "stamp MISMATCH — edited bypassing Elephant; next el write will rebuild (S4)",
                    "not-last": "stamp NOT LAST — something appended after it; next el write will rebuild (S4)"}[state]
            out.say(f"  {f.name}: {note}")
        for name, why in store.legacy_files(case):
            out.say(f"  ! {name}: legacy — {why}; outside the grammar and never stamped → {store.MIGRATE_HINT}")
        for rec in store.recover_files(case):
            out.say(f"  ! pending {rec.name} — re-enter its lines with el, then: rm '{rec}'")
        if case != store.project_case(store.find_root()):
            for stray in store.stray_files(case):
                out.say(f"  ! extra file in the case root: {stray.name} — move into a folder by kind (L4)")
    except StoreError as e:
        out.say(f"hand: — ({e})", f"  recovery: {e.recovery}")
    out.say("read-only: doctor changed nothing")
    return out


# ---- feedback -----------------------------------------------------------------------------------
def feedback_dir() -> Path:
    """Feedback pool lives in the elephant-cli clone (env EL_FEEDBACK_DIR overrides, e.g. in tests) —
    it travels between machines with `git pull`, like elephant's pool."""
    import os as _os

    override = _os.environ.get("EL_FEEDBACK_DIR")
    return Path(override) if override else Path(__file__).resolve().parent.parent / "feedback"


def feedback(title: str, expected: str, actual: str, why: str, acceptance: str, repro: str) -> Outcome:
    out = Outcome()
    title = " ".join(title.split())
    if not title or not expected or not actual:
        raise StoreError("feedback needs at least a title, --expected and --actual; add --repro/--why/--acceptance "
                         "when you can", 2)
    d, t = _now()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "feedback"
    folder = feedback_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{d}-{t.replace(':', '')}-{slug}.md"
    try:
        case = " › ".join(store.chain(store.hand(store.find_root()), store.find_root()))
    except StoreError:
        case = "—"
    from . import __version__
    sections = [f"# {title}", "", f"date: {d} {t} · el {__version__} · case: {case}", ""]
    for heading, text_ in (("Reproduction", repro), ("Actual", actual), ("Expected", expected),
                           ("Why", why), ("Acceptance", acceptance)):
        if text_:
            sections += [f"## {heading}", text_.strip(), ""]
    path.write_text("\n".join(sections), encoding="utf-8")
    out.say(f"feedback written: {path}")
    return out


# ---- mv: a file moves, its links follow -----------------------------------------------------------
def _rewrite_links(text: str, base: Path, src: Optional[Path] = None, dst: Optional[Path] = None,
                   new_base: Optional[Path] = None):
    """Markdown link targets in `text` (a file living in `base`) that resolve to `src` now point at
    `dst`; when the text itself moves (`new_base`), every relative target is re-based as well —
    with `src` omitted that is all it does (a line copied from TODO into phases/).
    Returns (text, number of links rewritten). URLs and anchors are left alone."""
    import os
    count = 0

    def fix(m):
        nonlocal count
        target = m.group(2)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            return m.group(0)
        path, _, anchor = target.partition("#")
        resolved = (base / path).resolve()
        if src is not None and resolved == src.resolve():
            new = os.path.relpath(dst, new_base or base)
        elif new_base is not None and new_base.resolve() != base.resolve():
            new = os.path.relpath(resolved, new_base.resolve())
        else:
            return m.group(0)
        if new == path:
            return m.group(0)
        count += 1
        return f"{m.group(1)}{new}{'#' + anchor if anchor else ''}{m.group(3)}"

    text = "".join(seg if code else order.LINK_RE.sub(fix, seg) for seg, code in order.outside_code(text))
    return text, count


def _case_path(case: Path, given: str) -> str:
    """A path as the agent typed it — case-relative (`docs/x.md`), repo-relative from tab completion
    (`.cases/<case>/docs/x.md`), or absolute — normalised to the case (feedback 2026-09-16: tab completion
    from the repo root expands `.cases/<case>/…`, and `mv` refused a valid file). Outside the case the text
    comes back as given, so the refusal that follows names it."""
    raw = given.strip()
    if not raw:
        return raw
    trailing = raw.endswith("/")
    cand = Path(raw).expanduser()
    if not cand.is_absolute():
        cand = Path.cwd() / cand
    try:
        rel = cand.resolve().relative_to(case.resolve()).as_posix()
        if rel == ".":
            return raw
        return rel + ("/" if trailing else "")
    except ValueError:
        pass
    try:  # from the project root with the case folder spelled out
        rel = cand.resolve().relative_to((_project_root(case) / store.CASES_DIR / case.name).resolve()).as_posix()
        return rel + ("/" if trailing and rel != "." else "")
    except ValueError:
        return raw


def mv(case: Path, old: str, new: str) -> Outcome:
    """Move or rename a file inside the case and rewrite every markdown link to it — in the three
    owned files (through the stamp door) and in the case's own documents — so the map stays true
    (feedback 2026-09-03: one folder split broke 33 links, found only by a hand-written checker).
    An action, not an event: git keeps the history."""
    out = Outcome()
    old, new = _case_path(case, old), _case_path(case, new)
    src = (case / old)
    if not src.is_file():
        raise StoreError(f"{old} is not a file in the case (paths are relative to the case: docs/x.md; "
                         f".cases/<case>/… and absolute paths inside the case are accepted too)", 4)
    if src.name in store.FILES and src.parent == case:
        raise StoreError(f"{src.name} is one of the three case files — it does not move (L3)", 2)
    dst = case / new
    if new.endswith("/") or dst.is_dir():
        dst = dst / src.name
    for p in (src, dst):
        if case.resolve() not in p.resolve().parents:
            raise StoreError("mv works inside the case folder only", 2)
    if dst.exists():
        raise StoreError(f"{dst.relative_to(case)} already exists — mv never overwrites", 4)
    old_rel, new_rel = src.relative_to(case).as_posix(), dst.relative_to(case).as_posix()
    touched: List[str] = []
    # 1. the moved file's own links follow it — when it is markdown; a pdf, an image, a script moves
    #    as bytes, its body is never read (feedback 2026-09-09: `mv X.pdf outbox/` died decoding it,
    #    nothing moved). Links TO it are rewritten like for any file (step 2).
    dst.parent.mkdir(parents=True, exist_ok=True)
    body = None
    if src.suffix.lower() == ".md":
        try:
            body = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            out.warn(f"{old_rel} is not UTF-8 text — moved as is, links inside it (if any) untouched")
    if body is None:
        src.replace(dst)
    else:
        body, n = _rewrite_links(body, src.parent, src, dst, new_base=dst.parent)
        dst.write_text(body, encoding="utf-8")
        src.unlink()
        if n:
            touched.append(f"{new_rel} ({n} of its own)")
    touched += _follow_links(case, src, dst, out, skip=dst)
    if "README.md" not in " ".join(touched):
        _refresh_readme(case, out)  # Links follow the files
    out.say(f"moved: {old_rel} → {new_rel}" + (f" · links rewritten: {', '.join(touched)}" if touched else " · no links pointed at it"))
    return out


def relink(case: Path, old: str, new: str) -> Outcome:
    """The file already moved outside el (a plain `mv`, a rename in the editor): every link to
    `old` now points at `new` — the rewrite `el mv` does, without moving anything. The one door
    to a link in the journal, which hands cannot touch (feedback 2026-09-08: 10 dead journal links
    after files were moved without el, nothing to see them with and nothing to fix them with).
    `new` = none: the file is gone for good, or the link was an example written without backticks —
    the link is retired into literal text (`[name](old)` in inline code): the words stay verbatim,
    nothing claims a file any more. Without it a dead journal link would be a line in Order that
    nothing can close — caught on this tool's own journal within a minute of adding the check."""
    out = Outcome()
    old = _case_path(case, old)
    if new.strip().lower() != "none":
        new = _case_path(case, new)
    src = case / old
    if case.resolve() not in src.resolve().parents:
        raise StoreError("relink works inside the case folder only", 2)
    old_rel = src.relative_to(case).as_posix()
    if new.strip().lower() == "none":
        if src.exists():
            raise StoreError(f"{old} exists — a link to it is not dead; to retire the links delete or move the file first", 4)
        touched = _follow_links(case, src, None, out)
        if "README.md" not in " ".join(touched):
            _refresh_readme(case, out)
        n = sum(int(t.rsplit("(", 1)[1].rstrip(")").split()[0]) for t in touched) if touched else 0
        out.say(f"retired: {old_rel} — {n} link(s) now literal text `[name]({old_rel})`" + (f": {', '.join(touched)}" if touched else " (none pointed at it)"))
        return out
    dst = case / new
    if src.exists():
        raise StoreError(f"{old} still exists — to move it and rewrite the links in one go: el mv {old} {new}", 4)
    if not dst.is_file():
        raise StoreError(f"{new} is not a file in the case (paths are relative to the case: docs/x.md) — "
                         f"relink points the links at a file that exists; gone for good or an example: el relink {old} none", 4)
    if case.resolve() not in dst.resolve().parents:
        raise StoreError("relink works inside the case folder only", 2)
    new_rel = dst.relative_to(case).as_posix()
    touched = _follow_links(case, src, dst, out)
    if "README.md" not in " ".join(touched):
        _refresh_readme(case, out)
    out.say(f"relinked: {old_rel} → {new_rel}" + (f" · links rewritten: {', '.join(touched)}" if touched else " · no links pointed at it"))
    return out


FULL_LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")


def _retire_links(text: str, base: Path, src: Path):
    """Every markdown link in `text` (living in `base`) that resolves to `src` becomes inline code —
    the words stay, the claim of a file goes. Returns (text, count)."""
    count = 0

    def fix(m):
        nonlocal count
        target = m.group(2)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            return m.group(0)
        if (base / target.partition("#")[0]).resolve() != src.resolve():
            return m.group(0)
        count += 1
        return f"`{m.group(0)}`"

    text = "".join(seg if code else FULL_LINK_RE.sub(fix, seg) for seg, code in order.outside_code(text))
    return text, count


def _follow_links(case: Path, src: Path, dst: Optional[Path], out: Outcome, skip: Optional[Path] = None) -> List[str]:
    """Every link to `src` in the case now points at `dst` (or, with `dst` None, is retired into
    literal text): the three owned files through the stamp door (README last, so its derived
    `last:` reads the rewritten journal), then every other markdown file of the case except `skip`
    (a moved file, already rewritten) and the legacy archive. Returns what was touched, for the report."""
    old_rel = src.relative_to(case).as_posix()
    new_rel = dst.relative_to(case).as_posix() if dst is not None else None

    def rewrite(text: str, base: Path):
        return _rewrite_links(text, base, src, dst) if dst is not None else _retire_links(text, base, src)

    touched: List[str] = []
    for name in ("JOURNAL.md", "TODO.md", "README.md"):
        p = store.file_path(case, name)
        if not p.exists():
            continue
        text, _ = stamp.split(store.read(case, name))
        new_text, n = rewrite(text, case)
        k = new_text.count(f"`{old_rel}`") if new_rel else 0
        if new_rel:
            new_text = new_text.replace(f"`{old_rel}`", f"`{new_rel}`")
        if new_text != text:
            if name == "README.md":
                _write_readme(case, new_text, out)
            else:
                out.absorb(store.write(case, name, new_text))
            touched.append(f"{name} ({n + k})")
    # every other markdown file of the case (documents, phase files), never the legacy archive
    for p in sorted(case.rglob("*.md")):
        rel = p.relative_to(case)
        if p == skip or any(part.startswith(".") or part in ("node_modules", "legacy") for part in rel.parts):
            continue
        if rel.parts[0] == store.CASES_DIR or any(store.is_case_dir(case / Path(*rel.parts[:i + 1])) for i in range(len(rel.parts) - 1)):
            continue
        if p.parent == case and p.name in store.FILES:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        new_text, n = rewrite(text, p.parent)
        if n:
            p.write_text(new_text, encoding="utf-8")
            touched.append(f"{rel.as_posix()} ({n})")
    return touched


# ---- dates: what the tool can count -----------------------------------------------------------------
STATE_DUE_RE = re.compile(r"^- due: (\d{4}-\d{2}-\d{2})(?:\s*[·—–-]?\s*(.*))?$", re.M)


def _child_readme_link(parent: Path, child: Path) -> str:
    """`[child-name](child-name/README.md)` — from a normal parent; `.cases/…` from the project case."""
    prefix = f"{order.CASES_DIR}/" if _is_project(parent) else ""
    return f"[{child.name}]({prefix}{child.name}/README.md)"


def _when(days: int) -> str:
    """`today` · `in 3 days` · `2 days ago` — how the tool says a distance in days."""
    if days == 0:
        return "today"
    if days > 0:
        return f"in {days} day{'s' if days != 1 else ''}"
    return f"{-days} day{'s' if days != -1 else ''} ago"


def _dated(todo: grammar.Todo, readme_body: str, today: dt.date):
    """(overdue, due today, next 7 days, deadline) — from `— due:` items of open phases and the
    State line `- due: YYYY-MM-DD · what` (the case deadline). Held and done items do not count."""
    items = []
    for p in todo.phases:
        if p.done:
            continue
        for it in p.items:
            if it.due and not it.done and not it.held:
                try:
                    items.append((it, dt.date.fromisoformat(it.due)))
                except ValueError:
                    continue
    overdue = [(it, d) for it, d in items if d < today]
    due_today = [it for it, d in items if d == today]
    week = [(it, d) for it, d in items if today < d <= today + dt.timedelta(days=7)]
    deadline = None
    m = STATE_DUE_RE.search(readme_body)
    if m:
        try:
            deadline = (dt.date.fromisoformat(m.group(1)), (m.group(2) or "").strip())
        except ValueError:
            deadline = None
    return overdue, due_today, week, deadline


def _evidence_line(todo: grammar.Todo) -> Optional[str]:
    """`evidence: 11 done · file 3 · owner 7 · untyped 1` — the done items of the open phases by the kind
    of their evidence (F20). A count, not an Order line: an item ticked before 1.5.0 has no kind and
    is read, never nagged — the rule lives at the write door (the owner's word, 2026-09-14)."""
    done = [it for p in todo.phases if not p.done for it in p.items if it.done]
    if not done:
        return None
    parts = [f"{k} {n}" for k in grammar.EVIDENCE_KINDS if (n := sum(1 for it in done if any(kd == k for kd, _ in it.evidence)))]
    untyped = sum(1 for it in done if not it.evidence)
    if untyped:
        parts.append(f"untyped {untyped}")
    return f"evidence: {len(done)} done · " + " · ".join(parts)


PROBLEM_UNTIL_RE = re.compile(r"\buntil: (\d{4}-\d{2}-\d{2})")


def _problem_untils(readme_body: str):
    """(k, line, date) for every Problems line carrying `until: YYYY-MM-DD` — a workaround that is tolerated
    until a date (the owner's word, 2026-09-15: a crutch used for three months must have a return moment,
    or it becomes permanent). The tool counts the date; whether the crutch still stands is the owner's."""
    parsed = grammar.parse_readme(readme_body)
    if parsed.errors:
        return []
    found = []
    for k, ln in enumerate(parsed.sections.get("Problems", []), start=1):
        m = PROBLEM_UNTIL_RE.search(ln)
        if m:
            try:
                found.append((k, ln.lstrip("- ").strip(), dt.date.fromisoformat(m.group(1))))
            except ValueError:
                continue
    return found


def _until_lines(readme_body: str) -> List[str]:
    today = dt.date.today()
    return [f"problem {k} «{order._short(ln, 50)}» passed its until date {d.isoformat()} ({_when((d - today).days)}) → fixed: "
            f"el readme drop problems {k} · still needed: el readme edit problems {k} \"… until: <new date>\""
            for k, ln, d in _problem_untils(readme_body) if d < today]


def _dates_line(todo: grammar.Todo, readme_body: str) -> Optional[str]:
    today = dt.date.today()
    overdue, due_today, week, deadline = _dated(todo, readme_body, today)
    untils = [(k, ln, d) for k, ln, d in _problem_untils(readme_body) if d >= today]
    if not (overdue or due_today or week or deadline or untils):
        return None
    parts = [f"today {today.isoformat()}"]
    if due_today:
        parts.append("due today: " + ", ".join(f"{it.n}.{it.m} «{it.text}»" for it in due_today))
    if week:
        parts.append("next 7 days: " + ", ".join(f"{it.n}.{it.m} ({d.isoformat()[5:]})" for it, d in week))
    if overdue:
        parts.append(f"overdue: {len(overdue)} — see Order")
    if deadline:
        d, what = deadline
        parts.append(f"deadline {d.isoformat()}{f' «{what}»' if what else ''} {_when((d - today).days)}")
    for k, ln, d in untils:
        parts.append(f"problem {k} «{order._short(ln, 40)}» until {d.isoformat()} {_when((d - today).days)}")
    return "dates: " + " · ".join(parts)


RULE_ITEMS_LINK_RE = re.compile(r"^- rule: items link", re.M)
RULE_ITEMS_LINK = 'rule: items link their material'


def _items_link_rule(readme_body: str) -> bool:
    """The case rule «every item links the material it needs» — a Context line
    `- rule: items link their material`. Opt-in: a coding case rarely needs a document per item, a
    coordination case always does, and only the case can say which it is (feedback 2026-09-03)."""
    return RULE_ITEMS_LINK_RE.search(readme_body) is not None


def _blind_items(todo: grammar.Todo, readme_body: str) -> List[str]:
    if not _items_link_rule(readme_body):
        return []
    blind = [it for p in todo.phases if not p.done for it in p.items if not it.done and "](" not in _item_context(it)]
    if not blind:
        return []
    shown = ", ".join(f"{it.n}.{it.m}" for it in blind[:6]) + (f" … +{len(blind) - 6}" if len(blind) > 6 else "")
    return [f"{len(blind)} item(s) without a link to their material — {shown} → el todo edit N.M \"text — [name](docs/file.md)\" "
            f"(this case's rule: items link their material)"]


def _overdue_lines(todo: grammar.Todo, readme_body: str) -> List[str]:
    overdue = _dated(todo, readme_body, dt.date.today())[0]
    return [f"overdue: {it.n}.{it.m} «{it.text}» was due {d.isoformat()} → el todo done {it.n}.{it.m} <kind> \"…\" · "
            f"el todo due {it.n}.{it.m} <date> · el todo cancel {it.n}.{it.m} \"why\"" for it, d in overdue]


# ---- entry, order and check ---------------------------------------------------------------------
def _journal_headlines(journal: grammar.Journal, limit: int) -> List[str]:
    """The last `limit` entries as headlines only: no body lines, no legacy tool noise
    (`DECISION · todo …` written by v0.7–0.8 for every TODO edit). Bodies stay on disk."""
    total = len(journal.entries)
    lines = [f"# JOURNAL — last {min(limit, total)} of {total} entries (headlines; bodies in JOURNAL.md)"]
    for e in journal.entries[:limit]:
        events = [ev for ev in e.events if not (ev.type == "DECISION" and ev.text.startswith("todo "))]
        if not events:
            continue
        lines.append(f"- {e.date} {e.time} · {e.phase}")
        lines.extend(f"  {ev.type} · {ev.text}" for ev in events)
    return lines


def _refresh_readme(case: Path, out: Outcome) -> str:
    """On entry the README follows the folder: Links from the files, `last:` from the journal,
    `progress:` from TODO. Written only when something changed; failures never block the entry."""
    body, _ = stamp.split(store.read(case, "README.md"))
    derived = _derive_readme(case, body)
    if derived != body:
        try:
            out.absorb(store.write(case, "README.md", derived))
            out.say("README refreshed: Links from the files' summary lines · last: from the journal")
            return derived
        except StoreError as e:
            out.warn(f"README not refreshed — {e}")
    return body


def _ended_phase_lines(case: Path, todo: grammar.Todo, journal: Optional[grammar.Journal]) -> List[str]:
    """A phase whose every item ended is ready to end itself — the moment the owner decides: close it,
    or add what is still missing. The tool forces the downward rule (an open item holds its phase);
    the upward one is shown here (feedback 2026-09-14: phase 4 stood open over one [x] item and
    `order` said everything was in place). A phase with no items says nothing — nothing ended there.
    The line names what the close still needs, so the command it offers is one the tool will take."""
    lines: List[str] = []
    for p in sorted(todo.phases, key=lambda x: x.n):
        if p.done or not p.items or any(not it.done for it in p.items):
            continue
        needs: List[str] = []
        if journal is not None:
            for m in _closing_checks(case, p, journal):
                if "result:" in m or "is missing (F12)" in m:
                    continue
                needs.append((m.split(" → ", 1)[1] if " → " in m else m.split(": ", 1)[-1]).split(" · or")[0].strip())
        one = (f" · or in one command: el phase close {p.n} \"…\" --reflect \"…\" --align \"…\""
               if any("reflect:" in n or "align:" in n for n in needs) else "")
        lines.append(f"phase {p.n} {p.name}: every item ended ({len(p.items)} done) → close it: el phase close {p.n} \"what came out\""
                     + (f" — first: {' · '.join(needs)}{one}" if needs else "")
                     + f" · or add what is missing: el todo add {p.n} \"…\"")
    return lines


def _order_lines(case: Path, root: Path, readme_body: str, journal: Optional[grammar.Journal]) -> List[str]:
    parsed = grammar.parse_readme(readme_body)
    links = parsed.sections.get("Links", []) if not parsed.errors else []
    lines = order.report(case, _is_project(case), readme_body, journal, links)
    try:
        todo_now = store.todo_of(case)
        lines.extend(_overdue_lines(todo_now, readme_body))  # a date that passed is out of order
        lines.extend(_until_lines(readme_body))                # a workaround past its until date (F3)
        lines.extend(_blind_items(todo_now, readme_body))    # an item with nowhere to go (case rule)
        lines.extend(_gone_lines(case, todo_now))              # waiting for something that no longer exists (F19)
        lines.extend(_ended_phase_lines(case, todo_now, journal))  # every item ended: the phase is ready to end (F20)
        lines.extend(_promise_lines(case, todo_now))               # a promised proof nobody works towards (F12)
    except StoreError:
        pass
    lines.extend(order.people_lines(root))  # L10: a card every case reads before calling that person
    lines.extend(order.shared_links_lines(case, root, readme_body))  # the same description in two cases → one card
    legacy = store.legacy_files(case)
    if legacy:
        lines.insert(0, f"legacy file(s) outside Elephant's grammar, never stamped: {', '.join(n for n, _ in legacy)} → "
                        f"{store.MIGRATE_HINT}")
    for rec in store.recover_files(case):
        lines.append(f"pending {rec.name} → re-enter its lines with el, then: rm '{rec}' (S4)")
    if case != store.project_case(root):
        for stray in store.stray_files(case):
            lines.append(f"extra file in the case root: {stray.name} → move it into a folder by kind (L4)")
    return lines


RULES_TOPICS = "el help model · files · order · limits"


def _rules_pointer(root: Path) -> str:
    """Where the rules can be read FROM HERE. The help topics always answer; the spec file only where
    it exists (the elephant-cli clone) — `case new` ships no RULES.md into a project, and a pointer printed
    on every entry must resolve (feedback 2026-09-03: root case, `.cases/` empty, pointer dead)."""
    spec = root / "RULES.md"
    return f"{spec.relative_to(root.parent)} · {RULES_TOPICS}" if spec.is_file() else RULES_TOPICS


def entry(root: Path, case: Path) -> Outcome:
    out = Outcome()
    names = store.chain(case, root)
    out.say(f"el · case in hand: {' › '.join(names)}", "")
    others = [c.name for c in store.all_cases(root) if store.is_open(c) and c != case]
    if others:
        out.say("other open cases: " + " · ".join(others) + " — switch: `el case use <name>`", "")
    readme_body = _refresh_readme(case, out)
    todo_body, _ = stamp.split(store.read(case, "TODO.md"))
    todo = grammar.parse_todo(todo_body)
    if not todo.errors and _derive_todo(case, todo):  # phase lines follow their files (F18)
        try:
            out.absorb(store.write(case, "TODO.md", render_todo(todo)))
            todo_body = render_todo(todo)
            out.say("TODO refreshed: open phase lines follow their phase files (goal · path)")
        except StoreError as e:
            out.warn(f"TODO not refreshed — {e}")
    dates = _dates_line(todo, readme_body) if not todo.errors else None
    if dates:
        out.say(dates, "")  # what the tool can count: due today, this week, overdue, the deadline
    unblocked = _unblocked_line(case, todo) if not todo.errors else None
    if unblocked:
        out.say(unblocked, "")  # candidates by the dependency graph (F19) — the owner's `next:` stays the direction
    evidence = _evidence_line(todo) if not todo.errors else None
    if evidence:
        out.say(evidence, "")  # what the done items stand on (F20): file · ref · run · owner — counted, never nagged
    out.say(readme_body.rstrip("\n"), "")
    out.say(todo_body.rstrip("\n"), "")
    journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
    parked = _parked_line(case, todo, journal if not journal.errors else None) if not todo.errors else None
    if parked:
        out.say(parked, "")  # knowledge parked under a planned phase has a moment of return — counted until then (F22)
    if journal.entries:
        out.say(*_journal_headlines(journal, ENTRY_LIMIT), "")
    issues = _order_lines(case, root, readme_body, journal)
    if issues:
        out.say(f"## Order — {len(issues)} thing(s) to put back", *(f"- {ln}" for ln in issues), "")
    else:
        out.say("## Order", "- ✓ everything in place: files carry summaries, Links follow the files, State is current", "")
    out.say(f"how to work: el help start · what goes where: el help where · rules: {_rules_pointer(root)} · full check: el check")
    if not todo.errors:  # one hint, derived from the case, last (a model weighs the last line most)
        hints.attach(out, "entry", case=case, todo=todo, journal=journal if not journal.errors else None,
                     phase_file_exists=lambda p: _phase_file(case, p.n, p.name).exists(),
                     repeats=order.links_repeating_cards(root, readme_body))
    total = "\n".join(out.lines)
    if len(total) > MAX_SCREEN:
        out.lines = [total[:MAX_SCREEN], "", f"[truncated at {MAX_SCREEN} chars — README/TODO/JOURNAL are on disk]"]
    return out


def order_cmd(root: Path, case: Path, adopt: bool = False) -> Outcome:
    """What is out of order in the case in hand, with the command that fixes each line (P12).
    `--adopt`: move the descriptions the agent wrote in README Links into the files as `summary:`
    lines (F14) — the one mechanical fix el can do on the lower layer."""
    out = Outcome()
    if adopt:
        body = _readme_text(case, out)
        parsed = grammar.parse_readme(body)
        if parsed.errors:
            raise StoreError("README.md is not parsable — run `el check`", 3)
        _, fallback = order.render_links(case, _is_project(case), parsed.sections.get("Links", []))
        changed = order.adopt(case, fallback)
        for rel in changed:
            out.say(f"summary written into {rel} (from its Links description)")
        if not changed:
            out.say("nothing to adopt: every described file already carries its own summary")
    readme_body = _refresh_readme(case, out)
    journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
    issues = _order_lines(case, root, readme_body, journal)
    if issues:
        out.say(f"order — {len(issues)} thing(s) to put back:", *(f"- {ln}" for ln in issues))
    else:
        out.say("order: ✓ everything in place")
    return out


def migrate_cmd(case: Path, apply: bool = False) -> Outcome:
    """Legacy case → canonical files (P13). Dry run by default; `--apply` archives and writes."""
    out = Outcome()
    date, time = _now()
    plan = migrate.analyse(case, (date, time))
    if plan.empty:
        out.say(f"nothing to migrate: {case.name} — the three files are in Elephant's grammar and stamped (or absent)")
        return out
    out.say(*migrate.report(plan, dry=not apply))
    if not apply:
        return out
    for line in migrate.apply(plan):
        out.say(line)
    rel = plan.archive.relative_to(case)
    out.lines += log(case, "PHASE", f"дело перенесено из legacy формата → {rel}/ ({', '.join(sorted(plan.legacy))} byte-for-byte); "
                     f"журнал не конвертирован — перенеси нужное: el log; State переписать: el readme set next", "p0").lines
    if "README.md" not in plan.legacy:  # README kept: it still gets the pointer to the archive
        out.lines += readme_add(case, "links", f"{migrate.ARCHIVE_DIR}/ — файлы дела до миграции {date}, byte-for-byte: "
                                f"{', '.join(sorted(plan.legacy))}").lines
    _sync_progress(case, _todo(case, out), out)
    out.say("migrated — now: el (Order shows what to rewrite) · el readme set next \"…\" · el check")
    return out


def check(root: Path, only: Optional[Path] = None, everything: bool = False) -> Outcome:
    """The case in hand (`only`, with its nested cases) against the rules; `only` None = every case
    here. Feedback 2026-09-09: a workspace with legacy cases from past months made the bare `check`
    a 1 MB dump and exit 3 while the case in hand was clean — a gate the agent could not pass. Now
    the bare command means the case in hand, like every other command; `--all` is the workspace,
    and a legacy file there is one line with its recovery, not its every grammar error."""
    out = Outcome()
    cases = store.all_cases(root)  # the project case first in root mode (feedback 2026-09-01 #1)
    rejected = store.scan(root)[1]
    if only is not None:
        cases = [c for c in cases if c == only or only in c.parents]
    for path, reason in rejected:
        out.warn(f"not a case, ignored: {path.relative_to(root)} — {reason}")
    for ln in order.people_lines(root):  # once per workspace, not once per case
        out.warn(f"people · {ln}")
    errors = 0
    log_lines = []
    date, time = _now()
    for case in cases:
        legacy = dict(store.legacy_files(case))  # name → why: never stamped, outside the grammar
        for name, parse in (("README.md", grammar.parse_readme), ("TODO.md", grammar.parse_todo), ("JOURNAL.md", grammar.parse_journal)):
            p = store.file_path(case, name)
            if not p.exists():
                out.say(f"x {case.name}/{name}: missing (L3)")
                errors += 1
                continue
            text = p.read_text(encoding="utf-8")
            r = parse(text)
            if name in legacy:  # one line, with the one recovery — its errors are not a to-do list, migrate is
                out.say(f"x {case.name}/{name}: legacy — {legacy[name]}, not listed → el --case {case.name} migrate")
                log_lines.append(f"{date} {time} · {case.name} · {name} · legacy · {legacy[name]}")
                errors += 1
                continue
            for f in r.errors:
                out.say(f"x {case.name}/{name}: {f}")
                log_lines.append(f"{date} {time} · {case.name} · {name} · {f.rule} · {f.message}")
                errors += 1
            for f in r.warnings:
                out.warn(f"{case.name}/{name}: {f}")
            if r.stamp_state in ("mismatch", "not-last"):
                out.warn(f"{case.name}/{name}: stamp {r.stamp_state} — written bypassing Elephant (S4)")
                log_lines.append(f"{date} {time} · {case.name} · {name} · S4 · stamp {r.stamp_state}")
        for pf in sorted((case / "phases").glob("*.md")) if (case / "phases").exists() else []:
            r = grammar.parse_phase_file(pf.read_text(encoding="utf-8"))
            for f in r.errors:
                out.say(f"x {case.name}/phases/{pf.name}: {f}")
                log_lines.append(f"{date} {time} · {case.name} · phases/{pf.name} · {f.rule} · {f.message}")
                errors += 1
        for rec in store.recover_files(case):
            out.warn(f"{case.name}: pending {rec.name}")
        readme_text_ = store.read(case, "README.md") if store.file_path(case, "README.md").exists() else ""
        for folder in sorted(case.iterdir()):
            if (not folder.is_dir() or folder.name.startswith(".") or folder.name == "phases"
                    or store.is_case_dir(folder) or case == store.project_case(root)):
                continue
            if f"{folder.name}/" not in readme_text_:
                n_files = sum(1 for f in folder.rglob("*") if f.is_file())
                out.warn(f"{case.name}: folder {folder.name}/ ({n_files} file(s)) has no line in README Links — "
                         f"for the owner it does not exist (L5); add: el readme add links \"{folder.name}/ — …\"")
        if case != store.project_case(root):
            for stray in store.stray_files(case):
                out.say(f"x {case.name}: L4 · extra file in the case root: {stray.name} — only README/TODO/JOURNAL live "
                        f"there; move it into a folder by kind (docs/ research/ logs/ scripts/ …)")
                log_lines.append(f"{date} {time} · {case.name} · {stray.name} · L4 · extra file in the case root")
                errors += 1
        # order of the lower layer (F14, F15, S5): shown, never refused — Elephant does not write those files;
        # a closed case is an archive — `el order` still answers there when asked, check stays quiet
        if store.is_open(case) and store.file_path(case, "README.md").exists() and store.file_path(case, "JOURNAL.md").exists():
            rb, _ = stamp.split(readme_text_)
            jr = grammar.parse_journal(store.read(case, "JOURNAL.md"))
            links = grammar.parse_readme(rb).sections.get("Links", [])
            dead: list = []
            for ln in order.report(case, _is_project(case), rb, jr if not jr.errors else None, links, link_violations=dead):
                out.warn(f"{case.name}: order · {ln}")
            # a dead link in the files el holds is a violation, not a warning: the owner clicks and
            # nothing opens, and `violations: 0` is what gets read (feedback 2026-09-03)
            for f, t in dead:
                out.say(f"x {case.name}/{f}: F16 · broken link → {t} — fix the link, or move files with `el mv old new` (links follow)")
                log_lines.append(f"{date} {time} · {case.name} · {f} · F16 · broken link → {t}")
                errors += 1
    if log_lines:
        with (root / "checks.log").open("a", encoding="utf-8") as fh:
            fh.write("\n".join(log_lines) + "\n")
    if not cases:
        out.say("cases: 0 — NOTHING WAS CHECKED (no cases found here); a zero here is not a green light")
    else:
        scope = "all" if only is None else f"in hand: {only.name}" + ("" if everything else " · every case: el check --all")
        out.say(f"cases: {len(cases)} ({scope}) · violations: {errors} · warnings: {len(out.warnings)}")
    if errors:
        raise StoreError("\n".join(out.lines + [f"warning: {w}" for w in out.warnings]), 3)
    return out
