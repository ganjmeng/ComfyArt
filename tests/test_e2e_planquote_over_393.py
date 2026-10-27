"""#393 (from tester): plan quote SUCCEEDS (_quote_steps mocked quiet), then one call exceeds the run quote → dedicated card."""
import pytest
from ComfyArt.bot.local_llm import OVER_QUOTE
from ComfyArt.bot.plan_quote import Line, Quote, canon_key, CANCEL_TEXT
from tests.test_agent_budget_391 import calls, reply, store  # noqa: F401
from tests.test_e2e_over_quote_393 import Run, click, gen, bundle, ui  # noqa: F401


def quiet(n):
    ls = [Line(f"s{i}", "$0.01", 0.01, False, False, canon_key("generate_image", gen(i)[1], "m")) for i in range(n)]
    return Quote(lines=ls, total=0.01 * n, n=n, ask=False, lang="zh", prompt="x", total_label="总价",
                 total_text="$0.0", keys=[l.key for l in ls], cancel_text=CANCEL_TEXT["zh"])


def setup(monkeypatch, run, n):
    """Mock `_quote_steps` so a quiet plan quote succeeds; asserts live inside the mock so dropping
    the outer `assert seen` / kind checks still fails if the mock is unused or fed the wrong steps."""
    seen = []

    async def q(steps, lang):
        assert len(steps) == n, steps
        assert all(s.get("tool") == "generate_image" for s in steps), steps
        seen.append(steps)
        return quiet(n)
    monkeypatch.setattr(run.r.p, "_quote_steps", q)
    return seen


async def test_plan_ok_then_over_quote_decline(monkeypatch, bot_client, store, ui):
    run = Run(monkeypatch, bot_client, store, prices=[0.3, 9.0],
              script=lambda m, n: calls(gen(0), gen(1)) if n == 0 else reply("好"))
    seen = setup(monkeypatch, run, 2)
    await run.start()
    b = await run.pending(1)
    assert seen, "plan quote must have run (_quote_steps mock)"
    assert b["kind"] == OVER_QUOTE["kind"] and "questions" not in b and b.get("credits") == 900
    assert len(run.r.paid_mcp()) == 1
    llm = run.r.n
    await click(ui, b, run.chat, "先到这里")
    blocks, stops = await run.done()
    assert stops[-1]["copy"]["key"] == "user_stop:quote_declined"
    assert len(run.asks) == 1 and len(run.r.paid_mcp()) == 1 and run.r.n == llm
    assert "已保留之前生成的 1 张" in stops[-1]["copy"]["zh"]["body"]


async def test_plan_ok_then_over_quote_confirm_once_then_requote(monkeypatch, bot_client, store, ui):
    run = Run(monkeypatch, bot_client, store, prices=[0.3, 9.0, 9.0],
              script=lambda m, n: calls(gen(0), gen(1), gen(2)) if n == 0 else reply("好"))
    seen = setup(monkeypatch, run, 3)
    await run.start()
    b1 = await run.pending(1)
    assert seen, "plan quote must have run (_quote_steps mock)"
    assert b1["kind"] == OVER_QUOTE["kind"] and b1.get("credits") == 900
    await click(ui, b1, run.chat, "确认")
    b2 = await run.pending(2)
    assert len(run.r.paid_mcp()) == 2, "确认 pays exactly the confirmed call"
    await click(ui, b2, run.chat, "先到这里")
    blocks, stops = await run.done()
    assert len(run.asks) == 2 and len(run.r.paid_mcp()) == 2
    assert stops[-1]["copy"]["key"] == "user_stop:quote_declined"
    assert "已保留之前生成的 2 张" in stops[-1]["copy"]["zh"]["body"]
