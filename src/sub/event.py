import discord
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

async def thread_chat(message, client: discord.Client) -> bool:
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

        channel_messages = await get_channel_messages(message, MAX_THREAD_MESSAGES)

        # generate the response
        async with thread.typing():
            response_data = await generate_completion_response(
                user=message.author, messages=channel_messages 
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

async def channel_chat(message, client: discord.Client) -> bool:
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
     
     channel_messages = await get_channel_messages(message, MAX_CHANNEL_MESSAGES)
     
     # generate the response
     async with channel.typing():
            response_data = await generate_completion_response(
                user=message.author, messages=channel_messages 
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