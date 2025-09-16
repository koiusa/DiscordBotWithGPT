from dotenv import load_dotenv
import os
import dacite
import yaml
from typing import Dict, List
from sub.core.base import Config

load_dotenv()

# load config.yaml
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG: Config = dacite.from_dict(
    Config, yaml.safe_load(open(os.path.join(SCRIPT_DIR, "config.yaml"), "r"))
)

BOT_NAME = CONFIG.name
EXAMPLE_CONVOS = CONFIG.example_conversations
OPENAI_MODEL = CONFIG.model
OPENAI_PROMPT_TOKEN_COST = float(os.environ.get("OPENAI_PROMPT_TOKEN_COST", "0.0"))  # USD per 1k tokens
OPENAI_COMPLETION_TOKEN_COST = float(os.environ.get("OPENAI_COMPLETION_TOKEN_COST", "0.0"))  # USD per 1k tokens

# Conversation summarization thresholds (heuristic)
SUMMARY_TRIGGER_PROMPT_TOKENS = int(os.environ.get("SUMMARY_TRIGGER_PROMPT_TOKENS", "2800"))
SUMMARY_TARGET_REDUCTION_RATIO = float(os.environ.get("SUMMARY_TARGET_REDUCTION_RATIO", "0.5"))  # reduce to 50% of chars heuristically
SUMMARY_MAX_SOURCE_CHARS = int(os.environ.get("SUMMARY_MAX_SOURCE_CHARS", "8000"))  # upper bound to attempt summarization
SUMMARY_MODEL = os.environ.get("SUMMARY_MODEL", OPENAI_MODEL)

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
DISCORD_CLIENT_ID = os.environ["DISCORD_CLIENT_ID"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
PERMISSIONS = os.environ["PERMISSIONS"]

ALLOWED_SERVER_IDS: List[int] = []
server_ids = os.environ["ALLOWED_SERVER_IDS"].split(",")
for s in server_ids:
    ALLOWED_SERVER_IDS.append(int(s))

SERVER_TO_MODERATION_CHANNEL: Dict[int, int] = {}
server_channels = os.environ.get("SERVER_TO_MODERATION_CHANNEL", "").split(",")
for s in server_channels:
    values = s.split(":")
    SERVER_TO_MODERATION_CHANNEL[int(values[0])] = int(values[1])

# Send Messages, Create Public Threads, Send Messages in Threads, Manage Messages, Manage Threads, Read Message History, Use Slash Command
BOT_INVITE_URL = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&permissions={PERMISSIONS}&scope=bot"

MAX_CHANNEL_MESSAGES = 10
MAX_THREAD_MESSAGES = 50
ACTIVATE_THREAD_PREFX = "💬✅"
INACTIVATE_THREAD_PREFIX = "💬❌"
MAX_CHARS_PER_REPLY_MSG = (
    1500  # discord has a 2k limit, we just break message into 1.5k
)
SECONDS_DELAY_RECEIVING_MSG = (
    3  # give a delay for the bot to respond so it can catch multiple messages
)

# History management for user identification
HISTORY_MAX_ITEMS = int(os.environ.get("HISTORY_MAX_ITEMS", "30"))

# Respond without explicit mention in normal channel messages (0/1). Default=1 (enabled)
RESPOND_WITHOUT_MENTION = int(os.environ.get("RESPOND_WITHOUT_MENTION", "1"))

# Simple per-user rate limiting (only applied to non-addressed fallback path)
RATE_LIMIT_WINDOW_SEC = int(os.environ.get("RATE_LIMIT_WINDOW_SEC", "30"))  # sliding window seconds
RATE_LIMIT_MAX_EVENTS = int(os.environ.get("RATE_LIMIT_MAX_EVENTS", "5"))   # max messages per user per window
