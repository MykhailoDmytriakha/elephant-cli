"""The entry: the command map, the parser, the dispatcher, `el help`.

`el help` prints the map below — it is read straight from this file, so the map and
the parser that registers the commands sit together and cannot drift apart.
"""
# general — storage · tasks · the hand
#   el init [--dir PATH]              create the .projects storage at the project root
#   el new "<description>" --id NAME  create a task; up to 5 words, the date is prepended:
#                                     2026-08-20-harvest-dislikes-and-dataset.
#                                     --raw "<verbatim>" records the human's raw request
#                                     WORD FOR WORD into init/request.md. THE SAME TASK AGAIN
#                                     is refused: words of the new one against name + request of
#                                     every open task — continue that one (el use) or --force
#   el boot "<description>" --id NAME idempotent: init if missing + new if missing + status line ·
#                                     --mode light|soft|strict sets the task's TIGHTNESS at birth ·
#                                     --raw on an EXISTING task appends «Повтор запроса» verbatim
#   el use <id>                       TAKE a task in hand — the one commands act on without
#                                     --task (a `hold` event; `el done` puts it down → idle)
#   el projects | el ls               list of tasks: phase, last touched, description, and the
#                                     REQUEST in his words — look here before opening a task
#   el spawn "<description>" --id N   a NEW wish that surfaced mid-flow becomes its own task,
#                                     with a note of where it came from; the task in hand stays
#                                     current. Neither swallowed nor lost. The test for a task
#                                     rather than a later stage: does it need its OWN context?
#                --raw "<verbatim>"    the human's words WORD FOR WORD into init/request.md —
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
#                                     to ANOTHER task — a note about a task you are not standing
#                                     in; the hand does not move (no write ever moves it)
#   el beat <name> [--ref FILE]       mark a beat that leaves no file of its own · --task <id>
#   el todo "<what>" --when <phase>   park work that belongs to a LATER phase; `el next`
#                                     surfaces it when that phase arrives · bare / --list: the
#                                     OPEN items, NUMBERED — N is what --done takes (open items
#                                     in file order); closed ones fold away, --all shows them ·
#                                     --done N with an optional note to close item N
#   el brief ["<text>"]               THE SHEET a returning agent reads first: baseline · measure ·
#                                     best · not again · now. Rewritten whole, ≤ 20 lines / 1500
#                                     chars; el and el status print it first
#   el lesson "<text>"                a lesson that OUTLIVES its task → <storage>/lessons.md;
#                                     bare `el` prints them, so the next agent starts warned
#   el feedback "<text>"              THE TOOL'S OWN INBOX — what in `el` got in the way, what
#                                     helped; one file per review in the skill's feedback/ (the
#                                     pool a meta-session reads, fixes, deletes) · --about · --by ·
#                                     --from user (his words) · --file · <id> · done <id>
#
# look — the three questions and the map
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
#   el doctor                         integrity: criteria answered but node open · two nodes in
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
#                                     --assumed "<why>" BORROWS it under a grant (el grant): what
#                                     you take for his word, marked as a loan; never --for final.
#                                     Context does not open without it, and --waive does not
#                                     excuse it: a checklist may not stand in for a human ·
#                                     --for <scope> says what the word is OVER: context · design:<fork>
#                                     · plan · node:<id> · observation:<id> · final (unscoped =
#                                     the phase's natural scope; only `final` counts on validate)
#                                     · --close with node:<id> closes that node with his words
#   el ack "<trace|area:x>" --why     leave a past-phase tail as is, on purpose — «за спиной»
#                                     stops repeating it
#   el grant "<his words>"            AUTONOMY — his word that opens it («работай сам»), verbatim;
#                                     bare: the state · --until · --no "<what not to touch>". While
#                                     it stands a missing word is BORROWED (--assumed); never the
#                                     final word · el blueprint autonomy — the whole law
#   el review                         the ledger of borrowed words — paid or DEBT; his el accept
#                                     over the same scope pays; completed is refused with a debt
#   el halt "<why · what is needed>"  autonomy stops HERE — the grant reaches no further. Not
#                                     «done»: task open, in hand; status prints it first; a new
#                                     el grant («продолжай») or his word lifts it
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
# context (phase 1/8)
#   el research [<source> "<finding>" --ref <anchor>]
#                                     a RESEARCH finding into research/<source>.md — the source
#                                     is what you looked AT (code · db · cluster · jira · any
#                                     name), the anchor is where to re-check · bare: the folder
#                                     — every source with its findings count and size, and the
#                                     command that opens it whole: el ctx --section <source>
#   el context [--section X]          THE WHOLE CONTEXT OF THE TASK, top to bottom, AS CONTENT
#                                     — original request · questions with their answers ·
#                                     clarified task · boundary · requirements · ideal result ·
#                                     what reaches past it · summary · what is still unknown ·
#                                     the owner's word. Prints the real files, never a link to
#                                     them: a pointer is not a presentation, and that pointer
#                                     is how the ideal result stayed invisible for a whole day
#   el context qa "<q>" "<a>"         record a clarifying pair AFTER the owner answered.
#                --area <area>        REQUIRED — which of the ten areas it covers. Counting
#                                     pairs measured nothing; coverage shows where you never went
#                --assumed "<why>"    autonomy: the question you WOULD have asked and the answer
#                                     you assume (the narrowest one) — marked, a debt his word
#                                     over the picture pays
#   el context add <src> "<finding>"  record a LOCAL source: what was looked at and what it
#                                     showed · --ref FILE[:LINE] for each anchor · --area to
#                                     mark which area it covers, exactly like a Q&A pair does ·
#                                     appends to context/<src>.md — code, db, logs, devices, ui
#   el context scope [<dim>]          THE BOUNDARY, asked dimension by dimension. Bare it PRINTS
#                                     THE SIX QUESTIONS (what·why·who·where·when·how) and shows
#                                     which are still empty · --in / --out / --blur record one.
#                                     A boundary is answers, never the agent's own prose
#   el context areas                  THE COVERAGE MAP: ten areas, who each comes FROM (ask the
#                                     owner / fetch it yourself), how many pairs each has
#   el context definitions "<t — m>"  the project's shared vocabulary: a term heard in his
#                                     speech lands here with what it means IN THIS project
#   el context success "<…>"          THE IDEAL RESULT, five parts, each its own file, in order:
#   el context outcomes "<…>"         success criteria (when is it a success, his words) ·
#   el context metrics "<…>"          expected outcomes (what will exist) · quality metrics
#   el context checklist "- …"        (numbers with thresholds) · the ACCEPTANCE CHECKLIST (what
#   el context ifr "<…>"              he checks by hand — phase 5 walks it) · the ideal itself,
#                                     one paragraph, written LAST. Grown from his answers to
#                                     «как поймёшь, что получилось?» (--area check)
#   el context beyond "<text>"        closes the frame: what sits RIGHT NEXT to the boundary
#                                     and is deliberately NOT done — said BEFORE the work, or
#                                     it surfaces mid-execution as "I thought that was in"
#   el context unknown "<gap>"        "what do I NOT know that I should know?" — condition 2,
#                                     the most ignored one; silence is not an answer
#   el context <part> "…" --why "…" --ref <основание>   PAST CONTEXT the same command is an
#                                     AMENDMENT: appended under its date and phase, never
#                                     overwriting (--replace refused); --why is required. The
#                                     boundary moves with el context scope <dim> --out "…"
#                                     --drop "<old line>" — the old line is struck, not erased.
#                                     An amendment after his word re-opens it: el next says so,
#                                     el forward wants a fresh el accept (or --waive)
#
# think (phase 2/8)
#   el think                          the state of every fork: who decides, how many options,
#                                     what was chosen, which are still open
#   el think fork <id> "<question>"   open a fork · --who owner|agent says whose call it is ·
#                                     --decide "<what exactly he must decide at this gate>" ·
#                                     --option "<name>" --cost "<what it costs>" [--model "<what
#                                     it is>"] [--falsifier "<which observation kills it>"]
#                                     [--recommend] adds an option · --preview <html|dir> — THE
#                                     THING TO TOUCH: one interactive page with every variant
#                                     side by side; copied into thinking/previews/ so the project
#                                     page can open it and the link outlives scratch folders ·
#                                     --recommendation "<the agent's working recommendation>".
#                                     One command writes both files: decisions.md (the ledger the
#                                     gates read) and options.md (the dossier, gate by gate)
#   el think decide <id> "<option>"   close it · --words "<his words>" when the owner decides,
#                                     --why when you did · fewer than three options is refused
#                                     unless --narrow says why the rest fell away ·
#                                     --fixed "<what his word settled — the basis the next gate
#                                     stands on>" · --assumed "<why>" --undo "<how to reverse>"
#                                     borrows HIS fork under a grant; prefer the reversible path
#   el think tools                    THE OPEN BOX: families of thinking instruments to pick
#                                     from · with text, records which was taken and what it gave
#   el think skip <step> --why "..."  a step this task genuinely does not need — recorded, never
#                                     silent; forks and the choice cannot be skipped
#   el think <step> "<text>"          write one step of the ladder — mirror · form · core ·
#                                     ideals · research · baseline · shoals · reversibility ·
#                                     crystal · refute · order; bare it prints the step; text
#                                     APPENDS (--ref <основание> adds a footnote)
#   el think crystal "<record>" [--ref f1]   THE CRYSTALLISATION: every record lands under its
#                                     own date — what became clear, what moved, why. The last
#                                     record is the solution as it crystallised; the chain
#                                     shows how it got there
#
# plan (phase 3/8)
#   el plan                           the whole plan: the network plan, then the tree of nodes
#                                     with fill state at every level
#   el plan s1                        one node in full: its eight fields and what is inside it
#   el plan s1 wp1                    the same, deeper. THE PATH IS THE HIERARCHY — depth says
#                                     the level (stage · work · task · subtask) and the parent,
#                                     so neither has to be declared
#   el plan new s1 wp1 "<name>"       create it there. Refused if the parent still has empty
#                                     fields: expand only the level you stand on (§5). A sibling
#                                     with the SAME name is refused too (a repeated hypothesis —
#                                     search tasks): name how this one differs, or --force
#   el plan set s1 wp1 check "..."    fill one field · result · check · resources · artifacts ·
#                                     storage · inputs · deps · executor · sync. Appends, so
#                                     criteria accumulate one at a time · --replace to start over
#   el plan done s1 wp1 "<result>"    close a node. REFUSED if it ends in a stop that has not
#                                     happened yet — a stop you can drive past is not a stop
#   el plan start s1 wp1              THE NODE IN WORK — one at a time (the previous steps back
#                                     to open); prints its contract and what to do next. Work on
#                                     EXECUTE goes node by node: start → do → criteria as you go
#                                     → traces --node → wait at the stop → done
#   el plan wait s1 wp1 "<shown>"     the baton goes to the owner: shown, waiting for his word —
#                                     the agent does not drive on; his word: el accept --for node:…
#   el plan block s1 --why "…"        stuck on something named (--owe <n>: on the owner's debt)
#                                     · el plan park s1 --why "…" sets a node aside ON PURPOSE
#                                     (terminal for the gates, like done)
#   el plan cover s1 ifr 2 3          WHAT THIS NODE CLOSES from the goal — items of the
#                                     acceptance checklist (ifr) and the owner's big pieces
#                                     (part). Read top-down this is ROUTE INTEGRITY
#   el plan integrity                 THE ROUTE SEEN TOP-DOWN: every piece of the goal and who
#                                     covers it. A piece nobody covers is work we are simply not
#                                     going to do — «целостность маршрута» (owner, 2026-08-24)
#   el plan unfold s3 "<what becomes known>" --after s2
#                                     A DECLARED BLANK SPOT: here the plan cannot be built until
#                                     something is learned. Counts as coverage — a hole named out
#                                     loud is part of the route; a silent one is a failure
#   el plan rm s1 wp1                 remove a node that has nothing inside it
#   el sync                           THE STOPS ALONG THE ROAD: which are passed, which comes
#                                     next, what exactly gets shown at each. Planned in the plan,
#                                     never improvised — a stop decided in the moment is decided
#                                     by whoever is tired, and the one that mattered gets skipped
#
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
#                                     holds the phase until answered, declined or waived
#
# close (phase 8/8)
#   el done "<result>" [--as KIND]    close a task WITH a result · kinds: completed |
#                                     closed (understood, no action needed) | dropped | blocked
#                                     completed is refused while any `el todo` remains open ·
#                                     closing puts the task DOWN: nothing is picked up in its place
import argparse, os, re, signal, sys
from .term import emit
from .protocol import MECHANICS
from .context import (cmd_areas, cmd_beyond, cmd_context_scope, cmd_context_step,
                      cmd_ctx_add, cmd_qa, cmd_unknown)
from .think import cmd_decide, cmd_fork, cmd_forks, cmd_think_skip, cmd_think_step, cmd_think_tools
from .plan import cmd_plan, cmd_sync
from .validate import cmd_validate
from .views import flush_renders
from .navigate import (cmd_ctx, cmd_forward, cmd_left, cmd_next, cmd_phase, cmd_progress,
                       cmd_projects, cmd_status, cmd_where)
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
    topic = (getattr(args, "topic", None) or "").strip().lower()
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
    if not hits:
        print(f"нет такой команды или группы «{topic}» · группы: {' · '.join(HELP_GROUPS)} · "
              "how — механика · все команды: el help", file=sys.stderr)
        return 1
    for first, rest in hits:
        out.append(first); out += rest
    print("\n".join(out))
    return 0


def main():
    # `el ctx | head` must not end in a traceback: let a closed pipe end the process quietly.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    ap = argparse.ArgumentParser(prog="el", add_help=False)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("init", add_help=False); p.add_argument("--dir"); p.set_defaults(fn=cmd_init)
    p = sub.add_parser("new", add_help=False); p.add_argument("description"); p.add_argument("--id"); p.add_argument("--raw"); p.add_argument("--mode"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_new)
    p = sub.add_parser("boot", add_help=False); p.add_argument("description", nargs="?", default=""); p.add_argument("--id"); p.add_argument("--raw"); p.add_argument("--mode"); p.add_argument("--force", action="store_true"); p.set_defaults(fn=cmd_boot)
    # `context` is a phase GROUP: bare call shows what is gathered, sub-commands act inside
    # the phase. Nested subparsers keep the command tree shaped like the process itself.
    for nm in ("context", "ctx"):
        p = sub.add_parser(nm, add_help=False)
        p.add_argument("--line", action="store_true")
        p.add_argument("--json", action="store_true")
        p.add_argument("--task")
        p.add_argument("--section")
        p.set_defaults(fn=cmd_ctx)
        inner = p.add_subparsers(dest="ctx_cmd")
        q = inner.add_parser("qa", add_help=False)
        q.add_argument("question", nargs="?"); q.add_argument("answer", nargs="?")
        q.add_argument("--list", action="store_true")
        q.add_argument("--round", type=int); q.add_argument("--new-round", action="store_true")
        q.add_argument("--area"); q.add_argument("--assumed")
        q.add_argument("--task"); q.set_defaults(fn=cmd_qa)
        a = inner.add_parser("add", add_help=False)
        a.add_argument("source", nargs="?"); a.add_argument("finding", nargs="?")
        a.add_argument("--ref", action="append"); a.add_argument("--area")
        a.add_argument("--task"); a.set_defaults(fn=cmd_ctx_add)
        u = inner.add_parser("unknown", add_help=False)
        u.add_argument("text", nargs="?"); u.add_argument("--risk")
        u.add_argument("--task"); u.set_defaults(fn=cmd_unknown)
        b = inner.add_parser("beyond", add_help=False)
        b.add_argument("text", nargs="?")
        b.add_argument("--why"); b.add_argument("--ref", action="append")
        b.add_argument("--adds", action="store_true"); b.add_argument("--contradicts")
        b.add_argument("--replace", action="store_true")
        b.add_argument("--task"); b.set_defaults(fn=cmd_beyond)
        # The free-text steps, each under its own name so the command is guessable.
        # --why / --ref matter past context, when the same command is an AMENDMENT.
        for _k in ("requirements", "constraints", "limitations", "resources", "finance",
                   "tools", "definitions", "success", "outcomes", "metrics", "checklist",
                   "ifr", "parts", "clarified", "summary"):
            w = inner.add_parser(_k, add_help=False)
            w.add_argument("text", nargs="?", default="")
            w.add_argument("--replace", action="store_true"); w.add_argument("--task")
            w.add_argument("--why"); w.add_argument("--ref", action="append")
            # поправка к тому, над чем стоит его слово: дополняет или отменяет
            w.add_argument("--adds", action="store_true"); w.add_argument("--contradicts")
            w.set_defaults(fn=cmd_context_step, step_key=_k)
        sc = inner.add_parser("scope", add_help=False)
        sc.add_argument("dim", nargs="?", default="")
        sc.add_argument("--in", dest="inside"); sc.add_argument("--out")
        sc.add_argument("--blur"); sc.add_argument("--replace", action="store_true")
        sc.add_argument("--drop"); sc.add_argument("--why"); sc.add_argument("--ref", action="append")
        sc.add_argument("--adds", action="store_true"); sc.add_argument("--contradicts")
        sc.add_argument("--task"); sc.set_defaults(fn=cmd_context_scope)
        r = inner.add_parser("areas", add_help=False)
        r.add_argument("--task"); r.set_defaults(fn=cmd_areas)
    p = sub.add_parser("blueprint", add_help=False); p.add_argument("part", nargs="?"); p.add_argument("--mode"); p.set_defaults(fn=cmd_blueprint)
    p = sub.add_parser("mode", add_help=False); p.add_argument("mode", nargs="?"); p.add_argument("--why"); p.add_argument("--task"); p.set_defaults(fn=cmd_mode)
    p = sub.add_parser("status", add_help=False); p.set_defaults(fn=cmd_status)
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
    f = ti.add_parser("fork", add_help=False)
    f.add_argument("id", nargs="?"); f.add_argument("text", nargs="?")
    f.add_argument("--who"); f.add_argument("--option", action="append")
    f.add_argument("--cost", action="append")
    f.add_argument("--recommend", action="store_true"); f.add_argument("--task")
    # the dossier: what this option IS, what would kill it; the preview to touch; the agent's
    # recommendation; what exactly the owner must decide at this gate.
    # append + a refusal in cmd_fork: repeated --option in ONE call used to collapse
    # silently into the last one (feedback pool, 2026-08-22) — one option per call.
    f.add_argument("--model", action="append"); f.add_argument("--falsifier", action="append")
    f.add_argument("--preview")
    f.add_argument("--recommendation"); f.add_argument("--decide")
    f.set_defaults(fn=cmd_fork)
    d = ti.add_parser("decide", add_help=False)
    d.add_argument("id", nargs="?"); d.add_argument("choice", nargs="?")
    d.add_argument("--words"); d.add_argument("--why"); d.add_argument("--narrow")
    d.add_argument("--fixed"); d.add_argument("--fidelity")
    d.add_argument("--assumed"); d.add_argument("--undo")
    d.add_argument("--task"); d.set_defaults(fn=cmd_decide)
    fl = ti.add_parser("forks", add_help=False)
    fl.add_argument("--task"); fl.set_defaults(fn=cmd_forks)
    tt = ti.add_parser("tools", add_help=False)
    tt.add_argument("text", nargs="?"); tt.add_argument("--task")
    tt.set_defaults(fn=cmd_think_tools)
    ts = ti.add_parser("skip", add_help=False)
    ts.add_argument("step", nargs="?"); ts.add_argument("--why"); ts.add_argument("--task")
    ts.set_defaults(fn=cmd_think_skip)
    # The free-text steps of the think ladder, each under its own name (like context's).
    # `undo` is the step key; `reversibility` is what a person would type — both work.
    for _k, _names in (("mirror", ("mirror",)), ("form", ("form",)), ("core", ("core",)),
                       ("ideals", ("ideals",)), ("research", ("research",)),
                       ("baseline", ("baseline",)), ("shoals", ("shoals",)),
                       ("undo", ("reversibility", "undo")), ("crystal", ("crystal",)),
                       ("refute", ("refute",)), ("order", ("order",))):
        tsx = ti.add_parser(_names[0], add_help=False, aliases=list(_names[1:]))
        tsx.add_argument("text", nargs="?"); tsx.add_argument("--ref", action="append")
        tsx.add_argument("--why"); tsx.add_argument("--replace", action="store_true")
        tsx.add_argument("--adds", action="store_true"); tsx.add_argument("--contradicts")
        tsx.add_argument("--task")
        tsx.set_defaults(fn=cmd_think_step, step_key=_k, step_name=_names[0])

    pl = sub.add_parser("plan", add_help=False)
    pl.add_argument("words", nargs="*"); pl.add_argument("--task")
    pl.add_argument("--force", action="store_true")
    pl.add_argument("--replace", action="store_true")
    pl.add_argument("--why")                       # el plan block / park
    pl.add_argument("--owe", type=int)             # el plan block — держит долг владельца #n
    pl.add_argument("--after")                     # el plan unfold — после чего раскроется
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
    p.add_argument("--list", action="store_true"); p.add_argument("--done", type=int)
    p.add_argument("--all", action="store_true")   # closed items too
    p.add_argument("--task"); p.set_defaults(fn=cmd_todo)
    p = sub.add_parser("accept", add_help=False)
    p.add_argument("words", nargs="?"); p.add_argument("--on"); p.add_argument("--task")
    p.add_argument("--for", dest="for_"); p.add_argument("--close", action="store_true")
    p.add_argument("--assumed")
    p.set_defaults(fn=cmd_accept)
    # the autonomy layer: his word that opens it · the ledger of borrowed words · the stop
    p = sub.add_parser("grant", add_help=False)
    p.add_argument("words", nargs="?"); p.add_argument("--until"); p.add_argument("--no")
    p.add_argument("--task"); p.set_defaults(fn=cmd_grant)
    p = sub.add_parser("halt", add_help=False)
    p.add_argument("why", nargs="?"); p.add_argument("--task"); p.set_defaults(fn=cmd_halt)
    for nm in ("review", "debt"):
        p = sub.add_parser(nm, add_help=False); p.add_argument("--task"); p.set_defaults(fn=cmd_review)
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
    p.add_argument("--task"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("lesson", add_help=False)
    p.add_argument("text"); p.add_argument("--task"); p.set_defaults(fn=cmd_lesson)
    p = sub.add_parser("research", add_help=False)
    p.add_argument("source", nargs="?"); p.add_argument("finding", nargs="?")
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
    p = sub.add_parser("help", add_help=False); p.add_argument("topic", nargs="?"); p.set_defaults(fn=cmd_help)

    # `-h` / `--help` cannot be subcommand NAMES: argparse reads a leading dash as an option
    # on the top parser and errors out before it ever dispatches. They are intercepted here
    # instead, and anywhere in the line — there are no per-command help pages, so asking for
    # help must never be able to fail.
    argv = sys.argv[1:]
    if not argv:
        return cmd_onboard(None)
    if "-h" in argv or "--help" in argv:
        return cmd_help(None)

    args = ap.parse_args(argv)
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
    flush_renders()
    return rc
