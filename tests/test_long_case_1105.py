"""The pool of 2026-10-29…11-05: a long case read whole, and lines that said more than el knew.

1. Four live reports, 2026-10-29…11-01, one long case: an artifact folder linked to a dependency tree under another name;
   el walked it — the README drew 33 000 lines of it, the entry printed 22 000 Order lines and 8 MB, a write took 109 s.
   A link to a folder is one artifact; a tree with no document is material, one name in `other:`; Order counts what repeats.
2. A report, 2026-11-01, and one of 2026-11-02 with the same root: the clock went back an hour (daylight saving ended); a
   journal write stamped earlier than the newest entry broke «newest first», and el called its own write a hand edit —
   events went to the recover file, and the next phase open found no `reflect:` of the phase before.
3. A wall report, 2026-11-05: the agents' `done --howto` answered the PROBLEMs of one phase; the owner's close was refused on
   three of other phases. A case's howto answers the case.
4. Three reports, 2026-10-30…11-05: `readme set owner` — the command el's own hint gives — refused, because a Context line
   began with the word «owner». The keys el names for State are State lines.
5. Reports 2026-10-30 and 11-04: `check --all` printed commands for case B with the `--case` of the call; two items on one
   changed file came as two lines, one hidden between the legend and the count; checks.log grew to 13 MB, read by no one.
6. Reports 2026-10-31: an acceptance «PASS,12checks» against «PASS, 12 checks» was called a different result; a subagent's
   `EL_MODEL=<family>` was recorded as no model, and the brief had not said a name carries its version.
7. Reports 2026-11-02…05: a lock refusal named no holder; «$2–2,5» in double quotes landed as «–2,5»; in a terminal with no
   session id every write asked for `el case use`, which cannot hold there; a refused plan did not say «not planned»;
   `el brief 1.1` was sent to `el todo brief` without its number; `case new --root` asked for a name the folder has."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

ENVS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_THREAD_ID", "COPILOT_AGENT",
        "COPILOT_CLI", "COPILOT_AGENT_SESSION_ID", "EL_MODEL", "EL_SESSION", "EL_HANDS_DIR", "EL_HINTS", "EL_TWO_HANDS",
        "EL_CASE", "EL_RECITE", "EL_LOCK_DIR", "EL_LOCK_WAIT")


TRACKER = " ".join(f"entry{k} of the tracker as it stood" for k in range(60))  # 300 distinct 3-grams


class Base(unittest.TestCase):
    def setUp(self):
        self.saved = {k: os.environ.get(k) for k in ENVS}
        for k in ENVS:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS="0", EL_RECITE="0", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          CLAUDECODE="1", EL_SESSION="doer1105")
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


class ALinkToAFolderIsOneArtifact(Base):
    def setUp(self):
        super().setUp()
        deps = Path(self.tmp.name, "frontend", "node_modules")
        for k in range(30):  # a dependency tree: packages with their readmes, many of them alike
            pkg = deps / f"pkg{k}"
            pkg.mkdir(parents=True)
            (pkg / "README.md").write_text("# pkg\n\n" + "the same license text of a package, word for word. " * 40,
                                           encoding="utf-8")
        art = self.case() / "artifacts"
        art.mkdir()
        (art / "report.md").write_text("# r\nsummary: what the run showed\n", encoding="utf-8")
        os.symlink(deps, art / "deps-alias")  # a link under another name than node_modules
        os.symlink(art, art / "loop")  # and a cycle
        stand = art / "stand-before" / "frontend" / "src"
        stand.mkdir(parents=True)
        (stand / "app.tsx").write_text("x\n", encoding="utf-8")

    def test_the_map_names_the_link_once_and_walks_nothing_behind_it(self):
        self.ok("readme", "set", "next", "look")
        links = self.read("README.md").split("## Links", 1)[1]
        self.assertNotIn("pkg", links, "nothing behind a link to a folder is drawn")
        self.assertIn("deps-alias/", links)
        self.assertIn("stand-before/", links, "a tree with no document is one name in other:")
        self.assertNotIn("- artifacts/stand-before/frontend/", links)
        self.assertIn("[report.md](artifacts/report.md) — what the run showed", links)

    def test_the_entry_says_no_line_about_files_behind_the_link(self):
        out, _ = self.ok()
        self.assertNotIn("pkg", out)
        self.assertLess(len(out), 6000, "the entry stays a dose")

    def test_the_proof_through_the_link_still_resolves(self):
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "Read the readme")
        out, _ = self.ok("todo", "done", "1.1", "file:artifacts/deps-alias/pkg1/README.md", "read it")
        self.assertIn("done: 1.1", out)


class OrderCountsWhatRepeats(Base):
    def test_many_pairs_of_alike_files_are_one_counted_line(self):
        docs = self.case() / "docs"
        docs.mkdir()
        for k in range(6):
            (docs / f"copy{k}.md").write_text(f"# c{k}\nsummary: copy {k}\n\n" + TRACKER,
                                              encoding="utf-8")
        out, _ = self.ok()  # the entry counts; `el order`, asked for, names every file once (1.76.0)
        lines = [ln for ln in out.split("\n") if "verbatim" in ln]
        self.assertEqual(len(lines), 1, out)
        self.assertIn("15 pair(s) of files share text verbatim", lines[0])
        self.assertIn("… +12 (each file named: el order)", lines[0])
        out, _ = self.ok("order")
        lines = [ln for ln in out.split("\n") if "verbatim" in ln]
        self.assertEqual(len(lines), 1, out)
        self.assertIn("every file named with its strongest pair (6 files)", lines[0])

    def test_a_few_pairs_keep_a_line_each(self):
        docs = self.case() / "docs"
        docs.mkdir()
        for k in range(2):
            (docs / f"copy{k}.md").write_text(f"# c{k}\nsummary: copy {k}\n\n" + TRACKER,
                                              encoding="utf-8")
        out, _ = self.ok("order")
        self.assertEqual(sum("verbatim" in ln for ln in out.split("\n")), 1)
        self.assertIn("docs/copy0.md ≈ docs/copy1.md", out)

    def test_many_folders_without_a_description_are_one_counted_line(self):
        for k in range(5):
            d = self.case() / f"run{k}"
            d.mkdir()
            (d / "x.txt").write_text("x\n", encoding="utf-8")
        out, _ = self.ok()  # the entry counts and names the door; `el order`, asked for, names each (1.76.0)
        self.assertIn("5 folder(s) without a description — run0/, run1/, run2/, run3/ … +1 (each named: el order)", out)
        out, _ = self.ok("order")
        self.assertIn("5 folder(s) without a description — run0/, run1/, run2/, run3/, run4/ →", out)

    def test_the_entry_prints_twelve_lines_of_order_and_the_door_to_all(self):
        from elephant import commands
        self.assertEqual(commands.ORDER_SHOWN, 12)
        many = [f"thing {k}" for k in range(20)]
        orig = commands._order_lines
        commands._order_lines = lambda *a, **k: many
        try:
            out, _ = self.ok()
        finally:
            commands._order_lines = orig
        self.assertIn("## Order — 20 thing(s) to put back", out)
        self.assertIn("- thing 11", out)
        self.assertNotIn("- thing 12", out)
        self.assertIn("- … +8 more → el order (every line)", out)


class TheClockGoesBack(Base):
    def test_a_write_after_the_clock_went_back_keeps_every_event(self):
        from elephant import commands
        times = iter([("2099-11-01", "01:40"), ("2099-11-01", "01:28"), ("2099-11-01", "01:29")])
        orig = commands._now
        commands._now = lambda: next(times)
        try:
            self.ok("log", "DECISION", "a neutral sentence one")
            out, err = self.ok("log", "RESULT", "a neutral sentence two")
            self.ok("log", "DECISION", "reflect: a neutral lesson")
        finally:
            commands._now = orig
        self.assertNotIn("bypassing", out + err)
        self.assertEqual(list(self.case().glob("*.recover.md")), [], "nothing quarantined")
        journal = self.read("JOURNAL.md")
        for words in ("a neutral sentence one", "a neutral sentence two", "reflect: a neutral lesson"):
            self.assertIn(words, journal)
        self.assertIn("- 2099-11-01 01:40 · p0", journal)
        self.assertNotIn("01:28", journal, "the newest entry's time stands in for a clock gone back")
        self.ok("check")

    def test_the_reflect_of_a_phase_closed_before_the_clock_went_back_is_found_by_the_next_open(self):
        from elephant import commands
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "One")
        self.ok("todo", "done", "1.1", "owner", "done by word")
        times = iter([("2099-11-01", "01:59")] * 6 + [("2099-11-01", "01:05")] * 6)
        orig = commands._now
        commands._now = lambda: next(times)
        try:
            self.ok("phase", "close", "1", "closed", "--reflect", "a lesson about agents", "--align", "the next plan")
            self.ok("phase", "plan", "2", "Next", "--goal", "n")
            self.ok("log", "DECISION", "a neutral sentence after the hour came again")
            self.ok("phase", "open", "2")
        finally:
            commands._now = orig
        self.assertEqual(list(self.case().glob("*.recover.md")), [], "nothing quarantined")
        self.assertIn("DECISION · reflect: a lesson about agents", self.read("JOURNAL.md"))


class TheCaseHowtoAnswersTheCase(Base):
    def test_the_owner_closes_what_the_agents_howto_answered(self):
        os.environ["EL_TWO_HANDS"] = "1"
        self.ok("case", "new", "farm", "--goal", "the farm works")
        c = ("--case", "farm")
        self.ok(*c, "phase", "open", "1", "Work", "--goal", "w")
        self.ok(*c, "todo", "add", "1", "One")
        self.ok(*c, "todo", "done", "1.1", "owner", "done by word")
        self.ok(*c, "todo", "accept", "1.1", "--by", "owner", "fine")
        self.ok(*c, "phase", "close", "1", "closed", "--reflect", "a lesson about agents", "--align", "the next plan")
        self.ok(*c, "log", "--phase", "p1", "PROBLEM", "a neutral trouble found late in phase one")
        self.ok(*c, "log", "PROBLEM", "a neutral trouble between phases")
        code, out, err = run(*c, "done", "the farm works")
        self.assertEqual(code, 4, out + err)
        self.assertIn("2 PROBLEM(s) no recipe answers", out + err)
        out, _ = self.ok(*c, "done", "the farm works", "--howto", "none: each trouble was one of a kind")
        self.assertIn("ready:", out)
        self.ok(*c, "done", "--by", "owner", "close it")
        farm = next(Path(self.tmp.name, ".cases").glob("*-farm"))
        self.assertIn("closed:", (farm / "README.md").read_text(encoding="utf-8"))

class TheKeysElNamesAreStateLines(Base):
    def test_set_owner_writes_state_under_a_context_line_that_starts_with_owner(self):
        self.ok("readme", "add", "context", "owner 2026-11-03: words of the owner")
        out, _ = self.ok("readme", "set", "owner", "decide X")
        readme = self.read("README.md")
        self.assertIn("- owner: decide X", readme.split("## State", 1)[1].split("## Decisions", 1)[0])
        self.assertIn("- owner 2026-11-03: words of the owner", readme.split("## Context", 1)[1].split("## State", 1)[0])

    def test_a_free_prefix_still_points_at_its_line_elsewhere(self):
        self.ok("readme", "add", "decisions", "1 Реклама — вилка 1000-3500")
        code, out, err = run("readme", "set", "1 Реклама", "вилка 1850-7300")
        self.assertEqual(code, 4, out + err)


class CheckSpeaksForEachCase(Base):
    def test_a_command_about_another_case_names_that_case(self):
        self.ok("case", "new", "farm", "--goal", "the farm works")
        farm = next(Path(self.tmp.name, ".cases").glob("*-farm"))
        (farm / "jira").mkdir()
        (farm / "jira" / "t.txt").write_text("x\n", encoding="utf-8")
        code, out, err = run("--case", "shop", "check", "--all")
        lines = [ln for ln in (out + err).split("\n") if "folder jira/" in ln]
        self.assertTrue(lines, out + err)
        self.assertIn("el --case " + farm.name + " readme add links", lines[0])
        self.assertNotIn("--case shop", lines[0])

    def test_two_items_on_one_changed_file_are_one_line_naming_both(self):
        docs = self.case() / "docs"
        docs.mkdir()
        (docs / "a.md").write_text("# a\nsummary: a file\n\ntext one\n", encoding="utf-8")
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "One")
        self.ok("todo", "add", "1", "Two")
        self.ok("todo", "done", "1.1", "file:docs/a.md", "one done")
        self.ok("todo", "done", "1.2", "file:docs/a.md", "two done")
        (docs / "a.md").write_text("# a\nsummary: a file\n\ntext two\n", encoding="utf-8")
        code, out, err = run("check")
        f20 = [ln for ln in (out + err).split("\n") if "F20" in ln]
        self.assertEqual(len(f20), 1, out + err)
        self.assertIn("the proof of 2 items: 1.1, 1.2", f20[0])
        self.assertIn("violations: 2", out + err)
        self.assertFalse(Path(self.tmp.name, ".cases", "checks.log").exists(), "check keeps no log")


class AcceptanceSaysWhatItKnows(Base):
    def setUp(self):
        super().setUp()
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "Verify")

    def test_spacing_alone_is_not_a_different_result(self):
        self.ok("todo", "done", "1.1", "run:python3 verify.py → PASS, 12 checks", "did it")
        out, err = self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "python3 verify.py → PASS,12checks", "ok")
        self.assertNotIn("differs", out + err)

    def test_other_numbers_still_differ(self):
        self.ok("todo", "done", "1.1", "run:python3 verify.py → PASS, 12 checks", "did it")
        out, err = self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "python3 verify.py → PASS, 11 checks", "ok")
        self.assertIn("differs", out + err)

    def test_a_family_without_its_version_is_told_why(self):
        self.ok("todo", "done", "1.1", "run:t → ok", "did it")
        os.environ["EL_MODEL"] = "claude-sonnet"
        out, err = self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "t → ok", "ok")
        self.assertIn("a name carries its version", out + err)


class TheLockNamesItsHolder(Base):
    def test_a_lock_refusal_names_the_holder_and_the_path(self):
        import fcntl
        from elephant import store
        os.environ.update(EL_LOCK_DIR=str(Path(self.tmp.name) / "locks"), EL_LOCK_WAIT="0.1")
        path = store.space_lock_path(store.find_root())
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a+") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            fh.write("pid 4242 · el todo accept 1.1 · since 10:00:00\n")
            fh.flush()
            code, out, err = run("readme", "set", "next", "x")
        self.assertEqual(code, 4, out + err)
        self.assertIn("held by: pid 4242 · el todo accept 1.1", out + err)
        self.assertIn(f"lock: {path}", out + err)
        self.assertIn("ps -p 4242", out + err)
        self.ok("readme", "set", "next", "x")  # the holder gone, the same command goes through


class ASwallowedSumIsRefused(Base):
    def test_a_range_without_its_dollar_is_refused(self):
        code, out, err = run("log", "RESULT", "дали –2,5 тыс. за работу")
        self.assertEqual(code, 2, out + err)
        self.assertIn("SINGLE quotes", out + err)
        self.assertNotIn("дали", self.read("JOURNAL.md"))

    def test_a_comma_without_its_number_is_refused(self):
        code, out, err = run("log", "RESULT", "заплатили ,5 сверху")
        self.assertEqual(code, 2, out + err)

    def test_what_live_cases_write_passes(self):
        for text in ("сумма $2–2,5 тыс.", "текст −85 px", "tail -4 of the log", "range 2–3 days", "dash — 2 items"):
            self.ok("log", "RESULT", text)


class ATerminalWithoutASession(Base):
    def test_no_note_about_another_session_when_el_cannot_tell_sessions_apart(self):
        self.ok("case", "new", "farm", "--goal", "the farm works")
        self.ok("--case", "farm", "log", "DECISION", "a neutral sentence written by an identified session")
        for k in ("CLAUDECODE", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["COPILOT_AGENT"] = "1"
        out, _ = self.ok("case", "use", "farm")
        self.assertIn("gives el no session id", out)
        self.assertIn("export EL_SESSION=", out)
        for _ in range(3):
            out, err = self.ok("log", "DECISION", "a neutral sentence from the terminal")
            self.assertNotIn("take your own", out + err)
        farm = next(Path(self.tmp.name, ".cases").glob("*-farm"))
        self.assertIn("from the terminal", (farm / "JOURNAL.md").read_text(encoding="utf-8"))


class ALengthRefusalSaysWhatWasNotDone(Base):
    LONG = "Срезы экспертов прогнаны на стенде; найден самый глубокий без просадки качества и без новых поломок [run: s → ok]"

    def test_a_refused_plan_says_the_phase_is_not_planned_first(self):
        code, out, err = run("phase", "plan", "3", "Ladder", "--goal", self.LONG)
        self.assertEqual(code, 3)
        self.assertTrue((out + err).startswith("el: ERROR [exit 3] phase 3 not planned: its goal"), out + err)

    def test_a_refused_add_and_edit_say_so_first(self):
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        code, out, err = run("todo", "add", "1", self.LONG)
        self.assertTrue((out + err).startswith("el: ERROR [exit 3] nothing added to phase 1: the item text"), out + err)
        self.ok("todo", "add", "1", "Short")
        code, out, err = run("todo", "edit", "1.1", self.LONG)
        self.assertTrue((out + err).startswith("el: ERROR [exit 3] 1.1 not changed: the new text"), out + err)


class SmallDoors(Base):
    def test_an_action_typed_as_a_command_keeps_its_number_in_the_door(self):
        code, out, err = run("brief", "1.1")
        self.assertEqual(code, 2)
        self.assertIn("recovery: el todo brief 1.1", out + err)
        code, out, err = run("--case", "shop", "phaseclose", "3")
        self.assertIn("recovery: el --case shop phase close 3", out + err)

    def test_root_mode_takes_the_project_folder_name(self):
        with tempfile.TemporaryDirectory() as other:
            proj = Path(other, "garden")
            proj.mkdir()
            os.chdir(proj)
            try:
                self.ok("case", "new", "--root", "--goal", "the garden grows")
                self.assertTrue((proj / "README.md").read_text(encoding="utf-8").startswith("# garden"))
            finally:
                os.chdir(self.tmp.name)


class TheInspection(Base):
    """Codex review of the change, 2026-11-05: six findings, each reproduced before the fix."""

    def test_a_link_loop_after_a_matching_link_does_not_crash(self):
        docs = self.case() / "docs"
        docs.mkdir()
        (docs / "b.md").write_text("# b\nsummary: b\n\n" + TRACKER, encoding="utf-8")
        (docs / "a.md").write_text("# a\nsummary: a\n\n" + TRACKER + "\n[b](b.md) [loop](loop)\n", encoding="utf-8")
        os.symlink("loop", docs / "loop")
        self.ok("order")

    def test_a_described_link_to_a_folder_keeps_its_description(self):
        outside = Path(self.tmp.name, "shared-stand")
        outside.mkdir()
        (outside / "x.txt").write_text("x\n", encoding="utf-8")
        art = self.case() / "artifacts"
        art.mkdir()
        (art / "r.md").write_text("# r\nsummary: the report\n", encoding="utf-8")
        os.symlink(outside, art / "stand")
        self.ok("readme", "add", "links", "artifacts/stand/ — the shared environment")
        links = self.read("README.md").split("## Links", 1)[1]
        self.assertIn("- artifacts/stand/ — the shared environment", links)
        self.assertNotIn("x.txt", links)

    def test_a_described_link_deep_in_a_tree_without_documents_keeps_its_line(self):
        # the second hand's return of 48.1, 2026-11-05: the fold above it took the described link along
        outside = Path(self.tmp.name, "shared-stand")
        outside.mkdir()
        deep = self.case() / "artifacts" / "wrapper" / "deep"
        deep.mkdir(parents=True)
        os.symlink(outside, deep / "stand")
        self.ok("readme", "add", "links", "artifacts/wrapper/deep/stand/ — the shared environment")
        self.ok("readme", "set", "next", "again")
        links = self.read("README.md").split("## Links", 1)[1]
        self.assertEqual(links.count("- artifacts/wrapper/deep/stand/ — the shared environment"), 1, links)

    def test_a_link_named_like_a_case_is_no_nested_case(self):
        outside = Path(self.tmp.name, "snapshot")
        outside.mkdir()
        os.symlink(outside, self.case() / "2026-01-01-snapshot")
        self.ok("phase", "open", "1", "Work", "--goal", "w")
        self.ok("todo", "add", "1", "One")
        self.ok("todo", "done", "1.1", "owner", "done by word")
        self.ok("phase", "close", "1", "closed", "--reflect", "a lesson about agents", "--align", "the next plan")
        out, _ = self.ok("done", "complete")
        self.assertNotIn("nested", out)

    def test_a_link_at_the_top_of_a_case_is_not_walked(self):
        from elephant import store
        outside = Path(self.tmp.name, "elsewhere")
        outside.mkdir()
        (outside / "one.txt").write_text("1\n", encoding="utf-8")
        os.symlink(outside, self.case() / "alias")
        self.assertEqual(store.case_files(self.case() / "alias"), [])
        code, out, err = run("check")
        self.assertNotIn("1 file(s)", out + err)

    def test_a_state_key_in_capitals_is_the_key(self):
        self.ok("readme", "set", "next", "original")
        self.ok("readme", "add", "context", "NEXT: quoted original words")
        self.ok("readme", "set", "NEXT", "ship release")
        state = self.read("README.md").split("## State", 1)[1].split("## Decisions", 1)[0]
        self.assertIn("- next: ship release", state)
        self.assertNotIn("NEXT:", state)
        self.assertNotIn("original", state)

    def test_the_door_finds_the_command_after_a_case_of_the_same_name(self):
        code, out, err = run("--case", "brief", "brief", "1.1")
        self.assertIn("recovery: el --case brief todo brief 1.1", out + err)


if __name__ == "__main__":
    unittest.main()
