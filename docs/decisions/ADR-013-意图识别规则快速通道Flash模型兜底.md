# ADR-013: 意图识别——规则快速通道 + Flash 模型兜底

**状态**：已采纳（2026-06-11）
**决策者**：开发团队
**关联文档**：RAG_PIPELINE.md §6 / API.md §6

## 上下文

Phase 3 使用规则级 `_is_casual_chat()` 做闲谈检测，覆盖率 ~70%，无法处理语义层面的意图分类。Phase 5 引入 LLM 意图分类器。

## 决策

两阶段分类：
1. **规则快速通道**：`_is_meta_question()` regex + `_is_casual_chat()` regex → 零延迟
2. **LLM Flash 兜底**：3 类分类（KNOWLEDGE/CASUAL/META）+ few-shot Prompt + Flash 模型（`deepseek-v4-flash`）→ ~1-2s

3 类分流：
- KNOWLEDGE：走完整 RAG 链路
- CASUAL：跳过检索，使用 `CASUAL_SYSTEM_PROMPT`
- META：不调 LLM，固定模板 SSE 响应

## 理由

- 规则通道覆盖高频模式（问候/致谢/元问题），延迟 <1ms
- Flash 模型成本 ~1/5 Pro 模型，延迟 ~1-2s
- 分类准确率从 ~70% 提升至 >95%

## 后果

- BM25Retriever 改为异步懒加载
- `MetaQuestionException` 异常中断主流程
