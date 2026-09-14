#!/usr/bin/env bash
# install.sh — put the `el` command on this machine. Run once after `git clone`, from anywhere:
#
#     git clone https://github.com/MykhailoDmytriakha/elephant-cli
#     ./elephant-cli/install.sh
#
# The clone may live at ANY path: the link points at the folder this script is in. After that,
# `git pull` in the clone is the whole update — the command, the rules and the tests all come
# from this one folder, and the link keeps working.
#
# What it does (idempotent — safe to run again):
#   ~/.local/bin/el  →  <clone>/bin/el        the command
#   <clone>/feedback/ exists                  the tool's own inbox (el feedback), travels with git
#
# What it deliberately does NOT do: touch any agent's skill folder. The skill (skill/SKILL.md)
# is the same text for Claude Code, Codex, Copilot or any other harness — and this machine may
# not have the one you expect. You connect it yourself; the recipe is printed at the end.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${HOME}/.local/bin"

[ -f "$HERE/bin/el" ] || { echo "not an elephant-cli clone: $HERE" >&2; exit 1; }
chmod +x "$HERE/bin/el"
mkdir -p "$BIN" "$HERE/feedback"
[ -L "$BIN/el" ] && rm "$BIN/el"
if [ -e "$BIN/el" ]; then
  echo "$BIN/el exists and is not a link — move it aside first" >&2; exit 1
fi
ln -s "$HERE/bin/el" "$BIN/el"
echo "linked    $BIN/el -> $HERE/bin/el"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "PATH      add ~/.local/bin to PATH (e.g. in ~/.zshrc): export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

python3 -c 'import sys; print("python    " + sys.version.split()[0] + " ok")' \
  || echo "python3   NOT found — Elephant needs Python 3, no dependencies"

printf '%s\n' \
  "done      el — the command · update: git -C \"$HERE\" pull" \
  "" \
  "next      teach the agent, once per project — either way works:" \
  "          skill   cp -r \"$HERE/skill\" ~/.claude/skills/elephant   (Claude Code; Codex and Copilot read their own folder)" \
  "          text    paste section 3 of \"$HERE/INSTALL.md\" into the project's CLAUDE.md / AGENTS.md / GEMINI.md" \
  "          then    cd <your project> && el case new \"first case\" --goal \"…\""
