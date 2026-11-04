#!/usr/bin/env python3
"""#673 C-group real-chain smoke (1K, one image per skill). Default = DRY RUN: prints the exact app requests, spends nothing.
--live drives the running app exactly like the UI skill launch (src/bot.ts):
  POST /comfyart/bot/chats -> POST /comfyart/bot/chats/{id}/send {text, skill, refs, lang, run_mode}
  The server turn opens paid_guard.begin_turn (#142/#709; text says "1 张" -> guard cap 1); the agent calls the
  generate_image MCP tool (api/mcp.py -> paid_guard.before_call -> api/mcp_tools/canvas.py Auto routing -> page ->
  /comfyart/wavespeed/run). The Loomi tab for --project must be open (canvas tools execute in the page).
Before each call: free POST /comfyart/wavespeed/estimate; stop if over our estimate or spent+quote > CAP.
WaveSpeed balance (key from /home/box/.secrets/comfyart-test.env, never printed) logged before/after each call.
2 consecutive failures on one skill -> stop. --only slug[,slug]; --ref slug=URL for skills needing a photo."""
import argparse, asyncio, json, os, sys, time, urllib.request
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests")); sys.path.insert(0, str(REPO.parent))
ENV = "/home/box/.secrets/comfyart-test.env"
CAP = 0.8
MAX_FAILS = 2
EST = {"openai/gpt-image-2.5-flare/text-to-image": 0.0378, "openai/gpt-image-2.5-flare/edit": 0.0378}  # 1K, #673 C-group logs
EST_UNKNOWN = 0.10  # conservative cap for models without a recorded price (e.g. midjourney); --live checks free /model/price first
SAMPLE_REF = {  # our own washed assets on main b47b6671 (not Lovart gold, not web); all verified HTTP 200 image/webp
    "logo-abstract": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/b47b6671368581f54d8a5c9e26fd0f3548010ffc/643/wash/premium-website/examples/03.webp",  # braided bread loaf, single object
    "photo-split-poster": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/b47b6671368581f54d8a5c9e26fd0f3548010ffc/643/wash/pose-fission/examples/01.webp",  # city street, sunlit sidewalk
    "promo-ecommerce": "https://raw.githubusercontent.com/ganjmeng/ComfyArt/b47b6671368581f54d8a5c9e26fd0f3548010ffc/643/wash/product-to-packaging/examples/05.webp"}  # 3 KOIRA cans product shot (no serum in washed assets)
SK = {
 "naive-illustration": dict(preset="line", ratio=(1024, 1360), refs=False, user="一个巨大的咖啡杯，旁边一个小小的上班族在搬方糖，配一句俏皮短语\"今日续命\"",
   style="Style: naive B/W line illustration, giant object vs tiny person, witty cafe/worker energy, clean strokes."),
 "logo-abstract": dict(preset="circle", ratio=(1024, 1024), refs=True, user="把这个辫子面包提炼成一个圆形几何 logo，双色，小尺寸也能认出",
   style="Style: minimal circular geometric logo mark distilled from the photo, two-color, scalable silhouette."),
 "photo-split-poster": dict(preset="hard", ratio=(1024, 1360), refs=True, user="上半部分保留这张街景照片，下半部分用照片里的颜色做几何抽象，标题\"CITY WALK\"",
   style="Style: hard horizontal split poster, photo above, geometric abstract below, palette sampled from the photo."),
 "ppt-visual": dict(preset="cover", ratio=(1824, 1024), refs=False, user="AI 创作工具年度发布会的封面页，标题\"2027 创作新范式\"，深色科技风",
   style="Style: premium deck cover slide 16:9, strong hierarchy, short title in quotes, shared module system."),
 "promo-ecommerce": dict(preset="kv", ratio=(1024, 1360), refs=True, user="双十一大促主视觉，产品是这组罐装气泡饮，主文案\"限时直降\"，日期\"11.11\"",
   style="Style: ecommerce promo key visual, bold sale hierarchy, product hero locked from ref, claims in quotes."),
}
def load_env():
    for l in open(ENV):
        l = l.strip()
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k.replace("export ", "").strip(), v.strip().strip("\"'"))
def build(slug, refs):
    """Auto choice (same _auto_choice the generate_image tool uses) + estimate inputs + the exact UI send body."""
    s = SK[slug]; prompt = f"{s['user']}\n{s['style']}"
    from ComfyArt.api.mcp_tools import canvas
    choice = canvas._auto_choice("generate_image", {"prompt": prompt, **({"refs": refs} if refs else {})})
    inp = {"feature": "image_edit" if refs else "text_to_image", "model": choice["model"], "prompt": prompt,
           "width": s["ratio"][0], "height": s["ratio"][1], **({"images": refs} if refs else {})}
    send = {"text": f"{s['user']}，出 1 张，{s['ratio'][0]}x{s['ratio'][1]}", "skill": slug, "lang": "zh",
            "run_mode": "unattended",
            **({"refs": [{"id": f"ref-{slug}", "src": r, "name": f"{slug}-ref", "kind": "image"} for r in refs]} if refs else {})}
    return choice, inp, send
def http(base, method, path, body=None, timeout=60):
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read() or b"{}")
def images_of(messages, after_id):
    seen, out = after_id is None, []
    for m in messages:
        if seen and m.get("role") == "assistant":
            out += [b.get("url") for b in m.get("blocks") or [] if b.get("type") == "image" and b.get("url")]
        if m.get("id") == after_id: seen = True
    return out
async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true"); ap.add_argument("--only")
    ap.add_argument("--ref", action="append", default=[]); ap.add_argument("--out", default="/workspace/smoke673/out")
    ap.add_argument("--base", default="http://127.0.0.1:8188"); ap.add_argument("--project", default="PROJECT_ID")
    ap.add_argument("--provider", default="local-llm"); ap.add_argument("--turn-timeout", type=int, default=600)
    a = ap.parse_args(); import conftest; conftest._install_stubs()
    refmap = dict(SAMPLE_REF, **dict(r.split("=", 1) for r in a.ref))
    slugs = a.only.split(",") if a.only else list(SK)
    plan = []
    for sl in slugs:
        refs = [refmap[sl]] if SK[sl]["refs"] else None
        choice, inp, send = build(sl, refs); est = EST.get(inp["model"], EST_UNKNOWN); plan.append((sl, inp, send, est))
        chat_body = {"project": a.project, "provider": a.provider, "title": f"smoke673 {sl}", "run_mode": "auto"}
        print(json.dumps({"skill": sl, "auto_model": inp["model"], "auto_reason": (choice.get("reason") or {}).get("en"), "est_usd": est,
            "requests": [
              {"method": "POST", "url": f"{a.base}/comfyart/wavespeed/estimate", "body": {"inputs": inp}, "note": "free quote"},
              {"method": "POST", "url": f"{a.base}/comfyart/bot/chats", "body": chat_body},
              {"method": "POST", "url": f"{a.base}/comfyart/bot/chats/{{chat_id}}/send", "body": send, "note": "paid when --live (paid_guard cap 1)"},
              {"method": "GET", "url": f"{a.base}/comfyart/bot/chats/{{chat_id}}", "note": "poll until chat.busy=false"}]},
            ensure_ascii=False, indent=1))
    total = sum(p[3] for p in plan); print(f"TOTAL est ${total:.4f} (cap ${CAP})")
    if total > CAP: sys.exit("over cap")
    if not a.live: print("DRY RUN — nothing submitted. Use --live to spend."); return
    if a.project == "PROJECT_ID": sys.exit("--project <id> required (open that project in the Loomi tab)")
    if any(str(r).startswith("REF_") for _, i, _, _ in plan for r in i.get("images", [])): sys.exit("replace REF_ placeholders via --ref")
    load_env(); from ComfyArt.api import wavespeed as ws
    key = os.environ["WAVESPEED_API_KEY"]; out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    spent, log = 0.0, []
    for sl, inp, send, est in plan:
        fails = 0
        while fails < MAX_FAILS:
            q = http(a.base, "POST", "/comfyart/wavespeed/estimate", {"inputs": inp})
            price = q.get("price") if isinstance(q, dict) else None
            if price is None or price > est: sys.exit(f"{sl}: quote {q} over estimate ${est}, stop")
            if spent + price > CAP: sys.exit(f"{sl}: spent ${spent:.4f} + ${price} > cap ${CAP}, stop")
            b0 = await ws.fetch_balance(key)
            chat = http(a.base, "POST", "/comfyart/bot/chats", {"project": a.project, "provider": a.provider, "title": f"smoke673 {sl}", "run_mode": "auto"})["chat"]
            r = http(a.base, "POST", f"/comfyart/bot/chats/{chat['id']}/send", send)
            uid = (r.get("user_message") or {}).get("id"); t0 = time.time()
            while True:
                await asyncio.sleep(5); st = http(a.base, "GET", f"/comfyart/bot/chats/{chat['id']}")
                if not st["chat"].get("busy") or time.time() - t0 > a.turn_timeout: break
            if st["chat"].get("busy"): http(a.base, "POST", f"/comfyart/bot/chats/{chat['id']}/stop", {})
            await asyncio.sleep(5); b1 = await ws.fetch_balance(key)
            charged = round(b0 - b1, 6) if b0 is not None and b1 is not None else price; spent += max(charged, 0)
            imgs = images_of(st["messages"], uid); ok = bool(imgs)
            rec = {"skill": sl, "chat": chat["id"], "quote": price, "balance_before": b0, "balance_after": b1,
                   "charged": charged, "spent": round(spent, 6), "images": imgs, "ok": ok}
            log.append(rec); print(json.dumps(rec, ensure_ascii=False))
            json.dump(log, open(out / "runs.json", "w"), ensure_ascii=False, indent=1, default=str)
            if ok: break
            fails += 1
        if fails >= MAX_FAILS: sys.exit(f"{sl}: {MAX_FAILS} consecutive failures, stop")
    print(f"DONE spent ${spent:.4f} (est ${total:.4f}, cap ${CAP})")
if __name__ == "__main__": asyncio.run(main())
