"""Phase 1 — CONTEXT, as behaviour: the ladder's recording commands and readers.

The boundary asked dimension by dimension (5W+1H), the Q/A pairs with their area tags,
the coverage map, the free-text steps of the frame (requirements … unknown), research
sources with anchors. The STEPS themselves — what each beat is and who it comes from —
are declared in protocol.CONTEXT_STEPS; this module only reads and writes their files.
"""
import os, re, sys
from .protocol import (AREA_KEYS, CONTEXT_FILES, CONTEXT_MIN, CONTEXT_STEPS, QA_AREAS,
                       SCOPE_DIMS, SCOPE_KEYS, required_in)
from . import autonomy
from .state import (pick_task, current_task, journal, norm_id, now_iso, require_root, resolve_task,
                    task_meta, task_mode, touch, write)
from .term import wrap
from .amend import MARK, amend_doc, is_amendment, parse_notes


def scope_read(tdir):
    """Parse context/5w-h.md back into {dim: {"in": [...], "out": [...], "blur": [...]}}.

    Reading back what we wrote — rather than keeping a second copy in some index — is the same
    rule the rest of the tool follows: the text file IS the state, and a parallel copy is the
    thing that silently drifts."""
    path = os.path.join(tdir, CONTEXT_FILES["scope"])
    out = {k: {"in": [], "out": [], "blur": [], "struck": []} for k in SCOPE_KEYS}
    if not os.path.exists(path):
        return out
    cur = None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("## "):
            head = line[3:].split("—")[0].strip()
            cur = head if head in out else None
        elif cur and line.startswith("~~"):
            # A retracted line — struck through by an amendment, never deleted (history).
            out[cur]["struck"].append(line)
        elif cur and line.startswith("+ "):
            out[cur]["in"].append(line[2:].strip())
        elif cur and line.startswith("- "):
            out[cur]["out"].append(line[2:].strip())
        elif cur and line.startswith("? "):
            out[cur]["blur"].append(line[2:].strip())
    return out


def scope_notes(tdir):
    """The п-notes of the boundary's amendments (the closing «## Поправки» section)."""
    path = os.path.join(tdir, CONTEXT_FILES["scope"])
    if not os.path.exists(path):
        return []
    tail = open(path, encoding="utf-8").read().split("\n## Поправки", 1)
    return parse_notes(tail[1].splitlines()) if len(tail) == 2 else []


def scope_write(tdir, state, notes=()):
    body = ["# Границы задачи — шесть измерений (5W+H)", "",
            "_Граница собирается ОТВЕТАМИ на вопросы, а не прозой агента._",
            "_`+` входит · `-` не входит · `?` линия ещё размыта · `[пN]` — поправка N, "
            "см. внизу; зачёркнутое — снято поправкой, не стёрто_", ""]
    for k, q in SCOPE_DIMS:
        body.append(f"## {k} — {q}")
        d = state[k]
        if not (d["in"] or d["out"] or d["blur"] or d.get("struck")):
            body.append("_пусто — вопрос ещё не задан_")
        for x in d["in"]:
            body.append(f"+ {x}")
        for x in d["out"]:
            body.append(f"- {x}")
        for x in d["blur"]:
            body.append(f"? {x}")
        for x in d.get("struck", []):
            body.append(x)
        body.append("")
    if notes:
        body.append("## Поправки")
        for n in notes:
            body.append(f"- п{n['n']} · {n['ts']} · {n['phase']} · почему: {n['why']} · "
                        f"основание: {n['refs']}")
        body.append("")
    write(os.path.join(tdir, CONTEXT_FILES["scope"]), "\n".join(body).rstrip() + "\n")


def scope_done(tdir):
    """A dimension counts as answered when something is IN or something is explicitly OUT.
    A lone "still blurred" is an honest note, not an answer — it leaves the boundary open."""
    st = scope_read(tdir)
    return [k for k in SCOPE_KEYS if st[k]["in"] or st[k]["out"]]


def area_coverage(tdir):
    """Which areas are covered — BY EITHER SOURCE, and that is the whole point.

    The first version counted only question-and-answer pairs, and an area marked `agent`
    could therefore never turn green: `how` and `where` are fetched with an instrument, never
    asked. The map then demanded the one thing the routing forbids — asking the owner about
    something measurable. Caught on the first live run (2026-08-19), fixed on the spot.

    Read from the files: `Q [area]:` in questions.md for what he answered, `[область: area]`
    in any source file for what the agent went and got."""
    # `el context add` writes its findings to research/<src>.md, not context/ — so the map
    # must read BOTH folders, or an agent-fetched `where`/`how` stays "blank" forever
    # (caught live 2026-08-22: three `--area where/how` findings recorded, map showed 0).
    hit = {a: 0 for a in AREA_KEYS}
    for sub in ("context", "research"):
        cdir = os.path.join(tdir, sub)
        if not os.path.isdir(cdir):
            continue
        for fn in os.listdir(cdir):
            if not fn.endswith(".md"):
                continue
            for line in open(os.path.join(cdir, fn), encoding="utf-8", errors="replace"):
                for m in re.finditer(r"(?:Q\s*\[([a-z]+)\]:|\[область:\s*([a-z]+)\])", line):
                    key = m.group(1) or m.group(2)
                    if key in hit:
                        hit[key] += 1
    # An answered scope dimension IS a covered area — six of the ten keys are literally the
    # 5W+H. Without this the two commands contradicted each other on the same folder: `el
    # context scope` said `when` was answered while `el context areas` called it blank, and
    # `saturate` refused on the strength of the second. Two answers to one question is the
    # defect class the mode calls "broken", not "inconvenient". (Caught live 2026-08-20.)
    for dim in scope_done(tdir):
        if dim in hit and not hit[dim]:
            hit[dim] += 1
    return hit


def context_step(tdir, mode=None):
    """The first step that is not DONE — the whole state machine, derived from disk.

    "Done" is normally "the file exists". Scope is the exception and has to be: its file is
    born with the first of six dimensions answered, so existence would move the pointer off a
    boundary that is still two sides open. A step not required under the task's MODE is
    skipped while its file is absent — written, it counts like any other."""
    mode = mode or task_mode(tdir)
    for key, rel, title, src, do, cmd in CONTEXT_STEPS:
        exists = os.path.exists(os.path.join(tdir, rel))
        if not required_in(CONTEXT_MIN.get(key, "soft"), mode) and not exists:
            continue    # not required in this mode: a task without it skips silently
        if key == "scope" and exists and len(scope_done(tdir)) < len(SCOPE_KEYS):
            return key, rel, title, src, do, cmd
        if not exists:
            return key, rel, title, src, do, cmd
    return None


def questions_stat(tdir):
    """Clarifying questions ARE the context work, and they only count when written down.
    Asked-and-not-recorded dies with the session, and the next run asks the same again
    (elephant-v1: ContextAnswers is a separate output of the phase)."""
    path = os.path.join(tdir, "context", "questions.md")
    if not os.path.exists(path):
        return None
    asked = answered = 0
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        low = s.lower()
        # `Q [area]:` — the area tag became mandatory and the old prefix list stopped matching,
        # so the gate reported "no questions in it" over a file holding eighteen pairs. Caught
        # by the gate refusing a move that should have passed (2026-08-19).
        if re.match(r"q\s*\[[a-z]+\]\s*:", low):
            asked += 1
            continue
        for mark in ("q:", "**q:", "- q:", "вопрос:"):
            if low.startswith(mark):
                asked += 1
                break
        else:
            for mark in ("a:", "**a:", "- a:", "ответ:"):
                if low.startswith(mark):
                    # An EMPTY answer line is not an answer. The whole point of the file is
                    # that what was asked and actually answered survives the session.
                    if s[len(mark):].strip(" *"):
                        answered += 1
                    break
    return asked, answered


def qa_read(tdir):
    """The Q/A rounds, parsed back for the human page: the owner wants to SEE the questions
    and answers on overview.html, not hunt them in a file (2026-08-21)."""
    rounds = []
    try:
        fh = open(os.path.join(tdir, "context", "questions.md"), encoding="utf-8")
    except OSError:
        return rounds
    cur = None
    for line in fh:
        s = line.strip()
        m = re.match(r"##\s*round\s*(\d+)\s*[—-]\s*(.*)$", s, re.I)
        if m:
            cur = {"round": int(m.group(1)), "ts": m.group(2).strip(), "pairs": []}
            rounds.append(cur)
            continue
        m = re.match(r"Q\s*(?:\[([a-z]+)\])?\s*:\s*(.+)$", s, re.I)
        if m:
            if cur is None:
                cur = {"round": len(rounds) + 1, "ts": "", "pairs": []}
                rounds.append(cur)
            cur["pairs"].append({"area": m.group(1) or "", "q": m.group(2).strip(), "a": ""})
            continue
        m = re.match(r"A\s*:\s*(.+)$", s, re.I)
        if m and cur and cur["pairs"]:
            cur["pairs"][-1]["a"] = m.group(1).strip()
            continue
        # A BORROWED answer (autonomy): the marker line under A: — the page shows it, because
        # these are the first thing the returning owner reviews.
        m = re.match(r"_предположено агентом[^—]*—\s*почему:\s*(.*?)_?$", s)
        if m and cur and cur["pairs"]:
            cur["pairs"][-1]["assumed"] = m.group(1).strip()
    return rounds


def _ctx_write(root, task, key, heading, text, extra_lines=()):
    """Write one step's trace. Shared by the small recording commands below."""
    rel = CONTEXT_FILES[key]
    path = os.path.join(root, task, rel)
    body = f"# {heading}\n\n{text.strip()}\n"
    for line in extra_lines:
        body += line + "\n"
    write(path, body)
    touch(root, task)
    return rel


# The playbooks/ folder and its readers (playbook, beats_of, beats_done) were removed
# 2026-08-21 (owner: "она не нужна, избыточна — всё внутри Elephant CLI"): the beats of
# every phase live in this file — CONTEXT_STEPS, THINK_STEPS, PHASE_MAP — and the yaml
# copy had quietly become dead code with no callers.
def cmd_qa(args):
    """Record a question AND its answer — together, never separately.

    The order is: ask the owner in the conversation → hear the answer → write the pair
    down. A file pre-filled with questions and empty answers is a questionnaire, not
    context gathering: the NEXT block of questions is derived from the PREVIOUS answers,
    so it cannot be generated in advance. (Owner, 2026-08-18.)"""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, args.task)
    if not task:
        return 1
    path0 = os.path.join(root, task, "context", "questions.md")
    if getattr(args, "list", False):
        if not os.path.exists(path0):
            print("no questions recorded yet.")
            print('hint     ask the owner, hear the answer, then: el context qa "<q>" "<a>"')
            return 0
        print(open(path0, encoding="utf-8").read().rstrip())
        return 0
    if not args.question or not args.answer:
        print("both a question and an answer are required.", file=sys.stderr)
        print('hint     el context qa "<question>" "<answer>"  ·  list them: el context qa --list',
              file=sys.stderr)
        return 1
    if not args.answer.strip():
        print("an answer is required — a question without one is not context yet.",
              file=sys.stderr)
        print("hint     ask the owner FIRST, hear the answer, then record the pair.",
              file=sys.stderr)
        print("         the next block of questions is derived from these answers,",
              file=sys.stderr)
        print("         so it cannot be written in advance. el help — the mechanics.",
              file=sys.stderr)
        return 1
    # An area tag is REQUIRED. Counting pairs measured nothing — ten questions about one
    # corner printed the same "10 asked / 10 answered" as ten that covered the task. The tag
    # turns the count into COVERAGE, and coverage is what shows the agent where it never went.
    area = (getattr(args, "area", None) or "").strip().lower()
    if area not in AREA_KEYS:
        print(f"--area is required, one of: {', '.join(AREA_KEYS)}", file=sys.stderr)
        for k, d, src in QA_AREAS:
            print(f"  {k:<8} {src:<6} {d}", file=sys.stderr)
        return 1
    path = os.path.join(root, task, "context", "questions.md")
    if not os.path.exists(path):
        write(path, "# Уточняющие вопросы и ответы\n\n"
                    "_Пара пишется ПОСЛЕ ответа. Следующий раунд строится из этих ответов._\n")
    rounds = sum(1 for l in open(path, encoding="utf-8") if l.startswith("## round "))
    rnd = args.round or (rounds if rounds and not args.new_round else rounds + 1)
    body = open(path, encoding="utf-8").read()
    if f"## round {rnd}" not in body:
        body += f"\n## round {rnd} — {now_iso()[:16]}\n"
    # A BORROWED ANSWER (autonomy, owner 2026-08-22): nobody to ask — the agent writes the
    # question it would have asked and the answer it assumes, marked; the pair counts for
    # coverage like any other, and the assumption is a debt his word over the picture pays.
    assumed = (getattr(args, "assumed", None) or "").strip()
    if assumed and not autonomy.guard(root, task, "ответ в его место"):
        return 1
    body += f"\nQ [{area}]: {args.question.strip()}\nA: {args.answer.strip()}\n"
    if assumed:
        body += f"  _предположено агентом в его место (под грантом) — почему: {assumed}_\n"
    write(path, body)
    journal(root, task, "qa", args.question.strip()[:80], {"round": rnd, "area": area,
                                                         **({"assumed": True} if assumed else {})})
    if assumed:
        journal(root, task, "assume", f"{args.question.strip()} → {args.answer.strip()}",
                {"phase": "context", "for": f"qa:{area}", "why": assumed})
    touch(root, task)
    tdir = os.path.join(root, task)
    qs = questions_stat(tdir)
    cov = area_coverage(tdir)
    blank = [a for a in AREA_KEYS if not cov[a]]
    print(f"recorded in round {rnd} · {qs[1]} pair(s) · area {area}"
          + (" · РЕШЕНИЕ АГЕНТА в его место — он прочтёт, вернувшись (el review)" if assumed else ""))
    if blank:
        owner_side = [a for a in blank
                      if dict((k, v) for k, _d, v in QA_AREAS)[a] == "owner"]
        print(f"blank     {', '.join(blank)}")
        if owner_side:
            print(f"ask him   {', '.join(owner_side)} — эти живут только у него в голове")
        rest = [a for a in blank if a not in owner_side]
        if rest:
            print(f"возьми сам  {', '.join(rest)} — добывается прибором, спрашивать = красть его время")
    else:
        print("blank     — все области покрыты")
    print("next      el context areas — карта покрытия · el next — шаг лестницы")
    return 0


def cmd_context_scope(args):
    """Ask the boundary dimension by dimension, and record what is in, out and still blurred.

    Called bare it PRINTS THE QUESTIONS — that is the whole point. The step used to name a
    required file with no command behind it, so the agent wrote a paragraph of its own prose
    and the six dimensions were never actually asked about."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
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
            for x in d.get("struck", []):
                print(f"    снято      {wrap(x, indent='               ')}")
        done = scope_done(tdir)
        left = [k for k in SCOPE_KEYS if k not in done]
        print(f"\nзакрыто  {len(done)}/6" + (f" · пусто: {', '.join(left)}" if left else ""))
        print('запись   el context scope <измерение> --in "<что входит>" '
              '--out "<что НЕ входит>" --blur "<где линия размыта>"')
        return 0

    if dim not in state:
        print(f"измерение одно из: {', '.join(SCOPE_KEYS)}", file=sys.stderr)
        return 1
    drop = (getattr(args, "drop", None) or "").strip()
    if not (args.inside or args.out or args.blur or drop):
        print("нечего записывать: дай --in, --out, --blur или --drop", file=sys.stderr)
        return 1
    # PAST CONTEXT the boundary is AMENDED, not redrawn: the line moves with a [пN] mark, a
    # retracted line is struck through, and the note says why and on what grounds. The
    # owner's word over the picture is re-opened (see amend.py).
    amend = is_amendment(root, task, CONTEXT_FILES["scope"])
    notes = scope_notes(tdir)
    mark = ""
    if amend:
        why = (getattr(args, "why", None) or "").strip()
        if getattr(args, "replace", False):
            print("поправка не перетирает: после выхода из контекста --replace запрещён — "
                  "вычеркни --drop и допиши --in/--out", file=sys.stderr)
            return 1
        if not why:
            print("после выхода из контекста граница правится ПОПРАВКОЙ: скажи --why и дай "
                  "--ref <основание> (развилка · research/… · evidence/… · его слова); "
                  '--drop "<строка>" вычёркивает старое', file=sys.stderr)
            return 1
        n = len(notes) + 1
        mark = f" [п{n}]"
    elif getattr(args, "replace", False):
        state[dim] = {"in": [], "out": [], "blur": [], "struck": []}
    if drop:
        hit = None
        for key, sign in (("in", "+"), ("out", "-"), ("blur", "?")):
            for x in state[dim][key]:
                if MARK.sub("", x).strip() == drop:
                    hit = (key, sign, x)
                    break
            if hit:
                break
        if not hit:
            print(f"нет такой строки в {dim}: «{drop}» — el context scope покажет, что есть",
                  file=sys.stderr)
            return 1
        key, sign, x = hit
        state[dim][key].remove(x)
        if amend:
            state[dim]["struck"].append(f"~~{sign} {x}~~{mark}")
    for flag, key in (("inside", "in"), ("out", "out"), ("blur", "blur")):
        val = getattr(args, flag, None)
        if val:
            state[dim][key].append(val.strip() + mark)
    phase = task_meta(root, task).get("phase", "context")
    if amend:
        refs = list(getattr(args, "ref", None) or [])
        notes = notes + [{"n": n, "ts": now_iso()[:16].replace("T", " "), "phase": phase,
                          "why": why, "refs": " · ".join(refs) or "—"}]
    scope_write(tdir, state, notes)
    touch(root, task)
    said = (args.inside or args.out or args.blur or f"вычеркнуто: {drop}")[:80]
    if amend:
        journal(root, task, "amend", f"scope п{n} {dim}: {said}",
                {"part": "scope", "n": n, "dim": dim, "why": why, "refs": refs, "phase": phase})
    else:
        journal(root, task, "scope", f"{dim}: {said}", {"dim": dim})
    done = scope_done(tdir)
    left = [k for k in SCOPE_KEYS if k not in done]
    if amend:
        print(f"поправка  п{n} · {CONTEXT_FILES['scope']} · {dim} · {phase}")
        print('слово     картина правилась после его слова — предъяви и запиши ответ: '
              'el accept "<его слова>"')
        return 0
    print(f"recorded  {CONTEXT_FILES['scope']} · {dim} · закрыто {len(done)}/6")
    if left:
        print(f"пусто     {', '.join(left)} — покажи вопросы: el context scope")
    else:
        print("граница   все шесть измерений отвечены — дальше el next")
    return 0


def cmd_context_step(args):
    """Write one free-text step of the ladder — requirements · ifr · clarified · summary.

    These four were required traces with no command behind them, so the only way to fill them
    was to write the file by hand — the very thing the tool exists to stop (§0.5: two paths for
    one operation). Named after the step itself, because the command a person can GUESS is the
    one they will use: standing on "требования и ресурсы" you type `el context requirements`.
    (Found the same way as the scope gap, on live work 2026-08-20.)"""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    key = args.step_key
    title = dict((k, t) for k, _r, t, *_x in CONTEXT_STEPS)[key]
    path = os.path.join(root, task, CONTEXT_FILES[key])
    if not args.text:
        if os.path.exists(path):
            print(open(path, encoding="utf-8").read().rstrip())
            return 0
        print(f'нечего показывать — напиши: el context {key} "<текст>"', file=sys.stderr)
        return 1
    if is_amendment(root, task, CONTEXT_FILES[key]):
        return 0 if amend_doc(root, task, CONTEXT_FILES[key], title, args) else 1
    if os.path.exists(path) and not getattr(args, "replace", False):
        body = open(path, encoding="utf-8").read().rstrip()
        body += "\n\n" + args.text.strip() + "\n"
        write(path, body)
        note = "дописано"
    else:
        _ctx_write(root, task, key, title, args.text)
        note = "записано"
    touch(root, task)
    journal(root, task, key, args.text.strip()[:80])
    print(f"{note}  {CONTEXT_FILES[key]}")
    print("next      el next — следующий шаг лестницы")
    return 0


# cmd_saturate is gone (owner, 2026-08-21): the end of questioning is the HUMAN's word,
# recorded as the last Q/A pair — a separate file about the agent's own feelings duplicated
# it and went stale the moment the human spoke again. Its one load-bearing check — an
# owner-only area never asked about — moved into the context exit gate in cmd_forward.


def cmd_unknown(args):
    """Condition 2 of the gate: "what do I NOT know that I should know?"

    The spec calls it the most frequently ignored condition (§4). It has to be written, not
    thought: a silent "we will figure it out as we go" is exactly what it forbids."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    rel = CONTEXT_FILES["unknown"]
    path = os.path.join(root, task, rel)
    if getattr(args, "text", None) is None:
        print('el context unknown "<чего не знаю, что должен бы знать>"', file=sys.stderr)
        return 1
    body = open(path, encoding="utf-8").read() if os.path.exists(path) else \
        "# Чего я не знаю, что должен бы знать\n\n_Явный вопрос перед спуском. " \
        "Молчаливое «разберёмся по ходу» не считается._\n"
    body += f"\n- {args.text.strip()}"
    if getattr(args, "risk", None):
        body += f"\n  - как закрываем: {args.risk.strip()}"
    body += "\n"
    write(path, body)
    journal(root, task, "unknown", args.text.strip()[:120])
    touch(root, task)
    print(f"recorded  {rel}")
    return 0


def cmd_beyond(args):
    """What sits RIGHT NEXT to the boundary and is deliberately NOT done — the frame's
    closing part (owner, 2026-08-21: "есть то, что внутри квадратика, и то, что снаружи —
    beyond описывает снаружи, и он входит в сам scope").

    The unstated "не делаем" surfaces mid-execution as "а я думал, это тоже входит".
    And the honest counterpart: something close by may be WORTH pulling inside — that is
    the human's call, made BEFORE the work: a lean-to is cheap while the house is being
    built and expensive once it stands."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    if not args.text:
        print("name what lies NEXT TO the boundary and is not done.", file=sys.stderr)
        print('hint     el context beyond "рядом лежит X и Y — сознательно НЕ делаем"',
              file=sys.stderr)
        print('         el context beyond "Z вплотную к границе — может, стоит втянуть: '
              'решает владелец"', file=sys.stderr)
        return 1
    if is_amendment(root, task, CONTEXT_FILES["beyond"]):
        return 0 if amend_doc(root, task, CONTEXT_FILES["beyond"],
                              "За рамкой — близко, но не делаем", args) else 1
    _ctx_write(root, task, "beyond", "За рамкой — близко, но не делаем", args.text)
    journal(root, task, "beyond-scope", args.text.strip()[:120])
    print(f"recorded  {CONTEXT_FILES['beyond']}")
    print("next      кандидата на втягивание в рамку — предъяви владельцу ДО начала работ")
    return 0


def cmd_areas(args):
    """The coverage map: which areas have been touched, who each one comes from, what is blank."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, getattr(args, "task", None))
    if not task:
        return 1
    tdir = os.path.join(root, task)
    cov = area_coverage(tdir)
    print("покрытие сбора — область · откуда берётся · сколько пар")
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
        print("\nвсе области покрыты хотя бы одной парой")
    return 0


def research_files(tdir):
    """Every source file in research/, with what a reader needs to choose: name · findings
    (bullet lines) · size. Any name is legal — sources are named by what was looked at
    (cluster, jira, dns …), not from a fixed list."""
    rdir = os.path.join(tdir, "research")
    out = []
    for f in sorted(os.listdir(rdir) if os.path.isdir(rdir) else []):
        if not f.endswith(".md") or f.startswith("."):
            continue
        p = os.path.join(rdir, f)
        try:
            text = open(p, encoding="utf-8").read()
        except OSError:
            continue
        # a finding written by `el research` is a dated «## » section whose first text line
        # is the finding itself (the anchor sits under it as «- якорь:»); a hand-written file
        # lists findings as top-level bullets — read whichever the file uses
        lines_ = text.splitlines()
        finds, cur = [], None
        if any(l.startswith("## ") for l in lines_):
            for l in lines_:
                if l.startswith("## "):
                    cur = "wait"
                elif cur == "wait" and l.strip() and not l.lstrip().startswith("- якорь"):
                    finds.append(l.strip().lstrip("- ").strip())
                    cur = None
        else:
            finds = [l[2:].strip() for l in lines_ if l.startswith("- ")]
        out.append({"name": f[:-3], "rel": f"research/{f}", "findings": len(finds),
                    "lines": finds, "chars": len(text)})
    return out


def research_lines(tdir):
    """The research folder as `el context` and bare `el research` show it — one line per
    source, and the command that opens it whole. Contents are NOT inlined here: nine sources
    can be 50K characters, past what one tool call carries (owner's question 2026-08-24:
    «не получится так, что файлы там есть, а он их прочитать не может?» — it could, until
    now: research/ was named, never readable through el)."""
    files = research_files(tdir)
    if not files:
        return ['  — ещё ничего: el research <источник> "<находка>" --ref <якорь>']
    # NAME · THE RESULTS, SHORT · THE PATH (owner, 2026-08-24: «название ресерча, результат
    # ресерча, и путь — чтобы агент мог ориентироваться, а прочитать — открыть файл»).
    out = [f"  папка: {os.path.join(tdir, 'research')}"]
    for r in files:
        out.append(f"  {r['name']} · {r['rel']} · находок {r['findings']}")
        for line in r["lines"][:3]:
            out.append(f"      · {line[:110]}")
        if r["findings"] > 3:
            out.append(f"      · … и ещё {r['findings'] - 3} — целиком: el ctx --section {r['name']}")
    out.append('  добавить: el research <источник> "<находка>" --ref <якорь> · '
               "один целиком: el ctx --section <источник>")
    return out


def cmd_ctx_add(args):
    """Record a RESEARCH source: what was looked at, what it showed, where to re-check.

    Research lives in its own folder at the project level (owner, 2026-08-21): research/,
    one file per SOURCE — code, a document, a device, a data store, the web, a book. Inside:
    the findings, each with a reference — the path, the link, the page — so any finding can
    be found AGAIN and verified. Findings append: one look at the code is rarely the last."""
    root = require_root()
    if not root:
        return 1
    task = pick_task(root, args.task)
    if not task:
        return 1
    if not args.source and not args.finding:
        # bare `el research` — the folder, readable: what was looked at, how much, how to open
        print(f"ИССЛЕДОВАНИЯ  {task} · research/")
        for l in research_lines(os.path.join(root, task)):
            print(l)
        return 0
    if not args.source or not args.finding:
        print("a source and a finding are required.", file=sys.stderr)
        print('hint     el research code "current copy sends name + lyric only" '
              '--ref path/to/File.kt:318', file=sys.stderr)
        print("         source is what you looked AT: code · db · logs · devices · ui · "
              "docs · web · book · data", file=sys.stderr)
        return 1
    name = norm_id(args.source)
    path = os.path.join(root, task, "research", f"{name}.md")
    if not os.path.exists(path):
        write(path, f"# Источник: {args.source.strip()}\n\n"
                    "_Что смотрели, что нашли и где это проверить снова. Каждая находка "
                    "с якорем — путём, ссылкой, страницей._\n")
    area = (getattr(args, "area", None) or "").strip().lower()
    if area and area not in AREA_KEYS:
        print(f"unknown --area '{area}'. one of: {', '.join(AREA_KEYS)}", file=sys.stderr)
        return 1
    body = open(path, encoding="utf-8").read()
    tag = f"  [область: {area}]" if area else ""
    body += f"\n## {now_iso()[:16]}{tag}\n\n{args.finding.strip()}\n"
    for ref in (args.ref or []):
        body += f"- якорь: `{ref}`\n"
    write(path, body)
    journal(root, task, "source", f"{args.source.strip()}: {args.finding.strip()[:70]}",
            {"refs": args.ref or [], "area": area or None})
    touch(root, task)
    print(f"recorded  research/{name}.md")
    print("next      el context — the big picture · el next — what still blocks the gate")
    return 0
