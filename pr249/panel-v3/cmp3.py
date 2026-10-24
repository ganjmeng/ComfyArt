from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw,ImageFont
import os,textwrap
O='out3/compare'; os.makedirs(O,exist_ok=True)
fp=[f for f in os.popen("fc-list :lang=zh -f '%{file}\n'").read().split('\n') if f][0]
F=lambda n:ImageFont.truetype(fp,n)
LV='/workspace/lovart-ma/'; PB=(812,148,1015,548)
def lov(f,box=PB,k=1.25):
  L=Image.open(LV+f).crop(box); return L.resize((int(L.width*k),int(L.height*k)),Image.LANCZOS)
ROWS={'zh':[
 ('① 主体 tab','04_panel_subject_default.png','subject','tab=subject',
  ['Lovart「主体」= 转动物体：方块正面贴原图，拖方块转物体。',
   '当前 main 对应：「对象」视图（three.js 方块，面上写 右侧/顶面/背面）。',
   'v3 对应：「主体」tab 的方块，加了面标记、正面蓝框高光、地面网格、阴影、拖动弧线、角度读数。',
   '参数：旋转→horizontal_angle（v+360）%360；倾斜→vertical_angle；缩放→distance。']),
 ('② 摄像头 tab','06_panel_camera_tab.png','camera','tab=camera',
  ['Lovart「摄像头」= 物体不动，相机绕球面移动；原图小块居中，小方块是相机。',
   '当前 main 对应：「相机」视图（线框球 + 粉/青色把手 + 预览小窗）。',
   'v3 对应：「摄像头」tab 线框球，赤道=水平轨道，经线=垂直轨道，相机把手+虚线指向原图。',
   '主体和摄像头驱动同一组参数（h/v/z），只是两种看法；切 tab 数值不变。']),
 ('③ 拖动/滑杆调整后','08_reset_hover.png','adjusted','tab=subject&state=snapped&nohover=1',
  ['Lovart：滑杆连续，旋转 −90~90、倾斜 −30~60，缩放三档。',
   '当前 main：水平 0~360、垂直 −30~60、远近 0~10 连续（例：左前+俯视+特写 → 315/50/8）。',
   'v3：旋转 −180~180 吸附每 45°（模型 8 个位置），倾斜吸附 −30/0/30/60，缩放 3 档；读数实时显示模型值。',
   '例：旋转 −45 → horizontal 315；倾斜 30 → vertical 30；特写 → distance 0。']),
 ('④ 四角度','','four','tab=subject&preset=four',
  ['Lovart：没有此功能。',
   '当前 main：底部「一次生成 4 个角度」按钮，点了立即提交 4 个请求，没有选中态。',
   'v3：预设里的「四角度」芯片，选中后旋转显示「4 个角度」并禁用，地面圈上 4 个蓝点；数量锁定 ×4，按钮「生成 4 张 $0.12」。',
   '4 个请求：horizontal 270 / 315 / 45 / 90，vertical、distance 相同。'])],
}
ROWS['en']=ROWS['zh']
def build(lang,th):
  with sync_playwright() as p:
    pg=p.chromium.launch().new_page(viewport={'width':1280,'height':800})
    rows=[]
    for title,lf,mk,qs,notes in ROWS[lang]:
      pg.goto(f'file://{os.getcwd()}/mock.html?lang={lang}&theme={th}&{qs}'); pg.locator('#pop').screenshot(path='/tmp/v3.png')
      L=lov(lf) if lf else None
      M=Image.open(f'/tmp/main/{mk}_{lang}_{th}.png').copy(); V=Image.open('/tmp/v3.png').copy()
      rows.append((title,L,M,V,notes))
  cw=[260,330,270]; tw=440; pad=24; H0=70
  bg='#ececec'; fg='#222'
  heights=[max((r[1].height if r[1] else 300),r[2].height,r[3].height)+50 for r in rows]
  W=pad+sum(c+pad for c in cw)+tw+pad; H=H0+sum(heights)+pad
  img=Image.new('RGB',(W,H),bg); d=ImageDraw.Draw(img)
  heads=['Lovart 实测','当前 main（0ec5d4d）','我们 v3（新）','对应关系 / 参数']
  x=pad
  for i,h in enumerate(heads): d.text((x,22),h,fill=fg,font=F(22)); x+= (cw[i] if i<3 else 0)+pad
  y=H0
  for (title,L,M,V,notes),hh in zip(rows,heights):
    d.text((pad,y),title,fill='#3b82f6',font=F(20)); yy=y+34; x=pad
    for im,w in zip([L,M,V],cw):
      if im is None:
        d.rounded_rectangle((x,yy,x+w,yy+300),12,outline='#bbb',width=2); d.text((x+70,yy+140),'（无此功能）',fill='#888',font=F(20))
      else: img.paste(im,(x,yy))
      x+=w+pad
    ty=yy
    for n in notes:
      for line in textwrap.wrap(n,22 if lang=='zh' else 44):
        d.text((x,ty),line,fill=fg,font=F(17)); ty+=25
      ty+=10
    y+=hh
  img.save(f'{O}/compare3col_{lang}_{th}.png')
for a in [('zh','light'),('zh','dark'),('en','light')]: build(*a)
# cube closeup
with sync_playwright() as p:
  b=p.chromium.launch(); pg=b.new_page(viewport={'width':1280,'height':800},device_scale_factor=2)
  for tab,lf,box,n in [('subject','04_panel_subject_default.png',(826,220,1002,392),'cube'),('camera','06_panel_camera_tab.png',(826,220,1002,392),'sphere')]:
    pg.goto(f'file://{os.getcwd()}/mock.html?lang=zh&theme=light&tab={tab}'); pg.locator('.stage').screenshot(path='/tmp/st.png')
    V=Image.open('/tmp/st.png'); L=Image.open(LV+lf).crop(box); L=L.resize((int(L.width*V.height/L.height),V.height),Image.LANCZOS)
    W=L.width+V.width+72; c=Image.new('RGB',(W,V.height+70),'#ececec'); d=ImageDraw.Draw(c)
    c.paste(L,(24,56)); c.paste(V,(48+L.width,56)); d.text((24,16),'Lovart 实测（放大）',fill='#222',font=F(22)); d.text((48+L.width,16),'我们 v3（2x）',fill='#222',font=F(22))
    c.save(f'{O}/closeup2x_{n}_lovart_vs_v3.png')
