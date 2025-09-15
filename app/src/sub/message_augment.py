from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from sub.base import Message
from sub.utils import logger

# 将来的に設定化したい値 (必要なら環境変数化)
DEFAULT_MAX_HISTORY_CHARS = 4000  # 会話履歴インジェクション最大長
DEFAULT_CONTEXT_HEADER = "会話履歴:"  # 会話履歴前に付与
INJECTED_SEARCH_GUIDELINE_JA = (
    "最新ニュース系の質問に対して、上に最新検索結果がある場合は『リアルタイム取得できません』等の定型免責を繰り返さず、検索結果と一般知識を統合し簡潔で正確な日本語要約を提供してください。"
)

@dataclass
class AugmentMeta:
    conversation_truncated: bool
    conversation_original_chars: int
    conversation_used_chars: int
    search_injected: bool
    guideline_injected: bool
    added_system: bool

@dataclass
class AugmentResult:
    messages: List[Dict[str, Any]]
    meta: AugmentMeta


def _truncate_conversation(text: str, limit: int) -> tuple[str, bool]:
    if not text:
        return "", False
    if len(text) <= limit:
        return text, False
    # 末尾(最新)を優先保持し、先頭を切り捨て
    ellipsis = "\n...(前方省略)...\n"
    keep = limit - len(ellipsis)
    truncated = text[-keep:]
    return ellipsis + truncated, True


def augment_messages(
    messages: List[Message],
    conversation_context: Optional[str] = None,
    search_context: Optional[str] = None,
    search_executed: bool = False,
    max_history_chars: int = DEFAULT_MAX_HISTORY_CHARS,
) -> AugmentResult:
    """汎用メッセージ拡張。
    - 会話履歴/検索結果/ガイドラインを既存 system に追記 (なければ作成)。
    - 会話履歴は長い場合後方優先トリミング。
    - すでに同一ブロックが存在する場合は重複注入を避ける。
    """
    rendered = [m.render() for m in messages]

    truncated = False
    used_chars = 0
    original_chars = len(conversation_context) if conversation_context else 0
    conversation_block = ""
    if conversation_context:
        truncated_text, truncated = _truncate_conversation(conversation_context, max_history_chars)
        used_chars = len(truncated_text)
        conversation_block = f"{DEFAULT_CONTEXT_HEADER}\n{truncated_text}" if truncated_text else ""

    # インジェクトするパーツを順序で蓄積
    parts: List[str] = []
    if conversation_block:
        parts.append(conversation_block)
    if search_context:
        parts.append(search_context)
    guideline_injected = False
    if search_executed:
        parts.append(INJECTED_SEARCH_GUIDELINE_JA)
        guideline_injected = True

    if not parts:
        return AugmentResult(rendered, AugmentMeta(False, original_chars, used_chars, bool(search_context), False, False))

    combined_block = "\n".join(parts)

    # 既存 system メッセージ探索
    system_found = None
    for msg in rendered:
        if msg.get("role") == "system":
            system_found = msg
            break

    def _already_contains(target: str, block: str) -> bool:
        return block.strip() in target

    added_system = False
    if system_found:
        # 重複挿入チェック（簡易: 完全一致含有）
        if not _already_contains(system_found.get("content", ""), conversation_block):
            # 末尾に追記
            system_found["content"] = (system_found.get("content", "").rstrip() + "\n\n" + combined_block).strip()
        else:
            logger.info("augment: skip duplicate conversation_block")
    else:
        rendered.insert(0, {"role": "system", "content": combined_block})
        added_system = True

    meta = AugmentMeta(
        conversation_truncated=truncated,
        conversation_original_chars=original_chars,
        conversation_used_chars=used_chars,
        search_injected=bool(search_context),
        guideline_injected=guideline_injected,
        added_system=added_system,
    )

    logger.info(
        "augment_meta truncated=%s orig_chars=%d used_chars=%d search_injected=%s guideline=%s added_system=%s",
        meta.conversation_truncated,
        meta.conversation_original_chars,
        meta.conversation_used_chars,
        meta.search_injected,
        meta.guideline_injected,
        meta.added_system,
    )

    return AugmentResult(rendered, meta)
