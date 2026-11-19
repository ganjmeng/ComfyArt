"""Raise an existing $2 ledger to $5. Temporary ledger only. No new authority."""
import json
from pathlib import Path

import pytest

from ComfyArt.bot import llm_scope_activation as activation
from ComfyArt.bot import llm_usd_gate as gate
from test_extend_post_limit_1004 import OPERATOR, REASON, _binding, extend, opened
from test_llm_usd_gate import _reserve_record
from test_source_migration_1004 import AUTHORITY, OLD_SOURCE, _files, _use_source, bound, migrate


FIVE = gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO


def raise_ceiling(env, amount=FIVE, runtime="new", **overrides):
    fields = dict(authorization_id=AUTHORITY, scope_id=env["scope_id"], ledger_path=env["path"],
                  new_amount_nano=amount, operator=OPERATOR, reason=REASON)
    fields.update(overrides)
    return activation.extend_ceiling(env[runtime], **fields)


def test_raise_two_to_five_writes_audit_and_leaves_other_fields(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    held = gate.reserve_external_spend(env["path"], quote_nano=80_000, task_ref="kept", operator=OPERATOR)
    assert gate.settle_external_spend(env["path"], held["reservation_id"], "ws-kept", 25_000, OPERATOR)["status"] == "reconciled"
    before = json.loads(Path(env["path"]).read_text())
    blocked = gate.reserve_nano(
        env["path"], nano=gate.TWO_DOLLAR_CEILING_NANO + 1,
        record=_reserve_record(gate.TWO_DOLLAR_CEILING_NANO + 1, "over-two"),
        runtime_binding=_binding(env))
    assert blocked["ok"] is False and blocked["code"] == "over_budget"
    result = raise_ceiling(env)
    raw = json.loads(Path(env["path"]).read_text())
    state = gate.ledger_state(env["path"])
    binding = _binding(env)
    assert result == {"ok": True, "scope_id": env["scope_id"], "amount_nano": FIVE, "idempotent": False, "resumed": False}
    assert state["ceiling_nano"] == FIVE
    assert state["authorized_ceiling_nano"] == FIVE
    assert state["control_limits"]["amount_nano"] == FIVE
    assert state["control_limits"]["max_posts"] == before["control_limits"]["max_posts"]
    assert state["control_limits"]["max_inflight"] == 1
    assert state["accounted_nano"] == before["accounted_nano"]
    assert state["control_state"]["attempts_total"] == before["control_state"]["attempts_total"]
    assert raw["reservations"] == before["reservations"]
    assert raw["external_spend"] == before["external_spend"]
    assert binding["manifest"]["scope_limits"]["amount_nano"] == FIVE
    assert binding["manifest"]["scope_limits"]["max_posts"] == before["control_limits"]["max_posts"]
    assert binding["manifest_sha256"]
    entry = json.loads(Path(env["new"].home, activation._REGISTRY).read_text())["authorities"][AUTHORITY]
    assert entry["status"] == "active" and entry["digest"] == activation._digest(binding)
    assert raw["ceiling_extension"] == [{
        "old": gate.TWO_DOLLAR_CEILING_NANO, "new": FIVE, "operator": OPERATOR, "reason": REASON,
        "at": raw["ceiling_extension"][0]["at"],
    }]
    assert raw["ceiling_extension"][0]["at"] > 0
    allowed = gate.reserve_nano(
        env["path"], nano=gate.TWO_DOLLAR_CEILING_NANO + 1,
        record=_reserve_record(gate.TWO_DOLLAR_CEILING_NANO + 1, "inside-five"),
        runtime_binding=_binding(env))
    assert allowed["ok"] is True and allowed["ceiling_nano"] == FIVE


def test_decrease_is_refused(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    before = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="decrease"):
        raise_ceiling(env, gate.TWO_DOLLAR_CEILING_NANO - 1)
    assert _files(env) == before
    raise_ceiling(env)
    extended = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="decrease"):
        raise_ceiling(env, gate.TWO_DOLLAR_CEILING_NANO)
    assert _files(env) == extended


def test_above_five_or_unreviewed_amount_is_refused(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    before = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="above_cap"):
        raise_ceiling(env, FIVE + 1)
    with pytest.raises(gate.LlmBudgetBlocked, match="amount"):
        raise_ceiling(env, gate.TWO_DOLLAR_CEILING_NANO + 1)
    assert _files(env) == before
    assert gate.ledger_state(env["path"])["ceiling_nano"] == gate.TWO_DOLLAR_CEILING_NANO


def test_inflight_reservation_breaker_or_journal_writes_nothing(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    gate.reserve_nano(env["path"], nano=1200, record=_reserve_record(1200, "held"), runtime_binding=_binding(env))
    before = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="hold|inflight"):
        raise_ceiling(env)
    assert _files(env) == before

    env = opened(tmp_path, monkeypatch, name="tripped.json")

    def trip(data):
        data["control_state"].update(circuit_open=True, circuit_reason="manual", first_anomaly_id="")
        return {"ok": True}

    gate._mutate(env["path"], trip, create=False)
    tripped = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="breaker"):
        raise_ceiling(env)
    assert _files(env) == tripped

    env = opened(tmp_path, monkeypatch, name="journal.json")
    Path(gate._outcome_pending_path(env["path"])).write_text("pending")
    journal = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="journal"):
        raise_ceiling(env)
    assert _files(env) == journal


def test_repeat_is_idempotent(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch)
    first = raise_ceiling(env)
    before = _files(env)
    second = raise_ceiling(env)
    assert _files(env) == before
    assert first["idempotent"] is False and second["idempotent"] is True
    assert len(json.loads(Path(env["path"]).read_text())["ceiling_extension"]) == 1


def test_posts_cap_is_12_before_raise_and_30_after(tmp_path, monkeypatch):
    env = opened(tmp_path, monkeypatch, posts=6)
    before = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="above_cap"):
        extend(env, 13)
    with pytest.raises(gate.LlmBudgetBlocked, match="above_cap"):
        extend(env, 30)
    assert _files(env) == before
    assert extend(env, 12)["max_posts"] == 12
    raise_ceiling(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="above_cap"):
        extend(env, 31)
    assert gate.ledger_state(env["path"])["control_limits"]["max_posts"] == 12
    assert extend(env, 30)["max_posts"] == 30
    state = gate.ledger_state(env["path"])
    assert state["control_limits"]["max_posts"] == 30
    assert state["ceiling_nano"] == FIVE
    assert state["control_limits"]["amount_nano"] == FIVE
    raw = json.loads(Path(env["path"]).read_text())
    assert raw["limit_extension"][-1]["new"] == 30
    assert raw["ceiling_extension"][0]["new"] == FIVE


def test_migration_after_ceiling_extension_keeps_the_raised_ceiling(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, OLD_SOURCE)
    raise_ceiling(env, runtime="old")
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    before = gate.ledger_state(env["path"])
    assert before["ceiling_nano"] == FIVE and before["accounted_nano"] == 0
    migrated = migrate(env)
    state = gate.ledger_state(env["path"])
    raw = json.loads(Path(env["path"]).read_text())
    assert migrated["ok"] is True
    assert state["ceiling_nano"] == FIVE
    assert state["authorized_ceiling_nano"] == FIVE
    assert state["control_limits"]["amount_nano"] == FIVE
    assert state["accounted_nano"] == before["accounted_nano"]
    assert state["control_state"]["attempts_total"] == before["control_state"]["attempts_total"]
    assert raw["reservations"] == {}
    assert "external_spend" not in raw
    assert raw["ceiling_extension"][0]["new"] == FIVE
    assert raw["runtime_activation"]["manifest"]["scope_limits"]["amount_nano"] == FIVE
