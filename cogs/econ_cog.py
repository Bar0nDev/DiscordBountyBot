import asyncio
import discord
from discord.ext import commands
from unbelievaboat import Client
import dotenv
import random
import os

dotenv.load_dotenv()
guild_id = 709884234214408212

class EconCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name='pod_racing', description="Start a Pod Race! Bet money!")
    async def pod_race(self, ctx):
        turns = 15
        bet = 100
        pods = ["Blaze Runner", "Turbo Twister", "Night Comet"]
        standings = pods.copy()
        random.shuffle(standings)
        pod_emojis = ["🔥",
                      "🌪️",
                      "☄️"]
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(255, 215, 0),
            title=f"🏁 The Pod Race is About to Begin! 🏁",
            description=f"Place your bets! The racers are warming up and ready to go.\n\n"
                        f"**Bet <:credits:1099938341467738122> {bet} credits** by reacting with the pod number:\n\n"
                        f"1️⃣ **{pod_emojis[0]} - Blaze Runner**\n\n"
                        f"2️⃣ **{pod_emojis[1]} - Turbo Twister**\n\n"
                        f"3️⃣ **{pod_emojis[2]} - Night Comet**\n\n\n"
                        f"🚨 *Hurry up! The race is about to start! Bets are locked in **30** seconds* 🚨"
        )
        embed.set_footer(text="React below with the corresponding pod racer number!")
        embed.set_image(
            url='https://i.imgur.com/K2JoRC7.gif')
        bot_response = await ctx.send(embed=embed)
        reactions = ["1️⃣", "2️⃣", "3️⃣"]
        for reaction in reactions:
            await bot_response.add_reaction(reaction)

        reaction_dict = {1: [], 2: [], 3: []}

        def check(reaction, user):
            return (
                    user != self.bot.user
                    and reaction.message.id == bot_response.id
                    and str(reaction.emoji) in reactions
            )

        try:
            while True:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=30, check=check)
                for other_emoji in reactions:
                    if other_emoji != str(reaction.emoji):
                        await bot_response.remove_reaction(other_emoji, user)

                for key in reaction_dict:
                    emoji = reactions[key - 1]
                    if str(reaction.emoji) == emoji:
                        if user not in reaction_dict[key]:
                            reaction_dict[key].append(user)

                for key in reaction_dict:
                    if key != reactions.index(str(reaction.emoji)) + 1 and user in reaction_dict[key]:
                        reaction_dict[key].remove(user)

        except:
            num_players = 0
            async with Client(os.getenv("U_TOKEN")) as u_client:
                guild = await u_client.get_guild(guild_id)
                for option in reaction_dict:
                    for player in reaction_dict[option]:
                        num_players += 1
                        user = await guild.get_user_balance(player.id)
                        await user.update(bank=-bet)
            if num_players:
                countdown_embed = discord.Embed(
                    title="🏎️  Pods are Lining Up!  🏎️",
                    description=f"The engines roar to life! \nThe race will begin in **10** seconds!",
                    colour=discord.Colour.dark_red()
                )
                countdown_embed.set_image(url="https://i.imgur.com/hPUns6I.gif")
                race_response = await ctx.send(embed=countdown_embed)
                await asyncio.sleep(10)

                for n in range(turns):
                    race_action = "All pods **keep** their positions!"
                    if random.getrandbits(1):
                        pod_1 = random.choice(standings[1:])
                        pod_1_index = standings.index(pod_1)

                        remaining_pods = [pod for pod in pods if pod != pod_1 and standings.index(pod) < pod_1_index]
                        pod_2 = random.choice(remaining_pods)
                        pod_2_index = standings.index(pod_2)

                        race_action = f"{pod_emojis[pods.index(pod_1)]} {pod_1} **overtakes** {pod_emojis[pods.index(pod_2)]} {pod_2}!"
                        standings[pod_1_index], standings[pod_2_index] = standings[pod_2_index], standings[pod_1_index]

                    race_standings = "\n".join(
                        [f"{ind}. {pod_emojis[pods.index(racer)]} {racer}" for ind, racer in enumerate(standings)])
                    race_embed = discord.Embed(
                        title="🏁 The Pod Race is On! 🏁",
                        description=(
                            f"Lap **{n + 1}** of {turns}\n\n"
                            f"**Current Standings:**\n{race_standings}\n\n"
                            f"**Race Highlights:**\n{race_action}\n\n"),
                        colour=discord.Colour.green()
                    )
                    race_embed.set_footer(text="Hold on to your bets! Anything can happen!")
                    race_embed.set_image(
                        url="https://static.wikia.nocookie.net/starwars/images/b/bc/Podrace.png/revision/latest?cb=20130120003616")

                    await race_response.edit(embed=race_embed)
                    await asyncio.sleep(3)

                total_pool = (num_players * bet) * 2
                individual_reward = int(total_pool // num_players)
                async with Client(os.getenv("U_TOKEN")) as u_client:
                    guild = await u_client.get_guild(guild_id)
                    for player in reaction_dict[pods.index(standings[0]) + 1]:
                        user = await guild.get_user_balance(player.id)
                        await user.update(bank=+individual_reward)

                result_embed = discord.Embed(
                    title="🏆 Pod Racing Results 🏆",
                    description=(
                        f"Laps: {turns}\n\n"
                        f"**Final Standings:**\n\n{race_standings}\n\n"
                        f"<:credits:1099938341467738122> Credits have been distributed."),
                    colour=discord.Colour.from_rgb(255, 215, 0)
                )
                result_embed.set_footer(text="Congratulations to the winning pod racers!")
                result_embed.set_image(
                    url="https://media2.giphy.com/media/3ornk6AoeOfjdZoRLq/giphy.gif?cid=6c09b9522dizx8gp7g58tp22i6c5vakw3ote49aoz0pjoomv&ep=v1_internal_gif_by_id&rid=giphy.gif&ct=g")
                await ctx.send(embed=result_embed)
            else:
                cancel_embed = discord.Embed(
                    colour=discord.Colour.red(),
                    title=f"❌ Pod Race Cancelled ❌",
                    description=f"No players have bet! The race is cancelled.\n\nTo bet on pod races, react to a pod racer"
                                f" emoji number during race start!"
                )
                cancel_embed.set_image(url="https://media1.tenor.com/m/hc4Q6xfGJpUAAAAd/mars-guo-star-wars.gif")
                await bot_response.edit(embed=cancel_embed)
                await bot_response.clear_reactions()


    async def bump_reminder(self, channel):
        await asyncio.sleep(7171)
        await channel.send("🔔 <@&1317012335516450836> Time to bump again!")


    async def process_disboard_bump(self, message):
        # Check if interaction is a Disboard Bump
        if message.author.id == 302050872383242240:
            if message.interaction_metadata and "Bump done!" in message.embeds[0].description:
                user_id = message.interaction_metadata.user.id

                # Add money
                async with Client(os.getenv("U_TOKEN")) as u_client:
                    guild = await u_client.get_guild(guild_id)
                    user = await guild.get_user_balance(user_id)
                    await user.update(bank=+300)
                embed = discord.Embed(
                    colour=discord.Colour.from_rgb(0, 0, 0),
                    title=f"✅  Transmission Received",
                    description=f"Your efforts have been acknowledged.\n\n"
                                f"<:credits:1099938341467738122> **300 credits** have been authorized and added to your account.\n\n\n"
                                f"Thanks for bumping!",
                )
                embed.set_image(
                    url=r"https://64.media.tumblr.com/f62a40f90224433a506da567f2be4d23/tumblr_nzqkxdieib1rlapeio2_500.gifv")
                await message.channel.send(embed=embed)
                await self.bump_reminder(message.channel)


    async def process_oc_submission(self, message):
        if message.channel.id == 991828501466464296:
            if "approved" in message.content.lower() or "accepted" in message.content.lower():
                async with Client(os.getenv("U_TOKEN")) as u_client:
                    guild = await u_client.get_guild(guild_id)
                    user = await guild.get_user_balance(message.author.id)
                    await user.update(bank=+300)
                await message.add_reaction("✅")


    async def process_bumps(self, message):
        await self.process_disboard_bump(message)
        await self.process_oc_submission(message)



async def setup(bot):
    await bot.add_cog(EconCog(bot))