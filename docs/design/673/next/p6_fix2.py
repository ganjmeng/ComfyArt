# poster6 round 2 (tech-lead wash ruling): REPLACE the gold-derived top-left cookie from p6_fix.py step 2.
# Cookie source = OUR OWN washed asset: the chocolate cookie in the box of docs/design/673/next/promo-ex01.webp
#   (tip 2640315d, ellipse centre (2270,1836) r 55x47) -- no gold pixels. Rotated 35deg, scaled 1.45x, dome-shaded:
#   round outline, no bite notch, chunk layout of our cookie -> visibly differs from gold's cookie.
# Also: M&M cookie right edge sharpened (x2262-2292,y1645-1695), packet bottom-right light spot cleaned.
import numpy as np,cv2;from PIL import Image
P='promo-ex01.webp';a=np.array(Image.open(P).convert('RGB')).astype(np.float32);H,W=a.shape[:2];rng=np.random.default_rng(11)
src=a.copy()
# 1) erase old cookie -> per-row mint from clean band
y0,y1,x0,x1=1444,1622,1868,2070
mint=np.median(a[y0:y1,2125:2200],1);reg=np.zeros((H,W),bool);reg[y0:y1,x0:x1]=1;reg[1575:,:1895]=0
for y in range(y0,y1):
    m=reg[y];a[y,m]=mint[y-y0]+rng.normal(0,1.2,(m.sum(),3))
# 2) our cookie
cx,cy,rx,ry=2270,1836,55,47;S=1.45;ang=35
pc=src[cy-70:cy+70,cx-70:cx+70];mk=np.zeros(pc.shape[:2],np.float32);cv2.ellipse(mk,(70,70),(rx,ry),0,0,360,1,-1)
M=cv2.getRotationMatrix2D((70,70),ang,S);M[:,2]+=[70*S-70,70*S-70];n=int(140*S)
pc=cv2.warpAffine(pc,M,(n,n),flags=cv2.INTER_CUBIC);mk=cv2.warpAffine(mk,M,(n,n))
mk=cv2.GaussianBlur(mk,(0,0),0.8)[...,None]
yy,xx=np.mgrid[0:n,0:n];d=np.sqrt(((xx-n/2-12)/(rx*S))**2+((yy-n/2-14)/(ry*S))**2)
pc=pc*np.clip(1.15-0.35*d,0.7,1.15)[...,None]   # dome light from top-left
pc=cv2.addWeighted(pc,1.5,cv2.GaussianBlur(pc,(0,0),1.2),-0.5,0)
tx,ty=1968-n//2,1612-int(ry*S*1.0)-n//2+int(ry*S*0.0)
ty=1536-n//2
a[ty:ty+n,tx:tx+n]=pc*mk+a[ty:ty+n,tx:tx+n]*(1-mk)
print('cookie box',tx+n//2-int(rx*S),ty+n//2-int(rx*S),tx+n//2+int(rx*S),ty+n//2+int(rx*S))
# 3) M&M right edge unsharp
r=a[1640:1700,2255:2298];a[1640:1700,2255:2298]=cv2.addWeighted(r,1.8,cv2.GaussianBlur(r,(0,0),1.5),-0.8,0)
# 4) packet bottom-right light spot: clone packet face from 30px left
r=a[1980:2070,2370:2480];bg=cv2.medianBlur(np.clip(r,0,255).astype(np.uint8),31).astype(np.float32)
hot=(r.mean(2)-bg.mean(2))>6;hot=cv2.dilate(hot.astype(np.uint8),np.ones((5,5)))
w=cv2.GaussianBlur(hot.astype(np.float32),(0,0),1.5)[...,None];print('spot px',int(hot.sum()))
a[1980:2070,2370:2480]=bg*w+r*(1-w)
Image.fromarray(np.clip(a,0,255).astype(np.uint8)).save(P,quality=90,method=6)
