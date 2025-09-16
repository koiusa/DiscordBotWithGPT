import asyncio
import time
import openai
from typing import List, Dict, Any, Optional, Tuple
from sub.constants import OPENAI_API_KEY, OPENAI_MODEL
from sub.infra.logging import logger, log_event

# Public semaphore size can be tuned later
_DEFAULT_CONCURRENCY = 3
_semaphore = asyncio.Semaphore(_DEFAULT_CONCURRENCY)

class OpenAIError(Exception):
    pass

async def chat(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    timeout: int = 20,
    max_attempts: int = 3,
    backoff_base: float = 0.8,
    purpose: str = "completion",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Unified OpenAI ChatCompletion wrapper with:
    - semaphore concurrency control
    - retry (exponential backoff + jitter)
    - timing metrics
    Returns: (raw_response, metrics_dict)
    metrics: queue_wait_ms, invoke_ms, attempt, purpose
    """
    start_wait = time.perf_counter()
    async with _semaphore:
        queue_wait_ms = (time.perf_counter() - start_wait) * 1000
        openai.api_key = OPENAI_API_KEY
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            def _sync_invoke():
                invoke_start = time.perf_counter()
                resp = openai.ChatCompletion.create(
                    model=model or OPENAI_MODEL,
                    messages=messages,
                    timeout=timeout,
                )
                invoke_ms = (time.perf_counter() - invoke_start) * 1000
                return resp, invoke_ms
            try:
                resp, invoke_ms = await asyncio.to_thread(_sync_invoke)
                metrics = {
                    'queue_wait_ms': queue_wait_ms,
                    'invoke_ms': invoke_ms,
                    'attempt': attempt,
                    'purpose': purpose,
                }
                try:
                    usage = getattr(resp, 'usage', None) or {}
                    prompt_t = usage.get('prompt_tokens') if isinstance(usage, dict) else None
                    comp_t = usage.get('completion_tokens') if isinstance(usage, dict) else None
                    total_t = usage.get('total_tokens') if isinstance(usage, dict) else None
                    log_event("openai_call", attempt=attempt, purpose=purpose, invoke_ms=f"{invoke_ms:.1f}", queue_wait_ms=f"{queue_wait_ms:.1f}", prompt_tokens=prompt_t, completion_tokens=comp_t, total_tokens=total_t, model=(model or OPENAI_MODEL))
                except Exception:
                    pass
                return resp, metrics
            except Exception as e:
                last_exc = e
                retriable = any(k in str(e).lower() for k in [
                    'rate limit', 'timeout', 'temporar', 'overloaded', '503'
                ])
                if attempt == max_attempts or not retriable:
                    log_event("openai_call_failed", purpose=purpose, attempt=attempt, retriable=retriable, error=str(e)[:300])
                    raise
                sleep_for = backoff_base * (2 ** (attempt - 1))
                jitter = 0.05 * sleep_for
                log_event("openai_retry", attempt=attempt, sleep_ms=int((sleep_for + jitter)*1000), retriable=retriable)
                await asyncio.sleep(sleep_for + jitter)
        raise OpenAIError(str(last_exc))  # safety
