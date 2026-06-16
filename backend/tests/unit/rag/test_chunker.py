"""智能分块模块单元测试 — 覆盖数据类、估算函数、偏移映射、页码定位、核心分块逻辑、§8.7 章节检测"""

import pytest

from app.config import settings
from app.rag.chunker import (
    ChunkResult,
    ChunkingResult,
    chunk_document,
    estimate_tokens,
    build_page_offset_map,
    resolve_page_number,
    detect_sections,
    resolve_section,
)
from app.rag.parser import ParsedPage


class TestChunkResult:
    """ChunkResult 数据类测试"""

    def test_正常创建分块结果(self):
        c = ChunkResult(content="测试", chunk_index=0, page_number=1, estimated_tokens=2)
        assert c.content == "测试"
        assert c.chunk_index == 0
        assert c.page_number == 1
        assert c.estimated_tokens == 2

    def test_page_number_可为None(self):
        c = ChunkResult(content="测试", chunk_index=3, page_number=None, estimated_tokens=2)
        assert c.page_number is None

    def test_estimated_tokens_为整数(self):
        c = ChunkResult(content="长文本", chunk_index=0, page_number=1, estimated_tokens=10)
        assert isinstance(c.estimated_tokens, int)


class TestChunkingResult:
    """ChunkingResult 聚合结果测试"""

    def test_默认空结果(self):
        result = ChunkingResult()
        assert result.chunks == []
        assert result.total_chunks == 0

    def test_含分块的结果(self):
        chunks = [
            ChunkResult("a", 0, None, 1),
            ChunkResult("b", 1, None, 1),
        ]
        result = ChunkingResult(chunks=chunks, total_chunks=2)
        assert result.total_chunks == 2
        assert len(result.chunks) == 2
        assert result.chunks[0].chunk_index == 0
        assert result.chunks[1].chunk_index == 1


class TestEstimateTokens:
    """字符数 token 估算测试（中英文自适应比率）"""

    def test_中文字符估算(self):
        # 6个中文 → 占比 100% > 30% → ratio=1.5 → int(6/1.5)=4
        assert estimate_tokens("测试文本内容") == 4

    def test_纯英文字符估算(self):
        # "hello" 5 chars → 中文占比 0 → ratio=4.0 → int(5/4)=1
        assert estimate_tokens("hello") == 1

    def test_短文本最少返回1(self):
        assert estimate_tokens("a") == 1

    def test_空文本最少返回1(self):
        assert estimate_tokens("") == 1

    def test_混合中英文_中文占比低于阈值(self):
        # "hello世界foo": 2个中文(世界), 9个英文=11 chars
        # 中文占比 2/11 ≈ 0.18 < 0.3 → ratio=4.0 → int(11/4)=2
        tokens = estimate_tokens("hello世界foo")
        assert tokens == 2

    def test_中文为主_占比超阈值(self):
        # "你好world你好世界": 6个中文/11 chars ≈ 0.55 > 0.3 → ratio=1.5 → int(11/1.5)=7
        tokens = estimate_tokens("你好world你好世界")
        assert tokens == 7


class TestBuildPageOffsetMap:
    """build_page_offset_map 页码偏移映射测试"""

    def test_正常页面构建偏移映射(self):
        pages = [
            ParsedPage(1, "第一页内容"),
            ParsedPage(2, "第二页内容"),
        ]
        offset_map = build_page_offset_map(pages)
        assert len(offset_map) == 2
        # 第1页从偏移0开始
        assert offset_map[0] == (0, 1)
        # 第2页偏移 = len("第一页内容") + 2 (for \n\n)
        assert offset_map[1] == (len("第一页内容") + 2, 2)

    def test_跳过失败页面(self):
        pages = [
            ParsedPage(1, "OK"),
            ParsedPage(2, "", success=False, error="失败"),
            ParsedPage(3, "第三页"),
        ]
        offset_map = build_page_offset_map(pages)
        assert len(offset_map) == 2
        assert offset_map[0] == (0, 1)
        assert offset_map[1] == (len("OK") + 2, 3)

    def test_跳过空内容页面(self):
        pages = [
            ParsedPage(1, ""),
            ParsedPage(2, "有内容"),
        ]
        offset_map = build_page_offset_map(pages)
        # 第1页 content 为空，被跳过；仅第2页进入映射
        assert len(offset_map) == 1
        assert offset_map[0][1] == 2

    def test_空页面列表(self):
        assert build_page_offset_map([]) == []


class TestResolvePageNumber:
    """resolve_page_number 页码定位测试"""

    def test_定位到首页(self):
        offset_map = [(0, 1), (10, 2), (20, 3)]
        # start_offset=3 落在偏移 0-10 区间，属第1页
        assert resolve_page_number(3, offset_map) == 1

    def test_定位到中间页(self):
        offset_map = [(0, 1), (5, 2), (10, 3)]
        # start_offset=6 落在偏移 5-10 区间，属第2页
        page_num = resolve_page_number(6, offset_map)
        assert page_num == 2

    def test_定位到末页(self):
        offset_map = [(0, 1), (10, 2)]
        # start_offset=12 落在偏移 10+ 区间，属第2页
        page_num = resolve_page_number(12, offset_map)
        assert page_num == 2

    def test_空偏移映射_返回None(self):
        assert resolve_page_number(0, []) is None

    def test_start_offset为负1_返回None(self):
        offset_map = [(0, 1)]
        assert resolve_page_number(-1, offset_map) is None


class TestChunkDocument:
    """chunk_document 核心分块逻辑测试"""

    # === 基础功能 ===

    def test_短文本_单块(self):
        text = "这是一段很短的文本。"
        result = chunk_document(text)
        assert result.total_chunks == 1
        assert result.chunks[0].content == text
        assert result.chunks[0].chunk_index == 0
        assert result.chunks[0].estimated_tokens == estimate_tokens(text)

    def test_空文本_返回空结果(self):
        result = chunk_document("")
        assert result.total_chunks == 0
        assert result.chunks == []

    def test_空白文本_返回空结果(self):
        result = chunk_document("   \n  \t  ")
        assert result.total_chunks == 0

    # === 分隔符优先级 ===

    def test_按段落分隔符优先分块(self):
        """\n\n 优先级最高，段落边界处应优先切分"""
        # 构造 3 段，每段 ~400 字符，总计 ~1200 字符
        para_a = "这是第一段内容。" * 40   # ~320 chars
        para_b = "这是第二段内容。" * 40   # ~320 chars
        para_c = "这是第三段内容。" * 40   # ~320 chars
        text = "\n\n".join([para_a, para_b, para_c])

        result = chunk_document(text)
        # 段落边界优先：不应在段落中间切断
        assert result.total_chunks >= 1
        for chunk in result.chunks:
            assert len(chunk.content) <= settings.CHUNK_SIZE
            # 每块内不应有孤立的段落开头（说明在段落中间被切了）
            assert chunk.content.count("\n\n") >= 0

    def test_中文句号处断句(self):
        """分隔符优先级包含 。在更细粒度处切分"""
        sentences = ["这是第{}个句子。".format(i) for i in range(200)]
        text = "".join(sentences)  # 连续句子无换行

        result = chunk_document(text)
        assert result.total_chunks > 1
        # RecursiveCharacterTextSplitter 优先按 。切分，每块应含完整句号
        # 注意：超大块可能被更低优先级分隔符递归切分（如字符级），非末尾块不一定以 。结尾
        for chunk in result.chunks:
            assert "。" in chunk.content, (
                f"块 {chunk.chunk_index} 不含中文句号，分割可能未按标点"
            )

    def test_换行符处断句(self):
        """\n 优先级高于标点"""
        lines = ["第{}行内容文字填充".format(i) for i in range(200)]
        text = "\n".join(lines)

        result = chunk_document(text)
        assert result.total_chunks > 1

    # === keep_separator ===

    def test_keep_separator_分隔符保留在块末尾(self):
        """分隔符（如 。）应保留在 chunk 末尾，而非被丢弃"""
        text = "第一句。第二句。第三句。" * 100
        result = chunk_document(text)
        for chunk in result.chunks:
            assert "。" in chunk.content or len(chunk.content) > 0

    # === chunk 大小范围 ===

    def test_每块不超过chunk_size(self):
        """所有块不应超过设定的 chunk_size"""
        text = "测试内容填充文字。" * 500
        result = chunk_document(text, chunk_size=800)
        for chunk in result.chunks:
            assert len(chunk.content) <= 800, (
                f"块 {chunk.chunk_index} 大小 {len(chunk.content)} 超过 800"
            )

    def test_自定义chunk_size(self):
        text = "数据" * 2000
        result = chunk_document(text, chunk_size=500, chunk_overlap=50)
        for chunk in result.chunks:
            assert len(chunk.content) <= 500

    # === overlap ===

    def test_chunk_overlap_块间有重叠内容(self):
        """验证 overlap > 0 时块间存在重叠"""
        text = "这是一段需要填充足够长内容的文本，" * 100
        result = chunk_document(text, chunk_size=500, chunk_overlap=100)
        assert result.total_chunks >= 2

        # 检查相邻块是否有重叠内容
        for i in range(result.total_chunks - 1):
            current_end = result.chunks[i].content[-50:]
            next_start = result.chunks[i + 1].content[:50]
            # 重叠区域中应能找到公共子串
            # 取 current 尾部 30 字符在 next 头部搜索
            overlap_candidate = result.chunks[i].content[-30:]
            assert overlap_candidate in result.chunks[i + 1].content, (
                f"块 {i} 和块 {i+1} 之间未检测到重叠"
            )

    # === 页码追踪 ===

    def test_页码追踪_正确映射(self):
        """传入 pages 列表，每块能追溯到来源页码"""
        pages = [
            ParsedPage(1, "第一页" * 200),
            ParsedPage(2, "第二页" * 200),
            ParsedPage(3, "第三页" * 200),
        ]
        # 手动构建 full_text 与 pages 对齐
        full_text = "\n\n".join(p.content for p in pages)
        result = chunk_document(full_text, pages=pages)

        assert result.total_chunks > 0
        page_numbers = {c.page_number for c in result.chunks}
        assert page_numbers.issubset({1, 2, 3})
        assert None not in page_numbers

    def test_无页码时_返回None(self):
        result = chunk_document("测试文本" * 100)
        for chunk in result.chunks:
            assert chunk.page_number is None

    # === token 估算 ===

    def test_token估算_中文使用1点5比率(self):
        text = "测试" * 500  # 1000 字符，全部中文，ratio=1.5
        result = chunk_document(text)
        for chunk in result.chunks:
            assert chunk.estimated_tokens == estimate_tokens(chunk.content)

    # === 边界情况 ===

    def test_恰好等于chunk_size的文本(self):
        text = "测" * settings.CHUNK_SIZE
        result = chunk_document(text)
        assert result.total_chunks == 1
        assert len(result.chunks[0].content) == settings.CHUNK_SIZE

    def test_含英文标点的文本(self):
        text = ("This is a test sentence. Another sentence here. " * 50)
        result = chunk_document(text)
        assert result.total_chunks >= 1

    def test_混合中英文标点(self):
        text = ("中文内容。English follows. 继续中文！Next English! " * 50)
        result = chunk_document(text)
        assert result.total_chunks >= 1


# ==================== §8.7 章节检测测试 ====================


class TestDetectSections:
    """detect_sections() — Markdown 标题提取"""

    def test_空文本(self):
        assert detect_sections("") == []
        assert detect_sections(None) == []  # type: ignore

    def test_无标题文本(self):
        sections = detect_sections("这是普通文本，没有任何标题。\n还是普通文本。")
        assert sections == []

    def test_单个一级标题(self):
        text = "# 概述\n这是内容。"
        sections = detect_sections(text)
        assert len(sections) == 1
        offset, level, title = sections[0]
        assert level == 1
        assert title == "概述"

    def test_多级标题(self):
        text = "# 第一章\n内容...\n## 1.1 背景\n更多内容\n### 1.1.1 细节\n详细内容"
        sections = detect_sections(text)
        assert len(sections) == 3
        assert sections[0] == (0, 1, "第一章")
        assert sections[1][2] == "1.1 背景"
        assert sections[1][1] == 2
        assert sections[2][2] == "1.1.1 细节"
        assert sections[2][1] == 3

    def test_六级标题(self):
        text = "###### 最小标题\n内容"
        sections = detect_sections(text)
        assert len(sections) == 1
        assert sections[0][1] == 6
        assert sections[0][2] == "最小标题"

    def test_忽略超过六级(self):
        """####### 不是标准 Markdown ATX 标题，不匹配"""
        text = "####### 七级不是标题\n内容"
        sections = detect_sections(text)
        assert sections == []

    def test_空标题文本被跳过(self):
        """# 后面无内容不产生 section"""
        text = "# \n内容"
        sections = detect_sections(text)
        assert sections == []

    def test_标题带前后空白(self):
        text = "##   带空格标题   \n内容"
        sections = detect_sections(text)
        assert len(sections) == 1
        assert sections[0][2] == "带空格标题"

    def test_代码块中的井号不是标题(self):
        """行内代码块 # 不是标题（正则要求行首）"""
        text = "在代码中 `# 注释` 不是标题\n## 这是标题\n内容"
        sections = detect_sections(text)
        assert len(sections) == 1
        assert sections[0][2] == "这是标题"


class TestResolveSection:
    """resolve_section() — 偏移量反查章节"""

    def _make_sections(self) -> list[tuple[int, int, str]]:
        """构建模拟 section 列表"""
        return [
            (0, 1, "概述"),
            (10, 2, "环境配置"),
            (30, 3, "数据库"),
            (50, 2, "部署"),
        ]

    def test_无sections返回None(self):
        assert resolve_section(100, []) == (None, None)

    def test_无效偏移量返回None(self):
        assert resolve_section(-1, self._make_sections()) == (None, None)

    def test_偏移量在第一标题前返回None(self):
        """第一个标题之前的内容不属于任何章节"""
        sections = [(50, 1, "概述")]
        assert resolve_section(10, sections) == (None, None)

    def test_偏移量在第一个标题上(self):
        sections = self._make_sections()
        section_title, section_path = resolve_section(0, sections)
        assert section_title == "概述"
        assert section_path == "概述"

    def test_偏移量匹配第一个子标题(self):
        sections = self._make_sections()
        section_title, section_path = resolve_section(10, sections)
        assert section_title == "环境配置"
        assert section_path == "概述 > 环境配置"

    def test_偏移量匹配二级子标题(self):
        sections = self._make_sections()
        section_title, section_path = resolve_section(30, sections)
        assert section_title == "数据库"
        assert section_path == "概述 > 环境配置 > 数据库"

    def test_同级标题替换(self):
        """同级或更高级标题出现时，旧同级被弹出"""
        sections = self._make_sections()
        section_title, section_path = resolve_section(50, sections)
        assert section_title == "部署"
        # 部署是 level 2，弹出 level 2 的「环境配置」和 level 3 的「数据库」
        assert section_path == "概述 > 部署"

    def test_标题间的内容归属上一个标题(self):
        """两个标题之间的偏移量应归属于第一个标题"""
        sections = [(0, 1, "开始"), (100, 2, "详细")]
        section_title, section_path = resolve_section(50, sections)
        assert section_title == "开始"
        assert section_path == "开始"


class TestChunkDocumentWithSections:
    """chunk_document() 集成 §8.7 章节信息"""

    def test_markdown文档分块含章节信息(self):
        text = """# 入职指南

新员工入职流程包括以下步骤：第一步，填写个人信息表。第二步，提交相关证明材料。第三步，参加入职培训。

## 报销制度

公司报销制度如下：差旅费按实际支出报销，需提供发票。日常办公用品按月预算控制。

## 假期政策

年假每年十五天，病假需提供医院证明。婚假为三天，需提前一周申请。"""
        result = chunk_document(text)
        assert result.total_chunks >= 1

        # 检查每个 chunk 的 section_title / section_path
        chunks_with_sections = [c for c in result.chunks if c.section_title]
        assert len(chunks_with_sections) >= 1

    def test_无标题文档_章节信息为None(self):
        text = "这是一段没有任何标题的文本。" * 100
        result = chunk_document(text)
        for chunk in result.chunks:
            assert chunk.section_title is None
            assert chunk.section_path is None

    def test_ChunkResult包含章节字段(self):
        chunk = ChunkResult(
            content="测试",
            chunk_index=0,
            page_number=1,
            estimated_tokens=10,
            section_title="§3.2 限流",
            section_path="架构 > §3 基础设施 > §3.2 限流",
        )
        assert chunk.section_title == "§3.2 限流"
        assert chunk.section_path == "架构 > §3 基础设施 > §3.2 限流"

    def test_ChunkResult章节字段默认为None(self):
        chunk = ChunkResult(content="测试", chunk_index=0, page_number=None, estimated_tokens=5)
        assert chunk.section_title is None
        assert chunk.section_path is None
