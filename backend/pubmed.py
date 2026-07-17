"""
AI-Medikelizar — PubMed API Integration
=========================================
Uses NCBI E-utilities (ESearch + EFetch) to search and retrieve
article metadata from PubMed / MEDLINE.

Usage:
    results = await search_pubmed("hypertension JNC 8 guidelines")
"""

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional
import httpx

from .config import PUBMED_API_KEY, PUBMED_EMAIL, PUBMED_TOOL, MAX_SOURCES

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
RATE_LIMIT = 10 if PUBMED_API_KEY else 3  # requests per second

# ── Simple rate-limiter ────────────────────────────────
_last_call = 0.0
_rate_lock = asyncio.Lock()


async def _rate_limited():
    global _last_call
    interval = 1.0 / RATE_LIMIT
    async with _rate_lock:
        now = time.monotonic()
        wait = interval - (now - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()


async def search_pubmed(query: str, retmax: int = None) -> list[dict]:
    """
    Search PubMed and return article metadata.

    1. ESearch to get PMIDs matching the query.
    2. EFetch to retrieve full article details in XML.
    3. Parse XML into structured dicts.

    Returns a list of dicts with keys:
        id, title, authors, journal, date, volume, doi, pmid, url,
        abstract, publisher, relevance
    """
    if retmax is None:
        retmax = MAX_SOURCES

    await _rate_limited()

    # ── Step 1: ESearch ────────────────────────────────
    esearch_params = {
        "db": "pubmed",
        "term": _build_search_term(query),
        "retmax": str(retmax * 2),  # fetch more than needed for filtering
        "retmode": "json",
        "sort": "relevance",
        "tool": PUBMED_TOOL,
        "email": PUBMED_EMAIL,
    }
    if PUBMED_API_KEY:
        esearch_params["api_key"] = PUBMED_API_KEY

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{BASE_URL}/esearch.fcgi",
                                params=esearch_params)
        resp.raise_for_status()
        data = resp.json()

    id_list = data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return []

    # Take only what we need
    pmids = id_list[:retmax]

    # ── Step 2: EFetch ─────────────────────────────────
    await _rate_limited()

    efetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "xml",
        "tool": PUBMED_TOOL,
        "email": PUBMED_EMAIL,
    }
    if PUBMED_API_KEY:
        efetch_params["api_key"] = PUBMED_API_KEY

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{BASE_URL}/efetch.fcgi",
                                params=efetch_params)
        resp.raise_for_status()
        xml_text = resp.text

    # ── Step 3: Parse XML ──────────────────────────────
    return _parse_pubmed_xml(xml_text)


def _build_search_term(query: str) -> str:
    """Build a PubMed-optimised search term from a natural language query.

    Strips stopwords, adds field qualifiers for best results.
    """
    # Simple heuristic: use the query as-is but wrap in quotes for phrases
    # and add date filter for recent results
    clean = re.sub(r"[^\w\s]", " ", query).strip()
    words = clean.split()

    # If query is long, treat it as a broad search
    if len(words) > 8:
        # Take key terms (skip very common words)
        stopwords = {"what", "is", "the", "are", "of", "in", "for", "to",
                     "and", "with", "from", "does", "how", "can", "a", "an",
                     "do", "or", "by", "on", "at", "be", "this", "that"}
        key_terms = [w for w in words if w.lower() not in stopwords]
        term = " AND ".join(key_terms[:8])
    else:
        term = " AND ".join(words)

    # Add date range for recent evidence (last 10 years)
    term += ' AND ("2014"[Date - Publication] : "3000"[Date - Publication])'

    return term


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    """Parse PubMed EFetch XML into structured article dicts."""
    import logging
    log = logging.getLogger("ai-medikelizar.pubmed")
    articles = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.error(f"XML ParseError: {e}")
        log.debug(f"XML preview: {xml_text[:500]}")
        return []

    articles_found = root.findall(".//PubmedArticle")
    log.debug(f"Found {len(articles_found)} PubmedArticle elements")

    for i, article_elem in enumerate(articles_found, start=1):
        try:
            # Use direct child find (no .// prefix) for better compatibility
            medline = None
            for child in article_elem:
                if child.tag == "MedlineCitation":
                    medline = child
                    break
            if medline is None:
                # Fallback: try XPath with namespace-agnostic search
                medline = article_elem.find(".//MedlineCitation")
            if medline is None:
                log.debug(f"Article {i}: No MedlineCitation found")
                continue

            article = None
            for child in medline:
                if child.tag == "Article":
                    article = child
                    break
            if article is None:
                article = medline.find("Article")
            if article is None:
                log.debug(f"Article {i}: No Article found in MedlineCitation")
                continue

            # ── Title ──
            title_el = article.find("ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else ""

            # ── Authors ──
            authors = []
            author_list = article.find("AuthorList")
            if author_list is not None:
                for au in author_list.findall("Author"):
                    last = au.find("LastName")
                    fore = au.find("ForeName")
                    if last is not None:
                        name = last.text or ""
                        if fore is not None:
                            name += f" {fore.text or ''}"
                        authors.append(name.strip())
                        if len(authors) >= 6:
                            authors.append("et al.")
                            break
            author_str = ", ".join(authors) if authors else ""

            # ── Journal ──
            journal_el = article.find("Journal")
            journal = ""
            if journal_el is not None:
                jtitle = journal_el.find("Title")
                if jtitle is not None:
                    journal = jtitle.text or ""
                iso = journal_el.find("ISOAbbreviation")
                if iso is not None and iso.text:
                    journal = iso.text

            # ── Date ──
            date_str = ""
            if journal_el is not None:
                ji = journal_el.find("JournalIssue")
                if ji is not None:
                    pubdate = ji.find("PubDate")
                    if pubdate is not None:
                        year = pubdate.find("Year")
                        month = pubdate.find("Month")
                        day = pubdate.find("Day")
                        parts = []
                        if year is not None:
                            parts.append(year.text or "")
                        if month is not None:
                            m = month.text or ""
                            # NCBI sometimes returns month names
                            if len(m) <= 3 and m.isdigit():
                                parts.append(m.zfill(2))
                            else:
                                parts.append(m)
                        if day is not None:
                            parts.append((day.text or "").zfill(2))
                        date_str = "-".join(parts) if parts else ""

            # ── Volume / Issue / Pages ──
            volume = ""
            if journal_el is not None:
                ji = journal_el.find("JournalIssue")
                if ji is not None:
                    vol = ji.find("Volume")
                    if vol is not None:
                        volume = vol.text or ""
                        issue = ji.find("Issue")
                        if issue is not None:
                            volume += f"({issue.text or ''})"
                        pagination = article.find("Pagination")
                        if pagination is not None:
                            pages = pagination.find("MedlinePgn")
                            if pages is not None:
                                volume += f":{pages.text or ''}"

            # ── PMID ──
            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # ── DOI ──
            doi = ""
            for eid in article_elem.findall(".//ArticleId"):
                if eid.get("IdType") == "doi":
                    doi = eid.text or ""
                    break

            # ── Abstract ──
            abstract_parts = []
            abstract_elem = article.find("Abstract")
            if abstract_elem is not None:
                for at in abstract_elem.findall("AbstractText"):
                    label = at.get("Label", "")
                    text = "".join(at.itertext()).strip()
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
            abstract = " ".join(abstract_parts) if abstract_parts else ""

            # ── URL ──
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

            # ── Publisher ──
            publisher = ""
            if journal_el is not None:
                pub_el = journal_el.find("PublisherName") or \
                         journal_el.find(".//Publisher/PublisherName")
                if pub_el is not None:
                    publisher = pub_el.text or ""

            articles.append({
                "id": i,
                "title": title,
                "authors": author_str,
                "journal": journal,
                "date": date_str,
                "volume": volume,
                "doi": doi,
                "pmid": pmid,
                "url": url,
                "abstract": abstract,
                "publisher": publisher,
                "relevance": max(0.7, 1.0 - (i - 1) * 0.08),  # decaying relevance
            })

        except Exception:
            continue  # skip malformed entries

    return articles
