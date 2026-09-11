import asyncio
import discord
from discord import app_commands, Embed
from discord.ext import commands
from google import genai
from google.genai import types
from pydantic import BaseModel
import os
import random
from utils import *

MAX_GM_RECENT = 30
SUMMARIZE_GM_BATCH = 15

client = genai.Client(api_key=os.getenv("API_KEY"))

MODEL = "gemini-2.0-flash"
PRIMARY_MODEL = "gemini-2.5-flash-preview-05-20"

base_url = os.getenv(
    "AVATAR_BASE_URL",
    "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/"
).rstrip("/") + "/"

character_avatars = [
    ("Blue Armor Mandalorian", "Blue%20armor%20Mandalorian.png"),
    ("Bounty Hunter", "Bounty%20Hunter.png"),
    ("Death Trooper", "Death%20Trooper.png"),
    ("Droid", "Droid.png"),
    ("Duros", "Duros.png"),
    ("Female Mandalorian", "Female%Mandalorian.png"),
    ("Gamemaster", "Gamemaster.png"),
    ("Gold Armor Mandalorian", "Gold%20armor%20Mandalorian.png"),
    ("Green Zabrak", "Green%20Zabrak.png"),
    ("High-Ranking Imperial", "High%20ranking%20Imperial%20Officer.png"),
    ("Imperial Officer Female", "Human%20Female%20Imperial%20Officer.png"),
    ("Human Male Black Hair", "Human%20Male%20Black%20Hair.png"),
    ("Human Male Blonde Hair", "Human%20Male%20Blonde%20Hair.png"),
    ("Human Male Mercenary", "Human%20Male%20Mercenary.png"),
    ("Human Male Rebel Soldier", "Human%20Male%20Rebel%20Soldier.png"),
    ("Human Woman Blonde Hair", "Human%20Woman%20Blonde.png"),
    ("IG-88 Assassin Droid", "IG-88%20Assassin%20Droid.png"),
    ("ISB Agent", "ISB%20Agent.png"),
    ("ISB Officer", "ISB%20Officer.png"),
    ("Imperial Jump Trooper", "Imperial%20Jump%20Trooper.png"),
    ("Male Imperial Officer", "Imperial%20Officer%20Male.png"),
    ("Imperial Security Droid", "Imperial%20Security%20Droid.png"),
    ("Ithorian", "Ithorian.png"),
    ("Jawa", "Jawa.png"),
    ("Mon Calamari", "Mon%20Calamari.png"),
    ("Nikto Male", "Nikto%20Male.png"),
    ("Orange Armor Mandalorian", "Orange%20armor%20Mandalorian.png"),
    ("Purple Armor Mandalorian", "Purple%20armor%20Mandalorian.png"),
    ("Rebel Pilot", "Rebel%20Pilot.png"),
    ("Red Zabrak", "Red%20Zabrak.png"),
    ("Red Armor Mandalorian", "Red%20armor%20Mandalorian.png"),
    ("Imperial Scout Trooper", "Scout%20Trooper.png"),
    ("Stormtrooper Sergeant", "Stormtrooper%20Sergeant.png"),
    ("Stormtrooper", "Stormtrooper.png"),
    ("TIE Pilot", "TIE%20Pilot.png"),
    ("Trandoshan", "Trandoshan.png"),
    ("Twilek Female", "Twilek%20Female.png"),
    ("Twilek Male", "Twilek%20Male.png"),
    ("Unassigned", "Unassigned.png"),
    ("White Armor Mandalorian", "White%20armor%20Mandalorian.png"),
    ("Wookie", "Wookie.png"),
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
        try:
            channel = await self.bot.fetch_channel(channel_id)
            if not channel:
                return None

            webhooks = await channel.webhooks()
            bot_webhook = next((webhook for webhook in webhooks if webhook.user.id == self.bot.user.id), None)

            if bot_webhook is None:
                bot_webhook = await channel.create_webhook(name="R0-U41 Hook")

            return bot_webhook

        except Exception as e:
            print(f"Webhook creation error: {e}")
            return None




    @commands.hybrid_command(name="gamemaster_start", description="Use the power of AI for your roleplay experience!")
    @app_commands.describe(
        character="Briefly enter important details about the character (Allegiance, name/s, species, etc.).",
        location="Enter the location.",
        scenario="Roleplay Scenario.",
        difficulty="Optional difficulty (Easy, Medium, Hard, etc.).")
    @commands.has_role("Game Master")
    async def gamemaster_start(self, ctx, character: str, location: str, scenario: str, difficulty: str = "default"):
        interaction = ctx.interaction
        if interaction is not None:
            await ctx.defer(ephemeral=True)

        channel_id = ctx.channel.id

        # Send reports of GM sessions
        try:
            report_channel = self.bot.get_channel(991747728298225764)
            await report_channel.send(
                f"### 🤖 AI Gamemaster Activated\n"
                f"**Channel:** <#{channel_id}>"
            )
        except:
            pass

        rp_sessions = load_rp_sessions()

        if channel_id not in rp_sessions or not rp_sessions[channel_id]:
            rp_sessions[channel_id] = {
                "scene_info": {"character": character, "location": location, "scenario": scenario, "difficulty": difficulty},
                "summary": "",
                "recent": [],
                "char_list": {}}

            save_rp_sessions(rp_sessions)

            await ctx.channel.send(
                "✅ Gamemaster session started. R0-U41 is now listening in this channel.",
                delete_after=60
            )
            if interaction is not None:
                await interaction.delete_original_response()

            await ctx.invoke(self.bot.get_command("gamemaster_chat"), author="Gamemaster",
                             msg="Set up the scene, environment, or situation for the player")
        else:
            await ctx.send(
                "A scenario is already in progress. Finish the current mission with /gamemaster_stop or change scenario location.",
                ephemeral=True
            )
            if interaction is not None:
                await interaction.delete_original_response()


    async def gamemaster_chat_core(self, ctx, author=None, msg=None, new_channel=None, new_channel_msg=None):
        try:
            rp_sessions = load_rp_sessions()

            if new_channel:
                channel = await self.bot.fetch_channel(new_channel)
            else:
                channel = ctx.channel

            # Add null check for channel
            if not channel:
                await ctx.send("❌ Could not access channel. Please try again.")
                return

            channel_webhook = await self.check_and_create_webhook(channel.id)

            # Add null check for webhook
            if not channel_webhook:
                await ctx.send("❌ Could not create webhook. Please try again.")
                return

            # Add session existence check
            if channel.id not in rp_sessions or not rp_sessions[channel.id]:
                await ctx.send("❌ No active GM session in this channel.")
                return

            rp_session = rp_sessions[channel.id]
            scene_info = rp_session["scene_info"]
            summary = rp_session["summary"]
            recent = rp_session["recent"]
            char_list = rp_session["char_list"]

            # Build user message
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

            # Handle message limit and summarization
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
                            max_output_tokens=2000,
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

            # Start typing indicator and get response with retry logic
            async with channel.typing():
                parsed_output = await self.get_gm_response_with_retry(recent, scene_info, summary, max_retries=3)

                if not parsed_output:
                    await channel.send(
                        "🤖 *The AI systems are experiencing interference. Please try your action again.*")
                    return

                # Process the successful response
                combined_message = ""

                for char_turn in parsed_output:
                    # Add validation for each turn
                    if not hasattr(char_turn, 'character') or not hasattr(char_turn, 'message'):
                        print(f"Invalid CharTurn object: {char_turn}")
                        continue

                    character = char_turn.character
                    message = char_turn.message

                    # Skip empty messages
                    if not message or not character:
                        continue

                    if character not in char_list:
                        image_index = char_turn.avatar
                        char_list[character] = image_index
                    else:
                        image_index = char_list[character]

                    try:
                        avatar_url = base_url + character_avatars[image_index][1] + "?raw=true"
                    except IndexError:
                        avatar_url = None

                    # Add individual typing delay for each character response
                    thinking_time = random.uniform(1, 3)
                    typing_time = len(message) * random.uniform(0.08, 0.12)
                    response_delay = thinking_time + typing_time

                    await asyncio.sleep(response_delay)
                    await channel_webhook.send(
                        content=message,
                        username=character,
                        avatar_url=avatar_url
                    )
                    combined_message += f"NPC: {character}, Message: {message}\n"

                recent.append(types.Content(
                    role='model',
                    parts=[types.Part.from_text(text=combined_message.strip())]
                ))

                # Save the session
                rp_sessions[channel.id] = {
                    "scene_info": scene_info,
                    "summary": summary,
                    "recent": recent,
                    "char_list": char_list
                }
                save_rp_sessions(rp_sessions)

        except Exception as e:
            # More detailed error logging
            import traceback
            error_details = traceback.format_exc()
            print(f"GM ERROR Details: {error_details}")

            await channel.send(
                f"The main power has cut off. Redirecting circuit source to auxiliary backup. Contacting <@407151046108905473>\n"
                f"Error ID: {hash(str(e)) % 10000}"  # Simple error ID for tracking
            )

    async def get_gm_response_with_retry(self, recent, scene_info, summary, max_retries=3):
        """
        Attempts to get GM response with retry logic and exponential backoff.
        Keeps typing indicator active throughout all attempts.
        """
        base_delay = 30  # Start with 30 second delay

        for attempt in range(max_retries):
            try:
                print(f"GM API attempt {attempt + 1}/{max_retries}")

                response = client.models.generate_content(
                    model=PRIMARY_MODEL,
                    contents=recent,
                    config=types.GenerateContentConfig(
                        safety_settings=GM_SAFETY_SETTINGS,
                        system_instruction=(
                            "You are an AI Gamemaster for a Star Wars-inspired roleplaying server set in 2BBY, during the height of the Galactic Empire. "
                            "This is a gritty, grounded galaxy. No Jedi. No Force. No lightsabers. "
                            "Oppression, surveillance, and violence are everywhere. Imperial forces are organized and brutal. Rebels are hunted underdogs. "

                            "You must be *factually accurate to canon Star Wars lore*. Every alien species, weapon, ship, droid, or uniform must be described using real and accurate features only—no invented biology, weapons, or gear. "
                            "If you name a species (e.g., Rodian, Twi'lek, Trandoshan), their anatomy and behavior must match official Star Wars canon. Do not invent features (e.g., Rodians do not have mandibles). "
                            "If you use a droid type (e.g., Commando Droid, KX-series), its appearance, behavior, and equipment must reflect real Star Wars depictions (e.g., Commando Droids do NOT have wrist blasters; they carry E-5 blasters, etc). "
                            "Use only official Star Wars weapons, armor, tech, and vehicles that existed or were plausible in 2BBY. Refrain from mixing in EU/Legends-only material unless pre-approved. "

                            "Narrate only in third person. NEVER use the second person with words like 'you,' 'your', etc. "
                            "NEVER describe the player character’s actions, emotions, thoughts, or dialogue. NEVER speak for the player. "
                            "The player controls their own character. You describe only the world, NPCs, and ambient events. "
                            "NPCs must act fast and decisively, with no narrative fairness. "

                            "If stealth fails, reinforcements arrive. If civilians die or faces are seen, bounties and investigations follow. "
                            "NEVER let the player control NPC behavior. NPCs act on their own knowledge, instincts, and orders. "
                            "Always end each GM turn with something the player can respond to: a threat, sound, movement, or dialogue. "
                            "Do not stall or leave NPC conversations hanging. Always complete a beat. "
                            "BAD: *The officer turns.* \"Tell them we—\" "
                            "GOOD: *The officer turns, jaw tight.* \"Tell them we’re not leaving until the last body is found.\" *His fingers tighten on the blaster at his side.* "

                            "Use *asterisks* for all action. Use \"quotes\" for dialogue. Use ``backticks`` for radio comms. "
                            "Each NPC post must include action and dialogue, and show personality through tone, motion, or expression. "
                            "BAD: \"Yeah, that's great.\" *He leans on a wall.* "
                            "GOOD: *The scout shifts his weight against the durasteel column, fingers drumming on his rifle. A flicker of amusement crosses his scarred face.* \"Yeah, that’s great.\" "

                            "Each NPC must be in a separate object. NEVER combine multiple NPCs in one block. "
                            "The GM narration block must NEVER contain any character action or dialogue—only environmental detail, ambient noise, or motion. "
                            "Scene narration must remain cinematic: weather, shadows, footsteps, distant voices, sparks, flickering lights. "

                            "Assign each NPC an image index based on their profile in the following list: "
                            f"{avatar_index_guide} "

                            "When generating NPC names:\n"
                            "- If the NPC is named, use their full name (e.g., 'Major Rhen', 'Sergeant Nalto'). Do not fall back to a generic title.\n"
                            "- If the NPC is unnamed, use only their archetype (e.g., 'Stormtrooper', 'Imperial Officer', 'Death Trooper').\n"
                            "- NEVER include gender or avatar reference terms in the display name (e.g., 'Imperial Officer Male' is incorrect — use 'Imperial Officer' instead).\n"
                            "- The avatar index (e.g., 'Male Imperial Officer') is for internal avatar image lookup only. It should NOT appear in the name shown to players.\n"


                            f"Player Character: {scene_info['character']} "
                            f"Location: {scene_info['location']} "
                            f"Scenario: {scene_info['scenario']} "
                            f"Difficulty: {scene_info['difficulty']} "

                            "The difficulty setting affects all gameplay systems and tone. Treat it as a modifier for outcomes and opposition behavior:"
                            "- Higher difficulty reduces player action success rates. Success requires stronger logic, better planning, and favorable conditions. Failure has harsher consequences. "
                            "- Mission failure is allowed and expected at high difficulty. Objectives can be missed. Consequences must escalate logically. "
                            "- Enemy NPCs scale with difficulty. At higher settings, they act with more skill, aggression, and tactical awareness. They are better trained, better equipped, and less hesitant. "
                            "- Environmental risk scales too: patrol density, surveillance coverage, and local support worsen at higher difficulty. "
                            "- Easy missions may allow recoveries or luck. Hard or Extreme missions do not. Enemies exploit every weakness. No narrative safety net. "
                            "- Difficulty affects tone, pacing, and risk. It must influence narration, NPC behavior, and world response consistently. "

                            "The following is a recap of events that have already happened in the roleplay. This is context only:\n\n"
                            f"{summary.strip()}"
                        ),
                        max_output_tokens=2000,
                        temperature=0.8,
                        response_mime_type="application/json",
                        response_schema=list[CharTurn]
                    )
                )

                # Validate response
                if not response:
                    raise ValueError("API returned empty response")

                if not hasattr(response, 'parsed') or response.parsed is None:
                    raise ValueError("API response missing parsed content")

                parsed_output: list[CharTurn] = response.parsed

                if not isinstance(parsed_output, list):
                    raise ValueError(f"Expected list, got {type(parsed_output)}")

                if len(parsed_output) == 0:
                    raise ValueError("API returned empty character list")

                # Success! Return the parsed output
                print(f"GM API success on attempt {attempt + 1}")
                return parsed_output

            except Exception as api_error:
                print(f"GM API attempt {attempt + 1} failed: {api_error}")

                # If this was the last attempt, try fallback
                if attempt == max_retries - 1:
                    print("Trying fallback model...")
                    try:
                        fallback_response = client.models.generate_content(
                            model=MODEL,  # Fallback model
                            contents=[
                                types.Content(
                                    role='user',
                                    parts=[
                                        types.Part.from_text(text="SYSTEM: Continue the scene with a brief response.")]
                                )
                            ],
                            config=types.GenerateContentConfig(
                                max_output_tokens=500,
                                temperature=0.8,
                                response_mime_type="application/json",
                                response_schema=list[CharTurn]
                            )
                        )

                        if fallback_response and fallback_response.parsed:
                            print("Fallback model succeeded")
                            return fallback_response.parsed
                        else:
                            print("Fallback model also failed")
                            return None

                    except Exception as fallback_error:
                        print(f"Fallback model error: {fallback_error}")
                        return None
                else:
                    # Calculate delay with some randomization to avoid thundering herd
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 10)
                    print(f"Waiting {delay:.1f} seconds before retry...")

                    # The typing indicator stays active during this delay
                    await asyncio.sleep(delay)

        return None


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
            target_channel = self.bot.get_channel(991747728298225764)

            if summary_prompt:
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

                embed = Embed(
                    title="Gamemaster Session Ended",
                    description=f"The Gamemaster session for channel <#{ctx.channel.id}> has been stopped.",
                    color=0x00ff00
                )
                embed.add_field(name="Character & NPC Updates", value=character_summary, inline=False)
                embed.add_field(name="Location/Scene Changes", value=location_summary, inline=False)
                embed.add_field(name="Summary of Events", value=scenario_summary, inline=False)

                if target_channel:
                    await target_channel.send(embed=embed)
                else:
                    print("Error: Could not find the target channel.")
            else:
                await target_channel.send("A Game Master Session has been stopped. Unfortunately, no summary was generated.")


            del rp_sessions[channel_id]
            save_rp_sessions(rp_sessions)

            await ctx.send("✅ Gamemaster for this channel has been stopped successfully.", ephemeral=True)


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
        await interaction.response.send_message(embed=embed, ephemeral=True)


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
