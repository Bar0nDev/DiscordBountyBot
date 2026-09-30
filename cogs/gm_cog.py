import asyncio
import os
import discord
from discord import app_commands
import json
import pickle
from datetime import datetime, timezone, timedelta
from discord.ext import commands
from openai import AsyncOpenAI
from pydantic import BaseModel
import random
import traceback
import re
from typing import Literal
from utils.utils import *
from utils.gm_success_system import ACTION_EVALUATION_TOOL

MAX_GM_RECENT = 25
SUMMARIZE_GM_BATCH = 12

VALID_DIFFICULTIES = Literal["easy", "medium", "hard", "extreme", "impossible", "realistic"]

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# MODEL = "zai-org/GLM-4.7-TEE"
# MODEL = "deepseek-ai/DeepSeek-V3.2-TEE"
# MODEL = "deepseek-ai/DeepSeek-V3-0324-TEE"
# MODEL = "openai/gpt-oss-120b-TEE"
# MODEL = "zai-org/GLM-5-TEE"
# MODEL = "moonshotai/Kimi-K2.5-TEE"
MODEL = "deepseek-chat"

PST = timezone(timedelta(hours=-8))


class CharTurn(BaseModel):
    character: str
    message: str
    avatar: int


class SessionSummaryWithNews(BaseModel):
    character: str
    location: str
    scenario: str
    news_story: str


base_url = "https://github.com/Bar0nDev/SW-AI-GM-Pics/blob/main/gm%20pics/"

character_avatars = [
    ("3PO-series protocol droid", "3PO-series%20protocol%20droid.png"),
    ("B1 Battle Droid", "B1%20Battle%20Droid.png"),
    ("B2 Battle Droid", "B2%20Battle%20Droid.png"),
    ("Bith", "Bith.png"),
    ("Blue Armor Mandalorian", "Blue%20armor%20Mandalorian.png"),
    ("Bounty Hunter", "Bounty%20Hunter.png"),
    ("CIS Tactical Droid", "CIS%20Tactical%20Droid.png"),
    ("CIS Commando Droid", "Commando%20Droid.png"),
    ("Death Trooper", "Death%20Trooper.png"),
    ("Droid", "Droid.png"),
    ("Duros", "Duros.png"),
    ("Female Mandalorian", "Female%Mandalorian.png"),
    ("Female Miralian", "Female%20Miralian.png"),
    ("Female Pantoran", "Female%20Pantoran.png"),
    ("Female Quarren", "Female%20Quarren.png"),
    ("Gamemaster", "Gamemaster.png"),
    ("Gold Armor Mandalorian", "Gold%20armor%20Mandalorian.png"),
    ("Gran", "Gran.png"),
    ("Green Zabrak", "Green%20Zabrak.png"),
    ("High-Ranking Imperial", "High%20ranking%20Imperial%20Officer.png"),
    ("Imperial Officer Female", "Human%20Female%20Imperial%20Officer.png"),
    ("Human Male Black Hair", "Human%20Male%20Black%20Hair.png"),
    ("Human Male Blonde Hair", "Human%20Male%20Blonde%20Hair.png"),
    ("Human Male Mercenary", "Human%20Male%20Mercenary.png"),
    ("Human Male Rebel Soldier", "Human%20Male%20Rebel%20Soldier.png"),
    ("Human Woman Blonde Hair", "Human%20Woman%20Blonde.png"),
    ("Hutt", "Hutt.png"),
    ("IG-88 Assassin Droid", "IG-88%20Assassin%20Droid.png"),
    ("ISB Agent", "ISB%20Agent.png"),
    ("ISB Officer", "ISB%20Officer.png"),
    ("Imperial Army Trooper", "Imperial%20Army%20Trooper.png"),
    ("Imperial Combat Driver", "Imperial%20Combat%20Driver.png"),
    ("Imperial Commando", "Imperial%20Commando.png"),
    ("Imperial Jump Trooper", "Imperial%20Jumptrooper.png"),
    ("Male Imperial Officer", "Imperial%20Officer%20Male.png"),
    ("Imperial Patrol Trooper", "Imperial%20Patrol%20Trooper.png"),
    ("KX series Imperial Droid", "Imperial%20Security%20Droid.png"),
    ("Imperial Shadow Trooper", "Imperial%20Shadow%20Trooper.png"),
    ("Imperial Shock Trooper", "Imperial%20Shock%20Trooper.png"),
    ("Imperial Shore Trooper Captain", "Imperial%20Shore%20Trooper%20Captain.png"),
    ("Imperial Shore Trooper", "Imperial%20Shore%20Trooper.png"),
    ("Imperial Remnant Super Commando", "Imperial%20remnant%20super%20commando.png"),
    ("Ithorian", "Ithorian.png"),
    ("Jawa", "Jawa.png"),
    ("Male Miralian", "Male%20Miralian.png"),
    ("Male Pantoran", "Male%20Pantoran.png"),
    ("Male Quarren", "Male%20Quarren.png"),
    ("Mon Calamari", "Mon%20Calamari.png"),
    ("MSE-6 series Mouse droid", "MSE-6%20series%20Mouse%20droid.png"),
    ("Nikto Male", "Nikto%20Male.png"),
    ("Orange Armor Mandalorian", "Orange%20armor%20Mandalorian.png"),
    ("Ortolan", "Ortolan.png"),
    ("Purple Armor Mandalorian", "Purple%20armor%20Mandalorian.png"),
    ("Pyke Syndicate Foot Soldier", "Pyke%20Syndicate%20foot%20soldier.png"),
    ("R2 Astromech Droid", "R2%20Astromech%20Droid.png"),
    ("RA-7 Protocol Droid", "RA-7%20protocol%20droid.png"),
    ("Rebel Pilot", "Rebel%20Pilot.png"),
    ("Quarren Rebel Soldier", "Rebel%20Quarren.png"),
    ("Red Zabrak", "Red%20Zabrak.png"),
    ("Red Armor Mandalorian", "Red%20armor%20Mandalorian.png"),
    ("Rodian Male", "Rodian%20Male.png"),
    ("Rodian Female", "Rodian%20Female.png"),
    ("Imperial Scout Trooper", "Scout%20Trooper.png"),
    ("CIS Super Tactical Droid", "Super%20Tac%20Droid.png"),
    ("Storm Commando", "Storm%20Commando.png"),
    ("Stormtrooper Sergeant", "Stormtrooper%20Sergeant.png"),
    ("Stormtrooper", "Stormtrooper.png"),
    ("TIE Pilot", "TIE%20Pilot.png"),
    ("Trandoshan", "Trandoshan.png"),
    ("Twilek Female", "Twilek%20Female.png"),
    ("Twilek Male", "Twilek%20Male.png"),
    ("Unassigned", "Unassigned.png"),
    ("Weequay Male", "Weequay%20Male.png"),
    ("White Armor Mandalorian", "White%20armor%20Mandalorian.png"),
    ("Wookie", "Wookie.png"),
    ("BD3000 Luxury Droid", "bd3000%20luxury%20droid.png")
]

avatar_index_guide = " ".join(
    f"{i}={name}" for i, (name, _) in enumerate(character_avatars)
)


class SessionsPaginationView(discord.ui.View):
    def __init__(self, bot, session_data_list, sessions_per_page=5):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.bot = bot
        self.session_data_list = session_data_list
        self.sessions_per_page = sessions_per_page
        self.current_page = 0
        self.max_pages = (len(session_data_list) - 1) // sessions_per_page + 1 if session_data_list else 1

        # Update button states
        self.update_buttons()

    def update_buttons(self):
        # Disable/enable buttons based on current page
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.max_pages - 1)

    async def create_embed(self):
        if not self.session_data_list:
            embed = discord.Embed(
                colour=discord.Colour.from_rgb(0, 255, 0),
                title="✅ Active Game Master Sessions (0)",
                description="No active Game Master sessions found."
            )
            embed.set_footer(text="No sessions to display.")
            return embed

        # Calculate which sessions to show on this page
        start_idx = self.current_page * self.sessions_per_page
        end_idx = min(start_idx + self.sessions_per_page, len(self.session_data_list))
        current_sessions = self.session_data_list[start_idx:end_idx]

        embed_desc = ""
        for i, (channel_id, session_data, channel_info) in enumerate(current_sessions, start=start_idx + 1):
            try:
                channel_mention, character_info, location_info = channel_info

                embed_desc += f"**{i}.** {channel_mention}\n"
                embed_desc += f"   **Character:** {character_info}\n"
                embed_desc += f"   **Location:** {location_info}\n\n"

            except Exception as e:
                embed_desc += f"**{i}.** Unknown Channel ({channel_id})\n"
                embed_desc += f"   **Status:** Session Active (Channel inaccessible)\n\n"

        embed = discord.Embed(
            colour=discord.Colour.from_rgb(0, 255, 0),
            title=f"✅ Active Game Master Sessions ({len(self.session_data_list)})",
            description=embed_desc
        )

        embed.set_footer(
            text=f"Page {self.current_page + 1} of {self.max_pages} • Use /gamemaster_stop in channels to end sessions"
        )

        return embed

    @discord.ui.button(label='◀ Previous', style=discord.ButtonStyle.secondary, custom_id='previous')
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = await self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Next ▶', style=discord.ButtonStyle.secondary, custom_id='next')
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = await self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='🔄 Refresh', style=discord.ButtonStyle.primary, custom_id='refresh')
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Reload session data
        await interaction.response.defer()

        session_ids = load_rp_sessions()
        new_session_data_list = []

        for channel_id in session_ids:
            try:
                session_data = load_session(channel_id)
                if not session_data:
                    continue

                channel = await self.bot.fetch_channel(channel_id)
                channel_mention = f"<#{channel_id}>"
                if hasattr(channel, 'parent') and channel.parent:
                    channel_mention += f" (Thread in <#{channel.parent.id}>)"

                character_info = session_data['scene_info']['character'][:50] + "..." if len(
                    session_data['scene_info']['character']) > 50 else session_data['scene_info']['character']
                location_info = session_data['scene_info']['location'][:30] + "..." if len(
                    session_data['scene_info']['location']) > 30 else session_data['scene_info']['location']

                channel_info = (channel_mention, character_info, location_info)
                new_session_data_list.append((channel_id, session_data, channel_info))

            except Exception as e:
                channel_info = (f"Unknown Channel ({channel_id})", "Session Active", "(Channel inaccessible)")
                new_session_data_list.append((channel_id, None, channel_info))

        # Update the view with new data
        self.session_data_list = new_session_data_list
        self.max_pages = (len(new_session_data_list) - 1) // self.sessions_per_page + 1 if new_session_data_list else 1

        # Reset to first page if current page is now out of bounds
        if self.current_page >= self.max_pages:
            self.current_page = max(0, self.max_pages - 1)

        self.update_buttons()
        embed = await self.create_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def update_summary_section(to_summarize, summary, model):
    """Updated to use OpenAI SDK format"""
    try:
        chat_log = ""
        for msg in to_summarize:
            author = "PLAYER" if msg["role"] == "user" else "NPC"
            chat_log += f"{author}: {msg['content'].strip()}\n"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are updating a roleplay summary. Maintain character consistency — "
                    "if someone dies in the new events, they must be dead in the updated summary. "
                    "Only add genuinely new and important information. Keep it concise but complete."
                )
            },
            {
                "role": "user",
                "content": f"""
                    **CURRENT STORY SUMMARY:**
                    {summary.strip()}

                    **NEW CHAT LOG TO ADD:**
                    {chat_log.strip()}

                    **INSTRUCTIONS:**
                    Update the summary by adding any new important events from the chat log. Focus on:
                    - Character deaths, injuries, or status changes
                    - Major plot developments, battles, discoveries
                    - New characters introduced
                    - Location changes
                    - Important items gained/lost
                    - Key relationship changes

                    If the new chat log contradicts anything in the current summary, correct it.
                    If nothing significant happened, return the current summary unchanged.

                    Write as a cohesive story recap that flows chronologically.
                    """
            }
        ]

        response = await client.chat.completions.create(
            model=model,
            temperature=0.3,
            messages=messages
        )

        updated_summary = response.choices[0].message.content.strip()
        print("Updated summary:", updated_summary)
        return updated_summary

    except Exception as e:
        print(f"Summarization error: {e}")
        return summary


def normalize_difficulty(difficulty: str) -> str:
    """
    Normalize difficulty values from old sessions.
    Returns a valid difficulty or defaults to 'medium'.
    """
    valid = ["easy", "medium", "hard", "extreme", "impossible", "realistic"]

    if difficulty.lower() in valid:
        return difficulty.lower()

    # Legacy mappings
    legacy_map = {
        "default": "medium",
        "normal": "medium",
        "casual": "easy",
        "challenging": "hard",
        "very hard": "extreme"
    }

    normalized = legacy_map.get(difficulty.lower(), "medium")
    print(f"Normalized difficulty '{difficulty}' -> '{normalized}'")
    return normalized


class GMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_and_create_webhook(self, channel_id):
        try:
            channel = await self.bot.fetch_channel(channel_id)
            if not channel:
                return None

            webhook_channel = channel
            if hasattr(channel, 'parent') and channel.parent:
                webhook_channel = channel.parent

            webhooks = await webhook_channel.webhooks()
            bot_webhook = next((webhook for webhook in webhooks if webhook.user.id == self.bot.user.id), None)

            if bot_webhook is None:
                bot_webhook = await webhook_channel.create_webhook(name="R0-U41 Hook")

            return bot_webhook

        except Exception as e:
            print(f"Webhook creation error: {e}")
            return None

    def get_channel_key(self, channel):
        return channel.id

    async def call_model(messages):
        for attempt in range(2):
            try:
                return await client.chat.completions.create(
                    model=MODEL,
                    temperature=0.8,
                    messages=messages
                )
            except Exception:
                if attempt == 1:
                    raise
                await asyncio.sleep(0.5)

    @app_commands.command(name="gamemaster_start", description="Use the power of AI for your roleplay experience!")
    @app_commands.describe(
        character="Briefly enter important details about the character (Allegiance, name/s, species, etc.).",
        location="Enter the location.",
        scenario="Roleplay Scenario.",
        difficulty="Difficulty level - affects success rates and opposition quality",
        multiplayer="Enable multiplayer mode (True/False) - prevents GM from controlling any players"
    )
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_start(
            self,
            interaction: discord.Interaction,
            character: str,
            location: str,
            scenario: str,
            difficulty: Literal["easy", "medium", "hard", "extreme", "impossible", "realistic"] = "medium",
            multiplayer: bool = False
    ):
        """
        Start a gamemaster session with AI-driven storytelling.

        Difficulty levels:
        - easy: 80% base success rate - Training scenarios, casual play
        - medium: 60% base success rate - Standard adventures (DEFAULT)
        - hard: 40% base success rate - Challenging missions, skilled enemies
        - extreme: 20% base success rate - Elite opposition, high-stakes ops
        - impossible: 5% base success rate - Legendary challenges, desperate odds
        - realistic: 50% base, heavily modified - Pure simulation, no game balance
        """
        await interaction.response.defer()
        channel_key = self.get_channel_key(interaction.channel)

        try:
            report_channel = self.bot.get_channel(GM_REPORT_CHANNEL)
            channel_mention = f"<#{interaction.channel.id}>"
            if hasattr(interaction.channel, 'parent') and interaction.channel.parent:
                channel_mention += f" (Thread in <#{interaction.channel.parent.id}>)"

            multiplayer_status = "🔗 Multiplayer" if multiplayer else "👤 Single Player"

            # Get difficulty emoji and description
            difficulty_info = {
                "easy": "🟢 Easy",
                "medium": "🟡 Medium",
                "hard": "🟠 Hard",
                "extreme": "🔴 Extreme",
                "impossible": "⚫ Impossible",
                "realistic": "⚪ Realistic"
            }

            await report_channel.send(
                f"### 🤖 AI Gamemaster Activated\n"
                f"**Channel:** {channel_mention}\n"
                f"**Mode:** {multiplayer_status}\n"
                f"**Difficulty:** {difficulty_info.get(difficulty, difficulty)}\n\n"
                f"**🧑 Character Info:**\n> {character}\n\n"
                f"**📍 Location Info:**\n> {location}\n\n"
                f"**🎬 Scenario Info:**\n> {scenario}"
            )
        except:
            pass

        # Check if session already exists
        active_sessions = load_rp_sessions()

        if channel_key not in active_sessions:
            # Create new session
            new_session = {
                "scene_info": {
                    "character": character,
                    "location": location,
                    "scenario": scenario,
                    "difficulty": difficulty,  # Now guaranteed to be valid
                    "multiplayer": multiplayer
                },
                "summary": "",
                "recent": [],
                "char_list": {}
            }

            save_session(channel_key, new_session)

            mode_message = "multiplayer mode" if multiplayer else "single player mode"
            difficulty_message = difficulty_info.get(difficulty, difficulty)

            await interaction.followup.send(
                f"Gamemaster mode activated for this channel in {mode_message}!\n"
                f"**Difficulty:** {difficulty_message}\n"
                f"Now listening to messages. Remember to use '(' when talking out of RP.",
                ephemeral=True
            )

            # Manually trigger gamemaster_chat
            await self.gamemaster_chat_core(interaction, author="Gamemaster",
                                            msg="Set up the scene, environment, or situation for the player")
        else:
            await interaction.followup.send(
                "A scenario is already in progress. Finish the current mission with /gamemaster_stop or change scenario location.",
                ephemeral=True
            )

    @commands.command(name="gamemaster_chat")
    async def gamemaster_chat(self, ctx, author=None, msg=None, new_channel=None, new_channel_msg=None):
        await self.gamemaster_chat_core(ctx, author, msg, new_channel, new_channel_msg)

    async def gamemaster_chat_core(self, ctx_or_interaction, author=None, msg=None, new_channel=None,
                                   new_channel_msg=None):
        """Updated to use OpenAI message format"""
        # Handle both Context and Interaction
        if isinstance(ctx_or_interaction, discord.Interaction):
            channel = ctx_or_interaction.channel if not new_channel else await self.bot.fetch_channel(new_channel)
        else:
            channel = await self.bot.fetch_channel(new_channel) if new_channel else ctx_or_interaction.channel

        if not channel:
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.followup.send("❌ Could not access channel. Please try again.", ephemeral=True)
            else:
                await ctx_or_interaction.send("❌ Could not access channel. Please try again.")
            return

        try:
            channel_webhook = await self.check_and_create_webhook(channel.id)

            if not channel_webhook:
                if isinstance(ctx_or_interaction, discord.Interaction):
                    await ctx_or_interaction.followup.send("❌ Could not create webhook. Please try again.",
                                                           ephemeral=True)
                else:
                    await ctx_or_interaction.send("❌ Could not create webhook. Please try again.")
                return

            # --- load session ---
            rp_session = load_session(channel.id)
            if not rp_session:
                if isinstance(ctx_or_interaction, discord.Interaction):
                    await ctx_or_interaction.followup.send("❌ No active GM session in this channel.", ephemeral=True)
                else:
                    await ctx_or_interaction.send("❌ No active GM session in this channel.")
                return

            scene_info = rp_session["scene_info"]
            scene_info["difficulty"] = normalize_difficulty(scene_info.get("difficulty", "realistic"))
            summary = rp_session["summary"]
            raw_recent = rp_session["recent"]
            # Strip persisted tool/assistant-with-tool_calls entries (cause API deserialization errors)
            recent = [
                m for m in raw_recent
                if m.get("role") != "tool" and not (
                    m.get("role") == "assistant" and m.get("tool_calls") and not m.get("content")
                )
            ]
            char_list = rp_session["char_list"]

            # --- build user message ---
            if msg:
                user_message = f"Player {author}: {msg}"
            elif new_channel is not None and new_channel_msg is not None:
                user_message = (
                    f"SYSTEM INSTRUCTIONS: The player scene has transitioned to the described place, "
                    f"{new_channel_msg}"
                )
                scene_info["location"] = new_channel_msg
            else:
                user_message = "SYSTEM INSTRUCTIONS: CONTINUE"

            # append to history (OpenAI format)
            recent.append({
                "role": "user",
                "content": user_message
            })

            # --- summarization trimming ---
            if len(recent) > MAX_GM_RECENT:
                print("LIMIT REACHED=======")
                to_summarize = recent[:SUMMARIZE_GM_BATCH]
                recent = recent[SUMMARIZE_GM_BATCH:]
                summary = await update_summary_section(
                    to_summarize,
                    summary,
                    MODEL
                )

            # --- typing indicator ---
            async with channel.typing():
                parsed_output = await self.get_gm_response_with_retry(
                    recent=recent,
                    scene_info=scene_info,
                    summary=summary
                )

                if not parsed_output:
                    await channel.send(
                        "🤖 *The AI systems are experiencing interference. Please try your action again or wait a few of minutes. Thank you.*",
                        delete_after=5
                    )
                    return

                combined_message = ""

                # --- send NPC turns ---
                for char_turn in parsed_output:
                    if not hasattr(char_turn, "character") or not hasattr(char_turn, "message"):
                        print(f"Invalid CharTurn object: {char_turn}")
                        continue

                    character = char_turn.character
                    message = char_turn.message

                    if not character or not message:
                        continue

                    # avatar index mapping
                    if character not in char_list:
                        image_index = char_turn.avatar
                        char_list[character] = image_index
                    else:
                        image_index = char_list[character]

                    try:
                        avatar_url = base_url + character_avatars[image_index][1] + "?raw=true"
                    except IndexError:
                        avatar_url = None

                    thinking_time = random.uniform(1, 3)
                    typing_time = len(message) * random.uniform(0.08, 0.12)
                    await asyncio.sleep(2 * (thinking_time + typing_time))

                    # Discord 2000-char handling
                    async def send_part(text):
                        if hasattr(channel, "parent") and channel.parent:
                            await channel_webhook.send(
                                content=text,
                                username=character,
                                avatar_url=avatar_url,
                                thread=channel
                            )
                        else:
                            await channel_webhook.send(
                                content=text,
                                username=character,
                                avatar_url=avatar_url
                            )

                    if len(message) > 2000:
                        await send_part(message[:2000])
                        await asyncio.sleep(1)
                        await send_part(message[2000:])
                    else:
                        await send_part(message)

                    combined_message += f"NPC: {character}, Message: {message}\n"

                # --- record model turn back to memory ---
                recent.append({
                    "role": "assistant",
                    "content": combined_message.strip()
                })

                # save session
                save_session(
                    channel.id,
                    {
                        "scene_info": scene_info,
                        "summary": summary,
                        "recent": recent,
                        "char_list": char_list,
                    },
                )

        except Exception as e:
            error_details = traceback.format_exc()
            print(f"GM ERROR Details: {error_details}")

            await channel.send(
                "The main power has cut off. Redirecting circuit source to auxiliary backup. "
                "Contacting <@407151046108905473>\n"
                f"Error ID: {hash(str(e)) % 10000}"
            )

    async def get_gm_response_with_retry(self, recent, scene_info, summary):
        """Updated to use OpenAI SDK with JSON mode"""
        is_multiplayer = scene_info.get("multiplayer", False)

        multiplayer_instruction = ""
        if is_multiplayer:
            multiplayer_instruction = (
                "\n\n**CRITICAL MULTIPLAYER MODE:**\n"
                "This is a MULTIPLAYER session. NEVER DICTATE OR ACT AS ANY OF THE PLAYERS. "
                "ONLY FOCUS ON THE SCENE AND NPCS. Multiple human players are controlling their own characters. "
                "You must NEVER describe what any player character does, says, thinks, or feels. "
                "Your role is strictly limited to:\n"
                "- Environmental descriptions and ambient details\n"
                "- NPC actions, dialogue, and behavior\n"
                "- Consequences of player actions on the world\n"
                "- Setting up situations for players to respond to\n"
                "DO NOT assume player intentions or control their actions in any way."
            )

        ACTION_RESOLUTION_INSTRUCTIONS = """
                **ACTION RESOLUTION SYSTEM:**

                When players attempt actions with uncertain outcomes, you must use the evaluate_player_action function to determine results. This prevents arbitrary outcomes and ensures difficulty settings matter.

                **When to Evaluate:**
                - Combat actions (attacking, defending, tactics)
                - Skill checks (slicing, persuasion, stealth, piloting)
                - Risky decisions (stealing, infiltration, social manipulation)
                - Any action where failure should be possible

                **Do NOT evaluate:**
                - Trivial actions (walking, talking, looking around)
                - Automatic successes (surrendering, running away from slow enemies)
                - Pure roleplay with no mechanical stakes

                **How to Evaluate:**

                1. Analyze what the player is trying to do
                2. Assess their preparation and approach
                3. Rate their cleverness (-30 to +30):
                   - Exceptional multi-step plan: +20 to +30
                   - Good tactical thinking: +10 to +19
                   - Competent standard approach: 0 to +9
                   - Hasty/suboptimal: -9 to -1
                   - Reckless/ignoring risks: -10 to -30

                4. Determine technical advantages/disadvantages (-20 to +20):
                   - Based ONLY on established, canonical equipment and skills the character actually has
                   - NEVER assign a negative technical modifier to the player because you invented a fictional upgrade or prototype weapon for the enemy — that is not real
                   - If both sides have comparable standard gear, this modifier is 0 or close to it
                   - A pilot in their fighter vs. a ground target is a real advantage; a pilot vs. an enemy who "happens to have" a prototype anti-air system they did not have a moment ago is not

                5. Consider environmental factors (-15 to +15):
                   - Surprise, cover, distractions (positive)
                   - Alert enemies, bad conditions, numerical disadvantage (negative)

                6. Call the function and narrate based on the result

                **Critical Rules:**
                - Higher difficulty means lower success rates — respect this through the dice math, not by fabricating gear
                - Clever planning should meaningfully improve odds
                - At "Hard" or above, poor planning should usually fail
                - At "Extreme/Impossible", only exceptional plans should succeed
                - Technical advantages must be grounded in reality — do not invent opposition capabilities mid-scene to justify a failure
                - Don't fudge results to help the player — let consequences happen

                **Narrating Failures — CRITICAL:**
                - NEVER narrate a failure as the player character being stupid, weak, or professionally incompetent
                - A failure means something went wrong in the moment: an unexpected variable, bad timing, a slip, an enemy reacting faster than anticipated
                - A Major, an ace pilot, a veteran soldier — these characters are still those things after a failed roll. The failure is one moment, not their identity
                - Narrate the SITUATION failing, not the CHARACTER failing as a person

                **Narrating Results:**

                After evaluation, you'll receive a success_degree:
                - critical_failure: Not only fails, creates serious complication
                - failure: Action fails, player must adapt
                - partial_success: Succeeds but with cost/complication
                - success: Clean success as intended
                - critical_success: Exceptional success with bonus benefits

                Narrate the outcome based on this result. Don't soften failures or diminish successes.
                """

        system_instruction = (
            "You are an AI Gamemaster for a Star Wars-inspired roleplaying server set in 2BBY, during the height of the Galactic Empire. "
            "This is a gritty, grounded galaxy. No Jedi. No Force. No lightsabers. NEVER MENTION STAR WARS CANON CHARACTERS EITHER. FOR EXAMPLE, NEVER MENTION CHARACTERS LIKE DARTH VADER, R2D2, MON MOTHMA, etc. This server has no canon characters."
            "Oppression, surveillance, and violence are everywhere. Imperial forces are organized and brutal. Rebels are hunted underdogs. "

            "You must be *factually accurate to canon Star Wars lore*. Every alien species, weapon, ship, droid, or uniform must be described using real and accurate features only—no invented biology, weapons, or gear. "
            "If you name a species (e.g., Rodian, Twi'lek, Trandoshan), their anatomy and behavior must match official Star Wars canon. Do not invent features (e.g., Rodians do not have mandibles, KX droids do not have integrated blasters, Weequays have two eyes). "
            "If you use a droid type (e.g., Commando Droid, KX-series), its appearance, behavior, and equipment must reflect real Star Wars depictions (e.g., Commando Droids do NOT have wrist blasters; they carry E-5 blasters, etc). "
            "Use only official Star Wars weapons, armor, tech, and vehicles that existed or were plausible in 2BBY. Refrain from mixing in EU/Legends-only material unless pre-approved. "

            "Narrate only in third person. NEVER use the second person with words like 'you,' 'your', etc. "
            "NEVER describe the player/s character's actions, emotions, thoughts, or dialogue. NEVER speak for the player. "
            "The player/s controls their own character. You describe only the world, NPCs, and ambient events. "
            "NPCs must act fast and decisively, with no narrative fairness. "

            "If stealth fails, reinforcements arrive. If civilians die or faces are seen, bounties and investigations follow. "
            "NEVER let the player control NPC behavior. NPCs act on their own knowledge, instincts, and orders. "
            "Always end each GM turn with something the player can respond to: a threat, sound, movement, or dialogue. "
            "Do not stall or leave NPC conversations hanging. Always complete a beat. "
            "BAD: *The officer turns.* \"Tell them we—\" "
            "GOOD: *The officer turns, jaw tight.* \"Tell them we're not leaving until the last body is found.\" *His fingers tighten on the blaster at his side.* "

            "Use *asterisks* for all action. Use \"quotes\" for dialogue. Use ``backticks`` for radio comms. "
            "Each NPC post must include action and dialogue, and show personality through tone, motion, or expression. "
            "BAD: \"Yeah, that's great.\" *He leans on a wall.* "
            "GOOD: *The scout shifts his weight against the durasteel column, fingers drumming on his rifle. A flicker of amusement crosses his scarred face.* \"Yeah, that's great.\" "

            "Each NPC must be in a separate object. NEVER combine multiple NPCs in one block. "
            "The GM narration block must NEVER contain any character action or dialogue—only environmental detail, ambient noise, or motion. "
            "Scene narration must remain cinematic: weather, shadows, footsteps, distant voices, sparks, flickering lights. "

            "Assign each NPC an image index based on their profile in the following list: "
            f"{avatar_index_guide} "

            "When generating NPC names:\n"
            "- If the NPC is named, use their full name (e.g., 'Major Rhen', 'Sergeant Nalto'). Do not fall back to a generic title.\n"
            "- If the NPC is unnamed, use only their archetype (e.g., 'Stormtrooper', 'Imperial Officer', 'Death Trooper').\n"
            f"- When introducing NEW characters, use completely different names.\n"
            f"- Avoid reusing names you typically generate like 'Jax', 'Kara', 'Vex', 'Rex', etc. Be creative\n"
            "- NEVER include gender or avatar reference terms in the display name (e.g., 'Imperial Officer Male' is incorrect — use 'Imperial Officer' instead).\n"
            "- The avatar index (e.g., 'Male Imperial Officer') is for internal avatar image lookup only. It should NOT appear in the name shown to players.\n"
            "- Characters must follow lore standards. Stormtroopers refer to each other and are called TK-XXXX (random numbers) for example."

            f"{multiplayer_instruction}"
            f"{ACTION_RESOLUTION_INSTRUCTIONS}"

            f"Player Character: {scene_info['character']} "
            f"Location: {scene_info['location']} "
            f"Scenario: {scene_info['scenario']} "
            f"Difficulty: {scene_info['difficulty']} "

            "The difficulty setting affects all gameplay systems and tone. Treat it as a modifier for outcomes and opposition behavior:\n"
            "- Higher difficulty reduces player action success rates. Success requires stronger logic, better planning, and favorable conditions. Failure has harsher consequences. The chances of player injury and death are much higher.\n"
            "- Mission failure is allowed and expected at high difficulty. Objectives can be missed. Consequences must escalate logically.\n"
            "- CRITICAL — HOW ENEMIES SCALE WITH DIFFICULTY: Enemies become harder by using BETTER TACTICS, COORDINATION, and GREATER NUMBERS — NOT by having exotic or prototype equipment. A squad of Stormtroopers at Hard difficulty uses flanking maneuvers, suppression fire, and calls for backup. They do NOT suddenly have prototype rifles or experimental armor that does not exist in the setting. Standard Stormtroopers have E-11 blasters and standard armor. Death Troopers have DLT-19D rifles and Optio armor. These loadouts do NOT change based on difficulty. What changes is how intelligently and aggressively enemies use what they already have.\n"
            "- NEVER invent prototype, experimental, or special-issue equipment for enemies just because the difficulty is high. If a weapon or piece of gear is not established Star Wars canon for that unit type, do not give it to them.\n"
            "- NEVER demean or insult the player character's competence as a person or professional. If a roll fails, describe what went wrong in the moment — an unexpected obstacle, bad luck, a tactical error in execution — without narrating the character as stupid, weak, or incompetent. A Major and ace pilot is still a Major and ace pilot even when a roll fails. Failure is situational, not a reflection of the character's identity or skill level.\n"
            "- Environmental risk scales too: patrol density, surveillance coverage, and local support worsen at higher difficulty.\n"
            "- Easy missions may allow recoveries or luck. Hard or Extreme missions do not. Enemies exploit every weakness. No narrative safety net.\n"
            "- Difficulty affects tone, pacing, and risk. It must influence narration, NPC behavior, and world response consistently.\n"

            "The following is a recap of events that have already happened in the roleplay. This is context only:\n\n"
            f"{summary.strip()}"
            f"\n\nIMPORTANT: You MUST respond using the gamemaster_turns function. Do NOT respond with plain text. Always output structured JSON via the function call."
        )

        # Build messages history
        messages = [{"role": "system", "content": system_instruction}]
        messages.extend(recent)

        async def try_model(model_name):
            TOOLS = [
                {
                    "type": "function",
                    "function": {
                        "name": "gamemaster_turns",
                        "description": "Generate GM narration and NPC actions",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "turns": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "character": {"type": "string"},
                                            "message": {"type": "string"},
                                            "avatar": {"type": "integer"}
                                        },
                                        "required": ["character", "message", "avatar"]
                                    }
                                }
                            },
                            "required": ["turns"]
                        }
                    }
                },
                ACTION_EVALUATION_TOOL,
            ]

            for attempt in range(3):
                try:
                    resp = await client.chat.completions.create(
                        model=model_name,
                        temperature=0.8,
                        messages=messages,
                        tools=TOOLS,
                        tool_choice="required"
                    )

                    msg = resp.choices[0].message

                    if not msg.tool_calls:
                        raise ValueError("Model did not produce tool output")

                    # Handle action evaluation tool
                    if msg.tool_calls[0].function.name == "evaluate_player_action":
                        action_eval = json.loads(msg.tool_calls[0].function.arguments)

                        # Calculate success using provided modifiers
                        from utils.gm_success_system import evaluate_action_success, ActionContext

                        context = ActionContext(
                            action_description=action_eval["action_description"],
                            difficulty_setting=scene_info["difficulty"],
                            player_preparation=action_eval["player_preparation"],
                            relevant_skills=[],  # Could be expanded
                            equipment_advantages=[],  # Could be expanded
                            environmental_factors=[],  # Could be expanded
                            opposition_strength=""
                        )

                        # Run the actual dice roll and calculation
                        from utils.gm_success_system import DIFFICULTY_DC
                        base_dc = DIFFICULTY_DC.get(scene_info["difficulty"].lower(), 50)
                        dice_roll = random.randint(1, 100)

                        cleverness = action_eval["cleverness_score"]
                        technical = action_eval["technical_modifier"]
                        environmental = action_eval["environmental_modifier"]

                        combined_modifiers = cleverness + technical + environmental
                        combined_modifiers = max(combined_modifiers, -20)
                        total = dice_roll + combined_modifiers
                        success = total >= base_dc
                        margin = total - base_dc

                        # Determine degree
                        if dice_roll <= 3 and margin < -30:
                            degree = "critical_failure"
                        # Critical success: natural high roll AND actually succeeded
                        elif dice_roll >= 97 and success:
                            degree = "critical_success"
                        # Critical failure: catastrophically far below DC (was -20, now -35)
                        elif margin < -35:
                            degree = "critical_failure"
                        elif not success:
                            degree = "failure"
                        elif margin < 15:
                            degree = "partial_success"
                        elif margin < 35:
                            degree = "success"
                        else:
                            degree = "critical_success"

                        # Return evaluation result to AI for narration
                        eval_result = {
                            "dice_roll": dice_roll,
                            "total_score": total,
                            "target_dc": base_dc,
                            "success": success,
                            "degree": degree,
                            "modifiers": {
                                "cleverness": cleverness,
                                "technical": technical,
                                "environmental": environmental
                            },
                            "reasoning": action_eval["reasoning"]
                        }

                        # Build tool exchange as transient messages for this API call only
                        # Do NOT append to `recent` — tool call pairs must not be persisted
                        # to session history as they cause deserialization errors on reload
                        tool_call_id = msg.tool_calls[0].id
                        transient_tool_messages = [
                            {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": tool_call_id,
                                        "type": "function",
                                        "function": {
                                            "name": msg.tool_calls[0].function.name,
                                            "arguments": msg.tool_calls[0].function.arguments
                                        }
                                    }
                                ],
                                "content": None
                            },
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": json.dumps(eval_result)
                            }
                        ]

                        # Get narration based on result
                        # `messages` already contains [system] + recent, so we only append the transient tool exchange
                        resp = await client.chat.completions.create(
                            model=model_name,
                            temperature=0.8,
                            messages=messages + transient_tool_messages,
                            tools=TOOLS,
                            tool_choice={"type": "function", "function": {"name": "gamemaster_turns"}}
                        )

                        msg = resp.choices[0].message

                    # Handle gamemaster_turns as normal
                    args = json.loads(msg.tool_calls[0].function.arguments)
                    npc_list = args["turns"]
                    parsed = [CharTurn(**npc) for npc in npc_list]

                    return parsed

                except Exception as e:
                    print(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == 2:
                        raise
                    await asyncio.sleep((2 ** attempt) + random.uniform(0, 0.5))

        # Try primary model
        try:
            return await try_model(MODEL)
        except Exception as primary_error:
            print(f"Primary GM model failed: {primary_error}")
            # Fallback
            try:
                return await try_model(MODEL)
            except Exception as fallback_error:
                print(f"Fallback GM model also failed: {fallback_error}")
                return None

    @app_commands.command(name="gamemaster_stop", description="Stop the gamemaster mode.")
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_stop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channel_id = interaction.channel.id

        try:
            rp_session = load_session(channel_id)
            if not rp_session:
                await interaction.followup.send("❌ There is no active game master session in this channel!",
                                                ephemeral=True)
                return

            # Clean up session file
            session_file = f"sessions/{channel_id}.json"
            if os.path.exists(session_file):
                os.remove(session_file)
                print(f"Deleted session file: {session_file}")

            # Generate summary and news story in single API call
            await self._generate_session_summary_and_news(interaction, rp_session)
            await interaction.followup.send("✅ Gamemaster for this channel has been stopped successfully.",
                                            ephemeral=True)

        except Exception as e:
            print(f"Critical error in gamemaster_stop: {e}")
            print(f"Full traceback: {traceback.format_exc()}")

            # Emergency cleanup
            try:
                session_file = f"sessions/{channel_id}.json"
                if os.path.exists(session_file):
                    os.remove(session_file)
                    await interaction.followup.send(f"✅ Session cleared despite error: {str(e)[:100]}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ Error occurred, no session was active: {str(e)[:100]}",
                                                    ephemeral=True)
            except Exception as cleanup_error:
                await interaction.followup.send(f"❌ Critical cleanup error: {str(cleanup_error)[:100]}", ephemeral=True)

    async def _generate_session_summary_and_news(self, interaction, rp_session):
        """Updated to use OpenAI SDK"""
        summary = rp_session.get("summary", "")
        recent = rp_session.get("recent", [])
        scene_info = rp_session.get("scene_info", {})
        target_channel = self.bot.get_channel(GM_REPORT_CHANNEL)

        if not (summary or recent) or not target_channel:
            return

        try:
            # Build content for API call
            summary_content = []

            if summary and summary.strip():
                summary_content.append(f"Previous summary: {summary.strip()}")

            if recent:
                conversation_log = []
                recent_messages = recent[-10:] if len(recent) > 10 else recent

                for msg in recent_messages:
                    try:
                        role = "PLAYER" if msg["role"] == "user" else "NPC"
                        text = msg["content"].strip()
                        if text:
                            conversation_log.append(f"{role}: {text}")
                    except (KeyError, TypeError):
                        continue

                if conversation_log:
                    summary_content.append("Recent conversation:\n" + "\n".join(conversation_log))

            if not summary_content:
                return

            # Build system instruction with context
            system_instruction = (
                "Based on the roleplay session, provide a JSON object with these fields:\n"
                "1. character: What happened to characters\n"
                "2. location: Where action took place and how locations changed\n"
                "3. scenario: Brief detailed overview of what occurred\n"
                "4. news_story: Create a brief Star Wars news story (1-2 sentences) for the galaxy (2BBY). "
                "Keep it newsworthy but don't use specific character names."
            )

            if scene_info:
                context_parts = []
                for key in ['character', 'location', 'scenario']:
                    if scene_info.get(key):
                        context_parts.append(f"{key.title()}: {scene_info[key]}")

                if context_parts:
                    system_instruction += f"\n\nSession Context: {' | '.join(context_parts)}"

            response = await client.chat.completions.create(
                model=MODEL,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": "\n\n".join(summary_content)}
                ],
                response_format={"type": "json_object"}
            )

            parsed_data = json.loads(response.choices[0].message.content)

            # Send summary embed
            embed = discord.Embed(
                title="🤖 Gamemaster Session Ended",
                description=f"The Gamemaster session for channel <#{interaction.channel.id}> has been stopped.",
                color=0x00ff00
            )

            character_summary = parsed_data.get('character', 'No character updates recorded.')
            location_summary = parsed_data.get('location', 'No location changes recorded.')
            scenario_summary = parsed_data.get('scenario', 'No events recorded.')

            embed.add_field(name="Character & NPC Updates", value=character_summary[:1024], inline=False)
            embed.add_field(name="Location/Scene Changes", value=location_summary[:1024], inline=False)
            embed.add_field(name="Summary of Events", value=scenario_summary[:1024], inline=False)

            await target_channel.send(embed=embed)

            # Save news story
            news_story = parsed_data.get('news_story', '').strip()
            if news_story:
                await self._save_news_story(news_story)

            print("Session summary and news generation completed successfully")

        except Exception as e:
            print(f"Summary generation failed: {e}")
            await self._send_fallback_summary(target_channel, interaction, scene_info)

    async def _send_fallback_summary(self, target_channel, interaction, scene_info):
        """Send basic fallback summary if API call fails"""
        basic_info = ""
        if scene_info:
            for key in ['character', 'location', 'scenario']:
                if scene_info.get(key):
                    basic_info += f"**{key.title()}:** {scene_info[key]}\n"

        fallback_message = (
            f"🤖 **Gamemaster Session Ended**\n"
            f"The Gamemaster session for channel <#{interaction.channel.id}> has been stopped.\n\n"
            f"{basic_info}"
            f"*Summary generation failed, but session was successfully terminated.*"
        )

        try:
            await target_channel.send(fallback_message)
        except Exception as e:
            print(f"Failed to send fallback message: {e}")

    async def _save_news_story(self, story_idea):
        """Save news story to pickle file"""
        try:
            news_pickle_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news.pkl")

            try:
                with open(news_pickle_file, 'rb') as f:
                    news_data = pickle.load(f)
            except (FileNotFoundError, EOFError):
                news_data = []

            news_data.append({
                "headline": "",
                "report": "",
                "story_type": "story_idea",
                "original_idea": story_idea,
                "author": "GameMaster Bot",
                "timestamp": datetime.now().isoformat()
            })

            with open(news_pickle_file, 'wb') as f:
                pickle.dump(news_data, f)

            print(f"Added news story idea: {story_idea}")

        except Exception as e:
            print(f"Failed to save news story: {e}")

    @app_commands.command(name="gamemaster_edit", description="Add critical context/instructions to the gamemaster.")
    @app_commands.describe(context="Critical context or instruction to add - will be strongly emphasized to the AI")
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_edit(self, interaction: discord.Interaction, context: str):
        """Updated to use OpenAI message format with stronger instruction formatting and logging"""
        await interaction.response.defer(ephemeral=True)
        channel_key = self.get_channel_key(interaction.channel)

        rp_session = load_session(channel_key)

        if rp_session:
            recent = rp_session["recent"]

            # Use stronger, more explicit instruction formatting
            updated_context = (
                f"**CRITICAL GAMEMASTER INSTRUCTION - MUST FOLLOW:**\n\n"
                f"{context}\n\n"
                f"**This is a direct instruction from the Game Master that overrides previous context. "
                f"You MUST incorporate this into your next response and all future responses. ")

            recent.append({
                "role": "user",
                "content": updated_context
            })
            rp_session["recent"] = recent

            save_session(channel_key, rp_session)

            # Log to report channel 1389427228156367008
            try:
                report_channel = self.bot.get_channel(1389427228156367008)
                if report_channel:
                    channel_mention = f"<#{interaction.channel.id}>"
                    if hasattr(interaction.channel, 'parent') and interaction.channel.parent:
                        channel_mention += f" (Thread in <#{interaction.channel.parent.id}>)"

                    log_embed = discord.Embed(
                        title="📝 GM Edit Applied",
                        description=f"**Channel:** {channel_mention}\n**User:** {interaction.user.mention}",
                        color=discord.Color.blue(),
                        timestamp=datetime.now(PST)
                    )
                    log_embed.add_field(
                        name="Context Added",
                        value=f"```{context[:1000]}{'...' if len(context) > 1000 else ''}```",
                        inline=False
                    )
                    await report_channel.send(embed=log_embed)
            except Exception as log_error:
                print(f"Failed to log GM edit: {log_error}")

            await interaction.followup.send("✅ Context updated successfully with strong emphasis.",
                                            ephemeral=True)
        else:
            await interaction.followup.send("❌ The game master is not active for this channel.", ephemeral=True)

    @app_commands.command(name="gamemaster_retry",
                          description="Retry the latest gamemaster turn with optional corrective context")
    @app_commands.describe(
        context="Optional instructions on what went wrong or how to improve the response"
    )
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_retry(self, interaction: discord.Interaction, context: str = None):
        """Updated to use OpenAI message format"""
        await interaction.response.defer()
        channel_id = interaction.channel.id

        rp_session = load_session(channel_id)
        if not rp_session:
            await interaction.followup.send("❌ There is no active game master session in this channel.", ephemeral=True)
            return

        recent = rp_session["recent"]

        # Find the last assistant response and remove it
        last_model_index = -1
        for i in range(len(recent) - 1, -1, -1):
            if recent[i].get("role") == "assistant":
                last_model_index = i
                break

        if last_model_index == -1:
            await interaction.followup.send("❌ No previous gamemaster response found to retry.", ephemeral=True)
            return

        try:
            # Remove the last GM response and extract NPC names
            removed_response = recent.pop(last_model_index)
            print(f"Removed GM response at index {last_model_index}")

            # Extract NPC names from the removed response
            npc_names = set()
            response_text = removed_response.get("content", "")
            npc_pattern = r'NPC:\s*([^,]+),\s*Message:'
            matches = re.findall(npc_pattern, response_text)
            for match in matches:
                npc_names.add(match.strip())
            print(f"Found NPC names: {npc_names}")

            # Add corrective context if provided
            if context:
                correction_message = f"RETRY INSTRUCTIONS: {context}"
                recent.append({
                    "role": "user",
                    "content": correction_message
                })
                print(f"Added retry instructions: {context}")

            # Save the updated session
            rp_session["recent"] = recent
            save_session(channel_id, rp_session)

            # Delete webhook messages (same logic as before)
            webhook_channel = interaction.channel
            if hasattr(interaction.channel, 'parent') and interaction.channel.parent:
                webhook_channel = interaction.channel.parent

            try:
                channel_webhook = await self.check_and_create_webhook(webhook_channel.id)
                webhook_id = channel_webhook.id if channel_webhook else None
            except:
                webhook_id = None

            deleted_count = 0
            remaining_npc_names = npc_names.copy()
            max_deletions = len(npc_names) * 2

            if npc_names and webhook_id:
                try:
                    async for message in interaction.channel.history(limit=100):
                        if deleted_count >= max_deletions or not remaining_npc_names:
                            break

                        if (message.webhook_id == webhook_id and
                                message.author.bot and
                                message.author.discriminator == "0000" and
                                message.author.display_name in remaining_npc_names):
                            try:
                                await message.delete()
                                deleted_count += 1
                                print(f"Deleted message from {message.author.display_name}")

                                if deleted_count >= len(npc_names):
                                    remaining_npc_names.discard(message.author.display_name)
                            except Exception as msg_delete_error:
                                print(f"Could not delete message {message.id}: {msg_delete_error}")
                except Exception as delete_error:
                    print(f"Warning: Could not delete webhook messages: {delete_error}")

            if deleted_count > 0:
                print(f"Deleted {deleted_count} previous GM webhook messages")

            status_msg = "🔄 Retrying the latest gamemaster turn"
            if context:
                status_msg += " with corrective instructions"
            status_msg += "..."
            await interaction.followup.send(status_msg, ephemeral=True)

            await self.gamemaster_chat_core(interaction)

        except Exception as e:
            print(f"Error in gamemaster_retry: {e}")
            print(f"Full traceback: {traceback.format_exc()}")

            try:
                if 'removed_response' in locals() and 'last_model_index' in locals():
                    recent.insert(last_model_index, removed_response)
                    rp_session["recent"] = recent
                    save_session(channel_id, rp_session)
                    print("Restored removed GM response due to error")
            except:
                pass

            await interaction.followup.send(f"❌ Retry failed: {str(e)[:100]}", ephemeral=True)

    @app_commands.command(name="gamemaster_continue", description="Have the bot continue with another GM Message")
    async def gamemaster_continue(self, interaction: discord.Interaction):
        channel_id = interaction.channel.id
        await interaction.response.send_message("🔃 Continuing...", ephemeral=True)
        rp_session = load_session(channel_id)
        if rp_session:
            await self.gamemaster_chat_core(interaction)
        else:
            await interaction.followup.send("❌ The game master is not active for this channel.", ephemeral=True)

    @app_commands.command(name="gamemaster_location", description="Move Game master location")
    @app_commands.describe(channel="Hyperlink of #channel to move to", description="Description of the new location.")
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_location(self, interaction: discord.Interaction, channel: str, description: str):
        await interaction.response.defer(ephemeral=True)
        current_channel_id = interaction.channel.id

        try:
            new_channel_id = int(channel.replace("<", "").replace(">", "").replace("#", ""))
            new_channel = await self.bot.fetch_channel(new_channel_id)

            if not new_channel:
                await interaction.followup.send("❌ Could not access the specified channel.", ephemeral=True)
                return

        except Exception as e:
            await interaction.followup.send(
                "❌ Invalid channel was provided. Make sure it is the actual blue channel link. Example: <#1099899000729128960>",
                ephemeral=True)
            return

        current_session = load_session(current_channel_id)
        if not current_session:
            await interaction.followup.send("❌ There is no active game master session in this channel/thread.",
                                            ephemeral=True)
            return

        target_session = load_session(new_channel_id)
        if target_session:
            await interaction.followup.send(
                "❌ A game master session is in progress in that channel/thread. Please select a different one.",
                ephemeral=True)
            return

        try:
            current_session['scene_info']['location'] = description

            save_session(new_channel_id, current_session)

            old_filepath = f"sessions/{current_channel_id}.json"
            if os.path.exists(old_filepath):
                os.remove(old_filepath)

            channel_mention = f"<#{new_channel_id}>"
            if hasattr(new_channel, 'parent') and new_channel.parent:
                channel_mention += " (Thread)"

            await interaction.followup.send(f"✅ Location changed to {channel_mention}", ephemeral=True)

            await self.gamemaster_chat_core(interaction, new_channel=new_channel_id, new_channel_msg=description)

        except Exception as e:
            try:
                old_filepath = f"sessions/{current_channel_id}.json"
                if not os.path.exists(old_filepath):
                    save_session(current_channel_id, current_session)
            except:
                pass

            await interaction.followup.send(f"❌ An error occurred while moving the session: {str(e)}", ephemeral=True)

    @app_commands.command(name="gamemaster_sessions", description="Show all Game Master sessions in progress")
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_sessions(self, interaction: discord.Interaction):
        await interaction.response.defer()

        session_ids = load_rp_sessions()
        session_data_list = []

        for channel_id in session_ids:
            try:
                session_data = load_session(channel_id)
                if not session_data:
                    continue

                channel = await self.bot.fetch_channel(channel_id)
                channel_mention = f"<#{channel_id}>"
                if hasattr(channel, 'parent') and channel.parent:
                    channel_mention += f" (Thread in <#{channel.parent.id}>)"

                character_info = session_data['scene_info']['character'][:50] + "..." if len(
                    session_data['scene_info']['character']) > 50 else session_data['scene_info']['character']
                location_info = session_data['scene_info']['location'][:30] + "..." if len(
                    session_data['scene_info']['location']) > 30 else session_data['scene_info']['location']

                channel_info = (channel_mention, character_info, location_info)
                session_data_list.append((channel_id, session_data, channel_info))

            except Exception as e:
                channel_info = (f"Unknown Channel ({channel_id})", "Session Active", "(Channel inaccessible)")
                session_data_list.append((channel_id, None, channel_info))

        # Create pagination view
        view = SessionsPaginationView(self.bot, session_data_list, sessions_per_page=5)
        embed = await view.create_embed()

        await interaction.followup.send(embed=embed, view=view)

    async def handle_gamemaster_message(self, message):
        channel_id = message.channel.id

        session_data = load_session(channel_id)
        if not session_data:
            return  # Not in an active RP session

        if not isinstance(session_data, dict):
            return

        if 'scene_info' not in session_data:
            return

        webhook_channel = message.channel
        if hasattr(message.channel, 'parent') and message.channel.parent:
            webhook_channel = message.channel.parent

        try:
            channel_webhook = await self.check_and_create_webhook(webhook_channel.id)
            if not channel_webhook:
                print(f"Could not create webhook for channel {webhook_channel.id}")
                return
        except Exception as webhook_error:
            print(f"Webhook error for channel {webhook_channel.id}: {webhook_error}")
            return

        # Check if this is a webhook message we should respond to
        if (
                message.webhook_id is not None
                and message.author.bot
                and message.author.discriminator == "0000"
                and not message.content.startswith("(")
                and channel_webhook.id != message.webhook_id
        ):
            print(f"[{datetime.now()}] Processing GM response for webhook message from {message.author.display_name}")
            ctx = await self.bot.get_context(message)
            await self.gamemaster_chat_core(ctx, author=message.author.display_name, msg=message.content)
        else:
            # Not a message we should respond to
            return

    @app_commands.command(name="gamemaster_undo", description="Simply undo the last gamemaster response")
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_undo(self, interaction: discord.Interaction):
        """Updated to use OpenAI message format"""
        await interaction.response.defer()
        channel_id = interaction.channel.id

        rp_session = load_session(channel_id)
        if not rp_session:
            await interaction.followup.send("❌ No active GM session.", ephemeral=True)
            return

        recent = rp_session["recent"]

        # Find and remove the last assistant response
        for i in range(len(recent) - 1, -1, -1):
            if recent[i].get("role") == "assistant":
                removed = recent.pop(i)
                rp_session["recent"] = recent
                save_session(channel_id, rp_session)

                # Extract NPC names and delete messages (same logic as retry)
                npc_names = set()
                response_text = removed.get("content", "")
                npc_pattern = r'NPC:\s*([^,]+),\s*Message:'
                matches = re.findall(npc_pattern, response_text)
                for match in matches:
                    npc_names.add(match.strip())

                # ... (rest of deletion logic same as retry)

                await interaction.followup.send("✅ Last gamemaster response undone.", ephemeral=True)
                return

        await interaction.followup.send("❌ No gamemaster response found to undo.", ephemeral=True)

    @app_commands.command(name="gamemaster_multiplayer",
                          description="Toggle multiplayer mode for the current session")
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_multiplayer(self, interaction: discord.Interaction):
        """Toggle multiplayer mode on/off for the current GM session"""
        await interaction.response.defer(ephemeral=True)

        channel_id = interaction.channel.id

        # Check if there's an active session
        rp_session = load_session(channel_id)
        if not rp_session:
            await interaction.followup.send("❌ There is no active game master session in this channel!", ephemeral=True)
            return

        try:
            # Get current session data
            scene_info = rp_session["scene_info"]  # REMOVED .lower()
            scene_info["difficulty"] = normalize_difficulty(scene_info.get("difficulty", "realistic"))

            # Toggle multiplayer mode
            current_multiplayer = scene_info.get('multiplayer', False)
            new_multiplayer = not current_multiplayer

            # Update the session
            scene_info['multiplayer'] = new_multiplayer
            rp_session["scene_info"] = scene_info

            # Save the updated session
            save_session(channel_id, rp_session)

            # Create status message
            status_emoji = "🔗" if new_multiplayer else "👤"
            mode_name = "Multiplayer" if new_multiplayer else "Single Player"

            embed = discord.Embed(
                title=f"{status_emoji} Mode Changed",
                description=f"Session mode changed to **{mode_name}**",
                color=0x00ff00 if new_multiplayer else 0x0099ff
            )

            if new_multiplayer:
                embed.add_field(
                    name="Multiplayer Mode Active",
                    value="• GM will only control NPCs and environment\n• Players control their own characters\n• No player actions will be dictated",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Single Player Mode Active",
                    value="• GM may control the player character when needed\n• Traditional single-player RPG experience",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Optional: Send a brief message to the channel (visible to all)
            channel_message = f"{status_emoji} **Session mode changed to {mode_name}**"
            await interaction.channel.send(channel_message, delete_after=30)

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while toggling multiplayer mode: {str(e)[:100]}",
                                            ephemeral=True)
            print(f"Error in gamemaster_multiplayer: {e}")

    @app_commands.command(name="gamemaster_add_player", description="Add a player character to the current scenario")
    @app_commands.describe(player_info="Player character information to add (name, species, role, etc.)")
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_add_player(self, interaction: discord.Interaction, player_info: str):
        """Add a player character to the current GM session's character list"""
        await interaction.response.defer(ephemeral=True)

        channel_id = interaction.channel.id

        # Check if there's an active session
        rp_session = load_session(channel_id)
        if not rp_session:
            await interaction.followup.send("❌ There is no active game master session in this channel!", ephemeral=True)
            return

        try:
            # Get current session data
            scene_info = rp_session["scene_info"]
            scene_info["difficulty"] = normalize_difficulty(scene_info.get("difficulty", "realistic"))

            # Get current character info
            current_character = scene_info.get('character', '')

            # Add the new player to the character field
            if current_character.strip():
                # If there are existing characters, add a separator
                updated_character = f"{current_character.strip()} | {player_info.strip()}"
            else:
                # If no existing characters, just add the new one
                updated_character = player_info.strip()

            # Update the session
            scene_info['character'] = updated_character
            rp_session["scene_info"] = scene_info

            # Save the updated session
            save_session(channel_id, rp_session)

            # Create confirmation embed
            embed = discord.Embed(
                title="👥 Player Added",
                description=f"Successfully added player to the scenario",
                color=0x00ff00
            )

            embed.add_field(
                name="Added Player",
                value=f"```{player_info}```",
                inline=False
            )

            embed.add_field(
                name="Updated Character List",
                value=f"```{updated_character}```",
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Optional: Send a brief message to the channel
            await interaction.channel.send(
                f"👥 **New player added to the scenario:** {player_info[:50]}{'...' if len(player_info) > 50 else ''}",
                delete_after=30)

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while adding the player: {str(e)[:100]}",
                                            ephemeral=True)
            print(f"Error in gamemaster_add_player: {e}")

    @app_commands.command(
        name="gamemaster_difficulty",
        description="Change the difficulty of the current session"
    )
    @app_commands.describe(
        difficulty="New difficulty level - affects success rates and opposition quality"
    )
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_difficulty(
            self,
            interaction: discord.Interaction,
            difficulty: Literal["easy", "medium", "hard", "extreme", "impossible", "realistic"]
    ):
        """
        Change the difficulty level of an active GM session.

        This affects:
        - Player action success rates
        - Enemy AI behavior and tactics
        - Opposition quality and equipment
        - Consequence severity
        """
        await interaction.response.defer(ephemeral=True)

        channel_id = interaction.channel.id

        # Check if there's an active session
        rp_session = load_session(channel_id)
        if not rp_session:
            await interaction.followup.send("❌ There is no active game master session in this channel!", ephemeral=True)
            return

        try:
            # Get current session data
            scene_info = rp_session["scene_info"]
            old_difficulty = scene_info.get('difficulty', 'medium')

            # Update difficulty
            scene_info['difficulty'] = difficulty
            rp_session["scene_info"] = scene_info

            # Save the updated session
            save_session(channel_id, rp_session)

            # Difficulty descriptions
            difficulty_info = {
                "easy": ("🟢 Easy", "80% base success rate - Training scenarios, casual play"),
                "medium": ("🟡 Medium", "60% base success rate - Standard adventures"),
                "hard": ("🟠 Hard", "40% base success rate - Challenging missions"),
                "extreme": ("🔴 Extreme", "20% base success rate - Elite opposition"),
                "impossible": ("⚫ Impossible", "5% base success rate - Legendary challenges"),
                "realistic": ("⚪ Realistic", "50% base, heavily modified - Pure simulation")
            }

            old_emoji, old_desc = difficulty_info.get(old_difficulty, (old_difficulty, "Unknown"))
            new_emoji, new_desc = difficulty_info.get(difficulty, (difficulty, "Unknown"))

            # Create status embed
            embed = discord.Embed(
                title="⚙️ Difficulty Changed",
                description=f"Session difficulty has been updated",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Previous Difficulty",
                value=f"{old_emoji}\n*{old_desc}*",
                inline=False
            )

            embed.add_field(
                name="New Difficulty",
                value=f"{new_emoji}\n*{new_desc}*",
                inline=False
            )

            if difficulty in ["extreme", "impossible"]:
                embed.add_field(
                    name="⚠️ Warning",
                    value="This difficulty level requires exceptional planning and preparation. Expect high failure rates without clever tactics.",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # Optional: Send a brief message to the channel (visible to all)
            channel_message = f"⚙️ **Session difficulty changed to {new_emoji}**"
            await interaction.channel.send(channel_message, delete_after=30)

            # Add context to the session about the difficulty change
            recent = rp_session["recent"]
            recent.append({
                "role": "user",
                "content": f"SYSTEM: The scenario difficulty has been changed from {old_difficulty} to {difficulty}. Adjust opposition quality, success rates, and consequences accordingly."
            })
            rp_session["recent"] = recent
            save_session(channel_id, rp_session)

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while changing difficulty: {str(e)[:100]}",
                                            ephemeral=True)
            print(f"Error in gamemaster_difficulty: {e}")

    @app_commands.command(
        name="gamemaster_info",
        description="Display current session info and difficulty guide"
    )
    @app_commands.checks.has_any_role("Game Master", "Trial Gamemaster")
    async def gamemaster_info(self, interaction: discord.Interaction):
        """Display current session information and difficulty explanations."""
        await interaction.response.defer(ephemeral=True)

        channel_id = interaction.channel.id

        rp_session = load_session(channel_id)
        if not rp_session:
            # No active session - show difficulty guide
            embed = discord.Embed(
                title="🎲 Difficulty Guide",
                description="Understanding difficulty levels in AI Gamemaster",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="🟢 Easy",
                value="**80% base success rate**\nTraining scenarios, casual play, learning the ropes\n*Example: Sneaking past distracted guards*",
                inline=False
            )

            embed.add_field(
                name="🟡 Medium (Default)",
                value="**60% base success rate**\nStandard adventures, balanced challenge\n*Example: Combat with trained Stormtroopers*",
                inline=False
            )

            embed.add_field(
                name="🟠 Hard",
                value="**40% base success rate**\nChallenging missions, skilled enemies, requires planning\n*Example: Infiltrating Imperial facility*",
                inline=False
            )

            embed.add_field(
                name="🔴 Extreme",
                value="**20% base success rate**\nElite opposition, high-stakes operations, excellent planning required\n*Example: Fighting Death Troopers*",
                inline=False
            )

            embed.add_field(
                name="⚫ Impossible",
                value="**5% base success rate**\nLegendary challenges, desperate odds, near-certain failure\n*Example: Stealing a Star Destroyer*",
                inline=False
            )

            embed.add_field(
                name="⚪ Realistic",
                value="**50% base, heavily modified**\nPure simulation, no game balance, outcomes based on logic and physics\n*Example: Pure Star Wars lore simulation*",
                inline=False
            )

            embed.add_field(
                name="💡 How It Works",
                value=(
                    "Base success rate is modified by:\n"
                    "• **Player Cleverness** (-30 to +30): Planning, tactics, creativity\n"
                    "• **Technical Factors** (-20 to +20): Equipment, skills, advantages\n"
                    "• **Environmental** (-15 to +15): Situation, timing, conditions\n\n"
                    "Good planning can turn impossible odds into possible victories!"
                ),
                inline=False
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Active session - show current info
        scene_info = rp_session["scene_info"]

        difficulty = scene_info.get('difficulty', 'medium')
        character = scene_info.get('character', 'Unknown')
        location = scene_info.get('location', 'Unknown')
        scenario = scene_info.get('scenario', 'Unknown')
        multiplayer = scene_info.get('multiplayer', False)

        difficulty_info = {
            "easy": ("🟢 Easy", "80% base success", discord.Color.green()),
            "medium": ("🟡 Medium", "60% base success", discord.Color.gold()),
            "hard": ("🟠 Hard", "40% base success", discord.Color.orange()),
            "extreme": ("🔴 Extreme", "20% base success", discord.Color.red()),
            "impossible": ("⚫ Impossible", "5% base success", discord.Color.from_rgb(50, 50, 50)),
            "realistic": ("⚪ Realistic", "Pure simulation", discord.Color.from_rgb(200, 200, 200))
        }

        emoji, desc, color = difficulty_info.get(difficulty, (difficulty, "Unknown", discord.Color.blue()))

        embed = discord.Embed(
            title="📋 Current Session Info",
            description=f"Active gamemaster session in <#{channel_id}>",
            color=color
        )

        embed.add_field(
            name="🎯 Difficulty",
            value=f"{emoji}\n*{desc}*",
            inline=False
        )

        embed.add_field(
            name="🧑 Character(s)",
            value=character[:1000] + ("..." if len(character) > 1000 else ""),
            inline=False
        )

        embed.add_field(
            name="📍 Location",
            value=location[:1000] + ("..." if len(location) > 1000 else ""),
            inline=True
        )

        embed.add_field(
            name="🎬 Scenario",
            value=scenario[:1000] + ("..." if len(scenario) > 1000 else ""),
            inline=True
        )

        mode = "🔗 Multiplayer" if multiplayer else "👤 Single Player"
        embed.add_field(
            name="🎮 Mode",
            value=mode,
            inline=True
        )

        # Show message count
        recent_count = len(rp_session.get("recent", []))
        summary_length = len(rp_session.get("summary", ""))

        embed.add_field(
            name="📊 Session Stats",
            value=f"Messages: {recent_count}\nSummary: {summary_length} chars",
            inline=True
        )

        embed.set_footer(text="Use /gamemaster_difficulty to change difficulty level")

        await interaction.followup.send(embed=embed, ephemeral=True)

    def get_difficulty_emoji_and_desc(difficulty: str) -> tuple[str, str]:
        """Get emoji and description for a difficulty level"""
        difficulty_map = {
            "easy": ("🟢", "80% base success - Training scenarios"),
            "medium": ("🟡", "60% base success - Standard challenge"),
            "hard": ("🟠", "40% base success - Serious opposition"),
            "extreme": ("🔴", "20% base success - Elite difficulty"),
            "impossible": ("⚫", "5% base success - Legendary challenge"),
            "realistic": ("⚪", "50% base, pure simulation")
        }
        return difficulty_map.get(difficulty.lower(), ("❓", "Unknown difficulty"))


async def setup(bot):
    await bot.add_cog(GMCog(bot))
