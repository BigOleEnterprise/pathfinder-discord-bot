"""Parser for free-text combat commands in Discord threads."""
import re
from typing import NamedTuple


class CombatCommand(NamedTuple):
    """Parsed combat command from a thread message."""

    action: str  # add_player, add_mob, damage, heal, condition, remove_condition,
    #              remove, next, status, end, done, hit, miss, pass, fail, roll
    target: str | None  # combatant name
    value: int | None  # damage/heal amount, condition value, etc.
    extra: dict  # additional args (hp, init, condition name, dice notation, etc.)


# Regex for "add player <Name> init:<N>" or "player <Name> init:<N>"
_PLAYER_RE = re.compile(
    r"^(?:add\s+)?player\s+(.+?)\s+init[:\s]+([+-]?\d+)$",
    re.IGNORECASE,
)

# Regex for "add mob <Name>" or "mob <Name>" with optional hp:<N> and init:<+N>
_MOB_RE = re.compile(
    r"^(?:add\s+)?mob\s+(.+?)(?:\s+hp[:\s]+(\d+))?(?:\s+init[:\s]+([+-]?\d+))?$",
    re.IGNORECASE,
)

# Regex for "damage <Name> <N>" or "dmg <Name> <N>"
_DAMAGE_RE = re.compile(r"^(?:damage|dmg)\s+(.+?)\s+(\d+)$", re.IGNORECASE)

# Regex for "heal <Name> <N>"
_HEAL_RE = re.compile(r"^(?:heal)\s+(.+?)\s+(\d+)$", re.IGNORECASE)

# Regex for "condition <Name> <condition_name> [value]"
_CONDITION_RE = re.compile(
    r"^condition\s+(.+?)\s+(\w+)(?:\s+(\d+))?$",
    re.IGNORECASE,
)

# Regex for "remove-condition <Name> <condition_name>"
_REMOVE_CONDITION_RE = re.compile(
    r"^remove[- ]condition\s+(.+?)\s+(\w+)$",
    re.IGNORECASE,
)

# Regex for "remove <Name>"
_REMOVE_RE = re.compile(r"^remove\s+(.+)$", re.IGNORECASE)

# Regex for "roll <notation>"
_ROLL_RE = re.compile(r"^roll\s+(.+)$", re.IGNORECASE)


class CombatParser:
    """Parses free-text messages into structured combat commands."""

    @staticmethod
    def parse(message: str) -> CombatCommand | None:
        """Parse a message into a CombatCommand, or None if not a combat command."""
        text = message.strip()
        if not text:
            return None

        lower = text.lower()

        # Simple single-word commands
        if lower in ("next", "n"):
            return CombatCommand(action="next", target=None, value=None, extra={})
        if lower in ("status", "s"):
            return CombatCommand(action="status", target=None, value=None, extra={})
        if lower in ("done", "d"):
            return CombatCommand(action="done", target=None, value=None, extra={})
        if lower == "start":
            return CombatCommand(action="start", target=None, value=None, extra={})
        if lower == "help":
            return CombatCommand(action="help", target=None, value=None, extra={})

        # Hit/miss confirmation
        if lower == "hit":
            return CombatCommand(action="hit", target=None, value=None, extra={})
        if lower == "miss":
            return CombatCommand(action="miss", target=None, value=None, extra={})
        if lower in ("pass", "save"):
            return CombatCommand(action="pass", target=None, value=None, extra={})
        if lower in ("fail",):
            return CombatCommand(action="fail", target=None, value=None, extra={})

        # Player: "player Valeros init:18"
        m = _PLAYER_RE.match(text)
        if m:
            return CombatCommand(
                action="add_player",
                target=m.group(1).strip(),
                value=None,
                extra={"initiative": int(m.group(2))},
            )

        # Mob: "mob Goblin Warrior hp:30 init:+4"
        m = _MOB_RE.match(text)
        if m:
            extra: dict = {}
            if m.group(2):
                extra["hp"] = int(m.group(2))
            if m.group(3):
                extra["initiative_modifier"] = int(m.group(3))
            return CombatCommand(
                action="add_mob",
                target=m.group(1).strip(),
                value=None,
                extra=extra,
            )

        # Damage
        m = _DAMAGE_RE.match(text)
        if m:
            return CombatCommand(
                action="damage",
                target=m.group(1).strip(),
                value=int(m.group(2)),
                extra={},
            )

        # Heal
        m = _HEAL_RE.match(text)
        if m:
            return CombatCommand(
                action="heal",
                target=m.group(1).strip(),
                value=int(m.group(2)),
                extra={},
            )

        # Condition
        m = _CONDITION_RE.match(text)
        if m:
            extra = {"condition_name": m.group(2).lower()}
            val = int(m.group(3)) if m.group(3) else None
            return CombatCommand(
                action="condition",
                target=m.group(1).strip(),
                value=val,
                extra=extra,
            )

        # Remove condition
        m = _REMOVE_CONDITION_RE.match(text)
        if m:
            return CombatCommand(
                action="remove_condition",
                target=m.group(1).strip(),
                value=None,
                extra={"condition_name": m.group(2).lower()},
            )

        # Remove combatant
        m = _REMOVE_RE.match(text)
        if m:
            return CombatCommand(
                action="remove",
                target=m.group(1).strip(),
                value=None,
                extra={},
            )

        # Roll dice
        m = _ROLL_RE.match(text)
        if m:
            return CombatCommand(
                action="roll",
                target=None,
                value=None,
                extra={"notation": m.group(1).strip()},
            )

        # Not a recognized command
        return None

    @staticmethod
    def resolve_name(query: str, names: list[str]) -> str | None:
        """Resolve a partial name to a full combatant name.

        Returns the name if unambiguous, None if no match or ambiguous.
        """
        query_lower = query.lower()

        # Exact match first
        for name in names:
            if name.lower() == query_lower:
                return name

        # Prefix match
        matches = [n for n in names if n.lower().startswith(query_lower)]
        if len(matches) == 1:
            return matches[0]

        # Substring match
        if not matches:
            matches = [n for n in names if query_lower in n.lower()]
            if len(matches) == 1:
                return matches[0]

        return None
