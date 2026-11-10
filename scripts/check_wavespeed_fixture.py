#!/usr/bin/env python3
"""Compare tests/fixtures/wavespeed_catalog_subset.json with the LIVE WaveSpeed catalog.

Read-only: one GET {base}/api/v3/models (the same free list endpoint api/wavespeed.py uses).
Never submits predictions or generations. Not used by pytest or CI.

Key: $WAVESPEED_API_KEY, else WAVESPEED_API_KEY=... in --env-file
(default ~/.config/comfyart/wavespeed.env). The key is never printed.

  python scripts/check_wavespeed_fixture.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "wavespeed_catalog_subset.json")
# These two are the #828 exact-size models. Their live `size` field must stay in the fixture.
FOCUS = (
    "wavespeed-ai/qwen-image-2.0/edit",
    "wavespeed-ai/qwen-image-2.0/text-to-image",
)
SIZE_KEYS = ("default", "description", "enum", "maximum", "minimum", "type", "x-hidden")


def read_key(env_file: str) -> str:
    if os.environ.get("WAVESPEED_API_KEY"):
        return os.environ["WAVESPEED_API_KEY"].strip()
    try:
        with open(os.path.expanduser(env_file), encoding="utf-8") as fh:
            for line in fh:
                k, _, v = line.strip().partition("=")
                if k.strip() == "WAVESPEED_API_KEY":
                    return v.strip().strip("\"'")
    except OSError:
        pass
    sys.exit("no WaveSpeed key (set WAVESPEED_API_KEY or --env-file)")


def fetch_catalog(key: str, base: str) -> dict:
    req = urllib.request.Request(
        f"{base}/api/v3/models", method="GET", headers={"Authorization": f"Bearer {key}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f"catalog GET failed: HTTP {e.code}")
    except urllib.error.URLError as e:
        sys.exit(f"catalog GET failed: {type(e.reason).__name__ if e.reason else type(e).__name__}")
    data = body.get("data") if isinstance(body, dict) else body
    return {m["model_id"]: m for m in data or [] if isinstance(m, dict) and "model_id" in m}


def size_of(meta: dict | None) -> dict | None:
    if not meta:
        return None
    try:
        props = meta["api_schema"]["api_schemas"][0]["request_schema"].get("properties") or {}
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    spec = props.get("size")
    return spec if isinstance(spec, dict) else None


def clip(spec: dict | None) -> dict | None:
    if spec is None:
        return None
    return {k: spec[k] for k in SIZE_KEYS if k in spec}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", default="~/.config/comfyart/wavespeed.env")
    ap.add_argument("--base", default=os.environ.get("WAVESPEED_BASE_URL", "https://api.wavespeed.ai"))
    a = ap.parse_args()
    fixture = json.load(open(FIXTURE, encoding="utf-8"))
    catalog = fetch_catalog(read_key(a.env_file), a.base.rstrip("/"))
    print(f"live catalog: {len(catalog)} models; fixture: {len(fixture)} models")
    fails: list[str] = []
    for mid in FOCUS:
        live = clip(size_of(catalog.get(mid)))
        fx = clip(size_of(fixture.get(mid)))
        if mid not in catalog:
            fails.append(f"{mid}: missing from live catalog")
            print(f"FAIL {mid}  (missing from live catalog)")
            continue
        if mid not in fixture:
            fails.append(f"{mid}: missing from fixture")
            print(f"FAIL {mid}  (missing from fixture)")
            continue
        if live != fx:
            fails.append(f"{mid}: size {fx} != live {live}")
            print(f"FAIL {mid}  fixture {fx} != live {live}")
        else:
            hidden = " x-hidden" if (live or {}).get("x-hidden") else ""
            print(f"ok   {mid}  size{hidden} {live}")
    # Informational: other fixture models whose size x-hidden flag disagrees with live.
    extras = 0
    for mid, meta in fixture.items():
        if mid in FOCUS:
            continue
        live_meta = catalog.get(mid)
        if not live_meta:
            continue
        fx_h = bool((size_of(meta) or {}).get("x-hidden"))
        live_h = bool((size_of(live_meta) or {}).get("x-hidden"))
        if fx_h != live_h:
            extras += 1
            print(f"note {mid}  fixture x-hidden={fx_h} live x-hidden={live_h}")
    if extras:
        print(f"{extras} other fixture model(s) differ on size x-hidden (informational, not a failure)")
    print(f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
