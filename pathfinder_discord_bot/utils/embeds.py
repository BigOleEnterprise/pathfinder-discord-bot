"""Discord embed builders for bot responses."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from pathfinder_discord_bot.services.dice_service import ComplexDiceRollResult, DiceRollResult

if TYPE_CHECKING:
    from pathfinder_discord_bot.database.models import CombatSession


class EmbedBuilder:
    """Creates formatted Discord embeds."""

    # Color palette (colorblind-friendly)
    COLOR_SUCCESS = 0x00D166  # Green
    COLOR_INFO = 0x5865F2     # Blurple
    COLOR_WARNING = 0xFEE75C  # Yellow
    COLOR_ERROR = 0xED4245    # Red

    @staticmethod
    def dice_roll(result: DiceRollResult, comment: str | None = None) -> discord.Embed:
        """Create formatted embed for dice roll results with optional comment label."""
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
        """Create formatted embed for complex dice rolls with multiple dice groups."""
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

    # --- Combat embeds ---

    @staticmethod
    def combat_setup() -> discord.Embed:
        """Embed shown when a combat thread is first created."""
        embed = discord.Embed(
            title="⚔️ Combat Setup",
            description=(
                "Add players and mobs, then type **start** to begin.\n\n"
                "**Adding combatants:**\n"
                "`player <Name> init:<N>` — add a player character\n"
                "`mob <Name> hp:<N> init:<+mod>` — add a mob (bot rolls init)\n"
                "`mob <Name> hp:<N>` — add a mob (no init mod, rolls flat)\n\n"
                "**Once ready:**\n"
                "`start` — begin combat (sorts by initiative, starts round 1)\n"
                "`status` — show current setup\n"
                "`help` — show all commands"
            ),
            color=EmbedBuilder.COLOR_INFO,
        )
        return embed

    @staticmethod
    def combat_status(session: CombatSession) -> discord.Embed:
        """Build the main combat tracker embed."""
        if session.round_number == 0:
            title = "⚔️ Combat Setup"
        else:
            title = f"⚔️ Round {session.round_number}"

        lines = []
        for i, c in enumerate(session.combatants):
            # Turn indicator
            if session.round_number > 0 and i == session.current_turn_index:
                prefix = "▶ "
            else:
                prefix = "   "

            # Name and role
            role = "[PC]" if c.is_player else ""
            name_part = f"**{c.name}** {role}".strip()

            # HP
            if c.current_hp is not None and c.max_hp is not None:
                if c.current_hp == 0 and not c.is_player:
                    hp_part = "💀 DEAD"
                else:
                    hp_part = f"HP: {c.current_hp}/{c.max_hp}"
            else:
                hp_part = ""

            # Initiative
            init_part = f"Init: {c.initiative:g}"

            # Conditions
            cond_parts = []
            for cond in c.conditions:
                if cond.value is not None:
                    cond_parts.append(f"{cond.name} {cond.value}")
                else:
                    cond_parts.append(cond.name)
            cond_str = f" [{', '.join(cond_parts)}]" if cond_parts else ""

            # Assemble line
            parts = [name_part, init_part]
            if hp_part:
                parts.append(hp_part)
            line = f"{prefix}{' — '.join(parts)}{cond_str}"
            lines.append(line)

        description = "\n".join(lines) if lines else "*No combatants yet.*"

        embed = discord.Embed(
            title=title,
            description=description,
            color=EmbedBuilder.COLOR_INFO,
        )

        if session.round_number > 0 and session.combatants:
            current = session.combatants[session.current_turn_index]
            phase_text = "Player's turn" if current.is_player else "Mob's turn (bot-controlled)"
            embed.set_footer(text=f"{current.name}'s turn — {phase_text}")

        return embed

    @staticmethod
    def combat_action(description: str, session: CombatSession | None = None) -> discord.Embed:
        """Embed for a combat action result."""
        embed = discord.Embed(
            description=description,
            color=EmbedBuilder.COLOR_SUCCESS,
        )
        return embed

    @staticmethod
    def combat_mob_action(
        mob_name: str,
        action_number: int,
        description: str,
        *,
        roll_result: int | None = None,
        target: str | None = None,
        waiting_for: str | None = None,
    ) -> discord.Embed:
        """Embed for a mob AI action."""
        title = f"🗡️ {mob_name} — Action {action_number}/3"
        parts = [description]
        if roll_result is not None and target:
            parts.append(f"\n🎲 Rolls **{roll_result}** against {target}")
        if waiting_for:
            parts.append(f"\n*{waiting_for}*")

        embed = discord.Embed(
            title=title,
            description="\n".join(parts),
            color=EmbedBuilder.COLOR_WARNING,
        )
        return embed

    @staticmethod
    def combat_help() -> discord.Embed:
        """Embed listing all combat thread commands."""
        embed = discord.Embed(
            title="⚔️ Combat Commands",
            color=EmbedBuilder.COLOR_INFO,
        )
        embed.add_field(
            name="Setup",
            value=(
                "`player <Name> init:<N>` — add player\n"
                "`mob <Name> hp:<N> init:<+mod>` — add mob\n"
                "`start` — begin combat\n"
                "`remove <Name>` — remove combatant"
            ),
            inline=False,
        )
        embed.add_field(
            name="During Combat",
            value=(
                "`next` / `n` — advance turn\n"
                "`done` / `d` — end your turn (same as next)\n"
                "`damage <Name> <N>` — deal damage\n"
                "`heal <Name> <N>` — heal\n"
                "`condition <Name> <cond> [val]` — add condition\n"
                "`remove-condition <Name> <cond>` — remove condition\n"
                "`roll <notation>` — roll dice\n"
                "`status` / `s` — show combat state"
            ),
            inline=False,
        )
        embed.add_field(
            name="Mob Turn Responses",
            value=(
                "`hit` / `miss` — confirm attack result\n"
                "`pass` / `fail` — confirm save result"
            ),
            inline=False,
        )
        embed.add_field(
            name="End",
            value="`/end-combat` — end combat and archive thread",
            inline=False,
        )
        return embed
