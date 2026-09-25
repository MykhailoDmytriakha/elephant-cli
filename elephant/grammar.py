"""Grammars of the case files — rules F0–F13 of .cases/RULES.md as parsers.

Each parser returns a Result: a structured model plus `errors` (rule violations → the write
is refused, exit code 3) and `warnings` (thresholds crossed → the write passes with a notice).
Every finding names the rule it comes from, so `el` can print "F7 · line 14 · ..." and the
agent can look the rule up. Nothing here touches the filesystem.
"""
import re
from dataclasses import dataclass, field
from typing import Tuple, List, Optional

from . import stamp as stamp_mod

# ---- limits (F2, F4, F7, F13; owner decisions 2026-08-30) --------------------------------------
README_WARN_LINES, README_WARN_BYTES = 200, 8 * 1024
README_MAX_LINES, README_MAX_BYTES = 300, 12 * 1024
README_POINTER_CHARS = 150
# 200 since 0.20 (feedback 2026-09-09): a rollout through five environments × 17 steps plus 26 phase
# lines is 113 lines of structure, not water — at 100 the agent cancelled live phases to fit.
TODO_MAX_LINES = 200
# 100 since 0.21 (feedback 2026-09-09): a rollout step reads `<Env>: [<Block>] <Action> -> expect <Result>`
# — the expected result IS the checkable outcome F13 asks for, and 80 squeezed it to `ENABLED=1`;
# 100 plus the `  - [ ] NN.MM ` prefix still fits one terminal line of 120 columns.
# The owner's word 2026-09-15: 100 stays; an item over it is rephrased, not counted differently.
TODO_ITEM_CHARS = 100
# F22 — an item's pockets: `why:` (one), `note:` (several), each a pointer-sized line; the number is
# README's pointer-line limit — a note points at context, the context itself lives in a file.
POCKET_CHARS = README_POINTER_CHARS
EVENT_CHARS = 200
EVENT_WARN_CHARS = 180
EVENT_BODY_LINES = 5

README_SECTIONS = ["Context", "State", "Decisions", "Problems", "Links"]
STATE_OWNED = ("progress", "last", "as of", "closed")  # State lines el writes (F3): whole, not the agent's to shorten
JOURNAL_TYPES = {"PHASE", "DECISION", "PROBLEM", "RESULT"}
# F20 (2026-09-14, the owner's word): a done item carries the KIND of its evidence — a closed list, on
# purpose. file = a thing in the case anyone can open · ref = a trace outside the case a person can
# check · run = a command and what came out, a machine can repeat · owner = the owner's word, the
# only word that counts (the agent writes the record, so its own word is not evidence — it leaves
# a file). A kind that is missing arrives through `el feedback`, not through a fifth spelling.
EVIDENCE_KINDS = ("file", "ref", "run", "owner")

TITLE_RE = re.compile(r"^# \S.*$")
ENTRY_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) · (p\d+(?:\.\d+)?)$")
EVENT_RE = re.compile(r"^  (PHASE|DECISION|PROBLEM|RESULT|[A-Z]+) · (.+)$")
BODY_RE = re.compile(r"^    (.+)$")
PHASE_LINE_RE = re.compile(r"^- \[( |x)\] (\d+) (.+?)(?: — (.+))?$")
PHASE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*(?: [A-Za-z0-9-]+){0,2}$")  # F13: English, 1–3 words
ITEM_RE = re.compile(r"^  - \[( |x|~)\] (\d+)\.(\d+) (.+)$")  # `~` = on hold
# F24 — the general list (the owner's word, 2026-09-25: «what is not for this phase goes to the general list; the next
# phase is formed from it»): a `## Later` section after the phases, one open line per thought with its own number for
# life and the date it was put there — the boundary counter reads it
LATER_HEAD = "## Later"
LATER_RE = re.compile(r"^  - \[ \] L(\d+) (.+)$")
SINCE_SUFFIX = " — since: "
AFTER_REF_RE = re.compile(r"\d+\.\d+|[A-Za-z0-9][\w-]*")  # F19: an item N.M or a nested case name
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
EVIDENCE_RE = re.compile(r"^(.*) — (file|ref|run|owner)(?:: (.+))?$")  # the evidence suffix of a done item
# the 1.5.0–1.9.0 order: evidence after the date or dependency suffix → (line up to the suffix, the evidence tail)
OLD_TAIL_RE = re.compile(r"^(.* — (?:due: \d{4}-\d{2}-\d{2}|after: [^—]+?))( — (?:file|ref|run|owner)(?:: .+)?)$")


def split_evidence(text: str):
    """`text — file: [x](evidence/x.jpg)` → (text, "file", "[x](evidence/x.jpg)"); `text — owner` → (text, "owner", "");
    no suffix → (text, "", ""). The suffix is written by `el todo done` and read here — never typed."""
    m = EVIDENCE_RE.match(text)
    if not m:
        return text, "", ""
    return m.group(1).rstrip(), m.group(2), (m.group(3) or "").strip()


def visible_len(text: str) -> int:
    """Length as the reader sees it: markdown links `[name](path)` count as `name` (feedback 2026-09-01).
    Nothing else is exempt (the owner's word, 2026-09-15: a 103-char item with an endpoint path is
    rephrased — verb first, the path stays, the filler goes — not counted differently)."""
    return len(LINK_RE.sub(r"\1", text))
DEEP_ITEM_RE = re.compile(r"^\s+- \[( |x)\] \d+\.\d+\.\d+")
WAITS_RE = re.compile(r"^  - waits: (\S+)$")
PHASE_NOTE_RE = re.compile(r"^  - note: (.+)$")                      # F22: a note under a phase line
POCKET_RE = re.compile(r"^    - (why|note|expect|result|fact|accepted):(?: (.+))?$")  # F22: an item's pockets; F23: accepted
EVIDENCE_LINE_RE = re.compile(r"^(?:    |      )- (file|ref|run|owner)(?:: (.+))?$")  # F20: one line per proof
POCKET_KINDS = ("why", "note", "expect", "result", "fact")  # the agent's pockets; `accepted:` is el's (F23)
# F22 `expect:` — what done will look like, written BEFORE the work; the proofs it names stand in brackets,
# `[file: docs/x.md] [run: k6 → p95] [owner]`, so `done` can hold the record to its own promise.
EXPECT_SLOT_RE = re.compile(r"\[(file|ref|run|owner)(?::\s*([^\]]*))?\]")
ANY_SLOT_RE = re.compile(r"\[([a-z][a-z-]*)(?::[^\]]*)?\]")


def expected_kinds(expect: str):
    """The proof placeholders of an `expect:` line: [(kind, what), …]."""
    return [(m.group(1), (m.group(2) or "").strip()) for m in EXPECT_SLOT_RE.finditer(expect)]
SECTION_RE = re.compile(r"^## (.+)$")
PHASE_TITLE_RE = re.compile(r"^# Phase (\d+) — (.+)$")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
CHECKBOX_RE = re.compile(r"^\s*- \[( |x)\] ")


@dataclass
class Finding:
    rule: str
    line: int  # 1-based; 0 = whole file
    message: str

    def __str__(self):
        where = f"line {self.line}" if self.line else "file"
        return f"{self.rule} · {where} · {self.message}"


@dataclass
class Result:
    title: Optional[str] = None
    stamp: Optional[str] = None
    stamp_state: str = "missing"  # ok | missing | not-last | mismatch
    errors: List[Finding] = field(default_factory=list)
    warnings: List[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, rule, line, message):
        self.errors.append(Finding(rule, line, message))

    def warn(self, rule, line, message):
        self.warnings.append(Finding(rule, line, message))


# ---- common: title + stamp (F0, S1) ------------------------------------------------------------
def _frame(text: str, result: Result):
    """Check first line (title) and last line (stamp); return body lines without the stamp."""
    body, found = stamp_mod.split(text)
    ok, state = stamp_mod.verify(text)
    result.stamp, result.stamp_state = found, state
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines or not TITLE_RE.match(lines[0]):
        result.error("F0", 1, "first line must be a title: `# <Title>`")
    else:
        result.title = lines[0][2:].strip()
    return lines


# ---- JOURNAL (F7, F8, F9, P5) ------------------------------------------------------------------
@dataclass
class Event:
    type: str
    text: str
    line: int
    body: List[str] = field(default_factory=list)


@dataclass
class Entry:
    date: str
    time: str
    phase: str
    line: int
    events: List[Event] = field(default_factory=list)


@dataclass
class Journal(Result):
    entries: List[Entry] = field(default_factory=list)

    def phases_with_result(self):
        return {e.phase for e in self.entries for ev in e.events if ev.type == "RESULT"}

    def last(self, n: int):
        return self.entries[:n]


def parse_journal(text: str) -> Journal:
    r = Journal()
    lines = _frame(text, r)
    entry, event, prev_key = None, None, None
    for i, raw in enumerate(lines[1:], start=2):
        if raw.strip() == "":
            continue
        m = ENTRY_RE.match(raw)
        if m:
            date, time, phase = m.groups()
            key = (date, time)
            if prev_key is not None and key > prev_key:
                r.error("F7", i, f"entries must be newest first: {date} {time} comes after an older entry")
            prev_key = key
            if entry is not None and not entry.events:
                r.error("F7", entry.line, "entry has no event lines under it")
            entry = Entry(date, time, phase, i)
            r.entries.append(entry)
            event = None
            continue
        m = EVENT_RE.match(raw)
        if m:
            if entry is None:
                r.error("F7", i, "event line before any entry header")
                continue
            typ, txt = m.groups()
            if typ not in JOURNAL_TYPES:
                r.error("F8", i, f"unknown event type `{typ}`; allowed: PHASE · DECISION · PROBLEM · RESULT")
            n = len(raw.strip())
            if n > EVENT_CHARS:
                r.error("F7", i, f"event line is {n} chars, limit {EVENT_CHARS}: move details into a body line")
            # «close to the limit» (soft, EVENT_WARN_CHARS) is said once, by `el log`, for the line just written —
            # not by the parser on history: 46 of 66 check warnings were old lines nobody would touch (2026-09-17)
            event = Event(typ, txt, i)
            entry.events.append(event)
            continue
        m = BODY_RE.match(raw)
        if m:
            if event is None:
                r.error("F7", i, "body line without an event above it")
                continue
            event.body.append(m.group(1))
            if len(event.body) > EVENT_BODY_LINES:
                r.error("F7", i, f"event body longer than {EVENT_BODY_LINES} lines")
            continue
        r.error("F7", i, "unparsable line: expected `- YYYY-MM-DD HH:MM · pN`, `  TYPE · text` or `    body`")
    if entry is not None and not entry.events:
        r.error("F7", entry.line, "entry has no event lines under it")
    return r


# ---- TODO (F4, F5, F6, F13) ---------------------------------------------------------------------
@dataclass
class Item:
    n: int
    m: int
    done: bool
    text: str
    line: int
    held: bool = False
    hold_reason: str = ""
    due: str = ""        # YYYY-MM-DD from the `— due: …` suffix; the tool counts dates it can parse
    after: List[str] = field(default_factory=list)  # F19: `— after: N.M, case` — what must end first
    # F22 — the pockets under the item, one line each, rendered in this order: why · note… · result
    why: str = ""                       # what the item is for — the owner's words, one line
    notes: List[str] = field(default_factory=list)   # constraints, who to call, what to bring, a link to a document
    expect: str = ""                    # what done will look like, with proof placeholders `[kind: what]` — before the work
    result: str = ""                    # what came out — written by `done` only
    fact: str = ""                      # what is now KNOWN (the owner's word, 2026-09-17): expected while the item is open,
                                        # established once it is done; the fact chain is made of these lines only
    # F20 — the evidence of a done item: (kind, proof) per line, kinds file · ref · run · owner; several allowed.
    # An item ticked before 1.5.0 has none ("untyped"); an item done before 1.10.0 carried one as a tail.
    evidence: List[Tuple[str, str]] = field(default_factory=list)
    # F23 — who accepted the done item and from which session: `codex · another session · 2026-09-25` — written by
    # `el todo accept` only (the owner's word, 2026-09-25: done by one hand, accepted by another); `reopen` clears it
    accepted: str = ""
    since: str = ""  # F24: a Later line only — the date it was put into the general list (written by el)

    @property
    def kind(self) -> str:
        """The first kind — for counts and old call sites; the full list is `evidence`."""
        return self.evidence[0][0] if self.evidence else ""

    @property
    def proof(self) -> str:
        return self.evidence[0][1] if self.evidence else ""


@dataclass
class Phase:
    n: int
    name: str
    done: bool
    line: int
    summary: Optional[str] = None
    items: List[Item] = field(default_factory=list)
    waits: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)  # F22: notes parked under a planned or open phase


@dataclass
class Todo(Result):
    phases: List[Phase] = field(default_factory=list)
    later: List[Item] = field(default_factory=list)  # F24: the general list — items with no phase yet, n = 0, `Lm`

    def phase(self, n: int):
        return next((p for p in self.phases if p.n == n), None)

    def closed(self):
        return {p.n for p in self.phases if p.done}

    def current(self):
        return next((p for p in self.phases if not p.done), None)


def parse_todo(text: str) -> Todo:
    r = Todo()
    lines = _frame(text, r)
    # F4 counts what the agent writes — phase and item lines, notes, why, waits. Lines el renders from
    # `done` (`result:` and the evidence under it) are named, not counted: the agent cannot shorten them.
    rendered = sum(1 for ln in lines if EVIDENCE_LINE_RE.match(ln)
                   or (POCKET_RE.match(ln) and ln.startswith(("    - result:", "    - accepted:"))))
    own = len(lines) - rendered
    if own > TODO_MAX_LINES:
        aside = f" (plus {rendered} result lines el renders, not counted)" if rendered else ""
        r.error("F4", 0, f"TODO is {own} lines of your text, limit {TODO_MAX_LINES}{aside}")
    phase, item, seen = None, None, set()
    in_result = False  # after `    - result:` the evidence nests one level deeper
    in_later, later_seen = False, set()  # F24: after `## Later` only Later lines and their pockets

    def finish(it: Optional[Item]):
        """The item's lines are all read. A done item with no proof line under it may carry the tail form
        of 1.5.0–1.9.0 (`text — kind: proof`): split it now — not at the item line, where a text that merely
        ends in «— file» (found in the tool's own case, 2026-09-15) would be mistaken for evidence once
        its proofs had moved to their own lines. The tail is outside the F13 count, the text is not."""
        if it is None:
            return
        if it.done and not it.evidence:
            txt, kind, proof = split_evidence(it.text)
            if kind:
                it.text = txt
                it.evidence.append((kind, proof))
        if visible_len(it.text) > TODO_ITEM_CHARS:
            r.error("F13", it.line, f"item {it.n}.{it.m} text is {visible_len(it.text)} visible chars, limit {TODO_ITEM_CHARS}")

    for i, raw in enumerate(lines[1:], start=2):
        if raw.strip() == "":
            continue
        if DEEP_ITEM_RE.match(raw):
            r.error("F13", i, "no items deeper than N.M — third level belongs in the phase file")
            continue
        if raw == LATER_HEAD:
            if in_later:
                r.error("F24", i, "`## Later` appears twice")
            finish(item)
            in_later, phase, item, in_result = True, None, None, False
            continue
        m = LATER_RE.match(raw)
        if m and in_later:
            finish(item)
            k, txt = int(m.group(1)), m.group(2).strip()
            since = ""
            if SINCE_SUFFIX in txt:
                txt, since = txt.rsplit(SINCE_SUFFIX, 1)
                since = since.strip()
                if not DATE_RE.fullmatch(since):
                    r.error("F24", i, f"L{k}: `since:` must be YYYY-MM-DD, got `{since}`")
            if k in later_seen:
                r.error("F24", i, f"L{k} appears twice")
            later_seen.add(k)
            item, in_result = Item(0, k, False, txt.strip(), i), False
            item.since = since
            r.later.append(item)
            continue
        if in_later and (PHASE_LINE_RE.match(raw) or ITEM_RE.match(raw)):
            r.error("F24", i, "phases and their items come before `## Later` — the general list is the last section of TODO")
            continue
        m = PHASE_LINE_RE.match(raw)
        if m:
            done, n, name, summary = m.group(1) == "x", int(m.group(2)), m.group(3).strip(), m.group(4)
            if n in seen:
                r.error("F4", i, f"phase {n} appears twice")
            seen.add(n)
            if not PHASE_NAME_RE.match(name):
                r.error("F13", i, f"phase name `{name}` must be English, 1–3 words, letters/digits/hyphen")
            if done:
                if not summary:
                    r.error("F5", i, f"closed phase {n} needs a summary: `— result · date · … · [phases/{n}-name.md](phases/{n}-name.md)`")
                else:
                    if not DATE_RE.search(summary):
                        r.error("F5", i, f"closed phase {n}: summary has no date")
                    if not re.search(rf"phases/{n}-[a-z0-9-]+\.md", summary):
                        r.error("F5", i, f"closed phase {n}: summary must end with a link to its file: `[phases/{n}-name.md](phases/{n}-name.md)`")
            # An open phase may carry `— <one-line intent>` (rolling wave); only closed phases need a summary.
            finish(item)
            phase, item, in_result = Phase(n, name, done, i, summary), None, False
            r.phases.append(phase)
            continue
        m = ITEM_RE.match(raw)
        if m:
            if phase is None:
                r.error("F4", i, "item before any phase")
                continue
            finish(item)
            mark, n, k, txt = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).strip()
            held, reason, due = mark == "~", "", ""
            if held and " — hold: " in txt:
                txt, reason = txt.rsplit(" — hold: ", 1)
            # 1.5.0–1.9.0 appended the evidence tail AFTER the date or dependency (`… — due: D — file: [x](p)`):
            # a line el wrote is a line el reads (feedback 2026-09-22: one such line made the whole TODO
            # unwritable). The tail goes back onto the text, and finish() splits it as evidence.
            tail = ""
            if mark == "x":
                mt = OLD_TAIL_RE.match(txt)
                if mt:
                    txt, tail = mt.group(1), mt.group(2)
            if " — due: " in txt:
                txt, due = txt.rsplit(" — due: ", 1)
                due = due.strip()
                if not DATE_RE.fullmatch(due):
                    r.error("F4", i, f"item {n}.{k}: `due:` must be YYYY-MM-DD, got `{due}`")
            after: List[str] = []
            if " — after: " in txt:
                txt, refs = txt.rsplit(" — after: ", 1)
                after = [x.strip() for x in refs.split(",") if x.strip()]
                for ref in after:
                    if not AFTER_REF_RE.fullmatch(ref):
                        r.error("F19", i, f"item {n}.{k}: `after:` expects N.M or a case name, got `{ref}`")
            txt += tail
            if n != phase.n:
                r.error("F4", i, f"item {n}.{k} listed under phase {phase.n}")
            if phase.done:
                r.error("F5", i, f"closed phase {phase.n} still lists items — they belong in the phase file")
            item, in_result = Item(n, k, mark == "x", txt, i, held, reason, due, after), False  # F13 is checked in finish()
            phase.items.append(item)
            continue
        m = EVIDENCE_LINE_RE.match(raw)
        if m and item is not None and (in_result or raw.startswith("    - ")):
            # F20: a proof line — `- file: [x](path)` · `- ref: …` · `- run: cmd → out` · `- owner`; only under a done item
            kind, proof = m.group(1), (m.group(2) or "").strip()
            if not item.done:
                r.error("F20", i, f"item {item.n}.{item.m} is open and carries evidence `{kind}` — evidence comes with `done`, or the tick is missing")
            elif kind == "owner" and proof:
                r.error("F20", i, f"item {item.n}.{item.m}: `owner` carries no value — the outcome is the owner's word")
            elif kind != "owner" and not proof:
                r.error("F20", i, f"item {item.n}.{item.m}: `{kind}:` needs its proof")
            item.evidence.append((kind, proof))
            continue
        m = POCKET_RE.match(raw)
        if m:
            if item is None:
                r.error("F22", i, f"`{m.group(1)}:` under no item — a pocket line belongs under `  - [ ] N.M …`")
                continue
            pocket, val = m.group(1), (m.group(2) or "").strip()
            if pocket == "accepted":  # F23: el's line, written by `el todo accept` over a done item only
                if not item.done:
                    r.error("F23", i, f"item {item.n}.{item.m} is open and carries `accepted:` — only a done item is accepted, "
                                      f"or the tick is missing")
                if item.accepted:
                    r.error("F23", i, f"item {item.n}.{item.m} has two `accepted:` lines — one acceptance per item, the journal keeps the rest")
                item.accepted, in_result = val, False
                continue
            if pocket == "result":
                if not item.done:
                    r.error("F20", i, f"item {item.n}.{item.m} is open and carries `result:` — the result comes with `done`, or the tick is missing")
                if item.result:
                    r.error("F22", i, f"item {item.n}.{item.m} has two `result:` lines — one result per item, several proofs under it")
                item.result, in_result = val, True
                continue
            in_result = False
            if not val:
                r.error("F22", i, f"item {item.n}.{item.m}: `{pocket}:` is empty")
            elif visible_len(val) > POCKET_CHARS:
                r.error("F22", i, f"item {item.n}.{item.m}: `{pocket}:` is {visible_len(val)} visible chars, limit {POCKET_CHARS} — "
                                  f"a pocket points at context; the context itself goes to a file, linked")
            if pocket == "why":
                if item.why:
                    r.error("F22", i, f"item {item.n}.{item.m} has two `why:` lines — one why per item; the rest are notes")
                item.why = val
            elif pocket == "fact":
                if item.fact:
                    r.error("F22", i, f"item {item.n}.{item.m} has two `fact:` lines — one fact per item")
                item.fact = val
            elif pocket == "expect":
                if item.expect:
                    r.error("F22", i, f"item {item.n}.{item.m} has two `expect:` lines — one expectation per item, several proofs inside it")
                for m2 in ANY_SLOT_RE.finditer(val):
                    if m2.group(1) not in EVIDENCE_KINDS:
                        r.error("F22", i, f"item {item.n}.{item.m}: `[{m2.group(1)}…]` is not a kind of proof — "
                                          f"placeholders are [file: …] [ref: …] [run: …] [owner]")
                item.expect = val
            else:
                item.notes.append(val)
            continue
        m = PHASE_NOTE_RE.match(raw)
        if m:
            if phase is None:
                r.error("F22", i, "`note:` before any phase")
            elif phase.done:
                r.error("F5", i, f"closed phase {phase.n} still carries a note — it belongs in the phase file")
            else:
                val = m.group(1).strip()
                if visible_len(val) > POCKET_CHARS:
                    r.error("F22", i, f"phase {phase.n}: `note:` is {visible_len(val)} visible chars, limit {POCKET_CHARS}")
                phase.notes.append(val)
            finish(item)
            item, in_result = None, False
            continue
        m = WAITS_RE.match(raw)
        if m:
            if phase is None:
                r.error("F6", i, "`waits:` before any phase")
            else:
                phase.waits.append(m.group(1))
            finish(item)
            item, in_result = None, False
            continue
        r.error("F4", i, "unparsable line: expected `- [ ] N Name`, `  - [ ] N.M text`, `  - note: …` (phase), "
                         "`    - why: | note: | expect: | result: | accepted: | fact: …` (item, F22, F23), `      - <kind>: <proof>` (evidence, F20), `  - waits: <case>`, "
                         "or after `## Later`: `  - [ ] Lk text — since: YYYY-MM-DD` (F24)")
    finish(item)
    return r


# ---- README (F1, F2, F3) ------------------------------------------------------------------------
@dataclass
class Readme(Result):
    sections: dict = field(default_factory=dict)  # name -> list of lines (without the heading)
    lines: int = 0
    bytes: int = 0
    rendered_lines: int = 0   # Links lines el renders from the files — not counted by F2
    rendered_bytes: int = 0


def parse_readme(text: str) -> Readme:
    r = Readme()
    lines = _frame(text, r)
    r.lines, r.bytes = len(lines), len("\n".join(lines).encode("utf-8"))
    order, current = [], None
    for i, raw in enumerate(lines[1:], start=2):
        m = SECTION_RE.match(raw)
        if m:
            current = m.group(1).strip()
            if current in r.sections:
                r.error("F1", i, f"section `{current}` appears twice")
            r.sections[current] = []
            order.append(current)
            continue
        if raw.strip() == "":
            continue
        if current is None:
            r.error("F1", i, "text before the first section")
            continue
        r.sections[current].append(raw)
        owned = current == "State" and raw.startswith(tuple(f"- {p}:" for p in STATE_OWNED))
        if current in ("Links", "State") and raw.startswith("- ") and not owned and visible_len(raw.strip()) > README_POINTER_CHARS:
            # a POINTER line — Links and State, where the owner clicks and scans (F2); Decisions, Problems and Context
            # are text, bounded by the README byte limit (2026-09-17: 19 Decisions lines warned for weeks, nobody acted).
            # Lines el derives (`progress:` over 21 phases) are not the agent's to shorten (feedback 2026-09-04)
            r.warn("F2", i, f"pointer line is {visible_len(raw.strip())} visible chars, over {README_POINTER_CHARS}")
    # F2 counts the text people write. The nested Links lines (files, sub-folders, `other:`) are
    # rendered by el from the files and cannot be shortened in README — they are reported, not
    # counted (feedback 2026-09-03: a growing file index squeezed the owner's own five lines out).
    rendered = [ln for ln in r.sections.get("Links", []) if ln.startswith("  ")]
    r.rendered_lines, r.rendered_bytes = len(rendered), sum(len(ln.encode("utf-8")) + 1 for ln in rendered)
    own_lines, own_bytes = r.lines - r.rendered_lines, r.bytes - r.rendered_bytes
    aside = (f" (Links rendered by el: {r.rendered_lines} lines / {r.rendered_bytes} bytes more, not counted)"
             if rendered else "")
    if own_lines > README_MAX_LINES or own_bytes > README_MAX_BYTES:
        r.error("F2", 0, f"README is {own_lines} lines / {own_bytes} bytes of your text, limit {README_MAX_LINES} / {README_MAX_BYTES}{aside}")
    elif own_lines > README_WARN_LINES or own_bytes > README_WARN_BYTES:
        r.warn("F2", 0, f"README is {own_lines} lines / {own_bytes} bytes of your text, over {README_WARN_LINES} / {README_WARN_BYTES}: "
                        f"move a section into a file{aside}")
    if order != README_SECTIONS:
        r.error("F1", 0, f"sections must be exactly {' · '.join(README_SECTIONS)}, got {' · '.join(order) or 'none'}")
    state = r.sections.get("State", [])
    if not any(ln.lstrip("- ").startswith("progress:") for ln in state):
        r.warn("F3", 0, "State has no `progress:` line")
    return r


# ---- phase file (F12) ---------------------------------------------------------------------------
@dataclass
class PhaseFile(Result):
    n: Optional[int] = None
    name: Optional[str] = None
    goal: str = ""
    result: str = ""
    body: List[str] = field(default_factory=list)


def parse_phase_file(text: str) -> PhaseFile:
    r = PhaseFile()
    lines = text.rstrip("\n").split("\n")
    m = PHASE_TITLE_RE.match(lines[0]) if lines else None
    if not m:
        r.error("F12", 1, "first line must be `# Phase N — Name`")
    else:
        r.title, r.n, r.name = lines[0][2:], int(m.group(1)), m.group(2).strip()
        if not PHASE_NAME_RE.match(r.name):
            r.error("F13", 1, f"phase name `{r.name}` must be English, 1–3 words")
    if len(lines) < 2 or not lines[1].startswith("goal:") or not lines[1][5:].strip():
        r.error("F12", 2, "second line must be `goal: <one line>`")
    else:
        r.goal = lines[1][5:].strip()
    if len(lines) < 3 or not lines[2].startswith("result:"):
        r.error("F12", 3, "third line must be `result:` (empty while the phase is open)")
    else:
        r.result = lines[2][7:].strip()
    r.body = lines[3:]
    for i, raw in enumerate(r.body, start=4):
        if CHECKBOX_RE.match(raw):
            r.error("F12", i, "no checklist in the phase file — that duplicates TODO")
            break
    return r
