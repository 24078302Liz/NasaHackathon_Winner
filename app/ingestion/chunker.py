"""Split text at paragraph boundaries and preserve provenance.

Evidence IDs combine the document ID and chunk sequence number.
For PDF page references, preserve page metadata in the loader and pass it to the chunker.
"""
from __future__ import annotations

import re

MAX_CHARS = 1200
OVERLAP = 150


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split long text into pieces no larger than max_chars."""
    parts = []
    while len(text) > max_chars:
        parts.append(text[:max_chars])
        text = text[max_chars:]
    if text:
        parts.append(text)
    return parts


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
        if len(para) > MAX_CHARS:
            # Flush buffered text before splitting a paragraph that exceeds the size limit.
            if buf.strip():
                chunks.append(_make(buf, document_id, investigation_id, source_url, len(chunks)))
                buf = ""
            for sub in _split_long(para, MAX_CHARS):
                chunks.append(_make(sub, document_id, investigation_id, source_url, len(chunks)))
            continue

        if buf and len(buf) + len(para) + 1 > MAX_CHARS:
            chunks.append(_make(buf, document_id, investigation_id, source_url, len(chunks)))
            # Retain the last OVERLAP characters to preserve context between chunks.
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
