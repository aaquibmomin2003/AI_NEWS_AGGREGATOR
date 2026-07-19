from typing import Optional
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.agent.digest_agent import DigestAgent
from app.database.repository import Repository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Small pause between each digest-generation call. Groq's free-tier rate
# limit was getting hit hard once processing more than ~10 articles in a
# run (repeated 429s, each costing several seconds of retry backoff) —
# pacing requests proactively is faster and cheaper overall than reacting
# to 429s after the fact.
DIGEST_REQUEST_DELAY_SECONDS = 1.0


def process_digests(limit: Optional[int] = None) -> dict:
    agent = DigestAgent()
    repo = Repository()

    articles = repo.get_articles_without_digest(limit=limit)
    total = len(articles)
    processed = 0
    failed = 0

    logger.info(f"Starting digest processing for {total} articles")

    for idx, article in enumerate(articles, 1):
        article_type = article["type"]
        article_id = article["id"]
        article_title = article["title"][:60] + "..." if len(article["title"]) > 60 else article["title"]

        logger.info(f"[{idx}/{total}] Processing {article_type}: {article_title} (ID: {article_id})")

        try:
            digest_result = agent.generate_digest(
                title=article["title"],
                content=article["content"],
                article_type=article_type
            )

            if digest_result:
                repo.create_digest(
                    article_type=article_type,
                    article_id=article_id,
                    url=article["url"],
                    title=digest_result.title,
                    summary=digest_result.summary,
                    published_at=article.get("published_at")
                )
                processed += 1
                logger.info(f"✓ Successfully created digest for {article_type} {article_id}")
            else:
                failed += 1
                logger.warning(f"✗ Failed to generate digest for {article_type} {article_id}")
        except Exception as e:
            failed += 1
            logger.error(f"✗ Error processing {article_type} {article_id}: {e}")

        # Pace requests to stay under Groq's rate limit, rather than
        # relying entirely on reactive retry-after-429 behavior. Skip the
        # sleep after the very last item — no point waiting when there's
        # nothing left to send.
        if idx < total:
            time.sleep(DIGEST_REQUEST_DELAY_SECONDS)

    logger.info(f"Processing complete: {processed} processed, {failed} failed out of {total} total")

    return {
        "total": total,
        "processed": processed,
        "failed": failed
    }


if __name__ == "__main__":
    result = process_digests()
    print(f"Total articles: {result['total']}")
    print(f"Processed: {result['processed']}")
    print(f"Failed: {result['failed']}")