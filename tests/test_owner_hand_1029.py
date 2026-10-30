"""Batch 47, 2026-10-29: el says about who waits and who works only what it knows — from a live run on a real project
(a fresh Sonnet session accepted 8 of 9 items as the second hand and told the owner in chat what waits for him) and the
Codex review of the design that followed.

1. A look took the hand and was announced as work: a session that only ran `el case list` made the next session's entry
   say «another session (…) holds it since 23:11», and the agent passed it to the owner as a fact. A bookmark is not work:
   the note says when the last write went there, and names no occupant.
2. The hand file was named by the 8 chars of the session: `shared01-A` and `shared01-B` shared one hand, and a bare
   command of one landed in the case the other had taken. The exact session keys the file; the old file is still read.
3. Eight acceptances left «next: a fresh session accepts 1.1–1.4…» in README and Order said nothing: freshness counted RESULT
   and PHASE. el's own DECISIONs that change the work (accepted, sent back, cancelled) make State behind too; and setting
   one State line (`owner:`) no longer certifies the whole State — only `next:` and `touch` read it whole.
4. What waits for the owner, as far as the structure says, is drawn by el right under `opened:` — the scope of a running
   phase, the word that closes a ready case, done items for a second hand — and made true by the write that changed it,
   not by the next entry the agent may never make. The agent's own `owner:` line stands under it.
5. Two printed commands of Order were refused when run (Codex, 2026-10-29): «every phase ended … el done» over a Context
   promise no phase proved, and `accept 1.1-1.3` over an open 1.2. The gate `done` asks and the span `accept` takes have one
   owner each, and Order prints through it.
6. The Codex inspection of the batch (2026-10-30): the side write of the owner line rebuilt a hand-edited README behind a
   command that succeeded; the printed `--howto <…>` broke the shell; a hand read from the old 8-char file stayed shared
   while an older el moved it; `case new` and `spawn` left no write mark."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import store
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
        os.environ.update(EL_HINTS="0", EL_RECITE="0", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"),
                          EL_SESSION="maker1029")
        self.ok("case", "new", "work", "--goal", "the work is done")

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

    def case(self, name: str = "work") -> Path:
        return next(Path(self.tmp.name, ".cases").glob(f"*-{name}"))


class ALookIsNotWork(Base):
    def test_a_session_that_only_looked_is_not_announced_to_the_next(self):
        for look in (("case", "list"), ("order",), ()):
            os.environ["EL_SESSION"] = "looker01"
            self.ok(*look)
            os.environ["EL_SESSION"] = f"fresh{len(look)}x"
            out, err = self.ok()
            self.assertNotIn("holds it", out + err)
            self.assertNotIn("looker01", out + err)

    def test_a_session_that_wrote_is_named_with_the_time_of_its_write(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        os.environ["EL_SESSION"] = "fresh0001"
        out, _ = self.ok()
        self.assertIn("note: this session had no case in hand and took", out)
        self.assertIn("session maker1029 wrote here at ", out)
        self.assertIn("if it works here now, take your own: el case use <name>", out)
        self.assertNotIn("holds it", out)

    def test_one_session_working_alone_hears_nothing(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        os.environ["EL_SESSION"] = "maker1029"
        out, err = self.ok("todo", "add", "1", "a step")
        self.assertNotIn("wrote here", out + err)


class TheExactSessionKeepsItsHand(Base):
    def test_two_sessions_with_one_beginning_keep_two_hands(self):
        os.environ["EL_SESSION"] = "shared01-A"
        self.ok("case", "use", self.case().name)
        os.environ["EL_SESSION"] = "shared01-B"
        self.ok("case", "new", "other", "--goal", "another work")
        os.environ["EL_SESSION"] = "shared01-A"
        out, _ = self.ok("status")
        self.assertIn(f"case in hand: {self.case().name}", out)

    def test_a_hand_kept_by_an_older_el_is_still_read(self):
        self.ok("case", "new", "other", "--goal", "another work")
        os.environ["EL_SESSION"] = "legacy01"
        old = Path(os.environ["EL_HANDS_DIR"]) / store._hand_file(store.find_root(self.case()), legacy=True).name
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_text(os.path.relpath(self.case().resolve(), Path(self.tmp.name, ".cases").resolve().parent), encoding="utf-8")
        out, _ = self.ok("status")
        self.assertIn(f"case in hand: {self.case().name}", out, "the session keeps the case its old file named")


class Freshness(Base):
    def setUp(self):
        super().setUp()
        os.environ["EL_TWO_HANDS"] = "1"
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        self.ok("phase", "agree", "1", "the owner agreed")
        self.ok("todo", "add", "1", "a step")
        self.ok("todo", "done", "1.1", "run:make → OK", "the step is done")
        self.ok("readme", "set", "next", "a fresh session accepts 1.1")

    def order(self):
        return self.ok("order")[0]

    def test_an_acceptance_makes_state_behind(self):
        self.assertNotIn("State is behind", self.order())
        os.environ["EL_SESSION"] = "second01"
        self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "make → OK", "re-ran, the same")
        self.assertIn("1 accepted, sent back or cancelled", self.order())
        self.ok("readme", "set", "next", "close phase 1")
        self.assertNotIn("State is behind", self.order())

    def test_an_owner_line_does_not_certify_a_stale_next(self):
        os.environ["EL_SESSION"] = "second01"
        self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "make → OK", "re-ran, the same")
        out, _ = self.ok("readme", "set", "owner", "answer five cards")
        self.assertIn("State's `as of` stays", out)
        self.assertIn("State is behind", self.order())
        self.ok("readme", "touch")
        self.assertNotIn("State is behind", self.order())


class OwnerWaits(Base):
    """README is read right after each write — no bare `el` in between, as the live agent ended its session."""
    def setUp(self):
        super().setUp()
        os.environ["EL_TWO_HANDS"] = "1"

    def state(self):
        body = (self.case() / "README.md").read_text(encoding="utf-8")
        return [ln for ln in body.split("## State", 1)[1].split("## ", 1)[0].split("\n") if ln.startswith("- ")]

    def waits(self):
        return next((ln for ln in self.state() if ln.startswith("- waits for the owner: ")), None)

    def test_the_scope_and_the_second_hand_follow_each_write(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        self.assertEqual(self.waits(), "- waits for the owner: your scope for phase 1 Work")
        self.ok("phase", "agree", "1", "the owner agreed")
        self.assertIsNone(self.waits(), "the agreed scope leaves the line at once")
        self.ok("todo", "add", "1", "a step")
        self.ok("todo", "done", "1.1", "run:make → OK", "the step is done")
        self.assertEqual(self.waits(), "- waits for the owner: 1 done item for a second hand — a fresh session or your word")
        os.environ["EL_SESSION"] = "second01"
        self.ok("todo", "accept", "1.1", "--by", "subagent", "--run", "make → OK", "re-ran, the same")
        self.assertIsNone(self.waits())

    def test_a_ready_case_waits_for_the_owners_word_and_his_word_ends_both_lines(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        self.ok("phase", "agree", "1", "the owner agreed")
        self.ok("todo", "add", "1", "a step")
        self.ok("todo", "done", "1.1", "owner", "the step is done")
        self.ok("todo", "accept", "1.1", "--by", "owner", "fine")
        self.ok("phase", "close", "1", "done", "--reflect", "r", "--align", "a")
        self.ok("readme", "set", "owner", "say whether it ships")
        self.ok("done", "the work is done")
        lines = self.state()
        self.assertTrue(lines[0].startswith("- opened: "), lines)
        self.assertEqual(lines[1], "- waits for the owner: your word that closes the case — it is ready")
        self.assertEqual(lines[2], "- owner: say whether it ships")
        self.ok("done", "--by", "owner", "ship it")
        self.assertIsNone(self.waits())
        self.assertFalse(any(ln.startswith("- owner: ") for ln in self.state()), "nothing waits for the owner of a closed case")

    def test_work_done_in_a_planned_phase_waits_for_a_second_hand_too(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        self.ok("phase", "agree", "1", "the owner agreed")
        self.ok("phase", "plan", "2", "Later", "--goal", "later work")
        self.ok("todo", "add", "2", "a later step")
        self.ok("todo", "done", "2.1", "owner", "done out of turn")  # the replay of 2026-10-30: 4.4 in a planned phase
        self.assertEqual(self.waits(), "- waits for the owner: 1 done item for a second hand — a fresh session or your word")

    def test_the_line_is_els_and_is_not_set_by_hand(self):
        code, _, err = run("readme", "set", "waits for the owner", "nothing")
        self.assertEqual(code, 2, err)
        self.assertIn("held by el", err)


class OrderPrintsWhatWorks(Base):
    def setUp(self):
        super().setUp()
        os.environ["EL_TWO_HANDS"] = "1"

    def test_every_phase_ended_says_what_done_asks_first(self):
        self.ok("readme", "edit", "context", "goal", "the work is done [file: signed contract]")
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        self.ok("phase", "agree", "1", "the owner agreed")
        self.ok("todo", "add", "1", "a step")
        self.ok("todo", "done", "1.1", "owner", "the step is done")
        self.ok("todo", "accept", "1.1", "--by", "owner", "fine")
        self.ok("phase", "close", "1", "done", "--reflect", "r", "--align", "a")
        out, _ = self.ok("order")
        line = next(ln for ln in out.split("\n") if "every phase ended" in ln)
        self.assertIn("before el done: it promised [file: signed contract] in Context", line)
        self.assertNotIn('el done "what came out"', line)
        code, _, err = run("done", "what came out")
        self.assertEqual(code, 4, "done refuses what Order now says first")

    def test_a_span_of_acceptance_never_crosses_an_open_item(self):
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        self.ok("phase", "agree", "1", "the owner agreed")
        for step in ("one", "two", "three"):
            self.ok("todo", "add", "1", step)
        self.ok("todo", "done", "1.1", "owner", "one is done")
        self.ok("todo", "done", "1.3", "owner", "three is done")
        out, _ = self.ok("order")
        self.assertNotIn("accept 1.1-1.3", out)
        self.assertIn("accept 1.1, 1.3", out)
        self.ok("todo", "accept", "1.1, 1.3", "--by", "owner", "fine")


class TheInspection(Base):
    def test_the_side_line_never_rebuilds_a_readme_el_cannot_vouch_for(self):
        os.environ["EL_TWO_HANDS"] = "1"
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        readme = self.case() / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(text.replace("## Context", "OWNER INSTRUCTION: do not ship\n\n## Context", 1), encoding="utf-8")
        before = readme.read_text(encoding="utf-8")
        self.ok("log", "DECISION", "a recorded decision")
        self.assertEqual(readme.read_text(encoding="utf-8"), before, "a hand edit waits for its own door")
        self.assertFalse((self.case() / "README.md.recover.md").exists())

    def test_the_printed_howto_runs_as_printed(self):
        os.environ["EL_TWO_HANDS"] = "1"
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")
        self.ok("phase", "agree", "1", "the owner agreed")
        self.ok("todo", "add", "1", "a step")
        self.ok("todo", "done", "1.1", "owner", "the step is done")
        self.ok("todo", "accept", "1.1", "--by", "owner", "fine")
        self.ok("phase", "close", "1", "done", "--reflect", "r", "--align", "a")
        self.ok("log", "--phase", "1", "PROBLEM", "a problem after the close")
        out, _ = self.ok("order")
        line = next(ln for ln in out.split("\n") if "every phase ended" in ln)
        self.assertNotIn("<", line)
        self.assertIn('el done "what came out" --howto "none: why"', line)
        self.ok("done", "what came out", "--howto", "none: nothing to reuse")

    def test_a_hand_read_from_the_old_file_becomes_this_sessions_own(self):
        self.ok("case", "new", "other", "--goal", "another work")
        os.environ["EL_SESSION"] = "shared01-A"
        root = store.find_root(self.case())
        old = store._hand_file(root, legacy=True)
        old.parent.mkdir(parents=True, exist_ok=True)
        base = Path(self.tmp.name, ".cases").resolve().parent
        old.write_text(os.path.relpath(self.case().resolve(), base), encoding="utf-8")
        self.assertIn(f"case in hand: {self.case().name}", self.ok("status")[0])
        old.write_text(os.path.relpath(self.case("other").resolve(), base), encoding="utf-8")  # an older el moved it
        self.assertIn(f"case in hand: {self.case().name}", self.ok("status")[0], "the hand stays where this session read it")

    def test_a_case_opened_and_a_child_spawned_are_this_sessions_writes(self):
        os.environ["EL_SESSION"] = "fresh0002"
        out, _ = self.ok()
        self.assertIn("session maker1029 wrote here at", out, "case new is a write")
        self.ok("phase", "open", "1", "Work", "--goal", "the work is done")  # a child is spawned inside a phase (P11)
        self.ok("spawn", "child", "--goal", "the child works")
        os.environ["EL_SESSION"] = "fresh0003"
        out, _ = self.ok()
        self.assertIn("child", out.split("\n")[0])
        self.assertIn("session fresh0002 wrote here at", out, "the child was written by the session that spawned it")


if __name__ == "__main__":
    unittest.main()
