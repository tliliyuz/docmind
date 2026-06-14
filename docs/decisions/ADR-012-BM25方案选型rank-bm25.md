# ADR-012: BM25 方案选型——rank-bm25

**状态**：已采纳（2026-05-18，2026-05-28 确认）
**决策者**：开发团队
**关联文档**：ARCHITECTURE.md §6.2§7.2 / ROADMAP.md §3.2

## 上下文

此前认为 `rank-bm25`「基于空格分词，中文无分词能力」而移除依赖，计划自定义 BM25 实现。

## 决策

切换回 `rank-bm25 (BM25Okapi)` + `jieba` 分词。

## 理由

1. `rank-bm25` 构造函数接受 `tokenizer` 参数，传入 `jieba.lcut` 后中文分词问题不存在
2. 库仅 260 行单文件 + numpy 依赖，小且稳定
3. BM25 核心公式几十年未变，2022 年停止更新不构成弃用理由
4. 自定义实现需重新处理 NumPy 向量化、IDF 负值 floor、batch_scores 等细节，造轮子性价比低

## 后果

- `requirements.txt` 加回 `rank-bm25==0.2.*`
- `BM25Retriever` 初始化传入 `preprocess_func=jieba.lcut`
