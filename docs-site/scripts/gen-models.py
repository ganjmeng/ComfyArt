"""Regenerate the model tables in guides/models.mdx (en + zh) from api/curated_models.json and api/wavespeed_models.json.

Run from the repo root: python docs-site/scripts/gen-models.py
"""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
cur = json.loads((ROOT / 'api/curated_models.json').read_text())['features']
ws = json.loads((ROOT / 'api/wavespeed_models.json').read_text())['features']
NAMES = {
    'text_to_image': ('Text to image', '文生图'), 'image_edit': ('Image edit', '图片编辑'),
    'text_to_video': ('Text to video', '文生视频'), 'image_to_video': ('Image to video', '图生视频'),
    'reference_to_video': ('Reference to video', '参考生视频'), 'motion_control': ('Motion control', '动作控制'),
    'lip_sync': ('Lip sync', '对口型'), 'extend_video': ('Extend video', '延长视频'),
    'upscale_video': ('Upscale video', '视频放大'), 'remove_video_background': ('Remove video background', '视频去背景'),
    'music': ('Music', '配乐'), 'sound_effect': ('Sound effect', '音效'), 'text_to_speech': ('Text to speech', '配音'),
    'voice_clone': ('Voice clone', '声音克隆'), 'image_to_3d': ('Image to 3D', '图转 3D'),
}
HELPERS = {
    'expand_image': ('Expand', '扩图'), 'split_layers': ('Split layers', '拆图层'),
    'remove_background': ('Remove background', '抠图'), 'erase_region': ('Eraser / move object', '擦除 / 移动物体'),
    'upscale_image': ('Upscale', '放大'), 'segment': ('Smart select / Edit Elements cut-outs', '智能选择 / 元素编辑抠图'),
    'change_angle': ('Multi-angle', '多角度'), 'structure_control': ('Structure modes', '结构类模式'),
    'ocr': ('Text recognition (OCR)', '文字识别（OCR）'), 'caption': ('Image caption', '图片描述'),
    'transcribe': ('Speech to text', '语音转文字'),
}

def model_id(m):
    return m if isinstance(m, str) else m.get('id') or m.get('model')

def table(i):
    head = ['| Function | Default model | Models (recommended + more) |', '|---|---|---|'] if i == 0 else ['| 功能 | 默认模型 | 模型数（推荐 + 更多） |', '|---|---|---|']
    rows = []
    for k, v in cur.items():
        d = v.get('default') or model_id(v['models'][0])
        more = len(v.get('more', []))
        rows.append(f"| {NAMES.get(k, (k, k))[i]} | `{d}` | {len(v['models'])}{f' + {more}' if more else ''} |")
    head2 = ['', '| Helper | Model |', '|---|---|'] if i == 0 else ['', '| 辅助功能 | 模型 |', '|---|---|']
    rows2 = []
    for k, n in HELPERS.items():
        m = ws.get(k)
        m = m if isinstance(m, str) else (m or {}).get('model') or (m or {}).get('default')
        if m:
            rows2.append(f'| {n[i]} | `{m}` |')
    return '\n'.join(head + rows + head2 + rows2)

for path, i in [('docs-site/guides/models.mdx', 0), ('docs-site/zh/guides/models.mdx', 1)]:
    p = ROOT / path
    s = p.read_text()
    s = re.sub(r'({/\* models:start \*/}\n)(?:.*?\n)?({/\* models:end \*/})', lambda m: m.group(1) + table(i) + '\n' + m.group(2), s, flags=re.S)
    p.write_text(s)
