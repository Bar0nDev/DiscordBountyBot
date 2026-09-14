from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands
from discord import app_commands
import os
import pickle
import asyncio
import urllib.error
import urllib.request
from pydantic import BaseModel
from typing import List, Dict, Any
from openai import AsyncOpenAI
import json
import traceback

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# MODEL = "deepseek-ai/DeepSeek-V3.2-TEE"
# MODEL = "deepseek-ai/DeepSeek-V3-0324-TEE"
# MODEL = "openai/gpt-oss-120b-TEE"
# MODEL = "zai-org/GLM-5-TEE"
# MODEL = "moonshotai/Kimi-K2.5-TEE"
MODEL = "deepseek-chat"

from utils.utils import NEWS_URL


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
        # Fixed to match Document 1's path structure
        self.pickle_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news.pkl")
        self.pickle_lock = asyncio.Lock()

    def _load_pickle_data(self) -> List[Dict[str, Any]]:
        """Load data from pickle file. Creates empty list if file doesn't exist."""
        try:
            with open(self.pickle_file, 'rb') as f:
                return pickle.load(f)
        except (FileNotFoundError, EOFError):
            return []

    def _save_pickle_data(self, data: List[Dict[str, Any]]):
        """Save data to pickle file."""
        with open(self.pickle_file, 'wb') as f:
            pickle.dump(data, f)

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
            raise ValueError(f"AI response missing required fields. Got: {parsed}")

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
                title = story.get('original_idea', 'No idea text')[:50]
                author = story.get('author', 'Unknown')
                embed["fields"].append({
                    "name": f"{i}. [IDEA] {title}{'...' if len(story.get('original_idea', '')) > 50 else ''}",
                    "value": f"Type: Story Idea | Author: {author}",
                    "inline": False
                })
            else:
                # Complete user story - show headline
                headline = story.get('headline', 'No headline')[:50]
                author = story.get('author', 'Unknown')
                embed["fields"].append({
                    "name": f"{i}. {headline}{'...' if len(story.get('headline', '')) > 50 else ''}",
                    "value": f"Type: {story.get('story_type', 'unknown')} | Author: {author}",
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
        # Get all entries from pickle
        all_pickle_data = await self._get_user_stories()

        # Separate story ideas from complete user stories
        user_stories = []
        story_ideas = []

        for entry in all_pickle_data:
            if entry.get("story_type") == "story_idea" and entry.get("original_idea"):
                story_ideas.append(entry)
            elif entry.get("headline") and entry.get("report"):
                user_stories.append(entry)

        # Process only the OLDEST story idea (first one in the list)
        processed_idea = None
        if story_ideas:
            oldest_idea = story_ideas[0]  # Get the first/oldest story idea
            try:
                processed_idea = await self._process_story_idea(oldest_idea["original_idea"])
                print(f"Processed story idea: {oldest_idea['original_idea']}")
                print(f"Processed result: {processed_idea}")  # Debug line
            except Exception as e:
                print(f"Failed to process story idea: {e}")

        # Determine how many AI stories to generate
        total_user_content = len(user_stories) + (1 if processed_idea else 0)

        if total_user_content > 0:
            # If there are user stories, generate no AI stories
            ai_stories_needed = 0
        else:
            # If no user stories, generate 5 AI stories
            ai_stories_needed = 5

        # Generate AI stories using Chutes AI
        # Generate AI stories using Chutes AI
        prompt = (
            "You are the Holonet News, the primary news source for stories and events across the Star Wars galaxy. "
            "The year is 2BBY. Imperials rule, and small rebel cells are emerging. "
            "In a witty yet serious tone, generate Star Wars news reports. "
            "Avoid mentioning canon characters like Darth Vader. "
            "Prepend an emoji to the headline relevant to the topic. "
            "Lothal civilians has also been recently nuked in the server lore, so locals are upset at the Rebel Alliance if ever news stories are made about Lothal and Imperials are now controlling the narrative. News stories about Lothal should be very rare however and"
            "it is absolutely ok not to generate any news story about Lothal."
            f"\n\nGenerate exactly {ai_stories_needed} different news stories. "
            'You must respond with a JSON object in this format:\n'
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
            print(f"AI Response: {parsed_response}")  # Debug line

            # Handle different possible JSON structures
            if isinstance(parsed_response, list):
                ai_news_data = parsed_response
            elif "stories" in parsed_response:
                ai_news_data = parsed_response["stories"]
            elif "news" in parsed_response:
                ai_news_data = parsed_response["news"]
            elif "headline" in parsed_response and "report" in parsed_response:
                # Single story wrapped as object
                ai_news_data = [parsed_response]
            else:
                print(f"Unexpected JSON structure: {parsed_response}")
                ai_news_data = []

            ai_news = [NewsReport(**story) for story in ai_news_data[:ai_stories_needed]]

        except Exception as e:
            print(f"Failed to generate AI news: {e}")
            print(f"Full error: {traceback.format_exc()}")  # Add this import: import traceback
            ai_news = []

        # Combine all stories
        all_stories = []

        # Add complete user stories
        for story in user_stories:
            all_stories.append(NewsReport(
                headline=story["headline"],
                report=story["report"]
            ))

        # Add the ONE processed story idea (if it exists)
        if processed_idea:
            all_stories.append(processed_idea)

        # Add AI stories
        all_stories.extend(ai_news)

        # Create and send embed
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

        for report in all_stories:
            headline = report.headline
            description = report.report
            embed["fields"].append({
                "name": headline.strip(),
                "value": description.strip(),
                "inline": False
            })
            embed["fields"].append({
                "name": "\u200b",
                "value": "\u200b",
                "inline": False
            })

        # Send the news report
        URL = NEWS_URL
        if URL:
            webhook_data = {'embeds': [embed]}
            request = urllib.request.Request(
                URL,
                data=json.dumps(webhook_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            response_status, response_body = await asyncio.to_thread(_post_webhook, request)
            if response_status != 204:
                print(f'Failed to send embed: {response_status}')
                print(f'Response body: {response_body}')
        else:
            print("NEWS_URL is not configured; skipping webhook report")

        # Remove only processed entries from pickle
        remaining_data = []

        # Keep all unprocessed story ideas (skip the one we just processed)
        if story_ideas and len(story_ideas) > 1:
            remaining_data.extend(story_ideas[1:])

        # Save the remaining story ideas back to pickle
        async with self.pickle_lock:
            self._save_pickle_data(remaining_data)

        print(f"Remaining story ideas in queue: {len(remaining_data)}")

    async def handle_news_report(self):
        if not self.scheduler_started:
            self.scheduler.start()
            self.scheduler_started = True
        await self.news_report()


async def setup(bot):
    await bot.add_cog(NewsCog(bot))
