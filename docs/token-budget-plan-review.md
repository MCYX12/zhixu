# Token 预算前后核对

2026-09-14。开工核对总计划 §8、§15，当前仍只有字符上限。依据本机锁定 llama.cpp b9716 的 README、server.cpp 路由及 server-context.cpp 计数实现，接入与生成相同的聊天计数接口；未使用在线或云端 tokenizer。

完工：全量提示 + 输出上限 + 32-token 余量检查；读取每槽 n_ctx；超限 413、服务失败 503，流式和非流式均在生成前执行且释放租约。当前/示例配置开启，状态页展示。总计划 v2.6，旧版归档。

123 项测试通过；真实预检 592 与模型输入用量一致，12106-token 输入在 8192 槽位限制下提前拒绝。详情见 token-budget-runtime-validation.json。此结果不代替长时压力测试或其他模型兼容性验收。

剩余：自动压缩、按 token 切块、M1/M2 容量矩阵；M3 OCR/结构解析；M4 语义混合检索/重排/评估；M5 SSO、网页成员治理、HTTPS、launchd、监控及离机恢复；M6 多引擎搜索/VPN 长期验收；M7 Cloud/DEEP。NAS 暂缓。
