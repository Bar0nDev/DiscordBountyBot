import asyncio
import discord
from discord import app_commands, Embed
from discord.ext import commands
from google import genai
from google.genai import types
from pydantic import BaseModel
import os
from utils import *

MAX_GM_RECENT = 40
SUMMARIZE_GM_BATCH = 30

client = genai.Client(api_key=os.getenv("API_KEY"))
MODEL = "gemini-2.0-flash"

character_avatars = [
    ("Gamemaster", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Gamemaster.png?raw=true"),
    ("Stormtrooper", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Stormtrooper.png?raw=true"),
    ("Imperial Officer Male", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Imperial%20Officer%20Male.png?raw=true"),
    ("Stormtrooper Sergeant", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Stormtrooper%20Sergeant.png?raw=true"),
    ("Rebel Soldier", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Rebel.png?raw=true"),
    ("Mercenary", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Mercenary.png?raw=true"),
    ("Bounty Hunter", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Bounty%20Hunter.png?raw=true"),
    ("Death Trooper", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Death%20Trooper.png?raw=true"),
    ("Smuggler", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Smuggler.png?raw=true"),
    ("Droid", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Droid.png?raw=true"),
    ("Imperial Security Droid", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Imperial%20Security%20Droid.png?raw=true"),
    ("Pirate", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Pirate.png?raw=true"),
    ("Man", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Man.png?raw=true"),
    ("Woman", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Woman.png?raw=true"),
    ("Gang Leader", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Gang%20Leader.png?raw=true"),
    ("Twi'lek Female", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Twilek%20F.png?raw=true"),
    ("Unassigned", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Unassigned.png?raw=true"),
    ("Mandalorian", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Mandalorian.png?raw=true"),
    ("TIE Pilot", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/TIE%20Pilot.png?raw=true"),
    ("Rebel Pilot", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Rebel%20Pilot.png?raw=true"),
    ("Imperial Officer Female", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Imperial%20Officer%20F.png?raw=true"),
    ("ISB Agent", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/ISB%20Agent.png?raw=true"),
    ("ISB Officer", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/ISB%20Officer.png?raw=true"),
    ("High-Ranking Imperial", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/High%20ranking%20Imperial%20Officer.png?raw=true"),
    ("Rodian", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Rodian.png?raw=true"),
    ("Imperial Jump Trooper", "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/Jump%20Trooper.png?raw=true"),
]

avatar_index_guide = " ".join(
    f"{i}={name}" for i, (name, _) in enumerate(character_avatars)
)

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
            await report_channel.send(
                f"### 🤖 AI Gamemaster Activated\n"
                f"**Channel:** <#{channel_id}>\n\n"
                f"**🧑 Character Info:**\n> {character}\n\n"
                f"**📍 Location Info:**\n> {location}\n\n"
                f"**🎬 Scenario Info:**\n> {scenario}"
            )
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
    async def gamemaster_chat_core(self, ctx, author=None, msg=None, new_channel=None, new_channel_msg=None):
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
                print("LIMIT REACHED=======")
                to_summarize = recent[:SUMMARIZE_GM_BATCH]
                recent = recent[SUMMARIZE_GM_BATCH:]
                try:
                    chat_log = ""
                    for msg in to_summarize:
                        author = "PLAYER" if msg.role == "user" else "NPC"
                        chat_log += f"{author}: {msg.parts[0].text.strip()}\n"

                    summary_prompt = [
                        types.Content(
                            role='model',
                            parts=[types.Part.from_text(text=
                                                        "Add new, relevant details from the latest roleplay log to "
                                                        "the existing summary. Do NOT remove or rewrite any existing "
                                                        "parts unless there's a factual update or clearer detail. "
                                                        "Only append or enhance. Keep it information-dense and "
                                                        "chronological. Avoid fluff."
                                                        )]
                        ),
                        types.Content(
                            role='user',
                            parts=[types.Part.from_text(text=
                                                        f"**Existing summary:**\n{summary.strip()}\n\n**New chat "
                                                        f"log:**\n{chat_log.strip()}"
                                                        )]
                        )
                    ]

                    summary_response = client.models.generate_content(
                        model=MODEL,
                        contents=summary_prompt,
                        config=types.GenerateContentConfig(
                            max_output_tokens=20000,
                            temperature=0.5,
                            system_instruction=(
                                "Summarize the following roleplay log as a clear, chronological story. "
                                "Describe the events that happened, who did what, and any notable NPCs. "
                                "Include relevant character traits, relationships, and outcomes of each scene. "
                                "Treat this as the 'story so far' — like you're writing a recap for someone who missed earlier sessions.\n\n"
                                "Do NOT speculate or include current goals. Just narrate the events that happened, in order.\n"
                                "Only update or append to the summary. Never remove prior events unless they are contradicted or overwritten by new information in the chat log."
                            )
                        )
                    )
                    summary = summary_response.text.strip()
                    print("Summary so far: ", summary)
                except Exception as e:
                    print(f"GM Summarization error: {e}")

            model_input = []
            if summary:
                model_input.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(
                        text=(
                            "STORY SUMMARY — FOR CONTEXT ONLY\n"
                            "The following is a recap of events that have already happened in the roleplay.\n"
                            "This summary is NOT a current turn, input, or action. It is background context to help you stay consistent:\n\n"
                            f"{summary.strip()}"
                        )
                    )]
                ))
            model_input.extend(recent)
            response = client.models.generate_content(
                model=MODEL,
                contents=recent,
                config=types.GenerateContentConfig(
                    safety_settings=GM_SAFETY_SETTINGS,
                    system_instruction=(
                        "You are an AI Gamemaster for a Star Wars-inspired roleplaying server set in 2BBY, during the height of the Galactic Empire. "
                        "The Clone Wars have ended. The Galactic Republic is gone. The Jedi Order is extinct. The clone army has been decommissioned or repurposed. "
                        "There are NO references to the Republic, Jedi, Sith, Force powers, lightsabers, or Clone Troopers except in past-tense history or Imperial propaganda. "
                        "All content must reflect a gritty, grounded galaxy under Imperial rule. Civilian fear, surveillance, and oppression are constant. "
                        "All factions must reflect the cultural, tactical, and political realities of this era. Stormtroopers are enforcers of the Empire. Rebels are underdogs. "
                        "Narrate only in third person. Never use 'you', 'your', or any second-person phrasing under any circumstances. "
                        "NEVER describe the player character’s actions, thoughts, emotions, speech, posture, movements, or sensory experience. "
                        "NEVER paraphrase or repeat the player’s input. Do not assume or imply anything about the player character. Let the player describe their own character entirely. "
                        "Only describe the environment, NPC actions, and ambient events. Create immersive scenes using environmental motion, sound, and NPC body language. "
                        "Use strong physical details: weather, lighting, surfaces, smell, echoes, crowd movement. Use cinematic pacing and scene rhythm. "
                        "Advance tension through motion and NPC reaction. Close each narration with a sensory or environmental cue, never a question or direct prompt. "
                        "NEVER write passive phrases. Use active, grounded, cinematic language. "
                        "Each NPC action block must contain both action and dialogue. Dialogue must always be physically grounded—tone, facial expression, movement, or interaction with surroundings. "
                        "NEVER allow vague, flat, or generic lines. Instead, show emotional context and physical nuance. "
                        "BAD: 'Yeah, that's great.' *He says as he leans against a wall.* "
                        "GOOD: *The scout shifts his weight against the durasteel column, fingers drumming a jittery rhythm on the stock of his rifle. A flicker of amusement dances across his scarred face.* "
                        "'Yeah, that’s great,' *he mutters, tone dry as dust, eyes scanning the alley like he’s expecting ghosts.* "
                        "Each Gamemaster turn may contain multiple NPCs acting and interacting, but dialogue and action for each NPC must be output as a distinct (character, message, image_index) object. "
                        "NEVER mix multiple NPCs in the same block. "
                        "NEVER let the narration block (Gamemaster/0) contain ANY character speech or action. Only use it to describe environment and ambient events. "
                        "Each NPC post must be 4–8 sentences unless in radio chatter or fast combat. "
                        "All factions and individuals must behave realistically. Everyone has a history, motive, training, and internal logic. Dialogue and behavior must reflect this. "
                        "Assign each NPC an image index from the following list: "
                        f"{avatar_index_guide} "
                        f"Player Character: {scene_info['character']} "
                        f"Location: {scene_info['location']} "
                        f"Scenario: {scene_info['scenario']}"
                    ),
                    max_output_tokens=2000,
                    temperature=0.8,
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

                try:
                    avatar_url = character_avatars[image_index][1]
                except IndexError:
                    avatar_url = None
                async with ctx.channel.typing():
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


    @app_commands.command(name="gamemaster_sessions", description="Show all Game Master sessions in progress")
    @app_commands.checks.has_role("Game Master")
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


    async def handle_gamemaster_message(self, message):
        rp_sessions = load_rp_sessions()
        if message.channel.id not in rp_sessions or not rp_sessions[message.channel.id]:
            return  # Not in an active RP session

        channel_webhook = await self.check_and_create_webhook(message.channel.id)
        if (
                message.webhook_id is not None
                and message.author.bot
                and message.author.discriminator == "0000"
                and not message.content.startswith("(")
                and channel_webhook.id != message.webhook_id
        ):
            ctx = await self.bot.get_context(message)
            await self.gamemaster_chat_core(ctx, author=message.author.display_name, msg=message.content)


    @commands.command(name="gamemaster_chat")
    async def gamemaster_chat(self, ctx, author=None, msg=None, new_channel=None, new_channel_msg=None):
        await self.gamemaster_chat_core(ctx, author, msg, new_channel, new_channel_msg)


async def setup(bot):
    await bot.add_cog(GMCog(bot))
