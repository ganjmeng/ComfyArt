# #870 单测分诊（step 2 · triage only）

- **主 tip：** `be41019d`（#875 已合入）
- **工作树：** `/workspace/wt870b`（分支 `docs/870-triage`，detached from `origin/main`）
- **命令（与 gate UNIT / #875 测试评论一致）：**
  ```bash
  env -u WAVESPEED_API_KEY -u KIE_API_KEY -u COMFYART_SKIP_NODE_TESTS GATE=1 no_proxy='*' \
    /workspace/ca-venv/bin/python -m pytest -q -rs -p no:cacheprovider \
    tests -k "not e2e" -m "not gate_skip"
  ```
- **结果：** **97 failed** / 3084 passed / 26 skipped / 456 deselected（≈3.5 min，$0）
- **说明：** 本文件只做分诊与批次建议，**不改代码、不开 PR、不评论 GitHub**。

## 桶计数

| 桶 | 条数 | 含义 |
|---|---:|---|
| **REAL BUG** | **79** | 产品代码/路由与当前契约不符（含管理端 LLM 覆盖导致回归套件全灭） |
| **STALE TEST** | **13** | 产品行为已变（#812/#707/#721 文案/结构/封面），测例仍断言旧值 |
| **ENV/FLAKY** | **4** | 缺 blob、无写权限、Chrome fixture 空 DOM |
| **SHOULD DELETE** | **1** | 依赖已不存在的 git 对象，无现行等价物 |
| **合计** | **97** | |

> 同一根因的参数化用例合并叙述；表中「条数」仍按 pytest node 计。

---

## REAL BUG（79）

### A. 管理端 LLM 覆盖打穿 settings / mock（58）

**根因：** `api/provider_admin.py` 在无管理员 LLM 区段时 `_llm_choice(None) → deepseek-flash`，`llm_model_override()` 经 `provider_model()` 始终返回官方 `deepseek-flash`，忽略 `bot-local-llm-url` / `bot-model-local-llm`。agent 回归与部分 WaveSpeed LLM 测例因此绕开 mock，落到官方 DeepSeek（GATE 下无 `DEEPSEEK_API_KEY` → 空 tools / 密钥 notice）。

**证据：** `api/bot_turns.py:67-72`；`api/provider_admin.py:217-229`；失败 notice 含 `DeepSeek 官方未配置 DEEPSEEK_API_KEY`；`assert tools == []`（期望 `generate_image` 等）。

| nodeid（代表） | 条数 | 动作 | 工作量 | 关联 |
|---|---:|---|---|---|
| `tests/agent_regression/test_agent_regression.py::test_agent_regression[*]` | 56 | 产品：无 admin 区段时勿覆盖显式 settings URL；或 harness 写入 WaveSpeed/`existing` admin 路由并 mock `DEEPSEEK`。先修覆盖规则再重跑全套。 | M | provider admin / DeepSeek 官方路由；#120/#870 |
| `tests/test_agent_llm_defaults.py::test_saved_custom_endpoint_and_model_still_win` | 1 | 同上：自定义 endpoint+model 必须赢过「无区段→官方默认」。 | S | 同上 |
| `tests/test_wavespeed.py::test_llm_complete_uses_openai_compatible_endpoint` | 1 | 列出的首个模型 `my-model` 被 override 成 `deepseek-flash`；修 override 或测例改为显式 WaveSpeed admin。 | S | 同上 |

### B. #721 明文错误未落到 generic（8）

**根因：** `tests/js/object_errors.ts` plain body `{ error: 'project not found' }` 期望 `wsErr.generic`（「这次生成没有完成…」），实际抛出原文 `project not found`——`wsBodyError` / allowlist 路径未覆盖该站点。

**证据：** `tests/test_object_errors.py:49` 附近；`src/wsErrors.ts` #721 注释要求非白名单 → generic。

| nodeid | 动作 | 工作量 | 关联 |
|---|---|---|---|
| `test_localized_message[elements\|projects\|bot\|llm]-[zh\|en]` ×8 | 修 `wsBodyError`/各 fetch 站点，明文非白名单 → `wsErr.generic`；补回归。 | S | #721 |

### C. 源码注释仍含竞品品牌名（违反 #559 守卫）（10）

**根因：** `#707` 注释写「Lovart dropdown」，触发全仓 brand 扫描。产品政策：`src/` 不得出现竞品词（含注释）。

**证据：** `src/generate.ts:56`、`src/botCommands.ts:141`、`src/sizeLockPref.ts:1`。

| nodeid | 动作 | 工作量 | 关联 |
|---|---|---|---|
| `test_no_lovart_string_in_src` / `test_no_brand_word_in_src` / `test_no_competitor_*` / `test_icons_not_bulb_and_no_lovart_in_src` / `test_no_lovart_in_src` / `test_no_lovart_string_in_src_skills` / `test_placeholder_mentions_at_reference` / `test_settings_menu_ac_structure` 等 ×10 | 注释改为「模型下拉 / picker / catalog dropdown」，不改逻辑。 | S | #559 #707 |

### D. 其它真实缺陷（3）

| nodeid | 原因（证据） | 动作 | 工作量 | 关联 |
|---|---|---|---|---|
| `tests/test_tts_voice_defaults.py::test_voice_clone_has_no_default_and_asks_for_sample_before_any_charge` | mock `submit` lambda 未接 `size_lock` 关键字（API 签名扩展） | 更新 mock 签名 / `submit` 调用点 | S | size_lock 推广 |
| `tests/test_models_registered_712.py::test_builtin_paths_use_only_registered_models` | `ProviderAdmin.tsx` 使用无 feature 后缀 id：`openai/gpt-image-2.6-flare` / `sunburst` | Admin 改为完整 catalog id，或注册表允许短 id | S | #712 #872 |
| `tests/test_model_order.py::test_list_models_text_to_image_recommended_first` | recommended 列表出现重复序号（`[96,281,…]` vs `[96,96,281,…]`） | 查 `list_models` 排序/去重 | S | model picker |

---

## STALE TEST（13）

| nodeid | 原因（证据） | 动作 | 工作量 | 关联 |
|---|---|---|---|---|
| `test_agent_llm_defaults.py::test_defaults_resolve_to_wavespeed_deepseek` | 默认已改为官方 `deepseek-flash`（catalog 文档），测例仍要 `deepseek/deepseek-v4.1-flash-1017` | 更新期望；或测「显式保存 WaveSpeed」路径 | S | provider admin |
| `test_default_builtin_agent.py::test_no_wavespeed_key_gives_a_clear_status_not_a_401` | notice 已是 DeepSeek 缺 key，不再含 `WaveSpeed Key` | 按新默认文案断言 | S | 同上 |
| `test_media_hero_356.py::test_canvas_gen_frame_flat_pill` | 脆弱 CSS 切片：`split("[data-running]")[1].split(".ca-gen-ring")[0]` 落到 error 子规则，看不到同文件稍后的 `animation: none`（`canvas.css:59-69` 仍在） | 改断言方式（正则/整段包含） | S | #356 #870 CSS |
| `test_skill_cards_494.py::test_covers_ten_webps_with_source_manifest` | `animated-poster` 等封面助手已换（非 `cover643`） | 按现行 `cover812`/`cover687`/… 更新 | S | #643 #812 |
| `test_skill_modal_541.py::test_examples_carousel_is_data_driven` | #812 解隐后示例计数/集合变化 | 更新期望 map | S | #812 #541 |
| `test_skill_fields_687.py::test_motion_title_desc_poster_806` | 注释含 `remake` 触发禁词 | 改注释或收紧扫描范围 | S | #806 |
| `test_plan_quote_235.py::test_card_reuses_the_confirm_component_and_skips_the_second_dialog` | 源码无 `ca-panel__secondary`（confirm UI 改名） | 对齐现行 class / testid | S | #235 |
| `test_video_quote_tier.py::test_frontend_wiring` | `comfy.ts` 不再含 `wsBody?.error?.estimate` | 对齐现行报价错误字段 | S | quote tier |
| `test_toolbar_fixed_244.py::test_preview_markup` | 无 `hint={t('common.download')}` | 对齐 ImageToolbar 现行 markup | S | #244 |
| `test_wavespeed.py::test_estimate_falls_back_to_catalog_price_marked_as_estimate` | `estimate` 多返回 `model` 字段 | 断言改为包含关系 / 更新期望 dict | S | #159 |
| `test_agent_loop_audit_410.py::test_harness_user_skill_chip_shrinks_first_text_one_line[zh\|en]` ×2 | `chipLeft` 几何断言失败（布局/#825 后） | 按现行气泡布局重测或改阈值 | M | #410 #825 |
| `test_storyboard_flow.py::test_storyboard_generate_to_canvas` | 走到报价确认（`$0.73; confirm`）而非直接落画布 | 测例补确认流，或 mock 报价阈值 | M | storyboard / paid |
| `test_personal_center_498` 等若仅因 Lovart 注释 → 已归 REAL BUG C；此处不重复 | — | — | — | — |

> Lovart 十测已计入 REAL BUG C（政策违规）。若技术经理认定「注释可保留竞品对照」，可改桶为 STALE（放宽扫描）。

---

## ENV/FLAKY（4）

| nodeid | 原因（证据） | 动作 | 工作量 | 关联 |
|---|---|---|---|---|
| `test_svg826_canvas_tip.py::test_three_product_states_are_local_fixtures` | `PermissionError: /opt/cursor`（`ART = Path("/opt/cursor/artifacts/svg826")`） | 改写到 workspace/`tmp`；或 gate 给权限 | S | #826 |
| `test_ui_controls_batch.py::test_confirm_click_and_escape_fire_once[ok\|cancel\|escape]` ×3 | Chrome dump 的 HTML 为空（`data-runs` 不在 `''`） | 查 headless Chrome/fixture 端口；标记 flaky 或改 Playwright | M | confirm UI |
| （可选）agent_regression 在修 override 前若强依赖真 key | GATE 无 `DEEPSEEK_API_KEY` | 不建议测环境塞真 key；应以 mock 修复为准 | — | — |

---

## SHOULD DELETE（1）

| nodeid | 原因（证据） | 动作 | 工作量 | 关联 |
|---|---|---|---|---|
| `test_clothing_swap_featured_reuse_805.py::test_reuse_featured_pins_and_single_cover_holds_stay_empty` | `git show e1eb48ba…:805/reuse/live-promo-decor/featured.webp` exit 128（对象不在当前历史） | 删除或改为现存 pin SHA；无现行 805 reuse 资产则删测 | S | #805 |

---

## 建议修复批次（优先级）

| 批次 | 内容 | 预计清掉 | 工作量 | 说明 |
|---|---|---:|---|---|
| **B0** | 注释去竞品词（Lovart→中性表述） | ~10 | S | 无行为风险，立刻降噪 |
| **B1** | LLM admin override：settings/自定义 URL 不被官方默认吞掉；agent_regression harness 钉 WaveSpeed/`existing` | ~58 | M | **最大块**；决定后续回归是否可绿 |
| **B2** | #721 plain → `wsErr.generic`（object_errors ×8） | 8 | S | 明确回归 |
| **B3** | 小真实缺陷：tts `size_lock` 签名、ProviderAdmin 短 id、model_order 去重 | 3 | S | |
| **B4** | 过期断言批：media_hero CSS、skill 封面/模态、plan/video quote、toolbar、estimate dict、defaults 文案 | ~12 | S–M | 可与 B0 并行 |
| **B5** | ENV：svg826 路径、confirm Chrome fixture、#805 删/换 pin | 5 | S–M | |
| **B6** | 布局类：audit_410 chip 几何、storyboard 确认流 | 3 | M | 需设计/产品一眼 |

**不建议：** 在 GATE 里注入真实 `DEEPSEEK_API_KEY` 来「绿」agent_regression——违反 $0/mock 契约，且掩盖 override 问题。

---

## 附录：按文件聚合

| 文件 | 失败数 | 主桶 |
|---|---:|---|
| `tests/agent_regression/test_agent_regression.py` | 56 | REAL BUG A |
| `tests/test_object_errors.py` | 8 | REAL BUG B |
| brand/Lovart 守卫（多文件） | 10 | REAL BUG C |
| `tests/test_ui_controls_batch.py` | 3 | ENV |
| 其余各 1–2 | 20 | 见上表 |

## 复现日志

- `/tmp/870unit/UNIT2.log`
- `/tmp/870unit/junit.xml`
- `/tmp/870unit/fails.json`
