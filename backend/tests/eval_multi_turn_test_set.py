"""多轮 RAG 回归测试集 — Phase 4 新增

供 regression_multi_turn_test.py 使用。
对齐 TESTING.md §7.4 设计原则：
  - 每个 session 包含多轮问答，后轮依赖前轮上下文
  - 覆盖：上下文依赖 / 主题切换 / 长对话 / 跨文档追问 / 指代消解
  - 核心验证：多轮后 RAG 不退化（每轮仍有 sources 事件）

与 eval_test_set.py（单轮 30 题）互补：
  - 单轮测试全部通过 ≠ 多轮没问题
  - 多轮场景下历史注入可能挤掉检索结果，导致 RAG 静默退化为纯聊天
"""

from __future__ import annotations

from typing import Any

MULTI_TURN_TEST_SET: list[dict[str, Any]] = [
    # ========================================================================
    # Session 1: 报销制度三连问（上下文依赖递增）
    # 验证：3 轮后 RAG 仍正常检索，每轮均有 sources
    # ========================================================================
    {
        "session_id": "multi-001",
        "name": "报销制度三连问",
        "description": "同一文档连续追问，验证上下文依赖递增 + RAG 不退化",
        "kb_id": 1,
        "turns": [
            {
                "turn": 1,
                "question": "介绍一下公司的报销制度",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["报销制度.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 2,
                "question": "审批流程需要多长时间？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：第 2 轮必须仍有 sources
                    "min_chunks": 1,
                    "expected_docs": ["报销制度.md"],
                    "context_dependent": True,     # ← 依赖 Turn 1 的"报销"上下文
                },
            },
            {
                "turn": 3,
                "question": "金额限制具体是多少？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：第 3 轮 RAG 不能退化
                    "min_chunks": 1,
                    "expected_docs": ["报销制度.md"],
                    "context_dependent": True,     # ← 依赖前两轮的"报销审批"上下文
                },
            },
        ],
    },

    # ========================================================================
    # Session 2: 多主题切换（验证历史不干扰本轮检索）
    # ========================================================================
    {
        "session_id": "multi-002",
        "name": "多主题切换",
        "description": "连续切换不同主题，验证每轮检索独立、历史不干扰",
        "kb_id": 1,
        "turns": [
            {
                "turn": 1,
                "question": "VPN 怎么连接？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["VPN配置指南.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 2,
                "question": "入职需要准备哪些材料？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：切换到入职，检索不能沿用 VPN
                    "min_chunks": 1,
                    "expected_docs": ["入职指南.md"],
                    "context_dependent": False,    # ← 独立问题，不应依赖前轮
                },
            },
            {
                "turn": 3,
                "question": "那请假呢，病假怎么申请？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：再次切换主题
                    "min_chunks": 1,
                    "expected_docs": ["请假与考勤制度.md"],
                    "context_dependent": False,    # ← 独立问题（"那"是口语转折）
                },
            },
            {
                "turn": 4,
                "question": "刚才说的 VPN，忘记密码怎么办？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：回到 VPN 主题
                    "min_chunks": 1,
                    "expected_docs": ["VPN配置指南.md"],
                    "context_dependent": True,     # ← "刚才说的 VPN"依赖 Turn 1
                },
            },
        ],
    },

    # ========================================================================
    # Session 3: 跨文档追问（从一个文档自然过渡到另一个）
    # ========================================================================
    {
        "session_id": "multi-003",
        "name": "离职场景跨文档追问",
        "description": "从离职流程出发，追问固定资产和报销，验证跨文档检索",
        "kb_id": 1,
        "turns": [
            {
                "turn": 1,
                "question": "员工离职需要办理哪些手续？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["离职交接流程.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 2,
                "question": "那手里的固定资产怎么处理？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：离开职流程→固定资产
                    "min_chunks": 1,
                    "expected_docs": ["固定资产管理办法.md", "离职交接流程.md"],
                    "context_dependent": True,     # ← "那"承接离职上下文
                },
            },
            {
                "turn": 3,
                "question": "未报销的费用也要在离职前结清吗？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：扩展到报销文档
                    "min_chunks": 1,
                    "expected_docs": ["报销制度.md", "离职交接流程.md"],
                    "context_dependent": True,     # ← "离职前"依赖 Turn 1
                },
            },
        ],
    },

    # ========================================================================
    # Session 4: 指代消解（代词/省略依赖前轮）
    # ========================================================================
    {
        "session_id": "multi-004",
        "name": "指代消解",
        "description": "后轮使用代词或省略主语，验证系统能正确补全上下文",
        "kb_id": 1,
        "turns": [
            {
                "turn": 1,
                "question": "代码评审的标准是什么？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["代码评审标准.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 2,
                "question": "它需要几个人参加？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← "它"指代"代码评审"
                    "min_chunks": 1,
                    "expected_docs": ["代码评审标准.md"],
                    "context_dependent": True,     # ← 强烈依赖 Turn 1 消解"它"
                },
            },
            {
                "turn": 3,
                "question": "不通过的话怎么办？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← "不通过"指代码评审不通过
                    "min_chunks": 1,
                    "expected_docs": ["代码评审标准.md"],
                    "context_dependent": True,     # ← 依赖 Turn 1+2 的上下文
                },
            },
        ],
    },

    # ========================================================================
    # Session 5: 长对话 RAG 保活（10 轮 +，验证截断后检索不退化）
    # ========================================================================
    {
        "session_id": "multi-005",
        "name": "长对话 RAG 保活",
        "description": "连续 10 轮不同主题问答，验证历史截断后最后几轮仍正常检索",
        "kb_id": 1,
        # 截断假设：系统默认 max_messages=20 条（10 轮 user+assistant），
        # 但 History Token 预算 6000 + 每轮约 500-800 tokens（question+answer+sources）→
        # 约在 Turn 7-8 之间 token 预算开始截断早期轮次。
        # 此处保守标记 Turn 8 起为截断观察区（truncation_zone_start=8），
        # 截断区内各轮 sources 不消失即证明历史截断未侵蚀检索预算。
        "truncation_zone_start": 8,
        "turns": [
            {
                "turn": 1,
                "question": "入职第一天需要做什么？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["入职指南.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 2,
                "question": "打印机卡纸了怎么处理？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["打印机使用说明.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 3,
                "question": "会议室预约后不用了怎么取消？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["会议室预约规则.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 4,
                "question": "访客来公司需要什么手续？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["访客登记流程.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 5,
                "question": "病假需要提供医院证明吗？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["请假与考勤制度.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 6,
                "question": "采购超过 5000 元谁审批？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["采购流程管理.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 7,
                "question": "VPN 密码忘了怎么办？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["VPN配置指南.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 8,
                "question": "数据安全有哪些基本要求？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,
                    "min_chunks": 1,
                    "expected_docs": ["数据安全规范.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 9,
                "question": "微信上能传工作文件吗？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：即使历史很长，仍应检索
                    "min_chunks": 1,
                    "expected_docs": ["邮箱与通讯工具使用规范.md"],
                    "context_dependent": False,
                },
            },
            {
                "turn": 10,
                "question": "发生火灾往哪里跑？",
                "expected": {
                    "has_answer": True,
                    "has_sources": True,           # ← 关键：第 10 轮 RAG 不能退化
                    "min_chunks": 1,
                    "expected_docs": ["突发事件应急预案.md"],
                    "context_dependent": False,
                },
            },
        ],
    },
]
