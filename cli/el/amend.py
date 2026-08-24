"""Поправки — the picture changes, the history stays.

A document of a phase, written to AFTER the task has left that phase, is not gathered any
more — it is AMENDED: the old text stays in place, a dated section is appended that says
WHEN, on which PHASE, WHY, and on what GROUNDS (a fork, a finding, evidence, the owner's
words). One rule and no new verb — the phase decides: the same `el context clarified "…"`
that gathers during context is a correction after it, and then `--why` is required and
`--replace` is refused (history is not erased; in the boundary a moved line is struck
through, never deleted).

An amendment made after the owner said «да» over the picture re-opens that word: `el next`
says so, `el forward` asks for a fresh `el accept` — or a recorded `--waive`. This is the
first big stop of the sync axis («слово над картиной») applied to every later phase.
(Owner, 2026-08-21: «она не должна перетирать всё, она должна append — когда добавлено,
почему добавлено».)

THE FORM, readable in a notepad:
    ## Поправка п1 · 2026-08-22 14:03 · думание
    почему:     на развилке f1 выяснилось, что share intent не умеет вложения
    основание:  f1 · research/code.md · слова владельца «ладно, без картинок»

    ожидаемый результат: список уходит ОДНИМ сообщением, без картинок
List files (the boundary) mark the line instead — `- X [п1]`, a retracted line becomes
`~~+ X~~ [п1]` — and keep the п-notes in a closing «## Поправки» section.
"""
import json, os, re, sys
from .state import PHASES, journal, journal_path, now_iso, task_meta, touch, write

# Which phase OWNS a document — a write past that phase is an amendment.
DOC_PHASE = (("context/", "context"), ("thinking/", "think"), ("plan.md", "plan"), ("nodes/", "plan"))

AMEND_HEAD = re.compile(r"^## Поправка п(\d+) · (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (\S+)\s*$")
NOTE_LINE = re.compile(r"^- п(\d+) · (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (\S+) · почему: (.*?) · основание: (.*)$")
MARK = re.compile(r"\s*\[п(\d+)\]\s*$")


def stamp():
    return now_iso()[:16].replace("T", " ")


def doc_phase(rel):
    for prefix, phase in DOC_PHASE:
        if rel.startswith(prefix):
            return phase
    return None


def is_amendment(root, task, rel):
    """True when the task has already LEFT the phase that owns `rel`."""
    own = doc_phase(rel)
    if not own:
        return False
    cur = task_meta(root, task).get("phase", "context")
    return PHASES.index(cur) > PHASES.index(own) if cur in PHASES else False


def amend_block(n, phase, why, refs, text):
    grounds = " · ".join(r.strip() for r in (refs or []) if r.strip()) or "—"
    return (f"\n\n## Поправка п{n} · {stamp()} · {phase}\n"
            f"почему:     {why.strip()}\n"
            f"основание:  {grounds}\n\n{text.strip()}\n")


def split_amendments(text):
    """(base text, [amendment dicts]) of a prose document."""
    lines = (text or "").splitlines()
    base, items, cur = [], [], None
    for line in lines:
        m = AMEND_HEAD.match(line)
        if m:
            cur = {"n": int(m.group(1)), "ts": m.group(2), "phase": m.group(3),
                   "why": "", "refs": "", "text": []}
            items.append(cur)
            continue
        if cur is None:
            base.append(line)
        elif line.startswith("почему:") and not cur["text"] and not cur["why"]:
            cur["why"] = line[len("почему:"):].strip()
        elif line.startswith("основание:") and not cur["text"] and not cur["refs"]:
            cur["refs"] = line[len("основание:"):].strip()
        else:
            cur["text"].append(line)
    for it in items:
        it["text"] = "\n".join(it["text"]).strip()
    return "\n".join(base).rstrip(), items


def next_no(text):
    return len(split_amendments(text)[1]) + 1


def note_line(n, phase, why, refs):
    grounds = " · ".join(r.strip() for r in (refs or []) if r.strip()) or "—"
    return f"- п{n} · {stamp()} · {phase} · почему: {why.strip()} · основание: {grounds}"


def parse_notes(lines):
    out = []
    for line in lines:
        m = NOTE_LINE.match(line.strip())
        if m:
            out.append({"n": int(m.group(1)), "ts": m.group(2), "phase": m.group(3),
                        "why": m.group(4), "refs": m.group(5)})
    return out


def amend_events(root, task):
    """Every `amend` and `accepted` event of the journal, in order — the sync question."""
    out = []
    try:
        with open(journal_path(root, task), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                # `assume` — a BORROWED word (autonomy): stands in for his word over the
                # amended picture exactly as `accepted` does; the debt is tracked elsewhere.
                if rec.get("type") in ("amend", "accepted", "assume"):
                    out.append(rec)
    except OSError:
        pass
    return out


def pending_word(root, task):
    """Amendments made AFTER the owner's last recorded word — the picture he said «да» over
    has changed since. Empty when nothing is pending."""
    pend = []
    for rec in amend_events(root, task):
        if rec.get("type") in ("accepted", "assume"):
            pend = []
        else:
            pend.append(rec)
    return pend


def word_given_on(root, task, phase):
    """Has the owner's word been recorded ON `phase` — after the task last ENTERED it?

    The third big stop of the sync axis (acceptance) asks for a word over the RESULT; the
    file acceptance.md alone cannot tell, because `el accept` on plan writes the same file —
    and the plan-time «да» passed for acceptance (found on the live test, 2026-08-21). So the
    journal answers: an `accepted` event carrying this phase, later than the last
    `advance`/`reroute` into it. Going back and coming again asks for a fresh word."""
    said = False
    try:
        with open(journal_path(root, task), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                kind = rec.get("type")
                if kind in ("advance", "reroute"):
                    tail = (rec.get("text") or "").rsplit("→", 1)[-1].strip()
                    if tail == phase:
                        said = False
                elif kind == "accepted" and rec.get("phase") == phase and (
                        phase != "validate" or rec.get("for") in (None, "", "final")):
                    # On validate only the FINAL word counts: «готово» over one observed
                    # scenario (--for observation:S2.4) is not acceptance of the system.
                    said = True
    except OSError:
        pass
    return said


def acked(root, task):
    """What the owner or the agent chose to leave as is — `el ack` events — so «за спиной»
    stops repeating it (owner, 2026-08-22: a warning resolved once must not nag forever)."""
    out = set()
    try:
        with open(journal_path(root, task), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") == "ack" and rec.get("what"):
                    out.add(rec["what"])
    except OSError:
        pass
    return out


def pending_line(pend):
    tags = ", ".join((f"{e.get('part', '?')}·поздний след" if e.get("late")
                      else f"п{e.get('n', '?')}·{e.get('part', '?')}") for e in pend)
    return f"{len(pend)} ({tags})"


def amend_doc(root, task, rel, title, args):
    """Append an amendment to a prose document of a phase the task has LEFT.

    Returns (n, phase) when written, None when refused (the reason is printed). The guard is
    the whole rule: a correction must say WHY (--why) and on what grounds (--ref …), and it
    never overwrites — --replace is refused once the phase is behind us."""
    why = (getattr(args, "why", None) or "").strip()
    path = os.path.join(root, task, rel)
    phase = task_meta(root, task).get("phase", "context")
    refs = list(getattr(args, "ref", None) or [])
    if not os.path.exists(path):
        # A LATE TRACE (owner, 2026-08-22): the document of a passed phase that never existed
        # — a beat added to the protocol after this task passed the phase, or one skipped. No
        # --why to demand, the reason is the one; it is written as a first fill, stamped with
        # the phase it was written on. The picture he said «да» over has GROWN, so the word is
        # asked again, exactly like after an amendment.
        own = doc_phase(rel) or "?"
        body = (f"# {title}\n\n_поздний след: записан на фазе {phase}, после выхода из {own} — "
                f"такт появился в протоколе позже или был пропущен_\n\n{args.text.strip()}\n")
        if refs:
            body += "".join(f"- основание: `{r}`\n" for r in refs)
        write(path, body)
        journal(root, task, "amend", f"{rel} поздний след: {args.text.strip()[:80]}",
                {"part": rel.split("/")[-1].rsplit(".", 1)[0], "late": True,
                 "why": "такт появился после прохода фазы", "refs": refs, "phase": phase})
        touch(root, task)
        print(f"поздний след  {rel} · {phase}")
        print('слово     картина дополнена после его слова — предъяви и запиши ответ: '
              'el accept "<его слова>"')
        return 0, phase
    if getattr(args, "replace", False):
        print("поправка не перетирает: после выхода из фазы --replace запрещён — допиши "
              "поправкой, старое остаётся", file=sys.stderr)
        return None
    if not why:
        print(f"после выхода из фазы запись в {rel} — ПОПРАВКА: скажи --why и дай --ref "
              "<основание> (развилка f1 · research/code.md · evidence/… · его слова)",
              file=sys.stderr)
        return None
    # ДОПОЛНЯЕТ ИЛИ ОТМЕНЯЕТ (his decision 2026-08-24). Two kinds of finding, and only one
    # of them is the agent's to absorb:
    #   дополняет   new knowledge that stands NEXT TO what he said — write it and work on;
    #   отменяет    knowledge that makes what he said untrue («делаем для iOS» → «на iOS
    #               нельзя»). Autonomy grants the right to decide the UNKNOWN; it never
    #               grants the right to cancel what he has already said. So this one stops
    #               the work at once — not at a convenient moment, immediately.
    own_phase = doc_phase(rel) or ""
    said = word_given_on(root, task, own_phase) if own_phase else False
    adds = bool(getattr(args, "adds", False))
    contra = (getattr(args, "contradicts", None) or "").strip()
    if said and not adds and not contra:
        print(f"над этим документом стоит его слово — скажи, что делает поправка:",
              file=sys.stderr)
        print("  --adds                        дополняет: новое встаёт РЯДОМ с тем, что он "
              "сказал", file=sys.stderr)
        print('  --contradicts "<что именно>"  отменяет: сказанное им перестало быть правдой',
              file=sys.stderr)
        print("  различие не формальность: дополнение агент вносит сам, отмена — только "
              "через него.", file=sys.stderr)
        return None
    body = open(path, encoding="utf-8").read()
    n = next_no(body)
    write(path, body.rstrip("\n") + amend_block(n, phase, why, refs, args.text))
    journal(root, task, "amend", f"{rel} п{n}: {args.text.strip()[:80]}",
            {"part": rel.split("/")[-1].rsplit(".", 1)[0], "n": n, "why": why, "refs": refs,
             "phase": phase})
    touch(root, task)
    if contra:
        # The record first — the halt must never be the only trace of a contradiction.
        journal(root, task, "contradiction", f"{rel} п{n}: {contra[:160]}",
                {"part": rel.split("/")[-1].rsplit(".", 1)[0], "n": n, "phase": phase})
        from . import autonomy
        st = autonomy.state(root, task)
        print(f"поправка  п{n} · {rel} · {phase}")
        print(f"ОТМЕНЯЕТ  {contra[:150]}")
        if st and st["active"]:
            journal(root, task, "halt",
                    f"найденное отменяет сказанное тобой: {contra[:150]} — работа "
                    f"остановлена до твоего слова", {"phase": phase, "by": "contradiction"})
            print("СТОП      автономия остановлена: занимать можно неизвестное, "
                  "но не отменять уже сказанное тобой.")
        print("нужно     покажи ему и запиши ответ: el accept \"<его слова>\"")
        print("          после слова: продолжай (el grant \"<его слова>\") — или "
              "el back <фаза> --why \"…\", если меняется маршрут")
        touch(root, task)
        return n, phase
    print(f"поправка  п{n} · {rel} · {phase}")
    print('слово     картина правилась после его слова — предъяви и запиши ответ: '
          'el accept "<его слова>"')
    return n, phase
