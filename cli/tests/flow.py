#!/usr/bin/env python3
"""flow.py — one task through all eight phases on the record-based storage (2026-08-27).

The differential test (scenario.py) asks «does el still do what it did». This one asks
«does the WHOLE ROAD hold»: a fresh storage, a task born, context gathered rung by rung,
думание with forks and paths, a map of stages, packages and tasks under a started stage —
inserted between and before, promises hung on every level, verdicts as events, the colour
folded to the root, his word at every stop, and the close. Every step is a real `el` call;
every phase ends in assertions on what is on disk and what the gates say.

    python3 cli/tests/flow.py                       the whole road, temporary storage, cleaned
    python3 cli/tests/flow.py --upto plan           stop AFTER plan — and keep the storage
    python3 cli/tests/flow.py --out /tmp/flow-plan  keep the storage here (implies keep)
    python3 cli/tests/flow.py --from plan --out D   resume a kept storage: `--upto think` leaves it
                                                    STANDING ON plan (think is done), so continue from plan
    python3 cli/tests/flow.py --serve 8770          after the run, serve the storage over http and print the page URL

`--upto` is how you LOOK at the page from a chosen point: run to a phase, open the URL,
see what the human sees. Assertions are named; a failed one is printed and counted, the
run goes on — the road is the thing under test, not one step.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EL = os.path.join(os.path.dirname(HERE), "el.py")
PHASES = ["context", "think", "plan", "execute", "validate", "reflect", "align", "close"]
TASK = "2026-08-27-flow-probe"

fails = []
steps = 0


STREAMS = ("records.jsonl", "checks.jsonl", "journal.jsonl")


def _bytes():
    out = {}
    for f in STREAMS:
        path = os.path.join(STORE, TASK, f)
        out[f] = open(path, "rb").read() if os.path.exists(path) else b""
    return out


def el(*args, ok=None):
    """Run one `el` command; return (rc, out). `ok` asserts the exit code when given.
    APPEND-ONLY, PROVEN ON EVERY CALL: the three streams may only grow, and what was there
    before the call is byte for byte the prefix of what is there after."""
    global steps
    steps += 1
    before = _bytes()
    env = dict(os.environ, ELEPHANT_DIR=STORE, ELEPHANT_FEEDBACK_DIR=os.path.join(WORK, "feedback"), ELEPHANT_DEBUG="1")
    p = subprocess.run([sys.executable, EL, *args], capture_output=True, text=True, env=env, cwd=WORK)
    out = (p.stdout or "") + (p.stderr or "")
    if ok is not None and p.returncode != ok:
        fails.append(f"exit {p.returncode} ≠ {ok}: el {' '.join(args)[:80]}\n    {out.strip()[:300]}")
    after = _bytes()
    for f in STREAMS:
        if not after[f].startswith(before[f]):
            fails.append(f"{f} ПЕРЕПИСАН (не append-only) на: el {' '.join(args)[:80]}")
    return p.returncode, out


def invariants():
    """What must hold on disk whatever the road did."""
    for f in ("records", "checks"):
        seqs = [r.get("seq", 0) for r in records(f)]
        check(f"{f}.jsonl: seq строго растёт", seqs == sorted(seqs) and len(set(seqs)) == len(seqs))
        ids = [r.get("id") for r in records(f) if r.get("id")]
        check(f"{f}.jsonl: id не повторяются", len(ids) == len(set(ids)), ", ".join(i for i in ids if ids.count(i) > 1)[:80])
    proms = [r for r in records("checks") if r.get("type") not in ("verdict", "amend")]
    check("у каждого обещания есть «чем проверим»", all((p.get("how") or "").strip() for p in proms))
    check("у каждого обещания есть адрес", all(p.get("at") for p in proms))
    first_event = {}
    for e in records("journal"):
        if e.get("type") in ("node-start", "node-done", "node-wait", "node-park"):
            nid = (e.get("text") or "").split(":", 1)[0].strip().split(" ")[0]
            first_event.setdefault(nid, e.get("ts", ""))
    for n in [r for r in records() if r.get("type") == "node"]:
        ev = first_event.get(n["id"])
        check(f"узел {n['id']} заведён ДО работы", not ev or n.get("ts", "") <= ev, f"узел {n.get('ts')} · событие {ev}")
    md = no_markdown()
    check("на диске нет markdown (кроме артефактов)", not md, ", ".join(md))


def check(name, cond, detail=""):
    if not cond:
        fails.append(f"{name}" + (f" — {detail}" if detail else ""))
    return cond


def records(stream="records"):
    path = os.path.join(STORE, TASK, stream + ".jsonl")
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def phase():
    rc, out = el("status")
    for ph in PHASES:
        if f"phase {PHASES.index(ph) + 1}/8 {ph}" in out:
            return ph
    return "?"


def gate_open():
    rc, out = el("next")
    return "gate     open" in out or "gate      открыт" in out or "gate     ОТКРЫТ" in out


def no_markdown():
    """The whole point: nothing the tool writes is markdown any more."""
    md = []
    for dp, dn, fn in os.walk(os.path.join(STORE, TASK)):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), os.path.join(STORE, TASK))
            if f.endswith(".md") and not rel.startswith(("artifacts/", "evidence/", "notes/")):
                md.append(os.path.relpath(os.path.join(dp, f), os.path.join(STORE, TASK)))
    return md


# ── the road ────────────────────────────────────────────────────────────────────────────

def ph_context():
    el("boot", "Сквозная проба: одна задача через все фазы на записях", "--id", "flow-probe",
       "--raw", "прогони всё от начала до конца", ok=0)
    check("задача родилась в контексте", phase() == "context")
    check("гейт закрыт без слова", not gate_open())
    el("context", "qa", "Как этим пользуются?", "Через el, каждый день", "--area", "goal", "--options", "el · руками", ok=0)
    el("context", "qa", "Как поймёшь, что стало лучше?", "Агент реже спотыкается", "--area", "check", "--new-round", ok=0)
    for a in ("must", "outcome", "limits", "why", "who", "when"):
        el("context", "qa", f"вопрос про {a}", f"ответ про {a}", "--area", a, ok=0)
    el("research", "code", "фаза context = 20 md-файлов", "--ref", "cli/el/context.py:18", "--area", "how", ok=0)
    el("context", "now", "агент читает 20 файлов", "--kind", "flow", ok=0)
    el("context", "now", "20 файлов на фазу", "--kind", "number", ok=0)
    el("context", "now", "витрина есть, потоков нет", "--kind", "state", ok=0)
    for d in ("what", "why", "who", "where", "when", "how"):
        el("context", "scope", d, "--in", f"входит: {d}", "--out", f"не входит: {d}", ok=0)
    el("context", "scope", "what", "--drop", "входит: what", ok=0)
    check("снятая строка границы осталась в истории", any(r.get("type") == "amend" for r in records()))
    el("context", "condition", "forbidden", "старые проекты не мигрируем", ok=0)
    el("context", "requirement", "store.py — дверь записи", "--state", "have", ok=0)
    el("context", "beyond", "фаза think", "--candidate", "--why", "тот же паттерн", ok=0)
    rc, _ = el("context", "success", "без how")
    check("обещание без «чем проверим» отвергнуто", rc != 0)
    el("context", "success", "агент реже спотыкается", "--observable", "меньше отзывов", "--how", "считать feedback/", ok=0)
    el("context", "metric", "мест парсинга прозы", "--threshold", "0", "--unit", "модулей", "--direction", "down", "--how", "grep re.match", "--baseline", "6", ok=0)
    el("context", "check", "открыть overview.html и увидеть весь контекст", "--how", "глазами", ok=0)
    el("context", "ifr", "Открываю страницу — и вижу всю картину.", ok=0)
    el("context", "part", "перестроить формат контекста", "--covers", "k1", ok=0)
    el("context", "part", "витрина", "--covers", "k1", ok=0)
    el("context", "define", "обещание", "проверяемое ожидание", "--heard", "критерий валидации", ok=0)
    el("context", "unknown", "как поведёт себя дифф-тест", "--how", "переписать scenario.py", ok=0)
    el("context", "clarified", "Перевести контекст на единый поток.", ok=0)
    el("context", "summary", "Собрано.", ok=0)
    check("слово ещё не дано — гейт закрыт", not gate_open())
    el("accept", "да, картина моя", ok=0)
    check("слово дано — гейт открыт", gate_open())
    el("context", "qa", "вопрос после слова", "ответ", "--area", "why", ok=0)
    check("запись после слова — слово устарело, гейт закрыт", not gate_open())
    el("accept", "да, и так", ok=0)
    check("свежее слово — открыт", gate_open())
    proms = [r for r in records("checks") if r.get("type") != "verdict"]
    check("три обещания родились на корне", len(proms) == 3 and all(p.get("at") == "task" for p in proms), str(len(proms)))
    el("forward", "--why", "контекст собран", ok=0)
    check("перешли в думание", phase() == "think", phase())


def ph_think():
    el("think", "mirror", "владелец", "--does", "смотрит страницу", "--affected", "видит полосы", "--tool", "мышление профессий", ok=0)
    el("think", "form", "страница с лентами", ok=0)
    el("think", "core", "поток записей", "--rank", "core", "--tool", "Парето", ok=0)
    rc, _ = el("think", "promise", "без how")
    check("инженерное обещание без how отвергнуто", rc != 0)
    el("think", "promise", "ничего не переписывается", "--how", "grep write(", "--breaks-if", "вернут --replace", ok=0)
    el("think", "irreversible", "переименование потока", "--guard", "snapshot git", ok=0)
    el("think", "option", "один поток", "--text", "все фазы в одном файле", "--score", "m1=6 → 0", "--score", "k1=да", "--score", "cr1=да", "--tool", "морфологический ящик", ok=0)
    el("think", "option", "поток на фазу", "--text", "файл на фазу", "--score", "m1=6 → 0", ok=0)
    el("think", "stress", "два агента пишут разом", "--path", "pt1", "--promise", "cr1", "--held", "yes", "--why-held", "append-only", "--tool", "адвокат дьявола", ok=0)
    rc, _ = el("think", "fork", "без why-yours", "--option", "а · + · −", "--option", "б · + · −")
    check("развилка без «почему твоё» отвергнута", rc != 0)
    el("think", "fork", "три файла сразу или промежуточная?", "--option", "сразу · один переход · ломаем всё", "--option", "промежуточная · шаг за шагом · дольше", "--recommend", "промежуточная", "--why-yours", "аппетит к риску — твой", ok=0)
    check("развилка открыта — гейт закрыт", not gate_open())
    el("think", "decide", "fk1", "промежуточная", "--words", "промежуточная, потом три файла", ok=0)
    el("think", "crystal", "выжила тропа pt1", "--path", "pt1", "--decided", "fk1", ok=0)
    el("think", "route", "перевести контекст", ok=0)
    el("think", "route", "перевести думание", "--after", "rt1", ok=0)
    el("think", "risk", "сломаем el посреди правки", "--chance", "mid", "--cost", "теряем учёт", "--then", "чиним el первым", ok=0)
    el("accept", "да, тропа моя", ok=0)
    check("думание: гейт открыт", gate_open())
    el("forward", "--why", "решение принято", ok=0)
    check("перешли в план", phase() == "plan", phase())


def ph_plan():
    el("plan", "new", "s1", "перевести контекст", ok=0)
    el("plan", "new", "s2", "перевести думание", ok=0)
    el("plan", "new", "s3", "итоговая проверка", ok=0)
    el("plan", "set", "s2", "deps", "после S1", ok=0)
    el("plan", "set", "s3", "deps", "после S2", ok=0)
    el("plan", "new", "s4", "витрина", "--after", "s1", "--before", "s2", ok=0)
    rc, out = el("plan", "s2")
    check("вставка между: S2 теперь после S4", "S4" in out, out[:200])
    for st in ("s1", "s4", "s2", "s3"):
        el("plan", "set", st, "result", f"{st} закрыт наблюдаемо", ok=0)
        el("plan", "set", st, "sync", "ПОКАЗ\\nпоказываю: страницу\\nувидишь: полосы\\nпотрогать: карточки\\nот тебя: ничего", ok=0)
        el("plan", "promise", st, f"{st} выдаёт своё", "--how", "глазами", ok=0)
    el("plan", "set", "s2", "sync", "РАЗРЕШЕНИЕ\\nпоказываю: ленту думания\\nувидишь: таблицу\\nпотрогать: развилки\\nот тебя: слово", ok=0)
    el("plan", "set", "s1", "covers", "ifr 1, part 1", ok=0)
    el("plan", "set", "s4", "covers", "part 2", ok=0)
    nodes = [r for r in records() if r.get("type") == "node"]
    check("четыре этапа записями", len(nodes) == 4, str(len(nodes)))
    check("plan.md не появился", not os.path.exists(os.path.join(STORE, TASK, "plan.md")))
    check("nodes/ не появилась", not os.path.isdir(os.path.join(STORE, TASK, "nodes")))
    check("без слова над картой — закрыт", not gate_open())
    el("accept", "да, карта моя", ok=0)
    check("слово над картой — открыт", gate_open())
    el("forward", "--why", "карта принята", ok=0)
    check("перешли в исполнение", phase() == "execute", phase())


def ph_execute():
    rc, out = el("plan", "start", "s1")
    check("этап без раскладки не стартует", "НЕ РАЗЛОЖЕН" in out or rc != 0)
    el("accept", "да, раскладка S1", "--for", "stage:s1", ok=0)
    el("plan", "new", "s1", "wp1", "store.py", ok=0)
    el("plan", "new", "s1", "wp2", "context.py", ok=0)
    el("plan", "set", "s1.wp2", "deps", "после S1.WP1", ok=0)
    el("plan", "new", "s1", "wp3", "protocol.py", "--after", "s1.wp1", "--before", "s1.wp2", ok=0)
    rc, out = el("plan", "s1.wp2")
    check("пакет вставлен между: WP2 после WP3", "S1.WP3" in out, out[:200])
    for w in ("wp1", "wp3", "wp2"):
        el("plan", "set", f"s1.{w}", "result", f"{w} готов", ok=0)
        el("plan", "set", f"s1.{w}", "sync", "ПОКАЗ\\nпоказываю: результат\\nувидишь: файл\\nпотрогать: команду\\nот тебя: ничего", ok=0)
        el("plan", "promise", f"s1.{w}", f"{w} держит своё", "--how", "прогон", ok=0)
    el("plan", "start", "s1.wp1", ok=0)
    el("plan", "new", "s1", "wp1", "t1", "read/append", ok=0)
    el("plan", "new", "s1", "wp1", "t2", "verdict", ok=0)
    el("plan", "new", "s1", "wp1", "t0", "снапшот", "--before", "s1.wp1.t1", ok=0)
    rc, out = el("plan", "s1.wp1.t1")
    check("задача вставлена в начало: T1 после T0", "S1.WP1.T0" in out, out[:200])
    for t in ("t0", "t1", "t2"):
        el("plan", "set", f"s1.wp1.{t}", "result", f"{t} сделан", ok=0)
        el("plan", "set", f"s1.wp1.{t}", "sync", "ПОКАЗ\\nпоказываю: t\\nувидишь: результат\\nпотрогать: —\\nот тебя: ничего", ok=0)
        el("plan", "promise", f"s1.wp1.{t}", f"{t} держит", "--how", "прогон", ok=0)
    el("log", "написал store.append", ok=0)
    el("validate", "s1.wp1.t1", "1", "--failed", "seq 3 вместо 2", ok=0)
    rc, out = el("plan", "done", "s1.wp1.t1", "append работает")
    check("узел с не сошедшимся критерием не закрывается", rc != 0)
    el("validate", "s1.wp1.t1", "1", "--met", "починил", ok=0)
    for t in ("t0", "t1", "t2"):
        if t != "t1":
            el("plan", "start", f"s1.wp1.{t}", ok=0)
            el("validate", f"s1.wp1.{t}", "1", "--met", "проверено", ok=0)
        el("plan", "done", f"s1.wp1.{t}", f"{t} готов", ok=0)
    el("validate", "s1.wp1", "1", "--met", "проверено", ok=0)
    el("plan", "done", "s1.wp1", "store.py готов", ok=0)
    for w in ("wp3", "wp2"):
        el("plan", "start", f"s1.{w}", ok=0)
        el("validate", f"s1.{w}", "1", "--met", "проверено", ok=0)
        el("plan", "done", f"s1.{w}", f"{w} готов", ok=0)
    el("validate", "s1", "1", "--met", "проверено", ok=0)
    el("plan", "done", "s1", "контекст на потоке", ok=0)
    for st in ("s4", "s2", "s3"):
        el("plan", "start", st, "--force", ok=0)
        el("validate", st, "1", "--met", "проверено", ok=0)
        if st == "s2":
            rc, out = el("plan", "done", st, "думание на потоке")
            check("РАЗРЕШЕНИЕ без слова не закрывается", rc != 0)
            el("accept", "да, думание принимаю", "--for", "node:s2", ok=0)
        el("plan", "done", st, f"{st} закрыт", ok=0)
    verd = [r for r in records("checks") if r.get("type") == "verdict"]
    check("вердикты — события в реестре", len(verd) >= 10, str(len(verd)))
    check("validation.md не появился", not os.path.exists(os.path.join(STORE, TASK, "validation.md")))
    os.makedirs(os.path.join(WORK, "out"), exist_ok=True)
    open(os.path.join(WORK, "out", "store-note.md"), "w").write("store.py\n")
    open(os.path.join(WORK, "out", "grep.txt"), "w").write("0\n")
    el("artifact", os.path.join(WORK, "out", "store-note.md"), "--node", "s1.wp1", ok=0)
    el("evidence", os.path.join(WORK, "out", "grep.txt"), "--node", "s1.wp1", "--check", "1", ok=0)
    el("forward", "--why", "все узлы закрыты", ok=0)
    check("перешли в проверку", phase() == "validate", phase())


def ph_validate():
    rc, out = el("validate")
    check("леджер печатается", "ПРОВЕРКА" in out)
    check("без приёмки — закрыт", not gate_open())
    el("validate", "task", "1", "--met", "feedback/ пуст", ok=0)
    el("validate", "task", "2", "--met", "grep: 0", ok=0)
    el("validate", "task", "3", "--met", "0 перезаписей", ok=0)
    el("validate", "ifr", "1", "--met", "страница открыта", ok=0)
    sys.path.insert(0, os.path.dirname(HERE))
    from el import store
    from el.plan import nodes_all
    tdir = os.path.join(STORE, TASK)
    tree = {}
    for n in nodes_all(tdir):
        tree.setdefault(n.get("parent") or "task", []).append(n["id"])
    col = store.colour(STORE, TASK, tree)
    check("корень зелёный после всех вердиктов", col["colour"] == "green", store.colour_line(col))
    el("accept", "принимаю", "--for", "final", ok=0)
    check("приёмка дана — открыт", gate_open())
    check("acceptance.md не появился", not os.path.exists(os.path.join(STORE, TASK, "acceptance.md")))
    el("forward", "--why", "всё сошлось", ok=0)
    check("перешли в рефлексию", phase() == "reflect", phase())


def ph_extras():
    """The side roads every real task walks: a todo, an owner's debt, a grant with a decision
    in his place, an amendment after his word, a node parked and a stage reopened, the return
    card, the printed picture, the doctor, the index page."""
    el("todo", "перевести guide на записи", "--when", "close", ok=0)
    rc, out = el("todo", "--list"); check("отложенное видно", "guide" in out)
    el("owe", "какой порог у m1 на живом проекте?", "--how", "спросить владельца", ok=0)
    rc, out = el("owe"); check("долг владельца открыт", "порог" in out)
    el("owe", "answer", "1", "ноль", ok=0)
    el("grant", "работай сам до конца этапа", "--name", "проба", "--hours", "1", ok=0)
    el("context", "qa", "вопрос под грантом", "ответ в его место", "--area", "why", "--assumed", "грант «проба»", ok=0)
    rc, out = el("review"); check("решение под грантом видно в review", "его место" in out or "решени" in out)
    el("grant", "end", "этап пройден", ok=0)
    rc, out = el("context", "requirement", "новое требование после слова", "--state", "missing")
    check("правка контекста после выхода из фазы без --why отвергнута", rc != 0)
    el("context", "requirement", "новое требование после слова", "--state", "missing", "--why", "всплыло на исполнении", "--ref", "evidence/grep.txt", ok=0)
    rc, out = el("resume"); check("карточка возврата печатается", "el next" in out or "ход" in out)
    rc, out = el("context", "--full"); check("картина печатается целиком", "ГРАНИЦЫ" in out.upper() or "SCOPE" in out.upper())
    rc, out = el("doctor"); check("doctor отвечает", rc in (0, 1))


def ph_reflect():
    el("lesson", "коллизии имён ловить grep'ом до правки", ok=0)
    el("forward", "--why", "урок записан", ok=0)
    check("перешли в сверку", phase() == "align", phase())


def ph_align():
    el("forward", "--why", "приехали", ok=0)
    check("перешли в закрытие", phase() == "close", phase())


def ph_close():
    rc, out = el("done", "проба прошла все восемь фаз", "--dirty", "проба вне git")
    check("открытое «на потом» держит закрытие", rc != 0)
    el("todo", "--done", "1", "guide переведён", ok=0)
    el("done", "проба прошла все восемь фаз", "--dirty", "проба вне git", ok=0)
    rc, out = el("status")
    check("задача закрыта", "все задачи закрыты" in out or "closed" in out, out[:200])


ROAD = [("context", ph_context), ("think", ph_think), ("plan", ph_plan), ("execute", ph_execute),
        ("validate", ph_validate), ("reflect", ph_reflect), ("align", ph_align), ("close", ph_close)]


def main():
    global STORE, WORK
    ap = argparse.ArgumentParser()
    ap.add_argument("--upto", choices=PHASES)
    ap.add_argument("--from", dest="from_", choices=PHASES)
    ap.add_argument("--out")
    ap.add_argument("--serve", type=int)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    WORK = a.out or tempfile.mkdtemp(prefix="el-flow-")
    os.makedirs(WORK, exist_ok=True)
    STORE = os.path.join(WORK, ".projects")
    keep = a.keep or bool(a.out) or bool(a.upto) or bool(a.serve)
    start = PHASES.index(a.from_) if a.from_ else 0
    stop = PHASES.index(a.upto) if a.upto else len(PHASES) - 1
    if a.from_:
        check("продолжаем с той фазы, на которой стоит хранилище", phase() == a.from_, phase())
    for name, fn in ROAD[start:stop + 1]:
        before = len(fails)
        fn()
        if name == "execute" and not a.upto:
            ph_extras()
        print(f"{'✓' if len(fails) == before else '✗'} {name:<9} шагов {steps}" + (f" · провалов {len(fails) - before}" if len(fails) > before else ""))
    before = len(fails)
    invariants()
    print(f"{'✓' if len(fails) == before else '✗'} инварианты" + (f" · провалов {len(fails) - before}" if len(fails) > before else ""))
    el("ui", "update")
    check("index-data.js собирается", os.path.exists(os.path.join(STORE, "metadata", "index-data.js")))
    check("данные страницы собираются", os.path.exists(os.path.join(STORE, "metadata", TASK + ".js")))
    print()
    if fails:
        print(f"ПРОВАЛОВ {len(fails)}:")
        for f in fails:
            print("  ✗ " + f)
    else:
        print(f"ВСЁ ДЕРЖИТ · шагов {steps}")
    page = os.path.join(STORE, TASK, "overview.html")
    if keep:
        print(f"\nхранилище: {STORE}\nстраница:  {page}")
    if a.serve:
        print(f"смотреть:  http://localhost:{a.serve}/{TASK}/overview.html")
        os.chdir(STORE)
        subprocess.run([sys.executable, "-m", "http.server", str(a.serve)])
    elif not keep:
        shutil.rmtree(WORK, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
