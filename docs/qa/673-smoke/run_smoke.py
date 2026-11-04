#!/usr/bin/env python3
"""#673 C-group real-chain smoke (1K, one run per skill). Default = DRY RUN: prints requests, spends nothing.
--live  submits via WaveSpeed (reads key from /home/box/.secrets/comfyart-test.env, never printed), logs balance.
--only slug[,slug]  restrict skills.  Refs: pass --ref slug=URL (public image URL) for skills that need a photo."""
import argparse, asyncio, json, os, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests")); sys.path.insert(0, str(REPO.parent))
ENV = "/home/box/.secrets/comfyart-test.env"
CAP = 0.8
EST = {"openai/gpt-image-2.5-flare/text-to-image": 0.0378, "openai/gpt-image-2.5-flare/edit": 0.0378}  # 1K, #673 C-group logs
EST_UNKNOWN = 0.10  # conservative cap for models without a recorded price (e.g. midjourney); --live checks free /model/price first
SAMPLE_REF = {  # placeholder public refs; replace with box-uploaded test photos before --live
    "logo-abstract": "REF_PHOTO_CAT", "photo-split-poster": "REF_PHOTO_STREET", "promo-ecommerce": "REF_PRODUCT_BOTTLE"}
SK = {
 "naive-illustration": dict(preset="line", ratio=(1024, 1360), refs=False, user="一个巨大的咖啡杯，旁边一个小小的上班族在搬方糖，配一句俏皮短语\"今日续命\"",
   style="Style: naive B/W line illustration, giant object vs tiny person, witty cafe/worker energy, clean strokes."),
 "logo-abstract": dict(preset="circle", ratio=(1024, 1024), refs=True, user="把这只橘猫提炼成一个圆形几何 logo，双色，小尺寸也能认出",
   style="Style: minimal circular geometric logo mark distilled from the photo, two-color, scalable silhouette."),
 "photo-split-poster": dict(preset="hard", ratio=(1024, 1360), refs=True, user="上半部分保留这张街景照片，下半部分用照片里的颜色做几何抽象，标题\"CITY WALK\"",
   style="Style: hard horizontal split poster, photo above, geometric abstract below, palette sampled from the photo."),
 "ppt-visual": dict(preset="cover", ratio=(1824, 1024), refs=False, user="AI 创作工具年度发布会的封面页，标题\"2027 创作新范式\"，深色科技风",
   style="Style: premium deck cover slide 16:9, strong hierarchy, short title in quotes, shared module system."),
 "promo-ecommerce": dict(preset="kv", ratio=(1024, 1360), refs=True, user="双十一大促主视觉，产品是这瓶精华液，主文案\"限时直降\"，日期\"11.11\"",
   style="Style: ecommerce promo key visual, bold sale hierarchy, product hero locked from ref, claims in quotes."),
}
def load_env():
    for l in open(ENV):
        l = l.strip()
        if "=" in l and not l.startswith("#"):
            k, v = l.split("=", 1); os.environ.setdefault(k.replace("export ", "").strip(), v.strip().strip("\"'"))
def build(slug, refs):
    s = SK[slug]; prompt = f"{s['user']}\n{s['style']}"
    from ComfyArt.api.mcp_tools import canvas
    args = {"prompt": prompt, **({"refs": refs} if refs else {})}
    choice = canvas._auto_choice("generate_image", args)
    feat = "image_edit" if refs else "text_to_image"
    inp = {"feature": feat, "model": choice["model"], "prompt": prompt, "width": s["ratio"][0], "height": s["ratio"][1]}
    if refs: inp["images"] = refs
    return choice, inp
async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true"); ap.add_argument("--only")
    ap.add_argument("--ref", action="append", default=[]); ap.add_argument("--out", default="/workspace/smoke673/out")
    a = ap.parse_args(); import conftest; conftest._install_stubs()
    refmap = dict(SAMPLE_REF, **dict(r.split("=", 1) for r in a.ref))
    slugs = a.only.split(",") if a.only else list(SK)
    plan = []
    for sl in slugs:
        refs = [refmap[sl]] if SK[sl]["refs"] else None
        choice, inp = build(sl, refs); plan.append((sl, choice, inp))
        print(json.dumps({"skill": sl, "model": inp["model"], "auto_reason": choice.get("reason", {}).get("en"), "request": inp, "est_usd": EST.get(inp["model"], EST_UNKNOWN)}, ensure_ascii=False, indent=1))
    total = sum(EST.get(i["model"], EST_UNKNOWN) for _, _, i in plan); print(f"TOTAL est ${total:.4f} (cap ${CAP})")
    if total > CAP: sys.exit("over cap")
    if not a.live: print("DRY RUN — nothing submitted. Use --live to spend."); return
    if any(str(r).startswith("REF_") for _, _, i in plan for r in i.get("images", [])): sys.exit("replace REF_ placeholders via --ref")
    load_env(); from ComfyArt.api import wavespeed as ws
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); key = os.environ["WAVESPEED_API_KEY"]
    b0 = await ws.fetch_balance(key); print("balance_before", b0); log = []
    for sl, choice, inp in plan:
        price = await ws.quote(inp["model"], inp)
        if price[0] is None or price[0] > EST.get(inp["model"], EST_UNKNOWN): sys.exit(f"{sl}: quote {price} over estimate, stop")
        task = await ws.submit({**inp, "confirmed": True})
        while True:
            r = await ws.poll(task); s = json.dumps(r, ensure_ascii=False)
            if not any(x in s for x in ('"processing"', '"created"', '"queued"')): break
            await asyncio.sleep(3)
        log.append({"skill": sl, "quote": price, "task": task, "result": r}); print(sl, price, s[:300])
    await asyncio.sleep(5); b1 = await ws.fetch_balance(key)
    print("balance_after", b1, "delta", round(b0 - b1, 6), "est", total)
    json.dump({"balance_before": b0, "balance_after": b1, "runs": log}, open(out / "runs.json", "w"), ensure_ascii=False, indent=1, default=str)
if __name__ == "__main__": asyncio.run(main())
