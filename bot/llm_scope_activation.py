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


def _write_registry(path, data):
    gate._atomic_write(path, gate._dump(data), stage_prefix="registry_")
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
