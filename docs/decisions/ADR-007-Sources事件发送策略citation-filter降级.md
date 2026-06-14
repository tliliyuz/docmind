# ADR-007: Sources 事件发送策略——citation filter 降级为优化

**状态**：已采纳（2026-06-08）
**决策者**：开发团队
**关联文档**：RAG_PIPELINE.md §5 / API.md §6.1

## 上下文

Sources 事件发送逻辑存在脆弱耦合：`sources` 是否发送 = LLM 是否在回答中写了 `[来源N]`。Prompt 中「引用来源时标注 [来源N]」是建议而非强约束，DeepSeek/Qwen 等模型经常正确回答但忘记写 `[来源N]`。

后果：检索成功 → chunk 进入 Prompt → LLM 给出正确答案 → 但没写 `[来源N]` → sources 事件消失 → 被误判为 RAG 退化。

## 决策

Citation filter 从「必须」降级为「优化」：
- LLM 写了 `[来源N]` → 保留引用过滤（仅发送被引用的 chunk）
- LLM 未引用 → **回退发送全部 used_chunks**
- LLM 声明「未找到」→ sources 不发送

## 理由

- Sources 应来自 used_chunks（检索结果），而非 LLM 是否记得写 `[来源N]`
- 对 LLM 输出格式不可控性的务实应对
- `SOURCES_DIAG` 日志保留在 INFO 级别，便于观察 LLM 引用行为分布

## 后果

- 原「零引用时 sources 不发送」测试改为「零引用时 sources 仍发送_回退全量」
