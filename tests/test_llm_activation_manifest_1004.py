"""Manifest interface only. Synthetic review identities and temporary fake scopes."""
from dataclasses import asdict, replace
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ComfyArt.bot import llm_activation_manifest as manifest, llm_usd_gate as gate
from test_llm_scope_controls_1004 import post, success
from test_llm_usd_gate import _text


@pytest.fixture
def candidate(tmp_path):
    # Synthetic hashes are fixture identities, never provider evidence/approval.
    path = str((tmp_path / "scope.json").resolve())
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=2)
    expected = manifest.ManifestContext(
        authorization_id="test-only-authorization", validation_run_id="test-only-run",
        scope_id=scope["scope_id"], canonical_absolute_ledger_path=path,
        policy_hash="a" * 64, evidence_hash="b" * 64,
        sources=((gate.CHAT_URL, "c" * 64), (gate.VISION_URL, "d" * 64)),
        runtime_binding=("reviewed_sha", "e" * 40), risk_mode="risk_accepted_context_contract",
        tool_allowlist=("memory_add", "mcp_screenshot"), max_posts=2,
        route_url="https://api.deepseek.com/chat/completions")
    c = {"version": 1, **asdict(expected)}
    c["sources"] = [{"url": u, "sha256": h} for u, h in expected.sources]
    c["runtime_binding"] = dict([expected.runtime_binding])
    c["tool_allowlist"] = list(expected.tool_allowlist)
    del c["max_posts"]
    c.update(scope_limits={"amount_nano": gate.TWO_DOLLAR_CEILING_NANO, "max_posts": 2, "max_inflight": 1},
             model_pin={"model": "deepseek-flash", "version": gate.price_snapshot("deepseek-flash")["version"]},
             price_snapshot=gate.price_snapshot("deepseek-flash"),
             capabilities={"client_mcp": True, "images": True, "thinking": True})
    return c, expected


def bytes_state(path):
    return {str(p): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in (Path(path), Path(path + ".activated")) if p.exists()}


def test_validation_receipt_never_activates_or_mutates_scope(candidate):
    c, expected = candidate
    before, bound = bytes_state(expected.canonical_absolute_ledger_path), gate._bound_ledger_path
    result = manifest.validate_existing_scope(c, expected=expected)
    assert result.scope_id == expected.scope_id
    assert len(result.manifest_sha256) == 64
    assert gate._bound_ledger_path == bound
    assert bytes_state(expected.canonical_absolute_ledger_path) == before
    assert not isinstance(result, gate.Bound)


@pytest.mark.parametrize("key", ["authorization_id", "validation_run_id", "scope_id", "policy_hash",
                                  "evidence_hash", "runtime_binding", "route_url", "sources",
                                  "model_pin", "price_snapshot", "scope_limits", "capabilities",
                                  "tool_allowlist", "risk_mode"])
def test_required_fields_default_deny(candidate, key):
    c, expected = candidate
    del c[key]
    with pytest.raises(manifest.ManifestInvalid):
        manifest.validate_existing_scope(c, expected=expected)


@pytest.mark.parametrize("patch", [
    {"version": True}, {"authorization_id": "different"}, {"validation_run_id": "different"},
    {"scope_id": "different"}, {"policy_hash": "z" * 64}, {"evidence_hash": "f" * 64},
    {"route_url": "https://api.deepseek.com/chat/completions?override=1"},
    {"route_url": "https://other.invalid/chat/completions"},
    {"risk_mode": "approved"}, {"runtime_binding": {"reviewed_sha": "f" * 40}},
    {"runtime_binding": {"reviewed_sha": "e" * 40, "approved_runtime_sha256": "f" * 64}},
    {"tool_allowlist": []}, {"tool_allowlist": ["memory_add"]},
    {"tool_allowlist": ["memory_add", "mcp_screenshot", "deepseek_web_search"]},
    {"capabilities": {"client_mcp": True, "images": False, "thinking": True}},
    {"capabilities": {"client_mcp": 1, "images": True, "thinking": True}},
    {"scope_limits": {"amount_nano": 4_000_000_000, "max_posts": 2, "max_inflight": 1}},
    {"scope_limits": {"amount_nano": 2_000_000_000, "max_posts": True, "max_inflight": 1}},
    {"scope_limits": {"amount_nano": 2_000_000_000, "max_posts": 7, "max_inflight": 1}},
    {"scope_limits": {"amount_nano": 2_000_000_000, "max_posts": 2, "max_inflight": True}},
    {"scope_limits": {"amount_nano": 2_000_000_000, "max_posts": 2, "max_inflight": 2}},
    {"expires_at": 100}, {"expires_at": True}, {"expires_at": "later"},
    {"unexpected_send_permission": True},
])
def test_malformed_mismatched_or_expired_manifest_never_changes_funds(candidate, patch):
    c, expected = candidate
    before = bytes_state(expected.canonical_absolute_ledger_path)
    c.update(copy.deepcopy(patch))
    with pytest.raises(manifest.ManifestInvalid):
        manifest.validate_existing_scope(c, expected=expected, now=100)
    assert bytes_state(expected.canonical_absolute_ledger_path) == before


def test_optional_expiry_and_alternative_review_binding(candidate):
    c, expected = candidate
    expected = replace(expected, runtime_binding=("approved_runtime_sha256", "f" * 64))
    c["runtime_binding"] = dict([expected.runtime_binding])
    c["expires_at"] = 101
    assert manifest.validate_existing_scope(c, expected=expected, now=100)
    with pytest.raises(manifest.ManifestInvalid, match="expires_at"):
        manifest.validate_manifest(c, expected=expected, now=101)


@pytest.mark.parametrize("problem", ["missing", "empty", "different_scope", "different_limit", "legacy"])
def test_existing_scope_mismatch_has_no_creation_fallback_or_extra_authority(candidate, problem):
    c, expected = candidate
    path = expected.canonical_absolute_ledger_path
    if problem == "missing":
        Path(path).unlink()
    elif problem == "empty":
        Path(path).write_text("")
    else:
        data = json.loads(Path(path).read_text())
        if problem == "different_scope":
            data["scope_id"] = "not-reviewed"
        elif problem == "different_limit":
            data["control_limits"]["max_posts"] = 1
        else:
            del data["control_limits"], data["control_state"]
        Path(path).write_text(json.dumps(data))
    before = bytes_state(path)
    with pytest.raises(manifest.ManifestInvalid):
        manifest.validate_existing_scope(c, expected=expected)
    assert bytes_state(path) == before


async def test_restart_validation_preserves_attempts_and_breaker(candidate):
    c, expected = candidate
    async def send():
        return success()
    await post(expected.canonical_absolute_ledger_path, send)
    assert manifest.validate_existing_scope(json.loads(json.dumps(c)), expected=expected)
    before = gate.ledger_state(expected.canonical_absolute_ledger_path)
    assert before["control_state"]["attempts_total"] == 1
    async def unknown():
        raise TimeoutError("fake transport")
    with pytest.raises(gate.LlmScopeStopped):
        await post(expected.canonical_absolute_ledger_path, unknown)
    stopped = bytes_state(expected.canonical_absolute_ledger_path)
    with pytest.raises(manifest.ManifestInvalid, match="existing_scope_stopped"):
        manifest.validate_existing_scope(json.loads(json.dumps(c)), expected=expected)
    assert bytes_state(expected.canonical_absolute_ledger_path) == stopped
    assert gate.ledger_state(expected.canonical_absolute_ledger_path)["control_state"]["attempts_total"] == 2


async def test_valid_manifest_cannot_bypass_production_input_or_structural_guards(candidate):
    c, expected = candidate
    manifest.validate_existing_scope(c, expected=expected)
    calls = []
    async def send():
        calls.append(1)
        return success()
    bodies = [_text(max_tokens=1), {**_text(max_tokens=1), "tools": [{"type": "deepseek_web_search"}]}]
    for body in bodies:
        with pytest.raises(gate.LlmBudgetBlocked):
            await post(expected.canonical_absolute_ledger_path, send, body=body, bound_fn=None)
    assert calls == []
    assert gate.ledger_state(expected.canonical_absolute_ledger_path)["control_state"]["attempts_total"] == 0


@pytest.mark.parametrize("mutation", ["price_bool", "price_float", "source_hash", "source_host", "source_duplicate", "source_missing", "source_bad_shape", "tool_duplicate", "path_relative", "path_alias", "path_second_scope", "path_nul"])
def test_schema_identity_edge_cases(candidate, tmp_path, mutation):
    c, expected = candidate
    before = bytes_state(expected.canonical_absolute_ledger_path)
    if mutation == "price_bool":
        c["price_snapshot"]["input_miss_peak_nano"] = True
    elif mutation == "price_float":
        c["price_snapshot"]["input_miss_peak_nano"] = 300.0
    elif mutation == "source_hash":
        c["sources"][0]["sha256"] = "f" * 64
    elif mutation == "source_host":
        c["sources"][0]["url"] = "https://other.invalid/source"
    elif mutation == "source_duplicate":
        c["sources"].append(copy.deepcopy(c["sources"][0]))
    elif mutation == "source_missing":
        c["sources"] = []
    elif mutation == "source_bad_shape":
        c["sources"][0] = None
    elif mutation == "tool_duplicate":
        c["tool_allowlist"].append(c["tool_allowlist"][0])
    elif mutation == "path_relative":
        c["canonical_absolute_ledger_path"] = "scope.json"
    elif mutation == "path_nul":
        c["canonical_absolute_ledger_path"] = "/invalid\x00path"
    elif mutation == "path_alias":
        alias = tmp_path / "alias.json"
        alias.symlink_to(expected.canonical_absolute_ledger_path)
        c["canonical_absolute_ledger_path"] = str(alias)
    else:
        other = str(tmp_path / "second.json")
        gate.open_authorized_scope(other, gate.TWO_DOLLAR_CEILING_NANO, max_posts=2)
        c["canonical_absolute_ledger_path"] = other
    with pytest.raises(manifest.ManifestInvalid):
        manifest.validate_existing_scope(c, expected=expected)
    assert bytes_state(expected.canonical_absolute_ledger_path) == before


async def test_fresh_interpreter_validates_same_scope_without_new_money(candidate, tmp_path):
    c, expected = candidate
    async def send():
        return success()
    await post(expected.canonical_absolute_ledger_path, send)
    inputs = tmp_path / "manifest-fixture.json"
    inputs.write_text(json.dumps({"candidate": c, "expected": asdict(expected)}))
    before = bytes_state(expected.canonical_absolute_ledger_path)
    program = """
import json,sys,types
from pathlib import Path
# The tests directory is argv[1]. Load only the two offline modules. Importing
# conftest pulls ComfyArt/__init__ and bot/__init__ (the whole agent, server,
# and provider stack). Under the gate that import did not finish inside 30s;
# this check does not need it. The parent process's ledger binding stays out.
repo=Path(sys.argv[1]).resolve().parent
sys.path.insert(0,str(repo.parent))
for name,path in (('ComfyArt',repo),('ComfyArt.bot',repo/'bot')):
    pkg=types.ModuleType(name)
    pkg.__path__=[str(path)]
    pkg.__package__=name
    sys.modules.setdefault(name,pkg)
from ComfyArt.bot import llm_activation_manifest as m, llm_usd_gate as gate
d=json.loads(Path(sys.argv[2]).read_text());e=d['expected']
e['sources']=tuple(tuple(p) for p in e['sources'])
e['runtime_binding']=tuple(e['runtime_binding']);e['tool_allowlist']=tuple(e['tool_allowlist'])
r=m.validate_existing_scope(d['candidate'],expected=m.ManifestContext(**e))
s=gate.ledger_state(r.canonical_absolute_ledger_path)
print(json.dumps({'manifest_sha256':r.manifest_sha256,'scope_id':r.scope_id,'attempts':s['control_state']['attempts_total'],'accounted_nano':s['accounted_nano'],'bound':gate._bound_ledger_path}))
"""
    child = subprocess.run([sys.executable, "-c", program, str(Path(__file__).resolve().parent), str(inputs)],
                           capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    observed = json.loads(child.stdout.splitlines()[-1])
    assert observed == {"manifest_sha256": manifest.validate_manifest(c, expected=expected).manifest_sha256,
                        "scope_id": expected.scope_id, "attempts": 1, "accounted_nano": 1200, "bound": None}
    assert bytes_state(expected.canonical_absolute_ledger_path) == before


def test_receipt_uses_private_snapshot_not_mutating_candidate(candidate, monkeypatch):
    c, expected = candidate
    original = copy.deepcopy(c)
    realpath = manifest.os.path.realpath
    def changing_path(path):
        c["scope_id"] = "changed-during-validation"
        return realpath(path)
    monkeypatch.setattr(manifest.os.path, "realpath", changing_path)
    receipt = manifest.validate_manifest(c, expected=expected)
    assert receipt.scope_id == expected.scope_id
    assert receipt.manifest_sha256 == __import__("hashlib").sha256(
        json.dumps(original, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
