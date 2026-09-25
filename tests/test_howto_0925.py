"""The owner's word of 2026-09-25: «every time we close a phase or a case there must be a step where .howto is checked —
we add what we found; agents rarely update it, and the close is the logical moment; nothing caught — say so». Measured on
the tool's own case the same day: 48 PROBLEM events, one of them names .howto/, four recipes in all. So the close asks
one question when the phase (the case) logged a PROBLEM no recipe answers: `--howto .howto/<verb>.md` (a file whose first
line is `when:`) or `--howto "none: why"`. A phase without PROBLEM is not asked; the rule lives at the close door — an
old phase closed before it is never asked again."""
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
        self.project = Path(self.tmp.name).resolve()
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "api", "--goal", "the service answers in under a second")
        run("phase", "open", "1", "Speed", "--goal", "p95 under a second")
        self.case = next(p for p in (self.project / ".cases").iterdir() if p.is_dir())
        run("todo", "add", "1", "cache the price lookup")
        run("todo", "done", "1.1", "owner", "cached")
        run("log", "RESULT", "p95 820 ms")
        (self.project / ".howto").mkdir()

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def journal(self) -> str:
        return (self.case / "JOURNAL.md").read_text(encoding="utf-8")

    def recipe(self, name="restart-redis.md", first="when: redis refuses connections after the deploy"):
        (self.project / ".howto" / name).write_text(f"{first}\n\n1. restart the pod\n", encoding="utf-8")

    def close(self, *extra):
        return run("phase", "close", "1", "fast", "--reflect", "measure first", "--align", "next: errors", *extra)


class PhaseClose(Base):
    def test_a_phase_with_a_problem_asks_for_the_recipe(self):
        run("log", "PROBLEM", "redis refused connections after the deploy → restart")
        before = self.journal()
        code, _, err = self.close()
        self.assertEqual(code, 4)
        self.assertIn("--howto", err)
        self.assertIn("none:", err)
        self.assertEqual(self.journal(), before, "a refused close writes nothing, reflect and align included")

    def test_a_recipe_answers_it_and_is_linked(self):
        run("log", "PROBLEM", "redis refused connections after the deploy → restart")
        self.recipe()
        code, out, err = self.close("--howto", ".howto/restart-redis.md")
        self.assertEqual(code, 0, err)
        self.assertIn("DECISION · howto: [restart-redis.md](../../.howto/restart-redis.md)", self.journal())

    def test_a_recipe_that_is_not_there_is_refused(self):
        run("log", "PROBLEM", "redis refused")
        code, _, err = self.close("--howto", ".howto/nothing.md")
        self.assertEqual(code, 4)
        self.assertIn(".howto/nothing.md", err)

    def test_a_recipe_without_its_when_line_is_refused(self):
        run("log", "PROBLEM", "redis refused")
        self.recipe(first="# how to restart redis")
        code, _, err = self.close("--howto", ".howto/restart-redis.md")
        self.assertEqual(code, 3)
        self.assertIn("when:", err)

    def test_nothing_caught_is_an_honest_answer_with_its_reason(self):
        run("log", "PROBLEM", "a typo in the config")
        self.assertEqual(self.close("--howto", "none")[0], 2, "none needs its reason")
        code, _, err = self.close("--howto", "none: a one-off typo, nothing repeats")
        self.assertEqual(code, 0, err)
        self.assertIn("DECISION · howto: none: a one-off typo, nothing repeats", self.journal())

    def test_no_problem_no_question(self):
        code, _, err = self.close()
        self.assertEqual(code, 0, err)
        self.assertNotIn("howto:", self.journal())

    def test_a_problem_that_already_names_its_recipe_is_answered(self):
        self.recipe()
        run("log", "PROBLEM", "redis refused → .howto/restart-redis.md")
        code, _, err = self.close()
        self.assertEqual(code, 0, err)

    def test_the_order_line_names_the_question_before_the_close(self):
        run("log", "PROBLEM", "redis refused")
        out = run()[1]
        self.assertIn("phase 1 Speed: every item ended", out)
        self.assertIn("--howto", out)


class CaseClose(Base):
    def test_the_case_asks_once_for_problems_no_phase_answered(self):
        run("log", "PROBLEM", "redis refused")
        self.close("--howto", "none: one-off")
        code, _, err = run("done", "the service is fast")
        self.assertEqual(code, 0, err + "\n— every PROBLEM was answered at its phase close")

    def test_a_problem_outside_any_answered_phase_holds_the_case(self):
        self.close()
        run("log", "--phase", "1", "PROBLEM", "the CDN cached a stale price")  # logged after the phase closed
        code, _, err = run("done", "the service is fast")
        self.assertEqual(code, 4)
        self.assertIn("--howto", err)
        code, _, err = run("done", "the service is fast", "--howto", "none: the CDN rule is in the deploy script now")
        self.assertEqual(code, 0, err)
        self.assertIn("DECISION · howto: none: the CDN rule is in the deploy script now", self.journal())


class NotRetroactive(Base):
    def test_a_phase_closed_before_the_rule_does_not_block_the_next_one(self):
        self.close()
        run("log", "--phase", "1", "PROBLEM", "found later, logged under the closed phase")
        code, _, err = run("phase", "open", "2", "Errors", "--goal", "no 5xx")
        self.assertEqual(code, 0, err)

    def test_the_marks_of_nested_cases_are_not_problems(self):
        run("spawn", "cdn investigation", "--goal", "why the CDN caches prices")
        child = next(p for p in self.case.iterdir() if p.is_dir() and p.name.endswith("cdn-investigation"))
        os.environ["EL_CASE"] = child.name
        run("done", "the CDN rule was wrong")
        os.environ.pop("EL_CASE")
        os.environ["EL_CASE"] = self.case.name
        code, _, err = self.close()
        os.environ.pop("EL_CASE")
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
