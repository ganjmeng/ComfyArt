from playwright.sync_api import sync_playwright
WAVE='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4.5 10.5v3M8.25 8v8M12 5v14M15.75 8v8M19.5 10.5v3"/></svg>'
ARROW='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5.5 11.5 12 5l6.5 6.5"/></svg>'
CSS="""
.ca-composer .ca-voice{display:none!important}
.ca-composer .ca-gen__send{position:relative;opacity:1!important;cursor:pointer}
.ca-composer .ca-gen__send[disabled]{background:var(--x268-bg)!important;color:var(--x268-fg)!important;opacity:1!important}
.ca-gen__send .x268{position:absolute;inset:0;display:grid;place-items:center;transition:opacity 120ms ease}
.ca-gen__send .x268 svg{width:16px;height:16px}
.ca-gen__send[data-x268=voice] .x268--send,.ca-gen__send[data-x268=send] .x268--voice{opacity:0}
"""
JS="""([wave,arrow,css])=>{const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
const s=document.querySelector('.ca-gen__send');const tmp=document.querySelector('.ca-gen__send');
s.innerHTML='<span class="x268 x268--voice">'+wave+'</span><span class="x268 x268--send">'+arrow+'</span>';
const c=getComputedStyle(s);}"""
def run(pg,typed,lang):
  # take enabled send colors as the shared colors
  pg.locator(".ca-composer__input").fill("x"); pg.wait_for_timeout(150)
  bg,fg=pg.evaluate("()=>{const c=getComputedStyle(document.querySelector('.ca-gen__send'));return [c.backgroundColor,c.color]}")
  pg.locator(".ca-composer__input").fill(("一只橘猫坐在窗台上，晨光" if lang=="zh" else "An orange cat on a windowsill, morning light") if typed else "")
  pg.evaluate(JS,[WAVE,ARROW,CSS]); pg.evaluate(f"()=>{{const r=document.documentElement.style;r.setProperty('--x268-bg','{bg}');r.setProperty('--x268-fg','{fg}');document.querySelector('.ca-gen__send').dataset.x268='{'send' if typed else 'voice'}';dispatchEvent(new Event('resize'))}}")
  pg.wait_for_timeout(400)
MODES={"image":{"zh":"图像","en":"Image"},"video":{"zh":"视频","en":"Video"}}
jobs=[]
for th in("light","dark"):
  for lang in("zh","en"):
    for w in(1280,360):
      for st in("empty","typed"):
        jobs.append(("before","image",th,lang,w,st)); jobs.append(("after","image",th,lang,w,st))
for m in("video","agent"):
  for st in("empty","typed"): jobs.append(("after",m,"dark","zh",360,st)); jobs.append(("before",m,"dark","zh",360,st))
with sync_playwright() as p:
  b=p.chromium.launch()
  for i,(k,m,th,lang,w,st) in enumerate(jobs):
    ctx=b.new_context(viewport={"width":w,"height":760},device_scale_factor=2); pg=ctx.new_page()
    pg.add_init_script(f"localStorage.setItem('comfyart.theme','{th}');localStorage.setItem('comfyart.lang','{lang}')")
    pg.goto(f"http://127.0.0.1:8871/comfyart/?project=p268-{i}&new=1"); pg.wait_for_timeout(2600); pg.keyboard.press("Escape")
    if m!="agent":
      pg.locator(".ca-composer__mode").click(); pg.wait_for_timeout(300)
      pg.locator(".ca-agentpick .ca-menu__item:not(.ca-agentpick__row)").filter(has_text=MODES[m][lang]).first.click(); pg.wait_for_timeout(400)
    if k=="after": run(pg,st=="typed",lang)
    else:
      if st=="typed": pg.locator(".ca-composer__input").fill("一只橘猫坐在窗台上，晨光" if lang=="zh" else "An orange cat on a windowsill, morning light")
      pg.wait_for_timeout(250)
    pg.locator(".ca-composer").screenshot(path=f"raw/{k}-{m}-{lang}-{th}-{w}-{st}.png"); ctx.close(); print(k,m,lang,th,w,st,flush=True)
