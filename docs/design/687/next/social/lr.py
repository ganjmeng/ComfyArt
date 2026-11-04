import sys;from PIL import Image,ImageDraw,ImageFont
g,o,out=sys.argv[1:4];H=900
a=Image.open(g).convert('RGB');b=Image.open(o).convert('RGB')
a=a.resize((int(a.width*H/a.height),H));b=b.resize((int(b.width*H/b.height),H))
st=a.width>1200
if st:
    H2=int(H*1200/a.width);a=a.resize((1200,H2));b=b.resize((1200,int(b.height*1200/b.width)));c=Image.new('RGB',(1200,a.height+b.height+60),'white');c.paste(a,(0,30));c.paste(b,(0,a.height+60))
else:
    c=Image.new('RGB',(a.width+b.width+20,H+40),'white');c.paste(a,(0,40));c.paste(b,(a.width+20,40))
d=ImageDraw.Draw(c);d.text((8,4),'L: gold',fill='black');d.text(((8,a.height+34) if st else (a.width+28,4)),'R: ours',fill='black')
c.save(out,quality=88)
