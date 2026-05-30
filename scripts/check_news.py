"""
NVIDIA 투자 뉴스 감지 — Google News RSS 기반
NVIDIA가 다른 기업에 투자/지분참여한 뉴스를 감지해 Telegram으로 알림.
13F가 놓치는 '분기 중 전략투자 발표'(워런트/우선주/사모)를 커버.

GitHub Actions에서 실행 — Google News는 클라우드 IP를 차단하지 않으므로
SEC와 달리 상시 작동(노트북 의존 없음).

설계: failure() 기반이 아니라 GITHUB_OUTPUT 플래그(found=true) 기반.
네트워크 오류 시 조용히 종료 → '에러=가짜 알람' 버그 구조적 차단.
"""
import requests
import sys
import os
import html
import xml.etree.ElementTree as ET
from urllib.parse import quote
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

WINDOW_HOURS = 25   # 매일 실행 + 25h 창 → 갭 방지, 중복 최소
MAX_ITEMS = 6

# Google News 검색 쿼리 — NVIDIA가 '주체'인 포트폴리오 변동(매수/13F/매도)만 좁힘
QUERY = (
    # 매수·투자
    '"nvidia invests" OR "nvidia-backed" OR "backed by nvidia" OR '
    '"nvidia investment" OR "nvidia takes stake" OR "nvidia leads" OR '
    '"nvidia buys stake" OR "nvidia acquires" OR "nvidia to invest" OR '
    # 13F·포트폴리오 변동
    '"nvidia 13f" OR "nvidia portfolio" OR "nvidia discloses" OR '
    # 매도·청산
    '"nvidia exits" OR "nvidia sells stake" OR "nvidia trims stake" OR '
    '"nvidia dumps" OR "nvidia reveals stake"'
)

# 제목 2차 필터 — NVIDIA가 주체(positive) / 남이 NVDA 주식을 사고파는 잡음(negative)
POSITIVE = [
    # 매수·투자
    "nvidia invests", "nvidia is investing", "nvidia to invest", "nvidia plans to invest",
    "nvidia-backed", "backed by nvidia", "nvidia backs",
    "nvidia investment", "nvidia takes stake", "nvidia takes a stake",
    "nvidia buys stake", "nvidia acquires", "nvidia-led",
    "nvidia bets", "nvidia commits", "nvidia pours", "nvidia stake in",
    "nvidia leads round", "nvidia leads investment", "nvidia leads funding",
    # 13F·포트폴리오 (쿼리가 nvidia로 스코프되므로 '13f' 단독 토큰도 안전)
    "13f", "nvidia portfolio", "nvidia's portfolio", "nvidia discloses", "nvidia reveals stake",
    # 매도·청산
    "nvidia exits", "nvidia sells stake", "nvidia trims", "nvidia dumps",
    "nvidia reduces", "nvidia dissolves", "nvidia cuts stake",
]
NEGATIVE = [
    # NVIDIA가 '대상'인 잡음 — 남이 NVDA 주식을 매매
    "purchased by", "sold by", "shares of nvidia", "stake in nvidia",
    "position in nvidia", "stake by", "holdings in nvidia",
    "shares purchased", "shares sold", "has stake in nvidia",
    "in nvidia stock", "of nvidia stock",
    "boosts nvidia", "trims nvidia", "buys nvidia", "sells nvidia",
    "lowers nvidia", "raises nvidia", "cuts nvidia", "reduces nvidia",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (nvidia-screener news monitor)"}


def fetch_items():
    url = ("https://news.google.com/rss/search?q=" + quote(QUERY) +
           "&hl=en-US&gl=US&ceid=US:en")
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for it in root.findall(".//item"):
        items.append({
            "title":  (it.findtext("title") or "").strip(),
            "link":   (it.findtext("link") or "").strip(),
            "pub":    (it.findtext("pubDate") or "").strip(),
            "source": (it.findtext("source") or "").strip(),
        })
    return items


def is_relevant(title):
    tl = title.lower()
    if not any(p in tl for p in POSITIVE):
        return False
    if any(n in tl for n in NEGATIVE):
        return False
    return True


def set_output(found):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"found={'true' if found else 'false'}\n")


def main():
    try:
        items = fetch_items()
    except Exception as e:
        # 네트워크/파싱 오류 → 조용히 종료 (가짜 알람 방지)
        print(f"fetch error: {e}")
        set_output(False)
        sys.exit(0)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=WINDOW_HOURS)

    seen = set()
    matches = []
    for it in items:
        try:
            dt = parsedate_to_datetime(it["pub"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if dt < cutoff:
            continue
        if not is_relevant(it["title"]):
            continue

        headline, source = it["title"], it["source"]
        if not source and " - " in headline:
            headline, source = headline.rsplit(" - ", 1)
        headline = headline.rstrip(" .…").strip()

        # 중복 제거 — 앞 4개 토큰 기준 (같은 사건 다른 매체 병합)
        tokens = "".join(c if c.isalnum() else " " for c in headline.lower()).split()
        key = "".join(tokens[:4])
        if key in seen:
            continue
        seen.add(key)
        matches.append({
            "headline": headline.strip(), "source": source.strip(),
            "link": it["link"], "dt": dt,
        })

    matches.sort(key=lambda x: x["dt"], reverse=True)
    matches = matches[:MAX_ITEMS]

    print(f"window={WINDOW_HOURS}h  fetched={len(items)}  matched={len(matches)}")
    for m in matches:
        print(f"  - {m['headline']}  [{m['source']}]")

    if not matches:
        set_output(False)
        return

    kst = (now + timedelta(hours=9)).strftime("%Y-%m-%d")
    lines = ["📰 <b>NVIDIA 투자 뉴스 감지</b>", "", f"⏰ {kst} KST", ""]
    for m in matches:
        h = html.escape(m["headline"])
        link = html.escape(m["link"], quote=True)
        d = m["dt"].strftime("%Y-%m-%d")
        meta = f"{html.escape(m['source'])} · {d}" if m["source"] else d
        lines.append(f'• <a href="{link}">{h}</a>')
        lines.append(f"   <i>{meta}</i>")
    lines += ["", "👉 트래커 업데이트 검토 필요"]
    msg = "\n".join(lines)

    with open("news_alert.txt", "w", encoding="utf-8") as f:
        f.write(msg)

    set_output(True)


if __name__ == "__main__":
    main()
