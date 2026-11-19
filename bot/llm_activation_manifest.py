"""Offline activation-manifest validation, NOT activation or billing evidence.

A validated receipt alone never binds the transport, creates/migrates a scope,
reserves funds, or replaces structural/input proof. llm_scope_activation supplies
separate explicit durable activation and runtime revalidation; reservation still
happens under the ledger lock. This read-only receipt is not a lease.

The expected context comes from independently reviewed configuration, not from
copying fields out of the candidate manifest. Matching evidence hashes records
identity, not proof that supplier error-path billing is bounded or that a user
accepted risk. No signature / same-account tamper-resistance claim is made.
One expected authorization binds one canonical path; cross-process uniqueness
is enforced by the separate deployment-home activation registry, not this helper.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from . import llm_usd_gate as gate


class ManifestInvalid(ValueError):
    """Candidate or existing scope does not match the reviewed offline context."""


@dataclass(frozen=True)
class ManifestContext:
    authorization_id: str
    validation_run_id: str
    scope_id: str
    canonical_absolute_ledger_path: str
    policy_hash: str
    evidence_hash: str
    # Immutable pairs of official source URL and hash of reviewed source bytes.
    sources: tuple[tuple[str, str], ...]
    # Exactly one: ("reviewed_sha", 40-hex) or ("approved_runtime_sha256", 64-hex).
    runtime_binding: tuple[str, str]
    risk_mode: str
    # All default client MCP function names, not a reduced substitute inventory.
    tool_allowlist: tuple[str, ...]
    max_posts: int
    route_url: str


@dataclass(frozen=True)
class ValidatedManifest:
    """Identity-only receipt. Not a send permit, scope activation, or input bound."""
    authorization_id: str
    validation_run_id: str
    scope_id: str
    canonical_absolute_ledger_path: str
    manifest_sha256: str


def _require(condition: bool, field: str) -> None:
    if not condition:
        # Never include candidate values: no credentials/body text in errors.
        raise ManifestInvalid(field)


def _text(value) -> bool:
    return type(value) is str and bool(value.strip()) and value == value.strip()


def _hex(value, length: int = 64) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{%d}" % length, value) is not None


def _names(value) -> bool:
    return type(value) is list and all(_text(v) for v in value) and len(value) == len(set(value))


def validate_manifest(candidate: dict, *, expected: ManifestContext,
                      now: float | None = None) -> ValidatedManifest:
    """Validate schema + independently expected identity, without touching disk.

    v1 requires the documented $2 / explicit 1..6 POST / one-inflight profile.
    No lifetime is invented: optional expires_at is a Unix-second expiry and is
    enforced when present. Caller-supplied now exists for deterministic offline
    tests; production callers must not substitute an old clock.
    """
    _require(type(candidate) is dict and type(expected) is ManifestContext, "manifest_shape")
    required = {"version", "authorization_id", "validation_run_id", "scope_id",
                "canonical_absolute_ledger_path", "model_pin", "route_url", "price_snapshot",
                "policy_hash", "evidence_hash", "sources", "runtime_binding", "risk_mode",
                "scope_limits", "capabilities", "tool_allowlist"}
    _require(required <= candidate.keys() <= required | {"expires_at"}, "manifest_fields")
    # Validate a private JSON snapshot: a caller changing a mutable candidate
    # during filesystem checks must not change the identity in our receipt.
    try:
        encoded = json.dumps(candidate, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        c = json.loads(encoded)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ManifestInvalid("manifest_json") from exc
    _require(type(c["version"]) is int and c["version"] == 1, "version")
    for key in ("authorization_id", "validation_run_id", "scope_id"):
        _require(_text(c[key]) and c[key] == getattr(expected, key), key)
    path = c["canonical_absolute_ledger_path"]
    _require(_text(path) and os.path.isabs(path), "ledger_path")
    try:
        canonical = os.path.realpath(path)
    except (OSError, ValueError) as exc:
        raise ManifestInvalid("ledger_path") from exc
    _require(canonical == path and path == expected.canonical_absolute_ledger_path, "ledger_path")
    for key in ("policy_hash", "evidence_hash"):
        _require(_hex(c[key]) and c[key] == getattr(expected, key), key)
    _require(c["risk_mode"] in ("strict_contract_evidence", "risk_accepted_context_contract")
             and c["risk_mode"] == expected.risk_mode, "risk_mode")
    binding = c["runtime_binding"]
    _require(type(binding) is dict and len(binding) == 1, "runtime_binding")
    key = next(iter(binding))
    _require(key in ("reviewed_sha", "approved_runtime_sha256")
             and _hex(binding[key], 40 if key == "reviewed_sha" else 64)
             and (key, binding[key]) == expected.runtime_binding, "runtime_binding")
    limits = c["scope_limits"]
    _require(type(limits) is dict and set(limits) == {"amount_nano", "max_posts", "max_inflight"}, "scope_limits")
    post_cap = (gate.CONTROLLED_POSTS_EXTENDED_HARD_CAP
                if limits["amount_nano"] == gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO
                else gate.CONTROLLED_POSTS_HARD_CAP)
    _require(all(type(v) is int for v in limits.values())
             and limits["amount_nano"] in (gate.TWO_DOLLAR_CEILING_NANO, gate.FIVE_DOLLAR_EXTENDED_CEILING_NANO)
             and 1 <= limits["max_posts"] <= post_cap
             and type(expected.max_posts) is int and limits["max_posts"] == expected.max_posts
             and limits["max_inflight"] == 1, "scope_limits")
    url = c["route_url"]
    _require(type(url) is str, "route_url")
    # Exact URL matching also rejects credentials, ports, query and redirects.
    _require(url in ("https://api.deepseek.com/chat/completions",
                     "https://api.deepseek.com/v1/chat/completions")
             and url == expected.route_url, "route_url")
    snapshot = gate.price_snapshot("deepseek-flash")
    _require(c["model_pin"] == {"model": snapshot["model"], "version": snapshot["version"]}, "model_pin")
    # JSON equality alone treats True == 1; canonical serialization is type-exact.
    try:
        actual_price = json.dumps(c["price_snapshot"], sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ManifestInvalid("price_snapshot") from exc
    _require(actual_price == json.dumps(snapshot, sort_keys=True, allow_nan=False), "price_snapshot")
    sources = c["sources"]
    _require(type(sources) is list and bool(sources), "sources")
    pairs = []
    for source in sources:
        _require(type(source) is dict and set(source) == {"url", "sha256"}, "sources")
        source_url = source["url"]
        _require(type(source_url) is str, "sources")
        try:
            parsed = urlsplit(source_url)
        except ValueError as exc:
            raise ManifestInvalid("sources") from exc
        _require(parsed.scheme == "https" and parsed.netloc == "api-docs.deepseek.com"
                 and bool(parsed.path) and not parsed.query and not parsed.fragment
                 and _hex(source["sha256"]), "sources")
        pairs.append((source_url, source["sha256"]))
    _require(len(set(pairs)) == len(pairs) and len({p[0] for p in pairs}) == len(pairs)
             and set(pairs) == set(expected.sources), "sources")
    capabilities = c["capabilities"]
    _require(type(capabilities) is dict and set(capabilities) == {"client_mcp", "images", "thinking"}
             and all(v is True for v in capabilities.values()), "capabilities")
    _require(_names(c["tool_allowlist"]) and bool(expected.tool_allowlist)
             and set(c["tool_allowlist"]) == set(expected.tool_allowlist), "tool_allowlist")
    if "expires_at" in c:
        clock = time.time() if now is None else now
        _require(type(clock) in (int, float) and math.isfinite(clock)
                 and type(c["expires_at"]) is int and c["expires_at"] > clock, "expires_at")
    return ValidatedManifest(c["authorization_id"], c["validation_run_id"], c["scope_id"], path,
                             hashlib.sha256(encoded).hexdigest())


def validate_existing_scope(candidate: dict, *, expected: ManifestContext,
                            now: float | None = None) -> ValidatedManifest:
    """Read under the existing stable lock; never create/migrate/bind/reset funds.

    Missing/empty/mismatched scope never falls back to default. Existing counts,
    holds and breaker must remain unchanged. This does not grant authority for
    future sends or promise the ledger state cannot change after lock release.
    """
    receipt = validate_manifest(candidate, expected=expected, now=now)
    try:
        state = gate.ledger_state(receipt.canonical_absolute_ledger_path)
    except (OSError, gate.LlmBudgetBlocked) as exc:
        raise ManifestInvalid("existing_scope_unreadable") from exc
    limits = {"amount_nano": gate.TWO_DOLLAR_CEILING_NANO,
              "max_posts": expected.max_posts, "max_inflight": 1}
    _require(state["scope_id"] == receipt.scope_id
             and state["authorization"] == gate.TWO_DOLLAR_AUTHORIZATION
             and state["authorized_ceiling_nano"] == limits["amount_nano"]
             and state["ceiling_nano"] == limits["amount_nano"]
             and state.get("control_limits") == {"version": 1, **limits}, "existing_scope_mismatch")
    _require(not state["control_state"]["circuit_open"] and not state["inflight"], "existing_scope_stopped")
    return receipt
