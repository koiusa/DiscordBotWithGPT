#!/usr/bin/env python3
import os
import sys
import discord
import logging
import asyncio
from typing import List, Tuple

# debugpyによるリモートデバッグ有効化
try:
    import debugpy
    debugpy.listen(("0.0.0.0", 5679))
    print("debugpy is listening on port 5679")
except ImportError:
    pass

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from sub.base import Message, Conversation
from sub.constants import (
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
    EXAMPLE_CONVOS,
    ACTIVATE_THREAD_PREFX,
    HISTORY_MAX_ITEMS,
    RESPOND_WITHOUT_MENTION,
    RATE_LIMIT_WINDOW_SEC,
    RATE_LIMIT_MAX_EVENTS,
)
from sub.utils import (
    logger,
    should_block,
    log_event,
)
from sub import completion
from sub.completion import (
    generate_completion_response,
    process_thread_response,
    process_channel_response,
)
from sub import event
from sub.event import (
    thread_chat,
    channel_chat,
)
from sub.history_store import HistoryStore
from sub.websearch import perform_web_search, format_search_results
from sub.dedup import GLOBAL_MESSAGE_DEDUP
from sub.rate_limit import build_rate_limiter


logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.message_content = True  # メッセージ本文取得
intents.guilds = True
intents.members = False
intents.typing = False
log_event("startup_intents", message_content=intents.message_content, guilds=intents.guilds)

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# Initialize global history store
history_store = HistoryStore(max_items=HISTORY_MAX_ITEMS)
rate_limiter = build_rate_limiter(RATE_LIMIT_WINDOW_SEC, RATE_LIMIT_MAX_EVENTS)

@client.event
async def on_ready():
    log_event("login", user=str(client.user), invite_url=BOT_INVITE_URL)
    log_event("guild_connected", guild_count=len(client.guilds))
    completion.READY_BOT_NAME = client.user.name
    completion.READY_BOT_EXAMPLE_CONVOS = [Conversation(messages=[m for m in c.messages]) for c in EXAMPLE_CONVOS]
    await tree.sync()
    schedule_background_tasks()

async def heartbeat_task():
    while True:
        try:
            latency_ms = client.latency * 1000 if client.latency else None
            log_event("heartbeat", latency_ms=f"{latency_ms:.1f}" if latency_ms is not None else None)
        except Exception as e:
            logger.warning(f"[health] heartbeat error: {e}")
        await asyncio.sleep(30)

def schedule_background_tasks():
    # Heartbeat
    client.loop.create_task(heartbeat_task())
    # Connectivity quick test
    async def _quick_test():
        try:
            from sub.websearch import perform_web_search
            result = await perform_web_search("diagnostic connectivity", max_results=1)
            log_event("websearch_connectivity", status=result.status.name, error=result.error_message)
        except Exception as e:
            logger.warning(f"[diag] websearch_connectivity failed error={e}")
    client.loop.create_task(_quick_test())

def _is_message_addressed(msg: discord.Message, bot_user: discord.User) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    # direct mention
    if bot_user in msg.mentions:
        reasons.append("direct_mention")
    # role mention
    try:
        if msg.guild and hasattr(msg.guild, "me") and msg.role_mentions:
            bot_roles = {r.id for r in msg.guild.me.roles}
            for r in msg.role_mentions:
                if r.id in bot_roles:
                    reasons.append("role_mention")
                    break
    except Exception:
        pass
    # name prefix
    try:
        content_norm = msg.content.lstrip()
        bot_name = bot_user.name if bot_user else ""
        if bot_name and content_norm.lower().startswith(bot_name.lower()):
            after = content_norm[len(bot_name):]
            if after == "" or after[:1] in [":", "：", " ", "　", ",", "、"]:
                reasons.append("name_prefix")
    except Exception:
        pass
    # reply
    try:
        if msg.reference and getattr(msg.reference, "resolved", None):
            ref = msg.reference.resolved
            if getattr(ref, "author", None) and ref.author.id == bot_user.id:
                reasons.append("reply")
    except Exception:
        pass
    return (len(reasons) > 0, reasons)

@client.event
async def on_message(message):
    try:
        log_event("on_message", author_id=getattr(message.author,'id',None), is_bot=getattr(message.author,'bot',None), channel_id=getattr(message.channel,'id',None), preview=(message.content[:40] if hasattr(message,'content') else None))
        # Duplicate suppression (e.g., Discord client resend / network glitch)
        mid = getattr(message, 'id', None)
        if mid is not None:
            if GLOBAL_MESSAGE_DEDUP.seen(mid):
                log_event("duplicate_skip", message_id=mid)
                return
            GLOBAL_MESSAGE_DEDUP.mark(mid)
        # block servers not in allow list
        if should_block(guild=message.guild):
            log_event("guild_blocked", guild_id=getattr(message.guild,'id',None))
            return

        # ignore messages from the bot
        if message.author.bot:
            log_event("ignore_bot_message", author_id=getattr(message.author,'id',None))
            return

        # ignore messages from self
        if message.author == client.user:
           log_event("ignore_self_message", author_id=getattr(message.author,'id',None))
           return

        channel = message.channel
        if isinstance(channel, discord.Thread):
            log_event("thread_message", author_id=getattr(message.author,'id',None), thread_id=getattr(channel,'id',None))
            await thread_chat(message=message, client=client, history_store=history_store)
            return

        addressed, reasons = _is_message_addressed(message, client.user)
        log_event("address_check", addressed=addressed, reasons=','.join(reasons) if reasons else None, author_id=getattr(message.author,'id',None), preview=message.content[:60])
        if not addressed:
            if RESPOND_WITHOUT_MENTION:
                # apply simple per-user rate limit to avoid spam
                uid = getattr(message.author, 'id', None)
                if uid is not None and not rate_limiter.allow(uid):
                    log_event("rate_limit_drop", user_id=uid, window_s=RATE_LIMIT_WINDOW_SEC, max_events=RATE_LIMIT_MAX_EVENTS)
                    return
                log_event("fallback_respond", reason="respond_without_mention")
            else:
                return
        log_event("address_accept", author_id=getattr(message.author,'id',None), reasons=','.join(reasons) if reasons else None)
        await channel_chat(message=message, client=client, history_store=history_store)
        
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
        log_event("thread_command", user_id=getattr(user,'id',None))
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
        log_event("message_command", user_id=getattr(user,'id',None))
        
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

# /websearch query:
@tree.command(name="websearch", description="Search the web for current information")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
async def websearch_command(int: discord.Interaction, query: str):
    try:
        # block servers not in allow list
        if should_block(guild=int.guild):
            return

        user = int.user
        log_event("websearch_command", user_id=getattr(user,'id',None), query_preview=query[:50])
        
        # Acknowledge the command immediately
        await int.response.defer()
        
        try:
            # Perform web search
            search_data = await perform_web_search(query, max_results=5)
            
            # Format results for Discord
            formatted_results = format_search_results(search_data, query)
            
            # Split message if too long for Discord (2000 char limit)
            if len(formatted_results) > 1900:
                # Split into chunks
                chunks = []
                current_chunk = ""
                lines = formatted_results.split('\n')
                
                for line in lines:
                    if len(current_chunk + line + '\n') > 1900:
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = line + '\n'
                        else:
                            # Single line too long, truncate it
                            chunks.append(line[:1900] + "...")
                            current_chunk = ""
                    else:
                        current_chunk += line + '\n'
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Send first chunk as follow-up
                await int.followup.send(chunks[0])
                
                # Send remaining chunks
                for chunk in chunks[1:]:
                    await int.followup.send(chunk)
            else:
                # Send as single message
                await int.followup.send(formatted_results)
                
        except Exception as e:
            logger.exception(e)
            await int.followup.send(
                f"❌ **検索エラー**: ウェブ検索中にエラーが発生しました: {str(e)}"
            )
            
    except Exception as e:
        logger.exception(e)
        try:
            await int.response.send_message(
                f"❌ **エラー**: コマンド実行中にエラーが発生しました: {str(e)}", ephemeral=True
            )
        except:
            # If response already sent, use followup
            await int.followup.send(
                f"❌ **エラー**: コマンド実行中にエラーが発生しました: {str(e)}"
            )

@tree.command(name="diag", description="診断情報を表示 (latency / guild / websearch quick check)")
@discord.app_commands.checks.has_permissions(send_messages=True)
async def diag_command(int: discord.Interaction):
    try:
        await int.response.defer(thinking=True, ephemeral=True)
        latency_ms = client.latency * 1000 if client.latency else None
        guild_count = len(client.guilds)
        # quick websearch test
        from sub.websearch import perform_web_search
        test_result = await perform_web_search("diagnostic ping", max_results=1)
        status = test_result.status.name
        result_line = "OK" if (test_result.results and len(test_result.results) > 0) else (test_result.error_message or "NO_RESULT")
        content = (
            f"Latency: {latency_ms:.1f}ms\n"
            f"Guilds: {guild_count}\n"
            f"WebSearch: status={status} detail={result_line[:120]}\n"
            f"Intents: message_content={intents.message_content} guilds={intents.guilds}"
        )
        await int.followup.send(content, ephemeral=True)
    except Exception as e:
        logger.exception(e)
        try:
            await int.followup.send(f"診断失敗: {e}", ephemeral=True)
        except Exception:
            pass
    
client.run(DISCORD_BOT_TOKEN)
