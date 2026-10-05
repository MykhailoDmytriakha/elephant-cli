"""Phase «Promises kept», 2026-10-05 — the record said more than it knew, in four places (the owner's yes to the batch).

1. L2 · a new case's State said «next: open phase 1» after the phase was open — el's own pointer, left like a sign
   «opening soon» on an open shop, and the entry's thread ended on it. el takes its own words down; the agent's stay.
2. L5 · two promised runs (the tests and the load test) were «2 of 2 filled» by one run and both shown against it —
   one exam task handed in, two marked. Each promise is paired with its own proof: at done, in the Digest, in a goal.
3. L7 · a child's close cut off between its own record and the parent's (a killed process): the parent kept waiting
   for a closed child, said nothing, and its phase could not close. The parent names it with the repair, and `done` in
   the closed child delivers what it recorded — nothing in the child is written twice.
4. L6 · the case's own promise — a proof slot in Context — was checked by nothing: every phase could close and the
   case with them while the promise above them was never proved. The phase-level check (F12) one size up."""
import os
import re
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
        os.environ["EL_SESSION"] = "doer1005p"
        os.environ["EL_TWO_HANDS"] = "0"

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def cases(self) -> Path:
        return Path(self.tmp.name) / ".cases"

    def case(self, part: str = "") -> Path:
        return next(p.parent for p in sorted(self.cases().rglob("README.md")) if part in p.parent.name)

    def readme(self, part: str = "") -> str:
        return (self.case(part) / "README.md").read_text()

    def todo(self, part: str = "") -> str:
        return (self.case(part) / "TODO.md").read_text()


class TheSignComesDown(Base):
    def test_el_takes_its_own_pointer_down_when_the_phase_opens(self):
        run("case", "new", "papers", "--goal", "g")
        self.assertIn("- next: open phase 1", self.readme())
        code, out, err = run("phase", "open", "1", "Collect", "--goal", "g")
        self.assertEqual(code, 0, err)
        self.assertNotIn("- next: open phase 1", self.readme(), "a sign «opening soon» on an open shop")
        self.assertIn("el's own «next: open phase 1» is taken down", out)
        code, out, err = run()
        thread = next(ln for ln in out.split("\n") if ln.startswith("thread: "))
        self.assertNotIn("open phase 1", thread, "the entry's vector ended on a step already done")

    def test_the_agents_own_next_stays(self):
        run("case", "new", "papers", "--goal", "g")
        run("readme", "set", "next", "ask the clerk which forms")
        run("phase", "open", "1", "Collect", "--goal", "g")
        self.assertIn("- next: ask the clerk which forms", self.readme(), "el cannot judge the agent's words")


class EachPromiseHasItsOwnProof(Base):
    def setUp(self):
        super().setUp()
        run("case", "new", "load", "--goal", "g")
        run("phase", "open", "1", "Speed", "--goal", "g")
        run("todo", "add", "1", "make the page fast", "--expect", "[run: tests → OK] [run: load test → p95 under 300ms]")

    def test_one_run_fills_one_of_two(self):
        code, out, err = run("todo", "done", "1.1", "run:make test → 40 OK", "fast")
        self.assertEqual(code, 0, err)
        self.assertIn("expect 1.1: 1 of 2 filled — missing [run: load test → p95 under 300ms]", out, "one task handed in, two marked")
        self.assertEqual(out.count("— does it show that?"), 1, "the one run is shown against its own promise only")

    def test_two_runs_fill_both_and_each_stands_by_its_promise(self):
        run("todo", "done", "1.1", "run:make test → 40 OK", "fast")
        code, out, err = run("todo", "done", "1.1", "run:k6 run load.js → p95 210ms", "fast")
        run("todo", "add", "1", "write the report", "--expect", "[run: tests → OK] [run: load test → p95 under 300ms]")
        code, out, err = run("todo", "done", "1.2", "run:make test → 40 OK", "run:k6 run load.js → p95 210ms", "both")
        self.assertIn("expect 1.2: 2 of 2 filled", out)
        self.assertIn("[run: tests → OK] ← run make test → 40 OK", out)
        self.assertIn("[run: load test → p95 under 300ms] ← run k6 run load.js → p95 210ms", out)

    def test_the_digest_counts_a_short_promise(self):
        run("todo", "done", "1.1", "run:make test → 40 OK", "fast")
        code, out, err = run("phase", "close", "1", "fast enough", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)
        digest = next(self.case().glob("phases/1-*.md")).read_text()
        self.assertIn("expectations: 0 met · 1 short", digest)

    def test_a_goal_that_names_the_owner_twice_needs_two_words_of_the_owner(self):
        run("phase", "plan", "2", "Review", "--goal", "two signatures [owner] [owner]")
        run("todo", "done", "1.1", "run:make test → 40 OK", "fast")
        run("phase", "close", "1", "fast enough", "--reflect", "r", "--align", "a")
        run("phase", "open", "2", "Review")
        run("todo", "add", "2", "get the first signature", "--expect", "[owner]")
        run("todo", "done", "2.1", "owner", "signed")
        code, out, err = run("phase", "close", "2", "signed", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4, "one owner's word proved two promises")
        self.assertIn("promised [owner]", err)


class AClosedChildTheParentWaitsFor(Base):
    def setUp(self):
        super().setUp()
        run("case", "new", "moving", "--goal", "move to the new office")
        run("phase", "open", "1", "Papers", "--goal", "g")
        run("spawn", "documents", "--goal", "collect the documents")
        run("--case", "documents", "phase", "open", "1", "Collect", "--goal", "g")
        run("--case", "documents", "todo", "add", "1", "collect the passport copies", "--expect", "[owner]")
        run("--case", "documents", "todo", "done", "1.1", "owner", "collected")
        run("--case", "documents", "phase", "close", "1", "collected", "--reflect", "r", "--align", "a")
        parent = self.case("moving")
        self.before = {f: (parent / f).read_text() for f in ("README.md", "TODO.md", "JOURNAL.md")}

    def cut_off(self):
        """The child's close as a killed process leaves it: the child closed, the parent as before."""
        code, out, err = run("--case", "documents", "done", "the documents are collected")
        self.assertEqual(code, 0, err)
        for f, text in self.before.items():
            (self.case("moving") / f).write_text(text)

    def test_the_parent_names_the_cut_and_the_same_door_repairs_it(self):
        self.cut_off()
        code, out, err = run("--case", "moving")
        line = next(ln for ln in out.split("\n") if "is closed — its close never reached this case" in ln)
        self.assertIn("phase 1 waits for", line)
        command = re.search(r"→ (el --case \S+ done '.*') delivers", line).group(1)
        self.assertIn("'the documents are collected'", command, "the repair carries the child's own recorded words")
        code, out, err = run("--case", "documents", "done", "the documents are collected")
        self.assertEqual(code, 0, err)
        self.assertIn("was closed already", out)
        todo = self.todo("moving")
        self.assertNotIn("waits:", todo, "the parent stops waiting")
        self.assertIn("[x] 1.1 the documents are collected", todo)
        child_journal = (self.case("documents") / "JOURNAL.md").read_text()
        self.assertEqual(child_journal.count("дело закрыто"), 1, "nothing in the child is written twice")
        code, out, err = run("--case", "moving")
        self.assertNotIn("its close never reached this case", out)

    def test_a_closed_case_nobody_waits_for_refuses_a_second_close(self):
        run("--case", "documents", "done", "the documents are collected")
        code, out, err = run("--case", "documents", "done", "again")
        self.assertEqual(code, 4)
        self.assertIn("is closed already «the documents are collected»", err)


class TheCaseHoldsItsOwnPromise(Base):
    PROMISE = "[run: e2e by region → 3 of 3]"

    def setUp(self):
        super().setUp()
        run("case", "new", "signup", "--goal", f"registration works in three regions {self.PROMISE}")

    def prove_phase(self, n: int, slot: str):
        run("phase", "open", str(n), f"Rollout{n}", "--goal", f"rolled out {slot}")
        run("todo", "add", str(n), "run the end-to-end check", "--expect", slot)
        run("todo", "done", f"{n}.1", "run:e2e.sh → 3 of 3", "green")
        code, out, err = run("phase", "close", str(n), "rolled out", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 0, err)

    def test_a_promise_no_phase_carries_is_named_with_its_two_doors(self):
        code, out, err = run()
        line = next(ln for ln in out.split("\n") if ln.startswith(f"- the case promises {self.PROMISE}"))
        self.assertIn("the goal nobody works towards", line)
        self.assertIn(f"el phase plan 1 'Name' --goal '… {self.PROMISE}'", line)
        self.assertIn("el readme edit context goal '…'", line)

    def test_the_phase_that_carries_it_word_for_word_covers_it(self):
        code, out, err = run("phase", "plan", "1", "Rollout", "--goal", f"rolled out {self.PROMISE}")
        self.assertNotIn("no phase carries it yet", out, "this phase carries it")
        code, out, err = run()
        self.assertNotIn("the goal nobody works towards", out)

    def test_other_words_are_shown_side_by_side_and_hint_at_the_moment(self):
        code, out, err = run("phase", "plan", "1", "Rollout", "--goal", "rolled out [run: e2e → OK]")
        self.assertIn(f"the case promises {self.PROMISE} and no phase carries it yet", out, "copy it now, the words then match")
        code, out, err = run()
        self.assertIn("phases promise [run: e2e → OK] — the same in other words?", out)

    def test_done_refuses_over_an_unproved_promise_and_closes_once_it_is_proved(self):
        self.prove_phase(1, "[run: e2e → OK]")
        code, out, err = run("done", "registration works")
        self.assertEqual(code, 4, "every phase closed, the promise above them never proved")
        self.assertIn(f"cannot close the case: it promised {self.PROMISE} in Context and no phase proves it", err)
        self.assertIn("the phases promised [run: e2e → OK]: the same in other words?", err)
        self.assertIn("el readme edit context goal '…'", err)
        code, out, err = run("readme", "edit", "context", "goal", "registration works in three regions [run: e2e → OK]")
        self.assertEqual(code, 0, err)
        self.assertIn("registration works in three regions [run: e2e → OK]", self.readme())
        code, out, err = run("done", "registration works")
        self.assertEqual(code, 0, err)
        self.assertIn("case promises: 1 of 1 proved — [run: e2e → OK] by phase 1", out)

    def test_a_cancelled_phase_proves_nothing(self):
        run("phase", "plan", "1", "Rollout", "--goal", f"rolled out {self.PROMISE}")
        run("phase", "cancel", "1", "the region list changed")
        code, out, err = run()
        self.assertIn("the goal nobody works towards", out)

    def test_an_unknown_kind_is_refused_before_the_folder_exists(self):
        code, out, err = run("case", "new", "other", "--goal", "g [test: x]")
        self.assertEqual(code, 2)
        self.assertIn("is not a kind of proof", err)
        self.assertFalse(any("other" in p.name for p in self.cases().iterdir()), "no half-made case is left behind")


class ACaseWithoutPromisesLivesAsBefore(Base):
    def test_done_says_nothing_of_promises(self):
        run("case", "new", "plain", "--goal", "tidy the shelf")
        run("phase", "open", "1", "Tidy", "--goal", "g")
        run("todo", "add", "1", "sort the books", "--expect", "[owner]")
        run("todo", "done", "1.1", "owner", "sorted")
        run("phase", "close", "1", "tidy", "--reflect", "r", "--align", "a")
        code, out, err = run("done", "the shelf is tidy")
        self.assertEqual(code, 0, err)
        self.assertNotIn("case promises", out)

    def test_a_bare_owner_promise_is_proved_by_the_owners_word(self):
        run("case", "new", "sign", "--goal", "the lease is signed [owner]")
        run("phase", "open", "1", "Sign", "--goal", "g")
        run("todo", "add", "1", "get the signature", "--expect", "[owner]")
        run("todo", "done", "1.1", "owner", "signed")
        run("phase", "close", "1", "signed", "--reflect", "r", "--align", "a")
        code, out, err = run("done", "signed")
        self.assertEqual(code, 0, err)
        self.assertIn("case promises: 1 of 1 proved — [owner]", out)


class TheCodexBreaksOfPromisesHeld(Base):
    """Codex peer review of this batch, 2026-10-05 (gpt-6.1-sol, high): each break that changed behaviour, pinned."""

    def test_a_repair_names_the_child_by_its_path_when_two_parents_have_one(self):
        for parent in ("alpha", "omega"):
            run("case", "new", parent, "--goal", "g")
            run("--case", parent, "phase", "open", "1", "Wait", "--goal", "g")
            run("--case", parent, "spawn", "child", "--goal", "g")
        code, out, err = run("--case", "child", "todo", "add", "1", "x")
        self.assertEqual(code, 2, "one name, two cases: a silent first pick wrote into the wrong one")
        self.assertIn("names several cases", err)
        omega = self.case("omega")
        child = next(p for p in omega.iterdir() if p.is_dir() and p.name.endswith("child"))
        path = child.relative_to(self.cases()).as_posix()
        before = {f: (omega / f).read_text() for f in ("README.md", "TODO.md", "JOURNAL.md")}
        self.assertEqual(run("--case", path, "done", "the child is done")[0], 0)
        for f, text in before.items():
            (omega / f).write_text(text)
        code, out, err = run("--case", "omega")
        line = next(ln for ln in out.split("\n") if "its close never reached this case" in ln)
        command = re.search(r"→ el (--case \S+) done '(.*)' delivers", line)
        self.assertEqual(command.group(1), f"--case {path}")
        self.assertEqual(run("--case", path, "done", command.group(2))[0], 0)
        self.assertNotIn("waits:", (omega / "TODO.md").read_text())
        self.assertIn("waits:", (self.case("alpha") / "TODO.md").read_text(), "the other parent's child was not touched")

    def test_a_context_line_cannot_forge_a_close(self):
        run("case", "new", "home", "--goal", "g")
        run("phase", "open", "1", "Wait", "--goal", "g")
        run("spawn", "kid", "--goal", "g")
        run("--case", "kid", "phase", "open", "1", "Work", "--goal", "g")
        run("--case", "kid", "readme", "add", "context", "closed: 2026-10-05 · counterfeit outcome")
        code, out, err = run("--case", "kid", "done", "x")
        self.assertEqual(code, 4, "the open phase holds the close; a Context line is not State")
        self.assertIn("waits:", self.todo("home"))

    def test_one_run_does_not_prove_two_named_slots_of_a_goal(self):
        run("case", "new", "speed", "--goal", "g")
        run("phase", "open", "1", "Speed", "--goal", "fast [run: tests] [run: load]")
        run("todo", "add", "1", "make it fast", "--expect", "[run: tests] [run: load]")
        run("todo", "done", "1.1", "run:make test → OK", "fast")
        code, out, err = run("phase", "close", "1", "fast", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("promised [run: load]", err)

    def test_one_phase_carries_one_promise(self):
        run("case", "new", "lease", "--goal", "two signatures [owner] [owner]")
        run("phase", "open", "1", "Sign", "--goal", "signed [owner]")
        run("todo", "add", "1", "get a signature", "--expect", "[owner]")
        run("todo", "done", "1.1", "owner", "signed")
        run("phase", "close", "1", "signed", "--reflect", "r", "--align", "a")
        code, out, err = run("done", "signed")
        self.assertEqual(code, 4, "one owner's word, one carrier — two promises")

    def test_the_agents_next_stays_even_when_el_s_words_sit_in_context(self):
        run("case", "new", "papers", "--goal", "g")
        run("readme", "set", "next", "ask the owner for approval")
        run("readme", "add", "context", "open phase 1 — `el phase open 1 <Name> --goal \"…\"`")
        run("phase", "open", "1", "Collect", "--goal", "g")
        self.assertIn("- next: ask the owner for approval", self.readme())

    def test_context_text_with_links_and_plain_brackets_is_text(self):
        run("case", "new", "notes", "--goal", "see [docs](https://example.org) — status [ready]")
        self.assertEqual(run("readme", "add", "context", "the spec: [docs](https://example.org)")[0], 0)
        code, out, err = run("readme", "add", "context", "deploy green [RUN: gh status]")
        self.assertEqual(code, 2)
        self.assertIn("kinds are lowercase: [run: …]", err)
        run("readme", "add", "context", "quoted, not promised: `[run: x]` and [owner](https://example.org)")
        code, out, err = run()
        self.assertNotIn("the case promises", out, "a link and a code span are not promises")

    def test_a_result_that_begins_with_the_word_is_not_a_cancel(self):
        run("case", "new", "film", "--goal", "the clip is shot [owner]")
        run("phase", "open", "1", "Shoot", "--goal", "shot [owner]")
        run("todo", "add", "1", "shoot the clip", "--expect", "[owner]")
        run("todo", "done", "1.1", "owner", "shot")
        run("phase", "close", "1", "снято видео с успешным дублем", "--reflect", "r", "--align", "a")
        self.assertEqual(run("done", "shot")[0], 0)

    def test_printed_commands_run_as_printed(self):
        import shlex
        run("case", "new", "echo", "--goal", 'the greeting prints [run: echo "hello world" → hello world]')
        code, out, err = run()
        line = next(ln for ln in out.split("\n") if ln.startswith("- the case promises"))
        command = re.search(r"(el phase plan \d+ .+?) · or correct", line).group(1)
        argv = shlex.split(command.replace("…", "the greeting"))[1:]
        self.assertEqual(run(*argv)[0], 0, command)
        self.assertNotIn("the case promises", run()[1], "the copied slot matches word for word")

    def test_a_slot_too_long_for_a_plan_line_goes_in_at_the_opening(self):
        slot = "[run: " + "x" * 100 + "]"
        run("case", "new", "long", "--goal", f"g {slot}")
        code, out, err = run()
        self.assertIn("el phase open 1 'Name' --goal", out)
        self.assertIn("longer than a plan line", out)

    def test_a_cancelled_child_cut_off_is_repaired_as_a_cancel(self):
        run("case", "new", "trip", "--goal", "g")
        run("phase", "open", "1", "Wait", "--goal", "g")
        run("spawn", "visa", "--goal", "g")
        trip = self.case("trip")
        before = {f: (trip / f).read_text() for f in ("README.md", "TODO.md", "JOURNAL.md")}
        run("--case", "visa", "case", "cancel", "not needed any more")
        for f, text in before.items():
            (trip / f).write_text(text)
        code, out, err = run("--case", "visa", "done", "снято: not needed any more")
        self.assertEqual(code, 0, err)
        journal = (trip / "JOURNAL.md").read_text()
        self.assertIn("DECISION · снято → not needed any more", journal, "the parent hears a cancel as a cancel")

    def test_an_old_case_with_el_s_pointer_heals_on_its_next_write(self):
        run("case", "new", "old", "--goal", "g")
        run("phase", "open", "1", "Run", "--goal", "g")
        readme = self.case() / "README.md"
        text = readme.read_text().replace("## State\n", "## State\n- next: open phase 1 — `el phase open 1 <Name> --goal \"…\"`\n", 1)
        from elephant import store
        store.write(self.case(), "README.md", text)
        run()  # the entry renders README from the folder: el's old pointer goes on the next write
        self.assertNotIn("- next: open phase 1", readme.read_text())

    def test_a_bare_promise_is_hinted_when_a_phase_is_planned(self):
        run("case", "new", "sign", "--goal", "signed [owner]")
        code, out, err = run("phase", "plan", "1", "Sign", "--goal", "g")
        self.assertIn("the case promises [owner] and no phase carries it yet", out)


class TheSecondPassHeld(Base):
    """Codex, second pass on the batch, 2026-10-05: six more — each pinned."""

    def close_phase(self, n, goal, expect, *proofs):
        run("phase", "open", str(n), f"P{n}", "--goal", goal)
        run("todo", "add", str(n), "the work", "--expect", expect)
        run("todo", "done", f"{n}.1", *proofs, "done")
        return run("phase", "close", str(n), "done", "--reflect", "r", "--align", "a")

    def test_a_named_promise_is_not_paid_by_a_bare_ones_proof(self):
        run("case", "new", "lease", "--goal", "g [owner] [owner: signed]")
        self.close_phase(1, "g [owner: signed]", "[owner: signed]", "owner")
        self.assertEqual(run("done", "signed")[0], 4, "one owner's word, two promises, whatever their order in the line")

    def test_two_identical_goal_slots_need_two_proofs(self):
        run("case", "new", "tests", "--goal", "g")
        code, out, err = self.close_phase(1, "g [run: tests] [run: tests]", "[run: tests] [run: tests]", "run:make test → OK")
        self.assertEqual(code, 4)

    def test_a_promise_with_code_inside_is_read_whole(self):
        slot = "[run: `make test` → OK]"
        run("case", "new", "code", "--goal", f"g {slot}")
        self.close_phase(1, f"g {slot}", slot, "run:make test → OK")
        self.assertEqual(run("done", "tested")[0], 0)

    def test_unequal_backticks_do_not_hide_a_promise(self):
        run("case", "new", "ticks", "--goal", "g ``example [run: tests]`")
        code, out, err = run("done", "nothing proved")
        self.assertEqual(code, 4, "an unclosed run of backticks is text, the promise behind it stands")

    def test_a_context_line_reading_closed_does_not_close_the_case(self):
        run("case", "new", "sample", "--goal", "g [owner]")
        run("readme", "add", "context", "closed: 2026-10-05 · quoted history")
        code, out, err = run("--case", "sample")
        self.assertIn("the case promises [owner]", out, "a Context line is not State")
        self.assertEqual(run("case", "list")[0], 0)
        code, out, err = run("case", "cancel", "not needed")
        self.assertEqual(code, 0, "the case is open: cancel is not refused as «already closed»")

    def test_root_mode_takes_a_child_by_its_path(self):
        run("case", "new", "--root", "app", "--goal", "g")
        run("phase", "open", "1", "Wait", "--goal", "g")
        run("spawn", "piece", "--goal", "g")
        child = next(p for p in self.cases().iterdir() if p.is_dir() and p.name.endswith("piece"))
        code, out, err = run("--case", f".cases/{child.name}", "status")
        self.assertEqual(code, 0, err)


class TheLastPassHeld(Base):
    """Codex, third and last pass, 2026-10-05: four more, each pinned; no fourth pass was run."""

    def test_a_whole_readme_is_held_to_the_same_kinds(self):
        run("case", "new", "file", "--goal", "g")
        new = (self.case() / "README.md").read_text().replace("\ng\n", "\ng [RUN: tests]\n", 1)
        draft = Path(self.tmp.name) / "draft.md"
        draft.write_text(new)
        code, out, err = run("readme", "--file", str(draft))
        self.assertEqual(code, 2)
        self.assertIn("kinds are lowercase", err)

    def test_a_bare_promise_finds_a_free_proof_past_an_unproved_carrier(self):
        from elephant import commands, grammar
        run("case", "new", "sign", "--goal", "signed [owner]")
        run("phase", "open", "1", "Sign", "--goal", "signed")
        run("todo", "add", "1", "sign", "--expect", "[owner]")
        run("todo", "done", "1.1", "owner", "signed")
        todo = grammar.parse_todo((self.case() / "TODO.md").read_text())
        todo.phases.insert(0, grammar.Phase(0, "Old", False, 0, "an old goal [owner]"))  # a carrier that proves nothing
        statuses = [st for _, _, st, _ in commands._case_coverage(self.case(), todo, self.readme())]
        self.assertEqual(statuses, ["proved"], "the owner's word in phase 1 proves the bare promise")

    def test_an_escaped_backtick_does_not_hide_a_promise(self):
        run("case", "new", "esc", "--goal", "g \\`[owner]\\`")
        self.assertIn("the case promises [owner]", run()[1])

    def test_a_reference_link_is_not_a_promise(self):
        run("case", "new", "ref", "--goal", "signed by [owner][signer]")
        self.assertNotIn("the case promises", run()[1])


class TheLiveShape(Base):
    """The shape of the one live case with promises in its goal (2026-10-05), in neutral words: the case promised a deploy
    after each phase push and the tracker entries staged with SHA; every phase promised the short form and closed."""
    LONG_RUN, LONG_FILE = "[run: deploy status success after each phase push]", "[file: tracker entries removed or staged with SHA]"
    SHORT_RUN, SHORT_FILE = "[run: deploy status success]", "[file: tracker re-scoped entries]"

    def test_the_live_shape_is_named_refused_and_repaired_in_one_command(self):
        (Path(self.tmp.name) / "tracker.md").write_text("entries\n")
        run("case", "new", "bugs", "--goal", f"fix the tracker bugs, deploy green {self.LONG_RUN} {self.LONG_FILE}")
        run("phase", "open", "1", "Cleanup", "--goal", f"stale entries closed {self.SHORT_FILE} {self.SHORT_RUN}")
        run("todo", "add", "1", "re-scope the entries", "--expect", self.SHORT_FILE)
        run("todo", "add", "1", "deploy", "--expect", self.SHORT_RUN)
        run("todo", "done", "1.1", "file:tracker.md", "re-scoped")
        run("todo", "done", "1.2", "run:gh deploy status → success", "green")
        self.assertEqual(run("phase", "close", "1", "cleaned", "--reflect", "r", "--align", "a")[0], 0)
        code, out, err = run()
        order = [ln for ln in out.split("\n") if ln.startswith("- the case promises")]
        self.assertEqual(len(order), 2, "both long promises are named")
        self.assertIn(f"(phases promise {self.SHORT_RUN} — the same in other words?", order[0])
        self.assertEqual(run("done", "fixed")[0], 4)
        run("readme", "edit", "context", "goal", f"fix the tracker bugs, deploy green {self.SHORT_RUN} {self.SHORT_FILE}")
        code, out, err = run("done", "fixed")
        self.assertEqual(code, 0, err)
        self.assertIn("case promises: 2 of 2 proved", out)


if __name__ == "__main__":
    unittest.main()
