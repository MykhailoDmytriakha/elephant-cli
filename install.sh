#!/usr/bin/env bash
# install.sh — put the `el` command on this machine. Run once after `git clone`, from anywhere:
#
#     git clone https://github.com/MykhailoDmytriakha/elephant-cli
#     ./elephant-cli/install.sh
#
# The clone may live at ANY path: the link points at the folder this script is in. After
# that, `git pull` in the clone is the whole update — the command, the page templates and
# the guide all come from this one folder.
#
# What it does (idempotent — safe to run again):
#   ~/.local/bin/el  →  <clone>/cli/el.py       the command
#   <clone>/feedback/ exists                    the tool's own inbox (el feedback), under git
#
# What it deliberately does NOT do: touch any agent's skill folder. The skill (skill/SKILL.md)
# is the same for Claude Code, Codex, Copilot or any other harness — and the machine may not
# have the one you expect. You connect it yourself; the recipe is printed at the end.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${HOME}/.local/bin"

[ -f "$HERE/cli/el.py" ] || { echo "not an elephant-cli clone: $HERE" >&2; exit 1; }
chmod +x "$HERE/cli/el.py"
mkdir -p "$BIN" "$HERE/feedback"
[ -L "$BIN/el" ] && rm "$BIN/el"
if [ -e "$BIN/el" ]; then
  echo "$BIN/el exists and is not a link — move it aside first" >&2; exit 1
fi
ln -s "$HERE/cli/el.py" "$BIN/el"
echo "linked    $BIN/el → $HERE/cli/el.py"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "PATH      add ~/.local/bin to PATH (e.g. in ~/.zshrc): export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

cat <<EOF
done      el — the command · update: git -C "$HERE" pull

skill     connect skill/ to YOUR agent — copy it, or link it so that git pull updates it too:
  Claude Code   ln -s "$HERE/skill" ~/.claude/skills/elephant
  Codex CLI     ln -s "$HERE/skill" ~/.codex/skills/elephant
  Copilot / other  paste skill/SKILL.md into the agent's instructions file (AGENTS.md,
                .github/copilot-instructions.md), or point it at "$HERE/skill/SKILL.md"
  In a project  a line in AGENTS.md / CLAUDE.md is enough: «работай по Elephant — el next»
EOF
