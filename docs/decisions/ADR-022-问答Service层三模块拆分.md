# ADR-022: 问答 Service 层三模块拆分

**状态**：已采纳（2026-06-18）
**决策者**：开发团队
**关联文档**：ARCHITECTURE.md §5 / ADR-017

## 上下文

`chat_service.py` 随功能迭代膨胀至 1015 行，包含三类职责：

1. **入口与校验**：`chat()` 主流程、知识库选择、权限校验准备
2. **SSE 流生成**：`_generate_sse_stream()` 生成器（~350 行）、固定响应生成、消息持久化
3. **辅助函数**：历史加载、标题生成、来源构建、引用索引提取

这些函数被多个模块 import（如 `chat_router.py` 通过 `from app.services.chat_service import build_sources` 直接引用辅助函数），简单拆分为独立模块会导致批量修改调用方。

## 决策

### 1. 三模块按职责拆分

| 模块 | 职责 | 关键函数 |
|:---|:---|:---|
| `chat_service.py` | 入口 + 校验 + re-export 兼容层 | `chat()`, `get_selectable_kbs()`, `_validate_and_prepare()` |
| `sse_stream.py` | SSE 流生成 + 固定响应 + 消息持久化 | `_generate_sse_stream()`, `_generate_meta_response()`, `_generate_reject_response()`, `_persist_message()` |
| `chat_helpers.py` | 问答辅助函数 | `load_history()`, `generate_title()`, `extract_citation_indices()`, `build_sources()`, `build_sources_event_data()` |

### 2. Re-export 兼容机制

`chat_service.py` 底部通过 re-export 保持向后兼容：

```python
from app.services.chat_helpers import (
    build_sources,
    build_sources_event_data,
    extract_citation_indices,
    generate_title,
    load_history,
)
from app.services.sse_stream import (
    _generate_sse_stream,
    _generate_meta_response,
    _generate_reject_response,
    _persist_message,
)
```

外部模块原有导入路径（如 `from app.services.chat_service import build_sources`）仍然有效，无需批量修改调用方。

## 理由

- **职责分离**：入口/流生成/辅助三类职责不再混杂在同一文件中
- **可维护性**：修改 SSE 逻辑只需关注 `sse_stream.py`（~350 行），而非在 1015 行中定位
- **零破坏性**：re-export 兼容层确保所有现有 import 路径不变
- **渐进式**：后续可逐步将调用方迁移到新模块路径，届时移除 re-export

## 后果

- `chat_service.py` 缩减为入口 + 校验 + re-export（~200 行）
- 新增 `sse_stream.py` 和 `chat_helpers.py` 两个模块文件
- 所有现有 import 路径保持有效，无调用方需要立即修改
- ADR-017 中描述的 DB 会话生命周期解耦在 `sse_stream.py` 中实现
