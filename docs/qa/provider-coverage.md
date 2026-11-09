# WaveSpeed 与 Replicate / DeepSeek 覆盖核对

核对日期：2026-11-08。没有调用付费生成，没有使用真实密钥。
实现覆盖和审计覆盖分开。只有契约测试过的路由可以在设置里保存后用于新任务。
相近模型不能当成同一条路由。

## 实现覆盖（会在保存后生效）

| 能力 | 供应商 | 状态 | 说明 |
| --- | --- | --- | --- |
| text_to_image | replicate | 已实现 | 已实现并有契约测试。无参考图时不发送 input_images。 |
| image_edit | replicate | 已实现 | 已实现。必须带 input_images。输出不是 gif。 |
| text_to_gif | replicate | 已实现 | 已实现。output_format=gif，不带参考图。不按静图价报价。 |
| reference_gif | replicate | 已实现 | 已实现。input_images 加 output_format=gif。缺图则失败，不降级成无图文生。 |
| reference_gif | wavespeed | 不启用 | 未启用。编辑不接受 gif。保存 WaveSpeed 也不改现有未托管路由。 |

Replicate 只登记了官方模型卡已核对的 GPT Image 2.6 Flare 与 Sunburst。
参数差异：WaveSpeed 用分开的 `/text-to-image` 与 `/edit`，参考图常见字段是 `images`；Replicate 用 `input_images`。
GIF 需要 `output_format=gif`，`frame_count` 2–16（默认 9），`frame_duration_ms` 20–2000（默认 200）。
官方说明 GIF 的 1:1 帧是 512×512、16:9 是 896×512，因为所有帧共用图像预算。这和静图尺寸不是一回事，静图价不能套到 GIF。费用显示为未知。
WaveSpeed 编辑 GIF 未启用：编辑只接受 png/jpeg/webp。

## 审计覆盖（不因此启用）

精选模型 153 条。
同模型已接通 4。
同模型已看过 schema、尚未接入 4。
替代模型，必须人工点名 18。
未核实（不是不支持）127。

Replicate 集合页见过 nano-banana、FLUX.3、Seedream 4.5、Ideogram 4.5、Kling、以及文案中的 Seedance / Veo。
这些 id 与仓库里的 WaveSpeed id 并不相同，没有逐字段对照，设置里不能选。

| 功能 | WaveSpeed 模型 | 结论 | 启用 |
| --- | --- | --- | --- |
| text_to_image | `openai/gpt-image-2/text-to-image` | same_model_pending | 否 |
| text_to_image | `google/nano-banana-2.1/text-to-image` | alternative_explicit | 否 |
| text_to_image | `bytedance/seedream-v5.0-pro` | unverified | 否 |
| text_to_image | `openai/gpt-image-2.5-sunburst/text-to-image` | unverified | 否 |
| text_to_image | `openai/gpt-image-2.5-flare/text-to-image` | same_model_pending | 否 |
| text_to_image | `alibaba/qwen-image-3.0/text-to-image` | unverified | 否 |
| text_to_image | `google/nano-banana-pro/text-to-image` | alternative_explicit | 否 |
| text_to_image | `google/nano-banana-2/text-to-image` | alternative_explicit | 否 |
| text_to_image | `google/nano-banana-2-lite/text-to-image` | alternative_explicit | 否 |
| text_to_image | `openai/gpt-image-1.5/text-to-image` | unverified | 否 |
| text_to_image | `bytedance/seedream-v5.0-lite` | unverified | 否 |
| text_to_image | `bytedance/seedream-v4.5` | unverified | 否 |
| text_to_image | `bytedance/seedream-v4` | alternative_explicit | 否 |
| text_to_image | `luma/uni-v1/text-to-image` | unverified | 否 |
| text_to_image | `black-forest-labs/flux-3/text-to-image` | alternative_explicit | 否 |
| text_to_image | `wavespeed-ai/flux-2-pro/text-to-image` | unverified | 否 |
| text_to_image | `wavespeed-ai/flux-2-max/text-to-image` | unverified | 否 |
| text_to_image | `alibaba/qwen-image-3.0-pro/text-to-image` | unverified | 否 |
| text_to_image | `midjourney/text-to-image` | unverified | 否 |
| text_to_image | `ideogram-ai/ideogram-v4` | unverified | 否 |
| text_to_image | `ideogram-ai/ideogram-v4.5` | unverified | 否 |
| text_to_image | `pruna-ai/p-image/ideogram` | unverified | 否 |
| text_to_image | `recraft-ai/recraft-v3` | unverified | 否 |
| text_to_image | `wavespeed-ai/flux-dev-lora` | unverified | 否 |
| text_to_image | `wavespeed-ai/qwen-image/text-to-image-lora` | unverified | 否 |
| text_to_image | `openai/gpt-image-2.6-flare/text-to-image` | connected | 是 |
| text_to_image | `openai/gpt-image-2.6-sunburst/text-to-image` | connected | 是 |
| image_edit | `openai/gpt-image-2/edit` | same_model_pending | 否 |
| image_edit | `google/nano-banana-2.1/edit` | alternative_explicit | 否 |
| image_edit | `bytedance/seedream-v5.0-pro/edit` | unverified | 否 |
| image_edit | `openai/gpt-image-2.5-sunburst/edit` | unverified | 否 |
| image_edit | `bytedance/seedream-v5.0-lite/edit` | unverified | 否 |
| image_edit | `alibaba/qwen-image-3.0/edit` | unverified | 否 |
| image_edit | `google/nano-banana-pro/edit` | alternative_explicit | 否 |
| image_edit | `google/nano-banana-2/edit` | alternative_explicit | 否 |
| image_edit | `google/nano-banana-2-lite/edit` | alternative_explicit | 否 |
| image_edit | `openai/gpt-image-2.5-flare/edit` | same_model_pending | 否 |
| image_edit | `openai/gpt-image-1.5/edit` | unverified | 否 |
| image_edit | `bytedance/seedream-v4.5/edit` | unverified | 否 |
| image_edit | `bytedance/seedream-v4/edit` | alternative_explicit | 否 |
| image_edit | `luma/uni-v1/edit` | unverified | 否 |
| image_edit | `black-forest-labs/flux-3/image-edit` | alternative_explicit | 否 |
| image_edit | `wavespeed-ai/flux-2-pro/edit` | unverified | 否 |
| image_edit | `wavespeed-ai/flux-2-max/edit` | unverified | 否 |
| image_edit | `alibaba/qwen-image-3.0-pro/edit` | unverified | 否 |
| image_edit | `ideogram-ai/ideogram-v4.5/edit` | unverified | 否 |
| image_edit | `wavespeed-ai/qwen-image/edit-lora` | unverified | 否 |
| image_edit | `openai/gpt-image-2.6-flare/edit` | connected | 是 |
| image_edit | `openai/gpt-image-2.6-sunburst/edit` | connected | 是 |
| text_to_video | `bytedance/seedance-2.0/text-to-video` | alternative_explicit | 否 |
| text_to_video | `kwaivgi/kling-v3.0-std/text-to-video` | unverified | 否 |
| text_to_video | `google/veo3.1-fast/text-to-video` | alternative_explicit | 否 |
| text_to_video | `wavespeed-ai/minimax-h3/text-to-video` | unverified | 否 |
| text_to_video | `bytedance/seedance-2.5/text-to-video` | unverified | 否 |
| text_to_video | `bytedance/seedance-2.0-fast/text-to-video` | unverified | 否 |
| text_to_video | `bytedance/seedance-2.0-mini/text-to-video` | unverified | 否 |
| text_to_video | `bytedance/seedance-v1-pro-t2v-720p` | unverified | 否 |
| text_to_video | `kwaivgi/kling-v4.0/text-to-video` | unverified | 否 |
| text_to_video | `kwaivgi/kling-video-o3-std/text-to-video` | unverified | 否 |
| text_to_video | `kwaivgi/kling-video-o1/text-to-video` | unverified | 否 |
| text_to_video | `kwaivgi/kling-v2.6-std/text-to-video` | unverified | 否 |
| text_to_video | `kwaivgi/kling-v2.5-turbo-pro/text-to-video` | unverified | 否 |
| text_to_video | `google/veo3.1/text-to-video` | alternative_explicit | 否 |
| text_to_video | `google/veo3` | unverified | 否 |
| text_to_video | `google/veo3-fast` | unverified | 否 |
| text_to_video | `google/gemini-omni-1.1-flash/text-to-video` | unverified | 否 |
| text_to_video | `google/gemini-omni-flash/text-to-video` | unverified | 否 |
| text_to_video | `alibaba/wan-3.0/text-to-video` | unverified | 否 |
| text_to_video | `alibaba/wan-3.0-prime/text-to-video` | unverified | 否 |
| text_to_video | `alibaba/wan-2.6/text-to-video` | unverified | 否 |
| text_to_video | `alibaba/wan-2.5/text-to-video` | unverified | 否 |
| text_to_video | `vidu/q3/text-to-video` | unverified | 否 |
| text_to_video | `vidu/text-to-video-q2` | unverified | 否 |
| text_to_video | `vidu/text-to-video-q1` | unverified | 否 |
| text_to_video | `minimax/hailuo-02/t2v-standard` | unverified | 否 |
| text_to_video | `minimax/hailuo-2.3/t2v-standard` | unverified | 否 |
| text_to_video | `lightricks/ltx-2-pro/text-to-video` | unverified | 否 |
| text_to_video | `wavespeed-ai/wan-2.2/t2v-480p-lora` | unverified | 否 |
| image_to_video | `bytedance/seedance-2.0/image-to-video` | alternative_explicit | 否 |
| image_to_video | `kwaivgi/kling-v3.0-std/image-to-video` | unverified | 否 |
| image_to_video | `google/veo3.1-fast/image-to-video` | alternative_explicit | 否 |
| image_to_video | `wavespeed-ai/minimax-h3/image-to-video` | unverified | 否 |
| image_to_video | `bytedance/seedance-2.5/image-to-video` | unverified | 否 |
| image_to_video | `bytedance/seedance-2.0-fast/image-to-video` | unverified | 否 |
| image_to_video | `bytedance/seedance-2.0-mini/image-to-video` | unverified | 否 |
| image_to_video | `bytedance/seedance-v1-pro-i2v-720p` | unverified | 否 |
| image_to_video | `kwaivgi/kling-v4.0/image-to-video` | unverified | 否 |
| image_to_video | `kwaivgi/kling-video-o3-std/image-to-video` | unverified | 否 |
| image_to_video | `kwaivgi/kling-video-o1/image-to-video` | unverified | 否 |
| image_to_video | `kwaivgi/kling-v2.6-std/image-to-video` | unverified | 否 |
| image_to_video | `kwaivgi/kling-v2.5-turbo-std/image-to-video` | unverified | 否 |
| image_to_video | `google/veo3.1/image-to-video` | alternative_explicit | 否 |
| image_to_video | `google/veo3/image-to-video` | unverified | 否 |
| image_to_video | `google/veo3-fast/image-to-video` | unverified | 否 |
| image_to_video | `google/gemini-omni-1.1-flash/image-to-video` | unverified | 否 |
| image_to_video | `google/gemini-omni-flash/image-to-video` | unverified | 否 |
| image_to_video | `alibaba/wan-3.0/image-to-video` | unverified | 否 |
| image_to_video | `alibaba/wan-3.0-prime/image-to-video` | unverified | 否 |
| image_to_video | `alibaba/wan-2.6/image-to-video` | unverified | 否 |
| image_to_video | `alibaba/wan-2.5/image-to-video` | unverified | 否 |
| image_to_video | `vidu/q3/image-to-video` | unverified | 否 |
| image_to_video | `vidu/image-to-video-q2-pro` | unverified | 否 |
| image_to_video | `vidu/image-to-video-q2-turbo` | unverified | 否 |
| image_to_video | `vidu/image-to-video-q1` | unverified | 否 |
| image_to_video | `minimax/hailuo-02/i2v-standard` | unverified | 否 |
| image_to_video | `minimax/hailuo-2.3/i2v-standard` | unverified | 否 |
| image_to_video | `minimax/hailuo-2.3/fast` | unverified | 否 |
| image_to_video | `lightricks/ltx-2-pro/image-to-video` | unverified | 否 |
| image_to_video | `wavespeed-ai/wan-2.2/i2v-480p-lora` | unverified | 否 |
| reference_to_video | `kwaivgi/kling-video-o3-std/reference-to-video` | unverified | 否 |
| reference_to_video | `wavespeed-ai/minimax-h3/reference-to-video` | unverified | 否 |
| reference_to_video | `alibaba/wan-3.0/reference-to-video` | unverified | 否 |
| reference_to_video | `google/veo3.1-fast/reference-to-video` | unverified | 否 |
| motion_control | `kwaivgi/kling-v3.0-std/motion-control` | unverified | 否 |
| motion_control | `wavespeed-ai/wan-2.2/animate` | unverified | 否 |
| motion_control | `pixverse/motion-control/mimic` | unverified | 否 |
| motion_control | `bytedance/seedance-2.5/motion-control` | unverified | 否 |
| lip_sync | `wavespeed-ai/infinitetalk-fast` | unverified | 否 |
| lip_sync | `kwaivgi/kling-lipsync/audio-to-video` | unverified | 否 |
| lip_sync | `bytedance/omni-human-2.0` | unverified | 否 |
| lip_sync | `sync/lipsync-3` | unverified | 否 |
| extend_video | `wavespeed-ai/minimax-h3/video-extend` | unverified | 否 |
| extend_video | `alibaba/wan-3.0/video-extend` | unverified | 否 |
| extend_video | `bytedance/seedance-2.0-fast/video-extend` | unverified | 否 |
| extend_video | `google/veo3.1-fast/video-extend` | unverified | 否 |
| upscale_video | `wavespeed-ai/video-upscaler` | unverified | 否 |
| upscale_video | `wavespeed-ai/flashvsr` | unverified | 否 |
| upscale_video | `wavespeed-ai/video-upscaler-pro` | unverified | 否 |
| remove_video_background | `wavespeed-ai/video-background-remover` | unverified | 否 |
| remove_video_background | `bria/fibo/video-background-remover` | unverified | 否 |
| music | `minimax/music-3.0` | unverified | 否 |
| music | `wavespeed-ai/ace-step-1.5` | unverified | 否 |
| music | `google/lyria-3.5/music` | unverified | 否 |
| music | `mureka-ai/mureka-v9/generate-bgm` | unverified | 否 |
| music | `elevenlabs/music-v2.5` | unverified | 否 |
| music | `wavespeed-ai/yue2-3b/text-to-music` | unverified | 否 |
| sound_effect | `mirelo-ai/sfx-2.0/text-to-audio` | unverified | 否 |
| sound_effect | `elevenlabs/sound-effects-v2` | unverified | 否 |
| sound_effect | `kwaivgi/kling-text-to-audio` | unverified | 否 |
| sound_effect | `sonilo/v1/text-to-sfx` | unverified | 否 |
| text_to_speech | `wavespeed-ai/qwen3-tts/text-to-speech` | unverified | 否 |
| text_to_speech | `minimax/speech-2.8-turbo` | unverified | 否 |
| text_to_speech | `elevenlabs/eleven-v4` | unverified | 否 |
| text_to_speech | `bytedance/seed-speech-tts-2.0` | unverified | 否 |
| voice_clone | `wavespeed-ai/qwen3-tts/voice-clone` | unverified | 否 |
| voice_clone | `wavespeed-ai/omnivoice/voice-clone` | unverified | 否 |
| voice_clone | `kwaivgi/kling-v2.6/create-voice` | unverified | 否 |
| voice_clone | `minimax/voice-clone` | unverified | 否 |
| image_to_3d | `tripo3d/h3.1/image-to-3d` | unverified | 否 |
| image_to_3d | `tripo3d/h3.1/multiview-to-3d` | unverified | 否 |
| image_to_3d | `wavespeed-ai/trellis-2/image-to-3d` | unverified | 否 |
| image_to_3d | `wavespeed-ai/hunyuan-3d-v3.1/image-to-3d-rapid` | unverified | 否 |
| image_to_3d | `hyper3d/rodin-v2.5/image-to-3d` | unverified | 否 |

## 工具

| 工具 | 功能 | Replicate |
| --- | --- | --- |
| generate_image | text_to_image | 仅保存后的文生/编辑 |
| edit_image | image_edit | 仅保存后的文生/编辑 |
| replace_text | image_edit | 否，留在 WaveSpeed |
| edit_region | image_edit | 否，留在 WaveSpeed |
| move_object | erase_region | 否，留在 WaveSpeed |
| style_transfer | image_edit | 否，留在 WaveSpeed |
| edit_elements | segment | 否，留在 WaveSpeed |
| create_mockup | image_edit | 否，留在 WaveSpeed |
| upscale_image | upscale_image | 否，留在 WaveSpeed |
| remove_background | remove_background | 否，留在 WaveSpeed |
| expand_image | expand_image | 否，留在 WaveSpeed |
| split_layers | split_layers | 否，留在 WaveSpeed |
| change_angle | change_angle | 否，留在 WaveSpeed |
| erase_region | erase_region | 否，留在 WaveSpeed |
| generate_video | image_to_video | 否，留在 WaveSpeed |
| animate_image | image_to_video | 否，留在 WaveSpeed |
| extend_video | extend_video | 否，留在 WaveSpeed |
| upscale_video | upscale_video | 否，留在 WaveSpeed |
| remove_video_background | remove_video_background | 否，留在 WaveSpeed |
| generate_music | music | 否，留在 WaveSpeed |
| generate_sound_effect | sound_effect | 否，留在 WaveSpeed |
| text_to_speech | text_to_speech | 否，留在 WaveSpeed |
| image_to_3d | image_to_3d | 否，留在 WaveSpeed |
| ocr | ocr | 否，留在 WaveSpeed |
| transcribe | transcribe | 否，留在 WaveSpeed |

## LLM

没有管理员覆盖时，语言模型默认是官方 `https://api.deepseek.com` 的 `deepseek-flash`。显式保存 WaveSpeed 才继续用 `deepseek/deepseek-v4.1-flash-1017`。
官方可选项是 `https://api.deepseek.com` 的 `deepseek-flash`（文档：现由 DeepSeek-V4.1-Flash-1017 提供）和 `deepseek-v4-pro`。
调用名不同。官方省略 thinking 时默认开启思考；思考模式下工具调用必须回传 reasoning_content，否则 400。
现有 Agent 不回传 reasoning_content，因此官方路由会显式关闭思考。deepseek-flash 非思考温度固定 1.0。
现有链路不使用 SSE 流式。工具调用形状按官方非思考文档对齐，本环境未做付费实测。
价格未知。不保存不改变活动配置。无密钥则新任务失败，不回退 WaveSpeed。
不能据此认为任意 OpenAI 兼容模型都可以换上。

