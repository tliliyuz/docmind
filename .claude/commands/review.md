# /review — 项目代码审查

审查当前分支或指定范围的代码变更，对照项目设计文档与编码规范逐项检查，输出违规清单与修复建议。

## 审查流程

### 第 1 步：确定审查范围

```bash
# 若用户未指定范围，默认对比 origin/main
git diff --name-only origin/main...HEAD
```

若用户指定了范围（如 `HEAD~3..HEAD`、`dev`），以用户指定为准。

### 第 2 步：读取变更文件内容

对每个变更文件，读取完整内容或关键 diff 片段。

### 第 3 步：对照文档检查（最高优先级）

**必须逐条对照以下文档中的约束进行审查：**

| 变更涉及 | 必读文档 | 重点检查项 |
|:---|:---|:---|
| 后端接口 | `backend/docs/API.md` | 路由路径、响应格式 `{code,message,data}`、错误码是否在枚举范围内、SSE 事件结构 |
| 数据库模型/schema | `backend/docs/DATABASE.md` | 表结构、索引定义、`ForeignKey` 声明、级联策略（§4）、`relationship` 双向关联 |
| RAG 管线 | `backend/docs/RAG_PIPELINE.md` | 检索/融合/Prompt/Rewrite/意图/Evidence/Trace 各阶段设计是否被遵循 |
| 前端页面/组件 | `frontend/docs/FRONTEND.md` | 交互流程是否匹配页面状态机、SSE 处理方式、表单反馈行为 |
| 前端样式 | `frontend/docs/UIDESIGN.md` | 是否硬编码颜色/字号/间距（必须用 `--dm-*` Design Token） |
| 架构/技术选型 | `docs/ARCHITECTURE.md` | 技术选型是否偏离、核心链路是否被破坏 |
| 新增依赖/环境 | `docs/DEVELOPMENT.md` | 环境要求是否变更、项目结构是否遵循 |

**文档一致性专项检查（必须执行）：**

- [ ] **文档元信息同步**：检查被修改文档的「文档版本」和「最后更新」日期是否已更新；不一致视为 🟡 规范问题
- [ ] **待办项时效性**：检查文档中的 `TODO` / `待办` / `待补充` 是否已在代码中实现但仍未移除；已过期待办视为 🟡 规范问题，误导性待办（如「当前仍残留」实际已移除）视为 🔴 严重问题
- [ ] **测试跟踪一致性**：检查 `docs/tests/TEST_CASES.md` 中标记为 ✅ 的用例，是否在测试代码中存在对应实现；不存在视为 🔴 严重问题。同时对照 CLAUDE.md 测试质量约束检查用例质量（详见第 4 步「测试规范检查项」）
- [ ] **进度偏差**：检查 `docs/ROADMAP.md` 中标记为 ✅ 的任务是否真实完成；检查「本阶段不做/推迟」项是否有代码提前实现（过度设计）
- [ ] **已实现功能提示待补充**：检查文档中是否仍有「待补充」「TODO」描述某功能，而该功能已在当前分支实现；视为 🟡 规范问题
- [ ] **时区一致性**：DATABASE.md §0 / ARCHITECTURE.md §11 的时区约定是否与代码实现一致（`UTCDateTime` TypeDecorator / `mysql_url` 含 `time_zone` / `datetime.now(timezone.utc)` / Pydantic 原生 `datetime` 类型）？不一致视为 🟡 规范问题

**若发现文档与代码冲突，标记为 🔴 严重问题，必须与开发人员确认。**

### 第 4 步：对照编码规范检查

逐项检查 CLAUDE.md 中「关键约定」节的每一条：

#### 后端规范检查项

- [ ] 导入是否使用 `from app.xxx` 绝对路径（禁止 `from ..core` 相对导入）
- [ ] api/ 层是否只做参数校验 + 调用 service（业务逻辑不得写在 api/ 层）
- [ ] IO 操作是否使用 async/await
- [ ] DB session 是否通过 `get_db()` 依赖注入获取
- [ ] 环境变量是否从 `settings` 单例读取（禁止硬编码）
- [ ] 新接口是否有 Pydantic schema（禁止裸用 dict）
- [ ] 所有 `*_id` 字段是否声明了 `sa.ForeignKey(...)`，级联策略是否对齐 DATABASE.md §4
- [ ] `default=0` 等 Python 默认值是否同步 `server_default=sa.text('0')`
- [ ] 业务异常是否继承 `AppException`
- [ ] **时区四层检查**（对齐 ARCHITECTURE.md §12）：
  1. **ORM 模型** — 所有 `DateTime` 列是否使用 `UTCDateTime` TypeDecorator（`app/models/_types.py`），而非裸 `DateTime` 或 `DateTime(timezone=True)`？**裸 `DateTime` 视为 🔴 严重问题**（MySQL 驱动返回 naive datetime，API 序列化无时区后缀，前端偏差 8 小时）
  2. **Python 代码** — 是否使用 `datetime.now(timezone.utc)`（禁止 `datetime.utcnow()` / `datetime.utcfromtimestamp()`）？是否残存 `replace(tzinfo=timezone.utc)` 手动补丁（TypeDecorator 已统一处理，手动补丁冗余且易遗漏）？
  3. **MySQL 连接** — `config.py` 的 `mysql_url` 是否包含 `init_command=SET time_zone='%2B00:00'`？缺失时 `CURRENT_TIMESTAMP` 返回 MySQL 系统时区而非 UTC
  4. **Pydantic Schema** — 时间字段类型是否为原生 `datetime`（而非自定义 PlainSerializer 补丁）？ORM 层 TypeDecorator 已确保返回 aware datetime，Pydantic 自然序列化 `Z` 后缀
- [ ] JWT payload 提取是否有 `KeyError/ValueError` 防护，返回 401 而非 500

#### 前端规范检查项

- [ ] 是否使用 Composition API + `<script setup>`
- [ ] 请求是否走 `api/` 封装（禁止组件内直接 axios）
- [ ] 状态是否提升到 Pinia store
- [ ] 样式是否严格使用 `--dm-*` Design Token（禁止硬编码颜色/字号/间距）
- [ ] 时间显示是否通过 `new Date(isoString)` 转换（禁止手动解析字符串再拼接时区偏移——JavaScript 自动识别 `Z`/`+00:00` 后缀为 UTC → 本地时区）
- [ ] 交互流程是否遵循 FRONTEND.md 页面状态机

#### 通用规范检查项

- [ ] 注释、变量名、提交信息是否使用中文
- [ ] 是否过度设计（超出当前 Phase 范围）
- [ ] 是否在 `docs/CHANGELOG.md` 中记录了本次变更

#### 测试规范检查项（对照 CLAUDE.md 测试质量约束）

- [ ] **测试分层完整性**：变更涉及的 service 模块是否同时存在 API 层测试（`test_*_api.py`，mock service 入口 → 验证序列化/校验/错误码）和 Service 层测试（`test_*_service.py`，mock DB session + 真实 service 函数 → 验证业务逻辑/SQL/异常）？**仅有一层视为 🔴 严重问题**——参考 `_fill_real_chunk_count` NameError 逃逸教训：API 层全量 mock 了 `update_kb`，Bug 对 API 测试完全不可见
- [ ] **禁止复制生产代码到测试**：检查测试中是否出现与生产函数**逻辑相同**的代码块（如 for-loop + dict 拼接复刻了 `_build_sources` 的内部实现），而非 `from module import _private_func` 调用真实函数？复制视为 🟡 规范问题——源码逻辑变更时测试静默过期（测试的是旧逻辑的副本）
- [ ] **重复 mock 样板提取**：同一测试文件内是否 ≥3 处出现相同 `patch()` 组合（且 mock 对象数 ≥5）而未提取为共享 context manager / fixture / 辅助函数？未提取视为 🟡 规范问题——新增测试倾向于复制粘贴，mock 接口变更时需逐个修改
- [ ] **断言精确性**：断言是否验证**具体预期值**（内容、顺序、分数范围、错误码、异常类型），而非仅 `assert result is not None` / `assert total > 0` / `assert isinstance(...)`？弱断言视为 🟡 规范问题——测试「通过」但未验证任何正确性
- [ ] **禁止条件断言**：断言是否被包裹在 `if` 条件内（如 `if output.total >= 2: assert result == expected`）？条件断言视为 🔴 严重问题——当条件为 False 时测试静默通过，Bug 被隐藏
- [ ] **禁止直接测试私有方法**：测试是否直接调用了 `_` 前缀的私有方法/函数（如 `test_parse_results()` 直接调用 `_parse_results()`）？视为 🟡 规范问题——私有方法应通过公共 API 间接覆盖
- [ ] **测试名与行为一致**：测试函数名和 docstring 是否精确描述了实际验证的行为？名实不符视为 🟡 规范问题

### 第 5 步：安全检查

- [ ] 是否存在 SQL 注入风险（裸拼 SQL）
- [ ] 是否存在 XSS 风险（v-html 未消毒）
- [ ] 是否存在命令注入风险（os.system/subprocess 拼接用户输入）
- [ ] 敏感信息是否被硬编码（密钥、密码、token）
- [ ] 文件上传是否有类型/大小校验

### 第 6 步：输出审查报告

按以下格式输出：

```
## 📋 审查报告 — [分支名/范围]

### 审查范围
- 变更文件数：N
- 审查文档：列出实际对照的文档

### 🔴 严重问题（必须修复）
> 违反设计文档约束，或存在安全风险

### 🟡 规范问题（建议修复）
> 违反编码规范，但不影响功能

### 🔵 改进建议（可选）
> 代码质量、可维护性方面的建议

### 🧪 测试质量
> 测试分层、断言精度、mock 复用、代码复制

- [ ] 是否仅有一层测试（API 或 Service），另一层缺失
- [ ] 是否存在复制生产代码到测试的现象
- [ ] 是否存在大量重复 mock 样板未提取
- [ ] 断言是否精确（验证具体值而非 None/类型）
- [ ] 是否存在条件断言（if 包裹 assert）
- [ ] 是否直接测试了私有方法

### ✅ 检查通过项
> 逐项列出所有通过的检查

### 📄 文档一致性检查
> 文档元信息、待办项、测试跟踪、进度偏差

- [ ] 被修改文档的版本号/最后更新日期是否同步更新
- [ ] 文档中的 TODO / 待办 / 待补充 是否已过期（代码已实现但未移除）
- [ ] TEST_CASES.md 中标记 ✅ 的用例是否在实际测试代码中存在
- [ ] ROADMAP.md 中标记 ✅ 的任务是否真实完成
- [ ] 已移除依赖/已废弃方案在文档中是否仍被描述为「当前使用」「仍残留」

### 📝 CHANGELOG.md 检查
> 是否记录了变更，记录是否完整
```

---

## 注意事项

- **文档冲突优先**：代码与设计文档不一致时，标记为严重问题，不自行判断孰对孰错
- **文档同步优先**：文档元信息（版本/日期）、待办项、测试跟踪状态必须与代码实际状态同步；文档过期与代码 bug 同等严重
- **不要只看 diff**：关键文件需要读取完整内容，diff 可能遗漏上下文
- **安全第一**：安全问题一律标记为严重
- **审查要有据可查**：每条问题必须引用对应的文档/规范条目
- **进度偏差必报**：已实现功能在文档中仍提示待补充、已标记 ✅ 的测试用例无对应代码、已移除依赖在文档中仍写「当前残留」等，均为文档与代码不一致，必须列出
