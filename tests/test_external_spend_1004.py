"""Provider quotes share the ledger ceiling and do not consume DeepSeek POSTs."""
import json
from pathlib import Path

import pytest

from ComfyArt.bot import llm_scope_activation as activation
from ComfyArt.bot import llm_usd_gate as gate
from test_llm_usd_gate import _reserve_record, _usage


def scope(tmp_path):
    path = str((tmp_path / "scope.json").resolve())
    gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=6)
    return path


def _llm(path, rid="llm"):
    assert gate.reserve_nano(path, nano=1200, record=_reserve_record(1200, rid))["ok"] is True
    assert gate.settle(path, rid, _usage(0, 1)["usage"])["code"] == "reconciled"


def test_reserve_within_ceiling_and_second_hold_is_refused(tmp_path):
    path = scope(tmp_path)
    before_posts = gate.ledger_state(path)["control_state"]["attempts_total"]
    held = gate.reserve_external_spend(path, quote_nano=50_000, task_ref="job-1", operator="ops")
    state = gate.ledger_state(path)
    assert held["ok"] is True and held["quote_nano"] == 50_000
    assert state["accounted_nano"] == 50_000
    assert state["control_state"]["attempts_total"] == before_posts == 0
    assert state["inflight"] == 0 and state["external_inflight"] == 1
    raw = Path(path).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="inflight"):
        gate.reserve_external_spend(path, quote_nano=1, task_ref="job-2", operator="ops")
    assert Path(path).read_bytes() == raw


def test_reserve_over_ceiling_writes_nothing(tmp_path):
    path = scope(tmp_path)
    before = Path(path).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="ceiling"):
        gate.reserve_external_spend(path, quote_nano=gate.TWO_DOLLAR_CEILING_NANO + 1, task_ref="too-big", operator="ops")
    assert Path(path).read_bytes() == before
    assert b"external_spend" not in before


def test_settle_records_task_id_and_actual_without_using_a_post(tmp_path):
    path = scope(tmp_path)
    _llm(path)
    posts = gate.ledger_state(path)["control_state"]["attempts_total"]
    held = gate.reserve_external_spend(path, quote_nano=80_000, task_ref="quote-a", operator="ops")
    result = gate.settle_external_spend(path, held["reservation_id"], "ws-task-9", 25_000, "ops")
    raw = json.loads(Path(path).read_text())
    row = raw["external_spend"][held["reservation_id"]]
    state = gate.ledger_state(path)
    assert result["idempotent"] is False and result["status"] == "reconciled"
    assert row["task_id"] == "ws-task-9" and row["actual_nano"] == 25_000 and row["status"] == "reconciled"
    assert state["accounted_nano"] == held["accounted_nano"] - (80_000 - 25_000)
    assert state["control_state"]["attempts_total"] == posts == 1
    assert state["external_inflight"] == 0 and state["inflight"] == 0
    assert state["control_state"]["circuit_open"] is False


def test_actual_above_quote_is_recorded_and_trips_the_breaker(tmp_path):
    path = scope(tmp_path)
    held = gate.reserve_external_spend(path, quote_nano=10_000, task_ref="quote-b", operator="ops")
    result = gate.settle_external_spend(path, held["reservation_id"], "ws-task-over", 16_000, "ops")
    row = json.loads(Path(path).read_text())["external_spend"][held["reservation_id"]]
    state = gate.ledger_state(path)
    assert result["circuit_open"] is True
    assert row["task_id"] == "ws-task-over" and row["actual_nano"] == 16_000 and row["status"] == "reconciled"
    assert state["accounted_nano"] == 16_000
    assert state["control_state"]["circuit_open"] is True
    assert state["control_state"]["circuit_reason"] == "external_over_quote"
    assert state["control_state"]["attempts_total"] == 0


def test_settle_is_idempotent(tmp_path):
    path = scope(tmp_path)
    held = gate.reserve_external_spend(path, quote_nano=4_000, task_ref="quote-c", operator="ops")
    first = gate.settle_external_spend(path, held["reservation_id"], "ws-task-same", 4_000, "ops")
    raw = Path(path).read_bytes()
    second = gate.settle_external_spend(path, held["reservation_id"], "ws-task-same", 4_000, "ops")
    assert Path(path).read_bytes() == raw
    assert second["idempotent"] is True
    assert {key: second[key] for key in second if key != "idempotent"} == {key: first[key] for key in first if key != "idempotent"}


def test_unknown_external_outcome_stays_retained_at_the_quote(tmp_path):
    path = scope(tmp_path)
    held = gate.reserve_external_spend(path, quote_nano=7_000, task_ref="quote-unknown", operator="ops")
    result = gate.settle_external_spend(path, held["reservation_id"], "", None, "ops")
    row = json.loads(Path(path).read_text())["external_spend"][held["reservation_id"]]
    state = gate.ledger_state(path)
    assert result["status"] == "retained"
    assert row["status"] == "retained" and row["actual_nano"] is None and row["quote_nano"] == 7_000
    assert state["accounted_nano"] == 7_000
    assert state["control_state"]["circuit_open"] is True
    assert state["control_state"]["attempts_total"] == 0


def test_llm_plus_external_reaching_the_ceiling_blocks_another_llm_reserve(tmp_path):
    path = scope(tmp_path)
    _llm(path)
    state = gate.ledger_state(path)
    remaining = state["ceiling_nano"] - state["accounted_nano"]
    held = gate.reserve_external_spend(path, quote_nano=remaining, task_ref="fill", operator="ops")
    gate.settle_external_spend(path, held["reservation_id"], "ws-fill", remaining, "ops")
    filled = gate.ledger_state(path)
    assert filled["accounted_nano"] == gate.TWO_DOLLAR_CEILING_NANO
    assert filled["control_state"]["attempts_total"] == 1
    before = Path(path).read_bytes()
    blocked = gate.reserve_nano(path, nano=1, record=_reserve_record(1, "one-more"))
    assert blocked["ok"] is False and blocked["code"] == "over_budget"
    assert Path(path).read_bytes() == before


def test_external_unknown_resolves_and_a_deepseek_post_can_proceed(tmp_path):
    path = scope(tmp_path)
    held = gate.reserve_external_spend(path, quote_nano=9_000, task_ref="unknown-ext", operator="ops")
    gate.settle_external_spend(path, held["reservation_id"], "", None, "ops")
    blocked = gate.reserve_nano(path, nano=1200, record=_reserve_record(1200, "blocked"))
    assert blocked["ok"] is False and blocked["code"] == "scope_circuit_open"
    result = gate.resolve_unknown_as_spent(path, held["reservation_id"], "tech-lead", "book the external unknown")
    row = json.loads(Path(path).read_text())["external_spend"][held["reservation_id"]]
    state = gate.ledger_state(path)
    assert result["ok"] is True and result["circuit_open"] is False and result["actual_nano"] == 9_000
    assert row["status"] == "resolved_as_spent" and row["actual_nano"] == row["quote_nano"] == 9_000
    assert state["accounted_nano"] == 9_000
    assert state["control_state"]["circuit_open"] is False
    assert state["control_state"]["attempts_total"] == 0
    assert state["external_inflight"] == 0 and state["inflight"] == 0
    posted = gate.reserve_nano(path, nano=1200, record=_reserve_record(1200, "after"))
    assert posted["ok"] is True
    assert gate.settle(path, "after", _usage(0, 1)["usage"])["code"] == "reconciled"
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 1
    with gate._with_ledger_lock(path):
        data, _, _ = gate._load_ledger(path, create=False)
        activation._require_safe_spend(path, data)


def test_other_retained_row_refuses_external_resolve_and_leaves_the_breaker_open(tmp_path):
    path = scope(tmp_path)
    held = gate.reserve_external_spend(path, quote_nano=4_000, task_ref="unknown-ext", operator="ops")
    gate.settle_external_spend(path, held["reservation_id"], "", None, "ops")

    def plant(data):
        data["reservations"]["still"] = {
            "id": "still", "status": "retained", "reserved_nano": 1200, "actual_nano": None,
            "retain_reason": "other", "authorization": data["authorization"],
            "authorized_ceiling_nano": data["authorized_ceiling_nano"],
        }
        return {"ok": True}

    gate._mutate(path, plant, create=False)
    before = Path(path).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked, match="other_retained"):
        gate.resolve_unknown_as_spent(path, held["reservation_id"], "tech-lead", "book the external unknown")
    assert Path(path).read_bytes() == before
    state = gate.ledger_state(path)
    assert state["control_state"]["circuit_open"] is True
    assert state["control_state"]["first_anomaly_id"] == held["reservation_id"]
    assert json.loads(before)["external_spend"][held["reservation_id"]]["status"] == "retained"


def test_existing_ledger_without_external_rows_loads_unchanged(tmp_path):
    path = scope(tmp_path)
    before = Path(path).read_bytes()
    assert b"external_spend" not in before
    state = gate.ledger_state(path)
    assert Path(path).read_bytes() == before
    assert state["external_inflight"] == 0 and state["accounted_nano"] == 0
    with gate._with_ledger_lock(path):
        data, _, _ = gate._load_ledger(path, create=False)
        activation._require_safe_spend(path, data)


def test_reconciled_external_row_still_allows_migration_checks(tmp_path):
    path = scope(tmp_path)
    held = gate.reserve_external_spend(path, quote_nano=3_000, task_ref="kept", operator="ops")
    with gate._with_ledger_lock(path):
        data, _, _ = gate._load_ledger(path, create=False)
        with pytest.raises(gate.LlmBudgetBlocked, match="external_hold"):
            activation._require_safe_spend(path, data)
    gate.settle_external_spend(path, held["reservation_id"], "ws-kept", 3_000, "ops")
    with gate._with_ledger_lock(path):
        data, _, _ = gate._load_ledger(path, create=False)
        activation._require_safe_spend(path, data)
