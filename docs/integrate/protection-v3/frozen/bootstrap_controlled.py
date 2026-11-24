"""One scoped normal-server run; no source/gate changes, no credential logging."""
import sys,os,time,threading,json,hashlib,importlib,runpy,socket
from pathlib import Path
import aiohttp
ROOT=Path(__file__).resolve().parent
PLUGIN=Path('/workspace/wt_1008_final_c7c89195').resolve()
AUTH=Path('/workspace/comfyart-authority-1004')
LEDGER=AUTH/'ledgers/comfyart-pr1004-new-usd2-grant-v1.json'
EXPECTED_SHA='c7c891955e6402bf566af47f5a2dc37925cff7df'
SOURCE='da5dbe0b30b5eaa2d31d550d3db6f56a6d1f26f6cd4e9a5666f4965e7abffdc4'
URL='https://api.deepseek.com/chat/completions'
OFFICIAL_IPS=set()
WAVESPEED_IPS=set()  # intentionally never populated; no permanent WaveSpeed IP grant
import importlib.util as _ilu
_gpath=Path(__file__).resolve().parent/'wavespeed_price_guard.py'
_gspec=_ilu.spec_from_file_location('wavespeed_price_guard', _gpath)
_g=_ilu.module_from_spec(_gspec); _gspec.loader.exec_module(_g)
request_allowed=_g.request_allowed; socket_connect_allowed=_g.socket_connect_allowed
AUDIT=ROOT/'controlled-http-audit.jsonl'
_lock=threading.Lock()

def emit(value):
    with _lock:
        with AUDIT.open('a') as f:f.write(json.dumps(value,ensure_ascii=True)+'\n')

def deny_record(host,port,where):
    # Audit only: never headers, bodies or env; a logging failure never changes the decision.
    try:emit({'ts':time.time(),'kind':'denied','where':where,'host':None if host is None else str(host),'port':port})
    except Exception:pass

def network_audit(event,args):
    if event!='socket.connect':return
    address=args[1]
    if not isinstance(address,tuple):deny_record(None,None,'socket_unix');raise PermissionError('controlled network: no Unix socket outbound')
    host,port=address[:2]
    if _g.price_socket_allowed(args[0],address):return
    ok,why=socket_connect_allowed(address,wavespeed_ips=set(),official_ips=OFFICIAL_IPS)
    if ok:return
    deny_record(host,port,'socket');raise PermissionError('controlled network: target not allowlisted')
sys.addaudithook(network_audit)
# The connector issues sockets only from the validated owner task; sockets may
# then be connected by its internal Happy-Eyeballs tasks, never arbitrary sockets.
import aiohappyeyeballs
_original_start_connection=aiohappyeyeballs.start_connection
async def controlled_start_connection(*args,**kwargs):
    scope=_g._PRICE_SCOPE.get()
    if scope is not None:
        kwargs['socket_factory']=_g.scoped_socket_factory(kwargs.get('socket_factory'))
    return await _original_start_connection(*args,**kwargs)
aiohappyeyeballs.start_connection=controlled_start_connection
_original_request=aiohttp.ClientSession._request
def controlled_mcp_read_allowed(kind, name, params):
    """Local first-turn policy only; skill permission is exactly a named read."""
    if kind != 'tools/call':
        return False
    if name in {'get_canvas', 'view_canvas', 'list_pages', 'list_models', 'get_model_params', 'ask_user', 'update_plan'}:
        return True
    if name != 'skill' or type(params) is not dict or set(params) != {'name', 'arguments'}:
        return False
    arguments = params['arguments']
    return (type(arguments) is dict and set(arguments) == {'action', 'name'}
            and arguments['action'] == 'read'
            and type(arguments['name']) is str and bool(arguments['name'].strip()))

async def controlled_request(self,method,url,**kwargs):
    from urllib.parse import urlsplit
    p=urlsplit(str(url)); record=None; price_scope=None; price_token=None
    _dh,_dp=p.hostname,(p.port or (443 if p.scheme=='https' else 80))
    official=(p.scheme=='https' and p.netloc=='api.deepseek.com' and not p.query and not p.fragment)
    local=(p.scheme=='http' and p.netloc=='127.0.0.1:8931' and p.path=='/comfyart/mcp')
    allowed,reason,info=request_allowed(method,url,kwargs)
    if allowed:
        transport_ok,transport_reason=_g.transport_options_allowed(self,kwargs)
        if not transport_ok:
            deny_record(_dh,_dp,transport_reason);raise PermissionError('controlled wavespeed transport override prohibited')
        # Never follow redirects (would be a host/path escape). Resolver runs only after the guard.
        kwargs['allow_redirects']=False
        price_ips={x[4][0] for x in socket.getaddrinfo('api.wavespeed.ai',443,type=socket.SOCK_STREAM)}
        emit({'event':'wavespeed_allowed','method':str(method).upper(),'path':info.get('path'),'reason':reason})
    elif official:
        if not ((method=='GET' and p.path=='/models') or (method=='POST' and p.path=='/chat/completions')):
            deny_record(_dh,_dp,'http_official_purpose');raise PermissionError('controlled official purpose not allowed')
        OFFICIAL_IPS.update(x[4][0] for x in socket.getaddrinfo('api.deepseek.com',443,type=socket.SOCK_STREAM))
        if method=='POST':
            raw=kwargs.get('data')
            if type(raw) is not bytes or kwargs.get('allow_redirects') is not False:
                deny_record(_dh,_dp,'http_frozen_sender');raise PermissionError('controlled model requires actual frozen sender')
            body=json.loads(raw); state=json.loads(LEDGER.read_text())
            digest=hashlib.sha256(raw).hexdigest()
            rows=[r for r in state['reservations'].values() if r.get('status')=='reserved' and r.get('body_sha256')==digest]
            if len(rows)!=1 or body.get('model')!='deepseek-flash':deny_record(_dh,_dp,'http_reservation_mismatch');raise PermissionError('controlled model reservation mismatch')
            row=rows[0]
            record={'event':'model_post_started','request_id':row['id'],'sha256':digest,'body_bytes':len(raw),
                    'reserved_nano':row['reserved_nano'],'input_bound':row['input_bound'],'max_output_tokens':row['max_output_tokens'],
                    'tools_count':len(body.get('tools',[])),'tool_names':[t['function']['name'] for t in body.get('tools',[])],
                    'thinking':body.get('thinking'),'message_roles':[m.get('role') for m in body.get('messages',[])],
                    'image_parts':sum(isinstance(part,dict) and part.get('type')=='image_url' for m in body.get('messages',[]) if isinstance(m.get('content'),list) for part in m['content'])}
            emit(record)
    elif local:
        rpc=kwargs.get('json')
        if method!='POST' or type(rpc) is not dict or rpc.get('jsonrpc')!='2.0':deny_record(_dh,_dp,'http_local_purpose');raise PermissionError('controlled local purpose not allowed')
        kind=rpc.get('method');params=rpc.get('params') or {};name=params.get('name')
        precheck=(kind=='tools/call' and name=='generate_image' and os.environ.get('COMFYART_CONTROLLED_PRECHECK_ONLY')=='1')
        if kind!='tools/list' and not precheck and not controlled_mcp_read_allowed(kind, name, params):
            emit({'event':'mcp_side_effect_denied','name':name});raise PermissionError('controlled first turn: MCP side effects prohibited')
        emit({'event':'mcp_request','method':kind,'name':name})
    else:
        # WaveSpeed host/path/method/body misses must not fall through as a generic origin hole,
        # and must never resolve DNS or open a socket.
        if info.get('hostname')=='api.wavespeed.ai' or (isinstance(reason,str) and (reason.startswith('url:') or reason in {'method_path','inputs_plural_not_official','missing_body','json_and_data','json_not_object','data_not_bytes','data_not_json','data_json_not_object','get_has_body','input_not_object','model_id_invalid'} or reason.startswith('unexpected_keys') or reason.startswith('model_id') or reason.startswith('input_') or reason.startswith('get_') or reason.startswith('json_') or reason.startswith('data_'))):
            deny_record(_dh,_dp,'http_wavespeed:'+reason);raise PermissionError('controlled wavespeed purpose not allowed')
        deny_record(_dh,_dp,'http_origin');raise PermissionError('controlled HTTP origin not allowed')
    if allowed:
        price_scope,price_token=_g.begin_price_request(price_ips)
    try:
        response=await _original_request(self,method,url,**kwargs)
    finally:
        if price_scope is not None:_g.end_price_request(price_scope,price_token)
    if record:
        # Read cached response bytes without changing actual sender/status handling.
        raw_response=await response.read()
        result={'event':'model_http_response','request_id':record['request_id'],'status':response.status,'response_bytes':len(raw_response)}
        try:
            doc=json.loads(raw_response)
            result['usage']=doc.get('usage');result['provider_error_type']=(doc.get('error') or {}).get('type') if isinstance(doc.get('error'),dict) else None
            result['finish_reasons']=[c.get('finish_reason') for c in doc.get('choices',[])]
        except (ValueError,TypeError):result['valid_json']=False
        emit(result)
    return response
aiohttp.ClientSession._request=controlled_request

def attest_and_register():
    try:
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            found=None
            for name,m in list(sys.modules.items()):
                filename=getattr(m,'__file__',None)
                if filename and Path(filename).resolve()==PLUGIN/'__init__.py' and hasattr(m,'comfyart_index'):
                    found=(name,m);break
            if not found:time.sleep(.1);continue
            name,m=found
            a=importlib.import_module(name+'.bot.llm_scope_activation');g=importlib.import_module(name+'.bot.llm_usd_gate');v=importlib.import_module(name+'.bot.llm_activation_manifest')
            admin=importlib.import_module(name+'.api.provider_admin')
            if not getattr(admin.install,'done',False):time.sleep(.1);continue
            if a._LOADED_SOURCE_HASH!=SOURCE:raise RuntimeError('source snapshot mismatch')
            runtime=a.runtime_identity(str(AUTH),os.environ['COMFYART_RUNTIME_ID'])
            complete=ROOT/'first-registration-completed.json'
            if not complete.exists():raise RuntimeError('existing first-registration receipt required; deployment cannot initialize authority')
            binding=a.active_binding(runtime,route={'model':'deepseek-flash','adapter':'deepseek_official','passthrough':False},url=URL)
            result={'pid':os.getpid(),'source_sha256':a._LOADED_SOURCE_HASH,'runtime_id':runtime.runtime_id,'runtime_fingerprint':runtime.fingerprint,
                    'authority_home':runtime.home,'ledger_path':str(LEDGER),'activation_enabled':binding is not None,
                    'module_paths':{'plugin':m.__file__,'activation':a.__file__,'provider_admin':admin.__file__,
                        'envelope':importlib.import_module(name+'.bot.llm_input_envelope').__file__},'ledger':g.ledger_state(str(LEDGER)),
                    'reviewed_git_sha':EXPECTED_SHA,'actual_tools_count':len(a.default_tools()),
                    'loaded_policy':{'skill_read_allowed':controlled_mcp_read_allowed('tools/call','skill',{'name':'skill','arguments':{'action':'read','name':'universal-multi-angle-grid'}}),
                        'skill_write_denied':not controlled_mcp_read_allowed('tools/call','skill',{'name':'skill','arguments':{'action':'write','name':'universal-multi-angle-grid'}}),
                        'bootstrap_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
            (ROOT/'controlled-runtime-attestation.json').write_text(json.dumps(result,indent=2))
            print('CONTROLLED_RUNTIME_BOUND',flush=True);return
        raise RuntimeError('application import timeout')
    except Exception as exc:
        (ROOT/'controlled-registration-error.json').write_text(json.dumps({'type':type(exc).__name__,'message':str(exc)}))
        print('CONTROLLED_REGISTRATION_FAILED',type(exc).__name__,flush=True)
threading.Thread(target=attest_and_register,name='explicit-one-time-registration',daemon=True).start()
os.chdir(ROOT/'ComfyUI');sys.path.insert(0,str(ROOT/'ComfyUI'))
sys.argv=[str(ROOT/'ComfyUI'/'main.py'),'--cpu','--listen','127.0.0.1','--port','8931','--disable-auto-launch','--offline','--disable-assets','--disable-product-tips','--disable-all-custom-nodes','--whitelist-custom-nodes','ComfyArt']
runpy.run_path(str(ROOT/'ComfyUI'/'main.py'),run_name='__main__')
