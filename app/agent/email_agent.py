import os
from datetime import datetime
from typing import List, Optional

from openai import OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


# -----------------------------
# Pydantic Models
# -----------------------------

class EmailIntroduction(BaseModel):
    greeting: str = Field(
        description="Personalized greeting with user's name and date"
    )

    introduction: str = Field(
        description="2-3 sentence overview of top ranked articles"
    )


class RankedArticleDetail(BaseModel):
    digest_id: str
    rank: int
    relevance_score: float
    title: str
    summary: str
    url: str
    article_type: str
    reasoning: Optional[str] = None



class EmailDigestResponse(BaseModel):

    introduction: EmailIntroduction
    articles: List[RankedArticleDetail]
    total_ranked: int
    top_n: int


    def to_markdown(self):

        markdown = f"{self.introduction.greeting}\n\n"

        markdown += (
            f"{self.introduction.introduction}\n\n"
        )

        markdown += "---\n\n"


        for article in self.articles:

            markdown += f"## {article.title}\n\n"

            markdown += (
                f"{article.summary}\n\n"
            )

            markdown += (
                f"[Read more →]({article.url})\n\n"
            )

            markdown += "---\n\n"


        return markdown



class EmailDigest(BaseModel):

    introduction: EmailIntroduction

    ranked_articles: List[dict]



# -----------------------------
# Prompt
# -----------------------------

EMAIL_PROMPT = """

You are an expert email writer specializing in AI news digest emails.

Create a short personalized introduction.

Requirements:

- Greet the user by name
- Include today's date
- Mention this is their daily AI digest
- Summarize important themes from the top ranked articles
- Keep it professional and engaging

Return ONLY valid JSON:

{
 "greeting":"...",
 "introduction":"..."
}

Do not use markdown.

"""



# -----------------------------
# Email Agent
# -----------------------------

class EmailAgent:


    def __init__(self, user_profile: dict):

        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1"
        )


        self.model = "llama-3.3-70b-versatile"

        self.user_profile = user_profile



    # -----------------------------
    # Generate Introduction
    # -----------------------------

    def generate_introduction(
            self,
            ranked_articles: List
    ) -> EmailIntroduction:


        current_date = datetime.now().strftime(
            "%B %d, %Y"
        )


        if not ranked_articles:

            return EmailIntroduction(

                greeting=
                f"Hey {self.user_profile['name']}, "
                f"here is your daily AI digest for {current_date}.",

                introduction=
                "No articles were ranked today."

            )



        top_articles = ranked_articles[:10]


        article_summaries = "\n".join(

            [
                f"""
{idx+1}. 
Title: {article.title}
Score: {article.relevance_score}/10
"""
                for idx, article in enumerate(top_articles)

            ]

        )



        user_prompt = f"""

Create an introduction for:

User:
{self.user_profile['name']}


Date:
{current_date}


Top AI Articles:

{article_summaries}

"""



        try:


            response = self.client.chat.completions.create(

                model=self.model,

                messages=[

                    {
                        "role":"system",
                        "content":EMAIL_PROMPT
                    },

                    {
                        "role":"user",
                        "content":user_prompt
                    }

                ],

                temperature=0.7

            )



            content = response.choices[0].message.content.strip()



            # Remove markdown if returned

            content = content.replace(
                "```json",
                ""
            )

            content = content.replace(
                "```",
                ""
            ).strip()



            intro = EmailIntroduction.model_validate_json(
                content
            )


            return intro



        except Exception as e:

            print(
                f"Error generating introduction: {e}"
            )


            return EmailIntroduction(

                greeting=
                f"Hey {self.user_profile['name']}, "
                f"here is your daily AI digest for {current_date}.",


                introduction=
                "Here are today's top AI news articles ranked by relevance."

            )



    # -----------------------------
    # Create Simple Digest
    # -----------------------------

    def create_email_digest(
            self,
            ranked_articles: List[dict],
            limit:int=10
    ) -> EmailDigest:


        top_articles = ranked_articles[:limit]


        introduction = self.generate_introduction(
            top_articles
        )


        return EmailDigest(

            introduction=introduction,

            ranked_articles=top_articles

        )



    # -----------------------------
    # Create Full Digest Response
    # -----------------------------

    def create_email_digest_response(

            self,

            ranked_articles: List[RankedArticleDetail],

            total_ranked:int,

            limit:int=10

    ) -> EmailDigestResponse:



        top_articles = ranked_articles[:limit]


        introduction = self.generate_introduction(
            top_articles
        )


        return EmailDigestResponse(

            introduction=introduction,

            articles=top_articles,

            total_ranked=total_ranked,

            top_n=limit

        )