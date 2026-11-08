"""Click through the provider settings page against the isolated local API.

This is the settings panel plus the real /comfyart/provider-admin routes.
It is not the full ComfyUI app, and it never calls a generation vendor.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

KEYED = "http://127.0.0.1:8765"
NOKEY = "http://127.0.0.1:8766"
OUT = Path("/opt/cursor/artifacts")
REPORT = Path("/agent/repos/ComfyArt/docs/qa/provider-settings-walk.md")
CHROME = "/opt/google/chrome/chrome"


def fetch_state(base: str) -> dict:
    req = urllib.request.Request(base + "/comfyart/provider-admin", headers={"comfy-user": "default"})
    with urllib.request.urlopen(req, timeout=5) as res:
        return json.loads(res.read().decode())


def tool(state: dict, tool_id: str) -> dict:
    return next(row for row in state["tools"] if row["id"] == tool_id)


def store_path(base: str) -> Path:
    with urllib.request.urlopen(base + "/health", timeout=5) as res:
        return Path(json.loads(res.read().decode())["store"])


class Log:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, name: str, steps: str, expected: str, observed: str, ok: bool, shot: str = "") -> None:
        self.rows.append({
            "name": name, "steps": steps, "expected": expected,
            "observed": observed, "ok": ok, "shot": shot,
        })
        print(("PASS " if ok else "FAIL ") + name + " :: " + observed[:240])


def overflow(page) -> dict:
    return page.evaluate(
        """() => {
          const root = document.querySelector('[data-testid=provider-admin]') || document.body
          const bad = []
          root.querySelectorAll('*').forEach((el) => {
            if (!el.clientWidth) return
            const style = getComputedStyle(el)
            if (style.overflowX === 'auto' || style.overflowX === 'scroll') return
            if (el.scrollWidth > el.clientWidth + 2) bad.push(String(el.className || el.tagName).slice(0, 80))
          })
          const doc = document.documentElement
          return { bad: bad.slice(0, 12), page: doc.scrollWidth > doc.clientWidth + 2 }
        }"""
    )


def reveal(page) -> None:
    editor = page.locator("[data-testid=provider-editor], [data-testid=provider-llm]")
    if editor.count():
        editor.first.evaluate("el => { el.scrollTop = el.scrollHeight }")


def shot(page, name: str) -> str:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def open_settings(page) -> None:
    page.get_by_test_id("settings-providers").click()
    page.get_by_test_id("provider-admin").wait_for()


def pick(page, tool_id: str) -> None:
    page.get_by_test_id(f"provider-tool-{tool_id}").click()
    page.get_by_role("heading", level=3).wait_for()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log = Log()
    console: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda err: console.append("pageerror: " + str(err)))
        page.on("console", lambda msg: console.append(msg.text) if msg.type == "error" else None)
        page.goto(KEYED, wait_until="networkidle")
        home = shot(page, "walk-home")
        open_settings(page)
        title = page.get_by_role("heading", name="供应商").inner_text()
        banner = page.locator("#mock-banner").inner_text()
        first = shot(page, "walk-enter")
        log.add(
            "进入设置",
            "打开本地页面，点击「供应商」。",
            "出现供应商对话框，横幅标明本地设置接口。",
            f"标题「{title}」；横幅「{banner}」。入口见 {home}。",
            title == "供应商" and "本地设置接口" in banner,
            first,
        )

        page.get_by_test_id("provider-group-video").click()
        video_on = page.get_by_test_id("provider-tool-generate_video").is_visible()
        image_off = page.get_by_test_id("provider-tool-generate_image").count() == 0
        page.get_by_test_id("provider-group-all").click()
        page.get_by_test_id("provider-search").fill("改图")
        found = page.get_by_test_id("provider-tool-edit_image").is_visible()
        missed = page.get_by_test_id("provider-tool-generate_image").count() == 0
        log.add(
            "分类和搜索",
            "点「视频」，再回到全部并搜索「改图」。",
            "视频分类只有视频工具；搜索只留下改图。",
            f"视频分类含生成视频={video_on} 且不含生成图片={image_off}；搜索只见改图={found and missed}。",
            video_on and image_off and found and missed,
            shot(page, "walk-search"),
        )

        page.get_by_test_id("provider-search").fill("")
        pick(page, "edit_image")
        page.locator("[data-testid=provider-primary] button", has_text="Replicate · Flare").click()
        page.locator("[data-testid=provider-backup] button", has_text="WaveSpeed").click()
        switcher = page.get_by_test_id("provider-fallback")
        if switcher.get_attribute("aria-checked") != "true":
            switcher.click()
        impact = page.get_by_test_id("provider-impact").inner_text()
        page.get_by_test_id("provider-save").click()
        page.get_by_test_id("provider-blocked").wait_for()
        reveal(page)
        blocked = page.get_by_test_id("provider-blocked").inner_text()
        live = page.get_by_test_id("provider-effective").inner_text()
        state = fetch_state(KEYED)
        edit = tool(state, "edit_image")
        gen = tool(state, "generate_image")
        coexist = (
            edit["effective"]["provider"] == "replicate"
            and edit["effective"]["model"].endswith("flare")
            and edit["effective"]["fallback"] is True
            and (edit["effective"]["backup"] or {}).get("provider") == "wavespeed"
            and gen["effective"]["source"] == "default"
        )
        log.add(
            "主备共存",
            "改图选 Replicate Flare、备选 WaveSpeed、打开兜底并保存。生成图片不改。",
            "改图生效为 Replicate，生成图片仍是默认。价格未知会拦住新任务。",
            f"页面「{live}」；拦截「{blocked[:42]}」；影响「{impact[:42]}」；接口改图={edit['effective']['provider']} 生成图片={gen['effective']['source']}。",
            coexist and "价格未知" in blocked and "没受理时会试备选" in live,
            shot(page, "walk-coexist"),
        )

        pick(page, "to_gif")
        before_live = page.get_by_test_id("provider-effective").inner_text()
        page.locator("[data-testid=provider-primary] button", has_text="Replicate · Flare").click()
        backup = page.locator("[data-testid=provider-backup] button", has_text="WaveSpeed")
        reason = backup.inner_text()
        disabled = backup.is_disabled()
        flare = page.locator("[data-testid=provider-primary] button", has_text="Replicate · Flare")
        log.add(
            "兼容限制",
            "打开静图转动图，主线路选 Flare，再看备选里的 WaveSpeed。",
            "WaveSpeed 不能当这条的备选，并写明原因。Flare 仍可选。",
            f"禁用={disabled}；文案「{reason}」；Flare 可选={flare.is_enabled()}。",
            disabled and "接不住" in reason and flare.is_enabled(),
            shot(page, "walk-compat"),
        )
        if "Flare" in before_live:
            flare.click()
        else:
            page.locator("[data-testid=provider-primary] button", has_text="WaveSpeed").click()

        pick(page, "generate_image")
        page.locator("[data-testid=provider-primary] button", has_text="Replicate · Flare").click()
        page.locator("[data-testid=provider-admin]").press("Escape")
        page.locator(".ca-prov__foot").get_by_text("没保存").wait_for()
        foot = page.locator(".ca-prov__foot").inner_text()
        leave = "还有 1 个工具没保存。" in foot
        page.get_by_role("button", name="继续编辑").click()
        still = page.get_by_test_id("provider-impact").is_visible()
        page.locator("[data-testid=provider-admin]").press("Escape")
        page.get_by_test_id("provider-discard").click()
        closed = page.get_by_test_id("provider-admin").count() == 0
        open_settings(page)
        pick(page, "generate_image")
        after = page.get_by_test_id("provider-effective").inner_text()
        gen_after = tool(fetch_state(KEYED), "generate_image")
        log.add(
            "未保存离开",
            "生成图片改成 Flare 但不保存，按 Esc，先继续编辑，再放弃并关闭，然后重开。",
            "出现未保存提示。放弃后生成图片仍是默认。",
            f"提示={leave}「{foot.replace(chr(10), ' ')}」；继续后草稿还在={still}；已关闭={closed}；重开「{after}」。",
            leave and still and closed and "系统默认" in after and gen_after["effective"]["source"] == "default",
            shot(page, "walk-leave"),
        )

        page.reload(wait_until="networkidle")
        open_settings(page)
        pick(page, "edit_image")
        reopened = page.get_by_test_id("provider-effective").inner_text()
        saved = json.loads(store_path(KEYED).read_text())
        disk_edit = saved["tools"]["edit_image"]["active"]
        disk_gen = saved["tools"].get("generate_image", {}).get("active")
        log.add(
            "关闭重开仍在",
            "整页刷新后再进入改图，并读临时目录里的配置文件。",
            "改图仍是 Replicate Flare 且开着备选。生成图片没有被写上活动配置。",
            f"页面「{reopened}」；文件主线路={disk_edit['primary']['provider']}；生成图片活动配置={disk_gen}。",
            "Replicate" in reopened and disk_edit["primary"]["model"].endswith("flare") and disk_gen is None,
            shot(page, "walk-persist"),
        )

        page.get_by_test_id("provider-check-to_gif").click()
        count = page.get_by_test_id("provider-batch-count").inner_text()
        page.get_by_test_id("provider-batch-apply").click()
        page.get_by_test_id("provider-saved").wait_for()
        reveal(page)
        batch_note = page.get_by_test_id("provider-saved").inner_text()
        after_batch = fetch_state(KEYED)
        gif = tool(after_batch, "to_gif")
        edit2 = tool(after_batch, "edit_image")
        gen2 = tool(after_batch, "generate_image")
        batch_ok = (
            "已选 1 个" in count
            and gif["effective"]["provider"] == "replicate"
            and edit2["effective"]["fallback"] is True
            and (edit2["effective"]["backup"] or {}).get("provider") == "wavespeed"
            and gen2["effective"]["source"] == "default"
        )
        log.add(
            "批量只改所选",
            "只勾选静图转动图，保存所选。",
            "只有静图转动图改成 Replicate。改图的备选和生成图片不变。",
            f"「{count}」；提示「{batch_note[:48]}」；转动图={gif['effective']['provider']}；改图备选={(edit2['effective'].get('backup') or {}).get('provider')}；生成图片={gen2['effective']['source']}。",
            batch_ok and "没选中" in batch_note,
            shot(page, "walk-batch"),
        )

        pick(page, "edit_image")
        page.get_by_test_id("provider-restore").click()
        page.get_by_text("已回到这个工具的上一份").wait_for()
        restored = page.get_by_test_id("provider-effective").inner_text()
        after_restore = fetch_state(KEYED)
        log.add(
            "恢复",
            "在改图上点恢复。",
            "改图回到默认。静图转动图仍是刚才批量保存的 Replicate。",
            f"页面「{restored}」；转动图={tool(after_restore, 'to_gif')['effective']['provider']}。",
            "系统默认" in restored and tool(after_restore, "to_gif")["effective"]["provider"] == "replicate",
            shot(page, "walk-restore"),
        )

        before_llm = fetch_state(KEYED)["llm"]["active"]
        page.get_by_test_id("provider-group-llm").click()
        page.get_by_test_id("provider-llm-deepseek").click()
        page.get_by_test_id("provider-llm-check").click()
        page.get_by_test_id("provider-llm-check-result").wait_for()
        reveal(page)
        note = page.get_by_test_id("provider-llm-check-result").inner_text()
        status = page.get_by_test_id("provider-llm-status").inner_text()
        after_llm = fetch_state(KEYED)["llm"]["active"]
        log.add(
            "语言模型草稿检查",
            "切到语言模型，选官方草稿，只点检查，不保存。",
            "提示没有改活动线路、没有付费。活动配置仍是空。",
            f"结果「{note}」；现在生效「{status}」；检查前={before_llm} 检查后={after_llm}。",
            before_llm == after_llm is None and "没变" in note and ("付费" in note or "未调用" in note),
            shot(page, "walk-llm"),
        )

        page.get_by_test_id("provider-group-image").click()
        pick(page, "generate_image")
        page.locator("[data-testid=provider-primary] button", has_text="Replicate · Flare").click()

        def fail_save(route) -> None:
            if route.request.method == "PUT" and "/provider-admin/tool/" in route.request.url:
                route.abort()
            else:
                route.continue_()

        page.route("**/*", fail_save)
        page.get_by_test_id("provider-save").click()
        page.get_by_test_id("provider-error").wait_for()
        err = page.get_by_test_id("provider-error").inner_text()
        page.unroute("**/*", fail_save)
        still_default = tool(fetch_state(KEYED), "generate_image")["effective"]["source"] == "default"
        reveal(page)
        log.add(
            "网络失败",
            "生成图片选 Flare 后保存，浏览器中断这次保存请求。",
            "页面说明没有保存成功。活动配置不变。",
            f"提示「{err}」；仍是默认={still_default}。",
            "没有保存成功" in err and still_default,
            shot(page, "walk-network"),
        )

        wide = overflow(page)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(300)
        page.locator("[data-testid=provider-editor]").evaluate("el => { el.scrollTop = el.scrollHeight }")
        placed = page.evaluate(
            """() => {
              const editor = document.querySelector('[data-testid=provider-editor]').getBoundingClientRect()
              const foot = document.querySelector('.ca-prov__foot').getBoundingClientRect()
              const node = document.querySelector('[data-testid=provider-fallback]').getBoundingClientRect()
              const title = document.querySelector('#provider-title').getBoundingClientRect()
              const banner = document.querySelector('#mock-banner').getBoundingClientRect()
              return {
                fallbackUnderFooter: node.bottom > foot.top + 1,
                fallbackOutsideEditor: node.top < editor.top - 1 || node.bottom > editor.bottom + 1,
                titleUnderBanner: !(title.bottom < banner.top || title.top > banner.bottom || title.right < banner.left || title.left > banner.right) && banner.height > 0
              }
            }"""
        )
        narrow = overflow(page)
        narrow_shot = shot(page, "walk-narrow")
        log.add(
            "窄屏和溢出",
            "1440 宽看过主流程后，把窗口改成 390×844。",
            "页面和卡片没有横向溢出。",
            f"宽屏溢出={wide['bad'][:4]} 页面={wide['page']}；窄屏溢出={narrow['bad'][:4]} 页面={narrow['page']}；位置={placed}。",
            not wide["bad"] and not wide["page"] and not narrow["bad"] and not narrow["page"] and not any(placed.values()),
            narrow_shot,
        )

        nokey = browser.new_page(viewport={"width": 1440, "height": 900})
        nokey.goto(NOKEY, wait_until="networkidle")
        nokey.get_by_test_id("settings-providers").click()
        nokey.get_by_test_id("provider-search").fill("改图")
        nokey.get_by_test_id("provider-tool-edit_image").click()
        nokey.locator("[data-testid=provider-primary] button", has_text="Replicate · Flare").click()
        nokey_banner = nokey.get_by_test_id("provider-nokey").inner_text()
        save_disabled = nokey.get_by_test_id("provider-save").is_disabled()
        nokey.get_by_test_id("provider-draft").click()
        nokey.get_by_text("草稿已记住").wait_for()
        reveal(nokey)
        draft_state = fetch_state(NOKEY)
        draft_tool = tool(draft_state, "edit_image")
        log.add(
            "缺密钥阻止启用",
            "在没有密钥的另一套临时目录里，把改图选成 Replicate，先看保存按钮，再只留草稿。",
            "不能点启用。草稿可以留下，活动线路不变。",
            f"「{nokey_banner}」；启用禁用={save_disabled}；活动={draft_tool['active']}；草稿={(draft_tool['draft'] or {}).get('primary', {}).get('provider')}。",
            save_disabled and "不能启用" in nokey_banner and draft_tool["active"] is None and (draft_tool["draft"] or {}).get("primary", {}).get("provider") == "replicate",
            shot(nokey, "walk-nokey"),
        )
        browser.close()

    unexpected = [line for line in console if "favicon" not in line and "net::ERR_FAILED" not in line]
    log.add(
        "控制台",
        "全程收集页面错误和控制台 error。",
        "没有页面脚本错误。中断请求产生的网络错误另计。",
        "；".join(unexpected[:4]) or "无",
        not unexpected,
    )

    lines = [
        "# 供应商设置走查",
        "",
        "范围：设置面板的真实点击，加上隔离临时目录里的本地设置接口。没有启动完整 ComfyUI，也没有调用 WaveSpeed、Replicate 或 DeepSeek。",
        "",
        "启动：见 `tests/js/provider-admin/LIVE.md`。带密钥的页面在 8765，缺密钥的页面在 8766。两套临时目录互不影响。",
        "",
        "| 场景 | 结果 | 步骤 | 预期 | 观察 | 截图 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in log.rows:
        mark = "PASS" if row["ok"] else "FAIL"
        cell = lambda text: " ".join(text.split())
        lines.append(
            f"| {cell(row['name'])} | {mark} | {cell(row['steps'])} | {cell(row['expected'])} | {cell(row['observed'])} | {cell(row['shot'])} |"
        )
    lines.append("")
    lines.append(f"合计：{sum(row['ok'] for row in log.rows)}/{len(log.rows)} 通过。")
    REPORT.write_text("\n".join(lines) + "\n")
    if not all(row["ok"] for row in log.rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
