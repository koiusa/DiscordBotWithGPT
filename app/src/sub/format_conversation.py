from typing import List
from .history_store import HistoryEntry


def format_conversation_history(history_entries: List[HistoryEntry], max_chars: int = 2000) -> str:
    """
    Format conversation history for GPT prompt in the format:
    username(userId): content
    
    Args:
        history_entries: List of HistoryEntry objects in chronological order
        max_chars: Maximum character limit for the formatted output (for token control)
    
    Returns:
        Formatted conversation history string
    """
    if not history_entries:
        return ""
    
    formatted_lines = []
    
    # Process from most recent to oldest to prioritize recent messages
    for entry in reversed(history_entries):
        # Format: username(userId): content
        formatted_line = f"{entry.username}({entry.user_id}): {entry.content}"
        
        # Add to the beginning of the list to maintain chronological order
        formatted_lines.insert(0, formatted_line)
        
        # Check if the current result exceeds character limit
        current_result = "\n".join(formatted_lines)
        if len(current_result) > max_chars:
            # Remove the line we just added and stop
            formatted_lines.pop(0)
            break
    
    return "\n".join(formatted_lines)


def create_conversation_context(history_entries: List[HistoryEntry], current_message: str, current_user_id: str, current_username: str) -> str:
    """
    Create full conversation context including history and current message
    
    Args:
        history_entries: Previous conversation history
        current_message: The current message content
        current_user_id: Current message author's user ID
        current_username: Current message author's username
    
    Returns:
        Complete conversation context for GPT
    """
    history_text = format_conversation_history(history_entries)
    
    # Add current message in the same format
    current_msg_formatted = f"{current_username}({current_user_id}): {current_message}"
    
    if history_text:
        return f"{history_text}\n{current_msg_formatted}"
    else:
        return current_msg_formatted