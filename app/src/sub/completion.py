import openai
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
import re
from sub.constants import OPENAI_API_KEY, BOT_NAME
from sub.constants import (
    EXAMPLE_CONVOS,
    OPENAI_MODEL,
)
from sub.base import Message
from sub.utils import split_into_shorter_messages, close_thread, logger
from sub.websearch import perform_web_search, format_search_results
from sub.search_decision import should_perform_web_search

import discord

READY_BOT_NAME = BOT_NAME
READY_BOT_EXAMPLE_CONVOS = EXAMPLE_CONVOS

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

        # 株価等の専用ロジックは排除し、汎用フローのみで処理
        
        # Web検索が必要かどうか判定
        search_query = should_perform_web_search(messages)
        search_context = ""
        
        if search_query:
            logger.info(f"Web search triggered for query: {search_query}")
            try:
                search_data = await perform_web_search(search_query, max_results=3)
                logger.info(f"Web search raw result: status={search_data.status}, error={search_data.error_message}, results={search_data.results}")
                if search_data.status.name == "OK" and search_data.results:
                    # 検索結果をコンテキストとして整理
                    search_context = "\n\n【Web検索結果】\n"
                    for i, result in enumerate(search_data.results[:3], 1):
                        title = result.get('title', 'タイトルなし')
                        snippet = result.get('snippet', 'スニペットなし')
                        url = result.get('url', '')
                        search_context += f"{i}. {title}\n{snippet}\n{url}\n\n"
                    logger.info(f"Search context added: {len(search_context)} characters")
                else:
                    # 検索結果が無い場合も、検索を試行したことをAIに伝える
                    search_context = f"\n\n【Web検索情報】\n「{search_query}」について検索を試行しましたが、具体的な最新情報は取得できませんでした。一般的な知識で回答してください。\n"
                    logger.info("Web search returned no results, providing fallback context")
            except Exception as e:
                logger.error(f"Web search failed: {e}")
                # エラー時も検索を試行したことを伝える
                search_context = f"\n\n【Web検索情報】\n「{search_query}」について検索を試行しましたが、技術的な問題により最新情報を取得できませんでした。\n"
        
        # If conversation context is provided, modify the messages to include it
        if conversation_context or search_context:
            # Add conversation context to the system message or create a new one
            rendered_messages = [message.render() for message in messages]
            
            # Find system message or create one
            system_message_found = False
            for msg in rendered_messages:
                if msg["role"] == "system":
                    # Append conversation context to existing system message
                    original_content = msg["content"]
                    context_parts = []
                    if conversation_context:
                        context_parts.append(f"会話履歴:\n{conversation_context}")
                    if search_context:
                        context_parts.append(search_context)
                    
                    msg["content"] = f"{original_content}\n\n" + "\n".join(context_parts)
                    system_message_found = True
                    break
            
            # If no system message found, create one with context
            if not system_message_found:
                context_parts = []
                if conversation_context:
                    context_parts.append(f"会話履歴:\n{conversation_context}")
                if search_context:
                    context_parts.append(search_context)
                
                context_message = {
                    "role": "system", 
                    "content": "\n".join(context_parts)
                }
                rendered_messages.insert(0, context_message)
            
            if conversation_context:
                logger.info(f"Conversation context added: {conversation_context[:200]}...")
        else:
            rendered_messages = [message.render() for message in messages]
        
        openai.api_key = OPENAI_API_KEY
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=rendered_messages,
            timeout=20  # タイムアウトを10秒から20秒に延長（しかし依然として適度）
        )
        reply = response.choices[0]["message"]["content"].strip()
        logger.info(reply)
        logger.info(response.usage)
        return CompletionData(
            status=CompletionResult.OK, reply_text=reply, status_text=None
        )
    except openai.error.InvalidRequestError as e:
        if "This model's maximum context length" in e.user_message:
            return CompletionData(
                status=CompletionResult.TOO_LONG, reply_text=None, status_text=str(e)
            )
        else:
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