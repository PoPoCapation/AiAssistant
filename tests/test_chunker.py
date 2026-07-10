"""阶段 5 切片器测试（纯文本，无需 API/Qdrant）。

直接运行：.venv/Scripts/python.exe tests/test_chunker.py
验证：段落拆分（含列表项）、句子边界切块、页面标记 [PAGE N]、清洗页码/页眉页脚。
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from domain.rag.model.entity.document import PageContent
from infrastructure.rag.text_chunker import (
    chunk_pages,
    chunk_text,
    clean_pages,
    clean_text,
    split_paragraphs,
)


def test_split_paragraphs_list() -> None:
    """含列表项的段落应按项拆。"""
    text = "标题\n\n第一段。第二句。\n\n- 项一\n- 项二\n- 项三"
    paras = split_paragraphs(text)
    assert len(paras) >= 4, paras  # 标题 + 段 + 3 个列表项
    assert any("项一" in p for p in paras)
    assert any("项三" in p for p in paras)


def test_chunk_text_sentence_aware() -> None:
    """超长文本按句号切，不切断句子。"""
    long = "这是一句话。" * 80  # 480 字符，单段
    chunks = chunk_text(long, chunk_size=100)
    assert len(chunks) > 1
    assert all(len(c) <= 110 for c in chunks), [len(c) for c in chunks]
    assert all(c.rstrip().endswith("。") for c in chunks), "不应在句中切断"


def test_chunk_pages_page_marker() -> None:
    """短文本跨页合并应插入 [PAGE N] 标记，page_no 为起始页。"""
    pages = [PageContent(page_no=1, text="第一页内容。"), PageContent(page_no=2, text="第二页内容。")]
    chunks = chunk_pages(pages, chunk_size=500)
    assert len(chunks) >= 1
    joined = "\n".join(c for c, _ in chunks)
    assert "[PAGE 2]" in joined, joined  # 跨页标记
    assert chunks[0][1] == 1  # 起始页码


def test_chunk_pages_respects_size() -> None:
    """两页各自较长时应分块，且存在起始页为 2 的 chunk。"""
    p1 = PageContent(page_no=1, text="句一。" * 50)
    p2 = PageContent(page_no=2, text="句二。" * 50)
    chunks = chunk_pages([p1, p2], chunk_size=100)
    assert len(chunks) > 1
    assert any(pno == 2 for _, pno in chunks)


def test_clean_text_removes_page_numbers() -> None:
    """页码行（纯数字 / 第N页）应被去掉，正文保留。"""
    assert "3" not in clean_text("正文\n3")
    assert "正文" in clean_text("正文\n3")
    assert "第 5 页" not in clean_text("正文\n第 5 页")


def test_clean_pages_removes_repeated_header() -> None:
    """跨页重复的短行（页眉页脚）应被去掉，正文保留。"""
    pages = [
        PageContent(page_no=1, text="公司页眉\n第一页正文\n1"),
        PageContent(page_no=2, text="公司页眉\n第二页正文\n2"),
    ]
    cleaned = clean_pages(pages)
    text = "\n".join(p.text for p in cleaned)
    assert "公司页眉" not in text, "重复页眉应被去掉"
    assert "第一页正文" in text and "第二页正文" in text
    assert "1" not in text.split() and "2" not in text.split(), "页码应被去掉"


if __name__ == "__main__":
    test_split_paragraphs_list()
    test_chunk_text_sentence_aware()
    test_chunk_pages_page_marker()
    test_chunk_pages_respects_size()
    test_clean_text_removes_page_numbers()
    test_clean_pages_removes_repeated_header()
    print("\n切片器测试通过 ✓")
