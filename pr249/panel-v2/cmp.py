from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw,ImageFont
import os
os.makedirs('out2/compare',exist_ok=True)
font=ImageFont.truetype([f for f in os.popen("fc-list :lang=zh -f '%{file}\n'").read().split() if f][0],22)
P=[('a_subject_default','04_panel_subject_default',(812,148,1015,548),'tab=subject','#pop'),
   ('b_camera_tab','06_panel_camera_tab',(812,148,1015,548),'tab=camera','#pop'),
   ('min_left_closeup','05_panel_subject_min',(812,148,1015,548),'tab=subject&state=min','#pop'),
   ('menu_entry','03_more_menu_with_duojiaodu',(752,132,888,438),'entry=1','#emenu')]
outs=[]
with sync_playwright() as p:
  pg=p.chromium.launch().new_page(viewport={'width':1280,'height':800})
  for n,ref,box,qs,sel in P:
    pg.goto(f'file://{os.getcwd()}/mock.html?lang=zh&theme=light&{qs}')
    pg.locator(sel).screenshot(path='/tmp/o.png')
    L=Image.open(f'/workspace/lovart-ma/{ref}.png').crop(box); L=L.resize((int(L.width*1.25),int(L.height*1.25)),Image.LANCZOS)
    O=Image.open('/tmp/o.png')
    W=L.width+O.width+90; H=max(L.height,O.height)+80
    c=Image.new('RGB',(W,H),'#ececec'); d=ImageDraw.Draw(c)
    c.paste(L,(30,60)); c.paste(O,(60+L.width,60))
    d.text((30,18),'Lovart 实测',fill='#333',font=font); d.text((60+L.width,18),'我们（v2）',fill='#333',font=font)
    f=f'out2/compare/compare_{n}.png'; c.save(f); outs.append(c)
W=max(o.width for o in outs); H=sum(o.height for o in outs)
A=Image.new('RGB',(W,H),'#ececec'); y=0
for o in outs: A.paste(o,(0,y)); y+=o.height
A.save('out2/compare/compare_all.png')
