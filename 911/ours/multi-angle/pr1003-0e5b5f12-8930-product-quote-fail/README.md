# #1003 product $0 quote-card FAIL shots (tip 0e5b5f12, 8930)

Product $0 acceptance on the default-agent path, 2026-11-17 Asia/Shanghai. Tip `0e5b5f1263e3c315b30f37dc2578b04b39ff023a`. Inquiry-card shots from this same tip are already pinned at `2e7efce2`. This set is the post-submit quote-card walk. Not a paid L/R, and it does not lift the `0f0e9328` effect HOLD.

- Input: `ma_subject_691.png` + 「商品详情页，纯白无缝背景」
- Product session (project `b211260f`): submitted aspect B `3:4 竖图`. A 确认费用 card appeared. There was no numbered 3×3 lineart preview before the quote. Chat also showed 「观察画面 · 失败」 (not a blocker).
- Live pending-card crops on `b211260f` were not kept: the card was dismissed (Escape) before a tight crop. After cancel the thread still shows the 3:4 answer, no lineart, the 14-credit quote line marked 已取消, and 「已取消，没有扣费 / 报价没有确认，不会扣费」 (`01`, `02`).
- The same preview had a second pending quote (project `7c0d5f78`, aspect card 已超时). Its live 确认费用 card used the same wording as the `b211260f` card before dismiss: 「生成图像 · Nano Banana Pro」「约 14 积分」, buttons 「取消」 and 「继续生成」 (`03`, `04`). That card was cancelled with 「取消」 (`05`).
- Both runs ended `quote_declined`. No generate started, no WaveSpeed image charge (credits used 0). Official LLM token rows for the cancelled turns are $0.

Only crops without account/balance chrome were pinned.
