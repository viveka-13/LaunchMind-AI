# agent/sentiment_service.py
# Real sentiment analysis combining Reddit (PRAW) and DuckDuckGo review discussions scored by VADER

import os
import json
import logging
import datetime
from typing import List, Dict, Any, Optional

import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

from agent.llm_client import llm_call

logger = logging.getLogger(__name__)

# Ensure VADER lexicon is available
try:
    _vader = SentimentIntensityAnalyzer()
except Exception:
    nltk.download("vader_lexicon", quiet=True)
    _vader = SentimentIntensityAnalyzer()


class SentimentSource:
    """Base interface for sentiment post retrieval."""
    def fetch_posts(self, query: str, limit: int = 25) -> List[Dict[str, str]]:
        raise NotImplementedError


class RedditSentimentSource(SentimentSource):
    """
    Retrieves public posts and comments from Reddit via PRAW.
    Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT.
    """
    def __init__(self):
        self.client_id = os.environ.get("REDDIT_CLIENT_ID")
        self.client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        self.user_agent = os.environ.get("REDDIT_USER_AGENT", "LaunchMindAI/1.0 by AutoStartup")

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def fetch_posts(self, query: str, limit: int = 25) -> List[Dict[str, str]]:
        if not self.is_configured():
            return []

        try:
            import praw
            reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
            posts = []
            for submission in reddit.subreddit("all").search(query, sort="relevance", limit=limit):
                text = f"{submission.title}. {submission.selftext}"
                if len(text.strip()) >= 20:
                    posts.append({
                        "text": text[:500],
                        "url": f"https://reddit.com{submission.permalink}",
                        "source": "reddit",
                    })
            return posts
        except Exception as e:
            logger.warning(f"[Reddit] Post fetch failed: {e}")
            return []


class WebSearchSentimentSource(SentimentSource):
    """
    Retrieves discussion & review snippets via DuckDuckGo.
    """
    def fetch_posts(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        try:
            from ddgs import DDGS
            ddgs = DDGS()
            posts = []
            for q in [f"{query} reviews complaints", f"{query} user feedback discussion"]:
                results = list(ddgs.text(q, max_results=limit // 2))
                for r in results:
                    body = r.get("body", "").strip()
                    if len(body) >= 20:
                        posts.append({
                            "text": f"{r.get('title', '')}: {body}"[:500],
                            "url": r.get("href", ""),
                            "source": "web_search",
                        })
            return posts
        except Exception as e:
            logger.warning(f"[WebSearch] Sentiment post fetch failed: {e}")
            return []


async def analyze_sentiment(query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch posts from Reddit & Web, score with VADER, and aggregate complaint/praise themes with LLM.
    """
    reddit_src = RedditSentimentSource()
    web_src = WebSearchSentimentSource()

    posts: List[Dict[str, str]] = []
    skipped_reasons = []

    if reddit_src.is_configured():
        reddit_posts = reddit_src.fetch_posts(query, limit=25)
        posts.extend(reddit_posts)
    else:
        skipped_reasons.append("REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET not configured")

    web_posts = web_src.fetch_posts(query, limit=25)
    posts.extend(web_posts)

    # Deduplicate by text similarity / URL
    seen_urls = set()
    unique_posts = []
    for p in posts:
        url = p.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_posts.append(p)
        elif not url:
            unique_posts.append(p)

    unique_posts = unique_posts[:50]  # Cap volume at 50
    sample_size = len(unique_posts)

    if sample_size < 5:
        reason_msg = "; ".join(skipped_reasons) if skipped_reasons else "Fewer than 5 relevant community posts found"
        return {
            "status": "ok",
            "reason": None,
            "data": {
                "sample_size": sample_size,
                "verdict": "insufficient data",
                "message": f"Sample size too small ({sample_size} posts). {reason_msg}.",
                "mean_compound_score": 0.0,
                "counts": {"positive": 0, "neutral": 0, "negative": 0},
                "praise_themes": [],
                "complaint_themes": [],
                "retrieved_at": datetime.datetime.utcnow().isoformat(),
            },
        }

    # Score each post with VADER
    pos_count = 0
    neu_count = 0
    neg_count = 0
    total_compound = 0.0

    scored_posts = []
    for p in unique_posts:
        scores = _vader.polarity_scores(p["text"])
        compound = scores["compound"]
        total_compound += compound

        if compound >= 0.05:
            label = "positive"
            pos_count += 1
        elif compound <= -0.05:
            label = "negative"
            neg_count += 1
        else:
            label = "neutral"
            neu_count += 1

        scored_posts.append({
            "text": p["text"],
            "url": p["url"],
            "compound": compound,
            "label": label,
        })

    mean_compound = round(total_compound / sample_size, 3)

    if mean_compound >= 0.15:
        overall_sentiment = "positive"
    elif mean_compound <= -0.15:
        overall_sentiment = "negative"
    else:
        overall_sentiment = "neutral"

    # LLM Batched Theme Extraction over sample (top 10 most polarized posts)
    praise_themes = []
    complaint_themes = []
    try:
        sample_for_llm = sorted(scored_posts, key=lambda x: abs(x["compound"]), reverse=True)[:10]
        sample_text = "\n\n".join(
            f"Snippet [{i+1}] (Score: {p['compound']}): {p['text']}\nURL: {p['url']}"
            for i, p in enumerate(sample_for_llm)
        )

        theme_prompt = f"""You are a customer feedback analyst. Based ONLY on the following scored user reviews and posts for '{query}', identify:
1. Top 2 praise themes (what users appreciate), with short direct quoted snippet.
2. Top 2 complaint themes (what users criticize or struggle with), with short direct quoted snippet.

Feedback:
{sample_text}

Respond in strictly valid JSON:
{{
  "praise_themes": ["Praise 1...", "Praise 2..."],
  "complaint_themes": ["Complaint 1...", "Complaint 2..."]
}}
"""
        res = await llm_call(theme_prompt, node="sentiment_themes", session_id=session_id)
        clean = res.text.strip().strip("```json").strip("```").strip()
        themes = json.loads(clean)
        praise_themes = themes.get("praise_themes", [])
        complaint_themes = themes.get("complaint_themes", [])
    except Exception as llm_err:
        logger.debug(f"[Sentiment] Theme extraction skipped: {llm_err}")

    return {
        "status": "ok",
        "reason": None,
        "data": {
            "sample_size": sample_size,
            "overall_sentiment": overall_sentiment,
            "mean_compound_score": mean_compound,
            "counts": {
                "positive": pos_count,
                "neutral": neu_count,
                "negative": neg_count,
            },
            "praise_themes": praise_themes,
            "complaint_themes": complaint_themes,
            "sources_used": [p["source"] for p in unique_posts[:5]],
            "retrieved_at": datetime.datetime.utcnow().isoformat(),
        },
    }
