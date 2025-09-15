import discord
import logging
from sub.completion import (
    generate_completion_response,
    process_thread_response,
    process_channel_response,
)
import asyncio
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
from datetime import datetime

async def thread_chat(message, client: discord.Client, history_store: HistoryStore) -> bool:
        logger.info(f"thread_chat called")
        channel = message.channel     
        # ignore threads not created by the bot
        thread = channel
        if thread.owner_id != client.user.id:
            return False

        # ignore threads that are archived locked or title is not what we want
        if (
            thread.archived
            or thread.locked
            or not thread.name.startswith(ACTIVATE_THREAD_PREFX)
        ):
            # ignore this thread
            return False

        if thread.message_count > MAX_THREAD_MESSAGES:
            # too many messages, no longer going to reply
            await close_thread(thread=thread)
            return False
        
        # wait a bit in case user has more messages
        if SECONDS_DELAY_RECEIVING_MSG > 0:
            await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
            if is_last_message_stale(
                interaction_message=message,
                last_message=thread.last_message,
                bot_id=client.user.id,
            ):
                # there is another message, so ignore this one
                return False

        logger.info(
            f"Thread message to process - {message.author}: {message.content[:50]} - {thread.name} {thread.jump_url}"
        )

        # Add current message to history store (source: "text")
        channel_id = str(message.channel.id)
        history_entry = HistoryEntry(
            user_id=str(message.author.id),
            username=message.author.display_name or message.author.name,
            content=message.content,
            source="text",
            timestamp=datetime.now()
        )
        history_store.add_message(channel_id, history_entry)

        # Get conversation history for context
        history_entries = history_store.get_history(channel_id)
        
        # Create conversation context with user identification
        conversation_context = create_conversation_context(
            history_entries[:-1],  # Exclude current message as it's already included
            message.content,
            str(message.author.id),
            message.author.display_name or message.author.name
        )

        channel_messages = await get_channel_messages(message, MAX_THREAD_MESSAGES)

        # generate the response
        async with thread.typing():
            response_data = await generate_completion_response(
                user=message.author, messages=channel_messages, conversation_context=conversation_context
            )

        if is_last_message_stale(
            interaction_message=message,
            last_message=thread.last_message,
            bot_id=client.user.id,
        ):
            # there is another message and its not from us, so ignore this response
            return False

        # send response
        await process_thread_response(
            user=message.author, thread=thread, response_data=response_data
        )
        
        return True

async def channel_chat(message, client: discord.Client, history_store: HistoryStore) -> bool:
    logger.info(f"channel_chat called")
    channel = message.channel 
    # wait a bit in case user has more messages
    if SECONDS_DELAY_RECEIVING_MSG > 0:
        await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
        if is_last_message_stale(
            interaction_message=message,
            last_message=channel.last_message,
            bot_id=client.user.id,
        ):
            # there is another message, so ignore this one
            return False     

    logger.info(
            f"Channel message to process - {message.author}: {message.content[:50]} - {channel.name} {channel.jump_url}"
    )
    
    # Add current message to history store (source: "text")
    channel_id = str(message.channel.id)
    history_entry = HistoryEntry(
        user_id=str(message.author.id),
        username=message.author.display_name or message.author.name,
        content=message.content,
        source="text",
        timestamp=datetime.now()
    )
    history_store.add_message(channel_id, history_entry)

    # Get conversation history for context
    history_entries = history_store.get_history(channel_id)
    
    # Create conversation context with user identification
    conversation_context = create_conversation_context(
        history_entries[:-1],  # Exclude current message as it's already included
        message.content,
        str(message.author.id),
        message.author.display_name or message.author.name
    )
     
    channel_messages = await get_channel_messages(message, MAX_CHANNEL_MESSAGES)
     
     # generate the response
    async with channel.typing():
            response_data = await generate_completion_response(
                user=message.author, messages=channel_messages, conversation_context=conversation_context
                        )
     
    # send response
    await process_channel_response(
            user=message.author, channel=channel, response_data=response_data
    )

    return True

async def get_channel_messages(message, limit) -> []:
     channel_messages = [
            discord_message_to_message(message)
            async for message in message.channel.history(limit=limit)
        ]
     channel_messages = [x for x in channel_messages if x is not None]
     channel_messages.reverse()
     return channel_messages