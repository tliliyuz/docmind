
---

# DocMind UI 样式规范

> 版本: v0.7
> 日期: 2026-06-03
> 用途: 面向 Agent 的 CSS 变量与组件样式参考
> 说明: 所有样式基于 Vue 3 + Element Plus 项目

---

## 1. CSS 变量定义（完整 Design Token）

以下变量必须放在项目全局样式文件的 `:root` 中：

```css
:root {
    /* ===== 品牌/强调色（纯黑白） ===== */
    --dm-primary: #1A1A1A;
    --dm-primary-hover: #000000;
    --dm-primary-light: #F5F5F5;
    --dm-primary-hover-light: #EBEBEB;

    /* ===== 语义色 ===== */
    --dm-success: #10B981;
    --dm-warning: #F59E0B;
    --dm-danger: #EF4444;
    --dm-info: #3B82F6;

    /* ===== 语义色浅色背景 ===== */
    --dm-success-light: #ECFDF5;
    --dm-warning-light: #FFFBEB;
    --dm-danger-light: #FEF2F2;
    --dm-info-light: #EFF6FF;

    /* ===== 部门图标色 ===== */
    --dm-hr-color: #DC2626;
    --dm-hr-bg: #FEF2F2;
    --dm-it-color: #2563EB;
    --dm-it-bg: #EFF6FF;
    --dm-admin-color: #059669;
    --dm-admin-bg: #ECFDF5;
    --dm-biz-color: #D97706;
    --dm-biz-bg: #FFFBEB;
    --dm-finance-color: #7C3AED;
    --dm-finance-bg: #F5F3FF;

    /* ===== 中性色（黑白灰体系） ===== */
    --dm-bg-page: #F2F2F2;
    --dm-bg-sidebar: #F5F5F5;
    --dm-bg-card: #FFFFFF;
    --dm-bg-chat: #FFFFFF;
    --dm-bg-input: #F5F5F5;
    --dm-text-primary: #1A1A1A;
    --dm-text-secondary: #737373;
    --dm-text-tertiary: #A3A3A3;
    --dm-border: #E0E0E0;
    --dm-border-light: #EBEBEB;

    /* ===== 字体族 ===== */
    --dm-font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                      "Helvetica Neue", Arial, "Noto Sans", sans-serif;
    --dm-font-mono: "SF Mono", "Fira Code", "JetBrains Mono", "Cascadia Code",
                    "Consolas", "Monaco", monospace;

    /* ===== 字号 ===== */
    --dm-text-3xl: 36px;
    --dm-text-2xl: 28px;
    --dm-text-xl: 24px;
    --dm-text-lg: 20px;
    --dm-text-base: 16px;
    --dm-text-sm: 15px;
    --dm-text-body: 14px;
    --dm-text-xs: 13px;
    --dm-text-2xs: 12px;
    --dm-text-3xs: 11px;

    /* ===== 字重 ===== */
    --dm-weight-bold: 700;
    --dm-weight-semibold: 600;
    --dm-weight-medium: 500;
    --dm-weight-normal: 400;

    /* ===== 行高 ===== */
    --dm-leading-title: 1.2;
    --dm-leading-body: 1.5;
    --dm-leading-chat: 1.7;

    /* ===== 间距 ===== */
    --dm-space-1: 4px;
    --dm-space-2: 8px;
    --dm-space-3: 12px;
    --dm-space-4: 16px;
    --dm-space-5: 20px;
    --dm-space-6: 24px;
    --dm-space-8: 32px;
    --dm-space-10: 40px;
    --dm-space-12: 48px;

    /* ===== 圆角 ===== */
    --dm-radius-xs: 4px;
    --dm-radius-sm: 8px;
    --dm-radius-md: 12px;
    --dm-radius-lg: 16px;
    --dm-radius-xl: 20px;
    --dm-radius-full: 50%;

    /* ===== 阴影（柔和中性） ===== */
    --dm-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.06);
    --dm-shadow-md: 0 4px 16px rgba(0, 0, 0, 0.08);
    --dm-shadow-lg: 0 8px 30px rgba(0, 0, 0, 0.10);
    --dm-shadow-xl: 0 20px 50px rgba(0, 0, 0, 0.15);
    --dm-shadow-sidebar: none;
    --dm-shadow-input: 0 1px 3px rgba(0, 0, 0, 0.05);
    --dm-shadow-input-focus: 0 0 0 3px rgba(0, 0, 0, 0.08);

    /* ===== 布局 ===== */
    --dm-sidebar-width-admin: 240px;
    --dm-sidebar-width-chat: 260px;
    --dm-sidebar-width-collapsed: 64px;
    --dm-header-height: 56px;
    --dm-chat-max-width: 768px;
    --dm-content-max-width: 1200px;

    /* ===== 过渡 ===== */
    --dm-transition-fast: 0.15s ease;
    --dm-transition-normal: 0.2s ease;
    --dm-transition-slow: 0.3s ease;

    /* ===== 其他 ===== */
    --dm-bg-code: #1A1A1A;
    --dm-text-code: #E5E5E5;
    --dm-welcome-logo-size: 56px;
    --dm-sidebar-logo-size: 32px;
}

/* Element Plus 主题覆盖 */
:root {
    --el-color-primary: #1A1A1A;
    --el-color-primary-light-3: #404040;
    --el-color-primary-light-5: #737373;
    --el-color-primary-light-7: #A3A3A3;
    --el-color-primary-light-8: #D4D4D4;
    --el-color-primary-light-9: #EBEBEB;
    --el-border-radius-base: 8px;
    --el-font-size-base: 14px;
    --el-font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                      "Helvetica Neue", Arial, sans-serif;
}
```

---

## 2. 全局样式

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: var(--dm-font-family);
    background: var(--dm-bg-page);
    color: var(--dm-text-primary);
    height: 100vh;
    overflow: hidden;
}

::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-track {
    background: transparent;
}
::-webkit-scrollbar-thumb {
    background: var(--dm-border);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: var(--dm-text-tertiary);
}
```

---

## 3. 布局规范

### 3.1 根布局

```css
#app {
    height: 100vh;
    display: flex;
}
```

### 3.2 通用侧边栏

```css
/* 侧边栏 */
.sidebar {
    width: var(--dm-sidebar-width-admin);      /* 管理端: 240px */
    /* 或 */
    width: var(--dm-sidebar-width-chat);       /* 聊天端: 260px */

    background: var(--dm-bg-sidebar);
    border-right: 1px solid var(--dm-border);
    box-shadow: var(--dm-shadow-sidebar);
    display: flex;
    flex-direction: column;
    z-index: 10;
    transition: width var(--dm-transition-normal);
    overflow-x: hidden;
}
```

**收起状态** (`.sidebar.collapsed`)：
- 宽度：`var(--dm-sidebar-width-collapsed)` (64px)
- 仅显示脑图标 Logo（居中）、导航项图标（含 `title` tooltip）、用户头像（居中）
- 隐藏所有文字标签、分组标题、空状态文案、退出按钮
- 顶部切换按钮：展开态位于右上角 (`fa-chevron-left`)，收起态居中 (`fa-chevron-right`)
- Logo 中不显示「DocMind」产品名（标题由 `AppLayout.vue` 顶部 header 展示）

### 3.3 通用主内容区

```css
/* 主内容区 */
.main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--dm-bg-page);
    overflow: hidden;
}

/* 顶部栏 */
.top-header,
.page-header {
    height: var(--dm-header-height);              /* 64px */
    background: var(--dm-bg-card);
    border-bottom: 1px solid var(--dm-border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--dm-space-6);                 /* 24px */
    z-index: 5;
}

/* 内容滚动区 */
.content-scroll {
    flex: 1;
    overflow-y: auto;
    padding: var(--dm-space-6) 28px;              /* 24px 28px */
}
```

---

## 4. 组件样式规范

### 4.1 按钮 (Button)

#### 主按钮 (.btn-primary)

```css
.btn-primary {
    height: 38px;
    padding: 0 18px;
    background: var(--dm-primary);
    color: white;
    border: none;
    border-radius: var(--dm-radius-sm);          /* 6px */
    font-size: var(--dm-text-body);              /* 14px */
    font-weight: var(--dm-weight-semibold);      /* 600 */
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: var(--dm-space-2);                      /* 8px */
    transition: all var(--dm-transition-normal); /* 0.2s ease */
}

.btn-primary:hover:not(:disabled) {
    background: var(--dm-primary-hover);
    box-shadow: var(--dm-shadow-sm);
}

.btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}
```

#### 登录/提交按钮 (.submit-btn)

```css
.submit-btn {
    width: 100%;
    height: 46px;
    background: var(--dm-text-primary);
    color: white;
    border: none;
    border-radius: var(--dm-radius-sm);          /* 8px */
    font-size: var(--dm-text-sm);                /* 15px */
    font-weight: var(--dm-weight-semibold);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--dm-space-2);
    transition: all var(--dm-transition-normal);
}

.submit-btn:hover:not(:disabled) {
    background: #000;
    box-shadow: var(--dm-shadow-md);
}

.submit-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
```

#### 图标按钮 (.icon-btn)

```css
.icon-btn {
    width: 36px;
    height: 36px;
    border: 1px solid var(--dm-border);
    border-radius: var(--dm-radius-xs);          /* 4px */
    background: transparent;
    color: var(--dm-text-tertiary);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all var(--dm-transition-normal);
}

.icon-btn:hover {
    border-color: var(--dm-primary);
    color: var(--dm-primary);
    background: var(--dm-primary-light);
}
```

#### 幽灵按钮 (.ghost-btn)

```css
.ghost-btn {
    height: 32px;
    padding: 0 14px;
    background: var(--dm-primary-light);
    color: var(--dm-primary);
    border: none;
    border-radius: var(--dm-radius-sm);
    font-size: var(--dm-text-xs);
    font-weight: var(--dm-weight-semibold);
    cursor: pointer;
    transition: background var(--dm-transition-fast);
}

.ghost-btn:hover {
    background: var(--dm-primary-hover-light);
}
```

---

### 4.2 输入框 (Input)

#### 标准输入框

```css
.form-input {
    width: 100%;
    height: 44px;
    padding: 0 14px;
    border: 1px solid var(--dm-border);
    border-radius: var(--dm-radius-md);          /* 10px */
    font-size: var(--dm-text-body);              /* 14px */
    color: var(--dm-text-primary);
    background: var(--dm-bg-page);
    outline: none;
    transition: all var(--dm-transition-normal);
}

.form-input:focus {
    border-color: var(--dm-primary);
    background: var(--dm-bg-card);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.08);
}

.form-input::placeholder {
    color: var(--dm-text-tertiary);
}
```

#### 带图标前缀的输入框

```css
.input-group {
    position: relative;
}

.input-group .prefix-icon {
    position: absolute;
    left: 14px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--dm-text-tertiary);
    font-size: var(--dm-text-body);
    pointer-events: none;
}

.input-group .input-with-icon {
    padding-left: 40px;
}
```

```html
<div class="input-group">
    <i class="fas fa-user prefix-icon"></i>
    <input class="form-input input-with-icon" placeholder="请输入用户名" />
</div>
```

#### Element Plus 搜索框容器

```css
.search-box-container {
    width: 280px;
}
```

```html
<div class="search-box-container">
    <el-input placeholder="搜索..." size="default" clearable>
        <template #prefix>
            <i class="fas fa-search" style="color: var(--dm-text-tertiary);"></i>
        </template>
    </el-input>
</div>
```

---

### 4.3 卡片 (Card)

#### 标准卡片

```css
.card {
    background: var(--dm-bg-card);
    border: 1px solid var(--dm-border);
    border-radius: var(--dm-radius-md);          /* 10px */
    padding: var(--dm-space-5);                  /* 20px */
    transition: all var(--dm-transition-normal);
}

.card:hover {
    border-color: var(--dm-primary);
    box-shadow: var(--dm-shadow-md);
    transform: translateY(-2px);
}
```

#### 可点击卡片（知识库卡片）

```css
.card-clickable {
    cursor: pointer;
}

.card-clickable:active {
    transform: translateY(0);
}
```

#### 统计卡片

```css
.stat-card {
    background: var(--dm-bg-card);
    border: 1px solid var(--dm-border);
    border-radius: var(--dm-radius-md);          /* 10px */
    padding: var(--dm-space-5);                  /* 20px */
    display: flex;
    align-items: center;
    gap: var(--dm-space-4);                      /* 16px */
    transition: box-shadow var(--dm-transition-fast);
}

.stat-card:hover {
    box-shadow: var(--dm-shadow-sm);
}
```

#### 统计卡片图标

```css
.stat-icon {
    width: 48px;
    height: 48px;
    border-radius: var(--dm-radius-sm);          /* 6px */
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--dm-text-lg);                /* 20px */
    flex-shrink: 0;
}

.stat-icon.primary  { background: var(--dm-primary-light); color: var(--dm-primary); }
.stat-icon.success  { background: var(--dm-success-light); color: var(--dm-success); }
.stat-icon.warning  { background: var(--dm-warning-light); color: var(--dm-warning); }
.stat-icon.danger   { background: var(--dm-danger-light); color: var(--dm-danger); }
```

#### 统计卡片数值

```css
.stat-value {
    font-size: var(--dm-text-xl);                /* 24px */
    font-weight: var(--dm-weight-bold);          /* 700 */
    color: var(--dm-text-primary);
}

.stat-label {
    font-size: var(--dm-text-xs);                /* 13px */
    color: var(--dm-text-secondary);
    margin-top: var(--dm-space-1);               /* 4px */
}
```

#### 知识库卡片图标

```css
.kb-icon {
    width: 44px;
    height: 44px;
    border-radius: var(--dm-radius-sm);          /* 6px */
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--dm-text-lg);                /* 20px */
    flex-shrink: 0;
}

.kb-icon.hr      { background: var(--dm-hr-bg);      color: var(--dm-hr-color); }
.kb-icon.it      { background: var(--dm-it-bg);      color: var(--dm-it-color); }
.kb-icon.admin   { background: var(--dm-admin-bg);   color: var(--dm-admin-color); }
.kb-icon.biz     { background: var(--dm-biz-bg);     color: var(--dm-biz-color); }
.kb-icon.finance { background: var(--dm-finance-bg); color: var(--dm-finance-color); }
```

#### 卡片元信息行

```css
.card-meta {
    display: flex;
    align-items: center;
    gap: var(--dm-space-4);                      /* 16px */
    padding-top: 14px;
    border-top: 1px solid var(--dm-border-light);
}

.card-meta-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--dm-text-2xs);               /* 12px */
    color: var(--dm-text-tertiary);
}

.card-meta-item i {
    font-size: var(--dm-text-xs);                /* 13px */
}
```

---

### 4.4 Logo 组件

#### 欢迎页大 Logo

```css
.welcome-logo {
    width: var(--dm-welcome-logo-size);          /* 56px */
    height: var(--dm-welcome-logo-size);
    background: var(--dm-primary);
    border-radius: var(--dm-radius-lg);          /* 16px */
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: var(--dm-text-2xl);               /* 28px */
}
```

#### 侧边栏小 Logo

```css
.sidebar-logo-icon {
    width: var(--dm-sidebar-logo-size);          /* 32px */
    height: var(--dm-sidebar-logo-size);
    background: var(--dm-primary);
    border-radius: var(--dm-radius-sm);          /* 8px */
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: var(--dm-text-sm);                /* 15px */
    flex-shrink: 0;
}
```

#### Logo 文字

```css
.logo-title {
    font-size: var(--dm-text-base);              /* 16px */
    font-weight: var(--dm-weight-bold);          /* 700 */
    color: var(--dm-text-primary);
    line-height: var(--dm-leading-title);        /* 1.2 */
}

.logo-subtitle {
    font-size: var(--dm-text-2xs);               /* 12px */
    color: var(--dm-text-tertiary);
}
```

---

### 4.5 消息气泡 (Message Bubble)

```css
.message-bubble {
    border-radius: var(--dm-radius-md);          /* 10px */
    padding: 14px 18px;
    font-size: var(--dm-text-body);              /* 14px */
    line-height: var(--dm-leading-chat);         /* 1.7 */
    max-width: 70%;
    word-break: break-word;
}

.message-bubble.user {
    background: var(--dm-text-primary);
    color: white;
    border: 1px solid var(--dm-text-primary);
    margin-left: auto;
}

.message-bubble.assistant {
    background: transparent;
    color: var(--dm-text-primary);
    border: none;
}
```

#### 消息头像

```css
.message-avatar {
    width: 36px;
    height: 36px;
    border-radius: var(--dm-radius-full);        /* 50% */
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--dm-text-body);              /* 14px */
    flex-shrink: 0;
}

.message-avatar.user {
    background: var(--dm-text-primary);
    color: white;
}

.message-avatar.assistant {
    background: var(--dm-primary);
    color: white;
}
```

#### 消息元信息

```css
.message-header {
    display: flex;
    align-items: center;
    gap: var(--dm-space-2);                      /* 8px */
    margin-bottom: 6px;
}

.message-name {
    font-size: var(--dm-text-xs);                /* 13px */
    font-weight: var(--dm-weight-semibold);      /* 600 */
    color: var(--dm-text-primary);
}

.message-time {
    font-size: var(--dm-text-3xs);               /* 11px */
    color: var(--dm-text-tertiary);
}
```

---

### 4.6 思考过程 (Thinking Box)

```css
.thinking-box {
    margin-bottom: var(--dm-space-3);            /* 12px */
    padding: 12px 16px;
    background: var(--dm-warning-light);         /* #FEF3C7 */
    border-radius: var(--dm-radius-sm);          /* 6px */
    border-left: 3px solid var(--dm-warning);    /* #F59E0B */
}

.thinking-title {
    font-size: var(--dm-text-2xs);               /* 12px */
    font-weight: var(--dm-weight-semibold);
    color: var(--dm-text-primary);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.thinking-content {
    font-size: var(--dm-text-xs);                /* 13px */
    color: var(--dm-text-secondary);
    line-height: 1.6;
}
```

---

### 4.7 引用来源 (Sources Box)

```css
.sources-box {
    margin-top: var(--dm-space-3);               /* 12px */
    padding: 12px 16px;
    background: var(--dm-primary-light);
    border-radius: var(--dm-radius-sm);          /* 6px */
    border-left: 3px solid var(--dm-primary);
}

.sources-title {
    font-size: var(--dm-text-2xs);               /* 12px */
    font-weight: var(--dm-weight-semibold);
    color: var(--dm-primary);
    margin-bottom: var(--dm-space-2);            /* 8px */
    display: flex;
    align-items: center;
    gap: 6px;
}

.source-item {
    display: flex;
    align-items: center;
    gap: var(--dm-space-2);
    padding: 6px 0;
    font-size: var(--dm-text-2xs);
    color: var(--dm-text-secondary);
    border-bottom: 1px solid var(--dm-border-light);
}

.source-item:last-child {
    border-bottom: none;
}

.source-doc {
    font-weight: var(--dm-weight-semibold);
    color: var(--dm-primary);
}

.source-score {
    margin-left: auto;
    background: var(--dm-primary);
    color: white;
    padding: 2px 8px;
    border-radius: var(--dm-radius-xs);          /* 4px */
    font-size: var(--dm-text-3xs);               /* 11px */
    font-weight: var(--dm-weight-semibold);
}
```

---

### 4.8 状态标签 (Status Tag)

```css
.status-tag {
    padding: 4px 10px;
    border-radius: var(--dm-radius-xs);          /* 4px */
    font-size: var(--dm-text-2xs);               /* 12px */
    font-weight: var(--dm-weight-semibold);      /* 600 */
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

/* 非终态 — 处理中（蓝色系） */
.status-tag.uploaded       { background: var(--dm-info-light);    color: var(--dm-info); }
.status-tag.parsing        { background: var(--dm-info-light);    color: var(--dm-info); }
.status-tag.chunking       { background: var(--dm-info-light);    color: var(--dm-info); }
.status-tag.embedding      { background: var(--dm-info-light);    color: var(--dm-info); }
.status-tag.vector_storing { background: var(--dm-info-light);    color: var(--dm-info); }

/* 终态 — 成功（绿色系） */
.status-tag.completed              { background: var(--dm-success-light); color: var(--dm-success); }
.status-tag.success_with_warnings  { background: var(--dm-success-light); color: var(--dm-success); }

/* 终态 — 部分失败（橙色/警告色） */
.status-tag.partial_failed { background: var(--dm-warning-light); color: var(--dm-warning); }

/* 终态 — 失败（红色系） */
.status-tag.failed { background: var(--dm-danger-light); color: var(--dm-danger); }

/* 中间态 — 删除中（灰色系） */
.status-tag.deleting { background: var(--dm-border-light); color: var(--dm-text-secondary); }

/* 通用 info（用于非文档状态的场景） */
.status-tag.info { background: var(--dm-info-light); color: var(--dm-info); }
```

**状态与图标配对**（Font Awesome 6）：

| 状态 | 图标 class | 说明 |
|:---|:---|:---|
| `uploaded` | `fa-upload` | 已上传等待处理 |
| `parsing` | `fa-spinner fa-spin` | 解析中 |
| `chunking` | `fa-spinner fa-spin` | 分块中 |
| `embedding` | `fa-spinner fa-spin` | 向量化中 |
| `vector_storing` | `fa-spinner fa-spin` | 写入向量库 |
| `completed` | `fa-check-circle` | 全部成功 |
| `success_with_warnings` | `fa-check-circle` | 成功但有警告 |
| `partial_failed` | `fa-exclamation-triangle` | 部分失败 |
| `failed` | `fa-times-circle` | 完全失败 |
| `deleting` | `fa-spinner fa-spin` | 清理中（完成后物理删除行） |

---

### 4.9 状态指示点 (Status Dot)

```css
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: var(--dm-radius-full);        /* 50% */
    flex-shrink: 0;
}

.status-dot.active   { background: var(--dm-success); }
.status-dot.indexing { background: var(--dm-warning); }
.status-dot.error    { background: var(--dm-danger); }
```

---

### 4.10 进度条 (Progress Bar)

```css
.progress-bar {
    width: 100%;
    height: 6px;
    background: var(--dm-border-light);
    border-radius: 3px;
    overflow: hidden;
    margin-top: var(--dm-space-2);               /* 8px */
}

.progress-fill {
    height: 100%;
    background: var(--dm-primary);
    border-radius: 3px;
    transition: width 0.3s ease;
}
```

---

### 4.11 空状态 (Empty State)

```css
.empty-state {
    text-align: center;
    padding: var(--dm-space-12) var(--dm-space-5);   /* 48px 20px */
    color: var(--dm-text-tertiary);
}

.empty-icon {
    font-size: 48px;
    margin-bottom: var(--dm-space-4);            /* 16px */
    opacity: 0.5;
}

.empty-title {
    font-size: var(--dm-text-base);              /* 16px */
    font-weight: var(--dm-weight-semibold);
    color: var(--dm-text-primary);
    margin-bottom: var(--dm-space-2);            /* 8px */
}

.empty-desc {
    font-size: var(--dm-text-body);              /* 14px */
}
```

---

### 4.12 加载动画 (Typing Indicator)

```css
.typing-indicator {
    display: flex;
    gap: 4px;
    padding: 12px 0;
}

.typing-dot {
    width: 8px;
    height: 8px;
    background: var(--dm-text-tertiary);
    border-radius: var(--dm-radius-full);
    animation: typing 1.4s infinite ease;
}

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
    0%, 60%, 100% { transform: translateY(0); }
    30%           { transform: translateY(-6px); }
}
```

---

### 4.13 上传区域 (Upload Area)

```css
.upload-area {
    border: 2px dashed var(--dm-border);
    border-radius: var(--dm-radius-md);
    padding: var(--dm-space-10);                 /* 40px */
    text-align: center;
    cursor: pointer;
    transition: all var(--dm-transition-normal);
}

.upload-area:hover {
    border-color: var(--dm-primary);
    background: var(--dm-primary-light);
}

.upload-icon {
    width: 56px;
    height: 56px;
    background: var(--dm-primary-light);
    border-radius: var(--dm-radius-full);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--dm-primary);
    font-size: 22px;
    margin: 0 auto var(--dm-space-4);
}
```

---

### 4.14 导航菜单 (Nav Menu)

```css
.nav-item {
    display: flex;
    align-items: center;
    gap: var(--dm-space-3);                      /* 12px */
    padding: 12px 14px;
    border-radius: var(--dm-radius-sm);          /* 6px */
    cursor: pointer;
    transition: all var(--dm-transition-fast);
    font-size: var(--dm-text-body);              /* 14px */
    color: var(--dm-text-secondary);
}

.nav-item:hover {
    background: var(--dm-bg-page);
    color: var(--dm-text-primary);
}

.nav-item.active {
    background: var(--dm-primary-light);
    color: var(--dm-primary);
    font-weight: var(--dm-weight-semibold);
}

.nav-item i {
    width: 20px;
    text-align: center;
    font-size: var(--dm-text-sm);                /* 15px */
}

.nav-badge {
    margin-left: auto;
    background: var(--dm-primary-light);
    color: var(--dm-primary);
    font-size: var(--dm-text-3xs);               /* 11px */
    font-weight: var(--dm-weight-semibold);
    padding: 2px 8px;
    border-radius: 10px;
}
```

---

### 4.15 对话列表项 (Conversation Item)

```css
.conv-item {
    padding: 10px 12px;
    border-radius: var(--dm-radius-sm);          /* 6px */
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 2px;
    transition: background var(--dm-transition-fast);
    position: relative;
}

.conv-item:hover {
    background: var(--dm-bg-chat);
}

.conv-item.active {
    background: var(--dm-primary-light);
}

.conv-item.active .conv-title {
    color: var(--dm-primary);
    font-weight: var(--dm-weight-semibold);
}

.conv-icon {
    width: 28px;
    height: 28px;
    background: var(--dm-bg-chat);
    border-radius: var(--dm-radius-sm);          /* 6px */
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--dm-text-tertiary);
    font-size: var(--dm-text-2xs);               /* 12px */
    flex-shrink: 0;
}

.conv-info {
    flex: 1;
    min-width: 0;
}

.conv-title {
    font-size: var(--dm-text-xs);                /* 13px */
    color: var(--dm-text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.conv-meta {
    font-size: var(--dm-text-3xs);               /* 11px */
    color: var(--dm-text-tertiary);
    margin-top: var(--dm-space-1);               /* 4px */
}

.conv-actions {
    opacity: 0;
    transition: opacity var(--dm-transition-fast);
    display: flex;
    gap: var(--dm-space-1);
}

.conv-item:hover .conv-actions {
    opacity: 1;
}

.conv-actions button {
    width: 24px;
    height: 24px;
    border: none;
    background: transparent;
    color: var(--dm-text-tertiary);
    cursor: pointer;
    border-radius: var(--dm-radius-xs);          /* 4px */
    display: flex;
    align-items: center;
    justify-content: center;
}

.conv-actions button:hover {
    background: var(--dm-border);
    color: var(--dm-text-primary);
}
```

---

### 4.16 用户信息栏 (User Bar)

```css
.user-bar {
    display: flex;
    align-items: center;
    gap: var(--dm-space-3);                      /* 12px */
    padding: var(--dm-space-2);                  /* 8px */
    border-radius: var(--dm-radius-sm);          /* 6px */
    cursor: pointer;
    transition: background var(--dm-transition-fast);
}

.user-bar:hover {
    background: var(--dm-bg-chat);
}

.user-avatar {
    width: 32px;
    height: 32px;
    border-radius: var(--dm-radius-full);        /* 50% */
    background: var(--dm-text-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: var(--dm-text-xs);                /* 13px */
    font-weight: var(--dm-weight-semibold);
    flex-shrink: 0;
}

.user-name {
    font-size: var(--dm-text-xs);                /* 13px */
    font-weight: var(--dm-weight-semibold);
    color: var(--dm-text-primary);
}

.user-role {
    font-size: var(--dm-text-3xs);               /* 11px */
    color: var(--dm-text-tertiary);
}
```

---

### 4.17 页面标题

```css
.page-title {
    font-size: var(--dm-text-lg);                /* 20px */
    font-weight: var(--dm-weight-bold);          /* 700 */
    color: var(--dm-text-primary);
}

.section-title {
    font-size: var(--dm-text-base);              /* 16px */
    font-weight: var(--dm-weight-bold);
    color: var(--dm-text-primary);
}
```

---

### 4.18 筛选按钮组 (Filter Buttons)

```css
.filter-btn {
    padding: 6px 14px;
    border: 1px solid var(--dm-border);
    border-radius: var(--dm-radius-sm);          /* 6px */
    background: var(--dm-bg-card);
    font-size: var(--dm-text-xs);                /* 13px */
    color: var(--dm-text-secondary);
    cursor: pointer;
    transition: all var(--dm-transition-fast);
}

.filter-btn:hover {
    border-color: var(--dm-primary);
    color: var(--dm-primary);
}

.filter-btn.active {
    background: var(--dm-primary);
    color: white;
    border-color: var(--dm-primary);
}
```

---

### 4.19 新建卡片（虚线样式）

```css
.new-card {
    border: 2px dashed var(--dm-border);
    border-radius: var(--dm-radius-md);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 180px;
    cursor: pointer;
    transition: all var(--dm-transition-normal);
}

.new-card:hover {
    border-color: var(--dm-primary);
    background: var(--dm-primary-light);
}

.new-card-icon {
    width: 48px;
    height: 48px;
    background: var(--dm-primary-light);
    border-radius: var(--dm-radius-full);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--dm-primary);
    font-size: 22px;
    margin-bottom: var(--dm-space-4);
}
```

---

## 5. 动画与过渡

### 5.1 过渡时长

| 场景 | 时长 | 缓动函数 |
|:---|:---|:---|
| 颜色/背景变化 | 0.15s | ease |
| 边框/阴影变化 | 0.2s | ease |
| 位移/缩放 | 0.2s | ease |
| 页面进入 | 0.3s | ease |
| 消息出现 | 0.3s | ease（fadeIn + translateY） |

### 5.2 关键帧动画

```css
/* 消息进入 */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

/* 加载动画 */
@keyframes typing {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-6px); }
}
```

---

## 6. 图标规范

使用 Font Awesome 6 Free，图标尺寸：

| 场景 | 尺寸 |
|:---|:---|
| 导航菜单图标 | 15px |
| 按钮内图标 | 12-14px |
| 卡片头部图标 | 20px |
| 大功能图标 | 28-32px |
| 品牌 Logo 图标 | 16px（侧边栏）/ 36px（欢迎页） |

---

## 7. Markdown 渲染样式

聊天消息气泡内的 Markdown 内容样式：

| 元素 | 样式 |
|:---|:---|
| h1/h2/h3 | 继承气泡文字色，margin: 12px 0 8px |
| p | margin: 8px 0，行高 1.7 |
| strong | font-weight: 600 |
| code（行内） | 背景 rgba(0,0,0,0.06)，padding: 2px 6px，圆角 4px，等宽字体 |
| pre > code | 背景 #1A1A1A，文字 #E5E5E5，padding: 16px，圆角 6px |
| blockquote | 左边框 3px solid var(--dm-primary)，背景 var(--dm-primary-light) |
| li | 列表项，配合 br 换行 |
| 链接 | var(--dm-primary)，hover 下划线 |

---

## 8. 使用示例

### 8.1 Element Plus 主题覆盖

```js
// main.js
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

const app = createApp(App)
app.use(ElementPlus)
```

```css
/* styles/element-override.css */
:root {
  --el-color-primary: #1A1A1A;
  --el-color-primary-light-3: #404040;
  --el-color-primary-light-5: #737373;
  --el-color-primary-light-7: #A3A3A3;
  --el-color-primary-light-8: #D4D4D4;
  --el-color-primary-light-9: #EBEBEB;
  --el-border-radius-base: 8px;
  --el-font-size-base: 14px;
}
```

### 8.2 UnoCSS / WindiCSS 工具类配置（可选）

```js
// uno.config.js
export default {
  theme: {
    colors: {
      'dm-primary': '#1A1A1A',
      'dm-primary-hover': '#000000',
      'dm-primary-light': '#F5F5F5',
      'dm-success': '#10B981',
      'dm-warning': '#F59E0B',
      'dm-danger': '#EF4444',
      'dm-bg-page': '#F2F2F2',
      'dm-bg-sidebar': '#F5F5F5',
      'dm-bg-card': '#FFFFFF',
      'dm-text-primary': '#1A1A1A',
      'dm-text-secondary': '#737373',
      'dm-text-tertiary': '#A3A3A3',
      'dm-border': '#E0E0E0',
    }
  }
}
```

---

## 9. 相关文档

- [产品需求文档](../docs/PRD.md)
- [架构设计文档](../docs/ARCHITECTURE.md)
- [数据库设计文档](../backend/docs/DATABASE.md)
- [接口文档](../backend/docs/API.md)
- [开发指南](../docs/DEVELOPMENT.md)
- [开发排期](../docs/ROADMAP.md)
- [测试策略](../docs/TESTING.md)