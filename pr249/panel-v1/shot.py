from playwright.sync_api import sync_playwright
import os
os.makedirs('out',exist_ok=True)
with sync_playwright() as p:
  b=p.chromium.launch()
  pg=b.new_page(viewport={'width':1280,'height':800})
  for lang in ['zh','en']:
    for th in ['light','dark']:
      for i,(tab,st) in enumerate([('subject','default'),('camera','default'),('subject','snapped')]):
        pg.goto(f'file://{os.getcwd()}/mock.html?lang={lang}&theme={th}&tab={tab}&state={st}')
        n=f"out/{'abc'[i]}_{['subject_default','camera_tab','snapped_hover_generate'][i]}_{lang}_{th}.png"; pg.screenshot(path=n)
        bb=pg.locator('#pop').bounding_box(); assert bb['y']+bb['height']<=800,(n,bb)
      p2=b.new_page(viewport={'width':1280,'height':800},device_scale_factor=2)
      p2.goto(f'file://{os.getcwd()}/mock.html?lang={lang}&theme={th}&tab=subject&state=default')
      p2.locator('#pop').screenshot(path=f'out/closeup2x_{lang}_{th}.png',padding=12) if False else p2.locator('#pop').screenshot(path=f'out/closeup2x_{lang}_{th}.png'); p2.close()
  print(bb)
