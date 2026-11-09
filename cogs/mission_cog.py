import asyncio
import json
import traceback
import unicodedata
import discord
from discord.ext import commands
from db.models import Missions
from discord import app_commands, Embed
from db.sessions import Session
import os
from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import asc
from utils import moderator_check
from utils.confirmation import confirm_action
from utils.utils import FACTION_CHOICES as SHARED_FACTION_CHOICES, FACTION_COLORS


MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MISSION_EMBED_DESCRIPTION_LIMIT = 3800


def faction_choices(include_universal=False):
    choices = [
        app_commands.Choice(name=choice.name, value=choice.value)
        for choice in SHARED_FACTION_CHOICES
    ]
    if include_universal:
        choices.append(app_commands.Choice(name="Universal", value="Universal"))
    return choices


def _choice_value(value):
    return getattr(value, "value", value)


def _selected_faction(interaction):
    namespace = getattr(interaction, "namespace", None)
    faction = getattr(namespace, "faction", None)
    return getattr(faction, "value", faction)


async def mission_name_autocomplete(interaction: discord.Interaction, current: str):
    """Suggest stable mission selectors for the currently selected faction."""
    session = None
    try:
        faction = _selected_faction(interaction)

        session = Session()
        mission_query = session.query(Missions)
        if faction and faction != "Universal":
            mission_query = mission_query.filter(Missions.faction == faction)
        search_text = (current or "").strip()
        if search_text.lower().startswith("id:"):
            try:
                database_id = int(search_text[3:].strip())
            except ValueError:
                return []
            mission_query = mission_query.filter(Missions.id == database_id)
        elif search_text:
            mission_query = mission_query.filter(Missions.title.ilike(f"%{search_text}%"))

        missions = (
            mission_query
            .order_by(asc(Missions.title), asc(Missions.id))
            .limit(25)
            .all()
        )
        return [
            app_commands.Choice(
                name=f"{_truncate_utf16(mission.title, 60)} — {mission.faction} (ID: {mission.id})",
                value=f"id:{mission.id}",
            )
            for mission in missions
        ]
    except SQLAlchemyError as exc:
        print(f"[delete_mission autocomplete] {type(exc).__name__}: {exc}")
        return []
    finally:
        if session is not None:
            try:
                session.close()
            except Exception as exc:
                print(f"[delete_mission autocomplete close] {type(exc).__name__}: {exc}")


def _utf16_length(value):
    return len(value.encode("utf-16-le", errors="replace")) // 2


def _truncate_utf16(value, limit=MISSION_EMBED_DESCRIPTION_LIMIT):
    value = str(value)
    if _utf16_length(value) <= limit:
        return value

    suffix = "…"
    remaining = max(0, limit - _utf16_length(suffix))
    truncated = []
    used_units = 0
    for character in value:
        character_units = _utf16_length(character)
        if used_units + character_units > remaining:
            break
        truncated.append(character)
        used_units += character_units
    return "".join(truncated) + suffix


def _split_utf16(value, limit=MISSION_EMBED_DESCRIPTION_LIMIT):
    chunks = []
    current = []
    used_units = 0
    for character in str(value):
        character_units = _utf16_length(character)
        if current and used_units + character_units > limit:
            chunks.append("".join(current))
            current = []
            used_units = 0
        current.append(character)
        used_units += character_units
    if current:
        chunks.append("".join(current))
    return chunks or [""]


def _mission_query(session, faction):
    query = session.query(Missions)
    if faction and faction != "Universal":
        query = query.filter_by(faction=faction)
    return query.order_by(asc(Missions.reward), asc(Missions.id))


def _mission_matches_faction(mission, faction):
    return faction == "Universal" or mission.faction == faction


def _resolve_mission(session, selector, faction, *, allow_numeric=True):
    """Resolve a stable database selector, legacy board ID, or unique exact title."""
    faction = _choice_value(faction)
    selector = str(selector or "").strip()
    if not selector:
        return None, "❌ A mission title, autocomplete selection, or board ID is required."

    if selector.casefold().startswith("id:"):
        try:
            database_id = int(selector[3:].strip())
        except ValueError:
            return None, "❌ Invalid mission selection. Choose a mission from the autocomplete list."
        if database_id <= 0:
            return None, "❌ Invalid mission selection. Choose a mission from the autocomplete list."
        targeted_mission = session.query(Missions).filter_by(id=database_id).one_or_none()
        if targeted_mission is None or not _mission_matches_faction(targeted_mission, faction):
            return None, "❌ That mission selection doesn't exist for the selected faction."
        return targeted_mission, None

    if selector.isdecimal():
        if not allow_numeric or faction == "Universal":
            return None, "❌ Universal missions use a stable `id:<id>` selector."
        board_id = int(selector)
        if board_id not in range(1, 11):
            return None, "❌ Invalid mission ID. Must be between 1 and 10."
        missions = _mission_query(session, faction).all()
        if board_id > len(missions):
            return None, "❌ That mission ID doesn't exist for the selected faction."
        return missions[board_id - 1], None

    exact_matches = [
        mission for mission in _mission_query(session, faction).all()
        if str(mission.title).strip().casefold() == selector.casefold()
    ]
    if len(exact_matches) == 1:
        return exact_matches[0], None
    if len(exact_matches) > 1:
        return None, "❌ That title is used by multiple missions. Choose the autocomplete `id:<id>` entry."
    return None, "❌ No exact mission title was found. Choose a mission from autocomplete or enter a faction board ID."


def _sanitize_embed_text(value):
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        character
        for character in text
        if character in "\n\t" or unicodedata.category(character) not in {"Cc", "Cs"}
    )
    return discord.utils.escape_mentions(text)


def _mission_embed_description(mission):
    description = (
        f"**🎯 {_sanitize_embed_text(mission.title)}**\n"
        f"> ⚙️ Difficulty: `{_sanitize_embed_text(mission.difficulty)}`\n"
        f"> 📌 Status: `{_sanitize_embed_text(mission.availability)}`\n"
        f"> 💰 Reward: <:credits:1099938341467738122> **{mission.reward:,}**\n"
        f"> 📝 Description:\n{_sanitize_embed_text(mission.description)}"
    )
    return _truncate_utf16(description)


async def _defer_mission_context(ctx):
    if getattr(ctx, "interaction", None) is None:
        return
    try:
        await ctx.defer()
    except Exception as exc:
        print(f"[mission command defer] {type(exc).__name__}: {exc}")


async def _safe_mission_send(ctx, content=None, *, embed=None):
    try:
        if content is None:
            return await ctx.send(embed=embed)
        if embed is None:
            return await ctx.send(content)
        return await ctx.send(content, embed=embed)
    except Exception as exc:
        print(f"[mission command send] {type(exc).__name__}: {exc}")
        return None


def _safe_mission_rollback(session):
    try:
        session.rollback()
    except Exception as exc:
        print(f"[mission command rollback] {type(exc).__name__}: {exc}")


def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    return AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL) if api_key else None


class MissionTemplate(BaseModel):
    title: str
    description: str
    reward: int
    difficulty: str

    @field_validator("title", "description")
    @classmethod
    def non_empty_text(cls, value):
        value = str(value).strip()
        if not value:
            raise ValueError("mission text must not be empty")
        return value

    @field_validator("reward")
    @classmethod
    def positive_reward(cls, value):
        if value <= 0:
            raise ValueError("reward must be positive")
        return value

    @field_validator("difficulty", mode="before")
    @classmethod
    def valid_difficulty(cls, value):
        normalized = str(value).strip().title()
        if normalized not in {"Easy", "Medium", "Hard", "Extreme", "Impossible"}:
            raise ValueError("invalid difficulty")
        return normalized


class MissionDetailsSelect(discord.ui.Select):
    def __init__(self, view):
        self.mission_view = view
        super().__init__(
            placeholder="View mission details…",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label="No missions on this page", value="none")],
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_id = self.values[0]
        if selected_id == "none":
            await interaction.response.send_message("❌ No mission is available on this page.", ephemeral=True)
            return

        session = None
        try:
            session = Session()
            mission = session.query(Missions).filter_by(id=int(selected_id)).one_or_none()
            if mission is None or not _mission_matches_faction(mission, self.mission_view.faction):
                await interaction.response.send_message("❌ That mission is no longer available on this board.", ephemeral=True)
                return
            embed_color = FACTION_COLORS.get(mission.faction, self.mission_view.embed_color)
            embed = discord.Embed(
                colour=embed_color,
                title=f"📘 {mission.faction} Mission Info — ID: {mission.id}",
                description=_mission_embed_description(mission),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (ValueError, SQLAlchemyError, discord.DiscordException) as exc:
            if session is not None:
                _safe_mission_rollback(session)
            print(f"[mission board details] {type(exc).__name__}: {exc}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Unable to load that mission right now.", ephemeral=True)
        finally:
            if session is not None:
                session.close()


class MissionPaginationView(discord.ui.View):
    def __init__(self, pages, embed_color, faction, missions_by_page=None):
        super().__init__(timeout=300)
        self.pages = pages
        self.embed_color = embed_color
        self.faction = faction
        self.missions_by_page = missions_by_page or [[] for _ in pages]
        self.current_page = 0
        self.message = None
        self.details_select = MissionDetailsSelect(self)
        self.add_item(self.details_select)
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.pages) - 1
        page_missions = self.missions_by_page[self.current_page] if self.missions_by_page else []
        options = [
            discord.SelectOption(
                label=_truncate_utf16(f"{mission.title} (ID: {mission.id})", 95),
                value=str(mission.id),
            )
            for mission in page_missions[:25]
        ]
        self.details_select.options = options or [
            discord.SelectOption(label="No missions on this page", value="none")
        ]
        self.details_select.disabled = not bool(options)

    def create_embed(self):
        embed = discord.Embed(
            colour=self.embed_color,
            title=f"📜 {self.faction} Mission Board",
            description=self.pages[self.current_page]
        )
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)}")
        return embed

    async def on_timeout(self):
        self.previous_button.disabled = True
        self.next_button.disabled = True
        self.details_select.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label='◀ Previous', style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label='Next ▶', style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)


class MissionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._board_lock = asyncio.Lock()

    @commands.hybrid_command(name="add_mission", description='Adds a new mission')
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(title="Title of mission", description="Job description",
                           reward="How much is earned upon completion?",
                           difficulty="Choose: Easy, Medium, Hard, Extreme, Impossible.",
                           faction='What faction is this mission for?')
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy", value="Easy"),
        app_commands.Choice(name="Medium", value="Medium"),
        app_commands.Choice(name="Hard", value="Hard"),
        app_commands.Choice(name="Extreme", value="Extreme"),
        app_commands.Choice(name="Impossible", value="Impossible"),
    ])
    @app_commands.choices(faction=faction_choices())
    async def add_mission(self, ctx, title: str, description: str, reward: int, difficulty: app_commands.Choice[str],
                          faction: app_commands.Choice[str]):
        embed_color = FACTION_COLORS.get(faction.value, discord.Colour.default())
        formatted_title = ' '.join(word.capitalize() for word in title.split())
        embed = discord.Embed(
            colour=embed_color,
            title="📝 Confirm New Mission Details",
            description=(
                f"**🎯 Title:** `{formatted_title}`\n"
                f"> 🛡️ Faction: `{faction.value}`\n"
                f"> ⚙️ Difficulty: `{difficulty.value}`\n"
                f"> 💰 Reward: <:credits:1099938341467738122> **{reward:,}**\n"
                f"> 📝 Description:\n{_sanitize_embed_text(description)}"
            )
        )
        try:
            if not await confirm_action(ctx, embed):
                return

            async with self._board_lock:
                session = Session()
                if len(session.query(Missions).filter_by(faction=faction.value).all()) >= 10:
                    await _safe_mission_send(ctx, "❌ Too many missions already listed. Maximum of 10 only.")
                    return
                new_mission = Missions(
                    title=formatted_title,
                    description=description,
                    reward=reward,
                    difficulty=difficulty.value,
                    faction=faction.value,
                    availability="Available",
                )
                session.add(new_mission)
                session.commit()
                await _safe_mission_send(ctx, "Confirmed! Mission added.")
        except SQLAlchemyError as exc:
            if "session" in locals():
                _safe_mission_rollback(session)
            print(f"[add_mission] {type(exc).__name__}: {exc}")
            await _safe_mission_send(ctx, "❌ Unable to add that mission right now. Please try again later.")
        except Exception as exc:
            print(f"[add_mission] {type(exc).__name__}: {exc}")
            await _safe_mission_send(ctx, "❌ Unable to process the mission confirmation right now.")
        finally:
            if "session" in locals():
                session.close()


    @commands.hybrid_command(name="mission_status", description="Claims a mission and sets to 'in progress' or vice versa.")
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(faction='What faction is this mission for?',
                           m_id="Mission title, autocomplete selection, or faction board ID"
                           )
    @app_commands.choices(faction=faction_choices())
    @app_commands.autocomplete(m_id=mission_name_autocomplete)
    async def mission_status(self, ctx, faction: app_commands.Choice[str], m_id: str):
        session = None
        try:
            await _defer_mission_context(ctx)
            session = Session()
            mission, error = _resolve_mission(session, m_id, faction.value)
            if error:
                await _safe_mission_send(ctx, error)
                return

            old_status = mission.availability
            new_status = "In Progress" if old_status == "Available" else "Available"
            mission.availability = new_status
            session.commit()

            embed_color = FACTION_COLORS.get(mission.faction, discord.Colour.default())
            embed = discord.Embed(
                colour=embed_color,
                title=f"🔄 Mission Status Updated — {mission.faction} ID: {mission.id}",
                description=(
                    f"**🎯 {_sanitize_embed_text(mission.title)}**\n"
                    f"> ⚙️ Difficulty: `{_sanitize_embed_text(mission.difficulty)}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{mission.reward:,}**\n"
                    f"> 📝 Status changed: `{_sanitize_embed_text(old_status)}` ➜ `{_sanitize_embed_text(new_status)}`"
                ),
            )
            await _safe_mission_send(ctx, embed=embed)
        except SQLAlchemyError as exc:
            if session is not None:
                _safe_mission_rollback(session)
            print(f"[mission_status] {type(exc).__name__}: {exc}")
            await _safe_mission_send(ctx, "❌ Unable to update that mission right now. Please try again later.")
        finally:
            if session is not None:
                session.close()


    @commands.hybrid_command(name="edit_mission", description='Edits a mission')
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(faction='What faction is this mission for?',
                           m_id="Mission title, autocomplete selection, or faction board ID",
                           mission_field='What mission info to edit?',
                           mission_value="What value to replace mission info?")
    @app_commands.choices(faction=faction_choices())
    @app_commands.choices(mission_field=[
        app_commands.Choice(name="Title", value="Title"),
        app_commands.Choice(name="Description", value="Description"),
        app_commands.Choice(name="Reward", value="Reward"),
        app_commands.Choice(name="Difficulty", value="Difficulty"),
    ])
    @app_commands.autocomplete(m_id=mission_name_autocomplete)
    async def edit_mission(self, ctx, faction: app_commands.Choice[str], m_id: str, mission_field: app_commands.Choice[str],
                           mission_value: str):
        session = None
        try:
            session = Session()
            targeted_mission, error = _resolve_mission(session, m_id, faction.value)
            if error:
                await _safe_mission_send(ctx, error)
                return
            target_id = targeted_mission.id
            proposed = {
                "title": targeted_mission.title,
                "description": targeted_mission.description,
                "reward": targeted_mission.reward,
                "difficulty": targeted_mission.difficulty,
            }
            if mission_field.value == "Title":
                proposed["title"] = " ".join(mission_value.split()).strip()
                if not proposed["title"]:
                    await _safe_mission_send(ctx, "❌ Title must not be empty.")
                    return
            elif mission_field.value == "Description":
                proposed["description"] = mission_value
            elif mission_field.value == "Reward":
                try:
                    proposed["reward"] = int(mission_value)
                except (TypeError, ValueError):
                    await _safe_mission_send(ctx, "❌ Reward must be a valid integer.")
                    return
                if proposed["reward"] <= 0:
                    await _safe_mission_send(ctx, "❌ Reward must be positive.")
                    return
            elif mission_field.value == "Difficulty":
                proposed["difficulty"] = mission_value.title()
                if proposed["difficulty"] not in {"Easy", "Medium", "Hard", "Extreme", "Impossible"}:
                    await _safe_mission_send(ctx, "❌ Invalid difficulty. Choose one of: Easy, Medium, Hard, Extreme, Impossible")
                    return

            embed = discord.Embed(
                colour=FACTION_COLORS.get(targeted_mission.faction, discord.Colour.default()),
                title=f"🛠️ Confirm Edited Mission — {targeted_mission.faction} (ID: {target_id})",
                description=(
                    f"**🎯 Title:** {_sanitize_embed_text(proposed['title'])}\n"
                    f"**⚙️ Difficulty:** {_sanitize_embed_text(proposed['difficulty'])}\n"
                    f"**💰 Reward:** <:credits:1099938341467738122> {proposed['reward']:,}\n"
                    f"**📜 Description:** {_sanitize_embed_text(proposed['description'])}"
                ),
            )
            session.close()
            session = None

            if not await confirm_action(ctx, embed):
                return

            session = Session()
            targeted_mission = session.query(Missions).filter_by(id=target_id).one_or_none()
            if targeted_mission is None or not _mission_matches_faction(targeted_mission, faction.value):
                await _safe_mission_send(ctx, "❌ That mission changed or no longer exists. Please select it again.")
                return
            for field, value in proposed.items():
                setattr(targeted_mission, field, value)
            session.commit()
            await _safe_mission_send(ctx, "✅ Mission updated successfully.")
        except SQLAlchemyError as exc:
            if session is not None:
                _safe_mission_rollback(session)
            print(f"[edit_mission] {type(exc).__name__}: {exc}")
            await _safe_mission_send(ctx, "❌ Unable to update that mission right now. Please try again later.")
        except Exception as exc:
            print(f"[edit_mission] {type(exc).__name__}: {exc}")
            await _safe_mission_send(ctx, "❌ Unable to process the mission confirmation right now.")
        finally:
            if session is not None:
                session.close()


    @commands.hybrid_command(name="all_missions", description="Shows all available missions for each faction.")
    @app_commands.describe(faction='What faction missions to show?')
    @app_commands.choices(faction=faction_choices(include_universal=True))
    async def all_missions(self, ctx, faction: app_commands.Choice[str]):
        session = None
        try:
            await _defer_mission_context(ctx)
            session = Session()
            board_faction = faction.value
            missions = _mission_query(session, board_faction).all()

            embed_color = FACTION_COLORS.get(board_faction, discord.Colour.from_rgb(0, 0, 0))

            listing_entries = []
            for idx, mission in enumerate(missions, start=1):
                mission_description = _truncate_utf16(_sanitize_embed_text(mission.description), 250)
                if board_faction == "Universal":
                    # Universal is intentionally cross-faction; only the stable database ID
                    # is safe to use as a selector because this board has no faction-local ID.
                    number_label = f"ID: {mission.id}"
                    faction_label = f" — `{_sanitize_embed_text(mission.faction)}`"
                else:
                    number_label = f"#{idx} (ID: {mission.id})"
                    faction_label = ""
                listing_entries.append(
                    (
                    f"**{number_label} — {_sanitize_embed_text(mission.title)}{faction_label}**\n"
                    f"> ⚙️ Difficulty: `{_sanitize_embed_text(mission.difficulty)}`\n"
                    f"> 📌 Status: `{_sanitize_embed_text(mission.availability)}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{mission.reward:,}**\n"
                    f"> 📝 {mission_description}\n\n"
                    )
                )

            pages = []
            missions_by_page = []
            current_page = ""
            current_missions = []
            for mission, entry in zip(missions, listing_entries):
                chunks = _split_utf16(entry, MISSION_EMBED_DESCRIPTION_LIMIT)
                if current_page and _utf16_length(current_page) + _utf16_length(chunks[0]) > MISSION_EMBED_DESCRIPTION_LIMIT:
                    pages.append(current_page)
                    missions_by_page.append(current_missions)
                    current_page = ""
                    current_missions = []
                if len(chunks) == 1:
                    current_page += chunks[0]
                    current_missions.append(mission)
                    continue
                if current_page:
                    pages.append(current_page)
                    missions_by_page.append(current_missions)
                    current_page = ""
                    current_missions = []
                for chunk_index, chunk in enumerate(chunks):
                    if chunk_index < len(chunks) - 1:
                        pages.append(chunk)
                        missions_by_page.append([mission])
                    else:
                        current_page = chunk
                        current_missions = [mission]
            if current_page:
                pages.append(current_page)
                missions_by_page.append(current_missions)
            if not pages:
                if board_faction == "Universal":
                    pages.append("No missions are currently listed across any faction.")
                else:
                    pages.append(f"No missions are currently listed for the {board_faction} faction.")
                missions_by_page.append([])

            view = MissionPaginationView(pages, embed_color, board_faction, missions_by_page)
            view.message = await ctx.send(embed=view.create_embed(), view=view)
        except Exception as exc:
            print(f"[all_missions] {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            await _safe_mission_send(ctx, "❌ Unable to load missions right now. Please try again later.")
        finally:
            if session is not None:
                session.close()


    @commands.hybrid_command(name="mission_info", description="Show info for specified mission ID (1-10).")
    @app_commands.describe(m_id="Mission title, autocomplete selection, or faction board ID",
                           faction='What faction missions to show?')
    @app_commands.choices(faction=faction_choices())
    @app_commands.autocomplete(m_id=mission_name_autocomplete)
    async def mission_info(self, ctx, faction: app_commands.Choice[str], m_id: str):
        session = None
        try:
            await _defer_mission_context(ctx)
            session = Session()
            mission, error = _resolve_mission(session, m_id, faction.value)
            if error:
                await _safe_mission_send(ctx, error)
                return
            embed_color = FACTION_COLORS.get(mission.faction, discord.Colour.default())
            embed = discord.Embed(
                colour=embed_color,
                title=f"📘 {mission.faction} Mission Info — ID: {mission.id}",
                description=_mission_embed_description(mission)
            )
            await _safe_mission_send(ctx, embed=embed)
        except SQLAlchemyError as exc:
            if session is not None:
                _safe_mission_rollback(session)
            print(f"[mission_info] {type(exc).__name__}: {exc}")
            await _safe_mission_send(ctx, "❌ Unable to load that mission right now. Please try again later.")
        except Exception as exc:
            print(f"[mission_info] {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            await _safe_mission_send(ctx, "❌ Unable to show mission info right now. Please try again later.")
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception as exc:
                    print(f"[mission_info close] {type(exc).__name__}: {exc}")


    @commands.hybrid_command(name="delete_mission", description="Delete a mission by name or board ID.")
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(mission="Mission title, autocomplete selection, or faction board ID",
                           faction='What faction mission to delete?')
    @app_commands.choices(faction=faction_choices())
    @app_commands.autocomplete(mission=mission_name_autocomplete)
    async def delete_mission(self, ctx, faction: app_commands.Choice[str], mission: str):
        session = None
        try:
            await _defer_mission_context(ctx)
            session = Session()
            targeted_mission, error = _resolve_mission(session, mission, faction.value)
            if error:
                await _safe_mission_send(ctx, error)
                return
            target_id = targeted_mission.id
            target_faction = targeted_mission.faction
            mission_reference = f"Database ID: {target_id}"

            embed_color = FACTION_COLORS.get(target_faction, discord.Colour.default())
            embed = discord.Embed(
                colour=embed_color,
                title=f"🗑️ Confirm Deletion — {target_faction} {mission_reference}",
                description=_mission_embed_description(targeted_mission)
            )
            session.close()
            session = None

            if not await confirm_action(ctx, embed):
                return

            async with self._board_lock:
                session = Session()
                targeted_mission = session.query(Missions).filter_by(id=target_id).one_or_none()
                if targeted_mission is None or not _mission_matches_faction(targeted_mission, faction.value):
                    await _safe_mission_send(ctx, "❌ That mission changed or no longer exists. Please select it again.")
                    return
                session.delete(targeted_mission)
                session.commit()
                await _safe_mission_send(ctx, "Mission deleted.")
        except SQLAlchemyError as exc:
            if session is not None:
                _safe_mission_rollback(session)
            print(f"[delete_mission] {type(exc).__name__}: {exc}")
            await _safe_mission_send(ctx, "❌ Unable to access missions right now. Please try again later.")
        except Exception as exc:
            print(f"[delete_mission] {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            await _safe_mission_send(ctx, "❌ Unable to delete that mission right now. Please try again later.")
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception as exc:
                    print(f"[delete_mission close] {type(exc).__name__}: {exc}")


    @app_commands.command(name="generate_missions", description="Generate missions for the specified faction")
    @app_commands.check(moderator_check)
    @app_commands.describe(faction='What faction to generate missions for?', amount="Number of missions to generate (default: Fills up mission board to 10 total missions)")
    @app_commands.choices(faction=faction_choices())
    async def generate_missions(self, interaction: discord.Interaction, faction: app_commands.Choice[str], amount: int = 10):
        await interaction.response.defer()
        faction_value = _choice_value(faction)
        requested_amount = max(1, min(10, int(amount)))
        session = None
        try:
            session = Session()
            existing = session.query(Missions).filter_by(faction=faction_value).all()
            mission_count = len(existing)
            difficulty_counts = {
                difficulty: sum(mission.difficulty == difficulty for mission in existing)
                for difficulty in ("Easy", "Medium", "Hard", "Extreme", "Impossible")
            }
            session.close()
            session = None

            if mission_count >= 10:
                await interaction.followup.send(
                    embed=Embed(
                        title="❌ Mission Generation Failed",
                        description="The mission list for that faction is already complete.\n(10 missions already registered).",
                        color=0xff0000,
                    )
                )
                return

            deepseek_client = get_deepseek_client()
            if deepseek_client is None:
                await interaction.followup.send(
                    "❌ AI mission generation is unavailable because DEEPSEEK_API_KEY is not configured.",
                    ephemeral=True,
                )
                return

            prompt = (
                f"You are to create {requested_amount} Star Wars-themed missions for the {faction_value} faction. The server is set in 2BBY, during the height of the Empire. This is a gritty, grounded galaxy. No Jedi. No Force. No canon characters like Luke Skywalker, etc.\n"
                f"Ensure the missions are appropriate for the {faction_value}'s style. Imperial and Rebel missions should be varied; Mandalorian and Rogue missions should reflect a wild-west tone.\n"
                f"Each mission must include a title, a neutral 3-6 sentence description, one difficulty from Easy, Medium, Hard, Extreme, Impossible, and a positive integer credit reward.\n"
                f"Use this difficulty ratio as a guide: 3 Easy, 2 Medium, 2 Hard, 2 Extreme, 1 Impossible per 10 missions. Existing counts are {difficulty_counts}.\n"
                "Return only a JSON object with a `missions` array."
            )
            response = await deepseek_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Generate Star Wars themed missions."},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
            )

            response_content = response.choices[0].message.content
            response_data = json.loads(response_content)
            if isinstance(response_data, dict):
                missions_payload = response_data.get("missions")
            else:
                missions_payload = response_data
            if not isinstance(missions_payload, list):
                raise ValueError("AI response did not contain a missions array")
            missions_generated = [MissionTemplate.model_validate(item) for item in missions_payload]

            # Re-query after the network await so concurrent moderators cannot
            # overfill a faction board.
            async with self._board_lock:
                session = Session()
                current_count = session.query(Missions).filter_by(faction=faction_value).count()
                remaining_slots = max(0, 10 - current_count)
                num_to_create = min(requested_amount, remaining_slots, len(missions_generated))
                if num_to_create == 0:
                    session.close()
                    session = None
                    await interaction.followup.send(
                        "❌ No mission slots remain, or the generator returned no valid missions."
                    )
                    return

                new_missions = [
                    Missions(
                        title=mission.title,
                        description=mission.description,
                        reward=mission.reward,
                        difficulty=mission.difficulty,
                        faction=faction_value,
                        availability="Available",
                    )
                    for mission in missions_generated[:num_to_create]
                ]
                session.add_all(new_missions)
                session.commit()
                saved_count = len(new_missions)
            await interaction.followup.send(
                embed=Embed(
                    title="🛠️ Missions Generated",
                    description=f"Successfully generated **{saved_count}** missions for faction **{faction_value}**.",
                    color=0x00FF00,
                )
            )
        except (ValueError, TypeError, json.JSONDecodeError, SQLAlchemyError) as exc:
            if session is not None:
                _safe_mission_rollback(session)
            print(f"[generate_missions] {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                "❌ Mission generation returned invalid data or could not be saved. No missions were added.",
                ephemeral=True,
            )
        except Exception as exc:
            if session is not None:
                _safe_mission_rollback(session)
            print(f"[generate_missions] {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                "❌ Unable to generate missions right now. Please try again later.",
                ephemeral=True,
            )
        finally:
            if session is not None:
                session.close()


async def setup(bot):
    await bot.add_cog(MissionCog(bot))
