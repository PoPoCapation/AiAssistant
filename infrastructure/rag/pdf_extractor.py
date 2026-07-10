"""PDF 文本提取（OCR，对应 IMPL 5.1）。

用 ``pypdfium2`` 把 PDF 每页渲染成图片，再调百炼 ``qwen-vl-ocr`` 识别文字。
- ``extract_pages``：返回每页 ``PageContent``（page_no + text），保留页面元信息；
- ``extract_text``：拼接所有页，带 ``[PAGE N]`` 页标记。
多页并发 OCR。
"""
from __future__ import annotations

import asyncio
import base64
import io

import httpx
import pypdfium2 as pdfium
from PIL import Image

from common.enums import ResponseCode
from common.exception import AppException
from domain.rag.model.entity.document import PageContent

_OCR_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
_DEFAULT_PROMPT = "提取图片中的所有文字，保持原文输出。"


class PdfOcrExtractor:
    """PDF -> 图片 -> qwen-vl-ocr 文字提取。"""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-vl-ocr",
        prompt: str = _DEFAULT_PROMPT,
        scale: float = 2.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._prompt = prompt
        self._scale = scale

    async def _ocr_image(self, client: httpx.AsyncClient, image: Image.Image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        try:
            resp = await client.post(
                _OCR_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "input": {
                        "messages": [
                            {"role": "user", "content": [{"image": data_uri}, {"text": self._prompt}]}
                        ]
                    },
                },
            )
        except Exception as e:
            raise AppException(ResponseCode.LLM_ERROR, f"OCR 调用失败: {e}", cause=e) from e
        if resp.status_code != 200:
            raise AppException(ResponseCode.LLM_ERROR, f"OCR HTTP {resp.status_code}: {resp.text[:200]}")
        choices = resp.json().get("output", {}).get("choices", [])
        if not choices:
            return ""
        for part in choices[0].get("message", {}).get("content", []):
            if part.get("text"):
                return part["text"]
        return ""

    async def extract_pages(self, data: bytes) -> list[PageContent]:
        """提取每页文字，返回 ``PageContent`` 列表（page_no 从 1 开始）。"""
        pdf = pdfium.PdfDocument(io.BytesIO(data))
        n_pages = len(pdf)
        if n_pages == 0:
            return []
        images = [pdf[i].render(scale=self._scale).to_pil() for i in range(n_pages)]
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            texts = await asyncio.gather(*[self._ocr_image(client, img) for img in images])
        return [PageContent(page_no=i + 1, text=t) for i, t in enumerate(texts)]

    async def extract_text(self, data: bytes) -> str:
        """提取并拼接全文，带 ``[PAGE N]`` 页标记。"""
        pages = await self.extract_pages(data)
        return "\n".join(f"[PAGE {p.page_no}]\n{p.text}" for p in pages if p.text).strip()
