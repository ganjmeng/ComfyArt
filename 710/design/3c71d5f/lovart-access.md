# lovart.ai 可访问性结论（设计 / 2026-11-07，本机 macOS + DSH sandbox）

金标口径：只认国际站 **www.lovart.ai**（不用 lovart.art）。本文件记录「本机能不能抓 Lovart 实测证据」以及确切阻塞点。

## 结论（TL;DR）

**本机无法访问 www.lovart.ai：出口对该域名做 TLS SNI 定向阻断，与登录态无关。**
- 匿名访问：不可用（所有传输方式 TLS 握手被重置）。
- 本机 Chrome 已登录 Profile 1 的**副本**：不可用（session cookie 在 sandbox 内无法解密 + 网络依旧被阻断）。原 profile 未改动。
- 可替代但不能当金标：`www.lovart.art`（Lovart 2.0 中文站）本机可访问；第三方渲染服务可匿名截到 www.lovart.ai 首页（仅证明站点在线、页面无登录墙，**不能提供 DOM/computed style，也不能交互**）。
- 需要 Lead/Jingmeng 决策的通道问题见文末「需要什么」。

## 证据 1：DNS 被污染（4 个解析器 4 组答案）

| 解析器 | www.lovart.ai | lovart.ai |
|---|---|---|
| 系统默认 1.1.1.1 (UDP 53) | 199.59.149.231 / 210.56.51.192 | 199.16.156.103 |
| 8.8.8.8 | **157.240.20.18（Facebook 段）** | 93.179.102.140 |
| 119.29.29.29 (DNSPod) | 199.59.148.8 | 199.59.149.235 |
| 223.5.5.5 (AliDNS) | **104.18.7.126 / 104.18.6.126**（CNAME `www.lovart.ai.cdn.cloudflare.net`，真答案） | 47.252.7.74 |

`dscacheutil`/`nslookup` 还出现过 `2a03:2880:*:face:b00c:*`（Facebook IPv6）、`31.13.95.48`（Facebook）、`50.87.93.246`（Oracle/UnifiedLayer 停车页）等假地址 —— 典型 DNS 投毒。
→ 用 AliDNS 拿到的真实 Cloudflare 地址做后续测试。

## 证据 2：SNI 定向 TLS 重置（关键证据）

对真实 Cloudflare 边缘 IP `104.18.7.126:443` 做 TCP+TLS：

```
TCP connect 104.18.7.126:443                      -> OK
TLS  SNI = www.cloudflare.com                     -> TLSv1.3 OK（同一 IP 同一端口）
TLS  SNI = www.lovart.ai                          -> SSLEOFError: UNEXPECTED_EOF_WHILE_READING（握手被重置）
```

换 IPv6 真实 Cloudflare 地址（2606:4700::6812:77e / 6812:67e）同样：TCP 通、SNI=www.lovart.ai 时 EOF。
→ 阻断点是**出口按 Host/SNI 拦截**，不是 DNS 单点、不是 IP 封锁、不是 Cloudflare 侧问题；换 DNS / 换 IP / 换 v4·v6 都无效。

## 证据 3：所有传输方式实测（均为失败）

| 方式 | 命令/环境 | 结果 |
|---|---|---|
| curl 直连（系统 DNS，v4+v6） | `curl https://www.lovart.ai/` | err 28 timeout（20s） |
| curl 强制真实 IP | `--resolve www.lovart.ai:443:104.18.7.126` | err 35 `SSL_ERROR_SYSCALL` |
| curl 本地 HTTP 代理 :8080 | `-x http://127.0.0.1:8080` | timeout（同代理下 github=200、baidu=200，排除代理自身故障） |
| curl 本地 SOCKS5 :8080 | `--socks5-hostname 127.0.0.1:8080` | timeout |
| curl 本机 Chrome 旁的 :10011 | `-x http://127.0.0.1:10011` | timeout（github 200） |
| Playwright + Chrome 156 匿名 | `chromium.launch({channel:'chrome'})`，`goto` 25s | `TimeoutError ... navigating to https://www.lovart.ai/`；`net::ERR_TIMED_OUT` |
| **Chrome 已登录 Profile 1 副本** | 原 profile `cp -R` 到 `/tmp/team/design/chrome-copy`，`launchPersistentContext`，原 profile 只读未动 | `context.cookies()` 对 lovart.ai 返回 **0 条**（Chrome Safe Storage 需 Keychain 解密，sandbox 内不可用）；导航仍 `net::ERR_TIMED_OUT` |
| DSH `web_fetch` 工具 | `https://www.lovart.ai/` | `Error: web fetch failed: TypeError: fetch failed` |
| DNS-over-HTTPS | `https://1.1.1.1/dns-query`、`https://dns.google/resolve` | timeout |

失败截图：`/tmp/team/design/shots/profile-session-lovart-ai-error.png`（Chrome 带 Profile 副本导航 → 错误页）。

## 证据 4：本机 Chrome Profile 1 确实有 Lovart 登录态（但救不了）

用只读 SQLite 查 `~/Library/Application Support/Google/Chrome/Profile 1/Cookies`（副本查，非原文件写）：
- `.lovart.ai` **26** 条、`www.lovart.ai` **8** 条、`.www.lovart.ai` 2 条，过期时间 2027-11 量级（未过期）；
- 另有 `.lovart.art` 7 条、`open-lovart.vercel.app` 等。
→ 说明**账号登录态本来在**，但 (a) sandbox 内 Keychain 解密失败 → cookie 不可用；(b) 即使解密可用，出口阻断照样 100% 失败。**登录态不是本轮阻塞原因**，网络通道才是。

## 证据 5：外部对照（不是金标，只用于判断“站点是否活着”）

- 第三方渲染服务（thum.io，外部网络）匿名渲染 `https://www.lovart.ai/` 成功：站点正常、**首页匿名可见、未见登录墙**，标题 “Welcome to Lovart 2.0”，含 Tools / Explore / Quick Starts with Skills 等区块。截图：`/tmp/team/design/shots/thirdparty-thumio-lovart-ai.png`（**标注 NON-GOLD：第三方浏览器渲染，无 DOM/computed，不能当验收金标**）。
- `www.lovart.art`（Lovart 2.0 中文站）本机直接访问 200：截图 `/tmp/team/design/shots/profile-session-lovart-art.png`。界面结构同 Lovart 2.0（中文文案）。**按任务口径不作金标**，是否作“非金标参考”须 Lead 决定。
- 其他同域/相关站也许可探测：`lovart.art`→308→`www.lovart.art`=200（istio-envoy）。

## 结论对下一批卡的影响

1. **#710（技能弹框+追问卡）**：Gold **不缺**——`docs/qa/lovart-ui/` 在 sha `82176288` 有全套 7 张（见 lr-inventory.md）。缺的是：
   - “760px/16px 为像素估算，待 computed + DPR 核实后再交开发” → **必须**登录态 DOM/computed，本轮无法取得 → 建议 HOLD 该项或由 Jingmeng 给通道后补。
   - 若还要补新状态（如 05 选中态若现存图不够、或多语言/深色对齐），同样需通道。
2. **#687 motion**：仍 NEED-SHOT（cover/featured 金标）；本机无通道 → 只能沿用 review-assets 既有 Lovart 模态截图（`687/lovart-skill-detail/r1/lovart-03-motion-poster-modal.png`，1280×717）与 `docs/qa/687-fields/lr-motion-lovart-vs-ours-en-light.png`，新金标补不了。
3. **#725**：review-assets/docs 里未找到对应 Lovart 金标；需通道或由 Jingmeng 提供。
4. 本机**不再重启 Clash/VPN**（Clash 未运行、harness 的 7890 无监听；启动系统级 VPN 会影响其他并行成员且超出设计写入范围）。若 Lead 授权改网络，请明确指示。

## 需要 Lead 找 Jingmeng 要什么（按优先级）

1. **给本机一条能访问 www.lovart.ai 的通道**（VPN/Clash 节点/出口白名单任一）。有通道后我可在 ~10 分钟补：`#710` 的 computed style（弹框宽/按钮高/圆角/字号/间距/颜色，devtools getComputedStyle）、缺失状态 Gold、`#687 motion` cover/featured 对照、`#725` Gold。
2. 或**授权在 Jingmeng 自己机器/浏览器上跑我交付的抓取脚本**（我可以把 Playwright 脚本 + 状态清单写好，只需对方有登录态 Chrome）；产出放 review-assets。
3. 或**明确降级口径**：本轮只用 sha `82176288` 既有 Gold（#710 七件套）+ review-assets 既有 Gold；`#710` computed 项、`#687 motion` 新图、`#725` 挂 HOLD 到通道恢复。

## 证据文件清单（本地）

```
/tmp/team/design/shots/profile-session-lovart-ai-error.png     # 带登录 Profile 副本仍 ERR_TIMED_OUT
/tmp/team/design/shots/profile-session-lovart-art.png          # 中文站可达（非金标）
/tmp/team/design/shots/thirdparty-thumio-lovart-ai.png         # 第三方渲染 www.lovart.ai（NON-GOLD）
/tmp/team/design/lovart-access.md                              # 本文件
```
（上传 review-assets 的固定 sha 链接见文末更新 / Lead 消息。）

---

## 固定 sha 链接（review-assets，可直接引用）

- 本文档：https://raw.githubusercontent.com/ganjmeng/ComfyArt/10bcbbd255a60bf9b9452fcf463923fb17b14187/710/design/3c71d5f/lovart-access.md
- 可访问性证据图（sha `cd14149d0b2fdc72c79f770701ed4393ec1fcb51`）：
  - https://raw.githubusercontent.com/ganjmeng/ComfyArt/cd14149d0b2fdc72c79f770701ed4393ec1fcb51/710/design/3c71d5f/access/lovart-ai-blocked-chrome-profile-copy.png
  - https://raw.githubusercontent.com/ganjmeng/ComfyArt/cd14149d0b2fdc72c79f770701ed4393ec1fcb51/710/design/3c71d5f/access/lovart-ai-thirdparty-render-NON-GOLD.png
  - https://raw.githubusercontent.com/ganjmeng/ComfyArt/cd14149d0b2fdc72c79f770701ed4393ec1fcb51/710/design/3c71d5f/access/lovart-art-reachable-NON-GOLD.png
- 补抓脚本：https://raw.githubusercontent.com/ganjmeng/ComfyArt/10bcbbd255a60bf9b9452fcf463923fb17b14187/710/design/3c71d5f/capture-lovart.mjs
