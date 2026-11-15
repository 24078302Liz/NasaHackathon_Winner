# LangGraph workflow

Implementation: `app/agents/graph.py`. State: `app/agents/state.py`. Nodes: `app/agents/nodes/`.

```mermaid
flowchart TD
    START --> entry{route_entry}
    entry -->|compare with at least two IDs| retrieve_compare
    entry -->|invalid| fallback_invalid
    entry -->|otherwise| analyze_query
    analyze_query --> intent{route_after_analyze}
    intent -->|search| retrieve
    intent -->|compare| retrieve_compare
    intent -->|invalid| fallback_invalid
    retrieve --> grade_evidence
    grade_evidence --> grade{route_after_grade}
    grade -->|sufficient| generate_answer
    grade -->|insufficient| fallback_insufficient
    retrieve_compare --> generate_comparison
    generate_answer --> validate_citations
    generate_comparison --> validate_citations
    validate_citations --> END
    fallback_invalid --> END
    fallback_insufficient --> END
```

| Node | Responsibility | External service |
|---|---|---|
| analyze_query | Classify intent and extract explicit filters and investigation IDs | Small language model |
| retrieve | Retrieve and rank evidence passages by investigation | Milvus |
| grade_evidence | Assess evidence sufficiency with rules and model grading where needed | Small language model |
| generate_answer | Generate conditions, findings, and interpretation with citations | Main language model |
| retrieve_compare | Retrieve evidence for each selected investigation | Milvus |
| generate_comparison | Compare experimental conditions before conclusions | Main language model |
| validate_citations | Check cited IDs against retrieved passages and suppress unsupported answers | None |
| fallback_insufficient | Return an insufficient-evidence response | None |
| fallback_invalid | Return an invalid-question response | None |

The comparison endpoint sets the comparison intent and selected IDs directly, so it skips query classification. Search requests pass through evidence grading before answer generation.

This is one graph with multiple workflow nodes. Model names are configurable through the environment. Retrieval and generation remain separate. Citation validation checks that IDs resolve to retrieved passages; it does not prove that every scientific claim follows from its cited passage.
