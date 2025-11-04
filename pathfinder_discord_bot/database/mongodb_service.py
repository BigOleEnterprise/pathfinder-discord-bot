"""MongoDB service for async database operations."""
import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from pathfinder_discord_bot.database.models import QuestionLog

logger = logging.getLogger(__name__)


class MongoDBService:
    """Handles MongoDB connections and operations."""

    def __init__(self, uri: str, database_name: str):
        """Initialize MongoDB service with connection URI and database name."""
        self.client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self.db: AsyncIOMotorDatabase = self.client[database_name]
        self.question_logs = self.db.question_logs
        self.rulebook_chunks = self.db.rulebook_chunks

    async def save_question_log(self, log: QuestionLog) -> str | None:
        """Save a question log to MongoDB and return the inserted document ID."""
        try:
            result = await self.question_logs.insert_one(log.to_mongo_dict())
            logger.info(f"Saved question log to MongoDB: {result.inserted_id}")
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.exception(f"Error saving question log to MongoDB: {e}")
            return None

    async def get_recent_questions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent questions from the database, sorted by timestamp."""
        try:
            cursor = self.question_logs.find().sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except PyMongoError as e:
            logger.exception(f"Error fetching recent questions: {e}")
            return []

    async def get_user_questions(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get questions from a specific user, sorted by timestamp."""
        try:
            cursor = (
                self.question_logs.find({"user_id": user_id})
                .sort("timestamp", -1)
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except PyMongoError as e:
            logger.exception(f"Error fetching user questions: {e}")
            return []

    async def save_rulebook_chunk(self, chunk: "RulebookChunk") -> str | None:
        """Save a rulebook chunk to MongoDB and return the inserted document ID."""
        try:
            result = await self.rulebook_chunks.insert_one(chunk.to_mongo_dict())
            return str(result.inserted_id)
        except PyMongoError as e:
            logger.exception(f"Error saving rulebook chunk to MongoDB: {e}")
            return None

    async def save_rulebook_chunks_batch(self, chunks: list["RulebookChunk"]) -> int:
        """Save multiple rulebook chunks in batch and return count of successfully saved chunks."""
        try:
            documents = [chunk.to_mongo_dict() for chunk in chunks]
            result = await self.rulebook_chunks.insert_many(documents)
            logger.info(f"Saved {len(result.inserted_ids)} chunks to MongoDB")
            return len(result.inserted_ids)
        except PyMongoError as e:
            logger.exception(f"Error saving rulebook chunks batch: {e}")
            return 0

    async def clear_rulebook_chunks(self) -> int:
        """Clear all rulebook chunks from MongoDB and return count of deleted documents."""
        try:
            result = await self.rulebook_chunks.delete_many({})
            logger.info(f"Deleted {result.deleted_count} rulebook chunks")
            return result.deleted_count
        except PyMongoError as e:
            logger.exception(f"Error clearing rulebook chunks: {e}")
            return 0

    async def vector_search_rulebooks(
        self, query_embedding: list[float], limit: int = 5, index_name: str = "vector_index"
    ) -> list[dict[str, Any]]:
        """Search rulebook chunks using vector similarity and return matching chunks with scores."""
        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": index_name,
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": limit * 10,  # Search more candidates for better results
                        "limit": limit,
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "text": 1,
                        "source": 1,
                        "chunk_index": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]

            results = []
            async for doc in self.rulebook_chunks.aggregate(pipeline):
                results.append(doc)

            logger.info(f"Vector search returned {len(results)} results")
            return results

        except Exception as e:
            logger.exception(f"Error in vector search: {e}")
            return []

    async def ping(self) -> bool:
        """Ping MongoDB to verify connection is healthy."""
        try:
            await self.client.admin.command("ping")
            logger.info("MongoDB connection is healthy")
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False

    async def close(self) -> None:
        """Close the MongoDB connection."""
        self.client.close()
        logger.info("MongoDB connection closed")
