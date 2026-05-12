# DocMind

企业内部知识库智能问答平台。员工用自然语言提问，系统从文档中语义检索，由 LLM 生成可溯源的答案。

> 本文档为设计文档集的入口导航页。详细内容已拆分至以下 7 份独立文档。

---

## 文档索引

| 文档                                   | 说明                                                   |
|:-------------------------------------|:-----------------------------------------------------|
| [PRD.md](./PRD.md)                   | **产品需求文档** — 业务场景、用户痛点、典型使用场景、验收标准                   |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | **架构设计文档** — 技术选型、系统架构、入库/问答流程、多路检索、会话记忆、关键设计决策与已知局限 |
| [DATABASE.md](./DATABASE.md)         | **数据库设计文档** — ER 关系、6 张表完整 DDL、索引策略                  |
| [API.md](./API.md)                   | **接口文档** — 全部 REST 接口定义、SSE 事件格式、统一错误码、权限矩阵、请求/响应示例  |
| [DEVELOPMENT.md](./DEVELOPMENT.md)   | **开发指南** — 项目结构、环境变量、依赖清单、本地启动命令、编码约定                |
| [ROADMAP.md](./ROADMAP.md)           | **开发排期** — Phase 1-5 任务分解、时间线、依赖关系                   |
| [TESTING.md](./TESTING.md)           | **测试策略** — 检索评估指标、人工评分标准、回归测试集、压测指标                  |
| [UIDESIGN.md](./UIDESIGN.md)         | **UI 设计规范** — CSS 变量、组件样式规范、布局规范，面向 Agent 的前端样式参考      |

---

## 技术栈速览

| 层面 | 技术 |
|:---|:---|
| 后端框架 | FastAPI (异步) |
| AI 编排 | LangChain |
| LLM | DeepSeek (OpenAI 兼容) |
| Embedding | DashScope text-embedding-v3 (1024 维) |
| 向量数据库 | ChromaDB |
| 关系数据库 | MySQL + SQLAlchemy 2.0 async |
| 缓存/队列 | Redis + Celery |
| 前端 | Vue 3 + Vite + Element Plus + Pinia |

---

## 当前进度

- [x] Phase 1 部分 — SQLAlchemy 模型 + Alembic 迁移 + DB 连接 + FastAPI 入口 + 前端环境
- [ ] Phase 1 剩余 — ChromaDB、JWT 认证、前端登录页
- [ ] Phase 2-5 — 见 [ROADMAP.md](./ROADMAP.md)

---

## 开发相关

- 编码约束详见项目根目录 [CLAUDE.md](./CLAUDE.md)
- 变更记录详见 [CHANGE.md](./CHANGE.md)
- 各文档版本均为 v0.2（草稿），最后更新 2026-05-11
