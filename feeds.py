"""
무료로 열람 가능한 미국/영어권 뉴스 RSS 피드 목록.
전문(全文) 스크래핑은 하지 않고, 각 피드가 제공하는 제목 + 짧은 요약만 사용합니다.
(저작권/paywall 이슈를 피하기 위함)

새 피드를 추가하고 싶으면 아래 리스트에 {"name": ..., "url": ...} 형태로 추가하면 됩니다.
"""

import feedparser

FEEDS = [
    {"name": "New York Times - World", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "New York Times - Home", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
    {"name": "BBC News - World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "NPR - News", "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "The Guardian - World", "url": "https://www.theguardian.com/world/rss"},
    {"name": "CNBC - Top News", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
]

# 하루에 소스별로 최대 몇 개의 기사를 가져올지
MAX_PER_FEED = 3


def fetch_all_entries():
    """모든 피드를 돌면서 (source, title, url, summary, published) 튜플 리스트를 반환."""
    entries = []
    for feed in FEEDS:
        parsed = feedparser.parse(feed["url"])
        for entry in parsed.entries[:MAX_PER_FEED]:
            title = getattr(entry, "title", "").strip()
            url = getattr(entry, "link", "").strip()
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            published = getattr(entry, "published", None) or getattr(entry, "updated", None)

            if not title or not url:
                continue

            entries.append(
                {
                    "source": feed["name"],
                    "title": title,
                    "url": url,
                    "original_summary": _clean_html(summary),
                    "published": published,
                }
            )
    return entries


def _clean_html(raw: str) -> str:
    """RSS description에 섞여 들어오는 HTML 태그를 아주 단순하게 제거."""
    import re

    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text
