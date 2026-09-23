# 远程访问知序（M5，公网入口已连通）

用户需要从其他设备通过互联网访问工作台。模型、知识库、会话和备份仍在 Mac；这不需要云模型 API Key，不启用 Cloud 推理。

目标链路：远程浏览器 → HTTPS 域名/受控入口 → Mac 上的 Gateway 9000 → 本地模型 8080。只发布工作台，不发布模型、搜索服务、数据库、备份目录或密钥文件。Mac 必须在线且服务运行；关机和休眠会影响可用性。

## 已实现的应用配置

在 `config/local.toml` 的现有 `[server]` 节增加（域名须替换为真实值）：

```toml
public_origin = "https://ai.example.com"
trusted_proxy_ips = "127.0.0.1"
```

Gateway 继续监听 `127.0.0.1:9000`。使用项目 CLI 启动，它明确将可信代理 IP 传给 Uvicorn，不使用环境变量扩大信任；禁止 `*`。本机工作台和启动器健康检查继续可用。配置公网域名后，其他 Host 被拒绝；公网域名请求必须由可信代理确认为 HTTPS。反向代理须保留原始 Host，覆盖 X-Forwarded-Proto，而不是转发用户伪造的头。原有账号、Cookie、CSRF 和资料 ACL 继续执行，HTTPS 登录 Cookie 使用 Secure。

## 入口方案待资源确认

- 已有域名、希望不开放路由器端口：可配置正式命名 Cloudflare Tunnel。模板见 `deploy/cloudflared.example.yml`，须先创建自己的隧道、凭据和 DNS；模板已通过 cloudflared 2026.6.1 的 ingress validate 和域名规则匹配检查；尚未通过真实网络验收。
- 已有云服务器：可使用 HTTPS 反向代理，通过受控私网链路连接 Mac；待确认服务器和域名后生成对应配置，不能把本机回环地址直接当作云服务器可达地址。
- 暂无资源：先明确需要公开网址还是仅企业成员私网访问，再确定入口。尚未创建任何外部账号、购买服务或公布临时链接。

Cloudflare 免费临时 Quick Tunnel 不支持本应用需要的 SSE，不能作为聊天交付入口。正式入口需验证登录、逐字输出、取消、上传下载、会话恢复和异网设备访问。TLS 终止方会经手浏览器请求和回答，不能把云端中转表述为完全没有数据经过第三方。

## 验收状态

8 项新增自动测试覆盖可信/非可信代理、HTTPS Cookie、同源与跨源操作、Host 校验、回环入口和配置拒绝。它们是本地模拟测试，不是证书、隧道可用性或真实多设备验收。仍需公网资源、登录限流/入口访问控制、服务守护、异网验证和长期可用性评估。

官方依据：
- https://www.uvicorn.org/settings/
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
- https://developers.cloudflare.com/tunnel/features/locally-managed-tunnels/configuration-file/

2026-09-22：用户确认仅有域名。已安装本机连接器，尚未登录 Cloudflare、创建隧道、变更 DNS 或启动公网服务。后续需要目标子域名及 DNS 托管平台信息；如需变更域名托管，先核对保留现有网站和邮件记录。

实际入口：https://zhixingmoyun.com/。已通过本机系统代理验证真实HTTPS、静态资源、登录/注销、Secure Cookie、CSRF和本地模型SSE回答。独立异网设备与长期验收待完成；正式public_origin已设为https://zhixingmoyun.com，可信代理仅127.0.0.1；已验证未知域名与公网明文请求被拒绝。原有模板中的ai子域名仅为此前提案，不是当前入口。

网页登录限制：同一来源60秒最多10次，超限429并提示重试时间。共享公网出口共享配额；单进程内存状态重启清零。直接Bearer API鉴权与边缘攻击防护仍待补充。
