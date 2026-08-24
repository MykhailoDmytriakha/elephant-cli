"""Phase 3 — PLAN: the fractal of nodes, the eight fields that make a node a contract,
the stops along the road. A node is a markdown file under nodes/ with frontmatter and
one `## field · heading` section per field; the path IS the hierarchy (S1 · S1.WP1 …).
The field set is protocol.NODE_FIELDS.
"""
import json, os, re, sys
from .protocol import NODE_FIELDS, NODE_KEYS, NODE_KEYS_OPTIONAL, PLAN_LEVELS
from . import autonomy
from .state import (pick_task, current_task, fm_read, fm_write, journal, now_iso, require_root,
                    resolve_task, task_mode, touch)
from .term import wrap


# ── PLAN commands: one verb, addressed by PATH ────────────────────────────────
#
# The owner asked for it in the shape he actually types (2026-08-19): `el plan s1 wp1`. So the
# address IS the hierarchy — `S1` is a stage, `S1.WP1` a work package inside it, `S1.WP1.T1` a
# task inside that. Nothing has to be declared: the level and the parent both fall out of how
# deep the path is, and a child under a missing parent is simply impossible to address.
PLAN_FIELD_SET = set(NODE_KEYS)


def nodes_dir(tdir):
    return os.path.join(tdir, "nodes")


def node_path(tdir, nid):
    return os.path.join(nodes_dir(tdir), f"{nid}.md")


def node_read(tdir, nid):
    path = node_path(tdir, nid)
    if not os.path.exists(path):
        return None
    meta, body = fm_read(path)
    fields = {}
    cur = None
    for line in body.splitlines():
        m = re.match(r"##\s+(\w+)\s+·", line)
        if m:
            cur = m.group(1)
            fields[cur] = []
        elif cur:
            fields[cur].append(line)
    # Fields written before the CLI unescaped "\n" hold the two characters literally; read
    # them as newlines, so the four lines of a stop are lines and the page shows breaks.
    meta["_fields"] = {k: "\n".join(v).strip().replace("\\n", "\n") for k, v in fields.items()}
    meta["id"] = nid
    return meta


def node_write(tdir, nid, meta, fields):
    body = f"# {nid} · {meta.get('name','')}\n"
    for key, head, _d in NODE_FIELDS:
        body += f"\n## {key} · {head}\n{fields.get(key, '').strip() or '_пусто_'}\n"
    fm_write(node_path(tdir, nid), {k: v for k, v in meta.items()
                                    if k not in ("_fields", "id")}, body)


def nodes_all(tdir):
    d = nodes_dir(tdir)
    if not os.path.isdir(d):
        return []
    out = [node_read(tdir, f[:-3]) for f in sorted(os.listdir(d)) if f.endswith(".md")]
    return [n for n in out if n]


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
    keys = LIGHT_KEYS if mode == "light" else NODE_KEYS
    return [k for k in keys if k not in NODE_KEYS_OPTIONAL
            and (not f.get(k) or f[k].strip() in ("_пусто_", ""))]


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
    for n in nodes:
        if node_status(n) == "active":
            return n
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
        return plan_new(root, task, tdir, words[1:], getattr(args, "force", False))
    if verb == "set":
        return plan_set(root, task, tdir, words[1:], getattr(args, "replace", False))
    if verb in ("rm", "drop"):
        return plan_rm(root, task, tdir, words[1:])
    if verb == "done":
        return plan_done(root, task, tdir, words[1:], getattr(args, "force", False))
    if verb == "start":
        return plan_start(root, task, tdir, words[1:], getattr(args, "force", False))
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


def plan_tree(tdir, root=None, task=None):
    """The plan AND its state: what is closed, what is open, what moved recently.

    A plan that only lists intentions is read once and then goes stale in the head. The owner
    asked for the state to be visible in the same view (2026-08-19): "чтобы показывало статус —
    что сделано, что изменено, что добавлено"."""
    nodes = nodes_all(tdir)
    mode = task_mode(tdir)
    if not nodes:
        pm = os.path.join(tdir, "plan.md")
        if os.path.exists(pm):
            print(open(pm, encoding="utf-8").read().rstrip())
            print()
        print("узлов нет.")
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
    print()

    for n in sorted(nodes, key=lambda x: x["id"]):
        gaps = node_gaps(n, mode)
        depth = n["id"].count(".")
        pad = "  " * depth
        st = node_status(n)
        mark = STATUS_MARK.get(st, "·")
        note = {"waiting": n.get("waiting_note"), "blocked": n.get("block_note"),
                "parked": n.get("park_note")}.get(st)
        state = STATUS_RU.get(st, st) + (f": {str(note)[:80]}" if note else "")
        if st == "open":
            state = "заполняется" if gaps else "готов к старту"
        sm = sync_mark(n)
        subj = sync_subject(n)
        print(f"{pad}{mark} {n['id']} · {n.get('name','')}  [{n.get('level','?')}]")
        print(f"{pad}    {state}"
              f"{'  ·  ' + sm if sm else ''}"
              f"{'  ·  пусто: ' + ', '.join(gaps) if gaps else ''}")
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

    pm = os.path.join(tdir, "plan.md")
    if os.path.exists(pm):
        print("\nСЕТЕВОЙ ПЛАН")
        print(open(pm, encoding="utf-8").read().rstrip())
    print("\nподробно     el plan s1 · el plan s1 wp1 · el sync — только остановки · "
          "в работу: el plan start s1")
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
    parent = nid.rsplit(".", 1)[0] if "." in nid else ""
    if parent:
        par = node_read(tdir, parent)
        if not par:
            print(f"нет родителя {parent} — заведи его первым", file=sys.stderr)
            return 1
        gaps = node_gaps(par, task_mode(tdir))
        if gaps:
            print(f"родитель {parent} ещё не заполнен: {', '.join(gaps)}", file=sys.stderr)
            print("  разворачивать вниз можно только заполненный узел: поэтапная",
                  file=sys.stderr)
            print("  декомпозиция закон (§5), разложить всё вперёд убило v1.", file=sys.stderr)
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
    os.makedirs(nodes_dir(tdir), exist_ok=True)
    meta = {"level": level_of_depth(nid), "parent": parent, "name": name.strip(),
            "status": "open", "created_at": now_iso()}
    node_write(tdir, nid, meta, {})
    journal(root, task, "node", f"{nid} [{meta['level']}] {meta['name'][:70]}",
            {"parent": parent})
    touch(root, task)
    print(f"узел {nid} · {meta['level']} · {meta['name']}")
    print(f"дальше   el plan {nid.lower().replace('.', ' ')} — какие из восьми полей пусты")
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
        missing = [w for w in ("показываю:", "увидишь:", "потрогать:", "от тебя:")
                   if w not in low]
        if missing:
            print(f"в остановке нет строк: {', '.join(missing)}", file=sys.stderr)
            print("  остановка описывается четырьмя строками, и каждая отвечает на своё:",
                  file=sys.stderr)
            print("  показываю: — предмет · увидишь: — куда смотреть ·", file=sys.stderr)
            print("  потрогать: — чем он поработает САМ · от тебя: — ничего/поправка/решение",
                  file=sys.stderr)
            print("  без них остановка превращается в «ну как?», а это не вопрос.",
                  file=sys.stderr)
            print(f'  готовый шаблон:  el plan set {nid.lower()} sync "показываю: <что>'
                  '\\nувидишь: <куда смотреть>\\nпотрогать: <что он сделает сам>'
                  '\\nот тебя: <ничего|поправка|решение>"', file=sys.stderr)
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
    if key == "check" and n < 5:
        print("         критериев меньше пяти — по спеке узел ещё не контракт")
    gaps = node_gaps(node_read(tdir, nid), task_mode(tdir))
    print(f"пусто    {', '.join(gaps) if gaps else '— все поля контракта заполнены'}")
    return 0


def plan_done(root, task, tdir, words, force=False):
    """Close a node — and refuse to close it past a stop that has not happened.

    This is where the sync point stops being a note and becomes a mechanism. A node whose stop
    is СВЕРКА or РАЗРЕШЕНИЕ cannot be marked done until the owner's words are recorded after it:
    `el accept`. Otherwise the plan would carry beautifully drawn stops that the agent drives
    straight past — which is exactly what happens when a rule lives only in prose."""
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
    from .validate import criteria_of, validation_parse  # function-level: validate imports plan
    kids_open = [n["id"] for n in nodes_all(tdir)
                 if (n.get("parent") or "") == nid and node_open(n)]
    if kids_open and not force:
        print(f"НЕ ЗАКРОЮ {nid} — родитель закрывается после детей, а открыты: "
              f"{', '.join(kids_open)}", file=sys.stderr)
        print("  закрой их (el plan done) или отложи осознанно (el plan park --why)",
              file=sys.stderr)
        return 1
    verdicts = validation_parse(tdir)
    crits = criteria_of(node)
    no_verdict = [i for i in range(1, len(crits) + 1)
                  if verdicts.get((nid, i), ("open", ""))[0] == "open"]
    bad = [(i, verdicts[(nid, i)][0]) for i in range(1, len(crits) + 1)
           if verdicts.get((nid, i), ("open", ""))[0] in ("failed", "unverified")]
    if no_verdict and not force:
        print(f"НЕ ЗАКРОЮ {nid} — критерии без вердикта: "
              f"{', '.join(str(i) for i in no_verdict)}. Проверь каждый:", file=sys.stderr)
        print(f'  el validate {nid.lower()} <N> --met "<чем доказано>" --evidence evidence/<файл>',
              file=sys.stderr)
        print("  снят вместе с работой — только явно и со своим «потому что»: "
              f'el validate {nid.lower()} <N> --declined "потому что …"', file=sys.stderr)
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
    if kind in ("РАЗВИЛКА", "РАЗРЕШЕНИЕ") and not force:
        ap = os.path.join(tdir, "acceptance.md")
        said_after = False
        if os.path.exists(ap):
            # his word counts only if it landed AFTER the node was last written
            said_after = os.path.getmtime(ap) >= os.path.getmtime(node_path(tdir, nid))
        if not said_after:
            print(f"НЕ ЗАКРОЮ — на {nid} стоит остановка ({kind}), а его слова нет.",
                  file=sys.stderr)
            print(f"  что показать: {(node['_fields'].get('sync') or '').strip()[:200]}",
                  file=sys.stderr)
            print('  показать → услышать → записать: el accept "<его слова>"', file=sys.stderr)
            print("  остановка, мимо которой можно проехать, — это не остановка.",
                  file=sys.stderr)
            return 1
    meta = {k: v for k, v in node.items() if k not in ("_fields", "id")}
    meta["status"] = "done"
    meta["closed_at"] = now_iso()
    if result:
        meta["result_note"] = result
    node_write(tdir, nid, meta, node["_fields"])
    journal(root, task, "node-done", f"{nid}: {result[:120]}", {"sync": kind or None})
    touch(root, task)
    print(f"закрыт {nid}" + (f" · {result[:80]}" if result else ""))
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
        print(f"дальше   el plan start {left[0].lower()} — следующий в работу")
    return 0


def plan_start(root, task, tdir, words, force=False):
    """Name THE node in work. One at a time: starting another steps the previous back to open.
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
    # STRICT: a stage is worked through its works — decompose before you start it.
    kids0 = [n for n in nodes_all(tdir) if n.get("parent") == nid]
    if mode == "strict" and node.get("level") == "stage" and not kids0 and not force:
        print(f"СТРОГО — этап {nid} перед работой раскладывается на работы: "
              f'el plan new {nid.lower()} wp1 "<работа>" — и стартуй работу', file=sys.stderr)
        return 1
    cur = active_node(tdir)
    if cur and cur["id"] != nid and node_status(cur) == "active":
        _set_status(root, task, tdir, cur, "open", {"started_at": None, "waiting_note": None},
                    "node-pause", f"уступил место {nid}")
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
    elif node.get("level") == "stage":
        print(f"этап      крупный? разложи перед работой — el plan new {nid.lower()} wp1 "
              f'"<работа>" — и стартуй работу; мелкий — делай прямо здесь')
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
    cur = active_node(tdir)
    if cur and cur["id"] != nid and node_status(cur) == "active":
        _set_status(root, task, tdir, cur, "open", {"started_at": None}, "node-pause",
                    f"уступил место {nid}")
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
    path = node_path(tdir, nid)
    if not os.path.exists(path):
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    kids = [n["id"] for n in nodes_all(tdir) if n["id"].startswith(nid + ".")]
    if kids:
        print(f"внутри {nid} есть узлы: {', '.join(kids)} — сперва убери их", file=sys.stderr)
        return 1
    os.remove(path)
    journal(root, task, "node-removed", nid)
    touch(root, task)
    print(f"убран {nid}")
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
