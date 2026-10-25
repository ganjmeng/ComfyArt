from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os, json
L='/workspace/lovart-radius/'; O='out'; os.makedirs(O+'/diff',exist_ok=True); os.makedirs(O+'/open',exist_ok=True)
FP='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
try: F=ImageFont.truetype(FP,26); FS=ImageFont.truetype(FP,20)
except: F=FS=ImageFont.load_default()
def bg(w,h,dark):
    im=Image.new('RGB',(w,h),(18,18,22) if dark else (236,238,243)); d=ImageDraw.Draw(im)
    cols=[(70,60,120),(30,90,110),(110,60,80)] if dark else [(200,210,255),(255,220,230),(210,245,235)]
    for i,c in enumerate(cols): d.ellipse([w*(i*.35-.1),h*((i%2)*.4-.2),w*(i*.35+.5),h*((i%2)*.4+.8)],fill=c)
    return im.filter(ImageFilter.GaussianBlur(min(w,h)//5))
def fit(im,h): return im.resize((int(im.width*h/im.height),h),Image.LANCZOS)
def card(im,pad=0,r=18):
    m=Image.new('L',(im.width+2*pad,im.height+2*pad),0);ImageDraw.Draw(m).rounded_rectangle([0,0,m.width-1,m.height-1],r,fill=255)
    c=Image.new('RGBA',m.size,(0,0,0,0));c.paste(im,(pad,pad));c.putalpha(m);return c
def compare(left,right,dark,title,out,h=520,labels=('Lovart (saved capture, measure-only)','ComfyArt #271 + lovart-polish-v1')):
    a,b=fit(left,h),fit(right,h); W=a.width+b.width+40*3+20; H=h+40*2+110
    im=bg(W,H,dark).convert('RGBA'); d=ImageDraw.Draw(im); tc=(240,240,240) if dark else (20,20,20)
    d.text((40,20),title,font=F,fill=tc)
    x=40
    for s,lab in ((a,labels[0]),(b,labels[1])):
        c=card(s.convert('RGB')); sh=Image.new('RGBA',c.size,(0,0,0,90 if dark else 40)); sh.putalpha(c.split()[3].point(lambda v:v*0.35))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)),(x+4,74)); im.alpha_composite(c,(x-10,64))
        d.text((x,H-40),lab,font=FS,fill=tc); x+=s.width+60
    im.convert('RGB').save(out)
lov={'dark':Image.open(L+'c31b_dark_chat_input.png'),'light':Image.open(L+'c07_chat_input.png')}
for lang in ['zh','en']:
  for th in ['dark','light']:
    for w in [1280,360]:
      compare(lov[th],Image.open(f'prop-{lang}-{th}-{w}.png'),th=='dark',f'Composer {lang} {th} {w}',f'{O}/cmp-{lang}-{th}-{w}.png',h=360)
for n in ['model','settings']:
  for th in ['dark','light']:
    for w in [1280,360]:
      compare(Image.open(L+'c10_dropdown.png'),Image.open(f'prop-pop-{n}-{th}-{w}.png'),th=='dark',f'Popover {n} {th} {w} (Lovart ref = its dropdown; no composer-popover capture)',f'{O}/open/cmp-{n}-{th}-{w}.png',h=700)
# diff crops: (lovart file, lovart box in file px), ours box in css px (x2 dsf, relative to clip x-16,y-16 of composer at 12,646 => clip origin (0,630)*2)
cur=Image.open('ours-zh-dark-1280.png'); pro=Image.open('prop-zh-dark-1280.png')
def oc(im,x0,y0,x1,y1,dy=0): return im.crop((int(x0*2),int((y0-630+dy)*2),int(x1*2),int((y1-630+dy)*2)))
D=[('01-button-gap','c31b_dark_chat_input',(40,330,480,500),(12,735,160,785)),
 ('02-left-right-padding','c31b_dark_chat_input',(0,330,1230,540),(0,700,392,800)),
 ('03-icon-text-size','c31b_dark_chat_input',(140,380,440,500),(55,740,160,780)),
 ('04-chevron-text-gap','c31b_dark_chat_input',(240,380,440,500),(80,740,160,780)),
 ('05-btn-to-input-bottom','c31b_dark_chat_input',(1000,360,1230,540),(320,730,392,800)),
 ('06-button-icon-size','c31b_dark_chat_input',(1030,380,1160,500),(335,738,385,782)),
 ('07-colors','c31b_dark_chat_input',(0,120,1230,540),(0,640,392,800)),
]
for name,lf,lb,ob in D:
    l=Image.open(L+lf+'.png').crop(lb)
    a=oc(cur,*ob); b=oc(pro,*ob,dy=2)
    h=300; parts=[fit(l,h),fit(a,h),fit(b,h)]; W=sum(p.width for p in parts)+40*4; im=bg(W,h+110,True); d=ImageDraw.Draw(im); x=40
    for p,lab in zip(parts,['Lovart','ours 18fcf17','proposed']): im.paste(p,(x,50)); d.text((x,h+65),lab,font=FS,fill=(240,240,240)); x+=p.width+40
    d.text((40,10),name,font=F,fill=(240,240,240)); im.save(f'{O}/diff/{name}.png')
# hover
for name,files in [('08-hover-states',('c10_dropdown',None)),('09-popover-radius-shadow',('c10_dropdown',None))]:
    l=Image.open(L+'c10_dropdown.png')
    a=Image.open('ours-zh-light-1280-hover.png' if name.startswith('08') else 'ours-pop-settings-light-1280.png'); b=Image.open('prop-zh-light-1280-hover.png' if name.startswith('08') else 'prop-pop-settings-light-1280.png')
    if name.startswith('09'): a=a.crop((0,240,720,1520)); b=b.crop((0,240,720,1520))
    h=400; parts=[fit(l,h),fit(a,h),fit(b,h)]; W=sum(p.width for p in parts)+160; im=bg(W,h+110,False); d=ImageDraw.Draw(im); x=40
    for p,lab in zip(parts,['Lovart','ours 18fcf17','proposed']): im.paste(p,(x,50)); d.text((x,h+65),lab,font=FS,fill=(20,20,20)); x+=p.width+40
    d.text((40,10),name,font=F,fill=(20,20,20)); im.save(f'{O}/diff/{name}.png')
