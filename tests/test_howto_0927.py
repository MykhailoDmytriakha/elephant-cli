"""The owner's word, 2026-09-27: «how-to is how to do things, so you know what you can do — and only then: stuck, solved,
add one; we have no instruction that how-to is to be used». Measured the same day: 30 PROBLEM events in live projects and
not one recipe; on the tool's own project five recipes over 48 PROBLEMs, one naming `.howto/`. The block taught half of P7
(«solved — el log PROBLEM»), the entry never named `.howto/`, and the PROBLEM hint fell silent at three recipes.
Since 1.28.0: the block says what .howto/ is and both halves of the loop; the entry renders `howto:` with the recipe names;
the PROBLEM hint asks until the PROBLEM names its recipe — the same test the phase close asks by."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge
from tests.test_commands import run


class HowtoOnEntry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        run("case", "new", "api", "--goal", "g")

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def test_no_recipes_no_line(self):
        code, out, _ = run()
        self.assertEqual(code, 0)
        self.assertNotIn("howto:", out, "nothing to list is not a line to read")

    def test_the_entry_names_what_the_project_already_knows_how_to_do(self):
        howto = Path(self.tmp.name) / ".howto"
        howto.mkdir()
        for name in ("restart-cache", "get-logs-from-instances"):
            (howto / f"{name}.md").write_text("when: x\n", encoding="utf-8")
        (howto / "notes.txt").write_text("not a recipe", encoding="utf-8")
        code, out, _ = run()
        self.assertEqual(code, 0)
        line = next(ln for ln in out.splitlines() if ln.startswith("howto: "))
        self.assertIn("2 recipe(s) — what this project already knows how to do: get-logs-from-instances · restart-cache", line)
        self.assertIn("taking a task, open its recipe", line, "before the task, not only after the wall")
        self.assertIn('grep -ril "<words>" .howto/', line)
        self.assertLess(out.index("howto: "), out.index("## Context"), "with the counted lines, above the README")

    def test_a_nested_case_sees_the_project_recipes(self):
        howto = Path(self.tmp.name) / ".howto"
        howto.mkdir()
        (howto / "restart-cache.md").write_text("when: x\n", encoding="utf-8")
        run("spawn", "cache down", "--goal", "g")
        code, out, _ = run()
        self.assertIn("howto: 1 recipe(s)", out, "recipes are the project's, not the case's (L7)")


class TheBlockTeachesTheWholeLoop(unittest.TestCase):
    def test_the_block_says_what_howto_is_and_both_halves(self):
        block = knowledge.ONBOARDING_BLOCK
        self.assertIn("`.howto/` — что здесь уже умеют", block, "what it is: what the project can already do")
        self.assertIn("берёшься за задачу — открой её рецепт", block, "used before the task")
        self.assertIn('упёрся — `grep -ril "<слова ошибки>" .howto/`', block, "and when stuck")
        self.assertIn("решил новое — `el log PROBLEM` и рецепт `.howto/<глагол>.md`", block, "P7 whole, not half")
        self.assertIn("`when: <слова беды>`", block)

    def test_the_start_dose_says_it_too(self):
        dose = knowledge.resolve("start")
        self.assertIn("what this project already knows how to do", dose)
        self.assertIn("open its recipe first", dose)


if __name__ == "__main__":
    unittest.main()
