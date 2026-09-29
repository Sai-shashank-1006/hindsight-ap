# Demo walkthrough

Five minutes. The point to land: **the agent gets better because it remembers what a human decided,
and why, for that vendor only.** Hindsight is that memory.

## Before you present

Commands run from `backend/` unless they say otherwise.

1. `.env` (at the repo root) has real `GROQ_API_KEY` and `HINDSIGHT_API_KEY`: `python -m scripts.check_setup` shows ✓ for both.
2. Optional rehearsal: `RUN_LIVE=1 pytest tests/live -m live -s` passes (PowerShell:
   `$env:RUN_LIVE="1"; pytest tests/live -m live -s`). This runs the story below three times against the real services.
3. Make a fresh bank and put it in `.env` as `HINDSIGHT_BANK_ID`:
   `python -m scripts.fresh_bank --prefix hap-demo`
4. Start the API (`uvicorn api:app`) and, from `frontend/`, the web app (`npm run dev`); or use the terminal:
   `python cli.py`.
5. The sidebar's System panel shows every row green (the same as `GET /health`: `groq: configured`,
   `hindsight: reachable`).

## The story (data/demo_scenario.json)

| Step | Invoice | Expect | Say |
|---|---|---|---|
| 1 | INV001 · ABC Pharma, ₹550 vs PO ₹500 | PRICE_MISMATCH, **NEEDS REVIEW**, "No relevant verified historical memory found" | "The agent has never seen this. It doesn't guess." |
| 2 | Approve INV001, reason `Contract price changed from ₹500 to ₹550 effective 2026-07-01` | `retained: true` | "That decision, and its reason, is now memory. Only human decisions are stored." |
| 3 | INV002 · ABC Pharma, ₹550 again | Memory shows the INV001 approval; reflection; **APPROVED**; the explanation cites the date and reason | "Nobody wrote a rule. It remembered a decision." |
| 4 | INV003 · XYZ Pharma, ₹550 | No memories, **NEEDS REVIEW** | "ABC's contract says nothing about XYZ. Memory is per vendor." |
| 5 | INV004 · ABC Pharma, ₹600 | ABC's ₹550 approval shown as context, evidence NO_EVIDENCE, **NEEDS REVIEW** | "₹550 was approved, not ₹600. The price drifted, so a human looks." |

Every recommendation shows `evidence_level`: the deterministic check that decides whether the model
is allowed to approve. The model can never approve without a verified human precedent.

## If something goes wrong

| You see | Meaning | Do |
|---|---|---|
| `memory_status: "unavailable"`, "Memory is offline" | Hindsight unreachable, bad key, no credits, or wrong bank | `GET /health`; the server log says which ("invalid Hindsight API key", "Hindsight credits exhausted", "bank … not found") |
| "The LLM was unavailable" | Groq down or rate-limited | Keep going: memory-based recommendations still work |
| Step 1 already shows memories | The bank has decisions from a rehearsal | Make a fresh bank (step 3 above) |
| `retained: false` | The retain failed; the message says why | Fix and resubmit the decision: it replaces, never duplicates |
