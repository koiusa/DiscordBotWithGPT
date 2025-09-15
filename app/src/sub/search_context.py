"""Search execution & context building utilities.

Responsibilities:
  - Execute web search based on a provided SearchDecision.
  - Summarize and truncate results to control token usage.
  - Provide a single function returning (search_context:str, executed:bool).

The summarization rules are aligned with completion.py previous inline logic
but centralized here so they can evolve independently.
"""
from __future__ import annotations
from typing import Tuple, List
from datetime import datetime, timezone
from sub.search_decision import SearchDecision, SearchDecisionType
from sub.base import Message
from sub.websearch import perform_web_search
from sub.websearch_cache import cache
from sub.utils import logger

# Tunable limits (could be externalized later)
_MAX_ITEMS = 3
_MAX_SNIPPET_CHARS = 220
_TOTAL_LIMIT = 1200

async def build_search_context(decision: SearchDecision, messages: List[Message]) -> Tuple[str, bool]:
    """Return (search_context, search_executed)."""
    if decision.decision != SearchDecisionType.QUERY or not decision.query:
        return "", False
    search_query = decision.query
    logger.info(f"Web search triggered for query: {search_query}")
    cache_hit = False
    search_data = cache.get(search_query)
    if search_data:
        cache_hit = True
    else:
        try:
            search_data = await perform_web_search(search_query, max_results=_MAX_ITEMS)
            cache.set(search_query, search_data)
        except Exception as e:
            logger.error(f"Web search failed before context build: {e}")
            search_data = None
    logger.info(
        f"Web search raw result: cache_hit={cache_hit} status={getattr(search_data,'status',None)} error={getattr(search_data,'error_message',None)} results={getattr(search_data,'results',None)}"
    )
    try:
        if search_data.status.name == "OK" and search_data.results:
            ts = datetime.now(timezone.utc).astimezone()
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S %Z")
            header = f"\n\n【Web検索結果（取得時刻: {ts_str}）】\n"
            parts: List[str] = []
            current_len = 0
            for i, result in enumerate(search_data.results[:_MAX_ITEMS], 1):
                title = (result.get("title") or "タイトルなし").strip()
                snippet = (result.get("snippet") or "スニペットなし").strip()
                url = (result.get("url") or "").strip()
                if len(snippet) > _MAX_SNIPPET_CHARS:
                    snippet = snippet[:_MAX_SNIPPET_CHARS] + "..."
                block = f"{i}. {title}\n{snippet}\n{url}\n"
                if current_len + len(block) > _TOTAL_LIMIT:
                    parts.append("(以降省略)\n")
                    break
                parts.append(block)
                current_len += len(block)
            ctx = header + "\n".join(parts) + "\n"
            logger.info(
                f"Search context added: {len(ctx)} characters truncated={'(省略あり)' if current_len >= _TOTAL_LIMIT else 'no'}"
            )
            return ctx, True
        else:
            ctx = f"\n\n【Web検索情報】\n「{search_query}」について検索を試行しましたが、具体的な最新情報は取得できませんでした。一般的な知識で回答してください。\n"
            logger.info("Web search returned no results, providing fallback context")
            return ctx, False
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        ctx = f"\n\n【Web検索情報】\n「{search_query}」について検索を試行しましたが、技術的な問題により最新情報を取得できませんでした。\n"
        return ctx, False

__all__ = ["build_search_context"]
