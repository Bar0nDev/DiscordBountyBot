import aiohttp
from discord.ext import commands
from google import genai
from google.genai import types
import os
from pydantic import BaseModel

client = genai.Client(api_key=os.getenv("API_KEY"))
MODEL = "gemini-2.0-flash"

NEWS_SAFETY_SETTINGS = [
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

class NewsReport(BaseModel):
    headline: str
    report: str


class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def news_report(self):
        prompt = (
            "You are the Holonet News, the primary news source for stories and events across the Star Wars galaxy. "
            "The year is 2BBY. Imperials rule, and small rebel cells are emerging. "
            "In a witty yet serious tone, generate five believable Star Wars news report. "
            "Avoid mentioning canon characters like Darth Vader. "
            "Prepend an emoji to the headline relevant to the topic. "
        )

        response = client.models.generate_content(
            model=MODEL,
            contents=["Generate Star Wars News Reports"],
            config=types.GenerateContentConfig(
                safety_settings=NEWS_SAFETY_SETTINGS,
                system_instruction=prompt,
                response_mime_type="application/json",
                response_schema=list[NewsReport]
            )
        )

        holonet_news: list[NewsReport] = response.parsed

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

        for report in holonet_news:
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

        URL = "https://discord.com/api/webhooks/1366335187729776721/V2cqAT5Z9JiEH7YKKNThgBLl6dF-370ijaZ9z6ajE8QUhxKE5ASxibveYpj6zMpofmDi"
        async with aiohttp.ClientSession() as session:
            webhook_data = {
                'embeds': [embed]
            }
            async with session.post(URL, json=webhook_data) as response:
                if response.status != 204:
                    print(f'Failed to send embed: {response.status}')


async def setup(bot):
    await bot.add_cog(NewsCog(bot))