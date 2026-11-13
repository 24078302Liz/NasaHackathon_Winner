# Flame in Freefall — Backend

AI 驱动的 NASA 微重力燃烧研究检索后端：**LangGraph 智能体工作流 + Milvus 混合检索 RAG**。

设计文档见仓库根目录的 `backend-design.md`。

## 目录结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 环境变量配置
│   ├── api/                    # 路由 + Pydantic 模型
│   ├── agents/                 # LangGraph 工作流（状态/节点/图/提示词）
│   ├── retrieval/              # Milvus 混合检索 + SQLite 结构化存储
│   ├── ingestion/              # 语料接入（解析/分块/入库）
│   └── services/               # LLM 客户端
├── scripts/ingest.py           # 一键接入语料
├── docker-compose.milvus.yml   # Milvus standalone
├── requirements.txt
└── .env.example
```

## 快速启动

> 要求 **Python 3.10+**（代码使用 `X | None` 联合类型注解，Python 3.9 不支持）。推荐用 conda/miniconda 的 Python 3.11+ 创建虚拟环境。

```bash
cd backend

# 1) 启动 Milvus（Docker standalone）
docker compose -f docker-compose.milvus.yml up -d

# 2) 安装依赖
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3) 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY（DeepSeek）

# 4) 接入语料
python scripts/ingest.py --source ../PRD_and_project_introduction/

# 5) 启动服务
uvicorn app.main:app --reload --port 8000
```

健康检查：`GET /health`；API 文档：`http://localhost:8000/docs`。

## 技术栈

| 层 | 选型 |
|---|---|
| Web | FastAPI |
| 编排 | LangGraph |
| 向量库 | Milvus standalone（hybrid search + 内置 BM25） |
| 生成模型 | DeepSeek（OpenAI 兼容接口） |
| 稠密向量 | HuggingFace BGE（`BAAI/bge-m3`，1024 维） |
| 稀疏向量 | Milvus 内置 BM25 function |
| 结构化存储 | SQLite（SQLAlchemy 抽象，可切 MySQL） |

## API

| 路由 | 说明 |
|---|---|
| `GET /api/investigations` | 调查列表（可选 `research_focus` 过滤） |
| `GET /api/investigations/{id}` | 调查详情（文档/测试/发现） |
| `POST /api/search` | 问答：`{"question": "..."}` |
| `POST /api/compare` | 对比：`{"id_a": "...", "id_b": "...", "focus": "..."}` |

## 数据接入待办

- BASS PDF 同时含 BASS / BASS-II / BASS-M 三个调查，需按文档 section 拆分归到各自 `investigation_id`。
- 结构化实验数值（氧浓度/气流/压力）目前未自动抽取，需从表格抽取为 `ExperimentalCondition`，并做人工抽样校验（PRD 8）。
- `SEED_INVESTIGATIONS` 里的 `source_url` 需按 NASA 官方资源核对。
