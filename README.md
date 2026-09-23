# 知序 · 企业知识工作台

基于 Mac M4 的本地企业试点应用。提供 AI 工作台、文档知识库、历史会话和系统状态四个页面，界面资源、模型推理和企业资料处理均在本机。当前不依赖 NAS；新增手动联网搜索，云端模型仍关闭。

实施依据见[总计划书](mac_m4_local_first_ai_v1.md)，已验证与待完成项见[实施状态](docs/implementation-status.md)。这是可运行的企业试点版本，正式多设备生产部署仍需身份治理、HTTPS 和运维验收。

## 启动

需要 `uv`、Python 3.12～3.14，以及支持所选模型的原生 `llama-server`。

```sh
uv sync --locked
python3 scripts/download_model.py
python3 scripts/start_model.py --binary /absolute/path/to/llama-server
```

模型下载约 5.68 GB，锁定 revision 并校验 SHA256。安装下载需联网，普通聊天与知识库问答不会外发问题或资料。WEB 模式将当前输入的问题用于公开搜索，并访问结果网页。推理服务只监听 `127.0.0.1:8080`。

另开终端，仅首次初始化账号：

```sh
uv run python -m local_ai create-user owner --role admin --key-file data/owner.key
uv run python -m local_ai ingest --owner owner --visibility public
```

随后启动网页服务：

```sh
uv run python -m local_ai serve
```

打开 [本机工作台](http://127.0.0.1:9000/)，输入 `data/owner.key` 中的密钥。本工作区已有 owner 管理员和示例资料，直接启动即可，无需重复创建。现有旧版账号可以用 `set-role owner admin` 升级角色。

密钥文件只在本机保存，不应分享或提交。网页用密钥换取 8 小时 HttpOnly 会话 Cookie，写入请求带 CSRF 校验；不会把密钥写入 localStorage。账号停用后会话立即失效。服务为前台进程，Ctrl+C 停止，尚未配置开机自启。

## 工作台使用

1. 在「文档知识库」上传本机文件，默认仅自己可见；随后可预览片段、下载原件、调整共享范围或删除。
2. 在「AI 工作台」选择知识库问答，输入问题。回答逐步显示，可停止、复制和打开引用核对原文。
3. 完整回答后自动保存到当前账号的历史会话，可恢复继续提问或导出 Markdown。保存失败会提示重试，不会显示为已保存。
4. 「系统状态」显示模型就绪情况、请求队列和操作记录；点击刷新更新状态。

网页支持 PDF、DOCX、Markdown、TXT 和常见代码文本。PDF 必须有可提取文字，扫描件需要先做 OCR；加密 PDF 不支持。DOCX 普通表格提取为文字，不保证复杂版式或合并单元格还原。

限制：单文件 5 MB、每账号 200 份文档/100 MB 原件、PDF 150 页、提取正文 40 万字符；单次最多选 10 个文件，逐个处理。解析进程有时间限制。重名上传创建另一份文档，不覆盖原文件。原件与检索片段保存在本机 SQLite 内，NAS 不参与当前流程。

检索目前是中文字符/双字与英文标识符 BM25 基线，不是语义混合检索。引用列表展示提供给模型的证据，不能保证每条都被答案采用或论断正确。大语料性能、跨文档语义召回和精确 token 预算仍待优化。

## 联网搜索（M6）

当前工作区已安装并启用搜索，owner 可以在回答方式中选择「联网搜索」。直接在问题框输入要查询的内容并发送，无需重复填写搜索词。联网模式会明确提示当前问题用于公开搜索。本地 Qwen 依据搜索证据总结，来源可预览正文节选/摘要与日期，也可打开原站。

联网模式点击发送即授权当前问题外发；不附带企业资料或历史对话。服务端会去除常见提问修饰词并过滤明显无关结果。WEB 本地总结也从当前问题开始，不沿用历史。普通 AUTO/LOCAL/KNOWLEDGE 模式不会因为出现“最新”而自动联网。公开搜索词将通过本机 SearXNG 发给当前配置的 Bing；来源网页会收到读取请求。公开搜索词不是保密通道，请勿填入机密内容。

重启时另开终端运行搜索服务：

```sh
python3 scripts/start_search.py
```

新环境首次安装可选搜索依赖：

```sh
python3 scripts/install_search.py
```

安装在 `data/searxng` 与 `data/searxng-venv`，独立于 Gateway；源码固定 revision，依赖固定在 `config/search-requirements.lock`。启动只监听 `127.0.0.1:8888`，使用 Waitress，不需要 Docker。当前网络验证 Bing 可用；其他搜索引擎尚未启用。

`config/example.toml` 仍默认关闭；本工作区 `config/local.toml` 已按授权配置：

```toml
[policy]
allow_web_search = true
allow_cloud_inference = false
allow_private_context_export = false

[web]
searxng_url = "http://127.0.0.1:8888"
allowed_users = ["owner"]
```

新增成员须由管理员把账号 ID 加入白名单并重启 Gateway。要关闭搜索，将 `allow_web_search` 设为 false 并重启。只有“服务配置开启 + 当前账号在白名单 + 显式 WEB + 填写公开关键词”同时满足才发起搜索。

搜索与正文读取总预算 25 秒，最多 3 个来源；每页 1 MB/8 秒、最多 2 次重定向。仅访问验证过的公网 HTTP(S)，拒绝内网/回环、危险地址、凭证 URL 与压缩响应；失败正文降级为明确标记的搜索摘要。网页正文只取节选，发布日期可能未知；检索时间不能当作发布日期或最新性证明。搜索服务错误和空结果会明确提示，不会改走云端。

联网会话仍保存于本机；网页来源按账号保存 30 天的有效预览，过期后历史加载会过滤该引用。清理在下次该用户成功搜索时执行，不是后台物理删除任务。账号自己的已保存回答文字保留。

## 跟随系统代理与 VPN

外部搜索和网页读取现在自动读取 macOS 系统 HTTP/HTTPS/SOCKS 代理及例外设置。当前本机代理为 `127.0.0.1:7897`；地址从系统读取，没有写死到代码或配置。切换 VPN、节点或系统代理后，新请求会跟随变化，无需重启应用（设置缓存最多 1 秒）。TUN/系统 VPN 的出口由系统路由控制；浏览器仅使用插件时不属于系统代理。

搜索使用新连接，避免复用旧节点的连接。切换中的请求可能失败，手动重试即可。系统仍配置代理但代理服务停止时，不会偷偷直连。没有开启系统代理时，使用系统路由；这仍可能经过 TUN/VPN。

本地模型与本机服务之间保持直连。外部网页仍验证公网 IP、固定目标并校验原域名 TLS；因此无法保证代理按域名分流及远端 DNS 与浏览器完全相同。Fake-IP、PAC/WPAD、认证代理和浏览器独立代理尚未适配。VPN 节点不会自动开启云端模型或私有文档外发。

「系统状态 → 搜索网络」显示当前采用系统代理还是系统路由。当前代理完成真搜索与网页读取测试；实际切换多种 VPN 产品尚未逐一验收，切换逻辑通过模拟配置变更回归。

## 成员、权限和备份

```sh
uv run python -m local_ai create-user alice --group engineering --key-file data/alice.key
uv run python -m local_ai set-role alice member
uv run python -m local_ai disable-user alice
uv run python -m local_ai backup data/backup-unique-name.sqlite3
```

账号/组目前通过管理员本机 CLI 管理，没有网页成员管理或 SSO。组参数可重复。private 仅所有者可见；group 仅该组成员和所有者可见；public 是本服务所有已认证账号可见，只有管理员可从网页发布为 public。管理员角色不绕过其他人的私有资料权限。本机 CLI 是受信任的运维入口，须限制主机访问。

权限同时覆盖列表、搜索、片段和下载。撤销权限后，历史会话中的来源再次过滤；已经显示的答案文字和已下载文件无法撤回。会话属于当前账号，使用版本号避免多标签页静默覆盖。

SQLite backup API 备份包含文档原件、索引、会话、账号哈希及会话认证状态，应按敏感资料保管。恢复前先停 Gateway，在新路径验证备份，再修改配置指向恢复库；不要直接覆盖运行中的数据库。当前只完成自动化备份恢复回归，离机恢复、备份轮换和保留策略仍需部署时落实。

## 配置与目录入库

```sh
cp -n config/example.toml config/local.toml
uv run python -m local_ai --config config/local.toml serve
```

配置选择顺序为显式 `--config`、`LOCAL_AI_CONFIG`、存在的 `config/local.toml`，最后为示例配置。相对路径以项目根目录解析。网页上传不依赖 `knowledge.root`；该项仅控制可选目录扫描。目录扫描支持 UTF-8 `.md/.txt/.py/.c/.h/.cpp/.hpp/.rs/.yaml/.yml`，不扫描 PDF/DOCX。

```sh
uv run python -m local_ai --config config/local.toml ingest --owner owner --visibility private
uv run python -m local_ai --config config/local.toml ingest --owner owner --visibility private --watch-seconds 60
uv run python -m local_ai delete-document DOCUMENT_ID
```

目录配置和入库 ACL 应一一对应，不要对混有不同访问范围的父目录整体发布为 public。扫描更新失败或根目录不可用时保留旧索引；文件缺失不自动删除。目录入库不保存原件 BLOB，网页原件下载仅适用于上传文档。

## API

API 可继续使用 `Authorization: Bearer <key>`。网页 Cookie 的写请求另外需要 `X-CSRF-Token`，跨源写入被拒绝。

| 接口 | 用途 |
|---|---|
| `GET /health`、`GET /ready` | 进程健康、鉴权后模型就绪检查 |
| `GET /v1/models` | auto/local/knowledge 模式 |
| `POST /v1/chat/completions` | 文本聊天与 SSE 流式输出 |
| `POST /v1/knowledge/search`、`GET /v1/sources/{id}` | 带权限的检索和引用片段 |
| `POST /api/session`、`DELETE /api/session` | 网页登录与退出 |
| `GET /api/me`、`GET /api/workspace` | 当前身份与工作台概览 |
| `GET/POST /api/documents` | 列表、上传原始二进制（非 multipart） |
| `GET/PATCH/DELETE /api/documents/{id}` | 预览、共享权限和删除 |
| `GET /api/documents/{id}/download` | 下载上传的原件 |
| `GET /api/web-sources/{id}` | 当前账号的本地网页证据快照 |
| `/api/conversations`、`/api/conversations/{id}` | 当前账号会话列表与创建、读取、更新、删除 |
| `GET /api/status` | 模型、队列、审计事件 |

上传使用查询参数 `filename`、`visibility` 以及组共享时的 `workspace_id`；请求正文为文件字节。具体契约见 FastAPI 的 `/docs` 页面。

聊天仅实现兼容 API 的文本子集，支持 `model/messages/stream/max_tokens/temperature`，WEB 另需 `web_query`；不接受工具、图像、音频或结构化输出选项。来源为自定义 `sources` 扩展。直接调用聊天 API 不会自动保存网页会话。AUTO 使用保守关键词规则，可能误判；显式 KNOWLEDGE 强制检索，最新信息在未联网时说明无法核实。

## 开发与验证

前端资源已放入 `local_ai/static/vendor`，运行服务不需要 Node 或 CDN。更新依赖后重新生成：

```sh
npm ci
npm run vendor
uv run pytest -q
uv run ruff check local_ai scripts tests
uv run ruff format --check local_ai scripts tests
node --check local_ai/static/app.js
npx prettier --check local_ai/static/app.js local_ai/static/app.css local_ai/static/index.html scripts/vendor-ui.mjs
```

自动测试使用模拟推理后端，另含真实 HTTP socket 的取消/断连测试。真实模型与浏览器闭环结果在实施状态中分别记录。

## 部署边界

默认 Gateway 仅监听 `127.0.0.1:9000`；WEB 受显式配置与账号白名单约束，CLOUD 和私有上下文外发仍不支持开启。模型地址只允许回环 IP，禁用代理环境继承和重定向。

当前单 Gateway worker、生成并发 2、等待队列 6、每用户在途 1。不要通过直接增加 worker 扩容。正式企业多设备部署需完成 HTTPS/可信代理配置、账号生命周期、解析进程权限和内存隔离、监控告警、备份恢复及持续负载验收。详见总计划书，当前不直接开放公网。

### 正确打开工作台

在浏览器访问 http://127.0.0.1:9000/，不要把 HTML 源文件当成独立网页使用。直接打开 `local_ai/static/index.html` 时，新增入口脚本会尝试跳转到默认本机服务；服务必须已启动。若浏览器限制 file 页面或禁用脚本，请直接打开上述地址。自定义端口请使用实际服务地址。

### 一键启动（macOS）

完成安装后，双击项目根目录的 `启动知序.command`。它依次检查本地模型、按配置开启的搜索服务和工作台，等待就绪后打开浏览器。关闭启动窗口不会停止已启动服务；重复打开会复用就绪服务。启动失败会显示对应日志路径，不会自动下载模型或切换云端。

```sh
./启动知序.command
.venv/bin/python scripts/start_workspace.py --status
.venv/bin/python scripts/start_workspace.py --no-open
```

首次安装在 `config/launcher.local.json` 设置 `model_binary` 为 llama-server 的绝对路径，或设置 `LLAMA_SERVER_BIN` / 传入 `--model-binary`。当前机器已写入本机路径，该配置不纳入版本管理。Gateway 环境 `.venv`、模型文件和已启用的 SearXNG 必须预先安装；关闭 Web 时不会启动 SearXNG。

一键启动仅适配默认回环端口 8080/8888/9000；自定义监听配置继续使用分项启动命令。若端口被占用但健康检查未通过，启动器会停止启动流程并提示排查，不会杀死占用者。单项启动超时只停止它新建的进程，其他已经就绪的服务保留。此功能不是开机自启或崩溃自动重启，launchd 后续实施。

### 生成前 Token 预算

当前及示例配置在 `[server]` 启用 `token_budget_enabled = true`。Gateway 使用本机 llama.cpp 的真实聊天计数接口检查完整提示（包含系统提示、历史和参考资料），加上回答上限和 32-token 余量，不能超过模型每槽上下文容量。超限提示缩短问题或开启新对话，不会静默删掉历史；计数失败不启动生成。系统状态可查看此检查是否启用。

成功生成的响应头包含 `X-Local-AI-Prompt-Tokens` 和 `X-Local-AI-Context-Tokens`。该适配依赖当前锁定 llama.cpp 的 `/props` 与 `/v1/chat/completions/input_tokens`，切换其他后端需重新适配验收，不能将字符数当作精确 tokens。

### 备份与恢复演练

双击项目根目录 `备份知序.command`，会在 `data/backups/` 下创建一个独立备份包。已有备份不会被删除。数据库通过 SQLite 在线备份 API 复制，不直接复制正在写入的主库/WAL 文件；完成后检查 SHA256、SQLite 完整性、外键和记录数量。

```sh
# 目标的父目录需已存在，目标目录必须不存在
.venv/bin/python -m local_ai snapshot data/my-backup
.venv/bin/python -m local_ai verify-backup data/my-backup
.venv/bin/python -m local_ai restore-backup data/my-backup data/my-restore
```

恢复副本位于 `data/my-restore/state.sqlite3`，旁边有恢复报告。恢复不会停止服务、替换在线库或自动采用备份中的联网配置；旧网页登录会话会清除，账号密钥哈希与权限保留。正式切换前，须先核对恢复点后的账号停用/权限变更，避免旧权限随历史备份重新生效。当前工具只支持本项目可信备份，不运行备份中的脚本。

备份包含上传原件、知识片段、会话与账号认证状态，目录/文件分别为 0700/0600，但并未加密；SHA256 用于发现损坏，不提供签名认证。`owner.key` 等原始访问密钥、模型权重和目录入库源文件不复制进包，须分别保管（目录入库的知识片段仍在数据库中）。配置快照和模型锁定信息用于人工核对，不自动应用。定时备份和自动保留轮换已启用，详见下方；加密和离机灾备后续实施。

### 已启用的自动备份

本机已安装当前用户 LaunchAgent `com.zhixu.workspace.backup`。登录时和每小时检查一次，距离上次成功备份满24小时则创建新备份；失败在下一次检查时重试，已有快照损坏/缺失会补做。与 Codex 或浏览器是否打开无关，需要 macOS 当前用户已登录且机器处于运行状态。关机、退出登录和休眠期间不执行；再次登录会检查到期状态，不修改睡眠设置。

管理员在工作台「系统状态 → 最近自动备份」查看结果；超过25小时无成功记录显示逾期。日志为 `data/auto-backup.log`，状态为 `data/auto-backup-status.json`。自动备份按下方保留策略清理；手动及无法确认来源的旧备份保留。尚未提供外部通知或离机灾备。

```sh
.venv/bin/python scripts/manage_auto_backup.py status
# 重新安装/更换项目路径后安装
.venv/bin/python scripts/manage_auto_backup.py install
# 停用定时任务（保留所有已有备份）
.venv/bin/python scripts/manage_auto_backup.py remove
```

项目移动后需从旧路径停用任务，再从新路径安装；安装器不会覆盖属于其他路径的同名任务。

### 自动删除旧备份（已启用）

每次自动备份成功且校验通过后执行清理。按 UTC 日期保留近7天每天最新一份，以及近28天每个滚动7天区间最新一份；重叠恢复点只保留一份，最新成功备份始终保护。同日重复自动备份可被清理。

只删除本项目新生成、带 `origin=automatic` 标记、规范命名且校验通过的备份目录。手动备份、旧版没有标记的包、损坏包、符号链接及异常日期均不自动删除。这些例外可能继续占用空间；清理不是按磁盘压力强制删除。状态页显示本次清理数量/异常。

```sh
# 立即创建并校验一份新自动备份，成功后执行上述清理策略
.venv/bin/python scripts/auto_backup.py --force
```

### 网页成员管理

管理员在「系统状态 → 团队成员」管理现有账号，可修改角色、所属组（英文逗号分隔）及启用状态。组名使用1～64位字母、数字、下划线或短横线。点击保存会提示确认权限变化，修改后该成员需重新登录；停用期间原密钥不能登录，重新启用也不会复活旧网页登录会话。启用恢复后原有有效密钥仍可使用。

普通成员不能查看或修改成员列表；管理员身份不会自动获得他人的私有文档权限，也不会自动加入联网搜索白名单。界面不显示访问密钥，当前账号的管理行只读以避免误锁定。网页新增账号、邀请与密钥轮换后续实现，现阶段新增账号继续使用本机 CLI。

### 本机轮换访问密钥

在项目目录执行（将 `MEMBER_ID` 替换为已有启用账号）：

```sh
uv run python -m local_ai rotate-key MEMBER_ID --key-file data/member-replacement.key
```

指定自定义配置时，把 `--config 配置路径` 放在 `rotate-key` 前。输出文件必须不存在，权限为 0600；命令只输出保存路径。成功后该账号所有旧密钥和网页登录会话立即失效，使用新文件中的密钥重新登录。所属组、文档和会话历史保留。网页暂不提供轮换入口。

### 云端接入准备（尚未启用推理）

用户已澄清需要远程访问工作台，未授权云模型 API。此前增加的准备工具未启用，独立模板为 `config/cloud.example.toml`。将副本保存为 `config/cloud.local.toml`，填写服务商、模型、接口、账号白名单及同一币种的价格和每日预算。密钥通过本机独立 0600 文件提供，不在聊天、配置正文或日志中填写。

```sh
uv run python -m local_ai cloud-check config/cloud.local.toml
```

此命令只做离线检查，不联网、不启用云端、不检查余额，也不执行费用限额。地址检查不含 DNS 验证。尚待服务商适配和真实调用验收，不能直接把现有 `allow_cloud_inference` 改为 true：Gateway 当前仍会拒绝未实现的云端策略。历史与文档外发范围需单独确认；当前准备模板仅支持本次问题。

### 通过互联网访问工作台

本项目已增加 HTTPS 代理适配和公网域名校验，实际公网入口尚未部署。模型与知识库继续运行在 Mac，无需云模型 API Key。配置、入口选择与验收限制见 [远程部署说明](docs/remote-access.md)。
