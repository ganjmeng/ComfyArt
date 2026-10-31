"""#559: repo-wide guard — the competitor brand word must not appear anywhere under src/
(code, comments, CSS, docs). No allowlist."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PATTERN = re.compile("lov" + "art", re.IGNORECASE)


def _text_files():
    for p in sorted(SRC.rglob("*")):
        if not p.is_file():
            continue
        try:
            yield p, p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary asset


def test_src_exists():
    assert SRC.is_dir()


def test_no_brand_word_in_src():
    hits = []
    for p, text in _text_files():
        for i, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                hits.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:120]}")
    assert not hits, "brand word found under src/:\n" + "\n".join(hits)
