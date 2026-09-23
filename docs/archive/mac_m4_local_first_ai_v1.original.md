# Mac M4 本地优先 AI 系统：第一版实施方案

## 1. 项目目标

在一台 **Mac M4 32GB** 上部署本地 Qwen 模型，以 NAS 作为主要资料与数据存储中心，构建一套“本地优先、必要时联网、必要时调用云端模型”的 AI 系统。

第一版目标不是追求大规模并发，而是实现一个稳定、可扩展、可多用户访问的基础平台。

最终希望达到：

- 用户可以直接向系统提问；
- 系统自动判断问题是否需要检索本地知识库；
- 优先使用 NAS 中的本地资料；
- 当本地资料不足、置信度低或问题需要最新信息时，自动联网搜索；
- 必要时可调用云端 API；
- 多台 Windows / macOS / Ubuntu 电脑可以统一访问；
- 多用户可以同时使用，但通过队列和并发限制保护 Mac 性能；
- 后续可以无缝替换本地模型或推理后端，而不重写整个系统。

---

# 2. 第一版最终架构

```text
Windows / Ubuntu / Mac / 手机
            │
            ▼
      Open WebUI / API
            │
            ▼
       AI Gateway
            │
   ┌────────┼─────────┐
   │        │         │
 Auth     Queue     Router
   │        │         │
   └────────┼─────────┘
            │
            ▼
      Intent Analysis
            │
   ┌────────┼───────────┐
   │        │           │
 General   RAG         Fresh
   │        │           │
   │        │        Web Search
   │        │           │
   └────────┼───────────┘
            │
            ▼
        Local Qwen
            │
     llama.cpp / Metal
            │
            ▼
       Answer Verifier
            │
     ┌──────┴──────┐
     │             │
   Good          Weak
     │             │
     ▼             ▼
  Return      Cloud API
```

---

# 3. 第一版技术选型

## 3.1 本地大模型

推荐：

```text
Qwen 9B 级模型
4bit 量化
GGUF
```

优先使用 9B 左右模型，而不是 27B 级模型。

原因：

- Mac M4 32GB 可以比较轻松运行；
- 给系统、KV Cache、RAG、Embedding、Reranker 留出足够内存；
- 更适合长时间常驻服务；
- 多用户时比大模型更容易维持稳定体验；
- 后续可通过 RAG 和联网搜索弥补模型参数规模不足。

---

# 4. 推理后端

第一版推荐：

```text
llama.cpp
```

原因：

- 对 Apple Silicon / Metal 支持成熟；
- 支持 GGUF；
- 支持 4bit / 5bit / 8bit 等多种量化；
- 内存利用灵活；
- 自带 OpenAI-compatible API；
- 支持多请求和 continuous batching；
- 很适合低并发到小规模多用户场景。

第一版不把系统写死在 llama.cpp。

所有上层服务统一通过：

```text
OpenAI-compatible API
```

访问模型。

以后可以替换为：

```text
vLLM-Metal
MLX
Ollama
Linux + NVIDIA + vLLM
Cloud API
```

而不需要重写 RAG 和 Gateway。

---

# 5. NAS 的职责

NAS 主要负责：

```text
原始文档
知识库资料
PDF
Word
Markdown
代码
论文
说明书
历史资料
用户上传文件
数据库备份
向量库快照
```

推荐目录：

```text
AI_DATA/

├── knowledge/
│   ├── public/
│   ├── robotics/
│   ├── ai/
│   ├── manuals/
│   └── papers/
│
├── groups/
│
├── users/
│
├── uploads/
│
├── datasets/
│
└── backups/
```

注意：

如果 NAS 是通过 SMB / NFS 挂载到 Mac，不建议把 Qdrant 的实时数据库目录直接放在 SMB / NFS 中。

推荐：

```text
NAS
→ 保存原始资料

Mac SSD
→ Qdrant 活跃数据库

NAS
→ 定期保存 Qdrant snapshot
```

如果 NAS 本身支持 Docker 并且性能合适，也可以让 Qdrant 直接运行在 NAS 本机磁盘上。

---

# 6. RAG 方案

第一版建议使用：

```text
Hybrid RAG
```

即：

```text
Vector Search
+
BM25 / Keyword Search
+
Reranker
```

完整流程：

```text
用户问题
   │
   ▼
Embedding
   │
   ├──────────────┐
   ▼              ▼
Vector Search   BM25
   │              │
   └──────┬───────┘
          ▼
        Merge
          ▼
       Reranker
          ▼
       Top 3~5
          ▼
        Qwen
```

这样特别适合技术知识库。

例如：

```text
STM32F103ZET6
PA8
TIM1
CAN
YOLOv8
ROS2
CUDA
```

这类精确关键词，BM25 比纯向量检索更可靠。

而：

```text
机器人定位漂移
机械臂抓取失败
PWM异常
```

这种语义问题，Vector Search 更有优势。

---

# 7. Embedding 与 Reranker

第一版建议：

```text
Embedding:
Qwen3-Embedding-0.6B

Reranker:
Qwen3-Reranker-0.6B
```

优点：

- 模型较小；
- 支持中文；
- 支持英文；
- 支持代码和技术资料；
- 对 M4 32GB 压力较低。

第一版不要使用 4B / 8B Embedding 模型。

---

# 8. 向量数据库

第一版：

```text
Qdrant
```

Qdrant 负责：

```text
Embedding
Document Chunk
Metadata
Semantic Search
```

未来如需用户系统、权限、会话、日志，可以增加：

```text
PostgreSQL
```

第一版可以先不引入复杂数据库体系。

---

# 9. 文档索引

建议切块：

```text
Chunk Size:
500~800 tokens

Overlap:
80~120 tokens
```

推荐初始值：

```text
chunk_size = 700
chunk_overlap = 100
```

Metadata：

```json
{
  "document_id": "xxx",
  "filename": "slam_notes.md",
  "path": "/knowledge/robotics/",
  "chunk_id": 12,
  "page": 8,
  "owner_id": "public",
  "workspace_id": "robotics",
  "visibility": "public",
  "modified_at": "2026-09-13",
  "sha256": "..."
}
```

重新扫描 NAS 时：

```text
SHA256 未变化
→ 不重新 Embedding

SHA256 变化
→ 删除旧索引
→ 重新 Embedding
```

---

# 10. 本地 / 联网决策

第一版不要让 Qwen 自己直接说：

```text
“我有 90% 把握”
```

这种自报置信度不可靠。

应该用外部指标判断。

建议：

```text
Local Confidence
=
Vector Score
+
Reranker Score
+
Coverage
+
Source Quality
+
Freshness
```

第一版可以设置：

```text
Local Confidence >= 0.78
→ LOCAL

0.55 ~ 0.78
→ HYBRID

< 0.55
→ WEB
```

这只是初始阈值，后面通过实际问题测试再调整。

---

# 11. Freshness 判断

系统还要单独判断：

```text
问题是否依赖实时信息
```

例如：

### 不需要实时信息

```text
PID 控制是什么？
STM32 PWM 怎么工作？
A* 算法原理是什么？
```

优先本地。

### 需要实时信息

```text
Qwen 最新模型是什么？
今天 NVIDIA 发布了什么？
现在某 GitHub 项目的最新版本是多少？
```

直接进入 Web Search。

即：

```text
Freshness 高
→ 即使 RAG 相似度很高
→ 仍然联网
```

---

# 12. 四种基本路由

## GENERAL

```text
普通知识
→ Local Qwen
```

## PRIVATE

```text
涉及 NAS / 私有资料
→ RAG
→ Local Qwen
```

## FRESH

```text
需要最新信息
→ Web Search
→ Local Qwen
```

## PRIVATE + FRESH

```text
NAS RAG
+
Web Search
→ Local Qwen 综合
```

---

# 13. Web Search

第一版建议：

```text
Primary:
SearXNG
```

后续可增加：

```text
Fallback:
Tavily
```

设计原则：

```text
联网搜索
≠
调用云端大模型
```

完全可以：

```text
SearXNG 搜索互联网
→ 抓取结果
→ 本地 Qwen 阅读
→ 本地 Qwen 输出
```

只有本地模型明显不够时，才调用云模型。

---

# 14. Cloud API

第一版可以先保留接口，不一定立刻接很多平台。

推荐 Gateway 预留：

```text
cloud_llm()
```

未来可接：

```text
OpenAI
Claude
Gemini
Qwen Cloud
OpenRouter
```

第二阶段可以加入 LiteLLM 统一管理。

---

# 15. 云端回退逻辑

例如：

```text
Local Queue > 阈值
→ Cloud

Local Model Timeout
→ Cloud

Verifier 判断答案质量低
→ Cloud

复杂推理
→ Cloud

用户主动选择 CLOUD
→ Cloud
```

这样即使以后只有这一台 Mac，也可以利用云端解决偶发高负载。

---

# 16. 多用户

第一版支持：

```text
多个用户账号
多个 API Key
多个设备
```

但要限制：

```text
Peak Concurrent Generation
```

而不是限制总账号数。

建议第一版：

```text
MAX_CONCURRENT_LLM = 2
MAX_QUEUE = 20
```

跑 benchmark 后再尝试：

```text
MAX_CONCURRENT_LLM = 4
```

不要一开始开放 8~10 个同时生成请求。

---

# 17. 多用户权限

RAG 数据必须加访问权限。

每个 Chunk：

```json
{
  "owner_id": "user_001",
  "workspace_id": "robot_lab",
  "visibility": "private"
}
```

查询：

```text
owner_id = 当前用户

OR

workspace_id = 当前用户所在组

OR

visibility = public
```

避免：

```text
用户 A
→ 检索到用户 B 的私人资料
```

---

# 18. 用户模式

建议第一版 UI 提供：

```text
AUTO
LOCAL
KNOWLEDGE
WEB
CLOUD
```

### AUTO

自动判断。

### LOCAL

永不联网。

### KNOWLEDGE

强制查 NAS。

### WEB

强制联网。

### CLOUD

强制使用云模型。

---

# 19. 服务模式

还可以提供：

```text
FAST
NORMAL
DEEP
```

## FAST

```text
RAG Context <= 2K
Output <= 512 tokens
不开复杂工具
```

## NORMAL

```text
RAG Context 4K~6K
可联网
Output 1K~2K
```

## DEEP

```text
较长 RAG
Web Search
更多工具调用
必要时 Cloud
```

建议：

```text
Deep 并发 = 1
```

---

# 20. API

所有客户端统一调用：

```text
/v1/chat/completions
```

示例：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://MAC_IP:9000/v1",
    api_key="USER_API_KEY"
)

response = client.chat.completions.create(
    model="auto",
    messages=[
        {
            "role": "user",
            "content": "根据我的 SLAM 资料推荐导航方案"
        }
    ]
)
```

其中：

```text
model="auto"
```

不是实际模型名。

它代表：

```text
Gateway Router
```

---

# 21. 外部设备

以下设备都可以访问：

```text
Windows
Ubuntu
MacBook
手机
树莓派
机器人
其他 Python / C++ 程序
```

只需要：

```text
HTTP / HTTPS
+
OpenAI-compatible API
```

不需要每台电脑部署 Qwen。

---

# 22. 推荐目录

```text
local-ai-system/

├── gateway/
│   ├── main.py
│   ├── router.py
│   ├── confidence.py
│   ├── queue.py
│   ├── auth.py
│   └── verifier.py
│
├── rag/
│   ├── ingest.py
│   ├── parser.py
│   ├── chunker.py
│   ├── embedding.py
│   ├── retrieval.py
│   ├── bm25.py
│   └── reranker.py
│
├── tools/
│   ├── web_search.py
│   ├── web_fetch.py
│   ├── nas_search.py
│   └── cloud_llm.py
│
├── llm/
│   └── local_client.py
│
├── api/
│   └── openai_api.py
│
├── config/
│   ├── models.yaml
│   ├── routing.yaml
│   └── users.yaml
│
├── scripts/
│   └── benchmark.py
│
├── tests/
│
└── .env
```

---

# 23. 第一版配置

```yaml
model:
  backend: llama_cpp
  model: qwen-9b-q4

routing:
  local_threshold: 0.78
  hybrid_threshold: 0.55
  freshness_force_web: 0.80

rag:
  chunk_size: 700
  chunk_overlap: 100
  retrieval_top_k: 20
  rerank_top_k: 5
  max_context_tokens: 6000

server:
  max_concurrent_llm: 2
  max_queue: 20

web:
  primary: searxng

cloud:
  enabled: true
```

---

# 24. 第一版开发顺序

## Phase 1

部署：

```text
Qwen
+
llama.cpp
```

验收：

- Mac 本地能正常聊天；
- 支持流式输出；
- OpenAI API 可调用。

---

## Phase 2

局域网访问。

验收：

- Windows 可以调用；
- Ubuntu 可以调用；
- 手机浏览器可以使用。

---

## Phase 3

NAS。

验收：

- 可以读取 NAS 文档；
- 文件变化可以被检测；
- 文档可以自动进入索引流程。

---

## Phase 4

RAG。

加入：

```text
Qwen Embedding
Qdrant
```

验收：

- 能根据 NAS 文档回答；
- 回答中可以显示资料来源。

---

## Phase 5

Hybrid RAG。

加入：

```text
BM25
+
Reranker
```

验收：

- 技术型号、代码、函数名检索更准确；
- 语义问题仍然能够找到相关资料。

---

## Phase 6

Confidence Router。

验收：

```text
高置信度
→ Local

中置信度
→ Hybrid

低置信度
→ Web
```

---

## Phase 7

Web Search。

部署：

```text
SearXNG
```

验收：

- 最新问题可以自动联网；
- 搜索结果由本地 Qwen 综合回答。

---

## Phase 8

多用户。

增加：

```text
Auth
API Key
Queue
Concurrency Limit
RAG Permission Filter
```

---

## Phase 9

Cloud Fallback。

加入一个云 API 即可。

验收：

```text
本地过载
本地失败
复杂任务
→ 自动 Cloud
```

---

# 25. 性能目标

M4 32GB + 9B 4bit 的实际速度需要最终 benchmark。

第一版可以把目标设定为：

```text
Generation:
约 15~25 token/s

RAG First Token:
约 1~5 秒级
```

实际会受到：

```text
Context 长度
RAG 文档量
量化方式
llama.cpp 版本
并发数量
KV Cache
后台服务
```

影响。

---

# 26. 多用户目标

第一版建议设计目标：

```text
1 用户
→ 非常流畅

2 用户同时生成
→ 主要目标

3~4 用户同时生成
→ benchmark 后决定

5+ 用户
→ Queue

大量注册用户
→ 没问题，只要不是同时生成
```

所以：

```text
100 个注册账号
```

并不意味着 M4 跑不动。

真正影响性能的是：

```text
同时有多少人在生成 token
```

---

# 27. 第一版预计能达到的实际效果

完成第一版后：

## 效果 1：私人知识库问答

用户：

```text
根据我 NAS 中 STM32 的资料，
告诉我 TIM1 PWM 为什么不输出。
```

系统：

```text
自动搜索 NAS
→ 找到 STM32 文档
→ Hybrid RAG
→ Reranker
→ Qwen 阅读
→ 给出答案
→ 显示引用文档
```

---

## 效果 2：普通知识直接回答

用户：

```text
什么是 PID？
```

系统：

```text
判断无需 RAG
→ Local Qwen
→ 直接回答
```

降低延迟。

---

## 效果 3：最新信息自动联网

用户：

```text
现在 Qwen 最新的模型是什么？
```

系统：

```text
Freshness 高
→ Web Search
→ 获取最新网页
→ Local Qwen 综合
→ 回答
```

---

## 效果 4：本地资料 + 最新互联网

用户：

```text
结合我 NAS 中的机器人资料，
以及目前最新 VLA 技术，
给我设计一套方案。
```

系统：

```text
RAG
+
Web Search
+
Local Qwen
→ 综合回答
```

---

## 效果 5：多台电脑访问

例如：

```text
Mac
Windows
Ubuntu
手机
机器人
```

全部通过：

```text
http(s)://MAC_IP:9000/v1
```

访问同一套 AI。

无需分别部署模型。

---

## 效果 6：多用户

例如：

```text
用户 A
用户 B
用户 C
```

可以有各自：

```text
API Key
Private Knowledge
Public Knowledge
Group Knowledge
```

同时系统通过 Queue 控制生成任务。

---

## 效果 7：隐私模式

用户可以选择：

```text
LOCAL
```

此时：

```text
不 Web Search
不 Cloud API
```

所有问题都只在：

```text
Mac + NAS
```

中处理。

---

## 效果 8：自动升级到云端

当：

```text
Mac 队列过长
本地模型失败
复杂问题
本地答案验证不足
```

系统可以：

```text
Cloud API
```

完成任务。

用户不需要自己切模型。

---

# 28. 第一版暂时不做

为了控制复杂度，第一版暂时不要做：

```text
大规模 Kubernetes
多节点推理
几十人同时生成
27B/70B 常驻
复杂 Agent Swarm
复杂工作流平台
模型自动微调
自动训练
复杂长期记忆
语音
视频理解
多模态
```

这些后面再加。

---

# 29. 第一版核心价值

第一版真正要完成的不是：

```text
“在 Mac 上运行一个 Qwen”
```

而是：

```text
一个本地优先 AI 基础设施
```

核心能力：

```text
Local LLM
+
NAS Knowledge
+
Hybrid RAG
+
Confidence Router
+
Web Search
+
Cloud Fallback
+
Multi-user
+
OpenAI API
```

模型只是其中一个可以替换的组件。

---

# 30. 最终第一版定义

```text
Hardware:
Mac M4 32GB
+
NAS

Local LLM:
Qwen 9B 4bit

Inference:
llama.cpp

RAG:
Hybrid RAG

Embedding:
Qwen3-Embedding-0.6B

Reranker:
Qwen3-Reranker-0.6B

Vector DB:
Qdrant

Storage:
NAS

Web:
SearXNG

Cloud:
预留 API / 后续 LiteLLM

Frontend:
Open WebUI

API:
OpenAI-compatible

Multi-user:
Auth + API Key + Queue

Concurrent Generation:
初始 2
后续测试 4

Routing:
LOCAL
HYBRID
WEB
CLOUD
```

---

# 31. 最终目标体验

用户只需要：

```text
打开网页
或者
调用 API
```

然后正常提问。

用户不需要知道：

```text
这次用了 RAG 吗？
联网了吗？
用了本地模型吗？
用了云端模型吗？
```

系统自动完成：

```text
理解问题
↓
判断是否需要知识库
↓
判断是否需要最新信息
↓
检索 NAS
↓
联网搜索
↓
计算本地可信度
↓
选择本地 / Hybrid / Web / Cloud
↓
生成答案
↓
返回来源
```

最终体验应该接近：

> 一个拥有你自己的 NAS 私有知识、可以访问互联网、可以自动选择本地或云端模型，并且可以被多台电脑和多个用户访问的私人 AI 服务。
