"""分块：按段落边界切分，保留 provenance。

说明：当前按段落切分，evidence_id 用 document_id + 序号。
后续若需要精确到 PDF 页码，可在 loaders 里保留分页信息，把 page 传给 chunker。
"""
from __future__ import annotations

import re

MAX_CHARS = 1200
OVERLAP = 150


def chunk_text(
    text: str,
    *,
    document_id: str,
    investigation_id: str,
    source_url: str = "",
) -> list[dict]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    chunks: list[dict] = []
    buf = ""
    for para in paragraphs:
        if buf and len(buf) + len(para) + 1 > MAX_CHARS:
            chunks.append(_make(buf, document_id, investigation_id, source_url, len(chunks)))
            # 简单重叠：保留末尾 OVERLAP 字符，缓解跨块语义断裂
            buf = buf[-OVERLAP:] + "\n\n" + para
        else:
            buf = (buf + "\n\n" + para).strip()

    if buf.strip():
        chunks.append(_make(buf, document_id, investigation_id, source_url, len(chunks)))
    return chunks


def _make(text: str, document_id: str, investigation_id: str, source_url: str, seq: int) -> dict:
    return {
        "evidence_id": f"{document_id}-p{seq + 1}",
        "document_id": document_id,
        "investigation_id": investigation_id,
        "text": text,
        "source_url": source_url,
    }
