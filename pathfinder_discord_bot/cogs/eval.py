"""Eval command cog for evaluating RAG pipeline answer quality."""

import logging
from pathlib import Path

import discord
import yaml
from discord import app_commands
from discord.ext import commands

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.claude_service import ClaudeService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService
from pathfinder_discord_bot.services.rag_judge import RAGJudge
from pathfinder_discord_bot.utils.embeds import EmbedBuilder

logger = logging.getLogger(__name__)

EVAL_DATA_PATH = Path(__file__).parent.parent / "data" / "eval_questions.yaml"


def _load_eval_questions() -> list[dict]:
    """Load evaluation questions from YAML file."""
    if not EVAL_DATA_PATH.exists():
        logger.error(f"Eval questions file not found: {EVAL_DATA_PATH}")
        return []
    with open(EVAL_DATA_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("questions") or []


class EvalCog(commands.Cog):
    """Handles /eval-askbot command for RAG pipeline evaluation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.claude_service = ClaudeService(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
        self.mongodb = MongoDBService(
            uri=settings.mongodb_uri,
            database_name=settings.mongodb_database,
        )
        self.embedding_service = EmbeddingService(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )
        self.judge = RAGJudge(api_key=settings.anthropic_api_key)

    async def _run_rag_pipeline(self, question: str) -> tuple[str, list[dict]]:
        """Run the same RAG pipeline as /ask and return (answer, search_results).

        Replicates the logic from AskCog (ask.py lines 152-173).
        """
        # Embed the question
        query_embedding_result = await self.embedding_service.embed_text(question)

        # Vector search for relevant rulebook chunks
        search_results = await self.mongodb.vector_search_rulebooks(
            query_embedding=query_embedding_result.embedding,
            limit=3,
        )

        # Format rulebook context (same as ask.py)
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

        # Ask Claude
        response = await self.claude_service.ask(question, rulebook_context=rulebook_context)
        return response.content, search_results

    @app_commands.command(
        name="eval-askbot",
        description="Evaluate the /ask RAG pipeline against test questions (admin only)",
    )
    @app_commands.describe(
        question_id="Run a single question by ID (default: run all)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def eval_askbot(
        self,
        interaction: discord.Interaction,
        question_id: str | None = None,
    ):
        """Run evaluation questions through the RAG pipeline and judge the answers."""
        try:
            # Load questions
            all_questions = _load_eval_questions()
            if not all_questions:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error(
                        "No evaluation questions found. "
                        "Populate `data/eval_questions.yaml` with test questions."
                    ),
                    ephemeral=True,
                )
                return

            # Filter to single question if specified
            if question_id:
                questions = [q for q in all_questions if q["id"] == question_id]
                if not questions:
                    available = ", ".join(q["id"] for q in all_questions)
                    await interaction.response.send_message(
                        embed=EmbedBuilder.error(
                            f"Question ID `{question_id}` not found.\nAvailable: {available}"
                        ),
                        ephemeral=True,
                    )
                    return
            else:
                questions = all_questions

            # Defer — this will take a while
            await interaction.response.defer()

            passed_count = 0
            total_count = len(questions)

            for q in questions:
                qid = q["id"]
                question = q["question"]
                category = q.get("category", "uncategorized")
                required_info_points = q["required_info_points"]

                try:
                    # Run RAG pipeline
                    answer, search_results = await self._run_rag_pipeline(question)

                    # Judge the answer
                    verdict = await self.judge.evaluate(
                        question_id=qid,
                        question=question,
                        answer=answer,
                        required_info_points=required_info_points,
                    )

                    if verdict.passed:
                        passed_count += 1
                        embed = discord.Embed(
                            title=f"PASS — {qid}",
                            description=f"**Category:** {category}\n**Question:** {question}",
                            color=EmbedBuilder.COLOR_SUCCESS,
                        )
                        # Show covered points
                        points_text = "\n".join(f"  {v.info_point}" for v in verdict.verdicts)
                        embed.add_field(
                            name=f"All {len(verdict.verdicts)} info points covered",
                            value=points_text[:1024],
                            inline=False,
                        )
                    else:
                        embed = discord.Embed(
                            title=f"FAIL — {qid}",
                            description=f"**Category:** {category}\n**Question:** {question}",
                            color=EmbedBuilder.COLOR_ERROR,
                        )

                        # Show missed points
                        missed = [v for v in verdict.verdicts if not v.covered]
                        missed_text = "\n".join(
                            f"  {v.info_point}\n    *{v.explanation}*" for v in missed
                        )
                        embed.add_field(
                            name=f"Missed ({len(missed)}/{len(verdict.verdicts)})",
                            value=missed_text[:1024],
                            inline=False,
                        )

                        # Show covered points
                        covered = [v for v in verdict.verdicts if v.covered]
                        if covered:
                            covered_text = "\n".join(f"  {v.info_point}" for v in covered)
                            embed.add_field(
                                name=f"Covered ({len(covered)}/{len(verdict.verdicts)})",
                                value=covered_text[:1024],
                                inline=False,
                            )

                        # Show sources retrieved
                        if search_results:
                            sources_text = "\n".join(
                                f"  {r.get('source', '?')} (score={r.get('score', 0):.3f})"
                                for r in search_results
                            )
                            embed.add_field(
                                name="Sources Retrieved",
                                value=sources_text[:1024],
                                inline=False,
                            )

                        # Show truncated answer
                        embed.add_field(
                            name="Answer (truncated)",
                            value=answer[:1024],
                            inline=False,
                        )

                    await interaction.followup.send(embed=embed)

                except Exception as e:
                    logger.exception(f"Error evaluating question {qid}: {e}")
                    embed = discord.Embed(
                        title=f"ERROR — {qid}",
                        description=f"**Question:** {question}\n\n`{e}`",
                        color=EmbedBuilder.COLOR_WARNING,
                    )
                    await interaction.followup.send(embed=embed)

            # Summary embed
            all_passed = passed_count == total_count
            summary = discord.Embed(
                title="Eval Summary",
                description=f"**{passed_count}/{total_count}** questions passed",
                color=EmbedBuilder.COLOR_SUCCESS if all_passed else EmbedBuilder.COLOR_ERROR,
            )
            await interaction.followup.send(embed=summary)

            logger.info(f"Eval complete: {passed_count}/{total_count} passed")

        except Exception as e:
            logger.exception(f"Error in /eval-askbot command: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(
                        embed=EmbedBuilder.error(
                            "An error occurred during evaluation. Check bot logs."
                        ),
                    )
                else:
                    await interaction.response.send_message(
                        embed=EmbedBuilder.error(
                            "An error occurred during evaluation. Check bot logs."
                        ),
                        ephemeral=True,
                    )
            except Exception:
                pass


async def setup(bot: commands.Bot):
    """Load the EvalCog."""
    await bot.add_cog(EvalCog(bot))
