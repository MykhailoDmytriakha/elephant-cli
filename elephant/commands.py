"""The ten commands of `el` — every write to the three files goes through here (P3).

Each function takes the case folder (already resolved by main), does its preconditions (exit 4),
validates through the grammar (exit 3) and writes with a fresh stamp. Functions return the lines
to print on success; warnings are collected in `Outcome.warnings` and printed to stderr by main.
"""
import datetime as dt
import hashlib
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import grammar, hints, migrate, onboarding, order, stamp, store
from .store import StoreError

ENTRY_BODY_MARK = "— the case on disk: README · TODO · journal headlines —"
MAX_SCREEN = 24_000  # chars: Claude Code truncates tool output around 30K (owner's measurement 2026-08-22)
ENTRY_LIMIT = 10  # P1: last 10 journal entries on entry
# measured on the tool's own case (2026-09-17): 10 entries carried 46 event headlines — 8.6K chars, the heaviest
# part of a 20.6K-char entry; entries had grown to 5–8 events each. The entry shows the last 10 entries but at most
# this many event headlines; the rest of those entries is named, not printed (the cold entry is the case's measure)
ENTRY_EVENTS = 24


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
        if report.bypassed and HAND_EDIT_REPORT not in self.warnings:  # once per command, however many files it wrote
            self.warnings.append(HAND_EDIT_REPORT)


# The one moment el sees a workaround (the owner's word, 2026-10-06): a hand edit past the stamp is often a command el
# lacks or one the agent could not find — both are reports (depth 1 and 2), and only the agent knows which it was.
HAND_EDIT_REPORT = ("edited by hand because el had no command for it, or you could not find one? "
                    "el feedback \"…\" — unasked, then go on (el help feedback)")


def _now():
    t = dt.datetime.now()
    return t.strftime("%Y-%m-%d"), t.strftime("%H:%M")


def _phase_of(todo: grammar.Todo, case: Optional[Path] = None) -> str:
    """The phase an event belongs to by default: the one in flight (its file exists), else the first not closed.
    Since a planned phase may run before an earlier planned one (F24, 2026-09-25), «first not closed» is not «in flight»."""
    flying = _flying(case, todo) if case is not None else None
    cur = flying or todo.current()
    return f"p{cur.n}" if cur else "p0"


def _flying(case: Path, todo: grammar.Todo) -> Optional[grammar.Phase]:
    """The phase in flight: not closed, not paused for a detour (F26), and opened (its phase file exists) — one at a time (P8)."""
    return next((p for p in sorted(todo.phases, key=lambda x: x.n)
                 if not p.done and not p.held and _phase_file(case, p.n, p.name).exists()), None)


def _resume_after(todo: grammar.Todo, n: int) -> List[grammar.Phase]:
    """F26: the detour N ended (closed or cancelled) — the phase it paused is in flight again, by itself: the return
    address the owner asked for (2026-10-06). Detours inside detours unwind one at a time, each to the one it paused."""
    back = [p for p in todo.phases if not p.done and p.held_for() == n]
    for p in back:
        p.held, p.hold_reason = False, ""
    return back


def _say_resumed(case: Path, todo: grammar.Todo, back: List[grammar.Phase], n: int, out: Outcome) -> None:
    for p in back:
        nxt = next((it for it in p.items if not it.done and not it.held), None)
        out.say(f"phase {p.n} {p.name} resumed — the detour {n} is over" + (f"; next: {nxt.ref} {nxt.text}" if nxt else ""))


# ---- TODO rendering (machine-owned text) ---------------------------------------------------------
BARE_PHASE_PATH_RE = re.compile(r"(?<![\w/(\[`])(phases/\d+-[a-z0-9-]+\.md)(?![\w)`])")
BARE_WAITS_RE = re.compile(r"^  - waits: [^\[]", re.M)  # the bare case name el wrote before 1.31.0 (F6)


def _phase_link(file_name: str) -> str:
    """The phase file cited from TODO — a markdown link, so the editor opens it (feedback 2026-09-08:
    a bare `phases/2-calls.md` is text to the reader, `[…](…)` next to it is a link)."""
    return f"[phases/{file_name}](phases/{file_name})"


def _link_phase_paths(summary: str) -> str:
    """A phase line written before 0.18 cites its file as a bare path; every write renders it as a link. A proof slot of
    the goal (`[file: phases/5-x.md]`) is a promise of a file that may not exist yet, not a link — left as written (found
    2026-09-25 when the whole goal reached TODO: the promise became a dead link and `check` a violation)."""
    link = lambda text: BARE_PHASE_PATH_RE.sub(lambda m: f"[{m.group(1)}]({m.group(1)})", text)
    out, last = [], 0
    for m in grammar.EXPECT_SLOT_RE.finditer(summary):
        out += [link(summary[last:m.start()]), m.group(0)]
        last = m.end()
    return "".join(out) + link(summary[last:])


def _sub_tally(it: grammar.Item) -> str:
    """F25: what the item's sub-items came to — `2 done · 1 cancelled · 1 on hold · 1 open`, drawn at the end of the
    item line from the sub-items themselves (the owner's mockup, 2026-10-06), never typed, outside the F13 count."""
    if not it.subs:
        return ""
    n = {"done": sum(s.done for s in it.subs), "cancelled": sum(s.cancelled for s in it.subs),
         "on hold": sum(1 for s in it.subs if s.held and not s.ended), "open": sum(1 for s in it.subs if not s.ended and not s.held)}
    return grammar.TALLY_SUFFIX + " · ".join(f"{v} {k}" for k, v in n.items() if v)


def _item_block(it: grammar.Item, two_hands: bool = False, depth: int = 0, brief_subs: bool = False) -> List[str]:
    """The item as TODO renders it (F4 · F20 · F22): its line with the suffixes el keeps outside the F13
    count (after · due · hold), then the pockets in one fixed order — `why:` · `note:`… · `result:` with
    one proof line under it per kind (file · ref · run · owner). A done item without result words (ticked
    before 1.10.0, or a child case at its parent) lists its proof lines directly under the item. Written
    by el, read by the owner: the tick, the words and the proof are three lines, not one (the owner's
    word, 2026-09-15 — «результат в одну строку неудобно»)."""
    # F23: in a case that asks two hands a done item owes its acceptance — `[/]` until a second hand accepts it, then `[x]`
    mark = (("/" if two_hands and not it.accepted else "x") if it.done else "-" if it.cancelled
            else ("~" if it.held else " "))
    suffix = ((f" — after: {', '.join(it.after)}" if it.after else "") + (f" — due: {it.due}" if it.due else "")
              + (f" — hold: {it.hold_reason}" if it.held and it.hold_reason else "")
              + (f" — check: {it.hold_check}" if it.held and it.hold_reason and it.hold_check else "")
              + (f"{grammar.CANCELLED_SUFFIX}{it.cancel_reason}" if it.cancelled else "") + _sub_tally(it))
    pad = "  " * depth  # F25: a sub-item and its pockets sit one level deeper than an item's
    lines = [f"{pad}  - [{mark}] {it.ref} {it.text}{suffix}"]
    if it.why:
        lines.append(f"{pad}    - why: {it.why}")
    lines += [f"{pad}    - note: {n}" for n in it.notes]
    if it.expect:
        lines.append(f"{pad}    - expect: {it.expect}")
    if it.done and (it.result or it.evidence):
        deeper = "      " if it.result else "    "
        if it.result:
            lines.append(f"{pad}    - result: {it.result}")
        lines += [f"{pad}{deeper}- {k}: {pr}" if pr else f"{pad}{deeper}- {k}" for k, pr in it.evidence]
    if it.fact:  # expected while open, established once done — the line the fact chain is made of
        lines.append(f"{pad}    - fact: {it.fact}")
    # the story of the step first (why · expected · result · fact), then the hands: who did it, who accepted it
    if it.done and it.done_by:  # L8: provider · tool · model · session — el's line, written by done
        lines.append(f"{pad}    - done: {it.done_by}")
    if it.done and it.accepted:  # F23: who accepted the result, from which session, with what mind — el's line
        lines.append(f"{pad}    - accepted: {it.accepted}")
    # F25: the answer first, then how it was reached — the sub-items in the order they were taken, ended ones kept
    for s in it.subs:
        if brief_subs and s.ended:  # the entry: an ended sub-item is its line and what it established
            lines.append(_item_block(s, two_hands, depth + 1)[0])
            if s.fact:
                lines.append(f"{pad}      - fact: {s.fact}")
        else:
            lines += _item_block(s, two_hands, depth + 1)
    return lines


def _owes_acceptance(todo: grammar.Todo, two_hands: bool) -> bool:
    return two_hands and any(it.done and not it.accepted for p in todo.phases if not p.done for it in grammar.flat(p.items))


def render_todo(todo: grammar.Todo, two_hands: bool = False, root_mode: bool = False) -> str:
    out = [f"# {todo.title}", ""] + ([grammar.LEGEND, ""] if _owes_acceptance(todo, two_hands) else [])
    for p in sorted(todo.phases, key=lambda x: x.n):
        out.append(_phase_head(p))
        out += [f"  - note: {n}" for n in p.notes]  # F22: what the phase has to know, parked until it runs
        for it in [i for i in p.items if not i.held] + [i for i in p.items if i.held]:
            out += _item_block(it, two_hands and not p.done)  # a closed phase is history: the rule has no force there
        for w in p.waits:
            out.append(f"  - waits: {_case_link(w, root_mode)}")
    out += _later_section(todo)
    return "\n".join(out) + "\n"


def _phase_head(p: grammar.Phase) -> str:
    """The phase line: `[x]` closed · `[~]` paused for a detour, its hold last (F26) · `[ ]` open or planned."""
    mark = "x" if p.done else ("~" if p.held else " ")
    head = f"- [{mark}] {p.n} {p.name}"
    if p.summary:
        head += f" — {_link_phase_paths(p.summary)}"
    if p.held and not p.done:
        head += f"{grammar.PHASE_HOLD_SUFFIX}{p.hold_reason}"
    return head


def _later_block(it: grammar.Item) -> List[str]:
    """A line of the general list (F24): `  - [ ] Lk text — since: YYYY-MM-DD` and the item's pockets under it."""
    block = _item_block(it)
    return [f"  - [ ] L{it.m} {it.text}" + (f"{grammar.SINCE_SUFFIX}{it.since}" if it.since else "")] + block[1:]


def _later_section(todo: grammar.Todo) -> List[str]:
    if not todo.later:
        return []
    return ["", grammar.LATER_HEAD] + [ln for it in todo.later for ln in _later_block(it)]


def render_todo_entry(todo: grammar.Todo, two_hands: bool = False, root_mode: bool = False) -> Tuple[str, int]:
    """TODO as the ENTRY shows it: open items with their pockets (what to do, why, what is expected), done items
    collapsed to their line and their `fact:` — the result and the proofs are history the file keeps (TODO.md), not
    what the next agent needs to continue. Found on the tool's own case (2026-09-17): 25 done items with pockets
    pushed the entry past 24 000 chars and the Order block off the screen — the cold entry is the case's own
    measure (≤ 3K tokens). Returns (text, number of collapsed items)."""
    out = [f"# {todo.title}", ""] + ([grammar.LEGEND, ""] if _owes_acceptance(todo, two_hands) else [])
    collapsed = 0
    for p in sorted(todo.phases, key=lambda x: x.n):
        out.append(_phase_head(p))
        out += [f"  - note: {n}" for n in p.notes]
        for it in [i for i in p.items if not i.held] + [i for i in p.items if i.held]:
            if it.done:
                out.append(f"  - [{'/' if two_hands and not p.done and not it.accepted else 'x'}] {it.ref} {it.text}{_sub_tally(it)}")
                if it.fact:
                    out.append(f"    - fact: {it.fact}")
                if it.result or it.evidence or it.why or it.notes or it.expect or it.subs:
                    collapsed += 1
            else:
                out += _item_block(it, two_hands and not p.done, brief_subs=True)
        for w in p.waits:
            out.append(f"  - waits: {_case_link(w, root_mode)}")
    out += _later_section(todo)
    return "\n".join(out) + "\n", collapsed


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
        tail = f"{' '.join(parsed.goal.split())} · {_phase_link(pf.name)}"  # whole: never cut inside a proof slot (2026-09-25)
        if p.summary != tail:
            p.summary, changed = tail, True
    return changed


def _write_todo(case: Path, todo: grammar.Todo):
    """The one door for TODO writes: derived lines first (F18), then the stamp door."""
    _derive_todo(case, todo)
    return store.write(case, "TODO.md", render_todo(todo, _case_two_hands(case), _is_project(case)))


def _case_two_hands(case: Path) -> bool:
    """Does the case ask two hands (its Context line)? Read without the stamp door — a read, never a write."""
    try:
        return _two_hands(stamp.split(store.read(case, "README.md"))[0])
    except StoreError:
        return False


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
        if in_state and ln.startswith(f"- {prefix}") and not grammar.DRAWN_WAIT_RE.match(ln):  # el's line (F6), not set here
            if value is not None and not done:
                out.append(f"- {prefix}{value}")
            done = True  # replaced or removed
            continue
        out.append(ln)
    if in_state and not done and value is not None:
        add_line()
    return "\n".join(out) + "\n"


def progress_line(todo: grammar.Todo, case: Optional[Path] = None) -> str:
    """`✓` closed · `▶` opened (its phase file exists) · `⏸` paused for a detour (F26) · no mark = planned (F3)."""
    parts = []
    for p in sorted(todo.phases, key=lambda x: x.n):
        opened = case is not None and _phase_file(case, p.n, p.name).exists()
        cancelled = _cancelled(p)
        mark = (" ✗" if cancelled else " ✓") if p.done else (" ⏸" if p.held else " ▶" if opened else "")
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
    links, _ = order.render_links(case, _is_project(case), [_parent_line(case, ln) for ln in parsed.sections.get("Links", [])])
    text = _replace_section(body, "Links", links)
    try:
        todo = grammar.parse_todo(store.read(case, "TODO.md"))
        if not todo.errors:
            text = _set_state_line(text, "progress: ", progress_line(todo, case))
            if _default_next_in_state(text) and any(_phase_file(case, p.n, p.name).exists() for p in todo.phases):
                text = _set_state_line(text, "next: ", None)  # el's own pointer, done once a phase opened (L2) — never the agent's
            text = _draw_waits(case, text, [w for p in todo.phases for w in p.waits])
            if _ready_value(text) and (not _two_hands(text) or any(not p.done for p in todo.phases) or any(
                    order.child_status(k)[0] != "closed" for k in order.child_cases(case, _is_project(case)))):
                text = _set_state_line(text, READY_PREFIX, None)  # el's own word, untrue once work resumed
    except StoreError:
        pass
    try:
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
        # entries run newest first, events inside an entry are appended — the newest RESULT is the LAST one of its entry
        # (feedback 2026-10-05: two RESULTs in one minute showed the older one as `last:`)
        if not journal.errors:  # the decisions of the case, drawn from its journal (the owner's «yes», 2026-10-08)
            text = _draw_decisions(text, journal)
        opened = _opened_line(journal, parsed) if not journal.errors else None
        if opened:  # where the case started, first in State (the owner, 2026-10-08: «I opened the README and could not find
            text = _set_first_state_line(text, "opened: ", opened)  # what I started with»)
        last = next((ev for ev in journal.newest_first() if ev.type == "RESULT"), None)
        if last:  # the whole RESULT — headline and body — never cut (the owner's word, 2026-09-25)
            text = _set_state_line(text, "last: ", _event_words(last))
    except StoreError:
        pass
    return _blank_before_headings(text)


# ---- decisions drawn from the journal (the cold reader and the owner's «yes», 2026-10-08) -----------------------------
# Agents decide in the journal (`el log DECISION`) and leave README Decisions empty: six of eight big live cases. A cold
# reader given the README alone answered «which decisions were taken» with «not in the README» 8 times of 16; with the
# five newest agent decisions drawn under the agent's own lines, 0 of 16. They are history, not the case's rules: dated,
# under a line that says so — an old decision beside a newer State is read as old. el's own bookkeeping (acceptance,
# reopen, reflect, align, howto, scope, cancel, pause) is not a decision of the work and is left out.
DECISIONS_DRAWN_HEAD = grammar.DECISIONS_DRAWN_HEAD
DECISIONS_DRAWN = 5
EL_DECISION_RE = re.compile(  # the formats el itself writes — an agent's «фаза 2 uses …» is a decision (Codex, 2026-10-08)
    r"^(?:howto|reflect|align): |^принято [\d., L]+: |^снято \d|^дело снято →|^объём фазы \d+ утверждён владельцем: «"
    r"|^остаток фазы \d+ → |^фаза \d+ (?:[\w-]+ ){0,3}(?:возвращена в план|на паузе)|^фаза \d+ раньше запланированных"
    r"|^[\d.,L ]+ \S+ в работу — |^todo (?:\d+\.\d+|add|done|edit|move|drop)\b")  # `todo …`: v0.7–0.8 logged each TODO edit


def _draw_decisions(readme: str, journal: grammar.Journal) -> str:
    lines = readme.rstrip("\n").split("\n")
    start = next((i for i, ln in enumerate(lines) if ln == "## Decisions"), None)
    if start is None:
        return readme
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body, drawn_on = [], False
    for ln in lines[start + 1:end]:  # what el drew before goes; the agent's own lines stay as written
        if ln == DECISIONS_DRAWN_HEAD:
            drawn_on = True
            continue
        if drawn_on and ln.startswith("  - "):
            continue
        drawn_on = False
        body.append(ln)
    own = " ".join(" ".join(ln.split()) for ln in body).lower()
    picked = []
    for e in journal.entries:  # newest entry first; inside an entry the newest event is the last
        for ev in reversed(e.events):
            if ev.type != "DECISION" or EL_DECISION_RE.match(ev.text):
                continue
            # history, not pointers: a link of the journal becomes its name — README holds its links to F16, the journal
            # does not, and an old decision must not bring a dead link into the owner's page
            words = re.sub(r"\[([^\]]+)\]\([^)\s]+\)", r"\1", _event_words(ev))
            if " ".join(words.split()).lower() in own:  # the whole decision: a shared opening is not the same choice
                continue  # the agent wrote it into Decisions already
            picked.append(f"  - {e.date} · {words}")
            if len(picked) == DECISIONS_DRAWN:
                break
        if len(picked) == DECISIONS_DRAWN:
            break
    while body and body[-1] == "":
        body.pop()
    block = [DECISIONS_DRAWN_HEAD, *picked] if picked else []
    return "\n".join(lines[:start + 1] + body + block + ([""] if end < len(lines) else []) + lines[end:]) + "\n"


def _opened_line(journal: grammar.Journal, parsed) -> Optional[str]:
    """`opened: <date> — with the goal above`, or `— the goal then: «…»` once the Context goal is no longer the one the case
    opened with — drawn from the journal's first entry, never typed. The cold reader (2026-10-08): given a finished case's
    README alone, eleven of sixteen readers answered «not in the README» to «what did you ask for, and when»; with this
    line, two. The goal at opening is the journal's `дело открыто:` event, kept whole."""
    if not journal.entries:
        return None
    first = journal.entries[-1]  # entries run newest first
    ev = first.events[0] if first.events else None
    words = _event_words(ev) if ev is not None else ""
    opening = next((o for o in ("дело открыто: ", "проект открыт: ") if words.startswith(o)), "")  # case new · root mode
    then = words[len(opening):].strip() if opening else ""
    if not then:
        return first.date
    norm = lambda s: " ".join(s.split()).rstrip(".…")  # noqa: E731
    context = " ".join(ln.strip() for ln in parsed.sections.get("Context", []) if ln.strip() and not ln.startswith("- "))
    if norm(context).startswith(norm(then)):  # the whole goal: a cut would hide a rewrite past it (Codex, 2026-10-08)
        return f"{first.date} — with the goal above"
    return f"{first.date} — the goal then: «{then}»"


def _set_first_state_line(readme: str, prefix: str, value: str) -> str:
    """The `- <prefix>` line as the first line of `## State` — moved there if it stood elsewhere."""
    out, in_state = [], False
    for ln in readme.rstrip("\n").split("\n"):
        if ln.startswith("## "):
            in_state = ln == "## State"
            out.append(ln)
            if in_state:
                out.append(f"- {prefix}{value}")
            continue
        if in_state and ln.startswith(f"- {prefix}"):
            continue
        out.append(ln)
    return "\n".join(out) + "\n"


def _draw_waits(case: Path, readme: str, waits: List[str]) -> str:
    """The State line `- ждёт: [<case>](<case>/README.md)` for every nested case a phase waits for (F6) — drawn from
    TODO on every README write, like `progress:`, never typed (feedback 2026-09-30: written once as a bare name, it did
    not click, and the patch that removed it at the child's close removed every `ждёт:` line — the agent's own too).
    A drawn line keeps its place; one whose case no longer waits goes; a new one goes at the end of State. The bare
    name el wrote before 1.31.0 is el's line as well when it names a case of this one, and is drawn as a link."""
    root_mode = _is_project(case)
    kids = {k.name for k in order.child_cases(case, root_mode)}
    lines = readme.rstrip("\n").split("\n")
    out: List[str] = []
    drawn, in_state = set(), False

    def add_missing():
        k = len(out)
        while k > 0 and out[k - 1] == "":
            k -= 1
        out[k:k] = [f"- ждёт: {_case_link(w, root_mode)}" for w in waits if w not in drawn]
        drawn.update(waits)

    for ln in lines:
        if ln.startswith("## "):
            if in_state:
                add_missing()
            in_state = ln == "## State"
        elif in_state:
            m = grammar.DRAWN_WAIT_RE.match(ln) or OLD_WAIT_LINE_RE.match(ln)
            if m and (ln.startswith("- ждёт: [") or m.group(1) in waits or m.group(1) in kids):
                name = m.group(1)
                if name in waits and name not in drawn:
                    out.append(f"- ждёт: {_case_link(name, root_mode)}")
                    drawn.add(name)
                continue
        out.append(ln)
    if in_state:
        add_missing()
    return "\n".join(out) + "\n"


OLD_WAIT_LINE_RE = re.compile(r"^- ждёт: (\d{4}-\d{2}-\d{2}-[A-Za-z0-9-]+)$")  # the bare name `spawn` wrote before 1.31.0
OLD_PARENT_LINE_RE = re.compile(r"^- parent: ([^\s\[]+)( · .*)?$")


def _parent_line(case: Path, line: str) -> str:
    """The child's Links line about its parent, as a link to the parent's README (feedback 2026-09-30: the bare folder
    name did not click). The bare line el wrote before 1.31.0 is drawn as a link on the next write; anything else as is."""
    m = OLD_PARENT_LINE_RE.match(line)
    if not m or not store.is_case_dir(case.parent) or m.group(1) != case.parent.name:
        return line
    return f"- parent: [{m.group(1)}](../README.md){m.group(2) or ''}"


def _event_words(ev: grammar.Event) -> str:
    """An event as one line of words: the headline without its «there is a body» mark, then the body — the provenance
    lines el adds (`session: …`) left out. What README shows of the journal is the whole event, not a cut of it."""
    head = ev.text[:-2].rstrip() if ev.text.endswith(" …") else ev.text
    body = [b for b in ev.body if not b.startswith("session: ")]
    return " ".join([head, *body]).strip()


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
    _refresh_parents(case, out)


def _refresh_parents(case: Path, out: Outcome) -> None:
    """L5 (measured 2026-10-06: a child with three phases, its line at the parent still «no phases yet»): what a parent
    shows about a child is drawn from the child's README — and was drawn only when the parent itself was written, so the
    owner reading the parent's README read yesterday. Every write of a child's README now redraws its parents, up while
    something changes (a grandparent shows the parent's State, which a child's write leaves as it was). A parent whose
    README el cannot vouch for (a hand edit, a case from before el) is left to its own next write — a command in the
    child never rebuilds a file in another case. The hand stays where the command wrote."""
    try:
        root = store.find_root(case)
    except StoreError:
        return
    child = case
    for _ in range(16):  # nesting is not bounded by the rules, a loop is (a link cycle is not a tree)
        parent = store.parent_case(child, root)
        if parent is None or parent == child:
            return
        try:
            text = store.read(parent, "README.md")
        except StoreError:
            return
        if not stamp.verify(text)[0]:
            return
        body, _ = stamp.split(text)
        derived = _derive_readme(parent, body)
        if derived == body:
            return
        try:
            store.write(parent, "README.md", derived)  # the parent's own warnings are its own, said at its own entry
        except StoreError:
            return
        child = parent


def _sync_progress(case: Path, todo: grammar.Todo, out: Outcome):
    _write_readme(case, _readme_text(case, out), out)


# the pointer el writes into a new case's State — el's own words, so el takes them down once they are done
DEFAULT_NEXT = 'open phase 1 — `el phase open 1 <Name> --goal "…"`'


def _say_default_next_down(had: bool, case: Path, out: Outcome) -> None:
    """A phase opened: el's own «next: open phase 1» is done and would read as the next step on every entry (L2: a sign
    «opening soon» left on an open shop). The render takes it down (`_derive_readme`) — only el's words, never a `next:` the
    agent wrote; this says so at the moment it happens."""
    if had and not _default_next_in_state(_readme_text(case)):
        out.say("State: el's own «next: open phase 1» is taken down — your next step in your words: el readme set next \"…\"")


def _default_next_in_state(readme_body: str) -> bool:
    parsed = grammar.parse_readme(readme_body)
    return not parsed.errors and f"- next: {DEFAULT_NEXT}" in parsed.sections.get("State", [])


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


ITEM_REF_RE = re.compile(r"(?<![\d.])(\d+)\.(\d+)(?:\.(\d+))?(?![\d.]*\d)")  # N.M or N.M.K (F25), not a version 1.20.0.1


def _named_refs(text: str, items: List[grammar.Item]) -> set:
    """The item numbers the text names among `items` (and their sub-items): `N.M`, and `N.M.K` only where that sub-item
    exists — a three-part number that names nothing here is a version (1.20.0), not a reference."""
    known = {x.ref for x in grammar.flat(items, cancelled=True)}
    found = set()
    for m in ITEM_REF_RE.finditer(text):
        ref = m.group(0) if m.group(3) else f"{m.group(1)}.{m.group(2)}"
        if ref in known:
            found.add(ref)
    return found


def _phase_by_refs(todo: grammar.Todo, text: str, out: Outcome, case: Optional[Path] = None) -> str:
    """The phase an event belongs to when `--phase` is not given: the one whose items the text names, else the
    phase in flight (feedback 2026-09-22: a RESULT about items 2.x landed under p1 because p1 was open — the
    journal then told the wrong story under the wrong phase). Items of several phases: the one in flight, said."""
    named = sorted({int(r.split(".")[0]) for r in _named_refs(text, [it for p in todo.phases if not p.done for it in p.items])})
    default = _phase_of(todo, case)
    if len(named) == 1 and f"p{named[0]}" != default:
        out.say(f"filed under p{named[0]}: the text names its item(s) — another phase: el log --phase N …")
        return f"p{named[0]}"
    if len(named) > 1:
        out.say(f"filed under {default} (in flight): the text names items of {', '.join(f'p{n}' for n in named)} — "
                f"another phase: el log --phase N …")
    return default


def _item_beside(case: Path, todo: grammar.Todo, phase: str, text: str) -> Optional[grammar.Item]:
    """The item in hand when a RESULT typed by the agent names no item of its running phase — None when it names one,
    or the phase is not running, or nothing in it is open (feedback 2026-10-02: an agent logged its steps as free
    RESULTs while TODO kept one coarse `[ ]` line — the work went on beside the plan, and nothing above the item moved;
    measured the same day on 19 live cases: 98 of 489 RESULTs were free ones logged before the next item ended)."""
    p = todo.phase(int(phase[1:])) if re.fullmatch(r"p\d+", phase) else None
    if p is None or p.done or not _phase_file(case, p.n, p.name).exists():
        return None
    if _named_refs(text, p.items):
        return None
    open_items = [it for it in p.items if not it.done]
    blocked = _blocking(case, todo)
    ready = [it for it in open_items if not it.held and f"{it.ref}" not in blocked]
    return (ready or open_items or [None])[0]


# The types agents reach for that the journal does not keep, and the door that does (the polygon, 2026-10-07: told «put
# your questions to me in the case», Haiku wrote `el log QUESTION`, was refused with the list alone and put the question
# into Decisions — a question is not a decision; Sonnet made a file of its own). A question is not an event until answered.
TYPE_DOORS = (
    ({"QUESTION", "QUESTIONS", "Q", "ASK", "OWNER", "ВОПРОС"},
     "a question to the owner is not an event until it is answered: it blocks an item → el todo hold N.M \"waiting for the "
     "owner: <question>\" (the entry names the wait) · it blocks nothing yet → el readme add problems \"question to the owner: "
     "<question>\" · the answer, when it comes → el log DECISION \"…\" and drop the line"),
    ({"NOTE", "NOTES", "INFO", "COMMENT", "ЗАМЕТКА"},
     "a note lives where it is needed: under an item → el todo note N.M \"…\" · on a phase → el phase note N \"…\""),
    ({"FACT", "FACTS", "ФАКТ"},
     "a fact is knowledge under the item it came from: el todo fact N.M \"…\" (el facts draws the chain)"),
)


def log(case: Path, typ: str, text: str, phase: Optional[str] = None, trailer: str = "", typed: bool = False) -> Outcome:
    """`trailer` — a provenance body line el adds under the event (`session: 1a2b3c4d` under a RESULT, F23): kept out of
    the headline, so the entry, which shows headlines only, does not change; dropped when the body is already full.
    `typed` — the agent wrote this event itself (`el log`), not a command on its behalf: only then a RESULT that no
    item carries is named at the moment it is written."""
    out = Outcome()
    typ = typ.upper()
    if typ not in grammar.JOURNAL_TYPES:
        door = next((d for words, d in TYPE_DOORS if typ in words), "")
        raise StoreError(f"unknown type `{typ}` — allowed: PHASE · DECISION · PROBLEM · RESULT (F8)" + (f"\n  {door}" if door else ""), 2)
    event_lines, split = _render_event(typ, text)
    if trailer and len(event_lines) - 1 < grammar.EVENT_BODY_LINES:
        event_lines = event_lines + [f"    {trailer}"]
    if not split and len(event_lines[0].strip()) > grammar.EVENT_WARN_CHARS:
        out.warn(f"event line is {len(event_lines[0].strip())} chars, close to the limit {grammar.EVENT_CHARS} (F7) — "
                 f"a line break in the text makes a body line")
    if split and "\n" in text.strip():
        out.warn(f"event written as a headline + {len(event_lines) - 1} body line(s): your line breaks are kept (F7)")
    elif split:
        out.warn(f"event longer than {grammar.EVENT_CHARS} chars — split into headline + {len(event_lines) - 1} body line(s) (F7)")
    todo = _todo(case, out)
    phase = _resolve_phase(todo, phase) if phase else _phase_by_refs(todo, text, out, case)
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
        if typed:
            hints.attach(out, "log", typ=typ, text=text, item=_item_beside(case, todo, phase, text))
    if typ == "PROBLEM":
        hints.attach(out, "log", typ=typ, text=text, project=_project_root(case))
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


CLAUSE_SEPS = (" — ", "; ", ": ", " · ", ", ")  # strongest boundary of meaning first
# links, code spans, autolinks, emphasis (* and _), entities, strikethrough — a split never falls between the first and the last;
# a snake_case word or «A & B» on both sides of a boundary costs the ready split, never a broken construct (Codex, 2026-10-05)
MARKUP_CHARS = "[]()`\\<>*_&~"


def _clause_cut(text: str, limit: int):
    """(head, rest, at_clause): the text cut at the last boundary of meaning that fits — a dash, `;`, `:`, `·`, `,` —
    else at a word (feedback 2026-09-22: a cut in the middle of a phrase, «не «следил за», cost two or three
    rounds per item). The head is a suggestion to rephrase from, the rest is context: a `note:`, never lost."""
    # a boundary is taken only outside the marked-up stretch — left of its first markup char or right of its last: every
    # link, code span, autolink and emphasis lies inside that stretch, so no split can cut one, whatever the escaping or
    # the title (Codex, 2026-10-05: four passes found markdown wider than any pattern; the guarantee is by construction)
    marks = [i for i, ch in enumerate(text) if ch in MARKUP_CHARS]
    marks += [m.end() - 1 for m in re.finditer(r"&#?\w+;", text)]  # an entity ends on its `;`, which is also a boundary
    marks.sort()
    lo, hi = (marks[0], marks[-1]) if marks else (len(text), -1)
    for sep in CLAUSE_SEPS:
        pos = text.rfind(sep, 0, limit + 1)
        while pos >= 0 and lo <= pos <= hi:
            pos = text.rfind(sep, 0, pos)
        if pos >= limit // 3:
            return text[:pos].rstrip(" ,;:·—"), text[pos + len(sep):].strip(), True
    cut = text.rfind(" ", 0, limit)
    cut = cut if cut > limit // 2 else limit
    return text[:cut].rstrip(), text[cut:].strip(), False


def _too_long(what: str, text: str, limit: int, rule: str) -> str:
    """The head of every length refusal — one voice at every door (feedback 2026-10-05: a note refused «when linking a
    doc» made the agent ask el to stop counting link targets, which never counted; the pocket refusal had not said so)."""
    names = sum(grammar.visible_len(m.group(0)) for m in grammar.LINK_RE.finditer(text))
    share = f" — {names} of them are link names: a short name keeps the link" if names else ""
    return f"{what} is {grammar.visible_len(text)} visible chars, limit {limit} ({rule}); markdown links count as their name{share}"


def _cut_loss(text: str, limit: int, why: str = "") -> str:
    """What a cut at the limit would drop, named instead of offered: a pocket has no second place for the rest, so a
    cut there is never whole (feedback 2026-10-05: the cut dropped the link a note exists for, ended a fact on «was»)."""
    text = " ".join(text.split())  # _short measures the normalized text — slice the same one
    kept = order._short(text, limit)
    lost = text[len(kept) - 1:].strip(" ,;:·—") if kept != text else ""
    over = grammar.visible_len(text) - limit
    if not lost:
        return f"  {over} over{why} — one token longer than the limit: rephrase around it"
    return f"  {over} over{why} — a cut at {limit} would lose «{order._short(lost, 40)}»" + (
        " (with its link)" if grammar.LINK_RE.search(lost) else "")


def _split_suggestion(text: str, add: str, note: str) -> str:
    """The refusal of a long item, with the rest kept: `add` is the command for the head, `note` the one for
    the rest — the agent's words move into the item's context pocket instead of being thrown away."""
    head, rest, at_clause = _clause_cut(text, grammar.TODO_ITEM_CHARS)
    if not at_clause:  # no boundary of meaning fits: the cut is not offered, the words it would drop are named
        # (a live report, 2026-10-02: the refusal printed the cut as `suggestion:` and «rephrase, do not truncate» under
        # it; the agent took the cut and lost a word of the claim — the printed line wins over the advice below it)
        return _cut_loss(text, grammar.TODO_ITEM_CHARS, " and no boundary of meaning to split at")
    if grammar.visible_len(rest) > grammar.POCKET_CHARS:  # the rest has no ready place: no head is offered without it
        return (f"  the rest after the boundary of meaning is too long for a note: a cut there would lose «{order._short(rest, 40)}» "
                f"— it goes to a file in the case, linked")
    if head.startswith("-") or rest.startswith("-"):  # argparse would take it for an option: the command would not run
        return _cut_loss(text, grammar.TODO_ITEM_CHARS, " and the split would start with `-`")
    quote = lambda t: "'" + t.replace("'", "'\\''") + "'"  # single quotes: the shell leaves `$` and `>` alone, `'` kept as typed
    return f"  suggestion — the item, the rest as its note: {add.replace('«head»', quote(head))} {note.replace('«rest»', quote(rest))}"


# ---- todo ---------------------------------------------------------------------------------------
EVIDENCE_KINDS_HELP = ("file:<path in the case or the project> (a photo, pdf, receipt, letter, screenshot, transcript, a source file) · "
                       "ref:<trace outside the case> (a request number, a URL, a letter in the mailbox) · "
                       "run:\"<command -> outcome>\" (a machine check; → or ->) · owner (the owner's word — the only word that counts)")


def _parse_evidence(case: Path, ref: str, token: str):
    """`file:evidence/x.jpg` → ("file", "[x.jpg](evidence/x.jpg)") · `ref:R000123` → ("ref", "R000123") ·
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
        example = {"file": "file:evidence/receipt.pdf", "ref": "ref:R000123-000001",
                   "run": "run:\"python3 -m unittest → 12 OK\""}[kind]
        raise StoreError(f"{kind}: needs a value — e.g. el todo done {ref} {example} \"what came out\"", 2)
    if kind == "file":
        m = re.fullmatch(r"\[[^\]]*\]\(([^)]+)\)", value)  # a link pasted whole is accepted; the path is what counts
        if m:
            value = m.group(1)
        if value.startswith(("/", "~")) or ".." in Path(value).parts:
            inside = _inside_project(case, value)  # the form wider, the canon inside (a live migration, 2026-10-07: a recipe
            if inside is None:                     # in .howto/ named from the case as ../../.howto/x.md was refused)
                raise StoreError(f"file: takes a path inside the case or the project, e.g. file:evidence/receipt.pdf or "
                                 f"file:src/app/parser.ts — `{value}` leads outside the project", 2)
            value = inside
        target = _evidence_file(case, value)
        if target is None:
            raise StoreError(f"file:{value} — no such file in the case or the project (paths are read from the case folder, "
                             f"then from the project root); put it there or name what you have: ref:<trace> · owner", 3)
        link = f"[{target.name}]({os.path.relpath(target, case)})"
        return kind, link + (f" · #{_fingerprint(target)}" if _versioned(case, target) else "")  # L8: the version done against
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


def _inside_project(case: Path, value: str) -> Optional[str]:
    """A path that climbs (`../../.howto/x.md`) or starts at `/` or `~`, read from the case folder: the project-relative
    path when it lands inside the project, else None."""
    try:
        p = Path(value).expanduser()
        p = (p if p.is_absolute() else case / p).resolve()
        return p.relative_to(_project_root(case).resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _pair_slots(slots: List[Tuple[str, str]], evidence: List[Tuple[str, str]]):
    """Each promised slot next to ITS proof: one proof of a kind fills one slot of that kind, in order (L5: two promised
    runs — the tests and the load test — were «2 of 2 filled» by one run, and both were shown against it). Returns
    [(kind, what, proof or None)] in the order of the slots."""
    left: Dict[str, List[str]] = {}
    for k, pr in evidence:
        left.setdefault(k, []).append(pr)
    return [(k, w, left[k].pop(0) if left.get(k) else None) for k, w in slots]


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
        paired = _pair_slots(slots, it.evidence)
        filled = [(k, w, pr) for k, w, pr in paired if pr is not None]
        missing = [(k, w) for k, w, pr in paired if pr is None]
        ref = f"{it.ref}"
        if missing:
            gap = " ".join(f"[{k}: {w}]" if w else f"[{k}]" for k, w in missing)
            out.say(f"expect {ref}: {len(filled)} of {len(slots)} filled — missing {gap}: the proof is short, or the expectation "
                    f"was wrong — say which: el todo done {ref} <kind> \"…\" adds a proof · el todo expect {ref} \"…\" corrects the promise")
            notes.append(f"{ref} expected {' · '.join(k for k, _ in slots)}, got {' · '.join(k for k, _ in it.evidence) or 'nothing'}")
        else:
            out.say(f"expect {ref}: {len(slots)} of {len(slots)} filled — {' · '.join(k for k, _ in slots)}")
        # the promise next to what arrived, in words — the tool matches kinds, the reader matches meaning
        # (feedback 2026-09-16: «HTTP 200 with benefits» filled a run slot that meant «discount applied»)
        for k, w, brought in filled:
            if w:
                out.say(f"  {_slot(k, w)} ← {k} {brought}".rstrip() + "  — does it show that?")
    return "; ".join(notes), out.lines


def _link_path(proof: str) -> str:
    """The path a proof points at — its link, without el's version mark (L8)."""
    proof = grammar.split_fingerprint(proof)[0]
    m = re.fullmatch(r"\[[^\]]*\]\(([^)]+)\)", proof)
    return m.group(1) if m else proof


_FINGERPRINTS: Dict[Tuple[str, int, int, int], str] = {}  # cleared by main.run: a file is hashed once per command


def _fingerprint(path: Path) -> Optional[str]:
    """The version of a file's content: the first 8 hex of its sha256. A line ending is not content — CRLF reads as LF,
    so a checkout with autocrlf on another machine does not read as a change. Streamed (a pdf is not loaded whole) and
    cached by path, size and mtime for the life of the command. None when the file cannot be read."""
    try:
        st = path.stat()
        key = (str(path.resolve()), st.st_size, st.st_mtime_ns, st.st_ctime_ns)
        if key not in _FINGERPRINTS:
            h, carry = hashlib.sha256(), b""
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    chunk = carry + chunk
                    carry, chunk = (b"\r", chunk[:-1]) if chunk.endswith(b"\r") else (b"", chunk)
                    h.update(chunk.replace(b"\r\n", b"\n"))
            h.update(carry)
            _FINGERPRINTS[key] = h.hexdigest()[:8]
        return _FINGERPRINTS[key]
    except OSError:
        return None


def _versioned(case: Path, target: Path) -> bool:
    """Which file proofs carry a version (the owner's word, 2026-10-02: «only the files of the case»): a document of
    the case — a letter, a note, a pdf, reviewed whole. Not a file of the project: source code lives on, its fixed version
    is a commit (`ref:`), its truth a run. Not a file el writes itself — the three case files of this case or a nested one,
    a phase file — or every write of el would read as a change of content. In root mode the project folder IS the case,
    so «inside the case» is everywhere: there the case's content is what el already counts as content (L4,
    order.content_folders) — a folder of a known kind (docs, evidence, letters …) or one that Links lists; code is not."""
    try:
        rel = target.resolve().relative_to(case.resolve())
    except ValueError:
        return False
    if _el_writes(case, target):
        return False
    if not _is_project(case):
        return True
    try:
        links = grammar.parse_readme(store.read(case, "README.md")).sections.get("Links", [])
    except (StoreError, OSError):
        links = []
    listed = {m.group(1).split("/")[0] for ln in links for m in [order.FOLDER_LINE_RE.match(ln)] if m}
    return len(rel.parts) > 1 and (rel.parts[0] in order.KNOWN_KINDS or rel.parts[0] in listed)


def _el_writes(case: Path, target: Path) -> bool:
    """A file el writes itself, found by its place, not its name: the three files of this case or of a case inside it, in
    any spelling a legacy case keeps (`journal.md`), and a phase file of either. A document that happens to be called
    README.md in docs/ is the author's (Codex's review of 2026-10-02: a basename rule hid it, and missed `journal.md`)."""
    t = target.resolve()
    owners = {case.resolve()} | {d for d in t.parents if store.is_case_dir(d)}
    names = {f.lower() for f in store.FILES}
    return any((t.parent == o and t.name.lower() in names) or t.parent == o / "phases" for o in owners)


def _changed_proofs(case: Path, todo: grammar.Todo, phases: Optional[List[grammar.Phase]] = None):
    """[(phase, item, path, the version done against, the version now)] — file proofs of done items whose content changed
    since `done` wrote their version (L8). Phases not closed only — a closed phase is history; the same set for every
    reader (entry, check, show, brief, accept, close). A file that is gone is a dead link, said by its own line; one that
    cannot be read is «unreadable» — not verified is not fresh; a proof without a version (before 1.35.0) is read as it was."""
    found = []
    for p in [p for p in (phases if phases is not None else todo.phases) if not p.done]:
        for it in grammar.flat(p.items):
            if not it.done:
                continue
            for kind, proof in it.evidence:
                link, was = grammar.split_fingerprint(proof)
                f = case / _link_path(link)
                if kind != "file" or not was or not f.is_file():
                    continue
                now = _fingerprint(f) or "unreadable"
                if now != was:
                    found.append((p, it, _link_path(link), was, now))
    return found


def _proof_owners(case: Path) -> List[Path]:
    """The case and every case above it up to the project: a parent may prove by a document inside its child, and el's
    rewrite in the child then touches the parent's proof too (Codex's review of 2026-10-02)."""
    top = _project_root(case).resolve()
    owners = [case]
    for d in case.resolve().parents:
        if d == top.parent:
            break
        if d != case.resolve() and store.file_path(d, "TODO.md").is_file():
            owners.append(d)
    return owners


def _fresh_proofs(case: Path, relocated: Optional[Tuple[Path, Path]] = None) -> List[Tuple[Path, set]]:
    """[(owner case, {(phase, item, k)})] — versioned file proofs whose file is still the version they were done against,
    in this case and the cases above it. Taken before el rewrites documents itself (`mv`, `relink`, `order --adopt`), so
    that afterwards el carries those versions along: a link rebased by el is not a change of content. `relocated` (old,
    new): a file renamed outside el, about to be relinked — its proof is checked against the bytes at the new place before
    el rewrites them. A proof already changed by its author is not in the set — el never launders it."""
    found = []
    for owner in _proof_owners(case):
        try:
            todo = _todo(owner)
        except StoreError:
            continue
        fresh = set()
        for p in todo.phases:
            for it in grammar.flat(p.items):
                for k, (kind, proof) in enumerate(it.evidence):
                    link, was = grammar.split_fingerprint(proof)
                    f = owner / _link_path(link)
                    if relocated is not None and not f.exists() and f.resolve() == relocated[0].resolve():
                        f = relocated[1]
                    if kind == "file" and was and f.is_file() and _fingerprint(f) == was:
                        fresh.add((it.ref, k))
        if fresh:
            found.append((owner, fresh))
    return found


def _carry_versions(fresh: List[Tuple[Path, set]], out: Outcome) -> None:
    """After el's own rewrite: every proof that was fresh before it carries the version of its file now (L8)."""
    for owner, keys in fresh:
        todo = _todo(owner, out)
        moved = False
        for p in todo.phases:
            for it in grammar.flat(p.items):
                for k, (kind, proof) in enumerate(it.evidence):
                    if (it.ref, k) not in keys:
                        continue
                    link, was = grammar.split_fingerprint(proof)
                    now = _fingerprint(owner / _link_path(link))
                    if now and now != was:
                        it.evidence[k] = (kind, f"{link} · #{now}")
                        moved = True
        if moved:
            out.absorb(_write_todo(owner, todo))


def _changed_moves(ref: str, path: str) -> str:
    return (f"this version is the proof: el todo done {ref} file:{path} \"what this version is\" (acceptance starts over) · "
            f"or el todo reopen {ref} \"why\"")


def _changed_line(p: grammar.Phase, it: grammar.Item, path: str, was: str, now: str) -> str:
    ref = f"{it.ref}"
    return (f"{ref} {path} changed since done (#{was} → now {'#' + now if now != 'unreadable' else now})" + (", accepted on the earlier version" if it.accepted else "")
            + f" → {_changed_moves(ref, path)}")


def _proof_warnings(phase: grammar.Phase, items: List[grammar.Item], proofs: List[Tuple[str, str]], out: Outcome):
    """What the tool can see about a proof without judging its truth (the owner's eye, 2026-09-16: a closed
    phase whose four items all pointed at one markdown the agent had written — the link resolved, the proof was
    hollow). Shown at the moment of writing, never refused: sometimes a case document IS the deliverable, and
    two items may honestly share one receipt."""
    named = ", ".join(f"{it.ref}" for it in items)
    for kind, proof in proofs:
        if kind != "file":
            continue
        path = _link_path(proof)
        if path.endswith(".md") and not path.startswith("../"):
            out.warn(f"file:{path} is a markdown inside the case — your own text, not the thing it describes. The proof is "
                     f"what stands behind it: run:\"<command → outcome>\" for a call or a test, file:<source or spec in the "
                     f"project> for code, file:<saved response, log, screenshot> for a result; keep the document as material")
        others = [f"{it.ref}" for it in grammar.flat(phase.items) if it.done and it not in items
                  and any(k == "file" and _link_path(pr) == path for k, pr in it.evidence)]
        if others:
            out.warn(f"file:{path} already proves {', '.join(others)} — one file for {len(others) + len(items)} items: "
                     f"is it the artifact of each, or one report about all of them? items are cut by what they leave behind — "
                     f"one outcome with its own proof each; two items with one artifact were one item with steps in its notes")
    for it in items:
        for k, note in enumerate(it.notes, start=1):
            if _note_repeats_proof(note, proofs + list(it.evidence)):
                out.warn(f"{it.ref} note {k} only points at the proof file — a note carries a constraint or context, the proof "
                         f"line carries the file: el todo note {it.ref} --drop {k}")
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
    """The words of `done` are for the owner who was not in the session (feedback 2026-09-16: «Commit a1b2c3d4e5
    removed region == EU check and gutted update()» — a code trace where the owner wanted «why was it
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


def todo_done(case: Path, ref: str, tokens: List[str], outcome: str = "", fact: Optional[str] = None) -> Outcome:
    """Done with evidence (F20): `el todo done N.M <kind> [<kind> …] "what came out"` — the kinds come
    first (file:<path> · ref:<trace> · run:"<command → outcome>" · owner), several when the proof is several
    things; the outcome goes to the journal as `RESULT · N.M: <kinds> — …` and under the TODO line as
    `result: …` with one proof line per kind (F22). The tick, the words and the proofs are one write.
    Nothing to say? Then it was not done: `el todo cancel N.M "why"`. A second `done` on a done item ADDS
    evidence (the owner's word, 2026-09-15: several artifacts per item) and renews the words only when given —
    the door for items ticked before 1.5.0; no RESULT, since the tick is not new (2026-09-22)."""
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
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)
    gone = [it for it in items if it.cancelled]
    if gone:  # F25: a cancelled sub-item stays in sight, ended — done on it would be a second end
        raise StoreError(f"{gone[0].ref} is cancelled ({gone[0].cancel_reason}) — the path came back? el todo reopen {gone[0].ref} "
                         f"\"why it is open again\", then done", 4)
    for it in items:
        if not it.done and it.open_subs():
            _open_subs_refusal(it, f"el todo done {it.ref} …")
    fresh_items = [it for it in items if not it.done]
    if fresh_items and phase.n and _could_open(case, todo, phase):  # the door before the work, not after it (feedback 2026-10-05)
        opener = f"el phase open {phase.n}" + ("" if phase.summary else " --goal '<what it delivers>'")  # a plan without a goal needs one
        raise StoreError(f"phase {phase.n} {phase.name} is planned, not open — it can open now: {opener} "
                         f"(its file holds the goal and the digest), then el todo done {ref} … · adding items to the plan stays "
                         f"open; work that ends out of turn — beside a phase still running — closes from the plan", 4)
    if all(it.done for it in items):  # a proof for an old tick: an edit of the record, not a new event
        return _attach_evidence(case, todo, phase, items, proofs, outcome, out)
    if not outcome:
        # the proof came, the words did not — said as such, and the command printed whole, each proof quoted (an agent's
        # report through `el feedback --wall`, pm-haiku-7, 2026-10-07: the refusal echoed a proof with spaces unquoted,
        # and the agent read it as a quoting error, not as the missing second argument)
        quoted = " ".join(t if re.fullmatch(r"[\w.:/@+-]+", t) else _sh(t) for t in tokens)
        raise StoreError(f"done needs what came out (F20) — the proof is here, the words are not: the outcome is a separate "
                         f"argument after the proof(s), in your words: el todo done {ref} {quoted} \"what came out\" — "
                         f"nothing came out? then it was not done: el todo cancel {ref} \"why\"", 2)
    # the `result:` line is el's (rendered from done) and it is whole: not counted in any limit, never cut (the owner's word,
    # 2026-09-25 — it reverses 2026-09-16, when el shortened it with «…»: the part cut off was lost to the owner reading TODO)
    shown_outcome = outcome
    fact = " ".join(fact.split()) if fact is not None else None
    expected_facts = [it for it in items if it.fact and not it.done]
    if expected_facts and fact is None:  # an expected fact asks for its verdict: confirmed, changed, or none
        it0 = expected_facts[0]
        raise StoreError(f"{it0.ref} expected the fact «{it0.fact}» — what is established now? "
                         f"el todo done {ref} {' '.join(tokens)} \"{outcome}\" --fact confirmed · --fact \"the fact as it turned out\" · "
                         f"--fact - (no fact came out)", 2)
    if fact is not None and fact.lower() not in ("confirmed", "same") and fact not in FACT_NONE:
        fact = _pocket_text("fact", fact, ref)
    _proof_warnings(phase, items, proofs, out)
    already = [it for it in items if it.done]
    fresh = [it for it in items if not it.done]
    blocking = _blocking(case, todo)
    done_now = {f"{it.ref}" for it in fresh}
    was = {f"{it.ref}": (list(it.evidence), it.result) for it in already}
    signed = f"{_sign_text(case)} · {_now()[0]}"
    for it in fresh:
        it.done, it.held, it.hold_reason = True, False, ""
        it.evidence = list(proofs)
        it.done_by = signed  # L8: who did it, on the item itself — read later, never guessed from the journal
    renewed = [it for it in already if _merge_proofs(case, it, proofs)]  # L8: the same door as a done on done items
    taken = _hand_taken(case, renewed)
    for it in renewed:
        it.done_by = signed  # a new version is a new claim, and this hand made it
    owed_again = [it for it in renewed if it.accepted]
    for it in owed_again:
        it.accepted = ""
    fact_note = ""
    for it in items:
        it.result = shown_outcome
        if fact is not None:
            if fact.lower() in ("confirmed", "same"):
                fact_note = f" · fact confirmed: {it.fact}" if it.fact else ""
            elif fact in FACT_NONE:
                fact_note = " · no fact" if it.fact else ""
                it.fact = ""
            else:
                fact_note = f" · fact: {fact}"
                it.fact = fact
    out.absorb(_write_todo(case, todo))
    refs = _refs(phase, items)
    shown = " · ".join(f"{k} {pr}".strip() for k, pr in proofs)
    short, expect_lines = _expect_check(phase, items)
    sid = session_id()
    out.lines += log(case, "RESULT", f"{refs}: {shown} — {outcome}" + (f" ({short})" if short else "") + fact_note, f"p{phase.n}",
                     trailer=f"session: {sid}" if sid else "").lines
    if not _sign_fields(case)[1] and hints.enabled():
        out.say(_sign_hint())
    for it in fresh:
        left = [r for r, _ in blocking.get(f"{it.ref}", []) if r not in done_now]
        if left:
            out.warn(f"{it.ref} was after {', '.join(left)}, still open — was the dependency wrong, or the order?")
    if len(fresh) == 1:
        out.say(f"done: {_refs(phase, fresh)} {fresh[0].text} → TODO.md (result + {len(proofs)} proof line(s)) · RESULT in the journal · evidence: {shown}")
    elif fresh:
        out.say(f"done: {_refs(phase, fresh)} ({len(fresh)} items) → TODO.md · one RESULT in the journal · evidence: {shown}")
    out.say(*expect_lines)  # after `done:` — the promise, then what arrived
    for it in items:
        if it.fact:
            out.say(f"  fact {it.ref}: «{it.fact}» — established; it enters the chain: el facts")
    hints.attach(out, "todo_done", items=items, proofs=proofs)
    if owed_again:
        out.say(f"new version recorded for {_refs(phase, owed_again)} → acceptance starts over: el todo brief {owed_again[0].ref} "
                f"— the old verdict stays in the journal")
    out.say(*taken)
    for it in already:
        ev0, words0 = was[f"{it.ref}"]
        before = " · ".join(f"{k} {pr}".strip() for k, pr in ev0) or "untyped"
        renewed = f"result renewed (was: «{words0}»)" if words0 and words0 != outcome else "result kept"
        out.say(f"{it.ref} was already done — evidence now: "
                f"{' · '.join(f'{k} {pr}'.strip() for k, pr in it.evidence)} (was: {before}) · {renewed} · RESULT in the journal")
    return out


ACCEPT_WORD_RE = re.compile(r"приёмк|приемк|принять|принят[ьоаы]|\baccept", re.I)
ACCEPT_WHO_RE = re.compile(r"рук|hand|сесси|session|субагент|subagent|\b\d+\.\d+", re.I)


def acceptance_as_text(case: Optional[Path], text: str) -> str:
    """Acceptance written as words of the plan — an item «accept 1.1–1.3 with a clean hand, not this session», a goal
    slot «[owner: acceptance by a clean hand]» — is a wall nobody can pass (the live migration of 2026-10-07: the rule
    «two hands» was lost, agents rebuilt it as text, and four fresh sessions in a row read «not this session» as
    themselves). el does not judge meaning; a word of acceptance next to a hand, a session or an item number is narrow
    enough to name the door (the owner's word, 2026-10-08)."""
    if case is None or not text or not (ACCEPT_WORD_RE.search(text) and ACCEPT_WHO_RE.search(text)):
        return ""
    line = ("acceptance written as text reads as a wall: every next session takes «not this session» for itself, and an "
            "[owner] slot waits for the owner alone. Acceptance is not an item — the second hand runs el todo accept N.M "
            "over the done item (el todo brief N.M prints its task) — el help acceptance")
    if not _case_two_hands(case):
        line += (" · this case has no rule «two hands»: one Context line switches it on — el readme add context "
                 f"\"{RULE_TWO_HANDS}\"")
    return line


def _hand_taken(case: Path, items) -> List[str]:
    """A new version signed by another session than the one that did the item names what it costs (the live migration of
    2026-10-07: each fresh session improved the map, recorded the new version and so became its doer — and none came
    only to check, so the acceptance never happened). The words are said before the item is re-signed."""
    if not _case_two_hands(case):
        return []
    sid = session_id()
    lines = []
    for it in items:
        m = re.search(r"\bsession (\S+)", it.done_by or "")
        if sid and m and m.group(1) != sid[:len(m.group(1))]:
            lines.append(f"{it.ref}: this version is signed by this session — it was session {m.group(1)}'s; you are its "
                         f"doer now, and its acceptance is another hand's: a fresh session or a clean-context subagent "
                         f"(el todo brief {it.ref}). Came only to check? A version you did not make is still a new claim — "
                         f"say so in the words, and leave the acceptance to the next hand")
    return lines


def _open_subs_refusal(it: grammar.Item, then: str) -> None:
    """F25: an item is assembled from its sub-items, as a phase from its items — it ends only when each of them has ended.
    The refusal names each open one and both of its ends."""
    left = it.open_subs()
    named = ", ".join(f"{s.ref} ({'on hold' if s.held else 'open'})" for s in left)
    s0 = left[0].ref
    raise StoreError(f"{it.ref} rests on its sub-items — {named}: end each first — el todo done {s0} <kind> \"what came out\" · "
                     f"el todo cancel {s0} \"why it is no longer needed\" — then {then}", 4)


def _merge_proofs(case: Path, it: grammar.Item, proofs) -> Optional[Tuple[str, str, str]]:
    """Put `proofs` onto a done item: one proof line per file — the same file replaces its line (and any duplicate the item
    carries), another kind or file is added. A version is never dropped silently: when the line had one and the new proof
    has none (the file moved where el gives no version), the version is kept by hashing the file. Returns (path, was, now)
    when the file came in another version — a new claim (L8; Codex's review of 2026-10-02: a range mixing an open and a
    done item appended a second line of the same file, and a proof without a version erased tracking and kept the
    acceptance)."""
    renewed = None
    for kind, proof in proofs:
        if kind != "file":
            if (kind, proof) not in it.evidence:
                it.evidence.append((kind, proof))
            continue
        path = _link_path(proof)
        same = [j for j, (k, pr) in enumerate(it.evidence) if k == "file" and _link_path(pr) == path]
        if not same:
            it.evidence.append((kind, proof))
            continue
        was = next((grammar.split_fingerprint(it.evidence[j][1])[1] for j in same if grammar.split_fingerprint(it.evidence[j][1])[1]), "")
        link, now = grammar.split_fingerprint(proof)
        if was and not now:
            now = _fingerprint(case / path) or "unreadable"
            proof = f"{link} · #{now}"
        it.evidence[same[0]] = (kind, proof)
        for j in reversed(same[1:]):
            del it.evidence[j]
        if was and now != was:
            renewed = (path, was, now)
    return renewed


def _attach_evidence(case: Path, todo: grammar.Todo, phase: grammar.Phase, items, proofs, outcome: str, out: Outcome) -> Outcome:
    """`done` on items that are already done: the proofs join theirs, the words are renewed only when given.
    No RESULT, `last:` untouched — the tick is not new, and the journal grows only from what changes the
    next reader's knowledge (P5; feedback 2026-09-22: kinds attached to six old ticks wrote six RESULTs,
    «the journal filled with bookkeeping»). The TODO lines carry the proofs; git keeps the edit."""
    _proof_warnings(phase, items, proofs, out)
    renewed = []  # L8: the same file in another version — a new claim, not a proof for an old tick
    befores = {}
    for it in items:
        befores[it.ref] = " · ".join(f"{k} {pr}".strip() for k, pr in it.evidence) or "untyped"
        r = _merge_proofs(case, it, proofs)
        if r:
            renewed.append((it, *r))
    if renewed and not outcome:
        it, path, was, now = renewed[0]
        raise StoreError(f"{it.ref}: a new version of {path} (#{was} → now #{now}) is a new claim — say what this version is: "
                         f"el todo done {it.ref} file:{path} \"what this version is\"", 2)
    for it in items:
        before = befores[it.ref]
        words = ""
        if outcome and outcome != it.result:
            words = f" · result renewed (was: «{it.result or '—'}»)"
            it.result = outcome
        out.say(f"{it.ref} was already done — evidence now: "
                f"{' · '.join(f'{k} {pr}'.strip() for k, pr in it.evidence)} (was: {before}){words}")
    if renewed:  # what was done, and maybe accepted, was other bytes: the new version is a RESULT, its acceptance starts over
        owed = [it for it, *_ in renewed if it.accepted]
        for it in owed:
            it.accepted = ""
        signed = f"{_sign_text(case)} · {_now()[0]}"
        taken = _hand_taken(case, [it for it, *_ in renewed])
        for it, *_ in renewed:
            it.done_by = signed  # L8: a new version is a new claim, signed by the hand that made it
        if not _sign_fields(case)[1] and hints.enabled():
            out.say(_sign_hint())
        out.absorb(_write_todo(case, todo))
        refs = ", ".join(sorted({it.ref for it, *_ in renewed}, key=lambda r: [int(x) for x in r.split(".")]))
        shown = " · ".join(f"{k} {pr}".strip() for k, pr in proofs)
        changes = "; ".join(f"{path} #{was} → #{now}" for _, path, was, now in renewed)
        sid = session_id()
        out.lines += log(case, "RESULT", f"{refs}: {shown} — {outcome} (new version: {changes})", f"p{phase.n}",
                         trailer=f"session: {sid}" if sid else "").lines
        out.say(f"new version recorded: {refs} ({changes}) → TODO.md · RESULT in the journal"
                + (f" · acceptance starts over: el todo brief {owed[0].ref} — the old verdict stays in the journal" if owed else ""),
                *taken)
        return out
    out.absorb(_write_todo(case, todo))
    out.say("→ TODO.md · no journal event: the tick is not new, only its proof (the words stay unless you give new ones)")
    out.say(*_expect_check(phase, items)[1])  # the promise, then what is attached now
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
    """Every live node of TODO — items and their sub-items (F25); a cancelled sub-item is gone from the work like a
    cancelled item, it only stays in sight."""
    return [it for p in todo.phases for it in grammar.flat(p.items)]


def _find_cycle(todo: grammar.Todo) -> Optional[List[str]]:
    """A cycle among `after` edges between items, as a path; None when the graph is a DAG."""
    graph = {it.ref: [r for r in it.after if re.fullmatch(grammar.ITEM_REF, r)] for it in _all_items(todo)}
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
    items = {f"{it.ref}" for it in _all_items(todo)}
    me = f"{item.ref}"
    clean: List[str] = []
    for ref in refs:
        if not grammar.AFTER_REF_RE.fullmatch(ref):
            raise StoreError(f"`{ref}` — after expects N.M or a nested case name (F19)", 2)
        if re.fullmatch(grammar.ITEM_REF, ref):
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
        # a sum, a version, a share, a time or a measure is not an item: `$1.27`, `v1.2`, `1.5%`, `16.09`, `16.639s` (the
        # polygon, 2026-10-07: a run's cost «$1.27» made the next item of phase 1 «1.28»; a time «сбой 16.09» in a
        # headline made the next item of phase 16 «16.10» — an item number never starts with 0 and never runs into a unit)
        pat = re.compile(rf"(?<![\w.$€£₽]){phase.n}\.(?!0)(\d+)(?![0-9A-Za-z.%])")  # «2.5проверен» is 2.5 (Codex)
        for e in journal.entries:
            for ev in e.events:
                for m in pat.finditer(ev.text):
                    used.add(int(m.group(1)))
    return max(used, default=0) + 1


def _blocking(case: Path, todo: grammar.Todo) -> Dict[str, List[Tuple[str, str]]]:
    """item key → [(ref, 'open' | 'case open' | 'gone')] for open items with unsatisfied `after`."""
    items = {f"{it.ref}": it for it in _all_items(todo)}
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
            out[f"{it.ref}"] = blockers
    return out


def _unblocked_line(case: Path, todo: grammar.Todo) -> Optional[str]:
    """Printed on entry only when the case declares dependencies: open items whose blockers are all
    done, ordered by due date then position — candidates, not the owner's `next:` (Codex: ready ≠
    what should happen next; never persisted into README)."""
    if not any(it.after for it in _all_items(todo)):
        return None
    blocking = _blocking(case, todo)
    open_items = [it for p in todo.phases if not p.done for it in p.items if not it.done and not it.held]
    ready = sorted((it for it in open_items if f"{it.ref}" not in blocking), key=lambda it: (it.due or "9999-99-99", it.n, it.m))
    blocked = [(it, blocking[f"{it.ref}"]) for it in open_items if f"{it.ref}" in blocking]
    shown = ", ".join(f"{it.ref} «{order._short(it.text, 40)}»" for it in ready[:6]) + (f" … +{len(ready) - 6}" if len(ready) > 6 else "")
    parts = [f"unblocked: {shown or 'none'}"]
    if blocked:
        parts.append("blocked: " + ", ".join(f"{it.ref} (after {', '.join(r for r, _ in bl)})" for it, bl in blocked[:6])
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


def _closed_words(readme_body: str) -> str:
    """A closed case's outcome as `done` recorded it: the `closed:` line without its date and el's acceptance tail."""
    parsed = grammar.parse_readme(readme_body)  # State only: a Context line «closed: …» is the agent's text (Codex, 2026-10-05)
    line = next((ln for ln in parsed.sections.get("State", []) if ln.startswith("- closed: ")), "") if not parsed.errors else ""
    if not line:
        return ""
    text = grammar.CLOSED_TALLY_RE.sub("", line[len("- closed: "):]).strip()
    return re.sub(r"^\d{4}-\d{2}-\d{2} · ", "", text)


def _closed_wait_lines(case: Path, todo: grammar.Todo) -> List[str]:
    """Order (L7): a phase waits for a nested case that is closed — the child's close was cut between its own record and
    this one (a killed process), so its outcome never landed here and the phase cannot close. The repair is the same
    door: `done` in the closed child delivers what it recorded, nothing in the child is written twice."""
    out = []
    children = {k.name: k for k in order.child_cases(case, _is_project(case))}
    for p in todo.phases:
        for name in ([] if p.done else p.waits):
            child = children.get(name)
            if child is None or order.child_status(child)[0] != "closed":
                continue
            words = _closed_words(store.read(child, "README.md"))
            path = child.relative_to(store.find_root(case)).as_posix()  # a path: one name may live under two parents
            out.append(f"phase {p.n} waits for {name}, and {name} is closed — its close never reached this case (cut off "
                       f"midway?) → el --case {path} done {_sh(words)} delivers its outcome here")
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
        raise StoreError(f"{_too_long(label + ':', text, grammar.POCKET_CHARS, 'F22')}\n"
                         f"{_cut_loss(text, grammar.POCKET_CHARS)}\n{POCKET_HINT}", 3)
    return text


REPHRASE_HINT = ("  rephrase, do not truncate: verb first, the path or flag stays, the filler goes — "
                 "«Trigger /v3/x, confirm FLAG=false in pod logs» is one action with its checkable outcome; "
                 "an opaque id (a hash, a generated entity id) is a trace, not words — name the thing, the id goes to a note")
POCKET_HINT = ("  rephrase, do not truncate: a pocket is one line that points at the context — the context itself goes to a "
               "file in the case, linked by a short name [trace](docs/trace.json); an opaque id (a hash, a generated entity "
               "id) is a trace, not words — it lives in that file, or in a ref: proof at done")
INTENT_HINT = ("  rephrase, do not truncate: the outcome first, the filler goes; the story goes into a phase note and the "
               "phase file once it opens")


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
    is proved when that item's own proof for that slot arrived (L5: one run no longer proves the item's two run
    slots, so it no longer proves two of the goal's). A bare kind (`[owner]`) is proved by a done proof of that kind
    the named promises did not use. Returns [(slot, status, ref)]: status ∈ proved · promised (item open) · uncovered."""
    slots = grammar.expected_kinds(goal)
    status: Dict[int, Tuple[str, str]] = {}
    used: Dict[str, int] = {}
    nodes = grammar.flat(phase.items)  # F25: a sub-item carries a criterion like an item — the beacon may sit one level down
    pairs = {it.ref: _pair_slots(grammar.expected_kinds(it.expect), it.evidence if it.done else []) for it in nodes}
    taken = set()  # (item, pair): one proof serves one goal slot — `[run: tests] [run: tests]` needs two (Codex, 2026-10-05)
    for i, (kind, what) in enumerate(slots):
        key = _slot_key(kind, what)
        if not key[1]:
            continue
        carriers = [it for it in nodes if key in {_slot_key(k, w) for k, w in grammar.expected_kinds(it.expect)}]
        free = next(((it, j) for it in carriers for j, (k, w, pr) in enumerate(pairs[it.ref])
                     if _slot_key(k, w) == key and pr is not None and (it.ref, j) not in taken), None)
        if free:
            taken.add((free[0].ref, free[1]))
            status[i] = ("proved", f"{free[0].ref}")
            used[kind] = used.get(kind, 0) + 1
        elif carriers:
            status[i] = ("promised", ", ".join(f"{it.ref}" for it in carriers))
        else:
            status[i] = ("uncovered", "")
    left: Dict[str, int] = {}  # a bare kind twice needs two done proofs of it (L5), beyond those the named ones took
    for it in nodes:
        for k, _ in (it.evidence if it.done else []):
            left[k] = left.get(k, 0) + 1
    for k, n in used.items():
        left[k] = left.get(k, 0) - n
    for i, (kind, what) in enumerate(slots):
        if i in status:
            continue
        ok = left.get(kind, 0) > 0
        if ok:
            left[kind] -= 1
        status[i] = ("proved" if ok else "uncovered", "")
    return [((kind, what), *status[i]) for i, (kind, what) in enumerate(slots)]


def _slot(kind: str, what: str) -> str:
    return f"[{kind}: {what}]" if what else f"[{kind}]"


def _cancelled(p: grammar.Phase) -> bool:
    """A phase ended by `phase cancel` — its line says «снято: <why>»; a result that merely begins with the word is not one."""
    return p.done and (p.summary or "").startswith("снято: ")


def _sh(text: str) -> str:
    """A value as the shell gets it back intact: single quotes, a `'` inside kept as typed."""
    return "'" + text.replace("'", "'\\''") + "'"


def _context_text(text: str) -> str:
    """A Context line at the write door (L6): free text, but a `[word: …]` in it is a promise and names a kind from the closed
    list — `[test: …]` or `[RUN: …]` would read as a promise el never counts. Links, code spans and a bracketed word without
    a colon (`[docs](…)`, `Status [ready]`) are text (Codex, 2026-10-05: the goal door refused them)."""
    text = " ".join(text.split())
    for m in _promise_slots(text, re.compile(r"\[([A-Za-z][\w-]*):[^\]]*\]")):
        if m.group(1) not in grammar.EVIDENCE_KINDS:
            low = m.group(1).lower()
            hint = f" — kinds are lowercase: [{low}: …]" if low in grammar.EVIDENCE_KINDS else ""
            raise StoreError(f"`[{m.group(1)}: …]` is not a kind of proof{hint} — a promise in Context is [file: what] · [ref: what] · "
                             f"[run: what] · [owner]; a kind that is missing: el feedback \"…\" · el help evidence", 2)
    return text


def _into_missing_phase(todo: grammar.Todo, to: str, ref: str) -> str:
    """A move into a phase that is not there names the whole way at once (feedback 2026-10-05: three refusals, one rule each);
    a closed phase takes nothing, and its number is taken — the way goes through the next free one (Codex, 2026-10-05)."""
    dest = todo.phase(int(to))
    n = max((p.n for p in todo.phases), default=0) + 1 if dest is not None else int(to)
    head = (f"phase {to} is closed — it takes no more work; into an open or planned phase, or a new one, the way in one go:"
            if dest is not None else f"phase {to} is not planned — the way in one go:")
    return (f"{head} el phase plan {n} '<English, 1–3 words>' --goal '<what it delivers, any language>' → el todo move {ref} {n} "
            f"→ el phase open {n} before the work on it")


def _could_open(case: Path, todo: grammar.Todo, phase: grammar.Phase) -> bool:
    """A planned phase (no file yet, not ended) whose previous phase has ended — `el phase open` would let it in now. The one
    test for both doors: `done` refuses work there and `phase close` refuses to close it from the plan; a planned phase
    behind a phase still running is out of turn, and its finished work closes from the plan (the owner's exit, 2026-09-14)."""
    if phase.done or _phase_file(case, phase.n, phase.name).exists():
        return False
    return not _open_blockers(case, todo, phase.n)


def _goal_line_index(lines: List[str]) -> Optional[int]:
    """Where the case goal sits in Context: the first line that is not blank and not a case rule (what `_context_goal` reads)."""
    return next((i for i, ln in enumerate(lines) if ln.strip() and not ln.strip().startswith("- rule:")), None)


CODE_SPAN_RE = re.compile(r"(?<![`\\])(`+)(?!`).*?(?<!`)\1(?!`)")  # CommonMark: a whole, unescaped run opens; as long a run closes
REF_LINK_RE = re.compile(r"\[[^\]]*\]\[[^\]]*\]")  # `[owner][signer]` — a reference link names its target elsewhere


def _promise_slots(line: str, pattern) -> List[re.Match]:
    """The slots of a Context line that are promises: not inside a code span (`` `[run: x]` `` quotes syntax) and not a link's
    name (`[owner](https://…)`) — while a code span INSIDE a slot (``[run: `make test` → OK]``) is part of it (Codex, 2026-10-05)."""
    quoted = [(m.start(), m.end()) for rx in (CODE_SPAN_RE, grammar.LINK_RE, REF_LINK_RE) for m in rx.finditer(line)]
    return [m for m in pattern.finditer(line) if not any(a <= m.start() < b and m.end() <= b for a, b in quoted)]


def _case_promises(readme_body: str) -> List[Tuple[Tuple[str, str], str]]:
    """The proofs the case promised in its Context (L6) — `[run: …] [file: …] [ref: …] [owner]` in the owner's goal or in
    any Context line but a case rule: [((kind, what), where)], `where` is how `el readme edit context` names the line —
    `goal`, a bullet's position, or "" for a plain line only a whole rewrite reaches."""
    parsed = grammar.parse_readme(readme_body)
    if parsed.errors:
        return []
    lines = parsed.sections.get("Context", [])
    gi = _goal_line_index(lines)
    bullets = [i for i, ln in enumerate(lines) if ln.startswith("- ")]
    out = []
    for i, ln in enumerate(lines):
        if ln.strip().startswith("- rule:"):
            continue
        where = "goal" if i == gi else (str(bullets.index(i) + 1) if i in bullets else "")
        out += [((m.group(1), (m.group(2) or "").strip()), where) for m in _promise_slots(ln, grammar.EXPECT_SLOT_RE)]
    return out


def _case_coverage(case: Path, todo: grammar.Todo, readme_body: str):
    """Each proof the case promised (L6) against its phases — the phase-level check (F12) one size up, the owner's word
    2026-10-05 («the expectation lives at every size of the node» was taught and checked by nothing): a promise with words
    is covered by a PHASE whose goal carries the same slot, and proved when that slot is proved inside the phase — by its
    items, the F12 count — not by the phase being closed (a goal edited after the close, a phase from before F12); a bare
    kind (`[owner]`) is proved by a done proof of that kind anywhere in the case. One carrier serves one promise; a
    cancelled phase carries nothing. Returns [(slot, where, status, phases)]: status ∈ proved · promised · uncovered."""
    promises = _case_promises(readme_body)
    if not promises:
        return []
    phases = [p for p in todo.phases if not _cancelled(p)]
    carriers: List[Tuple[Tuple[str, str], grammar.Phase, bool]] = []  # (key, phase, the slot proved in it)
    left: Dict[str, int] = {}
    for p in phases:
        items = _closed_phase_items(case, p) if p.done else p.items
        for it in grammar.flat(items):
            for k, _ in (it.evidence if it.done else []):
                left[k] = left.get(k, 0) + 1
        whole = grammar.Phase(p.n, p.name, p.done, p.line, p.summary, items)
        for (k, w), st, _ in _goal_coverage(whole, _phase_goal(case, p)):
            carriers.append((_slot_key(k, w), p, st == "proved"))
    results: Dict[int, tuple] = {}
    taken = set()
    for idx, ((kind, what), where) in sorted(enumerate(promises), key=lambda e: not e[1][0][1]):  # named first (Codex, 2026-10-05)
        key = _slot_key(kind, what)
        mine = [(i, p, ok) for i, (k, p, ok) in enumerate(carriers) if k == key and i not in taken]
        if not key[1] and not any(ok for _, _, ok in mine):  # a bare kind: any free proof of it, carried or not (Codex, 2026-10-05)
            ok = left.get(kind, 0) > 0
            if ok:
                left[kind] -= 1
            results[idx] = ((kind, what), where, "proved" if ok else "uncovered", "")
            continue
        pick = next(((i, p, ok) for i, p, ok in mine if ok), mine[0] if mine else None)
        if pick is None:
            results[idx] = ((kind, what), where, "uncovered", "")
            continue
        taken.add(pick[0])
        if pick[2]:
            left[kind] = left.get(kind, 0) - 1  # the proof under that carrier serves this promise and no other
        results[idx] = ((kind, what), where, "proved" if pick[2] else "promised", str(pick[1].n))
    return [results[i] for i in range(len(promises))]


def _near_promises(case: Path, todo: grammar.Todo, kind: str, what: str) -> str:
    """The slots of the same kind the phases did promise — the same promise in other words is the common case (a live case:
    «deploy green after each phase push» above, «deploy green» in every phase): shown side by side, the reader decides."""
    key = _slot_key(kind, what)
    seen = []
    for p in todo.phases:
        if _cancelled(p):
            continue
        for k, w in grammar.expected_kinds(_phase_goal(case, p)):
            if k == kind and _slot_key(k, w) != key and _slot(k, w) not in seen:
                seen.append(_slot(k, w))
    return " ".join(seen[:3])


def _promise_fix(where: str) -> str:
    if where:
        return f"el readme edit context {where} '…'"
    return "the line is plain text — rewrite README with it corrected: el readme --file <your edited copy>"


def _carry_command(n: int, slot: str) -> str:
    """The command that names a phase carrying a case promise — runnable as printed (Codex, 2026-10-05): shell-quoted, and a
    plan only while «… [slot]» fits a plan line; a longer slot goes in when the phase opens (its goal lives in its file)."""
    goal = f"… {slot}"
    if grammar.visible_len(goal) <= grammar.TODO_ITEM_CHARS:
        return f"el phase plan {n} 'Name' --goal {_sh(goal)}"
    return f"el phase open {n} 'Name' --goal {_sh(goal)} (longer than a plan line: it goes in at the opening)"


def _case_promise_lines(case: Path, todo: grammar.Todo, readme_body: str) -> List[str]:
    """Order (L6): a proof the case promised that no phase promises — the goal nobody works towards, shown while the case is
    open; `el done` refuses over it. The fix is a phase that carries the slot, or the promise corrected in the owner's words."""
    if grammar.is_closed(readme_body):
        return []
    lines = []
    free = max((p.n for p in todo.phases), default=0) + 1
    for (kind, what), where, status, _ in _case_coverage(case, todo, readme_body):
        if status != "uncovered":
            continue
        near = _near_promises(case, todo, kind, what)
        lines.append(f"the case promises {_slot(kind, what)} and no phase promises it — the goal nobody works towards: name the "
                     f"phase that proves it, {_carry_command(free, _slot(kind, what))} · or correct the promise: {_promise_fix(where)}"
                     + (f" (phases promise {near} — the same in other words? say it in theirs)" if near else ""))
    return lines


def _case_promise_hint(case: Path, todo: grammar.Todo, n: int, out: Outcome) -> None:
    """At the moment a phase gets its goal: the case's promises no phase carries yet, ready to copy — copied, the words match
    (L6: the case and its phases said the same thing in different words, and a word-for-word check could not see it)."""
    phase = todo.phase(n)
    carried = {_slot_key(k, w) for k, w in grammar.expected_kinds(_phase_goal(case, phase))} if phase else set()
    left = [_slot(k, w) for (k, w), _, st, _ in _case_coverage(case, todo, _readme_text(case)) if st == "uncovered"
            and _slot_key(k, w) not in carried]
    if left:
        out.say(f"the case promises {' '.join(left)} and no phase carries it yet — is it this one? copy the slot into its goal, "
                f"in the same words: the case closes when each of its promises is proved inside a phase")


def _phase_goal(case: Path, phase: grammar.Phase) -> str:
    """The goal of a phase where it lives: the phase file once open, the TODO intent while planned."""
    pf = _phase_file(case, phase.n, phase.name)
    if pf.exists():
        parsed = grammar.parse_phase_file(pf.read_text(encoding="utf-8"))
        if not parsed.errors:
            return parsed.goal
    return phase.summary or ""


def _running_phases(case: Path, todo: grammar.Todo) -> List[grammar.Phase]:
    """The phases in flight: open, with a phase file. The owner's word, 2026-09-17: a legacy case and its closed
    phases stay as they are — history is read, never nagged — but the phase you WORK in is not history: it is the
    write door itself, and it is held to the current form (goal with its promise, expect on every item, a kind on
    every tick). Nothing here touches closed phases."""
    return [p for p in todo.phases if not p.done and _phase_file(case, p.n, p.name).exists()]


def _untyped_running(case: Path, todo: grammar.Todo) -> List[Tuple[str, grammar.Item]]:
    return [(f"{it.ref}", it) for p in _running_phases(case, todo) for it in grammar.flat(p.items) if it.done and not it.evidence]


def _running_order_lines(case: Path, todo: grammar.Todo) -> List[str]:
    """Order for the phase in flight (the strict form applies where the work is): a goal that promises nothing,
    ticks without a kind. Closed phases are never listed here."""
    lines = []
    for p in _running_phases(case, todo):
        goal = _phase_goal(case, p)
        if p.items and goal and not grammar.expected_kinds(goal):  # work has started under a goal that promises nothing
            lines.append(f"phase {p.n} {p.name} (running): its goal promises no proof — what must be true when it closes? add "
                         f"[run: …] [file: …] [owner] to the goal line in phases/{_phase_file(case, p.n, p.name).name} (el help phases)")
    untyped = _untyped_running(case, todo)
    if untyped:
        shown = ", ".join(r for r, _ in untyped[:4]) + (f" … +{len(untyped) - 4}" if len(untyped) > 4 else "")
        lines.append(f"{len(untyped)} tick(s) without a kind of evidence in the running phase — {shown} → el todo done N.M <kind> "
                     f"attaches it — words kept, no journal event (F20: the running phase holds the current form; closed phases stay as they are)")
    lines += [_changed_line(*c) for c in _changed_proofs(case, todo)]  # L8: done against other bytes than lie there now
    return lines


def _expect_gap_lines(case: Path, todo: grammar.Todo) -> List[str]:
    """F22 (the owner's word, 2026-09-17): every item of a RUNNING phase says what work is expected and how it will
    be proved. Content, so shown: one line per phase, until every open item carries `expect:`."""
    lines = []
    for p in todo.phases:
        if p.done or not _phase_file(case, p.n, p.name).exists():
            continue
        gaps = [f"{it.ref}" for it in grammar.flat(p.items) if not it.done and not it.expect]
        if gaps:
            shown = ", ".join(gaps[:4]) + (f" … +{len(gaps) - 4}" if len(gaps) > 4 else "")
            lines.append(f"phase {p.n} {p.name}: {len(gaps)} open item(s) without expect: — {shown} → "
                         f"el todo expect N.M \"what work is expected [run: …] [file: …] [owner]\" (every item of a running phase says it, F22)")
    return lines


def _refuted_lines(todo: grammar.Todo) -> List[str]:
    """The fact chain (the owner's word, 2026-09-17): a done item resting (`after`) on an item that is open again
    or cancelled stands on a refuted fact — under question, never reopened by el: three exits."""
    by_ref = {f"{it.ref}": it for it in _all_items(todo)}
    lines = []
    for it in _all_items(todo):
        if not it.done or not it.after:
            continue
        shaky = [r for r in it.after if r in by_ref and not by_ref[r].done]
        if shaky:
            ref = f"{it.ref}"
            lines.append(f"{ref} «{order._short(it.fact or it.result or it.text, 50)}» rests on {', '.join(shaky)}, open again — a fact on a "
                         f"refuted one is under question: finish {shaky[0]} · or el todo reopen {ref} \"…\" · or el todo after {ref} <refs|none>")
    return lines


def _promise_lines(case: Path, todo: grammar.Todo) -> List[str]:
    """Order (F12): a proof the open phase promised in its goal that no item promises — the acceptance criterion
    nobody is working towards. Shown while the phase runs; the close refuses over it."""
    lines = []
    for p in todo.phases:
        if p.done or not _phase_file(case, p.n, p.name).exists():
            continue
        for (kind, what), status, ref in _goal_coverage(p, _phase_goal(case, p)):
            if status == "uncovered" and what:
                # the criterion is the beacon at the end; the way to it grows before it (feedback 2026-09-30: read as
                # «decompose everything now», while the steps to the probe were still to be found)
                lines.append(f"phase {p.n} {p.name} promises {_slot(kind, what)} and no item promises it — the criterion nobody works towards: "
                             f"name it as the phase's last item now, el todo add {p.n} \"…\" --expect \"{_slot(kind, what)}\"; the steps to it come "
                             f"as you find them, before it: el todo add {p.n} \"…\" --before {p.n}.K · or correct the goal line in phases/{_phase_file(case, p.n, p.name).name}")
    return lines


FACT_NONE = ("-", "—", "no", "none")
FACT_FROM_RESULT = "="  # `el todo fact N.M =` — the result's words, kept as the fact


def todo_fact(case: Path, ref: str, text: str) -> Outcome:
    """`el todo fact N.M "…"` — what this item is expected to establish (open) or has established (done): the
    line the fact chain is made of (the owner's word, 2026-09-17: a result is the work — «servers up, no errors»;
    a fact is what is now known and later work builds on — «in 3 DEV traces of checkout, no outbound
    pricing call» — bounded by what was observed). Not every item yields a fact: `-` says none. One per item; the journal keeps the old words."""
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    text = " ".join(text.split())
    if text == FACT_FROM_RESULT:  # the words of the result are the fact (2026-10-08): the cheapest honest answer at done
        if not item.done or not item.result:
            raise StoreError(f"`=` takes the words of {ref}'s result as its fact — {ref} has no result yet; "
                             f"say the fact: el todo fact {ref} '…'", 4)
        text = item.result
    old = item.fact
    item.fact = "" if text in FACT_NONE or not text else _pocket_text("fact", text, ref)
    out.absorb(_write_todo(case, todo))
    state = "established" if item.done else "expected"
    if item.fact:
        out.say(f"fact {ref} ({state}): «{item.fact}»" + (f" (was: «{old}»)" if old else "") + " → TODO.md")
        if item.done:
            out.lines += log(case, "RESULT", f"{ref}: fact — {item.fact}", f"p{phase.n}").lines
            # feedback 2026-10-05 asked the anchor to stay put; kept as the owner decided 2026-09-17 — a fact is a RESULT,
            # and said here, at the moment, instead of surprising the agent on the next `check`
            out.say("State: a fact is knowledge the next step stands on — read State again: still true → el readme touch "
                    "· changed → el readme set next \"…\" (at done, --fact rides the same RESULT)")
    else:
        out.say(f"fact {ref}: none" + (f" (was: «{old}»)" if old else "") + " → TODO.md")
    return out


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


def todo_show_all(case: Path) -> Outcome:
    """A bare `el todo` shows the plan of the case in hand (the live runs of 2026-10-07: three agents and the maintainer
    typed it to read the TODO and met a usage refusal, while a bare `el readme` shows the README). The last line is the
    door to write — the line a `tail -1` reader keeps."""
    out = Outcome()
    body, _ = stamp.split(store.read(case, "TODO.md"))
    out.say(body.rstrip("\n"), "",
            'write: el todo add N "…" · el todo done N.M <kind> "what came out" · one item\'s card: el todo show N.M — el help todo')
    return out


def phase_show(case: Path, n: int) -> Outcome:
    """`el todo show N` · `el phase show N` — one phase, the way a bare `el todo` shows the plan (the polygon, 2026-10-08:
    eighteen refusals «use N.M» on `el todo show 1`, and the maintainer typed `el phase show 18`). An open or planned
    phase: its lines of TODO; a closed or cancelled one: its folded line and its file, where its items and Digest live.
    Read-only; the last line is the door to one item."""
    out = Outcome()
    todo = _todo(case, out)
    phase = todo.phase(n)
    if phase is None:
        if not todo.phases:
            raise StoreError(f"no phase yet — open the first: el phase open 1 \"Name\" --goal \"…\"", 4)
        have = ", ".join(str(p.n) for p in sorted(todo.phases, key=lambda x: x.n))
        raise StoreError(f"no phase {n} in TODO.md (phases: {have}) — the whole plan: el todo", 4)
    body = stamp.split(store.read(case, "TODO.md"))[0].rstrip("\n").split("\n")
    start = phase.line - 1
    end = next((i for i in range(start + 1, len(body)) if body[i].startswith(("- [", "## ", "# "))), len(body))
    out.say(*body[start:end])
    pf = _phase_file(case, phase.n, phase.name)
    if phase.done and not pf.exists():  # history without its file: say so, never the door of an open phase (Codex)
        journal = _sh_path(_from_here(store.file_path(case, "JOURNAL.md")))
        out.say("", f"{pf.relative_to(case).as_posix()} is missing — the items of this closed phase lived there; its "
                    f"events stay in the journal: grep -n -A3 '· p{phase.n}$' {journal}")
        return out
    if phase.done:
        out.say("", f"— {pf.relative_to(case).as_posix()} —", *pf.read_text(encoding="utf-8").rstrip("\n").split("\n"))
        out.say("", "the whole plan: el todo · this phase is history — a step now goes to an open phase: el todo add N \"…\"")
    else:
        items = grammar.flat(list(phase.items))
        first = next((it for it in items if not it.done), items[0] if items else None)
        card = f"one item's card: el todo show {first.ref}" if first else f'its first item: el todo add {phase.n} "…"'
        out.say("", f"{card} · the whole plan: el todo — el help todo")
    return out


def todo_show(case: Path, ref: str) -> Outcome:
    """`el todo show N.M` — the item's card at the moment of picking it up: its pockets, and the inputs a chain
    hands it — the proofs of the items it comes after (F19) — and what it feeds in turn (the owner's sketch,
    2026-09-16: «сделал одно, пошёл к следующему»; Prove2Me: a proof imports the proved statements). Read-only."""
    out = Outcome()
    todo = _todo(case, out)
    mm = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", ref.strip())
    closed = todo.phase(int(mm.group(1))) if mm else None
    if closed is not None and closed.done:  # showing is reading: a closed phase's item is history, and history is shown
        # (the live map, 2026-10-08: a second hand asked `todo show 1.1` in a finished child and met the write refusal)
        want = tuple(int(g) for g in mm.groups() if g is not None)  # `01.01` is 1.1 (Codex)
        hist = next((it for it in grammar.flat(_closed_phase_items(case, closed), cancelled=True)
                     if tuple(int(x) for x in f"{it.ref}".split(".")) == want), None)
        if hist is not None:
            rel = _phase_file(case, closed.n, closed.name).relative_to(case).as_posix()
            out.say(f"phase {closed.n} {closed.name} (closed — history, kept in {rel})", *_item_block(hist, _case_two_hands(case)))
            out.say("", f"the whole phase: el todo show {closed.n} · new work on it is new work: el todo add later "
                        f"\"re-check {ref.strip()}: …\"")
            return out
    phase, item = _find_item(todo, ref)
    if phase.n == 0:
        out.say(f"general list (Later) · since {item.since or '—'} — the next phase boundary decides: el todo move {ref} N", *_later_block(item))
        return out
    state = "planned" if not _phase_file(case, phase.n, phase.name).exists() else "open"
    parent = _parent_of(phase, item)
    out.say(f"phase {phase.n} {phase.name} ({state})" + (f" · under {parent.ref} «{order._short(parent.text, 60)}»" if parent else ""),
            *_item_block(item, _case_two_hands(case), depth=1 if parent else 0))
    out.say(*(f"  {_changed_line(*c)}" for c in _changed_proofs(case, todo, [phase]) if c[1] is item))  # L8
    by_ref = {f"{it.ref}": it for it in _all_items(todo)}
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
    feeds = [f"{it.ref}" for it in _all_items(todo) if ref in it.after]
    if feeds:
        out.say(f"  → feeds {', '.join(feeds)}")
    back = _returns(_journal(case, out)).get(ref, [])
    if back:  # F23: every return is a reason in the journal — the next attempt starts from them
        out.say(f"  returned {len(back)} time(s), newest first: " + " · ".join(f"«{order._short(w, 60)}»" for w in back[:3]))
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


def _no_phase_for_add(todo: grammar.Todo, n: int) -> str:
    """Why `todo add N` has nowhere to go, and the door from each state (the polygon, 2026-10-07: Haiku and Sonnet sent
    items into phases they meant to plan next, read «phase 2 is missing or closed» and retried it three times — one line
    named two states and no way out). A missing phase is planned first; a closed one is history, the work goes on elsewhere."""
    free = max((p.n for p in todo.phases), default=0) + 1
    flight = todo.current()
    elsewhere = (f"el todo add {flight.n} \"…\" (phase {flight.n} {flight.name} is the one in flight)" if flight else "")
    later = "not for a phase yet: el todo add later \"…\""
    phase = todo.phase(n)
    if phase is not None:  # closed: its items are history
        doors = " · ".join(d for d in (elsewhere, f"a new phase: el phase plan {free} \"Name\" --goal \"…\"", later) if d)
        return f"phase {n} {phase.name} is closed — its items are history, nothing is added to it: {doors}"
    plan = (f"el phase plan {n} \"Name\" --goal \"…\", then this add" if n == free
            else f"phases are numbered in order and the next free number is {free}: el phase plan {free} \"Name\" --goal \"…\", "
                 f"then el todo add {free} \"…\"")
    return f"phase {n} does not exist yet — plan it first: {plan} (a planned phase takes items before it opens) · {later}"


def todo_add(case: Path, ref: str, text: str, before: Optional[str] = None, why: str = "", notes: Optional[List[str]] = None,
             expect: str = "", fact: str = "") -> Outcome:
    """Add item N.M (M = next free) to an open or planned phase N; `ref` is the phase number.
    The text may end with `— due: YYYY-MM-DD`. `before` = N.K puts it in place instead of at the
    end (feedback 2026-09-08: an item refused for length and re-added later landed last, and a
    batch of four cost four `move`s — the number is for life, the position is not)."""
    out = Outcome()
    if ref.strip().lower() in LATER_WORDS:
        return _add_later(case, text, before, why, notes, expect, fact)
    if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", ref.strip()):
        return _add_sub(case, ref.strip(), text, before, why, notes, expect, fact)
    if LATER_REF_RE.fullmatch(ref.strip()):
        raise StoreError(f"{ref.strip()} waits in the general list — it holds single thoughts, sub-items live under an item of a phase: "
                         f"el todo move {ref.strip()} N, then el todo add N.M \"…\" (F25)", 4)
    if not ref.isdigit():
        raise StoreError("use `el todo add N \"text\"` — N is the phase number; a sub-item under item N.M: el todo add N.M \"text\"; "
                         "not for this phase: el todo add later \"text\"", 2)
    todo = _todo(case, out)
    phase = todo.phase(int(ref))
    if phase is None or phase.done:
        raise StoreError(_no_phase_for_add(todo, int(ref)), 4)
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
        raise StoreError(f"{_too_long('item text', text, grammar.TODO_ITEM_CHARS, 'F13')}\n"
                         f"{_split_suggestion(text, 'el todo add ' + ref + ' «head»', '--note «rest»')}\n{REPHRASE_HINT}\n"
                         f"  (a re-added item takes the next free number at the END of the list — "
                         f"`el todo add {ref} \"…\" --before {phase.n}.K` puts it in place)", 3)
    m = _next_number(case, todo, phase)
    item = grammar.Item(phase.n, m, False, text, 0, due=due)
    if why:
        item.why = _pocket_text("why", why, f"{phase.n}.{m}")
    item.notes = [_pocket_text("note", n, f"{phase.n}.{m}") for n in (notes or [])]
    if expect:
        item.expect = _expect_text(expect, f"{phase.n}.{m}")
    if fact and fact.strip() not in ("-", "—", "no", "none"):
        item.fact = _pocket_text("fact", fact, f"{phase.n}.{m}")
    phase.items.insert(at, item)
    if after:
        _set_after(case, todo, item, after)
    out.absorb(_write_todo(case, todo))
    pockets = ((" · why" if item.why else "") + (f" · {len(item.notes)} note(s)" if item.notes else "") + (" · expect" if item.expect else "")
               + (" · expected fact" if item.fact else ""))
    out.say(f"added: {phase.n}.{m} {text}{f' — after: {chr(44).join(item.after)}' if item.after else ''}{f' — due: {due}' if due else ''}"
            f"{f' (before {before})' if before else ''}{pockets} → TODO.md")
    _remind_link(case, f"{phase.n}.{m}", _item_context(item), out)
    if not item.expect and _phase_file(case, phase.n, phase.name).exists():
        # the owner's word, 2026-09-17: every item of a running phase says what work is expected and how it will
        # be proved — content, so shown, not refused: a warning here, an Order line until it is there
        out.warn(f"{phase.n}.{m} has no expect: — every item of a running phase says what is expected and how it will be proved: "
                 f"el todo expect {phase.n}.{m} \"… [run: …] [file: …] [owner]\"")
    if item.expect:
        hints.attach(out, "todo_expect", item=item, phase=phase)
    else:
        hints.attach(out, "todo_add", item=item)
    return out


def _next_sub_number(case: Path, todo: grammar.Todo, parent: grammar.Item) -> int:
    """The next free K under item N.M (F25), by the rule of item numbers: above every sub-item present (a cancelled one
    too — it stays in sight), every `after` and every journal line that speaks of N.M.K — a number in use is never reused."""
    used = {s.k for s in parent.subs}
    pat = re.compile(rf"(?<![\d.]){parent.n}\.{parent.m}\.(\d+)(?![\d.]*\d)")
    for it in _all_items(todo):
        for r in it.after:
            m = pat.fullmatch(r)
            if m:
                used.add(int(m.group(1)))
    try:
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
    except StoreError:
        journal = None
    if journal is not None:
        for e in journal.entries:
            for ev in e.events:
                used |= {int(m.group(1)) for m in pat.finditer(ev.text)}
    return max(used, default=0) + 1


def _add_sub(case: Path, ref: str, text: str, before: Optional[str], why: str, notes: Optional[List[str]],
             expect: str, fact: str) -> Outcome:
    """`el todo add N.M "text"` → sub-item N.M.K under item N.M (F25; feedback and the owner's word, 2026-10-06): the
    probes of a question, the steps of a long item — each a node of the item's own shape, with its pockets, its proof
    and its end, shown under the item in the order taken. One level only: deeper is a nested case."""
    out = Outcome()
    todo = _todo(case, out)
    phase, parent = _find_item(todo, ref)
    if parent.k:
        raise StoreError(f"{ref} is a sub-item — sub-items stop one level down (F25): a step under it goes beside it "
                         f"(el todo add {parent.n}.{parent.m} \"…\"), work this deep is a nested case (el spawn \"name\" --goal \"…\")", 4)
    if parent.done:
        raise StoreError(f"{ref} is done — a new sub-item reopens the question: el todo reopen {ref} \"why the answer no longer "
                         f"holds\", then el todo add {ref} \"…\"", 4)
    text, due, after = _split_suffixes(text)
    at = len(parent.subs)
    if before:
        target = next((s for s in parent.subs if s.ref == before.strip()), None)
        if target is None:
            raise StoreError(f"--before {before}: no such sub-item under {ref} (sub-items: {', '.join(s.ref for s in parent.subs) or 'none'}) — "
                             f"drop --before to add at the end", 4)
        at = parent.subs.index(target)
    if grammar.visible_len(text) > grammar.TODO_ITEM_CHARS:
        raise StoreError(f"{_too_long('item text', text, grammar.TODO_ITEM_CHARS, 'F13')}\n"
                         f"{_split_suggestion(text, 'el todo add ' + ref + ' «head»', '--note «rest»')}\n{REPHRASE_HINT}", 3)
    k = _next_sub_number(case, todo, parent)
    sub = grammar.Item(parent.n, parent.m, False, text, 0, due=due)
    sub.k = k
    me = sub.ref
    if why:
        sub.why = _pocket_text("why", why, me)
    sub.notes = [_pocket_text("note", n, me) for n in (notes or [])]
    if expect:
        sub.expect = _expect_text(expect, me)
    if fact and fact.strip() not in ("-", "—", "no", "none"):
        sub.fact = _pocket_text("fact", fact, me)
    parent.subs.insert(at, sub)
    if after:
        _set_after(case, todo, sub, after)
    out.absorb(_write_todo(case, todo))
    pockets = ((" · why" if sub.why else "") + (f" · {len(sub.notes)} note(s)" if sub.notes else "") + (" · expect" if sub.expect else "")
               + (" · expected fact" if sub.fact else ""))
    out.say(f"added: {me} {text} — under {ref} «{parent.text}»{f' (before {before})' if before else ''}{pockets} → TODO.md · "
            f"{ref} ends when every sub-item has (done · cancel)")
    _remind_link(case, me, _item_context(sub), out)
    if not sub.expect and _phase_file(case, phase.n, phase.name).exists():
        out.warn(f"{me} has no expect: — every item of a running phase says what is expected and how it will be proved: "
                 f"el todo expect {me} \"… [run: …] [file: …] [owner]\"")
    hints.attach(out, "todo_expect" if sub.expect else "todo_add", item=sub, phase=phase)
    return out


def _next_later(case: Path, todo: grammar.Todo) -> int:
    """The next free number of the general list: above every line present and every `Lk` the journal speaks of."""
    used = {it.m for it in todo.later}
    try:
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
    except StoreError:
        journal = None
    for e in (journal.entries if journal is not None else []):
        for ev in e.events:
            # only the forms el writes — `снято L3 «…»`, `1.2 → L3` — not any `L<digits>` (found live, 2026-09-25: the
            # rule class L10 in this case's journal made the first line L11; a GPU «L4» would do the same)
            for a, b in re.findall(r"→ L(\d+)\b|\bL(\d+) «", ev.text):
                used.add(int(a or b))
    return max(used, default=0) + 1


def _later_refuse_suffixes(ref: str, due: str, after: List[str]):
    if due or after:
        raise StoreError(f"{ref}: a line of the general list waits for a phase — a date or a dependency belongs to an item of a phase: "
                         f"take it into one first (el todo move {ref} N), or plan the phase it needs (el phase plan N \"Name\")", 2)


def _add_later(case: Path, text: str, before: Optional[str], why: str, notes: Optional[List[str]], expect: str, fact: str) -> Outcome:
    """`el todo add later "…"` — a thought not for the running phase goes to the general list (F24; the owner's word,
    2026-09-25): one line with its number for life and the date, formed into a phase at the next boundary."""
    out = Outcome()
    todo = _todo(case, out)
    text, due, after = _split_suffixes(text)
    k = _next_later(case, todo)
    _later_refuse_suffixes(f"L{k}", due, after)
    if before:
        raise StoreError("--before is for items of a phase; the general list keeps the order thoughts came in", 2)
    if grammar.visible_len(text) > grammar.TODO_ITEM_CHARS:
        raise StoreError(f"{_too_long('line text', text, grammar.TODO_ITEM_CHARS, 'F13')}\n"
                         f"{_split_suggestion(text, 'el todo add later «head»', '--note «rest»')}\n{REPHRASE_HINT}", 3)
    item = grammar.Item(0, k, False, text, 0)
    item.since = _now()[0]
    ref = f"L{k}"
    if why:
        item.why = _pocket_text("why", why, ref)
    item.notes = [_pocket_text("note", n, ref) for n in (notes or [])]
    if expect:
        item.expect = _expect_text(expect, ref)
    if fact and fact.strip() not in FACT_NONE:
        item.fact = _pocket_text("fact", fact, ref)
    todo.later.append(item)
    out.absorb(_write_todo(case, todo))
    pockets = (" · why" if item.why else "") + (f" · {len(item.notes)} note(s)" if item.notes else "") + (" · expect" if item.expect else "")
    out.say(f"added: {ref} {text}{pockets} → TODO.md, the general list (Later) — the next phase boundary decides: "
            f"el todo move {ref} N takes it into a phase · el todo cancel {ref} \"why\" lets it go")
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
            out.warn(f"{it.ref}: this note only points at the item's proof file — a note carries a constraint or context; "
                     f"the proof line already carries the file: el todo note {it.ref} --drop {len(it.notes)}")
    out.absorb(_write_todo(case, todo))
    refs = _refs(phase, items)
    out.say(f"note added under {refs}: «{text}» → TODO.md" + (f" (note {len(items[0].notes)} of {ref})" if len(items) == 1 else ""))
    for it in items:
        _remind_link(case, f"{it.ref}", _item_context(it), out)
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


LATER_REF_RE = re.compile(r"[Ll](\d+)")
LATER_WORDS = ("later", "backlog", "pool", "general")
# what a line of the general list takes before it is in a phase: its words and its pockets — the rest (done, dates,
# dependencies, acceptance) belongs to items of a phase, so the refusal names the one move that makes it an item
LATER_ACTIONS = ("edit", "why", "note", "cancel", "drop", "move", "show")


def later_refusal(ref: str, action: str) -> Optional[StoreError]:
    """`el todo <action> Lk` for an action a Later line does not take: the refusal with the move that makes it an item."""
    if LATER_REF_RE.fullmatch(ref.strip()) and action not in LATER_ACTIONS:
        k = ref.strip()[1:]
        return StoreError(f"L{k} waits in the general list (Later, F24) — `{action}` is for items of a phase: take it into one first: "
                          f"el todo move L{k} N (then el todo {action} N.M …)", 4)
    return None


def _later_phase(todo: grammar.Todo) -> grammar.Phase:
    """The general list as a phase-shaped view (n = 0): the same list object, so removing from it removes from TODO."""
    return grammar.Phase(0, "Later", False, 0, items=todo.later)


def _closed_item_refusal(todo: grammar.Todo, phase: grammar.Phase, ref: str) -> str:
    """An item of a closed phase is history, and the refusal says so — not «no item» (an agent's report through
    `el feedback --wall`, the polygon, 2026-10-07: it re-checked 2.5 of a closed phase, wanted to add the proof, read
    «no item 2.5 in TODO.md» about an item it could see in the phase file, and tried twice). New work on old work is new
    work: an item where work runs now, naming the old one."""
    flight = todo.current()
    doors = ([f"el todo add {flight.n} \"re-check {ref}: …\" (phase {flight.n} {flight.name} is the one in flight; its "
              f"done carries the new proof)"] if flight else [])
    doors.append(f"not for a phase yet: el todo add later \"re-check {ref}: …\"")
    kind = "cancelled" if _cancelled(phase) else "closed"
    return (f"{ref} points into phase {phase.n} {phase.name}, {kind} — the items of a {kind} phase are history, kept in its "
            f"file under phases/; they take no new proof or tick. New work on one is new work: " + " · ".join(doors))


def _find_item(todo: grammar.Todo, ref: str):
    ml = LATER_REF_RE.fullmatch(ref.strip())
    if ml:
        item = next((it for it in todo.later if it.m == int(ml.group(1))), None)
        if item is None:
            have = ", ".join(f"L{it.m}" for it in todo.later) or "none"
            raise StoreError(f"no L{ml.group(1)} in the general list (lines: {have})", 4)
        return _later_phase(todo), item
    m = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", ref.strip())
    if not m:
        raise StoreError(f"`{ref}` — use N.M, e.g. 2.3 (a sub-item: N.M.K; a line of the general list: Lk; "
                         f"a whole phase: el todo show N)", 2)
    phase = todo.phase(int(m.group(1)))
    if phase is not None and phase.done:  # before «no item»: a closed phase folds to one line, its items are in its file
        raise StoreError(_closed_item_refusal(todo, phase, ref.strip()), 4)
    item = next((it for it in phase.items if it.m == int(m.group(2))), None) if phase else None
    if item is None:
        raise StoreError(f"no item {m.group(1)}.{m.group(2)} in TODO.md", 4)
    if m.group(3):  # F25: a sub-item under its item
        sub = next((s for s in item.subs if s.k == int(m.group(3))), None)
        if sub is None:
            have = ", ".join(s.ref for s in item.subs) or "none yet"
            raise StoreError(f"no sub-item {ref.strip()} in TODO.md (under {item.ref}: {have}) — a new one: el todo add {item.ref} \"…\"", 4)
        return phase, sub
    return phase, item


def _parent_of(phase: grammar.Phase, it: grammar.Item) -> Optional[grammar.Item]:
    """The item a sub-item sits under (F25); None for an item."""
    return next((p for p in phase.items if p.m == it.m), None) if it.k else None


def _done_parent_refusal(phase: grammar.Phase, it: grammar.Item, action: str) -> None:
    """F25: a done item is assembled from its sub-items — none of them changes its end under it. The way back first."""
    parent = _parent_of(phase, it)
    if parent is not None and parent.done:
        raise StoreError(f"{parent.ref} is done over its sub-items — {action} {it.ref} reopens the question: "
                         f"el todo reopen {parent.ref} \"why the answer no longer holds\", then {action} {it.ref}", 4)


def _select_items(todo: grammar.Todo, ref: str):
    """`N.M` · a range `N.A-N.B` (or `N.A-B`) · a list `N.A, N.B, …` → (phase, items in list order),
    one phase per call. A range takes the items that exist between A and B — numbers have gaps.
    Feedback 2026-09-09: rolling back a Pre-flight block meant six identical shell calls."""
    ref = ref.strip()
    ms = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)\s*[-–]\s*(?:(\d+)\.(\d+)\.)?(\d+)", ref)
    if ms:  # F25: a range of sub-items stays under one item
        n, mm, a, b = int(ms.group(1)), int(ms.group(2)), int(ms.group(3)), int(ms.group(6))
        if ms.group(4) is not None and (int(ms.group(4)), int(ms.group(5))) != (n, mm):
            raise StoreError(f"a range of sub-items stays under one item: `{n}.{mm}.{a}-{n}.{mm}.{b}`, not `{ref}`", 2)
        phase, parent = _find_item(todo, f"{n}.{mm}")
        subs = [s for s in parent.subs if a <= s.k <= b]
        if not subs:
            raise StoreError(f"no sub-items {n}.{mm}.{a}–{n}.{mm}.{b} under {parent.ref} "
                             f"(sub-items: {', '.join(s.ref for s in parent.subs) or 'none'})", 4)
        return phase, subs
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
            if it.ref not in seen:
                seen.add(it.ref)
                items.append(it)
        return pairs[0][0], items
    phase, item = _find_item(todo, ref)
    return phase, [item]


def _refs(phase: grammar.Phase, items) -> str:
    return ", ".join(_ref(phase, it) for it in items)


def _ref(phase: grammar.Phase, it: grammar.Item) -> str:
    """`N.M` for an item of a phase, `Lm` for a line of the general list (F24)."""
    return f"L{it.m}" if phase.n == 0 else it.ref


def todo_edit(case: Path, ref: str, text: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    text, due, after = _split_suffixes(text)  # a date or dependency kept in the item stays unless the new text carries one
    if phase.n == 0:
        _later_refuse_suffixes(ref, due, after)
    if after:
        _set_after(case, todo, item, after)
    if grammar.visible_len(text) > grammar.TODO_ITEM_CHARS:
        raise StoreError(f"{_too_long('item text', text, grammar.TODO_ITEM_CHARS, 'F13')}\n"
                         f"{_split_suggestion(text, 'el todo edit ' + ref + ' «head»', '&& el todo note ' + ref + ' «rest»')}\n{REPHRASE_HINT}", 3)
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
    pre = "L" if phase.n == 0 else f"{phase.n}."
    parts, i = [], 0
    while i < len(ms):
        j = i
        while j + 1 < len(ms) and ms[j + 1] == ms[j] + 1:
            j += 1
        parts.append(f"{pre}{ms[i]}" if i == j else f"{pre}{ms[i]}–{pre}{ms[j]}")
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
    if phase.n == 0:
        return _take_from_later(case, todo, item, to, out)
    if item.k:
        return _move_sub(case, todo, phase, item, to, out)
    if to.strip().lower() in LATER_WORDS:
        if item.subs:
            raise StoreError(f"{ref} carries sub-items ({', '.join(s.ref for s in item.subs)}) — the general list holds single "
                             f"thoughts: end or cancel them first, or move {ref} to another phase (el todo move {ref} K)", 4)
        return _put_to_later(case, todo, phase, item, out)
    if to.strip().isdigit():
        # to another phase: the item joins its end under the next free number there — the one time a
        # number changes, said aloud (feedback 2026-09-03: re-cutting a phase meant drop + add × 15)
        dest = todo.phase(int(to))
        if dest is None or dest.done:
            raise StoreError(_into_missing_phase(todo, to, ref), 4)
        if dest is phase:
            out.say(f"{ref} is already in phase {to} — nothing changed")
            return out
        phase.items.remove(item)
        old_subs = [s.ref for s in item.subs]
        item.n, item.m = dest.n, _next_number(case, todo, dest)
        for s in item.subs:  # F25: the sub-items go with their item and take its new number
            s.n, s.m = item.n, item.m
        dest.items.append(item)
        new = f"{item.ref}"
        renamed = {ref: new, **{o: s.ref for o, s in zip(old_subs, item.subs)}}
        followers = []
        for it in _all_items(todo):  # references follow the item, like links follow a moved file (F19)
            if set(it.after) & set(renamed):
                it.after = [renamed.get(r, r) for r in it.after]
                followers.append(f"{it.ref}")
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
    where = "last" if target is None else f"before {target.ref}"
    out.say(f"moved: {ref} now {where} — numbers never change; the phase list:", *_list_lines(phase))
    return out


def _move_sub(case: Path, todo: grammar.Todo, phase: grammar.Phase, sub: grammar.Item, to: str, out: Outcome) -> Outcome:
    """F25: a sub-item moves among its siblings (`before N.M.J` · `last`), or out from under its item — into a phase as an
    item of its own (`K`: the probe that grew), or to the general list (`later`). Its number is for life under its item;
    leaving the item is the one time it changes, said aloud, and every `after` pointing at it follows."""
    ref, parent, dest_word = sub.ref, _parent_of(phase, sub), to.strip().lower()
    _done_parent_refusal(phase, sub, "move")
    if sub.cancelled:
        raise StoreError(f"{ref} is cancelled ({sub.cancel_reason}) — it stays where it ended, as part of how {parent.ref} went; "
                         f"the path came back? el todo reopen {ref} \"why\", then move it", 4)
    if dest_word in ("last", "end") or re.fullmatch(r"\d+\.\d+\.\d+", to.strip()):
        target = None
        if dest_word not in ("last", "end"):
            target = next((s for s in parent.subs if s.ref == to.strip()), None)
            if target is None:
                raise StoreError(f"no sub-item {to.strip()} under {parent.ref} (sub-items: {', '.join(s.ref for s in parent.subs)}); "
                                 f"to put it last: el todo move {ref} last", 4)
            if target is sub:
                out.say(f"{ref} is already there — nothing changed")
                return out
        parent.subs.remove(sub)
        parent.subs.insert(len(parent.subs) if target is None else parent.subs.index(target), sub)
        out.absorb(_write_todo(case, todo))
        where = "last" if target is None else f"before {target.ref}"
        out.say(f"moved: {ref} now {where} under {parent.ref} — numbers never change:", *_item_block(parent)[0:1],
                *[_item_block(s, depth=1)[0] for s in parent.subs])
        return out
    if dest_word in LATER_WORDS or to.strip().isdigit():
        if dest_word in LATER_WORDS and sub.done:
            raise StoreError(f"{ref} is done — a done step stays under its item (its RESULT is the record); the general list "
                             f"holds what is still to do", 4)
        dest = None if dest_word in LATER_WORDS else todo.phase(int(to))
        if dest_word not in LATER_WORDS and (dest is None or dest.done):
            raise StoreError(_into_missing_phase(todo, to, ref), 4)
        parent.subs.remove(sub)
        sub.k = 0
        if dest is None:
            phase.items.append(sub)  # a moment's stop: _put_to_later takes it out of the phase into the general list
            return _put_to_later(case, todo, phase, sub, out, was=ref)
        sub.n, sub.m = dest.n, _next_number(case, todo, dest)
        dest.items.append(sub)
        new = sub.ref
        followers = []
        for it in _all_items(todo):
            if ref in it.after:
                it.after = [new if r == ref else r for r in it.after]
                followers.append(it.ref)
        out.absorb(_write_todo(case, todo))
        out.say(f"moved: {ref} → {new} «{sub.text}» (out from under {parent.ref}: an item of phase {dest.n} now, with its pockets"
                f"{' and its result' if sub.done else ''}; the number changes with the move)"
                + (f" · after-references rewritten in {', '.join(followers)}" if followers else ""))
        return out
    raise StoreError(f"a sub-item moves among its siblings — el todo move {ref} {parent.ref}.J (before J) · el todo move {ref} last — "
                     f"or out from under {parent.ref}: el todo move {ref} K (an item of phase K) · el todo move {ref} later", 2)


def _take_from_later(case: Path, todo: grammar.Todo, item: grammar.Item, to: str, out: Outcome) -> Outcome:
    """`el todo move Lk N` — a line of the general list becomes an item of phase N (planned or open) at the boundary."""
    ref = f"L{item.m}"
    if to.strip().lower() in LATER_WORDS:
        out.say(f"{ref} is already in the general list — nothing changed")
        return out
    if not to.strip().isdigit():
        raise StoreError(f"a line of the general list moves into a phase: el todo move {ref} N (N — a planned or open phase)", 2)
    dest = todo.phase(int(to))
    if dest is None or dest.done:
        raise StoreError(_into_missing_phase(todo, to, ref), 4)
    todo.later.remove(item)
    item.n, item.m, item.since = dest.n, _next_number(case, todo, dest), ""
    dest.items.append(item)
    out.absorb(_write_todo(case, todo))
    new = f"{item.ref}"
    out.say(f"taken: {ref} → {new} «{item.text}» (from the general list into phase {dest.n} {dest.name}; the number is its own now)")
    if not item.expect and _phase_file(case, dest.n, dest.name).exists():
        out.warn(f"{new} has no expect: — every item of a running phase says what is expected and how it will be proved: "
                 f"el todo expect {new} \"… [run: …] [file: …] [owner]\"")
    return out


def _put_to_later(case: Path, todo: grammar.Todo, phase: grammar.Phase, item: grammar.Item, out: Outcome, was: str = "") -> Outcome:
    """`el todo move N.M later` — an open item that is not for this phase goes to the general list with its pockets
    (a sub-item too, out from under its item — `was` is then its N.M.K)."""
    ref = was or f"{item.ref}"
    if item.done:
        raise StoreError(f"{ref} is done — a done item stays in its phase (its RESULT is the record); the general list holds what is "
                         f"still to do", 4)
    waiting = [f"{it.ref}" for it in _all_items(todo) if ref in it.after]
    if waiting:
        raise StoreError(f"{ref} is a dependency of {', '.join(waiting)} — rewire them first (el todo after N.M <refs|none>), "
                         f"then move it", 4)
    dropped = ([f"due {item.due}"] if item.due else []) + ([f"after {', '.join(item.after)}"] if item.after else []) \
        + (["hold"] if item.held else [])
    phase.items.remove(item)
    k = _next_later(case, todo)
    item.n, item.m, item.since = 0, k, _now()[0]
    item.due, item.after, item.held, item.hold_reason = "", [], False, ""
    todo.later.append(item)
    out.absorb(_write_todo(case, todo))
    out.say(f"moved: {ref} → L{k} «{item.text}» (to the general list; the next phase boundary decides: el todo move L{k} N)"
            + (f" · left behind: {', '.join(dropped)} — they belong to an item of a phase" if dropped else ""))
    return out


def todo_hold(case: Path, ref: str, reason: str, check: Optional[str] = None) -> Outcome:
    """An item that cannot be done now, and why: most often it waits for the outside — a ticket in another team's
    queue, an approval, a reply (feedback 2026-09-30: `[ ]` read «do me now», and a hold with no reason read «broken»).
    The reason is required, like cancel's and reopen's: a silent hold is the lie; the thread names it on entry.
    `--check "<command>"` (L4, a live wall 2026-09-30): the command that tells whether the wait is over — the next
    agent comes without memory and must be able to test the wall, not guess or ask. el never runs it; the entry names
    it. A hold again without `--check` keeps the command; `--check none` takes it away."""
    out = Outcome()
    reason = " ".join(reason.split())
    if not reason:
        raise StoreError(f"hold needs what the item waits for: el todo hold {ref} \"waiting for: ticket REQ-1 in the network "
                         f"team's queue\" — the thread names it on entry; it came → el todo resume {ref}", 2)
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    if item.done:
        raise StoreError(f"item {ref} is done — nothing to hold", 4)
    if item.cancelled:
        raise StoreError(f"{ref} is cancelled ({item.cancel_reason}) — the path came back? el todo reopen {ref} \"why\", then hold", 4)
    if check is not None:
        check = " ".join(check.split())
        if not check:
            raise StoreError(f"--check takes the command that tells the wait is over, or `none` to take it away: "
                             f"el todo hold {ref} \"…\" --check './check-port.sh'", 2)
        item.hold_check = "" if check.lower() in ("none", "-", "—") else check
    item.held, item.hold_reason = True, reason
    out.absorb(_write_todo(case, todo))
    test = (f"; is it over? `{item.hold_check}` — el never runs it, you do" if item.hold_check
            else f"; a command that tells it is over: el todo hold {ref} \"…\" --check '…'")
    out.say(f"on hold: {ref} — «{reason}»{test}; the entry's thread names the wait; it came → el todo resume {ref}")
    return out


def todo_reopen(case: Path, ref: str, why: str, by: Optional[str] = None) -> Outcome:
    """A tick taken back with a reason (feedback 2026-09-09: a database drift found at 22.2 sent
    22.1–22.6 back to open; `resume` only lifts a hold, so the agent edited the file and met the
    stamp). The RESULT logged at `done` stays — it is history — and a DECISION says it no longer
    holds. The item is open again: the phase cannot close over it, its dependents are blocked again.
    `--by <who>` — the return of an acceptor (F23): named in the DECISION with its session; every return counts
    towards «stuck» (three and Order says so)."""
    out = Outcome()
    why = " ".join(why.split())
    if not why:
        raise StoreError(f"reopen needs the reason: el todo reopen {ref} \"why the result no longer holds\"", 2)
    who = _acceptor(by, ref, "reopen") if by is not None else ""
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)  # a closed phase refuses: its items live in the phase file
    for it in items:  # F25: a sub-item comes back only under an item that is open — the answer above rested on it
        if it.k and it.ended:
            _done_parent_refusal(phase, it, "reopen")
    back = [it for it in items if it.cancelled]  # F25: a cancelled sub-item stays in sight, and so it can come back
    open_ = [it for it in items if not it.done and not it.cancelled]
    items = [it for it in items if it.done or it.cancelled]
    if open_:
        out.say(f"open already, nothing changed: {_refs(phase, open_)}"
                + (" (on hold — el todo resume)" if any(it.held for it in open_) else ""))
    if not items:
        return out
    tag = ""
    if who:
        journal = _journal(case, out)
        tag = f" (приёмка: {who} · {_session_word(_session_status(journal, phase, items[0], who), 'ru')})"
    for it in items:
        # the result, its proofs and its acceptance go with the tick; why/notes stay; the RESULT stays in the journal
        it.done, it.result, it.evidence, it.accepted, it.done_by = False, "", [], "", ""
        it.cancelled, it.cancel_reason = False, ""  # the reason it was cancelled stays in the journal
    out.absorb(_write_todo(case, todo))
    refs = _refs(phase, items)
    verb = "возвращён" if len(items) == 1 else "возвращены"
    out.lines += log(case, "DECISION", f"{refs} {verb} в работу — {why}{tag}", f"p{phase.n}").lines
    refuted = {f"{it.ref}" for it in items}
    resting = [it for it in _all_items(todo) if it.done and set(it.after) & refuted]
    if resting:  # the fact chain: what stands on the refuted item is under question — shown, never reopened by el
        out.say("  standing on it, done: " + ", ".join(f"{it.ref}" for it in resting)
                + " — a fact resting on a refuted one is under question; Order names them until you confirm, rewire or reopen (el facts)")
    what = f"{items[0].text}" if len(items) == 1 else f"({len(items)} items)"
    out.say(f"reopened: {refs} {what} → TODO.md · DECISION in the journal (the RESULTs stay as history)"
            + (f" · {', '.join(it.ref for it in back)} was cancelled — open again, the reason stays in the journal" if back else ""))
    return out


# ---- acceptance (F23) ----------------------------------------------------------------------------
# The owner's word, 2026-09-25 (synchronization over Anthropic's ART harness, 2026-09-23: 949 sessions, and no worker
# ever accepted its own task — a supervisor did): done by one hand, accepted by another. The other hand is a FRESH
# session — another chat, another agent, the same model with a clean context (ART ran one model throughout: the
# independence came from the clean context and the brief, not from another vendor). el launches nobody (the owner's
# word, 2026-09-22): it prints the brief (`el todo brief N.M`) and records the verdict — who, and whether the session was
# another. A self-acceptance passes only as the owner's word. Two errors, two guards (research/work-machine.md): the
# acceptor catches «done is not what was expected»; «expected is not what the owner meant» only the owner catches.
SESSION_ENVS = store.SESSION_ENVS
SESSION_WORDS = {"another": ("another session", "другая сессия"), "same": ("same session", "та же сессия"),
                 "subagent": ("clean-context subagent", "субагент с чистым контекстом"),
                 "mixed": ("sessions differ by item — see accepted: lines", "по-разному по пунктам — см. accepted:"),
                 "unknown": ("session not given", "сессия не указана"), "owner": ("the owner's word", "слово владельца")}
ACCEPTOR_RE = re.compile(r"[A-Za-z][\w.-]{0,23}")
RETURN_RE = re.compile(r"^(.+?) возвращ(?:ён|ены) в работу — ")
# three returns and the item is stuck — Order says so. ART stalled a task after ten revisions with no human in the loop;
# a case the owner leads sees the pattern sooner, and the line is shown, never refused (the number is a first guess,
# to be moved by a live case, like every limit here)
STALL_RETURNS = 3
RULE_TWO_HANDS_RE = re.compile(r"^\s*- rule:\s*two\s+hands\b", re.M | re.I)  # the name as _rule_key reads it
RULE_TWO_HANDS = "rule: two hands — the owner agrees each phase's scope, a fresh session accepts each done item"


session_id = store.session_id  # one reader of the harness's session id: the hand (store) and acceptance (F23)


def _sign_fields(case: Path) -> Tuple[str, str, str]:
    """(«Provider Tool», model, session) of the hand writing now — the harness's words and the agent's `el sign`."""
    return store.signature()


def _sign_text(case: Path) -> str:
    """`Anthropic Claude Code · Opus 5.5 · session 70cc2077` — the hand as a line; what nothing says is `?`, never guessed."""
    who, model, sid = _sign_fields(case)
    return f"{who or 'harness ?'} · {model or 'model ?'} · session {sid or '?'}"


def _sign_parse(line: str) -> Tuple[str, str, str]:
    """A signature line back into (who, model, session) — "" where it says `?`; a line el did not write gives ("", "", "")."""
    m = grammar.SIGN_LINE_RE.match(line or "")  # the same form the TODO door checks: what passes is what is read
    if not m:
        return "", "", ""
    clean = lambda v, q: "" if v in (q, "?") else v
    return clean(m.group("who"), "harness ?"), clean(m.group("model"), "model ?"), clean(m.group("sid"), "?")


def _engine_word(doer: str, acceptor: Tuple[str, str, str], lang: str = "en") -> str:
    """How independent the second hand is, by mind (the owner's word, 2026-10-05): another engine (another provider) ·
    another model · the same model — or why el cannot tell. The hand is the session; the mind is the model."""
    d_who, d_model, _ = _sign_parse(doer)
    a_who, a_model, _ = acceptor
    if not doer:
        word = ("doer not signed", "автор без подписи")
    elif not d_who or not a_who:  # independence el cannot see is not independence (Codex, 2026-10-05)
        word = ("harness not given", "среда не названа")
    elif not d_model or not a_model:
        word = ("model not given", "модель не названа")
    elif d_who.split()[0].casefold() != a_who.split()[0].casefold():
        word = ("another engine", "другой движок")
    elif d_model.casefold() != a_model.casefold():
        word = ("another model", "другая модель")
    else:
        word = ("same model", "та же модель")
    return word[0 if lang == "en" else 1]


def _sign_command(model: str = "<your model>", who: str = "") -> str:
    """The command that signs this session: `el sign '<model>'` — or, where the harness gives el no session id (VS Code
    Copilot, a terminal by hand), the same with a session named first. The signature is kept by the session, and a variable
    set for one command (`EL_SESSION=x el sign …`, the advice el printed until 1.40.1) is gone by the next `done` — the
    agent in Copilot followed el's advice into a refusal (the owner's word, 2026-10-06)."""
    as_ = f" --as '{who}'" if who else ""
    if store.session_id():
        return f"el sign '{model}'{as_}"
    return f"export EL_SESSION={secrets.token_hex(4)} && el sign '{model}'{as_}"


NO_SESSION = ("this harness gives el no session id: the export names one, and it holds while this terminal does — VS Code "
              "Copilot keeps its terminal between commands; a harness that opens a new shell for each one cannot, and done says "
              "`session ?` as it is")


def _sign_hint() -> str:
    return (f"el does not know your model — say it once per session: {_sign_command()} (provider, tool and session el takes "
            f"from the harness; the model goes into the done: and accepted: lines)" + ("" if store.session_id() else f" · {NO_SESSION}"))


def sign(model: Optional[str], who: Optional[str] = None) -> Outcome:
    """`el sign "Opus 5.5"` — this session says its model once (L8, the owner's word 2026-10-05: «provider, model and
    number»); the harness gives provider, tool and session. `--as "Provider Tool"` names a harness el does not know. Bare
    `el sign` shows the signature el would write now. Provenance, not proof: el records what it was told."""
    out = Outcome()
    if model is not None:
        model = " ".join(model.split())
        who = " ".join((who or "").split())
        if not model or "·" in model or "·" in who:  # the parts are el's to join: a `·` inside one would split it on reading
            raise StoreError("el sign \"<your model>\" — the model's name as your instructions give it, e.g. el sign \"Opus 5.5\"; "
                             "provider, tool and session el takes from the harness; no `·` inside a part", 2)
        if not store.session_id():  # the refusal carries the one command that works here, whole (2026-10-06)
            raise StoreError(f"{store.harness() or 'this harness'} gives el no session id, and el keeps the signature by the session — "
                             f"name this session once, in the terminal you keep working in: {_sign_command(model, who)} — the commands "
                             f"after it in that terminal carry the name; a variable set for one command (EL_SESSION=x el sign …) is "
                             f"gone by the next done", 4)
        store.sign(model, who)
    w, m, sid = store.signature()
    line = f"{w or 'harness ?'} · {m or 'model ?'} · session {sid or '?'}"
    out.say((f"signed: {line} — done: and accepted: lines carry it from now on" if model is not None
             else f"signature: {line} — what done: and accepted: lines would carry now"))
    if not m and hints.enabled():
        out.say("  " + _sign_hint())
    if not w:
        out.say(f"  el does not know this harness — name it: {_sign_command(m or '<model>', '<Provider Tool>')}")
    return out


def _session_word(status: str, lang: str = "en") -> str:
    return SESSION_WORDS[status][0 if lang == "en" else 1]


def _acceptor(by: Optional[str], ref: str, verb: str) -> str:
    """The one word naming who checked — codex · claude · gemini · subagent · owner. `self` is refused at accept."""
    by = (by or "").strip()
    if not by:
        raise StoreError(f"{verb} by whom? name the session that checked: el todo {verb} {ref} --by codex \"…\" "
                         f"(codex · claude · gemini · subagent · owner)", 2)
    if verb == "accept" and by.lower() in ("self", "me", "myself", "doer"):
        raise StoreError(f"a self-acceptance is not an acceptance (F23): a fresh session accepts — el todo brief {ref} prints its "
                         f"prompt (a new chat, another agent, a subagent with a clean context) — or the owner's word: "
                         f"el todo accept {ref} --by owner \"the owner's words, as said\"", 2)
    if not ACCEPTOR_RE.fullmatch(by):
        raise StoreError(f"--by takes one word naming who checked (codex · claude · gemini · subagent · owner), not `{by}`", 2)
    return by.lower()


def _result_names(text: str, ref: str) -> bool:
    """Does `RESULT · 2.1, 2.3: …` speak of `ref`? Only the refs before the first colon count."""
    head = text.split(":", 1)[0]
    return ref in re.findall(grammar.ITEM_REF, head)


def _doer_session(journal: grammar.Journal, phase: grammar.Phase, item: grammar.Item) -> str:
    """The session under the newest `done` RESULT of the item (the `session:` body line), "" when none was given."""
    if item.done_by:  # L8: the signature done wrote on the item — provenance by construction, not a reading of the text
        return _sign_parse(item.done_by)[2]
    ref = f"{item.ref}"
    for e in journal.entries:  # newest first
        for ev in e.events:
            if ev.type != "RESULT" or not _result_names(ev.text, ref) or re.match(r"^[^:]+: fact — ", ev.text):
                continue
            return next((b[len("session: "):].strip() for b in ev.body if b.startswith("session: ")), "")
    return ""


def _session_status(journal: grammar.Journal, phase: grammar.Phase, item: grammar.Item, who: str) -> str:
    if who == "owner":
        return "owner"
    mine, doer = session_id(), _doer_session(journal, phase, item)
    if not mine or not doer:
        return "unknown"
    if mine != doer:
        return "another"
    # the owner's word, 2026-10-07: «a subagent from the same session with a clean context, that knows nothing — that is a
    # clean hand». el cannot see the context, only the session: the kind is what the acceptor says, recorded as said
    return "subagent" if who == "subagent" else "same"


def todo_accept(case: Path, ref: str, text: str, by: Optional[str], runs: Optional[List[str]] = None) -> Outcome:
    """`el todo accept N.M --by codex "what was checked and how"` — the second hand (F23). Only a done item is accepted;
    the verdict goes under it as `accepted: <who> · <another session | same session | session not given | the owner's
    word> · <date>` (el's line) and into the journal as `DECISION · принято N.M: …`. The return is `el todo reopen N.M
    --by <who> "…"`. A range or a list takes one verdict for all."""
    out = Outcome()
    who = _acceptor(by, ref, "accept")
    text = " ".join(text.split())
    if who == "owner":  # the owner's word is recorded as the owner's words, quoted — not the agent's account of them
        text = _unwrap_quote(text)
    if not text:
        if who == "owner":
            raise StoreError(f"accept --by owner needs the owner's words, as said: el todo accept {ref} --by owner \"all good, close "
                             f"it\" — el writes them as a quote; one word for many items is one quote for them all (a range)", 2)
        raise StoreError(f"accept needs what was checked and how: el todo accept {ref} --by {who} \"re-ran the tests, opened the file: …\" — "
                         f"these words are what the owner reads instead of re-checking", 2)
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)
    _cancelled_refusal(items, "accept")
    open_ = [it for it in items if not it.done]
    if open_:
        raise StoreError(f"{_refs(phase, open_)} not done — nothing to accept yet; the doer ends it first: "
                         f"el todo done {open_[0].ref} <kind> \"what came out\"", 4)
    changed = [c for c in _changed_proofs(case, todo, [phase]) if c[1] in items]
    if changed:  # L8: the acceptor would sign bytes the doer never claimed — the doer records them first, or it goes back
        _, it, path, was, now = changed[0]
        raise StoreError(f"{it.ref} proof {path} changed since done (#{was} → now #{now}) — this is not the version the doer "
                         f"claimed: the doer records it: el todo done {it.ref} file:{path} \"what this version is\" · "
                         f"or return it: el todo reopen {it.ref} --by {who} \"why\"", 4)
    reruns = _reruns(ref, who, [pr for it in items for k, pr in it.evidence if k == "run"], runs or [])
    journal = _journal(case, out)
    date, _ = _now()
    statuses = [_session_status(journal, phase, it, who) for it in items]
    status = statuses[0] if len(set(statuses)) == 1 else "mixed"  # a range of two doers is said as such (Codex, 2026-10-05)
    mine_sign, mine_text = _sign_fields(case), _sign_text(case)
    engines = {_engine_word(it.done_by, mine_sign) for it in items}
    engine_ru = "" if who == "owner" else " · " + (_engine_word(items[0].done_by, mine_sign, "ru") if len(engines) == 1
                                                     else "по-разному по пунктам — см. accepted:")
    left, differs = list(reruns), []
    for it in items:  # the --run words go to the item proofs in order: each item counts its own re-runs
        proofs = [pr for k, pr in it.evidence if k == "run"]
        mine, left = left[:len(proofs)], left[len(proofs):]
        ran = [r for r in mine if not _outcome(r).startswith("not run")]
        tally = (f" · re-ran {len(ran)} of {len(mine)}" + (f" ({len(mine) - len(ran)} not run)" if len(ran) < len(mine) else "")
                 if mine else "")
        engine = "" if who == "owner" else f" · {_engine_word(it.done_by, mine_sign)}: {mine_text}"  # L8: the mind beside the hand
        it.accepted = f"{who} · {_session_word(_session_status(journal, phase, it, who))} · {date}{tally}{engine}"
        differs += [(it, pr, r) for pr, r in zip(proofs, ran) if _outcome(pr).casefold() != _outcome(r).casefold()]
    out.absorb(_write_todo(case, todo))
    refs = _refs(phase, items)
    body = "".join(f"\nre-run: {r}" for r in reruns[:4]) + (f"\nre-run: … +{len(reruns) - 4} more" if len(reruns) > 4 else "")
    said = f": «{text}»" if who == "owner" else f" — {text}"
    out.lines += log(case, "DECISION", f"принято {refs}: {who} · {_session_word(status, 'ru')}{engine_ru}{said}{body}", f"p{phase.n}").lines
    engine = "" if who == "owner" else " · " + (next(iter(engines)) if len(engines) == 1 else "differs by item — see accepted: lines")
    out.say(f"accepted: {refs} by {who} ({_session_word(status)}{engine}) → TODO.md (accepted: line) · DECISION in the journal")
    if who != "owner" and not mine_sign[1] and hints.enabled():
        out.say(_sign_hint())
    if "same" in statuses:
        out.warn(f"same session as the doer, and not said to be a subagent — recorded as the doer checking itself. A clean hand: "
                 f"a subagent with a clean context (hand it el todo brief {ref}; it accepts --by subagent), the next session, "
                 f"another agent, or the owner's word")
    elif "subagent" in statuses:
        out.say("  a subagent of the doer's session, recorded as you say: a clean context counts as a second hand (the owner's "
                "word, 2026-10-07) — the brief was all it knew")
    elif status == "unknown":
        out.say("  session not given — recorded as reported (EL_SESSION, or the harness's own session id, tells more)")
    for it, pr, r in differs:  # two records compared word for word, the meaning is the acceptor's — shown, not refused
        out.warn(f"{it.ref}: the doer's run came out «{_outcome(pr)}», yours «{_outcome(r)}» — a result that differs "
                 f"is a return: el todo reopen {it.ref} --by {who} \"now: {_outcome(r)}\" (the same thing in other words? "
                 f"then the acceptance stands)")
    return out


def _cancelled_refusal(items: List[grammar.Item], action: str) -> None:
    """F25: a cancelled sub-item ended with its reason — nothing was done, so nothing is accepted or briefed."""
    gone = [it for it in items if it.cancelled]
    if gone:
        raise StoreError(f"{gone[0].ref} is cancelled ({gone[0].cancel_reason}) — nothing was done, nothing to {action}; "
                         f"its reason is the record", 4)


def _unwrap_quote(text: str) -> str:
    """One quote pair that wraps the WHOLE text is taken off — el adds its own. `«yes» and «no»` is two phrases, not a
    wrapper, and stays as typed (the Codex review, 2026-09-29)."""
    for a, b in (("«", "»"), ("“", "”"), ('"', '"'), ("'", "'")):
        if len(text) < 2 or not (text.startswith(a) and text.endswith(b)):
            continue
        inner = text[1:-1]
        if a == b:
            return text if a in inner else inner.strip()
        depth = 0
        for ch in inner:
            depth += (ch == a) - (ch == b)
            if depth < 0:  # the first quote closed before the end: separate phrases
                return text
        return inner.strip() if depth == 0 else text
    return text


def _outcome(run: str) -> str:
    """What came out, the part after the arrow of `command → outcome`."""
    return " ".join(run.split("→", 1)[1].split()) if "→" in run else ""


def _reruns(ref: str, who: str, proofs: List[str], runs: List[str]) -> List[str]:
    """The second hand re-runs every `run:` proof and says what came out now (the owner's word, 2026-09-25: «the agent is
    the second hand — it runs the commands and says it worked»). el runs nothing itself (2026-09-22): it asks, one `--run`
    per proof, and records what was said — `→ not run: why` is an honest answer, counted as not re-run."""
    runs = [" ".join(r.replace("->", "→").split()) for r in runs]
    for r in runs:
        if "→" not in r:
            raise StoreError(f"--run takes the command and what came out now, joined by → or ->: --run \"{r} → <outcome now>\" "
                             f"(could not run it: --run \"{r} → not run: why\")", 2)
    if who == "owner" or len(runs) >= len(proofs):
        return runs
    missing = proofs[len(runs):]
    shown = " ".join(f'--run "{p.split("→")[0].strip()} → <what came out now>"' for p in missing)
    raise StoreError(f"{ref} stands on {len(proofs)} run proof(s): {' · '.join(proofs)} — the second hand re-runs each and says what "
                     f"came out now: el todo accept {ref} --by {who} {shown} \"what you checked\" (could not run one: "
                     f"--run \"<command> → not run: why\"; the owner's word needs none: --by owner)", 2)


def _context_goal(readme_body: str) -> str:
    """The case goal in the owner's words: the first Context line that is not a case rule."""
    parsed = grammar.parse_readme(readme_body)
    for ln in parsed.sections.get("Context", []) if not parsed.errors else []:
        t = ln.strip()
        if t and not t.startswith("- rule:"):
            return t[2:].strip() if t.startswith("- ") else t
    return ""


def _proof_for_brief(case: Path, kind: str, proof: str) -> str:
    """A proof as the acceptor meets it: a file by its path from the project folder, the rest as recorded."""
    if kind == "file":
        path = (case / _link_path(proof)).resolve()
        try:
            return f"file: {path.relative_to(_project_root(case).resolve())}  (open it)"
        except ValueError:
            return f"file: {path}  (open it)"
    if kind == "run":
        return f"run: {proof}  (re-run it and bring what came out now — el recorded it, nobody repeated it)"
    if kind == "ref":
        return f"ref: {proof}  (follow it if you can reach it)"
    return "owner  (the owner's word — ask the owner if it matters)"


def todo_brief(case: Path, ref: str) -> Outcome:
    """`el todo brief N.M` — the prompt for a FRESH session that accepts or returns the item (F23; the owner's word,
    2026-09-25: «no second agent here? print the prompt I paste into a new chat»). Drawn from the case, never typed:
    the case goal, the phase goal, the item with the owner's `why`, the promise written before the work (`expect`),
    what the doer says came out, the proofs as paths from the project folder, the inputs it rests on, and the two
    verdict commands. el prints; the owner or the agent's harness decides who runs it. Read-only."""
    out = Outcome()
    todo = _todo(case, out)
    phase, items = _select_items(todo, ref)
    _cancelled_refusal(items, "brief")
    open_ = [it for it in items if not it.done]
    if open_:
        raise StoreError(f"{_refs(phase, open_)} is open — a brief is for accepting done work; the doer ends it first: "
                         f"el todo done {open_[0].ref} <kind> \"what came out\"", 4)
    project = _project_root(case)
    readme_body = _readme_text(case)
    by_ref = {f"{it.ref}": it for it in _all_items(todo)}
    name = case.name
    # which hand is reading (the polygon, 2026-10-07: a fresh Haiku session ran `el todo brief`, read «for a FRESH
    # session, paste it», took the paste for someone else's job and left eleven items to «a separate session» — itself)
    mine = session_id()
    doers = {_sign_parse(it.done_by)[2] for it in items if it.done_by} - {""}
    if mine and doers and mine not in doers:
        reader = (f"done in session {', '.join(sorted(doers))}, you are another — this brief is YOUR task: do what is below "
                  f"the line yourself, then run one verdict.")
    elif mine and doers == {mine}:
        reader = ("done in this session — not yours to judge: paste everything below the line to a FRESH hand — a subagent "
                  "with a clean context (it answers --by subagent) or the next session.")
    else:
        reader = ("for a FRESH hand: another session, another agent, or a subagent with a clean context — paste everything "
                  "below the line.")
    out.say(f"brief · acceptance of {_refs(phase, items)} — {reader}", "---",
            "You accept or return work done in an Elephant case. You were not in the session that did it: judge by the things, "
            "not by the words.",
            f"project folder: {project}  ·  case: {os.path.relpath(case, project)}")
    goal = _context_goal(readme_body)
    if goal:
        out.say(f"case goal (the owner's words): {goal}")
    pgoal = _phase_goal(case, phase)
    out.say(f"phase {phase.n} {phase.name}: {pgoal or phase.summary or '(no goal)'}")
    changed = _changed_proofs(case, todo, [phase])  # once for the brief, not once per item
    for it in items:
        out.say(f"item {it.ref}: {it.text}")
        if it.why:
            out.say(f"  why (the owner's words): {it.why}")
        out.say(*(f"  note: {n}" for n in it.notes))
        anchor = "`why`" if it.why else "the item text and the phase goal"
        out.say(f"  expected before the work: {it.expect}" if it.expect else f"  expected before the work: (nothing was written — hold it to {anchor})")
        out.say(f"  the doer says came out: {it.result or '(no words)'}")
        if it.evidence:
            out.say("  proofs:", *(f"    - {_proof_for_brief(case, k, pr)}" for k, pr in it.evidence))
            out.say(*(f"  ⚠ {c[2]} changed since done (#{c[3]} → now {c[4]}) — the doer records this version before you accept: "
                      f"el todo done {it.ref} file:{c[2]} \"…\"" for c in changed if c[1] is it))
        else:
            out.say("  proofs: none recorded")
        for r in it.after:
            pre = by_ref.get(r)
            if pre is not None:
                proofs = " · ".join(f"{k} {pr}".strip() for k, pr in pre.evidence) or (pre.result or "")
                out.say(f"  rests on {r} {'✓' if pre.done else 'open'} «{order._short(pre.text, 60)}»" + (f" — {proofs}" if proofs else ""))
        parent = _parent_of(phase, it)
        if parent is not None:  # F25: a sub-item is a step of the item above — the brief says of what
            out.say(f"  a sub-item of {parent.ref}: {parent.text}" + (f" (why: {parent.why})" if parent.why else ""))
        if it.subs:  # F25: how the answer was reached — each path with its end; the closed ones are part of the proof
            out.say(f"  reached through its sub-items ({_sub_tally(it)[len(grammar.TALLY_SUFFIX):]}):",
                    *(f"    - {s.ref} {'✓' if s.done else '✗ cancelled: ' + s.cancel_reason if s.cancelled else 'open'} «{s.text}»"
                      + (f" — fact: {s.fact}" if s.done and s.fact else "") + (f" — accepted: {s.accepted}" if s.accepted else "")
                      for s in it.subs))
    out.say("How to judge:",
            "  1. Open every file, re-run every run you safely can, follow every ref you can reach — and say which you could not.",
            "  2. Hold the result to `why` and to what was expected before the work — not to the doer's words. Words that repeat "
            "the owner's words prove nothing.",
            "  3. Something missing, wrong or unproved → return it, naming what exactly. It does what `why` asks and the proofs "
            "show it → accept, saying what you checked.",
            "Verdict — run ONE per item from the project folder:")
    for it in items:
        reruns = "".join(f' --run "{pr.split("→")[0].strip()} → <what came out now>"' for k, pr in it.evidence if k == "run")
        out.say(f"  el --case {name} todo accept {it.ref} --by <you: codex|claude|gemini|subagent>{reruns} \"what you checked and how\"",
                f"  el --case {name} todo reopen {it.ref} --by <you> \"what is missing or wrong\"")
    if any(k == "run" for it in items for k, _ in it.evidence):
        out.say("Every run proof is re-run by you: one --run per proof with what came out now; could not run one — "
                "--run \"<command> → not run: why\". A result that differs is a return, not an acceptance.")
    out.say("No `el` where you run? Give the owner the verdict and the reason — the owner records it.")
    return out


def _returns(journal: Optional[grammar.Journal]) -> Dict[str, List[str]]:
    """item → the reasons it was sent back (`DECISION · N.M возвращён в работу — …`), newest first."""
    found: Dict[str, List[str]] = {}
    for ev in (journal.newest_first() if journal is not None else []):
        m = RETURN_RE.match(ev.text) if ev.type == "DECISION" else None
        if m:
            for r in re.findall(grammar.ITEM_REF, m.group(1)):
                found.setdefault(r, []).append(ev.text[m.end():])
    return found


def _stalled_lines(todo: grammar.Todo, journal: Optional[grammar.Journal]) -> List[str]:
    """Order (F23): an open item sent back STALL_RETURNS times or more is stuck — ART stalled such a task instead of
    letting it loop. Every exit is honest: finish it, cut it smaller, or cancel it with the reason."""
    counts = _returns(journal)
    lines = []
    for p in todo.phases:
        if p.done:
            continue
        for it in grammar.flat(p.items):
            ref = f"{it.ref}"
            k = len(counts.get(ref, []))
            if not it.done and k >= STALL_RETURNS:
                lines.append(f"{ref} returned {k} times — stuck: cut it into smaller items (el todo add {p.n} \"…\" · el todo note {ref} \"…\") "
                             f"· or cancel it with the reason: el todo cancel {ref} \"why\" · or finish it: el todo done {ref} <kind> \"…\"; "
                             f"the reasons: el todo show {ref}")
    return lines


LATER_BOUNDARIES = 3  # three closes passed it by: take it or let it go (F24) — shown, never refused


def _thread_line(case: Path, todo: grammar.Todo, readme_body: str, order_lines: Optional[List[str]] = None) -> Optional[str]:
    """`thread: goal «…» → phase N Name «goal» → item N.M «…» (why: …) → next: «…»` — the first line of the entry (the
    owner's word, 2026-09-25: an agent with no memory reads everything and must see what is subordinate to what — the big
    goal, the stage, where it stands, what it works on, and that its result moves the goal). Rendered from the case,
    never typed: Context, the phase in flight, its first item one can take (not held, not blocked), the first Order line
    it has not named yet, State `next:`. One vector (a live report, 2026-09-25): the thread led to the item and to `next:`
    while Order below asked to put a debt back first — the agent read two directions; now the debt is a step of the thread."""
    parts = []
    goal = _context_goal(readme_body)
    if goal:
        parts.append(f"goal «{order._short(goal, 70)}»")
    phase = _flying(case, todo) or todo.current()
    if phase is None:
        ready = _ready_value(readme_body)
        try:  # the owner's case: `done` is the agents' honest end, not a close behind his back (pm-haiku-13, 2026-10-08:
            owners = _owner_closes(store.find_root(), case)  # four sessions wrote «awaits the owner» in next: and never
        except StoreError:  # ran done, reading it as a close without him)
            owners = False
        parts.append(f"ready since {ready.split(' · ', 1)[0]} — awaits the owner's word: el done --by owner \"his words\"" if ready
                     else "no phase yet: el phase open 1 \"Name\" --goal \"…\"" if not todo.phases
                     else "every phase ended: el done \"what came out\" makes it ready — the owner's word closes it" if owners
                     else "every phase ended: el done \"…\"")
    else:
        pgoal = _phase_goal(case, phase) or (phase.summary or "")
        waiting = [p for p in todo.phases if not p.done and p.held_for() == phase.n]  # F26: what this detour paused
        parts.append(f"phase {phase.n} {phase.name}" + (f" «{order._short(pgoal, 60)}»" if pgoal else "")
                     + ("" if _phase_file(case, phase.n, phase.name).exists() else " (planned)")
                     + (f" (a detour: {', '.join(f'{p.n} {p.name}' for p in waiting)} paused for it, resumes when it ends)" if waiting else ""))
        if phase.held:  # paused, and what it was paused for is no longer in flight: the hand puts it back
            parts.append(f"paused for «{order._short(phase.hold_reason, 50)}», nothing in flight: el phase resume {phase.n}")
        blocked = _blocking(case, todo)
        open_items = [it for it in phase.items if not it.done]
        ready = [it for it in open_items if not it.held and f"{it.ref}" not in blocked]
        if ready:
            it = ready[0]
            parts.append(f"item {it.ref} «{order._short(it.text, 60)}»" + (f" (why: {order._short(it.why, 60)})" if it.why else ""))
            if it.subs:  # F25: the step in hand is one level down — the first sub-item one can take, or what the item waits for
                left = it.open_subs()
                take = [s for s in left if not s.held and s.ref not in blocked]
                if take:
                    parts.append(f"sub-item {take[0].ref} «{order._short(take[0].text, 60)}»")
                elif left:
                    parts.append(_waiting_step(phase, left, blocked))
                else:
                    parts.append(f"its sub-items ended: el todo done {it.ref} <kind> \"what came out\"")
        elif phase.items and not open_items:
            unaccepted = [it for it in grammar.flat(phase.items) if it.done and not it.accepted] if _two_hands(readme_body) else []
            parts.append(f"every item ended, {len(unaccepted)} not accepted: el todo brief {unaccepted[0].ref}" if unaccepted
                         else f"every item ended: el phase close {phase.n} \"…\"")
            order_lines = [ln for ln in (order_lines or []) if not ln.startswith(f"phase {phase.n} ")]  # named just now
        elif open_items:
            parts.append(_waiting_step(phase, open_items, blocked))
        else:
            parts.append(f"no items: el todo add {phase.n} \"…\"")
    if order_lines:
        more = f" (+{len(order_lines) - 1} more)" if len(order_lines) > 1 else ""
        parts.append(f"first: Order «{order._short(order_lines[0], 70)}»{more}")
    m = re.search(r"^- next: (.+)$", readme_body, re.M)
    if m:
        parts.append(f"next: «{order._short(m.group(1).strip(), 70)}»")
    return "thread: " + " → ".join(parts) if parts else None


def _waiting_step(phase: grammar.Phase, open_items: List[grammar.Item], blocked: Dict[str, List[Tuple[str, str]]]) -> str:
    """The thread's step when no open item can be taken: WHAT the phase waits for, with the move that ends the wait
    (feedback 2026-09-30: an item waiting for another team's ticket was left `[ ]`, reading «do me now», because the
    thread said «held or blocked: see unblocked:» — and `unblocked:` never lists either, so the pointer led nowhere)."""
    held = [it for it in open_items if it.held]
    if held:
        it = held[0]
        more = f" (+{len(held) - 1} more held)" if len(held) > 1 else ""
        why = f" «{order._short(it.hold_reason, 60)}»" if it.hold_reason else ""
        check = f" — is it over? `{it.hold_check}`" if it.hold_check else ""  # the agent runs it; el never does (L4)
        return f"waiting: {it.ref}{why}{more}{check} — it came: el todo resume {it.ref}"
    ref = next(f"{it.ref}" for it in open_items if f"{it.ref}" in blocked)
    on = ", ".join(r + ("" if st == "open" else f" ({st})") for r, st in blocked[ref])
    return f"blocked: {ref} after {on} — finish that first, or rewire: el todo after {ref} none"


def _later_lines(todo: grammar.Todo, journal: Optional[grammar.Journal]) -> List[str]:
    """Order (F24): a thought in the general list has a moment of return — every phase boundary; one that lay through
    LATER_BOUNDARIES closes is asked about by name (the owner's word, 2026-09-25; the old fear, 2026-09-15: «a backlog
    eats thoughts» — here every boundary is a return, and the counter says which thought was never taken)."""
    if journal is None or not todo.later:
        return []
    closes = [e.date for e in journal.entries for ev in e.events if ev.type == "PHASE" and "закрыта" in ev.text]
    lines = []
    for it in todo.later:
        k = sum(1 for d in closes if it.since and d > it.since)
        if k >= LATER_BOUNDARIES:
            lines.append(f"L{it.m} «{order._short(it.text, 50)}» lay through {k} phase closes — take it into a phase: el todo move L{it.m} N "
                         f"· or cancel it with the reason: el todo cancel L{it.m} \"why\"")
    return lines


def _later_boundary_line(todo: grammar.Todo) -> Optional[str]:
    """Said at `phase close` — the boundary is the moment the general list is looked at (F24)."""
    if not todo.later:
        return None
    first = todo.later[0].m
    shown = ", ".join(f"L{it.m} «{order._short(it.text, 40)}»" for it in todo.later[:5]) + (f" … +{len(todo.later) - 5}" if len(todo.later) > 5 else "")
    return (f"general list (Later) — {len(todo.later)} line(s) wait for this boundary: {shown} → into the next phase: "
            f"el todo move L{first} N · not needed: el todo cancel L{first} \"why\" · kept: it counts the boundaries it lies through")


def _two_hands(readme_body: str) -> bool:
    """The case rule «two hands» — a Context line `- rule: two hands …` (opt-in, like «items link their material»):
    here a fresh session accepts every done item of a running phase, and the owner agrees each phase's scope."""
    return RULE_TWO_HANDS_RE.search(readme_body) is not None


def _unaccepted_lines(case: Path, todo: grammar.Todo, readme_body: str) -> List[str]:
    if not _two_hands(readme_body):
        return []
    items = [it for p in _running_phases(case, todo) if any(not it.done for it in p.items)  # a finished phase: its own line
             for it in grammar.flat(p.items) if it.done and not it.accepted]
    if not items:
        return []
    first = f"{items[0].ref}"
    shown = ", ".join(f"{it.ref}" for it in items[:6]) + (f" … +{len(items) - 6}" if len(items) > 6 else "")
    same = [it for it in items if it.n == items[0].n]
    span = (", ".join(it.ref for it in same) if any(it.k for it in same)  # sub-items are named, a range is one item level
            else f"{items[0].n}.{min(it.m for it in same)}-{items[0].n}.{max(it.m for it in same)}")
    many = f"; many at once: el todo accept {span} --by owner \"…\"" if len(same) > 1 else ""
    return [f"{len(items)} done item(s) not accepted — {shown} → a fresh session accepts or returns: el todo brief {first} "
            f"(this case's rule: two hands; the owner's word instead: el todo accept {first} --by owner \"…\"{many})"]


def _second_hand_doors(items: List[grammar.Item], first: str, span: str, journal: Optional[grammar.Journal] = None) -> str:
    """Who can accept these now, said to the session that reads it (the polygon, 2026-10-07: sixteen items done by one
    Haiku session waited four sessions — each fresh one read «a fresh session accepts», took the doer for itself and asked
    the owner to drop the rule; Sonnet accepted through subagents and el called it «same session»). el knows the doer's
    session from the signature and its own from the harness — so it says which hand the reader is, and every door."""
    mine = session_id()
    doers = {(_sign_parse(it.done_by)[2] if it.done_by else (_doer_session(journal, None, it) if journal is not None else ""))
             for it in items} - {""}
    run = " --run \"<command> → what came out now>\"" if any(k == "run" for it in items for k, _ in it.evidence) else ""
    owner = f"the owner's word said to you: el todo accept {span} --by owner \"…\""
    sub = (f"a subagent with a clean context — hand it el todo brief {first} as its prompt, it answers "
           f"el todo accept {first} --by subagent{run} \"what it checked\"")
    if mine and doers and mine not in doers:
        return (f"done in session {', '.join(sorted(doers))}, you are another — you are the second hand: el todo brief {first} "
                f"says what to check, then el todo accept {span} --by <you>{run} \"what you checked\" · or return it: "
                f"el todo reopen {first} --by <you> \"why\" · {owner}")
    if mine and doers == {mine}:
        return f"done in this session, so not yours to accept: {sub} · or the next session · or {owner}"
    return f"another hand accepts: a fresh session, or {sub} · or {owner}"


def _acceptance_line(todo: grammar.Todo, readme_body: str, journal: Optional[grammar.Journal], changed: int = 0) -> Optional[str]:
    """`acceptance: 3 of 7 done accepted — another session 2 · the owner's word 1 · returned by an acceptor 1` on entry,
    when the case asks for two hands or anything was accepted or returned by an acceptor."""
    done = [it for p in todo.phases if not p.done for it in grammar.flat(p.items) if it.done]
    acc = [it for it in done if it.accepted]
    open_refs = {f"{it.ref}" for p in todo.phases if not p.done for it in grammar.flat(p.items)}
    by_acceptor = sum(1 for e in (journal.entries if journal is not None else []) for ev in e.events
                      if ev.type == "DECISION" and RETURN_RE.match(ev.text) and "(приёмка: " in ev.text
                      and set(re.findall(grammar.ITEM_REF, RETURN_RE.match(ev.text).group(1))) & open_refs)
    if not (_two_hands(readme_body) or acc or by_acceptor):
        return None
    # both doors, numbered (a live report, 2026-10-02: «the owner said it in the chat — is that enough, or must a
    # subagent be briefed for form's sake?» — the line named the brief only, so the owner's word read as a shortcut)
    owed = [it for it in done if not it.accepted]
    first = f"{owed[0].ref}" if owed else "N.M"
    span = first
    if owed and any(it.k for it in owed if it.n == owed[0].n):  # F25: sub-items are named one by one
        span = ", ".join(it.ref for it in owed if it.n == owed[0].n)
    elif owed:
        n = owed[0].n
        same = sorted(it.m for it in owed if it.n == n)
        between = {it.m for p in todo.phases if p.n == n for it in p.items if same[0] <= it.m <= same[-1]}
        if len(same) > 1:  # a range only when nothing else lies inside it — an open item in it would be refused
            span = f"{n}.{same[0]}-{n}.{same[-1]}" if between == set(same) else ", ".join(f"{n}.{m}" for m in same)
    doors = (_second_hand_doors([it for it in owed if f"{it.ref}" == first or it.n == owed[0].n], first, span, journal) if owed
             else f"a fresh session: el todo brief {first} · the owner's word said to you: el todo accept {span} --by owner \"…\"")
    return (f"acceptance: {_acceptance_tally(done)}" + (f" · returned by an acceptor {by_acceptor}" if by_acceptor else "")
            + (f" · {changed} on a version since changed" if changed else "")  # L8: the verdict was of other bytes
            + f" — {doors}")


RERAN_RE = re.compile(r"\bre-ran (\d+) of \d+")
# L8: the tail `accept` adds — `· another engine: <signature>` — is the acceptor's identity, never read as the verdict
ENGINE_TAIL_RE = re.compile(r" · (?:another engine|another model|same model|model not given|doer not signed|harness not given): .*$")


def _acceptance_tally(items: List[grammar.Item]) -> str:
    """How the done items were accepted, by kind — `3 of 4 done accepted — another session 2 · the owner's word 1 ·
    re-ran 2 of 4 run proof(s)`. One counter for every size the work rises to: the entry (running phases), the Digest of
    a phase, the `closed:` line of a case, which its parent draws (feedback 2026-09-29: sixteen items accepted on one
    blanket word of the owner read ✓ everywhere above the item, the same as a re-run). Counted like the kinds of evidence,
    beside the mark, not in it: the box says the state, the tally says how it was reached."""
    done = [it for it in items if it.done]
    acc = [it for it in done if it.accepted]
    kinds: Dict[str, int] = {}
    for it in acc:
        parts = [x.strip() for x in it.accepted.split(" · ")]
        word = parts[1] if len(parts) > 1 else "?"
        kinds[word] = kinds.get(word, 0) + 1
    tail = " · ".join(f"{w} {n}" for w, n in kinds.items())
    runs = sum(1 for it in done for k, _ in it.evidence if k == "run")
    reran = sum(int(m.group(1)) for it in acc for m in [RERAN_RE.search(ENGINE_TAIL_RE.sub("", it.accepted))] if m)
    return (f"{len(acc)} of {len(done)} done accepted" + (f" — {tail}" if tail else "")
            + (f" · re-ran {reran} of {runs} run proof(s)" if runs else ""))


def todo_resume(case: Path, ref: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    if not item.held:
        out.say(f"item {ref} is not on hold — nothing changed")
        return out
    check = item.hold_check
    item.held, item.hold_reason, item.hold_check = False, "", ""
    out.absorb(_write_todo(case, todo))
    out.say(f"resumed: {ref} {item.text} → TODO.md" + (f" — the wait had its check: `{check}`" if check else ""))
    return out


def todo_drop(case: Path, ref: str) -> Outcome:
    out = Outcome()
    todo = _todo(case, out)
    phase, item = _find_item(todo, ref)
    ref = item.ref if phase.n else ref
    ref_by = [f"{it.ref}" for it in _all_items(todo) if ref in it.after]
    if ref_by:  # F19: an item others wait for does not vanish silently
        raise StoreError(f"{ref} is a dependency of {', '.join(ref_by)} — rewire them first (el todo after N.M <refs|none>) "
                         f"or cancel {ref} with a reason (el todo cancel {ref} \"why\")", 4)
    if item.subs:  # F25: drop says nothing — the sub-items under it are work with their own ends
        raise StoreError(f"{ref} carries sub-items ({', '.join(s.ref for s in item.subs)}) — drop says nothing about them: "
                         f"el todo cancel {ref} \"why\" ends it and its open sub-items with the reason · or drop each first", 4)
    parent = _parent_of(phase, item)
    if parent is not None:
        parent.subs.remove(item)
        out.absorb(_write_todo(case, todo))
        out.say(f"dropped: {ref} «{item.text}» — numbers kept, {parent.ref} now holds "
                f"{', '.join(s.ref for s in parent.subs) or 'no sub-items'} (git keeps the history; a decision behind it → el log DECISION)")
        return out
    phase.items.remove(item)
    out.absorb(_write_todo(case, todo))
    # the numbers of the others are kept (N.M is for life) — and said aloud, so the next command in a
    # batch is aimed at a number the caller has just been shown (feedback 2026-09-03)
    where = "the general list" if phase.n == 0 else f"phase {phase.n}"
    out.say(f"dropped: {ref} «{item.text}» — numbers kept, {where} now reads {_number_ranges(phase)} "
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
    subs = [it for it in items if it.k]
    for s in subs:  # F25: a sub-item ends in sight — not twice, not under a finished item, not over its result
        _done_parent_refusal(phase, s, "cancel")
        if s.cancelled:
            raise StoreError(f"{s.ref} is cancelled already ({s.cancel_reason}) — nothing written", 4)
        if s.done:
            raise StoreError(f"{s.ref} is done — its result stands; it no longer holds? el todo reopen {s.ref} \"why\", "
                             f"then el todo cancel {s.ref} \"…\"", 4)
    reason = _pocket_text("cancel", why, subs[0].ref) if subs else why  # it stands on the sub-item's line in TODO
    tops = [it for it in items if not it.k]
    swept = [s for it in tops for s in it.open_subs()]  # an item cancelled ends its open sub-items with the same reason
    for s in subs + swept:
        s.cancelled, s.cancel_reason, s.held, s.hold_reason, s.hold_check = True, reason, False, "", ""
    for it in tops:
        phase.items.remove(it)
    out.absorb(_write_todo(case, todo))
    named = ", ".join(f"{_ref(phase, it)} «{it.text}»" for it in tops + subs + swept)
    out.lines += log(case, "DECISION", f"снято {named} — {why}", _phase_of(todo, case) if phase.n == 0 else f"p{phase.n}").lines
    where = "the general list" if phase.n == 0 else f"phase {phase.n}"
    if tops:
        out.say(f"cancelled: {', '.join(f'{_ref(phase, it)} «{it.text}»' for it in tops)} — out of TODO, the reason is in the journal; "
                f"{where} now reads {_number_ranges(phase)}" + (f" · its open sub-item(s) ended with it: {', '.join(s.ref for s in swept)}" if swept else ""))
    if subs:
        parent = _parent_of(phase, subs[0])
        out.say(f"cancelled: {', '.join(f'{s.ref} «{s.text}»' for s in subs)} — stays in sight under {parent.ref} with its reason "
                f"(F25: a path closed is part of how the item ended), the reason is in the journal · {parent.ref} now: "
                f"{_sub_tally(parent)[len(grammar.TALLY_SUFFIX):]}")
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
    if _cancelled(prev):
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
    if prev.waits:  # a count, a few names and the door — the live map, 2026-10-08: thirty names on one line, no command
        shown = ", ".join(prev.waits[:5]) + (f" +{len(prev.waits) - 5} more" if len(prev.waits) > 5 else "")
        missing.append(f"phase {prev.n}: still waits for {len(prev.waits)} nested case(s) — {shown} → each ends by its own "
                       f"close: el --case {prev.waits[0]} done \"what came out\" · where each stands: el case list")
    return missing


def phase_plan(case: Path, n: int, name: str, goal: Optional[str]) -> Outcome:
    """Name the next phase now, open it later: `- [ ] N Name — <intent>` in TODO, no phase file, no
    journal event (a plan is not an event, P5). Items may be parked under it (`todo add N`); it
    opens with `el phase open N` once the previous phase is closed — P8 stays: planned ≠ open.
    Feedback 2026-09-03: a dated deadline outside the current phase had nowhere to live in TODO."""
    out = Outcome()
    if not grammar.PHASE_NAME_RE.match(name):
        raise StoreError(f"phase name `{name}` must be English, 1–3 words, letters, digits, hyphen (F13) — it names the file "
                         f"phases/N-name.md; the words in your language go into the goal: el phase plan {n} '<English name>' "
                         f"--goal {_sh(name)}", 2)
    todo = _todo(case, out)
    existing = todo.phase(n)
    intent = _goal_text(goal) if goal else None
    if intent and grammar.visible_len(intent) > grammar.TODO_ITEM_CHARS:
        raise StoreError(f"{_too_long('intent (one line in TODO)', intent, grammar.TODO_ITEM_CHARS, 'F13')}\n"
                         f"{_split_suggestion(intent, f'el phase plan {n} {chr(39)}{name}{chr(39)} --goal «head»', f'&& el phase note {n} «rest»')}\n"
                         f"{INTENT_HINT}", 3)
    if existing is not None:
        free = max(p.n for p in todo.phases) + 1
        if _cancelled(existing):
            back = _replan_cancelled(case, todo, existing, name, intent, free, out)
            _case_promise_hint(case, _todo(case), n, back)
            return back
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
            _case_promise_hint(case, todo, n, out)
            return out
        out.absorb(_write_todo(case, todo))
        _sync_progress(case, todo, out)
        out.say(f"re-planned: phase {n} {name} — {existing.summary or '(no goal)'} ({', '.join(changes)}) → TODO.md")
        _case_promise_hint(case, todo, n, out)
        return out
    todo.phases.append(grammar.Phase(n, name, False, 0, intent))
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    out.say(f"planned: phase {n} {name} → TODO.md (no phase file until it opens) · items now: el todo add {n} \"…\" · "
            f"open once the previous phase is closed: el phase open {n}")
    _case_promise_hint(case, todo, n, out)
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
            pocket = re.fullmatch(r"  - (why|note|expect|fact): (.+)", ln)
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
                elif pocket.group(1) == "fact":
                    items[-1].fact = val
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
        store.remember(pf)
        pf.unlink()  # born closed at cancel, nothing of its own inside (checked above)
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    out.lines = log(case, "DECISION", f"фаза {n} {name} возвращена в план ({was.split(' · ')[0]})", f"p{n}").lines + out.lines
    out.say(f"re-planned: phase {n} {name} — {phase.summary or '(no goal)'} → TODO.md (was cancelled)"
            + (f" · items back: {_refs(phase, items)}" if items else "") + f" · open it later: el phase open {n}")
    return out


SCOPE_RE = re.compile(r"^объём фазы (\d+) утверждён владельцем")


def _scope_agreed(journal: grammar.Journal, n: int) -> bool:
    return any(ev.type == "DECISION" and (m := SCOPE_RE.match(ev.text)) and int(m.group(1)) == n
               for ev in _events_for_phase(journal, f"p{n}"))


def phase_agree(case: Path, n: int, text: str) -> Outcome:
    """`el phase agree N "the owner's words"` — the owner agreed the scope of phase N (the owner's word, 2026-09-25:
    «the agent proposes the phases, I agree the scope of the next one, then it plans»). A DECISION under the phase, in the
    owner's words; planned or open. A changed scope is a new agree — the journal keeps both. The agent writes the record,
    so this is the owner's word as reported — like `owner` evidence."""
    out = Outcome()
    text = " ".join(text.split())
    if not text:
        raise StoreError(f"agree needs the owner's words: el phase agree {n} \"what the owner agreed to, in the owner's words\"", 2)
    todo = _todo(case, out)
    phase = todo.phase(n)
    if phase is None:
        raise StoreError(f"no phase {n} in TODO.md — plan it first: el phase plan {n} \"Name\" --goal \"…\"", 4)
    if phase.done:
        raise StoreError(f"phase {n} {phase.name} is closed — its scope is history; the next one: el phase plan N \"Name\"", 4)
    out.lines += log(case, "DECISION", f"объём фазы {n} утверждён владельцем: «{text}»", f"p{n}").lines
    state = "open" if _phase_file(case, n, phase.name).exists() else "planned"
    out.say(f"agreed: phase {n} {phase.name} ({state}) — «{text}» → DECISION in the journal (a changed scope is a new agree)")
    return out


def _scope_lines(case: Path, todo: grammar.Todo, readme_body: str, journal: Optional[grammar.Journal]) -> List[str]:
    """Order under the rule «two hands»: a running phase whose scope the owner never agreed (F24)."""
    if journal is None or not _two_hands(readme_body):
        return []
    return [f"phase {p.n} {p.name} runs without the owner's agreed scope → el phase agree {p.n} \"the owner's words\" "
            f"(this case's rule: two hands)" for p in _running_phases(case, todo) if not _scope_agreed(journal, p.n)]


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


def _open_blockers(case: Path, todo: grammar.Todo, n: int, why: str = "", out: Optional[Outcome] = None) -> List[str]:
    """Why `el phase open N` would be refused now — one phase in flight (P8), a planned phase below skipped only with a
    reason (F24), the gates of the last closed phase. `phase open` raises on them; `done` asks them, so its refusal names
    a command that runs (feedback 2026-10-05)."""
    below = [p for p in todo.phases if p.n < n]
    skipped = sorted((p for p in below if not p.done and not _phase_file(case, p.n, p.name).exists()), key=lambda p: p.n)
    missing: List[str] = []
    for f in (p for p in todo.phases if not p.done and not p.held and p.n != n and _phase_file(case, p.n, p.name).exists()):
        # one phase in flight, wherever it stands in the numbering (P8); a reason pauses it for this one (F26)
        if why:
            continue
        missing.append(f"phase {f.n} {f.name} is still open — close it first (P8): el phase close {f.n} \"…\" "
                       f"· or cancel it: el phase cancel {f.n} \"why\" · or, when something came up that goes first, "
                       f"pause it for this one: el phase open {n} --why \"what came up\" ({f.n} resumes when {n} ends)")
    if skipped and not why:  # planned, never opened: phases run in order — unless something found says otherwise
        s0 = skipped[-1]
        missing.append(f"phase {s0.n} {s0.name} is planned and not opened — phases run in order: el phase open {s0.n} · or, if it is "
                       f"not needed: el phase cancel {s0.n} \"why\" · or, when something found makes {n} come first: "
                       f"el phase open {n} --why \"what was found\" (the plan below stays a plan)")
    if missing:
        missing.append(ALONGSIDE_HINT)
    last_closed = max((p for p in below if p.done), key=lambda p: p.n, default=None)
    if last_closed is not None:
        missing = _closing_checks(case, last_closed, _journal(case, out)) + missing
    return missing


def phase_open(case: Path, n: int, name: str, goal: Optional[str], why: Optional[str] = None) -> Outcome:
    """Open phase N. One phase in flight (P8); the gates of the last closed phase below hold. A planned phase below that
    never opened is skipped only with a reason (`--why`, F24; the owner's word, 2026-09-25: «a hidden blocker found —
    the fifth before the third»): it stays planned — a draft whose order the boundary decides — and a DECISION says
    what made N come first. Cancelling it to get past it would call a needed phase «not needed»."""
    out = Outcome()
    todo = _todo(case, out)
    existing = todo.phase(n)
    if not name and existing is not None and not existing.done:
        name = existing.name  # `el phase open N` opens the planned phase under its planned name
    if not name:
        raise StoreError(f"phase open needs a name: `el phase open {n} \"CLI core\" --goal …` — no planned phase {n} to take it from", 2)
    if not grammar.PHASE_NAME_RE.match(name):
        raise StoreError(f"phase name `{name}` must be English, 1–3 words, letters, digits, hyphen (F13) — it names the file "
                         f"phases/N-name.md; the words in your language go into the goal: el phase open {n} '<English name>' "
                         f"--goal {_sh(name)}", 2)
    if existing and existing.done:
        raise StoreError(f"phase {n} is already closed", 4)
    pf = _phase_file(case, n, existing.name if existing else name)
    if existing and not existing.done and pf.exists():
        out.say(f"phase {n} {existing.name} is already open — nothing changed")
        return out
    why = " ".join((why or "").split())
    missing = _open_blockers(case, todo, n, why, out)
    if missing:
        raise StoreError("cannot open phase %d:\n  " % n + "\n  ".join(missing), 4)
    pausing = _flying(case, todo) if why else None  # F26: the phase in flight steps aside for this one, with the reason
    if pausing is not None and pausing.n == n:
        pausing = None
    below = [p for p in todo.phases if p.n < n]
    skipped = sorted((p for p in below if not p.done and not _phase_file(case, p.n, p.name).exists()), key=lambda p: p.n)
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
        store.write_file(pf, f"# Phase {n} — {name}\ngoal: {' '.join(goal.split())}\nresult:\n{before}\n## Notes\n")
        out.say(f"created: {pf.relative_to(case)}" + (f" — {len(parked)} journal event(s) parked here before opening are in it" if parked else ""))
        if existing is not None and existing.notes:
            out.say(f"phase {n} carries {len(existing.notes)} note(s) in TODO — read them; they move into the phase file at close")
    if existing is None:
        todo.phases.append(grammar.Phase(n, name, False, 0))
    if pausing is not None:
        pausing.held, pausing.hold_reason = True, f"phase {n} {name} — {why}"
    had_default = _default_next_in_state(_readme_text(case))
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    _say_default_next_down(had_default, case, out)
    opened = f"{name} открыта" + (f" (запланирована была как «{renamed}»)" if renamed else "")
    early = []
    if skipped and why:  # the order was changed by something found: said once, with the reason, under this phase
        early = log(case, "DECISION", f"фаза {n} раньше запланированных {', '.join(str(p.n) for p in skipped)} — {why}", f"p{n}").lines
    if pausing is not None:  # the paused phase's own story says why it stood, and for what
        early += log(case, "DECISION", f"фаза {pausing.n} {pausing.name} на паузе ради фазы {n} {name} — {why}", f"p{pausing.n}").lines
    out.lines = early + log(case, "PHASE", opened, f"p{n}").lines + out.lines
    out.say(f"phase {n} {name} is open → TODO.md, README.md State"
            + (f" · before the planned {', '.join(str(p.n) for p in skipped)} — they stay planned; the next boundary decides their order"
               if skipped and why else ""))
    if pausing is not None:
        out.say(f"phase {pausing.n} {pausing.name} paused: [~] hold — waiting for phase {n} {name}; it resumes by itself when {n} "
                f"closes or is cancelled (F26) · its items stay as they are, work in it stays legal")
    if _two_hands(_readme_text(case)) and not _scope_agreed(_journal(case), n):
        out.warn(f"phase {n} opened without the owner's agreed scope (this case's rule: two hands) → el phase agree {n} \"the owner's words\"")
    _case_promise_hint(case, todo, n, out)
    hints.attach(out, "phase_open", rel=f"phases/{pf.name}", n=n,
                 promised=[_slot(k, w) for k, w in grammar.expected_kinds(_phase_goal(case, todo.phase(n)))],
                 covered=[_slot(k, w) for (k, w), st, _ in _goal_coverage(todo.phase(n), _phase_goal(case, todo.phase(n))) if st != "uncovered"])
    return out


def phase_close(case: Path, n: int, summary: str, reflect: Optional[str] = None, align: Optional[str] = None,
                rest: Optional[str] = None, howto: Optional[str] = None) -> Outcome:
    """Close a phase. `--reflect "…"` and `--align "…"` log the two DECISION events P8 asks for in the same
    command (feedback 2026-09-16: three shell round trips for one close added friction, not rigour) — the
    record is identical, the gates are the same, and nothing is logged if another gate refuses the close.
    `--rest later` closes early by the owner's word (F24, 2026-09-25: a dead end, a hidden blocker): the open items
    go to the general list with their pockets instead of holding the phase — nothing is lost, the boundary re-forms."""
    out = Outcome()
    if rest is not None and rest.strip().lower() not in LATER_WORDS:
        raise StoreError(f"--rest takes `later`: the open items go to the general list; to another phase: el todo move N.M K", 2)
    howto_text = _howto_text(case, howto) if howto else None  # checked before anything is written
    todo = _todo(case, out)
    phase = todo.phase(n)
    if phase is None:
        raise StoreError(f"no phase {n} in TODO.md", 4)
    if phase.done:
        out.say(f"phase {n} {phase.name} is already closed — nothing changed")
        return out
    pf = _phase_file(case, n, phase.name)
    rest_items = [it for it in phase.items if not it.done] if rest is not None else []
    carrying = [it for it in rest_items if it.subs]
    if carrying:  # F25: the general list holds single thoughts — an item with its sub-items is a branch, not a thought
        raise StoreError(f"--rest later: {', '.join(it.ref for it in carrying)} carries sub-items — the general list holds single "
                         f"thoughts: end or cancel the item (el todo cancel {carrying[0].ref} \"why\") or move it to a phase "
                         f"(el todo move {carrying[0].ref} K), then close", 4)
    if rest_items:
        moving = {f"{it.ref}" for it in rest_items}
        waiting = [f"{it.ref}" for it in _all_items(todo) if f"{it.ref}" not in moving and set(it.after) & moving]
        if waiting:
            raise StoreError(f"--rest later: {', '.join(waiting)} wait for items that would leave — rewire them first (el todo after N.M <refs|none>)", 4)
    open_items = [f"{it.ref}" for it in phase.items if not it.done and it not in rest_items]
    alongside = None  # (the earlier phase, its state) when this planned phase ended out of turn
    if not pf.exists():
        prev = max((p for p in todo.phases if p.n < n), key=lambda p: p.n, default=None)
        if prev is None or prev.done:
            # planned, never opened, and it COULD open: the pipeline is intact, so walk it (feedback
            # 2026-09-09: `close` died with «phases/22-….md is missing (F12)» and the agent wrote the file
            # by hand). Opening is the one place the gates on the previous phase run and PHASE is logged.
            cur = _flying(case, todo)
            if cur is not None and cur.n != n:  # behind no unfinished phase, beside one in flight: the detour is the way (F26)
                raise StoreError(f"phase {n} {phase.name} was planned and never opened, and phase {cur.n} {cur.name} is in flight — "
                                 f"pause it for this one: el phase open {n} --why \"what came up\" ({cur.n} resumes when {n} ends), "
                                 f"then el phase close {n} \"…\"", 4)
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
        cur = _flying(case, todo)  # the phase in flight, if any — that is what this one ran alongside
        running = cur if cur is not None and cur.n != n else None
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
    unanswered = _unanswered_problems(_events_for_phase(journal, f"p{n}"))
    if unanswered and not howto_text:  # P8: the close is the archivist's moment — what was caught becomes a recipe, or «none»
        missing.append(f"phase {n} logged {len(unanswered)} PROBLEM(s) no recipe answers — «{order._short(unanswered[0].text, 60)}»: "
                       f"{HOWTO_ASK}: el phase close {n} \"…\" --howto …")
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
    unaccepted = [f"{it.ref}" for it in grammar.flat(phase.items) if it.done and not it.accepted]
    if unaccepted and _two_hands(_readme_text(case)):  # F23: this case asked for two hands — the close waits for the second
        owed = [it for it in grammar.flat(phase.items) if it.done and not it.accepted]
        missing.append(f"phase {n}: done items not accepted — {', '.join(unaccepted)} (this case's rule: two hands): "
                       + _second_hand_doors(owed, unaccepted[0], unaccepted[0] if len(owed) == 1 else ", ".join(unaccepted)))
    for _, it, path, was, now in _changed_proofs(case, todo, [phase]):  # L8: the close would stand on bytes nobody claimed
        ref = it.ref
        missing.append(f"phase {n}: {ref} proof {path} changed since done (#{was} → now #{now}) — {_changed_moves(ref, path)}")
    if missing:
        raise StoreError("cannot close phase %d:\n  " % n + "\n  ".join(missing), 4)
    if rest_items:  # every gate held: the rest leaves for the general list now, in the same write as the close
        k0, moved = _next_later(case, todo), []
        for i, it in enumerate(rest_items):
            phase.items.remove(it)
            old_ref = f"{it.ref}"
            it.n, it.m, it.since = 0, k0 + i, _now()[0]
            it.due, it.after, it.held, it.hold_reason = "", [], False, ""
            todo.later.append(it)
            moved.append(f"{old_ref} → L{it.m}")
        out.lines += log(case, "DECISION", f"остаток фазы {n} → общий список: {', '.join(moved)}", f"p{n}").lines
        out.say(f"the rest of phase {n} → the general list: {', '.join(moved)} (with their pockets; the boundary decides where they go)")
    for tag, val in (("reflect", reflect), ("align", align)):
        if val:  # every other gate held: the two events are written now, then the close proceeds on them
            out.lines += log(case, "DECISION", f"{tag}: {val}", f"p{n}").lines
    if howto_text:
        out.lines += log(case, "DECISION", f"howto: {howto_text}", f"p{n}").lines
    if reflect or align or howto_text:  # the events just written belong to the Digest rendered below
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
        store.write_file(pf, f"# Phase {n} — {phase.name}\ngoal: {phase.summary or '—'}\nresult:\n\n## Notes\n")
        out.say(f"created: {pf.relative_to(case)} (from the plan)")
    # el's own count of how the phase was accepted stands beside the closer's words wherever the phase is read in one line —
    # TODO, the result line Links draws, the output (feedback 2026-10-05: «accepted by a second hand» over «same session 8»)
    nodes = grammar.flat(phase.items)  # F25: sub-items are done and accepted like items — the count is of every node
    tally = _acceptance_tally(nodes) if _case_two_hands(case) or any(it.accepted for it in nodes) else ""
    said = f"{summary} · acceptance: {tally}" if tally else summary
    text = pf.read_text(encoding="utf-8").split("\n")
    text[2] = f"result: {said}"
    goal_line = grammar.parse_phase_file("\n".join(text)).goal
    text = text[:3] + ["", "## Digest", *_digest(case, pf, phase, evs_here, goal_line)] + text[3:]
    if phase.items:
        text.append("")
        text.append("## Items at close")
        for it in phase.items:
            text.extend(_item_block_for_phase_file(case, pf, it))
    store.write_file(pf, re.sub(r"\n{3,}", "\n\n", "\n".join(text)).rstrip("\n") + "\n")
    rel = f"phases/{pf.name}"
    phase.done, phase.items, phase.notes, phase.held, phase.hold_reason = True, [], [], False, ""
    phase.summary = f"{said} · {date} · {_phase_link(pf.name)}" if rel not in summary else said
    back = _resume_after(todo, n)  # F26: a detour closed — what it paused is in flight again
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    ran = ""
    if alongside:  # the journal names the phase that was running; nothing in flight = closed before its turn
        ran = (f" (шла параллельно фазе {alongside[2].n}, без открытия)" if alongside[2]
               else " (закрыта до своей очереди, без открытия)")
    out.lines = log(case, "PHASE", f"{phase.name} закрыта{ran} → {summary}", f"p{n}").lines + out.lines
    out.say(f"closed: phase {n} {phase.name} → TODO.md (collapsed), {rel} (result), README.md State"
            + (f" · acceptance: {tally}" if tally else ""))
    later = _later_boundary_line(todo)
    if later:
        out.say(later)
    _say_resumed(case, todo, back, n, out)
    offer = _knowledge_offer(case)
    if offer:
        out.say(offer)
    hints.attach(out, "phase_close", n=n, events=evs_here)
    if alongside:
        out.say(f"closed from the plan, out of turn — phase {alongside[0].n} {alongside[0].name} is still {alongside[1]}, "
                f"the pipeline stays in order. {ALONGSIDE_HINT}")
    return out


# ---- recipes at the close (P8; the owner's word, 2026-09-25) --------------------------------------------------------
# «Every time we close a phase or a case there must be a step where .howto is checked — agents rarely update it, and the
# close is the logical moment; nothing caught — say so». Measured the same day on the tool's own case: 48 PROBLEM events,
# one names .howto/, four recipes in all. The close asks once, only when a PROBLEM of the phase (the case) has no recipe
# answering it; the answer is a recipe the next agent finds by grep, or «none» with its reason. At the close door only:
# an old phase closed before the rule is never asked again (P15).
HOWTO_PATH_RE = re.compile(r"\.howto/[\w./-]+\.md")
CASE_MARK_RE = re.compile(r" · open → \S+/$|^закрыто → .* · \S+/$|^дело закрыто → ")  # a nested case opened or closed — not a problem
HOWTO_ASK = ('what became a recipe? --howto ".howto/<verb>.md" (first line `when: <the error words>` — grep finds it next time) '
             '· nothing repeats → --howto "none: why"')


def _unanswered_problems(evs: List[grammar.Event]) -> List[grammar.Event]:
    """The PROBLEM events of a phase no recipe answers: none named `.howto/…` and no `DECISION · howto:` was given."""
    if any(ev.type == "DECISION" and ev.text.startswith("howto:") for ev in evs):
        return []
    return [ev for ev in evs if ev.type == "PROBLEM" and not CASE_MARK_RE.search(ev.text)
            and not HOWTO_PATH_RE.search(" ".join([ev.text, *ev.body]))]


def _howto_text(case: Path, value: str) -> str:
    """`--howto` checked before anything is written: `none: why` (the reason required), or recipe paths `.howto/x.md` that
    exist in the project with `when:` as their first line — rendered as links from the case. Returns the words after `howto:`."""
    value = " ".join(value.split())
    if value.lower().startswith("none") or value in ("-", "—"):
        rest = value[4:].lstrip(" :—-").strip() if value.lower().startswith("none") else ""
        if not rest:
            raise StoreError('--howto none needs its reason: --howto "none: why nothing here repeats"', 2)
        return f"none: {rest}"
    paths = HOWTO_PATH_RE.findall(value)
    if not paths:
        raise StoreError(f'--howto takes a recipe .howto/<verb>.md or "none: why" — not `{value}`', 2)
    project, text = _project_root(case), value
    for rel in dict.fromkeys(paths):
        f = project / rel
        if not f.is_file():
            raise StoreError(f"{rel} is not there — write the recipe first (first line `when: <the error words>`), then close; "
                             f"nothing repeats → --howto \"none: why\"", 4)
        first = f.read_text(encoding="utf-8").split("\n", 1)[0].strip()
        if not first.startswith("when:"):
            raise StoreError(f"{rel}: the first line must be `when: <the error words>` — that line is what grep finds next time; "
                             f"it reads «{order._short(first, 60)}»", 3)
        text = text.replace(rel, f"[{f.name}]({os.path.relpath(f, case)})")
    return text


def _item_block_for_phase_file(case: Path, pf: Path, it: grammar.Item) -> List[str]:
    """An item copied from TODO into the phase file — its line and its pockets (F22) — keeps pointing at the
    same files: TODO lives in the case root, the phase file in phases/, so every relative link is re-based
    (`docs/x.md` → `../docs/x.md`). Feedback 2026-09-08: verbatim copies left `el check` with broken links."""
    block = _item_block(it)
    prefix = f"  - [{'x' if it.done else ('~' if it.held else ' ')}] {it.ref} "
    rest = block[0][len(prefix):] if block[0].startswith(prefix) else it.text  # `  - [x] N.M text…` → `- N.M ✓ text…`
    lines = [f"- {it.ref} {'✓' if it.done else '✗'} {rest}".rstrip()]
    for ln in block[1:]:  # pockets one level up: the item is the bullet here
        ln = ln[2:]
        ms = re.fullmatch(r"  - \[(.)\] (\d+\.\d+\.\d+) (.*)", ln)  # F25: a sub-item, in the same form one level down
        lines.append(f"  - {ms.group(2)} {'✓' if ms.group(1) in 'x/' else '✗'} {ms.group(3)}" if ms else ln)
    return [_rewrite_links(ln, case, new_base=pf.parent)[0] for ln in lines]


ITEM_RESULT_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?(?:[,\s–-]+\d+\.\d+(?:\.\d+)?)*:")  # `RESULT · 2.1: …` · `2.1, 2.3: …` · `2.1-2.4: …`


def _verbatim_share(a: str, b: str) -> float:
    """Share of a's word 3-grams found verbatim in b (the duplicate detector of F15, on two texts)."""
    return order.text_share(a, b)


def _digest(case: Path, pf: Path, phase: grammar.Phase, evs: List[grammar.Event], goal: str = "") -> List[str]:
    """The `## Digest` of a closed phase — rendered, never typed (the owner's word, 2026-09-15: «клацаешь на
    ссылку, а там список; хочется выжимку»): what the phase held (items, notes), what came out (RESULT),
    what bit and what was decided (PROBLEM, DECISION), reflect and align — all from the journal events of
    this phase and its items. Poor journal, poor digest: it shows the record as it is."""
    def rel(text: str) -> str:
        return _rewrite_links(" ".join(text.split()), case, new_base=pf.parent)[0]  # the Digest is a file: whole

    def bucket(label: str, texts: List[str]) -> List[str]:
        return [f"- {label} ({len(texts)}):", *(f"  - {t}" for t in texts)] if texts else []

    nodes = grammar.flat(phase.items, cancelled=True)  # F25: the sub-items rise with their items
    subs = [it for it in nodes if it.k]
    done_n = sum(1 for it in phase.items if it.done)
    head = f"- items: {done_n} done" + (f" · {len(phase.items) - done_n} open" if len(phase.items) > done_n else "")
    if subs:
        head += (f" · sub-items: {sum(s.done for s in subs)} done" + (f" · {sum(s.cancelled for s in subs)} cancelled"
                                                                       if any(s.cancelled for s in subs) else ""))
    done_n += sum(s.done for s in subs)
    proofs = [grammar.split_fingerprint(pr)[0] if k == "file" else pr for it in nodes if it.done for k, pr in it.evidence]  # a thing, not its version
    distinct = len(set(proofs))
    if proofs and distinct < done_n:  # the owner's eye, 2026-09-16: four items, one self-written file eight times
        shared = max(set(proofs), key=proofs.count)
        head += f" · proofs: {distinct} distinct for {done_n} items ({rel(shared)} ×{proofs.count(shared)})"
    lines = [head]
    if any(it.accepted for it in nodes):  # F23: how the phase was accepted rises with it (feedback 2026-09-29)
        lines.append(f"- acceptance: {_acceptance_tally(nodes)}")
    coverage = _goal_coverage(phase, goal)
    if coverage:  # the phase's own promise (its goal), decomposed into its items and their proofs
        proved = [(sl, ref) for sl, st, ref in coverage if st == "proved"]
        lines.append(f"- phase promise: {len(proved)} of {len(coverage)} proved"
                     + (" — " + " · ".join(f"{_slot(*sl)} by {ref}" if ref else _slot(*sl) for sl, ref in proved) if proved else "")
                     + (" — not proved: " + " ".join(_slot(*sl) for sl, st, _ in coverage if st != "proved") if len(proved) < len(coverage) else ""))
    promised = [it for it in nodes if not it.cancelled and grammar.expected_kinds(it.expect)]
    if promised:  # F22: the record held to its own promises — met, or short and said so
        met = [it for it in promised if all(pr is not None for *_, pr in _pair_slots(grammar.expected_kinds(it.expect), it.evidence))]
        short = [it for it in promised if it not in met]
        line = f"- expectations: {len(met)} met"
        if short:
            line += f" · {len(short)} short (" + "; ".join(
                f"{it.ref} expected {' · '.join(k for k, _ in grammar.expected_kinds(it.expect))}, "
                f"got {' · '.join(k for k, _ in it.evidence) or 'nothing'}" for it in short) + ")"
        lines.append(line)
    lines += bucket("notes", [rel(n) for n in phase.notes])
    lines += bucket("facts", [f"{it.ref} {rel(it.fact)}" for it in nodes if it.done and it.fact])
    lines += bucket("closed paths", [f"{s.ref} {rel(s.text)} — {rel(s.cancel_reason)}" for s in subs if s.cancelled])
    # item results (`RESULT · N.M: …`) live under their items below; the digest keeps the phase-level ones
    lines += bucket("results", [rel(ev.text) for ev in evs if ev.type == "RESULT" and not ITEM_RESULT_RE.match(ev.text)])
    lines += bucket("problems", [rel(ev.text) for ev in evs if ev.type == "PROBLEM"])
    lines += bucket("decisions", [rel(ev.text) for ev in evs if ev.type == "DECISION"
                                  and not ev.text.startswith(("reflect:", "align:", "howto:"))])
    for tag in ("reflect", "align", "howto"):  # howto: what was caught became a recipe, or «none» (P8, 2026-09-25)
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
        store.write_file(pf, f"# Phase {phase.n} — {phase.name}\ngoal: {phase.summary or '—'}\nresult:\n\n## Notes\n")
    lines = pf.read_text(encoding="utf-8").split("\n")
    lines[2] = f"result: снято: {why}"
    if phase.notes:
        lines += ["", "## Notes at cancel", *(f"- note: {_rewrite_links(n, case, new_base=pf.parent)[0]}" for n in phase.notes)]
    if phase.items:
        lines += ["", "## Items at cancel", *(ln for it in phase.items for ln in _item_block_for_phase_file(case, pf, it))]
    store.write_file(pf, "\n".join(lines).rstrip("\n") + "\n")
    items = ", ".join(f"{it.ref}" for it in phase.items if not it.done)
    waits = ", ".join(phase.waits)
    phase.done, phase.items, phase.waits, phase.notes, phase.held, phase.hold_reason = True, [], [], [], False, ""
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
    back = _resume_after(todo, n)  # F26: a detour dropped — what it paused is in flight again
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    out.lines = log(case, "DECISION", text, f"p{n}").lines + out.lines
    out.say(f"cancelled: phase {n} {phase.name} → one line in TODO («снято»), reason in the journal, phases/{_phase_file(case, n, phase.name).name}")
    _say_resumed(case, todo, back, n, out)
    return out


def phase_resume(case: Path, n: int) -> Outcome:
    """`el phase resume N` — a paused phase back in flight by hand (F26). It resumes by itself when its detour ends; by
    hand only when nothing else is in flight — one phase at a time (P8)."""
    out = Outcome()
    todo = _todo(case, out)
    phase = todo.phase(n)
    if phase is None:
        raise StoreError(f"no phase {n} in TODO.md", 4)
    if not phase.held:
        out.say(f"phase {n} {phase.name} is not on hold — nothing changed")
        return out
    cur = _flying(case, todo)
    if cur is not None:
        raise StoreError(f"phase {cur.n} {cur.name} is in flight — {n} resumes by itself when {cur.n} closes (el phase close {cur.n} "
                         f"\"…\") or is cancelled (el phase cancel {cur.n} \"why\"); one phase at a time (P8)", 4)
    phase.held, phase.hold_reason = False, ""
    out.absorb(_write_todo(case, todo))
    _sync_progress(case, todo, out)
    out.say(f"phase {n} {phase.name} resumed → TODO.md, README.md State")
    return out


# ---- readme -------------------------------------------------------------------------------------
def _rule_key(line: str) -> str:
    """A case rule by its name — the one the check reads (`two hands`, `items link`), else its words before the dash, so
    keeping and enforcing agree (Codex review, 2026-10-07: `TWO HANDS` counted as kept and was no longer enforced)."""
    for name, rx in (("two hands", RULE_TWO_HANDS_RE), ("items link", RULE_ITEMS_LINK_RE)):
        if rx.match(line.strip()):
            return name
    return re.sub(r"\s+", " ", line.strip()[len("- rule:"):].split(" — ")[0]).strip().lower()


def _context_rules(text: str) -> List[str]:
    """The `- rule:` lines of a README's Context section, read from the raw text — a README with an unrelated error still
    has its rules (Codex review, 2026-10-07: stray text before Context made the old README unparsable, and the rewrite
    dropped the rule silently)."""
    rules, inside = [], False
    for ln in text.split("\n"):
        if ln.startswith("## "):
            inside = ln.strip() == "## Context"
            continue
        if inside and ln.strip().startswith("- rule:"):
            rules.append(ln.strip())
    return rules


def _keep_rules(case: Path, body: str) -> Tuple[str, List[str]]:
    """A whole README written again keeps the case's rules (the live migration of 2026-10-07: an agent wrote each child's
    README from stdin, the Context it wrote had no `- rule: two hands` line, el answered «written» — and forty-one cases
    closed with one hand under a map that asks for two). A rule is the owner's to drop, by a door that names it
    (`el readme drop context K`), never by leaving it out of a rewrite. Returns the body with the missing rule lines
    appended to its Context, and those lines."""
    try:
        old = _context_rules(stamp.split(store.read(case, "README.md"))[0])
    except StoreError:
        return body, []
    have = {_rule_key(ln) for ln in _context_rules(body)}
    missing = [ln for ln in old if _rule_key(ln) not in have]
    if not missing:
        return body, []
    lines = body.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == "## Context"), None)
    if start is None:
        return body, []  # no Context to keep them in: the grammar refuses the write and names the section
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[:end] + missing + lines[end:]), missing


def readme(case: Path, text: str) -> Outcome:
    out = Outcome()
    body, _ = stamp.split(text)
    body, kept = _keep_rules(case, body)
    parsed = grammar.parse_readme(body)
    for ln in ([] if parsed.errors else parsed.sections.get("Context", [])):  # one door rule for a line and a whole file (L6)
        _context_text(ln)
    try:
        todo = _todo(case, out)
        if not re.search(r"^- progress:", body, re.M):
            body = _set_state_line(body, "progress: ", progress_line(todo, case))
    except StoreError as e:  # readme-only mode: the README is written, progress: is not synced
        out.warn(f"progress: not synced — {e} (recovery: {e.recovery})")
    _write_readme(case, body, out, anchor=True)
    out.say("written: README.md (State anchored `as of` the newest journal entry; Links rendered from the files)")
    if kept:
        ctx = [ln for ln in grammar.parse_readme(stamp.split(store.read(case, "README.md"))[0]).sections.get("Context", [])
               if ln.startswith("- ")]
        for ln in kept:
            k = next((i + 1 for i, c in enumerate(ctx) if c.startswith("- rule:") and _rule_key(c) == _rule_key(ln)), "K")
            out.say(f"kept in Context: {ln} — your text left it out; a case rule is the owner's to drop: "
                    f"el readme drop context {k} (with the owner's word)")
    return out


def readme_show(case: Path, root: Optional[Path] = None) -> Outcome:
    """Bare `el readme` — nothing to write: what to do now (the entry's head), the README as it stands, then the doors
    that write it. Agents read `el readme` as the lighter entry (the polygon, 2026-10-07): the head goes with it."""
    out = Outcome()
    readme_body = _readme_text(case, out)
    if root is not None:
        todo = grammar.parse_todo(stamp.split(store.read(case, "TODO.md"))[0])
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
        out.lines += _entry_head(case, root, readme_body, todo, journal, _order_lines(case, root, readme_body, journal))
        out.say(ENTRY_BODY_MARK.replace("README · TODO · journal headlines", "README (TODO and journal: el)"), "")
    out.say(readme_body.rstrip("\n"), "",
            "write a line: el readme set <prefix> \"…\" · add|edit|drop <section> … · touch — whole file: el readme --file x.md · "
            "el help readme")
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
    if prefix.lower() == "next":
        _walls_question(out)
    return out


STATE_OWNED = grammar.STATE_OWNED  # lines el derives on every write — not yours to remove


def readme_add(case: Path, section: str, line: str) -> Outcome:
    out = Outcome()
    name = SECTION_NAMES.get(section.lower())
    if name is None:
        raise StoreError(f"no section `{section}` — sections: {' · '.join(grammar.README_SECTIONS)}", 2)
    line = _context_text(line) if name == "Context" else " ".join(line.split())  # a promise names a kind from the closed list
    parsed = _readme_sections(case, out)
    parsed.sections.setdefault(name, []).append(f"- {line}")
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
    if name == "Context":
        text = _context_text(text)  # a promise in Context names a kind from the closed list, like a goal or an expect (L6)
    parsed = _readme_sections(case, out)
    ref = str(ref).strip()
    if name == "Context" and ref.lower() == "goal":  # the goal line by name, like State lines by prefix (L6: no door reached it)
        lines = parsed.sections.get("Context", [])
        gi = _goal_line_index(lines)
        if gi is None:
            raise StoreError("Context has no goal line — el readme add context \"…\"", 4)
        old = lines[gi]
        lines[gi] = f"- {text}" if old.startswith("- ") else text
        _write_readme(case, _render_readme(parsed), out)
        out.say(f"README Context: the goal edited → «{text}» (was: «{old[2:] if old.startswith('- ') else old}»)")
        return out
    if not ref.isdigit():
        raise StoreError(f"usage: el readme edit {name.lower()} <k> \"new text\" — k is the line's position (1 = first bullet)"
                         + (" · the goal line: el readme edit context goal \"…\"" if name == "Context" else ""), 2)
    k = int(ref)
    bullets = [i for i, ln in enumerate(parsed.sections.get(name, [])) if ln.startswith("- ") and ln != DECISIONS_DRAWN_HEAD]
    if not 1 <= k <= len(bullets):
        drawn = " — the decisions from the journal under them are drawn by el and go by themselves" if (
            name == "Decisions" and DECISIONS_DRAWN_HEAD in parsed.sections.get(name, [])) else ""
        raise StoreError(f"{name} has {len(bullets)} line(s) of yours, nothing at position {k}{drawn}", 4)
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
    _walls_question(out)
    return out


RECITE_EVERY = 10  # el calls between two recitations — the owner's number (2026-10-07: «a command every 10 calls?»)


def recitation(root: Path, case: Path, calls: int, last_done: int) -> List[str]:
    """Two lines in the middle of the work: where you are, and what is not ticked yet (the owner's word, 2026-10-07; the
    field: Manus rewrites its todo at every step and recites it at the end of the context, or the model loses the goal
    within ~50 calls — convergence 6 of the world survey). The entry says it once; a long session needs it again."""
    try:
        readme_body = _readme_text(case, Outcome())
        todo = grammar.parse_todo(stamp.split(store.read(case, "TODO.md"))[0])
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
        issues = _order_lines(case, root, readme_body, journal)
        thread = _thread_line(case, todo, readme_body, issues) if not todo.errors else None
    except StoreError:
        return []
    lines = [f"recite (every {RECITE_EVERY} el calls): {thread}" if thread else f"recite (every {RECITE_EVERY} el calls):"]
    flight = todo.current()
    owed = [it for it in grammar.flat(flight.items) if not it.done and not it.cancelled] if flight else []
    since = calls - last_done if last_done else calls
    parts = [f"since your last done — {since} el call(s)" if last_done else f"no done yet this session — {calls} el call(s)"]
    if flight:
        shown = ", ".join(it.ref for it in owed[:5]) + (f" (+{len(owed) - 5})" if len(owed) > 5 else "")
        parts.append(f"open in phase {flight.n}: {shown}" if owed else f"phase {flight.n}: nothing open")
    if issues:
        parts.append(f"Order: {len(issues)} → el order")
    tail = f" · finished one? el todo done {owed[0].ref} <kind> \"…\"" if owed else ""
    lines.append("recite: " + " · ".join(parts) + tail)
    return lines


def _walls_question(out: Outcome) -> None:
    """At the end of a session — `next:` set or State confirmed — el names the walls it kept and asks once whether any
    stood where the work was right (the polygon, 2026-10-07: the agents told the owner what blocked them, in Problems
    and in their last message, and none told el). Asked once per new wall: a question repeated on every write is a
    reminder, and reminders are not read."""
    walls = store.session_walls()
    asked = store.walls_asked()
    if len(walls) <= asked:
        return
    fresh = walls[asked:]  # only what was not named yet: a recount of the whole session is a reminder (pm-haiku-6)
    heads: List[str] = []
    for w in fresh:
        h = _wall_head(w)
        if store.wall_key(h) not in {store.wall_key(x) for x in heads}:
            heads.append(h)
    shown = " · ".join(f"«{order._short(h, 70)}»" for h in heads[:3]) + (f" · +{len(heads) - 3} more" if len(heads) > 3 else "")
    # the question is the one the agent can answer honestly (the polygon, pm-haiku-6: «did any stand where your work was
    # right?» drew «no» five times — every refusal was fair, and the real defects of the day were refusals that left the
    # agent guessing and retrying, which it blamed on itself)
    since = "this session" if asked == 0 else "since el last asked"
    out.say(f"{since} el refused you {len(fresh)} time(s) — {shown}: did any leave you guessing the next step, or make you "
            f"try again? that is el's defect, not yours — one line: el feedback --wall --expected \"what it should have "
            f"said\" (el feedback --wall lists them) · none did: go on")
    store.mark_walls_asked(len(walls))


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
        state = parsed.sections.get("State", [])
        at = next((i for i, ln in enumerate(state) if ln.startswith(f"- {prefix}:") and not grammar.DRAWN_WAIT_RE.match(ln)), None)
        if at is None:
            drawn = next((ln for ln in state if ln.startswith(f"- {prefix}:")), None)
            if drawn:
                raise _drawn_wait_refusal(drawn)
            have = ", ".join(ln[2:].split(":")[0] for ln in state if ln.startswith("- "))
            raise StoreError(f"no `- {prefix}:` line in State (lines: {have})", 4)
        removed = parsed.sections["State"].pop(at)
        _write_readme(case, _render_readme(parsed), out, anchor=True)
        out.say(f"README State: `- {prefix}: …` removed")
        return out
    k = int(ref)
    bullets = [i for i, ln in enumerate(parsed.sections.get(name, [])) if ln.startswith("- ") and ln != DECISIONS_DRAWN_HEAD]
    if not 1 <= k <= len(bullets):
        drawn = " — the decisions from the journal under them are drawn by el and go by themselves" if (
            name == "Decisions" and DECISIONS_DRAWN_HEAD in parsed.sections.get(name, [])) else ""
        raise StoreError(f"{name} has {len(bullets)} line(s) of yours, nothing at position {k}{drawn}", 4)
    if name == "State" and grammar.DRAWN_WAIT_RE.match(parsed.sections[name][bullets[k - 1]]):
        raise _drawn_wait_refusal(parsed.sections[name][bullets[k - 1]])
    removed = parsed.sections[name].pop(bullets[k - 1])
    _write_readme(case, _render_readme(parsed), out, anchor=name == "State")
    out.say(f"README {name}: dropped «{removed[2:]}»")
    return out


def _drawn_wait_refusal(line: str) -> StoreError:
    """The `ждёт:` line about a nested case is drawn from the phase's `waits:` (F6): removed here it would come back on
    the next write, and the parent would still wait. It goes when the child ends — the same door that ends it."""
    name = grammar.DRAWN_WAIT_RE.match(line).group(1)
    return StoreError(f"«{line[2:]}» is drawn by el from the phase's `waits:` (F6) — the parent waits for {name}; the line "
                      f"goes when that case ends: el --case {name} done \"outcome\" · or el --case {name} case cancel \"why\"", 4)


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
    """`YYYY-MM-DD-<slug>`. A date already present in the name is used, not doubled (feedback 2026-08-31) — whatever
    follows it: a hyphen, a space, an underscore (a live project, 2026-09-25: «2026-08-31 prod release» became
    `2026-08-31-2026-08-31-prod-release`)."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[\s_:–—-]+(?=\S)", name.strip())
    if m:
        date, name = m.group(1), name.strip()[m.end():]
    else:
        date, _ = _now()
    folder = f"{date}-{_slug(name)}"
    if not store.CASE_NAME_RE.match(folder):
        raise StoreError(f"`{name.strip()}` leaves no folder name: a case is `YYYY-MM-DD-<words>`, and nothing in "
                         f"this name became letters or digits (L2)", 2,
                         recovery='name it in words, e.g. el case new "contract with the builder" --goal "…"')
    return folder


def case_new(root: Path, name: str, goal: str, parent: Optional[Path] = None) -> Path:
    """A new case: at the top of `.cases/`, or nested in `parent` — whose child of the project case (root mode) lives in
    `.cases/` all the same. A nested case links back to the parent's README (F6, L9; feedback 2026-09-30: the bare
    folder name did not click, and a child of the project case had no line about its parent at all)."""
    folder = _case_folder(name)
    case = (root if parent is None or _is_project(parent) else parent) / folder
    if case.exists():
        raise StoreError(f"{case} already exists", 4)
    goal = _context_text(goal)  # before the folder exists: a promise in the goal names a kind from the closed list (L6)
    case.mkdir()
    title = name.strip()
    back = Path(os.path.relpath(store.file_path(parent, "README.md"), case)).as_posix() if parent else ""
    links = [f"- parent: [{parent.name}]({back}) · фаза {_phase_of(store.todo_of(parent))[1:]}"] if parent else []
    d, t = _now()
    readme_text = "\n".join([
        f"# {title}", "", "## Context", goal, *_default_rules(), "", "## State", f"- opened: {d} — with the goal above", "- progress: (no phases yet)",
        f"- next: {DEFAULT_NEXT}", f"- as of: {d} {t} · p0 (1 event)", "",
        "## Decisions", "", "## Problems", "", "## Links", *links, ""])
    store_write_fresh(case, "README.md", readme_text)
    store_write_fresh(case, "TODO.md", f"# TODO — {title}\n")
    event_lines, _ = _render_event("PHASE", f"дело открыто: {goal}")
    store_write_fresh(case, "JOURNAL.md", "\n".join([f"# JOURNAL — {title}", "", f"- {d} {t} · p0", *event_lines]) + "\n")
    return case


def _default_rules() -> List[str]:
    """The Context rules a new case is born with (feedback 2026-09-25, hole «the tool keeps the order»: two hands opt-in by a
    line nobody writes meant one hand always). The line lives in the case, where the owner sees it and may drop it
    (`el readme drop context k`); an old case without it is left as it is. `EL_TWO_HANDS=0` — born without."""
    return [f"- {RULE_TWO_HANDS}"] if os.environ.get("EL_TWO_HANDS", "1") != "0" else []


def store_write_fresh(case: Path, name: str, body: str):
    store.write_file(case / name, stamp.apply(body))


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
    """Switch the hand like `cf target`: this session holds the case (store.hold), and the target's JOURNAL.md mtime is
    bumped for a harness that gives no session id — no content change."""
    import os as _os

    out = Outcome()
    case = store.resolve_case(root, name)
    if not store.is_open(case):
        raise StoreError(f"{case.name} is closed — the hand only holds open cases", 4)
    _os.utime(case / "JOURNAL.md")
    store.hold(root, case)  # this session's hand; the mtime still moves it for a harness without a session id
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
    goal = _context_text(goal)
    d, t = _now()
    store_write_fresh(project, "README.md", "\n".join([
        f"# {title}", "", "## Context", goal, *_default_rules(), "", "## State", f"- opened: {d} — with the goal above", "- progress: (no phases yet)",
        f"- next: {DEFAULT_NEXT}", f"- as of: {d} {t} · p0 (1 event)", "",
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
    cur = _flying(parent, todo) or todo.current()
    if cur is None:
        raise StoreError("parent has no open phase — spawn happens inside a phase (P11)", 4)
    into = root if _is_project(parent) else parent
    child_name = _case_folder(name)
    if (into / child_name).exists():
        raise StoreError(f"{into / child_name} already exists", 4)
    # Parent first, child last: without a session id the hand follows the freshest JOURNAL.md; with one, it is held.
    # README is written before the child too — a refusal there must not leave a folder behind (the undo keeps files).
    cur.waits.append(child_name)
    out.absorb(_write_todo(parent, todo))
    _write_readme(parent, _readme_text(parent, out), out)  # `ждёт:` is drawn from `waits:` (F6)
    out.lines = log(parent, "PROBLEM", f"{goal} · open → {child_name}/").lines + out.lines
    child = case_new(root, name, goal, parent=parent)
    _write_readme(parent, _readme_text(parent, out), out)  # the cases block of Links draws the child now, not next time
    store.hold(root, child)
    out.say(f"spawned: {child.relative_to(root)} — hand moves to the child; parent waits in phase {cur.n}")
    hints.attach(out, "case_new", root=root)
    return out


def _closed_line(value: str):
    """The `- closed:` State line is el's (written by `done` / `case cancel`, never typed): whole, like `last:` — not counted
    in any limit, never cut (the owner's word, 2026-09-25). Returns (the value, the value) for its old callers."""
    return value, value


def _child_item_check(root: Path, case: Path, text: str, words: str, what: str, retry: str) -> None:
    """A nested case awaited by its parent ends as an item of the parent (F13 counts its text) — held before any
    write and said in the words the agent typed. Feedback 2026-09-29: the refusal spoke of «item 1.7 is 328 chars»,
    an item the agent never wrote, and the child's folder name el appended ate a third of the budget. The item is
    the agent's words only now; the child is named by the item's proof line, which el writes and nobody counts."""
    parent = store.parent_case(case, root)
    if parent is None:
        return
    ptodo = _todo(parent, Outcome())
    phase = next((p for p in ptodo.phases if case.name in p.waits), None)
    n = grammar.visible_len(text)
    if phase is None or n <= grammar.TODO_ITEM_CHARS:
        return
    ref = f"{phase.n}.{_next_number(parent, ptodo, phase)}"
    budget = grammar.TODO_ITEM_CHARS - (n - grammar.visible_len(words))
    own = f" («{text[:len(text) - len(words)].strip()}» is el's word, the rest is yours)" if text != words else ""
    raise StoreError(f"the {what} becomes item {ref} of the parent {parent.name} — an item holds {grammar.TODO_ITEM_CHARS} "
                     f"visible chars{own}: yours is {grammar.visible_len(words)}, at most {budget} fit. Rephrase it, do not "
                     f"cut it: the outcome first, the filler out; the case is named by the item's proof line, not counted. "
                     f"Nothing was written: {retry}", 3)


def _case_tally(case: Path, todo: grammar.Todo, out: Outcome) -> str:
    """How the whole case was accepted, read back from its phase files — for its `closed:` line, at either end (done or
    cancelled); "" when nothing was done, or the case neither asks for two hands nor accepted anything."""
    items = [it for p in todo.phases for it in _closed_phase_items(case, p)]
    if not any(it.done for it in items):
        return ""
    return _acceptance_tally(items) if _two_hands(_readme_text(case, out)) or any(it.accepted for it in items) else ""


def _child_sign(case: Path, messenger: bool) -> str:
    """The signature of a child's outcome at its parent: the hand that ended the child — or, when the parent's half is
    delivered after a cut-off close, «unknown» with the hand that only carried it (Codex, 2026-10-05: the repair signed the
    carrier as the doer)."""
    if messenger:
        return f"harness ? · model ? · session ? · {_now()[0]} · carried after a cut-off close by {_sign_text(case)}"
    return f"{_sign_text(case)} · {_now()[0]}"


def _deliver_cancel_to_parent(root: Path, case: Path, why: str, out: Outcome, messenger: bool = False) -> None:
    parent = store.parent_case(case, root)
    if parent is None:
        return
    ptodo = _todo(parent, out)
    for p in ptodo.phases:
        if case.name in p.waits:
            p.waits.remove(case.name)
            m = _next_number(parent, ptodo, p)
            p.items.append(grammar.Item(p.n, m, True, f"снято: {why}", 0,
                                        evidence=[("file", _child_readme_link(parent, case))]))
            p.items[-1].done_by = _child_sign(case, messenger)  # L8: the hand that ended the child, or «unknown» on a repair
    out.absorb(_write_todo(parent, ptodo))
    _write_readme(parent, _readme_text(parent, out), out)  # `ждёт:` of this child is drawn no more (F6)
    out.lines += log(parent, "DECISION", f"снято → {why} · {case.name}/").lines
    out.say(f"parent updated: {parent.name}")


def _deliver_to_parent(root: Path, case: Path, summary: str, out: Outcome, messenger: bool = False) -> None:
    """The parent's half of a close: the awaited phase stops waiting and gets the child's outcome as a done item, the
    parent's journal hears of it. One helper for both ends of a child — done and cancelled («снято: <why>», which the parent
    records as a DECISION) — and for a close whose parent half was cut off (L7): the parent hears the same either way."""
    if summary.startswith("снято: "):
        return _deliver_cancel_to_parent(root, case, summary[len("снято: "):], out, messenger)
    parent = store.parent_case(case, root)
    if parent is None:
        return
    ptodo = _todo(parent, out)
    awaited = False
    for p in ptodo.phases:
        if case.name in p.waits:
            awaited = True
            p.waits.remove(case.name)
            m = _next_number(parent, ptodo, p)
            # the child's outcome lands at the parent as a done item whose evidence is the child itself
            # (F20: the tool does not write a tick without a kind): file → the child's README
            p.items.append(grammar.Item(p.n, m, True, summary, 0,  # the agent's words only; the proof line names the case
                                        evidence=[("file", _child_readme_link(parent, case))]))
            p.items[-1].done_by = _child_sign(case, messenger)  # L8: the hand that ended the child, or «unknown» on a repair
    out.absorb(_write_todo(parent, ptodo))
    _write_readme(parent, _readme_text(parent, out), out)  # `ждёт:` of this child is drawn no more (F6)
    # the child always reports to its parent, however it was created (F18): an awaited child
    # closes the PROBLEM that spawned it, any other child lands as a RESULT
    out.lines += log(parent, "PROBLEM" if awaited else "RESULT",
                     (f"закрыто → {summary} · {case.name}/" if awaited else f"дело закрыто → {summary} · {case.name}/")).lines
    out.say(f"parent updated: {parent.name} — hand returns to the parent")


# ---- the owner closes the top of the tree (the owner's word, 2026-10-08: «yes» to the proposal after the live map) -------
# Items are accepted by a second hand, a phase's scope by the owner — and the case closed by one agent command. On the
# live map a fresh Sonnet accepted 45 items through subagents and closed the owner's «capital order» in eight minutes;
# every line was true, the whole said more than anyone had checked, and no door asked the owner. The truth is the
# owner's (the concept: «structure and freshness — the tool; truth — the owner»): a top case of the two-hands rule ends
# like an item — the agents' `el done` makes it READY, the owner's word closes it. A nested case is closed by its
# parent's acceptance, as before; a case without the rule closes as before.
READY_PREFIX = "ready: "


def _owner_closes(root: Path, case: Path) -> bool:
    return store.parent_case(case, root) is None and _case_two_hands(case)


def _ready_value(readme_body: str) -> str:
    parsed = grammar.parse_readme(readme_body)
    line = next((ln for ln in parsed.sections.get("State", []) if ln.startswith(f"- {READY_PREFIX}")), "") if not parsed.errors else ""
    return line[len(f"- {READY_PREFIX}"):].strip()


def _ready_words(value: str) -> str:
    """The agents' outcome on the `ready:` line, without its date and el's acceptance tail."""
    return re.sub(r"^\d{4}-\d{2}-\d{2} · ", "", grammar.CLOSED_TALLY_RE.sub("", value).strip())


def done(root: Path, case: Path, summary: str, howto: Optional[str] = None, by: Optional[str] = None) -> Outcome:
    out = Outcome()
    if by is not None and by != "owner":
        raise StoreError(f"`--by {by}` — a case is closed by the owner's word alone: el done --by owner \"his words\"; "
                         f"the agents' part ends at el done \"what came out\"", 2)
    recorded = _closed_words(_readme_text(case, out))
    if recorded:  # closed already: the only thing left to do is the parent's half, if it was cut off (L7)
        parent = store.parent_case(case, root)
        if parent is None or not any(case.name in p.waits for p in _todo(parent, out).phases):
            raise StoreError(f"{case.name} is closed already «{recorded}» — nothing to close, and no parent waits for it", 4)
        _deliver_to_parent(root, case, recorded, out, messenger=True)
        out.say(f"{case.name} was closed already — its outcome as recorded «{recorded}» is delivered to the parent; "
                f"nothing in {case.name} was written again")
        return out
    howto_text = _howto_text(case, howto) if howto else None
    todo = _todo(case, out)
    open_phases = [p for p in todo.phases if not p.done]
    if open_phases:
        raise StoreError("cannot close the case: open phases " + ", ".join(f"{p.n} {p.name}" for p in open_phases), 4)
    live = [(k.name, order.child_status(k)[0]) for k in order.child_cases(case, _is_project(case))]
    live = [f"{n} ({st})" for n, st in live if st != "closed"]
    if live:  # F20: a parent closes only when every child is done or cancelled; BROKEN holds it open (F18)
        raise StoreError("cannot close the case: nested cases still open — " + ", ".join(live) +
                         " → close each (el --case <name> done \"…\") or cancel it with a reason", 4)
    coverage = _case_coverage(case, todo, _readme_text(case, out))
    unproved = [cv for cv in coverage if cv[2] != "proved"]
    if unproved:  # L6: the case's own promise holds its close, as a phase's goal holds the phase's (F12)
        (kind, what), where, status, refs = unproved[0]
        near = _near_promises(case, todo, kind, what)
        more = f" (+{len(unproved) - 1} more promise(s) unproved)" if len(unproved) > 1 else ""
        why = (f"phase {refs} carries it and did not prove it" if status == "promised"
               else "no phase proves it" + (f" — the phases promised {near}: the same in other words?" if near else ""))
        free = max((p.n for p in todo.phases), default=0) + 1
        raise StoreError(f"cannot close the case: it promised {_slot(kind, what)} in Context and {why} → prove it: a phase whose "
                         f"goal carries {_slot(kind, what)}, closed with its proof ({_carry_command(free, _slot(kind, what))}) · or correct "
                         f"the promise to what was proved, in the owner's words: {_promise_fix(where)}{more}", 4)
    words = " ".join(summary.split())
    _child_item_check(root, case, words, words, "summary", f"el done \"<the outcome in at most "
                      f"{grammar.TODO_ITEM_CHARS} chars>\"")
    journal = _journal(case, out)
    by_phase: Dict[str, List[grammar.Event]] = {}
    for e in journal.entries:
        by_phase.setdefault(e.phase, []).extend(e.events)
    unanswered = [ev for evs in by_phase.values() for ev in _unanswered_problems(evs)]
    if unanswered and not howto_text:  # P8 at the size of the case: what no phase close answered is asked once
        raise StoreError(f"cannot close the case: {len(unanswered)} PROBLEM(s) no recipe answers — «{order._short(unanswered[0].text, 60)}»: "
                         f"{HOWTO_ASK}: el done \"{' '.join(summary.split())}\" --howto …", 4)
    summary = " ".join(summary.split())
    owner_closes = _owner_closes(root, case)
    ready = _ready_value(_readme_text(case, out))
    if by == "owner" and not owner_closes:
        raise StoreError(f"{case.name} closes by el done \"what came out\" — the owner's word closes a top case that asks "
                         f"two hands, once its agents made it ready", 2)
    if by == "owner" and not ready:
        raise StoreError(f"the agents' part comes first — el done \"what came out\" makes {case.name} ready; then the "
                         f"owner's word closes it: el done --by owner \"his words\"", 4)
    if owner_closes and by is None:
        if ready:
            raise StoreError(f"{case.name} is ready since {ready.split(' · ', 1)[0]} and awaits the owner's word — tell him "
                             f"what came out; his word said to you: el done --by owner \"his words\" · work goes on: open "
                             f"a phase and the ready line goes by itself", 4)
        if howto_text:
            out.lines += log(case, "DECISION", f"howto: {howto_text}").lines
        date, _ = _now()
        tally = _case_tally(case, todo, out)
        out.lines = log(case, "PHASE", f"дело готово, ждёт слова владельца → {summary}").lines + out.lines  # before the
        text = _set_state_line(_readme_text(case, out), READY_PREFIX,  # README: State is current as of this event
                               f"{date} · {summary}" + (f" · acceptance: {tally}" if tally else ""))
        text = _set_state_line(text, "next: ", None)  # what is next is the owner's word, said by the ready line
        _write_readme(case, text, out, anchor=True)
        out.say(f"ready: {case.name} — the agents' part is done; the owner closes it (this case's rule: two hands)",
                f"tell the owner what came out — his word said to you closes it: el done --by owner \"his words\"")
        return out
    owner_words = ""
    if by == "owner":  # the owner's word closes what the agents made ready: their outcome stays, his words are quoted
        owner_words = summary
        if not owner_words:
            raise StoreError("the owner's words, as he said them: el done --by owner \"…\"", 2)
        summary = _ready_words(ready) or summary
    if howto_text:
        out.lines += log(case, "DECISION", f"howto: {howto_text}").lines
    date, _ = _now()
    tally = _case_tally(case, todo, out)
    # the case's own line carries how its work was accepted; the parent draws its line about the child from it
    closed, shown = _closed_line(f"{date} · {summary}" + (f" · acceptance: {tally}" if tally else "")
                                 + (f" · closed by the owner: «{owner_words}»" if owner_words else ""))
    text = _set_state_line(_readme_text(case, out), "closed: ", shown)
    text = _set_state_line(text, "next: ", None)  # a closed case has no next step — the line would be a lie (2026-09-14)
    text = _set_state_line(text, READY_PREFIX, None)  # ready is over: the owner closed it
    _write_readme(case, text, out, anchor=True)
    out.lines = log(case, "PHASE", f"дело закрыто → {summary}" + (f" · слово владельца: «{owner_words}»" if owner_words else "")).lines + out.lines
    _deliver_to_parent(root, case, summary, out)
    out.say(f"closed: {case.name}")
    if coverage:
        out.say(f"case promises: {len(coverage)} of {len(coverage)} proved — "
                + " · ".join(_slot(*sl) + (f" by phase {refs}" if refs else "") for sl, _, _, refs in coverage))
    if tally:
        out.say(f"acceptance: {tally} → the closed: line, drawn at the parent")
    return out


def case_cancel(root: Path, case: Path, why: str) -> Outcome:
    """The whole case is not needed (F20): open phases collapse with the reason, the case closes as
    «снято», the parent gets one line. Nested cases must already be closed or cancelled."""
    out = Outcome()
    why = " ".join(why.split())
    if not why:
        raise StoreError("cancel needs a reason: el case cancel \"why the case is no longer needed\"", 2)
    todo = _todo(case, out)
    if grammar.is_closed(_readme_text(case, out)):
        raise StoreError(f"{case.name} is already closed", 4)
    live = [f"{k.name} ({order.child_status(k)[0]})" for k in order.child_cases(case, _is_project(case)) if order.child_status(k)[0] != "closed"]
    if live:
        raise StoreError("cannot cancel the case: nested cases still open — " + ", ".join(live) + " → close or cancel each first", 4)
    _child_item_check(root, case, f"снято: {why}", why, "reason", "el case cancel \"<the reason, shorter>\"")
    for p in todo.phases:
        if not p.done:
            out.lines += log(case, "DECISION", _cancel_phase(case, todo, p, why, out), f"p{p.n}").lines
    out.absorb(_write_todo(case, todo))
    date, _ = _now()
    tally = _case_tally(case, todo, out)  # the work done before the cancel was accepted somehow — the line says how
    text = _set_state_line(_readme_text(case, out), "closed: ",
                           _closed_line(f"{date} · снято: {why}" + (f" · acceptance: {tally}" if tally else ""))[1])
    text = _set_state_line(text, "next: ", None)  # nothing is next for a cancelled case
    text = _set_state_line(text, READY_PREFIX, None)  # a cancel ends the wait for the owner too (Codex, 2026-10-08)
    _write_readme(case, text, out, anchor=True)
    out.lines = log(case, "DECISION", f"дело снято → {why}").lines + out.lines
    _deliver_to_parent(root, case, f"снято: {why}", out)
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
    """Feedback pool lives in the elephant-cli clone of the machine the agent works on (env EL_FEEDBACK_DIR overrides,
    e.g. in tests). The reports do not travel by git: `feedback/*` is ignored, so a report with the details of a live
    case never lands in a commit, and anyone may clone the tool while only the maintainer pushes — the owner carries
    the files to the maintainer's clone by hand (the owner's word, 2026-09-25)."""
    import os as _os

    override = _os.environ.get("EL_FEEDBACK_DIR")
    return Path(override) if override else Path(__file__).resolve().parent.parent / "feedback"


def feedback(title: str, expected: str, actual: str, why: str, acceptance: str, repro: str,
             onboarding: str = "") -> Outcome:
    """A report for the maintainer. Every report carries a word on the onboarding block (the owner's word, 2026-09-27):
    the block is the first dose, read before el says anything, and the reporting agent is the only one who lives with
    it — every rewrite of the block so far followed the owner's eye or a rule change, none came from an agent telling
    what the block did to its start, and the last one was never checked by a cold agent. «enough» is a full answer;
    silence would read as one."""
    out = Outcome()
    title = " ".join(title.split())
    missing = [name for name, value in (("a title", title), ("--actual", actual), ("--expected", expected),
                                        ("--onboarding", onboarding.strip())) if not value]
    if missing:
        raise StoreError(f"feedback needs {', '.join(missing)} — title, --actual, --expected and --onboarding are required; "
                         "--onboarding is a word on the Elephant block in your instruction file (el onboarding --show "
                         "prints it): «enough», or the line to add, change or drop; add --repro/--why/--acceptance "
                         "when you can", 2, recovery="el help feedback")
    d, t = _now()
    # the title transliterated like a case name, and a file never overwritten (feedback 2026-09-22: two Cyrillic
    # titles in one minute both became `…-feedback.md`, the second silently erased the first)
    slug = _slug(title)[:60].strip("-") or "feedback"
    folder = feedback_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stem, n = f"{d}-{t.replace(':', '')}-{slug}", 1
    while True:
        path = folder / (f"{stem}.md" if n == 1 else f"{stem}-{n}.md")
        try:
            with path.open("x", encoding="utf-8"):
                break
        except FileExistsError:
            n += 1
    from . import __version__
    # no case name in the header: the pool travels through git, and a case name is the owner's business data
    # (the owner's word 2026-09-22 — a folder name carried a ticket number and an internal API into the pool)
    sections = [f"# {title}", "", f"date: {d} {t} · el {__version__}", ""]
    for heading, text_ in (("Reproduction", repro), ("Actual", actual), ("Expected", expected),
                           ("Why", why), ("Acceptance", acceptance), ("Onboarding", onboarding)):
        if text_:
            sections += [f"## {heading}", text_.strip(), ""]
    path.write_text("\n".join(sections), encoding="utf-8")
    out.say(f"feedback written: {path}")
    # the report is a pause, not the end of the work (the owner's word, 2026-10-06: stop, write, go on, tell at the end)
    out.say(f"go on by your workaround · in your case: el log PROBLEM \"el: {title} — workaround: …\" · "
            "at the end tell the owner the report is there")
    return out


def feedback_wall(which: str, expected: str, title: Optional[str], why: str = "", onboarding: str = "") -> Outcome:
    """`el feedback --wall [K] --expected "…"` — a report from a refusal el kept this session (the polygon, 2026-10-07:
    thirty-odd walls in nineteen sessions and not one report; the agents told the owner, and a report cost a title, the
    verbatim output, the exit code and a word on the block — all of which el had just printed itself). el writes what it
    printed and the commands; the agent writes the one thing el cannot know — what it expected."""
    out = Outcome()
    full = ('the full form: el feedback "title" --actual "…" --expected "…" --onboarding "…" (el help feedback)')
    if store.session_id() == "":
        raise StoreError("el keeps walls per session and sees no session here — " + full, 4)
    walls = store.session_walls()
    if not walls:
        raise StoreError("no refusal kept in this session — nothing to attach; " + full, 4)
    listing = [f"  {k} [exit {w.get('code')}] {_wall_head(w)}  ← {_wall_command(w)[:90]}"
               for k, w in enumerate(walls, 1)]
    if which == "last":
        k = len(walls)
    elif re.fullmatch(r"[0-9]{1,6}", which) and 1 <= int(which) <= len(walls):  # `²` is a digit to isdigit() (Codex)
        k = int(which)
    else:
        raise StoreError(f"--wall {which}: this session kept {len(walls)} wall(s):\n" + "\n".join(listing), 2,
                         recovery="el feedback --wall K --expected \"…\"")
    if not expected.strip():  # a question: which walls are there, and the one line el needs
        out.say(f"walls el kept this session ({len(walls)}):", *listing,
                f"report one: el feedback --wall {k} --expected \"what you expected instead\" — el writes what it printed "
                f"and the commands; --why, --onboarding and a title of yours are welcome, not required")
        return out
    w = walls[k - 1]
    head = _wall_head(w)
    command = _wall_command(w)
    actual = (f"{command}\n\n```\n{w.get('text', '').rstrip()}\n```\nexit {w.get('code')} — written by el from its own "
              f"record of the session — the refusal as el raised it, without what el printed around it (the same-wall "
              f"question, the files put back); it may carry the project's words, nothing of it goes into git as is")
    repro = ("the refusals el kept this session, in order (el keeps refusals, not every command); the reported one is "
             f"{k}:\n" + "\n".join(f"{i}. {_wall_command(x)}  → exit {x.get('code')}" + ("   ← reported" if i == k else "")
                                     for i, x in enumerate(walls, 1)))
    seen = sum(1 for x in walls if x.get("key") == w.get("key"))
    if seen > 1:
        repro += f"\n(the same wall {seen} times this session)"
    out.lines += feedback(title or f"refused: {head}"[:90], expected, actual, why, "", repro,
                          onboarding or "not said — a quick wall report (el feedback --wall)").lines
    return out


def _wall_command(w: dict) -> str:
    """The refused call as the shell would take it back: argument boundaries kept (Codex review, 2026-10-07: a joined
    argv turned `'a; echo b'` into two commands in the report's reproduction)."""
    import shlex
    return "el " + shlex.join(str(a) for a in (w.get("argv") or []))


def _wall_head(w: dict) -> str:
    first = (w.get("text") or "").split("\n")[0]
    return re.sub(r"^el: ERROR \[exit \d+\] ", "", first)[:110]


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
    fresh = _fresh_proofs(case)  # L8: el's rewrites below are not a change of content
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
    store.remember(src)
    store.remember(dst)
    if body is None:
        src.replace(dst)
    else:
        body, n = _rewrite_links(body, src.parent, src, dst, new_base=dst.parent)
        dst.write_text(body, encoding="utf-8")
        src.unlink()
        if n:
            touched.append(f"{new_rel} ({n} of its own)")
    touched += _follow_links(case, src, dst, out, skip=dst)
    _carry_versions(fresh, out)
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
    nothing can close — caught on this tool's own journal within a minute of adding the check.
    A link may point at a file of the project outside the case (`../../.howto/x.md`): the path is read
    as Order prints it — from the case — and from here and from the project root (the polygon,
    2026-10-08: two agents tried both forms of a dead `.howto` link and met «inside the case folder only»)."""
    out = Outcome()
    retire = new.strip().lower() == "none"
    src = _relink_source(case, old)
    shown = Path(os.path.relpath(src, case)).as_posix()
    if src.is_dir():
        raise StoreError(f"{shown} is a folder — relink mends links to a file; a folder moved: el mv old/ new/", 2)
    if src.exists():
        raise StoreError(f"{shown} exists — a link to it is not dead; " + (
            "to retire the links delete or move the file first" if retire else f"to move it and rewrite the links in one go: el mv {old} {new}"), 4)
    if retire:
        fresh = _fresh_proofs(case, None)
        touched = _follow_links(case, src, None, out)
        _carry_versions(fresh, out)
        if "README.md" not in " ".join(touched):
            _refresh_readme(case, out)
        n = sum(int(t.rsplit("(", 1)[1].rstrip(")").split()[0]) for t in touched) if touched else 0
        out.say(f"retired: {shown} — {n} link(s) now literal text `[name]({shown})`" + (f": {', '.join(touched)}" if touched else " (none pointed at it)"))
        return out
    dst = next((d for d in _relink_places(case, new) if d.is_file()), None)
    if dst is None:
        raise StoreError(f"{new} is not a file of the project (paths as Order prints them, from the case: docs/x.md, "
                         f"../../.howto/x.md) — relink points the links at a file that exists; gone for good or an example: "
                         f"el relink {old} none", 4)
    relocated = (src, dst) if case.resolve() in src.parents and case.resolve() in dst.parents else None
    fresh = _fresh_proofs(case, relocated)  # L8: el's rewrites below are not a change of content
    touched = _follow_links(case, src, dst, out)
    _carry_versions(fresh, out)
    if "README.md" not in " ".join(touched):
        _refresh_readme(case, out)
    new_rel = Path(os.path.relpath(dst, case)).as_posix()
    out.say(f"relinked: {shown} → {new_rel}" + (f" · links rewritten: {', '.join(touched)}" if touched else " · no links pointed at it"))
    return out


def _relink_places(case: Path, given: str) -> List[Path]:
    """Where a path the agent typed may lie, inside the project: an absolute or case-qualified path (`.cases/<case>/x`)
    is one place; a relative one is read from the case (as Order prints it), from here and from the project root."""
    project = _project_root(case).resolve()
    raw = given.strip()
    p = Path(raw).expanduser()
    if p.is_absolute():
        found = [p.resolve()]
    else:
        norm = _case_path(case, raw)
        found = [(case / norm).resolve()] if norm != raw else list(dict.fromkeys(
            c.resolve() for c in (case / p, Path.cwd() / p, project / p)))
    return [c for c in found if c == project or project in c.parents]


def _relink_source(case: Path, given: str) -> Path:
    """The one dead target `given` names. Read two ways (from the case, from the project), the link of this case decides;
    two linked readings are refused, never both rewritten (Codex, 2026-10-08: an explicit path rewrote another file's links)."""
    places = _relink_places(case, given)
    if not places:
        raise StoreError(f"{given} leads outside the project — relink mends links to files of this project", 2)
    if len(places) == 1:
        return places[0]
    targets = set(_case_link_targets(case))
    linked = [c for c in places if c in targets]
    if len(linked) > 1:
        forms = " · ".join(str(c) for c in linked)
        raise StoreError(f"{given} names {len(linked)} files the links of this case point at: {forms} — give the one you "
                         f"mean as an absolute path: el relink <path> …", 2)
    return linked[0] if linked else places[0]  # no link decides: the reading from the case, as Order prints it


def _case_link_targets(case: Path) -> List[Path]:
    """Every resolved target the case's own files point at — the three files and its documents and phase files."""
    found: List[Path] = []
    for name in ("README.md", "TODO.md", "JOURNAL.md"):
        try:
            found += order._link_targets(stamp.split(store.read(case, name))[0], case, case)
        except (StoreError, OSError):
            continue
    for f in sorted(case.rglob("*.md")):
        rel = f.relative_to(case)
        if any(part.startswith(".") or part in ("node_modules", "legacy") for part in rel.parts):
            continue
        if any(store.is_case_dir(case / Path(*rel.parts[:i + 1])) for i in range(len(rel.parts) - 1)):
            continue
        if f.parent == case and f.name in store.FILES:
            continue
        try:
            found += order._link_targets(f.read_text(encoding="utf-8", errors="ignore"), f.parent, case)
        except OSError:
            continue
    return found


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
    old_rel = Path(os.path.relpath(src, case)).as_posix()  # a project file outside the case climbs: ../../.howto/x.md
    new_rel = Path(os.path.relpath(dst, case)).as_posix() if dst is not None else None

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
            store.write_file(p, new_text)
            touched.append(f"{rel.as_posix()} ({n})")
    return touched


# ---- dates: what the tool can count -----------------------------------------------------------------
STATE_DUE_RE = re.compile(r"^- due: (\d{4}-\d{2}-\d{2})(?:\s*[·—–-]?\s*(.*))?$", re.M)


def _child_readme_link(parent: Path, child: Path) -> str:
    """`[child-name](child-name/README.md)` — from a normal parent; `.cases/…` from the project case."""
    return _case_link(child.name, _is_project(parent))


def _case_link(name: str, root_mode: bool) -> str:
    """How el points at a nested case from its parent, wherever it draws one — a phase's `waits:`, the State line
    `ждёт:`, the cases block of Links, the proof line of the child's outcome: a link to the child's README, the face
    of the case (F6, F18). Feedback 2026-09-30: `waits:` and `ждёт:` were bare folder names — no click in the editor."""
    return f"[{name}]({order.CASES_DIR + '/' if root_mode else ''}{name}/README.md)"


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
        for it in grammar.flat(p.items):
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
    done = [it for p in todo.phases if not p.done for it in grammar.flat(p.items) if it.done]
    if not done:
        return None
    parts = [f"{k} {n}" for k in grammar.EVIDENCE_KINDS if (n := sum(1 for it in done if any(kd == k for kd, _ in it.evidence)))]
    untyped = sum(1 for it in done if not it.evidence)
    if untyped:
        parts.append(f"untyped {untyped}")
    return f"evidence: {len(done)} done · " + " · ".join(parts) + f" — {EVIDENCE_TRUST}"


# What el itself verified, said next to every count of proofs (feedback 2026-09-22: a well-formed record made
# a run nobody repeated look verified — «check 0 violations» read as «proved»). A file is checked to exist;
# run · ref · owner are recorded as reported. Structure passing is not evidence complete.
EVIDENCE_TRUST = "el checked: file exists, a case file its version · run, ref, owner: as reported"


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
    if overdue:  # named first, by number and date (feedback 2026-09-22: a count «see Order» hid 1.10 a day late)
        parts.append("OVERDUE: " + ", ".join(f"{it.ref} ({d.isoformat()[5:]}, {_when((d - today).days)})" for it, d in overdue)
                     + " — exits in Order")
    if due_today:
        parts.append("due today: " + ", ".join(f"{it.ref} «{it.text}»" for it in due_today))
    if week:
        parts.append("next 7 days: " + ", ".join(f"{it.ref} ({d.isoformat()[5:]})" for it, d in week))
    if deadline:
        d, what = deadline
        parts.append(f"deadline {d.isoformat()}{f' «{what}»' if what else ''} {_when((d - today).days)}")
    for k, ln, d in untils:
        parts.append(f"problem {k} «{order._short(ln, 40)}» until {d.isoformat()} {_when((d - today).days)}")
    return "dates: " + " · ".join(parts)


RULE_ITEMS_LINK_RE = re.compile(r"^\s*- rule:\s*items\s+link\b", re.M | re.I)
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
    shown = ", ".join(f"{it.ref}" for it in blind[:6]) + (f" … +{len(blind) - 6}" if len(blind) > 6 else "")
    return [f"{len(blind)} item(s) without a link to their material — {shown} → el todo edit N.M \"text — [name](docs/file.md)\" "
            f"(this case's rule: items link their material)"]


def _overdue_lines(todo: grammar.Todo, readme_body: str) -> List[str]:
    overdue = _dated(todo, readme_body, dt.date.today())[0]
    return [f"overdue: {it.ref} «{it.text}» was due {d.isoformat()} → el todo done {it.ref} <kind> \"…\" · "
            f"el todo due {it.ref} <date> · el todo cancel {it.ref} \"why\"" for it, d in overdue]


# ---- entry, order and check ---------------------------------------------------------------------
def _journal_headlines(journal: grammar.Journal, limit: int) -> List[str]:
    """The last `limit` entries as headlines only: no body lines, no legacy tool noise
    (`DECISION · todo …` written by v0.7–0.8 for every TODO edit). Bodies stay on disk."""
    total = len(journal.entries)
    lines = [f"# JOURNAL — last {min(limit, total)} of {total} entries (headlines; bodies in JOURNAL.md)"]
    shown, hidden = 0, 0
    for e in journal.entries[:limit]:
        events = [ev for ev in e.events if not (ev.type == "DECISION" and ev.text.startswith("todo "))]
        if not events:
            continue
        if shown >= ENTRY_EVENTS:
            hidden += len(events)
            continue
        lines.append(f"- {e.date} {e.time} · {e.phase}")
        room = ENTRY_EVENTS - shown
        lines.extend(f"  {ev.type} · {ev.text}" for ev in events[:room])
        shown += min(len(events), room)
        hidden += max(len(events) - room, 0)
    if hidden:
        lines.append(f"  … +{hidden} event line(s) more in these entries — JOURNAL.md (the entry shows {ENTRY_EVENTS})")
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
            _refresh_parents(case, out)
            return derived
        except StoreError as e:
            out.warn(f"README not refreshed — {e}")
    return body


def _ended_phase_lines(case: Path, todo: grammar.Todo, journal: Optional[grammar.Journal], readme_body: str = "") -> List[str]:
    """A phase whose every item ended is ready to end itself — the moment the owner decides: close it,
    or add what is still missing. The tool forces the downward rule (an open item holds its phase);
    the upward one is shown here (feedback 2026-09-14: phase 4 stood open over one [x] item and
    `order` said everything was in place). A phase with no items says nothing — nothing ended there.
    The line names what the close still needs, so the command it offers is one the tool will take."""
    lines: List[str] = []
    cur = _flying(case, todo)
    for p in sorted(todo.phases, key=lambda x: x.n):
        if p.done or not p.items or any(not it.done for it in p.items):
            continue
        prev = max((q for q in todo.phases if q.n < p.n), key=lambda q: q.n, default=None)
        if (cur is not None and cur.n != p.n and not _phase_file(case, p.n, p.name).exists()
                and (prev is None or prev.done)):  # L4: it cannot close from the plan, and opening asks for the detour (F26)
            lines.append(f"phase {p.n} {p.name}: every item ended, planned and never opened while {cur.n} {cur.name} is in flight → "
                         f"pause it for this one: el phase open {p.n} --why \"what came up\" ({cur.n} resumes when {p.n} ends), "
                         f"then el phase close {p.n} \"what came out\"")
            continue
        needs: List[str] = []
        if journal is not None:
            for m in _closing_checks(case, p, journal):
                if "result:" in m or "is missing (F12)" in m:
                    continue
                needs.append((m.split(" → ", 1)[1] if " → " in m else m.split(": ", 1)[-1]).split(" · or")[0].strip())
        ask_howto = journal is not None and bool(_unanswered_problems(_events_for_phase(journal, f"p{p.n}")))
        if ask_howto:
            needs.append('the recipe question: --howto ".howto/<verb>.md" · or --howto "none: why"')
        flags = ((" --reflect \"…\" --align \"…\"" if any("reflect:" in n or "align:" in n for n in needs) else "")
                 + (" --howto \"…\"" if ask_howto else ""))
        one = f" · or in one command: el phase close {p.n} \"…\"{flags}" if flags else ""
        unaccepted = [it for it in grammar.flat(p.items) if it.done and not it.accepted] if _two_hands(readme_body) else []
        if unaccepted:  # two hands: the second hand before the close (feedback 2026-09-25: Order used to say «close it»)
            first = f"{unaccepted[0].ref}"
            ms = sorted(it.m for it in unaccepted)
            many = (", ".join(it.ref for it in unaccepted) if any(it.k for it in unaccepted)  # F25: sub-items by name
                    else f"{p.n}.{ms[0]}-{p.n}.{ms[-1]}" if len(ms) > 1 else first)
            lines.append(f"phase {p.n} {p.name}: every item ended ({len(p.items)} done), {len(unaccepted)} not accepted → a fresh session "
                         f"accepts first: el todo brief {first} (the owner's word instead: el todo accept {many} --by owner \"…\"); "
                         f"then close: el phase close {p.n} \"what came out\"" + (f" — also: {' · '.join(needs)}{one}" if needs else ""))
            continue
        lines.append(f"phase {p.n} {p.name}: every item ended ({len(p.items)} done) → close it: el phase close {p.n} \"what came out\""
                     + (f" — first: {' · '.join(needs)}{one}" if needs else "")
                     + f" · or add what is missing: el todo add {p.n} \"…\"")
    return lines


def _unready_lines(case: Path, root: Path, todo: grammar.Todo, readme_body: str) -> List[str]:
    """The owner's case whose every phase ended and every child closed, neither ready nor closed: the moment of decision
    is named, not forced (the polygon, 2026-10-08, pm-haiku-13: four sessions and two more wrote «awaits the owner» into
    next: as prose, Order said ✓, and the case hung open with nothing for the owner to close). Two honest exits."""
    if not todo.phases or any(not p.done for p in todo.phases) or _ready_value(readme_body) or grammar.is_closed(readme_body):
        return []
    if not _owner_closes(root, case):
        return []
    if any(order.child_status(k)[0] != "closed" for k in order.child_cases(case, _is_project(case))):
        return []
    free = max(p.n for p in todo.phases) + 1
    return [f"every phase ended and the case is not said ready — the agents' part ends with el done \"what came out\" "
            f"(ready: the owner's word closes it) · more work first: el phase plan {free} \"Name\" --goal \"…\""]


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
        lines.extend(_closed_wait_lines(case, todo_now))       # waiting for a child that closed, its close cut off (L7)
        lines.extend(_ended_phase_lines(case, todo_now, journal, readme_body))  # every item ended: accept, then close (F20, F23)
        lines.extend(_promise_lines(case, todo_now))               # a promised proof nobody works towards (F12)
        lines.extend(_case_promise_lines(case, todo_now, readme_body))  # the same, one size up: the case's promise (L6)
        lines.extend(_expect_gap_lines(case, todo_now))            # an item of a running phase with no expectation (F22)
        lines.extend(_running_order_lines(case, todo_now))         # the phase in flight is held to the current form
        lines.extend(_refuted_lines(todo_now))                     # a fact resting on a refuted one (the fact chain)
        lines.extend(_stalled_lines(todo_now, journal))            # an item sent back again and again is stuck (F23)
        lines.extend(_later_lines(todo_now, journal))              # a thought the boundaries keep passing by (F24)
        lines.extend(_scope_lines(case, todo_now, readme_body, journal))  # a running phase without the owner's scope (F24)
        lines.extend(_unaccepted_lines(case, todo_now, readme_body))  # done by one hand, not yet accepted by another (F23)
        lines.extend(_unready_lines(case, root, todo_now, readme_body))  # the owner's case ended below, not said ready
    except StoreError:
        pass
    lines.extend(onboarding.order_lines(_project_root(case)))  # S6: a block el cannot keep current (edited or pasted by hand)
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


def _entry_head(case: Path, root: Path, readme_body: str, todo: grammar.Todo, journal: grammar.Journal,
                issues: List[str]) -> List[str]:
    """What to do now — the thread, the counts, Order and the hint: the head of the entry, and of a bare `el readme`
    (the polygon, 2026-10-07: fresh sessions came in through `el readme`, saw the README alone and missed the line that
    told them they were the second hand). Read-only."""
    out = Outcome()
    thread = _thread_line(case, todo, readme_body, issues) if not todo.errors else None
    if thread:
        out.say(thread, "")  # what is subordinate to what — the goal, the phase, the item and why, the next step (F24)
    if todo.errors:  # silence is not «nothing due»: what could not be counted says so (feedback 2026-09-22)
        out.say(f"dates · unblocked · evidence NOT counted — TODO.md is not parsable ({len(todo.errors)} error(s)) → el check", "")
    dates = _dates_line(todo, readme_body) if not todo.errors else None
    if dates:
        out.say(dates, "")  # what the tool can count: due today, this week, overdue, the deadline
    unblocked = _unblocked_line(case, todo) if not todo.errors else None
    if unblocked:
        out.say(unblocked, "")  # candidates by the dependency graph (F19) — the owner's `next:` stays the direction
    evidence = _evidence_line(todo) if not todo.errors else None
    if evidence:
        out.say(evidence, "")  # what the done items stand on (F20): file · ref · run · owner — counted, never nagged
    acceptance = (_acceptance_line(todo, readme_body, journal if not journal.errors else None,
                                   changed=len({(p.n, it.m) for p, it, *_ in _changed_proofs(case, todo) if it.accepted}))
                  if not todo.errors else None)
    if acceptance:
        out.say(acceptance, "")  # done by one hand, accepted by another (F23) — counted; the gaps are Order lines
    facts_line = _facts_line(case, todo, None) if not todo.errors else None
    if facts_line:
        out.say(facts_line, *_facts_shown(case, todo, journal if not journal.errors else None), "")  # the facts themselves
    howto = _howto_line(case)
    if howto:
        out.say(howto, "")
    known = knowledge_line(root)
    if known:
        out.say(known, "")  # what the project already knows, before the plan (the polygon, 2026-10-08)  # what the project already knows how to do — before the task, not only when stuck
    # what to do now comes first, the case on disk after it (the polygon, 2026-10-07; the owner's word: «turn it over»):
    # fresh agents read the entry as `el | head -60`, and Order and the hint, last, were never seen — 21K chars on a
    # 63-file case. The hint stood last because a model weighs the last line most; a line it never reads weighs nothing.
    if issues:
        out.say(f"## Order — {len(issues)} thing(s) to put back", *(f"- {ln}" for ln in issues), "")
    else:
        out.say("## Order", "- ✓ everything in place: files carry summaries, Links follow the files, State is current", "")
    if not todo.errors:  # one hint, derived from the case, right under Order: the two say what to do now
        before = len(out.lines)
        hints.attach(out, "entry", case=case, todo=todo, journal=journal if not journal.errors else None,
                     phase_file_exists=lambda p: _phase_file(case, p.n, p.name).exists(),
                     repeats=order.links_repeating_cards(root, readme_body))
        if len(out.lines) > before:
            out.say("")
    return out.lines


def _other_open_cases(root: Path, case: Path) -> List[str]:
    """The open cases besides the one in hand, a tree as its top: a nested case is reached through its parent, which
    names it on its own line (the live migration of 2026-10-07: a map and forty-one children were listed as forty-two
    equal names, and the map, where three items waited for a second hand, drowned among its own children)."""
    every = store.all_cases(root)
    known = set(every)
    open_cases = [c for c in every if store.is_open(c)]
    is_open = set(open_cases)

    def top(c: Path) -> Path:  # the highest open case above c — a closed parent does not hide its open children; in root
        t, p = c, store.parent_case(c, root)  # mode the project case is the parent of the top-level ones (Codex, 2026-10-07)
        while p is not None and p in known and p != c:
            if p in is_open:
                t = p
            p = store.parent_case(p, root)
        return t
    nested: Dict[Path, int] = {}
    for c in open_cases:
        if c != case and top(c) != c:
            nested[top(c)] = nested.get(top(c), 0) + 1
    out = []
    for c in open_cases:
        if c == case or top(c) != c:
            continue
        k = nested.get(c, 0)
        out.append(c.name + (" (from before el)" if store.legacy_files(c) else "")
                   + (f" (+{k} open nested — el case list)" if k else ""))
    return out


def entry(root: Path, case: Path) -> Outcome:
    out = Outcome()
    names = store.chain(case, root)
    legacy_here = store.legacy_files(case)
    if legacy_here:  # a case el cannot read yet: named, not poured onto the screen (a live project, 2026-09-25: 27 KB)
        return _legacy_entry(root, case, names, legacy_here)
    out.say(f"el · case in hand: {' › '.join(names)}", "")
    refreshed = onboarding.refresh(_project_root(case))  # the block in CLAUDE.md / AGENTS.md follows the one el ships
    if refreshed:
        out.say(*refreshed, "")
    others = _other_open_cases(root, case)
    if others:
        out.say("other open cases: " + " · ".join(others) + " — switch: `el case use <name>`", "")
    readme_body = _refresh_readme(case, out)
    todo_body, _ = stamp.split(store.read(case, "TODO.md"))
    todo = grammar.parse_todo(todo_body)
    # phase lines follow their files (F18); a bare `waits:` name el wrote before 1.31.0 becomes a link (F6)
    if not todo.errors and (_derive_todo(case, todo) or BARE_WAITS_RE.search(todo_body)):
        try:
            fresh = render_todo(todo, _two_hands(readme_body), _is_project(case))
            out.absorb(store.write(case, "TODO.md", fresh))
            todo_body = fresh
            out.say("TODO refreshed: open phase lines follow their phase files (goal · path), nested cases are links")
        except StoreError as e:
            out.warn(f"TODO not refreshed — {e}")
    journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
    issues = _order_lines(case, root, readme_body, journal)  # before the thread: a debt below is a step of the thread
    out.lines += _entry_head(case, root, readme_body, todo, journal, issues)
    out.say(ENTRY_BODY_MARK, "")
    body_from = len(out.lines)
    out.say(readme_body.rstrip("\n"), "")
    if not todo.errors:
        shown, collapsed = render_todo_entry(todo, _two_hands(readme_body), _is_project(case))
        out.say(shown.rstrip("\n"))
        if collapsed:
            out.say(f"({collapsed} done item(s) collapsed here — result and proofs: TODO.md · one item in full: el todo show N.M)")
        out.say("")
    else:
        out.say(todo_body.rstrip("\n"), "")
    parked = _parked_line(case, todo, journal if not journal.errors else None) if not todo.errors else None
    if parked:
        out.say(parked, "")  # knowledge parked under a planned phase has a moment of return — counted until then (F22)
    if journal.entries:
        out.say(*_journal_headlines(journal, ENTRY_LIMIT), "")
    body_to = len(out.lines)
    out.say(f"how to work: el help start · what goes where: el help where · rules: {_rules_pointer(root)} · full check: el check")
    total = "\n".join(out.lines)
    if len(total) > MAX_SCREEN:
        # the head — the thread, the counts, Order, the hint — is what the entry is FOR: cut the body, keep head and footer
        head, body, foot = out.lines[:body_from], out.lines[body_from:body_to], out.lines[body_to:]
        room = max(MAX_SCREEN - len("\n".join(head + foot)) - 120, 0)
        out.lines = head + ["\n".join(body)[:room], "", f"[body truncated at {room} chars — README/TODO/JOURNAL are on disk]", ""] + foot
    return out


def _legacy_entry(root: Path, case: Path, names: List[str], legacy: List[tuple]) -> Outcome:
    """The entry when the case in hand is from before el (a live project, 2026-09-25: the case touched last was one el
    cannot read, and the entry poured its raw README and TODO — 27 KB — while Order said «migrate»). The files stay on
    disk as they are; the screen says what the case is, the one way in (`el migrate`), and el's own open cases."""
    out = Outcome()
    out.say(f"el · case in hand: {' › '.join(names)} — from before el: el reads it only after migration", "")
    out.say(f"legacy file(s) outside Elephant's grammar, never stamped: {', '.join(n for n, _ in legacy)} → {store.MIGRATE_HINT}")
    readme = store.file_path(case, "README.md")
    title = ""
    if readme.exists():
        first = next((ln for ln in readme.read_text(encoding="utf-8", errors="replace").split("\n") if ln.strip()), "")
        title = first.lstrip("# ").strip()
    count = sum(1 for p in case.rglob("*") if p.is_file())
    out.say(f"  what it is: «{order._short(title or case.name, 80)}» · {count} file(s) in the folder — not shown, they stay as they are", "")
    others = [(c, order.child_status(c)) for c in store.all_cases(root) if c != case and store.is_open(c)]
    live = [(c, st) for c, st in others if st[0] == "open"]
    if live:
        out.say("el's open cases — switch: el case use <name>",
                *(f"  {c.name} — {order.case_desc(st)}" for c, st in live[:6]), "")
    pre = [c for c, st in others if st[0] == "legacy"]
    if pre:
        out.say(f"other cases from before el, open: {', '.join(c.name for c in pre[:6])} — el --case <name> migrate", "")
    out.say(f"how to work: el help migrate · el help start · every case here: el case list")
    return out


def _closed_phase_items(case: Path, p: grammar.Phase) -> List[grammar.Item]:
    """The items of a closed phase, read back from its file (`## Items at close`) with their pockets."""
    pf = _phase_file(case, p.n, p.name)
    if not pf.exists():
        return []
    items: List[grammar.Item] = []
    node: Optional[grammar.Item] = None  # the item or sub-item whose lines are being read
    section = ""
    for ln in pf.read_text(encoding="utf-8").split("\n"):
        if ln.startswith("## "):
            section = ln[3:].strip()
            continue
        if section not in ("Items at close", "Items at cancel"):
            continue
        m = re.fullmatch(rf"- {p.n}\.(\d+) ([✓✗]) (.*)", ln)
        if m:
            text, kind, proof = grammar.split_evidence(m.group(3))  # an item closed before 1.10.0 keeps its proof inline
            text, _, after = _split_suffixes(grammar.TALLY_RE.sub("", text))
            items.append(grammar.Item(p.n, int(m.group(1)), m.group(2) == "✓", text, 0, after=after,
                                      evidence=[(kind, proof)] if kind else []))
            node = items[-1]
            continue
        ms = re.fullmatch(rf"  - {p.n}\.(\d+)\.(\d+) ([✓✗]) (.*)", ln)  # F25: a sub-item under the item above
        if ms and items and int(ms.group(1)) == items[-1].m:
            text, reason = ms.group(4), ""
            if grammar.CANCELLED_SUFFIX in text:
                text, reason = text.rsplit(grammar.CANCELLED_SUFFIX, 1)
            text, _, after = _split_suffixes(text)
            node = grammar.Item(p.n, items[-1].m, ms.group(3) == "✓", text, 0, after=after)
            node.k, node.cancelled, node.cancel_reason = int(ms.group(2)), bool(reason), reason.strip()
            items[-1].subs.append(node)
            continue
        pocket = re.fullmatch(r"(  |    )- (why|note|expect|result|fact|done|accepted): (.+)", ln)
        if pocket and items:
            target = items[-1] if len(pocket.group(1)) == 2 else (node or items[-1])  # a sub-item's pockets: two spaces deeper
            node = target
            name = {"note": "notes", "done": "done_by"}.get(pocket.group(2), pocket.group(2))
            setattr(target, name, target.notes + [pocket.group(3)] if name == "notes" else pocket.group(3))
            continue
        ev = re.fullmatch(r"(\s+)- (file|ref|run|owner)(?:: (.+))?", ln)
        if ev and items:
            target = node if node is not items[-1] and len(ev.group(1)) >= 6 else items[-1]
            target.evidence.append((ev.group(2), (ev.group(3) or "").strip()))
    return items


def facts(case: Path, journal: Optional[grammar.Journal] = None) -> Outcome:
    """`el facts` — the fact chain of the case, rendered, never typed (the owner's word, 2026-09-17: a search tree
    where the branches that worked became facts, the branches that did not stayed as dead ends, and the next agent
    starts from proved facts, as in physics). Made of `fact:` lines only: ✓ established (done) · · expected (open)
    · ? under question (rests on an item open again) · ✗ dead branch (cancelled, from the journal). Results without
    a fact are work, not knowledge: counted, not listed."""
    out = Outcome()
    todo = _todo(case, out)
    journal = journal or _journal(case, out)
    by_ref: Dict[str, grammar.Item] = {}
    per_phase: List[Tuple[grammar.Phase, List[grammar.Item]]] = []
    for p in sorted(todo.phases, key=lambda x: x.n):
        its = grammar.flat(_closed_phase_items(case, p) if p.done else list(p.items))  # F25: sub-items carry facts too
        per_phase.append((p, its))
        for it in its:
            by_ref[f"{it.ref}"] = it
    dead = []
    for e in journal.entries:
        for ev in e.events:
            m = re.match(r"^снято ((?:\d+\.\d+(?:\.\d+)? «[^»]*»(?:, )?)+) — (.+)$", ev.text)
            if ev.type == "DECISION" and m:
                for ref, text in re.findall(r"(\d+\.\d+(?:\.\d+)?) «([^»]*)»", m.group(1)):
                    if ref not in by_ref:  # a sub-item cancelled and reopened is alive again — its fact line speaks for it
                        dead.append((ref, text, m.group(2), e.date))
    established = [it for its in (i for _, i in per_phase) for it in its if it.done and it.fact]
    pending = [it for its in (i for _, i in per_phase) for it in its if not it.done and it.fact]
    def shaky(it):
        return [r for r in it.after if r in by_ref and not by_ref[r].done]
    changed = {f"{it.ref}" for p, it, *_ in _changed_proofs(case, todo)}  # L8: done against another version
    question = [it for it in established if shaky(it) or f"{it.ref}" in changed]
    work_only = sum(1 for its in (i for _, i in per_phase) for it in its if it.done and not it.fact)
    out.say(f"facts — {case.name} · {len(established) - len(question)} established · {len(question)} under question · "
            f"{len(pending)} expected · {len(dead)} dead branch(es) · {work_only} done item(s) without a fact (work, not knowledge)")
    docs = _knowledge_docs(store.find_root())
    if docs:  # what the project knows by document — every case's, not this one's alone
        out.say(f"knowledge documents of the project ({len(docs)}) — read before you plan:")
        for k, name, f, summary in docs:
            out.say(f"  {name} ({k.name})" + (f" — {summary}" if summary else "") + f" — cat {_sh_path(_from_here(f))}")
    for p, its in per_phase:
        rows = [it for it in its if it.fact]
        dead_here = [d for d in dead if d[0].startswith(f"{p.n}.")]
        if not rows and not dead_here:
            continue
        out.say(f"phase {p.n} {p.name}" + (" (closed)" if p.done else ""))
        for it in sorted(rows, key=lambda x: (x.m, x.k)):
            ref = f"{it.ref}"
            sh = shaky(it) if it.done else []
            moved = it.done and ref in changed
            mark = "?" if sh or moved else ("✓" if it.done else "·")
            tail = (f"   ← rests on {', '.join(sh)}, open again" if sh else
                    f"   ← its proof changed since done: el todo show {ref}" if moved else
                    (f"   ← after: {', '.join(it.after)}" if it.after else ""))
            out.say(f"  {mark} {ref} {it.fact}{tail}")
            for k, pr in it.evidence:
                out.say(f"        {k}: {pr}".rstrip())
            if not it.done and it.expect:
                out.say(f"        expect: {it.expect}")
        for ref, text, why, date in sorted(dead_here):
            out.say(f"  ✗ {ref} {text}   ← снято {date}: {why}")
    if not any(ln.startswith(("phase ", "knowledge documents")) for ln in out.lines[1:]):
        out.say("  no fact lines yet — a done item that established something: el todo fact N.M \"what is now known\"; "
                "what it is for: el help facts")
    return out


def _howto_line(case: Path) -> Optional[str]:
    """The recipes of the project by name — what it already knows how to do (the owner's word, 2026-09-27: «how-to is how
    to do things, so you know what you can do»). Rendered, like Links from `summary:`: the block teaches the habit, only el
    can list this project's recipes. Measured the same day: 30 PROBLEM events in live projects, not one recipe; the entry
    never named `.howto/`, so a recipe was met only by a grep after the wall. Nothing is said while there are none."""
    folder = _project_root(case) / ".howto"
    names = sorted(p.stem for p in folder.glob("*.md")) if folder.is_dir() else []
    if not names:
        return None
    return (f"howto: {len(names)} recipe(s) — what this project already knows how to do: {' · '.join(names)} — "
            f"taking a task, open its recipe; stuck: grep -ril \"<words>\" .howto/")


# ---- knowledge documents (the polygon and the owner's word, 2026-10-08) ------------------------------------------------
# Agents keep what they found in a document — a table of closed paths with a source on every row (155 rows in one run,
# 33 of 41 digests of a live migration) — never one fact per item (0 facts in 371 done; asked 7 times, answered 0). The
# owner: «why not record links to these documents?». Measured the same day: the next agent, planning in a NEW case while
# the knowledge lay in a sibling case, never opened it (0 of 2) and proposed two closed paths again in each plan; with a
# line on the entry naming the document — opened at its third call (2 of 2), closed paths kept out. Printing the content
# on entry added nothing to the line. So: a link line in Context, the entry of every case of the project names it.
KNOWLEDGE_LINE_RE = re.compile(r"^- knowledge:\s*(.*)$")
KNOWLEDGE_SHOWN = 3  # documents named on the entry; `el facts` lists every one


def _knowledge_docs(root: Path) -> List[Tuple[Path, str, Path, str]]:
    """(case, name, file, summary) for every `- knowledge: [name](path)` line in the Context of any case of the project —
    open or closed: knowledge outlives the case that found it. A link that does not resolve is the README's own refusal
    (F16), never named here."""
    found: List[Tuple[Path, str, Path, str]] = []
    try:
        cases = store.all_cases(root)
    except StoreError:
        return found
    for c in cases:
        try:
            body = stamp.split(store.read(c, "README.md"))[0]
        except (StoreError, OSError, ValueError):  # UnicodeDecodeError too: a legacy README never breaks the entry (Codex, 2026-10-08)
            continue
        parsed = grammar.parse_readme(body)
        if parsed.errors:
            continue
        for ln in parsed.sections.get("Context", []):
            m = KNOWLEDGE_LINE_RE.match(ln)
            if not m:
                continue
            for name, target in re.findall(r"\[([^\]]+)\]\(([^)\s]+)\)", m.group(1)):
                f = (store.file_path(c, "README.md").parent / target.split("#")[0]).resolve()
                if f.is_file():
                    found.append((c, name, f, _doc_summary(f)))
    return found


def _doc_summary(f: Path) -> str:
    return (order.read_summary(f) or "") if f.suffix.lower() == ".md" else ""  # the canonical scan, as Links reads it


def _sh_path(p: str) -> str:
    """A path the agent runs as printed: bare when the shell keeps it whole, quoted otherwise (Codex, 2026-10-08:
    `cat docs/q&a.md` ran `cat docs/q` in the background)."""
    return p if re.fullmatch(r"[\w./@%+,:=-]+", p) else _sh(p)


def _from_here(f: Path) -> str:
    try:
        return Path(os.path.relpath(f, Path.cwd())).as_posix()
    except ValueError:
        return str(f)


def knowledge_line(root: Path) -> Optional[str]:
    """`knowledge: …` — what this project already knows, by document, with the command that reads it: on the entry of
    every case and at `case new`, the moment a task starts."""
    docs = _knowledge_docs(root)
    if not docs:
        return None
    shown = docs[:KNOWLEDGE_SHOWN]
    parts = " · ".join(f"{name} ({c.name})" + (f": {summary}" if summary else "") for c, name, _, summary in shown)
    more = f" · +{len(docs) - len(shown)} more — el facts" if len(docs) > len(shown) else ""
    return (f"knowledge: {len(docs)} document(s) of what this project already knows — {parts}{more} — before you plan or "
            f"propose a step, read it: cat {' '.join(_sh_path(_from_here(f)) for _, _, f, _ in shown)}")


def _knowledge_offer(case: Path) -> Optional[str]:
    """At a phase close — the exit of a piece of work (the owner's word, 2026-10-07: «at the output facts should be
    written»): when the case keeps documents and names none as knowledge, one line with the door and its documents. el
    does not judge which document is knowledge; it names the door and the candidates, once per close."""
    try:
        body = stamp.split(store.read(case, "README.md"))[0]
    except StoreError:
        return None
    parsed = grammar.parse_readme(body)
    if parsed.errors or any(KNOWLEDGE_LINE_RE.match(ln) for ln in parsed.sections.get("Context", [])):
        return None
    listed = {k[1].split("/")[0] for k in (order._classify(ln.lstrip(), case) for ln in parsed.sections.get("Links", []))
              if k[0] == "folder"}  # root mode reads only the folders README lists, as Links does (Codex, 2026-10-08)
    docs = [d for f in order.content_folders(case, _is_project(case), listed) for d in f.all_docs() if d.summary]
    if not docs:
        return None
    docs.sort(key=lambda d: -d.path.stat().st_size)
    names = " · ".join(d.rel for d in docs[:3]) + (f" +{len(docs) - 3}" if len(docs) > 3 else "")
    return (f"knowledge: does a document of this case hold what the project now knows — paths closed, things measured, "
            f"each with its source? name it, and the entry of every case shows it: el readme add context \"knowledge: "
            f"[name](path) — what it holds\" — this case's documents: {names} · none is: go on — el help facts")


def _facts_line(case: Path, todo: grammar.Todo, journal: Optional[grammar.Journal]) -> Optional[str]:
    """`facts: 5 established · 1 under question · 2 expected — el facts` on entry, when the case has any."""
    by_ref = {f"{it.ref}": it for it in _all_items(todo)}
    est = [it for it in _all_items(todo) if it.done and it.fact]
    changed = {f"{it.ref}" for p, it, *_ in _changed_proofs(case, todo)}
    q = [it for it in est if any(r in by_ref and not by_ref[r].done for r in it.after) or f"{it.ref}" in changed]
    pend = [it for it in _all_items(todo) if not it.done and it.fact]
    if not est and not pend:
        # zero facts is said, not hidden, once work is done (feedback 2026-09-22: 25 done, 0 facts, the line silent)
        done = [it for p in todo.phases if not p.done for it in p.items if it.done]
        if len(done) < 3:
            return None
        # the difference is said where the zero is (a live report, 2026-10-02: «a detailed result reads as the fact
        # already» — the line said «work, not yet knowledge» and left the two words to be told apart in the help)
        return (f"facts: 0 established over {len(done)} done items — a result says what the work did, a fact what is now "
                "true that the next step stands on (not every item has one): el todo fact N.M '…' · el help facts")
    return (f"facts: {len(est) - len(q)} established" + (f" · {len(q)} under question" if q else "")
            + (f" · {len(pend)} expected" if pend else "") + " — el facts")


FACTS_SHOWN = 8  # the newest facts on the entry; the whole chain is `el facts`


def _facts_shown(case: Path, todo: grammar.Todo, journal: Optional[grammar.Journal] = None) -> List[str]:
    """The facts themselves on the entry, the newest first (the owner's word, 2026-10-07: «with a million of context,
    3–6 thousand on entry is nothing — what matters is that it reads all of it»): the next agent stands on what is
    known before its first command, instead of a count it would have to open. A fact under question says so."""
    by_ref = {f"{it.ref}": it for it in _all_items(todo)}
    changed = {f"{it.ref}" for p, it, *_ in _changed_proofs(case, todo)}
    est = [it for it in _all_items(todo) if it.done and it.fact]
    if journal is not None:  # newest by the journal — the RESULT that last named the item — not by TODO position (Codex)
        events = [ev for ev in journal.newest_first() if ev.type == "RESULT"]
        age = {f"{it.ref}": next((k for k, ev in enumerate(events) if _result_names(ev.text, f"{it.ref}")), len(events))
               for it in est}
        est = sorted(est, key=lambda it: age[f"{it.ref}"], reverse=True)  # oldest first, as the TODO order was
    lines = []
    for it in reversed(est[-FACTS_SHOWN:]):
        q = any(r in by_ref and not by_ref[r].done for r in it.after) or f"{it.ref}" in changed
        lines.append(f"  {'?' if q else '✓'} {it.ref} {it.fact}" + ("  (under question: el facts)" if q else ""))
    if len(est) > FACTS_SHOWN:
        lines.append(f"  … {len(est) - FACTS_SHOWN} more — el facts")
    return lines


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
        fresh = _fresh_proofs(case)  # L8: a summary line el writes into a document is not the author's change
        changed = order.adopt(case, fallback)
        _carry_versions(fresh, out)
        for rel in changed:
            out.say(f"summary written into {rel} (from its Links description)")
        if not changed:
            out.say("nothing to adopt: every described file already carries its own summary")
    readme_body = _refresh_readme(case, out)
    journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
    issues = _order_lines(case, root, readme_body, journal)
    if issues:
        out.say(f"order — {len(issues)} thing(s) to put back{_refused_note()}:", *(f"- {ln}" for ln in issues))
    else:
        out.say(f"order: ✓ everything in place{_refused_note()}")
    return out


def _refused_note() -> str:
    """The lines an agent reads to verify its work say what of it never landed (the live migration of 2026-10-07: el
    refused 31 commands of one session — a README, twenty-four ticks on closed phases — every one sent to /dev/null by a
    helper script; the agent closed with `el check --all | tail -1` → «violations: 0 · warnings: 0» and reported the
    migration done and clean). The work the agent believes it did is not there; the count rides on the line it reads,
    not on a line below it. It says the count alone: a refused `check` still appends to checks.log (Codex, 2026-10-07)."""
    n = len(store.session_walls())
    return f" · refused this session: {n} command(s) — el feedback --wall lists them" if n else ""


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


def _grouped_warnings(findings) -> List[str]:
    """File warnings for `check`, one line per rule and message shape: «F2 · pointer line over 150 — lines 14, 15,
    18 (3 lines)» instead of three lines that differ only in numbers. `warnings: N` counts lines the reader can act on."""
    groups: Dict[Tuple[str, str], List[int]] = {}
    messages: Dict[Tuple[str, str], List[str]] = {}
    singles: List[str] = []
    for f in findings:
        if f.line == 0:
            singles.append(str(f))
            continue
        key = (f.rule, re.sub(r"\d+", "N", f.message))
        groups.setdefault(key, []).append(f.line)
        messages.setdefault(key, []).append(f.message)
    out = list(singles)
    for key, lines in groups.items():
        # a number shared by every line stays (the limit, 150); only the numbers that differ become N — found 2026-09-25:
        # «pointer line is N visible chars, over N» hid the limit, and a single line lost its own numbers
        parts = [re.split(r"(\d+)", m) for m in messages[key]]
        shape = "".join(bit if i % 2 == 0 or len({pp[i] for pp in parts}) == 1 else "N" for i, bit in enumerate(parts[0]))
        if len(lines) == 1:
            out.append(f"{key[0]} · line {lines[0]} · {shape}")
        else:
            shown = ", ".join(str(n) for n in lines[:6]) + (f" … +{len(lines) - 6}" if len(lines) > 6 else "")
            out.append(f"{key[0]} · {shape} — lines {shown} ({len(lines)} lines)")
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
            for line in _grouped_warnings(r.warnings):  # one line per rule, not one per old line (2026-09-17)
                out.warn(f"{case.name}/{name}: {line}")
            if r.stamp_state in ("mismatch", "not-last"):
                out.warn(f"{case.name}/{name}: stamp {r.stamp_state} — written bypassing Elephant (S4)")
                log_lines.append(f"{date} {time} · {case.name} · {name} · S4 · stamp {r.stamp_state}")
        for pf in sorted((case / "phases").glob("*.md")) if (case / "phases").exists() else []:
            r = grammar.parse_phase_file(pf.read_text(encoding="utf-8"))
            for f in r.errors:
                out.say(f"x {case.name}/phases/{pf.name}: {f}")
                log_lines.append(f"{date} {time} · {case.name} · phases/{pf.name} · {f.rule} · {f.message}")
                errors += 1
        try:  # the running phase is the write door: a tick without a kind there is F20 broken, not history (2026-09-17)
            for ref, it in _untyped_running(case, store.todo_of(case)):
                out.say(f"x {case.name}/TODO.md: F20 · {ref} is done without a kind of evidence in the running phase → "
                        f"el todo done {ref} <kind> attaches it — words kept, no journal event (the running phase holds the current form; "
                        f"closed phases stay as they are)")
                log_lines.append(f"{date} {time} · {case.name} · TODO.md · F20 · {ref} untyped in the running phase")
                errors += 1
            for p_, it, path, was, now in _changed_proofs(case, store.todo_of(case)):  # L8: done against other bytes
                ref = f"{it.ref}"
                out.say(f"x {case.name}/TODO.md: F20 · {ref} proof {path} changed since done (#{was} → now #{now}) → "
                        f"{_changed_moves(ref, path)}")
                log_lines.append(f"{date} {time} · {case.name} · TODO.md · F20 · {ref} proof {path} changed since done")
                errors += 1
        except StoreError:
            pass
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
        out.say(f"cases: {len(cases)} ({scope}) · violations: {errors} · warnings: {len(out.warnings)}{_refused_note()} "
                "— structure and form, not what the proofs prove (file: exists, a case file its version · run, ref, owner: as reported)")
    if errors:
        raise StoreError("\n".join(out.lines + [f"warning: {w}" for w in out.warnings]), 3)
    return out
