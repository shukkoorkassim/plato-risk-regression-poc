"""
agent/confluence_source.py — pull Flow 2's requirement changes LIVE from Confluence.

Reads a Confluence page that contains a "requirement changes" table (rows keyed
REQ-###) and returns them normalized like the CSV loader:

    {id, component, type="requirement", summary, source="requirement change"}

Environment (reuses the Atlassian credentials):
    ATLASSIAN_SITE=your-site.atlassian.net
    ATLASSIAN_EMAIL=you@example.com
    ATLASSIAN_TOKEN=ATATT...
    CONFLUENCE_PAGE_ID=1572866            # the page holding the REQ table (preferred)
      -- or --
    CONFLUENCE_SPACE_KEY=PM               # + title, to look the page up by name
    CONFLUENCE_PAGE_TITLE=Risk-Based Regression POC — Release Requirements & Overview

Any table row whose first cell looks like REQ-123 is treated as a requirement:
    | REQ-411 | payments | Tax must be charged on the discounted subtotal | 2026-08-20 |
      key        comp       summary                                        (ignored)
"""

import os
import re

from .common import load_dotenv

KNOWN_COMPONENTS = {"login", "inventory", "cart", "checkout", "search", "payments"}
_REQ_RE = re.compile(r"^REQ-\d+", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_ROW_RE = re.compile(r"<tr\b.*?</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<t[dh]\b.*?</t[dh]>", re.IGNORECASE | re.DOTALL)


def _cfg():
    load_dotenv()
    return {
        "site": os.environ.get("ATLASSIAN_SITE", "").strip().replace("https://", "").rstrip("/"),
        "email": os.environ.get("ATLASSIAN_EMAIL", "").strip(),
        "token": os.environ.get("ATLASSIAN_TOKEN", "").strip(),
        "page_id": os.environ.get("CONFLUENCE_PAGE_ID", "").strip(),
        "space": os.environ.get("CONFLUENCE_SPACE_KEY", "").strip(),
        "title": os.environ.get("CONFLUENCE_PAGE_TITLE", "").strip(),
    }


def confluence_configured():
    load_dotenv()
    c = _cfg()
    return bool(c["site"] and c["email"] and c["token"] and (c["page_id"] or (c["space"] and c["title"])))


def _text(html_fragment):
    return _TAG_RE.sub("", html_fragment).replace("&amp;", "&").replace("&#039;", "'").strip()


def parse_requirements(html):
    """Extract REQ-### rows from a Confluence page's HTML/storage body."""
    out = []
    for row in _ROW_RE.findall(html or ""):
        cells = [_text(c) for c in _CELL_RE.findall(row)]
        if len(cells) >= 3 and _REQ_RE.match(cells[0]):
            comp = cells[1].strip().lower()
            if comp not in KNOWN_COMPONENTS:
                comp = "unknown"
            out.append({
                "id": cells[0].strip(),
                "component": comp,
                "type": "requirement",
                "summary": cells[2].strip(),
                "source": "requirement change",
            })
    return out


def _fetch_page_html(c):
    import requests
    auth = (c["email"], c["token"])
    base = f"https://{c['site']}/wiki/rest/api"
    if c["page_id"]:
        r = requests.get(f"{base}/content/{c['page_id']}",
                         params={"expand": "body.storage"}, auth=auth, timeout=30)
        r.raise_for_status()
        return r.json().get("body", {}).get("storage", {}).get("value", "")
    # look up by space + title
    r = requests.get(f"{base}/content",
                     params={"spaceKey": c["space"], "title": c["title"],
                             "expand": "body.storage", "limit": 1},
                     auth=auth, timeout=30)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return ""
    return results[0].get("body", {}).get("storage", {}).get("value", "")


def load_requirements_live():
    """Fetch the Confluence page and return its requirement rows. Requires `requests`."""
    c = _cfg()
    if not (c["site"] and c["email"] and c["token"] and (c["page_id"] or (c["space"] and c["title"]))):
        return []
    try:
        import requests  # noqa: F401
    except ImportError:
        raise RuntimeError("live Confluence needs the 'requests' package — pip install requests")
    return parse_requirements(_fetch_page_html(c))
