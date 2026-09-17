"""The owner's word of 2026-09-14 (a court case, TODO.md on screen): a tick is not a proof. Prove2Me
(Anthropic, Fermat 2026-09-04) holds a proof behind every closed statement and the parent resolves from
its children; here `done` carried a free sentence in the journal and the TODO line only `[x]` — on the
live case 11 done items, none pointing at a file though the files lay in evidence/. F20 now: the kind of
evidence comes first (file · ref · run · owner, a closed list), the tail is written on the item, the
count is shown on entry; old ticks are read, never nagged — the rule lives at the write door."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import store
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        run("case", "new", "demo case", "--goal", "g")
        run("phase", "open", "1", "Work", "--goal", "g")
        self.case = next(p for p in (Path(self.tmp.name) / ".cases").iterdir() if p.is_dir())
        (self.case / "evidence").mkdir()
        (self.case / "evidence" / "receipt.pdf").write_bytes(b"%PDF")
        run("todo", "add", "1", "pay the fee")
        run("todo", "add", "1", "file the request")
        run("todo", "add", "1", "run the tests")

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class KindFirst(Base):
    def test_done_without_a_kind_is_refused_with_the_four_kinds(self):
        before = self.read("TODO.md")
        code, out, err = run("todo", "done", "1.1", "paid")
        self.assertEqual(code, 2)
        for kind in ("file:", "ref:", "run:", "owner"):
            self.assertIn(kind, err)
        self.assertIn("el feedback", err, "a kind that is missing arrives through feedback")
        self.assertEqual(self.read("TODO.md"), before)
        self.assertNotIn("RESULT", self.read("JOURNAL.md"))

    def test_a_fifth_spelling_is_refused_the_list_is_closed(self):
        code, out, err = run("todo", "done", "1.1", "photo:evidence/receipt.pdf", "paid")
        self.assertEqual(code, 2)
        self.assertIn("not a kind of evidence", err)
        self.assertIn("closed on purpose", err)

    def test_a_kind_without_an_outcome_is_not_done(self):
        code, out, err = run("todo", "done", "1.1", "owner")
        self.assertEqual(code, 2)
        self.assertIn("what came out", err)
        self.assertIn("el todo cancel 1.1", err)


class TheFourKinds(Base):
    def test_file_must_exist_in_the_case_and_becomes_a_link(self):
        code, out, err = run("todo", "done", "1.1", "file:evidence/nope.pdf", "paid")
        self.assertEqual(code, 3)
        self.assertIn("no such file in the case", err)
        self.assertNotIn("[x]", self.read("TODO.md"))
        code, out, err = run("todo", "done", "1.1", "file:evidence/receipt.pdf", "fee paid")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [x] 1.1 pay the fee\n    - result: fee paid\n      - file: [receipt.pdf](evidence/receipt.pdf)\n", self.read("TODO.md"))
        self.assertIn("RESULT · 1.1: file [receipt.pdf](evidence/receipt.pdf) — fee paid", self.read("JOURNAL.md"))
        self.assertIn("evidence: file [receipt.pdf](evidence/receipt.pdf)", out)

    def test_a_link_pasted_whole_and_a_path_outside_the_case(self):
        code, out, err = run("todo", "done", "1.1", "file:[receipt.pdf](evidence/receipt.pdf)", "paid")
        self.assertEqual(code, 0, err)
        self.assertIn("      - file: [receipt.pdf](evidence/receipt.pdf)", self.read("TODO.md"))
        self.assertEqual(run("todo", "done", "1.2", "file:../outside.pdf", "x")[0], 2)
        self.assertEqual(run("todo", "done", "1.2", "file:/etc/hosts", "x")[0], 2)

    def test_ref_run_and_owner(self):
        code, out, err = run("todo", "done", "1.2", "ref:D005532-091426", "request filed via the portal")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [x] 1.2 file the request\n    - result: request filed via the portal\n      - ref: D005532-091426\n", self.read("TODO.md"))
        code, out, err = run("todo", "done", "1.3", "run:make test", "x")
        self.assertEqual(code, 2, "run needs the arrow")
        self.assertIn("→", err)
        code, out, err = run("todo", "done", "1.3", "run:python3 -m unittest -> 12 OK", "tests pass")
        self.assertEqual(code, 0, err)
        self.assertIn("      - run: python3 -m unittest → 12 OK\n", self.read("TODO.md"), "-> is normalised to →")
        self.assertEqual(run("todo", "done", "1.1", "owner:me", "x")[0], 2, "owner takes no value")
        code, out, err = run("todo", "done", "1.1", "owner", "the clerk agreed: hand it in on Monday")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [x] 1.1 pay the fee\n    - result: the clerk agreed: hand it in on Monday\n      - owner\n", self.read("TODO.md"))
        self.assertIn("RESULT · 1.1: owner — the clerk agreed", self.read("JOURNAL.md"))

    def test_the_tail_is_outside_the_hundred_char_limit(self):
        run("todo", "add", "1", "x" * 100)
        code, out, err = run("todo", "done", "1.4", "file:evidence/receipt.pdf", "long text, long tail")
        self.assertEqual(code, 0, err)
        code, out, err = run("check")
        self.assertEqual(code, 0, out + err)
        self.assertIn("violations: 0", out)


class ShownNeverNagged(Base):
    def test_entry_counts_the_kinds_and_an_old_tick_is_untyped(self):
        run("todo", "done", "1.1", "file:evidence/receipt.pdf", "paid")
        run("todo", "done", "1.2", "owner", "agreed")
        # an item ticked before 1.5.0: the line carries no tail — written through the stamp door, as the old el did
        body = self.read("TODO.md").replace("  - [ ] 1.3 run the tests", "  - [x] 1.3 run the tests")
        body = body[: body.rindex("\nstamp: ")] + "\n"
        store.write(self.case, "TODO.md", body)
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn("evidence: 3 done · file 1 · owner 1 · untyped 1", out)
        # 1.19.0 (the owner's word 2026-09-17): history is never nagged, but the RUNNING phase is the write door —
        # a tick without a kind there is named in Order and is an F20 violation until a kind is attached
        self.assertIn("1 tick(s) without a kind of evidence in the running phase — 1.3", out.split("## Order")[1])
        code, out, err = run("check")
        self.assertEqual(code, 3)
        self.assertIn("F20 · 1.3 is done without a kind of evidence in the running phase", err + out)
        run("todo", "done", "1.3", "owner", "attached later")
        self.assertIn("violations: 0", run("check")[1])

    def test_no_done_items_no_line(self):
        self.assertNotIn("evidence:", run()[1])


class SameDoor(Base):
    def test_a_second_done_adds_evidence_to_a_done_item(self):
        # 1.10.0 (the owner's word 2026-09-15): several proofs per item — a second done ADDS, the words are renewed
        run("todo", "done", "1.1", "owner", "paid, the owner says")
        code, out, err = run("todo", "done", "1.1", "file:evidence/receipt.pdf", "receipt saved")
        self.assertEqual(code, 0, err)
        self.assertIn("1.1 was already done — evidence now: owner · file [receipt.pdf](evidence/receipt.pdf) (was: owner) · "
                      "result renewed (was: «paid, the owner says»)", out)
        self.assertIn("    - result: receipt saved\n      - owner\n      - file: [receipt.pdf](evidence/receipt.pdf)\n", self.read("TODO.md"))
        j = self.read("JOURNAL.md")
        self.assertIn("RESULT · 1.1: owner — paid", j, "history stays")
        self.assertIn("RESULT · 1.1: file [receipt.pdf](evidence/receipt.pdf) — receipt saved", j)

    def test_reopen_clears_the_tail_the_result_stays(self):
        run("todo", "done", "1.1", "file:evidence/receipt.pdf", "paid")
        code, out, err = run("todo", "reopen", "1.1", "the payment bounced")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [ ] 1.1 pay the fee\n", self.read("TODO.md"))
        self.assertIn("RESULT · 1.1: file [receipt.pdf](evidence/receipt.pdf) — paid", self.read("JOURNAL.md"))

    def test_a_range_gives_every_item_the_tail_with_one_result(self):
        code, out, err = run("todo", "done", "1.1-1.3", "run:make check → OK", "pre-flight verified")
        self.assertEqual(code, 0, err)
        todo = self.read("TODO.md")
        for m in (1, 2, 3):
            self.assertRegex(todo, rf"  - \[x\] 1\.{m} [^\n]*\n    - result: pre-flight verified\n      - run: make check → OK\n")
        self.assertEqual(self.read("JOURNAL.md").count("RESULT · 1.1, 1.2, 1.3: run make check → OK — pre-flight verified"), 1)


class TheTailTravels(Base):
    def test_phase_close_carries_the_tail_into_the_phase_file_links_rebased(self):
        run("todo", "done", "1.1", "file:evidence/receipt.pdf", "paid")
        run("todo", "done", "1.2", "ref:D005532", "filed")
        run("todo", "done", "1.3", "owner", "ok")
        run("log", "RESULT", "phase done")
        run("log", "DECISION", "reflect: x")
        run("log", "DECISION", "align: y")
        code, out, err = run("phase", "close", "1", "all three ended")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-work.md")
        self.assertIn("- 1.1 ✓ pay the fee\n  - result: paid\n    - file: [receipt.pdf](../evidence/receipt.pdf)\n", pf)
        self.assertIn("- 1.2 ✓ file the request\n  - result: filed\n    - ref: D005532\n", pf)
        self.assertIn("- 1.3 ✓ run the tests\n  - result: ok\n    - owner\n", pf)
        self.assertIn("violations: 0", run("check")[1])

    def test_a_deleted_evidence_file_is_a_dead_link_with_a_fix(self):
        run("todo", "done", "1.1", "file:evidence/receipt.pdf", "paid")
        (self.case / "evidence" / "receipt.pdf").unlink()
        code, out, err = run("check")
        self.assertEqual(code, 3, out + err)
        self.assertIn("evidence/receipt.pdf", out + err)
        self.assertIn("el relink", out + err)


if __name__ == "__main__":
    unittest.main()
