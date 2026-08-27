"""Phase 3 — PLAN: the fractal of nodes, the eight fields that make a node a contract,
the stops along the road. A node is a markdown file under nodes/ with frontmatter and
one `## field · heading` section per field; the path IS the hierarchy (S1 · S1.WP1 …).
The field set is protocol.NODE_FIELDS.
"""
import json, os, re, sys
from .protocol import NODE_FIELDS, NODE_KEYS, NODE_KEYS_OPTIONAL, PHASES, PLAN_LEVELS
from .state import path_marks
from . import autonomy
from .state import (pick_task, current_task, fm_read, fm_write, journal, now_iso, require_root, task_meta,
                    resolve_task, task_mode, touch, write)
from .term import wrap


# ── PLAN commands: one verb, addressed by PATH ────────────────────────────────
#
# The owner asked for it in the shape he actually types (2026-08-19): `el plan s1 wp1`. So the
# address IS the hierarchy — `S1` is a stage, `S1.WP1` a work package inside it, `S1.WP1.T1` a
# task inside that. Nothing has to be declared: the level and the parent both fall out of how
# deep the path is, and a child under a missing parent is simply impossible to address.
PLAN_FIELD_SET = set(NODE_KEYS)


# ── STORAGE: nodes are RECORDS in records.jsonl (2026-08-27), folded like everything else ──
#
# A node is born as one `node` record (id · level · parent · status · the nine fields); every
# later change is a `set` event over it (field · value · was), never a rewrite; a removed node
# is an `amend` that retracts it. node_read folds the base and its sets into the dict every
# caller has always used ({"id", "name", "level", "parent", "status", …, "_fields": {…}}),
# node_write diffs the dict against the fold and appends only what changed. The nodes/ folder
# and plan.md are gone: the network is computed from `deps`, the page draws the tree.
from . import store as _store


def _rt(tdir):
    tdir = os.path.abspath(tdir.rstrip("/"))
    return os.path.dirname(tdir), os.path.basename(tdir)


def _node_fold(tdir):
    """{id: node dict} — base records with their `set` events folded in, retractions honoured."""
    recs = _store.read(*_rt(tdir), "records")
    gone = _store.retracted(recs)
    nodes = {}
    for r in recs:
        if r.get("type") == "node" and r.get("id") and r["id"] not in gone:
            n = {k: v for k, v in r.items() if k not in ("type", "step", "fields", "seq", "ts", "phase", "by")}
            n["_fields"] = dict(r.get("fields") or {})
            n["_seq"] = r.get("seq", 0); n["_ts"] = r.get("ts", ""); n["_rec"] = r["id"]
            nodes[r["id"]] = n
    # the node's promises ride along from the registry — `check` used to be a field, now
    # it is the promises hung on the node (2026-08-27)
    try:
        by_at = {}
        for p in _store.promises(*_rt(tdir)):
            by_at.setdefault((p.get("at") or "").upper(), []).append(p)
        for nid_, n in nodes.items():
            n["_promises"] = by_at.get(nid_.upper(), [])
    except Exception:
        for n in nodes.values():
            n["_promises"] = []
    for r in recs:
        if r.get("type") == "set" and r.get("of") in nodes and r.get("id") not in gone:
            n = nodes[r["of"]]
            f = r.get("field", "")
            if f.startswith("fields."):
                n["_fields"][f[7:]] = r.get("value", "")
            elif f:
                n[f] = r.get("value")
            n["_ts"] = r.get("ts", n["_ts"])
    return nodes


def nodes_dir(tdir):
    return os.path.join(tdir, "nodes")     # legacy name; nothing is written there any more


def node_path(tdir, nid):
    return os.path.join(nodes_dir(tdir), f"{nid}.md")


def node_read(tdir, nid):
    return _node_fold(tdir).get(nid)


def node_write(tdir, nid, meta, fields):
    """Append what changed: a `node` record for a new node, `set` events for a known one."""
    root, task = _rt(tdir)
    cur = _node_fold(tdir).get(nid)
    meta = {k: v for k, v in meta.items() if k not in ("_fields", "id", "_seq", "_ts", "_rec")}
    fields = {k: (v or "").strip() for k, v in fields.items()}
    if cur is None:
        rec = {"step": "stages" if "." not in nid else "nodes", "type": "node", "id": nid, "by": "agent",
               "fields": {k: v for k, v in fields.items() if v and v != "_пусто_"}}
        rec.update(meta)
        _store.append(root, task, "records", rec)
        return
    for k, v in meta.items():
        if cur.get(k) != v and not (cur.get(k) in (None, "") and v in (None, "")):
            _store.append(root, task, "records", {"step": "nodes", "type": "set", "of": nid, "field": k,
                                                  "value": v, "was": cur.get(k), "by": "agent"})
    for k, v in fields.items():
        old = (cur["_fields"].get(k) or "").strip()
        if v == "_пусто_":
            v = ""
        if old != v:
            _store.append(root, task, "records", {"step": "nodes", "type": "set", "of": nid, "field": "fields." + k,
                                                  "value": v, "was": old, "by": "agent"})


def node_retract(tdir, nid, why):
    """Retract a node — and the promises hung on it: a promise with no node under it would
    keep the root red for work nobody does any more."""
    root, task = _rt(tdir)
    cur = _node_fold(tdir).get(nid)
    if not cur:
        return None
    for p in _store.promises(root, task):
        if (p.get("at") or "").upper() == nid.upper():
            _store.append(root, task, "checks", {"type": "amend", "retracts": p["id"], "why": f"узел {nid}: {why}", "by": "agent"})
    return _store.append(root, task, "records", {"step": "nodes", "type": "amend", "retracts": nid, "why": why, "by": "agent"})


def node_exists(tdir, nid):
    return nid in _node_fold(tdir)


def nodes_all(tdir):
    return [n for _k, n in sorted(_node_fold(tdir).items())]


def node_sync(node):
    """What kind of stop this node ends with, read from its own words.

    Three kinds, and only the first lets the agent keep going: ПОКАЗ (show and continue) ·
    РАЗВИЛКА (show and wait — an unknown gets resolved here and the answer changes the route) ·
    РАЗРЕШЕНИЕ (nothing proceeds without his word, this is where the irreversible sits).

    The kind is decided by ONE question — can his answer change the PLAN? It cannot be decided
    by how important the node feels. (Owner, 2026-08-19, on a stop I had labelled a check-in:
    "после Stage 1 — что там сверять, скажи мне?" There was nothing to check: the answer could
    only change that node, not the road. It was a show, and I had dressed it up.)"""
    raw = node.get("_fields", {}).get("sync") or ""
    # The template stub is NOT a stop. It used to count as a ПОКАЗ, so a node with all
    # eight fields still empty was listed among the stops and counted as one passed
    # (found by the differential test, 2026-08-21).
    if raw.strip() == "_пусто_":
        raw = ""
    text = raw.upper()
    # A WHOLE WORD, not a substring: the mandatory line "показываю:" contains "ПОКАЗ", and a
    # substring search turned every stop into a show — the acceptance one included. Found on
    # live work 2026-08-21: `el plan` printed five identical "показ" marks for five different
    # stops, and the owner asked what exactly he was going to be shown.
    for kind in ("РАЗРЕШЕНИЕ", "РАЗВИЛКА", "ПОКАЗ"):
        if re.search(r"\b" + kind + r"\b", text):
            return kind
    # Not named outright — then read the line that DECIDES the kind. The rule is the tool's
    # own: "ничего" is a show, an answer that can change the road is a fork, and a word the
    # work cannot proceed without is a permission.
    asked = ""
    for line in raw.splitlines():
        low = _sync_line(line).lower()
        if low.startswith("от тебя:"):
            asked = low[len("от тебя:"):].strip()
            break
    if not asked:
        # The four parts may sit on ONE line («показываю: … · от тебя: …»). `el plan set`
        # accepts that form, so the kind must be read from it too — otherwise the same
        # stop was a ПОКАЗ here and a fork elsewhere (found 2026-08-21).
        m = re.search(r"от тебя:\s*(.*)", raw.lower())
        if m:
            asked = m.group(1).strip()
    if asked:
        # "Ничего" FIRST, and by how the line STARTS. A line may go on to mention a decision
        # that belongs to some later stop ("ничего; про коммит спрошу отдельно") — reading the
        # whole line for keywords turned two reports into permissions.
        if asked.startswith("ничего"):
            return "ПОКАЗ"
        if any(w in asked for w in ("разрешение", "приёмк", "приемк", "коммит", "согласие")):
            return "РАЗРЕШЕНИЕ"
        if any(w in asked for w in ("решение", "поправк", "выбор", "ответ")):
            return "РАЗВИЛКА"
    return "ПОКАЗ" if raw.strip() else ""


def _sync_line(line):
    """One line of a stop, without the list bullet the file format puts in front of it.

    The field is stored as markdown, so the first line arrives as "- показываю: …". Matching
    the label without stripping that bullet silently found nothing — which is exactly how the
    subject stayed invisible while the data was there all along."""
    return line.strip().lstrip("-·*").strip()


def sync_subject(node, limit=64):
    """WHAT gets shown at this stop — the subject line, so an overview says it out loud.

    Without this the plan printed a row of identical "показ" marks: the four lines describing
    the stop lived in the node and were visible only through `el sync`. A mark that does not
    say what it shows is the same "ну как?" the four-line form exists to prevent."""
    raw = node.get("_fields", {}).get("sync") or ""
    for line in raw.splitlines():
        clean = _sync_line(line)
        if clean.lower().startswith("показываю:"):
            subj = clean[len("показываю:"):].strip()
            return subj if len(subj) <= limit else subj[:limit - 1].rstrip() + "…"
    return ""


def sync_mark(node):
    return {"РАЗРЕШЕНИЕ": "🔒 разрешение", "РАЗВИЛКА": "🙋 развилка",
            "ПОКАЗ": "👁 показ"}.get(node_sync(node), "")


# The node's contract under light mode: the result and how it is checked — the rest of the
# nine fields is filled when it matters, not to satisfy the form (owner, 2026-08-22).
LIGHT_KEYS = ["result", "check"]


def node_gaps(node, mode="soft"):
    """Which of the fields are still empty. `_пусто_` is the template stub, not an answer.
    Under light mode only result and check are owed; `covers` is never owed here — route
    integrity is demanded from the goal's side (el plan integrity), not from every node.

    A DECLARED BLANK SPOT owes nothing (owner, 2026-08-24): a place of unfolding exists
    precisely because the detail is not knowable yet — demanding nine filled fields from it
    would force the agent to invent them, which is the very thing the planning package
    prevents. Its own contract is different and is enforced where it is created: what must
    become known, and after which event."""
    if (node.get("unfold") or "").strip():
        return []
    f = node.get("_fields", {})
    # WHAT A NODE OWES (2026-08-27): result and its stop in the everyday mode, plus at least
    # one PROMISE in the registry (the old `check` field); strict asks for the whole contract.
    keys = {"light": ["result"], "soft": ["result", "sync"],
            "strict": ["result", "sync", "executor", "resources", "artifacts", "storage", "inputs"]}.get(mode, ["result", "sync"])
    gaps = [k for k in keys if (not f.get(k) or f[k].strip() in ("_пусто_", ""))]
    if mode != "light" and not node.get("_promises") and not (f.get("check") or "").strip():
        gaps.append("promise")
    return gaps


# ── THE LIFECYCLE of a node — what the live pilot lacked (owner, 2026-08-22) ──────────
#
# Two states, open and done, could not tell apart «planned», «being worked on right now»,
# «shown, the owner holds the baton», «stuck», «deliberately set aside». So the navigator could
# not name the ONE node in work, the page could not draw a live board, and a node with every
# criterion met stayed open unnoticed while the phases rolled on (S6 of the Settings pilot).
#   open     planned — its contract filled or still being filled
#   active   THE node in work; at most one — start another and this one steps back to open
#   waiting  shown to the owner, the baton is his: the agent does not drive on
#   blocked  stuck on something named; work cannot proceed until it is resolved
#   parked   deliberately set aside, with a reason — terminal for the gates, like done
#   done     closed with an observable result
TERMINAL = ("done", "parked")
STATUS_RU = {"open": "открыт", "active": "в работе", "waiting": "ждёт владельца",
             "blocked": "заблокирован", "parked": "отложен", "done": "закрыт"}
STATUS_MARK = {"open": "·", "active": "▶", "waiting": "⏸", "blocked": "✗", "parked": "⏹",
               "done": "✓"}


def status_ru(node):
    """The status in words — «не потребовался» for a cancelled node (parked for the gates,
    but not «later»: feedback 2026-08-26, a conditional task whose condition did not come)."""
    st = node_status(node)
    if st == "parked" and node.get("cancelled"):
        return "не потребовался"
    return STATUS_RU.get(st, st)


def status_mark(node):
    return "⊘" if node_status(node) == "parked" and node.get("cancelled") else STATUS_MARK.get(node_status(node), "·")


def node_status(node):
    return (node.get("status") or "open").strip() or "open"


def node_open(node):
    """Not terminal — still owed to the plan (open · active · waiting · blocked)."""
    return node_status(node) not in TERMINAL


def active_node(tdir):
    """The one node the AGENT works on (active); failing that, the first node waiting for the
    owner. None when nobody holds anything. Waiting nodes do not block the agent from starting
    another node — the owner tests S2 on the phone while the agent builds S3 — they only hold
    the baton for THEIR scenario; `el next` names them separately."""
    nodes = sorted(nodes_all(tdir), key=lambda x: x["id"])
    # the DEEPEST active node: a task inside a package in work is where the hands are
    act = [n for n in nodes if node_status(n) == "active"]
    if act:
        return max(act, key=lambda n: len(n["id"]))
    for n in nodes:
        if node_status(n) == "waiting":
            return n
    return None


def waiting_nodes(tdir):
    return [n for n in sorted(nodes_all(tdir), key=lambda x: x["id"]) if node_status(n) == "waiting"]


def _set_status(root, task, tdir, node, status, extra=None, event=None, text=""):
    meta = {k: v for k, v in node.items() if k not in ("_fields", "id")}
    meta["status"] = status
    for k, v in (extra or {}).items():
        if v is None:
            meta.pop(k, None)
        else:
            meta[k] = v
    # A LIFECYCLE STAMP that outlives its status is a false signal (feedback 2026-08-26:
    # «S1.WP5.md: status: active и одновременно waiting_since» — resume put the node back to
    # work and left the wait's «since when» behind): the stamp of a wait goes with the wait.
    if status != "waiting":
        meta.pop("waiting_since", None)
    node_write(tdir, node["id"], meta, node["_fields"])
    if event:
        journal(root, task, event, (f"{node['id']}: {text}" if text else node["id"])[:160],
                {"status": status})


def path_to_id(parts):
    """`s1 wp1` → `S1.WP1`. Accepts a ready id too, so `el plan S1.WP1` works as well."""
    flat = []
    for p in parts:
        flat.extend(str(p).split("."))
    return ".".join(x.strip().upper() for x in flat if x.strip())


def level_of_depth(nid):
    depth = nid.count(".")
    return PLAN_LEVELS[depth] if depth < len(PLAN_LEVELS) else PLAN_LEVELS[-1]


def _plan_task(root, args):
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return None, None
    return task, os.path.join(root, task)


def cmd_plan(args):
    """`el plan [что-то]` — весь план, один узел, или действие над узлом."""
    root = require_root()
    if not root:
        return 1
    task, tdir = _plan_task(root, args)
    if not task:
        return 1
    words = list(getattr(args, "words", None) or [])
    verb = words[0].lower() if words else ""

    if verb in ("new", "add"):
        rc = plan_new(root, task, tdir, words[1:], getattr(args, "force", False))
        # INSERT BETWEEN (owner, 2026-08-27): `--after s1 --before s2` — the new node waits for
        # s1, and s2 now waits for the new node: one node record, one set on the follower.
        aft, bef = (getattr(args, "after", None) or "").strip(), (getattr(args, "before", None) or "").strip()
        if rc == 0 and (aft or bef):
            nid = path_to_id([w for w in words[1:] if re.match(r"^[\w.]+$", w)] or words[1:2])
            if aft:
                plan_set(root, task, tdir, [nid, "deps", f"после {aft.upper()}"], replace=True)
            if bef:
                plan_set(root, task, tdir, [bef, "deps", f"после {nid}"], replace=True)
        return rc
    if verb == "promise":
        return plan_promise(root, task, tdir, words[1:], getattr(args, "how", None))
    if verb == "set":
        if getattr(args, "file", None):
            return plan_populate(root, task, tdir, words[1:], args.file)
        return plan_set(root, task, tdir, words[1:], getattr(args, "replace", False))
    if verb in ("rm", "drop"):
        return plan_rm(root, task, tdir, words[1:])
    if verb == "cancel":
        return plan_cancel(root, task, tdir, words[1:], getattr(args, "why", None))
    if verb == "rename":
        return plan_rename(root, task, tdir, words[1:], getattr(args, "why", None))
    if verb == "reopen":
        return plan_reopen(root, task, tdir, words[1:], getattr(args, "why", None))
    if verb == "done":
        return plan_done(root, task, tdir, words[1:], getattr(args, "force", False))
    if verb == "start":
        return plan_start(root, task, tdir, words[1:], getattr(args, "force", False),
                          switch=getattr(args, "switch", None))
    if verb == "wait":
        return plan_wait(root, task, tdir, words[1:])
    if verb in ("block", "park"):
        return plan_hold(root, task, tdir, words[1:], "blocked" if verb == "block" else "parked",
                         getattr(args, "why", None), getattr(args, "owe", None))
    if verb in ("cover", "покрывает"):
        from .integrity import cmd_cover
        return cmd_cover(root, task, tdir, words[1:])
    if verb in ("integrity", "целостность", "cover?"):
        from .integrity import cmd_integrity
        return cmd_integrity(root, task, tdir)
    if verb in ("unfold", "раскрытие"):
        return plan_unfold(root, task, tdir, words[1:], getattr(args, "why", None),
                           getattr(args, "after", None))
    if verb in ("show", "get", "card", "open", "cat") and len(words) > 1:
        # `el plan show r2` used to be parsed as the node SHOW.R2 — a node nobody has
        # («нет узла SHOW.R2», feedback pool, 2026-08-23). The card of a node needs no verb.
        rest = " ".join(words[1:])
        print(f"нет глагола «{verb}» — карточка узла печатается без него:", file=sys.stderr)
        print(f"  el plan {rest}", file=sys.stderr)
        print(f"  глаголы: new · set · done · start · wait · block · park · rm",
              file=sys.stderr)
        return 1
    if words:
        return plan_one(tdir, path_to_id(words))
    return plan_tree(tdir, root, task)


PROJECTION_MARK = "_Проекция дерева узлов"
ID_RE = re.compile(r"\b[Ss]\d+(?:\.(?:[Ww][Pp]|[Tt]|[Ss][Tt])\d+)*\b")
# A RELATIVE reference — «WP7», «WP6.WP7», «T3» — resolved against the node's own ancestors
# (feedback 2026-08-26: «After WP6.WP7» silently vanished from the graph and the node came
# out ready). The canonical prefix of every level, by depth: S · WP · T · ST.
REL_RE = re.compile(r"\b(?:[Ww][Pp]|[Tt]|[Ss][Tt])\d+(?:\.(?:[Ww][Pp]|[Tt]|[Ss][Tt])\d+)*\b")
LEVEL_PREFIX = ["S", "WP", "T", "ST"]


def canonical_gap(nid):
    """'' when every segment of `nid` carries its level's prefix (S1 · S1.WP2 · S1.WP2.T3 ·
    S1.WP2.T3.ST1); else the id it should have been (owner's plan, 2026-08-26: S1.WP6.WP1
    was accepted as a «task» and lied about the structure to every reader)."""
    segs = nid.split(".")
    if len(segs) > len(LEVEL_PREFIX):
        return "?"
    fixed = []
    for i, seg in enumerate(segs):
        m = re.match(r"^([A-Za-z]+)(\d+)$", seg)
        want = LEVEL_PREFIX[i]
        if not m or m.group(1).upper() != want:
            fixed.append(f"{want}{m.group(2) if m else 1}")
        else:
            fixed.append(seg.upper())
    return "" if fixed == [s.upper() for s in segs] else ".".join(fixed)


def resolve_relative(token, own):
    """«WP7» / «WP6.WP7» / «T3» / «ST2» → a full id under the ancestors of `own`: a WP is a
    package of own's stage, a T a task of own's package, an ST a subtask of own's task."""
    segs = [s.upper() for s in token.split(".")]
    first = re.match(r"^([A-Z]+)", segs[0]).group(1)
    depth = LEVEL_PREFIX.index(first) if first in LEVEL_PREFIX else -1
    own_segs = own.split(".") if own else []
    if depth <= 0 or len(own_segs) < depth:
        return ""
    return ".".join(own_segs[:depth] + segs)


AFTER_WORDS = ("after", "после", "depends", "зависит", "requires", "нужен", "нужны", "следом за")
BEFORE_WORDS = ("before", "до ", "перед", "раньше", "prior to", "затем", "потом", "then ", "gates", "открывает")


def deps_parse(text, own=""):
    """The `deps` field read as ORDER, not as a bag of ids (feedback 2026-08-24: «After S1.WP1;
    before S1.WP3 and S1.WP4» made a cycle, because every id named was taken as a
    prerequisite). Clauses split at «;» and line breaks; inside a clause the ids before a
    «before/до/перед» word are prerequisites, the ids after it are SUCCESSORS — nodes that
    wait for this one. Returns (prereqs, successors), own id dropped, order kept."""
    pre, suc = [], []
    if not text or text.strip() == "_пусто_":
        return pre, suc
    for clause in re.split(r"[;\n]+", text):
        low = clause.lower()
        cut = None
        for w in BEFORE_WORDS:
            i = low.find(w)
            if i >= 0 and (cut is None or i < cut):
                cut = i
        head, tail = (clause, "") if cut is None else (clause[:cut], clause[cut:])
        for part, bucket in ((head, pre), (tail, suc)):
            masked = ID_RE.sub(lambda m: " " * len(m.group(0)), part)
            for m in ID_RE.finditer(part):
                d = m.group(0).upper()
                if d != own and d not in bucket:
                    bucket.append(d)
            for m in REL_RE.finditer(masked):
                d = resolve_relative(m.group(0), own)
                if d and d != own and d not in bucket:
                    bucket.append(d)
    return pre, suc


def deps_of(node):
    """Prerequisites named in the node's `deps` — the ids it waits for."""
    return deps_parse((node.get("_fields", {}) or {}).get("deps") or "", node["id"])[0]


def successors_of(node):
    """Ids the node's `deps` says come AFTER it («before S1.WP3») — reverse edges."""
    return deps_parse((node.get("_fields", {}) or {}).get("deps") or "", node["id"])[1]


def plan_waves(tdir):
    """The network plan COMPUTED from the tree (owner, 2026-08-24: «план — проекция дерева»).

    Returns (waves, missing, cycle): waves — lists of node ids that can run side by side, in
    order (Kahn layers over `deps`; a child inherits its parent's deps, since it is part of
    the parent); missing — {node: [dep ids that are no node]}; cycle — ids left when the
    deps go round. The hand-written plan.md used to say the same things in prose and drift
    from the tree by definition — a computed field is not stored (his law for the phase)."""
    nodes = sorted(nodes_all(tdir), key=lambda x: x["id"])
    ids = {n["id"] for n in nodes}
    by_id = {n["id"]: n for n in nodes}
    deps, missing = {}, {}
    # reverse edges: «S1.WP1 … before S1.WP3» ⇒ S1.WP3 waits for S1.WP1
    reverse = {}
    for n in nodes:
        for s in successors_of(n):
            if s in ids:
                reverse.setdefault(s, []).append(n["id"])
            else:
                missing.setdefault(n["id"], []).append(s)
    for n in nodes:
        own = deps_of(n) + [x for x in reverse.get(n["id"], []) if x not in deps_of(n)]
        miss = [d for d in own if d not in ids]
        if miss:
            missing[n["id"]] = [x for x in missing.get(n["id"], []) if x not in miss] + miss
        eff = [d for d in own if d in ids]
        p = n.get("parent")
        while p and p in by_id:
            eff += [d for d in deps.get(p, []) if d not in eff]
            p = by_id[p].get("parent")
        deps[n["id"]] = [d for d in eff if not n["id"].startswith(d + ".") and d != n["id"]]
    placed, waves = set(), []
    while len(placed) < len(nodes):
        wave = [n["id"] for n in nodes if n["id"] not in placed
                and all(d in placed for d in deps[n["id"]])]
        if not wave:
            break
        waves.append(wave)
        placed.update(wave)
    cycle = [n["id"] for n in nodes if n["id"] not in placed]
    return waves, missing, cycle, deps


def network_plan(tdir):
    """plan.md as text — the projection. None when there are no nodes."""
    # the network is the movement between STAGES (owner, 2026-08-27) — packages stay inside
    nodes = sorted((n for n in nodes_all(tdir) if "." not in n["id"]), key=lambda x: x["id"])
    if not nodes:
        return None
    by_id = {n["id"]: n for n in nodes}
    waves, missing, cycle, deps = plan_waves(tdir)
    waves = [[i for i in w if "." not in i] for w in waves]
    waves = [w for w in waves if w]
    out = ["# Сетевой план — проекция дерева узлов", "",
           PROJECTION_MARK + ": строится из полей `deps` (что после чего) и `sync` (где "
           "остановки) командой `el`, рукой не правится. Почему порядок такой — "
           "`thinking/order.md`. Изменить план = изменить узлы: "
           '`el plan set s2 deps "после S1"`._', "", "## Порядок"]
    any_deps = any(deps[i] for i in deps)
    if not any_deps:
        out.append("_зависимостей не задано — порядок по id; параллельность не объявлена_")
    for k, wave in enumerate(waves, 1):
        head = f"**волна {k}**" + (" · параллельно" if len(wave) > 1 else "")
        out.append(head)
        for nid in wave:
            n = by_id[nid]
            st = node_status(n)
            after = [d for d in deps[nid] if d in by_id]
            sm = sync_mark(n)
            out.append(f"- {STATUS_MARK.get(st, '·')} {nid} · {n.get('name', '')}"
                       + (f" ← после {', '.join(after)}" if after else "")
                       + (f" · {sm}" if sm else ""))
    if cycle:
        out += ["", f"**ЦИКЛ зависимостей** — не разложить в порядок: {', '.join(cycle)}"]
    stops = [n for n in nodes if node_sync(n)]
    out += ["", "## Остановки"]
    if stops:
        for n in stops:
            subj = sync_subject(n)
            out.append(f"- {sync_mark(n)} {n['id']} · {n.get('name', '')}"
                       + (f" — {subj}" if subj else ""))
    else:
        out.append("_остановок не объявлено — поле sync пусто у всех узлов_")
    if missing:
        out += ["", "## Расхождение"]
        for nid, miss in missing.items():
            out.append(f"- {nid} зависит от {', '.join(miss)} — таких узлов нет")
    return "\n".join(out) + "\n"


def plan_drift(tdir):
    """Where the tree's own words do not add up: deps naming no node · a cycle.
    None when there are no nodes."""
    if not nodes_all(tdir):
        return None
    _w, missing, cycle, _d = plan_waves(tdir)
    return {"missing": missing, "cycle": cycle}


def drift_lines(tdir, indent="           "):
    """What the tree, `el next` and the gate say about it. [] when the plan adds up."""
    d = plan_drift(tdir)
    if not d:
        return []
    out = []
    for nid, miss in d["missing"].items():
        first = miss[0].lower().replace(".", " ")
        out.append(f"{indent}РАСХОЖДЕНИЕ  deps узла {nid} называет {', '.join(miss)} — таких узлов нет: "
                   f'el plan new {first} "<имя>" · либо поправь: el plan set {nid.lower()} deps "…" --replace')
    if d["cycle"]:
        _w, _m, _c, deps = plan_waves(tdir)
        cyc = set(d["cycle"])
        edges = [f"{nid} ← {', '.join(x for x in deps[nid] if x in cyc)}"
                 for nid in d["cycle"] if any(x in cyc for x in deps[nid])]
        out.append(f"{indent}ЦИКЛ  зависимости ходят по кругу: {' · '.join(edges)} — "
                   "разорви в поле deps того узла, чья стрелка лишняя")
        out.append(f"{indent}      deps читается как порядок: «после S1» — S1 раньше; "
                   "«перед S3» / «before S3» — S3 позже (не предпосылка)")
    return out


def plan_tree(tdir, root=None, task=None):
    """The plan AND its state: what is closed, what is open, what moved recently.

    A plan that only lists intentions is read once and then goes stale in the head. The owner
    asked for the state to be visible in the same view (2026-08-19): "чтобы показывало статус —
    что сделано, что изменено, что добавлено"."""
    nodes = nodes_all(tdir)
    mode = task_mode(tdir)
    if not nodes:
        print("узлов нет — и сетевого плана нет: план строится из узлов (deps · sync).")
        print('запись   el plan new s1 "<имя этапа>"')
        return 0

    done = [n for n in nodes if n.get("status") == "done"]
    left = [n for n in nodes if node_open(n)]
    holes = [n["id"] for n in nodes if node_gaps(n, mode)]
    stops = [n for n in sorted(nodes, key=lambda x: x["id"]) if node_sync(n)]
    passed = [n for n in stops if n.get("status") == "done"]
    nxt = next((n for n in stops if n.get("status") != "done"), None)
    act = active_node(tdir)

    print(f"СОСТОЯНИЕ  узлов {len(nodes)} · закрыто {len(done)} · открыто {len(left)}"
          f" · остановок пройдено {len(passed)} из {len(stops)}")
    if act:
        print(f"           {'ждём владельца ⏸' if node_status(act) == 'waiting' else 'сейчас ▶'} "
              f"{act['id']} · {act.get('name','')}")
    elif left:
        print(f"           в работе никого — назови: el plan start {left[0]['id'].lower()}")
    if nxt:
        print(f"           ближайшая остановка: {sync_mark(nxt)} {nxt['id']} · {nxt.get('name','')}")
    if holes:
        print(f"           с пустыми полями: {', '.join(holes)}")
    for l in drift_lines(tdir):
        print(l)
    print()

    for n in sorted(nodes, key=lambda x: x["id"]):
        gaps = node_gaps(n, mode)
        depth = n["id"].count(".")
        pad = "  " * depth
        st = node_status(n)
        mark = status_mark(n)
        note = {"waiting": n.get("waiting_note"), "blocked": n.get("block_note"),
                "parked": n.get("park_note")}.get(st)
        state = status_ru(n) + (f": {str(note)[:80]}" if note else "")
        if st == "open":
            state = "заполняется" if gaps else "готов к старту"
        sm = sync_mark(n)
        subj = sync_subject(n)
        print(f"{pad}{mark} {n['id']} · {n.get('name','')}  [{n.get('level','?')}]")
        ds = decomp_state(root, task, tdir, n) if (root and task and "." not in n["id"] and st != "done") else ""
        print(f"{pad}    {state}"
              f"{'  ·  ' + sm if sm else ''}"
              f"{'  ·  пусто: ' + ', '.join(gaps) if gaps else ''}"
              f"{'  ·  ' + DECOMP_RU[ds] if ds else ''}")
        if subj:
            print(f"{pad}      показываю: {subj}")
        note = n.get("result_note")
        if note:
            print(f"{pad}    итог: {wrap(str(note)[:200], indent=pad + '          ')}")

    # what MOVED — straight from the journal, so the view is not a static picture
    if root and task:
        jp = os.path.join(tdir, "journal.jsonl")
        if os.path.exists(jp):
            events = []
            for line in open(jp, encoding="utf-8"):
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("type") in ("node", "node-done", "node-removed", "step", "decision",
                                     "node-start", "node-wait", "node-pause", "node-blocked",
                                     "node-parked"):
                    events.append(e)
            if events:
                print("\nЧТО МЕНЯЛОСЬ ПОСЛЕДНИМ")
                names = {"node": "заведён узел", "node-done": "закрыт узел",
                         "node-removed": "убран узел", "step": "работа",
                         "decision": "решение", "node-start": "в работу",
                         "node-wait": "показан владельцу", "node-pause": "отложен в сторону",
                         "node-blocked": "заблокирован", "node-parked": "отложен"}
                for e in events[-6:]:
                    ts = str(e.get("ts", ""))[:16].replace("T", " ")
                    print(f"  {ts}  {names.get(e['type'], e['type']):<14} "
                          f"{wrap(str(e.get('text', ''))[:150], indent='                             ')}")

    text = network_plan(tdir) or ""
    body = [l for l in text.splitlines()[1:] if not l.startswith(PROJECTION_MARK)]
    print("\nСЕТЕВОЙ ПЛАН — движение по ЭТАПАМ: что за чем (считается из deps; пакеты живут внутри этапа)")
    print("\n".join(body).strip())
    print("\nподробно     el plan s1 · el plan s1 wp1 · el sync — только остановки · "
          'в работу: el plan start s1 · порядок: el plan set s2 deps "после S1"')
    return 0


def plan_one(tdir, nid):
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}.", file=sys.stderr)
        have = [n["id"] for n in nodes_all(tdir)]
        print(f"есть: {', '.join(have) or '— ни одного'}", file=sys.stderr)
        return 1
    gaps = node_gaps(node, task_mode(tdir))
    par = node.get("parent") or "—"
    st = node_status(node)
    print(f"{nid} · {node.get('name','')}   [{node.get('level','?')}]   родитель: {par}   "
          f"{STATUS_MARK.get(st, '·')} {STATUS_RU.get(st, st)}")
    for key, head, desc in NODE_FIELDS:
        val = (node["_fields"].get(key) or "").strip()
        if key in gaps:
            print(f"\n  ✗ {key} · {head}")
            print(f"      {wrap(desc, indent='      ')}")
        else:
            print(f"\n  ✓ {key} · {head}")
            for line in val.splitlines():
                if line.strip():
                    print(f"      {wrap(line.strip(), indent='        ')}")
            if key in ("artifacts", "storage"):
                # paths are MEASURED (feedback 2026-08-25): «на месте» / «нет по этому пути»
                pm = path_marks(tdir, val)
                for pth, ok in pm:
                    print(f"        {'✓ на месте' if ok else '✗ нет по этому пути'}: {pth}")
                if any(not ok for _p, ok in pm):
                    from .state import project_root
                    print(f"        искал от: {project_root()} · {tdir} · {os.getcwd()}")
    kids = [n for n in nodes_all(tdir) if n.get("parent") == nid]
    if kids:
        print("\n  внутри:")
        for k in sorted(kids, key=lambda x: x["id"]):
            g = node_gaps(k, task_mode(tdir))
            print(f"    {'✓' if not g else '▶'} {k['id']} · {k.get('name','')}"
                  f"{'' if not g else '  пусто: ' + ', '.join(g)}")
    else:
        nxt = level_of_depth(nid + ".X")
        print(f"\n  внутри пусто · разложить: el plan new {nid.lower()} wp1 \"<имя>\"  "
              f"(будет уровень {nxt})")
    # THE WORK LOG (owner, 2026-08-25): what was done on this node, in order — the notes
    # `el log` wrote while it was in work (older journals: by time), artifacts and evidence.
    from .worklog import worklog as _worklog
    from .term import human_when as _hw
    wl = _worklog(os.path.dirname(tdir), os.path.basename(tdir)).get(nid, [])
    if wl:
        # newest first (owner, 2026-08-25): the last step is what a returning reader wants
        print(f"\n  ход работы · {len(wl)} · свежие сверху" +
              ("  (~ по времени: запись без узла легла к узлу, который был в работе)"
               if any(e["by_time"] for e in wl) else ""))
        for e in reversed(wl[-10:]):
            print(f"    {_hw(e['ts']):<16} {e['type']:<10} {'~ ' if e['by_time'] else ''}{e['text'][:90]}")
        if len(wl) > 10:
            print(f"    … и ещё {len(wl) - 10} раньше")
    else:
        print("\n  ход работы · пусто — el log \"<что сделал>\" по ходу ложится сюда"
              + (" (узел в работе)" if st == "active" else ""))
    if gaps:
        print(f'\nзаполнить  el plan set {nid.lower()} <поле> "<текст>"')
    return 0


def plan_new(root, task, tdir, words, force=False):
    if not words:
        print('el plan new s1 "<имя этапа>"  ·  el plan new s1 wp1 "<имя пакета работ>"',
              file=sys.stderr)
        return 1
    name = words[-1] if len(words) > 1 or not re.match(r"^[\w.]+$", words[-1]) else ""
    path = words[:-1] if name else words
    if not path:
        print("нужен адрес узла: el plan new s1 \"<имя>\"", file=sys.stderr)
        return 1
    nid = path_to_id(path)
    if node_read(tdir, nid):
        print(f"узел {nid} уже есть")
        return 0
    # ONE SCHEMA FOR EVERY LEVEL (feedback 2026-08-26): the id says the level — S · WP · T · ST.
    want = canonical_gap(nid)
    if want:
        if want == "?":
            print(f"{nid} — глубже подзадачи уровней нет (этап → пакет → задача → подзадача)", file=sys.stderr)
        else:
            print(f"{nid} — не тот уровень в имени: этап S1 · пакет S1.WP1 · задача S1.WP1.T1 · "
                  f"подзадача S1.WP1.T1.ST1", file=sys.stderr)
            print(f"  так: el plan new {want.lower().replace('.', ' ')} \"{name}\"", file=sys.stderr)
        return 1
    parent = nid.rsplit(".", 1)[0] if "." in nid else ""
    if parent:
        par = node_read(tdir, parent)
        if not par:
            print(f"нет родителя {parent} — заведи его первым", file=sys.stderr)
            return 1
        # SCOPE GROWS UNDER A CLOSED PARENT (feedback 2026-08-24): a child born under a done
        # node silently makes «closed parent, open children». The parent is reopened first,
        # with a reason — that is the audit trail of the expansion.
        if node_status(par) in TERMINAL:
            print(f"родитель {parent} {STATUS_RU[node_status(par)]} — под закрытым узлом "
                  "новых работ не заводят молча.", file=sys.stderr)
            print(f'  расширение объёма: el plan reopen {parent.lower()} --why "<что прибавилось>" '
                  f"— потом el plan new {nid.lower().replace('.', ' ')} …", file=sys.stderr)
            return 1
        gaps = node_gaps(par, task_mode(tdir))
        if gaps:
            print(f"родитель {parent} ещё не заполнен: {', '.join(gaps)}", file=sys.stderr)
            print("  разворачивать вниз можно только заполненный узел: поэтапная",
                  file=sys.stderr)
            print("  декомпозиция закон (§5), разложить всё вперёд убило v1.", file=sys.stderr)
            return 1
        # THE LAYOUT IS TALKED OVER BEFORE IT IS WRITTEN (owner, 2026-08-26: «агент порывается
        # записывать декомпозицию, не разобравшись и не поговорив с пользователем»): on execute
        # the first package under a stage is recorded only after his word over the layout he
        # was shown in the chat — el accept "<его слова>" --for stage:s2 --on "<раскладка>".
        # On the plan phase his word over the plan covers packages drawn there. Light warns.
        from .state import task_meta as _tm
        ph_now = _tm(root, task).get("phase", "context")
        first_kid = "." not in parent and not any(n.get("parent") == parent for n in nodes_all(tdir))
        if first_kid and ph_now in PHASES and PHASES.index(ph_now) >= PHASES.index("execute") \
                and not stage_word(root, task, parent) and not force:
            low_p = parent.lower()
            if task_mode(tdir) == "light":
                print(f"раскладка {parent} без слова владельца — в light допустимо; правило: сначала обговорить "
                      f'в чате, после его «одобряю» — el accept "<его слова>" --for stage:{low_p} --on "<раскладка>"')
            else:
                print(f"РАСКЛАДКУ СНАЧАЛА ОБГОВОРИ — пакеты {parent} записываются после его «одобряю»:",
                      file=sys.stderr)
                print(f"  предложи раскладку владельцу в чате (пакеты → работы) → его слово: "
                      f'el accept "<его слова>" --for stage:{low_p} --on "<раскладка: wp1 … · wp2 …>" → '
                      f"потом el plan new {low_p} wp1 …", file=sys.stderr)
                print(f'  под грантом — реши в его место: el accept "<раскладка>" --for stage:{low_p} --assumed '
                      f'"<почему>" · осознанно без слова: --force', file=sys.stderr)
                return 1
    # A REPEATED HYPOTHESIS (search tasks, owner 2026-08-22): a sibling with the same name
    # already exists — tried or open. Loop hygiene: say so, show its result, and ask for a
    # different name or an explicit --force. The CLI compares names, not ideas — the agent
    # judges whether «int8» again is the same attempt.
    same = [n for n in nodes_all(tdir)
            if (n.get("parent") or "") == parent and n["id"] != nid
            and " ".join((n.get("name") or "").lower().split()) == " ".join(name.lower().split())
            and name.strip()]
    if same and not force:
        twin = same[0]
        print(f"уже есть узел с таким именем: {twin['id']} · {STATUS_RU.get(node_status(twin), '?')}"
              + (f" · итог: {(twin.get('result_note') or '')[:80]}" if twin.get("result_note") else ""),
              file=sys.stderr)
        print("  повтор гипотезы? назови иначе — чем эта отличается; та же — продолжай её; "
              "сознательно снова: --force", file=sys.stderr)
        return 1
    meta = {"level": level_of_depth(nid), "parent": parent, "name": name.strip(),
            "status": "open", "created_at": now_iso()}
    node_write(tdir, nid, meta, {})
    journal(root, task, "node", f"{nid} [{meta['level']}] {meta['name'][:70]}",
            {"parent": parent})
    touch(root, task)
    print(f"узел {nid} · {meta['level']} · {meta['name']}")
    print(f"дальше   el plan {nid.lower().replace('.', ' ')} — какие из девяти полей пусты · "
          f"el plan start {nid.lower()} — ДО работы, не после (контракт допишешь до закрытия)")
    return 0


def plan_reopen(root, task, tdir, words, why):
    """A closed or parked node goes back to OPEN — not to work — with the reason written
    (feedback 2026-08-24: «plan start --force смешивает reopening с execution»). Scope
    expansion of a done node starts here; `el plan start` is a separate, later act."""
    if not words:
        print('el plan reopen s1 --why "<что прибавилось · почему открываем>"', file=sys.stderr)
        return 1
    nid = path_to_id(words)
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    st = node_status(node)
    if st not in TERMINAL:
        print(f"{nid} и так {STATUS_RU[st]} — reopen только для закрытого или отложенного",
              file=sys.stderr)
        return 1
    why = (why or "").strip()
    if not why:
        print("скажи --why — переоткрытие без причины неотличимо от случайного", file=sys.stderr)
        return 1
    # The closing summary is history now (feedback 2026-08-26, plan-reopen: `el plan` kept
    # printing the old «итог» over a node that was open again) — the journal keeps it.
    _set_status(root, task, tdir, node, "open",
                {"reopened_at": now_iso(), "reopen_note": why, "park_note": None,
                 "result_note": None},
                "node-reopen", why)
    touch(root, task)
    print(f"открыт заново  {nid} · {node.get('name', '')} — {why}")
    print(f"дальше   расширить: el plan new {nid.lower().replace('.', ' ')} wpN \"<имя>\" · "
          f"в работу: el plan start {nid.lower()} · критерии узла остаются, вердикты — тоже")
    return 0


def sync_missing(text):
    """The four lines a stop must carry — which are absent."""
    low = (text or "").lower()
    return [w for w in ("показываю:", "увидишь:", "потрогать:", "от тебя:") if w not in low]


def print_sync_help(nid, missing):
    print(f"в остановке нет строк: {', '.join(missing)}", file=sys.stderr)
    print("  остановка описывается четырьмя строками, и каждая отвечает на своё:", file=sys.stderr)
    print("  показываю: — предмет · увидишь: — куда смотреть ·", file=sys.stderr)
    print("  потрогать: — чем он поработает САМ · от тебя: — ничего/поправка/решение", file=sys.stderr)
    print("  без них остановка превращается в «ну как?», а это не вопрос.", file=sys.stderr)
    print(f'  готовый шаблон:  el plan set {nid.lower()} sync "показываю: <что>'
          '\\nувидишь: <куда смотреть>\\nпотрогать: <что он сделает сам>'
          '\\nот тебя: <ничего|поправка|решение>"', file=sys.stderr)


def plan_populate(root, task, tdir, words, src):
    """The whole contract in ONE command (feedback 2026-08-24: «восемь полей и пять строк
    check — много однотипных shell-команд»). `--file <path>` or `--file -` (stdin): a
    markdown with a section per field —

        ## result
        - подписанный договор
        ## check
        - подписан обеими сторонами
        …

    Section heads are `## <field>` or `<field>:` on its own line; unknown heads are refused
    by name. Fields named in the file are REPLACED whole (this is a populate, not an append);
    fields not named stay as they are. Ends with the digest: what was set, what is still empty."""
    if not words:
        print('el plan set s1 wp1 --file contract.md   ·   --file - читает stdin', file=sys.stderr)
        return 1
    nid = path_to_id(words)
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    try:
        text = sys.stdin.read() if src == "-" else open(os.path.expanduser(src), encoding="utf-8").read()
    except OSError:
        print(f"не читается: {src}", file=sys.stderr)
        return 1
    sections, cur, bad = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^\s*(?:##\s*|)([A-Za-z_]+)\s*:?\s*$", line)
        if m and (line.lstrip().startswith("##") or line.rstrip().endswith(":")):
            key = m.group(1).lower()
            if key in PLAN_FIELD_SET:
                cur = key
                sections[cur] = []
            else:
                bad.append(key)
                cur = None
            continue
        if cur:
            sections[cur].append(line)
    if bad:
        print(f"неизвестные поля: {', '.join(bad)} — поля: {', '.join(NODE_KEYS)}", file=sys.stderr)
        return 1
    if not sections:
        print("в файле нет ни одной секции «## <поле>» — поля: " + ", ".join(NODE_KEYS),
              file=sys.stderr)
        return 1
    fields = dict(node["_fields"])
    for key, lines in sections.items():
        body = "\n".join(l.rstrip() for l in lines).strip()
        if not body:
            continue
        rows = [l.strip() for l in body.splitlines() if l.strip()]
        fields[key] = "\n".join(l if l.startswith("-") else f"- {l}" for l in rows)
    # THE SAME SEMANTICS AS FIELD BY FIELD (feedback 2026-08-26: --file printed «все поля
    # заполнены» over a one-line stop and a single criterion): a stop without its four lines
    # is refused whole; fewer than five criteria is said out loud.
    if "sync" in sections and fields.get("sync", "").strip():
        miss = sync_missing(fields["sync"])
        if miss:
            print_sync_help(nid, miss)
            print("  файл не записан — поправь секцию ## sync", file=sys.stderr)
            return 1
    node_write(tdir, nid, node, fields)
    touch(root, task)
    journal(root, task, "node-set", f"{nid}: {', '.join(sections)} (--file)", {"node": nid})
    print(f"{nid} · записано полей: {len(sections)} — {', '.join(sections)}")
    for key in sections:
        n = len([l for l in fields.get(key, '').splitlines() if l.strip().startswith('-')])
        print(f"  {key:<10} {n} строк(и)")
    if "deps" in sections:
        pre, suc = deps_parse(fields["deps"], nid)
        print("порядок  " + (f"после {', '.join(pre)}" if pre else "предпосылок нет")
              + (f" · перед {', '.join(suc)}" if suc else ""))
    n_check = len([l for l in fields.get("check", "").splitlines() if l.strip().startswith("-")])
    if "check" in sections and n_check < 5:
        print(f"         критериев {n_check} — меньше пяти: по спеке узел ещё не контракт")
    gaps = node_gaps(node_read(tdir, nid), task_mode(tdir))
    print(f"пусто    {', '.join(gaps) if gaps else ('— все поля контракта заполнены' if n_check >= 5 else '— поля заполнены, но контракт ещё тонкий (критериев < 5)')}")
    for l in drift_lines(tdir, indent="         "):
        print(l)
    return 0


def plan_set(root, task, tdir, words, replace=False):
    # `--replace` wipes the field first. Appending is the right default — criteria and results
    # accumulate as the work is understood — but with no way to replace, a wrong line stays
    # forever and gets edited in a text editor behind the tool's back.
    # flag comes from the parser, not from the word list — argparse eats it first
    # the path runs until the first token that names a field; everything after is the value
    idx = next((i for i, w in enumerate(words) if w.lower() in PLAN_FIELD_SET), -1)
    if idx < 1 or idx == len(words) - 1:
        print('el plan set s1 result "<текст>"  ·  el plan set s1 wp1 check "<текст>"',
              file=sys.stderr)
        print(f"  поля: {', '.join(NODE_KEYS)}", file=sys.stderr)
        return 1
    nid, key, value = path_to_id(words[:idx]), words[idx].lower(), " ".join(words[idx + 1:])
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    fields = dict(node["_fields"])
    cur = "" if replace else fields.get(key, "").strip()
    cur = "" if cur == "_пусто_" else cur
    line = value.strip()
    # A NUMBERED LIST IS A LIST, not one long criterion (feedback pool, 2026-08-23: «1) … 2) …
    # 5) …» went in as ONE criterion, so closing the node asked for one verdict instead of
    # five and the validation coarsened). Split «1) …» / «2. …» / «•» into separate bullets —
    # for `check` this is the difference between five promises and one.
    parts = re.split(r"(?:^|\s)(?:\d+[.)]|[•*])\s+", line)
    parts = [x.strip(" ;·") for x in parts if x.strip(" ;·")]
    if len(parts) > 1 and not line.startswith("-"):
        line = "\n".join("- " + x for x in parts)
        print(f"разложил в {len(parts)} строк(и) — нумерованный список это список, "
              f"не один пункт")
    fields[key] = (cur + "\n" if cur else "") + (line if line.startswith("-") else f"- {line}")
    if key == "sync":
        low = fields[key].lower()
        missing = sync_missing(fields[key])
        if missing:
            print_sync_help(nid, missing)
            return 1
        if "развилка" in low and ("вопрос:" not in low or "изменится:" not in low):
            print("развилка без вопроса — это не развилка.", file=sys.stderr)
            print("  добавь «вопрос: …» — что здесь выяснится,", file=sys.stderr)
            print("  и «изменится: …» — что в плане зависит от ответа.", file=sys.stderr)
            print("  назвать нечего — значит это ПОКАЗ, а не развилка.", file=sys.stderr)
            return 1
    node_write(tdir, nid, node, fields)
    touch(root, task)
    n = len([l for l in fields[key].splitlines() if l.strip().startswith("-")])
    print(f"{nid} · {key}: {n} строк(и)")
    if key == "deps":
        pre, suc = deps_parse(fields[key], nid)
        print("порядок  " + (f"после {', '.join(pre)}" if pre else "предпосылок нет")
              + (f" · перед {', '.join(suc)}" if suc else "")
              + "  (так прочитан deps: «после X» — X раньше; «перед Y»/«before Y» — Y позже)")
        for l in drift_lines(tdir, indent="         "):
            print(l)
    if key == "check" and n < 5:
        print("         критериев меньше пяти — по спеке узел ещё не контракт")
    gaps = node_gaps(node_read(tdir, nid), task_mode(tdir))
    print(f"пусто    {', '.join(gaps) if gaps else '— все поля контракта заполнены'}")
    return 0


def plan_done(root, task, tdir, words, force=False, dry=False):
    """Close a node — and refuse to close it past a stop that has not happened.

    This is where the sync point stops being a note and becomes a mechanism. A node whose stop
    is СВЕРКА or РАЗРЕШЕНИЕ cannot be marked done until the owner's words are recorded after it:
    `el accept`. Otherwise the plan would carry beautifully drawn stops that the agent drives
    straight past — which is exactly what happens when a rule lives only in prose.

    `dry` — run every refusal and stop before touching anything: `el accept --close` asks
    first whether the node CAN close, and records his word only if the answer is yes
    (feedback pool, 2026-08-24: the word landed, then «НЕ ЗАКРОЮ» — a flag that promised
    more than it did). The stop-word check is skipped when dry: that word is what the
    caller is about to write."""
    if not words:
        print('el plan done s1 wp1 "<что получилось>"', file=sys.stderr)
        return 1
    # The result is quoted, so it is always ONE argv item and always the last. Guessing by
    # "does it contain a space" turned `el plan done s1 "проба"` into the node `S1.ПРОБА`.
    path, result = (words, "") if len(words) == 1 else (words[:-1], words[-1])
    nid = path_to_id(path)
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    mode = task_mode(tdir)
    gaps = node_gaps(node, mode)
    if gaps and not force:
        print(f"у {nid} пусты поля: {', '.join(gaps)} — закрывать нечего", file=sys.stderr)
        return 1
    # UNDER AUTONOMY a node closed without a result is a hole nobody will ask about: the
    # record must carry what became true — one line, one format (search tasks: «6.4 ГБ ·
    # acc 0.925 · оставил»). With the owner around, `el doctor` still warns instead.
    if not result and autonomy.on(root, task) and not force:
        print(f"НЕ ЗАКРОЮ {nid} без результата — в автономии спросить «что вышло?» некому; "
              "запиши одной строкой: el plan done … \"<что стало правдой: числа · вердикт>\" "
              "(--force — сознательно без)", file=sys.stderr)
        return 1
    # STRICT: a node is a contract only with its five criteria — the soft-mode warning
    # becomes a refusal (owner, 2026-08-22: «везде проверяется каждая часть»).
    n_crit = len([l for l in (node["_fields"].get("check") or "").splitlines()
                  if l.strip().startswith("-")])
    if mode == "strict" and n_crit < 5 and not force:
        print(f"СТРОГО — у {nid} критериев {n_crit}, нужно не меньше пяти: "
              f'el plan set {nid.lower()} check "…"', file=sys.stderr)
        return 1
    # NESTED VALIDATION SEALS AT THE MOMENT OF CLOSING (owner, 2026-08-23): the check of a
    # node = its own criteria + the roll-up of its children, and `done` is where that check
    # is looked at — in EVERY mode, not a mode option. Two refusals follow from the law:
    #   1. a parent does not close over an open child — the guide said «родитель закрывается
    #      после детей», nothing enforced it;
    #   2. a node does not close over its own criteria without verdicts, and «не сошлось» /
    #      «не проверено» do not close either — the owner's rule is «останавливаться, если
    #      что-то не получается, и уточнить у пользователя», not to drive past.
    from .validate import (checklist_node, covered_target, criteria_of, resolve_verdicts,
                           validation_parse)  # function-level: validate imports plan
    all_nodes = nodes_all(tdir)
    kids_open = [n["id"] for n in all_nodes
                 if (n.get("parent") or "") == nid and node_open(n)]
    if kids_open and not force:
        print(f"НЕ ЗАКРОЮ {nid} — родитель закрывается после детей, а открыты: "
              f"{', '.join(kids_open)}", file=sys.stderr)
        print("  закрой их (el plan done) или отложи осознанно (el plan park --why)",
              file=sys.stderr)
        return 1
    raw = validation_parse(tdir)
    resolved, _cyc = resolve_verdicts([n for n in all_nodes if criteria_of(n)]
                                      + checklist_node(tdir), raw)
    crits = criteria_of(node)
    no_verdict = [i for i in range(1, len(crits) + 1)
                  if raw.get((nid, i), ("open", ""))[0] == "open"]
    # A criterion COVERED by another node whose answer is not in yet is a debt that
    # travels: the node closes, the debt is named downstream and holds the task there.
    travel = [(i, covered_target(raw[(nid, i)][1])) for i in range(1, len(crits) + 1)
              if raw.get((nid, i), ("open", ""))[0] == "covered"
              and resolved.get((nid, i), ("open", ""))[0] == "unverified"]
    travel_i = {i for i, _t in travel}
    bad = [(i, resolved[(nid, i)][0]) for i in range(1, len(crits) + 1)
           if resolved.get((nid, i), ("open", ""))[0] in ("failed", "unverified")
           and i not in travel_i]
    if no_verdict and not force:
        print(f"НЕ ЗАКРОЮ {nid} — критерии без вердикта: "
              f"{', '.join(str(i) for i in no_verdict)}. Проверь каждый:", file=sys.stderr)
        print(f'  el validate {nid.lower()} <N> --met "<чем доказано>" --evidence evidence/<файл>',
              file=sys.stderr)
        print("  снят вместе с работой — только явно и со своим «потому что»: "
              f'el validate {nid.lower()} <N> --declined "потому что …"', file=sys.stderr)
        print("  доказательство придёт из другого узла: "
              f'el validate {nid.lower()} <N> --covered-by <узел[.N]> --why "…"', file=sys.stderr)
        return 1
    if bad and not force:
        what = " · ".join(f"{i} {'не сошёлся' if k == 'failed' else 'не проверен'}"
                          for i, k in bad)
        print(f"НЕ ЗАКРОЮ {nid} — {what}.", file=sys.stderr)
        print("  не получается — не закрывай: почини и перемерь, или остановись и спроси "
              "человека:", file=sys.stderr)
        print(f'  el plan wait {nid.lower()} "<что не сходится и что нужно от него>"',
              file=sys.stderr)
        return 1
    kind = node_sync(node)
    if kind in ("РАЗВИЛКА", "РАЗРЕШЕНИЕ") and not force and not dry:
        # his word counts only if it landed AFTER the node was last written — by the clock
        # of the records, not the file system (2026-08-27)
        said_after = False
        try:
            from .state import journal_path as _jp
            import json as _json
            for _l in open(_jp(root, task), encoding="utf-8"):
                _e = _json.loads(_l)
                if _e.get("type") == "accepted" and _e.get("ts", "") >= (node.get("_ts") or ""):
                    said_after = True
        except OSError:
            pass
        if not said_after:
            print(f"НЕ ЗАКРОЮ — на {nid} стоит остановка ({kind}), а его слова нет.",
                  file=sys.stderr)
            print(f"  что показать: {(node['_fields'].get('sync') or '').strip()[:200]}",
                  file=sys.stderr)
            print('  показать → услышать → записать: el accept "<его слова>"', file=sys.stderr)
            print("  остановка, мимо которой можно проехать, — это не остановка.",
                  file=sys.stderr)
            return 1
    if dry:
        return 0                     # every refusal passed; nothing touched
    meta = {k: v for k, v in node.items() if k not in ("_fields", "id")}
    meta["status"] = "done"
    meta["closed_at"] = now_iso()
    if result:
        meta["result_note"] = result
    node_write(tdir, nid, meta, node["_fields"])
    journal(root, task, "node-done", f"{nid}: {result[:120]}", {"sync": kind or None})
    touch(root, task)
    print(f"закрыт {nid}" + (f" · {result[:80]}" if result else ""))
    if travel:
        print("долг     проверки уехал: " + " · ".join(
            f"{i} → {t[0]}{'.' + str(t[1]) if t[1] else ''}" for i, t in travel)
            + " — сочтётся там; выход из проверки держит, пока цель не сойдётся")
    # The validation card of the closed node — the moment of closing IS the moment its
    # check is sealed, so the roll-up is shown right here, not discovered later.
    try:
        from .validate import ROLL_MARK, ROLL_RU, rollup
        _, info = rollup(tdir)
        rec = info.get(nid)
        if rec and rec["sub"]["total"]:
            line = (f"проверка {ROLL_MARK[rec['verdict']]} {ROLL_RU[rec['verdict']]} · "
                    f"свои {rec['own']['done']}/{rec['own']['total']}")
            if rec["sub"]["total"] != rec["own"]["total"]:
                line += f" · с детьми {rec['sub']['done']}/{rec['sub']['total']}"
            print(line)
    except Exception:
        pass
    left = [n["id"] for n in nodes_all(tdir) if node_open(n)]
    print(f"осталось {', '.join(left) if left else '— все узлы закрыты'}")
    if left:
        for l in parent_closable_lines(tdir, nid):
            print(l)
        print("дальше   " + ready_line(tdir, root, task))
    return 0


def ready_nodes(tdir):
    """(ready, blocked) — who can be started now, by the GRAPH, and who waits for whom.

    `ready` — open leaves (no open child; a parent is led through its children) whose
    prerequisites in `deps` are all closed or parked, in wave order; `blocked` — {id:
    [open prerequisites]} for the rest. The hint used to name the first open node by id
    — «start WP1» after WP3 was closed and WP1 was the very node waiting on it (feedback
    pool, 2026-08-24). Order is read from the same `deps` that draw plan.md."""
    nodes = nodes_all(tdir)
    by = {n["id"]: n for n in nodes}
    waves, _m, _c, deps = plan_waves(tdir)
    placed = [i for w in waves for i in w]
    order = placed + sorted(i for i in by if i not in placed)
    parents_open = {n.get("parent") for n in nodes if n.get("parent") and node_open(n)}
    ready, blocked = [], {}
    for nid in order:
        n = by[nid]
        if node_status(n) != "open" or nid in parents_open:
            continue
        waits = [d for d in deps.get(nid, []) if d in by and node_open(by[d])]
        if waits:
            blocked[nid] = waits
        else:
            ready.append(n)
    return ready, blocked


def ready_line(tdir, root=None, task=None):
    """One line for `el next` / `el plan done`: the next node by the graph, and why."""
    ready, blocked = ready_nodes(tdir)
    if ready:
        first = ready[0]
        # THE STAGE LAW first (owner, 2026-08-26): a bare stage is laid out, a laid-out stage
        # waits for his word over the layout — only then a package starts.
        kids_f = [n for n in nodes_all(tdir) if (n.get("parent") or "") == first["id"]]
        if kids_f:
            low = first["id"].lower()
            return (f"все узлы внутри {first['id']} закрыты ({len(kids_f)}/{len(kids_f)}), а он открыт — "
                    f'закрой: el plan done {low} "<результат>" · или скажи, что ещё осталось: '
                    f'el plan new {low.replace(".", " ")} <следующий> "<имя>"')
        if "." not in first["id"]:
            low = first["id"].lower()
            return (f"этап {first['id']} не разложен — предложи раскладку владельцу в чате (пакеты → работы), "
                    f'после его «одобряю»: el accept "<его слова>" --for stage:{low} --on "<раскладка>" → '
                    f'запиши: el plan new {low} wp1 "<пакет>" … → el plan start {low}.wp1')
        _w, _m, _c, deps = plan_waves(tdir)
        after = [d for d in deps.get(first["id"], []) if d in {n["id"] for n in nodes_all(tdir)}]
        line = (f"el plan start {first['id'].lower()} — по графу готов"
                + (f" (после {', '.join(after)} — закрыты)" if after else " (предпосылок нет)"))
        if not stage_word(root, task, stage_of(first["id"])) and task_mode(tdir) != "light":
            line = (f"раскладка этапа {stage_of(first['id'])} ждёт его слова — покажи и запиши: "
                    f'el accept "<его слова>" --for stage:{stage_of(first["id"]).lower()} — потом ' + line)
        if len(ready) > 1:
            line += f" · готовы также: {', '.join(n['id'] for n in ready[1:5])}"
        return line
    if blocked:
        return ("по графу никто не готов: " + "; ".join(
            f"{k} ждёт {', '.join(v)}" for k, v in list(blocked.items())[:5])
            + " — закрой предпосылки или поправь порядок: el plan set <узел> deps \"…\"")
    return "открытых листьев нет — родители закрываются после детей: el plan done <родитель>"


# ── STAGES FIRST, PACKAGES AT THE START OF A STAGE (owner, 2026-08-26) ──────────────
# The plan phase draws the STAGES — a reasonable cut, the first holding the initial
# preparation (what is there, what is missing), the last holding the final check; the
# owner's «да» over the plan is a word over that cut, told plainly that every stage will
# be decomposed when it starts. On execute a stage does not start by itself: it is laid
# out into work packages (→ tasks → subtasks, the nearest level only), the layout is shown
# to the owner, his word is recorded over THE STAGE (el accept … --for stage:s2), and the
# packages are what start. A big task may draw packages on the plan already — allowed.
# In light mode the rule is a warning, not a refusal: light exists for small tasks.

def stage_of(nid):
    return nid.split(".", 1)[0]


def stage_word(root, task, sid):
    """His word (or the agent's decision in his place) over the layout of stage `sid` — the
    latest `accepted`/`assume` event with for == stage:<sid>; None when none."""
    import json as _json
    from .state import journal_path
    want = f"stage:{sid}".lower()
    found = None
    try:
        with open(journal_path(root, task), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") in ("accepted", "assume") and (rec.get("for") or "").lower() == want:
                    found = rec
    except OSError:
        pass
    return found


def decomp_state(root, task, tdir, node):
    """A stage's layout: none (no packages) · pending (packages, no word) · accepted."""
    if node.get("level") != "stage" and "." in node["id"]:
        return ""
    kids = [n for n in nodes_all(tdir) if n.get("parent") == node["id"]]
    if not kids:
        return "none"
    return "accepted" if stage_word(root, task, node["id"]) else "pending"


DECOMP_RU = {"none": "не разложен", "pending": "раскладка ждёт слова владельца", "accepted": "раскладка принята"}


def _natkey(nid):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", nid)]


def stage_gate(root, task, tdir, node):
    """STAGES GO ONE AFTER ANOTHER (owner, 2026-08-26, after an incident: the agent put S2 to
    wait while S1.WP6 was in work, and the board read both as «в работе»): a node of stage
    Sk may start or be shown only when the stages BEFORE it are closed whole — every nested
    node done or parked. «Before» = the stage's prerequisites by `deps` when it declares any,
    else every stage with a smaller number. (ok, [lines]) — the lines say what is open."""
    nodes = nodes_all(tdir)
    by = {n["id"]: n for n in nodes}
    sid = stage_of(node["id"])
    _w, _m, _c, deps = plan_waves(tdir)
    own = [d for d in deps.get(sid, []) if d in by]
    if own:
        prev = {stage_of(d) for d in own} - {sid}
    else:
        prev = {n["id"] for n in nodes if "." not in n["id"] and _natkey(n["id"]) < _natkey(sid)}
    open_prev = sorted((n for n in nodes if stage_of(n["id"]) in prev and node_open(n)),
                       key=lambda n: _natkey(n["id"]))
    if not open_prev:
        return True, []
    names = ", ".join(f"{n['id']} ({STATUS_RU.get(node_status(n), '?')})" for n in open_prev[:6])
    return False, [
        f"ЭТАП {sid} РАНО — предыдущий этап не закрыт целиком: {names}" + (" …" if len(open_prev) > 6 else ""),
        "  переход к следующему этапу — после закрытия всех узлов предыдущего: el plan done <узел> "
        '"<результат>" · отложить осознанно: el plan park <узел> --why "…"',
    ]


def plan_start(root, task, tdir, words, force=False, switch=None):
    """Name THE node in work. One at a time — and the previous one is never dropped in
    silence (owner, 2026-08-25: «начал делать, пошёл дальше, а work package так и не закрыл»):
    close it, put it to wait, park it, or switch WITH a reason that goes into the journal.
    A node waiting for the owner is not stepped over — his word comes first."""
    if not words:
        print("el plan start s1 wp1", file=sys.stderr)
        return 1
    nid = path_to_id(words)
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    st = node_status(node)
    mode = task_mode(tdir)
    if st in TERMINAL and not force:
        print(f"{nid} {STATUS_RU[st]} — вернуть в работу осознанно: el plan start "
              f"{nid.lower()} --force", file=sys.stderr)
        return 1
    if not force:
        ok_g, lines_g = stage_gate(root, task, tdir, node)
        if not ok_g:
            for l in lines_g:
                print(l, file=sys.stderr)
            print(f"  осознанно, в журнал: el plan start {nid.lower()} --force", file=sys.stderr)
            return 1
    # A STAGE IS WORKED THROUGH ITS PACKAGES (owner, 2026-08-26): lay it out first, show the
    # layout, record his word over it, start a package. Light mode warns; soft and strict refuse.
    kids0 = [n for n in nodes_all(tdir) if n.get("parent") == nid]
    if "." not in nid and not kids0 and not force:
        low = nid.lower()
        if mode == "light":
            print(f"этап     {nid} без пакетов — в light можно вести сам этап; правило — разложить "
                  f'перед стартом: el plan new {low} wp1 "<пакет работ>"')
        else:
            print(f"ЭТАП НЕ РАЗЛОЖЕН — {nid} перед стартом раскладывается на пакеты работ, "
                  "пакеты — на работы, работы — на подзадачи (только ближайший уровень):", file=sys.stderr)
            print(f"  предложи раскладку владельцу в чате → его «одобряю»: el accept \"<его слова>\" --for stage:{low} "
                  f'--on "<раскладка>" → запиши: el plan new {low} wp1 "<пакет работ>" … → el plan start {low}.wp1',
                  file=sys.stderr)
            print(f"  под грантом — реши в его место: el accept \"…\" --for stage:{low} --assumed \"<почему>\" · "
                  f"осознанно вести этап целиком: el plan start {low} --force", file=sys.stderr)
            return 1
    if "." in nid and not force:
        sid = stage_of(nid)
        if not stage_word(root, task, sid):
            low = sid.lower()
            if mode == "light":
                print(f"раскладка этапа {sid} без слова владельца — в light допустимо; правило — показать "
                      f'и записать: el accept "<его слова>" --for stage:{low}')
            else:
                print(f"РАСКЛАДКА ЭТАПА {sid} НЕ ПРИНЯТА — покажи её владельцу и запиши его слово: "
                      f'el accept "<его слова>" --for stage:{low}', file=sys.stderr)
                print(f'  под грантом — реши в его место: el accept "<что принимаешь>" --for stage:{low} '
                      f'--assumed "<почему>" · осознанно без слова: el plan start {nid.lower()} --force',
                      file=sys.stderr)
                return 1
    gaps = node_gaps(node, mode)
    if gaps and not force:
        print(f"у {nid} пусты поля: {', '.join(gaps)} — сначала контракт, потом работа "
              f"(el plan set {nid.lower()} <поле> \"…\"), либо --force", file=sys.stderr)
        return 1
    # THE OWNER'S DEBT holds this node (owner, 2026-08-24): the answer is his and has not
    # come — starting the node means building on a guess. --force says so out loud.
    from . import owe as _owe
    held_by = _owe.holding(root, task, f"node:{nid}")
    if held_by and not force:
        print(f"{nid} держит долг владельца — ответ есть только у него, и его пока нет:",
              file=sys.stderr)
        for it in held_by:
            print(f"  #{it['n']} {it['kind']} · {it['q'][:80]} · как: {it['how'][:60]}",
                  file=sys.stderr)
        print(f'  ответ: el owe answer <n> "<его ответ>" · не понадобилось: el owe drop <n> --why "…" '
              f"· осознанно без ответа: el plan start {nid.lower()} --force", file=sys.stderr)
        return 1
    cur = active_node(tdir)
    # GOING DEEPER IS NOT SWITCHING (2026-08-27): a task started under the package in work is
    # the same work, one level down — the package stays in work, the chain is one.
    inside = bool(cur) and nid.upper().startswith(cur["id"].upper() + ".")
    if cur and cur["id"] != nid and node_status(cur) == "active" and not inside:
        if not (switch or "").strip():
            low = cur["id"].lower()
            print(f"{cur['id']} в работе — бросить молча нельзя. Сначала скажи, что с ним:",
                  file=sys.stderr)
            print(f'  закрыть: el plan done {low} "<результат>" · ждать владельца: el plan wait {low} "…"',
                  file=sys.stderr)
            print(f'  отложить: el plan park {low} --why "…" · сменить с причиной: '
                  f'el plan start {nid.lower()} --switch "<почему>"', file=sys.stderr)
            return 1
        _set_status(root, task, tdir, cur, "open", {"started_at": None, "waiting_note": None},
                    "node-pause", f"уступил место {nid}: {switch.strip()}")
        print(f"открыт    {cur['id']} снова — уступил место {nid}: {switch.strip()}")
    for w in waiting_nodes(tdir):
        if w["id"] != nid:
            print(f"эстафета  {w['id']} по-прежнему у владельца — не трогай его сценарий; "
                  f'его слово: el accept "…" --for node:{w["id"].lower()}')
    _set_status(root, task, tdir, node, "active",
                {"started_at": now_iso(), "waiting_note": None, "block_note": None,
                 "park_note": None}, "node-start", node.get("name", ""))
    touch(root, task)
    kids = sorted((n for n in nodes_all(tdir) if n.get("parent") == nid), key=lambda x: x["id"])
    print(f"в работе  {nid} · {node.get('name','')}")
    print(f"ход       всё, что пишешь el log, ложится к {nid} — по ходу, не в конце · закрыть: "
          f'el plan done {nid.lower()} "<результат>"')
    result = [l for l in (node["_fields"].get("result") or "").splitlines() if l.strip()]
    if result:
        print(f"результат {wrap(result[0].lstrip('- ').strip(), indent='          ')}")
    crits = [l for l in (node["_fields"].get("check") or "").splitlines()
             if l.strip().startswith("-")]
    print(f"критерии  {len(crits)} — проверяй ПО ХОДУ, не в конце: el validate {nid.lower()} <N> "
          f'--met "<чем доказано>" --evidence <файл>')
    sm = sync_mark(node)
    if sm:
        print(f"остановка {sm} — показал человеку: el plan wait {nid.lower()} \"<что показал>\"")
    if kids:
        print(f"внутри    {', '.join(k['id'] for k in kids)} — крупный узел ведут его дети: "
              f"el plan start {kids[0]['id'].lower()}")
    elif "." not in nid:
        print(f"этап      ведётся целиком — правило: разложить на пакеты работ (el plan new {nid.lower()} wp1 "
              f'"<пакет>"), показать владельцу (el accept … --for stage:{nid.lower()}) и стартовать пакет')
    print(f"следы     el artifact <файл> --node {nid.lower()}  ·  el evidence <файл> --node "
          f"{nid.lower()} --check <N>")
    print(f"закрыть   el plan done {nid.lower()} \"<наблюдаемый результат>\"")
    return 0


def plan_wait(root, task, tdir, words):
    """Hand the baton to the owner: the node's stop is shown, the agent does not drive on.

    The Settings pilot (2026-08-22): after the phone went to the owner and he said «готово»,
    the agent kept navigating the screen. The state must say whose move it is."""
    if not words:
        print('el plan wait s2 "<что показал и что ждём>"', file=sys.stderr)
        return 1
    path, note = (words, "") if len(words) == 1 else (words[:-1], words[-1])
    nid = path_to_id(path)
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    if node_status(node) in TERMINAL:
        # A closed node has nothing to show (caught by the differential test 2026-08-26:
        # `plan wait` on a done stage put it back into waiting and broke the closing gate).
        print(f"{nid} {STATUS_RU[node_status(node)]} — ждать владельца может только открытый узел; "
              f'сначала el plan reopen {nid.lower()} --why "…"', file=sys.stderr)
        return 1
    cur = active_node(tdir)
    if cur and cur["id"] != nid and node_status(cur) == "active":
        # THE NODE IN WORK IS NOT PUSHED ASIDE BY A WAIT ON ANOTHER (incident 2026-08-26:
        # `el plan wait s2` while S1.WP6 was in work pushed S1.WP6 out and put S2 in
        # waiting — two nodes «в работе» and the wrong one shown to the owner).
        low = cur["id"].lower()
        print(f"в работе {cur['id']} — показать владельцу можно узел в работе, а не {nid}.", file=sys.stderr)
        print(f'  его и показывай: el plan wait {low} "<что показал>" · закончи с ним: el plan done {low} "…" · '
              f'el plan park {low} --why "…" — потом el plan start {nid.lower()}', file=sys.stderr)
        return 1
    if node_status(node) != "active":
        ok_g, lines_g = stage_gate(root, task, tdir, node)
        if not ok_g:
            for l in lines_g:
                print(l, file=sys.stderr)
            return 1
    _set_status(root, task, tdir, node, "waiting",
                {"waiting_note": note or None, "waiting_since": now_iso()}, "node-wait", note)
    touch(root, task)
    print(f"ЭСТАФЕТА У ВЛАДЕЛЬЦА  {nid} · {note or sync_subject(node) or node.get('name','')}")
    print("          агент не управляет устройством и не ходит по экранам — ждём его слово")
    print(f'его слово el accept "<его слова дословно>" --for node:{nid.lower()}   ·   '
          f"принял и закрываем: добавь --close")
    return 0


def node_resume(root, task, tdir, node):
    """The owner's word came back — the baton returns to the agent. The node goes back to work
    (active) — or, if the agent is already on another node, to open with the word noted, to be
    continued by `el plan start`."""
    busy = active_node(tdir)
    if busy and node_status(busy) == "active" and busy["id"] != node["id"]:
        _set_status(root, task, tdir, node, "open", {"waiting_note": None}, "node-resume",
                    "слово владельца получено; продолжить после " + busy["id"])
        return "open"
    _set_status(root, task, tdir, node, "active", {"waiting_note": None}, "node-resume",
                "слово владельца получено")
    return "active"


def plan_hold(root, task, tdir, words, status, why, owe_n=None):
    """blocked — stuck on something named; parked — set aside on purpose (terminal).

    `--owe N` names THE OWNER'S DEBT as the obstacle (owner, 2026-08-24): the work reached
    the point where only his answer opens the way. The block's reason is the debt itself,
    the debt is tied to the node, and `el owe answer N` lets the node go."""
    if not words:
        print(f'el plan {"block" if status == "blocked" else "park"} s1 wp1 --why "<почему>"'
              + (" · --owe <n> — держит долг владельца" if status == "blocked" else ""),
              file=sys.stderr)
        return 1
    nid = path_to_id(words)
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    why = (why or "").strip()
    debt = None
    if owe_n is not None and status == "blocked":
        from . import owe as _owe
        debt = next((x for x in _owe.ledger(root, task) if x["n"] == owe_n), None)
        if not debt:
            print(f"нет долга #{owe_n} — список: el owe", file=sys.stderr)
            return 1
        if debt["status"] != "open":
            print(f"долг #{owe_n} уже закрыт ({debt['status']}) — держать узел не может",
                  file=sys.stderr)
            return 1
        why = f"ждёт ответа владельца #{owe_n}: {debt['q']}" + (f" — {why}" if why else "")
    if not why:
        print("скажи --why — блок или отложенное без причины неотличимы от забытого",
              file=sys.stderr)
        return 1
    key = "block_note" if status == "blocked" else "park_note"
    _set_status(root, task, tdir, node, status, {key: why, "waiting_note": None},
                "node-" + status, why)
    if debt and f"node:{nid}" not in debt["holds"]:
        journal(root, task, "owe-holds", f"#{owe_n} держит node:{nid}",
                {"n": owe_n, "holds": f"node:{nid}"})
        _owe._md(root, task)
    touch(root, task)
    print(f"{STATUS_RU[status]}  {nid} — {why}")
    if status == "parked":
        for l in parent_closable_lines(tdir, nid):
            print(l)
    if debt:
        print(f'снять    el owe answer {owe_n} "<его ответ>" — узел отпустится сам')
    elif status == "blocked":
        print(f"снять    el plan start {nid.lower()} — когда препятствие убрано")
    else:
        print(f"вернуть  el plan start {nid.lower()} --force")
        # Parking closes the node for the gates, NOT its criteria: the owner's rule
        # (2026-08-23) — no automatic write-offs, each criterion is declined by hand with
        # its own «потому что». The validate gate will demand the verdicts anyway; say it
        # here, while the reason is still fresh.
        try:
            from .validate import criteria_of, validation_parse
            verd = validation_parse(tdir)
            n_open = sum(1 for i in range(1, len(criteria_of(node)) + 1)
                         if verd.get((nid, i), ("open", ""))[0] == "open")
            if n_open:
                print(f"критерии {n_open} без вердикта — снятие только явное, каждый со своим "
                      f'«потому что»: el validate {nid.lower()} <N> --declined "потому что …"')
        except Exception:
            pass
    return 0


def parent_closable(tdir, nid):
    """The parent of `nid` when every child of it is closed and the parent is still open —
    the moment to say so (owner, 2026-08-26: «закрыл все дочерние и промолчал, а пакет висит»).
    (parent node, n_children) or (None, 0)."""
    parent = nid.rsplit(".", 1)[0] if "." in nid else ""
    if not parent:
        return None, 0
    par = node_read(tdir, parent)
    if not par or not node_open(par):
        return None, 0
    kids = [n for n in nodes_all(tdir) if (n.get("parent") or "") == parent]
    if kids and all(not node_open(k) for k in kids):
        return par, len(kids)
    return None, 0


def parent_closable_lines(tdir, nid):
    par, n = parent_closable(tdir, nid)
    if not par:
        return []
    low = par["id"].lower()
    return [f"родитель {par['id']} · {par.get('name', '')[:50]} — все узлы внутри закрыты ({n}/{n}), а он открыт: "
            "обычно больше делать нечего",
            f'         закрой: el plan done {low} "<результат>" · или скажи, что ещё осталось: '
            f'el plan new {low.replace(".", " ")} <следующий> "<имя>" — молча не оставляй']


def plan_cancel(root, task, tdir, words, why):
    """CONDITIONAL WORK THAT WAS NOT NEEDED (feedback 2026-08-26: T8 «resolve a confirmed
    firewall issue» — the comparison found none; `park` said «отложен», which reads as «later»,
    and left the criterion without a verdict for a second command by hand). One explicit act:
    the node closes for the gates as «не потребовался», every open criterion of it is declined
    with the same «потому что» — explicit, once, written down — and reopen stays possible.
    Parent nodes are not cancelled through their children: cancel a leaf, or a node whose
    children are all closed."""
    why = (why or "").strip()
    if not words or not why:
        print('el plan cancel s1 wp6 t8 --why "<почему работа не потребовалась>"', file=sys.stderr)
        return 1
    nid = path_to_id(words)
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    st = node_status(node)
    if st in TERMINAL:
        print(f"{nid} уже {status_ru(node)} — отменять нечего; вернуть: el plan reopen {nid.lower()} --why \"…\"",
              file=sys.stderr)
        return 1
    kids_open = [n["id"] for n in nodes_all(tdir) if (n.get("parent") or "") == nid and node_open(n)]
    if kids_open:
        print(f"внутри {nid} открыты узлы: {', '.join(kids_open)} — отмени или закрой их первыми", file=sys.stderr)
        return 1
    from .validate import checklist_node, criteria_of, validation_parse, validation_render
    raw = validation_parse(tdir)
    crits = criteria_of(node)
    declined = []
    for i in range(1, len(crits) + 1):
        if raw.get((nid, i), ("open", ""))[0] == "open":
            raw[(nid, i)] = ("declined", why)
            declined.append(i)
    if declined:
        vnodes = [n for n in nodes_all(tdir) if criteria_of(n)] + checklist_node(tdir)
        validation_render(tdir, vnodes, raw)
    _set_status(root, task, tdir, node, "parked",
                {"park_note": why, "cancelled": True, "waiting_note": None, "block_note": None,
                 "started_at": None},
                "node-cancelled", why)
    for i in declined:
        journal(root, task, "validated", f"{nid}.{i} declined: {why[:120]}")
    touch(root, task)
    print(f"не потребовался  {nid} · {node.get('name', '')} — {why}")
    print(f"критерии {len(declined)} снят(о) тем же «потому что»" if declined else "критериев без вердикта не было")
    print(f'вернуть  el plan reopen {nid.lower()} --why "<что изменилось>"')
    for l in parent_closable_lines(tdir, nid):
        print(l)
    return 0


def plan_unfold(root, task, tdir, words, what=None, after=None):
    """МЕСТО РАСКРЫТИЯ — законная дыра в маршруте (его решение 2026-08-24).

    His case: a legal question where the plan CANNOT be built to the end — «просто сбор
    информации, потом этап решение что делаем дальше, и после этого план достраивается».
    Demanding a complete plan there forces the agent to invent one; dropping the demand
    brings back silent holes. The way out is the planning package of earned-value practice:
    a known piece of FUTURE work that holds its place in the plan without detail, and is
    unfolded later into ordinary nodes.

    So integrity counts an unfold as coverage — but only a DECLARED one. Three things make
    it declared, and without them it is just «потом разберёмся»:
      что       what exactly must become known (not «разберёмся» — «узнаем, разрешает ли
                лицензия коммерческое использование»)
      после     after which event it stops being unknown — the node or the decision
      покрывает which piece of the goal stands behind it (el plan cover)"""
    if not words:
        print('el plan unfold s3 "<что должно стать известно>" --after s2', file=sys.stderr)
        print("  место раскрытия — объявленная дыра: план тут не построить, пока не узнаем.",
              file=sys.stderr)
        print("  дыра, названная вслух, — часть маршрута; молчаливая — провал.", file=sys.stderr)
        return 1
    path, text = (words, "") if len(words) == 1 else (words[:-1], words[-1])
    nid = path_to_id(path)
    node = node_read(tdir, nid)
    what = (what or text or "").strip()
    if not what:
        print(f'нужно сказать, ЧТО должно стать известно: el plan unfold {nid.lower()} '
              '"<что узнаем>" --after <узел>', file=sys.stderr)
        return 1
    if not after:
        print("нужно --after: после чего оно перестанет быть неизвестным (узел, решение).",
              file=sys.stderr)
        print(f'  el plan unfold {nid.lower()} "{what[:40]}" --after s2', file=sys.stderr)
        print("  без этого раскрытие — способ не думать, а не место в маршруте.",
              file=sys.stderr)
        return 1
    if not node:
        meta = {"level": level_of_depth(nid), "parent": nid.rsplit(".", 1)[0] if "." in nid else "",
                "name": f"раскроется после {after.upper()}", "status": "open",
                "created_at": now_iso()}
        # NO result, NO criteria: a place of unfolding promises nothing to verify — it
        # promises to BE UNFOLDED. Giving it a synthetic criterion put a fake line into the
        # ledger, and the ledger is where real promises live. Whether it unfolded is read
        # from the graph (children appeared) and enforced by the gates.
        fields = {}
        node = dict(meta, id=nid, _fields=fields)
    else:
        meta = {k: v for k, v in node.items() if k not in ("_fields", "id")}
        fields = dict(node["_fields"])
    meta["unfold"] = what
    meta["unfold_after"] = after.upper()
    node_write(tdir, nid, meta, fields)
    journal(root, task, "unfold", f"{nid}: {what[:120]} — после {after.upper()}",
            {"node": nid})
    touch(root, task)
    print(f"место раскрытия {nid} · станет известно: {what[:70]}")
    print(f"раскроется      после {after.upper()}")
    print(f'привяжи к цели  el plan cover {nid.lower()} ifr <N>  — что за этой дырой стоит')
    print(f'раскрыть потом  el plan new {nid.lower().replace(".", " ")} wp1 "<работа>" — '
          "и место раскрытия закроется само, когда появятся дети")
    return 0


def plan_rm(root, task, tdir, words):
    if not words:
        print("el plan rm s1 wp1", file=sys.stderr)
        return 1
    nid = path_to_id(words)
    if not node_exists(tdir, nid):
        # Idempotent (feedback 2026-08-26: a chained «rm && rm && rm» stopped at the first
        # node already gone): nothing to remove is not an error.
        print(f"узла {nid} уже нет")
        return 0
    kids = [n["id"] for n in nodes_all(tdir) if n["id"].startswith(nid + ".")]
    if kids:
        print(f"внутри {nid} есть узлы: {', '.join(kids)} — сперва убери их", file=sys.stderr)
        return 1
    node_retract(tdir, nid, "el plan rm")
    journal(root, task, "node-removed", nid)
    touch(root, task)
    print(f"убран {nid}")
    return 0


def plan_rename(root, task, tdir, words, why):
    """A node keeps its identity under a new id (feedback 2026-08-26: fixing S1.WP6.WP1 →
    S1.WP6.T1 meant rm + new and lost the contract). The subtree moves with it, every `deps`
    that named the old id is rewritten, the validation ledger keeps its verdicts under the new
    heading, and the journal says from → to and why."""
    why = (why or "").strip()
    if len(words) < 2 or not why:
        print('el plan rename s1.wp6.wp1 s1.wp6.t1 --why "<почему>"', file=sys.stderr)
        return 1
    old, new = path_to_id([words[0]]), path_to_id([words[1]])
    if not node_read(tdir, old):
        print(f"нет узла {old}", file=sys.stderr)
        return 1
    if node_read(tdir, new):
        print(f"узел {new} уже есть", file=sys.stderr)
        return 1
    want = canonical_gap(new)
    if want:
        print(f"{new} — не тот уровень в имени (этап S1 · пакет S1.WP1 · задача S1.WP1.T1 · подзадача "
              f"S1.WP1.T1.ST1)" + (f"; так: {want}" if want != "?" else ""), file=sys.stderr)
        return 1
    new_parent = new.rsplit(".", 1)[0] if "." in new else ""
    if new_parent and not node_read(tdir, new_parent):
        print(f"нет родителя {new_parent} — заведи его первым", file=sys.stderr)
        return 1
    moved = []
    for n in sorted(nodes_all(tdir), key=lambda x: x["id"]):
        if n["id"] == old or n["id"].startswith(old + "."):
            nid2 = new + n["id"][len(old):]
            meta = {k: v for k, v in n.items() if k not in ("_fields", "id")}
            meta["parent"] = nid2.rsplit(".", 1)[0] if "." in nid2 else ""
            meta["level"] = level_of_depth(nid2)
            node_write(tdir, nid2, meta, n["_fields"])
            node_retract(tdir, n["id"], f"переименован в {nid2}")
            moved.append((n["id"], nid2))
    # every `deps` that named the old id (or a node under it)
    touched = []
    pat = re.compile(r"\b" + re.escape(old) + r"(?=\.|\b)", re.I)
    for n in nodes_all(tdir):
        deps_txt = n["_fields"].get("deps") or ""
        if pat.search(deps_txt):
            fields = dict(n["_fields"]); fields["deps"] = pat.sub(new, deps_txt)
            node_write(tdir, n["id"], {k: v for k, v in n.items() if k not in ("_fields", "id")}, fields)
            touched.append(n["id"])
    # the validation ledger keeps its verdicts
    vpath = os.path.join(tdir, "validation.md")
    if os.path.exists(vpath):
        vt = open(vpath, encoding="utf-8").read()
        vt2 = pat.sub(new, vt)
        if vt2 != vt:
            with open(vpath, "w", encoding="utf-8") as fh:
                fh.write(vt2)
            touched.append("validation.md")
    journal(root, task, "node-renamed", f"{old} → {new}: {why}"[:160],
            {"from": old, "to": new, "moved": [m[1] for m in moved], "touched": touched})
    touch(root, task)
    print(f"переименован  {old} → {new} — {why}")
    if len(moved) > 1:
        print(f"  вместе с ним: {', '.join(m[1] for m in moved[1:])}")
    if touched:
        print(f"  поправлены ссылки: {', '.join(touched)}")
    return 0


def cmd_sync(args):
    """The stops along the road — passed, current, ahead. The navigator view he asked for.

    A plan that only says what to do reads like a conveyor. The same plan with its stops marked
    reads like a route: here we show what came out, here we ask whether the goal still stands.
    That second question is the point — the destination itself may have moved while we worked."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    nodes = sorted(nodes_all(tdir), key=lambda x: x["id"])
    stops = [n for n in nodes if node_sync(n)]
    if not nodes:
        print("плана ещё нет.")
        return 0
    if not stops:
        print("ни у одного узла не назначена точка синхронизации.")
        print('  el plan set s1 sync "СВЕРКА — покажу собранное сообщение, жду ответа"')
        print("  остановки планируются заранее: решённая в моменте решается тем, кто устал.")
        return 0
    done_ids = {n["id"] for n in nodes if n.get("status") == "done"}
    print("ОСТАНОВКИ НА ПУТИ — где агент показывает работу и, где сказано, ждёт ответа\n")
    upcoming = None
    for n in stops:
        passed = n["id"] in done_ids
        mark = "✓ пройдена" if passed else ("▶ СЛЕДУЮЩАЯ" if upcoming is None else "· впереди")
        if not passed and upcoming is None:
            upcoming = n
        print(f"  {mark:<12} {sync_mark(n):<14} {n['id']} · {n.get('name','')}")
        body = (n["_fields"].get("sync") or "").strip()
        for line in body.splitlines():
            if line.strip():
                print(f"               {wrap(line.strip('- ').strip(), indent='               ')}")
        print()
    if upcoming:
        kind = node_sync(upcoming)
        print(f"ближайшая    {upcoming['id']} — {sync_mark(upcoming)}")
        if kind == "ПОКАЗ":
            print("             показать и идти дальше, ответа не ждать")
        elif kind == "РАЗВИЛКА":
            print("             показать и ДОЖДАТЬСЯ ответа: тут выясняется неизвестное, "
                  "и от ответа зависит, куда идём дальше")
        else:
            print("             без его слова дальше нельзя — здесь необратимое")
    else:
        print("все остановки пройдены")
    return 0


# ── THE PLAN AS A LADDER (2026-08-27): stages · their promises · their stops · coverage ──

def stages(tdir):
    return [n for n in nodes_all(tdir) if "." not in n["id"] and not n.get("cancelled")]


def node_promises(tdir, nid):
    root, task = _rt(tdir)
    return [p for p in _store.promises(root, task) if (p.get("at") or "").upper() == nid.upper()]


def plan_promise(root, task, tdir, words, how):
    """`el plan promise s1 "<what the stage must deliver>" --how "<чем проверим>"` — a promise
    hung on the node, born on this phase, not_validated until a verdict."""
    if len(words) < 2:
        print('el plan promise s1 "<что этап обязан выдать>" --how "<чем проверим>"', file=sys.stderr)
        return 1
    nid = path_to_id(words[:-1]); text = words[-1]
    if not node_exists(tdir, nid):
        print(f"нет узла {nid}", file=sys.stderr); return 1
    phase = task_meta(root, task).get("phase", "plan")
    out, reason = _store.promise(root, task, {"kind": "criterion", "at": nid, "born": phase, "text": text,
                                              "how": how or "", "by": "agent"})
    if reason:
        print(f"обещание не записано: {reason}", file=sys.stderr); return 1
    journal(root, task, "promise", text[:120], {"id": out["id"], "at": nid, "born": phase})
    print(f"recorded  {out['id']} · обещание на {nid} · not_validated · чем проверим: {(how or '')[:60]}")
    return 0


def plan_step_done(tdir, key, mode=None):
    from .state import task_mode as _tm
    mode = mode or _tm(tdir)
    st = stages(tdir)
    if key == "stages":
        return bool(st)
    if key == "promises":
        return bool(st) and all(node_promises(tdir, n["id"]) for n in st)
    if key == "sync":
        return bool(st) and all(node_sync(n) for n in st)
    if key == "coverage":
        try:
            from .integrity import gaps, has_goal
            return bool(st) and has_goal(tdir) and not any(gaps(tdir).values())
        except Exception:
            return False
    if key == "network":
        return bool(st)
    if key == "approval":
        from .context import word_over
        w, stale = word_over(tdir, "plan")
        return bool(w) and not stale
    return False
