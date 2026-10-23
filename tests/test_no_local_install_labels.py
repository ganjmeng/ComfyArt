"""#119: the upstream "model will download on first use" / "not installed" labels must not come back (cloud only)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERN = re.compile(r"modelWillDownloadOnFirst|modelPrefs\.notInstalled|Model will download on first use|首次使用会下载模型|Not installed|未安装")


def _hits(folder: str) -> list[str]:
    base = ROOT / folder
    if not base.exists():
        return []
    return [f"{p.relative_to(ROOT)}:{i}" for p in base.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx", ".js", ".json", ".css", ".html"}
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1) if PATTERN.search(line)]


def test_src_has_no_local_install_labels():
    assert _hits("src") == []


def test_dist_has_no_local_install_labels():
    assert _hits("dist") == []
