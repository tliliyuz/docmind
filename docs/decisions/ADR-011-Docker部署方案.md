# ADR-011: Docker 部署方案

**状态**：已采纳（2026-06-12）
**决策者**：开发团队
**关联文档**：ARCHITECTURE.md §12.1 / DEVELOPMENT.md §9 / ROADMAP.md §7.3.2

## 上下文

项目需要生产部署方案，FastAPI + Celery + MySQL + Redis + Nginx 五个组件需要编排。

## 决策

1. **同一镜像双用途**：Backend 和 Celery 共用 `Dockerfile.backend`，docker-compose 通过 `command` 区分启动方式
2. **Celery prefork pool**：Linux 容器使用默认 prefork pool（`--concurrency=4`），不传 `--pool=solo`（Windows 限制仅影响原生运行）
3. **Redis 客户端自动切换**：`sys.platform != "win32"` 判断，Linux 走原生 `redis.asyncio`，Windows 走 `ThreadedRedisClient` 线程池包装。零配置
4. **Nginx SSE 支持**：`proxy_buffering off` / `chunked_transfer_encoding off` / 300s 超时

## 理由

- 单镜像减少维护成本，Celery Worker 本质上就是 FastAPI 进程 + worker 启动参数
- Prefork pool 在 Linux 下性能优于 solo
- Redis 客户端切换对开发者透明，本地 Windows 和 Docker 生产均无需手动干预

## 后果

- `docker-compose.yml` 5 服务 + 4 持久化卷
- `nginx.conf` 需特别注意 SSE 配置
