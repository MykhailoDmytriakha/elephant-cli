"""The radio with Codex, 2026-11-08: the entry in a read-only sandbox died in a Python traceback.

`el` — a look — went to redraw README (`_refresh_readme → _atomic_write → PermissionError: Operation not permitted`), and
the agent had to read the traceback to learn what el had tried to change. A look needs no write: where the system lets
nothing be written, the entry shows the case and says in one line what it could not refresh; a write command is refused
as el refuses — what, why, nothing was written, the doors that need no write. Where no temp folder can be written at all,
el died earlier, in `tempfile`, before it read a line: the session's memory that cannot be kept is not kept."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_long_case_1105 import Base


def _lock(path: Path):
    """Take write access away from a folder and everything under it, as a read-only sandbox does."""
    for p in sorted(path.rglob("*"), key=lambda x: -len(x.parts)):
        if p.is_dir():
            p.chmod(stat.S_IRUSR | stat.S_IXUSR)
    path.chmod(stat.S_IRUSR | stat.S_IXUSR)


def _unlock(path: Path):
    path.chmod(stat.S_IRWXU)
    for p in path.rglob("*"):
        if p.is_dir():
            p.chmod(stat.S_IRWXU)


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes through any mode")
class ALookNeedsNoWrite(Base):
    def setUp(self):
        super().setUp()
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "docs").mkdir()
        (self.case / "docs" / "plan.md").write_text("# Plan\nsummary: the plan of the shop\n", encoding="utf-8")
        self.readme = (self.case / "README.md").read_text(encoding="utf-8")  # stale: Links do not draw docs/ yet
        _lock(Path(self.tmp.name) / ".cases")

    def tearDown(self):
        _unlock(Path(self.tmp.name) / ".cases")
        super().tearDown()

    def run_el(self, *argv):
        from tests.test_commands import run
        return run(*argv)

    def test_the_entry_shows_the_case_and_says_what_it_could_not_refresh(self):
        code, out, err = self.run_el()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("Traceback", out + err)
        self.assertIn("read-only here", out)
        self.assertIn("not refreshed — README.md", out)
        self.assertIn("thread:", out)
        self.assertNotIn("README not refreshed —", err)  # said once, by the entry, not again as a warning
        self.assertEqual((self.case / "README.md").read_text(encoding="utf-8"), self.readme)

    def test_a_write_is_refused_as_el_refuses_with_doors_that_need_no_write(self):
        journal = (self.case / "JOURNAL.md").read_text(encoding="utf-8")
        code, out, err = self.run_el("log", "DECISION", "keep the shop open on Sundays")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("Traceback", out + err)
        lines = [ln for ln in err.splitlines() if ln.strip()]
        self.assertTrue(lines[0].startswith("el: ERROR [exit 4] cannot write "), err)
        self.assertIn("JOURNAL.md", lines[0])
        self.assertIn("nothing was written", lines[0])
        self.assertIn("a look needs no write: el status · el todo · el order", lines[-1])
        self.assertEqual((self.case / "JOURNAL.md").read_text(encoding="utf-8"), journal)

    def test_the_doors_the_refusal_prints_run_as_printed(self):
        for argv in ((), ("todo",), ("order",)):
            code, out, err = self.run_el(*argv)
            self.assertEqual(code, 0, f"el {' '.join(argv)}: {out}{err}")
            self.assertNotIn("Traceback", out + err)
        code, out, _ = self.run_el("order")
        self.assertIn("read-only here", out)

    def test_a_write_outside_the_write_door_is_refused_too(self):
        code, out, err = self.run_el("case", "new", "garden", "--goal", "the garden grows")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("Traceback", out + err)
        self.assertIn("cannot write", err)
        self.assertIn("nothing was written", err)
        self.assertFalse(any("garden" in p.name for p in (Path(self.tmp.name) / ".cases").iterdir()))


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes through any mode")
class TheDeniedFileIsTheFileMeant(Base):
    """The second hand, 2026-11-08: with a stale onboarding block in a read-only project the entry said «not refreshed —
    .AGENTS.md.k3x9.tmp», and `el onboarding` refused «cannot write .AGENTS.md.k3x9.tmp» — el's own temp file, not
    the file it meant to write."""

    def setUp(self):
        super().setUp()
        from elephant import onboarding
        self.saved_onb = os.environ.get("EL_ONBOARDING")
        os.environ["EL_ONBOARDING"] = "1"
        old = "## Elephant — память работы в `.cases/`\n\nold rhythm: read README, then work."
        block = f"<!-- elephant onboarding 1.23.0 · {onboarding.fingerprint(old)} — written by el -->\n{old}\n{onboarding.END}"
        self.agents = Path(self.tmp.name) / "AGENTS.md"
        self.agents.write_text("# agents\n\n" + block + "\n", encoding="utf-8")
        self.before = self.agents.read_text(encoding="utf-8")
        Path(self.tmp.name).chmod(stat.S_IRUSR | stat.S_IXUSR)  # the project root only: the case itself may be written

    def tearDown(self):
        Path(self.tmp.name).chmod(stat.S_IRWXU)
        if self.saved_onb is None:
            os.environ.pop("EL_ONBOARDING", None)
        else:
            os.environ["EL_ONBOARDING"] = self.saved_onb
        super().tearDown()

    def test_the_entry_names_agents_md_not_a_temp_file(self):
        from tests.test_commands import run
        code, out, err = run()
        self.assertEqual(code, 0, out + err)
        self.assertIn("not refreshed — AGENTS.md", out)
        self.assertNotIn(".tmp", out + err)
        self.assertEqual(self.agents.read_text(encoding="utf-8"), self.before)
        self.assertEqual(sorted(p.name for p in Path(self.tmp.name).iterdir() if p.name.endswith(".tmp")), [])

    def test_el_onboarding_refuses_naming_agents_md(self):
        from tests.test_commands import run
        code, out, err = run("onboarding")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write AGENTS.md", err)
        self.assertNotIn(".tmp", out + err)


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes through any mode")
class ARefusalPutsBackWhatItWrote(Base):
    """The second hand, round 2, 2026-11-08: `el onboarding` refreshed CLAUDE.md, met AGENTS.md (a link into a folder
    with no write access) and refused «nothing was written» — CLAUDE.md stayed changed: the onboarding write was not one
    the command could put back."""

    def setUp(self):
        super().setUp()
        from elephant import onboarding
        self.saved_onb = os.environ.get("EL_ONBOARDING")
        os.environ["EL_ONBOARDING"] = "1"
        old = "## Elephant — память работы в `.cases/`\n\nold rhythm: read README, then work."
        block = f"<!-- elephant onboarding 1.23.0 · {onboarding.fingerprint(old)} — written by el -->\n{old}\n{onboarding.END}"
        root = Path(self.tmp.name)
        self.claude = root / "CLAUDE.md"
        self.claude.write_text("# mine\n\n" + block + "\n", encoding="utf-8")
        self.before = self.claude.read_bytes()
        (root / "protected").mkdir()
        (root / "protected" / "instructions.md").write_text("# agents\n\n" + block + "\n", encoding="utf-8")
        (root / "AGENTS.md").symlink_to("protected/instructions.md")
        (root / "protected").chmod(stat.S_IRUSR | stat.S_IXUSR)

    def tearDown(self):
        (Path(self.tmp.name) / "protected").chmod(stat.S_IRWXU)
        if self.saved_onb is None:
            os.environ.pop("EL_ONBOARDING", None)
        else:
            os.environ["EL_ONBOARDING"] = self.saved_onb
        super().tearDown()

    def test_el_onboarding_puts_claude_md_back_when_agents_md_is_denied(self):
        from tests.test_commands import run
        code, out, err = run("onboarding")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write AGENTS.md", err)
        self.assertIn("put back as it was: CLAUDE.md", err)
        self.assertEqual(self.claude.read_bytes(), self.before)

    def test_the_entry_says_what_it_refreshed_and_what_it_could_not(self):
        from tests.test_commands import run
        code, out, err = run()
        self.assertEqual(code, 0, out + err)
        refreshed = self.claude.read_bytes() != self.before
        self.assertEqual(refreshed, "onboarding refreshed in CLAUDE.md" in out, out)
        self.assertIn("not refreshed — AGENTS.md", out)


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes through any mode")
class NothingWrittenMeansNothingStays(Base):
    """The second hand, round 3, 2026-11-08: «nothing was written» over writes that stayed — a phase file rewritten in
    place in a folder el may not write (the rollback tried a temp file there and gave up silently), the folders a refused
    `mv` had made; and a binary `mv` into a protected folder named only its source."""

    def setUp(self):
        super().setUp()
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        self.locked: list = []

    def tearDown(self):
        for p in self.locked:
            p.chmod(stat.S_IRWXU)
        super().tearDown()

    def lock(self, *paths: Path):
        for p in paths:
            p.chmod(stat.S_IRUSR | stat.S_IXUSR)
            self.locked.append(p)

    def test_a_refused_close_puts_the_phase_file_back_in_place(self):
        for argv in (("phase", "open", "1", "First", "--goal", "the shop works"), ("todo", "add", "1", "check the shop"),
                     ("todo", "done", "1.1", "run:true → OK", "checked"),
                     ("log", "DECISION", "reflect: inspect the files first"), ("log", "DECISION", "align: no further phases")):
            self.ok(*argv)
        pf = next((self.case / "phases").glob("1-*.md"))
        before = pf.read_bytes()
        self.lock(self.case, self.case / "phases")
        from tests.test_commands import run
        code, out, err = run("phase", "close", "1", "the shop works")
        self.assertEqual(code, 4, out + err)
        self.assertIn("nothing was written", err)
        self.assertNotIn("NOT put back", err)
        self.assertIn(f"put back as it was: ", err)  # the phase file was written before TODO was denied — and came back
        self.assertIn(pf.name, err.split("put back as it was: ", 1)[1].splitlines()[0])
        self.assertEqual(pf.read_bytes(), before)

    def test_a_refused_move_takes_away_the_folders_it_made(self):
        (self.case / "source").mkdir()
        (self.case / "source" / "x.md").write_text("# X\nsummary: an artifact\n", encoding="utf-8")
        self.lock(self.case / "source")
        from tests.test_commands import run
        code, out, err = run("mv", "source/x.md", "target/new/deep/x.md")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot move", err)
        self.assertFalse((self.case / "target").exists(), err)
        self.assertTrue((self.case / "source" / "x.md").is_file())

    def test_a_phase_file_that_is_a_link_comes_back_as_a_link_with_its_target(self):
        """Round 5: the link was «put back» as a plain file, and the file it pointed at stayed changed."""
        for argv in (("phase", "open", "1", "First", "--goal", "the shop works"), ("todo", "add", "1", "check the shop"),
                     ("todo", "done", "1.1", "owner", "checked"),
                     ("log", "DECISION", "reflect: inspect the files first"), ("log", "DECISION", "align: no further phases")):
            self.ok(*argv)
        pf = next((self.case / "phases").glob("1-*.md"))
        real = Path(self.tmp.name) / "kept" / pf.name
        real.parent.mkdir()
        real.write_bytes(pf.read_bytes())
        pf.unlink()
        pf.symlink_to(real)
        before = real.read_bytes()
        self.lock(self.case)  # TODO is denied after the phase file was written through its link
        from tests.test_commands import run
        code, out, err = run("phase", "close", "1", "the shop works")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("NOT put back", err)
        self.assertTrue(pf.is_symlink(), "the link stays a link")
        self.assertEqual(real.read_bytes(), before)

    def test_a_move_whose_readme_is_denied_is_refused_whole(self):
        """A write command the system did not let finish is refused and put back — not «moved» with a warning."""
        for d in ("source", "target"):
            (self.case / d).mkdir()
        (self.case / "source" / "x.md").write_text("# X\nsummary: an artifact\n", encoding="utf-8")
        self.ok("readme", "add", "links", "source/x.md — an artifact")
        self.lock(self.case)
        from tests.test_commands import run
        code, out, err = run("mv", "source/x.md", "target/x.md")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("moved:", out)
        self.assertTrue((self.case / "source" / "x.md").is_file(), err)
        self.assertFalse((self.case / "target" / "x.md").exists(), err)

    def test_a_refused_move_of_a_link_puts_the_link_back(self):
        for d in ("source", "target"):
            (self.case / d).mkdir()
        (self.case / "kept").mkdir()
        (self.case / "kept" / "real.bin").write_bytes(b"abc")
        (self.case / "source" / "a.bin").symlink_to("../kept/real.bin")
        self.lock(self.case)
        from tests.test_commands import run
        code, out, err = run("mv", "source/a.bin", "target/a.bin")
        self.assertEqual(code, 4, out + err)
        self.assertTrue((self.case / "source" / "a.bin").is_symlink(), err)
        self.assertEqual(os.readlink(self.case / "source" / "a.bin"), "../kept/real.bin")
        self.assertEqual((self.case / "kept" / "real.bin").read_bytes(), b"abc")
        self.assertFalse((self.case / "target" / "a.bin").is_symlink() or (self.case / "target" / "a.bin").exists())

    def test_a_childs_write_whose_parent_line_is_denied_is_refused_whole(self):
        """Round 6: the parent's README could not follow — `phase open` in the child said exit 0, kept the child's
        change and left the parent's line about it stale."""
        self.ok("phase", "open", "1", "First", "--goal", "the shop works")
        self.ok("spawn", "field", "--goal", "the field grows")
        child = next(self.case.glob("*-field"))
        todo_before = (child / "TODO.md").read_bytes()
        parent_before = (self.case / "README.md").read_bytes()
        self.lock(self.case)
        from tests.test_commands import run
        code, out, err = run("phase", "open", "1", "Plant", "--goal", "the field grows")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write", err)
        self.assertEqual((child / "TODO.md").read_bytes(), todo_before, err)
        self.assertEqual((self.case / "README.md").read_bytes(), parent_before)
        self.assertFalse((child / "phases").exists() and any((child / "phases").iterdir()), err)

    def test_adopt_whose_readme_is_denied_is_refused_whole(self):
        """Round 7: `el order --adopt` wrote `summary:` into the document, met a denied README and answered exit 0 —
        a write, read as a look."""
        (self.case / "docs").mkdir()
        doc = self.case / "docs" / "plan.md"
        doc.write_text("# Plan\n\nthe body\n", encoding="utf-8")
        self.ok("readme", "add", "links", "docs/plan.md — the plan of the shop")
        (self.case / "docs" / "bed.md").write_text("# Bed\nsummary: a new garden bed\n", encoding="utf-8")  # README must follow
        before = doc.read_bytes()
        self.lock(self.case)
        from tests.test_commands import run
        code, out, err = run("order", "--adopt")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write", err)
        self.assertEqual(doc.read_bytes(), before, err)

    def test_a_denied_write_swallowed_on_the_way_refuses_the_command(self):
        """Round 8: `el readme --file` met a denied TODO rebuild inside a read, warned, wrote README and answered exit 0
        under «nothing was written». Wherever a handler swallowed it, a write command the system denied on the way is
        refused whole at its end."""
        self.ok("phase", "open", "1", "Plant", "--goal", "the shop works")
        self.ok("todo", "add", "1", "check the shop")
        protected = Path(self.tmp.name) / "protected"
        protected.mkdir()
        todo = self.case / "TODO.md"
        original = todo.read_bytes()
        todo.unlink()
        real = protected / "tasks.md"
        real.write_bytes(original.replace(b"check the shop", b"inspect the shop"))  # a hand edit: el rebuilds on read
        todo.symlink_to(real)
        readme_before = (self.case / "README.md").read_bytes()
        (Path(self.tmp.name) / "input.md").write_bytes(readme_before)
        self.lock(protected)
        from tests.test_commands import run
        code, out, err = run("readme", "--file", "input.md")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write", err)
        self.assertEqual((self.case / "README.md").read_bytes(), readme_before, err)

    def _hand_edited_todo_behind_a_lock(self):
        self.ok("phase", "open", "1", "Plant", "--goal", "the shop works")
        self.ok("todo", "add", "1", "check the shop")
        self.ok("todo", "done", "1.1", "owner", "checked")
        protected = Path(self.tmp.name) / "protected"
        protected.mkdir()
        todo = self.case / "TODO.md"
        real = protected / "tasks.md"
        real.write_bytes(todo.read_bytes().replace(b"check the shop", b"inspect the shop"))  # a hand edit
        todo.unlink()
        todo.symlink_to(real)
        self.lock(protected)
        return real

    def test_the_looks_read_a_hand_edited_file_the_system_will_not_let_el_rebuild(self):
        """Round 9: the rebuild of a hand-edited TODO is a write inside the read door; denied, it made `todo brief`,
        `todo show`, `phase show` and `facts` refuse. A look reads it as el would rebuild it, and says so."""
        real = self._hand_edited_todo_behind_a_lock()
        before = real.read_bytes()
        from tests.test_commands import run
        for argv in (("todo", "brief", "1.1"), ("todo", "show", "1.1"), ("phase", "show", "1"), ("facts",), (), ("todo",)):
            code, out, err = run(*argv)
            self.assertEqual(code, 0, f"el {' '.join(argv)}: {out}{err}")
        code, out, err = run("todo", "show", "1.1")
        self.assertIn("inspect the shop", out)
        self.assertTrue((self.case / "TODO.md").is_symlink(), "a look never replaces the link with a file")
        self.assertEqual(real.read_bytes(), before)
        self.assertFalse((self.case / "TODO.md.recover.md").exists())

    def test_a_look_over_a_denied_rebuild_keeps_an_older_recover_file(self):
        """Round 10: a look over a denied rebuild wrote the lines it would move out over an existing recover file."""
        real = self._hand_edited_todo_behind_a_lock()
        (real.parent).chmod(stat.S_IRWXU)
        real.write_text(real.read_text(encoding="utf-8").replace("\nstamp:", "\nsneaky line\n\nstamp:"), encoding="utf-8")
        real.parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
        rec = self.case / "TODO.md.recover.md"
        rec.write_text("older lines still to re-enter\n", encoding="utf-8")
        os.utime(rec, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
        from tests.test_commands import run
        for argv in (("todo", "show", "1.1"), ("todo", "brief", "1.1"), ("phase", "show", "1"), ("facts",)):
            code, out, err = run(*argv)
            self.assertEqual(code, 0, f"el {' '.join(argv)}: {out}{err}")
            self.assertEqual(rec.read_text(encoding="utf-8"), "older lines still to re-enter\n", argv)
            self.assertEqual(rec.stat().st_mtime_ns, 1_700_000_000_000_000_000, argv)  # round 24: its clock too

    def test_a_second_rebuild_adds_to_the_recover_file_never_over_it(self):
        """The same loss without a lock: a second hand edit rebuilt before the first one's lines were re-entered wrote
        its own lines over them."""
        self.ok("phase", "open", "1", "Plant", "--goal", "the shop works")
        j = self.case / "JOURNAL.md"
        rec = self.case / "JOURNAL.md.recover.md"
        j.write_text(j.read_text(encoding="utf-8").replace("\n- ", "\nFIRST STRAY LINE\n- ", 1), encoding="utf-8")
        self.ok("log", "DECISION", "keep the shop open")
        self.assertEqual(rec.read_text(encoding="utf-8"), "FIRST STRAY LINE\n")
        j.write_text(j.read_text(encoding="utf-8").replace("\n- ", "\nSECOND STRAY LINE\n- ", 1), encoding="utf-8")
        self.ok("log", "DECISION", "close at nine")
        self.assertEqual(rec.read_text(encoding="utf-8"), "FIRST STRAY LINE\nSECOND STRAY LINE\n")

    def test_a_refused_write_leaves_the_session_marks_as_they_were(self):
        """Round 12: a refused `readme --file` put the case back, but its «this session wrote here» mark stayed, and the
        next session was told so."""
        self._hand_edited_todo_behind_a_lock()
        self.ok("case", "new", "garden", "--goal", "the garden grows")
        hands = Path(os.environ["EL_HANDS_DIR"])
        marks = {p.name: p.read_bytes() for p in hands.iterdir() if p.is_file() and not p.name.endswith(("-walls.jsonl", "-calls.json"))}
        (Path(self.tmp.name) / "input.md").write_bytes((self.case / "README.md").read_bytes())
        from tests.test_commands import run
        code, out, err = run("--case", self.case.name, "readme", "--file", "input.md")
        self.assertEqual(code, 4, out + err)
        after = {p.name: p.read_bytes() for p in hands.iterdir() if p.is_file() and not p.name.endswith(("-walls.jsonl", "-calls.json"))}
        self.assertEqual(after, marks, err)

    def test_a_refused_done_gives_back_the_ask_it_did_not_show(self):
        """Round 13: a refused `todo done` spent the asks of an unsigned hand (three, then silence) without showing one."""
        self.ok("phase", "open", "1", "Plant", "--goal", "the shop works")
        self.ok("todo", "add", "1", "check the shop")
        (self.case / "docs").mkdir()
        doc = self.case / "docs" / "x.md"
        doc.write_text("# X\nsummary: first version\n", encoding="utf-8")
        self.ok("todo", "done", "1.1", "file:docs/x.md", "checked")
        doc.write_text("# X\nsummary: second version\n", encoding="utf-8")
        os.environ["EL_HINTS"] = "1"
        hands = Path(os.environ["EL_HANDS_DIR"])
        asks = lambda: {p.name: p.read_bytes() for p in hands.glob("*-asks")}  # noqa: E731
        before = asks()
        self.lock(self.case)
        from tests.test_commands import run
        for _ in range(3):
            code, out, err = run("todo", "done", "1.1", "file:docs/x.md", "checked the new version")
            self.assertEqual(code, 4, out + err)
        self.assertEqual(asks(), before)

    def _hand_locked_on(self, name: str):
        import re as _re
        from tests.test_commands import run
        self.assertEqual(run("case", "use", name)[0], 0)
        hand = next(p for p in Path(os.environ["EL_HANDS_DIR"]).iterdir()
                    if _re.fullmatch(r"[a-f0-9]{24}-[a-f0-9]{12}", p.name))
        hand.chmod(stat.S_IRUSR)
        self.locked.append(hand)
        return hand

    def test_case_use_that_cannot_keep_the_hand_is_refused(self):
        """Round 16: with the hand file read-only, `case use garden` said «current case: garden», and the next `log`
        wrote to the shop."""
        self.ok("case", "new", "garden", "--goal", "the garden grows")
        hand = self._hand_locked_on(self.case.name)
        before = hand.read_bytes()
        from tests.test_commands import run
        code, out, err = run("case", "use", "garden")
        self.assertEqual(code, 4, out + err)
        self.assertNotIn("current case", out)
        self.assertIn("cannot write", err)
        self.assertEqual(hand.read_bytes(), before)
        self.assertIn(f"# TODO — shop", run("todo")[1])

    def test_spawn_that_cannot_keep_the_hand_says_where_bare_commands_go(self):
        self.ok("phase", "open", "1", "Plant", "--goal", "the shop works")
        self._hand_locked_on(self.case.name)
        from tests.test_commands import run
        code, out, err = run("spawn", "field", "--goal", "the field grows")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("hand moves to the child", out)
        self.assertIn("hand not kept", out)
        self.assertIn("el --case", out)

    def test_the_door_case_new_prints_opens_the_new_case_when_the_hand_stays(self):
        """Round 18: with the old hand kept by a read-only file, `case new garden` printed `el phase open 1 …` — run as
        printed, it opened a phase in the shop."""
        import re as _re
        import shlex
        self._hand_locked_on(self.case.name)
        from tests.test_commands import run
        code, out, err = run("case", "new", "garden", "--goal", "the garden grows")
        self.assertEqual(code, 0, out + err)
        door = _re.search(r"now `([^`]+)`", out).group(1).replace("<Name>", "Plant").replace("\"…\"", "'the garden grows'")
        self.assertIn("--case", door, out)
        code, out, err = run(*shlex.split(door)[1:])
        self.assertEqual(code, 0, f"{door}: {out}{err}")
        garden = next((Path(self.tmp.name) / ".cases").glob("*-garden"))
        self.assertTrue(any((garden / "phases").glob("1-*.md")), out)
        self.assertFalse((self.case / "phases").exists() and any((self.case / "phases").glob("1-plant*.md")))

    def test_with_el_case_set_the_door_of_case_new_names_the_new_case(self):
        """Round 19: EL_CASE=shop in the shell, `case new garden` printed a door that opened a phase in the shop."""
        import re as _re
        import shlex
        os.environ["EL_CASE"] = self.case.name
        from tests.test_commands import run
        try:
            code, out, err = run("case", "new", "garden", "--goal", "the garden grows")
            self.assertEqual(code, 0, out + err)
            self.assertIn("EL_CASE=", out)
            door = _re.search(r"now `([^`]+)`", out).group(1).replace("<Name>", "Plant").replace("\"…\"", "'the garden grows'")
            code, out, err = run(*shlex.split(door)[1:])
            self.assertEqual(code, 0, f"{door}: {out}{err}")
        finally:
            os.environ.pop("EL_CASE", None)
        garden = next((Path(self.tmp.name) / ".cases").glob("*-garden"))
        self.assertTrue(any((garden / "phases").glob("1-*.md")))

    def test_an_el_case_the_new_case_makes_ambiguous_is_not_taken_for_here(self):
        """Round 20: EL_CASE=shop, then `case new zeta-shop` — the name now picks two cases; the door printed without
        --case failed exit 2 as printed."""
        import re as _re
        import shlex
        os.environ["EL_CASE"] = "shop"
        from tests.test_commands import run
        try:
            code, out, err = run("case", "new", "zeta-shop", "--goal", "the field grows")
            self.assertEqual(code, 0, out + err)
            door = _re.search(r"now `([^`]+)`", out).group(1).replace("<Name>", "Plant").replace("\"…\"", "'the field grows'")
            self.assertIn("--case", door, out)
            code, out, err = run(*shlex.split(door)[1:])
            self.assertEqual(code, 0, f"{door}: {out}{err}")
        finally:
            os.environ.pop("EL_CASE", None)

    def test_a_refusal_prints_no_look_door_an_ambiguous_el_case_would_refuse(self):
        """Round 21: EL_CASE named two cases; a refused `case new` still printed el status · el todo · el order, and each
        failed exit 2 as printed."""
        self.ok("case", "new", "zeta-shop", "--goal", "the field grows")
        os.environ["EL_CASE"] = "shop"
        cases = Path(self.tmp.name) / ".cases"
        self.lock(cases)
        from tests.test_commands import run
        try:
            code, out, err = run("case", "new", "garden", "--goal", "the garden grows")
            self.assertEqual(code, 4, out + err)
            self.assertNotIn("a look needs no write", err)
            self.assertIn("the same command where this session may write", err.strip().splitlines()[-1])
        finally:
            os.environ.pop("EL_CASE", None)

    def test_a_refused_spawn_gives_the_hand_and_the_mark_back(self):
        """Round 22: a hand-edited TODO beside a read-only recover file — spawn was refused late, the child was put back,
        but the hand and `.wrote` kept pointing at the child that no longer existed."""
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")
        todo = self.case / "TODO.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("\nstamp:", "\nSTRAY LINE\n\nstamp:"), encoding="utf-8")
        rec = self.case / "TODO.md.recover.md"
        rec.write_text("older lines\n", encoding="utf-8")
        rec.chmod(stat.S_IRUSR)
        self.locked.append(rec)
        hands = Path(os.environ["EL_HANDS_DIR"])
        marks = lambda: {p.name: p.read_bytes() for p in hands.iterdir()  # noqa: E731
                         if p.is_file() and not p.name.endswith(("-walls.jsonl", "-calls.json"))}
        before = marks()
        from tests.test_commands import run
        code, out, err = run("spawn", "child", "--goal", "the field grows")
        self.assertEqual(code, 4, out + err)
        self.assertEqual(list(self.case.glob("*-child")), [], err)
        self.assertEqual(marks(), before, err)
        self.assertIn("TODO — shop", run("todo")[1])

    def test_a_refused_spawn_keeps_the_journal_clock_a_fresh_session_follows(self):
        """Round 23: the refused spawn put the journal's bytes back with a new mtime — a fresh session, which goes where a
        write was last aimed, now went to the shop instead of the garden another session wrote last."""
        import time
        self.ok("phase", "open", "1", "Work", "--goal", "the shop works")
        os.environ["EL_SESSION"] = "other1108"
        time.sleep(0.02)
        self.ok("case", "new", "garden", "--goal", "the garden grows")
        os.environ["EL_SESSION"] = "doer1105"
        todo = self.case / "TODO.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("\nstamp:", "\nSTRAY LINE\n\nstamp:"), encoding="utf-8")
        rec = self.case / "TODO.md.recover.md"
        rec.write_text("older lines\n", encoding="utf-8")
        rec.chmod(stat.S_IRUSR)
        self.locked.append(rec)
        from tests.test_commands import run
        os.environ["EL_SESSION"] = "fresh0002"  # no hand of its own: it goes where a write was last aimed — the garden
        before = run("status")[1].splitlines()[0]
        self.assertTrue(before.endswith("-garden"), before)
        os.environ["EL_SESSION"] = "doer1105"  # its hand is on the shop: the spawn goes there, and is refused late
        code, out, err = run("spawn", "child", "--goal", "the field grows")
        self.assertEqual(code, 4, out + err)
        os.environ["EL_SESSION"] = "fresh0003"
        after = run("status")[1].splitlines()[0]
        os.environ["EL_SESSION"] = "doer1105"
        self.assertEqual(after, before, err)

    def test_a_system_refusal_under_case_keeps_the_case_in_its_doors(self):
        """Round 19: a denied folder in the case named by --case came through the last-resort net and printed look doors
        without --case — they showed the other case."""
        import shlex
        self.ok("case", "new", "garden", "--goal", "the garden grows")
        self.ok("case", "use", self.case.name)
        garden = next((Path(self.tmp.name) / ".cases").glob("*-garden"))
        self.lock(garden)
        from tests.test_commands import run
        code, out, err = run("--case", "garden", "phase", "open", "1", "Probe", "--goal", "the garden grows")
        self.assertEqual(code, 4, out + err)
        doors = err.split("a look needs no write: ", 1)[1].split(" — ", 1)[0].split(" · ")
        for door in doors:
            self.assertIn("--case", door, err)
            c, o, e = run(*shlex.split(door)[1:])
            self.assertEqual(c, 0, f"{door}: {o}{e}")
            if " order" not in door:  # `el order` acts on the case it is given and does not print its name
                self.assertIn("garden", o.splitlines()[0] + o[:400], door)

    def test_with_no_hand_the_door_follows_the_same_pick_as_the_hand(self):
        """Round 25: no hand of its own, a read-only hands folder, the shop's journal an hour ahead — `case new garden`
        assumed «last aimed = the new case» and printed a door that opened a phase in the shop."""
        import re as _re
        import shlex
        import time
        future = time.time_ns() + 3600 * 1_000_000_000
        os.utime(self.case / "JOURNAL.md", ns=(future, future))
        hands = Path(self.tmp.name) / "fresh-hands"
        hands.mkdir()
        hands.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.locked.append(hands)
        os.environ.update(EL_HANDS_DIR=str(hands), EL_SESSION="fresh1108")
        from tests.test_commands import run
        code, out, err = run("case", "new", "garden", "--goal", "the garden grows")
        self.assertEqual(code, 0, out + err)
        door = _re.search(r"now `([^`]+)`", out).group(1).replace("<Name>", "Plant").replace("\"…\"", "'the garden grows'")
        code, out, err = run(*shlex.split(door)[1:])
        self.assertEqual(code, 0, f"{door}: {out}{err}")
        garden = next((Path(self.tmp.name) / ".cases").glob("*-garden"))
        self.assertTrue(any((garden / "phases").glob("1-*.md")), door)

    def test_with_no_hand_of_its_own_spawn_says_nothing_untrue(self):
        """Round 17: with an empty, read-only hands folder spawn said bare commands would not follow to the child — they
        did, by the journal the spawn had just written."""
        self.ok("phase", "open", "1", "Plant", "--goal", "the shop works")
        hands = Path(self.tmp.name) / "no-hands"
        hands.mkdir()
        hands.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.locked.append(hands)
        os.environ["EL_HANDS_DIR"] = str(hands)
        from tests.test_commands import run
        code, out, err = run("spawn", "field", "--goal", "the field grows")
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("hand not kept", out)
        self.assertIn("TODO — field", run("todo")[1])

    def test_a_sampled_brief_over_a_denied_rebuild_is_refused_and_draws_nothing(self):
        """Round 26: `todo brief --sample` records its draw in the journal; read as a look, it skipped the end door —
        exit 0 over a denied rebuild, and the draw stayed."""
        self._hand_edited_todo_behind_a_lock()
        journal = self.case / "JOURNAL.md"
        before = journal.read_bytes()
        from tests.test_commands import run
        code, out, err = run("todo", "brief", "1.1", "--sample", "1")
        self.assertEqual(code, 4, out + err)
        self.assertEqual(journal.read_bytes(), before, err)
        self.assertEqual(run("todo", "brief", "1.1")[0], 0)  # the brief alone stays a look

    def test_sign_over_a_denied_write_is_refused(self):
        """Round 9: `el sign` returned before the end-of-command door and said exit 0 over a denied fill."""
        self._hand_edited_todo_behind_a_lock()
        from tests.test_commands import run
        os.environ.pop("EL_MODEL", None)
        hands = Path(os.environ["EL_HANDS_DIR"])
        signs_before = sorted(p.name for p in hands.glob("*-sign")) if hands.is_dir() else []
        code, out, err = run("sign", "Opus 5.5")  # 1.1 was done unsigned by this session: sign fills it — a write
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write", err)
        self.assertTrue((self.case / "TODO.md").is_symlink())
        # round 11: the refused sign had kept the new signature, and the next bare `el sign` read it
        self.assertEqual(sorted(p.name for p in hands.glob("*-sign")) if hands.is_dir() else [], signs_before, err)

    def test_a_refused_move_puts_an_executable_back_executable(self):
        """Round 24: the rollback put the bytes and the clock back through a temp file born 0600 — the script no longer
        ran."""
        for d in ("source", "target"):
            (self.case / d).mkdir()
        script = self.case / "source" / "run.sh"
        script.write_bytes(b"#!/bin/sh\necho ok\n")
        script.chmod(0o755)
        self.lock(self.case)  # README is denied after the move: the move is refused whole
        from tests.test_commands import run
        code, out, err = run("mv", "source/run.sh", "target/run.sh")
        self.assertEqual(code, 4, out + err)
        self.assertEqual(script.stat().st_mode & 0o777, 0o755, err)

    def test_a_write_keeps_the_mode_of_the_file_it_rewrites(self):
        """The same temp file under every ordinary write: a journal el rewrote came back 0600."""
        journal = self.case / "JOURNAL.md"
        journal.chmod(0o644)
        self.ok("log", "DECISION", "keep the shop open on Sundays")
        self.assertEqual(journal.stat().st_mode & 0o777, 0o644)

    def test_a_refused_binary_move_names_both_sides(self):
        (self.case / "source").mkdir()
        (self.case / "target").mkdir()
        (self.case / "source" / "a.bin").write_bytes(b"abc")
        self.lock(self.case / "target")
        from tests.test_commands import run
        code, out, err = run("mv", "source/a.bin", "target/a.bin")
        self.assertEqual(code, 4, out + err)
        first = err.splitlines()[0]
        self.assertIn("cannot move", first)
        self.assertIn("source/a.bin → ", first)
        self.assertIn("target/a.bin", first)
        self.assertTrue((self.case / "source" / "a.bin").is_file())


class _FreshProject(unittest.TestCase):
    """A project with no case yet, its own hands folder; folders listed in self.locked get write access back."""

    def setUp(self):
        from tests.test_long_case_1105 import ENVS
        self.saved = {k: os.environ.get(k) for k in ENVS + ("EL_ONBOARDING",)}
        for k in self.saved:
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.root = Path(self.tmp.name)
        os.environ.update(EL_HINTS="0", EL_TWO_HANDS="0", EL_RECITE="0", EL_HANDS_DIR=str(self.root / "hands"),
                          CLAUDECODE="1", EL_SESSION="first1108", EL_ONBOARDING="1")
        self.locked: list = []

    def tearDown(self):
        for p in self.locked:
            p.chmod(stat.S_IRWXU)
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes through any mode")
class TheFirstCase(_FreshProject):
    """The second hand, round 4, 2026-11-08: the first case of a project whose AGENTS.md links into a protected folder —
    the onboarding block was denied, the whole case was refused, an empty `.cases/` stayed, the output said «created»
    and «nothing was written» at once, and the look doors it printed refused over no case."""

    def test_a_denied_onboarding_block_leaves_the_first_case_standing(self):
        from tests.test_commands import run
        (self.root / "protected").mkdir()
        (self.root / "protected" / "instructions.md").write_text("# Mine\n", encoding="utf-8")
        (self.root / "CLAUDE.md").symlink_to("protected/instructions.md")
        (self.root / "protected").chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.locked.append(self.root / "protected")
        code, out, err = run("case", "new", "garden", "--goal", "the garden grows")
        self.assertEqual(code, 0, out + err)
        self.assertIn("created: .cases/", out)
        self.assertIn("onboarding block not written — CLAUDE.md", out)
        self.assertNotIn("nothing was written", out + err)
        self.assertEqual((self.root / "protected" / "instructions.md").read_text(encoding="utf-8"), "# Mine\n")
        for argv in ((), ("todo",), ("order",)):
            self.assertEqual(run(*argv)[0], 0, argv)

    def test_a_refused_first_case_leaves_no_empty_space(self):
        from tests.test_commands import run
        code, out, err = run("case", "new", "garden", "--goal", "the garden grows [wrongkind: y]")
        self.assertNotEqual(code, 0, out + err)
        self.assertFalse((self.root / ".cases").exists())

    def test_with_no_case_to_look_at_no_look_door_is_printed(self):
        from tests.test_commands import run
        self.root.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.locked.append(self.root)
        code, out, err = run("case", "new", "garden", "--goal", "the garden grows")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write", err)
        self.assertNotIn("el status · el todo · el order", err)
        self.assertIn("the same command where this session may write", err.strip().splitlines()[-1])


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes through any mode")
class AMigrationTheSystemDenies(_FreshProject):
    """Round 14: `migrate --apply` kept its own archive and phase writes outside the command's rollback — a denied phase
    file came back as exit 1 with a raw errno and no door, and with read-only originals as «nothing was written» over
    three new archive files."""

    def legacy_case(self, readonly_originals: bool) -> Path:
        c = self.root / ".cases" / "2026-11-08-old"
        c.mkdir(parents=True)
        for name, body in (("README.md", "# Old\n\n## Goal\nthe shop works\n"),
                           ("TODO.md", "# TODO\n\n## Finished\n- [x] inspected the shop\n"),
                           ("JOURNAL.md", "# Journal\n\n## Yesterday\n- checked the shop\n")):
            (c / name).write_text(body, encoding="utf-8")
            if readonly_originals:
                (c / name).chmod(stat.S_IRUSR)
                self.locked.append(c / name)
        (c / "phases").mkdir()
        (c / "phases").chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.locked.append(c / "phases")
        return c

    def check(self, readonly_originals: bool):
        from tests.test_commands import run
        c = self.legacy_case(readonly_originals)
        before = sorted(str(p.relative_to(c)) for p in c.rglob("*"))
        code, out, err = run("--case", c.name, "migrate", "--apply")
        self.assertEqual(code, 4, out + err)
        self.assertIn("cannot write", err)
        self.assertIn("nothing was written", err)
        self.assertEqual(sorted(str(p.relative_to(c)) for p in c.rglob("*")), before, err)

    def test_a_denied_phase_file_is_refused_as_el_refuses(self):
        self.check(readonly_originals=False)

    def test_with_read_only_originals_no_archive_stays(self):
        self.check(readonly_originals=True)

    def test_a_migration_refused_at_its_parents_line_takes_its_archive_away(self):
        """Round 15: the migration itself went through, then the parent's README was denied — the case files came back,
        the archive stayed under «nothing was written»."""
        from tests.test_commands import run
        for argv in (("case", "new", "parent", "--goal", "the shop works"), ("phase", "open", "1", "First", "--goal", "the shop works"),
                     ("spawn", "child", "--goal", "the field grows")):
            code, out, err = run(*argv)
            self.assertEqual(code, 0, f"{argv}: {out}{err}")
        parent = next(p for p in (self.root / ".cases").iterdir() if p.is_dir())
        child = next(parent.glob("*-child"))
        for name, body in (("README.md", "# Old child\n\n## Goal\nthe field grows\n"),
                           ("TODO.md", "# TODO\n\n## Finished\n- [x] inspected the field\n"),
                           ("JOURNAL.md", "# Journal\n\n## Yesterday\n- checked the field\n")):
            (child / name).write_text(body, encoding="utf-8")
        before = sorted(str(p.relative_to(self.root)) for p in (self.root / ".cases").rglob("*"))
        parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.locked.append(parent)
        code, out, err = run("--case", child.name, "migrate", "--apply")
        self.assertEqual(code, 4, out + err)
        self.assertEqual(sorted(str(p.relative_to(self.root)) for p in (self.root / ".cases").rglob("*")), before, err)


@unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes through any mode")
class TheRestOfRound15(_FreshProject):
    def test_a_refused_feedback_leaves_no_empty_report(self):
        """Round 15: under umask 0222 the reserved report could not be written, and the empty file stayed."""
        from tests.test_commands import run
        folder = self.root / "feedback"
        folder.mkdir()
        saved = os.environ.get("EL_FEEDBACK_DIR")
        os.environ["EL_FEEDBACK_DIR"] = str(folder)
        old = os.umask(0o222)
        try:
            code, out, err = run("feedback", "write denied", "--actual", "the file cannot be written",
                                 "--expected", "a refusal without leftovers", "--onboarding", "enough")
        finally:
            os.umask(old)
            if saved is None:
                os.environ.pop("EL_FEEDBACK_DIR", None)
            else:
                os.environ["EL_FEEDBACK_DIR"] = saved
        self.assertEqual(code, 4, out + err)
        self.assertEqual(list(folder.iterdir()), [], err)

    def test_the_printed_readme_file_door_runs_from_where_el_runs(self):
        """Round 15: Order printed `el readme --file README.md`; from the project root it died in a traceback."""
        from tests.test_commands import run
        import shlex
        for argv in (("case", "new", "shop", "--goal", "the shop works"), ("phase", "open", "1", "First", "--goal", "the shop works"),
                     ("todo", "add", "1", "check the shop"), ("todo", "done", "1.1", "owner", "checked")):
            code, out, err = run(*argv)
            self.assertEqual(code, 0, f"{argv}: {out}{err}")
        code, out, err = run("order")
        line = next(ln for ln in out.splitlines() if "State is behind" in ln)
        door = line.rsplit("· or ", 1)[1]
        self.assertTrue(door.startswith("el readme --file "), line)
        code, out, err = run(*shlex.split(door)[1:])
        self.assertEqual(code, 0, f"{door}: {out}{err}")
        code, out, err = run("readme", "--file", "README.md")  # a path that is not there: a refusal with the path that is
        self.assertEqual(code, 2, out + err)
        self.assertNotIn("Traceback", out + err)
        self.assertIn("el readme --file .cases/", err)


class NoTempFolder(Base):
    def test_the_entry_reads_where_no_temp_folder_can_be_written(self):
        from tests.test_commands import run
        os.environ.pop("EL_HANDS_DIR", None)
        boom = FileNotFoundError(2, "No usable temporary directory found")
        with mock.patch.object(tempfile, "gettempdir", side_effect=boom):
            code, out, err = run()
            self.assertEqual(code, 0, out + err)
            self.assertNotIn("Traceback", out + err)
            self.assertIn("thread:", out)
            code, out, err = run("log", "DECISION", "open on Sundays")  # the case may be written: the work goes on
            self.assertEqual(code, 0, out + err)


if __name__ == "__main__":
    unittest.main()
