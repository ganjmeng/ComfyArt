"""Book one retained unknown at its full reserve. Temporary ledger only.

Reproduces the captured totals: known $0.003995172, hold $0.3244032, count 3/6,
breaker open, available $1.671601628. Does not open the deployment ledger.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ComfyArt.bot import llm_scope_activation as activation
from ComfyArt.bot import llm_usd_gate as gate
from test_llm_usd_gate import _reserve_record, _usage
from test_source_migration_1004 import AUTHORITY, CAPTURED_NANO, CAPTURED_RESERVE, bound, migrate


UNKNOWN = "31a1d4f0c51f45f3a3d26cf53832add2"
UNKNOWN_DIGEST = "6747e3b20515f3fc74a59dca48f9603f5a3779448b475f81a21fd0618e69c41f"
SECOND_NANO = 352_428
KNOWN_NANO = CAPTURED_NANO + SECOND_NANO
ACCOUNTED = KNOWN_NANO + CAPTURED_RESERVE
AVAILABLE = gate.TWO_DOLLAR_CEILING_NANO - ACCOUNTED
NOTE = "book retained transport disconnect at its full reserve"


def _second_usage():
    return _usage(16101, 63, hit=15488, miss=613)["usage"]


def _post(env, rid, *, digest=UNKNOWN_DIGEST):
    record = _reserve_record(CAPTURED_RESERVE, rid)
    record["input_bound"] = 1_048_576
    record["max_output_tokens"] = 8192
    record["body_sha256"] = digest
    binding = json.loads(Path(env["old"].home, activation._REGISTRY).read_text())["authorities"][AUTHORITY]["binding"]
    gate.reserve_nano(env["path"], nano=CAPTURED_RESERVE, record=record, runtime_binding=binding)


def reproduce(env):
    _post(env, "known-first", digest="a" * 64)
    assert gate.settle(env["path"], "known-first", _usage(16054, 57, hit=4224, miss=11830)["usage"])["actual_nano"] == CAPTURED_NANO
    _post(env, "known-second", digest="b" * 64)
    assert gate.settle(env["path"], "known-second", _second_usage())["actual_nano"] == SECOND_NANO
    _post(env, UNKNOWN)
    gate.retain(env["path"], UNKNOWN, "transport:ServerDisconnectedError")


def finalize(env, **overrides):
    fields = dict(authorization_id=AUTHORITY, scope_id=env["scope_id"], request_id=UNKNOWN,
                  expected_reserve_nano=CAPTURED_RESERVE, expected_body_sha256=UNKNOWN_DIGEST, operator_note=NOTE)
    fields.update(overrides)
    return activation.finalize_unknown_as_worst_case(env["new"], **fields)


def test_worst_case_booking_then_allows_source_migration(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    before = gate.ledger_state(env["path"])
    assert before["accounted_nano"] == ACCOUNTED == 328_398_372
    assert KNOWN_NANO == 3_995_172
    assert before["ceiling_nano"] - before["accounted_nano"] == AVAILABLE == 1_671_601_628
    assert before["control_state"]["attempts_total"] == 3
    assert before["control_state"]["circuit_open"] is True
    assert before["control_state"]["first_anomaly_id"] == UNKNOWN
    assert before["inflight"] == 0
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_state_unsafe"):
        migrate(env)
    assert gate.ledger_state(env["path"]) == before
    result = finalize(env)
    state = gate.ledger_state(env["path"])
    assert result["idempotent"] is False
    assert state["accounted_nano"] == ACCOUNTED
    assert state["ceiling_nano"] - state["accounted_nano"] == AVAILABLE
    assert state["control_state"]["attempts_total"] == 3
    assert state["control_state"]["circuit_open"] is False
    assert state["control_state"]["circuit_reason"] == ""
    row = state["reservations"][UNKNOWN]
    assert row["status"] == "reconciled" and row["actual_nano"] == CAPTURED_RESERVE and row["reserved_nano"] == CAPTURED_RESERVE
    audit = json.loads(Path(env["path"]).read_text())["worst_case_finalizations"]
    assert len(audit) == 1 and audit[0]["operator_note"] == NOTE and audit[0]["runtime_id"] == env["new"].runtime_id
    assert len(audit[0]["prior_state_digest"]) == 64 and audit[0]["at"] > 0
    again = finalize(env)
    assert again["idempotent"] is True and gate.ledger_state(env["path"]) == state
    assert len(json.loads(Path(env["path"]).read_text())["worst_case_finalizations"]) == 1
    migrated = migrate(env)
    assert migrated["ok"] is True
    assert gate.ledger_state(env["path"]) == state


@pytest.mark.parametrize("change", ["request", "amount", "note_repeat", "digest"])
def test_wrong_identity_writes_nothing(tmp_path, monkeypatch, change):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    if change == "digest":
        text = Path(env["path"]).read_text()
        Path(env["path"]).write_text(text.replace(UNKNOWN_DIGEST, "c" * 64))
    before = Path(env["path"]).read_bytes()
    kwargs = {}
    if change == "request":
        kwargs["request_id"] = "0" * 32
    elif change == "amount":
        kwargs["expected_reserve_nano"] = CAPTURED_RESERVE - 1
    elif change == "note_repeat":
        finalize(env)
        before = Path(env["path"]).read_bytes()
        kwargs["operator_note"] = "different note"
    with pytest.raises(gate.LlmBudgetBlocked, match="finalize_refused"):
        finalize(env, **kwargs)
    assert Path(env["path"]).read_bytes() == before


def _plant(env, status):
    def change(data):
        data["reservations"]["still-open"] = {
            "id": "still-open", "status": status, "reserved_nano": 1200, "actual_nano": None,
            "retain_reason": "" if status == "reserved" else "other_unknown",
            "authorization": data["authorization"], "authorized_ceiling_nano": data["authorized_ceiling_nano"],
            "body_sha256": "d" * 64,
        }
        return {"ok": True}
    gate._mutate(env["path"], change, create=False)


def test_other_unknown_inflight_and_journal_are_refused(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    _plant(env, "reserved")
    before = Path(env["path"]).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="finalize_refused"):
        finalize(env)
    assert Path(env["path"]).read_bytes() == before
    _plant(env, "retained")
    retained = Path(env["path"]).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="finalize_refused"):
        finalize(env)
    assert Path(env["path"]).read_bytes() == retained
    Path(env["path"] + ".outcome_pending").write_text("{}")
    with pytest.raises(gate.LlmBudgetBlocked, match="finalize_refused"):
        finalize(env)
    assert Path(env["path"]).read_bytes() == retained


CHILD = r"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
import conftest
from ComfyArt.bot import llm_scope_activation as a, llm_usd_gate as g
payload = json.loads(sys.argv[2])
if payload.get("ready"):
    print("READY", flush=True)
if payload.get("crash_stage"):
    def fault(current):
        if current == payload["crash_stage"]:
            os._exit(93)
    g._write_fault = fault
runtime = a.runtime_identity(payload["home"], payload["runtime_id"])
try:
    result = a.finalize_unknown_as_worst_case(
        runtime, authorization_id=payload["authority"], scope_id=payload["scope_id"],
        request_id=payload["request_id"], expected_reserve_nano=payload["reserve"],
        expected_body_sha256=payload["digest"], operator_note=payload["note"])
    print(json.dumps({"ok": True, "idempotent": result["idempotent"], "state": g.ledger_state(payload["ledger"])}), flush=True)
except g.LlmBudgetBlocked as exc:
    print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}), flush=True)
"""


def _spawn(env, **extra):
    payload = dict(home=env["new"].home, runtime_id=env["new"].runtime_id, authority=AUTHORITY, scope_id=env["scope_id"],
                   ledger=env["path"], request_id=UNKNOWN, reserve=CAPTURED_RESERVE, digest=UNKNOWN_DIGEST, note=NOTE, **extra)
    return subprocess.Popen([sys.executable, "-c", CHILD, str(Path(__file__).parent), json.dumps(payload)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _finish(child, code=0):
    stdout, stderr = child.communicate(timeout=30)
    assert child.returncode == code, (stdout, stderr)
    return json.loads(stdout.strip().splitlines()[-1]) if code == 0 else None


@pytest.mark.parametrize("stage", ["finalize_pending_after_dir_fsync", "finalize_ledger_after_dir_fsync"])
def test_interrupted_finalize_resumes_without_releasing_or_double_booking(tmp_path, monkeypatch, stage):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    _finish(_spawn(env, crash_stage=stage), 93)
    result = finalize(env)
    state = gate.ledger_state(env["path"])
    assert state["accounted_nano"] == ACCOUNTED
    assert state["control_state"]["attempts_total"] == 3
    assert state["control_state"]["circuit_open"] is False
    assert state["reservations"][UNKNOWN]["actual_nano"] == CAPTURED_RESERVE
    assert len(json.loads(Path(env["path"]).read_text())["worst_case_finalizations"]) == 1
    assert not os.path.lexists(env["path"] + ".finalize_pending")
    assert result["idempotent"] is (stage == "finalize_ledger_after_dir_fsync")


def test_concurrent_finalize_books_once(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    with activation._registry_lock(env["new"].home):
        children = [_spawn(env, ready=True) for _ in range(2)]
        for child in children:
            assert child.stdout.readline().strip() == "READY"
    results = [_finish(child) for child in children]
    assert [row["ok"] for row in results] == [True, True]
    assert sum(not row["idempotent"] for row in results) == 1
    state = gate.ledger_state(env["path"])
    assert state["accounted_nano"] == ACCOUNTED and state["control_state"]["attempts_total"] == 3
    assert state["control_state"]["circuit_open"] is False
    assert len(json.loads(Path(env["path"]).read_text())["worst_case_finalizations"]) == 1
