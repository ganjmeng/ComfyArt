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
    if (data["scope_id"] != m["scope_id"] or data["authorization"] != gate.TWO_DOLLAR_AUTHORIZATION
            or data["ceiling_nano"] != gate.TWO_DOLLAR_CEILING_NANO
            or data.get("control_limits") != {"version": 1, **m["scope_limits"]}):
        _fail("activation_scope_mismatch", "scope/authority/limits")


# Git commits that reviewed the protocol change. They are not file hashes.
# The migration implementation itself changes api/ and bot/ bytes, so the
# loaded source hash is not the tree of REVIEWED_PROTOCOL_GIT.
REVIEWED_FROM_GIT = "571c7fb7184dc4e97c115429bd6859d445e98c21"
REVIEWED_PROTOCOL_GIT = "c3d3820e998985c678feea74a47ab4613946b761"


def _spend_view(data: dict) -> dict:
    rows = data.get("reservations") if type(data.get("reservations")) is dict else {}
    return {
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


def _fingerprint_for(home: str, runtime_id: str, source_sha256: str) -> str:
    return _digest({"home": home, "runtime_id": runtime_id, "source_sha256": source_sha256})


def _migration_provenance(old_binding: dict, runtime: RuntimeIdentity) -> dict:
    return {
        "version": 1,
        "from_source_sha256": old_binding["source_sha256"],
        "to_source_sha256": runtime.source_sha256,
        "from_runtime_fingerprint": old_binding["runtime_fingerprint"],
        "to_runtime_fingerprint": runtime.fingerprint,
        "reviewed_from_git": REVIEWED_FROM_GIT,
        "reviewed_protocol_git": REVIEWED_PROTOCOL_GIT,
        "previous_runtime_binding": old_binding["manifest"]["runtime_binding"],
    }


def _target_binding(old_binding: dict, runtime: RuntimeIdentity) -> dict:
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
        "source_migration": _migration_provenance(old_binding, runtime),
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


def _is_target_binding(binding: dict, runtime: RuntimeIdentity, from_source: str) -> bool:
    migration = binding.get("source_migration")
    return (type(binding) is dict and binding.get("home") == runtime.home
            and binding.get("runtime_id") == runtime.runtime_id
            and binding.get("source_sha256") == runtime.source_sha256
            and binding.get("runtime_fingerprint") == runtime.fingerprint
            and type(migration) is dict
            and migration.get("from_source_sha256") == from_source
            and migration.get("to_source_sha256") == runtime.source_sha256
            and migration.get("reviewed_from_git") == REVIEWED_FROM_GIT
            and migration.get("reviewed_protocol_git") == REVIEWED_PROTOCOL_GIT)


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

    The refusal does not clear those fields. A reconciled history, including a
    non-zero settled amount, is safe to rebind.
    """
    if os.path.lexists(gate._outcome_pending_path(path)):
        _fail("migration_state_unsafe", "outcome_pending")
    state = data.get("control_state") if type(data.get("control_state")) is dict else {}
    if state.get("circuit_open") is True:
        _fail("migration_state_unsafe", "breaker")
    rows = data.get("reservations") if type(data.get("reservations")) is dict else None
    if rows is None or any(type(row) is not dict or row.get("status") != "reconciled" for row in rows.values()):
        _fail("migration_state_unsafe", "hold")


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
    hash, the scope, the ledger path, and both reviewed git commits. The new
    source hash is this process's loaded tree, not a caller-supplied digest:
    ``REVIEWED_PROTOCOL_GIT`` is the reviewed protocol commit, and loading this
    migration changes the file hash again.

    Preconditions for a real rollout, none of which this function performs:
    the process is the new source; inflight is 0; every reservation is
    reconciled; the breaker is closed; no outcome journal exists; the registry
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
    if (reviewed_from_git != REVIEWED_FROM_GIT or reviewed_protocol_git != REVIEWED_PROTOCOL_GIT
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
                target = _target_binding(stored, runtime)
                registry["authorities"][authorization_id] = {"status": "pending", "digest": _digest(target), "binding": target}
                _write_registry(registry_path, registry, stage_prefix="migration_pending_")
                _write_rebind(ledger_path, data, target)
                registry["authorities"][authorization_id]["status"] = "active"
                _write_registry(registry_path, registry, stage_prefix="migration_active_")
                return {"ok": True, "scope_id": scope_id, "activation_digest": _digest(target), "resumed": False}
            if not _is_target_binding(stored, runtime, from_source_sha256):
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


def _finalize_pending_path(path: str) -> str:
    return path + ".finalize_pending"


def _row_digest(row: dict) -> str:
    return _digest({key: row.get(key) for key in ("id", "status", "reserved_nano", "actual_nano", "retain_reason", "body_sha256")})


def _audit_entry(data: dict, request_id: str) -> dict | None:
    rows = data.get("worst_case_finalizations")
    if type(rows) is not list:
        return None
    found = [row for row in rows if type(row) is dict and row.get("request_id") == request_id]
    return found[-1] if found else None


def _finalize_pending(path: str) -> dict | None:
    pending_path = _finalize_pending_path(path)
    if not os.path.lexists(pending_path):
        return None
    try:
        pending = json.loads(gate._read_raw(pending_path))
    except (OSError, ValueError) as exc:
        raise gate.LlmBudgetBlocked("finalize_refused", "pending_unreadable") from exc
    if type(pending) is not dict:
        _fail("finalize_refused", "pending_unreadable")
    return pending


def _same_finalize(pending: dict, *, authorization_id: str, scope_id: str, request_id: str,
                   expected_reserve_nano: int, expected_body_sha256: str, operator_note: str) -> bool:
    return (pending.get("op") == "finalize_unknown_as_worst_case"
            and pending.get("authority_id") == authorization_id and pending.get("scope_id") == scope_id
            and pending.get("request_id") == request_id and pending.get("reserve_nano") == expected_reserve_nano
            and pending.get("body_sha256") == expected_body_sha256 and pending.get("operator_note") == operator_note)


def _booked(row: dict, request_id: str, reserve: int) -> bool:
    return (type(row) is dict and row.get("id") == request_id and row.get("status") == "reconciled"
            and row.get("reserved_nano") == reserve and row.get("actual_nano") == reserve)


def finalize_unknown_as_worst_case(runtime: RuntimeIdentity, *, authorization_id: str, scope_id: str,
                                   request_id: str, expected_reserve_nano: int, expected_body_sha256: str,
                                   operator_note: str) -> dict:
    """Book one retained unknown at its full reserve, then close that anomaly's breaker.

    Not an activation and not a release. Count, ceiling, and accounted total stay
    put: the reserve is already in ``accounted_nano``, and booking it at the
    reserve does not subtract. A second call with the same note is a no-op.
    A crash after the pending marker resumes only this same operation.
    """
    _check_runtime(runtime)
    if (type(authorization_id) is not str or not authorization_id.strip()
            or type(scope_id) is not str or not scope_id.strip()
            or type(request_id) is not str or not request_id.strip()
            or type(expected_reserve_nano) is not int or expected_reserve_nano <= 0
            or type(expected_body_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_body_sha256)
            or type(operator_note) is not str or not operator_note.strip() or len(operator_note) > 500):
        _fail("finalize_refused", "arguments")
    with _registry_lock(runtime.home) as registry_path:
        registry = _read_registry(registry_path)
        if registry is None or registry["runtimes"].get(runtime.runtime_id) != authorization_id:
            _fail("finalize_refused", "authority")
        entry = registry["authorities"].get(authorization_id)
        if (type(entry) is not dict or entry.get("status") != "active" or set(entry) != {"status", "binding", "digest"}
                or _digest(entry.get("binding")) != entry.get("digest")):
            _fail("finalize_refused", "authority")
        binding = entry["binding"]
        manifest = binding.get("manifest") if type(binding.get("manifest")) is dict else {}
        path = manifest.get("canonical_absolute_ledger_path")
        if (binding.get("home") != runtime.home or binding.get("runtime_id") != runtime.runtime_id
                or manifest.get("scope_id") != scope_id or type(path) is not str):
            _fail("finalize_refused", "scope")
        with gate._with_ledger_lock(path):
            if os.path.lexists(gate._outcome_pending_path(path)):
                _fail("finalize_refused", "outcome_pending")
            pending = _finalize_pending(path)
            if pending is not None and not _same_finalize(pending, authorization_id=authorization_id, scope_id=scope_id,
                                                          request_id=request_id, expected_reserve_nano=expected_reserve_nano,
                                                          expected_body_sha256=expected_body_sha256, operator_note=operator_note):
                _fail("finalize_refused", "pending_conflict")
            data, _, _ = gate._load_ledger(path, create=False)
            if data.get("scope_id") != scope_id or data.get("ceiling_nano") != gate.TWO_DOLLAR_CEILING_NANO:
                _fail("finalize_refused", "scope")
            row = data.get("reservations", {}).get(request_id) if type(data.get("reservations")) is dict else None
            audit = _audit_entry(data, request_id)
            if _booked(row, request_id, expected_reserve_nano) and type(audit) is dict and audit.get("operator_note") == operator_note:
                if pending is not None:
                    os.unlink(_finalize_pending_path(path))
                return {"ok": True, "idempotent": True, "accounted_nano": data["accounted_nano"],
                        "attempts_total": data["control_state"]["attempts_total"], "circuit_open": data["control_state"]["circuit_open"]}
            if pending is not None and (_digest(_spend_view(data)) != pending.get("prior_state_digest")
                                         or type(row) is not dict or _row_digest(row) != pending.get("row_digest")):
                _fail("finalize_refused", "pending_digest")
            if type(row) is not dict or row.get("status") != "retained" or row.get("id") != request_id:
                _fail("finalize_refused", "request")
            if row.get("reserved_nano") != expected_reserve_nano or row.get("actual_nano") is not None:
                _fail("finalize_refused", "amount")
            digest = row.get("body_sha256")
            if digest != expected_body_sha256:
                _fail("finalize_refused", "digest")
            state = data.get("control_state") if type(data.get("control_state")) is dict else {}
            rows = data["reservations"]
            if any(other.get("status") == "reserved" for other in rows.values()):
                _fail("finalize_refused", "inflight")
            if any(key != request_id and other.get("status") != "reconciled" for key, other in rows.items()):
                _fail("finalize_refused", "other_unknown")
            if not state.get("circuit_open") or state.get("first_anomaly_id") != request_id:
                _fail("finalize_refused", "breaker")
            prior = _digest(_spend_view(data))
            row_digest = _row_digest(row)
            if pending is None:
                gate._atomic_write(_finalize_pending_path(path), gate._dump({
                    "version": 1, "op": "finalize_unknown_as_worst_case", "authority_id": authorization_id,
                    "scope_id": scope_id, "request_id": request_id, "reserve_nano": expected_reserve_nano,
                    "body_sha256": expected_body_sha256, "operator_note": operator_note,
                    "prior_state_digest": prior, "row_digest": row_digest,
                }), stage_prefix="finalize_pending_")
            accounted, attempts, ceiling = data["accounted_nano"], state["attempts_total"], data["ceiling_nano"]
            row["status"] = "reconciled"
            row["actual_nano"] = expected_reserve_nano
            previous_reason = row.get("retain_reason") or ""
            row["retain_reason"] = ""
            state["circuit_open"] = False
            state["circuit_reason"] = ""
            state["first_anomaly_id"] = ""
            if data["accounted_nano"] != accounted or state["attempts_total"] != attempts or data["ceiling_nano"] != ceiling:
                _fail("finalize_refused", "spend_changed")
            data.setdefault("worst_case_finalizations", []).append({
                "version": 1, "op": "finalize_unknown_as_worst_case", "request_id": request_id,
                "reserve_nano": expected_reserve_nano, "prior_state_digest": prior, "prior_retain_reason": previous_reason,
                "operator_note": operator_note, "runtime_id": runtime.runtime_id, "authority_id": authorization_id,
                "at": int(time.time()),
            })
            gate._atomic_write(path, gate._dump(data), stage_prefix="finalize_ledger_")
            if os.path.lexists(_finalize_pending_path(path)):
                os.unlink(_finalize_pending_path(path))
            return {"ok": True, "idempotent": False, "accounted_nano": accounted, "attempts_total": attempts, "circuit_open": False}


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
