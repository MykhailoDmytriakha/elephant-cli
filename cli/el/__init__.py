"""el — the Elephant CLI. Keeps the bookkeeping of work: where it lives, which phase it
is in, what proves the move forward.

THREE RULES THAT ARE NOT UP FOR DEBATE (ELEPHANT.md §0.2):
  1. Never calls a model. Not once. It creates folders, writes files, counts state.
     The agent thinks; the CLI remembers.
  2. Standard library only, one folder. Installed by copying `cli/`, fixed by reading.
     (One FILE until 2026-08-21, when it passed 4 700 lines; now one PACKAGE — `el.py`
     is the door, `el/` the rooms. The symlink `~/.local/bin/el → cli/el.py` is unchanged.)
  3. Source of truth is plain text files. State must open in a notepad.

THE ROOMS — a module is a PHASE or a LAYER, never a "utils" (owner, 2026-08-21):
  protocol   the contract: phases, the beats of each, what proves the move — the data
             `el blueprint` prints and every gate reads. Declarations only
  state      files on disk and what they mean: storage lookup, the journal, the derived
             card, the hand (hold / current / idle), the render-dirty set, git as a
             measurement, the tool's own inbox (feedback/ in the skill)
  term       how text is shaped for the agent's eye: wrap · human_when · bar
  autonomy   the credit of the owner's word: grant · borrowed words (--assumed) · debt ·
             halt — derived from the journal, printed first by status and next
  context    phase 1 — the ladder: Q/A pairs, the 5W+1H boundary, the frame, research
  think      phase 2 — forks, the decision, the open box of instruments, a recorded skip
  plan       phase 3 — the fractal of nodes, the eight fields, the stops along the road
  validate   phase 5 — the ledger: criteria from the plan, one verdict at a time
  views      the human's pages: metadata/ data files, templates kept equal to the skill's
  navigate   the three questions and the move: status · context · next · left · where ·
             projects · forward · phase
  commands   bookkeeping and lifecycle: init · new · boot · use · log · beat · artifact ·
             accept · todo · spawn · reopen · done · lesson · ui · feedback · blueprint ·
             onboard
  main       the command map, the parser, the dispatcher, `el help`

Imports flow one way — protocol ← state ← term ← amend · autonomy ← context · think · plan ←
validate ← views ← navigate ← commands ← main — so no module needs a module above it.
"""
