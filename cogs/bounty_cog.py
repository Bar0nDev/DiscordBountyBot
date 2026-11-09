import asyncio
import json
import os
import unicodedata

import discord
from discord import Embed, app_commands
from discord.ext import commands
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import asc

from db.models import Bounties
from db.sessions import Session
from utils import moderator_check
from utils.confirmation import confirm_action


MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
BOUNTY_BOARD_LIMIT = 10
BOUNTY_EMBED_DESCRIPTION_LIMIT = 3800
BOUNTY_AUTOCOMPLETE_LIMIT = 25


def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    return AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL) if api_key else None


class BountyTemplate(BaseModel):
    target: str = Field(min_length=1)
    description: str = Field(min_length=1)
    reward: int = Field(ge=150, le=13_000)
    client: str = Field(min_length=1)
    stars: int = Field(ge=1, le=5)


def _utf16_length(value):
    return len(str(value).encode("utf-16-le", errors="replace")) // 2


def _truncate_utf16(value, limit=BOUNTY_EMBED_DESCRIPTION_LIMIT):
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


def _split_utf16(value, limit=BOUNTY_EMBED_DESCRIPTION_LIMIT):
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


def _sanitize_embed_text(value):
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        character
        for character in text
        if character in "\n\t" or unicodedata.category(character) not in {"Cc", "Cs"}
    )
    return discord.utils.escape_mentions(text)


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _star_display(stars):
    stars = _safe_int(stars, default=5)
    if stars not in range(1, 6):
        stars = 5
    return "★" * (6 - stars) + "☆" * (stars - 1)


def _ordered_bounties(session):
    return session.query(Bounties).order_by(asc(Bounties.reward), asc(Bounties.id))


async def bounty_name_autocomplete(interaction: discord.Interaction, current: str):
    """Return stable-ID choices shared by bounty info and delete commands."""
    session = None
    try:
        session = Session()
        search_text = (current or "").strip()
        query = session.query(Bounties)
        if search_text:
            query = query.filter(Bounties.target.ilike(f"%{search_text}%"))
        bounties = (
            query.order_by(asc(Bounties.target), asc(Bounties.id))
            .limit(BOUNTY_AUTOCOMPLETE_LIMIT)
            .all()
        )
        choices = []
        for bounty in bounties:
            target = _sanitize_embed_text(bounty.target)
            label = f"{_truncate_utf16(target, 70)} — ID: {bounty.id}"
            choices.append(
                app_commands.Choice(
                    name=_truncate_utf16(label, 100),
                    value=f"id:{bounty.id}",
                )
            )
        return choices
    except Exception as exc:
        print(f"[bounty autocomplete] {type(exc).__name__}: {exc}")
        return []
    finally:
        if session is not None:
            session.close()


def _resolve_bounty(session, selector):
    """Resolve stable IDs, legacy board numbers, or one exact target title."""
    selector = str(selector or "").strip()
    if not selector:
        return None, "❌ Enter a bounty title, an autocomplete selection, or a board ID from 1 to 10."

    bounties = _ordered_bounties(session).all()

    if selector.casefold().startswith("id:"):
        try:
            database_id = int(selector[3:].strip())
        except (TypeError, ValueError):
            return None, "❌ Invalid bounty selection. Choose a bounty from the autocomplete list."
        if database_id <= 0:
            return None, "❌ Invalid bounty selection. Choose a bounty from the autocomplete list."
        bounty = next(
            (candidate for candidate in bounties if _safe_int(getattr(candidate, "id", None)) == database_id),
            None,
        )
        if bounty is None:
            return None, "❌ That bounty selection no longer exists."
        return bounty, None

    try:
        board_id = int(selector)
    except (TypeError, ValueError):
        board_id = None

    if board_id is not None:
        if board_id not in range(1, BOUNTY_BOARD_LIMIT + 1):
            return None, "❌ Invalid bounty ID. Enter a board ID from 1 to 10."
        if board_id > len(bounties):
            return None, "❌ That bounty ID doesn't exist on the board."
        return bounties[board_id - 1], None

    exact_matches = [
        bounty
        for bounty in bounties
        if str(getattr(bounty, "target", "")).strip().casefold() == selector.casefold()
    ]
    if len(exact_matches) == 1:
        return exact_matches[0], None
    if len(exact_matches) > 1:
        return None, "❌ Multiple bounties have that title. Choose one from autocomplete."
    return None, "❌ That bounty title doesn't exist. Choose one from autocomplete or enter a board ID from 1 to 10."


def _bounty_embed_description(bounty):
    reward = _safe_int(getattr(bounty, "reward", 0))
    description = (
        f"**🎯 Target:** `{_sanitize_embed_text(getattr(bounty, 'target', ''))}`\n"
        f"> 🚨 Priority: {_star_display(getattr(bounty, 'stars', 5))}\n"
        f"> 👤 Client: `{_sanitize_embed_text(getattr(bounty, 'client', ''))}`\n"
        f"> 💰 Reward: <:credits:1099938341467738122> **{reward:,}**\n"
        f"> 📝 {_sanitize_embed_text(getattr(bounty, 'description', ''))}"
    )
    return _truncate_utf16(description)


def _bounty_info_embed(bounty):
    database_id = getattr(bounty, "id", None)
    title = f"🎯 Bounty Contract — Database ID: `{database_id}`"
    return discord.Embed(
        colour=discord.Colour.from_rgb(0, 0, 0),
        title=_truncate_utf16(title, 256),
        description=_bounty_embed_description(bounty),
    )


def _bounty_listing_entry(bounty, board_id):
    target = _truncate_utf16(_sanitize_embed_text(getattr(bounty, "target", "")), 120)
    client = _truncate_utf16(_sanitize_embed_text(getattr(bounty, "client", "")), 120)
    description = _truncate_utf16(_sanitize_embed_text(getattr(bounty, "description", "")), 300)
    reward = _safe_int(getattr(bounty, "reward", 0))
    return (
        f"**#{board_id} — `{target}`**\n"
        f"> 🚨 Priority: {_star_display(getattr(bounty, 'stars', 5))}\n"
        f"> 👤 Client: `{client}`\n"
        f"> 💰 Reward: <:credits:1099938341467738122> **{reward:,}**\n"
        f"> 📝 {description}\n\n"
    )


def _build_bounty_pages(bounties):
    pages = []
    page_bounties = []
    current_page = ""
    current_bounties = []
    current_ids = set()

    for board_id, bounty in enumerate(bounties, start=1):
        entry = _bounty_listing_entry(bounty, board_id)
        for chunk in _split_utf16(entry, BOUNTY_EMBED_DESCRIPTION_LIMIT):
            if current_page and _utf16_length(current_page) + _utf16_length(chunk) > BOUNTY_EMBED_DESCRIPTION_LIMIT:
                pages.append(current_page)
                page_bounties.append(current_bounties)
                current_page = ""
                current_bounties = []
                current_ids = set()
            current_page += chunk
            bounty_id = getattr(bounty, "id", None)
            if bounty_id not in current_ids:
                current_bounties.append(bounty)
                current_ids.add(bounty_id)

    if current_page:
        pages.append(current_page)
        page_bounties.append(current_bounties)
    if not pages:
        pages = ["No bounties are currently listed on the board."]
        page_bounties = [[]]
    return pages, page_bounties


class BountyDetailsSelect(discord.ui.Select):
    def __init__(self, bounties):
        options = []
        for bounty in bounties[:25]:
            bounty_id = getattr(bounty, "id", None)
            target = _truncate_utf16(_sanitize_embed_text(getattr(bounty, "target", "")), 80)
            options.append(
                discord.SelectOption(
                    label=_truncate_utf16(f"{target} — ID: {bounty_id}", 100),
                    value=str(bounty_id),
                )
            )
        super().__init__(
            placeholder="View bounty details…",
            min_values=1,
            max_values=1,
            options=options,
        )
        self._bounties_by_id = {str(getattr(bounty, "id", None)): bounty for bounty in bounties}

    async def callback(self, interaction: discord.Interaction):
        bounty = self._bounties_by_id.get(self.values[0])
        if bounty is None:
            await interaction.response.send_message(
                "❌ That bounty is no longer available.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=_bounty_info_embed(bounty),
            ephemeral=True,
        )


class BountyPaginationView(discord.ui.View):
    def __init__(self, pages, page_bounties=None):
        super().__init__(timeout=300)
        self.pages = pages
        self.page_bounties = page_bounties or [[] for _ in pages]
        self.current_page = 0
        self.message = None
        self.details_select = None
        self.update_buttons()
        self._refresh_details_select()

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.pages) - 1

    def _refresh_details_select(self):
        if self.details_select is not None:
            self.remove_item(self.details_select)
        current_bounties = self.page_bounties[self.current_page] if self.page_bounties else []
        self.details_select = BountyDetailsSelect(current_bounties) if current_bounties else None
        if self.details_select is not None:
            self.add_item(self.details_select)

    def create_embed(self):
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(0, 0, 0),
            title="📜 Bounty Board",
            description=_truncate_utf16(self.pages[self.current_page]),
        )
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)}")
        return embed

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            self._refresh_details_select()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            self._refresh_details_select()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)


class BountyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._board_lock = asyncio.Lock()

    @commands.hybrid_command(name="add_bounty", description="Adds a new bounty")
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(
        target="Who does the bounty target?",
        stars="How much of a priority is the bounty? Enter a number from 1-5, with 1 being highest priority.",
        description="Bounty description or additional notes?",
        reward="How much will you pay upon completion? Minimum 150 credits!",
        client="Who is initiating the bounty?",
    )
    async def add_bounty(self, ctx, target: str, description: str, reward: int, stars: int, client: str):
        await ctx.defer()
        session = None
        try:
            if reward < 150:
                await ctx.send("Insufficient reward amount set. Canceled request.")
                return
            if not 1 <= stars <= 5:
                await ctx.send("Invalid star rating. Please enter a value between 1 (highest priority) and 5.")
                return

            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title="Confirm Bounty Details",
                description=_truncate_utf16(
                    f"**Target:** {_sanitize_embed_text(target)}\n"
                    f"**Priority:** {_star_display(stars)}\n"
                    f"**Reward:** <:credits:1099938341467738122>{reward:,}\n"
                    f"**Client:** {_sanitize_embed_text(client)}\n"
                    f"**Description:** {_sanitize_embed_text(description)}"
                ),
            )
            embed.set_footer(text="Confirm to add this bounty, or cancel.")

            if not await confirm_action(ctx, embed):
                return

            async with self._board_lock:
                session = Session()
                if len(session.query(Bounties).all()) >= BOUNTY_BOARD_LIMIT:
                    await ctx.send("Error. Too many bounties already listed. Maximum of 10 only.")
                    return

                new_bounty = Bounties(
                    target=target.title(),
                    description=description,
                    reward=reward,
                    client=client,
                    stars=stars,
                )
                session.add(new_bounty)
                session.commit()
                await ctx.send("Confirmed! Bounty added.")
        except Exception as exc:
            if session is not None:
                session.rollback()
            print(f"[add_bounty] {type(exc).__name__}: {exc}")
            await ctx.send("❌ Unable to add that bounty right now. Please try again later.")
        finally:
            if session is not None:
                session.close()

    @commands.hybrid_command(name="bounty_info", description="Show info for specified bounty ID, title, or autocomplete selection.")
    @app_commands.describe(b_id="Bounty title, autocomplete selection, or legacy board ID")
    @app_commands.autocomplete(b_id=bounty_name_autocomplete)
    async def bounty_info(self, ctx, b_id: str):
        await ctx.defer()
        session = None
        try:
            session = Session()
            bounty, error = _resolve_bounty(session, b_id)
            if error:
                await ctx.send(error)
                return
            await ctx.send(embed=_bounty_info_embed(bounty))
        except Exception as exc:
            print(f"[bounty_info] {type(exc).__name__}: {exc}")
            await ctx.send("❌ Unable to show bounty info right now. Please try again later.")
        finally:
            if session is not None:
                session.close()

    @commands.hybrid_command(name="all_bounties", description="Shows all available bounties.")
    async def all_bounties(self, ctx):
        session = None
        try:
            await ctx.defer()
            session = Session()
            bounties = _ordered_bounties(session).all()
            pages, page_bounties = _build_bounty_pages(bounties)
            view = BountyPaginationView(pages, page_bounties)
            view.message = await ctx.send(embed=view.create_embed(), view=view)
        except Exception as exc:
            print(f"[all_bounties] {type(exc).__name__}: {exc}")
            await ctx.send("❌ Unable to load bounties right now. Please try again later.", ephemeral=True)
        finally:
            if session is not None:
                session.close()

    @commands.hybrid_command(name="delete_bounty", description="Delete bounty by title, autocomplete selection, or legacy board ID.")
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(b_id="Bounty title, autocomplete selection, or legacy board ID")
    @app_commands.autocomplete(b_id=bounty_name_autocomplete)
    async def delete_bounty(self, ctx, b_id: str):
        await ctx.defer()
        session = None
        try:
            session = Session()
            bounty, error = _resolve_bounty(session, b_id)
            if error:
                await ctx.send(error)
                return

            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title=f"⚠️ Confirm Bounty — Database ID: `{getattr(bounty, 'id', None)}`",
                description=_bounty_embed_description(bounty),
            )
            embed.set_footer(text="Confirm to delete this exact bounty, or cancel.")

            if not await confirm_action(ctx, embed):
                return

            async with self._board_lock:
                session.delete(bounty)
                session.commit()
                await ctx.send("Bounty deleted.")
        except Exception as exc:
            if session is not None:
                session.rollback()
            print(f"[delete_bounty] {type(exc).__name__}: {exc}")
            await ctx.send("❌ Unable to delete that bounty right now. Please try again later.")
        finally:
            if session is not None:
                session.close()

    @app_commands.command(name="generate_bounties", description="Generate bounties")
    @app_commands.check(moderator_check)
    @app_commands.describe(
        amount="Number of bounties to generate (default: Fills up bounty board to 10 total bounties)"
    )
    async def generate_bounties(self, interaction: discord.Interaction, amount: int = 10):
        await interaction.response.defer()
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            amount = 0
        if amount <= 0:
            await interaction.followup.send("❌ Amount must be a positive integer.", ephemeral=True)
            return

        deepseek_client = get_deepseek_client()
        if deepseek_client is None:
            await interaction.followup.send(
                "❌ AI bounty generation is unavailable because DEEPSEEK_API_KEY is not configured.",
                ephemeral=True,
            )
            return

        session = Session()
        try:
            initial_count = len(session.query(Bounties).all())
            initial_slots = max(0, BOUNTY_BOARD_LIMIT - initial_count)
            if initial_slots == 0:
                await interaction.followup.send(
                    embed=Embed(
                        title="❌ Bounty Generation Failed",
                        description="The bounty board is already complete.\n(10 bounties already registered).",
                        color=0xFF0000,
                    )
                )
                return

            generation_amount = min(initial_slots, amount) if amount < BOUNTY_BOARD_LIMIT else initial_slots
            prompt = (
                f"You are to generate {generation_amount} Star Wars-themed bounties for specific individuals. No canon characters like Luke Skywalker, etc. "
                "These bounties appear on an encrypted black-market network or seedy bounty hunter board. "
                "The setting is 2BBY, during the height of the Empire. This is a grounded, gritty galaxy. No Jedi, no Force, no lightsabers.\n\n"
                "Each bounty is for a specific target. These individuals are wanted for various reasons — betrayal, theft, desertion, murder, smuggling, sabotage, or other criminal or political offenses.\n\n"
                "For each bounty, include the following:\n"
                "1. Target – A name or codename. Can be realistic, alias-based, or underworld-styled. Should sound like a Star Wars character.\n"
                "2. Description – 3–6 sentences. Written as if posted to an illicit network. Describe the target's crime, affiliations, last known location, danger level, or unique info. Do NOT use second-person language. This is a listing meant for hardened bounty hunters or syndicate enforcers. Also mention how the bounty is to be completed, whether dead, alive, etc.\n"
                "3. Reward – A numeric credit value between 150 and 13,000.\n"
                "4. Client – The name or alias of the individual, faction, or anonymous source who posted the bounty.\n"
                "5. Stars – The level of wanted priority from 1-5, where 1 is highest priority and 5 is lowest.\n"
                "Use an appropriately gritty, criminal tone — think dark holonet terminal postings. Be terse but evocative. Only use specific planetary names if essential; otherwise refer to regions like Outer Rim, Mid Rim, or Expansion Region. Avoid exposition or polite phrasing — this is underworld business."
            )
            response = await deepseek_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt + "\nReturn a JSON object with a `bounties` array."},
                    {"role": "user", "content": "Generate Star Wars themed bounties."},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
            )

            content = response.choices[0].message.content
            response_data = json.loads(content)
            bounties_payload = response_data.get("bounties") if isinstance(response_data, dict) else None
            if not isinstance(bounties_payload, list):
                raise ValueError("AI response did not contain a bounties array")

            valid_bounties = []
            for payload in bounties_payload:
                try:
                    valid_bounties.append(BountyTemplate.model_validate(payload))
                except (ValidationError, TypeError, ValueError) as exc:
                    print(f"[generate_bounties validation] skipped item: {exc}")

            # Re-read after the network await so concurrent additions cannot overfill the board.
            async with self._board_lock:
                session.close()
                session = Session()
                current_count = len(session.query(Bounties).all())
                available_slots = max(0, BOUNTY_BOARD_LIMIT - current_count)
                requested_after_wait = amount if amount < BOUNTY_BOARD_LIMIT else available_slots
                num_to_create = min(requested_after_wait, available_slots, len(valid_bounties))
                records = [
                    Bounties(
                        target=f"{template.target.strip()} [NPC]",
                        description=template.description.strip(),
                        reward=template.reward,
                        client=template.client.strip(),
                        stars=template.stars,
                    )
                    for template in valid_bounties[:num_to_create]
                ]

                if not records:
                    await interaction.followup.send(
                        "❌ No valid bounties were returned, or the board filled while generation was in progress.",
                        ephemeral=True,
                    )
                    return

                # Add all records and commit once so a failed save cannot leave a partial batch.
                for record in records:
                    session.add(record)
                session.commit()
                actual_count = len(records)
            await interaction.followup.send(
                embed=Embed(
                    title="🛠️ Bounties Generated",
                    description=f"Successfully generated **{actual_count}** bounties.",
                    color=0x00FF00,
                )
            )
        except Exception as exc:
            session.rollback()
            print(f"[generate_bounties] {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                "❌ Unable to generate bounties right now. Please try again later.",
                ephemeral=True,
            )
        finally:
            session.close()


async def setup(bot):
    await bot.add_cog(BountyCog(bot))
