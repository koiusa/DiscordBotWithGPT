"""Token estimation utilities.
Prefer tiktoken if available; otherwise fallback to simple heuristic.
"""
from __future__ import annotations
from typing import List, Dict, Any, Union
from sub.utils import logger

try:
    import tiktoken  # type: ignore
    _HAS_TIKTOKEN = True
except Exception:
    _HAS_TIKTOKEN = False

# Default model encoding mapping fallback
_DEFAULT_MODEL = "gpt-3.5-turbo"

def estimate_tokens_from_messages(messages: List[Dict[str, Any]], model: str = _DEFAULT_MODEL) -> int:
    if _HAS_TIKTOKEN:
        try:
            enc = tiktoken.encoding_for_model(model)
        except Exception:
            enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, list):
                # vision形式を単純連結
                parts = []
                for c in content:
                    if isinstance(c, dict):
                        if c.get("type") == "text":
                            parts.append(c.get("text", ""))
                        elif c.get("type") == "image_url":
                            parts.append("[image]")
                content = "\n".join(parts)
            total += len(enc.encode(str(content))) + 4  # role/name overheadざっくり
        return total + 2  # assistant priming
    # Heuristic fallback: 1 token ~= 4 chars
    char_sum = 0
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    char_sum += len(c.get("text", ""))
                elif isinstance(c, dict) and c.get("type") == "image_url":
                    char_sum += 20  # placeholder cost
        else:
            char_sum += len(str(content))
    approx = int(char_sum / 4)
    return approx

__all__ = ["estimate_tokens_from_messages"]
