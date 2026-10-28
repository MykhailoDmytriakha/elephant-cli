"""The pool of 2026-10-20…28: el's own lines — counted as the agent's, kept as the agent's, printed where they lead nowhere.

1. Found measuring a live case, 2026-10-28 (no agent reported it — they read the entry with `head`): a folder named
   `(pages)` or `[id]` — a route folder of a web app — was read back as the agent's line of Links, kept, and drawn again
   under it; every README write added the tree once more: 985 copies, a 7 MB README, 15 s an entry.
2. Two live reports, 2026-10-27 and 10-28: 194 closed phases took the 200 lines of TODO, and a done of the open phase was
   refused F4. The line of a closed phase is el's — written by close, one line, no door shortens it — not the agent's text.
   A third report, 2026-10-21: a TODO at 200 lines of the agent's own items, the done asked for a `to re-run:` note six
   times and six notes were refused; the F4 refusal named no way out.
3. A wall report, 2026-10-27: «phase plan answered only `exit 3 = rule violation, nothing was written`» — the limit stood
   on the first line, the agent read the last. A refusal ends with its own last line, never the legend.
4. A wall report, 2026-10-21: the close said «name the criterion as an item» over 1.5, done with file:report.md; the new
   item was then named a duplicate of 1.5. The close and Order name the done item whose file proof is the promised file.
5. A report, 2026-10-23: a second done with a new proof and a caption replaced the item's result; the brief read the caption
   as what came out. A new proof keeps the result; its words go to the journal with it.
6. A wall report, 2026-10-26: «972 chars, about 980 fit» — refused under its own number. And a report, 2026-10-27: a close
   sent with «x» to check the gates closed the phase; no door said its result again — the same close restates it.
7. A Codex session, 2026-10-15…21: `el next`, `el goal`, `el list`, `el phaseclose -h` met the list of commands; a subagent
   named itself `--by cart_retry_42_final_acceptance` six times. Each word gets its door, the name goes into the verdict."""
import os
import re
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp, store
from tests.test_commands import run

ENVS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_THREAD_ID", "COPILOT_AGENT",
        "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "EL_MODEL", "EL_SESSION", "EL_HANDS_DIR", "EL_HINTS", "EL_TWO_HANDS",
        "EL_CASE", "EL_RECITE")


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS="0", EL_RECITE="0", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          CLAUDECODE="1", EL_SESSION="doer1028")
        self.ok("case", "new", "shop", "--goal", "the shop works")

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

    def case(self) -> Path:
        return next(Path(self.tmp.name, ".cases").glob("*-shop"))

    def read(self, name: str) -> str:
        return (self.case() / name).read_text(encoding="utf-8")


class RouteFolders(Base):
    def test_a_folder_with_brackets_is_drawn_once_however_many_writes(self):
        deep = self.case() / "artifacts" / "app" / "(pages)" / "(private)" / "my notes" / "[id]"
        deep.mkdir(parents=True)
        (deep / "page.tsx").write_text("x\n", encoding="utf-8")
        (deep.parent / "b.md").write_text("# b\nsummary: the notes page\n", encoding="utf-8")
        sizes = []
        for _ in range(3):
            self.ok("readme", "set", "next", "look at the route")
            sizes.append(len(self.read("README.md").split("\n")))
        self.assertEqual(len(set(sizes)), 1, f"README grew on each write: {sizes}")
        links = self.read("README.md").split("## Links", 1)[1]
        self.assertEqual(links.count("- artifacts/app/(pages)/(private)/my notes/[id]/"), 1, links)
        self.assertIn("[b.md](artifacts/app/(pages)/(private)/my notes/b.md) — the notes page", links)

    def test_copies_an_older_el_left_are_folded_on_the_next_write(self):
        deep = self.case() / "artifacts" / "app" / "(pages)"
        deep.mkdir(parents=True)
        (deep / "page.tsx").write_text("x\n", encoding="utf-8")
        self.ok("readme", "set", "next", "one")
        body, _ = stamp.split(self.read("README.md"))
        head, links = body.split("## Links\n", 1)
        stale = "    - artifacts/app/(pages)/\n" * 5  # what 1.71.0 kept as the agent's lines, write after write
        store.write(self.case(), "README.md", head + "## Links\n" + stale + links)
        self.ok("readme", "set", "next", "two")
        links = self.read("README.md").split("## Links", 1)[1]
        self.assertEqual(links.count("artifacts/app/(pages)/"), 1, links)


    def test_a_folder_gone_without_el_takes_its_drawn_line_along(self):
        gone = self.case() / "artifacts" / "export" / "all_kinds"
        gone.mkdir(parents=True)
        (gone / "data.bin").write_bytes(b"x")
        self.ok("readme", "set", "next", "one")
        self.assertIn("- artifacts/export/all_kinds/", self.read("README.md"))
        (gone / "data.bin").unlink()
        gone.rmdir()
        self.ok("readme", "set", "next", "two")
        self.assertNotIn("all_kinds", self.read("README.md"), "a gone folder's line is el's drawing, not the agent's line")


    def test_a_nested_line_of_the_agent_that_ends_in_a_slash_stays(self):
        (self.case() / "docs").mkdir()
        (self.case() / "docs" / "a.md").write_text("# a\nsummary: a note\n", encoding="utf-8")
        self.ok("readme", "set", "next", "one")
        body, _ = stamp.split(self.read("README.md"))
        head, links = body.split("## Links\n", 1)
        store.write(self.case(), "README.md", head + "## Links\n- the outside world\n  - see the shared drive: team/specs/\n" + links)
        self.ok("readme", "set", "next", "two")
        self.assertIn("  - see the shared drive: team/specs/", self.read("README.md"), "prose, not a folder el drew")


class ClosedPhaseHistory(Base):
    def _history(self, closed: int):
        """A case with `closed` phases closed — written as el writes them, without 4×closed commands."""
        ph = self.case() / "phases"
        ph.mkdir(exist_ok=True)
        lines = ["# TODO — shop", ""]
        for n in range(1, closed + 1):
            (ph / f"{n}-step.md").write_text(f"# Phase {n} — Step\ngoal: step {n}\nresult: done {n}\n", encoding="utf-8")
            lines.append(f"- [x] {n} Step — done {n} · acceptance: 1 of 1 done accepted — the owner's word 1 · 2026-10-27 · "
                         f"[phases/{n}-step.md](phases/{n}-step.md)")
        store.write(self.case(), "TODO.md", "\n".join(lines) + "\n")
        for argv in (("RESULT", f"done {closed}"), ("DECISION", "reflect: r"), ("DECISION", "align: a")):
            self.ok("log", "--phase", str(closed), *argv)

    def _full(self, items: int = 98):
        """Phase 1 open with `items` items, each with its why: 3 + 2 × items lines of the agent's text."""
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        body, _ = stamp.split(self.read("TODO.md"))
        body = body.rstrip("\n") + "\n" + "".join(f"  - [ ] 1.{m} item {m}\n    - why: why {m}\n" for m in range(1, items + 1))
        store.write(self.case(), "TODO.md", body)

    def test_220_closed_phases_leave_the_open_one_its_two_hundred_lines(self):
        self._history(220)
        self.ok("phase", "open", "221", "Work", "--goal", "the work is done")
        self.ok("todo", "add", "221", "do the work", "--why", "the owner asked", "--note", "keep it short")
        self.ok("todo", "done", "221.1", "run:make test → 12 OK", "the work is done")
        os.environ["EL_SESSION"] = "othr1028"
        self.ok("todo", "accept", "221.1", "--by", "subagent", "--run", "make test → 12 OK", "re-ran, the same")
        todo = self.read("TODO.md")
        self.assertEqual(sum(1 for ln in todo.split("\n") if ln.startswith("- [x] ")), 220, "every closed phase stays")
        own, rendered, _ = grammar.todo_lines(stamp.split(todo)[0].split("\n"))
        self.assertLess(own, 20)
        self.assertGreaterEqual(rendered, 220)

    def test_the_f4_refusal_names_what_holds_the_lines_and_the_way_out(self):
        self._full()
        self.ok("todo", "note", "1.1", "the two hundredth line")
        code, _, err = run("todo", "note", "1.2", "one more")
        self.assertEqual(code, 3, err)
        self.assertIn("TODO is 201 lines of your text, limit 200", err)
        self.assertIn("they are phase 1 Work: 199", err)
        self.assertIn("el todo note N.M --edit K", err.rstrip("\n").split("\n")[-1], "the door ends the refusal")

    def test_the_re_run_question_at_a_full_todo_prints_no_note_that_would_be_refused(self):
        self._full()
        self.ok("todo", "note", "1.1", "the two hundredth line")
        out, _ = self.ok("todo", "done", "1.1", "run:make test → OK", "the first is done")
        self.assertNotIn("? el todo note 1.1 'to re-run: …' — the brief carries it", out)
        self.assertIn("TODO holds 200 of 200 lines of your text: make room first", out)


class RefusalTail(Base):
    def test_a_length_refusal_ends_with_its_limit_not_the_legend(self):
        code, _, err = run("phase", "plan", "2", "Fixes", "--goal", "a fixable set by channels, a census of the corpus, "
                                                                  "a replay before and after, a suite, a new build up and running")
        self.assertEqual(code, 3)
        last = err.rstrip("\n").split("\n")[-1]
        self.assertNotIn("exit 3 = ", last)
        self.assertIn("100 visible chars or fewer — rephrase, do not truncate", last)


class FileCarrier(Base):
    def test_the_close_names_the_done_item_that_proves_the_promised_file(self):
        self.ok("phase", "open", "1", "Diag", "--goal", "the diagnosis is written [file: report.md]")
        self.ok("todo", "add", "1", "write the report", "--expect", "[run: grep counts]")
        (self.case() / "report.md").write_text("# report\n", encoding="utf-8")
        self.ok("todo", "done", "1.1", "file:report.md", "run:grep → 3", "report written")
        code, _, err = run("phase", "close", "1", "done", "--reflect", "l", "--align", "a")
        self.assertEqual(code, 4)
        door = "el todo expect 1.1 '[run: grep counts] [file: report.md]'"
        self.assertIn(f"1.1 proves report.md by its file proof and does not promise it: the promise in its expect makes it "
                      f"count: {door}", err)
        order_out, _ = self.ok("order")
        self.assertIn(door, order_out, "Order says the same — one fact, one voice")
        self.ok(*door.split(" ", 1)[1].replace("'", "").split(" ", 3)[:3], "[run: grep counts] [file: report.md]")
        self.ok("phase", "close", "1", "done", "--reflect", "l", "--align", "a")


class SecondDone(Base):
    def test_a_new_proof_with_a_caption_keeps_the_result(self):
        self.ok("phase", "open", "1", "Fix", "--goal", "fixed")
        self.ok("todo", "add", "1", "fix it")
        for name in ("A.txt", "B.txt"):
            (self.case() / name).write_text(name, encoding="utf-8")
        self.ok("todo", "done", "1.1", "file:A.txt", "real result")
        out, _ = self.ok("todo", "done", "1.1", "file:B.txt", "local proof before deploy")
        self.assertIn("result kept «real result»", out)
        self.assertIn("    - result: real result\n", self.read("TODO.md"))
        self.assertRegex(self.read("JOURNAL.md"), r"RESULT · 1\.1: file \[B\.txt\]\(B\.txt\).* — local proof before deploy")
        brief, _ = self.ok("todo", "brief", "1.1")
        self.assertIn("real result", brief)
        self.assertNotIn("came out: local proof before deploy", brief)


class HonestNumbers(Base):
    def test_an_event_refused_says_how_much_of_its_own_words_fit(self):
        text = " ".join(f"step{i:03d} done in {i} ms on the stand" for i in range(1, 32))
        code, _, err = run("log", "RESULT", text)
        self.assertEqual(code, 3, err)
        m = re.search(r"(\d+) chars wrap into a headline and (\d+) body lines, 5 fit .* the first (\d+) chars of these words "
                      r"fit, (\d+) do not", err)
        self.assertTrue(m, err)
        size, fit, left = int(m.group(1)), int(m.group(3)), int(m.group(4))
        self.assertEqual(size, len(text))
        self.assertEqual(fit + left, size)
        self.assertLess(fit, size)
        self.ok("log", "RESULT", text[:fit])  # the number holds: that much is written


class Restate(Base):
    def test_a_close_again_says_the_closed_phase_in_other_words(self):
        self.ok("phase", "open", "1", "Fix", "--goal", "fixed")
        self.ok("todo", "add", "1", "fix it")
        self.ok("todo", "done", "1.1", "run:jest → ok", "fixed")
        self.ok("phase", "close", "1", "x", "--reflect", "x", "--align", "x")
        out, _ = self.ok("phase", "close", "1", "the poll backs off; jest is green", "--reflect", "a close is not a check")
        self.assertIn("restated: phase 1 Fix — result «the poll backs off; jest is green» (was «x») · reflect", out)
        self.assertRegex(self.read("TODO.md"), r"- \[x\] 1 Fix — the poll backs off; jest is green · \d{4}-\d{2}-\d{2} · "
                                               r"\[phases/1-fix\.md\]")
        pf = self.read("phases/1-fix.md")
        self.assertIn("result: the poll backs off; jest is green\n", pf)
        self.assertIn("- reflect: a close is not a check\n", pf)
        self.assertIn("- align: x\n", pf, "a lesson not given again stays")
        j = self.read("JOURNAL.md")
        self.assertIn("итог фазы 1 переписан: «x» → «the poll backs off; jest is green»", j)
        out, _ = self.ok("phase", "close", "1", "the poll backs off; jest is green")
        self.assertIn("already closed with these words — nothing changed", out)
        self.assertEqual(run("check")[0], 0)

    def test_a_closed_case_is_opened_before_its_phase_is_restated(self):
        self.ok("phase", "open", "1", "Fix", "--goal", "fixed")
        self.ok("todo", "add", "1", "fix it")
        self.ok("todo", "done", "1.1", "run:jest → ok", "fixed")
        self.ok("phase", "close", "1", "x", "--reflect", "x", "--align", "x")
        self.ok("done", "the shop works")
        code, _, err = run("--case", self.case().name, "phase", "close", "1", "other words")
        self.assertEqual(code, 4, err)
        self.assertIn('case reopen "why" — then el --case', err)
        self.assertIn("result: x\n", self.read("phases/1-fix.md"), "nothing was written")


class Doors(Base):
    def test_words_that_are_no_command_get_the_door_they_mean(self):
        for argv, door in ((["next"], "recovery: el · el readme set next"), (["goal"], "recovery: el · el phase show N"),
                           (["list"], "recovery: el case list · el todo"), (["phaseclose", "-h"], "recovery: el phase close"),
                           (["close", "2"], "recovery: el phase close")):
            code, _, err = run(*argv)
            self.assertEqual(code, 2, err)
            self.assertTrue(err.rstrip("\n").split("\n")[-1].strip().startswith(door), (argv, err))
        code, _, err = run("frobnicate")
        self.assertIn("recovery: el --help · el help start", err, "a word el cannot place keeps the start of the day")

    def test_a_hand_that_names_itself_gets_the_role_and_its_name_in_the_verdict(self):
        self.ok("phase", "open", "1", "Ship", "--goal", "shipped")
        self.ok("todo", "add", "1", "ship it")
        self.ok("todo", "done", "1.1", "run:python3 v.py → PASS", "shipped")
        os.environ["EL_SESSION"] = "othr1028"
        code, _, err = run("todo", "accept", "1.1", "--by", "cart_retry_42_final_acceptance", "--run",
                           "python3 v.py → PASS: reproduced at two widths", "Fresh review verified")
        self.assertEqual(code, 2, err)
        ready = ("el todo accept 1.1 --by subagent --run 'python3 v.py → PASS: reproduced at two widths' "
                 "'cart_retry_42_final_acceptance: Fresh review verified'")
        self.assertIn(ready, err)
        self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "python3 v.py → PASS: reproduced at two widths",
                "cart_retry_42_final_acceptance: Fresh review verified")
        code, _, err = run("todo", "accept", "1.1", "--by", "Codex fresh acceptance", "--run", "python3 v.py → PASS", "ok")
        self.assertIn("`Codex fresh acceptance` names codex: el todo accept 1.1 --by codex", err)


if __name__ == "__main__":
    unittest.main()
