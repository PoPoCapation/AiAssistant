"""文本切片 + 清洗（对应 IMPL 5.1，改进版）。

针对 FAQ / 规则 / 说明类文档优化，比纯字符滑窗更利于召回：
- 段落感知：先按空行 / 列表项拆段，再合并短段到目标长度；
- 句子边界：超长段按中英文句末标点（。；！？;!?\\n）切，尽量不切断句子；
- 清洗：去页码行、跨页重复短行（页眉页脚）、多余空行；
- 页面感知：PDF 按页切块，跨页合并时插入 ``[PAGE N]`` 标记，chunk 带 ``page_no``。
"""
from __future__ import annotations

import re

from domain.rag.model.entity.document import PageContent

# 句末标点（中英文）
_SENT_SPLIT = re.compile(r"(?<=[。；！？!?;\n])")
# 列表项标记：- • * ● / 1. 1) 1、 / (1) （1） / ①
_LIST_MARKER = re.compile(r"^\s*([-•*●]|\d+[.)、]|[(（]\d+[)）]|[①②③④⑤⑥⑦⑧⑨⑩])\s*")
# 页码 / 页脚模式：第N页 / page N / N/M / 纯数字
_PAGE_NO = re.compile(r"^\s*(第\s*\d+\s*页|p\.?\s*\d+|\d+\s*/\s*\d+|\d{1,4})\s*$", re.IGNORECASE)


def clean_text(text: str) -> str:
    """清洗单页文本：去页码行、压多余空行。"""
    lines = [ln for ln in text.splitlines() if not _PAGE_NO.match(ln)]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def clean_pages(pages: list[PageContent]) -> list[PageContent]:
    """清洗多页：先去页码，再去跨页重复短行（页眉页脚）。"""
    cleaned = [PageContent(page_no=p.page_no, text=clean_text(p.text)) for p in pages]
    if len(cleaned) < 2:
        return cleaned
    # 统计每行出现在多少页 -> 出现在多数页的短行视为页眉/页脚
    line_pages: dict[str, set[int]] = {}
    for p in cleaned:
        for ln in {ln.strip() for ln in p.text.splitlines() if ln.strip()}:
            line_pages.setdefault(ln, set()).add(p.page_no)
    threshold = max(2, len(cleaned) // 2)
    repeated = {ln for ln, s in line_pages.items() if len(s) >= threshold and len(ln) <= 30}
    out: list[PageContent] = []
    for p in cleaned:
        text = "\n".join(ln for ln in p.text.splitlines() if ln.strip() not in repeated)
        out.append(PageContent(page_no=p.page_no, text=text.strip()))
    return out


def split_paragraphs(text: str) -> list[str]:
    """按空行分段；若一段内多为列表项，则按项拆（FAQ / 规则友好）。"""
    if not text or not text.strip():
        return []
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text.strip()):
        para = para.strip()
        if not para:
            continue
        lines = para.splitlines()
        if len(lines) > 1 and sum(1 for ln in lines if _LIST_MARKER.match(ln)) >= len(lines) // 2:
            cur = ""
            for ln in lines:
                if _LIST_MARKER.match(ln):
                    if cur:
                        units.append(cur.strip())
                    cur = ln
                else:
                    cur += "\n" + ln
            if cur:
                units.append(cur.strip())
        else:
            units.append(para)
    return [u for u in units if u]


def _split_by_sentence(text: str, chunk_size: int) -> list[str]:
    """超长文本按句末标点切成 <= chunk_size 的段，尽量不切断句子。"""
    if len(text) <= chunk_size:
        return [text]
    pieces: list[str] = []
    buf = ""
    for part in _SENT_SPLIT.split(text):
        if not part:
            continue
        if len(buf) + len(part) <= chunk_size:
            buf += part
        else:
            if buf:
                pieces.append(buf)
            if len(part) <= chunk_size:
                buf = part
            else:  # 单句仍超长，硬切兜底
                for i in range(0, len(part), chunk_size):
                    pieces.append(part[i : i + chunk_size])
                buf = ""
        if len(buf) >= chunk_size:
            pieces.append(buf)
            buf = ""
    if buf:
        pieces.append(buf)
    return pieces


def merge_paragraphs(paras: list[str], chunk_size: int) -> list[str]:
    """把短段合并到 ~chunk_size；超长段按句子切。"""
    chunks: list[str] = []
    buf = ""
    for para in paras:
        if len(para) > chunk_size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_split_by_sentence(para, chunk_size))
        elif len(buf) + len(para) + 1 <= chunk_size:
            buf = (buf + "\n" + para) if buf else para
        else:
            if buf:
                chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c.strip()]


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 0) -> list[str]:
    """纯文本切块（段落感知 + 句子边界），无页面信息。"""
    paras = split_paragraphs(text)
    if not paras:
        return []
    return merge_paragraphs(paras, chunk_size)


def chunk_pages(pages: list[PageContent], chunk_size: int = 500) -> list[tuple[str, int]]:
    """按页切块：每段带 page_no，跨页合并时插入 ``[PAGE N]`` 标记。

    返回 ``[(chunk_text, page_no), ...]``，page_no 为该 chunk 起始页。
    """
    tagged: list[tuple[str, int]] = []
    for p in pages:
        for para in split_paragraphs(p.text):
            tagged.append((para, p.page_no))
    if not tagged:
        return []

    chunks: list[tuple[str, int]] = []
    buf = ""
    buf_page: int | None = None
    for para, pno in tagged:
        if len(para) > chunk_size:
            if buf:
                chunks.append((buf, buf_page))  # type: ignore[arg-type]
                buf = ""
            for piece in _split_by_sentence(para, chunk_size):
                chunks.append((piece, pno))
            continue
        sep = f"\n[PAGE {pno}]\n" if (buf and pno != buf_page) else ""
        if not buf:
            buf = para
            buf_page = pno
        elif len(buf) + len(sep) + len(para) + 1 <= chunk_size:
            buf += sep + para
        else:
            chunks.append((buf, buf_page))  # type: ignore[arg-type]
            buf = para
            buf_page = pno
    if buf:
        chunks.append((buf, buf_page))  # type: ignore[arg-type]
    return [(c, p) for c, p in chunks if c.strip()]
