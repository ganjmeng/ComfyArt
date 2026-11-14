# #968 plan-quote card copy — full-app mock shots

Real Full App (native chat + real `ChatInlineConfirm` + app CSS, 1600x1000 light), scripted provider + local mock
WaveSpeed. **No key, no network, no paid call, $0.** No user key appears in the shots.

- `before/` = PR #970 first head `cea304781564bf1ced978d8495762aa3459cfb4c` (the HOLD revision).
- `after/`  = `4d3e350c43b5dd7c4888b6ed69324976cfcd7c0c` (the HOLD fix).
- scenarios: `healthy` = #959 discounted rows $0.1035 + $0.117x3; `fallback` = first row on the
  undiscounted list price $0.115, rest $0.117; `unpriced` = one unknown price; `partial` = one known
  $0.02 + one unknown. zh/en each.
- before healthy total 47 (charge 46), before unpriced shows 「约 积分 0」; after healthy 46 (rows sum 46),
  after unpriced shows 「未定价」 with no amount.
- copy change under design review (zh/en) is listed in PR #970 comment; this branch only stores the shots.
