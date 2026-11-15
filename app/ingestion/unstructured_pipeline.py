"""PDF processing with Unstructured: cleaning and structuring before chunking.

Flow: partition_pdf(strategy="hi_res") -> build_clean_elements() -> chunk_by_title()

Unstructured hi_res does not extract font sizes; category_depth is only 0 or None.
This module uses PyMuPDF (fitz) to extract line font sizes relative to the modal body size.
Larger font sizes define descending heading levels for the heading stack.

This module returns clean_elements without chunking or merging elements into one large string.

Dependencies: unstructured, unstructured-client, and pymupdf; hosted parsing needs no local OCR models.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Type checking only; imports are lazy at runtime
    from unstructured.documents.elements import Element

# Filtering rules (requirement 1)
DROP_CATEGORIES = {"Header", "Footer", "Image", "PageBreak"}
TOC_TITLES = {"table of contents", "contents"}
REFERENCE_TITLES = {
    "references", "citations", "bibliography",
    "reference list", "literature cited", "works cited",
}
ACRONYM_TITLES = {
    "acronyms", "abbreviations",
    "acronyms and abbreviations", "abbreviations and acronyms",
    "list of acronyms", "list of abbreviations",
}
AD_KEYWORDS = ("complete iss researcher", "researcher's guide series")
TITLE_BLACKLIST = {"the lab is open"}

# Body elements receive the heading stack prefix
BODY_CATEGORIES = {"NarrativeText", "FigureCaption", "ListItem", "Text", "UncategorizedText"}


def partition_pdf_hi_res(path: str):
    """Partition with hosted Unstructured hi_res; require an API key and never use auto."""
    from app.config import settings

    if not settings.unstructured_api_key:
        raise RuntimeError(
            "UNSTRUCTURED_API_KEY is not configured. This project uses the hosted Unstructured API. "
            "Set UNSTRUCTURED_API_KEY in your backend .env file."
        )
    return _partition_via_api(path)


def _partition_via_api(path: str):
    """Parse through hosted Unstructured Transform using the local transform client.

    Convert returned element dictionaries to Element instances with elements_from_dicts.
    The default server URL is https://transform.unstructured.io.
    """
    from unstructured.staging.base import elements_from_dicts
    from unstructured_transform_client import TransformClient

    from app.config import settings

    client_kwargs = {"timeout_seconds": 960}  # Exceeds the server default wait of 900 seconds
    if settings.unstructured_api_key:
        client_kwargs["api_key"] = settings.unstructured_api_key
    if settings.unstructured_api_url:
        client_kwargs["server_url"] = settings.unstructured_api_url

    with TransformClient(**client_kwargs) as client:
        result = client.parse.run(input=path, output="elements")

    elements = getattr(result, "elements", None)
    if elements is None:
        raise RuntimeError(
            "Unstructured Parse returned no elements. Processing may still be in progress; retry or increase timeout_seconds."
        )
    # Convert SDK Pydantic models to dictionaries before elements_from_dicts
    dicts = []
    for e in elements:
        d = e.model_dump() if hasattr(e, "model_dump") else e
        if isinstance(d, dict):
            meta = d.get("metadata")
            if isinstance(meta, dict):
                # Remove fields whose values are None, for example coordinates
                # Prevent ElementMetadata.from_dict from calling .get on None
                d["metadata"] = {k: v for k, v in meta.items() if v is not None}
        dicts.append(d)
    return elements_from_dicts(dicts)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_title_levels(path: str) -> dict[str, int]:
    """Extract font sizes with PyMuPDF, excluding cover pages, relative to body text.

    - Use the most frequent font size as the body baseline.
    - At least 1.5x body size: level 1; at least 1.2x: level 2; above body size: level 3.
    - Exclude the cover and final two pages to avoid oversized cover or advertisement text.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    total = doc.page_count
    # Exclude the cover and final three pages: advertisements, contents, or blank pages
    skip_pages = {1, total, total - 1, total - 2}
    lines: list[tuple[str, float]] = []
    try:
        for page_num, page in enumerate(doc, start=1):
            if page_num in skip_pages:
                continue
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
                    sizes = [s["size"] for s in line.get("spans", []) if s.get("text", "").strip()]
                    if text and sizes:
                        lines.append((_normalize(text), max(sizes)))
    finally:
        doc.close()

    if not lines:
        return {}

    body_size = Counter(round(s, 1) for _, s in lines).most_common(1)[0][0]

    mapping: dict[str, int] = {}
    for text, size in lines:
        r = round(size, 1)
        if r <= body_size:  # Body-size text is not a heading
            continue
        ratio = r / body_size
        if ratio >= 1.5:
            level = 1
        elif ratio >= 1.2:
            level = 2
        else:
            level = 3
        if text not in mapping or level < mapping[text]:
            mapping[text] = level
    return mapping


def _clean_text(text: str) -> str:
    """Requirement 4: repair hyphenation and compress newlines; no stemming, stopword removal, or translation."""
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)   # Join words hyphenated across lines
    text = re.sub(r"\n{3,}", "\n\n", text)            # Preserve paragraph breaks with two newlines
    return text


def _title_level(el, title_levels: dict[str, int] | None = None) -> int:
    """Infer heading levels 1, 2, or 3.

    Priority: font mapping, metadata.category_depth, numbering patterns, then heuristics.
    """
    if title_levels:
        level = title_levels.get(_normalize(el.text))
        if level is not None:
            return level
    depth = getattr(el.metadata, "category_depth", None)
    if isinstance(depth, int) and depth >= 1:
        return depth
    t = el.text.strip()
    m = re.match(r"^(\d+(?:\.\d+)*)[\.\s]", t)
    if m:
        return m.group(1).count(".") + 1
    if len(t) <= 40 and t == t.upper():
        return 1
    return 2


def _is_ad(text: str) -> bool:
    return any(k in text.lower() for k in AD_KEYWORDS)


def _table_to_narrative(table) -> str:
    """Requirement 2: convert HTML tables to readable rows with pipe-separated cells."""
    html = getattr(table.metadata, "text_as_html", None) or table.text or ""
    if "<tr" in html.lower():
        lines = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL | re.IGNORECASE)
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
            if any(cells):
                lines.append(" | ".join(cells))
        return "\n".join(lines)
    return re.sub(r"<[^>]+>", " ", html)


def build_clean_elements(
    elements,
    *,
    investigation_id: str,
    document_id: str,
    source_url: str = "",
    title_levels: dict[str, int] | None = None,
):
    """Requirements 1-5: filter, process tables, prepend headings, clean, and attach metadata.

    Return clean_elements without calling any chunking functions.
    """
    from unstructured.documents.elements import NarrativeText

    clean = []
    title_stack: list[str] = []
    state = "body"  # body | toc | references | acronyms
    toc_reference: list[str] = []  # Contents headings are in-memory references only

    for el in elements:
        category = getattr(el, "category", None)

        if category in DROP_CATEGORIES:
            continue

        if category == "Title":
            t = el.text.strip()
            tl = t.lower()

            if tl in TITLE_BLACKLIST:
                continue

            if tl in TOC_TITLES:
                state = "toc"
                continue
            if tl in REFERENCE_TITLES:
                state = "references"
                continue
            if tl in ACRONYM_TITLES:
                state = "acronyms"
                level = _title_level(el, title_levels)
                title_stack = title_stack[: level - 1] + [t]
                clean.append(el)
                continue

            state = "body"
            level = _title_level(el, title_levels)
            title_stack = title_stack[: level - 1] + [t]
            clean.append(el)
            continue

        if state == "toc":
            toc_reference.append(el.text)
            continue
        if state == "references":
            continue

        if _is_ad(el.text):
            continue

        if state == "acronyms":
            el.text = _clean_text(el.text)
            clean.append(el)
            continue

        if category in BODY_CATEGORIES:
            prefix = "->".join(title_stack) + "->" if title_stack else ""
            el.text = _clean_text(prefix + el.text)
            clean.append(el)
            continue

        if category == "Table":
            clean.append(el)  # Preserve the original table and text_as_html for provenance
            prefix = "->".join(title_stack) + "->" if title_stack else ""
            narrative = NarrativeText(text=_clean_text(prefix + _table_to_narrative(el)))
            clean.append(narrative)
            continue

        el.text = _clean_text(el.text)
        clean.append(el)

    # Requirement 5: attach global metadata; Unstructured already retains page_number
    for el in clean:
        setattr(el.metadata, "investigation_id", investigation_id)
        setattr(el.metadata, "document_id", document_id)
        setattr(el.metadata, "source_url", source_url)

    return clean


def process_pdf(
    path: str,
    *,
    investigation_id: str,
    document_id: str,
    source_url: str = "",
):
    """Combine font hierarchy extraction, hi_res partitioning, and build_clean_elements."""
    title_levels = extract_title_levels(path)
    elements = partition_pdf_hi_res(path)
    return build_clean_elements(
        elements,
        investigation_id=investigation_id,
        document_id=document_id,
        source_url=source_url,
        title_levels=title_levels,
    )


def chunk_elements(
    clean_elements,
    *,
    max_characters: int = 1200,
    new_after_n_chars: int = 1000,
    overlap: int = 150,
):
    """Chunk clean_elements by title and return CompositeElement instances.

    Database writes belong to indexer.insert_passages.
    """
    from unstructured.chunking.title import chunk_by_title

    return chunk_by_title(
        clean_elements,
        max_characters=max_characters,
        new_after_n_chars=new_after_n_chars,
        overlap=overlap,
        combine_text_under_n_chars=200,   # Combine short sections to reduce fragmentation
    )


def chunk_to_passage(
    chunk,
    index: int,
    *,
    investigation_id: str,
    document_id: str,
    source_url: str = "",
) -> dict:
    """Convert a CompositeElement chunk to a passage dictionary without dense_vector.

    indexer.insert_passages computes BGE dense vectors; Milvus BM25 computes sparse vectors.
    Structured experimental fields remain None; table values are not extracted at this stage.
    """
    page = getattr(chunk.metadata, "page_number", None)
    return {
        "evidence_id": f"{document_id}-c{index + 1}",
        "document_id": document_id,
        "investigation_id": investigation_id,
        "test_id": None,
        "text": chunk.text,
        "page": str(page) if page is not None else None,
        "source_url": source_url,
        "material": None,
        "gravity_condition": None,
        "oxygen_value": None,
        "oxygen_unit": None,
        "pressure_value": None,
        "pressure_unit": None,
        "airflow_value": None,
        "airflow_unit": None,
        "research_focus": None,
    }
