import re,sys,json
from rapidocr_onnxruntime import RapidOCR
o=RapidOCR();N=lambda s:re.sub(r'[\W_]+','',s.lower())
t=lambda p:[x[1] for x in (o(p)[0] or []) if float(x[2])>0.6]
g=t(sys.argv[1]);w=t(sys.argv[2]);wn=' '.join(N(x) for x in w)
r=dict(gold=g,ours=w,verbatim=[x for x in g if len(N(x))>=4 and N(x) in wn]);print(json.dumps(r,ensure_ascii=False))
