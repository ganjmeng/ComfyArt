# #673 C 组 5 个 skill 真实链路冒烟计划（1K，每个 1 次）

- 基线：main `b47b6671`；skill 定义 `src/skills.ts`（5 个都在 `HIDDEN_BUILTIN_SKILL_IDS`）。
- 链路（app 真实链路，和 UI 点 skill 一致，见 `src/bot.ts`）：`POST /comfyart/bot/chats` → `POST /comfyart/bot/chats/{id}/send {text, skill, refs, lang, run_mode}`（`api/bot.py bot_send`）→ 服务端开轮次 `paid_guard.begin_turn`（#142/#709，文本写「出 1 张」→ 守卫上限 1）→ agent 调 MCP `generate_image`（`api/mcp.py _tools_call` → `paid_guard.before_call`）→ `api/mcp_tools/canvas._auto_choice` Auto 选模型 → 页面执行 → `/comfyart/wavespeed/run`。
- 尺寸：`src/generate.ts targetSize`，1K = 短边 1024，snap16。
- 脚本：`run_smoke.py`，默认 dry-run，逐个打印会打到 app 的完整请求（estimate / 建 chat / send / poll）；`--live` 不再直连 WaveSpeed，只打 app 接口。每次调用前先查免费 `POST /comfyart/wavespeed/estimate`，超估价即停；累计已花 + 本次报价 > $0.8 即停；同一 skill 连续失败 2 次即停；每次调用前后记 WaveSpeed 余额（key 从 `/home/box/.secrets/comfyart-test.env` 读、不回显），结果写 `runs.json`。

| skill | preset | 样例输入（用户填写） | refs | model（Auto 实际选中） | 尺寸 | 估价 |
|---|---|---|---|---|---|---|
| naive-illustration | line | 巨大咖啡杯+小上班族搬方糖，"今日续命" | 无 | midjourney/text-to-image | 1024×1360 (3:4) | ≤$0.10（无记录价，live 先 quote） |
| logo-abstract | circle | 橘猫照片 → 圆形几何双色 logo | 1 张猫照 | openai/gpt-image-2.5-flare/edit | 1024×1024 (1:1) | $0.0378 |
| photo-split-poster | hard | 街景照片上半 + 几何下半，"CITY WALK" | 1 张街景 | openai/gpt-image-2.5-flare/edit | 1024×1360 (3:4) | $0.0378 |
| ppt-visual | cover | 发布会封面，"2027 创作新范式" | 无 | openai/gpt-image-2.5-flare/text-to-image | 1824×1024 (16:9) | $0.0378 |
| promo-ecommerce | kv | 精华液双十一 KV，"限时直降" "11.11" | 1 张产品图 | openai/gpt-image-2.5-flare/edit | 1024×1360 (3:4) | $0.0378 |

prompt = 用户输入 + 换行 + 所选 preset 的 Style 句（原文见 `src/skills.ts` presets）。完整请求体以 `python docs/qa/673-smoke/run_smoke.py` 输出为准。

**预算**：4×$0.0378 + ≤$0.10 = **≤$0.2512**（上限 $0.8）。$0.0378 来源：#673 C 组 1K 出图记录（gpt-image-2.5-flare）；live 时以 WaveSpeed price API 报价为准。

**风险/待决**：naive-illustration 被 Auto 路由到 midjourney（非 gpt-image），价格与出图张数需 live 前 quote 确认；如技术经理要求统一模型，需在 skill 里指定 model。3 个带 refs 的 skill 需先把测试照片上传成公开 URL，替换 `REF_*` 占位（脚本遇占位拒绝 live）。

## 通过标准（每个 skill）
1. submit 返回 200 且拿到 task id；poll 终态 success，返回图片 URL。
2. 图片能下载并解码（PIL 打开），在画布/composer 正常显示（本地构建 app 截图核对）。
3. 输出尺寸 = 上表尺寸（或同比例，误差 ≤1%）。
4. RapidOCR 不出现 Lovart 金标文字（对照 docs/design/673/gold 的 OCR 词表）；只允许 prompt 里引号内的文案。
5. 产物落在画布 frame 上，composer 回显 skill 与 prompt。
6. 余额差 = 各张 quote 之和（误差 ≤$0.001），总计不超过 $0.8。

## 交接
- 状态：`--live` 已改为走 app 真实链路（bot chat send → paid_guard → generate_image → Auto 路由），dry-run 跑通 5 个 skill；**未做任何付费生成**。
- 本地起 app 跑 live：`WAVESPEED_API_KEY` 从 secrets env 导入后 `./scripts/start.sh`（http://127.0.0.1:8188/comfyart/）；Agent Settings 打开 MCP 和 Agent，配好 agent provider（默认 `local-llm`，需 LLM key）；新建一个项目并保持该 Loomi 标签页打开（画布工具在页面里执行）；然后 `python3 docs/qa/673-smoke/run_smoke.py --live --project <id> --ref logo-abstract=URL --ref photo-split-poster=URL --ref promo-ecommerce=URL`。
- 阻塞：`paid_gen_guard` P0 查清前不跑 live（技术经理定）；3 张 ref 公开 URL 待上传；#727 待合并。
- 注意：守卫只在 bot 轮次里生效（直接调 `/comfyart/mcp` 没有轮次时 `before_call` 放行），所以脚本必须走 `/send`，不能直调 MCP；agent 本身的 LLM 调用费用不在 WaveSpeed 余额里。
- 已花费：$0。
- 余额：$44.134249（开发工程师在 #687 报的最新值，本次未查询）。
