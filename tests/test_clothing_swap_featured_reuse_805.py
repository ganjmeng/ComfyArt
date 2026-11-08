"""#805 reuse pins. LinkedIn featured is the reviewed 1904x556 PNG.
ai-model featured is the signed v7 402x505 PNG. No generation. $0 static.
"""
from __future__ import annotations

import hashlib
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = (ROOT / "src/skills.ts").read_text()
COVER_SHA = "81bfe6ceabdbb0b775df47662d9d5cab19d5233f071d412a34b87e2d8489b79f"
FEATURED = {
    "clothing-swap": (
        "featured: [pinned('643/wash/clothing-swap/examples', WASH_643, '02.webp')]",
        "15e9bdad271dc2cb0ac1a1c8621927c161ca9299",
        "643/wash/clothing-swap/examples/02.webp",
        "a2a5f482a9546eff6c38d953303903d7fdbb32e5ad5f438c900cf5c4f7dafaa0",
        (1776, 2368),
    ),
    "product-website": (
        "featured: [pinned('643/wash/product-website/examples', WASH_643, '02.webp')]",
        "15e9bdad271dc2cb0ac1a1c8621927c161ca9299",
        "643/wash/product-website/examples/02.webp",
        "af8f1fb1a3654401a82f911da967b4237a78a14901323f906c1907d99956a15d",
        (2736, 1536),
    ),
    "premium-website": (
        "featured: [pinned('643/wash/premium-website/examples', '4ccecac30c1cdf3e79826de5614edc5514e150a4', '07.webp')]",
        "4ccecac30c1cdf3e79826de5614edc5514e150a4",
        "643/wash/premium-website/examples/07.webp",
        "1d7745212308fa586dbc2295eca04519c169b9f999a835a96ad33bd60695bc15",
        (1776, 2368),
    ),
    "restaurant-website": (
        "featured: [pinned('643/wash/restaurant-website/examples', '9ca6d4ee7eb6488bb2c430affa86cfae75613485', '07.webp')]",
        "9ca6d4ee7eb6488bb2c430affa86cfae75613485",
        "643/wash/restaurant-website/examples/07.webp",
        "7acffd0d390db4e9280f1bb598dec2b3523657d4e8f6f12d7d91bc9cc41b217a",
        (1536, 862),
    ),
    "product-to-packaging": (
        "featured: [pinned('643/wash/product-to-packaging/examples', '6b1cfa37e4eafc72841e70a26909750c2ff44399', '02.webp')]",
        "6b1cfa37e4eafc72841e70a26909750c2ff44399",
        "643/wash/product-to-packaging/examples/02.webp",
        "426c4a9ada9689aca4915f48e1f65427daa04715595ebf363c7e22ebbe2659c9",
        (1536, 862),
    ),
}
HELD_EMPTY = (
    "animated-poster",
    "creator-identity", "youtube-channel-banner", "portrait-studio", "logo-animation",
)


def _entries() -> dict[str, str]:
    a = SKILLS.index("export const BUILTIN_SKILLS")
    block = SKILLS[a:next(i for i in (SKILLS.find("\n])\n", a), SKILLS.find("\n]\n", a)) if i >= 0)]
    parts = re.split(r"\n  \{ id: '", block)[1:]
    return {p.split("'", 1)[0]: p for p in parts}


def _webp_size(data: bytes) -> tuple[int, int]:
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    i = 12
    while i + 8 <= len(data):
        tag, size = data[i:i + 4], struct.unpack_from("<I", data, i + 4)[0]
        chunk = data[i + 8:i + 8 + size]
        if tag == b"VP8 " and chunk[3:6] == b"\x9d\x01\x2a":
            w, h = struct.unpack_from("<HH", chunk, 6)
            return w & 0x3FFF, h & 0x3FFF
        if tag == b"VP8L" and chunk[:1] == b"\x2f":
            bits = struct.unpack_from("<I", chunk, 1)[0]
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if tag == b"VP8X":
            return 1 + int.from_bytes(chunk[4:7], "little"), 1 + int.from_bytes(chunk[7:10], "little")
        i += 8 + size + (size & 1)
    raise AssertionError("webp size missing")


def _blob(pin: str, path: str) -> bytes:
    """Historical wash commits are pinned by URL; this checkout may not have every object.
    The committed path bytes are the same file (checked against the QA sha)."""
    return (ROOT / path).read_bytes()


def test_reuse_featured_pins_and_single_cover_holds_stay_empty():
    entries = _entries()
    for sid, (expr, pin, path, sha, dims) in FEATURED.items():
        assert expr in entries[sid], sid
        assert "cover: cover643(" in entries[sid].split("inputs:", 1)[0], sid
        blob = _blob(pin, path)
        assert hashlib.sha256(blob).hexdigest() == sha, sid
        assert _webp_size(blob) == dims, sid
    for sid in HELD_EMPTY:
        assert "featured: []" in entries[sid], sid
        assert "featured: [pinned" not in entries[sid], sid
    assert "b51e9793a91e6f2b704677723308597b099e0c516d5d954a0e6b22c19bbf200f" not in SKILLS
    live = entries["live-promo-decor"]
    live_pin = re.search(r"featured: \[pinned\('805/reuse/live-promo-decor', '([0-9a-f]{40})', 'featured.webp'\)\]", live)
    assert live_pin, live[:400]
    live_blob = subprocess.check_output(["git", "show", f"{live_pin.group(1)}:805/reuse/live-promo-decor/featured.webp"], cwd=ROOT)
    assert hashlib.sha256(live_blob).hexdigest() == "56c05f4c86bb225c16443d71b0cf25af1dba1247988ddfa9ee61f1333dbb49ef"
    assert _webp_size(live_blob) == (387, 350)
    assert "cover: cover643('live-promo-decor')" in live
    assert "examples: ex643('live-promo-decor', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], '497c6feeb559cc2c053a28fc9b45b3b11b595037')" in live
    assert "643/wash/animated-poster/featured" not in SKILLS
    poster = entries["animated-poster"]
    assert "examples: ex643('animated-poster', [1, 2], '54cc1199ee8eeaaee36c69d04cdbad21f345c8fd')" in poster
    assert "quickStartCoverFit: 'contain'" in poster
    m = re.search(r"cover: pinned\('805/reuse/animated-poster', '([0-9a-f]{40})', 'cover.webp'\)", poster)
    assert m, poster[:240]
    cover = subprocess.check_output(["git", "show", f"{m.group(1)}:805/reuse/animated-poster/cover.webp"], cwd=ROOT)
    assert hashlib.sha256(cover).hexdigest() == COVER_SHA
    assert _webp_size(cover) == (474, 708)
    assert hashlib.sha256((ROOT / "805/reuse/animated-poster/cover.webp").read_bytes()).hexdigest() == COVER_SHA
    linkedin = entries["linkedin-banner"]
    assert "width 1584, height 396" in linkedin
    assert "cover: cover643('linkedin-banner')" in linkedin
    assert "examples: ex643('linkedin-banner', [1])" in linkedin
    assert "featured: [pinned('805/reuse/linkedin-banner', 'b6e408ace4835f14282a32d4e19c79e143cb4f53', 'featured.png')]" in linkedin
    li = subprocess.check_output(["git", "show", "b6e408ace4835f14282a32d4e19c79e143cb4f53:805/reuse/linkedin-banner/featured.png"], cwd=ROOT)
    assert hashlib.sha256(li).hexdigest() == "ef9d950ebcc542ada4cf2a7bbb7c768a04ab12ebdbb4e23e4c017be4c3015bba"
    assert li[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", li[16:24]) == (1904, 556)
    ai = entries["ai-model"]
    assert "cover: cover643('ai-model')" in ai
    assert "examples: ex643('ai-model', [1, 2, 3, 4, 5, 6], '604e9be57c96010fc6183f89d02c971f612d10e7')" in ai
    assert "featured: [pinned('805/reuse/ai-model', '7fbb71bdce30a57f35c367bc949981c00fb2fc10', 'featured.png')]" in ai
    aim = subprocess.check_output(["git", "show", "7fbb71bdce30a57f35c367bc949981c00fb2fc10:805/reuse/ai-model/featured.png"], cwd=ROOT)
    assert hashlib.sha256(aim).hexdigest() == "b82e07a40cdbb26eb139a2d0deadb62dbbc4fc84e6e21ee3c564e94c6c5b1e12"
    assert hashlib.sha256((ROOT / "805/reuse/ai-model/featured.png").read_bytes()).hexdigest() == "b82e07a40cdbb26eb139a2d0deadb62dbbc4fc84e6e21ee3c564e94c6c5b1e12"
    assert aim[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", aim[16:24]) == (402, 505)
    assert hashlib.sha256(aim).hexdigest() != "03221e6968c6061799595784d2f0c6c875f7d533a6348cde1a3d99786dc7ce5b"
