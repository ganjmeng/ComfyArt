import json, os, pytest
pw = pytest.importorskip("playwright.async_api")
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_e2e_default_agent import fake_tools  # noqa: F401
from test_e2e_default_agent import pytestmark  # noqa: F401
OUT="/workspace/r271/polish"; os.makedirs(OUT,exist_ok=True)
CSS=os.environ.get("POLISH_CSS","")
TAG=os.environ.get("POLISH_TAG","ours")
MEASURE="""() => { const f=document.querySelector('.ca-composer__foot'), c=document.querySelector('.ca-composer');
 const R=e=>{const b=e.getBoundingClientRect();return [Math.round(b.left*10)/10,Math.round(b.top*10)/10,Math.round(b.width*10)/10,Math.round(b.height*10)/10]};
 const kids=[...f.querySelectorAll('button')].filter(e=>e.getBoundingClientRect().width>0).map(e=>{const s=getComputedStyle(e);const t=e.querySelector('span:not(:empty)');return {cls:e.className.slice(0,50),txt:e.innerText.trim().slice(0,12),box:R(e),radius:s.borderRadius,bg:s.backgroundColor,color:s.color,fs:t?getComputedStyle(t).fontSize:s.fontSize,gapStyle:s.gap,svgs:[...e.querySelectorAll('svg')].map(R)}});
 const cs=getComputedStyle(c), fs=getComputedStyle(f);
 return {composer:R(c),cRadius:cs.borderRadius,cPad:cs.padding,foot:R(f),footPad:fs.padding,footGap:fs.gap,kids} }"""
@pytest.mark.parametrize("width", [1280, 360])
@pytest.mark.parametrize("lang", ["zh","en"])
@pytest.mark.parametrize("theme", ["dark","light"])
async def test_shot(app_url, fake_tools, monkeypatch, width, lang, theme):  # noqa: F811
    monkeypatch.setenv("WAVESPEED_API_KEY", "mock-key-not-real")
    async with pw.async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": width, "height": 800}, device_scale_factor=2)).new_page()
        await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
        await pg.goto(app_url + f"?project=pp{lang}{theme}{width}&new=1")
        await pg.locator(".ca-composer__mode").wait_for(); await pg.wait_for_timeout(1500)
        for _ in range(3):
            if await pg.locator(".ca-modal").count():
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await pg.locator(".ca-composer__mode").click(); await pg.wait_for_timeout(300)
        await pg.locator(".ca-agentpick .ca-menu__item:not(.ca-agentpick__row)").nth(0).click()
        await pg.wait_for_timeout(300)
        if await pg.locator(".ca-agentpick").count(): await pg.keyboard.press("Escape")
        if CSS: await pg.add_style_tag(content=open(CSS).read()); await pg.wait_for_timeout(200)
        m = await pg.evaluate(MEASURE)
        json.dump(m, open(f"{OUT}/{TAG}-{lang}-{theme}-{width}.json","w"), ensure_ascii=False, indent=1)
        c = await pg.locator(".ca-composer").bounding_box()
        clip={"x":max(0,c["x"]-16),"y":max(0,c["y"]-16),"width":min(width,c["width"]+32),"height":c["height"]+32}
        await pg.screenshot(path=f"{OUT}/{TAG}-{lang}-{theme}-{width}.png", clip=clip)
        # hover on settings
        await pg.locator(".ca-composer__foot [data-pill=settings]").first.hover(); await pg.wait_for_timeout(200)
        hv = await pg.locator(".ca-composer__foot [data-pill=settings]").first.evaluate("e=>getComputedStyle(e).backgroundColor")
        await pg.screenshot(path=f"{OUT}/{TAG}-{lang}-{theme}-{width}-hover.png", clip=clip)
        open(f"{OUT}/{TAG}-{lang}-{theme}-{width}.hover","w").write(hv)
        if lang=="zh":
            for name in ["model","settings"]:
                await pg.mouse.move(0,0)
                await pg.locator(f".ca-composer__foot [data-pill={name}]").first.click(); await pg.wait_for_timeout(500)
                pm = await pg.evaluate("""() => [...document.querySelectorAll('.ca-menu, .ca-gen__pop, .ca-pop')].filter(e=>e.getBoundingClientRect().width>0).map(e=>{const s=getComputedStyle(e),b=e.getBoundingClientRect();return {cls:e.className.slice(0,40),box:[b.left,b.top,b.width,b.height].map(Math.round),radius:s.borderRadius,shadow:s.boxShadow,border:s.border,bg:s.backgroundColor}})""")
                json.dump(pm, open(f"{OUT}/{TAG}-pop-{name}-{theme}-{width}.json","w"), indent=1)
                await pg.screenshot(path=f"{OUT}/{TAG}-pop-{name}-{theme}-{width}.png")
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
        await b.close()
