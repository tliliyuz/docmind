# ADR-008: NoopReranker 策略——保持 RRF 相关性排序

**状态**：已采纳（2026-06-04）
**决策者**：开发团队
**关联文档**：RAG_PIPELINE.md §3 / ARCHITECTURE.md §7.3 / ROADMAP.md §5.5

## 上下文

ARCHITECTURE.md §7.3 原将 NoopReranker 描述为「按 chunk 长度升序排列（短 chunk 优先）」，这是一个错误的启发式策略——在 RAG 场景中，相关性 >> 长度。短 chunk 优先导致语义匹配/跨文档场景下 LLM 拿到不相关短 chunk → 误判「未找到相关信息」→ sources 被抑制 → 回归测试 17/30 失败。

此外 `prompt_builder.py` 对 NoopReranker 输出再次执行 `sorted(key=len)`，将 RRF 相关性排序重新按长度打乱。

## 决策

1. NoopReranker 改为「保持 RRF 融合排序（相关性降序），仅截取 top_k」
2. prompt_builder 移除 `sorted(key=len)`，直接使用 `retrieval_output.results`

## 理由

- RRF 融合计算出的相关性排名具有语义意义，长度排序完全破坏
- 短 chunk ≠ 高信息密度，中文场景尤其不成立
- 双层长度排序（reranker + prompt_builder）形成负向叠加

## 后果

- 回归测试通过率从 13/30 提升至 26/30+
- 检索评估 Recall@5 = 1.000 与 chat 链路行为一致
- Phase 5.5 接入 DashScope Rerank API 后，NoopReranker 将被 `DashScopeReranker` 替换。本 ADR 的核心原则「保持 RRF 相关性排序」不因实现替换而改变
