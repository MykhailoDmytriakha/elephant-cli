"""Knowledge doses for `el help <topic>` — the manual lives inside the tool.

Each topic is one screen the agent opens at the moment of need, instead of reading everything
up front. Sourced from .cases/RULES.md of the elephant-cli repo; keep both in sync when rules change.
"""

ONBOARDING = """start here — no `.cases/` from this folder upwards
  el case new "name" --goal "goal in the owner's words"        a case folder under .cases/
  el case new --root "name" --goal "…"                          or: this folder IS the project (root mode)
then: `el` shows where the case stands · `el help start` — how a day goes · `el help where` — what goes where"""

TOPICS = {
    "model": """the model — work is a graph the tool can check (F18–F21; concept of 2026-09-04)
- one node shape at three sizes: case · phase · item. Each has a statement (Context / `goal:` /
  the item text), a status the tool computes, evidence when done, and edges to other nodes.
- the collapsed line: what a node looks like at its parent is RENDERED from the node's own
  header, never typed — a file's line from `summary:`, a phase line from `goal:` or `result:`
  (plus the path to its file), a nested case's line from its README (progress · next · closed).
  Links, `progress:`, `last:`, `as of:` and the `cases:` block are Elephant's: edit the source, not the line.
- edges: uses = `[name](path)` in an item, phase file or decision (a bare `docs/x.md` counts too) ·
  after = `— after: N.M, case` (F19) · child = nested case, phase file · evidence = `done` → RESULT.
- two ends for every node (F20): done with what came out, or cancelled with a reason —
  `el todo cancel` · `el phase cancel` · `el case cancel`. A parent closes only when every
  child ended: an open item holds its phase, an open phase holds its case, a BROKEN child its parent.
- computed on entry: `dates:` (due today · overdue · deadline), `unblocked:` (open items whose
  blockers are done), and the Order block — what is out of place plus the command that fixes it.
  Nothing in the work points at a file → it is named (F21): link it, park it in archive/, delete it.
- refused (exit 3/4): grammar and stamps, dead links in README/TODO, dependency cycles, dropping
  what others wait for, closing over open children, done without an outcome. Shown, never
  refused: summaries, duplicates, budgets, unreferenced files, blind items. The tool checks
  structure; the owner checks truth.""",

    "start": """a day with el
1. `el` (or `el status`) — prints the case in hand: README (the "now"), TODO (phases), journal
   headlines, `dates:` and `unblocked:` when the case has dates or dependencies, and the `## Order`
   block: what is out of order and the command that fixes each line. Read this, nothing else; first
   say in your own words where the case stands and what the next step is — then go. How the whole
   thing fits together: `el help model`.
2. Work as usual. When something is worth remembering — `el log <TYPE> "…"`.
3. Every new file in docs/ research/ … starts with `summary: <one line>` right under its title —
   README Links is rendered from those lines, so the map never rots (F14).
4. Stuck? First search the knowledge base: grep -ril "<error words>" .howto/ — maybe it is solved.
   Solved a problem yourself → `el log PROBLEM "problem → root cause → fix"` AND write a recipe
   file into .howto/ (first line `when: <error words>`).
5. Finished a piece → `el todo done N.M "what came out"`; not needed after all → `el todo cancel N.M "why"`;
   a phase → `el help phases`; the case → `el done "…"`.
6. Before you stop: `el` again — if Order says "State is behind", read State: something changed →
   `el readme set next "…"`; still true as it stands → `el readme touch`. The next session
   starts from that line.
7. Never edit README.md / TODO.md / JOURNAL.md by hand — Elephant is the only write door; hand edits
   are detected by the stamp and moved aside.""",

    "order": """order — the case keeps itself tidy (F14, F15, S5, P12)
Every `el` entry ends with `## Order`: each line = one thing out of place + the command that fixes it.
- files without `summary:` → add `summary: one line` as line 2 of the file (under its title);
  descriptions already written in README Links → `el order --adopt` moves them into the files.
- folder without a description → `el readme add links "docs/ — что здесь"` (the folder line is
  yours; the file lines under it are rendered by el from the summaries).
- two files sharing their text (≥ 50 % of the smaller one's phrasing appears verbatim in the other)
  → say the difference in each summary, or merge. Shared vocabulary is not shared text: two
  documents on one subject share the names and dates and stay two documents.
- a file over 24 KB of markdown → split by summary or trim. There is no folder total: a byte
  count cannot tell deliverables from water.
- State is behind → RESULT/PHASE events were logged after `as of` → read State: `el readme set
  next "…"` when something changed, `el readme touch` when it is still true (moves `as of` only).
- broken link(s) → the target is gone from where the link says (README, TODO, journal, phase files,
  documents) → moved with `el mv` links follow by themselves; moved without el → `el relink
  old new` rewrites every link, the journal included; gone for good, or an example written as a
  link → `el relink old none` turns those links into literal text (the words stay, the claim of
  a file goes). In the journal only file-looking targets count (`docs/x.md`, not `path`).
- a file nothing in the work points at (F21) → link it from an item, a phase file or a decision
  (RESULT/DECISION evidence counts, the rendered index and plain journal chatter do not), park it
  in archive/ (`el mv`), or delete it. Shown, never deleted by el.
- an item after something gone (cancelled or dropped) → `el todo after N.M <refs|none>` or cancel it.
Nothing here is refused (Elephant does not write those files); it is shown on every entry until fixed.
Why: a limit on README alone pushed the water one layer down — new files were cheap, merging never
happened. Now the lower layer is visible from the top, and the top is rendered from it.""",

    "files": """three files per case + folders by content
- README.md — the "now": Context (goal in the owner's words) · State (progress, last result, next
  step, what we wait for) · Decisions · Problems (open only) · Links. Always current, stale lines
  are removed, not kept. Written via `el readme`.
- TODO.md — phases only: `- [ ] N Name` with items `N.M`; a closed phase collapses to one summary
  line. Written via `el todo` / `el phase`. An item's number is for life: drop and move never
  renumber (move puts N.M before N.K, or `last`), a new item takes the next free number — so a
  batch of commands aimed at numbers you just read stays correct; gaps in the numbers are normal.
- JOURNAL.md — history, newest on top, a report for the owner who was not in the session. Written
  via `el log`.
- Everything else lives in folders by KIND of content: phases/ research/ scripts/ docs/ logs/
  meetings/ data/ … (English lowercase names, created with their first file). Each .md file there
  starts with `summary: <one line>` under its title (F14); README Links is rendered by el: your
  folder line (`- docs/ — что здесь`) with the files nested under it, described by their summaries.
  Sub-folders (docs/notes/ …) render one level deeper, each file by its own summary; their line
  `- docs/notes/ — …` is yours and optional. A line you wrote for a file Elephant does not render
  (outside the content folders) stays as written — nothing in Links is dropped silently.
  Recipes are NOT per-case: they go to the project-root .howto/.
- README State carries lines el owns: `progress:` (from TODO), `last:` (newest RESULT),
  `as of:` (the journal entry State was last rewritten against, S5). Yours: next, ждёт, due …
  — `el readme set <prefix> "…"` sets one, `el readme set <prefix> ""` (or `el readme drop state
  <prefix>`) removes it once it stops being true; a stale State line is a lie the owner reads.
  Other sections are ordered lists: `el readme add <section> "line"` · `el readme edit <section>
  <k> "line"` · `el readme drop <section> <k>` — the whole story: `el help readme`.
- Exactly five sections (F1): a topic of your project (a budget, a roster) is a State line
  (`- budget: …`), or a file with `summary:` — its line lands in Links by itself.""",

    "readme": """readme — one line at a time; the whole file rarely
- State lines go by prefix: `el readme set next "…"` sets or creates `- next: …`; `set <prefix> ""`
  (or `drop state <prefix>`) removes it. `progress:` / `last:` / `as of:` are Elephant's — derived on
  every write, refused to set or drop.
- the other sections are ordered lists addressed by position (1 = first bullet):
  `el readme add decisions "2026-09-05 · X over Y — why"` (to the end) ·
  `el readme edit decisions 3 "new text"` (in place, order kept) · `el readme drop decisions 3`.
  Sections: Context · State · Decisions · Problems · Links (your folder lines; file lines are rendered).
- `set` writes State only: a prefix that names a line of another section is refused with the
  edit command for that line — it never quietly opens a second line in State.
- Order says «State is behind»: RESULT/PHASE events landed after `as of`. Read State: something
  changed → `el readme set next "…"`; still true as it stands → `el readme touch` (moves the
  anchor only). Both put `as of` on the newest journal entry; el cannot tell truth, only freshness.
- `el readme --file README.md` rewrites the whole file — rare; el re-renders what it owns.
- text with `$` (sums): single quotes — inside double quotes the shell eats `$150` and el refuses
  the trace it leaves (a double space, an orphan `.72`) rather than record a hole.""",

    "journal": """journal events — `el log <TYPE> "text"`
Types: PHASE (phase opened/closed, with outcome) · DECISION (chose X over Y, why) ·
PROBLEM (problem → root cause → fix) · RESULT (measurement, number, verdict — in plain words).
- An event is something that changes what the next reader should know. Actions (read a file, ran
  a command, edited a line, moved a TODO item) are NOT events — git holds those; el itself
  writes none since 0.9 (a decision behind an edit → `el log DECISION` yourself).
- Every phase needs at least one RESULT before it can close.
- No open phase? The entry lands in p0 — the case-level lane (gathering info, talking it over).
- `--phase p1`, `--phase 1` or a unique phase name select the phase explicitly.
- Long text is split automatically into a headline + body lines; keep headlines meaningful.
- An event is not editable afterwards — so a text with a trace of a shell substitution (`$150`
  eaten inside double quotes leaves a double space) is refused: write sums in single quotes.
- A link in an event points at a file; the file moved without `el mv` → `el relink old new`
  rewrites the journal through the stamp door (Order names such links); gone for good, or the link
  was an example → `el relink old none` makes it literal text. Examples: write them in backticks.""",

    "todo": """todo items — `el todo <action> N.M …`
- `el todo add N "text"` (`--before N.K` puts it in place, not at the end) · `el todo done N.M "what came out"` · `el todo edit N.M "text"` ·
  `el todo drop N.M` · `el todo hold N.M "why"` / `el todo resume N.M` · `el todo cancel N.M "why"` ·
  `el todo due N.M YYYY-MM-DD` · `el todo after N.M "N.K, case"` · `el todo move N.M N.K|last|K`.
- done needs what came out (F20): it lands in the journal as `RESULT · N.M: …` — a link to the
  artifact is the norm. Nothing came out? Then it was not done: `cancel N.M "why"`.
- a tick taken back: `el todo reopen N.M "why the result no longer holds"` — the item is open
  again (the phase cannot close over it, its dependents are blocked again), the journal gets a
  DECISION and the old RESULT stays as history. `resume` only lifts a hold.
- a block at once: done, reopen and cancel take a range `3.1-3.5` or a list `3.1, 3.4` (one phase
  per call) — one journal line names every number, so nothing is reused by mistake.
- numbers are for life: drop, hold and move never renumber; a new item takes the next free number
  above everything still referred to (an `after`, a journal line), gaps are normal. `move N.M N.K`
  puts the item before N.K, `move N.M last` — last; `move N.M K` (a bare phase number) sends it to
  the end of phase K under a new number there, and every `after` pointing at it is rewritten.
- dependencies (F19): end the text with `— after: N.M, N.K, case-name` or `el todo after N.M "…"`
  (`none` clears). Targets must exist, no cycles; an item others wait for cannot be dropped, only
  cancelled — its dependents are then shown as blocked by something gone, with two exits. On entry
  `unblocked:` lists open items whose blockers are all done (by due date, then position) and
  `blocked:` the rest — candidates, not the owner's `next:`.
- cancel N.M "why" — the item stopped being needed: it leaves TODO and the reason goes to the
  journal as `DECISION · снято …`. Not `done` (that would say it was completed), not `drop`
  (that says nothing).
- dates: end the text with `— due: YYYY-MM-DD` (add/edit) or `el todo due N.M YYYY-MM-DD`
  (`none` clears). The case deadline is a State line: `el readme set due "2026-09-13 · what"`.
  On entry `el` prints `dates: today … · due today · next 7 days · overdue · deadline in N days`;
  an overdue item is an Order line with its three exits: done · due <date> · cancel "why".
- a live project re-cuts itself often: plan the next phase (`el phase plan`), move items across
  phases, cancel what died, move files with `el mv old new` (links follow the file).
- case rule «items link their material» (the owner reads only README and TODO, the work lives in
  documents): `el readme add context "rule: items link their material"`. Then `todo add`/`edit`
  warn when the text has no `[name](docs/file.md)`, and Order names the open items without one.
  Opt-in: a coding case rarely needs a document per item.""",

    "phases": """phases — `el phase plan|open|close N "Name"`
- plan: `el phase plan 3 "Rollout" --goal "one line"` — names the NEXT phase while the current one
  runs: a `- [ ] 3 Rollout — intent` line in TODO, no phase file, no journal event. Park its items
  there now (`el todo add 3 "…"`); it opens later with `el phase open 3` (name and goal come
  from the plan). One phase in flight stays the rule: planned is not open. A plan is rough when
  made: the same command on a planned phase re-plans it (new name and/or goal); once open, the
  goal lives in the phase file (`goal:` line) and the TODO line follows it (F18).
- open: `el phase open 2 "Server database" --goal "one line"` — creates phases/2-server-database.md
  (goal:/result: header + free body for details, dead ends, drafts). Name: English, 1–3 words.
- while it runs: items live in TODO (`el todo add 2 "…"`, `el todo done 2.1`), the story lives
  in the phase file. TODO holds WHAT, the phase file holds HOW and WHY.
- close: needs in the journal — a RESULT for pN, `DECISION · reflect: <lesson about the process>`
  and `DECISION · align: <next phase re-planned with what we now know>` — and every item of the
  phase ended: done with an outcome or cancelled with a reason (F20; an open item holds the phase
  open). Then `el phase close 2 "what it delivered"` fills result:, collapses TODO to one line
  `- [x] 2 Name — result · date · [phases/2-name.md](phases/2-name.md)` (the path is a link — it opens
  from the editor), lists the items under `## Items at close` in the phase file with their links
  re-based (`docs/x.md` → `../docs/x.md`, the same files as from TODO), updates State.
- cancel: `el phase cancel 2 "why"` — the branch is not needed: its items are cancelled with it,
  the file says `result: снято: …`, TODO keeps one line marked «снято», progress shows ✗.
- back from cancel: a phase cancelled while still PLANNED comes back with `el phase plan 2 "Name"
  [--goal …]` — its items return under their old numbers, a DECISION says so. A phase that ran
  before it was cancelled keeps its story; plan the work again under the next number.
- the next phase will not open until the previous one passed all of the above — a cancelled phase
  passes by itself (it never ran); a phase that is still open must close or be cancelled; a phase
  planned below and never opened must open first or be cancelled: phases run in order.""",

    "cases": """cases — units of work longer than a session
- `el case new "name" --goal "…"` — new case folder .cases/YYYY-MM-DD-name/ with the three files.
- `el case list` — every case, current marked *; `el case use <name>` — switch the hand.
- The hand follows the freshest journal; one agent works one case at a time.
- Rule of nesting: know what to do → an item N.M; do NOT know the cause / needs its own research /
  longer than a session → `el spawn "name" --goal "…"` — a nested case of the same shape inside
  the parent. The parent shows one `waits:` line; `el done "outcome"` in the child writes one
  summary line back and returns the hand.
- `el done "outcome"` closes the case (all phases and nested cases must be closed first);
  `el case cancel "why"` ends it the other honest way — open phases collapse with the reason.
- the parent's Links carries a `cases:` block rendered from each child's own README (progress ·
  next; closed ones as a count plus the latest few) — never typed by hand (F18); a child whose
  README el cannot parse shows as BROKEN and holds the parent open.
- Root mode: `el case new --root "my app" --goal "…"` makes the PROJECT FOLDER itself the top
  case (README/TODO/JOURNAL in the project root; refused if a README.md already exists there).
  Feature cases live in .cases/ as usual and report their outcome back to the project on `done`.""",

    "where": """what goes where
- read / ran / edited a line            → nowhere, git holds it
- fact needed to continue the case      → README State or Decisions (via `el readme`)
- solved a problem                      → `el log PROBLEM` + a recipe in .howto/ (when: line)
- a way to do a frequent operation      → .howto/<task-verb>.md; its script → scripts/
- received a file / doc / log / meeting → a case folder by kind, `summary:` as its line 2;
                                          Links picks it up by itself (folder line is yours)
- two files sharing their text (Order names them) → say the difference in each summary, or merge
- finished for today                     → `el` → Order says "State is behind"? rewrite State
- closed a phase                        → `el phase close N "…"` (does TODO+journal+README itself)
- took a measurement                    → `el log RESULT "…"` + the number in README State
- a piece of work has a date            → `— due: YYYY-MM-DD` at the end of the item; the case
                                          deadline → `el readme set due "YYYY-MM-DD · what"`
- an item is no longer needed           → `el todo cancel N.M "why"` (not done, not drop)
- a file moves or gets renamed          → `el mv old new` — links in README/TODO/JOURNAL and
                                          the documents are rewritten; Order names broken links
- cause unknown or work too big         → `el spawn` — a nested case
- el itself misbehaves                → `el feedback "title" --actual … --expected …`""",

    "stamp": """stamp — the write-door fingerprint
- The last line of the three files is `stamp: <hash>` over everything above it. Only el writes it.
- A hand edit makes the stamp mismatch. On the next el write the file is re-parsed: valid lines
  stay, invalid ones move to <FILE>.recover.md, the write proceeds with a warning.
- If a *.recover.md exists: re-enter its lines through el commands, then `rm` the file (the
  warning prints the exact command). Data is never lost silently.""",

    "feedback": """reporting an Elephant problem or wish
`el feedback "short title" --actual "what happened" --expected "what should happen"`
optional: --repro "commands" --why "…" --acceptance "…"
The artifact lands in the elephant-cli clone's feedback/ pool (travels with git) and the path is
printed. Title + --actual + --expected are required; nothing from your environment is included.""",
    "limits": """the numbers (all enforced at write time)
README: 200 lines / 8 KB of YOUR text → warning · 300 lines / 12 KB → refusal; pointer line ≤ 150 chars
  (warning). The nested Links lines el renders from the files are reported, not counted — you
  cannot shorten them in README, and the file index must not squeeze out what the owner writes.
TODO: ≤ 200 lines (100 before 0.20: a rollout through five environments × 17 steps is structure,
  not water); item text ≤ 100 VISIBLE chars (80 before 0.21: `<Env>: [<Block>] <Action> -> expect
  <Result>` is one action with its checkable outcome) — markdown links [name](path) count as `name`
  (a refusal prints a ready trimmed suggestion);
  phase name — English, 1–3 words; no items deeper than N.M.
JOURNAL: event headline ≤ 200 chars (soft 180); long text splits automatically into headline +
  up to 5 body lines of ≤ 160 chars; body beyond that → put the story in the phase file.
Lower layer (shown, not refused): file `summary:` ≤ 120 chars; a file over 24 KB → split by summary
  or trim; two files where ≥ 50 % of the smaller one's phrasing is verbatim in the other → duplicate.
  No folder total (dropped in 0.11): a byte count cannot tell deliverables from water.
Why limits exist: they keep the entry screen readable and squeeze water out — the detail belongs
in phase files and folders, pointers belong in README. A limit on the top layer alone moves the
water one layer down — that is why the lower layer has a budget too (F15).""",

    "migrate": """migrate — a legacy case into Elephant's grammar (P13)
A legacy file = README/TODO/JOURNAL that el never stamped and the grammar rejects (written
before el, or by hand since). Every write into it is refused — rebuilding by grammar (S4)
would move most of it into .recover.md, and that is not migration.
- `el migrate` — dry run: which files are legacy, what maps where, what stays in the archive
  for review. Changes nothing.
- `el migrate --apply` — copies the legacy files byte-for-byte into legacy/<date-time>/ (verified),
  then writes the canonical files atomically; any failure puts the archive back.
What maps: README sections by name (goal/context/summary → Context; decisions; problems/risks/
open → Problems; links) · TODO headings → phases (English 1–3 words, else `Legacy N`), checkbox
lines → items (long ones trimmed; a phase with all items done is closed, its phase file says
`migrated from legacy` and P8 gates skip it) · JOURNAL → not converted: guessing types would be
lying; the new journal opens with one PHASE event pointing at the archive — re-enter what still
matters with `el log`.
After apply: `el` (Order shows what to rewrite), `el readme set next "…"`, `el check`.""",

    "errors": """exit codes and what to do
0 — done. 1 — internal error. 2 — wrong usage (the message shows the correct form).
3 — rule violation: the write was REFUSED, no file was touched; fix the input as the message says.
    "outside Elephant's grammar and was never stamped" = a legacy file → `el migrate` (see `el help migrate`).
4 — precondition not met: no .cases/ from here upwards · every case closed · a case file missing ·
    a phase not ready to open/close. The message names the check and a recovery command.
Diagnostics without any writes: `el doctor`. Facts that save an investigation:
- el never reads or writes AGENTS.md / CLAUDE.md — they only point at el;
- el never changes your shell's cwd (a child process cannot);
- errors go to stderr; the bare `el` entry also mirrors them to stdout.""",
}


def topic_list() -> str:
    return " · ".join(sorted(TOPICS))
