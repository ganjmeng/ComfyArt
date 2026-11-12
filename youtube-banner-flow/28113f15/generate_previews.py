import io, sys, json, importlib.util
from PIL import Image, ImageDraw, ImageFilter
spec=importlib.util.spec_from_file_location("bc","/workspace/wt_ytflow/ComfyArt/api/banner_compose.py")
bc=importlib.util.module_from_spec(spec); sys.modules["bc"]=bc; spec.loader.exec_module(bc)
W,H=2048,1152
img=Image.new("RGB",(W,H),(250,247,240))
d=ImageDraw.Draw(img)
s=W/2560
# soft texture top-left / bottom (TV area)
lay=Image.new("RGB",(W,H),(250,247,240)); ld=ImageDraw.Draw(lay)
ld.ellipse((60*s,40*s,760*s,380*s),fill=(232,238,252)); ld.ellipse((1500*s,1120*s,2500*s,1440*s),fill=(253,236,226))
lay=lay.filter(ImageFilter.GaussianBlur(60)); img=lay
d=ImageDraw.Draw(img)
# main graphic right of middle band
d.ellipse((1790*s,560*s,2060*s,890*s),fill=(47,107,255))
d.rounded_rectangle((1930*s,630*s,2050*s,810*s),radius=18,fill=(255,122,89))
d.ellipse((1760*s,820*s,1810*s,870*s),fill=(255,210,90))
buf=io.BytesIO(); img.save(buf,"PNG"); base=buf.getvalue()
open("synthetic-base-2048x1152.png","wb").write(base)
png,rep=bc.compose(base,channel="Loomi Studio",tagline="AI 绘画教程 · 创意工作流",schedule="每周二 / 周五更新",brand_color="#2F6BFF",skill=bc.SKILL,purpose=bc.PURPOSE_USER_FINAL)
full=Image.open(io.BytesIO(png)).convert("RGB")
full.save("01-tv-full-canvas-2560x1440.png",optimize=True)
full.crop(bc.DESKTOP_BAND).save("02-desktop-band-0-509-2560-931.png",optimize=True)
full.crop(bc.HARD_BOUNDARY).save("03-all-devices-482-509-2078-931.png",optimize=True)
g=full.copy(); gd=ImageDraw.Draw(g)
for box,col in ((bc.DESKTOP_BAND,(120,120,120)),(bc.HARD_BOUNDARY,(220,40,40)),(bc.STRICT_CORE,(240,140,0)),(bc.TARGET_BOX,(0,160,80))):
    gd.rectangle([box[0],box[1],box[2]-1,box[3]-1],outline=col,width=4)
for l in rep["lines"]:
    b=l["ink_bbox"]; gd.rectangle([b[0],b[1],b[2]-1,b[3]-1],outline=(160,0,200),width=2)
g.save("04-guides-overlay.png",optimize=True)
json.dump(rep,open("report-short.json","w"),ensure_ascii=False,indent=1)
# long + very long on the same base, all-device crop
for tag,(ch,tg,sc) in {"long":("Loomi Studio 创意工作室官方频道","AI 绘画教程 · 创意工作流 · Stable Diffusion / ComfyUI / Midjourney 全流程实战","每周二、周五晚上 8 点更新，周末不定期直播答疑"),
 "very-long":("Loomi Studio 创意工作室官方频道 Creative Workflow Lab International Edition","AI 绘画教程 · 创意工作流 · Stable Diffusion / ComfyUI / Midjourney / Flux / Krea 全流程实战，从零基础到商业交付的完整课程体系","每周二、周五晚上 8 点更新，周末不定期直播答疑，会员专属工作流模板每月更新一次（北京时间）")}.items():
    p,r=bc.compose(base,channel=ch,tagline=tg,schedule=sc,brand_color="#2F6BFF",skill=bc.SKILL,purpose=bc.PURPOSE_USER_FINAL)
    Image.open(io.BytesIO(p)).convert("RGB").crop(bc.HARD_BOUNDARY).save(f"05-{tag}-all-devices.png",optimize=True)
    json.dump(r,open(f"report-{tag}.json","w"),ensure_ascii=False,indent=1)
print(rep["scale"], [ (l["role"],l["px"],l["ink_bbox"]) for l in rep["lines"]])
