"""Combat cog — /combat, /end-combat, and thread message listener."""
import asyncio
import logging
import secrets

import discord
from discord import app_commands
from discord.ext import commands

from pathfinder_discord_bot.config import settings
from pathfinder_discord_bot.database.models import CombatSession, TurnPhase
from pathfinder_discord_bot.database.mongodb_service import MongoDBService
from pathfinder_discord_bot.services.combat_service import CombatService
from pathfinder_discord_bot.services.dice_service import DiceService
from pathfinder_discord_bot.services.embedding_service import EmbeddingService
from pathfinder_discord_bot.services.mob_ai_service import MobAIService
from pathfinder_discord_bot.utils.combat_parser import CombatParser
from pathfinder_discord_bot.utils.embeds import EmbedBuilder

logger = logging.getLogger(__name__)


class CombatCog(commands.Cog):
    """Handles /combat, /end-combat, and the in-thread combat loop."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.combat_service = CombatService()
        self.dice_service = DiceService()
        self.active_combats: dict[int, CombatSession] = {}  # thread_id -> session
        self._locks: dict[int, asyncio.Lock] = {}  # thread_id -> lock

        self.mongodb = MongoDBService(
            uri=settings.mongodb_uri,
            database_name=settings.mongodb_database,
        )
        self.embedding_service = EmbeddingService(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )
        self.mob_ai = MobAIService(
            anthropic_api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            embedding_service=self.embedding_service,
            mongodb_service=self.mongodb,
        )

    async def cog_load(self) -> None:
        """Rehydrate active combats from MongoDB on startup."""
        try:
            active = await self.mongodb.get_active_combats()
            for doc in active:
                session = CombatSession.from_mongo_dict(doc)
                self.active_combats[session.thread_id] = session
                self._locks[session.thread_id] = asyncio.Lock()
            if active:
                logger.info(f"Rehydrated {len(active)} active combats from MongoDB")
        except Exception as e:
            logger.exception(f"Error rehydrating combats: {e}")

    def _get_lock(self, thread_id: int) -> asyncio.Lock:
        if thread_id not in self._locks:
            self._locks[thread_id] = asyncio.Lock()
        return self._locks[thread_id]

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    @app_commands.command(name="combat", description="Start a new combat encounter in a thread")
    @app_commands.describe(name="Name for this combat encounter")
    async def combat(self, interaction: discord.Interaction, name: str = "Combat Encounter"):
        """Create a combat thread and enter setup phase."""
        # Guard: max active combats per guild
        guild_id = interaction.guild_id
        guild_count = sum(
            1 for s in self.active_combats.values() if s.guild_id == guild_id
        )
        if guild_count >= settings.combat_max_active_per_guild:
            await interaction.response.send_message(
                embed=EmbedBuilder.error(
                    f"This server already has {guild_count} active combats "
                    f"(max {settings.combat_max_active_per_guild}). "
                    "End one with `/end-combat` first."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        thread = await interaction.channel.create_thread(
            name=f"⚔️ {name}",
            auto_archive_duration=60,
            type=discord.ChannelType.public_thread,
        )

        session = self.combat_service.create_session(
            thread_id=thread.id,
            channel_id=interaction.channel_id,
            guild_id=guild_id,
            creator_id=interaction.user.id,
        )
        self.active_combats[thread.id] = session
        self._locks[thread.id] = asyncio.Lock()

        await self.mongodb.save_combat_session(session)
        await thread.send(embed=EmbedBuilder.combat_setup())
        await interaction.followup.send(
            f"Combat started! Head to {thread.mention} to set up your encounter."
        )
        logger.info(f"Combat '{name}' created in thread {thread.id} by user {interaction.user.id}")

    @app_commands.command(name="end-combat", description="End the combat in the current thread")
    async def end_combat(self, interaction: discord.Interaction):
        """End the active combat in this thread."""
        thread_id = interaction.channel_id

        if thread_id not in self.active_combats:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("No active combat in this thread/channel."),
                ephemeral=True,
            )
            return

        session = self.active_combats[thread_id]

        # Only creator or admins can end
        is_admin = interaction.user.guild_permissions.administrator
        if interaction.user.id != session.creator_id and not is_admin:
            await interaction.response.send_message(
                embed=EmbedBuilder.error("Only the combat creator or an admin can end combat."),
                ephemeral=True,
            )
            return

        await self._cleanup_combat(thread_id)

        rounds = session.round_number if session.round_number > 0 else 0
        embed = discord.Embed(
            title="⚔️ Combat Ended",
            description=f"Combat concluded after {rounds} round(s).",
            color=EmbedBuilder.COLOR_INFO,
        )
        await interaction.response.send_message(embed=embed)
        logger.info(f"Combat ended in thread {thread_id}")

    async def _cleanup_combat(self, thread_id: int) -> None:
        """Remove combat from tracking and persist final state."""
        await self.mongodb.end_combat_session(thread_id)
        self.active_combats.pop(thread_id, None)
        self._locks.pop(thread_id, None)

    # ------------------------------------------------------------------
    # Message listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for combat commands in active combat threads."""
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.Thread):
            return
        if message.channel.id not in self.active_combats:
            return

        thread = message.channel
        lock = self._get_lock(thread.id)
        command = CombatParser.parse(message.content)

        async with lock:
            session = self.active_combats[thread.id]
            try:
                if command is not None:
                    await self._dispatch(message, thread, session, command)
                elif (
                    session.turn_phase == TurnPhase.PLAYER_ACTING
                    and session.round_number > 0
                ):
                    # Free-text during player turn — interpret via Claude
                    await self._handle_player_free_text(thread, session, message.content)
                else:
                    return  # Not a command and not a player turn — ignore
                # Persist after every state change
                await self.mongodb.save_combat_session(session)
            except ValueError as e:
                await thread.send(embed=EmbedBuilder.error(str(e)))
            except Exception as e:
                logger.exception(f"Error handling combat command: {e}")
                await thread.send(
                    embed=EmbedBuilder.error("An error occurred processing that command.")
                )

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, message, thread, session: CombatSession, command):
        """Route a parsed command to the appropriate handler."""
        action = command.action

        # --- Setup-phase commands ---
        if action == "add_player":
            await self._handle_add_player(thread, session, command)
        elif action == "add_mob":
            await self._handle_add_mob(thread, session, command)
        elif action == "start":
            await self._handle_start(thread, session)
        elif action == "help":
            await thread.send(embed=EmbedBuilder.combat_help())

        # --- Active combat commands ---
        elif action in ("next", "done"):
            await self._handle_next(thread, session)
        elif action == "damage":
            await self._handle_damage(thread, session, command)
        elif action == "heal":
            await self._handle_heal(thread, session, command)
        elif action == "condition":
            await self._handle_condition(thread, session, command)
        elif action == "remove_condition":
            await self._handle_remove_condition(thread, session, command)
        elif action == "remove":
            await self._handle_remove(thread, session, command)
        elif action == "status":
            await thread.send(embed=EmbedBuilder.combat_status(session))
        elif action == "roll":
            await self._handle_roll(thread, command)

        # --- Mob turn confirmations ---
        elif action in ("hit", "miss", "pass", "fail"):
            await self._handle_confirmation(thread, session, action)

    # ------------------------------------------------------------------
    # Setup handlers
    # ------------------------------------------------------------------

    async def _handle_add_player(self, thread, session: CombatSession, command):
        if session.round_number > 0:
            raise ValueError("Combat already started. Cannot add players mid-combat.")
        if len(session.combatants) >= settings.combat_max_combatants:
            raise ValueError(f"Max {settings.combat_max_combatants} combatants reached.")

        name = command.target
        initiative = command.extra["initiative"]
        self.combat_service.add_combatant(
            session, name, initiative, is_player=True
        )
        await thread.send(
            embed=EmbedBuilder.combat_action(f"✅ Added player **{name}** (init {initiative})")
        )
        await thread.send(embed=EmbedBuilder.combat_status(session))

    async def _handle_add_mob(self, thread, session: CombatSession, command):
        if session.round_number > 0:
            raise ValueError("Combat already started. Cannot add mobs mid-combat.")
        if len(session.combatants) >= settings.combat_max_combatants:
            raise ValueError(f"Max {settings.combat_max_combatants} combatants reached.")

        name = command.target
        hp = command.extra.get("hp")
        init_mod = command.extra.get("initiative_modifier", 0)
        initiative = CombatService.roll_initiative(init_mod)

        self.combat_service.add_combatant(
            session,
            name,
            initiative,
            is_player=False,
            max_hp=hp,
            initiative_modifier=init_mod,
        )

        hp_str = f", HP {hp}" if hp else ""
        await thread.send(
            embed=EmbedBuilder.combat_action(
                f"✅ Added mob **{name}** (rolled init: 🎲 **{initiative}**{hp_str})"
            )
        )
        await thread.send(embed=EmbedBuilder.combat_status(session))

    async def _handle_start(self, thread, session: CombatSession):
        self.combat_service.start_combat(session)
        await thread.send(embed=EmbedBuilder.combat_status(session))

        # If first turn is a mob, kick off mob AI
        current = self.combat_service.get_current_combatant(session)
        if current and not current.is_player:
            await self._run_mob_turn(thread, session)

    # ------------------------------------------------------------------
    # Active combat handlers
    # ------------------------------------------------------------------

    async def _handle_next(self, thread, session: CombatSession):
        if session.round_number == 0:
            raise ValueError("Combat hasn't started yet. Type `start` first.")

        self.combat_service.advance_turn(session)
        await thread.send(embed=EmbedBuilder.combat_status(session))

        # If next turn is a mob, kick off mob AI
        current = self.combat_service.get_current_combatant(session)
        if current and not current.is_player:
            await self._run_mob_turn(thread, session)

    async def _handle_damage(self, thread, session: CombatSession, command):
        name = self._resolve_target(session, command.target)
        session, desc = self.combat_service.apply_damage(session, name, command.value)
        await thread.send(embed=EmbedBuilder.combat_action(desc))

    async def _handle_heal(self, thread, session: CombatSession, command):
        name = self._resolve_target(session, command.target)
        session, desc = self.combat_service.apply_healing(session, name, command.value)
        await thread.send(embed=EmbedBuilder.combat_action(desc))

    async def _handle_condition(self, thread, session: CombatSession, command):
        name = self._resolve_target(session, command.target)
        cond_name = command.extra["condition_name"]
        self.combat_service.add_condition(session, name, cond_name, command.value)
        val_str = f" {command.value}" if command.value else ""
        await thread.send(
            embed=EmbedBuilder.combat_action(
                f"Added **{cond_name}{val_str}** to {name}"
            )
        )

    async def _handle_remove_condition(self, thread, session: CombatSession, command):
        name = self._resolve_target(session, command.target)
        cond_name = command.extra["condition_name"]
        self.combat_service.remove_condition(session, name, cond_name)
        await thread.send(
            embed=EmbedBuilder.combat_action(f"Removed **{cond_name}** from {name}")
        )

    async def _handle_remove(self, thread, session: CombatSession, command):
        name = self._resolve_target(session, command.target)
        self.combat_service.remove_combatant(session, name)
        await thread.send(embed=EmbedBuilder.combat_action(f"Removed **{name}** from combat"))

    async def _handle_roll(self, thread, command):
        notation = command.extra["notation"]
        result = self.dice_service.roll_complex(notation)
        embed = EmbedBuilder.complex_dice_roll(result)
        await thread.send(embed=embed)

    # ------------------------------------------------------------------
    # Player free-text interpretation
    # ------------------------------------------------------------------

    async def _handle_player_free_text(
        self, thread, session: CombatSession, text: str
    ):
        """Send player's free-text action to Claude for resolution against mob stats."""
        # Gather stat blocks for all mobs in combat
        mob_stat_blocks: dict[str, str | None] = {}
        for c in session.combatants:
            if not c.is_player:
                mob_stat_blocks[c.name] = await self.mob_ai.get_stat_block(c.name)

        result = await self.mob_ai.interpret_player_action(
            player_message=text,
            session=session,
            mob_stat_blocks=mob_stat_blocks,
        )

        if result.action_type == "not_action":
            return  # Just chat, ignore

        if not result.understood:
            await thread.send(
                embed=EmbedBuilder.combat_action(
                    f"⚠️ {result.description}"
                )
            )
            return

        # --- Attack resolution ---
        if result.action_type == "attack" and result.hit_result:
            hit_map = {
                "critical_hit": "💥 **CRITICAL HIT!**",
                "hit": "✅ That **hits**!",
                "miss": "❌ That **misses**.",
                "critical_miss": "💨 **Critical miss!**",
            }
            hit_text = hit_map.get(result.hit_result, result.hit_result)
            ac_text = f" (AC {result.mob_ac})" if result.mob_ac else ""
            target_text = f" against **{result.target}**" if result.target else ""

            desc = f"{hit_text}{target_text}{ac_text}"
            if result.description:
                desc = f"{result.description}\n\n{desc}"
            if result.notes:
                desc += f"\n*{result.notes}*"

            await thread.send(embed=EmbedBuilder.combat_action(desc))

        # --- Save resolution ---
        elif result.action_type == "save_effect" and result.save_modifier is not None:
            if result.save_dc is None:
                await thread.send(
                    embed=EmbedBuilder.combat_action(
                        f"⚠️ {result.description}\n"
                        "What's the DC? (I need it to roll the save.)"
                    )
                )
                return

            # Roll the mob's save
            save_roll = secrets.randbelow(20) + 1
            save_total = save_roll + result.save_modifier
            save_type = result.save_type or "save"
            target = result.target or "Mob"

            if save_total >= result.save_dc + 10:
                save_result = "**Critical Success!**"
            elif save_total >= result.save_dc:
                save_result = "**Success!** The save passes."
            elif save_total <= result.save_dc - 10:
                save_result = "**Critical Failure!**"
            else:
                save_result = "**Failure!** The save fails."

            desc = (
                f"{result.description}\n\n"
                f"🎲 **{target}** rolls {save_type}: "
                f"{save_roll} + {result.save_modifier} = **{save_total}** "
                f"vs DC {result.save_dc} — {save_result}"
            )
            if result.notes:
                desc += f"\n*{result.notes}*"

            await thread.send(embed=EmbedBuilder.combat_action(desc))

        # --- Other actions ---
        else:
            if result.description:
                await thread.send(
                    embed=EmbedBuilder.combat_action(result.description)
                )

    # ------------------------------------------------------------------
    # Mob AI turn
    # ------------------------------------------------------------------

    async def _run_mob_turn(self, thread, session: CombatSession):
        """Execute a full mob turn: 3 actions decided by Claude."""
        current = self.combat_service.get_current_combatant(session)
        if not current:
            return

        session.turn_phase = TurnPhase.MOB_DECIDING

        # Fetch stat block via RAG (cached after first lookup)
        stat_block = await self.mob_ai.get_stat_block(current.name)
        if stat_block is None:
            await thread.send(
                embed=EmbedBuilder.combat_action(
                    f"⚠️ No stat block found for **{current.name}**. "
                    "I'll improvise based on the creature name."
                )
            )

        for action_num in range(1, 4):
            # Skip if mob is dead
            if current.current_hp is not None and current.current_hp <= 0:
                await thread.send(
                    embed=EmbedBuilder.combat_action(
                        f"💀 **{current.name}** is dead and cannot act."
                    )
                )
                break

            decision = await self.mob_ai.decide_action(
                mob=current,
                session=session,
                action_number=action_num,
                stat_block=stat_block,
            )

            if decision.action_type == "strike" and decision.attack_bonus is not None:
                await self._handle_mob_strike(
                    thread, session, current, action_num, decision
                )
            elif decision.save_dc is not None:
                await self._handle_mob_save_action(
                    thread, session, current, action_num, decision
                )
            else:
                # Non-interactive action (move, etc.)
                await thread.send(
                    embed=EmbedBuilder.combat_mob_action(
                        current.name,
                        action_num,
                        decision.description,
                        notes=decision.notes,
                    )
                )

        # Mob turn done — persist and show status, but don't auto-advance
        session.turn_phase = TurnPhase.BETWEEN_TURNS
        await thread.send(
            embed=EmbedBuilder.combat_action(
                f"**{current.name}**'s turn is over. Type `next` to continue."
            )
        )

    async def _handle_mob_strike(self, thread, session, mob, action_num, decision):
        """Handle a mob strike: roll attack, ask for hit/miss, roll damage on hit."""
        # Roll attack
        attack_roll = secrets.randbelow(20) + 1
        total = attack_roll + decision.attack_bonus
        nat_text = " (NAT 20!)" if attack_roll == 20 else ""
        nat_text = " (NAT 1)" if attack_roll == 1 else nat_text

        target_name = decision.target or "target"

        session.turn_phase = TurnPhase.AWAITING_HIT_CONFIRM
        session.pending_action = {
            "action_num": action_num,
            "attack_roll": attack_roll,
            "total": total,
            "damage_dice": decision.damage_dice,
            "damage_type": decision.damage_type or "untyped",
            "target": target_name,
            "mob_name": mob.name,
            "notes": decision.notes,
        }

        await thread.send(
            embed=EmbedBuilder.combat_mob_action(
                mob.name,
                action_num,
                decision.description,
                roll_result=total,
                target=target_name,
                waiting_for=f"🎲 Rolled {attack_roll} + {decision.attack_bonus} = "
                f"**{total}**{nat_text}\nDoes that **hit** or **miss**?",
            )
        )

        # Wait for user confirmation
        confirmed = await self._wait_for_confirmation(
            thread, session, ("hit", "miss")
        )
        if confirmed is None:
            session.turn_phase = TurnPhase.MOB_DECIDING
            session.pending_action = {}
            return

        if confirmed == "hit":
            await self._roll_mob_damage(thread, session)
        else:
            await thread.send(
                embed=EmbedBuilder.combat_action(
                    f"**{mob.name}**'s attack misses {target_name}."
                )
            )

        session.turn_phase = TurnPhase.MOB_DECIDING
        session.pending_action = {}

    async def _handle_mob_save_action(self, thread, session, mob, action_num, decision):
        """Handle a mob action requiring a save from the target."""
        target_name = decision.target or "target"

        session.turn_phase = TurnPhase.AWAITING_SAVE_CONFIRM
        session.pending_action = {
            "action_num": action_num,
            "save_dc": decision.save_dc,
            "save_type": decision.save_type or "unknown",
            "target": target_name,
            "mob_name": mob.name,
            "effect_on_fail": decision.effect_on_fail or "The effect takes hold.",
            "damage_dice": decision.damage_dice,
            "damage_type": decision.damage_type,
        }

        await thread.send(
            embed=EmbedBuilder.combat_mob_action(
                mob.name,
                action_num,
                decision.description,
                target=target_name,
                waiting_for=f"DC {decision.save_dc} {decision.save_type or ''} save. "
                f"Does {target_name} **pass** or **fail**?",
            )
        )

        confirmed = await self._wait_for_confirmation(
            thread, session, ("pass", "fail")
        )
        if confirmed is None:
            session.turn_phase = TurnPhase.MOB_DECIDING
            session.pending_action = {}
            return

        if confirmed == "fail":
            effect = session.pending_action.get("effect_on_fail", "The effect takes hold.")
            await thread.send(
                embed=EmbedBuilder.combat_action(
                    f"❌ {target_name} **fails** the save! {effect}"
                )
            )
            # Roll damage if applicable
            if session.pending_action.get("damage_dice"):
                await self._roll_mob_damage(thread, session)
        else:
            await thread.send(
                embed=EmbedBuilder.combat_action(
                    f"✅ {target_name} **passes** the save!"
                )
            )

        session.turn_phase = TurnPhase.MOB_DECIDING
        session.pending_action = {}

    async def _roll_mob_damage(self, thread, session: CombatSession):
        """Roll and apply damage from a mob action."""
        pending = session.pending_action
        damage_dice = pending.get("damage_dice")
        if not damage_dice:
            return

        try:
            result = self.dice_service.roll_complex(damage_dice)
            damage = result.final_total
            damage_type = pending.get("damage_type", "untyped")
            target_name = pending.get("target", "target")
            mob_name = pending.get("mob_name", "Mob")

            await thread.send(
                embed=EmbedBuilder.combat_action(
                    f"💥 **{mob_name}** deals **{damage}** {damage_type} damage "
                    f"to {target_name}! (rolled {damage_dice})"
                )
            )

            # Auto-apply damage if target is a tracked mob
            names = [c.name for c in session.combatants]
            resolved = CombatParser.resolve_name(target_name, names)
            if resolved:
                combatant = next(
                    (c for c in session.combatants if c.name == resolved), None
                )
                if combatant and combatant.current_hp is not None:
                    session, desc = self.combat_service.apply_damage(
                        session, resolved, damage
                    )
                    await thread.send(embed=EmbedBuilder.combat_action(desc))

        except ValueError as e:
            await thread.send(
                embed=EmbedBuilder.error(f"Could not roll damage '{damage_dice}': {e}")
            )

    # ------------------------------------------------------------------
    # Confirmation waiting
    # ------------------------------------------------------------------

    async def _wait_for_confirmation(
        self, thread, session: CombatSession, valid_responses: tuple[str, ...]
    ) -> str | None:
        """Wait for the user to type a confirmation response in the thread."""

        def check(m: discord.Message) -> bool:
            return (
                m.channel.id == thread.id
                and not m.author.bot
                and m.content.strip().lower() in valid_responses
            )

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120)
            return msg.content.strip().lower()
        except asyncio.TimeoutError:
            await thread.send(
                embed=EmbedBuilder.error(
                    "Timed out waiting for response. Skipping this action."
                )
            )
            return None

    async def _handle_confirmation(self, thread, session: CombatSession, action: str):
        """Handle a hit/miss/pass/fail typed outside the wait_for flow (fallback)."""
        # This handles the case where someone types hit/miss but we're not
        # actively waiting (e.g. the wait_for already captured it).
        # Just ignore gracefully.
        if session.turn_phase not in (
            TurnPhase.AWAITING_HIT_CONFIRM,
            TurnPhase.AWAITING_SAVE_CONFIRM,
        ):
            await thread.send(
                embed=EmbedBuilder.error(
                    "Not currently waiting for a hit/miss/pass/fail response."
                )
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_target(self, session: CombatSession, raw_name: str | None) -> str:
        """Resolve a target name with fuzzy matching."""
        if not raw_name:
            raise ValueError("No target specified.")
        names = [c.name for c in session.combatants]
        resolved = CombatParser.resolve_name(raw_name, names)
        if not resolved:
            raise ValueError(
                f"Could not find combatant '{raw_name}'. "
                f"Current combatants: {', '.join(names)}"
            )
        return resolved


async def setup(bot: commands.Bot):
    """Load the CombatCog."""
    await bot.add_cog(CombatCog(bot))
