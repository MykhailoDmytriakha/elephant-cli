"""Hints — the tool's fourth voice (the owner's word, 2026-09-16).

A refusal says «not like this, here is how»; Order says «out of place, here is the command»; a warning says
«written, but look». None of them says «fine — and here is how it gets excellent». A hint does. It is not a
tip of the day: it is DERIVED from the state of the case (an item without `why:`, a proof that is only the
owner's word, a planned phase nobody parked anything under), it names one command with the real number in
it, it points at the help topic where the craft lives, and it disappears once the agent acted on it. One per
output, the last line, on stdout. A reminder multiplied by a bad record gives a bad record more often (the
owner, 2026-09-01) — a hint is not a reminder, it is the tool noticing something in the case before the
agent did. `EL_HINTS=0` silences them for an owner who knows the tool.

Each rule was born from an observed agent behaviour (CLAUDE.md, «what agents ask for»); a hint nobody acts on
is measured in the live trial and removed."""
import os
from pathlib import Path
from typing import List, Optional

from . import grammar


def enabled() -> bool:
    return os.environ.get("EL_HINTS", "1") != "0"


def attach(out, moment: str, **ctx) -> None:
    """Append the one hint for this moment as the last line of the command's output, if any applies."""
    if not enabled():
        return
    text = pick(moment, **ctx)
    if text:
        out.say(f"hint: {text}")


def pick(moment: str, **ctx) -> Optional[str]:
    fn = {"todo_add": _todo_add, "todo_expect": _todo_expect, "todo_done": _todo_done, "log": _log, "phase_open": _phase_open,
          "phase_close": _phase_close, "case_new": _case_new, "entry": _entry}.get(moment)
    return fn(**ctx) if fn else None


# ---- in progress ----------------------------------------------------------------------------------
def _todo_add(item: grammar.Item, **_) -> Optional[str]:
    ref = f"{item.n}.{item.m}"
    if not item.why:
        return f"the owner will read {ref} without you — say what it is for: el todo why {ref} \"…\" — el help todo"
    if not item.expect:
        return (f"what will prove {ref} done? write it before the work, not after: "
                f"el todo expect {ref} \"… [run: …] [file: …] [owner]\" — el help practice")
    return None


def _todo_expect(item: grammar.Item, phase: grammar.Phase, **_) -> Optional[str]:
    """Items are cut by what they leave behind (the owner's word, 2026-09-16): a placeholder that names the same
    artifact another item promised, or already left, says the two are one item — steps go to its notes."""
    mine = {(k, w.strip().lower()) for k, w in grammar.expected_kinds(item.expect) if k in ("file", "ref") and w.strip()}
    if not mine:
        return None
    for other in phase.items:
        if other is item:
            continue
        theirs = {(k, w.strip().lower()) for k, w in grammar.expected_kinds(other.expect) if w.strip()}
        theirs |= {(k, _link_path(pr).lower()) for k, pr in other.evidence if k in ("file", "ref")}
        shared = mine & theirs
        if shared:
            k, w = sorted(shared)[0]
            ref, oref = f"{item.n}.{item.m}", f"{other.n}.{other.m}"
            return (f"[{k}: {w}] is also the artifact of {oref} — one artifact, one item: is {ref} a step of {oref}? "
                    f"then el todo note {oref} \"…\" and el todo cancel {ref} \"step of {oref}\"; or name what {ref} leaves of its own — el help practice")
    return None


def _link_path(proof: str) -> str:
    import re
    m = re.fullmatch(r"\[[^\]]*\]\(([^)]+)\)", proof)
    return m.group(1) if m else proof


def _todo_done(items: List[grammar.Item], proofs, **_) -> Optional[str]:
    kinds = {k for k, _ in proofs}
    if kinds == {"owner"}:
        ref = f"{items[0].n}.{items[0].m}" if len(items) == 1 else "N.M"
        return (f"owner is the word that counts, and the hardest to check later — a file or a run behind it? "
                f"a second done adds it: el todo done {ref} file:… \"…\" — el help evidence")
    return None


def _log(typ: str, project: Optional[Path] = None, **_) -> Optional[str]:
    if typ != "PROBLEM":
        return None
    howto = (project / ".howto") if project else None
    recipes = len(list(howto.glob("*.md"))) if howto and howto.is_dir() else 0
    if recipes >= 3:
        return None  # the habit is there
    return ("will it bite again? a recipe .howto/<verb>.md whose first line is `when: <the error words>` is found by "
            "grep next time — el help where")


# ---- opening and closing --------------------------------------------------------------------------
def _phase_open(rel: str, n: int = 0, promised=(), covered=(), **_) -> Optional[str]:
    if promised and len(covered) < len(promised):  # the goal promises proofs no item works towards yet
        gap = [sl for sl in promised if sl not in covered]
        return (f"the goal promises {len(promised)} proof(s) and {len(covered)} have an item — name each criterion as an item "
                f"with the same slot: el todo add {n} \"…\" --expect \"{gap[0]}\" (a phase is proved by its items) — el help phases")
    if not promised:
        return (f"what must be true when phase {n} closes? promise it in the goal, one proof per criterion — "
                f"[run: …] [file: …] [owner] — and name each as an item; a baseline is not the goal — el help practice")
    return (f"{rel} is yours — dead ends, measurements, drafts go there; the Digest at close is rendered from what "
            f"you log as you go (PROBLEM · DECISION · RESULT) — el help phases")


def _phase_close(n: int, events, **_) -> Optional[str]:
    problems = sum(1 for ev in events if ev.type == "PROBLEM")
    decisions = sum(1 for ev in events if ev.type == "DECISION" and not ev.text.startswith(("reflect:", "align:")))
    if problems == 0 and decisions == 0:
        return (f"the Digest of phase {n} holds no PROBLEM and no DECISION — nothing bit, nothing was chosen? "
                f"next phase, log them as they happen — el help practice")
    return None


def _case_new(root: Optional[Path] = None, **_) -> Optional[str]:
    if root is not None:
        from . import store
        cards = store.people_cards(root)
        if cards:  # the more derived hint wins: this workspace already knows its people
            return (f"{len(cards)} people card(s) in .cases/people/ — link the ones this case deals with from Links "
                    f"or a note: [name](../people/<name>.md) — el help people")
    return ("phases you already see? name them now, decompose when you get there: "
            "el phase plan 2 \"Name\" --goal \"…\" — el help phases")


# ---- entry ------------------------------------------------------------------------------------------
def _entry(case: Path, todo: grammar.Todo, journal: Optional[grammar.Journal], phase_file_exists, repeats=(), **_) -> Optional[str]:
    """One hint per entry, chosen among the applicable ones by the number of journal events: every write moves
    the choice, so a long session sees them all — deterministic, no state file."""
    cands: List[str] = []
    for k, line, card in repeats:  # a person described again in Links while a card exists (L10)
        cands.append(f"Links line {k} repeats {card} — link the card instead: "
                     f"el readme edit links {k} \"[name](../{card}) — what this case needs from them\" — el help people")
        break
    open_items = [it for p in todo.phases if not p.done for it in p.items]
    done_items = [it for it in open_items if it.done]
    todo_items = [it for it in open_items if not it.done]
    for p in sorted(todo.phases, key=lambda x: x.n):
        if not p.done and not phase_file_exists(p) and not p.items and not p.notes:
            cands.append(f"an idea for phase {p.n} {p.name}? park it where it will be needed: "
                         f"el phase note {p.n} \"…\" · el todo add {p.n} \"…\" — it surfaces when the phase opens — el help phases")
            break
    if len(todo_items) >= 2 and not any(it.why or it.notes or it.expect for it in todo_items):
        cands.append("the owner reads TODO without you — items carry pockets: why · note · expect, written in the owner's words — el help todo")
    if len(todo_items) >= 2 and all(it.why for it in todo_items) and not any(it.expect for it in todo_items):
        cands.append("what will prove these items done? say it before the work: el todo expect N.M \"… [run: …] [file: …]\" — el help practice")
    if len(done_items) >= 2 and all(it.evidence and all(k == "owner" for k, _ in it.evidence) for it in done_items):
        if any((case / d).is_dir() for d in ("evidence", "docs", "testing", "logs")):
            cands.append("every proof so far is the owner's word — a file or a run stands behind some of them? "
                         "el todo done N.M file:… \"…\" adds it — el help evidence")
    untyped = [it for it in done_items if not it.evidence]
    if untyped:
        it = untyped[0]
        cands.append(f"{len(untyped)} older tick(s) carry no kind of evidence — attach one when you know it: "
                     f"el todo done {it.n}.{it.m} file:… \"…\" — el help evidence")
    # events, not entries: the events of one minute share one entry header, and the choice must move with
    # every write — a long session then sees every applicable hint, without a state file
    events = sum(len(e.events) for e in journal.entries) if journal is not None else 0
    if not cands and events < 8:  # the generic onboarding hint only when nothing specific is there to fix
        cands.append("how strong agents lead a case, by moment — weak against strong, side by side: el help practice")
    if not cands:
        return None
    return cands[events % len(cands)]
