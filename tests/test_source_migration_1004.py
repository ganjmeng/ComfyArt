"""Offline same-scope source migration. Not a deployment ledger and not a live rollout.

The $0.003642744 / count 1/6 figures are the captured illustrative settlement,
reproduced through reserve and settle. They are not permission to edit the
deployment registry. Git SHAs name the reviewed protocol pair; the loaded file
hash is whatever this checkout actually hashes, because this migration changes
those bytes.
"""
import copy
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ComfyArt.bot import llm_activation_manifest as manifests
from ComfyArt.bot import llm_scope_activation as activation
from ComfyArt.bot import llm_usd_gate as gate
from test_llm_usd_gate import URL, _reserve_record, _route, _usage


OLD_SOURCE = "ab" * 32
AUTHORITY = "comfyart-pr1004-new-usd2-grant-v1"
RUNTIME_ID = "comfyart-pr1004-controlled-v1"
CAPTURED_NANO = 3_642_744
CAPTURED_RESERVE = 324_403_200
ROUTE = "https://api.deepseek.com/chat/completions"


def _captured_usage():
    return _usage(16054, 57, hit=4224, miss=11830)["usage"]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    gate.clear_authorized_scope()
    for name in list(os.environ):
        if name.endswith("_API_KEY") or name in ("OPENAI_TOKEN", "DEEPSEEK_TOKEN"):
            monkeypatch.delenv(name, raising=False)
    yield
    gate.clear_authorized_scope()
    gate._write_fault = None


def _candidate(scope, path, fingerprint):
    expected = manifests.ManifestContext(
        authorization_id=AUTHORITY, validation_run_id="offline-migration-fixture",
        scope_id=scope["scope_id"], canonical_absolute_ledger_path=path,
        policy_hash=activation.profile_hash(), evidence_hash=activation.evidence_hash(),
        sources=activation.source_evidence(), runtime_binding=("approved_runtime_sha256", fingerprint),
        risk_mode="risk_accepted_context_contract", tool_allowlist=activation.default_tools(),
        max_posts=6, route_url=ROUTE)
    candidate = {"version": 1, **asdict(expected)}
    candidate["sources"] = [{"url": url, "sha256": digest} for url, digest in expected.sources]
    candidate["runtime_binding"] = dict([expected.runtime_binding])
    candidate["tool_allowlist"] = list(expected.tool_allowlist)
    del candidate["max_posts"]
    candidate.update(scope_limits={"amount_nano": gate.TWO_DOLLAR_CEILING_NANO, "max_posts": 6, "max_inflight": 1},
                     model_pin={"model": "deepseek-flash", "version": gate.price_snapshot("deepseek-flash")["version"]},
                     price_snapshot=gate.price_snapshot("deepseek-flash"),
                     capabilities={"client_mcp": True, "images": True, "thinking": True})
    return candidate, expected


def _use_source(monkeypatch, source):
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", source)
    monkeypatch.setattr(activation, "_source_hash", lambda: source)


def bound(tmp_path, monkeypatch):
    """Bind a temporary scope as if the reviewed old source were loaded."""
    path = str((tmp_path / "scope.json").resolve())
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=6)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, OLD_SOURCE)
    old = activation.runtime_identity(str((tmp_path / "home").resolve()), RUNTIME_ID)
    candidate, expected = _candidate(scope, path, old.fingerprint)
    activation.activate_scope(candidate, expected=expected, runtime=old)
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    new = activation.runtime_identity(old.home, old.runtime_id)
    return {"path": path, "scope_id": scope["scope_id"], "old": old, "new": new, "candidate": candidate, "expected": expected}


def _binding(home):
    registry = json.loads(Path(home, activation._REGISTRY).read_text())
    return registry["authorities"][AUTHORITY]["binding"]


def settle_captured(env):
    record = _reserve_record(CAPTURED_RESERVE, "illustrative-captured-post")
    record["input_bound"] = 1_048_576
    record["max_output_tokens"] = 8192
    gate.reserve_nano(env["path"], nano=CAPTURED_RESERVE, record=record, runtime_binding=_binding(env["old"].home))
    assert gate.settle(env["path"], "illustrative-captured-post", _captured_usage())["actual_nano"] == CAPTURED_NANO


def migrate(env, **overrides):
    fields = dict(authorization_id=AUTHORITY, from_source_sha256=OLD_SOURCE, scope_id=env["scope_id"],
                  ledger_path=env["path"], reviewed_from_git=activation.REVIEWED_FROM_GIT,
                  reviewed_protocol_git=activation.REVIEWED_PROTOCOL_GIT)
    fields.update(overrides)
    return activation.migrate_source_fingerprint(env["new"], **fields)


def _files(env):
    home = Path(env["old"].home)
    paths = [Path(env["path"]), Path(env["path"] + ".activated"), home / activation._REGISTRY, home / (activation._REGISTRY + ".activated")]
    return {str(path): path.read_bytes() for path in paths}


def test_migration_preserves_illustrative_settlement_and_replaces_only_the_source(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    settle_captured(env)
    before = gate.ledger_state(env["path"])
    assert before["accounted_nano"] == CAPTURED_NANO
    assert before["control_state"] == {"attempts_total": 1, "circuit_open": False, "circuit_reason": "", "first_anomaly_id": ""}
    assert before["inflight"] == 0 and before["ceiling_nano"] == gate.TWO_DOLLAR_CEILING_NANO
    assert before["control_limits"]["max_posts"] == 6
    first = migrate(env)
    state = gate.ledger_state(env["path"])
    assert state == before
    binding = _binding(env["new"].home)
    assert binding["source_sha256"] == activation._source_hash()
    assert binding["runtime_fingerprint"] == env["new"].fingerprint
    assert binding["runtime_id"] == RUNTIME_ID and binding["home"] == env["new"].home
    assert binding["manifest"]["authorization_id"] == AUTHORITY
    assert binding["manifest"]["scope_id"] == env["scope_id"]
    assert binding["manifest"]["canonical_absolute_ledger_path"] == env["path"]
    assert binding["source_migration"]["reviewed_from_git"] == activation.REVIEWED_FROM_GIT
    assert binding["source_migration"]["reviewed_protocol_git"] == activation.REVIEWED_PROTOCOL_GIT
    assert binding["source_migration"]["from_source_sha256"] == OLD_SOURCE
    assert binding["source_migration"]["to_source_sha256"] == env["new"].source_sha256
    assert json.loads(Path(env["path"]).read_text())["runtime_activation"]["source_sha256"] == env["new"].source_sha256
    assert gate._read_marker(env["path"])["runtime_activation"] == json.loads(Path(env["path"]).read_text())["runtime_activation"]
    second = migrate(env)
    assert second["activation_digest"] == first["activation_digest"] and second["resumed"] is False
    assert gate.ledger_state(env["path"]) == before
    fresh = copy.deepcopy(binding["manifest"])
    with pytest.raises(gate.LlmBudgetBlocked, match="activation_authority_conflict"):
        activation.activate_scope(fresh, expected=activation._expected(fresh), runtime=env["new"])
    assert gate.ledger_state(env["path"]) == before


@pytest.mark.parametrize("field", ["from_source_sha256", "scope_id", "reviewed_from_git", "reviewed_protocol_git"])
def test_wrong_compare_writes_nothing(tmp_path, monkeypatch, field):
    env = bound(tmp_path, monkeypatch)
    settle_captured(env)
    before = _files(env)
    wrong = {field: "cd" * 32 if field == "from_source_sha256" else "0" * 40 if "git" in field else "other-scope"}
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        migrate(env, **wrong)
    assert _files(env) == before


def test_wrong_runtime_and_home_write_nothing(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    before = _files(env)
    other = activation.runtime_identity(env["new"].home, "other-runtime")
    env["new"] = other
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        migrate(env)
    elsewhere = activation.runtime_identity(str((tmp_path / "elsewhere").resolve()), RUNTIME_ID)
    env["new"] = elsewhere
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        migrate(env)
    assert _files(env) == before


@pytest.mark.parametrize("kind", ["reserved", "retained"])
def test_inflight_or_breaker_is_retained_and_migration_is_refused(tmp_path, monkeypatch, kind):
    env = bound(tmp_path, monkeypatch)
    record = _reserve_record(1200, "hold")
    gate.reserve_nano(env["path"], nano=1200, record=record, runtime_binding=_binding(env["old"].home))
    if kind == "retained":
        gate.retain(env["path"], "hold", "synthetic_unknown")
    before = gate.ledger_state(env["path"])
    files = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_state_unsafe"):
        migrate(env)
    assert gate.ledger_state(env["path"]) == before
    assert _files(env) == files
    assert before["control_state"]["circuit_open"] is (kind == "retained")
    assert before["control_state"]["attempts_total"] == 1


def test_tampered_digest_is_not_rewritten(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    path = Path(env["old"].home, activation._REGISTRY)
    registry = json.loads(path.read_text())
    registry["authorities"][AUTHORITY]["digest"] = "0" * 64
    path.write_text(json.dumps(registry))
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_state_unsafe"):
        migrate(env)
    assert json.loads(Path(env["path"]).read_text())["runtime_activation"]["source_sha256"] == OLD_SOURCE


def test_old_loaded_source_cannot_send_after_migration(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    settle_captured(env)
    before = gate.ledger_state(env["path"])
    migrate(env)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, OLD_SOURCE)
    stale = activation.runtime_identity(env["old"].home, RUNTIME_ID)
    with pytest.raises(gate.LlmBudgetBlocked, match="activation_binding_mismatch"):
        activation.active_binding(stale, route=_route(), url=URL)
    with pytest.raises(gate.LlmBudgetBlocked, match="activation_binding_mismatch"):
        activation.reserve_for_runtime(stale, path=env["path"], nano=1200, record=_reserve_record(1200, "stale"),
                                       url=ROUTE, tools=["skill"])
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    current = activation.runtime_identity(env["new"].home, RUNTIME_ID)
    found = activation.active_binding(current, route=_route(), url=URL)
    assert found["source_sha256"] == current.source_sha256
    assert gate.ledger_state(env["path"]) == before


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
    result = a.migrate_source_fingerprint(
        runtime, authorization_id=payload["authorization_id"], from_source_sha256=payload["from_source"],
        scope_id=payload["scope_id"], ledger_path=payload["ledger"],
        reviewed_from_git=a.REVIEWED_FROM_GIT, reviewed_protocol_git=a.REVIEWED_PROTOCOL_GIT)
    print(json.dumps({"ok": True, "resumed": result["resumed"], "state": g.ledger_state(payload["ledger"])}), flush=True)
except g.LlmBudgetBlocked as exc:
    print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}), flush=True)
"""


def _payload(env, **extra):
    return dict(home=env["new"].home, runtime_id=RUNTIME_ID, authorization_id=AUTHORITY, from_source=OLD_SOURCE,
                scope_id=env["scope_id"], ledger=env["path"], **extra)


def _spawn(payload):
    return subprocess.Popen([sys.executable, "-c", CHILD, str(Path(__file__).parent), json.dumps(payload)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _finish(child, code=0):
    stdout, stderr = child.communicate(timeout=30)
    assert child.returncode == code, (stdout, stderr)
    if code != 0:
        return None
    return json.loads(stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("stage", ["migration_pending_after_dir_fsync", "after_dir_fsync", "marker_after_dir_fsync", "migration_active_after_replace"])
def test_interrupted_migration_resumes_without_reset(tmp_path, monkeypatch, stage):
    env = bound(tmp_path, monkeypatch)
    settle_captured(env)
    before = gate.ledger_state(env["path"])
    _finish(_spawn(_payload(env, crash_stage=stage)), 93)
    if stage == "migration_active_after_replace":
        assert activation.active_binding(env["new"], route=_route(), url=URL)["source_sha256"] == env["new"].source_sha256
    else:
        with pytest.raises(gate.LlmBudgetBlocked, match="activation_not_committed"):
            activation.active_binding(env["new"], route=_route(), url=URL)
    recovered = migrate(env)
    assert recovered["resumed"] is (stage != "migration_active_after_replace")
    assert gate.ledger_state(env["path"]) == before
    again = migrate(env)
    assert again["resumed"] is False and gate.ledger_state(env["path"]) == before


def test_concurrent_migration_keeps_one_authority_and_the_settlement(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    settle_captured(env)
    before = gate.ledger_state(env["path"])
    with activation._registry_lock(env["new"].home):
        children = [_spawn(_payload(env, ready=True)) for _ in range(2)]
        for child in children:
            assert child.stdout.readline().strip() == "READY"
    results = [_finish(child) for child in children]
    assert [row["ok"] for row in results] == [True, True]
    assert all(row["state"] == before for row in results)
    registry = json.loads(Path(env["new"].home, activation._REGISTRY).read_text())
    assert list(registry["authorities"]) == [AUTHORITY]
    assert registry["runtimes"] == {RUNTIME_ID: AUTHORITY}
    assert registry["authorities"][AUTHORITY]["status"] == "active"


# Loaded file hash of deployed commit 0b73f5db. Not a git SHA.
DEPLOYED_0B73_SOURCE = "79e40ca0196cbab67c018755e1e36b7010b45a8a8b70d1c12717bc07d4d4bd24"


def test_migration_hop_from_deployed_0b73_keeps_the_bcc804bc_pair(tmp_path, monkeypatch):
    path = str((tmp_path / "scope.json").resolve())
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=6)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, DEPLOYED_0B73_SOURCE)
    old = activation.runtime_identity(str((tmp_path / "home").resolve()), RUNTIME_ID)
    candidate, expected = _candidate(scope, path, old.fingerprint)
    activation.activate_scope(candidate, expected=expected, runtime=old)
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    new = activation.runtime_identity(old.home, old.runtime_id)
    env = {"path": path, "scope_id": scope["scope_id"], "old": old, "new": new}
    settle_captured(env)
    before = gate.ledger_state(path)
    new_hash = activation._source_hash()
    assert new_hash != DEPLOYED_0B73_SOURCE
    files = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git=activation.REVIEWED_LIVE_GIT, reviewed_protocol_git="0" * 40)
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git="0b73f5dbf909cba9578dcc4129bafb3d64c10f99",
            reviewed_protocol_git="69dd1c334173aa8860251ae939535464050d8ef9")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git="0b73f5dbf909cba9578dcc4129bafb3d64c10f99",
            reviewed_protocol_git="6cc69e544cb73ec425c75f92df47181ef882f84d")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git="0b73f5dbf909cba9578dcc4129bafb3d64c10f99",
            reviewed_protocol_git="325650381764923a82314777a03fd6cb52d2871c")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git="0b73f5dbf909cba9578dcc4129bafb3d64c10f99",
            reviewed_protocol_git="8a9593797f84d9afbb675b682cd82066a3ddf703")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git="0b73f5dbf909cba9578dcc4129bafb3d64c10f99",
            reviewed_protocol_git="93d7aa388f1bef7d3668e4c2a6936d653dab4a23")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git="0b73f5dbf909cba9578dcc4129bafb3d64c10f99",
            reviewed_protocol_git=activation.REVIEWED_LOGIC_GIT)
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git="0b73f5dbf909cba9578dcc4129bafb3d64c10f99",
            reviewed_protocol_git=activation.REVIEWED_SETUP_GIT)
    assert _files(env) == files
    migrated = activation.migrate_source_fingerprint(
        new, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
        scope_id=scope["scope_id"], ledger_path=path,
        reviewed_from_git=activation.REVIEWED_LIVE_GIT, reviewed_protocol_git=activation.REVIEWED_EXTERNAL_GIT)
    binding = _binding(old.home)
    provenance = binding["source_migration"]
    assert migrated["ok"] is True
    assert binding["source_sha256"] == new_hash
    assert provenance["from_source_sha256"] == DEPLOYED_0B73_SOURCE
    assert provenance["to_source_sha256"] == new_hash
    assert provenance["reviewed_from_git"] == "0b73f5dbf909cba9578dcc4129bafb3d64c10f99"
    assert provenance["reviewed_protocol_git"] == "bcc804bc13f3fa684c0ecf5547ac71023163da09"
    assert provenance["reviewed_protocol_git"] == activation.REVIEWED_EXTERNAL_GIT
    assert gate.ledger_state(path) == before
    assert before["accounted_nano"] == CAPTURED_NANO


# Loaded file hash of commit bcc804bc. Not a git SHA.
BCC804_SOURCE = "89ec805041e30abd5237c10f7fd4c65ca9b55f9e3e0c10a32f00ed27aeaaeba0"


def test_migration_hop_from_bcc804bc_to_external_resolve_commit(tmp_path, monkeypatch):
    path = str((tmp_path / "scope.json").resolve())
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=6)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, BCC804_SOURCE)
    old = activation.runtime_identity(str((tmp_path / "home").resolve()), RUNTIME_ID)
    candidate, expected = _candidate(scope, path, old.fingerprint)
    activation.activate_scope(candidate, expected=expected, runtime=old)
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    new = activation.runtime_identity(old.home, old.runtime_id)
    env = {"path": path, "scope_id": scope["scope_id"], "old": old, "new": new}
    settle_captured(env)
    before = gate.ledger_state(path)
    files = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git=activation.REVIEWED_EXTERNAL_GIT, reviewed_protocol_git="0" * 40)
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git=activation.REVIEWED_EXTERNAL_GIT,
            reviewed_protocol_git="6cc69e544cb73ec425c75f92df47181ef882f84d")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git=activation.REVIEWED_EXTERNAL_GIT,
            reviewed_protocol_git="325650381764923a82314777a03fd6cb52d2871c")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git=activation.REVIEWED_EXTERNAL_GIT,
            reviewed_protocol_git="8a9593797f84d9afbb675b682cd82066a3ddf703")
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        activation.migrate_source_fingerprint(
            new, authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
            scope_id=scope["scope_id"], ledger_path=path,
            reviewed_from_git=activation.REVIEWED_EXTERNAL_GIT,
            reviewed_protocol_git="93d7aa388f1bef7d3668e4c2a6936d653dab4a23")
    assert _files(env) == files
    migrated = activation.migrate_source_fingerprint(
        new, authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
        scope_id=scope["scope_id"], ledger_path=path,
        reviewed_from_git=activation.REVIEWED_EXTERNAL_GIT, reviewed_protocol_git=activation.REVIEWED_LOGIC_GIT)
    provenance = _binding(old.home)["source_migration"]
    assert migrated["ok"] is True
    assert provenance["from_source_sha256"] == BCC804_SOURCE
    assert provenance["to_source_sha256"] == activation._source_hash()
    assert provenance["reviewed_from_git"] == "bcc804bc13f3fa684c0ecf5547ac71023163da09"
    assert provenance["reviewed_protocol_git"] == "9c0a480753f6f9856fd137067e9026d20a425c3a"
    assert provenance["reviewed_protocol_git"] == activation.REVIEWED_LOGIC_GIT
    assert ("0b73f5dbf909cba9578dcc4129bafb3d64c10f99", "bcc804bc13f3fa684c0ecf5547ac71023163da09") in activation.REVIEWED_GIT_PAIRS
    assert ("bcc804bc13f3fa684c0ecf5547ac71023163da09", "8a9593797f84d9afbb675b682cd82066a3ddf703") not in activation.REVIEWED_GIT_PAIRS
    assert ("0b73f5dbf909cba9578dcc4129bafb3d64c10f99", "9c0a480753f6f9856fd137067e9026d20a425c3a") not in activation.REVIEWED_GIT_PAIRS
    assert ("bcc804bc13f3fa684c0ecf5547ac71023163da09", "d83072c8a8bddf726fc9e68f94f6550d3a3823de") in activation.REVIEWED_GIT_PAIRS
    assert ("9c0a480753f6f9856fd137067e9026d20a425c3a", "d83072c8a8bddf726fc9e68f94f6550d3a3823de") in activation.REVIEWED_GIT_PAIRS
    assert ("0b73f5dbf909cba9578dcc4129bafb3d64c10f99", "d83072c8a8bddf726fc9e68f94f6550d3a3823de") not in activation.REVIEWED_GIT_PAIRS
    assert gate.ledger_state(path) == before


def test_migration_hop_from_finals_commit_to_setup_card_commit(tmp_path, monkeypatch):
    env = bound(tmp_path, monkeypatch)
    before = gate.ledger_state(env["path"])
    files = _files(env)
    with pytest.raises(gate.LlmBudgetBlocked, match="migration_not_authorized"):
        migrate(env, reviewed_from_git=activation.REVIEWED_FINALS_GIT, reviewed_protocol_git="0" * 40)
    assert _files(env) == files
    migrated = migrate(env, reviewed_from_git=activation.REVIEWED_FINALS_GIT,
                       reviewed_protocol_git=activation.REVIEWED_SETUP_GIT)
    provenance = _binding(env["new"].home)["source_migration"]
    assert migrated["ok"] is True
    assert provenance["reviewed_from_git"] == "9c0a480753f6f9856fd137067e9026d20a425c3a"
    assert provenance["reviewed_protocol_git"] == "d83072c8a8bddf726fc9e68f94f6550d3a3823de"
    assert provenance["reviewed_protocol_git"] == activation.REVIEWED_SETUP_GIT
    state = gate.ledger_state(env["path"])
    assert state["accounted_nano"] == before["accounted_nano"]
    assert state["ceiling_nano"] == before["ceiling_nano"]


DIRECT_FROM = "bcc804bc13f3fa684c0ecf5547ac71023163da09"
DIRECT_TO = "d83072c8a8bddf726fc9e68f94f6550d3a3823de"


def _live_bcc_binding(tmp_path, monkeypatch):
    """The deployed binding: source hash of bcc804bc, provenance exactly 0b73 -> bcc804bc."""
    path = str((tmp_path / "scope.json").resolve())
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=6)
    real_loaded, real_hash = activation._LOADED_SOURCE_HASH, activation._source_hash
    _use_source(monkeypatch, DEPLOYED_0B73_SOURCE)
    old = activation.runtime_identity(str((tmp_path / "home").resolve()), RUNTIME_ID)
    candidate, expected = _candidate(scope, path, old.fingerprint)
    activation.activate_scope(candidate, expected=expected, runtime=old)
    _use_source(monkeypatch, BCC804_SOURCE)
    deployed = activation.runtime_identity(old.home, old.runtime_id)
    activation.migrate_source_fingerprint(
        deployed, authorization_id=AUTHORITY, from_source_sha256=DEPLOYED_0B73_SOURCE,
        scope_id=scope["scope_id"], ledger_path=path,
        reviewed_from_git=activation.REVIEWED_LIVE_GIT, reviewed_protocol_git=activation.REVIEWED_EXTERNAL_GIT)
    monkeypatch.setattr(activation, "_LOADED_SOURCE_HASH", real_loaded)
    monkeypatch.setattr(activation, "_source_hash", real_hash)
    new = activation.runtime_identity(old.home, old.runtime_id)
    return {"path": path, "scope_id": scope["scope_id"], "old": old, "new": new}


def _direct_hop(env):
    return activation.migrate_source_fingerprint(
        env["new"], authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
        scope_id=env["scope_id"], ledger_path=env["path"],
        reviewed_from_git=DIRECT_FROM, reviewed_protocol_git=DIRECT_TO)


def test_direct_hop_from_deployed_0b73_bcc804_binding(tmp_path, monkeypatch):
    env = _live_bcc_binding(tmp_path, monkeypatch)
    prior = _binding(env["new"].home)["source_migration"]
    assert (prior["reviewed_from_git"], prior["reviewed_protocol_git"]) == (
        "0b73f5dbf909cba9578dcc4129bafb3d64c10f99", DIRECT_FROM)
    assert _binding(env["new"].home)["source_sha256"] == BCC804_SOURCE
    settle_captured(env)
    before = gate.ledger_state(env["path"])
    migrated = _direct_hop(env)
    binding = _binding(env["new"].home)
    provenance = binding["source_migration"]
    assert migrated["ok"] is True and migrated["resumed"] is False
    assert binding["source_sha256"] == activation._source_hash()
    assert (provenance["reviewed_from_git"], provenance["reviewed_protocol_git"]) == (DIRECT_FROM, DIRECT_TO)
    assert provenance["from_source_sha256"] == BCC804_SOURCE
    assert provenance["to_source_sha256"] == activation._source_hash()
    assert type(provenance) is dict
    assert activation.REVIEWED_GIT_PAIRS[3] == (DIRECT_FROM, "9c0a480753f6f9856fd137067e9026d20a425c3a")
    assert activation.REVIEWED_GIT_PAIRS[4] == ("9c0a480753f6f9856fd137067e9026d20a425c3a", DIRECT_TO)
    assert (DIRECT_FROM, DIRECT_TO) == activation.REVIEWED_GIT_PAIRS[5]
    assert ("0b73f5dbf909cba9578dcc4129bafb3d64c10f99", DIRECT_TO) not in activation.REVIEWED_GIT_PAIRS
    assert gate.ledger_state(env["path"]) == before


def test_direct_hop_repeat_writes_no_new_audit_row(tmp_path, monkeypatch):
    env = _live_bcc_binding(tmp_path, monkeypatch)
    settle_captured(env)
    first = _direct_hop(env)
    files = _files(env)
    provenance = copy.deepcopy(_binding(env["new"].home)["source_migration"])
    ledger = json.loads(Path(env["path"]).read_text())
    audits = {key: copy.deepcopy(ledger.get(key)) for key in ("limit_extension", "ceiling_extension")}
    second = _direct_hop(env)
    assert second["ok"] is True and second["resumed"] is False
    assert second["activation_digest"] == first["activation_digest"]
    assert _files(env) == files
    again = _binding(env["new"].home)["source_migration"]
    assert again == provenance
    assert (again["reviewed_from_git"], again["reviewed_protocol_git"]) == (DIRECT_FROM, DIRECT_TO)
    reread = json.loads(Path(env["path"]).read_text())
    assert {key: reread.get(key) for key in ("limit_extension", "ceiling_extension")} == audits


LOGIC_TO = "d6b8047fb9f38a57e2f8400f71f9b360ccd6aafc"


def _logic_hop(env):
    return activation.migrate_source_fingerprint(
        env["new"], authorization_id=AUTHORITY, from_source_sha256=BCC804_SOURCE,
        scope_id=env["scope_id"], ledger_path=env["path"],
        reviewed_from_git=DIRECT_FROM, reviewed_protocol_git=LOGIC_TO)


def test_direct_hop_from_deployed_binding_to_controlled_stop_commit(tmp_path, monkeypatch):
    env = _live_bcc_binding(tmp_path, monkeypatch)
    prior = _binding(env["new"].home)["source_migration"]
    assert (prior["reviewed_from_git"], prior["reviewed_protocol_git"]) == (
        "0b73f5dbf909cba9578dcc4129bafb3d64c10f99", DIRECT_FROM)
    settle_captured(env)
    before = gate.ledger_state(env["path"])
    migrated = _logic_hop(env)
    provenance = _binding(env["new"].home)["source_migration"]
    assert migrated["ok"] is True and migrated["resumed"] is False
    assert (provenance["reviewed_from_git"], provenance["reviewed_protocol_git"]) == (DIRECT_FROM, LOGIC_TO)
    assert provenance["from_source_sha256"] == BCC804_SOURCE
    assert provenance["to_source_sha256"] == activation._source_hash()
    assert activation.REVIEWED_GIT_PAIRS[5] == (DIRECT_FROM, DIRECT_TO)
    assert activation.REVIEWED_GIT_PAIRS[6] == (DIRECT_FROM, LOGIC_TO)
    assert gate.ledger_state(env["path"]) == before


def test_controlled_stop_hop_repeat_writes_no_new_audit_row(tmp_path, monkeypatch):
    env = _live_bcc_binding(tmp_path, monkeypatch)
    settle_captured(env)
    first = _logic_hop(env)
    files = _files(env)
    provenance = copy.deepcopy(_binding(env["new"].home)["source_migration"])
    ledger = json.loads(Path(env["path"]).read_text())
    audits = {key: copy.deepcopy(ledger.get(key)) for key in ("limit_extension", "ceiling_extension")}
    second = _logic_hop(env)
    assert second["ok"] is True and second["resumed"] is False
    assert second["activation_digest"] == first["activation_digest"]
    assert _files(env) == files
    again = _binding(env["new"].home)["source_migration"]
    assert again == provenance
    assert (again["reviewed_from_git"], again["reviewed_protocol_git"]) == (DIRECT_FROM, LOGIC_TO)
    reread = json.loads(Path(env["path"]).read_text())
    assert {key: reread.get(key) for key in ("limit_extension", "ceiling_extension")} == audits
