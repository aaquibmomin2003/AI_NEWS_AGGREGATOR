import os
import json
from typing import List

from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class RankedArticle(BaseModel):
    digest_id: str = Field(description="The ID of the digest (article_type:article_id)")
    relevance_score: float = Field(description="Relevance score from 0.0 to 10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position (1 = most relevant)", ge=1)
    reasoning: str = Field(description="Brief explanation of why this article is ranked here")


class RankedDigestList(BaseModel):
    articles: List[RankedArticle]


CURATOR_PROMPT = """
You are an expert AI news curator specializing in personalized content ranking for AI professionals.

Your role is to analyze and rank AI-related news articles, research papers, and video content based on a user's specific profile, interests, and background.

Ranking Criteria:
1. Relevance to user's stated interests and background
2. Technical depth and practical value
3. Novelty and significance of the content
4. Alignment with user's expertise level
5. Actionability and real-world applicability

Scoring Guidelines:
- 9.0-10.0: Highly relevant
- 7.0-8.9: Very relevant
- 5.0-6.9: Moderately relevant
- 3.0-4.9: Somewhat relevant
- 0.0-2.9: Low relevance

Return ONLY valid JSON in the following format:

{
  "articles": [
    {
      "digest_id": "...",
      "relevance_score": 9.4,
      "rank": 1,
      "reasoning": "..."
    }
  ]
}

Do NOT wrap the JSON inside markdown.
"""


class CuratorAgent:

    def __init__(self, user_profile: dict):

        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        )

        # You can change this to another Groq model if desired
        self.model = "llama-3.3-70b-versatile"

        self.user_profile = user_profile
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):

        interests = "\n".join(
            f"- {interest}"
            for interest in self.user_profile["interests"]
        )

        preferences = self.user_profile["preferences"]

        pref_text = "\n".join(
            f"- {k}: {v}"
            for k, v in preferences.items()
        )

        return f"""
{CURATOR_PROMPT}

User Profile

Name:
{self.user_profile["name"]}

Background:
{self.user_profile["background"]}

Expertise Level:
{self.user_profile["expertise_level"]}

Interests:
{interests}

Preferences:
{pref_text}
"""

    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:

        if not digests:
            return []

        digest_list = "\n\n".join([
            f"""
ID: {d['id']}
Title: {d['title']}
Summary: {d['summary']}
Type: {d['article_type']}
"""
            for d in digests
        ])

        user_prompt = f"""
Rank these {len(digests)} AI news digests.

{digest_list}
"""

        try:

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self.system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                temperature=0.3,
            )

            content = response.choices[0].message.content.strip()

            # Remove markdown if Groq returns it
            content = content.replace("```json", "")
            content = content.replace("```", "").strip()

            ranked = RankedDigestList.model_validate_json(content)

            return ranked.articles

        except Exception as e:
            print(f"Error ranking digests: {e}")
            return []