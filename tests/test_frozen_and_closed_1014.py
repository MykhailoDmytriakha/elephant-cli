"""Two reports of 2026-10-14 (both the maintainer's own, from the polygon), and the owner's word the same day.

1. Order asked 14 files to rephrase their `summary:` — accepted reports whose version holds an acceptance, and
   pre-registered protocols whose «written before the data» rests on an unchanged file. No honest fix. The owner: «and the
   limit by the measure, and the freeze» — 533 live summaries: over 120 — 14 %, over 150 — 9 %, p90 140. The limit is 150;
   a case file that is a versioned proof of a done item is frozen — no Order line asks to edit it; `done` says it while the
   edit is still cheap.
2. A case closed on the 8th took phase 3 on the 14th; then `case use` and `done` said «closed». The owner: a new phase in a
   closed case is refused with the door to open the case; once open, the phase is added — `el case reopen "why"`."""
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_commands import run

LONG = ("what the two regions do differently: manifests, replicas, CPU, memory, routes and the database each one talks to, "
        "with the timing of every smoke call and the numbers")  # 170 chars
MID = "what the two regions do differently: manifests, replicas, CPU, memory, routes and the database each one talks to, timed"


class Base(unittest.TestCase):
    KEYS = ("EL_HINTS", "EL_SESSION", "EL_HANDS_DIR", "EL_TWO_HANDS", "EL_CASE")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        os.environ.pop("EL_CASE", None)
        os.environ.pop("EL_TWO_HANDS", None)
        os.environ.update(EL_HINTS="0", EL_SESSION="doer1014", EL_HANDS_DIR=str(Path(self.tmp.name) / "hands"))

    def tearDown(self):
        os.chdir(self.old)
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def case(self, name: str) -> Path:
        return next(Path(self.tmp.name, ".cases").glob(f"*-{name}"))

    def ok(self, *argv):
        code, out, err = run(*argv)
        self.assertEqual(code, 0, f"{argv}: {err}")
        return out, err


class FrozenSummary(Base):
    def setUp(self):
        super().setUp()
        self.ok("case", "new", "regions", "--goal", "compare the regions")
        self.ok("phase", "open", "1", "Compare", "--goal", "compare [file]")
        self.ok("todo", "add", "1", "write the comparison", "--expect", "[file: docs/r.md]")
        docs = self.case("regions") / "docs"
        docs.mkdir()
        (docs / "r.md").write_text(f"# Regions\nsummary: {LONG}\n\nbody\n", encoding="utf-8")
        (docs / "m.md").write_text(f"# Mid\nsummary: {MID}\n\nbody\n", encoding="utf-8")

    def test_the_limit_is_150_by_the_measure(self):
        line = next(ln for ln in run("order")[1].split("\n") if "`summary:` line(s) over" in ln)
        self.assertIn("docs/r.md", line)
        self.assertNotIn("docs/m.md", line, f"{len(MID)} chars is in the limit now")
        self.assertIn("over 150 chars", line)

    def test_the_reports_acceptance(self):  # a versioned proof is frozen: done says it, Order does not ask again
        _, err = self.ok("todo", "done", "1.1", "file:docs/r.md", "the comparison")
        self.assertIn(f"its `summary:` is {len(LONG)} chars, over 150", err)
        self.assertIn("rephrase line 2 now", err)
        self.assertNotIn("`summary:` line(s) over", run("order")[1])
        self.ok("todo", "accept", "1.1", "--by", "owner", "ok")
        self.ok("phase", "close", "1", "compared", "--reflect", "r", "--align", "a")
        self.assertNotIn("`summary:` line(s) over", run("order")[1], "a closed phase's proof stays frozen")

    def test_a_sub_items_proof_stays_frozen_after_the_close(self):  # Codex, 2026-10-14: only top items were read back
        self.ok("todo", "add", "1.1", "draft the comparison", "--expect", "[file: docs/r.md]")
        self.ok("todo", "done", "1.1.1", "file:docs/r.md", "the draft")
        self.ok("todo", "done", "1.1", "run:diff a b → 3 lines", "the comparison")
        self.ok("todo", "accept", "1.1", "--by", "owner", "ok")
        self.ok("todo", "accept", "1.1.1", "--by", "owner", "ok")
        self.ok("phase", "close", "1", "compared", "--reflect", "r", "--align", "a")
        self.assertNotIn("`summary:` line(s) over", run("order")[1])

    def test_the_warning_is_said_once(self):  # Codex, 2026-10-14: a second done of the accepted file asked again
        self.ok("todo", "done", "1.1", "file:docs/r.md", "the comparison")
        self.ok("todo", "accept", "1.1", "--by", "owner", "ok")
        _, err = self.ok("todo", "done", "1.1", "file:docs/r.md")
        self.assertNotIn("rephrase line 2 now", err)

    def test_a_frozen_file_brought_to_another_item_is_not_asked(self):  # Codex, 2026-10-14: the closed phase's file asked again
        self.ok("todo", "done", "1.1", "file:docs/r.md", "the comparison")
        self.ok("todo", "accept", "1.1", "--by", "owner", "ok")
        self.ok("phase", "close", "1", "compared", "--reflect", "r", "--align", "a")
        self.ok("phase", "open", "2", "Reuse", "--goal", "reuse [file]")
        self.ok("todo", "add", "2", "cite the comparison", "--expect", "[file: docs/r.md]")
        _, err = self.ok("todo", "done", "2.1", "file:docs/r.md", "cited")
        self.assertNotIn("rephrase line 2 now", err)

    def test_a_file_that_proves_nothing_is_still_asked(self):
        self.ok("todo", "done", "1.1", "run:diff a b → 3 lines", "the comparison")
        self.assertIn("`summary:` line(s) over 150 chars — docs/r.md", run("order")[1])


class ClosedCaseReopen(Base):
    def closed(self, name="probe", parent_flag=()):
        self.ok("case", "new", name, "--goal", "the probe answers", *parent_flag)
        self.ok("--case", name, "phase", "open", "1", "Probe", "--goal", "probe")
        self.ok("--case", name, "todo", "add", "1", "step")
        self.ok("--case", name, "todo", "done", "1.1", "run:x → ok", "ok")
        self.ok("--case", name, "todo", "accept", "1.1", "--by", "owner", "ok")
        self.ok("--case", name, "phase", "close", "1", "closed", "--reflect", "r", "--align", "a")
        self.ok("--case", name, "done", "the probe answers")
        self.ok("--case", name, "done", "--by", "owner", "good")
        return self.case(name)

    def test_the_reports_acceptance(self):  # refused with the door; once open, the phase is added
        case = self.closed()
        for verb in ("open", "plan"):
            code, _, err = run("--case", case.name, "phase", verb, "2", "Second", "--goal", "round two")
            self.assertEqual(code, 4, verb)
            self.assertIn("is closed", err)
            self.assertIn(f'el --case {case.name} case reopen "why it goes on"', err)
        self.assertNotIn("Second", (case / "TODO.md").read_text(encoding="utf-8"), "nothing was written")
        out, _ = self.ok("--case", case.name, "case", "reopen", "the owner asked for a second round")
        self.assertIn(f"reopened: {case.name}", out)
        readme = (case / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("- closed: ", readme)
        self.assertIn("дело открыто заново → the owner asked for a second round", (case / "JOURNAL.md").read_text(encoding="utf-8"))
        self.ok("--case", case.name, "phase", "open", "2", "Second", "--goal", "round two")
        self.ok("case", "use", case.name)

    def test_case_use_and_the_empty_hand_name_the_door(self):
        case = self.closed()
        code, _, err = run("case", "use", case.name)
        self.assertEqual(code, 4)
        self.assertIn(f'el --case {case.name} case reopen "why it goes on"', err)
        code, _, err = run("phase", "plan", "2", "Second")
        self.assertEqual(code, 4)
        self.assertIn(f'el --case {case.name} case reopen "why it goes on", then el --case {case.name} phase plan', err)

    def test_a_name_two_cases_share_is_printed_as_a_path(self):  # Codex, 2026-10-14: the printed `--case <name>` was refused
        for top in ("east", "west"):
            self.ok("case", "new", top, "--goal", "x")
            self.ok("--case", top, "phase", "open", "1", "Branch", "--goal", "b")
            self.ok("--case", top, "spawn", "probe", "--goal", "a branch")
        child = next(self.case("east").glob("*-probe"))
        rel = child.relative_to(Path(self.tmp.name, ".cases")).as_posix()
        for argv in (("phase", "open", "1", "Leaf", "--goal", "l"), ("todo", "add", "1", "s"),
                     ("todo", "done", "1.1", "run:x → ok", "ok"), ("todo", "accept", "1.1", "--by", "owner", "ok"),
                     ("phase", "close", "1", "c", "--reflect", "r", "--align", "a"), ("done", "the branch")):
            self.ok("--case", rel, *argv)
        code, _, err = run("case", "use", rel)
        self.assertEqual(code, 4)
        self.assertIn(f'el --case {rel} case reopen "why it goes on", then el case use {rel}', err)
        self.ok("--case", rel, "case", "reopen", "more")

    def test_a_top_case_sharing_a_nested_name_is_printed_as_a_path(self):  # Codex, 2026-10-14: `--case <name>` was ambiguous
        top = self.closed("probe")  # a top case, then a nested one of the same name
        self.ok("case", "new", "outer", "--goal", "x")
        self.ok("--case", "outer", "phase", "open", "1", "Branch", "--goal", "b")
        self.ok("--case", "outer", "spawn", "probe", "--goal", "a branch")
        rel = top.relative_to(Path(self.tmp.name)).as_posix()  # .cases/<date>-probe
        code, _, err = run("case", "use", rel)
        self.assertEqual(code, 4)
        self.assertIn(f'el --case {rel} case reopen "why it goes on"', err)
        self.ok("--case", rel, "case", "reopen", "more")

    def test_reopen_needs_a_closed_case_and_a_reason(self):
        self.ok("case", "new", "live", "--goal", "x")
        code, _, err = run("--case", "live", "case", "reopen", "why")
        self.assertEqual(code, 4)
        self.assertIn("is open — nothing to reopen", err)
        case = self.closed()
        code, _, err = run("--case", case.name, "case", "reopen")
        self.assertEqual(code, 2)
        self.assertIn("reopen needs a reason", err)

    def test_a_closed_parent_is_opened_first(self):  # nothing open lies under a closed node
        self.ok("case", "new", "top", "--goal", "the map")
        top = self.case("top")
        self.ok("--case", top.name, "phase", "open", "1", "Branch", "--goal", "b")
        self.ok("--case", top.name, "spawn", "child", "--goal", "a branch")
        child = next(top.glob("*-child"))
        for argv in (("phase", "open", "1", "Leaf", "--goal", "l"), ("todo", "add", "1", "s"),
                     ("todo", "done", "1.1", "run:x → ok", "ok"), ("todo", "accept", "1.1", "--by", "owner", "ok"),
                     ("phase", "close", "1", "c", "--reflect", "r", "--align", "a"), ("done", "the branch")):
            self.ok("--case", child.name, *argv)
        for argv in (("todo", "add", "1", "s"), ("todo", "done", "1.2", "run:x → ok", "ok"),  # 1.1 is the child's, spawn made it
                     ("todo", "accept", "1.1-1.2", "--by", "owner", "ok"),
                     ("phase", "close", "1", "c", "--reflect", "r", "--align", "a"), ("done", "the map"), ("done", "--by", "owner", "good")):
            self.ok("--case", top.name, *argv)
        code, _, err = run("--case", child.name, "case", "reopen", "more")
        self.assertEqual(code, 4)
        self.assertIn(f"the parent {top.name} is closed — open it first", err)
        self.ok("--case", top.name, "case", "reopen", "a second branch")
        self.ok("--case", child.name, "case", "reopen", "more")
        self.assertNotIn("- closed: ", (child / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
