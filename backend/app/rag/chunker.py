"""智能分块 — 使用 RecursiveCharacterTextSplitter 对文档全文执行固定大小分块

对齐 ARCHITECTURE.md §4.2:
- 算法: RecursiveCharacterTextSplitter
- 分隔符优先级: 段落 → 换行 → 中文标点 → 英文标点 → 空格 → 字符
- chunk_size: 1000 chars（800-1200 范围）
- chunk_overlap: 150 chars（≈50 tokens）
- keep_separator: True（中文场景保留语义完整性）
- Token 估算: int(len(content) / 1.5)，不引入 tiktoken
"""

import logging
from dataclasses import dataclass, field

from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.rag.parser import ParsedPage

from app.config import settings

logger = logging.getLogger(__name__)

# 分隔符优先级（对齐 ARCHITECTURE.md §4.2）
# RecursiveCharacterTextSplitter.separators 是精确字符串匹配，非正则，
# 因此中文/英文标点展开为独立字符，才能在每个标点处正确断句。
CHUNK_SEPARATORS = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]


@dataclass
class ChunkResult:
    """单个分块结果"""
    content: str
    chunk_index: int
    page_number: int | None
    estimated_tokens: int


@dataclass
class ChunkingResult:
    """分块聚合结果"""
    chunks: list[ChunkResult] = field(default_factory=list)
    total_chunks: int = 0


def chunk_document(
    text: str,
    pages: list[ParsedPage] | None = None,
    chunk_size: int = settings.CHUNK_SIZE,
    chunk_overlap: int = settings.CHUNK_OVERLAP,
) -> ChunkingResult:
    """对文档全文执行智能分块，可选附带页码元数据。

    Args:
        text: 文档全文（ParseResult.full_text）
        pages: 解析结果中的页面列表，用于回溯每块的来源页码
        chunk_size: 每块最大字符数
        chunk_overlap: 块间重叠字符数

    Returns:
        ChunkingResult: 包含所有分块及总数
    """
    if not text or not text.strip():
        logger.warning("文档全文为空，跳过智能分块")
        return ChunkingResult()

    splitter = RecursiveCharacterTextSplitter(
        separators=CHUNK_SEPARATORS,
        keep_separator=True,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )

    chunk_texts = splitter.split_text(text)
    logger.info(f"文档分块完成: {len(chunk_texts)} 块")

    # 构建页码偏移映射，用于回溯每块的来源页码
    page_offset_map = _build_page_offset_map(pages) if pages else []

    # 通过累进搜索定位每块在全文中的偏移量，避免重复片段歧义
    chunks: list[ChunkResult] = []
    search_start = 0
    for i, chunk_text in enumerate(chunk_texts):
        start_offset = text.find(chunk_text, search_start)
        if start_offset != -1:
            search_start = start_offset + len(chunk_text)
        page_number = _resolve_page_number(start_offset, page_offset_map)
        estimated_tokens = estimate_tokens(chunk_text)
        chunks.append(ChunkResult(
            content=chunk_text,
            chunk_index=i,
            page_number=page_number,
            estimated_tokens=estimated_tokens,
        ))

    return ChunkingResult(chunks=chunks, total_chunks=len(chunks))


def _build_page_offset_map(pages: list[ParsedPage]) -> list[tuple[int, int]]:
    """构建 (字符偏移量, 页码) 映射列表，按偏移量升序。

    重建 full_text 拼接逻辑：每页 content 后跟 "\n\n" 分隔符。
    """
    offset_map: list[tuple[int, int]] = []
    pos = 0
    for page in pages:
        if page.success and page.content:
            offset_map.append((pos, page.page_number))
            pos += len(page.content) + 2  # +2 for "\n\n"
    return offset_map


def _resolve_page_number(
    start_offset: int,
    offset_map: list[tuple[int, int]],
) -> int | None:
    """通过字符偏移量在偏移映射中反查来源页码。"""
    if not offset_map or start_offset == -1:
        return None

    page_number: int | None = None
    for offset, pg in offset_map:
        if offset <= start_offset:
            page_number = pg
        else:
            break

    return page_number


def estimate_tokens(text: str) -> int:
    """用字符数估算 token 数。

    中文字符占比 > 30% → 1 token ≈ 1.5 字符
    否则（纯英文/英文为主）→ 1 token ≈ 4.0 字符
    """
    if not text:
        return 1

    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    ratio = 1.5 if chinese_chars / len(text) > 0.3 else 4.0
    return max(1, int(len(text) / ratio))
