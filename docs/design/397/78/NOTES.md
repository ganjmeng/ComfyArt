# #397 → #78 visual review

All "after" shots are harness screenshots (real Confirm / KeySettings chrome + app CSS). Mock only — no WaveSpeed, no paid calls.

| Surface | after (this PR) | Lovart CN |
|---|---|---|
| Plan quote card (#235) | after/plan-confirm-{zh,en}-{light,dark}.png | CN 无对照 (Lovart uses credits; no paired quote-card crop in review-assets) |
| Cloud confirm (`jobs.confirmCost`) | after/cloud-{zh,en}-{light,dark}.png | CN 无对照 |
| Settings confirm-line | after/settings-{zh,en}-{light,dark}.png | CN 无对照 |

Rules checked in the same pytest runs (`tests/test_plan_quote_card_235.py`, `tests/test_credits_shots_397.py`):
- No `$` in the card text
- zh shows `积分`, en shows `credits`
- Settings input is integer credits (`data-testid=ws-confirm-credits`)

Regenerate:
```
PLAN235_SHOTS=docs/design/397/78/after pytest tests/test_plan_quote_card_235.py
CREDITS397_SHOTS=docs/design/397/78/after pytest tests/test_credits_shots_397.py
```
