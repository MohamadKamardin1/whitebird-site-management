# White Bird Frontend

This directory contains the React/Vite White Bird Zanzibar operations workspace. It is developed separately from Django for fast iteration and is packaged into the Django image as static content for production delivery.

| Command | Purpose |
|---|---|
| `pnpm install` | Install frontend dependencies. |
| `pnpm dev` | Run Vite at `http://127.0.0.1:5173`; `/api/*` proxies to `http://127.0.0.1:8000` by default. |
| `pnpm check` | Run TypeScript validation. |
| `pnpm build` | Build the production bundle into `frontend/dist`. |

The client deliberately uses a relative `API_BASE_URL` (`/api/site-management/v1`) so the Vite proxy works in development and Django serves API and SPA from the same public origin in production. The Django image builds this frontend and collects it beneath `/static/frontend/`; the backend serves the SPA entry at `/app/`.

> The React permission layer improves clarity but never replaces the Django API’s authorization checks.
