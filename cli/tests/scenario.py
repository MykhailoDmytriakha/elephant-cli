#!/usr/bin/env python3
"""scenario.py — the proof that `el` still does what it did.

A DIFFERENTIAL test, not a unit test: the CLI is a bookkeeping tool whose whole
contract is "given these commands, this is what lands on disk and on the screen".
So the test replays one long, scripted scenario — every command, the gates, the
refusals, the aliases, the `--task` variants, a run from a sub-folder, the
ELEPHANT_DIR override, an ambiguous storage — against a fresh temporary project,
and records, per step: argv · exit code · stdout · stderr. At the end it records
the whole project tree with file contents. Times and absolute paths are normalised
(a timestamp is not a behaviour). Two runs — two binaries, or a binary before and
after a change — are then compared byte for byte.

    python3 cli/tests/scenario.py run  --bin cli/el.py --out /tmp/snap-new
    python3 cli/tests/scenario.py run  --bin cli/el.old.py --out /tmp/snap-old
    python3 cli/tests/scenario.py diff /tmp/snap-old /tmp/snap-new

    --fixture <storage>   also replay read-and-write commands on a COPY of a real
                          storage (the one with the .elephant marker), task by task
    --trace               wrap every call in `python -m trace --count` and write a
                          line-coverage report next to the snapshot (slow; advisory —
                          trace swallows SystemExit, so exit codes are not checked)
    --keep                keep the temporary workspace and print its path

Exit codes the scenario EXPECTS are written next to each step; a mismatch is
reported at the end (and recorded in summary.json) but never stops the run — the
binary under test is the truth, the expectation is a smoke check.

TAKING THE «OLD» SNAPSHOT — export the WHOLE skill, not just cli/ (an agent lost ten
minutes here, 2026-08-22): the page templates in html/ are resolved RELATIVE TO THE
BINARY (state.SKILL_ROOT), so a bare `git archive HEAD elephant/cli` runs a binary that
finds no templates and yields thousands of lines of false diff in tree.txt.

    git -C ~/.claude/skills archive HEAD elephant | tar -x -C /tmp/el-old
    python3 cli/tests/scenario.py run --bin /tmp/el-old/elephant/cli/el.py --out /tmp/snap-old

`run` checks that html/overview.html sits next to the binary and says so if it does not.
The tool's inbox (feedback/ in the skill) is redirected into the workspace for every step
via ELEPHANT_FEEDBACK_DIR — a test run must never write into the skill.

Standard library only, like the tool it tests.
"""
import argparse, difflib, glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from datetime import datetime

HERE = os.path.dirname(os.path.realpath(__file__))      # cli/tests
CLI_DIR = os.path.dirname(HERE)                          # cli
SKILL = os.path.dirname(CLI_DIR)                         # the skill root


# ── the scenario ─────────────────────────────────────────────────────────────
#
# Each step: argv (without the binary) · cwd key · expected rc · optional pre-hook ·
# optional env additions. The cwd keys name folders of the workspace:
#   A      the main project (a real git repo with a CLAUDE.md marker)
#   A/sub  a sub-folder two levels inside A — the walk-up lookup
#   N      a neutral folder with no storage anywhere above it (bounded by a .git dir)
#   C      a project holding TWO marked folders — the ambiguous case
#   D      a project where the storage is created in a custom --dir
#   R      the copy of a real storage, when --fixture is given

def _step(argv, rc=0, cwd="A", pre=None, env=None, label=None):
    return {"argv": list(argv), "rc": rc, "cwd": cwd, "pre": pre, "env": env or {},
            "label": label or " ".join(argv)}


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _task_dir(ws, tail):
    """The task folder whose name ends with `tail` — the date prefix is today's."""
    hits = glob.glob(os.path.join(ws["A"], ".projects", "*-" + tail))
    assert len(hits) == 1, (tail, hits)
    return hits[0]


# pre-hooks: things an AGENT does by hand around the CLI (files it writes, the git tree)
def pre_git(ws):
    subprocess.run(["git", "init", "-q"], cwd=ws["A"], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _write(os.path.join(ws["A"], "CLAUDE.md"), "# test project\n")
    os.makedirs(os.path.join(ws["A"], "sub", "dir"), exist_ok=True)


def pre_out_files(ws):
    _write(os.path.join(ws["A"], "out", "app.apk"), "not really an apk\n")
    _write(os.path.join(ws["A"], "out", "log.txt"), "build ok\ntests green\n")


def pre_plan_md_A(ws):
    _write(os.path.join(_task_dir(ws, "share-songs-from-journal-now"), "plan.md"),
           "# Сетевой план\n\nS1 → S1.WP1 → S2; остановка после S1.WP1.\n")


THINK_FILES = ["mirror", "form", "core", "ideals", "research", "baseline", "shoals",
               "reversibility", "options", "crystal", "refute", "order"]


def pre_think_files_B(ws):
    d = os.path.join(_task_dir(ws, "share-songs"), "thinking")
    for k in THINK_FILES:
        _write(os.path.join(d, k + ".md"), f"# {k}\n\nнаписано агентом для теста: {k}.\n")


def pre_junk_files(ws):
    """Nine untracked files: `el done` shows eight and counts the rest."""
    for i in range(9):
        _write(os.path.join(ws["A"], f"j{i}.txt"), "junk\n")


def pre_context_scraps(ws):
    """A non-markdown file and a dotfile inside context/: skipped by the coverage
    map, and the dotfile skipped by the page inventory."""
    d = os.path.join(_task_dir(ws, "share-songs-from-journal-now"), "context")
    _write(os.path.join(d, "scratch.txt"), "not markdown\n")
    _write(os.path.join(d, ".hidden"), "dot\n")


def pre_age_journals(ws):
    """Push two journals into the past so `el projects` prints «вчера» and «N дн. назад»."""
    now = time.time()
    for tail, days in (("dependent-one", 1), ("chords-editor", 3)):
        jp = os.path.join(_task_dir(ws, tail), "journal.jsonl")
        os.utime(jp, (now - days * 86400, now - days * 86400))


def pre_age_task_d(ws):
    hits = glob.glob(os.path.join(ws["D"], "store2", "*-task-d", "journal.jsonl"))
    assert len(hits) == 1, hits
    os.utime(hits[0], (time.time() - 10 * 86400, time.time() - 10 * 86400))


def pre_preview_B(ws):
    """A tiny interactive preview the agent built somewhere outside the project."""
    _write(os.path.join(ws["home"], "preview-g1.html"),
           "<!doctype html><title>g1</title><button>один</button><button>два</button>\n")


def pre_plan_md_B(ws):
    _write(os.path.join(_task_dir(ws, "share-songs"), "plan.md"),
           "# План B\n\nпока только набросок.\n")


def pre_letter(ws):
    """A long review written elsewhere — `el feedback --file` takes it whole."""
    _write(os.path.join(ws["home"], "letter.md"),
           "# Письмо агенту, который дорабатывает el\n\nПонравилось: знание дозами.\n\n"
           "Обжёгся: `el beat` без --task.\n")


def pre_ambiguous(ws):
    for n in (".a", ".b"):
        _write(os.path.join(ws["C"], n, ".elephant"), "")


def pre_neutral(ws):
    os.makedirs(os.path.join(ws["N"], ".git"), exist_ok=True)       # bounds the walk-up
    os.makedirs(os.path.join(ws["C"], ".git"), exist_ok=True)
    os.makedirs(os.path.join(ws["D"], ".git"), exist_ok=True)


def scenario(ws):
    S = _step
    A_ID = "share-songs-from-journal-now"
    B_ID = "share-songs"
    steps = []
    add = steps.append

    # ── stage 0: nothing here yet ────────────────────────────────────────────
    add(S([], pre=pre_git, label="el (bare, no storage)"))
    add(S(["status"], cwd="N", pre=pre_neutral, label="status in a neutral folder, no storage"))
    for argv in (["think", "fork", "f1", "q"], ["plan", "new", "s1", "x"], ["accept", "x"],
                 ["todo", "x"], ["lesson", "x"], ["research", "code", "x"],
                 ["forward", "--why", "x"], ["phase", "think"], ["done", "x"],
                 ["reopen", "x"], ["spawn", "x", "--id", "y"], ["beat", "x"],
                 ["artifact", "x"], ["validate"], ["sync"], ["think", "tools"],
                 ["think", "skip", "mirror", "--why", "x"], ["think", "decide", "f1", "x"],
                 ["context", "qa", "q", "a", "--area", "goal"], ["context", "scope"],
                 ["context", "requirements", "x"], ["context", "unknown", "x"],
                 ["context", "beyond", "x"], ["context", "areas"], ["left"], ["where"],
                 ["use", "x"], ["log", "x"]):
        add(S(argv, rc=1, cwd="N", label="no storage: " + " ".join(argv)))
    add(S(["status"]))
    add(S(["next"]))
    add(S(["projects"]))
    add(S(["ls"]))
    add(S(["where"], rc=1))
    add(S(["context"]))
    add(S(["context", "--line"]))
    add(S(["new", "x", "--id", "y"], rc=1))
    add(S(["left"], rc=1))
    add(S(["ui"], rc=1))
    add(S(["boot"], label="el boot (folder only)"))
    add(S(["init"]))
    add(S([], label="el (bare, storage, no tasks)"))
    add(S(["status"]))
    add(S(["next"]))
    add(S(["projects"]))
    add(S(["context"]))
    add(S(["context", "--json"]))
    add(S(["where"]))
    add(S(["left"], rc=1))
    add(S(["plan"], rc=1))
    add(S(["think"], rc=1))
    add(S(["validate"], rc=1))
    add(S(["log", "x"], rc=1))
    add(S(["use", "x"], rc=1))
    for argv in (["think", "fork", "f1", "q"], ["plan", "new", "s1", "x"], ["accept", "x"],
                 ["todo", "x"], ["research", "code", "x"], ["forward", "--why", "x"],
                 ["phase", "think"], ["done", "x"], ["beat", "x"], ["artifact", "x"],
                 ["sync"], ["think", "tools"], ["think", "skip", "mirror", "--why", "x"],
                 ["think", "decide", "f1", "x"], ["context", "qa", "q", "a", "--area", "goal"],
                 ["context", "scope"], ["context", "requirements", "x"],
                 ["context", "unknown", "x"], ["context", "beyond", "x"],
                 ["context", "areas"], ["reopen", "x"]):
        add(S(argv, rc=1, label="no tasks: " + " ".join(argv)))
    add(S(["lesson", "урок без задачи"], label="lesson with no task: lands as «—»"))
    add(S(["new", "Собрать песни из дневника и выложить"], rc=1))
    add(S(["new", "Собрать песни из дневника и выложить", "--id",
           "Share Songs From Journal Now Please"]))
    add(S(["next"], label="el next (init nag: request not recorded)"))
    add(S(["new", "again", "--id", A_ID]))
    add(S(["boot", "Песни из дневника", "--id", B_ID, "--raw",
           "хочу делиться песнями из дневника одной кнопкой"], rc=1,
          label="boot: looks like a twin of the first task — refused, the twin named"))
    add(S(["boot", "Песни из дневника", "--id", B_ID, "--raw",
           "хочу делиться песнями из дневника одной кнопкой", "--force"],
          label="boot --force: the second task on purpose"))
    add(S(["boot", "Песни из дневника", "--id", B_ID, "--raw", "повтор"]))
    add(S(["projects"]))
    add(S(["use", A_ID]))
    add(S(["use", "nope"], rc=1))
    add(S(["use", datetime.now().strftime("%Y-%m-%d") + " share songs from journal now"],
          label="use: id typed with spaces and the date — minted form resolves"))
    add(S(["context", "qa", "--list", "--task", B_ID], label="qa --list before any pair"))
    add(S(["context", "qa", "Q", "   ", "--area", "goal"], rc=1,
          label="qa: whitespace answer refused"))
    add(S(["boot", "x", "--id", A_ID, "--raw", "сырые слова первой задачи дословно"]))
    add(S(["status"]))
    add(S(["next"]))
    add(S(["where"]))
    add(S(["path"]))
    add(S(["context"]))
    add(S(["ctx"]))
    add(S(["context", "--json"]))
    add(S(["context", "--line"]))
    add(S(["context", "--section", "ifr"]))
    add(S(["context", "--section", "nosuch"], rc=1))
    add(S(["context", "--task", "nope"], rc=1, label="context --task: unknown task is an error, not the held one"))
    add(S(["next"], cwd="A/sub", label="el next from a sub-folder"))
    add(S(["status"], cwd="A/sub"))

    # ── context phase, task A: the ladder, the gates, the refusals ───────────
    add(S(["context", "qa"], rc=1))
    add(S(["context", "qa", "q1", "a1"], rc=1))
    add(S(["context", "qa", "q1", "a1", "--area", "bogus"], rc=1))
    add(S(["context", "qa", "Как вы это используете?", "Отправляю список программы в чат",
           "--area", "goal"]))
    add(S(["context", "qa", "Кому?", "Ведущему прославления", "--area", "who"]))
    add(S(["context", "qa", "Что обязательно?", "Имя и текст", "--area", "must",
           "--new-round"]))
    add(S(["context", "qa", "Когда нужно?", "В четверг вечером", "--area", "when",
           "--round", "2"]))
    add(S(["context", "qa", "Зачем?", "Чтобы не копировать руками", "--area", "why"]))
    add(S(["context", "qa", "--list"]))
    add(S(["context", "qa", "Q", "", "--area", "goal"], rc=1))
    add(S(["context", "areas"]))
    add(S(["next"]))
    add(S(["context", "scope"]))
    add(S(["context", "scope", "what"], rc=1))
    add(S(["context", "scope", "bogus", "--in", "x"], rc=1))
    add(S(["context", "scope", "what", "--in", "делимся песнями", "--out",
           "не редактор текстов"]))
    add(S(["context", "scope", "why", "--in", "боль: копирование руками"]))
    add(S(["context", "scope", "who", "--in", "ведущий", "--blur", "а гости?"]))
    add(S(["context", "scope", "where", "--in", "телефон и ноутбук"]))
    add(S(["context", "scope", "when", "--blur", "пока неясно"]))
    add(S(["next"]))
    add(S(["forward", "--why", "test"], rc=1, label="forward: scope incomplete"))
    add(S(["context", "scope", "when", "--in", "в четверг перед служением", "--replace"]))
    add(S(["context", "scope", "how", "--in", "через share intent"]))
    add(S(["context", "scope"]))
    add(S(["context", "areas"]))
    add(S(["forward", "--why", "test"], rc=1, label="forward: owner areas blank"))
    add(S(["context", "qa", "Как выглядит успех?", "Список в чате одним сообщением",
           "--area", "outcome"]))
    add(S(["context", "qa", "Чего нельзя?", "Нельзя менять формат дневника",
           "--area", "limits"]))
    add(S(["context", "qa", "Как проверишь?", "открою чат — там один список",
           "--area", "check"]))
    add(S(["forward", "--why", "test"], rc=1, label="forward: no owner word"))
    add(S(["accept"], rc=1))
    add(S(["accept", "да, всё так"]))
    add(S(["forward", "--why", "test"], rc=1, label="forward: traces missing"))
    add(S(["context", "requirements"], rc=1))
    add(S(["context", "requirements", "есть: дневник в приложении; нет: экспорта"]))
    add(S(["context", "requirements", "дописка: ещё один пункт"]))
    add(S(["context", "requirements"]))
    add(S(["context", "requirements", "заново", "--replace"]))
    add(S(["context", "constraints", "бюджет нулевой"]))
    add(S(["context", "limitations", "нет доступа к API"]))
    add(S(["context", "resources", "один разработчик"]))
    add(S(["context", "finance", "денег в задаче нет"]))
    add(S(["context", "tools", "kotlin, android"]))
    add(S(["context", "definitions", "программа — список песен на служение"]))
    add(S(["context", "beyond"], rc=1))
    add(S(["context", "beyond", "рядом: редактор аккордов — НЕ делаем"]))
    add(S(["context", "success", "список уходит сам, править руками не надо"]))
    add(S(["context", "outcomes", "в чате появляется список программы"]))
    add(S(["context", "metrics", "сообщений — ровно одно; ручных правок — 0"]))
    add(S(["context", "checklist", "- нажать поделиться → в чате один список\n"
           "- открыть список → порядок как в программе"]))
    # HOW HE SEES THE WORK IN BIG PIECES — the second source of route integrity (2026-08-24)
    add(S(["context", "parts", "- собрать список\n- отправить в чат\n- убедиться, что дошло"],
          label="parts: his rough shape of the road, in his words"))
    add(S(["context", "ifr", "идеал: одна кнопка → список в чате"]))
    add(S(["context", "clarified", "задача: кнопка поделиться программой"]))
    add(S(["status"], pre=pre_context_scraps, label="status: task state «clarified»"))
    add(S(["context", "summary", "всё собрано: кнопка, intent, список"]))
    add(S(["context", "unknown"], rc=1))
    add(S(["context", "unknown", "не знаю формат дневника", "--risk", "посмотрю код"]))
    add(S(["context", "unknown", "второе незнание"]))
    add(S(["research"], label="research (bare): empty folder, listed"))
    add(S(["research", "code", "копия шлёт имя и текст", "--ref", "app/Share.kt:318",
           "--area", "how"]))
    add(S(["context", "add", "code", "вторая находка", "--ref", "x.kt:1"]))
    add(S(["research"], label="research (bare): sources with findings and size"))
    add(S(["ctx", "--section", "code"], label="ctx --section: a research file is readable"))
    add(S(["research", "web", "находка", "--area", "bogus"], rc=1))
    add(S(["context"]))
    add(S(["context", "--section", "требован"]))
    add(S(["context", "--section", "источник"], rc=1, label="context --section: sources moved to research/"))
    add(S(["next"]))
    add(S(["status"]))
    add(S(["left"]))
    add(S(["forward"], rc=1, label="forward: no reason"))
    add(S(["forward", "--why", "контекст собран и утверждён"]))
    add(S(["status"]))
    add(S(["phase", "execute"], rc=1))
    add(S(["phase", "think"]))
    add(S(["phase", "bogus"], rc=1))

    # ── think phase, task A: forks, tools, skip; leaves by --waive ───────────
    add(S(["next"]))
    add(S(["think"]))
    add(S(["think", "forks"]))
    add(S(["think", "tools"]))
    add(S(["think", "tools", "взял пять почему — дал корень"]))
    add(S(["think", "skip"], rc=1))
    add(S(["think", "skip", "decision", "--why", "x"], rc=1))
    add(S(["think", "skip", "mirror"], rc=1))
    add(S(["think", "skip", "mirror", "--why", "один пользователь, очевидно"]))
    add(S(["think", "skip", "mirror", "--why", "опять"]))
    add(S(["think", "fork"], rc=1))
    add(S(["think", "fork", "f1", "--option", "x", "--cost", "y"], rc=1))
    add(S(["think", "fork", "f1", "как шарить: intent или буфер?", "--who", "owner"]))
    add(S(["think", "fork", "f1", "again"]))
    add(S(["think", "fork", "f2", "q", "--who", "bogus"], rc=1))
    add(S(["think", "fork", "f1", "--option", "intent"], rc=1))
    add(S(["think", "fork", "f1", "--option", "intent", "--cost",
           "зависимость от системы", "--recommend"]))
    add(S(["think", "fork", "f1", "--option", "буфер", "--cost", "ручная вставка"]))
    add(S(["think", "decide", "f1", "intent"], rc=1))
    add(S(["think", "decide", "f1", "intent", "--words", "intent, конечно"], rc=1))
    add(S(["think", "fork", "f1", "--option", "ничего не делать", "--cost",
           "остаётся копирование руками"]))
    add(S(["think", "decide"], rc=1))
    add(S(["think", "decide", "f9", "x"], rc=1))
    add(S(["think", "decide", "f1"], rc=1))
    add(S(["forward", "--why", "x"], rc=1, label="forward: open forks"))
    add(S(["next"]))
    add(S(["think", "decide", "f1", "intent", "--words", "intent, конечно"]))
    add(S(["think", "fork", "f2", "второй вопрос", "--who", "agent"]))
    add(S(["think", "fork", "f2", "--option", "a", "--cost", "1"]))
    add(S(["think", "fork", "f2", "--option", "b", "--cost", "2"]))
    add(S(["think", "decide", "f2", "a", "--why", "проще", "--narrow", "третьего нет"]))
    add(S(["think", "forks"]))
    add(S(["think"]))
    add(S(["context"]))
    add(S(["forward", "--why", "x"], rc=1, label="forward: think traces missing"))
    add(S(["forward", "--waive", "думание минимальное для теста"]))

    # ── plan phase, task A: nodes, fields, stops, acceptance ─────────────────
    add(S(["next"], label="next: plan, no nodes"))
    add(S(["plan"]))
    add(S(["sync"]))
    add(S(["plan", "new"], rc=1))
    add(S(["plan", "new", "s1", "Подготовка"]))
    add(S(["plan", "new", "s1", "dup"]))
    add(S(["plan", "new", "s1", "wp1", "Пакет"], rc=1))
    add(S(["plan", "new", "s9", "wp1", "x"], rc=1))
    add(S(["plan", "new", "s3"]))
    add(S(["plan", "s3"]))
    add(S(["plan", "rm", "s3"]))
    add(S(["plan", "rm"], rc=1))
    add(S(["plan", "rm", "s9"], rc=1))
    add(S(["sync"]))
    add(S(["next"]))
    add(S(["plan", "s1"]))
    add(S(["plan", "set"], rc=1))
    add(S(["plan", "set", "s1", "result", "дневник открывается"]))
    for i in range(1, 5):
        add(S(["plan", "set", "s1", "check", f"критерий {i}"]))
    add(S(["plan", "set", "s1", "check", "- критерий 5 с дефисом"]))
    add(S(["plan", "set", "s1", "resources", "время: 1ч"]))
    add(S(["plan", "set", "s1", "artifacts", "apk"]))
    add(S(["plan", "set", "s1", "storage", "artifacts/app.apk"]))
    add(S(["plan", "set", "s1", "inputs", "N/A — первый узел"]))
    add(S(["plan", "set", "s1", "deps", "нет"]))
    add(S(["plan", "set", "s1", "executor", "AGENT"]))
    add(S(["plan", "set", "s1", "sync", "показываю: сообщение"], rc=1))
    add(S(["plan", "set", "s1", "sync", "показываю: сообщение\nувидишь: список\n"
           "потрогать: файл\nот тебя: ничего"]))
    add(S(["plan", "set", "s1", "sync", "- развилка тут"], rc=1))
    add(S(["plan", "set", "s1", "sync", "от тебя: решение", "--replace"], rc=1))
    add(S(["plan", "s1"]))
    add(S(["plan", "new", "s1", "wp1", "Пакет работ"]))
    add(S(["plan", "s1"], label="plan s1: with a child inside"))
    add(S(["plan", "new", "имя с пробелом"], rc=1))
    add(S(["plan", "set", "s9", "result", "x"], rc=1))
    add(S(["plan", "new", "s1", "wp1", "t1", "Задача"], rc=1))
    add(S(["plan", "s1", "wp1"]))
    add(S(["plan", "S1.WP1"]))
    add(S(["plan", "nosuch"], rc=1))
    add(S(["plan", "set", "s1", "wp1", "result", "список собран"]))
    for i in range(1, 6):
        add(S(["plan", "set", "s1", "wp1", "check", f"wp критерий {i}"]))
    add(S(["plan", "set", "s1", "wp1", "resources", "время"]))
    add(S(["plan", "set", "s1", "wp1", "artifacts", "список"]))
    add(S(["plan", "set", "s1", "wp1", "storage", "artifacts/list.txt"]))
    add(S(["plan", "set", "s1", "wp1", "inputs", "apk из S1"]))
    add(S(["plan", "set", "s1", "wp1", "deps", "S1"]))
    add(S(["plan", "set", "s1", "wp1", "executor", "AGENT"]))
    add(S(["plan", "set", "s1", "wp1", "sync", "показываю: список\nувидишь: порядок\n"
           "потрогать: файл\nот тебя: решение — принять ли вид"]))
    add(S(["plan", "new", "s2", "Второй этап"]))
    add(S(["next"]))
    add(S(["forward", "--why", "x"], rc=1, label="forward: node with holes"))
    add(S(["plan", "set", "s2", "result", "r"]))
    for i in range(1, 6):
        add(S(["plan", "set", "s2", "check", f"s2 критерий {i}"]))
    for k, v in (("resources", "x"), ("artifacts", "x"), ("storage", "x"),
                 ("inputs", "x"), ("deps", "S1"), ("executor", "HUMAN")):
        add(S(["plan", "set", "s2", k, v]))
    add(S(["plan", "set", "s2", "sync", "показываю: сборку\nувидишь: экран\n"
           "потрогать: эмулятор\nот тебя: РАЗРЕШЕНИЕ на коммит"]))
    add(S(["plan", "set", "s2", "resources", "x заново", "--replace"]))
    add(S(["next"], label="next: plan filled, owner's yes missing"))
    add(S(["sync"]))
    add(S(["plan"]))
    add(S(["left"]))
    add(S(["plan", "done"], rc=1))
    add(S(["plan", "done", "s9"], rc=1))
    # ЗАКРЫТИЕ = ПЕЧАТЬ ПРОВЕРКИ (owner, 2026-08-23). A node no longer closes over criteria
    # without verdicts, and a parent no longer closes before its children — so the scenario
    # now answers the criteria first, and every refusal below keeps its ORIGINAL meaning.
    add(S(["plan", "done", "s1", "wp1", "готово"], rc=1,
          label="plan done: criteria without verdicts hold the node"))
    for i in range(1, 6):
        add(S(["validate", "s1", "wp1", str(i), "--met", f"проверено по ходу {i}"]))
    add(S(["validate", "s1", "wp1"], label="validate <node>: own criteria of a leaf"))
    add(S(["plan", "done", "s1", "wp1", "готово"], rc=1, label="plan done: stop, no word"))
    add(S(["forward", "--why", "x"], rc=1, label="forward: plan needs owner's yes"))
    add(S(["accept", "план принят, поехали", "--on", "план целиком"]))
    add(S(["plan", "done", "s1"], rc=1, label="plan done: a parent closes after its children"))
    add(S(["sync"], label="sync: next stop is a РАЗВИЛКА"))
    add(S(["plan", "done", "s1", "wp1", "готово"]))
    for i in range(1, 5):
        add(S(["validate", "s1", str(i), "--met", f"этап проверен {i}"]))
    add(S(["validate", "s1", "5", "--failed", "интеграция не сошлась"]))
    add(S(["plan", "done", "s1"], rc=1, label="plan done: «не сошлось» does not close a node"))
    add(S(["validate", "s1", "5", "--met", "перемерил после починки — сошлось"]))
    add(S(["plan", "done", "s1"], label="plan done: the roll-up card, own + children"))
    add(S(["validate", "s1"], label="validate <node>: own criteria plus the children's roll-up"))
    add(S(["sync"], label="sync: next stop is a РАЗРЕШЕНИЕ"))
    add(S(["plan", "set", "s2", "check", "s2 критерий 6\n  с продолжением на второй строке"]))
    add(S(["plan", "set", "s2", "check", "1) первый 2) второй 3) третий"],
          label="plan set check: a numbered list is a LIST, not one criterion"))
    for i in range(1, 10):
        add(S(["validate", "s2", str(i), "--met", f"s2 проверено {i}"]))
    add(S(["plan", "done", "s2", "x"], rc=1, label="plan done: node newer than word"))
    add(S(["plan", "done", "s2", "x", "--force"]))
    add(S(["validate"], label="validate: the whole matryoshka, the task on top"))
    # IFR is a target for a proof too — it is the ledger's pseudo-node, not a plan node
    add(S(["evidence", "out/log.txt", "--node", "ifr", "--check", "1"],
          pre=pre_out_files, label="evidence --node ifr: the checklist item takes a proof"))
    add(S(["plan", "show", "s1"], rc=1, label="plan show: a verb that is not one says so"))
    add(S(["plan", "rm", "s1"], rc=1))
    add(S(["plan"]))
    add(S(["sync"], label="sync: all stops passed"))
    add(S(["next"]))
    add(S(["status"]))
    # ROUTE INTEGRITY holds the plan gate now (owner, 2026-08-24): every checklist item and
    # every big piece he named must be covered by a node or by a declared unfold.
    add(S(["plan", "integrity"], rc=1, label="integrity: nothing is covered yet"))
    add(S(["plan", "cover"], rc=1, label="cover: usage"))
    add(S(["plan", "cover", "s1", "ifr", "1"], label="cover: a node closes a checklist item"))
    add(S(["plan", "cover", "s1", "ifr", "9"], rc=1, label="cover: no such item"))
    add(S(["plan", "cover", "s2", "ifr", "2"]))
    add(S(["plan", "unfold", "s3"], rc=1, label="unfold: usage"))
    add(S(["plan", "unfold", "s3", "разрешает ли лицензия коммерческое использование"], rc=1,
          label="unfold: --after is owed — otherwise it is a way not to think"))
    add(S(["plan", "unfold", "s3", "разрешает ли лицензия коммерческое использование",
           "--after", "s2"], label="unfold: a hole named out loud is part of the route"))
    add(S(["plan", "cover", "s3", "part", "1"], label="cover: the unfold stands for a big piece"))
    add(S(["plan", "cover", "s1", "part", "2"]))
    add(S(["plan", "cover", "s2", "part", "3"]))
    add(S(["plan", "integrity"], label="integrity: covered, one piece unfolds later"))
    add(S(["forward", "--why", "план принят владельцем"], rc=1,
          label="forward: plan.md missing"))
    add(S(["plan"], pre=pre_plan_md_A))
    add(S(["forward", "--why", "план принят владельцем"]))

    # ── execute phase, task A ───────────────────────────────────────────────
    add(S(["next"]))
    add(S(["left"]))
    add(S(["artifact"], rc=2))
    add(S(["artifact", "out/app.apk", "--why", "сборка"], pre=pre_out_files))
    add(S(["artifact", "out/app.apk", "--node", "s1", "--check", "1", "--why", "к узлу"],
          label="artifact --node --check: filed to the node"))
    add(S(["evidence", "out/log.txt", "--node", "s9"], rc=1, label="evidence --node: no such node"))
    add(S(["evidence", "out/log.txt", "--node", "s1.wp1", "--as", "wp1-log"]))
    add(S(["doctor"], label="doctor at execute: all nodes closed"))
    add(S(["artifact", "out/app.apk", "out/log.txt", "--as", "renamed"], rc=1))
    add(S(["artifact", "out/log.txt", "--as", "build-log"]))
    add(S(["evidence", "out/log.txt"]))
    add(S(["evidence", "nofile.txt"], rc=1))
    add(S(["log", "сделал шаг", "--type", "step"]))
    add(S(["log", "заметка"]))
    add(S(["log", "x", "--type", "advance"], rc=1))
    add(S(["beat", "sync", "--ref", "artifacts/app.apk"]))
    add(S(["beat", "gate"]))
    add(S(["todo"]))
    add(S(["todo", "проверить на телефоне", "--when", "validate", "--why",
           "эмулятор не то"]))
    add(S(["todo", "x", "--when", "bogus"], rc=1))
    add(S(["todo", "без фазы"]))
    add(S(["todo", "--list"]))
    add(S(["todo", "--all"], label="todo --all: closed items too"))
    add(S(["todo", "--done", "5"], rc=1))
    add(S(["next"]))
    add(S(["context", "ifr", "метрика: одно сообщение, без вложений", "--adds", "--why",
           "evidence показал лимит intent", "--ref", "evidence/log.txt"],
          label="amend п1 ifr at execute"))
    add(S(["next"], label="next: amendment without his word"))
    add(S(["plan", "park", "s3", "--why", "лицензию решили не трогать в этой задаче"],
          label="park: a declared blank spot closed on purpose, not unfolded"))
    add(S(["forward", "--why", "исполнено"], rc=1, label="forward: amendment without his word"))
    add(S(["accept", "ок, принимаю поправку"], label="accept covers the amendment"))
    add(S(["forward", "--why", "исполнено"]))

    # ── validate phase, task A: the ledger ─────────────────────────────────
    add(S(["next"]))
    add(S(["validate"]))
    add(S(["validate", "s1"]))
    add(S(["validate", "s9"], rc=1))
    add(S(["validate", "s1", "9"], rc=1))
    add(S(["validate", "s1", "1"], rc=1))
    add(S(["validate", "s1", "1", "--skip", "x"], rc=1))
    add(S(["validate", "s1", "1", "--met", "проверено глазами", "--evidence", "evidence/nope.png"],
          rc=1, label="validate --evidence: file must exist"))
    add(S(["validate", "s1", "1", "--met", "проверено глазами", "--evidence", "evidence/log.txt"],
          label="validate --evidence: proof links the file"))
    add(S(["validate", "s1", "2", "--failed", "не сошлось"]))
    add(S(["validate", "s1", "3", "--declined", "работа отменена"]))
    add(S(["validate", "s1", "4", "--unverified", "не мерили"]))
    add(S(["validate", "s1", "5", "--met", "ок"]))
    add(S(["check"]))
    add(S(["left"]))
    add(S(["next"]))
    add(S(["forward", "--why", "x"], rc=1, label="forward: criteria open"))
    add(S(["forward", "--waive", "x"], rc=1, label="forward --waive: open criteria stay hard"))
    add(S(["validate", "s1", "wp1", "1", "--met", "x"],
          label="validate by PATH words: lists S1, marks nothing"))
    for i in range(1, 6):
        add(S(["validate", "s1.wp1", str(i), "--met", f"wp ок {i}"]))
    add(S(["validate", "S1.WP1"]))
    for i in range(1, 7):
        add(S(["validate", "s2", str(i), "--met", f"s2 ок {i}"]))
    add(S(["validate", "ifr"], label="validate ifr: the checklist as a ledger node"))
    add(S(["validate", "ifr", "1", "--met", "потрогал: один список"]))
    add(S(["validate", "ifr", "2", "--met", "порядок верный"]))
    add(S(["forward", "--why", "x"], rc=1, label="forward: unverified debt"))
    add(S(["validate", "s1", "4", "--met", "теперь мерили"]))
    add(S(["forward", "--why", "x"], rc=1, label="forward: failed criterion"))
    add(S(["validate", "s1", "2", "--met", "починил"]))
    add(S(["validate"]))
    add(S(["next"], label="next: criteria done, acceptance word missing"))
    add(S(["left"]))
    add(S(["accept", "готово по сценарию", "--for", "observation:s1"],
          label="accept --for observation: not the final word"))
    add(S(["forward", "--why", "проверено"], rc=1, label="forward: no acceptance word on validate"))
    add(S(["forward", "--waive", "x"], rc=1, label="forward --waive: acceptance not waivable"))
    add(S(["accept", "принимаю результат, потрогал"]))
    add(S(["next"]))
    add(S(["forward", "--why", "проверено"]))
    add(S(["validate", "s1", "1", "--met", "ещё раз, уже на reflect"]))

    # ── reflect · align · close, task A ────────────────────────────────────
    add(S(["next"]))
    add(S(["lesson"], rc=2))
    add(S(["lesson", ""], rc=1))
    add(S(["lesson", "не закрывай задачу без коммита"]))
    add(S([], label="el (bare, with lessons)"))
    for i in range(2, 9):
        add(S(["lesson", f"урок номер {i}"]))
    add(S([], label="el (bare, more than seven lessons)"))
    add(S(["forward", "--why", "урок записан"]))
    add(S(["next"]))
    add(S(["projects"], label="projects: a phase with no required traces"))
    add(S(["forward", "--why", "направление верное"]))
    add(S(["next"]))
    add(S(["status"]))
    add(S(["done", "готово"], rc=1, label="done: open todos"))
    add(S(["todo", "--done", "1", "проверил"]))
    add(S(["todo", "--done", "1"]))
    add(S(["todo", "--list"]))
    add(S(["done", "готово", "--as", "bogus"], rc=1))
    add(S(["done", ""], rc=1))
    add(S(["done", "готово"], rc=1, pre=pre_junk_files, label="done: dirty git tree"))
    add(S(["done", "готово", "--dirty", "тест: без коммита"]))
    add(S(["done", "ещё раз", "--task", A_ID]))
    add(S(["next"]))
    add(S(["next", "--task", A_ID], label="next: task CLOSED"))
    add(S(["use", A_ID]))
    add(S(["context", "--task", A_ID]))
    add(S(["context", "--task", A_ID, "--json"]))
    add(S(["forward", "--task", A_ID, "--why", "x"]))
    add(S(["projects"]))
    add(S(["reopen"], rc=1))
    add(S(["reopen", A_ID], rc=1))
    add(S(["reopen", A_ID, "--why", "передумал"]))
    add(S(["reopen", A_ID, "--why", "x"]))
    add(S(["phase", "context", "--task", A_ID, "--why", "новый цикл"]))
    add(S(["status"]))
    add(S(["projects"]))

    # ── spawn · dependencies · second closing kind ─────────────────────────
    add(S(["spawn"], rc=1))
    add(S(["spawn", "Подзадача: редактор аккордов", "--id", "chords-editor", "--why",
           "всплыло на думании"]))
    add(S(["spawn", "Зависимая задача", "--id", "dependent-one", "--depends-on",
           "chords-editor"]))
    add(S(["use", A_ID], label="use: A current again, clear of the spawn's millisecond"))
    add(S(["projects"], pre=pre_age_journals, label="projects: «вчера» and «дн. назад»"))
    add(S(["left", "--task", "chords-editor"]))
    # closing from an early phase is legal — and now says WHY (owner, 2026-08-23)
    add(S(["done", "понято", "--as", "closed", "--task", "chords-editor", "--dirty", "тест"],
          rc=1, label="done from an early phase: the reason is owed"))
    add(S(["done", "понято", "--as", "closed", "--task", "chords-editor",
           "--why", "владелец сказал: дальше не идём, вопрос снят", "--dirty",
           "тест"]))
    add(S(["projects"]))
    add(S(["ui"]))
    add(S(["blueprint"], label="blueprint: the big picture"))
    add(S(["blueprint", "context"], label="blueprint: one phase"))
    add(S(["blueprint", "4"], label="blueprint: phase by number"))
    add(S(["blueprint", "init"]))
    add(S(["blueprint", "rules"]))
    add(S(["blueprint", "modes"]))
    add(S(["blueprint", "files"]))
    add(S(["blueprint", "full"], label="blueprint: everything, one stream"))
    add(S(["blueprint", "nope"], rc=1, label="blueprint: unknown part"))
    add(S(["help"]))
    add(S(["help", "context"], label="help: one group"))
    add(S(["help", "forward"], label="help: one command"))
    add(S(["help", "nope"], rc=1, label="help: unknown topic"))
    add(S(["-h"]))
    add(S(["status", "--help"]))
    add(S(["bogus"], rc=2))
    add(S(["context", "--task", A_ID, "--section", "unknown"]))

    # ── task B: the full ladder, a full think, the plan gate ───────────────
    add(S(["use", B_ID]))
    add(S(["status"]))
    add(S(["next"]))
    for dim in ("where", "how", "what"):
        add(S(["context", "scope", dim, "--in", f"{dim}: входит", "--task", B_ID]))
    for q, a, area in (("Цель?", "делиться программой", "goal"),
                       ("Обязательно?", "имя и текст", "must"),
                       ("Успех?", "одно сообщение", "outcome"),
                       ("Нельзя?", "ломать дневник", "limits"),
                       ("Зачем?", "меньше ручной работы", "why"),
                       ("Кто?", "ведущий", "who"),
                       ("Когда срабатывает?", "в четверг", "when"),
                       ("Как проверишь?", "увижу список в чате", "check"),
                       ("Достаточно?", "достаточно", "goal")):
        add(S(["context", "qa", q, a, "--area", area, "--task", B_ID]))
    add(S(["next", "--task", B_ID], label="next: scope step, every area covered"))
    for dim in ("why", "who", "when"):
        add(S(["context", "scope", dim, "--in", f"{dim}: входит", "--out",
               f"{dim}: не входит", "--task", B_ID]))
    add(S(["context", "requirements", "требования B", "--task", B_ID]))
    add(S(["context", "beyond", "за рамкой B", "--task", B_ID]))
    add(S(["context", "success", "успех B", "--task", B_ID]))
    add(S(["context", "metrics", "метрик нет, качество субъективное", "--task", B_ID]))
    add(S(["context", "checklist", "- пункт приёмки B", "--task", B_ID]))
    add(S(["context", "ifr", "идеал B", "--task", B_ID]))
    add(S(["context", "clarified", "задача B", "--task", B_ID]))
    add(S(["context", "summary", "свёртка B", "--task", B_ID]))
    add(S(["context", "unknown", "незнание B", "--task", B_ID]))
    add(S(["research", "docs", "документация читана", "--ref", "README:1",
           "--task", B_ID]))
    add(S(["validate", "--task", B_ID], label="validate: the checklist alone makes a ledger"))
    add(S(["sync", "--task", B_ID]))
    add(S(["next", "--task", B_ID]))
    add(S(["accept", "да", "--task", B_ID]))
    add(S(["next", "--task", B_ID]))
    add(S(["forward", "--why", "контекст B собран", "--task", B_ID]))
    add(S(["next"], pre=pre_think_files_B, label="next: think ladder written by hand"))
    add(S(["think", "skip", "baseline", "--why", "x"], rc=1,
          label="think skip: step already written"))
    add(S(["think", "crystal"], label="think crystal: print (written by hand)"))
    add(S(["think", "crystal", "первая мысль: два пути — intent или буфер"]))
    add(S(["think", "crystal", "после g1 остаёмся на intent", "--ref", "g1"]))
    add(S(["think", "crystal"], label="think crystal: the chain"))
    add(S(["think", "mirror", "один человек, телефон"]))
    add(S(["think", "reversibility", "всё откатывается", "--ref", "research/docs.md"]))
    add(S(["think", "undo"], label="think undo: alias prints reversibility"))
    add(S(["think", "form"], label="think form: print"))
    add(S(["think", "nosuchstep", "x"], rc=2))
    add(S(["context", "outcomes", "поздний след: что появится", "--task", B_ID],
          label="late trace: a missing doc of a passed phase, no --why needed"))
    add(S(["next"], label="next: late trace pending his word"))
    add(S(["context", "clarified", "сдвиг: только текст"], rc=1,
          label="amend: --why missing"))
    add(S(["context", "clarified", "сдвиг: только текст", "--adds", "--why", "intent без вложений",
           "--ref", "g1"], label="amend п1 clarified at think"))
    add(S(["context", "requirements", "x", "--replace", "--why", "y"], rc=1,
          label="amend: --replace refused"))
    add(S(["context", "scope", "what", "--drop", "нет такой", "--why", "x"], rc=1,
          label="amend: --drop misses"))
    add(S(["context", "scope", "what", "--drop", "what: входит", "--out",
           "what: только текст", "--why", "граница сдвинулась", "--ref", "g1"],
          label="amend п1 scope: drop + out"))
    add(S(["context", "scope", "why", "--out", "не ради денег", "--why", "уточнение",
           "--ref", "research/docs.md"], label="amend п2 scope"))
    add(S(["context", "scope"]))
    add(S(["context", "beyond", "ещё за рамкой", "--adds", "--why", "нашли на думании"],
          label="amend п1 beyond"))
    add(S(["context"], label="context: amendments counted and shown"))
    add(S(["next"], label="next: amendments without his word"))
    add(S(["left"]))
    add(S(["forward", "--why", "x"], rc=1, label="forward: amendments without his word"))
    add(S(["accept", "да, с поправками"], label="accept covers the amendments"))
    add(S(["next"]))
    add(S(["think", "fork", "g1", "вопрос B", "--who", "agent", "--decide",
           "основа · что заимствовать"], pre=pre_preview_B, label="fork g1 with --decide"))
    add(S(["think", "fork", "g1", "--preview", os.path.join(ws["home"], "preview-g1.html")],
          label="fork g1 --preview: copied into thinking/previews/"))
    add(S(["think", "fork", "g1", "--preview", os.path.join(ws["home"], "nope.html")], rc=1))
    add(S(["think", "fork", "g1", "--option", "один", "--cost", "цена один", "--model",
           "модель один", "--falsifier", "не различает строки"]))
    add(S(["think", "fork", "g1", "--option", "два", "--cost", "цена два", "--recommend"]))
    add(S(["think", "fork", "g1", "--option", "три", "--cost", "цена три"]))
    add(S(["think", "fork", "g1", "--recommendation", "два как основа, контроль — один"]))
    add(S(["think", "fork", "g1", "вопрос B снова"], label="fork g1: exists, nothing to add"))
    add(S(["think", "forks"], label="think forks: the dossier fields"))
    add(S(["think", "decide", "g1", "два", "--why", "x", "--fidelity", "pixel"], rc=1,
          label="decide --fidelity: unknown level"))
    add(S(["think", "decide", "g1", "два", "--why", "потому что", "--fixed",
           "основа — два; один остаётся контролем", "--fidelity", "visual"]))
    add(S(["think", "forks"]))
    add(S(["think", "options"], rc=2, label="think options: no such command (the file is written by fork)"))
    add(S(["next"]))
    add(S(["forward", "--why", "думание B закрыто"]))
    add(S(["next"], label="next: plan (B)"))
    add(S(["forward", "--why", "x"], rc=1, label="forward: plan has no nodes (B)"))
    add(S(["plan"], pre=pre_plan_md_B, label="plan: plan.md but no nodes (B)"))
    add(S(["plan", "new", "s1", "узел без полей"]))
    add(S(["plan", "set", "s1", "result", "строка раз\\nстрока два"],
          label="plan set: a literal backslash-n becomes a newline"))
    add(S(["plan", "s1"], label="plan s1: the result shows two lines"))
    add(S(["plan", "done", "s1", "x"], rc=1, label="plan done: hollow node"))
    add(S(["plan", "start", "s1"], rc=1, label="plan start: contract has gaps"))
    add(S(["plan", "start", "s1", "--force"], label="plan start --force: active"))
    add(S(["plan", "start"], rc=1))
    add(S(["plan", "start", "s9"], rc=1))
    add(S(["plan", "new", "s2", "второй"]))
    add(S(["plan", "start", "s2", "--force"], label="plan start s2: s1 steps back to open"))
    add(S(["plan"], label="plan: statuses in the tree"))
    add(S(["plan", "wait", "s2", "показал экран"], label="plan wait: the baton goes to the owner"))
    add(S(["next"], label="next: baton with the owner"))
    add(S(["left"]))
    add(S(["plan", "start", "s1", "--force"], label="plan start while s2 waits: allowed, s2 keeps the baton"))
    add(S(["accept", "ок, смотрел", "--for", "node:s2"], label="accept --for node: baton back, s1 busy → s2 open"))
    add(S(["plan", "s2"], label="plan s2: open again, word noted"))
    add(S(["plan", "block", "s2"], rc=1, label="plan block: --why required"))
    add(S(["plan", "block", "s2", "--why", "нет доступа"]))
    add(S(["plan", "start", "s2", "--force"], label="plan start: from blocked"))
    add(S(["plan", "wait", "s2", "показал ещё раз"]))
    add(S(["accept", "принимаю этот узел", "--for", "node:s2", "--close"], rc=1,
          label="accept --close: the node still has gaps"))
    add(S(["plan", "park", "s2", "--why", "не в этой итерации"]))
    add(S(["plan", "park", "s1", "--why", "тоже позже"]))
    add(S(["doctor"], label="doctor: nothing in work, parked nodes"))
    add(S(["ack", "context/expected-outcomes.md"], rc=1, label="ack: --why required"))
    add(S(["ack", "thinking/tools.md", "--why", "приёмы здесь не нужны"]))
    add(S(["next"]))
    add(S(["todo", "--done", "1", "--task", B_ID], rc=1))
    add(S(["sync"]))
    add(S(["plan", "set", "s1", "sync", "показываю: x · увидишь: y · потрогать: z · "
           "от тебя: решение"], label="plan set sync: the four parts on ONE line"))
    add(S(["sync"], label="sync: how a one-line stop is classified"))
    add(S(["plan"]))
    add(S(["left"]))
    add(S(["where"]))
    add(S(["forward", "--why", "x"], rc=1, label="forward: plan without acceptance (B)"))
    add(S(["forward", "--waive", "x"], rc=1, label="forward --waive: plan still has holes"))
    add(S(["think", "shoals", "новая мель: лимит intent", "--adds", "--why", "нашли на плане",
           "--ref", "s1"], label="amend п1 shoals at plan"))
    add(S(["think", "shoals"]))
    add(S(["next"]))
    add(S(["left"]))
    add(S(["where"]))

    # ── other roots: ELEPHANT_DIR, ambiguity, custom --dir ─────────────────
    add(S(["status"], cwd="N", pre=pre_neutral, label="status in a neutral folder"))
    add(S(["status"], cwd="N", env={"ELEPHANT_DIR": os.path.join(ws["A"], ".projects")},
          label="status with ELEPHANT_DIR"))
    add(S(["projects"], cwd="N", env={"ELEPHANT_DIR": os.path.join(ws["A"], ".projects")}))
    add(S(["status"], cwd="C", pre=pre_ambiguous, label="status: two marked folders"))
    add(S(["init"], cwd="C"))
    add(S(["status"], cwd="C"))
    add(S(["init", "--dir", "custom/store"], cwd="D"))
    add(S(["status"], cwd="D", label="status: storage two levels down is not found"))
    add(S(["init", "--dir", "store2"], cwd="D"))
    add(S(["status"], cwd="D"))
    add(S(["boot", "задача D", "--id", "task-d"], cwd="D"))
    add(S([], cwd="D", label="el (bare) in D"))
    add(S(["projects"], cwd="D", pre=pre_age_task_d, label="projects: a task touched ten days ago"))
    add(S(["mode"], cwd="D", label="mode: show (soft by default)"))
    add(S(["mode", "bogus"], cwd="D", rc=1))
    add(S(["blueprint", "--mode", "bogus"], cwd="D", rc=1))
    add(S(["mode", "light", "--why", "простая задача"], cwd="D"))
    add(S(["mode", "light"], cwd="D", label="mode: already light"))
    add(S(["status"], cwd="D", label="status: mode line"))
    add(S(["blueprint"], cwd="D", label="blueprint for the task's mode (light)"))
    add(S(["blueprint", "--mode", "strict"], cwd="D"))
    add(S(["next"], cwd="D", label="next: light context ladder"))
    add(S(["context", "qa", "что нужно?", "кнопка", "--area", "goal"], cwd="D"))
    add(S(["context", "clarified", "задача D: кнопка"], cwd="D"))
    add(S(["accept", "да"], cwd="D"))
    add(S(["forward", "--why", "light: вопросы, задача, слово"], cwd="D",
          label="forward from context in light: spine only"))
    add(S(["next"], cwd="D", label="next: think in light — nothing required"))
    add(S(["forward", "--why", "light: думать нечего"], cwd="D"))
    add(S(["plan", "new", "s1", "сделать кнопку"], cwd="D"))
    add(S(["plan", "set", "s1", "result", "кнопка есть"], cwd="D"))
    add(S(["plan", "set", "s1", "check", "кнопка нажимается"], cwd="D"))
    add(S(["plan", "start", "s1"], cwd="D", label="plan start in light: result+check is the contract"))
    add(S(["plan", "done", "s1", "кнопка стоит"], cwd="D", rc=1,
          label="light: even here a node does not close over an unanswered criterion"))
    add(S(["validate", "s1", "1", "--met", "нажал — работает"], cwd="D"))
    add(S(["plan", "done", "s1", "кнопка стоит"], cwd="D"))
    add(S(["accept", "план ок", "--for", "plan"], cwd="D"))
    add(S(["forward", "--why", "light: план принят"], cwd="D", label="forward from plan in light: no plan.md needed"))
    add(S(["next"], cwd="D", label="next: execute in light, all nodes done"))
    add(S(["forward", "--why", "light: узел закрыт"], cwd="D", label="forward from execute in light: no artifacts needed"))
    add(S(["validate"], cwd="D", label="validate in light: one node, one criterion, the task on top"))
    add(S(["accept", "принимаю", "--for", "final"], cwd="D"))
    add(S(["forward", "--why", "light: принято"], cwd="D"))
    add(S(["mode", "strict", "--why", "усложнилось"], cwd="D"))
    add(S(["forward", "--waive", "x"], cwd="D", rc=1, label="strict: --waive refused"))
    add(S(["blueprint"], cwd="D", label="blueprint: strict"))
    add(S(["doctor"], cwd="D"))

    # ── the hand: a hold event, not the freshest journal · idle after close ────────
    # (owner, 2026-08-22; an agent's review the same day). Writes elsewhere do not move
    # the hand; closing the task in hand leaves the hand EMPTY; a closed task cannot be
    # taken; reopening takes it back.
    add(S(["status"], label="hand: before"))
    add(S(["beat", "sync", "--task", A_ID], label="beat --task: a beat elsewhere, hand stays"))
    add(S(["beat", "x", "--task", "nope"], rc=1, label="beat --task: unknown task"))
    add(S(["log", "заметка в чужую задачу", "--task", B_ID], label="log --task: hand stays"))
    add(S(["log", "x", "--task", "nope"], rc=1, label="log --task: unknown task"))
    add(S(["done", "x", "--task", "nope"], rc=1, label="done --task: unknown task is refused, not the held one"))
    add(S(["status"], label="hand: unchanged after writes elsewhere"))
    add(S(["done", "закрыта для проверки idle", "--as", "closed", "--dirty", "тест",
           "--why", "проверяем idle — задача закрывается его словом"],
          label="done: the task in hand is put down"))
    add(S([], label="el (bare): idle"))
    add(S(["status"], label="status: idle"))
    add(S(["next"], label="next: idle — take a task"))
    add(S(["where"], label="where: idle"))
    add(S(["projects"], label="projects: idle"))
    add(S(["log", "x"], rc=1, label="log: idle, nothing to write into"))
    add(S(["plan"], rc=1, label="plan: idle"))
    add(S(["context", "--line"], label="ctx --line: idle"))
    add(S(["use", "dependent-one"], label="use: take one"))
    add(S(["use", "dependent-one"], label="use: already in hand"))
    add(S(["status"], label="status: in hand again"))
    add(S(["done", "закрыта", "--as", "closed"], cwd="D", label="done in D: the only task put down"))
    add(S(["status"], cwd="D", label="status in D: every task closed"))
    add(S(["next"], cwd="D", label="next in D: every task closed"))
    add(S(["use", "task-d"], cwd="D", label="use: a closed task cannot be taken"))
    add(S(["reopen", "task-d", "--why", "проверка руки"], cwd="D", label="reopen: back in hand"))
    add(S(["status"], cwd="D"))

    # ── the tool's own inbox: el feedback ─────────────────────────────────────────
    add(S(["feedback"], label="feedback: empty pool"))
    add(S(["feedback", "el beat без --task — ловится наощупь", "--about", "el beat"]))
    add(S(["feedback", "слова человека про инструмент", "--from", "user", "--by", "тест"]))
    add(S(["feedback", "--file", os.path.join(ws["home"], "letter.md")], pre=pre_letter,
          label="feedback --file: a long letter"))
    add(S(["feedback", "--file", os.path.join(ws["home"], "nope.md")], rc=1))
    add(S(["feedback", "x", "--from", "bogus"], rc=1))
    add(S(["feedback"], label="feedback: the pool"))
    add(S(["feedback", "001"], label="feedback <id>: one in full"))
    add(S(["feedback", "done"], rc=1))
    add(S(["feedback", "done", "nope"], rc=1))
    add(S(["feedback", "done", "001"]))
    add(S(["feedback"], label="feedback: after one removed"))
    add(S(["feedback", "ещё один после удаления"], label="feedback: numbered past the highest"))
    add(S([], label="el (bare): the pool is counted"))

    # ── autonomy: a credit of the word · the sheet · search hygiene (owner, 2026-08-22) ──
    # On a fresh task in A: no grant → borrowing refused; grant → borrowed answer, borrowed
    # word over the picture, borrowed fork, the ledger, the sheet, the pulse, the halt, the
    # owner's word paying the debt, «продолжай».
    add(S(["spawn", "ужать модель на 2 ГБ без потери качества", "--id", "shrink-model",
           "--raw", "ужми модель на 2 ГБ, работай сам"], label="autonomy: the task is born"))
    add(S(["use", "shrink-model"]))
    add(S(["mode", "light", "--why", "поисковая задача — узлы result + check"]))
    add(S(["grant"], label="grant: none yet"))
    add(S(["accept", "да", "--assumed", "почему"], rc=1, label="assumed: no grant"))
    add(S(["context", "qa", "Что значит без потери?", "acc не хуже 1%", "--area", "goal",
           "--assumed", "самое узкое"], rc=1, label="qa --assumed: no grant"))
    add(S(["halt", "x"], rc=1, label="halt: no grant"))
    add(S(["grant", "работай сам, без меня", "--no", "push, деньги", "--until", "приёмка"]))
    add(S(["grant"], label="grant: the state"))
    add(S(["status"], label="status: autonomy line"))
    add(S(["context", "qa", "Что значит без потери?", "acc на eval-v1 не хуже 1%", "--area", "goal",
           "--assumed", "самое узкое из его слов"], label="qa --assumed: a borrowed answer"))
    add(S(["accept", "x", "--assumed", "y", "--for", "final"], rc=1, label="final is never borrowed"))
    add(S(["accept", "картина принята за его да", "--assumed", "человека нет, грант есть"],
          label="accept --assumed: the word over the picture, borrowed"))
    add(S(["review"], label="review: two debts"))
    add(S(["debt"], label="debt: alias"))
    add(S(["next"], label="next: autonomy block, borrowed hints"))
    add(S(["brief"], label="brief: none"))
    add(S(["brief", "x\n" * 25], rc=1, label="brief: over the line limit"))
    add(S(["brief", "baseline: 8.0 ГБ / 0.930 — S1\nзамер: make eval\nлучшее: —\nсейчас: стенд"]))
    add(S(["brief"], label="brief: printed"))
    add(S([], label="el (bare): autonomy + brief first"))
    add(S(["status"], label="status: brief + pulse (first look)"))
    add(S(["status"], label="status: pulse — no new trace"))
    add(S(["think", "fork", "g1", "с чего начать?", "--who", "owner", "--decide", "семейство"]))
    add(S(["think", "fork", "g1", "--option", "int8", "--cost", "дёшево"]))
    add(S(["think", "fork", "g1", "--option", "прунинг", "--cost", "дольше"]))
    add(S(["think", "fork", "g1", "--option", "дистилляция", "--cost", "дорого"]))
    add(S(["think", "decide", "g1", "int8", "--assumed", "обратимо"], rc=1, label="decide --assumed: needs --undo"))
    add(S(["think", "decide", "g1", "int8", "--assumed", "обратимо и дёшево", "--undo", "вернуть fp16"],
          label="decide --assumed: a borrowed fork"))
    add(S(["plan", "new", "s1", "стенд замера"]))
    add(S(["plan", "new", "s2", "стенд замера"], rc=1, label="plan new: a repeated name is refused"))
    add(S(["plan", "new", "s2", "стенд замера", "--force"], label="plan new: --force"))
    add(S(["plan", "set", "s1", "result", "baseline записан"]))
    add(S(["plan", "set", "s1", "check", "- замер воспроизводим"]))
    add(S(["plan", "done", "s1"], rc=1, label="plan done: no result under autonomy"))
    add(S(["validate", "s1", "1", "--met", "два прогона подряд дали одно число"]))
    add(S(["plan", "done", "s1", "baseline 8.0 ГБ / 0.930"]))
    add(S(["plan", "set", "s2", "result", "x"])); add(S(["plan", "set", "s2", "check", "- y"]))
    add(S(["plan", "park", "s2", "--why", "гипотеза отложена — семейство исчерпано"],
          label="park: the criteria are NOT written off automatically"))
    add(S(["plan", "start", "s2", "--force"], label="park → back into work"))
    add(S(["validate", "s2", "1", "--met", "замер сошёлся"]))
    add(S(["plan", "done", "s2", "z"]))
    add(S(["done", "готово", "--dirty", "тест"], rc=1, label="done: completed refused — debt"))
    add(S(["halt", "готово, жду приёмки: показать модель"]))
    add(S(["halt", "ещё раз"], label="halt: already"))
    add(S(["accept", "x", "--assumed", "y"], rc=1, label="assumed after halt: refused"))
    add(S(["status"], label="status: halted first"))
    add(S(["next"], label="next: halted"))
    add(S(["accept", "да, картина верна", "--for", "context"], label="his word pays the context loans"))
    add(S(["review"], label="review: paid"))
    add(S(["grant", "продолжай"], label="grant: «продолжай» lifts the halt"))
    add(S(["status"]))
    add(S(["blueprint", "autonomy"]))
    add(S(["blueprint", "search"]))
    add(S(["blueprint", "поиск"], label="blueprint: alias"))
    add(S(["help", "grant"])); add(S(["help", "brief"])); add(S(["help", "halt"])); add(S(["help", "review"]))
    # ── the owner's debt (owner, 2026-08-24): an answer only he can bring and has not ──
    # Born on any phase; not a brake by itself — holds only what it is tied to; a node
    # blocked on it is refused to start and let go by the answer; completed is refused.
    add(S(["owe"], label="owe: none yet"))
    add(S(["owe", "Кто принимает модель?"], rc=1, label="owe: --how is required"))
    add(S(["owe", "Кто принимает модель?", "--how", "спросить у Пети", "--area", "who",
           "--by", "2026-01-01"], label="owe #1: overdue, holds nothing"))
    add(S(["owe", "int8 или прунинг — что предпочтёт?", "--how", "подумать", "--kind", "решить",
           "--holds", "phase:context"], label="owe #2: holds the phase gate"))
    add(S(["owe", "x", "--how", "y", "--kind", "bogus"], rc=1, label="owe: bad kind"))
    add(S(["owe", "x", "--how", "y", "--holds", "junk"], rc=1, label="owe: bad hold"))
    add(S(["owe", "9", "--holds", "node:s1"], rc=1, label="owe: no such debt"))
    add(S(["owe", "1"], label="owe 1: one debt"))
    add(S(["log", "x", "--type", "owe"], rc=1, label="log: owe is reserved"))
    add(S(["forward", "--why", "x"], rc=1, label="forward: held by owe #2"))
    add(S(["plan", "new", "s3", "приёмка модели"]))
    add(S(["plan", "set", "s3", "result", "модель принята"])); add(S(["plan", "set", "s3", "check", "- принято"]))
    add(S(["plan", "block", "s3", "--owe", "9"], rc=1, label="plan block --owe: no such debt"))
    add(S(["plan", "block", "s3", "--owe", "2"], label="plan block --owe: the node stands on #2"))
    add(S(["plan", "start", "s3"], rc=1, label="plan start: held by the owner's debt"))
    add(S(["owe"], label="owe: ledger — standing, overdue"))
    add(S(["status"], label="status: ЗА ВЛАДЕЛЬЦЕМ first"))
    add(S(["next"], label="next: ЗА ВЛАДЕЛЬЦЕМ under autonomy"))
    add(S(["left"], label="left: the debt first"))
    add(S(["done", "готово", "--dirty", "тест"], rc=1, label="done: completed refused — owed"))
    add(S(["owe", "answer", "2"], rc=1, label="owe answer: words required"))
    add(S(["owe", "answer", "2", "int8, обратимо"], label="owe answer #2: node s3 let go, gate free"))
    add(S(["owe", "answer", "2", "ещё раз"], rc=1, label="owe answer: already paid"))
    add(S(["plan", "start", "s3"], label="plan start s3: free now"))
    add(S(["owe", "drop", "1"], rc=1, label="owe drop: --why required"))
    add(S(["owe", "drop", "1", "--why", "нашли в переписке"], label="owe drop #1"))
    add(S(["owe"], label="owe: all closed"))
    add(S(["help", "owe"]))
    # ids: the date prefix does not eat the five-word cap; a cut is said out loud
    add(S(["spawn", "скорость после ансамбля", "--id", "2026-01-01-speed-after-ensemble-test"],
          label="spawn: a dated id keeps its words"))
    add(S(["spawn", "шесть слов", "--id", "one-two-three-four-five-six"], label="spawn: the cut is announced"))
    # the same task again: refused with the twin named; --force; a repeated request is appended
    add(S(["new", "ужать модель на 2 ГБ без потери качества", "--id", "shrink-twin"], rc=1,
          label="new: a twin of an open task is refused"))
    add(S(["new", "ужать модель на 2 ГБ без потери качества", "--id", "shrink-twin", "--force"],
          label="new: --force opens it anyway"))
    add(S(["new", "починить парсер логов сервера", "--id", "fix-log-parser"], label="new: unrelated, no note"))
    add(S(["boot", "x", "--id", "shrink-model", "--raw", "ещё раз: ужми модель на два гига"],
          label="boot --raw on an existing task: the request repeated, appended"))
    add(S(["projects"], label="projects: requests in his words under each task"))
    add(S(["progress"], label="progress: the main files of every phase, whole"))
    add(S(["progress", "think"], label="progress think: one phase"))
    add(S(["progress", "план"], label="progress: a Russian alias"))
    add(S(["progress", "nope"], rc=1))
    add(S(["story", "--task", A_ID], label="story: alias, another task"))
    add(S(["help", "how"], label="help how: the mechanics, its own screen"))
    add(S(["help"], label="help: the map alone, under the budget"))
    return steps


def fixture_steps(ws):
    """Read-and-write commands on a COPY of a real storage — every task in it."""
    root = os.path.join(ws["R"], ".projects")
    tasks = sorted(n for n in os.listdir(root)
                   if re.match(r"^\d{4}-\d{2}-\d{2}[-_]", n)
                   and os.path.isdir(os.path.join(root, n)))
    S = lambda argv, rc=0, label=None: _step(argv, rc=rc, cwd="R", label=label)
    steps = [S([], label="el (bare) on the fixture"), S(["status"]), S(["projects"]),
             S(["next"]), S(["left"]), S(["where"]), S(["context"]), S(["context", "--json"]),
             S(["context", "--line"]), S(["context", "scope"]), S(["context", "areas"]),
             S(["context", "qa", "--list"]), S(["think"]), S(["think", "tools"]),
             S(["plan"]), S(["sync"]), S(["todo", "--list"]), S(["ui"])]
    for t in tasks:
        steps += [S(["context", "--task", t]), S(["context", "--task", t, "--json"]),
                  S(["next", "--task", t]), S(["left", "--task", t]),
                  S(["plan", "--task", t]), S(["sync", "--task", t]),
                  S(["think", "--task", t]), S(["context", "scope", "--task", t]),
                  S(["context", "areas", "--task", t]),
                  S(["validate", "--task", t], rc=None)]
        for sec in ("ifr", "summary", "требован", "думание"):
            steps.append(S(["context", "--task", t, "--section", sec], rc=None))
    steps += [S(["log", "проба дифф-теста", "--type", "note"]),
              S(["todo", "проба отложенного", "--when", "validate"]),
              S(["plan"]), S(["next"]), S(["status"]), S(["ui"])]
    return steps


# ── normalisation: a timestamp is not a behaviour ────────────────────────────

_PATTERNS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}"), "<TS>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?"), "<TSM>"),
    (re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"), "<DT>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}"), "<DATE>"),
    (re.compile(r"(сегодня|вчера) \d{2}:\d{2}"), r"\1 <HM>"),
    (re.compile(r'"_mtime": [0-9.]+'), '"_mtime": <F>'),
]


def normalise(text, repl):
    for real, token in repl:
        text = text.replace(real, token)
    for pat, sub in _PATTERNS:
        text = pat.sub(sub, text)
    return text


def snapshot_tree(top, repl):
    """Every file under `top` (sorted), with its content — or a hash for binaries."""
    out = []
    for base, dirs, files in os.walk(top):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for f in sorted(files):
            p = os.path.join(base, f)
            rel = os.path.relpath(p, top).replace(os.sep, "/")
            try:
                data = open(p, "rb").read()
            except OSError as e:
                out.append(f"### {rel}\n<unreadable: {e}>\n")
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                out.append(f"### {rel}\nsha256:{hashlib.sha256(data).hexdigest()} "
                           f"({len(data)} bytes)\n")
                continue
            out.append(f"### {rel}\n{text}\n")
    return normalise("".join(out), repl)


# ── the runner ───────────────────────────────────────────────────────────────

def run(args):
    bin_path = os.path.realpath(args.bin)
    work = os.path.realpath(args.work or tempfile.mkdtemp(prefix="el-scenario-"))
    # F — the tool's inbox (feedback/), redirected out of the skill for the whole run.
    ws = {k: os.path.join(work, k) for k in ("A", "N", "C", "D", "F", "home")}
    tpl = os.path.join(os.path.dirname(os.path.dirname(bin_path)), "html", "overview.html")
    if not os.path.isfile(tpl):
        print(f"!! no page templates next to the binary: {tpl}\n"
              "   export the WHOLE skill (git archive HEAD elephant), not cli/ alone — "
              "otherwise tree.txt fills with false diff", file=sys.stderr)
    ws["A/sub"] = os.path.join(ws["A"], "sub", "dir")
    for p in ws.values():
        os.makedirs(p, exist_ok=True)
    steps = scenario(ws)
    if args.fixture:
        fx = os.path.realpath(args.fixture)
        ws["R"] = os.path.join(work, "R")
        os.makedirs(ws["R"], exist_ok=True)
        shutil.copytree(fx, os.path.join(ws["R"], ".projects"), symlinks=True)
        _write(os.path.join(ws["R"], "CLAUDE.md"), "# fixture host\n")
        os.makedirs(os.path.join(ws["R"], ".git"), exist_ok=True)
        steps += fixture_steps(ws)

    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": ws["home"],
           "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "PYTHONIOENCODING": "utf-8",
           "TZ": os.environ.get("TZ", "America/Los_Angeles"), "PYTHONDONTWRITEBYTECODE": "1",
           "ELEPHANT_FEEDBACK_DIR": ws["F"]}
    repl = [(work, "<WS>"), (bin_path, "<EL>"), (SKILL, "<SKILL>")]
    repl.sort(key=lambda kv: -len(kv[0]))

    trace_file = os.path.join(work, "trace.counts")
    prefix = [sys.executable]
    if args.trace:
        # --coverdir on EVERY call: trace writes .cover files after each run, and without a
        # coverdir it drops them next to the sources — inside the skill tree.
        prefix += ["-m", "trace", "--count", "--file", trace_file,
                   "--coverdir", os.path.join(work, "cover-tmp"),
                   "--ignore-dir", sys.prefix, "--ignore-dir", sys.exec_prefix]

    os.makedirs(args.out, exist_ok=True)
    lines, raw_lines, summary = [], [], []
    mismatches = 0
    for i, st in enumerate(steps, 1):
        if st["pre"]:
            st["pre"](ws)
        cwd = ws[st["cwd"]]
        e = dict(env)
        e.update(st["env"])
        proc = subprocess.run(prefix + [bin_path] + st["argv"], cwd=cwd, env=e,
                              capture_output=True, text=True, errors="replace")
        ok = st["rc"] is None or args.trace or proc.returncode == st["rc"]
        if not ok:
            mismatches += 1
        summary.append({"n": i, "label": st["label"], "argv": st["argv"], "cwd": st["cwd"],
                        "rc": proc.returncode, "expected": st["rc"], "ok": ok})
        block = (f"=== {i:03d} [{st['cwd']}] el {' '.join(st['argv'])}\n"
                 f"--- label: {st['label']}\n--- rc: {proc.returncode}\n"
                 f"--- stdout:\n{proc.stdout}--- stderr:\n{proc.stderr}")
        raw_lines.append(block)
        lines.append(normalise(block, repl))
        if proc.returncode < 0 or "Traceback (most recent call last)" in proc.stderr:
            print(f"!! step {i:03d} crashed: el {' '.join(st['argv'])}\n{proc.stderr}",
                  file=sys.stderr)

    with open(os.path.join(args.out, "steps.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    with open(os.path.join(args.out, "steps.raw.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(raw_lines))
    tree = "".join(f"##### {k}\n{snapshot_tree(ws[k], repl)}" for k in sorted(ws)
                   if k not in ("A/sub", "home"))
    with open(os.path.join(args.out, "tree.txt"), "w", encoding="utf-8") as fh:
        fh.write(tree)
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"bin": bin_path, "steps": len(steps), "rc_mismatches": mismatches,
                   "results": summary}, fh, ensure_ascii=False, indent=1)

    if args.trace:
        cov = os.path.join(args.out, "coverage")
        os.makedirs(cov, exist_ok=True)
        rep = subprocess.run([sys.executable, "-m", "trace", "--report", "--file", trace_file,
                              "--coverdir", cov, "--missing", "--summary"],
                             capture_output=True, text=True)
        with open(os.path.join(cov, "summary.txt"), "w", encoding="utf-8") as fh:
            fh.write(rep.stdout + rep.stderr)

    print(f"steps {len(steps)} · rc mismatches {mismatches} · snapshot → {args.out}")
    for s in summary:
        if not s["ok"]:
            print(f"  rc mismatch {s['n']:03d}: got {s['rc']}, expected {s['expected']} — "
                  f"el {' '.join(s['argv'])}")
    if args.keep:
        print(f"workspace kept: {work}")
    elif not args.work:
        shutil.rmtree(work, ignore_errors=True)
    return 0


def diff(args):
    rc = 0
    for name in ("steps.txt", "tree.txt"):
        a = open(os.path.join(args.a, name), encoding="utf-8").read().splitlines()
        b = open(os.path.join(args.b, name), encoding="utf-8").read().splitlines()
        d = list(difflib.unified_diff(a, b, fromfile=f"{args.a}/{name}",
                                      tofile=f"{args.b}/{name}", lineterm="", n=2))
        if d:
            rc = 1
            print("\n".join(d[:args.max_lines]))
            if len(d) > args.max_lines:
                print(f"... {len(d) - args.max_lines} more diff lines")
        print(f"{name}: {'IDENTICAL' if not d else str(len(d)) + ' diff lines'} "
              f"({len(a)} vs {len(b)} lines)")
    return rc


def main():
    ap = argparse.ArgumentParser(prog="scenario.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--bin", required=True, help="the el.py to test")
    r.add_argument("--out", required=True, help="where the snapshot goes")
    r.add_argument("--fixture", help="a real storage folder to copy and replay on")
    r.add_argument("--work", help="workspace folder (default: a fresh temp dir)")
    r.add_argument("--trace", action="store_true")
    r.add_argument("--keep", action="store_true")
    r.set_defaults(fn=run)
    d = sub.add_parser("diff")
    d.add_argument("a"); d.add_argument("b")
    d.add_argument("--max-lines", type=int, default=400)
    d.set_defaults(fn=diff)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
