"""The owner's word of 2026-09-24/25 (synchronization over the ART harness, Anthropic 2026-09-23): «I set the direction,
the agent decomposes and delivers, Elephant keeps the order». Done by one hand, accepted by another: a fresh session
(another chat, another agent) accepts or returns, el records who and whether the session was another, a self-acceptance
passes only by the owner's word. The acceptor gets its brief from el — el prints the prompt, it never launches anyone.
A thing returned again and again is stuck, and Order says so. Everything that is not for the running phase goes to
the general list (Later) and the next phase is formed from it at the boundary; a planned phase may run before an earlier
one when a hidden blocker is found — with a reason, never through a false «cancelled»."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "api", "--goal", "the service answers in under a second")
        run("phase", "open", "1", "Speed", "--goal", "p95 under a second")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "evidence").mkdir()
        (self.case / "evidence" / "k6.txt").write_text("p95 820 ms\n", encoding="utf-8")
        run("todo", "add", "1", "cache the price lookup", "--why", "the owner waits two seconds on every page",
            "--expect", "[run: k6 → p95]")

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")

    def done(self, session: str = "aaaaaaaa1111"):
        os.environ["EL_SESSION"] = session
        code, out, err = run("todo", "done", "1.1", "run:k6 -> p95 820 ms", "file:evidence/k6.txt", "price lookup cached, p95 820 ms")
        self.assertEqual(code, 0, err)
        return out


class Accept(Base):
    def test_accept_by_another_session_is_recorded_in_todo_and_journal(self):
        self.done("aaaaaaaa1111")
        os.environ["EL_SESSION"] = "bbbbbbbb2222"
        code, out, err = run("todo", "accept", "1.1", "--by", "codex", "re-ran k6 and read k6.txt: p95 820 ms")
        self.assertEqual(code, 0, err)
        self.assertIn("    - accepted: codex · another session", self.read("TODO.md"))
        self.assertIn("DECISION · принято 1.1: codex · другая сессия — re-ran k6", self.read("JOURNAL.md"))
        self.assertIn("accepted: 1.1 by codex (another session)", out)

    def test_the_doer_session_rides_under_its_result(self):
        self.done("aaaaaaaa1111")
        self.assertIn("RESULT · 1.1: run k6 → p95 820 ms", self.read("JOURNAL.md"))
        self.assertIn("    session: aaaaaaaa", self.read("JOURNAL.md"))
        self.assertNotIn("price lookup cached, p95 820 ms …", run()[1], "the headline carries no body marker for the session")

    def test_same_session_is_named_not_hidden(self):
        self.done("aaaaaaaa1111")
        code, out, err = run("todo", "accept", "1.1", "--by", "claude", "looked at it again")
        self.assertEqual(code, 0, err)
        self.assertIn("accepted: claude · same session", self.read("TODO.md"))
        self.assertIn("same session as the doer", err)

    def test_no_session_known_is_said(self):
        os.environ.pop("EL_SESSION", None)
        run("todo", "done", "1.1", "run:k6 -> p95 820 ms", "cached")
        code, out, err = run("todo", "accept", "1.1", "--by", "codex", "re-ran k6")
        self.assertEqual(code, 0, err)
        self.assertIn("accepted: codex · session not given", self.read("TODO.md"))

    def test_self_acceptance_is_refused_the_owner_word_passes(self):
        self.done()
        code, _, err = run("todo", "accept", "1.1", "--by", "self", "fine")
        self.assertEqual(code, 2)
        self.assertIn("el todo brief 1.1", err)
        self.assertIn("--by owner", err)
        code, _, err = run("todo", "accept", "1.1", "--by", "owner", "the owner looked at the page: fast now")
        self.assertEqual(code, 0, err)
        self.assertIn("accepted: owner · the owner's word", self.read("TODO.md"))

    def test_accept_needs_by_and_words_and_a_done_item(self):
        code, _, err = run("todo", "accept", "1.1", "--by", "codex", "checked")
        self.assertEqual(code, 4)
        self.assertIn("not done", err)
        self.done()
        self.assertEqual(run("todo", "accept", "1.1", "checked")[0], 2)
        self.assertEqual(run("todo", "accept", "1.1", "--by", "codex")[0], 2)

    def test_accepted_line_is_rendered_not_counted_and_only_under_a_done_item(self):
        self.done("a1")
        os.environ["EL_SESSION"] = "b2"
        run("todo", "accept", "1.1", "--by", "codex", "re-ran")
        todo = grammar.parse_todo(stamp.split(self.read("TODO.md"))[0])
        self.assertEqual(todo.errors, [])
        self.assertTrue(todo.phase(1).items[0].accepted.startswith("codex · another session"))
        bad = self.read("TODO.md").replace("  - [x] 1.1", "  - [ ] 1.1")
        errs = grammar.parse_todo(stamp.split(bad)[0]).errors
        self.assertTrue(any("accepted" in str(e) for e in errs), errs)

    def test_accepted_travels_into_the_phase_file_at_close(self):
        self.done("a1")
        os.environ["EL_SESSION"] = "b2"
        run("todo", "accept", "1.1", "--by", "codex", "re-ran")
        run("log", "RESULT", "p95 820 ms")
        code, _, err = run("phase", "close", "1", "p95 under a second", "--reflect", "measure first", "--align", "next: errors")
        self.assertEqual(code, 0, err)
        self.assertIn("  - accepted: codex · another session", (self.case / "phases" / "1-speed.md").read_text(encoding="utf-8"))


class Return(Base):
    def test_reopen_by_the_acceptor_names_it_and_clears_the_acceptance(self):
        self.done("a1")
        os.environ["EL_SESSION"] = "b2"
        run("todo", "accept", "1.1", "--by", "codex", "re-ran")
        code, out, err = run("todo", "reopen", "1.1", "--by", "codex", "p95 is 1400 ms on a cold cache")
        self.assertEqual(code, 0, err)
        self.assertIn("DECISION · 1.1 возвращён в работу — p95 is 1400 ms on a cold cache (приёмка: codex", self.read("JOURNAL.md"))
        self.assertNotIn("accepted:", self.read("TODO.md"))

    def test_three_returns_make_a_stuck_item_in_order(self):
        for k in range(3):
            self.done("a1")
            run("todo", "reopen", "1.1", "--by", "codex", f"still slow, try {k}")
        out = run()[1]
        self.assertIn("1.1 returned 3 times", out)
        self.assertIn("el todo cancel 1.1", out)

    def test_two_returns_are_not_yet_stuck(self):
        for k in range(2):
            self.done("a1")
            run("todo", "reopen", "1.1", f"try {k}")
        self.assertNotIn("returned 2 times", run()[1])


class Brief(Base):
    def test_brief_carries_the_owner_words_the_promise_the_proofs_and_both_verdicts(self):
        self.done()
        code, out, err = run("todo", "brief", "1.1")
        self.assertEqual(code, 0, err)
        for piece in ("the service answers in under a second",       # the case goal
                      "p95 under a second",                          # the phase goal
                      "cache the price lookup",                       # the item
                      "the owner waits two seconds on every page",   # why — the owner's words
                      "[run: k6 → p95]",                              # the promise written before the work
                      "price lookup cached, p95 820 ms",              # what the doer says came out
                      "evidence/k6.txt",                              # the proof, reachable from the project root
                      f"el --case {self.case.name} todo accept 1.1 --by",
                      f"el --case {self.case.name} todo reopen 1.1 --by"):
            self.assertIn(piece, out)
        self.assertIn("FRESH", out)

    def test_brief_on_an_open_item_is_refused(self):
        code, _, err = run("todo", "brief", "1.1")
        self.assertEqual(code, 4)
        self.assertIn("el todo done 1.1", err)


class TwoHandsRule(Base):
    def setUp(self):
        super().setUp()
        run("readme", "add", "context", "rule: two hands — the owner agrees each phase's scope, a fresh session accepts each done item")

    def test_order_names_the_done_items_nobody_accepted(self):
        self.done("a1")
        out = run()[1]
        self.assertIn("1 done item(s) not accepted — 1.1", out)
        self.assertIn("el todo brief 1.1", out)

    def test_close_refuses_over_an_unaccepted_item_then_passes(self):
        self.done("a1")
        run("log", "RESULT", "p95 820 ms")
        code, _, err = run("phase", "close", "1", "fast", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("not accepted", err)
        os.environ["EL_SESSION"] = "b2"
        run("todo", "accept", "1.1", "--by", "codex", "re-ran k6")
        code, _, err = run("phase", "close", "1", "fast", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)

    def test_acceptance_line_on_entry(self):
        self.done("a1")
        self.assertIn("acceptance: 0 of 1 done accepted", run()[1])


class Later(Base):
    def todo(self):
        return grammar.parse_todo(stamp.split(self.read("TODO.md"))[0])

    def test_a_thought_not_for_this_phase_goes_to_later_with_its_date(self):
        code, out, err = run("todo", "add", "later", "cache warm-up on deploy", "--why", "the acceptor saw a cold cache")
        self.assertEqual(code, 0, err)
        import datetime as dt
        today = dt.date.today().isoformat()
        text = self.read("TODO.md")
        self.assertIn(f"## Later\n  - [ ] L1 cache warm-up on deploy — since: {today}\n    - why: the acceptor saw a cold cache", text)
        todo = self.todo()
        self.assertEqual(todo.errors, [])
        self.assertEqual([(it.m, it.text) for it in todo.later], [(1, "cache warm-up on deploy")])
        self.assertIn("added: L1", out)

    def test_numbers_are_for_life_in_later_too(self):
        run("todo", "add", "later", "one")
        run("todo", "cancel", "L1", "not needed")  # the journal speaks of L1 now: the number is never reused
        run("todo", "add", "later", "two")
        self.assertIn("L2 two", self.read("TODO.md"))

    def test_a_rule_name_in_the_journal_is_not_a_later_number(self):
        # found live, 2026-09-25: this very case's journal speaks of the rule class «L10», and the first line became L10
        run("log", "DECISION", "people cards (L10) stay inside .cases; a GPU L4 is not ours")
        run("todo", "add", "later", "idea")
        self.assertIn("  - [ ] L1 idea", self.read("TODO.md"))

    def test_taken_into_a_phase_at_the_boundary(self):
        run("todo", "add", "later", "cache warm-up on deploy", "--why", "cold cache")
        code, out, err = run("todo", "move", "L1", "1")
        self.assertEqual(code, 0, err)
        todo = self.todo()
        self.assertEqual(todo.later, [])
        it = todo.phase(1).items[-1]
        self.assertEqual((it.m, it.text, it.why), (2, "cache warm-up on deploy", "cold cache"))
        self.assertIn("L1 → 1.2", out)

    def test_an_open_item_goes_to_later_with_its_pockets_a_done_one_does_not(self):
        code, out, err = run("todo", "move", "1.1", "later")
        self.assertEqual(code, 0, err)
        todo = self.todo()
        self.assertEqual(todo.phase(1).items, [])
        self.assertEqual((todo.later[0].text, todo.later[0].why), ("cache the price lookup", "the owner waits two seconds on every page"))
        self.assertIn("1.1 → L1", out)
        run("todo", "move", "L1", "1")
        self.done()
        self.assertEqual(run("todo", "move", "1.2", "later")[0], 4)

    def test_cancel_from_later_leaves_a_reason(self):
        run("todo", "add", "later", "rewrite in rust")
        code, _, err = run("todo", "cancel", "L1", "the cache was enough")
        self.assertEqual(code, 0, err)
        self.assertIn("DECISION · снято L1 «rewrite in rust» — the cache was enough", self.read("JOURNAL.md"))
        self.assertEqual(self.todo().later, [])

    def test_a_later_line_is_not_done_before_it_is_taken(self):
        run("todo", "add", "later", "idea")
        code, _, err = run("todo", "done", "L1", "owner", "x")
        self.assertIn(code, (2, 4))
        self.assertIn("el todo move L1", err)

    def test_the_boundary_shows_the_general_list(self):
        run("todo", "add", "later", "cache warm-up on deploy")
        self.done()
        run("log", "RESULT", "p95 820 ms")
        code, out, err = run("phase", "close", "1", "fast", "--reflect", "measure first", "--align", "next: warm-up")
        self.assertEqual(code, 0, err)
        self.assertIn("general list (Later) — 1 line(s) wait for this boundary: L1 «cache warm-up on deploy»", out)
        self.assertIn("el todo move L1 N", out)

    def test_three_boundaries_passed_by_is_an_order_line(self):
        run("todo", "add", "later", "cache warm-up on deploy")
        body, _ = stamp.split(self.read("TODO.md"))
        import re
        body = re.sub(r"since: \d{4}-\d{2}-\d{2}", "since: 2026-01-01", body)
        (self.case / "TODO.md").write_text(stamp.apply(body), encoding="utf-8")
        jbody, _ = stamp.split(self.read("JOURNAL.md"))
        head, rest = jbody.split("\n", 1)
        closes = "".join(f"- 2026-0{m}-01 10:00 · p9\n  PHASE · Old{m} закрыта → done\n\n" for m in (4, 3, 2))
        (self.case / "JOURNAL.md").write_text(stamp.apply(head + "\n\n" + rest.lstrip("\n").rstrip("\n") + "\n\n" + closes.rstrip("\n") + "\n"),
                                              encoding="utf-8")
        out = run()[1]
        self.assertIn("L1 «cache warm-up on deploy» lay through 3 phase closes", out)

    def test_entry_shows_later(self):
        run("todo", "add", "later", "cache warm-up on deploy")
        self.assertIn("L1 cache warm-up on deploy", run()[1])


class PhaseMoves(Base):
    def setUp(self):
        super().setUp()
        self.done()
        run("log", "RESULT", "p95 820 ms")
        code, _, err = run("phase", "close", "1", "fast", "--reflect", "measure first", "--align", "data before deploy")
        self.assertEqual(code, 0, err)
        run("phase", "plan", "2", "Data", "--goal", "the data is migrated")
        run("phase", "plan", "3", "Deploy", "--goal", "the new build is live")

    def test_a_planned_phase_runs_first_only_with_a_reason(self):
        code, _, err = run("phase", "open", "3")
        self.assertEqual(code, 4)
        self.assertIn('el phase open 3 --why', err)
        code, out, err = run("phase", "open", "3", "--why", "the deploy pipeline blocks the migration")
        self.assertEqual(code, 0, err)
        self.assertIn("DECISION · фаза 3 раньше запланированных 2 — the deploy pipeline blocks the migration", self.read("JOURNAL.md"))
        self.assertIn("progress: 1 Speed ✓ · 2 Data · 3 Deploy ▶", self.read("README.md"))

    def test_the_phase_in_flight_takes_the_journal_not_the_first_planned(self):
        run("phase", "open", "3", "--why", "blocker found")
        run("log", "RESULT", "pipeline green")
        self.assertRegex(self.read("JOURNAL.md"), r"- \d{4}-\d{2}-\d{2} \d{2}:\d{2} · p3\n(?:  .+\n)*  RESULT · pipeline green")

    def test_one_phase_in_flight_holds_when_the_order_is_changed(self):
        run("phase", "open", "3", "--why", "blocker found")
        code, _, err = run("phase", "open", "2")
        self.assertEqual(code, 4)
        self.assertIn("in flight", err)

    def test_the_skipped_phase_opens_after_the_early_one_closed(self):
        code, _, err = run("phase", "open", "3", "--why", "blocker found")
        self.assertEqual(code, 0, err)
        self.assertIn("PHASE · Deploy открыта", self.read("JOURNAL.md"))
        run("todo", "add", "3", "fix the pipeline", "--expect", "[run: ci → green]")
        run("todo", "done", "3.1", "run:ci -> green", "pipeline fixed")
        code, _, err = run("phase", "close", "3", "pipeline fixed", "--reflect", "look for blockers first", "--align", "now the data")
        self.assertEqual(code, 0, err)
        code, _, err = run("phase", "open", "2")
        self.assertEqual(code, 0, err)
        self.assertIn("2 Data ▶ · 3 Deploy ✓", self.read("README.md"))


class ForcedClose(Base):
    def test_close_early_sends_the_rest_to_later(self):
        run("todo", "add", "1", "shard the database", "--why", "only if the cache is not enough")
        self.done()
        run("log", "RESULT", "p95 820 ms")
        code, out, err = run("phase", "close", "1", "fast enough", "--reflect", "r", "--align", "a", "--rest", "later")
        self.assertEqual(code, 0, err)
        todo = grammar.parse_todo(stamp.split(self.read("TODO.md"))[0])
        self.assertEqual([(it.m, it.text, it.why) for it in todo.later], [(1, "shard the database", "only if the cache is not enough")])
        self.assertIn("DECISION · остаток фазы 1 → общий список: 1.2 → L1", self.read("JOURNAL.md"))
        self.assertIn("1.2 → L1", out)

    def test_a_refused_early_close_moves_nothing(self):
        run("todo", "add", "1", "shard the database")
        self.done()
        before = self.read("TODO.md")
        code, _, err = run("phase", "close", "1", "fast enough", "--rest", "later")  # no RESULT, no reflect/align
        self.assertEqual(code, 4)
        self.assertEqual(self.read("TODO.md"), before)


class AgreedScope(Base):
    def test_agree_records_the_owner_words(self):
        code, out, err = run("phase", "agree", "1", "only the cache, no sharding")
        self.assertEqual(code, 0, err)
        self.assertIn("DECISION · объём фазы 1 утверждён владельцем: «only the cache, no sharding»", self.read("JOURNAL.md"))

    def test_under_two_hands_a_running_phase_without_agreed_scope_is_named(self):
        run("readme", "add", "context", "rule: two hands — the owner agrees each phase's scope, a fresh session accepts each done item")
        self.assertIn("phase 1 Speed runs without the owner's agreed scope", run()[1])
        run("phase", "agree", "1", "only the cache")
        self.assertNotIn("agreed scope", run()[1])


class Thread(Base):
    def test_entry_opens_with_the_thread_goal_phase_item_step(self):
        run("readme", "set", "next", "measure the cold cache")
        out = run()[1]
        line = next(ln for ln in out.split("\n") if ln.startswith("thread: "))
        self.assertEqual(line, "thread: goal «the service answers in under a second» → phase 1 Speed «p95 under a second» → "
                               "item 1.1 «cache the price lookup» (why: the owner waits two seconds on every page) → next: «measure the cold cache»")
        self.assertLess(out.index("thread: "), out.index("## Context"), "the thread comes before the files it summarizes")

    def test_every_item_ended_is_said_in_the_thread(self):
        self.done()
        out = run()[1]
        self.assertIn("→ phase 1 Speed «p95 under a second» → every item ended: el phase close 1", out)


if __name__ == "__main__":
    unittest.main()
