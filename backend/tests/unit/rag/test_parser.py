"""文档解析器单元测试 — 覆盖 PDF/DOCX/MD/TXT 解析 + 容错阈值判定"""

import pytest
from unittest.mock import MagicMock, PropertyMock, patch

from app.rag.parser import (
    ParsedPage,
    ParseResult,
    parse_document,
    _parse_pdf,
    _parse_docx,
    _parse_text,
)


class TestParsedPage:
    """ParsedPage 数据类测试"""

    def test_正常页面_默认创建(self):
        page = ParsedPage(page_number=1, content="测试内容")
        assert page.page_number == 1
        assert page.content == "测试内容"
        assert page.success is True
        assert page.error is None

    def test_失败页面_记录错误信息(self):
        page = ParsedPage(page_number=3, content="", success=False, error="解析异常")
        assert page.success is False
        assert page.error == "解析异常"
        assert page.content == ""


class TestParseResult:
    """ParseResult 聚合结果测试"""

    def test_failure_rate_全部成功_返回0(self):
        result = ParseResult(
            pages=[ParsedPage(1, "a"), ParsedPage(2, "b")],
            total_pages=2, failed_pages=0
        )
        assert result.failure_rate == 0.0

    def test_failure_rate_全部失败_返回1(self):
        result = ParseResult(
            pages=[ParsedPage(1, "", success=False)],
            total_pages=1, failed_pages=1
        )
        assert result.failure_rate == 1.0

    def test_failure_rate_一半失败(self):
        result = ParseResult(
            pages=[
                ParsedPage(1, "ok"),
                ParsedPage(2, "", success=False),
            ],
            total_pages=2, failed_pages=1
        )
        assert result.failure_rate == 0.5

    def test_failure_rate_空文档_视为全部失败(self):
        result = ParseResult(total_pages=0, failed_pages=0)
        assert result.failure_rate == 1.0

    def test_full_text_仅拼接成功页面(self):
        result = ParseResult(
            pages=[
                ParsedPage(1, "第一页"),
                ParsedPage(2, "", success=False),
                ParsedPage(3, "第三页"),
            ],
            total_pages=3, failed_pages=1
        )
        assert result.full_text == "第一页\n\n第三页"

    def test_full_text_全部失败_返回空串(self):
        result = ParseResult(
            pages=[ParsedPage(1, "", success=False, error="err")],
            total_pages=1, failed_pages=1
        )
        assert result.full_text == ""

    def test_warnings_收集所有失败页面(self):
        result = ParseResult(
            pages=[
                ParsedPage(1, "ok"),
                ParsedPage(2, "", success=False, error="第2页错误"),
                ParsedPage(3, "", success=False, error="第3页错误"),
            ],
            total_pages=3, failed_pages=2
        )
        warnings = result.warnings
        assert len(warnings) == 2
        assert "第2页: 第2页错误" in warnings
        assert "第3页: 第3页错误" in warnings

    def test_warnings_无失败_返回空列表(self):
        result = ParseResult(
            pages=[ParsedPage(1, "ok")],
            total_pages=1, failed_pages=0
        )
        assert result.warnings == []


class TestParseText:
    """纯文本解析测试（md/txt）"""

    def test_txt_正常解析(self, tmp_path):
        file_path = tmp_path / "test.txt"
        file_path.write_text("这是一段测试文本。\n\n包含两段内容。", encoding="utf-8")

        result = _parse_text(str(file_path))
        assert result.total_pages == 1
        assert result.failed_pages == 0
        assert result.failure_rate == 0.0
        assert "测试文本" in result.full_text

    def test_md_正常解析(self, tmp_path):
        file_path = tmp_path / "readme.md"
        file_path.write_text("# 标题\n\n正文内容，**加粗**文字。", encoding="utf-8")

        result = _parse_text(str(file_path))
        assert result.failed_pages == 0
        assert "# 标题" in result.full_text
        assert result.failure_rate == 0.0

    def test_空文件_返回失败(self, tmp_path):
        file_path = tmp_path / "empty.txt"
        file_path.write_text("", encoding="utf-8")

        result = _parse_text(str(file_path))
        assert result.failed_pages == 1
        assert result.failure_rate == 1.0
        assert "内容为空" in result.pages[0].error

    def test_gbk编码_自动回退解析(self, tmp_path):
        file_path = tmp_path / "gbk.txt"
        file_path.write_bytes("GBK编码测试内容".encode("gbk"))

        result = _parse_text(str(file_path))
        assert result.failed_pages == 0
        assert "GBK编码测试内容" in result.full_text

    def test_文件不存在_返回失败(self):
        result = _parse_text("/nonexistent/file.txt")
        assert result.failed_pages == 1
        assert result.failure_rate == 1.0


class TestParsePdf:
    """PDF 解析测试（Mock PyPDF2）"""

    def test_正常PDF_逐页解析全部成功(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock(), MagicMock()]
        mock_reader.pages[0].extract_text.return_value = "第一页内容"
        mock_reader.pages[1].extract_text.return_value = "第二页内容"
        mock_reader.pages[2].extract_text.return_value = "第三页内容"

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert result.total_pages == 3
        assert result.failed_pages == 0
        assert result.failure_rate == 0.0
        assert len(result.pages) == 3
        assert result.pages[0].content == "第一页内容"
        assert result.pages[2].page_number == 3

    def test_部分页面无文本_标记失败(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock(), MagicMock()]
        mock_reader.pages[0].extract_text.return_value = "OK"
        mock_reader.pages[1].extract_text.return_value = ""
        mock_reader.pages[2].extract_text.return_value = "OK"

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert result.total_pages == 3
        assert result.failed_pages == 1
        assert not result.pages[1].success
        assert "无文本" in result.pages[1].error

    def test_单页解析异常_跳过继续(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]
        mock_reader.pages[0].extract_text.return_value = "OK"
        mock_reader.pages[1].extract_text.side_effect = RuntimeError("PDF 解析错误")

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert result.failed_pages == 1
        assert result.pages[0].success is True
        assert result.pages[1].success is False
        assert "PDF 解析错误" in result.pages[1].error

    def test_全部页面失败(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]
        mock_reader.pages[0].extract_text.return_value = ""
        mock_reader.pages[1].extract_text.side_effect = Exception("fail")

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert result.failed_pages == 2
        assert result.failure_rate == 1.0

    def test_PDF文件损坏(self):
        with patch("app.rag.parser.PdfReader", side_effect=ValueError("PDF 文件已损坏")):
            result = _parse_pdf("corrupted.pdf")

        assert result.failed_pages == 1
        assert result.failure_rate == 1.0
        assert "PDF 文件已损坏" in result.pages[0].error

    def test_PDF空文档_0页(self):
        mock_reader = MagicMock()
        mock_reader.pages = []

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("empty.pdf")

        assert result.total_pages == 0
        assert result.failure_rate == 1.0


class TestParseDocx:
    """DOCX 解析测试（Mock python-docx）"""

    def test_正常DOCX_逐段提取(self):
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="第一段内容"),
            MagicMock(text="第二段内容"),
        ]

        with patch("app.rag.parser.DocxDocument", return_value=mock_doc):
            result = _parse_docx("test.docx")

        assert result.total_pages == 2  # 逐段容错：每段一个 ParsedPage
        assert result.failed_pages == 0
        assert result.failure_rate == 0.0
        assert "第一段内容" in result.full_text
        assert "第二段内容" in result.full_text

    def test_空白段落被跳过_不影响容错率(self):
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="有效段落"),
            MagicMock(text=""),
            MagicMock(text="   "),
            MagicMock(text="另一有效段落"),
        ]

        with patch("app.rag.parser.DocxDocument", return_value=mock_doc):
            result = _parse_docx("test.docx")

        # 空白段落被跳过，不计入失败（仅计入 total_pages）
        assert result.total_pages == 4
        assert result.failed_pages == 0
        assert result.failure_rate == 0.0
        assert len(result.pages) == 2  # 仅有效段落创建 ParsedPage

    def test_DOCX全部空白_无有效文本(self):
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text=""),
            MagicMock(text="   "),
        ]

        with patch("app.rag.parser.DocxDocument", return_value=mock_doc):
            result = _parse_docx("empty.docx")

        assert result.failed_pages == 2
        assert result.failure_rate == 1.0
        assert "无有效文本" in result.pages[0].error

    def test_DOCX单段解析异常_跳过继续(self):
        bad_para = MagicMock()
        type(bad_para).text = PropertyMock(side_effect=RuntimeError("段落损坏"))

        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="正常段落"),
            bad_para,
            MagicMock(text="另一正常段落"),
        ]

        with patch("app.rag.parser.DocxDocument", return_value=mock_doc):
            result = _parse_docx("test.docx")

        assert result.failed_pages == 1
        assert result.total_pages == 3
        assert result.pages[0].success is True
        assert result.pages[2].success is True

    def test_DOCX文件损坏(self):
        with patch("app.rag.parser.DocxDocument", side_effect=ValueError("DOCX 文件损坏")):
            result = _parse_docx("corrupted.docx")

        assert result.failed_pages == 1
        assert result.failure_rate == 1.0
        assert "DOCX 文件损坏" in result.pages[0].error

    def test_DOCX无段落(self):
        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        with patch("app.rag.parser.DocxDocument", return_value=mock_doc):
            result = _parse_docx("empty.docx")

        assert result.failed_pages == 1
        assert "无段落" in result.pages[0].error


class TestParseDocumentDispatch:
    """parse_document 入口分发测试"""

    def test_文件不存在(self):
        result = parse_document("/nonexistent/test.pdf")
        assert result.failed_pages == 1
        assert "不存在" in result.pages[0].error

    def test_不支持的文件类型(self, tmp_path):
        file_path = tmp_path / "test.xyz"
        file_path.write_text("test", encoding="utf-8")

        result = parse_document(str(file_path), "xyz")
        assert result.failed_pages == 1
        assert "不支持" in result.pages[0].error

    def test_从扩展名自动推断类型_txt(self, tmp_path):
        file_path = tmp_path / "readme.txt"
        file_path.write_text("Hello World", encoding="utf-8")

        result = parse_document(str(file_path))
        assert result.failed_pages == 0
        assert "Hello World" in result.full_text

    def test_从扩展名自动推断类型_md(self, tmp_path):
        file_path = tmp_path / "readme.md"
        file_path.write_text("# Hello", encoding="utf-8")

        result = parse_document(str(file_path))
        assert result.failed_pages == 0


class TestFaultToleranceThresholds:
    """容错阈值场景测试（对齐 ARCHITECTURE.md §4.7）"""

    def test_5页PDF_1页失败_正好20pct(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock() for _ in range(5)]
        for i in range(4):
            mock_reader.pages[i].extract_text.return_value = f"第{i+1}页"
        mock_reader.pages[4].extract_text.return_value = ""

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert result.failure_rate == 0.2

    def test_3页PDF_1页失败_33pct_在20到50区间(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock() for _ in range(3)]
        mock_reader.pages[0].extract_text.return_value = "OK"
        mock_reader.pages[1].extract_text.side_effect = Exception("fail")
        mock_reader.pages[2].extract_text.return_value = "OK"

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert 0.2 < result.failure_rate < 0.5

    def test_2页PDF_1页失败_正好50pct(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]
        mock_reader.pages[0].extract_text.return_value = "OK"
        mock_reader.pages[1].extract_text.side_effect = Exception("fail")

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert result.failure_rate == 0.5

    def test_2页PDF_全部失败_100pct(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]
        mock_reader.pages[0].extract_text.side_effect = Exception("fail1")
        mock_reader.pages[1].extract_text.side_effect = Exception("fail2")

        with patch("app.rag.parser.PdfReader", return_value=mock_reader):
            result = _parse_pdf("test.pdf")

        assert result.failure_rate == 1.0
