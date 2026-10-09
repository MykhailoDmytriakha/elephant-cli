"""A Codex peer review of batch 22 before commit (2026-10-08): six findings, each a form of failure kept here."""
import os
import tempfile
import unittest
from pathlib import Path

from elephant import grammar, stamp
from tests.test_commands import run


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ.pop("EL_CASE", None)
        self.saved = {k: os.environ.get(k) for k in ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS")}
        os.environ.update(EL_HINTS="0", EL_SESSION="codex22", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))
        os.environ.pop("EL_TWO_HANDS", None)
        run("case", "new", "probe", "--goal", "g")
        self.case = next(Path(self.tmp.name, ".cases").glob("*-probe"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def readme(self):
        return (self.case / "README.md").read_text(encoding="utf-8")

    def finish(self):
        run("phase", "open", "1", "Work", "--goal", "w")
        run("todo", "add", "1", "step")
        run("todo", "done", "1.1", "run:x → ok", "ok")
        run("todo", "accept", "1.1", "--by", "owner", "ok")
        run("phase", "close", "1", "closed", "--reflect", "r", "--align", "a")


class TheReadyTallyIsElsToo(Base):
    def test_a_readme_at_its_byte_limit_still_becomes_ready(self):
        """Codex: 12,209 counted bytes, and `el done` failed with exit 3 — the acceptance tail on `ready:` was counted."""
        self.finish()
        body, _ = stamp.split(self.readme())
        parsed = grammar.parse_readme(body)
        room = grammar.README_MAX_BYTES - 60 - (parsed.bytes - parsed.rendered_bytes)
        filler = "- 2026-10-08 · " + "x" * (room - len("- 2026-10-08 · ") - 1)
        src = Path(self.tmp.name) / "in.md"
        src.write_text(body.replace("## Decisions\n", "## Decisions\n" + filler + "\n", 1), encoding="utf-8")
        code, _, err = run("readme", "--file", str(src))
        self.assertEqual(code, 0, err)
        code, out, err = run("done", "outcome")
        self.assertEqual(code, 0, err)
        self.assertIn("- ready: ", self.readme())


class DecisionsAreTheAgents(Base):
    def test_a_shared_opening_is_not_the_same_choice(self):
        opening = "the storage of the case files in the shared folder, after the long talk with the team: "
        run("readme", "add", "decisions", "2026-10-08 · " + opening + "retain the existing schema")
        run("log", "DECISION", opening + "migrate to the new schema")
        run()
        self.assertIn("migrate to the new schema", self.readme())

    def test_an_agent_decision_that_starts_like_el_is_drawn(self):
        run("log", "DECISION", "фаза 2 использует PostgreSQL вместо SQLite из-за нескольких писателей")
        run("log", "DECISION", "todo хранится в SQLite вместо JSON, чтобы обновления были атомарны")
        run()
        text = self.readme()
        self.assertIn("фаза 2 использует PostgreSQL", text)
        self.assertIn("todo хранится в SQLite", text)


class ReadyEndsWhereItIsNoLongerTrue(Base):
    def test_dropping_the_rule_drops_ready(self):
        self.finish()
        run("done", "outcome")
        run("readme", "drop", "context", "1")
        self.assertNotIn("- ready: ", self.readme())

    def test_a_cancel_ends_the_wait(self):
        self.finish()
        run("done", "outcome")
        code, _, err = run("case", "cancel", "goal abandoned")
        self.assertEqual(code, 0, err)
        text = self.readme()
        self.assertIn("- closed: ", text)
        self.assertNotIn("- ready: ", text)

    def test_a_case_without_phases_shows_ready_not_open_a_phase(self):
        run("done", "outcome")
        code, out, _ = run()
        thread = next(ln for ln in out.split("\n") if ln.startswith("thread:"))
        self.assertIn("awaits the owner's word", thread)
        self.assertNotIn("no phase yet", thread)


class RelinkTakesTheOneTheLinkMeans(Base):
    """The second review of batch 22: the relink that reads a path from the case and from the project rewrote links to
    another file when both readings were dead and linked, an unrelated live reading blocked a dead link's repair, and a
    folder crashed it."""

    def setUp(self):
        super().setUp()
        (self.case / "docs").mkdir()
        (self.case / "docs" / "final.md").write_text("# final\nsummary: the final file\n", encoding="utf-8")

    def test_an_absolute_path_rewrites_only_its_own_links(self):
        run("log", "DECISION", "see [case copy](docs/gone.md) and [project copy](../../docs/gone.md)")
        code, out, err = run("relink", str(self.case / "docs" / "gone.md"), "docs/final.md")
        self.assertEqual(code, 0, err)
        journal = (self.case / "JOURNAL.md").read_text(encoding="utf-8")
        self.assertIn("[case copy](docs/final.md)", journal)
        self.assertIn("[project copy](../../docs/gone.md)", journal)

    def test_two_linked_readings_are_refused_not_both_rewritten(self):
        run("log", "DECISION", "see [case copy](docs/gone.md) and [project copy](../../docs/gone.md)")
        code, _, err = run("relink", "docs/gone.md", "docs/final.md")
        self.assertEqual(code, 2)
        self.assertIn("names 2 files the links of this case point at", err)

    def test_a_live_project_file_does_not_block_the_case_link(self):
        (Path(self.tmp.name) / "docs").mkdir()
        (Path(self.tmp.name) / "docs" / "gone.md").write_text("# a different file\n", encoding="utf-8")
        run("log", "DECISION", "see [case copy](docs/gone.md)")
        code, out, err = run("relink", "docs/gone.md", "docs/final.md")
        self.assertEqual(code, 0, err)
        self.assertIn("[case copy](docs/final.md)", (self.case / "JOURNAL.md").read_text(encoding="utf-8"))

    def test_a_folder_is_refused_without_a_crash(self):
        code, _, err = run("relink", "docs", "none")
        self.assertEqual(code, 2)
        self.assertIn("is a folder", err)


if __name__ == "__main__":
    unittest.main()
