"""Combat state management service."""
import logging
import secrets
from datetime import datetime

from pathfinder_discord_bot.database.models import (
    Combatant,
    CombatSession,
    Condition,
    TurnPhase,
)

logger = logging.getLogger(__name__)


class CombatService:
    """Handles combat state transitions: adding combatants, damage, healing, turns."""

    def create_session(
        self,
        thread_id: int,
        channel_id: int,
        guild_id: int,
        creator_id: int,
    ) -> CombatSession:
        """Create a new combat session in setup phase."""
        return CombatSession(
            thread_id=thread_id,
            channel_id=channel_id,
            guild_id=guild_id,
            creator_id=creator_id,
        )

    def add_combatant(
        self,
        session: CombatSession,
        name: str,
        initiative: float,
        *,
        is_player: bool = True,
        max_hp: int | None = None,
        initiative_modifier: int = 0,
    ) -> CombatSession:
        """Add a combatant and re-sort by initiative."""
        # Check for duplicate names
        existing = [c.name.lower() for c in session.combatants]
        if name.lower() in existing:
            raise ValueError(f"A combatant named '{name}' already exists.")

        combatant = Combatant(
            name=name,
            initiative=initiative,
            initiative_modifier=initiative_modifier,
            is_player=is_player,
            max_hp=max_hp,
            current_hp=max_hp,
        )
        session.combatants.append(combatant)
        self._sort_initiative(session)
        session.updated_at = datetime.utcnow()
        return session

    def remove_combatant(self, session: CombatSession, name: str) -> CombatSession:
        """Remove a combatant by name."""
        idx = self._find_combatant(session, name)
        removed = session.combatants.pop(idx)

        # Adjust turn index if needed
        if session.round_number > 0 and session.combatants:
            if idx < session.current_turn_index:
                session.current_turn_index -= 1
            elif idx == session.current_turn_index:
                if session.current_turn_index >= len(session.combatants):
                    session.current_turn_index = 0
        session.updated_at = datetime.utcnow()
        logger.info(f"Removed combatant: {removed.name}")
        return session

    def apply_damage(
        self, session: CombatSession, name: str, amount: int
    ) -> tuple[CombatSession, str]:
        """Apply damage to a mob combatant. Returns session and description."""
        combatant = self._get_combatant(session, name)
        if combatant.current_hp is None:
            raise ValueError(f"{combatant.name} doesn't have tracked HP (player character).")

        old_hp = combatant.current_hp
        combatant.current_hp = max(0, combatant.current_hp - amount)
        desc = f"{combatant.name} takes {amount} damage ({old_hp} -> {combatant.current_hp} HP)"

        if combatant.current_hp == 0 and not combatant.is_player:
            desc += " -- DEAD"

        session.updated_at = datetime.utcnow()
        return session, desc

    def apply_healing(
        self, session: CombatSession, name: str, amount: int
    ) -> tuple[CombatSession, str]:
        """Apply healing to a mob combatant. Returns session and description."""
        combatant = self._get_combatant(session, name)
        if combatant.current_hp is None or combatant.max_hp is None:
            raise ValueError(f"{combatant.name} doesn't have tracked HP (player character).")

        old_hp = combatant.current_hp
        combatant.current_hp = min(combatant.max_hp, combatant.current_hp + amount)
        desc = f"{combatant.name} heals {amount} ({old_hp} -> {combatant.current_hp} HP)"
        session.updated_at = datetime.utcnow()
        return session, desc

    def add_condition(
        self,
        session: CombatSession,
        name: str,
        condition_name: str,
        value: int | None = None,
    ) -> CombatSession:
        """Add a condition to a combatant."""
        combatant = self._get_combatant(session, name)

        # Replace if already exists
        combatant.conditions = [
            c for c in combatant.conditions if c.name.lower() != condition_name.lower()
        ]
        combatant.conditions.append(Condition(name=condition_name, value=value))
        session.updated_at = datetime.utcnow()
        return session

    def remove_condition(
        self, session: CombatSession, name: str, condition_name: str
    ) -> CombatSession:
        """Remove a condition from a combatant."""
        combatant = self._get_combatant(session, name)
        before = len(combatant.conditions)
        combatant.conditions = [
            c for c in combatant.conditions if c.name.lower() != condition_name.lower()
        ]
        if len(combatant.conditions) == before:
            raise ValueError(f"{combatant.name} doesn't have condition '{condition_name}'.")
        session.updated_at = datetime.utcnow()
        return session

    def start_combat(self, session: CombatSession) -> CombatSession:
        """Transition from setup to round 1."""
        if not session.combatants:
            raise ValueError("Add at least one combatant before starting.")
        self._sort_initiative(session)
        session.round_number = 1
        session.current_turn_index = 0
        current = session.combatants[0]
        session.turn_phase = (
            TurnPhase.PLAYER_ACTING if current.is_player else TurnPhase.MOB_DECIDING
        )
        session.updated_at = datetime.utcnow()
        return session

    def advance_turn(self, session: CombatSession) -> CombatSession:
        """Advance to the next combatant's turn."""
        if not session.combatants:
            raise ValueError("No combatants in combat.")

        # Tick down conditions for the combatant whose turn just ended
        self._tick_conditions(session.combatants[session.current_turn_index])

        session.current_turn_index += 1
        if session.current_turn_index >= len(session.combatants):
            session.current_turn_index = 0
            session.round_number += 1

        current = session.combatants[session.current_turn_index]
        session.turn_phase = (
            TurnPhase.PLAYER_ACTING if current.is_player else TurnPhase.MOB_DECIDING
        )
        session.pending_action = {}
        session.updated_at = datetime.utcnow()
        return session

    def get_current_combatant(self, session: CombatSession) -> Combatant | None:
        """Get the combatant whose turn it currently is."""
        if not session.combatants or session.round_number == 0:
            return None
        if session.current_turn_index >= len(session.combatants):
            return None
        return session.combatants[session.current_turn_index]

    @staticmethod
    def roll_initiative(modifier: int = 0) -> int:
        """Roll 1d20 + modifier for initiative."""
        return secrets.randbelow(20) + 1 + modifier

    # --- Private helpers ---

    def _sort_initiative(self, session: CombatSession) -> None:
        """Sort combatants by initiative descending, modifier as tiebreaker."""
        session.combatants.sort(
            key=lambda c: (c.initiative, c.initiative_modifier),
            reverse=True,
        )

    def _find_combatant(self, session: CombatSession, name: str) -> int:
        """Find combatant index by name (case-insensitive). Raises ValueError."""
        for i, c in enumerate(session.combatants):
            if c.name.lower() == name.lower():
                return i
        raise ValueError(f"No combatant named '{name}'.")

    def _get_combatant(self, session: CombatSession, name: str) -> Combatant:
        """Get combatant by name (case-insensitive). Raises ValueError."""
        idx = self._find_combatant(session, name)
        return session.combatants[idx]

    @staticmethod
    def _tick_conditions(combatant: Combatant) -> None:
        """Tick down condition values at end of turn (PF2E: frightened reduces by 1, etc.)."""
        remaining = []
        for cond in combatant.conditions:
            if cond.value is not None and cond.value > 0:
                cond.value -= 1
                if cond.value > 0:
                    remaining.append(cond)
                # value hit 0 -> condition removed
            elif cond.duration is not None and cond.duration > 0:
                cond.duration -= 1
                if cond.duration > 0:
                    remaining.append(cond)
            else:
                remaining.append(cond)
        combatant.conditions = remaining
