#!/usr/bin/env python3
# el — Elephant CLI: the door. The code lives in the el/ package next to this file
# (one module per phase or layer; `el/__init__.py` is the map of the rooms); this
# script only finds the package and hands over. The command reference is `el help`,
# the protocol is `el blueprint`, and bare `el` onboards.
#
# Kept as a plain script, not a module of the package, so the symlink
# `~/.local/bin/el → <skill>/cli/el.py` and `python3 <skill>/cli/el.py` both keep working.
import os, sys

# No .pyc litter in the skill tree: the skill travels between machines, and the monolith
# never left bytecode behind either (a script is compiled on every run; so is this one).
sys.dont_write_bytecode = True
# Resolve the symlink first: the package sits next to the REAL file, not next to the link.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from el.main import main  # noqa: E402  (the path above must come first)

if __name__ == "__main__":
    sys.exit(main())
