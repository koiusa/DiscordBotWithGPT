import openai  # kept for InvalidRequestError reference
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
from sub.core.base import Message
from sub.discord.discord_utils import split_into_shorter_messages, close_thread
from sub.infra.logging import logger
from sub.search.websearch import perform_web_search, format_search_results
from sub.disclaimer import sanitize_reply
from sub.llm.message_augment import augment_messages
from sub.constants import (
    SUMMARY_TRIGGER_PROMPT_TOKENS,
    SUMMARY_TARGET_REDUCTION_RATIO,
    SUMMARY_MAX_SOURCE_CHARS,
    SUMMARY_MODEL,
)
from sub.search.search_decision import should_perform_web_search, SearchDecisionType
from sub.search.search_context import build_search_context
from datetime import datetime, timezone
from sub.llm.openai_wrapper import chat as openai_chat, chat_with_fallback, OpenAITimeoutError, OpenAIFinalError

import discord

READY_BOT_NAME = BOT_NAME
READY_BOT_EXAMPLE_CONVOS = EXAMPLE_CONVOS

# _call_openai_async removed: replaced by openai_wrapper.chat

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
        # 1. 会話履歴要約検討 (簡易トークン概算 = 4 chars / token 近似)
        summary_applied = False
        if conversation_context:
            try:
                approx_prompt_tokens = len(conversation_context) / 4
                if (
                    approx_prompt_tokens > SUMMARY_TRIGGER_PROMPT_TOKENS
                    and len(conversation_context) < SUMMARY_MAX_SOURCE_CHARS
                ):
                    system_sum = {
                        "role": "system",
                        "content": "以下は過去会話の生ログです。重要な事実・ユーザーの意図・未回答の要求・決定事項を日本語で簡潔に列挙し、不要な挨拶や雑談は除外し200～300文字程度に要約してください。出力は箇条書き風で。",
                    }
                    user_sum = {"role": "user", "content": conversation_context}
                    try:
                        sum_resp, sum_metrics = await openai_chat(
                            [system_sum, user_sum],
                            model=SUMMARY_MODEL,
                            timeout=15,
                            purpose="summary",
                        )
                        summarized = sum_resp.choices[0]["message"]["content"].strip()
                        target_chars = int(len(conversation_context) * SUMMARY_TARGET_REDUCTION_RATIO)
                        if len(summarized) > target_chars:
                            summarized = summarized[: target_chars - 15] + "..."
                        conversation_context = summarized
                        summary_applied = True
                    except Exception as se:
                        logger.warning(f"summary_failed err={se}")
            except Exception:
                pass
        decision = should_perform_web_search(messages)
        # datetime direct answer short-circuit
        if decision.decision == SearchDecisionType.DATETIME_ANSWER:
            return CompletionData(
                status=CompletionResult.OK,
                reply_text=decision.direct_answer or "",
                status_text=None,
            )
        search_result = await build_search_context(decision, messages)
        search_context = search_result.context
        search_executed = search_result.executed
        search_status = search_result.status
        augment_result = augment_messages(
            messages,
            conversation_context=conversation_context,
            search_context=search_context,
            search_executed=search_executed,
        )
        rendered_messages = augment_result.messages
        response, metrics, model_used = await chat_with_fallback(rendered_messages, model=OPENAI_MODEL, purpose="completion")
        queue_wait_ms = metrics.get('queue_wait_ms', 0.0)
        invoke_ms = metrics.get('invoke_ms', 0.0)
        attempt_used = metrics.get('attempt', 1)
        reply = response.choices[0]["message"]["content"].strip()
        
        # Add model prefix to reply
        if model_used == "primary":
            reply = f"(model: {OPENAI_MODEL}) {reply}"
        elif model_used == "fallback":
            from sub.constants import OPENAI_FALLBACK_MODEL
            reply = f"(fallback: {OPENAI_FALLBACK_MODEL}) {reply}"
        
        reply = sanitize_reply(reply, search_executed)
        usage = getattr(response, "usage", {}) or {}
        prompt_toks = usage.get("prompt_tokens", "?")
        comp_toks = usage.get("completion_tokens", "?")
        total_toks = usage.get("total_tokens", "?")
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
            "openai_metrics decision=%s decision_score=%s decision_reasons=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s "
            "queue_wait_ms=%.1f invoke_ms=%.1f attempt=%d messages=%d reply_chars=%d cost_prompt=%.6f cost_completion=%.6f cost_total=%.6f summary_applied=%s "
            "augment_truncated=%s augment_sections=%s search_executed=%s search_status=%s",
            decision.decision.name,
            getattr(decision, 'score', '?'),
            getattr(decision, 'reasons', []),
            prompt_toks,
            comp_toks,
            total_toks,
            queue_wait_ms,
            invoke_ms,
            attempt_used,
            len(rendered_messages),
            len(reply),
            cost_prompt,
            cost_completion,
            total_cost,
            summary_applied,
            augment_result.meta.conversation_truncated,
            ','.join(augment_result.meta.sections_applied),
            search_executed,
            search_status,
        )
        return CompletionData(status=CompletionResult.OK, reply_text=reply, status_text=None)
    except (OpenAITimeoutError, OpenAIFinalError) as e:
        logger.warning(f"OpenAI timeout/final error: {e}")
        # Return user-friendly Japanese timeout message
        timeout_message = "申し訳ありませんが、AIサービスがタイムアウトしました。しばらく待ってから再度お試しください。"
        return CompletionData(status=CompletionResult.OK, reply_text=timeout_message, status_text=None)
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