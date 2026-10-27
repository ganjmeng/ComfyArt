"""#381: server-side memory store — one interface, rev-checked writes under a lock, owner_id/workspace_id defaults."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path


async def _get(c):
    res = await c.get("/comfyart/memory")
    assert res.status == 200
    return await res.json()


async def _post(c, state, base):
    res = await c.post("/comfyart/memory", json={"memory": state["memory"], "log": state.get("log", []), "meta": state.get("meta", {}), "base_rev": base})
    return res.status, await res.json()


async def test_never_written_is_a_real_empty_store(bot_client, fresh_user_dir):
    # the server is the only truth: no null "fall back to your local copy" signal any more
    assert await _get(bot_client) == {"memory": [], "log": [], "meta": {}, "rev": 0}


async def test_write_stamps_owner_and_workspace_defaults_and_bumps_rev(bot_client, fresh_user_dir):
    status, st = await _post(bot_client, {"memory": [{"id": "a", "text": "x", "time": 1}]}, 0)
    assert status == 200 and st["rev"] == 1
    t = st["memory"][0].pop("time")
    assert st["memory"] == [{"id": "a", "text": "x", "owner_id": "local", "workspace_id": "local"}] and t > 1_700_000_000_000  # server time, not the client's 1
    on_disk = json.loads((fresh_user_dir / "user/default/comfyart/memory-store.json").read_text())
    assert on_disk["rev"] == 1 and on_disk["memory"][0]["owner_id"] == "local" and on_disk["memory"][0]["workspace_id"] == "local"
    # explicit values are kept (not overwritten by the default)
    _, st = await _post(bot_client, {"memory": [{"id": "b", "text": "y", "time": 1, "owner_id": "u7", "workspace_id": "p3"}]}, 1)
    assert st["memory"][0]["owner_id"] == "u7" and st["memory"][0]["workspace_id"] == "p3"


async def test_empty_list_is_a_real_zero(bot_client, fresh_user_dir):
    await _post(bot_client, {"memory": [{"id": "a", "text": "x", "time": 1}]}, 0)
    status, st = await _post(bot_client, {"memory": []}, 1)
    assert status == 200 and (await _get(bot_client))["memory"] == []


async def test_stale_write_is_rejected_with_current_state(bot_client, fresh_user_dir):
    await _post(bot_client, {"memory": [{"id": "a", "text": "x", "time": 1}]}, 0)
    status, body = await _post(bot_client, {"memory": []}, 0)  # based on rev 0, store is at rev 1
    assert status == 409 and body["state"]["rev"] == 1 and len(body["state"]["memory"]) == 1
    assert len((await _get(bot_client))["memory"]) == 1  # nothing was overwritten


async def test_concurrent_read_modify_write_loses_nothing(bot_client, fresh_user_dir):
    """40 writers (agent learning + UI edits) each add one memory with read → modify → rev-checked write → retry on 409."""
    async def add(i):
        while True:
            st = await _get(bot_client)
            status, _ = await _post(bot_client, {"memory": [*(st["memory"] or []), {"id": f"m{i}", "text": f"t{i}", "time": i}], "log": [], "meta": st["meta"] or {}}, st["rev"])
            if status == 200:
                return
            assert status == 409
    await asyncio.gather(*(add(i) for i in range(40)))
    st = await _get(bot_client)
    assert sorted(m["id"] for m in st["memory"]) == sorted(f"m{i}" for i in range(40)) and st["rev"] == 40


async def test_bad_body_and_unknown_user(bot_client, fresh_user_dir):
    assert (await bot_client.post("/comfyart/memory", json={"memory": "x", "base_rev": 0})).status == 400
    assert (await bot_client.get("/comfyart/memory", headers={"Comfy-User": "mallory"})).status == 403


def _store_dir(fresh_user_dir):
    return fresh_user_dir / "user/default/comfyart"


async def test_single_file_holds_memory_log_meta_rev_together(bot_client, fresh_user_dir):
    await _post(bot_client, {"memory": [{"id": "a", "text": "x", "time": 1}], "log": [{"id": "l1"}], "meta": {"demoCleanup381": True}}, 0)
    d = _store_dir(fresh_user_dir)
    on_disk = json.loads((d / "memory-store.json").read_text())
    assert on_disk["rev"] == 1 and on_disk["log"] == [{"id": "l1"}] and on_disk["meta"] == {"demoCleanup381": True}
    assert not list(d.glob("*.tmp"))  # temp file renamed away, nothing left behind


async def test_crash_mid_write_keeps_previous_state(bot_client, fresh_user_dir, monkeypatch):
    """EL MUST 4: a crash after the bytes are written but before the commit must not tear memory/log/meta/rev."""
    from ComfyArt.api import memory as mem
    await _post(bot_client, {"memory": [{"id": "a", "text": "x", "time": 1}], "log": [{"id": "l1"}]}, 0)
    before = (_store_dir(fresh_user_dir) / "memory-store.json").read_text()

    def boom(_fd):
        raise OSError("disk died")
    monkeypatch.setattr(mem.os, "fsync", boom)
    res = await bot_client.post("/comfyart/memory", json={"memory": [], "log": [], "meta": {}, "base_rev": 1})
    assert res.status == 500
    monkeypatch.undo()
    assert (_store_dir(fresh_user_dir) / "memory-store.json").read_text() == before
    st = await _get(bot_client)
    assert st["rev"] == 1 and [m["id"] for m in st["memory"]] == ["a"] and st["log"] == [{"id": "l1"}]
    assert not list(_store_dir(fresh_user_dir).glob("*.tmp"))


async def test_temp_file_name_is_random(bot_client, fresh_user_dir, monkeypatch):
    from ComfyArt.api import memory as mem
    seen = []
    real = mem.os.replace
    monkeypatch.setattr(mem.os, "replace", lambda a, b: (seen.append(a), real(a, b)))
    await _post(bot_client, {"memory": []}, 0)
    await _post(bot_client, {"memory": []}, 1)
    assert len(seen) == 2 and seen[0] != seen[1] and all(s.endswith(".tmp") for s in seen)


async def test_op_id_retry_is_applied_once(bot_client, fresh_user_dir):
    """EL MUST 1/3: a write resent after a network error (same op_id) must not apply twice or 409."""
    body = {"memory": [{"id": "a", "text": "x", "time": 1}], "log": [], "meta": {}, "base_rev": 0, "op_id": "op-1"}
    first = await bot_client.post("/comfyart/memory", json=body)
    again = await bot_client.post("/comfyart/memory", json=body)
    assert first.status == 200 and again.status == 200
    st = await again.json()
    assert st["rev"] == 1 and st.get("replayed") is True and len(st["memory"]) == 1
    assert (await _get(bot_client))["rev"] == 1


async def test_meta_schema_is_validated(bot_client, fresh_user_dir):
    async def post_meta(meta):
        return (await bot_client.post("/comfyart/memory", json={"memory": [], "log": [], "meta": meta, "base_rev": 0})).status
    assert await post_meta({"evil": 1}) == 400
    assert await post_meta({"demoCleanup381": "yes"}) == 400
    assert (await _get(bot_client))["rev"] == 0
    assert await post_meta({"demoCleanup381": True, "rev": 99}) == 200  # echoed rev is ignored, server owns it
    st = await _get(bot_client)
    assert st["rev"] == 1 and st["meta"] == {"demoCleanup381": True}


async def test_legacy_three_files_are_read_until_first_write(bot_client, fresh_user_dir):
    d = _store_dir(fresh_user_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / "memory.json").write_text(json.dumps([{"id": "old", "text": "legacy", "time": 1}]))
    (d / "memory-meta.json").write_text(json.dumps({"rev": 3, "demoCleanup381": True}))
    st = await _get(bot_client)
    assert [m["id"] for m in st["memory"]] == ["old"] and st["rev"] == 3 and st["meta"] == {"demoCleanup381": True}
    status, st = await _post(bot_client, {"memory": st["memory"], "meta": st["meta"]}, 3)
    assert status == 200 and st["rev"] == 4 and (d / "memory-store.json").exists()
    assert json.loads((d / "memory.json").read_text())[0]["id"] == "old"  # legacy file untouched


def test_policy_is_shared_with_client():
    from ComfyArt.api import memory as mem
    import pathlib
    policy = json.loads((pathlib.Path(mem.__file__).parent / "memory_policy.json").read_text())
    assert mem.OWNER_DEFAULT == policy["owner_default"] == "local" and policy["max_retries"] == 5
    src = (pathlib.Path(mem.__file__).parent.parent / "src/memoryStore.ts").read_text()
    assert "memory_policy.json" in src
    assert "TODO(#381)" in (pathlib.Path(mem.__file__)).read_text() and "lease" in pathlib.Path(mem.__file__).read_text()


async def test_record_time_is_server_authoritative(bot_client, fresh_user_dir, monkeypatch):
    """#381 EL: create/update get the server clock (ms); any client-sent time is ignored; unchanged records keep theirs."""
    from ComfyArt.api import memory as mem
    clock = [1_793_096_400.0]
    monkeypatch.setattr(mem.time, "time", lambda: clock[0])
    _, st = await _post(bot_client, {"memory": [{"id": "a", "text": "x", "time": 5}, {"id": "b", "text": "y", "time": 9_999_999_999_999}]}, 0)  # past and future client times
    assert [m["time"] for m in st["memory"]] == [1_793_096_400_000] * 2  # create: server time, client 5 dropped
    clock[0] += 60
    _, st = await _post(bot_client, {"memory": [{"id": "a", "text": "x2", "time": 9_999_999_999_999}, {"id": "b", "text": "y", "time": 1}]}, 1)
    assert [m["time"] for m in st["memory"]] == [1_793_096_460_000, 1_793_096_400_000]  # update → now; unchanged keeps stored, ignores client
    on_disk = json.loads((_store_dir(fresh_user_dir) / "memory-store.json").read_text())
    assert [m["time"] for m in on_disk["memory"]] == [1_793_096_460_000, 1_793_096_400_000]
    assert [m["time"] for m in (await _get(bot_client))["memory"]] == [1_793_096_460_000, 1_793_096_400_000]


async def test_legacy_record_without_time_stays_untimed_until_edited(bot_client, fresh_user_dir):
    d = _store_dir(fresh_user_dir); d.mkdir(parents=True, exist_ok=True)
    (d / "memory-store.json").write_text(json.dumps({"memory": [{"id": "old", "text": "z"}], "log": [], "meta": {}, "rev": 3, "ops": []}))
    _, st = await _post(bot_client, {"memory": [{"id": "old", "text": "z", "time": 42}]}, 3)
    assert "time" not in st["memory"][0]  # client cannot backfill a time
    _, st = await _post(bot_client, {"memory": [{"id": "old", "text": "z!"}]}, 4)
    assert st["memory"][0]["time"] > 1_700_000_000_000


def test_client_never_sends_record_time():
    src = (Path(__file__).resolve().parents[1] / "src/memory.ts").read_text()
    # Date.now() only stamps log entries; memory records get their time from the server
    assert [l.strip().split(' =')[0] for l in src.splitlines() if "Date.now()" in l and "memoryToastAtom" not in l] == ["const entry"]
