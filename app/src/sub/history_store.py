from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class HistoryEntry:
    """Represents a single message in conversation history"""
    user_id: str
    username: str  # display name
    content: str
    source: str  # "text" or future "voice"
    timestamp: datetime


class HistoryStore:
    """Manages conversation history per channel with circular buffer"""
    
    def __init__(self, max_items: int = 30):
        self.max_items = max_items
        self.channel_histories: Dict[str, List[HistoryEntry]] = {}
    
    def add_message(self, channel_id: str, entry: HistoryEntry) -> None:
        """Add a message to the channel's history"""
        if channel_id not in self.channel_histories:
            self.channel_histories[channel_id] = []
        
        history = self.channel_histories[channel_id]
        history.append(entry)
        
        # Maintain circular buffer - remove oldest if exceeding max_items
        if len(history) > self.max_items:
            history.pop(0)
    
    def get_history(self, channel_id: str) -> List[HistoryEntry]:
        """Get the conversation history for a channel"""
        return self.channel_histories.get(channel_id, [])
    
    def clear_history(self, channel_id: str) -> None:
        """Clear history for a specific channel"""
        if channel_id in self.channel_histories:
            del self.channel_histories[channel_id]
    
    def get_channel_count(self) -> int:
        """Get the number of channels with stored history"""
        return len(self.channel_histories)