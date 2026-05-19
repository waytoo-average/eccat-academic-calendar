"""
scraper/fetch.py
Fetches raw text about the Egyptian academic calendar from multiple sources.

Long-term reliability strategy:
- Primary: DuckDuckGo search (no API key, no rate limits, finds current announcement
  regardless of which site published it this year)
- Secondary: Direct scrape of top Egyptian news sites that cover SCU announcements
- Tertiary: SCU/MHE official sites directly
- All fetches: SSL verify disabled (CI runner cert issues), 20s timeout, retries

This approach is year-agnostic: as long as someone publishes the SCU calendar
announcement online (which they always do), the scraper will find it.
"""
import time
import urllib.parse
import httpx
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en;q=0.9",
}

_CALENDAR_KEYWORDS_AR = [
    "العام الدراسي", "الفصل الدراسي", "بداية الدراسة", "نهاية الدراسة",
    "تقويم", "جدول الدراسة", "المجلس الأعلى للجامعات", "الدراسة الجامعية",
    "الفصل الأول", "الفصل الثاني", "سبتمبر", "أكتوبر", "فبراير",
]
_CALENDAR_KEYWORDS_EN = [
    "academic year", "semester", "first semester", "second semester",
    "start of study", "end of study", "supreme council of universities",
    "september", "october", "february",
]
_CALENDAR_KEYWORDS = _CALENDAR_KEYWORDS_AR + _CALENDAR_KEYWORDS_EN


def _is_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in _CALENDAR_KEYWORDS)


def _fetch_url(url: str, timeout: int = 20, retries: int = 2) -> str:
    """Fetch URL with retries, SSL disabled for CI compatibility."""
    for attempt in range(retries + 1):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                verify=False,
                headers=_HEADERS,
            ) as client:
                r = client.get(url)
                r.raise_for_status()
                return r.text
        except httpx.TimeoutException:
            if attempt < retries:
                print(f"  [fetch] timeout on {url}, retrying ({attempt+1}/{retries})...")
                time.sleep(3)
            else:
                print(f"  [fetch] timeout on {url} after {retries+1} attempts")
        except Exception as e:
            print(f"  [fetch] {url} — {type(e).__name__}: {e}")
            break
    return ""


def _extract_relevant_text(html: str, max_chunks: int = 12) -> str:
    """Extract relevant text chunks from HTML."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    # Remove nav, footer, scripts
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    chunks = []
    for tag in soup.find_all(["article", "p", "div", "li", "h1", "h2", "h3", "span"]):
        text = tag.get_text(" ", strip=True)
        if len(text) > 60 and _is_relevant(text) and text not in chunks:
            chunks.append(text)
        if len(chunks) >= max_chunks:
            break
    return "\n\n---\n\n".join(chunks)


def _build_search_query(year: int) -> str:
    """Build a search query for the given academic year announcement."""
    next_year = year + 1
    # Arabic query targeting SCU announcement
    return f"المجلس الأعلى للجامعات العام الدراسي {year} {next_year} بداية الدراسة"


def fetch_duckduckgo(year: int) -> str:
    """
    Search DuckDuckGo HTML for the academic calendar announcement.
    DuckDuckGo's HTML search requires no API key and works from CI runners.
    This is year-agnostic: it searches for the current year's announcement
    regardless of which news site covered it.
    """
    print("  Trying DuckDuckGo search...")
    query = _build_search_query(year)
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    html = _fetch_url(url, timeout=25)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    # Extract snippets from search results
    chunks = []
    for result in soup.select(".result__snippet, .result__title, .result__url"):
        text = result.get_text(" ", strip=True)
        if len(text) > 40:
            chunks.append(text)
    # Also grab the article URLs and fetch the top 2
    article_urls = []
    for a in soup.select(".result__title a")[:3]:
        href = a.get("href", "")
        if href.startswith("http") and "duckduckgo" not in href:
            article_urls.append(href)

    text = "\n\n---\n\n".join(chunks)

    # Fetch up to 2 linked articles for richer content
    for article_url in article_urls[:2]:
        print(f"    Fetching article: {article_url[:60]}...")
        article_html = _fetch_url(article_url, timeout=20)
        article_text = _extract_relevant_text(article_html, max_chunks=8)
        if article_text:
            text += f"\n\n=== SOURCE: {article_url} ===\n\n{article_text}"

    return text


def fetch_youm7(year: int) -> str:
    """Search Youm7 — reliable Egyptian news site covering SCU announcements."""
    print("  Trying Youm7...")
    next_year = year + 1
    query = f"العام الدراسي {year} {next_year}"
    url = f"https://www.youm7.com/search/?q={urllib.parse.quote(query)}"
    html = _fetch_url(url)
    return _extract_relevant_text(html)


def fetch_masrawy(year: int) -> str:
    """Search Masrawy — another reliable Egyptian news aggregator."""
    print("  Trying Masrawy...")
    next_year = year + 1
    query = f"العام الدراسي {year} {next_year}"
    url = f"https://www.masrawy.com/search?q={urllib.parse.quote(query)}"
    html = _fetch_url(url)
    return _extract_relevant_text(html)


def fetch_scu_direct() -> str:
    """Fetch SCU news page directly."""
    print("  Trying SCU direct (scu.eg)...")
    html = _fetch_url("https://scu.eg/ar/news/", timeout=30)
    if not html:
        html = _fetch_url("https://scu.eg/en/news/", timeout=30)
    return _extract_relevant_text(html)


def fetch_mhe() -> str:
    """Fetch Ministry of Higher Education news."""
    print("  Trying MHE (mhe.gov.eg)...")
    html = _fetch_url("https://mhe.gov.eg/ar/News", timeout=25)
    return _extract_relevant_text(html)


def fetch_all(year: int) -> dict[str, str]:
    """
    Fetch from all sources in priority order.
    Stops once 2 sources with sufficient content are found.
    Year-agnostic: always searches for the announcement of the given year.
    """
    sources = [
        ("duckduckgo", lambda: fetch_duckduckgo(year)),
        ("youm7",      lambda: fetch_youm7(year)),
        ("masrawy",    lambda: fetch_masrawy(year)),
        ("mhe",        lambda: fetch_mhe()),
        ("scu",        lambda: fetch_scu_direct()),
    ]

    results = {}
    for name, fn in sources:
        try:
            text = fn()
            if text and len(text) > 150:
                results[name] = text
                print(f"  ✅ Got {len(text)} chars from {name}")
                if len(results) >= 2:
                    break
            else:
                print(f"  ⚠️  {name} returned no relevant content")
        except Exception as e:
            print(f"  ❌ {name} error: {e}")

    return results
