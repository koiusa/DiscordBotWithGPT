import openai
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
import re
from sub.constants import (
    OPENAI_API_KEY,
    BOT_NAME,
    OPENAI_PROMPT_TOKEN_COST,
    OPENAI_COMPLETION_TOKEN_COST,
)
from sub.constants import (
    EXAMPLE_CONVOS,
    OPENAI_MODEL,
)
from sub.base import Message
from sub.utils import split_into_shorter_messages, close_thread, logger
from sub.websearch import perform_web_search, format_search_results
from sub.disclaimer import sanitize_reply
from sub.message_augment import augment_messages
from sub.search_decision import should_perform_web_search, SearchDecisionType
from sub.search_context import build_search_context
from datetime import datetime, timezone

import discord

READY_BOT_NAME = BOT_NAME
READY_BOT_EXAMPLE_CONVOS = EXAMPLE_CONVOS

# Limit concurrent OpenAI calls to avoid flooding threads
_OPENAI_CONCURRENCY = 3
_openai_semaphore = asyncio.Semaphore(_OPENAI_CONCURRENCY)

async def _call_openai_async(messages_rendered: List[dict]) -> tuple[dict, float, float]:
    """Run OpenAI ChatCompletion in a worker thread to avoid blocking event loop.
    Returns raw response dict. Raises exceptions unchanged.
    Adds timing logs and semaphore control.
    """
    start_wait = time.perf_counter()
    async with _openai_semaphore:
        queue_wait_ms = (time.perf_counter() - start_wait) * 1000
        openai.api_key = OPENAI_API_KEY
        max_attempts = 3
        backoff_base = 0.8
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            def _sync_invoke():
                invoke_start = time.perf_counter()
                resp = openai.ChatCompletion.create(
                    model=OPENAI_MODEL,
                    messages=messages_rendered,
                    timeout=20,
                )
                invoke_ms_local = (time.perf_counter() - invoke_start) * 1000
                return resp, invoke_ms_local
            try:
                resp, invoke_ms = await asyncio.to_thread(_sync_invoke)
                return resp, queue_wait_ms, invoke_ms
            except Exception as e:
                last_exc = e
                retriable = any(k in str(e).lower() for k in ["rate limit", "timeout", "temporar", "overloaded", "503"])  # noqa
                if attempt == max_attempts or not retriable:
                    raise
                sleep_for = backoff_base * (2 ** (attempt - 1))
                jitter = 0.05 * sleep_for
                await asyncio.sleep(sleep_for + jitter)
        # Should not reach here
        raise last_exc  # type: ignore

class CompletionResult(Enum):
    OK = 0
    TOO_LONG = 1
    INVALID_REQUEST = 2
    OTHER_ERROR = 3

@dataclass
class CompletionData:
    status: CompletionResult
    reply_text: Optional[str]
    status_text: Optional[str]


async def generate_completion_response(
    messages: List[Message], user: str, conversation_context: str = None
) -> CompletionData:
    try:
        logger.info(messages)
        decision = should_perform_web_search(messages)
        # datetime direct answer short-circuit
        if decision.decision == SearchDecisionType.DATETIME_ANSWER:
            return CompletionData(
                status=CompletionResult.OK,
                reply_text=decision.direct_answer or "",
                status_text=None,
            )
        search_context, search_executed = await build_search_context(decision, messages)
        augment_result = augment_messages(
            messages,
            conversation_context=conversation_context,
            search_context=search_context,
            search_executed=search_executed,
        )
        rendered_messages = augment_result.messages
        response, queue_wait_ms, invoke_ms = await _call_openai_async(rendered_messages)
        reply = response.choices[0]["message"]["content"].strip()
        reply = sanitize_reply(reply, search_executed)
        usage = getattr(response, "usage", {}) or {}
        prompt_toks = usage.get("prompt_tokens", "?")
        comp_toks = usage.get("completion_tokens", "?")
        total_toks = usage.get("total_tokens", "?")
        # Cost (USD) estimation
        cost_prompt = 0.0
        cost_completion = 0.0
        try:
            if isinstance(prompt_toks, int) or str(prompt_toks).isdigit():
                cost_prompt = (int(prompt_toks) / 1000.0) * OPENAI_PROMPT_TOKEN_COST
            if isinstance(comp_toks, int) or str(comp_toks).isdigit():
                cost_completion = (int(comp_toks) / 1000.0) * OPENAI_COMPLETION_TOKEN_COST
        except Exception:
            pass
        total_cost = cost_prompt + cost_completion
        logger.info(
            "openai_metrics decision=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s "
            "queue_wait_ms=%.1f invoke_ms=%.1f messages=%d reply_chars=%d cost_prompt=%.6f cost_completion=%.6f cost_total=%.6f",
            decision.decision.name,
            prompt_toks,
            comp_toks,
            total_toks,
            queue_wait_ms,
            invoke_ms,
            len(rendered_messages),
            len(reply),
            cost_prompt,
            cost_completion,
            total_cost,
        )
        return CompletionData(
            status=CompletionResult.OK, reply_text=reply, status_text=None
        )
    except openai.error.InvalidRequestError as e:
        if "This model's maximum context length" in e.user_message:
            return CompletionData(
                status=CompletionResult.TOO_LONG, reply_text=None, status_text=str(e)
            )
        logger.exception(e)
        return CompletionData(
            status=CompletionResult.INVALID_REQUEST,
            reply_text=None,
            status_text=str(e),
        )
    except Exception as e:
        logger.exception(e)
        return CompletionData(
            status=CompletionResult.OTHER_ERROR, reply_text=None, status_text=str(e)
        )

async def process_thread_response(
    user: str, thread: discord.Thread, response_data: CompletionData
):
    status = response_data.status
    reply_text = response_data.reply_text
    status_text = response_data.status_text
    if status is CompletionResult.OK:
        sent_message = None
        if not reply_text:
            sent_message = await thread.send(
                embed=discord.Embed(
                    description=f"**Invalid response** - empty response",
                    color=discord.Color.yellow(),
                )
            )
        else:
            shorter_response = split_into_shorter_messages(reply_text)
            for r in shorter_response:
                sent_message = await thread.send(r)
    elif status is CompletionResult.TOO_LONG:
        await close_thread(thread)
    elif status is CompletionResult.INVALID_REQUEST:
        await thread.send(
            embed=discord.Embed(
                description=f"**Invalid request** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
    else:
        await thread.send(
            embed=discord.Embed(
                description=f"**Error** - {status_text}",
                color=discord.Color.yellow(),
            )
        )

async def process_channel_response(
    user: str, channel, response_data: CompletionData
):
    status = response_data.status
    reply_text = response_data.reply_text
    status_text = response_data.status_text
    if status is CompletionResult.OK:
        sent_message = None
        if not reply_text:
            sent_message = await channel.send(
                embed=discord.Embed(
                    description=f"**Invalid response** - empty response",
                    color=discord.Color.yellow(),
                )
            )
        else:
            shorter_response = split_into_shorter_messages(reply_text)
            for r in shorter_response:
                sent_message = await channel.send(r)
    elif status is CompletionResult.TOO_LONG:
        await channel.send(
            embed=discord.Embed(
                description=f"**To Long** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
    elif status is CompletionResult.INVALID_REQUEST:
        await channel.send(
            embed=discord.Embed(
                description=f"**Invalid request** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
    else:
        await channel.send(
            embed=discord.Embed(
                description=f"**Error** - {status_text}",
                color=discord.Color.yellow(),
            )
        )