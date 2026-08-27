"""Записи вместо прозы — the single door through which a phase's traces are written.

Until 2026-08-26 a phase wrote markdown and read it back with regular expressions: the
boundary was parsed out of `## what` headings, a node's nine fields out of its own file,
the acceptance checklist out of `- [x] 7.` lines. Markdown was serving as a database, and
every parser was a place where a slightly changed wording silently dropped data. The owner
called it: «переходим на JSONL — и тебе удобнее, и поиск, и работа; файлы я всё равно не
открываю, я смотрю overview.html».

THE SHAPE. One stream per concern, one record per line, append-only:

    records.jsonl   every beat of every phase AND every through-flow (questions · research ·
                    risks · unknown · definitions · forks), each record stamped with the
                    phase it was born on
    checks.jsonl    THE REGISTRY OF PROMISES — everything anyone promised to verify,
                    wherever it was born, each carrying its own status

Every record wears the same envelope, inherited from the journal so the tool has one
grammar and not two:

    {"seq": 14, "ts": "…", "phase": "context", "step": "scope", "type": "dim", "by": "owner", "id": "w2", …}

    phase where the record was born — the only address a flow record has
    seq   monotonic within the stream — what `over_seq` on the owner's word points at, and
          what makes «поправка пришла ПОСЛЕ его слова» a computation instead of a guess
    step  which beat of the ladder this belongs to
    type  what kind of record it is; the payload's shape follows from it
    by    owner · agent · external — who it came from, never guessed
    id    short stable anchor (`q3`, `w2`, `s1`) — what amendments and verdicts point at

NOTHING IS EVER EDITED OR DELETED. A picture that changed is a NEW record plus an `amend`
that says which id it retracts and why (the same law the markdown files kept by striking a
line through instead of erasing it — here it costs no parser). A status that changed is a
`verdict` event; the current status is the fold of events over an id, exactly as the task's
phase is folded out of the journal rather than stored in a field.
"""
import json, os

from .state import now_iso, mark_render, task_meta, touch


# ONE STREAM FOR EVERY PHASE AND EVERY FLOW (owner, 2026-08-27: «одна тетрадь на всю работу»):
# a flow — questions · research · risks · unknown · definitions · forks — runs through all
# phases, so it cannot live in one phase's file; the record's `phase` says where it was born.
# The old names stay as aliases so nothing that says "context" or "research" breaks.
STREAMS = {"records": "records.jsonl", "context": "records.jsonl", "research": "records.jsonl",
           "checks": "checks.jsonl"}


# The prefix each kind of record mints its ids from. Short on purpose: these are typed by
# hand into `--retracts w2` and read aloud off the page.
ID_PREFIX = {
    "qa": "q", "now": "n", "dim": "w", "condition": "o", "req": "r", "beyond": "b",
    "risk": "x", "part": "p", "unknown": "u", "definition": "t", "finding": "f",
    "clarified": "cl", "summary": "sm", "ifr": "ifr", "word": "acc", "amend": "am",
    # думание (2026-08-27) — each type its own prefix, so `form` and `fork` never share one
    "person": "who", "form": "fm", "core": "co", "fork": "fk", "decision": "d", "irreversible": "ir",
    "path": "pt", "attack": "at", "crystal": "cy", "stage_seed": "rt", "skip": "sk", "toolnote": "tn",
    "todo": "td", "todo_done": "tdd", "node": "n", "set": "st", "request": "rq", "brief": "br", "origin": "og",
    # checks.jsonl
    "success": "s", "metric": "m", "checklist": "k", "criterion": "cr", "verdict": "v",
}


# A promise starts life unverified — that is a STATE, not a missing record (owner,
# 2026-08-26: «они записываются и, допустим, статус там какой-то not_validated»). The gate
# of validate then costs one line: is anything still `not_validated`.
NOT_VALIDATED = "not_validated"
# passed · failed · waived (снят вместе с работой) · unverified (работа есть, проверки нет —
# долг) · covered (указатель: доказательство живёт в другом узле — долг, пока тот не сошёлся)
VERDICTS = [NOT_VALIDATED, "passed", "failed", "waived", "unverified", "covered"]


# THE TREE OF PROMISES IS THE TREE OF WORK, read upward (owner, 2026-08-26: «сверху идеи,
# внизу результаты и проверки результатов» — a chiasm). Every promise has two addresses:
#   at    where it HANGS — `task` (the root: what he checks himself) · `s2` · `s2.wp1`
#   born  where it CAME FROM — context · think · plan · execute · validate
# A root promise never moves down: the stage's own promises say which root promise they
# unfold (`covers`), so coverage is counted top-down at PLAN and the colour is counted
# bottom-up at VALIDATE — two questions to one tree.
ROOT = "task"
PROMISE_KINDS = ["success", "metric", "checklist", "criterion"]


def promise_ok(rec):
    """A promise without a way to check it is a wish, not a promise (the skill's first rule,
    applied at the door). Returns the reason it is refused, or None."""
    if rec.get("kind") not in PROMISE_KINDS:
        return f"kind — one of {', '.join(PROMISE_KINDS)}"
    if not (rec.get("text") or rec.get("name")):
        return "text — what is promised"
    if not (rec.get("how") or "").strip():
        return "how — чем проверим; без способа проверки обещание не записывается"
    return None


# THREE COLOURS, and the links to where the colour is (owner, 2026-08-26): «если всё
# зелёное, то всё зелёное; если где-то жёлтое — жёлтое и ссылка на S1 или S2.WP6.T3, где
# оно; пять жёлтых — пять ссылок; то же с красным».
#   green   every promise here and below passed
#   yellow  something was waived with a debt — passed, but the debt shows and links
#   red     something failed, or is still not checked — links say which and where
GREEN, YELLOW, RED = "green", "yellow", "red"
COLOUR_OF = {"passed": GREEN, "waived": YELLOW, "covered": YELLOW, "failed": RED,
             "unverified": RED, NOT_VALIDATED: RED}


def colour(root, task, tree=None, node=ROOT):
    """The colour of a node folded out of its promises and its children, with the links.

    `tree` maps a node id to its children ids ({} in context, when there are no nodes yet).
    Returns {"colour", "yellow": [(where, id)], "red": [(where, id)], "open": [...]} — the
    lists ARE the links the page prints next to the colour. `open` is the part of red that is
    merely not checked yet, kept apart so «не проверено» reads differently from «не сошлось»."""
    tree = tree or {}
    out = {"colour": GREEN, "yellow": [], "red": [], "open": []}
    for p in promises(root, task):
        if p.get("at", ROOT) != node:
            continue
        c = COLOUR_OF.get(p["status"], RED)
        if c == YELLOW:
            out["yellow"].append((node, p["id"]))
        elif c == RED:
            (out["open"] if p["status"] == NOT_VALIDATED else out["red"]).append((node, p["id"]))
    for child in tree.get(node, []):
        sub = colour(root, task, tree, child)
        for k in ("yellow", "red", "open"):
            out[k] += sub[k]
    if out["red"] or out["open"]:
        out["colour"] = RED
    elif out["yellow"]:
        out["colour"] = YELLOW
    return out


def colour_line(c):
    """One line for the terminal: the colour and its links, the way he asked to read it."""
    mark = {GREEN: "🟢", YELLOW: "🟡", RED: "🔴"}[c["colour"]]
    bits = []
    if c["red"]:
        bits.append("не сошлось: " + ", ".join(f"{w}/{i}" for w, i in c["red"]))
    if c["open"]:
        bits.append("не проверено: " + ", ".join(f"{w}/{i}" for w, i in c["open"]))
    if c["yellow"]:
        bits.append("с долгом: " + ", ".join(f"{w}/{i}" for w, i in c["yellow"]))
    return mark + (" " + " · ".join(bits) if bits else " всё сошлось")


def stream_path(root, task, stream):
    return os.path.join(root, task, STREAMS[stream])


def read(root, task, stream):
    """Every record of the stream, in the order written. Missing file — no records."""
    path = stream_path(root, task, stream)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                # A hand-mangled line must not take the whole stream down with it: the
                # bookkeeping is worth more than the one record somebody broke.
                continue
    return out


def next_seq(records):
    return max([r.get("seq", 0) for r in records] or [0]) + 1


def mint_id(records, rtype):
    """`q3` — the next id of this kind. Ids never repeat, even after a retraction."""
    pre = ID_PREFIX.get(rtype, rtype[:2])
    n = 0
    for r in records:
        rid = r.get("id") or ""
        if rid.startswith(pre) and rid[len(pre):].isdigit():
            n = max(n, int(rid[len(pre):]))
    return f"{pre}{n + 1}"


def append(root, task, stream, rec):
    """Write one record. Fills in seq · ts · id; the caller brings the meaning."""
    records = read(root, task, stream)
    full = {"seq": next_seq(records), "ts": now_iso()}
    if stream != "checks":
        full["phase"] = task_meta(root, task).get("phase", "context")
    full.update(rec)
    if not full.get("id"):
        full["id"] = mint_id(records, full.get("type", "rec"))
    path = stream_path(root, task, stream)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(full, ensure_ascii=False) + "\n")
    touch(root, task)
    mark_render(root, task)
    return full


def promise(root, task, rec):
    """Record a promise — refused without `how`. Born unverified, hung on the root unless
    told otherwise. Returns (record, None) or (None, reason)."""
    reason = promise_ok(rec)
    if reason:
        return None, reason
    full = {"type": rec["kind"], "at": ROOT, "status": NOT_VALIDATED}
    full.update(rec)
    return append(root, task, "checks", full), None


def verdict(root, task, of, status, proof, by="agent", why=None):
    """One verdict over one promise — an event, never an edit of the promise itself."""
    if status not in VERDICTS:
        raise ValueError(f"status — one of {', '.join(VERDICTS)}")
    rec = {"type": "verdict", "of": of, "status": status, "proof": proof, "by": by}
    if why:
        rec["why"] = why
    return append(root, task, "checks", rec)


def retracted(records):
    """Ids struck by an amendment — read, never written over."""
    return {r["retracts"] for r in records if r.get("type") == "amend" and r.get("retracts")}


def live(records, step=None, rtype=None):
    """The picture as it stands: records still in force, newest last.

    An amendment does not erase — it says this id no longer holds. The retracted record
    stays on disk (history), and stays out of the picture (truth)."""
    gone = retracted(records)
    out = [r for r in records if r.get("id") not in gone and r.get("type") != "amend"]
    if step:
        out = [r for r in out if r.get("step") == step]
    if rtype:
        out = [r for r in out if r.get("type") == rtype]
    return out


def steps_present(records):
    """Which beats have left a trace — what the gate counts instead of listing files."""
    return {r.get("step") for r in live(records) if r.get("step")}


def status_of(checks):
    """id → current status, folded out of the verdict events over it.

    The promise itself carries `not_validated` when it is born; each verdict is its own
    record, so the history of «сначала не сошлось, потом сошлось» survives — and the
    current answer is still one lookup."""
    st = {}
    for r in live(checks):
        if r.get("type") == "verdict":
            if r.get("of"):
                st[r["of"]] = r.get("status", NOT_VALIDATED)
        elif r.get("id"):
            st.setdefault(r["id"], r.get("status", NOT_VALIDATED))
    return st


def verdict_of(root, task, pid):
    """(status, proof, why) — the latest verdict event over a promise, or its birth state."""
    recs = live(read(root, task, "checks"))
    st, proof, why = NOT_VALIDATED, "", ""
    for r in recs:
        if r.get("type") == "verdict" and r.get("of") == pid:
            st, proof, why = r.get("status", NOT_VALIDATED), r.get("proof", ""), r.get("why", "")
    return st, proof, why


def promises(root, task, kind=None, born=None):
    """The registry's promises with their standing status — verdict events folded in."""
    recs = read(root, task, "checks")
    st = status_of(recs)
    out = []
    for r in live(recs):
        if r.get("type") == "verdict":
            continue
        if kind and r.get("kind") != kind:
            continue
        if born and r.get("born") != born:
            continue
        r = dict(r)
        r["status"] = st.get(r["id"], NOT_VALIDATED)
        out.append(r)
    return out


def open_promises(root, task):
    """What still has no verdict — the whole of the validate gate, in one call."""
    return [p for p in promises(root, task) if p["status"] == NOT_VALIDATED]
