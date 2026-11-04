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
CAP = 0.8          # combined hard cap: image_spent + llm_spent + next_quote must stay <= CAP (tech lead)
LLM_CAP = 0.2      # LLM sub-cap across the 5 turns; after turn 1 stop if first-turn LLM cost x 5 > LLM_CAP
LLM_MODEL = "deepseek/deepseek-v4.1-flash-1017"  # via llm.wavespeed.ai; no price in repo/docs ->
# LLM cost method: optional env SMOKE_LLM_USD_PER_M_IN / _OUT (token price) else balance delta - image quote.
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
CDN_HOST = "d2h7xmz5gqybh9.cloudfront.net"  # WaveSpeed output CDN (#687 ex01 download died with TLS EOF)


def llm_usage(messages, after_id):
    """Sum token usage of assistant messages after the user message (chat_store 'usage' field)."""
    pin = pout = 0; seen = after_id is None
    for m in messages:
        if not seen: seen = m.get("id") == after_id; continue
        u = m.get("usage") or {}
        pin += int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
        pout += int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    return pin, pout


def llm_cost(pin, pout, delta, quote):
    pi, po = os.environ.get("SMOKE_LLM_USD_PER_M_IN"), os.environ.get("SMOKE_LLM_USD_PER_M_OUT")
    if pi and po: return round(pin * float(pi) / 1e6 + pout * float(po) / 1e6, 6), "token_price_env"
    if pin or pout:  # WaveSpeed LLM /v1/models price for deepseek-v4.1-flash-1017: $0.15/M in, $0.60/M out
        return round(pin * 0.15 / 1e6 + pout * 0.60 / 1e6, 6), "usage_tokens_x_v1_models_price"
    return None, "unattributable (concurrent spend)"  # never derived from balance delta (#687 spends concurrently)
CONCURRENT_NOTE = ("Tech rule: image cost = each submitted prediction id at its quoted price; LLM = usage tokens x price else unattributed; "
                   "per-call balance deltas not relied on (dev #687 batch may run concurrently); balance start/end with timestamps is for the combined reconciliation only.")
NOTE2 = ("#687 batch paused during this run (parent all-clear); per-call balance delta is clean. Image cost per prediction id = app gen_ledger quote "
                   "(WaveSpeed predictions carry no cost field); LLM cost = balance delta - image cost; token x price kept as cross-check. "
                   "Pre-call drift check: stop if balance moved > $0.01 since last reading.")
OLD_NOTE = ("#687 batch spent from the same WaveSpeed balance concurrently: balance before/after is a reconciliation "
                   "reference only. Image spend = per-prediction billing (app gen_ledger quoted_usd per WaveSpeed prediction id); "
                   "LLM spend = usage tokens x price. Caps enforced on these attributed numbers.")
LEDGER = os.environ.get("SMOKE_LEDGER", "")
def ledger_since(t0):
    try: runs = json.load(open(LEDGER)).get("runs", {})
    except Exception: return []
    return [r for r in runs.values() if (r.get("submitted_at") or 0) >= t0]
def prediction_billing(task, key):
    """WaveSpeed prediction result: keep status and any cost/price fields it carries."""
    try:
        req = urllib.request.Request(f"https://api.wavespeed.ai/api/v3/predictions/{task}/result", headers={"Authorization": f"Bearer {key}"})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read()).get("data") or {}
        return {k: d.get(k) for k in d if k in ("status", "model", "cost", "price", "billing", "amount", "created_at")}
    except Exception as e: return {"error": type(e).__name__}


def cdn_preflight(out, host=CDN_HOST, timeout=15):
    """Free TLS handshake probe of the result CDN; a paid image we cannot download is wasted money."""
    import socket, ssl
    rec = {"host": host, "t": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    try:
        with socket.create_connection((host, 443), timeout=timeout) as raw:
            with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as tls:
                rec.update(ok=True, tls=tls.version())
    except Exception as e:  # SSLEOFError / handshake / timeout
        rec.update(ok=False, error=f"{type(e).__name__}: {e}")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "cdn_preflight.json"), "w") as f: json.dump(rec, f, indent=1)
    print("CDN preflight:", json.dumps(rec)); return rec


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true"); ap.add_argument("--cdn-probe", action="store_true"); ap.add_argument("--only")
    ap.add_argument("--ref", action="append", default=[]); ap.add_argument("--out", default="/workspace/smoke673/out")
    ap.add_argument("--base", default="http://127.0.0.1:8188"); ap.add_argument("--project", default="PROJECT_ID")
    ap.add_argument("--provider", default="local-llm"); ap.add_argument("--turn-timeout", type=int, default=600)
    a = ap.parse_args()
    if a.cdn_probe:
        os.makedirs(a.out, exist_ok=True); sys.exit(0 if cdn_preflight(a.out)["ok"] else 2)
    import conftest; conftest._install_stubs()
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
    total = sum(p[3] for p in plan); print(f"TOTAL image est ${total:.4f}; combined cap ${CAP} (image+LLM), LLM sub-cap ${LLM_CAP} ({LLM_MODEL})")
    if total > CAP: sys.exit("over cap")
    if not a.live: print("DRY RUN — nothing submitted. Use --live to spend."); return
    if a.project == "PROJECT_ID": sys.exit("--project <id> required (open that project in the Loomi tab)")
    if any(str(r).startswith("REF_") for _, i, _, _ in plan for r in i.get("images", [])): sys.exit("replace REF_ placeholders via --ref")
    if not cdn_preflight(a.out)["ok"]: sys.exit("abort: WaveSpeed CDN TLS preflight failed; no paid call made")
    load_env(); from ComfyArt.api import wavespeed as ws
    key = os.environ["WAVESPEED_API_KEY"]; out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    spent, llm_spent, log = 0.0, 0.0, []; last_bal = None
    recon = {"note": CONCURRENT_NOTE, "start_ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "start_balance": await ws.fetch_balance(key)}
    def save_recon():
        json.dump(recon, open(out / "reconciliation.json", "w"), ensure_ascii=False, indent=1)
    save_recon()
    import atexit
    def _end():
        import asyncio as _a
        try: recon["end_balance"] = _a.new_event_loop().run_until_complete(ws.fetch_balance(key))
        except Exception as e: recon["end_balance"] = f"error {type(e).__name__}"
        recon["end_ts"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        recon["attributed"] = {"image": round(spent_box[0], 6), "llm": round(spent_box[1], 6), "total": round(sum(spent_box), 6),
                               "llm_unattributed_turns": sum(1 for r in log if r.get("llm_cost_est") is None),
                               "predictions": [b["prediction_id"] for r in log for b in r["predictions"]]}
        save_recon()
    spent_box = [0.0, 0.0]; atexit.register(_end)
    for sl, inp, send, est in plan:
        fails = 0
        while fails < MAX_FAILS:
            q = http(a.base, "POST", "/comfyart/wavespeed/estimate", {"inputs": inp})
            price = q.get("price") if isinstance(q, dict) else None
            if price is None or price > est: sys.exit(f"{sl}: quote {q} over estimate ${est}, stop")
            if spent + llm_spent + price > CAP: sys.exit(f"{sl}: image ${spent:.4f} + LLM ${llm_spent:.4f} + ${price} > combined cap ${CAP}, stop")
            if llm_spent > LLM_CAP: sys.exit(f"LLM ${llm_spent:.4f} > LLM cap ${LLM_CAP}, stop")
            b0 = await ws.fetch_balance(key)
            chat = http(a.base, "POST", "/comfyart/bot/chats", {"project": a.project, "provider": a.provider, "title": f"smoke673 {sl}", "run_mode": "auto"})["chat"]
            t_send = time.time() - 1; r = http(a.base, "POST", f"/comfyart/bot/chats/{chat['id']}/send", send)
            uid = (r.get("user_message") or {}).get("id"); t0 = time.time()
            while True:
                await asyncio.sleep(5); st = http(a.base, "GET", f"/comfyart/bot/chats/{chat['id']}")
                if not st["chat"].get("busy") or time.time() - t0 > a.turn_timeout: break
            if st["chat"].get("busy"): http(a.base, "POST", f"/comfyart/bot/chats/{chat['id']}/stop", {})
            await asyncio.sleep(5); b1 = await ws.fetch_balance(key)
            charged = round(b0 - b1, 6) if b0 is not None and b1 is not None else None
            imgs = images_of(st["messages"], uid); ok = bool(imgs)
            preds = ledger_since(t_send)
            billing = [dict(prediction_id=p["task_id"], model=p.get("model"), status=p.get("status"), cost_usd=p.get("quoted_usd") if p.get("quoted_usd") is not None else p.get("cost_usd"),
                            ws=prediction_billing(p["task_id"], key)) for p in preds]
            img_cost = round(sum(b["cost_usd"] or 0 for b in billing), 6); spent += img_cost
            pin, pout = llm_usage(st["messages"], uid); lc_tok, _ = llm_cost(pin, pout, None, img_cost)
            last_bal = b1
            lc, method = (lc_tok, "usage_tokens_x_price ($0.15/M in, $0.60/M out)") if lc_tok is not None else (None, "unattributed")
            llm_spent += lc or 0.0
            rec = {"skill": sl, "chat": chat["id"], "quote": price, "balance_before": b0, "balance_after": b1,
                   "balance_delta_unreliable": charged, "note": CONCURRENT_NOTE, "predictions": billing, "image_cost": img_cost, "image_spent": round(spent, 6),
                   "llm_model": LLM_MODEL, "llm_prompt_tokens": pin, "llm_completion_tokens": pout,
                   "llm_cost_est": lc, "llm_cost_tokens_x_price": lc_tok, "llm_cost_method": method, "llm_spent": round(llm_spent, 6),
                   "combined_spent": round(spent + llm_spent, 6), "caps": {"combined": CAP, "llm": LLM_CAP},
                   "images": imgs, "ok": ok}
            spent_box[:] = [spent, llm_spent]; log.append(rec); print(json.dumps(rec, ensure_ascii=False))
            json.dump(log, open(out / "runs.json", "w"), ensure_ascii=False, indent=1, default=str)
            if ok and not billing: sys.exit(f"stop: {sl} produced an image but no prediction billing record was found; spend unattributed")
            if len(log) == 1 and lc is None: sys.exit("stop: first-turn LLM usage unattributed; cannot apply LLM sub-cap projection")
            if len(log) == 1 and (lc or 0) * 5 > LLM_CAP:
                sys.exit(f"stop: first-turn LLM ${lc} x 5 = ${(lc or 0) * 5:.4f} > LLM cap ${LLM_CAP} (method {method})")
            if llm_spent > LLM_CAP: sys.exit(f"stop: LLM ${llm_spent:.4f} > LLM cap ${LLM_CAP}")
            if ok: break
            fails += 1
        if fails >= MAX_FAILS: sys.exit(f"{sl}: {MAX_FAILS} consecutive failures, stop")
    print(f"DONE image ${spent:.4f} + LLM ${llm_spent:.4f} = ${spent + llm_spent:.4f} (image est ${total:.4f}, combined cap ${CAP}, LLM cap ${LLM_CAP})")
if __name__ == "__main__": asyncio.run(main())
