"""Two reports of one live session, 2026-10-10. A session did its first done before `el sign` and the done: line kept
`model ?` for good — the model was named one call later (on disk: 21 sessions, 62 such lines). And `el todo edit 1.6
note '…'` took «note …» as the item's new words: a long one was refused with a suggestion that kept the mistake, a
short one replaced the item text with exit 0. And a third of the same day: a length refusal's ready cut moved a goal's
proof slot into a note."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

HARNESS = ("--as", "Anthropic Claude Code")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS", "EL_MODEL")}
        os.environ.update(EL_HINTS="0", EL_SESSION="aaaa1010", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"), EL_TWO_HANDS="0")
        os.environ.pop("EL_MODEL", None)
        run("case", "new", "errand", "--goal", "the parcel is in hand")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-errand"))
        run("phase", "open", "1", "Find", "--goal", "find it")

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

    def line(self, ref, kind):
        lines = self.todo().split("\n")
        at = next(i for i, ln in enumerate(lines) if f" {ref} " in ln)
        return next(ln for ln in lines[at + 1:] if ln.strip().startswith(f"- {kind}:"))

    def as_session(self, sid):
        os.environ["EL_SESSION"] = sid


class TheModelSaidLaterFillsTheSessionsLines(Base):
    def test_a_done_before_the_sign_carries_the_model_after_it(self):
        run("todo", "add", "1", "read the order letter")
        run("todo", "done", "1.1", "owner", "the order number is found")
        self.assertIn("model ? · session aaaa1010", self.line("1.1", "done"))
        code, out, err = run("sign", "Opus 5.5", *HARNESS)
        self.assertEqual(code, 0, err)
        self.assertIn("filled: 1 line(s) this session wrote before it named its model", out)
        self.assertIn("Anthropic Claude Code · Opus 5.5 · session aaaa1010", self.line("1.1", "done"))
        self.assertEqual(run("check")[0], 0)

    def test_another_sessions_lines_are_not_touched(self):
        run("todo", "add", "1", "read the order letter")
        self.as_session("bbbb1010")
        run("todo", "done", "1.1", "owner", "found")
        self.as_session("aaaa1010")
        _, out, _ = run("sign", "Opus 5.5", *HARNESS)
        self.assertNotIn("filled:", out)
        self.assertIn("model ? · session bbbb1010", self.line("1.1", "done"))

    def test_an_acceptance_says_its_engine_word_again(self):
        run("todo", "add", "1", "read the order letter")
        self.as_session("bbbb1010")
        run("sign", "Sonnet 5.5", *HARNESS)
        run("todo", "done", "1.1", "owner", "found")
        self.as_session("aaaa1010")
        run("todo", "accept", "1.1", "--by", "claude", "opened the letter")
        self.assertIn("harness ? · model ? · session aaaa1010", self.line("1.1", "accepted"))
        run("sign", "Opus 5.5", *HARNESS)
        self.assertIn("another model: Anthropic Claude Code · Opus 5.5 · session aaaa1010", self.line("1.1", "accepted"))

    def test_a_subagents_acceptance_keeps_its_own_mind(self):
        run("todo", "add", "1", "read the order letter")
        run("todo", "done", "1.1", "owner", "found")
        run("todo", "accept", "1.1", "--by", "subagent", "opened the letter")
        run("sign", "Opus 5.5", *HARNESS)
        self.assertIn("Opus 5.5 · session aaaa1010", self.line("1.1", "done"))
        self.assertIn("· model ? · session aaaa1010", self.line("1.1", "accepted"))

    def test_a_closed_phases_file_is_filled_too(self):
        run("todo", "add", "1", "read the order letter")
        run("todo", "done", "1.1", "owner", "found")
        code, _, err = run("phase", "close", "1", "found", "--reflect", "r", "--align", "a", "--howto", "none: t")
        self.assertEqual(code, 0, err)
        pf = next((self.case / "phases").glob("1-*.md"))
        self.assertIn("model ? · session aaaa1010", pf.read_text(encoding="utf-8"))
        _, out, _ = run("sign", "Opus 5.5", *HARNESS)
        self.assertIn(f"phases/{pf.name} 1", out)
        self.assertIn("Anthropic Claude Code · Opus 5.5 · session aaaa1010", pf.read_text(encoding="utf-8"))
        self.assertNotIn("model ?", pf.read_text(encoding="utf-8"))

    def test_signing_outside_a_project_still_works(self):
        run("todo", "add", "1", "read the order letter")
        run("todo", "done", "1.1", "owner", "found")
        with tempfile.TemporaryDirectory() as elsewhere:
            os.chdir(elsewhere)
            code, out, err = run("sign", "Opus 5.5", *HARNESS)
        self.assertEqual(code, 0, err)
        self.assertNotIn("filled:", out)


class APocketWordIsThePocket(Base):
    def setUp(self):
        super().setUp()
        run("todo", "add", "1", "watch the parcel")

    def test_edit_with_note_as_its_own_word_is_refused_with_the_note_command(self):
        code, _, err = run("todo", "edit", "1.1", "note", "the bot sees delivery on the 12th")
        self.assertEqual(code, 2)
        self.assertIn('el todo note 1.1 "the bot sees delivery on the 12th"', err)
        self.assertIn("1.1 watch the parcel", self.todo())

    def test_a_long_note_is_refused_the_same_way_not_on_length(self):
        long = "chat 10 Oct: the bot sees delivery on Oct 12, no live agent — [chat](evidence/x.md); sms waits the owner's word"
        code, _, err = run("todo", "edit", "1.1", "note", long)
        self.assertEqual(code, 2)
        self.assertNotIn("el todo edit 1.1 'note", err)
        self.assertIn("el todo note 1.1", err)

    def test_the_pocket_line_form_is_the_pocket(self):
        code, _, err = run("todo", "edit", "1.1", "note: the bot sees it")
        self.assertEqual(code, 2)
        self.assertIn('el todo note 1.1 "the bot sees it"', err)

    def test_the_items_own_words_pass_as_one_quoted_text(self):
        code, out, err = run("todo", "edit", "1.1", "note the codes down")
        self.assertEqual(code, 0, err)
        self.assertIn("1.1 note the codes down", self.todo())

    def test_add_under_an_item_does_not_make_a_note_a_sub_item(self):
        code, _, err = run("todo", "add", "1.1", "note", "the bot sees it")
        self.assertEqual(code, 2)
        self.assertNotIn("1.1.1", self.todo())
        self.assertIn('el todo note 1.1 "the bot sees it"', err)

    def test_add_to_a_phase_names_the_phase_note_and_the_flag(self):
        code, _, err = run("todo", "add", "1", "why", "the owner asked")
        self.assertEqual(code, 2)
        self.assertIn('el todo add 1 "…" --why "the owner asked"', err)


class TheReview(Base):
    """The Codex review of batch 25, 2026-10-10: five edges, each kept here."""

    def test_1_a_bare_pocket_word_does_not_become_the_item(self):
        run("todo", "add", "1", "original")
        for words in (("note",), ("note:",)):
            code, _, err = run("todo", "edit", "1.1", *words)
            self.assertEqual(code, 2, err)
        self.assertIn("1.1 original", self.todo())

    def test_2_an_open_phases_file_is_the_agents_page(self):
        pf = next((self.case / "phases").glob("1-*.md"))
        pf.write_text(pf.read_text(encoding="utf-8") + "\n## Example\n  - done: harness ? · model ? · session aaaa1010 · 2026-10-10\n",
                      encoding="utf-8")
        before = pf.read_text(encoding="utf-8")
        run("sign", "X", *HARNESS)
        self.assertEqual(pf.read_text(encoding="utf-8"), before)

    def test_3_a_todo_with_nothing_to_fill_is_not_opened_through_the_door(self):
        run("todo", "add", "1", "original")
        self.as_session("bbbb1010")
        run("todo", "done", "1.1", "owner", "found")
        todo = self.case / "TODO.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("\nstamp:", "\nKEEP THIS NOTE\nstamp:"), encoding="utf-8")
        before = todo.read_text(encoding="utf-8")
        self.as_session("aaaa1010")
        run("sign", "X", *HARNESS)
        self.assertEqual(todo.read_text(encoding="utf-8"), before)
        self.assertFalse((self.case / "TODO.md.recover.md").exists())

    def test_4_the_door_works_for_a_later_line_and_a_list(self):
        run("todo", "add", "1", "a")
        run("todo", "add", "1", "b")
        run("todo", "add", "later", "warm the cache")
        _, _, err = run("todo", "edit", "L1", "note", "hello")
        self.assertIn('el todo note L1 "hello"', err)
        _, _, err = run("todo", "edit", "1.1, 1.2", "note", "hello")
        self.assertIn('el todo note 1.1, 1.2 "hello"', err)
        _, _, err = run("todo", "add", "later", "note", "hello")
        self.assertIn('el todo add later "…" --note "hello"', err)
        self.assertNotIn("el phase note later", err)
        self.assertEqual(run("todo", "note", "L1", "hello")[0], 0)

    def test_5_the_model_is_put_in_literally(self):
        run("todo", "add", "1", "read")
        run("todo", "done", "1.1", "owner", "found")
        code, _, err = run("sign", "X\\Y", *HARNESS)
        self.assertEqual(code, 0, err)
        self.assertIn("X\\Y · session aaaa1010", self.line("1.1", "done"))


class TheSecondReview(Base):
    """The second Codex round of batch 25, 2026-10-10: six edges the first fixes left."""

    def hand_edit(self, old, new):
        todo = self.case / "TODO.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    def test_1_the_same_words_in_a_note_are_not_a_signature(self):
        run("todo", "add", "1", "original")
        run("todo", "note", "1.1", "model ? · session aaaa1010")
        self.hand_edit("1.1 original", "1.1 hand edited")
        before = (self.case / "TODO.md").read_text(encoding="utf-8")
        run("sign", "X", *HARNESS)
        self.assertEqual((self.case / "TODO.md").read_text(encoding="utf-8"), before)

    def test_2_a_note_that_starts_with_a_dash_gets_no_command_that_drops_one(self):
        run("todo", "add", "1", "original")
        run("todo", "note", "1.1", "KEEP")
        code, _, err = run("todo", "edit", "1.1", "--", "note", "--drop=1")
        self.assertEqual(code, 2)
        self.assertNotIn('el todo note 1.1 "--drop=1"', err)
        self.assertIn("begin it with a word", err)
        self.assertIn("KEEP", self.todo())

    def test_3_later_lines_take_a_note_one_at_a_time(self):
        for text in ("first", "second", "third"):
            run("todo", "add", "later", text)
        _, _, err = run("todo", "edit", "L1, L3", "note", "hello")
        self.assertIn('el todo note L1 "hello" — one item at a time', err)

    def test_4_and_5_a_repaired_todo_is_filled_and_the_repair_is_said(self):
        run("todo", "add", "1", "original")
        run("todo", "done", "1.1", "owner", "found")
        self.hand_edit("\nstamp:", "\nKEEP THIS NOTE\nstamp:")
        code, out, err = run("sign", "X", *HARNESS)
        self.assertEqual(code, 0, err)
        self.assertIn("filled: 1 line(s)", out)
        self.assertIn("warning:", err)
        self.assertIn("X · session aaaa1010", self.line("1.1", "done"))

    def test_6_a_doer_filled_now_is_the_same_model_as_one_said_on_the_call(self):
        saved = os.environ.get("CLAUDECODE")
        os.environ["CLAUDECODE"] = "1"  # the harness names itself, as Claude Code does
        try:
            run("todo", "add", "1", "original")
            run("todo", "done", "1.1", "owner", "found")
            os.environ["EL_MODEL"] = "X"
            run("todo", "accept", "1.1", "--by", "claude", "opened it")
            os.environ.pop("EL_MODEL")
            self.assertIn("model not given: Anthropic Claude Code · X · session aaaa1010", self.line("1.1", "accepted"))
            run("sign", "X")
            self.assertIn("same model: Anthropic Claude Code · X · session aaaa1010", self.line("1.1", "accepted"))
        finally:
            if saved is None:
                os.environ.pop("CLAUDECODE", None)
            else:
                os.environ["CLAUDECODE"] = saved

    def test_7_the_own_words_door_is_printed_only_where_it_works(self):
        run("todo", "add", "1", "original")
        run("todo", "add", "1.1", "child")
        _, _, err = run("todo", "add", "1.1.1", "note", "hello")
        self.assertNotIn('el todo add 1.1.1 "note hello"', err)
        self.assertIn('el todo note 1.1.1 "hello"', err)


class TheThirdReview(Base):
    """The third Codex round of batch 25, 2026-10-10: five more edges (the sixth — two sessions sharing an eight-character
    id are one hand — is how el tells hands apart everywhere; accepted with its reason, not fixed)."""

    def test_2_a_colon_pocket_followed_by_words_is_the_pocket(self):
        run("todo", "add", "1", "original")
        code, _, err = run("todo", "edit", "1.1", "note: hello", "world")
        self.assertEqual(code, 2)
        self.assertIn('el todo note 1.1 "hello world"', err)
        self.assertIn("1.1 original", self.todo())

    def test_3_a_subagents_hole_alone_does_not_open_the_door(self):
        run("sign", "X", *HARNESS)
        run("todo", "add", "1", "original")
        run("todo", "done", "1.1", "owner", "found")
        run("todo", "accept", "1.1", "--by", "subagent", "opened it")
        todo = self.case / "TODO.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("\nstamp:", "\nKEEP THIS NOTE\nstamp:"), encoding="utf-8")
        before = todo.read_text(encoding="utf-8")
        run("sign", "X", *HARNESS)
        self.assertEqual(todo.read_text(encoding="utf-8"), before)

    def test_4_an_unreadable_todo_elsewhere_does_not_stop_the_sign(self):
        run("case", "new", "other", "--goal", "x")
        other = next(Path(self.tmp.name, ".cases").glob("*-other"))
        (other / "TODO.md").write_bytes(b"\xff\xfe broken")
        os.environ["EL_CASE"] = self.case.name
        try:
            run("todo", "add", "1", "original")
            run("todo", "done", "1.1", "owner", "found")
            code, out, err = run("sign", "X", *HARNESS)
        finally:
            os.environ.pop("EL_CASE", None)
        self.assertEqual(code, 0, err)
        self.assertIn("filled: 1 line(s)", out)

    def test_5_a_list_across_phases_takes_its_note_one_item_at_a_time(self):
        run("todo", "add", "1", "a")
        run("phase", "plan", "2", "Next", "--goal", "x")
        run("todo", "add", "2", "b")
        _, _, err = run("todo", "edit", "1.1, 2.1", "note", "hello")
        self.assertIn('el todo note 1.1 "hello" — one item at a time', err)

    def test_6_a_dash_text_on_a_later_line_still_names_the_move(self):
        run("todo", "add", "later", "warm the cache")
        _, _, err = run("todo", "edit", "L1", "--", "expect", "--drop=1")
        self.assertIn("a Later line takes no expect: el todo move L1 N", err)
        self.assertIn("begin it with a word", err)


class TheFourthReview(Base):
    """The fourth Codex round of batch 25, 2026-10-10: four more edges, each with a printed command run as printed."""

    def test_1_a_spaced_list_is_printed_back_as_the_list_main_gathers(self):
        run("todo", "add", "1", "first")
        run("todo", "add", "1", "second")
        _, _, err = run("todo", "edit", "1.1 , 1.2", "note", "hello")
        self.assertIn('el todo note 1.1, 1.2 "hello"', err)

    def test_2_a_stray_line_in_todo_does_not_hide_a_closed_phases_hole(self):
        run("todo", "add", "1", "first")
        run("todo", "done", "1.1", "owner", "found")
        run("phase", "close", "1", "found", "--reflect", "r", "--align", "a", "--howto", "none: t")
        todo = self.case / "TODO.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("\nstamp:", "\nKEEP THIS NOTE\nstamp:"), encoding="utf-8")
        before = todo.read_text(encoding="utf-8")
        _, out, _ = run("sign", "X", *HARNESS)
        pf = next((self.case / "phases").glob("1-*.md"))
        self.assertIn("Anthropic Claude Code · X · session aaaa1010", pf.read_text(encoding="utf-8"))
        self.assertEqual(todo.read_text(encoding="utf-8"), before)

    def test_3_the_harness_named_after_the_model_reaches_the_earlier_lines(self):
        run("todo", "add", "1", "first")
        run("todo", "done", "1.1", "owner", "found")
        run("sign", "X")
        self.assertIn("harness ? · X · session aaaa1010", self.line("1.1", "done"))
        _, out, _ = run("sign", "X", *HARNESS)
        self.assertIn("Anthropic Claude Code · X · session aaaa1010", self.line("1.1", "done"))
        self.assertIn("filled: 1 line(s)", out)

    def test_4_a_range_gets_the_note_command_that_takes_it(self):
        run("todo", "add", "1", "first")
        run("todo", "add", "1", "second")
        _, _, err = run("todo", "edit", "1.1-1.2", "note", "hello")
        self.assertIn('el todo note 1.1-1.2 "hello"', err)
        self.assertNotIn("el todo add 1.1-1.2", err)
        self.assertEqual(run("todo", "note", "1.1-1.2", "hello")[0], 0)

    def test_5_every_range_spelling_gets_the_same_command(self):
        run("todo", "add", "1", "first")
        run("todo", "add", "1", "second")
        for spelled in ("1.1 - 1.2", "1.1–1.2"):
            _, _, err = run("todo", "edit", spelled, "note", "hello")
            self.assertIn('el todo note 1.1-1.2 "hello"', err, spelled)
            self.assertNotIn("el todo add 1.1", err, spelled)


class AGoalKeepsItsPromise(Base):
    """A third report of the same day (2026-10-10, el's own maintainer): `phase plan` with a goal of 122 chars ending in
    a proof slot was refused on length — rightly — with a ready command that moved `[run: …]` into a phase note."""

    def test_no_ready_cut_carries_a_slot_out_of_the_goal(self):
        goal = ("the document of the case is accepted by deriving from its sources: a bad one returned, a good one "
                "accepted [run: polygon]")
        code, _, err = run("phase", "plan", "2", "Acceptance", "--goal", goal)
        self.assertEqual(code, 3)
        self.assertNotIn("el phase note 2", err)
        self.assertIn("no ready cut: the words after the boundary of meaning carry [run: polygon]", err)

    def test_a_cut_without_a_slot_is_still_offered(self):
        goal = ("the document of the case is accepted by deriving from its sources: a bad one returned, a good one "
                "accepted, and so on")
        _, _, err = run("phase", "plan", "2", "Acceptance", "--goal", goal)
        self.assertIn("el phase note 2", err)


if __name__ == "__main__":
    unittest.main()
