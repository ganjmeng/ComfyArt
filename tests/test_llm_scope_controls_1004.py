"""Local controlled validation scopes: fake HTTP, temporary ledgers only.

No control here proves a supplier billing contract or activates a live scope.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ComfyArt.api import provider_admin
from ComfyArt.bot import llm_usd_gate as gate, local_llm
from ComfyArt.bot.local_llm import LlmHttpError
from ComfyArt.bot.providers import TurnHandle
from test_llm_usd_gate import _provider, _reserve_record, _route, _text, _usage as _usage_envelope, _zero_bound, URL


@pytest.fixture(autouse=True)
def isolated_controls(monkeypatch):
    monkeypatch.setenv("COMFYART_LLM_USD_GATE", "1")
    gate.clear_authorized_scope()
    gate._write_fault = None
    token = provider_admin._llm_lock.set(_route())
    for name in list(os.environ):
        if name.endswith("_API_KEY") or name in ("DEEPSEEK_TOKEN", "OPENAI_TOKEN"):
            monkeypatch.delenv(name, raising=False)
    yield
    provider_admin._llm_lock.reset(token)
    gate._write_fault = None
    gate.clear_authorized_scope()


def scope(tmp_path, *, max_posts, amount=gate.CEILING_NANO):
    path = str(tmp_path / "controlled.json")
    gate.open_authorized_scope(path, amount, max_posts=max_posts)
    return path


def _usage(prompt, completion):
    return _usage_envelope(prompt, completion)["usage"]


def success(*, completion=1):
    return {"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": _usage(0, completion)}


async def post(path, send, *, body=None, bound_fn=_zero_bound):
    return await gate.dispatch(body or _text(max_tokens=1), route=_route(), url=URL,
                               send=send, ledger_path=path, bound_fn=bound_fn)


@pytest.mark.parametrize("invalid", [True, False, 0, -1, 7, 1.5, "6"])
def test_controls_require_explicit_valid_post_limit(tmp_path, invalid):
    path = str(tmp_path / "invalid.json")
    with pytest.raises(gate.LlmScopeConflict):
        gate.open_authorized_scope(path, gate.CEILING_NANO, max_posts=invalid)
    assert not Path(path).exists()


async def test_success_releases_inflight_not_post_count_and_limit_is_exact(tmp_path):
    path = scope(tmp_path, max_posts=2)
    sent = []

    async def send():
        state = gate.ledger_state(path)
        assert state["inflight"] == 1
        assert state["control_state"]["attempts_total"] == len(sent) + 1
        sent.append(1)
        return success()

    await post(path, send)
    await post(path, send)
    before = Path(path).read_bytes()
    with pytest.raises(gate.LlmBudgetBlocked) as blocked:
        await post(path, send)
    assert blocked.value.code == "scope_posts_exhausted"
    assert Path(path).read_bytes() == before
    state = gate.ledger_state(path)
    assert len(sent) == 2
    assert state["inflight"] == 0
    assert state["control_state"]["attempts_total"] == 2
    assert state["accounted_nano"] == 2400


async def test_amount_cap_and_count_are_same_reservation_transaction(tmp_path):
    path = scope(tmp_path, max_posts=6)
    sent = []

    async def send():
        sent.append(1)
        return success(completion=8192)

    for _ in range(5):
        await post(path, send, body=_text(max_tokens=8192))
    with pytest.raises(gate.LlmBudgetBlocked) as blocked:
        await post(path, send, body=_text(max_tokens=8192))
    assert blocked.value.code == "over_budget"
    assert len(sent) == 5
    state = gate.ledger_state(path)
    assert state["control_state"]["attempts_total"] == 5
    assert state["accounted_nano"] == 5 * 8192 * 1200


async def test_production_preflight_rejection_does_not_consume_attempt(tmp_path):
    path = scope(tmp_path, max_posts=1)
    before = Path(path).read_bytes()

    async def never():
        raise AssertionError("production proof must remain fail-closed")

    with pytest.raises(gate.LlmBudgetBlocked) as blocked:
        await post(path, never, bound_fn=None)
    assert blocked.value.code == "unbounded_billed_input"
    assert Path(path).read_bytes() == before
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 0


async def test_one_inflight_rejects_competitor_without_spending_count(tmp_path):
    path = scope(tmp_path, max_posts=2)
    started, release = asyncio.Event(), asyncio.Event()

    async def held():
        started.set()
        await release.wait()
        return success()

    task = asyncio.create_task(post(path, held))
    await started.wait()
    try:
        with pytest.raises(gate.LlmBudgetBlocked) as blocked:
            await post(path, held)
        assert blocked.value.code == "scope_inflight"
        assert gate.ledger_state(path)["control_state"]["attempts_total"] == 1
    finally:
        release.set()
        await task
    assert gate.ledger_state(path)["inflight"] == 0


@pytest.mark.parametrize("failure", [
    "timeout", "cancel", "http400", "http429", "http500", "overflow", "json", "error200",
    "refusal", "filter", "finish_error", "bad_response", "missing_usage", "bad_usage", "over_bound",
])
async def test_first_anomaly_latches_unknown_and_stops_all_followups(tmp_path, failure):
    path = scope(tmp_path, max_posts=6)
    sent = []
    original = None

    async def send():
        nonlocal original
        sent.append(1)
        if failure in ("http400", "http429", "http500", "overflow"):
            status = {"http400": 400, "http429": 429, "http500": 500, "overflow": 400}[failure]
            original = LlmHttpError(status, "context length exceeded" if failure == "overflow" else "fake provider error")
            raise original
        if failure == "timeout":
            original = asyncio.TimeoutError("fake timeout")
            raise original
        if failure == "cancel":
            original = asyncio.CancelledError()
            raise original
        if failure == "json":
            original = ValueError("fake invalid JSON")
            raise original
        result = success()
        if failure == "error200":
            result["error"] = {"code": "fake_inference_interrupted"}
        elif failure == "refusal":
            result["choices"][0]["message"]["refusal"] = "fake refusal"
        elif failure == "filter":
            result["choices"][0]["finish_reason"] = "content_filter"
        elif failure == "finish_error":
            result["choices"][0]["finish_reason"] = "error"
        elif failure == "bad_response":
            return []
        elif failure == "missing_usage":
            del result["usage"]
        elif failure == "bad_usage":
            result["usage"]["prompt_tokens"] = True
        elif failure == "over_bound":
            result["usage"] = _usage(1, 1)
        return result

    expected = asyncio.CancelledError if failure == "cancel" else gate.LlmScopeStopped
    with pytest.raises(expected) as stopped:
        await post(path, send)
    if original is not None and failure != "cancel":
        assert stopped.value.__cause__ is original
    state = gate.ledger_state(path)
    assert state["control_state"]["circuit_open"] is True
    assert state["control_state"]["attempts_total"] == 1
    assert state["inflight"] == 0
    assert next(iter(state["reservations"].values()))["status"] == "retained"
    assert state["accounted_nano"] >= 1200
    reason = state["control_state"]["circuit_reason"]
    for _kind in ("retry", "summary", "overflow", "boost"):
        with pytest.raises(gate.LlmBudgetBlocked) as blocked:
            await post(path, send)
        assert blocked.value.code == "scope_circuit_open"
    assert sent == [1]
    assert gate.ledger_state(path)["control_state"]["circuit_reason"] == reason


def test_immutable_limits_marker_rejects_reconfiguration_and_policy_removal(tmp_path):
    path = scope(tmp_path, max_posts=2)
    before = Path(path).read_bytes()
    with pytest.raises(gate.LlmScopeConflict):
        gate.constrain_authorized_scope(path, max_posts=3)
    assert Path(path).read_bytes() == before
    parsed = json.loads(before)
    del parsed["control_limits"]
    del parsed["control_state"]
    Path(path).write_text(json.dumps(parsed))
    with pytest.raises(gate.LlmBudgetBlocked) as blocked:
        gate.ledger_state(path)
    assert blocked.value.detail == "controlled_limits_changed"


@pytest.mark.parametrize("historical", ["reconciled", "reserved", "retained"])
def test_explicit_legacy_migration_never_resets_count_money_or_default_authority(tmp_path, historical):
    path = str(tmp_path / "legacy.json")
    gate.open_authorized_scope(path, gate.CEILING_NANO)
    record = _reserve_record(1200, "old")
    gate.reserve_nano(path, nano=1200, record=record)
    if historical == "reconciled":
        gate.settle(path, "old", _usage(0, 1))
    elif historical == "retained":
        gate.retain(path, "old", "old_unknown")
    before = gate.ledger_state(path)
    assert "control_limits" not in before
    gate.constrain_authorized_scope(path, max_posts=2)
    state = gate.ledger_state(path)
    assert state["scope_id"] == before["scope_id"]
    assert state["accounted_nano"] == before["accounted_nano"]
    assert state["ceiling_nano"] == gate.CEILING_NANO
    assert state["control_limits"]["amount_nano"] == gate.CEILING_NANO
    assert state["control_state"]["attempts_total"] == 1
    assert state["control_state"]["circuit_open"] == (historical != "reconciled")
    marker = json.loads(Path(path + ".activated").read_text())
    assert marker["control_limits"] == state["control_limits"]
    with pytest.raises(gate.LlmScopeConflict):
        gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=6)


def test_controlled_duplicate_settlement_and_retain_never_double_release_or_reset_breaker(tmp_path):
    path = scope(tmp_path, max_posts=3)
    gate.reserve_nano(path, nano=1200, record=_reserve_record(1200, "first"))
    assert gate.settle(path, "first", _usage(0, 1))["code"] == "reconciled"
    before = gate.ledger_state(path)
    assert gate.settle(path, "first", _usage(0, 0))["code"] == "missing_reservation"
    assert gate.retain(path, "first", "duplicate")["code"] == "missing_reservation"
    assert gate.ledger_state(path) == before
    gate.reserve_nano(path, nano=1200, record=_reserve_record(1200, "unknown"))
    gate.retain(path, "unknown", "first_anomaly")
    latched = gate.ledger_state(path)
    gate.settle(path, "unknown", _usage(0, 0))
    gate.retain(path, "unknown", "different")
    assert gate.ledger_state(path) == latched


@pytest.mark.parametrize("shape", ["normal", "error", "refusal"])
async def test_overbound_observation_is_not_clipped_to_authorized_amount(tmp_path, shape):
    path = scope(tmp_path, max_posts=1)

    async def send():
        result = success(completion=100_000)
        if shape == "error":
            result["error"] = {"code": "fake_interrupted"}
        elif shape == "refusal":
            result["choices"][0]["message"]["refusal"] = "fake refusal"
        return result

    with pytest.raises(gate.LlmScopeStopped):
        await post(path, send)
    state = gate.ledger_state(path)
    row = next(iter(state["reservations"].values()))
    assert row["observed_nano"] == 120_000_000
    assert row["reservation_violation"] and row["budget_violation"]
    assert state["accounted_nano"] == 120_000_000 > state["ceiling_nano"]
    assert state["control_state"]["circuit_open"]


@pytest.mark.parametrize("outcome", ["success", "http_error"])
@pytest.mark.parametrize("stage", ["before_temp", "before_replace", "dir_fsync"])
async def test_outcome_write_failure_preserves_hold_and_latches_before_unlock(tmp_path, outcome, stage):
    path = scope(tmp_path, max_posts=2)
    injected = []
    original = LlmHttpError(500, "fake transport failure")

    def fail_once(name):
        if name == stage and not injected:
            injected.append(name)
            raise OSError("fake outcome write failure")

    async def send():
        gate._write_fault = fail_once
        if outcome == "http_error":
            raise original
        return success(completion=0)

    with pytest.raises(gate.LlmScopeStopped) as stopped:
        await post(path, send)
    gate._write_fault = None
    if outcome == "http_error":
        assert stopped.value.__cause__ is original
    state = gate.ledger_state(path)
    assert injected == [stage]
    assert state["accounted_nano"] == 1200
    assert state["control_state"]["attempts_total"] == 1
    assert state["control_state"]["circuit_open"]
    with pytest.raises(gate.LlmBudgetBlocked):
        await post(path, send)


_CHILD_PROGRAM = r"""
import asyncio, importlib.util, json, os, sys, time
spec = importlib.util.spec_from_file_location('gate', sys.argv[1])
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
action, path = sys.argv[2:4]
if action == 'state':
    print(json.dumps(gate.ledger_state(path)))
    raise SystemExit(0)
if action == 'crash' or action.startswith('reserve_fault:'):
    if action.startswith('reserve_fault:'):
        stage = action.split(':', 1)[1]
        def fault(name):
            if name == stage:
                os._exit(91)
        gate._write_fault = fault
    record = {'id':'crashed','status':'reserved','reserved_nano':1200,'actual_nano':None,
              'retain_reason':'','input_bound':0,'max_output_tokens':1,
              'snapshot':gate.price_snapshot('deepseek-flash')}
    gate.reserve_nano(path, nano=1200, record=record)
    os._exit(91)
async def send():
    active = path + '.fake_transport_active'
    fd = os.open(active, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        time.sleep(0.03)
        completion = 1
        if action.startswith('outcome_crash:'):
            completion = 0
            stage = action.split(':', 1)[1]
            def fault(name):
                if name == stage:
                    os._exit(91)
            gate._write_fault = fault
        return {'choices':[{'message':{'role':'assistant','content':'ok'}}], 'usage':{
            'prompt_tokens':0,'completion_tokens':completion,'total_tokens':completion,
            'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':0,
            'prompt_tokens_details':{'cached_tokens':0}}}
    finally:
        os.unlink(active)
route = {'provider':'deepseek','model':'deepseek-flash','catalog_model':'deepseek-flash',
         'base_url':'https://api.deepseek.com','adapter':'deepseek_official','passthrough':False,'quote':'unknown'}
body = {'model':'deepseek-flash','messages':[{'role':'user','content':'hi'}],
        'thinking':{'type':'disabled'},'max_tokens':1}
try:
    asyncio.run(gate.dispatch(body, route=route, url='https://api.deepseek.com/chat/completions', send=send,
                             ledger_path=path, bound_fn=lambda b,s: gate.Bound(True,0,'','test-only')))
    print(json.dumps({'sent':True}))
except gate.LlmBudgetBlocked as exc:
    print(json.dumps({'sent':False,'code':exc.code}))
"""


def child(path, action):
    return subprocess.run([sys.executable, "-c", _CHILD_PROGRAM, str(Path(gate.__file__).resolve()), action, path],
                          capture_output=True, text=True, timeout=10)


def test_process_exit_after_reserve_keeps_count_amount_and_inflight_across_restart(tmp_path):
    path = scope(tmp_path, max_posts=2)
    proc = child(path, "crash")
    assert proc.returncode == 91, proc.stderr
    restarted = child(path, "state")
    assert restarted.returncode == 0, restarted.stderr
    state = json.loads(restarted.stdout)
    assert state["control_state"]["attempts_total"] == 1
    assert state["accounted_nano"] == 1200 and state["inflight"] == 1
    attempt = child(path, "post")
    assert attempt.returncode == 0, attempt.stderr
    assert json.loads(attempt.stdout) == {"sent": False, "code": "scope_inflight"}


def test_multiprocess_reserve_and_success_never_exceed_posts_or_one_transport(tmp_path):
    path = scope(tmp_path, max_posts=3)
    args = [sys.executable, "-c", _CHILD_PROGRAM, str(Path(gate.__file__).resolve()), "post", path]
    processes = [subprocess.Popen(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(12)]
    results = []
    for proc in processes:
        out, err = proc.communicate(timeout=15)
        assert proc.returncode == 0, (out, err)
        results.append(json.loads(out))
    state = gate.ledger_state(path)
    assert state["control_state"]["attempts_total"] <= 3
    assert sum(result["sent"] for result in results) == state["control_state"]["attempts_total"]
    # Fill unused slots serially, then prove a fresh process cannot get slot 4.
    while gate.ledger_state(path)["control_state"]["attempts_total"] < 3:
        proc = child(path, "post")
        assert proc.returncode == 0 and json.loads(proc.stdout)["sent"], proc.stderr
    last = child(path, "post")
    assert json.loads(last.stdout) == {"sent": False, "code": "scope_posts_exhausted"}
    state = gate.ledger_state(path)
    assert state["accounted_nano"] == 3600 and state["inflight"] == 0


async def test_fresh_interpreter_sees_first_anomaly_and_cannot_send(tmp_path):
    path = scope(tmp_path, max_posts=6)

    async def uncertain():
        raise asyncio.TimeoutError("fake timeout")

    with pytest.raises(gate.LlmScopeStopped):
        await post(path, uncertain)
    proc = child(path, "post")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"sent": False, "code": "scope_circuit_open"}


@pytest.mark.parametrize("status", [400, 429, 500])
async def test_real_provider_retry_overflow_and_summary_stop_at_first_anomaly(tmp_path, monkeypatch, status):
    path = scope(tmp_path, max_posts=6)
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(json_body)
        raise LlmHttpError(status, "context length exceeded; maximum context length is 8192" if status == 400 else "fake retryable failure")

    provider = _provider(transport, path)
    monkeypatch.setattr(local_llm, "_RETRY_BACKOFF_S", (0.0, 0.0))

    async def emit(event):
        pass

    with pytest.raises(gate.LlmScopeStopped):
        await provider._llm_request_fit(None, URL, _text(max_tokens=1), emit, TurnHandle(),
                                        model="deepseek-flash", window=32000, refit=lambda m,w:m)
    with pytest.raises(gate.LlmBudgetBlocked):
        await provider._summarize_llm(None, "https://api.deepseek.com", "deepseek-flash", "", "fake old turns")
    assert len(calls) == 1
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 1


@pytest.mark.parametrize("stage,committed", [
    ("before_temp", False), ("after_temp_write", False), ("after_temp_fsync", False), ("before_replace", False),
    ("after_replace", True), ("dir_fsync", True), ("after_dir_fsync", True),
])
def test_abrupt_reservation_crash_cannot_split_amount_count_or_inflight(tmp_path, stage, committed):
    path = scope(tmp_path, max_posts=2)
    proc = child(path, "reserve_fault:" + stage)
    assert proc.returncode == 91, proc.stderr
    restarted = child(path, "state")
    assert restarted.returncode == 0, restarted.stderr
    state = json.loads(restarted.stdout)
    assert state["control_state"]["attempts_total"] == int(committed)
    assert state["accounted_nano"] == 1200 * int(committed)
    assert state["inflight"] == int(committed)


@pytest.mark.parametrize("amount", [gate.CEILING_NANO, gate.TWO_DOLLAR_CEILING_NANO])
def test_new_controlled_scope_records_explicit_limits_without_inference(tmp_path, amount):
    path = scope(tmp_path, max_posts=4, amount=amount)
    state = gate.ledger_state(path)
    assert state["control_limits"] == {"version": 1, "amount_nano": amount, "max_posts": 4, "max_inflight": 1}
    assert state["accounted_nano"] == 0
    assert state["control_state"]["attempts_total"] == 0
    assert not state["control_state"]["circuit_open"]


@pytest.mark.parametrize("bad", ["wrong_amount", "wrong_status", "empty_id", "actual_prepopulated"])
def test_invalid_reservation_record_never_consumes_controlled_attempt(tmp_path, bad):
    path = scope(tmp_path, max_posts=1)
    before = Path(path).read_bytes()
    record = _reserve_record(1200, "bad")
    if bad == "wrong_amount":
        record["reserved_nano"] = 1
    elif bad == "wrong_status":
        record["status"] = "reconciled"
    elif bad == "empty_id":
        record["id"] = ""
    else:
        record["actual_nano"] = 0
    with pytest.raises(gate.LlmBudgetBlocked):
        gate.reserve_nano(path, nano=1200, record=record)
    assert Path(path).read_bytes() == before


async def test_controlled_short_write_then_enospc_does_not_replace_or_send(tmp_path, monkeypatch):
    from test_llm_usd_gate import _inject_r1_writes
    path = scope(tmp_path, max_posts=1)
    before = Path(path).read_bytes()
    writes, replacements = _inject_r1_writes(monkeypatch, Path(path), "enospc")
    sent = []

    async def never():
        sent.append(1)
        return success()

    with pytest.raises(OSError):
        await post(path, never)
    assert len(writes) == 2 and path not in replacements
    assert sent == [] and Path(path).read_bytes() == before
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 0


async def test_real_provider_main_and_summary_each_consume_a_post_not_a_step(tmp_path):
    path = scope(tmp_path, max_posts=2)
    calls = []

    async def transport(session, method, url, *, headers, json_body=None, timeout=120):
        calls.append(json_body)
        return success(completion=0)

    provider = _provider(transport, path)

    async def emit(_event):
        pass

    await provider._llm_request(None, URL, _text(max_tokens=1), emit, TurnHandle())
    await provider._summarize_llm(None, "https://api.deepseek.com", "deepseek-flash", "", "fake old turns")
    with pytest.raises(gate.LlmBudgetBlocked) as blocked:
        await provider._llm_request(None, URL, _text(max_tokens=1), emit, TurnHandle())
    assert blocked.value.code == "scope_posts_exhausted"
    assert len(calls) == 2
    state = gate.ledger_state(path)
    assert state["control_state"]["attempts_total"] == 2
    assert state["accounted_nano"] == 0 and state["inflight"] == 0


async def test_permanent_write_failure_after_visible_settlement_cannot_free_unknown(tmp_path):
    path = scope(tmp_path, max_posts=2)
    failed = []

    def storage_failure(stage):
        if stage == "dir_fsync":
            failed.append("visible_replace_then_failure")
            raise OSError("fake settlement directory fsync failure")
        if failed and stage == "before_temp":
            raise OSError("fake persistent disk-full blocks fallback write")

    async def send():
        gate._write_fault = storage_failure
        return success(completion=0)

    with pytest.raises(gate.LlmScopeStopped):
        await post(path, send)
    gate._write_fault = None
    assert failed == ["visible_replace_then_failure"]
    assert Path(path + ".outcome_pending").is_file()
    # Actual ledger replace may be visible as reconciled, but the durable
    # pending journal takes precedence for all readers and future dispatches.
    state = gate.ledger_state(path)
    assert state["accounted_nano"] == 1200 and state["inflight"] == 1
    assert state["control_state"]["circuit_open"]
    proc = child(path, "post")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"sent": False, "code": "scope_circuit_open"}


@pytest.mark.parametrize("stage", [
    "outcome_before_temp", "outcome_after_temp_write", "outcome_after_replace",
    "before_replace", "after_replace", "dir_fsync",
])
def test_process_exit_during_outcome_never_releases_unconfirmed_hold(tmp_path, stage):
    path = scope(tmp_path, max_posts=2)
    crashed = child(path, "outcome_crash:" + stage)
    assert crashed.returncode == 91, crashed.stderr
    restored = child(path, "state")
    assert restored.returncode == 0, restored.stderr
    state = json.loads(restored.stdout)
    assert state["accounted_nano"] == 1200 and state["inflight"] == 1
    assert state["control_state"]["attempts_total"] == 1
    attempt = child(path, "post")
    assert attempt.returncode == 0, attempt.stderr
    outcome = json.loads(attempt.stdout)
    assert outcome["sent"] is False
    assert outcome["code"] in ("scope_inflight", "scope_circuit_open")


async def test_journal_unlink_failure_is_persistent_stop_and_readonly_view(tmp_path, monkeypatch):
    path = scope(tmp_path, max_posts=2)
    pending = path + ".outcome_pending"
    real_unlink = os.unlink

    def fail_pending_unlink(name, *args, **kwargs):
        if os.fspath(name) == pending:
            raise OSError("fake journal unlink failure")
        return real_unlink(name, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", fail_pending_unlink)

    async def send():
        return success(completion=0)

    with pytest.raises(gate.LlmScopeStopped):
        await post(path, send)
    paths = [Path(path), Path(path + ".activated"), Path(pending)]
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]

    def no_write(*args, **kwargs):
        raise AssertionError("ledger_state must not repair or rewrite journal/ledger/marker")

    monkeypatch.setattr(gate, "_atomic_write", no_write)
    monkeypatch.setattr(gate, "_persist_ledger", no_write)
    monkeypatch.setattr(gate, "_write_activation_marker", no_write)
    for _ in range(2):
        state = gate.ledger_state(path)
        assert state["control_state"]["circuit_open"]
        assert state["accounted_nano"] == 1200 and state["inflight"] == 1
        assert state["control_state"]["attempts_total"] == 1
    assert [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths] == before
    proc = child(path, "post")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"sent": False, "code": "scope_circuit_open"}


@pytest.mark.parametrize("anomaly", [False, True])
async def test_post_unlink_directory_fsync_failure_cannot_lose_durable_outcome(tmp_path, anomaly):
    path = scope(tmp_path, max_posts=2)
    cleanup = []

    def fail_cleanup(stage):
        if stage == "outcome_cleanup_dir_fsync":
            cleanup.append(1)
            raise OSError("fake optional cleanup directory fsync failure")

    async def send():
        gate._write_fault = fail_cleanup
        result = success(completion=0)
        if anomaly:
            result["error"] = {"code": "fake_interrupted"}
        return result

    if anomaly:
        with pytest.raises(gate.LlmScopeStopped):
            await post(path, send)
    else:
        await post(path, send)
    gate._write_fault = None
    assert cleanup == [1]
    assert not Path(path + ".outcome_pending").exists()
    state = gate.ledger_state(path)
    assert state["control_state"]["attempts_total"] == 1
    if anomaly:
        # Error ledger was fsynced before cleanup; it remains an immutable stop.
        assert state["control_state"]["circuit_open"]
        assert state["accounted_nano"] == 1200
        proc = child(path, "post")
        assert json.loads(proc.stdout) == {"sent": False, "code": "scope_circuit_open"}
    else:
        # Success ledger was already fsynced, so this is trusted, NOT unknown.
        # A power-loss resurrection of the old pending file can only add a stop.
        assert not state["control_state"]["circuit_open"]
        assert state["accounted_nano"] == 0 and state["inflight"] == 0
        proc = child(path, "post")
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == {"sent": True}
