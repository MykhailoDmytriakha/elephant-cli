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


CONTEXT_STEPS = [
    # init/request.md is NOT here on purpose (owner, 2026-08-21): it is a trace of STAGE 0,
    # not of context — by the time context starts, the tree exists and the request is
    # recorded. `el next` checks stage 0 separately and nags until it is closed.
    ("questions", "context/questions.md", "уточняющие вопросы", "owner",
     "ПЕРВЫЙ круг вопросов, и он про ЛЮДЕЙ и жизнь (его правка 2026-08-21): как этим "
     "пользуются, что при этом происходит, где человек находится — опыт и сценарии, НЕ 5W+H "
     "(те — отдельный ВТОРОЙ круг, шаг scope). ЦИКЛ, а не один проход: до 5 вопросов за "
     "раунд → услышать ответы → записать пары → после КАЖДОГО раунда сказать «вот как я "
     "сейчас понимаю задачу, вот какие вопросы остались — продолжать или достаточно?» — его "
     "«достаточно» и есть признак насыщения. НЕ проскакивай: requirements и ИКР не пишутся, "
     "пока круг вопросов не закрыт — контекст существует ради раскопок, а не ради галочек. "
     "Вопрос с вариантами ответа даёт более конкретный ответ, чем открытый — предлагай "
     "варианты. Вопросы печатаются В ЧАТ обычным текстом — вопрос и варианты под ним; НЕ "
     "интерактивной формой с кнопками: человек читает глазами и отвечает голосом. КОНЕЦ "
     "ОПРОСА решает ЧЕЛОВЕК, не счётчик: его «достаточно» записывается последней парой. "
     "Верный признак близкого конца — он сам спросил «а что ты ещё предлагаешь?» или "
     "«хочешь что-то добавить?»: он уже проверяет, не упущено ли, — предложи своё и "
     "закругляйся. Ответы теряют конкретику («не знаю», «позже») — тоже конец: дальше "
     "добираешь сам из кода и мира. И обязательно спроси, КАК ОН ПОЙМЁТ, что получилось — что "
     "проверит руками, что измерит (--area check): из этого вырастают критерии успеха, метрики "
     "и чек-лист приёмки, а не из головы агента",
     'el context qa "<вопрос>" "<ответ>" --area <область>   ·   второй и следующий раунд: '
     'добавь --new-round, иначе пары молча лягут в первый и цикл перестанет быть виден'),
    # The file IS the six questions, so it is named after them (owner, 2026-08-21):
    # 5w-h.md, not scope.md. The command stays `el context scope` — the word people say.
    ("scope", "context/5w-h.md", "границы 5W+1H: что входит в задачу, что не входит", "both",
     "ВТОРОЙ круг вопросов, после уточняющих, и он про ДЕЛО (его правка 2026-08-21): что "
     "делаем · зачем · кто делает и кто пользуется · когда срабатывает · где · как. "
     "Открывается сверкой: «вот как я сейчас понимаю задачу» — и только потом вопросы. "
     "ГРАНИЦА — ЭТО ВОПРОСЫ, по одному на измерение: what · why · who · where · when · how. "
     "Позови «el context scope» без аргументов — он напечатает сами вопросы и покажет, какие "
     "измерения ещё пусты. У каждого измерения обязательно называется и то, что ЯВНО НЕ "
     "входит: невысказанное «не входит» потом всплывает как «а я думал, это тоже». "
     "6 измерений собираются ОТВЕТАМИ, а не прозой агента: что уже закрыто вопросами — "
     "берётся оттуда, остальное добываешь сам или спрашиваешь точечно. Когда все шесть "
     "собраны — напечатай в чат СВОДКУ: по каждому измерению bullet-список, — и услышь "
     "подтверждение человека, что картина его",
     'el context scope — сами вопросы   ·   el context scope <изм> --in "<входит>" '
     '--out "<НЕ входит>" --blur "<где размыто>"'),
    # SCOPE IS THE WHOLE FRAME (owner, 2026-08-21): 5W+1H plus the six parts below — each
    # its own file, together they are «рамка», the frame the task lives inside.
    ("requirements", "context/requirements.md", "требования — что рамка обязана вместить", "both",
     "что внутри границы уже построено, чего нет, что неизвестно — с именами файлов, числами, "
     "путями. Требования решают, ЧТО в задачу входит, а что нет",
     'el context requirements "<что уже есть, чего нет, что неизвестно>"'),
    ("constraints", "context/constraints.md", "ограничения снаружи — чего нельзя", "owner",
     "рамки, поставленные миром и человеком: бюджет, сроки, правила, «этого не трогаем». "
     "«Ограничений нет» — тоже ответ, и он записывается",
     'el context constraints "<чего нельзя и почему>"'),
    ("limitations", "context/limitations.md", "пределы — чего мы не сможем", "both",
     "честные пределы возможностей: чего система, инструменты или мы сами не умеем. "
     "Названный предел не всплывёт на исполнении как сюрприз",
     'el context limitations "<чего не сможем и где предел>"'),
    ("resources", "context/resources.md", "ресурсы — что есть под рукой", "both",
     "люди, время, деньги, доступы, готовые куски. Чего нет — так и пиши: это и есть находка",
     'el context resources "<что доступно: люди · время · доступы · готовое>"'),
    ("finance", "context/finance.md", "финансы — бюджет и во что обойдётся", "owner",
     "деньги рамки: какой бюджет, что стоит денег (сервисы, подписки, люди, железо), "
     "что окупается и чем. Денег в задаче нет — так и записывается",
     'el context finance "<бюджет · что стоит денег · что окупается>"'),
    ("tools", "context/tools.md", "инструменты — чем будем работать", "agent",
     "чем делается работа: языки, сервисы, библиотеки, приборы. То, что уже выбрано или "
     "навязано окружением, — сюда; выбор новых — дело думания",
     'el context tools "<чем работаем и что навязано окружением>"'),
    ("definitions", "context/definitions.md", "определения — общий язык проекта", "both",
     "термины этой задачи, одинаково понятые всеми: у проекта своя терминология, и слово, "
     "понятое двояко, всплывает на исполнении как разное построенное. Собирается из его "
     "речи по ходу: прозвучал термин — запиши, что он означает ЗДЕСЬ",
     'el context definitions "<термин — что означает в этом проекте>"'),
    # beyond closes the FRAME (owner, 2026-08-21): есть то, что внутри квадратика, и то,
    # что снаружи — beyond и есть описание «снаружи», и оно входит в состав scope.
    ("beyond", "context/beyond-scope.md", "за рамкой — близко к границе, но НЕ делаем", "both",
     "замыкает рамку: вещи, которые лежат ВПЛОТНУЮ к границе и соблазнительно прихватить — "
     "но мы их сознательно НЕ делаем. Невысказанное «не делаем» потом всплывает как «а я "
     "думал, это тоже входит» посреди исполнения. Сюда же честно: что из близкого, может, "
     "СТОИТ втянуть в рамку — и это решает человек, до начала работ: пристройку дешевле "
     "поставить на стройке, чем достраивать к готовому дому",
     'el context beyond "<что рядом с границей и НЕ делается — и что, может, стоит втянуть>"'),
    # THE IDEAL RESULT THROUGH THE USER'S EYES — FIVE PARTS, each its own file, in the order
    # of accumulation (owner, 2026-08-21, after re-reading v1's project.json where IFR had
    # success_criteria · expected_outcomes · quality_metrics · validation_checklist · the ideal
    # — all generated by the model and only approved as a whole): the parts grow out of HIS
    # answers («как ты поймёшь, что получилось?» — the `check` area), and the ideal itself is
    # written LAST, when the four parts lie on the table. The checklist is what phase 5 walks.
    ("success", "context/success-criteria.md", "критерии успеха — при каких условиях это успех", "both",
     "ПРИ КАКИХ УСЛОВИЯХ человек назовёт это успехом — его словами, из его ответов на «как "
     "поймёшь, что получилось?». Условия, не перечень фич: «список уходит одним сообщением и "
     "его не надо править руками». Меньше трёх условий — спроси ещё",
     'el context success "<при каких условиях это успех — его словами>"'),
    ("outcomes", "context/expected-outcomes.md", "ожидаемые результаты — что будет существовать и наблюдаться", "both",
     "ЧТО БУДЕТ СУЩЕСТВОВАТЬ или наблюдаться, когда сделано: артефакты, состояния, поведение "
     "— «на экране X есть кнопка Y; после нажатия в чате появляется Z». Не путать с "
     "условиями успеха: это не «когда хорошо», а «что именно появится». Нет смысла для задачи "
     "— пропускается",
     'el context outcomes "<что появится и будет наблюдаться>"'),
    ("metrics", "context/quality-metrics.md", "метрики качества — числа с порогами", "both",
     "ЧИСЛА С ПОРОГАМИ, которыми проверка сможет мерить: «уведомление за 30 секунд», «не "
     "больше одного сообщения», «0 ручных правок». Значение предлагает агент, порог "
     "подтверждает человек. Задача без чисел — так и пиши: «метрик нет, качество субъективное»",
     'el context metrics "<метрика — порог · метрика — порог>"'),
    ("checklist", "context/acceptance-checklist.md", "чек-лист приёмки — что человек проверит руками", "both",
     "ЧТО ЧЕЛОВЕК ПРОВЕРИТ РУКАМИ на приёмке, пункт за пунктом, каждый — действие с "
     "наблюдаемым исходом: «- нажать поделиться → в чате один список». Bullet-список: по "
     "этим пунктам фаза проверки пойдёт буквально (el validate показывает их рядом с "
     "критериями узлов), из них же растут критерии узлов плана. Изменилась задача — чек-лист "
     "правится поправкой, и проверка читает свежий",
     'el context checklist "- <действие → что увидишь>\n- <…>"'),
    ("ifr", "context/ifr.md", "идеальный результат ГЛАЗАМИ ПОЛЬЗОВАТЕЛЯ — одним абзацем, последним", "both",
     "ПИШЕТСЯ ПОСЛЕДНИМ, когда четыре части уже лежат: сам идеал одним абзацем, глазами "
     "человека, не инженера — функция выполняется, а эти затраты не платятся. ИКР "
     "формулируется, когда рамка замкнута: нельзя сказать, какая цена не платится, пока не "
     "знаешь, какие цены есть. Инженерный идеал будет ПОЗЖЕ, на думании (семья идеалов) — "
     "это два разных взгляда, и нужны оба",
     'el context ifr "<идеал одним абзацем — функция выполняется, а эти затраты не платятся>"'),
    # HOW HE SEES THE WORK IN BIG PIECES (his decision 2026-08-24). The acceptance checklist
    # says what must be TRUE AT THE END; this says WHAT WE GO THROUGH to get there — and only
    # he knows it, because he has walked this road before. His example: «есть документы, их
    # нужно отправить, значит последний этап — получить confirmation». That stage follows
    # from no checklist item; it follows from his experience. Together with the checklist this
    # is the second source of ROUTE INTEGRITY: a plan missing a piece he named is not whole.
    ("parts", "context/big-parts.md", "крупные части пути — как ЧЕЛОВЕК видит работу", "owner",
     "СПРОСИ ЕГО: «через какие крупные куски мы туда идём, как ты это видишь?» — и запиши его "
     "словами, по строке на кусок. Это НЕ план: план строится позже и подробнее, здесь — его "
     "грубая рамка пути, то, что он знает из опыта, а агент знать не может («отправили "
     "документы — значит нужен этап дождаться подтверждения»). Из этих строк потом считается "
     "целостность маршрута: план, в котором нет названного им куска, неполон — либо заводи "
     "узел, либо скажи вслух, почему считаешь лишним, и возьми его слово. Молча выкинуть "
     "нельзя. Пути не видно совсем («вообще непонятно») — так и пиши: тогда первая часть "
     "будет «собрать информацию», вторая — «решить, что дальше», а остальное достроится после",
     'el context parts "- <крупный кусок>\n- <следующий>"'),
    ("clarified", "context/task.clarified.md", "задача после уточнений", "agent",
     "отдельное именованное действие, а не «файлы собрались»: свернуть всё в ЧЁТКУЮ задачу — "
     "цель, ключевые требования, желаемый результат, ограничения",
     'el context clarified "<задача одним куском: цель, требования, результат, ограничения>"'),
    ("summary", "context/summary.md", "всё собранное в одном чтении", "agent",
     "всё собранное в одно плотное чтение: что установлено фактом с якорем, что принято "
     "допущением, что осталось неизвестным",
     'el context summary "<всё собранное в одном плотном чтении>"'),
    ("unknown", "context/unknown.md", "чего я не знаю, но должен бы знать", "agent",
     "явный вопрос перед спуском: «что я НЕ знаю, что должен бы знать?» — по спецификации это "
     "самое часто игнорируемое условие гейта. Молчаливое «разберёмся по ходу» не считается",
     'el context unknown "<чего не знаю, что должен бы знать>"'),
    ("approval", "context/approval.md", "согласие человека, его словами", "owner",
     "ПРЕДЪЯВИ содержимым, а не ссылками: `el context` печатает всё сверху донизу — задача, "
     "границы, требования, ИКР, чего не знаем. Потом запиши его ответ ДОСЛОВНО. Это условие "
     "гейта, которое нельзя заменить чек-листом",
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
    "questions": "light", "scope": "soft", "requirements": "soft",
    "constraints": "strict", "limitations": "strict", "resources": "strict", "finance": "strict",
    "tools": "strict", "definitions": "strict", "beyond": "soft",
    "success": "soft", "outcomes": "strict", "metrics": "strict", "checklist": "soft",
    "ifr": "soft", "parts": "soft", "clarified": "light", "summary": "soft", "unknown": "soft",
    "approval": "light",
}
# The optional parts under the everyday (soft) mode — kept under its old name for readers.
CONTEXT_OPTIONAL = {k for k, m in CONTEXT_MIN.items() if m == "strict"}
# THE IDEAL RESULT, in order — what the overview page shows as one group, the ideal LAST.
IFR_PARTS = ["success", "outcomes", "metrics", "checklist", "ifr"]


# SCOPE THE FRAME, in order — what the overview page shows as one group. The ORDER is the
# accumulation (owner, 2026-08-21: "порядок помогает накапливать, плавно приходить шаг за
# шагом"): each part stands on the ones before it, and `beyond` closes the frame.
SCOPE_FRAME = ["requirements", "constraints", "limitations", "resources", "finance",
               "tools", "definitions", "beyond"]


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
THINK_STEPS = [
    # THE MIRROR COMES FIRST, and it is the owner's own pick (2026-08-19): "в оптике решателя
    # была классная тема — это зеркало". Its job is to stop the agent building for an imagined
    # user. His case, lived: a web app used by ONE person who is either on a laptop or on a
    # phone — never both at once — and the agent slid into multi-user mode and started building
    # synchronisation that nobody needed. Knowing who the people are and how they actually work
    # is what tells the agent where NOT to go.
    ("mirror", "thinking/mirror.md", "кто будет этим пользоваться и кого это заденет", "both",
     "ЗАЧЕМ ЭТОТ ШАГ: пока не сказано, кто именно этим пользуется, легко построить лишнее — например защиту от того, что несколько человек работают одновременно, когда человек один. Что написать: кто целевая аудитория · СКОЛЬКО их на самом деле и бывают ли они одновременно · как "
     "пользуются · чего ждут · в каком окружении живут. Дальше — главное: **в какие дебри НЕ "
     "уходить**. Приложение на одного человека не требует мультипользовательской синхронизации, "
     "и решить это надо ЗДЕСЬ, а не после того, как построили лишнее. "
     "И отдельным вопросом: КОГО ЕЩЁ это касается — люди, которых нет в разговоре, но которых "
     "решение задевает. В стройке соседи и разрешения · в учёте бухгалтер и налоговая · в "
     "обучении родители · в софте те, кто получит результат. Их не замечают, потому что они "
     "молчат, а всплывают они поздно и дорого",
     'el think mirror "<кто пользуется НА САМОМ ДЕЛЕ · сколько их · кого ещё заденет>"'),
    # First principles, with the owner's correction: the point is not to purify the request but
    # to notice when the PERSON is over-complicating because he cannot see the simpler road.
    # The agent that follows him builds the heavy system he described instead of the light one
    # he wanted.
    # The shape of the deliverable is a THINKING decision, not an implementation detail. His
    # examples (2026-08-19) span domains on purpose: research — video, audio, text with or
    # without pictures? a building — where, how, which colours? Decide it here or it gets
    # decided by accident, by whoever writes the first line.
    ("form", "thinking/form.md", "в каком виде человек получит результат", "both",
     "ЗАЧЕМ ЭТОТ ШАГ: одну и ту же работу можно отдать человеку по-разному, и выбор вида меняет саму работу — решить его после того, как сделано, значит переделывать. Что написать: не «что сделаем», а В КАКОМ ВИДЕ это придёт к человеку. Исследование — видео, аудио, "
     "текст с картинками или без? Интерфейс — где кнопка, какой жест, какие цвета, сколько "
     "тапов? Постройка — где, как, какого вида? Документ — таблица, письмо, схема? Форма — "
     "часть решения, а не оформление: она определяет, воспользуются результатом или нет",
     'el think form "<в каком виде человек получит результат>"'),
    ("core", "thinking/core.md", "что здесь главное, а что можно добавить потом", "agent",
     "ЗАЧЕМ ЭТОТ ШАГ: чтобы отделить то, без чего задачи нет, от того, что можно добавить позже — и не выбросить при этом просимое человеком. Как думать: первые принципы работают в ОБЕ стороны. Что здесь неоспоримо, а что «так принято». И "
     "отдельно: не усложняет ли сам человек, не видя более простого пути — увидел такой путь, "
     "СКАЖИ ему, а не строй тяжёлое молча. "
     "⚠️ ЯДРО НЕ ОТСЕКАЕТ, А РАЗДЕЛЯЕТ: что первостепенно и есть ядро, а что навешивается на "
     "него сверху. Просьбу человека, не попавшую в ядро, НЕ ВЫКИДЫВАЮТ — её кладут в обвес. "
     "Выбрасывание просимого уже стоило нескольких прецедентов",
     'el think core "<что ядро · что обвес сверху>"'),
    ("ideals", "thinking/ideals.md", "каким был бы идеальный результат и где он сломается", "both",
     "ЗАЧЕМ ЭТОТ ШАГ: идеал показывает, куда двигаться, даже если дойти нельзя; а края показывают, где решение сломается. Оба нужны ДО работы, а не после. Как думать: ОДИН идеал искажает. Минимум четыре, в терминах ЭТОЙ задачи: идеальный РЕЗУЛЬТАТ · "
     "идеальная ПРОЦЕДУРА · идеальное ВЗАИМОДЕЙСТВИЕ · идеальный ПУТЬ · идеальное СОСТОЯНИЕ "
     "человека. Проверка: идеал можно скопировать в чужой проект? значит это пожелание. "
     "И тут же — ГДЕ ЛОМАЕТСЯ: edge cases названы вслух, а рядом с каждым помечено, лежит он "
     "ВНУТРИ границ или за ними. Уйти чинить край за границей — самый частый способ раздуть "
     "работу вдвое",
     'el think ideals "<идеалы этой задачи · где ломается и по какую сторону границы>"'),
    # Research belongs HERE, not in context. Context gathers what IS; think goes looking for
    # what could be — best practice, how the field solves this class, which stack, which flow,
    # which design. The owner listed them himself (2026-08-19): "research, поиски, собирать
    # best practices… определения каких-то flow… технологический стек… или юридические,
    # финансовые вопросы — вот когда они насобирались, из них принялось решение".
    ("research", "thinking/research.md", "как такое делают другие и какими средствами", "agent",
     "ЗАЧЕМ ЭТОТ ШАГ: почти всякую задачу кто-то уже решал, и способ обычно дешевле придумать заново. Это не сбор контекста задачи, а поиск ПОД РЕШЕНИЕ: как этот класс решают в поле · какой стек "
     "и почему · какой flow · какой дизайн · какие нормы и цены, если вопрос юридический или "
     "денежный. Каждый факт с источником и датой. Из собранного потом принимается решение — "
     "поэтому оно и стоит перед развилками",
     'el think research "<как это решают другие · источник и дата>"'),
    # BASELINE. The measurement taken BEFORE anything is built — without it "стало лучше" is
    # an opinion. His words: "мы делаем baseline, замер до того, как делаем, чтобы что-то
    # понять".
    ("baseline", "thinking/baseline.md", "как оно работает сейчас, до всякой правки", "agent",
     "ЗАЧЕМ ЭТОТ ШАГ: без записанного «как было» фраза «стало лучше» останется мнением, и проверить работу будет нечем. Что написать: число или наблюдение, снятое ДО первой правки, и записанный СТЕНД — чем именно мерили, "
     "чтобы потом повторить тем же. Замер «до» бывает не только у поломки: задумали новое — "
     "запиши, чего сейчас нет, сколько занимает вручную, где ломается. Нет «до» — на проверке "
     "сравнивать будет не с чем",
     'el think baseline "<замер до · чем мерили>"'),
    # SHALLOWS AND BLOCKS — his image: feel out the bottom before sailing. Not risk-management
    # theatre; the concrete question of where the road is closed and who can close it.
    ("shoals", "thinking/shoals.md", "что может помешать: запреты, деньги, люди, сроки, техника", "both",
     "ЗАЧЕМ ЭТОТ ШАГ: препятствие, найденное на исполнении, стоит переделки; найденное сейчас — стоит одного абзаца. Что написать: где встанем, ДО того как пошли — где мель, где дорога закрыта, где пробка. Блоки "
     "бывают разной природы и их надо назвать по имени — ЮРИДИЧЕСКИЕ (нельзя по закону или "
     "договору) · ФИНАНСОВЫЕ (нет денег или не окупается) · ЛЮДСКИЕ (некому, или человек не "
     "согласится) · ВРЕМЕННЫЕ (не успеваем к сроку, окно закрыто) · ТЕХНИЧЕСКИЕ (платформа не "
     "даёт). И форс-мажоры: что может случиться и что мы тогда делаем",
     'el think shoals "<где встанем: юр · фин · люди · сроки · техника>"'),
    # REVERSIBILITY decides where the gates go, which is why it is its own step and not a note
    # inside the obstacles. "Where the road is closed" and "where the road is one-way" are
    # different questions with different consumers: the first shapes the route, the second
    # shapes who is allowed to press the button.
    ("undo", "thinking/reversibility.md", "что нельзя будет отменить, если сделаем", "both",
     "ЗАЧЕМ ЭТОТ ШАГ: отсюда становится понятно, где человек обязан нажать кнопку сам, а где агент может идти без спроса. Что написать: пройди по задуманному и раздели: что откатывается своими силами · что откатывается "
     "дорого · что НЕ откатывается вовсе. Необратимое узнаётся по следу вне разговора — залитый "
     "фундамент · проведённый платёж · отправленное письмо · миграция базы · сказанное человеку "
     "слово · опубликованное. Из этой границы прямо следует, где кнопку нажимает ЧЕЛОВЕК, а "
     "где агент идёт сам: там, где откатить нельзя, решает человек",
     'el think reversibility "<что откатывается · что дорого · что нельзя>"'),
    ("forks", "thinking/options.md", "какие есть пути и чем платит каждый", "agent",
     "ЗАЧЕМ ЭТОТ ШАГ: решение, выбранное из одного варианта, — это не выбор, а угадывание. Что написать: выложи ВСЕ ходы, а не первые попавшиеся. У каждого — цена: чем платим, что станет хуже, "
     "что придётся держать потом. Меньше трёх на развилку значит поле не открыто. "
     "⚠️ И на КАЖДОЙ развилке обязателен НУЛЕВОЙ ВАРИАНТ — не делать, оставить как есть — со "
     "своей ценой. Это самая дешёвая экономия, какая бывает: иногда лучший ход именно он, а "
     "выложить его на стол некому, потому что разговор начинается с того, что делать БУДЕМ. "
     "И смотри ВПЕРЁД, в разработку: какие технические связи и нюансы вылезут — выяснять ДО "
     "решения, а не перестраивать после. РАЗВИЛКА — ЭТО ГЕЙТ, и у гейта форма (владелец, "
     "2026-08-21): вопрос и кто решает · ПРЕВЬЮ, которое можно потрогать — одна интерактивная "
     "страница со всеми вариантами рядом, с настоящим содержимым, переключателями; копируется "
     "в проект (thinking/previews/) и открывается со страницы · у каждого варианта модель, "
     "цена и falsifier — какое наблюдение его убьёт · рабочая рекомендация до выбора · что "
     "именно должен решить человек. Развилку, которую решает человек, без превью не показывай: "
     "описание вариантов — не предъявление. Одна команда пишет ОБА файла: decisions.md — леджер "
     "(по нему ходят гейты) и options.md — досье, гейт за гейтом, только в конец",
     'el think fork <id> "<вопрос>" --who owner|agent --decide "<что решить>"  ·  '
     '--option "<вариант>" --cost "<цена>" --model "<что это>" --falsifier "<что убьёт>"  ·  '
     '--preview <html>  ·  --recommendation "<что советую>"'),
    # The owner's verdict on solitary crystallisation (2026-08-19): "механизм варки не сработал
    # ни разу". So the step is no longer the agent stewing alone — it is the two of them, and
    # the crystal is the thing that ripens in BOTH heads at once.
    # CRYSTALLISATION, not a final line (owner, 2026-08-21): the crystal is a PROCESS — it
    # grows record by record while thinking goes on, and at the end one can read not only
    # WHAT was chosen but HOW the road led there. `thinking/destination.md` is gone the same
    # evening: the goal in the owner's words is context/task.clarified.md (amended if thinking
    # moved it), the goal in the engineer's words is this file plus decisions.md.
    ("crystal", "thinking/crystal.md", "кристаллизация — как вызревает решение, запись за записью", "both",
     "ЗАЧЕМ ЭТОТ ШАГ: настоящее решение не собирается по кусочкам — оно вызревает, и вызревает в разговоре; а через неделю никто не помнит, ПОЧЕМУ пришли именно к этому. Кристалл — ПРОЦЕСС, не финальная строчка: пиши по ходу думания датированными записями, что прояснилось, что сдвинулось и почему — со ссылкой на развилку или находку (--ref). Последняя запись — решение, каким оно выкристаллизовалось; по цепочке видно, как к нему шли. Как думать: про себя и молча не сработало ни разу. Кристалл вызревает в обмене: приноси свою "
     "картину, слушай его, спорь — и созревает он у ОБОИХ сразу. Признак попадания — снял "
     "мысль с языка, и он говорит «да, именно». Признак решения, а не обхода: стало ПРОЩЕ и "
     "эффективнее одновременно. Не выпал — законный исход, так и пиши. Сдвинулась САМА "
     "ЗАДАЧА — это ещё и поправка к context/task.clarified.md (el context clarified \"…\" "
     "--why … --ref …), не только запись здесь",
     'el think crystal "<что прояснилось · что сдвинулось · почему>" [--ref f1]   ·   голый: el think crystal — вся цепочка'),
    ("refute", "thinking/refute.md", "попытка развалить своё же решение", "agent",
     "ЗАЧЕМ ЭТОТ ШАГ: решение, которое сошлось с первого раза и понравилось, разваливается на первом применении — если его никто не пробовал сломать. Что сделать: хотя бы один честный заход на опровержение. Бей по своему же решению: где оно "
     "разваливается, что не держит. Удар, который НЕ держится, называется вслух — иначе слом "
     "превращается в самоподтверждение",
     'el think refute "<удар по решению · держится ли>"'),
    ("order", "thinking/order.md", "что делаем первым, что потом, что от чего зависит", "both",
     "ЗАЧЕМ ЭТОТ ШАГ: порядок работ — это решение, а не следствие плана. Решённый здесь, он потом просто переносится в план. Что написать: что делается ПЕРВЫМ, что вторым, и что от чего зависит. Ядро — первым этапом; обвес — "
     "последующими этапами ТОЙ ЖЕ задачи, как в стройке: фундамент, потом фрейм, а "
     "электричество и стены могут идти параллельно. Здесь же говорится, что делается НЕ сейчас "
     "и почему. План потом строится ПО этому графику, а не изобретает его заново",
     'el think order "<что первым · что потом · что от чего зависит>"'),
    ("decision", "thinking/decisions.md", "что именно выбрали на каждом пути", "owner",
     "ЗАЧЕМ ЭТОТ ШАГ: выбор, сделанный в разговоре и нигде не записанный, через неделю невозможно ни вспомнить, ни оспорить. Что написать: развилка без записанного выбора уедет в план как догадка. Развилку, помеченную owner, "
     "закрывает ЕГО слово; помеченную agent — твоё объяснение, почему решил сам. КАК ЗАКРЫВАТЬ "
     "РАЗВИЛКУ ЧЕЛОВЕКА: предъяви её с превью (el think forks покажет, где оно), назови, что "
     "именно ему решить, услышь выбор — и запиши ЕГО СЛОВА ДОСЛОВНО (--words), не пересказ; "
     "тут же --fixed: что этим решением зафиксировано — основа, на которой стоит следующий "
     "гейт (следующая развилка вырастает из этого решения, не открывается с нуля). Команда "
     "допишет решение и в леджер decisions.md, и в досье options.md. ВЫБРАЛ ДИЗАЙН — назови "
     "ОБЯЗАТЕЛЬНОСТЬ превью (--fidelity): conceptual — обязательна идея · layout — структура, "
     "порядок и размеры областей · visual — плюс controls, плотность, цвета и композиция · "
     "production — реализация совпадает максимально, отклонение согласуется заново. Без этого "
     "реализация разъезжается с тем, что он выбирал (пилот 2026-08-22): узел плана, строящий "
     "этот UI, пишет id развилки в inputs — и перед закрытием сверяет as-built с превью",
     'el think decide <fork> "<вариант>" --words "<его слова>" --fixed "<что этим зафиксировано>" '
     '--fidelity conceptual|layout|visual|production'),
]


# CARTA MOVED OUT (owner, 2026-08-19): "карта — это же относится к контексту, правильно?"
# Yes. The map of the system is gathering, and it belongs to phase 1; what happens in Think
# when a piece of it is missing is a DRAWDOWN, not a return — you go and fetch the fact and
# keep thinking. Keeping a required `map.md` here duplicated the context phase and made the
# ladder heavier than the work.

THINK_FILES = {k: rel for k, rel, *_ in THINK_STEPS}
# From which mode each THINK beat is required: the forks and the choice hold in every mode,
# the ladder in soft, the heavy instruments (research, refutation, the box) in strict.
THINK_MIN = {
    "mirror": "soft", "form": "soft", "core": "soft", "ideals": "soft", "research": "strict",
    "baseline": "soft", "shoals": "soft", "undo": "soft", "forks": "soft", "crystal": "soft",
    "refute": "strict", "order": "soft", "decision": "soft",
}


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
        "how": ("A LADDER, not a pile — beat by beat: questions (a loop; the HUMAN ends it "
                "with his «достаточно», written as the last pair) → SCOPE, THE FRAME: 5W+1H "
                "plus requirements · constraints · limitations · resources · finance · "
                "tools · definitions · beyond (близко, но НЕ делаем — замыкает рамку), each "
                "its own file. THE ORDER IS THE ACCUMULATION: каждая часть стоит на "
                "предыдущих → THE IDEAL RESULT through the USER's eyes, five parts each its "
                "own file: success criteria → expected outcomes → quality metrics → acceptance "
                "checklist → the ideal itself, written LAST → clarified task → "
                "summary → what I still do not know → the owner's word. The raw request is "
                "already on disk (init/request.md, stage 0). `el next` names the step you "
                "are on and who the answer comes from. Ask the owner ONLY what lives in his "
                "head; anything measurable you fetch yourself — code, logs, the web."),
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
                 "один файл в research/ · СЛОВО ВЛАДЕЛЬЦА (не обходится ничем; остальное — "
                 "--waive с причиной)"),
        "cmds": ['el context qa "<question>" "<answer>" --area <area>', "el context scope",
                 'el research <source> "<finding>" --ref <anchor>', "el context",
                 'el accept "<его слова дословно>"'],
    },
    "think": {
        # Generated from THINK_STEPS, same reason as context: the ladder and the checklist must
        # not be able to drift apart. `tools.md` stays optional and is listed separately.
        "artifacts": [(rel, title, THINK_MIN.get(_k, "soft")) for _k, rel, title, *_r in THINK_STEPS] +
                     [("thinking/tools.md", "какие приёмы брал и что дал каждый", "strict")],
        "how": ("Lay out options before choosing: fewer than three means the field was not "
                "opened. Name the cost of each, walking back from the ideal final result "
                "stated in context. This is where thinking WITH the owner happens. Run at "
                "least one falsification pass before calling it done. A FORK THE OWNER "
                "DECIDES IS A GATE WITH A FORM: a PREVIEW he can touch (one page, every "
                "variant side by side, real content — copied into thinking/previews/), each "
                "option with model · cost · falsifier, the agent's recommendation, what "
                "exactly he must decide; then his words verbatim and what they FIXED — the "
                "basis the next gate stands on. `el think fork` writes the ledger "
                "(decisions.md) and the dossier (options.md) together. Работа живёт во "
                "внешней системе (код в git, база, документы)? Подход решается ЗДЕСЬ: "
                "нужна ли ветка, как вливаем, как откатываем."),
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
            ("plan.md", "network plan — a PROJECTION of the tree (deps · sync), written by el", "soft"),
            # nodes/ and the owner's word are what `el forward` actually refuses without —
            # the blueprint said «по нужде» while the gate said «НЕ ПУЩУ» (caught 2026-08-21).
            ("nodes/", "hierarchical decomposition: nodes with the eight fields", "light"),
            ("acceptance.md", "слово владельца над планом — el accept", "light"),
        ],
        "how": ("Two things live here and nowhere else: the NETWORK PLAN (what runs in what "
                "order, what depends on what, where it branches and merges) and the "
                "HIERARCHICAL DECOMPOSITION (one level at a time — expanding everything up "
                "front is what killed v1). EIGHT FIELDS per node, and a field may be 'N/A with "
                "a reason' but never silently empty: (1) result as an observable STATE, not "
                "effort spent · (2) validation criteria, at least five, each measurable without "
                "interpretation · (3) resources: people, technical, money, time · (4) artifacts "
                "the node produces · (5) where each artifact is stored — a concrete path, not "
                "'somewhere' · (6) inputs required from the parent or neighbours · (7) "
                "dependencies and order, acyclic · (8) who executes it. The move out of plan "
                "needs the owner's explicit yes — not an assumption."),
        "gate": ("узлы заведены ДО работы, не после (план — не бумаги задним числом); есть хотя бы один узел и у каждого заполнены все девять полей · ЦЕЛОСТНОСТЬ МАРШРУТА: за каждым пунктом чек-листа приёмки и каждой крупной частью пути стоит узел или объявленное место раскрытия (el plan integrity) · слово "
                 "владельца над планом (acceptance.md) · plan.md — проекция дерева, есть всегда, когда есть узлы"),
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
                "at a time) — a big stage is split into works first (el plan new s4 wp1 …) "
                "and the works are what you start · do it · answer its criteria AS YOU GO "
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
            ("validation.md", "ЛЕДЖЕР: вердикт по каждому критерию плана и пункту чек-листа приёмки — el validate", "soft"),
            # NOT context/acceptance.md — nothing has ever written that path. `el accept` puts
            # the owner's word in acceptance.md at the task root once the task is past context
            # (context has its own approval.md), and every other check in this file looks there.
            # The typo made validate demand a file that could not exist, which pushes an agent
            # to invent a second one. Found by the owner running `el status` (2026-08-20).
            ("acceptance.md", "слово приёмки, его словами — el accept НА ЭТОЙ фазе (слово над "
                              "планом не считается)", "light"),
        ],
        "how": ("Acceptance is given by the HUMAN — an agent saying 'looks fine' is not "
                "validation. Show the result in a form that can be judged, compare against "
                "the before-measurement, and record both the objective result and the "
                "subjective response."),
        "gate": ("свёртка сошлась на всех уровнях: у каждого критерия каждого узла И у каждого "
                 "пункта чек-листа приёмки из ИФР есть вердикт · ни одного «не проверено» и «не "
                 "сошлось» (иначе — доделать, снять вместе с работой, или --waive с долгом в "
                 "журнале; отказ называет держащие пункты адресом узел.номер) · validation.md · "
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
        ("целостность маршрута: за каждым куском цели кто-то стоит", "agent", "поле covers у узлов", "soft",
         "ПРОВЕРКА СВЕРХУ ВНИЗ, вторая половина проверки (его решение 2026-08-24): свёртка "
         "снизу отвечает «сдержали ли обещанное», а это — «а всё ли нужное мы обещали». "
         "Источников два, и оба его слова: чек-лист приёмки (что станет правдой в конце) и "
         "крупные части пути (через что идём). Каждый пункт обоих должен быть привязан к узлу "
         "(el plan cover), иначе это работа, которую мы просто не собираемся делать. Не знаем, "
         "что там будет — объяви дыру вслух (el plan unfold … --after <узел>): названная дыра "
         "тоже покрытие, молчаливая — провал",
         "el plan integrity  ·  el plan cover s1 ifr 2 3  ·  el plan cover s1 part 1"),
        ("сетевой план — проекция дерева", "agent", "plan.md", "soft",
         "не пишется рукой: el строит его из полей узлов — deps (что после чего; волны = что "
         "можно вести параллельно) и sync (где остановки). Почему порядок такой — thinking/order.md. "
         "Изменить план = изменить узлы (его решение 2026-08-24)",
         'el plan — печатает · el plan set s2 deps "после S1" · el plan set s2 sync "…"'),
        ("узлы с контрактом из девяти полей", "agent", "nodes/<узел>.md", "light",
         "узел — единица работы с контрактом: outcome · inputs · outputs · check · sync · "
         "depends · size · scope (light: результат + критерии). Уровни: этап s1 → работа s1/wp1 "
         "→ подзадача; id — имя из плана человека, не счётчик",
         'el plan new s1 "<этап>" · el plan set s1 <поле> "…"'),
        ("остановки узлов — показ · развилка · разрешение", "agent", "поле sync узла", "soft",
         "остановка назначается в плане, не на ходу: показ (показываю · увидишь · потрогать · "
         "от тебя) · развилка · разрешение; одна строка без ролей — тоже остановка, её вид CLI "
         "определит сам",
         'el plan set s1 sync "показываю: …\\nувидишь: …\\nпотрогать: …\\nот тебя: …"'),
        ("этап разложен на работы перед стартом", "agent", "nodes/s1/wp1.md", "strict",
         "в строгом режиме этап не стартует, пока не разложен на работы — чтобы активный узел "
         "был размером с день, не с неделю",
         'el plan new s1 wp1 "<работа>"'),
        ("не меньше пяти критериев у узла", "agent", "поле check узла", "strict",
         "в строгом режиме у узла не меньше пяти критериев: чем он закрыт, видно без автора",
         'el plan set s1 check "…"'),
        ("слово владельца над планом", "owner", "acceptance.md (for: plan)", "light",
         "план показан человеку, его слово записано дословно; без него в execute не пускает — "
         "обхода нет",
         'el accept "<его да>" --for plan'),
    ],
    "execute": [
        ("назван активный узел — один", "agent", "status: active в nodes/<узел>.md", "light",
         "СНАЧАЛА УЗЕЛ, ПОТОМ РАБОТА — узел заводится и стартует ДО первого шага, не после (владелец, 2026-08-25: агенты делали работу, а потом заводили узлы и заполняли бумаги; по штампам узел жил 40 секунд и «сделал» час работы). Увидел новую работу — el plan new, потом делай; контракт допишешь до закрытия, но узел существует раньше работы. Дальше узел за узлом: start → делать и писать el log (ложится к узлу) → критерии по ходу, не пачкой в конце → следы к узлу → остановка "
         "(wait) → done; активный узел один — по нему el next ведёт доску",
         "el plan start s1"),
        ("критерии узла отвечаются по ходу, доказательство — файлом", "agent", "validation.md", "soft",
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
        ("слово человека по узлу, эстафета назад", "owner", "acceptance.md (for: node:s1)", "soft",
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
        ("вердикт по каждому критерию узлов — свёрткой снизу вверх", "agent", "validation.md", "light",
         "ОДИН ЗАКОН НА ВСЕ УРОВНИ: проверка узла = свои критерии + свёртка детей; работа — только "
         "свои, пакет — свои плюс работы, этап — свои плюс пакеты, корень — САМА ЗАДАЧА: чек-лист "
         "приёмки (ifr) плюс все этапы плюс слово человека. Ничего не собирается отдельным тактом: "
         "вердикты ставятся по ходу и запечатываются при закрытии узла, сюда приходит уже готовое "
         "дерево. «Не проверено» и «не сошлось» не пускают вперёд: доделать, снять вместе с работой "
         "(--declined со своим «потому что»), либо --waive с долгом в журнале",
         'el validate  ·  el validate s1  ·  el validate s1 3 --met "…" --evidence …'),
        ("вердикт по каждому пункту чек-листа приёмки из ИФР", "both", "validation.md (ifr)", "soft",
         "чек-лист приёмки (context/acceptance-checklist.md) проходится как псевдоузел ifr — "
         "пункт за пунктом, вердикт его словами",
         'el validate ifr 1 --met "<его слова>"'),
        ("показано так, что можно потрогать", "agent", "—", "light",
         "файл, экран, ссылка, запуск — не рассказ о том, что сделано; показ делается руками, "
         "записи в CLI у него нет",
         "—"),
        ("слово приёмки владельца НА ЭТОЙ фазе", "owner", "acceptance.md (for: final)", "light",
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
        ("все el todo закрыты", "agent", "todo.md", "light",
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
     'el boot "<задача>" --id <имя> --raw "<слова дословно>"'),
    ("проект <дата>-<имя из 3–5 английских слов>", "agent", "<проект>/journal.jsonl · overview.html", "light",
     "имя придумывает агент — короткое, каким задачу назвали бы вслух; транслит фразы — брак. "
     "Внутри: журнал (только в конец), страница проекта; папки этапов появляются с первым "
     "следом; карточка не хранится — имя, фаза, исход выводятся из журнала",
     "тот же el boot — идемпотентен: чего нет, создаст; что есть, не тронет"),
    ("сырой запрос человека, слово в слово", "owner", "init/request.md", "light",
     "дословно, не пересказ: переформулировка может потерять деталь, дословная запись — "
     "страховка; пока не записан — el next напоминает",
     'el boot "<задача>" --id <имя> --raw "<слова дословно>"'),
]

# One line per phase — the essence for the big picture (el blueprint without a part).
PHASE_BRIEF = {
    "init":     "из разговора родилась задача: хранилище · проект · запрос человека дословно",
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
        out.append(("приёмы думания — что брал и что дал каждый", "agent", "thinking/tools.md", "strict",
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
    Research is ONE FILE PER SOURCE (research/code.md, research/web.md, research/book.md),
    every finding with an anchor — path, link, page — so it can be found AGAIN and checked:
        el research <source> "<finding>" --ref <anchor>
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

  AUTONOMY IS A CREDIT OF THE WORD, NOT ITS ABSENCE (owner, 2026-08-22)
    el grant "<his words: работай сам>"        his word that opens autonomy — recorded verbatim
    el accept "<what you take for his word>" --assumed "<why>" [--for <scope>]
    el context qa "<q>" "<assumed answer>" --assumed "<why>" --area <a>
    el think decide <fork> "<option>" --assumed "<why>" --undo "<how to reverse>"
    Every borrowed word is a DEBT: el review lists them, his later el accept over the same
    scope pays them; `completed` is refused while a debt stands. The last word (final
    acceptance) is never borrowed. When the grant does not reach the next step — it needs his
    word, or an irreversible act he did not allow, or you honestly have no move left:
    el halt "<why it stops here · what is needed from him>"  — and stop. Not «done».
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
AUTONOMY_TITLE = "АВТОНОМИЯ — кредит слова человека"
AUTONOMY_RULES = [
    ("грант", 'автономию выдаёт человек своим словом — «работай сам», «действуй автономно», '
              '«продолжай без меня»: el grant "<его слова дословно>" [--until "<до какой остановки>"] '
              '[--no "<чего не делать: push · деньги · удаление · отправка>"]. Агент сам себе '
              'автономию не выдаёт. Грант — событие журнала; «выдана / остановлена / долг N» '
              'вычисляется, не хранится'),
    ("займ", 'там, где нужен человек, а его нет, агент занимает слово: те же команды с --assumed '
             '"<почему так принял>" — el accept … --assumed (слово над картиной · планом · остановкой '
             'узла), el context qa "<вопрос, который задал бы>" "<ответ, который предполагаю>" '
             '--assumed, el think decide … --assumed --undo "<как откатить>". Предположение — самое '
             'узкое, совместимое с его словами; помечено в файле и в журнале'),
    ("долг", 'каждый займ — долг слова: el review печатает леджер (что принял · почему · оплачен ли). '
             'Платит человек своим словом над той же областью: el accept "<его слова>" --for context '
             'покрывает все займы контекста; --for node:<id> — займ остановки; --for design:<id> — '
             'развилку. completed с открытым долгом — отказ'),
    ("владелец", 'ДОЛГ ВЛАДЕЛЬЦА, обратный случай: ответ есть только у человека, и его пока нет — он пошёл '
                       'выяснять или думать (кто подписывает, кто третий, какой вариант). '
                       'el owe "<вопрос>" --how "<у кого / где>" — на любой фазе. Занять ТАКОЙ ответ '
                       'нельзя — знание не у агента; сам по себе он не тормоз: держит только то, к '
                       'чему привязан (--holds node:… · el plan block <узел> --owe <n>), там работа '
                       'стоит; всё держится → el halt. Принёс ответ — el owe answer <n>, узел '
                       'отпускается сам'),
    ("последнее слово", 'приёмка (--for final) не занимается никогда: автономный прогон кончается '
                        'состоянием «готово, жду приёмки», а не completed. Смена цели — только его словом'),
    ("граница", 'грант кончился, когда следующий шаг требует слова, которое занять нельзя; '
                'необратимого действия, которого грант не разрешал; или ходов честно не осталось '
                '(плато, семейства исчерпаны). Тогда: el halt "<почему дальше без человека нельзя · '
                'что нужно от него>" — и стоп. Это не «задача закрыта», это «мой кредит дальше не '
                'распространяется». el status печатает это первым; человек снимает остановку новым '
                'грантом («продолжай») или своим словом'),
    ("замер", 'автономный поиск возможен ровно настолько, насколько автоматичен замер: «лучше» '
              'должно мериться командой. Нет прибора — агент сначала строит его (узел-стенд) и '
              'помечает выбор займом; иначе он меряет на глаз и врёт себе'),
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
                 'ответ, пометка займа. Цель словами — в ИФР (критерии успеха · чек-лист); числа — в '
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
