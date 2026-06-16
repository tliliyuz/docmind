# ADR-017: SSE 流 DB 会话生命周期解耦

**状态**：已采纳（2026-06-15）
**决策者**：开发团队
**关联文档**：ARCHITECTURE.md §5.1 / API.md §6

## 上下文

`chat_service.py` 的 `_generate_sse_stream()` 和 `_generate_meta_response()` 是两个 async generator，用于 SSE 流式输出。当前它们接收 `db: AsyncSession` 参数，该 session 来自 FastAPI `Depends(get_db)` 依赖注入。

问题链路：

```
API endpoint → Depends(get_db) → async with async_session() as session:
    ↓
chat() → _validate_and_prepare(db)  # 使用 session，完成后 commit
    ↓
_generate_sse_stream(db)  # 持有 session 引用
    ↓
for chunk in llm.stream():  # 持续 10–60 秒
    yield ...
    ↓
db.add(assistant_msg)  # 仅最后 50ms 使用 session
db.commit()
```

`Depends(get_db)` 的 `async with async_session()` 上下文在 StreamingResponse **完全发送后**才退出，意味着一个 SSE 连接持有 DB 连接 30 秒，而实际 DB 操作仅占用最后 ~50ms。

### 影响量化

- 连接池配置：`pool_size=5, max_overflow=10` → 最大 15 并发连接
- SSE 长连接：单用户复杂问题 = 占用 1 个连接 30 秒
- 15 个并发 SSE → 连接池耗尽 → 第 16 个请求（含普通 CRUD）阻塞等待
- 普通 CRUD 请求 DB 占用仅 ~20ms，但被 SSE 请求的闲置连接阻塞

这是典型的**资源泄漏模式**：长生命周期请求持有短生命周期资源。

## 决策

### 1. Generator 内部自管短生命周期 Session

`_generate_sse_stream()` 和 `_generate_meta_response()` **不再接收外部 `db` 参数**。在需要持久化消息和 Trace 时，内部创建独立的短生命周期 session：

```python
async def _generate_sse_stream(conv, ...) -> AsyncIterator[str]:
    # LLM 流式阶段：不使用 DB
    async for chunk in stream_chat_completion(...):
        yield ...

    # 持久化阶段：独立短 session
    async with async_session() as s:
        try:
            conv_in = await s.get(Conversation, conv.id)  # 重新查询
            # ... 保存消息、更新会话 ...
            if recorder:
                await recorder.finish(s, commit=False)
            await s.commit()  # 单事务提交
        except Exception:
            await s.rollback()
            raise

    yield format_sse_event("finish", {...})  # session 已释放
```

### 2. 消息 + Trace 单事务提交

当前实现存在**部分提交**风险：

```python
# 旧代码：两次独立 commit
await db.commit()          # ① 消息已落库
await recorder.finish(db)  # ② record_trace() 内部 commit —— 若失败，消息已落库而 Trace 丢失
```

改为**单事务**：消息写入 → Trace 写入（不 commit）→ 统一 `await s.commit()`。任一失败均回滚全部。

为支持此模式，`TraceRecorder.finish()` 和 `record_trace()` 新增 `commit: bool = True` 参数，调用方可传入 `commit=False` 由外层统一提交。

### 3. `yield finish` 置于 Session 外部

`finish` 事件包含 `message_id`，该 ID 在 `s.flush()` 后即可获取。`yield` 放在 `async with` 块外部，确保 session 已释放后才向客户端发送最终事件。

```python
# session 已释放
yield format_sse_event("finish", {
    "message_id": assistant_msg.id,  # flush 后已赋值
    ...
})
```

### 4. 跨 Session 对象安全

`conv` 对象来自调用方 session（`_validate_and_prepare` 中加载），传入新 session 时处于 detached 状态。通过 `await s.get(Conversation, conv.id)` 重新查询，确保拿到当前最新状态并绑定到当前 session。

## 理由

- **连接池保护**：SSE 流式期间不持有任何 DB 连接，连接仅在最后持久化阶段短暂占用（~10ms）
- **事务一致性**：assistant 消息和 Trace 记录在同一事务中提交，避免部分落库
- **并发安全**：重新查询 `conv` 获取最新状态，天然处理 SSE 期间会话被外部修改（如删除）的场景
- **最小改动**：仅修改 `chat_service.py` 两个 generator 函数 + `trace_recorder.py`/`trace_service.py` 各一个参数，不动 API 层

## 后果

- `Depends(get_db)` 在 chat 端点中仍然存在（`_validate_and_prepare` 使用），但 session 在 `_validate_and_prepare` 返回前已 commit 全部变更，SSE 期间闲置等待 StreamingResponse 完成。彻底解耦需额外 ADR（将 API 端点改为手动 session 管理），当前方案已解决核心资源泄漏问题
- generator 内部 `async with async_session()` 创建独立 session，需要从 `app.core.database` 导入
- 测试需调整：原来 mock 外部传入的 `db`，现在需 mock `async_session()` 上下文管理器

---

> **实现更新（2026-06-16）**：`_generate_sse_stream()` 和 `_generate_meta_response()`（含 `_persist_fixed_response()`）已从 `chat_service.py` 提取到独立的 `sse_stream.py` 模块。`chat_service.py` 通过 re-export 保持向后兼容导入路径。本 ADR 描述的设计决策和 DB 会话解耦方案不变。
