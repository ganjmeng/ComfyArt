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


# Exact reviewed git hops. They are not file hashes, and there is no wildcard.
# Provenance stores the pair the caller names. The loaded source hash is this
# process tree, which changes when api/ or bot/ bytes change, so it is not the
# tree of the "to" commit.
# Pair 1: original protocol review. Pair 2: deployed 42413ac7 -> the commit that
# added resolve_unknown_as_spent. The second commit SHA is filled by the commit
# immediately after that addition; until then the placeholder is not a real tip.
REVIEWED_GIT_PAIRS = (
    ("571c7fb7184dc4e97c115429bd6859d445e98c21", "c3d3820e998985c678feea74a47ab4613946b761"),
    ("42413ac72626671a1790dbed87544f9f32ebaedf", "e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7"),
)
REVIEWED_FROM_GIT = REVIEWED_GIT_PAIRS[0][0]
REVIEWED_PROTOCOL_GIT = REVIEWED_GIT_PAIRS[0][1]
REVIEWED_DEPLOYED_GIT = REVIEWED_GIT_PAIRS[1][0]
REVIEWED_RESOLVE_GIT = REVIEWED_GIT_PAIRS[1][1]


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
