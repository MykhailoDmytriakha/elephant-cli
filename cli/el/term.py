"""Terminal typography — the three ways text is shaped for the agent's eye.

wrap: long protocol lines at a fixed width under a hanging indent · human_when: a
stamp as «сегодня 14:03» · bar: a progress bar · emit: a screen under the tool-call budget. Nothing else belongs here — a helper
that is not about how text LOOKS in the terminal belongs to its own layer.
"""
import os, sys
from datetime import datetime

# One screen = one tool call. Claude Code hands the agent at most ~30 000 characters of a
# command's output (measured 2026-08-22: 25K arrives whole, 33K arrives as a 2 KB preview
# plus a file path); other harnesses may cut lower. So every reading screen aims under this
# budget, and a screen that cannot fit says so IN ITS HEAD — the head survives a cut, the
# tail does not — and names the parts it can be read by.
# One screen — what a single tool call carries to the agent (Claude Code ≈ 30 000 characters).
# ELEPHANT_SCREEN=<chars> for a harness with a smaller window (feedback 2026-08-26).
try:
    SCREEN_BUDGET = int(os.environ.get("ELEPHANT_SCREEN", "") or 24000)
except ValueError:
    SCREEN_BUDGET = 24000


def emit(text, parts=None, budget=SCREEN_BUDGET):
    """Print a screen; if it is longer than one tool call can carry, put the map of parts first."""
    n = len(text)
    if n > budget:
        lines = text.count("\n") + 1
        print(f"⚠ вывод длинный: {n} символов · {lines} строк — один вызов команды может его "
              f"обрезать (Claude Code ≈ 30 000). Голова дошла, хвост — не факт.")
        if parts:
            print(f"  по частям: {parts}")
        print()
    if text:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def wrap(text, indent="         ", width=86):
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line); line = word
        else:
            line = f"{line} {word}".strip()
    if line: out.append(line)
    return ("\n" + indent).join(out)


def human_when(iso):
    """«сегодня 14:03» instead of «2026-08-20T14:03» — the reader is a person, not a parser."""
    if not iso:
        return ""
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:16]
    today = datetime.now(when.tzinfo).date()
    delta = (today - when.date()).days
    stamp = when.strftime("%H:%M")
    if delta == 0:
        return f"сегодня {stamp}"
    if delta == 1:
        return f"вчера {stamp}"
    if delta < 7:
        return f"{delta} дн. назад"
    return when.strftime("%d.%m")


def bar(done, total, width=10):
    """A filled bar reads at a glance; «1/11 следов» has to be decoded first."""
    if not total:
        return "─" * width
    filled = round(width * done / total)
    return "█" * filled + "·" * (width - filled)
