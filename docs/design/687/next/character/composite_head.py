"""Local head/face composite (SOP, $0): paste ONLY head+hair ellipses from a generated sheet onto the gold.
usage: python3 composite_head.py gold gen out '[[cx,cy,rx,ry],...]' [feather_px]
- gen is resized to gold size (generated sheets keep gold layout); everything outside the ellipses stays gold pixels.
- per ellipse: LAB mean/std of gen skin/hair is matched to gold inside a thin ring around the lower ellipse (neck seam),
  (set COLOR_MATCH=0 to skip for flat/anime art or when the ring is mostly clothing), then alpha-blended with a Gaussian-feathered mask."""
import os,sys,json,numpy as np,cv2
g=cv2.imread(sys.argv[1]);o=cv2.resize(cv2.imread(sys.argv[2]),(g.shape[1],g.shape[0]),interpolation=cv2.INTER_LANCZOS4)
E=json.loads(sys.argv[4]);F=int(sys.argv[5]) if len(sys.argv)>5 else 24
out=g.astype(np.float32)
for cx,cy,rx,ry in E:
    m=np.zeros(g.shape[:2],np.uint8);cv2.ellipse(m,(cx,cy),(rx,ry),0,0,360,255,-1)
    ring=np.zeros_like(m);cv2.ellipse(ring,(cx,cy),(rx+F,ry+F),0,0,360,255,-1);ring[m>0]=0;ring[:cy]=0
    fg=(cv2.cvtColor(g,cv2.COLOR_BGR2GRAY)<235)  # ignore white background in seam stats
    sel=(ring>0)&fg
    lo=cv2.cvtColor(o,cv2.COLOR_BGR2LAB).astype(np.float32);lg=cv2.cvtColor(g,cv2.COLOR_BGR2LAB).astype(np.float32)
    if sel.sum()>50 and os.environ.get('COLOR_MATCH','1')!='0':  # COLOR_MATCH=0: flat/anime art, ring stats from clothes skew skin
        for c in range(3):
            lo[...,c]=(lo[...,c]-lo[...,c][sel].mean())*(lg[...,c][sel].std()+1)/(lo[...,c][sel].std()+1)*0.3+ (lo[...,c]-lo[...,c][sel].mean())*0.7+lg[...,c][sel].mean()
    oc=cv2.cvtColor(np.clip(lo,0,255).astype(np.uint8),cv2.COLOR_LAB2BGR).astype(np.float32)
    wb=cv2.GaussianBlur((cv2.cvtColor(o,cv2.COLOR_BGR2GRAY)>232).astype(np.float32),(0,0),3)[...,None]
    oc=oc*(1-wb)+o.astype(np.float32)*wb  # keep white background untouched by colour match
    a=cv2.GaussianBlur(m.astype(np.float32)/255,(0,0),F/2)[...,None]
    out=out*(1-a)+oc*a
cv2.imwrite(sys.argv[3],np.clip(out,0,255).astype(np.uint8),[cv2.IMWRITE_WEBP_QUALITY,92]);print('ok',g.shape)
