"""ЦЕЛОСТНОСТЬ МАРШРУТА — вторая половина проверки (его решение 2026-08-24).

Свёртка проверки идёт СНИЗУ ВВЕРХ и отвечает: «сдержали ли мы то, что обещали?» Она
работает только с тем, что кто-то записал, — а дыра невидима именно потому, что там,
где ничего не записано, нечего и проверять. Можно безупречно закрыть три отрезка пути
и не доехать, потому что четвёртый никто не нарисовал.

Целостность идёт СВЕРХУ ВНИЗ и отвечает на другой вопрос: «а всё ли нужное мы вообще
обещали?» Источников у неё два, и оба — слова человека:

  чек-лист приёмки  что он проверит руками — то, что должно стать правдой В КОНЦЕ
  крупные части     как он видит путь — через что мы туда идём (его пример: «отправили
                    документы — значит нужен этап дождаться подтверждения»; из чек-листа
                    такой этап не выводится, его знает только он)

Правило ста процентов (WBS): дети покрывают родителя целиком — не меньше и не больше.
Меньше — дыра; больше — работа, которой никто не просил.

И главная оговорка, без которой целостность душит работу (его второй пример: юридический
вопрос, где план до конца построить нельзя): **целостен не тот план, который расписан до
конца, а тот, в котором нет МОЛЧАЛИВЫХ дыр**. Дыра, объявленная вслух — что должно стать
известно, кто раскроет, что за ней стоит, — это законная часть маршрута (в управлении
проектами — planning package, планировочный пакет). Она покрывает цель наравне с работой.
"""
import os, re, sys
from .protocol import CONTEXT_FILES
from .state import journal, pick_task, require_root, task_mode, touch
from .plan import node_read, node_write, nodes_all, path_to_id
from .amend import acked


GOAL_KINDS = {"ifr": ("чек-лист приёмки", "checklist"),
              "part": ("крупные части пути", "parts")}


def goal_items(tdir, kind):
    """The goal's items of one kind, as a list — read from the source, never copied.

    Same principle as the ledger's checklist node: the text lives in context/, only the
    links live in the plan. Amended checklist ⇒ integrity is recomputed against the fresh
    text on the next call, with no migration of anything."""
    rel = CONTEXT_FILES.get(GOAL_KINDS[kind][1])
    if not rel:
        return []
    path = os.path.join(tdir, rel)
    if not os.path.exists(path):
        return []
    # One item per line — bulleted, numbered or PLAIN: `el context parts` writes the owner's
    # pieces one per line with no bullet, and until 2026-08-24 those counted as nothing
    # (found through the scenario: «parts only» → «считать не от чего»). Skipped: headings,
    # italic notes, amendment heads and their почему/основание lines.
    from .amend import AMEND_HEAD
    out = []
    for line in open(path, encoding="utf-8"):
        st = line.strip()
        if not st or st.startswith(("#", "_", "почему:", "основание:", "- основание:")):
            continue
        if AMEND_HEAD.match(line):
            continue
        m = re.match(r"^(?:[-*•]|\d+[.)])\s+(.+)$", st)
        out.append((m.group(1) if m else st).strip())
    return out


def covers_of(node):
    """{"ifr": {2, 3}, "part": {1}} — what this node declares it closes."""
    raw = (node.get("_fields", {}) or {}).get("covers") or ""
    out = {k: set() for k in GOAL_KINDS}
    for m in re.finditer(r"\b(ifr|part)\s*[:.]?\s*(\d+)", raw, re.I):
        out[m.group(1).lower()].add(int(m.group(2)))
    return out


def unfold_of(node):
    """The declared blank spot, if this node is one — see plan.unfold (planning package)."""
    return (node.get("unfold") or "").strip()


def integrity_state(tdir):
    """Everything integrity knows, in one call.

    {kind: [{n, text, by:[node ids], unfolded:[node ids]}]} plus the orphan nodes —
    those that declare no link to the goal at all."""
    nodes = sorted(nodes_all(tdir), key=lambda x: x["id"])
    out = {}
    for kind in GOAL_KINDS:
        items = []
        for i, text in enumerate(goal_items(tdir, kind), 1):
            by, unf = [], []
            for n in nodes:
                if i in covers_of(n)[kind]:
                    (unf if unfold_of(n) else by).append(n["id"])
            items.append({"n": i, "text": text, "by": by, "unfolded": unf})
        out[kind] = items
    linked = set()
    for n in nodes:
        c = covers_of(n)
        if c["ifr"] or c["part"]:
            linked.add(n["id"])
    # A node that covers nothing is not automatically wrong — a scaffolding node serves
    # other nodes. It is only worth naming when NOTHING in its subtree links to the goal:
    # then the whole branch is work nobody asked for (the other half of the 100% rule).
    orphans = []
    for n in nodes:
        sub = [x for x in nodes if x["id"] == n["id"] or x["id"].startswith(n["id"] + ".")]
        if not any(x["id"] in linked for x in sub) and "." not in n["id"]:
            orphans.append(n["id"])
    return out, orphans


def gaps(tdir):
    """The holes only: goal items nobody covers, by kind. Empty ⇒ the route is whole."""
    state, _orphans = integrity_state(tdir)
    return {k: [it for it in v if not it["by"] and not it["unfolded"]]
            for k, v in state.items()}


def has_goal(tdir):
    return bool(goal_items(tdir, "ifr") or goal_items(tdir, "part"))


# ── el plan cover · el plan integrity ─────────────────────────────────────────

def cmd_cover(root, task, tdir, words):
    """`el plan cover s1 ifr 2 3` — this node closes those items of the goal."""
    if len(words) < 3:
        print("el plan cover s1 ifr 2 3   ·   el plan cover s1 wp1 part 1", file=sys.stderr)
        print("  ifr  — пункты чек-листа приёмки (что человек проверит руками)", file=sys.stderr)
        print("  part — крупные части пути, названные человеком", file=sys.stderr)
        print("  посмотреть, что чем покрыто: el plan integrity", file=sys.stderr)
        return 1
    cut = next((i for i, w in enumerate(words) if w.lower() in GOAL_KINDS), -1)
    if cut < 1:
        print(f"скажи, что покрываем: {' · '.join(GOAL_KINDS)}", file=sys.stderr)
        return 1
    nid = path_to_id(words[:cut])
    kind = words[cut].lower()
    nums = []
    for w in words[cut + 1:]:
        if not w.isdigit():
            print(f"«{w}» не номер пункта — el plan cover {nid.lower()} {kind} 2 3",
                  file=sys.stderr)
            return 1
        nums.append(int(w))
    node = node_read(tdir, nid)
    if not node:
        print(f"нет узла {nid}", file=sys.stderr)
        return 1
    items = goal_items(tdir, kind)
    if not items:
        title, step = GOAL_KINDS[kind]
        print(f"нечего покрывать: {title} пуст — сначала собери на контексте "
              f"(el context {step})", file=sys.stderr)
        return 1
    bad = [x for x in nums if not (1 <= x <= len(items))]
    if bad:
        print(f"в «{GOAL_KINDS[kind][0]}» пунктов {len(items)}, а не "
              f"{', '.join(str(b) for b in bad)}", file=sys.stderr)
        return 1
    have = covers_of(node)[kind]
    fields = dict(node["_fields"])
    cur = (fields.get("covers") or "").strip()
    cur = "" if cur == "_пусто_" else cur
    added = []
    for x in nums:
        if x in have:
            continue
        cur = (cur + "\n" if cur else "") + f"- {kind}:{x} — {items[x - 1][:100]}"
        added.append(x)
    fields["covers"] = cur
    node_write(tdir, nid, node, fields)
    touch(root, task)
    if added:
        journal(root, task, "cover", f"{nid} покрывает {kind}: "
                f"{', '.join(str(a) for a in added)}", {"node": nid})
    print(f"{nid} покрывает {GOAL_KINDS[kind][0]}: "
          f"{', '.join(str(x) for x in sorted(have | set(nums)))}")
    left = gaps(tdir)
    n_left = sum(len(v) for v in left.values())
    print(f"без покрытия  {n_left}" + (" — маршрут целостен" if not n_left else
          " · что именно: el plan integrity"))
    return 0


def cmd_integrity(root, task, tdir, quiet=False):
    """The route seen TOP-DOWN: every item of the goal and who closes it."""
    if not has_goal(tdir):
        if not quiet:
            print("ЦЕЛОСТНОСТЬ НЕ ПОСЧИТАНА — считать не от чего: нет ни чек-листа приёмки, "
                  "ни крупных частей пути (код выхода 1)", file=sys.stderr)
            print("  собери на контексте: el context checklist … · el context parts …",
                  file=sys.stderr)
        return 1
    state, orphans = integrity_state(tdir)
    print("ЦЕЛОСТНОСТЬ МАРШРУТА — сверху вниз: за каждым куском цели кто-то стоит")
    total = covered = 0
    for kind, (title, step) in GOAL_KINDS.items():
        items = state[kind]
        if not items:
            print(f"\n{title}: пусто — el context {step}")
            continue
        print(f"\n{title}")
        for it in items:
            total += 1
            if it["by"]:
                covered += 1
                mark, who = "✓", ", ".join(it["by"])
            elif it["unfolded"]:
                covered += 1
                mark, who = "◻", ", ".join(it["unfolded"]) + " (раскроется позже)"
            else:
                mark, who = "✗", "НИКТО"
            print(f"  {mark} {it['n']}. {it['text'][:70]:<72}{who}")
    print(f"\nитого     {covered}/{total} кусков цели покрыто")
    # THE CHECKLIST IS THE OBLIGATORY SOURCE (context: success criteria · checklist · ideal
    # are required); without it the count above stands on the parts alone and must not read
    # as «whole». Non-zero, so a script or a gate cannot mistake it (feedback 2026-08-24:
    # «returned 0 while reporting that integrity could not be calculated»).
    partial = not state["ifr"]
    if partial:
        print("НЕ ПОСЧИТАНА до конца — чек-лист приёмки пуст: считалось только по крупным "
              "частям; собери: el context checklist … (код выхода 1)")
    holes = [f"{GOAL_KINDS[k][0]}: {', '.join(str(i['n']) for i in v)}"
             for k, v in gaps(tdir).items() if v]
    if holes:
        for h in holes:
            print(f"ДЫРА      {h}   ← держит ворота выхода из плана")
        print('закрыть   el plan cover <узел> ifr <N>  ·  завести узел: el plan new … · '
              'либо объявить незнание: el plan unfold <узел> "<что должно стать известно>"')
    # ORPHANS ARE ADVISORY (feedback 2026-08-24: «различать hard gaps и advisory orphans,
    # позволять пометить branch как out of scope»): they never hold the gate; a branch kept
    # on purpose is acknowledged once — el ack orphan:S2 --why — and stops being named.
    ack = acked(root, task)
    orphans = [o for o in orphans if f"orphan:{o}" not in ack]
    if orphans:
        print(f"ничьи     {', '.join(orphans)} — совет, ворота не держит: эти ветки не работают "
              "ни на один кусок цели")
        print("          привяжи: el plan cover <узел> ifr <N> · осознанно вне цели: "
              f'el ack orphan:{orphans[0]} --why "<зачем ветка>"')
    return 0 if not holes and not partial else 1
