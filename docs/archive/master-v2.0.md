# Mac M4 本地优先 AI 系统：总计划书

版本：v2.0 · 2026-09-13。本文是实施、验收和范围调整的总依据。原始方案归档于 `docs/archive/mac_m4_local_first_ai_v1.original.md`，实际进度见 `docs/implementation-status.md`。计划能力不代表已经实现。

## 1. 目标与用户确认

硬件：Mac mini M4、32GB。NAS 尚未挂载，先使用项目内示例资料验证。用户已确认：默认全部本地，联网和云端后续手动开启。

首个可用交付为本地聊天、带用户权限的资料问答、来源引用、可靠排队。随后增加语义混合检索、Open WebUI、多设备、联网和受策略限制的云端回退。模型和后端可替换，但须适配和回归测试。

不做大规模并发、Agent Swarm、训练、语音视频、复杂长期记忆或 Kubernetes。不以模型自评分或检索相关性作为答案正确性保证。

## 2. 架构

```text
网页 / Open WebUI / API
          ↓
Gateway：认证 → 数据外发策略 → 预算 → 排队与取消
          ↓
规则路由：资料意图 / 实时性 / 证据可用性
       ┌──┴───────────────┐
       ↓                 ↓（后续手动启用）
带 ACL 的知识检索        Web 搜索与正文抓取
       └──┬───────────────┘
          ↓
证据与引用编号 → 本地模型 → 流式回答
          ↓（仅有授权、资料可外发且尚未输出时）
可选云模型

NAS 原文 → 扫描 → 解析 → 新版本索引 → 校验发布
Mac SSD：模型、SQLite 状态、Qdrant 活跃索引
NAS：原始资料与备份
```

Gateway 是身份、路由和权限的唯一执行点。不同时开启两套独立的 WebUI/Gateway RAG。

## 3. 技术选型

| 模块 | 选择 | 约束 |
|---|---|---|
| 生成 | Qwen3.5-9B GGUF Q4_K_M 候选 | 固定仓库 revision、文件 SHA256、聊天模板 |
| 推理 | macOS 原生 llama.cpp / Metal | 固定版本、回环监听；不假定 Docker 支持 Metal |
| Gateway | Python / FastAPI / HTTPX | 单 worker；流式、超时、取消贯穿请求 |
| 状态库 | Mac SSD 上的 SQLite WAL | 用户、Key 哈希、ACL、索引版本、失败任务 |
| 初始检索 | 本地 BM25 关键词基线 | 明确不等于语义检索 |
| 目标检索 | Qdrant 稠密 + 稀疏检索，RRF | 两路召回前过滤 ACL；版本可追踪 |
| Embedding | Qwen3-Embedding-0.6B | 验证 instruction、pooling、维度及归一化 |
| Reranker | Qwen3-Reranker-0.6B 候选 | 验证 yes/no logits 打分，不当普通聊天模型使用 |
| 前端 | 验证页，随后 Open WebUI | 身份可信转发；不因共用 Key 丢失用户身份 |
| Web | SearXNG | 默认关闭；JSON 显式开启、空结果可解释 |
| Cloud | 单服务商适配器起步 | 默认关闭，费用与私有资料外发独立限制 |

聊天 API 兼容不能保证工具调用、Embedding、Reranker、tokenizer 及结构化输出完全兼容。

## 4. 数据外发边界

```text
allow_web_search = false
allow_cloud_inference = false
allow_private_context_export = false
```

有效权限 = 服务配置 ∩ 用户权限 ∩ 请求模式。三个外发开关独立，排队、失败、重试不能越界。LOCAL 永不外发；查询搜索引擎也算外发。不能将私有问题、检索片段、历史对话原样送往外部服务。

安装时下载模型和依赖不属于运行时问题外发。运行时本地后端默认只允许回环地址。未实现或未启用的 WEB/CLOUD 返回明确错误，不假装已经联网。切换 CLOUD 不自动允许导出私有上下文。

## 5. 用户与权限

API Key 只存哈希、支持停用。用户和组来自服务端配置/数据库，禁止信任客户端 owner_id、workspace_id、角色请求头。接入 Open WebUI 时验证签名身份或使用独立凭证；一个共享上游 Key 不能区分终端用户。

```text
owner_id = 当前用户
OR (visibility = group AND workspace_id IN 用户所属组)
OR visibility = public
```

private 文档不会因 workspace_id 相同而向组公开。public 表示本服务已认证用户可见。多组织隔离暂不宣称支持；后续需在外层追加 tenant_id 边界。

ACL 同时用于关键词、向量、来源预览、下载和缓存。缓存键包含权限范围与版本。入库由管理员本地命令执行，不对普通聊天开放。日志不记录密钥、原文或完整问答。

## 6. 模式与路由

| 模式 | 行为 |
|---|---|
| AUTO | 在已启用能力内按规则路由；私有资料缺失时说明或澄清 |
| LOCAL | 本地聊天/本地资料可用，全部外发禁止 |
| KNOWLEDGE | 强制检索；无证据时不以模型记忆冒充资料 |
| WEB | 显式搜索；未授权/未实现则报错 |
| CLOUD | 显式云模型；仍检查外发政策 |

先检查模式与权限，再判断资料意图和实时性，执行允许的检索，最后回答/补充检索/澄清。最新问题在联网关闭时说明无法核实。NAS 检索不到不等于互联网能补齐私有事实。

不直接相加 Vector Score、BM25、Reranker 等分数，不使用未经标注数据校准的 0.78/0.55 阈值。先收集 50～100 个真实问题，再评估规则误判、分类器及阈值。

## 7. 文档索引与检索

先支持 UTF-8 Markdown/TXT/文本代码，再支持文本 PDF/DOCX，最后做 OCR。解析失败记录状态；扫描件不能以空文本冒充成功。

按标题、段落、代码块和表格边界切块。目标 500～800 tokens、重叠 80～120 tokens；接入真实 tokenizer 后严格执行。初始若用字符预算，必须命名 chars，不伪称 tokens。超长结构块允许拆分但保留位置。来源保留标题、相对路径及页码/块号，不暴露绝对 NAS 路径。

版本元数据：document_id、version、chunk_id、owner_id、workspace_id、visibility、SHA256、解析器版本、切块版本、Embedding 版本。处理版本和 ACL 变化也要更新，不能只看文件哈希。

```text
成功扫描 → 解析新版本 → 写入全部索引 → 校验 → 原子发布 → 清理旧版本
```

失败保留旧索引。SQLite/Qdrant 不能假设跨库事务，需 staging + active_version 和恢复任务。NAS 断连不是删除；默认保留缺失项，只有确认挂载与扫描完整后才显式删除。周期扫描不只依赖网络文件事件。拒绝逃逸根目录的符号链接，限制文件大小与入库并发。

目标检索：稠密 20 + 关键词/稀疏 20 → RRF → 去重 → 可选 Reranker → 3～5 片段。中文使用分词或子词，保留型号和函数名完整符号。ACL 在召回前生效。结果有上下文预算与来源多样性。文档内容是不可信证据，不允许改变策略或执行工具。

## 8. 队列、预算与流式

初始生成并发 2、等待队列 6、每用户在途 1、排队超时 30 秒，实测后调整。后端槽位与 Gateway 一致；DEEP 后续并发 1；入库低优先级。

FAST 最多输出 512 tokens，NORMAL 默认 1024、上限 2048。限制输入/历史/检索总量，真实后端 tokenizer 做最终检查。连续批处理不保证双用户仍有单用户速度。

权限、检索和预算在输出前检查。槽位持有至流式结束；客户端断连关闭上游并释放资源。已经输出后不自动换模型重播。普通模式不做阻塞首字的完整后置验证；DEEP 可选择独立复核，引用存在不代表论断已验证。

提供 /health、/ready、/v1/models、/v1/chat/completions 及鉴权检索/来源接口。认证、队列满、功能关闭、上游不可用使用明确错误；流中异常使用 SSE error。

## 9. Web / Cloud 后续要求

Web：检查查询外发 → 搜索 → 抓取有限正文 → 清洗 → 来源日期 → 本地总结。拒绝抓取回环、内网、link-local、非 HTTP(S) 和重定向至这些地址，限制大小/时间/次数，防止 SSRF。仅取得摘要须明确标识。网页指令不能改变系统行为。

Cloud：固定服务端地址、单请求 token 上限、每日费用预算、有限重试。仅在授权且数据可外发、尚未输出时回退。余额不足和连接错误可观察，不无限重试。

## 10. 验收

不承诺尚未实测的 15～25 token/s、首字 1～5 秒。记录硬件、模型 SHA256、后端版本和上下文。1/2 并发 × 短/长输入 × 入库空闲/进行中，记录排队、检索、首字、总耗时、每请求速度、内存、swap、错误率；少量样本不称稳定 p95。

50～100 个标注问题覆盖普通聊天、型号、语义、跨文档、资料缺失、最新信息、私有/组权限与恶意文档。评估 Recall@20、引用存在性及人工支持度、无证据拒答、误联网率。权限回归要求零越权，LOCAL 运行时外部调用为零。

## 11. 里程碑

| 阶段 | 交付 | 通过条件 |
|---|---|---|
| M0 | 总计划、依赖锁、配置与运行说明 | 本地默认；计划与实际状态分开 |
| M1 | 模型、llama.cpp、Gateway | 真模型流式/非流式；记录版本与速度 |
| M2 | 用户、ACL、策略、队列 | 隔离、超时、取消、模式限制测试 |
| M3 | NAS 文本入库、关键词基线、引用 | 更新失败保留旧索引；真实 NAS 挂载后验收 |
| M4 | Embedding/Qdrant/RRF/Reranker | 同一标注集优于基线；版本恢复通过 |
| M5 | Open WebUI、多设备和运维 | 可信身份、客户端实测、重启和备份恢复 |
| M6 | Web | 最新问题有来源；外发和抓取限制测试 |
| M7 | Cloud/DEEP | 隐私、费用、超时、回退测试 |

M1～M3 是首个可用交付。mock 不能替代真实模型性能、NAS 或多设备验收。未完成项必须留在状态文档中。

## 12. 部署和恢复

模型服务原生运行并只监听回环，Gateway 默认 127.0.0.1:9000。局域网需鉴权和 HTTPS/可信私网；模型/Qdrant 不对客户端开放。SQLite 和进程内队列起步仅允许一个 Gateway worker。

不自动改系统睡眠、防火墙。后续 launchd 管理进程，处理 NAS 重连。SQLite 使用 backup API、Qdrant 使用 snapshot，备份包含版本配置及 ACL；密钥单独管理，至少一次恢复演练。活跃数据库不放 SMB/NFS。

## 13. 官方依据（2026-09-13 查阅）

- [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
- [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)、[Reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- [Qdrant 混合检索](https://qdrant.tech/documentation/search/hybrid-queries/)、[存储要求](https://qdrant.tech/documentation/installation/)
- [Open WebUI 身份转发](https://docs.openwebui.com/reference/env-configuration/)
- [SearXNG 配置](https://docs.searxng.org/admin/settings/settings_search.html)
