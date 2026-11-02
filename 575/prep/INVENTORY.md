# #575 — Motion template video wash inventory

**Date:** 2026-11-02 Asia/Shanghai · inventory only (no paid wash / no gh comments)  
**Issue:** [ganjmeng/ComfyArt#575](https://github.com/ganjmeng/ComfyArt/issues/575) OPEN  
**Refs:** #569 P2 · #494 · product lock comments `6559610972` / `6559613275` · `594/prep/COVER-FOCUS-MOTION.md`  
**Soft next:** after #620 / #573 (tip context main@`b2811cd5`); this box `ComfyArt-main` HEAD was `b315a57` at inventory time.

---

## 1. Sources found

### 1.1 Motion template videos (the #575 rewash targets)

| slot | title | current file (on-disk + remote) | tech |
|---|---|---|---|
| **motion-01** | Poster Animation / 海报动画 | `569/wash/motion/templates/01-poster-animation.mp4` | h264 · **1112×834** · **11.46s** · ~5.1 MB · 24 fps |
| **motion-02** | First-to-Last Frame Animation / 首帧到末帧动画 | `569/wash/motion/templates/02-first-to-last-frame-animation.mp4` | h264 · **720×1280** · **4.04s** · ~1.6 MB |

**Commit pin (live, HTTP 200):** `bd043d4cff5019fc4117b5b2f3a33ae437015a28`  
Raw URLs (also in `569/wash/manifest.json` → `motion.templates[].video`):

- `https://raw.githubusercontent.com/ganjmeng/ComfyArt/bd043d4c…/569/wash/motion/templates/01-poster-animation.mp4`
- `https://raw.githubusercontent.com/ganjmeng/ComfyArt/bd043d4c…/569/wash/motion/templates/02-first-to-last-frame-animation.mp4`

**Companion stills (same dir / same commit):** `@thumb.webp`, `@poster.webp`, full `.webp` per template; SBS `569/wash/sbs-motion.webp` @ `bd043d4c` (manifest link also via `881494ff` for older SBS path in #569 tip).

**Local box copies (not under `ComfyArt-review-assets/` HEAD):**

- `/workspace/594w/review-assets/569/wash/motion/templates/*.mp4`
- `/workspace/ra-590-wash-v2/569/wash/motion/templates/*.mp4`
- Manifest: `…/569/wash/manifest.json` (`assets_commit` = `bd043d4c`)

`ComfyArt-review-assets/` checkout itself has **no** `569/` or `575/` tree yet (detached at docs tip `0cfcb82d`); this prep folder is the first `575/` artifact on that mount.

### 1.2 Path mismatch vs `src/skills.ts` TODO comment

`src/skills.ts` (#575 TODO block) documents expected future paths as:

```
569/wash/videos/motion-01-poster-animation.mp4
569/wash/videos/motion-02-first-to-last-frame-animation.mp4
```

Those **do not exist** (HTTP **404** at `bd043d4c`). Real assets live under **`569/wash/motion/templates/`** with names **`01-poster-animation.mp4` / `02-first-to-last-frame-animation.mp4`**. Prefer keeping the existing templates layout on rewash; update the TODO comment when wiring `preset.video`.

### 1.3 Skill-level cover hover video (already shipped — not the P2 rewash)

Upgrade-9 card hover for `motion` already uses:

- `video('motion')` → `https://raw.githubusercontent.com/ganjmeng/ComfyArt/1bbb3f208f18b26ef95c8d9f16efeea111c43ac7/494/wash/videos/motion.mp4`
- From #529 / #532 WaveSpeed **`bytedance/seedance-v1-pro-fast/image-to-video`** (d=3, 480p, 4:3); **different pipeline** from the #569 template mp4s.

`preset.video` for the two motion templates is still **unset** (`[None, None]` asserted in `test_skill_cover_494.py` / TODO string in `test_skill_cover_video_575.py`). Card uses cover `video('motion')` only until design PASS + wire.

### 1.4 Thumbnail / banner example videos (issue scope, already wired)

Per #575 body + current `skills.ts`:

- `thumbnail.examples` leads with `video('thumbnail')` then stills `ex541`
- `banner.examples` leads with `video('banner')` then thin stills

These are the short cover mp4s under `494/wash/videos/{thumbnail,banner}.mp4` @ `1bbb3f20` — **not** the motion-01/02 rewash. No new wash required for that bullet unless product opens a separate eye FAIL.

### 1.5 Prior wash notes (#569 P2)

| source | note |
|---|---|
| #569 body (设计 P2 08:5x) | Re-wash videos; then kie balance ~140 insufficient; wait EL top-up. **motion-01** 小海报轻微晃动 (Lovart left is static). **motion-02** 中间过渡约半秒文字发糊. |
| Comment [6551000076](https://github.com/ganjmeng/ComfyArt/issues/569#issuecomment-6551000076) | Design PASS with those 2 P2s; 01 = 11.5s 1112×834 LUMEN DRIFT→KOI-77; 02 = 4s 720×1280 cream magazine morph. |
| Comment [6550761346](https://github.com/ganjmeng/ComfyArt/issues/569#issuecomment-6550761346) | Wash list: stills `nano-banana-2-1` (fallback GPT Image 2.5 i2i); **视频沿用 #532 的 seedance 管线**. |
| Manifest `model.video` | **01:** `bytedance/seedance-2-mini` (two 6s first=last clips + ffmpeg 0.6s xfade). **02:** `bytedance/seedance-2` (first+last frame). Frames: `nano-banana-2-1`. |
| Manifest `kie.rejected` | `motion-0 v1 seedance-2 12s first->last (garbled KOI-70 title, cropped)` — prior fail motif. |
| #575 body | Design rewash motion 2 first (cost on this card); fullstack may scaffold `video` field / play-fallback in parallel; schedule after #552→#557→#573→#576 data (later product: after #586/#587, before #583). Soft: hover muted loop P1 AC on comments 6559610972 / 6559613275; morning hard was stills+#595 only. |

### 1.6 Brand / copyright collide motifs (from NOTES, not pixel eye this turn)

- Fiction titles/copy in current 01: **「LUMEN DRIFT」→「KOI-77」** (design-authored; rejected v1 had garbled **KOI-70**).
- Wash rule: **no Lovart original text**, no watermark / author / avatar, no logo; compose like Lovart layout with **our** titles/dates/people ([6550761346](https://github.com/ganjmeng/ComfyArt/issues/569#issuecomment-6550761346)).
- Image standing rule WaveSpeed `openai/gpt-image-2.5-sunburst/edit` i2i applies to **stills**, **not** these videos — do not default video rewash to that model.
- No separate brand-collide FAIL logged beyond “clear readable original copy / no Lovart glyphs.” Re-check on eye PASS that new titles stay fictional and sharp.

---

## 2. Gaps

| gap | detail |
|---|---|
| P2 quality | 01 left mini-poster still wobbles vs Lovart static; 02 mid-xfade text blur ~0.5s |
| `preset.video` unset | Fullstack blocked on design PASS + new commit pin |
| Path docs drift | skills.ts TODO `569/wash/videos/motion-0N-…` ≠ actual `569/wash/motion/templates/0N-…` |
| No `575/` wash tree yet | Only this `prep/INVENTORY.md`; no staging / SBS / ledger |
| `ComfyArt-review-assets` missing `569/` | Must fetch `bd043d4c` (or clone from `/workspace/594w/review-assets/569`) before local eye |
| New6 hover mp4 | Optional A-video under `594/wash/videos/<id>.mp4` still deferred (`SKILL_VIDEO_PENDING_NEW6`); separate from motion-01/02 |
| Lovart refs | Manifest points to `/workspace/569ref/motion-{0,1}.mp4` — **not present** on this box |
| Paid wash not run | Explicit: inventory only; kie key present but **do not call** |

---

## 3. Recommended wash steps (before fullstack wires `preset.video`)

**Tooling (known from #569 manifest — not WaveSpeed sunburst stills):**

1. **Frames / key stills:** kie `nano-banana-2-1` i2i from current washed stills (or Lovart-masked refs if available). Fallback GPT Image 2.5 i2i only if frames FAIL.
2. **Video:**
   - **01:** kie `bytedance/seedance-2-mini` — prefer two ~6s loops with **static left panel** (or post composite: left = locked still, right = animated), ffmpeg xfade ≤0.6s if stitching; keep ~4:3 / ~12s / text sharp on both panels.
   - **02:** kie `bytedance/seedance-2` first+last frame; target ~9:16 / ~4s; **no mid-transition text smear** (hold type as overlay / regenerate with sharper text guidance / shorter morph).
3. **Do not** spend on WaveSpeed cover-style `seedance-v1-pro-fast` for these template clips unless kie seedance regresses — that path is for short explore hover (`494/wash/videos`).
4. Deliver under `569/wash/motion/templates/` (overwrite or `v2/` subdir + manifest bump). Also refresh `@poster` / `@thumb` / SBS left Lovart | right us.
5. Update `569/wash/manifest.json` (`assets_commit`, `model`, `taskIds`, reject bad takes). Pin raw URLs.
6. Design PASS tip on #575 (SBS + playable raw links). **Then** fullstack sets `preset.video` on motion presets + drops TODO; tests flip `motionPresetVideos` from `[None,None]`.
7. Cost: book on #575; confirm kie balance before submit (issue noted prior top-up; do not invent spend).

**Out of scope for this rewash:** upgrade9 `video('motion')` cover hover; new6 A-video; Ken Burns fakes (product lock: no fake motion).

---

## 4. Acceptance (design PASS gate)

- [ ] **motion-01:** left mini-poster **static** (no wobble); right motion OK; titles/dates/people fictional & sharp; no Lovart glyphs / logos / watermarks.
- [ ] **motion-02:** first→last morph smooth; **transition text stays sharp** (no ~0.5s blur).
- [ ] Spec roughly matches current: 01 ~4:3 ~12s; 02 ~9:16 ~4s (ok to nudge if quality wins).
- [ ] Assets commit-pinned on review-assets; manifest + SBS updated.
- [ ] **zh-light + en-dark** play (template grid / detail) recorded or screenshot+note; pair with Lovart if available.
- [ ] **#78 pin** path noted in tip (follow project #78 before/after or harness convention used on sibling design tips).
- [ ] Fullstack may proceed to wire `preset.video` only after design PASS comment.

Hover muted-loop card AC (comments 6559610972 / 6559613275) is **P1 soft** for the wider #575 package — not a blocker for the motion-01/02 still rewash PASS, but tip should call out play/leave→poster when wired.

---

## 5. Blockers

1. **Paid API / kie spend** — rewash not started this turn by instruction; needs design owner + balance check.
2. **Missing local Lovart refs** (`/workspace/569ref/…`) — restore or re-pull for SBS eye.
3. **`preset.video` wire** blocked on design PASS + new pin (tests currently require TODO / null videos).
4. Soft schedule only — does not gate morning stills/#595 hard line (already product-locked).

---

## 6. Pointers

| item | path / URL |
|---|---|
| This inventory | `ComfyArt-review-assets/575/prep/INVENTORY.md` |
| Cover focus product lock | `594/prep/COVER-FOCUS-MOTION.md` |
| Wash list (A-video deferred) | `594/prep/WASH-LIST.md` |
| Current motion mp4s (local) | `/workspace/594w/review-assets/569/wash/motion/templates/` |
| Manifest | `/workspace/594w/review-assets/569/wash/manifest.json` |
| skills.ts TODO | `src/skills.ts` ~L107–114 / motion skill ~L201 |
| Issue | https://github.com/ganjmeng/ComfyArt/issues/575 |
