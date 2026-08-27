"""Phase 2 — THINK, as behaviour: the ladder's recording commands and readers.

Since 2026-08-27 думание writes RECORDS into records.jsonl like context does: a rung is a
type of record, the forks and the risks are flows, a tool is a FIELD on the record it
produced (`--tool`), and the engineering promises go to checks.jsonl. The STEPS — what
each beat is and who it comes from — live in protocol.THINK_STEPS.

The bars of this phase are the measurements of thinking: the forks decided N/N · the
cells «paths × promises» scored · the categories of the box touched. None of it is
stored — all of it is folded out of the records.
"""
import os, sys
from .protocol import (THINK_CATS, THINK_CATS_MIN, THINK_FLOWS, THINK_MIN, THINK_STEPS, THINK_TOOLBOX,
                       THINK_TOOLS, THINK_RUNG_TOOLS, required_in)
from . import autonomy, store
from .context import _open, _amend_fields, live, records, last_seq, word_over, promises_at_root
from .state import journal, task_meta, task_mode, touch
from .term import wrap


# ── reading ─────────────────────────────────────────────────────────────────────────────

def forks_read(tdir):
    """The NEEDED DECISIONS with their standing (owner, 2026-08-27: «need decisions» on the
    page, the result is the «decision») — folded out of `fork` records and the `decision`
    events over them. A record that a later one `replaces` (rewritten in his language) is
    folded away, not lost."""
    out, by = [], {}
    recs = list(live(tdir, rtype="fork"))
    replaced = {x for r in recs for x in (r.get("replaces") or [])}
    for r in recs:
        if r["id"] in replaced:
            continue
        f = {"id": r["id"], "q": r.get("q", ""), "who": r.get("who", "owner"),
             "options": [], "details": [], "decision": None, "decide": r.get("decide", ""),
             "preview": r.get("preview", ""), "recommendation": r.get("recommend", ""),
             "why_yours": r.get("why_yours", ""), "fixed": "", "fidelity": "", "words": "",
             "opts": r.get("options") or [], "phase": r.get("phase", "think"), "seq": r.get("seq", 0)}
        for o in f["opts"]:
            f["options"].append(o.get("name", "") + (f" · +{o['plus']}" if o.get("plus") else "")
                                + (f" · −{o['minus']}" if o.get("minus") else ""))
            f["details"].append({"model": o.get("model", ""), "falsifier": o.get("falsifier", "")})
        out.append(f); by[f["id"]] = f
    for r in live(tdir, rtype="decision"):
        f = by.get(r.get("of"))
        if not f:
            continue
        f["decision"] = r.get("choice") or "—"
        f["words"] = r.get("words", ""); f["fixed"] = r.get("fixed", ""); f["fidelity"] = r.get("fidelity", "")
        f["decided_by"] = r.get("by", "owner"); f["assumed"] = r.get("assumed", "")
    return out


def paths_read(tdir):
    return live(tdir, step="options", rtype="path")


def cells(tdir):
    """(scored, total) — the cells of «paths × promises»: the measurement of думание."""
    paths = paths_read(tdir)
    proms = promises_at_root(tdir)
    total = len(paths) * len(proms)
    scored = sum(1 for p in paths for q in proms if (p.get("scores") or {}).get(q["id"]))
    return scored, total


def _cats_of(tool):
    """The categories a named tool falls into — matched by name inside the box's line."""
    t = tool.strip().lower()
    out = []
    for cat, line in THINK_TOOLS:
        if any(tok.strip().lower() and tok.strip().lower() in t or t in tok.strip().lower()
               for tok in line.split("·")):
            out.append(cat)
    return out


def tools_taken(tdir):
    """{category: [{id, step, tool}]} — every record born on думание that named a tool, by
    the category it fell into. The page opens a category on click and shows exactly this
    (owner, 2026-08-27: «нажать на каждый — что за tools внутри — а там ничего нету»)."""
    out = {}
    for r in live(tdir):
        t = (r.get("tool") or "").strip()
        if not t or r.get("phase") != "think":
            continue
        for cat in _cats_of(t):
            out.setdefault(cat, []).append({"id": r.get("id", ""), "step": r.get("step", ""), "tool": t})
    return out


def tool_cats(tdir):
    """Which categories of the box were TOUCHED — read from the `tool` field of the records
    born on думание."""
    used = set(tools_taken(tdir))
    return [c for c in THINK_CATS if c in used]


def step_done(tdir, key, mode=None):
    mode = mode or task_mode(tdir)
    if live(tdir, step=key, rtype="skip"):
        return True
    if key == "forks":
        fs = forks_read(tdir)
        return bool(fs) and all(f["decision"] for f in fs)
    if key == "promises":
        return any(p.get("born") == "think" for p in promises_at_root(tdir))
    if key == "approval":
        w, stale = word_over(tdir, "design")
        return bool(w) and not stale
    return bool(live(tdir, step=key))


def think_step(tdir, mode=None):
    """The first think beat that is not DONE; a beat not required under the MODE is skipped
    while empty."""
    mode = mode or task_mode(tdir)
    for key, rel, title, src, do, cmd in THINK_STEPS:
        done = step_done(tdir, key, mode)
        if not required_in(THINK_MIN.get(key, "soft"), mode) and not done:
            continue
        if not done:
            return key, rel, title, src, do, cmd
    return None


# ── writing ─────────────────────────────────────────────────────────────────────────────

def _put(root, task, args, rec, what, event=None, text=None):
    extra = _amend_fields(root, task, args, what) if False else {}
    # Past думание a write is an amendment — the same rule as context, keyed on «thinking/».
    from .amend import is_amendment
    if is_amendment(root, task, "thinking/"):
        why = (getattr(args, "why", None) or "").strip()
        if not why:
            print(f"после выхода из думания {what} правится ПОПРАВКОЙ: --why и --ref <основание>", file=sys.stderr)
            return None
        extra = {"amends": True, "why": why, "refs": list(getattr(args, "ref", None) or []),
                 "phase_amend": task_meta(root, task).get("phase", "think")}
    tool = (getattr(args, "tool", None) or "").strip()
    if tool:
        rec["tool"] = tool
    frm = (getattr(args, "from_", None) or "").strip()
    if frm:
        rec["from"] = frm
    rec = dict(rec, **extra)
    out = store.append(root, task, "records", rec)
    journal(root, task, event or rec.get("type", "think"), (text or "")[:120],
            {"id": out["id"], "step": rec.get("step"), **({"amend": True} if extra else {})})
    if extra:
        print(f"поправка  {out['id']} · {what} — его слово над решением устарело: el accept \"<его слова>\"")
    return out


def _rows(tdir, key):
    return live(tdir, step=key)


def cmd_forks(args):
    root, task, tdir = _open(args)
    if not root:
        return 1
    fs = forks_read(tdir)
    if not fs:
        print("решений от него пока не нужно.")
        print('hint     el think need "<вопрос его словами>" --option "<имя · плюс · минус>" --option … '
              '--recommend "<какой и почему>" --why-yours "<что знаешь только ты>"')
        return 0
    nd = sum(1 for f in fs if f["decision"])
    print(f"НУЖНЫ РЕШЕНИЯ  принято {nd} из {len(fs)}")
    for f in fs:
        mark = "✓" if f["decision"] else "▶"
        print(f"  {mark} {f['id']:<4} [{f['who']}] {f['q']}")
        for i, o in enumerate(f["opts"]):
            # one option — three lines: the name, «за», «против» (owner, 2026-08-27: «в одну
            # строку читается непонятно»)
            print(f"        {i + 1}. {o.get('name', '')}")
            if o.get("plus"):
                print(f"           за:      {wrap(o['plus'], indent='                    ')}")
            if o.get("minus"):
                print(f"           против:  {wrap(o['minus'], indent='                    ')}")
        if f["recommendation"]:
            print(f"        рекомендация: {f['recommendation']}")
        if f["why_yours"]:
            print(f"        почему твоё: {f['why_yours']}")
        if f["decision"]:
            print(f"        решено: {f['decision']}" + (f" — «{f['words']}»" if f.get("words") else "")
                  + (" · В ЕГО МЕСТО" if f.get("assumed") else ""))
    return 0


NEED_CMD = ('el think need "<вопрос его словами>" --option "<имя · плюс · минус>" … '
            '--recommend "<какой и почему>" --why-yours "<что знаешь только ты>"')


def cmd_fork(args):
    """Open a NEEDED DECISION (`el think need`; `fork` stays as the old spelling) — a question
    whose answer changes the road. Written in HIS language (owner, 2026-08-27: «записывать
    по-человечески, адаптированно к человеку»): the question and the options say what changes
    for him, not which command or phase — «с чего начинать, когда ты возвращаешься», not
    «фаза plan после reopen». Offering a choice obliges the
    agent to say why it could not choose itself (--why-yours) and to recommend."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    q = (getattr(args, "text", None) or getattr(args, "id", None) or "").strip()
    if getattr(args, "text", None) is None and getattr(args, "id", None):
        # `el think fork "<question>"` — the first positional IS the question
        q = args.id.strip()
    if not q:
        return cmd_forks(args)
    opts = []
    for o in (args.option or []):
        bits = [b.strip() for b in o.split("·")]
        opts.append({"name": bits[0], "plus": bits[1] if len(bits) > 1 else "", "minus": bits[2] if len(bits) > 2 else ""})
    if len(opts) < 2:
        print("нужное решение — это два и больше вариантов: --option \"<имя · плюс · минус>\" на каждый", file=sys.stderr)
        print("языком владельца: что меняется для него, без имён команд, фаз и файлов", file=sys.stderr)
        return 1
    rec = {"step": "forks", "type": "fork", "by": "agent", "q": q, "who": (args.who or "owner"),
           "options": opts, "status": "open"}
    for k in ("recommend", "why_yours", "decide", "preview"):
        v = (getattr(args, k, None) or "").strip()
        if v:
            rec[k] = v
    if rec["who"] == "owner" and not rec.get("why_yours"):
        print("предложил выбор — скажи, почему не выбрал сам: --why-yours \"<что живёт только у него>\"", file=sys.stderr)
        return 1
    reps = [x.strip() for x in (getattr(args, "replaces", None) or "").split(",") if x.strip()]
    if reps:
        rec["replaces"] = reps
    out = _put(root, task, args, rec, "нужные решения", "fork", q)
    if not out:
        return 1
    print(f"recorded  {out['id']} · нужно решение · {len(opts)} варианта · решает {rec['who']}"
          + (f" · вместо {', '.join(reps)}" if reps else ""))
    print(f"next      предъяви ему: варианты с плюсом и минусом, рекомендацию · el think decide {out['id']} \"<вариант>\" --words \"<его слова>\"")
    return 0


def cmd_decide(args):
    root, task, tdir = _open(args)
    if not root:
        return 1
    fid = (args.id or "").strip()
    fs = {f["id"]: f for f in forks_read(tdir)}
    if fid not in fs:
        print(f"нет такого решения: {fid or '?'} — список: el think", file=sys.stderr)
        return 1
    if getattr(args, "undo", None):
        dec = [r for r in live(tdir, rtype="decision") if r.get("of") == fid]
        if not dec:
            print("решения нет — нечего снимать", file=sys.stderr)
            return 1
        am = store.append(root, task, "records", {"step": "forks", "type": "amend", "retracts": dec[-1]["id"],
                                                  "why": args.undo, "by": "owner"})
        journal(root, task, "amend", f"decision {fid} снято: {args.undo}", {"id": am["id"]})
        print(f"снято     решение по {fid} — {am['id']}")
        return 0
    choice = (args.choice or "").strip()
    if not choice:
        print("что выбрано? el think decide <id> \"<вариант>\" --words \"<его слова>\"", file=sys.stderr)
        return 1
    assumed = (getattr(args, "assumed", None) or "").strip()
    words = (getattr(args, "words", None) or "").strip()
    if not words and not assumed:
        print("его слова дословно: --words \"…\" — или в его место под грантом: --assumed \"<почему>\"", file=sys.stderr)
        return 1
    if assumed and not autonomy.guard(root, task, "решение в его место"):
        return 1
    rec = {"step": "forks", "type": "decision", "of": fid, "choice": choice,
           "by": "agent" if assumed else "owner", "words": words}
    for k in ("why", "fixed", "fidelity"):
        v = (getattr(args, k, None) or "").strip()
        if v:
            rec[k] = v
    if assumed:
        rec["assumed"] = assumed
    out = store.append(root, task, "records", rec)
    journal(root, task, "decided", f"{fid}: {choice}", {"id": out["id"], "words": words, **({"assumed": assumed} if assumed else {})})
    if assumed:
        journal(root, task, "assume", f"{fid} → {choice}", {"phase": "think", "for": f"fork:{fid}", "why": assumed})
    touch(root, task)
    left = [f for f in forks_read(tdir) if not f["decision"]]
    print(f"решено    {fid} → {choice}" + (" · В ЕГО МЕСТО, под грантом" if assumed else ""))
    print(f"решений   ждёт {len(left)}" + (": " + ", ".join(f["id"] for f in left) if left else " — все приняты"))
    return 0


def _show(tdir, key, fmt):
    rows = _rows(tdir, key)
    for r in rows:
        print(f"  {r['id']:<5} {fmt(r)}" + (f"  [{r['tool']}]" if r.get("tool") else ""))
    return rows


def cmd_think_step(args):
    """One record on a rung of думание. The rung is `args.step_key`; bare it prints what
    the rung holds. `--tool` names the instrument the record came from."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    key = args.step_key
    text = (getattr(args, "text", None) or "").strip()
    title = dict((k, t) for k, _r, t, *_x in THINK_STEPS)[key]
    if not text:
        fmt = {
            "mirror": lambda r: f"{r['who']} — {r.get('does', '')}" + (f" · заденет: {r['affected']}" if r.get("affected") else ""),
            "form": lambda r: r["text"],
            "core": lambda r: f"[{r.get('rank', '')}] {r['text']}",
            "reversibility": lambda r: f"{r['text']} · защита: {r.get('guard', '—')}",
            "options": lambda r: f"{r['name']} — {r.get('text', '')} · оценки: " + (", ".join(f"{k}={v}" for k, v in (r.get("scores") or {}).items()) or "—"),
            "stress": lambda r: f"{r.get('path', '?')} × {r.get('promise', '?')}: {r['text']} → {'устояло' if r.get('held') else 'НЕ устояло'}",
            "crystal": lambda r: r["text"] + (f" · тропа {r['path']}" if r.get("path") else ""),
            "route": lambda r: r["text"] + (f" · после {', '.join(r['after'])}" if r.get("after") else ""),
        }.get(key, lambda r: r.get("text", ""))
        rows = _show(tdir, key, fmt)
        if key == "options":
            sc, tot = cells(tdir)
            print(f"  клетки пути × обещания: {sc}/{tot}")
        if not rows:
            cmd = dict((k, c) for k, _r, _t, _s, _d, c in THINK_STEPS)[key]
            print(f"пусто — {title}\n  {cmd}", file=sys.stderr)
            print(f"  приёмы: {THINK_RUNG_TOOLS.get(key, '—')}", file=sys.stderr)
            return 1
        return 0
    rec = {"step": key, "by": "agent"}
    if key == "mirror":
        rec.update(type="person", who=text, does=(args.does or "").strip(), affected=(args.affected or "").strip(), by="both")
    elif key == "form":
        rec.update(type="form", text=text, by="both")
    elif key == "core":
        rank = (args.rank or "").strip().lower()
        if rank not in ("core", "later", "never"):
            print("--rank core|later|never", file=sys.stderr); return 1
        rec.update(type="core", text=text, rank=rank)
    elif key == "promises":
        how = (args.how or "").strip()
        prec = {"kind": "criterion", "born": "think", "at": store.ROOT, "text": text, "how": how, "by": "both"}
        if (args.breaks_if or "").strip():
            prec["breaks_if"] = args.breaks_if.strip()
        if (getattr(args, "tool", None) or "").strip():
            prec["tool"] = args.tool.strip()
        out, reason = store.promise(root, task, prec)
        if reason:
            print(f"обещание не записано: {reason}", file=sys.stderr); return 1
        journal(root, task, "promise", text[:120], {"id": out["id"], "kind": "criterion", "at": store.ROOT, "born": "think"})
        print(f"recorded  {out['id']} · инженерное обещание · на корне · not_validated · чем проверим: {how[:60]}")
        return 0
    elif key == "reversibility":
        rec.update(type="irreversible", text=text, guard=(args.guard or "").strip(), by="both")
    elif key == "options":
        scores = {}
        for sc in (args.score or []):
            k, _, v = sc.partition("=")
            if k.strip() and v.strip():
                scores[k.strip()] = v.strip()
        rec.update(type="path", name=text, text=(getattr(args, "body", None) or "").strip(), scores=scores,
                   pros=(args.pros or "").strip(), cons=(args.cons or "").strip())
        if (args.parent or "").strip():
            rec["parent"] = args.parent.strip()
    elif key == "stress":
        held = (args.held or "").strip().lower()
        if held not in ("yes", "no", "да", "нет"):
            print("--held yes|no — устояло или нет", file=sys.stderr); return 1
        rec.update(type="attack", text=text, path=(args.path or "").strip(), promise=(args.promise or "").strip(),
                   held=held in ("yes", "да"), why=(args.why_held or "").strip())
    elif key == "crystal":
        rec.update(type="crystal", text=text, by="both")
        if (args.path or "").strip():
            rec["path"] = args.path.strip()
        if (getattr(args, "decided", None) or "").strip():
            rec["decided"] = [x.strip() for x in args.decided.split(",") if x.strip()]
    elif key == "route":
        rec.update(type="stage_seed", text=text, by="both", n=len(_rows(tdir, "route")) + 1)
        if (getattr(args, "after", None) or "").strip():
            rec["after"] = [x.strip() for x in args.after.split(",") if x.strip()]
    else:
        rec.update(type=key, text=text)
    out = _put(root, task, args, rec, title, key, text)
    if not out:
        return 1
    line = f"recorded  {out['id']} · {key}"
    if key == "options":
        sc, tot = cells(tdir)
        line += f" · клетки пути × обещания {sc}/{tot}"
    print(line)
    if key == "stress" and not rec["held"]:
        print("не устояло — путь правится или отсекается; запиши, что с ним: el think crystal / el think option")
    return 0


def cmd_think_tools(args):
    """The open box, printed by category — and which categories this task has TOUCHED,
    counted from the `tool` field of its records. With text: a tool note (what was taken
    and what it gave) — a record on the rung `tools` that counts for coverage too."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    text = (getattr(args, "text", None) or "").strip()
    if text and text.lower() in THINK_TOOLBOX:
        # ONE CATEGORY, tool by tool — the catalogue the page opens on a click (owner,
        # 2026-08-27: «что за tools внутри, как работает, когда применять, какой outcome»)
        cat = text.lower()
        box = THINK_TOOLBOX[cat]
        taken = tools_taken(tdir).get(cat, [])
        print(f"{cat.upper()} — {box['for']} · приёмов {len(box['tools'])}\n")
        for t in box["tools"]:
            print(f"  {t['name']}")
            print(f"           {wrap(t['what'], indent='           ')}")
            if t.get("about"):
                print(f"           {wrap(t['about'], indent='           ')}")
            for lab, key in (("когда", "when"), ("как", "how"), ("даёт", "gives")):
                print(f"    {lab:<6} {wrap(t[key], indent='           ')}")
            print()
        if taken:
            print("взято в этой задаче: " + " · ".join(f"{x['id']} {x['tool']} ({x['step']})" for x in taken))
        else:
            print("в этой задаче ещё не брали")
        print('запись   любая команда думания принимает --tool "<приём>"')
        return 0
    if text:
        rec = {"step": "tools", "type": "toolnote", "text": text, "by": "agent"}
        tool = (getattr(args, "tool", None) or "").strip() or text.split("—")[0].split(":")[0].strip()
        rec["tool"] = tool
        out = _put(root, task, args, rec, "приёмы", "tools", text)
        if not out:
            return 1
        print(f"recorded  {out['id']} · приём «{tool}»")
        return 0
    mode = task_mode(tdir)
    used = set(tool_cats(tdir))
    need = THINK_CATS_MIN.get(mode, [])
    print("ЯЩИК ПРИЁМОВ ДУМАНИЯ — бери под ступень, не один любимый на всё\n")
    for cat, line in THINK_TOOLS:
        mark = "✓" if cat in used else ("▶" if cat in need else "·")
        print(f"  {mark} {cat:<13} {wrap(line, indent='                  ')}")
    print(f"\nкатегорий взято {len(used)}/{len(THINK_CATS)} · режим {mode} просит: {', '.join(need) or '—'}")
    print("на ступенях:")
    for k, t in THINK_RUNG_TOOLS.items():
        print(f"  {k:<14} {t}")
    print('\nвнутри   el think tools <категория> — приёмы категории: что это · когда · как · что даёт')
    print('запись   любая команда думания принимает --tool "<приём>" · заметка о приёме: el think tools "<что взял — что дал>"')
    return 0


def cmd_think_skip(args):
    """Skip a rung on purpose — a record with the reason; the gate counts it as done."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    key = (args.step or "").strip()
    keys = [k for k, *_x in THINK_STEPS]
    if key not in keys or key in ("forks", "approval"):
        print(f"ступень одна из: {', '.join(k for k in keys if k not in ('forks', 'approval'))}", file=sys.stderr)
        return 1
    why = (args.why or "").strip()
    if not why:
        print('пропуск — с причиной: el think skip <ступень> --why "<почему не нужна здесь>"', file=sys.stderr)
        return 1
    out = store.append(root, task, "records", {"step": key, "type": "skip", "why": why, "by": "agent"})
    journal(root, task, "skip", f"{key}: {why}", {"id": out["id"]})
    print(f"пропущено {key} — {why}")
    return 0
