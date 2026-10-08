"""Batch 19 (2026-10-08): two reports — one from an agent in a live migration, one the maintainer wrote through
`el feedback --wall` — and the live chain of sessions that never accepted."""
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
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="aaaa1008", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)
        run("case", "new", "probe", "--goal", "g")
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")
        run("todo", "add", "1", "a step", "--expect", "[run: probe → ok]")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-probe"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class ABareTodoShowsThePlan(Base):
    """Three agents in two live runs and the maintainer typed bare `el todo` to read the plan and met a usage refusal;
    a bare `el readme` answers the same question by showing."""

    def test_bare_todo_prints_the_todo_and_ends_with_the_door(self):
        code, out, err = run("todo")
        self.assertEqual(code, 0, err)
        self.assertIn("- [ ] 1.1 a step", out)
        self.assertNotIn("stamp:", out)
        self.assertTrue(out.rstrip("\n").split("\n")[-1].startswith("write: el todo add N"), "tail -1 is the door")

    def test_an_action_without_its_number_keeps_the_usage_voice(self):
        code, _, err = run("todo", "done")
        self.assertEqual(code, 2)
        self.assertIn("the following arguments are required: ref", err)


class AProofPathThatClimbsIntoTheProject(Base):
    """The live agent named a recipe from the case folder as `file:../../.howto/x.md` and was refused, though the file
    lies inside the project — the form wider, the canon inside."""

    def test_a_climbing_path_inside_the_project_is_taken(self):
        (Path(self.tmp.name) / ".howto").mkdir()
        (Path(self.tmp.name) / ".howto" / "probe.md").write_text("when: the probe fails\n", encoding="utf-8")
        code, out, err = run("todo", "done", "1.1", "file:../../.howto/probe.md", "the recipe is written")
        self.assertEqual(code, 0, err)
        self.assertIn("[probe.md](../../.howto/probe.md)", (self.case / "TODO.md").read_text(encoding="utf-8"))

    def test_a_path_out_of_the_project_is_still_refused(self):
        code, _, err = run("todo", "done", "1.1", "file:../../../elsewhere.md", "x")
        self.assertEqual(code, 2)
        self.assertIn("leads outside the project", err)


class ANewVersionNamesItsDoer(Base):
    """The live migration: each fresh session improved the map, recorded the new version and so became its doer — none
    came only to check, and the acceptance never happened. The re-signing names what it costs."""

    def test_a_version_signed_by_another_session_says_whose_acceptance_it_is(self):
        docs = self.case / "docs"
        docs.mkdir()
        (docs / "map.md").write_text("# map\n\nsummary: the map\n\nv1\n", encoding="utf-8")
        run("todo", "done", "1.1", "file:docs/map.md", "the map, first version")
        (docs / "map.md").write_text("# map\n\nsummary: the map\n\nv2\n", encoding="utf-8")
        os.environ["EL_SESSION"] = "bbbb1008"
        code, out, err = run("todo", "done", "1.1", "file:docs/map.md", "the map, second version")
        self.assertEqual(code, 0, err)
        self.assertIn("1.1: this version is signed by this session — it was session aaaa1008's", out)
        self.assertIn("el todo brief 1.1", out)

    def test_the_same_session_renewing_its_own_version_is_not_told(self):
        docs = self.case / "docs"
        docs.mkdir()
        (docs / "map.md").write_text("# map\n\nsummary: the map\n\nv1\n", encoding="utf-8")
        run("todo", "done", "1.1", "file:docs/map.md", "first")
        (docs / "map.md").write_text("# map\n\nsummary: the map\n\nv2\n", encoding="utf-8")
        code, out, _ = run("todo", "done", "1.1", "file:docs/map.md", "second")
        self.assertNotIn("this version is signed by this session", out)


if __name__ == "__main__":
    unittest.main()


class AcceptanceWrittenAsText(Base):
    """The owner's word, 2026-10-08, on the live map: the rule «two hands» was lost to a README rewrite, agents rebuilt it
    as an item «acceptance of 1.1–1.3 by a clean hand, not this session» and an [owner] slot, and four fresh sessions in
    a row stopped. el names the door where acceptance is written as text."""

    def test_an_item_that_is_an_acceptance_names_the_door_last(self):
        code, out, err = run("todo", "add", "1", "приёмка 1.1 чистой рукой (не эта сессия)")
        self.assertEqual(code, 0, err)
        last = out.rstrip("\n").split("\n")[-1]
        self.assertTrue(last.startswith("acceptance written as text reads as a wall"), last)
        self.assertIn("el todo accept N.M", last)
        self.assertNotIn("this case has no rule", last, "the rule is there: the door alone")

    def test_without_the_rule_it_names_the_line_that_switches_it_on(self):
        run("readme", "drop", "context", "1")
        code, out, _ = run("todo", "add", "1", "accept 1.1 by a second hand", "--expect", "[run: probe → ok]")
        self.assertIn('el readme add context "rule: two hands', out)

    def test_an_owner_slot_for_acceptance_in_a_phase_goal_names_it_too(self):
        code, out, _ = run("phase", "plan", "2", "Next", "--goal", "maps checked [owner: приёмка чистой рукой]")
        self.assertIn("acceptance written as text reads as a wall", out)

    def test_acceptance_tests_are_not_an_acceptance(self):
        code, out, _ = run("todo", "add", "1", "acceptance tests for the parser pass", "--expect", "[run: probe → ok]")
        self.assertNotIn("acceptance written as text", out)
