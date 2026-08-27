"""Phase 1 — CONTEXT, as behaviour: the ladder's recording commands and readers.

Since 2026-08-26 the phase writes RECORDS, not prose: every beat appends a line to
context.jsonl (research to research.jsonl; the checkable parts of the ideal — promises —
to checks.jsonl), and every reader here folds those lines back into a picture. The STEPS
themselves — what each beat is and who it comes from — are declared in
protocol.CONTEXT_STEPS; this module only reads and writes their records through store.py.

Nothing is edited in place. A line that stopped being true is retracted by an `amend`
record that names it and says why; the boundary's «зачёркнуто, не стёрто» costs no parser
any more. Past context the same commands are AMENDMENTS (--why required) — and the owner's
word carries the seq it was said over, so «картина правилась после его слова» is a number
comparison, not a guess.
"""
import os, sys
from .protocol import (AREA_KEYS, CONTEXT_FLOWS, CONTEXT_MIN, CONTEXT_STEPS, QA_AREAS,
                       SCOPE_DIMS, SCOPE_KEYS, required_in)
from . import autonomy, store
from .state import (pick_task, journal, now_iso, require_root, task_meta, task_mode, touch)
from .term import wrap
from .amend import is_amendment


# ── reading the stream back ─────────────────────────────────────────────────────────────

def _rt(tdir):
    """(root, task) out of a task folder — the readers are called with the folder, the store
    speaks in root and task; this is the one seam."""
    tdir = os.path.abspath(tdir.rstrip("/"))
    return os.path.dirname(tdir), os.path.basename(tdir)


def records(tdir, stream="records"):
    return store.read(*_rt(tdir), stream)


def live(tdir, step=None, rtype=None, stream="records"):
    return store.live(records(tdir, stream), step=step, rtype=rtype)


def amendments(tdir):
    """The п-notes: every amend record, numbered in the order written."""
    out = []
    for r in records(tdir):
        if r.get("type") == "amend":
            out.append({"n": len(out) + 1, "id": r["id"], "ts": r.get("ts", "")[:16].replace("T", " "),
                        "phase": r.get("phase", "context"), "why": r.get("why", ""),
                        "refs": " · ".join(r.get("refs") or []) or "—",
                        "retracts": r.get("retracts")})
    return out


def scope_read(tdir):
    """{dim: {"in": [...], "out": [...], "blur": [...], "struck": [...]}} — the boundary as it
    stands, plus what was struck by an amendment (kept: history, not truth)."""
    out = {k: {"in": [], "out": [], "blur": [], "struck": []} for k in SCOPE_KEYS}
    recs = records(tdir)
    gone = store.retracted(recs)
    mark = {a["retracts"]: f"[п{a['n']}]" for a in amendments(tdir) if a.get("retracts")}
    for r in recs:
        if r.get("type") != "dim" or r.get("dim") not in out:
            continue
        side = r.get("side", "blur")
        if r["id"] in gone:
            sign = {"in": "+", "out": "-", "blur": "?"}.get(side, "?")
            out[r["dim"]]["struck"].append(f"~~{sign} {r.get('text', '')}~~ {mark.get(r['id'], '')}".strip())
        elif side in ("in", "out", "blur"):
            out[r["dim"]][side].append(r.get("text", ""))
    return out


def scope_notes(tdir):
    """The amendments that touched the boundary — what the page lists under it."""
    dims = {r["id"] for r in records(tdir) if r.get("type") == "dim"}
    return [a for a in amendments(tdir) if a.get("retracts") in dims or a.get("step") == "scope"]


def scope_done(tdir):
    """A dimension counts as answered when something is IN or something is explicitly OUT.
    A lone "still blurred" is an honest note, not an answer — it leaves the boundary open."""
    st = scope_read(tdir)
    return [k for k in SCOPE_KEYS if st[k]["in"] or st[k]["out"]]


def area_coverage(tdir):
    """Which areas are covered — by a pair he answered OR a finding the agent fetched. Six
    of the keys are literally the 5W+H, so an answered dimension covers its area too."""
    hit = {a: 0 for a in AREA_KEYS}
    for r in live(tdir, rtype="qa"):
        if r.get("area") in hit:
            hit[r["area"]] += 1
    for r in live(tdir, step="research"):
        if r.get("area") in hit:
            hit[r["area"]] += 1
    for dim in scope_done(tdir):
        if dim in hit and not hit[dim]:
            hit[dim] += 1
    return hit


def questions_stat(tdir):
    """(asked, answered) — a pair is written only after the answer, so the two are equal;
    None when nothing was asked yet."""
    n = len(live(tdir, rtype="qa"))
    return (n, n) if n else None


def qa_read(tdir):
    """The Q/A rounds for the human page — the owner wants to SEE them (2026-08-21)."""
    rounds = {}
    for r in live(tdir, rtype="qa"):
        rnd = rounds.setdefault(r.get("round", 1), {"round": r.get("round", 1),
                                                    "ts": r.get("ts", "")[:16], "pairs": []})
        pair = {"id": r["id"], "area": r.get("area", ""), "q": r.get("q", ""), "a": r.get("a", ""),
                "ts": r.get("ts", "")[:16]}
        if r.get("options"):
            pair["options"] = r["options"]
        if r.get("assumed"):
            pair["assumed"] = r["assumed"]
        rnd["pairs"].append(pair)
    return [rounds[k] for k in sorted(rounds)]


def research_files(tdir):
    """The research grouped by SOURCE — what the folder view used to list, from one stream."""
    by = {}
    for r in live(tdir, step="research"):
        src = r.get("source", "?")
        d = by.setdefault(src, {"name": src, "rel": "records.jsonl#research", "findings": 0,
                                "lines": [], "chars": 0})
        d["findings"] += 1
        d["lines"].append(r.get("finding", ""))
        d["chars"] += len(r.get("finding", ""))
    return [by[k] for k in sorted(by)]


def research_topics(tdir):
    """The research as TOPICS (owner, 2026-08-27: «research — это выжимка: тема, краткое summary
    ясным языком, ссылка на файл, где всё собрано»). Returns (topics, loose): the topic records
    in order, and the old per-finding records no topic has folded in yet — shown apart, never
    lost."""
    recs = live(tdir, step="research")
    topics = [r for r in recs if r.get("type") == "research"]
    folded = set()
    for t in topics:
        folded.update(t.get("folds") or [])
    loose = [r for r in recs if r.get("type") != "research" and r["id"] not in folded]
    return topics, loose


RESEARCH_CMD = 'el research "<тема>" --summary "<выжимка ясным языком>" --file research/<имя>.md [--area <область>] [--folds f1,f2]'


def research_lines(tdir):
    topics, loose = research_topics(tdir)
    if not topics and not loose:
        return [f"  — ещё ничего: {RESEARCH_CMD}"]
    out = []
    for t in topics:
        out.append(f"  {t['id']:<4} {t.get('topic', '')}" + (f"  [{t['area']}]" if t.get("area") else ""))
        out.append(f"       {wrap(t.get('summary', ''), indent='       ')}")
        out.append(f"       файл: {t.get('file', '')}")
    if loose:
        out.append(f"  находки без темы ({len(loose)}) — сверни в тему: --folds " + ",".join(r["id"] for r in loose[:6]))
        for r in loose[:3]:
            out.append(f"      {r['id']:<4} [{r.get('source', '')}] {r.get('finding', '')[:100]}")
        if len(loose) > 3:
            out.append(f"      … и ещё {len(loose) - 3}: el ctx --section research")
    out.append(f"  добавить: {RESEARCH_CMD}")
    return out


def promises_at_root(tdir, kind=None):
    root, task = _rt(tdir)
    return [p for p in store.promises(root, task, kind=kind) if p.get("at", store.ROOT) == store.ROOT]


def last_seq(tdir):
    return store.next_seq(records(tdir)) - 1


def word_over(tdir, scope="context"):
    """His latest word over `scope`, and whether the picture moved after it."""
    words = [r for r in live(tdir, rtype="word") if r.get("scope") == scope]
    if not words:
        return None, False
    w = words[-1]
    # Stale when anything but another word landed AFTER it — the word's own seq is the
    # line; what it was said over is what stood before that line.
    # Only records born on the SAME phase count: думание writing after his word over the
    # context does not re-open the context (caught on the page, 2026-08-27).
    # …and only STRUCTURE counts: a node's status moving (started · waiting · done) is the
    # work happening under the map, not the map changing (caught on the probe, 2026-08-27).
    def _structural(r):
        if r.get("type") == "word":
            return False
        if r.get("type") == "set":
            f = r.get("field", "")
            return f.startswith("fields.") or f in ("name", "level", "parent", "deps", "unfold")
        return True
    stale = any(r.get("seq", 0) > w.get("seq", 0) and _structural(r)
                and r.get("phase", "context") == w.get("phase", "context")
                for r in live(tdir))
    return w, stale


def step_done(tdir, key, mode=None):
    """Has the beat left its trace? Most beats: at least one live record. The exceptions
    are the ones whose trace is a SHAPE, not a line: scope — all six dimensions; ideal — the
    paragraph AND at least one promise (strict: one of each kind); approval — a word that
    is still fresh."""
    mode = mode or task_mode(tdir)
    if key == "research":
        return bool(live(tdir, step="research"))
    if key == "scope":
        return len(scope_done(tdir)) == len(SCOPE_KEYS)
    if key == "ideal":
        have = bool(live(tdir, rtype="ifr")) and bool(promises_at_root(tdir, "checklist"))
        if mode == "strict":
            have = have and bool(promises_at_root(tdir, "metric")) and bool(promises_at_root(tdir, "success"))
        return have
    if key == "approval":
        w, stale = word_over(tdir, "context")
        return bool(w) and not stale
    if key == "conditions":
        return bool(live(tdir, step="conditions"))
    return bool(live(tdir, step=key))


def context_step(tdir, mode=None):
    """The first beat that is not DONE — the whole state machine, derived from the stream.
    A beat not required under the task's MODE is skipped while empty; written, it counts."""
    mode = mode or task_mode(tdir)
    for key, rel, title, src, do, cmd in CONTEXT_STEPS:
        done = step_done(tdir, key, mode)
        if not required_in(CONTEXT_MIN.get(key, "soft"), mode) and not done:
            continue
        if not done:
            return key, rel, title, src, do, cmd
    return None


# ── writing: one door, and the amendment rule at it ─────────────────────────────────────

def _open(args):
    root = require_root()
    if not root:
        return None, None, None
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return None, None, None
    return root, task, os.path.join(root, task)


def _amend_fields(root, task, args, what):
    """Past context a write is an AMENDMENT: it must say why and on what grounds. Returns
    the extra fields to stamp on the record, or None (refused, reason printed)."""
    if not is_amendment(root, task, "context/"):
        return {}
    why = (getattr(args, "why", None) or "").strip()
    if not why:
        print(f"после выхода из контекста {what} правится ПОПРАВКОЙ: скажи --why и дай "
              "--ref <основание> (развилка · research · evidence · его слова)", file=sys.stderr)
        return None
    phase = task_meta(root, task).get("phase", "context")
    return {"amends": True, "why": why, "refs": list(getattr(args, "ref", None) or []),
            "phase": phase}


FLOW_STEPS = {"questions", "research", "unknown", "definitions", "risks"}


# ── retracting: the one door for a correction that REPLACES instead of adding ──────────
#
# Feedback 2026-08-27 (Copilot, MLE): `el context now … --why` past the phase stamped
# `amends` on the NEW record — and the old one stayed live and showed beside it; the
# store's law («a picture that changed is a NEW record plus an `amend` that says which id
# it retracts») had a door only in scope --drop, plan rm and think decide --undo. Now every
# writing command of context and думание takes --retracts <id>, and `el context retract` /
# `el think retract` strike a record with nothing in its place. Nothing is deleted: the
# struck record stays on disk, out of live().

def _split_ids(raw):
    """--retracts n1 --retracts n2 · --retracts n1,n2 — one list, order kept."""
    out = []
    for chunk in (raw or []):
        for x in str(chunk).split(","):
            x = x.strip()
            if x and x not in out:
                out.append(x)
    return out


def resolve_retracts(tdir, ids):
    """The records the ids point at — each must be LIVE (on disk and not struck yet) and a
    record of the picture: a word, a verdict, a decision or an amendment has its own door.
    Returns (records, error)."""
    alive = {r.get("id"): r for r in live(tdir) if r.get("id")}
    recs, bad = [], []
    for i in ids:
        r = alive.get(i)
        if not r or r.get("type") in ("word", "amend", "verdict", "decision"):
            bad.append(i)
        else:
            recs.append(r)
    if bad:
        return None, (f"нет живой записи {', '.join(bad)} — снимается запись картины по её id "
                      "(el context --full · el think покажут id); снятую второй раз — нельзя, "
                      "решение — el think decide --undo")
    return recs, None


def retract(root, task, tdir, args, recs, replaced_by=None):
    """Strike records OUT OF THE PICTURE: one `amend` record per id — which id no longer
    holds, why, on what grounds, and (when a write carried --retracts) which record stands
    in its place. Journaled as `amend`, so the page's «Поправки» list and the sync question
    («его слово над картиной устарело») see it like any other amendment."""
    why = (getattr(args, "why", None) or "").strip()
    if not why and replaced_by:
        why = f"заменено записью {replaced_by}"
    if not why:
        print("снятие без причины не пишется: --why \"<почему запись больше не верна>\" "
              "[--ref <основание>]", file=sys.stderr)
        return None
    refs = list(getattr(args, "ref", None) or [])
    phase = task_meta(root, task).get("phase", "context")
    out = []
    for r in recs:
        am = {"step": r.get("step"), "type": "amend", "by": "agent", "retracts": r["id"],
              "why": why, "refs": refs, "phase": phase}
        if replaced_by:
            am["replaced_by"] = replaced_by
        a = store.append(root, task, "records", am)
        n_am = len(amendments(tdir))
        gist = (r.get("text") or r.get("q") or r.get("term") or r.get("finding") or "").strip()[:60]
        journal(root, task, "amend",
                f"{r.get('step')} п{n_am}: снята {r['id']}" + (f" → {replaced_by}" if replaced_by else "")
                + (f": «{gist}»" if gist else ""),
                {"id": a["id"], "part": r.get("step"), "n": n_am, "why": why, "refs": refs,
                 "phase": phase, "retracts": r["id"],
                 **({"replaced_by": replaced_by} if replaced_by else {})})
        print(f"снято     {r['id']} · {r.get('step')}" + (f" · «{gist}»" if gist else "")
              + f" — поправка {a['id']}" + (f" · вместо неё {replaced_by}" if replaced_by else ""))
        out.append(a)
    return out


def cmd_retract(args):
    """el context retract <id> [<id>…] --why "<…>" [--ref …] — strike a record out of the
    picture with nothing in its place. To REPLACE in one go, any writing command takes
    --retracts <id>: el context now "<новое>" --kind flow --retracts n1 [--why …]."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    ids = _split_ids(list(getattr(args, "ids", None) or []))
    if not ids:
        print('el context retract <id> [<id>…] --why "<почему>" [--ref <основание>]\n'
              '  заменить одной командой: el context now "<новое>" --kind flow --retracts n1 · '
              'думание: el think form "<новое>" --retracts fm1', file=sys.stderr)
        return 1
    recs, err = resolve_retracts(tdir, ids)
    if err:
        print(err, file=sys.stderr)
        return 1
    return 0 if retract(root, task, tdir, args, recs) else 1


def _put(root, task, args, rec, what, event=None, text=None):
    """Append one context record with the amendment stamp when due; journal it; say so.
    A FLOW record (a question, a finding, a risk…) is never an amendment — flows run through
    every phase by design (2026-08-27). --retracts <id>: the old record is struck by an
    amend record right after the new one lands — a replacement, not a neighbour."""
    extra = {} if rec.get("step") in FLOW_STEPS else _amend_fields(root, task, args, what)
    if extra is None:
        return None
    tdir = os.path.join(root, task)
    old, err = resolve_retracts(tdir, _split_ids(getattr(args, "retracts", None)))
    if err:
        print(err, file=sys.stderr)
        return None
    rec = dict(rec, **extra)
    out = store.append(root, task, "context", rec)
    journal(root, task, event or rec.get("type", "context"), (text or "")[:120],
            {"id": out["id"], "step": rec.get("step"), **({"amend": True} if extra else {})})
    if old:
        retract(root, task, tdir, args, old, replaced_by=out["id"])
    if extra:
        print(f"поправка  {out['id']} · {what} · {extra['phase']} · его слово над картиной "
              "устарело — предъяви и запиши ответ: el accept \"<его слова>\"")
    return out


def _fresh_word_hint(tdir):
    w, stale = word_over(tdir, "context")
    if w and stale:
        print("слово     картина изменилась после его «да» — на выходе из фазы понадобится "
              "свежее: el accept \"<его слова>\"")


# ── the flows ───────────────────────────────────────────────────────────────────────────

def cmd_qa(args):
    """Record a question AND its answer — together, never separately (owner, 2026-08-18):
    the next block of questions is derived from the previous answers, so a pre-filled
    questionnaire cannot exist."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    if getattr(args, "list", False):
        rounds = qa_read(tdir)
        if not rounds:
            print("no questions recorded yet.")
            print('hint     ask the owner, hear the answer, then: el context qa "<q>" "<a>"')
            return 0
        for rnd in rounds:
            print(f"## round {rnd['round']} — {rnd['ts']}")
            for p in rnd["pairs"]:
                print(f"  {p['id']:<4} [{p['area']}] {p['q']}")
                print(f"       → {p['a']}")
                if p.get("assumed"):
                    print(f"       (предположено агентом в его место: {p['assumed']})")
        return 0
    if not args.question or not (args.answer or "").strip():
        print("both a question and an answer are required — a question without one is not "
              "context yet. ask the owner FIRST, hear the answer, then record the pair.",
              file=sys.stderr)
        print('hint     el context qa "<question>" "<answer>" --area <область>', file=sys.stderr)
        return 1
    area = (getattr(args, "area", None) or "").strip().lower()
    if area not in AREA_KEYS:
        print(f"--area is required, one of: {', '.join(AREA_KEYS)}", file=sys.stderr)
        for k, d, src in QA_AREAS:
            print(f"  {k:<8} {src:<6} {d}", file=sys.stderr)
        return 1
    have = live(tdir, rtype="qa")
    cur = max([r.get("round", 1) for r in have] or [0])
    rnd = args.round or (cur + 1 if (args.new_round or not cur) else cur)
    assumed = (getattr(args, "assumed", None) or "").strip()
    if assumed and not autonomy.guard(root, task, "ответ в его место"):
        return 1
    rec = {"step": "questions", "type": "qa", "by": "agent" if assumed else "owner",
           "round": rnd, "area": area, "q": args.question.strip(), "a": args.answer.strip()}
    opts = (getattr(args, "options", None) or "").strip()
    if opts:
        rec["options"] = [o.strip() for o in opts.split("·") if o.strip()]
    if assumed:
        rec["assumed"] = assumed
    out = _put(root, task, args, rec, "вопросы", "qa", args.question)
    if not out:
        return 1
    if assumed:
        journal(root, task, "assume", f"{args.question.strip()} → {args.answer.strip()}",
                {"phase": "context", "for": f"qa:{area}", "why": assumed})
    cov = area_coverage(tdir)
    blank = [a for a in AREA_KEYS if not cov[a]]
    print(f"recorded  {out['id']} · round {rnd} · {len(have) + 1} pair(s) · area {area}"
          + (" · РЕШЕНИЕ АГЕНТА в его место — он прочтёт, вернувшись (el review)" if assumed else ""))
    if blank:
        src = dict((k, v) for k, _d, v in QA_AREAS)
        owner_side = [a for a in blank if src[a] == "owner"]
        print(f"blank     {', '.join(blank)}")
        if owner_side:
            print(f"ask him   {', '.join(owner_side)} — эти живут только у него в голове")
        rest = [a for a in blank if a not in owner_side]
        if rest:
            print(f"возьми сам  {', '.join(rest)} — добывается прибором, спрашивать = красть его время")
    else:
        print("blank     — все области покрыты")
    _fresh_word_hint(tdir)
    print("next      el context areas — карта покрытия · el next — шаг лестницы")
    return 0


def cmd_ctx_add(args):
    """RESEARCH — a topic: what was investigated · the digest in plain words · the file that
    holds the material (owner, 2026-08-27). The file is the research; the record is its
    address. The old per-finding form (`el research <источник> "<находка>" --ref`) still
    writes a finding, listed apart as «без темы» until a topic folds it in with --folds."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    summary = (getattr(args, "summary", None) or "").strip()
    if not args.source and not args.finding and not summary:
        print(f"ИССЛЕДОВАНИЯ  {task} · records.jsonl#research · файлы: {os.path.join(tdir, 'research')}")
        for l in research_lines(tdir):
            print(l)
        return 0
    area = (getattr(args, "area", None) or "").strip().lower()
    if area and area not in AREA_KEYS:
        print(f"unknown --area '{area}'. one of: {', '.join(AREA_KEYS)}", file=sys.stderr)
        return 1
    if summary or getattr(args, "file", None):
        topic = (args.source or "").strip()
        fpath = (getattr(args, "file", None) or "").strip()
        if not topic or not summary or not fpath:
            print("тема · --summary · --file — все три: тема одной строкой, выжимка ясным языком, "
                  "файл с материалом (короткий — тоже файл).", file=sys.stderr)
            print(f"hint     {RESEARCH_CMD}", file=sys.stderr)
            return 1
        full = fpath if os.path.isabs(fpath) else os.path.join(tdir, fpath)
        if not os.path.exists(full):
            print(f"нет файла {fpath} — положи материал в research/ этой задачи и укажи путь к нему",
                  file=sys.stderr)
            return 1
        rec = {"step": "research", "type": "research", "by": "agent", "topic": topic,
               "summary": summary, "file": fpath, "refs": list(args.ref or [])}
        folds = [x.strip() for x in (getattr(args, "folds", None) or "").split(",") if x.strip()]
        if folds:
            rec["folds"] = folds
        if area:
            rec["area"] = area
        out = store.append(root, task, "records", rec)
        journal(root, task, "source", f"{topic}: {summary[:70]}",
                {"id": out["id"], "file": fpath, "area": area or None, "folds": folds or None})
        print(f"recorded  {out['id']} · research · «{topic}» · {fpath}"
              + (f" · свёрнуто: {', '.join(folds)}" if folds else ""))
        print("next      el research — темы · el context — the big picture")
        return 0
    if not args.source or not args.finding:
        print("тема и выжимка нужны обе.", file=sys.stderr)
        print(f"hint     {RESEARCH_CMD}", file=sys.stderr)
        return 1
    rec = {"step": "research", "type": "finding", "by": "agent", "source": args.source.strip(),
           "finding": args.finding.strip(), "refs": list(args.ref or [])}
    if area:
        rec["area"] = area
    out = store.append(root, task, "records", rec)
    journal(root, task, "source", f"{args.source.strip()}: {args.finding.strip()[:70]}",
            {"id": out["id"], "refs": args.ref or [], "area": area or None})
    print(f"recorded  {out['id']} · research · {args.source.strip()}"
          + ("" if args.ref else " · без якоря — где это перепроверить? --ref <путь:строка>"))
    print("next      el context — the big picture · el next — what still blocks the gate")
    return 0


def cmd_unknown(args):
    """Condition 2 of the gate: «what do I NOT know that I should know?» — written, not
    thought, and written WHEN it surfaced."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    if not getattr(args, "text", None):
        rows = live(tdir, step="unknown")
        if not rows:
            print('el context unknown "<чего не знаю, что должен бы знать>" [--how "<как закрываем>"]',
                  file=sys.stderr)
            return 1
        for r in rows:
            print(f"  {r['id']:<4} {r['text']}" + (f" · как: {r['how']}" if r.get("how") else "")
                  + (" · ДЕРЖИТ ГЕЙТ" if r.get("blocking") else ""))
        return 0
    rec = {"step": "unknown", "type": "unknown", "by": "agent", "text": args.text.strip()}
    how = (getattr(args, "how", None) or getattr(args, "risk", None) or "").strip()
    if how:
        rec["how"] = how
    if getattr(args, "blocking", False):
        rec["blocking"] = True
    out = _put(root, task, args, rec, "неизвестное", "unknown", args.text)
    if not out:
        return 1
    print(f"recorded  {out['id']} · unknown" + (" · держит гейт" if rec.get("blocking") else ""))
    return 0


def cmd_define(args):
    """A term heard in his speech, with what it means IN THIS project — the moment it
    sounded. His image is kept beside the plain phrase (heard_from), never instead of it."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    if not args.term:
        rows = live(tdir, step="definitions")
        for r in rows:
            print(f"  {r['id']:<4} {r['term']} — {r['means']}"
                  + (f" (его слова: «{r['heard_from']}»)" if r.get("heard_from") else ""))
        if not rows:
            print('el context define "<термин>" "<что значит здесь>" [--heard "<его слова>"]',
                  file=sys.stderr)
            return 1
        return 0
    if not args.means:
        print("a term AND what it means here — both.", file=sys.stderr)
        return 1
    rec = {"step": "definitions", "type": "definition", "by": "both", "term": args.term.strip(),
           "means": args.means.strip()}
    heard = (getattr(args, "heard", None) or "").strip()
    if heard:
        rec["heard_from"] = heard
    out = _put(root, task, args, rec, "определения", "definition", args.term)
    if not out:
        return 1
    print(f"recorded  {out['id']} · {args.term.strip()}")
    return 0


# ── the rungs ───────────────────────────────────────────────────────────────────────────

def cmd_now(args):
    """How it happens TODAY — the baseline (owner, 2026-08-26: «как это сейчас всё
    происходит, или что у нас есть, в каком оно состоянии»). Three layers, each a kind."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    kinds = ("flow", "state", "number")
    if not args.text:
        rows = live(tdir, step="now")
        for r in rows:
            print(f"  {r['id']:<4} {r.get('kind', ''):<7} {r['text']}"
                  + (f" · {r['ref']}" if r.get("ref") else ""))
        if not rows:
            print('el context now "<как сейчас>" --kind flow|state|number [--ref <якорь>]\n'
                  "  flow — что человек делает руками сегодня, шаг за шагом · state — что уже "
                  "построено и в каком виде · number — сколько сейчас (шагов, минут, ошибок)",
                  file=sys.stderr)
            return 1
        return 0
    kind = (getattr(args, "kind", None) or "").strip().lower()
    if kind not in kinds:
        print(f"--kind — one of: {', '.join(kinds)}", file=sys.stderr)
        return 1
    rec = {"step": "now", "type": "now", "by": "both", "kind": kind, "text": args.text.strip()}
    if getattr(args, "ref", None):
        rec["ref"] = " · ".join(args.ref)
    out = _put(root, task, args, rec, "точка отсчёта", "now", args.text)
    if not out:
        return 1
    print(f"recorded  {out['id']} · now · {kind}")
    return 0


def cmd_context_scope(args):
    """The boundary, dimension by dimension. Bare it PRINTS THE QUESTIONS — that is the
    point: the step used to name a file with no command behind it, and the six dimensions
    were never actually asked about. One line — one record; --drop retracts one."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    state = scope_read(tdir)
    dim = (getattr(args, "dim", None) or "").strip().lower()
    if not dim:
        print("ГРАНИЦЫ — шесть измерений, каждое отвечается вопросом\n")
        for k, q in SCOPE_DIMS:
            d = state[k]
            mark = "✓" if (d["in"] or d["out"]) else "✗"
            print(f"{mark} {k:<6} {wrap(q, indent='         ')}")
            for x in d["in"]:
                print(f"    входит     {wrap(x, indent='               ')}")
            for x in d["out"]:
                print(f"    НЕ входит  {wrap(x, indent='               ')}")
            for x in d["blur"]:
                print(f"    размыто    {wrap(x, indent='               ')}")
            for x in d["struck"]:
                print(f"    снято      {wrap(x, indent='               ')}")
        done = scope_done(tdir)
        left = [k for k in SCOPE_KEYS if k not in done]
        print(f"\nзакрыто  {len(done)}/6" + (f" · пусто: {', '.join(left)}" if left else ""))
        print('запись   el context scope <измерение> --in "<что входит>" '
              '--out "<что НЕ входит>" --blur "<где линия размыта>" · --drop "<строка>" снимает')
        return 0
    if dim not in state:
        print(f"измерение одно из: {', '.join(SCOPE_KEYS)}", file=sys.stderr)
        return 1
    drop = (getattr(args, "drop", None) or "").strip()
    if not (args.inside or args.out or args.blur or drop):
        print("нечего записывать: дай --in, --out, --blur или --drop", file=sys.stderr)
        return 1
    if getattr(args, "replace", False):
        print("--replace нет: картина не перетирается — сними строку --drop и допиши новую",
              file=sys.stderr)
        return 1
    if drop:
        hit = [r for r in live(tdir, rtype="dim") if r.get("dim") == dim and r.get("text") == drop]
        if not hit:
            print(f"нет такой строки в {dim}: «{drop}» — el context scope покажет, что есть",
                  file=sys.stderr)
            return 1
        why = (getattr(args, "why", None) or "").strip() or "снято на сборе контекста"
        am = {"step": "scope", "type": "amend", "by": "both", "retracts": hit[-1]["id"], "why": why,
              "refs": list(getattr(args, "ref", None) or []),
              "phase": task_meta(root, task).get("phase", "context")}
        if is_amendment(root, task, "context/") and not (getattr(args, "why", None) or "").strip():
            print("после выхода из контекста строка снимается ПОПРАВКОЙ: --why и --ref", file=sys.stderr)
            return 1
        out = store.append(root, task, "context", am)
        n_am = len(amendments(tdir))
        journal(root, task, "amend", f"scope п{n_am} {dim}: снято «{drop}»",
                {"id": out["id"], "part": "scope", "n": n_am, "dim": dim, "why": why,
                 "refs": am["refs"], "phase": am["phase"]})
        print(f"снято     {hit[-1]['id']} · {dim} · «{drop}» — поправка {out['id']}")
    ids = []
    for flag, side in (("inside", "in"), ("out", "out"), ("blur", "blur")):
        val = getattr(args, flag, None)
        if val:
            rec = {"step": "scope", "type": "dim", "by": "both", "dim": dim, "side": side,
                   "text": val.strip()}
            out = _put(root, task, args, rec, "граница", "scope", f"{dim} {side}: {val}")
            if not out:
                return 1
            ids.append(out["id"])
    done = scope_done(tdir)
    left = [k for k in SCOPE_KEYS if k not in done]
    if ids:
        print(f"recorded  {', '.join(ids)} · {dim} · закрыто {len(done)}/6")
    if left:
        print(f"пусто     {', '.join(left)} — покажи вопросы: el context scope")
    else:
        print("граница   все шесть измерений отвечены — дальше el next")
    _fresh_word_hint(tdir)
    return 0


def cmd_condition(args):
    """Under what conditions we work — one rung, five kinds. «Условий нет» is recorded."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    kinds = ("forbidden", "limit", "resource", "money", "tool")
    none = getattr(args, "none", None)
    if not args.kind and not none:
        rows = live(tdir, step="conditions")
        for r in rows:
            print(f"  {r['id']:<4} {r.get('kind', 'none'):<9} {r.get('text', '')}"
                  + (f" · {r['ref']}" if r.get("ref") else ""))
        if not rows:
            print('el context condition <forbidden|limit|resource|money|tool> "<что>" [--ref] · '
                  '--none "<почему условий нет>"', file=sys.stderr)
            return 1
        return 0
    if none:
        rec = {"step": "conditions", "type": "condition", "by": "owner", "none": True,
               "text": none.strip()}
    else:
        kind = args.kind.strip().lower()
        if kind not in kinds or not args.text:
            print(f"kind — one of {', '.join(kinds)}, and the text.", file=sys.stderr)
            return 1
        rec = {"step": "conditions", "type": "condition", "by": "both", "kind": kind,
               "text": args.text.strip()}
        if getattr(args, "ref", None):
            rec["ref"] = " · ".join(args.ref)
    out = _put(root, task, args, rec, "условия", "condition", rec["text"])
    if not out:
        return 1
    print(f"recorded  {out['id']} · condition · {rec.get('kind', 'none')}")
    return 0


def cmd_requirement(args):
    root, task, tdir = _open(args)
    if not root:
        return 1
    states = ("have", "missing", "unknown")
    if not args.text:
        rows = live(tdir, step="requirements")
        for r in rows:
            print(f"  {r['id']:<4} {r.get('state', ''):<8} {r['text']}"
                  + (f" · {r['ref']}" if r.get("ref") else ""))
        if not rows:
            print('el context requirement "<что>" --state have|missing|unknown [--ref <якорь>]',
                  file=sys.stderr)
            return 1
        return 0
    st = (getattr(args, "state", None) or "").strip().lower()
    if st not in states:
        print(f"--state — one of: {', '.join(states)} (уже есть · нет · неизвестно)", file=sys.stderr)
        return 1
    rec = {"step": "requirements", "type": "req", "by": "both", "state": st, "text": args.text.strip()}
    if getattr(args, "ref", None):
        rec["ref"] = " · ".join(args.ref)
    out = _put(root, task, args, rec, "требования", "requirement", args.text)
    if not out:
        return 1
    print(f"recorded  {out['id']} · requirement · {st}")
    return 0


def cmd_beyond(args):
    """What sits RIGHT NEXT to the boundary and is deliberately NOT done — and the honest
    counterpart: a candidate worth pulling in, his call BEFORE the work."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    if not args.text:
        rows = live(tdir, step="beyond")
        for r in rows:
            print(f"  {r['id']:<4} {'КАНДИДАТ' if r.get('verdict') == 'candidate' else 'не делаем':<9} {r['text']}"
                  + (f" · {r['why']}" if r.get("why") else ""))
        if not rows:
            print('el context beyond "<рядом лежит X — не делаем>" [--candidate --why "<стоит втянуть?>"]',
                  file=sys.stderr)
            return 1
        return 0
    rec = {"step": "beyond", "type": "beyond", "by": "both", "text": args.text.strip(),
           "verdict": "candidate" if getattr(args, "candidate", False) else "out"}
    # --why here is the candidate's argument; past context it doubles as the amendment's why
    why = (getattr(args, "why", None) or "").strip()
    if why and rec["verdict"] == "candidate":
        rec["why"] = why
    out = _put(root, task, args, rec, "за рамкой", "beyond-scope", args.text)
    if not out:
        return 1
    print(f"recorded  {out['id']} · beyond · {rec['verdict']}")
    if rec["verdict"] == "candidate":
        print("next      кандидата на втягивание в рамку — предъяви владельцу ДО начала работ")
    return 0


def cmd_risk(args):
    root, task, tdir = _open(args)
    if not root:
        return 1
    chances = ("low", "mid", "high")
    if not args.text:
        rows = live(tdir, step="risks")
        for r in rows:
            print(f"  {r['id']:<4} {r.get('chance', ''):<5} {r['text']} · цена: {r.get('cost', '—')}"
                  + (f" · если случилось: {r['then']}" if r.get("then") else ""))
        if not rows:
            print('el context risk "<что может случиться>" --chance low|mid|high --cost "<чем '
                  'обойдётся>" --then "<что делаем>"', file=sys.stderr)
            return 1
        return 0
    ch = (getattr(args, "chance", None) or "").strip().lower()
    cost = (getattr(args, "cost", None) or "").strip()
    if ch not in chances or not cost:
        print(f"--chance one of {', '.join(chances)} and --cost «чем обойдётся» — a risk without a "
              "price is a worry", file=sys.stderr)
        return 1
    rec = {"step": "risks", "type": "risk", "by": "both", "text": args.text.strip(), "chance": ch,
           "cost": cost}
    then = (getattr(args, "then", None) or "").strip()
    if then:
        rec["then"] = then
    out = _put(root, task, args, rec, "риски", "risk", args.text)
    if not out:
        return 1
    print(f"recorded  {out['id']} · risk · {ch}")
    return 0


def _promise(args, kind, rec, what):
    """A promise born in context hangs on the root. Refused without `how`."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    extra = _amend_fields(root, task, args, what)
    if extra is None:
        return 1
    rec = dict(rec, kind=kind, born="context", by=rec.get("by", "owner"), **extra)
    out, reason = store.promise(root, task, rec)
    if reason:
        print(f"обещание не записано: {reason}", file=sys.stderr)
        return 1
    journal(root, task, "promise", (rec.get("text") or rec.get("name") or "")[:120],
            {"id": out["id"], "kind": kind, "at": store.ROOT})
    print(f"recorded  {out['id']} · {kind} · на корне · not_validated · чем проверим: {rec['how'][:60]}")
    if extra:
        print("поправка  обещание добавлено после его слова — понадобится свежее: el accept")
    _fresh_word_hint(tdir)
    return 0


def cmd_success(args):
    if not args.text:
        return _show_promises(args, "success")
    return _promise(args, "success", {"text": args.text.strip(), "how": getattr(args, "how", None),
                                      "observable": (getattr(args, "observable", None) or "").strip()},
                    "критерии успеха")


def cmd_metric(args):
    if not args.text:
        return _show_promises(args, "metric")
    rec = {"name": args.text.strip(), "how": getattr(args, "how", None),
           "unit": (getattr(args, "unit", None) or "").strip(),
           "direction": (getattr(args, "direction", None) or "").strip().lower()}
    if rec["direction"] not in ("up", "down", "equal"):
        print("--direction up|down|equal — куда должно сдвинуться", file=sys.stderr)
        return 1
    if getattr(args, "threshold", None) is None:
        print("--threshold N — порог, названный ДО правки", file=sys.stderr)
        return 1
    _num = lambda v: int(v) if float(v).is_integer() else v
    rec["threshold"] = _num(args.threshold)
    if getattr(args, "baseline", None) is not None:
        rec["baseline"] = _num(args.baseline)
    return _promise(args, "metric", rec, "метрики")


def cmd_check(args):
    if not args.text:
        return _show_promises(args, "checklist")
    return _promise(args, "checklist", {"text": args.text.strip(), "how": getattr(args, "how", None)},
                    "чек-лист приёмки")


def _show_promises(args, kind):
    root, task, tdir = _open(args)
    if not root:
        return 1
    rows = promises_at_root(tdir, kind)
    for p in rows:
        head = p.get("text") or p.get("name")
        extra = ""
        if kind == "metric":
            extra = f" · порог {p.get('threshold')} {p.get('unit', '')} {p.get('direction', '')}" \
                    + (f" · baseline {p['baseline']}" if p.get("baseline") is not None else "")
        print(f"  {p['id']:<4} {p['status']:<14} {head}{extra} · чем: {p.get('how', '')}")
    if not rows:
        print(f"нет обещаний вида {kind}: el help context — команды ступени ideal", file=sys.stderr)
        return 1
    return 0


def cmd_ifr(args):
    root, task, tdir = _open(args)
    if not root:
        return 1
    if not args.text:
        rows = live(tdir, rtype="ifr")
        if not rows:
            print('el context ifr "<идеал одним абзацем, глазами пользователя>"', file=sys.stderr)
            return 1
        print(rows[-1]["text"])
        return 0
    rec = {"step": "ideal", "type": "ifr", "by": "owner", "text": args.text.strip()}
    out = _put(root, task, args, rec, "идеал", "ifr", args.text)
    if not out:
        return 1
    print(f"recorded  {out['id']} · ifr")
    return 0


def cmd_part(args):
    root, task, tdir = _open(args)
    if not root:
        return 1
    if not args.text:
        rows = live(tdir, step="parts")
        for i, r in enumerate(rows, 1):
            print(f"  {i}. {r['id']:<4} {r['text']}" + (f" · раскрывает {', '.join(r['covers'])}" if r.get("covers") else ""))
        if not rows:
            print('el context part "<крупный кусок>" [--covers k1,s2] · по одной, в порядке пути',
                  file=sys.stderr)
            return 1
        return 0
    rec = {"step": "parts", "type": "part", "by": "owner", "text": args.text.strip(),
           "n": len(live(tdir, step="parts")) + 1}
    covers = (getattr(args, "covers", None) or "").strip()
    if covers:
        rec["covers"] = [c.strip() for c in covers.split(",") if c.strip()]
    out = _put(root, task, args, rec, "крупные части", "parts", args.text)
    if not out:
        return 1
    print(f"recorded  {out['id']} · part {rec['n']}")
    return 0


def cmd_context_step(args):
    """The two fold-ups — clarified · summary. Each remembers the seq it was folded over."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    key = args.step_key
    if not args.text:
        rows = live(tdir, step=key)
        if not rows:
            print(f'нечего показывать — напиши: el context {key} "<текст>"', file=sys.stderr)
            return 1
        r = rows[-1]
        print(r["text"])
        if last_seq(tdir) > r.get("over_seq", 0):
            print(f"\n(собрано над картиной #{r.get('over_seq')}; с тех пор она изменилась)")
        return 0
    rec = {"step": key, "type": key, "by": "agent", "text": args.text.strip(), "over_seq": last_seq(tdir)}
    out = _put(root, task, args, rec, key, key, args.text)
    if not out:
        return 1
    print(f"записано  {out['id']} · {key} · над картиной #{rec['over_seq']}")
    print("next      el next — следующий шаг лестницы")
    return 0


def cmd_areas(args):
    """The coverage map: which areas have been touched, who each one comes from."""
    root, task, tdir = _open(args)
    if not root:
        return 1
    cov = area_coverage(tdir)
    print("покрытие сбора — область · откуда берётся · сколько записей")
    for key, desc, src in QA_AREAS:
        n = cov[key]
        mark = "✓" if n else "✗"
        who = {"owner": "СПРОСИТЬ у владельца", "agent": "добыть САМОМУ прибором",
               "both": "начать самому, спросить остаток"}[src]
        print(f"  {mark} {key:<8} {n:>2}  {who:<32} {desc}")
    blank = [a for a in AREA_KEYS if not cov[a]]
    if blank:
        print(f"\nпусто    {', '.join(blank)}")
        print('запись   el context qa "<вопрос>" "<ответ>" --area <область>')
    else:
        print("\nвсе области покрыты хотя бы одной записью")
    return 0


def record_word(root, task, words, scope, assumed=None):
    """His word over the picture, with the seq it was said over — called by `el accept` on
    context. Returns the record."""
    tdir = os.path.join(root, task)
    rec = {"step": "approval", "type": "word", "by": "agent" if assumed else "owner",
           "scope": scope, "words": words.strip(), "over_seq": last_seq(tdir)}
    if assumed:
        rec["assumed"] = assumed
    return store.append(root, task, "context", rec)


# ── the picture, printed — «предъяви содержимым, а не ссылками» ─────────────────────────

def section_lines(tdir, key):
    """One beat of the ladder as lines for the eye — what `el context` prints instead of
    a file. Empty list when the beat has left no trace. Records are folded into the shape
    each beat has: pairs by round, the boundary by dimension, promises with their status."""
    L = []
    if key == "questions":
        for rnd in qa_read(tdir):
            L.append(f"раунд {rnd['round']} · {rnd['ts']}")
            for p in rnd["pairs"]:
                L.append(f"  {p['id']:<4} [{p['area']}] {p['q']}")
                if p.get("options"):
                    L.append(f"       варианты: {' · '.join(p['options'])}")
                L.append(f"       → {p['a']}")
                if p.get("assumed"):
                    L.append(f"       (в его место, под грантом: {p['assumed']})")
        return L
    if key == "research":
        topics, loose = research_topics(tdir)
        for t in topics:
            L.append(f"  {t['id']:<4} {t.get('topic', '')}" + (f"  [{t['area']}]" if t.get("area") else ""))
            L.append(f"       {t.get('summary', '')}")
            L.append(f"       файл: {t.get('file', '')}" + (f" · свёрнуто: {', '.join(t['folds'])}" if t.get("folds") else ""))
        if loose:
            L.append(f"  находки без темы ({len(loose)}):")
            for r in loose:
                L.append(f"  {r['id']:<4} [{r.get('source', '')}] {r.get('finding', '')}")
                for ref in r.get("refs") or []:
                    L.append(f"       якорь: {ref}")
        return L
    if key == "scope":
        st = scope_read(tdir)
        if not any(st[k]["in"] or st[k]["out"] or st[k]["blur"] or st[k]["struck"] for k in st):
            return L
        for k, q in SCOPE_DIMS:
            d = st[k]
            L.append(f"  {k} — {q}")
            for x in d["in"]:
                L.append(f"    + {x}")
            for x in d["out"]:
                L.append(f"    - {x}")
            for x in d["blur"]:
                L.append(f"    ? {x}")
            for x in d["struck"]:
                L.append(f"    {x}")
            if not (d["in"] or d["out"] or d["blur"] or d["struck"]):
                L.append("    _пусто_")
        return L
    if key == "ideal":
        for kind, title in (("success", "критерии успеха"), ("metric", "метрики"), ("checklist", "чек-лист приёмки")):
            rows = promises_at_root(tdir, kind)
            if not rows:
                continue
            L.append(f"  {title}:")
            for p in rows:
                head = p.get("text") or p.get("name")
                tail = ""
                if kind == "metric":
                    tail = f" · порог {p.get('threshold')} {p.get('unit', '')} {p.get('direction', '')}" \
                           + (f" · сейчас {p['baseline']}" if p.get("baseline") is not None else "")
                if kind == "success" and p.get("observable"):
                    tail = f" · видно: {p['observable']}"
                L.append(f"    {p['id']:<4} [{p['status']}] {head}{tail}")
                L.append(f"         чем проверим: {p.get('how', '')}")
        ifr = live(tdir, rtype="ifr")
        if ifr:
            L.append("  идеал:")
            L += ["    " + x for x in ifr[-1]["text"].splitlines()]
        return L
    if key == "approval":
        for w in live(tdir, rtype="word"):
            tag = " · В ЕГО МЕСТО, под грантом" if w.get("assumed") else ""
            L.append(f"  {w['id']:<4} над {w.get('scope')} · картина #{w.get('over_seq')}{tag}")
            L.append(f"       «{w.get('words', '')}»")
        w, stale = word_over(tdir, "context")
        if w and stale:
            L.append("  ⚠ картина изменилась после этого слова — нужно свежее")
        return L
    rows = live(tdir, step=key)
    for r in rows:
        if key == "now":
            L.append(f"  {r['id']:<4} {r.get('kind', ''):<7} {r['text']}" + (f" · {r['ref']}" if r.get("ref") else ""))
        elif key == "conditions":
            L.append(f"  {r['id']:<4} {'нет условий' if r.get('none') else r.get('kind', ''):<11} {r.get('text', '')}"
                     + (f" · {r['ref']}" if r.get("ref") else ""))
        elif key == "requirements":
            L.append(f"  {r['id']:<4} {r.get('state', ''):<8} {r['text']}" + (f" · {r['ref']}" if r.get("ref") else ""))
        elif key == "beyond":
            L.append(f"  {r['id']:<4} {'КАНДИДАТ' if r.get('verdict') == 'candidate' else 'не делаем':<9} {r['text']}"
                     + (f" · {r['why']}" if r.get("why") else ""))
        elif key == "risks":
            L.append(f"  {r['id']:<4} {r.get('chance', ''):<5} {r['text']} · цена: {r.get('cost', '—')}"
                     + (f" · если случилось: {r['then']}" if r.get("then") else ""))
        elif key == "parts":
            L.append(f"  {r.get('n', '?')}. {r['text']}" + (f" · раскрывает {', '.join(r['covers'])}" if r.get("covers") else ""))
        elif key == "definitions":
            L.append(f"  {r['id']:<4} {r['term']} — {r['means']}" + (f" (его слова: «{r['heard_from']}»)" if r.get("heard_from") else ""))
        elif key == "unknown":
            L.append(f"  {r['id']:<4} {r['text']}" + (f" · как закрываем: {r['how']}" if r.get("how") else "")
                     + (" · ДЕРЖИТ ГЕЙТ" if r.get("blocking") else ""))
        elif key in ("clarified", "summary"):
            L += ["  " + x for x in r["text"].splitlines()]
            if last_seq(tdir) > r.get("over_seq", 0):
                L.append(f"  (над картиной #{r.get('over_seq')}; с тех пор она изменилась)")
        else:
            L.append(f"  {r.get('id', ''):<4} {r.get('text', '')}")
        if r.get("amends"):
            L.append(f"       поправка ({r.get('phase', '')}): {r.get('why', '')}"
                     + (f" · основание: {' · '.join(r['refs'])}" if r.get("refs") else ""))
    return L
