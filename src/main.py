import discord
import logging
from src.base import Message, Conversation
from src.constants import (
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
    EXAMPLE_CONVOS,
    ACTIVATE_THREAD_PREFX,
)
from src.utils import (
    logger,
    should_block,
)
from src import completion
from src.completion import (
    generate_completion_response,
    process_thread_response,
    process_channel_response,
)
from src import event
from src.event import (
    thread_chat,
    channel_chat,
)

logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}. Invite URL: {BOT_INVITE_URL}")
    completion.READY_BOT_NAME = client.user.name
    completion.READY_BOT_EXAMPLE_CONVOS = []
    for c in EXAMPLE_CONVOS:
        messages = []
        for m in c.messages:
            messages.append(m)
        completion.READY_BOT_EXAMPLE_CONVOS.append(Conversation(messages=messages))
    await tree.sync()

@client.event
async def on_message(message):
    try:
        # block servers not in allow list
        if should_block(guild=message.guild):
            return

        # ignore messages from the bot
        if message.author.bot:
            return

        channel = message.channel
        if not isinstance(channel, discord.Thread):
            await channel_chat(message=message,client=client)
        else:
            await thread_chat(message=message,client=client)
        
    except Exception as e:
        logger.exception(e)
        
# /thread message:
@tree.command(name="thread", description="Create a new thread for conversation")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(manage_threads=True)
async def thread_command(int: discord.Interaction, message: str):
    try:
        # only support creating thread in text channel
        if not isinstance(int.channel, discord.TextChannel):
            return

        # block servers not in allow list
        if should_block(guild=int.guild):
            return

        user = int.user
        logger.info(f"Thread command by {user} {message[:20]}")
        try:
            embed = discord.Embed(
                description=f"<@{user.id}> wants to chat! 🤖💬",
                color=discord.Color.green(),
            )
            embed.add_field(name=user.name, value=message)

            await int.response.send_message(embed=embed)
            response = await int.original_response()

        except Exception as e:
            logger.exception(e)
            await int.response.send_message(
                f"Failed to start chat {str(e)}", ephemeral=True
            )
            return

        # create the thread
        thread = await response.create_thread(
            name=f"{ACTIVATE_THREAD_PREFX} {user.name[:20]} - {message[:30]}",
            slowmode_delay=1,
            reason="gpt-bot",
            auto_archive_duration=60,
        )
        async with thread.typing():
            # fetch completion
            messages = [Message(role="system", user=user.name, content=message)]
            response_data = await generate_completion_response(
                messages=messages, user=user
            )
            # send the result
            await process_thread_response(
                user=user, thread=thread, response_data=response_data
            )
    except Exception as e:
        logger.exception(e)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )

# /message message:
@tree.command(name="message", description="Create a new message for conversation")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
async def message_command(int: discord.Interaction, message: str):
    try:
        # only support creating message in text channel
        if not isinstance(int.channel, discord.TextChannel):
            return

        # block servers not in allow list
        if should_block(guild=int.guild):
            return

        user = int.user
        logger.info(f"Message command by {user} {message[:20]}")
        
        try:
            embed = discord.Embed(
                description=f"<@{user.id}> wants to chat! 🤖💬",
                color=discord.Color.green(),
            )
            embed.add_field(name=user.name, value=message)

            await int.response.send_message(embed=embed)
            response = await int.original_response()

        except Exception as e:
            logger.exception(e)
            await int.response.send_message(
                f"Failed to start chat {str(e)}", ephemeral=True
            )
            return
 
        async with int.channel.typing():
            # fetch completion
            messages = [Message(role="system", user=user.name, content=message)]
            response_data = await generate_completion_response(
                messages=messages, user=user
            )
            # send the result
            await process_channel_response(
                user=user, channel=int.channel, response_data=response_data
            )
    except Exception as e:
        logger.exception(e)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )
    
client.run(DISCORD_BOT_TOKEN)