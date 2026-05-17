# DATABASE — 数据库设计文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.4 |
| 最后更新 | 2026-05-17 |
| 作者 | yuz |
| 状态 | 草稿 |

---

## 1. ER 关系

```
users (用户表)
  │
  ├── knowledge_bases (知识库表)
  │     └── documents (文档表)
  │           └── chunks (分块表)
  │
  └── conversations (会话表)
        └── messages (消息表)
```

**关系说明**：
- 一个用户可创建多个知识库，每个知识库属于一个用户（1:N）
- 一个知识库包含多个文档，每个文档属于一个知识库（1:N）
- 一个文档被切分为多个分块，每个分块属于一个文档（1:N）
- 一个用户可发起多个会话，每个会话属于一个用户（1:N）
- 一个会话包含多条消息，每条消息属于一个会话（1:N）
- 会话可关联一个知识库（可选），表示当前对话的知识库上下文

---

## 2. 表结构

### 2.1 用户表 `users`

```sql
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role ENUM('user', 'admin') DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| username | VARCHAR(64) | 用户名，唯一索引 |
| password_hash | VARCHAR(256) | bcrypt 哈希后的密码 |
| role | ENUM | 角色：user（普通用户）/ admin（管理员） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间，自动更新 |

### 2.2 知识库表 `knowledge_bases`

```sql
CREATE TABLE knowledge_bases (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    user_id BIGINT NOT NULL,
    status ENUM('active', 'deleting') DEFAULT 'active',
    chunk_count INT DEFAULT 0,
    doc_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    UNIQUE INDEX idx_user_name (user_id, name)
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| name | VARCHAR(128) | 知识库名称，与 user_id 联合唯一（同一用户下名称不重复） |
| description | TEXT | 知识库描述 |
| user_id | BIGINT | 创建者用户 ID |
| status | ENUM | active（正常）/ deleting（异步清理中，随后物理删除行） |
| chunk_count | INT | 分块总数（冗余缓存，避免 COUNT 查询） |
| doc_count | INT | 文档总数（冗余缓存） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 2.3 文档表 `documents`

```sql
CREATE TABLE documents (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    kb_id BIGINT NOT NULL,
    filename VARCHAR(256) NOT NULL,
    file_type VARCHAR(32) NOT NULL COMMENT 'pdf/docx/md/txt',
    file_path VARCHAR(512) COMMENT '文件存储路径：uploads/{kb_id}/{doc_id}/{uuid}_{sanitized_filename}',
    file_size BIGINT COMMENT 'bytes',
    status ENUM('uploaded','parsing','chunking','embedding','vector_storing','completed','success_with_warnings','partial_failed','failed','deleting') DEFAULT 'uploaded',
    chunk_count INT DEFAULT 0,
    error_msg TEXT,
    current_stage VARCHAR(32) COMMENT '当前处理阶段，用于断点恢复',
    last_success_batch INT DEFAULT 0 COMMENT '最后成功的批次号，用于批次级 checkpoint',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_kb_id (kb_id),
    INDEX idx_kb_filename (kb_id, filename) COMMENT '文档唯一性检查',
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| kb_id | BIGINT | 所属知识库 ID，有索引 |
| filename | VARCHAR(256) | 原始文件名 |
| file_type | VARCHAR(32) | 文件类型：pdf / docx / md / txt |
| file_path | VARCHAR(512) | 文件存储路径 |
| file_size | BIGINT | 文件大小（字节） |
| status | ENUM | 入库状态，使用 `DocumentStatus(str, Enum)` 统一管理（见 API.md §4.0） |
| chunk_count | INT | 分块数量 |
| error_msg | TEXT | 入库失败时的错误信息 |
| current_stage | VARCHAR(32) | 当前处理阶段（parsing/chunking/embedding/vector_storing），断点恢复用 |
| last_success_batch | INT | 最后成功批次号（Embedding 批次级 checkpoint） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**文档状态流转**：

```
uploaded → parsing → chunking → embedding → vector_storing → completed
              ↓         ↓          ↓            ↓
          ───────────→ failed ←───────────────
              ↓         ↓          ↓            ↓
          success_with_warnings / partial_failed

**任一终态 → reprocess → parsing（重新入库）**
`completed` / `success_with_warnings` / `partial_failed` / `failed` = 终态（`TERMINAL_STATUSES`）
`deleting` = 异步清理中，清理完成后物理删除行（非终态，行删除后不存在）
```

**新增索引**：`idx_kb_filename (kb_id, filename)` 用于文档唯一性检查（同名文档快速查找）。

**状态枚举定义**（详见 API.md §4.0）：
```python
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    VECTOR_STORING = "vector_storing"
    COMPLETED = "completed"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    DELETING = "deleting"

TERMINAL_STATUSES = {
    "completed",
    "success_with_warnings",
    "partial_failed",
    "failed"
}
```

### 2.4 分块表 `chunks`

```sql
CREATE TABLE chunks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    doc_id BIGINT NOT NULL,
    kb_id BIGINT NOT NULL,
    chroma_id VARCHAR(256) NOT NULL COMMENT 'ChromaDB中的chunk id',
    content TEXT NOT NULL,
    chunk_index INT NOT NULL COMMENT '在原文档中的顺序',
    token_count INT DEFAULT 0,
    metadata JSON COMMENT '页码、段落标题等',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_doc_id (doc_id),
    INDEX idx_kb_id (kb_id),
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| doc_id | BIGINT | 所属文档 ID，有索引 |
| kb_id | BIGINT | 所属知识库 ID，有索引（冗余，便于按知识库统计分块） |
| chroma_id | VARCHAR(256) | ChromaDB 中对应的 chunk id，用于回溯和删除 |
| content | TEXT | 分块文本内容 |
| chunk_index | INT | 在原文档中的顺序（从 0 开始） |
| token_count | INT | 估算的 token 数量 |
| metadata | JSON | 额外元数据（页码、段落标题等） |
| created_at | DATETIME | 创建时间 |

### 2.5 会话表 `conversations`

```sql
CREATE TABLE conversations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    kb_id BIGINT COMMENT '关联的知识库',
    title VARCHAR(256) DEFAULT '新对话',
    message_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (kb_id) REFERENCES knowledge_bases(id) ON DELETE SET NULL
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| user_id | BIGINT | 所属用户 ID，有索引 |
| kb_id | BIGINT | 关联的知识库 ID（可选，表示对话的知识域） |
| title | VARCHAR(256) | 对话标题（可由首条消息自动生成） |
| message_count | INT | 消息总数（冗余缓存） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 2.6 消息表 `messages`

```sql
CREATE TABLE messages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content TEXT NOT NULL,
    thinking_content TEXT COMMENT '深度思考内容',
    token_count INT DEFAULT 0,
    feedback ENUM('like', 'dislike') NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_conversation_id (conversation_id),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
```

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| id | BIGINT | 主键 |
| conversation_id | BIGINT | 所属会话 ID，有索引 |
| role | ENUM | 消息角色：user / assistant / system |
| content | TEXT | 消息正文 |
| thinking_content | TEXT | DeepSeek 深度思考内容（可空） |
| token_count | INT | 消息消耗的 token 估算 |
| feedback | ENUM | 用户反馈：like / dislike（可空） |
| created_at | DATETIME | 创建时间 |

---

## 3. 索引策略

| 表 | 索引 | 类型 | 用途 |
|:---|:---|:---|:---|
| users | username (UNIQUE) | 唯一索引 | 登录查询 |
| knowledge_bases | idx_user_name (user_id, name) | 唯一索引 | 用户级知识库名称唯一性约束 |
| documents | idx_kb_id | 普通索引 | 按知识库列出文档 |
| documents | idx_kb_filename (kb_id, filename) | 复合索引 | 文档唯一性检查 + 同名查找 |
| chunks | idx_doc_id | 普通索引 | 按文档列出分块 |
| chunks | idx_kb_id | 普通索引 | 按知识库统计分块 |
| conversations | idx_user_id | 普通索引 | 按用户列出会话 |
| messages | idx_conversation_id | 普通索引 | 按会话列出消息 |

> **注意**：MySQL 会自动为外键列创建索引（若该列尚未建立索引）。上表中 `chunks.doc_id`、`chunks.kb_id` 等因已有显式索引，不再重复；`conversations.kb_id` 无外键索引，如需频繁按知识库查询会话，可后续补充。

> TODO: [待补充] 如后续文档量和用户量增大，考虑：
> - `documents` 表增加 `(kb_id, status)` 复合索引用于状态过滤
> - `messages` 表增加 `(conversation_id, created_at)` 复合索引用于按时间排序

---

## 4. 外键策略

| 字段 | 引用表 | 级联行为 | 设计理由 |
|:---|:---|:---|:---|
| `knowledge_bases.user_id` | `users(id)` | `ON DELETE RESTRICT` | 知识库是组织资产，删除用户前必须先转移或手动删除其知识库，防止误删导致数据丢失 |
| `documents.kb_id` | `knowledge_bases(id)` | `ON DELETE CASCADE` | 删除知识库时自动清空旗下所有文档，与业务「删除知识库及其下所有文档」对齐 |
| `chunks.doc_id` | `documents(id)` | `ON DELETE CASCADE` | 删除文档时自动清空其分块，保证 MySQL 与 ChromaDB 数据一致性 |
| `chunks.kb_id` | `knowledge_bases(id)` | `ON DELETE CASCADE` | 冗余字段，知识库删除时级联清理分块记录，便于按知识库统计 |
| `conversations.user_id` | `users(id)` | `ON DELETE CASCADE` | 用户删除时自动清理其会话历史，避免悬空数据 |
| `conversations.kb_id` | `knowledge_bases(id)` | `ON DELETE SET NULL` | 知识库删除后会话保留，仅解除关联（kb_id 置空），防止历史对话丢失 |
| `messages.conversation_id` | `conversations(id)` | `ON DELETE CASCADE` | 删除会话时自动清理全部消息，与业务「删除会话及其全部消息」对齐 |

> **重要**：知识库/文档的实际删除采用 **Celery 异步物理删除**（先标记 `deleting` → Worker 清理 ChromaDB 向量 + 磁盘文件 → 物理 `DELETE FROM` MySQL 记录）。`ON DELETE CASCADE` 作为数据库层兜底保障——即使 Celery 仅执行 `DELETE FROM knowledge_bases WHERE id=?`，子记录（documents → chunks）也会由 FK CASCADE 自动级联清理，无需显式逐表删除。

**一致性保障**：
- 外键约束在数据库层保证引用完整性，避免程序 Bug 产生脏数据（如指向不存在的 `kb_id`）
- SQLAlchemy 模型中必须同步声明 `sa.ForeignKey(...)`，与 Alembic 迁移脚本保持一致
- 模型中应补充 `relationship` 定义，支持 ORM 级联操作和跨表查询

---

## 5. 相关文档

- [架构设计文档](../docs/ARCHITECTURE.md)
- [接口文档](API.md)
- [开发指南](../docs/DEVELOPMENT.md)
- [UI 设计规范](../../frontend/docs/UIDESIGN.md)
