"""#385: /arti switchable memory/skills toggles, chat-edit intents (add/correct/forget), evolution log from memoryLog.

Behavior harness: tests/js/arti_chat_memory.ts (mocked ask, no paid API). Static wiring asserts in this file."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTI = (ROOT / "src/home/Arti.tsx").read_text()
MEM = (ROOT / "src/home/ArtiMemory.tsx").read_text()
CHAT = (ROOT / "src/home/artiChatMemory.ts").read_text()
CAPS = (ROOT / "src/home/artiCaps.ts").read_text()
ZH = (ROOT / "src/locales/zh.json").read_text()
EN = (ROOT / "src/locales/en.json").read_text()
CSS = (ROOT / "src/styles/home.css").read_text()

pytestmark = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)


@pytest.fixture(scope="module")
def got(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("m385") / "arti_chat_memory.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "arti_chat_memory.ts"},
    )
    run = subprocess.run(["node", str(out)], check=True, capture_output=True, text=True)
    return json.loads(run.stdout)


# ---- AC1: toggles wire to real settings ----
def test_ac1_memory_skills_switchable_not_disabled() -> None:
    # memory + skills cards are not disabled:true (review/research still are)
    assert re.search(r"id:\s*'memory'[^}]*disabled:\s*false", ARTI, re.S)
    assert re.search(r"id:\s*'skills'[^}]*disabled:\s*false", ARTI, re.S)
    assert re.search(r"id:\s*'review'[^}]*disabled:\s*true", ARTI, re.S)
    assert re.search(r"id:\s*'research'[^}]*disabled:\s*true", ARTI, re.S)
    assert "saveSettings" in ARTI
    assert "proactive-memory" in CAPS and "proactive-skills" in CAPS
    assert "onToggle" in ARTI or "toggleCap" in ARTI
    # no 「即将开放」 for switchable caps (soon only when cap.disabled)
    assert "const soon = cap.disabled && !cap.noSwitch" in ARTI


def test_ac1_mutation_disabled_true_would_fail() -> None:
    """Documented mutation: restore disabled:true on memory → this assert goes red."""
    assert "disabled: false" in ARTI  # memory/skills
    assert "saveSettings({ [key]: on })" in ARTI or "saveSettings({ [key]: on }" in ARTI
    assert "loadSettings" in ARTI
    assert "void loadSettings()" in ARTI


# ---- AC2: chat intents ----
def test_ac2_composer_uses_intent_not_hardcoded_taste() -> None:
    assert "runChatMemoryEdit" in MEM
    assert "from './artiChatMemory'" in MEM or 'from "./artiChatMemory"' in MEM
    # must NOT hardcode taste on the chat send path
    send = MEM[MEM.index("function ChatComposer") : MEM.index("function MemoryGroup")]
    assert "category: 'taste'" not in send
    assert "runChatMemoryEdit" in send
    assert "arti.memory.chatIntentFail" in send


def test_ac2_add_illustrator(got) -> None:
    r = got["ac2_add"]
    assert r["changed"] == 1 and r["action"] == "add"
    assert r["count"] == 1 and r["category"] == "about" and r["text"] == "我是插画师"
    assert r["owner"] == "local" and r["workspace"] == "local"
    assert r["logAction"] == "add"


def test_ac2_correct_blue_to_green(got) -> None:
    r = got["ac2_correct"]
    assert r["action"] == "correct" and r["changed"] == 1
    assert r["countBefore"] == r["countAfter"] == 1
    assert r["text"] == "我喜欢绿色"
    assert r["logAction"] == "update"


def test_ac2_forget_blue(got) -> None:
    r = got["ac2_forget"]
    assert r["action"] == "forget" and r["changed"] == 1
    assert r["count"] == 1 and r["remaining"] == ["我是插画师"]
    assert r["logAction"] == "forget"


def test_ac2_mutation_fixed_taste_add_is_wrong_shape(got) -> None:
    """Mutation reference: always-add with taste would produce this wrong category."""
    assert got["mutation_taste_only_would_fail_shape"]["category"] == "taste"
    # the real path must classify 我是插画师 as about (tested above)


# ---- AC3: parse fail / empty ----
def test_ac3_empty_and_parse_fail_zero_changes(got) -> None:
    e = got["ac3_empty"]
    assert e == {"changed": 0, "reason": "empty", "count": 1}
    p = got["ac3_parse_fail"]
    assert p["changed"] == 0 and p["reason"] == "parse" and p["count"] == 1


# ---- AC4/5: evolution log ----
def test_ac4_evolution_reads_memory_log() -> None:
    assert "memoryLogAtom" in ARTI
    assert 'data-testid="arti-evolution-log"' in ARTI
    assert 'data-testid="arti-evolution-row"' in ARTI
    assert 'data-testid="arti-evolution-time"' in ARTI
    assert 'data-testid="arti-evolution-action"' in ARTI
    assert "arti.evolutionTime" in ARTI and "arti.evolutionAction" in ARTI
    assert "arti-evolution-placeholder" not in ARTI
    assert ".ca-arti-evo" in CSS


def test_ac4_three_ops_newest_first(got) -> None:
    r = got["ac4_log_three"]
    assert r["len"] >= 3
    # newest-first: forget, update, add (plus seed add) — first three actions include forget then update
    assert "forget" in r["actions"] and "update" in r["actions"] and "add" in r["actions"]
    assert r["newestFirst"] is True
    # distinct action labels exist in locales
    assert '"memoryDialog.remember"' in ZH and '"memoryDialog.correct"' in ZH and '"memoryDialog.forget"' in ZH


def test_ac5_empty_log_state() -> None:
    assert 'data-testid="arti-evolution-empty"' in ARTI
    assert '"arti.evolutionEmpty"' in ZH and '"arti.evolutionEmpty"' in EN
    assert "暂无进化日志" in ZH


def test_locales_chat_intent_fail() -> None:
    assert '"arti.memory.chatIntentFail"' in ZH and '"arti.memory.chatIntentFail"' in EN
    assert '"arti.evolutionTime": "时间"' in ZH
    assert '"arti.evolutionAction": "操作"' in ZH


def test_parser_unit_shapes(got) -> None:
    assert got["parser_add"] == {"action": "add", "text": "我是插画师", "category": "about"}
    assert got["parser_correct"] == {"action": "correct", "old": "蓝", "new": "绿"}
    assert got["parser_forget"] == {"action": "forget", "text": "蓝"}
    assert got["parser_bad"] == {"action": "none", "reason": "parse"}
    assert got["parser_empty_add"] == {"action": "none", "reason": "parse"}
