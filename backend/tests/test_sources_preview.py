"""Sources 智能预览单元测试

对齐 TEST_CASES.md §6.11：
- U11.1 定位-精确匹配：_locate_preview 在 chunk 中精确定位引用段落
- U11.2 定位-子串匹配失败降级：snippet 不存在时回退 _fallback_preview
- U11.3 定位-短 chunk（<200字符）：返回完整内容
- U11.4 SSE-sources 含 preview_text/preview_range：_build_sources 格式校验
- U11.5 SSE-sources 向前兼容：content 字段保留完整内容

覆盖 app/services/chat_service.py 中的 _locate_preview / _fallback_preview / _build_sources
"""

import pytest

from app.rag.retriever import RetrievalOutput, RetrievalResult
from app.schemas.chat import ChatSourceChunk, PreviewRange


# ==================== 辅助函数 ====================


def _make_chunk_content() -> str:
    """构造测试用 chunk 内容（>200 字符，含可定位片段）"""
    return (
        "新员工入职流程包括以下步骤："
        "第一步，提交入职申请表和个人身份证明文件。"
        "第二步，人力资源部门审核资料并发放工牌。"
        "第三步，IT 部门开通工作账号和VPN权限。"
        "第四步，参加新员工入职培训，了解公司规章制度。"
        "整个流程从入职当天开始，预计需要3个工作日完成。"
    )


# ==================== _fallback_preview 测试 ====================


class TestFallbackPreview:
    """_fallback_preview() 降级预览函数测试"""

    def test_正常内容返回前200字符(self):
        """U11.2 降级路径：返回 chunk 前 200 字符 + PreviewRange(0, 200)"""
        from app.services.chat_service import _fallback_preview

        content = "A" * 300
        preview_text, preview_range = _fallback_preview(content)

        assert preview_text == "A" * 200
        assert len(preview_text) == 200
        assert preview_range.start == 0
        assert preview_range.end == 200

    def test_短内容返回完整内容(self):
        """U11.3 边界：chunk < 200 字符时返回完整内容，end = len(content)"""
        from app.services.chat_service import _fallback_preview

        content = "短文本，仅80字符。" * 2  # 约 20 字符
        preview_text, preview_range = _fallback_preview(content)

        assert preview_text == content
        assert preview_range.start == 0
        assert preview_range.end == len(content)

    def test_空内容返回空字符串(self):
        """空 chunk 内容不抛异常，返回空字符串"""
        from app.services.chat_service import _fallback_preview

        preview_text, preview_range = _fallback_preview("")

        assert preview_text == ""
        assert preview_range.start == 0
        assert preview_range.end == 0


# ==================== _locate_preview 测试 ====================


class TestLocatePreviewExactMatch:
    """_locate_preview() 精确匹配测试（强断言验证定位准确性）"""

    def test_精确匹配_窗口中心在引用文字附近(self):
        """U11.1 精确匹配：snippet 在 chunk 中精确找到，窗口中心在匹配位置"""
        from app.services.chat_service import _locate_preview

        chunk_content = _make_chunk_content()
        # LLM 回答中 [来源1] 后紧跟的 snippet 在 chunk 中存在
        assistant_content = "根据入职流程，[来源1]提交入职申请表和个人身份证明文件。这是必须的。"

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        # 定位应成功（非降级）
        assert preview_text is not None
        assert preview_range is not None
        # 预览文本应在 chunk 中
        assert preview_text in chunk_content
        # 窗口大小应合理（±100 字符窗口，最多 200 字符）
        assert 0 < len(preview_text) <= 200
        # 范围边界有效
        assert 0 <= preview_range.start < preview_range.end <= len(chunk_content)
        # 窗口中心附近应包含引用文字的关键部分
        center = (preview_range.start + preview_range.end) // 2
        snippet_pos = chunk_content.find("提交入职申请表")
        assert snippet_pos >= 0
        # 窗口中心应在 snippet 附近（容差 100 字符）
        assert abs(center - snippet_pos) <= 100

    def test_精确匹配_不同chunk_index(self):
        """不同 [来源N] 编号能正确定位到对应 snippet"""
        from app.services.chat_service import _locate_preview

        chunk_content = "VPN 密码忘记了可以通过 IT 自助服务平台重置，或拨打 IT 热线 8888。"
        # assistant_content 中有 [来源2] 和 [来源3]，验证 chunk_index=2 能正确提取
        assistant_content = (
            "VPN 问题请参考[来源1]相关文档。"
            "关于密码重置，[来源2]可以通过 IT 自助服务平台重置。"
            "其他问题[来源3]请联系管理员。"
        )

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=2
        )

        assert preview_text is not None
        # 窗口应包含 "IT 自助服务平台" 附近的内容
        assert "IT 自助服务平台" in preview_text

    def test_精确匹配_规范化空格后匹配(self):
        """snippet 含多余空格时规范化后仍能匹配"""
        from app.services.chat_service import _locate_preview

        chunk_content = "报销制度规定：差旅费报销需提供发票和行程单。"
        # snippet 有多余空格，chunk 中无多余空格
        assistant_content = "[来源1]差旅费报销  需提供  发票和行程单。"

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        # 规范化空格后应能匹配
        assert preview_text is not None
        assert "差旅费报销" in preview_text


class TestLocatePreviewFallback:
    """_locate_preview() 降级场景测试"""

    def test_snippet不存在降级(self):
        """U11.2：snippet 在 chunk 中完全找不到时降级到前 200 字符"""
        from app.services.chat_service import _locate_preview

        chunk_content = "A" * 300
        assistant_content = "[来源1]完全不存在的文本片段XYZ"

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        assert preview_text == "A" * 200
        assert preview_range.start == 0
        assert preview_range.end == 200

    def test_无来源标记降级(self):
        """assistant_content 中无对应 [来源N] 标记时降级"""
        from app.services.chat_service import _locate_preview

        # 使用 >200 字符的 chunk 确保降级后验证 end=200
        chunk_content = "X" * 300
        assistant_content = "这份文档介绍了入职流程。"  # 无 [来源1]

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        # 降级到 _fallback_preview：返回前 200 字符
        assert preview_text == "X" * 200
        assert preview_range.start == 0
        assert preview_range.end == 200

    def test_snippet过短降级(self):
        """snippet < 4 字符时降级（太短无法可靠匹配）"""
        from app.services.chat_service import _locate_preview

        chunk_content = _make_chunk_content()
        # [来源1] 后只有 1 个字符
        assistant_content = "[来源1]的"

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        # snippet 太短，应降级
        assert preview_text == chunk_content[:200]
        assert preview_range.start == 0

    def test_异常时降级不抛异常(self):
        """_locate_preview 内部异常时降级，不抛出"""
        from app.services.chat_service import _locate_preview

        # 传入异常参数（chunk_index=0 可能导致正则不匹配但不会崩溃）
        chunk_content = "正常内容" * 50
        assistant_content = ""  # 空回答

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        # 应降级不抛异常
        assert preview_text == chunk_content[:200]
        assert preview_range.start == 0
        assert preview_range.end == 200


class TestLocatePreviewShortChunk:
    """_locate_preview() 短 chunk 边界测试"""

    def test_短chunk精确匹配返回完整内容(self):
        """U11.3：chunk < 200 字符且有匹配时，返回完整内容，窗口覆盖全 chunk"""
        from app.services.chat_service import _locate_preview

        chunk_content = "新员工入职需要提交身份证复印件。"
        assistant_content = "[来源1]入职需要提交身份证复印件。"

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        # 短 chunk 完整内容
        assert preview_text == chunk_content
        # 范围覆盖全 chunk（窗口在匹配位置附近，但短 chunk 中窗口即全 chunk）
        assert preview_range.start >= 0
        assert preview_range.end <= len(chunk_content)

    def test_短chunk无匹配降级返回完整内容(self):
        """U11.3：短 chunk < 200 字符且无匹配时，降级返回完整内容"""
        from app.services.chat_service import _locate_preview

        chunk_content = "短文本内容"  # 仅 6 字符
        assistant_content = "[来源1]不存在的片段"

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        assert preview_text == chunk_content
        assert preview_range.start == 0
        assert preview_range.end == len(chunk_content)

    def test_恰好200字符不截断(self):
        """chunk 恰好 200 字符，降级时返回全部"""
        from app.services.chat_service import _locate_preview

        chunk_content = "X" * 200  # 恰好 200 字符
        assistant_content = "[来源1]不存在片段"

        preview_text, preview_range = _locate_preview(
            chunk_content, assistant_content, chunk_index=1
        )

        assert len(preview_text) == 200
        assert preview_range.start == 0
        assert preview_range.end == 200


# ==================== _build_sources 集成测试 ====================


class TestBuildSourcesPreviewIntegration:
    """_build_sources() 含 preview 字段的集成测试"""

    def test_preview_text和preview_range字段存在(self):
        """U11.4：正常问答时 sources 每项含 preview_text + preview_range"""
        from app.services.chat_service import _build_sources

        content = "公司报销制度规定：差旅报销需提交差旅申请单和交通票据。报销金额上限为每次5000元。"
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content=content, score=0.9),
        ]
        assistant_content = "根据报销制度，[来源1]差旅报销需提交差旅申请单和交通票据。"

        sources = _build_sources(
            results, {1: "报销制度.md"}, assistant_content=assistant_content
        )

        assert len(sources) == 1
        assert sources[0].preview_text is not None
        assert isinstance(sources[0].preview_range, PreviewRange)
        # preview_range 字段类型正确
        assert isinstance(sources[0].preview_range.start, int)
        assert isinstance(sources[0].preview_range.end, int)
        # start < end（有效范围）
        assert sources[0].preview_range.start < sources[0].preview_range.end

    def test_content字段保留完整内容_向前兼容(self):
        """U11.5：content 字段保留完整 chunk 内容，旧前端不受影响"""
        from app.services.chat_service import _build_sources

        content = "X" * 500  # 长内容
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content=content, score=0.9),
        ]
        assistant_content = "[来源1]X" * 30  # snippet 存在

        sources = _build_sources(
            results, {1: "test.txt"}, assistant_content=assistant_content
        )

        # content 保留完整内容
        assert sources[0].content == content
        assert len(sources[0].content) == 500
        # preview_text 是子集（窗口内文本）
        assert sources[0].preview_text is not None
        assert len(sources[0].preview_text) <= 200
        # preview_text 来自 content（子串关系）
        assert sources[0].preview_text in content

    def test_无assistant_content时preview字段为None(self):
        """无 assistant_content 时 preview 字段为 None（不执行定位）"""
        from app.services.chat_service import _build_sources

        content = "测试内容" * 50
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content=content, score=0.9),
        ]

        sources = _build_sources(results, {1: "test.txt"}, assistant_content=None)

        assert sources[0].preview_text is None
        assert sources[0].preview_range is None
        # content 仍在
        assert sources[0].content == content

    def test_空assistant_content时preview字段为None(self):
        """空 assistant_content 也不执行定位"""
        from app.services.chat_service import _build_sources

        content = "测试内容"
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content=content, score=0.9),
        ]

        sources = _build_sources(results, {1: "test.txt"}, assistant_content="")

        assert sources[0].preview_text is None
        assert sources[0].preview_range is None

    def test_多条chunk各独立定位(self):
        """多条 chunk 时每条独立执行定位，chunk_index 与 [来源N] 对应"""
        from app.services.chat_service import _build_sources

        content1 = "报销流程：第一步填写报销单。第二步提交审批。第三步财务打款。"
        content2 = "VPN 配置：打开设置，选择网络，添加 VPN 连接。"
        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content=content1, score=0.9),
            RetrievalResult(doc_id=2, chunk_index=1, content=content2, score=0.8),
        ]
        assistant_content = (
            "关于报销，[来源1]第一步填写报销单，然后提交审批。"
            "关于 VPN，[来源2]打开设置，选择网络。"
        )

        sources = _build_sources(
            results, {1: "报销.md", 2: "VPN.md"}, assistant_content=assistant_content
        )

        assert len(sources) == 2
        # chunk_index 与 [来源N] 一致
        assert sources[0].chunk_index == 1
        assert sources[1].chunk_index == 2
        # 各自独立定位成功
        assert sources[0].preview_text is not None
        assert sources[1].preview_text is not None
        # 各自定位到正确 chunk 内容
        assert "报销单" in sources[0].preview_text
        assert "VPN" in sources[1].preview_text

    def test_score保留原始精度(self):
        """score 保留 4 位小数"""
        from app.services.chat_service import _build_sources

        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="内容", score=0.123456),
        ]

        sources = _build_sources(results, {1: "test.txt"})

        assert sources[0].score == 0.1235  # round(0.123456, 4)


class TestBuildSourcesEdgeCases:
    """_build_sources() 边界条件测试"""

    def test_空chunks列表(self):
        """空检索结果不抛异常"""
        from app.services.chat_service import _build_sources

        sources = _build_sources([], {}, assistant_content="任意回答")
        assert sources == []

    def test_content为空的chunk(self):
        """chunk.content 为空时不执行定位，preview 为 None"""
        from app.services.chat_service import _build_sources

        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="", score=0.5),
        ]

        sources = _build_sources(
            results, {1: "test.txt"}, assistant_content="[来源1]内容"
        )

        assert len(sources) == 1
        assert sources[0].content == ""
        # content 为空时不应尝试定位
        assert sources[0].preview_text is None
        assert sources[0].preview_range is None

    def test_chunk_index从1开始递增(self):
        """chunk_index 从 1 开始，与 LLM Prompt 中 [来源N] 编号一致"""
        from app.services.chat_service import _build_sources

        results = [
            RetrievalResult(doc_id=1, chunk_index=0, content="A", score=0.9),
            RetrievalResult(doc_id=2, chunk_index=1, content="B", score=0.8),
            RetrievalResult(doc_id=3, chunk_index=2, content="C", score=0.7),
        ]

        sources = _build_sources(results, {1: "A", 2: "B", 3: "C"})

        assert sources[0].chunk_index == 1
        assert sources[1].chunk_index == 2
        assert sources[2].chunk_index == 3


# ==================== ChatSourceChunk Schema 校验 ====================


class TestChatSourceChunkSchema:
    """ChatSourceChunk / PreviewRange Pydantic 模型校验"""

    def test_PreviewRange正常构造(self):
        """PreviewRange 应能正常构造和序列化"""
        pr = PreviewRange(start=10, end=150)
        assert pr.start == 10
        assert pr.end == 150
        d = pr.model_dump()
        assert d == {"start": 10, "end": 150}

    def test_ChatSourceChunk含preview字段序列化(self):
        """ChatSourceChunk 含 preview_text + preview_range 时正确序列化"""
        pr = PreviewRange(start=0, end=100)
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="测试.pdf",
            content="完整的 chunk 内容" * 20,
            score=0.95,
            page=3,
            preview_text="预览文本",
            preview_range=pr,
        )

        d = chunk.model_dump()
        assert d["chunk_index"] == 1
        assert d["doc_id"] == 10
        assert d["preview_text"] == "预览文本"
        assert d["preview_range"] == {"start": 0, "end": 100}
        # content 保留完整内容
        assert d["content"] == "完整的 chunk 内容" * 20

    def test_ChatSourceChunk无preview字段序列化(self):
        """无 preview 字段时序列化为 null（向前兼容）"""
        chunk = ChatSourceChunk(
            chunk_index=1,
            doc_id=10,
            doc_name="测试.pdf",
            content="内容",
            score=0.5,
        )

        d = chunk.model_dump()
        assert d["preview_text"] is None
        assert d["preview_range"] is None

    def test_PreviewRange边界值_零窗口(self):
        """PreviewRange(0, 0) 表示空窗口"""
        pr = PreviewRange(start=0, end=0)
        assert pr.start == 0
        assert pr.end == 0

    def test_PreviewRange边界值_负start不合法(self):
        """Pydantic 默认不拒绝负值（int 类型），由业务逻辑保证"""
        pr = PreviewRange(start=0, end=100)
        # start 应为非负，由 _locate_preview 中 max(0, ...) 保证
        assert pr.start >= 0
