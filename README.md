<p align="center">
  <img src="docs/brand/paysage-logo.webp" alt="PaySage: every invoice teaches the next one" width="320" />
</p>

# PaySage

**Every invoice teaches the next one.** An accounts-payable agent that learns from human decisions. A reviewer resolves an invoice
exception once; [Hindsight](https://hindsight.vectorize.io) remembers the decision and the reason;
the next matching invoice from the **same vendor** gets a better, explained recommendation, and other
vendors get nothing from it.

> **New here?** [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) explains everything: the problem, what PaySage
> does, the tech and API keys, why this design, the alternatives, and which code files matter most.

```
invoice ─▶ rules ─▶ recall ─▶ reflect ─▶ LLM ─▶ evidence guardrail ─▶ recommendation + why
                  (Hindsight, (only if   (Groq)  (deterministic)              │
                   vendor-     memory                                human decides
                   filtered)   exists)                                     │
                                                          retain (Hindsight) ◀┘  only human decisions
```

- **Rules** compare the invoice with the PO record (by `po_id`, else the vendor's latest PO). The
  `po_price` an invoice quotes is never trusted. Price: CRITICAL above 10%, WARNING above 5%, else
  INFO. Quantity: CRITICAL above 10%, else WARNING.
- **Recall** asks Hindsight a natural-language question. Hindsight returns extracted facts, so each
  retained decision carries an `[AP-RECORD …]` line that recall reads back from the original chunk.
  Anything for another vendor, or without a readable record, is dropped: vendor isolation is enforced
  in code, not left to semantic search.
- **Reflect** runs only when the vendor has memories, and only about that vendor.
- **The guardrail** decides what the LLM may say: APPROVED needs a human-approved precedent for the
  same vendor, exception type and invoiced amount (`VERIFIED_MATCH`). Everything else is
  NEEDS_REVIEW (or REJECTED on a verified rejection). If Groq is down, memory still works.
- **Failures never crash and never lie**: `memory_status: "unavailable"` means memory is offline,
  which is different from "no memory found"; a failed retain returns `retained: false`.

## Meet the mascot

<p align="center">
  <img src="docs/brand/paysage-mascot.webp" alt="The PaySage mascot in its states" width="560" />
</p>

The mascot shows what the agent is doing and how sure it is, so the learning loop reads as a story:
confident, curious, puzzled, investigating, alarmed, asking you, learning, confident again. Each
situation in the app picks one state (`frontend/src/utils/mascot.ts`):

| Situation | Pose | The mascot says |
|---|---|---|
| Running the agent | laptop, then thinking, then memory orb | “Let’s see what this invoice is hiding…” → “Checking the price and quantity against the purchase order…” → “Wait… let me check what happened last time.” |
| Exception found | alarmed | “Whoa! This invoice doesn’t match the purchase order.” |
| No verified history | alarmed | “I don’t know this pattern yet. Better check with you.” |
| Memory exists, but the amount differs | puzzled | “Hmm… this looks different from what I remember.” |
| Verified precedent | thumbs up | “I’ve seen this before. Based on verified history, I recommend approval.” |
| Conflicting history | puzzled | “My past decisions disagree on this one. I need your judgment.” |
| Memory offline | puzzled | “I can’t reach my memory right now, so I haven’t checked any history. Let’s review this together.” |
| You overrule the agent | thinking | “Got it. I’ll remember why you made that decision.” |
| Decision retained | memory orb | “Memory saved. I’ll remember this for next time.” |
| Over time | memory orb | “Every decision makes me a little wiser.” |

The lines only claim what the system does: it checks price and quantity against the PO, recalls
human decisions from Hindsight, and stores decisions, not rules.

## Project layout

```
backend/     Python: the API, the agent, Hindsight memory, storage, tools and tests
  api.py       the HTTP API the web app calls
  cli.py       the same pipeline in the terminal
  app/         agent/ (pipeline, rules, guardrail, LLM) · memory/ (Hindsight) · storage/ · utils/
  scripts/     setup checks, memory banks, local Hindsight, MySQL, dataset builders
  tests/       offline tests, live rehearsal, MySQL integration
frontend/    React + TypeScript web app
data/        the datasets: demo, real, synthetic
docs/        the project guide, the demo script, the logo and mascot
```

The full map, with what every file does, is in [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md#8-the-code-map).

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt              # add -r backend/requirements-dev.txt to run the tests
cp .env.example .env                                 # then fill in your keys (.env stays at the repo root)
```

`.env`:

| Variable | |
|---|---|
| `GROQ_API_KEY` | Groq key: [console.groq.com/keys](https://console.groq.com/keys) |
| `GROQ_MODEL` | Default `openai/gpt-oss-120b` |
| `HINDSIGHT_API_KEY`, `HINDSIGHT_BANK_ID` | Hindsight Cloud key ([ui.hindsight.vectorize.io](https://ui.hindsight.vectorize.io); none for a local server) and memory bank |
| `HINDSIGHT_API_URL` | Default `https://api.hindsight.vectorize.io`; `http://127.0.0.1:8888` for a local server |
| `DATASET` | `demo` (default), `real` or `synthetic`: see [Data](#data) |
| `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` | Optional. Keep the data and the decision log in MySQL: see [MySQL](#mysql-optional) |
| `DATA_DIR`, `INVOICES_FILE` | Optional. Any folder with `vendors.json`, `purchase_orders.json` and a queue; overrides `DATASET` |
| `DECISION_LOG_PATH` | Optional, without MySQL. Keeps the dashboard's decision log in a file across restarts |

The commands below run from `backend/` (`cd backend`). For a clean demo, make a fresh Hindsight bank
and put its id in `HINDSIGHT_BANK_ID`:

```bash
python -m scripts.fresh_bank --prefix hap-demo
```

Then check everything with real calls that cost nothing (it never prints a key):

```bash
python -m scripts.check_setup
```

### Hindsight on your own machine (no Hindsight key needed)

Hindsight is open source. Without a Hindsight Cloud key, run the server locally; it uses your Groq key
for its own LLM calls:

```bash
uv tool install hindsight-api          # once (or: pipx install hindsight-api)
python -m scripts.local_hindsight      # in a terminal of its own: http://127.0.0.1:8888
```

Then in `.env`: `HINDSIGHT_API_URL=http://127.0.0.1:8888` and an empty `HINDSIGHT_API_KEY`. Memories
persist between runs in the server's embedded PostgreSQL. The launcher sizes the server for Groq's free
tier (a few thousand tokens per minute per model): the `on_demand` service tier (the default, `auto`,
needs a paid plan), low reasoning effort for fact extraction, a separate model for reflect, and a
2-step reflect. PaySage creates its banks without observations, which it never reads.

## Run

```bash
cd backend
uvicorn api:app --reload            # API; docs at http://127.0.0.1:8000/docs
python cli.py --fresh               # the same pipeline in the terminal, on a fresh bank
```

The web app (React + Vite) lives in [frontend/](frontend/README.md). With the API running:

```bash
cd frontend
npm install
npm run dev                         # http://localhost:3000
```

| Endpoint | |
|---|---|
| `POST /api/v1/invoice/process` | `{invoice_id, vendor, po_price, invoice_price, quantity, invoice_date}` → recommendation, memories, reflection, evidence, explanation |
| `POST /api/v1/invoice/store-decision` | `{invoice_id, human_decision, human_reason}` → `{success, retained, memory_id}` |
| `GET /api/v1/invoice/next`, `GET /api/v1/invoices?limit=10&offset=0` | The invoice queue, a page at a time |
| `GET /api/v1/queue/summary` | `{total, pending, processed, decided, first_open}` for the whole queue |
| `GET /api/v1/dashboard`, `/dashboard/stats` | Totals, approval rate, recent memories (local log only) |
| `GET /api/v1/vendors`, `/vendor/{name}`, `/vendor/{name}/timeline` | Vendor pages (local log only) |
| `GET /health` | `{groq, hindsight, bank_id, data_source, dataset, database}`: configured / reachable, never keys or passwords |

Errors are always `{"error": {"code", "message"}}`. Rates and confidence are fractions from 0 to 1.
The dashboard and vendor routes never call Groq or Hindsight, so polling them costs nothing.

## Data

Three datasets, picked with `DATASET` in `.env`:

| `DATASET` | What | Invoices | Built by (from `backend/`) |
|---|---|---|---|
| `demo` | The demo story: ABC ₹550, ABC ₹550, XYZ ₹550, ABC ₹600. Illustrative | 4 | hand-written |
| `real` | Every purchase line sold directly by an Indian manufacturer (Aurobindo, Hetero, Cipla, Mylan, ...) in USAID's SCMS dataset, 2006-2015 | 1,623 | `python -m scripts.download_real_data` |
| `synthetic` | 12 invented Indian vendors, Jan-Sep 2026, with the exception patterns AP teams see: price revisions the PO master hasn't caught up with, recurring overbilling, carton-rounded short shipments, rounding differences, extra trips | 482 | `python -m scripts.generate_synthetic_data` |

- **real**: prices are real; each PO price is the vendor's most common price for that item that year
  (per year, because prices drift over nine years). 22% of lines differ from it.
- **synthetic**: deterministic (`--seed`). 28% of invoices have an exception, and 30 exception
  patterns (same vendor, type and amount) occur more than once: the learning loop at scale. Approve
  the first invoice of a price revision, and the next identical one is recalled as a verified match,
  the evidence the agent needs before it may recommend approval. `data/synthetic/labels.json` records
  the pattern behind each invoice and the decision a careful reviewer would make; the app never reads it.
- Sources and licenses: [data/SOURCES.md](data/SOURCES.md). Presenter script: [docs/demo_walk.md](docs/demo_walk.md).

### MySQL (optional)

Without MySQL the data comes from the JSON files and the decision log lives in memory. With it, the
vendors, POs, invoice queue and decision log are stored in MySQL: the dashboard survives restarts,
and the data can be browsed in MySQL Workbench. Hindsight is still the only memory the agent uses.

1. In `.env`, set `MYSQL_USER` and `MYSQL_PASSWORD` (and `MYSQL_PORT` if it isn't 3306).
2. Load the datasets (the `paysage` database and its tables are created if missing):

```bash
cd backend
python -m scripts.db import all      # demo, real and synthetic
python -m scripts.db status          # what is stored
```

3. Restart the API. The sidebar's System panel shows `Data: MySQL · <dataset>`.

The API also imports the selected dataset by itself on its first start. The decision log is kept per
dataset and Hindsight bank, so a fresh bank starts with a fresh dashboard; `python -m scripts.db
clear-log --yes` empties the current one. Tables: `datasets`, `vendors`, `purchase_orders`,
`invoices`, `decision_events`.

## Testing

All from `backend/`, after `pip install -r requirements-dev.txt`.

### Offline (default): free, deterministic, no network

```bash
pytest -q
pytest --cov=app --cov-report=term-missing
pytest tests/e2e -s        # prints the learning-loop transcript: it doubles as the demo script
```

Groq and Hindsight are replaced by fakes at the client boundary (`backend/tests/fakes.py`). The fakes
check every call against the installed clients' real signatures and return their real response models,
so they cannot drift. The Hindsight fake is deliberately leaky (recall returns every vendor's
memories); vendor isolation has to come from the app. Any network access fails the test.

### Live rehearsal: real Groq and Hindsight, spends credits

bash:

```bash
RUN_LIVE=1 pytest tests/live -m live -s
```

PowerShell:

```powershell
$env:RUN_LIVE = "1"; pytest tests/live -m live -s; Remove-Item Env:RUN_LIVE
```

Needs real `GROQ_API_KEY` and `HINDSIGHT_API_KEY` in `.env`. Each test creates its own bank,
`hap-test-<utc timestamp>`, and refuses to run if that equals `HINDSIGHT_BANK_ID`.

What the printed numbers mean:

| Number | Meaning | Healthy |
|---|---|---|
| `retain took Xs` | A synchronous retain, including Hindsight's fact extraction | a few seconds |
| `visible to recall after Xs` | From retain returning to recall first finding the decision | ~0s; the test fails above 15s |
| `process INVxxx Xs` | One `/process` call: rules, recall, reflect (if memory), Groq | warns above 8s, fails above 20s |
| `store-decision Xs` | Recording the human decision, including the retain | a few seconds |

The story runs three times on three fresh banks and must give the same recommendations every time
(NEEDS_REVIEW, APPROVED, NEEDS_REVIEW, NEEDS_REVIEW): LLM nondeterminism is the main thing
that can break a demo.

### MySQL: the storage code on a real server

The offline suite runs the storage code on SQLite. To run it on MySQL as well (a local server; each run
creates and drops its own `paysage_test_*` database):

```bash
TEST_MYSQL_URL=mysql+pymysql://root:password@127.0.0.1:3306 pytest tests/integration -m mysql
```
