"""The radio with Codex, #178 (2026-11-09): the recitation ended with `next: «…»` — a step written into State four hours
and 16 RESULTs before, a step already done and checked — while the item in hand was another one. el knew the State was
behind: Order said «State is behind», but the thread named it as a step of its own, cut before its door, and printed the
old `next:` last, as the step. The agent takes the last step of the thread. `next:` is the agent's words — el does not
judge them; it says beside them how much work landed after they were written, and the door."""
import re
import shlex
import unittest

from tests.test_commands import run
from tests.test_long_case_1105 import Base
from tests.test_recitation_1007 import Base as RecitationBase


def thread(out: str) -> str:
    return next((ln for ln in out.splitlines() if "thread: " in ln), "")


class ANextWrittenBeforeTheWorkSaysItsAge(Base):
    def setUp(self):
        super().setUp()
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")
        self.ok("todo", "add", "1", "open the shop")
        self.ok("todo", "add", "1", "count the till")
        self.ok("readme", "set", "next", "open the shop first")
        self.ok("todo", "done", "1.1", "run:probe → ok", "the shop opens")

    def test_the_thread_says_how_old_next_is_beside_it(self):
        line = thread(self.ok()[0])
        self.assertIn("next, written before 1 RESULT (as of ", line)
        self.assertIn("«open the shop first» — still the step? el readme set next", line)
        self.assertIn("still true as it stands: el readme touch", line)

    def test_state_is_behind_is_not_a_step_of_its_own_when_next_carries_it(self):
        out = self.ok()[0]
        self.assertNotIn("first: Order «State is behind", thread(out))
        self.assertIn("- State is behind: ", out, "Order keeps the line — the thread says it beside next:")

    def test_a_new_next_reads_as_now(self):
        self.ok("readme", "set", "next", "count the till")
        line = thread(self.ok()[0])
        self.assertIn("next: «count the till»", line)
        self.assertNotIn("written before", line)

    def test_the_printed_door_runs_as_printed_and_the_mark_goes(self):
        line = thread(self.ok()[0])
        door = re.search(r"still true as it stands: (el readme touch)", line).group(1)
        self.ok(*shlex.split(door)[1:])
        line = thread(self.ok()[0])
        self.assertIn("next: «open the shop first»", line)
        self.assertNotIn("written before", line)

    def test_an_acceptance_after_next_counts_too(self):
        self.ok("readme", "touch")
        code, out, err = run("todo", "accept", "1.1", "--by", "owner", "--run", "probe → ok", "seen it")
        self.assertEqual(code, 0, out + err)
        self.assertIn("next, written before 1 accepted, sent back or cancelled (as of ", thread(self.ok()[0]))

    def test_without_next_the_order_line_stays_the_first_step(self):
        self.ok("readme", "set", "next", "")
        self.ok("todo", "done", "1.2", "run:till → 40", "the till counts")
        line = thread(self.ok()[0])
        self.assertNotIn("→ next", line)
        self.assertIn("first: Order «State is behind", line)


class TheRecitationSaysItToo(RecitationBase):
    def test_the_recitation_says_the_age_of_next(self):
        run("readme", "set", "next", "probe the first step")    # 5
        run("todo", "done", "1.1", "run:probe → ok", "it answers")  # 6
        out = self.calls(4)                                      # 7..10
        line = next((ln for ln in out.splitlines() if ln.startswith("recite (every")), "")
        self.assertIn("next, written before 1 RESULT (as of ", line)
        self.assertIn("«probe the first step» — still the step?", line)


if __name__ == "__main__":
    unittest.main()
