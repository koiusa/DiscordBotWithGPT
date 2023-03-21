from dataclasses import dataclass
from typing import Optional, List


@dataclass(frozen=True)
class Message:
    user: str
    role: str
    content: Optional[str] = None

    def render(self):
        return {"role": self.role, "content": self.content}


@dataclass
class Conversation:
    messages: List[Message]

    def prepend(self, message: Message):
        self.messages.insert(0, message)
        return self

    def render(self):
        return [message.render() for message in self.messages]


@dataclass(frozen=True)
class Config:
    name: str
    example_conversations: List[Conversation]
