"""#381: server-side memory store — one interface, rev-checked writes under a lock, owner_id/workspace_id defaults."""
from __future__ import annotations

import asyncio
import json


async def _get(c):
    res = await c.get("/comfyart/memory")
    assert res.status == 200
    return await res.json()


async def _post(c, state, base):
    res = await c.post("/comfyart/memory", json={"memory": state["memory"], "log": state.get("log", []), "meta": state.get("meta", {}), "base_rev": base})
    return res.status, await res.json()


async def test_never_written_reads_null_so_client_may_fall_back(bot_client, fresh_user_dir):
    assert await _get(bot_client) == {"memory": None, "log": None, "meta": None, "rev": 0}


async def test_write_stamps_owner_and_workspace_defaults_and_bumps_rev(bot_client, fresh_user_dir):
    status, st = await _post(bot_client, {"memory": [{"id": "a", "text": "x", "time": 1}]}, 0)
    assert status == 200 and st["rev"] == 1
    assert st["memory"] == [{"id": "a", "text": "x", "time": 1, "owner_id": "local", "workspace_id": "local"}]
    on_disk = json.loads((fresh_user_dir / "user/default/comfyart/memory.json").read_text())
    assert on_disk[0]["owner_id"] == "local" and on_disk[0]["workspace_id"] == "local"
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
