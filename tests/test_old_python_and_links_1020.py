"""Seven reports of 2026-10-15…18, from two live code cases.

1. Three Codex reports: `el todo note N.M --edit K "text"` — the form `el help todo` prints — was refused, «unrecognized
   arguments», and the same text before `--edit` passed. Codex ran el under /usr/bin/python3 3.9; argparse before 3.13
   fills an optional positional with nothing at the first stretch of positionals, and the words after an option come
   back unrecognized. On the maintainer's 3.14 the suite was green; under 3.9, 21 tests of 1127 failed (`--edit`,
   `case new --root "name"`). Words after an option go to the optional positional the call left empty, as 3.13 does.
2. Two reports: `artifacts/report.md` says `summary: … [baseline](baseline.md)`; README copied the link as it was, from
   the case root, and check refused F16 on a file that exists. README draws a summary's links from the file's folder;
   the file, and its version under acceptance, stay as they are.
3. A proof `file:../../app/(pages)/(private)/studies/[id]/page.tsx` (a route folder): the brief printed the path cut at
   `(pages`, check named a broken link. Every pattern that reads a link's target knows one level of parentheses.
4. `el todo done …; el check` ended with check's «exit 3 = rule violation, nothing was written»: the agent read it as the
   done not written. check finds, it refuses nothing — its legend says so."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from elephant import main
from tests.test_commands import run

ROOT = Path(__file__).resolve().parent.parent
PAGE = "app/(pages)/(private)/studies/[id]/page.tsx"
NEW_ARGPARSE = argparse.ArgumentParser.parse_known_args


def old_argparse(self, args=None, namespace=None):
    """What argparse before 3.13 returns for `… --edit K "text"`: the text after the option is left over, unrecognized."""
    ns, extra = NEW_ARGPARSE(self, args, namespace)
    if "--edit" in list(args or []) and getattr(ns, "text", None):
        late = ns.text if isinstance(ns.text, list) else [ns.text]
        ns.text = [] if isinstance(ns.text, list) else ""
        extra = late + extra
    return ns, extra


class Base(unittest.TestCase):
    KEYS = ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS", "EL_CASE", "EL_RECITE")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.pop("EL_CASE", None)
        os.environ.pop("EL_TWO_HANDS", None)
        os.environ.update(EL_HINTS="0", EL_RECITE="0", EL_SESSION="old1020a", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        self.ok("case", "new", "shop", "--goal", "the shop works")
        self.ok("phase", "open", "1", "Pages", "--goal", "the pages render [run: tests]")
        self.ok("todo", "add", "1", "render the study page", "--note", "first note", "--expect", "[run: tests]")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-shop"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def ok(self, *argv):
        code, out, err = run(*argv)
        self.assertEqual(code, 0, f"{argv}: {out}{err}")
        return out, err

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class TextAfterAnOption(Base):
    def test_the_printed_note_edit_works_where_argparse_is_old(self):
        with mock.patch.object(argparse.ArgumentParser, "parse_known_args", old_argparse):
            out, _ = self.ok("todo", "note", "1.1", "--edit", "1", "rewritten note")
            self.assertIn("«rewritten note»", out)
            self.ok("phase", "note", "1", "a phase note")
            self.ok("phase", "note", "1", "--edit", "1", "the phase note, rewritten")
        self.assertIn("  - note: rewritten note", self.read("TODO.md"))
        self.assertIn("the phase note, rewritten", self.read("TODO.md"))

    def test_words_split_by_an_option_are_still_not_guessed(self):
        code, _, err = run("todo", "add", "1", "half", "--before", "1.1", "other half")
        self.assertEqual(code, 2, err)
        self.assertIn("unrecognized arguments", err)

    @unittest.skipUnless(Path("/usr/bin/python3").exists(), "no system python3 here")
    def test_under_the_system_python(self):
        ver = subprocess.run(["/usr/bin/python3", "-c", "import sys; print(sys.version_info[:2] < (3, 13))"],
                             capture_output=True, text=True).stdout.strip()
        if ver != "True":
            self.skipTest("the system python3 has the new argparse")
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        for argv in (["todo", "note", "1.1", "--edit", "1", "under the old python"],):
            p = subprocess.run(["/usr/bin/python3", str(ROOT / "elephant.py"), *argv], capture_output=True, text=True,
                               env=env, stdin=subprocess.DEVNULL)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("  - note: under the old python", self.read("TODO.md"))


class SummaryLinks(Base):
    def test_a_summary_link_is_drawn_from_the_files_folder(self):
        art = self.case / "artifacts"
        art.mkdir()
        (art / "baseline.md").write_text("# Baseline\nsummary: the numbers before\n\nbody\n", encoding="utf-8")
        report = art / "report.md"
        report.write_text("# Report\nsummary: against [baseline](baseline.md) · [the case](../README.md#state) · "
                          "[spec](https://example.org/spec)\n\nbody\n", encoding="utf-8")
        before = report.read_bytes()
        self.ok("readme", "touch")
        readme = self.read("README.md")
        self.assertIn("[report.md](artifacts/report.md) — against [baseline](artifacts/baseline.md) · "
                      "[the case](README.md#state) · [spec](https://example.org/spec)", readme)
        code, out, err = run("check")
        self.assertNotIn("F16", out + err)
        self.assertEqual(report.read_bytes(), before, "the file and its version stay as they are")


class ParenthesesInAPath(Base):
    def setUp(self):
        super().setUp()
        page = Path(self.tmp.name, PAGE)
        page.parent.mkdir(parents=True)
        page.write_text("export default function Page() {}\n", encoding="utf-8")

    def test_done_brief_accept_and_check_keep_the_path_whole(self):
        self.ok("todo", "done", "1.1", f"file:../../{PAGE}", "the page renders")
        brief, _ = self.ok("todo", "brief", "1.1")
        self.assertIn(f"file: {PAGE}  (open it)", brief)
        code, out, err = run("check")
        self.assertNotIn("F16", out + err)
        self.assertNotIn("gone", out + err)
        os.environ["EL_SESSION"] = "old1020b"
        self.ok("todo", "accept", "1.1", "--by", "subagent", "opened the page")

    def test_a_gone_page_is_named_by_its_whole_path(self):
        self.ok("todo", "done", "1.1", f"file:../../{PAGE}", "the page renders")
        Path(self.tmp.name, PAGE).unlink()
        _, out, _ = run("order")
        self.assertIn(f"broken link(s): TODO.md → ../../{PAGE}", out)  # the whole path, not `../../app/(pages`


class CheckLegend(Base):
    def test_check_does_not_say_nothing_was_written(self):
        docs = self.case / "docs"
        docs.mkdir()
        (docs / "route.md").write_text("# Route\nsummary: the route\n", encoding="utf-8")
        self.ok("readme", "add", "links", "the route: [route](docs/route.md)")
        (docs / "route.md").unlink()
        code, out, err = run("check")
        self.assertEqual(code, 3, out + err)
        self.assertIn("check refuses nothing", err)
        self.assertNotIn("nothing was written", err)
        code, _, err = run("todo", "add", "1", "word " * 30)  # a refusal of a command that writes keeps its own legend
        self.assertEqual(code, 3, err)
        self.assertIn("exit 3 = rule violation, nothing was written", err)


if __name__ == "__main__":
    unittest.main()
