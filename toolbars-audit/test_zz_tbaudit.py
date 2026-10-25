"""Toolbar audit #283: shots + computed styles per element. Mock only, $0.
Env: TB_OUT (dir), TB_VARIANTS e.g. "zh-dark,en-light" (default zh-dark), TB_W (1280)."""
import io, json, os
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from test_e2e_comment_edit import app_url, mock_ws  # noqa
pw = pytest.importorskip("playwright.async_api")
OUT = Path(os.environ.get("TB_OUT", "/workspace/tb-audit/shots")); OUT.mkdir(parents=True, exist_ok=True)
VARS = [v.split("-") for v in os.environ.get("TB_VARIANTS", "zh-dark").split(",")]
W = int(os.environ.get("TB_W", "1280")); MED = Path(__file__).resolve().parent.parent / "media"
MEASURE = """(sel) => { const bars=[...document.querySelectorAll(sel)].filter(e=>e.getClientRects().length); if(!bars.length) return null;
 const bar=bars[bars.length-1]; const cs=getComputedStyle(bar), R=bar.getBoundingClientRect();
 const kids=[...bar.querySelectorAll(':scope > button, :scope > * > button, :scope > .ca-bar__sep, :scope > input, :scope > span.ca-bar__label')].filter(e=>e.getClientRects().length);
 const btns=kids.filter(e=>e.tagName==='BUTTON'); const rs=btns.map(b=>b.getBoundingClientRect()).sort((a,b)=>a.left-b.left);
 const gaps=[]; for(let i=1;i<rs.length;i++) gaps.push(+(rs[i].left-rs[i-1].right).toFixed(1));
 const b0=btns[0]? getComputedStyle(btns[0]):null; const ic=bar.querySelector('.ca-icon svg, button svg'); const icr=ic&&ic.getBoundingClientRect();
 const sep=bar.querySelector('.ca-bar__sep'); const ss=sep&&getComputedStyle(sep), sr=sep&&sep.getBoundingClientRect();
 return {cls:bar.className, h:R.height, w:R.width, radius:cs.borderRadius, shadow:cs.boxShadow, bg:cs.backgroundColor, border:cs.border, pad:cs.padding, gapCss:cs.gap,
  nBtn:btns.length, btnGaps:[...new Set(gaps)], btnH:[...new Set(rs.map(r=>r.height))], btnW:rs.map(r=>Math.round(r.width)), btnRadius:b0&&b0.borderRadius, btnPad:b0&&b0.padding, btnFont:b0&&(b0.fontSize+' '+b0.fontWeight),
  icon:icr&&[icr.width,icr.height], sep:sep&&{w:sr.width,h:sr.height,bg:ss.backgroundColor,margin:ss.margin},
  labels:btns.map(b=>(b.innerText||b.title||b.getAttribute('aria-label')||'').trim().slice(0,12))} }"""
HOVER = """(sel)=>{const bars=[...document.querySelectorAll(sel)].filter(e=>e.getClientRects().length); const b=bars.at(-1)?.querySelector('button'); return b&&getComputedStyle(b).backgroundColor}"""
TIP = """()=>{const t=document.querySelector('.ca-tip'); if(!t) return {native:document.querySelector('.ca-toolbar button:hover')?.title||null}; const c=getComputedStyle(t),r=t.getBoundingClientRect(); return {h:r.height,radius:c.borderRadius,bg:c.backgroundColor,color:c.color,font:c.fontSize,pad:c.padding,shadow:c.boxShadow,text:t.innerText}}"""
MENU = """()=>{const m=[...document.querySelectorAll('.ca-menu')].filter(e=>e.getClientRects().length && !e.closest('.ca-dock')).at(-1); if(!m) return null; const c=getComputedStyle(m),r=m.getBoundingClientRect(); const it=m.querySelector('.ca-menu__item'); const ic=it&&getComputedStyle(it), ir=it&&it.getBoundingClientRect(); const sp=m.querySelector('.ca-menu__sep');
 return {w:r.width,radius:c.borderRadius,shadow:c.boxShadow,pad:c.padding,bg:c.backgroundColor,itemH:ir&&ir.height,itemRadius:ic&&ic.borderRadius,itemFont:ic&&ic.fontSize,itemPad:ic&&ic.padding,sep:sp&&getComputedStyle(sp).backgroundColor}}"""

def png():
    im = Image.new("RGB", (480, 360), (232, 222, 205)); d = ImageDraw.Draw(im); d.ellipse((160, 90, 320, 250), fill=(80, 130, 200))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

async def fresh(pg, app_url, tag):
    await pg.goto(app_url + f"?project=tb{tag}&new=1"); await pg.locator(".tl-canvas").wait_for(); await pg.wait_for_timeout(1200)
    for _ in range(3):
        if await pg.locator(".ca-modal").count(): await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)

async def upload(pg, files):
    await pg.locator(".ca-dock input[type=file][multiple]").set_input_files(files); await pg.wait_for_timeout(2000)

async def tool_drag(pg, key, a=(560, 300), b=(760, 440)):
    await pg.mouse.click(900, 650); await pg.keyboard.press("Escape"); await pg.keyboard.press(key); await pg.wait_for_timeout(200)
    await pg.mouse.move(*a); await pg.mouse.down(); await pg.mouse.move(*b, steps=8); await pg.mouse.up(); await pg.wait_for_timeout(400)
    await pg.keyboard.press("Escape"); await pg.wait_for_timeout(200)

async def sel_center(pg, cx=660, cy=370):
    await pg.keyboard.press("v"); await pg.mouse.click(cx, cy); await pg.wait_for_timeout(600)

async def setup(pg, el, tmp):
    if el == "image": await upload(pg, {"name": "i.png", "mimeType": "image/png", "buffer": png()}); await pg.locator(".tl-image").first.click()
    elif el == "video": await upload(pg, str(MED / "v.mp4")); await pg.locator(".tl-shape").last.click()
    elif el == "audio": await upload(pg, str(MED / "a.wav")); await pg.locator(".tl-shape").last.click()
    elif el == "text":
        await pg.mouse.click(900, 650); await pg.keyboard.press("t"); await pg.mouse.click(560, 320); await pg.wait_for_timeout(300)
        await pg.keyboard.type("标题文字 Title"); await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await pg.keyboard.press("v"); await pg.locator(".tl-shape").last.click(force=True)
    elif el == "shape": await tool_drag(pg, "r"); await sel_center(pg)
    elif el == "pen":
        await pg.mouse.click(900, 650); await pg.keyboard.press("p")
        for x, y in [(560, 300), (700, 260), (760, 420), (600, 450)]: await pg.mouse.click(x, y); await pg.wait_for_timeout(120)
        await pg.keyboard.press("Enter"); await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await pg.keyboard.press("v"); await pg.mouse.click(700, 260); await pg.wait_for_timeout(500)
    elif el == "pen-nodes":
        await setup(pg, "pen", tmp); await pg.mouse.dblclick(700, 260); await pg.wait_for_timeout(600)
    elif el == "note": await pg.mouse.click(900, 650); await pg.keyboard.press("n"); await pg.mouse.click(620, 340); await pg.wait_for_timeout(400); await pg.keyboard.press("Escape"); await pg.keyboard.press("Escape"); await sel_center(pg, 640, 360)
    elif el == "frame": await tool_drag(pg, "f", (500, 250), (820, 500)); await pg.keyboard.press("v"); await pg.mouse.click(505, 240); await pg.wait_for_timeout(500)
    elif el == "refframe":
        await pg.locator(".ca-composer button[title*='参考区'], .ca-composer button[title*='eference']").first.click(); await pg.wait_for_timeout(800)
        await pg.locator(".tl-shape[data-shape-type=frame]").last.click(position={"x": 30, "y": 30}, force=True)
    elif el == "multi": await upload(pg, {"name": "i.png", "mimeType": "image/png", "buffer": png()}); await tool_drag(pg, "r", (900, 200), (1000, 300)); await pg.keyboard.press("v"); await pg.keyboard.press("Control+a")
    await pg.wait_for_timeout(700)

ELS0 = ["image", "video", "audio", "text", "shape", "pen", "pen-nodes", "note", "frame", "refframe", "multi"]
ELS = os.environ.get("TB_ELS", ",".join(ELS0)).split(",")
async def test_tb_audit(app_url, tmp_path):
    res = {}
    async with pw.async_playwright() as p:
        b = await p.chromium.launch(args=["--no-sandbox"])
        for lang, th in VARS:
            for el in ELS:
                k = f"{el}-{lang}-{th}-{W}"; ctx = await b.new_context(viewport={"width": W, "height": 800}, device_scale_factor=2); pg = await ctx.new_page()
                await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{th}')")
                r = {}
                try:
                    await fresh(pg, app_url, k.replace("-", "")); await setup(pg, el, tmp_path)
                    sel = ".ca-toolbar"; m = await pg.evaluate(MEASURE, sel)
                    if not m: sel = ".ca-dock .ca-doodle"; m = await pg.evaluate(MEASURE, sel); m and m.update(native=True)
                    r["bar"] = m; await pg.screenshot(path=str(OUT / f"{k}-full.png"))
                    if m:
                        bar = pg.locator(sel).last; bb = await bar.bounding_box()
                        await pg.screenshot(path=str(OUT / f"{k}-bar.png"), clip={"x": max(bb["x"] - 24, 0), "y": max(bb["y"] - 24, 0), "width": min(bb["width"] + 48, W), "height": bb["height"] + 48})
                        btn = bar.locator("button").first; await btn.hover(force=True); await pg.wait_for_timeout(900)
                        r["hoverBg"] = await pg.evaluate(HOVER, sel); r["tip"] = await pg.evaluate(TIP)
                        await pg.screenshot(path=str(OUT / f"{k}-hover.png"), clip={"x": max(bb["x"] - 24, 0), "y": max(bb["y"] - 60, 0), "width": min(bb["width"] + 48, W), "height": bb["height"] + 140})
                        more = bar.locator("button[title*='更多'], button[aria-label*='更多'], button[title*='More'], button[aria-label*='More']")
                        r["menu"] = None
                        if await more.count(): await more.last.click(); await pg.wait_for_timeout(500); r["menu"] = await pg.evaluate(MENU)
                        if r["menu"]: await pg.screenshot(path=str(OUT / f"{k}-menu.png"))
                except Exception as e: r["error"] = repr(e)[:300]; await pg.screenshot(path=str(OUT / f"{k}-err.png"))
                res[k] = r; await ctx.close()
        await b.close()
    mp = OUT / "measure.json"; old = json.loads(mp.read_text()) if mp.exists() else {}; old.update(res); mp.write_text(json.dumps(old, ensure_ascii=False, indent=1))
