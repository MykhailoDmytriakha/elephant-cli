"""Phase 2 — THINK, as behaviour: forks and their options, the decision, the open box
of instruments, a deliberate skip. The ladder is protocol.THINK_STEPS.
"""
import os, re, shutil, sys
from .protocol import THINK_FILES, THINK_MIN, THINK_STEPS, THINK_TOOLS, required_in
from . import autonomy
from .state import (pick_task, current_task, journal, now_iso, require_root, resolve_task, task_mode,
                    touch, write)
from .term import wrap
from .amend import amend_doc, is_amendment


def think_step(tdir, mode=None):
    """The first think step that is not DONE. "Done" is "the file exists" — except the
    decision: decisions.md appears the moment a fork is OPENED, so by file alone the step
    looked closed while forks were still open, and `el next` lost the step's instruction
    (how to close a fork, --words verbatim, --fixed) right when it was needed (2026-08-21).
    The decision step is done when no fork is open. A step not required under the task's
    MODE is skipped while its file is absent."""
    mode = mode or task_mode(tdir)
    for key, rel, title, src, do, cmd in THINK_STEPS:
        exists = os.path.exists(os.path.join(tdir, rel))
        if key == "decision" and exists and any(not f["decision"] for f in forks_read(tdir)):
            return key, rel, title, src, do, cmd
        if not exists and not required_in(THINK_MIN.get(key, "soft"), mode):
            continue
        if not exists:
            return key, rel, title, src, do, cmd
    return None


def forks_read(tdir):
    """Parse the decision file — the LEDGER of forks. Plain markdown, because state must
    open in a notepad.

        ## РАЗВИЛКА <id> · <вопрос>   [решает: owner|agent]
        решить: <what exactly the owner must decide at this gate>       (optional)
        превью: thinking/previews/<id>.html                            (optional)
        - вариант · цена: ...            (a `←` marks the recommended one)
          модель: <what this variant IS>                               (optional, indented)
          falsifier: <which observation would kill it>                 (optional, indented)
        рекомендация: <the agent's working recommendation before his choice>   (optional)
        решение: <вариант> — <кем и чем обосновано>   (or `—` while open)
        зафиксировано: <what his word settled>                         (optional)

    The optional lines are THE DOSSIER (owner, 2026-08-21, from the hand-written options.md
    of a live project he liked): a fork he decides comes with a preview he can TOUCH, every
    option names its model, its price and its falsifier, the agent states a recommendation
    and the exact questions he must answer, and his word fixes a basis. A file without them
    reads exactly as before."""
    path = os.path.join(tdir, THINK_FILES["decision"])
    if not os.path.exists(path):
        return []
    forks, cur = [], None
    for line in open(path, encoding="utf-8"):
        m = re.match(r"##\s*РАЗВИЛКА\s+(\S+)\s*·\s*(.*?)\s*\[решает:\s*(\w+)\]", line)
        if m:
            cur = {"id": m.group(1), "q": m.group(2), "who": m.group(3),
                   "options": [], "details": [], "decision": None,
                   "decide": "", "preview": "", "recommendation": "", "fixed": "",
                   "fidelity": ""}
            forks.append(cur)
            continue
        if cur is None:
            continue
        low = line.lower()
        if line.startswith("- "):
            cur["options"].append(line[2:].strip())
            cur["details"].append({"model": "", "falsifier": ""})
        elif line.startswith("  ") and cur["details"] and \
                low.strip().startswith(("модель:", "falsifier:")):
            key, _, val = line.strip().partition(":")
            cur["details"][-1]["model" if key.strip().lower() == "модель" else "falsifier"] = \
                val.strip()
        elif low.startswith("решение:"):
            val = line.split(":", 1)[1].strip()
            cur["decision"] = None if val in ("—", "-", "") else val
        elif low.startswith("решить:"):
            cur["decide"] = line.split(":", 1)[1].strip()
        elif low.startswith("превью:"):
            cur["preview"] = line.split(":", 1)[1].strip()
        elif low.startswith("рекомендация:"):
            cur["recommendation"] = line.split(":", 1)[1].strip()
        elif low.startswith("зафиксировано:"):
            cur["fixed"] = line.split(":", 1)[1].strip()
        elif low.startswith("обязательность:"):
            cur["fidelity"] = line.split(":", 1)[1].strip()
    return forks


def _forks_path(root, task):
    return os.path.join(root, task, THINK_FILES["decision"])


def _forks_write(root, task, forks):
    body = ("# Развилки и выбор\n\n_Развилка без записанного выбора уедет в план как "
            "догадка. Помеченную `owner` закрывает ЕГО слово._\n")
    for f in forks:
        body += f"\n## РАЗВИЛКА {f['id']} · {f['q']}   [решает: {f['who']}]\n"
        if f.get("decide"):
            body += f"решить: {f['decide']}\n"
        if f.get("preview"):
            body += f"превью: {f['preview']}\n"
        details = f.get("details") or []
        for i, o in enumerate(f["options"]):
            body += f"- {o}\n"
            d = details[i] if i < len(details) else {}
            if d.get("model"):
                body += f"  модель: {d['model']}\n"
            if d.get("falsifier"):
                body += f"  falsifier: {d['falsifier']}\n"
        if f.get("recommendation"):
            body += f"рекомендация: {f['recommendation']}\n"
        body += f"решение: {f['decision'] or '—'}\n"
        if f.get("fixed"):
            body += f"зафиксировано: {f['fixed']}\n"
        if f.get("fidelity"):
            body += f"обязательность: {f['fidelity']}\n"
    write(_forks_path(root, task), body)


def _dossier_append(root, task, text):
    """Append one piece of narrative to thinking/options.md — THE DOSSIER of the forks, gate by
    gate, in the shape the owner liked (2026-08-21). Append only, never rewritten: a hand-written
    options.md keeps everything it had and simply grows. This is the `forks` step's trace, so
    the step closes by the commands and not by a file written by hand."""
    path = os.path.join(root, task, THINK_FILES["forks"])
    body = open(path, encoding="utf-8").read().rstrip("\n") if os.path.exists(path) else (
        "# Какие есть пути и чем платит каждый\n\n_Досье развилок, гейт за гейтом: вопрос и "
        "кто решает · превью, которое можно потрогать · варианты с моделью, ценой и falsifier "
        "· рекомендация до выбора · что должен решить владелец · его решение дословно и что им "
        "зафиксировано. Пишется командами `el think fork` / `el think decide`; леджер — "
        "decisions.md._")
    write(path, body + "\n" + text)


def _copy_preview(tdir, fid, src):
    """Copy a preview INTO the project — thinking/previews/<fork>.<ext> (or a folder). The link
    then outlives any scratch folder the preview was built in, travels with the storage, and the
    page opens it by a relative href. Returns the relative path, or None if the source is missing."""
    src = os.path.expanduser(src)
    if not os.path.exists(src):
        return None
    dst_dir = os.path.join(tdir, "thinking", "previews")
    os.makedirs(dst_dir, exist_ok=True)
    if os.path.isdir(src):
        dst = os.path.join(dst_dir, fid)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        if os.path.exists(os.path.join(dst, "index.html")):
            dst = os.path.join(dst, "index.html")
    else:
        ext = os.path.splitext(src)[1] or ".html"
        dst = os.path.join(dst_dir, fid + ext)
        shutil.copyfile(src, dst)
    return os.path.relpath(dst, tdir).replace(os.sep, "/")


def cmd_fork(args):
    """Open a fork, or add to it — an option, a preview, a recommendation, what to decide.

    Counting is not thinking — the CLI never judges whether an option is good, only that the
    field was opened wide enough to choose from. THE DOSSIER (owner, 2026-08-21, from the
    hand-written options.md of a live project): a fork he decides comes with a PREVIEW he can
    touch — one interactive page with every variant side by side, real content — copied into
    the project so the page can open it; each option names its model, its price and its
    falsifier; the agent states a working recommendation and the exact questions he must
    answer. One command writes both files: the ledger (decisions.md) and the narrative
    (options.md)."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    forks = forks_read(tdir)
    fid = args.id
    # --option/--cost/--model/--falsifier parse as APPEND lists for one reason: repeating
    # them in ONE call used to collapse silently into the last value, and the agent believed
    # every option was recorded (feedback pool, 2026-08-22). One option per call — several
    # at once is an explicit refusal, not a quiet loss.
    multi = [k for k in ("option", "cost", "model", "falsifier")
             if len(getattr(args, k, None) or []) > 1]
    if multi:
        print(f"по нескольку --{' · --'.join(multi)} в одном вызове нельзя — "
              "один вариант на вызов:", file=sys.stderr)
        print('  el think fork <id> --option "<вариант>" --cost "…" [--model "…"] '
              '[--falsifier "…"]  — и так на каждый вариант', file=sys.stderr)
        return 1
    for k in ("option", "cost", "model", "falsifier"):
        v = getattr(args, k, None)
        setattr(args, k, v[0] if v else None)
    option = getattr(args, "option", None)
    preview = getattr(args, "preview", None)
    recommendation = (getattr(args, "recommendation", None) or "").strip()
    decide = (getattr(args, "decide", None) or "").strip()
    extras = bool(option or preview or recommendation or decide)
    # Adding to a fork needs only its id — the question was given when the fork opened. The
    # first version demanded the positional text in both modes and silently printed usage
    # instead of recording, so twelve options in a row went nowhere. Caught on first use.
    if not fid or (not args.text and not extras):
        print('el think fork <id> "<вопрос развилки>" --who owner|agent --decide "<что решить>"',
              file=sys.stderr)
        print('el think fork <id> --option "<вариант>" --cost "<чем платим>" [--model "<что это>"] '
              '[--falsifier "<что убьёт>"] [--recommend]', file=sys.stderr)
        print("el think fork <id> --preview <html|папка>   ·   --recommendation \"<что советую>\"",
              file=sys.stderr)
        return 1
    cur = next((f for f in forks if f["id"] == fid), None)
    done = []
    if args.text:
        if cur:
            print(f"развилка {fid} уже есть: {cur['q']}")
            if not extras:
                return 0
        else:
            who = (getattr(args, "who", None) or "agent").lower()
            if who not in ("owner", "agent"):
                print("--who: owner или agent", file=sys.stderr)
                return 1
            cur = {"id": fid, "q": args.text.strip(), "who": who, "options": [], "details": [],
                   "decision": None, "decide": "", "preview": "", "recommendation": "", "fixed": ""}
            forks.append(cur)
            _dossier_append(root, task,
                            f"\n## РАЗВИЛКА {fid} · {cur['q']}   [решает: {who}]\n")
            journal(root, task, "fork", f"{fid}: {cur['q'][:90]}", {"who": who})
            done.append(f"развилка {fid} заведена · решает: {who}")
    if not cur:
        print(f"нет развилки {fid} — сперва заведи её", file=sys.stderr)
        return 1
    if decide:
        cur["decide"] = decide
        _dossier_append(root, task, f"\n**Что должен решить владелец:** {decide}\n")
        done.append("что решить — записано")
    if preview:
        rel = _copy_preview(tdir, fid, preview)
        if not rel:
            print(f"нет файла превью: {preview}", file=sys.stderr)
            return 1
        cur["preview"] = rel
        _dossier_append(root, task,
                        f"\nИнтерактивное превью: `{rel}` — открыть в браузере, переключать "
                        "варианты, потрогать; ссылка есть и на странице проекта.\n")
        journal(root, task, "preview", f"{fid}: {rel}", {"fork": fid})
        done.append(f"превью → {rel}")
    if option:
        if not args.cost:
            print("--cost обязателен: вариант без названной цены это не вариант, а лозунг",
                  file=sys.stderr)
            return 1
        mark = "  ← РЕКОМЕНДУЮ" if getattr(args, "recommend", False) else ""
        cur["options"].append(f"{option.strip()} · цена: {args.cost.strip()}{mark}")
        model = (getattr(args, "model", None) or "").strip()
        falsifier = (getattr(args, "falsifier", None) or "").strip()
        cur.setdefault("details", []).append({"model": model, "falsifier": falsifier})
        piece = f"\n### {option.strip()}\n\n**Платит:** {args.cost.strip()}{mark}\n"
        if model:
            piece += f"\n**Модель:** {model}\n"
        if falsifier:
            piece += f"\n**Falsifier:** {falsifier}\n"
        _dossier_append(root, task, piece)
        done.append(f"развилка {fid}: {len(cur['options'])} вариант(ов)")
        if len(cur["options"]) < 3:
            done.append("         меньше трёх — поле ещё не открыто (спека, фаза Думать)")
    if recommendation:
        cur["recommendation"] = recommendation
        _dossier_append(root, task,
                        f"\n**Рабочая рекомендация до выбора владельца:** {recommendation}\n")
        done.append("рекомендация — записана")
    _forks_write(root, task, forks)
    touch(root, task)
    for line in done:
        print(line)
    if args.text and not option:
        print(f'дальше   el think fork {fid} --option "<вариант>" --cost "<чем платим>" '
              '--model "<что это>" --falsifier "<что убьёт>"  ·  --preview <html>')
    return 0


def cmd_decide(args):
    """Close a fork with a CHOICE — and say who made it.

    A fork marked `owner` needs his words. Not a paraphrase, not "he agreed": the sentence he
    said. This is the same honest limit as `el accept` — it cannot prove he spoke, but a
    forgery is stored verbatim, printed back, and journalled, so it is visible on his next
    read. --fixed writes what his word SETTLED — the basis the next gate stands on."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    forks = forks_read(tdir)
    cur = next((f for f in forks if f["id"] == args.id), None) if args.id else None
    if not cur:
        print(f"нет развилки {args.id}; есть: {', '.join(f['id'] for f in forks) or '— ни одной'}",
              file=sys.stderr)
        return 1
    if not args.choice:
        print('el think decide <fork> "<вариант>" --words "<его слова>" | --why "<почему сам>"',
              file=sys.stderr)
        return 1
    assumed = (getattr(args, "assumed", None) or "").strip()
    undo = (getattr(args, "undo", None) or "").strip()
    if cur["who"] == "owner" and not getattr(args, "words", None) and not assumed:
        print(f"развилку {cur['id']} решает ВЛАДЕЛЕЦ — нужны его слова, а не твой вывод.",
              file=sys.stderr)
        print('  el think decide %s "<вариант>" --words "<что он сказал>"' % cur["id"],
              file=sys.stderr)
        print('  его нет, автономия выдана — займи слово: --assumed "<почему так>" --undo "<как откатить>"',
              file=sys.stderr)
        print("  решил сам вопреки пометке — перезаведи развилку с --who agent и объясни почему",
              file=sys.stderr)
        return 1
    # A BORROWED DECISION (autonomy, owner 2026-08-22): his fork, he is away, the grant
    # stands — the agent chooses, says why, and says how to reverse it: in autonomy the
    # reversible path is preferred, and the reversal is written at the moment of choice.
    if assumed:
        if not autonomy.guard(root, task, "займ решения"):
            return 1
        if not undo:
            print('займ решения требует --undo "<как откатить, если он решит иначе>"', file=sys.stderr)
            return 1
    if len(cur["options"]) < 3 and not getattr(args, "narrow", False):
        print(f"у развилки {cur['id']} только {len(cur['options'])} вариант(ов).", file=sys.stderr)
        print("  меньше трёх значит поле не открыто — доложи варианты,", file=sys.stderr)
        print('  либо закрой сознательно: --narrow "<почему остальные отпали>"', file=sys.stderr)
        return 1
    by = "владелец" if getattr(args, "words", None) else ("агент (ЗАЙМ СЛОВА)" if assumed else "агент")
    just = (f'«{args.words.strip()}»' if getattr(args, "words", None)
            else (assumed or (args.why or "").strip() or "без объяснения"))
    cur["decision"] = f"{args.choice.strip()} — {by}: {just}" + (f" · откат: {undo}" if undo else "")
    if getattr(args, "narrow", False):
        cur["decision"] += f" · вариантов меньше трёх сознательно: {args.narrow}"
    fixed = (getattr(args, "fixed", None) or "").strip()
    if fixed:
        cur["fixed"] = fixed
    # FIDELITY of the accepted preview (owner, 2026-08-22): the first build of the Settings
    # pilot drifted from the previews he had chosen, because nobody had said how binding
    # they were. Four honest levels, named at the moment of choice.
    FIDELITY = ("conceptual", "layout", "visual", "production")
    fid = (getattr(args, "fidelity", None) or "").strip().lower()
    if fid and fid not in FIDELITY:
        print(f"--fidelity: одно из {', '.join(FIDELITY)}", file=sys.stderr)
        return 1
    if fid:
        cur["fidelity"] = fid
    _forks_write(root, task, forks)
    stamp = now_iso()[:16].replace("T", " ")
    if getattr(args, "words", None):
        piece = (f"\n## Решение владельца по {cur['id']} — {stamp}\n\n> {args.words.strip()}\n\n"
                 f"Выбрано: {args.choice.strip()}\n")
    elif assumed:
        piece = (f"\n## Решение по {cur['id']} — {stamp} (агент · ЗАЙМ СЛОВА)\n\n"
                 f"{args.choice.strip()} — почему так принял: {assumed}\n\nОткат: {undo}\n")
    else:
        piece = (f"\n## Решение по {cur['id']} — {stamp} (агент)\n\n{args.choice.strip()} — "
                 f"{(args.why or '').strip() or 'без объяснения'}\n")
    if fixed:
        piece += f"\n**Зафиксированная основа:** {fixed}\n"
    if fid:
        piece += (f"\n**Обязательность превью:** {fid} — " + {
            "conceptual": "обязательна идея, внешний вид может измениться",
            "layout": "обязательны структура, порядок и размеры областей",
            "visual": "обязательны layout, controls, плотность, цвета и композиция",
            "production": "реализация совпадает максимально; отклонение согласуется заново"}[fid] + "\n")
    _dossier_append(root, task, piece)
    journal(root, task, "decision", f"{cur['id']} → {args.choice.strip()[:60]}", {"by": by})
    if assumed:
        journal(root, task, "assume", f"{cur['id']}: {args.choice.strip()}",
                {"phase": "think", "for": f"design:{cur['id']}", "why": assumed, "undo": undo})
    touch(root, task)
    left = [f["id"] for f in forks if not f["decision"]]
    print(f"решено   {cur['id']} → {args.choice.strip()}")
    if fixed:
        print(f"зафиксировано  {wrap(fixed, indent='               ')}")
    if fid:
        print(f"обязательность {fid} — узел плана, строящий этот UI, пишет «{cur['id']}» в inputs "
              "и сверяет as-built с превью перед закрытием")
    elif cur.get("preview"):
        print("подсказка  у развилки есть превью — назови его обязательность: "
              "--fidelity conceptual|layout|visual|production")
    print(f"осталось {', '.join(left) if left else '— все развилки закрыты'}")
    return 0


def cmd_forks(args):
    """The state of every fork: who decides, how many options, what was chosen."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    forks = forks_read(os.path.join(root, task))
    if not forks:
        print("развилок не заведено.")
        print('запись   el think fork <id> "<вопрос>" --who owner|agent')
        return 0
    for f in forks:
        mark = "✓" if f["decision"] else "▶"
        print(f"\n{mark} {f['id']} · {f['q']}   [решает: {f['who']}]  "
              f"{len(f['options'])} вариант(ов)")
        if f.get("decide"):
            print(f"    решить:  {wrap(f['decide'], indent='             ')}")
        if f.get("preview"):
            print(f"    превью:  {f['preview']}")
        details = f.get("details") or []
        for i, o in enumerate(f["options"]):
            print(f"    · {wrap(o, indent='      ')}")
            d = details[i] if i < len(details) else {}
            if d.get("model"):
                print(f"        модель:    {wrap(d['model'], indent='                   ')}")
            if d.get("falsifier"):
                print(f"        falsifier: {wrap(d['falsifier'], indent='                   ')}")
        if f.get("recommendation"):
            print(f"    рекомендация: {wrap(f['recommendation'], indent='                  ')}")
        print(f"    решение: {f['decision'] or '— ОТКРЫТА'}")
        if f.get("fixed"):
            print(f"    зафиксировано: {wrap(f['fixed'], indent='                   ')}")
        if f.get("fidelity"):
            print(f"    обязательность превью: {f['fidelity']}")
    left = [f["id"] for f in forks if not f["decision"]]
    print(f"\nоткрыто  {', '.join(left) if left else '— ни одной'}")
    return 0


def cmd_think_step(args):
    """Write one free-text step of the think ladder — `el think mirror "…"` and the rest.

    Until 2026-08-21 these eleven steps had no command at all: the agent wrote the files by
    hand, the very two-paths-for-one-operation the tool exists to prevent (and the context
    ladder had had its commands for a day). Bare, it prints the step. Text appends — a step
    is rarely finished in one sitting. CRYSTAL is special on purpose: every record lands under
    its own date (and the fork or finding it leans on, --ref), because the crystal is the
    PROCESS of crystallisation and must read as a chain — how the solution ripened, not only
    what it became. Past think, any of them is an AMENDMENT (amend.py)."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    key = args.step_key
    title = next(t for k, _r, t, *_x in THINK_STEPS if k == key)
    rel = THINK_FILES[key]
    path = os.path.join(root, task, rel)
    if not getattr(args, "text", None):
        if os.path.exists(path):
            print(open(path, encoding="utf-8").read().rstrip())
            return 0
        print(f'нечего показывать — напиши: el think {args.step_name} "<текст>"', file=sys.stderr)
        return 1
    if is_amendment(root, task, rel):
        return 0 if amend_doc(root, task, rel, title, args) else 1
    refs = [r.strip() for r in (getattr(args, "ref", None) or []) if r.strip()]
    if key == "crystal":
        body = open(path, encoding="utf-8").read().rstrip() if os.path.exists(path) else (
            f"# {title}\n\n_Записи по ходу думания: что прояснилось, что сдвинулось, почему "
            "— со ссылкой на развилку или находку. Последняя запись — решение, каким оно "
            "выкристаллизовалось; по цепочке видно, как к нему шли._")
        head = now_iso()[:16].replace("T", " ") + (" · " + " · ".join(refs) if refs else "")
        body += f"\n\n## {head}\n\n{args.text.strip()}\n"
        note = "запись"
    elif os.path.exists(path):
        body = open(path, encoding="utf-8").read().rstrip() + "\n\n" + args.text.strip() + "\n"
        if refs:
            body = body.rstrip("\n") + "\n" + "".join(f"- основание: `{r}`\n" for r in refs)
        note = "дописано"
    else:
        body = f"# {title}\n\n{args.text.strip()}\n"
        if refs:
            body += "".join(f"- основание: `{r}`\n" for r in refs)
        note = "записано"
    write(path, body)
    journal(root, task, key, args.text.strip()[:80], {"refs": refs} if refs else None)
    touch(root, task)
    print(f"{note:<9} {rel}")
    print("next      el next — следующий шаг лестницы")
    return 0


def cmd_think_tools(args):
    """Print the open box of thinking instruments, and record which were taken.

    The spec names "one favourite instrument for everything" as an anti-pattern (§6.2). An
    instrument you never saw cannot be chosen, so the box is printed rather than remembered."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    if not getattr(args, "text", None):
        print("ЯЩИК ПРИЁМОВ ДУМАНИЯ — бери под задачу, не один любимый на всё\n")
        for fam, items in THINK_TOOLS:
            print(f"  {fam:<13} {wrap(items, indent='                ')}")
        print("\nзапись   el think tools \"<какой взял и что он дал>\"")
        print("         пиши, что КАЖДЫЙ дал — приём, не сдвинувший структуру, идёт в мусор")
        return 0
    path = os.path.join(root, task, "thinking", "tools.md")
    body = open(path, encoding="utf-8").read() if os.path.exists(path) else \
        "# Приёмы думания — что брал и что дал каждый\n"
    body += f"\n- {args.text.strip()}\n"
    write(path, body)
    journal(root, task, "tool", args.text.strip()[:120])
    touch(root, task)
    print("записано  thinking/tools.md")
    return 0


def cmd_think_skip(args):
    """Mark a thinking step as deliberately not needed — with the reason, in its own file.

    Proportionality is real: a one-line change does not need a system map. But a SILENT skip
    is indistinguishable from forgetting, so the step still leaves a trace saying why it was
    not taken."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    key = (args.step or "").strip().lower()
    if key not in THINK_FILES:
        print(f"--step: одно из {', '.join(THINK_FILES)}", file=sys.stderr)
        return 1
    if key in ("decision", "forks"):
        print(f"шаг «{key}» пропустить нельзя: без развилок и выбора думание не состоялось.",
              file=sys.stderr)
        return 1
    if not args.why:
        print("скажи, ПОЧЕМУ шаг не нужен на этой задаче.", file=sys.stderr)
        return 1
    title = next(t for k, _r, t, *_x in THINK_STEPS if k == key)
    # A skip must never destroy work. Caught by doing exactly that: a demo `skip` wiped a step
    # that already held two pages of real thinking, and nothing warned.
    path = os.path.join(root, task, THINK_FILES[key])
    if os.path.exists(path) and "НЕ ПОНАДОБИЛОСЬ" not in open(path, encoding="utf-8").read():
        print(f"шаг «{title}» уже написан — пропуск затёр бы его.", file=sys.stderr)
        print(f"  если он правда лишний, удали файл руками: {THINK_FILES[key]}", file=sys.stderr)
        return 1
    write(path,
          f"# {title}\n\n**НЕ ПОНАДОБИЛОСЬ.** {args.why.strip()}\n\n"
          "_Пропуск сознательный и записан. Молчаливый пропуск неотличим от забытого._\n")
    journal(root, task, "skip", f"{key}: {args.why.strip()[:100]}")
    touch(root, task)
    print(f"пропущено «{title}» — причина записана")
    return 0
