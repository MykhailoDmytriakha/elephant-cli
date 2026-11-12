"""Three places where el's output did not say what landed (2026-11-12).

The radio with Codex, #227–#228: for two days every event of his — four bugs of other phases and a merge of main among
them — went under a phase paused for the next one, by a `--phase` kept from an earlier command. el answered «logged: …»
and its hint asked whether the item the paused phase waits on had ended; the owner's TODO did not move. Work in a paused
phase stays legal: the write says what stands and the door for the work in flight.

A wall report, 2026-11-11: `todo add` refused by length three times, the agent read the output by `tail -1` — the last
line was an aside about numbering — took the items for added, and `done 4.4` met «no item 4.4» with no cause.

A report, 2026-11-11: `el relink <retired file> none` turned the Links line el drew from the file's summary into literal
text, which el then kept as the agent's — a fresh agent read it as a dead link. Each printed door is executed here."""
import os
import re
import shlex
import unittest

from tests.test_commands import run
from tests.test_long_case_1105 import Base


def door(text: str, verb: str) -> list:
    """The first printed `el <verb> …` command in TEXT, as argv (without `el`); quoted words kept whole."""
    m = re.search(rf"el {verb} [^·()—\n]*?(?=\s+(?:·|\(|—|$)|\n|$)", text)
    assert m, f"no `el {verb}` in: {text}"
    return shlex.split(m.group(0))[1:]


class Paused(Base):
    """Phase 1 paused for phase 2: 1.1 done, 1.2 waits for a repeat of the bug."""

    def setUp(self):
        super().setUp()
        self.ok("phase", "open", "1", "Editor", "--goal", "editor keeps text [run: tests → OK]")
        self.ok("todo", "add", "1", "repro the loop", "--expect", "[run: tests → OK]")
        self.ok("todo", "add", "1", "a new stack of the failure", "--expect", "[run: tests → OK]")
        self.ok("todo", "done", "1.1", "run:tests → OK", "17 runs, no error")
        self.ok("todo", "hold", "1.2", "waiting for: another real failure")
        self.ok("phase", "open", "2", "Chronology", "--goal", "older work kept [run: t → OK]", "--why", "next bug while 1 waits")
        self.ok("todo", "add", "2", "map the conflicts", "--expect", "[run: t → OK]")

    def tag_of_newest(self) -> str:
        return re.search(r"(?m)^- \d{4}-\d{2}-\d{2} \d{2}:\d{2} · (p\d+)", self.read("JOURNAL.md")).group(1)


class AWriteIntoAPausedPhase(Paused):
    def test_names_the_phase_in_flight_and_its_door_files_there(self):
        out, _ = self.ok("log", "--phase", "1", "RESULT", "the word topic bug closed locally")
        self.assertIn("phase 1 Editor is paused — phase 2 Chronology is in flight: this RESULT went into 1's story", out)
        self.ok(*door(out, "log"))
        self.assertEqual(self.tag_of_newest(), "p2")

    def test_a_phase_that_only_waits_hears_the_inspector(self):
        out, _ = self.ok("log", "--phase", "1", "DECISION", "QA target: the loop on the current build")
        self.assertIn("the inspector rule: phase 1 has nothing left but waiting (1.2)", out)

    def test_the_item_hint_does_not_point_into_a_paused_phase(self):
        os.environ["EL_HINTS"] = "1"
        out, _ = self.ok("log", "--phase", "1", "RESULT", "the word topic bug closed locally")
        self.assertNotIn("1.2 ended?", out)

    def test_a_write_into_the_phase_in_flight_says_nothing_of_it(self):
        out, _ = self.ok("log", "RESULT", "conflict mapped for dates")
        self.assertNotIn("is paused", out)
        self.assertEqual(self.tag_of_newest(), "p2")

    def test_open_of_a_paused_phase_speaks_as_resume(self):
        code, out, err = run("phase", "open", "1")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("already open", out + err)
        self.assertIn("phase 2 Chronology is in flight — 1 resumes by itself when 2 closes", err)
        self.ok(*door(err, "todo add"))  # the work meanwhile stays legal, as printed
        self.assertIn("1.3", self.read("TODO.md"))


LONG = ("Rotation of the audio archive ate four answers of the owner to the disputed records of the last cycle — the fix")


class TheAddRefusalAndTheMissingNumber(Base):
    def setUp(self):
        super().setUp()
        self.ok("phase", "open", "1", "Work", "--goal", "work done [run: t → OK]")
        self.ok("todo", "add", "1", "first", "--expect", "[run: t → OK]")
        self.ok("todo", "add", "1", "second", "--expect", "[run: t → OK]")

    def test_the_last_line_of_the_add_refusal_is_its_limit(self):
        self.assertGreater(len(LONG), 100)
        code, out, err = run("todo", "add", "1", LONG)
        self.assertEqual(code, 3)
        last = err.rstrip("\n").split("\n")[-1]
        self.assertIn("100 visible chars or fewer — rephrase", last)
        self.assertNotIn("1.3", self.read("TODO.md"))

    def test_no_item_names_the_refused_adds_of_the_session(self):
        run("todo", "add", "1", LONG)
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "rotation fixed")
        self.assertEqual(code, 4)
        self.assertIn("this session el refused `el todo add 1` 1 time(s), and nothing of it was added", err)
        self.assertIn("the item text is", err)
        self.ok(*door(err, "todo show"))

    def test_a_refused_add_of_another_phase_is_not_named(self):
        self.ok("phase", "plan", "2", "Later", "--goal", "later [run: t → OK]")
        run("todo", "add", "2", LONG)
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertNotIn("this session el refused", err)

    def test_a_refused_add_of_another_case_is_not_named(self):
        self.ok("case", "new", "other", "--goal", "another case")
        self.ok("--case", "other", "phase", "open", "1", "Other", "--goal", "o [run: t → OK]")
        run("--case", "other", "todo", "add", "1", LONG)
        code, out, err = run("--case", "shop", "todo", "done", "1.3", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertNotIn("this session el refused", err)

    # the second hand (Codex, 2026-11-12): el read the case and the phase back from argv — a suffix, `--case` after the
    # command and `01` each fooled that copy of the rules; the wall now keeps what el resolved when it refused
    def test_the_case_named_by_a_suffix_and_after_the_command(self):
        self.ok("case", "new", "audit-paused", "--goal", "another case")
        self.ok("--case", "paused", "phase", "open", "1", "Other", "--goal", "o [run: t → OK]")
        self.ok("--case", "paused", "todo", "add", "1", "first", "--expect", "[run: t → OK]")
        run("todo", "add", "1", LONG, "--case", "paused")
        code, out, err = run("todo", "done", "1.2", "run:t → OK", "x", "--case", "shop")  # shop has 1.2: not a wall
        self.assertEqual(code, 0, out + err)
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x", "--case", "shop")
        self.assertNotIn("this session el refused", err)
        code, out, err = run("--case", "paused", "todo", "done", "1.2", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertIn("this session el refused `el --case paused todo add 1` 1 time(s)", err)  # the call's --case carried

    def test_the_aside_door_runs_as_printed(self):
        code, out, err = run("todo", "add", "1", LONG)
        m = re.search(r"`(el todo add 1 \"…\" --before 1\.\d+)`", err)
        self.assertIsNotNone(m, err)
        self.ok(*shlex.split(m.group(1))[1:])
        todo = self.read("TODO.md")
        self.assertLess(todo.index("1.3 …"), todo.index("1.2 second"), "the re-added item stands before the one named")

    # the second hand, round 2: an empty phase answered «no items yet» without the refused add; a refusal raised before
    # the case was resolved (a trace of substitution) was kept without its case
    def test_an_empty_phase_names_the_refused_add(self):
        self.ok("phase", "plan", "2", "Later", "--goal", "later [run: t → OK]")
        run("todo", "add", "2", LONG)
        code, out, err = run("todo", "done", "2.1", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertIn("phase 2 has no items yet — this session el refused `el todo add 2` 1 time(s)", err)

    def test_a_refusal_before_the_case_is_resolved_keeps_its_case(self):
        code, _, _ = run("--case", "shop", "todo", "add", "1", "pay  for the permit")
        self.assertNotEqual(code, 0)
        code, out, err = run("--case", "shop", "todo", "done", "1.3", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertIn("todo add 1` 1 time(s)", err)
        code, _, _ = run("todo", "add", "1", "pay  for the permit")  # the hand: the case the session holds
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x")
        self.assertIn("todo add 1` 2 time(s)", err)

    # the second hand, round 3: a range of sub-items looked the parent up without the case; a call el could not read
    # (a usage error) carries no case and no phase — named as such, never guessed into this phase
    def test_a_range_of_sub_items_names_the_refused_add(self):
        run("todo", "add", "1", LONG)
        code, out, err = run("todo", "done", "1.3.1-1.3.2", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertIn("this session el refused `el todo add 1` 1 time(s)", err)

    def test_a_call_el_could_not_read_is_named_as_such(self):
        code, _, _ = run("todo", "add", "1", "third", "--before")
        self.assertEqual(code, 2)
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertNotIn("this session el refused `el todo add", err)
        self.assertIn("el refused 1 call(s) this session before it could read them — el feedback --wall lists them", err)
        self.assertTrue(err.rstrip().endswith("el todo show 1"), err)

    # the second hand, round 4: each branch of «no item» had its own copy of the cause — a readable refusal hid the count
    # of unread calls, a phase that does not exist did not name the add refused for it; two cases named went to the first
    def test_both_the_refused_add_and_the_unread_call_are_named(self):
        run("todo", "add", "1", LONG)
        run("todo", "add", "1", "third", "--before")
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x")
        self.assertIn("this session el refused `el todo add 1` 1 time(s)", err)
        self.assertIn("el refused 1 call(s) this session before it could read them", err)
        self.assertTrue(err.rstrip().endswith("el todo show 1"), err)

    def test_a_phase_that_does_not_exist_names_the_add_refused_for_it(self):
        run("todo", "add", "2", "third")
        code, out, err = run("todo", "done", "2.1", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertIn("there is no phase 2 (phases: 1) — this session el refused `el todo add 2` 1 time(s)", err)

    def test_two_cases_named_in_one_call_are_not_attributed(self):
        self.ok("case", "new", "other", "--goal", "another case")
        code, _, _ = run("--case", "shop", "todo", "add", "1", "third", "--case", "other")
        self.assertNotEqual(code, 0)
        code, out, err = run("--case", "shop", "todo", "done", "1.3", "run:t → OK", "x")
        self.assertNotIn("this session el refused `el", err)

    def test_a_refused_add_with_a_non_ascii_digit_breaks_nothing(self):  # the second hand, round 5: `²` crashed int()
        run("todo", "add", "²", "pay  for the permit")
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("Traceback", out + err)

    def test_a_non_ascii_digit_is_refused_not_a_traceback(self):  # the class of round 5: isdigit before int()
        for argv in (("todo", "add", "²", "text"), ("readme", "edit", "links", "²", "x"), ("todo", "move", "1.1", "²")):
            code, out, err = run(*argv)
            self.assertIn(code, (2, 4), f"{argv}: {out}{err}")
            self.assertNotIn("Traceback", out + err, argv)

    def test_a_huge_number_and_a_padded_one_are_not_phases(self):  # the second hand, round 6
        run("todo", "add", "9" * 5000, "text")
        run("todo", "add", " 1", LONG)
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("Traceback", out + err)
        self.assertNotIn("this session el refused `el todo add 1`", err)
        code, out, err = run("todo", "done", "9" * 5000 + ".1", "run:t → OK", "x")
        self.assertNotIn("Traceback", out + err)

    def test_every_no_item_door_names_the_cause(self):  # the second hand, round 7: move, after and a range had none of it
        run("todo", "add", "1", LONG)
        for argv in (("todo", "move", "1.1", "1.3"), ("todo", "after", "1.1", "1.3"),
                     ("todo", "done", "1.3-1.4", "run:t → OK", "x")):
            code, out, err = run(*argv)
            self.assertEqual(code, 4, f"{argv}: {out}{err}")
            self.assertIn("this session el refused `el todo add 1` 1 time(s)", err, argv)
        code, out, err = run("todo", "after", "1.1", "1.3")
        self.ok(*door(err, "todo add"))  # the door runs as printed: the phase's number, not `N`

    def test_the_remaining_doors_name_the_cause(self):  # the second hand, round 8: --before, a range in a missing phase,
        run("todo", "add", "1", LONG)                   # and sub-items under an item (a refused `todo add N.M`)
        code, out, err = run("todo", "add", "1", "third", "--before", "1.3")
        self.assertIn("this session el refused `el todo add 1` 1 time(s)", err)
        run("todo", "add", "2", "third")
        code, out, err = run("todo", "done", "2.1-2.2", "run:t → OK", "x")
        self.assertIn("no phase 2 in TODO.md — this session el refused `el todo add 2` 1 time(s)", err)
        run("todo", "add", "1.1", LONG)
        for argv in (("todo", "done", "1.1.1", "run:t → OK", "x"), ("todo", "done", "1.1.1-1.1.2", "run:t → OK", "x")):
            code, out, err = run(*argv)
            self.assertEqual(code, 4, f"{argv}: {out}{err}")
            self.assertIn("this session el refused `el todo add 1.1` 1 time(s)", err, argv)

    def test_sub_item_doors_and_numbers_as_the_add_reads_them(self):  # the second hand, round 9
        run("todo", "add", "1.1", LONG)
        code, out, err = run("todo", "add", "1.1", "x", "--before", "1.1.1")
        self.assertIn("this session el refused `el todo add 1.1` 1 time(s)", err)
        code, out, err = run("todo", "after", "1.2", "1.1.1")
        self.assertIn("this session el refused `el todo add 1.1` 2 time(s)", err)  # the --before add was refused too
        self.ok(*door(err, "todo add"))  # the door names the item a sub-item goes under
        run("todo", "add", " 1.2", LONG)  # the add reads it as item 1.2
        run("todo", "add", "١.٢", LONG)
        code, out, err = run("todo", "done", "1.2.1", "run:t → OK", "x")
        self.assertIn("this session el refused `el todo add 1.2` 2 time(s)", err)

    def test_a_phase_number_with_a_leading_zero(self):
        run("todo", "add", "01", LONG)
        code, out, err = run("todo", "done", "1.3", "run:t → OK", "x")
        self.assertEqual(code, 4)
        self.assertIn("this session el refused `el todo add 1` 1 time(s)", err)


class RelinkNoneOfARetiredFile(Base):
    def setUp(self):
        super().setUp()
        data = self.case() / "data"
        (data / "chart").mkdir(parents=True)
        (data / "chart-extracts.md").write_text("# Chart extracts\nsummary: extracts of five charts in one file\n\nbody\n",
                                                encoding="utf-8")
        self.ok()  # Links draws the file from its summary
        self.assertIn("[chart-extracts.md](data/chart-extracts.md) — extracts of five charts", self.read("README.md"))
        self.ok("log", "DECISION", "split [chart-extracts.md](data/chart-extracts.md) into one file per chart")
        for k in (1, 2):
            (data / "chart" / f"0{k}.md").write_text(f"# Chart {k}\nsummary: extract of chart {k}\n", encoding="utf-8")
        (data / "chart-extracts.md").unlink()

    def links(self) -> str:
        return self.read("README.md").split("## Links", 1)[1]

    def test_el_s_own_links_line_goes_with_the_file(self):
        out, _ = self.ok("relink", "data/chart-extracts.md", "none")
        self.assertNotIn("chart-extracts", self.links())
        self.assertIn("README Links: the line el drew from its summary went with the file", out)
        self.assertIn("`[chart-extracts.md](data/chart-extracts.md)`", self.read("JOURNAL.md"))  # the agent's words: literal
        self.ok()
        self.assertNotIn("chart-extracts", self.links())


if __name__ == "__main__":
    unittest.main()
