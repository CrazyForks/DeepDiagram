from typing import Optional, List, Any
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="New Chat")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    
    messages: List["ChatMessage"] = Relationship(back_populates="session")

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[int] = Field(default=None, foreign_key="chatsession.id")
    parent_id: Optional[int] = Field(default=None, foreign_key="chatmessage.id")
    role: str # "user" or "assistant"
    content: str
    images: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    steps: Optional[List[Any]] = Field(default=None, sa_column=Column(JSON))
    agent: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    
    session: Optional[ChatSession] = Relationship(back_populates="messages")
