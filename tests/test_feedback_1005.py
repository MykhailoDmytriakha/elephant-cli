"""Feedback of 2026-10-05 — the length refusal spoke with two voices, and State's `last:` read the wrong end of an entry.

1. An item with an opaque id and an endpoint path was refused at 108 of 100, a note «when linking a doc» at 158 of 150;
   the agent asked el to stop counting opaque ids and link targets. Link targets never counted (2026-09-01) and the
   limit stays (the owner's word, 2026-09-15: rephrased, not counted differently) — but the pocket refusal had not
   said what counts, and it still printed a cut as `suggestion:` that dropped the link itself or ended a fact mid-claim:
   the 2026-10-02 fix reached the item door only. Every door with a length limit speaks one voice now — what counts
   (link names, with their share), what a cut would lose, how to rephrase — and offers no cut that loses meaning.
2. `el todo fact N.M` on a done item turned a clean `check` into «State is behind»; the agent asked el to keep the
   anchor. Not taken: a fact is a RESULT (the owner's word, 2026-09-17), knowledge the next step stands on, so State is
   read again — and el says so at the moment of writing, not only on the next entry.
3. Found on the way: `last:` took the FIRST RESULT of the newest entry, while events inside an entry are appended —
   two RESULTs in one minute showed the older one as the last."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

PROOF = "[run: make test → OK]"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        os.environ["EL_SESSION"] = "doer1005"
        run("case", "new", "login trace", "--goal", "g")
        run("phase", "open", "1", "Trace", "--goal", f"the login path is traced {PROOF}")
        run("todo", "add", "1", "trace the login call", "--expect", PROOF)

    def tearDown(self):
        os.chdir(self.old)
        for k in ("EL_HINTS", "EL_SESSION"):
            os.environ.pop(k, None)
        os.environ["EL_TWO_HANDS"] = "0"
        self.tmp.cleanup()

    def case(self) -> Path:
        return next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())

    def todo(self) -> str:
        return (self.case() / "TODO.md").read_text()


class APocketRefusalSpeaksTheItemVoice(Base):
    # invented words of the live shape: a note that ends in the link it exists for, 169 visible chars
    NOTE = ("the trace for SERVICE_METHOD-1234567890ABCDEF1234567890ABCDEF through the gateway and the identity provider "
            "is saved here: [service-method trace of the signin post](docs/trace/sm-1234567890abcdef.json)")

    def test_a_long_note_names_what_counts_and_what_a_cut_would_lose(self):
        before = self.todo()
        code, _, err = run("todo", "note", "1.1", self.NOTE)
        self.assertEqual(code, 3)
        self.assertEqual(self.todo(), before, "nothing was written")
        self.assertIn("markdown links count as their name", err, "the agent believed the link target counted")
        self.assertIn("of them are link names: a short name keeps the link", err)
        self.assertNotIn('suggestion: "', err, "the cut dropped the link the note exists for")
        self.assertIn("a cut at 150 would lose", err)
        self.assertIn("(with its link)", err)
        self.assertIn("rephrase, do not truncate", err)
        self.assertIn("an opaque id (a hash, a generated entity id) is a trace, not words", err)

    def test_a_fact_is_not_cut_mid_claim(self):
        fact = ("in 3 traces of the identity provider through the gateway the signin post answered 302 and "
                "SERVICE_METHOD-1234567890ABCDEF1234567890ABCDEF was the method")
        for pocket in ("fact", "why", "expect"):
            code, _, err = run("todo", pocket, "1.1", fact)
            self.assertEqual(code, 3, pocket)
            self.assertNotIn('suggestion: "', err, pocket)
            self.assertIn("would lose «", err, pocket)

    def test_a_phase_note_speaks_the_same_voice(self):
        code, _, err = run("phase", "note", "1", self.NOTE)
        self.assertEqual(code, 3)
        self.assertNotIn('suggestion: "', err)
        self.assertIn("markdown links count as their name", err)

    def test_a_link_target_still_does_not_count(self):
        target = "docs/trace/" + "x" * 140 + ".json"
        code, _, err = run("todo", "note", "1.1", f"the saved trace: [trace]({target})")
        self.assertEqual(code, 0, err)


class TheIntentOfAPlanSpeaksTheSameVoice(Base):
    def test_no_boundary_names_the_loss(self):
        code, _, err = run("phase", "plan", "2", "Rollout", "--goal", "слово " * 30)
        self.assertEqual(code, 3)
        self.assertNotIn('suggestion: "', err)
        self.assertIn("a cut at 100 would lose «", err)

    def test_a_boundary_keeps_the_rest_as_a_phase_note(self):
        goal = ("the login path runs through the gateway in every region — the region list and the owners of each "
                "gateway are in the docs")
        code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
        self.assertEqual(code, 3)
        self.assertIn("suggestion — the item, the rest as its note: el phase plan 2 'Rollout' --goal '", err)
        self.assertIn("&& el phase note 2 '", err)


class TheLimitStays(Base):
    def test_an_opaque_id_and_a_path_still_count(self):
        # the acceptance the feedback asked for — a 32-char id and a 30-char path in a 110-char item accepted — is not
        # taken: the owner's word 2026-09-15, and the quoted-token exemption was rolled back as a door for filler
        text = "Verify SERVICE_METHOD-1234567890ABCDEF1234567890AB for /api/v1/auth/idp-initiated-post/x in the flow"
        text = text + "!" * (110 - len(text))
        code, _, err = run("todo", "add", "1", text)
        self.assertEqual(code, 3)
        self.assertIn("110 visible chars, limit 100 (F13)", err)
        self.assertIn("the id goes to a note", err)


class TheLastLineIsTheNewestResult(Base):
    def test_two_results_in_one_entry_show_the_second(self):
        run("todo", "add", "1", "read the gateway log", "--expect", PROOF)
        run("todo", "done", "1.1", "run:make test → OK", "the call is traced")
        run("todo", "done", "1.2", "run:make test → OK", "the gateway log is read")
        state = (self.case() / "README.md").read_text()
        last = next(ln for ln in state.split("\n") if ln.startswith("- last: "))
        self.assertIn("1.2", last, "the newest RESULT is the one written last inside the entry")


class AFactOnADoneItemAsksStateToBeReadAgain(Base):
    def test_the_rule_stays_and_is_said_at_the_moment(self):
        run("todo", "done", "1.1", "run:make test → OK", "traced")
        run("readme", "touch")
        code, out, err = run("check")
        self.assertIn("warnings: 0", out + err)
        code, out, err = run("todo", "fact", "1.1", "the login call goes through the gateway in 3 of 3 traces")
        self.assertEqual(code, 0, err)
        self.assertIn("a fact is knowledge the next step stands on — read State again", out)
        self.assertIn("el readme touch", out)
        code, out, err = run("check")
        self.assertIn("State is behind", out + err, "the fact is a RESULT (the owner's word, 2026-09-17)")
        run("readme", "touch")
        code, out, err = run("check")
        self.assertIn("warnings: 0", out + err, "one touch is the honest repair")
        last = next(ln for ln in (self.case() / "README.md").read_text().split("\n") if ln.startswith("- last: "))
        self.assertIn("fact", last, "the newest RESULT is the fact")


class TheCodexBreaksHeld(Base):
    """Codex peer review of this batch, 2026-10-05 (gpt-6.1-sol, high): eight P2 — each pinned here."""

    def test_a_boundary_inside_a_link_is_not_a_boundary(self):
        goal = "Read the saved production evidence file [the trace, " + "important " * 8 + "](docs/trace.json)"
        code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
        self.assertEqual(code, 3)
        self.assertNotIn("suggestion —", err, "the split broke the link into a goal and a note")
        self.assertIn("would lose «", err)

    def test_a_quote_in_the_words_is_kept_as_typed(self):
        import re
        import subprocess
        goal = "Confirm config['prod'] is correct in every region — " + "background " * 7
        code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
        self.assertEqual(code, 3)
        quoted = re.search(r"--goal ('(?:[^']|'\\'')*')", err).group(1)
        shell = subprocess.run(["sh", "-c", "printf %s " + quoted], capture_output=True, text=True).stdout
        self.assertEqual(shell, "Confirm config['prod'] is correct in every region", "not ’ — the agent's own text")

    def test_a_split_that_starts_with_a_dash_is_not_offered(self):
        goal = "Confirm the login succeeds in production — --" + "x" * 75
        code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
        self.assertEqual(code, 3)
        self.assertNotIn("suggestion —", err, "argparse takes '--x…' for an option: the printed command would not run")
        self.assertIn("the split would start with `-`", err)

    def test_a_rest_too_long_for_a_note_offers_no_head(self):
        goal = "The login succeeds in the production environment — " + "required limitation " * 10
        code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
        self.assertEqual(code, 3)
        self.assertNotIn('suggestion: "', err, "the head alone hides the limitation")
        self.assertIn("too long for a note: a cut there would lose «required limitation", err)

    def test_a_text_that_ends_in_an_ellipsis_is_not_taken_for_a_cut(self):
        code, _, err = run("todo", "note", "1.1", "x" * 151 + "…")
        self.assertEqual(code, 3)
        self.assertIn("one token longer than the limit", err)

    def test_a_link_name_with_brackets_counts_as_its_name(self):
        code, _, err = run("todo", "note", "1.1", "a " * 70 + "[trace [prod]](docs/" + "x" * 200 + ".md)")
        self.assertEqual(code, 3)
        self.assertIn("note: is 152 visible chars", err, "the target does not count, nested brackets or not")
        self.assertIn("12 of them are link names", err)

    def test_add_later_and_edit_speak_the_same_head(self):
        text = "a " * 55 + "[one](docs/x) [two](docs/y)"
        for argv in (("todo", "add", "1", text), ("todo", "add", "later", text), ("todo", "edit", "1.1", text)):
            code, _, err = run(*argv)
            self.assertEqual(code, 3, argv)
            self.assertIn("117 visible chars, limit 100 (F13); markdown links count as their name — 6 of them are link names",
                          err, argv)

    def test_a_link_with_parentheses_or_a_title_is_not_split(self):
        for link in ('[Trace](docs/(prod).md "source, details")', "[Trace](docs/(prod, eu).md)"):
            goal = "Read the saved production evidence file " + link + " " + "important " * 6
            code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
            self.assertEqual(code, 3, link)
            self.assertNotIn("suggestion —", err, link)
        target = "docs/(prod)" + "x" * 151 + ".md"
        self.assertEqual(run("todo", "note", "1.1", f"the trace: [Trace]({target})")[0], 0, "the target does not count")

    def test_a_double_backtick_code_span_is_not_split(self):
        goal = "Run the production check in every region of the cluster ``grep -c, x ` y`` " + "important " * 4
        code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
        self.assertEqual(code, 3)
        self.assertNotIn("suggestion —", err)

    def test_a_free_result_does_not_hide_the_doer(self):
        os.environ["EL_SESSION"] = "doer1005"
        run("todo", "done", "1.1", "run:make test → OK", "traced")
        run("log", "RESULT", "1.1: extra verification completed")
        code, out, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test → OK", "re-ran")
        self.assertIn("same session as the doer", out + err, "the done is the doer, not a RESULT typed after it")

    def test_a_split_that_may_cut_markup_is_not_printed(self):
        for goal in ('Read the saved production evidence file [Trace](docs/(prod).md "source), details") ' + "important " * 6,
                     "Run the production check in every region ``of the cluster `alpha, beta` " + "important " * 5,
                     'Read the saved production evidence file [Trace](docs/(prod).md "source), details (") ' + "important " * 5,
                     r"Run the production check in every region \`of the cluster `alpha, beta` " + "important " * 5,
                     "Read the saved production evidence page <https://example.org/a, b> in every region " + "important " * 3,
                     "Verify _the gateway handles every region — the deployment evidence remains complete across all regions_",
                     "Verify the gateway handles every region &nbsp; " + "evidence " * 12):
            code, _, err = run("phase", "plan", "2", "Rollout", "--goal", goal)
            self.assertEqual(code, 3, goal)
            self.assertNotIn("suggestion —", err, goal)
            self.assertIn("would lose «", err, goal)

    def test_a_typed_result_with_a_kind_word_is_not_a_done(self):
        run("todo", "done", "1.1", "run:make test → OK", "traced")
        run("log", "RESULT", "1.1: run passed on the spare host")
        code, out, err = run("todo", "accept", "1.1", "--by", "codex", "--run", "make test → OK", "re-ran")
        self.assertIn("same session as the doer", out + err)

    def test_a_wrapped_range_done_is_still_the_doer(self):
        for k in range(2, 33):
            run("todo", "add", "1", f"trace the call number {k}", "--expect", "[owner]")
        code, _, err = run("todo", "done", "1.1-1.32", "owner", "the owner confirmed every trace of the login call " * 3)
        self.assertEqual(code, 0, err)
        code, out, err = run("todo", "accept", "1.3", "--by", "codex", "checked the owner's word in the chat")
        self.assertIn("same session as the doer", out + err, "the RESULT wrapped `: owner` into its body")


if __name__ == "__main__":
    unittest.main()
