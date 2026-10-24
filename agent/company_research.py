# agent/company_research.py
# Real company research via Crunchbase, SEC EDGAR, and Wikidata/Wikipedia

import os
import json
import logging
import datetime
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "LaunchMindAI/1.0 (contact@launchmind.ai)")


class CompanyResearchProvider:
    """Base provider interface for company research."""
    def search_company(self, query: str) -> Dict[str, Any]:
        raise NotImplementedError


class CrunchbaseProvider(CompanyResearchProvider):
    """
    Crunchbase Enterprise/Basic API.
    Note: Crunchbase API requires a paid enterprise key.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("CRUNCHBASE_API_KEY")

    def search_company(self, query: str) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "skipped",
                "reason": "CRUNCHBASE_API_KEY not configured (paid Crunchbase API access required).",
                "data": None,
            }

        try:
            # Query Crunchbase entities API
            url = f"https://api.crunchbase.com/api/v4/entities/organizations/{query.lower().strip()}"
            params = {
                "user_key": self.api_key,
                "card_ids": "fields,funding_rounds,investors,headquarters_address",
            }
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 404:
                return {
                    "status": "ok",
                    "reason": f"No Crunchbase record found for '{query}'",
                    "data": None,
                }
            resp.raise_for_status()
            raw = resp.json()

            properties = raw.get("properties", {})
            return {
                "status": "ok",
                "reason": None,
                "data": {
                    "name": properties.get("name", query),
                    "source": "crunchbase",
                    "retrieved_at": datetime.datetime.utcnow().isoformat(),
                    "total_funding_usd": properties.get("funding_total", {}).get("value_usd"),
                    "num_funding_rounds": properties.get("num_funding_rounds"),
                    "headquarters": properties.get("headquarters_address"),
                    "employee_range": properties.get("num_employees_enum"),
                    "description": properties.get("short_description"),
                },
            }
        except Exception as e:
            logger.warning(f"[Crunchbase] Lookup failed: {e}")
            return {
                "status": "failed",
                "reason": f"Crunchbase request failed: {e}",
                "data": None,
            }


class SecEdgarProvider(CompanyResearchProvider):
    """
    Free public company research via SEC EDGAR.
    Requires a descriptive User-Agent complying with SEC fair-access policy.
    """
    def search_company(self, query: str) -> Dict[str, Any]:
        try:
            headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
            # Fetch company tickers mapping
            tickers_url = "https://www.sec.gov/files/company_tickers.json"
            resp = requests.get(tickers_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                return {
                    "status": "failed",
                    "reason": f"SEC EDGAR tickers endpoint returned HTTP {resp.status_code}",
                    "data": None,
                }
            
            tickers_data = resp.json()
            norm_query = query.lower().strip()

            matched_entry = None
            matches = 0
            for idx, entry in tickers_data.items():
                title = entry.get("title", "").lower()
                ticker = entry.get("ticker", "").lower()
                if norm_query == ticker or norm_query == title or norm_query in title:
                    matches += 1
                    matched_entry = entry

            # Entity resolution: if ambiguous or not found, return clean status
            if matches == 0:
                return {
                    "status": "ok",
                    "reason": f"No public SEC EDGAR company found for '{query}'",
                    "data": None,
                }
            if matches > 5:
                return {
                    "status": "ok",
                    "reason": f"Ambiguous match on SEC EDGAR ({matches} companies found for '{query}')",
                    "data": None,
                }

            cik = str(matched_entry["cik_str"]).zfill(10)
            sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            sub_resp = requests.get(sub_url, headers=headers, timeout=10)
            if sub_resp.status_code != 200:
                return {
                    "status": "ok",
                    "reason": f"Found ticker {matched_entry.get('ticker')} but could not fetch submissions",
                    "data": {
                        "name": matched_entry.get("title"),
                        "ticker": matched_entry.get("ticker"),
                        "cik": cik,
                        "source": "sec_edgar",
                        "retrieved_at": datetime.datetime.utcnow().isoformat(),
                    },
                }

            sub_data = sub_resp.json()
            return {
                "status": "ok",
                "reason": None,
                "data": {
                    "name": sub_data.get("name"),
                    "ticker": matched_entry.get("ticker"),
                    "cik": cik,
                    "entity_type": sub_data.get("entityType"),
                    "sic_description": sub_data.get("sicDescription"),
                    "fiscal_year_end": sub_data.get("fiscalYearEnd"),
                    "state_of_incorporation": sub_data.get("stateOfIncorporation"),
                    "source": "sec_edgar",
                    "retrieved_at": datetime.datetime.utcnow().isoformat(),
                },
            }
        except Exception as e:
            logger.warning(f"[SEC EDGAR] Lookup failed: {e}")
            return {
                "status": "failed",
                "reason": f"SEC EDGAR request error: {e}",
                "data": None,
            }


class WikidataProvider(CompanyResearchProvider):
    """
    Free company facts via Wikidata and Wikipedia API.
    """
    def search_company(self, query: str) -> Dict[str, Any]:
        try:
            # 1. Search Wikidata entities
            search_url = "https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "format": "json",
                "limit": 5,
            }
            headers = {"User-Agent": "LaunchMindAI/1.0 (contact@launchmind.ai)"}
            resp = requests.get(search_url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                return {
                    "status": "failed",
                    "reason": f"Wikidata search returned HTTP {resp.status_code}",
                    "data": None,
                }

            results = resp.json().get("search", [])
            if not results:
                return {
                    "status": "ok",
                    "reason": f"No Wikidata entry found for '{query}'",
                    "data": None,
                }

            # Filter for business / company / enterprise in description
            candidate = None
            for item in results:
                desc = (item.get("description") or "").lower()
                if any(w in desc for w in ("company", "corporation", "business", "startup", "technology", "firm", "enterprise", "software")):
                    candidate = item
                    break

            if not candidate:
                candidate = results[0]

            entity_id = candidate.get("id")
            label = candidate.get("label")
            description = candidate.get("description")

            # 2. Wikipedia summary for rich overview
            wiki_summary = ""
            try:
                wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{label.replace(' ', '_')}"
                wiki_resp = requests.get(wiki_url, headers=headers, timeout=5)
                if wiki_resp.status_code == 200:
                    wiki_summary = wiki_resp.json().get("extract", "")
            except Exception:
                pass

            return {
                "status": "ok",
                "reason": None,
                "data": {
                    "name": label,
                    "wikidata_id": entity_id,
                    "description": description,
                    "summary": wiki_summary,
                    "source": "wikidata_wikipedia",
                    "retrieved_at": datetime.datetime.utcnow().isoformat(),
                },
            }
        except Exception as e:
            logger.warning(f"[Wikidata] Lookup failed: {e}")
            return {
                "status": "failed",
                "reason": f"Wikidata request error: {e}",
                "data": None,
            }


def fetch_company_research(company_or_idea: str) -> Dict[str, Any]:
    """
    Orchestrate company research:
    1. Try Crunchbase if key is present.
    2. Fall back to free SEC EDGAR and Wikidata/Wikipedia.
    Returns honest status object.
    """
    # 1. Crunchbase
    cb_key = os.environ.get("CRUNCHBASE_API_KEY")
    if cb_key:
        cb_provider = CrunchbaseProvider(cb_key)
        res = cb_provider.search_company(company_or_idea)
        if res.get("status") == "ok" and res.get("data"):
            return res

    # 2. SEC EDGAR (for public companies)
    edgar = SecEdgarProvider()
    edgar_res = edgar.search_company(company_or_idea)
    if edgar_res.get("status") == "ok" and edgar_res.get("data"):
        return edgar_res

    # 3. Wikidata / Wikipedia (broad free factual knowledge)
    wiki = WikidataProvider()
    wiki_res = wiki.search_company(company_or_idea)
    if wiki_res.get("status") == "ok" and wiki_res.get("data"):
        return wiki_res

    # If no data found from free sources and crunchbase was skipped:
    if not cb_key:
        return {
            "status": "skipped",
            "reason": "CRUNCHBASE_API_KEY not configured; no public SEC EDGAR or Wikidata records matched query.",
            "data": None,
        }

    return {
        "status": "ok",
        "reason": f"No company data found across providers for '{company_or_idea}'",
        "data": None,
    }
