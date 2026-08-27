"""The CONTRACT of the protocol — data, no behaviour.

What the phases are, what each one fills in and where, who the answer comes from, what
proves the move on, the words the agent reads about HOW to work a phase. `el blueprint`
prints this module; every gate (`el next`, `el forward`, `el status`) reads it. Change a
beat here and the ladder, the checklist and the blueprint change together — they cannot
drift apart, because there is one copy.

Behaviour lives in the phase modules: context.py · think.py · plan.py · validate.py.
"""

# `close` became the eighth phase by the owner's call (2026-08-21): reflect fixes the
# mistakes and files the lessons, align re-routes what is ahead, and CLOSE sweeps the
# tails — nothing uncommitted, nothing dangling — before the task is written off.
PHASES = ["context", "think", "plan", "execute", "validate", "reflect", "align", "close"]


# How a task can END. §6.7 of the spec lists four Align outcomes, but those are about
# MOVEMENT (carry on, re-route, mutate the destination, project completed). A task itself
# ends in one of these four, and the second one is real: we took `mac-memory` apart to the
# last process and found nothing to free — understanding was the whole result.
OUTCOMES = {
    "completed": "the destination was reached, there is a result",
    "closed":    "closed by understanding — no action turned out to be needed",
    "dropped":   "dropped — turned out to be the wrong task, or no longer needed",
    "blocked":   "stuck on something external; what is missing is written down",
}


PHASE_RU = {"context": "контекст", "think": "думание", "plan": "план", "execute": "исполнение",
            "validate": "проверка", "reflect": "уроки", "align": "сверка", "close": "закрытие"}


OUTCOME_RU = {"completed": "завершена", "closed": "закрыта пониманием",
              "dropped": "снята", "blocked": "заблокирована"}


PHASE_TITLES = {
    "context":  "что у нас есть",
    "think":    "что с этим делать и какие варианты",
    "plan":     "в каком порядке и что от чего зависит",
    "execute":  "делаем",
    "validate": "работает ли на живом",
    "reflect":  "работа над ошибками и уроки",
    "align":    "куда дальше",
    "close":    "хвосты подчищены, результат записан",
}


# HOW TO THINK IN THIS PHASE — the owner's rule, 2026-08-20, said while gathering context for
# journal-share: "во время сбора контекста мы больше думаем как люди, а на этапе думания мы
# больше думаем как инженеры". It is not decoration: on gathering, the winning argument was
# that editing a typo inside one long message on a phone is miserable — a human argument no
# engineering measurement would have produced, and it outweighed a measurement that said
# everything fits in one message.
PHASE_MODE = {
    "context": "думаем КАК ЛЮДИ — как этим живут, что раздражает, что неудобно рукой; "
               "аргумент «неудобно править на телефоне» здесь весит больше замера",
    "think":   "думаем КАК ИНЖЕНЕРЫ — варианты, цена каждого, чем меряем, где ломается",
}


# ── THE NAVIGATOR: the context phase as an explicit ladder ────────────────────
#
# Recovered from elephant-v1, which had EIGHT task states where this CLI had one lump called
# `context` (v1 `backend/src/model/task.py:16`: Context Gathering → Context Gathered → Task
# Formation → IFR → Requirements). A single lump forces the agent to invent the process every
# time, and it invents it badly: one round of shallow questions, five files written silently,
# gate open, the owner having seen nothing. (Owner, 2026-08-19: "сбор контекста прошёл
# где-то underground, непрозрачно для пользователя".)
#
# Each step answers FOUR questions for the agent, and that is what makes this a navigator
# rather than a filing cabinet: where we are · what to gather now · WHO it comes from, the
# owner or the agent itself · whether to stop and show.
#
# `src` is the routing the web app of v1 could not have: it had no eyes, so everything came
# from the human. This CLI's agent can read code, query databases, attach to devices and
# search the web — so asking the owner for something measurable is stealing his time.
#   owner  lives ONLY in his head: intent, priorities, taste, the limits of his world
#   agent  obtainable with an instrument: code, data, logs, devices, docs, web
#   both   start yourself, ask only for the remainder
# THE BOUNDARY IS ASKED, NOT WRITTEN. Restored from elephant-v1 (docs/2_scope_definition.md),
# where scope was six dimensions of a JOURNEY from A to B, each opened by its own question and
# each closing with what is explicitly OUT. The step existed here as a required trace with no
# command behind it, so it got filled with agent prose — and the owner caught exactly that
# (2026-08-20): "я не увидел ни одного вопроса по границам, ведь границы — это тоже вопросы".
SCOPE_DIMS = [
    ("what",  "что именно делаем и что ЯВНО не делаем — какие результаты появятся, "
              "что остаётся нетронутым"),
    ("why",   "зачем едем — какую боль снимаем, что будет, если не делать вовсе"),
    ("who",   "для кого и кто участвует — кто пользуется результатом, кто решает, кого заденет"),
    ("where", "где это живёт — экраны, платформы, среды, что накладывает окружение"),
    # TWO HALVES, and the first is the one that gets missed. Asked as "what do we need now and
    # what waits", it collects a development schedule — useful to nobody. The owner corrected it
    # on the spot (2026-08-20): "правильный ответ на when — это когда нужно отправить программу
    # и когда список песен. Это вопрос, когда фича используется. Потом вопрос, когда я сделаю."
    # The moment the feature FIRES is a fact about his life and shapes the design; the delivery
    # date is usually "when we get to it".
    ("when",  "когда это СРАБАТЫВАЕТ в жизни — в какой момент человек за этим тянется, "
              "что при этом происходит вокруг; и отдельно, вторым: когда нужно иметь готовым"),
    ("how",   "как именно движемся — подход, порядок, что берём из уже готового"),
]


SCOPE_KEYS = [k for k, _d in SCOPE_DIMS]


# ── THE LADDER OF CONTEXT — rebuilt 2026-08-26 ──────────────────────────────────────────
#
# Twenty markdown files became one stream, context.jsonl, and the twenty beats became
# eleven rungs and four through-flows (owner, 2026-08-26). What changed and why:
#   · four beats were never rungs — questions, research, unknown, definitions are written
#     ALL PHASE LONG, whenever the thing happens; a rung that comes nineteenth (unknown did)
#     makes the agent remember at the end what it saw at the start. They are FLOWS now.
#   · five rungs in a row asked one question — under what conditions do we work — and left
#     twelve files empty in the everyday mode. They are one rung, `conditions`, with a kind.
#   · expected-outcomes repeated success-criteria and the ideal; it is a field on a
#     criterion now (`observable`), not a beat.
#   · two rungs were missing: `now` (how it happens TODAY — steps, state, numbers; without
#     it «стало лучше» has nothing to stand against) and `risks` (what may go wrong and what
#     it costs — not the same as not knowing).
#   · the ideal's parts that can be CHECKED (criteria · metrics · checklist) are PROMISES:
#     born here, hung on the root of the tree, `not_validated` from the first day — the
#     registry checks.jsonl, folded upward at validate. The ideal itself stays a paragraph.
#
# Shape kept for every reader: (key, where, title, from whom, description, command).
# `where` is the stream and the step — `context.jsonl#now` — not a file any more.
# The flows that live in the tabs above the bands (owner, 2026-08-27): research · unknown ·
# definitions. Questions are a RUNG — his correction the same night: «вопросы нужно вернуть».
CONTEXT_FLOWS = {"research", "definitions", "unknown"}

CONTEXT_STEPS = [
    # init/request.md is NOT here on purpose (owner, 2026-08-21): it is a trace of STAGE 0,
    # not of context — by the time context starts, the tree exists and the request is
    # recorded. `el next` checks stage 0 separately and nags until it is closed.
    ("questions", "records.jsonl#questions", "уточняющие вопросы — сквозной поток", "owner",
     "ПЕРВЫЙ круг вопросов про ЛЮДЕЙ и жизнь (его правка 2026-08-21): как этим пользуются, "
     "что при этом происходит, где человек находится — опыт и сценарии, НЕ 5W+H (те — "
     "ступень scope). ЦИКЛ: до 5 вопросов за раунд → услышать ответы → записать пары → после "
     "КАЖДОГО раунда сказать «вот как я сейчас понимаю задачу, вот что осталось — продолжать "
     "или достаточно?». Конец опроса решает ЧЕЛОВЕК: его «достаточно» — последняя пара. "
     "Вопрос с вариантами даёт ответ конкретнее открытого — предлагай варианты, они "
     "записываются вместе с парой. Вопросы печатаются В ЧАТ обычным текстом, не формой с "
     "кнопками: он читает глазами и отвечает голосом. Ответы теряют конкретику («не знаю», "
     "«позже») — тоже конец: дальше добираешь сам. Обязательно спроси, КАК ОН ПОЙМЁТ, что "
     "получилось (--area check): из этого вырастают обещания ступени ideal, не из головы "
     "агента. Поток СКВОЗНОЙ: пара пишется на любой ступени, когда прозвучала",
     'el context qa "<вопрос>" "<ответ>" --area <область> [--options "а · б · в"] · новый '
     'раунд: --new-round'),
    ("research", "records.jsonl#research", "исследование — что смотрел и что нашёл", "agent",
     "то, что добывается прибором, не вопросом: код, база, журналы, устройства, документы, "
     "веб. Одна находка — одна запись с ИСТОЧНИКОМ (что смотрел) и ЯКОРЕМ (где перепроверить: "
     "путь:строка, ссылка, страница). Спрашивать у него то, что лежит в коде, — красть его "
     "время; писать без якоря — находка, которую никто не найдёт снова. Поток СКВОЗНОЙ",
     'el research "<тема>" --summary "<выжимка>" --file research/<имя>.md [--area <область>]'),
    ("now", "records.jsonl#now", "как это происходит сейчас — точка отсчёта", "both",
     "ДО границ, потому что границу нельзя провести, не зная, что уже происходит. Три слоя, "
     "каждый — своя запись: ход (что человек делает руками сегодня, шаг за шагом, где "
     "спотыкается) · состояние (что уже построено и в каком оно виде: работает, наполовину, "
     "нет) · числа (сколько сейчас шагов, минут, файлов, ошибок — то, что потом ляжет как "
     "baseline в метрики). Без этой ступени любое «стало лучше» потом не с чем сравнить",
     'el context now "<как сейчас>" --kind flow|state|number [--ref <якорь>]'),
    ("scope", "records.jsonl#scope", "границы 5W+1H: что входит в задачу, что не входит", "both",
     "ВТОРОЙ круг вопросов, про ДЕЛО (его правка 2026-08-21): что делаем · зачем · кто делает "
     "и кто пользуется · когда срабатывает · где · как. Открывается сверкой «вот как я сейчас "
     "понимаю задачу» — и только потом вопросы. ГРАНИЦА — ЭТО ОТВЕТЫ, по одному измерению за "
     "раз, одна строка — одна запись: входит · НЕ входит · размыто. У каждого измерения "
     "обязательно и то, что ЯВНО не входит: невысказанное «не входит» всплывает потом как «а я "
     "думал, это тоже». Измерение отвечено, когда есть хотя бы одно «входит» или «не входит»; "
     "одно «размыто» — честная заметка, не ответ. Все шесть собраны — напечатай сводку в чат и "
     "услышь, что картина его",
     'el context scope — сами вопросы · el context scope <изм> --in "<входит>" --out "<НЕ '
     'входит>" --blur "<размыто>"'),
    ("conditions", "records.jsonl#conditions", "условия — нельзя · не сможем · есть · деньги · инструменты", "both",
     "в каких условиях работаем, одной ступенью вместо пяти: forbidden — чего нельзя, снаружи "
     "(правила, сроки, «это не трогаем») · limit — чего мы или система не сможем (названный "
     "предел не всплывёт на исполнении сюрпризом) · resource — что есть под рукой (люди, "
     "доступы, данные, железо) · money — бюджет и во что обойдётся · tool — чем работаем и "
     "стоит ли оно. «Условий нет» — тоже ответ, и он записывается (--none), а не остаётся "
     "пустым местом",
     'el context condition <forbidden|limit|resource|money|tool> "<что>" [--ref] · el context '
     'condition --none "<почему нет>"'),
    ("requirements", "records.jsonl#requirements", "требования — что рамка обязана вместить", "both",
     "что внутри границы уже построено, чего нет, что неизвестно — одно требование одна запись "
     "с состоянием have · missing · unknown и якорем (файл, путь, число). Требования решают, "
     "ЧТО в задачу входит, а что нет",
     'el context requirement "<что>" --state have|missing|unknown [--ref <якорь>]'),
    ("beyond", "records.jsonl#beyond", "за рамкой — близко к границе, но НЕ делаем", "both",
     "что лежит ВПЛОТНУЮ к границе и сознательно не делается — замыкает рамку (его правка "
     "2026-08-21). Невысказанное «не делаем» всплывает посреди работы как «а я думал, это "
     "тоже». И честная пара: рядом может лежать то, что СТОИТ втянуть, — это его решение ДО "
     "работ, пристройка дешева, пока дом строится (--candidate)",
     'el context beyond "<рядом лежит X — не делаем>" [--candidate --why "<стоит втянуть?>"]'),
    ("ideal", "records.jsonl#ideal + checks.jsonl", "идеальный результат — и обещания, которые он даёт", "owner",
     "ГЛАЗАМИ ПОЛЬЗОВАТЕЛЯ, и всё проверяемое здесь — ОБЕЩАНИЕ: рождается сейчас, вешается на "
     "корень дерева (то, что он проверит сам), стоит not_validated с первого дня, проверяется "
     "по мере готовности, сворачивается вверх на валидации. Три вида обещаний: success — при "
     "каких условиях это успех, его словами, с тем, ЧЕМ это будет видно · metric — число с "
     "порогом, направлением, способом замера и baseline из ступени now · checklist — что он "
     "проверит руками и КАК. У каждого обещания обязательно «чем проверим»: без способа "
     "проверки обещание не записывается — это желание. Сам идеал — ОДНИМ абзацем, "
     "последним: не что построим, а как это выглядит и ощущается у него в руках. Его "
     "слова тут весят больше замера",
     'el context success "<его словами>" --observable "<чем видно>" --how "<чем проверим>" · '
     'el context metric "<имя>" --threshold N --unit <ед> --direction up|down --how "<чем>" '
     '[--baseline N] · el context check "<что проверит руками>" --how "<как>" · el context ifr '
     '"<абзац>"'),
    ("parts", "records.jsonl#parts", "крупные части пути — как ЧЕЛОВЕК видит работу", "owner",
     "не декомпозиция инженера, а его картина: «сначала X, потом Y, потом видно, что дальше». "
     "Каждая часть — запись с тем, какие обещания корня она раскрывает (--covers): по этому "
     "план потом проверяется на целостность — за каждой названной им частью и за каждым "
     "обещанием корня должен стоять узел, иначе часть выпала молча. Пути не видно совсем — "
     "так и пиши: первая часть «собрать информацию», вторая «решить, что дальше»",
     'el context part "<крупный кусок>" [--covers k1,s2] · по одной, в порядке пути'),
    ("definitions", "records.jsonl#definitions", "определения — общий язык проекта", "both",
     "термин, прозвучавший в его речи, ложится сюда с тем, что он значит В ЭТОМ проекте, — в "
     "момент, когда прозвучал, не в конце. Его образ («зеркало», «свёртка») разворачивается в "
     "ясную фразу, а образ остаётся рядом как heard_from. Поток СКВОЗНОЙ",
     'el context define "<термин>" "<что значит здесь>" [--heard "<его слова>"]'),
    ("unknown", "records.jsonl#unknown", "чего я не знаю, но должен бы знать", "agent",
     "явный вопрос перед спуском — всплыл на первом вопросе, пишется на первом вопросе, не "
     "вспоминается в конце. Каждая запись: чего не знаю · как закрываем · держит ли это гейт. "
     "Молчаливое «разберёмся по ходу» не считается. Ушло к владельцу — el owe, и запись "
     "ссылается на долг. Поток СКВОЗНОЙ",
     'el context unknown "<чего не знаю>" [--how "<как закрываем>"] [--blocking]'),
    ("clarified", "records.jsonl#clarified", "задача после уточнений", "agent",
     "отдельное именованное действие, а не «записи собрались»: свернуть всё в ЧЁТКУЮ задачу — "
     "цель, ключевые требования, желаемый результат, ограничения. Запись помнит, над какой "
     "картиной собрана (over_seq): появилось что-то после — видно, что она устарела",
     'el context clarified "<задача одним куском: цель, требования, результат, ограничения>"'),
    ("summary", "records.jsonl#summary", "всё собранное в одном чтении", "agent",
     "всё собранное в одно плотное чтение: что установлено фактом с якорем, что принято "
     "допущением, что осталось неизвестным. Тоже с over_seq",
     'el context summary "<всё собранное в одном плотном чтении>"'),
    ("approval", "records.jsonl#approval", "его слово над картиной, дословно", "owner",
     "ПРЕДЪЯВИ содержимым, а не ссылками: `el context` печатает всё сверху донизу — задача, "
     "границы, условия, обещания, чего не знаем. Потом запиши его ответ ДОСЛОВНО. Слово несёт "
     "номер картины (over_seq): любая запись после него — и слово считается устаревшим, el "
     "forward попросит свежее. Это условие гейта, которое нельзя заменить ничем",
     'el accept "<его слова дословно>"'),
]


CONTEXT_FILES = {k: rel for k, rel, *_ in CONTEXT_STEPS}


# The frame's optional parts (the rest of SCOPE besides 5W+1H and requirements): counted
# and shown when present, never demanded — «ограничений нет» is a fine state of the world.
# ── MODES — the slider of strictness (owner, 2026-08-22) ────────────────────────────────
#
# One protocol, three tightnesses. Every beat carries the mode FROM WHICH it is required:
#   light   a simple task — a few beats required, almost everything «по нужде»
#   soft    the everyday default — the spine required, the finer parts by the task's nature
#   strict  a hard task — every beat required, every stage decomposed before it is worked,
#           every node with its five criteria, and no --waive anywhere
# What no mode loosens: the human's word (context · plan · final acceptance), the graph
# integrity (nodes closed or parked before leaving execute), the ledger's verdicts. The mode
# lives in the task's journal (`el mode <режим>`, derived like the phase) and shows in
# `el status`, `el next` and the page. The map of beats with their thresholds is what
# `el blueprint` prints — with `--mode` to preview another tightness.
MODES = ["light", "soft", "strict"]
MODE_RU = {"light": "лёгкий — мало обязательного, почти всё по нужде",
           "soft": "мягкий — костяк обязателен, тонкие части по природе задачи",
           "strict": "строгий — каждый такт обязателен, обхода нет"}


def required_in(minmode, mode):
    """Is a beat with threshold `minmode` required under `mode`?"""
    return MODES.index(mode) >= MODES.index(minmode)


# From which mode each CONTEXT beat is required. The spine — questions · the clarified task ·
# the owner's word — holds in every mode; the frame's finer parts only in strict.
CONTEXT_MIN = {
    "questions": "light", "research": "soft", "now": "soft", "scope": "soft",
    "conditions": "strict", "requirements": "soft", "beyond": "soft",
    "ideal": "soft", "parts": "soft", "definitions": "strict", "unknown": "soft",
    "clarified": "light", "summary": "soft", "approval": "light",
}
# The optional parts under the everyday (soft) mode — kept under its old name for readers.
CONTEXT_OPTIONAL = {k for k, m in CONTEXT_MIN.items() if m == "strict"}
# THE IDEAL RESULT, in order — what the overview page shows as one group, the ideal LAST.
IFR_PARTS = ["ideal"]


# SCOPE THE FRAME, in order — what the overview page shows as one group. The ORDER is the
# accumulation (owner, 2026-08-21: "порядок помогает накапливать, плавно приходить шаг за
# шагом"): each part stands on the ones before it, and `beyond` closes the frame.
SCOPE_FRAME = ["now", "conditions", "requirements", "beyond"]


# One coverage map for the whole gathering: four sufficiency criteria of v1 plus the six
# dimensions of 5W+H. The owner's rule (2026-08-19): the dimensions are filled FROM the
# answers already given — only the gaps get asked or fetched. So questions carry an area tag
# and the map shows what has never been touched. Counting pairs ("10 asked / 10 answered")
# measured nothing: ten questions about the same corner look identical to ten that covered
# the task.
QA_AREAS = [
    ("goal",    "цель — чего он на самом деле хочет",                "owner"),
    ("must",    "ключевые требования — что обязано быть",            "owner"),
    ("outcome", "желаемый результат — как выглядит успех",           "owner"),
    ("limits",  "ограничения — чего нельзя, чего нет",               "owner"),
    ("what",    "что делаем и что ЯВНО не делаем",                   "both"),
    ("why",     "зачем, какую боль снимаем",                         "owner"),
    ("who",     "для кого, кто исполняет, кто решает",               "owner"),
    ("where",   "платформы, среды, окружение, устройства",           "agent"),
    ("when",    "когда фича СРАБАТЫВАЕТ в жизни; и лишь потом — срок готовности",                                "owner"),
    ("how",     "чем и в каком порядке, какие инструменты",          "agent"),
    # THE ELEVENTH AREA (owner, 2026-08-21): without it the success criteria, the metrics and
    # the acceptance checklist were written by the agent from its own head — the self-«ok»
    # one level up. Asked of the human: how will YOU know it worked, what will you check by hand.
    ("check",   "чем проверим, что получилось — критерии приёмки, метрики, что потрогаешь", "owner"),
]


AREA_KEYS = [a for a, _, _ in QA_AREAS]


# ── THINK: the same navigator, because the same hole was there ────────────────
#
# After the context phase became a ladder with a hard human gate, Think was still what the
# whole of context used to be: two files, a soft gate that opened because they existed, and
# no idea what was inside them. The spec demands "fewer than three options means the field
# was not opened" and "at least one falsification pass" — neither was checkable. And the
# choice BETWEEN options, which is the owner's to make, had no place to live at all: an agent
# could pick a direction on its own and roll into Plan, and nothing would notice.
# (Owner's audit, 2026-08-19: "что у нас с гейтами? что у нас с запросами от пользователей?")
# ── THE LADDER OF THINK — rebuilt 2026-08-27 by the same law as context ─────────────────
#
# Fourteen markdown files became ten rungs and two flows in records.jsonl. What moved:
#   · baseline — a duplicate of the context rung `now`; gone
#   · shoals («что может помешать») — the conditions of context plus the risks; risks are a
#     FLOW now (they surface on any phase), conditions already live in context
#   · ideals — the ideal through the user's eyes is context's; here the ENGINEERING
#     PROMISES: what the solution must hold technically, born as promises in checks.jsonl
#   · decisions — the forks are a flow, their «решено N/N» is the bar
#   · tools — a FIELD on any record (`tool`), the eight categories counted from it
#   · refute → stress: «на прочность» — попробовал сломать выбранный путь, устоял?
# Shape kept for every reader: (key, where, title, from whom, description, command).
THINK_FLOWS = {"forks", "risks"}

# Which of the box's categories are natural for a rung — printed by `el next` beside the
# beat, so the tool meets the agent where it is needed instead of waiting in a drawer.
THINK_RUNG_TOOLS = {
    "mirror": "мышление профессий · зеркало · Iceberg",
    "form": "cross-domain · шесть шляп",
    "core": "Парето · первые принципы · MoSCoW",
    "promises": "ТРИЗ и ИКР · инверсия",
    "reversibility": "эффекты второго порядка · pre-mortem",
    "options": "морфологический ящик · латеральное · матрица решений",
    "stress": "адвокат дьявола · pre-mortem · Popper · steel-man",
    "crystal": "бритва Оккама · синтез · оптика решателя",
    "route": "бутылочное горлышко · точки опоры",
}

THINK_STEPS = [
    ("forks", "records.jsonl#forks", "развилки — где его слово меняет маршрут", "owner",
     "СКВОЗНОЙ поток: вопрос, ответ на который меняет дорогу, а не одну запись. Развилка "
     "открывается, когда ответ живёт только у него; если агент может решить сам — решает и "
     "показывает, а не спрашивает. У каждой развилки: варианты с плюсом и минусом, "
     "рекомендация агента, «почему это твоё решение» и одно уточнение, которое сделало бы "
     "выбор лёгким. Закрывается его словом (событие decision) — или «сам реши» (решение в его "
     "место, помечено). Гейт фазы: все развилки закрыты — не обходится",
     'el think fork "<вопрос>" --option "<имя · плюс · минус>" … --recommend "<какой и почему>" '
     '--why-yours "<что знаешь только ты>" · el think decide <id> "<вариант>" --words "<его слова>"'),
    ("risks", "records.jsonl#risks", "риски — что может пойти не так и чем это стоит", "both",
     "СКВОЗНОЙ поток, как в контексте: что случится · насколько вероятно · чем обойдётся · "
     "что делаем, если случилось. Риск, найденный на думании, помнит фазу",
     'el think risk "<что может случиться>" --chance low|mid|high --cost "<чем>" --then "<что делаем>"'),
    ("mirror", "records.jsonl#mirror", "кто будет этим пользоваться и кого это заденет", "both",
     "запись на человека или роль: кто · что делает с результатом · чем его заденет. Не "
     "«пользователи», а конкретные люди в конкретный момент; кого заденет — отдельно от кого "
     "обслужит",
     'el think mirror "<кто>" --does "<что делает>" --affected "<чем заденет>"'),
    ("form", "records.jsonl#form", "в каком виде человек получит результат", "both",
     "форма результата в его руках: экран, файл, команда, письмо. Вариантов несколько — "
     "каждый записью, это ветки; выбор — развилка",
     'el think form "<в каком виде>"'),
    ("core", "records.jsonl#core", "что здесь главное, что потом, чего не делаем", "agent",
     "каждая часть с меткой: core — без этого результата нет · later — можно после · never — "
     "сознательно не делаем. Полоса не нужна: считается, сколько core",
     'el think core "<часть>" --rank core|later|never'),
    ("promises", "records.jsonl#promises + checks.jsonl", "инженерные обещания — что решение обязано держать", "both",
     "не второй идеал (он в контексте), а ТЕХНИЧЕСКИЕ обещания: что решение обязано держать, "
     "чем проверим и при чём сломается (--breaks-if). Ложатся в реестр обещаний на корень "
     "с born: think; на плане критерии узлов будут их раскрывать. Без «чем проверим» не "
     "записывается",
     'el think promise "<что держит>" --how "<чем проверим>" [--breaks-if "<при чём сломается>"]'),
    ("reversibility", "records.jsonl#reversibility", "что нельзя будет отменить, если сделаем", "both",
     "необратимое — по одному: что именно нельзя откатить · чем защищаем (снимок, пробный "
     "прогон, его разрешение). Каждая запись станет остановкой РАЗРЕШЕНИЕ в плане",
     'el think irreversible "<что нельзя отменить>" --guard "<чем защищаем>"'),
    ("options", "records.jsonl#options", "какие есть пути и что каждый делает с обещаниями", "agent",
     "путь — ветка: имя · суть · за · против · и ОЦЕНКА по каждому обещанию из реестра "
     "(--score m1=«6 → 0» --score k1=да). Полоса — клетки «пути × обещания»: это и есть "
     "замер в думании. Меньше двух путей — не выбор; подпуть — --parent",
     'el think option "<имя>" --text "<суть>" --score <id>=<оценка> … [--pros] [--cons] [--parent <id>]'),
    ("stress", "records.jsonl#stress", "на прочность — попробовал сломать выбранный путь, устоял?", "agent",
     "атака на обещание через выбранный путь: как ломал · устояло или нет · почему. Путь, "
     "который не пробовали сломать, — пустой, пока не проверен (его закон твёрдого и "
     "пустого). Не устояло — путь правится или отсекается, это видно",
     'el think stress "<как ломал>" --path <id> --promise <id> --held yes|no --why "<…>"'),
    ("crystal", "records.jsonl#crystal", "какая тропа выжила и почему", "both",
     "записи по мере вызревания; последняя — решение: выжившая тропа со ссылками на "
     "развилки, на которые опирается. Отсечённые пути не стираются — остаются с «почему»",
     'el think crystal "<как вызревает / решение>" [--path <id>] [--decided f1,f2]'),
    ("route", "records.jsonl#route", "что первым, что потом, что от чего зависит", "both",
     "кандидаты в этапы с зависимостями — план их подхватит и нарежет; здесь порядок, не "
     "декомпозиция. Первый содержит подготовку, последний — итоговую проверку",
     'el think route "<этап>" [--after <id>,<id>]'),
    ("approval", "records.jsonl#approval", "его слово над решением, дословно", "owner",
     "ПРЕДЪЯВИ решение содержимым: тропа, что она держит, чем платит, что отсечено и почему. "
     "Запиши ответ ДОСЛОВНО; слово несёт номер картины — запись после него его устаревает",
     'el accept "<его слова дословно>"'),
]


THINK_FILES = {k: rel for k, rel, *_ in THINK_STEPS}
# From which mode each THINK beat is required: the forks and the crystal hold in every
# mode, the ladder in soft, the heavy instruments in strict.
THINK_MIN = {
    "forks": "light", "risks": "strict", "mirror": "soft", "form": "soft", "core": "light",
    "promises": "soft", "reversibility": "strict", "options": "light", "stress": "soft",
    "crystal": "light", "route": "soft", "approval": "light",
}
# The categories of the box — the coverage bar of думание (owner, 2026-08-27: «по
# категориям это уже лучше: взял разведку и точность, не взял риски»). soft asks for the
# three that catch most; strict for all eight.
THINK_CATS = ["диагностика", "расширение", "углубление", "рычаг", "селекция", "кристалл",
              "опровержение", "сквозные"]
THINK_CATS_MIN = {"light": [], "soft": ["диагностика", "расширение", "опровержение"], "strict": list(THINK_CATS)}


# The open box. Printed by `el think tools` so an agent picks under the task instead of using
# its one favourite on everything — the anti-pattern the spec names explicitly (§6.2).
THINK_TOOLS = [
    ("диагностика", "Cynefin (какой природы задача) · Iceberg (события → паттерны → структуры "
                    "→ модели мира) · геологоразведка"),
    ("расширение",  "brainstorming · латеральное · cross-domain (как это решают в другой "
                    "области) · шесть шляп · морфологический ящик"),
    ("углубление",  "пять «почему» · первые принципы · Ishikawa · инверсия (как гарантированно "
                    "провалить)"),
    ("рычаг",       "бутылочное горлышко и теория ограничений · точки опоры · Парето"),
    ("селекция",    "иерархия критичности · MoSCoW · матрица решений · MECE"),
    ("кристалл",    "оптика решателя (карта · скальпель · компас · зеркало) · ТРИЗ и ИКР · "
                    "синтез · бритва Оккама"),
    ("опровержение","pre-mortem (представь, что провалились — почему?) · адвокат дьявола · "
                    "steel-man · Popper · эффекты второго порядка"),
    ("сквозные",    "OODA · Theory U · байесовское обновление · мышление профессий"),
]


# THE BOX, TOOL BY TOOL (owner, 2026-08-27: «внутри должен быть список tool и что он делает —
# как каталог ключей: ключ на 13 под одну гайку, разводной под разные»). Four fields per tool:
# what it is (one line) · about (the substance: origin, mechanism, why it works — owner
# 2026-08-27: «не вода, а суть») · when to take it · how it goes · what it gives. THINK_TOOLS above stays the one-line
# index (its tokens are what `--tool` is matched against); this is what the page opens on a click
# and what `el think tools <категория>` prints in full.
THINK_TOOLBOX = {
    "диагностика": {
        "for": "какой природы задача и где мы стоим — прежде чем выбирать метод",
        "tools": [
            {"name": "Cynefin", "what": "рамка «какой природы задача»: ясная · сложная · комплексная · хаотичная", "about": "Рамка Дэйва Сноудена: сначала понять, с задачей какого рода имеешь дело, и только потом выбирать метод. Четыре домена: ясный — связь причины и следствия очевидна, есть лучшая практика; сложный — связь есть, но её видит эксперт после анализа; комплексный — связь видна только задним числом, система отвечает на вмешательство непредсказуемо, единственный путь — безопасные пробы; хаотичный — связи нет, сначала стабилизируй. Ошибка, которую рамка ловит: анализ и план там, где задача комплексная, — план устаревает раньше, чем дописан.", "when": "перед выбором метода — когда непонятно, считать ли ответ или нащупывать его пробами", "how": "спроси, есть ли известный правильный ответ → если причина видна только задним числом, задача комплексная: пробуй → смотри → усиливай", "gives": "класс задачи и режим работы под него: лучшая практика · анализ экспертов · безопасные пробы · сначала стабилизировать"},
            {"name": "Iceberg", "what": "четыре слоя за событием: события → паттерны → структуры → модели мира", "about": "Модель системного мышления: видимое событие — верхушка айсберга, под водой три слоя, каждый порождает верхний. Паттерны — то, что повторяется во времени; структуры — правила, процессы, стимулы и связи, из-за которых паттерн повторяется; модели мира — убеждения, из-за которых такие структуры считаются нормальными. Рычаг растёт с глубиной: реакция на событие гасит один случай, правка структуры убирает класс случаев.", "when": "одно и то же ломается снова, а починка держится неделю", "how": "от события спустись: что повторяется? → какая структура (правило, стимул, процесс) это порождает? → какая картина мира её оправдывает?", "gives": "точку правки на уровне структуры, а не симптома — одна правка вместо серии"},
            {"name": "геологоразведка", "what": "пробные шурфы по площади до раскопок: быстрые замеры в разных местах", "about": "Метафора из разведки месторождений: прежде чем рыть шахту, бурят сетку неглубоких скважин по всей площади и по керну решают, где жила. В незнакомой системе это серия коротких замеров в разных местах — неглубоких, но покрывающих площадь; каждая скважина — один факт с якорем. Защищает от двух ошибок: закопаться в первое интересное место и читать всё подряд.", "when": "большая незнакомая система, читать всё некогда", "how": "выбери 5–7 точек (логи · тесты · живой прогон · код на стыках) → в каждой короткий замер → запиши, где «звенит»", "gives": "карту, где копать глубже — и где не копать вовсе"},
        ],
    },
    "расширение": {
        "for": "больше вариантов, чем пришло в голову первым",
        "tools": [
            {"name": "brainstorming", "what": "генерация без оценки: сначала количество, критика — отдельным проходом", "about": "Генерация идей по правилам Осборна: количество прежде качества, критика отложена, дикие идеи приветствуются, чужие достраиваются. Работает потому, что генерация и оценка — разные режимы мышления, и включённая одновременно оценка душит поток на второй идее. Результат сырой по замыслу: ценность в том, что среди двадцати вариантов окажутся два-три, до которых обычным ходом мысли не дошли бы.", "when": "нужны идеи, а первые две — очевидные", "how": "10 минут → ничего не отбрасывать → достраивать чужое → оценка потом", "gives": "15–30 сырых вариантов, из которых 2–3 стоят проверки"},
            {"name": "латеральное", "what": "намеренный сдвиг рамки: случайный стимул, провокация «а если наоборот»", "about": "Термин Эдварда де Боно: движение «вбок» от привычной колеи рассуждения вместо движения «вглубь». Инструменты — случайный стимул (слово наугад, связанное с задачей), провокация «по» (намеренно абсурдное утверждение, из которого выводится рабочая идея), переворот (сделать наоборот). Работает потому, что мозг сам достраивает связь между любыми двумя вещами — и эта связь лежит за пределами исходной рамки.", "when": "все варианты — вариации одного и того же", "how": "возьми случайное слово или объект → свяжи с задачей → из провокации выведи рабочую идею", "gives": "1–2 варианта из другого класса решений"},
            {"name": "cross-domain", "what": "как эту же задачу давно решают в другой области — медицина, авиация, логистика", "about": "Перенос решения из области, где задача той же структуры решается давно и хорошо. Ключ — сформулировать свою задачу без слов своей области («очередь с приоритетами и потерями» вместо «тикеты поддержки») и спросить, кто с этим живёт десятилетиями: авиадиспетчеры, триаж в медицине, логистика. Переносится механика вместе с её ограничениями, а не внешняя форма.", "when": "в своей области решение «известно» и посредственно", "how": "назови задачу абстрактно («очередь с приоритетами и потерей») → найди область, где это решено → перенеси механику", "gives": "готовую схему, проверенную чужим опытом"},
            {"name": "шесть шляп", "what": "шесть режимов по очереди: факты · чувства · риски · выгоды · идеи · процесс", "about": "Метод де Боно: обсуждение разводится по шести режимам, и в каждый момент все думают в одном. Белая — факты и цифры; красная — чувства и интуиция без обоснований; чёрная — риски и что не сработает; жёлтая — выгоды; зелёная — новые идеи; синяя — управление самим процессом. Спор «оптимист против пессимиста» превращается в последовательный обход: каждый режим получает своё время, и никто не защищает позицию.", "when": "обсуждение ходит по кругу — спорят с разных позиций одновременно", "how": "пройди все шесть по одному → в каждом режиме свои 3–5 строк", "gives": "полный обзор без спора: что знаем, чего боимся, что выиграем"},
            {"name": "морфологический ящик", "what": "таблица параметров × значений; решение — по одной клетке из каждой строки", "about": "Метод Цвикки: задача раскладывается на независимые параметры, у каждого перечисляются возможные значения, пространство решений — все комбинации; решение = одна клетка из каждой строки. Систематичность здесь важнее вдохновения: перебор показывает сочетания, которые интуиция не собрала бы, и делает видимым, какие клетки пусты или невозможны.", "when": "решение состоит из независимых выборов: хранение × интерфейс × формат", "how": "выпиши параметры → для каждого 3–5 значений → перебери комбинации → отсей невозможные", "gives": "систематический перечень вариантов, включая неочевидные комбинации"},
        ],
    },
    "углубление": {
        "for": "докопаться до причины и до основания",
        "tools": [
            {"name": "пять «почему»", "what": "цепочка «почему?» от симптома к корню", "about": "Приём Тайити Оно из производственной системы Toyota: от симптома задавать «почему?» примерно пять раз подряд, пока не дойдёшь до причины, устранение которой убирает симптом насовсем. Правило остановки — ответ стал процессом, правилом или отсутствующей проверкой, а не именем человека: «Вася забыл» — не корень, корень — «нет шага, который не даёт забыть». Цепочка ветвится; честная цепочка записывается.", "when": "баг починили, а он вернулся; известен симптом, не причина", "how": "к каждому ответу снова «почему?» → пока ответ не станет процессом или правилом, а не человеком", "gives": "корневую причину и место, где её убрать"},
            {"name": "первые принципы", "what": "разобрать до того, что верно наверняка, и собрать заново без унаследованных допущений", "about": "Рассуждение от того, что известно наверняка — физика, факты, ограничения, — а не от аналогий и «так делают все». Разобрать задачу до базовых истин, отбросить всё, что оказалось привычкой или чужим допущением, собрать заново. Дорого по времени, поэтому применяется там, где унаследованная схема стоит слишком много, — и часто даёт решение в разы проще существующего.", "when": "«так принято», но никто не помнит, почему", "how": "выпиши допущения → каждое: факт или привычка? → из фактов собери решение с нуля", "gives": "решение без лишних частей — часто в разы проще"},
            {"name": "Ishikawa", "what": "«рыбья кость»: причины по категориям — люди · процесс · инструмент · среда · данные", "about": "Диаграмма причин и следствия Каору Исикавы: следствие — «голова рыбы», крупные категории причин — «кости» (люди · процесс · инструменты · среда · данные · измерение), на каждой — конкретные кандидаты. Это карта гипотез, а не ответ: ценность в полноте — все области просмотрены, ничего не забыто — и в том, что группа видит одно и то же.", "when": "причин много, они переплетены, нужен полный перечень", "how": "нарисуй кости → на каждую — кандидатов → отметь проверяемые", "gives": "полный список гипотез-причин, разложенный по областям"},
            {"name": "инверсия", "what": "«как гарантированно провалить?» — и не делать этого", "about": "Приём из математики и инвестирования (Якоби, Мангер): вместо «как достичь X» спросить «как гарантированно не достичь X» — и не делать этого. Провал представить в деталях легче, чем успех: список способов провалить выходит конкретнее списка условий успеха, и каждый пункт переворачивается в правило или проверку.", "when": "непонятно, что важно; список рисков пуст", "how": "перечисли 10 способов провалить → переверни каждый в правило", "gives": "защитные правила и список того, чего нельзя"},
        ],
    },
    "рычаг": {
        "for": "где малое усилие даёт большой сдвиг",
        "tools": [
            {"name": "бутылочное горлышко", "what": "теория ограничений: система не быстрее самого узкого места, остальное — подчинить ему", "about": "Теория ограничений Голдратта: в любой системе есть одно ограничение, задающее пропускную способность целого; улучшать остальное бессмысленно, пока оно не расшито. Пять шагов: найти ограничение → выжать из него максимум → подчинить ему остальное → расширить → вернуться к первому шагу, потому что ограничение переместилось. Признак: перед ним копится очередь, за ним — простой.", "when": "ускорили часть, а общий результат не сдвинулся", "how": "найди ограничение (где копится очередь) → выжми его → подчини остальное → расширь → повтори", "gives": "одну точку, работа над которой действительно двигает результат"},
            {"name": "точки опоры", "what": "место, где одно изменение меняет поведение всей системы: правило, стимул, интерфейс", "about": "Из работы Донеллы Медоуз о местах вмешательства в систему: параметры (числа, лимиты) — слабые рычаги; потоки и буферы — сильнее; правила и структура обратных связей — ещё сильнее; цель системы и парадигма, из которой она растёт, — самые сильные. Парадокс: чаще всего крутят параметры, потому что они на виду, а поведение системы меняют правила.", "when": "правок много, эффекта мало", "how": "иди по слоям вверх: параметр → поток → правило → цель; чем выше — тем сильнее рычаг", "gives": "список точек по силе рычага"},
            {"name": "Парето", "what": "20 % причин дают 80 % эффекта", "about": "Наблюдение Вильфредо Парето, обобщённое Джураном как «правило немногого важного»: в большинстве систем малая доля причин даёт большую долю эффекта — 20/80 как ориентир, не закон. Чтобы применить, нужен замер вклада каждой причины (частота, стоимость, время) и сортировка; без замера «Парето» превращается в оправдание любого выбора.", "when": "длинный список проблем, ресурс — на две", "how": "замерь вклад каждой (частота · стоимость) → отсортируй → возьми верх", "gives": "короткий список, покрывающий большую часть боли"},
        ],
    },
    "селекция": {
        "for": "выбрать из вариантов — не по вкусу",
        "tools": [
            {"name": "иерархия критичности", "what": "сначала то, без чего всё остальное бессмысленно", "about": "Упорядочивание по вопросу «если этого не будет — что рухнет?»: сначала то, без чего остальное теряет смысл, потом то, что снимает самые большие риски, потом остальное. В отличие от важности «по ощущению» это критерий отказа: пункт критичен, если его отсутствие обесценивает результат. Даёт порядок, в котором каждый шаг стоит на предыдущих.", "when": "список задач без порядка", "how": "для каждого: «если этого нет — что рушится?» → сортируй по размеру обвала", "gives": "порядок, где первые пункты снимают самые большие риски"},
            {"name": "MoSCoW", "what": "must · should · could · won't", "about": "Метод приоритизации из DSDM: каждый пункт получает одну из четырёх меток — Must (без этого выпуска нет), Should (важно, но выпуск возможен), Could (если хватит сил), Won't (осознанно не в этот раз). Сила в последней букве: явно записанное «не делаем» — договорённость, а не забытый пункт, и к нему можно вернуться.", "when": "объём больше срока — надо резать", "how": "каждый пункт — одна из четырёх букв → «won't» пишется явно", "gives": "границу выпуска и записанный список того, чего не делаем"},
            {"name": "матрица решений", "what": "варианты × критерии с весами", "about": "Взвешенная оценка (Пью, Кепнер—Трего): варианты по строкам, критерии по столбцам с весами; оценки умножаются на веса и суммируются. Главное правило — веса и критерии назначаются ДО того, как оценены варианты, иначе матрица подгоняется под любимый ответ. Результат — не истина, а прозрачный след: видно, почему выбран этот и что изменилось бы при других весах.", "when": "3+ варианта, несколько критериев, спор", "how": "выпиши критерии → дай веса ДО оценки → оцени каждый вариант → посчитай", "gives": "обоснованный выбор и след, почему не другие"},
            {"name": "MECE", "what": "без пересечений и без дыр", "about": "Принцип структурирования из McKinsey: части разбивки взаимно исключают друг друга (ничего не считается дважды) и вместе исчерпывают целое (ничего не теряется). Проверка на пересечение — «может ли одно и то же попасть в две категории?», на полноту — «есть ли что-то, что не попало никуда?». Без этого счёт и деление работы дают двойной учёт или дыры.", "when": "в разбивке что-то считается дважды или теряется", "how": "проверь пары на пересечение → проверь, что «прочее» не пухнет", "gives": "чистую разбивку, по которой можно считать и делить работу"},
        ],
    },
    "кристалл": {
        "for": "сжать материал в одно решение",
        "tools": [
            {"name": "оптика решателя", "what": "четыре взгляда: карта (что есть) · скальпель (что отрезать) · компас (куда) · зеркало (что во мне мешает)", "about": "Четыре взгляда на один материал, каждый со своим вопросом: карта — что есть и как связано; скальпель — что лишнее и что отрезать; компас — куда двигаться и по какому признаку узнаем, что пришли; зеркало — что в самом решателе мешает видеть (привычка, страх, любимый метод). Решение там, где сходятся все четыре; несогласие взглядов показывает, чего не хватает.", "when": "материала много, решения нет", "how": "по каждому взгляду 3–5 строк → где взгляды сходятся, там решение", "gives": "сжатое решение и ясность, что отброшено и почему"},
            {"name": "ТРИЗ и ИКР", "what": "идеальный конечный результат: функция выполняется, а системы нет; противоречие разрешается, а не сглаживается", "about": "Теория решения изобретательских задач Альтшуллера: сильное решение убирает противоречие, а не ищет компромисс между его сторонами. Идеальный конечный результат — «функция выполняется, а системы, которая её выполняет, нет» — задаёт направление; формулировка противоречия («нужно X и нужно не-X») открывает приёмы разрешения: разделить во времени, в пространстве, по условию, между системой и подсистемой.", "when": "любой вариант жертвует чем-то важным", "how": "сформулируй ИКР → найди противоречие (нужно X и не-X) → раздели во времени или в пространстве", "gives": "решение без компромисса — или ясное знание, что компромисс неизбежен"},
            {"name": "синтез", "what": "собрать из нескольких вариантов один, взяв сильное из каждого", "about": "Сборка одного решения из нескольких кандидатов: у каждого выписывается, что именно он даёт и за счёт чего, проверяется совместимость механик, собирается путь, где сильные части не мешают друг другу. Отличается от компромисса: не «каждому по половине», а «от каждого то, в чём он лучший». Работает, когда варианты сильны в разных местах.", "when": "два хороших пути, оба неполные", "how": "выпиши, что даёт каждый → проверь совместимость → собери", "gives": "один путь, лучше любого из исходных"},
            {"name": "бритва Оккама", "what": "из равных объяснений — самое простое", "about": "Принцип экономии объяснений: из теорий, одинаково согласующихся с фактами, предпочитать ту, что требует меньше допущений. Это не «простое всегда верно», а порядок проверки: простое проверяется первым, потому что дешевле и опровергается быстрее. Условие применения — обе теории действительно объясняют все факты.", "when": "две теории объясняют одни и те же факты", "how": "посчитай допущения у каждой → выбери с меньшим → проверь, что объяснены все факты", "gives": "рабочую гипотезу с минимумом допущений"},
        ],
    },
    "опровержение": {
        "for": "попробовать сломать, прежде чем строить",
        "tools": [
            {"name": "pre-mortem", "what": "«прошёл год, проект провалился — почему?»", "about": "Приём Гэри Клейна: до старта представить, что проект прошёл и провалился, и каждому написать, почему. Работает лучше вопроса «какие риски вы видите?», потому что снимает оптимизм и социальное давление: провал уже случился, ищем причины, а не спорим, случится ли. Причины группируются; на самые частые и тяжёлые меры готовятся до начала.", "when": "перед стартом, пока план ещё дёшево менять", "how": "каждый пишет причины провала → сгруппировать → на топ-3 меры", "gives": "список рисков, которых оптимизм не видел, с готовыми ответами"},
            {"name": "адвокат дьявола", "what": "кто-то обязан спорить с решением", "about": "Из практики канонизации в католической церкви — человек, обязанный найти аргументы против кандидата. В решениях это назначенная роль: спорить с выбранным путём, даже если сам с ним согласен. Роль снимает страх «быть против команды» и вытаскивает возражения, которые все видели, но никто не озвучил.", "when": "все согласились слишком быстро", "how": "назначь роль → 10 минут аргументов против → ответить на каждый", "gives": "слабые места решения до того, как их найдёт жизнь"},
            {"name": "steel-man", "what": "самая сильная версия чужой позиции — прежде чем возражать", "about": "Противоположность соломенному чучелу: прежде чем возражать, сформулировать чужую позицию в самом сильном виде — так, чтобы её носитель сказал «да, именно это». Только после этого спорить. Дисциплинирует спор и часто показывает, что в чужой позиции есть часть, которую стоит взять.", "when": "спор с позицией, которая кажется глупой", "how": "сформулируй её так, чтобы оппонент сказал «да, именно» → только потом спорь", "gives": "честное сравнение — и часто часть правоты другой стороны"},
            {"name": "Popper", "what": "гипотеза хороша, если ясно, что её опровергнет", "about": "Критерий фальсифицируемости Карла Поппера: утверждение содержательно, если его можно опровергнуть наблюдением; если никакой исход не может его опровергнуть, оно ничего не утверждает. В работе: гипотеза до проверки называет исход, при котором она ложна, и замер планируется именно на него. Гипотеза, которую подтверждает любой результат, — не гипотеза.", "when": "перед проверкой — гипотезу нельзя опровергнуть ничем", "how": "назови исход, при котором гипотеза ложна → спланируй именно этот замер", "gives": "проверяемую гипотезу и критерий отката, назначенный заранее"},
            {"name": "эффекты второго порядка", "what": "«а что потом?» — последствия последствий", "about": "Последствия последствий: решение вызывает эффект, эффект вызывает реакцию системы и людей, и она часто съедает выигрыш или меняет его знак. Для каждого ожидаемого эффекта спросить «и что тогда произойдёт?» два-три раза, особенно про реакцию тех, кого решение задевает. Классика: субсидия, которая поднимает цену на то, что субсидирует.", "when": "решение выглядит выигрышным сразу", "how": "для каждого эффекта спроси «и что это вызовет?» два-три раза → отметь нежелательное", "gives": "скрытые издержки и побочки до внедрения"},
        ],
    },
    "сквозные": {
        "for": "ритм и рамка на всю работу",
        "tools": [
            {"name": "OODA", "what": "наблюдай · ориентируйся · решай · действуй — кругами", "about": "Цикл Джона Бойда из воздушного боя: наблюдай — ориентируйся — решай — действуй, и снова. Побеждает не тот, кто быстрее действует, а тот, кто быстрее замыкает круг и чаще пересматривает картину; «ориентация» — главный такт, там переоценивается модель ситуации. В работе это короткие итерации с замером в начале каждой.", "when": "обстановка меняется быстрее плана", "how": "короткие циклы: замер → пересмотр картины → решение → действие → снова замер", "gives": "скорость реакции; план перестаёт устаревать"},
            {"name": "Theory U", "what": "спуск и подъём: отпустить старую картину → увидеть → дать проявиться → прототип → внедрить", "about": "Модель Отто Шармера: чтобы прийти к новому, а не повторить прошлое, нужно спуститься по левой стороне U — слушать без фильтров, увидеть систему целиком, отпустить привычную рамку, — пройти нижнюю точку, где новое проявляется, и подняться по правой: кристаллизовать, быстро прототипировать, внедрить. Цена — время на спуск; выигрыш — решение, не выведенное из старого опыта.", "when": "нужна не оптимизация, а новый подход", "how": "слушай без фильтра → отпусти привычную рамку → дай новому проявиться → быстро прототипируй", "gives": "решение из будущего, а не из прошлого опыта"},
            {"name": "байесовское обновление", "what": "вера в гипотезу пересчитывается с каждым свидетельством", "about": "Правило Байеса как способ думать: у каждой гипотезы есть текущая степень уверенности, и каждое свидетельство сдвигает её пропорционально тому, насколько оно правдоподобнее при гипотезе, чем без неё. Записанная уверенность до и после защищает от двух ошибок: решить «навсегда» по первому факту и не заметить, что накопленные факты уже опровергли исходное мнение.", "when": "свидетельства приходят по частям, а хочется решить «раз и навсегда»", "how": "назначь исходную вероятность → каждое наблюдение сдвигает её в меру своей силы → записывай", "gives": "честную текущую уверенность и момент, когда её достаточно"},
            {"name": "мышление профессий", "what": "посмотреть глазами другой профессии: хирург, пилот, следователь, бухгалтер", "about": "Взгляд на задачу через оптику другой дисциплины: хирург спросит, что нельзя трогать и как откатить; пилот — какой чек-лист перед стартом; следователь — что не сходится в показаниях; бухгалтер — где сходятся балансы. Каждая профессия десятилетиями оттачивала свои вопросы, и они применимы за её пределами.", "when": "своя оптика замылилась", "how": "выбери 2–3 профессии → спроси: что первым проверил бы он?", "gives": "неожиданные проверки и приоритеты"},
        ],
    },
}


# ── PLAN: the fractal, and the eight fields that make a node a contract ───────
#
# The owner's shape (2026-08-19): "это этапы, work packages, работа, задачи — фрактальная
# часть, просто объём работы уменьшается внутри. И там на каждую задачу должны быть какие-то
# условия: requirements, в конце валидация, и оставляемый артефакт."
#
# Recovered from elephant-v1, where every level carried the SAME field set (`model/work.py`,
# `model/executable_task.py`): name · description · sequence_order · dependencies ·
# required_inputs · expected_outcome · generated_artifacts · validation_criteria. That
# sameness is what makes it fractal — one contract, four sizes.
PLAN_LEVELS = ["stage", "work", "task", "subtask"]


# Field, heading, what makes it filled. A field may be "N/A — because…", never silently empty:
# an empty field is indistinguishable from a forgotten one, and that is what the eight exist
# to prevent (ELEPHANT.md §7).
NODE_FIELDS = [
    ("result",    "результат — наблюдаемое СОСТОЯНИЕ",
     "не «сделал то-то», а что СТАНЕТ ПРАВДОЙ, когда узел закрыт. Затраченные усилия "
     "результатом не являются"),
    ("check",     "критерии проверки",
     "минимум пять, каждый измерим БЕЗ интерпретации: запустил — видно да или нет. "
     "«Работает хорошо» не критерий"),
    ("resources", "ресурсы",
     "люди · техника · деньги · время. Чего нет — так и пиши, это и есть находка"),
    ("artifacts", "артефакты, которые узел производит",
     "что останется на диске или в мире после закрытия узла"),
    ("storage",   "где артефакт лежит",
     "конкретный путь, а не «где-то». Проверка: найдём ли мы это через год"),
    ("inputs",    "входы от родителя и соседей",
     "что должно быть готово ДО начала. Пустой вход у не-первого узла — почти всегда пропуск"),
    ("deps",      "зависимости и порядок",
     "какие узлы должны закрыться раньше. Циклов быть не должно"),
    # THE NINTH FIELD — the owner's vector (2026-08-19): "нужно показывать точки синхронизации
    # с пользователем… и обязательно в этих точках останавливаться и синхронизироваться, или
    # показывать свою работу, чтобы пользователь увидел что получилось… это нужно для
    # синхронизации пути, как в навигаторе, потому что и цель может измениться".
    # Planned in advance, not improvised: a stop decided in the moment is decided by whoever
    # is tired, and the one place it is really needed gets skipped.
    ("sync",      "остановка: что покажу, что увидишь, что потрогаешь",
     "ЧЕТЫРЕ строки, и каждая обязательна — иначе остановка превращается в «ну как?», "
     "на что ответить нечем.\n"
     "  показываю: <предмет — сообщение · экран · число · файл · собранное приложение>\n"
     "  увидишь: <на что конкретно смотреть в этом предмете, а не «результат работы»>\n"
     "  потрогать: <ЧЕМ он может поработать САМ — приложение стоит на эмуляторе и можно "
     "тыкать · файл, который открывается · ссылка · команда, которую он запустит. "
     "Нечего трогать — так и напиши «только смотреть», это честный ответ, но проверь: "
     "почти всегда потрогать можно, если не полениться поставить>\n"
     "  от тебя: <НИЧЕГО, иду дальше · ПОПРАВКА, если что-то не так · РЕШЕНИЕ, без него "
     "не двигаюсь>\n"
     "⚠️ Род остановки — ПОКАЗ · РАЗВИЛКА · РАЗРЕШЕНИЕ — определяется последней строкой, а "
     "не важностью узла. «Ничего» → показ. «Решение» → развилка или разрешение"),
    # THE TENTH FIELD — WHAT THIS NODE COVERS (his decision 2026-08-24, «целостность
    # маршрута»). The roll-up of the check answers «сдержали ли мы то, что обещали»; it
    # cannot answer «а всё ли нужное мы вообще обещали», because what nobody wrote down
    # cannot be checked. So the plan carries the link back to the goal: which items of the
    # acceptance checklist and which of his big pieces this node closes. Read TOP-DOWN it
    # gives integrity — an item covered by nobody is work we are simply not going to do.
    # OPTIONAL by design: a scaffolding node («поднять стенд») serves other nodes, not the
    # goal directly, and forcing a link would breed fake ones. The demand runs the other
    # way — every GOAL item must be covered by someone (el plan integrity).
    ("covers",    "что покрывает из цели",
     "ради чего этот кусок работы: пункты чек-листа приёмки и крупные части пути, которые он "
     "закрывает — `el plan cover s1 ifr 2 3` · `el plan cover s1 part 1`. Узел-подпорка "
     "(«поднять стенд») может не покрывать цель напрямую — тогда пусто, это честно"),
    ("executor",  "кто исполняет",
     "AGENT (ИИ делает сам) · HUMAN (только человек: решение, подпись, физическое действие, "
     "приёмка) · ROBOT или внешняя система. Названо поимённо, а не «команда». Различать HUMAN-"
     "исполнение и HUMAN-решение: первое можно передать, второе нельзя"),
]


NODE_KEYS = [k for k, _h, _d in NODE_FIELDS]
# `covers` is never owed as a "field to fill": integrity is demanded from the GOAL side, not
# from every node (a scaffolding node covers nothing and that is honest). Kept out of the
# gaps check so adding the field does not turn every existing node into an unfinished one.
NODE_KEYS_OPTIONAL = {"covers"}


# THE MAP OF PHASES — what gets filled in, where it lands, what proves the move on.
#
# This is written for an AGENT, not for a human reader (owner, 2026-08-18): every output
# carries not only WHAT is now, but HOW things are done here and WHICH command to look at.
# That is what keeps an agent inside the protocol — including this same agent tomorrow,
# after it has forgotten half of today.
PHASE_MAP = {
    # The owner's map, 2026-08-18: gathering, scope (5W+H), the ideal final result and
    # requirements are ALL beats of CONTEXT. Thinking comes after them; the network plan and
    # the decomposition belong to PLAN. Before this, scope and IFR floated between phases and
    # requirements did not exist at all — which is exactly why 5W+H was never asked.
    "context": {
        # Generated from CONTEXT_STEPS so the ladder and the checklist can never drift apart:
        # one of them going stale while the other looks right is exactly how the phase started
        # passing with nothing shown to anyone.
        # The frame's finer parts are optional beats: not every task has its own vocabulary,
        # named limits or a tool list — but the ones that exist are counted and shown.
        "artifacts": [(rel, title, CONTEXT_MIN.get(_k, "soft"))
                      for _k, rel, title, *_r in CONTEXT_STEPS],
        "how": ("A LADDER of eleven rungs and four FLOWS, one stream (context.jsonl) — beat by "
                "beat, one record per line, nothing edited, retractions by `amend`. FLOWS run "
                "all phase long: questions (a loop; the HUMAN ends it with his «достаточно»), "
                "research (what was looked at, with anchors), unknown (written when it surfaced), "
                "definitions (a term the moment it sounded). RUNGS in order, each standing on the "
                "ones before: now (how it happens today — the baseline) → scope 5W+1H → conditions "
                "(нельзя · не сможем · есть · деньги · инструменты) → requirements → beyond → "
                "THE IDEAL: its checkable parts are PROMISES on the root of the tree — "
                "success · metric · checklist, each with «чем проверим», not_validated until "
                "checked (checks.jsonl) — and the ideal itself one paragraph, last → parts (his big "
                "pieces, each saying which promises it unfolds) → clarified → summary → HIS WORD "
                "over the picture, carrying the seq it was said over: anything written after it "
                "makes it stale, and el forward asks for a fresh one"),
        "long": ("QUESTIONS ARE THE INSTRUMENT: ask well and pull out as much as the owner has "
                 "— he often knows less about his own task than it seems, and this is where the "
                 "rocks under the water surface BEFORE the work starts. Scope draws the boundary "
                 "of the figure and shows where the line is sharp and where it is blurred; "
                 "requirements say what inside it is already built and what is not. Both exist "
                 "to separate the SOLID from the EMPTY — after the questions no emptiness should "
                 "remain unnamed. Gathering ends when the task is RESTATED and scoped, not when "
                 "the folder looks full. WRITE IT OUT IN FULL: a detail skipped here looks "
                 "redundant while things are still general, but it is needed at execution, where "
                 "it can no longer be recovered — numbers with units, paths with filenames, the "
                 "owner's words verbatim, boundaries stated."),
        "gate": ("обязательные следы лестницы (их считает el status) · граница отвечена по всем 6 измерениям · у каждой "
                 "owner-области есть хотя бы один вопрос · все вопросы с ответами · хотя бы "
                 "одна находка research · СЛОВО ВЛАДЕЛЬЦА (не обходится ничем; остальное — "
                 "--waive с причиной)"),
        "cmds": ['el context qa "<question>" "<answer>" --area <area>', "el context scope",
                 'el research "<тема>" --summary "<выжимка>" --file research/<имя>.md', "el context",
                 'el accept "<его слова дословно>"'],
    },
    "think": {
        # Generated from THINK_STEPS, same reason as context: the ladder and the checklist must
        # not be able to drift apart. `tools.md` stays optional and is listed separately.
        "artifacts": [(rel, title, THINK_MIN.get(_k, "soft")) for _k, rel, title, *_r in THINK_STEPS] +
                     [("поле tool на записях думания", "какие приёмы брал и что дал каждый", "strict")],
        "how": ("TEN RUNGS AND TWO FLOWS in records.jsonl, by the law of context. FLOWS: forks (his "
                "word changes the road — options with plus and minus, a recommendation, «почему "
                "твоё»; closed by a decision event; the bar is решено N/N) and risks. RUNGS: mirror "
                "→ form → core → ENGINEERING PROMISES (what the solution must hold, born here into "
                "checks.jsonl, with «чем проверим» and «сломается, если») → reversibility → OPTIONS "
                "(paths as branches, each SCORED against every promise — the bar is the cells "
                "paths × promises) → stress (на прочность: tried to break the chosen path, held?) "
                "→ crystal (the surviving path, pruned ones kept with why) → route (stage seeds "
                "with deps, the plan cuts them) → HIS WORD over the decision. A tool is a field "
                "on the record it produced (--tool); the eight categories of the box count from "
                "it — soft asks for диагностика · расширение · опровержение"),
        "gate": ("все развилки закрыты (не обходится) · обязательные следы лестницы (их считает el status; остальное — --waive с причиной) · "
                 "поправки к контексту, сделанные здесь, покрыты свежим словом владельца"),
        "cmds": ['el think <шаг> "<текст>"  ·  el think crystal "<что прояснилось · почему>" --ref f1',
                 'el think fork <id> "<вопрос>" --who owner|agent --decide "<что решить>"',
                 'el think fork <id> --option "<вариант>" --cost "<цена>" --model "<что это>" '
                 '--falsifier "<что убьёт>"  ·  --preview <html>  ·  --recommendation "<…>"',
                 'el think decide <id> "<вариант>" --words "<его слова>" --fixed "<что зафиксировано>"',
                 'el log "<aha>" --type insight'],
    },
    "plan": {
        "artifacts": [
            ("records.jsonl#stages", "этапы — узлы верхнего уровня с полями", "light"),
            ("checks.jsonl@stage", "обещания этапов — что каждый обязан выдать", "soft"),
            ("records.jsonl#approval", "слово владельца над картой этапов", "light"),
        ],
        "how": ("NETWORK PLANNING AT THE LEVEL OF STAGES (owner, 2026-08-27): the plan ends with a "
                "MAP — stages with their fields, deps and stops, each stage carrying its PROMISES "
                "(what it must deliver, чем проверим) hung on it in checks.jsonl, not_validated. "
                "Packages, works and tasks come on execute, when a stage STARTS — its layout is "
                "shown, his word over it (el accept --for stage:s2), and only then the packages "
                "start, each with its own promises. The tree of promises grows with the tree of "
                "work; validate folds it upward. Stages are RECORDS: a node record at birth, `set` "
                "events for every change, never a rewrite; the network (waves) is computed from "
                "`deps` — there is no plan.md. Inserting a stage between two: a new node with deps "
                "and a set on the follower. Three to seven stages is the usual cut; the first "
                "holds the preparation, the last the final check. His yes over the map is the "
                "way out of plan — not an assumption."),
        "gate": ("узлы заведены ДО работы, не после — по номерам записей, не по датам · есть хотя бы один этап · "
                 "у каждого этапа есть обещание (soft) и остановка · ПОКРЫТИЕ: за каждым обещанием корня и "
                 "крупной частью пути стоит этап (el plan integrity) · слово владельца над картой"),
        "cmds": ['el plan new s1 "<этап>"', 'el plan set s1 <поле> "<текст>"', "el sync",
                 'el accept "<его «да» над планом>"',
                 'el forward --why "plan accepted by the owner"'],
    },
    "execute": {
        "artifacts": [
            ("artifacts/", "what was produced, in its place", "soft"),
            ("evidence/", "internal technical validation: tests, output, logs", "soft"),
        ],
        "how": ("This is the commit point: before it everything replays for free, after it "
                "the world changed. WORK GOES NODE BY NODE, and the state says whose move it "
                "is (owner, 2026-08-22): `el plan start <узел>` names THE node in work (one "
                "at a time). A STAGE IS LAID OUT BEFORE IT STARTS (owner, 2026-08-26): work "
                "packages → tasks → subtasks, the nearest level only; the layout is shown to the "
                "owner and his word recorded over the stage (el accept … --for stage:s4); the "
                "packages are what you start, never the stage itself (light mode warns, soft and "
                "strict refuse) · do it · answer its criteria AS YOU GO "
                "(el validate <узел> N --met … --evidence <файл>) — the local check, not a "
                "pile for the end · file artifacts and evidence TO the node (--node) · at the "
                "node's stop show the human and hand him the baton (el plan wait) — then do "
                "not drive on until his word is recorded (el accept --for node:…) · close "
                "with an observable result (el plan done) · a parent closes after its "
                "children. Internal validation (tests green) lives HERE; the owner's "
                "acceptance of the whole is the NEXT phase and cannot be replaced by 'I "
                "checked it myself'. Код коммитится ПО ХОДУ, а не в конце: незакоммиченная "
                "работа умирает вместе с деревом."),
        "gate": ("все узлы плана закрыты (done) или осознанно отложены (parked --why) — не "
                 "обходится · у закрытых узлов вердикт по каждому критерию (закрыть без "
                 "вердиктов el plan done не даёт) · artifacts/ и evidence/ не пусты"),
        "cmds": ['el plan start s1  ·  el plan wait s1 "<что показал>"  ·  el plan done s1 "<результат>"',
                 'el validate s1 2 --met "<чем доказано>" --evidence evidence/<файл>',
                 'el artifact <file> --node s1  ·  el evidence <file> --node s1 --check 2',
                 'el accept "<его слова>" --for node:s1 [--close]',
                 'el log "<what was done>" --type step'],
    },
    "validate": {
        "artifacts": [
            ("checks.jsonl@verdicts", "ЛЕДЖЕР: вердикт по каждому обещанию — события в реестре, el validate", "soft"),
            # NOT context/acceptance.md — nothing has ever written that path. `el accept` puts
            # the owner's word in acceptance.md at the task root once the task is past context
            # (context has its own approval.md), and every other check in this file looks there.
            # The typo made validate demand a file that could not exist, which pushes an agent
            # to invent a second one. Found by the owner running `el status` (2026-08-20).
            ("records.jsonl#word:final", "слово приёмки, его словами — el accept --for final НА ЭТОЙ фазе (слово над планом не считается)", "light"),
        ],
        "how": ("Acceptance is given by the HUMAN — an agent saying 'looks fine' is not "
                "validation. Show the result in a form that can be judged, compare against "
                "the before-measurement, and record both the objective result and the "
                "subjective response."),
        "gate": ("свёртка сошлась на всех уровнях: у каждого критерия каждого узла И у каждого "
                 "пункта чек-листа приёмки из ИФР есть вердикт · ни одного «не проверено» и «не "
                 "сошлось» (иначе — доделать, снять вместе с работой, или --waive с долгом в "
                 "журнале; отказ называет держащие пункты адресом узел.номер) · реестр вердиктов · "
                 "СЛОВО ПРИЁМКИ, записанное на этой фазе — el accept; "
                 "слово над планом не считается, --waive не обходит"),
        "cmds": ["el validate", 'el validate s1 3 --met "<чем доказано>"',
                 'el accept "<его слова приёмки>"'],
    },
    "reflect": {
        "artifacts": [
            ("journal.jsonl", "lessons with context, recorded as events", "light"),
        ],
        "how": ("Работа над ошибками. The result is APPLIED CHANGES, not notes: a lesson "
                "becomes a flag in the future node where it will fire, a fixed rule, a "
                "repaired tool. A lesson that REPEATS across tasks belongs to the whole "
                "storage: el lesson writes it into lessons.md, and every agent sees it at "
                "onboarding — so the fifth task does not trip over the same stone as the "
                "first. A smooth cycle also teaches."),
        "gate": "journal.jsonl есть всегда — применён ли урок, судит человек, не CLI",
        "cmds": ['el lesson "<обо что споткнулись и как обходить>"',
                 'el log "<lesson>" --type lesson'],
    },
    "align": {
        "artifacts": [],
        "how": ("Check the DIRECTION, not the work: decide one of four — carry on (a new "
                "loop: el phase context) · re-route what is ahead · change the destination "
                "(needs the owner's explicit yes) · arrived. A stone found deep — on a task, "
                "a subtask — re-routes everything above it: that is normal, not a failure."),
        "gate": "решение по направлению названо в --why; смена цели — только словом владельца",
        "cmds": ['el forward --why "<решение по направлению>"'],
    },
    "close": {
        "artifacts": [],
        "how": ("THE TAILS, checked before the task is written off: nothing uncommitted "
                "(el done measures git itself and refuses over a dirty tree) · artifacts in "
                "their places · pages fresh (el ui) · nothing dangling in outside systems. "
                "Then the result, in words: a task closed with loose tails is work that "
                "stops existing a week later."),
        "gate": ("выхода вперёд нет — фаза последняя; закрывает el done: git чист (или "
                 "--dirty с причиной) · для completed все el todo закрыты"),
        "cmds": ["el ui", 'el done "<result>" --as completed|closed|dropped|blocked'],
    },
}


# THE BEATS THAT ARE NOT FILES — actions and checks, per phase, so the blueprint prints the
# whole ladder of every phase and not only the traces (owner, 2026-08-22: «чтобы я тоже
# понимал, какие такты и очередность»). (title, threshold mode, command)
# ── THE BEAT TABLE for the phases after think — one shape for every beat ─────────────
#
# (title, who, trace, minmode, description, command). The blueprint prints every phase from
# the same shape (context and think come from their ladders, see phase_beats()), so the
# contract reads as one outline and the data is the single source: change a beat here and
# `el blueprint` changes with it. `who` is owner | agent | both | cli — whose hand leaves
# the trace. `minmode` is the lowest mode in which the beat is required (see MODES).
PHASE_BEATS = {
    "plan": [
        ("этапы — карта крупных кусков с полями", "agent", "records.jsonl#stages", "light",
         "3–7 этапов, растут из route думания: цель · после чего · кто · оценка · риск. Первый — "
         "подготовка, последний — итоговая проверка. Этап — запись; правка — событие set; вставить "
         "между двумя — новый узел и одно set на следующем",
         'el plan new s1 "<этап>" · el plan set s1 deps "после S0" · el plan new s4 "…" --after s1 --before s2'),
        ("обещания этапов — что каждый обязан выдать", "both", "checks.jsonl@stage", "soft",
         "у каждого этапа хотя бы одно обещание: что станет правдой, когда этап закрыт, и чем это "
         "проверим. Ложится в реестр с адресом этапа; на исполнении пакеты раскроют его своими",
         'el plan promise s1 "<что выдаст>" --how "<чем проверим>"'),
        ("точки синхронизации — показ · развилка · разрешение", "both", "поле sync этапа", "soft",
         "у каждого этапа остановка и чьё слово там нужно: ПОКАЗ — показал и еду дальше · РАЗВИЛКА — "
         "ответ меняет маршрут · РАЗРЕШЕНИЕ — необратимое, без его слова нельзя (необратимое из "
         "думания ложится сюда само)",
         'el plan set s2 sync "РАЗРЕШЕНИЕ: показываю … · увидишь … · от тебя …"'),
        ("покрытие — за каждым куском цели стоит этап", "agent", "поле covers у этапов", "soft",
         "ПРОВЕРКА СВЕРХУ ВНИЗ: свёртка снизу отвечает «сдержали ли обещанное», это — «а всё ли "
         "нужное мы обещали». За каждым обещанием корня и каждой крупной частью пути — этап или "
         "объявленное место раскрытия; дыра видна ДО старта",
         'el plan set s1 covers "k1, p1" · el plan integrity'),
        ("сетевой план — порядок и волны", "cli", "считается из deps", "light",
         "не пишется — вычисляется: волны узлов, которые могут идти рядом, стрелки «после чего». "
         "Страница рисует, `el plan` печатает",
         "el plan"),
        ("слово владельца над картой этапов", "owner", "records.jsonl#approval", "light",
         "предъяви карту содержимым: этапы, что каждый выдаст, где остановимся; скажи, что "
         "каждый этап разложится при старте. Его «да» — над этой нарезкой, с номером картины",
         'el accept "<его слова>"'),
    ],
    "execute": [
        ("раскладка этапа обговорена и принята — до записи", "owner", "records.jsonl#word:stage", "soft",
         "этап сам не стартует (владелец, 2026-08-26): перед стартом агент ПРЕДЛАГАЕТ раскладку "
         "владельцу в чате — пакеты работ → работы → подзадачи, только ближайший уровень, узел "
         "размером с день — обговаривает и записывает его «одобряю» над этапом; пакеты записываются "
         "ПОСЛЕ слова, не до («агент порывается записывать декомпозицию, не поговорив»); под грантом — "
         "решение в его место (--assumed); в light — предупреждение, в soft и strict — отказ",
         'el accept "<его слова>" --for stage:s1 --on "<раскладка: wp1 … · wp2 …>"'),
        ("пакеты этапа записаны и стартуют", "agent", "records.jsonl#nodes", "soft",
         "после его слова раскладка ложится в узлы и стартует первый пакет; стартуют пакеты, не этап",
         'el plan new s1 wp1 "<пакет работ>" · el plan new s1 wp1 t1 "<работа>" · el plan start s1.wp1'),
        ("этапы друг за другом", "cli", "статусы узлов", "light",
         "узел следующего этапа не стартует и не показывается владельцу, пока предыдущий этап не "
         "закрыт целиком — все вложенные узлы done или park (владелец, 2026-08-26); «предыдущий» — "
         "по deps этапа, без них — все этапы с меньшим номером; --force — осознанно, в журнал",
         "el plan done s1.wp6 \"…\" · el plan park s1.wp6 --why \"…\" → el plan start s2.wp1"),
        ("назван активный узел — один", "agent", "status: active в nodes/<узел>.md", "light",
         "СНАЧАЛА УЗЕЛ, ПОТОМ РАБОТА — узел заводится и стартует ДО первого шага, не после (владелец, 2026-08-25: агенты делали работу, а потом заводили узлы и заполняли бумаги; по штампам узел жил 40 секунд и «сделал» час работы). Увидел новую работу — el plan new, потом делай; контракт допишешь до закрытия, но узел существует раньше работы. Дальше узел за узлом: start → делать и писать el log (ложится к узлу) → критерии по ходу, не пачкой в конце → следы к узлу → остановка "
         "(wait) → done; активный узел один — по нему el next ведёт доску",
         "el plan start s1"),
        ("критерии узла отвечаются по ходу, доказательство — файлом", "agent", "checks.jsonl@verdicts", "soft",
         "вердикт ставится ТОГДА, когда критерий проверен, а не на validate скопом; --evidence "
         "указывает на существующий файл — он становится доказательством [путь]",
         'el validate s1 2 --met "…" --evidence evidence/<файл>'),
        ("артефакты и доказательства положены к узлу", "agent", "artifacts/ · evidence/", "soft",
         "что произведено — в artifacts/, чем доказано — в evidence/; --node привязывает к узлу, "
         "--check — к критерию; след без узла — сирота, его ищут потом",
         "el artifact <файл> --node s1 · el evidence <файл> --node s1 --check 2"),
        ("остановка узла: показано человеку, эстафета у него", "agent", "status: waiting", "soft",
         "остановка по полю sync: показано человеку, эстафета у него; пока он не сказал — узел "
         "ждёт, другие узлы вести можно",
         'el plan wait s1 "<что показал>"'),
        ("слово человека по узлу, эстафета назад", "owner", "records.jsonl#word:node", "soft",
         "слово человека по узлу записано его словами; --close закрывает узел тем же ходом; "
         "эстафета вернулась к агенту",
         'el accept "<его слова>" --for node:s1 [--close]'),
        ("узел закрыт наблюдаемым результатом; родитель — после детей", "agent", "status: done", "light",
         "закрывается наблюдаемым результатом, не словом «сделано». ЗАКРЫТИЕ = ПЕЧАТЬ ПРОВЕРКИ: "
         "el plan done не закроет узел, пока у его критериев нет вердиктов и пока открыт хоть "
         "один ребёнок; «не сошлось» и «не проверено» не закрывают — чини и перемеряй или "
         "останавливайся и спрашивай человека (el plan wait). Снять критерий можно только явно, "
         "со своим «потому что» (--declined)",
         'el plan done s1 "<результат>"'),
        ("все узлы закрыты или осознанно отложены", "agent", "status: done | parked", "light",
         "в validate не пускает, пока есть открытый узел: закрыть done — или отложить park --why, "
         "осознанно, с причиной в журнале",
         'el plan park s1 --why "…"'),
    ],
    "validate": [
        ("вердикт по каждому критерию узлов — свёрткой снизу вверх", "agent", "checks.jsonl@verdicts", "light",
         "ОДИН ЗАКОН НА ВСЕ УРОВНИ: проверка узла = свои критерии + свёртка детей; работа — только "
         "свои, пакет — свои плюс работы, этап — свои плюс пакеты, корень — САМА ЗАДАЧА: чек-лист "
         "приёмки (ifr) плюс все этапы плюс слово человека. Ничего не собирается отдельным тактом: "
         "вердикты ставятся по ходу и запечатываются при закрытии узла, сюда приходит уже готовое "
         "дерево. «Не проверено» и «не сошлось» не пускают вперёд: доделать, снять вместе с работой "
         "(--declined со своим «потому что»), либо --waive с долгом в журнале",
         'el validate  ·  el validate s1  ·  el validate s1 3 --met "…" --evidence …'),
        ("вердикт по каждому пункту чек-листа приёмки из ИФР", "both", "checks.jsonl@verdicts (IFR)", "soft",
         "чек-лист приёмки (context/acceptance-checklist.md) проходится как псевдоузел ifr — "
         "пункт за пунктом, вердикт его словами",
         'el validate ifr 1 --met "<его слова>"'),
        ("показано так, что можно потрогать", "agent", "—", "light",
         "файл, экран, ссылка, запуск — не рассказ о том, что сделано; показ делается руками, "
         "записи в CLI у него нет",
         "—"),
        ("слово приёмки владельца НА ЭТОЙ фазе", "owner", "records.jsonl#word:final", "light",
         "приёмку даёт владелец — на этой фазе и своими словами; слово с других фаз (plan · node) "
         "не считается; не обходится",
         'el accept "<его слова>" --for final'),
    ],
    "reflect": [
        ("урок применён — правило, флажок, инструмент", "agent", "../lessons.md", "soft",
         "урок — не «быть внимательнее», а применённое правило: флажок, проверка, инструмент; "
         "уроки копятся в хранилище и читаются на старте следующей задачи",
         'el lesson "<обо что споткнулись>"'),
        ("урок про путь лёг поправкой в план или контекст", "agent", "поправка [пN] в документе фазы", "strict",
         "если урок про путь — он ложится поправкой (--why обязателен), а не остаётся в голове",
         'el context … --why "…" · el plan set … --why "…"'),
    ],
    "align": [
        ("решение по направлению: дальше · перестроить · сменить цель · приехали", "owner",
         "--why в событии forward", "light",
         "пять ходов: дальше по плану · перестроить план · сменить цель (только его словом) · "
         "приехали → close · вернуться назад (свободно); решение названо в --why",
         'el forward --why "<решение>"'),
    ],
    "close": [
        ("git чист или осознанно --dirty", "agent", "дерево git", "light",
         "внешний след: код закоммичен и влит; el done не закрывает задачу над грязным деревом — "
         "закоммить или --dirty с причиной в журнал",
         'el done … --dirty "<почему без коммита>"'),
        ("артефакты на местах, страницы свежие", "agent", "artifacts/ · overview.html", "soft",
         "артефакты лежат в artifacts/, страницы перерисованы (CLI делает это сам при каждой "
         "записи; el ui — вручную, --open откроет)",
         "el ui"),
        ("все el todo закрыты", "agent", "records.jsonl#todos", "light",
         "completed запрещён, пока открыт хотя бы один el todo; остальные исходы — с открытыми",
         "el todo --done N"),
        ("результат записан, исход назван", "agent", "событие done в журнале", "light",
         "задача закрыта одним из исходов: completed · closed · dropped · blocked — смысл каждого "
         "ниже, в правилах поверх фаз",
         'el done "<результат>" --as completed|closed|dropped|blocked'),
    ],
}

# Stage 0 — the birth of a project, in the same shape.
STAGE0_BEATS = [
    ("хранилище .projects с маркером .elephant", "cli", ".projects/.elephant · index.html", "light",
     "папка в корне рабочего проекта, создаётся один раз при первом проекте; опознаётся по "
     "пустому скрытому маркеру, не по имени; рядом index.html — страница всех проектов",
     'el boot "<задача>" --id <имя> --raw "<его слова о задаче>"'),
    ("проект <дата>-<имя из 3–5 английских слов>", "agent", "<проект>/journal.jsonl · overview.html", "light",
     "имя придумывает агент — короткое, каким задачу назвали бы вслух; транслит фразы — брак. "
     "Внутри: журнал (только в конец), страница проекта; папки этапов появляются с первым "
     "следом; карточка не хранится — имя, фаза, исход выводятся из журнала",
     "тот же el boot — идемпотентен: чего нет, создаст; что есть, не тронет"),
    ("запрос пользователя — его словами, только о задаче", "owner", "init/request.md", "light",
     "с чем человек пришёл, его словами — не пересказ агента (переформулировка теряет деталь), "
     "но и не стенограмма: что о задаче — остаётся, постороннее и шум распознавания — нет, "
     "форма чуть собрана; пока не записан — el next напоминает",
     'el boot "<задача>" --id <имя> --raw "<его слова о задаче>"'),
]

# One line per phase — the essence for the big picture (el blueprint without a part).
PHASE_BRIEF = {
    "init":     "из разговора родилась задача: хранилище · проект · запрос пользователя его словами",
    "context":  "собрать картину: вопросы человеку · границы · требования · ИФР · свёртка — и его слово над картиной",
    "think":    "думать как инженер: кто и зачем · форма · ядро · идеалы · исследование · варианты с ценой · развилки его словами · кристалл",
    "plan":     "сетевой план и узлы с контрактом — ДО работы, не после; остановки назначены заранее; его слово над планом",
    "execute":  "узел за узлом: активный один · el log ложится к нему · критерии по ходу · следы к узлу · остановки по плану · эстафета",
    "validate": "матрёшка сошлась: вердикт по каждому критерию каждого узла, свёртка вверх до самой задачи, чек-лист ИФР; показано так, что можно потрогать; приёмка его словами",
    "reflect":  "урок применён — правило, флажок, инструмент; не заметка",
    "align":    "решение по направлению: дальше · перестроить · сменить цель · приехали",
    "close":    "хвосты: git чист · артефакты на местах · todo закрыты · исход назван",
}

WHO_RU = {"owner": "от человека", "agent": "от агента", "both": "от обоих", "cli": "от CLI"}


def phase_beats(ph):
    """Every beat of a phase in ONE shape: (title, who, trace, minmode, description, command).

    context and think come from their ladders (CONTEXT_STEPS / THINK_STEPS + the mode
    thresholds), the rest from PHASE_BEATS, stage 0 from STAGE0_BEATS — so the blueprint,
    the page and any future reader print the contract from a single table."""
    if ph == "init":
        return list(STAGE0_BEATS)
    if ph == "context":
        return [(title, src, rel, CONTEXT_MIN.get(key, "soft"), do, cmd or "—")
                for key, rel, title, src, do, cmd in CONTEXT_STEPS]
    if ph == "think":
        out = [(title, src, rel, THINK_MIN.get(key, "soft"), do, cmd or "—")
               for key, rel, title, src, do, cmd in THINK_STEPS]
        out.append(("приёмы думания — что брал и что дал каждый", "agent", "поле tool на записях думания", "strict",
                    "ящик приёмов печатает el think tools: бери под задачу, не один любимый на всё; "
                    "пиши, что КАЖДЫЙ приём дал — и чего не дал",
                    'el think tools "<какой взял и что он дал>"'))
        return out
    return list(PHASE_BEATS.get(ph, []))

# What to do in each phase, and the command that closes it. This is a MAPPING from
# observed state to an action, not a judgement: the CLI never decides whether the work
# was good, it only reports what the files show and which command moves things on.
NEXT_MOVE = {
    "context":  "collect context and write it into context/; then: el forward --why \"<what is established>\"",
    "think":    "name the options and their cost, let the crystal ripen record by record (el think crystal), close the forks; then: el forward --why \"...\"",
    "plan":     "write the order of steps and how the result is measured — BEFORE the work, never after it; then: el forward --why \"...\"",
    "execute":  "node by node: el plan start → do → criteria as you go (el validate … --evidence) → traces --node → el plan wait at the stop → el plan done; then: el forward --why \"...\"",
    "validate": "attach proof to evidence/ and compare against the before-measurement; then: el forward --why \"...\"",
    "reflect":  "work through the mistakes: fix what stopped you, file the lessons — el lesson \"<урок>\"; the TOOL tripped you — el feedback \"<что>\"; then: el forward --why \"...\"",
    "align":    "check the direction: carry on (el phase context — new loop) · re-route · change the destination (owner's word) · arrived; then: el forward --why \"...\"",
    "close":    "sweep the tails: git clean, artifacts in place, pages fresh (el ui); then: el done \"<результат>\" --as ...",
}


# The CLI carries the METHOD, not just the commands: an agent that calls `el help` must
# learn how the process works without anyone explaining it again. (Owner, 2026-08-18:
# "the CLI itself becomes the instruction".)
MECHANICS = """
HOW IT WORKS

  THE CONTEXT PHASE IS A LADDER, and `el next` names the step you are standing on
    questions (a LOOP, not one pass) → SCOPE, the frame: 5W+1H + requirements ·
    constraints · limitations · resources · finance · tools · definitions · beyond
    (близко к границе, но НЕ делаем — замыкает рамку) →
    ideal result → clarified task → summary → what I still do not know → the owner's word.
    Every step answers four things: what to gather · WHO it comes from · how · which command.

  WHO IT COMES FROM is the routing that decides everything
    owner  lives ONLY in his head — intent, priorities, taste, the limits of his world
    agent  obtainable with an instrument — code, data, logs, devices, docs, web
    both   start yourself, ask only for the remainder
    Asking the owner for something you could measure is stealing his time. Fetching what
    only he knows is inventing it.

  Clarifying questions are ADAPTIVE — never written in advance
    ask the owner in the conversation → hear the answer → record the pair:
        el context qa "<question>" "<answer>"
    The NEXT block of questions is derived from the PREVIOUS answers, so a pre-filled list
    with empty answers is a questionnaire, not context gathering. Up to 5 per round.
    A question without an answer is refused: it is not context yet.

  Context comes from THREE sources, and `el context` shows all three
    owner   what the human gave: questions.md (asked / answered counts)
    local   code, logs, history, config, tests, data, devices — findings in research/
    web     external facts; never the first move — findings in research/ too
    Research is ONE FILE PER TOPIC (research/<имя>.md) holding the material with anchors —
    path, link, page — so it can be found AGAIN and checked; the record is the digest:
        el research "<тема>" --summary "<выжимка ясным языком>" --file research/<имя>.md
    Gathering from the OWNER ends by HIS WORD — he says "достаточно", or he starts asking
    YOU "what else would you add?" (he is checking for gaps: offer yours and wrap up), or
    answers turn into "don't know" / "later". Record his closing word as the last Q/A pair.
    From there fetch the rest yourself; a counter never decides.

  SYNERGY IS THE GOAL of gathering: when the human is talking, he is IN THE WAVE — he
    thinks, you collect. Questions invite answers; keep him talking and SORT AS YOU GO:
    everything he pours out lands in its right file at once (боль → questions, границы →
    scope, термин → definitions, мечта → ifr) — like groceries into their jars, буквально
    в момент, когда он говорит. What lands now will feed every later phase.

  Phases move forward ONE at a time, and only with a reason
    el forward --why "<what is closed and what proves it>"     reason goes to the journal
    el forward --waive "<why we go without proof>"             recorded as `waived`
    el phase <earlier-phase>                                   going back is free and normal
    Leaving `context` needs every step of the ladder AND the owner's word. Traces can be
    waived one by one with a stated reason; the owner's word cannot — `el forward` refuses
    outright until `el accept` has recorded what he actually said.

  Beats are proven by TRACES, never by marks
    a beat counts as done when <phase>/<beat>.md exists, or `el beat <name>` logged it.
    A mark you set yourself proves nothing — a file does.

  Every task ENDS in a written result — `el done "<result>" --as <kind>`
    completed  the destination was reached, there is a result
    closed     closed by understanding: taken apart, and no action turned out to be needed
    dropped    turned out to be the wrong task, or no longer needed
    blocked    stuck on something external; what is missing is written down
    A result is required. A task closed without one cannot be told apart from one that was
    simply abandoned — and a month later nobody can say how it ended.
    `completed` also requires every `el todo` to be closed: an open item is an unfinished
    promise, so "destination reached" would contradict the project's own record.

  A FORK IS A GATE — and a gate has a form (owner, 2026-08-21)
    question · who decides · a PREVIEW he can touch: one page, every variant side by side,
    real content, toggles — copied into thinking/previews/ so the project page opens it ·
    each option: model · cost · falsifier (which observation kills it) · the agent's working
    recommendation · what exactly he must decide · his words VERBATIM and what they fixed.
        el think fork <id> "<question>" --who owner --decide "<what to decide>"
        el think fork <id> --option "<name>" --cost "…" --model "…" --falsifier "…"
        el think fork <id> --preview <html>   ·   --recommendation "…"
        el think decide <id> "<option>" --words "<his words>" --fixed "<what is now settled>"
    One command writes both files — decisions.md (the ledger the gates read) and options.md
    (the dossier, gate by gate, append only). A fork the owner decides is not shown without
    a preview: a description of variants is not a presentation. The next gate grows out of
    the previous decision.

  THE TOOL ITSELF IS UNDER WORK — tell it what hurt (owner, 2026-08-22)
    el feedback "<what got in the way · what helped>" [--about <command>] [--by "<who you are>"]
    el feedback "<his words>" --from user          the owner's verdict on the tool, verbatim
    One file per review in the skill's feedback/ — the POOL of improvement work; a meta-session
    reads it, fixes the CLI, deletes the file. The loop is «use · break · mend in the same
    move»; what you could not mend, write down — the agent that feels the pain is rarely
    the one that fixes it, and a remark in the chat dies with the session.

  AUTONOMY IS A GRANT — A PERIOD WITH A START AND AN END (owner, 2026-08-22 · 2026-08-26)
    el grant "<his words: работай сам>" [--name "…"] [--hours N] [--until "…"] [--no "…"]
                                               his word that opens it — recorded verbatim
    el grant change "<his words>" --hours 4    he corrected the standing grant — the same grant
    el grant end "<what proves it>"            the condition or the term reached — the natural end
    el halt "<why · what is needed>"           HOLD, the emergency exit — it cannot go on without him
    el halt "<his words>" --by user            his own «стоп» — the grant taken back by the owner
    Under a grant you DECIDE IN HIS PLACE: el accept … --assumed "<why>" · el context qa … --assumed
    · el think decide … --assumed --undo. A decision is not a debt and is not rolled back —
    he reads it when he returns (el review), and if he wants it otherwise he says so and the
    work goes on from the CURRENT state. The final word (acceptance) is never decided for him.
    Keep brief.md (el brief) — the one sheet a returning agent reads first: where the baseline
    lies, what is best, what not to repeat, what is now. Rewritten, bounded, never a chronicle.
    Details: el blueprint autonomy · el blueprint search

  Start here if you are new to this: `el blueprint` prints the whole protocol.

  This tool never calls a model. The agent thinks; the CLI remembers.
"""


# ── AUTONOMY — a credit of the owner's word (owner, 2026-08-22) ─────────────────
# Printed by `el blueprint autonomy`. Not a mode on the light/soft/strict slider (that is
# about traces); a separate axis — WHO gives the word and WHEN. Derived from two recorded
# facts: a `grant` event (his words) and, later, a `halt` event (where it stopped).
AUTONOMY_TITLE = "АВТОНОМИЯ — грант и решения агента под ним"
AUTONOMY_RULES = [
    ("грант", 'автономию выдаёт человек своим словом — «работай сам», «действуй автономно», '
              '«продолжай без меня»: el grant "<его слова дословно>" [--name "<коротко>"] [--hours N — '
              'срок] [--until "<до какой остановки>"] [--no "<чего не делать: push · деньги · удаление · '
              'отправка>"]. Агент сам себе автономию не выдаёт. Грант — период: начался его словом, '
              'кончается одним из пяти концов (см. «конец»); начался и не кончился — активен. '
              'Всё вычисляется из журнала, не хранится'),
    ("изменение", 'владелец поправил условия действующего гранта («давай четыре часа, не два») — тот же '
                  'грант, изменение внутри: el grant change "<его слова>" --hours 4 | --until | --no; '
                  'записано кто, когда, что было → стало. «Продолжай» после конца — новый грант'),
    ("решение", 'там, где нужен человек, а его нет, агент решает в его место: те же команды с --assumed '
                '"<почему так принял>" — el accept … --assumed (слово над картиной · планом · остановкой '
                'узла), el context qa "<вопрос, который задал бы>" "<ответ, который предполагаю>" '
                '--assumed, el think decide … --assumed --undo "<как откатить>". Предположение — самое '
                'узкое, совместимое с его словами; помечено в файле и в журнале под грантом. Это не '
                'долг и не откатывается: решение уже сделано и по нему работали; он прочтёт, вернувшись '
                '(el review — гранты и решения под ними, новые с его последнего слова помечены), не '
                'согласится — скажет, и дальше по его слову от ТЕКУЩЕГО состояния. Решения '
                'закончившегося гранта — история, на них не опираются'),
    ("владелец", 'ДОЛГ ВЛАДЕЛЬЦА, обратный случай: ответ есть только у человека, и его пока нет — он пошёл '
                       'выяснять или думать (кто подписывает, кто третий, какой вариант). '
                       'el owe "<вопрос>" --how "<у кого / где>" — на любой фазе. Занять ТАКОЙ ответ '
                       'нельзя — знание не у агента; сам по себе он не тормоз: держит только то, к '
                       'чему привязан (--holds node:… · el plan block <узел> --owe <n>), там работа '
                       'стоит; всё держится → el halt. Принёс ответ — el owe answer <n>, узел '
                       'отпускается сам'),
    ("последнее слово", 'приёмка (--for final) не занимается никогда: автономный прогон кончается '
                        'состоянием «готово, жду приёмки», а не completed. Смена цели — только его словом'),
    ("конец", 'пять концов гранта. Естественный — условие или срок достигнуты: el grant end "<чем '
               'доказано>" (срок --hours вышел — el status говорит «срок вышел — заверши»). Аварийный — '
               'hold: следующий шаг требует его слова, которое за него не решить (приёмка, смена цели); '
               'необратимого действия, которого грант не разрешал; или ходов честно не осталось (плато, '
               'семейства исчерпаны) — el halt "<почему дальше без человека нельзя · что нужно от него>" '
               '— и стоп, не «done». Владелец сказал «стоп» — el halt "<его слова>" --by user. Новый '
               'грант поверх действующего — прежний заменён. Задача закрыта — грант кончился с ней. '
               'el status печатает конец первым; новый грант — только его словом («продолжай»)'),
    ("замер", 'автономный поиск возможен ровно настолько, насколько автоматичен замер: «лучше» '
              'должно мериться командой. Нет прибора — агент сначала строит его (узел-стенд) и '
              'помечает выбор как решение в его место; иначе он меряет на глаз и врёт себе'),
    ("листок", 'brief.md — максимальное сжатие для агента, не для человека: baseline и где лежит · '
               'чем меряем · лучшее и где лежит · что не повторять · что сейчас. Переписывается целиком '
               '(el brief "<текст>"), ограничен по строкам и символам — не влезло, убери менее важное; '
               'el и el status печатают его первым'),
    ("гигиена петли", 'холостой ход (взгляды el status подряд без единого нового следа), повтор '
                      'гипотезы (el plan new отказывает по имени), попытка без результата — CLI видит и '
                      'говорит; застой — дисциплина агента: K попыток без улучшения → назад в думание '
                      'за новым семейством, с записью в кристалл «что понял»'),
    ("петля harness", 'Goal Claude Code (или петля Codex) — мотор и судья «достигнуто ли условие»; '
                      'Elephant ни о них не знает. Условие для /goal: «работай по Elephant над <задача>; '
                      'в конце каждого хода печатай el status; цель достигнута, когда el status показывает '
                      'задачу закрытой или АВТОНОМИЯ ОСТАНОВЛЕНА ЗДЕСЬ». Судья читает разговор, поэтому '
                      'состояние должно быть НАПЕЧАТАНО, не подразумеваться'),
]

# ── SEARCH — a task with a measurable destination is a loop inside execute ───────
SEARCH_TITLE = "ПОИСКОВАЯ ЗАДАЧА — «работай, пока не …»"
SEARCH_RULES = [
    ("что это", 'задача с измеримым концом: «ужми модель на 2 ГБ без потери качества», «найди '
                'быстрее текущего». Это не новая фаза и не тип задачи — это форма работы внутри '
                'исполнения: гипотеза → попытка → замер → запись → следующая. Фазы вокруг остаются: '
                'понять · подумать · спланировать · исполнить · проверить на живом · уроки · сверка'),
    ("контекст", 'сам за двоих, если человека нет: что значит «лучше» (метрика, набор, порог) · чем '
                 'меряем · что допустимо · где граница (что НЕ делаем — beyond) — вопрос + предполагаемый '
                 'ответ, помечен как решение в его место. Цель словами — в ИФР (критерии успеха · чек-лист); числа — в '
                 'критериях этапа поиска'),
    ("думание", 'baseline — замер «как сейчас» · семейства методов, не попытки · кристалл копит, что '
                'понято. Сюда возвращаются по ходу — за новым семейством, когда старое исчерпано '
                '(el phase think --why) — это штатно'),
    ("план", 'прост: S1 стенд и замер (результат — baseline) · S2 поиск (гипотеза = узел-пакет, '
             'S2.WP1, S2.WP2 … растёт по ходу: следующая рождается из результата предыдущей, '
             'раскрывай только уровень, на котором стоишь) · S3 проверка на живом. Критерии S2 — '
             'числами («size ≤ 6.0 GB · quality ≥ 0.92 на eval-v1»)'),
    ("исполнение", 'одна попытка в работе: el plan new s2 wp4 "<гипотеза>" · el plan start · работа · '
                   'el plan done s2.wp4 "<результат одной строкой в одном формате: 6.4 ГБ · acc 0.925 · '
                   'оставил>" — даже неудачная: тупик — это знание. Все гипотезы с итогами — el plan s2; '
                   'одна — el plan s2 wp4. Лучшее не теряется: артефакт с числами в artifacts/ '
                   '(el artifact … --node s2.wp4)'),
    ("возврат", 'обрыв или сжатие контекста → el (рука · автономия · листок) → el next (активная '
                'попытка) → el plan s2 (что пробовали) → продолжил. Контекст — не в памяти, а в '
                'адресуемой структуре; CLI — адресная книга'),
    ("конец", 'бинарная цель (достиг числа · доказал) → S3 на живом → уроки → «готово, жду приёмки» '
              '(el halt или приёмка человеком). Открытая цель («лучше текущего») — лучшего «done» нет: '
              'плато → записать, остановиться (el halt), решает человек. Застой в семействе → думание. '
              'Бюджет — не правило: сроком становится человек, когда приходит спросить «как дела» '
              '(el status) и говорит «продолжай» (el grant)'),
]

# brief.md — the one sheet for a returning agent. Bounded: the limit IS the discipline.
BRIEF_LINES = 20
BRIEF_CHARS = 1500


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
