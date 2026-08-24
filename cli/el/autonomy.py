"""Autonomy — a credit of the owner's word (owner, 2026-08-22).

Not a mode: the light/soft/strict slider says which traces must exist; this layer says WHO
gives the word and WHEN. Two recorded facts — a `grant` (his words that opened autonomy)
and, later, a `halt` (where the agent stopped because the grant reached no further) — and
everything else is derived: whether autonomy is on, which words were borrowed (`assume`
events), which of them his later words have paid, what the debt is.

The law behind it: the owner's word is never removed or replaced — it is borrowed and
written down as a debt. Same law as amendments and the journal: append, never overwrite.
"""
import os, sys
from .state import task_meta
from .term import human_when


def state(root, task):
    """None when no grant was ever given; else a dict: grant · halt · assumes · debt."""
    meta = task_meta(root, task)
    g = meta.get("grant")
    if not g:
        return None
    assumes = list(meta.get("assumes") or [])
    return {"grant": g, "halt": meta.get("halt"), "assumes": assumes,
            "debt": debt(meta), "active": not meta.get("halt")
            and meta.get("status", "active") == "active"}


def pays(word_for, assume_for):
    """Does his word over `word_for` cover a borrowed word over `assume_for`?

    Exact scope pays exact scope. The word over the PICTURE (context) pays every borrowed
    answer and borrowed context word — the picture he says «да» over includes them. The
    final word pays only final: accepting the result is not reading the assumptions.

    What deliberately does NOT roll up (owner's law, restated 2026-08-23 on a feedback
    report that `--for plan` did not clear `node:*` debts): the word over the PLAN is given
    BEFORE the work, and a borrowed word inside a node is taken DURING it — «да, план
    такой» cannot retroactively mean «да, узел S2 действительно работает». Widening the
    coverage here would be the tool paying the human's debt for him. The hint below names
    the exact command instead."""
    if word_for == assume_for:
        return True
    if word_for == "context" and (assume_for.startswith("qa") or assume_for == "context"):
        return True
    return False


def debt(meta):
    """Borrowed words not yet paid by a later real word over the same scope."""
    out = []
    for a in meta.get("assumes") or []:
        paid = any(w.get("ts", "") > a.get("ts", "") and pays(w.get("for") or "", a.get("for") or "")
                   for w in meta.get("words") or [])
        if not paid:
            out.append(a)
    return out


def on(root, task):
    """Autonomy is ON: a grant stands and no halt followed it (and the task is open)."""
    st = state(root, task)
    return bool(st and st["active"])


def guard(root, task, what="займ слова"):
    """Refuse a borrowed word when no grant covers it — printed, returns False."""
    st = state(root, task)
    if not st:
        print(f"{what} без гранта невозможен — человек не давал автономии.", file=sys.stderr)
        print('hint     спроси его · либо, если он сказал «работай сам», запиши это: '
              'el grant "<его слова дословно>"', file=sys.stderr)
        return False
    if st["halt"]:
        print(f"{what} невозможен — автономия остановлена здесь: "
              f"{(st['halt'].get('text') or '')}", file=sys.stderr)
        print('hint     продолжить может только человек: el grant "<его слова: продолжай>"',
              file=sys.stderr)
        return False
    return True


def lines(root, task, full=False):
    """What `el` · `el status` · `el next` print about autonomy. [] when there is none."""
    st = state(root, task)
    if not st:
        return []
    g, out = st["grant"], []
    # His words are printed WHOLE, on their own line under the header: the conditions of the
    # credit often stand at the END of a long sentence («…пока не срежешь 2 ГБ»), and a cut
    # quote is a different grant (owner, 2026-08-23). Never truncate here.
    if st["halt"]:
        h = st["halt"]
        out.append(f"АВТОНОМИЯ ОСТАНОВЛЕНА ЗДЕСЬ  {human_when(h.get('ts'))}")
        out.append(f"          «{(h.get('text') or '').strip()}»")
        out.append('          грант дальше не распространяется; продолжить — его слово: '
                   'el grant "<его слова>" · долг слова: el review')
    else:
        out.append(f"автономия выдана {human_when(g.get('ts'))}"
                   + (f" · до: {g['until']}" if g.get("until") else "")
                   + (f" · нельзя: {g['no']}" if g.get("no") else ""))
        out.append(f"          «{(g.get('text') or '').strip()}»")
        if full:
            out.append('          займ слова: el accept "<что принимаешь за его слово>" --assumed "<почему>" '
                       '[--for <scope>] · граница: el halt "<почему · что нужно>"')
    n = len(st["debt"])
    if n or full:
        out.append(f"долг слова {n}" + (" — el review · платит его слово над той же областью" if n else ""))
    return out


def review_lines(root, task):
    """The ledger of borrowed words — for `el review`."""
    meta = task_meta(root, task)
    st = state(root, task)
    out = []
    if not st:
        out.append("автономии у задачи не было — займов нет")
        return out
    g = st["grant"]
    out.append(f"ГРАНТ     {human_when(g.get('ts'))} · «{(g.get('text') or '').strip()}»"
               + (f" · до: {g['until']}" if g.get("until") else "")
               + (f" · нельзя: {g['no']}" if g.get("no") else ""))
    if st["halt"]:
        out.append(f"СТОП      {human_when(st['halt'].get('ts'))} · {(st['halt'].get('text') or '').strip()}")
    assumes = st["assumes"]
    if not assumes:
        out.append("займов    нет")
        return out
    unpaid = {id(a) for a in st["debt"]}
    out.append(f"займы     {len(assumes)} · долг {len(unpaid)}")
    for i, a in enumerate(assumes, 1):
        mark = "ДОЛГ  " if id(a) in unpaid else "оплач."
        out.append(f"  #{i:<3}{mark} {human_when(a.get('ts')):<14} {a.get('for') or '?':<16} "
                   f"{(a.get('text') or '').strip()}")
        if a.get("why"):
            out.append(f"        почему: {a['why']}")
        if a.get("undo"):
            out.append(f"        откат:  {a['undo']}")
    if unpaid:
        # A READY COMMAND PER DEBT (feedback pool, 2026-08-23: the agent read «одно слово над
        # картиной покрывает все займы контекста» as a promise that `--for plan` clears
        # node-debts too, and paid each node by hand after a detour). Coverage is narrow by
        # design — so the hint stops hinting and prints exactly what pays what.
        scopes, seen = [], set()
        for a in st["debt"]:
            sc = a.get("for") or "context"
            if sc not in seen:
                seen.add(sc)
                scopes.append(sc)
        out.append("платить   его слово над ТОЙ ЖЕ областью — по команде на каждую:")
        for sc in scopes:
            out.append(f'  el accept "<его слова>" --for {sc}')
        out.append("правило   слово над картиной (--for context) покрывает qa-займы контекста; "
                   "остальные области платятся точь-в-точь — слово над планом не гасит "
                   "займы по узлам (план принят ДО работы, займ взят ВО ВРЕМЯ), приёмку "
                   "(--for final) не занимают никогда")
    return out
