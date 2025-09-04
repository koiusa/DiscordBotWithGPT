from dataclasses import dataclass
from typing import Optional, List, Union


@dataclass(frozen=True)
class Message:
    user: str
    role: str
    # Vision対応: contentはstrまたはlist（text/image_urlなど）
    content: Optional[Union[str, list]] = None

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
    model: str
    name: str
    example_conversations: List[Conversation]
