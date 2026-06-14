# ADR-006: Query Rewrite 提前至 Phase 4

**状态**：已采纳（2026-06-08）
**决策者**：开发团队
**关联文档**：RAG_PIPELINE.md §4 / ARCHITECTURE.md §8.10 / ROADMAP.md §6.1§6.7

## 上下文

多轮 RAG 回归测试稳定复现指代词退化：指代词「它需要几个人参加？」直接发给检索器 → 嵌入模型无法消解指代 → 检索出无关文档。原决策「推迟到 Phase 5，DeepSeek 结合 history 可自然消解」被证伪——检索发生在 LLM 之前，history 注入无法解决检索阶段的 query 歧义。

## 决策

1. Query Rewrite 提前至 Phase 4 实现
2. 触发策略：`_needs_rewrite()` 轻量歧义检测（13 个信号词），无歧义跳过
3. 改写结果仅用于检索，不持久化到 messages 表
4. LLM 失败降级到原始 question，不阻塞主流程

## 理由

- 检索阶段在 LLM 之前，history 无法影响 query 向量化
- 仅信号词触发避免全量改写的误触发风险
- 最近 2 轮 history 足够消解指代，全量历史浪费 token

## 已知局限

纯省略/隐含依赖无法通过信号词检测（如「审批流程需要多长时间？」省略了「报销」）。后续方向：Retrieval-aware Rewrite（先检索，结果差时再 Rewrite）。
