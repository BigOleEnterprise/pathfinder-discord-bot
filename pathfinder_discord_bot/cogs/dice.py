"""Dice rolling cog for Pathfinder 2E."""
import logging
from discord import app_commands
from discord.ext import commands
from pathfinder_discord_bot.services import DiceService
from pathfinder_discord_bot.utils import EmbedBuilder

logger = logging.getLogger(__name__)


class DiceCog(commands.Cog):
    """Handles /roll command for dice rolling."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.dice_service = DiceService()

    @app_commands.command(name="roll", description="Roll dice for Pathfinder 2E")
    @app_commands.describe(
        dice='Dice notation (e.g., "2d20 + 1d6 + 5"). Defaults to "1d20" if not specified.',
        advantage="Roll with advantage (roll 2d20, keep highest)",
        disadvantage="Roll with disadvantage (roll 2d20, keep lowest)",
        comment="Label for this roll (e.g., 'Attack roll')",
        silent="Reply only visible to you",
    )
    async def roll(
        self,
        interaction,
        dice: str = "1d20",
        advantage: bool = False,
        disadvantage: bool = False,
        comment: str | None = None,
        silent: bool = False,
    ):
        """Roll dice using string notation with optional advantage/disadvantage."""
        try:
            # Validate comment length
            if comment and len(comment) > 100:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Comment must be 100 characters or less"),
                    ephemeral=True,
                )
                return

            # Validate advantage/disadvantage
            if advantage and disadvantage:
                await interaction.response.send_message(
                    embed=EmbedBuilder.error("Cannot use both advantage and disadvantage"),
                    ephemeral=True,
                )
                return

            # Roll with the dice service
            result = self.dice_service.roll_complex(
                dice, advantage=advantage, disadvantage=disadvantage
            )
            embed = EmbedBuilder.complex_dice_roll(result, comment)

            # Log the roll
            adv_dis = ""
            if advantage:
                adv_dis = " (advantage)"
            elif disadvantage:
                adv_dis = " (disadvantage)"
            logger.info(f"Dice roll: {dice}{adv_dis} = {result.final_total}")

            # Send result
            await interaction.response.send_message(embed=embed, ephemeral=silent)

        except ValueError as e:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(str(e)),
                ephemeral=True,
            )
            logger.warning(f"Invalid dice roll parameters: {e}")

        except Exception as e:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("An unexpected error occurred"),
                ephemeral=True,
            )
            logger.exception(f"Unexpected error in dice roll: {e}")


async def setup(bot: commands.Bot):
    """Load the DiceCog."""
    await bot.add_cog(DiceCog(bot))
