"""PaySage HTTP API.

    uvicorn api:app --reload        docs at http://127.0.0.1:8000/docs

Success responses are raw JSON; every error is {"error": {"code", "message"}}. Groq and Hindsight
clients are built lazily through Depends (never at import), so tests swap them with
app.dependency_overrides. /dashboard and /vendors read only the local decision log: the UI polls
them, and they must not spend Groq or Hindsight credits.

Data comes from JSON files, or from MySQL when it is configured (app/storage/sources.py).
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import List, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from groq import AsyncGroq
from hindsight_client import Hindsight
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import storage
from app.agent.llm import LLMAgent
from app.agent.pipeline import InvoiceProcessor, NotProcessed, PurchaseOrderNotFound
from app.config import Settings, load_settings
from app.memory.hindsight import HindsightMemory, make_client
from app.models import (
    DashboardResponse,
    DashboardStats,
    HealthResponse,
    Invoice,
    ProcessResponse,
    QueuedInvoice,
    QueueSummary,
    StoreDecisionRequest,
    StoreDecisionResponse,
    TimelineEvent,
    VendorSummary,
    normalize_vendor,
)
from app.storage.database import DatabaseUnavailable
from app.storage.decision_log import DecisionLog
from app.storage.reference import ReferenceData
from app.utils.logs import configure_logging

log = logging.getLogger("paysage")
configure_logging()

CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]

_clients: list = []  # network clients the app created, closed on shutdown


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    while _clients:
        client = _clients.pop()
        try:
            await (client.aclose() if hasattr(client, "aclose") else client.close())
        except Exception as exc:  # shutting down: log and carry on
            log.warning("shutdown: could not close %s: %s", type(client).__name__, type(exc).__name__)
    _hindsight.cache_clear()
    _groq.cache_clear()
    storage.dispose_engines()


app = FastAPI(title="PaySage API", description="Accounts-payable agent that learns from human decisions. Every invoice teaches the next one.",
              lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Errors ───────────────────────────────────────────────────────────────────

class APIError(RuntimeError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@app.exception_handler(APIError)
async def _api_error(request: Request, exc: APIError) -> JSONResponse:
    return _error(exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in err['loc'] if part != 'body') or 'body'}: {err['msg']}" for err in exc.errors()
    )
    return _error(422, "validation_error", problems)


@app.exception_handler(StarletteHTTPException)
async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {404: "not_found", 405: "method_not_allowed"}
    return _error(exc.status_code, codes.get(exc.status_code, "http_error"), str(exc.detail))


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
    return _error(500, "internal_error", "Internal server error. It has been logged.")


# ── Dependencies ─────────────────────────────────────────────────────────────

@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache(maxsize=4)
def _reference(settings: Settings) -> ReferenceData:
    return storage.open_reference(settings)


def get_reference(settings: Settings = Depends(get_settings)) -> ReferenceData:
    try:
        return _reference(settings)
    except DatabaseUnavailable as exc:
        raise APIError(503, "database_unavailable", str(exc)) from exc


_decision_log: Optional[DecisionLog] = None
_decision_log_lock = threading.Lock()  # first requests arrive together; the log must be created once


def get_decision_log(settings: Settings = Depends(get_settings)) -> DecisionLog:
    global _decision_log
    with _decision_log_lock:
        if _decision_log is None:
            try:
                _decision_log = storage.open_decision_log(settings)
            except DatabaseUnavailable as exc:
                raise APIError(503, "database_unavailable", str(exc)) from exc
        return _decision_log


@lru_cache(maxsize=2)
def _hindsight(settings: Settings) -> Optional[Hindsight]:
    client = make_client(settings)
    if client is not None:
        _clients.append(client)
    return client


def get_hindsight_client(settings: Settings = Depends(get_settings)) -> Optional[Hindsight]:
    return _hindsight(settings)


@lru_cache(maxsize=2)
def _groq(api_key: str) -> AsyncGroq:
    client = AsyncGroq(api_key=api_key)
    _clients.append(client)
    return client


def get_groq_client(settings: Settings = Depends(get_settings)) -> Optional[AsyncGroq]:
    return _groq(settings.groq_api_key) if settings.groq_api_key else None


def get_processor(
    settings: Settings = Depends(get_settings),
    reference: ReferenceData = Depends(get_reference),
    decisions: DecisionLog = Depends(get_decision_log),
    hindsight=Depends(get_hindsight_client),
    groq_client=Depends(get_groq_client),
) -> InvoiceProcessor:
    memory = None
    if hindsight is not None and settings.hindsight_bank_id:
        memory = HindsightMemory(hindsight, settings.hindsight_bank_id, settings.hindsight_timeout)
    return InvoiceProcessor(reference, memory, LLMAgent(groq_client, settings.groq_model), decisions)


# ── Invoices ─────────────────────────────────────────────────────────────────

@app.post("/api/v1/invoice/process", response_model=ProcessResponse)
async def process_invoice(invoice: Invoice, processor: InvoiceProcessor = Depends(get_processor)) -> ProcessResponse:
    try:
        return await processor.process(invoice)
    except PurchaseOrderNotFound as exc:
        raise APIError(404, "po_not_found", str(exc)) from exc


@app.post("/api/v1/invoice/store-decision", response_model=StoreDecisionResponse)
async def store_decision(body: StoreDecisionRequest,
                         processor: InvoiceProcessor = Depends(get_processor)) -> StoreDecisionResponse:
    try:
        return await processor.store_decision(body)
    except NotProcessed as exc:
        raise APIError(404, "invoice_not_processed", str(exc)) from exc


@app.get("/api/v1/invoice/next", response_model=QueuedInvoice)
def next_invoice(reference: ReferenceData = Depends(get_reference),
                 decisions: DecisionLog = Depends(get_decision_log)) -> QueuedInvoice:
    for invoice in reference.invoices:
        if decisions.status(invoice.invoice_id) == "pending":
            return QueuedInvoice(**invoice.model_dump(), status="pending")
    raise APIError(404, "queue_empty", "Every invoice in the queue has been processed")


@app.get("/api/v1/invoices", response_model=List[QueuedInvoice])
def list_invoices(limit: int = Query(10, ge=1, le=500), offset: int = Query(0, ge=0),
                  reference: ReferenceData = Depends(get_reference),
                  decisions: DecisionLog = Depends(get_decision_log)) -> List[QueuedInvoice]:
    """The queue in order, a page at a time: `limit` invoices from position `offset`."""
    return [QueuedInvoice(**inv.model_dump(), status=decisions.status(inv.invoice_id))
            for inv in reference.invoices[offset:offset + limit]]


@app.get("/api/v1/queue/summary", response_model=QueueSummary)
def queue_summary(reference: ReferenceData = Depends(get_reference),
                  decisions: DecisionLog = Depends(get_decision_log)) -> QueueSummary:
    statuses = [decisions.status(inv.invoice_id) for inv in reference.invoices]
    first_open = next((n for n, status in enumerate(statuses) if status != "decided"), None)
    return QueueSummary(total=len(statuses), pending=statuses.count("pending"), processed=statuses.count("processed"),
                        decided=statuses.count("decided"), first_open=first_open)


# ── Dashboard and vendors (local decision log only: no Groq, no Hindsight) ──

@app.get("/api/v1/dashboard", response_model=DashboardResponse)
def dashboard(decisions: DecisionLog = Depends(get_decision_log)) -> DashboardResponse:
    return decisions.dashboard()


@app.get("/api/v1/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(decisions: DecisionLog = Depends(get_decision_log)) -> DashboardStats:
    return decisions.stats()


@app.get("/api/v1/vendors", response_model=List[VendorSummary])
def vendors(reference: ReferenceData = Depends(get_reference),
            decisions: DecisionLog = Depends(get_decision_log)) -> List[VendorSummary]:
    names = {key: v.name for key, v in reference.vendors.items()}
    for name in decisions.vendor_names():
        names.setdefault(normalize_vendor(name), name)
    return [decisions.vendor_summary(name, reference.vendor(name)) for name in sorted(names.values())]


def _known_vendor(name: str, reference: ReferenceData, decisions: DecisionLog) -> str:
    if not (reference.vendor(name) or decisions.knows_vendor(name)):
        raise APIError(404, "vendor_not_found", f"No vendor named '{name}'")
    return name


@app.get("/api/v1/vendor/{name}", response_model=VendorSummary)
def vendor(name: str, reference: ReferenceData = Depends(get_reference),
           decisions: DecisionLog = Depends(get_decision_log)) -> VendorSummary:
    return decisions.vendor_summary(_known_vendor(name, reference, decisions), reference.vendor(name))


@app.get("/api/v1/vendor/{name}/timeline", response_model=List[TimelineEvent])
def vendor_timeline(name: str, reference: ReferenceData = Depends(get_reference),
                    decisions: DecisionLog = Depends(get_decision_log)) -> List[TimelineEvent]:
    return decisions.timeline(_known_vendor(name, reference, decisions))


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings), hindsight=Depends(get_hindsight_client)) -> HealthResponse:
    """Reports what is configured and reachable. Never returns key values or passwords."""
    if hindsight is None or not settings.hindsight_bank_id:
        status = "missing"
    else:
        memory = HindsightMemory(hindsight, settings.hindsight_bank_id, settings.hindsight_timeout)
        status = "reachable" if await memory.reachable() else "unreachable"
    return HealthResponse(groq="configured" if settings.groq_api_key else "missing", hindsight=status,
                          bank_id=settings.hindsight_bank_id, groq_model=settings.groq_model,
                          data_source=settings.data_source, dataset=settings.dataset,
                          database=storage.database_status(settings))
