"""RAG 实体（值对象）。"""
from __future__ import annotations

from pydantic import BaseModel


class PageContent(BaseModel):
    """PDF 一页的 OCR 结果：页码 + 文本。"""

    page_no: int
    text: str


class DocumentChunk(BaseModel):
    """一个文档片段：内容 + 来源 + 相似度分 + 页码。"""

    id: str
    content: str
    source: str = ""
    score: float = 0.0
    page_no: int | None = None
