"""Claude AI service for Pathfinder 2E rules Q&A."""
import logging
import time
from typing import NamedTuple

from anthropic import Anthropic, AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ClaudeResponse(NamedTuple):
    """Response from Claude API."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    response_time_ms: int

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """
        Calculate estimated cost in USD based on model pricing.

        Claude Sonnet 4.5 pricing (as of 2025):
        - Input: $3 per million tokens
        - Output: $15 per million tokens
        """
        input_cost = (self.input_tokens / 1_000_000) * 3.0
        output_cost = (self.output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost


class ClaudeService:
    """Handles interactions with Claude API for rules Q&A."""

    SYSTEM_PROMPT = """You are an expert on Pathfinder 2nd Edition (PF2E) rules.
Your role is to help players and Game Masters understand the rules clearly and accurately.

Guidelines:
- Provide concise, accurate answers based on official PF2E rules
- If you're unsure or the rule is ambiguous, say so
- Cite relevant mechanics (e.g., "According to the action economy rules...")
- Use clear examples when helpful
- Keep responses under 300 words unless more detail is explicitly requested
- Be friendly and encouraging to new players

If a question is not about Pathfinder 2E, politely redirect the user."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20240620"):
        """Initialize Claude service with API key and model selection."""
        self.client = AsyncAnthropic(api_key=api_key)
        self.sync_client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = 1024  # Reasonable for Q&A responses

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def ask(self, question: str, rulebook_context: str | None = None) -> ClaudeResponse:
        """Ask Claude a PF2E rules question with optional rulebook context and return response with metadata."""
        try:
            logger.info(f"Sending question to Claude: {question[:100]}...")

            # Track response time
            start_time = time.time()

            # Build user message with optional rulebook context
            if rulebook_context:
                user_message = f"""Here are relevant excerpts from the Pathfinder 2E rulebooks:

{rulebook_context}

Based on these rulebook excerpts, please answer the following question:

{question}"""
            else:
                user_message = question

            message = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Extract text content from response
            content = message.content[0].text if message.content else ""

            # Get token usage
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens

            logger.info(
                f"Received response from Claude ({input_tokens + output_tokens} tokens, "
                f"{response_time_ms}ms, {len(content)} chars)"
            )

            return ClaudeResponse(
                content=content,
                model=message.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                response_time_ms=response_time_ms,
            )

        except Exception as e:
            logger.exception(f"Error calling Claude API: {e}")
            raise
