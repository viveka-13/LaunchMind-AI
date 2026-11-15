# agent/research_filter.py
# Relevance scoring, deduplication, spam filtering, and recency checks for research results

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import List, Dict, Any, Tuple, Optional


TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "ref", "source", "ref_src", "mc_cid", "mc_eid"
}

BLACKLISTED_DOMAINS = {
    "cleartax.in", "incometax.gov.in", "quickitr.com", "tax2win.in",
    "indeed.com", "glassdoor.com", "ziprecruiter.com", "naukri.com",
    "monster.com", "simplyhired.com"
}

OFF_TOPIC_KEYWORDS = [
    "income tax return", "itr filing", "tax refund", "file itr", "itr-1", "itr-2",
    "tds return", "income tax department", "e-filing portal", "tax deduction",
]

GENERIC_AI_LISTICLE_PATTERNS = [
    r"forbes\s+.*ai\s+50",
    r"top\s+50\s+ai\s+companies",
    r"top\s+100\s+ai\s+startups",
]


def normalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, trailing slashes, and protocol casing."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        
        # Clean query parameters
        query_dict = parse_qs(parsed.query, keep_blank_values=False)
        cleaned_query = {k: v for k, v in query_dict.items() if k.lower() not in TRACKING_PARAMS}
        new_query = urlencode(cleaned_query, doseq=True)
        
        # Clean path
        path = parsed.path.rstrip("/")
        if not path:
            path = "/"
            
        return urlunparse((scheme, netloc, path, parsed.params, new_query, ""))
    except Exception:
        return url.strip().rstrip("/")


def extract_domain(url: str) -> str:
    """Extract clean domain name from URL."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return "web"


def _tokenize(text: str) -> set[str]:
    """Tokenize lowercase alphanumeric tokens > 2 chars."""
    if not text:
        return set()
    words = re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower())
    # Exclude ultra-generic stopwords
    stopwords = {
        "and", "the", "for", "with", "that", "this", "from", "are", "have", "has",
        "was", "were", "what", "which", "will", "would", "about", "into", "more"
    }
    return {w for w in words if w not in stopwords}


def title_similarity(t1: str, t2: str) -> float:
    """Jaccard similarity between two titles."""
    tokens1 = _tokenize(t1)
    tokens2 = _tokenize(t2)
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    return len(intersection) / len(union) if union else 0.0


def is_blacklisted_or_spam(url: str, title: str, snippet: str, category_tokens: set[str]) -> Tuple[bool, str]:
    """Check if result is blacklisted domain, tax filing, job board, or off-topic listicle."""
    domain = extract_domain(url)
    for bad_domain in BLACKLISTED_DOMAINS:
        if bad_domain in domain:
            return True, f"blacklisted domain: {domain}"

    combined_text = f"{title} {snippet}".lower()

    # Tax filing check
    for kw in OFF_TOPIC_KEYWORDS:
        if kw in combined_text:
            return True, f"tax filing / government off-topic: '{kw}'"

    # Job board / recruitment URLs
    if "/jobs/" in url.lower() or "/careers/" in url.lower() or "job-opening" in url.lower():
        return True, "job board / career page"

    # Generic AI listicles (e.g. Forbes AI 50) that do not mention the target vertical
    for pat in GENERIC_AI_LISTICLE_PATTERNS:
        if re.search(pat, combined_text):
            # If the listicle doesn't mention any key category token, drop it
            overlap = _tokenize(combined_text) & category_tokens
            if len(overlap) < 2:
                return True, "generic AI listicle without vertical relevance"

    # Login / Sign up portals
    if any(p in url.lower() for p in ("/login", "/signin", "/signup", "/auth/login")):
        return True, "login / account portal"

    return False, ""


def is_stale_result(snippet: str, url: str) -> bool:
    """
    Check if result is strictly dated before 2023 without any mention of 2023-2027.
    """
    text = f"{url} {snippet}"
    recent_years = {"2023", "2024", "2025", "2026", "2027"}
    old_years = {"2015", "2016", "2017", "2018", "2019", "2020", "2021", "2022"}

    found_recent = any(y in text for y in recent_years)
    found_old = any(y in text for y in old_years)

    if found_old and not found_recent:
        # Check if URL explicitly contains an old year in path like /2019/04/
        if re.search(r"/(?:201[5-9]|202[0-2])/", url):
            return True
    return False


def score_relevance(
    title: str,
    snippet: str,
    category_tokens: set[str],
    domain_tokens: set[str],
    target_customer_tokens: set[str]
) -> float:
    """
    Calculate relevance score for a search result snippet (0.0 to 10.0 scale).
    Higher weight given to category and domain matches in title.
    """
    title_toks = _tokenize(title)
    snippet_toks = _tokenize(snippet)
    all_toks = title_toks | snippet_toks

    score = 0.0

    # Matches in title (weight = 2.5 per category match)
    cat_title_matches = len(title_toks & category_tokens)
    score += cat_title_matches * 2.5

    # Matches in snippet (weight = 1.0 per category match)
    cat_snippet_matches = len(snippet_toks & category_tokens)
    score += cat_snippet_matches * 1.0

    # Domain / problem matches
    dom_matches = len(all_toks & domain_tokens)
    score += dom_matches * 0.8

    # Customer matches
    cust_matches = len(all_toks & target_customer_tokens)
    score += cust_matches * 0.6

    # Market data signal bonus (numbers, $, %, CAGR, market size, valuation, growth)
    if re.search(r"\$\s*\d+|\b\d+(?:\.\d+)?\s*(?:billion|million|trillion|b|m|%)\b|\bcagr\b|\bmarket size\b|\bvaluation\b", snippet.lower()):
        score += 1.5

    return round(score, 2)


def filter_and_rank_results(
    raw_results: List[Dict[str, Any]],
    understanding: Dict[str, Any],
    max_keep: int = 10
) -> Tuple[List[Dict[str, Any]], bool, List[str]]:
    """
    De-duplicates, filters out spam/stale/off-topic results, scores relevance,
    and returns top results along with thin data flag and data gaps list.
    """
    category = understanding.get("category", "")
    problem_domain = understanding.get("problem_domain", "")
    target_customers = understanding.get("target_customers", [])
    
    category_tokens = _tokenize(category)
    domain_tokens = _tokenize(problem_domain)
    cust_tokens = set()
    for c in target_customers:
        cust_tokens |= _tokenize(str(c))

    seen_urls = set()
    kept_items = []

    for item in raw_results:
        url = item.get("url", "") or item.get("href", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "") or item.get("body", "") or item.get("summary", "")
        query = item.get("query", "")

        if not title and not snippet:
            continue

        norm_url = normalize_url(url)
        if norm_url in seen_urls:
            continue

        # Check title similarity against existing items
        is_dup_title = False
        for kept in kept_items:
            if title_similarity(title, kept["title"]) > 0.8:
                is_dup_title = True
                break
        if is_dup_title:
            continue

        # Check blacklist / spam
        is_spam, reason = is_blacklisted_or_spam(url, title, snippet, category_tokens)
        if is_spam:
            continue

        # Check staleness
        if is_stale_result(snippet, url):
            continue

        # Compute relevance score
        score = score_relevance(title, snippet, category_tokens, domain_tokens, cust_tokens)
        
        # Must have at least minimal relevance (> 0.5)
        if score < 0.5:
            continue

        seen_urls.add(norm_url)
        kept_items.append({
            "query": query,
            "source": extract_domain(url),
            "title": title,
            "snippet": snippet,
            "url": url,
            "score": score,
        })

    # Sort descending by relevance score
    kept_items.sort(key=lambda x: x["score"], reverse=True)
    final_results = kept_items[:max_keep]

    is_thin = len(final_results) < 2
    data_gaps = []
    if is_thin:
        cat_name = category or "this specific vertical"
        data_gaps.append(
            f"Limited empirical search data found for '{cat_name}'. Later nodes will extrapolate using industry-standard SaaS benchmarks rather than ungrounded claims."
        )

    return final_results, is_thin, data_gaps

