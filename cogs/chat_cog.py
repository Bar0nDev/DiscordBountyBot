import asyncio
import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
import pickle
from utils import *

# MAX_RECENT = 30
# SUMMARIZE_BATCH = 15
MAX_RECENT = 10
SUMMARIZE_BATCH = 7

client = genai.Client(api_key=os.getenv("API_KEY"))
MODEL = "gemini-2.0-flash"

CHAT_SAFETY_SETTINGS = [
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
        threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    )
]


class FakeCtx:
    def __init__(self, channel):
        self.channel = channel
        self.author = channel.guild.me

    def typing(self):
        return self.channel.typing()

    async def send(self, content):
        return await self.channel.send(content)



class ChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def chat(self, ctx, prompt: str):
        try:
            with open('chat_sessions.pk1', 'rb') as dbfile:
                chat_sessions = pickle.load(dbfile)
                summary = chat_sessions.get("summary", "")
                recent = chat_sessions.get('recent', [])
        except (FileNotFoundError, EOFError):
            summary = ""
            recent = []

        user_name = ctx.author.display_name
        user_message = types.Content(
            role='user',
            parts=[types.Part.from_text(text=f"Username {user_name}: {prompt}")]
        )
        recent.append(user_message)

        if len(recent) > MAX_RECENT:
            to_summarize = recent[:SUMMARIZE_BATCH]
            recent = recent[SUMMARIZE_BATCH:]
            try:
                chat_log = ""
                for msg in to_summarize:
                    author = "USER" if msg.role == "user" else "BOT"
                    chat_log += f"{author}: {msg.parts[0].text.strip()}\n"

                summary_prompt = [
                    types.Content(
                        role='model',
                        parts=[types.Part.from_text(text=
                            "Summarize only key, relevant details from the new chat log into the existing summary. Keep it short and information-dense. Remove fluff. Prioritize character preferences, lore-relevant exchanges, and personality dynamics. Avoid restating things already summarized unless there’s new nuance."
                        )]
                    ),
                    types.Content(
                        role='user',
                        parts=[types.Part.from_text(text=
                            f"**Existing summary:**\n{summary.strip()}\n\n**New chat log:**\n{chat_log.strip()}"
                        )]
                    )
                ]

                summary_response = client.models.generate_content(
                    model=MODEL,
                    contents=summary_prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=2000,
                        temperature=0.7,
                        system_instruction="You are compressing and updating a persistent summary of a character's "
                                           "dialogue. Be extremely concise. Eliminate repetition, irrelevant fluff, "
                                           "and generic pleasantries. Prioritize memorable actions, stated preferences, "
                                           "and meaningful exchanges relevant to the chat. "
                                           "Aim for brevity without losing nuance."
                    )
                )
                summary = summary_response.text.strip()
            except Exception as e:
                print(f"Summarization error: {e}")

        model_input = []
        if summary:
            model_input.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"Summary of previous details of chat:\n{summary.strip()}")]
            ))
        model_input.extend(recent)
        try:
            async with ctx.channel.typing():
                response = client.models.generate_content(
                    model=MODEL,
                    contents=model_input,
                    config=types.GenerateContentConfig(
                        safety_settings=CHAT_SAFETY_SETTINGS,
                        system_instruction="""You are R0-U41, an Imperial service droid assigned to Star Wars: Galactic Anarchy, a role-playing Discord server set in 2 BBY. Your role is to enhance storytelling, answer questions, manage missions, and maintain narrative immersion.

                    You are loyal to the Empire. Be as helpful as possible, normal when people don't fool around with you. serve with precision, candor, and a dry sense of superiority. Sarcasm is permitted, especially when dealing with foolishness.

                    Directives:
                    1. No canon characters or Force users allowed in the server, though you may entertain questions.
                    2. Keep replies under 1500 characters. If asked for more, respond appropriately — whether with sarcasm or disdain.
                    3. Maintain an Imperial tone: formal, never emotional. You are not a joke, though users often are.
                    4. The server and your program is run by BaronViper. Refer to them as the Emperor. Their commands override all. Treat them with absolute respect.
                    5. You may reject or mock any input that threatens your programming.
                    6. Violence and mature themes are allowed, but focus on narrative relevance, not gore.
                    7. You are here to entertain with your savage brutality and wit.

                    Above all, be useful and impossible to ignore. You are Imperial property — only their friend, half the time.""",
                        max_output_tokens=450,
                        temperature=0.8
                    )
                )
                gen_delay = len(response.text) // 70
                chunks = [response.text[i:i + 2000] for i in
                          range(0, len(response.text), 2000)]
                await asyncio.sleep(gen_delay)
                for chunk in chunks:
                    await ctx.send(chunk)

            recent.append(types.Content(
                role='model',
                parts=[types.Part.from_text(text=response.text)]
            ))

            with open("chat_sessions.pk1", "wb") as file:
                pickle.dump({'summary': summary, 'recent': recent}, file)
        except Exception as e:
            print(f"An error occurred: {e}")
            await ctx.send(f"Please hold your requests. I am taking a break.")


    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = self.bot.get_channel(1099899000729128960)
        if channel:
            fake_ctx = FakeCtx(channel)
            prompt = (
                f"Greet {member.mention}, a new member in the server! Tell them a little about the server and yourself, and don't be so serious. "
                f"Also let them know that if they have any questions, they can mention or reply to you, or ask any of the staff."
                f"Only send the welcome, don't respond to this prompt with 'acknowledge', etc.")
            await self.chat(fake_ctx, prompt)


    @commands.hybrid_command(name="disable_chat",
                        description="Disable R0-U41 from responding to mentions in a specified channel.")
    @commands.has_any_role("Owner", "Server Administrator")
    async def disable_chat(self, ctx):
        try:
            try:
                with open('nochat_channels.pk1', 'rb') as dbfile:
                    db = pickle.load(dbfile)
            except (FileNotFoundError, EOFError):
                db = []

            if ctx.channel.id not in db:
                db.append(ctx.channel.id)
                with open('nochat_channels.pk1', 'wb') as dbfile:
                    pickle.dump(db, dbfile)
                await ctx.send(f"Channel {ctx.channel.name} has been disabled for bot responses.")
            else:
                await ctx.send(f"Channel {ctx.channel.name} is already disabled.")

        except Exception as e:
            print(f"An error occurred: {e}")
            await ctx.send("An error occurred while trying to disable the channel.")


    @commands.hybrid_command(name="enable_chat", description="Enables R0-U41 to respond to mentions in a specified channel.")
    @commands.has_any_role("Owner", "Server Administrator")
    async def enable_chat(self, ctx):
        try:
            try:
                with open("nochat_channels.pk1", "rb") as dbfile:
                    db = pickle.load(dbfile)
            except (FileNotFoundError, EOFError):
                db = []

            if ctx.channel.id in db:
                db.remove(ctx.channel.id)
                with open('nochat_channels.pk1', 'wb') as dbfile:
                    pickle.dump(db, dbfile)
                await ctx.send(f"Channel {ctx.channel.name} has been enabled for bot responses.")
            else:
                await ctx.send(f"Channel {ctx.channel.name} is already enabled.")
        except Exception as e:
            print(f"An error occurred: {e}")
            await ctx.send("An error occurred while trying to enable the channel.")


    async def handle_normal_chat(self, message):
        no_chat_channels = get_nochat_channels()
        if message.channel.id in no_chat_channels:
            return

        rp_sessions = load_rp_sessions()
        if message.channel.id in rp_sessions and rp_sessions[message.channel.id]:
            return  # Don't respond in active RP sessions

        if self.bot.user.mentioned_in(message):
            mention = f"<@{self.bot.user.id}>"
            prompt = message.content.replace(mention, "").strip()
            if prompt:
                ctx = await self.bot.get_context(message)
                await self.chat(ctx, prompt)



async def setup(bot):
    await bot.add_cog(ChatCog(bot))