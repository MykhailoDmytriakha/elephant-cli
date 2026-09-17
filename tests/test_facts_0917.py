"""The owner's word of 2026-09-17: a result is the work («servers up»), a fact is what is now known and later work
builds on («the router never calls Premier Pricing in the CSET flow»). The fact chain is a search tree: branches
that worked became facts, dead branches stayed with their reason, the next agent starts from proved facts. So:
`fact:` as the fifth pocket (expected while open, established when done, verdict at done), `el facts` rendered
from those lines only, `expect:` on every item of a running phase (shown, not refused), refutation running down
`after` edges as «under question», never as an automatic reopen."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "api", "--goal", "g")
        run("phase", "open", "1", "Research", "--goal", "r")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class FactPocket(Base):
    def test_expected_fact_then_verdict_at_done(self):
        code, out, err = run("todo", "add", "1", "grep the DEV trace", "--expect", "[run: trace shows the outbound call]",
                             "--fact", "the router calls Premier Pricing for the pair")
        self.assertEqual(code, 0, err)
        self.assertIn("· expect · expected fact", out)
        self.assertIn("    - expect: [run: trace shows the outbound call]\n    - fact: the router calls Premier Pricing for the pair\n", self.read("TODO.md"))
        code, out, err = run("todo", "done", "1.1", "run:grep trace -> no outbound call", "trace read on three pods")
        self.assertEqual(code, 2, "an expected fact asks for its verdict")
        self.assertIn("expected the fact «the router calls Premier Pricing for the pair» — what is established now?", err)
        self.assertIn("--fact confirmed", err)
        code, out, err = run("todo", "done", "1.1", "run:grep trace -> no outbound call", "trace read on three pods",
                             "--fact", "the router never calls Premier Pricing in the CSET flow")
        self.assertEqual(code, 0, err)
        self.assertIn("fact 1.1: «the router never calls Premier Pricing in the CSET flow» — established; it enters the chain: el facts", out)
        todo = self.read("TODO.md")
        self.assertIn("    - result: trace read on three pods\n      - run: grep trace → no outbound call\n    - fact: the router never calls Premier Pricing in the CSET flow\n", todo)
        self.assertIn("· fact: the router never calls Premier Pricing in the CSET flow", self.read("JOURNAL.md"))

    def test_confirmed_none_and_later_fact(self):
        run("todo", "add", "1", "a", "--expect", "[owner]", "--fact", "X is true")
        code, out, err = run("todo", "done", "1.1", "owner", "ok", "--fact", "confirmed")
        self.assertEqual(code, 0, err)
        self.assertIn("    - fact: X is true\n", self.read("TODO.md"))
        self.assertIn("· fact confirmed: X is true", self.read("JOURNAL.md"))
        run("todo", "add", "1", "b", "--expect", "[owner]", "--fact", "Y is true")
        code, out, err = run("todo", "done", "1.2", "owner", "ok", "--fact", "-")
        self.assertEqual(code, 0, err)
        self.assertNotIn("Y is true", self.read("TODO.md"))
        self.assertIn("· no fact", self.read("JOURNAL.md"))
        run("todo", "add", "1", "c", "--expect", "[owner]")
        code, out, err = run("todo", "done", "1.3", "owner", "servers up, no errors")
        self.assertEqual(code, 0, "no expected fact: no verdict asked — the work is the outcome")
        code, out, err = run("todo", "fact", "1.3", "Z holds on DEV")
        self.assertEqual(code, 0, err)
        self.assertIn("fact 1.3 (established): «Z holds on DEV»", out)
        self.assertIn("RESULT · 1.3: fact — Z holds on DEV", self.read("JOURNAL.md"))
        code, out, _ = run("todo", "fact", "1.3", "-")
        self.assertIn("fact 1.3: none (was: «Z holds on DEV»)", out)


class ExpectOnEveryRunningItem(Base):
    def test_add_without_expect_warns_and_order_names_the_gaps_until_filled(self):
        code, out, err = run("todo", "add", "1", "start the servers")
        self.assertEqual(code, 0, "content: shown, not refused")
        self.assertIn("1.1 has no expect: — every item of a running phase says what is expected", err)
        run("todo", "add", "1", "second")
        order = run()[1].split("## Order")[1]
        self.assertIn("phase 1 Research: 2 open item(s) without expect: — 1.1, 1.2 → el todo expect N.M", order)
        run("todo", "expect", "1.1", "[run: servers up]")
        run("todo", "expect", "1.2", "[owner]")
        self.assertNotIn("without expect", run()[1])
        run("phase", "plan", "2", "Later", "--goal", "l")
        code, out, err = run("todo", "add", "2", "an idea for later")
        self.assertNotIn("has no expect", err, "a planned phase is not running: parked ideas need no expectation yet")
        self.assertNotIn("phase 2 Later", run()[1].split("## Order")[1])


class EntryStaysLean(Base):
    def test_done_items_collapse_on_entry_but_stay_whole_in_the_file(self):
        run("todo", "add", "1", "a", "--why", "w", "--expect", "[owner]", "--fact", "A holds")
        run("todo", "add", "1", "b", "--why", "w2", "--expect", "[owner]")
        run("todo", "done", "1.1", "owner", "did a", "--fact", "confirmed")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        entry_todo = out.split("# TODO")[1].split("# JOURNAL")[0]
        self.assertIn("  - [x] 1.1 a\n    - fact: A holds\n", entry_todo, "a done item: its line and its fact")
        self.assertNotIn("result: did a", entry_todo, "result and proofs are history — the file keeps them")
        self.assertNotIn("- why: w\n", entry_todo)
        self.assertIn("  - [ ] 1.2 b\n    - why: w2\n    - expect: [owner]\n", entry_todo, "an open item keeps its pockets")
        self.assertIn("(1 done item(s) collapsed here — result and proofs: TODO.md · one item in full: el todo show N.M)", out)
        self.assertIn("    - result: did a\n      - owner\n    - fact: A holds\n", self.read("TODO.md"))
        self.assertIn("## Order", out, "the tail is never lost")


class JournalHeadlinesAreCapped(Base):
    def test_ten_dense_entries_show_at_most_the_cap_and_name_the_rest(self):
        for i in range(30):
            run("log", "DECISION", f"decision number {i} about something")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        journal = out.split("# JOURNAL")[1].split("## Order")[0]
        event_lines = [ln for ln in journal.splitlines() if ln.startswith("  ") and " · " in ln and not ln.startswith("  …")]
        self.assertEqual(len(event_lines), 24, "24 headlines (the PHASE of open + 23 decisions), not 31")
        self.assertIn("… +", journal)
        self.assertIn("event line(s) more in these entries — JOURNAL.md (the entry shows 24)", journal)


class TheChain(Base):
    def setUp(self):
        super().setUp()
        (self.case / "research").mkdir()
        (self.case / "research" / "db.md").write_text("# db\nsummary: db\n", encoding="utf-8")
        run("todo", "add", "1", "grep the trace", "--expect", "[run: trace]", "--fact", "the router calls Premier")
        run("todo", "add", "1", "read the DB", "--expect", "[file: research/db.md]", "--fact", "the DB holds the live pair")
        run("todo", "add", "1", "combine — after: 1.1, 1.2", "--expect", "[run: rerun]", "--fact", "the discount applies end to end")
        run("todo", "add", "1", "start the servers", "--expect", "[run: up]")
        run("todo", "add", "1", "search the RAML specs", "--expect", "[file: research/raml.md]", "--fact", "the pair is in the specs")

    def test_el_facts_renders_the_tree_and_the_entry_counts(self):
        run("todo", "done", "1.1", "run:grep -> no call", "read", "--fact", "the router never calls Premier in the CSET flow")
        run("todo", "done", "1.2", "file:research/db.md", "read", "--fact", "confirmed")
        run("todo", "done", "1.4", "run:make up -> ok", "servers up")
        run("todo", "cancel", "1.5", "the specs hold test data only")
        code, out, err = run("facts")
        self.assertEqual(code, 0, err)
        self.assertIn("facts — ", out)
        self.assertIn("2 established · 0 under question · 1 expected · 1 dead branch(es) · 1 done item(s) without a fact (work, not knowledge)", out)
        self.assertIn("  ✓ 1.1 the router never calls Premier in the CSET flow\n        run: grep → no call\n", out)
        self.assertIn("  ✓ 1.2 the DB holds the live pair\n        file: [db.md](research/db.md)\n", out)
        self.assertIn("  · 1.3 the discount applies end to end   ← after: 1.1, 1.2\n        expect: [run: rerun]\n", out)
        self.assertIn("  ✗ 1.5 search the RAML specs   ← снято ", out)
        self.assertIn(": the specs hold test data only", out)
        self.assertNotIn("1.4", out.split("\n", 1)[1], "work without a fact is counted, not listed")
        self.assertIn("facts: 2 established · 1 expected — el facts", run()[1])

    def test_refutation_runs_down_the_chain_as_a_question_not_a_reopen(self):
        run("todo", "done", "1.1", "run:grep -> call seen", "read", "--fact", "confirmed")
        run("todo", "done", "1.2", "file:research/db.md", "read", "--fact", "confirmed")
        run("todo", "done", "1.3", "run:curl -> rate changed", "combined", "--fact", "confirmed")
        code, out, err = run("todo", "reopen", "1.1", "the exact DEV trace shows no outbound call")
        self.assertEqual(code, 0, err)
        self.assertIn("standing on it, done: 1.3 — a fact resting on a refuted one is under question", out)
        self.assertIn("  - [x] 1.3 combine — after: 1.1, 1.2", self.read("TODO.md"), "el never reopens the dependents itself")
        order = run()[1].split("## Order")[1]
        self.assertIn("1.3 «the discount applies end to end» rests on 1.1, open again — a fact on a refuted one is under question", order)
        self.assertIn("finish 1.1 · or el todo reopen 1.3", order)
        out = run("facts")[1]
        self.assertIn("1 established · 1 under question · 2 expected", out)
        self.assertIn("  ? 1.3 the discount applies end to end   ← rests on 1.1, open again", out)
        self.assertIn("  · 1.1 the router calls Premier", out, "the reopened item keeps its fact as an expectation")
        self.assertIn("facts: 1 established · 1 under question · 2 expected — el facts", run()[1])
        run("todo", "reopen", "1.3", "rests on a refuted fact")
        self.assertNotIn("under question", run()[1].split("## Order")[1])

    def test_closed_phase_facts_are_read_back_and_the_digest_lists_them(self):
        run("todo", "done", "1.1", "run:grep -> no call", "read", "--fact", "the router never calls Premier in the CSET flow")
        run("todo", "done", "1.2", "file:research/db.md", "read", "--fact", "confirmed")
        run("todo", "done", "1.3", "run:curl -> rate changed", "combined", "--fact", "confirmed")
        run("todo", "done", "1.4", "run:make up -> ok", "servers up")
        run("todo", "cancel", "1.5", "test data only")
        run("log", "RESULT", "r")
        code, out, err = run("phase", "close", "1", "done", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-research.md")
        self.assertIn("- facts (3):\n  - 1.1 the router never calls Premier in the CSET flow\n  - 1.2 the DB holds the live pair\n  - 1.3 the discount applies end to end\n", pf)
        self.assertIn("  - fact: the DB holds the live pair\n", pf)
        out = run("facts")[1]
        self.assertIn("phase 1 Research (closed)", out)
        self.assertIn("  ✓ 1.3 the discount applies end to end   ← after: 1.1, 1.2", out)
        self.assertIn("3 established", out)


if __name__ == "__main__":
    unittest.main()
