# #687 paid list — recount under Angela's 23:00 rule (for the morning review)

Nothing here has been generated. All images are 1K, **$0.0378** each (google/nano-banana-2.1/edit).

**Rule applied:** platform and festival elements (双11, 天猫, 淘宝, 抖音, 京东, 618, plus their logos and badges) may stay exactly as on the gold. Only gold brand names and specific selling copy have to change.

**How the recount was done (free):** RapidOCR at 2x on the gold-vs-ours audit L/Rs (`docs/qa/687-audit/lr/*.png` @ 6fdfd01c) for packaging, meta-ads, marketing-campaign and interior, plus a by-eye check of the audit reason for every row. **None of the golds has a platform or festival element, so no row was listed because one was deleted, and nothing comes off the list.** Every row is there because of a gold brand name, composition or count gap, or a missing supplement. The one addition is youtube-channel-banner.

| # | slug | type | count | unit | subtotal | reason |
|---|------|------|------:|-----:|---------:|--------|
| 1 | packaging | re-wash (featured) | 8 | $0.0378 | $0.3024 | featured lifestyle multi-brand, count 5 vs 8 (cover is already fixed locally: every box and the card read BOTANICA LAB, fc1c2785) |
| 2 | meta-ads | re-wash | 4 | $0.0378 | $0.1512 | different layout family, no gold base |
| 3 | marketing-campaign | re-wash | 8 | $0.0378 | $0.3024 | gold has 8 multi-frame strips, ours has 4 single frames |
| 4 | interior | re-wash | 2 | $0.0378 | $0.0756 | different rooms, count 4 vs 2 |
| 5 | logo-material | supplement | 3 | $0.0378 | $0.1134 | not washed from the gold (4/3) |
| 6 | web-product | supplement | 5 | $0.0378 | $0.1890 | count 4 vs 9 |
| 7 | mobile-ui | supplement | 9 | $0.0378 | $0.3402 | count 4 vs 13 |
| 8 | youtube-channel-banner | re-wash (cover) **new** | 1 | $0.0378 | $0.0378 | still shows the gold copy "FAMILY FIRST"; cropping cannot fix a 4:3 cover |
|   | **total** | | **40** | | **$1.5120** | |

- **Retry cap:** at most 1 retry per image, so the worst case is 80 calls = **$3.0240**.
- **Not in this list:** the social + character remainder, character ex02–06 = 5 × $0.0378 = **$0.1890** (up to $0.3780 with one retry each). It runs under the #687 $0.50 cap (spent so far $0.3024) only after design PASSes ex01 rev2.
- **Tonight:** this list does not run. It is over the approved $0.50 (技术经理, 23:0x). Angela decides in the morning.

## 交接
- **Tip:** fix/687-local (see the commit that adds this file). assets/687-local = 240d6d8b. review-assets = df85d080 (has the 240d6d8b merge).
- **Done:** recount (40 images / $1.512, retry cap $3.024), the packaging cover fully relabelled, and product featured restored to 04 only.
- **Next:** Angela approves or trims the list. Then the paid run at 1K, and a PR once design and test pass the L/R images.
- **Spend:** $0 on this work.
- **Balance:** $43.86 (last known value, not re-queried).
