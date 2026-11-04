import os,sys,json,time,requests
sys.path.insert(0,'/workspace/ws');import ws
B=ws.B;H=ws.H
def bal(): return float(requests.get(B+'/balance',headers=H,timeout=20).json()['data']['balance'])
import subprocess
def dl(u,out):
    for _ in range(6):
        if subprocess.run(['curl','-sS','--retry','5','-o',out,u]).returncode==0: return True
        time.sleep(5)
    return False
CAP=0.50;UNIT=0.0378  # tech lead: actual charge per 1K image, measured by balance delta
def recs():
    try: return [json.loads(l) for l in open('calls.jsonl') if l.strip()]
    except FileNotFoundError: return []
def spent(): return round(sum(r.get('cost',0) for r in recs()),6)
def consec_fail(out):
    n=0
    for r in recs():
        if r.get('out')!=out: continue
        n=0 if r.get('ok') else n+1
    return n
import base64
def b64(o,out):
    if not isinstance(o,str) or o.startswith('http'): print('NO BASE64 (url or empty):',str(o)[:60]);return False
    if o.startswith('data:'): o=o.split(',',1)[1]
    open(out,'wb').write(base64.b64decode(o));return True
def run(src,prompt,out,ar):
    if spent()+UNIT>CAP+1e-9: print('CAP STOP spent',spent());sys.exit(3)
    if consec_fail(out)>=2: print('2 CONSEC FAILS STOP',out);sys.exit(4)
    pend=out+'.pending.json'
    if os.path.exists(pend):  # interrupted submit: poll the existing prediction, never resubmit
        p=json.load(open(pend));b0=p['before'];r={'code':200,'data':{'id':p['id']}};print('RESUME poll',p['id'])
    else:
        b0=bal()
        if b0<20: print('BALANCE<20 STOP');sys.exit(2)
        if spent()+UNIT>CAP+1e-9: print('CAP STOP');sys.exit(3)  # pre-check at actual charge $0.0378
        u=[ws.up(src)]
        r=requests.post(f'{B}/google/nano-banana-2.1/edit',headers=H,json={'images':u,'prompt':prompt,'output_format':'png','resolution':'1k','aspect_ratio':ar,'enable_base64_output':True},timeout=60).json()
        if r.get('code')==200: json.dump(dict(id=r['data']['id'],before=b0),open(pend,'w'))
    ok=False;rid=None;done=False
    if r.get('code')==200:
        rid=r['data']['id']
        for _ in range(90):
            time.sleep(4);g=requests.get(f'{B}/predictions/{rid}/result',headers=H,timeout=30).json()['data']
            if g['status']=='completed': ok=b64(g['outputs'][0],out);done=True;break
            if g['status']=='failed': print('FAIL',g.get('error'));done=True;break
        if not done: print('POLL TIMEOUT, pending kept, rerun to resume',rid);sys.exit(5)
    else: print('ERR',{k:v for k,v in r.items() if k!='data'})
    time.sleep(3);b1=bal()
    rec=dict(out=out,id=rid,ok=ok,before=b0,after=b1,cost=round(b0-b1,6));print(json.dumps(rec),flush=True)
    open('calls.jsonl','a').write(json.dumps(rec)+'\n')
    if os.path.exists(pend): os.remove(pend)
    return ok
if __name__=='__main__':
    j=json.load(open(sys.argv[1]));sys.exit(0 if run(j['src'],j['prompt'],j['out'],j['ar']) else 1)
