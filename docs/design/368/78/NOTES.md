# #368 Arti P0-2 记忆中心 · #78 shots

**Branch:** `tip/368-arti-p0-2-memory` · closes #368  
**AC:** issue comment [6431402780](https://github.com/ganjmeng/ComfyArt/issues/368#issuecomment-6431402780) · box `ComfyArt-review-assets/arti/P0-2-MEMORY.md`  
**Product lock:** 账户级跨项目记忆；四组 + 行内编辑 + 对话改记忆；mock-first；体验 1:1 Lovart CN。

**Base:** `origin/main` @ `0fab025` (after #370 / #367)

## Honest source
Tip CSS harness + static DOM matching ArtiMemory (four groups / edit row / … menu / chat CTA composer / assets add) — NOT full Electron / NOT live userdata backend. Persistence in app = `memory.ts` userdata + localStorage demo fallback.

## After (this tip)
| Shot | Theme | Shows | Priority |
|------|-------|-------|----------|
| `after/memory-groups.png` | light | 四组：基础信息 / 协作方式 / 审美偏好 / 常用资产 + sticky CTA | **MUST** |
| `after/memory-edit.png` | light | 行内更正：文本 + / 取消 / 保存 | **MUST** |
| `after/memory-row-menu.png` | light | … 菜单：更正记忆 / 删除 | **MUST** |
| `after/memory-chat-cta.png` | light | 「通过对话修改记忆」composer；+：从本地上传 / 从资产库选择 | **MUST** |
| `after/memory-assets-add.png` | light | 常用资产用途提示 → 添加 / 取消 | **MUST** |

## Evidence (box, not in tip)
`ComfyArt-review-assets/lovart-arti-20261027/` · `arti-memory.png` · `arti-memory-edit.png` · `NOTES.md`

## Out of scope (not shot / not touched)
P0-3 进化日志完整实现（SHOULD → follow-up）· P1 mascot / 委托 · P0-1 shell rework · Brand Kit merge · paid generation · voice input
