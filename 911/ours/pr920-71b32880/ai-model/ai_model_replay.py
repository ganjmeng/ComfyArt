#!/usr/bin/env python3
"""$0 ai-model replay through the product generate_image path (canvas._relay_run).

submit_command (the page relay that would start the WaveSpeed job) is replaced by a
recorder, so nothing is submitted. No WaveSpeed key in this process. Usage:
  CAPTURE_REPO=<repo> python ai_model_replay.py <out.json>
"""
import asyncio, json, os, sys, tempfile, types
from pathlib import Path
for k in ("WAVESPEED_API_KEY", "KIE_API_KEY", "REPLICATE_API_TOKEN", "DEEPSEEK_API_KEY"):
    os.environ.pop(k, None)
os.environ["TURN"] = "studio-model"  # only to import the shared stubs from run_zero
sys.path.insert(0, str(Path(__file__).parent))
import run_zero as rz

SIZE_KEYS = ("model", "edit_model", "auto_model", "width", "height", "ratio", "resolution",
             "edit_resolution", "size_lock", "size_candidates", "count")
SIZES = [{}, {"ratio": "3:4", "width": 1536, "height": 2048}, {"ratio": "1:1", "width": 1024, "height": 1024},
         {"ratio": "16:9", "width": 2048, "height": 1152}, {"ratio": "3:4"}, {"width": 1024, "height": 1536},
         {"ratio": "3:4", "width": 1536, "height": 2048, "size_lock": True}]


async def main(out: Path) -> None:
    base = Path(tempfile.mkdtemp(prefix="ca-aimodel-replay-"))
    for sub in ("input", "output", "temp", "user"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("COMFYART_SKIP_KEY_CHECK", "1")
    rz._install_stubs(base)
    rz.bind_comfyart()
    from ComfyArt.api import wavespeed
    from ComfyArt.api.mcp_tools import canvas
    cat = json.loads(Path("/workspace/911-clothing-capture/pr919-ef13a681/ws-catalog.json").read_text())

    async def _cat(refresh=False):
        return cat
    wavespeed.catalog = _cat

    async def _blocked(*a, **k):
        raise RuntimeError("blocked: no WaveSpeed submit in $0 replay")
    wavespeed.submit = _blocked
    captured = []

    async def fake_submit(action, args, project, timeout, chat=None):
        captured.append(json.loads(json.dumps(args, default=str)))
        return {"ids": ["x"], "model": args.get("edit_model") or args.get("model") or "", "stubbed": True}
    canvas.submit_command = fake_submit
    rows = []
    for refk in ("none", "refs", "base"):
        for size in SIZES:
            args = {"prompt": "AI model wearing the reference outfit, studio photo", "skill": "ai-model", **size}
            if refk == "refs":
                args["refs"] = ["shape:r1"]
            if refk == "base":
                args["base"] = "shape:b"
            n = len(captured)
            res = await canvas._relay_run("generate_image", dict(args), "", 30)
            sent = captured[n] if len(captured) > n else None
            rows.append({"ref": refk, "in": size,
                         "sent": None if sent is None else {k: sent[k] for k in SIZE_KEYS if k in sent},
                         "model_choice": None if sent is None else {k: (sent.get("model_choice") or {}).get(k) for k in ("model", "category", "skill")},
                         "result_status": res.get("status") if isinstance(res, dict) else None})
    out.write_text(json.dumps({"repo": str(rz.REPO), "tip": rz.TIP, "via": "canvas._relay_run (apply_generate -> select_model/_auto_choice -> _pin_args -> submit_command recorder)",
                               "rows": rows, "wavespeed_submit_called": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(rz.TIP, len(rows), sum(1 for r in rows if r["sent"]))

asyncio.run(main(Path(sys.argv[1])))
