# ADR-014: Redis 异步接口 Windows 兼容方案

**状态**：已采纳（2026-06-11）
**决策者**：开发团队
**关联文档**：ARCHITECTURE.md §6.2 / DEVELOPMENT.md §9

## 上下文

Windows 开发环境下 `redis.asyncio` 存在连接超时和稳定性问题。

## 决策

采用「同步 Redis + `asyncio.to_thread()`」提供异步接口，避免阻塞事件循环。生产环境（Linux）使用原生 `redis.asyncio` + `ConnectionPool`。

通过 `sys.platform` 自动判断，零配置。

## 理由

- 同步客户端在 Windows 下稳定可靠
- `asyncio.to_thread` 在线程池中执行，不阻塞事件循环
- 进程内缓存（L1）依然在，Redis 网络 IO 开销不变
- `get_async_redis()` 返回值签名不变，调用方无需修改

## 后果

- 新增 `ThreadedRedisClient` 包装类
- 极高 QPS 时线程池有额外开销（DocMind 当前 10~50 QPS 完全够用）
