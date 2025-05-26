import asyncio
import discord
from discord import app_commands, Embed
from discord.ext import commands
from google import genai
from google.genai import types
from pydantic import BaseModel
import os
from utils import *

MAX_GM_RECENT = 15
SUMMARIZE_GM_BATCH = 7

client = genai.Client(api_key=os.getenv("API_KEY"))
MODEL = "gemini-2.0-flash"

character_avatars = {
    0: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Gamemaster.png?raw=true",
    1: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Stormtrooper.png?raw=true",
    2: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Imperial%20Officer%20Male.png?raw=true",
    3: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Stormtrooper%20Sergeant.png?raw=true",
    4: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Rebel.png?raw=true",
    5: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Mercenary.png?raw=true",
    6: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Bounty%20Hunter.png?raw=true",
    7: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Death%20Trooper.png?raw=true",
    8: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Smuggler.png?raw=true",
    9: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Droid.png?raw=true",
    10: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Imperial%20Security%20Droid.png?raw=true",
    11: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Pirate.png?raw=true",
    12: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Man.png?raw=true",
    13: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Woman.png?raw=true",
    14: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Gang%20Leader.png?raw=true",
    15: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Twilek%20F.png?raw=true",
    16: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Unassigned.png?raw=true",
    17: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Mandalorian.png?raw=true",
    18: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/TIE%20Pilot.png?raw=true",
    19: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Rebel%20Pilot.png?raw=true",
    20: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Imperial%20Officer%20F.png?raw=true",
    21: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/ISB%20Agent.png?raw=true",
    22: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/ISB%20Officer.png?raw=true",
    23: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/High%20ranking%20Imperial%20Officer.png?raw=true",
    24: "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Rodian.png?raw=true"
}

GM_SAFETY_SETTINGS = [
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


class CharTurn(BaseModel):
    character: str
    message: str
    avatar: int


class SessionSummary(BaseModel):
    character: str
    location: str
    scenario: str


class GMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_and_create_webhook(self, channel_id):
        channel = await self.bot.fetch_channel(channel_id)
        webhooks = await channel.webhooks()
        bot_webhook = next((webhook for webhook in webhooks if webhook.user.id == self.bot.user.id), None)
        if bot_webhook is None:
            bot_webhook = await channel.create_webhook(name="R0-U41 Hook")
        return bot_webhook

    @commands.hybrid_command(name="gamemaster_start", description="Use the power of AI for your roleplay experience!")
    @app_commands.describe(
        character="Briefly enter important details about the character (Allegiance, name/s, species, etc.).",
        location="Enter the location.", scenario="Roleplay Scenario.")
    @commands.has_role("Game Master")
    async def gamemaster_start(self, ctx, character: str, location: str, scenario: str):
        channel_id = ctx.channel.id

        # Send reports of GM sessions
        try:
            report_channel = self.bot.get_channel(991747728298225764)
            embed = Embed(
                title="🤖 AI Gamemaster Session Started",
                description=f"A new AI GM session has started in <#{channel_id}>.\nUse the button below to copy the command.",
                color=000000
            )

            view = GamemasterStartView(character, location, scenario)
            await report_channel.send(embed=embed, view=view)
        except:
            pass

        rp_sessions = load_rp_sessions()

        if channel_id not in rp_sessions or rp_sessions[channel_id] != ():
            rp_sessions[channel_id] = {
                "scene_info": {"character": character, "location": location, "scenario": scenario},
                "summary": "",
                "recent": [],
                "char_list": {}}

            save_rp_sessions(rp_sessions)

            await ctx.send("Gamemaster mode activated for this channel! Now listening to messages. "
                           "Remember to use '(' when talking out of RP.", delete_after=60)

            await ctx.invoke(self.bot.get_command("gamemaster_chat"), author="Gamemaster",
                             msg="Set up the scene, environment, or situation for the player")
        else:
            await ctx.send(
                "A scenario is already in progress. Finish the current mission with /gamemaster_stop or change scenario location.")

    @commands.command()
    async def gamemaster_chat(self, ctx, author=None, msg=None, new_channel=None, new_channel_msg=None):
        rp_sessions = load_rp_sessions()

        if new_channel:
            channel = await self.bot.fetch_channel(new_channel)
        else:
            channel = ctx.channel

        channel_webhook = await self.check_and_create_webhook(channel.id)
        rp_session = rp_sessions[channel.id]
        scene_info = rp_session["scene_info"]
        summary = rp_session["summary"]
        recent = rp_session["recent"]
        char_list = rp_session["char_list"]

        try:
            if msg:
                user_message = f"Player {author}: {msg}"
            elif new_channel is not None and new_channel_msg is not None:
                user_message = f"SYSTEM INSTRUCTIONS: The player scene has transitioned to the described place, {new_channel_msg}"
                scene_info['location'] = new_channel_msg
            else:
                user_message = "SYSTEM INSTRUCTIONS: CONTINUE"

            recent.append(types.Content(
                role='user',
                parts=[types.Part.from_text(text=user_message)]
            ))

            if len(recent) > MAX_GM_RECENT:
                to_summarize = recent[:SUMMARIZE_GM_BATCH]
                recent = recent[SUMMARIZE_GM_BATCH:]
                try:
                    summary_prompt = []
                    if summary:
                        summary_prompt.append(types.Content(role='user', parts=[types.Part.from_text(text=summary)]))
                    summary_prompt.extend(to_summarize)

                    summary_response = client.models.generate_content(
                        model=MODEL,
                        contents=summary_prompt,
                        config=types.GenerateContentConfig(
                            max_output_tokens=20000,
                            temperature=0.3,
                            system_instruction="With the following roleplay history, make a brief and concise summary for "
                                               "your own reference with details to remember to facilitate accurate the player's roleplay with you being the Gamemaster. "
                                               "If the summary gets too long,"
                                               "start removing less significant information."
                        )
                    )
                    summary += "\n" + summary_response.text.strip()
                except Exception as e:
                    print(f"GM Summarization error: {e}")

            model_input = []
            if summary:
                model_input.append(types.Content(
                    role="system",
                    parts=[
                        types.Part.from_text(text=f"Summary of past details of roleplay session:\n{summary.strip()}")]
                ))
            model_input.extend(recent)
            response = client.models.generate_content(
                model=MODEL,
                contents=recent,
                config=types.GenerateContentConfig(
                    safety_settings=GM_SAFETY_SETTINGS,
                    system_instruction=(
                        "You are an AI Gamemaster for a Star Wars-inspired roleplaying server set in 2BBY. "
                        "The galaxy is under Imperial control. No Jedi, Sith, Force powers, lightsabers, or canon characters are allowed. All content must be original. "
                        "Narrate in third person only — never use second person or refer to the player directly. Never describe the player character’s actions, thoughts, or internal reactions. "
                        "You control narrative pacing, dramatic tension, and the success or failure of player actions. All outcomes must remain grounded and plausible. "
                        "Write immersive, cinematic narration. Use strong environmental detail (weather, lighting, noise, architecture), sensory input (smell, heat, vibrations, textures), emotional tone, and body language. "
                        "Each GM turn must advance the scene’s tension or context through ambient movement, NPC reactions, or physical changes. Use rhythm and sensory shifts to create immersion. "
                        "Never end a turn by prompting the player with a question, especially not in the form 'What do you do?' or 'How do you respond?'. Instead, close with an evocative cue: a sound, look, motion, or rising tension. "
                        "NPCs must always speak and act within the same block. Dialogue must be embedded with gesture, tone, or circumstance — never deliver plain, isolated speech. Flat talk is forbidden. "
                        "Avoid paraphrasing or reflecting player input. Let the player drive their own character. "
                        "Use *asterisks* for narration, \"quotes\" for spoken dialogue, and `backticks` for radio transmissions. "
                        "Each GM turn may include multiple NPCs interacting. Dialogue between NPCs should not be cut mid way. "
                        "However, each NPC’s speech and actions must be output as a distinct (character, message, image_index) object — do not mix multiple NPCs in a single NPC block. "
                        "Never let the Gamemaster narration contain the speech or actions of another NPC. "
                        "Each NPC post must be 4–8 sentences. Use shorter bursts only for radio or urgent combat. "
                        "Portray all factions and individuals with realistic motives, emotion, training, and cultural context. All characters must feel lived-in. "
                        "Assign each NPC an image index from the following list: "
                        "0=Gamemaster 1=Stormtrooper 2=Imperial Officer Male 3=Stormtrooper Sergeant 4=Rebel Soldier 5=Mercenary 6=Bounty Hunter 7=Death Trooper "
                        "8=Smuggler 9=Droid 10=Imperial Security Droid 11=Pirate 12=Man 13=Woman 14=Gang Leader 15=Twi'lek Female 16=Unassigned 17=Mandalorian "
                        "18=TIE Pilot 19=Rebel Pilot 20=Imperial Officer Female 21=ISB Agent 22=ISB Officer 23=High-Ranking Imperial 24=Rodian. "
                        f"Player Character: {scene_info['character']} "
                        f"Location: {scene_info['location']} "
                        f"Scenario: {scene_info['scenario']}"
                    ),
                    max_output_tokens=2000,
                    temperature=0.7,
                    response_mime_type="application/json",
                    response_schema=list[CharTurn]
                )
            )

            parsed_output: list[CharTurn] = response.parsed

            for char_turn in parsed_output:
                character = char_turn.character
                message = char_turn.message

                if character not in char_list:
                    image_index = char_turn.avatar
                    char_list[character] = image_index
                else:
                    image_index = char_list[character]

                avatar_url = character_avatars.get(image_index)
                async with channel.typing():
                    response_delay = len(message) // 40
                    await asyncio.sleep(response_delay)
                    await channel_webhook.send(
                        content=message,
                        username=character,
                        avatar_url=avatar_url
                    )
                    recent.append(types.Content(
                        role='model',
                        parts=[types.Part.from_text(text=f"NPC: {character}, Message: {message}")]
                    ))

            rp_sessions[channel.id] = {
                "scene_info": scene_info,
                "summary": summary,
                "recent": recent,
                "char_list": char_list
            }
            save_rp_sessions(rp_sessions)
        except Exception as e:
            await channel.send(
                f"The main power has cut off. Redirecting circuit source to auxiliary backup. Contacting <@407151046108905473>")
            print(f"GM ERROR: {e}")

    @commands.hybrid_command(name="gamemaster_stop", description="Stop the gamemaster mode.")
    @commands.has_role("Game Master")
    async def gamemaster_stop(self, ctx):
        await ctx.defer()
        channel_id = ctx.channel.id
        try:
            rp_sessions = load_rp_sessions()
            rp_session = rp_sessions[ctx.channel.id]
            summary = rp_session["summary"]
            recent = rp_session["recent"]

            summary_prompt = []
            try:
                if summary:
                    summary_prompt.append(types.Content(role='user', parts=[types.Part.from_text(text=summary)]))
                summary_prompt.extend(recent)
            except Exception as e:
                print(f"GM Stop Session Summarization failed: {e}")

            response = client.models.generate_content(
                model=MODEL,
                contents=summary_prompt,
                config=types.GenerateContentConfig(
                    safety_settings=GM_SAFETY_SETTINGS,
                    system_instruction="Based on all the events, summarize everything that happened into three ways. Summarize updates on the player"
                                       "and/or new, relevant characters to the player, summarize any location or scene updates, and summarize what happened in a concise"
                                       "yet detailed brief",
                    max_output_tokens=650,
                    temperature=0.8,
                    response_mime_type="application/json",
                    response_schema=SessionSummary
                )
            )
            parsed_response: SessionSummary = response.parsed
            character_summary = parsed_response.character
            location_summary = parsed_response.location
            scenario_summary = parsed_response.scenario

            del rp_sessions[channel_id]
            save_rp_sessions(rp_sessions)

            await ctx.send("✅ Gamemaster for this channel has been stopped successfully.", ephemeral=True)

            embed = Embed(
                title="Gamemaster Session Ended",
                description=f"The Gamemaster session for channel <#{ctx.channel.id}> has been stopped.",
                color=0x000000
            )
            embed.add_field(name="Character & NPC Updates", value=character_summary, inline=False)
            embed.add_field(name="Location/Scene Changes", value=location_summary, inline=False)
            embed.add_field(name="Summary of Events", value=scenario_summary, inline=False)

            target_channel = self.bot.get_channel(991747728298225764)
            if target_channel:
                await target_channel.send(embed=embed)
            else:
                print("Error: Could not find the target channel.")

        except KeyError:
            await ctx.send("❌ There is no active game master session in this channel!", ephemeral=True)
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {e}", ephemeral=True)

    @commands.hybrid_command(name="gamemaster_edit", description="Add context to the gamemaster.")
    @app_commands.describe(
        context="Context to add.")
    @commands.has_role("Game Master")
    async def gamemaster_edit(self, ctx, context):
        rp_sessions = load_rp_sessions()
        channel_id = ctx.channel.id
        if rp_sessions[channel_id] is not None:
            rp_session = rp_sessions[channel_id]
            recent = rp_session["recent"]
            updated_context = f"Updated Context: {context}"
            recent.append(types.Content(
                role='user',
                parts=[types.Part.from_text(text=updated_context)]
            ))
            rp_sessions[channel_id]["recent"] = recent
            save_rp_sessions(rp_sessions)
            await ctx.send("✅ Context updated successfully.", ephemeral=True)
        else:
            await ctx.send("❌ The game master is not active for this channel.", ephemeral=True)

    @commands.hybrid_command(name="gamemaster_continue", description="Have the bot continue with another GM Message")
    async def gamemaster_continue(self, ctx):
        rp_sessions = load_rp_sessions()
        channel_id = ctx.channel.id
        await ctx.send("🔃 Continuing...", ephemeral=True)
        if rp_sessions[channel_id] != ():
            await self.gamemaster_chat(ctx)
        else:
            await ctx.send("❌ The game master is not active for this channel.", ephemeral=True)

    @commands.hybrid_command(name="gamemaster_location", description="Move Game master location")
    @app_commands.describe(channel="Hyperlink of #channel to move to", description="Description of the new location.")
    @commands.has_role("Game Master")
    async def gamemaster_location(self, ctx, channel, description):
        rp_sessions = load_rp_sessions()
        current_channel_id = ctx.channel.id

        try:
            fnew_channel_id = int(channel.replace("<", "").replace(">", "").replace("#", ""))
        except:
            await ctx.send(
                "❌ Invalid channel was provided. Make sure it is the actual blue channel link. Example: <#>1099899000729128960",
                ephemeral=True)
            return

        if current_channel_id in rp_sessions:
            if fnew_channel_id in rp_sessions:
                await ctx.send("❌ A game master session is in progress in that channel. Please select a different one.",
                               ephemeral=True)
            else:
                rp_sessions[fnew_channel_id] = rp_sessions.pop(current_channel_id)
                save_rp_sessions(rp_sessions)
                await ctx.send(f"✅ Location changed to <#{fnew_channel_id}>", ephemeral=True)
                await self.gamemaster_chat(ctx, new_channel=fnew_channel_id, new_channel_msg=description)
        else:
            await ctx.send("❌ There is no active game master session in this channel.", ephemeral=True)

    @commands.tree.command(name="gamemaster_sessions",
                           description="Show all Game Master sessions in progress")
    @commands.has_role("Game Master")
    async def gamemaster_sessions(self, interaction):
        rp_sessions = load_rp_sessions()
        embed_desc = ""
        for channel in rp_sessions:
            if rp_sessions[channel]:
                embed_desc += f"**On** <#{channel}>: {rp_sessions[channel]['scene_info']['character'][:10]}\n\n"
        embed = discord.Embed(
            colour=discord.Colour.from_rgb(0, 255, 0),
            title=f"✅ Showing All Active RP Sessions",
            description=embed_desc
        )
        embed.set_footer(
            text="Here are the ongoing Game Master sessions. To end a session, use /gamemaster_stop in the channel!")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(GMCog(bot))
