import discord
from typing import List, Tuple
import asyncio
from datetime import datetime
from sub.completion import (
    generate_completion_response,
    process_thread_response,
    process_channel_response,
)
from sub.utils import (
    logger,
    close_thread,
    is_last_message_stale,
    discord_message_to_message,
)
from sub.constants import (
    ACTIVATE_THREAD_PREFX,
    MAX_THREAD_MESSAGES,
    MAX_CHANNEL_MESSAGES,
    SECONDS_DELAY_RECEIVING_MSG,
)
from sub.history_store import HistoryEntry, HistoryStore
from sub.format_conversation import create_conversation_context

async def thread_chat(message, client: discord.Client, history_store: HistoryStore) -> bool:
    logger.info("thread_chat called")
    thread: discord.Thread = message.channel

    # Ownership / state checks
    if thread.owner_id != client.user.id:
        return False
    if thread.archived or thread.locked or not thread.name.startswith(ACTIVATE_THREAD_PREFX):
        return False
    if thread.message_count > MAX_THREAD_MESSAGES:
        await close_thread(thread=thread)
        return False

    # Debounce
    if SECONDS_DELAY_RECEIVING_MSG > 0:
        await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
        if is_last_message_stale(
            interaction_message=message,
            last_message=thread.last_message,
            bot_id=client.user.id,
        ):
            return False

    logger.info(
        f"Thread message to process - {message.author}: {message.content[:50]} - {thread.name} {thread.jump_url}"
    )

    conversation_context, channel_messages = await _prepare_context_and_messages(
        message=message,
        history_store=history_store,
        max_messages=MAX_THREAD_MESSAGES,
    )

    async with thread.typing():
        response_data = await generate_completion_response(
            user=message.author, messages=channel_messages, conversation_context=conversation_context
        )

    if is_last_message_stale(
        interaction_message=message,
        last_message=thread.last_message,
        bot_id=client.user.id,
    ):
        return False

    await process_thread_response(
        user=message.author, thread=thread, response_data=response_data
    )
    return True

async def channel_chat(message, client: discord.Client, history_store: HistoryStore) -> bool:
    logger.info("channel_chat called")
    channel: discord.TextChannel = message.channel

    # Debounce
    if SECONDS_DELAY_RECEIVING_MSG > 0:
        await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
        if is_last_message_stale(
            interaction_message=message,
            last_message=channel.last_message,
            bot_id=client.user.id,
        ):
            return False

    logger.info(
        f"Channel message to process - {message.author}: {message.content[:50]} - {channel.name} {channel.jump_url}"
    )

    conversation_context, channel_messages = await _prepare_context_and_messages(
        message=message,
        history_store=history_store,
        max_messages=MAX_CHANNEL_MESSAGES,
    )

    async with channel.typing():
        response_data = await generate_completion_response(
            user=message.author, messages=channel_messages, conversation_context=conversation_context
        )

    await process_channel_response(
        user=message.author, channel=channel, response_data=response_data
    )
    return True

async def get_channel_messages(message: discord.Message, limit: int) -> List:
    # Collect + convert
    converted = [
        discord_message_to_message(m)
        async for m in message.channel.history(limit=limit)
    ]
    filtered = [x for x in converted if x is not None]
    filtered.reverse()  # chronological order oldest -> newest
    return filtered

async def _prepare_context_and_messages(
    message: discord.Message,
    history_store: HistoryStore,
    max_messages: int,
) -> Tuple[str, List]:
    """Add current message to history, build conversation context, fetch channel messages.

    Returns: (conversation_context, channel_messages)
    """
    channel_id = str(message.channel.id)
    history_entry = HistoryEntry(
        user_id=str(message.author.id),
        username=message.author.display_name or message.author.name,
        content=message.content,
        source="text",
        timestamp=datetime.now(),
    )
    history_store.add_message(channel_id, history_entry)

    history_entries = history_store.get_history(channel_id)
    conversation_context = create_conversation_context(
        history_entries[:-1],  # exclude current
        message.content,
        str(message.author.id),
        message.author.display_name or message.author.name,
    )
    channel_messages = await get_channel_messages(message, max_messages)
    return conversation_context, channel_messages