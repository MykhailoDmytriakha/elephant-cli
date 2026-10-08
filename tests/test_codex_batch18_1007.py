"""A Codex peer review of batches 17–18 before commit (2026-10-07): twelve findings, each a form of failure kept here."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

EL = str(Path(__file__).resolve().parent.parent / "bin" / "el")
README = """# probe

## Context
{context}

## State
- next: go

## Decisions

## Problems

## Links
"""


class Base(unittest.TestCase):
    session = "codex18"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_RECITE", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION=self.session, EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          EL_RECITE="0")
        os.environ.pop("EL_TWO_HANDS", None)

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def write_readme(self, context):
        src = Path(self.tmp.name) / "readme-in.md"
        src.write_text(README.format(context=context), encoding="utf-8")
        return run("readme", "--file", str(src))

    def readme(self):
        return next(Path(self.tmp.name, ".cases").glob("*/README.md"))


class TheRuleIsKept(Base):
    def setUp(self):
        super().setUp()
        run("case", "new", "probe", "--goal", "g")

    def test_an_old_readme_with_an_unrelated_error_still_gives_its_rule(self):
        f = self.readme()
        f.write_text("stray words before the sections\n" + f.read_text(encoding="utf-8"), encoding="utf-8")
        code, out, err = self.write_readme("A new context.")
        self.assertIn("- rule: two hands", self.readme().read_text(encoding="utf-8"), out + err)

    def test_the_drop_number_points_at_the_rule_not_a_bullet_that_mentions_it(self):
        code, out, err = self.write_readme("A new context.\n- goal: two hands are better than one")
        self.assertEqual(code, 0, err)
        self.assertIn("el readme drop context 2", out, "bullet 1 is the agent's goal line; the rule is bullet 2")

    def test_a_rule_kept_in_capitals_is_still_enforced(self):
        self.write_readme("A new context.\n- rule: TWO HANDS — as the owner said")
        self.assertEqual(self.readme().read_text(encoding="utf-8").count("rule:"), 1, "kept as written, not doubled")
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")
        run("todo", "add", "1", "a step", "--expect", "[run: probe → ok]")
        run("todo", "done", "1.1", "run:probe → ok", "it answers")
        code, _, err = run("phase", "close", "1", "s", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("not accepted", err)


class TheCountHolds(Base):
    def test_parallel_calls_of_one_session_are_all_counted(self):
        env = dict(os.environ, EL_RECITE="1")
        procs = [subprocess.Popen([EL, "help", "start"], env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL) for _ in range(24)]
        for p in procs:
            p.wait()
        from elephant import store
        self.assertEqual(store.count_call()[0], 25, "24 parallel calls and this one")

    def test_a_refused_parse_counts_as_a_call(self):
        from elephant import store
        run("todo")  # bare: a usage refusal
        run("todo")
        self.assertEqual(store.count_call()[0], 3)


class RecitationKeepsItsPlace(Base):
    def setUp(self):
        super().setUp()
        os.environ["EL_RECITE"] = "1"
        run("case", "new", "probe", "--goal", "PARENT GOAL")                        # 1
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")  # 2

    def test_a_spawn_on_the_tenth_call_does_not_recite_the_parent(self):
        for _ in range(7):
            run("todo", "show", "1")                                             # 3..9
        code, out, err = run("spawn", "child", "--goal", "CHILD GOAL")          # 10
        self.assertEqual(code, 0, err)
        self.assertNotIn("PARENT GOAL", out)

    def test_the_command_keeps_its_last_line(self):
        for _ in range(7):
            run("todo", "show", "1")                                             # 3..9
        code, out, err = self.write_readme("A new context without the rule.")   # 10
        self.assertEqual(code, 0, err)
        self.assertIn("recite (every 10 el calls)", out)
        self.assertIn("kept in Context: - rule: two hands", out.rstrip("\n").split("\n")[-1])


class AFreshSessionFollowsWrites(Base):
    def test_a_look_that_refreshes_does_not_move_the_next_sessions_start(self):
        run("case", "new", "alpha", "--goal", "a")
        run("case", "new", "beta", "--goal", "b")
        run("--case", "beta", "log", "DECISION", "the last write aims at beta")
        (next(Path(self.tmp.name, ".cases").glob("*-alpha")) / "notes.md").write_text("# n\n\nsummary: a note\n")
        run("--case", "alpha", "order")  # a look; Links of alpha redraw on the way
        os.environ["EL_SESSION"] = "codex18-fresh"
        self.assertTrue(run()[1].split("\n")[0].endswith("beta"))


class RootModeFoldsToo(Base):
    def test_the_project_case_carries_its_children(self):
        run("case", "new", "--root", "app", "--goal", "the app")
        run("phase", "open", "1", "Work", "--goal", "w")
        project = Path(self.tmp.name).name  # the project case is named by its folder
        for name in ("one", "two", "three"):
            code, _, err = run("--case", project, "spawn", name, "--goal", name)
            self.assertEqual(code, 0, err)
        run("case", "use", "one")
        line = next(ln for ln in run()[1].split("\n") if ln.startswith("other open cases:"))
        self.assertIn("(+2 open nested", line)
        self.assertNotIn("three", line)


class ARefusalWithoutADoorEndsWithTheLegend(unittest.TestCase):
    def test_no_command_at_the_end_puts_the_legend_last(self):
        from elephant.main import _refusal_lines
        from elephant.store import StoreError
        lines = _refusal_lines(StoreError("README.md: refused:\n  F1 · sections missing\n", 3), [])
        self.assertTrue(lines[-1].startswith("  exit 3 = "), lines)
        self.assertNotEqual(lines[-1].strip(), "")
        self.assertTrue(lines[0].startswith("el: ERROR [exit 3] README.md: refused:"))

    def test_a_command_at_the_end_stays_the_door(self):
        from elephant.main import _refusal_lines
        from elephant.store import StoreError
        lines = _refusal_lines(StoreError("cannot close phase 1:\n  open items 1.2 → el todo done 1.2 run:… \"…\"", 4), [])
        self.assertIn("el todo done 1.2", lines[-1])


if __name__ == "__main__":
    unittest.main()
