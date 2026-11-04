# small-text audit: gold block must exist in ours (OCR 1x+3x tiles), shift tolerant
import csv,os,json,difflib
from rapidocr_onnxruntime import RapidOCR
from PIL import Image,ImageDraw
import numpy as np
ocr=RapidOCR()
W='/tmp/q736/wt/';G='/workspace/673/gold/';TG='/workspace/ComfyArt/docs/design/643/78/gold/taobao-product/'
P=[]
for s,g in [('logo-abstract','logo-abstract/cover.webp'),('naive-illustration','naive-illustration/cover.webp'),('photo-split-poster','photo-split-poster-v2/cover.png'),('ppt-visual','ppt-visual/cover.png'),('promo-ecommerce','promo-ecommerce/cover.webp')]: P.append((f'673/wash/{s}/cover.webp',G+g,'#727'))
for i,e in enumerate(['ex02','ex06','ex09','ex10'],1): P.append((f'673/wash/logo-abstract/examples/0{i}.webp',G+f'logo-abstract/{e}.webp','#727'))
for i,e in enumerate(['ex01.png','ex02.png','ex03.png','ex04.webp'],1): P.append((f'673/wash/naive-illustration/examples/0{i}.webp',G+'naive-illustration/'+e,'#727'))
P+=[('673/wash/photo-split-poster/examples/01.webp',G+'photo-split-poster-v2/ex01.webp','#727'),('673/wash/ppt-visual/examples/01.webp',G+'ppt-visual/ex01.jpg','#727+#736'),('673/wash/promo-ecommerce/examples/01.webp',G+'promo-ecommerce/ex02.webp','#727+#736'),
 ('643/wash/taobao-product/cover.webp',TG+'cover.webp','#736'),('643/wash/taobao-product/examples/07.webp',TG+'examples/ex-07.webp','#736')]
def boxes(im):
    res=[]
    for s in (1,3):
        a=im if s==1 else im.resize((im.width*3,im.height*3));T=1600;st=1400
        for y0 in range(0,a.height,st):
          for x0 in range(0,a.width,st):
            r,_=ocr(np.array(a.crop((x0,y0,min(x0+T,a.width),min(y0+T,a.height))))[:,:,::-1])
            for b,t,c in (r or []):
                xs=[p[0]+x0 for p in b];ys=[p[1]+y0 for p in b]
                if float(c)>0.6: res.append([min(xs)/s,min(ys)/s,max(xs)/s,max(ys)/s,t])
    out=[]
    for b in sorted(res,key=lambda b:-(b[2]-b[0])):
        if not any(ov(b,d)>0.5 for d in out): out.append(b)
    return out
def ov(a,b):
    ix=max(0,min(a[2],b[2])-max(a[0],b[0]));iy=max(0,min(a[3],b[3])-max(a[1],b[1]));return ix*iy/max((a[2]-a[0])*(a[3]-a[1]),1)
rows=[];allD={}
for o,g,pr in P:
    if not os.path.exists(g): rows.append([o,g,pr,'','','','','NO_GOLD','']);continue
    GI=Image.open(g).convert('RGB');OI=Image.open(W+o).convert('RGB')
    sx,sy=OI.width/GI.width,OI.height/GI.height
    gb=[b for b in boxes(GI) if len(b[4].strip())>=2];ob=boxes(OI)
    gb=[[b[0]*sx,b[1]*sy,b[2]*sx,b[3]*sy,b[4]] for b in gb]
    tol=0.04*max(OI.size);drop=[];typo=[]
    for b in gb:
        e=[b[0]-tol,b[1]-tol,b[2]+tol,b[3]+tol]
        near=[x for x in ob if ov(x,e)>0.3 or ov(e,x)>0.05]
        if not near: drop.append(b)
        else:
            best=max(near,key=lambda x:difflib.SequenceMatcher(None,x[4],b[4]).ratio())
            r=difflib.SequenceMatcher(None,best[4],b[4]).ratio()
            if 0.6<=r<1 and len(b[4])>=3: typo.append((b[4],best[4]))
    allD[o]=dict(drop=[[int(v) for v in d[:4]]+[d[4]] for d in drop],typo_candidates=typo)
    if drop:
        cr=[]
        for d in drop[:30]:
            bx=tuple(int(v) for v in (max(0,d[0]-20),max(0,d[1]-15),d[2]+20,d[3]+15))
            gc=GI.crop(tuple(int(v) for v in (bx[0]/sx,bx[1]/sy,bx[2]/sx,bx[3]/sy))).resize((bx[2]-bx[0],bx[3]-bx[1]));oc=OI.crop(bx)
            r=Image.new('RGB',(gc.width*2+20,gc.height),'white');r.paste(gc,(0,0));r.paste(oc,(gc.width+20,0));cr.append(r)
        Wd=max(c.width for c in cr);S=Image.new('RGB',(Wd,sum(c.height+8 for c in cr)),'gray');y=0
        for c in cr:S.paste(c,(0,y));y+=c.height+8
        S.save('sheets/'+o.replace('/','_').replace('.webp','.jpg'),quality=80)
    rows.append([o,g.replace('/workspace/',''),pr,len(gb),len(ob),len(drop),len(typo),'FAIL' if drop else 'PASS','；'.join(d[4] for d in drop)])
    print(rows[-1],flush=True)
w=csv.writer(open('small_text_audit.csv','w',newline=''));w.writerow(['image','gold','pr','gold_blocks','our_blocks','dropped','typo_candidates','ocr_verdict','dropped_items']);w.writerows(rows)
json.dump(allD,open('audit_detail.json','w'),ensure_ascii=False,indent=1)
