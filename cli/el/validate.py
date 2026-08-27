"""Phase 5 — VALIDATE: the ledger. Criteria come from the plan's nodes (the `check`
field) and can only be given a verdict here, one at a time; the text is never edited.
"""
import os, re, sys
from .protocol import CONTEXT_FILES
from .state import current_task, journal, pick_task, require_root, resolve_task, touch, write
from .state import path_marks
from .plan import STATUS_RU, node_open, node_status, nodes_all, path_to_id
from .amend import word_given_on


# ── Проверка по критериям плана ────────────────────────────────────────────────
#
# The criteria are written in PLAN, one node at a time, and until now nobody ever read them
# back: `el forward` out of validate only asked that a file called validation.md exist, and an
# agent writes that file itself. Five measurable criteria per node turned into decoration.
#
# Owner, 2026-08-20: "по el validate должен проверять что все этапы и внутренние задачи,
# их валидации которые лежат там, все закрыты... и чтобы после execution можно было сверять".
#
# So the ledger is GENERATED from the nodes and can only be filled in one criterion at a time.
# Text always comes from the plan, so a criterion cannot quietly drift into something easier to
# pass; only the verdict and its proof are added here.



def criteria_of(node):
    """The node's criteria — its PROMISES from the registry (2026-08-27), in the order they
    were born; a node written before that still reads its `check` field."""
    proms = node.get("_promises") or []
    if proms:
        return [f"{p['id']} · {p.get('text') or p.get('name') or ''}" for p in proms]
    raw = (node.get("_fields", {}) or {}).get("check") or ""
    out, cur = [], ""
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if cur:
                out.append(cur.strip())
            cur = stripped[2:]
        elif stripped and cur:
            cur += " " + stripped
    if cur:
        out.append(cur.strip())
    return out


def _rt(tdir):
    tdir = os.path.abspath(tdir.rstrip("/"))
    return os.path.dirname(tdir), os.path.basename(tdir)


def checklist_node(tdir):
    """The promises hung on the ROOT, as two pseudo-nodes of the ledger (2026-08-27):
    IFR — the acceptance checklist, what he checks by hand; TASK — the rest of the root's
    promises (success criteria · metrics · engineering promises from думание). They carry
    `_promises` like every node, so verdicts land on promise ids."""
    from . import store
    root_, task_ = _rt(tdir)
    at_root = [p for p in store.promises(root_, task_) if p.get("at", store.ROOT) == store.ROOT]
    out = []
    ifr = [p for p in at_root if p.get("kind") == "checklist"]
    rest = [p for p in at_root if p.get("kind") != "checklist"]
    if rest:
        out.append({"id": "TASK", "name": "обещания задачи — критерии · метрики · инженерные", "_fields": {}, "_promises": rest})
    if ifr:
        out.append({"id": "IFR", "name": "чек-лист приёмки (из ИФР)", "_fields": {}, "_promises": ifr})
    return out


def baseline_line(tdir):
    """The before-measurement, so the comparison is in front of the eye, not in memory."""
    path = os.path.join(tdir, "thinking", "baseline.md")
    if not os.path.exists(path):
        return ""
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("_"):
            return line[:200]
    return ""


# The ledger's words and the registry's words — one map, both ways.
_TO_LEDGER = {"passed": "met", "failed": "failed", "waived": "declined", "unverified": "unverified",
              "covered": "covered", "not_validated": "open"}
_TO_REGISTRY = {v: k for k, v in _TO_LEDGER.items()}


def _ledger_nodes(tdir):
    return [n for n in nodes_all(tdir) if criteria_of(n)] + checklist_node(tdir)


def validation_parse(tdir):
    """Verdicts already recorded, keyed by (node id, criterion number) — folded out of the
    verdict events in checks.jsonl (2026-08-27); the ledger file is gone."""
    from . import store
    root_, task_ = _rt(tdir)
    out = {}
    for n in _ledger_nodes(tdir):
        for i, p in enumerate(n.get("_promises") or [], 1):
            st, proof, why = store.verdict_of(root_, task_, p["id"])
            if st == store.NOT_VALIDATED:
                continue
            out[(n["id"], i)] = (_TO_LEDGER.get(st, "open"), proof if st != "waived" else (proof or why))
    return out


def validation_render(tdir, nodes, verdicts):
    """Write what CHANGED as verdict events — the registry is append-only, the ledger is
    its fold. Called with the full picture the way the file writer was."""
    from . import store
    root_, task_ = _rt(tdir)
    have = validation_parse(tdir)
    by_id = {n["id"]: n for n in _ledger_nodes(tdir)}
    for (nid, i), (st, proof) in verdicts.items():
        if have.get((nid, i)) == (st, proof):
            continue
        n = by_id.get(nid)
        proms = (n or {}).get("_promises") or []
        if not n or i > len(proms):
            continue
        store.verdict(root_, task_, proms[i - 1]["id"], _TO_REGISTRY.get(st, "not_validated"), proof, by="agent")
    touch_ = None


# ── Покрыт другим узлом — вердикт-указатель ───────────────────────────────────
#
# The fifth mark is not a fifth verdict. An agent (Copilot, 2026-08-24) had to close WP1
# and WP2 whose proof would only come from the end-to-end run in WP4/WP5, and the only
# door was `--declined` — the CLI printed «снят» over work that was never cancelled, and
# the link «the proof lives downstream» survived only as prose inside ten reasons.
#
# `--covered-by <node[.N]>` records a POINTER: the criterion's verdict IS the verdict of
# what it points at, derived at read time the way a phase is derived from the journal.
# While the target is undecided the criterion reads «ждёт S1.WP4» and COUNTS AS A DEBT
# (unverified): the node it belongs to may close — the debt travels downstream and is
# named there — but the task does not leave validate over it. When the target comes in
# met, the criterion resolves to met by itself; failed there — failed here. Nothing is
# copied, so nothing can drift.

def covered_target(proof):
    """`S1.WP4 · why` → ("S1.WP4", None) · `S1.WP4.2 · why` → ("S1.WP4", 2)."""
    head = proof.split("·", 1)[0].strip()
    parts = [p for p in head.split(".") if p]
    if len(parts) > 1 and parts[-1].isdigit():
        return ".".join(parts[:-1]).upper(), int(parts[-1])
    return head.upper(), None


def resolve_verdicts(nodes, verdicts):
    """The ledger with every pointer followed: (resolved verdicts, cycle keys).

    A covered criterion takes the verdict of its target — one criterion, or a whole node
    read by the matryoshka law (own criteria + everything below it): any failed → failed;
    all met (declined ones may sit among them) → met; all declined → declined; anything
    still open → unverified, the travelling debt. Its proof is rewritten as «ждёт S1.WP4 ·
    why», so every screen that prints a proof says where the answer will come from."""
    ncrit = {n["id"]: len(criteria_of(n)) for n in nodes}
    cycles = set()

    def one(key, seen):
        st, proof = verdicts.get(key, ("open", ""))
        if st != "covered":
            return st
        if key in seen:
            cycles.add(key)
            return "unverified"
        seen = seen | {key}
        tid, num = covered_target(proof)
        if num:
            if tid not in ncrit or not 1 <= num <= ncrit[tid]:
                return "unverified"
            r = one((tid, num), seen)
            return r if r in ("met", "failed", "declined") else "unverified"
        if tid not in ncrit:
            return "unverified"
        sts = [one((i, k), seen) for i in ncrit if i == tid or i.startswith(tid + ".")
               for k in range(1, ncrit[i] + 1)]
        if not sts or "failed" in sts:
            return "failed" if sts else "unverified"
        if all(s == "declined" for s in sts):
            return "declined"
        if all(s in ("met", "declined") for s in sts):
            return "met"
        return "unverified"

    out = {}
    for key, (st, proof) in verdicts.items():
        if st != "covered":
            out[key] = (st, proof)
            continue
        r = one(key, frozenset())
        tid, num = covered_target(proof)
        label = tid + (f".{num}" if num else "")
        reason = proof.split("·", 1)[1].strip() if "·" in proof else ""
        word = {"met": f"сошлось через {label}", "failed": f"НЕ сошлось в {label}",
                "declined": f"снято вместе с {label}"}.get(r, f"ждёт {label}")
        out[key] = (r, word + (f" · {reason}" if reason else ""))
    return out, cycles


def covered_pending(nodes, raw):
    """[(key, target label)] — pointers whose target has not answered yet."""
    resolved, _c = resolve_verdicts(nodes, raw)
    out = []
    for key, (st, proof) in raw.items():
        if st == "covered" and resolved[key][0] == "unverified":
            tid, num = covered_target(proof)
            out.append((key, tid + (f".{num}" if num else "")))
    return sorted(out)


def validation_state(tdir):
    """(nodes, verdicts, open, failed, declined, unverified) — the whole picture."""
    # Nodes first — «работает ли» — then the checklist — «то ли это, чего он ждал».
    nodes = _ledger_nodes(tdir)
    # Pointers followed: a covered criterion reads as what it points at, and a pending one
    # counts as the debt it is. Only the ledger WRITER wants the raw file (validation_parse).
    verdicts, _cycles = resolve_verdicts(nodes, validation_parse(tdir))
    open_n = failed_n = declined_n = unverified_n = 0
    for n in nodes:
        for i in range(1, len(criteria_of(n)) + 1):
            st = verdicts.get((n["id"], i), ("open", ""))[0]
            if st == "open":
                open_n += 1
            elif st == "failed":
                failed_n += 1
            elif st == "declined":
                declined_n += 1
            elif st == "unverified":
                unverified_n += 1
    return nodes, verdicts, open_n, failed_n, declined_n, unverified_n


def validation_split(tdir):
    """Two ledgers that must not blur (feedback 2026-08-26, the MLE task: «44/57 verdicts,
    4/6 nodes и 13 открытых пунктов ИФР читаются как общий успех»): the NODES' own criteria
    — does it work — apart from the acceptance checklist IFR — is it what he asked for.
    {"nodes": c, "owner": c}, c = {total, met, failed, open, unverified, declined}."""
    nodes, verdicts, *_ = validation_state(tdir)
    out = {"nodes": dict(total=0, met=0, failed=0, open=0, unverified=0, declined=0),
           "owner": dict(total=0, met=0, failed=0, open=0, unverified=0, declined=0)}
    for n in nodes:
        c = out["owner"] if n["id"] == "IFR" else out["nodes"]
        for i in range(1, len(criteria_of(n)) + 1):
            st = verdicts.get((n["id"], i), ("open", ""))[0]
            c["total"] += 1
            c[st if st in ("failed", "open", "unverified", "declined") else "met"] += 1
    return out


def check_line(vs, word):
    """The `проверка` line of `el status`: nodes · owner's checklist · owner's word."""
    def part(c):
        if not c["total"]:
            return "критериев нет"
        s = f"{c['met']}/{c['total']} сошлось"
        if c["failed"]:
            s += f" · {c['failed']} НЕ сошлось"
        if c["unverified"]:
            s += f" · {c['unverified']} не проверено"
        if c["open"]:
            s += f" · {c['open']} без вердикта"
        if c["declined"]:
            s += f" · {c['declined']} снято"
        return s
    return (f"узлы (работает ли): {part(vs['nodes'])}  |  приёмка владельца (то ли это): "
            f"чек-лист {part(vs['owner'])} · его слово {'есть' if word else 'нет'}")


# ── Свёртка — один закон на все уровни ────────────────────────────────────────
#
# The owner's design (2026-08-23): validation is a matryoshka, not a flat list. The check
# of any node = its OWN criteria + the ROLL-UP of its children — the same rule on every
# level (stage → work → task). The root of the tree is THE TASK ITSELF: its own criteria
# are the acceptance checklist (the IFR pseudo-node), its children are the stages, and
# above the root stands the owner's word — the one thing never computed.
#
# Nothing here is collected as a separate step: verdicts are recorded while the work runs
# and sealed when the node closes (plan_done refuses to close over open criteria); the
# roll-up is DERIVED, the way a phase is derived from the journal.

VERDICT_RU = {"met": "сошёлся", "failed": "НЕ сошёлся", "declined": "снят",
              "unverified": "не проверен", "open": "без вердикта",
              "covered": "покрыт другим узлом"}
ROLL_MARK = {"failed": "✗", "debt": "?", "open": "▶", "ok": "✓", "empty": "·"}
ROLL_RU = {"failed": "не сошлось", "debt": "не проверено", "open": "открыто",
           "ok": "сошлось", "empty": "нечего проверять"}


def _fold(c):
    """The folded verdict of one counter: the worst news wins."""
    if c["failed"]:
        return "failed"
    if c["unverified"]:
        return "debt"
    if c["open"]:
        return "open"
    return "ok" if c["total"] else "empty"


def rollup(tdir):
    """(order, info) — the whole matryoshka, derived.

    `order` — node ids in tree order, only nodes whose subtree holds at least one
    criterion; IFR last. `info[id]` — name · level · status · depth · parent ·
    items [{text, status, proof}] · own / sub counters {met, failed, declined,
    unverified, open, done, total} · verdict (see _fold). `info["ROOT"]` is the root —
    the task itself: own = the IFR checklist, sub = everything. It is NOT `info["TASK"]`:
    that id belongs to the pseudo-node holding the root's other promises (success · metric ·
    engineering), which the page lists like any node (owner, 2026-08-27: the root used to
    overwrite it, so k1/k2 showed twice and s1…m2 nowhere)."""
    real = sorted(nodes_all(tdir), key=lambda n: n["id"])
    verdicts, _cycles = resolve_verdicts(real + checklist_node(tdir), validation_parse(tdir))
    info, kids = {}, {}
    for n in real + checklist_node(tdir):
        nid = n["id"]
        own = {"met": 0, "failed": 0, "declined": 0, "unverified": 0, "open": 0}
        items = []
        for i, c in enumerate(criteria_of(n), 1):
            st, proof = verdicts.get((nid, i), ("open", ""))
            items.append({"text": c, "status": st, "proof": proof})
            own[st] = own.get(st, 0) + 1
        own["total"] = len(items)
        own["done"] = own["total"] - own["open"]
        parent = nid.rsplit(".", 1)[0] if "." in nid else ""
        info[nid] = {"id": nid, "name": n.get("name", ""), "level": n.get("level", ""),
                     "status": "" if nid == "IFR" else node_status(n),
                     "depth": nid.count("."), "parent": parent,
                     "items": items, "own": own, "sub": dict(own)}
    for nid, rec in info.items():
        if rec["parent"] and rec["parent"] not in info:
            rec["parent"] = ""          # orphan — shown at the top level, not lost
        kids.setdefault(rec["parent"], []).append(nid)
    # Bottom-up: the deepest first, each child pours its subtree into the parent.
    for nid in sorted(info, key=lambda i: -info[i]["depth"]):
        rec = info[nid]
        if rec["parent"]:
            psub = info[rec["parent"]]["sub"]
            for k, v in rec["sub"].items():
                psub[k] += v
    for rec in info.values():
        rec["verdict"] = _fold(rec["sub"])
    # The root — the task itself. Its own criteria are the acceptance checklist.
    task_sub = {"met": 0, "failed": 0, "declined": 0, "unverified": 0, "open": 0,
                "total": 0, "done": 0}
    for nid in kids.get("", []):
        for k, v in info[nid]["sub"].items():
            task_sub[k] += v
    ifr = info.get("IFR") or {"own": {"met": 0, "failed": 0, "declined": 0,
                                      "unverified": 0, "open": 0, "total": 0, "done": 0},
                              "items": []}
    info["ROOT"] = {"id": "ROOT", "name": "задача целиком", "level": "", "status": "",
                    "depth": -1, "parent": None, "items": ifr["items"],
                    "own": ifr["own"], "sub": task_sub, "verdict": _fold(task_sub)}
    order = []

    def walk(nid):
        rec = info[nid]
        if rec["sub"]["total"]:
            order.append(nid)
        for c in sorted(kids.get(nid, [])):
            walk(c)
    for top in sorted(kids.get("", [])):
        if top != "IFR":
            walk(top)
    if "IFR" in info and info["IFR"]["own"]["total"]:
        order.append("IFR")
    return order, info


def cmd_validate(args):
    """The ledger: every criterion of every node, with its verdict and what proves it."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    nodes, verdicts, _, _, _, _ = validation_state(tdir)
    raw = validation_parse(tdir)          # the file as written — pointers kept as pointers
    if not nodes:
        # NEVER AN EMPTY SCREEN (feedback pool, 2026-08-24: «el validate без аргументов
        # вернул пустой экран»). The ledger with nothing in it is still a screen: it says
        # what the ledger is made of, why it is empty, and the next call that fills it.
        print(f"ПРОВЕРКА  {task} · леджер пуст — проверять пока нечего")
        print("          критерии приходят из плана: поле `check` каждого узла (по одному "
              "на строку) и чек-лист приёмки context/acceptance-checklist.md")
        n_all = len(nodes_all(tdir))
        if n_all:
            print(f"          узлов {n_all}, ни у одного нет поля check — задай: "
                  'el plan set <узел> check "- критерий 1\\n- критерий 2 …"')
        else:
            print('          узлов нет — план начинается с них: el plan new s1 "<этап>"')
        print('дальше    заполнил критерии → el validate (леджер) · отметить: '
              'el validate <узел> <N> --met "<чем доказано>"')
        return 0

    words = list(getattr(args, "words", None) or [])
    if words:
        # Addressed the way `el plan` is addressed — `s1 wp1 3` and `s1.wp1 3` name the
        # same node: the path runs up to the first token that is a number. Taking only the
        # first word silently SHOWED S1 when S1.WP1 was meant, and the agent believed the
        # criterion was marked (found by the differential test, 2026-08-21).
        cut = next((i for i, w in enumerate(words) if w.isdigit()), len(words))
        nid = path_to_id(words[:cut] or [words[0]])
        node = next((n for n in nodes if n["id"] == nid), None)
        if not node:
            print(f"нет узла {nid} с критериями", file=sys.stderr)
            return 1
        crits = criteria_of(node)
        if cut >= len(words):
            # One node = its own criteria + the roll-up of its children — the same law
            # as the whole ledger, shown one level deep (owner, 2026-08-23).
            order, info = rollup(tdir)
            rec = info.get(node["id"])
            head = f"{node['id']} · {node.get('name','')}"
            if rec and rec["sub"]["total"] != rec["own"]["total"]:
                head += (f"   свои {rec['own']['done']}/{rec['own']['total']} · "
                         f"с детьми {rec['sub']['done']}/{rec['sub']['total']}")
            print(head)
            for i, c in enumerate(crits, 1):
                st, proof = verdicts.get((node["id"], i), ("open", ""))
                mark = {"met": "✓", "failed": "✗", "declined": "—",
                "unverified": "?"}.get(st, "·")
                if raw.get((node["id"], i), ("", ""))[0] == "covered":
                    mark = "⇢"          # a pointer: the verdict is read from another node
                print(f"  {mark} {i}. {c[:90]}")
                if proof:
                    # a proof that names a file — «… [evidence/x.png]» — is measured
                    marks = path_marks(tdir, proof)
                    tail = "".join(f"  {'✓' if ok else '✗ нет файла:'} {p}" for p, ok in marks
                                   if not ok or len(marks) == 1)
                    print(f"       → {proof[:88]}{tail}")
            kids = [info[i] for i in order
                    if rec and info[i]["parent"] == node["id"]] if rec else []
            if kids:
                print("дети:")
                for k in kids:
                    print(f"  {ROLL_MARK[k['verdict']]} {k['id']:<10} "
                          f"{k['name'][:44]:<46}{k['sub']['done']}/{k['sub']['total']}")
            print(f'\nотметить  el validate {node["id"].lower()} <номер> --met "<чем доказано>"')
            return 0
        num = int(words[cut])
        if not (1 <= num <= len(crits)):
            print(f"у {node['id']} критериев {len(crits)}, а не {num}", file=sys.stderr)
            return 1
        met = getattr(args, "met", None)
        failed = getattr(args, "failed", None)
        # FOUR verdicts, and the last two are not one thing under a vague name. The first cut of
        # this had a single `--skip`, and the owner refused the word outright (2026-08-20:
        # "skip — это как бы пропустить и пойти дальше... skipов не должно быть, всё должно быть
        # осмысленное"). He was right, and the name was hiding TWO different facts:
        #   declined   — the criterion no longer applies: the work behind it was cancelled.
        #                Nothing to check, and no debt. Legitimately closed.
        #   unverified — the work exists, the check does not. The promise still stands and
        #                nobody answered it. That IS a debt, and it must not pass quietly.
        # Collapsing them loses the difference between "снято" and "неизвестно".
        declined = getattr(args, "declined", None)
        unverified = getattr(args, "unverified", None)
        covered = (getattr(args, "covered_by", None) or "").strip()
        if getattr(args, "skip", None):
            print("нет вердикта «skip» — пропуск без смысла запрещён.", file=sys.stderr)
            print('  снят вместе с работой:   --declined "<почему отменили>"', file=sys.stderr)
            print('  работа есть, проверки нет: --unverified "<почему не мерили>"', file=sys.stderr)
            print('  доказательство придёт из другого узла: --covered-by <узел[.N]> --why "…"',
                  file=sys.stderr)
            return 1
        if not met and not failed and not declined and not unverified and not covered:
            print('нужен вердикт: --met "<чем доказано>" · --failed "<что не сошлось>" · '
                  '--declined "<почему снят>" · --unverified "<почему не мерили>" · '
                  '--covered-by <узел[.N]> --why "<почему там>"',
                  file=sys.stderr)
            return 1
        if covered:
            # A POINTER, not a verdict (see resolve_verdicts): the criterion will read as
            # whatever its target reads. Refused when the target is not in the ledger, is
            # the same node, or points back around — a circle of promises proves nothing.
            why = (getattr(args, "why", None) or "").strip()
            if not why:
                print('покрытие называет причину: --covered-by <узел[.N]> --why '
                      '"<почему доказательство живёт там>"', file=sys.stderr)
                return 1
            tid, tnum = covered_target(covered)
            tid = path_to_id([tid])
            target = next((n for n in nodes if n["id"] == tid), None)
            if not target:
                print(f"нет узла {tid} с критериями — покрыть можно только тем, что проверяется: "
                      f"{', '.join(n['id'] for n in nodes)}", file=sys.stderr)
                return 1
            if tid == node["id"]:
                print(f"{tid} не покрывает сам себя — назови другой узел", file=sys.stderr)
                return 1
            if tnum and not 1 <= tnum <= len(criteria_of(target)):
                print(f"у {tid} критериев {len(criteria_of(target))}, а не {tnum}",
                      file=sys.stderr)
                return 1
            label = tid + (f".{tnum}" if tnum else "")
            trial = dict(raw)
            trial[(node["id"], num)] = ("covered", f"{label} · {why}")
            resolved, cycles = resolve_verdicts(nodes, trial)
            if (node["id"], num) in cycles or (tnum and (tid, tnum) in cycles):
                print(f"круг: {node['id']}.{num} → {label} → … → {node['id']}.{num} — "
                      "покрытие по кругу ничего не доказывает; один из них надо мерить",
                      file=sys.stderr)
                return 1
            raw[(node["id"], num)] = ("covered", f"{label} · {why}")
            validation_render(tdir, nodes, raw)
            journal(root, task, "validated",
                    f"{node['id']}.{num} covered: {label} — {why[:100]}")
            touch(root, task)
            r_st, r_proof = resolved[(node["id"], num)]
            print(f"{node['id']}.{num} · покрыт {label} — вердикт читается оттуда: сейчас "
                  f"{VERDICT_RU[r_st]}" + (f" ({r_proof[:60]})" if r_st != "unverified" else ""))
            if r_st == "unverified":
                print(f"          узел {node['id']} закрыть можно — долг проверки уедет на "
                      f"{label} и будет держать выход из проверки, пока {tid} не сойдётся")
            _, _, open_n, failed_n, _d, _u = validation_state(tdir)
            print(f"осталось  {open_n} без вердикта · не сошлось {failed_n}")
            return 0
        kind = ("met" if met else "failed" if failed else
                "declined" if declined else "unverified")
        proof = (met or failed or declined or unverified).strip()
        # THE EVIDENCE LINK (owner, 2026-08-22): a proof written as prose is a claim; a proof
        # that names the file in evidence/ can be opened and re-checked. Stored inside the
        # proof as [path] — the ledger stays a plain file, the page turns it into a link.
        ev = (getattr(args, "evidence", None) or "").strip()
        if ev:
            # The proof must live INSIDE the project — an absolute path to /tmp passed the
            # old check (os.path.join swallows absolute paths) and the ledger pointed at a
            # file that would not survive the night.
            if os.path.isabs(ev) or not os.path.exists(os.path.join(tdir, ev)):
                # The path must live INSIDE the project — and the error must hand over the
                # READY command, not a hint: an agent given only «положи его» went in a
                # circle twice, re-passing the source path (feedback pool, 2026-08-23).
                base = os.path.basename(ev)
                nl, flag = node["id"].lower(), ("--met" if met else "--failed" if failed
                                                else "--declined" if declined else "--unverified")
                if os.path.exists(os.path.join(tdir, "evidence", base)):
                    print(f"файл уже лежит в evidence/ — ссылайся на путь внутри проекта:",
                          file=sys.stderr)
                    print(f'  el validate {nl} {num} {flag} "…" --evidence evidence/{base}',
                          file=sys.stderr)
                elif os.path.exists(ev):
                    print(f"{ev} лежит вне проекта — сначала положи, потом ссылайся на копию:",
                          file=sys.stderr)
                    print(f"  el evidence {ev} --node {nl} --check {num}", file=sys.stderr)
                    print(f'  el validate {nl} {num} {flag} "…" --evidence evidence/{base}',
                          file=sys.stderr)
                else:
                    print(f"нет файла {ev} в проекте — положи его: el evidence <файл> --node "
                          f"{nl} --check {num}, затем --evidence evidence/<имя>", file=sys.stderr)
                return 1
            proof = f"{proof} [{ev}]"
        raw[(node["id"], num)] = (kind, proof)
        validation_render(tdir, nodes, raw)
        if node["id"] not in ("IFR", "TASK") and node_status(node) == "open":
            # a verdict on a node nobody started — the work happened off the board (2026-08-26)
            print(f"узел      {node['id']} не в работе — вердикт записан, но объяви узел до работы: "
                  f"el plan start {node['id'].lower()}")
        journal(root, task, "validated",
                f"{node['id']}.{num} {kind}: "
                f"{(met or failed or declined or unverified).strip()[:120]}")
        touch(root, task)
        print(f"{node['id']}.{num} · " + {"met": "сошлось", "failed": "НЕ сошлось",
              "declined": "снят", "unverified": "не проверено"}[kind])
        if kind == "met" and not ev:
            # A verdict is the agent's ATTESTATION, not the tool's check (feedback 2026-08-26):
            # said out loud when nothing on disk stands behind it.
            print("          свидетельство агента без файла — инструмент ничего не проверял; "
                  "доказательство рядом: --evidence <файл>")
        _, _, open_n, failed_n, _d, _u = validation_state(tdir)
        print(f"осталось  {open_n} без вердикта · не сошлось {failed_n}")
        return 0

    # No arguments: refresh the ledger from the plan and show the whole matryoshka —
    # every line a node with its OWN count and the roll-up of its subtree, the task on top.
    validation_render(tdir, nodes, raw)
    base = baseline_line(tdir)
    print(f"ПРОВЕРКА  {task} · один закон на все уровни: узел = свои критерии + свёртка детей")
    if base:
        print(f"мерка до  {base[:88]}")
    order, info = rollup(tdir)
    for nid in order:
        rec = info[nid]
        pad = "  " * (rec["depth"] + 1)
        own, sub = rec["own"], rec["sub"]
        cnt = (f"свои {own['done']}/{own['total']}" if own["total"] else "своих нет")
        if sub["total"] != own["total"]:
            cnt += f" · всего {sub['done']}/{sub['total']}"
        idw = max(12 - len(pad), len(nid))
        print(f"{pad}{ROLL_MARK[rec['verdict']]} {nid:<{idw}} {rec['name'][:44]:<46}{cnt}" +
              (f"  ✗ {sub['failed']}" if sub["failed"] else ""))
    root_rec = info["ROOT"]
    word = word_given_on(root, task, "validate")
    sub = root_rec["sub"]
    print(f"ЗАДАЧА    {ROLL_MARK[root_rec['verdict']]} {ROLL_RU[root_rec['verdict']]} · "
          f"{sub['done']}/{sub['total']} с вердиктом" +
          (f" · НЕ сошлось {sub['failed']}" if sub["failed"] else "") +
          (f" · снято {sub['declined']}" if sub["declined"] else "") +
          (f" · НЕ проверено {sub['unverified']}" if sub["unverified"] else "") +
          " · слово приёмки: " + ("есть" if word else "НЕТ (el accept --for final)"))
    # Pointers still waiting: the debt that travelled downstream, named by address, so
    # nobody re-marks a criterion that will answer itself when its target comes in.
    pend = covered_pending(nodes, raw)
    if pend:
        print(f"ждут      {len(pend)} покрыты другими узлами — сочтутся, когда сойдётся цель:")
        for (nid_c, i_c), label in pend[:12]:
            print(f"          ⇢ {nid_c}.{i_c} ← {label}")
        if len(pend) > 12:
            print(f"          … ещё {len(pend) - 12}")
    # INTEGRITY: every criterion answered, the node still open — the S6 case of the pilot.
    # The ledger cannot close the node (closing is a decision with a result), but it must
    # say so out loud instead of printing «complete» over an open graph.
    for n in nodes:
        if n["id"] in ("IFR", "TASK"):
            continue
        crits = criteria_of(n)
        allv = all(verdicts.get((n["id"], i), ("open", ""))[0] != "open"
                   for i in range(1, len(crits) + 1))
        if crits and allv and node_open(n):
            print(f"⚠ узел    {n['id']}: критерии закрыты, а узел ещё {STATUS_RU.get(node_status(n), '?')} — "
                  f'закрой: el plan done {n["id"].lower()} "<результат>"')
    print(f"реестр    {os.path.join(tdir, 'checks.jsonl')} — вердикты событиями")
    print('отметить  el validate <узел> <номер> --met "<чем доказано>"')
    return 0
