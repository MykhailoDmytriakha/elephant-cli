"""THE WORK LOG — what was done on each node, in the order it was done.

Owner, 2026-08-25: «мы работаем над S1, внутри WP1, делаем какую-то работу — и чтобы она
туда записывалась: на странице видно, что по этой работе сделано, и агент видит; а так лог
ни к чему не привязан». Two sources, one reading:
  · `el log` written while a node is in work carries {"node": …} from now on (or `--node`);
  · older journals get the same BY TIME — a note written between a node's start and its
    pause / wait / done belongs to that node. Nothing is rewritten; the reading is derived.

And the discipline the log makes possible (owner: «а что, если он начал делать, пошёл дальше,
а work package так и не закрыл?»): a node in work that has seen no trace for a day while
other things WERE written is named «брошен?» by `el`, `el status`, `el next` and the page —
with the four honest ways out: done · wait · park · start <другой> --switch.
"""
import json, os, re
from datetime import datetime, timezone
from .state import RESERVED_EVENTS, journal_path

# node events write «S1.WP1: …» — the id is read from the text, the status rides in `status`
NODE_ID = re.compile(r"^([A-Z][A-Z0-9]*(?:\.[A-Z][A-Z0-9]*)*):")
ON = ("node-start", "node-resume")
OFF = ("node-pause", "node-done", "node-wait", "node-blocked", "node-parked", "node-removed")
# journal lines that are bookkeeping, not work — never attributed to a node by time
NOT_WORK = set(RESERVED_EVENTS) | {"request", "todo", "todo-done", "lesson", "amend", "brief",
                                   "research", "feedback", "accepted", "node", "mode", "spawn"}
STALE_HOURS = 24


def events(root, task):
    out = []
    try:
        with open(journal_path(root, task), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def worklog(root, task):
    """{node id: [{ts, type, text, by_time, files}]} — explicit `node` first; else the node in
    work at that moment (by_time=True). Node bookkeeping events themselves are not entries."""
    active, out = None, {}
    for rec in events(root, task):
        t = rec.get("type") or ""
        if t in ON or t in OFF:
            m = NODE_ID.match(rec.get("text") or "")
            nid = m.group(1) if m else None
            if t in ON:
                active = nid
            elif nid is None or active == nid:
                active = None
            continue
        if t in NOT_WORK or t.startswith("node-") or rec.get("free"):
            continue
        nid, by_time = rec.get("node"), False
        if not nid and active:
            nid, by_time = active, True
        if not nid:
            continue
        out.setdefault(str(nid).upper(), []).append(
            {"ts": rec.get("ts", ""), "type": t, "text": rec.get("text") or "",
             "by_time": by_time, "files": rec.get("files") or []})
    return out


def stale(root, task, tdir, hours=STALE_HOURS):
    """The node in work that looks abandoned: no trace on it for `hours`, while the journal
    kept moving elsewhere. None when there is nothing to say. Silence everywhere is a pause,
    not abandonment — the return beat covers that."""
    from .plan import active_node, node_status
    act = active_node(tdir)
    if not act or node_status(act) != "active":
        return None
    wl = worklog(root, task).get(act["id"], [])
    last = wl[-1]["ts"] if wl else (act.get("started_at") or "")
    if not last:
        return None
    try:
        age_h = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
    except ValueError:
        return None
    if age_h < hours:
        return None
    stray = sum(1 for e in events(root, task)
                if (e.get("ts") or "") > last and e.get("type") not in ("hold",))
    if not stray:
        return None
    return {"id": act["id"], "name": act.get("name", ""), "hours": int(age_h), "stray": stray,
            "traces": len(wl), "started_at": act.get("started_at", "")}


def span(hours):
    return f"{hours // 24} дн." if hours >= 48 else f"{hours} ч"


def stale_lines(root, task, tdir):
    """The «брошен?» warning as `el status` / `el next` / `el` print it; [] when clean."""
    s = stale(root, task, tdir)
    if not s:
        return []
    low = s["id"].lower()
    return [f"⚠ брошен? {s['id']} в работе, последний след {span(s['hours'])} назад · с тех пор "
            f"{s['stray']} запис(ей) мимо узла" + ("" if s["traces"] else " · следов по узлу нет вовсе"),
            f"          закрой: el plan done {low} \"<результат>\" · ждать владельца: el plan wait {low} \"…\"",
            f"          отложить: el plan park {low} --why \"…\" · сменить: el plan start <узел> "
            f"--switch \"<почему>\""]


def last_line(root, task, nid, width=70):
    """«ход работы 7 · последняя сегодня 14:03: …» for one node — or the nudge to write."""
    from .term import human_when
    wl = worklog(root, task).get(nid, [])
    if not wl:
        return f"ход работы пусто — el log \"<что сделал>\" по ходу ложится к {nid}"
    e = wl[-1]
    return f"ход работы {len(wl)} · последняя {human_when(e['ts'])}: {e['text'][:width]}"
