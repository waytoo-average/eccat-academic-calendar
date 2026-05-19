"""
scraper/fetch.py
Fetches raw HTML/text from SCU and Al-Ahram for the academic calendar announcement.
"""
import httpx
from bs4 import BeautifulSoup

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; eccat-calendar-bot/1.0)"}


def fetch_scu_news() -> str:
    """Fetch SCU news page and return text of calendar-related articles."""
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get("https://scu.eg/en/news/", headers=_HEADERS)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        articles = []
        for tag in soup.find_all(["article", "div", "li", "p"]):
            text = tag.get_text(" ", strip=True)
            if len(text) > 80 and any(
                t in text.lower()
                for t in ["academic year", "semester", "timetable", "الجدول", "الفصل"]
            ):
                articles.append(text)
        return "\n\n---\n\n".join(articles[:8])
    except Exception as e:
        print(f"[fetch_scu_news] failed: {e}")
        return ""


def fetch_ahram(year: int) -> str:
    """Fetch Al-Ahram English search results for the current year's academic calendar."""
    url = f"https://english.ahram.org.eg/News/Search/?q=universities+academic+year+{year}"
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            r = client.get(url, headers=_HEADERS)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for tag in soup.select(".news-list-item, .article-summary, h3, p")[:10]:
            text = tag.get_text(" ", strip=True)
            if len(text) > 60:
                items.append(text)
        return "\n\n---\n\n".join(items)
    except Exception as e:
        print(f"[fetch_ahram] failed: {e}")
        return ""


def fetch_all(year: int) -> dict[str, str]:
    """Fetch from all sources and return a dict {source_name: text}."""
    results = {}
    scu = fetch_scu_news()
    if scu:
        results["scu"] = scu
    ahram = fetch_ahram(year)
    if ahram:
        results["ahram"] = ahram
    return results
