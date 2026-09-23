# 跟随浏览器系统网络：计划核对

## 开工前 · 2026-09-14

已阅读 AGENTS.md、总计划 v2.2、实施状态。用户要求联网搜索采用与浏览器一样的网络模式。本轮对应 M6 的联网传输，调整 §9 的“不继承系统代理”：读取 macOS 系统代理，搜索引擎及网页读取跟随系统 HTTP/HTTPS/SOCKS 设置，保留 §4 的显式公开查询与本地数据边界，以及 §9 的公网检查/固定目标地址/TLS 校验。

本机检测到系统 HTTP/HTTPS/SOCKS 代理为 127.0.0.1:7897，未启用 PAC。只读取设置，不修改 VPN、系统网络、浏览器或代理软件。浏览器插件、自定义浏览器代理、PAC 和认证代理不在当前已确认配置中，不能宣称完全模拟浏览器网络栈。

## 完工后 · 2026-09-14

再次核对总计划 v2.3 的 §4/8/9/15 与实际代码和运行记录：

| 要求 | 实现与验收 |
|---|---|
| 跟随当前系统代理/VPN | 按请求读取 scutil 系统 HTTP/HTTPS/SOCKS 与例外配置，缓存最多 1 秒；不写死代理端口。配置变化模拟测试通过 |
| VPN 节点变化后不沿用旧连接 | 搜索设置 FRESH_CONNECT、FORBID_REUSE、DNS_CACHE_TIMEOUT=0；网页每次使用独立连接。回归断言通过；实际切换 VPN 产品未逐一验收 |
| 搜索与网页两条链路 | 当前系统代理下真搜索+网页读取+Qwen 回答成功，HTTP 200，约 13.37 秒，结束 active=0/waiting=0；见 system-network-runtime-validation.json |
| 地区变化 | 修复 Bing 代理出口地区重定向引起的空正文解析；改用通用入口并验证最多 3 次 Bing 域内 HTTPS 重定向 |
| 仍保护本地数据 | 回环服务始终直连，仅显式 WEB 的公开查询外发；云端和私有上下文外发未启用 |
| 网页安全边界 | 代理读取保留公网 DNS、固定 IP、原域名 TLS、字节限额与取消；代理失效不改走直连 |
| 状态可见 | 系统状态新增搜索网络，服务接口返回“跟随系统代理”或系统路由状态 |
| 回归 | 99 项测试通过（本轮新增 18 项）；Ruff、格式、Node、Prettier、锁定依赖同步通过 |

当前代理实测通过；没有修改用户的 VPN、网络或代理配置。系统 VPN/TUN 的实际出口由 macOS 路由决定，不读取 VPN 软件私有配置。不保证浏览器独立插件、PAC/WPAD、认证代理、Fake-IP 及代理按域名规则与本系统完全一致；正文仍固定公网 IP，不为兼容代理而放开 SSRF 边界。切换中的请求可能失败，需要重试，不自动重播。

## 计划仍未完成

M1/M2 的精确 token 预算与长时容量矩阵；M3 的 OCR/复杂文档；M4 的语义混合检索与标注评估；M5 的 SSO、网页成员管理、HTTPS 多设备、开机启动、监控与恢复演练；M6 的长期网络稳定性、不同 VPN/PAC 等兼容性验收；M7 的 Cloud/费用/DEEP。NAS 按用户要求暂缓。

网络适配实现参考 [SearXNG outgoing 配置](https://docs.searxng.org/admin/settings/settings_outgoing.html) 与 [libcurl CONNECT_TO](https://curl.se/libcurl/c/CURLOPT_CONNECT_TO.html)；原源码固定版本不变，适配层位于项目 scripts/search_runtime.py。

