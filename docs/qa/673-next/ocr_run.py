import csv,json,re,sys
from PIL import Image
import numpy as np
from rapidocr_onnxruntime import RapidOCR
ocr=RapidOCR()
gold=set("VANT LENO 双11 BONBUN 天猫 廓形之选 LUMVEX SUMMICRON ASPH".split())
for r in csv.DictReader(open('/workspace/qa673c/qa673c.csv')):
  if r['name'].split('-')[0] in('promo','ppt','taobao'):
    for t in r['ocr_gold'].split(' | '):
      t=t.strip()
      if len(t)>=3: gold.add(t)
def norm(s): return re.sub(r'[\s\W_]+','',s).upper()
G={norm(g):g for g in gold if len(norm(g))>=2}
imgs={'promo-ex01':'promo-ex01.webp','taobao':'taobao-product-cover.webp','ppt5p':'ppt-visual-ex01-stitched-5p.webp'}
for f in ['LR-promo-ex01-poster5-lens','LR-promo-ex01','LR-ppt-p07','LR-taobao-product']: imgs[f]='lr/'+f+'.jpg'
P=Image.open('promo-ex01.webp').convert('RGB')
xs=[(0,808),(870,1688),(1750,2560)];ys=[(0,1070),(1138,2214)]
crops={}
k=1
for y in ys:
  for x in xs:
    c=P.crop((x[0],y[0],x[1],y[1]));c.save(f'/workspace/qa673n/poster{k}.png');crops[f'poster{k}']=c;k+=1
S=Image.open('ppt-visual-ex01-stitched-5p.webp').convert('RGB')
for i,y in enumerate([0,1047,2094,3141,4188]):
  crops[f'ppt_page{i+1}']=S.crop((0,y,1920,min(y+1047,5235)))
out={}
for n,f in imgs.items(): crops[n]=Image.open(f).convert('RGB')
for n,im in crops.items():
  res,_=ocr(np.array(im)); txt=[(t,round(float(s),2)) for _,t,s in (res or [])]
  hits=[]
  for t,_ in txt:
    nt=norm(t)
    for ng,g in G.items():
      if (len(ng)>=3 and ng in nt) or nt==ng: hits.append((t,g))
  out[n]={'text':txt,'gold_hits':hits}
  print(n,'|',' / '.join(t for t,_ in txt)); print('  GOLD:',hits)
json.dump(out,open('/workspace/qa673n/ocr.json','w'),ensure_ascii=False,indent=1)
