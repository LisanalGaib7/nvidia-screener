"""
한화엔진 수주·계약 뉴스 감지 — Google News RSS (국내 언론 위주)
한화엔진의 신규 수주, 계약, 파트너십, 수출 뉴스를 감지해 Telegram 알림.

GitHub Actions에서 실행 — 매일 09:00 KST.
Google News hl=ko&gl=KR 파라미터로 국내 언론사(연합뉴스·조선비즈·매일경제·한국경제 등) 우선 수집.

설계: found=true 플래그 기반 — 에러 시 조용히 종료(가짜 알람 차단).
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

# Google News 검색 쿼리 — 한화엔진이 '주체'인 수주·계약·협약만 좁힘
QUERY = (
    # 수주·계약
    '"한화엔진 수주" OR "한화엔진 계약" OR "한화엔진 공급" OR '
    '"한화엔진 납품" OR "한화엔진 수출" OR "한화엔진 협약" OR '
    # MOU·파트너십
    '"한화엔진 MOU" OR "한화엔진 업무협약" OR "한화엔진 파트너십" OR '
    '"한화엔진 협력" OR "한화엔진 선정" OR "한화엔진 체결" OR '
    # 제품·개발
    '"한화엔진 개발" OR "한화엔진 엔진" OR "한화엔진 선박" OR '
    '"한화엔진 암모니아" OR "한화엔진 메탄올" OR "한화엔진 LNG"'
)

# 제목 2차 필터 — 수주·계약 기사(positive) / 주가·지분 잡음(negative)
POSITIVE = [
    # 수주·계약
    "한화엔진 수주", "한화엔진 계약", "한화엔진 공급",
    "한화엔진 납품", "한화엔진 수출", "한화엔진 협약",
    # MOU·파트너십
    "한화엔진 mou", "한화엔진 업무협약", "한화엔진 파트너십",
    "한화엔진 협력", "한화엔진 선정", "한화엔진 체결",
    # 제품·개발
    "한화엔진 개발", "한화엔진 엔진", "한화엔진 선박",
    "한화엔진 암모니아", "한화엔진 메탄올", "한화엔진 lng",
    # 피동형
    "한화엔진이 선정", "한화엔진을 선택", "한화엔진과 계약",
]
NEGATIVE = [
    # 주가·투자 기사 잡음
    "한화엔진 주가", "한화엔진 주식", "한화엔진 실적",
    "한화엔진 목표가", "한화엔진 공매도", "한화엔진 배당",
    "한화엔진 영업이익", "한화엔진 매출", "한화엔진 순이익",
    "한화엔진 투자의견", "한화엔진 상향", "한화엔진 하향",
    "사는 한화엔진", "파는 한화엔진",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (nvidia-screener hanwha-news monitor)"}


def fetch_items():
    # hl=ko&gl=KR → 국내 언론사 우선 노출
    url = ("https://news.google.com/rss/search?q=" + quote(QUERY) +
           "&hl=ko&gl=KR&ceid=KR:ko")
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
    lines = ["🟠 <b>한화엔진 수주·계약 감지</b>", "", f"⏰ {kst} KST", ""]
    for m in matches:
        h = html.escape(m["headline"])
        link = html.escape(m["link"], quote=True)
        d = m["dt"].strftime("%Y-%m-%d")
        meta = f"{html.escape(m['source'])} · {d}" if m["source"] else d
        lines.append(f'• <a href="{link}">{h}</a>')
        lines.append(f"   <i>{meta}</i>")
    lines += ["", "👉 포트폴리오 동향 확인"]
    msg = "\n".join(lines)

    with open("hanwha_news_alert.txt", "w", encoding="utf-8") as f:
        f.write(msg)

    set_output(True)


if __name__ == "__main__":
    main()
