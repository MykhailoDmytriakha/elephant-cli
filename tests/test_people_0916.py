"""L10 — people cards (the owner's word, 2026-09-16): the people the cases deal with get one card each in
.cases/people/ — inside .cases/ because a card is personal data and hides with the cases. Not a case: never
scanned as one, never written by el. `summary:` as line 2 is the dose; a card without it is named once per
workspace; a case links to a card like to any file and the link is checked."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import knowledge
from tests.test_commands import run


class People(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        os.environ["EL_HINTS"] = "0"
        self.root = Path(self.tmp.name) / ".cases"
        run("case", "new", "court", "--goal", "g")
        run("phase", "open", "1", "Filing", "--goal", "f")
        self.case = next(p for p in self.root.iterdir() if p.is_dir())
        self.people = self.root / "people"
        self.people.mkdir()

    def tearDown(self):
        os.chdir(self.old)
        os.environ.pop("EL_HINTS", None)
        self.tmp.cleanup()

    def card(self, name: str, text: str) -> Path:
        p = self.people / name
        p.write_text(text, encoding="utf-8")
        return p

    def test_people_is_a_known_folder_not_a_rejected_case(self):
        self.card("court-secretary-3.md", "# Секретарь суда, участок 3\nsummary: назначает даты · по телефону не отвечает · приём лично по вторникам\n")
        code, out, err = run("case", "list")
        self.assertEqual(code, 0, err)
        self.assertNotIn("not a case", err + out)
        self.assertNotIn("people", out, "a card is not a case line")
        code, out, err = run("check", "--all")
        self.assertEqual(code, 0, err + out)
        self.assertNotIn("people", err, "a card with its summary is silent")

    def test_a_card_without_summary_is_named_once_and_a_case_links_to_a_card(self):
        self.card("menuka-perera.md", "# Менука Перера\n\nстейкхолдер\n")
        code, out, err = run("check", "--all")
        self.assertEqual(code, 0, "the lower layer is the agent's — shown, not a violation")
        self.assertEqual(err.count("people card people/menuka-perera.md has no `summary:` line"), 1)
        self.assertIn("add `summary: role · what they own · how to reach` as line 2 (F14, L10)", err)
        code, out, err = run()
        self.assertIn("people card people/menuka-perera.md has no `summary:` line", out.split("## Order")[1])
        self.card("menuka-perera.md", "# Менука Перера\nsummary: стейкхолдер · решает по бюджету · Teams до полудня\n")
        self.assertNotIn("people card", run()[1])
        run("todo", "add", "1", "согласовать дату", "--note", "перед звонком прочитать [Менуку](../people/menuka-perera.md)")
        code, out, err = run("check")
        self.assertEqual(code, 0, f"the link to the card resolves from the case: {err + out}")
        (self.people / "menuka-perera.md").unlink()
        code, out, err = run("check")
        self.assertEqual(code, 3, "a card that is gone is a dead link in TODO (F16)")
        self.assertIn("../people/menuka-perera.md", out + err)

    def test_the_same_links_line_in_two_cases_is_named_and_a_card_settles_it(self):
        line = "секретарь участка 3 — не отвечает по телефону, приём лично по вторникам с 10 до 13"
        run("readme", "add", "links", line)
        run("case", "new", "fine", "--goal", "g")
        run("readme", "add", "links", "секретарь участка 3 — не отвечает по телефону, приём лично по вторникам с 10 до 13, взять паспорт")
        code, out, err = run()
        order = out.split("## Order")[1]
        self.assertIn("Links line 1 «секретарь участка 3 — не отвечает по телефону, приём лично", order)
        self.assertIn("» is also in 2026-", order)
        self.assertIn("2026-", order)
        self.assertIn("a person → .cases/people/<name>.md with summary: (el help people)", order)
        self.card("court-secretary-3.md", "# Секретарь суда, участок 3\nsummary: назначает даты · по телефону не отвечает · приём лично по вторникам\n")
        run("readme", "edit", "links", "1", "[секретарь](../people/court-secretary-3.md) — даты заседаний")
        run("case", "use", "court")
        run("readme", "edit", "links", "1", "[секретарь](../people/court-secretary-3.md) — даты заседаний")
        self.assertNotIn("is also in", run()[1], "both cases link the card: the duplication is gone")
        self.assertEqual(run("check", "--all")[0], 0)

    def test_case_new_hints_the_cards_and_entry_names_a_line_repeating_a_card(self):
        os.environ.pop("EL_HINTS", None)
        code, out, _ = run("case", "new", "empty", "--goal", "g")
        self.assertIn("hint: phases you already see?", out, "no cards yet: the phases hint")
        self.assertIn("[Menuka](../people/menuka-perera.md)", out, "the exemplar shows where people live, before any card exists")
        self.card("court-secretary-3.md", "# Секретарь суда, участок 3\nsummary: назначает даты заседаний · по телефону не отвечает · приём лично по вторникам\n")
        code, out, _ = run("case", "new", "fine", "--goal", "g")
        self.assertIn("hint: 1 people card(s) in .cases/people/ — link the ones this case deals with", out)
        run("readme", "add", "links", "секретарь — назначает даты заседаний · по телефону не отвечает · приём лично по вторникам")
        hint = run()[1].rstrip().splitlines()[-1]
        self.assertIn("Links line 1 repeats people/court-secretary-3.md — link the card instead: el readme edit links 1", hint)
        code, out, _ = run("help", "practice")
        self.assertIn("PEOPLE", out)
        self.assertIn(".cases/people/court-secretary-3.md", out)

    def test_help_people_and_its_aliases(self):
        for word in ("people", "person", "who", "contacts"):
            code, out, _ = run("help", word)
            self.assertEqual(code, 0)
            self.assertIn(".cases/people/", out)
        self.assertIn(".cases/people/<name>.md", knowledge.TOPICS["where"])


if __name__ == "__main__":
    unittest.main()
