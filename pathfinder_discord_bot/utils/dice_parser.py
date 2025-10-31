"""Parser for dice notation strings like '2d20 + 1d6 + 5'."""
import re
from typing import NamedTuple


class DiceGroup(NamedTuple):
    """Represents a single dice group (e.g., '2d20')."""
    count: int
    sides: int


class ParsedDiceRoll(NamedTuple):
    """Result of parsing a dice notation string."""
    dice_groups: list[DiceGroup]
    modifier: int


class DiceParser:
    """Parses dice notation strings into structured data."""

    # Regex pattern for dice notation: 2d20, 3d6, etc.
    DICE_PATTERN = re.compile(r"(\d+)d(\d+)", re.IGNORECASE)
    # Pattern for modifiers: +5, -3, etc.
    MODIFIER_PATTERN = re.compile(r"([+-]\s*\d+)")

    @staticmethod
    def parse(notation: str) -> ParsedDiceRoll:
        """
        Parse dice notation string into groups and modifiers.

        Examples:
            "2d20 + 1d6 + 5" -> dice_groups=[(2, 20), (1, 6)], modifier=5
            "3d6-2" -> dice_groups=[(3, 6)], modifier=-2
            "1d20" -> dice_groups=[(1, 20)], modifier=0

        Args:
            notation: Dice notation string

        Returns:
            ParsedDiceRoll with dice groups and total modifier

        Raises:
            ValueError: If notation is invalid or empty
        """
        if not notation or not notation.strip():
            raise ValueError("Dice notation cannot be empty")

        # Remove all whitespace for easier parsing
        clean_notation = notation.replace(" ", "").lower()

        # Find all dice groups (e.g., 2d20, 1d6)
        dice_matches = DiceParser.DICE_PATTERN.findall(clean_notation)
        if not dice_matches:
            raise ValueError(
                "Invalid dice notation. Expected format like '2d20' or '1d6+5'"
            )

        dice_groups = []
        for count_str, sides_str in dice_matches:
            count = int(count_str)
            sides = int(sides_str)

            if count < 1 or count > 100:
                raise ValueError(f"Dice count must be between 1 and 100 (got {count})")
            if sides < 2:
                raise ValueError(f"Dice must have at least 2 sides (got {sides})")

            dice_groups.append(DiceGroup(count=count, sides=sides))

        # Find all modifiers (e.g., +5, -3)
        modifier_matches = DiceParser.MODIFIER_PATTERN.findall(clean_notation)
        total_modifier = sum(int(m.replace(" ", "")) for m in modifier_matches)

        return ParsedDiceRoll(dice_groups=dice_groups, modifier=total_modifier)

    @staticmethod
    def format_notation(parsed: ParsedDiceRoll) -> str:
        """
        Format a ParsedDiceRoll back into readable notation.

        Args:
            parsed: ParsedDiceRoll to format

        Returns:
            Formatted string like "2d20 + 1d6 + 5"
        """
        parts = []

        # Add dice groups
        for group in parsed.dice_groups:
            parts.append(f"{group.count}d{group.sides}")

        # Add modifier if non-zero
        if parsed.modifier != 0:
            parts.append(f"{parsed.modifier:+d}")

        return " ".join(parts)
