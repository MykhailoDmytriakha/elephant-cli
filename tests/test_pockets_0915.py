"""F22 — the item's pockets, the owner's word of 2026-09-15 in sync mode:
«результат в одну строку неудобно» → the tick, the words and the proofs are lines under the item;
«зачем эта задача» → `why:`; «ограничения, кого позвать, что взять, ссылка» → `note:` (several);
«закинуть наперёд, но не декомпозировать» → a planned phase with notes and parked journal events that
surface when it opens; «по ссылке — выжимка» → `## Digest` rendered at close; «костыль на два-три
месяца» → a Problems line with `until:` counted on entry. Everything el renders is not counted in F4."""
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, store
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.root = Path(self.tmp.name) / ".cases"
        run("case", "new", "house", "--goal", "дом построен")
        run("phase", "open", "1", "Court", "--goal", "ходатайство подано")
        self.case = next(p for p in self.root.iterdir() if p.is_dir())
        (self.case / "evidence").mkdir()
        (self.case / "evidence" / "receipt.pdf").write_bytes(b"%PDF")
        (self.case / "docs").mkdir()
        (self.case / "docs" / "permit.pdf").write_bytes(b"%PDF")

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()

    def read(self, name: str) -> str:
        return (self.case / name).read_text(encoding="utf-8")


class WhyAndNotes(Base):
    def test_add_with_pockets_renders_in_one_order(self):
        code, out, err = run("todo", "add", "1", "спросить секретаря о дате", "--why", "без даты не подать до 20.09",
                             "--note", "по телефону не отвечают, только лично", "--note", "взять [разрешение](docs/permit.pdf)")
        self.assertEqual(code, 0, err)
        self.assertIn("· why · 2 note(s) → TODO.md", out)
        self.assertIn("  - [ ] 1.1 спросить секретаря о дате\n"
                      "    - why: без даты не подать до 20.09\n"
                      "    - note: по телефону не отвечают, только лично\n"
                      "    - note: взять [разрешение](docs/permit.pdf)\n", self.read("TODO.md"))
        self.assertEqual(run("check")[0], 0, "the link in the note resolves; the pockets are valid grammar")

    def test_why_is_set_replaced_and_cleared_through_the_door(self):
        run("todo", "add", "1", "оплатить пошлину")
        code, out, err = run("todo", "why", "1.1", "без оплаты не примут")
        self.assertEqual(code, 0, err)
        self.assertIn("    - why: без оплаты не примут\n", self.read("TODO.md"))
        code, out, _ = run("todo", "why", "1.1", "иначе вернут без рассмотрения")
        self.assertIn("(was: «без оплаты не примут»)", out)
        self.assertEqual(self.read("TODO.md").count("- why:"), 1, "one why per item")
        code, out, _ = run("todo", "why", "1.1", "")
        self.assertEqual(code, 0)
        self.assertIn("why 1.1 removed", out)
        self.assertNotIn("- why:", self.read("TODO.md"))

    def test_notes_add_edit_drop_and_a_list_of_items(self):
        run("todo", "add", "1", "шаг в SIT")
        run("todo", "add", "1", "шаг в UAT")
        run("todo", "add", "1", "шаг в PROD")
        code, out, err = run("todo", "note", "1.2,", "1.3", "в SIT падал, пока не сняли старый PVC")  # typed with a space
        self.assertEqual(code, 0, err)
        self.assertIn("note added under 1.2, 1.3", out)
        t = self.read("TODO.md")
        self.assertEqual(t.count("    - note: в SIT падал, пока не сняли старый PVC"), 2)
        self.assertNotIn("1.1\n    - note", t)
        run("todo", "note", "1.2", "звать платформу, не ждать таймаута")
        code, out, _ = run("todo", "note", "1.2", "--edit", "2", "звать #platform")
        self.assertEqual(code, 0)
        self.assertIn("note 2 of 1.2: «звать #platform» (was: «звать платформу, не ждать таймаута»)", out)
        code, out, _ = run("todo", "note", "1.2", "--drop", "1")
        self.assertEqual(code, 0)
        self.assertIn("note 1 dropped from 1.2", out)
        self.assertIn("  - [ ] 1.2 шаг в UAT\n    - note: звать #platform\n  - [ ] 1.3", self.read("TODO.md"))
        code, _, err = run("todo", "note", "1.2", "--drop", "5")
        self.assertEqual(code, 4)
        self.assertIn("k is 1..1", err)

    def test_pocket_limits_and_grammar_refusals(self):
        run("todo", "add", "1", "пункт")
        code, _, err = run("todo", "note", "1.1", "н" * 151)
        self.assertEqual(code, 3)
        self.assertIn("151 visible chars, limit 150 (F22)", err)
        self.assertIn("suggestion:", err)
        self.assertEqual(run("todo", "why", "1.1", "з" * 150)[0], 0, "150 fits")
        # hand-written forms the parser refuses: a pocket under no item, two whys, result under an open item
        r = grammar.parse_todo("# T\n\n- [ ] 1 Court\n    - why: lost\n")
        self.assertTrue(any(f.rule == "F22" and "under no item" in f.message for f in r.errors))
        r = grammar.parse_todo("# T\n\n- [ ] 1 Court\n  - [ ] 1.1 a\n    - why: x\n    - why: y\n")
        self.assertTrue(any("two `why:` lines" in f.message for f in r.errors))
        r = grammar.parse_todo("# T\n\n- [ ] 1 Court\n  - [ ] 1.1 a\n    - result: done\n")
        self.assertTrue(any(f.rule == "F20" and "is open and carries `result:`" in f.message for f in r.errors))
        r = grammar.parse_todo("# T\n\n- [ ] 1 Court\n  - [ ] 1.1 a\n    - owner\n")
        self.assertTrue(any(f.rule == "F20" and "carries evidence `owner`" in f.message for f in r.errors))
        r = grammar.parse_todo("# T\n\n- [ ] 1 Court\n  - [x] 1.1 a\n    - result: ok\n      - file\n")
        self.assertTrue(any("`file:` needs its proof" in f.message for f in r.errors))

    def test_result_lines_are_not_counted_in_the_two_hundred(self):
        head = "# T\n\n- [ ] 1 Court\n"
        items = "".join(f"  - [x] 1.{m} item {m}\n    - result: ok\n      - owner\n" for m in range(1, 66))  # 65 items = 195 lines
        r = grammar.parse_todo(head + items)
        self.assertTrue(r.ok, [str(f) for f in r.errors])  # 3 + 65 own lines, 130 rendered
        many = "".join(f"  - [ ] 1.{m} item {m}\n    - why: w\n    - note: n\n" for m in range(1, 70))  # 3 + 207 own lines
        r = grammar.parse_todo(head + many)
        self.assertTrue(any(f.rule == "F4" and "of your text" in f.message for f in r.errors), "why/note are the agent's lines and count")


class SeveralProofs(Base):
    def setUp(self):
        super().setUp()
        run("todo", "add", "1", "оплатить пошлину", "--why", "без оплаты вернут")

    def test_done_with_two_kinds_then_a_third(self):
        code, out, err = run("todo", "done", "1.1", "file:evidence/receipt.pdf", "ref:4471-09", "оплачено, чек в папке")
        self.assertEqual(code, 0, err)
        self.assertIn("(result + 2 proof line(s))", out)
        self.assertIn("  - [x] 1.1 оплатить пошлину\n    - why: без оплаты вернут\n    - result: оплачено, чек в папке\n"
                      "      - file: [receipt.pdf](evidence/receipt.pdf)\n      - ref: 4471-09\n", self.read("TODO.md"))
        self.assertIn("RESULT · 1.1: file [receipt.pdf](evidence/receipt.pdf) · ref 4471-09 — оплачено, чек в папке", self.read("JOURNAL.md"))
        code, out, err = run("todo", "done", "1.1", "owner", "подтверждено владельцем")
        self.assertEqual(code, 0, err)
        self.assertIn("evidence now: file [receipt.pdf](evidence/receipt.pdf) · ref 4471-09 · owner", out)
        self.assertIn("result renewed (was: «оплачено, чек в папке»)", out)
        self.assertIn("      - owner\n", self.read("TODO.md"))
        self.assertIn("evidence: 1 done · file 1 · ref 1 · owner 1", run()[1])
        self.assertEqual(run("check")[0], 0)

    def test_outcome_is_one_line_and_reopen_keeps_the_pockets(self):
        # 1.12.0 (feedback 2026-09-16): the `result:` line is el's — shortened like `closed:`, never refused; the journal keeps the words
        code, out, err = run("todo", "done", "1.1", "owner", "о" * 151)
        self.assertEqual(code, 0, err)
        self.assertIn("result: line shortened to 150 chars in TODO", out)
        self.assertIn("    - result: " + "о" * 149 + "…\n", self.read("TODO.md"))
        run("todo", "reopen", "1.1", "again")
        run("todo", "note", "1.1", "чек в синей папке")
        run("todo", "done", "1.1", "owner", "оплачено")
        code, out, err = run("todo", "reopen", "1.1", "платёж вернулся")
        self.assertEqual(code, 0, err)
        self.assertIn("  - [ ] 1.1 оплатить пошлину\n    - why: без оплаты вернут\n    - note: чек в синей папке\n", self.read("TODO.md"))
        self.assertNotIn("- result:", self.read("TODO.md"))
        self.assertNotIn("- owner", self.read("TODO.md"))

    def test_move_to_another_phase_carries_the_pockets(self):
        run("phase", "plan", "2", "Hearing", "--goal", "заседание")
        run("todo", "note", "1.1", "взять паспорт")
        code, out, err = run("todo", "move", "1.1", "2")
        self.assertEqual(code, 0, err)
        self.assertIn("- [ ] 2 Hearing — заседание\n  - [ ] 2.1 оплатить пошлину\n    - why: без оплаты вернут\n    - note: взять паспорт\n", self.read("TODO.md"))

    def test_a_text_ending_in_a_kind_word_is_not_mistaken_for_evidence(self):
        # found in the tool's own case (2026-09-15): item 4.14 read «…; ребёнок — file» and carried a run tail;
        # once the proof moved to its own line, the next parse took «— file» for evidence without a proof
        run("todo", "edit", "1.1", "child at the parent — file")
        run("todo", "done", "1.1", "run:make → OK", "ok")
        self.assertIn("  - [x] 1.1 child at the parent — file\n    - why: без оплаты вернут\n    - result: ok\n      - run: make → OK\n", self.read("TODO.md"))
        code, out, err = run("todo", "add", "1", "next")  # any write re-parses the rendered form
        self.assertEqual(code, 0, err)
        r = grammar.parse_todo(self.read("TODO.md").split("\nstamp:")[0])
        it = r.phases[0].items[0]
        self.assertEqual((it.text, it.evidence), ("child at the parent — file", [("run", "make → OK")]))

    def test_an_old_tail_is_read_and_rerendered_as_lines(self):
        body = self.read("TODO.md")
        body = body[: body.rindex("\nstamp: ")] + "\n"
        body = body.replace("  - [ ] 1.1 оплатить пошлину\n", "  - [x] 1.1 оплатить пошлину — owner\n")
        store.write(self.case, "TODO.md", body)
        self.assertIn("evidence: 1 done · owner 1", run()[1], "the 1.5.0–1.9.0 tail still reads")
        run("todo", "add", "1", "ещё пункт")  # any write re-renders
        self.assertIn("  - [x] 1.1 оплатить пошлину\n    - why: без оплаты вернут\n    - owner\n", self.read("TODO.md"))
        self.assertEqual(run("check")[0], 0)


class ParkedForAPlannedPhase(Base):
    def setUp(self):
        super().setUp()
        run("todo", "add", "1", "первый шаг")
        run("phase", "plan", "5", "Roof", "--goal", "крыша закрыта")

    def test_phase_notes_items_and_journal_events_wait_and_are_counted(self):
        code, out, err = run("phase", "note", "5", "разрешение действует до марта")
        self.assertEqual(code, 0, err)
        self.assertIn("(planned)", out)
        self.assertIn("moves into the phase file at close", out)
        run("phase", "note", "5", "лампочки под свесом")
        run("phase", "note", "5", "--edit", "2", "лампочки под свесом, тёплый свет")
        run("todo", "add", "5", "повесить лампочки")
        run("log", "--phase", "5", "DECISION", "лампочки — идея 15.09")
        self.assertIn("- [ ] 5 Roof — крыша закрыта\n  - note: разрешение действует до марта\n  - note: лампочки под свесом, тёплый свет\n"
                      "  - [ ] 5.1 повесить лампочки\n", self.read("TODO.md"))
        out = run()[1]
        self.assertIn("parked: phase 5 Roof — 1 item(s) · 2 note(s) · 1 journal event(s) (surfaces when the phase opens)", out)
        self.assertNotIn("phase 1 Court —", out.split("parked:")[1].split("\n")[0], "the open phase is not parked")
        code, _, err = run("phase", "note", "5", "--drop", "1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read("TODO.md").count("  - note:"), 1)
        self.assertEqual(run("check")[0], 0)

    def test_open_surfaces_the_parked_events_and_keeps_the_notes_in_todo(self):
        run("phase", "note", "5", "разрешение до марта")
        run("log", "--phase", "5", "DECISION", "лампочки — идея 15.09, см. [эскиз](docs/permit.pdf)")
        run("log", "--phase", "5", "PROBLEM", "бетон вставал сутки — заложить в срок стяжки")
        # close phase 1 so phase 5 may open (2–4 are not planned: the pipeline walks to the next planned one)
        run("todo", "done", "1.1", "owner", "ok")
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: r")
        run("log", "DECISION", "align: a")
        run("phase", "close", "1", "закрыта")
        code, out, err = run("phase", "open", "5")
        self.assertEqual(code, 0, err)
        self.assertIn("2 journal event(s) parked here before opening are in it", out)
        self.assertIn("carries 1 note(s) in TODO", out)
        pf = self.read("phases/5-roof.md")
        self.assertIn("## Before opening\n- DECISION · лампочки — идея 15.09, см. [эскиз](../docs/permit.pdf)\n"
                      "- PROBLEM · бетон вставал сутки — заложить в срок стяжки\n", pf)
        self.assertIn("\n## Notes\n", pf)
        self.assertIn("  - note: разрешение до марта\n", self.read("TODO.md"), "a note stays in the now-view while the phase runs")
        self.assertNotIn("parked:", run()[1])
        self.assertEqual(run("check")[0], 0)

    def test_cancel_and_replan_bring_the_pockets_and_notes_back(self):
        run("phase", "note", "5", "разрешение до марта")
        run("todo", "add", "5", "повесить лампочки", "--why", "красиво", "--note", "тёплый свет")
        run("phase", "cancel", "5", "крыши не будет в этом году")
        pf = self.read("phases/5-roof.md")
        self.assertIn("## Notes at cancel\n- note: разрешение до марта\n", pf)
        self.assertIn("## Items at cancel\n- 5.1 ✗ повесить лампочки\n  - why: красиво\n  - note: тёплый свет\n", pf)
        code, out, err = run("phase", "plan", "5", "Roof")
        self.assertEqual(code, 0, err)
        self.assertIn("- [ ] 5 Roof — крыша закрыта\n  - note: разрешение до марта\n  - [ ] 5.1 повесить лампочки\n"
                      "    - why: красиво\n    - note: тёплый свет\n", self.read("TODO.md"))


class DigestAtClose(Base):
    def test_the_phase_file_opens_with_a_rendered_digest(self):
        run("phase", "note", "1", "секретарь принимает по вторникам")
        run("todo", "add", "1", "оплатить пошлину", "--why", "без оплаты вернут")
        run("todo", "add", "1", "согласовать дату — [адвокат](docs/permit.pdf)")
        run("todo", "done", "1.1", "file:evidence/receipt.pdf", "оплачено")
        run("todo", "done", "1.2", "owner", "24 сентября")
        run("log", "PROBLEM", "секретарь не отвечает по телефону → ходить лично")
        run("log", "DECISION", "ходатайство подаём до заседания, не после")
        run("log", "RESULT", "ходатайство подано 18.09")
        run("log", "DECISION", "reflect: спрашивать «зачем» до похода")
        run("log", "DECISION", "align: к заседанию подготовить копии")
        code, out, err = run("phase", "close", "1", "подано, заседание 24.09", "--howto", "none: секретарь один, рецепт не нужен")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-court.md")
        self.assertIn("result: подано, заседание 24.09\n\n## Digest\n- items: 2 done\n- notes (1):\n  - секретарь принимает по вторникам\n"
                      "- results (1):\n  - ходатайство подано 18.09\n", pf)
        self.assertNotIn("  - 1.1: file", pf, "item results live under their items, not twice (the owner's eye, 2026-09-16)")
        self.assertNotIn("proofs:", pf, "two items, two distinct proofs — nothing to count")
        self.assertIn("- problems (1):\n  - секретарь не отвечает по телефону → ходить лично\n", pf)
        self.assertIn("- decisions (1):\n  - ходатайство подаём до заседания, не после\n", pf)
        self.assertIn("- reflect: спрашивать «зачем» до похода\n- align: к заседанию подготовить копии\n"
                      "- howto: none: секретарь один, рецепт не нужен\n", pf)
        self.assertIn("\n## Notes\n", pf)
        self.assertIn("## Items at close\n- 1.1 ✓ оплатить пошлину\n  - why: без оплаты вернут\n  - result: оплачено\n"
                      "    - file: [receipt.pdf](../evidence/receipt.pdf)\n- 1.2 ✓ согласовать дату — [адвокат](../docs/permit.pdf)\n"
                      "  - result: 24 сентября\n    - owner\n", pf)
        self.assertNotIn("- note:", self.read("TODO.md"), "the phase notes travelled into the file")
        code, out, err = run("check")
        self.assertEqual(code, 0, out + err)


class HollowProofs(Base):
    """The owner's eye over a closed phase of a live case (2026-09-16): four items, eight links to one
    markdown the agent had written itself — the link resolved, the proof was hollow. Shown, never refused."""

    def setUp(self):
        super().setUp()
        (self.case / "testing").mkdir()
        (self.case / "testing" / "evidence.md").write_text("# E\nsummary: what I did\n", encoding="utf-8")
        for t in ("analyze the query", "find the live pair", "run the live calls", "validate the response"):
            run("todo", "add", "1", t)

    def test_a_case_markdown_as_proof_gets_a_warning_not_a_refusal(self):
        code, out, err = run("todo", "done", "1.1", "file:testing/evidence.md", "analyzed")
        self.assertEqual(code, 0, err)
        self.assertIn("is a markdown inside the case — your own text", err)
        self.assertIn('run:"<command → outcome>"', err)
        self.assertIn("      - file: [evidence.md](testing/evidence.md)", self.read("TODO.md"), "written all the same")
        code, out, err = run("todo", "done", "1.2", "file:evidence/receipt.pdf", "paid")
        self.assertEqual(code, 0, err)
        self.assertNotIn("your own text", err, "a pdf is a thing")
        (Path(self.tmp.name) / "src").mkdir()
        (Path(self.tmp.name) / "src" / "query.sql").write_text("select 1\n", encoding="utf-8")
        code, out, err = run("todo", "done", "1.3", "file:src/query.sql", "the query")
        self.assertEqual(code, 0, err)
        self.assertNotIn("your own text", err, "a source file in the project is a thing")

    def test_one_file_for_several_items_is_named_at_done_and_counted_in_the_digest(self):
        run("todo", "done", "1.1", "file:testing/evidence.md", "analyzed")
        code, out, err = run("todo", "done", "1.2", "file:testing/evidence.md", "found")
        self.assertEqual(code, 0, err)
        self.assertIn("file:testing/evidence.md already proves 1.1 — one file for 2 items", err)
        run("todo", "done", "1.3", "file:testing/evidence.md", "called")
        code, out, err = run("todo", "done", "1.4", "file:testing/evidence.md", "validated")
        self.assertIn("already proves 1.1, 1.2, 1.3 — one file for 4 items", err)
        run("log", "RESULT", "r")
        run("log", "DECISION", "reflect: r")
        run("log", "DECISION", "align: a")
        code, out, err = run("phase", "close", "1", "done")
        self.assertEqual(code, 0, err)
        pf = self.read("phases/1-court.md")
        self.assertIn("- items: 4 done · proofs: 1 distinct for 4 items ([evidence.md](../testing/evidence.md) ×4)\n", pf)
        self.assertEqual(pf.count("- results"), 1)
        self.assertIn("- results (1):\n  - r\n", pf, "the phase-level RESULT stays, the four item results are under the items")

    def test_a_note_that_only_points_at_the_proof_is_named(self):
        run("todo", "note", "1.1", "Documented in [evidence.md](testing/evidence.md)")
        code, out, err = run("todo", "done", "1.1", "file:testing/evidence.md", "analyzed")
        self.assertEqual(code, 0, err)
        self.assertIn("1.1 note 1 only points at the proof file", err)
        self.assertIn("el todo note 1.1 --drop 1", err)
        code, out, err = run("todo", "note", "1.1", "see [evidence.md](testing/evidence.md)")
        self.assertIn("this note only points at the item's proof file", err)
        self.assertIn("--drop 2", err)
        code, out, err = run("todo", "note", "1.1", "the query lives in [evidence.md](testing/evidence.md), section 3, run it before 9:00")
        self.assertEqual(err, "", "a note with content of its own is a note")


class WorkaroundUntil(Base):
    def test_until_is_counted_on_entry_and_a_passed_one_is_an_order_line(self):
        soon = (dt.date.today() + dt.timedelta(days=77)).isoformat()
        run("readme", "add", "problems", f"open · Redis падает после деплоя · workaround: рестарт руками · until: {soon} (chart 2.3)")
        run("readme", "add", "problems", "open · старый костыль · until: 2026-01-01")
        code, out, err = run()
        self.assertEqual(code, 0, err)
        self.assertIn(f"problem 1 «open · Redis падает после деплоя ·…» until {soon} in 77 days", out)
        self.assertIn("problem 2 «open · старый костыль · until: 2026-01-01» passed its until date 2026-01-01", out)
        self.assertIn("→ fixed: el readme drop problems 2 · still needed: el readme edit problems 2", out)
        run("readme", "drop", "problems", "2")
        self.assertNotIn("passed its until date", run()[1])


if __name__ == "__main__":
    unittest.main()
