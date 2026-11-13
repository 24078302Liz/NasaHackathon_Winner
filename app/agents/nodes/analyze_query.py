"""查询分析 / 路由节点：判断问题类型、抽取过滤条件与调查 id。"""
from __future__ import annotations

import json
import re

from app.agents.prompts import QUERY_ANALYSIS_SYSTEM
from app.agents.state import GraphState
from app.services.llm import get_small_llm

VALID_INVESTIGATION_IDS = {"BASS", "BASS-II", "BASS-M", "Saffire"}


def _parse_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象，容错处理前后噪声。"""
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def analyze_query(state: GraphState) -> GraphState:
    question = state["question"]

    llm = get_small_llm(temperature=0.0)
    raw = llm.invoke(QUERY_ANALYSIS_SYSTEM + "\n\n用户问题：" + question)
    content = raw.content if hasattr(raw, "content") else str(raw)
    parsed = _parse_json(content)

    qtype = parsed.get("question_type", "search")
    if qtype not in ("search", "compare", "invalid"):
        qtype = "search"

    filters = parsed.get("filters") or {}
    selected_ids = [i for i in (parsed.get("selected_ids") or []) if i in VALID_INVESTIGATION_IDS]

    if qtype == "compare" and len(selected_ids) != 2:
        # 声明要对比但没给出两个合法调查 → 退回普通搜索
        qtype = "search"

    state["question_type"] = qtype
    state["filters"] = filters
    state["selected_ids"] = selected_ids
    return state
