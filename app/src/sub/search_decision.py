"""Search decision & query optimization utilities.

Responsibilities:
- SearchConfig: configuration for search triggering
- Datetime direct answer detection
- Scoring-based decision whether to perform web search
- Query cleanup & optimization

Public API:
  should_perform_web_search(messages: List[Message], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> Optional[str]
    Returns one of:
      * direct datetime answer text (already formatted for reply)
      * optimized search query
      * None (no search needed)

Internal helpers kept private by underscore naming.
"""
from __future__ import annotations
from typing import List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import re
import datetime
from sub.base import Message
import os
from sub.utils import logger, log_event

# Enrich keywords used during optimization to inject recency tokens
_QUERY_ENRICH_KEYWORDS = ["株価", "為替", "ニュース", "速報", "物価", "金利"]

class SearchConfig:
    def __init__(
        self,
        search_patterns: List[str],
        question_words: List[str],
        factual_keywords: List[str],
        enrich_keywords: List[str],
        min_score: int = 2,
        pattern_score: int = 2,
        question_score: int = 1,
        factual_score: int = 1,
    ):
        self.search_patterns = search_patterns
        self.question_words = question_words
        self.factual_keywords = factual_keywords
        self.enrich_keywords = enrich_keywords
        self.min_score = min_score
        self.pattern_score = pattern_score
        self.question_score = question_score
        self.factual_score = factual_score

_CURRENT_YEAR = datetime.datetime.now().year
_PREV_YEAR = _CURRENT_YEAR - 1

_AGGRESSIVE = os.environ.get("SEARCH_AGGRESSIVE_MODE", "0") in ("1", "true", "True")

DEFAULT_SEARCH_CONFIG = SearchConfig(
    search_patterns=[
        r"最新.+?(情報|データ|状況)",
        r"今日.+?ニュース",
        r"最近.+?(話題|トレンド)",
        r".+?(について)?調べて",
        r".+?の最新",
        r".+?はいつ",
        r".+?の(値段|価格|相場)",
        r".+?の評判",
        r".+?のレビュー",
        r".+?天気",
        r".+?株価",
        r".+?為替",
        r".+?の速報",
        r".+?の開催",
        r".+?のイベント",
    ],
    question_words=["何", "いつ", "どこ", "だれ", "どう", "なぜ", "どの", "どんな"],
    factual_keywords=[str(_PREV_YEAR), str(_CURRENT_YEAR), "今年", "現在", "最新", "今", "最近"],
    enrich_keywords=_QUERY_ENRICH_KEYWORDS,
    min_score=1 if _AGGRESSIVE else 2,
)

def _detect_datetime_direct_answer(text: str) -> Optional[str]:
    import datetime
    lower = text.lower()
    patterns = [
        r"今日[は]?何日", r"現在の日時", r"今[は]?何時", r"今日の日付", r"本日の日付", r"今日の曜日", r"今の時間", r"現在の時間"
    ]
    if any(re.search(p, lower) for p in patterns):
        now = datetime.datetime.now()
        try:
            import pytz
            jst = pytz.timezone("Asia/Tokyo")
            now = now.astimezone(jst)
        except Exception:
            pass
        date_str = now.strftime("%Y年%m月%d日 %H:%M")
        if any(k in lower for k in ["何日", "日付", "今日"]):
            return f'本日は「{now.strftime("%Y年%m月%d日") }」です。'
        if any(k in lower for k in ["何時", "時間", "現在"]):
            return f'現在の時刻は「{now.strftime("%H:%M") }」です。'
        return f'現在日時は「{date_str}」です。'
    return None

def _evaluate_search_need(content: str, config: SearchConfig) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    for pat in config.search_patterns:
        if re.search(pat, content):
            score += config.pattern_score
            reasons.append(f"pattern:{pat}")
            break
    if any(w in content for w in config.question_words):
        score += config.question_score
        reasons.append("question_form")
    if any(k in content for k in config.factual_keywords):
        score += config.factual_score
        reasons.append("factual_keyword")
    return score, reasons

def _clean_search_query(query: str) -> str:
    query = re.sub(r"<@!?\d+>", "", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query or "最新ニュース"

def _optimize_query(query: str, enrich_keywords: List[str]) -> str:
    original = query
    q = re.sub(r"<@!?.+?>", " ", query)
    q = re.sub(r"[（）「」『』【】［］]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    lowered = q.lower()
    years_tokens = [str(_CURRENT_YEAR), str(_PREV_YEAR)]
    needs_time_boost = not any(k in lowered for k in years_tokens + ["最新", "現在"]) and len(q) < 60
    if any(k in q for k in enrich_keywords) and needs_time_boost:
        q = f"{q} 現在 {_CURRENT_YEAR} 最新"
    if len(q) > 120:
        q = q[:120]
    if q != original:
        log_event("query_opt", before=original, after=q)
    return q

class SearchDecisionType(Enum):
    NONE = "none"
    QUERY = "query"
    DATETIME_ANSWER = "datetime_answer"

@dataclass
class SearchDecision:
    decision: SearchDecisionType
    query: Optional[str] = None
    direct_answer: Optional[str] = None
    score: int = 0
    reasons: List[str] = None

def should_perform_web_search(messages: List[Message], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> SearchDecision:
    user_messages = [m for m in messages if m.role == "user"]
    if not user_messages:
        return SearchDecision(SearchDecisionType.NONE, score=0, reasons=[])

    latest_raw = user_messages[-1].content
    latest_lower = latest_raw.lower()

    dt_answer = _detect_datetime_direct_answer(latest_lower)
    if dt_answer:
        log_event("search_decision", type=SearchDecisionType.DATETIME_ANSWER.value, reasons='datetime_pattern')
        return SearchDecision(
            decision=SearchDecisionType.DATETIME_ANSWER,
            direct_answer=dt_answer,
            score=0,
            reasons=["datetime_pattern"],
        )

    score, reasons = _evaluate_search_need(latest_lower, config)
    # Aggressive mode: 追加ヒューリスティック
    if _AGGRESSIVE and score == 0:
        # 質問文疑似: 末尾が「?」 / 日本語の「？」 / '教えて' / 'とは'
        if any(latest_lower.endswith(suf) for suf in ["?", "？"]) or any(k in latest_lower for k in ["教えて", "とは", "まとめて", "一覧"]):
            score = 1
            reasons.append("aggressive_form")
    if score < config.min_score:
        log_event("search_decision", type=SearchDecisionType.NONE.value, score=score, reasons=','.join(reasons) if reasons else None)
        return SearchDecision(SearchDecisionType.NONE, score=score, reasons=reasons)

    query = _clean_search_query(latest_raw)
    query = _optimize_query(query, config.enrich_keywords)
    log_event("search_decision", type=SearchDecisionType.QUERY.value, score=score, reasons=','.join(reasons) if reasons else None, query=query[:120])
    return SearchDecision(
        decision=SearchDecisionType.QUERY,
        query=query[:100],
        score=score,
        reasons=reasons,
    )