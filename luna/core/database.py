"""Async SQLAlchemy database setup.

Provides async database operations with SQLAlchemy 2.0.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

from luna.core.models import AppConfig

Base = declarative_base()


class GameSessionModel(Base):
    """Database model for game sessions."""
    
    __tablename__ = "game_sessions"
    
    id = Column(Integer, primary_key=True)
    world_id = Column(String, nullable=False)
    active_companion = Column(String, nullable=False)
    
    # Time & Progress
    turn_count = Column(Integer, default=0)
    time_of_day = Column(String, default="Morning")
    current_location = Column(String, default="Unknown")
    companion_outfit = Column(String, default="default")
    
    # Player state (serialized)
    player_state = Column(JSON, default=dict)
    
    # NPC states (serialized)
    npc_states = Column(JSON, default=dict)
    
    # Relationships
    affinity = Column(JSON, default=dict)
    flags = Column(JSON, default=dict)
    
    # Personality engine state
    personality_state = Column(JSON, default=dict)
    
    # Outfit states (serialized dict of companion_name -> OutfitState)
    outfit_states = Column(JSON, default=dict)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = relationship(
        "ConversationMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    memories = relationship(
        "MemoryEntryModel",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    quest_states = relationship(
        "QuestStateModel",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class ConversationMessageModel(Base):
    """Database model for conversation history."""
    
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    
    role = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    turn_number = Column(Integer, nullable=False)
    
    # AI generation metadata
    visual_en = Column(Text, default="")
    tags_en = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("GameSessionModel", back_populates="messages")


class MemoryEntryModel(Base):
    """Database model for long-term memories."""
    
    __tablename__ = "memories"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    
    memory_type = Column(String, nullable=False)  # summary, fact, event
    content = Column(Text, nullable=False)
    turn_number = Column(Integer, nullable=False)
    importance = Column(Integer, default=5)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    session = relationship("GameSessionModel", back_populates="memories")


class QuestStateModel(Base):
    """Database model for quest states."""
    
    __tablename__ = "quest_states"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"), nullable=False)
    
    quest_id = Column(String, nullable=False)
    status = Column(String, default="not_started")
    current_stage_id = Column(String, nullable=True)
    stage_data = Column(JSON, default=dict)
    
    started_at = Column(Integer, default=0)
    completed_at = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    session = relationship("GameSessionModel", back_populates="quest_states")


class DatabaseManager:
    """Manages async database operations."""
    
    def __init__(self, config: Optional[AppConfig] = None) -> None:
        """Initialize database manager.
        
        Args:
            config: Application configuration. Uses default if not provided.
        """
        self.config = config or AppConfig()
        self.database_url = self.config.database_url
        
        # Create async engine
        self.engine = create_async_engine(
            self.database_url,
            echo=self.config.log_level == "DEBUG",
            future=True,
        )
        
        # Create session factory
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self) -> None:
        """Drop all tables (DANGER!)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get database session context manager.
        
        Usage:
            async with db_manager.session() as db:
                result = await db.execute(...)
        """
        async with self.async_session() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise
            finally:
                await db.close()
    
    # =========================================================================
    # Session Operations
    # =========================================================================
    
    async def create_session(
        self,
        db: AsyncSession,
        world_id: str,
        companion: str,
        affinity: Dict[str, int],
    ) -> GameSessionModel:
        """Create new game session.
        
        Args:
            db: Database session
            world_id: World identifier
            companion: Starting companion name
            affinity: Initial affinity values
            
        Returns:
            Created session model
        """
        session = GameSessionModel(
            world_id=world_id,
            active_companion=companion,
            affinity=affinity,
            player_state={},
            npc_states={},
            flags={},
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)
        return session
    
    async def get_session(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> Optional[GameSessionModel]:
        """Get session by ID.
        
        Args:
            db: Database session
            session_id: Session ID
            
        Returns:
            Session model or None
        """
        result = await db.execute(
            select(GameSessionModel).where(GameSessionModel.id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def update_session(
        self,
        db: AsyncSession,
        session_id: int,
        **kwargs: Any,
    ) -> bool:
        """Update session fields.
        
        Args:
            db: Database session
            session_id: Session ID
            **kwargs: Fields to update
            
        Returns:
            True if updated
        """
        result = await db.execute(
            select(GameSessionModel).where(GameSessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return False
        
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.updated_at = datetime.utcnow()
        return True
    
    async def list_sessions(
        self,
        db: AsyncSession,
        limit: int = 50,
    ) -> List[GameSessionModel]:
        """List recent sessions.
        
        Args:
            db: Database session
            limit: Maximum results
            
        Returns:
            List of sessions
        """
        result = await db.execute(
            select(GameSessionModel)
            .order_by(GameSessionModel.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    # =========================================================================
    # Message Operations
    # =========================================================================
    
    async def add_message(
        self,
        db: AsyncSession,
        session_id: int,
        role: str,
        content: str,
        turn_number: int,
        visual_en: str = "",
        tags_en: Optional[List[str]] = None,
    ) -> ConversationMessageModel:
        """Add conversation message.
        
        Args:
            db: Database session
            session_id: Session ID
            role: Message role (user, assistant, system)
            content: Message content
            turn_number: Game turn number
            visual_en: Visual description
            tags_en: Image generation tags
            
        Returns:
            Created message model
        """
        msg = ConversationMessageModel(
            session_id=session_id,
            role=role,
            content=content,
            turn_number=turn_number,
            visual_en=visual_en,
            tags_en=tags_en or [],
        )
        db.add(msg)
        await db.flush()
        return msg
    
    async def get_messages(
        self,
        db: AsyncSession,
        session_id: int,
        limit: int = 50,
    ) -> List[ConversationMessageModel]:
        """Get recent messages for session.
        
        Args:
            db: Database session
            session_id: Session ID
            limit: Maximum results
            
        Returns:
            List of messages (chronological order)
        """
        result = await db.execute(
            select(ConversationMessageModel)
            .where(ConversationMessageModel.session_id == session_id)
            .order_by(ConversationMessageModel.id.desc())
            .limit(limit)
        )
        # Return in chronological order
        return list(reversed(result.scalars().all()))
    
    async def delete_old_messages(
        self,
        db: AsyncSession,
        session_id: int,
        keep_count: int = 50,
    ) -> int:
        """Delete old messages beyond keep_count.
        
        Args:
            db: Database session
            session_id: Session ID
            keep_count: Number of recent messages to keep
            
        Returns:
            Number of deleted messages
        """
        # Get IDs to delete
        subquery = (
            select(ConversationMessageModel.id)
            .where(ConversationMessageModel.session_id == session_id)
            .order_by(ConversationMessageModel.id.desc())
            .offset(keep_count)
        )
        
        result = await db.execute(subquery)
        ids_to_delete = [row[0] for row in result.all()]
        
        if ids_to_delete:
            await db.execute(
                ConversationMessageModel.__table__.delete()
                .where(ConversationMessageModel.id.in_(ids_to_delete))
            )
        
        return len(ids_to_delete)
    
    # =========================================================================
    # Memory Operations
    # =========================================================================
    
    async def add_memory(
        self,
        db: AsyncSession,
        session_id: int,
        memory_type: str,
        content: str,
        turn_number: int,
        importance: int = 5,
    ) -> MemoryEntryModel:
        """Add memory entry.
        
        Args:
            db: Database session
            session_id: Session ID
            memory_type: Type (summary, fact, event)
            content: Memory content
            turn_number: Game turn number
            importance: Importance score (1-10)
            
        Returns:
            Created memory model
        """
        mem = MemoryEntryModel(
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            turn_number=turn_number,
            importance=importance,
        )
        db.add(mem)
        await db.flush()
        return mem
    
    async def get_memories(
        self,
        db: AsyncSession,
        session_id: int,
        memory_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[MemoryEntryModel]:
        """Get memories for session.
        
        Args:
            db: Database session
            session_id: Session ID
            memory_type: Filter by type
            limit: Maximum results
            
        Returns:
            List of memories (chronological order)
        """
        query = select(MemoryEntryModel).where(
            MemoryEntryModel.session_id == session_id
        )
        
        if memory_type:
            query = query.where(MemoryEntryModel.memory_type == memory_type)
        
        query = query.order_by(MemoryEntryModel.id.desc()).limit(limit)
        
        result = await db.execute(query)
        return list(reversed(result.scalars().all()))
    
    # =========================================================================
    # Quest State Operations
    # =========================================================================
    
    async def get_quest_state(
        self,
        db: AsyncSession,
        session_id: int,
        quest_id: str,
    ) -> Optional[QuestStateModel]:
        """Get quest state.
        
        Args:
            db: Database session
            session_id: Session ID
            quest_id: Quest identifier
            
        Returns:
            Quest state or None
        """
        result = await db.execute(
            select(QuestStateModel)
            .where(QuestStateModel.session_id == session_id)
            .where(QuestStateModel.quest_id == quest_id)
        )
        return result.scalar_one_or_none()
    
    async def save_quest_state(
        self,
        db: AsyncSession,
        session_id: int,
        quest_id: str,
        status: str,
        current_stage_id: Optional[str] = None,
        stage_data: Optional[Dict[str, Any]] = None,
        started_at: int = 0,
        completed_at: Optional[int] = None,
    ) -> QuestStateModel:
        """Save or update quest state.
        
        Args:
            db: Database session
            session_id: Session ID
            quest_id: Quest identifier
            status: Quest status
            current_stage_id: Current stage
            stage_data: Stage-specific data
            started_at: Turn when started
            completed_at: Turn when completed
            
        Returns:
            Quest state model
        """
        # Try to find existing
        existing = await self.get_quest_state(db, session_id, quest_id)
        
        if existing:
            existing.status = status
            existing.current_stage_id = current_stage_id
            existing.stage_data = stage_data or {}
            if completed_at:
                existing.completed_at = completed_at
            await db.flush()
            return existing
        
        # Create new
        state = QuestStateModel(
            session_id=session_id,
            quest_id=quest_id,
            status=status,
            current_stage_id=current_stage_id,
            stage_data=stage_data or {},
            started_at=started_at,
            completed_at=completed_at,
        )
        db.add(state)
        await db.flush()
        return state
    
    async def get_all_quest_states(
        self,
        db: AsyncSession,
        session_id: int,
    ) -> List[QuestStateModel]:
        """Get all quest states for session.
        
        Args:
            db: Database session
            session_id: Session ID
            
        Returns:
            List of quest states
        """
        result = await db.execute(
            select(QuestStateModel)
            .where(QuestStateModel.session_id == session_id)
        )
        return list(result.scalars().all())


# Singleton instance (will be initialized with config)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(config: Optional[AppConfig] = None) -> DatabaseManager:
    """Get or create database manager singleton.
    
    Args:
        config: Application configuration
        
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(config)
    return _db_manager
