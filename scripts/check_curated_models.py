#!/usr/bin/env python3
"""Check api/curated_models.json against the LIVE WaveSpeed catalog (#95).

Read-only: one GET {base}/api/v3/models (the same free list endpoint api/wavespeed.py uses).
Never submits predictions/generations. Not used by pytest (tests are fixture-only).

Key: $WAVESPEED_API_KEY, else WAVESPEED_API_KEY=... in --env-file
(default ~/.config/comfyart/wavespeed.env). The key is never printed.

  python scripts/check_curated_models.py                 # report, exit 1 on any failure
  python scripts/check_curated_models.py --update-fixture  # also add curated ids to the test fixture
"""
import argparse, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURATED = os.path.join(ROOT, "api", "curated_models.json")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "wavespeed_catalog_subset.json")


def read_key(env_file: str) -> str:
    if os.environ.get("WAVESPEED_API_KEY"):
        return os.environ["WAVESPEED_API_KEY"].strip()
    try:
        for line in open(os.path.expanduser(env_file), encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k.strip() == "WAVESPEED_API_KEY":
                return v.strip().strip('"\'')
    except OSError:
        pass
    sys.exit("no WaveSpeed key (set WAVESPEED_API_KEY or --env-file)")


def fetch_catalog(key: str, base: str) -> dict:
    req = urllib.request.Request(f"{base}/api/v3/models", method="GET", headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    data = body.get("data") if isinstance(body, dict) else body
    return {m["model_id"]: m for m in data or [] if isinstance(m, dict) and "model_id" in m}


def props(meta: dict) -> dict:
    try:
        return meta["api_schema"]["api_schemas"][0]["request_schema"].get("properties") or {}
    except (KeyError, IndexError, TypeError, AttributeError):
        return {}


def trim(meta: dict) -> dict:
    """Fixture form: name, price, description, and per-field enum/maxItems only."""
    p = {k: {a: v[a] for a in ("enum", "maxItems") if isinstance(v, dict) and a in v} for k, v in props(meta).items()}
    out = {"api_schema": {"api_schemas": [{"request_schema": {"properties": p}}]}}
    out.update({k: meta[k] for k in ("base_price", "description", "model_id", "name") if k in meta})
    return out


def check(curated: dict, catalog: dict) -> list[str]:
    """Return failure lines; prints one line per curated id."""
    fails = []
    for feature, cur in curated.items():
        for i, mid in enumerate(cur["models"]):
            tag = "★" if i == 0 else " "
            meta = catalog.get(mid)
            if not meta:
                fails.append(f"{feature}: {mid} not in live catalog")
                print(f"FAIL {tag} {feature:24} {mid}  (missing)")
                continue
            missing = [n for n in cur.get("needs", []) if n not in props(meta)]
            if missing:
                fails.append(f"{feature}: {mid} lacks fields {missing}")
                print(f"FAIL {tag} {feature:24} {mid}  (lacks {missing})")
            else:
                print(f"ok   {tag} {feature:24} {mid}  ${meta.get('base_price')}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", default="~/.config/comfyart/wavespeed.env")
    ap.add_argument("--base", default=os.environ.get("WAVESPEED_BASE_URL", "https://api.wavespeed.ai"))
    ap.add_argument("--update-fixture", action="store_true")
    a = ap.parse_args()
    curated = json.load(open(CURATED, encoding="utf-8"))["features"]
    catalog = fetch_catalog(read_key(a.env_file), a.base.rstrip("/"))
    print(f"live catalog: {len(catalog)} models")
    fails = check(curated, catalog)
    if a.update_fixture:
        fx = json.load(open(FIXTURE, encoding="utf-8"))
        for cur in curated.values():
            for mid in cur["models"]:
                if mid in catalog and mid not in fx:
                    fx[mid] = trim(catalog[mid])
        with open(FIXTURE, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(fx.items())), f, indent=0, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        print(f"fixture: {len(fx)} models")
    print(f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
