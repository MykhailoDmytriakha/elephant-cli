"""An argument el takes is never lost (three Codex acceptors, 2026-10-11: `el todo reopen N.M --by codex --run "… → …"`
answered exit 0 and the re-run was gone — `accept` kept it, `reopen` dropped it); a verdict too long for one event is
refused with how much fits and the acceptor's own door, not «put the story into the phase file»; `--case` typed after the
command is the same option (a live report, 2026-10-11: `el log DECISION "…" --case <name>` → «unrecognized arguments»)."""
import os
import shlex
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run


class KeptArguments(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_CASE")}
        os.environ.pop("EL_CASE", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="doer1011", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        run("case", "new", "engine", "--goal", "x")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-engine"))
        run("phase", "open", "1", "Work", "--goal", "x [run: make test → OK]")
        run("todo", "add", "1", "parser")
        code, _, err = run("todo", "done", "1.1", "run:make test → 12 OK", "parser reads both forms")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def files(self):
        return {n: (self.case / n).read_text(encoding="utf-8") for n in ("TODO.md", "JOURNAL.md")}

    def as_acceptor(self, *args):
        os.environ["EL_SESSION"] = "check1011"
        try:
            return run(*args)
        finally:
            os.environ["EL_SESSION"] = "doer1011"

    def test_a_return_keeps_its_re_run(self):
        code, out, err = self.as_acceptor("todo", "reopen", "1.1", "--by", "codex", "--run", "make test → 3 fail",
                                          "the parser drops the second form")
        self.assertEqual(code, 0, err)
        journal = self.files()["JOURNAL.md"]
        self.assertIn("1.1 возвращён в работу — the parser drops the second form", journal)
        self.assertIn("re-run: make test → 3 fail", journal)
        self.assertIn("re-run: 1 kept", out)

    def test_a_return_re_run_without_an_outcome_is_refused_before_writing(self):
        before = self.files()
        code, _, err = self.as_acceptor("todo", "reopen", "1.1", "--by", "codex", "--run", "make test", "why")
        self.assertEqual(code, 2)
        self.assertIn("joined by → or ->", err)
        self.assertEqual(self.files(), before)

    def test_an_option_the_action_does_not_read_is_refused_not_dropped(self):
        before = self.files()
        for args, said in [(("todo", "done", "1.1", "--run", "make test → OK", "run:make test → OK", "again"),
                            "el todo done does not take --run"),
                           (("todo", "accept", "1.1", "--by", "codex", "--sample", "2", "--run", "make test → 12 OK", "ok"),
                            "el todo accept does not take --sample"),
                           (("phase", "plan", "2", "Next", "--goal", "y", "--reflect", "lesson"),
                            "el phase plan does not take --reflect")]:
            code, _, err = self.as_acceptor(*args)
            self.assertEqual(code, 2, args)
            self.assertIn(said, err)
            self.assertIn("nothing was written", err)
        self.assertEqual(self.files(), before)

    def test_a_note_edit_still_reaches_note(self):
        run("todo", "note", "1.1", "first note")
        code, _, err = run("todo", "note", "1.1", "--edit", "1", "the note, rewritten")
        self.assertEqual(code, 0, err)

    def test_a_verdict_too_long_names_what_fits_and_the_acceptors_door(self):
        before = self.files()
        code, _, err = self.as_acceptor("todo", "accept", "1.1", "--by", "codex", "--run", "make test → 12 OK",
                                        " ".join(["compared"] * 140))
        self.assertEqual(code, 3)
        self.assertIn("the verdict does not fit one journal event (F7)", err)
        self.assertRegex(err, r"1259 chars of words, \d+ fit beside 1 re-run\(s\) on 1 body line")
        self.assertIn("its own --run", err)
        self.assertIn("a file of the case", err)
        self.assertNotIn("phase file", err)
        self.assertEqual(self.files(), before)

    def test_a_long_event_names_its_size(self):
        code, _, err = run("log", "DECISION", " ".join(["word"] * 300))
        self.assertEqual(code, 3)
        self.assertIn("1499 chars, about", err)

    def test_the_brief_offers_the_re_run_to_a_return_too(self):
        _, out, _ = run("todo", "brief", "1.1")
        self.assertIn('todo reopen 1.1 --by <you> --run "make test → <what came out now>"', out)

    def test_case_after_the_command_is_the_same_option(self):
        for args in (("log", "DECISION", "chose the second form", "--case", self.case.name),
                     ("log", "DECISION", "chose the third form", f"--case={self.case.name}")):
            code, _, err = run(*args)
            self.assertEqual(code, 0, err)
        journal = self.files()["JOURNAL.md"]
        self.assertIn("chose the second form", journal)
        self.assertIn("chose the third form", journal)

    def test_case_named_twice_with_two_names_is_refused(self):
        code, _, err = run("--case", self.case.name, "log", "DECISION", "x", "--case", "other")
        self.assertEqual(code, 2)
        self.assertIn("one call acts on one case", err)

    def test_case_after_a_double_dash_is_text(self):
        code, _, err = run("todo", "add", "1", "--", "--case", "x")
        self.assertNotIn("one call acts on one case", err)

    # the Codex review of this batch, 2026-10-11 — six defects of the first version

    def test_every_re_run_is_kept_not_counted(self):
        runs = [a for k in "abcde" for a in ("--run", f"{k} → fail")]
        code, out, err = self.as_acceptor("todo", "reopen", "1.1", "--by", "codex", *runs, "why")
        self.assertEqual(code, 0, err)
        journal = self.files()["JOURNAL.md"]
        self.assertIn("e → fail", journal)
        self.assertNotIn("more", journal)

    def test_a_case_flag_without_a_value_is_refused_not_dropped(self):
        before = self.files()
        code, _, err = run("log", "DECISION", "marker", "--case", self.case.name, "--case")
        self.assertEqual(code, 2)
        self.assertEqual(self.files(), before)

    def test_a_headline_at_the_limit_with_a_body_is_split_not_refused_after_the_write(self):
        code, _, err = self.as_acceptor("todo", "reopen", "1.1", "--by", "codex", "--run", "make test → FAIL", "x" * 164)
        self.assertEqual(code, 0, err)

    def test_a_long_verdict_gets_its_budget_not_a_half_ready_command(self):
        code, _, err = self.as_acceptor("todo", "reopen", "1.1", " ".join(["compared"] * 140))
        self.assertEqual(code, 3)
        self.assertIn("The same call with the words shortened", err)
        self.assertNotIn("<you>", err)
        self.assertNotIn("todo reopen 1.1", err)

    def test_a_case_name_with_a_dash_moves_as_one_word(self):
        code, _, err = run("todo", "show", "1.1", f"--case={self.case.name}")
        self.assertEqual(code, 0, err)

    def test_a_proof_with_quotes_is_briefed_in_quotes_that_work(self):
        run("todo", "add", "1", "printer")
        run("todo", "done", "1.2", 'run:python3 -c "print(1)" → 1', "prints")
        _, out, _ = run("todo", "brief", "1.2")
        self.assertIn("""--run 'python3 -c "print(1)" → <what came out now>'""", out)

    # the second round of the same review — the edges of the first fixes

    def test_a_malformed_call_stays_refused_when_case_comes_after(self):
        before = self.files()
        code, _, err = run("log", "DECISION", "marker", "--phase", "--case", self.case.name, "p1")
        self.assertEqual(code, 2)
        self.assertEqual(self.files(), before)

    def test_two_names_before_the_command_are_refused_too(self):
        code, _, err = run("--case", self.case.name, "--case", "other", "log", "DECISION", "marker")
        self.assertEqual(code, 2)
        self.assertIn("one call acts on one case", err)

    def test_re_runs_that_alone_overflow_the_event_get_no_printed_command(self):
        runs = [a for k in range(6) for a in ("--run", f"cmd{k} → " + "x" * 140)]
        before = self.files()
        code, _, err = self.as_acceptor("todo", "accept", "1.1", "--by", "codex", *runs, "checked")
        self.assertEqual(code, 3)
        self.assertRegex(err, r"its 6 re-run\(s\) take \d+ body lines of 5")
        self.assertNotIn("todo accept 1.1 --by", err)
        self.assertEqual(self.files(), before)

    def test_the_arrow_refusal_prints_quoting_that_works(self):
        code, _, err = self.as_acceptor("todo", "reopen", "1.1", "--by", "codex", "--run", 'python3 -c "print(1)"', "why")
        self.assertEqual(code, 2)
        self.assertIn("""--run 'python3 -c "print(1)" → <outcome now>'""", err)

    # the third round — the ready command works as printed

    def test_a_hard_quoted_proof_is_briefed_in_a_word_the_shell_gives_back(self):
        run("todo", "add", "1", "quoted")
        run("todo", "done", "1.2", """run:python3 -c "print('x')" → x""", "prints")
        _, out, _ = run("todo", "brief", "1.2")
        line = next(ln for ln in out.split("\n") if "todo accept 1.2" in ln)
        argv = shlex.split(line.replace("<you: codex|claude|gemini|subagent>", "codex"))
        self.assertEqual(argv[argv.index("--run") + 1], """python3 -c "print('x')" → <what came out now>""")
        self.assertEqual(argv[:3], ["el", "--case", self.case.name])

    def test_the_brief_says_how_big_a_verdict_can_be(self):
        _, out, _ = run("todo", "brief", "1.1")
        self.assertIn("one verdict is one journal event", out)

    def test_a_headline_that_already_ends_with_an_ellipsis_keeps_its_five_body_lines(self):
        why = "checked " * 19 + "all tests: …"
        runs = [a for k in range(5) for a in ("--run", f"cmd{k} → " + "x" * 80)]
        code, _, err = self.as_acceptor("todo", "reopen", "1.1", *runs, why)  # no --by: the headline ends with « …»
        self.assertEqual(code, 0, err)

    def test_a_nested_case_sharing_a_name_is_named_by_its_path(self):
        code, _, err = run("spawn", "store", "--goal", "y")
        self.assertEqual(code, 0, err)
        nested = next(self.case.glob("*-store"))
        run("case", "new", "store", "--goal", "z")  # a top case of the same name
        from elephant import commands
        self.assertEqual(commands._case_opt(nested), f"--case {self.case.name}/{nested.name}")
        top = next(p for p in Path(self.tmp.name, ".cases").glob("*-store"))
        self.assertEqual(commands._case_opt(top), f"--case .cases/{top.name}")

    def test_text_split_by_an_option_is_refused_with_how_to_quote(self):
        code, _, err = run("todo", "add", "1", "alpha", "--case", self.case.name, "beta")
        self.assertEqual(code, 2)
        self.assertIn("put the text in one pair of quotes", err)

    # the batch's own acceptance (Codex, 2026-10-11) — the class is wider than todo and phase, and --case is one call

    def test_case_and_readme_refuse_an_option_their_action_does_not_read(self):
        before = self.files()
        for args, said in [(("case", "cancel", "--goal", "x"), "el case cancel does not take --goal"),
                           (("readme", "set", "next", "y", "--file", "z.md"), "el readme set does not take --file")]:
            code, _, err = run(*args)
            self.assertEqual(code, 2, args)
            self.assertIn(said, err)
        self.assertEqual(self.files(), before)
        self.assertNotIn("cancelled", (self.case / "README.md").read_text(encoding="utf-8").lower().split("## state")[1][:200])

    def test_a_refusal_under_case_prints_its_door_with_the_same_case(self):
        run("case", "new", "other", "--goal", "z")  # the session's hand is now on another case
        code, _, err = self.as_acceptor("--case", self.case.name, "todo", "accept", "1.1", "--by", "codex", "checked")
        self.assertEqual(code, 2)
        line = next(ln for ln in err.split("\n") if "todo accept 1.1" in ln)
        door = line[line.index("el --case"):line.index('"what you checked"') + len('"what you checked"')]
        argv = shlex.split(door.replace("<what came out now>", "12 OK"))
        self.assertEqual(argv[1:3], ["--case", self.case.name])
        code, _, err = self.as_acceptor(*argv[1:])
        self.assertEqual(code, 0, err)
        self.assertIn("принято 1.1", self.files()["JOURNAL.md"])

    def test_a_bare_todo_refuses_an_option_it_would_drop(self):
        code, _, err = run("todo", "--run", "make test → FAIL")
        self.assertEqual(code, 2)
        self.assertIn("bare el todo shows the plan and takes no --run", err)


if __name__ == "__main__":
    unittest.main()
