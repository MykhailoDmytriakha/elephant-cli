"""The polygon, 2026-10-08: eighteen refusals «`1` — use N.M» on `el todo show 1` across the runs — agents ask for one
phase by its number, as a bare `el todo` shows the plan — and the maintainer typed `el phase show 18`. One phase is shown:
an open one by its lines of TODO, a closed one by its folded line and its file."""
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
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="show1008", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          EL_TWO_HANDS="0")
        run("case", "new", "probe", "--goal", "g")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def two_phases(self):
        run("phase", "open", "1", "First", "--goal", "first done")
        run("todo", "add", "1", "step one")
        run("todo", "done", "1.1", "run:one → ok", "one")
        run("phase", "close", "1", "first done", "--reflect", "r", "--align", "a")
        run("phase", "open", "2", "Second", "--goal", "second done")
        run("todo", "add", "2", "step two")
        run("todo", "add", "2", "step three")


class OnePhaseByItsNumber(Base):
    def test_an_open_phase_shows_its_lines_and_names_an_item(self):
        self.two_phases()
        code, out, err = run("todo", "show", "2")
        self.assertEqual(code, 0, err)
        lines = out.rstrip("\n").split("\n")
        self.assertTrue(lines[0].startswith("- [ ] 2 Second"), lines[0])
        self.assertIn("  - [ ] 2.1 step two", out)
        self.assertNotIn("1 First", out)
        self.assertTrue(lines[-1].startswith("one item's card: el todo show 2.1"), lines[-1])

    def test_phase_show_is_the_same(self):
        self.two_phases()
        self.assertEqual(run("phase", "show", "2")[1], run("todo", "show", "2")[1])

    def test_a_closed_phase_shows_its_file(self):
        self.two_phases()
        code, out, err = run("todo", "show", "1")
        self.assertEqual(code, 0, err)
        self.assertIn("— phases/1-first.md —", out)
        self.assertIn("# Phase 1 — First", out)
        self.assertIn("this phase is history", out.rstrip("\n").split("\n")[-1])

    def test_an_item_of_a_closed_phase_is_shown_as_history(self):
        """The live map, 2026-10-08: `todo show 1.1` in a finished child met «the items of a closed phase are history»."""
        self.two_phases()
        code, out, err = run("todo", "show", "1.1")
        self.assertEqual(code, 0, err)
        self.assertIn("phase 1 First (closed — history, kept in phases/1-first.md)", out)
        self.assertIn("step one", out)
        self.assertIn("the whole phase: el todo show 1", out.rstrip("\n").split("\n")[-1])

    def test_writing_to_a_closed_items_is_still_refused(self):
        self.two_phases()
        code, _, err = run("todo", "why", "1.1", "because")
        self.assertEqual(code, 4)
        self.assertIn("history", err)

    def test_a_missing_phase_names_the_ones_there_are(self):
        self.two_phases()
        code, _, err = run("todo", "show", "7")
        self.assertEqual(code, 4)
        self.assertIn("no phase 7 in TODO.md (phases: 1, 2)", err)

    def test_no_phase_yet_names_the_first_open(self):
        code, _, err = run("phase", "show", "1")
        self.assertEqual(code, 4)
        self.assertIn('el phase open 1 "Name"', err)

    def test_an_item_card_is_still_an_item_card(self):
        self.two_phases()
        code, out, err = run("todo", "show", "2.2")
        self.assertEqual(code, 0, err)
        self.assertIn("step three", out)

    def test_a_bare_number_elsewhere_names_the_phase_door(self):
        self.two_phases()
        code, _, err = run("todo", "why", "2", "because")
        self.assertEqual(code, 2)
        self.assertIn("a whole phase: el todo show N", err)


class AWaitNamesItsDoor(Base):
    """The live map, 2026-10-08: «cannot close phase 1: still waits for» and thirty case names on one line — the last
    line a `tail -1` reader keeps named no command."""

    def test_open_children_are_counted_and_the_close_door_named(self):
        run("phase", "open", "1", "Structure", "--goal", "one research, one case")
        for k in range(7):
            run("--case", "probe", "spawn", f"child {k}", "--goal", f"research {k}")
        code, _, err = run("--case", "probe", "phase", "close", "1", "s", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        line = next(ln for ln in err.split("\n") if "still waits for" in ln)
        self.assertIn("still waits for 7 nested case(s)", line)
        self.assertIn("+2 more", line)
        self.assertIn('done "what came out" · where each stands: el case list', line)


class AnExtraFlagNamesTheCommandCalled(Base):
    """The live map, 2026-10-08: `el --case <child> done "…" --reflect x --align x` — the flags of a phase close on a case
    close — answered with the generic start of el, not with what `done` takes."""

    def test_the_examples_and_the_dose_are_dones(self):
        code, _, err = run("--case", "probe", "done", "all written", "--reflect", "x", "--align", "y")
        self.assertEqual(code, 2)
        self.assertIn("el done: unrecognized arguments: --reflect x --align y", err)
        self.assertIn('el done "database connected and validated"', err)
        self.assertIn("recovery: el help cases · el done -h", err)


class AMeasureIsNotMoney(Base):
    """The live map, 2026-10-08: an acceptance quoting a digest — «WER .0878» — met «an orphan decimal like `.72` —
    a `$…` swallowed by the shell?». Cents are what a swallowed `$150.72` leaves; four digits are a measure."""

    def test_a_ratio_with_four_digits_is_written(self):
        run("phase", "open", "1", "First", "--goal", "g")
        code, _, err = run("todo", "add", "1", "WER .0878 on the gold set holds")
        self.assertEqual(code, 0, err)

    def test_cents_are_still_a_trace(self):
        run("phase", "open", "1", "First", "--goal", "g")
        code, _, err = run("todo", "add", "1", "pay .72 to the vendor")
        self.assertEqual(code, 2)
        self.assertIn("orphan decimal", err)




class ARelinkReachesTheProject(Base):
    """The polygon, 2026-10-08: a journal link to `../../.howto/x.md` went dead (the recipe was not in the copy); two
    agents tried `el relink .howto/x.md none` and `el relink ../../.howto/x.md none` and met «inside the case folder only».
    Order named the link and its door; the door must take a file of the project."""

    def setUp(self):
        super().setUp()
        self.case = next(Path(self.tmp.name, ".cases").glob("*-probe"))
        run("log", "DECISION", "the recipe [collect](../../.howto/collect.md) holds the steps")

    def test_retired_in_the_form_order_prints(self):
        code, out, err = run("relink", "../../.howto/collect.md", "none")
        self.assertEqual(code, 0, err)
        self.assertIn("retired: ../../.howto/collect.md — 1 link(s)", out)
        self.assertIn("`[collect](../../.howto/collect.md)`", (self.case / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_retired_in_the_form_from_the_project_root(self):
        code, out, err = run("relink", ".howto/collect.md", "none")
        self.assertEqual(code, 0, err)
        self.assertIn("1 link(s)", out)

    def test_relinked_to_the_recipe_where_it_is_now(self):
        (Path(self.tmp.name) / ".howto").mkdir()
        (Path(self.tmp.name) / ".howto" / "collect-output.md").write_text("when: collect\n", encoding="utf-8")
        code, out, err = run("relink", "../../.howto/collect.md", ".howto/collect-output.md")
        self.assertEqual(code, 0, err)
        self.assertIn("(../../.howto/collect-output.md)", (self.case / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_outside_the_project_is_refused(self):
        code, _, err = run("relink", "../../../elsewhere.md", "none")
        self.assertEqual(code, 2)
        self.assertIn("leads outside the project", err)


if __name__ == "__main__":
    unittest.main()
