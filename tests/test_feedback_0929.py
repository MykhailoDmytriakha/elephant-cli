"""Two reports of 2026-09-29 (el 1.29.0).

1. `el done` in a nested case was refused with «item 1.7 text is 328 visible chars» — an item the agent never wrote: el
   appended the child's folder name to the summary at the parent, the name ate a third of the 100 chars, and the agent
   retried blind. Since 1.30.0 the parent's item is the agent's words only (the case is named by the proof line, which
   already linked to it), and the summary is checked before any write, in the agent's words, with the number.
2. Sixteen items accepted `--by owner` on one blanket word of the owner read ✓ at the phase, the case and the parent —
   the same as a re-run by a second hand. Since 1.30.0 one tally by kind rises with the work: entry, Digest, the case's
   `closed:` line and so its line at the parent; and the owner's word is recorded as the owner's words, quoted."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

CHILD = "a child with a rather long descriptive folder name"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        for k in ("EL_CASE", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_SESSION"] = "doer0001"

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    def cases(self) -> Path:
        return Path(self.tmp.name) / ".cases"

    def parent(self) -> Path:
        return next(p for p in self.cases().iterdir() if p.name.endswith("-parent"))

    def child(self) -> Path:
        return next(p for p in self.parent().iterdir() if p.is_dir() and p.name.endswith("-name"))

    def nested(self, items=1):
        """A parent waiting for a child whose one phase has `items` done items, not yet accepted."""
        run("case", "new", "parent", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")
        run("spawn", CHILD, "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")
        for k in range(1, items + 1):
            run("todo", "add", "1", f"item {k}", "--expect", "[run: t]")
            run("todo", "done", f"1.{k}", "run:true -> ok", "done")

    def close_child_phase(self):
        code, out, err = run("phase", "close", "1", "r", "--reflect", "a lesson about the work", "--align", "the next plan")
        self.assertEqual(code, 0, err)


class TheSummaryIsTheAgentsWords(Base):
    def setUp(self):
        super().setUp()
        self.nested()
        os.environ["EL_SESSION"] = "second02"
        run("todo", "accept", "1.1", "--by", "codex", "--run", "true -> ok", "re-ran it")
        os.environ["EL_SESSION"] = "doer0001"
        self.close_child_phase()

    def test_the_report_repro_a_93_char_summary_passes_whatever_the_name(self):
        summary = "a summary of about ninety-three characters that the agent believes fits the hundred-char limit"
        self.assertLessEqual(len(summary), 100)
        self.assertGreater(len(summary) + len(self.child().name) + 4, 100, "with the old tail it did not fit")
        code, out, err = run("done", summary)
        self.assertEqual(code, 0, err)
        todo = (self.parent() / "TODO.md").read_text(encoding="utf-8")
        self.assertIn(f"1.1 {summary}\n", todo, "the item is the agent's words only")
        self.assertIn(f"- file: [{self.child().name}]({self.child().name}/README.md)", todo, "the proof line names the case")

    def test_an_over_long_summary_is_refused_before_any_write_in_the_agents_words(self):
        before = {p: p.read_bytes() for p in self.cases().rglob("*.md")}
        code, out, err = run("done", "x" * 120)
        self.assertEqual(code, 3)
        self.assertIn("the summary becomes item 1.1 of the parent", err)
        self.assertIn("yours is 120, at most 100 fit", err)
        self.assertIn("Rephrase it, do not cut it", err)
        self.assertEqual(before, {p: p.read_bytes() for p in self.cases().rglob("*.md")}, "nothing was written")

    def test_a_cancel_reason_says_the_word_el_adds(self):
        before = {p: p.read_bytes() for p in self.cases().rglob("*.md")}
        code, out, err = run("case", "cancel", "y" * 94)
        self.assertEqual(code, 3)
        self.assertIn("«снято:» is el's word, the rest is yours", err)
        self.assertIn("yours is 94, at most 93 fit", err)
        self.assertEqual(before, {p: p.read_bytes() for p in self.cases().rglob("*.md")}, "nothing was written")

    def test_a_93_char_cancel_reason_lands_whole_without_the_tail(self):
        # the Codex review, 2026-09-29: the successful cancel had no guard — the old tail came back unnoticed
        reason = "z" * 93
        code, out, err = run("case", "cancel", reason)
        self.assertEqual(code, 0, err)
        todo = (self.parent() / "TODO.md").read_text(encoding="utf-8")
        self.assertIn(f"1.1 снято: {reason}\n", todo)
        self.assertIn(f"- file: [{self.child().name}]({self.child().name}/README.md)", todo)
        self.assertNotIn("waits:", todo)


class TheAcceptanceTallyRises(Base):
    def setUp(self):
        super().setUp()
        self.nested(items=3)
        os.environ["EL_SESSION"] = "second02"
        run("todo", "accept", "1.1", "--by", "codex", "--run", "true -> ok", "re-ran it")
        os.environ["EL_SESSION"] = "doer0001"
        code, out, err = run("todo", "accept", "1.2-1.3", "--by", "owner", "«all good, close it»")
        self.assertEqual(code, 0, err)

    def test_the_owners_word_is_recorded_as_a_quote(self):
        journal = (self.child() / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn("принято 1.2, 1.3: owner · слово владельца: «all good, close it»", journal)

    def test_a_quote_inside_the_owners_words_is_kept(self):
        run("todo", "add", "1", "item 4", "--expect", "[run: t]")
        run("todo", "done", "1.4", "run:true -> ok", "done")
        code, out, err = run("todo", "accept", "1.4", "--by", "owner", '"ship it" — and the rest later')
        self.assertEqual(code, 0, err)
        self.assertIn('слово владельца: «"ship it" — and the rest later»', (self.child() / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_two_quoted_phrases_are_not_a_wrapper(self):
        # the Codex review, 2026-09-29: first and last char alone took «yes» and «no» for one wrapping pair
        run("todo", "add", "1", "item 4", "--expect", "[run: t]")
        run("todo", "done", "1.4", "run:true -> ok", "done")
        code, out, err = run("todo", "accept", "1.4", "--by", "owner", "«yes» and «no»")
        self.assertEqual(code, 0, err)
        self.assertIn("слово владельца: ««yes» and «no»»", (self.child() / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_a_cancelled_case_carries_the_tally_too(self):
        # the Codex review, 2026-09-29: `case cancel` wrote only the reason — accepted work inside vanished above
        code, out, err = run("case", "cancel", "not needed any more")
        self.assertEqual(code, 0, err)
        tally = "3 of 3 done accepted — another session 1 · the owner's word 2 · re-ran 1 of 3 run proof(s)"
        self.assertIn(f"снято: not needed any more · acceptance: {tally}", (self.parent() / "README.md").read_text(encoding="utf-8"))

    def test_the_owners_word_without_words_asks_for_them(self):
        run("todo", "add", "1", "item 4", "--expect", "[run: t]")
        run("todo", "done", "1.4", "run:true -> ok", "done")
        code, out, err = run("todo", "accept", "1.4", "--by", "owner", "«»")
        self.assertEqual(code, 2)
        self.assertIn("needs the owner's words, as said", err)

    def test_one_tally_on_entry_digest_closed_line_and_at_the_parent(self):
        tally = "3 of 3 done accepted — another session 1 · the owner's word 2 · re-ran 1 of 3 run proof(s)"
        self.assertIn(f"acceptance: {tally}", run()[1], "entry")
        self.close_child_phase()
        phase = next((self.child() / "phases").glob("1-*.md")).read_text(encoding="utf-8")
        self.assertIn(f"- acceptance: {tally}", phase, "the Digest of the phase")
        code, out, err = run("done", "the child is done")
        self.assertEqual(code, 0, err)
        self.assertIn(f"acceptance: {tally}", out, "el done says it")
        self.assertIn(f"- closed: ", (self.child() / "README.md").read_text(encoding="utf-8"))
        self.assertIn(f"the child is done · acceptance: {tally}", (self.child() / "README.md").read_text(encoding="utf-8"))
        self.assertIn(f"the child is done · acceptance: {tally}", (self.parent() / "README.md").read_text(encoding="utf-8"),
                      "the parent draws its line about the child from the child's closed: line")


class TheTallyIsCountedHonestly(unittest.TestCase):
    """The Codex review of 2026-09-29, at the level of the readers."""

    def test_an_old_inline_proof_stays_in_the_denominator(self):
        from elephant import commands, grammar
        with tempfile.TemporaryDirectory() as d:
            case = Path(d)
            (case / "phases").mkdir()
            (case / "phases" / "1-work.md").write_text(
                "# Phase 1 — Work\ngoal: g\nresult: r\n\n## Items at close\n"
                "- 1.1 ✓ old task — run: true → ok\n"
                "- 1.2 ✓ new task\n  - result: done\n    - run: true → ok\n  - accepted: codex · another session · 2026-09-29 · re-ran 1 of 1\n",
                encoding="utf-8")
            items = commands._closed_phase_items(case, grammar.Phase(1, "Work", True, 0))
            self.assertEqual(commands._acceptance_tally(items),
                             "1 of 2 done accepted — another session 1 · re-ran 1 of 2 run proof(s)")

    def test_the_tally_on_closed_is_not_counted_in_the_readme_budget(self):
        from elephant import grammar
        body = ("# T\n\n## Context\ng\n\n## State\n- progress: 1 Work ✓\n- closed: 2026-09-29 · ok"
                " · acceptance: 1 of 1 done accepted — the owner's word 1" + " x" * 8000 + "\n\n## Decisions\n\n## Problems\n\n## Links\n")
        r = grammar.parse_readme(body)
        self.assertFalse([e for e in r.errors if e.rule == "F2"], "el's drawing does not fill the owner's budget")


if __name__ == "__main__":
    unittest.main()
