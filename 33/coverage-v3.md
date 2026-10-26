# #33 功能覆盖表 v3

> **基线 tip**：`main` `d1629e9`（含 #154 WaveSpeed mock、#156/#169/#170/#171 导出与报错抽测等）  
> **规则**：全程 mock / $0；不做 Playwright e2e；不卡 CI。  
> **本 PR（PR1）**：只刷新对照表。本地画布工具补测见 **PR2**（`tests/test_local_canvas_tools.py`），不挡本 PR。

列说明：`file::test` 指向当前 tip 上存在的用例；✅ = 已有；○ = 可选加固；🔲 = M6 / PR2 后续。

---

## A. 导出（#156 AC — 已满足）

| 功能 | 正常路径 | 报错路径 | 备注 |
|---|---|---|---|
| 导出 PNG | `tests/test_export_formats.py::test_png_export_opens_with_scaled_size` ✅ | `::test_export_is_offline`（断网/无云端） ✅ | #156 / #162 |
| 导出 PDF | `::test_pdf_export_is_one_page_with_frame_size` ✅ | 同上 ✅ | 单页、尺寸对齐画板 |
| 导出 PPTX | `::test_pptx_export_one_slide_per_frame` ✅ | 同上 ✅ | 一画板一页 |
| 导出 JPG | `::test_jpg_export_opens_with_scaled_size_and_background` ✅ | 同上 ✅ | #169 |
| 导出 SVG | `::test_svg_export_is_vector_svg` ✅ | 同上 ✅ | #169 |
| PPTX 可编辑文字 | `::test_pptx_editable_text_keeps_text_runs` / `::test_pptx_one_ppr_per_paragraph_first_child` ✅ | 同上 ✅ | #169 |
| 导出对话框默认 2x | `::test_export_dialog_defaults_to_2x` ✅ | — | #169 |
| 视频编辑器导出 | `tests/test_video_editor_flow.py::test_export_renders_valid_video_matching_timeline` ✅ | `::test_export_missing_clip_fails_without_output` ✅ | 本地 ffmpeg，无 WaveSpeed |
| 时间线+音乐导出 | `tests/test_timeline_music_export.py::test_export_24fps_with_music_track` ✅ | — | |

`pytest tests/test_export_formats.py` 期望：**9 passed**。

---

## B. WaveSpeed / PAID 工具与 feature（#154 后）

| 功能 / tool → feature | 正常路径 | 报错路径 | 备注 |
|---|---|---|---|
| `generate_image` → `text_to_image` | `test_wavespeed.py::test_text_to_image_submit_poll_download` ✅ | `::test_failed_task_reports_error` / `::test_401_on_submit_and_poll` / `::test_timeout` / `::test_170_image_task_failed_is_readable` ✅ | #161 / #170 |
| `edit_image` → `image_edit` | `::test_edit_uploads_local_input` ✅ | 共用 submit/poll 报错族 ✅ | |
| `replace_text` → `image_edit` | `test_quote_equals_charge_203.py`（报价=扣费）✅ | 共用报错族 ✅ | 无独立 submit 专用用例；报价覆盖 |
| `edit_region` → `image_edit` | `test_region_pasteback.py::test_region_edit_sends_only_the_crop_to_sunburst…` ✅ | `::test_empty_selection_is_400…` / `::test_box_fully_outside_is_400…` ✅ | |
| `style_transfer` → `image_edit` | 走 `image_edit` 共用路径；**专用 submit happy 未单测** ○ | 共用报错族 ✅ | **可选加固**（不挡 #33） |
| `create_mockup` → `image_edit` | `test_wavespeed.py::test_mockup_surface_depth_and_mask` ✅ | `::test_mockup_surface_failure_propagates` ✅ | |
| `move_object` → `erase_region` | `test_region_pasteback.py::test_move_object_erases_a_crop_and_composites_locally` ✅ | 区域校验 400 用例 ✅ | |
| `erase_region` | `test_wavespeed.py::test_erase_converts_mask` ✅ | 共用报错族 ✅ | |
| `edit_elements` → `segment` | `::test_sam_segment_points_and_text`；`test_seg_prompts.py` 多条 ✅ | `test_seg_prompts.py::test_empty_segment_request_is_blocked…` ✅ | |
| `split_layers` | `::test_split_layers_default_runs_without_confirmation` ✅ | `::test_jobs_over_50_cents_need_confirmation` / `::test_confirmation_route_answers_409…` ✅ | |
| `change_angle` | `test_angle_249.py::test_angle_request_body` ✅ | 报价/面板校验同文件 ✅ | |
| `upscale_image` | `test_quote_equals_charge_203.py`（含该 tool）✅ | 共用报错族 / #170 图片失败 ✅ | |
| `remove_background` | `test_quote_equals_charge_203.py` ✅ | 共用报错族 ✅ | |
| `expand_image` | `test_quote_equals_charge_203.py` ✅ | 共用报错族 ✅ | |
| `structure_control`（含 depth 等） | `test_control_preview.py` / `test_ref_structure.py` / `test_semantic_seg.py` ✅ | `test_control_preview.py::test_missing_fields_400`；`test_ref_structure` 校验失败路径 ✅ | 本地 map 免费；云端 map 需确认 |
| `generate_video` / `animate_image` → `image_to_video` | `::test_image_to_video_with_last_frame` / animate 同文件 ✅ | `::test_170_video_insufficient_balance_on_submit` ✅ | #170 |
| `text_to_video` | `::test_text_to_video_default_and_mapping` / `::test_video_duration_snaps…` ✅ | 同上 + 时长校验 ✅ | |
| `reference_to_video` / `motion_control` / `lip_sync` | `::test_reference_motion_lipsync` ✅ | 共用视频报错 ✅ | |
| `extend_video` / `upscale_video` / `remove_video_background` | `::test_video_tools` ✅ | 共用视频报错 ✅ | |
| `generate_music` → `music` | `::test_audio_tools` / duration clamp / ace-step 字段 ✅ | `::test_170_audio_task_moderation_is_readable` ✅ | #170 |
| `generate_sound_effect` | `::test_audio_tools` ✅ | 同上 ✅ | |
| `text_to_speech` / `voice_clone` | `::test_audio_tools`；`test_tts_voice_defaults.py` ✅ | voice-clone 缺采样拦截 ✅ | |
| `image_to_3d` | `::test_3d_single_and_multiview` ✅ | `::test_170_3d_submit_server_error_is_readable` ✅ | #170 |
| `ocr` | `::test_ocr_runs_on_wavespeed`；`test_ocr.py` 解析 ✅ | `test_text_outputs.py::test_ocr_empty_outputs_raise` ✅ | |
| `transcribe` / `caption` | `::test_transcribe_route` / `::test_caption_route`；`test_text_outputs.py` ✅ | `test_text_outputs.py` 空文本/超时带扣费 ✅ | |
| `custom_workflow` | `::test_custom_workflow_submit_maps_fields` / check 路由 ✅ | check 失败路径同文件 ✅ | #75 恢复 |
| 余额不足 / 权限 / 超时文案 | — | `test_ws_errors.py` 全套；`::test_error_kind_1407…` / `::test_insufficient_permissions…` / `::test_170_task_timeout…` ✅ | #161 / #170 / #174 |
| 付费确认守卫 | `test_paid_gen_guard.py` ✅ | declined / cancel 文案 ✅ | |
| 报价=扣费 | `test_quote_equals_charge_203.py` / `test_quote_matches_submit.py` ✅ | unpriced / schema 缺失 ✅ | #203 |

---

## C. 项目 / MCP / Agent / 其它原版保留能力

| 功能 | 正常路径 | 报错路径 | 备注 |
|---|---|---|---|
| 项目新建/打开/保存往返 | `test_project_flow.py::test_new_edit_save_reopen…` ✅ | `::test_bad_save_keeps_previous_copy` ✅ | |
| 项目列表 CRUD / 版本 | `test_projects.py` ✅ | 删除联动 chat 等 ✅ | |
| MCP 工具列表与中继 | `test_mcp.py` ✅ | `::test_page_errors_come_back_as_tool_errors` / 无页面 / 超时 ✅ | `focus` 仅有错误中继抽测 |
| Agent 回归集（#231） | `tests/agent_regression/`（含 create_slides / add_text / update_shapes 脚本路径）✅ | fault-retry / 步数上限 (#232) ✅ | mock LLM + mock WS；$0 |
| 原版工具未删守卫 | `test_original_features_kept.py` ✅ | — | 只断言工具仍在，不替代行为测 |
| PDF 导入 | `test_pdf.py::test_pages_are_rendered_into_input` ✅ | `::test_not_a_pdf_is_a_bad_request` ✅ | |
| Key / 余额 UX | `test_wavespeed_key.py` / `test_key_*.py` ✅ | 缺 key 拦截 ✅ | |
| 分镜 | `::test_storyboard_*`；`test_storyboard_flow.py` ✅ | 总价确认 ✅ | |
| 视频编辑（本地） | `test_edit_video.py` / `test_video_editor_flow.py` ✅ | 缺 clip 导出失败 ✅ | 非付费工具 |

---

## D. 本地画布工具缺口 → **PR2 / M6，不挡本 PR**

下列工具不走 WaveSpeed 云端；#33 产品绿灯只要求覆盖表刷新 + 导出 mock。行为测放到 PR2 `tests/test_local_canvas_tools.py`：

| 工具 | 现状 | 计划 |
|---|---|---|
| `vectorize_image` | 仅工具保留断言 / guide | PR2 本地 happy + 坏输入 |
| `place_design` | 同上 | PR2 |
| `place_html` | 同上 | PR2 |
| `create_slides` | Agent 回归 case `12` 有脚本路径；无独立 pytest 单测文件 | PR2 补专用单测（导出 PPTX 已由 `test_export_formats` 覆盖） |
| `add_text` / `add_shape` / `create_frame` | Agent 回归部分触及；无 `test_local_canvas_tools` | PR2 |
| `update_shapes` / `delete_shapes` | 同上 | PR2 |
| `focus` | `test_mcp.py` 仅错误中继 | PR2 补 happy |

---

## E. #241 遗留（M6 follow-up，不挡合并）

- [ ] 回复语言：界面语言 ≠ 输入语言 的用例（mock 模型目前跟输入语言）
- [ ] 断网拦截：除域名解析外，在 socket 层拦 IP 直连

---

## F. 相对 v2 的变更摘要（`f785ada` / `13010aa` → `d1629e9`）

| 项 | v2 | v3（本 tip） |
|---|---|---|
| PNG/PDF/PPTX 导出 mock | 有（#162） | **仍满足**；并含 JPG/SVG/可编辑 PPTX/默认 2x（#169） |
| 图/视/音/3D 报错抽测 | 发版前计划 | **已落地**（#170） |
| 覆盖表文档 | issue 评论 + `33/coverage-v2.png` | **本文件** `33/coverage-v3.md` 按 tip 重扫 |
| 本地画布工具 | 「无 mock」 | 仍列缺口，明确 **PR2** |
| `style_transfer` 专用 submit | 未单列 | 标为 **可选加固** |

---

## G. 关卡建议

1. 产品勾选 #33 AC：导出 mock（#156）✅ + 覆盖表（本 PR）✅  
2. 本地工具与 #241 项进 M6 / 开 PR2，**不**作为本 PR 合并阻塞  
3. 可选：补 `style_transfer` 专用 submit happy（hardening）
