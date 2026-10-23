"""#40 guard: no local-model call residue in api/, bot/, src/.

ComfyUI as plugin host (PromptServer, routes, 8188, the host ComfyUI workflow
MCP tools, custom_workflow) is allowed and is not scanned for.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ["api", "bot", "src"]
SKIP_PARTS = {"node_modules", "dist", "tests", "docs", "__pycache__"}
EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json"}

PATTERNS = [
    re.compile(r"\.safetensors"),
    re.compile(r"MOSS-Image"),
    re.compile(r"Pixal3D"),
    # loading a local workflows/*.api.json for inference
    re.compile(r"workflows[/\\\\][^\s'\"]*\.api\.json"),
]

# (relative path, substring on the line) -> reason. Keep small and explicit.
ALLOWLIST = {
    # LoRA picker strips the extension from cloud LoRA names for display only.
    ("src/loras.ts", "replace(/\\.safetensors$/, '')"): "display label, no local load",
    # Toolbar label kept from upstream; routes to cloud tripo3d multiview model.
    ("src/ui/ImageToolbar.tsx", 'label="Pixal3D"'): "UI label, cloud model",
    # Mapping metadata naming the upstream local model this cloud id replaces.
    ("api/wavespeed_models.json", '"local": "Pixal3D multiview"'): "mapping note",
    # i18n hint text for the multi-view 3D tool (cloud-backed).
    ("src/locales/zh.json", "Pixal3D"): "UI text",
    ("src/locales/en.json", "Pixal3D"): "UI text",
}


def _allowed(rel, line):
    return any(rel == p and s in line for (p, s) in ALLOWLIST)


def test_no_local_model_residue():
    hits = []
    for d in SCAN_DIRS:
        for f in (ROOT / d).rglob("*"):
            if not f.is_file() or f.suffix not in EXTS:
                continue
            if SKIP_PARTS & set(f.relative_to(ROOT).parts):
                continue
            rel = f.relative_to(ROOT).as_posix()
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if any(p.search(line) for p in PATTERNS) and not _allowed(rel, line):
                    hits.append(f"{rel}:{n}: {line.strip()[:160]}")
    for h in hits:
        print(h)
    assert not hits, "local-model residue found:\n" + "\n".join(hits)
