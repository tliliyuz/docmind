"""Query Rewrite 单元测试 — 触发判断 / Rewrite 正确性 / 降级

对齐 TEST_CASES.md §6.2.2：
- U8.20–U8.33  触发判断 _needs_rewrite() 14 用例
- U8.30–U8.33  Rewrite 正确性 rewrite_query() 4 用例（注意：ID 与触发判断新用例共享 U8.30-U8.33）
- U8.40–U8.43  降级行为 4 用例

触发策略（v2）：仅检查明确歧义信号词，不使用短问题阈值。
详细设计见 ARCHITECTURE.md §5.1.5。
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.query_rewriter import (
    _needs_rewrite,
    rewrite_query,
    AMBIGUOUS_SIGNALS,
    MIN_REWRITE_LENGTH,
    REWRITE_SYSTEM_PROMPT,
    REWRITE_USER_TEMPLATE,
)


# ===== 辅助 fixture =====

def _make_history(messages: list[tuple[str, str]]) -> list[dict[str, str]]:
    """快捷构造 history 列表。

    Args:
        messages: [(role, content), ...] 如 [("user", "什么是代码评审？"), ("assistant", "代码评审是……")]

    Returns:
        list[dict]: history 格式
    """
    return [{"role": role, "content": content} for role, content in messages]


# ===== 触发判断 _needs_rewrite() =====

class TestNeedsRewrite:
    """触发判断测试（U8.20–U8.33）"""

    # --- 无历史 ---

    def test_U820_无历史_跳过(self):
        """无历史时即使含代词也跳过 — 无参考上下文无法消解"""
        result = _needs_rewrite("它需要几个人参加？", history=[])
        assert result is False

    # --- 原始信号词（v1 保留） ---

    def test_U821_有历史_含代词_触发(self):
        """有历史 + 含「它」→ 触发 rewrite"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审需要至少2人参加……"),
        ])
        result = _needs_rewrite("它需要几个人参加？", history=history)
        assert result is True

    def test_U822_有历史_短问题但无信号词_跳过(self):
        """有历史但问题无歧义信号词 → 不触发（短问题本身不是触发条件）"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审标准包括……"),
        ])
        # "不通过的话怎么办？" — 无任何歧义信号词，不应触发
        result = _needs_rewrite("不通过的话怎么办？", history=history)
        assert result is False

    def test_U823_有历史_指示词触发(self):
        """有历史 + 含「这个」→ 触发 rewrite"""
        history = _make_history([
            ("user", "怎么配置 VPN？"),
            ("assistant", "VPN 配置需要……"),
        ])
        result = _needs_rewrite("这个怎么处理？", history=history)
        assert result is True

    def test_U824_有历史_多重歧义信号触发(self):
        """有历史 + 含「那」+「呢」→ 触发 rewrite（任一信号即触发）"""
        history = _make_history([
            ("user", "年假怎么申请？"),
            ("assistant", "年假需要在 OA 系统提交……"),
        ])
        result = _needs_rewrite("那请假呢？", history=history)
        assert result is True

    def test_U825_有历史_独立完整问题_跳过(self):
        """有历史但问题无歧义信号词 → 不触发"""
        history = _make_history([
            ("user", "年假怎么申请？"),
            ("assistant", "年假需要在 OA 系统提交……"),
        ])
        # 无歧义信号词
        question = "新员工入职流程具体包含哪些步骤？"
        result = _needs_rewrite(question, history=history)
        assert result is False

    def test_U826_有历史_含关键词完整问题_跳过(self):
        """虽有 context_dependent 标记但无歧义信号词 → 不用 rewrite"""
        history = _make_history([
            ("user", "公司 VPN 怎么配置？"),
            ("assistant", "VPN 需要下载客户端……"),
        ])
        # "刚才说的" 已加入 AMBIGUOUS_SIGNALS，但完整问题是「刚才说的 VPN，忘记密码怎么办？」
        # 含「刚才」→ 触发（"刚才" 在信号列表中）
        # 注意：此行为与 v1 不同 —— v2 中 "刚才" 是信号词
        result = _needs_rewrite("刚才说的 VPN，忘记密码怎么办？", history=history)
        assert result is True  # 含「刚才」信号词

    def test_U827_有历史_含呢字_触发(self):
        """含「呢」→ 触发 rewrite（呢 为歧义信号词，与问题长度无关）"""
        history = _make_history([
            ("user", "培训费用是多少？"),
            ("assistant", "培训费用为每人 500 元……"),
        ])
        # "具体多少钱呢？" 含「呢」→ 触发
        result = _needs_rewrite("具体多少钱呢？", history=history)
        assert result is True

    # --- 新增信号词（v2 扩展） ---

    def test_U828_有历史_含他们_触发(self):
        """有历史 + 含「他们」→ 触发 rewrite"""
        history = _make_history([
            ("user", "项目组有哪些成员？"),
            ("assistant", "项目组包括张三、李四、王五……"),
        ])
        result = _needs_rewrite("他们的分工是什么？", history=history)
        assert result is True

    def test_U829_有历史_含这些_触发(self):
        """有历史 + 含「这些」→ 触发 rewrite"""
        history = _make_history([
            ("user", "报销需要哪些材料？"),
            ("assistant", "需要发票、审批单、出差报告……"),
        ])
        result = _needs_rewrite("这些材料有模板吗？", history=history)
        assert result is True

    def test_U830_有历史_含那些_触发(self):
        """有历史 + 含「那些」→ 触发 rewrite"""
        history = _make_history([
            ("user", "公司有哪些福利？"),
            ("assistant", "五险一金、餐补、交通补贴……"),
        ])
        result = _needs_rewrite("那些福利需要申请吗？", history=history)
        assert result is True

    def test_U831_有历史_含上面_触发(self):
        """有历史 + 含「上面」→ 触发 rewrite"""
        history = _make_history([
            ("user", "考勤制度是怎样的？"),
            ("assistant", "考勤制度规定每天 9:00-18:00……"),
        ])
        result = _needs_rewrite("上面提到的迟到怎么处理？", history=history)
        assert result is True

    def test_U832_有历史_含前面说的_触发(self):
        """有历史 + 含「前面说的」→ 触发 rewrite"""
        history = _make_history([
            ("user", "公司的培训政策是怎样的？"),
            ("assistant", "培训分为内部和外部……"),
        ])
        result = _needs_rewrite("前面说的内部培训费用谁出？", history=history)
        assert result is True

    def test_U833_有历史_含刚才_触发(self):
        """有历史 + 含「刚才」→ 触发 rewrite"""
        history = _make_history([
            ("user", "怎么连接公司 VPN？"),
            ("assistant", "需要下载客户端并配置……"),
        ])
        result = _needs_rewrite("刚才说的客户端在哪里下载？", history=history)
        assert result is True


# ===== Rewrite 正确性 =====

class TestRewriteQueryCorrectness:
    """Rewrite 正确性测试（U8.30–U8.33）"""

    @pytest.mark.asyncio
    async def test_U830_代词消解(self):
        """含「它」→ LLM 改写后含上下文实体"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审需要至少 2 位资深工程师参与，评审不通过需修改后重新提交。"),
        ])
        mock_result = MagicMock()
        mock_result.content = "代码评审需要几个人参加？"

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            result = await rewrite_query("它需要几个人参加？", history)

        assert "代码评审" in result
        assert "需要几个人参加" in result

    @pytest.mark.asyncio
    async def test_U831_省略补全(self):
        """省略主语「不通过」→ LLM 改写后补全为完整上下文"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审不通过需要修改后重新提交。"),
        ])
        mock_result = MagicMock()
        mock_result.content = "代码评审不通过怎么办？"

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            result = await rewrite_query("不通过的话怎么办？", history)

        assert "代码评审" in result
        assert "不通过" in result

    @pytest.mark.asyncio
    async def test_U832_指代消解(self):
        """上下文依赖「金额限制」→ LLM 改写后含「报销制度」"""
        history = _make_history([
            ("user", "介绍一下公司的报销制度"),
            ("assistant", "公司报销制度包括差旅、培训等，差旅费金额限制为每人每天 300 元……"),
        ])
        mock_result = MagicMock()
        mock_result.content = "报销制度的金额限制是多少？"

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            result = await rewrite_query("金额限制具体是多少？", history)

        assert "报销制度" in result
        assert "金额限制" in result

    @pytest.mark.asyncio
    async def test_U833_recent_4_truncation(self):
        """6 条消息（3 轮）→ 传入 LLM 的 history 仅含最近 4 条（2 轮）"""
        history = _make_history([
            ("user", "第一轮问题1"),        # T-3 user (应被截掉)
            ("assistant", "第一轮回答1"),    # T-3 assistant (应被截掉)
            ("user", "第二轮的完整问题文本内容"),   # T-2 user (保留)
            ("assistant", "第二轮的回答内容"),     # T-2 assistant (保留)
            ("user", "代码评审的标准是什么？"),      # T-1 user (保留)
            ("assistant", "代码评审需要至少 2 位资深工程师参与。"),  # T-1 assistant (保留)
        ])
        mock_result = MagicMock()
        mock_result.content = "代码评审需要几个人参加？"

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            await rewrite_query("它需要几个人参加？", history)

            # 验证传入 LLM 的 messages
            call_args = mock_llm.call_args[1]["messages"]
            # 提取 user message 中的 history 部分
            user_msg_content = call_args[1]["content"]

        # 不应包含被截掉的第 1 轮内容
        assert "第一轮问题1" not in user_msg_content
        assert "第一轮回答1" not in user_msg_content
        # 应包含最近 2 轮内容
        assert "第二轮的完整问题文本内容" in user_msg_content
        assert "第二轮的回答内容" in user_msg_content
        assert "代码评审的标准是什么？" in user_msg_content
        assert "代码评审需要至少 2 位资深工程师参与" in user_msg_content


# ===== 降级行为 =====

class TestRewriteQueryDegradation:
    """降级测试（U8.40–U8.43）"""

    @pytest.mark.asyncio
    async def test_U840_LLM_失败降级(self):
        """LLM 抛异常 → 返回原始 question，不抛异常"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审需要……"),
        ])
        original = "它需要几个人参加？"

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("LLM API 不可用")
            result = await rewrite_query(original, history)

        assert result == original

    @pytest.mark.asyncio
    async def test_U841_LLM_空字符串降级(self):
        """LLM 返回空字符串 → 降级返回原始 question"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审需要……"),
        ])
        original = "它需要几个人参加？"
        mock_result = MagicMock()
        mock_result.content = ""

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            result = await rewrite_query(original, history)

        assert result == original

    @pytest.mark.asyncio
    async def test_U842_LLM_解释性文本处理(self):
        """LLM 返回带引号/前缀文本 → strip 处理后 ≥2 字即采用"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审需要……"),
        ])
        mock_result = MagicMock()
        # 中文双引号包裹
        mock_result.content = "“代码评审需要几个人参加？”"

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            result = await rewrite_query("它需要几个人参加？", history)

        # 中文引号被 strip 掉，采用有效内容
        assert "“" not in result
        assert "”" not in result
        assert "代码评审需要几个人参加" in result

    @pytest.mark.asyncio
    async def test_U843_LLM_单字符降级(self):
        """LLM 返回单字符「。」→ < 2 字，降级返回原始 question"""
        history = _make_history([
            ("user", "代码评审的标准是什么？"),
            ("assistant", "代码评审需要……"),
        ])
        original = "它需要几个人参加？"
        mock_result = MagicMock()
        mock_result.content = "。"

        with patch("app.rag.query_rewriter.chat_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_result
            result = await rewrite_query(original, history)

        assert result == original


# ===== 常量验证 =====

class TestRewriteConstants:
    """常量正确性验证"""

    def test_歧义信号词完整性(self):
        """验证歧义信号词列表包含所有设计指定的词"""
        expected = [
            "它", "这个", "那个", "该", "此", "呢", "那",
            "他们", "这些", "那些",
            "上面", "前面说的", "刚才",
        ]
        assert AMBIGUOUS_SIGNALS == expected

    def test_所有信号词均为非空字符串(self):
        """验证所有信号词均为有效非空字符串"""
        for signal in AMBIGUOUS_SIGNALS:
            assert isinstance(signal, str)
            assert len(signal) >= 1

    def test_最小有效改写长度(self):
        """验证最小有效改写长度为 2"""
        assert MIN_REWRITE_LENGTH == 2
        # 单字符不采用（边界值验证）
        assert 1 < MIN_REWRITE_LENGTH

    def test_rewrite_prompt_含输出约束(self):
        """验证 System Prompt 包含输出格式约束"""
        assert "只输出改写后的问题" in REWRITE_SYSTEM_PROMPT
        assert "不要解释" in REWRITE_SYSTEM_PROMPT

    def test_rewrite_user_template_含占位符(self):
        """验证 User Template 包含必要的占位符"""
        assert "{history}" in REWRITE_USER_TEMPLATE
        assert "{question}" in REWRITE_USER_TEMPLATE
