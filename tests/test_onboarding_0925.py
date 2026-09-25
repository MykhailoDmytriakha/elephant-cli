"""The owner's word of 2026-09-25: «bake the onboarding into el — if Elephant updated, the onboarding must update too;
el decides where to write it: where the current onboarding is, it writes there; where there is none, it finds the place».
A pasted copy goes stale silently (three versions of the block in three days), so the block el writes carries a
fingerprint between two marks; the entry compares it with the block el ships and refreshes it itself. A block edited by
hand is not overwritten silently, a block pasted by hand is named, the text outside the marks is never touched."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge, onboarding
from tests.test_commands import run

HARNESS_ENVS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "AI_AGENT")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.project = Path(self.tmp.name).resolve()
        self.saved = {k: os.environ.pop(k, None) for k in HARNESS_ENVS + ("EL_CASE", "EL_ONBOARDING")}
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_ONBOARDING"] = "0"
        run("case", "new", "api", "--goal", "the service answers in under a second")
        os.environ["EL_ONBOARDING"] = "1"

    def tearDown(self):
        os.chdir(self.old)
        for k in HARNESS_ENVS + ("EL_HINTS",):
            os.environ.pop(k, None)
        for k, v in self.saved.items():
            if v is not None:
                os.environ[k] = v
        os.environ["EL_ONBOARDING"] = "0"
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.project / name).read_text(encoding="utf-8")

    def stale_block(self) -> str:
        old = "## Elephant — память работы в `.cases/`\n\nold rhythm: read README, then work."
        return (f"<!-- elephant onboarding 1.23.0 · {onboarding.fingerprint(old)} — written by el -->\n{old}\n{onboarding.END}")


class Write(Base):
    def test_no_block_anywhere_claude_code_gets_claude_md(self):
        os.environ["CLAUDECODE"] = "1"
        code, out, err = run("onboarding")
        self.assertEqual(code, 0, err)
        text = self.read("CLAUDE.md")
        self.assertIn(knowledge.ONBOARDING_BLOCK.strip(), text)
        self.assertRegex(text, r"<!-- elephant onboarding \S+ · [0-9a-f]{12} ")
        self.assertIn(onboarding.END, text)
        self.assertIn("CLAUDE.md", out)
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_another_agent_gets_agents_md(self):
        code, out, err = run("onboarding")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / "CLAUDE.md").exists())

    def test_the_owner_text_stays_byte_for_byte(self):
        os.environ["CLAUDECODE"] = "1"
        own = "# My project\n\n- run tests with make test\n"
        (self.project / "CLAUDE.md").write_text(own, encoding="utf-8")
        run("onboarding")
        text = self.read("CLAUDE.md")
        self.assertTrue(text.startswith(own), "the owner's lines come first, untouched")
        self.assertEqual(text.count("<!-- elephant onboarding"), 1)

    def test_it_writes_where_the_block_already_is(self):
        os.environ["CLAUDECODE"] = "1"
        (self.project / "CLAUDE.md").write_text("# claude rules\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("# agents\n\n" + self.stale_block() + "\n\n## after\n- keep me\n", encoding="utf-8")
        code, out, err = run("onboarding")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read("CLAUDE.md"), "# claude rules\n", "not added where it never was")
        agents = self.read("AGENTS.md")
        self.assertIn(knowledge.ONBOARDING_BLOCK.strip(), agents)
        self.assertNotIn("old rhythm", agents)
        self.assertTrue(agents.startswith("# agents\n\n") and agents.endswith("\n\n## after\n- keep me\n"))

    def test_a_block_pasted_by_hand_is_put_under_marks_in_place(self):
        pasted = "# rules\n\n## Elephant — память работы в `.cases/`\n\n- Начинай сессию с `el`.\n- Пиши только через `el`.\n\n## Deploy\n- via make\n"
        (self.project / "AGENTS.md").write_text(pasted, encoding="utf-8")
        code, out, err = run("onboarding")
        self.assertEqual(code, 0, err)
        text = self.read("AGENTS.md")
        self.assertTrue(text.startswith("# rules\n\n<!-- elephant onboarding"))
        self.assertTrue(text.endswith("\n\n## Deploy\n- via make\n"))
        self.assertNotIn("Пиши только через `el`.\n", text.split(onboarding.END)[1])
        self.assertIn("pasted by hand", out)

    def test_symlinked_files_get_one_block(self):
        (self.project / "AGENTS.md").write_text("# shared\n", encoding="utf-8")
        (self.project / "CLAUDE.md").symlink_to("AGENTS.md")
        os.environ["CLAUDECODE"] = "1"
        run("onboarding")
        self.assertTrue((self.project / "CLAUDE.md").is_symlink(), "the link stays a link")
        self.assertEqual(self.read("AGENTS.md").count("<!-- elephant onboarding"), 1)
        run("onboarding")
        self.assertEqual(self.read("AGENTS.md").count("<!-- elephant onboarding"), 1)

    def test_show_prints_and_writes_nothing(self):
        code, out, err = run("onboarding", "--show")
        self.assertEqual(code, 0, err)
        self.assertIn(knowledge.ONBOARDING_BLOCK.strip(), out)
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_current_block_is_left_alone(self):
        run("onboarding")
        before = self.read("AGENTS.md")
        code, out, _ = run("onboarding")
        self.assertIn("current", out)
        self.assertEqual(self.read("AGENTS.md"), before)


class Entry(Base):
    def test_entry_refreshes_a_stale_block_itself(self):
        (self.project / "CLAUDE.md").write_text("# mine\n\n" + self.stale_block() + "\n", encoding="utf-8")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn("onboarding refreshed in CLAUDE.md", out)
        text = self.read("CLAUDE.md")
        self.assertTrue(text.startswith("# mine\n\n"))
        self.assertIn(knowledge.ONBOARDING_BLOCK.strip(), text)
        self.assertNotIn("old rhythm", text)
        self.assertNotIn("onboarding refreshed", run()[1], "once refreshed, silent")

    def test_a_hand_edit_inside_the_marks_is_named_not_overwritten(self):
        run("onboarding")
        text = self.read("AGENTS.md").replace("Ты начинаешь без памяти", "Ты начинаешь без памяти (my edit)")
        (self.project / "AGENTS.md").write_text(text, encoding="utf-8")
        out = run()[1]
        self.assertIn("(my edit)", self.read("AGENTS.md"))
        self.assertIn("edited by hand", out)
        self.assertIn("el onboarding", out)

    def test_a_pasted_block_is_an_order_line_on_entry(self):
        (self.project / "AGENTS.md").write_text("## Elephant — память работы в `.cases/`\n\n- Начинай сессию с `el`.\n", encoding="utf-8")
        out = run()[1]
        self.assertIn("pasted by hand", out)
        self.assertIn("el onboarding", out)

    def test_switched_off_means_silent(self):
        (self.project / "CLAUDE.md").write_text(self.stale_block() + "\n", encoding="utf-8")
        os.environ["EL_ONBOARDING"] = "0"
        run()
        self.assertIn("old rhythm", self.read("CLAUDE.md"))


class CaseNew(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.pop(k, None) for k in HARNESS_ENVS + ("EL_CASE",)}
        os.environ["EL_ONBOARDING"] = "1"

    def tearDown(self):
        os.chdir(self.old)
        for k in HARNESS_ENVS:
            os.environ.pop(k, None)
        for k, v in self.saved.items():
            if v is not None:
                os.environ[k] = v
        os.environ["EL_ONBOARDING"] = "0"
        self.tmp.cleanup()

    def test_the_first_case_writes_the_block_where_the_agent_reads(self):
        os.environ["CLAUDECODE"] = "1"
        code, out, err = run("case", "new", "api", "--goal", "g")
        self.assertEqual(code, 0, err)
        self.assertIn("onboarding → CLAUDE.md", out)
        self.assertIn(knowledge.ONBOARDING_BLOCK.strip(), (Path(self.tmp.name) / "CLAUDE.md").read_text(encoding="utf-8"))


class Source(unittest.TestCase):
    def test_onboarding_md_carries_the_block_el_ships(self):
        text = (Path(__file__).resolve().parent.parent / "ONBOARDING.md").read_text(encoding="utf-8")
        self.assertEqual(text.split("\n---\n", 1)[1].strip(), knowledge.ONBOARDING_BLOCK.strip(),
                         "one source: the block lives in el (knowledge.ONBOARDING_BLOCK); ONBOARDING.md shows the same text")


if __name__ == "__main__":
    unittest.main()
