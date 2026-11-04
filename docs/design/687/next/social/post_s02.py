from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np,cv2
from rembg import remove,new_session
W,Hh=1088,1360
raw=Image.open('s_ex02_raw.png').convert('RGB')
a=np.array(raw);k=928/660
m=np.zeros(a.shape[:2],np.uint8);cv2.ellipse(m,(int(297*k),int(424*k)),(int(13*k),int(22*k)),0,0,360,255,-1)
a=cv2.inpaint(a,m,7,cv2.INPAINT_TELEA)
im=Image.fromarray(a).resize((W,Hh),Image.LANCZOS)
cut=remove(im,session=new_session('u2net'))
al=np.array(cut)[...,3];al[:int(Hh*0.30)]=al[:int(Hh*0.30)]  # keep
F='/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
import os
if not os.path.exists(F):F='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
bg=im.copy();d=ImageDraw.Draw(bg)
# giant word band y 10-38%
txt='SURGE';sz=400
while True:
    f=ImageFont.truetype(F,sz);b=d.textbbox((0,0),txt,font=f)
    if b[2]-b[0]<=W-60:break
    sz-=10
x=(W-(b[2]-b[0]))//2-b[0];y=int(Hh*0.10)-b[1]
glow=Image.new('RGBA',(W,Hh),(0,0,0,0));gd=ImageDraw.Draw(glow);gd.text((x,y),txt,font=f,fill=(40,230,220,255))
glow=glow.filter(ImageFilter.GaussianBlur(18))
bg=Image.alpha_composite(bg.convert('RGBA'),glow);d=ImageDraw.Draw(bg)
d.text((x,y),txt,font=f,fill=(225,255,252,255))
out=Image.alpha_composite(bg,cut);d=ImageDraw.Draw(out)
fb=ImageFont.truetype(F,46);fs=ImageFont.truetype(F,22)
def c(t,y,f,fill):
    bb=d.textbbox((0,0),t,font=f);d.text(((W-(bb[2]-bb[0]))//2-bb[0],y),t,font=f,fill=fill)
c('L U M O R A',40,fb,(240,255,255,255));c('TIDE  SERIES',100,fs,(60,230,220,255))
c('Hall-effect sticks   ·   40h battery   ·   Low-latency 2.4G',1180,ImageFont.truetype(F,26),(230,245,245,255))
pw,ph=360,68;px=(W-pw)//2;py=1250
d.rounded_rectangle((px,py,px+pw,py+ph),radius=34,fill=(40,215,205,255))
c('RESERVE YOURS',py+10,ImageFont.truetype(F,34),(10,25,30,255))
out.convert('RGB').save('s_ex02.webp',quality=90);print(out.size)
