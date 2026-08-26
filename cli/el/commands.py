"""Bookkeeping and lifecycle — the general commands that WRITE.

init · new · boot (stage 0) · use · log · beat · artifact / evidence · accept · todo ·
spawn · reopen · done · lesson · ui · feedback (the tool's own inbox), and the two screens
that teach: blueprint (the whole contract) and onboard (bare `el`).
"""
import argparse, json, os, re, shutil, sys
from .protocol import BRIEF_CHARS, BRIEF_LINES, CONTEXT_FILES, MODE_RU, MODES, OUTCOMES, PHASES
from .navigate import return_lines
from .worklog import stale_lines
from .state import SKILL_ROOT
from . import autonomy, owe
from .blueprint import PARTS, render, resolve_part
from .state import (MARKER, RESERVED_EVENTS, STORAGE_DIR, brief_path, brief_read, brief_when, current_task, feedback_dir,
                    todo_items, todo_line,
                    feedback_ids, feedback_looks_like_id, feedback_resolve, find_root, fm_read, fm_write, git_dirty,
                    hold, id_words_dropped, journal, lessons_path, lessons_read, mark_render, norm_id, now_iso,
                    request_line, similar_tasks,
                    open_tasks, phase_no, pick_task, project_root, require_root, resolve_task,
                    task_meta, tasks_of, touch, write)
from .term import emit, wrap
from .views import render_views
from .navigate import ctx_line
from .amend import pending_line, pending_word
from .plan import (STATUS_RU, active_node, node_open, node_read, node_resume, node_status,
                   nodes_all, path_to_id, plan_done)
from .validate import criteria_of, validation_state
from .views import skill_html


def cmd_init(args):
    root = os.path.abspath(args.dir) if args.dir else os.path.join(project_root(), STORAGE_DIR)
    if os.path.isfile(os.path.join(root, MARKER)):
        print(f"already set up: {root}")
        return 0
    os.makedirs(root, exist_ok=True)
    open(os.path.join(root, MARKER), "a", encoding="utf-8").close()
    mark_render(root)
    print(f"created: {root}")
    return 0


def cmd_new(args):
    root = require_root()
    if not root:
        return 1
    desc = args.description.strip()
    if not args.id:
        print("a short id is required — the CLI does not invent names.", file=sys.stderr)
        print('hint     el new "<description>" --id <name>', file=sys.stderr)
        print("         up to FIVE English words: harvest-dislikes-and-dataset, stt-ensemble-variants",
              file=sys.stderr)
        print("         the date is prepended automatically: 2026-08-20-harvest",
              file=sys.stderr)
        print("         the full description goes in the text, the id is what you call it by",
              file=sys.stderr)
        return 1
    # Date first: tasks sort chronologically in the folder and in `el projects`, and a name
    # alone stops being enough once there are two of the same kind. (Owner, 2026-08-18.)
    # The date is a PREFIX, not part of the name — the name itself stays short and English.
    # Separator is a hyphen since 2026-08-20 (guide §3): 2026-08-20-share-songs-from-journal.
    tid = norm_id(args.id)
    if not re.match(r"^\d{4}-\d{2}-\d{2}[-_]", tid):
        tid = f"{now_iso()[:10]}-{tid}"
    dropped = id_words_dropped(args.id)
    if dropped:
        # Said out loud, never in silence (an agent's review, 2026-08-22).
        print(f"⚠ id урезан до пяти слов: {tid} — отброшено: {'-'.join(dropped)}")
    tdir = os.path.join(root, tid)
    if os.path.isdir(tdir):
        hold(root, tid, "взята в руку: el new на существующей")
        print(f"task already exists: {tid}")
        return 0
    # THE SAME TASK AGAIN? (owner, 2026-08-22: he repeats a request in another conversation
    # and an agent that never saw the first one opens a twin.) The words of the new task —
    # description and raw request — against the name and request of every OPEN task: a strong
    # overlap is refused with the twin named and the way to continue it; a weak one is shown
    # and we go on. The CLI compares words; whether it IS the same task the agent judges.
    raw0 = (getattr(args, "raw", None) or "").strip()
    twins = similar_tasks(root, desc + " " + raw0)
    strong = [h for h in twins if h[1] >= 2 and h[0] >= 0.5]
    if strong and not getattr(args, "force", False):
        print("НЕ ЗАВЕДУ — похоже, эта задача уже есть:", file=sys.stderr)
        for score, n, t, name in strong:
            print(f"  {t}  ·  {name[:70]}", file=sys.stderr)
            rl = request_line(os.path.join(root, t), 100)
            if rl:
                print(f"      запрос: {rl}", file=sys.stderr)
        print("  продолжить её: el use <id> · дозаписать повтор запроса: el boot \"…\" --id <id> "
              '--raw "<слова>" · точно новая: --force', file=sys.stderr)
        return 1
    if twins and not strong:
        print("похожие задачи (проверь, не дубль ли): " +
              " · ".join(f"{t} — {name[:40]}" for _s, _n, t, name in twins))
    # Stage folders are NOT pre-created (owner, 2026-08-21): a folder appears the moment its
    # phase leaves the first trace — write() makes parents on demand. The tree itself becomes
    # a progress indicator: a project abandoned at context HOLDS only init/ and context/,
    # and an empty evidence/ can no longer pretend anything happened there.
    os.makedirs(tdir, exist_ok=True)
    # The user's request IN HIS WORDS (guide §2). Not a transcript any more (owner,
    # 2026-08-26: «не то что слово в слово, но чуть-чуть собраннее; что не относится к
    # запросу — не записывать»): what is about the task stays, side talk and speech-recognition
    # noise are left out, the shape is tidied just enough to read as a request. Still not the
    # agent's reformulation — that can lose a detail; his own wording is the insurance.
    raw = (getattr(args, "raw", None) or "").strip()
    if raw:
        write(os.path.join(tdir, "init", "request.md"),
              f"# Запрос пользователя\n\n_записано {now_iso()[:16].replace('T', ' ')}_\n\n{raw}\n")
    # NOT created any more (owner, 2026-08-20 — stage 0 creates only what the guide names):
    #   project.md          — the card is DERIVED from the journal (task_meta); a stored
    #                         card was a second written copy of what the events already say
    #   BIG-PICTURE.md      — its aggregator role went to overview.html (the human's page)
    #                         and `el status` (the agent's view)
    #   context/task.draft.md — was the user's request; init/request.md IS that record now
    #   open-questions.md   — `el defer` creates it the moment something is actually parked
    # The `created` event below is load-bearing: it is the FIRST journal line and the
    # derived card reads the task's name from it.
    journal(root, tid, "created", desc)
    # Born INTO the hand — except a spawned task, which is put down at birth so the task
    # it fell out of stays in hand (cmd_spawn passes hand=False).
    if getattr(args, "hand", True):
        journal(root, tid, "hold", "взята в руку: рождение")
    if raw:
        journal(root, tid, "request", "запрос пользователя записан — его словами",
                {"ref": "init/request.md"})
    # The mode at birth — by the task's weight (light · soft · strict); default soft.
    mode0 = (getattr(args, "mode", None) or "").strip().lower()
    if mode0 and mode0 in MODES and mode0 != "soft":
        journal(root, tid, "mode", f"soft → {mode0} — задан при рождении", {"mode": mode0})
    print(f"task created: {tid}" + (f" · mode {mode0}" if mode0 else ""))
    return 0


def cmd_boot(args):
    """One call for the BOOT beat: folder exists or is created, task exists or is created."""
    root, made = find_root(), []
    if not root:
        cmd_init(argparse.Namespace(dir=None))
        root = find_root()
        made.append("folder")
    if not root:
        print("could not set up Elephant", file=sys.stderr)
        return 1
    desc = (args.description or "").strip()
    if desc and args.id:
        # Look the task up the way every other command does — the given id has no date
        # prefix, the folder does, and comparing them raw reported "created: task" on a
        # task that already existed (caught live 2026-08-20).
        existing = resolve_task(root, args.id)
        if existing:
            # A late --raw completes stage 0 on an existing task: the request was not
            # recorded at birth, the human repeated it, it lands now — in his words.
            raw = (getattr(args, "raw", None) or "").strip()
            req = os.path.join(root, existing, "init", "request.md")
            if raw and not os.path.exists(req):
                write(req, f"# Запрос пользователя\n\n_записано "
                           f"{now_iso()[:16].replace('T', ' ')}_\n\n{raw}\n")
                journal(root, existing, "request",
                        "запрос пользователя дозаписан — его словами", {"ref": "init/request.md"})
                made.append("request")
            elif raw:
                # THE REQUEST REPEATED (owner, 2026-08-22): the same task asked again, in
                # other words, another day — appended under its date, in his words, never
                # overwriting the first: how he put it each time is history worth keeping.
                with open(req, "a", encoding="utf-8") as fh:
                    fh.write(f"\n## Повтор запроса · {now_iso()[:16].replace('T', ' ')}\n\n{raw}\n")
                journal(root, existing, "request", "запрос повторён — дозаписан его словами",
                        {"ref": "init/request.md", "repeat": True})
                made.append("request-repeat")
            hold(root, existing, "взята в руку: el boot")
        else:
            # A refusal inside `new` (a twin of an open task) is a refusal of boot too — it
            # used to fall through and print «created: task» over a task that was not.
            rc = cmd_new(argparse.Namespace(description=desc, id=args.id,
                                            raw=getattr(args, "raw", None),
                                            mode=getattr(args, "mode", None),
                                            force=getattr(args, "force", False)))
            if rc:
                return rc
            made.append("task")
    print(ctx_line(root) + (f" · created: {', '.join(made)}" if made else ""))
    return 0


def cmd_use(args):
    """TAKE a task in hand — one `hold` event in its journal; «current» is computed from
    those events (state.current_task), so there is still no stored field."""
    root = require_root()
    if not root:
        return 1
    tid = resolve_task(root, args.task)
    if not tid or not os.path.isdir(os.path.join(root, tid)):
        print(f"no task {args.task}.", file=sys.stderr)
        print(f"hint     available: {', '.join(tasks_of(root)) or '— none yet'}", file=sys.stderr)
        print("         el projects — with phases and descriptions", file=sys.stderr)
        return 1
    meta = task_meta(root, tid)
    if meta.get("status", "active") != "active":
        print(f"{tid} is closed as {meta['status']} — it cannot become current.")
        print(f"read it: el context --task {tid}")
        return 0
    if not hold(root, tid, "взята в руку: el use"):
        print(f"{tid} и так в руке")
    print(ctx_line(root))
    return 0


def cmd_log(args):
    root = require_root()
    if not root:
        return 1
    # `--task` writes into ANOTHER task — a note about a task you are not standing in. The
    # hand does not move: it is a hold event, not the freshest journal (it used to be, and
    # this very command had to `touch` the held task back — 2026-08-22).
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    # The derived card reads state from these event types, so writing one through `log`
    # would move the phase or close the task PAST the gates. Each has its own command.
    if args.type in RESERVED_EVENTS:
        print(f"event type `{args.type}` is written by its own command, not by log:",
              file=sys.stderr)
        print("  advance → el forward · reroute → el phase · done → el done · "
              "reopened → el reopen", file=sys.stderr)
        return 1
    # TO THE NODE IN WORK (owner, 2026-08-25: «чтобы работа записывалась туда, где делается»):
    # a note written during execute lands on the active node — the page and `el plan <узел>`
    # show it there. `--node` aims elsewhere, `--free` keeps it off any node, on purpose.
    tdir = os.path.join(root, task)
    from .plan import active_node as _act, node_read as _nread, node_status as _nst, path_to_id
    act = _act(tdir)
    act = act if act and _nst(act) == "active" else None
    want = (getattr(args, "node", None) or "").strip()
    free = bool(getattr(args, "free", False))
    extra = {}
    if want:
        nid = path_to_id([want])
        if not _nread(tdir, nid):
            print(f"нет узла {nid}", file=sys.stderr)
            return 1
        extra["node"] = nid
    elif act and not free:
        extra["node"] = act["id"]
    if free:
        extra["free"] = True      # said so — the by-time reading must not attach it either
    journal(root, task, args.type, args.text, extra or None)
    print(f"logged: {args.type}" + (f" → {extra['node']}" if extra.get("node") else "")
          + (f" → {task}" if getattr(args, "task", None) else ""))
    if extra.get("node") and act and extra["node"] != act["id"]:
        print(f"⚠ {act['id']} всё ещё в работе, а запись ушла в {extra['node']} — закрой "
              f"(el plan done {act['id'].lower()}), поставь ждать (el plan wait), отложи "
              f"(el plan park --why) или смени: el plan start {extra['node'].lower()} --switch \"<почему>\"")
    elif not extra.get("node") and not free and task_meta(root, task).get("phase") == "execute":
        print("⚠ запись без узла — на execute работа идёт по узлам: сначала узел (el plan new · "
              "el plan start), потом работа; осознанно мимо узлов: --free")
    return 0


def cmd_beat(args):
    """Mark a beat that leaves no file of its own (sync, gate, course). `--task` like every
    other command that writes about a task — it was the one command without it (an agent's
    review, 2026-08-22: «ожидаемый инвариант; несоблюдение ловится только наощупь»)."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    phase = task_meta(root, task).get("phase", "context")
    journal(root, task, "beat", args.name.lower(),
            {"phase": phase, **({"ref": args.ref} if args.ref else {})})
    touch(root, task)
    print(f"beat {phase}/{args.name.lower()} marked")
    return 0


def cmd_put(args):
    """Put a file into the task's artifacts/ or evidence/ — and write the journal line for it.

    Every phase demands traces "in their place", and `el next` says so on every run, but there
    was no command that PUT anything there: the agent copied by hand and then had to remember
    to log it separately. Two steps that always go together are one command. (Owner, 2026-08-20:
    "когда тебе чего-то не хватает — сразу добавляй эти команды".)

    Copies rather than moves: the source is usually a scratch file the agent still works with."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    kind = args.kind
    tdir = os.path.join(root, task)
    dest_dir = os.path.join(tdir, kind)
    os.makedirs(dest_dir, exist_ok=True)
    rename = getattr(args, "rename", None)
    files = list(args.files)
    if rename and len(files) > 1:
        print("--as works with ONE file", file=sys.stderr)
        return 1
    put = []
    for src in files:
        # a path the agent wrote from inside the task («research/x.md») resolves from the task
        # folder too (recorder 2026-08-25: `el artifact research/*.md` failed and was retried
        # with the full .history/<task>/ prefix)
        if not os.path.exists(src) and os.path.exists(os.path.join(tdir, src)):
            src = os.path.join(tdir, src)
        if not os.path.exists(src):
            print(f"нет файла: {src}", file=sys.stderr)
            return 1
        name = rename or os.path.basename(src)
        if rename and os.path.splitext(name)[1] == "" and os.path.splitext(src)[1]:
            name += os.path.splitext(src)[1]
        dst = os.path.join(dest_dir, name)
        # The agent may have written the file straight into artifacts/ or evidence/ —
        # then src IS dst, and copyfile raised SameFileError instead of just linking it
        # to the node (feedback pool, 2026-08-22).
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copyfile(src, dst)
            print(f"{kind:<9} {dst}")
        else:
            print(f"{kind:<9} {dst} — уже на месте")
        put.append(name)
    why = getattr(args, "why", None)
    line = f"{kind}: " + ", ".join(put) + (f" — {why}" if why else "")
    # FILED TO A NODE (owner, 2026-08-22): a file in artifacts/ says nothing about which
    # promise it serves. --node ties it to the node (and --check to the criterion), the
    # board and the page show it there, `el doctor` can find a node with no traces.
    extra = {"files": put}
    nid = (getattr(args, "node", None) or "").strip()
    if nid:
        nid = path_to_id([nid])
        # IFR IS A TARGET TOO (feedback pool, 2026-08-23): the acceptance checklist is a
        # pseudo-node of the ledger, not a node of the plan — `--node ifr` used to fail with
        # «нет узла IFR» AFTER copying the file, so the agent had to ignore the exit code and
        # call twice. A proof of a checklist item belongs to that item like any other.
        if nid != "IFR" and not node_read(tdir, nid):
            print(f"нет узла {nid} — файлы скопированы, но не привязаны; проверь: el plan",
                  file=sys.stderr)
            return 1
        extra["node"] = nid
        chk = getattr(args, "check", None)
        if chk:
            extra["check"] = int(chk)
            line += f" → {nid}.{chk}"
        else:
            line += f" → {nid}"
    journal(root, task, kind, line, extra)
    if nid:
        print(f"узел      {nid}" + (f" · критерий {extra['check']} — отметь: el validate "
                                  f"{nid.lower()} {extra['check']} --met \"<чем доказано>\" "
                                  f"--evidence {kind}/{put[0]}" if extra.get("check") else ""))
    # THE PATH INSIDE THE PROJECT, spelled out: the next command (`el validate --evidence`)
    # takes exactly this, not the source path — and an agent given only «записано в журнал»
    # re-passed the original path and went in a circle (feedback pool, 2026-08-23).
    print(f"ссылаться на  " + " · ".join(f"{kind}/{n}" for n in put))
    print('записано  в журнал · дальше: el left — что осталось')
    return 0


def cmd_accept(args):
    """The owner's word — condition 3 of the gate, and the one thing a checklist cannot replace.

    HONEST LIMIT, stated out loud because pretending otherwise would be worse: nothing here
    can PROVE the owner spoke. An agent can type this command with words nobody said. What the
    design buys instead is that a forgery becomes visible and expensive: the quote is stored
    verbatim, printed back inside `el context`, and stamped in the journal — so the owner reads
    his own words on the next pass and sees at once if they are not his. The gate makes bypass
    a deliberate act rather than an oversight; the audit makes it detectable afterwards. That
    is the whole of it. (Owner's open question, 2026-08-19: "как ты это проверишь?")"""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    if not args.words:
        print("record the owner's words VERBATIM — not your paraphrase of them.", file=sys.stderr)
        print('hint     el accept "да, так и делаем" ', file=sys.stderr)
        return 1
    phase = task_meta(root, task).get("phase", "context")
    pend = pending_word(root, task)
    # SCOPED (owner, 2026-08-22): «готово» over one observed scenario is not acceptance of
    # the system; his «да» over the plan is not acceptance of the result. Every word says
    # what it is over: context · design:<fork> · plan · node:<id> · observation:<id> · final.
    # Unscoped, it takes the phase's natural scope; the final word on validate is the only
    # one the validate gate counts.
    act = active_node(tdir)
    scope = (getattr(args, "for_", None) or "").strip()
    if not scope:
        scope = {"context": "context", "plan": "plan", "validate": "final",
                 "think": "design"}.get(phase) or (f"node:{act['id']}" if act else "note")
    rel = CONTEXT_FILES["approval"] if phase == "context" else "acceptance.md"
    path = os.path.join(tdir, rel)
    body = open(path, encoding="utf-8").read() if os.path.exists(path) else \
        "# Слово владельца\n\n_Дословно. Не пересказ._\n"
    # A BORROWED WORD (owner, 2026-08-22: autonomy = a credit of the word). The agent writes
    # what it takes for his word and why — marked in the file, an `assume` event in the
    # journal; the gates read the file as they always did, so the borrowed word opens them
    # ONLY under a standing grant (autonomy.guard refuses otherwise). The final word is never
    # borrowed: an autonomous run ends at «готово, жду приёмки», not at completed.
    assumed = (getattr(args, "assumed", None) or "").strip()
    if assumed:
        if scope == "final":
            print("последнее слово не занимают: приёмку даёт только человек. Остановись: "
                  'el halt "готово, жду приёмки: <что показать>"', file=sys.stderr)
            return 1
        if not autonomy.guard(root, task):
            return 1
        body += (f"\n## {now_iso()[:16]} · фаза {phase} · {scope} · ЗАЙМ СЛОВА (предположено агентом)\n\n"
                 f"> {args.words.strip()}\n\nпочему так принял: {assumed}\n")
        write(path, body)
        journal(root, task, "assume", args.words.strip(),
                {"phase": phase, "for": scope, "why": assumed})
        touch(root, task)
        n = len(autonomy.debt(task_meta(root, task)))
        print(f"занято    слово над {scope} — записано в {rel} как займ · долг слова {n} (el review)")
        print('          его слово потом: el accept "<его слова>" --for ' + scope.split(":")[0]
              + (" — покрывает все займы контекста" if scope == "context" else ""))
        if scope.lower().startswith("node:"):
            nid = path_to_id([scope.split(":", 1)[1]])
            node = node_read(tdir, nid)
            if node and node_status(node) == "waiting":
                node_resume(root, task, tdir, node)
                print(f"эстафета  снова у агента — {nid}")
        print('gate      открыт займом — el forward --why "<что закрыто и чем доказано>"')
        return 0
    # --close PROMISES «его слово и узел закрыт» — so the question «can it close?» is asked
    # BEFORE the word is written, and a «no» writes nothing (feedback pool, 2026-08-24: the
    # word landed, then «НЕ ЗАКРОЮ» over criteria without verdicts, exit 1 — half a command).
    # His word is not lost: the refusal hands back the same call without --close.
    if scope.lower().startswith("node:") and getattr(args, "close", False):
        nid_c = path_to_id([scope.split(":", 1)[1]])
        node_c = node_read(tdir, nid_c)
        if not node_c:
            print(f"нет узла {nid_c} — слово не записано", file=sys.stderr)
            return 1
        if plan_done(root, task, tdir, [nid_c, args.words.strip()[:120]], dry=True):
            print(f"слово НЕ записано: --close обещает закрыть {nid_c}, а закрыть его нельзя "
                  "(причина выше).", file=sys.stderr)
            print(f'  записать слово сейчас, узел позже:  el accept "{args.words.strip()[:60]}" '
                  f"--for node:{nid_c.lower()}", file=sys.stderr)
            print(f"  или сначала ответь критериям, потом повтори с --close", file=sys.stderr)
            return 1
    body += f"\n## {now_iso()[:16]} · фаза {phase} · {scope}\n\n> {args.words.strip()}\n"
    if getattr(args, "on", None):
        body += f"\nутверждено: {args.on.strip()}\n"
    write(path, body)
    journal(root, task, "accepted", args.words.strip(), {"phase": phase, "for": scope})
    touch(root, task)
    print(f"recorded  {rel} · {scope}")
    mark = change_mark(args.words)
    if mark:
        # Acceptance does not edit the contract: what he ADDED goes the amendment way, which
        # re-opens his word by itself — otherwise the archive keeps both readings and no one
        # knows which one the nodes and verdicts answer to.
        print(f"похоже    в слове есть изменение («{mark}»), а не только приёмка — приёмка контракт не правит.")
        print('          оформи поправкой: el context requirements "<что добавилось>" --why "<его слова>" · '
              'чек-лист приёмки: el context checklist "…" --why "…"')
        print("          затем: затронутые узлы — el plan set … · их вердикты устарели — el validate … · "
              "листок — el brief; поправка сама попросит его свежее слово")
    paid = [a for a in task_meta(root, task).get("assumes", [])
            if autonomy.pays(scope, a.get("for") or "")]
    if paid:
        left = len(autonomy.debt(task_meta(root, task)))
        print(f"оплачено  его словом займов над {scope}: {len(paid)} · долг слова теперь {left}")
    if scope.lower().startswith("node:"):
        nid = path_to_id([scope.split(":", 1)[1]])
        node = node_read(tdir, nid)
        if node and getattr(args, "close", False):
            rc = plan_done(root, task, tdir, [nid, args.words.strip()[:120]])
            if rc:
                return rc
        elif node and node_status(node) == "waiting":
            st = node_resume(root, task, tdir, node)
            print(f"эстафета  снова у агента — {nid} " +
                  ("в работе" if st == "active" else f"готов продолжить: el plan start {nid.lower()}"))
    if phase == "validate" and scope != "final":
        print("приёмка   это слово над частью; итоговую приёмку запиши отдельно: "
              'el accept "<его слова>" --for final')
    if pend:
        print(f"покрыто   поправки {pending_line(pend)} — его слово над ними записано")
    print('gate      открыт — el forward --why "<что закрыто и чем доказано>"')
    return 0


def cmd_todo(args):
    """Park something that must NOT be lost, but does not belong to the phase we are on.

    The folder had `open-questions.md` from day one and no command ever wrote to it, so the
    only way to carry a "check this when we get to the phone" was to hold it in the agent's
    head — and a session ends. Written down with the phase it belongs to; `el next` surfaces
    the ones whose phase has arrived, which is the whole point: a note nobody is shown at the
    right moment is the same as a forgotten one. (Owner, 2026-08-19: "запиши в task list".)"""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    path = os.path.join(root, task, "open-questions.md")
    if getattr(args, "list", False) or (not args.text and not getattr(args, "done", None)):
        # NUMBERED, the way --done counts (feedback 2026-08-24: the raw file had no numbers,
        # the agent counted by eye and closed the wrong item — twice). Open items carry their
        # number; closed ones are folded away unless --all.
        items = todo_items(os.path.join(root, task))
        open_items = [it for it in items if it["open"]]
        closed_items = [it for it in items if not it["open"]]
        if not items:
            print("нет отложенного.")
        else:
            print(f"отложено  открыто {len(open_items)} · закрыто {len(closed_items)}"
                  " — номер у пункта = N для --done")
            for it in open_items:
                print(f"  {todo_line(it)}")
                if it["why"]:
                    print(f"         зачем: {it['why'][:90]}")
            if closed_items:
                if getattr(args, "all", False):
                    print(f"закрыто   {len(closed_items)}")
                    for it in closed_items:
                        print(f"  {todo_line(it)}")
                else:
                    print(f"закрыто   {len(closed_items)} — показать: el todo --all")
        if not args.text:
            print('\nзапись   el todo "<что сделать>" --when <фаза> [--every "<как часто>" — напоминание ⟳] · '
                  'закрыть: el todo --done N "<чем доказано>"')
        return 0
    # Closing a parked item was impossible until now: `el next` kept surfacing work already
    # done, and a reminder that will not go away stops being read. Found on the first live use.
    if getattr(args, "done", None):
        if not os.path.exists(path):
            print("нет отложенного.", file=sys.stderr)
            return 1
        lines = open(path, encoding="utf-8").read().splitlines()
        open_idx = [i for i, l in enumerate(lines) if l.strip().startswith("- [ ]")]
        n = args.done
        if not (1 <= n <= len(open_idx)):
            print(f"нет открытого пункта {n}; открыто: {len(open_idx)}", file=sys.stderr)
            for it in todo_items(os.path.join(root, task)):
                if it["open"]:
                    print(f"  {todo_line(it)}", file=sys.stderr)
            return 1
        i = open_idx[n - 1]
        lines[i] = lines[i].replace("- [ ]", "- [x]", 1) + f"  ← закрыто {now_iso()[:16]}"
        if args.text:
            lines[i] += f": {args.text.strip()}"
        write(path, "\n".join(lines) + "\n")
        journal(root, task, "todo-done", lines[i][5:120])
        touch(root, task)
        # the item just closed — by its POSITION among the checkbox lines, not «the last
        # closed one» (which is whichever closed item sits lowest in the file)
        k = sum(1 for l in lines[:i] if l.strip().startswith(("- [ ]", "- [x]")))
        closed_it = todo_items(os.path.join(root, task))[k]
        print(f"закрыто   {todo_line(closed_it)}")
        left_n = len(open_idx) - 1
        if left_n:
            print(f"осталось  {left_n} — номера сдвинулись, перечитай: el todo")
        return 0
    when = (getattr(args, "when", None) or "").strip().lower()
    if when and when not in PHASES:
        print(f"--when: одна из фаз {', '.join(PHASES)}", file=sys.stderr)
        return 1
    body = open(path, encoding="utf-8").read() if os.path.exists(path) else \
        "# Открытые вопросы и отложенное\n\n"
    every = (getattr(args, "every", None) or "").strip()
    body += f"\n- [ ] **{when or 'когда угодно'}{' ⟳ ' + every if every else ''}** · {args.text.strip()}"
    if getattr(args, "why", None):
        body += f"\n      зачем: {args.why.strip()}"
    body += "\n"
    write(path, body)
    journal(root, task, "todo", args.text.strip()[:120], {"when": when or None})
    touch(root, task)
    if every:
        print(f"напоминание  open-questions.md · ⟳ {every} · всплывает на фазе {when or 'любой'} "
              "под ходом, не как ход; закрытию проекта не мешает")
    else:
        print(f"отложено  open-questions.md · всплывёт на фазе {when or 'любой'} — под ходом, "
              "как обещание к фазе")
    return 0


def cmd_spawn(args):
    """Split a NEW task off the flow without derailing the one in hand.

    Thinking always attracts new wishes — the owner's observation (2026-08-19): "всегда новые
    фичи, новые пожелания… надо отделять: что мы сейчас делаем, а что потом". Two bad answers
    exist. Take it in now: the current task swells and never lands. Say "later" without writing
    it: it dies. This is the third — it becomes a real task on disk, with a note saying which
    conversation it fell out of, and the current task stays current."""
    root = require_root()
    if not root:
        return 1
    src = current_task(root)
    if not args.description or not args.id:
        print('el spawn "<описание>" --id <короткое-имя> [--why "<откуда пришло>"]',
              file=sys.stderr)
        return 1
    # The raw request travels WITH the spawn: a wish that surfaced mid-conversation has the
    # human's own wording available at the very moment it is written down, and stage 0 is not
    # closed until init/request.md exists (guide §2). Without this the freshest wording in
    # the whole protocol was the one the CLI dropped. (2026-08-22, live task.)
    rc = cmd_new(argparse.Namespace(description=args.description, id=args.id, mode=None,
                                    raw=getattr(args, "raw", None), hand=False,
                                    force=getattr(args, "force", False)))
    if rc != 0:
        return rc
    tid = norm_id(args.id)
    if not re.match(r"^\d{4}-\d{2}-\d{2}[-_]", tid):
        tid = f"{now_iso()[:10]}-{tid}"
    dep = getattr(args, "depends_on", None)
    if dep:
        dep = resolve_task(root, dep) or dep
        # A DEPENDENT PROJECT, in his terms (2026-08-19): a separate task because it needs its
        # OWN context — its own settings, its own questions — while still standing on what this
        # one builds. The link is written on BOTH sides so neither can be found without the
        # other: "просто нужно записать, что есть ещё зависимый проект, и там статус такой-то".
        journal(root, tid, "depends", f"зависит от {dep}", {"on": dep})
        journal(root, dep, "dependent", f"{tid} зависит от этой задачи")
    if src:
        origin = args.why or f"отделено от задачи {src}"
        write(os.path.join(root, tid, "context", "origin.md"),
              f"# Откуда взялась эта задача\n\n{origin}\n\n"
              f"- родительская задача: `{src}`\n- отделено: {now_iso()[:16]}\n")
        journal(root, src, "spawned", f"{tid}: {args.description[:90]}")
    # The task in hand stays in hand — structurally: the new one is born WITHOUT a hold
    # event (hand=False above), and nothing else moves the hand (state.current_task).
    print(f"новая задача  {tid} — заведена и ЖДЁТ, в руке осталась прежняя")
    print(f"в руке        {src or '—'}")
    print("список        el projects")
    return 0


def cmd_reopen(args):
    """Bring a closed task back to life — a decision reversed IS normal work.

    `el done` was one-way, so a task closed on a judgement that later turned out wrong could
    only be recreated from scratch, losing its history. Reversal happens: this very session
    closed three tasks as "dropped, they are stages", and then the owner's sharper criterion —
    does it need its OWN context? — put one of them back. The reason for reopening is written
    into the journal next to the reason for closing, so the pair reads as one story."""
    root = require_root()
    if not root:
        return 1
    tid = resolve_task(root, args.task_id)
    if not tid:
        print(f"нет задачи {args.task_id}", file=sys.stderr)
        return 1
    was = task_meta(root, tid).get("status", "active")
    if was == "active":
        print(f"{tid} и так открыта")
        return 0
    if not args.why:
        print("скажи, почему открываем обратно — это парная запись к причине закрытия.",
              file=sys.stderr)
        return 1
    journal(root, tid, "reopened", args.why.strip()[:160], {"was": was})
    hold(root, tid, "взята в руку: открыта заново")
    print(f"открыта заново  {tid} (была {was}) — и снова в руке")
    return 0


def cmd_done(args):
    """Close a task WITH a result. Every task must end in something readable a month later:
    what we did, how it ended, why. Closing by hand is the operation that gets forgotten —
    and a folder of tasks without endings is exactly what makes the bookkeeping useless."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, args.task)
    if not task:
        return 1
    if args.outcome not in OUTCOMES:
        print("outcome must be one of:", file=sys.stderr)
        for k, v in OUTCOMES.items():
            print(f"  {k:<10} {v}", file=sys.stderr)
        return 1
    if not args.result.strip():
        print("a result is required — a task closed without one is indistinguishable "
              "from an abandoned one.", file=sys.stderr)
        print('hint     el done "<what came out of it>" --as completed|closed|dropped|blocked',
              file=sys.stderr)
        print("         el context — the big picture, to write the result from", file=sys.stderr)
        return 1
    tdir = os.path.join(root, task)
    # a reminder (⟳) is a standing duty, not a promise — it does not hold completion
    open_todos = [it for it in todo_items(tdir) if it["open"] and not it.get("every")]
    if args.outcome == "completed" and open_todos:
        print("completion refused — open el todo items are unfinished promises:", file=sys.stderr)
        for it in open_todos:
            print(f"  {todo_line(it, width=100)}", file=sys.stderr)
        print('finish and close them first: el todo --done N "<what proved it>"', file=sys.stderr)
        return 1
    open_nodes = [n for n in nodes_all(tdir) if node_open(n)]
    if args.outcome == "completed" and open_nodes:
        print("НЕ ЗАКРОЮ как completed — узлы плана не закрыты:", file=sys.stderr)
        for n in open_nodes:
            print(f"  {n['id']:<6} {STATUS_RU.get(node_status(n), '?'):<14} "
                  f"{(n.get('name') or '')[:60]}", file=sys.stderr)
        print('  закрыть: el plan done <узел> "<результат>" · отложить: el plan park <узел> --why "…"',
              file=sys.stderr)
        unf = [n["id"] for n in open_nodes if (n.get("unfold") or "").strip()]
        if unf:
            print(f"  из них места раскрытия: {', '.join(unf)} — их закрывают не «done», а "
                  "раскрытием:", file=sys.stderr)
            print("  завести под ними работы (el plan new <узел> wp1 \"…\") и закрыть их — "
                  "или отложить осознанно (el plan park), если решено не идти туда",
                  file=sys.stderr)
        return 1
    meta = task_meta(root, task)
    if meta.get("status", "active") != "active":
        print(f"already closed as {meta['status']} on {meta.get('closed_at', '?')[:10]}")
        return 0
    # A borrowed word is a DEBT, and «destination reached» cannot stand on debts: the owner
    # has not read the assumptions the result rests on (owner, 2026-08-22).
    owed = autonomy.debt(meta)
    if args.outcome == "completed" and owed:
        print(f"НЕ ЗАКРОЮ как completed — долг слова: {len(owed)} займ(ов) не оплачены его словом.",
              file=sys.stderr)
        print("  леджер: el review · его слово: el accept \"<его слова>\" --for context | plan | "
              "design:<id> | node:<id>", file=sys.stderr)
        print('  без него — остановись: el halt "готово, жду приёмки и слова над займами"',
              file=sys.stderr)
        return 1
    # THE OWNER'S DEBT (2026-08-24): an answer he never brought is either still needed — then
    # «completed» is a guess — or never came due — then say so: el owe drop.
    open_owed = owe.open_items(root, task)
    if args.outcome == "completed" and open_owed:
        print(f"НЕ ЗАКРОЮ как completed — за владельцем {len(open_owed)} ответ(ов), которых он не принёс:",
              file=sys.stderr)
        for it in open_owed:
            print(f"  #{it['n']} {it['kind']} · {it['q'][:80]}", file=sys.stderr)
        print('  ответ: el owe answer <n> "<его ответ>" · не понадобилось: el owe drop <n> --why "…"',
              file=sys.stderr)
        return 1
    phase = meta.get("phase", "context")
    # WORK LIVING IN AN OUTSIDE SYSTEM must leave its trace THERE before the task closes
    # (owner, 2026-08-21: an agent closed a task with the code never committed — a week
    # later that work does not exist). Git is the one outside system the CLI can MEASURE;
    # the others (a database, a sent document) are named in the blueprint and checked by
    # eyes. Closing over a dirty tree stays legal, but only said out loud.
    proj = project_root()
    dirty = git_dirty(proj, exclude=os.path.relpath(root, proj))
    if dirty and not getattr(args, "dirty", None):
        print("НЕ ЗАКРОЮ — в рабочем дереве git незакоммиченные изменения:", file=sys.stderr)
        for line in dirty[:8]:
            print(f"  {line}", file=sys.stderr)
        if len(dirty) > 8:
            print(f"  … и ещё {len(dirty) - 8}", file=sys.stderr)
        print("  закоммить работу — либо закрой осознанно:", file=sys.stderr)
        print('  el done "<результат>" --as <вид> --dirty "<почему без коммита>"',
              file=sys.stderr)
        return 1
    # CLOSING FROM AN EARLY PHASE IS LEGAL — AND MUST SAY WHY (owner, 2026-08-23, on a task
    # that stood at «2/8 думать» while it was finished and shipped):
    #   «задача закрывается только по слову владельца… если мы дошли до контекста и
    #    пользователь закрывает задачу — тут нет проблем… и выводы, результаты пишет,
    #    где-то в конце это должно быть закрытие».
    # So his word is the universal key, not a bypass: a task may close from ANY phase, and
    # what the bookkeeping owes in return is the reason, written next to the result. Without
    # it a folder holds a task that stops mid-road and nobody can say what happened.
    why = (getattr(args, "why", None) or "").strip()
    early = phase not in ("validate", "reflect", "align", "close")
    if early and not why:
        print(f"НЕ ЗАКРОЮ молча — задача стоит на {phase}, а закрывается сейчас: скажи, почему.",
              file=sys.stderr)
        print("  закрыть можно с ЛЮБОЙ фазы — это слово человека, а не обход;", file=sys.stderr)
        print("  но «почему» должно остаться в папке, иначе через месяц не прочитать:",
              file=sys.stderr)
        print(f'  el done "<что вышло>" --as {args.outcome} --why "<его слова: почему закрываем '
              'здесь>"', file=sys.stderr)
        return 1
    # The event IS the closing: the derived card reads status, outcome and result from it.
    extra = {"outcome": args.outcome, "phase": phase}
    if why:
        extra["why"] = why
    if dirty:
        extra["dirty"] = getattr(args, "dirty")
    journal(root, task, "done", args.result.strip()[:200], extra)
    print(f"{task} closed as {args.outcome} — {OUTCOMES[args.outcome]}")
    if why:
        print(f"почему    {why}")
    # Closing PUTS THE TASK DOWN (owner, 2026-08-22): the hand is empty until `el use`
    # takes another — nothing is picked up in its place by freshness.
    cur = current_task(root)
    if cur:
        print(f"в руке    {cur} — осталась (закрыта была другая)")
    else:
        print("в руке    ничего — задача снята с руки · взять следующую: el use <id>")
    print("next      el projects — what is still open")
    print('отзыв     об инструменте, пока свежо: el feedback "наблюдал: <команда дословно → вывод как есть> · '
          'до/после: … · ожидал: … · обошёл: … · помогло: …" --about <команда> · длинное — --file')
    return 0


def cmd_lesson(args):
    """A lesson that outlives its task (owner, 2026-08-21: "агент на первой, второй, пятой
    задаче споткнулся об одно и то же — куда это занести, чтобы следующий прочитал?").

    Written to <storage>/lessons.md — STORAGE level, because the stone is usually in the
    repo, not in one task — and echoed into the task's journal for the story. Read at
    onboarding: bare `el` prints the lessons, so every new agent starts already warned."""
    root = require_root()
    if not root:
        return 1
    text = args.text.strip()
    if not text:
        print('el lesson "<обо что споткнулись и как обходить>"', file=sys.stderr)
        return 1
    want = getattr(args, "task", None)
    task = resolve_task(root, want) if want else current_task(root)
    if want and not task:
        print(f"no task {want}", file=sys.stderr)
        return 1
    path = lessons_path(root)
    if not os.path.exists(path):
        write(path, "# Уроки этого хранилища\n\n"
                    "_Что споткнуло и как обходить. Пишется на фазе уроков (`el lesson`), "
                    "читается каждым агентом на входе — голый `el` печатает этот список._\n\n")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"- {now_iso()[:10]} · {task or '—'}: {text}\n")
    if task:
        journal(root, task, "lesson", text[:200], {"ref": "../lessons.md"})
    print(f"урок записан → {path}")
    return 0


def cmd_ui(args):
    """Refresh the human pages ON DEMAND (owner, 2026-08-21: "ввёл ui update — и весь UI
    обновился"), without waiting for the agent's next write. Covers the honest gap too:
    files edited PAST `el` never trigger a render, and this command catches them up.
    `--open` also opens the storage page in the browser."""
    root = require_root()
    if not root:
        return 1
    render_views(root)
    idx = os.path.join(root, "index.html")
    print(f"обновлено  {len(tasks_of(root))} проект(ов): страницы и их данные свежие")
    print(f"открыть    {idx}")
    if getattr(args, "open", False):
        import subprocess
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        try:
            subprocess.Popen([opener, idx], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            print("открыл в браузере")
        except OSError:
            pass
    return 0


def cmd_blueprint(args):
    """The contract in doses (owner, 2026-08-22): bare — the big picture, one screen;
    <фаза> — that phase with all its beats; rules · modes · files — the other sections;
    full — everything in one stream, the human's one-shot listing. Screens that cannot fit
    one tool call say so in their head (term.emit)."""
    bp_mode = (getattr(args, "mode", None) or "").strip().lower()
    if bp_mode and bp_mode not in MODES:
        print(f"--mode: одно из {', '.join(MODES)}", file=sys.stderr)
        return 1
    if not bp_mode:
        r0 = find_root()
        t0 = current_task(r0) if r0 else None
        bp_mode = task_meta(r0, t0).get("mode", "soft") if t0 else "soft"
    word = getattr(args, "part", None)
    part = resolve_part(word) if word else None
    if word and not part:
        print(f"нет части «{word}» · части: {' · '.join(PARTS)} (или номер фазы 0–8)", file=sys.stderr)
        return 1
    emit(render(part, bp_mode),
         parts="el blueprint " + " · ".join(p for p in PARTS if p != "full"))
    return 0


def cmd_mode(args):
    """Set the task's tightness — light · soft · strict — or show it (owner, 2026-08-22).

    The mode is an event in the journal, derived like the phase: one written truth. It is
    chosen at birth by the task's weight (`el boot … --mode`) and may be changed on the way
    with a reason; the blueprint, the gates and the ladders follow it."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    cur = task_meta(root, task).get("mode", "soft")
    want = (getattr(args, "mode", None) or "").strip().lower()
    if not want:
        print(f"mode      {cur} — {MODE_RU[cur]}")
        for m in MODES:
            print(f"  {'▶' if m == cur else '·'} {m:<7} {MODE_RU[m]}")
        print('сменить   el mode <режим> --why "<почему>" · карта тактов: el blueprint --mode <режим>')
        return 0
    if want not in MODES:
        print(f"режим — одно из {', '.join(MODES)}", file=sys.stderr)
        return 1
    if want == cur:
        print(f"режим уже {cur}")
        return 0
    why = (getattr(args, "why", None) or "").strip()
    journal(root, task, "mode", f"{cur} → {want}" + (f" — {why}" if why else ""),
            {"mode": want, "why": why})
    touch(root, task)
    print(f"режим     {cur} → {want} — {MODE_RU[want]}")
    print("карта     el blueprint — что теперь обязательно · el next — следующий шаг под этот режим")
    return 0


def cmd_ack(args):
    """Leave a past-phase tail AS IS — on purpose, once, with a reason — and stop being nagged.

    «за спиной» names what the protocol now expects and this task never wrote; some of it is
    genuinely not needed here. Saying so is a decision, and a decision is recorded (owner,
    2026-08-22: a warning resolved once must not repeat in every `el next`)."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    what = (args.what or "").strip()
    why = (getattr(args, "why", None) or "").strip()
    if not what or not why:
        print('el ack "<след или area:<область>>" --why "<почему оставляем как есть>"',
              file=sys.stderr)
        return 1
    journal(root, task, "ack", f"{what} — {why}"[:160], {"what": what, "why": why})
    touch(root, task)
    print(f"оставлено {what} — {why}")
    print("         «за спиной» больше не напомнит; передумал — просто допиши след")
    return 0


def cmd_doctor(args):
    """Integrity — the contradictions a state machine must not hold (owner, 2026-08-22).

    Finds, does not fix: criteria all answered but the node still open · two nodes in work ·
    a node closed without a result · a waiting node nobody answered · a phase past execute
    with open nodes · evidence the ledger or the journal points at that is not on disk ·
    pages behind the skill's template · missing page data. ERROR means the state lies to a
    reader; WARN means a gap worth closing."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    errs, warns = [], []
    nodes = nodes_all(tdir)
    acts = [n for n in nodes if node_status(n) in ("active", "waiting")]
    if len(acts) > 1:
        errs.append(f"в работе больше одного узла: {', '.join(n['id'] for n in acts)} — "
                    "активный один: el plan start <узел>")
    vnodes, verdicts, *_c = validation_state(tdir)
    for n in vnodes:
        if n["id"] == "IFR":
            continue
        crits = criteria_of(n)
        if crits and node_open(n) and all(
                verdicts.get((n["id"], i), ("open", ""))[0] != "open"
                for i in range(1, len(crits) + 1)):
            errs.append(f"{n['id']}: все критерии с вердиктом, узел ещё "
                        f"{STATUS_RU.get(node_status(n), '?')} — el plan done {n['id'].lower()} \"<результат>\"")
    for n in nodes:
        if node_status(n) == "done" and not (n.get("result_note") or "").strip():
            warns.append(f"{n['id']} закрыт без результата — что стало правдой? "
                         f"(el plan done {n['id'].lower()} \"<результат>\" --force)")
        if node_status(n) == "waiting":
            warns.append(f"{n['id']} ждёт владельца с {str(n.get('waiting_since') or '')[:16]} — "
                         f'его слово: el accept "…" --for node:{n["id"].lower()}')
        elif n.get("waiting_since"):
            # A stamp that outlived its status (feedback 2026-08-26): written by an older
            # el, or by hand; the next status change of the node clears it.
            warns.append(f"{n['id']}: статус {STATUS_RU.get(node_status(n), node_status(n))}, а "
                         f"waiting_since {str(n.get('waiting_since'))[:16]} остался — устаревший штамп, "
                         f"ложный сигнал; сотрётся следующей сменой статуса узла или убери строку из "
                         f"nodes/{n['id']}.md")
    phase = task_meta(root, task).get("phase", "context")
    if phase in PHASES and PHASES.index(phase) > PHASES.index("execute"):
        left = [n["id"] for n in nodes if node_open(n)]
        if left:
            errs.append(f"фаза {phase}, а узлы не закрыты: {', '.join(left)} — "
                        "el plan done / el plan park")
    for (nid, i), (_st, proof) in verdicts.items():
        m = re.search(r"\[([^\]]+)\]\s*$", proof or "")
        if m and not os.path.exists(os.path.join(tdir, m.group(1))):
            warns.append(f"{nid}.{i}: доказательство {m.group(1)} не на диске")
    try:
        with open(os.path.join(tdir, "journal.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") in ("artifacts", "evidence") and rec.get("files"):
                    for f in rec["files"]:
                        if not os.path.exists(os.path.join(tdir, rec["type"], f)):
                            warns.append(f"{rec['type']}/{f} записан в журнал, но файла нет")
    except OSError:
        pass
    for name, dest in (("overview.html", os.path.join(tdir, "overview.html")),
                       ("index.html", os.path.join(root, "index.html"))):
        try:
            if open(skill_html(name), encoding="utf-8").read() != open(dest, encoding="utf-8").read():
                warns.append(f"{name} отстаёт от шаблона скилла — el ui")
        except OSError:
            warns.append(f"{name} нет на месте — el ui")
    if not os.path.exists(os.path.join(root, "metadata", task + ".js")):
        warns.append("данных страницы нет (metadata/) — el ui")
    print(f"DOCTOR    {task} · фаза {phase} · узлов {len(nodes)}")
    for e in errs:
        print(f"  ERROR   {wrap(e, indent='          ')}")
    for w in warns:
        print(f"  WARN    {wrap(w, indent='          ')}")
    if not errs and not warns:
        print("  чисто — противоречий нет")
    return 1 if errs else 0


def cmd_grant(args):
    """His word that opens autonomy — recorded verbatim (owner, 2026-08-22: «работай сам» и есть
    грант). Bare: the state. The agent does not grant itself anything: the command wants his
    words, and the gates read borrowed words only while a grant stands."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    words = (getattr(args, "words", None) or "").strip()
    if not words:
        for l in autonomy.lines(root, task, full=True) or ["автономии нет — человек её не выдавал"]:
            print(l)
        print('выдать    el grant "<его слова: работай сам · продолжай>" [--until "<до какой остановки>"] '
              '[--no "<чего не делать>"]')
        return 0
    extra = {}
    if getattr(args, "until", None):
        extra["until"] = args.until.strip()
    if getattr(args, "no", None):
        extra["no"] = args.no.strip()
    was = autonomy.state(root, task)
    # His words WHOLE — the conditions live at the end («пока не срежешь 2 ГБ»); a cut grant is
    # a different grant (owner, 2026-08-23: «не обрезать ни в коем случае, даже если очень длинный»).
    journal(root, task, "grant", words, extra)
    touch(root, task)
    print(("автономия выдана" if not (was and was["halt"]) else "автономия продолжена")
          + (f" · до: {extra['until']}" if extra.get("until") else "")
          + (f" · нельзя: {extra['no']}" if extra.get("no") else ""))
    print(f"          «{words}»")
    print('займ      там, где нужен он: el accept … --assumed "<почему>" · el context qa … --assumed · '
          'el think decide … --assumed --undo · леджер: el review')
    print('граница   el halt "<почему дальше без человека нельзя · что нужно>" — и стоп, не «done»')
    if brief_read(os.path.join(root, task)):
        print("листок    brief.md написан ДО этого гранта — его «жди владельца» больше не действует; "
              "перепиши под грант: el brief \"<baseline · замер · лучшее · не повторять · сейчас>\"")
    else:
        print("листок    el brief \"<baseline · замер · лучшее · не повторять · сейчас>\" — перечитывается первым")
    return 0


def cmd_halt(args):
    """«Мой кредит дальше не распространяется» — autonomy stops HERE, with the reason and what
    is needed from the owner. Not «done»: the task stays open and in hand; `el status` prints
    the halt first, so the agent stops, the harness judge sees it, the owner reads it."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    why = (getattr(args, "why", None) or "").strip()
    if not why:
        print('el halt "<почему дальше без человека нельзя · что нужно от него>"', file=sys.stderr)
        return 1
    st = autonomy.state(root, task)
    if not st:
        print("автономии не было — останавливать нечего: просто жди человека (его слово — el accept).",
              file=sys.stderr)
        return 1
    if st["halt"]:
        print(f"уже остановлена: {(st['halt'].get('text') or '')}")
        return 0
    journal(root, task, "halt", why, {"phase": task_meta(root, task).get("phase", "context"),
                                            "debt": len(st["debt"])})
    touch(root, task)
    print(f"АВТОНОМИЯ ОСТАНОВЛЕНА ЗДЕСЬ — {why}")
    print(f"долг слова {len(st['debt'])} · el review · задача открыта и в руке: "
          f"{task} · фаза {task_meta(root, task).get('phase', 'context')}")
    print('дальше    решает человек: el accept "<его слова>" --for … · продолжить автономию: '
          'el grant "<его слова>"')
    return 0


# WHAT A SHEET MUST CARRY (feedback 2026-08-26: a one-line brief held an old result and
# none of: the current retry, the RCA, the owner gate, the open criteria, the next command —
# «the limit is reasonable, the schema is not enforced»). Not refused — a thin sheet beats
# none — but named, part by part, so the agent sees what a returning agent will not know.
BRIEF_PARTS = [
    ("baseline", ("baseline", "базов", "эталон", "исходн")),
    ("замер", ("замер", "меря", "метрик", "measure", "как проверя")),
    ("лучшее", ("лучш", "best", "рекорд")),
    ("не повторять", ("не повторя", "тупик", "не сработа", "не работа", "dead end", "нельзя")),
    ("сейчас", ("сейчас", "now", "текущ", "стоим", "следующ", "next")),
    ("следующая команда", ("el ",)),
]


def brief_nudge(text):
    low = text.lower()
    return [name for name, keys in BRIEF_PARTS if not any(k in low for k in keys)]


# A WORD THAT CARRIES A CHANGE (feedback 2026-08-26, the MLE task: «добавь health, versions,
# datasources, scale instances и rerun» was filed as acceptance; the old and the new
# requirement stayed side by side, verdicts and nodes untouched, the contract ambiguous).
CHANGE_MARKS = ("добавь", "добавить", "ещё ", "еще ", "также", "плюс ", "вместо", "переделай",
                "убери", "замени", "перезапусти", "не так", "add ", "also ", "instead", "remove ",
                "change ", "rerun")


def change_mark(words):
    low = " " + words.lower() + " "
    return next((m.strip() for m in CHANGE_MARKS if m in low), "")


def cmd_brief(args):
    """brief.md — the sheet in the hand (owner, 2026-08-22: «максимальное сжатие для агента, не
    для человека»). What a returning agent must know: where the baseline lies, how we measure,
    what is best and where, what not to repeat, what is now. REWRITTEN whole (the only file
    here that is), bounded by lines and characters — the limit is the discipline: does not
    fit → drop the less important. Pointers and judgements, not state: phase · hand · checklist
    the CLI computes; the sheet holds what cannot be computed."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    text = (getattr(args, "text", None) or "").strip()
    if not text:
        b = brief_read(tdir)
        if not b:
            print("листка нет — el brief \"<baseline и где лежит · чем меряем · лучшее и где · "
                  "не повторять · сейчас>\"")
            print(f"          лимит {BRIEF_LINES} строк / {BRIEF_CHARS} символов · переписывается целиком")
            return 0
        n_l, n_c = len(b.splitlines()), len(b)
        print(f"BRIEF     {task} · {n_l}/{BRIEF_LINES} строк · {n_c}/{BRIEF_CHARS} символов"
              f" · переписан {brief_when(tdir)}"
              + ("  ⚠ больше лимита — ужми" if n_l > BRIEF_LINES or n_c > BRIEF_CHARS else ""))
        print(b)
        thin = brief_nudge(b)
        if thin:
            print(f"тонко     без: {' · '.join(thin)} — вернувшийся агент этого не узнает; перепиши: el brief")
        return 0
    n_l, n_c = len(text.splitlines()), len(text)
    if n_l > BRIEF_LINES or n_c > BRIEF_CHARS:
        print(f"не влезает: {n_l} строк / {n_c} символов · лимит {BRIEF_LINES} / {BRIEF_CHARS} — "
              "убери менее важное: листок держит ориентиры, а не хронику", file=sys.stderr)
        return 1
    write(brief_path(tdir), text + "\n")
    journal(root, task, "brief", f"листок переписан: {n_l} строк", {"ref": "brief.md"})
    touch(root, task)
    print(f"листок    переписан · {n_l}/{BRIEF_LINES} строк · {n_c}/{BRIEF_CHARS} символов · "
          "el и el status печатают его первым")
    thin = brief_nudge(text)
    if thin:
        print(f"тонко     без: {' · '.join(thin)} — вернувшийся агент этого не узнает; "
              "лимит тот же — ужми другое")
    return 0


def cmd_review(args):
    """The ledger of borrowed words — what the agent took for the owner's word, why, and which
    of them his later words have paid. First thing the owner reads when he comes back."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    print(f"REVIEW    {task}")
    for l in autonomy.review_lines(root, task):
        print(l)
    return 0


def harness_guess():
    """Who is writing — by the environment, when the agent did not say (--by)."""
    if os.environ.get("CLAUDECODE"):
        return "Claude Code"
    env = os.environ
    for prefix, name in (("CODEX", "Codex"), ("COPILOT", "Copilot"), ("GITHUB_COPILOT", "Copilot"),
                         ("CURSOR", "Cursor"), ("GEMINI", "Gemini CLI"), ("WINDSURF", "Windsurf"),
                         ("AIDER", "Aider")):
        if any(k.startswith(prefix) for k in env):
            return name
    if env.get("TERM_PROGRAM") == "vscode":
        return "VS Code terminal"
    return "unknown harness"


# THE SHAPE OF A REVIEW (owner, 2026-08-24: «нужно, чтобы писали конкретнее — задать формат»).
# A review the meta-session cannot REPRODUCE is a mood, not a task: it needs the command that
# was run, what it printed, what was expected instead, and what the agent did to get by.
FEEDBACK_FORMAT = [
    "формат   свидетельство, не пересказ — ты видел экран, мета-сессия нет:",
    "           наблюдал: команда ДОСЛОВНО, как набрал → вывод КАК ЕСТЬ, вставь целиком, не своими словами",
    "           до/после: 2–3 команды перед этим и что сделал сразу после — без них не воспроизвести",
    "           ожидал:   что должно было быть вместо этого",
    "           обошёл:   что сделал, чтобы продолжить — или «встал»",
    "           помогло:  что в el сработало хорошо — тоже ценно",
    "         плюс --about <команда> — о какой команде речь · длина не ограничена: --file <путь>",
]


# THE REVIEW PROMPT FOR THE HUMAN (owner, 2026-08-26: «когда мне нужен отзыв от агента по
# работе системы, мне нужен промпт, который я могу скопировать и вставить; когда прошу
# своими словами — выходит то одно, то другое; а руками выпрошенный развёрнутый — понравился»).
# `el feedback prompt` prints it and puts it on the clipboard; the human pastes it into the
# agent's chat, the agent writes the long review and files it with `el feedback --file`.
# Two parts — the TOOL (how `el` behaved on this task: findings with evidence) and the
# CONCEPT (how Elephant should be built: model, layers, what to keep) — because the review
# he liked had exactly these two, and a bare «напиши отзыв» yields neither in full.
PROMPT_HEAD = """\
Ты работал над задачей с Elephant — бухгалтерией больших задач: CLI `el`, хранилище .projects,
фазы context → close, страницы overview.html. Напиши развёрнутый отзыв об Elephant по итогам
ЭТОЙ работы — не заметку, а разбор, по которому мета-сессия сможет чинить инструмент и
пересматривать концепцию, не видя твоего экрана.

Пиши подробно: тезис одним абзацем сверху, дальше развёртка. Конкретика — из этой задачи:
команды дословно, вывод как есть, пути файл:строка. Свидетельство, а не пересказ guide."""

PROMPT_TOOL = """\
ЧАСТЬ 1 — ОБ ИНСТРУМЕНТЕ: как `el` вёл себя на работе
- Главный вывод: что Elephant делает хорошо и где слаб — 2–4 предложения.
- Findings — по убыванию риска (критический · высокий · средний · низкий). Каждый:
  что наблюдал (команда → вывод, файл:строка) · что ожидал · причина, если нашёл её в коде
  (путь:строка) · чем это грозит человеку или агенту. Сначала посмотри pool `el feedback`:
  что уже зафиксировано — сошлись на id, не дублируй.
- Что было ясно — что сработало и помогло; это тоже ценно.
- Что было трудно — где терял время, что сверял вручную, где искал источник истины.
- Границы ответственности: что дефект Elephant/CLI · что протокола и документации · что
  процесса агента (что ты сам должен был сделать иначе) · что специфика самой задачи, а
  не Elephant.
- Приоритетные улучшения — конкретно: команда, поле, правило; нумерованным списком."""

PROMPT_CONCEPT = """\
ЧАСТЬ 2 — О КОНЦЕПЦИИ: как Elephant должен быть устроен
- Что в ядре правильно и трогать не нужно.
- Главная проблема модели: какие понятия смешаны, чего не хватает — с примерами из этой
  задачи (файл:строка).
- Какой должна быть основа: слои, состояния, что из чего выводится — и как должен выглядеть
  идеальный ответ инструмента на «что истинно сейчас, что блокирует, какой следующий
  безопасный шаг»: покажи пример экрана.
- Что изменить в концепции — нумерованно, каждое с «почему» и «как».
- Что оставить без изменений — списком.
- Приоритет изменений: P0 · P1 · P2 · P3.
- Итог одним абзацем: менять ли концепцию, что убрать, что исчезнет само как следствие."""

PROMPT_RULES = """\
ПРАВИЛА
- Развёрнуто: не сжимай ради краткости — лучше длинно и точно. Не смягчай: сломано — так и
  пиши, с доказательством.
- Разделяй «что исторически было», «что истинно сейчас» и «что агент имел право делать»;
  где инструмент это смешивает — это и есть finding.
- Не предлагай замену концепции целиком, если ядро работает — говори, что оставить.
- Язык — тот, на котором идёт разговор; термины и команды — как есть.

КУДА
Покажи отзыв целиком в чате. Затем сохрани его в файл и положи в pool инструмента:
  el feedback --file <путь> --about {about}
Проверь, что `el feedback` показывает записанное."""

PROMPT_KINDS = {"all": "tool-and-concept", "tool": "tool", "concept": "concept"}


def feedback_prompt(kind="all"):
    """The review prompt, whole: head · the parts asked for · rules with the filing line."""
    parts = [PROMPT_HEAD]
    if kind in ("all", "tool"):
        parts.append(PROMPT_TOOL)
    if kind in ("all", "concept"):
        parts.append(PROMPT_CONCEPT)
    parts.append(PROMPT_RULES.format(about=PROMPT_KINDS[kind]))
    return "\n\n".join(parts) + "\n"


def clipboard_put(text):
    """Text → the system clipboard. Returns the tool that took it, or None: no tool found,
    or ELEPHANT_CLIPBOARD=off (the differential test sets it — a test run must not touch
    the human's clipboard). Never raises: the prompt is printed anyway."""
    if os.environ.get("ELEPHANT_CLIPBOARD", "").strip().lower() in ("off", "0", "no", "none"):
        return None
    import subprocess
    for cmd in (["pbcopy"], ["wl-copy"], ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"], ["clip"]):
        if not shutil.which(cmd[0]):
            continue
        try:
            subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return cmd[0]
        except Exception:
            continue
    return None


def feedback_nudge(text):
    """[] when the review carries what a fix needs; else the lines that say what is missing.
    Never refuses — a thin review is better than none — but says out loud that it is thin."""
    low = text.lower()
    missing = []
    if not any(k in low for k in ("ожидал", "expected", "должн", "should", "вместо", "instead")):
        missing.append("ожидал")
    if not any(k in low for k in ("el ", "команд", "command", "напечат", "printed", "returned", "вернул", "rc")):
        missing.append("наблюдал (команда → вывод)")
    if not any(k in low for k in ("до этого", "перед", "потом", "после", "затем", "before", "after", "then")):
        missing.append("до/после (что делал перед и сразу после)")
    if len(text) < 160:
        missing.append("подробности — короче двух предложений не воспроизвести")
    return missing


def cmd_feedback(args):
    """The tool's own inbox (owner, 2026-08-22: «команда — отзыв от агента, чтобы он клал его
    в какое-то место, а мета-сессия потом читала, разбиралась, чинила и удаляла»).

    An agent that tripped over `el` — or heard the owner's verdict on it — writes it HERE:
    one file per review in the skill's feedback/ folder (with the tool, never in a storage:
    guide §3, the border). The folder is the POOL of improvement work for the meta-session,
    which reads, fixes the CLI, deletes the file. Why a pool and not a chat remark: the
    agent that feels the pain is not the one that will fix it, and a remark dies with the
    session; a file travels with the tool to the next machine and the next meta-session.

      el feedback                                   the pool
      el feedback "<text>" [--about <cmd>] [--by …] a new review — the agent's own experience
      el feedback "<his words>" --from user         the owner's verdict, verbatim
      el feedback --file <path>                     a long letter written elsewhere
      el feedback <id>                              one review in full
      el feedback done <id>                         remove it — after the fix
      el feedback prompt [tool|concept]             THE PROMPT for the human: printed and put on
                                                    the clipboard, pasted into an agent's chat"""
    words = list(getattr(args, "words", None) or [])
    fdir = feedback_dir()
    ids = feedback_ids()
    if words and words[0] == "prompt":
        kind = (words[1] if len(words) > 1 else "all").strip().lower()
        if len(words) > 2 or kind not in PROMPT_KINDS:
            print("el feedback prompt [tool|concept] — об инструменте · о концепции · без слова: обе части",
                  file=sys.stderr)
            return 1
        text = feedback_prompt(kind)
        took = clipboard_put(text)
        if took:
            print(f"в буфере  ✓ скопировано ({took}) — вставь агенту в чат; он напишет отзыв и положит "
                  "его в pool: el feedback")
        elif os.environ.get("ELEPHANT_CLIPBOARD", "").strip().lower() in ("off", "0", "no", "none"):
            print("в буфере  нет — ELEPHANT_CLIPBOARD=off; скопируй текст ниже с экрана")
        else:
            print("в буфере  нет — не нашёл pbcopy · wl-copy · xclip · xsel · clip; скопируй текст ниже с экрана")
        print(f"части     {'об инструменте + о концепции' if kind == 'all' else ('об инструменте' if kind == 'tool' else 'о концепции')}"
              " · только одна: el feedback prompt tool | concept")
        print()
        print(text, end="")
        return 0
    if words and words[0] == "done":
        if len(words) < 2:
            print("el feedback done <id>", file=sys.stderr)
            return 1
        fid = feedback_resolve(words[1])
        if not fid:
            print(f"нет отзыва {words[1]} · pool: {', '.join(ids) or '—'}", file=sys.stderr)
            return 1
        os.remove(os.path.join(fdir, fid + ".md"))
        left = feedback_ids()
        # feedback/ is outside git (.gitignore, 2026-08-24): once removed, the text lives only
        # in the meta-session that read it — say so instead of promising a history.
        print(f"удалён    {fid} — разобран; папка feedback/ вне git, текст остался только у "
              "мета-сессии, которая его прочла")
        print("          если это было решение — строка в ideas.md «Решённые»")
        print(f"в pool    {len(left)}" + (": " + ", ".join(left) if left else " — пусто"))
        return 0
    src_file = (getattr(args, "file", None) or "").strip()
    text = " ".join(words).strip()
    if len(words) == 1 and not src_file and feedback_looks_like_id(words[0]):
        # A lone id-shaped word is a LOOKUP — and a lookup that finds nothing is an error,
        # not a one-word review named «3».
        fid = feedback_resolve(words[0])
        if not fid:
            print(f"нет отзыва {words[0]} · pool: {', '.join(ids) or '—'}", file=sys.stderr)
            return 1
        meta, body = fm_read(os.path.join(fdir, fid + ".md"))
        print(f"ОТЗЫВ     {fid}")
        print("          " + " · ".join(f"{k}: {v}" for k, v in meta.items()))
        print()
        print(body.rstrip())
        return 0
    if src_file:
        try:
            text = open(os.path.expanduser(src_file), encoding="utf-8").read().strip()
        except OSError:
            print(f"не читается: {src_file}", file=sys.stderr)
            return 1
    if text:
        who = (getattr(args, "from_", None) or "agent").strip().lower()
        if who not in ("agent", "user"):
            print("--from agent|user — чей это отзыв: агента или слова человека", file=sys.stderr)
            return 1
        about = (getattr(args, "about", None) or "").strip()
        # Numbered past the highest existing number, so a deleted review's number is not
        # reused and an old mention of «007» cannot point at a newer file.
        top = 0
        for i in ids:
            m = re.search(r"-(\d{3})-", i)
            if m:
                top = max(top, int(m.group(1)))
        slug = norm_id(about) if about else ""
        stem = f"{now_iso()[:10]}-{top + 1:03d}-{who}" + (f"-{slug}" if slug else "")
        root = find_root()
        task = current_task(root) if root else None
        meta = {"date": now_iso()[:16].replace("T", " "), "from": who,
                "by": (getattr(args, "by", None) or "").strip() or harness_guess(),
                "project": project_root(), "task": task or "—", "about": about or "—"}
        path = os.path.join(fdir, stem + ".md")
        fm_write(path, meta, text)
        print(f"записан   {stem}")
        print(f"          {path}")
        if meta["by"] == "unknown harness":
            print('          кто ты — не определилось по окружению; в следующий раз: --by "<harness>"')
        print(f"в pool    {len(ids) + 1} · читает и чинит мета-сессия над скиллом: el feedback")
        thin = feedback_nudge(text) if who == "agent" else []
        if thin:
            print(f"тонко     не хватает: {' · '.join(thin)} — допиши тем же id: "
                  f'el feedback "<ещё>" (новый файл) или правь {stem}.md руками')
            for l in FEEDBACK_FORMAT:
                print(l)
        return 0
    if not ids:
        print("POOL      пусто — отзывов об инструменте нет")
        print('оставить  el feedback "<наблюдал → до/после → ожидал → обошёл → помогло>" [--about <команда>] [--by "<кто ты>"]')
        for l in FEEDBACK_FORMAT:
            print(l)
        print("          --from user — слова человека дословно · --file <путь> — длинное письмо")
        print("промпт    человеку: el feedback prompt [tool|concept] — в буфер обмена, вставить агенту в чат →"
              " развёрнутый отзыв об инструменте и о концепции")
        return 0
    print(f"POOL      {len(ids)} отзыв(ов) об инструменте · {fdir}")
    for fid in ids:
        meta, body = fm_read(os.path.join(fdir, fid + ".md"))
        first = next((l.strip().lstrip("#").strip() for l in body.splitlines() if l.strip()), "")
        print(f"  {fid}")
        print(f"    {meta.get('from', '?')} · {meta.get('by', '?')} · {meta.get('date', '?')}"
              f" · о: {meta.get('about', '—')} · задача: {meta.get('task', '—')}")
        print(f"    {first[:110]}")
    print('читать    el feedback <id> · разобрал и починил: el feedback done <id> · новый: el feedback "<текст>"')
    print("промпт    человеку: el feedback prompt [tool|concept] — в буфер обмена, вставить агенту в чат")
    return 0


def cmd_onboard(_args):
    """Bare `el` — THE ONBOARDING (owner, 2026-08-21): the tool IS the instruction.

    Any agent in any harness, told nothing but "запусти el", must land here and understand:
    what this is, what is here right now, and which command to run next. The skill is only
    a door; the knowledge lives in the CLI and comes out DOSED — this screen, then
    blueprint for the whole contract, then next for the current step. That is what makes
    switching engines free: the context sits in the files, not in the agent."""
    print("🐘 ELEPHANT — бухгалтерия больших задач: всё состояние живёт в файлах на диске,")
    print("   а не в памяти сессии. Человек решает · агент думает и записывает · el помнит")
    print("   и показывает. Любой агент продолжает работу с того места, где остановился")
    print("   предыдущий — хоть завтра, хоть в другом инструменте.\n")
    root = find_root()
    if not root:
        print("  здесь сейчас   хранилища проектов нет — эта папка Elephant ещё не видела")
        print(f"                 (искал маркер .elephant вверх от {os.getcwd()}; если harness")
        print("                 сбрасывает cwd между вызовами — `cd <проект> && el` одной строкой,")
        print("                 либо ELEPHANT_DIR=<путь к .projects>)")
        print('  начать         el boot "<задача>" --id <имя-3-5-слов> --raw "<его слова о')
        print('                 задаче>" — заведёт хранилище и первый проект')
    else:
        tasks = tasks_of(root)
        metas = [task_meta(root, t) for t in tasks]
        open_n = sum(1 for m in metas if m.get("status", "active") == "active")
        cur = current_task(root)
        print(f"  здесь сейчас   хранилище {root}")
        print(f"                 проектов: открыто {open_n} · закрыто {len(tasks) - open_n}")
        if cur:
            cm = task_meta(root, cur)
            print(f"  в руке         {cur} · фаза {phase_no(cm.get('phase', 'context'))}/8 "
                  f"{cm.get('phase', 'context')}")
            print(f"                 {cm.get('name', '')[:70]}")
            for l in autonomy.lines(root, cur):
                print(f"  {l}")
            for l in return_lines(root, cur):
                print(f"  {l}")
            for l in stale_lines(root, cur, os.path.join(root, cur)):
                print(f"  {l}")
            # THE SHEET FIRST (owner, 2026-08-22): a returning agent reads brief.md before
            # anything else — baseline, best, what not to repeat, what is now.
            b = brief_read(os.path.join(root, cur))
            if b:
                print(f"  листок (brief.md · переписан {brief_when(os.path.join(root, cur))}) — читать первым:")
                for bl in b.splitlines():
                    print(f"    {bl}")
                bs = autonomy.brief_stale_line(root, cur, indent="    ")
                if bs:
                    print(bs)
        else:
            live = open_tasks(root)
            if live:
                print(f"  в руке         ничего (idle) · взять: el use <id> — открытые: "
                      f"{', '.join(live[:4])}{' …' if len(live) > 4 else ''}")
            else:
                print('  в руке         ничего — открытых задач нет · новая: el boot "<задача>" --id <имя>')
        print("  список         el projects — все проекты; взять в руку: el use <id>")
        print(f"  где el         {os.path.join(SKILL_ROOT, 'cli', 'el.py')} · замер: "
              f"bash {os.path.join(SKILL_ROOT, 'cli', 'detect.sh')}")
        lessons = lessons_read(root)
        if lessons:
            print(f"\n  уроки ({len(lessons)}) — на этом месте уже спотыкались; прочитай, прежде чем работать:")
            for l in lessons[-7:]:
                print(f"    {l}")
            if len(lessons) > 7:
                print(f"    … остальные в {lessons_path(root)}")
    # THE READING LADDER — knowledge in doses, each step one screen (owner, 2026-08-22):
    # the big picture once, the phase card where the agent stands, the commands by name.
    ph = None
    if root:
        cur = current_task(root)
        ph = task_meta(root, cur).get("phase") if cur else None
    print("\n  порядок        план раньше работы: узел заводится ДО первого шага (el plan new → "
          "el plan start), не после — бумаги задним числом видны по штампам")
    print("\n  читать по порядку — каждая ступень влезает в один экран:")
    print("    1. el blueprint            big picture: 8 фаз, гейты, правила — один раз, первым")
    if ph:
        print(f"    2. el blueprint {ph:<10} такты фазы, в которой стоишь сейчас; остальные —")
        print("                               когда войдёшь (el forward сам покажет карточку)")
    else:
        print("    2. el blueprint <фаза>     такты фазы, в которой стоишь: el blueprint context")
        print("                               для первой; дальше el forward сам покажет карточку")
    print("    3. el help                 команды · el help <команда|группа> — одна")
    print("  вернулся       el resume — карточка возврата: листок · что за тобой · узел · gate · один ход")
    print("  где мы         el status — фаза, чек-лист следов, что заполнено")
    print("  что дальше     el next — конкретный следующий шаг и его команда")
    print("  человеку       el blueprint full — весь контракт одним списком (длинный)")
    # The tool is under work too: what hurt goes into its own inbox, not into the void.
    pool = feedback_ids()
    print('  инструмент     споткнулся об el — el feedback "<что мешало · что помогло>"; слова')
    print("                 человека об инструменте — --from user. Это pool улучшений скилла"
          + (f" (сейчас {len(pool)})" if pool else ""))
    return 0
