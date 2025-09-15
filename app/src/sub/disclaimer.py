"""Disclaimer removal utilities.

Responsibility:
  - Provide central patterns for stale knowledge / realtime denial disclaimers
  - Offer a sanitize_reply function that removes those patterns when web search
    results are already injected, avoiding redundant apologies.

Design:
  - Patterns kept relatively conservative to avoid stripping legitimate content.
  - Collapse excessive blank lines after removal.
  - If content becomes empty, return fallback hint.
"""
from __future__ import annotations
from typing import List, Pattern
import re
import os
import datetime
from sub.utils import logger

def _current_year_range_patterns(year: int) -> List[str]:
    # Allow dynamic adaptation to new years without code change (e.g., 2025, 2026)
    # Accept mentions like 2024年/2025年 etc.
    return [
        rf"(私|このモデル|わたし|i|this model).{{0,25}}(知識|学習|トレーニング|training|knowledge).{{0,30}}(20(2\d|3\d)|{year}|{year-1})(年|年頃|年まで|まで|時点)?",
    ]

def _base_japanese_patterns() -> List[str]:
    return [
        r"現在、?私はインターネットからリアルタイムで(最新)?(ニュース)?を取得できません",
        r"(最新|リアルタイム).{0,10}アクセス(できません|できない)",
        r"リアルタイム.{0,15}(提供|取得)(できません|できない)",
    ]

def _base_english_patterns() -> List[str]:
    return [
        r"(i|we) (do not|don't|can't) (have )?(real[- ]?time|live) (access|information)",
        r"(as of|my knowledge (cut|is)|knowledge cutoff).{0,30}(20\d\d)",
        r"my training (data|knowledge).{0,40}(only|up to|until)",
    ]

def build_patterns() -> List[Pattern]:
    year = datetime.datetime.utcnow().year
    patterns: List[str] = []
    # Japanese core
    patterns.extend(_base_japanese_patterns())
    # Dynamic year range disclaimers
    patterns.extend(_current_year_range_patterns(year))
    # English (optional)
    if os.environ.get("DISCLAIMER_ENABLE_ENGLISH", "1") not in ("0", "false", "False"):
        patterns.extend(_base_english_patterns())
    # Extra patterns from env (comma-separated)
    extra = os.environ.get("DISCLAIMER_EXTRA_PATTERNS")
    if extra:
        for raw in extra.split(","):
            raw = raw.strip()
            if raw:
                patterns.append(raw)
    compiled: List[Pattern] = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error as e:
            logger.warning(f"[disclaimer] invalid_pattern skipped pattern='{p}' error={e}")
    logger.info(f"[disclaimer] compiled_patterns count={len(compiled)}")
    return compiled

_COMPILED_PATTERNS = build_patterns()

_FALLBACK_TEXT = "(検索結果を踏まえて最新と思われる要点を上に示しました。必要なら追加で質問してください。)"

def sanitize_reply(reply: str, search_executed: bool) -> str:
    if not (search_executed and reply):
        return reply
    cleaned = reply
    removed_any = False
    for reg in _COMPILED_PATTERNS:
        new_cleaned = reg.sub("", cleaned)
        if new_cleaned != cleaned:
            removed_any = True
            cleaned = new_cleaned
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if removed_any:
        logger.info("reply_disclaimer_removed=1")
        return cleaned if cleaned else _FALLBACK_TEXT
    return cleaned

__all__ = ["sanitize_reply"]