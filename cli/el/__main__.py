"""`python3 -m el` (from cli/) and `python3 cli/el` — the same door as `el.py`."""
import os, sys

sys.dont_write_bytecode = True        # same as el.py: no .pyc litter in the skill tree
if __package__:                       # python3 -m el
    from .main import main
else:                                 # python3 cli/el — run as a directory, no package context
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
    from el.main import main

sys.exit(main())
