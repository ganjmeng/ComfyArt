from playwright.sync_api import sync_playwright
import os
os.makedirs('out2',exist_ok=True)
F=[('a_subject_default','tab=subject&state=default'),('b_camera_tab','tab=camera&state=default'),('c_snapped_hover_generate','tab=subject&state=snapped'),('d_four_angles','tab=subject&preset=four'),('e_count_menu_open','tab=subject&menu=open&n=2')]
with sync_playwright() as p:
  b=p.chromium.launch()
  pg=b.new_page(viewport={'width':1280,'height':800})
  for lang in ['zh','en']:
    for th in ['light','dark']:
      for n,qs in F:
        pg.goto(f'file://{os.getcwd()}/mock.html?lang={lang}&theme={th}&{qs}')
        pg.screenshot(path=f'out2/{n}_{lang}_{th}.png')
        bb=pg.locator('#pop').bounding_box(); g=pg.locator('.go').bounding_box(); assert bb['y']+bb['height']<=800 and g['y']+g['height']<=800,(n,bb)
      p2=b.new_page(viewport={'width':1280,'height':800},device_scale_factor=2)
      for n,qs in [('closeup2x','tab=subject'),('closeup2x_four','tab=subject&preset=four')]:
        p2.goto(f'file://{os.getcwd()}/mock.html?lang={lang}&theme={th}&{qs}'); p2.locator('#pop').screenshot(path=f'out2/{n}_{lang}_{th}.png')
      p2.close()
  print(bb)
