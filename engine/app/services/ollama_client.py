from __future__ import annotations

import hashlib
import time
from typing import Any, Callable

import httpx

from ..observability import get_logger
from .json_guard import JSONGuardError, extract_json_candidate, json_guard_parse

logger = get_logger("ollama_client")


class ClientError(Exception):
    def __init__(self, code: str, message: str, meta: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.meta = meta or {}


class OllamaUnavailable(ClientError):
    pass


class ModelNotFound(ClientError):
    pass


class LLMTimeout(ClientError):
    pass


class Ollama5xx(ClientError):
    pass


class BadResponse(ClientError):
    pass


class EmbedFailed(ClientError):
    pass


def _sha1_short(value: str) -> str:
    return hashlib.sha1((value or "").encode("utf-8")).hexdigest()[:10]


def _map_status_error(status_code: int, meta: dict[str, Any]) -> ClientError:
    if status_code == 404:
        return ModelNotFound("MODEL_NOT_FOUND", "model not found", meta)
    if 500 <= status_code <= 599:
        return Ollama5xx("OLLAMA_5XX", f"ollama {status_code}", meta)
    return BadResponse("LLM_BAD_RESPONSE", f"unexpected status={status_code}", meta)


class OllamaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def chat(
        self,
        *,
        model: str,
        user: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 900,
        timeout_s: int = 120,
        retries: int = 2,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_meta = dict(meta or {})
        base_meta.update(
            {
                "model": model,
                "prompt_chars": len(user or ""),
                "prompt_hash": _sha1_short(user or ""),
                "timeout_s": timeout_s,
            }
        )
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "messages": [],
        }
        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].append({"role": "user", "content": user})

        last_error: ClientError | None = None
        for attempt in range(1, retries + 2):
            t0 = time.perf_counter()
            meta_try = {**base_meta, "attempt": attempt}
            logger.info("ollama.chat.start", extra={"meta": meta_try, **meta_try})
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s, connect=3.0)) as client:
                    resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            except httpx.ConnectError as exc:
                last_error = OllamaUnavailable("OLLAMA_UNAVAILABLE", "connection error", {**meta_try, "err": str(exc)})
            except httpx.ConnectTimeout as exc:
                last_error = OllamaUnavailable("OLLAMA_UNAVAILABLE", "connect timeout", {**meta_try, "err": str(exc)})
            except httpx.ReadTimeout as exc:
                last_error = LLMTimeout("LLM_TIMEOUT", "read timeout", {**meta_try, "err": str(exc)})
            except Exception as exc:
                last_error = BadResponse("LLM_BAD_RESPONSE", "unexpected client error", {**meta_try, "err": str(exc)})

            if last_error:
                latency = int((time.perf_counter() - t0) * 1000)
                logger.warning("ollama.chat.fail", extra={"meta": {**last_error.meta, "latency_ms": latency}, **meta_try})
                if last_error.code in {"OLLAMA_UNAVAILABLE", "LLM_TIMEOUT", "OLLAMA_5XX"} and attempt <= retries:
                    await _sleep_backoff(attempt)
                    continue
                raise last_error

            latency = int((time.perf_counter() - t0) * 1000)
            assert resp is not None
            if resp.status_code != 200:
                mapped = _map_status_error(resp.status_code, {**meta_try, "status_code": resp.status_code, "latency_ms": latency})
                logger.warning("ollama.chat.http_error", extra={"meta": mapped.meta, **meta_try})
                if mapped.code == "OLLAMA_5XX" and attempt <= retries:
                    await _sleep_backoff(attempt)
                    continue
                raise mapped

            try:
                data = resp.json()
                text_value = (((data.get("message") or {}).get("content")) or "").strip()
            except Exception as exc:
                raise BadResponse("LLM_BAD_RESPONSE", "invalid response json", {**meta_try, "err": str(exc)})

            if not text_value:
                raise BadResponse("LLM_BAD_RESPONSE", "empty model content", meta_try)

            out_meta = {
                **meta_try,
                "latency_ms": latency,
                "response_chars": len(text_value),
                "tokens_in_est": int(len(user or "") / 3) + 1,
                "tokens_out_est": int(len(text_value) / 3) + 1,
            }
            logger.info("ollama.chat.ok", extra={"meta": out_meta, **meta_try})
            return {"text": text_value, "raw": data, "latency_ms": latency, "tokens_in_est": out_meta["tokens_in_est"], "tokens_out_est": out_meta["tokens_out_est"]}

        raise last_error or BadResponse("LLM_BAD_RESPONSE", "unknown failure", base_meta)

    async def chat_json(
        self,
        *,
        model: str,
        user: str,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout_s: int = 120,
        retries: int = 2,
        schema_hint: str | None = None,
        validate: Callable[[dict[str, Any] | list[Any]], None] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        base_meta = dict(meta or {})
        response = await self.chat(
            model=model,
            user=user,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            retries=retries,
            meta={**base_meta, "expect": "json"},
        )
        raw_text = str(response.get("text") or "")
        repaired = False
        try:
            parsed = json_guard_parse(raw_text)
        except JSONGuardError as exc:
            logger.warning(
                "ollama.chat_json.parse_fail",
                extra={
                    **base_meta,
                    "meta": {
                        "err": str(exc),
                        "snippet": exc.snippet[:240],
                    },
                },
            )
            candidate = raw_text
            try:
                candidate = extract_json_candidate(raw_text)
            except Exception:
                pass
            repair_prompt = (
                "Output ONLY valid JSON. Keep the same keys and structure. "
                "Do not add markdown or comments.\n"
            )
            if schema_hint:
                repair_prompt += f"Schema hint:\n{schema_hint}\n\n"
            repair_prompt += f"JSON to fix:\n{candidate}"
            repair = await self.chat(
                model=model,
                user=repair_prompt,
                system="Output ONLY valid JSON.",
                temperature=0.0,
                max_tokens=max_tokens,
                timeout_s=min(timeout_s, 90),
                retries=1,
                meta={**base_meta, "stage": "JSON_FIX", "expect": "json"},
            )
            repaired = True
            try:
                parsed = json_guard_parse(str(repair.get("text") or ""))
            except JSONGuardError as exc2:
                raise BadResponse(
                    "LLM_BAD_RESPONSE",
                    f"json guard failed after repair: {exc2}",
                    {**base_meta, "snippet": exc2.snippet[:240]},
                ) from exc2

        if validate:
            try:
                validate(parsed)
            except Exception as exc:
                raise BadResponse("LLM_BAD_RESPONSE", f"json schema validation failed: {exc}", base_meta) from exc

        logger.info(
            "ollama.chat_json.ok",
            extra={
                **base_meta,
                "meta": {
                    "repaired": repaired,
                    "type": type(parsed).__name__,
                },
            },
        )
        return parsed

    async def embeddings(
        self,
        *,
        model: str,
        texts: list[str],
        timeout_s: int = 120,
        retries: int = 2,
        meta: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        texts = [str(x or "") for x in (texts or [])]
        if not texts:
            return []

        def _normalize_vectors(data: Any, expected: int, meta_try: dict[str, Any]) -> list[list[float]]:
            if not isinstance(data, dict):
                raise EmbedFailed("EMBED_FAILED", "invalid embed response payload", meta_try)
            raw = data.get("embeddings")
            if raw is None:
                one = data.get("embedding")
                if isinstance(one, list) and one and all(isinstance(v, (int, float)) for v in one):
                    raw = [one]
            if not isinstance(raw, list) or len(raw) == 0:
                raise EmbedFailed("EMBED_FAILED", "empty embedding list", meta_try)
            out: list[list[float]] = []
            for vec in raw:
                if not isinstance(vec, list) or len(vec) == 0:
                    raise EmbedFailed("EMBED_FAILED", "invalid embedding vector", meta_try)
                casted = [float(v) for v in vec]
                out.append(casted)
            if len(out) != expected:
                raise EmbedFailed(
                    "EMBED_FAILED",
                    f"embedding count mismatch expected={expected} got={len(out)}",
                    meta_try,
                )
            return out

        base_meta = dict(meta or {})
        base_meta.update(
            {
                "model": model,
                "batch_size": len(texts),
                "batch_chars": sum(len(t) for t in texts),
            }
        )
        last_error: ClientError | None = None
        fallback_single = False

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s, connect=3.0)) as client:
            for attempt in range(1, retries + 2):
                t0 = time.perf_counter()
                meta_try = {**base_meta, "attempt": attempt, "endpoint": "/api/embed"}
                logger.info("ollama.embed.batch.start", extra={"meta": meta_try, **meta_try})
                try:
                    resp = await client.post(f"{self.base_url}/api/embed", json={"model": model, "input": texts})
                except httpx.ConnectError as exc:
                    last_error = OllamaUnavailable("OLLAMA_UNAVAILABLE", "connection error", {**meta_try, "err": str(exc)})
                except httpx.ConnectTimeout as exc:
                    last_error = OllamaUnavailable("OLLAMA_UNAVAILABLE", "connect timeout", {**meta_try, "err": str(exc)})
                except httpx.ReadTimeout as exc:
                    last_error = LLMTimeout("LLM_TIMEOUT", "read timeout", {**meta_try, "err": str(exc)})
                except Exception as exc:
                    last_error = EmbedFailed("EMBED_FAILED", "unexpected embed batch client error", {**meta_try, "err": str(exc)})

                if last_error:
                    latency = int((time.perf_counter() - t0) * 1000)
                    logger.warning("ollama.embed.batch.fail", extra={"meta": {**last_error.meta, "latency_ms": latency}, **meta_try})
                    if last_error.code in {"OLLAMA_UNAVAILABLE", "LLM_TIMEOUT", "OLLAMA_5XX"} and attempt <= retries:
                        await _sleep_backoff(attempt)
                        continue
                    raise last_error

                latency = int((time.perf_counter() - t0) * 1000)
                assert resp is not None
                if resp.status_code == 404:
                    fallback_single = True
                    logger.info("ollama.embed.batch.fallback_single", extra={"meta": {**meta_try, "latency_ms": latency}, **meta_try})
                    break
                if resp.status_code != 200:
                    mapped = _map_status_error(resp.status_code, {**meta_try, "status_code": resp.status_code, "latency_ms": latency})
                    logger.warning("ollama.embed.batch.http_error", extra={"meta": mapped.meta, **meta_try})
                    if mapped.code == "OLLAMA_5XX" and attempt <= retries:
                        await _sleep_backoff(attempt)
                        continue
                    raise mapped

                try:
                    data = resp.json()
                    vectors = _normalize_vectors(data, len(texts), meta_try)
                except ClientError:
                    raise
                except Exception as exc:
                    raise EmbedFailed("EMBED_FAILED", "invalid embed batch response json", {**meta_try, "err": str(exc)})

                logger.info(
                    "ollama.embed.batch.ok",
                    extra={
                        "meta": {
                            **meta_try,
                            "latency_ms": latency,
                            "count": len(vectors),
                            "dim": len(vectors[0]) if vectors else 0,
                        },
                        **meta_try,
                    },
                )
                return vectors

            if not fallback_single:
                raise last_error or EmbedFailed("EMBED_FAILED", "unknown embedding batch failure", base_meta)

            vectors: list[list[float]] = []
            for idx, text_value in enumerate(texts):
                per_meta = {
                    "model": model,
                    "text_chars": len(text_value or ""),
                    "text_hash": _sha1_short(text_value or ""),
                    "segment_index": idx,
                    "endpoint": "/api/embeddings",
                }
                last_error = None
                for attempt in range(1, retries + 2):
                    t0 = time.perf_counter()
                    meta_try = {**per_meta, "attempt": attempt}
                    logger.info("ollama.embed.single.start", extra={"meta": meta_try, **meta_try})
                    try:
                        resp = await client.post(f"{self.base_url}/api/embeddings", json={"model": model, "prompt": text_value})
                    except httpx.ConnectError as exc:
                        last_error = OllamaUnavailable("OLLAMA_UNAVAILABLE", "connection error", {**meta_try, "err": str(exc)})
                    except httpx.ConnectTimeout as exc:
                        last_error = OllamaUnavailable("OLLAMA_UNAVAILABLE", "connect timeout", {**meta_try, "err": str(exc)})
                    except httpx.ReadTimeout as exc:
                        last_error = LLMTimeout("LLM_TIMEOUT", "read timeout", {**meta_try, "err": str(exc)})
                    except Exception as exc:
                        last_error = EmbedFailed("EMBED_FAILED", "unexpected embed client error", {**meta_try, "err": str(exc)})

                    if last_error:
                        latency = int((time.perf_counter() - t0) * 1000)
                        logger.warning("ollama.embed.single.fail", extra={"meta": {**last_error.meta, "latency_ms": latency}, **meta_try})
                        if last_error.code in {"OLLAMA_UNAVAILABLE", "LLM_TIMEOUT", "OLLAMA_5XX"} and attempt <= retries:
                            await _sleep_backoff(attempt)
                            continue
                        raise last_error

                    latency = int((time.perf_counter() - t0) * 1000)
                    assert resp is not None
                    if resp.status_code != 200:
                        mapped = _map_status_error(resp.status_code, {**meta_try, "status_code": resp.status_code, "latency_ms": latency})
                        logger.warning("ollama.embed.single.http_error", extra={"meta": mapped.meta, **meta_try})
                        if mapped.code == "OLLAMA_5XX" and attempt <= retries:
                            await _sleep_backoff(attempt)
                            continue
                        raise mapped

                    try:
                        data = resp.json()
                        vec = data.get("embedding")
                    except Exception as exc:
                        raise EmbedFailed("EMBED_FAILED", "invalid response json", {**meta_try, "err": str(exc)})

                    if not isinstance(vec, list) or len(vec) == 0:
                        raise EmbedFailed("EMBED_FAILED", "empty embedding", meta_try)
                    casted = [float(v) for v in vec]
                    logger.info(
                        "ollama.embed.single.ok",
                        extra={"meta": {**meta_try, "latency_ms": latency, "dim": len(casted)}, **meta_try},
                    )
                    vectors.append(casted)
                    break
                else:
                    raise last_error or EmbedFailed("EMBED_FAILED", "unknown embedding failure", per_meta)
            return vectors


async def _sleep_backoff(attempt: int) -> None:
    import asyncio

    await asyncio.sleep(min(0.4 * attempt, 1.2))
