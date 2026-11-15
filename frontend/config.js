// Set this to the public HTTPS URL of the deployed FastAPI service.
// Leave empty during local development; the UI uses http://127.0.0.1:8000 on localhost.
window.FLAME_API_BASE_URL = '';

// FastAPI serves this marker only when it also serves the frontend.
if (window.FLAME_SAME_ORIGIN) window.FLAME_API_BASE_URL = location.origin;
