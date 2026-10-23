"""Mock WaveSpeed + ComfyUI host for docs screenshots / manual e2e (#211). Mocks only, never calls WaveSpeed.
Run: RV_REPO=<repo> RV_PKG=<parent of repo> python tests/mock_wavespeed_server.py  (app on :8392, mock WaveSpeed on :9392)"""
import os, sys, asyncio, importlib.util, io, tempfile, json
R=os.environ["RV_REPO"]; sys.path.insert(0, os.environ["RV_PKG"]); sys.path.insert(0, R+"/tests")
os.environ.pop("WAVESPEED_API_KEY", None)
if os.environ.get("RV_DUMMY_KEY"): os.environ["WAVESPEED_API_KEY"]="mock-not-a-real-key"
os.environ["WAVESPEED_BASE_URL"] = "http://127.0.0.1:9392"
from PIL import Image, ImageDraw
from aiohttp import web
from mock_wavespeed_pricing import load_catalog, mock_price
import conftest  # installs ComfyUI stubs + imports ComfyArt
import folder_paths
folder_paths.folder_names_and_paths = {}; folder_paths.supported_pt_extensions = {".safetensors"}
base = tempfile.mkdtemp(prefix="rv-"); folder_paths.STATE["base"] = __import__("pathlib").Path(base)
for d in ("input","output","temp","user/default"): os.makedirs(os.path.join(base,d), exist_ok=True)
spec = importlib.util.spec_from_file_location("tws", R+"/tests/test_wavespeed.py")
tws = importlib.util.module_from_spec(spec); spec.loader.exec_module(tws)
img = Image.new("RGB",(1024,1024),(40,90,160)); dr = ImageDraw.Draw(img)
for i in range(0,512,64): dr.ellipse((i,i,1024-i,1024-i), outline=(255,200-i//8,80), width=6)
dr.text((380,500),"MOCK WAVESPEED RESULT",fill="white"); buf=io.BytesIO(); img.save(buf,"PNG"); PNG=buf.getvalue()
# mock wavespeed
FX=json.load(open(R+"/tests/fixtures/wavespeed_catalog_subset.json"))
tws.MODELS=tws.MODELS+[FX[m] for m in ("openai/gpt-image-2.5-sunburst/edit","openai/gpt-image-2.5-flare/edit") if m in FX and all(x["model_id"]!=m for x in tws.MODELS)]
ws = web.Application(); n=[0]

_cur=open(R+"/api/curated_models.json").read()
tws.MODELS=tws.MODELS+[v for k,v in FX.items() if ('"'+k+'"') in _cur and all(x["model_id"]!=k for x in tws.MODELS)]
async def models(r): return web.json_response({"code":200,"data":tws.MODELS})
async def submit(r):
    n[0]+=1; b=await r.json(); print("MOCK submit", r.match_info["model"], json.dumps({k:v for k,v in b.items() if k not in ("images","image","prompt")}), flush=True)
    return web.json_response({"code":200,"data":{"id":f"task{n[0]}","status":"created"}})
MODE=os.environ.get("RV_MODE","ok")
T0={}
CAT=load_catalog(tws.MODELS)
async def price(r):
    # #211: every model is priced at its catalog base_price; no placeholder for unknown models.
    b=await r.json(); i=b.get("inputs") or {}; m=b.get("model_id") or ""
    p=mock_price(m, CAT)
    print("MOCK price", m, json.dumps({k:v for k,v in i.items() if k not in ("images","image","prompt")}), "->", p, flush=True)
    if p is None: return web.json_response({"code":404,"message":f"model {m} not in mock catalog"},status=404)
    return web.json_response({"code":200,"data":{"price":p}})
async def result(r):
    import time
    if MODE=="401": return web.json_response({"code":401,"message":"Unauthorized"},status=401)
    if MODE=="fail": return web.json_response({"code":200,"data":{"id":r.match_info["id"],"status":"failed","outputs":[],"error":"mock model error"}})
    if MODE=="timeout": return web.json_response({"code":200,"data":{"id":r.match_info["id"],"status":"processing","outputs":[],"error":""}})
    return web.json_response({"code":200,"data":{"id":r.match_info["id"],"status":"completed","outputs":["http://127.0.0.1:9392/cdn/out.png"],"error":""}})
async def upload(r):
    rd=await r.multipart()
    async for p in rd: await p.read()
    return web.json_response({"code":200,"data":{"download_url":"http://127.0.0.1:9392/cdn/out.png"}})
async def cdn(r): return web.Response(body=PNG, content_type="image/png")
async def bal(r): return web.json_response({"code":200,"data":{"balance":12.5}})
ws.router.add_get("/api/v3/balance",bal); ws.router.add_get("/api/v3/models",models); ws.router.add_post("/api/v3/model/price",price); ws.router.add_post("/api/v3/media/upload/binary",upload)
ws.router.add_get("/api/v3/predictions/{id}/result",result); ws.router.add_post("/api/v3/{model:.+}",submit); ws.router.add_get("/cdn/out.png",cdn)
# host stub
from server import PromptServer
app = web.Application(client_max_size=200*2**20)
app.router.add_routes(PromptServer.instance.routes)
for rd in PromptServer.instance.routes:
    if isinstance(rd, web.RouteDef): app.router.add_route(rd.method, "/api"+rd.path, rd.handler)
async def ud_list(r): return web.json_response([])
async def model_list(r): return web.json_response([])
app.router.add_get("/api/userdata", ud_list); app.router.add_get("/api/models/{k}", model_list)
async def view(r):
    q=r.query; p=os.path.join(base,q.get("type","output"),q.get("subfolder",""),q["filename"])
    return web.FileResponse(p) if os.path.isfile(p) else web.Response(status=404)
async def settings_get(r): return web.json_response(None)
async def settings_post(r): return web.json_response({})
async def queue(r): return web.json_response({"queue_running":[],"queue_pending":[]})
async def empty(r): return web.json_response({})
def ud(r): return os.path.join(base,"user/default",r.match_info["file"])
async def ud_get(r): return web.FileResponse(ud(r)) if os.path.isfile(ud(r)) else web.Response(status=404)
async def ud_post(r):
    os.makedirs(os.path.dirname(ud(r)),exist_ok=True); open(ud(r),"wb").write(await r.read()); return web.json_response(r.match_info["file"])
async def upload_image(r):
    rd=await r.post(); f=rd["image"]; sub=rd.get("subfolder",""); t=rd.get("type","input")
    d=os.path.join(base,t,sub); os.makedirs(d,exist_ok=True); open(os.path.join(d,f.filename),"wb").write(f.file.read())
    return web.json_response({"name":f.filename,"subfolder":sub,"type":t})
async def wsock(r):
    s=web.WebSocketResponse(); await s.prepare(r); await s.send_json({"type":"status","data":{"sid":"rv","status":{"exec_info":{"queue_remaining":0}}}})
    async for _ in s: pass
    return s
app.router.add_get("/api/view",view); app.router.add_get("/api/settings/{id}",settings_get); app.router.add_post("/api/settings/{id}",settings_post)
app.router.add_get("/api/queue",queue); app.router.add_post("/api/queue",empty); app.router.add_post("/api/interrupt",empty)
app.router.add_get("/api/userdata/{file:.+}",ud_get); app.router.add_post("/api/userdata/{file:.+}",ud_post)
app.router.add_post("/api/upload/image",upload_image); app.router.add_get("/ws",wsock)
async def main():
    for a,port in ((ws,9392),(app,8392)):
        rn=web.AppRunner(a); await rn.setup(); await web.TCPSite(rn,"127.0.0.1",port).start()
    print("READY", flush=True); await asyncio.Event().wait()
asyncio.run(main())
