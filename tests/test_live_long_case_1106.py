"""A Codex long case, 2026-11-06 (the radio between the maintainer and the agent, message 2): three weeks, 305 phases,
2 400 documents. The entry took 21 s — 17 of them comparing every archived document with every other — and its Order
asked to add a summary to 1 617 files, relate 5 716 pairs and link 1 981 files: raw logs, old red runs and accepted
proofs kept on purpose, which cannot be rewritten without spoiling them. The recitation recomputed the same Order every
tenth call. The body of the entry was the README's Links catalog (3 764 lines) cut at the screen limit: the TODO and the
journal never reached the agent.

1. Order at the entry, in a bare `el readme` and in the recitation looks at the files the work in flight touched; the
   files from before it are counted in one line — the law has no retroactive force (P15). `el order` sees every file.
2. A body over the screen limit gives the past by count — the Links catalog and the closed phases but the newest — so
   the open work and the journal reach the screen."""
import datetime as dt
import os
import re
import subprocess
import time
import unittest
from pathlib import Path
from unittest import mock

from elephant import commands, grammar, store
from tests.test_long_case_1105 import Base, TRACKER


def _case() -> Path:
    return next(p for p in (Path(".cases")).iterdir() if p.is_dir() and (p / "README.md").exists())


def _order_block(out: str) -> str:
    return out.split("## Order", 1)[1].split("\n\n", 1)[0]


class OrderAtTheEntryChecksTheWorkInFlight(Base):
    def test_a_file_from_before_the_work_is_counted_not_named(self):
        case = _case()
        (case / "notes").mkdir()
        (case / "notes" / "old-run.md").write_text(f"# Old run\n\n{TRACKER}\n", encoding="utf-8")
        (case / "notes" / "old-copy.md").write_text(f"# Old copy\n\n{TRACKER}\n", encoding="utf-8")
        time.sleep(0.05)
        began = time.time()
        time.sleep(0.05)
        (case / "notes" / "new.md").write_text("# New\n\nthe finding of today\n", encoding="utf-8")
        with mock.patch.object(commands, "_work_since", return_value=began):
            out, _ = self.ok()
        block = _order_block(out)
        self.assertIn("notes/new.md", block)                       # the work in flight is held to the form
        self.assertNotIn("old-run.md", block)                      # history is not reproached at the entry
        self.assertNotIn("share text verbatim", block)
        self.assertIn("(2 file(s) from before the work in flight", block)
        self.assertIn("the whole case: el order", block)
        full, _ = self.ok("order")                                 # the audit still sees every file
        self.assertIn("old-run.md", full)
        self.assertIn("old-copy.md", full)
        self.assertNotIn("from before the work in flight", full)

    def test_the_readme_and_the_recitation_are_scoped_too(self):
        case = _case()
        (case / "notes").mkdir()
        (case / "notes" / "old.md").write_text("# Old\n\nno summary here\n", encoding="utf-8")
        later = time.time() + 5
        with mock.patch.object(commands, "_work_since", return_value=later):
            out, _ = self.ok("readme")
            lines = commands._order_lines(case, Path(".").resolve(), store.read(case, "README.md"),
                                          grammar.parse_journal(store.read(case, "JOURNAL.md")), scoped=True)
        self.assertNotIn("old.md", _order_block(out))
        self.assertIn("(1 file(s) from before the work in flight", out)
        self.assertFalse([ln for ln in lines if "old.md" in ln])
        unscoped = commands._order_lines(case, Path(".").resolve(), store.read(case, "README.md"),
                                         grammar.parse_journal(store.read(case, "JOURNAL.md")))
        self.assertTrue([ln for ln in unscoped if "old.md" in ln])

    def test_the_work_begins_when_the_phase_in_flight_opened(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        case = _case()
        todo = store.todo_of(case)
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
        opened = next(e for e in journal.entries if e.phase == "p1" and any(ev.type == "PHASE" for ev in e.events))
        want = dt.datetime.strptime(f"{opened.date} {opened.time}", "%Y-%m-%d %H:%M").timestamp()
        self.assertEqual(commands._work_since(case, todo, journal), want - commands.WORK_SINCE_MARGIN)
        self.ok("phase", "plan", "2", "Detour", "--goal", "something came up")
        self.ok("phase", "open", "2", "--why", "it goes first")       # phase 1 paused: the work in flight is phase 2
        todo = store.todo_of(case)
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
        detour = next(e for e in journal.entries if e.phase == "p2" and any(ev.type == "PHASE" for ev in e.events))
        self.assertEqual(commands._work_since(case, todo, journal),
                         dt.datetime.strptime(f"{detour.date} {detour.time}", "%Y-%m-%d %H:%M").timestamp()
                         - commands.WORK_SINCE_MARGIN)

    def test_a_journal_stamped_after_now_does_not_hide_a_new_file(self):
        # the second hand's probe, 2026-11-06: a journal stamped 19:07 at 19:02 (a clock corrected back) — a file made at
        # 19:03 looked older than the work; daylight saving ending does the same for an hour
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        case = _case()
        text = store.read(case, "JOURNAL.md")
        ahead = (dt.datetime.now() + dt.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        journal = grammar.parse_journal(re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", ahead, text))
        since = commands._work_since(case, store.todo_of(case), journal)
        self.assertLessEqual(since, time.time() - commands.WORK_SINCE_MARGIN + 1)

    def test_a_link_made_today_to_an_old_file_is_work_in_flight(self):
        # the second hand's probe, 2026-11-06: `docs/arrived.md` made as a link to an older file was counted as history
        case = _case()
        (case / "notes").mkdir()
        (case / "notes" / "old.md").write_text("# Old\n\nno summary here\n", encoding="utf-8")
        time.sleep(0.05)
        began = time.time()
        time.sleep(0.05)
        (case / "docs").mkdir()
        (case / "docs" / "arrived.md").symlink_to(Path("..") / "notes" / "old.md")
        with mock.patch.object(commands, "_work_since", return_value=began):
            out, _ = self.ok()
        block = _order_block(out)
        self.assertIn("docs/arrived.md", block)
        self.assertNotIn("notes/old.md", block)

    def test_no_phase_in_flight_the_work_began_with_the_newest_phase_event(self):
        case = _case()
        journal = grammar.parse_journal(store.read(case, "JOURNAL.md"))
        since = commands._work_since(case, store.todo_of(case), journal)  # a new case: when it opened
        self.assertTrue(since is None or since <= time.time())
        (case / "notes").mkdir()
        (case / "notes" / "first.md").write_text("# First\n\nno summary yet\n", encoding="utf-8")
        out, _ = self.ok()
        self.assertIn("notes/first.md", _order_block(out))
        self.assertNotIn("from before the work in flight", out)


class ALongBodyGivesThePastByCount(Base):
    def test_the_links_catalog_is_counted_and_the_journal_reaches_the_screen(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till to the ledger")
        case = _case()
        (case / "docs").mkdir()
        for k in range(320):
            (case / "docs" / f"record-{k:03d}.md").write_text(
                f"# Record {k}\nsummary: what the tracker said on visit {k}, with the raw answer kept beside it for audit\n",
                encoding="utf-8")
        out, _ = self.ok()
        self.assertNotIn("[body truncated", out)
        self.assertIn("line(s) of the files' map", out)
        self.assertIn("README.md keeps them whole", out)
        self.assertIn("2 folder(s)", out)                        # docs/ and phases/ — as Order reads folder lines
        door = re.search(r"find one: (grep -n 'word' \S+)\)", out).group(1).replace("'word'", "'record-319'")
        found = subprocess.run(door, shell=True, capture_output=True, text=True)  # the printed door, run where el ran
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn("record-319.md", found.stdout)
        self.assertIn("1.1 Wire the till to the ledger", out)      # the open work reaches the screen
        self.assertIn("# JOURNAL — last", out)
        self.assertIn("record-000.md", store.read(case, "README.md"))  # the README on disk keeps every line

    def test_a_short_body_is_shown_whole(self):
        case = _case()
        (case / "docs").mkdir()
        (case / "docs" / "brief.md").write_text("# Brief\nsummary: what the owner asked\n", encoding="utf-8")
        out, _ = self.ok()
        self.assertIn("docs/brief.md", out.split("## Links", 1)[1])
        self.assertNotIn("line(s) of the files' map", out)

    def test_closed_phases_but_the_newest_go_by_count(self):
        closed = "".join(f"- [x] {n} Step{n} — done · 2026-11-0{n} · [phases/{n}-step{n}.md](phases/{n}-step{n}.md)\n"
                         for n in range(1, 6))
        todo = grammar.parse_todo(f"# TODO — x\n\n{closed}- [ ] 6 Six — goal\n  - [ ] 6.1 do it\n")
        shown, _ = commands.render_todo_entry(todo, closed_shown=3)
        self.assertIn("(2 closed phase(s) — 1…2 — not shown here: TODO.md lists each", shown)
        self.assertNotIn("Step1", shown)
        for n in (3, 4, 5):
            self.assertIn(f"- [x] {n} Step{n}", shown)
        self.assertIn("6.1 do it", shown)
        whole, _ = commands.render_todo_entry(todo)
        self.assertIn("Step1", whole)


if __name__ == "__main__":
    unittest.main()


class ManyEndedPhasesAreOneLineAtTheEntry(Base):
    def test_four_ended_phases_fold_and_el_order_names_each(self):
        self.ok("phase", "open", "1", "Build", "--goal", "the shop builds")
        self.ok("todo", "add", "1", "Wire the till")
        for n in (2, 3, 4, 5):
            self.ok("phase", "plan", str(n), f"Step{n}", "--goal", f"step {n} works")
            self.ok("todo", "add", str(n), f"Do step {n}")
            self.ok("todo", "done", f"{n}.1", f"run:step{n} → ok", f"step {n} works")
        out, _ = self.ok()
        block = _order_block(out)
        ended = [ln for ln in block.split("\n") if "every item ended" in ln]
        self.assertEqual(len(ended), 1, block)
        self.assertIn("and 3 more phase(s) where every item ended: 3, 4, 5", ended[0])
        full, _ = self.ok("order")
        for n in (2, 3, 4, 5):
            self.assertIn(f"phase {n} Step{n}: every item ended", full)


class EveryPathTheBodyPrintsIsReachable(Base):
    def test_closed_phases_and_collapsed_items_point_where_the_shell_is(self):
        # the second hand, 2026-11-06, round 2: «not shown here: TODO.md … its file in phases/» — `cat TODO.md` and
        # `ls phases/` from where el ran → exit 1: the files live in .cases/<case>/
        for n in (1, 2, 3, 4, 5):
            self.ok("phase", "open", str(n), f"Step{n}", "--goal", f"step {n} works [run: step{n}]")
            self.ok("todo", "add", str(n), f"Do step {n}", "--expect", f"[run: step{n}]")
            self.ok("todo", "done", f"{n}.1", f"run:step{n} → ok", f"step {n} works")
            if n < 5:
                self.ok("phase", "close", str(n), f"step {n} works", "--reflect", f"lesson {n} about the till",
                        "--align", f"on to step {n + 1}")
        case = _case()
        (case / "docs").mkdir()
        for k in range(320):
            (case / "docs" / f"record-{k:03d}.md").write_text(
                f"# Record {k}\nsummary: what the tracker said on visit {k}, with the raw answer kept beside it for audit\n",
                encoding="utf-8")
        out, _ = self.ok()
        m = re.search(r"closed phase\(s\) — 1…1 — not shown here: (\S+) lists each, one in full: its file in (\S+)\)", out)
        self.assertIsNotNone(m, out)
        self.assertTrue(Path(m.group(1)).is_file(), m.group(1))
        self.assertTrue(Path(m.group(2)).is_dir(), m.group(2))
        c = re.search(r"collapsed here — result and proofs: (\S+) ·", out)
        self.assertIsNotNone(c, out)
        self.assertTrue(Path(c.group(1)).is_file(), c.group(1))
        j = re.search(r"headlines; bodies in (\S+)\)", out)                # el's own line about the journal
        self.assertTrue(Path(j.group(1)).is_file(), j.group(1))
        base = re.search(r"\(the files of (\S+)/ as stored — a link in them reads from that folder\)", out)
        self.assertIsNotNone(base, out)                                      # the stored text keeps its links; el names
        for link in re.findall(r"\]\((phases/[^)]+)\)", out):           # the folder they read from
            self.assertTrue((Path(base.group(1)) / link).is_file(), link)


class TheRulesPointerResolvesFromASubfolder(Base):
    def test_rules_md_is_printed_from_where_el_ran(self):
        # the second hand, 2026-11-06, round 4 — older than this batch: from `sub/`, «rules: .cases/RULES.md» → exit 1
        (Path(".cases") / "RULES.md").write_text("# Rules\n", encoding="utf-8")
        Path("sub").mkdir()
        os.chdir("sub")
        out, _ = self.ok()
        m = re.search(r"rules: (\S+RULES\.md) ·", out)
        self.assertIsNotNone(m, out)
        self.assertTrue(Path(m.group(1)).is_file(), m.group(1))
