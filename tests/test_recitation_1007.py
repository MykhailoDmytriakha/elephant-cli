"""The owner's idea, 2026-10-07: «what if a command were called every 10 calls?» — el recites where the agent stands.

The polygon measured the need: in 17 of 35 sessions an agent made ten and more el calls in a row without ticking
anything, and 14 sessions ended without State. The field agrees (the world survey, convergence 6: Manus rewrites its
todo at every step and recites it at the end of the context, or the model loses the goal within ~50 calls). el said
where the agent stands on entry only; now every 10 calls of a session the next command on the case says it again."""
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
        self.saved = {k: os.environ.get(k) for k in ("EL_RECITE", "EL_HINTS", "EL_SESSION", "EL_HANDS_DIR")}
        os.environ.update(EL_RECITE="1", EL_HINTS="0", EL_SESSION="recite1007",
                          EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "recite test", "--goal", "g")                                  # 1
        run("phase", "open", "1", "Probe", "--goal", "the probe answers [run: probe → ok]")  # 2
        run("todo", "add", "1", "first step", "--expect", "[run: probe → ok]")              # 3
        run("todo", "add", "1", "second step", "--expect", "[run: probe → ok]")             # 4

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def calls(self, n):
        out = ""
        for _ in range(n):
            out = run("todo", "show", "1.1")[1]
        return out


class EveryTenCallsElSaysWhereYouAre(Base):
    def test_the_tenth_call_recites_the_ninth_does_not(self):
        out9 = self.calls(5)                      # calls 5..9
        self.assertNotIn("recite", out9)
        out10 = self.calls(1)                     # call 10
        self.assertIn("recite (every 10 el calls): thread: goal «g» → phase 1 Probe", out10)
        self.assertIn("no done yet this session — 10 el call(s) · open in phase 1: 1.1, 1.2", out10)
        self.assertIn('finished one? el todo done 1.1 <kind> "…"', out10)

    def test_it_recites_once_per_ten_not_on_every_call_after(self):
        self.calls(6)
        self.assertNotIn("recite", self.calls(1), "call 11 is quiet after the recitation at 10")

    def test_a_done_resets_the_count_since_the_last_done(self):
        self.calls(4)                              # calls 5..8
        code, _, err = run("todo", "done", "1.1", "run:probe → ok", "it answers")   # 9
        self.assertEqual(code, 0, err)
        out = self.calls(1)                        # 10
        self.assertIn("since your last done — 1 el call(s)", out)
        self.assertIn("open in phase 1: 1.2", out)

    def test_the_entry_and_help_count_but_do_not_recite(self):
        self.calls(5)                              # calls 5..9
        code, out, _ = run("help", "start")        # 10: counted, not recited
        self.assertNotIn("recite (every 10 el calls)", out)
        self.assertIn("recite (every 10 el calls)", self.calls(1), "the next command on the case says it")

    def test_switched_off_it_is_quiet(self):
        os.environ["EL_RECITE"] = "0"
        self.assertNotIn("recite", self.calls(8))


class NoSessionNoCount(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        for k in ("EL_SESSION", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "EL_CASE"):
            os.environ.pop(k, None)
        os.environ["EL_RECITE"] = "1"
        run("case", "new", "no session", "--goal", "g")
        run("phase", "open", "1", "Probe", "--goal", "x [run: y]")
        run("todo", "add", "1", "a step", "--expect", "[run: y]")

    def tearDown(self):
        os.environ["EL_RECITE"] = "0"
        os.chdir(self.old)
        self.tmp.cleanup()

    def test_without_a_session_nothing_is_counted_or_recited(self):
        out = "".join(run("todo", "show", "1.1")[1] for _ in range(12))
        self.assertNotIn("recite", out)


if __name__ == "__main__":
    unittest.main()
