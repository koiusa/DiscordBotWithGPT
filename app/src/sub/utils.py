from sub.constants import (
    ALLOWED_SERVER_IDS,
)
import logging

logger = logging.getLogger(__name__)
from sub.base import Message
from discord import Message as DiscordMessage
from typing import Optional, List
import discord

from sub.constants import MAX_CHARS_PER_REPLY_MSG, INACTIVATE_THREAD_PREFIX


def discord_message_to_message(message: DiscordMessage) -> Optional[Message]:
    if (
        message.type == discord.MessageType.thread_starter_message
        and message.reference.cached_message
        and len(message.reference.cached_message.embeds) > 0
        and len(message.reference.cached_message.embeds[0].fields) > 0
    ):
        field = message.reference.cached_message.embeds[0].fields[0]
        if field.value:
            return Message(role="system", user=field.name, content=field.value)
    else:
        # Vision対応: 画像がある場合はcontentをリストで格納
        if message.content or message.attachments:
            role = "assistant" if message.author.bot else "user"
            if message.attachments:
                content_list = []
                if message.content:
                    content_list.append({"type": "text", "text": message.content})
                for attachment in message.attachments:
                    if hasattr(attachment, "content_type") and attachment.content_type and attachment.content_type.startswith("image/"):
                        content_list.append({
                            "type": "image_url",
                            "image_url": {"url": attachment.url}
                        })
                return Message(role=role, user=message.author.name, content=content_list)
            else:
                return Message(role=role, user=message.author.name, content=message.content)
    return None


def split_into_shorter_messages(message: str) -> List[str]:
    return [
        message[i : i + MAX_CHARS_PER_REPLY_MSG]
        for i in range(0, len(message), MAX_CHARS_PER_REPLY_MSG)
    ]


def is_last_message_stale(
    interaction_message: DiscordMessage, last_message: DiscordMessage, bot_id: str
) -> bool:
    return (
        last_message
        and last_message.id != interaction_message.id
        and last_message.author
        and last_message.author.id != bot_id
    )


async def close_thread(thread: discord.Thread):
    await thread.edit(name=INACTIVATE_THREAD_PREFIX)
    await thread.send(
        embed=discord.Embed(
            description="**Thread closed** - Context limit reached, closing...",
            color=discord.Color.blue(),
        )
    )
    await thread.edit(archived=True, locked=True)


def should_block(guild: Optional[discord.Guild]) -> bool:
    if guild is None:
        # dm's not supported
        logger.info(f"DM not supported")
        return True

    if guild.id and guild.id not in ALLOWED_SERVER_IDS:
        # not allowed in this server
        logger.info(f"Guild {guild} not allowed")
        return True
    return False
