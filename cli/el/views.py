"""The human's pages — projections, never the base.

The pages themselves (index.html · overview.html) are copies of the skill's templates,
kept equal to them; the DATA they show is written into <storage>/metadata/ as one JS
file for the index and one per project. Rebuilt once per command, only for the projects
the command touched (state._DIRTY). A broken view must never break the bookkeeping.
"""
import json, os
from .protocol import CONTEXT_FILES, IFR_PARTS, NODE_FIELDS, SCOPE_FRAME, THINK_STEPS, feedback_prompt, required_in
from .state import _DIRTY, SKILL_ROOT, current_task, now_iso, task_meta, task_mode, tasks_of, todo_items, write
from .context import qa_read, scope_notes, scope_read
from .think import forks_read
from .amend import pending_word, split_amendments, word_given_on
from .plan import active_node, node_status, node_sync, nodes_all, sync_mark, waiting_nodes
from .validate import criteria_of, rollup, validation_state
from . import autonomy, owe
from .worklog import stale, worklog


def skill_html(name):
    """A page template from the skill's html/ folder (SKILL_ROOT is computed in
    state.py from the package's own location)."""
    return os.path.join(SKILL_ROOT, "html", name)


def sync_page(name, dest):
    """Keep a page copy equal to the skill's template. The page is a pure projection —
    CODE from the template plus DATA from metadata/ — so when the template evolves, every
    existing copy is brought up to date and an old project can never show an old page
    (owner, 2026-08-21: "CLI обновился, а у меня в проекте старая HTML"). Data is still
    never written into the page itself."""
    try:
        tpl = open(skill_html(name), encoding="utf-8").read()
    except OSError:
        return
    try:
        cur = open(dest, encoding="utf-8").read()
    except OSError:
        cur = None
    if cur != tpl:
        write(dest, tpl)


FILE_KINDS = {
    "audio": ("mp3", "m4a", "wav", "aac", "ogg", "flac", "opus"),
    "image": ("png", "jpg", "jpeg", "gif", "webp", "heic", "svg"),
    "video": ("mp4", "mov", "webm", "m4v"),
    "pdf":   ("pdf",),
}


def file_kind(name):
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    for kind, exts in FILE_KINDS.items():
        if ext in exts:
            return kind
    return "file"


def project_files(tdir):
    """Inventory of the project's folders for the page: name, relative path, size, kind.
    Relative paths matter — the page links straight to them, and media tags (audio,
    images) work from disk even though programmatic reads do not."""
    out = {}
    for sub in ("init", "context", "research", "thinking", "nodes", "evidence",
                "artifacts", "notes"):
        d = os.path.join(tdir, sub)
        if not os.path.isdir(d):
            continue
        items = []
        for base, dirs, files in os.walk(d):
            dirs[:] = sorted(x for x in dirs if not x.startswith("."))
            for f in sorted(files):
                if f.startswith("."):
                    continue
                p = os.path.join(base, f)
                try:
                    size = os.stat(p).st_size
                except OSError:
                    continue
                items.append({"name": f,
                              "path": os.path.relpath(p, tdir).replace(os.sep, "/"),
                              "size": size, "kind": file_kind(f)})
        if items:
            out[sub] = items
    return out


def page_key(rel):
    """Where on overview.html the document `rel` is drawn — the data-key of its foldable
    section, so the amendments list can jump to the card. None when the page has no place
    for it (the link is then omitted, the line still shows)."""
    by_rel = {v: k for k, v in CONTEXT_FILES.items()}
    k = by_rel.get(rel)
    if k in SCOPE_FRAME:
        return "ctx.frame." + k
    if k in IFR_PARTS:
        return "ifr.ideal" if k == "ifr" else "ifr." + k
    fixed = {"scope": "ctx.scope.5w", "clarified": "ctx.clarified", "summary": "ctx.summary",
             "unknown": "ctx.unknown", "questions": "ctx.qa"}
    if k in fixed:
        return fixed[k]
    if rel.startswith("thinking/"):
        return "think." + rel.split("/")[-1].rsplit(".", 1)[0]
    if rel == "plan.md":
        return "plan.md"
    if rel.startswith("nodes/"):
        return "plan.tree"
    return None


def amend_list(root, task, entries):
    """The amendments as ONE list for the page (owner, 2026-08-23: the badge counted them, the
    cards sat each under its own document — nowhere to see «what changed since I confirmed»).
    Source — the journal's `amend` events, in time order; `pending` mirrors amend.pending_word
    (an amendment later than his last recorded word), so the page and `el next` agree on what
    still waits for his confirmation."""
    pend = {(e.get("ts"), e.get("text")) for e in pending_word(root, task)}
    # WHO covered each amendment — his real word (`accepted`) or a borrowed one (`assume`,
    # autonomy): `el next` treats both as a word (the debt is tracked elsewhere), but the
    # human must see the difference — «подтверждено тобой» is not «принято за тебя».
    cover, open_items, out = {}, [], []
    for e in entries:
        if e.get("type") in ("accepted", "assume"):
            for it in open_items:
                cover[it] = e.get("type")
            open_items = []
        elif e.get("type") == "amend":
            open_items.append((e.get("ts"), e.get("text")))
    for e in entries:
        if e.get("type") != "amend":
            continue
        text = e.get("text") or ""
        if e.get("part") == "scope":
            rel = CONTEXT_FILES["scope"]
        elif e.get("late"):
            rel = text.split(" поздний след:", 1)[0].strip()
        else:
            rel = text.split(" п", 1)[0].strip()
        out.append({"ts": e.get("ts", ""), "phase": e.get("phase", ""), "rel": rel,
                    "part": e.get("part", ""), "n": e.get("n"), "dim": e.get("dim"),
                    "late": bool(e.get("late")), "why": e.get("why") or "",
                    "refs": [r for r in (e.get("refs") or []) if r],
                    "text": text.split(": ", 1)[-1] if ": " in text else text,
                    "key": page_key(rel),
                    "pending": (e.get("ts"), text) in pend,
                    "covered_by": cover.get((e.get("ts"), text))})
    return out


def autonomy_view(root, task):
    """Autonomy as the pages show it — the SAME state the CLI prints (autonomy.state), so the
    page and `el status` can never disagree. Grants as periods, oldest first, each with its
    changes, end, decisions (with `new`), work and term (owner, 2026-08-26). None when no
    grant was ever given."""
    st = autonomy.state(root, task)
    if not st:
        return None
    gl = []
    for g in st["grants"]:
        gl.append({"ts": g.get("ts", ""), "name": g["name"], "text": g.get("text", ""),
                   "until": g.get("until"), "no": g.get("no"), "hours": g["hours"],
                   "changes": [{"ts": c.get("ts", ""), "text": c.get("text", ""), "what": c.get("what", "")}
                               for c in g["changes"]],
                   "end": g.get("end"), "active": g["active"], "overrun": g["overrun"],
                   "elapsed": int(g["elapsed"]), "elapsed_text": autonomy.span_text(g["elapsed"]),
                   "decisions": [{"ts": d.get("ts", ""), "for": d.get("for", ""), "text": d.get("text", ""),
                                  "why": d.get("why", ""), "new": d["new"]} for d in g["decisions"]],
                   "new": g["new"], "work": g["work"], "work_text": autonomy.work_text(g["work"])})
    last = gl[-1]
    return {"grants": gl, "active": st["active"], "end": last["end"], "grant": last,
            "decisions": sum(len(g["decisions"]) for g in gl), "new": st["new"]}


def owed_view(root, task):
    """The owner's debt as the pages show it — the SAME ledger `el status` prints (owe.ledger):
    every item with its state, which of its holds is REACHED (work stands there), whether it
    is overdue. None when nothing was ever owed (owner, 2026-08-24)."""
    items = owe.ledger(root, task)
    if not items:
        return None
    out = []
    for it in items:
        stands = owe._stands(root, task, it) if it["status"] == "open" else []
        out.append(dict(it, stands=stands, overdue=owe.overdue(it),
                        holds_labels=[owe.hold_label(h) for h in it["holds"]]))
    n_open = sum(1 for it in items if it["status"] == "open")
    return {"items": out, "open": n_open,
            "standing": sum(1 for it in out if it["stands"]),
            "overdue": sum(1 for it in out if it["overdue"])}


# WHAT A CARD ON THE INDEX SHOWS beyond its name (owner, 2026-08-23): the request in one
# line, how much of the plan is closed, how much of the check is answered. The index is
# rebuilt on EVERY command that writes, so this is cached by the mtimes it depends on —
# the folder of nodes and the ledger; nothing is read twice for nothing.
_CARD_CACHE = {}


def closing_of(root, task):
    """The closing event of a task: outcome · result · why · when — or None while it is open."""
    try:
        last = None
        with open(os.path.join(root, task, "journal.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") == "done":
                    last = rec
                elif rec.get("type") == "reopened":
                    last = None
        if not last:
            return None
        return {"outcome": last.get("outcome") or "", "result": last.get("text") or "",
                "why": last.get("why") or "", "ts": last.get("ts") or "",
                "phase": last.get("phase") or "", "dirty": last.get("dirty") or ""}
    except OSError:
        return None


def phase_reached(tdir, meta):
    """THE PHASE THE TRACES REACHED — not the one that was declared.

    The owner's principle is «фаза — вычислимое поле», and until 2026-08-23 it was computed
    from the journal's advance/reroute events only: from what the agent DECLARED, not from
    what it LEFT on disk. A five-day campaign run in waves — plan, work, check, plan again —
    showed «2/8 думать» over 12 closed nodes, 69 verdicts and a `completed` badge (his
    screenshot). So the trace answers too:
      close     the task is closed — every phase is behind it, no argument
      validate  a verdict exists, or his word was said on validate
      execute   at least one node is closed
      plan      nodes/ exists
      think     thinking/ has something in it
    The DECLARED phase still rules the gates: a phase is entered by the owner's word and the
    agent's reason, and a trace must never skip that. This is what the human SEES."""
    if meta.get("outcome") or meta.get("status") in ("done", "completed", "closed", "dropped"):
        return "close"
    try:
        if os.path.exists(os.path.join(tdir, "checks.jsonl")):
            from .validate import validation_parse
            if any(v[0] != "open" for v in validation_parse(tdir).values()):
                return "validate"
        for n in nodes_all(tdir):
            if node_status(n) == "done":
                return "execute"
        if os.path.isdir(os.path.join(tdir, "nodes")) and os.listdir(os.path.join(tdir, "nodes")):
            return "plan"
        td = os.path.join(tdir, "thinking")
        if os.path.isdir(td) and os.listdir(td):
            return "think"
    except Exception:
        pass
    return "context"


def card_extras(tdir):
    """(request line, [nodes done, total], [criteria with verdict, total], verdict)."""
    key = tdir
    stamp = tuple(os.path.getmtime(p) if os.path.exists(p) else 0.0
                  for p in (os.path.join(tdir, "records.jsonl"), os.path.join(tdir, "checks.jsonl")))
    hit = _CARD_CACHE.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    from .state import request_line
    req = request_line(tdir, 160)
    nodes_done = nodes_total = 0
    val_done = val_total = 0
    verdict = ""
    try:
        from .plan import TERMINAL
        for n in nodes_all(tdir):
            nodes_total += 1
            if node_status(n) in TERMINAL:
                nodes_done += 1
        _o, info = rollup(tdir)
        rt = info["ROOT"]
        val_done, val_total = rt["sub"]["done"], rt["sub"]["total"]
        verdict = rt["verdict"]
    except Exception:
        pass
    out = {"request": req, "nodes": [nodes_done, nodes_total],
           "val": [val_done, val_total], "verdict": verdict}
    _CARD_CACHE[key] = (stamp, out)
    return out


def context_view(tdir):
    """THE CONTEXT FOR THE PAGE — folded out of records.jsonl · checks.jsonl
    (2026-08-26): the ladder in the order the agent walks it, each beat with its records;
    the registry of promises with their standing status and the root's colour; his word
    with the seq it was said over, and whether the picture moved since."""
    from .context import (amendments, last_seq, live as ctx_live, promises_at_root, qa_read,
                          scope_read, step_done, word_over)
    from .protocol import CONTEXT_FLOWS, CONTEXT_MIN, CONTEXT_STEPS
    from . import store
    mode = task_mode(tdir)
    steps = []
    for key, rel, title, src, _do, cmd in CONTEXT_STEPS:
        if key == "questions":
            items = qa_read(tdir)
        elif key == "research":
            items = ctx_live(tdir, step="research")
        elif key == "scope":
            items = scope_read(tdir)
        elif key == "ideal":
            items = {"promises": promises_at_root(tdir),
                     "ifr": [r["text"] for r in ctx_live(tdir, rtype="ifr")]}
        elif key == "approval":
            items = ctx_live(tdir, rtype="word")
        else:
            items = ctx_live(tdir, step=key)
        if isinstance(items, dict):
            n = sum(len(v) for v in items.values()) if key == "ideal" else \
                sum(len(v["in"]) + len(v["out"]) + len(v["blur"]) for v in items.values())
        else:
            n = sum(len(r["pairs"]) for r in items) if key == "questions" else len(items)
        steps.append({"key": key, "rel": rel, "title": title, "src": src, "cmd": cmd,
                      "flow": key in CONTEXT_FLOWS,
                      "required": required_in(CONTEXT_MIN.get(key, "soft"), mode),
                      "done": step_done(tdir, key, mode), "n": n, "items": items})
    # BARS — only where a NATURAL WHOLE exists (owner's drawing, 2026-08-27: «context ── 12/12 ·
    # 5W+H ── 5/5 · не больше»): the required rungs of the phase · the areas he owes · the three
    # layers of «now» · the six dimensions · the parts of the ideal. Later the same day he took
    # the ROW bars off the page («иногда вопросов нужно больше, иногда меньше — всего нет»):
    # the page now draws a count and a tick on every rung and keeps the bar on the band only;
    # the data below still carries the whole for `el status` / `el next`.
    from .context import area_coverage
    from .protocol import AREA_KEYS, QA_AREAS
    cov = area_coverage(tdir)
    src = {k: v for k, _d, v in QA_AREAS}
    need = {"light": ["goal", "check"], "soft": [a for a in AREA_KEYS if src[a] == "owner"],
            "strict": list(AREA_KEYS)}[mode]
    ideal_parts = ["checklist", "ifr"] if mode != "strict" else ["success", "metric", "checklist", "ifr"]
    by_key = {st["key"]: st for st in steps}
    have_parts = [k for k in ideal_parts if (by_key["ideal"]["items"]["ifr"] if k == "ifr"
                  else [p for p in by_key["ideal"]["items"]["promises"] if p["kind"] == k])]
    bars = {
        "questions": (sum(1 for a in need if cov[a]), len(need), "областей, которые за ним"),
        "now": (len({r.get("kind") for r in by_key["now"]["items"]}), 3, "слоя: ход · состояние · числа"),
        "scope": (sum(1 for k, v in by_key["scope"]["items"].items() if v["in"] or v["out"]), 6, "измерений"),
        "ideal": (len(have_parts), len(ideal_parts), "частей: " + " · ".join(ideal_parts)),
    }
    for st in steps:
        if st["key"] in bars:
            n, m, what = bars[st["key"]]
            st["bar"] = {"n": n, "m": m, "what": what}
    # The phase bar counts RUNGS only — the flows live in the tabs above the bands (owner,
    # 2026-08-27: «одна секция, но табами можно переключаться»).
    req = [st for st in steps if st["required"] and not st["flow"]]
    phase_bar = {"n": sum(1 for st in req if st["done"]), "m": len(req), "what": "обязательных ступеней"}
    # THE FLOWS — everything that runs through every phase, gathered once for the tabs;
    # each record carries the phase it was born on, so a tab can filter by it.
    # a research topic carries its FILE'S TEXT into the page data: the page opens by file://,
    # where the browser refuses fetch() of a sibling file, so the modal preview (owner,
    # 2026-08-27: «открыть, просмотреть — или открыть в отдельном окне») reads from here
    research = [dict(r) for r in ctx_live(tdir, step="research")]
    for r in research:
        if r.get("type") == "research" and r.get("file"):
            fp = r["file"] if os.path.isabs(r["file"]) else os.path.join(tdir, r["file"])
            try:
                with open(fp, encoding="utf-8") as fh:
                    r["body"] = fh.read(200_000)
            except OSError:
                r["body"] = ""
    flows = {"research": research,
             "unknown": ctx_live(tdir, step="unknown"), "definitions": ctx_live(tdir, step="definitions")}
    root_, task_ = os.path.dirname(os.path.abspath(tdir)), os.path.basename(os.path.abspath(tdir))
    w, stale = word_over(tdir, "context")
    return {"steps": steps, "seq": last_seq(tdir), "bar": phase_bar, "flows": flows,
            "promises": store.promises(root_, task_),
            "colour": store.colour(root_, task_),
            "word": dict(w, stale=stale) if w else None,
            "amendments": amendments(tdir)}


def think_view(tdir):
    """ДУМАНИЕ FOR THE PAGE — the rungs with their records and the three measurements of
    thinking as bars: forks решено N/N · cells paths × promises · categories of the box."""
    from .context import live as ctx_live, last_seq, promises_at_root, word_over
    from .think import cells, forks_read, step_done, tool_cats, tools_taken
    from .protocol import (THINK_CATS, THINK_CATS_MIN, THINK_FLOWS, THINK_MIN, THINK_STEPS,
                           THINK_RUNG_TOOLS, THINK_TOOLBOX)
    from . import store
    mode = task_mode(tdir)
    forks = forks_read(tdir)
    proms = promises_at_root(tdir)
    steps = []
    for key, rel, title, src, _do, cmd in THINK_STEPS:
        if key == "forks":
            items = forks
        elif key == "promises":
            items = proms
        elif key == "approval":
            items = [r for r in ctx_live(tdir, rtype="word") if r.get("scope") == "design"]
        else:
            items = [r for r in ctx_live(tdir, step=key) if r.get("type") != "skip"]
        st = {"key": key, "rel": rel, "title": title, "src": src, "cmd": cmd, "flow": key in THINK_FLOWS,
              "required": required_in(THINK_MIN.get(key, "soft"), mode), "done": step_done(tdir, key, mode),
              "n": len(items), "items": items, "tools": THINK_RUNG_TOOLS.get(key, ""),
              "skipped": bool(ctx_live(tdir, step=key, rtype="skip"))}
        if key == "forks":
            st["bar"] = {"n": sum(1 for f in forks if f["decision"]), "m": len(forks), "what": "решений принято"}
        if key == "options":
            sc, tot = cells(tdir)
            st["bar"] = {"n": sc, "m": tot, "what": "клеток пути × обещания оценено"}
        steps.append(st)
    used = tool_cats(tdir)
    need = THINK_CATS_MIN.get(mode, [])
    req = [st for st in steps if st["required"] and not st["flow"]]
    root_, task_ = os.path.dirname(os.path.abspath(tdir)), os.path.basename(os.path.abspath(tdir))
    w, stale = word_over(tdir, "design")
    return {"steps": steps, "seq": last_seq(tdir),
            "bar": {"n": sum(1 for st in req if st["done"]), "m": len(req), "what": "обязательных ступеней"},
            "tools": {"cats": THINK_CATS, "used": used, "need": need,
                      "box": THINK_TOOLBOX,                             # what is inside each category, tool by tool
                      "taken": tools_taken(tdir),                       # which records took which
                      "bar": {"n": len(used), "m": len(THINK_CATS), "what": "категорий приёмов"}},
            "colour": store.colour(root_, task_),
            "word": dict(w, stale=stale) if w else None}


def plan_view(tdir):
    """THE PLAN FOR THE PAGE (2026-08-27): the ladder with its bars — stages · promises per
    stage N/N · stops N/N · coverage N/M — the computed waves, and per node: its promises
    from the registry and its colour."""
    from .plan import node_promises, node_sync, nodes_all, plan_step_done, plan_waves, stages
    from .protocol import PHASE_BEATS
    from .context import word_over, last_seq
    from . import store
    mode = task_mode(tdir)
    st = stages(tdir)
    keys = ["stages", "promises", "sync", "coverage", "network", "approval"]
    rows = []
    ig = {"covered": 0, "total": 0}
    try:
        from .integrity import integrity_state
        state_, _orph = integrity_state(tdir)
        for items in state_.values():
            for it in items:
                ig["total"] += 1
                if it["by"] or it["unfolded"]:
                    ig["covered"] += 1
    except Exception:
        pass
    for (title, who, trace, minmode, _d, cmd), key in zip(PHASE_BEATS["plan"], keys):
        r = {"key": key, "title": title, "src": who, "cmd": cmd, "required": required_in(minmode, mode),
             "done": plan_step_done(tdir, key, mode), "n": 0}
        if key == "stages":
            r["n"] = len(st)
        elif key == "promises":
            r["bar"] = {"n": sum(1 for n in st if node_promises(tdir, n["id"])), "m": len(st), "what": "этапов с обещанием"}
        elif key == "sync":
            r["bar"] = {"n": sum(1 for n in st if node_sync(n)), "m": len(st), "what": "этапов с остановкой"}
        elif key == "coverage":
            tot = ig.get("total", 0); r["bar"] = {"n": ig.get("covered", 0), "m": tot, "what": "кусков цели покрыто"}
        elif key == "network":
            r["n"] = len(st)
        rows.append(r)
    try:
        waves, missing, cycle, deps = plan_waves(tdir)
        # the network is the movement between STAGES — packages live inside their stage
        # (owner, 2026-08-27: «Work Packages нет в Network Plan»)
        waves = [[i for i in w if "." not in i] for w in waves]
        waves = [w for w in waves if w]
        deps = {k: [d for d in v if "." not in d] for k, v in deps.items() if "." not in k}
    except Exception:
        waves, missing, cycle, deps = [], {}, [], {}
    root_, task_ = os.path.dirname(os.path.abspath(tdir)), os.path.basename(os.path.abspath(tdir))
    tree = {}
    for n in nodes_all(tdir):
        tree.setdefault(n.get("parent") or store.ROOT, []).append(n["id"])
    per = {}
    for n in nodes_all(tdir):
        per[n["id"]] = {"promises": node_promises(tdir, n["id"]),
                        "colour": store.colour(root_, task_, tree, n["id"])}
    w, stale = word_over(tdir, "plan")
    for r in rows:
        if r["key"] == "approval":
            r["n"] = 1 if w else 0
    req = [r for r in rows if r["required"]]
    return {"rows": rows, "bar": {"n": sum(1 for r in req if r["done"]), "m": len(req), "what": "обязательных ступеней"},
            "waves": waves, "missing": missing, "cycle": cycle, "deps": deps, "nodes": per,
            "word": dict(w, stale=stale) if w else None, "seq": last_seq(tdir)}


def render_views(root, only=None):
    """Refresh the projection behind the human pages (guide §3). The base stays the base
    and the pages stay untouched static readers; regenerated are only the data files in
    <root>/metadata/ — one for the index, one per project — which the pages include by
    relative path (allowed from disk, unlike reading files directly). `only` limits the
    per-project rebuild to the projects actually touched; the index is cheap and always
    refreshed; a project whose data file is missing is rebuilt regardless. The whole
    metadata/ folder is derived state: delete it, and the next command rebuilds it.
    A broken view must never break the bookkeeping, hence the blanket except."""
    try:
        meta_dir = os.path.join(root, "metadata")
        sync_page("index.html", os.path.join(root, "index.html"))
        projects = []
        in_hand = current_task(root)
        for t in tasks_of(root):
            sync_page("overview.html", os.path.join(root, t, "overview.html"))
            meta = dict(task_meta(root, t))
            meta["dir"] = t
            # THE PASSPORT (owner, 2026-08-25): the page's header names where the project
            # lives so the human can copy the folder — and hand it to an agent in a new
            # session — without a terminal; `in_hand` says whether the agent holds it now.
            meta["path"] = os.path.abspath(os.path.join(root, t))
            meta["root"] = os.path.abspath(root)
            meta["store"] = os.path.basename(os.path.abspath(root))
            meta["in_hand"] = (t == in_hand)
            meta["todos"] = todo_items(os.path.join(root, t))   # «на потом» on the page
            # THE BATON (2026-08-25): nodes waiting for the owner's hands — his debt of the kind
            # «потрогать и сказать»; the index badge counts it with the rest of «за тобой».
            meta["baton"] = [{"id": n["id"], "name": n.get("name", ""),
                              "note": n.get("waiting_note") or ""}
                             for n in waiting_nodes(os.path.join(root, t))]
            meta["autonomy"] = autonomy_view(root, t)   # index badge + overview ledger
            meta["owed"] = owed_view(root, t)           # «за тобой» — badge + section
            meta.update(card_extras(os.path.join(root, t)))
            meta["phase_reached"] = phase_reached(os.path.join(root, t), meta)
            # THE CLOSING, on the card (owner, 2026-08-23): «для закрытых проектов нужно
            # писать закрытие… почему мы закрыли, с каким результатом». The `done` event
            # carries all three — outcome, result, reason — and until now the card showed
            # only the badge.
            meta["closing"] = closing_of(root, t)
            projects.append(meta)
        projects.sort(key=lambda m: m.get("_mtime", 0.0), reverse=True)   # same clock as `el projects`
        stamp = now_iso()

        def dump(var, obj):
            return ("window." + var + " = "
                    + json.dumps(obj, ensure_ascii=False, indent=2).replace("</", "<\\/")
                    + ";\n")

        write(os.path.join(meta_dir, "index-data.js"),
              dump("ELEPHANT_INDEX", {"generated": stamp,
                                      "storage": os.path.basename(root),
                                      "projects": projects}))
        for m in projects:
            t = m["dir"]
            tdir = os.path.join(root, t)
            data_path = os.path.join(meta_dir, t + ".js")
            if only is not None and t not in only and os.path.exists(data_path):
                continue
            entries = []
            try:
                with open(os.path.join(tdir, "journal.jsonl"), encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(json.loads(line))
                            except ValueError:
                                pass
            except OSError:
                pass
            request = ""
            try:
                from .state import request_text
                request = request_text(tdir)
            except OSError:
                pass

            def md_text(rel):
                """A context document's text for the page, without its heading line."""
                try:
                    lines = open(os.path.join(tdir, rel),
                                 encoding="utf-8").read().strip().splitlines()
                except OSError:
                    return ""
                while lines and (not lines[0].strip() or lines[0].startswith("#")):
                    lines.pop(0)
                return "\n".join(lines).strip()

            def md_doc(rel):
                """A document as the page shows it: the base text and its amendments apart,
                so the page can draw a correction as a dated card under the original."""
                base, items = split_amendments(md_text(rel))
                return {"text": base, "amend": items}

            scope = scope_read(tdir)
            if not any(v["in"] or v["out"] or v["blur"] or v.get("struck")
                       for v in scope.values()):
                scope = None
            # THE VALIDATION LEDGER for the page: criteria come from the plan's nodes,
            # verdicts from `el validate` — the owner wants them visible, not buried
            # (2026-08-21: "я не увидел на HTML validation criteria"). Since 2026-08-23 the
            # ledger is a MATRYOSHKA (his design): each entry carries its depth, parent, own
            # and rolled-up counts — the page folds them the way the plan tree folds — and
            # `val_root` is the top line: the task itself, whose own criteria are the
            # acceptance checklist, with the owner's word above it all.
            criteria, val_root = [], None
            try:
                vorder, vinfo = rollup(tdir)
                for nid in vorder:
                    rec = vinfo[nid]
                    criteria.append({"node": nid, "name": rec["name"],
                                     "level": rec["level"], "status": rec["status"],
                                     "depth": rec["depth"], "parent": rec["parent"],
                                     "verdict": rec["verdict"],
                                     "own": [rec["own"]["done"], rec["own"]["total"]],
                                     "sub": [rec["sub"]["done"], rec["sub"]["total"]],
                                     "items": rec["items"]})
                rt = vinfo["ROOT"]
                word = None
                if word_given_on(root, t, "validate"):
                    for e in entries:
                        if e.get("type") == "accepted" and (
                                e.get("for") == "final" or e.get("phase") == "validate"):
                            word = {"ts": e.get("ts", ""), "words": e.get("text", "")}
                val_root = {"verdict": rt["verdict"],
                            "done": rt["sub"]["done"], "total": rt["sub"]["total"],
                            "failed": rt["sub"]["failed"],
                            "unverified": rt["sub"]["unverified"],
                            "ifr": [rt["own"]["done"], rt["own"]["total"]],
                            "word": word}
            except Exception:
                pass
            # ROUTE INTEGRITY for the page (owner, 2026-08-24): the check seen TOP-DOWN —
            # every piece of the goal and who covers it. Sits next to the plan, because it is
            # a property of the plan, not of the verdicts.
            integrity = None
            try:
                from .integrity import GOAL_KINDS, has_goal, integrity_state
                if has_goal(tdir):
                    st_i, orph = integrity_state(tdir)
                    integrity = {"kinds": [{"key": k, "title": GOAL_KINDS[k][0],
                                            "items": st_i[k]} for k in GOAL_KINDS],
                                 "orphans": orph}
            except Exception:
                integrity = None
            # THE LIVE BOARD of EXECUTE (owner, 2026-08-22): which node is in work, whose move
            # it is, how far each node is, what is filed to it. PLAN stays the contract; this
            # is the runtime, drawn from the same nodes plus the journal (traces filed --node).
            exec_data, plan_word = None, None
            try:
                traces = {}
                for e in entries:
                    if e.get("node") and e.get("type") in ("artifacts", "evidence") and e.get("files"):
                        traces.setdefault(e["node"], {"artifacts": [], "evidence": []})[
                            e["type"]].extend(e["files"])
                vn2, verd2, *_c2 = validation_state(tdir)
                forks_d = forks_read(tdir)
                ex_nodes = []
                for n in sorted(nodes_all(tdir), key=lambda x: x["id"]):
                    crits = criteria_of(n)
                    cd = sum(1 for i in range(1, len(crits) + 1)
                             if verd2.get((n["id"], i), ("open", ""))[0] != "open")
                    st = node_status(n)
                    note = {"waiting": n.get("waiting_note"), "blocked": n.get("block_note"),
                            "parked": n.get("park_note"), "done": n.get("result_note")}.get(st) or ""
                    txt = ((n["_fields"].get("inputs") or "") + " " +
                           (n["_fields"].get("deps") or "")).lower()
                    design = [{"fork": f["id"], "fidelity": f.get("fidelity") or "",
                               "preview": f.get("preview") or ""}
                              for f in forks_d if f["id"].lower() in txt and f.get("decision")]
                    res = [l for l in (n["_fields"].get("result") or "").splitlines() if l.strip()]
                    tr = traces.get(n["id"], {"artifacts": [], "evidence": []})
                    ex_nodes.append({"id": n["id"], "name": n.get("name", ""),
                                     "level": n.get("level", ""), "status": st, "note": str(note),
                                     "result": res[0].lstrip("- ").strip() if res else "",
                                     "crit_done": cd, "crit_total": len(crits),
                                     "artifacts": tr["artifacts"], "evidence": tr["evidence"],
                                     "started_at": n.get("started_at", ""),
                                     "reopen_note": n.get("reopen_note") or "",
                                     "cancelled": bool(n.get("cancelled")),
                                     "stop": sync_mark(n), "design": design})
                act = active_node(tdir)
                stops = [n for n in nodes_all(tdir) if node_sync(n)]
                # BETWEEN TWO NODES (feedback 2026-08-26: T2 closed at 15:32, T3 started at
                # 15:38 — in between the page put the owner's baton S2 in the «now» slot and
                # read as «current work is S2»): the last node closed and the next one ready
                # by the graph, so «now» is honest without an active node.
                last_done = None
                for e in entries:
                    if e.get("type") == "node-done":
                        last_done = {"id": (e.get("text") or "").split(":", 1)[0].strip(),
                                     "ts": e.get("ts", "")}
                try:
                    from .plan import ready_nodes as _rn
                    ready_ids = [n["id"] for n in _rn(tdir)[0][:3]]
                except Exception:
                    ready_ids = []
                exec_data = {"active": act["id"] if act and node_status(act) == "active" else None,
                             "waiting": [n["id"] for n in waiting_nodes(tdir)],
                             "last_done": last_done, "ready": ready_ids,
                             "nodes": ex_nodes,
                             "stops": {"total": len(stops),
                                       "passed": sum(1 for n in stops if node_status(n) == "done")}}
                for e in entries:
                    if e.get("type") == "accepted" and (
                            e.get("for") == "plan" or (e.get("phase") == "plan" and not e.get("for"))):
                        plan_word = {"ts": e.get("ts", ""), "words": e.get("text", "")}
            except Exception:
                exec_data, plan_word = None, None
            # THE PLAN TREE for the page (owner, 2026-08-21): every node with its filled
            # fields, foldable on the page. Labels ride along from NODE_FIELDS so the page
            # and the CLI can never disagree on what a field is called.
            plan_nodes = []
            try:
                from .plan import decomp_state
                for n in nodes_all(tdir):
                    fields = {k: v for k, v in (n.get("_fields") or {}).items()
                              if v and v != "_пусто_"}
                    plan_nodes.append({"id": n["id"], "level": n.get("level", ""),
                                       "name": n.get("name", ""),
                                       "status": n.get("status", ""), "fields": fields,
                                       "cancelled": bool(n.get("cancelled")),
                                       # the stage's layout: none · pending · accepted (2026-08-26)
                                       "decomp": decomp_state(root, t, tdir, n) if "." not in n["id"] else ""})
            except Exception:
                plan_nodes = []
            frame = {k: md_doc(CONTEXT_FILES[k]) for k in SCOPE_FRAME}
            frame = {k: v for k, v in frame.items() if v["text"] or v["amend"]}
            ifr_parts = {k: md_doc(CONTEXT_FILES[k]) for k in IFR_PARTS if k != "ifr"}
            ifr_parts["parts"] = md_doc(CONTEXT_FILES["parts"])
            ifr_parts = {k: v for k, v in ifr_parts.items() if v["text"] or v["amend"]}
            docs = {"clarified": md_doc("context/task.clarified.md"),
                    "ifr": md_doc("context/ifr.md"), "ideals": md_doc("thinking/ideals.md"),
                    "summary": md_doc("context/summary.md"),
                    "crystal": md_doc("thinking/crystal.md")}
            # THE THINK LADDER for the page (owner, 2026-08-21: «такой же, как для контекста,
            # в порядке тактов»): every step's document, keyed by step, plus the order and the
            # titles — they ride along from THINK_STEPS so the page and the CLI cannot disagree.
            think_parts = {k: md_doc(rel) for k, rel, *_x in THINK_STEPS}
            think_steps = [[k, title] for k, _rel, title, *_x in THINK_STEPS]
            # THE BADGE «поправок: N» counts each amendment ONCE, by file: thinking/crystal.md and
            # thinking/ideals.md are shown twice on the page (their own section and the think
            # ladder), and summing over the sections counted them twice (owner, 2026-08-23: badge
            # said 2, the project had one).
            amend_files = set(CONTEXT_FILES[k] for k in SCOPE_FRAME)
            amend_files |= set(CONTEXT_FILES[k] for k in IFR_PARTS)
            amend_files |= set(rel for _k, rel, *_x in THINK_STEPS)
            amend_files |= {"context/task.clarified.md", "context/summary.md",
                            "thinking/crystal.md", "thinking/ideals.md", "thinking/tools.md"}
            n_amend = sum(len(split_amendments(md_text(rel))[1]) for rel in amend_files)
            n_amend += len(scope_notes(tdir))
            write(data_path,
                  dump("ELEPHANT_OVERVIEW",
                       dict(m, generated=stamp, request=request,
                            # the review prompt for the page's «feedback» button — one copy,
                            # the same text `el feedback prompt` prints (owner, 2026-08-26)
                            feedback_prompt=feedback_prompt("all"),
                            worklog=worklog(root, t), stale=stale(root, t, tdir),
                            clarified=docs["clarified"],
                            ifr=docs["ifr"],
                            ideals=docs["ideals"],
                            summary=docs["summary"],
                            crystal=docs["crystal"],
                            unknown=md_text("context/unknown.md"),
                            amendments=n_amend,
                            amend_list=amend_list(root, t, entries),
                            scope_notes=scope_notes(tdir),
                            frame=frame, ifr_parts=ifr_parts,
                            exec=exec_data, plan_word=plan_word,
                            think_steps=think_steps, think_parts=think_parts,
                            think_tools=md_doc("thinking/tools.md"),
                            forks=forks_read(tdir),
                            criteria=criteria, val_root=val_root, integrity=integrity,
                            qa=qa_read(tdir),
                            ctx=context_view(tdir),
                            think=think_view(tdir),
                            plan="", plan_nodes=plan_nodes, planv=plan_view(tdir),
                            node_labels={k: head for k, head, _d in NODE_FIELDS},
                            scope=scope, files=project_files(tdir),
                            journal=entries[-200:])))
    except Exception:
        # A broken view must never break the bookkeeping — but a TEST must see it:
        # ELEPHANT_DEBUG=1 re-raises (the flow test sets it; a silent render failure hid a
        # NameError for a whole evening, 2026-08-27).
        if os.environ.get("ELEPHANT_DEBUG"):
            raise


def flush_renders():
    for root, tids in _DIRTY.items():
        render_views(root, tids or None)
    _DIRTY.clear()
