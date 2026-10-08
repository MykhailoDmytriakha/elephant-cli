"""A Codex peer review of batch 20 before commit (2026-10-08): seven findings, each reproduced, each a form of failure
kept here."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp
from tests.test_commands import run

README = """# probe

## Context
{context}

## State
- next: go

## Decisions
{decisions}
## Problems

## Links
{links}
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="codex20", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          EL_TWO_HANDS="0")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def case(self, name):
        return next(Path(self.tmp.name, ".cases").glob(f"*-{name}"))

    def write(self, context, decisions="", links=""):
        src = Path(self.tmp.name) / "readme-in.md"
        src.write_text(README.format(context=context, decisions=decisions, links=links), encoding="utf-8")
        return run("readme", "--file", str(src))


class AnUnreadableSiblingNeverBreaksTheEntry(Base):
    def test_a_legacy_readme_in_bytes_is_skipped(self):
        run("case", "new", "old notes", "--goal", "g")
        old = self.case("old-notes") / "README.md"
        old.write_bytes(old.read_bytes() + b"\xff\xfe broken bytes\n")
        run("case", "new", "probe", "--goal", "g")
        code, out, err = run("--case", "probe")
        self.assertEqual(code, 0, err)
        code, out, err = run("case", "new", "next", "--goal", "g")
        self.assertEqual(code, 0, err)


class TheDrawnStartIsNotTheAgentsText(Base):
    def test_a_readme_at_its_limit_takes_the_next_write(self):
        run("case", "new", "probe", "--goal", "g")
        body, _ = stamp.split(self.case("probe").joinpath("README.md").read_text(encoding="utf-8"))
        parsed = grammar.parse_readme(body)
        own = parsed.lines - parsed.rendered_lines - 1  # the `opened:` line is el's
        filler = "".join(f"- d{k}\n" for k in range(grammar.README_MAX_LINES - own))
        full = body.replace("## Decisions\n", "## Decisions\n" + filler, 1)
        self.assertEqual([f for f in grammar.parse_readme(full).errors if f.rule == "F2"], [])
        typed = full.replace("- opened: ", "- started: ")  # the same line typed by the agent counts
        self.assertTrue([f for f in grammar.parse_readme(typed).errors if f.rule == "F2"])


class APrintedCommandKeepsTheFileWhole(Base):
    def test_a_path_with_a_shell_sign_is_quoted(self):
        run("case", "new", "research", "--goal", "g")
        docs = self.case("research") / "docs"
        docs.mkdir()
        (docs / "q&a.md").write_text("# qa\nsummary: answers\n", encoding="utf-8")
        run("--case", "research", "readme", "add", "context", "knowledge: [qa](docs/q&a.md)")
        code, out, _ = run()
        self.assertIn(f"cat '.cases/{self.case('research').name}/docs/q&a.md'", out)
        code, out, _ = run("facts")
        self.assertIn("— cat '.cases/", out)

    def test_a_plain_path_stays_bare(self):
        run("case", "new", "research", "--goal", "g")
        docs = self.case("research") / "docs"
        docs.mkdir()
        (docs / "doors.md").write_text("# d\nsummary: closed paths\n", encoding="utf-8")
        run("--case", "research", "readme", "add", "context", "knowledge: [doors.md](docs/doors.md)")
        code, out, _ = run()
        self.assertIn(f"cat .cases/{self.case('research').name}/docs/doors.md", out)


class AGoalRewrittenPastItsStartIsSeen(Base):
    def test_the_whole_opening_goal_is_compared(self):
        start = "x" * 121
        run("case", "new", "probe", "--goal", start + " ORIGINAL")
        self.write(start + " DIFFERENT")
        text = self.case("probe").joinpath("README.md").read_text(encoding="utf-8")
        self.assertIn(f"- opened: ", text)
        self.assertIn("the goal then: «" + start + " ORIGINAL»", text)


class TheNewestFactsAreTheNewest(Base):
    def test_a_fact_finished_last_shows_first(self):
        run("case", "new", "probe", "--goal", "g")
        run("phase", "open", "1", "Probe", "--goal", "probe")
        for k in range(1, 10):
            run("todo", "add", "1", f"step {k}")
        for k in range(2, 10):
            run("todo", "done", "1.%d" % k, "run:probe → ok", f"step {k} done", "--fact", f"fact {k}")
        run("todo", "done", "1.1", "run:probe → ok", "step 1 done", "--fact", "the newest fact")
        code, out, _ = run()
        head = out.split("— the case on disk")[0]
        shown = [ln.strip() for ln in head.split("\n") if ln.startswith("  ✓ ")]
        self.assertEqual(shown[0], "✓ 1.1 the newest fact", shown)


class RootModeOffersFromItsListedFolders(Base):
    def test_a_listed_folder_in_root_mode_is_a_candidate(self):
        run("case", "new", "--root", "app", "--goal", "the app")
        (Path(self.tmp.name) / "measurements").mkdir()
        (Path(self.tmp.name) / "measurements" / "result.md").write_text("# r\nsummary: measured things\n", encoding="utf-8")
        run("readme", "add", "links", "measurements/ — measured things")
        run("phase", "open", "1", "Work", "--goal", "w")
        run("todo", "add", "1", "measure")
        run("todo", "done", "1.1", "run:measure → ok", "measured")
        code, out, err = run("phase", "close", "1", "measured", "--reflect", "r", "--align", "a", "--howto", "none: nothing")
        self.assertEqual(code, 0, err)
        self.assertIn("measurements/result.md", out)


class TheSummaryIsReadAsLinksReadsIt(Base):
    def test_a_summary_on_line_five_is_named(self):
        run("case", "new", "research", "--goal", "g")
        docs = self.case("research") / "docs"
        docs.mkdir()
        (docs / "doors.md").write_text("# d\n\n> a quote\n\nsummary: closed paths, line five\n", encoding="utf-8")
        run("--case", "research", "readme", "add", "context", "knowledge: [doors.md](docs/doors.md)")
        code, out, _ = run()
        self.assertIn("closed paths, line five", out.split("— the case on disk")[0])


if __name__ == "__main__":
    unittest.main()
