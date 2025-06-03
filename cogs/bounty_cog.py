import asyncio
import discord
from discord.ext import commands
from db.models import Bounties
from discord import app_commands, Embed
from db.sessions import Session
from google import genai
from google.genai import types
import os
from pydantic import BaseModel


client = genai.Client(api_key=os.getenv("API_KEY"))
MODEL = "gemini-2.0-flash"


BOUNTY_SAFETY_SETTINGS = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    )
]


class BountyTemplate(BaseModel):
    target: str
    description: str
    reward: int
    client: str


class BountyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="add_bounty", description='Adds a new bounty')
    @commands.has_role("Member")
    @app_commands.describe(target="Who does the bounty target?", description="Bounty description or additional notes?",
                           reward="How much will you pay upon completion? Minimum 150 credits!")
    async def add_bounty(self, ctx, target: str, description: str, reward: int):
        session = Session()
        if reward < 150:
            await ctx.send("Insufficient reward amount set. Canceled request.")
        else:
            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title="Confirm Bounty Details",
                description=f"**Target:** {target}\n\n**Reward:** <:credits:1099938341467738122>{reward:,}\n\n**Client:** {ctx.author}\n\n**Description:** {description}"
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
                            client=str(ctx.author)
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
        session = Session()
        if b_id not in range(1, 11):
            await ctx.send("Invalid bounty ID. Enter an ID number from 1-10")
        else:
            bounty = session.query(Bounties).all()[b_id - 1]
            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title=f"=== Bounty Info - ID: {b_id} ===",
                description=f"**<:credits:1099938341467738122>{bounty.reward:,} - {bounty.target}**\n`From {bounty.client}`\n{bounty.description}"
            )
            await ctx.send(embed=embed)
        session.close()


    @commands.hybrid_command(name="all_bounties", description="Shows all available bounties.")
    async def all_bounties(self, ctx):
        session = Session()
        bounties = session.query(Bounties).all()
        embed_description = ""
        for bounty in bounties:
            embed_description += f"\n\n**<:credits:1099938341467738122>{bounty.reward:,} - ID: {bounties.index(bounty) + 1} - {bounty.target}**\n`From {bounty.client}`\n{bounty.description}"
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(0, 0, 0),
            title="=== Bounty Board ===",
            description=embed_description
        )
        await ctx.send(embed=embed)
        session.close()


    @commands.hybrid_command(name="delete_bounty", description="Delete bounty by specified bounty ID (1-10).")
    @commands.has_role('Game Master')
    @app_commands.describe(b_id="ID of bounty")
    async def delete_bounty(self, ctx, b_id: int):
        session = Session()
        if b_id not in range(1, 11):
            await ctx.send("Invalid bounty ID. Enter an ID number from 1-10")
        else:
            bounty = session.query(Bounties).all()[b_id - 1]
            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 0, 0),
                title=f"=== Delete Bounty - ID: {b_id} ===",
                description=f"**<:credits:1099938341467738122>{bounty.reward:,} - {bounty.target}**\n `From {bounty.client}`\n{bounty.description}"
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
                    session.delete(bounty)
                    session.commit()
                    await ctx.send("Bounty deleted.")
                elif str(reaction.emoji) == "❌":
                    await ctx.send("Canceled request.")
            except asyncio.TimeoutError:
                await ctx.send("Confirmation timed out.")
        session.close()


    @app_commands.command(name="generate_bounties", description="Generate bounties")
    @app_commands.describe(amount="Number of bounties to generate (default: Fills up bounty board to 10 total bounties)")
    async def generate_bounties(self, interaction: discord.Interaction, amount: int = 10):
        await interaction.response.defer()
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
                f"3. Reward – A numeric credit value (between 500–13,000) based on how high-profile or dangerous the bounty is. Use your judgment. Small-time targets can be under 1,000 credits; major threats or factional figures can command 10,000+.\\n"
                f"4. Client – The name or alias of the individual, faction, or anonymous source who posted the bounty.\\n\\n"
                f"Use an appropriately gritty, criminal tone — think dark holonet terminal postings. Be terse but evocative. Only use specific planetary names if essential; otherwise refer to regions like 'Outer Rim', 'Mid Rim', 'Expansion Region', etc. Avoid exposition or polite phrasing — this is underworld business."
            )

            response = client.models.generate_content(
                model=MODEL,
                contents=["Generate Star Wars themed bounties"],
                config=types.GenerateContentConfig(
                    safety_settings=BOUNTY_SAFETY_SETTINGS,
                    system_instruction=prompt,
                    response_mime_type="application/json",
                    temperature=0.8,
                    response_schema=list[BountyTemplate]
                )
            )

            bounties_generated: list[BountyTemplate] = response.parsed
            for bounty in bounties_generated:
                new_bounty = Bounties(
                    target=bounty.target,
                    description=bounty.description,
                    reward=bounty.reward,
                    client=bounty.client
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
