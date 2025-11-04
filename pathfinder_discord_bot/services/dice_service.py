"""Dice rolling service with secure random generation."""
import secrets
from typing import NamedTuple


class DiceRollResult(NamedTuple):
    """Result of a dice roll operation."""
    individual_rolls: list[int]
    kept_rolls: list[int]
    total: int
    modifier: int
    final_total: int


class DiceGroupResult(NamedTuple):
    """Result of rolling a single dice group (e.g., 2d20)."""
    count: int
    sides: int
    rolls: list[int]
    total: int


class ComplexDiceRollResult(NamedTuple):
    """Result of a complex dice roll with multiple dice groups."""
    groups: list[DiceGroupResult]
    modifier: int
    subtotal: int
    final_total: int
    notation: str


class DiceService:
    """Handles dice rolling logic for Pathfinder 2E."""

    VALID_DICE_SIDES = {4, 6, 8, 10, 12, 20, 100}
    MAX_DICE = 100

    @staticmethod
    def roll(
        number_of_dice: int = 1,
        sides_of_dice: int = 20,
        modifier: int = 0,
        keep_highest: int = 0,
        keep_lowest: int = 0,
    ) -> DiceRollResult:
        """Roll dice with optional modifiers and keep mechanics (advantage/disadvantage)."""
        # Validate inputs
        if number_of_dice < 1 or number_of_dice > DiceService.MAX_DICE:
            raise ValueError(f"Number of dice must be between 1 and {DiceService.MAX_DICE}")

        if sides_of_dice < 2:
            raise ValueError("Dice must have at least 2 sides")

        if keep_highest > 0 and keep_lowest > 0:
            raise ValueError("Cannot use keep_highest and keep_lowest simultaneously")

        keep_count = keep_highest or keep_lowest
        if keep_count > number_of_dice:
            raise ValueError("Cannot keep more dice than rolled")

        # Roll dice using secure random
        rolls = [secrets.randbelow(sides_of_dice) + 1 for _ in range(number_of_dice)]

        # Determine which dice to keep
        if keep_highest > 0:
            kept = sorted(rolls, reverse=True)[:keep_highest]
        elif keep_lowest > 0:
            kept = sorted(rolls)[:keep_lowest]
        else:
            kept = rolls

        # Calculate totals
        roll_total = sum(kept)
        final_total = roll_total + modifier

        return DiceRollResult(
            individual_rolls=rolls,
            kept_rolls=kept,
            total=roll_total,
            modifier=modifier,
            final_total=final_total,
        )

    @staticmethod
    def roll_complex(
        notation: str, advantage: bool = False, disadvantage: bool = False
    ) -> ComplexDiceRollResult:
        """Roll multiple dice groups from notation string with optional advantage/disadvantage."""
        from pathfinder_discord_bot.utils.dice_parser import DiceParser

        # Parse the notation
        parsed = DiceParser.parse(notation)

        # Validate advantage/disadvantage usage
        if (advantage or disadvantage) and parsed.dice_groups:
            first_group = parsed.dice_groups[0]
            if first_group.count != 1:
                raise ValueError(
                    "Advantage/disadvantage only works with a single die "
                    f"(e.g., 1d20), not {first_group.count}d{first_group.sides}"
                )

        # Roll each dice group
        groups = []
        for i, dice_group in enumerate(parsed.dice_groups):
            # Handle advantage/disadvantage for first group only
            if i == 0 and (advantage or disadvantage):
                # Roll twice and keep highest or lowest
                roll1 = secrets.randbelow(dice_group.sides) + 1
                roll2 = secrets.randbelow(dice_group.sides) + 1

                if advantage:
                    kept_roll = max(roll1, roll2)
                    rolls = [roll1, roll2]  # Show both rolls
                else:  # disadvantage
                    kept_roll = min(roll1, roll2)
                    rolls = [roll1, roll2]  # Show both rolls

                group_total = kept_roll
            else:
                # Normal rolling
                rolls = [
                    secrets.randbelow(dice_group.sides) + 1
                    for _ in range(dice_group.count)
                ]
                group_total = sum(rolls)

            groups.append(
                DiceGroupResult(
                    count=dice_group.count,
                    sides=dice_group.sides,
                    rolls=rolls,
                    total=group_total,
                )
            )

        # Calculate totals
        subtotal = sum(group.total for group in groups)
        final_total = subtotal + parsed.modifier

        # Format notation for display
        formatted_notation = DiceParser.format_notation(parsed)

        return ComplexDiceRollResult(
            groups=groups,
            modifier=parsed.modifier,
            subtotal=subtotal,
            final_total=final_total,
            notation=formatted_notation,
        )
