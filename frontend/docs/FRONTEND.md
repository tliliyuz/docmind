# FRONTEND — 前端交互文档

| 属性 | 值 |
|:---|:---|
| 文档版本 | v0.14 |
| 最后更新 | 2026-06-04 |
| 作者 | yuz |
| 状态 | 草稿 |

---

## 1. 全局交互架构

### 1.1 技术栈

| 层面 | 技术 | 用途 |
|:---|:---|:---|
| 框架 | Vue 3 | Composition API + `<script setup>` |
| 构建工具 | Vite | 开发服务器（端口 5173）|
| UI 组件库 | Element Plus | 表单、表格、弹窗、消息提示等 |
| 状态管理 | Pinia | 认证、聊天、知识库三个 store |
| 路由 | Vue Router | 三级路由守卫（公开/需登录/需管理员）|
| HTTP 客户端 | Axios | 请求/响应拦截器，自动处理 Token 和 401 |
| 图标 | Font Awesome 6 Free | 全站统一图标方案 |
| Markdown 渲染 | markdown-it | 答案内容解析 |

### 1.2 状态管理总览

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  auth.js    │  │  chat.js    │  │knowledge.js │
│  认证状态    │  │  聊天状态    │  │ 知识库状态   │
├─────────────┤  ├─────────────┤  ├─────────────┤
│ • user      │  │ • messages  │  │ • kbList    │
│ • token     │  │ • loading   │  │ • currentKb │
│ • isAdmin   │  │ • streaming │  │ • docList   │
│ • login()   │  │ • send()    │  │ • upload()  │
│ • logout()  │  │ • abort()   │  │ • create()  │
└─────────────┘  └─────────────┘  └─────────────┘
```

**规则**：组件内不直接调用 axios，所有请求走 `api/` 目录封装；状态提升到 Pinia，不用 props 透传超过两层。

### 1.3 全局错误处理

| 场景 | 前端行为 |
|:---|:---|
| HTTP 401 | 响应拦截器自动清除 token，跳转 `/login`（已在登录页则不动）|
| HTTP 403 | Element Plus `ElMessage.error('无权限执行此操作')` |
| HTTP 422 | 提取后端返回的字段级错误，聚焦到对应表单项 |
| HTTP 500/503 | `ElMessage.error('服务暂不可用，请稍后重试')` |
| 网络中断 | 请求超时 30s，提示 `网络异常，请检查连接` |

---

## 2. 路由与页面结构

### 2.1 路由表

> **权限模型**：后端 API 区分两种视角——user 管理自己的资源，admin 跨用户管理全部资源。前端路由对齐此模型。

**用户视角路由**（所有登录用户可访问）：

| 路径 | 页面 | 权限 | 说明 |
|:---|:---|:---|:---|
| `/` | → `/chat` | 公开 | 根路径重定向到问答页 |
| `/login` | LoginPage | 公开 | 已登录者访问自动重定向到 `/chat` |
| `/chat` | ChatPage | 需登录 | 核心问答页，默认首页（Phase 3 完整实现） |
| `/knowledge-bases` | KnowledgeList | 需登录 | 我的知识库列表（Phase 2.3.3 实现） |
| `/knowledge-bases/public` | PublicKnowledgeList | 需登录 | 公开知识库列表，浏览所有 public KB（Phase 2.5 新增） |
| `/knowledge-bases/:id` | KnowledgeDetail | 需登录（owner/admin/public KB 可查看） | 知识库详情：KB 信息 + 文档上传/管理。public KB 非 owner 只读查看 |

**管理员视角路由**（仅 admin 可访问，后端接口 Phase 5 实现）：

| 路径 | 页面 | 权限 | 说明 |
|:---|:---|:---|:---|
| `/admin/knowledge` | AdminKnowledgeList | 需管理员 | 全部知识库（跨用户），后端接口 Phase 5 |
| `/admin/documents` | AdminDocumentList | 需管理员 | 全部文档（跨库），后端接口 Phase 5 |
| `/admin/conversations` | AdminConversationList | 需管理员 | 全部会话（跨用户），后端接口 Phase 4-5 |
| `/admin/stats` | AdminStats | 需管理员 | 系统概览统计，后端接口 Phase 5 |

**兜底**：

| `*` | → `/chat` | - | 兜底重定向 |

### 2.2 路由守卫逻辑

```
用户访问某个路径
    ↓
已登录且访问 /login → 重定向 /chat
    ↓
未登录且访问需认证页 → 重定向 /login
    ↓
非 admin 访问 admin/* → 重定向 /chat
    ↓
正常放行
```

---

## 3. 登录/注册页（LoginPage）

### 3.1 页面布局

| 区域 | 交互说明 |
|:---|:---|
| 品牌区 | 渐变背景 + Logo + 标题「DocMind」+ 副标题 |
| Tab 切换 | 登录/注册 两段式切换，带动画高亮 |
| 表单区 | 用户名 + 密码输入框，带图标前缀 |
| 错误提示 | 校验失败或 API 错误时，红色提示条出现 |
| 提交按钮 | loading 时禁用并显示旋转图标 |
| 底部链接 | 「还没有账号？立即注册」互转 |

### 3.2 交互流程

**登录流程**：
```
用户输入用户名、密码
    ↓
点击「登录」→ 前端校验（用户名非空、密码≥6位）
    ↓
调用 authStore.login() → POST /api/auth/login
    ↓
成功：ElMessage.success('登录成功') → 存储 token + 解析 JWT 用户信息 → 跳转 /chat
失败：显示后端错误消息（如「用户名或密码错误」）
```

**注册流程**：
```
用户输入用户名、密码
    ↓
点击「注册」→ 前端校验
    ↓
调用 authStore.register() → POST /api/auth/register
    ↓
成功：自动切换回登录模式，清空密码框，用户需手动登录
失败：显示错误（如「用户名已存在」）
```

### 3.3 表单校验规则

| 字段 | 规则 | 错误提示 |
|:---|:---|:---|
| 用户名 | 非空，长度 ≥ 2 | 请输入用户名 / 用户名至少 2 个字符 |
| 密码 | 长度 ≥ 6 | 密码至少 6 个字符 |

---

## 4. 聊天页（ChatPage）— 核心交互

### 4.1 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  Sidebar (260px/64px收起)      │  Main Content               │
│  ─────────────────────────────┤  ─────────────────────────  │
│  Logo + 新建对话               │  Top: 知识库选择器（双下拉框）  │
│  ─────────────────────────────┤    [我的知识库 ▼] [公共知识库 ▼]│
│  会话区域（Phase 3 空态）       │    ├─ 我的知识库             │
│  • 新建对话按钮                │    └─ 公共知识库             │
│  • 历史会话列表（Phase 4 实现） │  ─────────────────────────  │
│  ─────────────────────────────┤                             │
│  [所有用户] 我的知识库           │  ─────────────────────────  │
│  • 点击进入 /knowledge-bases   │  MessageList               │
│  [所有用户] 公共知识库           │  • WelcomeScreen（空态）     │
│  • 点击进入 /kb/public         │  • User Bubble              │
│  ─────────────────────────────┤  • Assistant Bubble         │
│  [admin] 管理后台              │    - thinking box（黄色折叠） │
│  • 知识库管理 / 文档管理 / …   │    - markdown content       │
│  ─────────────────────────────┤    - sources box            │
│  用户头像 + 退出按钮             │  ─────────────────────────  │
│  • 点击头像→个人资料（预留）     │  ChatInput                   │
│  • 点击退出→提示+跳转登录页      │  • 输入框 + 发送按钮          │
│                                  │  • 深度思考开关               │
│                                  │  • 快捷键：Enter 发送          │
└──────────────────────────────┴─────────────────────────────┘
```

**知识库选择器**（ChatPage 顶部）：

- 数据来源：`GET /api/knowledge-bases/selectable`（Phase 3 新增接口）
- 渲染方式：两个独立的 `<el-select>` 并排——左侧「我的知识库」下拉仅列出当前用户创建的 KB，右侧「公共知识库」下拉列出所有 `visibility=public` 的 KB（含 `username` 标注所有者）
- 两个下拉框各自独立选中，互不干扰；当用户选择了私有 KB 又选择公共 KB 时，后者覆盖前者（单一 `selectedKBId` 语义）
- 分组标题样式：`el-select-group__title` 使用 `--dm-text-3xs` + 大写 + 加粗，与可选项明显区分
- 默认选中：优先 localStorage 缓存 `last_kb_id`，否则选中「我的知识库」第一个；若用户无私有 KB，则选中「公共知识库」第一个
- 切换 KB：新建会话（`conversation_id=null`），不同 KB 的对话使用不同会话

### 4.2 核心问答交互流程

```
用户选择知识库（下拉选择器，默认最近使用的知识库）
    ↓
用户在输入框输入问题，按 Enter 或点击发送
    ↓
前端立即在消息列表插入「用户消息」+「助手占位」（typing 动画）
    ↓
调用 chatStore.sendMessage() → POST /api/chat（SSE）
    ↓
接收 SSE 事件流：
  event: meta      → 记录 conversation_id（新对话时后端自动创建）、task_id
  event: thinking  → 展开思考过程框（黄色折叠面板），实时追加内容
  event: message   → 逐字追加到助手消息内容区（Markdown 实时渲染）
  event: sources   → 在消息底部渲染引用来源卡片（每个片段标注 [来源N] 编号，与 LLM 回答中的引用一一对应）
  event: finish    → 关闭 typing，更新消息 ID，首轮保存 title
  event: error     → 替换为错误提示，关闭 typing
  : ping\n\n       → SSE 心跳注释帧（15s 间隔），前端忽略
    ↓
用户可点击「停止生成」中断 SSE 连接
```

**会话自动创建**（Phase 3 单轮模式）：
- 新对话时前端传 `conversation_id=null`，后端自动创建会话并通过 `event: meta` 返回新 `conversation_id`
- 前端收到 `meta` 事件后更新 `chatStore.currentConversationId`，后续追问使用该 ID
- Phase 3 单轮问答不注入历史（`history=[]`），Phase 4 开始支持多轮记忆

**对话标题生成**：
- 首轮问答的 `event: finish` 中返回 `title` 字段（截取用户问题前 12 字）
- 前端将 title 存入会话列表，侧边栏显示为会话标题
- 后续轮次 `finish` 事件不返回 title（或为 null），标题保持不变

**thinking_content 展示**（仅 `deep_thinking=true` 时）：
- `event: thinking` 到达时，助手气泡内展开黄色边框折叠面板，内容逐字追加
- 默认展开，用户可手动折叠
- **仅前端实时展示，不落库**：刷新页面后 thinking 内容丢失，消息历史中不存在

**SSE 心跳处理**：
- 后端每 15 秒发送 `: ping\n\n` 注释帧防止代理超时断连
- 浏览器原生 `EventSource` / `fetch` 读取 SSE 时自动忽略注释帧（以 `:` 开头），前端无需特殊处理

### 4.3 输入框行为（ChatInput）

| 操作 | 行为 |
|:---|:---|
| 输入文字 | 实时显示字数统计（≤ 2000 字符）|
| Enter | 直接发送 |
| Shift + Enter | 换行 |
| 发送中 | 输入框禁用，按钮变为「停止生成」|
| 空内容发送 | 输入框轻微抖动，不触发请求 |
| 深度思考开关 | 切换 `deep_thinking` 参数，默认关闭 |

### 4.4 消息列表行为（MessageList）

| 场景 | 行为 |
|:---|:---|
| 新消息到达 | 自动滚动到底部；若用户已手动上滚，显示「新消息」浮动按钮 |
| 代码块 | 支持一键复制，hover 显示复制按钮 |
| 引用来源 | 点击文档名可预览该分块内容（弹窗或展开）|
| 重新生成 | 每条助手消息 hover 显示「重新生成」按钮，重新发送上一条问题 |
| 长消息 | 默认展开，无截断 |

### 4.5 侧边栏导航行为

#### 4.5.1 会话区域

| 操作 | 行为 |
|:---|:---|
| 点击「新建对话」| 清空当前消息列表，重置 `conversation_id=null`，首轮问答时后端自动创建会话并通过 `event: meta` 返回新 ID，标题由首轮 `finish` 事件自动生成 |
| 点击历史会话 | 加载该会话的消息历史，切换 conversation_id |
| 悬停会话项 | 显示重命名和删除图标按钮 |
| 重命名 | 点击后标题变为可编辑输入框，Enter 保存，Esc 取消 |
| 删除 | 确认弹窗 `ElMessageBox.confirm`，确认后删除并清空当前会话（如果是当前打开的）|
| 会话分组 | 按时间分组：今天 / 昨天 / 近 7 天 / 更早 |

#### 4.5.2 知识库导航（所有用户可见）

| 操作 | 行为 |
|:---|:---|
| 点击「我的知识库」| 跳转 `/knowledge-bases`，显示当前用户的知识库列表 |
| 点击「公共知识库」| 跳转 `/knowledge-bases/public`，浏览所有 `visibility=public` 的知识库 |
| 高亮状态 | 当路由在 `/knowledge-bases`（不含 `/public`）或 `/knowledge-bases/:id` 时，「我的知识库」高亮；当路由在 `/knowledge-bases/public` 时，「公共知识库」高亮 |

#### 4.5.3 管理后台导航（仅 admin 可见）

> **注意**：管理后台的后端接口排期至 Phase 5。Phase 2.3.3 仅完成前端页面，接口联调待 Phase 5。

| 操作 | 行为 |
|:---|:---|
| 点击「知识库管理」| 跳转 `/admin/knowledge`（全部知识库，跨用户） |
| 点击「文档管理」| 跳转 `/admin/documents`（全部文档，跨库） |
| 点击「会话管理」| 跳转 `/admin/conversations`（Phase 4 实现） |
| 点击「系统概览」| 跳转 `/admin/stats`（Phase 5 实现） |

#### 4.5.4 用户栏行为

| 操作 | 行为 |
|:---|:---|
| 点击头像/用户名 | 跳转个人资料页（Phase 1 预留，当前无操作） |
| 点击退出图标 | `ElMessage.success('已退出登录')` → 清除 token → 跳转 `/login` |

#### 4.5.5 侧边栏展开/收起

- **切换按钮**：侧边栏顶部右侧，`fa-chevron-left`（展开态）/ `fa-chevron-right`（收起态）
- **展开态**（260px）：Logo 图标 + 「知识库问答平台」副标题 + 新建对话按钮（含文字）+ 导航项（图标 + 文字）+ 用户信息（头像 + 用户名 + 角色 + 退出按钮）
- **收起态**（64px）：Logo 图标居中 + 新建对话「+」图标按钮 + 导航项（仅图标，hover 显示 `title` tooltip）+ 用户头像居中
- **过渡动画**：`width var(--dm-transition-normal)`（0.2s ease）
- **状态管理**：`Sidebar.vue` 本地 `ref`，不持久化（刷新恢复展开）
- **产品名移除**：Logo 区域不显示「DocMind」产品名，标题由 `AppLayout.vue` 顶部 header 展示（Chat 路由显示「DocMind」）

### 4.6 空状态（WelcomeScreen）

当消息列表为空时显示：
- 大 Logo + 欢迎语「我是 DocMind，你的企业知识助手」
- 快捷问题卡片（如「报销流程是怎样的？」「入职需要准备什么？」）
- 点击快捷问题直接填入输入框并发送

---

## 5. 知识库管理页（KnowledgeList — `/knowledge-bases`）

> **权限**：所有登录用户。用户只能看到和管理自己的知识库。
> **对应后端**：`GET/POST /api/knowledge-bases`（已实现）

### 5.1 页面布局

网格布局展示知识库卡片 + 顶部操作栏：
- 搜索框：按名称过滤知识库
- 新建按钮：弹窗创建知识库

### 5.2 知识库卡片交互

| 元素 | 交互 |
|:---|:---|
| 卡片整体 | hover 边框高亮 + 阴影上浮，点击进入 `/knowledge-bases/:id`（知识库详情页） |
| 图标 | 根据名称关键词自动匹配部门色（HR 红 / IT 蓝 / 行政绿等） |
| 文档数/分块数 | 实时显示 |
| 操作菜单 | 编辑名称描述 / 删除（确认弹窗） |

### 5.3 新建知识库弹窗

```
点击「新建知识库」
    ↓
弹窗：名称（必填）+ 描述（选填）
    ↓
确认 → POST /api/knowledge-bases
    ↓
成功：弹窗关闭，卡片列表 prepend 新项
失败：表单错误提示
```

### 5.4 编辑/删除

| 操作 | 行为 |
|:---|:---|
| 编辑 | 弹窗预填名称+描述+可见性 → 确认 → PUT `/api/knowledge-bases/{id}` |
| 删除 | `ElMessageBox.confirm`（危险色） → 确认 → DELETE（202 异步） → 卡片移除 |

---

## 5.5 知识库详情页（KnowledgeDetail — `/knowledge-bases/:id`）

> **权限**：KB 所有者、admin 或 public KB 的任意登录用户。**Phase 2.3.3 新增页面**。
> **对应后端**：`GET /api/knowledge-bases/{id}` + 文档接口族（`/api/knowledge-bases/{kb_id}/documents/**`）
>
> **非 owner 访问 public KB**：仅可查看 KB 基本信息 + 统计。文档上传区、文档表格（含筛选/分页）、编辑/删除按钮对非 owner 隐藏。用户可从该页面点击「开始问答」跳转到 `/chat?kb_id=xxx` 使用该 KB 进行问答。

### 5.5.1 页面布局

```
┌─────────────────────────────────────────────────────────────┐
│  页面标题栏                                                   │
│  ← 返回知识库列表    KB 名称 + 描述    [编辑] [删除]            │
├─────────────────────────────────────────────────────────────┤
│  KB 统计卡片行                                                │
│  [文档总数: 15] [分块总数: 340] [创建时间: 2026-05-11]         │
├─────────────────────────────────────────────────────────────┤
│  文档上传区域（见 §6.2）                                       │
│  ┌ - - - - - - - - - - - - - - - - - - - - - - - - - - ┐  │
│  │     📁  拖拽文件到此处，或点击选择文件                      │  │
│  │     支持 pdf / docx / md / txt，单文件 ≤ 50MB              │  │
│  └ - - - - - - - - - - - - - - - - - - - - - - - - - - ┘  │
├─────────────────────────────────────────────────────────────┤
│  文档表格（见 §6.1）                                          │
│  [状态筛选] [文件名搜索] [排序]                                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 文件名 │ 类型 │ 大小 │ 状态 │ 分块数 │ 上传时间 │ 操作    │  │
│  └───────────────────────────────────────────────────────┘  │
│  分页器                                                      │
└─────────────────────────────────────────────────────────────┘
```

### 5.5.2 交互流程

```
进入 /knowledge-bases/:id
    ↓
GET /api/knowledge-bases/{id} → 显示 KB 信息 + 统计
    ↓
判断是否 owner：
  ├─ 是 owner → GET /api/knowledge-bases/{kb_id}/documents → 显示文档列表
  └─ 非 owner（访问 public KB）→ 跳过文档列表，仅显示 KB 基本信息 + 「开始问答」入口
```

---

## 5.6 管理员知识库列表（AdminKnowledgeList — `/admin/knowledge`）

> **权限**：admin。**后端接口 Phase 5 实现**，Phase 2.3.3 仅完成前端页面。
> **对应后端**：`GET /api/admin/knowledge-bases`（Phase 5）

与用户视角的区别：
- 可查看**全部用户**的知识库（含 `username` 字段）
- 可按 `user_id` 筛选
- 可查看全部用户的知识库（含 private KB）
- 可编辑 KB 元数据（名称/描述/visibility 修正）
- 可删除 KB（违规清理），展示原 owner
- 不可创建新 KB 或上传文档

---

## 5.7 公共知识库浏览页（PublicKnowledgeList — `/knowledge-bases/public`）

> **权限**：所有登录用户。**Phase 2.5 新增页面**。
> **对应后端**：`GET /api/knowledge-bases/public`（已实现）

### 5.7.1 页面定位

与「我的知识库」（§5）并列的独立页面，展示所有 `visibility=public` 且 `status=active` 的知识库。用户可浏览和进入 public KB 进行问答，但不可编辑/删除/上传文档。

### 5.7.2 与「我的知识库」的差异

| 维度 | 我的知识库 | 公共知识库 |
|:---|:---|:---|
| 数据源 | `GET /api/knowledge-bases`（仅当前用户） | `GET /api/knowledge-bases/public`（跨用户） |
| 卡片信息 | KB 名称、描述、文档数、分块数 | 额外显示 `username`（KB 所有者） |
| 操作菜单 | 编辑、删除 | 无（仅查看） |
| 新建按钮 | 有（新建知识库） | 无 |
| 可搜索 | 是 | 是 |
| 点击卡片 | 进入详情页（可管理文档） | 进入详情页（只读，不可上传/管理文档） |

### 5.7.3 页面布局

与 KnowledgeList（§5.1）基本一致，区别：
- 页面标题为「公共知识库」
- 无「新建知识库」按钮
- 卡片无操作菜单（无编辑/删除按钮）
- 卡片额外显示 owner 用户名
- 空状态文案：「暂无公开知识库」

---

## 6. 文档管理（KnowledgeDetail 页面内 — `/knowledge-bases/:id`）

> **权限**：KB 所有者或 admin。文档管理是知识库详情页的内嵌功能，不是独立页面。
> **对应后端**：`POST/GET/DELETE /api/knowledge-bases/{kb_id}/documents/**`（已实现）

### 6.1 文档表格

Element Plus 表格，位于知识库详情页内，展示该 KB 下的所有文档。支持：
- 按状态筛选（多选下拉，默认显示全部）
- 按文件名模糊搜索
- 按 `created_at` 排序（默认倒序）
- 分页（20 条/页）

**表格列**：

| 列 | 说明 |
|:---|:---|
| 文件名 | 显示文件名，点击可展开详情 |
| 类型 | pdf / docx / md / txt |
| 大小 | 格式化显示（KB/MB） |
| 状态 | 状态标签（见 §6.5） |
| 分块数 | `chunk_count`（终态文档显示实际值，非终态显示 `-`） |
| 上传时间 | `created_at` 格式化 |
| 操作 | 查看分块 / reprocess（仅 partial_failed/failed）/ 删除 |

### 6.2 上传交互

文档上传入口在知识库详情页（`/knowledge-bases/:id`）内，上传自动归属该 KB。

```
用户在知识库详情页
    ↓
拖拽文件到上传区 或 点击选择文件
    ↓
前端校验：
  - 格式（pdf/docx/md/txt），拒绝 .doc（提示「请先转换为 .docx」）
  - 大小（≤ 50MB）
    ↓
通过 multipart/form-data 上传
  POST /api/knowledge-bases/{kb_id}/documents
  - axios onUploadProgress 显示实时进度（百分比 + 速度 + 剩余时间）
    ↓
立即在文档列表新增一行，status = uploaded
    ↓
开始轮询 GET /api/knowledge-bases/{kb_id}/documents/{id}
  （非终态 2s 间隔，终态停止，5 分钟超时）
    ↓
status 变为终态（completed / success_with_warnings / partial_failed / failed）
→ 停止轮询，更新列表行
```

### 6.3 同名文件冲突处理

| 场景 | 用户操作 | 前端提示 |
|:---|:---|:---|
| 无冲突 | 正常上传 | 无提示 |
| 同名且终态 | 弹出确认框：「文档 `xxx.pdf` 已存在，是否覆盖？」 | 用户确认后 `force=true` 重新上传 |
| 同名且处理中 | 拒绝 | `ElMessage.warning('文档正在处理中，请稍后再试')` |
| 同名 + force + 旧文档处理中 | 拒绝 | `ElMessage.error('旧文档仍在处理中，无法覆盖')` |

### 6.4 文档状态轮询

```js
// 轮询策略
const POLL_INTERVAL = 2000       // 非终态 2s
const POLL_TIMEOUT = 5 * 60 * 1000  // 5 分钟超时

function startPolling(docId) {
  const timer = setInterval(async () => {
    const { data } = await getDocumentDetail(docId)
    if (isTerminal(data.status)) {
      clearInterval(timer)  // 终态停止
    }
  }, POLL_INTERVAL)

  // 超时保护
  setTimeout(() => clearInterval(timer), POLL_TIMEOUT)
}
```

**终态判定**（前端共享 `TERMINAL_STATUSES` 常量）：
```js
const TERMINAL_STATUSES = [
  'completed', 'success_with_warnings', 'partial_failed', 'failed'
]
```

### 6.5 文档状态标签映射

| 状态 | 标签样式 | 图标 | 用户可见行为 |
|:---|:---|:---|:---|
| `uploaded` | `--dm-info` 色 | `fa-upload` | 等待处理 |
| `parsing` | `--dm-info` 色 | `fa-spinner fa-spin` | 解析中 |
| `chunking` | `--dm-info` 色 | `fa-spinner fa-spin` | 分块中 |
| `embedding` | `--dm-info` 色 | `fa-spinner fa-spin` | 向量化中 |
| `vector_storing` | `--dm-info` 色 | `fa-spinner fa-spin` | 写入向量库 |
| `completed` | `--dm-success` 色 | `fa-check-circle` | 可查看分块，不可重处理 |
| `success_with_warnings` | `--dm-success` 色 | `fa-check-circle` + warning 角标 | 部分警告但可用，不可重处理 |
| `partial_failed` | `--dm-warning` 色 | `fa-exclamation-triangle` | 显示失败比例，**可 reprocess** |
| `failed` | `--dm-danger` 色 | `fa-times-circle` | 显示错误原因，**可 reprocess** |
| `deleting` | 灰色 | `fa-spinner fa-spin` | 清理中（完成后物理删除行） |

### 6.6 上传进度反馈

```js
// axios onUploadProgress
const { data } = await api.post(
  `/knowledge-bases/${kbId}/documents`,
  formData,
  {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
      const speed = (progressEvent.loaded / (Date.now() - startTime) * 1000 / 1024).toFixed(0) // KB/s
      // 显示：百分比 + 上传速度 + 预估剩余时间
      uploadState.value = { percent, speed, eta: computeEta(progressEvent) }
    }
  }
)
```

**上传状态阶段**：
```
选择文件 → 上传中（百分比 + 速度） → 已上传（等待处理） → 处理中（轮询状态） → 完成/失败
```

### 6.7 空状态

知识库无文档时显示：
- 图标 + 「暂无文档」
- 「上传第一个文档」引导按钮

### 6.8 分块预览

文档详情展开面板（表格行内展开或弹窗）展示分块列表（分页，20 条/页）：
- 默认返回 `preview`（截断 200 字符）
- 点击展开可查看完整 `content`
- 显示 chunk_index + token_count + 页码等 metadata

### 6.9 reprocess（重新处理）

仅 `partial_failed` / `failed` 状态文档显示「重新处理」按钮：
```
点击「重新处理」
    ↓
POST /api/knowledge-bases/{kb_id}/documents/{id}/reprocess
    ↓
成功：文档状态重置为 parsing，重新开始轮询
失败：ElMessage.error 显示错误
```

---

## 7. 管理后台交互（admin 专属）

> **实现状态**：管理后台后端接口均排期至 Phase 5。Phase 2.3.3 仅完成前端页面开发，使用 mock 数据或空状态展示。

### 7.1 管理员导航

Sidebar「管理后台」分组，仅 `role === 'admin'` 可见：
- 知识库管理 → `/admin/knowledge`（全部知识库，跨用户）
- 文档管理 → `/admin/documents`（全部文档，跨库）
- 会话管理 → `/admin/conversations`（Phase 4-5 实现）
- 系统概览 → `/admin/stats`（统计卡片）

### 7.2 Admin 文档管理页（`/admin/documents`）

> **后端接口**：`GET /api/admin/documents`（Phase 5 实现）

与 KB 内文档表格的区别：
- 数据源为全部文档（跨库跨用户）
- 额外显示 `kb_name` 列和 `username` 列（或通过 `kb_id` 关联）
- 可按 `kb_id` 筛选
- 不可上传（上传入口在 KB 详情页内），仅查看/筛选

### 7.3 Admin 知识库管理页（`/admin/knowledge`）

> **后端接口**：`GET /api/admin/knowledge-bases`（Phase 5 实现）

与用户 KB 列表（§5）的区别：
- 可查看全部用户的知识库（含 private KB），含 `username` 列
- 可按 `user_id` 筛选
- 可编辑 KB 元数据（名称/描述/visibility 修正，如离职员工 KB 转 public）
- 可删除 KB（违规清理），展示原 owner
- 不可创建新 KB 或上传文档

### 7.4 系统概览页（`/admin/stats`）

> **后端接口**：`GET /api/admin/stats`（Phase 5 实现）

顶部四张统计卡片：用户总数、知识库数、文档总数、总问答数。点击卡片可下钻到对应管理页。

---

## 8. 组件交互规范

### 8.1 按钮状态

| 状态 | 视觉 | 交互 |
|:---|:---|:---|
| 默认 | 主色背景 | 可点击 |
| hover | 背景加深 + 阴影 | 手型光标 |
| loading | 禁用 + 旋转图标 | 不可点击，不重复提交 |
| disabled | 透明度 0.4-0.6 | 不可点击 |

### 8.2 表单反馈

| 场景 | 反馈方式 |
|:---|:---|
| 前端校验失败 | 表单项红色边框 + 下方文字提示 |
| 提交成功 | `ElMessage.success('操作成功')` |
| 提交失败 | `ElMessage.error(msg)` 或表单内错误提示 |
| 异步操作 | 按钮 loading，操作完成后 toast 提示 |
| 退出登录 | `ElMessage.success('已退出登录')` → 清除 token → 跳转登录页 |
| 登录成功 | `ElMessage.success('登录成功')` → 跳转 /chat |

### 8.3 加载状态

| 场景 | 加载方式 |
|:---|:---|
| 页面初始化 | 骨架屏或 spinning 全屏遮罩 |
| 表格数据 | 表格内 spinning |
| 发送消息 | 输入框禁用 + typing 动画 |
| 上传文件 | 进度条或圆形进度 |

### 8.4 确认操作

删除类操作统一使用 `ElMessageBox.confirm`：
```
标题：确认删除？
内容：删除后不可恢复，是否继续？
确认按钮：危险色（红色）
取消按钮：默认
```

---

## 9. SSE 流式输出交互细节

### 9.1 连接管理

```js
// 使用 fetch + ReadableStream 读取 SSE（推荐，支持 POST 请求）
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ question, kb_id, conversation_id, deep_thinking })
})

const reader = response.body.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })

  // 按 \n\n 分割 SSE 事件
  const events = buffer.split('\n\n')
  buffer = events.pop()  // 保留未完成的事件片段

  for (const event of events) {
    if (!event.trim()) continue
    parseSSEEvent(event)  // 解析 event: xxx\ndata: {...}
  }
}

// 手动中断
function abort() {
  reader.cancel()
  chatStore.streaming = false
}
```

> **为什么不用 EventSource**：`EventSource` API 仅支持 GET 请求，无法发送 POST body。问答请求体包含 `question`、`kb_id` 等参数，必须用 `fetch + ReadableStream` 实现 SSE 读取。

### 9.2 SSE 心跳处理

后端每 **15 秒**发送 SSE 注释帧 `: ping\n\n`，防止 Nginx/Cloudflare 代理超时断连。注释帧以 `:` 开头，SSE 协议规定客户端忽略注释行，前端解析时直接跳过：

```js
function parseSSEEvent(raw) {
  const lines = raw.split('\n')
  let event = 'message'
  let data = ''

  for (const line of lines) {
    if (line.startsWith(':')) continue  // 忽略心跳注释帧
    if (line.startsWith('event: ')) event = line.slice(7)
    else if (line.startsWith('data: ')) data = line.slice(6)
  }

  return { event, data: data ? JSON.parse(data) : null }
}
```

### 9.3 事件处理状态机

```
[idle] --发送请求--> [streaming]
[streaming] --收到 finish --> [idle]
[streaming] --收到 error --> [error]
[streaming] --用户点击停止 --> [idle]
```

### 9.4 事件处理详情

| 事件类型 | 触发条件 | 前端处理 |
|:---|:---|:---|
| meta | 连接建立后首个事件 | 记录 `conversation_id`（新对话时后端自动创建）、`task_id` |
| thinking | `deep_thinking=true` 时 | 助手气泡内展开黄色边框折叠面板，内容逐字追加。**仅实时展示，不落库**（刷新丢失） |
| message | 正常生成 | 逐字追加到助手消息内容区，Markdown 实时渲染 |
| sources | 检索结果就绪（message 前或后） | 消息底部渲染引用来源卡片（[来源N] 编号 + 文档名 + 页码 + 内容摘要），`chunk_index` 与 LLM Prompt 编号一致 |
| finish | 全部输出完毕 | 关闭 typing 动画，更新消息 ID，首轮保存 title，记录 token_usage |
| error | 检索/LLM 异常 | 替换 typing 为错误提示卡片，关闭 streaming 状态 |
| (注释帧) | 每 15s | `: ping\n\n`，解析时跳过，用户不可见 |

### 9.5 内容渲染策略

| 事件类型 | 渲染方式 |
|:---|:---|
| thinking | 黄色边框卡片，内容逐字追加，默认展开可手动折叠 |
| message | Markdown 实时渲染，代码块高亮，支持一键复制 |
| sources | 折叠面板，默认展开，每条显示 [来源N] 标签 + 文档名 + 页码 + 内容摘要（截断 200 字符） |

---

## 10. 响应式设计边界

当前版本为桌面端优先，最小适配宽度 **1280px**。以下布局在不同宽度下的行为：

| 宽度 | 行为 |
|:---|:---|
| ≥ 1280px | 完整三栏/双栏布局 |
| < 1280px | Sidebar 可收起为图标栏（64px），仅显示图标 |
| < 768px | 当前版本不做适配，提示「请使用桌面端访问」|

---

## 11. 已知 TODO

| 模块 | 当前状态 | Phase 3 实现 | 后续 Phase |
|:---|:---|:---|:---|
| ChatPage | ✅ 已实现 | KB 选择器、ChatInput、MessageList、MessageItem、WelcomeScreen、SSE 解析器、Markdown 渲染器、sources 展示 | Phase 4：历史会话列表集成、多轮对话 |
| ChatPage Sidebar | ✅ 已实现 | 会话区域空态 + 「新建对话」按钮（清空消息列表 + conversation_id=null，已在 /chat 页时清空；route 高亮） | Phase 4：历史会话列表、重命名、删除、按时间分组 |
| ChatInput | ✅ 已实现 | 输入框 ≤2000字计数 + Enter发送/Shift+Enter换行 + 深度思考开关 + 停止生成按钮 + 空输入抖动 | — |
| MessageList | ✅ 已实现 | 自动滚动底部 + 手动上滚「新消息」浮动按钮 + MessageItem 渲染 | — |
| MessageItem | ✅ 已实现 | 角色头像 + Markdown 渲染 + thinking 折叠面板 + sources 引用卡片 + typing 动画 + 重新生成按钮 | — |
| WelcomeScreen | ✅ 已实现 | Logo + 欢迎语 + 4 个快捷问题卡片 → emit 触发发送 | — |
| KnowledgeList (`/knowledge-bases`) | ✅ 已实现 | — | — |
| PublicKnowledgeList (`/knowledge-bases/public`) | ✅ 已实现 | — | — |
| KnowledgeDetail (`/knowledge-bases/:id`) | ✅ 已实现 | — | — |
| AdminKnowledgeList (`/admin/knowledge`) | 占位页面 | — | Phase 5：联调 `GET /api/admin/knowledge-bases` |
| AdminDocumentList (`/admin/documents`) | 占位页面 | — | Phase 5：联调 `GET /api/admin/documents` |
| Admin Stats (`/admin/stats`) | 占位页面 | — | Phase 5：统计卡片、数据下钻 |
| 状态轮询 | ✅ 已实现 | — | Phase 5：可选升级 WebSocket |
| SSE 流式输出 | ✅ 已实现 | fetch + ReadableStream 手动 SSE 解析、6 种事件类型处理、15s 心跳忽略、thinking 面板 | — |
| 会话自动创建 | ✅ 已实现 | `conversation_id=null` 传参 → `event: meta` 返回新 ID | Phase 4：多轮历史注入 |
| 标题自动生成 | ✅ 已实现 | 首轮 `finish` 事件返回 title（截取 question[:12]） | — |

---

## 12. 相关文档

- [产品需求文档](../docs/PRD.md)
- [架构设计文档](../docs/ARCHITECTURE.md)
- [接口文档](../backend/docs/API.md)
- [数据库设计文档](../backend/docs/DATABASE.md)
- [开发指南](../docs/DEVELOPMENT.md)
- [开发排期](../docs/ROADMAP.md)
- [测试策略](../docs/TESTING.md)
- [UI 设计规范](UIDESIGN.md)
