import os, json, re, io, zipfile
from pathlib import Path
from test_e2e_comment_edit import app_url, mock_ws  # noqa
from test_e2e_skill_cards_494 import _seed_personal
import playwright.async_api as pw
OUT = Path(os.environ["OUT"]); MEAS = {}; ERR = []
MJS = """(sels)=>{const o={};for(const s of sels){const els=[...document.querySelectorAll(s)].filter(e=>e.getBoundingClientRect().width>0);if(!els.length)continue;const e=els[0],r=e.getBoundingClientRect(),c=getComputedStyle(e);
const rec={count:els.length,x:Math.round(r.x),y:Math.round(r.y),w:+r.width.toFixed(1),h:+r.height.toFixed(1),radius:c.borderRadius,font:c.fontSize+'/'+c.lineHeight+' '+c.fontWeight,color:c.color,bg:c.backgroundColor,border:c.borderTop,padding:c.padding,gap:c.gap,gridCols:c.gridTemplateColumns!=='none'?c.gridTemplateColumns:undefined};
if(els.length>1){const r2=els[1].getBoundingClientRect();rec.dx2=+(r2.x-r.x).toFixed(1);rec.dy2=+(r2.y-r.y).toFixed(1);rec.gapX=+(r2.x-r.right).toFixed(1);}o[s]=rec}return o}"""
HOME = ['[data-testid=home-shell]','[data-testid=home-start-skill]','[data-testid=home-skill-grid]','[data-testid=home-skill-card]','[data-testid=home-skill-card] img','[data-testid=home-featured]','[data-testid=home-featured-grid]','[data-testid=home-featured-card]','[data-testid=home-featured-card] img','[data-testid=home-tools]','[data-testid=home-plus-menu]','[data-testid=home-skills-menu]','[data-testid=home-skill-row]','[data-testid=home-skills-more-menu]','[data-testid=home-create-skill]','[data-testid=home-import-skill]','[data-testid=home-skill-chip]','.ca-composer','.ca-composer__input']
SK = ['[data-testid=skills-page]','.ca-skills__title','.ca-skills h1','[data-testid=skills-tabs]','.ca-skills__tab','[data-testid=skills-chips]','.ca-skills__chip','[data-testid=skills-wall]','[data-testid=skills-wall-card]','.ca-swall__cover','.ca-swall__title','[data-testid=skills-card-author]','[data-testid=skills-card-kind]','[data-testid=skills-card-try]','[data-testid=skills-card-bookmark]','[data-testid=skills-create]','[data-testid=skills-create-menu]','.ca-menu__item','[data-testid=skills-group-yours]','[data-testid=skills-group-loomi]','[data-testid=skills-wall-yours] [data-testid=skills-wall-card]','[data-testid=skills-empty]']
RUN = ['[data-testid=skill-run-modal]','[data-testid=skill-run-dialog]','.ca-skillrun__left','.ca-skillrun__right','[data-testid=skill-run-head]','[data-testid=skill-run-title]','[data-testid=skill-run-desc]','[data-testid=skill-run-meta]','[data-testid=skill-run-author]','[data-testid=skill-run-presets]','.ca-skillrun__tile','.ca-skillrun__presetimg','[data-testid=skill-run-preset]','.ca-skillrun__check','[data-testid=skill-run-current]','.ca-skillrun__currentrow','[data-testid=skill-run-field]','[data-testid=skill-run-upload]','[data-testid=skill-run-go]','[data-testid=skill-run-detail]','[data-testid=skill-run-examples]','[data-testid=skill-run-example-stage]','[data-testid=skill-run-example-thumb]','[data-testid=skill-form]','[data-testid=skill-import-dialog]','[data-testid=skill-import-drop]','[data-testid=skill-import-notes]','[data-testid=skill-import-error]']
CR = ['.ca-agent','[data-testid=creator-landing-title]','[data-testid=skill-creator-chip]','.ca-chat__start','.ca-composer','.ca-composer__input']
async def shot(pg, key, name, sels):
    await pg.mouse.move(2, 790); await pg.wait_for_timeout(700)
    try: await pg.wait_for_function("()=>[...document.images].filter(i=>{const r=i.getBoundingClientRect();return r.bottom>0&&r.top<800&&r.width}).every(i=>i.complete)", timeout=20000)
    except Exception: pass
    await pg.screenshot(path=str(OUT/f"{name}-{key}.png"))
    MEAS.setdefault(key, {})[name] = await pg.evaluate(MJS, sels)
async def step(key, name, fn):
    try: await fn()
    except Exception as e: ERR.append(f"{key}/{name}: {str(e)[:200]}"); print("ERR", key, name, str(e)[:300])
async def new(p, app_url, lang, theme, path="", seed=False):
    b = await p.chromium.launch()
    pg = await (await b.new_context(viewport={"width":1280,"height":800}, device_scale_factor=1)).new_page()
    await pg.add_init_script(f"localStorage.setItem('comfyart.lang','{lang}');localStorage.setItem('comfyart.theme','{theme}')")
    if seed: await _seed_personal(pg)
    pg.set_default_timeout(10000); await pg.goto(app_url + path); await pg.wait_for_timeout(1200)
    return b, pg
async def run(p, app_url, lang, theme):
    key = f"{lang}-{theme}"
    # HOME
    b, pg = await new(p, app_url, lang, theme)
    async def h1():
        await pg.get_by_test_id("home-start-skill").wait_for(); await shot(pg, key, "01-home-top", HOME)
        await pg.get_by_test_id("home-start-skill").scroll_into_view_if_needed(); await shot(pg, key, "02-home-skills-area", HOME)
        await pg.get_by_test_id("home-featured").scroll_into_view_if_needed(); await shot(pg, key, "03-home-featured", HOME)
        await pg.evaluate("scrollTo(0,0);document.querySelectorAll('*').forEach(e=>{if(e.scrollTop)e.scrollTop=0})")
    await step(key, "home", h1)
    async def h2():
        await pg.get_by_test_id("home-plus").click(); await pg.get_by_test_id("home-plus-menu").wait_for(); await shot(pg, key, "04-home-plus-menu", HOME)
        await pg.get_by_test_id("home-plus-skills").click(); await pg.get_by_test_id("home-skill-row").first.wait_for(); await shot(pg, key, "05-home-skills-panel", HOME)
        await pg.get_by_test_id("home-skills-more").click(); await pg.get_by_test_id("home-create-skill").wait_for(); await shot(pg, key, "06-home-skills-more-creator-import", HOME)
        await pg.keyboard.press("Escape"); await pg.keyboard.press("Escape")
    await step(key, "home-plus", h2)
    await b.close(); b, pg = await new(p, app_url, lang, theme)
    async def h3():
        inp = pg.locator(".ca-landing__input").first; await inp.click(); await inp.type("/"); await pg.wait_for_timeout(800)
        await shot(pg, key, "07-home-typed-slash", HOME)
        MEAS[key]["07-home-typed-slash"]["_slashOpensPanel"] = await pg.get_by_test_id("home-skill-row").count() > 0
        if not MEAS[key]["07-home-typed-slash"]["_slashOpensPanel"]:
            await inp.fill(""); await pg.get_by_test_id("home-plus").click(); await pg.get_by_test_id("home-plus-skills").click(); await pg.get_by_test_id("home-skill-row").first.wait_for()
        await pg.get_by_test_id("home-skill-row").first.click(); await pg.wait_for_timeout(500); await shot(pg, key, "08-home-skill-chip-selected", HOME)
    await step(key, "home-slash", h3)
    async def h4():
        await pg.goto(app_url); await pg.get_by_test_id("home-skill-card").first.click(); await pg.get_by_test_id("skill-run-dialog").wait_for(); await shot(pg, key, "09-home-skill-card-dialog", RUN)
    await step(key, "home-card", h4)
    await b.close()
    # SKILLS PAGE
    b, pg = await new(p, app_url, lang, theme, "?view=skills", seed=True)
    async def s1():
        await pg.get_by_test_id("skills-wall-card").first.wait_for(); await shot(pg, key, "10-skills-list-explore-forYou", SK)
        await pg.evaluate("document.querySelector('[data-testid=skills-wall]').scrollIntoView({block:'end'})"); await shot(pg, key, "11-skills-list-scrolled", SK)
        await pg.evaluate("scrollTo(0,0);document.querySelectorAll('*').forEach(e=>{if(e.scrollTop)e.scrollTop=0})")
        ids = await pg.get_by_test_id("skills-chips").locator("button").evaluate_all("bs=>bs.map(b=>b.dataset.testid)")
        for i, t in enumerate(ids[1:]):
            await pg.get_by_test_id(t).click(); await shot(pg, key, f"12-skills-chip-{t.split('-')[-1]}", SK)
        await pg.get_by_test_id(ids[0]).click()
        await pg.get_by_test_id("skills-tab-favourites").click(); await shot(pg, key, "13-skills-tab-favourites", SK)
        await pg.get_by_test_id("skills-tab-personal").click(); await shot(pg, key, "14-skills-tab-personal-imported-cards", SK)
        await pg.get_by_test_id("skills-tab-explore").click()
        await pg.get_by_test_id("skills-create").hover(); await shot(pg, key, "15-skills-create-hover", SK)
    await step(key, "skills", s1)
    async def s2():
        await pg.locator(".ca-skills__head button, .ca-skills button[title]").first.wait_for()
        await pg.get_by_test_id("skills-create-menu").click(); await pg.get_by_test_id("skills-import").wait_for(); await shot(pg, key, "16-skills-create-menu", SK)
        await pg.get_by_test_id("skills-import").click(); await pg.get_by_test_id("skill-import-dialog").wait_for(); await shot(pg, key, "17-import-dialog", RUN)
        buf = io.BytesIO(); z = zipfile.ZipFile(buf, "w"); z.writestr("demo-skill/SKILL.md", "---\nname: Demo Skill\ndescription: audit import\n---\nDo things.\n"); z.close()
        await pg.get_by_test_id("skill-import-zip-input").set_input_files(files=[{"name":"demo-skill.zip","mimeType":"application/zip","buffer":buf.getvalue()}])
        await pg.wait_for_timeout(1500); await shot(pg, key, "18-import-after-zip", RUN)
    await step(key, "import", s2)
    async def s3():
        await pg.goto(app_url + "?view=skills"); await pg.get_by_test_id("skills-wall-card").first.wait_for()
        await pg.evaluate("(async()=>{})()"); await pg.locator("[data-testid=skills-create]").evaluate("e=>e.closest('.ca-skills__createwrap').previousElementSibling.click()")
        await pg.wait_for_timeout(800); await shot(pg, key, "19-skills-search-dialog", SK + ['[role=dialog]','.ca-skillsdlg','[data-testid=skills-dialog]'])
    await step(key, "search", s3)
    await b.close()
    for kind, skills in (("template", ["brand","packaging","product","character","motion"]), ("example", ["poster","social","thumbnail","banner","interior","custom-workflow"])):
        b, pg = await new(p, app_url, lang, theme, "?view=skills")
        for sk in skills:
            async def d(sk=sk):
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(300)
                if await pg.get_by_test_id("skill-run-dialog").count():
                    await pg.goto(app_url + "?view=skills")
                await pg.get_by_test_id("skills-wall-card").first.wait_for()
                await pg.locator(f'[data-skill="{sk}"] .ca-swall__cover').click(); await pg.get_by_test_id("skill-run-dialog").wait_for()
                await shot(pg, key, f"20-detail-{kind}-{sk}", RUN)
                if kind == "template" and await pg.get_by_test_id("skill-run-preset").count():
                    await pg.get_by_test_id("skill-run-preset").nth(1).click(); await shot(pg, key, f"21-detail-{sk}-selected-input", RUN)
                if sk == "poster":
                    await pg.get_by_test_id("skill-run-detail").click(); await pg.get_by_test_id("skill-form").wait_for(); await shot(pg, key, "22-skill-detail-form-poster", RUN)
            await step(key, f"detail-{sk}", d)
        await b.close()
    for name, path, go in (("home", "", ["home-plus","home-plus-skills","home-skills-more","home-create-skill"]), ("skills", "?view=skills", ["skills-create"])):
        b, pg = await new(p, app_url, lang, theme, path)
        async def c(go=go, name=name):
            for t in go: await pg.get_by_test_id(t).click()
            await pg.get_by_test_id("creator-landing-title").wait_for(); await shot(pg, key, f"30-create-skill-via-{name}", CR)
        await step(key, f"create-{name}", c); await b.close()
async def test_audit(app_url):  # noqa
    async with pw.async_playwright() as p:
        await run(p, app_url, "zh", "light"); await run(p, app_url, "en", "dark")
    (OUT/"measurements.json").write_text(json.dumps({"base":"1cd857a3","viewport":"1280x800@1x","surfaces":MEAS,"errors":ERR}, ensure_ascii=False, indent=1))
