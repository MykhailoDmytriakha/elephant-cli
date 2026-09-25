"""Knowledge doses for `el help <topic>` — the manual lives inside the tool.

Each topic is one screen the agent opens at the moment of need, instead of reading everything
up front. Sourced from .cases/RULES.md of the elephant-cli repo; keep both in sync when rules change.
"""

EXEMPLAR = """a well-led item looks like this — pockets in the owner's words, the proof promised before the work (el help practice):
  - [ ] 1.2 choose the database
    - why: the data model, the migrations and the cost for years depend on it
    - note: find out the volumes, the cost, the migration path, how many environments we keep
    - note: the numbers come from [Menuka](../people/menuka-perera.md) — read her card before the call
    - expect: the chosen DB with its case [file: docs/db-choice.md] · load on a prototype [run: k6 → p95] · budget and horizon [owner]"""

# The block an agent's instruction file carries (CLAUDE.md · AGENTS.md · GEMINI.md) — one source: `el onboarding` writes it
# between marks with a fingerprint, the entry keeps it fresh, ONBOARDING.md shows the same text (a test holds them equal).
# The owner's word, 2026-09-25: a strong push is not a long one — why, the rhythm in three moments, one IMPORTANT line.
ONBOARDING_BLOCK = """## Elephant — память работы в `.cases/`

Ты начинаешь без памяти, и следующий агент — тоже ты. Чего нет в `el` — сделанного, решений, причин, — для него не существует. Форму держит `el`: порядок, отказы, подсказки; содержание — ты.

**Начало — `el`.** Первая строка `thread:` — цель → фаза → пункт → шаг. Перескажи владельцу не его словами: что из этого следует, чего он не сказал (помечай «вывожу»), что спросишь. Его же слова в ответ — эхо, а не понимание.

**Работа — пункт за пунктом.** **IMPORTANT: закончил пункт — сразу `el todo done N.M <вид> "что вышло"`, не в конце сессии** (вид — `file:путь` · `ref:след` · `run:"команда → исход"` · `owner`). Решение — `el log DECISION "что · вместо чего · почему"`. Упёрся — сначала `grep -ril "<слова ошибки>" .howto/`, решил — `el log PROBLEM`. Не для этой фазы — `el todo add later "…"`.

**Конец — снова `el`.** Order чист, State правдив: `el readme set next "…"`, а если всё верно — `el readme touch`. Сделанное принимает свежая сессия: `el todo brief N.M` печатает для неё задание; `[/]` в TODO — сделано, ждёт приёмки. Ты — вторая рука: перезапусти каждое `run:` и принеси, что вышло сейчас — `el todo accept N.M --by <ты> --run "команда → исход" "…"`.

README, TODO, JOURNAL — только через `el`: правку руками ловит отпечаток. Строки `hint:` и `Order` — команды тебе, с номером: сделай или скажи, почему нет. Знание дозами: `el help start`, потом `el help <тема>`.

Нет `el` → `git clone https://github.com/MykhailoDmytriakha/elephant-cli`, затем `./elephant-cli/install.sh`."""

ONBOARDING = """start here — no `.cases/` from this folder upwards
  el case new "name" --goal "goal in the owner's words"        a case folder under .cases/
  el case new --root "name" --goal "…"                          or: this folder IS the project (root mode)
then: `el` shows where the case stands · `el help start` — how a day goes · `el help where` — what goes where"""

TOPICS = {
    "philosophy": """philosophy — why Elephant exists and what every change and every report is weighed against
(the owner's word; the tool carries it to every machine it runs on — a report written in these words is fixed in one pass)

What it is: the memory of WORK, not of text. Work is done by agents with no memory between sessions, and everything given
them instead of memory grew until nobody read it. A case is a folder: a goal in the owner's words, the now (README), the
plan (TODO), the history (JOURNAL) — and the TOOL keeps their shape, not the agent's discipline. Success: any agent on any
machine enters a case in one screen and continues instead of starting over; the owner opens README and TODO and sees where
the work stands, without being in the session.

Proof from the bottom up (the blueprint of a formal proof: a statement is proved when every statement it imports is):
work is one tree — case · phase · item, one node shape at three sizes. A leaf ends one of two ways: done with evidence
someone other than the writer can check, or cancelled with a reason. A parent never types its own status — it is
assembled from its children. The tool is the auditor at every step: a crooked step is refused with the command that does
it right; an unclear one is an Order line with its fix. Structure does what intelligence alone does not: many agents,
one work.

Every report and every change is weighed against four holes — name the one you see:
- proof from the bottom up — something ended below and is not visible above, or there is no legal move up
- the tool keeps the order — the order of the work is held by the agent's discipline, not by the tool
- the record does not lie — a line says more or less than is true: «done» on the cancelled, a cut text, a dead pointer
- knowledge in doses — the agent does not get what it needs at the moment it needs it

The principles a fix is held to:
- the tool keeps the form, the agent the content; a limit is a refusal, and its number comes from a live case
- every printed line resolves and has an honest fix — a line closable only by spoiling good work teaches to skip it
- every record has an edit through the same door (edit · touch · plan again · reopen · relink · cancel)
- rendered, not written: nothing about children is typed at the parent; a rendered line is whole, never counted, never cut
- refuse the structure, show the content: the tool cannot judge meaning — it names it and gives the ways out
- a rule lives at the write door: it holds the record written now, never the history (the phase you work in IS the door)
- evidence is a thing, not a phrase: a file anyone opens · a trace a person checks · a run a machine repeats · the owner's word
- an action is not an event: the journal grows only from what changes the next reader's knowledge
- two ends for every branch — done with evidence or cancelled with a reason — and a way back with a reason (reopen)
- instructions do not retell the tool: knowledge lives in `el help`, a project carries one short block (el onboarding)
- the system grows only from live use: a report from a real case → a principle → a change → a measurement → a test

A report is not a spec: it is weighed against these, and the fix goes to the hole, not to the symptom — sometimes as an
honest alternative to what was asked. Decided not to do: an external database or JSONL as the source of truth · hidden
node ids in TODO · reading dates or dependencies out of free text · deleting files by the tool · reminders before a live
check · a second copy of the stamp.""",

    "model": """the model — work is a graph the tool can check (F18–F21; concept of 2026-09-04)
- one node shape at three sizes: case · phase · item. Each has a statement (Context / `goal:` /
  the item text), a status the tool computes, evidence when done, and edges to other nodes. An item
  carries its pockets under it (F22): `why:` — what it is for, `note:`… — what to know, `result:` +
  proof lines — what came out (Prove2Me: statement, description, proof — separate lines, one node).
- the collapsed line: what a node looks like at its parent is RENDERED from the node's own
  header, never typed — a file's line from `summary:`, a phase line from `goal:` or `result:`
  (plus the path to its file), a nested case's line from its README (progress · next · closed).
  Links, `progress:`, `last:`, `as of:` and the `cases:` block are Elephant's: edit the source, not the line.
- edges: uses = `[name](path)` in an item, phase file or decision (a bare `docs/x.md` counts too) ·
  after = `— after: N.M, case` (F19) · child = nested case, phase file · evidence = `done` → RESULT
  with a KIND: file · ref · run · owner (`el help evidence`) — the tick, the kind and the RESULT are one write.
- two ends for every node (F20): done with what came out, or cancelled with a reason —
  `el todo cancel` · `el phase cancel` · `el case cancel`. A parent closes only when every
  child ended: an open item holds its phase, an open phase holds its case, a BROKEN child its parent.
  The other direction is shown, not forced: every item of a phase ended → Order says close it or
  add what is missing — the owner decides, the tool names the moment. Phases are one pipeline
  (in order, one in flight); work on its own clock is a nested case (`el spawn`), one line at the parent.
- computed on entry: `dates:` (due today · overdue · deadline), `unblocked:` (open items whose
  blockers are done), and the Order block — what is out of place plus the command that fixes it.
  Nothing in the work points at a file → it is named (F21): link it, park it in archive/, delete it.
- refused (exit 3/4): grammar and stamps, dead links in README/TODO, dependency cycles, dropping
  what others wait for, closing over open children, done without a kind or an outcome. Shown, never
  refused: summaries, duplicates, budgets, unreferenced files, blind items, items ticked before the
  kinds existed (`untyped` in the `evidence:` count). The tool checks structure; the owner checks truth.
- the machine (F23, F24; the owner's word, 2026-09-25): one course at three sizes — proposed (the general list,
  `el help later`) → agreed (`phase agree`) → in work → done → accepted or returned (`el help acceptance`) →
  closed; from any state, cancelled with a reason. Three roles: the owner sets the direction and agrees the scope,
  the agent decomposes and delivers, el keeps the order — and what one hand did, a fresh session accepts. The entry
  opens with `thread:` — goal → phase → item (why) → first: the Order debt it has not named → next: what is
  subordinate to what, and one direction: a debt below is a step of the thread, not a second voice.""",

    "start": """a day with el
1. `el` (or `el status`) — prints the case in hand: README (the "now"), TODO (phases), journal
   headlines, `dates:` and `unblocked:` when the case has dates or dependencies, and the `## Order`
   block: what is out of order and the command that fixes each line. Read this, nothing else; the first
   line, `thread:`, says what is subordinate to what. Then retell it to the owner — not in the owner's words:
   where the case stands, the next step, what follows from it that nobody said (marked as your inference) and
   what you would ask; words that repeat the owner's words prove nothing (el help practice: RETELLING) — then go. How the whole
   thing fits together: `el help model`. The last line may be a `hint:` — el saw something in the case you
   can do better; do it, or say why not. How strong agents lead a case: `el help practice`.
2. Work as usual. When something is worth remembering — `el log <TYPE> "…"`.
3. Every new file in docs/ research/ … starts with `summary: <one line>` right under its title —
   README Links is rendered from those lines, so the map never rots (F14).
4. Stuck? First search the knowledge base: grep -ril "<error words>" .howto/ — maybe it is solved.
   Solved a problem yourself → `el log PROBLEM "problem → root cause → fix"` AND write a recipe
   file into .howto/ (first line `when: <error words>`). The phase close asks for it anyway: a PROBLEM of the phase
   no recipe answers → `--howto .howto/<verb>.md` or `--howto "none: why"` (el help phases).
5. Finished a piece → `el todo done N.M <kind> "what came out"` — the kind of evidence first:
   file:<path> · ref:<trace> · run:"<command → outcome>" · owner (`el help evidence`); not needed after all → `el todo cancel N.M "why"`;
   a phase → `el help phases`; the case → `el done "…"`. Done by you is accepted by another hand: `el todo brief N.M`
   prints the prompt for a fresh session (`el help acceptance`). Not for this phase → `el todo add later "…"` (`el help later`).
6. Before you stop: `el` again — if Order says "State is behind", read State: something changed →
   `el readme set next "…"`; still true as it stands → `el readme touch`. The next session
   starts from that line.
7. An old case? Its closed phases are history — leave them. The phase you work in is held to the
   current form: Order names what it lacks (a promise in the goal, expect on items, a kind on ticks).
8. Never edit README.md / TODO.md / JOURNAL.md by hand — Elephant is the only write door; hand edits
   are detected by the stamp and moved aside.
9. The Elephant block in CLAUDE.md / AGENTS.md is el's: `el onboarding` writes it where your agent reads, `el` keeps it
   current after every update (el help onboarding).""",

    "order": """order — the case keeps itself tidy (F14, F15, S5, P12)
Every `el` entry ends with `## Order`: each line = one thing out of place + the command that fixes it.
- files without `summary:` → add `summary: one line` as line 2 of the file (under its title);
  descriptions already written in README Links → `el order --adopt` moves them into the files
  (markdown only — a file with no body keeps its description in the Links line).
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
- a phase whose every item ended → close it (`el phase close N "…"`) or add what is still missing
  (`el todo add N "…"`); the line names what the close needs first (RESULT, reflect:, align: —
  `el log --phase N …`). A phase with no items says nothing. Shown until the phase ends (F20).
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
  `- docs/notes/ — …` is yours and optional. A file that is not .md (pdf, html, png, a script) has
  no body to read: describe it with a Links line — `el readme add links "docs/council/send.html —
  what it is"` — and it renders as a link among the folder's documents; undescribed ones stay
  folded into one `other:` line. A line you wrote for a file Elephant does not render (outside the
  content folders) stays as written — nothing in Links is dropped silently.
  A document is one question per file, and the answer first: the line under `summary:` (or the first
  paragraph) says the conclusion, the breakdown follows — the owner reads the Links line, then the top of
  the file, and should not scroll for the answer. Two questions in one file dilute the summary and bury
  both answers: make it two files (feedback 2026-09-16: «why-x-and-router-flow.md»).
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
  Bare `el readme` (nothing piped) prints the README and these doors — it writes nothing.
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
- `--phase p1`, `--phase 1` or a unique phase name select the phase explicitly. Without it the event goes
  to the phase whose items the text names (`RESULT "2.3: …"` → p2, said in the output); items of several
  phases or none → the phase in flight. A version like `1.20.0` is not an item.
- Long text is split automatically into a headline + body lines; keep headlines meaningful.
  Your own line breaks are kept: each line after the first becomes a body line (up to 5) — fields
  written one per line stay one per line.
- An event is not editable afterwards — so a text with a trace of a shell substitution (`$150`
  eaten inside double quotes leaves a double space) is refused: write sums in single quotes.
- A link in an event points at a file; the file moved without `el mv` → `el relink old new`
  rewrites the journal through the stamp door (Order names such links); gone for good, or the link
  was an example → `el relink old none` makes it literal text. Examples: write them in backticks.""",

    "todo": """todo items — `el todo <action> N.M …`
- `el todo add N "text"` (`--before N.K` puts it in place, not at the end) · `el todo done N.M <kind> "what came out"` · `el todo edit N.M "text"` ·
  `el todo drop N.M` · `el todo hold N.M "why"` / `el todo resume N.M` · `el todo cancel N.M "why"` ·
  `el todo due N.M YYYY-MM-DD` · `el todo after N.M "N.K, case"` · `el todo move N.M N.K|last|K`.
- done needs the KIND of its evidence and what came out (F20): `el todo done 2.4 file:evidence/receipt.pdf "fee paid"`
  — kinds: file:<path> · ref:<trace> · run:"<command → outcome>" · owner, several at once when the proof is several
  things; the journal gets `RESULT · N.M: file [receipt.pdf](…) — fee paid` and under the TODO line el writes
  `result: fee paid` with one proof line per kind. A second done on a done item ADDS a proof. Who checks each kind: `el help evidence`.
  The words are for the owner who was not in the session — what came out for the item, in plain terms, answering
  its `why:`; a commit hash, a function name, an operator is a trace, and a trace is proof (ref:<hash> · file:<source>),
  not the words (el warns when the words read like a code trace).
  Nothing came out? Then it was not done: `cancel N.M "why"`.
- a tick taken back: `el todo reopen N.M "why the result no longer holds"` — the item is open
  again (the phase cannot close over it, its dependents are blocked again), the journal gets a
  DECISION and the old RESULT stays as history. `resume` only lifts a hold.
- the second hand (F23): `el todo brief N.M` prints the prompt for a fresh session · its verdict:
  `el todo accept N.M --by codex --run "make test → 12 OK" "what was checked"` (one `--run` per `run:` proof, re-run
  now) or `el todo reopen N.M --by codex "what is wrong"` — el help acceptance. In a case with two hands el renders the
  mark: `[/]` done, awaiting acceptance · `[x]` accepted — the legend under the TODO title says so while one is owed.
- the general list (F24): `el todo add later "…"` → `## Later`, `Lk` · `el todo move Lk N` takes it into a phase ·
  `el todo move N.M later` puts an open item there with its pockets — el help later.
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
  Opt-in: a coding case rarely needs a document per item.
- the item's pockets (F22) — lines under the item, in one order, each ≤ 150 visible chars:
  `why:` what it is for (one; `el todo why N.M "…"`, "" removes) · `note:` a constraint, who to call, what to
  bring, a link to the document (several; `el todo note N.M "…"`, `--edit k "…"`, `--drop k`; a list
  `N.M, N.K` puts one note under several items — a problem met in one environment is expected at the
  same step of the next) · `expect:` what done will look like, written BEFORE the work, with the proofs it
  will take in brackets — `[file: docs/x.md] [run: k6 → p95] [owner]` (one; `el todo expect N.M "…"`); at
  `done` el holds the record to it: `expect: 2 of 3 filled — missing [run: …]` · `result:` + proof lines,
  written by `done` only. `todo add … --why "…" --note "…" --expect "…"` sets them at once. why/note/expect
  are yours and count in the 200 lines; result and proof lines are el's and do not.
- `fact:` — the fifth pocket: what the item is expected to establish (open) or has established (done); `-` says
  none. Every item of a RUNNING phase says what work is expected (`expect:`) — el warns at add and Order names
  the gaps; a fact is expected only where knowledge is the outcome (el help facts).
- cut items by what they leave behind: one outcome with its own proof per item. Two items whose proof is one
  artifact were one item — its steps go to `note:` lines or the phase file; an item that leaves nothing checkable
  is a step of another. el says so when an `expect:` names an artifact another item promised or left.
- `el todo show N.M` — the item's card when you pick it up: its pockets, the proofs of the items it comes after
  (`— after: N.K`, F19) as its inputs, and what it feeds. A chain hands its artifacts forward; a side branch on
  its own clock is a nested case, and `after: <case>` joins it.
""",

    "evidence": """evidence — what `done` stands on (F20; the owner's word, 2026-09-14)
A tick is not a proof. `el todo done N.M <kind> "what came out"` — the kind of evidence comes first,
then the words; the tick, the kind and the RESULT are one write. Four kinds, and who can check each:
- file:<path>                a thing anyone can open — photo, pdf, receipt, letter, screenshot,
                             transcript, export, saved response, or the source file itself when the case
                             drives code. NOT a markdown you wrote in the case about the work: that is your
                             own text with a link on it — el warns, and names the thing behind it (a run,
                             the source or spec file, the saved response). One file proving every item of a
                             phase is a report, not four proofs — el warns at `done` and the Digest counts
                             distinct proofs.
                             The path is read from the case folder first, then from the project root
                             (`file:src/app/parser.ts`); the tool checks the file is there (later: that
                             it did not change) and writes the link from the case. The strongest kind.
                                                          → tail `— file: [receipt.pdf](evidence/receipt.pdf)`
- ref:<trace outside>        a request number, a case number on a portal, a URL, a letter in the
                             mailbox, a commit hash — a person can check it outside the case; the tool checks only
                             that a trace is named. A screenshot or pdf turns a ref into a file; a ref
                             that names a file in reach gets a warning: that is a file, say file:.
                                                          → tail `— ref: R000123-000001`
- run:"<command → outcome>"  a machine check — tests, a build, a measurement; the tool checks the
                             arrow (`->` is fine, el writes →), a repeat is the proof. QUOTE the value:
                             unquoted, the shell reads `>` as a redirection and the outcome lands in a file.
                                                          → tail `— run: python3 -m unittest → 219 OK`
- owner                      the owner's word — talked and agreed, a meeting without a recording,
                             a rule the owner confirmed. Nothing to check, and it says so honestly.
                             The agent's own word is not a kind: the agent writes the record, so it
                             leaves a file instead.        → tail `— owner`
The list is closed on purpose: a fifth spelling is refused (exit 2) with this list; a kind that is
really missing comes through `el feedback` and, if it is needed, becomes one.
Where it shows (F22, since 1.10.0): under the TODO line of a done item el writes `result: <what came out>`
and one proof line per kind (`- file: [receipt.pdf](evidence/receipt.pdf)` · `- ref: …` · `- run: …` ·
`- owner`) — the tick, the words and the proofs are separate lines, a click away for the owner and outside
the 100-char count; several kinds in one `done` when the proof is several things; a second `done` on a done
item adds a proof (the words stay unless given) and writes no RESULT — the tick is not new. At `phase close` the block travels into the phase file, links
re-based. On entry `evidence: 11 done · file 3 · owner 8 — el checked: file exists · run, ref, owner: as reported`
counts the done items of the open phases and says what el itself verified: a file exists; a run is as the agent
reported it, nobody repeated it — `check` passing means structure and form, not proof. el never runs a check itself: running it
is the agent's job and the agent's responsibility (the owner's word, 2026-09-22) — el records what was reported.
Old records: an item ticked before 1.5.0 has no kind and counts as `untyped` — read, never nagged: the
rule lives at the write door, not at the read. The exception is the phase in flight — it IS the write door,
so there `check` counts a tick without a kind (el help phases). Attach evidence later through the same door —
`el todo done 2.9 file:evidence/abstract.pdf` on a done item attaches it, keeps the words (new words renew
them) and writes no journal event: the journal grows from new knowledge, not from bookkeeping. `reopen N.M "why"` clears the result and its proofs (why and notes stay): the result no longer holds.
Two ends without evidence stay: `cancel N.M "why"` (not needed) · `reopen N.M "why"` (refuted).""",

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
  planned below and never opened must open first or be cancelled: phases are one pipeline, in
  order, one in flight — unless something found makes N come first: `el phase open N --why "what was found"`
  (F24, the owner's word 2026-09-25: a hidden blocker) — the planned ones below stay planned, a DECISION says why,
  one phase in flight still. A dead end: `el phase close N "…" --rest later` — the open items go to the general
  list with their pockets, the gates are the same (`el help later`). The scope the owner agreed:
  `el phase agree N "the owner's words"` — at the boundary, before opening; under the case rule «two hands»
  Order names a running phase without it (`el help acceptance`).
- out of turn: work parked under a planned phase may end before its turn (it ran alongside). Then
  `el phase close N "…"` closes it straight from the plan once every item ended — the file is born
  at close, the journal says it ran alongside, progress shows ✓; `open` stays refused. Every gate
  still applies, logged under that phase: `el log --phase N RESULT|DECISION "…"`. Next time, work
  that runs on its own clock is a nested case, not a phase: `el spawn "name" --goal "…"` (P11) —
  its own phases, its own agent, one rendered line at the parent when it closes.
- the phase in flight is held to the current form; closed phases are history. A legacy case, an old phase:
  read as they are, never nagged, never migrated by hand. The phase you WORK in is the write door itself
  (the owner's word, 2026-09-17): its goal promises proofs, every open item carries `expect:`, every tick
  carries a kind — Order names what is missing there, `check` counts a tick without a kind there as a
  violation, and nothing is asked of the phases before it. Start on an old case: migrate it if it is
  pre-el, then bring only the running phase to order.
- acceptance is a promise, and a promise is items. The `goal:` names what must be TRUE when the phase closes,
  one proof per criterion, in the brackets `expect:` uses — `--goal "discount applied [run: trace shows the outbound
  pricing call] [run: discount fields non-zero] [run: rerun shows the changed total]"`. Each criterion
  with words is covered by an ITEM whose `expect:` carries the same slot (`el todo add N "…" --expect "[run: trace
  shows …]"`) and proved when that item is done with a proof of that kind — the phase is proved by its items
  (Prove2Me). While the phase runs, Order names a promised proof no item works towards; `phase close` REFUSES
  over an unproved promise (finish the item, or correct the goal line); the Digest says `phase promise: 3 of 4
  proved — [run: …] by 2.3 · not proved: [run: …]`. A baseline, an HTTP 200, a manual computation are steps —
  RESULT events and notes — not the criterion (feedback 2026-09-16: a phase closed on a baseline, `check` 0).
  The expectation lives at every size of the node: Context for the case, `goal:` for the phase, `expect:` for the item.
- the recipe question (P8; the owner's word, 2026-09-25 — 48 PROBLEM events and four recipes on the tool's own case):
  a phase that logged a PROBLEM no recipe answers closes with `--howto .howto/<verb>.md` (the file exists, its first line
  is `when: <the error words>` — grep finds it next time; logged as a link) or `--howto "none: why nothing repeats"`;
  a PROBLEM that names `.howto/…` is answered already; a phase without PROBLEM is not asked. `el done` asks once for the
  PROBLEMs no phase close answered. The close door only: a phase closed before the rule is never asked again.
- `el phase close N "what it delivered" --reflect "the lesson" --align "what changes next"` — the two DECISIONs
  P8 asks for and the close in one command; the gates are the same, nothing is logged if another gate refuses.
- `el phase note N "…"` (`--edit k` · `--drop k`) — what the phase has to know: a permit that expires, a
  service to call, a problem seen one stage earlier. Under a planned phase it waits in TODO (`parked:` on
  entry counts items, notes and journal events logged with `--phase N`); `phase open` writes the parked
  journal events into the file as `## Before opening`; `phase close` moves the notes into the file.
- the closed phase file opens with `## Digest`, rendered at close — items (and how many distinct proofs
  stand behind them), notes, phase-level results (item results live under their items below), problems,
  decisions, reflect, align, all from the journal events of that phase; then `## Notes` (yours) and
  `## Items at close` with every item and its pockets, links re-based. Poor journal, poor digest.
""",

    "cases": """cases — units of work longer than a session
- `el case new "name" --goal "…"` — new case folder .cases/YYYY-MM-DD-name/ with the three files.
  Name it in the owner's own words, any language: Cyrillic is transliterated into the folder name
  and the name itself stays as the README title.
- `el case list` — where every case stands: open ones first, each on the line it shows at its parent
  (progress · next · due, rendered from its own README), closed ones as a count plus the latest few,
  cases from before el (README never stamped, outside the grammar) as one count line — `--all` names
  every closed and legacy one, `el --case <name> migrate` reads a legacy case; current marked *;
  `el case use <name>` — switch the hand.
- The hand follows the freshest journal; one agent works one case at a time.
- Rule of nesting: know what to do → an item N.M; do NOT know the cause / needs its own research /
  longer than a session → `el spawn "name" --goal "…"` — a nested case of the same shape inside
  the parent. The parent shows one `waits:` line; `el done "outcome"` in the child writes one
  summary line back and returns the hand.
- `el done "outcome"` closes the case (all phases and nested cases must be closed first);
  `el case cancel "why"` ends it the other honest way — open phases collapse with the reason.
- the parent's Links carries a `cases:` block rendered from each child's own README (progress ·
  next; closed ones as a count plus the latest few) — never typed by hand (F18); a child from before
  el shows as legacy → migrate, a child whose stamped README el cannot parse any more as BROKEN →
  check; both hold the parent open.
- Root mode: `el case new --root "my app" --goal "…"` makes the PROJECT FOLDER itself the top
  case (README/TODO/JOURNAL in the project root; refused if a README.md, TODO.md or JOURNAL.md already
  exists there — keep it and use the ordinary form). Those three files lie outside .cases/: a
  .gitignore rule for .cases/ does not cover them — ignore them too, or commit them on purpose.
  Feature cases live in .cases/ as usual and report their outcome back to the project on `done`.""",

    "where": """what goes where
- read / ran / edited a line            → nowhere, git holds it
- fact needed to continue the case      → README State or Decisions (via `el readme`)
- solved a problem                      → `el log PROBLEM` + a recipe in .howto/ (when: line); the phase close asks
                                           once for every PROBLEM no recipe answers: --howto .howto/<verb>.md · "none: why"
- a way to do a frequent operation      → .howto/<task-verb>.md; its script → scripts/
- received a file / doc / log / meeting → a case folder by kind, `summary:` as its line 2;
                                          Links picks it up by itself (folder line is yours)
- wrote a document                      → one question per file, the answer right under `summary:`,
                                          the breakdown after it (el help files)
- a person the cases deal with          → .cases/people/<name>.md, `summary:` as line 2 (role · what they
                                          own · how to reach); cases link to the card (el help people)
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

    "feedback": """feedback — telling Elephant it is wrong (the door when the tool does not let you through honestly)
el refused what the work needs, a printed line has no honest fix, a kind or a form is missing? Do not
forge the record (no `done` on a cancelled item, no path written as text) — report it and go on by a workaround.
  el feedback "short title" --actual "…" --expected "…" [--repro "…"] [--why "…"] [--acceptance "…"]
  title          what el did wrong, in a few words — it becomes the file name
  --actual       what el printed or wrote, verbatim, with the exit code — what happened, not what you feared
  --expected     what should have happened instead
  --repro        the commands in order, from a clean case, so the reader can replay it
  --why          which hole it shows, in the words of `el help philosophy`: proof from the bottom up · the tool keeps the
                 order · the record does not lie · knowledge in doses — and the principle it breaks
  --acceptance   how to see it is fixed — a check someone can run; it becomes the test
Title, --actual and --expected are required; the other three are what makes the report fixable in one pass.
Three depths — say which one you bring (feedback 2026-09-25: reports stayed at the first, the tool grew by the third):
  1 a wall    el refused, crashed or printed a line that lies — the exact output is the report
  2 a dose    the way exists, but you could not find it, or the refusal did not teach the fix
  3 a lever   («move 37») el's own behavior breaks a principle of `el help philosophy` — Order sends you past a gate,
              a mark says «checked» where one hand did it. Name the rule that lets the dishonest path exist and propose
              the form in which the honest path is the only one: a state, a mark, a refusal, a rendered line — not one
              more warning on top. That is how `[/]` came (1.27.0): the fix is in the form, not in the discipline.
              Not a lever: --force or --skip, a larger limit without a measure of a live case, an opt-in line nobody
              writes — each keeps the dishonest path open. At this depth --actual is where el lets the disorder in,
              --expected the form in which it cannot happen, --acceptance a test a careless agent can no longer pass.
The report goes to the maintainer of el and may end up in a shared repository: no business data — no names of projects, clients,
people, internal APIs or endpoints, no ticket, case or request numbers, addresses, sums. Describe the SHAPE
(«an item with an endpoint path and a flag name, 103 chars»), invent a neutral example of the same form.
Valuable to the reader: the exact output and exit code · the source line you read (`commands.py:NN`) · what you
did instead · Actual checked against the live case (a fear written as a fact is the first thing that fails).
A report is not a spec: it is weighed against the principles (`el help philosophy`) and may get an honest alternative.
Where it lands: `<elephant-cli clone>/feedback/<date-time-title>.md` (the title transliterated like a case
name; a second report in the same minute gets `-2`, never overwrites), its header carrying the date and the el
version — nothing else from your environment, not even the case name. It does not travel by itself: anyone may
clone elephant-cli, few may push to it — the owner carries the file to the maintainer's clone (its feedback/ folder);
until then it lies there and nobody has read it. Tell the owner it is there.
In your own case: `el log PROBLEM "el: <title> — workaround: …"` so the next agent does not hit the same wall
twice; after `git pull` raised the el version, try the wall again.""",
    "practice": """how strong agents lead a case — weak against strong, by moment (the owner's word, 2026-09-16)
The agent woke up with no memory, a good notebook (.cases/) and good search. What separates a case that
merely gets ticked from one the next agent can continue is below; each `hint:` line el prints points here.

ENTRY
  weak    reads README, TODO, ten journal entries and starts working
  strong  reads them and says in its own words where the case stands and what the next step is — the hand-over
          is accepted, not just read; then works item by item, recording as it goes, not at the end

RETELLING (the owner's word, 2026-09-25: «he notices more than I said — and I see he understood»)
  weak    «You want Scrum.» — the owner's words back: clear, and it proves nothing — the same words match always;
          three times in one session such an echo looked like understanding and the work went the wrong way
  strong  «Scrum: a backlog, a sprint goal, the scope fixed while the sprint runs — do you size the items, and in
          what?» — what follows from the words, marked as inference and open to the owner's check; the question at
          the seam; what it changes for the goal. Surplus asserted as fact is the echo's twin: story points are not
          in the Scrum Guide — say «I infer», not «we will have»

ACCEPTANCE
  weak    el todo done 2.3 … and the phase closes on the doer's word
  strong  el todo brief 2.3 → a fresh session opens the files, re-runs every `run:` proof, holds the result to `why`
          and to `expect` → el todo accept 2.3 --by codex --run "make test → 12 OK" "…" · or el todo reopen 2.3 --by
          codex "what is missing"

AN ITEM
  weak    el todo add 3 "database"
  strong  el todo add 3 "choose the database" --why "data model, migrations and cost depend on it" \
            --note "find out volumes, cost, migration path, environments" \
            --expect "chosen DB with its case [file: docs/db-choice.md] · load on a prototype [run: k6 → p95] · budget [owner]"
          one action with a checkable outcome; why and note in the owner's words; the proof promised before the work.
          Cut by what is left behind: one outcome with its own proof per item — four items proven by one file were
          one item with four steps (steps go to its notes)

A CHAIN
  weak    3.1 analyze · 3.2 look in the DB · 3.3 combine — all three proven by research/notes.md
  strong  3.1 why was it disconnected → [file: research/why-disconnected.md]
          3.2 what the DB holds for group X → [file: research/db-group-x.md]
          3.3 the answer — after: 3.1, 3.2 → [file: research/answer.md], and it links both inputs
          each step leaves its artifact, the next one imports it; `el todo show 3.3` prints the inputs; a side
          branch on its own clock is a nested case and `after: <case>` joins it (the owner's sketch, 2026-09-16)

RESULT AND FACT
  weak    el todo done 4.1 run:"grep trace -> no call" "checked the trace"          — what you did
  weak    ... --fact "checkout never calls the pricing API"   — three traces became «never»: a sample stated as always
  strong  el todo done 4.1 run:"grep 3 DEV traces -> no outbound pricing call" "trace read across three DEV pods" \
            --fact "in 3 DEV traces of checkout, no outbound pricing call — not seen, not proved absent"
          the result is the work, the fact is what is now known WITHIN what was observed — where, how many, what
          would refute it; the next agent builds on the fact (el facts) and knows how far it reaches

DONE
  weak    el todo done 3.2 owner "done"                                  — the agent's word dressed as the owner's
  weak    el todo done 3.2 file:testing/what-i-did.md "see the write-up"  — the agent's own text with a link on it
  weak    el todo done 4.1 file:x.md "Commit a1b2c3d4e5 removed region == EU check and gutted update()"
          — a code trace; the owner asked «why was it disconnected» and reads TODO without a terminal
  strong  el todo done 4.1 ref:a1b2c3d4e5 "disconnected on purpose in the merge: the region check is gone, so
          checkout no longer reaches the pricing call" — the answer in the owner's words, the hash where it belongs: the proof
  strong  el todo done 3.2 file:docs/db-choice.md run:"k6 run load.js -> p95 48ms" owner "Postgres; budget 200$/mo confirmed"
          a thing anyone opens, a run anyone repeats, the owner's word for what only the owner can confirm; el then
          holds the record to the promise: `expect: 3 of 3 filled` — or names what is short

A PROBLEM
  weak    fixes it and moves on — the next agent hits the same wall
  strong  el log PROBLEM "error text → root cause → fix" and a recipe .howto/<verb>.md whose first line is
          `when: <the error words>` — found by grep by an agent who does not know it exists

PARKING AN IDEA
  weak    a backlog item, a TODO in the code, a note to self — forgotten
  strong  el phase plan 5 "Roof" --goal "…" · el phase note 5 "lamps under the eaves" · el todo add 5 "…" ·
          el log --phase 5 DECISION "…" — parked where it will be needed; `parked:` counts it on entry, it
          surfaces in the phase file when the phase opens. Decompose only what you work on.

A DOCUMENT
  weak    research/why-x-and-router-flow.md — two questions in one file, `summary: analysis of X and the router`,
          the answer somewhere in section 4
  strong  research/why-x-disconnected.md — `summary: X was disconnected on purpose in the API merge`, the
          first paragraph is the conclusion, the breakdown follows; the router flow is its own file.
          One question per file, the answer first: the owner reads the Links line, then the top

PEOPLE
  weak    the secretary is described in the Links of every case, in slightly different words, one of them stale
  strong  one card, .cases/people/court-secretary-3.md — `summary: sets hearing dates · no phone · in person on
          Tuesdays 10–13` — and every case links it: `note: read [the secretary](../people/court-secretary-3.md) first`.
          Personal data lives inside .cases/ and hides with the cases (el help people)

A WORKAROUND
  weak    the crutch stays for months and becomes the architecture
  strong  el readme add problems "open · <root problem> · workaround: <what we do> · until: 2026-12-01 (<what fixes it>)"
          — counted on entry; past the date, Order asks: fixed, or move the date?

ACCEPTANCE
  weak    phase 4 «Discount»: items «build the baseline», «compute the discounted values by hand», «call
          checkout» — all done, all proved (HTTP 200, five cost rows); phase closed; check 0. The DEV trace
          later: no pricing call, discount = 0. The proofs proved the baseline, not the goal.
  strong  --goal "discount applied end to end [run: same request finds the customer's discount group]
          [run: trace shows the outbound pricing call with the group id] [run: discount in the response
          logs] [run: the rerun shows the changed total]" — four criteria, four items with the same
          slots in their expect, four proofs; the baseline is a RESULT on the way, not a criterion. The close refuses
          until each criterion is proved; the Digest shows which item proved which

CLOSING A PHASE
  weak    reflect: "tests passed on DEV and UAT"           — that is a result
  weak    align: "curl ready to hand to the stakeholder"    — that is a deliverable
  strong  reflect: "ask WHY before going, not after"        — a lesson about how you worked
  strong  align: "phase 3 loses the 2024 items; hearing needs copies prepared" — what changes in the next plan
          the Digest is rendered from what you logged: poor journal, poor digest — that is the honest mirror

""" + EXEMPLAR + """
""",
    "people": """people — the cards of the people the cases deal with (L10; the owner's word, 2026-09-16)
A secretary, a stakeholder, a service you call: they appear in several cases, and a line in one case's Links
goes stale in the next. One card per person, outside the cases and inside .cases/ — personal data hides with
the cases under the same .gitignore rule:
  .cases/people/menuka-perera.md
    # Менука Перера
    summary: stakeholder of pricing-disc-api · decides on budget and release dates · Teams, answers before noon
    ## How to work with her
    - show a ready curl and numbers, not a description
    ## What she owns
    - PROD acceptance, the signature on a contract change
- the file name is Latin, lowercase, hyphens (a role when the name is unknown: court-secretary-3.md);
  `summary:` is line 2 — the dose an agent reads before calling or writing: role · what they own · how to reach.
  The body is free: how to work with them, what they own, what they never answer. Not their history —
  that lives in the journals of the cases.
- a case points at a card like at any file: `el todo note 2.4 "read [Menuka](../people/menuka-perera.md) first"`
  or a Links line; the link is checked like every link (F16), a card without `summary:` is named in Order.
- el writes nothing here — you write the card, like a recipe in .howto/. Later, if the cards are read:
  `el who <name>` (the summary line at the moment of need) and «appears in cases: …» rendered from the links.""",
    "facts": """facts — the chain of what is known (the owner's word, 2026-09-17)
A result is the work: «servers up, no errors», «trace grepped across three pods». A fact is what is now KNOWN
and later work builds on: «in 3 DEV traces of checkout, no outbound pricing call». Not every item yields a
fact — starting servers does not; grepping the trace does. The fact chain is made of facts only, like the
proved statements of a theory: found and proved once, then built on, not re-derived by the next agent.
- `fact:` is the fifth pocket. Expected while the item is open (`el todo add … --fact "…"`, `el todo fact N.M
  "…"`), established once done. `done` on an item with an expected fact asks for the verdict: `--fact confirmed`
  · `--fact "the fact as it turned out"` · `--fact -` (none came out). The journal RESULT carries it.
- `el facts` renders the chain: ✓ established · · expected (open) · ? under question (rests on an item that is
  open again — refuted, and el never reopens the dependents itself: finish the base, rewire `after`, or reopen)
  · ✗ dead branch (cancelled, with its reason, from the journal). Done items without a fact are counted as work.
- the chain has edges: `— after: N.K` says what a fact rests on; `el todo show N.M` prints the inputs.
- a fact carries its bounds (feedback 2026-09-22: four samples read as «the fallback is always safe», a direct
  API response as end to end): what was observed, where, how many — and, when it matters, what would refute it.
  Not seen is not absent · a sample is not always · a direct call is not end to end · the owner's decision (keep
  the fallback) is a decision, not evidence that the fallback works — it goes to the journal as DECISION, the
  fact stays as open as it was. Unknown is a legitimate state: an expected fact stays open, `--fact -` says none
  came out; el does not judge the words, the agent answers for them.
- what the strong form looks like: `result:` says what the work produced, `fact:` says what is true now, and the
  expectation written before the work (`expect:`, expected `fact:`) stands next to both — confirmed or refuted
  is knowledge either way. `el help practice` shows the pair.""",
    "acceptance": """acceptance — done by one hand, accepted by another (F23; the owner's word, 2026-09-25)
Why: the agent who did the work already knows what it meant and reads that into the result; a fresh session knows
only what lies in front of it. Anthropic's ART campaign (2026-09-23: 949 sessions, 119 tasks) never let a worker accept
its own task — a supervisor did: the same model with a clean context. el launches nobody: it prints the brief and
records the verdict.
- `el todo brief N.M` — the prompt for a FRESH session (a new chat, another agent, a subagent with a clean context):
  the case goal, the phase goal, the item with the owner's `why`, what was expected before the work, what the doer
  says came out, the proofs as paths from the project, the two verdict commands. No second agent at hand? The owner
  pastes it into a new chat.
- the verdict — `el todo accept N.M --by codex --run "make test → 12 OK" "what you checked and how"` → under the item
  `accepted: codex · another session · 2026-09-25 · re-ran 1 of 1` and `DECISION · принято N.M: …` with a body line
  `re-run: …` per command; the return — `el todo reopen N.M --by codex "what is missing or wrong"` → the tick and the
  acceptance go, the reason stays.
- re-run, not re-read (the owner's word, 2026-09-25: «the second hand runs the commands and says it worked»): every
  `run:` proof of the item is re-run by the acceptor, one `--run "<command> → <what came out now>"` each; accept
  refuses without them and names them. Could not run one here — `--run "<command> → not run: why"`, counted as not
  re-run (`re-ran 0 of 1 (1 not run)`), said, not hidden. A result that differs is a return, not an acceptance.
  el runs nothing itself — it asks and records what was said. The owner's word needs no re-run.
- the marks (a live report, 2026-09-25: `[x]` on one hand's work read as «checked» to everybody): in a case with two
  hands el renders the box from the item — `[ ]` open · `[/]` done, awaiting acceptance (half of an x: one hand of
  two) · `[x]` accepted, finished · `[~]` on hold. A legend under the TODO title says so while an item is owed. The
  mark is rendered, not written: `done` makes `[/]`, `accept` makes `[x]`, `reopen` makes `[ ]`. A case without the
  rule keeps `[x]` for done.
- the session: `done` writes the doer's session under its RESULT (`session: 1a2b3c4d` — EL_SESSION, else the
  harness's id; Claude Code sets CLAUDE_CODE_SESSION_ID); `accept` compares: another session · same session ·
  session not given · the owner's word. Provenance, not proof: a subagent shares its parent's session id.
- `--by self` is refused: a self-acceptance is not an acceptance. The owner's word passes: `--by owner "…"`.
- two errors, two guards: the acceptor catches «done is not what was expected»; «expected is not what the owner
  meant» only the owner catches — at the start, when the agent retells the task (el help practice: RETELLING).
- stuck: an open item returned 3 times → an Order line with three honest exits: cut it smaller · cancel it with the
  reason · finish it; `el todo show N.M` lists the reasons.
- the case rule — a new case is born with it (`case new` writes the Context line; feedback 2026-09-25: opt-in meant one
  hand always); an older case takes it by the same line: `el readme add context "rule: two hands — the owner agrees each
  phase's scope, a fresh session accepts each done item"`; the owner drops it with `el readme drop context k`. It makes
  the entry count `acceptance: k of n done accepted`, Order names the done items
  nobody accepted and a running phase whose scope the owner never agreed (`el phase agree N "…"`), and `phase close`
  refuses over an unaccepted item — a fresh session accepts, or the owner's word.""",

    "onboarding": """onboarding — the block your agent's instruction file carries (S6; the owner's word, 2026-09-25)
An agent starts with no memory; what it reads first is its instruction file — CLAUDE.md (Claude Code), AGENTS.md (Codex,
Cursor, Copilot and most others), GEMINI.md. The Elephant block there is the push: why (you have no memory, the next agent
is you), the rhythm in three moments (start with `el` and retell with surplus · tick each item at once · end with `el`),
one IMPORTANT line. The rest el says itself, in the moment: `thread:`, Order, `hint:`.
- `el onboarding` — where the block is, it is refreshed there; where it is nowhere, el picks the file the running agent
  reads (CLAUDE.md under Claude Code, else an instruction file that exists, else AGENTS.md) and adds the block at the end.
  Your own text is never touched; a link (CLAUDE.md → AGENTS.md) is one file.
- `el case new` in a project without the block writes it the same way — the first case teaches the agent's file the rhythm.
- the block sits between marks with a fingerprint of its text: `<!-- elephant onboarding 1.25.0 · 3f2a9c1b7d20 … -->` …
  `<!-- /elephant onboarding -->`. After `git pull` brings a new el, the next `el` refreshes a stale copy itself
  («onboarding refreshed in CLAUDE.md»); a release that leaves the text as it was changes nothing.
- edited by hand inside the marks → not overwritten: an Order line, and `el onboarding` rewrites it (keep your own lines
  outside the marks); a block pasted by hand (the heading, no marks) → an Order line, `el onboarding` takes it under marks
  in place.
- `el onboarding --show` prints the block and writes nothing — to paste it where el does not look (.cursor/rules/, a
  global ~/.claude/CLAUDE.md). `EL_ONBOARDING=0` switches the automatic part off.""",

    "later": """later — the general list and the phase boundary (F24; the owner's word, 2026-09-25)
What is not for the running phase does not break it: it goes to the general list, and the next phase is formed from
that list at the boundary — when a phase closes, or earlier by the owner's word. Not a backlog that eats thoughts:
every boundary is a moment of return, and a counter names what the boundaries keep passing by.
- `el todo add later "cache warm-up on deploy" --why "…"` → the last section of TODO, `## Later`:
  `  - [ ] L3 cache warm-up on deploy — since: 2026-09-25`, pockets under it like an item; the number is for life.
- at the boundary `el phase close N "…"` prints the list; each line gets a decision — into a phase: `el todo move L3 5`
  (it becomes 5.k; the phase may be planned or open) · not needed: `el todo cancel L3 "why"` · kept: nothing to do,
  it counts the boundaries. A line three closes passed by → an Order line asking by name.
- the other way: an open item not for this phase → `el todo move 4.7 later` (with its pockets; a date or a dependency
  stays behind — they belong to an item of a phase); a done item stays where it was done.
- a Later line takes words and pockets only (edit · why · note · cancel · drop · show); done, dates, dependencies and
  acceptance come after `move Lk N` — the refusal names that move.
- a thought whose moment is known («this is for phase 5») parks at that phase: `el todo add 5 "…"` into the plan,
  `el phase note 5 "…"` — `parked:` counts it until the phase opens.
- the order of phases is decided at the boundary too: a hidden blocker makes a planned phase come first —
  `el phase open 5 --why "the pipeline blocks the migration"`: the planned ones below stay planned, a DECISION says
  why, one phase in flight still. A dead end → close early by the owner's word: `el phase close 4 "…" --rest later`
  — the open items go to the general list, nothing is lost.""",

    "limits": """the numbers (all enforced at write time)
README: 200 lines / 8 KB of YOUR text → warning · 300 lines / 12 KB → refusal; a POINTER line (Links, State)
  ≤ 150 chars (warning) — Decisions, Problems and Context are text, bounded by the byte limit only. The nested
  Links lines el renders from the files are reported, not counted — you cannot shorten them in README, and the
  file index must not squeeze out what the owner writes.
TODO: ≤ 200 lines (100 before 0.20: a rollout through five environments × 17 steps is structure,
  not water); item text ≤ 100 VISIBLE chars (80 before 0.21: `<Env>: [<Block>] <Action> -> expect
  <Result>` is one action with its checkable outcome) — markdown links [name](path) count as `name`, nothing
  else is exempt: an item over 100 is rephrased, not recounted (the owner's word 2026-09-15 — verb first, the
  path stays, the filler goes); a refusal cuts at the last boundary of meaning (— ; : · ,) and offers the rest
  as the item's note in a ready command (`el todo add N '…' --note '…'`); no boundary fits → rephrase;
  pockets (F22): `why:` / `note:` ≤ 150 visible chars each and they count in the 200 lines; `result:` and the
  proof lines under it are el's — reported, not counted, and written whole: el cuts nothing in README, TODO or a phase
  file (the owner's word, 2026-09-25 — a cut part is lost to the reader; `result:`, `closed:`, `last:`, Links, the TODO
  phase line and the Digest carry the whole text);
  phase name — English, 1–3 words; no items deeper than N.M.
JOURNAL: event headline ≤ 200 chars (soft 180 — said once, by `el log`, for the line you just wrote); long text
  splits automatically into headline + up to 5 body lines of ≤ 160 chars; body beyond that → put the story in
  the phase file.
The machine (F23, F24): an open item returned 3 times → Order «stuck»; a Later line three phase closes passed by →
  Order asks by name — both shown, never refused; the numbers are a first guess, moved by a live case.
Warnings are about THIS write: a command warns only about lines it introduced; history is `check`'s business,
  and `check` says it once per rule («F2 · pointer line over 150 — lines 14, 15, 18 (3 lines)»).
Lower layer (shown, not refused): file `summary:` ≤ 120 chars — over it, an Order line asks to rephrase line 2 of the
  file (Links shows it whole, never cut: a limit asks the source, it never cuts the copy); a file over 24 KB → split by summary
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
After apply: `el` (Order shows what to rewrite), `el readme set next "…"`, `el check`.
A case from before el in hand — the one touched last — is named, not shown: the entry prints what it is and `el migrate`,
plus el's own open cases (`el case use <name>`); its files stay on disk as they are (a live project, 2026-09-25: the raw
README and TODO filled 27 KB). A folder with no README where el stamped nothing is from before el too: `el case list`
counts it with the legacy ones and `--all` names it — BROKEN is only a case el wrote that broke since.""",

    "errors": """exit codes and what to do
0 — done. 1 — internal error. 2 — wrong usage: the message names what is missing, prints the command's
    examples (for `feedback` its whole dose) and `el help <topic>`; the library's bare `usage:` line is never the answer.
3 — rule violation: the write was REFUSED, no file was touched; fix the input as the message says.
    "outside Elephant's grammar and was never stamped" = a legacy file → `el migrate` (see `el help migrate`).
4 — precondition not met: no .cases/ from here upwards · every case closed · a case file missing ·
    a phase not ready to open/close. The message names the check and a recovery command.
Warnings: a write warns only about what it introduced (an old long line is not your business today); `check` shows
    the soft layer once per rule with the line numbers. `violations: N` is what to read; warnings are the lower layer.
Diagnostics without any writes: `el doctor`. Facts that save an investigation:
- el never reads or writes AGENTS.md / CLAUDE.md — they only point at el;
- el never changes your shell's cwd (a child process cannot);
- errors go to stderr; the bare `el` entry prints its refusal on stdout instead, once — it explains itself where it is read.""",
}


# What an agent types for a topic, in the words it has in its head — singular forms and the common nouns of the
# craft (feedback 2026-09-16: `el help phase` was a wall). The list of doses stays closed; the door is wider.
ALIASES = {
    "phase": "phases", "plan": "phases", "digest": "phases", "close": "phases", "open": "phases",
    "case": "cases", "spawn": "cases", "nested": "cases", "list": "cases",
    "file": "files", "folder": "files", "folders": "files", "summary": "files",
    "limit": "limits", "numbers": "limits", "error": "errors", "exit": "errors", "codes": "errors",
    "item": "todo", "items": "todo", "pocket": "todo", "pockets": "todo", "note": "todo", "notes": "todo", "why": "todo",
    "due": "todo", "after": "todo", "dates": "todo", "done": "evidence", "proof": "evidence", "proofs": "evidence",
    "kind": "evidence", "kinds": "evidence", "expect": "practice", "hint": "practice", "hints": "practice",
    "best": "practice", "practices": "practice", "craft": "practice", "log": "journal", "event": "journal",
    "events": "journal", "problem": "journal", "decision": "journal", "result": "journal", "stamps": "stamp",
    "recover": "stamp", "rule": "model", "rules": "model", "graph": "model", "howto": "where", "recipe": "where",
    "recipes": "where", "legacy": "migrate", "migration": "migrate", "problems": "order", "until": "order",
    "workaround": "order", "report": "feedback", "bug": "feedback",
    "fact": "facts", "chain": "facts", "knowledge": "facts",
    "accept": "acceptance", "accepted": "acceptance", "mark": "acceptance", "marks": "acceptance", "checkbox": "acceptance",
    "rerun": "acceptance", "re-run": "acceptance", "brief": "acceptance", "review": "acceptance", "reviewer": "acceptance",
    "verdict": "acceptance", "hands": "acceptance", "supervisor": "acceptance", "return": "acceptance", "stuck": "acceptance",
    "onboard": "onboarding", "instructions": "onboarding", "claude.md": "onboarding", "agents.md": "onboarding",
    "backlog": "later", "pool": "later", "general": "later", "triage": "later", "boundary": "later", "thread": "model",
    "machine": "model", "agree": "phases", "scope": "phases",
    "why": "philosophy", "principles": "philosophy", "principle": "philosophy", "idea": "philosophy", "direction": "philosophy",
    "holes": "philosophy", "hole": "philosophy",
    "person": "people", "who": "people", "contact": "people", "contacts": "people", "participants": "people", "team": "people",
}


def resolve(topic: str):
    """The dose for what the agent typed: the topic, its alias, or its singular/plural form; None when nothing fits."""
    key = topic.strip().lower()
    for cand in (key, ALIASES.get(key), key.rstrip("s"), key + "s"):
        if cand and cand in TOPICS:
            return TOPICS[cand]
    return None


def topic_list() -> str:
    return " · ".join(sorted(TOPICS))
