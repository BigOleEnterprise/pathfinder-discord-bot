"""Main entry point for the Pathfinder Discord bot."""
import asyncio
import logging
from pathlib import Path
import discord
from discord.ext import commands
from pathfinder_discord_bot.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PathfinderBot(commands.Bot):
    """Pathfinder 2E Discord bot."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Required for certain features

        super().__init__(
            command_prefix="!",  # Fallback prefix (we use slash commands)
            intents=intents,
        )

    async def setup_hook(self):
        """Load cogs and sync commands."""
        # Load all cogs from the cogs directory
        cogs_dir = Path(__file__).parent / "cogs"
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.stem != "__init__":
                try:
                    await self.load_extension(f"pathfinder_discord_bot.cogs.{cog_file.stem}")
                    logger.info(f"Loaded cog: {cog_file.stem}")
                except Exception as e:
                    logger.exception(f"Failed to load cog {cog_file.stem}: {e}")

        # Sync commands to Discord
        # Always sync globally for all servers (takes up to 1 hour to propagate)
        await self.tree.sync()
        logger.info("Commands synced globally")

        # Also sync to specific guilds for instant updates during dev
        if settings.guild_id_list:
            for guild_id in settings.guild_id_list:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Commands synced to guild {guild_id} (instant)")

    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        logger.info("Bot is ready!")


async def main():
    """Run the bot."""
    bot = PathfinderBot()

    try:
        await bot.start(settings.discord_bot_token)
    except KeyboardInterrupt:
        logger.info("Shutting down bot...")
        await bot.close()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
