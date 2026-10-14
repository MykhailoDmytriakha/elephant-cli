"""Two reports of 2026-10-13/14, one hole — a record with no honest door of its own.

1. A map was done with `file:artifacts/map.html` and accepted; the agent kept the version handed in as `map.v1.html` and
   went on with round five in `map.html`. Order named two doors — record round five as round one's proof, or reopen
   work that was done — both false; `done 1.1 file:map.v1.html` ADDED a second proof and Order kept the item. A file that
   holds the very version a proof was done against, while the proof's own file no longer holds it, now takes that
   proof's line: the bytes handed in are the same, only where they lie moved — the doer and the acceptance stay. Order,
   check, the close, the brief and the accept refusal name the copy when it lies beside the file.
2. `el readme edit context 6 x` said «Context has 0 line(s) of yours» over seven plain lines the agent had written. The
   refusal now counts what the section holds — bullets, which k addresses, and plain lines — and names the door to each:
   the goal by name, the rest by a whole rewrite, a line that changes on its own as a bullet."""
import os
import re
import shutil
import unittest

from elephant import grammar
from tests.test_commands import run
from tests.test_proof_version_1002 import Base, DOER, REVIEWER


class KeptVersionCopy(Base):
    def setUp(self):
        super().setUp()
        code, err = self.accept()
        self.assertEqual(code, 0, err)
        shutil.copy(self.case() / "docs/note.txt", self.case() / "docs/note.v1.txt")  # the version handed in, kept
        self.write("Version B: round five of the work.\n")

    def proofs(self):
        return grammar.parse_todo(self.todo()).phase(1).items[0].evidence

    def test_order_names_the_kept_copy_whole(self):
        _, out, _ = run("order")
        self.assertIn("the version done against is kept in docs/note.v1.txt: el todo done 1.1 file:docs/note.v1.txt", out)

    def test_the_reports_acceptance(self):  # after done on the copy, Order no longer names the item; only the copy proves it
        journal = (self.case() / "JOURNAL.md").read_text(encoding="utf-8")
        code, out, err = run("todo", "done", "1.1", "file:docs/note.v1.txt", "Note written")
        self.assertEqual(code, 0, err)
        self.assertIn("1.1: the proof moved to docs/note.v1.txt", out + err)
        self.assertEqual([pr for k, pr in self.proofs() if k == "file" and "note.txt" in pr], [], self.todo())
        self.assertEqual(len([1 for k, pr in self.proofs() if "note.v1.txt" in pr]), 1, self.todo())
        item = grammar.parse_todo(self.todo()).phase(1).items[0]
        self.assertTrue(item.accepted, "the bytes accepted are the bytes that prove it now")
        self.assertIn(DOER, item.done_by, "not a new claim — the doer stays")
        _, out, _ = run("order")
        self.assertNotIn("changed since done", out)
        self.assertEqual((self.case() / "JOURNAL.md").read_text(encoding="utf-8"), journal, "an edit of the record, not an event")

    def test_a_copy_added_before_the_change_is_cleaned_by_the_same_door(self):
        # the live workaround: the copy already stands beside the changed file — done on the copy drops the stale line
        self.write("Version A: approved content.\n")
        run("todo", "done", "1.1", "file:docs/note.v1.txt", "Note written")
        self.assertEqual(len([1 for k, _ in self.proofs() if k == "file"]), 2, "same bytes in both: nothing to move yet")
        self.write("Version B: round five of the work.\n")
        code, out, err = run("todo", "done", "1.1", "file:docs/note.v1.txt", "Note written")
        self.assertEqual(code, 0, err)
        self.assertEqual([pr for k, pr in self.proofs() if k == "file"], [pr for k, pr in self.proofs() if "note.v1.txt" in pr])
        self.assertNotIn("changed since done", run("order")[1])

    def test_a_file_gone_is_replaced_by_its_copy(self):
        (self.case() / "docs/note.txt").unlink()
        code, _, err = run("todo", "done", "1.1", "file:docs/note.v1.txt", "Note written")
        self.assertEqual(code, 0, err)
        self.assertNotIn("note.txt)", self.todo())
        self.assertTrue(grammar.parse_todo(self.todo()).phase(1).items[0].accepted)

    def test_a_copy_of_other_bytes_is_added_not_moved(self):
        self.write("Version C: something else.\n", "docs/note.v1.txt")
        code, _, err = run("todo", "done", "1.1", "file:docs/note.v1.txt", "Note written")
        self.assertEqual(code, 0, err)
        self.assertEqual(len([1 for k, _ in self.proofs() if k == "file"]), 2)
        self.assertIn("changed since done", run("order")[1], "el never launders a changed proof")

    def test_the_accept_refusal_and_the_brief_name_the_copy(self):
        os.environ["EL_SESSION"] = REVIEWER
        code, _, err = run("todo", "accept", "1.1", "--by", "subagent", "Read it")
        os.environ["EL_SESSION"] = DOER
        self.assertEqual(code, 4)
        self.assertIn("the version claimed is kept in docs/note.v1.txt", err)
        _, out, _ = run("todo", "brief", "1.1")
        self.assertIn("the version claimed is kept in docs/note.v1.txt — the doer moves the proof there: el todo done 1.1 "
                      "file:docs/note.v1.txt", out)

    def test_without_a_copy_every_door_names_it_in_words(self):  # Codex, 2026-10-14: brief and accept were silent
        (self.case() / "docs/note.v1.txt").unlink()
        os.environ["EL_SESSION"] = REVIEWER
        code, _, err = run("todo", "accept", "1.1", "--by", "subagent", "Read it")
        os.environ["EL_SESSION"] = DOER
        self.assertEqual(code, 4)
        self.assertIn("the doer kept a copy of the version claimed? el todo done 1.1 file:<the copy>", err)
        _, out, _ = run("todo", "brief", "1.1")
        self.assertIn("the doer kept a copy of the version claimed? el todo done 1.1 file:<the copy>", out)

    def test_a_copy_whose_name_has_a_space_is_printed_quoted_and_works(self):  # Codex, 2026-10-14: printed bare → exit 3
        (self.case() / "docs/note.v1.txt").rename(self.case() / "docs/note kept.txt")
        _, out, _ = run("order")
        self.assertIn("el todo done 1.1 'file:docs/note kept.txt' — the proof moves there", out)
        code, _, err = run("todo", "done", "1.1", "file:docs/note kept.txt", "Note written")
        self.assertEqual(code, 0, err)
        self.assertNotIn("changed since done", run("order")[1])

    def test_a_link_to_a_project_file_is_no_kept_copy(self):  # Codex, 2026-10-14: the printed door added an unversioned proof
        (self.case() / "docs/note.v1.txt").unlink()
        saved = self.case().parent.parent / "saved.txt"
        saved.write_text("Version A: approved content.\n", encoding="utf-8")
        (self.case() / "docs/kept.txt").symlink_to(saved)
        _, out, _ = run("order")
        self.assertNotIn("is kept in docs/kept.txt", out)
        self.assertIn("kept a copy of the version done against? el todo done 1.1 file:<the copy>", out)

    def test_ninth_round_edges(self):  # Codex, 2026-10-14: `file:` strips a leading space and expands `~` — at the case root
        self.write("Root A.\n", "rootnote.txt")
        run("todo", "done", "1.1", "file:rootnote.txt", "Note written")
        self.write("Root A.\n", "~rootkept.txt")
        self.write("Root A.\n", " rootkept.txt")
        self.write("Root B.\n", "rootnote.txt")
        _, out, _ = run("order")
        self.assertIn("1.1 rootnote.txt changed since done", out)
        self.assertNotIn("is kept in ~rootkept.txt", out)
        self.assertNotIn("is kept in  rootkept.txt", out)
        self.assertNotIn("rootkept.txt: el todo done", out, "neither copy reads back through `file:` as itself")
        (self.case() / "docs/note.v1.txt").unlink()
        self.write("Version A: approved content.\n", "docs/space kept.txt")  # a space inside a path is a path `file:` keeps
        self.assertIn("'file:docs/space kept.txt'", run("order")[1])

    def test_tenth_round_the_new_version_door_reads_back(self):  # Codex, 2026-10-14: `file:~note.txt` named the home folder
        for name in ("~note.txt", " note.txt"):
            with self.subTest(name=name):
                self.write("Root A.\n", name)
                code, _, err = run("todo", "done", "1.1", f"file:./{name}", "Note written")
                self.assertEqual(code, 0, err)
                self.write("Root B.\n", name)
                _, out, _ = run("order")
                line = next(ln for ln in out.split("\n") if f"1.1 {name} changed since done" in ln)
                door = re.search(r"this version is the proof: el todo done 1\.1 ('file:[^']*'|\S+) ", line)
                self.assertIsNotNone(door, out)
                token = door.group(1).strip("'")
                self.assertEqual(token, f"file:./{name}")
                code, _, err = run("todo", "done", "1.1", token, "round two")
                self.assertEqual(code, 0, err)
                self.assertNotIn(f"{name} changed since done", run("order")[1])

    def test_without_a_copy_beside_it_the_door_is_named_in_words(self):
        (self.case() / "docs/note.v1.txt").unlink()
        _, out, _ = run("order")
        self.assertIn("kept a copy of the version done against? el todo done 1.1 file:<the copy>", out)
        self.assertNotIn("is kept in", out)


class GoneProof(Base):
    """Codex, 2026-10-14: the version kept as docs/kept.txt and the original deleted — accept and close passed with exit 0
    over a proof that no longer exists (on HEAD too). A gone versioned proof holds both gates and names its doors."""
    def setUp(self):
        super().setUp()
        shutil.copy(self.case() / "docs/note.txt", self.case() / "docs/kept.txt")
        (self.case() / "docs/note.txt").unlink()

    def accept(self):
        os.environ["EL_SESSION"] = REVIEWER
        code, _, err = run("todo", "accept", "1.1", "--by", "subagent", "Read it")
        os.environ["EL_SESSION"] = DOER
        return code, err

    def test_accept_close_and_brief_say_it_is_gone(self):
        code, err = self.accept()
        self.assertEqual(code, 4)
        self.assertIn("1.1 proof docs/note.txt is gone", err)
        self.assertIn("the doer moves the proof there: el todo done 1.1 file:docs/kept.txt", err)
        code, _, err = run("phase", "close", "1", "x", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("1.1 proof docs/note.txt is gone", err)
        _, out, _ = run("todo", "brief", "1.1")
        self.assertIn("⚠ docs/note.txt is gone", out)

    def test_a_folder_in_its_place_is_still_gone(self):  # Codex, 2026-10-14: a folder at the path passed every gate
        (self.case() / "docs/note.txt").mkdir()
        self.assertEqual(self.accept()[0], 4)
        code, _, err = run("phase", "close", "1", "x", "--reflect", "r", "--align", "a")
        self.assertEqual(code, 4)
        self.assertIn("1.1 proof docs/note.txt is gone", err)
        _, out, _ = run("order")
        self.assertIn("1.1 proof docs/note.txt is not a file any more", out)
        code, out, err = run("check")
        self.assertIn("F20 · 1.1 proof docs/note.txt is not a file any more", out + err)
        self.assertNotIn("violations: 0", out + err)
        _, out, _ = run("todo", "brief", "1.1")
        self.assertIn("⚠ docs/note.txt is gone", out)
        self.assertNotIn("el relink", out + err, "relink refuses an old path that is a folder")  # Codex, 2026-10-14

    def test_a_printed_relink_works(self):
        code, err = self.accept()
        door = re.search(r"el relink (\S+) <where it is now>", err)
        self.assertIsNotNone(door, err)
        code, _, err = run("relink", door.group(1), "docs/kept.txt")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.accept()[0], 0)

    def test_a_gone_path_with_a_space_names_no_relink(self):  # Codex, 2026-10-14: relink cannot rewrite such a link
        (self.case() / "docs/kept.txt").rename(self.case() / "docs/note original.txt")
        run("todo", "done", "1.1", "file:docs/note original.txt", "Note written")  # the proof now names a path with a space
        shutil.copy(self.case() / "docs/note original.txt", self.case() / "docs/kept.txt")
        (self.case() / "docs/note original.txt").unlink()
        code, err = self.accept()
        self.assertEqual(code, 4)
        self.assertIn("is gone", err)
        self.assertNotIn("el relink", err)
        self.assertIn("el todo done 1.1 file:docs/kept.txt", err)

    def test_seventh_round_edges(self):  # Codex, 2026-10-14: `=` up front, a `)` in the copy, a gone path with a space in check
        self.assertEqual(__import__("elephant.commands", fromlist=["_word"])._word("=note.txt"), "'=note.txt'")
        shutil.copy(self.case() / "docs/kept.txt", self.case() / "docs/note(kept).txt")
        (self.case() / "docs/kept.txt").unlink()
        code, err = self.accept()
        self.assertNotIn("note(kept)", err, "a copy whose link el cannot read back is no door")
        (self.case() / "docs/note(kept).txt").rename(self.case() / "docs/note original.txt")
        run("todo", "done", "1.1", "file:docs/note original.txt", "Note written")
        shutil.copy(self.case() / "docs/note original.txt", self.case() / "docs/kept.txt")
        (self.case() / "docs/note original.txt").unlink()
        code, out, err = run("check")
        self.assertIn("F20 · 1.1 proof docs/note original.txt is gone", out + err)
        self.assertNotIn("violations: 0", out + err)
        _, out, _ = run("order")
        self.assertIn("1.1 proof docs/note original.txt is gone", out)

    def test_eighth_round_edges(self):  # Codex, 2026-10-14: `#`, a backtick, a scheme — paths the dead-link scan does not see
        for name in ("docs/note#old.txt", "docs/note`old`.txt", "http:note.txt"):  # the last at the case root: a scheme up front
            with self.subTest(name=name):
                src = self.case() / name
                shutil.copy(self.case() / "docs/kept.txt", src)
                if "#" in name:
                    (self.case() / "docs/note").write_text("x", encoding="utf-8")  # what the scan reads behind the `#`
                code, _, err = run("todo", "done", "1.1", f"file:{name}", "Note written")
                self.assertEqual(code, 0, err)
                src.unlink()
                _, out, _ = run("order")
                self.assertIn(f"1.1 proof {name} is gone", out)
                code, out, err = run("check")
                self.assertNotIn("violations: 0", out + err)
                self.assertEqual(self.accept()[0], 4)
                self.assertNotIn("el relink", self.accept()[1], "relink cannot mend a link the scan does not see")
                code, _, err = run("todo", "done", "1.1", "file:docs/kept.txt", "Note written")  # the copy door closes it
                self.assertEqual(code, 0, err)
                self.assertEqual(self.accept()[0], 0)
                os.environ["EL_SESSION"] = REVIEWER
                run("todo", "reopen", "1.1", "--by", "subagent", "next case")  # back to done-not-accepted for the next name
                os.environ["EL_SESSION"] = DOER
                run("todo", "done", "1.1", "file:docs/kept.txt", "Note written")

    def test_no_relink_where_relink_reads_another_path(self):  # Codex, 2026-10-14: relink expands a leading `~`
        self.write("Version A: approved content.\n", "~note.txt")
        code, _, err = run("todo", "done", "1.1", "file:./~note.txt", "Note written")
        self.assertEqual(code, 0, err)
        (self.case() / "~note.txt").unlink()
        code, err = self.accept()
        self.assertEqual(code, 4)
        self.assertNotIn("el relink", err)
        self.assertIn("the doer kept a copy of the version claimed? el todo done 1.1 file:<the copy>", err)

    def test_done_on_the_copy_opens_the_gate(self):
        code, _, err = run("todo", "done", "1.1", "file:docs/kept.txt", "Note written")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.accept()[0], 0)

    def test_relink_opens_the_gate(self):
        code, _, err = run("relink", "docs/note.txt", "docs/kept.txt")
        self.assertEqual(code, 0, err)
        self.assertIn("kept.txt", self.todo())
        self.assertEqual(self.accept()[0], 0)


class ContextPlainLines(Base):
    def setUp(self):
        super().setUp()
        readme = (self.case() / "README.md").read_text(encoding="utf-8")
        body = re.sub(r"(## Context\n)(.*?)(\n## State)", lambda m: m.group(1) + "Prepare a note\nThe note is short.\n"
                      "It goes to the board on Monday.\n- rule: two hands — the owner agrees each phase's scope, a fresh "
                      "session accepts each done item" + m.group(3), readme, flags=re.S)
        (self.case().parent.parent / "r.md").write_text(body, encoding="utf-8")
        code, _, err = run("readme", "--file", str(self.case().parent.parent / "r.md"))
        self.assertEqual(code, 0, err)

    def test_the_reports_acceptance(self):  # the refusal says what Context holds and the door to the line
        code, _, err = run("readme", "edit", "context", "3", "x")
        self.assertEqual(code, 4)
        self.assertNotIn("0 line(s) of yours", err)
        self.assertIn("its 3 plain line(s) are a paragraph, not a list", err)
        self.assertIn('the first is the case goal: el readme edit context goal "…"', err)
        self.assertIn("the other 2 only a whole rewrite reaches: el readme --file", err)
        self.assertIn('el readme add context "…" — then el readme edit context <k> reaches it', err)

    def test_drop_says_the_same(self):
        code, _, err = run("readme", "drop", "context", "3")
        self.assertEqual(code, 4)
        self.assertIn("plain line(s) are a paragraph", err)
        self.assertIn("then el readme drop context <k> reaches it", err)

    def test_a_section_of_bullets_only_keeps_its_count(self):
        code, _, err = run("readme", "edit", "problems", "2", "x")
        self.assertEqual(code, 4)
        self.assertIn("Problems has 0 line(s) of yours, nothing at position 2", err)


if __name__ == "__main__":
    unittest.main()
