"""One writer in the space at a time (L7, the owner's word 2026-10-10: «делай»). A command reads a case file, changes it
and writes it back whole; two el processes in one space both read the old TODO and the later write dropped the earlier
one's change, each told «done» — two concurrent `todo add` lost an item in 6 to 29 trials of 30."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from elephant import store
from tests.test_commands import run

EL = [sys.executable, str(Path(__file__).resolve().parents[1] / "elephant.py")]
try:
    import fcntl
except ImportError:  # no POSIX locks here: el runs unlocked, as before, and these tests have nothing to hold
    fcntl = None


@unittest.skipIf(fcntl is None, "no POSIX file locks on this system")
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS", "EL_LOCK_DIR",
                                                    "EL_LOCK_WAIT")}
        os.environ.update(EL_HINTS="0", EL_SESSION="lock1010", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          EL_TWO_HANDS="0", EL_LOCK_DIR=str(Path(self.tmp.name) / "locks"))
        run("case", "new", "space", "--goal", "x")
        run("phase", "open", "1", "Work", "--goal", "x")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-space"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def todo(self):
        return (self.case / "TODO.md").read_text(encoding="utf-8")


class ConcurrentWritersKeepEachOthersChanges(Base):
    def test_three_sessions_adding_at_once_lose_nothing(self):
        for trial in range(6):
            procs = [subprocess.Popen(EL + ["todo", "add", "1", f"item {trial}-{k}"], cwd=self.tmp.name,
                                      env=dict(os.environ, EL_SESSION=f"sess{trial}{k:03d}"),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for k in range(3)]
            for p in procs:
                self.assertEqual(p.wait(), 0)
        todo = self.todo()
        missing = [f"item {t}-{k}" for t in range(6) for k in range(3) if f"item {t}-{k}" not in todo]
        self.assertEqual(missing, [])
        self.assertEqual(run("check")[0], 0)


class AHeldLockIsWaitedForThenSaid(Base):
    def hold(self):
        path = store.space_lock_path(Path(self.tmp.name, ".cases"))
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, "a+")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        return fh

    def test_a_command_past_the_wait_is_refused_and_writes_nothing(self):
        before = self.todo()
        fh = self.hold()
        try:
            os.environ["EL_LOCK_WAIT"] = "0.3"
            code, _, err = run("todo", "add", "1", "blocked")
        finally:
            fh.close()
        self.assertEqual(code, 4)
        self.assertIn("another el command has been writing in this case space", err)
        self.assertIn("run the same command again", err)
        self.assertEqual(self.todo(), before)

    def test_the_command_goes_through_once_the_lock_is_let_go(self):
        fh = self.hold()
        fh.close()
        os.environ["EL_LOCK_WAIT"] = "0.3"
        code, _, err = run("todo", "add", "1", "after")
        self.assertEqual(code, 0, err)
        self.assertIn("1.1 after", self.todo())

    def test_each_command_lets_its_lock_go(self):
        run("todo", "add", "1", "first")
        fh = self.hold()  # would block, were the last command still holding it
        fh.close()

    def test_a_wait_that_is_not_a_number_of_seconds_is_the_default(self):
        for value in ("inf", "nan", "soon"):
            os.environ["EL_LOCK_WAIT"] = value
            code, _, err = run("todo", "add", "1", f"wait {value}")
            self.assertEqual(code, 0, err)

    def test_no_space_yet_is_no_lock_and_no_wall(self):
        with tempfile.TemporaryDirectory() as fresh:
            os.chdir(fresh)
            code, _, err = run("case", "new", "first", "--goal", "x")
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
