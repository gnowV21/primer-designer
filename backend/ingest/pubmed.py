"""
pubmed.py — fetch paper metadata + abstracts from PubMed E-utilities
[SPEC_Phase1 §3.1, §3.2].

Two calls per ingest run:
  1. esearch  — keyword query            -> list of PMIDs
  2. efetch   — PMIDs                    -> XML with title/authors/journal/year/abstract

Copyright [SPEC_Phase1 §3.3]: we store metadata + abstract + link only. Full text
is stored ONLY when the paper is open-access, which we detect from PubMed's own
PMC-availability signal. We never download publisher PDFs.
"""

import os
import re
import time
import xml.etree.ElementTree as ET

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# NCBI asks every client to identify itself; unidentified clients get throttled first.
#
# The address is read from the environment rather than hardcoded: it is personal data, and a
# repository is a bad place to keep it. Set NCBI_EMAIL in the deployment environment. NCBI only
# uses it to contact you if your client misbehaves, so the placeholder is safe for local use —
# but a lab running this against PubMed in earnest should set a real one.
TOOL_NAME = "primer-designer-phase1-chatbot"
EMAIL     = os.environ.get("NCBI_EMAIL", "hglab@hcmus.edu.vn")

# NCBI rate limit: 3 requests/sec without an API key. 0.4 s keeps us safely under.
# https://www.ncbi.nlm.nih.gov/books/NBK25497/
_RATE_DELAY = 0.4
_TIMEOUT    = 20

MAX_RESULTS = 100   # hard cap per ingest call — keeps one request bounded


def search_pmids(query: str, max_results: int = 20) -> list[str]:
    """esearch: keyword query -> PMIDs, most relevant first."""
    max_results = max(1, min(MAX_RESULTS, int(max_results)))

    r = requests.get(
        f"{EUTILS}/esearch.fcgi",
        params={
            "db":      "pubmed",
            "term":    query,
            "retmax":  max_results,
            "retmode": "json",
            "sort":    "relevance",
            "tool":    TOOL_NAME,
            "email":   EMAIL,
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("esearchresult", {}).get("idlist", [])


def fetch_papers(pmids: list[str]) -> list[dict]:
    """efetch: PMIDs -> parsed paper dicts. Returns [] for an empty input."""
    if not pmids:
        return []

    time.sleep(_RATE_DELAY)   # spacing between esearch and efetch

    r = requests.get(
        f"{EUTILS}/efetch.fcgi",
        params={
            "db":      "pubmed",
            "id":      ",".join(pmids),
            "retmode": "xml",
            "tool":    TOOL_NAME,
            "email":   EMAIL,
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()

    root = ET.fromstring(r.content)
    return [
        paper
        for article in root.findall(".//PubmedArticle")
        if (paper := _parse_article(article)) is not None
    ]


def _parse_article(article: ET.Element) -> dict | None:
    """Parse one <PubmedArticle>. Returns None if it has no PMID or no abstract."""
    pmid_el = article.find(".//PMID")
    if pmid_el is None or not (pmid_el.text or "").strip():
        return None
    pmid = pmid_el.text.strip()

    # Abstract: structured abstracts have several <AbstractText Label="METHODS">
    # sections. Concatenate them, keeping the labels — they carry real signal for
    # retrieval ("METHODS: ... stem-loop RT ...").
    parts = []
    for at in article.findall(".//Abstract/AbstractText"):
        text = "".join(at.itertext()).strip()
        if not text:
            continue
        label = at.get("Label")
        parts.append(f"{label}: {text}" if label else text)
    abstract = " ".join(parts).strip()

    # A paper with no abstract has nothing to embed and can never be cited with a
    # quote, so it is useless to the RAG brain. Skip it.
    if not abstract:
        return None

    title_el = article.find(".//ArticleTitle")
    title    = "".join(title_el.itertext()).strip() if title_el is not None else ""

    authors = []
    for a in article.findall(".//AuthorList/Author"):
        last = a.findtext("LastName")
        init = a.findtext("Initials")
        if last:
            authors.append(f"{last} {init}" if init else last)
        elif (coll := a.findtext("CollectiveName")):
            authors.append(coll)

    journal = (
        article.findtext(".//Journal/ISOAbbreviation")
        or article.findtext(".//Journal/Title")
        or ""
    )

    return {
        "pmid":           pmid,
        "title":          title,
        "authors":        authors,
        "journal":        journal.strip(),
        "year":           _parse_year(article),
        "abstract":       abstract,
        "url":            f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "is_open_access": _is_open_access(article),
        "full_text":      None,   # never populated from efetch [SPEC_Phase1 §3.3]
    }


def _parse_year(article: ET.Element) -> int | None:
    """Year from PubDate/Year, or the leading year of a MedlineDate ('2019-2020')."""
    if (y := article.findtext(".//Journal/JournalIssue/PubDate/Year")):
        try:
            return int(y)
        except ValueError:
            pass
    if (md := article.findtext(".//Journal/JournalIssue/PubDate/MedlineDate")):
        if (m := re.search(r"\b(\d{4})\b", md)):
            return int(m.group(1))
    return None


def _is_open_access(article: ET.Element) -> bool:
    """
    True when PubMed reports a PMC id for the article.

    A PMC deposit is a strong signal the full text is freely readable, but it is
    NOT proof of an open licence (some PMC records are author-manuscript,
    embargoed, or all-rights-reserved). This flag therefore only gates whether we
    are ALLOWED to consider storing full text later — we still store metadata +
    abstract + link only, so no full text is fetched in Phase 1 [SPEC_Phase1 §3.3].
    """
    return any(
        (aid.get("IdType") or "").lower() == "pmc"
        for aid in article.findall(".//ArticleIdList/ArticleId")
    )


def search_and_fetch(query: str, max_results: int = 20) -> list[dict]:
    """Convenience: esearch + efetch in one call."""
    return fetch_papers(search_pmids(query, max_results))
