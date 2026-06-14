# ADR-010: Evidence Highlight——句级 BM25 替代 LLM 引用定位

**状态**：已采纳（2026-06-11）
**决策者**：开发团队
**关联文档**：RAG_PIPELINE.md §7 / API.md §6.1

## 上下文

原方案从 LLM 回答中提取 `[来源N]` 后的文本，在 chunk 中做规范化匹配定位高亮区间。问题：DeepSeek/Qwen 常将引用标在句末（如「...事由 [来源2]。」），`extractSnippetAfter` 提取到的是标点/下一句而非相关文本；且前端 snippet 体系复杂（5 个辅助函数 ~80 行）。

## 决策

1. 检索时用 BM25 句级定位确定证据句（`sentence_matcher.py`）
2. 后端计算 `highlight_start/end`（`preview_text` 内偏移），前端纯 `slice` 渲染
3. 删除前端 snippet 体系（`extractSnippet`/`extractSnippetAfter`/`normalizeWhitespace`/`buildNormPosMap`/`isNormCharStart`）

数据流：`BM25 句级定位 → matched_sentence → preview_text ±100 字符 → highlight_start/end → 前端纯渲染`

## 理由

- 「检索时就确定证据句」优于「事后猜 LLM 引用了哪里」
- 后端计算偏移，前端零匹配逻辑，前后端解耦
- 净代码减少 ~130 行

## 后果

- `ChatSourceChunk` 新增 `highlight_start`/`highlight_end` 字段
- 前端 `<mark>` 渲染从规范化匹配改为纯切片
