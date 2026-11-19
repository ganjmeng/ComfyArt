"""Book one retained unknown as spent. Temporary ledger only.

Reproduces the captured totals: known $0.003995172, hold $0.3244032, count 3/6,
breaker open, available $1.671601628. The hold is already inside accounted.
Does not open the deployment ledger.
"""
import json
from pathlib import Path

import pytest

from ComfyArt.bot import llm_scope_activation as activation
from ComfyArt.bot import llm_usd_gate as gate
from test_llm_usd_gate import _reserve_record, _usage
from test_source_migration_1004 import (
    AUTHORITY, CAPTURED_NANO, CAPTURED_RESERVE, RUNTIME_ID, _candidate, _use_source, bound, migrate,
)


UNKNOWN = "31a1d4f0c51f45f3a3d26cf53832add2"
UNKNOWN_DIGEST = "6747e3b20515f3fc74a59dca48f9603f5a3779448b475f81a21fd0618e69c41f"
SECOND_NANO = 352_428
KNOWN_NANO = CAPTURED_NANO + SECOND_NANO
ACCOUNTED = KNOWN_NANO + CAPTURED_RESERVE
AVAILABLE = gate.TWO_DOLLAR_CEILING_NANO - ACCOUNTED
OPERATOR = "tech-lead"
REASON = "book retained transport disconnect as spent"
# Loaded file hash of commit 42413ac7, measured from that tree. Not a git SHA.
DEPLOYED_42413_SOURCE = "44e7fc54d1860908a33625042a15e385597c017488422bd0158263d2d4911856"


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


def resolve(env, reservation_id=UNKNOWN):
    return gate.resolve_unknown_as_spent(env["path"], reservation_id, OPERATOR, REASON)


def test_resolve_closes_breaker_and_migration_succeeds(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    before = gate.ledger_state(env["path"])
    limits = json.loads(Path(env["path"]).read_text())["control_limits"]
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
    result = resolve(env)
    state = gate.ledger_state(env["path"])
    raw = json.loads(Path(env["path"]).read_text())
    assert result["ok"] is True and result["idempotent"] is False and result["circuit_open"] is False
    assert result["actual_nano"] == CAPTURED_RESERVE and result["accounted_nano"] == ACCOUNTED
    assert result["attempts_total"] == 3
    assert state["accounted_nano"] == ACCOUNTED
    assert state["ceiling_nano"] - state["accounted_nano"] == AVAILABLE
    assert state["control_state"]["attempts_total"] == 3
    assert state["control_state"]["circuit_open"] is False
    assert state["control_state"]["circuit_reason"] == ""
    assert state["control_state"]["first_anomaly_id"] == ""
    assert state["inflight"] == 0
    assert raw["control_limits"] == limits
    assert raw["ceiling_nano"] == gate.TWO_DOLLAR_CEILING_NANO
    row = state["reservations"][UNKNOWN]
    assert row["status"] == "resolved_as_spent"
    assert row["actual_nano"] == CAPTURED_RESERVE == row["reserved_nano"]
    audit = raw["resolution_audit"]
    assert len(audit) == 1
    assert audit[0]["reservation_id"] == UNKNOWN
    assert audit[0]["operator"] == OPERATOR and audit[0]["reason"] == REASON and audit[0]["at"] > 0
    migrated = migrate(env)
    assert migrated["ok"] is True
    assert gate.ledger_state(env["path"])["accounted_nano"] == ACCOUNTED
    assert gate.ledger_state(env["path"])["control_state"]["attempts_total"] == 3
    assert gate.ledger_state(env["path"])["control_state"]["circuit_open"] is False


def test_id_mismatch_is_refused_with_no_write(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    before = Path(env["path"]).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="resolve_refused"):
        resolve(env, "0" * 32)
    assert Path(env["path"]).read_bytes() == before
    assert gate.ledger_state(env["path"])["control_state"]["circuit_open"] is True


def test_other_retained_row_is_refused_with_no_write(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)

    def plant(data):
        data["reservations"]["still-open"] = {
            "id": "still-open", "status": "retained", "reserved_nano": 1200, "actual_nano": None,
            "retain_reason": "other_unknown", "authorization": data["authorization"],
            "authorized_ceiling_nano": data["authorized_ceiling_nano"], "body_sha256": "d" * 64,
        }
        return {"ok": True}

    gate._mutate(env["path"], plant, create=False)
    before = Path(env["path"]).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="other_retained"):
        resolve(env)
    assert Path(env["path"]).read_bytes() == before


def test_retained_row_that_is_not_first_anomaly_is_refused_by_the_breaker(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)

    def plant(data):
        data["control_state"]["circuit_open"] = True
        data["control_state"]["circuit_reason"] = "transport:other"
        data["control_state"]["first_anomaly_id"] = "someone-else"
        data["reservations"]["held"] = {
            "id": "held", "status": "retained", "reserved_nano": 1200, "actual_nano": None,
            "retain_reason": "not_the_first_anomaly", "authorization": data["authorization"],
            "authorized_ceiling_nano": data["authorized_ceiling_nano"],
        }
        return {"ok": True}

    gate._mutate(env["path"], plant, create=False)
    before = Path(env["path"]).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="breaker"):
        resolve(env, "held")
    assert Path(env["path"]).read_bytes() == before
    assert gate.ledger_state(env["path"])["control_state"]["first_anomaly_id"] == "someone-else"


def test_second_call_is_idempotent_and_does_not_write(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    reproduce(env)
    first = resolve(env)
    raw = Path(env["path"]).read_bytes()
    second = resolve(env)
    assert Path(env["path"]).read_bytes() == raw
    assert second["idempotent"] is True
    assert {key: second[key] for key in second if key != "idempotent"} == {key: first[key] for key in first if key != "idempotent"}
    assert len(json.loads(raw)["resolution_audit"]) == 1


def test_second_migration_hop_from_deployed_42413_hash_after_resolve(tmp_path, monkeypatch):
    path = str((tmp_path / "scope.json").resolve())
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=6)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, DEPLOYED_42413_SOURCE)
    old = activation.runtime_identity(str((tmp_path / "home").resolve()), RUNTIME_ID)
    candidate, expected = _candidate(scope, path, old.fingerprint)
    activation.activate_scope(candidate, expected=expected, runtime=old)
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    new = activation.runtime_identity(old.home, old.runtime_id)
    env = {"path": path, "scope_id": scope["scope_id"], "old": old, "new": new}
    reproduce(env)
    resolve(env)
    new_hash = activation._source_hash()
    assert new_hash != DEPLOYED_42413_SOURCE
    before = Path(path).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_42413_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git=activation.REVIEWED_DEPLOYED_GIT, reviewed_protocol_git="0" * 40)
    assert Path(path).read_bytes() == before
    migrated = activation.migrate_source_fingerprint(
        new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_42413_SOURCE,
        scope_id=scope["scope_id"], ledger_path=path,
        reviewed_from_git=activation.REVIEWED_DEPLOYED_GIT, reviewed_protocol_git=activation.REVIEWED_RESOLVE_GIT)
    binding = json.loads(Path(old.home, activation._REGISTRY).read_text())["authorities"][AUTHORITY]["binding"]
    provenance = binding["source_migration"]
    assert migrated["ok"] is True
    assert binding["source_sha256"] == new_hash
    assert provenance["from_source_sha256"] == DEPLOYED_42413_SOURCE
    assert provenance["to_source_sha256"] == new_hash
    assert provenance["reviewed_from_git"] == "42413ac72626671a1790dbed87544f9f32ebaedf"
    assert provenance["reviewed_protocol_git"] == activation.REVIEWED_RESOLVE_GIT
    assert provenance["reviewed_from_git"] != activation.REVIEWED_FROM_GIT
    assert provenance["reviewed_protocol_git"] != activation.REVIEWED_PROTOCOL_GIT
    state = gate.ledger_state(path)
    assert state["accounted_nano"] == ACCOUNTED
    assert state["control_state"]["attempts_total"] == 3
    assert state["control_state"]["circuit_open"] is False
    assert state["reservations"][UNKNOWN]["status"] == "resolved_as_spent"
