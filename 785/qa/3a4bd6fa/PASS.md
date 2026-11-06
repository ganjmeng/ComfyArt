# QA PASS tip 3a4bd6fa

Independent Full-App (`/comfyart/`, Firefox zh-light) against **committed dist** on tip `3a4bd6fae6f3f211ea5ee2d85822f7c6de0ebced` (serve :8285 → wt784 dist = tip).

## Verdict
PASS this SHA only. Prior HOLD on `e160da32` (6676759885) remains valid — do not sign that tip.

## Checks
1. Dialog 7 RESULT commercials @ `d17ae7c9` 784/wash/product/examples/{01..07}: 美妆 red-lipstick model · 服装 yellow-check+denim+blue bag · 食品饮料 drink · 数码 earbuds/headphones · 家居 warm living room (not honey) · 户外 mountain bike (not lume) · 软件 office business person (not empty).
2. Cover 3×2 BR = MAREN pink lip-tube; featured still WASH_779 NODAL (`47bd9752` 779/wash/product/featured).
3. Dialog L/R uses real lovart.ai Product Commercial skill dialog LEFT (masked) — not #779 six-grid gold cover.
4. RIGHT frames are Full App committed dist (not local vite-only).
