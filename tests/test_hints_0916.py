"""The owner's word of 2026-09-16 in sync mode: agents lack best practices, and a pasted instruction does not
teach — what teaches is the line in the command output right before the next decision. So: `hint:` as the
tool's fourth voice (derived from the case, one per output, last line, gone once acted on, EL_HINTS=0 off),
`el help practice` as weak-against-strong pairs by moment, an exemplar after `case new` to imitate, and
`expect:` — the proof promised BEFORE the work, held to at `done` (pre-registration; Lean's type of a theorem)."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, hints, knowledge
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ.pop("EL_HINTS", None)
        self.root = Path(self.tmp.name) / ".cases"

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def case(self) -> Path:
        return next(p for p in self.root.iterdir() if p.is_dir())

    def read(self, name: str) -> str:
        return (self.case() / name).read_text(encoding="utf-8")

    def open_case(self):
        run("case", "new", "app", "--goal", "g")
        run("phase", "open", "1", "Build", "--goal", "b")
        (self.case() / "docs").mkdir()
        (self.case() / "docs" / "db-choice.md").write_text("# DB\nsummary: why postgres\n", encoding="utf-8")


class Expect(Base):
    def setUp(self):
        super().setUp()
        self.open_case()
        run("todo", "add", "1", "choose the database", "--why", "cost and migrations depend on it")

    def test_set_render_and_promised_kinds(self):
        code, out, err = run("todo", "expect", "1.1", "chosen DB with its case [file: docs/db-choice.md] · load [run: k6 → p95] · budget [owner]")
        self.assertEqual(code, 0, err)
        self.assertIn("proofs promised: file · run · owner", out)
        self.assertIn("  - [ ] 1.1 choose the database\n    - why: cost and migrations depend on it\n"
                      "    - expect: chosen DB with its case [file: docs/db-choice.md] · load [run: k6 → p95] · budget [owner]\n", self.read("TODO.md"))
        self.assertEqual(grammar.expected_kinds("a [file: x] b [owner] c [run: k6 → 1]"), [("file", "x"), ("owner", ""), ("run", "k6 → 1")])
        code, _, err = run("todo", "expect", "1.1", "a screenshot [photo: x]")
        self.assertEqual(code, 2)
        self.assertIn("`[photo…]` is not a kind of proof", err)
        r = grammar.parse_todo("# T\n\n- [ ] 1 B\n  - [ ] 1.1 a\n    - expect: x [photo: y]\n")
        self.assertTrue(any("is not a kind of proof" in f.message for f in r.errors), "the parser refuses it too")
        code, out, _ = run("todo", "expect", "1.1", "")
        self.assertIn("expect 1.1 removed", out)

    def test_done_holds_the_record_to_the_promise(self):
        run("todo", "expect", "1.1", "chosen DB with its case [file: docs/db-choice.md] · load [run: k6 → p95] · budget [owner]")
        code, out, err = run("todo", "done", "1.1", "owner", "Postgres, agreed")
        self.assertEqual(code, 0, f"short proof is shown, never refused: {err}")
        self.assertIn("expect 1.1: 1 of 3 filled — missing [file: docs/db-choice.md] [run: k6 → p95]: the proof is short, or the expectation was wrong", out)
        self.assertIn("el todo expect 1.1", out)
        self.assertIn("RESULT · 1.1: owner — Postgres, agreed (1.1 expected file · run · owner, got owner)", self.read("JOURNAL.md"))
        code, out, err = run("todo", "done", "1.1", "file:docs/db-choice.md", "run:k6 run load.js -> p95 48ms", "case written, load measured")
        self.assertEqual(code, 0, err)
        self.assertIn("expect 1.1: 3 of 3 filled — file · run · owner", out)
        j = self.read("JOURNAL.md")
        self.assertNotIn("got file · owner · run)", j, "a kept promise adds nothing to the RESULT")

    def test_digest_counts_expectations_and_reopen_keeps_expect(self):
        run("todo", "expect", "1.1", "the choice [file: docs/db-choice.md] [owner]")
        run("todo", "add", "1", "write the migration", "--expect", "[run: alembic upgrade → ok]")
        run("todo", "done", "1.1", "file:docs/db-choice.md", "owner", "Postgres")
        run("todo", "done", "1.2", "owner", "done, no run")
        run("todo", "reopen", "1.2", "not really")
        self.assertIn("    - expect: [run: alembic upgrade → ok]\n", self.read("TODO.md"), "reopen keeps the promise")
        self.assertNotIn("- result:", self.read("TODO.md").split("1.2 write")[1])
        run("todo", "done", "1.2", "owner", "done, still no run")
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: ask before choosing")
        run("log", "DECISION", "align: next phase migrates")
        code, out, err = run("phase", "close", "1", "chosen")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-build.md")
        self.assertIn("- expectations: 1 met · 1 short (1.2 expected run, got owner)\n", pf)
        self.assertIn("  - expect: [run: alembic upgrade → ok]\n", pf, "the promise travels into the phase file")
        self.assertEqual(run("check")[0], 0)


class Hints(Base):
    def test_todo_add_hints_why_then_expect_then_nothing_and_off_switch(self):
        self.open_case()
        code, out, _ = run("todo", "add", "1", "choose the database")
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("hint: the owner will read 1.1 without you — say what it is for: el todo why 1.1"), out)
        self.assertEqual(out.count("hint:"), 1, "one hint per output")
        code, out, _ = run("todo", "add", "1", "write the migration", "--why", "w")
        self.assertIn("hint: what will prove 1.2 done? write it before the work, not after: el todo expect 1.2", out)
        code, out, _ = run("todo", "add", "1", "ship", "--why", "w", "--expect", "[run: deploy → ok]")
        self.assertNotIn("hint:", out, "nothing left to hint — the hint is gone once acted on")
        os.environ["EL_HINTS"] = "0"
        code, out, _ = run("todo", "add", "1", "plain")
        self.assertNotIn("hint:", out)

    def test_done_with_only_owner_hints_a_thing_behind_it(self):
        self.open_case()
        run("todo", "add", "1", "a", "--why", "w", "--expect", "[owner]")
        code, out, _ = run("todo", "done", "1.1", "owner", "agreed")
        self.assertIn("hint: owner is the word that counts, and the hardest to check later", out)
        run("todo", "add", "1", "b")
        code, out, _ = run("todo", "done", "1.2", "file:docs/db-choice.md", "written")
        self.assertNotIn("owner is the word", out)

    def test_problem_hints_a_recipe_until_the_habit_is_there(self):
        self.open_case()
        code, out, _ = run("log", "PROBLEM", "timeout → pool too small → raised it")
        self.assertIn("hint: will it bite again? a recipe .howto/<verb>.md", out)
        howto = Path(self.tmp.name) / ".howto"
        howto.mkdir()
        for i in range(3):
            (howto / f"r{i}.md").write_text("when: x\n", encoding="utf-8")
        code, out, _ = run("log", "PROBLEM", "another one")
        self.assertNotIn("hint:", out, "three recipes: the habit is there")
        code, out, _ = run("log", "DECISION", "chose x")
        self.assertNotIn("hint:", out)

    def test_open_close_and_case_new_hints_and_the_exemplar(self):
        code, out, _ = run("case", "new", "app", "--goal", "g")
        self.assertIn("a well-led item looks like this", out)
        self.assertIn("    - expect: the chosen DB with its case [file: docs/db-choice.md]", out)
        self.assertTrue(out.rstrip().splitlines()[-1].startswith("hint: phases you already see? name them now"))
        code, out, _ = run("phase", "open", "1", "Build", "--goal", "b")
        self.assertIn("hint: what must be true when phase 1 closes? promise it in the goal, one proof per criterion", out)
        run("todo", "add", "1", "a")
        run("todo", "done", "1.1", "owner", "ok")
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: ask first")
        run("log", "DECISION", "align: next")
        code, out, err = run("phase", "close", "1", "done")
        self.assertEqual(code, 0, err)
        self.assertIn("hint: the Digest of phase 1 holds no PROBLEM and no DECISION", out)

    def test_entry_hint_is_last_derived_and_rotates_with_the_journal(self):
        self.open_case()
        code, out, _ = run()
        lines = out.rstrip().splitlines()
        self.assertTrue(lines[-1].startswith("hint: how strong agents lead a case"), "nothing specific yet: the onboarding hint")
        self.assertEqual(out.count("\nhint: "), 1)
        run("phase", "plan", "2", "Rollout", "--goal", "r")   # specific: an empty planned phase
        run("todo", "add", "1", "a")                          # specific: items without pockets
        run("todo", "add", "1", "b")
        seen = {run()[1].rstrip().splitlines()[-1]}
        for text in ("a", "b", "c", "d"):
            run("log", "DECISION", text)  # every write moves the choice
            seen.add(run()[1].rstrip().splitlines()[-1])
        self.assertGreater(len(seen), 1, "a long session sees more than one hint")
        self.assertTrue(any("phase 2 Rollout? park it" in h for h in seen), seen)
        self.assertTrue(any("items carry pockets" in h for h in seen), seen)
        self.assertFalse(any("el help practice" in h and "weak against strong" in h for h in seen), "the generic hint yields to specific ones")
        os.environ["EL_HINTS"] = "0"
        self.assertNotIn("hint:", run()[1])

    def test_practice_topic_and_start_mention_hints(self):
        code, out, _ = run("help", "practice")
        self.assertEqual(code, 0)
        for word in ("ENTRY", "DONE", "weak", "strong", "reflect", "a well-led item looks like this"):
            self.assertIn(word, out)
        self.assertIn("`hint:`", knowledge.TOPICS["start"])
        self.assertIn("hint:", Path("/Users/mykhailo/MyProjects/elephant-cli/AGENT.md").read_text(encoding="utf-8"))


class ReflectRepeatsAResult(Base):
    def test_a_result_dressed_as_a_lesson_is_named_at_close(self):
        self.open_case()
        run("todo", "add", "1", "a")
        run("todo", "done", "1.1", "owner", "ok")
        run("log", "RESULT", "live testing on DEV and UAT confirmed group 000009641 returns 22.0% discounts from Azure SQL")
        run("log", "DECISION", "reflect: live testing on DEV and UAT confirmed group 000009641 returns 22.0% discounts")
        run("log", "DECISION", "align: phase 2 prepares the copies for the hearing")
        code, out, err = run("phase", "close", "1", "verified")
        self.assertEqual(code, 0, f"a warning, not a gate: {err}")
        self.assertIn("reflect: repeats RESULT · live testing on DEV and UAT", err)
        self.assertIn("reflect is a lesson about how you worked", err)
        self.assertNotIn("align: repeats", err)


if __name__ == "__main__":
    unittest.main()
