"""Discord embed builders for bot responses."""
import discord
from pathfinder_discord_bot.services.dice_service import ComplexDiceRollResult, DiceRollResult


class EmbedBuilder:
    """Creates formatted Discord embeds."""

    # Color palette (colorblind-friendly)
    COLOR_SUCCESS = 0x00D166  # Green
    COLOR_INFO = 0x5865F2     # Blurple
    COLOR_WARNING = 0xFEE75C  # Yellow
    COLOR_ERROR = 0xED4245    # Red

    @staticmethod
    def dice_roll(result: DiceRollResult, comment: str | None = None) -> discord.Embed:
        """
        Create embed for dice roll results.

        Args:
            result: DiceRollResult from dice service
            comment: Optional label for the roll

        Returns:
            Formatted Discord embed
        """
        title = f"🎲 {comment}" if comment else "🎲 Dice Roll"

        embed = discord.Embed(
            title=title,
            color=EmbedBuilder.COLOR_INFO,
        )

        # Show individual rolls
        rolls_display = ", ".join(str(r) for r in result.individual_rolls)
        embed.add_field(
            name="Rolls",
            value=f"`[{rolls_display}]`",
            inline=False,
        )

        # Show kept rolls if different from all rolls
        if result.kept_rolls != result.individual_rolls:
            kept_display = ", ".join(str(r) for r in result.kept_rolls)
            embed.add_field(
                name="Kept",
                value=f"`[{kept_display}]`",
                inline=False,
            )

        # Show calculation
        if result.modifier != 0:
            modifier_str = f"{result.modifier:+d}"
            calculation = f"{result.total} {modifier_str} = **{result.final_total}**"
        else:
            calculation = f"**{result.final_total}**"

        embed.add_field(
            name="Total",
            value=calculation,
            inline=False,
        )

        return embed

    @staticmethod
    def complex_dice_roll(
        result: ComplexDiceRollResult, comment: str | None = None
    ) -> discord.Embed:
        """
        Create embed for complex dice roll results with multiple dice groups.

        Args:
            result: ComplexDiceRollResult from dice service
            comment: Optional label for the roll

        Returns:
            Formatted Discord embed
        """
        title = f"🎲 {comment}" if comment else f"🎲 {result.notation}"

        embed = discord.Embed(
            title=title,
            color=EmbedBuilder.COLOR_INFO,
        )

        # Show each dice group
        for i, group in enumerate(result.groups):
            # Detect advantage/disadvantage (2 rolls for a single die)
            is_adv_dis = group.count == 1 and len(group.rolls) == 2

            if is_adv_dis:
                # Show both rolls with indication of which was kept
                roll1, roll2 = group.rolls
                kept = group.total
                dropped = roll1 if roll2 == kept else roll2

                rolls_display = f"~~{dropped}~~, **{kept}**"
                group_name = f"{group.count}d{group.sides} ({'Advantage' if kept > dropped else 'Disadvantage'})"
            else:
                # Normal display
                rolls_display = ", ".join(str(r) for r in group.rolls)
                group_name = f"{group.count}d{group.sides}"

            embed.add_field(
                name=group_name,
                value=f"`[{rolls_display}]` = **{group.total}**",
                inline=False,
            )

        # Show calculation
        parts = [str(group.total) for group in result.groups]
        if result.modifier != 0:
            parts.append(f"{result.modifier:+d}")

        calculation = " + ".join(parts) if len(parts) > 1 else parts[0]
        calculation += f" = **{result.final_total}**"

        embed.add_field(
            name="Total",
            value=calculation,
            inline=False,
        )

        return embed

    @staticmethod
    def error(message: str, title: str = "Error") -> discord.Embed:
        """Create error embed."""
        return discord.Embed(
            title=f"❌ {title}",
            description=message,
            color=EmbedBuilder.COLOR_ERROR,
        )
