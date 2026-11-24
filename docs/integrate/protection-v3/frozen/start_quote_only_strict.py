from pathlib import Path
import os,shlex,hashlib,uuid
R=Path(__file__).resolve().parent
assert hashlib.sha256((R/'bootstrap_quote_only_strict.py').read_bytes()).hexdigest()=='fab44c9a26114200fcc0b21f29e92db1dfce7c166e3da8684dd709847f2557ff'
assert hashlib.sha256((R/'wavespeed_price_guard.py').read_bytes()).hexdigest()=='565b321b4f2773d100be570642d0eb8a003f1fa68ed1e429921d36a5a3ce3526'
assert hashlib.sha256((R/'quote_detail_probe_80d1d1fe.strict.py').read_bytes()).hexdigest()=='42bb78cd9ce09941081cbfef6b08d88ad763014c4f13ec01400713d8ba49420a','strict probe hash mismatch'
key=None
for line in Path('/home/box/.secrets/comfyart-test.env').read_text().splitlines():
    item=line.strip()
    for prefix in ('WAVESPEED_API_KEY=','export WAVESPEED_API_KEY='):
        if item.startswith(prefix):
            value=shlex.split(item[len(prefix):],comments=True)
            if value and value[0].strip():key=value[0]
    if key:break
if not key:raise SystemExit('WaveSpeed key missing; not started')
private=R/('strict-private-'+uuid.uuid4().hex);private.mkdir(exist_ok=False)
for name in ('comfyui-user','input','output'):(private/name).mkdir()
env={'PATH':'/workspace/cu-venv/bin:/usr/local/bin:/usr/bin:/bin','HOME':str(private),'XDG_CACHE_HOME':str(private/'cache'),
'PYTHONUNBUFFERED':'1','PYTHONDONTWRITEBYTECODE':'1','COMFYART_SKIP_KEY_CHECK':'1','COMFYUI_DISABLE_PRODUCT_TIPS':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
'COMFYART_HOME':str(private),'COMFYART_PLUGIN':str(R.parent/'source-80d1d1fe'),'COMFYART_CONTROLLED_PRECHECK_ONLY':'1',
'COMFYART_QUOTE_PROBE_EXECUTE':'1','WAVESPEED_API_KEY':key}
os.execve('/workspace/cu-venv/bin/python',['/workspace/cu-venv/bin/python',str(R/'bootstrap_quote_only_strict.py')],env)
