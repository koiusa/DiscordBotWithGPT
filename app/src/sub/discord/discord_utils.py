import discord
from typing import Optional, List
from sub.core.base import Message
from sub.constants import MAX_CHARS_PER_REPLY_MSG, INACTIVATE_THREAD_PREFIX
from sub.infra.logging import logger

def discord_message_to_message(message: discord.Message) -> Optional[Message]:
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
    interaction_message: discord.Message, last_message: discord.Message, bot_id: str
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

__all__ = [
    'discord_message_to_message',
    'split_into_shorter_messages',
    'is_last_message_stale',
    'close_thread'
]
