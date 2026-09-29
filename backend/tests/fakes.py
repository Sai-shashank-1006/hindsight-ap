"""Fakes for the two network clients. Everything else in the app runs for real in tests.

Both fakes check each call against the INSTALLED client's real signature (inspect.signature(...).bind),
so an argument the real client doesn't accept fails the test instead of passing silently, and both
return the real response models so the response shape can't drift either.
"""

from __future__ import annotations

import datetime as dt
import inspect
import json
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional, Union

import groq
import httpx
from groq.resources.chat.completions import AsyncCompletions
from groq.types.chat import ChatCompletion
from hindsight_client import (
    BankProfileResponse,
    Hindsight,
    RecallResponse,
    RecallResult,
    ReflectResponse,
    RetainResponse,
    VersionResponse,
)
from hindsight_client_api.exceptions import ApiException, NotFoundException, ServiceException, UnauthorizedException
from hindsight_client_api.models import ChunkData, DispositionTraits, FeaturesInfo

HINDSIGHT_METHODS = ("retain", "recall", "reflect", "create_bank", "get_version")
REAL_HINDSIGHT = {prefix + name: inspect.signature(getattr(Hindsight, prefix + name))
                  for name in HINDSIGHT_METHODS for prefix in ("", "a")}
REAL_GROQ_CREATE = inspect.signature(AsyncCompletions.create)


def llm_json(recommendation: str = "NEEDS_REVIEW", confidence: float = 0.5, explanation: str = "Fake model says so.") -> str:
    return json.dumps({"recommendation": recommendation, "confidence": confidence, "explanation": explanation})


# ── Hindsight ────────────────────────────────────────────────────────────────

class FakeHindsight:
    """In-memory hindsight_client.Hindsight with the same method names and parameters, sync and async.

    DELIBERATELY LEAKY: recall returns every memory in the bank for any query, the way semantic
    search can pull in a similar vendor. Vendor isolation has to come from the app.
    Recall returns extracted-fact text (not the retained content) plus, with include_chunks=True,
    the original text as chunks, like the real service.
    """

    def __init__(self, return_metadata: bool = False):
        self.banks: Dict[str, Dict[str, dict]] = {}  # bank_id -> document_id -> document
        self.calls: List[tuple] = []  # (method, kwargs actually passed)
        self.created_banks: List[dict] = []
        self.reflect_text = "Reflection: the current exception matches a decision previously verified for this vendor."
        self.return_metadata = return_metadata
        self._failures: List[tuple] = []  # (kind, method or None)

    # ── test controls ──
    def fail_next(self, kind: Union[str, int], method: Optional[str] = None) -> None:
        """Make the next call (to `method`, or to anything) fail: 'timeout', 401, 402, 404 or 500."""
        self._failures.append((kind, method))

    def calls_to(self, method: str) -> List[dict]:
        return [kwargs for name, kwargs in self.calls if name == method]

    def documents(self, bank_id: str) -> Dict[str, dict]:
        return self.banks.get(bank_id, {})

    # ── plumbing ──
    def _enter(self, name: str, args: tuple, kwargs: dict) -> dict:
        bound = REAL_HINDSIGHT[name].bind(self, *args, **kwargs)  # TypeError if the real client lacks a kwarg
        passed = {k: v for k, v in bound.arguments.items() if k != "self"}
        method = name[1:] if name.startswith("a") and name[1:] in HINDSIGHT_METHODS else name
        self.calls.append((method, passed))
        for i, (kind, target) in enumerate(self._failures):
            if target in (None, method):
                del self._failures[i]
                self._raise(kind)
        return passed

    @staticmethod
    def _raise(kind: Union[str, int]) -> None:
        if kind == "timeout":
            raise TimeoutError("fake Hindsight timed out")
        status = int(kind)
        cls = {401: UnauthorizedException, 404: NotFoundException, 500: ServiceException}.get(status, ApiException)
        raise cls(status=status, reason=f"fake HTTP {status}")

    def _retain(self, kw: dict) -> RetainResponse:
        bank = self.banks.setdefault(kw["bank_id"], {})
        doc_id = kw.get("document_id") or f"doc-{sum(len(b) for b in self.banks.values()) + 1}"
        timestamp = kw.get("timestamp") or dt.datetime.now(dt.timezone.utc)
        bank[doc_id] = {"content": kw["content"], "context": kw.get("context"), "metadata": kw.get("metadata"),
                        "mentioned_at": timestamp.isoformat()}  # same document_id replaces, never duplicates
        return RetainResponse(success=True, bank_id=kw["bank_id"], items_count=1, var_async=kw.get("retain_async", False))

    def _recall(self, kw: dict) -> RecallResponse:
        results, chunks = [], {}
        for doc_id, doc in self.banks.get(kw["bank_id"], {}).items():
            chunk_id = f"{doc_id}::0"
            prose = doc["content"].splitlines()[0]
            for n, fact in enumerate([f"Extracted fact: {prose}", f"Extracted fact: a reviewer decision is on file ({doc_id})."]):
                results.append(RecallResult(
                    id=f"{doc_id}-fact-{n}", text=fact, type="world", chunk_id=chunk_id, document_id=doc_id,
                    mentioned_at=doc["mentioned_at"], metadata=doc["metadata"] if self.return_metadata else None,
                ))
            chunks[chunk_id] = ChunkData(id=chunk_id, text=doc["content"], chunk_index=0)
        return RecallResponse(results=results, chunks=chunks if kw.get("include_chunks") else None)

    def _reflect(self, kw: dict) -> ReflectResponse:
        return ReflectResponse(text=self.reflect_text)

    def _create_bank(self, kw: dict) -> BankProfileResponse:
        self.created_banks.append(kw)
        self.banks.setdefault(kw["bank_id"], {})
        traits = DispositionTraits(skepticism=kw.get("disposition_skepticism") or 3,
                                   literalism=kw.get("disposition_literalism") or 3,
                                   empathy=kw.get("disposition_empathy") or 3)
        return BankProfileResponse(bank_id=kw["bank_id"], name=kw.get("name") or kw["bank_id"],
                                   disposition=traits, mission=kw.get("mission") or "")

    def _get_version(self, kw: dict) -> VersionResponse:
        return VersionResponse(api_version="fake", features=FeaturesInfo(**{f: False for f in FeaturesInfo.model_fields}))

    # ── the client's surface ──
    def retain(self, *a, **k): return self._retain(self._enter("retain", a, k))
    def recall(self, *a, **k): return self._recall(self._enter("recall", a, k))
    def reflect(self, *a, **k): return self._reflect(self._enter("reflect", a, k))
    def create_bank(self, *a, **k): return self._create_bank(self._enter("create_bank", a, k))
    def get_version(self, *a, **k): return self._get_version(self._enter("get_version", a, k))

    async def aretain(self, *a, **k): return self._retain(self._enter("aretain", a, k))
    async def arecall(self, *a, **k): return self._recall(self._enter("arecall", a, k))
    async def areflect(self, *a, **k): return self._reflect(self._enter("areflect", a, k))
    async def acreate_bank(self, *a, **k): return self._create_bank(self._enter("acreate_bank", a, k))
    async def aget_version(self, *a, **k): return self._get_version(self._enter("aget_version", a, k))

    async def aclose(self) -> None:
        pass


# ── Groq ─────────────────────────────────────────────────────────────────────

_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
Reply = Union[str, List[str], Callable[[list], str]]


class FakeGroq:
    """Stands in for groq.AsyncGroq: await .chat.completions.create(...) returns a real ChatCompletion.
    reply is a fixed string, a queue of strings, or fn(messages) -> str."""

    def __init__(self, reply: Reply = None):
        self.reply = llm_json() if reply is None else reply
        self.calls: List[dict] = []
        self.fail_always: Optional[Union[int, str, BaseException]] = None
        self._failures: List[Union[int, str, BaseException]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def fail_next(self, kind: Union[int, str, BaseException]) -> None:
        """429, 'timeout', or any exception instance."""
        self._failures.append(kind)

    @property
    def prompt(self) -> str:
        """Every message of the last call, joined."""
        return "\n".join(m["content"] for m in self.calls[-1]["messages"]) if self.calls else ""

    async def _create(self, **kwargs) -> ChatCompletion:
        REAL_GROQ_CREATE.bind(None, **kwargs)  # TypeError if the real SDK lacks a kwarg
        self.calls.append(kwargs)
        failure = self.fail_always if self.fail_always is not None else (self._failures.pop(0) if self._failures else None)
        if failure == 429:
            raise groq.RateLimitError("Rate limit reached", response=httpx.Response(429, request=_REQUEST), body=None)
        if failure == "timeout":
            raise groq.APITimeoutError(request=_REQUEST)
        if isinstance(failure, BaseException):
            raise failure
        if callable(self.reply):
            content = self.reply(kwargs["messages"])
        elif isinstance(self.reply, list):
            content = self.reply.pop(0)
        else:
            content = self.reply
        return ChatCompletion.model_validate({
            "id": f"fake-{len(self.calls)}", "object": "chat.completion", "created": 0, "model": kwargs["model"],
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        })
