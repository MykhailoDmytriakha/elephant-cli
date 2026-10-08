"""The live migration of 2026-10-07: an agent spawned forty-one nested cases under a map that asks for two hands, then
wrote each child's README whole from stdin. The Context it wrote had no `- rule: two hands` line, el answered «written»,
and every child closed its phase with one hand while the map showed ✓. A case rule is the owner's to drop — by a door
that names it, never by being left out of a rewrite."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

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
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="rules1007", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)
        run("case", "new", "probe", "--goal", "g")
        self.readme = next(Path(self.tmp.name, ".cases").glob("*/README.md"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def write(self, context):
        src = Path(self.tmp.name) / "readme-in.md"
        src.write_text(README.format(context=context), encoding="utf-8")
        return run("readme", "--file", str(src))


class AWholeRewriteKeepsTheRules(Base):
    def test_a_rewrite_without_the_rule_keeps_it_and_says_how_to_drop_it(self):
        code, out, err = self.write("A new context without the rule.")
        self.assertEqual(code, 0, err)
        self.assertIn("- rule: two hands", self.readme.read_text(encoding="utf-8"))
        self.assertIn("kept in Context: - rule: two hands", out)
        self.assertTrue(out.rstrip("\n").split("\n")[-1].endswith("el readme drop context 1 (with the owner's word)"),
                        "the last line says it — the agent reads `tail -1`")

    def test_a_rewrite_that_keeps_the_rule_in_its_own_words_is_left_alone(self):
        code, out, err = self.write("A new context.\n- rule: two hands — as the owner said")
        self.assertEqual(code, 0, err)
        text = self.readme.read_text(encoding="utf-8")
        self.assertEqual(text.count("- rule: two hands"), 1)
        self.assertNotIn("kept in Context", out)

    def test_the_kept_rule_still_holds_the_close(self):
        self.write("A new context without the rule.")
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")
        run("todo", "add", "1", "a step", "--expect", "[run: probe → ok]")
        run("todo", "done", "1.1", "run:probe → ok", "it answers")
        code, _, err = run("phase", "close", "1", "s", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("done items not accepted — 1.1 (this case's rule: two hands)", err)

    def test_the_drop_door_still_drops_it(self):
        code, out, err = run("readme", "drop", "context", "1")
        self.assertEqual(code, 0, err)
        self.assertNotIn("- rule: two hands", self.readme.read_text(encoding="utf-8"))
        code, out, err = self.write("A context after the owner dropped the rule.")
        self.assertNotIn("kept in Context", out)
        self.assertNotIn("- rule: two hands", self.readme.read_text(encoding="utf-8"))

    def test_an_opt_in_rule_is_kept_the_same_way(self):
        run("readme", "add", "context", "rule: items link their material")
        code, out, err = self.write("A new context.\n- rule: two hands — kept by me")
        self.assertIn("- rule: items link their material", self.readme.read_text(encoding="utf-8"))
        self.assertIn("kept in Context: - rule: items link their material", out)


if __name__ == "__main__":
    unittest.main()
