"""The entry: the command map, the parser, the dispatcher, `el help`.

`el help` prints the map below — it is read straight from this file, so the map and
the parser that registers the commands sit together and cannot drift apart.
"""
# general — storage · tasks · the hand
#   el init [--dir PATH]              create the .projects storage at the project root
#   el new "<description>" --id NAME  create a task; up to 5 words, the date is prepended:
#                                     2026-08-20-harvest-dislikes-and-dataset.
#                                     --raw "<his words>" records the user's request IN HIS
#                                     WORDS — only what is about the task, side talk left out —
#                                     into init/request.md. THE SAME TASK AGAIN is refused: words
#                                     of the new one against name + request of every open task —
#                                     continue that one (el use) or --force
#   el boot "<description>" --id NAME idempotent: init if missing + new if missing + status line ·
#                                     --mode light|soft|strict sets the task's TIGHTNESS at birth ·
#                                     --raw on an EXISTING task appends «Повтор запроса» in his words
#                                     · --raw "<fact>" --source jira — an EXTERNAL fact (Jira, a
#                                     document, a colleague): its own section, typed apart from
#                                     his words — never filed as the owner's request
#   el use <id>                       TAKE a task in hand — the one commands act on without
#                                     --task (a `hold` event; `el done` puts it down → idle)
#   el projects | el ls               list of tasks: phase, last touched, description, and the
#                                     REQUEST in his words — look here before opening a task
#   el spawn "<description>" --id N   a NEW wish that surfaced mid-flow becomes its own task,
#                                     with a note of where it came from; the task in hand stays
#                                     current. Neither swallowed nor lost. The test for a task
#                                     rather than a later stage: does it need its OWN context?
#                --raw "<his words>"   the user's request in HIS words into init/request.md —
#                                     a wish is born IN the conversation, so its wording is
#                                     right there and is the first thing lost by retelling
#                --depends-on <task>   a DEPENDENT project: own context, but standing on that
#                                     one. The link is written on both sides and shown in the list
#   el reopen <task> --why "..."      a closed task comes back: reversing a judgement is normal
#                                     work, and the reason is written next to the closing one
#   el mode [light|soft|strict]       the slider of strictness: light — a few beats required,
#                                     soft — the spine (default), strict — every beat, every stage
#                                     decomposed, five criteria per node, no --waive. Bare: show.
#                                     The human's word and the graph integrity hold in every mode
#   el log "<text>" [--type T]        append an event to the journal · --task <id> writes it
#                                     during execute the note lands on the node IN WORK
#                                     (el plan <узел> and the page show it there) · --node <id>
#                                     aims elsewhere · --free keeps it off nodes on purpose
#                                     to ANOTHER task — a note about a task you are not standing
#                                     in; the hand does not move (no write ever moves it)
#   el beat <name> [--ref FILE]       mark a beat that leaves no file of its own · --task <id>
#   el todo "<what>" --when <phase>   park work that belongs to a LATER phase; `el next`
#                                     surfaces it when that phase arrives — BELOW the move,
#                                     as «на потом» (a promise, not the next step) · --every
#                                     "<how often>": a standing REMINDER (⟳) — never a step,
#                                     never holds completion · bare / --list: the
#                                     OPEN items, NUMBERED — N is what --done takes (open items
#                                     in file order); closed ones fold away, --all shows them ·
#                                     --done N with an optional note to close item N
#   el brief ["<text>"]               THE SHEET a returning agent reads first: baseline · measure ·
#                                     best · not again · now. Rewritten whole, ≤ 20 lines / 1500
#                                     chars; el and el status print it first
#   el lesson "<text>"                a lesson that OUTLIVES its task → <storage>/lessons.md;
#                                     bare `el` prints them, so the next agent starts warned
#   el feedback "<text>"              THE TOOL'S OWN INBOX — what in `el` got in the way, what
#                                     helped; one file per review in feedback/ of the clone (the
#                                     pool a meta-session reads, fixes, deletes) · --about · --by ·
#                                     --from user (his words) · --file · <id> · done <id> ·
#                                     add <id> "<more>" | --file — a revision, appended under its
#                                     date (never a second pool item for one observation)
#                                     THE SHAPE, so it can be reproduced: наблюдал: <command →
#                                     what it printed> · ожидал: <instead> · обошёл: <how you went
#                                     on> · помогло: <what worked> — a thin review is taken, but
#                                     told it is thin
#                                     el feedback prompt [tool|concept] — THE PROMPT for the human:
#                                     printed and put on the clipboard (pbcopy · wl-copy · xclip ·
#                                     xsel · clip; ELEPHANT_CLIPBOARD=off), pasted into an agent's
#                                     chat → a long review: the tool (findings with evidence) ·
#                                     the concept (model, layers, what to keep), filed by --file
#
# look — the three questions and the map
#   el resume                         ONE CARD TO COME BACK ON: the sheet · autonomy · the owner's
#                                     debt · the baton · the node in work · three states of
#                                     checking · contradictions · the gate · THE one move (the
#                                     same `el next` gives) · the rule of the return. The page's
#                                     «карточка для агента» ends with it; --task <id> for another
#   el status                         where we are: project, task, and the phase strip —
#                                     what is passed, what is current, what lies ahead
#   el next                           the next move: phase, beat, what blocks, which command
#   el progress [<фаза>]              THE STORY SO FAR — the main files of every phase, whole:
#                                     request · clarified task and summary · crystal and decisions
#                                     · plan.md and the nodes with results · criteria with
#                                     verdicts · lessons · the chain of phase moves. One screen;
#                                     <фаза> — that phase's files without the cap
#   el left | el rest                 WHAT IS STILL LEFT on the current task: open nodes with
#                                     their stops, the first stop that blocks, parked questions,
#                                     missing traces, and who is waiting on us
#   el where                          ABSOLUTE paths: project, folder, task, and every trace
#                                     of the current phase — what `el next` names relatively
#   el blueprint [<part>] [--mode M]  THE CONTRACT in doses: bare — the big picture (one screen);
#                                     <фаза>|init — one phase with all its beats (read it on
#                                     entry; el forward shows the card); rules · modes · files
#                                     — the other sections; full — everything in one stream
#                                     (the human's one-shot listing)
#   el help [<команда>|<группа>|how]  the map (this screen) · one command · one group ·
#                                     how — the mechanics, its own screen
#   el ui [update] [--open]           refresh the human pages NOW, without waiting for the
#                                     agent's next write; --open opens them in the browser
#   el doctor [--fix]                 integrity: criteria answered but node open · two nodes in
#                                     work · closed without result · waiting unanswered · phase
#                                     past execute with open nodes · proof files missing · pages
#                                     behind the template
#
# move — one phase forward with a reason · back freely
#   el forward --why "<reason>"       move ONE phase forward; --waive instead = no proof
#   el phase <name> [--why]           move BACK to any earlier phase (forward is refused)
#
# owner — his word · autonomy
#   el accept "<his words>"           THE OWNER'S WORD, verbatim — condition 3 of the gate.
#                                     --assumed "<why>" DECIDES IN HIS PLACE under a grant (el grant):
#                                     what you take for his word, marked; never --for final.
#                                     Context does not open without it, and --waive does not
#                                     excuse it: a checklist may not stand in for a human ·
#                                     --for <scope> says what the word is OVER: context · design:<fork>
#                                     · plan · stage:<id> (the LAYOUT of a stage into packages —
#                                     the packages start after it) · node:<id> · observation:<id>
#                                     · final (unscoped = the phase's natural scope; only `final`
#                                     counts on validate)
#                                     · --close with node:<id> closes that node with his words
#   el ack "<trace|area:x>" --why     leave a past-phase tail as is, on purpose — «за спиной»
#                                     stops repeating it
#   el grant "<his words>"            AUTONOMY — a GRANT, his word that opens it («работай сам»),
#                                     verbatim; a PERIOD: it starts here and ends by `grant end`
#                                     · `halt` · his stop · a new grant · the task closing. Bare:
#                                     the state · --name "<short>" · --hours N (the term; status
#                                     says «срок вышел») · --until · --no "<what not to touch>".
#                                     While it stands a missing word is DECIDED IN HIS PLACE
#                                     (--assumed); never the final word · el blueprint autonomy
#                el grant change "<his words>" --hours 4 | --until | --no | --name
#                                     he corrected the standing grant — the SAME grant, changed
#                el grant end "<what proves it>"   the natural end: condition or term reached
#   el review                         the grants, newest first, each with the agent's decisions
#                                     under it (what · why · NEW since his last word) and the
#                                     work done under it. No debt, no rollback: he reads, and
#                                     says otherwise if he wants — from the current state
#   el halt "<why · what is needed>"  HOLD — the emergency exit: autonomy stops HERE, the grant
#                                     ends. Not «done»: task open, in hand; status prints it
#                                     first; only a new el grant («продолжай») opens it again ·
#                                     --by user — his own «стоп»: the grant taken back by him
#   el owe "<question>" --how "<who/where>"
#                                     THE OWNER'S DEBT — an answer only he can bring and does
#                                     not have yet (who signs, who the third party is, which
#                                     option he wants): he goes to find out or to think. Born on
#                                     ANY phase. Not a brake by itself — work goes on; it holds
#                                     only what it is tied to · --kind выяснить|решить ·
#                                     --by <due> · --area <area> (the area stays uncovered) ·
#                                     --holds node:<id>|fork:<id>|phase:<phase> — where work
#                                     stands without it · bare: the ledger
#   el owe <n> --holds node:s1.wp2    tie a debt to the point that needs it, later
#   el plan block s1 wp2 --owe <n>    the same from the plan's side: reached the point, the
#                                     node stands on his answer; start is refused meanwhile
#   el owe answer <n> "<his answer>"  he brought it — the debt is paid, a node it held is let
#                                     go (reread its contract), a fork it held is decided by
#                                     his words · el owe drop <n> --why "…" — never came due
#
# context (phase 1/8) — one stream, records.jsonl: a record per line, nothing edited (2026-08-26)
#   el context [--section X]          THE WHOLE CONTEXT OF THE TASK, top to bottom, AS CONTENT
#                                     — folded out of the stream, never a link to a file;
#                                     bounded: longer than one screen → a TABLE OF CONTENTS,
#                                     --section <раздел> opens one, --full prints the whole.
#                                     This is what you show him before el accept
#   FLOWS — written all phase long, the moment the thing happens:
#   el context qa "<q>" "<a>"         a clarifying pair AFTER the owner answered · --area
#                --area <area>        REQUIRED (eleven areas; coverage, not count) · --options
#                                     "а · б · в" the choices you offered · --new-round the
#                                     next round · --assumed "<why>" autonomy: an answer in
#                                     his place, marked, his word over the picture pays it
#   el research "<тема>"              a research TOPIC: what was investigated · --summary the
#                --summary "<…>"      digest in plain words · --file research/<имя>.md the file
#                --file <path>        that holds the material, long or short (owner 2026-08-27)
#                [--folds f1,f2]      · --area marks coverage · --folds folds old findings in
#   el research <src> "<finding>"     (old form) one finding by source — listed as «без темы»
#                --ref <path:line>    and where to re-check · --area marks coverage like a pair
#   el context unknown "<gap>"        «what do I NOT know that I should?» — written WHEN it
#                --how "<…>"          surfaced · --blocking if it holds the gate
#   el context define "<t>" "<m>"     a term the moment it sounded, with what it means HERE ·
#                --heard "<his words>" his image kept beside the plain phrase, never instead
#   RUNGS — in order, each standing on the ones before; bare → prints what it holds:
#   el context now "<…>" --kind K     how it happens TODAY — flow (his steps by hand) · state
#                                     (what is built, in what shape) · number (the baseline)
#   el context scope [<dim>]          THE BOUNDARY, dimension by dimension; bare PRINTS THE SIX
#                                     QUESTIONS · --in/--out/--blur one line each · --drop
#                                     "<line>" retracts (an amend record, the line stays)
#   el context condition K "<…>"      forbidden · limit · resource · money · tool ·
#                --none "<why>"       «условий нет» is an answer and gets recorded
#   el context requirement "<…>"      --state have|missing|unknown · --ref <anchor>
#   el context beyond "<…>"           right next to the boundary, NOT done · --candidate
#                                     --why "<…>" worth pulling in — his call BEFORE the work
#   el context risk "<…>"             --chance low|mid|high --cost "<…>" --then "<what we do>"
#   THE IDEAL — its checkable parts are PROMISES on the root of the tree (checks.jsonl),
#   not_validated from birth, each REFUSED without --how «чем проверим»:
#   el context success "<his words>"  --observable "<чем видно>" --how "<чем проверим>"
#   el context metric "<name>"        --threshold N --unit U --direction up|down|equal
#                                     --how "<…>" [--baseline N — from the now rung]
#   el context check "<by hand>"      --how "<как>" — the acceptance checklist, phase 5 walks it
#   el context ifr "<paragraph>"      the ideal itself, one paragraph, LAST
#   el context part "<big piece>"     his picture of the road, one at a time · --covers k1,s2
#                                     which promises this piece unfolds (plan integrity reads it)
#   el context clarified "<…>"        the task after clarification — remembers the seq it was
#   el context summary "<…>"          folded over; so does the summary
#   el context areas                  THE COVERAGE MAP: eleven areas, who each comes FROM
#   el accept "<his words>"           HIS WORD over the picture — a record carrying the seq it
#                                     was said over: anything written after it makes it stale
#                                     and el forward asks for a fresh one
#   PAST CONTEXT every command is an AMENDMENT: --why required, --ref <grounds>; nothing is
#                                     overwritten — a new record, and his stale word re-asked
#
# think (phase 2/8) — ten rungs and two flows in records.jsonl (2026-08-27); a tool is a field
#   el think                          the NEEDED DECISIONS with their standing — принято N из M
#   el think need "<question>"        open a NEEDED DECISION (2026-08-27; `fork` still works):
#                                     his word changes the road. WRITTEN IN HIS LANGUAGE — what
#                                     changes for him, no command or phase names. Two or more
#                --option "<name · plus · minus>"   one per option · --recommend "<which and
#                                     why>" · --why-yours "<what only he knows>" REQUIRED when
#                                     he decides: offering a choice obliges you to say why you
#                                     could not choose · --who agent for a fork you decide
#   el think decide <id> "<choice>"   his decision — --words "<his words verbatim>" · --undo
#                --assumed "<why>"    autonomy: decided in his place under a grant, marked
#   el think mirror "<who>" --does "<…>" --affected "<…>"   one person or role per record
#   el think form "<in what shape he gets the result>"
#   el think core "<part>" --rank core|later|never
#   el think promise "<what it must hold>" --how "<чем проверим>" [--breaks-if "<…>"]
#                                     an ENGINEERING promise → checks.jsonl, born here,
#                                     hung on the root; refused without --how
#   el think irreversible "<what cannot be undone>" --guard "<how we protect it>"
#   el think option "<name>" --text "<what it is>" --score <promise>=<value> …
#                [--pros] [--cons] [--parent <id>]   a PATH, scored against every promise —
#                                     the bar is the cells paths × promises
#   el think stress "<how you tried to break it>" --path <id> --promise <id> --held yes|no
#                --why-held "<…>"     на прочность: a path nobody tried to break is empty
#   el think crystal "<how it ripens / the decision>" [--path <id>] [--decided fk1,fk2]
#   el think route "<stage>" [--after <id>,<id>]   stage seeds with deps — the plan cuts them
#   el think risk "<…>" --chance low|mid|high --cost "<…>" --then "<…>"   the risks flow
#   el think tools                    the box by category, which categories this task TOUCHED
#                                     (from the `tool` field), what the mode asks for
#   el think tools <категория>        ONE category tool by tool: what it is · when · how · what
#                                     it gives — the catalogue the page opens on a click
#   el think tools "<took — gave>"    a note about a tool · every command takes --tool "<приём>"
#   el think skip <rung> --why "<…>"  skip a rung on purpose — counts as done, reason kept
#   el accept "<his words>"           HIS WORD over the decision (scope design), with the seq
#   --tool "<приём>" · --from <id>    on any rung: what instrument gave it · what it grew from
#   PAST THINK every command is an AMENDMENT: --why and --ref required; nothing overwritten

# plan (phase 3/8) — stages as RECORDS in records.jsonl (2026-08-27): a node at birth, `set`
#   events for every change, an `amend` for a removal; the network is computed from deps;
#   there is no plan.md and no nodes/ folder. Promises of a stage live in checks.jsonl.
#   el plan                           the map: stages, waves, what is empty, what changed last
#   el plan new s1 "<stage>"          a stage · el plan new s1 wp1 "<package>" — under a stage
#                --after s1 --before s2   INSERT BETWEEN: the new node waits for s1, s2 now
#                                     waits for the new node (one record, one set)
#   el plan set s1 <field> "<text>"   one field — result · sync · covers · deps · executor ·
#                                     inputs · resources · artifacts · storage. sync takes the
#                                     four lines: показываю · увидишь · потрогать · от тебя,
#                                     headed ПОКАЗ · РАЗВИЛКА · РАЗРЕШЕНИЕ
#   el plan promise s1 "<what it must deliver>" --how "<чем проверим>"
#                                     a promise hung on the node (at: S1, born: plan) —
#                                     not_validated until a verdict; the node's colour folds it
#   el plan rm s1                     retracts the node AND its promises (nothing deleted)
#   el plan cancel s1 --why "…"       the node was not needed — an event, the node stays
#   el plan integrity                 coverage top-down: every root promise and big part has a
#                                     stage behind it (covers), or a declared unfold
#   el accept "<his words>"           HIS WORD over the map of stages (scope plan), with the seq
#   el forward --why "…"              out of plan — only with his word

# execute (phase 4/8)
#   el artifact <file...> [--as NAME] put a produced file into the task's artifacts/ and log it ·
#                                     --node s1 [--check 2] files it TO the node (and criterion)
#   el evidence <file...>             the same into evidence/ — proof, not product
#
# validate (phase 5/8)
#   el validate | el check            THE LEDGER: every criterion of every node with its verdict.
#                                     Criteria come from the plan, so they cannot drift into
#                                     something easier to pass; only verdict and proof are added
#   el validate s1 3 --met "<proof>"  answer ONE criterion — AS YOU GO on execute, not in a pile
#                                     at the end · --evidence evidence/<file> names the proof on
#                                     disk (a prose proof is a claim). Four verdicts, no fifth:
#                                     --met "<proof>" · --failed "<what did not hold>" ·
#                                     --declined "<work cancelled, criterion no longer applies>" ·
#                                     --unverified "<work exists, check does not>" — a DEBT that
#                                     holds the phase until answered, declined or waived ·
#                                     --covered-by <node[.N]> --why "…" — a POINTER: proven downstream
#                                     (WP1 ← e2e in WP4); reads as the target reads; a debt until then
#
# close (phase 8/8)
#   el done "<result>" [--as KIND]    close a task WITH a result · kinds: completed |
#                                     closed (understood, no action needed) | dropped | blocked
#                                     completed is refused while any `el todo` remains open ·
#                                     closing puts the task DOWN: nothing is picked up in its place ·
#                                     --dirty "<почему без коммита>" closes over an uncommitted
#                                     worktree ON PURPOSE (the close gate asks for it) ·
#                                     --why "<его слова>" when closing from a phase before close
import argparse, os, re, signal, sys
from .term import emit
from .protocol import MECHANICS
from .context import (cmd_areas, cmd_beyond, cmd_check, cmd_condition, cmd_context_scope,
                      cmd_context_step, cmd_ctx_add, cmd_define, cmd_ifr, cmd_metric, cmd_now,
                      cmd_part, cmd_qa, cmd_requirement, cmd_risk, cmd_success, cmd_unknown)
from .think import cmd_decide, cmd_fork, cmd_forks, cmd_think_skip, cmd_think_step, cmd_think_tools
from .plan import cmd_plan, cmd_sync
from .validate import cmd_validate
from .views import flush_renders
from .navigate import (cmd_ctx, cmd_forward, cmd_left, cmd_next, cmd_phase, cmd_progress,
                       cmd_projects, cmd_resume, cmd_status, cmd_where)
from .owe import cmd_owe
from .commands import (cmd_accept, cmd_ack, cmd_beat, cmd_blueprint, cmd_boot, cmd_brief, cmd_doctor,
                       cmd_done, cmd_feedback, cmd_grant, cmd_halt, cmd_init, cmd_lesson, cmd_log,
                       cmd_mode, cmd_new, cmd_onboard, cmd_put, cmd_reopen, cmd_review, cmd_spawn,
                       cmd_todo, cmd_ui, cmd_use)


HELP_GROUPS = ("general", "look", "move", "owner", "context", "think", "plan", "execute",
               "validate", "close")


def help_blocks():
    """The command map as blocks: [(group, [(first line, [continuation lines])])]."""
    blocks, cur = [], None
    for line in open(os.path.realpath(__file__), encoding="utf-8").read().splitlines():
        # A group heading is «# name …» — a comment line that is neither an entry («#   el …»)
        # nor a continuation (deeper indent): the groups are read from the map itself.
        if re.match(r"^# [a-z]", line):
            cur = (line[2:].strip(), [])
            blocks.append(cur)
        elif line.startswith("#   el ") and cur is not None:
            cur[1].append((line[2:], []))
        # A continuation is ANY comment line deeper than an entry (`#   el …` sits at 3
        # spaces) — by structure, not by a magic indent. The rule used to be «≥20 spaces»,
        # then «≥16»: the OPTION lines of a command (`--raw`, `--depends-on`, `--area`) sat at
        # 16 and were silently dropped while their own deeper continuations still landed, so
        # `el help spawn` printed a sentence whose subject had vanished (caught live
        # 2026-08-22). No indent number is left to drift: below an entry, every comment line
        # until the next entry or group belongs to that entry.
        elif line.startswith("#    ") and cur is not None and cur[1]:
            cur[1][-1][1].append(line[2:])
    return blocks


def cmd_help(args):
    """`el help` — the whole map (one screen, the head says if it cannot be); `el help <группа>`
    — one group; `el help <команда>` — the entries of one command (owner, 2026-08-22)."""
    topic = getattr(args, "topic", None) or ""
    if isinstance(topic, list):
        topic = " ".join(topic)          # `el help plan cover` — a two-word command
    topic = topic.strip().lower()
    blocks = help_blocks()
    out = []
    if not topic:
        out.append("COMMANDS")
        for group, entries in blocks:
            out.append(f"\n  {group}")
            for first, rest in entries:
                out.append(first); out += rest
        # HOW IT WORKS moved to its own screen (2026-08-22): the map alone passed the
        # one-call budget once grant · halt · brief · review · feedback joined it; knowledge
        # in doses — the map here, the mechanics one address away.
        out.append("\n  как это работает — el help how · контракт дозами — el blueprint")
        emit("\n".join(out), parts="el help " + " · ".join(HELP_GROUPS) + " · how · или el help <команда>")
        return 0
    if topic in ("how", "mechanics", "механика"):
        emit(MECHANICS, parts="el blueprint · el blueprint rules · autonomy · search")
        return 0
    if topic in ("names", "имена", "index", "список"):
        # THE INDEX OF NAMES (agent retro, 2026-08-23): to run `el help <команда>` you must
        # first KNOW the name, and finding it meant paging the whole map. Names only, by
        # group, one screen — the map's table of contents.
        out.append("ИМЕНА КОМАНД — подробности: el help <команда>")
        for group, entries in blocks:
            names = []
            for first, _rest in entries:
                m = re.match(r"\s*el\s+([a-z-]+)", first)
                if m and m.group(1) not in names:
                    names.append(m.group(1))
            if names:
                out.append(f"\n  {group}")
                out.append("    " + " · ".join(names))
        print("\n".join(out))
        return 0
    groups = [(g, e) for g, e in blocks if g.split(" ")[0] == topic]
    if groups:
        for group, entries in groups:
            out.append(f"  {group}")
            for first, rest in entries:
                out.append(first); out += rest
        print("\n".join(out))
        return 0
    hits = [(first, rest) for _g, entries in blocks for first, rest in entries
            if re.match(rf"  el {re.escape(topic)}(\s|$)", first)]
    # a SUB-VERB («cover», «unfold», «decide») or a bare word: any entry whose first line
    # names it (feedback 2026-08-24: `el help cover` exited 1 while `el plan cover` worked)
    if not hits:
        hits = [(first, rest) for _g, entries in blocks for first, rest in entries
                if re.search(rf"\bel \S+ {re.escape(topic)}(\s|$)", first)]
    if not hits:
        hits = [(first, rest) for _g, entries in blocks for first, rest in entries
                if re.search(rf"\b{re.escape(topic)}\b", first)]
    if not hits:
        print(f"нет такой команды или группы «{topic}» · группы: {' · '.join(HELP_GROUPS)} · "
              "how — механика · все команды: el help", file=sys.stderr)
        return 1
    for first, rest in hits:
        out.append(first); out += rest
    print("\n".join(out))
    return 0



def _hoist_options(ap, argv):
    """Let a flag sit ANYWHERE in the line — `el plan set s1 sync --replace "<text>"` included.

    argparse reads one `nargs="*"` positional in a single gulp: the words up to the first
    flag are the list, and whatever follows the flag is «unrecognized arguments» — printed
    back verbatim, exit 2, nothing written. An agent read that echo as success and filed the
    stop field as broken (feedback pool, 2026-08-24: «печатает переданный текст обратно,
    поле остаётся ✗»). The words were fine; only the flag stood between them.

    So before parsing, the flags the addressed (sub)command KNOWS — with their values —
    are moved up front and the words keep their order. Unknown `--flags` stay where they
    were, so a typo still fails loudly instead of landing inside a field as text."""
    parser, depth = ap, 0
    while depth < len(argv):
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        nxt = subs[0]._name_parser_map.get(argv[depth]) if subs else None
        if nxt is None:
            break
        parser, depth = nxt, depth + 1
    if depth == 0:
        return argv
    takes_value = {}
    for a in parser._actions:
        for flag in a.option_strings:
            takes_value[flag] = a.nargs != 0          # store_true → nargs == 0
    opts, words = [], []
    i = depth
    while i < len(argv):
        w = argv[i]
        name = w.split("=", 1)[0]
        if name in takes_value:
            opts.append(w)
            if takes_value[name] and "=" not in w and i + 1 < len(argv):
                i += 1
                opts.append(argv[i])
        else:
            words.append(w)
        i += 1
    return argv[:depth] + opts + words


def main():
    """The door: run the command under the flight recorder (el/calls.py) — every call
    leaves one line in the storage's metadata/calls.jsonl, including the ones argparse
    refused (rc 2). The body is _dispatch; the recorder wraps it so the screen is counted
    and the line is written whatever the command did."""
    # `el ctx | head` must not end in a traceback: let a closed pipe end the process quietly.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    from .calls import run_recorded
    return run_recorded(_dispatch, sys.argv[1:])


def _dispatch(argv):
    ap = argparse.ArgumentParser(prog="el", add_help=False)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("init", add_help=False); p.add_argument("--dir"); p.set_defaults(fn=cmd_init)
    p = sub.add_parser("new", add_help=False); p.add_argument("description"); p.add_argument("--id"); p.add_argument("--raw"); p.add_argument("--mode"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_new)
    p = sub.add_parser("boot", add_help=False); p.add_argument("description", nargs="?", default=""); p.add_argument("--id"); p.add_argument("--raw"); p.add_argument("--source"); p.add_argument("--mode"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_boot)
    # `context` is a phase GROUP: bare call shows what is gathered, sub-commands act inside
    # the phase. Nested subparsers keep the command tree shaped like the process itself.
    for nm in ("context", "ctx"):
        p = sub.add_parser(nm, add_help=False)
        p.add_argument("--line", action="store_true")
        p.add_argument("--json", action="store_true")
        p.add_argument("--task")
        p.add_argument("--section"); p.add_argument("--full", action="store_true")
        p.set_defaults(fn=cmd_ctx)
        inner = p.add_subparsers(dest="ctx_cmd")
        # THE FLOWS — written all phase long, whenever the thing happens
        q = inner.add_parser("qa", add_help=False)
        q.add_argument("question", nargs="?"); q.add_argument("answer", nargs="?")
        q.add_argument("--list", action="store_true")
        q.add_argument("--round", type=int); q.add_argument("--new-round", action="store_true")
        q.add_argument("--area"); q.add_argument("--options"); q.add_argument("--assumed")
        q.add_argument("--why"); q.add_argument("--ref", action="append")
        q.add_argument("--task"); q.set_defaults(fn=cmd_qa)
        a = inner.add_parser("add", add_help=False)
        a.add_argument("source", nargs="?"); a.add_argument("finding", nargs="?")
        a.add_argument("--ref", action="append"); a.add_argument("--area")
        a.add_argument("--task"); a.set_defaults(fn=cmd_ctx_add)
        u = inner.add_parser("unknown", add_help=False)
        u.add_argument("text", nargs="?"); u.add_argument("--how"); u.add_argument("--risk")
        u.add_argument("--blocking", action="store_true")
        u.add_argument("--why"); u.add_argument("--ref", action="append")
        u.add_argument("--task"); u.set_defaults(fn=cmd_unknown)
        d = inner.add_parser("define", add_help=False)
        d.add_argument("term", nargs="?"); d.add_argument("means", nargs="?"); d.add_argument("--heard")
        d.add_argument("--why"); d.add_argument("--ref", action="append")
        d.add_argument("--task"); d.set_defaults(fn=cmd_define)
        # THE RUNGS — in order; every one prints what it holds when called bare
        n = inner.add_parser("now", add_help=False)
        n.add_argument("text", nargs="?"); n.add_argument("--kind"); n.add_argument("--ref", action="append")
        n.add_argument("--why"); n.add_argument("--task"); n.set_defaults(fn=cmd_now)
        sc = inner.add_parser("scope", add_help=False)
        sc.add_argument("dim", nargs="?", default="")
        sc.add_argument("--in", dest="inside"); sc.add_argument("--out")
        sc.add_argument("--blur"); sc.add_argument("--replace", action="store_true")
        sc.add_argument("--drop"); sc.add_argument("--why"); sc.add_argument("--ref", action="append")
        sc.add_argument("--task"); sc.set_defaults(fn=cmd_context_scope)
        c = inner.add_parser("condition", add_help=False)
        c.add_argument("kind", nargs="?"); c.add_argument("text", nargs="?"); c.add_argument("--none")
        c.add_argument("--ref", action="append"); c.add_argument("--why")
        c.add_argument("--task"); c.set_defaults(fn=cmd_condition)
        rq = inner.add_parser("requirement", add_help=False)
        rq.add_argument("text", nargs="?"); rq.add_argument("--state"); rq.add_argument("--ref", action="append")
        rq.add_argument("--why"); rq.add_argument("--task"); rq.set_defaults(fn=cmd_requirement)
        b = inner.add_parser("beyond", add_help=False)
        b.add_argument("text", nargs="?"); b.add_argument("--candidate", action="store_true")
        b.add_argument("--why"); b.add_argument("--ref", action="append")
        b.add_argument("--task"); b.set_defaults(fn=cmd_beyond)
        rk = inner.add_parser("risk", add_help=False)
        rk.add_argument("text", nargs="?"); rk.add_argument("--chance"); rk.add_argument("--cost")
        rk.add_argument("--then"); rk.add_argument("--why"); rk.add_argument("--ref", action="append")
        rk.add_argument("--task"); rk.set_defaults(fn=cmd_risk)
        # the ideal: three kinds of PROMISE (each needs --how) and the paragraph itself
        su = inner.add_parser("success", add_help=False)
        su.add_argument("text", nargs="?"); su.add_argument("--observable"); su.add_argument("--how")
        su.add_argument("--why"); su.add_argument("--ref", action="append")
        su.add_argument("--task"); su.set_defaults(fn=cmd_success)
        me = inner.add_parser("metric", add_help=False)
        me.add_argument("text", nargs="?"); me.add_argument("--threshold", type=float)
        me.add_argument("--unit"); me.add_argument("--direction"); me.add_argument("--how")
        me.add_argument("--baseline", type=float)
        me.add_argument("--why"); me.add_argument("--ref", action="append")
        me.add_argument("--task"); me.set_defaults(fn=cmd_metric)
        ck = inner.add_parser("check", add_help=False)
        ck.add_argument("text", nargs="?"); ck.add_argument("--how")
        ck.add_argument("--why"); ck.add_argument("--ref", action="append")
        ck.add_argument("--task"); ck.set_defaults(fn=cmd_check)
        ifr = inner.add_parser("ifr", add_help=False)
        ifr.add_argument("text", nargs="?"); ifr.add_argument("--why"); ifr.add_argument("--ref", action="append")
        ifr.add_argument("--task"); ifr.set_defaults(fn=cmd_ifr)
        pt = inner.add_parser("part", add_help=False)
        pt.add_argument("text", nargs="?"); pt.add_argument("--covers")
        pt.add_argument("--why"); pt.add_argument("--ref", action="append")
        pt.add_argument("--task"); pt.set_defaults(fn=cmd_part)
        # the two fold-ups
        for _k in ("clarified", "summary"):
            w = inner.add_parser(_k, add_help=False)
            w.add_argument("text", nargs="?", default="")
            w.add_argument("--task"); w.add_argument("--why"); w.add_argument("--ref", action="append")
            w.set_defaults(fn=cmd_context_step, step_key=_k)
        r = inner.add_parser("areas", add_help=False)
        r.add_argument("--task"); r.set_defaults(fn=cmd_areas)
    p = sub.add_parser("blueprint", add_help=False); p.add_argument("part", nargs="?"); p.add_argument("--mode"); p.set_defaults(fn=cmd_blueprint)
    p = sub.add_parser("mode", add_help=False); p.add_argument("mode", nargs="?"); p.add_argument("--why"); p.add_argument("--task"); p.set_defaults(fn=cmd_mode)
    p = sub.add_parser("status", add_help=False); p.add_argument("--short", action="store_true"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("resume", add_help=False); p.add_argument("--task"); p.set_defaults(fn=cmd_resume)
    for nm in ("projects", "ls"):
        sub.add_parser(nm, add_help=False).set_defaults(fn=cmd_projects)
    for nm in ("validate", "check"):
        q = sub.add_parser(nm, add_help=False)
        q.add_argument("words", nargs="*")
        q.add_argument("--met")
        q.add_argument("--failed")
        q.add_argument("--skip")          # kept only to refuse it with guidance
        q.add_argument("--declined")
        q.add_argument("--unverified")
        q.add_argument("--covered-by", dest="covered_by")   # a pointer: verdict lives there
        q.add_argument("--why")           # its reason — required with --covered-by
        q.add_argument("--evidence")      # the file in the project that proves it
        q.add_argument("--task")
        q.set_defaults(fn=cmd_validate)
    for nm in ("artifact", "evidence"):
        q = sub.add_parser(nm, add_help=False)
        q.add_argument("files", nargs="+")
        q.add_argument("--as", dest="rename")
        q.add_argument("--why")
        q.add_argument("--node"); q.add_argument("--check", type=int)
        q.add_argument("--task")
        q.set_defaults(fn=cmd_put, kind="artifacts" if nm == "artifact" else "evidence")
    for nm in ("left", "rest"):
        q = sub.add_parser(nm, add_help=False); q.add_argument("--task"); q.set_defaults(fn=cmd_left)
    for nm in ("progress", "story"):
        q = sub.add_parser(nm, add_help=False); q.add_argument("part", nargs="?"); q.add_argument("--task")
        q.set_defaults(fn=cmd_progress)
    p = sub.add_parser("next", add_help=False); p.add_argument("--task")
    p.add_argument("--short", action="store_true"); p.set_defaults(fn=cmd_next)
    p = sub.add_parser("beat", add_help=False); p.add_argument("name"); p.add_argument("--ref"); p.add_argument("--task"); p.set_defaults(fn=cmd_beat)
    p = sub.add_parser("use", add_help=False); p.add_argument("task"); p.set_defaults(fn=cmd_use)
    p = sub.add_parser("forward", add_help=False); p.add_argument("--why"); p.add_argument("--waive"); p.add_argument("--task"); p.set_defaults(fn=cmd_forward)
    for nm in ("phase", "back", "назад"):
        p = sub.add_parser(nm, add_help=False); p.add_argument("name")
        p.add_argument("--task"); p.add_argument("--why"); p.set_defaults(fn=cmd_phase)
    p = sub.add_parser("done", add_help=False); p.add_argument("result"); p.add_argument("--as", dest="outcome", default="completed"); p.add_argument("--task"); p.add_argument("--dirty")
    p.add_argument("--why"); p.set_defaults(fn=cmd_done)
    p = sub.add_parser("log", add_help=False); p.add_argument("text"); p.add_argument("--type", default="note")
    p.add_argument("--node")                        # aim at a node other than the one in work
    p.add_argument("--free", action="store_true")   # on purpose off any node
    p.add_argument("--task"); p.set_defaults(fn=cmd_log)
    for nm in ("where", "path"):
        sub.add_parser(nm, add_help=False).set_defaults(fn=cmd_where)
    # `accept` is top-level, not under `context`: the owner's word is asked for on more than
    # one phase, and burying it inside a phase group would make it look like context's private
    # affair. It writes to whichever phase the task is actually on.
    # `think` is a phase GROUP, like `context`: its commands belong to it and are called
    # through it, so `help` stays a map of the process rather than a pile of verbs.
    t = sub.add_parser("think", add_help=False)
    t.add_argument("--task"); t.set_defaults(fn=cmd_forks)
    ti = t.add_subparsers(dest="think_cmd")
    def _common(x):
        x.add_argument("--tool"); x.add_argument("--from", dest="from_")
        x.add_argument("--why"); x.add_argument("--ref", action="append"); x.add_argument("--task")
    for _name in ("need", "fork"):          # `need` is the name; `fork` — the old spelling
        f = ti.add_parser(_name, add_help=False)
        f.add_argument("id", nargs="?"); f.add_argument("text", nargs="?")
        f.add_argument("--who"); f.add_argument("--option", action="append")
        f.add_argument("--recommend"); f.add_argument("--why-yours", dest="why_yours")
        f.add_argument("--decide"); f.add_argument("--preview"); f.add_argument("--replaces")
        _common(f); f.set_defaults(fn=cmd_fork)
    d = ti.add_parser("decide", add_help=False)
    d.add_argument("id", nargs="?"); d.add_argument("choice", nargs="?")
    d.add_argument("--words"); d.add_argument("--why"); d.add_argument("--fixed"); d.add_argument("--fidelity")
    d.add_argument("--assumed"); d.add_argument("--undo"); d.add_argument("--task")
    d.set_defaults(fn=cmd_decide)
    fl = ti.add_parser("forks", add_help=False)
    fl.add_argument("--task"); fl.set_defaults(fn=cmd_forks)
    tt = ti.add_parser("tools", add_help=False)
    tt.add_argument("text", nargs="?"); _common(tt); tt.set_defaults(fn=cmd_think_tools)
    ts = ti.add_parser("skip", add_help=False)
    ts.add_argument("step", nargs="?"); ts.add_argument("--why"); ts.add_argument("--task")
    ts.set_defaults(fn=cmd_think_skip)
    rk = ti.add_parser("risk", add_help=False)
    rk.add_argument("text", nargs="?"); rk.add_argument("--chance"); rk.add_argument("--cost"); rk.add_argument("--then")
    _common(rk); rk.set_defaults(fn=cmd_risk)
    # THE RUNGS — one record each; `--tool` names the instrument it came from
    for _k, _names, _extra in (
            ("mirror", ("mirror",), ("--does", "--affected")),
            ("form", ("form",), ()),
            ("core", ("core",), ("--rank",)),
            ("promises", ("promise", "promises"), ("--how", "--breaks-if")),
            ("reversibility", ("irreversible", "reversibility", "undo"), ("--guard",)),
            ("options", ("option", "options", "path"), ("--text:body", "--score+", "--pros", "--cons", "--parent")),
            ("stress", ("stress",), ("--path", "--promise", "--held", "--why-held")),
            ("crystal", ("crystal",), ("--path", "--decided")),
            ("route", ("route", "order"), ("--after",))):
        tsx = ti.add_parser(_names[0], add_help=False, aliases=list(_names[1:]))
        tsx.add_argument("text", nargs="?")
        for _e in _extra:
            if _e.endswith("+"): tsx.add_argument(_e[:-1], action="append")
            elif ":" in _e:
                _flag, _dest = _e.split(":"); tsx.add_argument(_flag, dest=_dest)
            else: tsx.add_argument(_e)
        _common(tsx)
        tsx.set_defaults(fn=cmd_think_step, step_key=_k, step_name=_names[0])

    pl = sub.add_parser("plan", add_help=False)
    pl.add_argument("words", nargs="*"); pl.add_argument("--task")
    pl.add_argument("--force", action="store_true")
    pl.add_argument("--replace", action="store_true")
    pl.add_argument("--why")                       # el plan block / park
    pl.add_argument("--switch")                    # el plan start <другой> --switch "<почему>" — сменить узел в работе
    pl.add_argument("--owe", type=int)             # el plan block — держит долг владельца #n
    pl.add_argument("--file")                      # el plan set <узел> --file <контракт.md> | -
    pl.add_argument("--after")                     # el plan unfold — после чего раскроется
    pl.add_argument("--how")                       # el plan promise <узел> "<…>" --how "<чем проверим>"
    pl.add_argument("--before")                    # el plan new s4 "…" --after s1 --before s2 — вставить между
    pl.set_defaults(fn=cmd_plan)

    sy = sub.add_parser("sync", add_help=False)
    sy.add_argument("--task"); sy.set_defaults(fn=cmd_sync)
    ro = sub.add_parser("reopen", add_help=False)
    ro.add_argument("task_id", nargs="?"); ro.add_argument("--why")
    ro.set_defaults(fn=cmd_reopen)
    sp = sub.add_parser("spawn", add_help=False)
    sp.add_argument("description", nargs="?"); sp.add_argument("--id"); sp.add_argument("--why")
    sp.add_argument("--depends-on", dest="depends_on"); sp.add_argument("--raw")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(fn=cmd_spawn)

    p = sub.add_parser("todo", add_help=False)
    p.add_argument("text", nargs="?"); p.add_argument("--when"); p.add_argument("--why")
    p.add_argument("--every")   # a reminder: «каждый день» — a standing duty, not a step
    p.add_argument("--list", action="store_true"); p.add_argument("--done", type=int)
    p.add_argument("--all", action="store_true")   # closed items too
    p.add_argument("--task"); p.set_defaults(fn=cmd_todo)
    p = sub.add_parser("accept", add_help=False)
    p.add_argument("words", nargs="?"); p.add_argument("--on"); p.add_argument("--task")
    p.add_argument("--for", dest="for_"); p.add_argument("--close", action="store_true")
    p.add_argument("--assumed")
    p.set_defaults(fn=cmd_accept)
    # the autonomy layer: the grant · his changes and the natural end · the hold · the review
    p = sub.add_parser("grant", add_help=False)
    p.add_argument("words", nargs="*"); p.add_argument("--until"); p.add_argument("--no")
    p.add_argument("--name"); p.add_argument("--hours")
    p.add_argument("--task"); p.set_defaults(fn=cmd_grant)
    p = sub.add_parser("halt", add_help=False)
    p.add_argument("why", nargs="?"); p.add_argument("--by"); p.add_argument("--task"); p.set_defaults(fn=cmd_halt)
    p = sub.add_parser("review", add_help=False); p.add_argument("--task"); p.set_defaults(fn=cmd_review)
    # the owner's debt: an answer only he can bring and does not have yet (2026-08-24)
    p = sub.add_parser("owe", add_help=False)
    p.add_argument("words", nargs="*"); p.add_argument("--how"); p.add_argument("--kind")
    p.add_argument("--by"); p.add_argument("--area"); p.add_argument("--holds", action="append")
    p.add_argument("--why"); p.add_argument("--task"); p.set_defaults(fn=cmd_owe)
    p = sub.add_parser("brief", add_help=False)
    p.add_argument("text", nargs="?"); p.add_argument("--task"); p.set_defaults(fn=cmd_brief)
    p = sub.add_parser("ack", add_help=False)
    p.add_argument("what", nargs="?"); p.add_argument("--why"); p.add_argument("--task")
    p.set_defaults(fn=cmd_ack)
    p = sub.add_parser("doctor", add_help=False)
    p.add_argument("--task"); p.add_argument("--fix", action="store_true"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("lesson", add_help=False)
    p.add_argument("text"); p.add_argument("--task"); p.set_defaults(fn=cmd_lesson)
    p = sub.add_parser("research", add_help=False)
    p.add_argument("source", nargs="?"); p.add_argument("finding", nargs="?")   # topic · (legacy finding)
    p.add_argument("--summary"); p.add_argument("--file"); p.add_argument("--folds")
    p.add_argument("--ref", action="append"); p.add_argument("--area")
    p.add_argument("--task"); p.set_defaults(fn=cmd_ctx_add)
    p = sub.add_parser("ui", add_help=False)
    p.add_argument("word", nargs="?")            # `el ui update` reads naturally; ignored
    p.add_argument("--open", action="store_true")
    p.set_defaults(fn=cmd_ui)
    # `feedback` is the tool's own inbox — one positional list, read by shape: bare = the pool ·
    # "done <id>" = remove · a lone existing id = show · anything else = the text of a new review.
    p = sub.add_parser("feedback", add_help=False)
    p.add_argument("words", nargs="*"); p.add_argument("--from", dest="from_")
    p.add_argument("--about"); p.add_argument("--by"); p.add_argument("--file")
    p.set_defaults(fn=cmd_feedback)
    p = sub.add_parser("help", add_help=False); p.add_argument("topic", nargs="*"); p.set_defaults(fn=cmd_help)

    # `-h` / `--help` cannot be subcommand NAMES: argparse reads a leading dash as an option
    # on the top parser and errors out before it ever dispatches. They are intercepted here
    # instead, and anywhere in the line — there are no per-command help pages, so asking for
    # help must never be able to fail.
    if not argv:
        return cmd_onboard(None)
    if "-h" in argv or "--help" in argv:
        # `el done --help` asks about DONE, not about everything (recorder 2026-08-25: the
        # whole 25 000-character map came back twice in one session)
        topic = " ".join(a for a in argv if not a.startswith("-"))
        return cmd_help(argparse.Namespace(topic=topic))
    # `context big-parts` — the file is big-parts.md, the section key is `parts`; both work
    if len(argv) >= 2 and argv[0] in ("context", "ctx") and argv[1] in ("big-parts", "parts"):
        argv = [argv[0], "part"] + argv[2:]

    args = ap.parse_args(_hoist_options(ap, argv))
    # A LITERAL "\n" typed inside a shell string — the common case when an agent writes a
    # four-line stop or a bullet list in one argument — becomes a real newline in every text
    # argument (owner, 2026-08-22: «тестами\nпотрогать: N/A — перенос строк не работает»).
    # The shell will not do it for him; the tool does, once, here.
    for _k, _v in list(vars(args).items()):
        if isinstance(_v, str) and "\\n" in _v:
            setattr(args, _k, _v.replace("\\n", "\n"))
        elif isinstance(_v, list) and any(isinstance(x, str) and "\\n" in x for x in _v):
            setattr(args, _k, [x.replace("\\n", "\n") if isinstance(x, str) else x for x in _v])
    rc = args.fn(args) if getattr(args, "fn", None) else cmd_help(args)
    # THE SCREEN LEAVES BEFORE THE PAGES ARE DRAWN. Rendering the HTML views is a side job
    # after the command; a harness that caps a call by time and kills the process mid-render
    # would take the buffered screen down with it — the one way `el validate` can hand back
    # an empty screen (feedback pool, 2026-08-24). Flush first: the answer is already out.
    sys.stdout.flush()
    flush_renders()
    return rc
