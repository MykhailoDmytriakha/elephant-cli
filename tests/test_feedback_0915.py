"""Four reports of 2026-09-15 16:44 from a live case (el 1.8.0), carried over by hand:
(1) `el case list` drew 28 `BROKEN: README unparsable` lines for folders from before el and pushed
    the live cases off the screen — a legacy case (never stamped, outside the grammar) is not a
    broken one (stamped, then hand-edited): each is named by its own name and fix, and legacy
    cases fold into one count line unless `--all`;
(2) `el done` with a 140-char summary wrote a 192-char `- closed:` line and warned about it — a line
    el writes obeys el's own pointer limit, like `last:` (shortened, the whole text in the journal);
    found on the way: `el readme set closed "…"` closed a case past every gate — refused now;
(3) F13: a one-action item with an endpoint path and a flag reached 103 visible chars and the ready
    suggestion cut «in pod logs» to «in pod» — the owner's word: the limit stands, the item is rephrased
    (verb first, the path stays, the filler goes); the refusal now teaches that instead of truncating;
(4) `run:"cmd -> out"` was said to be refused — it was accepted since 1.5.0; typed WITHOUT quotes the
    shell took `>` as a redirection and el saw `cmd -`; the refusal named only → and now names both
    arrows and the shell trace."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, order
from tests.test_commands import run

LEGACY_README = "# Old matter\n\nSome notes from before el, no sections, no stamp.\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.root = Path(self.tmp.name) / ".cases"

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def case(self, part: str) -> Path:
        return next(p for p in self.root.iterdir() if p.is_dir() and part in p.name)

    def legacy(self, name: str) -> Path:
        d = self.root / name
        d.mkdir(parents=True)
        (d / "README.md").write_text(LEGACY_README, encoding="utf-8")
        (d / "TODO.md").write_text("# TODO\n\n- [ ] something\n", encoding="utf-8")
        (d / "JOURNAL.md").write_text("# JOURNAL\n\n- 2026-02-13 · note\n", encoding="utf-8")
        return d


class LegacyCasesFold(Base):
    def test_legacy_is_not_broken_and_folds_into_one_line(self):
        for i in range(28):
            self.legacy(f"2026-02-{(i % 28) + 1:02d}-old-matter-{i}")
        run("case", "new", "live one", "--goal", "g")
        run("case", "new", "live two", "--goal", "g")
        code, out, err = run("case", "list")
        self.assertEqual(code, 0, err)
        self.assertNotIn("BROKEN", out, "a case from before el is legacy, not broken")
        self.assertEqual(out.count("old-matter"), 0, "28 legacy folders are not 28 lines")
        self.assertIn("legacy (before el): 28 case(s) el cannot read until migrated", out)
        self.assertIn("el case list --all names them · el --case <name> migrate", out)
        self.assertIn("live-one", out)
        self.assertIn("live-two", out)
        self.assertIn("cases: 30 · 2 open · 0 closed · 28 legacy", out)
        self.assertLess(len(out.splitlines()), 8, "the screen holds the live cases, not the archive")
        code, out, _ = run("case", "list", "--all")
        self.assertEqual(out.count("legacy: 2026-02-"), 28, "--all names every legacy case")
        self.assertIn("→ el --case 2026-02-01-old-matter-0 migrate", out)

    def test_legacy_child_holds_the_parent_with_its_own_name_and_fix(self):
        run("case", "new", "parent", "--goal", "g")
        parent = self.case("parent")
        kid = parent / "2026-02-13-old-kid"
        kid.mkdir()
        (kid / "README.md").write_text(LEGACY_README, encoding="utf-8")
        self.assertEqual(order.child_status(kid)[0], "legacy")
        code, out, err = run("status")
        self.assertEqual(code, 0, err)
        self.assertIn(f"nested case 2026-02-13-old-kid: from before el (never stamped, outside the grammar) — it holds this case open (F18) → el --case 2026-02-13-old-kid migrate", out)
        readme = (parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("legacy (before el): not read until migrated, holds this case open → el --case 2026-02-13-old-kid migrate", readme)
        self.assertNotIn("BROKEN", readme)
        code, _, err = run("done", "finished")
        self.assertEqual(code, 4)
        self.assertIn("2026-02-13-old-kid (legacy)", err)

    def test_stamped_then_broken_readme_is_still_broken(self):
        run("case", "new", "parent", "--goal", "g")
        parent = self.case("parent")
        kid = parent / "2026-02-13-edited-kid"
        kid.mkdir()
        (kid / "README.md").write_text("# Kid\n\nno sections\n\nstamp: 000000000000\n", encoding="utf-8")
        self.assertEqual(order.child_status(kid)[0], "broken", "a stamp that does not match is a hand edit, not a legacy case")


class ClosedLineIsEls(Base):
    LONG = ("All phases complete: forceDebugLogs successfully disabled across DEV, SIT, UAT, LNP, STG, and PROD; "
            "Redis instances restarted; log hygiene restored; all services healthy")

    def close_case(self, summary: str):
        run("case", "new", "t", "--goal", "g")
        run("phase", "open", "1", "Phase", "--goal", "g")
        run("todo", "add", "1", "task")
        run("todo", "done", "1.1", "owner", "done")
        run("log", "DECISION", "reflect: r")
        run("log", "DECISION", "align: a")
        run("phase", "close", "1", "Phase done")
        return run("done", summary)

    def test_long_summary_is_shortened_and_no_warning_about_els_own_line(self):
        code, out, err = self.close_case(self.LONG)
        self.assertEqual(code, 0, err)
        self.assertNotIn("F2", err, "el does not warn about a line it wrote itself")
        self.assertIn("closed: shortened to the pointer limit (150 chars, F2) — the whole summary is in the journal (PHASE)", out)
        readme = (self.case("t") / "README.md").read_text(encoding="utf-8")
        line = next(ln for ln in readme.splitlines() if ln.startswith("- closed: "))
        self.assertLessEqual(grammar.visible_len(line), grammar.README_POINTER_CHARS)
        self.assertTrue(line.endswith("…"))
        journal = (self.case("t") / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn("all services healthy", journal, "the whole summary lives in the journal")
        self.assertEqual(order.child_status(self.case("t"))[0], "closed")

    def test_short_summary_is_kept_whole_and_silent(self):
        code, out, err = self.close_case("finished")
        self.assertEqual(code, 0, err)
        self.assertNotIn("shortened", out)
        self.assertIn("- closed: 20", (self.case("t") / "README.md").read_text(encoding="utf-8"))

    def test_readme_set_closed_is_refused(self):
        run("case", "new", "t", "--goal", "g")
        code, _, err = run("readme", "set", "closed", "2026-09-15 · done by hand")
        self.assertEqual(code, 2)
        self.assertIn("written by `el done", err)
        self.assertIn("not by a State line", err)
        self.assertNotIn("- closed:", (self.case("t") / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(order.child_status(self.case("t"))[0], "open")


class ItemsAreRephrasedNotRecounted(Base):
    """The report asked for 120–140 or paths left out of the count. The owner's word (2026-09-15): the
    limit is fine, the item is rephrased — «Trigger /v3/…, confirm FLAG=false in pod logs» is 76 chars and
    keeps the checkable outcome. So: strict count, and the refusal teaches rephrasing, not truncation."""
    ITEM = "Verify logs: trigger endpoint (/v3/app/test/log-generator) and confirm forceDebugLogs=false in pod logs"

    def setUp(self):
        super().setUp()
        run("case", "new", "t", "--goal", "g")
        run("phase", "open", "1", "Phase", "--goal", "g")

    def test_visible_len_exempts_links_only(self):
        self.assertEqual(grammar.visible_len(self.ITEM), 103)
        marked = "Verify logs: trigger endpoint `/v3/app/test/log-generator` and confirm `forceDebugLogs=false` in pod logs"
        self.assertEqual(grammar.visible_len(marked), len(marked), "backticks change nothing: no token exemption")
        self.assertEqual(grammar.visible_len("see [notes](docs/very/long/path/notes.md) now"), len("see notes now"))

    def test_refusal_suggests_rephrasing_and_the_rephrased_item_fits(self):
        code, _, err = run("todo", "add", "1", self.ITEM)
        self.assertEqual(code, 3)
        self.assertIn("103 visible chars, limit 100 (F13)", err)
        self.assertIn("rephrase, do not truncate: verb first, the path or flag stays, the filler goes", err)
        code, out, err = run("todo", "add", "1", "Trigger /v3/app/test/log-generator, confirm forceDebugLogs=false in pod logs")
        self.assertEqual(code, 0, err)
        self.assertIn("in pod logs", out, "the checkable outcome survives the rephrasing")
        code, _, err = run("todo", "edit", "1.1", self.ITEM)
        self.assertEqual(code, 3)
        self.assertIn("rephrase, do not truncate", err)


class RunArrow(Base):
    def setUp(self):
        super().setUp()
        run("case", "new", "t", "--goal", "g")
        run("phase", "open", "1", "Phase", "--goal", "g")
        run("todo", "add", "1", "task")

    def test_ascii_arrow_quoted_is_accepted_and_normalised(self):
        code, out, err = run("todo", "done", "1.1", "run:curl localhost/health -> UP", "checked health")
        self.assertEqual(code, 0, err)
        self.assertIn("      - run: curl localhost/health → UP", (self.case("t") / "TODO.md").read_text(encoding="utf-8"))

    def test_refusal_names_both_arrows_and_the_shell_trace(self):
        code, _, err = run("todo", "done", "1.1", "run:curl localhost/health -", "UP")
        self.assertEqual(code, 2)
        self.assertIn("joined by → or ->", err)
        self.assertIn("the value ends with `-`: a `->` cut by the shell?", err)
        self.assertIn("quote the value", err)
        code, _, err = run("todo", "done", "1.1", "run:make test", "x")
        self.assertEqual(code, 2)
        self.assertIn("joined by → or ->", err)
        self.assertNotIn("cut by the shell", err, "no trailing `-`, no shell story")


if __name__ == "__main__":
    unittest.main()
