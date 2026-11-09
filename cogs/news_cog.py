from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from discord import app_commands
import os
import pickle
import asyncio
import logging
import tempfile
import urllib.error
import urllib.request
from pydantic import BaseModel
from typing import List, Dict, Any
from openai import AsyncOpenAI
import json

def get_deepseek_client():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    return AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com") if api_key else None


client = get_deepseek_client()

# MODEL = "deepseek-ai/DeepSeek-V3.2-TEE"
# MODEL = "deepseek-ai/DeepSeek-V3-0324-TEE"
# MODEL = "openai/gpt-oss-120b-TEE"
# MODEL = "zai-org/GLM-5-TEE"
# MODEL = "moonshotai/Kimi-K2.5-TEE"
MODEL = "deepseek-chat"

from utils.utils import NEWS_URL

logger = logging.getLogger(__name__)

DISCORD_MAX_EMBED_FIELDS = 25
DISCORD_MAX_EMBED_CHARACTERS = 6000
DISCORD_MAX_FIELD_NAME = 256
DISCORD_MAX_FIELD_VALUE = 1024


def _utf16_length(value: str) -> int:
    """Return the length Discord uses for a string with supplementary Unicode."""
    return len(value.encode("utf-16-le")) // 2


def _truncate_utf16(value: str, maximum: int) -> str:
    """Truncate to a Discord UTF-16 limit without leaving a broken surrogate."""
    encoded = value.encode("utf-16-le")
    if len(encoded) <= maximum * 2:
        return value
    return encoded[:maximum * 2].decode("utf-16-le", errors="ignore")


def _post_webhook(request):
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return error.code, body

class NewsReport(BaseModel):
    headline: str
    report: str


class UserStory(BaseModel):
    headline: str
    report: str
    story_type: str  # "user_story" or "story_idea"


class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.news_report, 'interval', hours=12)
        self.scheduler_started = False
        self.startup_report_started = False
        # Fixed to match Document 1's path structure
        self.pickle_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news.pkl")
        self.pickle_lock = asyncio.Lock()
        self.publish_lock = asyncio.Lock()
        pickle_directory = os.path.dirname(self.pickle_file)
        if pickle_directory:
            os.makedirs(pickle_directory, exist_ok=True)

    def _load_pickle_data(self) -> List[Dict[str, Any]]:
        """Load data from pickle file. Creates empty list if file doesn't exist."""
        try:
            with open(self.pickle_file, 'rb') as f:
                return pickle.load(f)
        except (FileNotFoundError, EOFError):
            return []

    def _save_pickle_data(self, data: List[Dict[str, Any]]):
        """Atomically replace the pickle file after fully writing its contents."""
        pickle_directory = os.path.dirname(self.pickle_file)
        if pickle_directory:
            os.makedirs(pickle_directory, exist_ok=True)

        temporary_path = None
        file_descriptor = None
        try:
            file_descriptor, temporary_path = tempfile.mkstemp(
                prefix=".news-",
                suffix=".tmp",
                dir=pickle_directory or ".",
            )
            with os.fdopen(file_descriptor, "wb") as pickle_file:
                file_descriptor = None
                pickle.dump(data, pickle_file)
                pickle_file.flush()
                os.fsync(pickle_file.fileno())
            os.replace(temporary_path, self.pickle_file)
            temporary_path = None
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass

    async def _add_to_pickle(self, story_data: Dict[str, Any]):
        """Thread-safe method to add story to pickle file."""
        async with self.pickle_lock:
            current_data = self._load_pickle_data()
            current_data.append(story_data)
            self._save_pickle_data(current_data)

    async def _get_user_stories(self) -> List[Dict[str, Any]]:
        """Get all user stories from pickle file."""
        async with self.pickle_lock:
            return self._load_pickle_data()

    async def _clear_user_stories(self):
        """Clear all user stories from pickle file after processing."""
        async with self.pickle_lock:
            self._save_pickle_data([])

    async def _process_story_idea(self, story_idea: str) -> NewsReport:
        """Process a story idea through the AI to generate a full news report."""
        prompt = (
            "You are the Holonet News, the primary news source for stories and events across the Star Wars galaxy. "
            "The year is 2BBY. Imperials rule, and small rebel cells are emerging. "
            "Take the following story idea and develop it into a believable Star Wars news report. "
            "Write in a witty yet serious tone. Avoid mentioning canon characters like Darth Vader. "
            "Create a headline with a relevant emoji prepended, and write a detailed report. "
            "\n\n**LENGTH REQUIREMENTS:**\n"
            "- Headline: Maximum 250 characters (keep it punchy and concise)\n"
            "- Report: Maximum 900 characters (be detailed but stay within this limit)\n"
            "\n\nYou must respond with a JSON object in this exact format:\n"
            '{"headline": "your headline here", "report": "your report here"}\n\n'
            f"Story idea: {story_idea}"
        )

        response = await client.chat.completions.create(
            model=MODEL,
            temperature=0.8,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Develop this story idea into a news report: {story_idea}"}
            ],
            response_format={"type": "json_object"}
        )

        parsed = json.loads(response.choices[0].message.content)

        # Validate the response has required fields
        if "headline" not in parsed or "report" not in parsed:
            raise ValueError("AI response missing required fields")

        return NewsReport(**parsed)

    @commands.hybrid_command(name="add_user_story", description="Add a user story directly to the news queue")
    @app_commands.describe(headline="The headline for the news story",
                           report="The full report/content of the news story")
    @commands.has_role("Game Master")
    async def add_user_story(self, ctx, headline: str = None, *, report: str = None):
        """Add a user story directly to the news queue."""
        if not headline or not report:
            await ctx.send("Usage: `/add_user_story headline:\"your headline\" report:your report text`")
            return

        story_data = {
            "headline": headline,
            "report": report,
            "story_type": "user_story",
            "author": str(ctx.author),
            "timestamp": ctx.message.created_at.isoformat()
        }

        await self._add_to_pickle(story_data)
        await ctx.send(f"✅ User story added: **{headline}**")

    @commands.hybrid_command(name="add_story_idea", description="Add a story idea that will be processed by the bot")
    @app_commands.describe(idea="The story idea to be processed into a full news report")
    @commands.has_role("Game Master")
    async def add_story_idea(self, ctx, *, idea: str = None):
        """Add a story idea that will be processed by the bot."""
        if not idea:
            await ctx.send("Usage: `/add_story_idea idea:your story idea here`")
            return

        try:
            # Process the story idea through AI
            processed_story = await self._process_story_idea(idea)

            story_data = {
                "headline": processed_story.headline,
                "report": processed_story.report,
                "story_type": "story_idea",
                "original_idea": idea,
                "author": str(ctx.author),
                "timestamp": ctx.message.created_at.isoformat()
            }

            await self._add_to_pickle(story_data)
            await ctx.send(f"✅ Story idea processed and added: **{processed_story.headline}**")

        except Exception as e:
            await ctx.send(f"❌ Error processing story idea: {str(e)}")

    @commands.hybrid_command(name="view_pending_stories", description="View all pending user stories in the queue")
    @commands.has_role("Game Master")
    async def view_pending_stories(self, ctx):
        """View all pending user stories in the queue."""
        stories = await self._get_user_stories()

        if not stories:
            await ctx.send("📰 No pending stories in the queue.")
            return

        embed = {
            "title": "Pending News Stories",
            "description": f"Total stories in queue: {len(stories)}",
            "color": 0x3498db,
            "fields": []
        }

        for i, story in enumerate(stories[:5], 1):  # Show first 5 stories
            # Handle both story ideas and complete user stories
            if story.get('story_type') == 'story_idea':
                # Story idea from gamemaster - show the original idea
                original_idea = str(story.get('original_idea', 'No idea text'))
                title = _truncate_utf16(original_idea, 50)
                author = _truncate_utf16(str(story.get('author', 'Unknown')), 256)
                embed["fields"].append({
                    "name": f"{i}. [IDEA] {title}{'...' if len(story.get('original_idea', '')) > 50 else ''}",
                    "value": _truncate_utf16(f"Type: Story Idea | Author: {author}", DISCORD_MAX_FIELD_VALUE),
                    "inline": False
                })
            else:
                # Complete user story - show headline
                raw_headline = str(story.get('headline', 'No headline'))
                headline = _truncate_utf16(raw_headline, 50)
                author = _truncate_utf16(str(story.get('author', 'Unknown')), 256)
                embed["fields"].append({
                    "name": f"{i}. {headline}{'...' if _utf16_length(raw_headline) > 50 else ''}",
                    "value": _truncate_utf16(
                        f"Type: {str(story.get('story_type', 'unknown'))} | Author: {author}",
                        DISCORD_MAX_FIELD_VALUE,
                    ),
                    "inline": False
                })

        if len(stories) > 5:
            embed["fields"].append({
                "name": "...",
                "value": f"And {len(stories) - 5} more stories",
                "inline": False
            })

        await ctx.send(embed=embed)

    async def news_report(self):
        """Publish one report without allowing overlapping queue acknowledgements."""
        async with self.publish_lock:
            await self._publish_news_report()

    async def _publish_news_report(self):
        """Build and publish a report, acknowledging only entries in a successful payload."""
        # A missing webhook is a no-op. In particular, do not process model input while
        # delivery is disabled because there is no successful publish to acknowledge.
        if not NEWS_URL:
            logger.info("news webhook skipped: missing_url")
            return

        all_pickle_data = await self._get_user_stories()

        user_stories = []
        story_ideas = []
        for index, entry in enumerate(all_pickle_data):
            if entry.get("story_type") == "story_idea" and entry.get("original_idea"):
                story_ideas.append((index, entry))
            elif entry.get("headline") and entry.get("report"):
                user_stories.append((index, entry))

        processed_idea = None
        processed_idea_index = None
        if story_ideas:
            processed_idea_index, oldest_idea = story_ideas[0]
            try:
                processed_idea = await self._process_story_idea(oldest_idea["original_idea"])
            except Exception:
                logger.warning("news model failure: story_idea")
                # The idea remains queued. Complete user stories can still be delivered
                # in the same report, if there are any.
                processed_idea = None
                processed_idea_index = None

        report_candidates = []
        for index, story in user_stories:
            try:
                report_candidates.append((index, NewsReport(
                    headline=story["headline"],
                    report=story["report"],
                )))
            except Exception:
                # Invalid entries are retained rather than making the whole queue unsafe.
                continue

        if processed_idea is not None:
            report_candidates.append((processed_idea_index, processed_idea))

        ai_news = []
        if not report_candidates:
            # A failed story-idea conversion is not a reason to replace the queued idea
            # with generated content. It must remain pending for a later attempt.
            if story_ideas:
                return

            ai_stories_needed = 5
            prompt = (
                "You are the Holonet News, the primary news source for stories and events across the Star Wars galaxy. "
                "The year is 2BBY. Imperials rule, and small rebel cells are emerging. "
                "In a witty yet serious tone, generate Star Wars news reports. "
                "Avoid mentioning canon characters like Darth Vader. "
                "Prepend an emoji to the headline relevant to the topic. "
                "Lothal civilians has also been recently nuked in the server lore, so locals are upset at the Rebel Alliance if ever news stories are made about Lothal and Imperials are now controlling the narrative. News stories about Lothal should be very rare however and"
                "it is absolutely ok not to generate any news story about Lothal."
                f"\n\nGenerate exactly {ai_stories_needed} different news stories. "
                '{"stories": [{"headline": "...", "report": "..."}, {"headline": "...", "report": "..."}]}\n'
                "Each story must have both a 'headline' and a 'report' field."
            )

            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    temperature=0.8,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user",
                         "content": f"Generate {ai_stories_needed} Star Wars News Reports in the specified JSON format"}
                    ],
                    response_format={"type": "json_object"}
                )

                parsed_response = json.loads(response.choices[0].message.content)
                if isinstance(parsed_response, list):
                    ai_news_data = parsed_response
                elif isinstance(parsed_response, dict) and "stories" in parsed_response:
                    ai_news_data = parsed_response["stories"]
                elif isinstance(parsed_response, dict) and "news" in parsed_response:
                    ai_news_data = parsed_response["news"]
                elif isinstance(parsed_response, dict) and {
                    "headline", "report"
                }.issubset(parsed_response):
                    ai_news_data = [parsed_response]
                else:
                    ai_news_data = []

                ai_news = [
                    NewsReport(**story)
                    for story in ai_news_data[:ai_stories_needed]
                ]
            except Exception:
                logger.warning("news model failure: generated_news")
                # No queued entries are acknowledged when model generation fails.
                return

            report_candidates.extend((None, report) for report in ai_news)

        embed = {
            "title": "Holonet News Report",
            "description": "Latest updates from across the galaxy:",
            "color": 224767,
            "fields": [],
            "image": {
                "url": "https://i.imgur.com/HbvWHt3.png"
            },
            "thumbnail": {
                "url": "https://static.wikia.nocookie.net/starwars/images/9/91/Bettiebotvj.png/revision/latest/thumbnail/width/360/height/360?cb=20200420000222"
            }
        }

        # Discord allows at most 25 fields and 6,000 characters per embed. Truncate
        # individual fields to their limits and stop before the aggregate limit.
        embed_characters = _utf16_length(embed["title"]) + _utf16_length(embed["description"])
        delivered_indices = set()
        for source_index, report in report_candidates:
            headline = _truncate_utf16(str(report.headline).strip(), DISCORD_MAX_FIELD_NAME)
            description = _truncate_utf16(str(report.report).strip(), DISCORD_MAX_FIELD_VALUE)
            if not headline or not description:
                continue

            if len(embed["fields"]) >= DISCORD_MAX_EMBED_FIELDS:
                break
            field_characters = _utf16_length(headline) + _utf16_length(description)
            if embed_characters + field_characters > DISCORD_MAX_EMBED_CHARACTERS:
                break

            embed["fields"].append({
                "name": headline,
                "value": description,
                "inline": False
            })
            embed_characters += field_characters
            if source_index is not None:
                delivered_indices.add(source_index)

        if not embed["fields"]:
            return

        webhook_data = {"embeds": [embed]}
        request = urllib.request.Request(
            NEWS_URL,
            data=json.dumps(webhook_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            response_status, _ = await asyncio.to_thread(_post_webhook, request)
        except Exception:
            logger.warning("news webhook failure: transport")
            # Delivery failures leave every queued entry untouched.
            return

        if not 200 <= response_status < 300:
            logger.warning("news webhook failure: status=%s", response_status)
            return

        try:
            await self._acknowledge_entries(all_pickle_data, delivered_indices)
        except Exception:
            logger.warning("news queue acknowledgement failure")

    async def _acknowledge_entries(
            self,
            snapshot: List[Dict[str, Any]],
            delivered_indices: set,
    ):
        """Remove delivered snapshot entries while preserving concurrent appends."""
        if not delivered_indices:
            return

        async with self.pickle_lock:
            current_data = self._load_pickle_data()
            if any(index >= len(current_data) for index in delivered_indices):
                return

            # Enqueues append to the pickle. Verify the delivered positions still
            # contain the original entries before removing them, so a concurrent
            # writer can never cause an unrelated entry to be acknowledged.
            if any(current_data[index] != snapshot[index] for index in delivered_indices):
                return

            remaining_data = [
                entry for index, entry in enumerate(current_data)
                if index not in delivered_indices
            ]
            self._save_pickle_data(remaining_data)

    async def handle_news_report(self):
        if not self.scheduler_started:
            self.scheduler.start()
            self.scheduler_started = True
        if self.startup_report_started:
            return
        self.startup_report_started = True
        await self.news_report()


async def setup(bot):
    await bot.add_cog(NewsCog(bot))
