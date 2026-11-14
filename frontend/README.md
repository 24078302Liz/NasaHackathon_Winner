# Frontend setup

The site is static HTML, CSS, and JavaScript. `app.js` uses the FastAPI routes
documented in the repository root `API_CONTRACT.md`.

## Local development

Run the API on `http://127.0.0.1:8000`, then serve this directory from
`http://localhost:5173` (for example, `python3 -m http.server 5173`). On localhost,
the UI uses the local API automatically. Add that exact frontend origin to
`CORS_ALLOWED_ORIGINS` in the backend environment if the browser blocks requests.

## Vercel deployment

Before deploying the frontend, edit `config.js` and set
`window.FLAME_API_BASE_URL` to the public HTTPS origin of the deployed FastAPI
service, with no trailing slash. Add `https://winner-flame-in-freefall.vercel.app`
to the API's `CORS_ALLOWED_ORIGINS`. Never add the LLM API key to frontend files.

The Vercel page cannot reach a FastAPI process running only on a developer laptop.
Deploy the backend and populate its database/vector index before expecting live
search results. Without a configured API, the page retains curated reference browsing.
