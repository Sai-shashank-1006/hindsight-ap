# Hindsight AP

An accounts-payable agent that learns from human decisions. A reviewer resolves an invoice
exception once; [Hindsight](https://hindsight.vectorize.io) remembers the decision and the reason;
the next matching invoice from the **same vendor** gets a better, explained recommendation, and other
vendors get nothing from it.

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

## Setup

```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt                      # add -r requirements-dev.txt to run the tests
cp .env.example .env                                 # then fill in your keys
```

`.env`:

| Variable | |
|---|---|
| `GROQ_API_KEY` | Groq key |
| `GROQ_MODEL` | Default `openai/gpt-oss-120b` (`qwen/qwen3-32b` also works) |
| `HINDSIGHT_API_KEY`, `HINDSIGHT_BANK_ID` | Hindsight Cloud key and memory bank |
| `HINDSIGHT_API_URL` | Default `https://api.hindsight.vectorize.io` |
| `DATA_DIR` | Default `data/`. `data/real` for the real dataset |
| `INVOICES_FILE` | The queue. Default: `demo_scenario.json`, else `invoices.json`, in `DATA_DIR` |
| `DECISION_LOG_PATH` | Optional. Keeps the dashboard's decision log across restarts |

For a clean demo, make a fresh bank and put its id in `HINDSIGHT_BANK_ID`:

```bash
python -m scripts.fresh_bank --prefix hap-demo
```

## Run

```bash
uvicorn api:app --reload            # API; docs at http://127.0.0.1:8000/docs
python main.py --fresh              # the same pipeline in the terminal, on a fresh bank
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
| `GET /api/v1/invoice/next`, `GET /api/v1/invoices?limit=10` | The invoice queue |
| `GET /api/v1/dashboard`, `/dashboard/stats` | Totals, approval rate, recent memories (local log only) |
| `GET /api/v1/vendors`, `/vendor/{name}`, `/vendor/{name}/timeline` | Vendor pages (local log only) |
| `GET /health` | `{groq, hindsight, bank_id}`: configured / reachable, never key values |

Errors are always `{"error": {"code", "message"}}`. Rates and confidence are fractions from 0 to 1.
The dashboard and vendor routes never call Groq or Hindsight, so polling them costs nothing.

## Data

- `data/demo_scenario.json`: the demo story (ABC ₹550, ABC ₹550, XYZ ₹550, ABC ₹600). Illustrative.
- `data/real/`: 150 real purchase lines from Indian pharmaceutical manufacturers, built by
  `python download_real_data.py` from USAID's SCMS dataset. Use it with `DATA_DIR=data/real`.
  Real data won't contain the demo story; the demo never depends on it.
- Sources and licenses: [data/SOURCES.md](data/SOURCES.md). Presenter script: [data/demo_walk.md](data/demo_walk.md).

## Testing

### Offline (default): free, deterministic, no network

```bash
pytest -q
pytest --cov=app --cov-report=term-missing
pytest tests/e2e -s        # prints the learning-loop transcript: it doubles as the demo script
```

Groq and Hindsight are replaced by fakes at the client boundary (`tests/fakes.py`). The fakes check
every call against the installed clients' real signatures and return their real response models,
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
