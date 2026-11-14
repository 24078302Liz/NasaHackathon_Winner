# Flame in Freefall API contract

The FastAPI service is the source of truth for the deployed UI. Use the interactive
OpenAPI page at `/docs` while the backend is running.

## Routes

### `GET /api/investigations`

Optional query parameters: `research_focus` and `material`.

Returns records with `investigation_id`, `title`, `objective`, `research_focus`,
`materials`, `source_url`, and optional `doi`. The material filter is a case-insensitive
substring match.

### `GET /api/investigations/{investigation_id}`

Returns the summary plus `documents`, `tests`, and `findings`. Documents retain their
source URL, local filename, retrieval date, and license reference. Test records retain
each condition's units. Findings retain test IDs, supporting evidence IDs, and
limitations.

### `POST /api/search`

Request:

```json
{"question":"Which studies examine solid materials under different oxygen conditions?"}
```

Response includes the original `question`, `answer`, validated `citations`, all retrieved
`evidence` passages, up to three ranked `investigations`, and `evidence_status`. Each
ranked item includes its rank, hit count, best retrieval score, matched evidence IDs,
and a plain-language ranking explanation. Treat scores as retrieval relevance, never as
confidence or fire risk.

### `POST /api/compare`

Request:

```json
{"id_a":"BASS-II","id_b":"Saffire-I","focus":"Compare fuels and airflow"}
```

Response includes a cited `answer`, `citations`, `evidence_status`, and two structured
`comparison` records. Each record has investigation identity, source URL, and fields for
objective, research focus, fuels, geometry, oxygen, pressure, airflow, gravity,
measurements, findings, and limitations. A field also reports availability as
`reported`, `not_reported`, or `not_yet_extracted`; the UI should display the supplied
value verbatim and must not infer missing measurements.

## UI request states

- Keep the entered question or selected investigation IDs when a request fails.
- Show a loading state during search and comparison requests.
- HTTP 422 means invalid input; show the response detail beside the relevant control.
- HTTP 404 means a selected investigation is not in the loaded corpus.
- HTTP 502 or 504 means the service failed or timed out; preserve inputs and offer Retry.
- `evidence_status: "insufficient"` is a valid result, not a transport error. Show the
  answer and any retrieved evidence while making the evidence gap clear.

## Deployment configuration

The browser app must call the public FastAPI origin over HTTPS and include that exact
origin in the backend CORS allowlist before production use. Do not put the LLM key in
browser code. Keep the API base URL configurable per deployment.
