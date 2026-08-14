import json
import os
import sys
import threading
from datetime import date, datetime

if sys.platform == "win32":
    # Windows 콘솔의 기본 코드페이지(cp949)는 이모지/em-dash 등을 출력하지 못해 print()가 죽는 경우가 있어 UTF-8로 고정
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, abort, render_template
from sqlalchemy import distinct, select
from zoneinfo import ZoneInfo

from db import get_session, init_db
from fetch_and_summarize import run_daily_digest, today_kst
from models import Article

load_dotenv()

KST = ZoneInfo("Asia/Seoul")

app = Flask(__name__)
init_db()

_fetch_lock = threading.Lock()
_fetching = False


def _run_fetch_in_background():
    global _fetching
    with _fetch_lock:
        if _fetching:
            return
        _fetching = True
    try:
        run_daily_digest()
    finally:
        with _fetch_lock:
            _fetching = False


def _ensure_today_digest_is_fresh():
    """오늘자 다이제스트가 없으면 백그라운드 스레드로 생성을 시작한다.
    (무료 호스팅에서 서버가 잠들었다 깨어나도 방문자가 있으면 스스로 최신화)"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return
    session = get_session()
    has_today = session.execute(
        select(Article).where(Article.digest_date == today_kst()).limit(1)
    ).scalar_one_or_none()
    session.close()

    if not has_today and not _fetching:
        thread = threading.Thread(target=_run_fetch_in_background, daemon=True)
        thread.start()


def _article_to_card(article: Article) -> dict:
    return {
        "id": article.id,
        "source": article.source,
        "url": article.url,
        "headline_kr": article.headline_kr,
        "easy_english": article.easy_english,
        "korean_explanation": article.korean_explanation,
        "vocab": json.loads(article.vocab_json or "[]"),
    }


@app.route("/")
def index():
    _ensure_today_digest_is_fresh()

    session = get_session()
    latest_date_row = session.execute(
        select(Article.digest_date).order_by(Article.digest_date.desc()).limit(1)
    ).first()
    latest_date = latest_date_row[0] if latest_date_row else None

    articles = []
    if latest_date:
        rows = session.execute(
            select(Article)
            .where(Article.digest_date == latest_date)
            .order_by(Article.id.desc())
        ).scalars()
        articles = [_article_to_card(a) for a in rows]

    all_dates = session.execute(
        select(distinct(Article.digest_date)).order_by(Article.digest_date.desc()).limit(14)
    ).scalars().all()
    session.close()

    return render_template(
        "index.html",
        articles=articles,
        digest_date=latest_date,
        all_dates=all_dates,
        is_empty=not articles,
        api_key_missing=not os.environ.get("ANTHROPIC_API_KEY"),
    )


@app.route("/day/<date_str>")
def day(date_str):
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        abort(404)

    session = get_session()
    rows = session.execute(
        select(Article).where(Article.digest_date == target_date).order_by(Article.id.desc())
    ).scalars()
    articles = [_article_to_card(a) for a in rows]

    all_dates = session.execute(
        select(distinct(Article.digest_date)).order_by(Article.digest_date.desc()).limit(14)
    ).scalars().all()
    session.close()

    if not articles:
        abort(404)

    return render_template(
        "index.html",
        articles=articles,
        digest_date=target_date,
        all_dates=all_dates,
        is_empty=False,
        api_key_missing=False,
    )


@app.route("/article/<int:article_id>")
def article_detail(article_id):
    session = get_session()
    article = session.get(Article, article_id)
    session.close()

    if not article:
        abort(404)

    return render_template("article.html", article=_article_to_card(article), source=article.source)


def _start_scheduler():
    hour = int(os.environ.get("DIGEST_HOUR", 7))
    minute = int(os.environ.get("DIGEST_MINUTE", 0))

    scheduler = BackgroundScheduler(timezone=str(KST))
    scheduler.add_job(
        _run_fetch_in_background,
        "cron",
        hour=hour,
        minute=minute,
        id="daily_news_digest",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[app] 스케줄러 시작됨 — 매일 {hour:02d}:{minute:02d} (KST)에 자동 실행")


# debug reloader를 쓰지 않으므로(app.run(debug=False)) 프로세스당 한 번만 시작된다.
# gunicorn으로 배포할 때는 워커가 여러 개면 스케줄러도 여러 번 실행되니 --workers 1 을 권장 (README 참고)
if os.environ.get("DISABLE_SCHEDULER") != "true":
    _start_scheduler()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
