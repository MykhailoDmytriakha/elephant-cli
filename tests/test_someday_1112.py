"""Ideas a case did not get to do not die with it (the owner's word, 2026-11-12: «not every Later line is done in the
case … when a case closes, they just go to the store of ideas»; «a sub-case closes — its Later lines go to the case
above; that one closes — they go up, to the level where .howto lies»; «one folder, a file per idea: why it came, its
context — you read the list of files and you see the ideas»; «on start it walks the old cases and gathers them»;
«.someday, beside .howto»).

The form of the loss, measured the same day on every case on disk: 93 closed cases, 15 of them still held open Later
lines — 8 different ideas once copies of one project in other worktrees are set aside; `el done` said «closed» and left
them `[ ]` inside a case nobody opens again. Each printed door is executed here as printed."""
import re
import shlex
import unittest
from pathlib import Path

from elephant import stamp
from tests.test_commands import run
from tests.test_long_case_1105 import Base


def door(text: str, verb: str) -> list:
    m = re.search(rf"el {verb}[^·()—\n]*?(?=\s+(?:·|\(|—|$)|\n|$)", text)
    assert m, f"no `el {verb}` in: {text}"
    return shlex.split(m.group(0))[1:]


class Store(Base):
    def someday(self) -> Path:
        return Path(self.tmp.name) / ".someday"

    def ideas(self) -> dict:
        d = self.someday()
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.md"))} if d.is_dir() else {}

    def work(self, case: str = None):
        pre = ("--case", case) if case else ()
        self.ok(*pre, "phase", "open", "1", "Work", "--goal", "work done [run: t → OK]")
        self.ok(*pre, "todo", "add", "1", "do it", "--expect", "[run: t → OK]")
        self.ok(*pre, "todo", "done", "1.1", "run:t → OK", "done")
        self.ok(*pre, "phase", "close", "1", "done", "--reflect", "the work was plain", "--align", "nothing changes")


class ATopCaseCloses(Store):
    def test_its_open_later_lines_become_files_beside_howto(self):
        self.ok("todo", "add", "later", "warm the cache on deploy", "--why", "the first request is slow",
                "--note", "the deploy script runs no warm-up")
        self.work()
        out, _ = self.ok("done", "the shop works")
        self.assertIn("carried 1 Later line(s) to .someday/", out)
        ideas = self.ideas()
        self.assertEqual(len(ideas), 1, ideas)
        name, text = next(iter(ideas.items()))
        self.assertTrue(name.startswith("warm-the-cache-on-deploy"), name)
        self.assertIn("warm the cache on deploy", text)
        self.assertIn("the first request is slow", text)
        self.assertIn("the deploy script runs no warm-up", text)
        self.assertRegex(text, r"from: \[[^\]]*shop\]\(\.\./\.cases/[^)]*shop/README\.md\) · L1")
        self.assertNotRegex(self.read("TODO.md"), r"- \[ \] L1 ")  # the line went: no `[ ]` left in a closed case
        self.assertIn(".someday/" + name, self.read("JOURNAL.md"))  # where it went, in the case's story

    def test_a_case_without_later_lines_says_nothing_of_it(self):
        self.work()
        out, _ = self.ok("done", "the shop works")
        self.assertNotIn("someday", out)
        self.assertFalse(self.someday().exists())

    def test_two_hands_carry_at_the_owner_word_not_at_ready(self):
        self.ok("readme", "add", "context", "rule: two hands — work is accepted by a second hand")
        self.ok("todo", "add", "later", "an idea for another day")
        self.ok("phase", "open", "1", "Work", "--goal", "work done [run: t → OK]")
        self.ok("todo", "add", "1", "do it", "--expect", "[run: t → OK]")
        self.ok("todo", "done", "1.1", "run:t → OK", "done")
        self.ok("todo", "accept", "1.1", "--by", "owner", "checked")
        self.ok("phase", "close", "1", "done", "--reflect", "the work was plain", "--align", "nothing changes")
        out, _ = self.ok("done", "the shop works")
        self.assertIn("ready:", out)
        self.assertEqual(self.ideas(), {})
        out, _ = self.ok("done", "--by", "owner", "yes, closed")
        self.assertIn("carried 1 Later line(s) to .someday/", out)
        self.assertEqual(len(self.ideas()), 1)

    def test_one_name_twice_gets_its_own_file(self):
        self.ok("todo", "add", "later", "same idea")
        self.work()
        self.ok("done", "the shop works")
        self.ok("case", "new", "other", "--goal", "another case")
        self.ok("--case", "other", "todo", "add", "later", "same idea")
        self.work("other")
        self.ok("--case", "other", "done", "the other works")
        self.assertEqual(len(self.ideas()), 2, self.ideas())


class AReopenedCaseAndAMany(Store):  # the second hand, 2026-11-12
    def test_a_reopened_case_never_gives_a_number_twice(self):
        self.ok("todo", "add", "later", "first idea")
        self.work()
        self.ok("done", "the shop works")
        c = ("--case", "shop")
        self.ok(*c, "case", "reopen", "one more round")
        out, _ = self.ok(*c, "todo", "add", "later", "second idea")
        self.assertIn("L2", out)
        self.ok(*c, "phase", "open", "2", "More", "--goal", "more done [run: t → OK]")
        self.ok(*c, "todo", "add", "2", "do more", "--expect", "[run: t → OK]")
        self.ok(*c, "todo", "done", "2.1", "run:t → OK", "done")
        self.ok(*c, "phase", "close", "2", "done", "--reflect", "plain", "--align", "nothing")
        self.ok(*c, "done", "the shop works again")
        titles = sorted(t.splitlines()[0] for t in self.ideas().values())
        self.assertEqual(titles, ["# first idea", "# second idea"])

    def test_fifteen_long_ideas_close_in_one_bounded_record(self):  # round 2: long titles spilled the headline
        for k in range(1, 16):
            self.ok("todo", "add", "later", f"idea number {k:02d} " + "with a long description of what it would take to do " * 1 + "x" * 30)
        self.work()
        self.ok("done", "the shop works")
        self.assertEqual(len(self.ideas()), 15)
        self.assertIn("L15 «idea number 15", self.read("JOURNAL.md"))
        self.assertTrue(all(len(t.splitlines()[0]) > 90 for t in self.ideas().values()))  # long titles, not short ones
        self.ok("--case", "shop", "case", "reopen", "one more round")
        out, _ = self.ok("--case", "shop", "todo", "add", "later", "after the close")  # a number for life, past a bounded record
        self.assertIn("L16", out)


class LinksFollowTheIdea(Store):
    def test_a_link_in_the_idea_is_re_based_into_someday(self):  # a live copy, 2026-11-12: `[concept](../../X.md)`
        Path(self.tmp.name, "CONCEPTS.md").write_text("# concepts\n", encoding="utf-8")
        self.ok("todo", "add", "later", "build the reject door — [concept](../../CONCEPTS.md)")
        self.work()
        self.ok("done", "the shop works")
        name, text = next(iter(self.ideas().items()))
        self.assertIn("[concept](../CONCEPTS.md)", text)
        self.assertTrue((self.someday() / "../CONCEPTS.md").resolve().is_file())


class ANestedCaseCloses(Store):
    def test_its_ideas_go_to_the_parent_later_list(self):
        self.ok("phase", "open", "1", "Work", "--goal", "work done [run: t → OK]")
        self.ok("spawn", "storage", "--goal", "storage works")
        self.ok("--case", "storage", "todo", "add", "later", "shard the store by year", "--why", "it grows")
        self.ok("--case", "storage", "phase", "open", "1", "Store", "--goal", "s [run: t → OK]")
        self.ok("--case", "storage", "todo", "add", "1", "store it", "--expect", "[run: t → OK]")
        self.ok("--case", "storage", "todo", "done", "1.1", "run:t → OK", "stored")
        self.ok("--case", "storage", "phase", "close", "1", "stored")
        out, _ = self.ok("--case", "storage", "done", "storage works")
        self.assertIn("carried 1 Later line(s) to", out)
        self.assertEqual(self.ideas(), {}, "a nested case gives its ideas to its parent, not to .someday/")
        todo = self.read("TODO.md")
        self.assertRegex(todo, r"- \[ \] L\d+ shard the store by year")
        self.assertIn("it grows", todo)
        self.assertIn("storage", todo.split("shard the store by year", 1)[1].split("\n- ", 1)[0])  # where it came from


class OldClosedCases(Store):
    def close_the_old_way(self):
        """A case el closed before it carried ideas: closed in README, the Later line still open in TODO."""
        self.ok("todo", "add", "later", "print the receipt in two languages")
        self.work()
        self.ok("done", "the shop works")
        body, _ = stamp.split(self.read("TODO.md"))  # put the line back as an older el left it
        body = body.rstrip("\n") + "\n\n## Later\n  - [ ] L1 print the receipt in two languages — since: 2026-10-01\n"
        body = re.sub(r"\n## Later\n(?=[\s\S]*\n## Later\n)", "\n", body)
        (self.case() / "TODO.md").write_text(stamp.apply(body), encoding="utf-8")
        for f in self.someday().glob("*.md"):
            f.unlink()

    def test_the_entry_names_them_and_the_printed_door_gathers_them_once(self):
        self.close_the_old_way()
        self.ok("case", "new", "next", "--goal", "the next work")
        out, _ = self.ok()
        line = next((ln for ln in out.splitlines() if "el someday gather" in ln), None)  # the Order line, its door whole
        self.assertIsNotNone(line, out)
        before = self.read("TODO.md")
        gathered, _ = self.ok(*door(line, "someday"))
        self.assertIn("gathered 1", gathered)
        self.assertEqual(len(self.ideas()), 1)
        self.assertEqual(self.read("TODO.md"), before, "a closed case is not written: the file keeps where it came from")
        again, _ = self.ok("someday", "gather")
        self.assertIn("nothing to gather", again)
        self.assertEqual(len(self.ideas()), 1)
        out, _ = self.ok()
        self.assertNotIn("el someday gather", out)


class TheList(Store):
    def test_el_someday_lists_the_ideas(self):
        self.ok("todo", "add", "later", "warm the cache on deploy")
        self.work()
        self.ok("done", "the shop works")
        out, _ = self.ok("someday")
        self.assertIn("warm-the-cache-on-deploy", out)
        self.assertIn("1 idea(s)", out)

    def test_an_empty_store_says_so(self):
        out, _ = self.ok("someday")
        self.assertIn("no ideas", out)

    def test_the_dose(self):
        out, _ = self.ok("help", "someday")
        self.assertIn(".someday/", out)
        out, _ = self.ok("help", "later")
        self.assertIn(".someday/", out)


if __name__ == "__main__":
    unittest.main()
