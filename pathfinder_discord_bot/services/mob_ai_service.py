"""Claude-powered mob AI for combat decisions and stat block retrieval via RAG."""
import json
import logging
import re
import time
from typing import Any, NamedTuple

from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from pathfinder_discord_bot.database.models import Combatant, CombatSession
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

MOB_AI_SYSTEM_PROMPT = """\
You are controlling a monster/NPC in a Pathfinder 2nd Edition combat encounter.
You will be given:
1. The monster's stat block (if available)
2. The current combat state (initiative order, HP, conditions)
3. Which action number this is (1, 2, or 3 — each creature gets 3 actions per turn)

Decide what the monster does with this action. Be tactically reasonable but not optimal — \
play the creature according to its intelligence and instincts.

Respond with ONLY a JSON object (no markdown fencing) in this format:
{
    "action_type": "strike" | "spell" | "move" | "skill" | "other",
    "description": "Short description of what the creature does",
    "target": "Name of the target (if applicable)",
    "attack_bonus": +N (if a strike, the creature's attack modifier),
    "damage_dice": "damage notation like 1d6+3" (if a strike that hits),
    "damage_type": "slashing" | "piercing" | etc. (if a strike),
    "save_dc": N (if the action requires a save),
    "save_type": "fortitude" | "reflex" | "will" (if save required),
    "effect_on_fail": "description of what happens on failed save",
    "notes": "any extra info (e.g., MAP applied, special abilities triggered)"
}

Only include fields that are relevant. For a simple Strike, you need: action_type, description, \
target, attack_bonus, damage_dice, damage_type. For movement, just action_type and description.

Important PF2E rules:
- Multiple Attack Penalty (MAP): -5 on 2nd attack, -10 on 3rd (or -4/-8 with agile weapons)
- Creatures with low intelligence (animal, mindless) attack the nearest threat
- Consider the creature's abilities from its stat block if available
"""


PLAYER_ACTION_SYSTEM_PROMPT = """\
You are the Game Master bot in a Pathfinder 2nd Edition combat encounter.
A player has described their action in free text. You have access to the mob stat blocks.

Your job is to interpret the player's action and resolve it using the mob's stats.

Respond with ONLY a JSON object (no markdown fencing):
{
    "understood": true,
    "action_type": "attack" | "save_effect" | "skill" | "other" | "not_action",
    "description": "Brief narration of what happens",
    "target": "name of the targeted mob (if any)",
    "attack_check": {
        "player_roll_total": N,
        "mob_ac": N,
        "result": "critical_hit" | "hit" | "miss" | "critical_miss"
    },
    "save_check": {
        "save_type": "fortitude" | "reflex" | "will",
        "mob_save_modifier": +N,
        "dc": N
    },
    "notes": "any extra context"
}

Rules for resolving:
- Only include "attack_check" if the player made an attack roll (they mention a number to hit)
- PF2E critical hit: nat 20, OR total >= AC + 10. Critical miss: nat 1, OR total <= AC - 10.
- Hit: total >= AC. Miss: total < AC.
- Only include "save_check" if the player's action forces a mob to make a saving throw
- For "save_check", extract the mob's save modifier from the stat block. The player must \
provide the DC (if they didn't, set dc to null and ask for it in the description).
- If the message is just chat/not an action, set action_type to "not_action" and understood to true
- If you can't determine the target or the action is ambiguous, set understood to false \
and explain in description

Important: Use the mob stat blocks to determine AC and save modifiers. \
If no stat block is available, say so in the description and set understood to false.
"""


class PlayerActionResult(NamedTuple):
    """Result of interpreting a player's free-text action."""

    understood: bool
    action_type: str  # "attack", "save_effect", "skill", "other", "not_action"
    description: str
    target: str | None
    # Attack resolution
    hit_result: str | None  # "critical_hit", "hit", "miss", "critical_miss"
    mob_ac: int | None
    # Save resolution
    save_type: str | None
    save_modifier: int | None
    save_dc: int | None
    notes: str | None
    raw_response: str


class MobDecision(NamedTuple):
    """Structured decision from the mob AI."""

    action_type: str
    description: str
    target: str | None
    attack_bonus: int | None
    damage_dice: str | None
    damage_type: str | None
    save_dc: int | None
    save_type: str | None
    effect_on_fail: str | None
    notes: str | None
    raw_response: str


class MobAIService:
    """Handles mob AI decisions using Claude and stat block retrieval via RAG."""

    def __init__(
        self,
        anthropic_api_key: str,
        model: str,
        embedding_service: EmbeddingService,
        mongodb_service: MongoDBService,
    ):
        self.client = AsyncAnthropic(api_key=anthropic_api_key)
        self.model = model
        self.embedding_service = embedding_service
        self.mongodb = mongodb_service
        # Cache stat blocks per combat to avoid repeated RAG lookups
        self._stat_block_cache: dict[str, str | None] = {}

    async def get_stat_block(self, mob_name: str) -> str | None:
        """Retrieve a mob's stat block via RAG search. Returns text or None."""
        cache_key = mob_name.lower()
        if cache_key in self._stat_block_cache:
            return self._stat_block_cache[cache_key]

        try:
            query = f"Pathfinder 2E stat block for {mob_name}"
            embedding_result = await self.embedding_service.embed_text(query)
            results = await self.mongodb.vector_search_rulebooks(
                query_embedding=embedding_result.embedding,
                limit=3,
            )

            if results:
                stat_block = "\n\n---\n\n".join(
                    r.get("text", "") for r in results
                )
                self._stat_block_cache[cache_key] = stat_block
                logger.info(f"Found stat block for {mob_name} via RAG")
                return stat_block

            logger.info(f"No stat block found for {mob_name}")
            self._stat_block_cache[cache_key] = None
            return None

        except Exception as e:
            logger.exception(f"Error fetching stat block for {mob_name}: {e}")
            return None

    def _format_combat_state(self, session: CombatSession) -> str:
        """Format the current combat state as a readable string for Claude."""
        lines = [f"Round {session.round_number}"]
        for i, c in enumerate(session.combatants):
            marker = ">>>" if i == session.current_turn_index else "   "
            hp_str = f"HP: {c.current_hp}/{c.max_hp}" if c.current_hp is not None else "HP: unknown"
            role = "PC" if c.is_player else "MOB"
            cond_str = ""
            if c.conditions:
                conds = [
                    f"{cd.name}{f' {cd.value}' if cd.value else ''}" for cd in c.conditions
                ]
                cond_str = f" [{', '.join(conds)}]"
            lines.append(f"{marker} {c.name} ({role}) — Init {c.initiative} — {hp_str}{cond_str}")
        return "\n".join(lines)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def decide_action(
        self,
        mob: Combatant,
        session: CombatSession,
        action_number: int,
        stat_block: str | None = None,
    ) -> MobDecision:
        """Ask Claude what the mob should do with its current action."""
        combat_state = self._format_combat_state(session)

        stat_block_section = ""
        if stat_block:
            stat_block_section = f"\n\nSTAT BLOCK:\n{stat_block}"
        else:
            stat_block_section = (
                f"\n\nNo stat block available for {mob.name}. "
                "Use reasonable defaults for a creature of this type."
            )

        user_message = (
            f"You are controlling: {mob.name}\n"
            f"Action {action_number} of 3 this turn.\n\n"
            f"COMBAT STATE:\n{combat_state}"
            f"{stat_block_section}"
        )

        try:
            start_time = time.time()
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=MOB_AI_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text if response.content else "{}"
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"Mob AI decision for {mob.name} action {action_number} ({elapsed}ms)")

            return self._parse_decision(raw_text)

        except Exception as e:
            logger.exception(f"Error getting mob AI decision: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def interpret_player_action(
        self,
        player_message: str,
        session: CombatSession,
        mob_stat_blocks: dict[str, str | None],
    ) -> PlayerActionResult:
        """Interpret a player's free-text action and resolve against mob stats."""
        combat_state = self._format_combat_state(session)

        # Build stat block section for all mobs
        stat_sections = []
        for mob_name, stat_block in mob_stat_blocks.items():
            if stat_block:
                stat_sections.append(f"--- {mob_name} ---\n{stat_block}")
            else:
                stat_sections.append(f"--- {mob_name} ---\nNo stat block available.")
        all_stats = "\n\n".join(stat_sections) if stat_sections else "No mob stat blocks available."

        user_message = (
            f"PLAYER MESSAGE: {player_message}\n\n"
            f"COMBAT STATE:\n{combat_state}\n\n"
            f"MOB STAT BLOCKS:\n{all_stats}"
        )

        try:
            start_time = time.time()
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system=PLAYER_ACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            raw_text = response.content[0].text if response.content else "{}"
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"Player action interpretation ({elapsed}ms)")

            return self._parse_player_action(raw_text)

        except Exception as e:
            logger.exception(f"Error interpreting player action: {e}")
            raise

    @staticmethod
    def _parse_player_action(raw_text: str) -> PlayerActionResult:
        """Parse Claude's JSON response into a PlayerActionResult."""
        json_text = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", json_text, re.DOTALL)
        if fence_match:
            json_text = fence_match.group(1).strip()

        try:
            data: dict[str, Any] = json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning(f"Player action AI returned non-JSON: {raw_text[:200]}")
            return PlayerActionResult(
                understood=False,
                action_type="other",
                description="Could not interpret that action.",
                target=None,
                hit_result=None,
                mob_ac=None,
                save_type=None,
                save_modifier=None,
                save_dc=None,
                notes=None,
                raw_response=raw_text,
            )

        # Extract attack check
        attack = data.get("attack_check") or {}
        hit_result = attack.get("result")
        mob_ac = attack.get("mob_ac")

        # Extract save check
        save = data.get("save_check") or {}
        save_type = save.get("save_type")
        save_modifier = save.get("mob_save_modifier")
        save_dc = save.get("dc")

        return PlayerActionResult(
            understood=data.get("understood", False),
            action_type=data.get("action_type", "other"),
            description=data.get("description", ""),
            target=data.get("target"),
            hit_result=hit_result,
            mob_ac=mob_ac,
            save_type=save_type,
            save_modifier=save_modifier,
            save_dc=save_dc,
            notes=data.get("notes"),
            raw_response=raw_text,
        )

    @staticmethod
    def _parse_decision(raw_text: str) -> MobDecision:
        """Parse Claude's JSON response into a MobDecision."""
        # Strip markdown code fences if present
        json_text = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", json_text, re.DOTALL)
        if fence_match:
            json_text = fence_match.group(1).strip()

        try:
            data: dict[str, Any] = json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning(f"Mob AI returned non-JSON: {raw_text[:200]}")
            return MobDecision(
                action_type="other",
                description=raw_text[:200],
                target=None,
                attack_bonus=None,
                damage_dice=None,
                damage_type=None,
                save_dc=None,
                save_type=None,
                effect_on_fail=None,
                notes="Failed to parse AI response as JSON",
                raw_response=raw_text,
            )

        return MobDecision(
            action_type=data.get("action_type", "other"),
            description=data.get("description", "The creature acts."),
            target=data.get("target"),
            attack_bonus=data.get("attack_bonus"),
            damage_dice=data.get("damage_dice"),
            damage_type=data.get("damage_type"),
            save_dc=data.get("save_dc"),
            save_type=data.get("save_type"),
            effect_on_fail=data.get("effect_on_fail"),
            notes=data.get("notes"),
            raw_response=raw_text,
        )
