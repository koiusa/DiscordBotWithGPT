import asyncio
import time
import openai
from typing import List, Dict, Any, Optional, Tuple
from sub.constants import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_PRIMARY_TIMEOUT_SEC, OPENAI_FALLBACK_TIMEOUT_SEC, OPENAI_FALLBACK_MODEL, OPENAI_MAX_ATTEMPTS
from sub.infra.logging import logger, log_event

# Public semaphore size can be tuned later
_DEFAULT_CONCURRENCY = 3
_semaphore = asyncio.Semaphore(_DEFAULT_CONCURRENCY)

class OpenAIError(Exception):
    pass

class OpenAITimeoutError(OpenAIError):
    """Raised when OpenAI API call times out."""
    pass

class OpenAIFinalError(OpenAIError):
    """Raised when all retry attempts are exhausted."""
    pass

def _is_timeout(exception: Exception) -> bool:
    """Check if exception indicates a timeout."""
    return 'timeout' in str(exception).lower()

def _is_retriable(exception: Exception) -> bool:
    """Check if exception is retriable (includes timeouts, rate limits, etc.)."""
    error_str = str(exception).lower()
    return any(k in error_str for k in [
        'rate limit', 'timeout', 'temporar', 'overloaded', '503'
    ])

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
                retriable = _is_retriable(e)
                is_timeout = _is_timeout(e)
                
                if is_timeout:
                    log_event("openai_timeout", purpose=purpose, attempt=attempt, timeout=timeout, model=(model or OPENAI_MODEL))
                
                if attempt == max_attempts or not retriable:
                    log_event("openai_call_failed", purpose=purpose, attempt=attempt, retriable=retriable, error=str(e)[:300])
                    if is_timeout:
                        raise OpenAITimeoutError(str(e))
                    else:
                        raise OpenAIFinalError(str(e))
                sleep_for = backoff_base * (2 ** (attempt - 1))
                jitter = 0.05 * sleep_for
                log_event("openai_retry", attempt=attempt, sleep_ms=int((sleep_for + jitter)*1000), retriable=retriable)
                await asyncio.sleep(sleep_for + jitter)
        raise OpenAIError(str(last_exc))  # safety

async def chat_with_fallback(
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    purpose: str = "completion",
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Chat function with automatic fallback to secondary model on primary failure.
    
    Returns: (raw_response, metrics_dict, model_used)
    model_used: "primary", "fallback", or the actual model name used
    """
    primary_model = model or OPENAI_MODEL
    fallback_model = OPENAI_FALLBACK_MODEL.strip() if OPENAI_FALLBACK_MODEL else None
    
    # Try primary model first
    try:
        log_event("openai_primary_start", model=primary_model, purpose=purpose, has_fallback=bool(fallback_model))
        resp, metrics = await chat(
            messages=messages,
            model=primary_model,
            timeout=OPENAI_PRIMARY_TIMEOUT_SEC,
            max_attempts=OPENAI_MAX_ATTEMPTS,
            purpose=purpose,
        )
        return resp, metrics, "primary"
        
    except (OpenAITimeoutError, OpenAIFinalError) as e:
        log_event("openai_primary_failed", model=primary_model, purpose=purpose, 
                 error_type=type(e).__name__, error=str(e)[:200])
        
        # Try fallback if configured
        if fallback_model:
            try:
                log_event("openai_fallback_start", primary_model=primary_model, 
                         fallback_model=fallback_model, purpose=purpose)
                resp, metrics = await chat(
                    messages=messages,
                    model=fallback_model,
                    timeout=OPENAI_FALLBACK_TIMEOUT_SEC,
                    max_attempts=OPENAI_MAX_ATTEMPTS,
                    purpose=purpose,
                )
                log_event("openai_fallback_success", model=fallback_model, purpose=purpose)
                return resp, metrics, "fallback"
                
            except (OpenAITimeoutError, OpenAIFinalError) as fallback_e:
                log_event("openai_fallback_failed", model=fallback_model, purpose=purpose,
                         error_type=type(fallback_e).__name__, error=str(fallback_e)[:200])
                raise fallback_e
        else:
            # No fallback configured, re-raise original error
            raise e
