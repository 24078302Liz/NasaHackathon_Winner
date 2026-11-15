# Run the application at one address

Use Python 3.12 or newer. From the repository root, create your environment, install requirements.txt, and configure .env using .env.example. Keep credentials private. The existing ingestion workflow requires source documents, a populated SQLite database, a running Milvus instance, embedding model weights, and a valid model-provider key.

Start the existing Milvus stack:

```powershell
docker compose -f docker-compose.milvus.yml up -d
```

Run the ingestion commands in README.md for your actual source documents. Then start the application:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ for the frontend and http://127.0.0.1:8000/docs for API documentation. FastAPI now serves the frontend and API together. The same-origin configuration marker selects the correct API automatically. A separately hosted static frontend still requires window.FLAME_API_BASE_URL in frontend/config.js.

For a remote host, use its required bind address and port, persistent database storage, and an accessible Milvus service. Configure its HTTPS origin in frontend/config.js and include the frontend origin in the backend CORS_ORIGINS JSON array. These changes prepare hosting; they do not create a public deployment.

Before submitting, verify these flows:

- GET /health returns 200. This checks process liveness, not model or database readiness.
- GET /api/investigations returns your real ingested records.
- Search returns passages and source IDs, or an explicit insufficient-evidence response.
- An explicitly restricted search with no matches does not silently use another investigation.
- Compare two populated investigations. Check that values retain their source units and missing data remains marked.
- Stop a required dependency and retry search. Expect a readable error, retained input, and a Retry action.
- Open the public website from another device before describing it as a live deployment.

Run deterministic regression checks without paid model calls:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

These checks use controlled dependency responses. They do not verify your live model account, Milvus corpus, or public deployment.
