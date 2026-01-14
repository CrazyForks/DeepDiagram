from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.chat import ChatSession, ChatMessage

class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(self, title: str = "New Chat") -> ChatSession:
        chat_session = ChatSession(title=title)
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session

    async def get_session(self, session_id: int) -> ChatSession | None:
        statement = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.session.exec(statement)
        return result.first()

    async def add_message(
        self, 
        session_id: int, 
        role: str, 
        content: str, 
        images: list[str] | None = None,
        files: list[dict] | None = None,
        file_context: str | None = None,
        steps: list[any] | None = None,
        agent: str | None = None,
        parent_id: int | None = None
    ) -> ChatMessage:
        turn_index = 0
        if parent_id and parent_id > 0:
            parent_statement = select(ChatMessage).where(ChatMessage.id == parent_id)
            parent_result = await self.session.exec(parent_statement)
            parent = parent_result.first()
            if parent:
                turn_index = parent.turn_index + 1

        message = ChatMessage(
            session_id=session_id, 
            role=role, 
            content=content,
            images=images,
            files=files,
            file_context=file_context,
            steps=steps,
            agent=agent,
            parent_id=parent_id,
            turn_index=turn_index
        )
        self.session.add(message)
        
        # Update session updated_at
        from datetime import datetime, timezone
        statement = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.session.exec(statement)
        chat_session = result.first()
        if chat_session:
            chat_session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.session.add(chat_session)
            
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def update_message(self, message_id: int, **kwargs) -> ChatMessage | None:
        statement = select(ChatMessage).where(ChatMessage.id == message_id)
        result = await self.session.exec(statement)
        message = result.first()
        if message:
            for key, value in kwargs.items():
                if hasattr(message, key):
                    setattr(message, key, value)
            self.session.add(message)
            await self.session.commit()
            await self.session.refresh(message)
        return message

    async def get_history(self, session_id: int):
        statement = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        result = await self.session.exec(statement)
        return result.all()

    async def get_all_sessions(self):
        statement = select(ChatSession).order_by(ChatSession.updated_at.desc())
        result = await self.session.exec(statement)
        return result.all()

    async def delete_session(self, session_id: int):
        # SQLModel/SQLAlchemy will handle cascade if configured, but let's be safe or just delete session
        # Actually ChatMessage has foreign key to chatsession.id. 
        # If we didn't specify ondelete="CASCADE" in models/chat.py, we should delete messages first.
        
        from sqlmodel import delete
        
        # Delete messages
        msg_statement = delete(ChatMessage).where(ChatMessage.session_id == session_id)
        await self.session.exec(msg_statement)
        
        # Delete session
        sess_statement = delete(ChatSession).where(ChatSession.id == session_id)
        await self.session.exec(sess_statement)
        
        await self.session.commit()
