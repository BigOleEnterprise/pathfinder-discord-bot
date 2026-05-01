"""MongoDB data models for question/response logging and rulebook storage."""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QuestionLog(BaseModel):
    """Model for logging /ask questions and responses."""

    question: str = Field(..., description="User's question")
    response: str = Field(..., description="Claude's response")
    user_id: int = Field(..., description="Discord user ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When question was asked")

    # Model metadata
    model: str = Field(..., description="Claude model used")
    input_tokens: int = Field(..., description="Input tokens used")
    output_tokens: int = Field(..., description="Output tokens used")
    total_tokens: int = Field(..., description="Total tokens used")
    estimated_cost: float = Field(..., description="Estimated cost in USD")

    # Performance
    response_time_ms: int = Field(..., description="Response time in milliseconds")

    # Optional feedback (for future use)
    user_feedback: str | None = Field(None, description="User feedback: positive, negative, or none")
    feedback_comment: str | None = Field(None, description="Optional feedback comment")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "question": "How does flanking work in Pathfinder 2E?",
                "response": "In Pathfinder 2E, flanking occurs when...",
                "user_id": 123456789,
                "timestamp": "2025-10-31T04:58:13Z",
                "model": "claude-sonnet-4-5-20250929",
                "input_tokens": 100,
                "output_tokens": 441,
                "total_tokens": 541,
                "estimated_cost": 0.0061,
                "response_time_ms": 11117,
            }
        }

    def to_mongo_dict(self) -> dict[str, Any]:
        """Convert to MongoDB-ready dictionary."""
        data = self.model_dump()
        # MongoDB doesn't need special handling for datetimes in Python
        return data


class RulebookChunk(BaseModel):
    """Model for rulebook text chunks with embeddings."""

    text: str = Field(..., description="Chunk text content")
    source: str = Field(..., description="Source book (e.g., 'core_rulebook', 'gm_core')")
    chunk_index: int = Field(..., description="Index of this chunk in the source")
    char_count: int = Field(..., description="Character count of chunk")
    token_count: int = Field(..., description="Approximate token count")

    # Embedding
    embedding: list[float] = Field(..., description="1536-dimensional embedding vector")
    embedding_model: str = Field(..., description="Model used for embedding")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When chunk was created")

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "text": "Flanking: When you and an ally...",
                "source": "core_rulebook",
                "chunk_index": 245,
                "char_count": 3200,
                "token_count": 800,
                "embedding": [0.123, -0.456],  # Truncated for example
                "embedding_model": "text-embedding-3-small",
                "created_at": "2025-10-31T06:00:00Z",
            }
        }

    def to_mongo_dict(self) -> dict[str, Any]:
        """Convert to MongoDB-ready dictionary."""
        return self.model_dump()


class TurnPhase(StrEnum):
    """Current phase of a combat turn."""

    SETUP = "setup"  # adding combatants, not yet started
    PLAYER_ACTING = "player_acting"  # waiting for player to act / say "done"
    MOB_DECIDING = "mob_deciding"  # Claude is choosing mob action
    AWAITING_HIT_CONFIRM = "awaiting_hit_confirm"  # bot rolled attack, waiting hit/miss
    AWAITING_SAVE_CONFIRM = "awaiting_save_confirm"  # bot asked for save, waiting pass/fail
    BETWEEN_TURNS = "between_turns"  # turn just ended, about to advance


class Condition(BaseModel):
    """A PF2E condition on a combatant."""

    name: str = Field(..., description="Condition name (e.g., frightened, sickened)")
    value: int | None = Field(None, description="Numeric value if applicable (e.g., frightened 2)")
    duration: int | None = Field(None, description="Rounds remaining, if timed")


class Combatant(BaseModel):
    """A single creature or character in combat."""

    name: str = Field(..., description="Display name, used as identifier")
    max_hp: int | None = Field(None, description="Maximum HP (known for mobs, None for players)")
    current_hp: int | None = Field(None, description="Current HP (tracked for mobs, None for players)")
    initiative: float = Field(..., description="Initiative value")
    initiative_modifier: int = Field(0, description="Initiative modifier (for mobs, rolled by bot)")
    conditions: list[Condition] = Field(default_factory=list, description="Active conditions")
    is_player: bool = Field(True, description="True for PCs (user-controlled), False for mobs")
    notes: str = Field("", description="Freeform notes")


class CombatSession(BaseModel):
    """Full combat state persisted to MongoDB."""

    thread_id: int = Field(..., description="Discord thread ID")
    channel_id: int = Field(..., description="Parent channel ID")
    guild_id: int = Field(..., description="Guild ID")
    creator_id: int = Field(..., description="User who started the combat")

    combatants: list[Combatant] = Field(default_factory=list, description="All combatants")
    current_turn_index: int = Field(0, description="Index into sorted combatants list")
    round_number: int = Field(0, description="Current round (0 = setup phase)")
    turn_phase: TurnPhase = Field(TurnPhase.SETUP, description="Current turn phase")

    # Pending action context for multi-step mob turns
    pending_action: dict[str, Any] = Field(
        default_factory=dict, description="Context for in-progress mob action"
    )

    is_active: bool = Field(True, description="Whether combat is ongoing")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_mongo_dict(self) -> dict[str, Any]:
        """Convert to MongoDB-ready dictionary."""
        data = self.model_dump()
        data["turn_phase"] = self.turn_phase.value
        return data

    @classmethod
    def from_mongo_dict(cls, data: dict[str, Any]) -> "CombatSession":
        """Reconstruct from a MongoDB document."""
        data.pop("_id", None)
        return cls(**data)
