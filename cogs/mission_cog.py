import asyncio
import json
import traceback
import discord
from discord.ext import commands
from db.models import Missions
from discord import app_commands, Embed
from db.sessions import Session
import os
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy import asc
from utils import moderator_check


MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    return AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL) if api_key else None


class MissionTemplate(BaseModel):
    title: str
    description: str
    reward: int
    difficulty: str


class MissionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    @app_commands.choices(faction=[
        app_commands.Choice(name="Rogue", value="Rogue"),
        app_commands.Choice(name="Imperial", value="Imperial"),
        app_commands.Choice(name="Rebel", value="Rebel"),
        app_commands.Choice(name="Mandalorian", value="Mandalorian"),
    ])
    async def add_mission(self, ctx, title: str, description: str, reward: int, difficulty: app_commands.Choice[str],
                          faction: app_commands.Choice[str]):
        session = Session()

        faction_colors = {
            "Rogue": discord.Colour.from_rgb(220, 20, 60),
            "Imperial": discord.Colour.from_rgb(0, 0, 0),
            "Rebel": discord.Colour.from_rgb(255, 165, 0),
            "Mandalorian": discord.Colour.from_rgb(149, 0, 255)
        }
        embed_color = faction_colors.get(faction.value, discord.Colour.default())

        formatted_title = ' '.join(word.capitalize() for word in title.split())
        embed = discord.Embed(
            colour=embed_color,
            title="📝 Confirm New Mission Details",
            description=(
                f"**🎯 Title:** `{formatted_title}`\n"
                f"> 🛡️ Faction: `{faction.value}`\n"
                f"> ⚙️ Difficulty: `{difficulty.value}`\n"
                f"> 💰 Reward: <:credits:1099938341467738122> **{reward:,}**\n"
                f"> 📝 Description:\n{description}"
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
                if len(session.query(Missions).filter_by(faction=faction.value).all()) == 10:
                    await ctx.send("Error. Too many missions already listed. Maximum of 10 only.")
                else:
                    new_mission = Missions(
                        title=' '.join(x.capitalize() for x in title.split()),
                        description=description,
                        reward=reward,
                        difficulty=difficulty.value,
                        faction=faction.value,
                        availability="Available"
                    )
                    session.add(new_mission)
                    session.commit()
                    await ctx.send("Confirmed! Mission added.")

            elif str(reaction.emoji) == "❌":
                await ctx.send("Canceled request.")

        except asyncio.TimeoutError:
            await ctx.send("Confirmation timed out.")
        session.close()


    @commands.hybrid_command(name="mission_status", description="Claims a mission and sets to 'in progress' or vice versa.")
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(faction='What faction is this mission for?',
                           m_id="What is the mission's ID?"
                           )
    @app_commands.choices(
        faction=[
            app_commands.Choice(name="Rogue", value="Rogue"),
            app_commands.Choice(name="Imperial", value="Imperial"),
            app_commands.Choice(name="Rebel", value="Rebel"),
            app_commands.Choice(name="Mandalorian", value="Mandalorian"),
        ]
    )
    async def mission_status(self, ctx, m_id: int, faction: app_commands.Choice[str]):
        session = Session()

        if m_id not in range(1, 11):
            await ctx.send("❌ Invalid mission ID. Must be between 1 and 10.")
            session.close()
            return

        missions = session.query(Missions).filter_by(faction=faction.value).order_by(asc(Missions.reward)).all()

        if m_id > len(missions):
            await ctx.send("❌ That mission ID doesn't exist for the selected faction.")
            session.close()
            return

        mission = missions[m_id - 1]

        old_status = mission.availability
        new_status = "In Progress" if old_status == "Available" else "Available"
        mission.availability = new_status

        try:
            session.commit()
        except PendingRollbackError:
            session.rollback()

        faction_colors = {
            "Rogue": discord.Colour.from_str("#dc143c"),
            "Imperial": discord.Colour.from_rgb(0, 0, 0),
            "Rebel": discord.Colour.from_str("#ffa500"),
            "Mandalorian": discord.Colour.from_str("#9500ff")
        }
        embed_color = faction_colors.get(faction.value, discord.Colour.default())

        embed = discord.Embed(
            colour=embed_color,
            title=f"🔄 Mission Status Updated — {faction.value} ID: {m_id}",
            description=(
                f"**🎯 {mission.title}**\n"
                f"> ⚙️ Difficulty: `{mission.difficulty}`\n"
                f"> 💰 Reward: <:credits:1099938341467738122> **{mission.reward:,}**\n"
                f"> 📝 Status changed: `{old_status}` ➜ `{new_status}`"
            )
        )
        await ctx.send(embed=embed)
        session.close()


    @commands.hybrid_command(name="edit_mission", description='Edits a mission')
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(faction='What faction is this mission for?',
                           m_id="What is the mission's ID?",
                           mission_field='What mission info to edit?',
                           mission_value="What value to replace mission info?")
    @app_commands.choices(faction=[
        app_commands.Choice(name="Rogue", value="Rogue"),
        app_commands.Choice(name="Imperial", value="Imperial"),
        app_commands.Choice(name="Rebel", value="Rebel"),
        app_commands.Choice(name="Mandalorian", value="Mandalorian"),
    ])
    @app_commands.choices(mission_field=[
        app_commands.Choice(name="Title", value="Title"),
        app_commands.Choice(name="Description", value="Description"),
        app_commands.Choice(name="Reward", value="Reward"),
        app_commands.Choice(name="Difficulty", value="Difficulty"),
    ])
    async def edit_mission(self, ctx, m_id: int, faction: app_commands.Choice[str], mission_field: app_commands.Choice[str],
                           mission_value: str):
        session = Session()

        # Validate mission ID
        if m_id not in range(1, 11):
            await ctx.send("❌ Invalid mission ID. Must be between 1 and 10.")
            session.close()
            return

        try:
            targeted_mission = \
            session.query(Missions).filter_by(faction=faction.value).order_by(asc(Missions.reward)).all()[m_id - 1]
        except IndexError:
            await ctx.send("❌ No mission found for the given ID and faction.")
            session.close()
            return

        success = True

        if mission_field.value == 'Title':
            mission_value = ' '.join(x.capitalize() for x in mission_value.split())
            targeted_mission.title = mission_value

        elif mission_field.value == 'Description':
            targeted_mission.description = mission_value

        elif mission_field.value == 'Reward':
            try:
                targeted_mission.reward = int(mission_value)
            except ValueError:
                await ctx.send("❌ Reward must be a valid integer.")
                session.close()
                return

        elif mission_field.value == 'Difficulty':
            allowed = ['Easy', 'Medium', 'Hard', 'Extreme', 'Impossible']
            diff_value = mission_value.title()
            if diff_value in allowed:
                targeted_mission.difficulty = diff_value
            else:
                await ctx.send(f"❌ Invalid difficulty. Choose one of: {', '.join(allowed)}")
                session.close()
                return

        # Faction-based color
        faction_colors = {
            "Rogue": discord.Colour.from_str("#dc143c"),
            "Imperial": discord.Colour.from_rgb(0, 0, 0),
            "Rebel": discord.Colour.from_str("#ffa500"),
            "Mandalorian": discord.Colour.from_str("#9500ff")
        }
        embed_color = faction_colors.get(faction.value, discord.Colour.default())

        embed = discord.Embed(
            colour=embed_color,
            title=f"🛠️ Confirm Edited Mission - {faction.value} (ID: {m_id})",
            description=(
                f"**🎯 Title:** {targeted_mission.title}\n"
                f"**⚙️ Difficulty:** {targeted_mission.difficulty}\n"
                f"**💰 Reward:** <:credits:1099938341467738122> {targeted_mission.reward:,}\n"
                f"**📜 Description:** {targeted_mission.description}"
            )
        )
        embed.set_footer(text="✅ to confirm, ❌ to cancel.")

        bot_response = await ctx.send(embed=embed)
        await bot_response.add_reaction("✅")
        await bot_response.add_reaction("❌")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == bot_response.id

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            if str(reaction.emoji) == "✅":
                session.commit()
                await ctx.send("✅ Mission updated successfully.")
            else:
                await ctx.send("❌ Edit canceled.")
        except asyncio.TimeoutError:
            await ctx.send("⏰ Confirmation timed out.")

        session.close()


    @commands.hybrid_command(name="all_missions", description="Shows all available missions for each faction.")
    @app_commands.describe(faction='What faction missions to show?')
    @app_commands.choices(faction=[
        app_commands.Choice(name="Rogue", value="Rogue"),
        app_commands.Choice(name="Imperial", value="Imperial"),
        app_commands.Choice(name="Rebel", value="Rebel"),
        app_commands.Choice(name="Mandalorian", value="Mandalorian"),
    ])
    async def all_missions(self, ctx, faction: app_commands.Choice[str]):
        session = None
        try:
            await ctx.defer()
            session = Session()
            missions = session.query(Missions).filter_by(faction=faction.value).order_by(asc(Missions.reward)).all()

            faction_colors = {
                "Rogue": discord.Colour.from_rgb(220, 20, 60),
                "Imperial": discord.Colour.from_rgb(0, 0, 0),
                "Rebel": discord.Colour.from_rgb(255, 165, 0),
                "Mandalorian": discord.Colour.from_rgb(149, 0, 255)
            }
            embed_color = faction_colors.get(faction.value, discord.Colour.default())

            embed_description = ""
            for idx, mission in enumerate(missions, start=1):
                description_str = str(mission.description)
                mission_description = (
                    description_str[:250] + "..."
                    if len(description_str) > 250
                    else description_str
                )
                embed_description += (
                    f"**#{idx} — {mission.title}**\n"
                    f"> ⚙️ Difficulty: `{mission.difficulty}`\n"
                    f"> 📌 Status: `{mission.availability}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{mission.reward:,}**\n"
                    f"> 📝 {mission_description}\n\n"
                )
            embed = discord.Embed(
                colour=embed_color,
                title=f"📜 {faction.value} Mission Board",
                description=embed_description
            )
            await ctx.send(embed=embed)
        except Exception as exc:
            print(f"[all_missions] {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            await ctx.send("❌ Unable to load missions right now. Please try again later.", ephemeral=True)
        finally:
            if session is not None:
                session.close()


    @commands.hybrid_command(name="mission_info", description="Show info for specified mission ID (1-10).")
    @app_commands.describe(m_id="ID of mission",
                           faction='What faction missions to show?')
    @app_commands.choices(faction=[
        app_commands.Choice(name="Rogue", value="Rogue"),
        app_commands.Choice(name="Imperial", value="Imperial"),
        app_commands.Choice(name="Rebel", value="Rebel"),
        app_commands.Choice(name="Mandalorian", value="Mandalorian"),
    ])
    async def mission_info(self, ctx, m_id: int, faction: app_commands.Choice[str]):
        session = Session()
        if m_id not in range(1, 11):
            await ctx.send("❌ Invalid mission ID. Please enter a number from 1 to 10.")
        else:
            missions = session.query(Missions).filter_by(faction=faction.value).order_by(asc(Missions.reward)).all()
            if m_id > len(missions):
                await ctx.send("❌ That mission ID doesn't exist for the selected faction.")
                session.close()
                return
            mission = missions[m_id - 1]

            faction_colors = {
                "Rogue": discord.Colour.from_rgb(220, 20, 60),
                "Imperial": discord.Colour.from_rgb(0, 0, 0),
                "Rebel": discord.Colour.from_rgb(255, 165, 0),
                "Mandalorian": discord.Colour.from_rgb(149, 0, 255)
            }
            embed_color = faction_colors.get(faction.value, discord.Colour.default())

            embed = discord.Embed(
                colour=embed_color,
                title=f"📘 {faction.value} Mission Info — ID: {m_id}",
                description=(
                    f"**🎯 {mission.title}**\n"
                    f"> ⚙️ Difficulty: `{mission.difficulty}`\n"
                    f"> 📌 Status: `{mission.availability}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{mission.reward:,}**\n"
                    f"> 📝 Description:\n{mission.description}"
                )
            )
            await ctx.send(embed=embed)
        session.close()


    @commands.hybrid_command(name="delete_mission", description="Delete mission by specified mission ID (1-10).")
    @commands.check(moderator_check)
    @app_commands.check(moderator_check)
    @app_commands.describe(m_id="ID of mission",
                           faction='What faction mission to delete?')
    @app_commands.choices(faction=[
        app_commands.Choice(name="Rogue", value="Rogue"),
        app_commands.Choice(name="Imperial", value="Imperial"),
        app_commands.Choice(name="Rebel", value="Rebel"),
        app_commands.Choice(name="Mandalorian", value="Mandalorian"),
    ])
    async def delete_mission(self, ctx, m_id: int, faction: app_commands.Choice[str]):
        session = Session()
        if m_id not in range(1, 11):
            await ctx.send("❌ Invalid mission ID. Please enter a number from 1 to 10.")
        else:
            missions = session.query(Missions).filter_by(faction=faction.value).order_by(asc(Missions.reward)).all()

            if m_id > len(missions):
                await ctx.send("❌ That mission ID doesn't exist for the selected faction.")
                session.close()
                return

            mission = missions[m_id - 1]

            faction_colors = {
                "Rogue": discord.Colour.from_rgb(220, 20, 60),
                "Imperial": discord.Colour.from_rgb(0, 0, 0),
                "Rebel": discord.Colour.from_rgb(255, 165, 0),
                "Mandalorian": discord.Colour.from_rgb(149, 0, 255)
            }
            embed_color = faction_colors.get(faction.value, discord.Colour.default())

            embed = discord.Embed(
                colour=embed_color,
                title=f"🗑️ Confirm Deletion — {faction.value} Mission ID: {m_id}",
                description=(
                    f"**🎯 {mission.title}**\n"
                    f"> ⚙️ Difficulty: `{mission.difficulty}`\n"
                    f"> 📌 Status: `{mission.availability}`\n"
                    f"> 💰 Reward: <:credits:1099938341467738122> **{mission.reward:,}**\n"
                    f"> 📝 Description:\n{mission.description}"
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
                    session.delete(mission)
                    session.commit()
                    await ctx.send("Mission deleted.")
                elif str(reaction.emoji) == "❌":
                    await ctx.send("Canceled request.")
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out.")
        session.close()


    @app_commands.command(name="generate_missions", description="Generate missions for the specified faction")
    @app_commands.check(moderator_check)
    @app_commands.describe(faction='What faction to generate missions for?', amount="Number of missions to generate (default: Fills up mission board to 10 total missions)")
    @app_commands.choices(faction=[
        app_commands.Choice(name="Rogue", value="Rogue"),
        app_commands.Choice(name="Imperial", value="Imperial"),
        app_commands.Choice(name="Rebel", value="Rebel"),
        app_commands.Choice(name="Mandalorian", value="Mandalorian"),
    ])
    async def generate_missions(self, interaction: discord.Interaction, faction: app_commands.Choice[str], amount: int = 10):
        await interaction.response.defer()
        deepseek_client = get_deepseek_client()
        if deepseek_client is None:
            await interaction.followup.send(
                "❌ AI mission generation is unavailable because DEEPSEEK_API_KEY is not configured.",
                ephemeral=True,
            )
            return

        session = Session()
        missions = session.query(Missions).filter_by(faction=faction.value).all()
        mission_count = len(missions)

        easy_count = 0
        medium_count = 0
        hard_count = 0
        extreme_count = 0
        impossible_count = 0
        for mission in missions:
            if mission.difficulty == "Easy":
                easy_count += 1
            elif mission.difficulty == "Medium":
                medium_count += 1
            elif mission.difficulty == "Hard":
                hard_count += 1
            elif mission.difficulty == "Extreme":
                extreme_count += 1
            elif mission.difficulty == "Impossible":
                impossible_count += 1


        faction = faction.value
        if mission_count < 10:
            if amount >= 10:
                num_to_create = 10 - mission_count
            else:
                num_to_create = amount
            prompt = (
                f"You are to create {num_to_create} Star Wars-themed missions for the {faction} faction. The server is set in 2BBY, during the height of the Empire. This is a gritty, grounded galaxy. No Jedi. No Force. No canon characters like Luke Skywalker, etc."
                f"Ensure the missions are appropriate for the {faction}'s style. For example:\n"
                f"- Imperial and Rebel missions should be varied. While they may involve direct conflict, they can also include operations like attacking pirate outposts, escorting convoys, gathering intel, or other creative objectives. Also create misisons varied for both navy and ground forces\n"
                f"- Mandalorian and Rogue-aligned missions should reflect a more 'wild west' tone, often involving bounty hunting, smuggling, sabotage, or skirmishes with local factions or major powers.\n"
                f"\nMissions can involve conflict with other major factions (e.g., Imperials vs. Rebels), but should not be exclusively about that. Some missions can be independent or against pirates, crime syndicates, or regional threats.\n"
                f"\nEach mission must include the following:\n"
                f"1. A title\n"
                f"2. A description of the mission with vague details (3-6 sentences). Write mission descriptions without using second-person pronouns like 'you' or 'your'. Describe events, objectives, and situations in a neutral or third-person tone. Do not use weird phrasing such as 'The Imperial faction' or 'the rogue faction' etc. I should be as if these missions are on some kind of 'internet' job board or mission board.\n"
                f"3. A difficulty rating, using only one of the following options: Easy, Medium, Hard, Extreme, Impossible.\n"
                f"4. A credit reward appropriate to the difficulty tier:\n"
                f"   - Easy: 1,000 - 1,300 credits\n"
                f"   - Medium: 1,500 - 2,000 credits\n"
                f"   - Hard: 2,500 - 3,100 credits\n"
                f"   - Extreme: 5,000 - 6,200 credits\n"
                f"   - Impossible: 8,500 - 13,000 credits\n"
                f"There should be in a ratio of 10 missions, a total of 3 easy missions, 2 medium missions, 2 hard missions, 2 extreme missions, 1 impossible mission. Currently, the count of registered mission difficulties out of {mission_count} missions are {easy_count} easies, {medium_count} mediums, {hard_count} hards, {extreme_count} extremes, {impossible_count} impossible."
                f"\nOnly name specific planets if the planet is significant to the mission. Otherwise, use general locations like: Outer Rim, Inner Rim, Mid Rim, Deep Core, Unknown Regions, Galactic Core, Expansion Region, or Colony Region.\n"
            )

            response = await deepseek_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt + "\nReturn a JSON object with a `missions` array."},
                    {"role": "user", "content": "Generate Star Wars themed missions."},
                ],
                response_format={"type": "json_object"},
                temperature=0.8,
            )

            response_data = json.loads(response.choices[0].message.content)
            missions_payload = response_data.get("missions", response_data)
            missions_generated: list[MissionTemplate] = [
                MissionTemplate.model_validate(mission)
                for mission in missions_payload
            ]
            for mission in missions_generated[:num_to_create]:
                new_mission = Missions(
                    title=mission.title,
                    description=mission.description,
                    reward=mission.reward,
                    difficulty=mission.difficulty,
                    faction=faction,
                    availability="Available"
                )
                session.add(new_mission)
                session.commit()
            embed = Embed(
                title="🛠️ Missions Generated",
                description=f"Successfully generated **{num_to_create}** missions for faction **{faction}**.",
                color=0x00ff00  # green
            )
            await interaction.followup.send(embed=embed)

        else:
            else_embed = Embed(
                title="❌ Mission Generation Failed",
                description="The mission list for that faction is already complete.\n(10 missions already registered).",
                color=0xff0000
            )
            await interaction.followup.send(embed=else_embed)

        session.close()


async def setup(bot):
    await bot.add_cog(MissionCog(bot))
