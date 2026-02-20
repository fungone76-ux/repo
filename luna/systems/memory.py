"""Memory management system for long-term narrative memory.

Handles:
- Important facts storage (from LLM responses)
- History compression/summarization
- Context retrieval for LLM prompts
- Keyword-based and semantic search (optional)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from luna.core.database import DatabaseManager
from luna.core.models import ConversationMessage, MemoryEntry

logger = logging.getLogger(__name__)


@dataclass
class MemorySearchResult:
    """Result from a memory search operation."""
    
    memory: MemoryEntry
    score: float
    match_type: str  # "keyword", "semantic", "importance"


class KeywordExtractor:
    """Extract keywords from text for matching."""
    
    # Common stop words in Italian and English
    STOP_WORDS: Set[str] = {
        # Italian
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
        "di", "del", "della", "dei", "delle", "a", "al", "alla",
        "ai", "alle", "da", "dal", "dalla", "dai", "dalle",
        "in", "nel", "nella", "nei", "nelle", "con", "su",
        "per", "tra", "fra", "è", "sono", "era", "erano",
        "ho", "hai", "ha", "abbiamo", "avete", "hanno",
        # English
        "the", "a", "an", "is", "are", "was", "were", "be",
        "been", "being", "have", "has", "had", "do", "does",
        "did", "will", "would", "could", "should", "may",
        "might", "must", "can", "this", "that", "these",
        "those", "i", "you", "he", "she", "it", "we", "they",
        "me", "him", "her", "us", "them", "my", "your", "his",
        "in", "on", "at", "to", "for", "of", "with", "about",
    }
    
    @classmethod
    def extract(cls, text: str, min_length: int = 3) -> Set[str]:
        """Extract significant keywords from text.
        
        Args:
            text: Input text
            min_length: Minimum keyword length
            
        Returns:
            Set of keywords
        """
        # Lowercase and extract words
        words = re.findall(r'\b[a-zA-Zàèéìòóù]+\b', text.lower())
        
        # Filter stop words and short words
        keywords = {
            w for w in words 
            if w not in cls.STOP_WORDS and len(w) >= min_length
        }
        
        return keywords
    
    @classmethod
    def calculate_similarity(cls, text1: str, text2: str) -> float:
        """Calculate keyword overlap similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score 0.0-1.0
        """
        keywords1 = cls.extract(text1)
        keywords2 = cls.extract(text2)
        
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = keywords1 & keywords2
        union = keywords1 | keywords2
        
        return len(intersection) / len(union)


class SemanticMemoryStore:
    """Optional semantic memory storage using ChromaDB."""
    
    def __init__(self, session_id: int, storage_path: Path) -> None:
        """Initialize semantic memory store.
        
        Args:
            session_id: Session identifier
            storage_path: Path for vector storage
        """
        self.session_id = session_id
        self.storage_path = storage_path
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._embedder: Optional[Any] = None
        self._available = False
        
    def initialize(self) -> bool:
        """Initialize ChromaDB and embedder.
        
        Returns:
            True if successfully initialized
        """
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
            
            # Create storage directory
            db_path = self.storage_path / "vectors"
            db_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize embedder (lightweight model)
            logger.info("Loading embedding model...")
            self._embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Initialize ChromaDB
            self._client = chromadb.PersistentClient(path=str(db_path))
            
            # Get or create collection for this session
            collection_name = f"session_{self.session_id}"
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"session_id": self.session_id}
            )
            
            self._available = True
            logger.info(f"Semantic memory initialized for session {self.session_id}")
            return True
            
        except ImportError as e:
            logger.warning(f"Semantic memory dependencies not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize semantic memory: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        """True if semantic search is available."""
        return self._available and self._collection is not None
    
    def add_memory(self, memory_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        """Add memory to semantic store.
        
        Args:
            memory_id: Unique memory identifier
            content: Memory content to embed
            metadata: Associated metadata
            
        Returns:
            True if added successfully
        """
        if not self.is_available:
            return False
        
        try:
            embedding = self._embedder.encode(content).tolist()
            
            self._collection.add(
                ids=[memory_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[metadata]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add semantic memory: {e}")
            return False
    
    def search(self, query: str, k: int = 5) -> List[Tuple[str, float, str]]:
        """Search memories by semantic similarity.
        
        Args:
            query: Search query
            k: Number of results
            
        Returns:
            List of (memory_id, score, content) tuples
        """
        if not self.is_available:
            return []
        
        try:
            query_embedding = self._embedder.encode(query).tolist()
            
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=["documents", "distances"]
            )
            
            # Convert distances to similarity scores (Chroma returns distances)
            # Cosine distance to similarity: 1 - distance
            memories = []
            for i, memory_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                content = results["documents"][0][i]
                similarity = 1.0 - distance  # Convert to similarity
                memories.append((memory_id, similarity, content))
            
            return memories
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def delete_session(self) -> bool:
        """Delete all memories for this session.
        
        Returns:
            True if deleted successfully
        """
        if not self.is_available:
            return False
        
        try:
            self._client.delete_collection(f"session_{self.session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete semantic memories: {e}")
            return False


class MemoryManager:
    """Manages long-term memories and conversation history.
    
    Features:
    - Store important facts from gameplay
    - Compress old history when too long
    - Retrieve relevant memories using keyword or semantic search
    - Hybrid scoring combining multiple match types
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        session_id: int,
        history_limit: int = 50,
        enable_semantic: bool = False,
        storage_path: Optional[Path] = None,
    ) -> None:
        """Initialize memory manager.
        
        Args:
            db_manager: Database manager
            session_id: Current session ID
            history_limit: Max messages to keep in recent history
            enable_semantic: Enable semantic search (requires ChromaDB)
            storage_path: Path for vector storage (required if semantic enabled)
        """
        self.db = db_manager
        self.session_id = session_id
        self.history_limit = history_limit
        self.enable_semantic = enable_semantic
        
        # Cache
        self._recent_messages: List[ConversationMessage] = []
        self._facts: List[MemoryEntry] = []
        self._loaded = False
        
        # Keyword extractor
        self._keyword_extractor = KeywordExtractor()
        
        # Semantic store (optional)
        self._semantic_store: Optional[SemanticMemoryStore] = None
        if enable_semantic and storage_path:
            self._semantic_store = SemanticMemoryStore(session_id, storage_path)
    
    async def load(self) -> None:
        """Load memories from database."""
        if self._loaded:
            return
        
        # Initialize semantic store if enabled
        if self._semantic_store and not self._semantic_store.initialize():
            logger.warning("Failed to initialize semantic memory, falling back to keyword search")
            self.enable_semantic = False
        
        async with self.db.session() as db_session:
            # Load recent messages
            db_messages = await self.db.get_messages(
                db_session, self.session_id, limit=self.history_limit
            )
            
            self._recent_messages = [
                ConversationMessage(
                    role=msg.role,
                    content=msg.content,
                    turn_number=msg.turn_number,
                    visual_en=msg.visual_en,
                    tags_en=msg.tags_en,
                )
                for msg in db_messages
            ]
            
            # Load facts
            db_memories = await self.db.get_memories(
                db_session, self.session_id, memory_type="fact", limit=100
            )
            
            self._facts = [
                MemoryEntry(
                    id=mem.id,
                    type="fact",
                    content=mem.content,
                    turn_count=mem.turn_number,
                    importance=mem.importance,
                )
                for mem in db_memories
            ]
            
            # Add to semantic store if available
            if self._semantic_store and self._semantic_store.is_available:
                for fact in self._facts:
                    if fact.id:  # Only add if has ID
                        self._semantic_store.add_memory(
                            memory_id=str(fact.id),
                            content=fact.content,
                            metadata={
                                "turn": fact.turn_count,
                                "importance": fact.importance,
                                "type": fact.type,
                            }
                        )
        
        self._loaded = True
        logger.info(
            f"Memory loaded: {len(self._recent_messages)} messages, "
            f"{len(self._facts)} facts, semantic={self.enable_semantic}"
        )
    
    async def add_message(
        self,
        role: str,
        content: str,
        turn_number: int,
        visual_en: str = "",
        tags_en: Optional[List[str]] = None,
    ) -> None:
        """Add message to history.
        
        Args:
            role: user/assistant/system
            content: Message text
            turn_number: Game turn
            visual_en: Visual description
            tags_en: SD tags
        """
        # Add to cache
        message = ConversationMessage(
            role=role,
            content=content,
            turn_number=turn_number,
            visual_en=visual_en,
            tags_en=tags_en or [],
        )
        self._recent_messages.append(message)
        
        # Save to DB
        async with self.db.session() as db_session:
            await self.db.add_message(
                db_session,
                self.session_id,
                role,
                content,
                turn_number,
                visual_en,
                tags_en or [],
            )
        
        # Check if compression needed
        if len(self._recent_messages) > self.history_limit:
            await self._compress_history()
    
    async def add_fact(
        self,
        content: str,
        turn_number: int,
        importance: int = 5,
        associated_npc: Optional[str] = None,
        context_tags: Optional[List[str]] = None,
    ) -> None:
        """Store important fact.
        
        Args:
            content: Fact description
            turn_number: When it happened
            importance: 1-10 importance score
            associated_npc: NPC associated with this memory
            context_tags: Additional context tags (e.g., ["conflict", "gift"])
        """
        # Add to cache
        fact = MemoryEntry(
            type="fact",
            content=content,
            turn_count=turn_number,
            importance=importance,
        )
        self._facts.append(fact)
        
        # Save to DB
        async with self.db.session() as db_session:
            mem = await self.db.add_memory(
                db_session,
                self.session_id,
                "fact",
                content,
                turn_number,
                importance,
            )
            fact.id = mem.id
        
        # Add to semantic store if available
        if self._semantic_store and self._semantic_store.is_available and fact.id:
            metadata: Dict[str, Any] = {
                "turn": turn_number,
                "importance": importance,
                "type": "fact",
            }
            if associated_npc:
                metadata["npc"] = associated_npc
            if context_tags:
                metadata["tags"] = ",".join(context_tags)
            
            self._semantic_store.add_memory(
                memory_id=str(fact.id),
                content=content,
                metadata=metadata
            )
        
        logger.debug(f"Added fact (importance={importance}): {content[:50]}...")
    
    def get_recent_history(self, limit: Optional[int] = None) -> List[ConversationMessage]:
        """Get recent conversation history.
        
        Args:
            limit: Max messages to return
            
        Returns:
            List of recent messages
        """
        limit = limit or self.history_limit
        return self._recent_messages[-limit:]
    
    def get_important_facts(self, min_importance: int = 5, limit: int = 20) -> List[MemoryEntry]:
        """Get important facts sorted by importance.
        
        Args:
            min_importance: Minimum importance threshold
            limit: Maximum number of facts
            
        Returns:
            List of important facts
        """
        filtered = [f for f in self._facts if f.importance >= min_importance]
        sorted_facts = sorted(filtered, key=lambda f: f.importance, reverse=True)
        return sorted_facts[:limit]
    
    def search_memories(
        self,
        query: str,
        k: int = 5,
        min_importance: int = 1,
        use_semantic: Optional[bool] = None,
    ) -> List[MemorySearchResult]:
        """Search memories using keyword and/or semantic matching.
        
        Args:
            query: Search query
            k: Number of results to return
            min_importance: Minimum importance threshold
            use_semantic: Force semantic search (None = auto)
            
        Returns:
            List of search results sorted by relevance
        """
        if not self._facts:
            return []
        
        # Determine search strategy
        use_semantic = use_semantic if use_semantic is not None else self.enable_semantic
        
        # Collect scores from different methods
        memory_scores: Dict[int, Tuple[MemoryEntry, float, str]] = {}
        
        # 1. Keyword-based search (always run)
        query_keywords = self._keyword_extractor.extract(query)
        
        for fact in self._facts:
            if fact.importance < min_importance:
                continue
            
            # Calculate keyword similarity
            keyword_sim = self._keyword_extractor.calculate_similarity(query, fact.content)
            
            # Boost for exact keyword matches
            fact_keywords = self._keyword_extractor.extract(fact.content)
            keyword_overlap = query_keywords & fact_keywords
            if keyword_overlap:
                keyword_sim += len(keyword_overlap) * 0.1  # Boost per matching keyword
            
            if keyword_sim > 0:
                memory_scores[fact.id or 0] = (fact, keyword_sim, "keyword")
        
        # 2. Semantic search (if available and requested)
        if use_semantic and self._semantic_store and self._semantic_store.is_available:
            semantic_results = self._semantic_store.search(query, k=k * 2)
            
            for memory_id, score, _ in semantic_results:
                try:
                    fact_id = int(memory_id)
                    # Find the fact
                    for fact in self._facts:
                        if fact.id == fact_id and fact.importance >= min_importance:
                            # Combine scores if already present from keyword search
                            if fact_id in memory_scores:
                                existing_fact, existing_score, existing_type = memory_scores[fact_id]
                                # Weighted combination
                                combined_score = max(existing_score, score * 0.9) + 0.1
                                memory_scores[fact_id] = (fact, combined_score, "hybrid")
                            else:
                                memory_scores[fact_id] = (fact, score, "semantic")
                            break
                except ValueError:
                    continue
        
        # 3. Add importance-boosted facts (if we have few results)
        if len(memory_scores) < k:
            for fact in self._facts:
                if fact.id not in memory_scores and fact.importance >= min_importance + 3:
                    # Add with small score based on importance
                    importance_boost = (fact.importance - 5) / 100  # 0.03 to 0.05 boost
                    memory_scores[fact.id or 0] = (fact, importance_boost, "importance")
        
        # Sort by score and return top-k
        sorted_results = sorted(
            memory_scores.values(),
            key=lambda x: x[1],
            reverse=True
        )[:k]
        
        return [
            MemorySearchResult(memory=fact, score=score, match_type=match_type)
            for fact, score, match_type in sorted_results
        ]
    
    def get_memory_context(
        self,
        query: Optional[str] = None,
        max_facts: int = 10,
        min_importance: int = 4,
    ) -> str:
        """Build memory context for LLM prompt.
        
        Args:
            query: Optional query to find relevant memories
            max_facts: Max facts to include
            min_importance: Minimum importance threshold
            
        Returns:
            Formatted memory context
        """
        lines = ["=== IMPORTANT MEMORY ==="]
        
        if query and (self.enable_semantic or len(self._facts) > 20):
            # Use search for targeted retrieval
            results = self.search_memories(query, k=max_facts, min_importance=min_importance)
            memories = [r.memory for r in results]
        else:
            # Fall back to importance-based selection
            memories = self.get_important_facts(min_importance, max_facts)
        
        if memories:
            for mem in memories:
                # Optional: add importance indicator for high-value memories
                prefix = ""
                if mem.importance >= 8:
                    prefix = "[IMPORTANT] "
                lines.append(f"• {prefix}{mem.content}")
        else:
            lines.append("(No significant memories yet)")
        
        lines.append("=== END MEMORY ===")
        
        return "\n".join(lines)
    
    async def _compress_history(self) -> None:
        """Compress old history into summary."""
        if len(self._recent_messages) < self.history_limit + 10:
            return
        
        # Get oldest messages to compress
        to_compress = self._recent_messages[:10]
        
        # Create a meaningful summary
        start_turn = to_compress[0].turn_number
        end_turn = to_compress[-1].turn_number
        
        # Extract key topics from messages
        all_content = " ".join([m.content for m in to_compress])
        keywords = self._keyword_extractor.extract(all_content)
        key_topics = ", ".join(list(keywords)[:5]) if keywords else "general conversation"
        
        summary_text = (
            f"Summary of turns {start_turn}-{end_turn}: "
            f"Discussed topics: {key_topics}. "
            f"({len(to_compress)} messages)"
        )
        
        # Add as summary memory
        async with self.db.session() as db_session:
            await self.db.add_memory(
                db_session,
                self.session_id,
                "summary",
                summary_text,
                end_turn,
                importance=3,
            )
        
        # Remove old messages from cache
        self._recent_messages = self._recent_messages[10:]
        
        # Delete old messages from DB
        async with self.db.session() as db_session:
            await self.db.delete_old_messages(
                db_session, self.session_id, self.history_limit
            )
        
        logger.debug(f"Compressed history: {summary_text}")
    
    async def get_memories_by_npc(self, npc_name: str) -> List[MemoryEntry]:
        """Get all memories associated with a specific NPC.
        
        Args:
            npc_name: Name of the NPC
            
        Returns:
            List of memories associated with the NPC
        """
        # For now, do simple keyword search on content
        # In future, could use semantic search with metadata filtering
        npc_lower = npc_name.lower()
        return [
            f for f in self._facts
            if npc_lower in f.content.lower()
        ]
    
    async def get_memories_by_tag(self, tag: str) -> List[MemoryEntry]:
        """Get memories by context tag.
        
        Args:
            tag: Context tag to search for
            
        Returns:
            List of matching memories
        """
        # Simple keyword search for now
        tag_lower = tag.lower()
        return [
            f for f in self._facts
            if tag_lower in f.content.lower()
        ]
    
    async def clear(self) -> None:
        """Clear all memories (use with caution)."""
        self._recent_messages.clear()
        self._facts.clear()
        
        # Clear semantic store
        if self._semantic_store:
            self._semantic_store.delete_session()
        
        self._loaded = False
        logger.info("Memory cleared")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "recent_messages": len(self._recent_messages),
            "total_facts": len(self._facts),
            "high_importance_facts": len([f for f in self._facts if f.importance >= 7]),
            "semantic_enabled": self.enable_semantic,
            "semantic_available": (
                self._semantic_store.is_available if self._semantic_store else False
            ),
        }
