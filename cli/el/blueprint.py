"""The contract as SCREENS — knowledge in doses (owner, 2026-08-22).

One law: every screen fits one tool call; the big picture is read once, the detail is read
at the place where the agent stands. So the contract has addresses instead of grep:

    el blueprint            the big picture — rule · modes · nine declarations · rules in short
    el blueprint <фаза>     one phase with all its beats (the card the agent reads on entry)
    el blueprint rules      the rules above the phases · modes · files — the other sections
    el blueprint full       everything in one stream — the human's one-shot listing

Everything is rendered from the single beat table (protocol.phase_beats) in ONE outline
shape: a phase declaration, under it the beats with an indent, under each beat its card
(файл · required|optional · описание · команда), wrapped to the terminal width with hanging
indents so a continuation line never jumps to column 0.
"""
import shutil, sys
from .protocol import (AUTONOMY_RULES, AUTONOMY_TITLE, BRIEF_CHARS, BRIEF_LINES, CONTEXT_FILES,
                       CONTEXT_MIN, MODE_RU, MODES, OUTCOME_RU, OUTCOMES, PHASE_BRIEF, PHASE_MAP,
                       PHASE_MODE, PHASE_TITLES, PHASES, SEARCH_RULES, SEARCH_TITLE, WHO_RU,
                       phase_beats, required_in)
from .term import wrap

I1, I2, LW = 5, 9, 11          # beat indent · card indent · card label width
PARTS = ["init"] + PHASES + ["rules", "modes", "files", "autonomy", "search", "full"]
ALIASES = {"0": "init", "инициализация": "init", "правила": "rules", "режимы": "modes",
           "файлы": "files", "всё": "full", "все": "full", "all": "full",
           "автономия": "autonomy", "auto": "autonomy", "поиск": "search", "loop": "search",
           "цикл": "search"}
ALIASES.update({str(i): ph for i, ph in enumerate(PHASES, 1)})


def resolve_part(word):
    w = (word or "").strip().lower()
    w = ALIASES.get(w, w)
    return w if w in PARTS else None


def screen_width():
    W = shutil.get_terminal_size((100, 24)).columns if sys.stdout.isatty() else 100
    return max(64, min(W, 110))


def para(text, indent, W):
    return " " * indent + wrap(text, indent=" " * indent, width=W - indent)


def card(label, text, W):
    pad = " " * (I2 + LW)
    return " " * I2 + f"{label:<{LW}}" + wrap(text, indent=pad, width=W - I2 - LW)


def req_line(minmode, who, mode):
    since = {"light": "всегда", "soft": "с режима soft", "strict": "с режима strict"}[minmode]
    if required_in(minmode, mode):
        return ("required", f"{since} · {WHO_RU.get(who, who)}")
    return ("optional", f"обязателен {since} · {WHO_RU.get(who, who)}")


def rule(W):
    return "─" * W


def exit_line(ph):
    if ph == "init":
        return "выход: el next ведёт в контекст; пока запрос не записан — напоминает"
    if ph == "close":
        return 'выход: фаза последняя — закрывает el done "<результат>" --as <вид>'
    return 'выход: el forward --why "<что закрыто и чем доказано>"'


def title_line(ph):
    if ph == "init":
        return "0/8  ИНИЦИАЛИЗАЦИЯ — рождение проекта"
    return f"{PHASES.index(ph) + 1}/8  {ph.upper()} — {PHASE_TITLES.get(ph, '')}"


def declaration(ph, W):
    """The phase declaration: title · mind · gate · exit."""
    out = [title_line(ph)]
    if ph == "init":
        out.append(para("когда: из разговора появилась СФОРМУЛИРОВАННАЯ задача — не раньше: разговор "
                        "без задачи бухгалтерии не заводит", I1, W))
        out.append(para("гейт: дерево на диске и init/request.md записан — только после этого "
                        "начинается контекст", I1, W))
    else:
        if PHASE_MODE.get(ph):
            out.append(para(PHASE_MODE[ph], I1, W))
        gate = PHASE_MAP.get(ph, {}).get("gate")
        if gate:
            out.append(para("гейт: " + gate.rstrip(" ·"), I1, W))
    out.append(para(exit_line(ph), I1, W))
    return out


def beats_block(ph, mode, W):
    out = []
    for title, who, trace, minmode, desc, cmd in phase_beats(ph):
        out.append(para(title, I1, W))
        head = trace.split()[0] if trace.split() else ""
        out.append(card("файл" if ("/" in head or head.endswith(".md")) else "след", trace, W))
        out.append(card(*req_line(minmode, who, mode), W))
        out.append(card("описание", desc, W))
        out.append(card("команда", cmd, W))
        out.append("")
    return out


def beats_short(ph, mode, W):
    """The beat list without cards — what `el forward` shows on entering a phase."""
    out = []
    for title, who, trace, minmode, _desc, _cmd in phase_beats(ph):
        mark = "●" if required_in(minmode, mode) else "○"
        out.append(para(f"{mark} {title} — {trace} · {WHO_RU.get(who, who)}", I1, W))
    return out


def counts(ph, mode):
    beats = phase_beats(ph)
    return len(beats), sum(1 for b in beats if required_in(b[3], mode))


def header_block(mode, W):
    return ["ELEPHANT — КОНТРАКТ ПРОТОКОЛА", "",
            para("Задача проходит 8 фаз по порядку: вперёд — по одной и с названным основанием, "
                 "назад — свободно, возврат штатен. Такт засчитан следом на диске, не отметкой. "
                 "Слово человека (контекст · план · приёмка) и целостность графа узлов — вне "
                 "режимов: их не снимает ничто.", I1, W), ""]


def modes_block(mode, W):
    out = [para(f"режимы — ползунок строгости. У такта: required — обязателен в режиме {mode}, "
                f"optional — по нужде; рядом — с какого режима обязателен и от кого след.", I1, W)]
    for m in MODES:
        out.append(" " * I2 + f"{'▶' if m == mode else '·'} {m:<8} {MODE_RU[m]}")
    out.append(para('другой режим: el blueprint --mode light|soft|strict · сменить у задачи: '
                    'el mode <режим> --why "…"', I2, W))
    out.append("")
    return out


def rules_block(mode, W):
    out = ["ПРАВИЛА ПОВЕРХ ФАЗ", ""]

    def block(title, *paras):
        out.append(" " * I1 + title)
        for t in paras:
            out.append(para(t, I2, W))
        out.append("")

    n_ctx = len([k for k in CONTEXT_FILES if required_in(CONTEXT_MIN.get(k, "soft"), mode)])
    block("права",
          "приёмку на VALIDATE даёт ЧЕЛОВЕК — агент себе «ок» сказать не может",
          "waiver (пропуск гейта) выдаёт человек; агент может только запросить",
          "фазу пройденной объявляет CLI по следам, а не агент по ощущению")
    block("гейт",
          "мягкий: показывает, чего не хватает, и пускает с пометкой waived — кроме слова "
          "человека и целостности графа узлов, которые не обходятся никогда",
          f"из контекста не пускает без {n_ctx} следов (режим {mode}) — это фаза с наибольшей "
          "ценой пропуска; в strict --waive не работает вовсе",
          "через фазу не прыгает: execute из context объявить нельзя")
    block("синхронизация — ось всего цикла: три больших остановки и два ритма",
          "1. СЛОВО НАД КАРТИНОЙ (выход из контекста): собранное предъявлено, его «да» записано "
          "дословно — жёстко, не обходится. Направление сверено ДО думания",
          "2. СЛОВО НАД ВЫБОРОМ (думание → план): развилки человека закрыты его словами, спуск в "
          "план — принятие, что уровень выше закрыт. Решение сверено ДО работы",
          "3. ПРИЁМКА (проверка): показано так, что можно потрогать; принял человек. Результат "
          "сверен ДО закрытия",
          "ритм 1: цикл вопросов на контексте — после каждого раунда «вот как понимаю — продолжать "
          "или достаточно?»; конец опроса решает человек",
          "ритм 2: остановки исполнения — по плану (поле sync узла), не на ходу",
          "каждая большая остановка стоит ПЕРЕД местом, где ошибка направления дорожает. Человек "
          "вовлёкся и говорит — он В ВОЛНЕ: слушай, спрашивай, раскладывай его слова по файлам НА "
          "ХОДУ — синергия и есть цель синхронизации")
    block("поправки — картина меняется, история остаётся",
          "запись в документ фазы ПОСЛЕ выхода из неё — поправка, не сбор: те же команды "
          '(el context clarified "…", el context scope what --out "…" --drop "…", el think shoals "…"), '
          "но --why обязателен, --ref даёт основание (развилка · research/… · evidence/… · его слова), "
          "--replace запрещён: старое не стирается, в границе снятая строка зачёркивается [пN]",
          "поправка после его слова вновь открывает слово над картиной: el next показывает, el forward "
          "не пускает без свежего el accept — либо осознанно --waive",
          "цель задачи = task.clarified.md с поправками (его словами) + thinking/crystal.md "
          "(инженерно); отдельного destination нет")
    block("внешние следы",
          "работа, живущая во внешней системе, закрыта только когда след оставлен ТАМ: код — "
          "закоммичен и влит (ветку и порядок merge реши на думании) · база — миграция применена и "
          "записана · документ — отправлен адресату",
          "git CLI меряет САМ: el done не закрывает задачу над грязным деревом — закоммить, либо "
          'осознанно: --dirty "<почему без коммита>" (уйдёт в журнал)',
          "остальные внешние системы не меряются — их следы пиши в критерии узлов")
    out.append(" " * I1 + 'чем кончается задача — el done "<результат>" --as <вид>')
    w = max(len(k) for k in OUTCOMES)
    for kind in OUTCOMES:
        out.append(" " * I2 + f"{kind:<{w}}  {OUTCOME_RU.get(kind, OUTCOMES[kind])}")
    out.append(para("completed запрещён, пока открыт хотя бы один el todo (напоминание --every "
                    "не в счёт)", I2, W))
    out.append("")
    out.append(" " * I1 + "команды для человека — только читают, ничего не меняют, безопасны всегда")
    for c, what in (("el status", "где мы: какой проект, какая фаза, что заполнено"),
                    ("el projects", "какие проекты есть: открытые, закрытые и чем кончились"),
                    ("el next", "какой ход следующий и чего не хватает"),
                    ("el left", "что осталось до конца задачи"),
                    ("el progress", "история задачи одним экраном: главные файлы каждой фазы целиком"),
                    ("el doctor", "где граф узлов и следы расходятся"),
                    ("el blueprint", "контракт: big picture · <фаза> · rules · files · full · --mode"),
                    ("el help", "команды · el help <команда|группа> — одна"),
                    ("el ui", "обновить страницы для браузера сейчас · --open откроет их")):
        out.append(" " * I2 + f"{c:<14}{what}")
    out.append(para("то же глазами, без терминала: overview.html в папке проекта · index.html в "
                    "хранилище — открываются двойным кликом", I2, W))
    out.append("")
    return out


def named_block(title, rules, W):
    """A titled list of (label, text) cards — the autonomy and search sections."""
    out = [title, ""]
    for label, text in rules:
        out.append(card(label, text, W))
        out.append("")
    return out


def autonomy_block(W):
    return named_block(AUTONOMY_TITLE, AUTONOMY_RULES, W)


def search_block(W):
    return named_block(SEARCH_TITLE, SEARCH_RULES, W)


def files_block(W):
    out = ["ГДЕ ЧТО ЛЕЖИТ", ""]
    for path, what in (("init/request.md", "запрос пользователя — его словами, только о задаче"),
                       ("context/", "сбор: вопросы, рамка scope, ИФР, свёртка — выходы фазы"),
                       ("research/", "исследования: по файлу на ИСТОЧНИК (код · документ · база · "
                                     "устройство · веб · книга); находки с якорями для перепроверки"),
                       ("thinking/", "лестница думания: варианты с ценой · decisions.md — леджер "
                                     "развилок · options.md — досье гейтов · previews/ — превью к "
                                     "развилкам · кристалл"),
                       ("plan.md, nodes/", "сетевой план и декомпозиция по уровням"),
                       ("artifacts/", "что произведено · evidence/ — чем доказано"),
                       ("brief.md", f"листок агента: baseline · замер · лучшее · не повторять · сейчас; "
                                    f"переписывается целиком, ≤ {BRIEF_LINES} строк / {BRIEF_CHARS} "
                                    "символов; el и el status печатают его первым"),
                       ("journal.jsonl", "append-only хроника: ts · type · text"),
                       ("overview.html", "страница проекта для человека — читатель базы; её данные CLI "
                                         "кладёт в ../metadata/ при каждой записи, а саму страницу "
                                         "держит равной шаблону скилла · ../index.html — все проекты")):
        pad = " " * (I2 + 17)
        out.append(" " * I2 + f"{path:<17}" + wrap(what, indent=pad, width=W - I2 - 17))
    out.append("")
    return out


def phase_screen(ph, mode, W):
    return declaration(ph, W) + [""] + beats_block(ph, mode, W)


def big_picture(mode, W):
    """One screen: the rule, the modes, nine declarations, the rules in short, the addresses."""
    out = header_block(mode, W) + modes_block(mode, W)
    out.append(para("читать дальше: el blueprint <фаза> — такты фазы, в которой стоишь · "
                    "el blueprint rules · modes · files · autonomy · search · full (всё одним списком, "
                    "длинный)", I1, W))
    for ph in ["init"] + PHASES:
        out.append(rule(W))
        out.append(title_line(ph))
        out.append(para("суть: " + PHASE_BRIEF.get(ph, ""), I1, W))
        gate = ("дерево на диске и init/request.md записан" if ph == "init"
                else PHASE_MAP.get(ph, {}).get("gate", "").rstrip(" ·"))
        out.append(para("гейт: " + gate, I1, W))
        out.append(para(exit_line(ph), I1, W))
        n, req = counts(ph, mode)
        out.append(para(f"такты: {n} · обязательных в {mode}: {req} · подробно: el blueprint "
                        f"{'init' if ph == 'init' else ph}", I1, W))
    out.append(rule(W))
    out.append("ПРАВИЛА ПОВЕРХ ФАЗ — коротко · подробно: el blueprint rules")
    for line in (
        "права: приёмку даёт человек · waiver выдаёт человек · фазу пройденной объявляет CLI по следам",
        "гейт: мягкий — пускает с пометкой waived, кроме слова человека и целостности графа узлов; "
        "через фазу не прыгает; в strict --waive не работает",
        "синхронизация: три остановки — слово над картиной (контекст → думание) · слово над выбором "
        "(думание → план) · приёмка (проверка → закрытие); ритмы — раунды вопросов и остановки узлов по плану",
        "поправки: запись в документ прошлой фазы — с --why и --ref, без --replace; после его слова "
        "нужно свежее слово",
        "внешние следы: закрыто, когда след оставлен там — код влит · миграция применена · документ "
        "отправлен; git el done меряет сам",
        'исходы: completed · closed · dropped · blocked — el done "<результат>" --as <вид>',
        "автономия: человек сказал «работай сам» — el grant \"<его слова>\"; слово занимают (--assumed), "
        "долг видит el review, последнее слово не занимают, граница — el halt; листок brief.md — "
        "первым · подробно: el blueprint autonomy",
        "поиск «работай, пока не …»: S1 стенд и baseline · S2 гипотеза = узел, растёт по ходу · S3 "
        "проверка на живом; результат попытки одной строкой · подробно: el blueprint search",
        "читать: el status — где мы · el next — что делать · el left — что осталось · el progress — "
        "история задачи: главные файлы фаз целиком · el doctor — где расходится · el help — команды · "
        "el blueprint files — где что лежит",
    ):
        out.append(para(line, I1, W))
    return out


def full_screen(mode, W):
    out = header_block(mode, W) + modes_block(mode, W)
    for ph in ["init"] + PHASES:
        out.append(rule(W))
        out += phase_screen(ph, mode, W)
    out.append(rule(W))
    out += rules_block(mode, W)
    out += files_block(W)
    out.append(rule(W))
    out += autonomy_block(W)
    out.append(rule(W))
    out += search_block(W)
    out.append(" " * I1 + "дальше: el status — где мы · el next — что делать · el help — команды")
    return out


def render(part, mode, W=None):
    """Text of one screen of the contract. part: None (big picture) · phase · init · rules ·
    modes · files · full."""
    W = W or screen_width()
    if not part:
        return "\n".join(big_picture(mode, W))
    if part == "full":
        return "\n".join(full_screen(mode, W))
    if part == "rules":
        return "\n".join(rules_block(mode, W))
    if part == "modes":
        return "\n".join(header_block(mode, W) + modes_block(mode, W))
    if part == "files":
        return "\n".join(files_block(W))
    if part == "autonomy":
        return "\n".join(autonomy_block(W))
    if part == "search":
        return "\n".join(search_block(W))
    return "\n".join(phase_screen(part, mode, W))


def phase_brief(ph, mode, W=None):
    """What `el forward` / `el phase` print on entering a phase: the declaration, the beats
    in one line each (● required · ○ optional), and the address of the full card."""
    W = W or screen_width()
    out = [""] + declaration(ph, W) + [""] + beats_short(ph, mode, W)
    out.append(para(f"подробно, с описанием и командой каждого такта: el blueprint {ph}", I1, W))
    return "\n".join(out)
