# 供应商设置走查

范围：设置面板的真实点击，加上隔离临时目录里的本地设置接口。没有启动完整 ComfyUI，也没有调用 WaveSpeed、Replicate 或 DeepSeek。

启动：见 `tests/js/provider-admin/LIVE.md`。带密钥的页面在 8765，缺密钥的页面在 8766。两套临时目录互不影响。

| 场景 | 结果 | 步骤 | 预期 | 观察 | 截图 |
| --- | --- | --- | --- | --- | --- |
| 进入设置 | PASS | 打开本地页面，点击「供应商」。 | 出现供应商对话框，横幅标明本地设置接口。 | 标题「供应商」；横幅「本地设置接口 · 临时目录 · 不调用生成供应商」。入口见 /opt/cursor/artifacts/walk-home.png。 | /opt/cursor/artifacts/walk-enter.png |
| 分类和搜索 | PASS | 点「视频」，再回到全部并搜索「改图」。 | 视频分类只有视频工具；搜索只留下改图。 | 视频分类含生成视频=True 且不含生成图片=True；搜索只见改图=True。 | /opt/cursor/artifacts/walk-search.png |
| 主备共存 | PASS | 改图选 Replicate Flare、备选 WaveSpeed、打开兜底并保存。生成图片不改。 | 改图生效为 Replicate，生成图片仍是默认。价格未知会拦住新任务。 | 页面「现在生效 Replicate · Flare，没受理时会试备选」；拦截「这条已保存，但价格未知，所以新任务会停住，不会扣费。保存成功不等于已经能用。」；影响「保存后只影响这个工具的新任务。 主线路改为 Replicate。 备选已设置。 兜底」；接口改图=replicate 生成图片=default。 | /opt/cursor/artifacts/walk-coexist.png |
| 兼容限制 | PASS | 打开静图转动图，主线路选 Flare，再看备选里的 WaveSpeed。 | WaveSpeed 不能当这条的备选，并写明原因。Flare 仍可选。 | 禁用=True；文案「WaveSpeed · 现有模型 这个工具的结果 WaveSpeed 接不住，不能当备选」；Flare 可选=True。 | /opt/cursor/artifacts/walk-compat.png |
| 未保存离开 | PASS | 生成图片改成 Flare 但不保存，按 Esc，先继续编辑，再放弃并关闭，然后重开。 | 出现未保存提示。放弃后生成图片仍是默认。 | 提示=True「还有 1 个工具没保存。 继续编辑 放弃并关闭」；继续后草稿还在=True；已关闭=True；重开「现在生效 WaveSpeed，系统默认」。 | /opt/cursor/artifacts/walk-leave.png |
| 关闭重开仍在 | PASS | 整页刷新后再进入改图，并读临时目录里的配置文件。 | 改图仍是 Replicate Flare 且开着备选。生成图片没有被写上活动配置。 | 页面「现在生效 Replicate · Flare，没受理时会试备选」；文件主线路=replicate；生成图片活动配置=None。 | /opt/cursor/artifacts/walk-persist.png |
| 批量只改所选 | PASS | 只勾选静图转动图，保存所选。 | 只有静图转动图改成 Replicate。改图的备选和生成图片不变。 | 「已选 1 个可切换工具」；提示「已保存 1 个。价格未知，这些新任务会停住，不会扣费。没选中的工具没变。」；转动图=replicate；改图备选=wavespeed；生成图片=default。 | /opt/cursor/artifacts/walk-batch.png |
| 恢复 | PASS | 在改图上点恢复。 | 改图回到默认。静图转动图仍是刚才批量保存的 Replicate。 | 页面「现在生效 WaveSpeed，系统默认」；转动图=replicate。 | /opt/cursor/artifacts/walk-restore.png |
| 语言模型草稿检查 | PASS | 切到语言模型，选官方草稿，只点检查，不保存。 | 提示没有改活动线路、没有付费。活动配置仍是空。 | 结果「只检查草稿。当前对话线路没变，没有付费请求。价格未知。官方模型不是无差异替换。」；现在生效「现在生效 WaveSpeed · deepseek/deepseek-v4.1-flash-1017」；检查前=None 检查后=None。 | /opt/cursor/artifacts/walk-llm.png |
| 网络失败 | PASS | 生成图片选 Flare 后保存，浏览器中断这次保存请求。 | 页面说明没有保存成功。活动配置不变。 | 提示「没有保存成功。请检查网络后再试。」；仍是默认=True。 | /opt/cursor/artifacts/walk-network.png |
| 窄屏和溢出 | PASS | 1440 宽看过主流程后，把窗口改成 390×844。 | 页面和卡片没有横向溢出。 | 宽屏溢出=[] 页面=False；窄屏溢出=[] 页面=False；位置={'fallbackUnderFooter': False, 'fallbackOutsideEditor': False, 'titleUnderBanner': False}。 | /opt/cursor/artifacts/walk-narrow.png |
| 缺密钥阻止启用 | PASS | 在没有密钥的另一套临时目录里，把改图选成 Replicate，先看保存按钮，再只留草稿。 | 不能点启用。草稿可以留下，活动线路不变。 | 「还没有 Replicate 密钥。可以先留草稿，不能启用。」；启用禁用=True；活动=None；草稿=replicate。 | /opt/cursor/artifacts/walk-nokey.png |
| 控制台 | PASS | 全程收集页面错误和控制台 error。 | 没有页面脚本错误。中断请求产生的网络错误另计。 | 无 |  |

合计：13/13 通过。
