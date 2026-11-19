"""Explicit durable activation for ONE authority -> ledger + configured runtime.

Nothing calls activate_scope automatically. Runtime selection is read-only and
requires an existing committed claim. The registry is shared by all workers in
one canonical COMFYART_HOME (fallback: existing ComfyArt system-user directory).
COMFYART_RUNTIME_ID is an explicit stable deployment/server name, NOT a PID or a
shared hardcoded identity. No runtime ID means the installed path stays strict.
No credentials, network, new funds, recovery/reset API or anti-admin seal here.
The shared registry namespace is deployment home, never runtime_id. An unchanged
approved manifest cannot be remapped to a different home/runtime fingerprint.
An administrator replacing the configuration, reviewed manifest or all persistent
files is outside these local consistency guarantees (not a global grant seal).
"""
from __future__ import annotations

import contextlib
from contextvars import ContextVar
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid
from urllib.parse import urlsplit
from dataclasses import dataclass

from . import llm_usd_gate as gate
from . import llm_activation_manifest as manifests
from . import llm_input_envelope as envelope

_AUXILIARY = ContextVar("llm_designated_auxiliary", default=None)
_AUX_NO_REDIRECT = ContextVar("llm_aux_no_redirect", default=False)


@contextlib.contextmanager
def auxiliary_request(purpose, method, url, body):
    # Only explicit catalog/MCP helper call sites create this context. A model
    # payload cannot select its own purpose by URL substring or JSON fields.
    token = _AUXILIARY.set((purpose, method, str(url), _digest(body)))
    try:
        yield
    finally:
        _AUXILIARY.reset(token)


@contextlib.contextmanager
def auxiliary_no_redirects():
    token = _AUX_NO_REDIRECT.set(True)
    try:
        yield
    finally:
        _AUX_NO_REDIRECT.reset(token)


def no_auxiliary_redirects():
    return _AUX_NO_REDIRECT.get()


def auxiliary_designation():
    return _AUXILIARY.get() is not None


def validate_auxiliary(binding, method, url, body):
    designation = _AUXILIARY.get()
    if designation is None:
        _fail("activation_aux_invalid", "purpose")
    purpose, bound_method, endpoint, digest = designation
    if (method, str(url), _digest(body)) != (bound_method, endpoint, digest):
        _fail("activation_aux_invalid", "designated_method/endpoint/body")
    m = binding["manifest"]
    if purpose == "catalog":
        if method != "GET" or str(url) != m["route_url"].removesuffix("/chat/completions") + "/models" or body is not None:
            _fail("activation_aux_invalid", "catalog_origin/method/schema")
        return
    try:
        parsed = urlsplit(str(url))
        valid_url = (parsed.scheme in ("http", "https") and bool(parsed.hostname) and parsed.username is None
                     and parsed.password is None and not parsed.fragment and parsed.hostname != "api.deepseek.com")
    except ValueError:
        valid_url = False
    if (not valid_url or method != "POST" or type(body) is not dict
            or set(body) != {"jsonrpc", "id", "method", "params"} or body["jsonrpc"] != "2.0"
            or type(body["id"]) not in (str, int) or type(body["params"]) is not dict):
        _fail("activation_aux_invalid", "mcp_origin/method/schema")
    if purpose == "mcp_list" and body["method"] == "tools/list" and body["params"] == {}:
        return
    params = body["params"]
    if (purpose == "mcp_call" and body["method"] == "tools/call" and set(params) == {"name", "arguments"}
            and params["name"] in m["tool_allowlist"] and type(params["arguments"]) is dict):
        return
    _fail("activation_aux_invalid", "mcp_purpose/schema/allowlist")


_REGISTRY = "llm_scope_authorities.json"
_REGISTRY_THREAD_LOCK = threading.RLock()  # Independent from gate._thread_lock.
_REPO = Path(__file__).resolve().parents[1]


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _fail(code, field):
    raise gate.LlmBudgetBlocked(code, field)


def _source_hash() -> str:
    h = hashlib.sha256()
    files = [_REPO / "__init__.py"]
    for folder in ("api", "bot"):
        files.extend((_REPO / folder).rglob("*.py"))
    for path in sorted(files):
        h.update(str(path.relative_to(_REPO)).encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()


# A source edit after this module was loaded must not masquerade as a freshly
# reviewed runtime. Restart/review is required; registry data is never rewritten.
_LOADED_SOURCE_HASH = _source_hash()


@dataclass(frozen=True)
class RuntimeIdentity:
    home: str
    runtime_id: str
    source_sha256: str
    fingerprint: str


def runtime_identity(home: str, runtime_id: str) -> RuntimeIdentity:
    if (type(home) is not str or not os.path.isabs(home) or type(runtime_id) is not str
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", runtime_id)):
        _fail("activation_runtime_invalid", "home/runtime_id")
    home = os.path.realpath(home)
    source = _source_hash()
    if source != _LOADED_SOURCE_HASH:
        _fail("activation_runtime_stale", "loaded_source")
    return RuntimeIdentity(home, runtime_id, source, _digest({"home": home, "runtime_id": runtime_id, "source_sha256": source}))


def configured_runtime(default_home: str) -> RuntimeIdentity | None:
    """Only known NON-secret deployment variables are read. Never initializes."""
    name = os.environ.get("COMFYART_RUNTIME_ID", "")
    if not name:
        return None
    return runtime_identity(os.environ.get("COMFYART_HOME") or default_home, name)


def _check_runtime(runtime: RuntimeIdentity):
    if type(runtime) is not RuntimeIdentity or runtime != runtime_identity(runtime.home, runtime.runtime_id):
        _fail("activation_runtime_mismatch", "identity")


def profile_hash() -> str:
    names = ("CONTEXT_TOKENS", "TOKENS_PER_IMAGE", "MAX_MESSAGES", "MAX_TOOLS", "MAX_SCHEMA_BYTES",
             "MAX_SINGLE_SCHEMA_BYTES", "MAX_TEXT_BYTES", "MAX_IMAGES", "MAX_IMAGE_BYTES", "MAX_ALL_IMAGE_BYTES",
             "MAX_BODY_BYTES", "MAX_SIDE", "MAX_PIXELS", "MAX_PROFILE_OUTPUT", "MODE")
    return _digest({name: getattr(envelope, name) for name in names})


def source_evidence() -> tuple[tuple[str, str], ...]:
    """Identity of reviewed quoted excerpts, not a claim to hash whole web pages."""
    return tuple((url, hashlib.sha256(text.encode()).hexdigest()) for url, text in envelope.EVIDENCE)


def evidence_hash() -> str:
    return _digest(source_evidence())


def default_tools() -> tuple[str, ...]:
    from ..api.mcp_tools import TOOLS
    from .guide import CORE_MCP_TOOLS
    from .local_llm import QUOTE_TOOL
    return tuple(sorted({name for name in CORE_MCP_TOOLS if name in TOOLS} | {QUOTE_TOOL}))


def _reviewed_binding(binding: dict, runtime: RuntimeIdentity):
    if binding == {"approved_runtime_sha256": runtime.fingerprint}:
        return
    sha = binding.get("reviewed_sha") if type(binding) is dict else None
    if type(sha) is not str:
        _fail("activation_runtime_mismatch", "runtime_binding")
    # Local read-only Git metadata only; no CLI auth/provider/network operations.
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "api", "bot", "__init__.py"],
                           cwd=_REPO, capture_output=True, text=True)
    if head.returncode or dirty.returncode or head.stdout.strip() != sha or dirty.stdout.strip():
        _fail("activation_runtime_mismatch", "reviewed_sha/source_cleanliness")


def _validate(candidate, expected, runtime):
    _check_runtime(runtime)
    try:
        receipt = manifests.validate_manifest(candidate, expected=expected)
    except manifests.ManifestInvalid as exc:
        _fail("activation_manifest_invalid", str(exc))
    if expected.policy_hash != profile_hash() or expected.evidence_hash != evidence_hash() or set(expected.sources) != set(source_evidence()):
        _fail("activation_policy_mismatch", "profile/evidence")
    if set(expected.tool_allowlist) != set(default_tools()):
        _fail("activation_policy_mismatch", "default_tool_inventory")
    if expected.risk_mode != "risk_accepted_context_contract":
        _fail("activation_policy_mismatch", "non-strict_context_mode")
    _reviewed_binding(candidate["runtime_binding"], runtime)
    return receipt


def _expected(manifest):
    return manifests.ManifestContext(
        authorization_id=manifest["authorization_id"], validation_run_id=manifest["validation_run_id"],
        scope_id=manifest["scope_id"], canonical_absolute_ledger_path=manifest["canonical_absolute_ledger_path"],
        policy_hash=profile_hash(), evidence_hash=evidence_hash(), sources=source_evidence(),
        runtime_binding=next(iter(manifest["runtime_binding"].items())), risk_mode="risk_accepted_context_contract",
        tool_allowlist=default_tools(), max_posts=manifest["scope_limits"]["max_posts"], route_url=manifest["route_url"])


@contextlib.contextmanager
def _registry_lock(home):
    os.makedirs(home, exist_ok=True)
    path = os.path.join(home, _REGISTRY)
    with _REGISTRY_THREAD_LOCK:
        fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield path
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _read_registry(path, *, create=False):
    present, marked = os.path.lexists(path), os.path.lexists(path + ".activated")
    if not present:
        if marked:
            _fail("activation_registry_unreadable", "missing_after_initialization")
        if create:
            return {"version": 1, "registry_id": uuid.uuid4().hex, "authorities": {}, "runtimes": {}}
        return None
    try:
        data = json.loads(gate._read_raw(path))
        if (type(data) is not dict or set(data) != {"version", "registry_id", "authorities", "runtimes"}
                or type(data["version"]) is not int or data["version"] != 1
                or type(data["registry_id"]) is not str or not re.fullmatch(r"[0-9a-f]{32}", data["registry_id"])
                or type(data["authorities"]) is not dict or type(data["runtimes"]) is not dict):
            raise ValueError()
        if marked:
            marker = json.loads(gate._read_raw(path + ".activated"))
            if type(marker) is not dict or type(marker.get("version")) is not int or marker != {"version": 1, "registry_id": data["registry_id"]}:
                raise ValueError()
        elif not create:
            _fail("activation_registry_incomplete", "initialization_marker")
        return data
    except (ValueError, OSError) as exc:
        raise gate.LlmBudgetBlocked("activation_registry_unreadable", "registry/marker") from exc


def _write_registry(path, data, stage_prefix="registry_"):
    gate._atomic_write(path, gate._dump(data), stage_prefix=stage_prefix)
    if not os.path.lexists(path + ".activated"):
        gate._atomic_write(path + ".activated", gate._dump({"version": 1, "registry_id": data["registry_id"]}),
                           stage_prefix="registry_marker_")


def _binding(candidate, receipt, runtime):
    return {"version": 1, "home": runtime.home, "runtime_id": runtime.runtime_id,
            "runtime_fingerprint": runtime.fingerprint, "source_sha256": runtime.source_sha256,
            "manifest_sha256": receipt.manifest_sha256, "manifest": candidate}


def _scope_matches(data, binding):
    m = binding["manifest"]
    ceiling = data.get("ceiling_nano")
    if (data["scope_id"] != m["scope_id"] or data["authorization"] != gate.TWO_DOLLAR_AUTHORIZATION
            or ceiling not in (gate.TWO_DOLLAR_CEILING_NANO, gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO)
            or data.get("authorized_ceiling_nano") != ceiling
            or not gate._ceiling_extension_matches(data, ceiling)
            or data.get("control_limits") != {"version": 1, **m["scope_limits"]}):
        _fail("activation_scope_mismatch", "scope/authority/limits")


# Exact reviewed git hops. They are not file hashes, and there is no wildcard.
# Provenance stores the pair the caller names. The loaded source hash is this
# process tree, which changes when api/ or bot/ bytes change, so it is not the
# tree of the "to" commit.
# Pair 1: original protocol review. Pair 2: deployed 42413ac7 -> a8c5c13c, the
# commit that added resolve_unknown_as_spent. Pair 3: deployed 0b73f5db ->
# bcc804bc, recorded by c2ee84ac and deployed with that tree. Pair 4:
# bcc804bc -> 9c0a4807, the commit that aligns multi-angle finals and stops a
# controlled generate after precheck. Pair 5: 9c0a4807 -> d83072c8, the commit
# that always asks both setup questions. Pair 6: bcc804bc -> d83072c8 in one
# hop. Pair 7: bcc804bc -> d6b8047f, the commit that keeps live-tab and
# policy-denial stops on controlled turns. After hop 1 the binding source
# equals this tree, so a second hop fails reviewed_source; _is_old_binding
# does not walk the pair chain. 8a959379 remains an ancestor. A direct
# 0b73f5db -> d83072c8 hop stays unauthorized.
# Recording a pair changes the loaded file hash again. Provenance stores the
# named git pair; the destination source hash is this process tree, not the
# "to" commit's tree.
REVIEWED_GIT_PAIRS = (
    ("571c7fb7184dc4e97c115429bd6859d445e98c21", "c3d3820e998985c678feea74a47ab4613946b761"),
    ("42413ac72626671a1790dbed87544f9f32ebaedf", "a8c5c13c8977e2473ed3b1e2d12cbe414f3addbc"),
    ("0b73f5dbf909cba9578dcc4129bafb3d64c10f99", "bcc804bc13f3fa684c0ecf5547ac71023163da09"),
    ("bcc804bc13f3fa684c0ecf5547ac71023163da09", "9c0a480753f6f9856fd137067e9026d20a425c3a"),
    ("9c0a480753f6f9856fd137067e9026d20a425c3a", "d83072c8a8bddf726fc9e68f94f6550d3a3823de"),
    ("bcc804bc13f3fa684c0ecf5547ac71023163da09", "d83072c8a8bddf726fc9e68f94f6550d3a3823de"),
    ("bcc804bc13f3fa684c0ecf5547ac71023163da09", "d6b8047fb9f38a57e2f8400f71f9b360ccd6aafc"),
)
# Index 0 is the original protocol review, not the newest hop. A caller must
# name the exact pair for the hop it is performing; nothing here means "latest".
REVIEWED_FROM_GIT = REVIEWED_GIT_PAIRS[0][0]
REVIEWED_PROTOCOL_GIT = REVIEWED_GIT_PAIRS[0][1]
REVIEWED_DEPLOYED_GIT = REVIEWED_GIT_PAIRS[1][0]
REVIEWED_RESOLVE_GIT = REVIEWED_GIT_PAIRS[1][1]
REVIEWED_LIVE_GIT = REVIEWED_GIT_PAIRS[2][0]
REVIEWED_EXTERNAL_GIT = REVIEWED_GIT_PAIRS[2][1]
REVIEWED_LOGIC_GIT = REVIEWED_GIT_PAIRS[3][1]
REVIEWED_FINALS_GIT = REVIEWED_GIT_PAIRS[4][0]
REVIEWED_SETUP_GIT = REVIEWED_GIT_PAIRS[4][1]


def _spend_view(data: dict) -> dict:
    rows = data.get("reservations") if type(data.get("reservations")) is dict else {}
    view = {
        "scope_id": data.get("scope_id"),
        "authorization": data.get("authorization"),
        "authorized_ceiling_nano": data.get("authorized_ceiling_nano"),
        "ceiling_nano": data.get("ceiling_nano"),
        "accounted_nano": data.get("accounted_nano"),
        "control_limits": data.get("control_limits"),
        "control_state": data.get("control_state"),
        "reservations": {key: {field: row.get(field) for field in ("status", "reserved_nano", "actual_nano", "retain_reason")}
                         for key, row in rows.items() if type(row) is dict},
    }
    if "external_spend" in data:
        external = data.get("external_spend") if type(data.get("external_spend")) is dict else {}
        view["external_spend"] = {key: {field: row.get(field) for field in ("status", "quote_nano", "actual_nano", "task_id")}
                                  for key, row in external.items() if type(row) is dict}
    return view


def _fingerprint_for(home: str, runtime_id: str, source_sha256: str) -> str:
    return _digest({"home": home, "runtime_id": runtime_id, "source_sha256": source_sha256})


def _migration_provenance(old_binding: dict, runtime: RuntimeIdentity, pair: tuple[str, str]) -> dict:
    return {
        "version": 1,
        "from_source_sha256": old_binding["source_sha256"],
        "to_source_sha256": runtime.source_sha256,
        "from_runtime_fingerprint": old_binding["runtime_fingerprint"],
        "to_runtime_fingerprint": runtime.fingerprint,
        "reviewed_from_git": pair[0],
        "reviewed_protocol_git": pair[1],
        "previous_runtime_binding": old_binding["manifest"]["runtime_binding"],
    }


def _target_binding(old_binding: dict, runtime: RuntimeIdentity, pair: tuple[str, str]) -> dict:
    """Same manifest identity, source fingerprint replaced by the loaded runtime."""
    manifest = json.loads(_canonical(old_binding["manifest"]))
    manifest["runtime_binding"] = {"approved_runtime_sha256": runtime.fingerprint}
    receipt = _validate(manifest, _expected(manifest), runtime)
    return {
        "version": 1,
        "home": runtime.home,
        "runtime_id": runtime.runtime_id,
        "runtime_fingerprint": runtime.fingerprint,
        "source_sha256": runtime.source_sha256,
        "manifest_sha256": receipt.manifest_sha256,
        "manifest": manifest,
        "source_migration": _migration_provenance(old_binding, runtime, pair),
    }


def _is_old_binding(binding: dict, runtime: RuntimeIdentity, from_source: str, authorization_id: str,
                    scope_id: str, ledger_path: str) -> bool:
    manifest = binding.get("manifest") if type(binding.get("manifest")) is dict else {}
    return (binding.get("home") == runtime.home and binding.get("runtime_id") == runtime.runtime_id
            and binding.get("source_sha256") == from_source
            and binding.get("runtime_fingerprint") == _fingerprint_for(runtime.home, runtime.runtime_id, from_source)
            and manifest.get("authorization_id") == authorization_id
            and manifest.get("scope_id") == scope_id
            and manifest.get("canonical_absolute_ledger_path") == ledger_path)


def _is_target_binding(binding: dict, runtime: RuntimeIdentity, from_source: str, pair: tuple[str, str]) -> bool:
    migration = binding.get("source_migration")
    return (type(binding) is dict and binding.get("home") == runtime.home
            and binding.get("runtime_id") == runtime.runtime_id
            and binding.get("source_sha256") == runtime.source_sha256
            and binding.get("runtime_fingerprint") == runtime.fingerprint
            and type(migration) is dict
            and migration.get("from_source_sha256") == from_source
            and migration.get("to_source_sha256") == runtime.source_sha256
            and migration.get("reviewed_from_git") == pair[0]
            and migration.get("reviewed_protocol_git") == pair[1])


def _raw_ledger(path: str) -> dict:
    try:
        data = json.loads(gate._read_raw(path))
    except (OSError, ValueError) as exc:
        raise gate.LlmBudgetBlocked("migration_state_unreadable", "ledger") from exc
    if type(data) is not dict:
        _fail("migration_state_unreadable", "ledger")
    return data


def _require_safe_spend(path: str, data: dict) -> None:
    """Refuse an open breaker, an outstanding hold, or a pending outcome journal.

    The refusal does not clear those fields. A reconciled row, or a row booked
    by resolve_unknown_as_spent, is spent. retained and reserved rows stay refused.
    """
    if os.path.lexists(gate._outcome_pending_path(path)):
        _fail("migration_state_unsafe", "outcome_pending")
    state = data.get("control_state") if type(data.get("control_state")) is dict else {}
    if state.get("circuit_open") is True:
        _fail("migration_state_unsafe", "breaker")
    rows = data.get("reservations") if type(data.get("reservations")) is dict else None
    if rows is None or any(type(row) is not dict or row.get("status") not in ("reconciled", "resolved_as_spent") for row in rows.values()):
        _fail("migration_state_unsafe", "hold")
    external = data.get("external_spend")
    if external is not None and (type(external) is not dict or any(
            type(row) is not dict or row.get("status") not in ("reconciled", "resolved_as_spent") for row in external.values())):
        _fail("migration_state_unsafe", "external_hold")


def _loaded_spend(path: str) -> dict:
    data, _, _ = gate._load_ledger(path, create=False)
    _require_safe_spend(path, data)
    if _spend_view(data) != _spend_view(_raw_ledger(path)):
        _fail("migration_state_unsafe", "normalized_drift")
    return data


def _write_rebind(path: str, data: dict, binding: dict) -> None:
    before = _spend_view(data)
    data["runtime_activation"] = binding
    gate._persist_ledger(path, data, write_marker=True)
    # An existing marker is not rewritten by _persist_ledger. Leaving the old
    # activation there makes the next read unreadable, so the marker moves in
    # the same locked section, after the ledger fsync.
    gate._write_activation_marker(path, data)
    if _spend_view(_raw_ledger(path)) != before:
        _fail("migration_state_unsafe", "spend_changed")


def migrate_source_fingerprint(runtime: RuntimeIdentity, *, authorization_id: str, from_source_sha256: str,
                               scope_id: str, ledger_path: str, reviewed_from_git: str,
                               reviewed_protocol_git: str) -> dict:
    """Move one active binding from a reviewed source hash onto this loaded source.

    This is not activation. ``activate_scope`` still rejects any different
    binding for an existing authority. The caller must name the bound source
    hash, the scope, the ledger path, and one exact pair from
    ``REVIEWED_GIT_PAIRS``. Provenance stores that pair. The deployed 42413ac7
    hop therefore records 42413ac7 and the resolve commit, not 571. The new
    source hash is this process's loaded tree, not a caller-supplied digest.
    Loading this migration changes the file hash again.

    Preconditions for a real rollout, none of which this function performs:
    the process is the new source; inflight is 0; every reservation is
    reconciled or resolved_as_spent; the breaker is closed; no outcome journal
    exists; the registry
    entry is active for this same runtime id and authority. A failed check
    writes nothing. Rollback is not a flag here. Before the pending registry
    write, stopping is the rollback. After that write, sends stay blocked until
    this same migration completes; completing it does not restore the old
    fingerprint. A reverse move requires a later reviewed migration whose
    loaded source is the source being restored.

    Registry pending is published before the ledger binding changes. Pending
    and active both fail closed for a process still loaded with the old source.
    Interrupted work is finished only by repeating this same call.
    """
    _check_runtime(runtime)
    pair = (reviewed_from_git, reviewed_protocol_git)
    if (pair not in REVIEWED_GIT_PAIRS
            or type(from_source_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", from_source_sha256)
            or from_source_sha256 == runtime.source_sha256):
        _fail("migration_not_authorized", "reviewed_source")
    if (type(authorization_id) is not str or not authorization_id.strip()
            or type(scope_id) is not str or not scope_id.strip()
            or type(ledger_path) is not str or not os.path.isabs(ledger_path)
            or os.path.realpath(ledger_path) != ledger_path):
        _fail("migration_not_authorized", "scope")
    with _registry_lock(runtime.home) as registry_path:
        registry = _read_registry(registry_path)
        if registry is None or registry["runtimes"].get(runtime.runtime_id) != authorization_id:
            _fail("migration_not_authorized", "runtime")
        entry = registry["authorities"].get(authorization_id)
        if type(entry) is not dict or set(entry) != {"status", "binding", "digest"} or entry["status"] not in ("pending", "active"):
            _fail("migration_state_unsafe", "authority")
        stored = entry["binding"]
        if type(stored) is not dict or _digest(stored) != entry["digest"]:
            _fail("migration_state_unsafe", "digest")
        with gate._with_ledger_lock(ledger_path):
            if _is_old_binding(stored, runtime, from_source_sha256, authorization_id, scope_id, ledger_path):
                if entry["status"] != "active":
                    _fail("migration_state_unsafe", "inactive_old_binding")
                data = _loaded_spend(ledger_path)
                _scope_matches(data, stored)
                if data.get("runtime_activation") != stored:
                    _fail("migration_state_unsafe", "ledger_binding")
                target = _target_binding(stored, runtime, pair)
                registry["authorities"][authorization_id] = {"status": "pending", "digest": _digest(target), "binding": target}
                _write_registry(registry_path, registry, stage_prefix="migration_pending_")
                _write_rebind(ledger_path, data, target)
                registry["authorities"][authorization_id]["status"] = "active"
                _write_registry(registry_path, registry, stage_prefix="migration_active_")
                return {"ok": True, "scope_id": scope_id, "activation_digest": _digest(target), "resumed": False}
            if not _is_target_binding(stored, runtime, from_source_sha256, pair):
                _fail("migration_not_authorized", "binding")
            target = stored
            manifest = target.get("manifest") if type(target.get("manifest")) is dict else {}
            if (manifest.get("authorization_id") != authorization_id or manifest.get("scope_id") != scope_id
                    or manifest.get("canonical_absolute_ledger_path") != ledger_path):
                _fail("migration_not_authorized", "scope")
            raw = _raw_ledger(ledger_path)
            marker = gate._read_marker(ledger_path)
            ledger_activation = raw.get("runtime_activation")
            marker_activation = marker.get("runtime_activation")
            if ledger_activation == target and marker_activation == target:
                data = _loaded_spend(ledger_path)
                _scope_matches(data, target)
                was_pending = entry["status"] == "pending"
                if was_pending:
                    registry["authorities"][authorization_id]["status"] = "active"
                    _write_registry(registry_path, registry, stage_prefix="migration_active_")
                return {"ok": True, "scope_id": scope_id, "activation_digest": entry["digest"], "resumed": was_pending}
            if (ledger_activation == target and type(marker_activation) is dict
                    and _is_old_binding(marker_activation, runtime, from_source_sha256, authorization_id, scope_id, ledger_path)):
                if marker.get("scope_id") != raw.get("scope_id") or marker.get("control_limits") != raw.get("control_limits"):
                    _fail("migration_state_unsafe", "marker")
                gate._write_activation_marker(ledger_path, raw)
                data = _loaded_spend(ledger_path)
                _scope_matches(data, target)
                registry["authorities"][authorization_id]["status"] = "active"
                _write_registry(registry_path, registry, stage_prefix="migration_active_")
                return {"ok": True, "scope_id": scope_id, "activation_digest": entry["digest"], "resumed": True}
            if (type(ledger_activation) is dict
                    and _is_old_binding(ledger_activation, runtime, from_source_sha256, authorization_id, scope_id, ledger_path)
                    and marker_activation == ledger_activation):
                data = _loaded_spend(ledger_path)
                _scope_matches(data, ledger_activation)
                _write_rebind(ledger_path, data, target)
                registry["authorities"][authorization_id]["status"] = "active"
                _write_registry(registry_path, registry, stage_prefix="migration_active_")
                return {"ok": True, "scope_id": scope_id, "activation_digest": entry["digest"], "resumed": True}
            _fail("migration_state_unsafe", "torn_binding")


def _manifest_posts(binding: dict) -> int | None:
    manifest = binding.get("manifest") if type(binding.get("manifest")) is dict else {}
    limits = manifest.get("scope_limits") if type(manifest.get("scope_limits")) is dict else {}
    posts = limits.get("max_posts")
    return posts if type(posts) is int else None


def _same_activated_scope(binding: dict, runtime: RuntimeIdentity, authorization_id: str, scope_id: str,
                          ledger_path: str) -> bool:
    manifest = binding.get("manifest") if type(binding.get("manifest")) is dict else {}
    return (binding.get("home") == runtime.home and binding.get("runtime_id") == runtime.runtime_id
            and binding.get("source_sha256") == runtime.source_sha256
            and binding.get("runtime_fingerprint") == runtime.fingerprint
            and manifest.get("authorization_id") == authorization_id
            and manifest.get("scope_id") == scope_id
            and manifest.get("canonical_absolute_ledger_path") == ledger_path)


def _require_extendable(path: str, data: dict, binding: dict) -> None:
    if os.path.lexists(gate._outcome_pending_path(path)):
        _fail("extend_refused", "journal")
    state = data.get("control_state") if type(data.get("control_state")) is dict else {}
    limits = data.get("control_limits") if type(data.get("control_limits")) is dict else {}
    manifest = binding.get("manifest") if type(binding.get("manifest")) is dict else {}
    scope_limits = manifest.get("scope_limits") if type(manifest.get("scope_limits")) is dict else {}
    ceiling = data.get("ceiling_nano")
    if (ceiling not in (gate.TWO_DOLLAR_CEILING_NANO, gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO)
            or data.get("authorized_ceiling_nano") != ceiling
            or limits.get("amount_nano") != ceiling
            or scope_limits.get("amount_nano") != ceiling
            or not gate._ceiling_extension_matches(data, ceiling)
            or limits.get("max_inflight") != 1
            or scope_limits.get("max_inflight") != 1):
        _fail("extend_refused", "usd")
    if state.get("circuit_open") is True:
        _fail("extend_refused", "breaker")
    rows = data.get("reservations") if type(data.get("reservations")) is dict else None
    if rows is None or any(type(row) is not dict or row.get("status") not in ("reconciled", "resolved_as_spent") for row in rows.values()):
        _fail("extend_refused", "hold")
    if any(row.get("status") == "reserved" for row in rows.values()):
        _fail("extend_refused", "inflight")
    external = data.get("external_spend")
    if external is not None and (type(external) is not dict or any(
            type(row) is not dict or row.get("status") not in ("reconciled", "resolved_as_spent") for row in external.values())):
        _fail("extend_refused", "external_hold")


def _extended_binding(old_binding: dict, runtime: RuntimeIdentity, new_max_posts: int) -> dict:
    manifest = json.loads(_canonical(old_binding["manifest"]))
    manifest["scope_limits"] = dict(manifest["scope_limits"])
    manifest["scope_limits"]["max_posts"] = new_max_posts
    receipt = _validate(manifest, _expected(manifest), runtime)
    binding = {
        "version": 1,
        "home": runtime.home,
        "runtime_id": runtime.runtime_id,
        "runtime_fingerprint": runtime.fingerprint,
        "source_sha256": runtime.source_sha256,
        "manifest_sha256": receipt.manifest_sha256,
        "manifest": manifest,
    }
    if "source_migration" in old_binding:
        binding["source_migration"] = old_binding["source_migration"]
    return binding


def _apply_post_extension(path: str, data: dict, binding: dict, old_posts: int, new_posts: int,
                          operator: str, reason: str) -> None:
    accounted = data["accounted_nano"]
    attempts = data["control_state"]["attempts_total"]
    rows = _canonical(data["reservations"])
    ceiling = data["ceiling_nano"]
    amount = data["control_limits"]["amount_nano"]
    inflight_limit = data["control_limits"]["max_inflight"]
    data["control_limits"]["max_posts"] = new_posts
    audits = data.get("limit_extension")
    if not (type(audits) is list and audits and audits[-1].get("new") == new_posts):
        data.setdefault("limit_extension", []).append({
            "old": old_posts, "new": new_posts, "operator": operator, "reason": reason, "at": int(time.time()),
        })
    data["runtime_activation"] = binding
    if (data["accounted_nano"] != accounted or data["control_state"]["attempts_total"] != attempts
            or _canonical(data["reservations"]) != rows):
        _fail("extend_refused", "spend_changed")
    if (data["ceiling_nano"] != ceiling or data["control_limits"]["amount_nano"] != amount
            or data["control_limits"]["max_inflight"] != inflight_limit or data["control_limits"]["max_posts"] != new_posts):
        _fail("extend_refused", "usd")
    if not gate._extension_matches(data, new_posts):
        _fail("extend_refused", "audit")
    gate._persist_ledger(path, data, write_marker=True)
    gate._write_activation_marker(path, data)


def _ledger_extension_state(path: str, binding: dict) -> str:
    """Return 'done', 'marker', or 'open' without treating a torn marker as unreadable."""
    raw = _raw_ledger(path)
    marker = gate._read_marker(path)
    limits = raw.get("control_limits") if type(raw.get("control_limits")) is dict else {}
    marker_limits = marker.get("control_limits") if type(marker.get("control_limits")) is dict else {}
    posts = _manifest_posts(binding)
    if limits.get("max_posts") == posts and raw.get("runtime_activation") == binding and gate._extension_matches(raw, posts):
        if marker_limits.get("max_posts") == posts and marker.get("runtime_activation") == binding:
            return "done"
        return "marker"
    if marker.get("control_limits") == raw.get("control_limits") and marker.get("runtime_activation") == raw.get("runtime_activation"):
        return "open"
    _fail("extend_refused", "torn")


def extend_post_limit(runtime: RuntimeIdentity, *, authorization_id: str, scope_id: str, ledger_path: str,
                      new_max_posts: int, operator: str, reason: str) -> dict:
    """Raise one scope's POST limit. Ceiling, inflight, spend, and rows stay put.

    Registry pending is published before the ledger limit changes. A repeated
    call of the same extension finishes an interrupted write and does not append
    a second audit row.     A decrease, a ceiling change, an open breaker, a hold,
    or a limit above the ceiling's post cap writes nothing. That cap is 12
    until extend_ceiling raises the same ledger to $5, and 30 after that.
    """
    _check_runtime(runtime)
    if (type(new_max_posts) is not int or not 1 <= new_max_posts <= gate.CONTROLLED_POSTS_EXTENDED_HARD_CAP
            or type(operator) is not str or not operator.strip()
            or type(reason) is not str or not reason.strip()):
        _fail("extend_refused", "above_cap" if type(new_max_posts) is int and new_max_posts > gate.CONTROLLED_POSTS_EXTENDED_HARD_CAP else "arguments")
    if (type(authorization_id) is not str or not authorization_id.strip()
            or type(scope_id) is not str or not scope_id.strip()
            or type(ledger_path) is not str or not os.path.isabs(ledger_path)
            or os.path.realpath(ledger_path) != ledger_path):
        _fail("extend_refused", "scope")
    with _registry_lock(runtime.home) as registry_path:
        registry = _read_registry(registry_path)
        if registry is None or registry["runtimes"].get(runtime.runtime_id) != authorization_id:
            _fail("extend_refused", "runtime")
        entry = registry["authorities"].get(authorization_id)
        if type(entry) is not dict or set(entry) != {"status", "binding", "digest"} or entry["status"] not in ("pending", "active"):
            _fail("extend_refused", "authority")
        stored = entry["binding"]
        if type(stored) is not dict or _digest(stored) != entry["digest"]:
            _fail("extend_refused", "digest")
        if not _same_activated_scope(stored, runtime, authorization_id, scope_id, ledger_path):
            _fail("extend_refused", "runtime")
        current = _manifest_posts(stored)
        if current is None:
            _fail("extend_refused", "limits")
        if current > new_max_posts:
            _fail("extend_refused", "decrease")
        with gate._with_ledger_lock(ledger_path):
            if current == new_max_posts:
                state = _ledger_extension_state(ledger_path, stored)
                if state == "open":
                    if entry["status"] != "pending":
                        _fail("extend_refused", "decrease")
                    data, _, _ = gate._load_ledger(ledger_path, create=False)
                    _require_extendable(ledger_path, data, stored)
                    old_posts = data["control_limits"]["max_posts"]
                    if type(old_posts) is not int or old_posts >= new_max_posts:
                        _fail("extend_refused", "decrease")
                    _apply_post_extension(ledger_path, data, stored, old_posts, new_max_posts, operator, reason)
                    registry["authorities"][authorization_id]["status"] = "active"
                    _write_registry(registry_path, registry, stage_prefix="extension_active_")
                    return {"ok": True, "scope_id": scope_id, "max_posts": new_max_posts, "idempotent": False, "resumed": True}
                if state == "marker":
                    gate._write_activation_marker(ledger_path, _raw_ledger(ledger_path))
                data, _, _ = gate._load_ledger(ledger_path, create=False)
                if data.get("control_limits", {}).get("max_posts") != new_max_posts:
                    _fail("extend_refused", "limits")
                was_pending = entry["status"] == "pending"
                if was_pending:
                    registry["authorities"][authorization_id]["status"] = "active"
                    _write_registry(registry_path, registry, stage_prefix="extension_active_")
                return {"ok": True, "scope_id": scope_id, "max_posts": new_max_posts,
                        "idempotent": not was_pending, "resumed": was_pending or state == "marker"}
            if entry["status"] != "active":
                _fail("extend_refused", "pending")
            if new_max_posts <= current:
                _fail("extend_refused", "decrease")
            data, _, _ = gate._load_ledger(ledger_path, create=False)
            _require_extendable(ledger_path, data, stored)
            if new_max_posts > gate.posts_hard_cap(data):
                _fail("extend_refused", "above_cap")
            _scope_matches(data, stored)
            if data.get("runtime_activation") != stored:
                _fail("extend_refused", "ledger_binding")
            old_posts = data["control_limits"]["max_posts"]
            if old_posts != current or new_max_posts <= old_posts:
                _fail("extend_refused", "decrease")
            target = _extended_binding(stored, runtime, new_max_posts)
            registry["authorities"][authorization_id] = {"status": "pending", "digest": _digest(target), "binding": target}
            _write_registry(registry_path, registry, stage_prefix="extension_pending_")
            _apply_post_extension(ledger_path, data, target, old_posts, new_max_posts, operator, reason)
            registry["authorities"][authorization_id]["status"] = "active"
            _write_registry(registry_path, registry, stage_prefix="extension_active_")
            return {"ok": True, "scope_id": scope_id, "max_posts": new_max_posts, "idempotent": False, "resumed": False}


def _manifest_amount(binding: dict) -> int | None:
    manifest = binding.get("manifest") if type(binding.get("manifest")) is dict else {}
    limits = manifest.get("scope_limits") if type(manifest.get("scope_limits")) is dict else {}
    amount = limits.get("amount_nano")
    return amount if type(amount) is int else None


def _extended_ceiling_binding(old_binding: dict, runtime: RuntimeIdentity, new_amount: int) -> dict:
    manifest = json.loads(_canonical(old_binding["manifest"]))
    manifest["scope_limits"] = dict(manifest["scope_limits"])
    manifest["scope_limits"]["amount_nano"] = new_amount
    receipt = _validate(manifest, _expected(manifest), runtime)
    binding = {
        "version": 1,
        "home": runtime.home,
        "runtime_id": runtime.runtime_id,
        "runtime_fingerprint": runtime.fingerprint,
        "source_sha256": runtime.source_sha256,
        "manifest_sha256": receipt.manifest_sha256,
        "manifest": manifest,
    }
    if "source_migration" in old_binding:
        binding["source_migration"] = old_binding["source_migration"]
    return binding


def _apply_ceiling_extension(path: str, data: dict, binding: dict, old_amount: int, new_amount: int,
                             operator: str, reason: str) -> None:
    accounted = data["accounted_nano"]
    attempts = data["control_state"]["attempts_total"]
    rows = _canonical(data["reservations"])
    external = _canonical(data["external_spend"]) if "external_spend" in data else None
    posts = data["control_limits"]["max_posts"]
    inflight_limit = data["control_limits"]["max_inflight"]
    data["ceiling_nano"] = new_amount
    data["authorized_ceiling_nano"] = new_amount
    data["control_limits"]["amount_nano"] = new_amount
    audits = data.get("ceiling_extension")
    if not (type(audits) is list and audits and audits[-1].get("new") == new_amount):
        data.setdefault("ceiling_extension", []).append({
            "old": old_amount, "new": new_amount, "operator": operator, "reason": reason, "at": int(time.time()),
        })
    data["runtime_activation"] = binding
    if (data["accounted_nano"] != accounted or data["control_state"]["attempts_total"] != attempts
            or _canonical(data["reservations"]) != rows
            or ("external_spend" in data and _canonical(data["external_spend"]) != external)):
        _fail("extend_refused", "spend_changed")
    if (data["control_limits"]["max_posts"] != posts or data["control_limits"]["max_inflight"] != inflight_limit
            or data["ceiling_nano"] != new_amount or data["control_limits"]["amount_nano"] != new_amount
            or data["authorized_ceiling_nano"] != new_amount):
        _fail("extend_refused", "usd")
    if not gate._ceiling_extension_matches(data, new_amount):
        _fail("extend_refused", "audit")
    gate._persist_ledger(path, data, write_marker=True)
    gate._write_activation_marker(path, data)


def _ledger_ceiling_state(path: str, binding: dict) -> str:
    raw = _raw_ledger(path)
    marker = gate._read_marker(path)
    limits = raw.get("control_limits") if type(raw.get("control_limits")) is dict else {}
    marker_limits = marker.get("control_limits") if type(marker.get("control_limits")) is dict else {}
    amount = _manifest_amount(binding)
    if (limits.get("amount_nano") == amount and raw.get("ceiling_nano") == amount
            and raw.get("authorized_ceiling_nano") == amount
            and raw.get("runtime_activation") == binding
            and gate._ceiling_extension_matches(raw, amount)):
        if (marker_limits.get("amount_nano") == amount and marker.get("authorized_ceiling_nano") == amount
                and marker.get("runtime_activation") == binding):
            return "done"
        return "marker"
    if (marker.get("control_limits") == raw.get("control_limits")
            and marker.get("runtime_activation") == raw.get("runtime_activation")
            and marker.get("authorized_ceiling_nano") == raw.get("authorized_ceiling_nano")):
        return "open"
    _fail("extend_refused", "torn")


def extend_ceiling(runtime: RuntimeIdentity, *, authorization_id: str, scope_id: str, ledger_path: str,
                   new_amount_nano: int, operator: str, reason: str) -> dict:
    """Raise one existing ledger's USD ceiling. No new ledger and no new authority.

    The only increase is to FIVE_DOLLAR_EXTENDED_CEILING_NANO. Opening a scope
    still uses TWO_DOLLAR_CEILING_NANO. Accounted spend, attempts, reservations,
    external spend, the post limit, and inflight stay put. A repeated call of
    the same ceiling finishes an interrupted write and does not append a second
    audit row. A decrease, an amount above $5, an open breaker, a hold, or a
    pending outcome journal writes nothing.
    """
    _check_runtime(runtime)
    if (type(new_amount_nano) is not int or new_amount_nano <= 0
            or type(operator) is not str or not operator.strip()
            or type(reason) is not str or not reason.strip()):
        _fail("extend_refused", "above_cap" if type(new_amount_nano) is int and new_amount_nano > gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO else "arguments")
    if new_amount_nano > gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO:
        _fail("extend_refused", "above_cap")
    if (type(authorization_id) is not str or not authorization_id.strip()
            or type(scope_id) is not str or not scope_id.strip()
            or type(ledger_path) is not str or not os.path.isabs(ledger_path)
            or os.path.realpath(ledger_path) != ledger_path):
        _fail("extend_refused", "scope")
    with _registry_lock(runtime.home) as registry_path:
        registry = _read_registry(registry_path)
        if registry is None or registry["runtimes"].get(runtime.runtime_id) != authorization_id:
            _fail("extend_refused", "runtime")
        entry = registry["authorities"].get(authorization_id)
        if type(entry) is not dict or set(entry) != {"status", "binding", "digest"} or entry["status"] not in ("pending", "active"):
            _fail("extend_refused", "authority")
        stored = entry["binding"]
        if type(stored) is not dict or _digest(stored) != entry["digest"]:
            _fail("extend_refused", "digest")
        if not _same_activated_scope(stored, runtime, authorization_id, scope_id, ledger_path):
            _fail("extend_refused", "runtime")
        current = _manifest_amount(stored)
        if current is None:
            _fail("extend_refused", "limits")
        if current > new_amount_nano:
            _fail("extend_refused", "decrease")
        if new_amount_nano != current and new_amount_nano != gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO:
            _fail("extend_refused", "amount")
        with gate._with_ledger_lock(ledger_path):
            if os.path.lexists(gate._outcome_pending_path(ledger_path)):
                _fail("extend_refused", "journal")
            if current == new_amount_nano:
                state = _ledger_ceiling_state(ledger_path, stored)
                if state == "open":
                    if entry["status"] != "pending":
                        _fail("extend_refused", "decrease")
                    data, _, _ = gate._load_ledger(ledger_path, create=False)
                    _require_extendable(ledger_path, data, stored)
                    old_amount = data["control_limits"]["amount_nano"]
                    if type(old_amount) is not int or old_amount >= new_amount_nano:
                        _fail("extend_refused", "decrease")
                    _apply_ceiling_extension(ledger_path, data, stored, old_amount, new_amount_nano, operator, reason)
                    registry["authorities"][authorization_id]["status"] = "active"
                    _write_registry(registry_path, registry, stage_prefix="ceiling_active_")
                    return {"ok": True, "scope_id": scope_id, "amount_nano": new_amount_nano, "idempotent": False, "resumed": True}
                if state == "marker":
                    gate._write_activation_marker(ledger_path, _raw_ledger(ledger_path))
                data, _, _ = gate._load_ledger(ledger_path, create=False)
                if data.get("ceiling_nano") != new_amount_nano or data.get("control_limits", {}).get("amount_nano") != new_amount_nano:
                    _fail("extend_refused", "limits")
                was_pending = entry["status"] == "pending"
                if was_pending:
                    registry["authorities"][authorization_id]["status"] = "active"
                    _write_registry(registry_path, registry, stage_prefix="ceiling_active_")
                return {"ok": True, "scope_id": scope_id, "amount_nano": new_amount_nano,
                        "idempotent": not was_pending, "resumed": was_pending or state == "marker"}
            if entry["status"] != "active":
                _fail("extend_refused", "pending")
            if new_amount_nano <= current:
                _fail("extend_refused", "decrease")
            data, _, _ = gate._load_ledger(ledger_path, create=False)
            _require_extendable(ledger_path, data, stored)
            _scope_matches(data, stored)
            if data.get("runtime_activation") != stored:
                _fail("extend_refused", "ledger_binding")
            old_amount = data["control_limits"]["amount_nano"]
            if old_amount != current or new_amount_nano <= old_amount:
                _fail("extend_refused", "decrease")
            target = _extended_ceiling_binding(stored, runtime, new_amount_nano)
            registry["authorities"][authorization_id] = {"status": "pending", "digest": _digest(target), "binding": target}
            _write_registry(registry_path, registry, stage_prefix="ceiling_pending_")
            _apply_ceiling_extension(ledger_path, data, target, old_amount, new_amount_nano, operator, reason)
            registry["authorities"][authorization_id]["status"] = "active"
            _write_registry(registry_path, registry, stage_prefix="ceiling_active_")
            return {"ok": True, "scope_id": scope_id, "amount_nano": new_amount_nano, "idempotent": False, "resumed": False}


def activate_scope(candidate: dict, *, expected: manifests.ManifestContext, runtime: RuntimeIdentity) -> dict:
    """EXPLICIT local admin operation; no HTTP, no funds creation, no auto-reset.

    Registry pending claim is durable BEFORE ledger binding; registry active is
    durable only AFTER ledger+marker fsync. Interrupted calls stop runtime sends;
    only an explicit identical operation can complete them. Registry->ledger is
    the sole nested lock ordering. Repeating never resets spend/count/breaker.
    """
    candidate = json.loads(_canonical(candidate))
    receipt = _validate(candidate, expected, runtime)
    binding = _binding(candidate, receipt, runtime)
    digest = _digest(binding)
    path = receipt.canonical_absolute_ledger_path
    with _registry_lock(runtime.home) as registry:
        data = _read_registry(registry, create=True)
        auth, rid = receipt.authorization_id, runtime.runtime_id
        old = data["authorities"].get(auth)
        if old is not None and (type(old) is not dict or set(old) != {"status", "binding", "digest"}
                                or old.get("status") not in ("pending", "active")
                                or old.get("binding") != binding or old.get("digest") != digest):
            _fail("activation_authority_conflict", "authorization_already_claimed")
        if rid in data["runtimes"] and data["runtimes"][rid] != auth:
            _fail("activation_runtime_conflict", "runtime_already_designated")
        # Validate ledger before creating any authority claim; it must exist.
        with gate._with_ledger_lock(path):
            ledger, _, _ = gate._load_ledger(path, create=False)
            _scope_matches(ledger, binding)
            current = ledger.get("runtime_activation")
            if current is not None and current != binding:
                _fail("activation_scope_conflict", "ledger_already_bound")
            if old is None and (ledger["control_state"]["circuit_open"] or any(r["status"] != "reconciled" for r in ledger["reservations"].values())):
                _fail("activation_scope_stopped", "unknown/breaker")
            if os.path.lexists(gate._outcome_pending_path(path)):
                _fail("activation_scope_stopped", "outcome_pending")
            data["authorities"][auth] = {"status": "pending", "digest": digest, "binding": binding}
            data["runtimes"][rid] = auth
            _write_registry(registry, data)
            ledger["runtime_activation"] = binding
            gate._persist_ledger(path, ledger, write_marker=True)
            # Explicit retry also re-fsyncs identical ledger state before active.
            data["authorities"][auth]["status"] = "active"
            _write_registry(registry, data)
    return {"ok": True, "scope_id": receipt.scope_id, "activation_digest": digest}


def _lookup_locked(registry, runtime):
    data = _read_registry(registry)
    if data is None:
        return None
    auth = data["runtimes"].get(runtime.runtime_id)
    if type(auth) is not str or auth not in data["authorities"]:
        _fail("activation_runtime_mismatch", "no_designated_authority")
    entry = data["authorities"][auth]
    if type(entry) is not dict or set(entry) != {"status", "digest", "binding"} or entry["status"] != "active":
        _fail("activation_not_committed", "authority_claim")
    binding = entry["binding"]
    try:
        if (type(binding) is not dict or binding["home"] != runtime.home or binding["runtime_id"] != runtime.runtime_id
                or binding["runtime_fingerprint"] != runtime.fingerprint or binding["source_sha256"] != runtime.source_sha256
                or _digest(binding) != entry["digest"] or binding["manifest"]["authorization_id"] != auth):
            raise ValueError()
        receipt = _validate(binding["manifest"], _expected(binding["manifest"]), runtime)
        if receipt.manifest_sha256 != binding["manifest_sha256"]:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise gate.LlmBudgetBlocked("activation_binding_mismatch", "registry_identity") from exc
    return entry


def active_binding(runtime: RuntimeIdentity, *, route: dict, url: str | None) -> dict | None:
    _check_runtime(runtime)
    with _registry_lock(runtime.home) as path:
        entry = _lookup_locked(path, runtime)
        if entry is None:
            return None
        manifest = entry["binding"]["manifest"]
        if ((url is not None and url != manifest["route_url"]) or type(route) is not dict or route.get("model") != manifest["model_pin"]["model"]
                or route.get("adapter") != "deepseek_official" or route.get("passthrough")):
            _fail("activation_route_mismatch", "route/model")
        return entry["binding"]


def reserve_for_runtime(runtime, *, path, nano, record, url, tools):
    _check_runtime(runtime)
    with _registry_lock(runtime.home) as registry:
        entry = _lookup_locked(registry, runtime)
        if entry is None:
            _fail("activation_required", "authority_registry")
        binding = entry["binding"]
        m = binding["manifest"]
        if path != m["canonical_absolute_ledger_path"] or url != m["route_url"]:
            _fail("activation_scope_mismatch", "path/route")
        if not set(tools) <= set(m["tool_allowlist"]) or (record.get("input_evidence") or {}).get("mode") != envelope.MODE:
            _fail("activation_policy_mismatch", "tools/profile")
        return gate.reserve_nano(path, nano=nano, record=record, runtime_binding=binding)
