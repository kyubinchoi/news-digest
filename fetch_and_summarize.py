"""
RSS 피드에서 최신 기사를 가져와 Claude로 쉬운 영어 요약 + 한국어 설명을 생성하고 DB에 저장.

로컬에서 수동 실행: python fetch_and_summarize.py
Flask 앱(app.py)의 APScheduler가 매일 자동으로 이 모듈의 run_daily_digest()를 호출한다.
"""

import sys
from datetime import datetime
from zoneinfo import ZoneInfo

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from sqlalchemy import select

from db import get_session, init_db
from feeds import fetch_all_entries
from models import Article
from summarizer import summarize_article, vocab_to_json

KST = ZoneInfo("Asia/Seoul")


def today_kst():
    return datetime.now(KST).date()


def run_daily_digest():
    init_db()
    session = get_session()
    today = today_kst()

    print(f"[fetch_and_summarize] {today} 다이제스트 생성 시작")

    entries = fetch_all_entries()
    print(f"[fetch_and_summarize] RSS에서 {len(entries)}개 기사 발견")

    saved = 0
    for entry in entries:
        existing = session.execute(
            select(Article).where(Article.url == entry["url"])
        ).scalar_one_or_none()
        if existing:
            continue

        try:
            summary = summarize_article(
                source=entry["source"],
                title=entry["title"],
                original_summary=entry["original_summary"],
            )
        except Exception as exc:  # noqa: BLE001 - 개별 기사 실패는 건너뛰고 계속 진행
            print(f"[fetch_and_summarize] 요약 실패: {entry['title'][:50]}... ({exc})")
            continue

        article = Article(
            source=entry["source"],
            title=entry["title"],
            url=entry["url"],
            original_summary=entry["original_summary"],
            digest_date=today,
            published_at=None,
            headline_kr=summary.get("headline_kr", entry["title"]),
            easy_english=summary.get("easy_english", ""),
            korean_explanation=summary.get("korean_explanation", ""),
            vocab_json=vocab_to_json(summary.get("vocab", [])),
        )
        session.add(article)
        session.commit()
        saved += 1
        print(f"[fetch_and_summarize] 저장됨: {article.headline_kr}")

    session.close()
    print(f"[fetch_and_summarize] 완료 — 새로 저장된 기사 {saved}개")
    return saved


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    sys.exit(0 if run_daily_digest() >= 0 else 1)
