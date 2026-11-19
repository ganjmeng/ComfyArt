"""Raise one scope's POST limit without moving the $2 ceiling. Temporary ledger only."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from ComfyArt.bot import llm_scope_activation as activation
from ComfyArt.bot import llm_usd_gate as gate
from test_llm_usd_gate import _reserve_record, _usage
from test_source_migration_1004 import (
    AUTHORITY, OLD_SOURCE, RUNTIME_ID, _candidate, _files, _use_source, migrate,
)


OPERATOR = "tech-lead"
REASON = "raise the post cap"


def opened(tmp_path, monkeypatch, posts=2, name="scope.json"):
    root = tmp_path / Path(name).stem
    root.mkdir(parents=True, exist_ok=True)
    path = str((root / "scope.json").resolve())
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=posts)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, OLD_SOURCE)
    old = activation.runtime_identity(str((root / "home").resolve()), RUNTIME_ID)
    candidate, expected = _candidate(scope, path, old.fingerprint)
    candidate["scope_limits"]["max_posts"] = posts
    expected = replace(expected, max_posts=posts)
    activation.activate_scope(candidate, expected=expected, runtime=old)
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    new = activation.runtime_identity(old.home, old.runtime_id)
    env = {"path": path, "scope_id": scope["scope_id"], "old": old, "new": new}
    migrate(env)
    return env


def extend(env, new_posts=3, **overrides):
    fields = dict(authorization_id=AUTHORITY, scope_id=env["scope_id"], ledger_path=env["path"],
                  new_max_posts=new_posts, operator=OPERATOR, reason=REASON)
    fields.update(overrides)
    return activation.extend_post_limit(env["new"], **fields)


def _binding(env):
    registry = json.loads(Path(env["new"].home, activation._REGISTRY).read_text())
    return registry["authorities"][AUTHORITY]["binding"]


def _settle(env, rid):
    reserved = gate.reserve_nano(env["path"], nano=1200, record=_reserve_record(1200, rid), runtime_binding=_binding(env))
    assert reserved["ok"] is True
    assert gate.settle(env["path"], rid, _usage(0, 1)["usage"])["code"] == "reconciled"


def test_extension_raises_the_post_limit_and_exhausts_there(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch, posts=2)
    _settle(env, "one")
    _settle(env, "two")
    blocked = gate.reserve_nano(env["path"], nano=1200, record=_reserve_record(1200, "three"), runtime_binding=_binding(env))
    assert blocked["ok"] is False and blocked["code"] == "scope_posts_exhausted"
    before = gate.ledger_state(env["path"])
    spent = json.loads(Path(env["path"]).read_text())
    rows = spent["reservations"]
    result = extend(env, 3)
    raw = json.loads(Path(env["path"]).read_text())
    state = gate.ledger_state(env["path"])
    binding = _binding(env)
    assert result == {"ok": True, "scope_id": env["scope_id"], "max_posts": 3, "idempotent": False, "resumed": False}
    assert state["control_limits"]["max_posts"] == 3
    assert state["control_limits"]["amount_nano"] == gate.TWO_DOLLAR_CEILING_NANO
    assert state["control_limits"]["max_inflight"] == 1
    assert state["accounted_nano"] == before["accounted_nano"]
    assert state["control_state"]["attempts_total"] == before["control_state"]["attempts_total"] == 2
    assert state["reservations"].keys() == rows.keys()
    assert binding["manifest"]["scope_limits"]["max_posts"] == 3
    assert binding["manifest"]["scope_limits"]["amount_nano"] == gate.TWO_DOLLAR_CEILING_NANO
    assert binding["manifest_sha256"]
    entry = json.loads(Path(env["new"].home, activation._REGISTRY).read_text())["authorities"][AUTHORITY]
    assert entry["status"] == "active" and entry["digest"] == activation._digest(binding)
    assert raw["limit_extension"] == [{
        "old": 2, "new": 3, "operator": OPERATOR, "reason": REASON, "at": raw["limit_extension"][0]["at"],
    }]
    assert raw["limit_extension"][0]["at"] > 0
    assert raw["runtime_activation"]["manifest"]["scope_limits"]["max_posts"] == 3
    _settle(env, "three")
    again = gate.reserve_nano(env["path"], nano=1200, record=_reserve_record(1200, "four"), runtime_binding=_binding(env))
    assert again["ok"] is False and again["code"] == "scope_posts_exhausted"
    assert gate.ledger_state(env["path"])["control_state"]["attempts_total"] == 3


def test_open_breaker_or_hold_writes_nothing(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    gate.reserve_nano(env["path"], nano=1200, record=_reserve_record(1200, "held"), runtime_binding=_binding(env))
    before = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="hold"):
        extend(env, 3)
    assert _files(env) == before
    gate.retain(env["path"], "held", "unknown")
    retained = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="hold|breaker"):
        extend(env, 3)
    assert _files(env) == retained

    env = opened(tmp_path, monkeypatch, name="tripped.json")

    def trip(data):
        data["control_state"].update(circuit_open=True, circuit_reason="manual", first_anomaly_id="")
        return {"ok": True}

    gate._mutate(env["path"], trip, create=False)
    tripped = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="breaker"):
        extend(env, 3)
    assert _files(env) == tripped


def test_decrease_or_usd_change_writes_nothing(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch, posts=2)
    before = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="decrease"):
        extend(env, 1)
    assert _files(env) == before
    registry_path = Path(env["new"].home, activation._REGISTRY)
    registry = json.loads(registry_path.read_text())
    registry["authorities"][AUTHORITY]["binding"]["manifest"]["scope_limits"]["amount_nano"] = 1
    registry["authorities"][AUTHORITY]["digest"] = activation._digest(registry["authorities"][AUTHORITY]["binding"])
    registry_path.write_text(json.dumps(registry))
    changed = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="usd"):
        extend(env, 3)
    assert _files(env) == changed


def test_limit_above_12_writes_nothing(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    before = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="above_cap"):
        extend(env, 13)
    assert _files(env) == before


def test_repeat_is_idempotent(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    first = extend(env, 4)
    before = _files(env)
    second = extend(env, 4)
    assert _files(env) == before
    assert first["idempotent"] is False and second["idempotent"] is True
    assert {key: second[key] for key in second if key != "idempotent"} == {key: first[key] for key in first if key != "idempotent"}
    assert len(json.loads(Path(env["path"]).read_text())["limit_extension"]) == 1


def test_two_dollar_ceiling_still_blocks_after_extension(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    _settle(env, "spent")
    extend(env, 4)
    state = gate.ledger_state(env["path"])
    assert state["ceiling_nano"] == gate.TWO_DOLLAR_CEILING_NANO
    before = Path(env["path"]).read_bytes()
    blocked = gate.reserve_nano(
        env["path"], nano=state["ceiling_nano"] - state["accounted_nano"] + 1,
        record=_reserve_record(state["ceiling_nano"] - state["accounted_nano"] + 1, "over"),
        runtime_binding=_binding(env))
    assert blocked["ok"] is False and blocked["code"] == "over_budget"
    assert Path(env["path"]).read_bytes() == before
    assert gate.ledger_state(env["path"])["ceiling_nano"] == gate.TWO_DOLLAR_CEILING_NANO


def test_interrupted_extension_resumes_without_a_second_audit_row(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    real = activation._write_registry

    def torn(path, data, stage_prefix="registry_"):
        real(path, data, stage_prefix=stage_prefix)
        if stage_prefix == "extension_pending_":
            raise RuntimeError("torn")

    monkeypatch.setattr(activation, "_write_registry", torn)
    with pytest.raises(RuntimeError, match="torn"):
        extend(env, 5)
    monkeypatch.setattr(activation, "_write_registry", real)
    assert gate.ledger_state(env["path"])["control_limits"]["max_posts"] == 2
    result = extend(env, 5)
    raw = json.loads(Path(env["path"]).read_text())
    assert result["resumed"] is True and result["max_posts"] == 5
    assert raw["control_limits"]["max_posts"] == 5
    assert len(raw["limit_extension"]) == 1 and raw["limit_extension"][0]["old"] == 2
    entry = json.loads(Path(env["new"].home, activation._REGISTRY).read_text())["authorities"][AUTHORITY]
    assert entry["status"] == "active"
