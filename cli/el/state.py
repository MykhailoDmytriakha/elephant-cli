"""Files on disk and what they mean — the floor everything stands on.

Where the storage is (by marker, walking up), what a task is (a folder with a date in its
name), the journal (append-only JSON Lines, the single written truth), the task's card
DERIVED from the journal, which task is IN HAND (the latest `hold` event — or none: idle),
the dirty set that tells the views what to refresh, and the tool's own inbox (feedback/ in
the skill). Nothing here prints a phase or judges a gate.
"""
import json, os, re, sys, time
from datetime import datetime, timezone
from .protocol import CONTEXT_FILES, MODES, PHASE_MAP, PHASES, required_in


# The marker is an EMPTY hidden file with no extension — a sign on the door, nothing opens
# it. The storage folder is found by this file, never by the folder's name (guide §3).
MARKER = ".elephant"


STORAGE_DIR = ".projects"


# Where the code itself lives — needed by two callers only: `el status` prints the
# entry script, and the views take the page templates from the skill's html/ folder.
# Computed from THIS file: realpath survives the ~/.local/bin/el symlink.
CLI_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))   # …/cli
CLI_ENTRY = os.path.join(CLI_DIR, "el.py")
SKILL_ROOT = os.path.dirname(CLI_DIR)


# Project markers, in order. `.git` is deliberately LAST: in a monorepo it points at the
# repository boundary, while the work happens in one project inside it, and the bookkeeping
# belongs to that project — not to a root nobody will look in.
PROJECT_MARKERS = ["CLAUDE.md", "package.json", "Package.swift", "pyproject.toml",
                   "Cargo.toml", "go.mod", "AGENTS.md"]


# A task folder is one whose NAME says so: `2026-08-20-share-songs`. The date prefix is
# already how ids are minted, so it costs nothing and needs no blacklist of service names —
# anything without a date is simply not a task. This replaced a `projects/` level that
# separated five folders from one file and nothing else (owner, 2026-08-20).
# The separator is a hyphen since 2026-08-20 (guide §3); the underscore is still accepted
# so folders created before that date keep working.
TASK_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}[-_]")


# `hold` is reserved too: it is what moves the hand (current_task), so it is written only
# by the commands that TAKE a task — use · new/boot · reopen — never by `el log`.
# `grant` · `halt` · `assume` are the autonomy layer (el grant · el halt · --assumed); they
# change how gates read, so `el log` may not write them either.
# `owe` · `owe-holds` · `owe-paid` · `owe-drop` are the owner's debt (el owe): they hold
# nodes and gates, so they are written only by that command.
RESERVED_EVENTS = ("created", "advance", "reroute", "done", "reopened", "depends", "hold",
                   "grant", "halt", "assume", "owe", "owe-holds", "owe-paid", "owe-drop")


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def norm_id(text):
    """Normalise a given name into a path segment. Does NOT invent one.

    Inventing a short meaningful name is the agent's job — the CLI does not think (§0.2),
    and transliterating a sentence produced unreadable ids."""
    s = re.sub(r"-+", "-", "".join(c if (c.isalnum() and c.isascii()) else "-"
                                   for c in text.lower())).strip("-")
    # Up to FIVE words (owner, 2026-08-18): one or two were too terse to carry meaning once
    # several tasks of the same kind pile up; more than five and the folder name stops being
    # readable at a glance. The DATE PREFIX does not count: `2026-08-22-speed-after-ensemble`
    # used to lose its tail because the date ate three of the five slots — silently (an
    # agent's review from the pool, 2026-08-22).
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.*)$", s)
    date, rest = (m.group(1) + "-", m.group(2)) if m else ("", s)
    return (date + "-".join(rest.split("-")[:5])[:48]).rstrip("-")


def id_words_dropped(text):
    """The words `norm_id` would drop from `text` past the five-word cap — so the caller can
    say «id урезан» out loud instead of cutting in silence."""
    s = re.sub(r"-+", "-", "".join(c if (c.isalnum() and c.isascii()) else "-"
                                   for c in text.lower())).strip("-")
    m = re.match(r"^\d{4}-\d{2}-\d{2}-(.*)$", s)
    rest = m.group(1) if m else s
    return rest.split("-")[5:]


# ── frontmatter ───────────────────────────────────────────────────────────────

def fm_read(path):
    try:
        raw = open(path, encoding="utf-8").read()
    except OSError:
        return {}, ""
    if not raw.startswith("---"):
        return {}, raw
    _, _, rest = raw.partition("---")
    head, sep, body = rest.partition("\n---")
    meta = {}
    for line in head.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, body.lstrip("\n") if sep else ""


def fm_write(path, meta, body):
    head = "\n".join(f"{k}: {v}" for k, v in meta.items())
    write(path, f"---\n{head}\n---\n\n{body.strip()}\n")


# ── file primitives ───────────────────────────────────────────────────────────

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def journal(root, task, event, text, extra=None):
    """Three fields, none spare. No `actor` — only the agent writes so far. No `task` —
    the journal LIVES inside the task folder, so the folder name already answers that.
    One journal per task: a second one at folder level held a single record."""
    rec = {"ts": now_iso(), "type": event, "text": text}
    if extra:
        rec.update(extra)
    path = os.path.join(root, task, "journal.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    _META_CACHE.pop((root, task), None)
    mark_render(root, task)


# ── lookup: same logic as detect.sh — by marker, walking up the tree ──────────

def find_root(start=None):
    d = os.path.abspath(start or os.getcwd())
    env = os.environ.get("ELEPHANT_DIR")
    if env and os.path.isfile(os.path.join(env, MARKER)):
        return os.path.abspath(env)
    while True:
        try:
            subs = [os.path.join(d, n) for n in os.listdir(d)]
        except OSError:
            subs = []
        hits = [s for s in subs if os.path.isdir(s)
                and os.path.basename(s) not in (".git", "node_modules", ".Trash")
                and os.path.isfile(os.path.join(s, MARKER))]
        if hits:
            return sorted(hits)[0] if len(hits) == 1 else None
        if os.path.isdir(os.path.join(d, ".git")) or d in (os.path.expanduser("~"), "/"):
            return None
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def project_root(start=None):
    """Root of the project we were launched in: nearest project marker up the tree,
    starting with the working directory itself; the repository boundary is a fallback."""
    cwd = os.path.abspath(start or os.getcwd())
    d = cwd
    while True:
        if any(os.path.isfile(os.path.join(d, m)) for m in PROJECT_MARKERS):
            return d
        parent = os.path.dirname(d)
        if parent == d or d == os.path.expanduser("~"):
            break
        d = parent
    d = cwd
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d or d == os.path.expanduser("~"):
            return cwd
        d = parent


def tasks_of(root):
    if not os.path.isdir(root):
        return []
    try:
        names = os.listdir(root)
    except OSError:  # unreadable dir (e.g. macOS-protected) is the same as empty
        return []
    return sorted(n for n in names
                  if TASK_DIR.match(n) and os.path.isdir(os.path.join(root, n)))


def resolve_task(root, text):
    """Find a task by whatever the caller typed.

    `norm_id` exists to MINT an id from a description, and it turns every non-alphanumeric
    character into a hyphen — including the underscore that separates the date prefix. Run it
    over an id that already exists and `2026-08-19_el-navigator` becomes `2026-08-19-el-navigator`,
    which matches nothing. So: take the string as given first, then the minted form, then a
    unique tail match — pasting a name the CLI itself just printed must always work."""
    if not text:
        return None
    known = tasks_of(root)
    if text in known:
        return text
    minted = norm_id(text)
    if minted in known:
        return minted
    hits = [t for t in known
            if any(t.endswith(sep + n) for sep in ("-", "_") for n in (text, minted))]
    return hits[0] if len(hits) == 1 else None


def journal_path(root, task):
    return os.path.join(root, task, "journal.jsonl")


# task_meta walks one journal per call, so the result is cached per (root, task) and keyed
# by the journal's mtime — a second call inside the same command costs nothing, a write
# anywhere invalidates naturally.
_META_CACHE = {}


def task_meta(root, task):
    """The task's card, DERIVED — never stored (owner, 2026-08-20: "фаза — это вычислимое
    поле"). There is no project.md: the journal is the single written truth, and the card
    is computed from it —
      name        the `created` event (the first line)
      phase       the last `advance`/`reroute` event, else context
      status      the last of `done`/`reopened`: done → its outcome, reopened → active
      result      the `done` event's text
      depends_on  the `depends` event
      held_at     the last `hold` event — when this task was last TAKEN IN HAND
      grant       the last `grant` event (his words that opened autonomy) — or absent
      halt        the last `halt` event AFTER that grant — autonomy stopped here — or absent
      assumes     every `assume` event (borrowed words), in order
      words       every `accepted` event (his real words), in order — debt is computed from
                  these two lists (autonomy.debt)
      owes        every `owe` · `owe-holds` · `owe-paid` · `owe-drop` event, in order — the
                  owner's debt is computed from them (owe.ledger)
      updated_at  the journal file's mtime — ORDERING tasks needs no read at all
    """
    jp = journal_path(root, task)
    try:
        mtime = os.path.getmtime(jp)
    except OSError:
        return {}
    hit = _META_CACHE.get((root, task))
    if hit and hit[0] == mtime:
        return hit[1]
    # Trace renames migrate SILENTLY here — every command passes through task_meta, so a
    # live project keeps working the moment a trace file gets a better name.
    # 2026-08-21: scope.md → 5w-h.md ("файл в реальности и есть 5W+1H").
    for old, new in (("context/scope.md", "context/5w-h.md"),):
        op, np_ = os.path.join(root, task, old), os.path.join(root, task, new)
        if os.path.isfile(op) and not os.path.exists(np_):
            try:
                os.rename(op, np_)
            except OSError:
                pass
    # 2026-08-21: sources moved OUT of context/ into research/ — any .md in context/ that
    # is not a step's own output IS a source file and rides over.
    cdir_m = os.path.join(root, task, "context")
    if os.path.isdir(cdir_m):
        # origin.md is `el spawn`'s note of where the task came from — a context document,
        # not a source; without this line it rode over to research/ (found by the
        # differential test, 2026-08-21).
        own = {os.path.basename(rel) for rel in CONTEXT_FILES.values()} | {
            "human.md", "task.draft.md", "task.md", "acceptance.md", "scope.md", "origin.md"}
        for fn in os.listdir(cdir_m):
            if fn.endswith(".md") and fn not in own:
                try:
                    dst = os.path.join(root, task, "research", fn)
                    if not os.path.exists(dst):
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        os.rename(os.path.join(cdir_m, fn), dst)
                except OSError:
                    pass
    meta = {"name": task, "phase": "context", "status": "active", "_mtime": mtime, "mode": "soft",
            "assumes": [], "words": [], "owes": [], "events": 0,
            "updated_at": datetime.fromtimestamp(mtime, timezone.utc).astimezone()
                                  .isoformat(timespec="milliseconds")}
    try:
        with open(jp, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                kind = rec.get("type")
                meta["events"] += 1
                if kind == "created" and rec.get("text"):
                    meta["name"] = rec["text"]
                elif kind in ("advance", "reroute"):
                    tail = (rec.get("text") or "").rsplit("→", 1)[-1].strip()
                    if tail in PHASES:
                        meta["phase"] = tail
                elif kind == "done":
                    meta["status"] = meta["outcome"] = rec.get("outcome", "closed")
                    meta["result"] = rec.get("text", "")
                    meta["closed_at"] = rec.get("ts", "")
                elif kind == "reopened":
                    meta["status"] = "active"
                    for k in ("outcome", "result", "closed_at"):
                        meta.pop(k, None)
                elif kind == "depends" and rec.get("on"):
                    meta["depends_on"] = rec["on"]
                elif kind == "hold":
                    meta["held_at"] = rec.get("ts", "")
                elif kind == "grant":
                    meta["grant"] = rec
                    meta.pop("halt", None)      # a new grant («продолжай») lifts a halt
                elif kind == "halt" and meta.get("grant"):
                    meta["halt"] = rec
                elif kind == "assume":
                    meta["assumes"].append(rec)
                elif kind == "accepted":
                    meta["words"].append(rec)
                elif kind in ("owe", "owe-holds", "owe-paid", "owe-drop"):
                    meta["owes"].append(rec)
                elif kind == "mode" and rec.get("mode") in MODES:
                    meta["mode"] = rec["mode"]
    except OSError:
        pass
    _META_CACHE[(root, task)] = (mtime, meta)
    return meta


def current_task(root):
    """The task IN HAND — computed, never stored. The hand holds the task whose `hold`
    event is the latest in the whole storage (`el use` · birth by `el new`/`el boot` ·
    `el reopen` write one); when that task is closed, the hand is EMPTY — idle. `el done`
    puts the task down and nothing is picked up in its place (owner, 2026-08-22: «el done
    снимает задачу с руки; el и el status честно говорят, что задачи в руке нет»).

    Until 2026-08-22 «current» was the freshest journal by mtime. Two things were wrong
    with that, both found on live work: any write into ANOTHER task — `el log --task`, a
    spawn's note in the parent — stole the hand, and was held back only by hand-made
    compensations (a `touch` back in spawn, then in log; a third command would forget); and
    after the last open task closed, a CLOSED task was «current» — one `el use` refuses to
    choose. Now nothing but a hold event moves the hand: structural, not disciplinary."""
    best, best_ts = None, ""
    for t in tasks_of(root):
        ts = task_meta(root, t).get("held_at", "")
        if ts > best_ts:
            best, best_ts = t, ts
    if not best:
        return None
    return best if task_meta(root, best).get("status", "active") == "active" else None


def hold(root, tid, why=""):
    """TAKE a task in hand — one `hold` event in its journal; the hand is then computed
    from these events (current_task). Writes nothing when it is already in hand.
    Returns True when the hand moved."""
    if current_task(root) == tid:
        return False
    journal(root, tid, "hold", why or "взята в руку")
    return True


def open_tasks(root):
    """The open tasks, freshest first — what `el use` can take."""
    live = [t for t in tasks_of(root) if task_meta(root, t).get("status", "active") == "active"]
    return sorted(live, key=lambda t: task_meta(root, t).get("_mtime", 0.0), reverse=True)


def pick_task(root, want=None):
    """The task a command acts on: `--task <id>` when given, else the one in hand.
    Prints the refusal itself and returns None — «no task <id>» for a name that matches
    nothing (it used to fall silently onto the task in hand), or the idle notice."""
    if want:
        tid = resolve_task(root, want)
        if not tid:
            print(f"no task {want}", file=sys.stderr)
            print(f"hint     known: {', '.join(tasks_of(root)) or '— none'} · el projects",
                  file=sys.stderr)
        return tid
    tid = current_task(root)
    if not tid:
        no_task(root)
    return tid


def no_task(root):
    """Why there is nothing to act on — the two cases are different and must read
    differently: no tasks at all, or tasks exist and the hand is EMPTY (idle)."""
    live = open_tasks(root)
    if not live:
        print("no tasks" if not tasks_of(root) else "no open tasks — every task is closed",
              file=sys.stderr)
        print('hint     el new "<description>" --id <name> · el reopen <task> --why "…" · el projects',
              file=sys.stderr)
        return
    print(f"в руке нет задачи (idle) · открытых {len(live)}: "
          f"{', '.join(live[:4])}{' …' if len(live) > 4 else ''}", file=sys.stderr)
    print("hint     взять: el use <id> · разово: --task <id> · список: el projects",
          file=sys.stderr)


def touch(root, tid):
    """Bump a task's journal clock — the ORDER of `el projects` (freshest first), nothing
    else; the hand is a hold event, not a timestamp (see current_task). No file is
    rewritten and no field is stored. The stamp is forced strictly ABOVE every other
    task's, because several tasks written inside one command can land on the same tick,
    and then the order flips to whichever sorts higher by name (caught live on three
    `el spawn` calls in a row)."""
    jp = journal_path(root, tid)
    if not os.path.exists(jp):
        os.makedirs(os.path.dirname(jp), exist_ok=True)
        open(jp, "a", encoding="utf-8").close()
    top = 0.0
    for t in tasks_of(root):
        if t != tid:
            try:
                top = max(top, os.path.getmtime(journal_path(root, t)))
            except OSError:
                pass
    stamp = max(time.time(), top + 0.000001)
    os.utime(jp, (stamp, stamp))
    _META_CACHE.pop((root, tid), None)
    mark_render(root, tid)


def task_state(tdir):
    """Which of the three states the task is in — read from files, never from a flag."""
    c = os.path.join(tdir, "context")
    has = lambda n: os.path.exists(os.path.join(c, n))
    if has("summary.md"):
        return "summary", "context folded into one read"
    if has("task.clarified.md"):
        return "clarified", "questions answered"
    if (os.path.exists(os.path.join(tdir, "init", "request.md"))
            or has("task.draft.md") or has("task.md")):
        return "draft", "as it arrived, not clarified yet"
    return "none", "nothing written down yet"


def phase_no(name):
    return PHASES.index(name) + 1 if name in PHASES else 0


def task_mode(tdir):
    """The task's mode — light · soft · strict — derived from its journal (default soft)."""
    root, task = os.path.split(os.path.normpath(tdir))
    return task_meta(root, task).get("mode", "soft") if task else "soft"


def phase_state(tdir, phase, mode=None):
    """What the phase has and what it still misses — by files on disk, never by marks.
    `required` follows the task's MODE: a trace is required when its threshold is at or
    below the mode (light ≤ soft ≤ strict)."""
    mode = mode or task_mode(tdir)
    spec = PHASE_MAP.get(phase, {})
    have, missing = [], []
    for rel, what, minmode in spec.get("artifacts", []):
        path = os.path.join(tdir, rel)
        ok = (os.path.isdir(path) and os.listdir(path)) if rel.endswith("/") \
            else os.path.exists(path)
        (have if ok else missing).append((rel, what, required_in(minmode, mode)))
    return have, missing


def require_root():
    root = find_root()
    if not root:
        print("Elephant is not set up here.", file=sys.stderr)
        # The cwd trap (an agent's review, 2026-08-22): the storage is found by walking UP
        # from the working directory, and a harness that resets cwd between calls turns
        # «cd here; el there» into «not set up» — which reads as «nothing exists», not as
        # «you are standing elsewhere». Say where we looked from, and name both ways out.
        print(f"         looked for the `{MARKER}` marker walking UP from: {os.getcwd()}",
              file=sys.stderr)
        print("         if your harness resets cwd between calls: `cd <project> && el …` in ONE",
              file=sys.stderr)
        print("         call, or ELEPHANT_DIR=<path to .projects> el …", file=sys.stderr)
        print('hint     el boot "<description>" --id <name> — sets it up and creates the task',
              file=sys.stderr)
        print("         el help — the whole flow, phase by phase", file=sys.stderr)
    return root


# Which projections need refreshing, per storage root. Writes only MARK; the actual
# rebuild happens ONCE, at the end of main() — a command that logs and touches five times
# still renders once, and only for the projects it touched.
_DIRTY = {}


def mark_render(root, tid=None):
    s = _DIRTY.setdefault(root, set())
    if tid:
        s.add(tid)


def git_dirty(path, exclude=None):
    """Uncommitted changes in the working tree at `path`, or [] when clean / not a repo /
    git absent. A measurement, not a judgement — `el done` refuses over a dirty tree.
    `exclude` drops one directory from the count: the storage itself lives in the tree,
    and its journals change with every command — the bookkeeping must not be able to
    declare ITSELF the uncommitted work."""
    import subprocess
    try:
        out = subprocess.run(["git", "-C", path, "status", "--porcelain"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    lines = [l for l in out.stdout.splitlines() if l.strip()]
    if exclude and not exclude.startswith(".."):
        pref = exclude.rstrip("/") + "/"
        lines = [l for l in lines
                 if not l[3:].strip().strip('"').startswith((pref, exclude))]
    return lines


def lessons_path(root):
    return os.path.join(root, "lessons.md")


def lessons_read(root):
    """The bullet lines of lessons.md, for onboarding."""
    try:
        return [l.strip() for l in open(lessons_path(root), encoding="utf-8")
                if l.strip().startswith("- ")]
    except OSError:
        return []


# ── the tool's own inbox: feedback/ in the SKILL, never in a storage ──────────
# A review of the INSTRUMENT belongs with the instrument (guide §3, the border: the skill
# holds nothing about tasks, a project nothing about the tool). One file per review; the
# folder is the POOL of improvement work for the meta-session: read · fix · delete.
# ELEPHANT_FEEDBACK_DIR redirects it — the differential test must not write into the skill.

def feedback_dir():
    return os.environ.get("ELEPHANT_FEEDBACK_DIR") or os.path.join(SKILL_ROOT, "feedback")


def feedback_ids():
    """The pool, oldest first — file stems, which are the ids."""
    try:
        names = os.listdir(feedback_dir())
    except OSError:
        return []
    return sorted(n[:-3] for n in names if n.endswith(".md") and not n.startswith("."))


def feedback_resolve(text):
    """An id as typed, or its number (3 · 003), or a unique head of the id (ids start with
    the date). Never an arbitrary word: a one-word review must not turn into a lookup."""
    ids = feedback_ids()
    if not text:
        return None
    if text in ids:
        return text
    if text.isdigit():
        num = f"-{int(text):03d}-"
        hits = [i for i in ids if num in i]
    elif text[:1].isdigit():
        hits = [i for i in ids if i.startswith(text)]
    else:
        return None
    return hits[0] if len(hits) == 1 else None


def feedback_looks_like_id(text):
    """Would a lone word be read as a LOOKUP (id or number) rather than review text?"""
    return bool(text) and (text in feedback_ids() or text[:1].isdigit())


# ── brief.md — the one sheet a returning agent reads first ───────────────────────
# Bounded and REWRITTEN, the only such file here: everything else is a chronicle, this is
# the sheet in the hand. Printed by `el`, `el status`; written by `el brief` (the limit is
# checked) or by hand (the limit is reported).

def todo_items(tdir):
    """The parked items of open-questions.md, as `el todo --done N` counts them: N runs over
    the OPEN items in FILE order, closed ones carry no number. One parser for the list, the
    navigator and the closer — an agent closed the wrong item twice in one session because
    --list printed the raw file without numbers and the number had to be computed in the
    head (feedback, 2026-08-24)."""
    path = os.path.join(tdir, "open-questions.md")
    items = []
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return items
    n = 0
    for line in lines:
        s = line.strip()
        if s.startswith("- [ ]") or s.startswith("- [x]"):
            is_open = s.startswith("- [ ]")
            body = s[5:].strip()
            m = re.match(r"\*\*(\S+)\*\*\s*·\s*(.*)$", body)
            phase, text = (m.group(1), m.group(2)) if m else ("", body)
            closed = ""
            if not is_open and "  ← " in text:
                text, closed = text.split("  ← ", 1)
            if is_open:
                n += 1
            items.append({"n": n if is_open else None, "open": is_open, "phase": phase,
                          "text": text.strip(), "closed": closed.strip(), "why": ""})
        elif s.startswith("зачем:") and items:
            items[-1]["why"] = s[6:].strip()
    return items


def todo_line(it, width=90):
    """«3. [ ] [validate] проверить на телефоне» — the number is what --done takes."""
    head = f"{it['n']}. [ ]" if it["open"] else "   [x]"
    ph = f"[{it['phase']}] " if it["phase"] else ""
    tail = f"  ← {it['closed']}" if it["closed"] else ""
    return f"{head} {ph}{it['text'][:width]}{tail}"


def brief_path(tdir):
    return os.path.join(tdir, "brief.md")


def brief_read(tdir):
    try:
        return open(brief_path(tdir), encoding="utf-8").read().rstrip("\n")
    except OSError:
        return ""


# ── the raw request, one line — and «is this the same task again?» ──────────────
# The owner repeats a task in another conversation and the agent, not seeing the first one,
# opens a second (owner, 2026-08-22). Two answers, both cheap: `el projects` shows each
# task's request in HIS words, and `el new` looks for a twin before it creates.

STOPWORDS = {"и", "в", "во", "на", "не", "что", "это", "для", "как", "при", "по", "из", "от", "до",
             "за", "или", "но", "же", "ли", "бы", "то", "так", "там", "тут", "его", "её", "их",
             "мы", "вы", "он", "она", "они", "этот", "эта", "это", "все", "всё", "уже", "ещё",
             "the", "and", "for", "with", "from", "that", "this", "into", "over", "under",
             "задача", "задачу", "проект", "сделать", "нужно", "надо", "хочу", "давай"}


def request_line(tdir, width=110):
    """The first content line of init/request.md — the request in his words, one line."""
    try:
        for l in open(os.path.join(tdir, "init", "request.md"), encoding="utf-8"):
            t = l.strip()
            if not t or t.startswith("#") or t.startswith("_записано") or t.startswith("_"):
                continue
            return t[:width] + ("…" if len(t) > width else "")
    except OSError:
        pass
    return ""


def stems(text):
    """Crude stems for «the same words?»: lowercase words of four letters or more, cut to
    five letters (Russian inflection: модель · модели · моделью → «модел»), stopwords out."""
    out = set()
    for w in re.findall(r"[^\W\d_]+", (text or "").lower()):
        if len(w) >= 4 and w not in STOPWORDS:
            out.add(w[:5])
    return out


def similar_tasks(root, text, limit=3):
    """Open tasks whose name + request share words with `text`: [(score, common, tid, name)],
    best first. score = common / the smaller set — «is one mostly inside the other?»."""
    new = stems(text)
    if not new:
        return []
    hits = []
    for t in tasks_of(root):
        m = task_meta(root, t)
        if m.get("status", "active") != "active":
            continue
        old = stems((m.get("name") or "") + " " + request_line(os.path.join(root, t), 400))
        if not old:
            continue
        common = new & old
        if not common:
            continue
        score = len(common) / max(1, min(len(new), len(old)))
        hits.append((score, len(common), t, m.get("name") or ""))
    hits.sort(key=lambda h: (-h[0], -h[1]))
    return hits[:limit]
