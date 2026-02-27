from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .ollama_client import OllamaClient


def _fallback_embedding(text_value: str, dim: int = 96) -> list[float]:
    vec = [0.0] * dim
    terms = re.findall(r"[\u4e00-\u9fff]{1}|[a-zA-Z0-9_]+", (text_value or "").lower())
    if not terms:
        return vec
    for term in terms[:4096]:
        digest = hashlib.sha1(term.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dim
        sign = -1.0 if (digest[2] & 1) else 1.0
        vec[idx] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [round(v / norm, 8) for v in vec]
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dim = min(len(a), len(b))
    if dim <= 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(dim):
        av = float(a[i])
        bv = float(b[i])
        dot += av * bv
        na += av * av
        nb += bv * bv
    if na <= 1e-9 or nb <= 1e-9:
        return 0.0
    return float(dot / (math.sqrt(na) * math.sqrt(nb)))


def _lexical_score(query: str, candidate: str) -> float:
    q_terms = set(re.findall(r"[\u4e00-\u9fff]{1,2}|[a-zA-Z0-9_]+", (query or "").lower()))
    c_terms = set(re.findall(r"[\u4e00-\u9fff]{1,2}|[a-zA-Z0-9_]+", (candidate or "").lower()))
    if not q_terms or not c_terms:
        return 0.0
    inter = len(q_terms & c_terms)
    union = len(q_terms | c_terms) or 1
    return float(inter / union)


class LLMProvider(Protocol):
    name: str
    supports_chat_json: bool
    supports_embeddings: bool
    supports_rerank: bool

    async def chat_json(
        self,
        *,
        model: str,
        user: str,
        system: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
        timeout_s: int = 90,
        retries: int = 1,
        schema_hint: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        ...

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
        timeout_s: int = 90,
        retries: int = 1,
        meta: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        ...

    async def rerank(
        self,
        *,
        model: str,
        query: str,
        candidates: list[str],
        top_k: int = 20,
        timeout_s: int = 90,
        retries: int = 1,
        meta: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...


@dataclass
class RulesOnlyProvider:
    name: str = "rules"
    supports_chat_json: bool = False
    supports_embeddings: bool = True
    supports_rerank: bool = True

    async def chat_json(
        self,
        *,
        model: str,
        user: str,
        system: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
        timeout_s: int = 90,
        retries: int = 1,
        schema_hint: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        raise RuntimeError("PROVIDER_CHAT_UNAVAILABLE")

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
        timeout_s: int = 90,
        retries: int = 1,
        meta: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        return [_fallback_embedding(str(x or ""), dim=96) for x in (texts or [])]

    async def rerank(
        self,
        *,
        model: str,
        query: str,
        candidates: list[str],
        top_k: int = 20,
        timeout_s: int = 90,
        retries: int = 1,
        meta: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        qvec = _fallback_embedding(query, dim=96)
        out: list[dict[str, Any]] = []
        for idx, cand in enumerate(candidates or []):
            ctext = str(cand or "")
            cvec = _fallback_embedding(ctext, dim=96)
            cos = _cosine_similarity(qvec, cvec)
            lex = _lexical_score(query, ctext)
            score = max(0.0, min(1.0, 0.7 * cos + 0.3 * lex))
            out.append({"idx": idx, "score": round(score, 6), "text": ctext})
        out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        return out[: max(1, int(top_k))]


@dataclass
class OllamaProvider:
    host: str

    def __post_init__(self) -> None:
        self._client = OllamaClient(self.host)
        self.name = "ollama"
        self.supports_chat_json = True
        self.supports_embeddings = True
        self.supports_rerank = True

    async def chat_json(
        self,
        *,
        model: str,
        user: str,
        system: str,
        temperature: float = 0.0,
        max_tokens: int = 1200,
        timeout_s: int = 90,
        retries: int = 1,
        schema_hint: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        return await self._client.chat_json(
            model=model,
            user=user,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            retries=retries,
            schema_hint=schema_hint,
            meta=meta or {},
        )

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
        timeout_s: int = 90,
        retries: int = 1,
        meta: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []
        try:
            return await self._client.embeddings(
                model=model,
                texts=[str(x or "") for x in texts],
                timeout_s=timeout_s,
                retries=retries,
                meta=meta or {},
            )
        except Exception:
            return [_fallback_embedding(str(x or ""), dim=96) for x in texts]

    async def rerank(
        self,
        *,
        model: str,
        query: str,
        candidates: list[str],
        top_k: int = 20,
        timeout_s: int = 90,
        retries: int = 1,
        meta: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        q_vecs = await self.embed(
            model=model,
            texts=[query],
            timeout_s=timeout_s,
            retries=retries,
            meta={**(meta or {}), "stage": "RERANK_QUERY_EMBED"},
        )
        q_vec = q_vecs[0] if q_vecs else _fallback_embedding(query, dim=96)
        c_vecs = await self.embed(
            model=model,
            texts=[str(x or "") for x in candidates],
            timeout_s=timeout_s,
            retries=retries,
            meta={**(meta or {}), "stage": "RERANK_CAND_EMBED"},
        )
        out: list[dict[str, Any]] = []
        for idx, cand in enumerate(candidates):
            ctext = str(cand or "")
            cvec = c_vecs[idx] if idx < len(c_vecs) else _fallback_embedding(ctext, dim=96)
            cos = _cosine_similarity(q_vec, cvec)
            lex = _lexical_score(query, ctext)
            score = max(0.0, min(1.0, 0.75 * cos + 0.25 * lex))
            out.append({"idx": idx, "score": round(score, 6), "text": ctext})
        out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        return out[: max(1, int(top_k))]


def resolve_llm_provider(provider_name: str, *, ollama_host: str) -> LLMProvider:
    name = str(provider_name or "").strip().lower()
    if name == "ollama":
        return OllamaProvider(host=ollama_host)
    return RulesOnlyProvider()
