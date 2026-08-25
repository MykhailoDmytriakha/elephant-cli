"""The flight recorder — every `el` call, one line, no judgement.

The owner's decision (2026-08-24): the only witness of what an agent REALLY does with the
tool is the tool itself — and only inside its own calls. Everything between calls is out of
sight; the tool does not guess at it. So this file writes facts and nothing else: what was
called, what came back, how long it took. It is read by the meta-session, a week at a time,
next to the feedback pool — the reviews say what the agent THOUGHT, the recorder says what
happened. No episode detection, no «expected next move» — that would be interpretation of
things the recorder cannot see.

One file per storage: <storage>/metadata/calls.jsonl — service data like the page data
next to it (delete it, nothing is lost but the record). One line per call:
  {"ts", "task", "argv": [...], "rc", "out": lines, "chars", "err": lines, "ms"}
and, whenever the tool's own version changed since the last call on this storage, one
marker line before it:
  {"type": "version", "ts", "el": "<git short hash>", "python", "platform"}
— so a week of calls reads as «this ran on 228725c, then on a1b2c3d from here on»; the
version is not repeated on every line.
"""
import json, os, platform, sys, time
from datetime import datetime, timezone
from .state import SKILL_ROOT, current_task, find_root, now_iso

CALLS_FILE = "calls.jsonl"
VERSION_FILE = "calls.version"
ARG_MAX = 80          # an argument longer than this is the owner's words, not a command


def version():
    """The clone's git short hash, read from .git without a subprocess; '?' outside git."""
    git = os.path.join(SKILL_ROOT, ".git")
    try:
        head = open(os.path.join(git, "HEAD"), encoding="utf-8").read().strip()
        if not head.startswith("ref: "):
            return head[:7]
        ref = head[5:]
        loose = os.path.join(git, *ref.split("/"))
        if os.path.exists(loose):
            return open(loose, encoding="utf-8").read().strip()[:7]
        packed = os.path.join(git, "packed-refs")
        if os.path.exists(packed):
            for line in open(packed, encoding="utf-8"):
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0][:7]
    except OSError:
        pass
    return "?"


RETURN_GAP = 30 * 60      # seconds of silence after which the next call is a RETURN


def session_start(root, gap=RETURN_GAP):
    """(iso, pause_seconds) — when the current run of calls began, and how long the tool had
    been silent before it; (None, 0) with no recorder or no pause of `gap` seconds in it.

    The one fact the recorder can honestly add (2026-08-25): calls come in runs, and a run
    that starts after a long silence is an agent coming BACK. The line for the current call
    is not written yet, so the newest line is the previous call: silent for longer than the
    gap → this call opens the run (start = now); otherwise walk back to the gap."""
    path = os.path.join(root, "metadata", CALLS_FILE)
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return None, 0
    stamps = []
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") == "version" or not rec.get("ts"):
            continue
        stamps.append(rec["ts"])
        if len(stamps) > 500:
            break
    if not stamps:
        return None, 0
    try:
        newer = datetime.now(timezone.utc)
        for i, s in enumerate(stamps):
            t = datetime.fromisoformat(s)
            pause = (newer - t).total_seconds()
            if pause >= gap:
                return (now_iso() if i == 0 else stamps[i - 1]), int(pause)
            newer = t
    except ValueError:
        return None, 0
    return None, 0


class Counter:
    """A stream that counts what passes through it — the size of the screen the agent got."""

    def __init__(self, stream):
        self.stream, self.chars, self.lines = stream, 0, 0

    def write(self, s):
        self.chars += len(s)
        self.lines += s.count("\n")
        return self.stream.write(s)

    def flush(self):
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def _task_of(root, argv):
    """The task the call was about: `--task X` when given, else the one in hand."""
    for i, a in enumerate(argv):
        if a == "--task" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--task="):
            return a[7:]
    try:
        return current_task(root)
    except Exception:
        return None


def record(argv, rc, out, err, ms):
    """Append one line for this call — and a version marker first when the tool changed.

    Silent on every failure: the recorder must never turn a working command into a broken
    one. Off when ELEPHANT_CALLS=off. Nothing is written outside a storage — there is no
    place for it."""
    if os.environ.get("ELEPHANT_CALLS", "").lower() in ("off", "0", "no"):
        return
    try:
        root = find_root()
        if not root:
            return
        meta_dir = os.path.join(root, "metadata")
        os.makedirs(meta_dir, exist_ok=True)
        ver = version()
        vpath = os.path.join(meta_dir, VERSION_FILE)
        last = open(vpath, encoding="utf-8").read().strip() if os.path.exists(vpath) else ""
        lines = []
        if ver != last:
            lines.append({"type": "version", "ts": now_iso(), "el": ver,
                          "python": platform.python_version(), "platform": platform.system()})
            with open(vpath, "w", encoding="utf-8") as fh:
                fh.write(ver)
        lines.append({"ts": now_iso(), "task": _task_of(root, argv),
                      "argv": [a if len(a) <= ARG_MAX else a[:ARG_MAX] + "…" for a in argv],
                      "rc": rc, "out": out.lines, "chars": out.chars, "err": err.lines,
                      "ms": ms})
        with open(os.path.join(meta_dir, CALLS_FILE), "a", encoding="utf-8") as fh:
            for rec in lines:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def run_recorded(fn, argv):
    """Run the CLI body under the recorder: count the screen, time it, catch argparse's
    exit (rc 2 — «did not understand the call» — is exactly the kind of call worth keeping),
    and write the line. The original streams come back whatever happens."""
    out, err = Counter(sys.stdout), Counter(sys.stderr)
    sys.stdout, sys.stderr = out, err
    t0 = time.monotonic()
    try:
        try:
            rc = fn(argv)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        ms = int((time.monotonic() - t0) * 1000)
    finally:
        try:
            out.flush(); err.flush()
        except Exception:
            pass
        sys.stdout, sys.stderr = out.stream, err.stream
    record(argv, rc if rc is not None else 0, out, err, ms)
    return rc
