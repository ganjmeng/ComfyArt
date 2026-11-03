# #642 → #78 tip-pin — Phase3-S3 full copy + dialog (NEW19)

**Branch:** `feat/642-skills-phase3-s3-copy-dialog` · **Asia/Shanghai** · Issue #642  
**Base tip:** `567967b7` (main after #657)  
**SSOT:** `PRODUCT-LOCK-PHASE3.md` · `PHASE3-HARDEN-DIFF.md` · design Page Phase3 S2/S3  
**Comments chain to:** `#642` + locks. Soft mainline Phase3 / **#490 HOLD**. Media wash → **#643**. Skill Creator → **#650**.

## Scope (this issue)

Phase3-S3 = **全文案 + 弹框** for the 19 NEW ids landed as skeletons in #640.

| In | Out |
|---|---|
| Production instructions / presets / inputs deepen for NEW19 | Soft-wash or near-original product art |
| Dialog data/schema parity per skill (Upload / notes / category fields as gold requires) | New skill ids; dropped-13 |
| Shared SkillRunDialog shell (Header → MediaGallery → optional PresetChips → FormFields → FooterCTA) | Homepage mount (S5) |
| Design L/R gate (card + dialog) before merge | Competitor CDN / verbatim copy under `src/` |
| Empty `examples`/`featured`/`cover` until #643 wash pins | Treating #643 wash as required to open this PR |

## NEW19 (hard lock)

`taobao-product` · `before-after` · `anim-2d` · `creator-identity` · `product-website` · `studio-model` · `youtube-channel-banner` · `ai-model` · `product-to-packaging` · `game-art` · `portrait-studio` · `premium-website` · `animated-poster` · `pose-fission` · `live-promo-decor` · `linkedin-banner` · `logo-animation` · `restaurant-website` · `clothing-swap`

Do **not** re-land dropped-13 (`app-listing-kit`, …). Upgrade `thumbnail` stays on #641 path (already merged via #657).

## Dialog parity rules

- Gold site = external Explore dual-column SkillRunDialog; **never** name that brand under `src/`.
- **Parity, not deepen:** right-column fields follow each skill's gold (Upload / notes / category). Do not invent required Title copy or Preset chips when gold has none.
- Left rail: production Examples (≥1, prefer ≈6) once #643 pins land; empty examples OK in S3 tip until wash.
- Shared IA: top → main visual → (optional) preset chips → inputs → primary CTA.

## Pack tips (optional)

May land as ecommerce / website / social·ads / motion sub-tips; keep one branch tip for review unless PM splits.

## AC (issue)

- [ ] 19 open SkillRunDialog; production-grade fields; no demo shrinkage
- [ ] No competitor CDN / verbatim; no gray placeholders as product art
- [ ] Per-skill card L/R + dialog L/R in PR body (design sign → test → tech merge)
- [ ] Tests: `tests/test_skills_phase3_642.py` green; no `Lovart`/`lovart` under `src/`

## Next concrete code steps

1. Per-skill field map from design L/R (which keep `P()` chips vs EFFECT_INPUTS-style Upload+notes).
2. Deepen instructions/locales where S1 skeleton is thin vs PRODUCT-LOCK rows.
3. After #643 wash: pin `cover` / `examples` / `featured` (same pattern as `cover643` / `ex643`).
4. Design L/R screenshots into `docs/design/642/78/lr/<id>/` then PR body embeds.
