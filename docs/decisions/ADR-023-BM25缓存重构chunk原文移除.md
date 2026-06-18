# ADR-023：BM25 缓存重构 — chunk 原文从缓存中移除

## 状态

✅ 已采纳（2026-06-18）

## 背景

BM25 关键词检索采用三级缓存设计：

1. **L1 进程内缓存**（dict，TTL=60s）：存储 `BM25Okapi` 实例 + doc_ids + chunk 原文 + section_info
2. **L2 Redis 缓存**（TTL=300s）：存储 tokenized_corpus + doc_ids + chunk 原文 + section_info
3. **L3 MySQL 懒加载**：缓存未命中时从 MySQL 加载全库 chunk 并 jieba 分词

对于 **20000 chunk** 的知识库，单次 BM25 查询的内存开销：

| 组件 | 估算内存 | 说明 |
|:---|:---|:---|
| tokenized_corpus | ~230MB | 4M token × ~50B Python 字符串开销 |
| BM25Okapi 内部结构 | ~50MB | idf/dict/doc_freqs（含 `self.corpus` 引用 token 列表） |
| chunk 原文列表 | ~20MB | 20000 × 500 字符 × Python 开销 |
| section_info | ~5MB | 20000 × 2 短字符串 |
| **合计** | **~300MB** | |

加上 FastAPI 进程自身 + ChromaDB（同进程）的内存占用，在 512MB~1GB 容器的限制下极易触发 **Linux OOM Kill**（exit code 137）。

## 决策

### 1. 从所有缓存层移除 chunk 原文（contents）

**之前**：
```json
{
  "doc_ids": [[1, 0], [1, 1]],
  "tokens": [["入职", "指南"], ["报销", "制度"]],
  "contents": ["入职指南欢迎加入公司", "报销制度差旅标准"],
  "section_info": [...]
}
```

**之后**：
```json
{
  "doc_ids": [[1, 0], [1, 1]],
  "tokens": [["入职", "指南"], ["报销", "制度"]],
  "section_info": [...]
}
```

BM25 评分后，仅对 top_k 条结果按需从 MySQL 批量取原文：

```sql
SELECT doc_id, chunk_index, content FROM chunks
WHERE (doc_id, chunk_index) IN ((1,0), (2,5), ...)  -- ≤10 条
```

### 2. 大知识库跳过进程内缓存

新增配置项 `BM25_LOCAL_CACHE_MAX_CHUNKS`（默认 5000）。chunk 数超过阈值的 KB 不写入进程内缓存，每次请求从 Redis 读取 token 缓存后重建 BM25Okapi，请求结束后由 GC 回收内存。

### 3. 内存监控日志

大 KB 加载时在关键节点（MySQL 读取后 / jieba 分词后 / BM25Okapi 构建后）打印 RSS 内存日志：

```
BM25_LOAD_START kb_id=1 mem=120.5MB
BM25_LOAD mysql_done kb_id=1 rows=20000 time=0.5s mem=180.3MB
BM25_LOAD jieba_done kb_id=1 chunks=20000 time=3.2s mem=520.7MB
BM25_LOAD bm25_done kb_id=1 chunks=20000 time=1.8s mem=580.1MB
BM25_LOAD done kb_id=1 ... mem_start=120.5MB mem_end=580.1MB delta=459.6MB
```

## 后果

### 正面

- **OOM 风险大幅降低**：进程内缓存不再持有全库 chunk 原文（~20MB→0），大 KB 不再持有 BM25Okapi 实例（~280MB→0），内存峰值仅在请求期间
- **Redis 缓存体积缩减**：移除 contents 后 JSON payload 减少约 30-40%
- **内存可观测性提升**：psutil 日志精确追踪每个阶段的 RSS 增量，便于定位瓶颈
- **向后兼容**：旧缓存中的 `contents` 字段自动忽略，旧缓存无 `section_info` 字段时默认空列表

### 负面

- **大 KB 每次查询需重建 BM25Okapi**：对于 >5000 chunks 的 KB，每次请求需从 Redis 反序列化 token JSON（10-30MB payload）+ 调用 `BM25Okapi(tokens)` 重建索引（20000 chunks ~2-5s CPU），无进程内缓存加速
- **每次查询额外 1 次 MySQL 批量查询**：取 top_k chunk 原文（≤10 条，<10ms），开销可忽略
- **依赖 psutil**：新增依赖，仅用于内存日志打印（非核心路径，psutil 不可用时日志显示 -1.0MB）

### 风险

- **大 KB BM25 重建时间线性增长**：当前 ~2-5s @ 20000 chunks，未来 50000+ chunks 可能达到 ~5-12s。需关注 Redis GET 超时（当前无显式超时设置）
- **缓解方案**（后续 Phase）：
  - 将 BM25Okapi 序列化为 pickle 存入 Redis（消除重建 CPU 成本，但 pickle 不安全且跨版本脆弱）
  - 使用 Redis Sorted Sets 实现倒排索引（避免全量加载到 Python 内存）
  - 迁移 BM25 到 Elasticsearch（专用检索引擎，天然支持增量更新和分布式）

## 备选方案

### 方案 A：pickle BM25Okapi 存入 Redis（未采纳）

- 优点：Redis 命中后直接反序列化，零重建成本
- 缺点：pickle 跨 Python 版本脆弱、安全风险（任意代码执行）、Redis 中不可读不可排查、内存占用不变（pickle 内含 `self.corpus` 即全量 tokenized_corpus）

### 方案 B：全部缓存都跳过，每次从 MySQL 重建（未采纳）

- 优点：零 Redis 依赖，逻辑最简单
- 缺点：每次请求需 jieba 分词全库 chunk（20000 chunks ~3-5s），功耗浪费

### 方案 C：Redis 只存 BM25 索引参数（idf / doc_len / avgdl），按需计算（未采纳）

- 优点：Redis payload 最小
- 缺点：`rank-bm25` 内部 `get_scores()` 仍需要遍历 `self.corpus` 计算 TF，无法绕过 tokenized_corpus；需 fork 或重写 BM25Okapi

## 相关

- [ADR-012：BM25 方案选型 rank-bm25](ADR-012-BM25方案选型rank-bm25.md)
- [ADR-014：Redis 异步接口 Windows 兼容方案](ADR-014-Redis异步接口Windows兼容方案.md)
- [RAG_PIPELINE.md §2.2](../backend/docs/RAG_PIPELINE.md#22-bm25-关键词检索)
