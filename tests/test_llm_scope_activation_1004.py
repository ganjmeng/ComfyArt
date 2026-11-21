"""Explicit temporary activation only; actual installed raw sender, fake socket."""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import pytest

from ComfyArt.api import provider_admin
from ComfyArt.bot import llm_scope_activation as activation, llm_usd_gate as gate, local_llm
from test_llm_activation_manifest_1004 import candidate as old_candidate
from test_llm_input_envelope_1004 import offline, body, FakeSocketSession, DefaultRig
from test_llm_usd_gate import URL, _route


@pytest.fixture
def activated_candidate(old_candidate, tmp_path, monkeypatch):
    c, old = old_candidate
    home = str(tmp_path / "home")
    runtime = activation.runtime_identity(home, "offline-server-A")
    expected = replace(old, policy_hash=activation.profile_hash(), evidence_hash=activation.evidence_hash(),
                       sources=activation.source_evidence(), tool_allowlist=activation.default_tools(),
                       runtime_binding=("approved_runtime_sha256", runtime.fingerprint))
    c.update(policy_hash=expected.policy_hash, evidence_hash=expected.evidence_hash,
             sources=[{"url": u, "sha256": h} for u, h in expected.sources],
             tool_allowlist=list(expected.tool_allowlist), runtime_binding=dict([expected.runtime_binding]))
    monkeypatch.setenv("COMFYART_HOME", home)
    monkeypatch.setenv("COMFYART_RUNTIME_ID", runtime.runtime_id)
    return c, expected, runtime


def activate(fixture):
    c, expected, runtime = fixture
    return activation.activate_scope(c, expected=expected, runtime=runtime)


async def installed_post(session, payload):
    p = local_llm.LocalLlmProvider(base_url=lambda: "https://api.deepseek.com")
    return await provider_admin.installed_llm_http(session, "POST", URL, headers={}, json_body=payload, transport=p._request_json)


async def test_installed_default_image_uses_byte_bound_and_does_not_touch_the_activated_ledger(activated_candidate):
    """No manifest is not a deny for a measurable image. The $2 candidate ledger stays untouched."""
    c, expected, runtime = activated_candidate
    before = Path(expected.canonical_absolute_ledger_path).read_bytes()
    sent = []

    class Done:
        status = 200
        headers = {}
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def text(self):
            return json.dumps({"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]})

    class Session:
        def request(self, method, url, **kwargs):
            sent.append((method, url, kwargs))
            return Done()

    await installed_post(Session(), body())
    assert len(sent) == 1
    payload = sent[0][2]["json"]
    urls = [part["image_url"]["url"] for msg in payload["messages"] if isinstance(msg.get("content"), list)
            for part in msg["content"] if isinstance(part, dict) and part.get("type") == "image_url"]
    assert urls and urls[0].startswith("data:image/png;base64,")
    assert Path(expected.canonical_absolute_ledger_path).read_bytes() == before
    assert not Path(runtime.home, activation._REGISTRY).exists()


async def test_explicit_activation_installed_raw_request_and_idempotent_balance(activated_candidate):
    c, expected, runtime = activated_candidate
    receipt = activate(activated_candidate)
    session = FakeSocketSession(expected.canonical_absolute_ledger_path)
    await installed_post(session, body())
    assert len(session.requests) == 1
    before = gate.ledger_state(expected.canonical_absolute_ledger_path)
    assert activate(activated_candidate) == receipt
    assert gate.ledger_state(expected.canonical_absolute_ledger_path) == before
    assert before["control_state"]["attempts_total"] == 1 and before["accounted_nano"] > 0


@pytest.mark.parametrize("wrong", ["runtime", "route", "model", "unbound_entry"])
async def test_wrong_binding_denies_before_socket(activated_candidate, monkeypatch, wrong):
    c, expected, runtime = activated_candidate
    activate(activated_candidate)
    session = FakeSocketSession(expected.canonical_absolute_ledger_path)
    if wrong == "runtime": monkeypatch.setenv("COMFYART_RUNTIME_ID", "other-server")
    if wrong == "route": provider_admin._llm_lock.set({**_route(), "adapter": "existing"})
    if wrong == "model": provider_admin._llm_lock.set({**_route(), "model": "deepseek-pro"})
    with pytest.raises(gate.LlmBudgetBlocked):
        if wrong == "unbound_entry":
            from test_llm_input_envelope_1004 import through_gate
            await through_gate(expected.canonical_absolute_ledger_path, body(), lambda *a, **k: pytest.fail("no bypass"))
        else:
            await installed_post(session, body())
    assert not session.requests
    assert gate.ledger_state(expected.canonical_absolute_ledger_path)["control_state"]["attempts_total"] == 0


def test_same_authority_cannot_bind_second_ledger_or_alias_home(activated_candidate, tmp_path):
    c, expected, runtime = activated_candidate
    activate(activated_candidate)
    path = str(tmp_path / "second.json")
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=2)
    second = copy.deepcopy(c); second.update(scope_id=scope["scope_id"], canonical_absolute_ledger_path=path)
    other = replace(expected, scope_id=scope["scope_id"], canonical_absolute_ledger_path=path)
    alias = tmp_path / "home-alias"; alias.symlink_to(runtime.home, target_is_directory=True)
    assert activation.runtime_identity(str(alias), runtime.runtime_id) == runtime
    with pytest.raises(gate.LlmBudgetBlocked, match="activation_authority_conflict"):
        activation.activate_scope(second, expected=other, runtime=runtime)
    assert gate.ledger_state(path)["control_state"]["attempts_total"] == 0
    assert "runtime_activation" not in json.loads(Path(path).read_text())

# Child interpreters load the actual package afresh, never provider credentials.
CHILD = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import conftest
from ComfyArt.bot import llm_scope_activation as a, llm_activation_manifest as m, llm_usd_gate as g
payload=json.loads(sys.argv[2]); c=payload['candidate']; d=payload['expected']
d['sources']=tuple(map(tuple,d['sources'])); d['runtime_binding']=tuple(d['runtime_binding']); d['tool_allowlist']=tuple(d['tool_allowlist'])
e=m.ManifestContext(**d); r=a.runtime_identity(payload['home'],payload['runtime_id'])
if payload.get('ready'): print('READY',flush=True)
stage=payload.get('crash_stage'); nth=payload.get('nth',1); seen=0
if stage:
 def fault(current):
  global seen
  if current==stage:
   seen+=1
   if seen==nth: os._exit(93)
 g._write_fault=fault
try:
 if payload.get('action')=='post':
  import asyncio
  from ComfyArt.api import provider_admin
  from ComfyArt.bot.local_llm import LocalLlmProvider
  from test_llm_input_envelope_1004 import FakeSocketSession,body
  from test_llm_usd_gate import _route,URL
  provider_admin._llm_lock.set(_route())
  p=LocalLlmProvider(base_url=lambda:'https://api.deepseek.com')
  socket=FakeSocketSession(e.canonical_absolute_ledger_path)
  asyncio.run(provider_admin.installed_llm_http(socket,'POST',URL,headers={},json_body=body(),transport=p._request_json))
  result={'fake_posts':len(socket.requests)}
 else:
  result=a.activate_scope(c,expected=e,runtime=r)
 print(json.dumps({'ok':True,'receipt':result,'state':g.ledger_state(e.canonical_absolute_ledger_path)}),flush=True)
except g.LlmBudgetBlocked as ex:
 print(json.dumps({'ok':False,'code':ex.code}),flush=True)
'''


def child_payload(fixture, **extra):
    from dataclasses import asdict
    c, expected, runtime = fixture
    return dict(candidate=c, expected=asdict(expected), home=runtime.home, runtime_id=runtime.runtime_id, **extra)


def spawn_child(payload):
    import subprocess, sys
    return subprocess.Popen([sys.executable, "-c", CHILD, str(Path(__file__).parent), json.dumps(payload)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def finish_child(child, returncode=0):
    stdout, stderr = child.communicate(timeout=25)
    assert child.returncode == returncode, (stdout, stderr)
    return json.loads(stdout.splitlines()[-1]) if returncode == 0 else None


async def test_fresh_interpreter_reopen_preserves_spend_posts_and_unknown(activated_candidate):
    c, expected, runtime = activated_candidate
    activate(activated_candidate)
    session = FakeSocketSession(expected.canonical_absolute_ledger_path, 500)
    with pytest.raises(gate.LlmScopeStopped): await installed_post(session, body())
    before = gate.ledger_state(expected.canonical_absolute_ledger_path)
    result = finish_child(spawn_child(child_payload(activated_candidate)))
    assert result["ok"] and result["state"] == before
    assert before["control_state"]["attempts_total"] == 1 and before["control_state"]["circuit_open"]
    with pytest.raises(gate.LlmBudgetBlocked): await installed_post(session, body())
    assert len(session.requests) == 1


def test_two_children_same_authority_only_one_ledger_can_claim(activated_candidate, tmp_path):
    c, expected, runtime = activated_candidate
    path = str(tmp_path / "other-scope.json")
    scope = gate.open_authorized_scope(path, gate.TWO_DOLLAR_CEILING_NANO, max_posts=2)
    c2=copy.deepcopy(c); c2.update(scope_id=scope["scope_id"],canonical_absolute_ledger_path=path)
    other=(c2,replace(expected,scope_id=scope["scope_id"],canonical_absolute_ledger_path=path),runtime)
    with activation._registry_lock(runtime.home):
        children=[spawn_child(child_payload(f,ready=True)) for f in (activated_candidate,other)]
        for child in children: assert child.stdout.readline().strip() == "READY"
    results=[finish_child(child) for child in children]
    assert sum(r["ok"] for r in results) == 1
    assert [r["code"] for r in results if not r["ok"]] == ["activation_authority_conflict"]
    assert sum("runtime_activation" in json.loads(Path(p).read_text()) for p in (path,expected.canonical_absolute_ledger_path)) == 1


@pytest.mark.parametrize("stage,nth", [("registry_after_dir_fsync",1), ("after_dir_fsync",1),
    ("marker_after_dir_fsync",1), ("registry_before_replace",2)])
async def test_abrupt_process_exit_pending_claim_blocks_then_explicit_identical_recovery(activated_candidate,stage,nth):
    c, expected, runtime=activated_candidate
    before=gate.ledger_state(expected.canonical_absolute_ledger_path)
    finish_child(spawn_child(child_payload(activated_candidate,crash_stage=stage,nth=nth)),93)
    session=FakeSocketSession(expected.canonical_absolute_ledger_path)
    with pytest.raises(gate.LlmBudgetBlocked): await installed_post(session,body())
    assert not session.requests and gate.ledger_state(expected.canonical_absolute_ledger_path)==before
    assert finish_child(spawn_child(child_payload(activated_candidate)))["ok"]
    assert gate.ledger_state(expected.canonical_absolute_ledger_path)==before
    await installed_post(session,body())
    assert len(session.requests)==1


async def test_active_publication_after_replace_has_durable_ledger_not_new_funds(activated_candidate):
    c,e,r=activated_candidate
    before=gate.ledger_state(e.canonical_absolute_ledger_path)
    finish_child(spawn_child(child_payload(activated_candidate,crash_stage="registry_after_replace",nth=2)),93)
    # Process crash is not power-loss simulation: published active is visible.
    # Either post-power-loss directory entry (pending/active) is safe, because
    # pending claim and ledger+marker were already fsynced before publication.
    assert gate._read_marker(e.canonical_absolute_ledger_path)["runtime_activation"] == json.loads(Path(e.canonical_absolute_ledger_path).read_text())["runtime_activation"]
    assert activate(activated_candidate)["ok"] and gate.ledger_state(e.canonical_absolute_ledger_path)==before


@pytest.mark.parametrize("change", ["home", "runtime", "source", "policy", "expiry", "missing_registry", "empty_registry"])
async def test_stale_or_remapped_grant_never_restarts_authority(activated_candidate,tmp_path,monkeypatch,change):
    c,e,r=activated_candidate
    if change in ("home","runtime"):
        other=activation.runtime_identity(str(tmp_path/"remapped") if change=="home" else r.home,
                                          "different-server" if change=="runtime" else r.runtime_id)
        with pytest.raises(gate.LlmBudgetBlocked): activation.activate_scope(c,expected=e,runtime=other)
        assert "runtime_activation" not in json.loads(Path(e.canonical_absolute_ledger_path).read_text())
        return
    if change=="expiry": c["expires_at"]=2000000000
    activate(activated_candidate)
    registry=Path(r.home,activation._REGISTRY)
    if change=="source": monkeypatch.setattr(activation,"_source_hash",lambda:"0"*64)
    elif change=="policy": monkeypatch.setattr(activation,"profile_hash",lambda:"0"*64)
    elif change=="expiry": monkeypatch.setattr("ComfyArt.bot.llm_activation_manifest.time.time",lambda:2000000001)
    elif change=="missing_registry": registry.unlink()
    elif change=="empty_registry": registry.write_text("")
    session=FakeSocketSession(e.canonical_absolute_ledger_path)
    with pytest.raises(gate.LlmBudgetBlocked): await installed_post(session,body())
    assert not session.requests and gate.ledger_state(e.canonical_absolute_ledger_path)["control_state"]["attempts_total"]==0


@pytest.mark.parametrize("purpose,method,url,payload", [
 (None,"POST","https://api.deepseek.com/models",{}),
 (None,"POST","http://fake.invalid/mcp",{"jsonrpc":"2.0","id":"x","method":"tools/list","params":{}}),
 ("catalog","POST","https://api.deepseek.com/models",None),
 ("catalog","GET","https://not-official.invalid/models",None),
 ("mcp_list","POST",URL,{"jsonrpc":"2.0","id":"x","method":"tools/list","params":{}}),
 ("mcp_list","POST","http://fake.invalid/mcp",{"model":"deepseek-flash","messages":[]}),
])
async def test_purpose_schema_or_origin_spoof_does_not_bypass(activated_candidate,purpose,method,url,payload):
    import contextlib
    c,e,r=activated_candidate; activate(activated_candidate)
    p=local_llm.LocalLlmProvider(base_url=lambda:"https://api.deepseek.com")
    session=FakeSocketSession(e.canonical_absolute_ledger_path)
    context=activation.auxiliary_request(purpose,method,url,payload) if purpose else contextlib.nullcontext()
    with context, pytest.raises(gate.LlmBudgetBlocked):
        await provider_admin.installed_llm_http(session,method,url,headers={},json_body=payload,transport=p._request_json)
    assert not session.requests


@pytest.mark.parametrize("thinking",[False,True])
async def test_actual_default_builder_catalog_and_mcp_helpers_through_only_fake_socket(activated_candidate,tmp_path,monkeypatch,thinking):
    import aiohttp
    from test_llm_input_envelope_1004 import response
    c,e,r=activated_candidate
    rig=DefaultRig(monkeypatch,tmp_path,thinking)
    # Restore REAL MCP helper; no fake discovery/call entrypoint survives here.
    monkeypatch.setattr(rig.p,"_mcp_call_tool",local_llm.LocalLlmProvider._mcp_call_tool.__get__(rig.p))
    monkeypatch.setattr(rig.p,"_mcp_headers",lambda:{})
    raw=local_llm.LocalLlmProvider._request_json.__get__(rig.p)
    c=copy.deepcopy(c); scope=gate.ledger_state(rig.path)
    c.update(scope_id=scope["scope_id"],canonical_absolute_ledger_path=rig.path)
    c["scope_limits"]["max_posts"]=6
    e=replace(e,scope_id=scope["scope_id"],canonical_absolute_ledger_path=rig.path,max_posts=6)
    activation.activate_scope(c,expected=e,runtime=r)
    socket=FakeSocketSession(rig.path); aux=[]; wire=[]
    class Reply:
        status=200; headers={}
        def __init__(self,value): self.value=value
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def text(self): return json.dumps(self.value)
    def fake_socket(session,method,url,**kwargs):
        assert kwargs["allow_redirects"] is False
        if url==URL:
            socket.request(method,url,**kwargs)
            wire.append(json.loads(kwargs["data"]))
            result=response()
            if thinking and len(wire)==1:
                result["choices"][0]={"finish_reason":"tool_calls","message":{"role":"assistant","content":"","reasoning_content":"",
                    "tool_calls":[{"id":"default-memory","type":"function","function":{"name":"memory","arguments":json.dumps({"action":"add","text":"warm colors","category":"taste"})}}]}}
            return Reply(result)
        aux.append((method,url,kwargs.get("json")))
        if url=="https://api.deepseek.com/models": return Reply({"data":[{"id":"deepseek-flash"}]})
        assert url=="http://fake.invalid/mcp" and method=="POST"
        rpc=kwargs["json"]
        if rpc["method"]=="tools/list": return Reply({"result":{"tools":rig.catalog}})
        assert rpc["method"]=="tools/call" and rpc["params"]["name"]=="memory"
        return Reply({"result":{"content":[{"type":"text","text":json.dumps({"memory_ids":["fixture-memory"],"added":"warm colors"})}]}})
    monkeypatch.setattr(aiohttp.ClientSession,"request",fake_socket)
    async def installed(session,method,url,*,headers,json_body=None,timeout=120):
        return await provider_admin.installed_llm_http(session,method,url,headers=headers,json_body=json_body,timeout=timeout,transport=raw)
    monkeypatch.setattr(rig.p,"_request_json",installed)
    async with aiohttp.ClientSession() as session:
        assert (await rig.p._request_auxiliary_json("catalog",session,"GET","https://api.deepseek.com/models",headers={}))["data"] == [{"id":"deepseek-flash"}]
    assert await rig.p.list_models()==["deepseek-flash"]
    result=await rig.run()
    assert not result.error
    assert len(wire)==(2 if thinking else 1)
    assert any(m=="GET" for m,u,b in aux)
    assert any((b or {}).get("method")=="tools/list" for m,u,b in aux)
    assert sum((b or {}).get("method")=="tools/call" for m,u,b in aux)==int(thinking)
    for payload in wire:
        assert {t["function"]["name"] for t in payload["tools"]}==set(activation.default_tools())
        assert {"ask_user","get_canvas","memory","generate_image"} <= set(activation.default_tools())
        assert payload["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    if thinking: assert wire[1]["thinking"]=={"type":"enabled"} and wire[1]["max_tokens"]==65536
    state=gate.ledger_state(rig.path)
    assert state["control_state"]["attempts_total"]==len(wire) and state["inflight"]==0


async def test_subprocess_runtime_uses_committed_activation_without_reactivation_and_count_reset(activated_candidate):
    c,e,r=activated_candidate
    activate(activated_candidate)
    socket=FakeSocketSession(e.canonical_absolute_ledger_path)
    await installed_post(socket,body())
    before=gate.ledger_state(e.canonical_absolute_ledger_path)
    assert finish_child(spawn_child(child_payload(activated_candidate)))["state"]==before
    result=finish_child(spawn_child(child_payload(activated_candidate,action="post")))
    assert result["ok"] and result["receipt"]["fake_posts"]==1
    assert result["state"]["control_state"]["attempts_total"]==2
    assert result["state"]["accounted_nano"]==before["accounted_nano"]*2
    stopped=finish_child(spawn_child(child_payload(activated_candidate,action="post")))
    assert not stopped["ok"] and stopped["code"]=="scope_posts_exhausted"
    assert gate.ledger_state(e.canonical_absolute_ledger_path)==result["state"]


def test_claimed_review_sha_must_be_actual_clean_runtime_not_manifest_self_assertion(activated_candidate):
    c,e,r=activated_candidate
    c=copy.deepcopy(c); c["runtime_binding"]={"reviewed_sha":"0"*40}
    e=replace(e,runtime_binding=("reviewed_sha","0"*40))
    with pytest.raises(gate.LlmBudgetBlocked,match="activation_runtime_mismatch"):
        activation.activate_scope(c,expected=e,runtime=r)
    assert not Path(r.home,activation._REGISTRY).exists()


async def test_actual_summary_uses_same_active_scope_and_physical_post_limit(activated_candidate,monkeypatch):
    c,e,r=activated_candidate; activate(activated_candidate)
    p=local_llm.LocalLlmProvider(base_url=lambda:"https://api.deepseek.com")
    monkeypatch.setattr(p,"_api_headers",lambda:{})
    raw=p._request_json
    async def installed(session,method,url,*,headers,json_body=None,timeout=120):
        return await provider_admin.installed_llm_http(session,method,url,headers=headers,json_body=json_body,timeout=timeout,transport=raw)
    monkeypatch.setattr(p,"_request_json",installed)
    socket=FakeSocketSession(e.canonical_absolute_ledger_path)
    await installed_post(socket,body())
    assert await p._summarize_llm(socket,"https://api.deepseek.com","deepseek-flash","","Synthetic completed turns") == "Synthetic done"
    assert len(socket.requests)==2
    with pytest.raises(gate.LlmBudgetBlocked,match="scope_posts_exhausted"):
        await p._summarize_llm(socket,"https://api.deepseek.com","deepseek-flash","","Synthetic later turns")
    assert len(socket.requests)==2 and gate.ledger_state(e.canonical_absolute_ledger_path)["control_state"]["attempts_total"]==2
