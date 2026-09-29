# PaySage · frontend

React 18 + Vite + TypeScript (strict) + Tailwind CSS 3 + Recharts + React Router 6. It is the UI for
the FastAPI backend in [../backend](../backend): invoices are checked against their POs, Hindsight recalls
past human decisions for the same vendor, and every recommendation waits for a human.

## Run it

Needs Node 20.19+ and the backend running on port 8000 (`cd ../backend && uvicorn api:app`).

```bash
npm install
npm run dev          # http://localhost:3000
```

| Script | |
|---|---|
| `npm run dev` | Dev server on port 3000 with hot reload |
| `npm run build` | Type-check (`tsc`), then a production build in `dist/` |
| `npm run preview` | Serve `dist/` on port 3000 |
| `npm run lint` | ESLint |
| `npm run type-check` | TypeScript only |

## Configuration

`.env.local` (copy `.env.example`):

| Variable | |
|---|---|
| `VITE_API_URL` | Backend origin, default `http://localhost:8000`. Set it empty to call the same origin: the dev server proxies `/api`, `/health` and `/docs` to port 8000 |
| `VITE_APP_NAME` | Name in the navbar |

The backend allows browser calls from `localhost:3000` and `localhost:5173`. For any other origin
(a Vercel URL, say), add it on the backend: `CORS_ORIGINS=https://your-app.vercel.app`.

## Pages

| Route | What it shows | API calls |
|---|---|---|
| `/` Dashboard | Totals, approval rate, exceptions by type, the learning-loop funnel, recent memories | `GET /api/v1/dashboard` and `/dashboard/stats` every 10 s. Served from the backend's local log: no Groq or Hindsight credits |
| `/review` Invoice review | The queue, 50 invoices a page (it opens on the page with the first invoice still needing a decision); run the agent on an invoice; see the exceptions, the recommendation with its evidence level, the recalled memories and Hindsight's reflection; record your decision | `GET /api/v1/queue/summary`, `GET /api/v1/invoices?limit&offset`, `POST /api/v1/invoice/process`, `POST /api/v1/invoice/store-decision` |
| `/review?mode=manual` | Enter an invoice by hand or upload a JSON file (one invoice or a list) | `POST /api/v1/invoice/process` |
| `/vendors`, `/vendors/:name` | What was learned per vendor: decisions, approval rate, status, price history, timeline | `GET /api/v1/vendors`, `/vendor/{name}`, `/vendor/{name}/timeline` (local log only) |

The navbar status pill and the sidebar's System panel come from `GET /health`, checked once a
minute because it pings Hindsight. The panel's Data row says where the invoices live: `Files · demo`,
or `MySQL · synthetic` when the backend stores them in MySQL.

What the screens are careful to say:

- **"Memory offline" is not "no memory found".** When the backend reports `memory_status: "unavailable"`,
  the review page says so instead of showing an empty memory list.
- **A decision that wasn't remembered is shown as such.** `store-decision` can return `retained: false`;
  the page then says the decision was recorded but not stored in Hindsight, and lets you resubmit.
- **Nothing is pre-selected.** The agent's suggestion is marked on its option, but the reviewer chooses.

## Structure

```
src/
  api/          axios client (errors normalised to {status, code, message}) and typed endpoints
  types/        the backend's response shapes (keep in sync with app/models.py)
  hooks/        useDashboard (+ useHealth), useInvoice (+ useInvoiceQueue), useVendorMemory (+ useVendors)
  components/   layout/, common/ (GradientButton, BentoCard, …), dashboard/, invoice/, vendor/
  pages/        Dashboard, InvoiceReview, VendorMemory, NotFound
  utils/        formatters (₹, dates for en-IN), validators (mirror the backend's rules), constants
  styles/       colour tokens, animations, global rules
```

## Deploy (Vercel)

Import the repository with `frontend/` as the root directory. Set `VITE_API_URL` to the deployed
backend's URL, and add the Vercel URL to the backend's `CORS_ORIGINS`. `vercel.json` rewrites every
path to `index.html`, so reloading `/review` or `/vendors/ABC%20Pharma` works.

## Notes

- **No shadcn/ui.** Its current CLI targets Tailwind 4, and this project is pinned to Tailwind 3; the
  small set of components here (buttons, cards, alerts, empty states) is written directly.
- **ESLint 10 flat config.** `npm run lint` runs `eslint src`; the `--ext` flag no longer exists.
