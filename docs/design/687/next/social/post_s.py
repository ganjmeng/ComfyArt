import sys,os,numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from rembg import remove,new_session
ex=sys.argv[1]
C={'01':dict(W=1088,H=1920,word='BOOST',band=0.17,line='SUNRISE FORMULA',claim='Blood-orange C  ·  Daily softgels  ·  Gentle on stomach',cta='GET YOURS',wc=(220,105,45),gc=(255,200,150),ac=(214,96,40),tc=(70,40,25)),
'03':dict(W=1088,H=1360,word='ECHO',band=0.10,line='SOUND STUDIO',claim='Adaptive quiet  ·  All-day comfort  ·  Lossless detail',cta='LISTEN IN',wc=(250,232,225),gc=(220,160,150),ac=(190,130,115),tc=(80,55,50)),
'04':dict(W=1088,H=1360,word='CRAFT',band=0.10,line='ATELIER FOOTWEAR',claim='Suede upper  ·  Goodyear welt  ·  Hand-finished edges',cta='DISCOVER',wc=(245,238,228),gc=(150,130,100),ac=(110,90,60),tc=(60,50,40)),
'05':dict(W=1088,H=1456,word='ZEST',band=0.08,line='PRESSED DAILY',claim='Just oranges  ·  Nothing added  ·  Bottled cold',cta='GRAB A BOTTLE',wc=(255,255,245),gc=(255,170,30),ac=(235,120,20),tc=(60,40,10))}[ex]
W,Hh=C['W'],C['H']
im=Image.open(f's_ex{ex}_raw.png').convert('RGB').resize((W,Hh),Image.LANCZOS)
cut=remove(im,session=new_session('u2net'))
F='/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc'
if not os.path.exists(F):F='/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
bg=im.convert('RGBA');d=ImageDraw.Draw(bg);txt=C['word'];sz=420
while True:
    f=ImageFont.truetype(F,sz);b=d.textbbox((0,0),txt,font=f)
    if b[2]-b[0]<=W-70:break
    sz-=10
x=(W-(b[2]-b[0]))//2-b[0];y=int(Hh*C['band'])+60-b[1]
g=Image.new('RGBA',(W,Hh),(0,0,0,0));ImageDraw.Draw(g).text((x,y),txt,font=f,fill=C['gc']+(200,))
bg=Image.alpha_composite(bg,g.filter(ImageFilter.GaussianBlur(16)));ImageDraw.Draw(bg).text((x,y),txt,font=f,fill=C['wc']+(255,))
out=Image.alpha_composite(bg,cut);d=ImageDraw.Draw(out)
def c(t,y,f,fill):
    bb=d.textbbox((0,0),t,font=f);d.text(((W-(bb[2]-bb[0]))//2-bb[0],y),t,font=f,fill=fill)
c('L U M O R A',36,ImageFont.truetype(F,44),C['tc']);c(C['line'],94,ImageFont.truetype(F,22),C['ac'])
fc=ImageFont.truetype(F,26);c(C['claim'],Hh-180,fc,C['tc'])
pf=ImageFont.truetype(F,32);bb=d.textbbox((0,0),C['cta'],font=pf);pw=bb[2]-bb[0]+90;px=(W-pw)//2;py=Hh-120
d.rounded_rectangle((px,py,px+pw,py+66),radius=33,fill=C['ac'])
c(C['cta'],py+11,pf,(255,255,255))
if ex=='01':
    c2=lambda t,y,f,fill:(lambda bb:d.text((542-(bb[2]-bb[0])//2-bb[0],y),t,font=f,fill=fill))(d.textbbox((0,0),t,font=f))
    c2('LUMORA',1190,ImageFont.truetype(F,30),(110,60,30));c2('C+ SOFTGELS',1240,ImageFont.truetype(F,20),(200,95,40))
out.convert('RGB').save(f's_ex{ex}.webp',quality=90);print(out.size)
