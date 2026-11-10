"""The radio with Codex, #209 (2026-11-10): `el readme show | head` on a long case printed a Python traceback —
BrokenPipeError at the last print of the command. Agents read el from one end (`head -60`, `grep -q`), so a reader
that leaves early is the ordinary way to read, not an edge. Worse than the noise: el took the closed pipe for a crash
of the command and rolled back what the command had written, while the pipeline answered with the reader's exit 0 —
a write that vanished in silence. The receipt is not the record: a reader that left means nobody read the rest; the
command's work and its exit code stay its own."""
import argparse
import contextlib
import errno
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from elephant import main
from tests.test_commands import run
from tests.test_long_case_1105 import Base

EL = [sys.executable, str(Path(__file__).resolve().parents[1] / "elephant.py")]


class Gone(io.StringIO):
    """A pipe whose reader left (`| head` after its lines, `grep -q` after its match): every write is refused."""

    def write(self, text):
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(errno.EPIPE, "Broken pipe")


def run_gone(*argv, out_gone=True, err_gone=False):
    out = Gone() if out_gone else io.StringIO()
    err = Gone() if err_gone else io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        return main.run(list(argv))


class AReaderThatLeftDoesNotUndoTheWrite(Base):
    def setUp(self):
        super().setUp()
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")

    def test_a_write_whose_receipt_nobody_reads_stays_written(self):
        self.assertEqual(run_gone("todo", "add", "1", "count the till"), 0)
        self.assertIn("count the till", self.read("TODO.md"))
        self.assertEqual(run("check")[0], 0)

    def test_a_done_stays_done(self):
        self.ok("todo", "add", "1", "count the till")
        self.assertEqual(run_gone("todo", "done", "1.1", "run:probe → ok", "the till counted"), 0)
        self.assertIn("the till counted", self.read("JOURNAL.md"))

    def test_a_look_ends_quietly_with_its_own_code(self):
        self.assertEqual(run_gone("readme", "show"), 0)
        self.assertEqual(run_gone("todo"), 0)
        self.assertEqual(run_gone(), 0)

    def test_a_refusal_keeps_its_code_when_its_reader_left(self):
        code = run("todo", "done", "9.9", "run:probe → ok", "nothing")[0]
        self.assertNotEqual(code, 0)
        self.assertEqual(run_gone("todo", "done", "9.9", "run:probe → ok", "nothing", out_gone=True, err_gone=True), code)

    def test_the_streams_are_given_back(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            main.run(["todo"])
            self.assertIs(sys.stdout, out)
            self.assertIs(sys.stderr, err)


class AClosedPipeIsQuietInARealProcess(Base):
    """What a test stream cannot show: the interpreter flushes stdout at exit, and a closed pipe there printed
    «Exception ignored … BrokenPipeError» with exit 120 — after the command had already succeeded."""

    def el(self, *argv):
        p = subprocess.Popen(EL + list(argv), cwd=self.tmp.name, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.stdout.close()  # the reader left before el said a word
        err = p.stderr.read().decode("utf-8", "replace")
        p.stderr.close()
        return p.wait(), err

    def test_a_look_into_a_closed_pipe(self):
        code, err = self.el("help", "practice")
        self.assertNotIn("BrokenPipeError", err)
        self.assertNotIn("Exception ignored", err)
        self.assertEqual(code, 0, err)

    def test_a_write_into_a_closed_pipe(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")
        code, err = self.el("todo", "add", "1", "count the till")
        self.assertNotIn("BrokenPipeError", err)
        self.assertEqual(code, 0, err)
        self.assertIn("count the till", self.read("TODO.md"))


def print_message_39(parser, message, file=None):
    """argparse of Python 3.9 — the one another agent runs el under — writes without a guard; newer ones swallow."""
    if message:
        if file is None:
            file = sys.stderr
        file.write(message)


class AStreamClosedBeforeElStarted(Base):
    """The second hand, 2026-11-10: `el --help 1>&- 2>&-` under Python 3.9 exited 1 instead of 0 — a stream closed
    before the start is None in Python, and argparse of 3.9 wrote into it. Its writer is emulated here, so the test is
    red on the old code under any Python; the real process below is red under 3.9."""

    def test_help_into_closed_streams_ends_with_zero(self):
        with mock.patch.object(argparse.ArgumentParser, "_print_message", print_message_39), \
                contextlib.redirect_stdout(None), contextlib.redirect_stderr(None):
            with self.assertRaises(SystemExit) as caught:
                main.run(["--help"])
        self.assertIn(caught.exception.code, (0, None))

    def test_a_write_with_closed_streams_stays_written(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")
        with contextlib.redirect_stdout(None), contextlib.redirect_stderr(None):
            self.assertEqual(main.run(["todo", "add", "1", "count the till"]), 0)
        self.assertIn("count the till", self.read("TODO.md"))

    def test_a_real_process_with_both_streams_closed(self):
        closed = ["sh", "-c", 'exec "$@" 1>&- 2>&-', "sh"]
        self.assertEqual(subprocess.call(closed + EL + ["--help"], cwd=self.tmp.name), 0)
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")
        self.assertEqual(subprocess.call(closed + EL + ["todo", "add", "1", "count the till"], cwd=self.tmp.name), 0)
        self.assertIn("count the till", self.read("TODO.md"))


if __name__ == "__main__":
    unittest.main()
