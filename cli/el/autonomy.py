"""Autonomy — GRANTS and the agent's DECISIONS under them (owner, 2026-08-22; remodelled
by his words 2026-08-26).

A grant is a PERIOD, like a research grant: it starts with his words (and conditions —
until · no · hours · a name), and it ends in one of five ways — завершён (the condition or
the term reached: `el grant end`), hold (the emergency exit — the agent cannot go on
without him: `el halt`), снят владельцем (his «стоп»: `el halt --by user`), заменён (a new
grant issued over a standing one), задача закрыта. A grant that started and did not end is
ACTIVE. His correction of a standing grant's conditions («давай четыре часа, не два») is a
CHANGE inside the same grant, not a new one; his «продолжай» after an end IS a new grant.

Under a grant sit the agent's DECISIONS — the `assume` events: what it decided in his
place, why. No debt and no rollback (owner, 2026-08-26: «решение уже сделано, на его
основе действовали — тут уже ничего не вернёшь»): a decision is history, the truth is the
current state; a decision made after his last word in the task is marked NEW, so a
returning owner sees what he has not read yet. Everything here is derived from the journal.
"""
import json, os, sys
from datetime import datetime
from .state import journal_path, task_meta
from .term import human_when
from .worklog import NOT_WORK

END_RU = {"done": "завершён", "hold": "hold", "owner": "снят владельцем",
          "replaced": "заменён новым", "closed": "задача закрыта"}


def _dt(iso):
    try:
        return datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def span_text(seconds):
    """«1 ч 50 мин» · «35 мин» · «2 дн 3 ч» — a length of time for a person."""
    s = int(max(seconds or 0, 0))
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d} дн {h} ч"
    if h:
        return f"{h} ч {m} мин" if m else f"{h} ч"
    return f"{m} мин"


def hours_text(hours):
    if hours is None:
        return ""
    return f"{int(hours)} ч" if float(hours).is_integer() else f"{hours:g} ч"


def grant_name(g):
    return (g.get("name") or " ".join((g.get("text") or "").split()[:5]) or "грант").strip()


def _events(root, task):
    out = []
    try:
        with open(journal_path(root, task), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def grants(root, task):
    """Every grant, oldest first — each with: name · changes · end · decisions (with `new`) ·
    work (what happened under it) · elapsed seconds · hours · overrun · active."""
    meta = task_meta(root, task)
    gl = [dict(g, changes=list(g.get("changes") or [])) for g in meta.get("grants") or []]
    if not gl:
        return []
    # His LAST WORD in the task: a real accept, a grant, a change of one, his own stop.
    owner_ts = [w.get("ts", "") for w in meta.get("words") or []]
    for g in gl:
        owner_ts.append(g.get("ts", ""))
        owner_ts += [c.get("ts", "") for c in g["changes"]]
        if (g.get("end") or {}).get("kind") == "owner":
            owner_ts.append(g["end"].get("ts", ""))
    last_owner = max(owner_ts) if owner_ts else ""
    assumes = meta.get("assumes") or []
    events = _events(root, task)
    open_task = meta.get("status", "active") == "active"
    for g in gl:
        start = g.get("ts", "")
        end_ts = (g.get("end") or {}).get("ts")

        def inside(ts, start=start, end_ts=end_ts):
            return ts >= start and (end_ts is None or ts <= end_ts)
        g["decisions"] = [dict(a, new=(a.get("ts", "") > last_owner))
                          for a in assumes if inside(a.get("ts", ""))]
        g["new"] = sum(1 for d in g["decisions"] if d["new"])
        work = {"nodes": 0, "verdicts": 0, "phases": 0, "logs": 0}
        for e in events:
            if not inside(e.get("ts", "")):
                continue
            t = e.get("type") or ""
            if t == "node-done":
                work["nodes"] += 1
            elif t == "validated":
                work["verdicts"] += 1
            elif t == "advance":
                work["phases"] += 1
            elif t not in NOT_WORK and not t.startswith("node-") and not e.get("free"):
                work["logs"] += 1      # the same rule that puts a line on a node's work log
        g["work"] = work
        g["name"] = grant_name(g)
        st_dt = _dt(start)
        en_dt = _dt(end_ts) if end_ts else (datetime.now(st_dt.tzinfo) if st_dt else None)
        g["elapsed"] = (en_dt - st_dt).total_seconds() if st_dt and en_dt else 0
        try:
            g["hours"] = float(g["hours"]) if g.get("hours") not in (None, "") else None
        except (TypeError, ValueError):
            g["hours"] = None
        g["active"] = g.get("end") is None and open_task
        g["overrun"] = bool(g["hours"] and g["active"] and g["elapsed"] > g["hours"] * 3600)
    return gl


def state(root, task):
    """None when no grant was ever given; else: grant (the last) · grants · active · end ·
    decisions (all) · new (unread by him)."""
    gl = grants(root, task)
    if not gl:
        return None
    last = gl[-1]
    return {"grant": last, "grants": gl, "active": last["active"], "end": last.get("end"),
            "halt": task_meta(root, task).get("halt"),
            "decisions": [d for g in gl for d in g["decisions"]],
            "new": sum(g["new"] for g in gl)}


def work_text(w):
    parts = []
    if w["nodes"]:
        parts.append(f"узлов закрыто {w['nodes']}")
    if w["verdicts"]:
        parts.append(f"вердиктов {w['verdicts']}")
    if w["phases"]:
        parts.append(f"фаз пройдено {w['phases']}")
    if w["logs"]:
        parts.append(f"записей хода {w['logs']}")
    return " · ".join(parts) if parts else "следов под грантом нет"


def brief_stale(root, task):
    """The sheet written BEFORE the standing grant — its «wait for the owner» is void, and a
    returning agent must not obey it (feedback 2025-08-25, Copilot: after `el grant` the
    onboarding still printed brief.md with the old owner-gated guidance). (grant_ts,
    brief_ts) when stale, else None."""
    from .state import brief_path
    st = state(root, task)
    if not st or not st["active"]:
        return None
    p = brief_path(os.path.join(root, task))
    try:
        b_ts = os.path.getmtime(p)
        g_ts = datetime.fromisoformat(st["grant"].get("ts", "")).timestamp()
    except (OSError, ValueError):
        return None
    return (st["grant"].get("ts", ""), b_ts) if b_ts < g_ts else None


def brief_stale_line(root, task, indent="          "):
    """One line to print right under the sheet — or ''."""
    s = brief_stale(root, task)
    if not s:
        return ""
    b_when = human_when(datetime.fromtimestamp(s[1]).astimezone().isoformat(timespec="minutes"))
    return (f"{indent}⚠ листок старше гранта ({b_when} < грант {human_when(s[0])}): его «жди владельца» "
            f"грант отменяет — верь автономии; перепиши: el brief \"…\"")


def on(root, task):
    """Autonomy is ON: a grant stands — started, not ended, the task open."""
    st = state(root, task)
    return bool(st and st["active"])


def guard(root, task, what="решение в его место"):
    """Refuse a decision in his place when no grant covers it — printed, returns False."""
    st = state(root, task)
    if not st:
        print(f"{what} без гранта невозможно — человек не давал автономии.", file=sys.stderr)
        print('hint     спроси его · либо, если он сказал «работай сам», запиши это: '
              'el grant "<его слова дословно>"', file=sys.stderr)
        return False
    if not st["active"]:
        e = st["end"] or {}
        kind = e.get("kind", "")
        how = {"hold": "автономия на hold", "owner": "автономия снята владельцем",
               "done": "грант завершён", "closed": "задача закрыта"}.get(kind, "гранта нет")
        print(f"{what} невозможно — {how}: {(e.get('text') or '').strip()}", file=sys.stderr)
        print('hint     новый грант — только его слово: el grant "<его слова: продолжай>"', file=sys.stderr)
        return False
    return True


def _cond_line(g):
    parts = []
    if g.get("until"):
        parts.append(f"до: {g['until']}")
    if g.get("no"):
        parts.append(f"нельзя: {g['no']}")
    return " · ".join(parts)


def lines(root, task, full=False):
    """What `el` · `el status` · `el next` · `el resume` print about autonomy. [] when none."""
    st = state(root, task)
    if not st:
        return []
    g, out = st["grant"], []
    total = len(st["decisions"])
    if g["active"]:
        head = f"автономия грант «{g['name']}» · с {human_when(g.get('ts'))}"
        head += (f" · прошло {span_text(g['elapsed'])} из {hours_text(g['hours'])}" if g["hours"]
                 else f" · идёт {span_text(g['elapsed'])}")
        out.append(head)
        # His words WHOLE: the conditions of a grant stand at the END of a long sentence
        # («…пока не срежешь 2 ГБ»), and a cut quote is a different grant (owner, 2026-08-23).
        out.append(f"          «{(g.get('text') or '').strip()}»")
        if _cond_line(g):
            out.append(f"          {_cond_line(g)}")
        if g["changes"]:
            c = g["changes"][-1]
            out.append(f"          изменён владельцем {human_when(c.get('ts'))}: «{(c.get('text') or '').strip()}»"
                       + (f" — {c['what']}" if c.get("what") else ""))
        out.append(f"          решений агента {len(g['decisions'])}" +
                   (f" · новых {g['new']}" if g["new"] else "") + " · el review")
        if g["overrun"]:
            out.append('          СРОК ВЫШЕЛ — заверши грант: el grant end "<чем доказано>" · '
                       'или остановись: el halt "<почему · что нужно>"')
        if full:
            out.append('          в его место: el accept … --assumed "<почему>" · дошёл: el grant end "<чем '
                       'доказано>" · дальше без него нельзя: el halt "<почему · что нужно>"')
        return out
    e = g.get("end") or {}
    kind, when, text = e.get("kind", ""), human_when(e.get("ts")), (e.get("text") or "").strip()
    if kind == "hold":
        out.append(f"АВТОНОМИЯ ОСТАНОВЛЕНА ЗДЕСЬ (hold)  {when}")
        out.append(f"          «{text}»")
        out.append(f"          грант «{g['name']}» дальше не действует; продолжить — его слово: "
                   'el grant "<его слова>" · решения под ним: el review')
    elif kind == "owner":
        out.append(f"АВТОНОМИЯ СНЯТА ВЛАДЕЛЬЦЕМ  {when}")
        out.append(f"          «{text}»")
        out.append('          новый грант — его словом: el grant "<его слова>"')
    elif kind == "done":
        out.append(f"автономия завершена {when} — грант «{g['name']}» дошёл: «{text}»")
        out.append('          нового гранта нет: на остановках ждём его слово · продолжить сам он может: el grant')
    elif kind == "closed":
        out.append(f"автономия кончилась с задачей {when} — грант «{g['name']}»")
    if total:
        out.append(f"          решений агента под грантами {total} — el review")
    return out


def review_lines(root, task):
    """`el review` — the grants, newest first, each with the agent's decisions under it."""
    gl = grants(root, task)
    if not gl:
        return ["автономии у задачи не было — грантов нет"]
    out = []
    for i, g in reversed(list(enumerate(gl, 1))):
        e = g.get("end") or {}
        status = "АКТИВЕН" if g["active"] else END_RU.get(e.get("kind"), "?").upper()
        right = (f"{human_when(e.get('ts'))} · {span_text(g['elapsed'])}" if e else
                 (f"срок {hours_text(g['hours'])} · прошло {span_text(g['elapsed'])}" if g["hours"]
                  else f"идёт {span_text(g['elapsed'])}"))
        out.append(f"ГРАНТ #{i}  «{g['name']}» · {status} · {human_when(g.get('ts'))} → {right}")
        out.append(f"          «{(g.get('text') or '').strip()}»")
        if _cond_line(g):
            out.append(f"          {_cond_line(g)}")
        for c in g["changes"]:
            out.append(f"          изменён владельцем {human_when(c.get('ts'))}: «{(c.get('text') or '').strip()}»"
                       + (f" — {c['what']}" if c.get("what") else ""))
        if e:
            out.append(f"          {END_RU.get(e.get('kind'), '?')} — «{(e.get('text') or '').strip()}»")
        if g["overrun"]:
            out.append("          СРОК ВЫШЕЛ — заверши: el grant end \"<чем доказано>\"")
        if g["decisions"]:
            out.append(f"  решения агента {len(g['decisions'])}" + (f" · новых {g['new']}" if g["new"] else "")
                       + ("" if g["active"] else " — история: грант закончился, правда — текущее состояние"))
            for d in g["decisions"]:
                out.append(f"    {human_when(d.get('ts')):<14} {d.get('for') or '?':<16} "
                           f"{(d.get('text') or '').strip()}" + ("   ← новое" if d["new"] else ""))
                if d.get("why"):
                    out.append(f"        почему так принял: {d['why']}")
        else:
            out.append("  решений агента под грантом нет")
        out.append(f"  работа под грантом: {work_text(g['work'])}")
        out.append("")
    if out and out[-1] == "":
        out.pop()
    return out
