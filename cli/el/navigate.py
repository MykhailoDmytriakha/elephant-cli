"""THE NAVIGATOR — the three questions and the move.

status (is it on, where are we) · context (what is gathered, top to bottom, as content) ·
next (the move: step, who answers, what blocks, which command) · left (what is still
open) · where (absolute paths) · projects (the list) · forward / phase (one phase on
with a reason; back is free). `next` and `forward` must answer the gate question the
same way — they live side by side on purpose.
"""
import argparse, contextlib, io, json, os, re, sys
from .protocol import (AREA_KEYS, CONTEXT_FILES, CONTEXT_MIN, CONTEXT_STEPS, MODES, NEXT_MOVE, THINK_FILES,
                       OUTCOME_RU, PHASE_MAP, PHASE_MODE, PHASE_RU, PHASES, QA_AREAS, SCOPE_KEYS,
                       THINK_STEPS, required_in)
from . import autonomy, owe
from .worklog import last_line, stale_lines, worklog
from .state import (CLI_ENTRY, SKILL_ROOT, brief_read, brief_when, current_task, find_root, journal, journal_path, open_tasks,
                    phase_no, phase_state, pick_task, request_line, task_mode,
                    project_root, require_root, resolve_task, task_meta, task_state,
                    todo_items, todo_line,
                    tasks_of)
from .term import bar, emit, human_when, wrap
from .blueprint import phase_brief
from .context import area_coverage, context_step, questions_stat, scope_done
from .think import forks_read, think_step
from .plan import (STATUS_MARK, STATUS_RU, active_node, drift_lines, plan_drift, node_gaps, node_open, node_status,
                   node_sync, nodes_all, sync_mark, waiting_nodes)
from .validate import VERDICT_RU, check_line, criteria_of, rollup, validation_split, validation_state
from .amend import acked, amend_events, pending_line, pending_word, word_given_on


def node_traces(root, task, nid):
    """Artifacts and evidence FILED TO this node — `el artifact/evidence … --node` events."""
    arts, evs = [], []
    try:
        with open(os.path.join(root, task, "journal.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("node") == nid and rec.get("type") in ("artifacts", "evidence"):
                    names = rec.get("files") or []
                    (arts if rec["type"] == "artifacts" else evs).extend(names)
    except OSError:
        pass
    return arts, evs


def node_board(root, task, tdir, node, verdicts):
    """The active node, as a board: result · criteria progress · filed traces · stop · design."""
    nid = node["id"]
    st = node_status(node)
    since = str(node.get("started_at") or "")[:16].replace("T", " ")
    print(f"сейчас   {STATUS_MARK.get(st, '▶')} {nid} · {node.get('name','')}  [{node.get('level','?')}]"
          + (f" · в работе с {since}" if since else ""))
    result = [l for l in (node["_fields"].get("result") or "").splitlines() if l.strip()]
    if result:
        print(f"результат {wrap(result[0].lstrip('- ').strip(), indent='          ')}")
    crits = [l for l in (node["_fields"].get("check") or "").splitlines()
             if l.strip().startswith("-")]
    if crits:
        open_i = [str(i) for i in range(1, len(crits) + 1)
                  if verdicts.get((nid, i), ("open", ""))[0] == "open"]
        print(f"критерии  {len(crits) - len(open_i)}/{len(crits)} с вердиктом"
              + (f" · без вердикта: {', '.join(open_i)}" if open_i else " — все закрыты"))
    arts, evs = node_traces(root, task, nid)
    print(f"следы     артефакты {len(arts)} · доказательства {len(evs)}"
          + ("" if (arts or evs) else f" — ещё нет: el artifact <файл> --node {nid.lower()} · "
                                      f"el evidence <файл> --node {nid.lower()} --check <N>"))
    sm = sync_mark(node)
    if sm:
        print(f"остановка {sm} — показал человеку: el plan wait {nid.lower()} \"<что показал>\"")
    # A UI node that implements an accepted design carries the fork id in its inputs; the
    # accepted preview is the contract (owner, 2026-08-22: the first build drifted from the
    # previews he had chosen). The reminder names the fidelity he set.
    text = ((node["_fields"].get("inputs") or "") + " " + (node["_fields"].get("deps") or "")).lower()
    for f in forks_read(tdir):
        if f["id"].lower() in text and f.get("decision"):
            fid = f.get("fidelity") or "—"
            print(f"дизайн    {f['id']} · обязательность превью: {fid}"
                  + (f" · превью: {f['preview']}" if f.get("preview") else "")
                  + " — as-built сверить с превью перед закрытием; расхождение = поправка + слово владельца")
    kids = sorted((n for n in nodes_all(tdir) if n.get("parent") == nid), key=lambda x: x["id"])
    if kids:
        kd = sum(1 for k in kids if node_status(k) == "done")
        print(f"внутри    {kd}/{len(kids)} закрыто: " + " ".join(
            f"{STATUS_MARK.get(node_status(k), '·')}{k['id']}" for k in kids))


def return_lines(root, task):
    """THE RETURN (feedback 2026-08-25, the owner's words: «ожидал, что агент сначала рассмотрит
    проект, даст статус, расскажет, что дальше, и спросит, готовы ли приступать; вместо этого
    хватался за всё»). The recorder knows when the previous call was; the journal knows whether
    this run has left a trace yet. Silence longer than RETURN_GAP and no trace since — the agent
    has just come back, and the first move after a break is a REPORT to the human, not an action.
    Printed by `el`, `el status`, `el next` until the first trace (taking the task in hand is
    not one). Under a standing grant the report is one line and the work goes on."""
    if not task:
        return []
    try:
        from .calls import session_start
        from .state import last_trace_ts
        start, pause = session_start(root)
        if not start:
            return []
        last = last_trace_ts(root, task, skip=("hold",))
        if last:
            from datetime import datetime, timedelta
            # the journal line of a call is written BEFORE the recorder's line for the same
            # call — a few seconds of slack keep the run's own first write inside the run
            if datetime.fromisoformat(last) >= datetime.fromisoformat(start) - timedelta(seconds=10):
                return []
    except Exception:
        return []
    h = pause // 3600
    p = f"{h // 24} дн." if h >= 48 else (f"{h} ч" if h >= 1 else f"{pause // 60} мин")
    out = [f"возврат   пауза {p} с прошлого вызова el · следов этой сессии ещё нет"]
    if autonomy.on(root, task):
        out.append("          грант стоит — доложи человеку одной строкой (где мы · что дальше) "
                   "и продолжай")
    else:
        out.append("          первый ход — доклад человеку: где мы · что дальше · что за ним — и "
                   "вопрос,")
        out.append("          приступать ли; до его слова только читай: el status · el next · "
                   "el context")
    return out


def ctx_line(root, task=None):
    task = task or current_task(root)
    if not task:
        live = open_tasks(root)
        if live:
            return (f"🐘 {os.path.basename(root)} · в руке ничего (idle) · открытых {len(live)} · "
                    f"взять: el use <id>")
        return f'🐘 {os.path.basename(root)} · no tasks · create one: el new "<description>" --id <name>'
    meta = task_meta(root, task)
    phase = meta.get("phase", "context")
    tdir = os.path.join(root, task)
    if phase == "context":
        ok = os.path.exists(os.path.join(tdir, CONTEXT_FILES["approval"]))
        gate = "gate ОТКРЫТ владельцем" if ok else "gate HARD · нет слова владельца"
    else:
        gate = "gate soft"
    return (f"🐘 {os.path.basename(root)} · {task} · "
            f"phase {phase_no(phase)}/8 {phase} · {gate}")


def cmd_ctx(args):
    root = find_root()
    if not root:
        print("🐘 Elephant is not set up here" if args.line else "dir=absent")
        return 0
    # --task reads ANY task, including a closed one: a closed task is the archive of the
    # work, and an archive you cannot open is not an archive.
    want = getattr(args, "task", None)
    task = resolve_task(root, want) if want else current_task(root)
    if want and not task:
        print(f"no task {want}; available: {', '.join(tasks_of(root)) or '—'}", file=sys.stderr)
        return 1
    if args.line:
        print(ctx_line(root, task))
        return 0
    if args.json:
        print(json.dumps({"dir": root, "task": task,
                          "meta": task_meta(root, task) if task else {}},
                         ensure_ascii=False, indent=2))
        return 0
    print(ctx_line(root, task))
    if not task:
        return 0
    # `context` returns the CURRENT BIG PICTURE — the one file read top-down.
    # `status` answers where we are; `next` answers what to do now. Three questions,
    # three commands, no overlap. (Owner, 2026-08-18.)
    tdir = os.path.join(root, task)
    # THE WHOLE CONTEXT OF THE TASK, TOP TO BOTTOM, AS CONTENT — the page the owner remembers
    # from elephant-v1: original request → clarified task → context → 5W+H with the questions
    # and their answers → requirements → ideal result, one below the other. "Дай мне контекст
    # задачи" and it hands it over, whole. (Owner, 2026-08-19.)
    #
    # It prints the REAL FILES, not a hand-written aggregator with links. The previous version
    # printed the big picture as a tree of headings ending in "→ подробно: context/ifr.md" —
    # and that line is precisely how the ideal result stayed invisible: the tree looked
    # complete, the file was never opened, and nothing ever reached the person. A pointer is
    # not a presentation.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = print_context_full(root, task, tdir, getattr(args, "section", None))
    # THE COST OF A BOOT (recorder 2026-08-25: twelve session starts in an afternoon, each
    # reading the whole picture — 54 000 characters a time): after a break the return needs
    # `el status` · `el next`; the whole picture is for when the picture is the question.
    from .term import SCREEN_BUDGET as _budget
    if len(buf.getvalue()) > _budget:
        print("после обрыва целиком читать не обязательно: el status · el next — где мы и ход; "
              "el context --section <раздел> — один раздел; целиком — когда вопрос в самой картине")
    emit(buf.getvalue(), parts="el ctx --section <раздел> · разделы: " +
         " · ".join(k for k, _r, _t in ctx_sections(tdir)))
    return rc


def ctx_sections(tdir):
    """The sections of the whole road, in the order they are read — the addresses of `el ctx`."""
    order = [(k, rel, title) for k, rel, title, *_x in CONTEXT_STEPS]
    cdir = os.path.join(tdir, "context")
    known = {rel.split("/")[-1] for _k, rel, _t in order}
    sources = sorted(f for f in (os.listdir(cdir) if os.path.isdir(cdir) else [])
                     if f.endswith(".md") and f not in known)
    order += [(f[:-3], f"context/{f}", f"источник: {f[:-3]}") for f in sources]
    # research/ is READABLE by section (2026-08-24): `el ctx --section cluster` prints the
    # file; the full picture lists them (research_lines) instead of inlining — budget.
    from .context import research_files
    order += [(r["name"], r["rel"], f"исследование · {r['name']}") for r in research_files(tdir)]
    order += [(k, rel, f"думание · {title}") for k, rel, title, *_x in THINK_STEPS]
    order += [("tools", "thinking/tools.md", "думание · приёмы, которые брал"),
              ("plan", "plan.md", "план · сетевой план"),
              ("validation", "validation.md", "проверка на живом"),
              ("acceptance", "acceptance.md", "слово владельца на плане и приёмке")]
    return order


def print_context_full(root, task, tdir, want=None):
    """THE ELEPHANT CONTEXT — the whole road, not one phase of it.

    His name for it and his requirement (2026-08-19): "где бы ты ни был на всём этом пути — в
    execution, в validation — оно всегда показывает, откуда ты начал, куда ты доехал, твой
    текущий статус, и куда тебе дальше". So it does not stop at the gathering: everything the
    thinking produced — the research, the ideals, the forks and WHY each was decided that way —
    lands in the same read. That is what makes it possible, three phases later when something
    breaks, to come back and see why this road was chosen at all."""
    order = ctx_sections(tdir)

    if want:
        hits = [(k, rel, t) for k, rel, t in order
                if want.lower() in k.lower() or want.lower() in t.lower()]
        if not hits:
            print(f"нет раздела «{want}».", file=sys.stderr)
            print("hint     " + " · ".join(k for k, _r, _t in order), file=sys.stderr)
            return 1
        order = hits

    if not want:
        meta = task_meta(root, task)
        ph = meta.get("phase", "context")
        strip = " ".join(("✓" + p if k < PHASES.index(ph) else
                          ("▶" + p.upper() if k == PHASES.index(ph) else "·" + p))
                         for k, p in enumerate(PHASES))
        print(f"\nпуть     {strip}")
        print(f"задача   {meta.get('name','')}")
        am = [e for e in amend_events(root, task) if e.get("type") == "amend"]
        if am:
            last = am[-1]
            print(f"поправок {len(am)} · последняя п{last.get('n', '?')} "
                  f"{str(last.get('ts', ''))[:16].replace('T', ' ')} ({last.get('phase', '?')}) — "
                  f"в файлах ниже, секции «Поправка»")
    shown = 0
    for key, rel, title in order:
        if not want and rel.startswith("research/"):
            continue                      # listed below, one line per source
        path = os.path.join(tdir, rel)
        if not os.path.exists(path):
            if not want:
                print(f"\n── {title.upper()}   ✗ ещё не собрано  →  {rel}")
            continue
        body = open(path, encoding="utf-8").read().strip()
        # The file's own H1 repeats the heading we just printed; drop it, keep everything else.
        lines = body.splitlines()
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
        body = "\n".join(lines).strip()
        print(f"\n── {title.upper()}   ✓  {rel}")
        print(body if body else "  _пусто_")
        shown += 1

    if not want:
        # Research rides along: sources live in their own folder (owner, 2026-08-21) but
        # the gathering picture is not whole without naming what was actually looked at.
        from .context import research_lines
        print("\n── ИССЛЕДОВАНИЯ (research/)")
        for l in research_lines(tdir):
            print(l)
        cov = area_coverage(tdir)
        blank = [a for a in AREA_KEYS if not cov[a]]
        print("\n── ПОКРЫТИЕ СБОРА")
        print("  " + " · ".join(f"{a}:{cov[a]}" for a in AREA_KEYS))
        if blank:
            print(f"  пусто: {', '.join(blank)}   → el context areas")
        forks = forks_read(tdir)
        if forks:
            print("\n── РЕШЕНИЯ И ПОЧЕМУ ИМЕННО ТАК")
            for f in forks:
                print(f"  {f['id']} · {f['q']}")
                print(f"     {wrap(f['decision'] or '— ЕЩЁ НЕ РЕШЕНО', indent='     ')}")
        cstep, tstep = context_step(tdir), think_step(tdir)
        nxt = (f"шаг сбора «{cstep[2]}»" if cstep else
               (f"шаг думания «{tstep[2]}»" if tstep else "оба этапа закрыты"))
        print(f"\nдальше   {nxt}  → el next")
    return 0


def cmd_status(args):
    """Where are we and is Elephant on here — a question about the SYSTEM.

    Three commands, three different questions, and they must not blur into one:
      status — is it on, which project folder, which task is selected  (the system)
      ctx    — what is going on inside the selected task               (the project)
      next   — which move comes now                                    (the action)"""
    root = find_root()
    proj = project_root()
    cli = CLI_ENTRY
    if not root:
        print("elephant  off — not set up in this project")
        print(f"project   {proj}")
        print(f"cli       {cli}")
        print('start     el boot "<description>" --id <name>')
        return 0
    task = current_task(root)
    print(f"elephant  on · {root}")
    print(f"project   {proj}")
    if task:
        meta = task_meta(root, task)
        ph = meta.get("phase", "context")
        tdir = os.path.join(root, task)
        state, human = task_state(tdir)
        st = meta.get("status", "active")
        print(f"current   {task} · phase {phase_no(ph)}/8 {ph}"
              + ("" if st == "active" else f" · {st.upper()}"))
        print(f"          {meta.get('name', '')[:70]}")
        for l in return_lines(root, task):
            print(l)
        for l in stale_lines(root, task, tdir):
            print(l)
        # AUTONOMY FIRST (owner, 2026-08-22): whether the grant stands or stopped here is
        # what the agent, the harness judge and the returning owner all need before anything
        # else — so it is printed, not implied.
        for l in autonomy.lines(root, task):
            print(l)
        # THE OWNER'S DEBT next (owner, 2026-08-24): answers only he can bring and has not —
        # what stands on them is what he must see before anything else.
        for l in owe.lines(root, task):
            print(l)
        print(f"task      {state} — {human}")
        print(f"mode      {meta.get('mode', 'soft')} — {MODES.index(meta.get('mode', 'soft')) + 1}/3 по строгости"
              f" · el mode light|soft|strict")
        # The phase strip: passed · current · ahead, at a glance — and «~» for a phase the
        # TRACES reached without being declared, so the two readings sit on one line.
        i = PHASES.index(ph) if ph in PHASES else 0
        # THE DRIFT between what was declared and what the traces reached (his case
        # 2026-08-23: «2/8 думать» over 12 closed nodes and 69 verdicts). The declared phase
        # still rules the gates — a phase is entered with a reason, not by a side effect —
        # but a silent drift is how a task ends up closed from the middle of the road.
        # Said with the evidence and in two readings (feedback pool, 2026-08-24: «status
        # should separate the declared phase from what the traces cover»): which traces
        # pulled it there, and whether that is a wave inside execute or a gate driven past.
        r_i = i
        try:
            from .views import phase_reached
            reached = phase_reached(tdir, meta)
            r_i = PHASES.index(reached)
        except Exception:
            reached = ph
        strip = " ".join(("✓" + p if k < i else ("▶" + p.upper() if k == i else
                          ("~" + p if k <= r_i else "·" + p)))
                         for k, p in enumerate(PHASES))
        print(f"phases    {strip}" + ("   ~ следы есть, фаза не объявлена" if r_i > i else ""))
        # THE GATE in one line (feedback 2026-08-25): checklist and transition are two facts
        if st == "active":
            g_open, g_why = gate_verdict(root, task, tdir, ph)
            print("gate      " + ("открыт — el forward --why \"…\"" if g_open else f"закрыт — {g_why} · подробно: el next"))
            # THREE STATES, not one «готово» (feedback 2026-08-26): the nodes' own criteria say
            # «it works», the IFR checklist says «it is what he asked for», and his final word
            # is a third thing — apart, so green node verdicts cannot read as acceptance.
            vs = validation_split(tdir)
            if vs["nodes"]["total"] or vs["owner"]["total"]:
                print("проверка  " + check_line(vs, word_given_on(root, task, "validate")))
        if getattr(args, "short", False):
            print(f"cli       {cli}")
            return 0
        if r_i > i and st == "active":
            try:
                from .plan import node_status as _ns, nodes_all as _na
                _nodes = _na(tdir)
                _closed = sum(1 for n in _nodes if _ns(n) == "done")
                _vn, _vv, _o, *_r = validation_state(tdir)
                _total = sum(len(criteria_of(n)) for n in _vn)
                proof = (f" — узлов закрыто {_closed}/{len(_nodes)}"
                         + (f" · вердиктов {_total - _o}/{_total}" if _total else ""))
            except Exception:
                proof = ""
            print(f"объявлено {phase_no(ph)}/8 {ph} — эта фаза правит гейтами")
            print(f"по следам {phase_no(reached)}/8 {reached}{proof}")
            if i < PHASES.index("execute") and r_i >= PHASES.index("execute"):
                print(f"          исполнение началось, а {ph} не закрыт — закрой его, чтобы "
                      'путь сходился с диском: el forward --why "<что закрыто и чем доказано>"')
            else:
                print('          волна внутри исполнения (план → работа → проверка → снова план) '
                      '— нормально; переводить фазу — el forward --why "<что закрыто>"')
        # A CHECKLIST, not a mood: for each phase, how many required traces exist. An agent
        # reads it and sees at once "validation never came in", without asking anyone.
        print("checklist")
        for k, ph_name in enumerate(PHASES):
            have, missing = phase_state(tdir, ph_name)
            req = [x for x in have + missing if x[2]]
            got = [x for x in have if x[2]]
            mark = "✓" if k < i else ("▶" if k == i else "·")
            line = f"  {mark} {ph_name:<9} {len(got)}/{len(req)}"
            gaps = [r for r, _, rq in missing if rq]
            if k <= i and gaps:
                line += "  missing: " + ", ".join(gaps)
            print(line)
    else:
        live = open_tasks(root)
        if live:
            print(f"current   — в руке ничего (idle) · открытых {len(live)}: "
                  f"{', '.join(live[:4])}{' …' if len(live) > 4 else ''}")
            print("          взять: el use <id> · список с фазами: el projects")
        elif tasks_of(root):
            print('current   — в руке ничего · все задачи закрыты · новая: el new "<description>" --id <name>')
        else:
            print("current   — no tasks yet")
    print(f"tasks     {len(tasks_of(root))}")
    print(f"cli       {cli}")
    # WHERE THE TOOL LIVES (feedback 2026-08-25: an agent had to find detect.sh
    # through its own env var): the clone, the entry, the probe — measured from the package.
    tool = os.path.join(SKILL_ROOT, "cli", "el.py")
    if os.path.realpath(tool) != os.path.realpath(str(cli)):
        print(f"tool      {tool}")
    print(f"probe     bash {os.path.join(SKILL_ROOT, 'cli', 'detect.sh')} — есть ли Elephant здесь")
    # THE SHEET (owner, 2026-08-22): brief.md — what a returning agent must know, printed
    # whole; it is bounded, so it always fits.
    if task:
        b = brief_read(os.path.join(root, task))
        if b:
            print(f"листок    brief.md · переписан {brief_when(tdir)} — читать первым:")
            for bl in b.splitlines():
                print(f"  {bl}")
            bs = autonomy.brief_stale_line(root, task, indent="  ")
            if bs:
                print(bs)
        # LOOP HYGIENE under autonomy: «холостой ход» — looks at `el status` that follow one
        # another with not a single new trace between them. The count lives in metadata/
        # (service data, derived — delete it and it restarts), never in the journal.
        if autonomy.on(root, task):
            pulse_path = os.path.join(root, "metadata", task + ".pulse.json")
            seen = {"events": -1, "streak": 0}
            try:
                seen.update(json.load(open(pulse_path, encoding="utf-8")))
            except (OSError, ValueError):
                pass
            ev = task_meta(root, task).get("events", 0)
            fresh = ev - seen["events"] if seen["events"] >= 0 else None
            streak = seen["streak"] + 1 if fresh == 0 else 0
            try:
                os.makedirs(os.path.dirname(pulse_path), exist_ok=True)
                json.dump({"events": ev, "streak": streak}, open(pulse_path, "w", encoding="utf-8"))
            except OSError:
                pass
            if fresh is not None:
                print(f"пульс     следов с прошлого взгляда: +{fresh}"
                      + (f" · ⚠ холостой ход: {streak + 1} взгляда подряд без единого следа — "
                         'работай или остановись честно: el halt "…"' if streak >= 1 else ""))
    # "Where am I" without "what is left" sends the reader to three more commands to add up
    # by hand. The block below is the same one `el left` prints (owner, 2026-08-20).
    if task:
        tdir = os.path.join(root, task)
        behind = passed_lines(root, task, tdir)
        if behind:
            print("ПРОЙДЕНО")
            for l in behind:
                print(l)
        lines = left_lines(root, task, tdir, owed=False)   # printed first, above
        if lines:
            print("ОСТАЛОСЬ")
            for l in lines:
                print(l)
    print("next      el next — the move · el left — what is left · el help — how it works")
    return 0


def passed_lines(root, task, tdir):
    """The road BEHIND: which phases are closed, which nodes are done, whose word closed them.

    `status` answered "where am I" and, since this morning, "what is left" — and still not
    "what have we passed". The owner asked it in plain words and then guessed the command name
    (2026-08-20: "я до сих пор не знаю, какую команду напечатать, чтобы увидеть... что мы
    прошли... это el status, правильно?"). Guessing the name is a defect report, so the answer
    belongs in the command he guessed."""
    out = []
    meta = task_meta(root, task)
    cur = meta.get("phase", "context")
    i = PHASES.index(cur) if cur in PHASES else 0
    for k, name in enumerate(PHASES[:i]):
        have, missing = phase_state(tdir, name)
        req = [x for x in have + missing if x[2]]
        out.append(f"фазы      ✓ {name:<9} следов {len([x for x in have if x[2]])}/{len(req)}"
                   if k == 0 else
                   f"          ✓ {name:<9} следов {len([x for x in have if x[2]])}/{len(req)}")
    nodes = nodes_all(tdir)
    done = [n for n in nodes if n.get("status") == "done"]
    stops = [n for n in nodes if node_sync(n)]
    passed = [n for n in stops if n.get("status") == "done"]
    for k, n in enumerate(done):
        note = (n.get("result_note") or "").strip().replace("\n", " ")
        head = "узлы      " if k == 0 else "          "
        out.append(f"{head}✓ {n['id']:<4} {(n.get('name','') or '')[:44]:<46}{note[:38]}")
    if stops:
        out.append(f"остановки пройдено {len(passed)} из {len(stops)}")
    ap = os.path.join(tdir, "acceptance.md")
    if os.path.exists(ap):
        quotes = [l.strip()[2:].strip() for l in open(ap, encoding="utf-8") if l.startswith("> ")]
        if quotes:
            out.append(f"его слово «{quotes[-1][:70]}»")
    return out


def left_lines(root, task, tdir, owed=True):
    """The one answer to "what is still left" — assembled from files, never from memory.

    It existed nowhere: `status` said where we are, `plan` printed the whole tree, `todo` held
    parked notes, `projects` listed neighbours. To answer his question an agent had to run four
    commands and add them up in its head, which is exactly the kind of work a navigator is
    supposed to do FOR you. (Owner, 2026-08-20: "el status что еще осталось".)

    Order is deliberate: what blocks first, then what waits, then who is waiting on us."""
    out = []
    everything = nodes_all(tdir)
    nodes = [n for n in everything if node_open(n)]
    done = [n for n in everything if n.get("status") == "done"]
    stops = [n for n in nodes if node_sync(n) in ("РАЗРЕШЕНИЕ", "РАЗВИЛКА")]
    meta = task_meta(root, task)
    ph = meta.get("phase", "context")

    if owed:
        out += owe.lines(root, task)
    if nodes or done:
        out.append(f"узлы      открыто {len(nodes)} из {len(everything)}")
        act = active_node(tdir)
        for w_n in waiting_nodes(tdir):
            out.append(f"          ⏸ {w_n['id']} ждёт владельца — {str(w_n.get('waiting_note') or '')[:60]} "
                       f"→ el accept \"<его слова>\" --for node:{w_n['id'].lower()}")
        if act and node_status(act) == "active":
            out.append(f"          ▶ сейчас {act['id']} · {(act.get('name') or '')[:50]}")
            out.append(f"          {last_line(root, task, act['id'])}")
        elif nodes and not waiting_nodes(tdir):
            out.append(f"          в работе никого — el plan start {nodes[0]['id'].lower()}")
        for n in nodes:
            mark = sync_mark(n)
            title = (n.get("name") or n.get("id", ""))[:50]
            st = node_status(n)
            out.append(f"          {STATUS_MARK.get(st, '·')} {n.get('id', '?'):<6} "
                       f"{title:<52}{STATUS_RU.get(st, st):<14}{mark}")
    if stops:
        first = stops[0]
        out.append(f"стоп      {sync_mark(first)} на {first.get('id', '?')} — "
                   f"без его слова дальше нельзя")

    # What actually blocks at validate is not the node list — the nodes are closed — but the
    # promises the plan made and nobody answered. Left out of here, "осталось 0 узлов" reads
    # like "nothing left" while the gate refuses to move.
    _n, _v, open_n, failed_n, decl_n, unver_n = validation_state(tdir)
    if open_n or failed_n or unver_n:
        out.append(f"критерии  без вердикта {open_n}" +
                   (f" · НЕ проверено {unver_n}" if unver_n else "") +
                   (f" · НЕ сошлось {failed_n}" if failed_n else "") + "  → el validate")

    openq = [it for it in todo_items(tdir) if it["open"]]
    if openq:
        out.append(f"на потом  {len(openq)} — обещания к фазам, не ход · el todo · "
                   "закрыть: el todo --done N")
        for it in openq[:4]:
            out.append(f"          {todo_line(it, width=72)}")
        if len(openq) > 4:
            out.append(f"          … и ещё {len(openq) - 4} — el todo")

    have, missing = phase_state(tdir, ph)
    gaps = [rel for rel, _, req in missing if req]
    if gaps:
        out.append(f"следы     не хватает: {', '.join(gaps)}")
    pend = pending_word(root, task)
    if pend:
        out.append(f"поправки  без его слова: {pending_line(pend)} — el accept")
    behind_l = []
    for ph_b in PHASES[:PHASES.index(ph)] if ph in PHASES else []:
        _hb, _mb = phase_state(tdir, ph_b)
        behind_l += [rel for rel, _w, req in _mb if req]
    if behind_l:
        out.append(f"за спиной {', '.join(behind_l)} — следы прошлых фаз, допиши или осознанно оставь")
    if ph == "validate" and not word_given_on(root, task, "validate"):
        out.append("приёмка   слова человека над результатом на этой фазе нет — el accept")

    waiting = []
    for other in tasks_of(root):
        if other == task:
            continue
        m = task_meta(root, other)
        if m.get("depends_on") == task and m.get("status", "active") == "active":
            waiting.append(f"{other} · фаза {phase_no(m.get('phase', 'context'))}/8")
    for w in waiting:
        out.append(f"ждёт нас  {w}")
    return out


# ── el progress — the main files of every phase, whole, one screen ─────────────
# (owner, 2026-08-22: «Progress выводит просто реальные главные файлы каждой фазы в полном
# составе — один-два на фазу, 200–300 строк максимум, сильно ужимать не надо».)
# Nothing is written, nothing is composed: per phase one or two REAL files printed whole
# (request · clarified task and the summary · crystal and decisions · plan.md), and where the
# phase's truth is a graph rather than a document — the nodes with their results, the
# criteria with their verdicts, the lessons, the chain of phase moves with their reasons.
# A file longer than PROGRESS_FILE_LINES is cut with its address; the whole screen goes
# through term.emit, so a long one says so in its head and names its parts.
PROGRESS_FILE_LINES = 120
PROGRESS_PARTS = ["init", "context", "think", "plan", "execute", "validate", "reflect", "align", "close"]


def _file_block(tdir, rel, title, part):
    path = os.path.join(tdir, rel)
    if not os.path.exists(path):
        return []
    lines = open(path, encoding="utf-8").read().rstrip("\n").splitlines()
    out = [f"── {title} · {rel}"]
    body = lines[:PROGRESS_FILE_LINES]
    out += body
    if len(lines) > PROGRESS_FILE_LINES:
        out.append(f"… ещё {len(lines) - PROGRESS_FILE_LINES} строк — файл целиком: {rel} · "
                   f"el progress {part}")
    out.append("")
    return out


def _events(root, task, kinds):
    out = []
    try:
        with open(journal_path(root, task), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") in kinds:
                    out.append(rec)
    except OSError:
        pass
    return out


def progress_lines(root, task, part=None):
    tdir = os.path.join(root, task)
    meta = task_meta(root, task)
    ph = meta.get("phase", "context")
    want = lambda p: part is None or part == p
    out = []
    if part is None:
        st = meta.get("status", "active")
        out.append(f"PROGRESS  {task} · фаза {phase_no(ph)}/8 {ph} · режим {meta.get('mode', 'soft')}"
                   + ("" if st == "active" else f" · {st.upper()}"))
        out.append(f"          {(meta.get('name') or '')[:90]}")
        out += autonomy.lines(root, task)
        b = brief_read(tdir)
        if b:
            out.append("── листок · brief.md")
            out += b.splitlines()
            bs = autonomy.brief_stale_line(root, task, indent="")
            if bs:
                out.append(bs)
            out.append("")
    if want("init"):
        out += _file_block(tdir, "init/request.md", "0 · запрос пользователя", "init")
    if want("context"):
        out += _file_block(tdir, CONTEXT_FILES["clarified"], "1 · задача после уточнений", "context")
        out += _file_block(tdir, CONTEXT_FILES["summary"], "1 · свёртка контекста", "context")
        if not os.path.exists(os.path.join(tdir, CONTEXT_FILES["clarified"])) \
                and not os.path.exists(os.path.join(tdir, CONTEXT_FILES["summary"])):
            qs = questions_stat(tdir)
            out.append("── 1 · контекст — ни clarified, ни свёртки ещё нет"
                       + (f" · вопросов {qs[1]}" if qs else "") + " · el context")
            out.append("")
    if want("think"):
        out += _file_block(tdir, THINK_FILES["crystal"], "2 · кристалл — как вызревало решение", "think")
        out += _file_block(tdir, THINK_FILES["decision"], "2 · развилки и решения", "think")
    if want("plan"):
        out += _file_block(tdir, "plan.md", "3 · сетевой план", "plan")
        nodes = sorted(nodes_all(tdir), key=lambda x: x["id"])
        if nodes:
            out.append("── 3 · узлы плана с итогами · nodes/")
            for n in nodes:
                st_n = node_status(n)
                note = (n.get("result_note") or "").strip().replace("\n", " ")
                out.append(f"  {STATUS_MARK.get(st_n, '·')} {n['id']:<8} {(n.get('name') or '')[:48]:<50}"
                           f"{STATUS_RU.get(st_n, st_n):<14}{note[:60]}")
            out.append("")
    if want("execute"):
        nodes = nodes_all(tdir)
        if nodes:
            act = active_node(tdir)
            done_n = [n for n in nodes if node_status(n) == "done"]
            wait_n = waiting_nodes(tdir)
            out.append(f"── 4 · исполнение · закрыто {len(done_n)}/{len(nodes)}"
                       + (f" · в работе {act['id']} — {(act.get('name') or '')[:50]}" if act and node_status(act) == "active" else "")
                       + (f" · ждут владельца {', '.join(w['id'] for w in wait_n)}" if wait_n else ""))
            for d in os.listdir(os.path.join(tdir, "artifacts")) if os.path.isdir(os.path.join(tdir, "artifacts")) else []:
                out.append(f"  артефакт  artifacts/{d}")
            out.append("")
    if want("validate"):
        vnodes, verdicts, open_n, failed_n, decl_n, unver_n = validation_state(tdir)
        total = sum(len(criteria_of(n)) for n in vnodes)
        if total:
            out.append(f"── 5 · проверка · критериев {total} · без вердикта {open_n} · не сошлось {failed_n}"
                       f" · не проверено {unver_n} · снято {decl_n} · леджер: el validate")
            for (nid, i), (st_v, proof) in sorted(verdicts.items()):
                out.append(f"  {nid}.{i:<3} {st_v:<11} {(proof or '')[:80]}")
            out.append("")
    if want("reflect"):
        les = _events(root, task, ("lesson",))
        if les:
            out.append(f"── 6 · уроки · {len(les)} · lessons.md хранилища")
            for r in les:
                out.append(f"  · {(r.get('text') or '')[:100]}")
            out.append("")
    if want("align"):
        moves = _events(root, task, ("advance", "reroute"))
        if moves:
            out.append("── 7 · ход по фазам — переходы с основаниями · journal.jsonl")
            for r in moves:
                why = (r.get("why") or "").strip()
                out.append(f"  {human_when(r.get('ts')):<14} {r.get('type'):<8} {(r.get('text') or ''):<20} "
                           f"{why[:80]}")
            out.append("")
    if want("close"):
        if meta.get("status", "active") != "active":
            out.append(f"── 8 · закрыта · {meta.get('outcome', '')} · {human_when(meta.get('closed_at'))}")
            out.append(f"  {(meta.get('result') or '')[:200]}")
            out.append("")
    if part is None:
        out.append("дальше    el next · где мы: el status · одна фаза целиком: el progress <фаза>")
    return out


def cmd_progress(args):
    """`el progress` — the story so far: the main files of every phase, whole, one screen;
    `el progress <фаза>` — one phase's files without the cap."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    part = (getattr(args, "part", None) or "").strip().lower()
    part = {"0": "init", "запрос": "init", "контекст": "context", "думание": "think", "план": "plan",
            "исполнение": "execute", "проверка": "validate", "уроки": "reflect", "сверка": "align",
            "закрытие": "close"}.get(part, part)
    if part and part not in PROGRESS_PARTS:
        print(f"нет части «{part}» · части: {' · '.join(PROGRESS_PARTS)}", file=sys.stderr)
        return 1
    emit("\n".join(progress_lines(root, task, part or None)),
         parts="el progress " + " · ".join(PROGRESS_PARTS))
    return 0


def cmd_left(args):
    """What is still left on the current task — nodes, stops, parked questions, dependants."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    meta = task_meta(root, task)
    print(f"ОСТАЛОСЬ  {task} · фаза {phase_no(meta.get('phase', 'context'))}/8 "
          f"{meta.get('phase', 'context')}")
    lines = left_lines(root, task, tdir)
    if not lines:
        print("          ничего открытого — задача идёт к закрытию фазы")
    for l in lines:
        print(l)
    print("дальше    el next — ход · el plan — дерево целиком")
    return 0


def cmd_projects(args):
    """The list of tasks, written for the OWNER first.

    The old shape put open and closed tasks in one column, printed raw ISO stamps, and cut the
    description mid-word — so the eye had to filter, decode and guess. Reworked on his request
    (2026-08-20: "el ls сделай удобнее вывод для пользователя"). The rules used: what is alive
    comes first and what is closed sits in its own group below · the date prefix is dropped from
    the name because the date has its own column · the description gets its own line instead of
    being amputated · phases are named in the language the rest of the output speaks."""
    root = find_root()
    if not root:
        print("Elephant is not set up here")
        return 0
    cur = current_task(root)
    ids = tasks_of(root)
    if not ids:
        print("задач пока нет   ·   завести:  el new \"<описание>\" --id <имя>")
        return 0
    live, closed = [], []
    for tid in ids:
        m = task_meta(root, tid)
        (live if m.get("status", "active") == "active" else closed).append((tid, m))
    # Freshest first: the one touched last is almost always the one being asked about.
    # By the journal's mtime — the clock `current_task` uses. The millisecond ISO stamp
    # tied two tasks written by one command (`el spawn`) and let the order flip between
    # runs (found by the differential test, 2026-08-21).
    live.sort(key=lambda x: x[1].get("_mtime", 0.0), reverse=True)
    closed.sort(key=lambda x: x[1].get("_mtime", 0.0), reverse=True)

    # The date STAYS in the name. Stripping it read cleaner and lost a meaning the owner uses:
    # the prefix says WHEN the task was started, while the right-hand column says when it was
    # last touched — two different facts, and he reads both (2026-08-20: "там дата и потом
    # SongShare... сразу было понятно, где, когда началась задача").
    short = lambda tid: tid
    w = max((len(short(t)) for t, _ in live + closed), default=12)

    print(f"ЗАДАЧИ    открыто {len(live)} · закрыто {len(closed)}")
    for tid, m in live:
        ph = m.get("phase", "context")
        tdir = os.path.join(root, tid)
        have, missing = phase_state(tdir, ph)
        req_have = len([x for x in have if x[2]])
        req_all = req_have + len([x for x in missing if x[2]])
        ready = req_all and req_have == req_all
        # «готова к переходу» is the GATE's word, not the checklist's (feedback 2026-08-25):
        # a full checklist over open nodes says so, and names the door that is shut
        g_open, g_why = gate_verdict(root, tid, tdir, ph)
        label = ("   готова к переходу" if g_open
                 else (f"   чек-лист готов · переход закрыт: {g_why}" if ready else ""))
        mark = "▶" if tid == cur else " "
        phase_txt = f"{phase_no(ph)}/8 {PHASE_RU.get(ph, ph)}"
        print(f"\n{mark} {short(tid):<{w}}  {phase_txt:<14} {bar(req_have, req_all)} "
              f"{req_have}/{req_all:<3} {human_when(m.get('updated_at', ''))}" + label)
        name = (m.get("name", "") or "").strip()
        if name:
            print(f"  {'':<{w}}  {wrap(name, indent=' ' * (w + 4), width=92)}")
        # HIS WORDS under the name (owner, 2026-08-22): an agent in another conversation
        # recognises a task by the request, not by an id it never saw — and does not open
        # a twin.
        rl = request_line(tdir, 100)
        if rl:
            print(f"  {'':<{w}}  запрос: {rl}")
        dep = m.get("depends_on", "")
        if dep:
            dm = task_meta(root, dep)
            dst = dm.get("status", "active")
            state = ("путь свободен: " + OUTCOME_RU.get(dst, dst)) if dst != "active" \
                else f"ещё идёт, фаза {phase_no(dm.get('phase', 'context'))}/8"
            print(f"  {'':<{w}}  ждёт {short(dep)} — {state}")
    if closed:
        print("\nЗАКРЫТЫ")
        for tid, m in closed:
            st = m.get("status", "")
            print(f"  {short(tid):<{w}}  {OUTCOME_RU.get(st, st):<14} "
                  f"{human_when(m.get('updated_at', ''))}")
    if live and not cur:
        print("\nв руке    ничего (idle) — взять: el use <имя>   ·   новая   el spawn \"<описание>\" --id <имя>")
    else:
        print("\nв руку    el use <имя>   ·   новая   el spawn \"<описание>\" --id <имя>")
    print("          та же задача снова — не заводи дубль: el use <имя> · повтор запроса: "
          'el boot "…" --id <имя> --raw "<слова>"')
    return 0


def cmd_next(args):
    """The next move — and HOW things are done on this phase.

    Written for an AGENT: every answer carries what is missing, the rule of the phase, and
    the exact command. Says "undefined" honestly when there is no route — inventing one is
    the kind of plausible output that makes a tool untrustworthy."""
    root = find_root()
    if not root:
        print("no Elephant here.")
        print('hint     start with: el boot "<description>" --id <name>')
        print("         el help — the whole flow, phase by phase")
        return 0
    want = getattr(args, "task", None)
    task = resolve_task(root, want) if want else current_task(root)
    if want and not task:
        print(f"no task {want}", file=sys.stderr)
        print(f"hint     known: {', '.join(tasks_of(root)) or '— none'} · el projects", file=sys.stderr)
        return 1
    if not task:
        live = open_tasks(root)
        if live:
            # Idle is a real state (owner, 2026-08-22): nothing is picked up by freshness —
            # the next move is to TAKE a task, and that is said, not guessed.
            print(f"в руке   ничего (idle) · открытых {len(live)}")
            for t in live[:6]:
                m = task_meta(root, t)
                print(f"         {t} · {phase_no(m.get('phase', 'context'))}/8 {m.get('phase', 'context')}"
                      f" · {(m.get('name') or '')[:50]}")
            print("hint     взять: el use <id> · новая: el new \"<description>\" --id <name>")
            return 0
        print("no tasks." if not tasks_of(root) else "no open tasks — every task is closed.")
        print('hint     el new "<description>" --id <short-name>')
        print("         el projects — what already exists")
        return 0
    tdir = os.path.join(root, task)
    meta = task_meta(root, task)
    phase = meta.get("phase", "context")
    if meta.get("status", "active") != "active":
        print(f"task     {task} — CLOSED as {meta['status']} on {meta.get('closed_at','?')[:10]}")
        print("hint     el projects — what is still open · el use <id> — switch")
        return 0

    st, st_human = task_state(tdir)
    mode = meta.get("mode", "soft")
    have, missing = phase_state(tdir, phase, mode)
    spec = PHASE_MAP.get(phase, {})
    print(f"task     {task} · phase {phase_no(phase)}/8 {phase} · {st} ({st_human}) · mode {mode}")
    # AUTONOMY (owner, 2026-08-22): the grant, the decisions, the stop — before the navigator
    # speaks, because it changes what «спроси его» means below: no owner → decide in his place,
    # mark it, go on; the grant reaches no further → el halt, not «done».
    auto = autonomy.state(root, task)
    for l in autonomy.lines(root, task, full=True):
        print(l)
    if auto and auto["halt"]:
        print("         дальше без человека нельзя — остановись; его слово снимает остановку")
    auto_on = bool(auto and auto["active"])
    for l in return_lines(root, task):
        print(l)
    for l in stale_lines(root, task, tdir):
        print(l)
    b_line = brief_read(tdir).splitlines()
    if b_line:
        print(f"листок   {b_line[0][:80]} … · el brief — целиком (читай первым после обрыва)")
        bs = autonomy.brief_stale_line(root, task, indent="         ")
        if bs:
            print(bs)
    elif auto_on:
        print('листок   brief.md пуст — заведи: el brief "<baseline · замер · лучшее · не повторять · сейчас>"')
    # Stage 0 closes with the tree on disk AND the user's request recorded (owner, 2026-08-21):
    # by the time any phase is worked, init/request.md must already exist. Not a context
    # trace — a nag that stays until initialization is actually finished.
    if not os.path.exists(os.path.join(tdir, "init", "request.md")):
        print("init ✗   этап 0 не закрыт: init/request.md не записан — запрос пользователя его")
        print("         словами, только о задаче. Попроси повторить запрос и дозапиши:")
        print(f'         el boot "<задача>" --id {task} --raw "<его слова о задаче>"')
    if have:
        print("have     " + " · ".join(f"✓ {r}" for r, _, _ in have))
    for rel, what, required in missing:
        print(f"missing  ✗ {rel:<28}{'REQUIRED' if required else 'optional'} — {what}")

    # THE PICTURE HAS CHANGED SINCE HIS WORD. An amendment to a context document made past
    # context (a moved boundary, a corrected task, a new requirement found by evidence) re-opens
    # the first big stop: show it, hear him, record — or go on by --waive, out loud. The
    # separate `thinking/destination.md` that used to block here is gone (2026-08-21): the goal
    # IS context/task.clarified.md with its amendments, the engineer's half is crystal.md.
    pend = pending_word(root, task)
    if pend:
        print(f"слово    картина правилась после его слова: {pending_line(pend)} — "
              f'предъяви поправки, запиши ответ: el accept "<его слова>"')
    # BEHIND: required traces of PASSED phases that are missing. The protocol grows on live
    # work — a beat added after this task passed the phase — and a trace nobody is shown is a
    # trace nobody fills (owner, 2026-08-22, on a live project: «next не говорит, что нужно
    # это делать»). Never blocks: what is passed is passed. The same for owner-areas never
    # asked about, once context is behind.
    behind_tr = []
    for ph_b in PHASES[:PHASES.index(phase)]:
        _hb, _mb = phase_state(tdir, ph_b)
        behind_tr += [rel for rel, _w, req in _mb if req]
    owner_blank_b = []
    if phase != "context":
        cov_b = area_coverage(tdir)
        src_b = dict((k, v) for k, _d, v in QA_AREAS)
        owner_blank_b = [a for a in AREA_KEYS if not cov_b[a] and src_b[a] == "owner"]
    ack_b = acked(root, task)
    behind_tr = [r for r in behind_tr if r not in ack_b]
    owner_blank_b = [a for a in owner_blank_b if a not in ack_b and f"area:{a}" not in ack_b]
    if behind_tr or owner_blank_b:
        print("за спиной следы прошлых фаз не на месте — такт появился после прохода или был пропущен:")
        if behind_tr:
            print(f"         {wrap(' · '.join(behind_tr), indent='         ')}")
        if owner_blank_b:
            print(f"         области без единого вопроса владельцу: {', '.join(owner_blank_b)} "
                  f'— спроси: el context qa "…" "…" --area <область>')
        print("         допиши той же командой — ляжет как поздний след (картина изменится → его "
              'слово заново) · либо осознанно оставь: el ack "<след>" --why "<почему>"')
    # THE OWNER'S DEBT (owner, 2026-08-24): answers only he can bring and does not have yet.
    # Not a brake by itself — the navigator goes on below; but what STANDS on them is said
    # first, and under autonomy the rule is the opposite of a borrowed word: this knowledge
    # is not the agent's to guess.
    owe_lines = owe.lines(root, task, full=True)
    if owe_lines:
        for l in owe_lines:
            print(l)
        if any(owe._stands(root, task, it) for it in owe.open_items(root, task)):
            print("      стоим — делай то, что не держится этим ответом; если держится всё — "
                  'остановись честно: el halt "жду ответа владельца #n"')
        if auto_on:
            print("      автономия: ЭТОТ ответ занять нельзя — знание не у агента (кто подписывает, "
                  "кто третий, чего он хочет); работай вокруг, необходимое без ответа — el halt")
    # THE BATON. When a node waits for the owner, whose move it is comes first — before any
    # navigation: the agent does not drive on while the phone is in his hands (2026-08-22).
    for w_n in waiting_nodes(tdir):
        print(f"ЭСТАФЕТА У ВЛАДЕЛЬЦА  {w_n['id']} · "
              f"{w_n.get('waiting_note') or w_n.get('name','')}")
        print("         агент не управляет устройством и не ходит по экранам этого сценария — ждём его слово;")
        print(f'         запиши дословно: el accept "<его слова>" --for node:{w_n["id"].lower()}'
              "  ·  принял и закрываем: --close")
        if auto_on:
            print(f'         автономия: его нет — реши в его место: el accept "<что принимаешь>" --for node:'
                  f'{w_n["id"].lower()} --assumed "<почему>" · необратимое без гранта — el halt')

    # THE NAVIGATOR. On context the answer is not "what is missing" but four things at once:
    # which step, what it wants, WHO the answer comes from, and whether to stop and show.
    move = NEXT_MOVE.get(phase, "undefined")
    if phase == "context":
        step = context_step(tdir)
        cov = area_coverage(tdir)
        # The saturation step is gone (owner, 2026-08-21): the END OF QUESTIONING is the
        # human's word, recorded as the last Q/A pair — not the agent's note about its own
        # feelings. The expiry problem died with the file: a word said later simply becomes
        # a later pair.
        blank = [a for a in AREA_KEYS if not cov[a]]
        src_of = dict((k, v) for k, _d, v in QA_AREAS)
        # A tick means "this is DONE", not "a file with this name exists". Scope is the one
        # step where the two can differ: the file appears with the first dimension answered
        # and would show ✓ over a boundary drawn on two sides out of six.
        def _tick(k, rel):
            if k == "scope" and os.path.exists(os.path.join(tdir, rel)):
                return "✓" if len(scope_done(tdir)) == len(SCOPE_KEYS) else "▶"
            return "✓" if os.path.exists(os.path.join(tdir, rel)) else \
                   ("▶" if step and step[0] == k else "·")
        ladder = " → ".join(_tick(k, rel) + title for k, rel, title, *_x in CONTEXT_STEPS)
        print(f"лестница {wrap(ladder, indent='         ')}")
        print(f"режим    {wrap(PHASE_MODE['context'], indent='         ')}")
        if step:
            key, rel, title, src, do, cmd = step
            who = {"owner": "У ВЛАДЕЛЬЦА — это живёт только у него в голове, спроси"
                            + (' · автономия: его нет — предположи самое узкое и пометь: '
                               '… --assumed "<почему>"' if auto_on else ""),
                   "agent": "САМ, прибором — код, база, устройство, логи, веб",
                   "both": "начни сам, спроси только остаток",
                   "auto": "пишется автоматически при заведении задачи"}[src]
            print(f"шаг      {title}  →  {rel}")
            print(f"берётся  {who}")
            print(f"как      {wrap(do, indent='         ')}")
            if cmd:
                print(f"команда  {cmd}")
            if key == "scope":
                sdone = scope_done(tdir)
                sleft = [k for k in SCOPE_KEYS if k not in sdone]
                print(f"измерения закрыто {len(sdone)}/6" +
                      (f" · пусто: {', '.join(sleft)}" if sleft else ""))
            if key in ("questions", "scope"):
                if blank:
                    ask = [a for a in blank if src_of[a] == "owner"]
                    self_ = [a for a in blank if src_of[a] != "owner"]
                    print(f"пусто    {', '.join(blank)}")
                    if ask:
                        print(f"  спроси {', '.join(ask)}")
                    if self_:
                        print(f"  добудь {', '.join(self_)}")
                else:
                    print("покрытие все области закрыты хотя бы одной парой")
            move = f"закрой шаг «{title}» — дальше el next покажет следующий"
        else:
            move = 'всё собрано и утверждено; дальше: el forward --why "<что установлено>"'

    elif phase == "plan":
        nodes = nodes_all(tdir)
        if not nodes:
            print("узлов  нет ни одного — план начинается с этапов верхнего уровня")
            move = ('el plan new s1 "<этап>"  ·  этапов обычно 3-7, '
                    "и разворачиваем вниз ТОЛЬКО заполненный узел")
        else:
            holes = [n for n in nodes if node_gaps(n, mode)]
            for n in nodes:
                g = node_gaps(n, mode)
                print(f"узел     {'▶' if g else '✓'} {n['id']} · {n.get('name','')} "
                      f"[{n.get('level','?')}]{'  пусто: ' + ', '.join(g) if g else ''}")
            for l in drift_lines(tdir, indent="план.md  "):
                print(l)
            dr = plan_drift(tdir) or {}
            if holes:
                nid = holes[0]["id"]
                move = f'заполни {nid}: el plan {nid.lower()} — покажет, каких полей нет'
            elif dr.get("missing") or dr.get("cycle"):
                move = ("дерево само с собой не сходится (deps на несуществующий узел или цикл) "
                        "— поправь deps или заведи узлы: см. РАСХОЖДЕНИЕ выше")
            elif not os.path.exists(os.path.join(tdir, "acceptance.md")):
                move = 'покажи план владельцу (el plan) и запиши его «да»: el accept "<слова>"'
            else:
                move = 'план принят; дальше: el forward --why "<что решено>"'
        print("правило  на плане — ЭТАПЫ: крупность разумная (обычно 3–7); первый содержит первичную "
              "подготовку (что есть, чего нет), последний — итоговую проверку; имена — любые. "
              "Пакеты работ — при старте этапа на исполнении; крупная задача — можно и здесь")
        print("правило  владельцу показать нарезку на этапы с пометкой: каждый этап будет разложен на "
              "пакеты при старте — его «да» над планом (el accept --for plan) это слово над нарезкой")
        print("правило  план раньше работы: узел заводится, когда работа стала видна, а не когда сделана — "
              "бумаги задним числом видны по штампам (узел моложе своих следов)")
        print("правило  разворачиваем ТОЛЬКО текущий уровень: этап → его пакеты работ → их "
              "задачи → подзадачи. Разложить всё вперёд — это то, что убило v1 (§5)")

    elif phase == "execute":
        # THE LIVE BOARD (owner, 2026-08-22): EXECUTE used to say «artifacts/ and evidence/
        # are not empty» and nothing about the plan. Now it answers: which node is in work,
        # how far it is, what it still owes, whose move it is.
        nodes_e = sorted(nodes_all(tdir), key=lambda x: x["id"])
        act = active_node(tdir)
        left_e = [n for n in nodes_e if node_open(n)]
        done_e = [n for n in nodes_e if node_status(n) == "done"]
        wait_e = [n for n in nodes_e if node_status(n) == "waiting"]
        _vn, verd_e, _o, _f, _d, _u = validation_state(tdir)
        print(f"узлы     закрыто {len(done_e)}/{len(nodes_e)} · открыто {len(left_e)}"
              + (f" · ждут владельца {len(wait_e)}" if wait_e else "")
              + " · " + " ".join(f"{STATUS_MARK.get(node_status(n), '·')}{n['id']}" for n in nodes_e))
        if act and node_status(act) == "waiting":
            move = (f'запиши его слово: el accept "<его слова>" --for node:{act["id"].lower()}'
                    " (принял и закрываем: --close)")
        elif act:
            node_board(root, task, tdir, act, verd_e)
            print(f"ход      {last_line(root, task, act['id'])}")
            move = (f"веди {act['id']}: пиши el log по ходу (ложится к узлу); проверяй критерии ПО ХОДУ — el validate {act['id'].lower()} "
                    f"<N> --met \"…\" --evidence <файл>; клади следы --node {act['id'].lower()}; "
                    f"показал — el plan wait {act['id'].lower()} \"…\"; готово — el plan done "
                    f"{act['id'].lower()} \"<наблюдаемый результат>\"")
        elif left_e:
            # BY THE GRAPH, not by id (feedback pool, 2026-08-24: «start WP1» after WP3 was
            # closed): the next node is an open leaf whose prerequisites are closed, and
            # the board says who waits for whom, so the priority is visible, not implied.
            from .plan import ready_line, ready_nodes
            ready_e, blocked_e = ready_nodes(tdir)
            if ready_e or blocked_e:
                print("граф     " + (f"готовы: {', '.join(n['id'] for n in ready_e[:6])}"
                                    if ready_e else "готовых нет")
                      + ("" if not blocked_e else " · ждут: " + "; ".join(
                          f"{k} ← {', '.join(v)}" for k, v in list(blocked_e.items())[:5])))
            gaps_f = node_gaps(ready_e[0], mode) if ready_e else []
            move = ("в работе никого — " + ready_line(tdir, root, task)
                    + (f" (сначала заполни: {', '.join(gaps_f)})" if gaps_f else ""))
        elif not nodes_e:
            move = ('плана нет — узлы заводятся на плане: el phase plan --why "…" · '
                    'el plan new s1 "<этап>"')
        else:
            move = 'все узлы закрыты — проверь следы и дальше: el forward --why "<что исполнено и чем доказано>"'
        print("правило  ЭТАП РАСКЛАДЫВАЕТСЯ ПЕРЕД СТАРТОМ: пакеты работ → работы → подзадачи, только "
              "ближайший уровень; раскладку показать владельцу и записать его слово над этапом "
              '(el accept "…" --for stage:<id>) — стартуют пакеты, не этап; в light — предупреждение')
        print("правило  СНАЧАЛА УЗЕЛ, ПОТОМ РАБОТА: узел заводится и стартует до первого шага, не после — "
              "бумаги задним числом видны по штампам (узел моложе своих следов, вердикты пачкой)")
        print("         дальше узел за узлом: start → делать и писать el log (ложится к узлу) → критерии по ходу, "
              "не пачкой в конце → следы к узлу → остановка (wait) → done; крупный этап перед работой "
              "раскладывается на работы")

    elif phase == "think":
        step = think_step(tdir)
        forks = forks_read(tdir)
        # The step the navigator stands on is ▶ even when its file exists — the decision file
        # appears with the first fork and the step is done only when every fork is decided.
        ladder = " → ".join(("▶" if step and step[0] == k else
                             ("✓" if os.path.exists(os.path.join(tdir, rel)) else "·")) + title
                            for k, rel, title, *_x in THINK_STEPS)
        print(f"лестница {wrap(ladder, indent='         ')}")
        print(f"режим    {wrap(PHASE_MODE['think'], indent='         ')}")
        # WHAT THE PREVIOUS PHASE PARKED HERE. Context records what sits next to the boundary
        # and is not done — and whether anything is worth PULLING INSIDE; that decision is
        # taken here, with the human. An artifact nobody re-opens is an artifact nobody
        # reads, so it is carried forward.
        bs = os.path.join(tdir, CONTEXT_FILES["beyond"])
        if os.path.exists(bs):
            head = [l.strip() for l in open(bs, encoding="utf-8")
                    if l.strip() and not l.startswith("#")][:1]
            print("из контекста  за рамкой лежит близкое — втягивать ли, решается ЗДЕСЬ, с человеком:")
            print(f"         {wrap(head[0] if head else 'см. context/beyond-scope.md', indent='         ')}")
        if forks:
            for f in forks:
                mark = "✓" if f["decision"] else "▶"
                print(f"развилка {mark} {f['id']} · {f['q']}  [{f['who']}]  "
                      f"{len(f['options'])} вар.{'' if f['decision'] else '  ← ОТКРЫТА'}")
        if step:
            key, rel, title, src, do, cmd = step
            who = {"owner": "У ВЛАДЕЛЬЦА — выбор направления его, а не твой",
                   "agent": "САМ — это твоя работа думания",
                   "both": "начни сам, спроси остаток"}[src]
            print(f"шаг      {title}  →  {rel}")
            print(f"берётся  {who}")
            print(f"как      {wrap(do, indent='         ')}")
            if cmd:
                print(f"команда  {cmd}")
            move = f"закрой шаг «{title}»"
        else:
            open_forks = [f["id"] for f in forks if not f["decision"]]
            move = (f"развилки без выбора: {', '.join(open_forks)} — закрой их"
                    if open_forks else
                    'думание закрыто; дальше: el forward --why "<что решено и чем обосновано>"')

    print(f"next     {wrap(move)}")
    # PARKED WORK surfaces when its phase arrives — BELOW the move and without a command
    # (feedback 2026-08-25: «отложено … → el todo --done» stood first with a ready command,
    # and the agent went to Jira instead of the active node). A promise kept when its time
    # comes, not the next move; a reminder (⟳) is not even a step.
    parked = [it for it in todo_items(tdir) if it["open"] and it["phase"] == phase]
    if parked:
        for it in parked:
            print(f"на потом {wrap(todo_line(it, width=72), indent='         ')}")
        print("         это не ход — обещание к этой фазе; закрыть, когда сделано: "
              "el todo --done N \"<чем доказано>\"")
    # --short: the move and the commands, without the teaching prose. On the first call of a
    # session the «why» and the «how» are what an agent needs; on the third they are noise it
    # scrolls past (agent retro, 2026-08-23).
    short = bool(getattr(args, "short", False))
    if spec.get("how") and not short:
        print(f"how      {wrap(spec['how'])}")
    for c in spec.get("cmds", []):
        print(f"cmd      {c}")
    if not short:
        print("короче   el next --short — только шаг и команды, без объяснений")
    req_missing = [r for r, _, req in missing if req]
    # HARD on the owner's word, soft on everything else. --waive can excuse a trace the agent
    # judged unnecessary; it cannot excuse the human. Condition 3 of the gate exists precisely
    # because it is the one thing an agent must not be able to grant itself (§4).
    if phase == "context" and not os.path.exists(os.path.join(tdir, CONTEXT_FILES["approval"])):
        print("gate     ЗАКРЫТ НАГЛУХО — нет слова владельца. Предъяви ему собранное "
              "содержимым (el context), потом: el accept \"<его слова дословно>\"")
        if auto_on:
            print('         автономия: его нет — реши в его место над картиной: el accept "<что принимаешь '
                  'за его да>" --assumed "<почему>" (он прочтёт, вернувшись)')
        if req_missing:
            print(f"         и ещё {len(req_missing)} след(а) не написано")
    elif pend:
        print(f"gate     ЗАКРЫТ — поправки без его слова: {pending_line(pend)}")
        print('         предъяви · услышь · запиши: el accept "<его слова>"  ·  либо осознанно: '
              'el forward --waive "<почему без его слова>"')
    elif phase == "think" and [f for f in forks_read(tdir) if not f["decision"]]:
        left = [f for f in forks_read(tdir) if not f["decision"]]
        owner_left = [f["id"] for f in left if f["who"] == "owner"]
        print(f"gate     ЗАКРЫТ — развилок без выбора: {len(left)}")
        if owner_left:
            print(f"         из них решает ВЛАДЕЛЕЦ: {', '.join(owner_left)} — "
                  "предъяви ему варианты с ценой и запиши его слова")
            if auto_on:
                print('         автономия: его нет — реши в его место: el think decide <id> "<вариант>" '
                      '--assumed "<почему>" --undo "<как откатить>"; предпочти обратимый путь')
        print('         el think forks — состояние · el think decide <id> "<вариант>"')
    elif phase in ("execute", "validate") and [n for n in nodes_all(tdir) if node_open(n)]:
        left_g = [n for n in nodes_all(tdir) if node_open(n)]
        wl_g = worklog(root, task)
        print("gate     ЗАКРЫТ — узлы плана не закрыты: " + ", ".join(
            f"{n['id']} ({STATUS_RU.get(node_status(n), '?')}"
            + (f", следов {len(wl_g.get(n['id'], []))}" if node_status(n) == "active" else "") + ")"
            for n in left_g))
        print('         закрыть: el plan done <узел> "<результат>" · отложить осознанно: '
              'el plan park <узел> --why "…"')
    elif req_missing:
        print(f"gate     CLOSED — {len(req_missing)} required trace(s) missing; "
              f'deliberate skip: el forward --waive "<why>"')
    elif phase == "validate" and any(validation_state(tdir)[i] for i in (2, 3, 5)):
        # `next` and `forward` must answer the same question the same way. Reporting the gate
        # open and then refusing the move is worse than saying nothing: the navigator becomes
        # something you check against reality instead of relying on. Caught the moment the
        # criteria gate appeared — the owner ran `el next` and it said open (2026-08-20).
        # Declined criteria (index 4) are NOT a block — `forward` lets them through with a
        # note; counting them here printed «без вердикта: 0» over an open gate (2026-08-21).
        _n, _v, open_n, failed_n, _d, unver_n = validation_state(tdir)
        print(f"gate     ЗАКРЫТ — критериев без вердикта: {open_n}" +
              (f" · НЕ сошлось: {failed_n}" if failed_n else "") +
              (f" · не проверено: {unver_n}" if unver_n else ""))
        print("         сверка с тем, что обещал план:  el validate")
    elif phase == "validate" and not word_given_on(root, task, "validate"):
        print("gate     ЗАКРЫТ — приёмки нет: слово человека над результатом на этой фазе не записано")
        print('         покажи так, чтобы можно было потрогать · услышь · запиши: el accept "<его слова>"')
    else:
        print('gate     open — el forward --why "<what is closed and what proves it>"')
    return 0


def cmd_resume(args):
    """ONE CARD TO COME BACK ON (feedback 2026-08-26 → owner: «есть проект, мне нужно
    продолжить работать — это и есть el resume»). Not a new source of truth: every line is
    what another command already answers — the sheet, autonomy, the owner's debt, the baton,
    the node in work, the three states of checking, contradictions, the gate, and THE one
    move `el next` gives — gathered on one screen, so a returning agent (or a fresh chat
    given the page's «карточка для агента») starts here and not from the whole picture.
    Closed by the rule of the return: with a grant — report in a line and go; without —
    report and ask; on the owner's debt — work around it, never guess it."""
    root = find_root()
    if not root:
        print("elephant  off — хранилища здесь нет")
        print('start     el boot "<задача>" --id <имя> --raw "<его слова о задаче>"')
        return 0
    want = getattr(args, "task", None)
    task = resolve_task(root, want) if want else current_task(root)
    if want and not task:
        print(f"нет задачи {want}", file=sys.stderr)
        print(f"hint     известны: {', '.join(tasks_of(root)) or '—'} · el projects", file=sys.stderr)
        return 1
    if not task:
        live = open_tasks(root)
        print(f"в руке    ничего (idle) · открытых {len(live)}")
        for t in live[:6]:
            m = task_meta(root, t)
            print(f"          {t} · {phase_no(m.get('phase', 'context'))}/8 {m.get('phase', 'context')}"
                  f" · {(m.get('name') or '')[:50]}")
        print("взять     el use <id> — и снова el resume" if live else
              'новая     el boot "<задача>" --id <имя> --raw "<его слова о задаче>"')
        return 0
    tdir = os.path.join(root, task)
    meta = task_meta(root, task)
    ph = meta.get("phase", "context")
    st = meta.get("status", "active")
    print(f"RESUME    {task}")
    print(f"          {(meta.get('name') or '')[:80]}")
    if st != "active":
        print(f"исход     {st.upper()} · закрыта {str(meta.get('closed_at', '?'))[:10]}")
        print(f"читать    el context --task {task} · el progress --task {task} · снова открыть: "
              f'el reopen {task} --why "…"')
        return 0
    try:
        from .views import phase_reached
        reached = phase_reached(tdir, meta)
    except Exception:
        reached = ph
    drift = f" · по следам {phase_no(reached)}/8 {reached}" if reached != ph else ""
    _state, human = task_state(tdir)
    print(f"фаза      {phase_no(ph)}/8 {ph}{drift} · mode {meta.get('mode', 'soft')} · {human}")
    # THE SHEET, whole — it is bounded for exactly this reading.
    b = brief_read(tdir)
    if b:
        print(f"листок    переписан {brief_when(tdir)} — читать первым:")
        for bl in b.splitlines():
            print(f"          {bl}")
        bs = autonomy.brief_stale_line(root, task, indent="          ")
        if bs:
            print(bs)
    else:
        print('листок    нет — вернувшийся агент начнёт с нуля; заведи: el brief "<baseline · замер · '
              'лучшее · не повторять · сейчас · следующая команда>"')
    for l in return_lines(root, task):
        print(l)
    for l in stale_lines(root, task, tdir):
        print(l)
    auto = autonomy.state(root, task)
    for l in autonomy.lines(root, task):
        print(l)
    for l in owe.lines(root, task):
        print(l)
    for w_n in waiting_nodes(tdir):
        print(f"эстафета  у владельца — {w_n['id']} · {w_n.get('waiting_note') or w_n.get('name', '')} "
              f'· его слово: el accept "…" --for node:{w_n["id"].lower()}')
    act = active_node(tdir)
    if act and node_status(act) == "active":
        print(f"узел      {act['id']} · {act.get('name', '')[:50]} · в работе"
              + (f" с {human_when(act['started_at'])}" if act.get("started_at") else ""))
        print(f"следы     {last_line(root, task, act['id'])}")
    pend = pending_word(root, task)
    if pend:
        print(f"поправки  без его слова: {pending_line(pend)} — предъяви и запиши ответ: el accept")
    vs = validation_split(tdir)
    if vs["nodes"]["total"] or vs["owner"]["total"]:
        print("проверка  " + check_line(vs, word_given_on(root, task, "validate")))
    # CONTRADICTIONS — the doctor's count, so a lying state is caught before the first move.
    from .commands import cmd_doctor
    buf_d = io.StringIO()
    with contextlib.redirect_stdout(buf_d), contextlib.redirect_stderr(io.StringIO()):
        cmd_doctor(argparse.Namespace(task=task))
    n_err = sum(1 for l in buf_d.getvalue().splitlines() if l.strip().startswith("ERROR"))
    n_warn = sum(1 for l in buf_d.getvalue().splitlines() if l.strip().startswith("WARN"))
    if n_err or n_warn:
        print(f"сверка    противоречий {n_err} · предупреждений {n_warn} — el doctor")
    g_open, g_why = gate_verdict(root, task, tdir, ph)
    print("gate      " + ('открыт — el forward --why "…"' if g_open else f"закрыт — {g_why}"))
    # THE ONE MOVE — the same answer `el next` gives, taken from it, not recomputed.
    buf_n = io.StringIO()
    with contextlib.redirect_stdout(buf_n), contextlib.redirect_stderr(io.StringIO()):
        cmd_next(argparse.Namespace(task=task, short=True))
    lines_n = buf_n.getvalue().splitlines()
    move = []
    for i, l in enumerate(lines_n):
        if l.startswith("next     "):
            move.append("next      " + l[9:])
            for c in lines_n[i + 1:]:
                if c.startswith("         "):
                    move.append(" " + c)
                else:
                    break
            break
    for l in move or ["next      ход не определён — el next"]:
        print(l)
    # THE RULE OF THE RETURN — what the state allows before anything is written.
    if auto and auto["halt"]:
        rule = "стоп стоит — дальше без человека нельзя: доложи и жди его слова"
    elif auto and auto["active"]:
        rule = ("грант стоит — доложи одной строкой и продолжай; недостающее слово решай в его место и "
                "помечай (--assumed), ответ владельца (за тобой) не решается за него, необратимое — el halt; "
                "дошёл до условия или срока — el grant end")
    else:
        rule = ("гранта нет — доложи человеку (где мы · что дальше · что за ним) и спроси, приступать ли; "
                "до его слова только чтение: ни записи, ни el forward")
    if pend:
        rule = "картина правилась после его слова — сначала предъяви поправки; " + rule
    if n_err:
        rule = "состояние противоречиво — сначала el doctor и сверка; " + rule
    print(f"правило   {wrap(rule, indent='          ')}")
    print("дальше    el next — ход подробно · el context --section <раздел> — один раздел · "
          "el context — вся картина, только если вопрос в ней")
    return 0


def gate_verdict(root, task, tdir, phase):
    """(open, reason) — THE SAME answer the gate gives in `el next` and `el forward`, in one
    line, for the places that only have room for one: the projects list and status.
    Feedback 2026-08-25 (Copilot): `el projects` said «готова к переходу» from the trace
    checklist alone while `el next` refused with open nodes — two answers to one question.
    The checklist is one door of the gate, not the gate. Mirrors cmd_next's chain; the
    differential test keeps them equal."""
    have, missing = phase_state(tdir, phase)
    req_missing = [r for r, _w, req in missing if req]
    if phase == "context" and not os.path.exists(os.path.join(tdir, CONTEXT_FILES["approval"])):
        return False, "нет слова владельца"
    pend = pending_word(root, task)
    if pend:
        return False, "поправки без его слова"
    if phase == "think":
        left = [f for f in forks_read(tdir) if not f["decision"]]
        if left:
            return False, f"развилок без выбора: {len(left)}"
    if phase in ("execute", "validate"):
        left_n = [n for n in nodes_all(tdir) if node_open(n)]
        if left_n:
            return False, "узлы не закрыты: " + ", ".join(n["id"] for n in left_n[:4]) + \
                          (" …" if len(left_n) > 4 else "")
    if req_missing:
        return False, f"следов не хватает: {len(req_missing)}"
    if phase == "validate":
        _n, _v, open_n, failed_n, _d, unver_n = validation_state(tdir)
        if open_n or failed_n or unver_n:
            return False, f"критериев без вердикта: {open_n + failed_n + unver_n}"
        if not word_given_on(root, task, "validate"):
            return False, "приёмки нет"
    return True, ""


def gate_doors(phase):
    """The four answers of a gate, printed when one refuses (owner, 2026-08-24).

    A refusal that names only «доделай» hides three other legal moves, and an agent that
    sees one door either forces it or stalls."""
    return ["", "у ворот четыре ответа, а не один:",
            "  доделать и пройти   — то, что просит гейт выше",
            f'  вернуться назад     — el back <фаза> --why "<что выяснилось>" '
            f"(нашли новое · план не сходится)",
            '  заморозить          — el done "<где встали>" --as blocked --why "<чего ждём>"',
            '  закрыть             — el done "<что вышло>" --as closed --why "<почему здесь>"']


def cmd_forward(args):
    """One phase forward, and only with a stated reason.

    Skipping is refused: declaring yourself at execute while sitting in context is the
    formal-checkbox pattern that killed V2 (§15). The gate is soft (§10): the CLI does not
    judge the MEANING of the reason, it requires that a reason exists and lands in the
    journal. Moving without proof is legal, but it is recorded as `waived`, so "skipped"
    and "deliberately skipped" never look the same."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, args.task)
    if not task:
        return 1
    tdir_f = os.path.join(root, task)
    phase_f = task_meta(root, task).get("phase", "context")
    mode_f = task_meta(root, task).get("mode", "soft")
    # STRICT knows no --waive (owner, 2026-08-22: «везде проверяется каждая часть»): every
    # required trace is either there or the phase is not left. Soft and light keep the
    # recorded skip.
    if mode_f == "strict" and getattr(args, "waive", None):
        print("СТРОГО — в режиме strict --waive не принимается: допиши след или смени режим "
              "осознанно (el mode soft --why \"…\")", file=sys.stderr)
        return 1
    # The word over the picture is re-asked when the picture changed after it (amend.py):
    # soft — --waive passes, but says so in the journal.
    pend = pending_word(root, task)
    if pend and not getattr(args, "waive", None):
        print(f"НЕ ПУЩУ — картина правилась после его слова: {pending_line(pend)}", file=sys.stderr)
        for e in pend:
            print(f"  п{e.get('n', '?')} · {e.get('part', '?')} · {e.get('phase', '?')} · "
                  f"{str(e.get('why', ''))[:90]}", file=sys.stderr)
        print('  предъяви поправки, услышь ответ, запиши: el accept "<его слова>"', file=sys.stderr)
        print('  либо осознанно: el forward --waive "<почему идём без его слова>"', file=sys.stderr)
        return 1
    # CONDITION 3 OF THE GATE, AND IT DOES NOT BEND (§4). --waive can excuse a trace the agent
    # judged unnecessary; it cannot excuse the human, because the whole point of the condition
    # is that it is the one thing an agent must not be able to grant itself. Soft everywhere
    # else, hard here — the owner's call, 2026-08-19: "gate soft можно убрать и оставить hard".
    # THE OWNER'S DEBT tied to THIS gate (owner, 2026-08-24: «когда доходим — говорим, мы
    # заблокированы»). A debt tied to a node holds the node, not the phase; only one tied to
    # `phase:<this phase>` stands here. --waive passes, out loud, as everywhere.
    held_ph = owe.holding(root, task, f"phase:{phase_f}")
    if held_ph and not getattr(args, "waive", None):
        print(f"НЕ ПУЩУ — выход из {phase_f} держит долг владельца: ответ есть только у него, "
              "и его пока нет.", file=sys.stderr)
        for it in held_ph:
            print(f"  #{it['n']} {it['kind']} · {it['q'][:80]} · как: {it['how'][:60]}",
                  file=sys.stderr)
        print('  ответ: el owe answer <n> "<его ответ>" · не понадобилось: el owe drop <n> --why "…"',
              file=sys.stderr)
        print('  либо осознанно: el forward --waive "<почему идём без ответа>"', file=sys.stderr)
        for l in gate_doors(phase_f):
            print(l, file=sys.stderr)
        return 1
    if phase_f == "think":
        left = [f for f in forks_read(tdir_f) if not f["decision"]]
        if left:
            print("НЕ ПУЩУ — из думания с открытыми развилками выхода нет.", file=sys.stderr)
            for f in left:
                print(f"  {f['id']} · {f['q']}   [решает: {f['who']}]", file=sys.stderr)
            print('  закрой: el think decide <id> "<вариант>" --words "<его слова>"',
                  file=sys.stderr)
            print("  развилка без выбора уезжает в план догадкой, и на исполнении", file=sys.stderr)
            print("  выясняется, что строили не то, что он имел в виду.", file=sys.stderr)
            return 1
    if phase_f == "plan":
        nodes = nodes_all(tdir_f)
        holes = [n["id"] for n in nodes if node_gaps(n, mode_f)]
        if not nodes:
            print("НЕ ПУЩУ — плана нет: ни одного узла.", file=sys.stderr)
            print('  el plan new s1 "<этап>"', file=sys.stderr)
            return 1
        if holes:
            print(f"НЕ ПУЩУ — узлы с пустыми полями: {', '.join(holes)}", file=sys.stderr)
            print("  девять полей — это контракт узла; пустое поле неотличимо от забытого.",
                  file=sys.stderr)
            print("  поле правда не нужно — напиши в нём «N/A, потому что…», это законно.",
                  file=sys.stderr)
            return 1
        # ROUTE INTEGRITY (his decision 2026-08-24): the roll-up asks «сдержали ли мы то, что
        # обещали»; this asks «а всё ли нужное мы обещали». A piece of the goal covered by
        # nobody is work we are simply not going to do — and it stays invisible to every
        # other check, because what nobody wrote down cannot be verified. Not waivable in
        # spirit but waivable in fact: `--waive` writes the debt into the journal, like
        # everywhere else, because sometimes the human decides a piece is not ours.
        # THE TREE MUST ADD UP (feedback 2026-08-24, then his decision: the network plan is a
        # PROJECTION of the tree): a dep naming no node is a stage promised and never held;
        # a cycle is an order nobody can walk. Both stop the gate; --waive says so aloud.
        dr = plan_drift(tdir_f) or {}
        if (dr.get("missing") or dr.get("cycle")) and not getattr(args, "waive", None):
            print("НЕ ПУЩУ — дерево не сходится само с собой:", file=sys.stderr)
            for l in drift_lines(tdir_f, indent="  "):
                print(l, file=sys.stderr)
            print('  либо осознанно: el forward --waive "<почему>"', file=sys.stderr)
            for d in gate_doors(phase_f):
                print(d, file=sys.stderr)
            return 1
        from .integrity import gaps as integrity_gaps, has_goal
        if has_goal(tdir_f) and not getattr(args, "waive", None):
            holes_g = {k: v for k, v in integrity_gaps(tdir_f).items() if v}
            if holes_g:
                names = {"ifr": "чек-лист приёмки", "part": "крупные части пути"}
                print("НЕ ПУЩУ — маршрут не целостен: за этими кусками цели не стоит никто.",
                      file=sys.stderr)
                for k, items in holes_g.items():
                    for it in items:
                        print(f"    {names[k]} {it['n']}: {it['text'][:66]}", file=sys.stderr)
                print("  план, в котором чего-то не хватает, — это не план: проверка потом "
                      "честно скажет «всё сошлось», потому что считает от нарисованного.",
                      file=sys.stderr)
                print("  завести узел: el plan new … · привязать: el plan cover <узел> ifr <N>",
                      file=sys.stderr)
                print('  не знаем, что там: el plan unfold <узел> "<что должно стать известно>" '
                      "--after <узел> — объявленная дыра тоже покрытие", file=sys.stderr)
                print('  кусок не наш: el forward --waive "<почему не делаем>"', file=sys.stderr)
                for d in gate_doors(phase_f):
                    print(d, file=sys.stderr)
                return 1
        if not os.path.exists(os.path.join(tdir_f, "acceptance.md")):
            print("НЕ ПУЩУ — выход из плана требует ЯВНОГО «да» владельца (§8.5).",
                  file=sys.stderr)
            print("  покажи ему план: el plan", file=sys.stderr)
            print('  запиши его слово: el accept "<что он сказал>"', file=sys.stderr)
            return 1
    if phase_f in ("execute", "validate"):
        # THE GRAPH GATE (owner, 2026-08-22). EXECUTE used to be left when two folders were
        # not empty; the plan's nodes could stay open — and did (S6 of the Settings pilot sat
        # open through validate and reflect). A phase is left when every node is terminal:
        # done, or parked on purpose with a reason. Not waivable — parking IS the honest
        # way out, and it leaves a trace.
        left_nodes = [n for n in nodes_all(tdir_f) if node_open(n)]
        if left_nodes:
            print("НЕ ПУЩУ — узлы плана не закрыты:", file=sys.stderr)
            for n in left_nodes:
                print(f"  {STATUS_MARK.get(node_status(n), '·')} {n['id']:<6} "
                      f"{STATUS_RU.get(node_status(n), '?'):<14} {(n.get('name') or '')[:60]}",
                      file=sys.stderr)
            unf_ids = [n["id"] for n in left_nodes if (n.get("unfold") or "").strip()]
            if unf_ids:
                print(f"  места раскрытия {', '.join(unf_ids)} закрывают не «done», а "
                      "раскрытием: заведи под ними работы — или отложи (park), если решено "
                      "туда не идти", file=sys.stderr)
            print('  закрыть: el plan done <узел> "<наблюдаемый результат>"', file=sys.stderr)
            print('  отложить осознанно: el plan park <узел> --why "<почему не делаем сейчас>"',
                  file=sys.stderr)
            return 1
    if phase_f == "validate":
        # The phase exists to compare the result against what the plan promised. Leaving it with
        # criteria nobody answered is the formal-checkbox pattern one level up: the file exists,
        # the promises were never read back.
        _nodes, _v, open_n, failed_n, decl_n, unver_n = validation_state(tdir_f)

        def _holding(*kinds):
            """WHICH criteria hold the gate, by address — not just how many.

            The refusal used to print only the count, and the agent had to grep journal.jsonl
            to learn WHICH criterion was unverified (feedback pool, 2026-08-23). A gate that
            names the count but hides the address makes the next command a guess."""
            out = []
            _o, info = rollup(tdir_f)
            for nid in _o:
                for i, it in enumerate(info[nid]["items"], 1):
                    if it["status"] in kinds:
                        out.append(f"    {nid}.{i} · {VERDICT_RU.get(it['status'], it['status'])}"
                                   f" · {it['text'][:70]}")
            return out

        if open_n:
            print(f"НЕ ПУЩУ — критериев без вердикта: {open_n}", file=sys.stderr)
            for line in _holding("open"):
                print(line, file=sys.stderr)
            print("  что обещано планом, то и сверяем:  el validate", file=sys.stderr)
            print('  отметить:  el validate <узел> <номер> --met "<чем доказано>"', file=sys.stderr)
            return 1
        if unver_n and not getattr(args, "waive", None):
            # A promise the work still owes an answer to. Three honest ways out and no fourth:
            # check it, decline it because the work behind it is gone, or leave on purpose with
            # --waive, which writes the debt into the journal instead of hiding it. (The hint
            # promised --waive while the check ignored it — fixed 2026-08-21.)
            print(f"НЕ ПУЩУ — критериев не проверено: {unver_n}", file=sys.stderr)
            for line in _holding("unverified"):
                print(line, file=sys.stderr)
            print("  это ДОЛГ: работа есть, проверки нет — не то же самое, что снятый критерий.",
                  file=sys.stderr)
            print("  проверить:  el validate <узел> <номер> --met \"<чем доказано>\"",
                  file=sys.stderr)
            print("  снять, если работа отменена:  --declined \"<почему>\"", file=sys.stderr)
            print('  уйти осознанно:  el forward --waive "<почему уходим с долгом>"',
                  file=sys.stderr)
            return 1
        if decl_n:
            print(f"снято вместе с работой: {decl_n} критериев — остаются видимыми в validation.md")
            args.why = (args.why or "") + f" · снятых критериев: {decl_n}"
        if failed_n and not getattr(args, "waive", None):
            print(f"НЕ ПУЩУ — критериев НЕ сошлось: {failed_n}", file=sys.stderr)
            for line in _holding("failed"):
                print(line, file=sys.stderr)
            print("  либо доделать и переотметить, либо вернуть узел в работу:", file=sys.stderr)
            print("  el reopen <узел>  ·  или осознанно:  el forward --waive \"<почему>\"",
                  file=sys.stderr)
            return 1
        # THE THIRD BIG STOP — acceptance — is a word over the RESULT, said ON this phase. The
        # file acceptance.md is not proof: `el accept` on plan writes the same file, and the
        # plan-time «да» used to pass for acceptance (found on the live test, 2026-08-21; the
        # owner: «требовать»). Hard, like context and plan: --waive does not excuse the human.
        if not word_given_on(root, task, "validate"):
            print("НЕ ПУЩУ — приёмки нет: слово человека над РЕЗУЛЬТАТОМ на этой фазе не записано.",
                  file=sys.stderr)
            print("  слово над планом не считается — это другая остановка.", file=sys.stderr)
            print('  покажи так, чтобы можно было потрогать → услышь → запиши: el accept "<его слова>"',
                  file=sys.stderr)
            print("  --waive это не обходит: приёмку даёт человек, заменить её нечем.", file=sys.stderr)
            for d in gate_doors(phase_f):
                print(d, file=sys.stderr)
            return 1
    if phase_f == "context" and required_in(CONTEXT_MIN["scope"], mode_f) \
            and os.path.exists(os.path.join(tdir_f, CONTEXT_FILES["scope"])) \
            and len(scope_done(tdir_f)) < len(SCOPE_KEYS) and not getattr(args, "waive", None):
        # A boundary drawn on four sides out of six is not a boundary — and the two nobody asked
        # about are exactly where "а я думал, это тоже входит" comes from later.
        miss = [k for k in SCOPE_KEYS if k not in scope_done(tdir_f)]
        print(f"НЕ ПУЩУ — граница отвечена не вся: пусто {', '.join(miss)}", file=sys.stderr)
        print("  вопросы: el context scope", file=sys.stderr)
        print('  ответ:   el context scope <изм> --in "<входит>" --out "<НЕ входит>"',
              file=sys.stderr)
        return 1
    if phase_f == "context" and mode_f != "light" and not getattr(args, "waive", None):
        # Light mode asks for the spine only — the questions, the clarified task, the word;
        # the coverage map is a soft-and-up demand.
        # Moved here from the deleted saturate command (2026-08-21): declaring the gathering
        # finished while an owner-only area was never asked about is not saturation — it is
        # giving up on asking. The gate names the silent areas instead of letting them pass.
        cov_f = area_coverage(tdir_f)
        src_f = dict((k, v) for k, _d, v in QA_AREAS)
        owner_blank = [a for a in AREA_KEYS if not cov_f[a] and src_f[a] == "owner"]
        if owner_blank:
            print(f"НЕ ПУЩУ — owner-области без единого вопроса: {', '.join(owner_blank)}",
                  file=sys.stderr)
            print("  это живёт только у него в голове — спроси, или осознанно:", file=sys.stderr)
            print('  el forward --waive "<почему выходим, не спросив>"', file=sys.stderr)
            return 1
    if phase_f == "context" and not os.path.exists(os.path.join(tdir_f, CONTEXT_FILES["approval"])):
        print("НЕ ПУЩУ — из контекста без слова владельца выхода нет.", file=sys.stderr)
        print("  1. предъяви ему собранное СОДЕРЖИМЫМ:  el context", file=sys.stderr)
        print("  2. услышь его ответ", file=sys.stderr)
        print('  3. запиши дословно:  el accept "<его слова>"', file=sys.stderr)
        print("  --waive это не обходит: он снимает след, который ты счёл ненужным,",
              file=sys.stderr)
        print("  а человека снять нельзя — иначе гейт и есть тот чек-лист,", file=sys.stderr)
        print("  которым спецификация запрещает подменять согласие.", file=sys.stderr)
        return 1
    # THE EXIT VALIDATION, uniform for every phase (owner, 2026-08-21): a phase is left when
    # its required traces EXIST — the CLI counts files (and in places their content: answered
    # pairs, six boundary sides, verdicts), it never judges quality. Context has its own
    # richer block above; every other phase is checked here. Deliberate skipping stays legal
    # and recorded: --waive names why we go without.
    if phase_f != "context" and not args.waive:
        _have, _missing = phase_state(tdir_f, phase_f)
        req = [(rel, what) for rel, what, required in _missing if required]
        if req:
            print(f"gate {phase_f}: CLOSED — следы фазы не на месте", file=sys.stderr)
            for rel, what in req:
                print(f"  missing  {rel} — {what}", file=sys.stderr)
            print("  заполни (el next называет шаг и команду), либо осознанно:", file=sys.stderr)
            print('  el forward --waive "<почему идём без них>"', file=sys.stderr)
            return 1
    cur = task_meta(root, task).get("phase", "context")
    i = PHASES.index(cur) if cur in PHASES else 0
    if i + 1 >= len(PHASES):
        print(f"{cur} is the last phase; a new cycle starts with: el phase context")
        return 0
    nxt = PHASES[i + 1]

    # The context gate is the one with real substance behind it: everything downstream
    # aims at what was gathered here. We check for TRACES, never for quality.
    if cur == "context" and not args.waive:
        tdir = os.path.join(root, task)
        cdir = os.path.join(tdir, "context")
        missing = []
        qs = questions_stat(tdir)
        if qs is None:
            missing.append("context/questions.md — clarifying questions were never recorded")
        elif qs[0] == 0:
            missing.append("context/questions.md — no questions in it")
        elif qs[1] < qs[0]:
            missing.append(f"context/questions.md — {qs[0]} asked, only {qs[1]} answered")
        if not os.path.exists(os.path.join(cdir, "task.clarified.md")):
            missing.append("context/task.clarified.md — the task is still the draft")
        rdir = os.path.join(tdir, "research")
        local = [f for f in (os.listdir(rdir) if os.path.isdir(rdir) else [])
                 if f.endswith(".md")]
        if not local and mode_f != "light":
            missing.append("no research gathered — nothing from code, logs, docs, the web "
                           '(el research <источник> "<находка>" --ref <якорь>)')
        if not os.path.exists(os.path.join(cdir, "summary.md")) \
                and required_in(CONTEXT_MIN["summary"], mode_f):
            missing.append("context/summary.md — gathered material is not folded into one read")
        if missing:
            print(f"gate {cur} → {nxt}: CLOSED", file=sys.stderr)
            for m in missing:
                print(f"  missing  {m}", file=sys.stderr)
            print('  waive it deliberately: el forward --waive "<why we go without it>"',
                  file=sys.stderr)
            return 1

    reason = args.why or args.waive
    if not reason:
        print(f"gate {cur} → {nxt}: CLOSED — no reason given for the move\n"
              f'  el forward --why "<what is closed and what proves it>"\n'
              f'  el forward --waive "<why we move without proof>"', file=sys.stderr)
        return 1
    # The event IS the transition — the derived card reads the phase back from it.
    journal(root, task, "advance", f"{cur} → {nxt}",
            {"why": reason, "gate": "waived" if args.waive else "open"})
    print(f"gate {cur} → {nxt}: {'WAIVED' if args.waive else 'open'} · {reason}")
    print(f"next      el next — what {nxt} needs")
    # The dose at the door: the new phase's declaration and its beats, here and now —
    # the agent reads the contract of the place where it stands, not from memory.
    print(phase_brief(nxt, task_mode(os.path.join(root, task))))
    return 0


def cmd_phase(args):
    """ВОЗВРАТ — один из четырёх законных ответов ворот (his decision 2026-08-24).

    In stage-gate practice a gate has four answers, not two: go · recycle (back for rework) ·
    hold · kill. Elephant had only «пущу» and «НЕ ПУЩУ»: going back existed technically but
    was described nowhere as a DECISION — no reason, no trace, no standing. So it read as a
    failure, and an agent would rather drive on than turn around.

    His picture: a jam on the road. The driver decides — turn around and go home (kill),
    take the long detour (recycle: same goal, other route), wait it out (hold), or go
    somewhere else entirely (a new goal, and that needs his word). All four are normal.

    Hence: back is a first-class move, and it costs a REASON — because a return nobody
    explained is indistinguishable from wandering."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, args.task)
    if not task:
        return 1
    name = args.name.lower()
    if name not in PHASES:
        print(f"phase must be one of: {', '.join(PHASES)}", file=sys.stderr)
        return 1
    was = task_meta(root, task).get("phase", "context")
    i_was, i_new = PHASES.index(was) if was in PHASES else 0, PHASES.index(name)
    if i_new > i_was:
        print(f'forward moves one phase at a time and needs a reason: el forward --why "..."\n'
              f"  now {was} ({i_was + 1}/8), requested {name} ({i_new + 1}/8)", file=sys.stderr)
        return 1
    if i_new < i_was:
        why = (getattr(args, "why", None) or "").strip()
        if not why:
            print("возврат — это решение, и оно стоит причины:", file=sys.stderr)
            print(f'  el back {name} --why "<что выяснилось и что идём менять>"',
                  file=sys.stderr)
            print("  вернуться назад — законный ход (нашли новое, план не сходится, "
                  "цель сдвинулась);", file=sys.stderr)
            print("  но возврат без причины через месяц неотличим от блуждания.",
                  file=sys.stderr)
            return 1
        journal(root, task, "reroute", f"{was} → {name}", {"why": why, "from": was})
        print(f"возврат ↩ {was} → {name} · {why[:70]}")
        print("вернуться вперёд, когда поправишь: el forward --why \"<что изменилось>\"")
        print(phase_brief(name, task_mode(os.path.join(root, task))))
    else:
        print(f"phase unchanged: {name}")
    return 0


def cmd_where(_args):
    """ABSOLUTE paths for everything the current phase needs.

    `el next` names its traces relatively — `context/scope.md` — against a root it never
    prints, and a relative path is not something a caller can write into. This is the command
    that was missing: it turns the checklist into places on disk."""
    root = require_root()
    if not root:
        return 1
    task = current_task(root)
    print(f"project   {project_root(root)}")
    print(f"elephant  {root}")
    if not task:
        if open_tasks(root):
            print("task      —  в руке ничего (idle): el use <id> берёт · el projects — список")
        else:
            print('task      —  create one: el new "<description>" --id <name>')
        return 0
    tdir = os.path.join(root, task)
    meta = task_meta(root, task)
    phase = meta.get("phase", "context")
    print(f"task      {tdir}")
    print(f"phase     {phase_no(phase)}/8 {phase}")
    print(f"journal   {os.path.join(tdir, 'journal.jsonl')}   ← правда проекта: события, "
          f"переходы, исход; карточка выводится из него")
    print(f"request   {os.path.join(tdir, 'init', 'request.md')}")
    print(f"goal      {os.path.join(tdir, 'context', 'task.clarified.md')}   ← задача его словами "
          f"(+ поправки) · инженерно: thinking/crystal.md")
    have, missing = phase_state(tdir, phase)
    print("traces    of this phase — write the missing ones at these paths")
    for rel, _what, required in have + missing:
        ok = "✓" if (rel, _what, required) in have else "✗"
        tag = "" if required else "   (optional)"
        print(f"  {ok} {os.path.join(tdir, rel)}{tag}")
    print("next      el next — the move · el context — what is gathered")
    return 0
