"""The owner's debt — an answer only he can bring, and does not have yet (owner, 2026-08-24).

Real life, in his words: the agent asks, and the OWNER does not know either — who signs the
document, who the third party is, which of the options he wants. He has to go and find out,
or go away and think. That is neither the agent's borrowed word (autonomy: the agent owes)
nor a node waiting for his word (the baton: he has what is needed and must look). Here the
knowledge is NOT in the project at all, and time passes before it arrives.

Two laws:
  1. It is born on ANY phase — context, research, inside a work package, at a fork — so it
     lives at the level of the task, not of context/questions.md.
  2. It is not a brake by itself. Work goes on around it; it BLOCKS only at the point that
     needs the answer — a node, a fork, a phase gate — and only when tied to it (`--holds`,
     or `el plan block … --owe N` from the plan's side). Until then, «пока не держит» is a
     legal and common state: half of these questions never come due.

Like autonomy, everything here is DERIVED from the journal: an `owe` event (the question,
how he will find out, what it holds), `owe-holds` (tied later to what it blocks),
`owe-paid` (his answer) and `owe-drop` (closed as not needed). owed.md next to the journal
is a projection of that ledger for a person with a notepad — rewritten, never the truth.
"""
import os, sys
from datetime import date
from .protocol import PHASES
from .state import journal, task_meta, touch, write
from .term import human_when, wrap

KINDS = {"выяснить": "факт, которого в проекте нет — у третьих лиц, в документах, в мире",
         "решить": "его собственный выбор, на который нужно время"}
KIND_ALIASES = {"find": "выяснить", "fact": "выяснить", "decide": "решить",
                "решение": "решить", "выяснение": "выяснить"}


def ledger(root, task):
    """Every debt, in order, with its state — from the journal's four event kinds."""
    items, by_n = [], {}
    for e in task_meta(root, task).get("owes") or []:
        kind = e.get("type")
        if kind == "owe":
            it = {"n": e.get("n"), "q": e.get("text") or "", "kind": e.get("kind") or "выяснить",
                  "how": e.get("how") or "", "by": e.get("by") or "", "area": e.get("area") or "",
                  "holds": list(e.get("holds") or []), "ts": e.get("ts") or "",
                  "phase": e.get("phase") or "", "status": "open", "answer": "",
                  "paid_ts": "", "why": ""}
            items.append(it)
            by_n[it["n"]] = it
            continue
        it = by_n.get(e.get("n"))
        if not it:
            continue
        if kind == "owe-holds":
            h = e.get("holds")
            if h and h not in it["holds"]:
                it["holds"].append(h)
        elif kind == "owe-paid":
            it["status"], it["answer"], it["paid_ts"] = "paid", e.get("text") or "", e.get("ts") or ""
        elif kind == "owe-drop":
            it["status"], it["why"], it["paid_ts"] = "dropped", e.get("why") or "", e.get("ts") or ""
    return items


def open_items(root, task):
    return [it for it in ledger(root, task) if it["status"] == "open"]


def holding(root, task, target):
    """The open debts tied to `target` («node:S1.WP2» · «fork:F2» · «phase:plan»)."""
    t = target.strip()
    return [it for it in open_items(root, task) if t in it["holds"]]


def overdue(it, today=None):
    """A due date the page and the CLI can compare: only an ISO date (YYYY-MM-DD…) counts."""
    by = (it.get("by") or "").strip()
    if it.get("status") != "open" or len(by) < 10:
        return False
    try:
        return date.fromisoformat(by[:10]) < (today or date.today())
    except ValueError:
        return False


def norm_hold(text):
    """«node:s1 wp2» → «node:S1.WP2» · «fork:f2» → «fork:F2» · «phase:plan» — or an error string."""
    from .plan import path_to_id
    t = (text or "").strip()
    kind, _, rest = t.partition(":")
    kind, rest = kind.strip().lower(), rest.strip()
    if kind == "node" and rest:
        return "node:" + path_to_id(rest.replace(" ", ".").split(".")), ""
    if kind == "fork" and rest:
        return "fork:" + rest.upper(), ""
    if kind == "phase" and rest.lower() in PHASES:
        return "phase:" + rest.lower(), ""
    return "", (f"держит — одно из: node:<узел> · fork:<развилка> · phase:<{'|'.join(PHASES)}>; "
                f"получил «{t}»")


def hold_label(h):
    kind, _, rest = h.partition(":")
    return {"node": "узел", "fork": "развилка", "phase": "выход из фазы"}.get(kind, kind) + " " + rest


def _stands(root, task, it):
    """Which of the debt's holds is REACHED — the point of need is here, work stands."""
    tdir = os.path.join(root, task)
    ph = task_meta(root, task).get("phase", "context")
    out = []
    for h in it["holds"]:
        kind, _, rest = h.partition(":")
        if kind == "phase" and rest == ph:
            out.append(h)
        elif kind == "node":
            try:
                from .plan import node_read, node_status
                n = node_read(tdir, rest)
                if n and node_status(n) == "blocked":
                    out.append(h)
            except Exception:
                pass
        elif kind == "fork" and ph == "think":
            out.append(h)
    return out


def lines(root, task, full=False):
    """What `el status` and `el next` print about the owner's debt. [] when there is none."""
    items = open_items(root, task)
    if not items:
        return []
    stand = [it for it in items if _stands(root, task, it)]
    held = [it for it in items if it["holds"]]
    out = [f"ЗА ВЛАДЕЛЬЦЕМ  {len(items)} — ответ есть только у него, и его пока нет"
           + (f" · стоим из-за: {len(stand)}" if stand else "")
           + (f" · привязано к точке: {len(held)}" if held and not stand else "")]
    for it in items:
        st = _stands(root, task, it)
        where = (" · СТОИМ: " + ", ".join(hold_label(h) for h in st)) if st else \
                (" · держит: " + ", ".join(hold_label(h) for h in it["holds"])) if it["holds"] else \
                " · пока не держит"
        due = (f" · срок {it['by']}" + (" — ПРОСРОЧЕН" if overdue(it) else "")) if it["by"] else ""
        out.append(f"  #{it['n']} {it['kind']} · {it['q']}")
        out.append("      " + wrap(f"как: {it['how'] or '?'} · ждёт с {human_when(it['ts'])}"
                                    f"{due}{where}", indent="      "))
    if full:
        out.append('      ответ: el owe answer <n> "<его ответ>" · не понадобилось: el owe drop <n> '
                   '--why "…" · привязать: el owe <n> --holds node:<узел>|fork:<id>|phase:<фаза>')
    return out


def _lift(root, task, it):
    """The answer came — what the debt held is let go. A node blocked by this debt goes
    back to open (the block was this debt and nothing else); a fork or a phase is simply
    no longer held — the gate passes on its own. Prints what to reread."""
    tdir = os.path.join(root, task)
    other_open = [o for o in open_items(root, task) if o["n"] != it["n"]]
    for h in it["holds"]:
        kind, _, rest = h.partition(":")
        if kind == "node":
            still = [o["n"] for o in other_open if h in o["holds"]]
            if still:
                print(f"узел      {rest} держит ещё долг #{', #'.join(map(str, still))} — остаётся")
                continue
            try:
                from .plan import _set_status, node_read, node_status
                n = node_read(tdir, rest)
                if n and node_status(n) == "blocked":
                    _set_status(root, task, tdir, n, "open", {"block_note": None}, "node-unblock",
                                f"ответ владельца по долгу #{it['n']} получен")
                    print(f"узел      {rest} отпущен (был заблокирован этим долгом) — перечитай "
                          f"его контракт с ответом в руках: el plan {rest.lower()} · "
                          f"в работу: el plan start {rest.lower()}")
            except Exception:
                pass
        elif kind == "fork":
            print(f"развилка  {rest} — ответ есть, реши её его словами: "
                  f'el think decide {rest.lower()} "<вариант>" --words "<его слова>"')
        elif kind == "phase":
            print(f"ворота    выход из {rest} больше не держится этим долгом")


def cmd_owe(args):
    root_task = _root_task(args)
    if not root_task:
        return 1
    root, task = root_task
    words = list(getattr(args, "words", None) or [])
    verb = words[0].lower() if words else ""
    if verb in ("answer", "paid", "ответ"):
        return _answer(root, task, words[1:])
    if verb in ("drop", "снять"):
        return _drop(root, task, words[1:], getattr(args, "why", None))
    if verb.lstrip("#").isdigit():
        return _tie(root, task, int(verb.lstrip("#")), getattr(args, "holds", None))
    if not words or verb in ("list", "ls"):
        return _list(root, task)
    return _record(root, task, " ".join(words), args)


def _root_task(args):
    from .state import pick_task, require_root
    root = require_root()
    if not root:
        return None
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return None
    return root, task


def _list(root, task):
    items = ledger(root, task)
    if not items:
        print("за владельцем ничего — ни одного вопроса, ответ на который есть только у него.")
        print('запись    el owe "<вопрос>" --how "<у кого / где выяснит>" [--kind выяснить|решить] '
              "[--by <срок>] [--area <область>] [--holds node:<узел>|fork:<id>|phase:<фаза>]")
        return 0
    for l in lines(root, task, full=True):
        print(l)
    closed = [it for it in items if it["status"] != "open"]
    if closed:
        print(f"закрыто   {len(closed)}")
        for it in closed:
            tail = f"ответ: {it['answer']}" if it["status"] == "paid" else f"снято: {it['why']}"
            print(f"  #{it['n']} {'✓' if it['status'] == 'paid' else '⏹'} {it['q'][:70]} — {tail[:90]}")
    return 0


def _record(root, task, q, args):
    q = (q or "").strip()
    how = (getattr(args, "how", None) or "").strip()
    if not q:
        print('el owe "<вопрос>" --how "<у кого / где выяснит>"', file=sys.stderr)
        return 1
    if not how:
        print("скажи --how — КАК он это выяснит или решит (у кого спросит, где посмотрит, «подумать "
              "до пятницы»): долг без пути к ответу неотличим от пожелания.", file=sys.stderr)
        print(f'hint     el owe "{q[:50]}" --how "<у кого / где>"', file=sys.stderr)
        return 1
    kind = (getattr(args, "kind", None) or "выяснить").strip().lower()
    kind = KIND_ALIASES.get(kind, kind)
    if kind not in KINDS:
        print(f"--kind: одно из {', '.join(KINDS)}", file=sys.stderr)
        for k, d in KINDS.items():
            print(f"  {k:<9} {d}", file=sys.stderr)
        return 1
    area = (getattr(args, "area", None) or "").strip().lower()
    if area:
        from .protocol import AREA_KEYS
        if area not in AREA_KEYS:
            print(f"--area: одна из {', '.join(AREA_KEYS)}", file=sys.stderr)
            return 1
    holds = []
    for h in getattr(args, "holds", None) or []:
        norm, err = norm_hold(h)
        if err:
            print(err, file=sys.stderr)
            return 1
        holds.append(norm)
    meta = task_meta(root, task)
    n = sum(1 for e in meta.get("owes") or [] if e.get("type") == "owe") + 1
    extra = {"n": n, "kind": kind, "how": how, "phase": meta.get("phase", "context")}
    if getattr(args, "by", None):
        extra["by"] = args.by.strip()
    if area:
        extra["area"] = area
    if holds:
        extra["holds"] = holds
    journal(root, task, "owe", q[:200], extra)
    touch(root, task)
    print(f"за владельцем  #{n} {kind} · {q}")
    print(f"           как: {how}" + (f" · срок: {extra['by']}" if extra.get("by") else ""))
    if holds:
        print("           держит: " + ", ".join(hold_label(h) for h in holds))
    else:
        print("           пока не держит ничего — работа идёт; привяжи, когда дойдём до точки, где без")
        print(f"           ответа нельзя: el owe {n} --holds node:<узел> · или el plan block <узел> --owe {n}")
    print(f'ответ      el owe answer {n} "<его ответ>" — когда принесёт')
    return 0


def _find(root, task, words):
    if not words or not words[0].lstrip("#").isdigit():
        return None, 'el owe answer <n> "<ответ>"'
    n = int(words[0].lstrip("#"))
    it = next((x for x in ledger(root, task) if x["n"] == n), None)
    if not it:
        return None, f"нет долга #{n} — список: el owe"
    return it, ""


def _answer(root, task, words):
    it, err = _find(root, task, words)
    if err:
        print(err, file=sys.stderr)
        return 1
    ans = " ".join(words[1:]).strip()
    if not ans:
        print(f'ответ нужен словами: el owe answer {it["n"]} "<что он выяснил / решил>"', file=sys.stderr)
        return 1
    if it["status"] != "open":
        print(f"#{it['n']} уже закрыт ({it['status']})", file=sys.stderr)
        return 1
    journal(root, task, "owe-paid", ans[:300], {"n": it["n"]})
    touch(root, task)
    print(f"оплачено  #{it['n']} · {it['q'][:60]}")
    print(f"ответ     {ans}")
    _lift(root, task, it)
    if it["area"]:
        print(f'контекст  ответ по области {it["area"]} — запиши парой, чтобы он лёг в картину: '
              f'el context qa "{it["q"][:40]}…" "<ответ>" --area {it["area"]}')
    print("картина   если ответ её сдвинул — поправка документа и его слово заново (как всегда)")
    return 0


def _drop(root, task, words, why):
    it, err = _find(root, task, words)
    if err:
        print(err, file=sys.stderr)
        return 1
    why = (why or "").strip()
    if not why:
        print(f'снять без причины нельзя: el owe drop {it["n"]} --why "<почему не понадобилось>"',
              file=sys.stderr)
        return 1
    if it["status"] != "open":
        print(f"#{it['n']} уже закрыт ({it['status']})", file=sys.stderr)
        return 1
    journal(root, task, "owe-drop", it["q"][:120], {"n": it["n"], "why": why})
    touch(root, task)
    print(f"снято     #{it['n']} · {it['q'][:60]} — {why}")
    _lift(root, task, it)
    return 0


def _tie(root, task, n, holds):
    it = next((x for x in ledger(root, task) if x["n"] == n), None)
    if not it:
        print(f"нет долга #{n} — список: el owe", file=sys.stderr)
        return 1
    if not holds:
        print(f"#{it['n']} {it['kind']} · {it['q']}")
        print(f"   как: {it['how']} · {it['status']}"
              + (" · держит: " + ", ".join(hold_label(h) for h in it["holds"]) if it["holds"] else ""))
        print(f"   привязать: el owe {n} --holds node:<узел>|fork:<id>|phase:<фаза>")
        return 0
    if it["status"] != "open":
        print(f"#{n} уже закрыт ({it['status']}) — держать ничего не может", file=sys.stderr)
        return 1
    for h in holds:
        norm, err = norm_hold(h)
        if err:
            print(err, file=sys.stderr)
            return 1
        if norm in it["holds"]:
            print(f"#{n} уже держит {hold_label(norm)}")
            continue
        journal(root, task, "owe-holds", f"#{n} держит {norm}", {"n": n, "holds": norm})
        print(f"держит    #{n} → {hold_label(norm)}")
        if norm.startswith("node:"):
            print(f"          узел встанет, когда дойдём: el plan block {norm[5:].lower()} --owe {n}")
    touch(root, task)
    return 0
