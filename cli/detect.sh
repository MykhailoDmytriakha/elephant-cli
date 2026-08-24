#!/usr/bin/env bash
# detect.sh — THE single probe answering "is there an Elephant here and what can it do".
#
# CONTRACT. The whole lookup mechanism lives HERE. The mode description carries one line,
# "run this and read the output"; no other instructions about finding the folder exist.
#
#   bash <skill root>/cli/detect.sh [path]
#     → key=value block. Output is NEVER empty, exit is ALWAYS 0.
#
# FIELDS
#   dir        absolute path to the storage folder | absent | ambiguous
#   config     path to the .elephant marker, or "—"
#   schema     kept for contract stability, always "—" (the marker is empty by design)
#   cli        the `el` command if it resolves in PATH, otherwise "—"
#              ← "—" means: call el.py by its full path, and tell the owner one line
#                on how to install it. The symlink lives OUTSIDE the skill tree, so a
#                fresh machine gets the skill but not the command.
#   tool       path to el.py when it sits next to this probe, otherwise "—"
#              ← "—" means: no CLI yet, everything by hand. We look AT THE FILE, not into
#                the config, which may claim a tool exists when it does not.
#   projects   absolute path to the folder holding the tasks, or "—"
#              ← that folder IS the Elephant folder: since 2026-08-20 a task lies directly
#                inside it (spec §12, the `projects/` level was removed). Kept under the old
#                field name because callers read the path, not the name.
#   tasks      number of tasks, or 0. A task folder is recognised the way el.py does it —
#                by the DATE PREFIX in the name (2026-08-19_song-share), so any future
#                service folder simply gets a name without a date.
#   candidates when dir=ambiguous — every folder found, comma separated
#
# WHY BY MARKER, NOT BY NAME. The folder name belongs to the human: `.projects` in one
# project, `.sessions` in another, `MyProjects` in a third. The signal is the empty hidden
# file `.elephant` inside it. The name is never checked.
#
# WHY UP THE TREE. Work happens in any subfolder of a project; searching only the cwd
# would find Elephant from the root alone and silently report "not here" one level
# deeper — the worst kind of failure, because it looks like an honest answer.
#
# THE PROBE READS AND WRITES NOTHING. A probe that creates the folder confirms itself.
# The folder is created by a human running a command, not by the probe.

# The CLI is looked up NEXT TO THE PROBE: both live in the skill tree and travel together.
cli_path() {
  self_dir="$(cd "$(dirname "$0")" && pwd)"
  [ -f "$self_dir/el.py" ] && printf '%s' "$self_dir/el.py" || printf '—'
}

# Is `el` reachable as a plain command? The symlink is the one piece living outside the
# skill tree, so it must be MEASURED, never assumed.
cli_cmd() { command -v el 2>/dev/null || printf '—'; }

START="${1:-$PWD}"
[ -d "$START" ] || START="$PWD"
START="$(cd "$START" 2>/dev/null && pwd)" || START="$PWD"

MARKER=".elephant"
FOUND=""

# ── 1. An explicit pointer overrides the search ───────────────────────────────
if [ -n "${ELEPHANT_DIR:-}" ] && [ -f "$ELEPHANT_DIR/$MARKER" ]; then
  FOUND="$(cd "$ELEPHANT_DIR" && pwd)"
fi

# ── 2. Walk up the tree; at each level check first-depth folders ──────────────
# Stops at: $HOME, the filesystem root, or a git repository root (inclusive).
if [ -z "$FOUND" ]; then
  d="$START"
  while :; do
    hits=""
    for sub in "$d"/*/ "$d"/.*/; do
      [ -d "$sub" ] || continue
      case "$(basename "$sub")" in .|..|.git|node_modules|.Trash) continue ;; esac
      [ -f "$sub$MARKER" ] || continue
      hits="$hits${hits:+,}$(cd "$sub" && pwd)"
    done
    if [ -n "$hits" ]; then FOUND="$hits"; break; fi
    [ -d "$d/.git" ] && break
    [ "$d" = "$HOME" ] || [ "$d" = "/" ] && break
    parent="$(dirname "$d")"
    [ "$parent" = "$d" ] && break
    d="$parent"
  done
fi

# ── 3. Nothing found — an honest refusal, not empty output ───────────────────
if [ -z "$FOUND" ]; then
  printf 'dir=absent\nconfig=—\nschema=—\ntool=%s\ncli=%s\nprojects=—\ntasks=0\n' "$(cli_path)" "$(cli_cmd)"
  exit 0
fi

# ── 4. Two or more — do not guess, say it out loud ───────────────────────────
case "$FOUND" in
  *,*)
    printf 'dir=ambiguous\ncandidates=%s\nconfig=—\nschema=—\ntool=%s\ncli=%s\nprojects=—\ntasks=0\n' "$FOUND" "$(cli_path)" "$(cli_cmd)"
    exit 0
    ;;
esac

DIR="$FOUND"
CFG="$DIR/$MARKER"

# The marker is an EMPTY file — a sign on the door, not a config (guide §3). The schema
# field stays in the output for contract stability, but nothing is parsed any more.
SCHEMA="—"
TOOL="$(cli_path)"
# Tasks lie DIRECTLY in the folder, recognised by the date prefix — same rule as el.py's
# TASK_DIR. Hyphen separator since 2026-08-20 (guide §3); the underscore is still counted
# so folders created before that date keep working.
PROJ_ABS="$DIR"
TASKS="$(find "$DIR" -mindepth 1 -maxdepth 1 -type d \
  \( -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-*' \
     -o -name '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]_*' \) 2>/dev/null | wc -l | tr -d ' ')"

printf 'dir=%s\nconfig=%s\nschema=%s\ntool=%s\ncli=%s\nprojects=%s\ntasks=%s\n' \
  "$DIR" "$CFG" "$SCHEMA" "$TOOL" "$(cli_cmd)" "$PROJ_ABS" "$TASKS"
exit 0
