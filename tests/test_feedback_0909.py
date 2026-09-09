"""Feedback of 2026-09-09 (a rollout case through five environments): a tick taken back with
`todo reopen`, the TODO line limit raised to 200, and `phase open` after a cancelled phase."""
import os
import tempfile
import unittest
from pathlib import Path

from mike import grammar
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("MIKE_CASE", None)
        run("case", "new", "demo case", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class Reopen(Base):
    def test_a_tick_is_taken_back_with_a_reason(self):
        run("todo", "add", "1", "migrate UAT")
        run("todo", "add", "1", "smoke UAT — after: 1.1")
        run("todo", "done", "1.1", "migrated, 12 tables")
        self.assertIn("- [x] 1.1 migrate UAT", self.read("TODO.md"))
        code, out, err = run("todo", "reopen", "1.1")
        self.assertEqual(code, 2)
        self.assertIn("reopen needs the reason", err)
        code, out, err = run("todo", "reopen", "1.1", "the databases drifted")
        self.assertEqual(code, 0, err)
        self.assertIn("reopened: 1.1 migrate UAT", out)
        self.assertIn("- [ ] 1.1 migrate UAT", self.read("TODO.md"))
        j = self.read("JOURNAL.md")
        self.assertIn("DECISION · 1.1 возвращён в работу — the databases drifted", j)
        self.assertIn("RESULT · 1.1: migrated, 12 tables", j, "history stays")
        self.assertIn("nothing changed", run("todo", "reopen", "1.1", "again")[1])
        code, out, err = run()
        self.assertIn("blocked", out, "1.2 waits for 1.1 again")
        self.assertNotIn("bypassing mike", err)
        self.assertEqual(run("check")[0], 0)


class LineLimit(Base):
    def test_a_rollout_checklist_fits_and_the_limit_still_exists(self):
        body = ["# TODO — x", ""]
        for n in range(1, 27):  # 26 phases, five of them with 17 steps: 113 lines of structure
            body.append(f"- [ ] {n} Env{n}")
            if n > 21:
                body += [f"  - [ ] {n}.{k} step {k}" for k in range(1, 18)]
        r = grammar.parse_todo("\n".join(body) + "\n")
        self.assertTrue(r.ok, r.errors)
        self.assertEqual(len(body), 113)
        body += [f"  - [ ] 26.{k} step {k}" for k in range(18, 110)]
        r = grammar.parse_todo("\n".join(body) + "\n")
        self.assertIn("F4", {e.rule for e in r.errors})
        self.assertIn("limit 200", " ".join(e.message for e in r.errors))


class OpenAfterCancelled(Base):
    def test_a_cancelled_phase_does_not_gate_the_next_one(self):
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")
        run("phase", "close", "1", "done")
        run("phase", "plan", "2", "Legacy", "--goal", "old plan")
        run("phase", "plan", "3", "UAT", "--goal", "rollout")
        code, out, err = run("phase", "open", "3")
        self.assertEqual(code, 4)
        self.assertIn("phase 2 Legacy is planned and not opened", err)
        self.assertIn("mike phase open 2", err)
        self.assertIn('mike phase cancel 2 "why"', err)
        run("phase", "cancel", "2", "not needed")
        code, out, err = run("phase", "open", "3")
        self.assertEqual(code, 0, err + out)
        self.assertIn("phase 3 UAT is open", out)
        self.assertIn("progress: 1 Work ✓ · 2 Legacy ✗ · 3 UAT ▶", self.read("README.md"))
        run("phase", "plan", "4", "Prod", "--goal", "g")
        code, out, err = run("phase", "open", "4")
        self.assertEqual(code, 4)
        self.assertIn("phase 3 UAT is still open — close it first", err)
        self.assertIn('mike phase cancel 3 "why"', err)
        self.assertEqual(run("check")[0], 0)
