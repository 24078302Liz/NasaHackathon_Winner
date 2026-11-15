"""基于 unstructured.io 的 PDF 处理流水线（切片前的清洗与结构化）。

流程：partition_pdf(strategy="hi_res") → build_clean_elements() → 交给 chunk_by_title()

标题层级：unstructured 不提取字体大小（hi_res 的 category_depth 只是 0/None），
本模块用 PyMuPDF(fitz) 独立提取每行字号，以正文众数为基准、比正文大的字号降序分档，
得到「标题文本 → 层级」映射，供标题栈使用（一级标题字号 > 二级 > 三级）。

本模块只产出 clean_elements，【不在此处做 chunk 分块】，也【绝不把 elements 合并成大字符串】。

依赖：unstructured + unstructured-client + pymupdf（托管 API，无需本地模型与 poppler/tesseract）。
"""
from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 仅类型检查用，运行时懒加载
    from unstructured.documents.elements import Element

# ── 过滤规则（要求 1）──
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

# 正文类：需要拼标题栈前缀
BODY_CATEGORIES = {"NarrativeText", "FigureCaption", "ListItem", "Text", "UncategorizedText"}


def partition_pdf_hi_res(path: str):
    """hi_res 分区（Unstructured 托管 API，禁止 auto）。未配置 key 时给出明确提示。"""
    from app.config import settings

    if not settings.unstructured_api_key:
        raise RuntimeError(
            "未配置 UNSTRUCTURED_API_KEY。本项目使用 Unstructured 托管 API，"
            "请在 backend/.env 里填写 UNSTRUCTURED_API_KEY。"
        )
    return _partition_via_api(path)


def _partition_via_api(path: str):
    """托管 API（Unstructured Transform）：云端 Parse，本地只装 unstructured-transform-client。

    返回 Element 列表（用 elements_from_dicts 把 Parse 返回的 element dict 转回 Element）。
    默认 server_url 即 https://transform.unstructured.io。
    """
    from unstructured.staging.base import elements_from_dicts
    from unstructured_transform_client import TransformClient

    from app.config import settings

    client_kwargs = {"timeout_seconds": 960}  # 略大于服务端默认 900s 等待
    if settings.unstructured_api_key:
        client_kwargs["api_key"] = settings.unstructured_api_key
    if settings.unstructured_api_url:
        client_kwargs["server_url"] = settings.unstructured_api_url

    with TransformClient(**client_kwargs) as client:
        result = client.parse.run(input=path, output="elements")

    elements = getattr(result, "elements", None)
    if elements is None:
        raise RuntimeError(
            "Unstructured Parse 未返回 elements（可能仍在处理中）。请稍后重试或增大 timeout_seconds。"
        )
    # Transform SDK 返回的是 Pydantic 模型（不是 dict），先转成 dict 再交给 elements_from_dicts
    dicts = []
    for e in elements:
        d = e.model_dump() if hasattr(e, "model_dump") else e
        if isinstance(d, dict):
            meta = d.get("metadata")
            if isinstance(meta, dict):
                # 删除值为 None 的字段（如 coordinates=null），
                # 避免 ElementMetadata.from_dict 对 None 调 .get 报错
                d["metadata"] = {k: v for k, v in meta.items() if v is not None}
        dicts.append(d)
    return elements_from_dicts(dicts)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_title_levels(path: str) -> dict[str, int]:
    """用 PyMuPDF 提取字号，排除封面/封底，按相对正文字号分层。

    - 正文基准 = 出现最多的字号（众数）
    - 字号 >= 正文 1.5x → 一级（章）；>= 1.2x → 二级（节）；> 正文 → 三级（实验名）
    - 排除 page 1（封面）与最后 2 页（封底/丛书广告），避免大字号干扰分档
    """
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    total = doc.page_count
    # 排除封面（p1）与最后 3 页（封底丛书广告 + 目录 + 可能的空白尾页）
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
        if r <= body_size:  # 字号不大于正文，不是标题
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
    """要求 4：只修复断词与压缩换行，严禁词干/停用词/翻译。"""
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)   # 修复跨行断词 flammabil-\nity → flammability
    text = re.sub(r"\n{3,}", "\n\n", text)            # 连续换行压缩为 2 个，保留段落分隔
    return text


def _title_level(el, title_levels: dict[str, int] | None = None) -> int:
    """推断标题层级 1/2/3。

    优先级：字体字号映射（fitz）> metadata.category_depth > 编号模式 > 启发式。
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
    """要求 2：把表格 HTML 转成可读的行文本（单元格用 | 分隔）。"""
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
    """要求 1/2/3/4/5：过滤 → 表格处理 → 标题栈拼接 → 清洗 → 挂元数据。

    返回 clean_elements（Element 列表）。不调用任何 chunk 分块函数。
    """
    from unstructured.documents.elements import NarrativeText

    clean = []
    title_stack: list[str] = []
    state = "body"  # body | toc | references | acronyms
    toc_reference: list[str] = []  # 目录标题仅内存参考，不入库

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
            clean.append(el)  # 原始 Table（text_as_html）供溯源，不改 text
            prefix = "->".join(title_stack) + "->" if title_stack else ""
            narrative = NarrativeText(text=_clean_text(prefix + _table_to_narrative(el)))
            clean.append(narrative)
            continue

        el.text = _clean_text(el.text)
        clean.append(el)

    # 要求 5：挂载全局元数据（page_number 已由 unstructured 保留）
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
    """组合：提取字号层级 + partition(hi_res) + build_clean_elements。"""
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
    """用 chunk_by_title 对 clean_elements 切片，返回 CompositeElement 列表。

    不在此处写库；写库交给 indexer.insert_passages。
    """
    from unstructured.chunking.title import chunk_by_title

    return chunk_by_title(
        clean_elements,
        max_characters=max_characters,
        new_after_n_chars=new_after_n_chars,
        overlap=overlap,
        combine_text_under_n_chars=200,   # 太短的段合并到前一块，避免碎片
    )


def chunk_to_passage(
    chunk,
    index: int,
    *,
    investigation_id: str,
    document_id: str,
    source_url: str = "",
) -> dict:
    """把一个 CompositeElement chunk 转成 passage dict（不含 dense_vector）。

    dense_vector 由 indexer.insert_passages 统一用 BGE 生成；sparse 由 Milvus BM25 生成。
    结构化实验字段（oxygen/airflow/...）此阶段不抽表格数值，先置 None。
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
