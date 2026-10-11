"""Walls of a live run (the polygon, 2026-10-10, phase 2 of a knowledge map: a fresh Sonnet re-checks 41 digests) and one
report of the same day. Each class keeps one form of failure."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

SHARED = " ".join(f"the run measured walls and entries and acceptance step {i} of the scenario" for i in range(30))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="wall1010", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"), EL_TWO_HANDS="0")
        run("case", "new", "map", "--goal", "every study in one place")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-map"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class AClosedSpaceNamesTheDoorToContinue(Base):
    """`el` in a space whose every case is closed said «nothing to pick up» with `case list` and `case new` — the agent
    took eight calls to find that a closed case takes a new phase."""

    def test_the_refusal_names_a_new_phase_in_the_top_case(self):
        run("phase", "open", "1", "Structure", "--goal", "x")
        run("todo", "add", "1", "lay it out")
        run("todo", "done", "1.1", "owner", "laid out")
        run("phase", "close", "1", "laid out", "--reflect", "r", "--align", "a", "--howto", "none: t")
        run("done", "the map stands")
        os.environ["EL_SESSION"] = "fresh101"
        code, out, err = run()
        self.assertEqual(code, 4)
        self.assertIn(f"el --case {self.case.name} phase plan N", out + err)


class AMissingItemNamesTheNumbersThePhaseHolds(Base):
    """`todo add 2 …` printed 2.7 (2.1–2.6 were taken before); the agent's `done 2.1` met «no item 2.1 in TODO.md»."""

    def test_the_refusal_lists_the_items(self):
        run("phase", "open", "1", "Work", "--goal", "x")
        for text in ("a", "b", "c"):
            run("todo", "add", "1", text)
        run("todo", "drop", "1.1")
        code, _, err = run("todo", "done", "1.1", "owner", "x")
        self.assertEqual(code, 4)
        self.assertIn("no item 1.1 in phase 1 (items: 1.2–1.3)", err)

    def test_a_missing_phase_is_named_as_such(self):
        run("phase", "open", "1", "Work", "--goal", "x")
        _, _, err = run("todo", "done", "7.1", "owner", "x")
        self.assertIn("there is no phase 7 (phases: 1)", err)


class ARefusedPocketSaysTheItemWasNotAdded(Base):
    """Forty adds refused on a 164-char note; the agent's recipe recorded «todo add silently creates no items»."""

    def test_the_first_line_says_nothing_added(self):
        run("phase", "open", "1", "Work", "--goal", "x")
        code, _, err = run("todo", "add", "1", "re-check the digest", "--note", "x" * 170)
        self.assertEqual(code, 3)
        first = next(ln for ln in err.split("\n") if ln.startswith("el: ERROR"))
        self.assertIn("nothing added — the item «re-check the digest» is refused with its pocket: note:", first)


class TwoRelatedFilesAreNotADuplicate(Base):
    """Two honest reports of two runs share their generated sections; the Order line said «say the difference in each
    summary», and only merging them closed it (feedback 2026-10-10)."""

    def write(self, name, body):
        (self.case / "reports").mkdir(exist_ok=True)
        (self.case / "reports" / name).write_text(f"# {name}\n\nsummary: {name}\n\n{body}\n", encoding="utf-8")

    def order(self):
        return run("order")[1]

    def test_a_link_from_one_to_the_other_closes_the_line(self):
        self.write("run-1.md", SHARED)
        self.write("run-2.md", SHARED + " and more")
        self.assertIn("run-1.md ≈ reports/run-2.md", self.order())
        self.assertIn("link one from the other", self.order())
        self.write("run-2.md", "Second run over [run 1](run-1.md): what differs is the acceptance. " + SHARED + " and more")
        self.assertNotIn("≈", self.order())


class AReturnConditionIsTheSources(Base):
    """The re-audit of a knowledge map, 2026-10-10: asked for «the condition for returning to each», a rewriter supplied
    conditions the source never gave. The acceptor's protocol says: as the source states it, none stated is «not stated»."""

    def test_the_document_protocol_forbids_a_supplied_condition(self):
        (self.case / "docs").mkdir()
        (self.case / "docs" / "digest.md").write_text("# Digest\nsummary: x\n", encoding="utf-8")
        run("phase", "open", "1", "Digest", "--goal", "x [file: docs/digest.md]")
        run("todo", "add", "1", "sum up", "--expect", "[file: docs/digest.md]")
        run("todo", "done", "1.1", "file:docs/digest.md", "summed up")
        os.environ["EL_SESSION"] = "other101"
        out = run("todo", "brief", "1.1")[1]
        self.assertIn("as the source states it — none stated is «not stated», never one supplied", out)
        self.assertIn("a return condition or a status the source never gave is that too", out)


if __name__ == "__main__":
    unittest.main()
