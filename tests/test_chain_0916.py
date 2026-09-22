"""The owner's word of 2026-09-16 in sync mode: items are cut by what they leave behind (one outcome with its own
proof each; two items with one artifact were one item), the expectation lives at every size of the node (a phase
`goal:` may promise artifacts and the Digest holds it to them), and a chain hands its artifacts forward — the
proofs of the items an item comes after are its inputs (`el todo show N.M`)."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ.pop("EL_HINTS", None)
        run("case", "new", "api", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "research").mkdir()
        for name in ("why.md", "db.md", "answer.md"):
            (self.case / "research" / name).write_text(f"# {name}\nsummary: {name}\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class CutByWhatIsLeft(Base):
    def setUp(self):
        super().setUp()
        run("phase", "open", "1", "Research", "--goal", "r")
        run("todo", "add", "1", "why was it disconnected", "--why", "w", "--expect", "the reason [file: research/why.md]")

    def test_an_expect_naming_another_items_artifact_is_named(self):
        code, out, _ = run("todo", "add", "1", "read the merge commit", "--why", "w", "--expect", "the commit [file: research/why.md]")
        self.assertEqual(code, 0)
        self.assertIn("hint: [file: research/why.md] is also the artifact of 1.1 — one artifact, one item: is 1.2 a step of 1.1?", out)
        self.assertIn('el todo note 1.1 "…" and el todo cancel 1.2 "step of 1.1"', out)
        code, out, _ = run("todo", "expect", "1.2", "the commit [file: research/db.md]")
        self.assertNotIn("one artifact, one item", out, "a different artifact: nothing to say")
        run("todo", "done", "1.1", "file:research/why.md", "disconnected on purpose")
        code, out, _ = run("todo", "expect", "1.2", "again [file: research/why.md]")
        self.assertIn("is also the artifact of 1.1", out, "an artifact another item already left counts too")

    def test_the_done_warning_names_the_cutting_rule(self):
        run("todo", "add", "1", "another")
        run("todo", "done", "1.1", "file:research/why.md", "a")
        code, out, err = run("todo", "done", "1.2", "file:research/why.md", "b")
        self.assertIn("items are cut by what they leave behind", err)
        self.assertIn("two items with one artifact were one item with steps in its notes", err)


class PhasePromise(Base):
    def test_goal_placeholders_are_validated_and_held_to_at_close(self):
        code, _, err = run("phase", "plan", "1", "Research", "--goal", "the answer [photo: x]")
        self.assertEqual(code, 2)
        self.assertIn("not a kind of proof", err)
        run("phase", "plan", "1", "Research", "--goal", "why and how [file: research/answer.md] [run: curl → 200]")
        self.assertIn("- [ ] 1 Research — why and how [file: research/answer.md] [run: curl → 200]", self.read("TODO.md"))
        run("phase", "open", "1")
        self.assertIn("goal: why and how [file: research/answer.md] [run: curl → 200]", self.read("phases/1-research.md"))
        run("todo", "add", "1", "write the answer", "--expect", "[file: research/answer.md]")
        run("todo", "done", "1.1", "file:research/answer.md", "written")
        run("log", "RESULT", "r")
        code, out, err = run("phase", "close", "1", "answered", "--reflect", "ask first", "--align", "next phase re-enables")
        self.assertEqual(code, 4, "the promise holds the close (1.17.0): [run: curl → 200] has no item")
        self.assertIn("phase 1 promised [run: curl → 200] and no done item proves it", err)
        self.assertNotIn("reflect: ask first", self.read("JOURNAL.md"), "a refused close logs nothing")
        run("todo", "add", "1", "call it", "--expect", "[run: curl → 200]")
        run("todo", "done", "1.2", "run:curl /v2 -> 200", "re-enabled")
        code, out, err = run("phase", "close", "1", "answered", "--reflect", "ask first", "--align", "next phase re-enables")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-research.md")
        self.assertIn("- phase promise: 2 of 2 proved — [file: research/answer.md] by 1.1 · [run: curl → 200] by 1.2\n", pf)
        self.assertEqual(run("check")[0], 0)


class TodoShow(Base):
    def test_the_card_prints_pockets_inputs_and_feeds(self):
        run("phase", "open", "1", "Research", "--goal", "r")
        run("todo", "add", "1", "why was it disconnected", "--why", "the owner asked", "--expect", "[file: research/why.md]")
        run("todo", "add", "1", "what the DB holds", "--expect", "[file: research/db.md]")
        run("todo", "add", "1", "the answer — after: 1.1, 1.2", "--note", "combine both", "--expect", "[file: research/answer.md]")
        run("spawn", "side", "--goal", "s")
        run("case", "use", "api")
        run("todo", "after", "1.3", "1.1, 1.2, " + next(p.name for p in self.case.iterdir() if p.is_dir() and p.name.endswith("-side")))
        run("todo", "done", "1.1", "file:research/why.md", "disconnected on purpose in the API merge")
        code, out, err = run("todo", "show", "1.3")
        self.assertEqual(code, 0, err)
        self.assertIn("phase 1 Research (open)", out)
        self.assertIn("  - [ ] 1.3 the answer — after: 1.1, 1.2, ", out)
        self.assertIn("    - note: combine both\n    - expect: [file: research/answer.md]", out)
        self.assertIn("  ← 1.1 ✓ «why was it disconnected» — file [why.md](research/why.md)", out)
        self.assertIn("  ← 1.2 open «what the DB holds» — nothing to hand over yet", out)
        self.assertIn("(nested case) — its README is the input: el --case", out)
        code, out, err = run("todo", "show", "1.1")
        self.assertIn("  → feeds 1.3", out)
        code, out, err = run("todo", "show", "1.2")
        self.assertIn("→ feeds 1.3", out)
        code, _, err = run("todo", "show", "1.9")
        self.assertNotEqual(code, 0)

    def test_practice_has_the_chain_and_the_cutting_rule(self):
        p = knowledge.TOPICS["practice"]
        self.assertIn("A CHAIN", p)
        self.assertIn("Cut by what is left behind", p)
        self.assertIn("el todo show", knowledge.TOPICS["todo"])
        self.assertIn("phase promise", knowledge.TOPICS["phases"])


if __name__ == "__main__":
    unittest.main()
