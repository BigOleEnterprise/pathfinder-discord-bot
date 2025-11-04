"""MongoDB data models for question/response logging and rulebook storage."""
from datetime import datetime
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
