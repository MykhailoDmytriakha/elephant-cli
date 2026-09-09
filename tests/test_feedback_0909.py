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


class ClosePlanned(Base):
    """Second report of the same day: items of a planned phase were worked in TODO (the gate had
    refused `open`), then `phase close` died with «file is missing (F12)» and the agent wrote the file
    by hand. The refusal names the cause and the path: open first, then close."""

    def test_a_never_opened_phase_says_open_first(self):
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")
        run("phase", "close", "1", "done")
        run("phase", "plan", "2", "UAT", "--goal", "rollout")
        run("todo", "add", "2", "UAT: [DB] migrate -> expect 12 tables")
        run("todo", "done", "2.1", "12 tables")
        code, out, err = run("phase", "close", "2", "rolled out")
        self.assertEqual(code, 4)
        self.assertIn("phase 2 UAT was planned and never opened", err)
        self.assertIn("mike phase open 2", err)
        self.assertNotIn("F12", err)
        code, out, err = run("phase", "open", "2")
        self.assertEqual(code, 0, err)
        run("log", "RESULT", "rolled out")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")
        code, out, err = run("phase", "close", "2", "rolled out")
        self.assertEqual(code, 0, err)
        self.assertEqual(run("check")[0], 0)


class ItemLength(Base):
    def test_a_rollout_step_with_its_expected_result_fits(self):
        step = "PROD-ONPREM: [Migration] run flyway migrate on prod-onprem-db -> expect 12 tables, 0 errors"
        self.assertGreater(len(step), 80)
        code, out, err = run("todo", "add", "1", step)
        self.assertEqual(code, 0, err)
        code, out, err = run("todo", "add", "1", step + " and then some more words that push it over")
        self.assertEqual(code, 3)
        self.assertIn("limit 100", err)


class Ranges(Base):
    """Third report of the day: a Pre-flight block rolled back item by item — six identical calls."""

    def setUp(self):
        super().setUp()
        for k in range(1, 7):
            run("todo", "add", "1", f"UAT: [Pre-flight] check {k}")

    def test_done_reopen_cancel_take_a_range_or_a_list(self):
        code, out, err = run("todo", "done", "1.1-1.5", "pre-flight verified")
        self.assertEqual(code, 0, err)
        self.assertIn("done: 1.1, 1.2, 1.3, 1.4, 1.5 (5 items)", out)
        t = self.read("TODO.md")
        self.assertEqual(t.count("- [x] 1."), 5)
        self.assertIn("- [ ] 1.6", t)
        self.assertEqual(self.read("JOURNAL.md").count("RESULT · 1.1, 1.2, 1.3, 1.4, 1.5: pre-flight verified"), 1)
        code, out, err = run("todo", "reopen", "1.1-1.6", "database drift detected")
        self.assertEqual(code, 0, err)
        self.assertIn("open already, nothing changed: 1.6", out)
        self.assertIn("reopened: 1.1, 1.2, 1.3, 1.4, 1.5 (5 items)", out)
        self.assertEqual(self.read("TODO.md").count("- [x] 1."), 0)
        self.assertIn("DECISION · 1.1, 1.2, 1.3, 1.4, 1.5 возвращены в работу — database drift detected", self.read("JOURNAL.md"))
        code, out, err = run("todo", "cancel", "1.2, 1.4", "not on this env")
        self.assertEqual(code, 0, err)
        self.assertIn("phase 1 now reads", out)
        self.assertNotIn("1.2 UAT", self.read("TODO.md"))
        self.assertIn("DECISION · снято 1.2 «UAT: [Pre-flight] check 2», 1.4 «UAT: [Pre-flight] check 4» — not on this env", self.read("JOURNAL.md"))
        code, out, err = run("todo", "add", "1", "another")
        self.assertIn("added: 1.7", out, "cancelled numbers stay reserved by the journal line")
        self.assertEqual(run("todo", "done", "1.1-2.3", "x")[0], 2, "a range stays in one phase")
        self.assertEqual(run("todo", "done", "1.40-1.50", "x")[0], 4)
        self.assertEqual(run("check")[0], 0)


class ReplanAfterCancel(Base):
    def test_a_phase_cancelled_while_planned_comes_back_with_its_items(self):
        run("phase", "plan", "2", "Exhibition", "--goal", "seven days")
        run("todo", "add", "2", "book the truck — [truck](docs/truck.md)")
        run("todo", "add", "2", "print the leaflets")
        (self.case / "docs").mkdir()
        (self.case / "docs" / "truck.md").write_text("# T\nsummary: t\n", encoding="utf-8")
        run("phase", "cancel", "2", "planned for after STG")
        self.assertIn("- [x] 2 Exhibition — снято:", self.read("TODO.md"))
        code, out, err = run("phase", "plan", "2", "Exhibition")
        self.assertEqual(code, 0, err)
        self.assertIn("re-planned: phase 2 Exhibition — seven days → TODO.md (was cancelled) · items back: 2.1, 2.2", out)
        t = self.read("TODO.md")
        self.assertIn("- [ ] 2 Exhibition — seven days\n", t)
        self.assertIn("- [ ] 2.1 book the truck — [truck](docs/truck.md)", t, "links come back up to the case root")
        self.assertIn("- [ ] 2.2 print the leaflets", t)
        self.assertFalse((self.case / "phases" / "2-exhibition.md").exists(), "the born-closed file is gone")
        self.assertIn("DECISION · фаза 2 Exhibition возвращена в план (снято: planned for after STG)", self.read("JOURNAL.md"))
        self.assertIn("progress: 1 Work ▶ · 2 Exhibition", self.read("README.md"))
        self.assertEqual(run("check")[0], 0)

    def test_a_phase_that_ran_does_not_come_back(self):
        run("todo", "add", "1", "a")
        run("phase", "cancel", "1", "venue fell through")
        code, out, err = run("phase", "plan", "1", "Work", "--goal", "again")
        self.assertEqual(code, 4)
        self.assertIn("ran before it was cancelled", err)
        self.assertIn('mike phase plan 2 "Work"', err)
        self.assertTrue((self.case / "phases" / "1-work.md").exists())


class StaleLinksLine(Base):
    """A nested Links line mike drew for a file that is gone is a dead pointer in the rendered index:
    it made README violate F16 with nothing to drop it by (found twice on 2026-09-08/09)."""

    def test_a_rendered_line_for_a_gone_file_disappears_on_the_next_render(self):
        (self.case / "docs").mkdir()
        (self.case / "docs" / "a.md").write_text("# A\nsummary: a\n", encoding="utf-8")
        run("readme", "add", "links", "docs/ — документы")
        (Path(self.tmp.name) / "NOTES.md").write_text("# notes\n", encoding="utf-8")
        run("readme", "add", "links", "[outside](../../NOTES.md) — the agent's own line stays")
        self.assertIn("[a.md](docs/a.md) — a", self.read("README.md"))
        os.remove(self.case / "docs" / "a.md")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        r = self.read("README.md")
        self.assertNotIn("docs/a.md", r)
        self.assertIn("[outside](../../NOTES.md)", r)
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)


class MoveBinary(Base):
    """Feedback 2026-09-09 13:24: `mike mv X.pdf outbox/X.pdf` died with UnicodeDecodeError reading
    the pdf as UTF-8 to rewrite its own links; nothing moved, links elsewhere stayed dead."""

    def test_a_pdf_moves_as_bytes_and_links_to_it_follow(self):
        raw = b"%PDF-1.4\n\xc4\xe9\x00 binary body"
        (self.case / "docs").mkdir()
        (self.case / "docs" / "x.pdf").write_bytes(raw)
        run("readme", "add", "links", "docs/ — документы")
        run("todo", "add", "1", "sign it — [pdf](docs/x.pdf)")
        pf = self.case / "phases" / "1-work.md"
        pf.write_text(pf.read_text(encoding="utf-8") + "\nsee [the pdf](../docs/x.pdf)\n", encoding="utf-8")
        code, out, err = run("mv", "docs/x.pdf", "outbox/x.pdf")
        self.assertEqual(code, 0, err)
        self.assertIn("moved: docs/x.pdf → outbox/x.pdf · links rewritten: TODO.md (1), phases/1-work.md (1)", out)
        self.assertEqual((self.case / "outbox" / "x.pdf").read_bytes(), raw, "byte for byte")
        self.assertFalse((self.case / "docs" / "x.pdf").exists())
        self.assertIn("[pdf](outbox/x.pdf)", self.read("TODO.md"))
        self.assertIn("[the pdf](../outbox/x.pdf)", pf.read_text(encoding="utf-8"))
        self.assertNotIn("broken link", run()[1])
        code, out, err = run("check")
        self.assertEqual(code, 0, err + out)

    def test_a_markdown_file_that_is_not_utf8_moves_with_a_warning(self):
        (self.case / "docs").mkdir()
        (self.case / "docs" / "old.md").write_bytes(b"# old\nsummary: \xc4 latin-1 body\n")
        code, out, err = run("mv", "docs/old.md", "docs/archive/old.md")
        self.assertEqual(code, 0, err)
        self.assertIn("not UTF-8 text — moved as is", err)
        self.assertTrue((self.case / "docs" / "archive" / "old.md").exists())
