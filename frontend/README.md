# Frontend setup

The site is static HTML, CSS, and JavaScript. `app.js` uses the FastAPI routes
documented in the repository root `API_CONTRACT.md`.

## Local development

Run the API on `http://127.0.0.1:8000`, then serve this directory from
`http://localhost:5173` (for example, `python3 -m http.server 5173`). On localhost,
the UI uses the local API automatically. Add that exact frontend origin to
`CORS_ORIGINS` in the backend environment if the browser blocks requests.

## Optional live access from Vercel

To connect the Vercel frontend to a remote backend, edit `config.js` and set
`window.FLAME_API_BASE_URL` to the public HTTPS origin of the deployed FastAPI
service, with no trailing slash. Add `https://winner-flame-in-freefall.vercel.app`
to the API's `CORS_ORIGINS`. Never add the LLM API key to frontend files.

The Vercel page cannot reach a FastAPI process running only on a developer laptop.
Public backend hosting is optional for a recorded local demonstration. Live
remote search requires a reachable backend with a populated database/vector index.
Run the full application locally to record it. The investigation library and
search require the API; if the
API URL is missing or the service is unavailable, the page shows an error and a
Retry action instead of substituting local mock records.
