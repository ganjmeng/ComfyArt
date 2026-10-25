from PIL import Image,ImageDraw,ImageFilter,ImageFont
import glob
F=[f for f in glob.glob('/usr/share/fonts/**/*CJK*Regular*',recursive=True)+glob.glob('/usr/share/fonts/**/*CJK*',recursive=True)][0]
def font(s): return ImageFont.truetype(F,s)
def backdrop(W,H,dark):
  base=(18,19,22) if dark else (244,243,240)
  im=Image.new('RGB',(W,H),base); L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
  blobs=[((-.1,-.2,.55,.6),(120,110,190,70) if dark else (214,206,240,150)),((.5,.4,1.15,1.2),(70,130,150,60) if dark else (200,228,226,150)),((.25,-.3,.85,.35),(160,110,90,40) if dark else (246,222,206,130))]
  for (a,b,c,e),col in blobs: d.ellipse((a*W,b*H,c*W,e*H),fill=col)
  L=L.filter(ImageFilter.GaussianBlur(min(W,H)//4)); im.paste(L,(0,0),L); return im
def card(bg,img,x,y,dark):
  sh=Image.new('RGBA',bg.size,(0,0,0,0)); ImageDraw.Draw(sh).rounded_rectangle((x,y+10,x+img.width,y+img.height+10),36,fill=(0,0,0,120 if dark else 40))
  sh=sh.filter(ImageFilter.GaussianBlur(22)); bg.paste(sh,(0,0),sh)
  m=Image.new('L',img.size,0); ImageDraw.Draw(m).rounded_rectangle((0,0,img.width-1,img.height-1),32,fill=255); bg.paste(img,(x,y),m)
def make(key,dark,title):
  cells=[[f'raw/before-{key}-empty.png',f'raw/before-{key}-typed.png'],[f'raw/after-{key}-empty.png',f'raw/after-{key}-typed.png']]
  ims=[[Image.open(p).convert('RGB') for p in c] for c in cells]
  cw=max(i.width for c in ims for i in c); ch=max(i.height for c in ims for i in c)
  P=72;G=56;T=120;LB=56
  W=P*2+cw*2+G; H=T+P+(ch+LB)*2+G+P//2
  bg=backdrop(W,H,dark); d=ImageDraw.Draw(bg); tc=(236,236,236) if dark else (28,28,30); sc=(150,150,156) if dark else (110,110,116)
  d.text((P,P-16),title,font=font(40),fill=tc)
  heads=[('Before · main 9ce7b98 + #267','After · #268 mock')]
  for ci,col in enumerate(['Before（#267 tip 787c9e8）','After（#268 mock）']):
    x=P+ci*(cw+G); d.text((x,T+P-8-LB//2),col,font=font(30),fill=tc)
    for ri,lab in enumerate(['空 / empty','有文字 / typed']):
      y=T+P+ri*(ch+LB+G//2)+LB//2
      d.text((x,y-4),lab,font=font(24),fill=sc); card(bg,ims[ci][ri],x,y+LB-14,dark); d=ImageDraw.Draw(bg)
  out=f'out/cmp-{key}.png'; bg.save(out,optimize=True); print(out,bg.size)
for th in('light','dark'):
  for lang in('zh','en'):
    for w in(1280,360): make(f'image-{lang}-{th}-{w}',th=='dark',f'#268 语音/发送合一 · 图像 · {lang} · {th} · {w}')
for m in('video','agent'): make(f'{m}-zh-dark-360',True,f'#268 语音/发送合一 · {"视频" if m=="video" else "Agent"} · zh · dark · 360')
