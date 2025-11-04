"""Ask command cog for Pathfinder 2E rules Q&A using Claude."""
import logging

import discord
from discord import app_commands, ui
from discord.ext import commands

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.database.models import QuestionLog
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.claude_service import ClaudeService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService
from pathfinder_discord_bot.utils.embeds import EmbedBuilder
from pathfinder_discord_bot.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SourcesView(ui.View):
    """View with button to show rulebook sources."""

    def __init__(self, search_results: list[dict]):
        super().__init__(timeout=300)  # 5 minute timeout
        self.search_results = search_results

    @ui.button(label="📚 View Sources", style=discord.ButtonStyle.secondary)
    async def show_sources(self, interaction: discord.Interaction, button: ui.Button):
        """Show the rulebook excerpts used for this answer."""
        if not self.search_results:
            await interaction.response.send_message(
                "No rulebook sources were used for this answer.",
                ephemeral=True,
            )
            return

        # Build source message as text (embeds are too large)
        message_parts = ["**📚 Rulebook Excerpts Used:**\n"]

        for i, result in enumerate(self.search_results, 1):
            source = result.get("source", "unknown").replace("_", " ").title()
            text = result.get("text", "")
            score = result.get("score", 0)
            chunk_idx = result.get("chunk_index", 0)

            # Truncate to fit Discord's 2000 char message limit per excerpt
            max_text_len = 600  # Keep it readable
            truncated_text = text[:max_text_len]
            if len(text) > max_text_len:
                truncated_text += "..."

            message_parts.append(
                f"\n**Source {i}** - {source} (Chunk #{chunk_idx}) - Relevance: {score:.1%}\n"
                f"```\n{truncated_text}\n```"
            )

        full_message = "\n".join(message_parts)

        # If message is too long, split it
        if len(full_message) > 2000:
            # Send first source only
            await interaction.response.send_message(
                message_parts[0] + message_parts[1],
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                full_message,
                ephemeral=True,
            )


class AskCog(commands.Cog):
    """Handles /ask command for PF2E rules Q&A."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.claude_service = ClaudeService(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
        self.rate_limiter = RateLimiter(
            max_requests=settings.ask_rate_limit_requests,
            window_seconds=settings.ask_rate_limit_window_seconds,
        )
        self.mongodb = MongoDBService(
            uri=settings.mongodb_uri,
            database_name=settings.mongodb_database,
        )
        self.embedding_service = EmbeddingService(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )

    @app_commands.command(name="ask", description="Ask a Pathfinder 2E rules question")
    @app_commands.describe(
        question="Your Pathfinder 2E rules question",
        silent="Reply only visible to you (default: False)",
    )
    async def ask(
        self,
        interaction: discord.Interaction,
        question: str,
        silent: bool = False,
    ):
        """Ask Claude a PF2E rules question with rulebook RAG context."""
        user_id = interaction.user.id

        try:
            # Check rate limit
            if self.rate_limiter.is_rate_limited(user_id):
                reset_time = self.rate_limiter.get_reset_time(user_id)
                minutes = int(reset_time / 60)
                seconds = int(reset_time % 60)

                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        f"Rate limit exceeded. Try again in {minutes}m {seconds}s.",
                        title="Too Many Requests",
                    ),
                    ephemeral=True,
                )
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return

            # Validate question length
            if len(question) < 10:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        "Please provide a more detailed question (at least 10 characters)."
                    ),
                    ephemeral=True,
                )
                return

            if len(question) > 500:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        "Question is too long. Please keep it under 500 characters."
                    ),
                    ephemeral=True,
                )
                return

            # Defer response since AI call takes time
            await interaction.response.defer(ephemeral=silent)

            # Record request for rate limiting
            self.rate_limiter.record_request(user_id)

            # Search rulebooks for relevant context
            logger.info("Searching rulebooks for context...")
            query_embedding_result = await self.embedding_service.embed_text(question)
            search_results = await self.mongodb.vector_search_rulebooks(
                query_embedding=query_embedding_result.embedding,
                limit=3,  # Top 3 most relevant chunks
            )

            # Format rulebook context if found
            rulebook_context = None
            if search_results:
                context_parts = []
                for i, result in enumerate(search_results, 1):
                    source = result.get("source", "unknown").replace("_", " ").title()
                    text = result.get("text", "")
                    score = result.get("score", 0)
                    context_parts.append(
                        f"[Excerpt {i} from {source} - Relevance: {score:.2f}]\n{text}"
                    )
                rulebook_context = "\n\n---\n\n".join(context_parts)
                logger.info(f"Found {len(search_results)} relevant rulebook chunks")

            # Get answer from Claude (with optional rulebook context)
            response = await self.claude_service.ask(question, rulebook_context=rulebook_context)

            # Save to MongoDB for eval tracking
            question_log = QuestionLog(
                question=question,
                response=response.content,
                user_id=user_id,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                estimated_cost=response.estimated_cost,
                response_time_ms=response.response_time_ms,
            )
            await self.mongodb.save_question_log(question_log)

            # Create embed response
            embed = discord.Embed(
                title="🎲 Pathfinder 2E Rules",
                description=response.content,
                color=EmbedBuilder.COLOR_INFO,
            )
            embed.add_field(
                name="Question",
                value=f"*{question}*",
                inline=False,
            )
            # Build footer (cost hidden from users but tracked in MongoDB)
            footer_text = f"Powered by The Network • Model: Claude"
            if search_results:
                footer_text += f" • 📚 {len(search_results)} rulebook excerpts"

            embed.set_footer(text=footer_text)

            # Add View Sources button if rulebook context was used
            view = SourcesView(search_results) if search_results else None

            await interaction.followup.send(embed=embed, view=view)

            logger.info(
                f"Question answered for user {user_id}: "
                f"{question[:50]}... ({response.total_tokens} tokens, ${response.estimated_cost:.4f})"
            )

        except Exception as e:
            logger.exception(f"Error in /ask command: {e}")

            # Try to send error message
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        embed=EmbedBuilder.error(
                            "An error occurred while processing your question. Please try again."
                        ),
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        embed=EmbedBuilder.error(
                            "An error occurred while processing your question. Please try again."
                        ),
                        ephemeral=True,
                    )
            except Exception:
                pass  # If we can't send error message, just log it


async def setup(bot: commands.Bot):
    """Load the AskCog."""
    await bot.add_cog(AskCog(bot))
