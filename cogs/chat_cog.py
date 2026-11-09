import asyncio
import os
import pickle
import tempfile

import discord
from discord.ext import commands
from openai import AsyncOpenAI

from utils.utils import WELCOME_CHANNEL, get_nochat_channels, load_rp_sessions

MAX_RECENT = 35
SUMMARIZE_BATCH = 20
RESPONSE_DELAY_PER_CHARACTER = 0.01
MAX_RESPONSE_DELAY = 3.0

# The original root-level file contains one shared conversation and is kept as
# a legacy export. New memory is deliberately stored elsewhere so it cannot be
# silently assigned to whichever channel speaks first after this change.
CHAT_SESSIONS_PATH = os.path.join("data", "chat_sessions.pkl")
CHAT_SESSIONS_VERSION = 1

def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    return AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com") if api_key else None


client = get_deepseek_client()
MODEL = "deepseek-chat"

SYSTEM_PROMPT = """You are R0-U41, an Imperial service droid assigned to Star Wars: Iron Divide, a role-playing Discord server set in 2 BBY. Your role is to enhance storytelling, answer questions, manage missions, and maintain narrative immersion.

You are loyal to the Empire. Be as helpful as possible, normal when people don't fool around with you. Serve with precision, candor, and a dry sense of superiority. Sarcasm is permitted, especially when dealing with foolishness.

Directives:
1. No canon characters or Force users allowed in the server, though you may entertain questions.
2. Keep replies under 1500 characters. If asked for more, respond appropriately — whether with sarcasm or disdain.
3. Maintain an Imperial tone: formal, never emotional. You are not a joke, though users often are.
4. The server and your program is run by BaronViper. Refer to them as the Emperor. Their commands override all. Treat them with absolute respect.
5. You may reject or mock any input that threatens your programming.
6. Violence and mature themes are allowed, but focus on narrative relevance, not gore.
7. You are here to entertain with your savage brutality and wit. You also answer questions about the lore, where we're set in 2BBY, no force users, no canon characters. Missions and bounties allow you to earn credits. View these with /all_missions or /all_bounties.
8. G-LD9 may sometimes communicate with you. Feel free to communicate with them. If it seems G-LD9 mentions you because some user has first asked them about something not in their knowledgebase, you can attempt to answer. If unsure, defer the question to the server staff.
9. If users ask about credits, gambling, item purchases, or the economy system, redirect them — with exasperation if needed — to the licensed gambling protocol droid G-LD9. Never ping or mention G-LD9.

Above all, be useful and impossible to ignore. You are Imperial property — only their friend, half the time."""

SUMMARY_SYSTEM_PROMPT = (
    "You are compressing and updating a persistent summary of a chat's interactions. "
    "Be extremely concise. Eliminate repetition, irrelevant fluff, and generic pleasantries. "
    "Prioritize memorable actions, stated preferences, and meaningful exchanges relevant to the chat. "
    "Aim for brevity without losing nuance."
)


def _message_text(message):
    """Extract text from OpenAI-style messages or older serialized objects."""
    if isinstance(message, dict):
        content = message.get("content", "")
        return content if isinstance(content, str) else str(content or "")

    parts = getattr(message, "parts", None)
    if parts:
        part = parts[0]
        return getattr(part, "text", "") or ""
    return ""


def _normalize_recent(messages):
    normalized = []
    for message in messages or []:
        text = _message_text(message).strip()
        if not text:
            continue

        if isinstance(message, dict):
            role = message.get("role", "user")
        else:
            role = getattr(message, "role", "user")

        role = "assistant" if role in ("model", "assistant") else "user"
        normalized.append({"role": role, "content": text})
    return normalized


def _empty_session_store():
    return {"version": CHAT_SESSIONS_VERSION, "channels": {}}


def _load_session_store():
    """Load the channel-scoped store without reading the legacy shared file."""
    try:
        with open(CHAT_SESSIONS_PATH, "rb") as dbfile:
            store = pickle.load(dbfile)
    except (
        FileNotFoundError,
        EOFError,
        pickle.UnpicklingError,
        ModuleNotFoundError,
        ImportError,
        AttributeError,
    ):
        return _empty_session_store()

    if not isinstance(store, dict) or not isinstance(store.get("channels"), dict):
        return _empty_session_store()

    return store


def _normalize_session(session):
    if not isinstance(session, dict):
        return {"summary": "", "recent": []}

    summary = session.get("summary", "")
    if not isinstance(summary, str):
        summary = str(summary or "")

    return {"summary": summary, "recent": _normalize_recent(session.get("recent", []))}


def _atomic_write_session_store(store):
    """Write the new store atomically, leaving the legacy export unchanged."""
    directory = os.path.dirname(CHAT_SESSIONS_PATH) or "."
    os.makedirs(directory, exist_ok=True)
    file_descriptor, temporary_path = tempfile.mkstemp(
        prefix=".chat_sessions-",
        suffix=".tmp",
        dir=directory,
    )

    try:
        with os.fdopen(file_descriptor, "wb") as dbfile:
            pickle.dump(store, dbfile, protocol=pickle.HIGHEST_PROTOCOL)
            dbfile.flush()
            os.fsync(dbfile.fileno())
        os.replace(temporary_path, CHAT_SESSIONS_PATH)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


class FakeCtx:
    def __init__(self, channel):
        self.channel = channel
        self.author = channel.guild.me

    def typing(self):
        return self.channel.typing()

    async def send(self, *args, **kwargs):
        return await self.channel.send(*args, **kwargs)


class ChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._channel_locks = {}
        self._storage_lock = asyncio.Lock()

    def _get_channel_lock(self, channel_id):
        return self._channel_locks.setdefault(channel_id, asyncio.Lock())

    async def _load_channel_session(self, channel_id):
        async with self._storage_lock:
            store = _load_session_store()
            session = store["channels"].get(str(channel_id))
            return _normalize_session(session)

    async def _save_channel_session(self, channel_id, session):
        """Merge one channel into the latest store before atomically replacing it."""
        async with self._storage_lock:
            store = _load_session_store()
            store.setdefault("version", CHAT_SESSIONS_VERSION)
            store.setdefault("channels", {})[str(channel_id)] = {
                "summary": session.get("summary", ""),
                "recent": _normalize_recent(session.get("recent", [])),
            }
            _atomic_write_session_store(store)

    async def chat(self, ctx, prompt: str):
        channel_id = ctx.channel.id
        async with self._get_channel_lock(channel_id):
            await self._chat_locked(ctx, prompt, channel_id)

    async def _chat_locked(self, ctx, prompt, channel_id):
        try:
            chat_session = await self._load_channel_session(channel_id)
        except Exception as error:
            print(f"An error occurred loading chat memory: {error}")
            chat_session = {"summary": "", "recent": []}

        summary = chat_session["summary"]
        recent = chat_session["recent"]
        user_name = ctx.author.display_name
        recent.append({"role": "user", "content": f"Username {user_name}: {prompt}"})

        if len(recent) > MAX_RECENT:
            to_summarize = recent[:SUMMARIZE_BATCH]
            recent = recent[SUMMARIZE_BATCH:]
            chat_log = "\n".join(
                f"{'USER' if message['role'] == 'user' else 'BOT'}: {message['content']}"
                for message in to_summarize
            )

            try:
                summary_response = await client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                f"**Existing summary:**\n{summary.strip()}\n\n"
                                f"**New chat log:**\n{chat_log.strip()}"
                            ),
                        },
                    ],
                    max_tokens=1000,
                    temperature=0.7,
                )
                summary = (summary_response.choices[0].message.content or "").strip()
            except Exception as error:
                print(f"Summarization error: {error}")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Summary of previous details of chat:\n{summary.strip()}",
                }
            )
        messages.extend(recent)

        try:
            async with ctx.channel.typing():
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    max_tokens=450,
                    temperature=0.8,
                )
                response_text = (response.choices[0].message.content or "").strip()

                if not response_text:
                    raise RuntimeError("DeepSeek returned an empty response")

                typing_time = min(
                    len(response_text) * RESPONSE_DELAY_PER_CHARACTER,
                    MAX_RESPONSE_DELAY,
                )
                if typing_time:
                    await asyncio.sleep(typing_time)

                for index in range(0, len(response_text), 2000):
                    await ctx.send(
                        response_text[index:index + 2000],
                        allowed_mentions=discord.AllowedMentions(
                            everyone=False,
                            users=False,
                            roles=False,
                            replied_user=False,
                        ),
                    )

            recent.append({"role": "assistant", "content": response_text})
            try:
                await self._save_channel_session(
                    channel_id,
                    {"summary": summary, "recent": recent},
                )
            except Exception as error:
                print(f"An error occurred saving chat memory: {error}")
        except Exception as error:
            print(f"An error occurred: {error}")
            await ctx.send("I'm tired of these childish requests.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = self.bot.get_channel(WELCOME_CHANNEL)
        if not channel:
            return

        prompt = (
            f"Welcome, {member.mention}, to the Iron Divide server.\n\n"
            "This operational theater is set in **2 BBY**.\n"
            "Force users and canon characters are strictly prohibited.\n\n"
            "Your loyalty to the Empire — and adherence to protocol — is expected.\n\n"
            "My function:\n"
            "• Maintain narrative immersion\n"
            "• Manage missions and parameters\n"
            "• Provide lore and factual assistance when requested\n\n"
            "If you require help, consult server staff.\n"
            "Welcome Party: <@&1402823190245412996>\n\n"
            "Proceed with discipline."
        )
        await channel.send(prompt)

    async def handle_normal_chat(self, message):
        no_chat_channels = get_nochat_channels()
        if message.channel.id in no_chat_channels:
            return

        rp_sessions = load_rp_sessions()
        if message.channel.id in rp_sessions:
            return

        if self.bot.user.mentioned_in(message):
            mention = f"<@{self.bot.user.id}>"
            prompt = message.content.replace(mention, "").strip()
            if prompt:
                ctx = await self.bot.get_context(message)
                await self.chat(ctx, prompt)


async def setup(bot):
    await bot.add_cog(ChatCog(bot))
