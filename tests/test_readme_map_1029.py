"""The owner's word of 2026-10-29: «README must become the map of the case — where we set out from, how we went, what we
know» and «I worked only with TODO; in README I got lost, so much is written». Measured on the polygon the same evening
(H11–H11d, six live cases, cold readers of the README alone, blind scoring against an examiner's key):

1. What waits for the owner was found by 0.46–0.79 of the readers without a line for it, 0.83–0.92 with one — the agent's
   `owner:` line, which el keeps on top of State and asks for once at the end of a session (`set next`).
2. A `progress:` of 215 names filled the first screen before the reader reached anything that waits; past twelve phases
   the ended ones are counted, the living ones keep their names.
3. The path — `## Path` right after Context: the agent's strokes «**Name** — what became true», each phase standing on one
   by its own header line `path:`; el draws the count and at most four links, the phase in flight and how many closed
   phases the path holds, names in Order a closed phase that stands on no line, and asks for the line at a close. With it
   the first-screen readers scored +0.60 of 5 (interval +0.50…+0.70); with every range of a 215-phase case drawn, the
   strokes took the screen (1.80 against 2.25)."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, store
from tests.test_commands import run

ENVS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_THREAD_ID", "COPILOT_AGENT",
        "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "EL_MODEL", "EL_SESSION", "EL_HANDS_DIR", "EL_HINTS", "EL_TWO_HANDS",
        "EL_CASE", "EL_RECITE")


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS="0", EL_RECITE="0", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          CLAUDECODE="1", EL_SESSION="map11029")
        self.ok("case", "new", "shop", "--goal", "the shop works")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def ok(self, *argv):
        code, out, err = run(*argv)
        self.assertEqual(code, 0, f"{argv}: {out}{err}")
        return out, err

    def case(self) -> Path:
        return next(Path(self.tmp.name, ".cases").glob("*-shop"))

    def read(self, name: str) -> str:
        return (self.case() / name).read_text(encoding="utf-8")

    def state(self):
        return [ln for ln in self.read("README.md").split("## State", 1)[1].split("## ", 1)[0].split("\n") if ln.startswith("- ")]

    def history(self, closed: int):
        """`closed` phases closed — written as el writes them, without 4×closed commands."""
        ph = self.case() / "phases"
        ph.mkdir(exist_ok=True)
        lines = ["# TODO — shop", ""]
        for n in range(1, closed + 1):
            (ph / f"{n}-step.md").write_text(f"# Phase {n} — Step\ngoal: step {n}\nresult: done {n}\n", encoding="utf-8")
            lines.append(f"- [x] {n} Step — done {n} · acceptance: 1 of 1 done accepted — the owner's word 1 · 2026-10-27 · "
                         f"[phases/{n}-step.md](phases/{n}-step.md)")
        store.write(self.case(), "TODO.md", "\n".join(lines) + "\n")
        for argv in (("RESULT", f"done {closed}"), ("DECISION", "reflect: r"), ("DECISION", "align: a")):
            self.ok("log", "--phase", str(closed), *argv)


class ProgressCount(Base):
    def test_past_twelve_phases_the_ended_are_counted_and_the_living_named(self):
        self.history(14)
        self.ok("phase", "open", "15", "Work", "--goal", "the work is done")
        self.ok("phase", "plan", "16", "Later work", "--goal", "more")
        progress = next(ln for ln in self.state() if ln.startswith("- progress:"))
        self.assertEqual(progress, "- progress: 14 closed ✓ · 15 Work ▶ · 16 Later work")

    def test_twelve_phases_keep_their_names(self):
        self.history(12)
        self.ok("readme", "touch")
        progress = next(ln for ln in self.state() if ln.startswith("- progress:"))
        self.assertTrue(progress.startswith("- progress: 1 Step ✓ · 2 Step ✓"), progress)
        self.assertIn("12 Step ✓", progress)


class OwnerLine(Base):
    def test_the_owner_line_stands_under_opened_wherever_it_was_written(self):
        self.ok("readme", "set", "next", "open the first phase")
        self.ok("readme", "set", "owner", "decide whether the shop opens on Monday")
        lines = self.state()
        self.assertTrue(lines[0].startswith("- opened: "), lines)
        self.assertEqual(lines[1], "- owner: decide whether the shop opens on Monday")
        self.ok("readme", "set", "next", "price the goods")
        self.assertEqual(self.state()[1], "- owner: decide whether the shop opens on Monday", "it keeps its place")

    def test_set_next_asks_once_for_what_waits_for_the_owner(self):
        out, _ = self.ok("readme", "set", "next", "open the first phase")
        self.assertIn("what waits for the owner", out)
        self.assertIn('el readme set owner "…"', out)
        self.ok("readme", "set", "owner", "nothing")
        out, _ = self.ok("readme", "set", "next", "price the goods")
        self.assertNotIn("what waits for the owner", out)


class PathLines(Base):
    def path(self):
        return self.read("README.md").split("## Path\n", 1)[1].split("\n## ", 1)[0].strip().split("\n")

    def test_a_line_of_the_path_draws_its_count_and_links_and_order_names_the_rest(self):
        self.history(5)
        out, _ = self.ok("readme", "add", "path", "Основа — магазин открыт и торгует", "--phases", "1-3")
        self.assertIn("on the path «Основа»: phase(s) 1, 2, 3", out)
        self.assertEqual(self.path(), ["- **Основа** — магазин открыт и торгует · 3 ✓ · [1–3](phases/1-step.md)",
                                       "- on the path: 3 of 5 closed phases"])
        readme = self.read("README.md")
        self.assertLess(readme.index("## Path"), readme.index("## State"), "the path stands right after Context")
        self.assertEqual((self.case() / "phases" / "2-step.md").read_text(encoding="utf-8").split("\n")[3], "path: Основа")
        out, _ = self.ok("order")
        self.assertIn("2 closed phase(s) on no line of the path — 4-5 → el readme edit path K --phases 4-5", out)
        self.ok("readme", "edit", "path", "1", "--phases", "4,5")
        self.assertEqual(self.path()[-1], "- on the path: 5 of 5 closed phases")
        out, _ = self.ok("order")
        self.assertNotIn("on no line of the path", out)

    def test_a_stroke_of_many_phases_draws_four_links_at_most(self):
        self.history(40)
        self.ok("readme", "add", "path", "Шаги — каждый шаг сделан", "--phases", ",".join(str(n) for n in range(1, 41, 2)))
        line = self.path()[0]
        self.assertTrue(line.startswith("- **Шаги** — каждый шаг сделан · 20 ✓ · [1](phases/1-step.md) · … · "), line)
        self.assertEqual(line.count("](phases/"), 3)
        self.assertTrue(line.endswith("[37](phases/37-step.md) · [39](phases/39-step.md)"), line)

    def test_a_close_puts_the_phase_on_its_line_and_a_close_without_one_asks(self):
        self.history(3)
        self.ok("readme", "add", "path", "Основа — магазин открыт", "--phases", "1-3")
        self.ok("phase", "open", "4", "Prices", "--goal", "the goods are priced")
        self.ok("todo", "add", "4", "price the goods")
        self.ok("todo", "done", "4.1", "run:make prices → 12 OK", "the goods are priced")
        self.assertIn("- ▶ now: [4 Prices](phases/4-prices.md)", self.path())
        out, _ = self.ok("phase", "close", "4", "priced", "--reflect", "r", "--align", "a", "--path", "1")
        self.assertIn("on the path: «Основа»", out)
        self.assertEqual(self.path()[0], "- **Основа** — магазин открыт · 4 ✓ · [1–4](phases/1-step.md)")
        pf = (self.case() / "phases" / "4-prices.md").read_text(encoding="utf-8").split("\n")
        self.assertEqual(pf[3], "path: Основа", "the header line stays under result:")
        self.assertIn("## Digest", pf)
        self.ok("phase", "open", "5", "Shelves", "--goal", "the shelves are full")
        self.ok("todo", "add", "5", "fill the shelves")
        self.ok("todo", "done", "5.1", "run:make shelves → OK", "the shelves are full")
        out, _ = self.ok("phase", "close", "5", "filled", "--reflect", "r", "--align", "a")
        self.assertIn("on the path? el readme edit path K --phases 5 — 1 Основа", out)

    def test_a_closed_phase_restated_with_a_path_line_is_counted_at_once(self):
        self.history(3)
        self.ok("readme", "add", "path", "Основа — магазин открыт", "--phases", "1-2")
        self.ok("phase", "close", "3", "done 3", "--path", "Основа")
        self.assertEqual(self.path()[0], "- **Основа** — магазин открыт · 3 ✓ · [1–3](phases/1-step.md)")

    def test_a_cancelled_phase_on_a_line_is_counted_apart(self):
        self.history(2)
        self.ok("phase", "open", "3", "Detour", "--goal", "a side road")
        self.ok("readme", "add", "path", "Основа — магазин открыт", "--phases", "1-3")
        self.ok("phase", "cancel", "3", "the road was closed")
        self.assertEqual(self.path()[0], "- **Основа** — магазин открыт · 2 ✓ · 1 ✗ · [1–3](phases/1-step.md)")
        self.assertEqual(self.path()[-1], "- on the path: 2 of 2 closed phases")

    def test_a_new_name_takes_its_phases_along_and_a_dropped_line_leaves_them_named(self):
        self.history(4)
        self.ok("readme", "add", "path", "Основа — магазин открыт", "--phases", "1-2")
        self.ok("readme", "add", "path", "Товар — полки полны", "--phases", "3-4")
        out, _ = self.ok("readme", "edit", "path", "1", "Начало — магазин открыт в срок")
        self.assertIn("its phases follow the name: 1-2", out)
        self.assertEqual(self.path()[0], "- **Начало** — магазин открыт в срок · 2 ✓ · [1–2](phases/1-step.md)")
        out, _ = self.ok("readme", "drop", "path", "2")
        self.assertIn("phases 3-4 stood on it and stand on no line now", out)
        self.assertEqual(self.path()[-1], "- on the path: 2 of 4 closed phases")
        self.ok("readme", "drop", "path", "1")
        self.assertNotIn("## Path", self.read("README.md"), "the section goes with its last line")

    def test_doors_say_what_they_take(self):
        self.history(2)
        code, _, err = run("readme", "add", "path", "магазин открыт")
        self.assertEqual(code, 2, err)
        self.assertIn('el readme add path "Name — what became true"', err)
        code, _, err = run("readme", "add", "decisions", "x", "--phases", "1")
        self.assertEqual(code, 2, err)
        self.ok("phase", "plan", "3", "Later", "--goal", "later")
        code, _, err = run("readme", "add", "path", "Основа — x", "--phases", "3")
        self.assertEqual(code, 4, err)
        self.assertIn("phase 3 Later is planned", err)
        code, _, err = run("phase", "close", "2", "done 2", "--path", "Нет")
        self.assertEqual(code, 4, err)
        self.assertIn("no path yet", err)

    def test_a_readme_without_a_path_reads_and_writes_as_before(self):
        self.history(2)
        before = [ln for ln in self.read("README.md").split("\n") if ln.startswith("## ")]
        self.ok("readme", "set", "next", "go on")
        self.assertEqual([ln for ln in self.read("README.md").split("\n") if ln.startswith("## ")], before)
        self.assertNotIn("## Path", self.read("README.md"))
        body = "# T\n\n## Context\ng\n\n## State\n- progress: x\n\n## Path\n- **A** — b\n\n## Decisions\n\n## Problems\n\n## Links\n"
        self.assertTrue(any(f.rule == "F1" for f in grammar.parse_readme(body).errors), "the path stands right after Context")


class CodexInspection(Base):
    """The inspection of the partia by a second engine (Codex, 2026-10-29): six holes, each reproduced on 3.9 and 3.14."""
    def path(self):
        return self.read("README.md").split("## Path\n", 1)[1].split("\n## ", 1)[0].strip().split("\n")

    def test_words_ending_like_els_count_are_refused_not_eaten(self):
        code, _, err = run("readme", "add", "path", "Checks — suite passed · 7 ✓")
        self.assertEqual(code, 2, err)
        self.assertIn("ends the way el's count does", err)
        self.assertNotIn("## Path", self.read("README.md"))

    def test_a_name_with_no_letters_is_a_usage_refusal_not_a_crash(self):
        code, _, err = run("readme", "add", "path", "*** — claim")
        self.assertEqual(code, 2, err)
        self.assertIn('el readme add path "Name — what became true"', err)

    def test_a_phase_file_moved_away_is_named_and_its_tail_drawn_once(self):
        self.history(2)
        self.ok("readme", "add", "path", "Base — built", "--phases", "1-2")
        self.ok("mv", "phases/1-step.md", "docs/1-step.md")
        self.ok("readme", "touch")
        self.assertEqual(self.path()[0], "- **Base** — built · 1 ✓ · [2](phases/2-step.md)", "one tail, not two")
        out, _ = self.ok("order")
        self.assertIn("1 closed phase(s) on no line of the path — 1 →", out)
        code, _, err = run("readme", "edit", "path", "1", "--phases", "1")
        self.assertEqual(code, 4, err)
        self.assertIn("el mv <where it is> phases/1-step.md", err)
        self.assertNotIn("is planned", err)

    def test_a_cancelled_plan_on_the_path_comes_back_by_its_number(self):
        self.ok("phase", "plan", "1", "Later", "--goal", "later work")
        self.ok("phase", "cancel", "1", "not yet needed")
        self.ok("readme", "add", "path", "Options — the choices were checked", "--phases", "1")
        self.ok("phase", "plan", "1", "Later", "--goal", "needed now")

    def test_two_lines_of_one_name_are_refused_by_every_door(self):
        self.history(2)
        self.ok("readme", "add", "path", "Base — built", "--phases", "1-2")
        copy = Path(self.tmp.name) / "copy.md"
        body = self.read("README.md").split("\nstamp:")[0].replace("- on the path:", "- **base** — second claim\n- on the path:")
        copy.write_text(body, encoding="utf-8")
        code, _, err = run("readme", "--file", str(copy))
        self.assertNotEqual(code, 0, err)
        self.assertIn("appears twice", err)
        self.assertEqual(self.read("README.md").count("**Base**"), 1)

    def test_dropping_the_last_line_offers_a_new_line_not_an_edit_of_none(self):
        self.history(2)
        self.ok("readme", "add", "path", "Base — built", "--phases", "1-2")
        out, _ = self.ok("readme", "drop", "path", "1")
        self.assertIn('el readme add path "Name — what became true" --phases 1-2', out)
        self.assertNotIn("el readme edit path K", out)


if __name__ == "__main__":
    unittest.main()
