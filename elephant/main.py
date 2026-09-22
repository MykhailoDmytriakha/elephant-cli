"""Command line for `el` (C1–C9): ten commands, text output, exit codes 0/1/2/3/4, no prompts."""
import argparse
import re
import sys
from pathlib import Path
from typing import Optional

from . import __version__, commands, hints, knowledge, store
from .store import StoreError

EXAMPLES = """examples
  el  ·  el status                   where the case in hand stands + next step (read this first)
  el log DECISION "chose X over Y because Z"
  el log RESULT "p95 dropped 120 → 48 ms"
  el todo add 3 "write the parser"      el todo done 3.1 run:"python3 -m unittest → 12 OK" "parser passes"   done = KIND of evidence + what came out (→ RESULT)
  el todo done 2.4 file:evidence/receipt.pdf "fee paid" · el todo done 2.5 ref:R000123-000001 "request filed" · el todo done 2.6 owner "agreed with the clerk"
  el todo done 3.1-3.5 run:"make check → OK" "pre-flight verified" · el todo reopen 3.1-3.6 "drift" · el todo cancel 3.2, 3.4 "why"   a range or list: one journal line
  el help evidence                      the four kinds — file · ref · run · owner — who can check each, what the tool checks
  el todo edit 3.1 "new text" · el todo move 3.7 3.2 (before 3.2; or `last`) · el todo drop 3.4   numbers never change
  el todo add 3 "send the material — due: 2026-09-09" · el todo due 3.2 2026-09-12 · el todo cancel 3.5 "no longer needed"
  el todo add 3 "text" --before 3.4         in place instead of the end (the number is for life, the position is not)
  el todo add 3 'pay $150 for the permit'   SINGLE quotes when the text has `$`: the shell eats $150 inside double quotes
  el todo add 6 "weld the first gas pipe" --why "no meter, no acceptance" --note "call the gas service before welding — they install the meter"
  el todo why 6.1 "…" · el todo note 6.1 "bring the permit: [permit](docs/gas-permit.pdf)" · el todo note 6.1 --edit 2 "…" · --drop 2   the item's pockets (F22)
  el todo note 4.3, 5.3, 6.3 "in SIT this step failed until the old PVC was removed — check PVC first"   one note under the same step of the next environments
  el todo done 2.3 file:evidence/receipt.pdf ref:4471-09 "paid, receipt in the folder"   several proofs: one `result:` line, one proof line each
  el todo expect 3.2 "chosen DB with its case [file: docs/db-choice.md] · load [run: k6 → p95] · budget [owner]"   the proof, promised before the work; done holds you to it
  el todo show 3.3                      the item's card: pockets, the proofs of the items it comes after (its inputs), what it feeds
  el todo add 3 "grep the DEV trace" --expect "[run: trace shows the outbound call]" --fact "checkout calls the pricing API for the pair"   the expected fact
  el todo done 3.4 run:"grep 3 traces -> no outbound call" "trace read" --fact "in 3 DEV traces, no outbound pricing call"   the fact as it turned out, within what was seen
  el facts                              the fact chain: ✓ established · · expected · ? under question · ✗ dead branches — what the next agent builds on
  el phase plan 3 "Answer" --goal "why and how to re-enable [file: research/answer.md] [run: curl → 200]"   the phase's own promise; the Digest holds it to it
  el help practice                      how strong agents lead a case — weak against strong, by moment; every `hint:` points here
  el help people                        a card per person the cases deal with: .cases/people/<name>.md, `summary:` as line 2; cases link to it
  el phase note 6 "the permit runs out in March" · el log --phase 6 DECISION "lamps under the eaves — idea of 15.09"   parked for a planned phase; surfaces when it opens
  el readme add problems "open · Redis fails after the chart deploy · workaround: restart by hand · until: 2026-12-01 (chart 2.3)"   a crutch with a return date, counted on entry
  el todo move 3.6 4                    to another phase (joins its end under the next free number)
  el todo add 3 "ship it — after: 3.1, 3.2" · el todo after 3.4 "3.1, 3.2" · el todo after 3.4 none   dependencies (→ unblocked: on entry)
  el phase cancel 4 "the venue fell through" · el case cancel "merged into the other case"   the second honest end of a branch
  el readme set due "2026-09-13 · decision meeting"   the case deadline — `el` counts the days on entry
  el mv docs/old.md docs/notes/new.md   move a file; every link to it is rewritten (README/TODO/JOURNAL and the documents)
  el relink docs/old.md docs/notes/new.md   the file already moved without el: the links follow now (journal included)
  el relink docs/old.md none            gone for good, or an example written as a link: the links become literal text
  el todo hold 3.2 "ждём ответа заказчика" · el todo resume 3.2
  el todo reopen 3.1 "the databases drifted — the result no longer holds"   a tick taken back: DECISION in the journal, the RESULT stays
  el readme set next "call the customer" · el readme set пауза "" (removes the line) · el readme add links "docs/contacts.md — кто есть кто"
  el phase open 3 "CLI core" --goal "single write door with tests"
  el phase plan 4 "Rollout" --goal "first users on the new build"   name the NEXT phase now, park items under it (todo add 4), open it later
  el log DECISION "reflect: …"  ·  el log DECISION "align: …"   (both before closing)
  el phase close 3 "parsers, stamp and commands work, 55 tests" --reflect "ask why before going" --align "phase 4 loses the 2024 items"   one command: the two DECISIONs and the close
  el phase close 4 "…"                 a planned phase out of turn whose every item ended closes from the plan; own clock next time: el spawn
  el readme add decisions "2026-09-05 · X over Y — why" · el readme drop decisions 2 · el readme drop state пауза
  el readme edit decisions 3 "2026-09-05 · X over Y — why"   line 3 in place, order kept (context · decisions · problems · links)
  el readme touch                      State read and still true after new RESULTs: moves `as of` only (Order: State is behind)
  el readme --file README.md           validate and write a README (progress line kept in sync)
  el case new "connect database" --goal "app talks to the prod database"
  el case new --root "my app" --goal "…"   root mode: the project folder itself is the top case
  el case list                         open cases first (progress · next · due), closed as a count + latest few, pre-el cases as a count; --all names every one
  el case use connect-database         switch the hand (like `cf target` / `oc project`)
  el spawn "db unreachable from server" --goal "server cannot reach the database, cause unknown"
  el done "database connected and validated"
  el feedback "done refuses run: with spaces" --actual "exit 2: …" --expected "…" --repro "el todo done 3.1 run:'make → OK' ok"   el is wrong or in the way? report it, never forge the record (el help feedback)
  el order                             what is out of order in the case in hand + the fix for each line
  el order --adopt                     move file descriptions from README Links into the files as `summary:`
  el migrate                           legacy case (files el never stamped): dry run — what maps where, nothing changes
  el migrate --apply                   archive the legacy files byte-for-byte, write canonical ones atomically
  el check                             the case in hand against the rules; violations → exit 3
  el check --all                       every case in the workspace (a legacy case = one line per file, not its error dump)
  el doctor                            read-only diagnostics, changes nothing
  el --case connect-database check     check one case only
  el help model                        how it all fits: nodes, rendered lines, edges, two ends, what is refused vs shown
  el help <topic>                      topics are listed at the bottom of this help
options: --case <name or suffix> (or EL_CASE) picks the case; exit codes 0 ok · 1 error · 2 usage · 3 rule violation · 4 precondition
"""


HELP_TOPIC = {"log": "journal", "todo": "todo", "phase": "phases", "readme": "readme", "case": "cases", "spawn": "cases", "facts": "facts",
              "done": "cases", "feedback": "feedback", "migrate": "migrate", "mv": "order", "relink": "order",
              "order": "order", "check": "errors", "status": "start"}
# The form of every other command carries its meaning in its placeholders (N.M, TYPE, old new); feedback's
# three free texts do not — the agent must know what is valuable to the reader before writing a word, so
# a wrong call prints the whole dose, not one example line.
INLINE_DOSE = {"feedback"}


def _cmd_of(prog: str) -> Optional[str]:
    parts = prog.split()
    return parts[1] if len(parts) > 1 else None


def examples_for(cmd: str) -> list:
    """The lines of `el --help` examples that show `el <cmd>` (C2: examples first, the library's usage line never)."""
    rx = re.compile(rf"(^|\s)el {re.escape(cmd)}(\s|$)")
    return [line.strip() for line in EXAMPLES.splitlines() if rx.search(line.strip()) and line.startswith("  ")]


def usage_error(prog: str, message: str) -> str:
    """What a wrong call prints (the owner's word, 2026-09-15): what is missing, then the command's examples or —
    for feedback — its whole dose. One voice for every command; argparse's bare `usage:` line is never shown."""
    cmd = _cmd_of(prog)
    lines = [f"{prog}: {message}"]
    if cmd in INLINE_DOSE:
        lines += [f"  {ln}" if ln else "" for ln in knowledge.TOPICS[cmd].splitlines()]
    elif cmd:
        shown = examples_for(cmd)
        if shown:
            lines.append("  examples:")
            lines += [f"    {ln}" for ln in shown]
    else:
        lines.append("  the bare `el` prints where the case stands; a day with el: el help start")
    return "\n".join(lines)


def usage_recovery(prog: str) -> str:
    cmd = _cmd_of(prog)
    topic = HELP_TOPIC.get(cmd) if cmd else None
    return f"el help {topic} · el {cmd} -h" if topic else "el --help · el help start"


class Parser(argparse.ArgumentParser):
    """argparse with el's voice. A wrong call is a StoreError (exit 2, C4/C5) — what is missing, the
    examples, the recovery — never the library's bare `usage:` line: for the agent who typed `el feedback`
    to learn the form, that line was the moment of need and it answered with nothing (2026-09-15)."""

    def error(self, message: str):
        raise StoreError(usage_error(self.prog, message), 2, recovery=usage_recovery(self.prog))


def build_parser() -> argparse.ArgumentParser:
    p = Parser(prog="el", description="the write door for .cases/ — rules: el help files · order · limits",
               epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    p.add_argument("--case", help="case name or unique suffix (default: EL_CASE or the freshest open case)")
    p.add_argument("--version", action="version", version=f"elephant {__version__}")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("log", help="add a journal event: PHASE · DECISION · PROBLEM · RESULT", allow_abbrev=False)
    s.add_argument("type")
    s.add_argument("text")
    s.add_argument("--phase", help="p1, 1 or a unique phase name (default: the open phase); e.g. `el log --phase p1 DECISION \"…\"`")

    s = sub.add_parser("todo", help="add · done · edit · move · drop · hold · resume items — N.M is an item's number for life: drop and move never renumber", allow_abbrev=False)
    s.add_argument("action", choices=["add", "done", "edit", "move", "drop", "hold", "resume", "reopen", "cancel", "due", "after", "why", "note", "expect", "fact", "show"])
    s.add_argument("ref", help="phase number for add (N), item for the rest (N.M); done/reopen/cancel also take a range N.A-N.B or a list \"N.A, N.B\"")
    s.add_argument("text", nargs="*", default=[], help="text for add/edit (may end with `— due: YYYY-MM-DD`); for move: N.K (before K), `last`, or a phase number K; for done: the KIND of evidence, then what came out — file:<path> · ref:<trace> · run:\"<command → outcome>\" · owner (el help evidence); for cancel/reopen: why; for due: YYYY-MM-DD or none; for after: \"N.M, N.K, case\" or none")
    s.add_argument("--before", help="add only: put the new item before N.K instead of at the end (numbers never change, positions do)")
    s.add_argument("--why", help="add only: what the item is for, one line (F22) — later: el todo why N.M \"…\"")
    s.add_argument("--note", action="append", help="add only, repeatable: a constraint, who to call, what to bring, a link (F22) — later: el todo note N.M \"…\"")
    s.add_argument("--expect", help="add only: what done will look like, proofs in brackets [file: …] [run: …] [owner] (F22) — later: el todo expect N.M \"…\"")
    s.add_argument("--fact", help="add: the fact this item is expected to establish (or `-`: none); done: the verdict — `confirmed`, the fact as it turned out, or `-`")
    s.add_argument("--edit", type=int, metavar="K", help="note only: rewrite note K in place")
    s.add_argument("--drop", type=int, metavar="K", help="note only: remove note K")

    s = sub.add_parser("phase", help="plan · open · close a phase (plan = name the next one without opening it, repeat it to sharpen the goal; close needs RESULT, reflect:, align:)", allow_abbrev=False)
    s.add_argument("action", choices=["plan", "open", "close", "cancel", "note"])
    s.add_argument("n", type=int)
    s.add_argument("text", nargs="?", default="", help="name for plan/open (open takes it from the plan when omitted), summary for close, why for cancel, the note for note")
    s.add_argument("--goal", help="one line; required for a new phase unless it was planned with one")
    s.add_argument("--reflect", help="close only: the lesson about how you worked — logged as `DECISION · reflect: …` in the same command (P8)")
    s.add_argument("--align", help="close only: what changes in the next plan — logged as `DECISION · align: …` in the same command (P8)")
    s.add_argument("--edit", type=int, metavar="K", help="note only: rewrite note K in place")
    s.add_argument("--drop", type=int, metavar="K", help="note only: remove note K")

    s = sub.add_parser("readme", help="write from --file/stdin · set <prefix> \"…\" (\"\" removes; State only) · add <section> \"…\" · edit <section> <k> \"…\" · drop <section> <k> | drop state <prefix> · touch (State read and still true: moves `as of`)", allow_abbrev=False)
    s.add_argument("action", nargs="?", choices=["set", "add", "edit", "drop", "touch"])
    s.add_argument("a", nargs="?")
    s.add_argument("b", nargs="?")
    s.add_argument("c", nargs="?")
    s.add_argument("--file", default=None, help="a whole README to validate and write (`-` = stdin)")

    s = sub.add_parser("case", help="case new <name> --goal … · case list · case use <name> · case new --root", allow_abbrev=False)
    s.add_argument("action", choices=["new", "list", "use", "cancel"])
    s.add_argument("name", nargs="?")
    s.add_argument("--goal")
    s.add_argument("--root", action="store_true", help="root mode: the project folder itself becomes the top case")
    s.add_argument("--all", action="store_true", help="list only: every closed case, not just the latest few")

    s = sub.add_parser("mv", help="move/rename a file inside the case; every link to it is rewritten", allow_abbrev=False)
    s.add_argument("old", help="current path, relative to the case (docs/x.md)")
    s.add_argument("new", help="new path or folder (docs/notes/ or docs/notes/y.md)")

    s = sub.add_parser("relink", help="the file already moved without el: rewrite every link from old to new (journal included), move nothing; new = none retires the links into literal text", allow_abbrev=False)
    s.add_argument("old", help="the path the links still name (docs/x.md) — must not exist any more")
    s.add_argument("new", help="where the file is now (docs/notes/x.md) — must exist; or `none` (gone for good / an example)")

    s = sub.add_parser("spawn", help="open a nested case inside the case in hand (P11)", allow_abbrev=False)
    s.add_argument("name")
    s.add_argument("--goal", required=True)

    s = sub.add_parser("done", help="close the case in hand (all phases must be closed)", allow_abbrev=False)
    s.add_argument("summary")

    s = sub.add_parser("feedback", help="report an Elephant problem or wish — lands in the elephant-cli clone's feedback/ pool", allow_abbrev=False)
    s.add_argument("title")
    s.add_argument("--expected", default="")
    s.add_argument("--actual", default="")
    s.add_argument("--why", default="")
    s.add_argument("--acceptance", default="")
    s.add_argument("--repro", default="")

    s = sub.add_parser("order", help="what is out of order in the case in hand, with the fix for each line", allow_abbrev=False)
    s.add_argument("--adopt", action="store_true", help="write `summary:` into files from their README Links descriptions")
    s = sub.add_parser("migrate", help="legacy case → Elephant's grammar: dry run by default, --apply archives and writes", allow_abbrev=False)
    s.add_argument("--apply", action="store_true", help="archive legacy files under legacy/<date-time>/ and write the canonical files")
    s = sub.add_parser("check", help="the case in hand against the rules (violations → exit 3); --all: every case in the workspace", allow_abbrev=False)
    s.add_argument("--all", action="store_true", help="every case here, legacy ones included (one line each); default: the case in hand")
    sub.add_parser("facts", help="the fact chain of the case in hand — established · expected · under question · dead branches; rendered from the fact: lines", allow_abbrev=False)
    sub.add_parser("doctor", help="read-only diagnostics: what el sees from here; changes nothing", allow_abbrev=False)
    sub.add_parser("status", help="where the case stands — the same screen as bare `el` (git/oc/cf habit)", allow_abbrev=False)
    s = sub.add_parser("help", help="examples; `el help <topic>` opens a knowledge dose", allow_abbrev=False)
    s.add_argument("topic", nargs="?")
    return p


# A `$150` inside double quotes is eaten by the shell before el sees the text (zsh: `$150` is
# positional parameter 150, empty) — the record then carries a hole nobody typed, and a journal
# line is not editable afterwards (feedback 2026-09-08: «заплатить $150 …» landed as «заплатить  …»).
# What survives of the swallowed word is a trace; a text with a trace is refused, not recorded.
SHELL_TRACES = (
    (re.compile(r"\S  +\S"), "a double space"),
    (re.compile(r"(?:^|\s)\.\d"), "an orphan decimal like `.72`"),
    (re.compile(r"^\s"), "a leading space"),  # a trailing one is too often innocent (`"x " * n`) to refuse
)
TEXT_ARGS = ("text", "goal", "a", "b", "c", "name", "summary", "title", "expected", "actual", "why", "acceptance", "repro", "note", "expect", "reflect", "align", "fact")


def shell_trace(args) -> Optional[str]:
    """The refusal text when a text argument carries a trace of a shell substitution, else None."""
    for key in TEXT_ARGS:
        raw = getattr(args, key, None)
        vals = raw if isinstance(raw, list) else [raw]  # `todo` text is a list since 1.5.0 (the kind of evidence, then the words)
        for val in vals:
            if not isinstance(val, str) or not val:
                continue
            for rx, what in SHELL_TRACES:
                m = rx.search(val)
                if not m:
                    continue
                where = val[max(0, m.start() - 15):m.end() + 15].replace("\n", " ")
                return (f"text not written: {what} at «…{where}…» — a `$…` swallowed by the shell? inside double quotes "
                        f"`$150` is a variable and vanishes; write the text in SINGLE quotes: el {args.cmd} … '…' "
                        f"(a double space is never kept anyway — fix the text and repeat)")
    return None


def run(argv=None) -> int:
    parser = build_parser()
    args = None
    try:
        args = parser.parse_args(argv)  # a wrong call raises StoreError(2) in el's voice — see Parser.error
        trace = shell_trace(args)
        if trace:
            raise StoreError(trace, 2)
        if args.cmd == "help":
            if args.topic:
                dose = knowledge.resolve(args.topic)
                if dose is None:
                    raise StoreError(f"no topic `{args.topic}` — topics: {knowledge.topic_list()}", 2, recovery="el help <topic>")
                print(dose)
                return 0
            parser.print_help()
            print(f"\ntopics (open at the moment of need): el help <{knowledge.topic_list()}> — singular forms and common words work too (phase, item, proof, hint)")
            return 0
        if args.cmd == "feedback":
            out = commands.feedback(args.title, args.expected, args.actual, args.why, args.acceptance, args.repro)
            print("\n".join(out.lines))
            return 0
        if args.cmd == "doctor":
            out = commands.doctor()
            print("\n".join(out.lines))
            return 0
        if args.cmd == "case" and args.action == "new":
            if not args.name or not args.goal:
                raise StoreError("usage: el case new <name> --goal \"one line\" [--root]", 2)
            root = _root_or_create()
            if args.root:
                out = commands.project_new(root, args.name, args.goal)
                print("\n".join(out.lines))
                return 0
            case = commands.case_new(root, args.name, args.goal)
            print(f"created: {case.relative_to(root.parent)} — now `el phase open 1 <Name> --goal \"…\"`")
            if hints.enabled():  # something to imitate: a model imitates the form it sees (2026-09-16)
                print("", knowledge.EXEMPLAR, sep="\n")
                tip = hints.pick("case_new", root=root)
                if tip:
                    print(f"hint: {tip}")
            return 0
        root = store.find_root()
        if args.cmd == "case":
            if args.action == "list":
                out = commands.case_list(root, everything=args.all)
            elif args.action == "cancel":
                out = commands.case_cancel(root, store.hand(root, args.case), args.name or "")
            else:
                if not args.name:
                    raise StoreError("usage: el case use <name or unique suffix>", 2)
                out = commands.case_use(root, args.name)
        elif args.cmd == "check":
            if args.all:
                only = None
            elif args.case:
                only = store.resolve_case(root, args.case)
            else:
                try:
                    only = store.hand(root)  # the case in hand, like every other command (feedback 2026-09-09)
                except StoreError:
                    only = None  # nothing in hand (every case closed): the whole workspace
            out = commands.check(root, only, everything=args.all)
        else:
            case = store.hand(root, args.case)
            if args.cmd is None or args.cmd == "status":
                out = commands.entry(root, case)
            elif args.cmd == "log":
                out = commands.log(case, args.type, args.text, args.phase)
            elif args.cmd == "todo":
                parts = list(args.text or [])
                ref = args.ref
                # a list typed with spaces — `el todo done 3.2, 3.4 "why"` — reaches argparse as ref `3.2,` plus
                # text `3.4`: the numbers are gathered back into the ref (done · reopen · cancel · note take lists)
                while ref.endswith(",") and parts and re.fullmatch(r"\d+\.\d+,?", parts[0]):
                    ref += " " + parts.pop(0)
                args.ref = ref
                text = " ".join(parts)
                if args.action == "add":
                    out = commands.todo_add(case, args.ref, text, args.before, why=args.why or "", notes=args.note or [],
                                            expect=args.expect or "", fact=args.fact or "")
                elif args.action == "done":  # the kinds of evidence first (one or several), then what came out (F20)
                    kinds = []
                    while parts and commands._is_kind_token(parts[0]):
                        kinds.append(parts.pop(0))
                    if not kinds and parts:  # the first word is not a kind: the refusal names it and lists the four
                        kinds.append(parts.pop(0))
                    out = commands.todo_done(case, args.ref, kinds, " ".join(parts), fact=args.fact)
                elif args.action == "why":
                    out = commands.todo_why(case, args.ref, text)
                elif args.action == "expect":
                    out = commands.todo_expect(case, args.ref, text)
                elif args.action == "show":
                    out = commands.todo_show(case, args.ref)
                elif args.action == "fact":
                    out = commands.todo_fact(case, args.ref, text)
                elif args.action == "note":
                    out = commands.todo_note(case, args.ref, text, edit=args.edit, drop=args.drop)
                elif args.action == "edit":
                    if not text:
                        raise StoreError("usage: el todo edit N.M \"new text\"", 2)
                    out = commands.todo_edit(case, args.ref, text)
                elif args.action == "move":
                    if not text:
                        raise StoreError("usage: el todo move N.M N.K", 2)
                    out = commands.todo_move(case, args.ref, text)
                elif args.action == "hold":
                    out = commands.todo_hold(case, args.ref, text)
                elif args.action == "resume":
                    out = commands.todo_resume(case, args.ref)
                elif args.action == "reopen":
                    out = commands.todo_reopen(case, args.ref, text)
                elif args.action == "cancel":
                    out = commands.todo_cancel(case, args.ref, text)
                elif args.action == "due":
                    out = commands.todo_due(case, args.ref, text)
                elif args.action == "after":
                    out = commands.todo_after(case, args.ref, text)
                else:
                    out = commands.todo_drop(case, args.ref)
            elif args.cmd == "phase":
                if args.action == "open":
                    out = commands.phase_open(case, args.n, args.text, args.goal)  # name may come from the plan
                elif args.action == "plan":
                    if not args.text:
                        raise StoreError("phase plan needs a name: `el phase plan 3 \"Rollout\" --goal \"one line\"`", 2)
                    out = commands.phase_plan(case, args.n, args.text, args.goal)
                elif args.action == "cancel":
                    out = commands.phase_cancel(case, args.n, args.text)
                elif args.action == "note":
                    out = commands.phase_note(case, args.n, args.text, edit=args.edit, drop=args.drop)
                else:
                    if not args.text:
                        raise StoreError("phase close needs a summary: `el phase close 3 \"what it delivered\"`", 2)
                    out = commands.phase_close(case, args.n, args.text, reflect=args.reflect, align=args.align)
            elif args.cmd == "readme":
                if args.action == "set":
                    if not args.a or args.b is None:
                        raise StoreError("usage: el readme set <prefix> \"text\" (a State line; \"\" removes it)", 2)
                    out = commands.readme_set(case, args.a, args.b)
                elif args.action == "add":
                    if not args.a or not args.b:
                        raise StoreError("usage: el readme add <section> \"line\"", 2)
                    out = commands.readme_add(case, args.a, args.b)
                elif args.action == "edit":
                    if not args.a or not args.b or args.c is None:
                        raise StoreError("usage: el readme edit <section> <k> \"new text\" · el readme edit state <prefix> \"text\"", 2)
                    out = commands.readme_edit(case, args.a, args.b, args.c)
                elif args.action == "touch":
                    out = commands.readme_touch(case)
                elif args.action == "drop":
                    if not args.a or not args.b:
                        raise StoreError("usage: el readme drop <section> <k> · el readme drop state <prefix>", 2)
                    out = commands.readme_drop(case, args.a, args.b)
                else:
                    if args.file is None:  # bare `el readme`: piped text is a write, nothing piped is a question
                        text = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.read()
                    else:
                        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
                    # nothing to write is not a broken README (feedback 2026-09-22: «F1 · sections … got none» read
                    # as damage): the bare call shows the README and the ways to write it
                    out = commands.readme(case, text) if text.strip() or args.file is not None else commands.readme_show(case)
            elif args.cmd == "order":
                out = commands.order_cmd(root, case, args.adopt)
            elif args.cmd == "facts":
                out = commands.facts(case)
            elif args.cmd == "migrate":
                out = commands.migrate_cmd(case, args.apply)
            elif args.cmd == "mv":
                out = commands.mv(case, args.old, args.new)
            elif args.cmd == "relink":
                out = commands.relink(case, args.old, args.new)
            elif args.cmd == "spawn":
                out = commands.spawn(root, case, args.name, args.goal)
            elif args.cmd == "done":
                out = commands.done(root, case, args.summary)
            else:  # pragma: no cover
                parser.print_usage()
                return 2
        for w in out.warnings:
            print(f"warning: {w}", file=sys.stderr)
        print("\n".join(out.lines))
        return 0
    except StoreError as e:
        lines = [f"el: ERROR [exit {e.code}] {e}"]
        if e.recovery:
            lines.append(f"  recovery: {e.recovery}")
        lines.append(f"  exit {e.code} = {store.EXIT_MEANING.get(e.code, '?')} — `el help errors`")
        if args is not None and args.cmd in (None, "status"):
            # the entry explains itself on stdout (feedback #4) — and only there: printed to both streams,
            # a terminal with 2>&1 showed the same refusal twice, as two failures (feedback 2026-09-14)
            print("\n".join(lines))
            if e.code == 4 and "no `.cases/`" in str(e):
                print(knowledge.ONBOARDING)
        else:
            print("\n".join(lines), file=sys.stderr)
        return e.code


def _root_or_create() -> Path:
    try:
        return store.find_root()
    except StoreError:
        root = Path.cwd() / store.CASES_DIR
        root.mkdir()
        return root


def main():  # pragma: no cover
    sys.exit(run())
