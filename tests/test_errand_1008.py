"""Six reports of one live session, 2026-10-08: an agent ran an errand for the owner (a parcel delivered to the wrong door)
in a root-mode case and wrote el feedback as it went. Each class keeps one form of failure."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

RULE = "rule: two hands — the owner agrees each phase's scope, a fresh session accepts each done item"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS", "EL_MODEL")}
        os.environ.update(EL_HINTS="0", EL_SESSION="errand01", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)
        os.environ.pop("EL_MODEL", None)

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def new_case(self):
        run("case", "new", "errand", "--goal", "the parcel is in hand")
        return next(Path(self.tmp.name, ".cases").glob("*-errand"))


class TheSameLineIsNotAddedTwice(Base):
    """`case new --root` wrote the rule line without saying so; the agent added it again, el said «line added»."""

    def test_root_mode_says_the_rule_it_wrote(self):
        code, out, err = run("case", "new", "--root", "errand", "--goal", "the parcel is in hand")
        self.assertEqual(code, 0, err)
        self.assertIn("this case asks two hands", out)

    def test_an_exact_duplicate_is_named_not_written(self):
        run("case", "new", "--root", "errand", "--goal", "the parcel is in hand")
        code, out, err = run("readme", "add", "context", RULE)
        self.assertEqual(code, 0, err)
        self.assertIn("README Context: line 1 says this already — nothing changed", out)
        readme = (Path(self.tmp.name) / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count(RULE), 1)

    def test_a_different_line_is_still_added(self):
        case = self.new_case()
        run("readme", "add", "decisions", "2026-10-08 · we wait for the carrier")
        code, out, _ = run("readme", "add", "decisions", "2026-10-08 · we call the sender")
        self.assertIn("line added", out)
        self.assertIn("we call the sender", (case / "README.md").read_text(encoding="utf-8"))


class HelpKnowsTheFirstWord(Base):
    def test_init_and_new_lead_to_cases(self):
        for word in ("init", "new"):
            code, out, err = run("help", word)
            self.assertEqual(code, 0, err)
            self.assertIn("el case new", out)


class TheResultsWordsAreTheFact(Base):
    """`--fact =` at done recorded a literal «=» as an established fact; `el todo fact N.M =` took the result's words."""

    def test_equals_at_done_takes_the_outcome(self):
        case = self.new_case()
        run("phase", "open", "1", "Find", "--goal", "find it")
        run("todo", "add", "1", "walk the doors", "--fact", "where it lies")
        code, out, err = run("todo", "done", "1.1", "owner", "it lies at the neighbours", "--fact", "=")
        self.assertEqual(code, 0, err)
        self.assertIn("fact 1.1: «it lies at the neighbours»", out)
        self.assertIn("- fact: it lies at the neighbours", (case / "TODO.md").read_text(encoding="utf-8"))
        self.assertNotIn("«=»", out)


class ASubagentIsNotItsParentsMind(Base):
    """A subagent on another model accepted, and the line said «same model: … Opus»: it shares the session's signature."""

    def setUp(self):
        super().setUp()
        self.case = self.new_case()
        run("sign", "Opus 5.5", "--as", "Anthropic Claude Code")
        run("phase", "open", "1", "Find", "--goal", "find it")
        run("todo", "add", "1", "read the order letter")
        run("todo", "done", "1.1", "owner", "the order number is found")

    def accepted(self):
        return next(ln for ln in (self.case / "TODO.md").read_text(encoding="utf-8").split("\n") if "accepted:" in ln)

    def test_unnamed_model_is_not_the_parents(self):
        code, out, err = run("todo", "accept", "1.1", "--by", "subagent", "opened the letter")
        self.assertEqual(code, 0, err)
        self.assertIn("model not given", self.accepted())
        self.assertNotIn("Opus 5.5", self.accepted())
        self.assertIn("EL_MODEL='<your model>'", out)

    def test_a_model_said_on_the_call_is_recorded(self):
        os.environ["EL_MODEL"] = "Sonnet 5.5"
        code, _, err = run("todo", "accept", "1.1", "--by", "subagent", "opened the letter")
        self.assertEqual(code, 0, err)
        self.assertIn("another model", self.accepted())
        self.assertIn("Sonnet 5.5", self.accepted())

    def test_the_brief_tells_the_subagent_to_name_its_model(self):
        code, out, _ = run("todo", "brief", "1.1")
        self.assertIn("EL_MODEL='<your model>'", out)


class TheDoersOwnReopenIsNoReturn(Base):
    """The doer swapped its own markdown proof for screenshots (`reopen --by claude`); the entry said «returned by an acceptor 1»."""

    def setUp(self):
        super().setUp()
        self.case = self.new_case()
        run("phase", "open", "1", "Find", "--goal", "find it")
        run("todo", "add", "1", "read the order letter")
        run("todo", "add", "1", "walk the doors")
        run("todo", "done", "1.1", "owner", "found")

    def test_same_session_reopen_is_a_correction(self):
        code, out, err = run("todo", "reopen", "1.1", "--by", "claude", "swap the proof for the screenshot")
        self.assertEqual(code, 0, err)
        self.assertIn("a correction, not an acceptor's return", out)
        self.assertNotIn("returned by an acceptor", run()[1])

    def test_another_sessions_reopen_still_counts(self):
        os.environ["EL_SESSION"] = "errand02"
        run("todo", "reopen", "1.1", "--by", "claude", "the screenshot shows another order")
        self.assertIn("returned by an acceptor 1", run()[1])


class TheSameWordsAreOneCommandAway(Base):
    """The goal promised [file: photo], the item expected [file: photo of the parcel in hand]: el said «0 have an item»."""

    def setUp(self):
        super().setUp()
        self.case = self.new_case()
        run("phase", "plan", "1", "Find", "--goal", "boots in hand [file: photo]; shoes move [ref: tracking]")
        run("todo", "add", "1", "walk the doors", "--expect", "[file: photo of the parcel in hand]")
        run("phase", "agree", "1", "the owner agreed")

    def test_the_hint_names_the_pair_and_the_command(self):
        os.environ["EL_HINTS"] = "1"
        code, out, err = run("phase", "open", "1")
        self.assertEqual(code, 0, err)
        hint = next(ln for ln in out.split("\n") if ln.startswith("hint:"))
        self.assertIn("1.1 expects [file: photo of the parcel in hand]", hint)
        self.assertIn("el todo expect 1.1 '[file: photo]'", hint)
        self.assertIn('[ref: tracking] has no item: el todo add 1 "…" --expect "[ref: tracking]"', hint)

    def test_the_printed_command_closes_the_order_line(self):
        run("phase", "open", "1")
        line = next(ln for ln in run()[1].split("\n") if "promises [file: photo]" in ln)
        self.assertIn("in these words — 1.1 expects", line)
        code, _, err = run("todo", "expect", "1.1", "[file: photo]")
        self.assertEqual(code, 0, err)
        self.assertNotIn("promises [file: photo]", run()[1])


class TheCasesWordsAboutKnowledgeReachTheEntry(Base):
    """The owner's yes, 2026-10-08, after an audit of a knowledge map: «a pointer, not a substitute for the sources» was
    written on the map's knowledge line — and the entry of every case showed the file's own summary, without it."""

    def setUp(self):
        super().setUp()
        self.case = self.new_case()
        (self.case / "docs").mkdir()
        (self.case / "docs" / "map.md").write_text("# Map\nsummary: every closed path with its number\n", encoding="utf-8")

    def knowledge(self):
        return next(ln for ln in run()[1].split("\n") if ln.startswith("knowledge:"))

    def test_the_lines_words_come_first(self):
        run("readme", "add", "context", "knowledge: [map.md](docs/map.md) — a pointer, not a substitute: check the source")
        line = self.knowledge()
        self.assertIn("a pointer, not a substitute: check the source", line)
        self.assertNotIn("every closed path with its number", line)

    def test_a_bare_line_falls_back_to_the_files_summary(self):
        run("readme", "add", "context", "knowledge: [map.md](docs/map.md)")
        self.assertIn("every closed path with its number", self.knowledge())


if __name__ == "__main__":
    unittest.main()
