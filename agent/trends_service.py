# agent/trends_service.py
# Real Google Trends data retrieval via pytrends (unofficial Google Trends API)
# Note: pytrends uses Google Trends' unofficial API which may be rate-limited (HTTP 429).
# Results are cached locally in SQLite for 24 hours.

import os
import sqlite3
import json
import logging
import datetime
from typing import List, Dict, Any, Optional
import time

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("DB_PATH", "./data/startup_history.db")
CACHE_TTL_HOURS = 24


def _init_trends_cache():
    """Ensure the trends_cache table exists in SQLite."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trends_cache (
                keyword      TEXT PRIMARY KEY,
                timeframe    TEXT,
                response_json TEXT,
                cached_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[GoogleTrends] Failed to init cache table: {e}")


def _get_cached_trends(keyword: str, timeframe: str) -> Optional[dict]:
    """Retrieve cached trends data if within TTL."""
    try:
        _init_trends_cache()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT response_json, cached_at 
            FROM trends_cache 
            WHERE keyword = ? AND timeframe = ?
            """,
            (keyword.lower().strip(), timeframe)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            raw_json, cached_at_str = row
            cached_dt = datetime.datetime.fromisoformat(cached_at_str.replace("Z", "+00:00")) if "T" in cached_at_str else datetime.datetime.strptime(cached_at_str, "%Y-%m-%d %H:%M:%S")
            age_hours = (datetime.datetime.utcnow() - cached_dt).total_seconds() / 3600.0
            if age_hours < CACHE_TTL_HOURS:
                logger.info(f"[GoogleTrends] Cache hit for '{keyword}' ({timeframe})")
                return json.loads(raw_json)
    except Exception as e:
        logger.debug(f"[GoogleTrends] Cache read error: {e}")
    return None


def _save_cached_trends(keyword: str, timeframe: str, data: dict):
    """Store trends data into SQLite cache."""
    try:
        _init_trends_cache()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO trends_cache (keyword, timeframe, response_json, cached_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(keyword) DO UPDATE SET
                timeframe = excluded.timeframe,
                response_json = excluded.response_json,
                cached_at = excluded.cached_at
            """,
            (keyword.lower().strip(), timeframe, json.dumps(data))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[GoogleTrends] Cache write error: {e}")


def extract_keywords(idea: str, max_keywords: int = 3) -> List[str]:
    """Extract 2-4 clean, searchable keywords from the startup idea."""
    stop_words = {
        "a", "an", "the", "and", "or", "for", "with", "in", "on", "at", "to", "of", "is",
        "app", "platform", "ai", "powered", "based", "tool", "saas", "startup", "solution",
        "market", "smart", "system", "using", "that", "helps", "users", "build"
    }
    words = [w.strip(".,!?\"'()[]") for w in idea.lower().split() if len(w) > 2]
    filtered = [w for w in words if w not in stop_words]
    
    if len(filtered) >= 2:
        return filtered[:max_keywords]
    return [idea[:25].strip()]


def calculate_direction(series: List[int]) -> str:
    """
    Calculate trend direction from series points using linear regression slope.
    Returns: 'growing', 'flat', or 'declining'.
    """
    if not series or len(series) < 2:
        return "flat"

    n = len(series)
    x = list(range(n))
    y = series

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
    denominator = sum((x[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return "flat"

    slope = numerator / denominator
    if slope > 0.15:
        return "growing"
    elif slope < -0.15:
        return "declining"
    return "flat"


def fetch_google_trends(idea: str) -> Dict[str, Any]:
    """
    Fetch Google Trends data via pytrends with 24h caching and 429 backoff.
    Never synthesizes fake numbers.
    """
    keywords = extract_keywords(idea, max_keywords=3)
    if not keywords:
        return {
            "status": "failed",
            "reason": "Could not extract searchable keywords from idea.",
            "data": None,
        }

    cache_key = "+".join(sorted(keywords))
    cached = _get_cached_trends(cache_key, "12m_and_5y")
    if cached:
        return {
            "status": "ok",
            "reason": None,
            "data": cached,
        }

    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))

        # 1. 12 months interest over time
        pytrends.build_payload(kw_list=keywords[:3], timeframe="today 12-m", geo="")
        df_12m = pytrends.interest_over_time()

        series_data = {}
        directions = {}

        if not df_12m.empty:
            for kw in keywords[:3]:
                if kw in df_12m.columns:
                    points = [int(v) for v in df_12m[kw].tolist()][-12:]  # last 12 points
                    series_data[kw] = points
                    directions[kw] = calculate_direction(points)

        # 2. Related / Rising Queries
        rising_queries = {}
        try:
            time.sleep(1.0)  # brief polite delay to reduce 429
            rel = pytrends.related_queries()
            for kw in keywords[:3]:
                if kw in rel and rel[kw].get("rising") is not None:
                    rising_df = rel[kw]["rising"]
                    if not rising_df.empty:
                        rising_queries[kw] = rising_df["query"].head(5).tolist()
        except Exception as rel_err:
            logger.debug(f"[GoogleTrends] Related queries fetch skipped: {rel_err}")

        # Overall trend direction
        all_dirs = list(directions.values())
        if "growing" in all_dirs:
            overall_direction = "growing"
        elif "declining" in all_dirs and "growing" not in all_dirs:
            overall_direction = "declining"
        else:
            overall_direction = "flat"

        result_payload = {
            "keywords": keywords[:3],
            "direction": overall_direction,
            "series_12m": series_data,
            "directions_by_keyword": directions,
            "rising_queries": rising_queries,
            "retrieved_at": datetime.datetime.utcnow().isoformat(),
            "source": "google_trends_pytrends",
        }

        # Cache valid result
        _save_cached_trends(cache_key, "12m_and_5y", result_payload)

        return {
            "status": "ok",
            "reason": None,
            "data": result_payload,
        }

    except Exception as e:
        err_msg = str(e)
        logger.warning(f"[GoogleTrends] Request failed: {err_msg}")
        if "429" in err_msg or "too many requests" in err_msg.lower():
            return {
                "status": "failed",
                "reason": "Google Trends rate limit encountered (HTTP 429). pytrends uses unofficial endpoints subject to Google quotas.",
                "data": None,
            }
        return {
            "status": "failed",
            "reason": f"Google Trends query failed: {err_msg}",
            "data": None,
        }
