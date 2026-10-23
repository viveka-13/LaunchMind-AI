# agent/llm_client.py
# Unified resilient LLM client with tenacity retries, circuit breaker, and exception classification

import os
import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable
from functools import wraps

from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception,
)
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Data Structures & Exceptions
# ─────────────────────────────────────────────

@dataclass
class LLMResult:
    text: str
    attempts: int
    latency_ms: float
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class LLMCallError(Exception):
    """Unified custom exception for all LLM call failures."""
    def __init__(
        self,
        node: str,
        reason: str,
        retryable: bool,
        attempts: int,
        original_exc: Optional[Exception] = None,
    ):
        self.node = node
        self.reason = reason
        self.retryable = retryable
        self.attempts = attempts
        self.original_exc = original_exc
        super().__init__(f"LLMCallError(node='{node}', reason='{reason}', retryable={retryable}, attempts={attempts})")


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

def _get_max_attempts() -> int:
    return int(os.environ.get("LLM_MAX_ATTEMPTS", "4"))

def _get_backoff_base() -> float:
    return float(os.environ.get("LLM_BACKOFF_BASE_SECONDS", "1.0"))

def _get_backoff_max() -> float:
    return float(os.environ.get("LLM_BACKOFF_MAX_SECONDS", "30.0"))

def _get_timeout() -> float:
    return float(os.environ.get("LLM_TIMEOUT_SECONDS", "120.0"))

def _get_circuit_breaker_threshold() -> int:
    return int(os.environ.get("LLM_CIRCUIT_BREAKER_THRESHOLD", "5"))


# ─────────────────────────────────────────────
# Per-Run Circuit Breaker
# ─────────────────────────────────────────────

_circuit_breakers: Dict[str, int] = {}  # session_id -> consecutive failure count

def get_consecutive_failures(session_id: str) -> int:
    return _circuit_breakers.get(session_id, 0)

def record_success(session_id: Optional[str]):
    if session_id and session_id in _circuit_breakers:
        _circuit_breakers[session_id] = 0

def record_failure(session_id: Optional[str]):
    if session_id:
        _circuit_breakers[session_id] = _circuit_breakers.get(session_id, 0) + 1

def reset_circuit_breaker(session_id: Optional[str]):
    if session_id and session_id in _circuit_breakers:
        del _circuit_breakers[session_id]


# ─────────────────────────────────────────────
# Exception Classification & Retry-After Extraction
# ─────────────────────────────────────────────

def get_retry_after(exc: Exception) -> Optional[float]:
    """Extract Retry-After header in seconds (capped at 60s) from HTTP or SDK exceptions."""
    try:
        # Check response headers (httpx or requests or SDK response)
        resp = getattr(exc, "response", None)
        if resp and hasattr(resp, "headers"):
            val = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
            if val:
                sec = float(val)
                return min(sec, 60.0)
        # Check direct attribute on exception (e.g. RateLimitError)
        val = getattr(exc, "retry_after", None)
        if val is not None:
            return min(float(val), 60.0)
    except Exception:
        pass
    return None


def is_retryable(exc: Exception) -> bool:
    """
    Classify whether an exception is retryable.
    Retry on: timeouts, connection errors, HTTP 429, 5xx, and 529 overloaded.
    NEVER retry on: 400, 401, 403, 404, or context-length / invalid-request errors.
    """
    if isinstance(exc, LLMCallError):
        return exc.retryable

    # Check for non-retryable status codes first
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        resp = getattr(exc, "response", None)
        if resp and hasattr(resp, "status_code"):
            status_code = resp.status_code

    if status_code in (400, 401, 403, 404):
        return False

    msg = str(exc).lower()

    # Explicit non-retryable keywords
    if any(k in msg for k in ("unauthorized", "invalid_api_key", "authentication", "forbidden", "model_not_found")):
        return False

    # Retryable status codes
    if status_code in (429, 500, 502, 503, 504, 529):
        return True

    # Timeout and Connection errors
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return True

    # Check exception type name or class inheritance
    type_name = type(exc).__name__.lower()
    if any(t in type_name for t in ("timeout", "connection", "ratelimit", "internalserver", "servererror", "overloaded")):
        return True

    # Keywords in error string
    if any(k in msg for k in ("rate limit", "too many requests", "overloaded", "timeout", "timed out", "connection reset", "connection refused")):
        return True

    return False


# ─────────────────────────────────────────────
# Primary and Fallback Provider Instantiation
# ─────────────────────────────────────────────

def _create_llm_client(provider: str, max_tokens: int = 1500, timeout: float = 120.0, temperature: float = 0.2):
    """Create Chat client for the requested provider."""
    provider = provider.lower().strip()
    if provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not configured.")
        return ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=api_key,
            max_tokens=max_tokens,
            timeout=timeout,
            temperature=temperature,
        )
    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured.")
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                anthropic_api_key=api_key,
                max_tokens_to_sample=max_tokens,
                default_request_timeout=timeout,
                temperature=temperature,
            )
        except ImportError:
            raise ValueError("langchain-anthropic package is not installed for anthropic provider.")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


# ─────────────────────────────────────────────
# Core LLM Call Function
# ─────────────────────────────────────────────

async def llm_call(
    prompt_or_messages,
    *,
    node: str,
    max_tokens: Optional[int] = None,
    timeout: Optional[float] = None,
    temperature: Optional[float] = None,
    session_id: Optional[str] = None,
    retry_callback: Optional[Callable[[dict], Any]] = None,
) -> LLMResult:
    """
    Central, single wrapper for all LLM calls in LaunchMind-AI.
    Handles:
    - Tenacity retries with exponential backoff & jitter
    - Retry-After header enforcement
    - Circuit breaker (fails fast after N consecutive retryable failures in run)
    - Empty response retry and truncation error detection
    - Optional fallback provider
    - Safe structured logging
    """
    max_tokens = max_tokens or 1500
    timeout_sec = timeout or _get_timeout()
    temp = temperature if temperature is not None else 0.2
    max_attempts = _get_max_attempts()
    base_backoff = _get_backoff_base()
    max_backoff = _get_backoff_max()
    threshold = _get_circuit_breaker_threshold()

    # 1. Circuit breaker check
    if session_id and get_consecutive_failures(session_id) >= threshold:
        logger.error(f"[LLMClient] Circuit breaker tripped for session {session_id} on node '{node}'")
        raise LLMCallError(
            node=node,
            reason="provider_unavailable",
            retryable=False,
            attempts=0,
        )

    # 2. Normalize messages
    if isinstance(prompt_or_messages, str):
        messages = [HumanMessage(content=prompt_or_messages)]
    elif isinstance(prompt_or_messages, list):
        messages = prompt_or_messages
    else:
        messages = [HumanMessage(content=str(prompt_or_messages))]

    # Primary provider
    provider = "groq"
    fallback_provider = os.environ.get("LLM_FALLBACK_PROVIDER")

    attempt_counter = 0
    start_time = time.time()
    last_exception = None

    async def _execute_single(llm_inst, current_provider: str) -> LLMResult:
        nonlocal attempt_counter
        attempt_counter += 1
        t0 = time.time()
        
        logger.debug(f"[LLMClient] Attempt {attempt_counter} on node '{node}' ({current_provider})")
        resp = await llm_inst.ainvoke(messages)
        latency = (time.time() - t0) * 1000

        text = getattr(resp, "content", "")
        if isinstance(text, list):
            text = "".join(str(p) for p in text)
        text = str(text).strip()

        # Check metadata
        meta = getattr(resp, "response_metadata", {}) or {}
        finish_reason = meta.get("finish_reason") or meta.get("stop_reason")

        # Truncated response check
        if finish_reason in ("length", "max_tokens"):
            raise LLMCallError(
                node=node,
                reason=f"truncated_response: token limit ({max_tokens}) reached on node '{node}'",
                retryable=False,
                attempts=attempt_counter,
            )

        # Token usage
        usage = meta.get("token_usage", {})
        in_tokens = usage.get("prompt_tokens")
        out_tokens = usage.get("completion_tokens")

        model_name = getattr(llm_inst, "model", current_provider)
        logger.info(f"[LLM] node={node} provider={current_provider} attempt={attempt_counter} latency={latency:.1f}ms")
        
        return LLMResult(
            text=text,
            attempts=attempt_counter,
            latency_ms=latency,
            model=model_name,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

    # 3. Primary execution with Tenacity retry loop
    try:
        primary_client = _create_llm_client(provider, max_tokens=max_tokens, timeout=timeout_sec, temperature=temp)
    except Exception as e:
        record_failure(session_id)
        raise LLMCallError(
            node=node,
            reason=f"Failed to initialize LLM provider '{provider}': {e}",
            retryable=False,
            attempts=0,
            original_exc=e,
        ) from e

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(initial=base_backoff, max=max_backoff),
            retry=retry_if_exception(is_retryable),
            reraise=True,
        ):
            with attempt:
                try:
                    res = await _execute_single(primary_client, provider)
                    # Handle empty response: retry once
                    if not res.text:
                        if attempt_counter < max_attempts:
                            logger.warning(f"[LLMClient] Empty response on node '{node}', triggering retry...")
                            raise ValueError("empty_response")
                        else:
                            raise LLMCallError(
                                node=node,
                                reason="empty_response",
                                retryable=False,
                                attempts=attempt_counter,
                            )
                    record_success(session_id)
                    return res
                except Exception as e:
                    last_exception = e
                    # If this is a 429 carrying a Retry-After header, sleep at least that long
                    retry_after = get_retry_after(e)
                    if retry_after and retry_after > 0:
                        logger.info(f"[LLMClient] Honoring Retry-After: waiting {retry_after:.1f}s")
                        await asyncio.sleep(retry_after)

                    if retry_callback and is_retryable(e):
                        try:
                            retry_callback({
                                "node": node,
                                "attempt": attempt_counter,
                                "max_attempts": max_attempts,
                                "wait_seconds": retry_after or base_backoff,
                                "reason": str(e),
                            })
                        except Exception:
                            pass
                    raise
    except Exception as exc:
        last_exception = exc

    # 4. Fallback Provider (if configured and error was retryable)
    if fallback_provider and is_retryable(last_exception):
        logger.warning(f"[LLMClient] Primary exhausted for node '{node}'. Attempting fallback provider '{fallback_provider}'...")
        try:
            fb_client = _create_llm_client(fallback_provider, max_tokens=max_tokens, timeout=timeout_sec, temperature=temp)
            res = await _execute_single(fb_client, fallback_provider)
            if res.text:
                record_success(session_id)
                return res
        except Exception as fb_err:
            logger.error(f"[LLMClient] Fallback provider '{fallback_provider}' failed: {fb_err}")
            last_exception = fb_err

    # 5. Record final failure & raise unified LLMCallError
    record_failure(session_id)
    retryable_flag = is_retryable(last_exception)
    reason = getattr(last_exception, "reason", None) or str(last_exception)
    
    raise LLMCallError(
        node=node,
        reason=reason,
        retryable=retryable_flag,
        attempts=attempt_counter,
        original_exc=last_exception,
    ) from last_exception


# ─────────────────────────────────────────────
# Synchronous Helper
# ─────────────────────────────────────────────

def llm_call_sync(*args, **kwargs) -> LLMResult:
    """Synchronous wrapper for llm_call."""
    return asyncio.run(llm_call(*args, **kwargs))


# ─────────────────────────────────────────────
# HTTP Retry Decorator for External Outbound Tools
# ─────────────────────────────────────────────

def http_retry(max_attempts: int = 3, initial_backoff: float = 1.0, max_backoff: float = 10.0):
    """
    Decorator for external HTTP tool calls (DuckDuckGo, Pexels, Mermaid).
    Applies tenacity exponential jitter retry and graceful degradation.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from tenacity import Retrying, stop_after_attempt, wait_exponential_jitter, retry_if_exception
            try:
                for attempt in Retrying(
                    stop=stop_after_attempt(max_attempts),
                    wait=wait_exponential_jitter(initial=initial_backoff, max=max_backoff),
                    retry=retry_if_exception(is_retryable),
                    reraise=True,
                ):
                    with attempt:
                        return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"[HTTPRetry] {func.__name__} failed after {max_attempts} attempts: {e}")
                raise
        return wrapper
    return decorator
