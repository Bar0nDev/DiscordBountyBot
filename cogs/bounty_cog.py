import asyncio
import json
import traceback
import discord
from discord.ext import commands
from db.models import Bounties
from discord import app_commands, Embed
from db.sessions import Session
import os
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import asc
from utils import moderator_check


MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    return AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL) if api_key else None


class BountyTemplate(BaseModel):
    target: str
    description: str
    reward: int
    client: str
    stars: int


class BountyPaginationView(discord.ui.View):
    def __init__(self, pages):
        super().__init__(timeout=300)
        self.pages = pages
        self.current_page = 0
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.pages) - 1

    def create_embed(self):
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(0, 0, 0),
            title="📜 Bounty Board",
            description=self.pages[self.current_page]
        )
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)}")
        return embed

    async def on_timeout(self):
        self.previous_button.disabled = True
        self.next_button.disabled = True
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


class BountyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="add_bounty", description='Adds a new bounty')
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(target="Who does the bounty target?",
                           stars="How much of a priority is the bounty? Enter a number from 1-5, with 1 being highest priority.",
                           description="Bounty description or additional notes?",
                           reward="How much will you pay upon completion? Minimum 150 credits!",
                           client="Who is initiating the bounty?")
    async def add_bounty(self, ctx, target: str, description: str, reward: int, stars: int, client: str):
        await ctx.defer()
        session = Session()
        if reward < 150:
            await ctx.send("Insufficient reward amount set. Canceled request.")
        elif not 1 <= stars <= 5:
            await ctx.send("Invalid star rating. Please enter a value between 1 (highest priority) and 5.")
        else:
            star_display = "★" * (6 - stars) + "☆" * (stars - 1)
            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title="Confirm Bounty Details",
                description=(
                    f"**Target:** {target}\n"
                    f"**Priority:** {star_display}\n"
                    f"**Reward:** <:credits:1099938341467738122>{reward:,}\n"
                    f"**Client:** {client}\n"
                    f"**Description:** {description}"
                )
            )
            embed.set_footer(text="✅ to confirm, or ❌ to cancel.")

            bot_response = await ctx.send(embed=embed)

            await bot_response.add_reaction("✅")
            await bot_response.add_reaction("❌")

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message == bot_response

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                if str(reaction.emoji) == "✅":
                    if len(session.query(Bounties).all()) == 10:
                        await ctx.send("Error. Too many bounties already listed. Maximum of 10 only.")
                    else:
                        new_bounty = Bounties(
                            target=target.title(),
                            description=description,
                            reward=reward,
                            client=client,
                            stars=stars
                        )
                        session.add(new_bounty)
                        session.commit()
                        await ctx.send("Confirmed! Bounty added.")
                elif str(reaction.emoji) == "❌":
                    await ctx.send("Canceled request.")
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out.")
        session.close()


    @commands.hybrid_command(name="bounty_info", description="Show info for specified bounty ID (1-10).")
    @app_commands.describe(b_id="ID of bounty")
    async def bounty_info(self, ctx, b_id: int):
        await ctx.defer()
        session = Session()
        if b_id not in range(1, 11):
            await ctx.send("Invalid bounty ID. Enter an ID number from 1-10")
        else:
            bounty = session.query(Bounties).order_by(asc(Bounties.reward)).all()[b_id - 1]
            star_display = "★" * (6 - bounty.stars) + "☆" * (bounty.stars - 1)
            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title=f"🎯 Bounty Contract — ID: `{b_id}`",
                description=(
                    f"**🎯 Target:** `{bounty.target}`\n"
                    f"> 🚨 Priority: {star_display}\n"
                    f"> 👤 Client: `{bounty.client}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{bounty.reward:,}**\n"
                    f"> 📝 {bounty.description}"
                )
            )
            await ctx.send(embed=embed)
        session.close()


    @commands.hybrid_command(name="all_bounties", description="Shows all available bounties.")
    async def all_bounties(self, ctx):
        session = None
        try:
            await ctx.defer()
            session = Session()
            bounties = session.query(Bounties).order_by(asc(Bounties.reward)).all()
            listing_entries = []
            for i, bounty in enumerate(bounties, start=1):
                star_display = "★" * (6 - bounty.stars) + "☆" * (bounty.stars - 1)

                description_str = str(bounty.description)
                bounty_description = (
                    description_str[:250] + "..."
                    if len(description_str) > 250
                    else description_str
                )

                listing_entries.append(
                    f"**#{i} — `{bounty.target}`**\n"
                    f"> 🚨 Priority: {star_display}\n"
                    f"> 👤 Client: `{bounty.client}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{bounty.reward:,}**\n"
                    f"> 📝 {bounty_description}\n\n"
                )

            # Discord validates this field by UTF-16 length; leave headroom for
            # emoji and other non-BMP characters in the rendered board.
            description_limit = 3800
            pages = []
            current_page = ""
            for entry in listing_entries:
                while len(entry) > description_limit:
                    if current_page:
                        pages.append(current_page)
                        current_page = ""
                    pages.append(entry[:description_limit])
                    entry = entry[description_limit:]
                if current_page and len(current_page) + len(entry) > description_limit:
                    pages.append(current_page)
                    current_page = ""
                current_page += entry
            if current_page:
                pages.append(current_page)
            if not pages:
                pages.append("No bounties are currently listed on the board.")

            view = BountyPaginationView(pages)
            view.message = await ctx.send(embed=view.create_embed(), view=view)
        except Exception as exc:
            print(f"[all_bounties] {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            await ctx.send("❌ Unable to load bounties right now. Please try again later.", ephemeral=True)
        finally:
            if session is not None:
                session.close()


    @commands.hybrid_command(name="delete_bounty", description="Delete bounty by specified bounty ID (1-10).")
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(b_id="ID of bounty")
    async def delete_bounty(self, ctx, b_id: int):
        await ctx.defer()
        session = Session()
        if b_id not in range(1, 11):
            await ctx.send("Invalid bounty ID. Enter an ID number from 1-10")
        else:
            bounty = session.query(Bounties).order_by(asc(Bounties.reward)).all()[b_id - 1]
            star_display = "★" * (6 - bounty.stars) + "☆" * (bounty.stars - 1)

            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title=f"⚠️ Confirm Bounty — ID: `{b_id}`",
                description=(
                    f"**🎯 Target:** `{bounty.target}`\n"
                    f"> 🚨 Priority: {star_display}\n"
                    f"> 👤 Client: `{bounty.client}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{bounty.reward:,}**\n"
                    f"> 📝 {bounty.description}"
                )
            )
            embed.set_footer(text="React with ✅ to confirm deletion, or ❌ to cancel.")

            bot_response = await ctx.send(embed=embed)
            await bot_response.add_reaction("✅")
            await bot_response.add_reaction("❌")

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message == bot_response

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                if str(reaction.emoji) == "✅":
                    session.delete(bounty)
                    session.commit()
                    await ctx.send("Bounty deleted.")
                elif str(reaction.emoji) == "❌":
                    await ctx.send("Canceled request.")
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out.")
        session.close()


    @app_commands.command(name="generate_bounties", description="Generate bounties")
    @app_commands.check(moderator_check)
    @app_commands.describe(amount="Number of bounties to generate (default: Fills up bounty board to 10 total bounties)")
    async def generate_bounties(self, interaction: discord.Interaction, amount: int = 10):
        await interaction.response.defer()
        deepseek_client = get_deepseek_client()
        if deepseek_client is None:
            await interaction.followup.send(
                "❌ AI bounty generation is unavailable because DEEPSEEK_API_KEY is not configured.",
                ephemeral=True,
            )
            return

        session = Session()
        bounties = session.query(Bounties).all()
        bounty_count = len(bounties)
        if bounty_count < 10:
            if amount >= 10:
                num_to_create = 10 - bounty_count
            else:
                num_to_create = amount
            prompt = (
                f"You are to generate {num_to_create} Star Wars-themed bounties for specific individuals. No canon characters like Luke Skywalker, etc. "
                f"These bounties appear on an encrypted black-market network or seedy bounty hunter board. "
                f"The setting is 2BBY, during the height of the Empire. This is a grounded, gritty galaxy. No Jedi, no Force, no lightsabers.\\n\\n"
                f"Each bounty is for a specific target. These individuals are wanted for various reasons — betrayal, theft, desertion, murder, smuggling, sabotage, or other criminal or political offenses.\\n\\n"
                f"For each bounty, include the following:\\n"
                f"1. Target – A name or codename. Can be realistic, alias-based, or underworld-styled. Should sound like a Star Wars character.\\n"
                f"2. Description – 3–6 sentences. Written as if posted to an illicit network. Describe the target's crime, affiliations, last known location, danger level, or unique info. Do NOT use second-person language. This is a listing meant for hardened bounty hunters or syndicate enforcers. Also mention how the bounty is to be completed, whether dead, alive, etc.\\n"
                f"3. Reward – A numeric credit value (between 1000–13,000) based on how high-profile or dangerous the bounty is. Use your judgment. Small-time targets can be under 1,000 credits; major threats or factional figures can command 10,000+.\\n"
                f"4. Client – The name or alias of the individual, faction, or anonymous source who posted the bounty."
                f"5. Stars - The level of 'wanted' or priority level for the bounty from 1-5. A 1 star means highest priority while 5 means lowest"
                f"Use an appropriately gritty, criminal tone — think dark holonet terminal postings. Be terse but evocative. Only use specific planetary names if essential; otherwise refer to regions like 'Outer Rim', 'Mid Rim', 'Expansion Region', etc. Avoid exposition or polite phrasing — this is underworld business."
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

            response_data = json.loads(response.choices[0].message.content)
            bounties_payload = response_data.get("bounties", response_data)
            bounties_generated: list[BountyTemplate] = [
                BountyTemplate.model_validate(bounty)
                for bounty in bounties_payload
            ]
            for bounty in bounties_generated[:num_to_create]:
                new_bounty = Bounties(
                    target=f"{bounty.target} [NPC]",
                    description=bounty.description,
                    reward=bounty.reward,
                    client=bounty.client,
                    stars=bounty.stars
                )
                session.add(new_bounty)
                session.commit()
            embed = Embed(
                title="🛠️ Bounties Generated",
                description=f"Successfully generated **{num_to_create}** bounties.",
                color=0x00ff00  # green
            )
            await interaction.followup.send(embed=embed)

        else:
            else_embed = Embed(
                title="❌ Bounty Generation Failed",
                description="The bounty board is already complete.\n(10 bounties already registered).",
                color=0xff0000
            )
            await interaction.followup.send(embed=else_embed)

        session.close()


async def setup(bot):
    await bot.add_cog(BountyCog(bot))
