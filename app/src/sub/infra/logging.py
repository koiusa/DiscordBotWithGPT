import logging
import time
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import discord

from sub.constants import ALLOWED_SERVER_IDS

logger = logging.getLogger(__name__)

_LOG_START_TIME = time.time()

def should_block(guild: Optional['discord.Guild']) -> bool:
    """Check if bot should block operation for given guild."""
    if guild is None:
        # dm's not supported
        logger.info(f"DM not supported")
        return True

    if guild.id and guild.id not in ALLOWED_SERVER_IDS:
        # not allowed in this server
        logger.info(f"Guild {guild} not allowed")
        return True
    return False

_LOG_START_TIME = time.time()

def _fmt_val(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(ch in s for ch in [' ', '=', '\n', '\t']):
        s = s.replace('\n', '↵')[:400]
        return f'"{s}"'
    return s[:400]

def log_event(event: str, **fields: Any) -> None:
    """Structured event logging.
    Format: key=value space separated single line for easy grep & ingestion.
    Automatically injects uptime_s since process start.
    """
    uptime = time.time() - _LOG_START_TIME
    base: Dict[str, Any] = {"event": event, "uptime_s": f"{uptime:.1f}"}
    base.update(fields)
    parts = []
    for k, v in base.items():
        parts.append(f"{k}={_fmt_val(v)}")
    logger.info(' '.join(parts))

__all__ = ["logger", "log_event"]
