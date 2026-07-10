"""文档上传入库接口（对应 IMPL 5.1）。

- ``POST /api/v1/assistant/upload``：JSON 文本入库（段落+句子切块）。
- ``POST /api/v1/assistant/upload/file``：PDF / TXT 文件入库。
  - PDF：走 OCR 提取每页 -> 清洗 -> 按页切块（带 page_no + 跨页标记）-> 入库；
  - TXT：直接解码 -> 切块 -> 入库。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from api.response import Response
from app.dependency import get_pdf_extractor, get_retrieval_service
from common.enums import ResponseCode
from domain.rag.service.retrieval_service import IRetrievalService
from infrastructure.rag.pdf_extractor import PdfOcrExtractor

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


class UploadRequest(BaseModel):
    """文本入库请求。"""

    text: str = Field(..., description="要入库的文本（规则 / FAQ / 文档）")
    source: str = Field(default="manual", description="来源标记，便于追溯")


@router.post("/upload")
async def upload(req: UploadRequest, svc: IRetrievalService = Depends(get_retrieval_service)):
    """文本切块、嵌入、写入向量库。"""
    n = await svc.ingest(req.text, req.source)
    return Response.success({"chunks": n})


@router.post("/upload/file")
async def upload_file(
    file: UploadFile = File(...),
    svc: IRetrievalService = Depends(get_retrieval_service),
    extractor: PdfOcrExtractor = Depends(get_pdf_extractor),
):
    """上传 PDF / TXT 文件入库。PDF 走 OCR 提取每页 + 清洗 + 按页切块。"""
    data = await file.read()
    name = (file.filename or "").lower()
    ctype = (file.content_type or "").lower()

    if name.endswith(".pdf") or ctype == "application/pdf":
        pages = await extractor.extract_pages(data)
        n = await svc.ingest_pages(pages, source=file.filename or "file")
        return Response.success({"chunks": n, "pages": len(pages)})
    if name.endswith(".txt") or ctype.startswith("text/"):
        text = data.decode("utf-8", errors="ignore")
        n = await svc.ingest(text, source=file.filename or "file")
        return Response.success({"chunks": n, "chars": len(text)})
    return Response.failure(ResponseCode.ILLEGAL_PARAMETER, "仅支持 PDF / TXT")
