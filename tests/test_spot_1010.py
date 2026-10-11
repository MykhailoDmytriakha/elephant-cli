"""A spot check (the owner's word, 2026-10-10: «find what gives a leap in quality»). The leap of the day came from six
accepted digests picked at random and re-checked by another engine — none could be trusted, and forty-five acceptances
had not said so. el picks the handful, the doer cannot choose it, the journal keeps it, and the count rises."""
import os
import re
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
        os.environ.update(EL_HINTS="0", EL_SESSION="doer1010", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)
        run("case", "new", "map", "--goal", "every study in one place")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-map"))
        run("phase", "open", "1", "Digests", "--goal", "ten digests [owner]")
        run("phase", "agree", "1", "the owner agreed")

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def ten_accepted(self, by="subagent"):
        for i in range(1, 11):
            run("todo", "add", "1", f"digest {i}")
        run("todo", "done", "1.1-1.10", "owner", "written")
        os.environ["EL_SESSION"] = "acc01010"
        run("todo", "accept", "1.1-1.10", "--by", by, "numbers match")
        os.environ["EL_SESSION"] = "chk01010"

    def picked(self):
        text = (self.case / "JOURNAL.md").read_text(encoding="utf-8")
        m = re.findall(r"выборочная проверка фазы 1: ([^—]+) —", text)
        return re.findall(r"\d+\.\d+", m[0]) if m else []


class ManyAcceptedAsksForASpotCheckBeforeTheClose(Base):
    def test_the_close_line_names_the_spot_check_first(self):
        self.ten_accepted()
        order = run("order")[1]
        self.assertIn("before the close rests on its acceptances, 10 items accepted, none spot-checked", order)
        self.assertIn("el todo brief 1.1-1.10 --sample 3", order)

    def test_the_owners_word_needs_no_spot_check(self):
        self.ten_accepted(by="owner")
        self.assertNotIn("spot-checked", run("order")[1])


class ThePickIsElsAndIsKept(Base):
    def test_el_picks_records_and_prints_the_sample(self):
        self.ten_accepted()
        code, out, err = run("todo", "brief", "1.1-1.10", "--sample", "3")
        self.assertEqual(code, 0, err)
        picked = self.picked()
        self.assertEqual(len(picked), 3)
        self.assertIn(f"SPOT CHECK — el picked these 3 of 10 done items at random ({', '.join(picked)})", out)
        for ref in picked:
            self.assertIn(f"item {ref}:", out)

    def test_no_re_roll_while_the_sample_waits(self):
        self.ten_accepted()
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        first = self.picked()
        _, out, _ = run("todo", "brief", "1.1-1.10", "--sample", "3")
        self.assertIn(f"({', '.join(first)})", out)
        self.assertIn("This sample waits for its verdicts", out)
        text = (self.case / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("выборочная проверка фазы 1"), 1)


class TheVerdictsRiseAsATrustNumber(Base):
    def test_returned_and_confirmed_are_counted_on_the_entry_and_in_the_digest(self):
        self.ten_accepted()
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        a, b, c = self.picked()
        run("todo", "reopen", a, "--by", "codex", "a closed path is lost")
        run("todo", "accept", b, "--by", "codex", "holds against the sources")
        entry = run()[1]
        self.assertIn("spot check: 3 picked at random of 10 · 1 returned · 1 confirmed · 1 awaiting a verdict", entry)
        self.assertIn(f"the spot check waits for 1 verdict(s) — {c}", run("order")[1])
        run("todo", "accept", c, "--by", "codex", "holds")
        run("todo", "done", a, "owner", "rewritten")
        run("todo", "accept", a, "--by", "codex", "now holds")
        code, _, err = run("phase", "close", "1", "ten digests", "--reflect", "r", "--align", "a", "--howto", "none: t")
        self.assertEqual(code, 0, err)
        digest = next((self.case / "phases").glob("1-*.md")).read_text(encoding="utf-8")
        self.assertIn("spot check: 3 picked at random of 10 · 1 returned · 2 confirmed", digest)

    def test_a_new_sample_only_after_every_verdict(self):
        self.ten_accepted()
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        for ref in self.picked():
            run("todo", "accept", ref, "--by", "codex", "holds")
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        text = (self.case / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("выборочная проверка фазы 1"), 2)


class TheReview(Base):
    """The Codex review of batch 29, 2026-10-10: five edges of the spot check."""

    def forty(self):
        for i in range(1, 41):
            run("todo", "add", "1", f"digest {i}")
        run("todo", "done", "1.1-1.40", "owner", "written")
        os.environ["EL_SESSION"] = "acc01010"
        run("todo", "accept", "1.1-1.40", "--by", "subagent", "numbers match")
        os.environ["EL_SESSION"] = "chk01010"

    def test_1_a_long_pick_is_kept_and_long_verdicts_count(self):
        self.forty()
        run("todo", "brief", "1.1-1.40", "--sample", "40")
        run("todo", "brief", "1.1-1.40", "--sample", "2")
        text = (self.case / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("выборочная проверка фазы 1"), 1)
        run("todo", "accept", "1.1-1.40", "--by", "owner", "all forty hold")
        self.assertIn("spot check: 40 picked at random of 40 · 0 returned · 40 confirmed", run()[1])

    def test_2_a_returned_pick_does_not_block_the_rest(self):
        self.ten_accepted()
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        a, b, c = self.picked()
        run("todo", "reopen", a, "--by", "codex", "missing sources")
        code, out, err = run("todo", "brief", "1.1-1.10", "--sample", "3")
        self.assertEqual(code, 0, err)
        self.assertIn(f"item {b}:", out)
        self.assertNotIn(f"item {a}:", out)

    def test_3_a_cancelled_pick_is_resolved(self):
        self.ten_accepted()
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        a, b, c = self.picked()
        run("todo", "cancel", a, "out of scope")
        run("todo", "accept", b, "--by", "codex", "holds")
        run("todo", "accept", c, "--by", "codex", "holds")
        self.assertIn("· 2 confirmed · 1 cancelled", run()[1])
        self.assertNotIn("awaiting a verdict", run()[1])

    def test_4_the_doers_correction_is_no_spot_return(self):
        self.ten_accepted()
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        a, b, c = self.picked()
        os.environ["EL_SESSION"] = "doer1010"
        run("todo", "reopen", a, "--by", "codex", "my own fix")
        os.environ["EL_SESSION"] = "chk01010"
        self.assertIn("0 returned", run()[1])

    def test_5_a_spot_check_picks_items_not_sub_items(self):
        self.ten_accepted()
        run("todo", "add", "1.1", "a step")
        run("todo", "done", "1.1.1", "owner", "stepped")
        code, out, err = run("todo", "brief", "1.1-1.10", "--sample", "10")
        self.assertEqual(code, 0, err)
        self.assertNotIn("1.1.1", self.picked())
        self.assertEqual(len(self.picked()), 10)

    def test_6_a_plain_reopen_by_the_doer_is_no_return(self):
        self.ten_accepted()
        run("todo", "brief", "1.1-1.10", "--sample", "3")
        a = self.picked()[0]
        os.environ["EL_SESSION"] = "doer1010"
        run("todo", "reopen", a, "my own fix")
        os.environ["EL_SESSION"] = "chk01010"
        self.assertIn("0 returned", run()[1])

    def test_7_a_pick_back_in_work_names_its_done_not_an_empty_range(self):
        run("todo", "add", "1", "only one")
        run("todo", "done", "1.1", "owner", "written")
        run("todo", "brief", "1.1", "--sample", "1")
        os.environ["EL_SESSION"] = "doer1010"
        run("todo", "reopen", "1.1", "--by", "codex", "my own correction")
        order = run("order")[1]
        self.assertNotIn("el todo brief  --sample", order)
        self.assertIn("the doer ends it first: el todo done 1.1", order)


if __name__ == "__main__":
    unittest.main()
