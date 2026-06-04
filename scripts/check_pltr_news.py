"""
Palantir 계약·파트너십 뉴스 감지 — Google News RSS 기반
Palantir의 신규 계약(award), 파트너십, 주요 딜 뉴스를 감지해 Telegram 알림.
NVIDIA 전략 파트너(Sovereign AI OS)로서 계약 확장이 AI 사이클 선행지표.

GitHub Actions에서 실행 — 매일 09:00 KST.

설계: failure() 기반이 아니라 GITHUB_OUTPUT 플래그(found=true) 기반.
네트워크 오류 시 조용히 종료 → '에러=가짜 알람' 버그 구조적 차단.

소스: Google News RSS — FT·WSJ·Politico·NYT·Reuters·Bloomberg·Defense One 등
      investors.palantir.com 공식 PR은 Google News가 수분 내 인덱싱하므로 별도 스크래핑 불필요.
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

# Google News 검색 쿼리 — Palantir가 '주체'인 계약·파트너십·주요 발표만 좁힘
QUERY = (
    # 계약 수주·선정
    '"palantir wins" OR "palantir awarded" OR "palantir award" OR '
    '"palantir selected" OR "palantir secures" OR "palantir contract" OR '
    '"palantir wins contract" OR "awarded to palantir" OR '
    # 파트너십·협업
    '"palantir partnership" OR "palantir partners with" OR "palantir teams with" OR '
    '"palantir signs" OR "palantir agreement" OR "palantir collaborates" OR '
    '"selects palantir" OR "chooses palantir" OR "picks palantir" OR "taps palantir" OR '
    # 발표·확장·배포
    '"palantir announces" OR "palantir launches" OR "palantir deploys" OR '
    '"palantir expands" OR "palantir integrates" OR "palantir deal"'
)

# 제목 2차 필터 — 계약·파트너십 기사(positive) / 주가·지분 잡음(negative)
POSITIVE = [
    # 계약·수주
    "palantir wins", "palantir awarded", "palantir award",
    "palantir selected", "palantir secures", "palantir contract",
    "palantir wins contract", "awarded to palantir",
    # 파트너십·협업
    "palantir partnership", "palantir partners", "palantir teams",
    "palantir signs", "palantir agreement", "palantir collaborates",
    "selects palantir", "chooses palantir", "picks palantir", "taps palantir",
    # 발표·확장
    "palantir announces", "palantir launches", "palantir deploys",
    "palantir expands", "palantir integrates", "palantir deal",
    "palantir receives", "palantir to provide", "palantir to deploy",
]
NEGATIVE = [
    # 주가·투자 기사 잡음 — Palantir가 '대상'인 주식 매매 기사
    "palantir stock", "palantir shares", "palantir earnings",
    "palantir price target", "palantir valuation", "palantir revenue",
    "palantir quarterly", "palantir q1", "palantir q2", "palantir q3", "palantir q4",
    "buys palantir", "sells palantir", "buying palantir", "selling palantir",
    "palantir short", "palantir insider", "palantir ceo sells",
    "stake in palantir", "position in palantir", "holdings in palantir",
    "adds palantir", "trim palantir", "raises palantir", "cuts palantir",
    "palantir price", "palantir rally", "palantir plunges", "palantir surges",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (nvidia-screener pltr-news monitor)"}


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
    lines = ["🟦 <b>Palantir 계약·파트너십 감지</b>", "", f"⏰ {kst} KST", ""]
    for m in matches:
        h = html.escape(m["headline"])
        link = html.escape(m["link"], quote=True)
        d = m["dt"].strftime("%Y-%m-%d")
        meta = f"{html.escape(m['source'])} · {d}" if m["source"] else d
        lines.append(f'• <a href="{link}">{h}</a>')
        lines.append(f"   <i>{meta}</i>")
    lines += ["", "👉 NVIDIA 전략파트너 동향 확인"]
    msg = "\n".join(lines)

    with open("pltr_news_alert.txt", "w", encoding="utf-8") as f:
        f.write(msg)

    set_output(True)


if __name__ == "__main__":
    main()
