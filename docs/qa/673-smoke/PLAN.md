# #673 C 组 5 个 skill 真实链路冒烟计划（1K，每个 1 次）

- 基线：main `b47b6671`；skill 定义 `src/skills.ts`（5 个都在 `HIDDEN_BUILTIN_SKILL_IDS`）。
- 链路（app 真实链路，和 UI 点 skill 一致，见 `src/bot.ts`）：`POST /comfyart/bot/chats` → `POST /comfyart/bot/chats/{id}/send {text, skill, refs, lang, run_mode}`（`api/bot.py bot_send`）→ 服务端开轮次 `paid_guard.begin_turn`（#142/#709，文本写「出 1 张」→ 守卫上限 1）→ agent 调 MCP `generate_image`（`api/mcp.py _tools_call` → `paid_guard.before_call`）→ `api/mcp_tools/canvas._auto_choice` Auto 选模型 → 页面执行 → `/comfyart/wavespeed/run`。
- 尺寸：`src/generate.ts targetSize`，1K = 短边 1024，snap16。
- 脚本：`run_smoke.py`，默认 dry-run，逐个打印会打到 app 的完整请求（estimate / 建 chat / send / poll）；`--live` 不再直连 WaveSpeed，只打 app 接口。每次调用前先查免费 `POST /comfyart/wavespeed/estimate`，超估价即停；累计已花 + 本次报价 > $0.8 即停；同一 skill 连续失败 2 次即停；每次调用前后记 WaveSpeed 余额（key 从 `/home/box/.secrets/comfyart-test.env` 读、不回显），结果写 `runs.json`。

| skill | preset | 样例输入（用户填写） | refs | model（Auto 实际选中） | 尺寸 | 估价 |
|---|---|---|---|---|---|---|
| naive-illustration | line | 巨大咖啡杯+小上班族搬方糖，"今日续命" | 无 | midjourney/text-to-image | 1024×1360 (3:4) | ≤$0.10（无记录价，live 先 quote） |
| logo-abstract | circle | 辫子面包照片 → 圆形几何双色 logo | 1 张面包照 | openai/gpt-image-2.5-flare/edit | 1024×1024 (1:1) | $0.0378 |
| photo-split-poster | hard | 街景照片上半 + 几何下半，"CITY WALK" | 1 张街景 | openai/gpt-image-2.5-flare/edit | 1024×1360 (3:4) | $0.0378 |
| ppt-visual | cover | 发布会封面，"2027 创作新范式" | 无 | openai/gpt-image-2.5-flare/text-to-image | 1824×1024 (16:9) | $0.0378 |
| promo-ecommerce | kv | 罐装气泡饮双十一 KV，"限时直降" "11.11" | 1 张产品图 | openai/gpt-image-2.5-flare/edit | 1024×1360 (3:4) | $0.0378 |

prompt = 用户输入 + 换行 + 所选 preset 的 Style 句（原文见 `src/skills.ts` presets）。完整请求体以 `python docs/qa/673-smoke/run_smoke.py` 输出为准。

**预算**：4×$0.0378 + ≤$0.10 = **≤$0.2512**（上限 $0.8）。$0.0378 来源：#673 C 组 1K 出图记录（gpt-image-2.5-flare）；live 时以 WaveSpeed price API 报价为准。

**风险/待决**：naive-illustration 被 Auto 路由到 midjourney（非 gpt-image），价格与出图张数需 live 前 quote 确认；如技术经理要求统一模型，需在 skill 里指定 model。3 个带 refs 的 skill 已用仓库自有洗图（见下「Refs」），脚本默认值即这三张。

## Refs（技术经理定：用仓库里已洗好的图，不用 Lovart 金标，不上网找；pin main `b47b6671` 全 SHA，均已验 HTTP 200 image/webp）
- logo-abstract：`643/wash/premium-website/examples/03.webp`（单个辫子面包，1536×1536）— https://raw.githubusercontent.com/ganjmeng/ComfyArt/b47b6671368581f54d8a5c9e26fd0f3548010ffc/643/wash/premium-website/examples/03.webp
- photo-split-poster：`643/wash/pose-fission/examples/01.webp`（城市街道、阳光人行道，有一位人物，1529×2048）— https://raw.githubusercontent.com/ganjmeng/ComfyArt/b47b6671368581f54d8a5c9e26fd0f3548010ffc/643/wash/pose-fission/examples/01.webp
- promo-ecommerce：`643/wash/product-to-packaging/examples/05.webp`（三罐 KOIRA 产品图，自有虚构品牌，1536×1017）— https://raw.githubusercontent.com/ganjmeng/ComfyArt/b47b6671368581f54d8a5c9e26fd0f3548010ffc/643/wash/product-to-packaging/examples/05.webp
- 偏差：洗图里没有宠物/动物照片，也没有精华液产品照；所以 logo 改用面包（物体），promo 改用罐装饮料，样例文案已同步改（「辫子面包」「罐装气泡饮」）。要换成猫/精华液需另洗一张（付费），待定。

## Agent LLM（技术经理定）
- 用 app 测试环境默认 provider，不为冒烟另换：`bot-provider=local-llm`，URL `https://llm.wavespeed.ai/v1`，模型 `deepseek/deepseek-v4.1-flash-1017`（`api/settings.py`）。
- key 解析（`api/llm_key.py`）：`COMFYART_LOCAL_LLM_API_KEY` → Agent 设置里的 `bot-local-llm-key` → 端点是 llm.wavespeed.ai 时回落到 `WAVESPEED_API_KEY`。测试 env 里 `WAVESPEED_API_KEY` 已配，另两项未配 → 默认链路可用，不会卡。
- 注意：LLM 走 WaveSpeed 同一个账号，token 费用会从 WaveSpeed 余额里扣。所以余额差 = 图片 quote 之和 + LLM token 费；通过标准 6 改为「余额差 − 记录的 LLM 估算费 ≈ quote 之和（误差 ≤$0.001）」。
- 每个 turn 记 token 数（prompt/completion）和估算花费，写进交接单独一列，**不算进 $0.8**。
- 测试 env 没配可用 key（LLM 调用返回鉴权错误）就立即停，报告，不重试。

## 通过标准（每个 skill）
1. submit 返回 200 且拿到 task id；poll 终态 success，返回图片 URL。
2. 图片能下载并解码（PIL 打开），在画布/composer 正常显示（本地构建 app 截图核对）。
3. 输出尺寸 = 上表尺寸（或同比例，误差 ≤1%）。
4. RapidOCR 不出现 Lovart 金标文字（对照 docs/design/673/gold 的 OCR 词表）；只允许 prompt 里引号内的文案。
5. 产物落在画布 frame 上，composer 回显 skill 与 prompt。
6. 余额差 − 各 turn 记录的 LLM 估算费 = 各张 quote 之和（误差 ≤$0.001）；图片总计不超过 $0.8（LLM 费单列，不计入）。

## 交接
- 状态：`--live` 已改为走 app 真实链路（bot chat send → paid_guard → generate_image → Auto 路由），dry-run（带 refs）跑通 5 个 skill，输出见 `dryrun.txt`，合计估价 $0.2512；**未做任何付费生成**。
- 本地起 app 跑 live：`WAVESPEED_API_KEY` 从 secrets env 导入后 `./scripts/start.sh`（http://127.0.0.1:8188/comfyart/）；Agent Settings 打开 MCP 和 Agent，agent provider 保持默认 `local-llm`（WaveSpeed LLM，回落用 `WAVESPEED_API_KEY`）；新建一个项目并保持该 Loomi 标签页打开（画布工具在页面里执行）；然后 `python3 docs/qa/673-smoke/run_smoke.py --live --project <id>`（refs 已是默认值）。
- 阻塞：#727 合并后即可跑 live（技术经理定：守卫 bug 不会超支，$0.8 兜底，不等守卫 PR）。refs 已就绪。
- 注意：守卫只在 bot 轮次里生效（直接调 `/comfyart/mcp` 没有轮次时 `before_call` 放行），所以脚本必须走 `/send`，不能直调 MCP；agent 的 LLM 调用默认也走 WaveSpeed，费用在同一余额里，单独记账。
- CDN 预检（新增）：`--live` 在任何付费调用前先对 WaveSpeed 出图 CDN `d2h7xmz5gqybh9.cloudfront.net:443` 做免费 TLS 握手，失败即中止并写 `out/cdn_preflight.json`。2026-11-04 22:41（UTC+8）本机实测：**失败**，`SSLEOFError: UNEXPECTED_EOF_WHILE_READING`（curl 同样 exit 35）；同时 `api.wavespeed.ai` 200、GitHub 正常，问题只在这台机器到该 CDN 的链路。CDN 不通前 live 会自动中止，不花钱。
- 已花费：$0。
- 余额：$44.134249（开发工程师在 #687 报的最新值，本次未查询）。
