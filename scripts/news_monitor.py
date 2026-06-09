"""
공용 뉴스 모니터 코어 — Google News RSS 기반.

종목별 스크립트(check_news.py / check_pltr_news.py / check_hanwha_news.py)는
MonitorConfig만 정의해 run_monitor()를 호출한다. 수집·필터·중복제거·메시지
포맷 로직은 전부 여기 한 곳에만 둔다 (3중 복붙 제거).

설계: found=true 플래그(GITHUB_OUTPUT) 기반 — 네트워크/파싱 오류 시 조용히
종료해 '에러=가짜 알람' 버그를 구조적으로 차단.
"""
import requests
import sys
import os
import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

WINDOW_HOURS = 25   # 매일 실행 + 25h 창 → 갭 방지, 중복 최소
MAX_ITEMS = 6

# Google News 로케일 — 영문 종목은 "en", 국내(한글) 종목은 "ko"
LOCALES = {
    "en": "hl=en-US&gl=US&ceid=US:en",
    "ko": "hl=ko&gl=KR&ceid=KR:ko",
}


@dataclass
class MonitorConfig:
    query: str          # Google News 검색 쿼리
    positive: list      # 제목 2차 필터 (포함되어야 함)
    negative: list      # 제목 2차 필터 (있으면 제외)
    header: str         # 메시지 첫 줄, 예: "🟢 <b>NVIDIA 투자 뉴스 감지</b>"
    footer: str         # 메시지 끝 줄, 예: "👉 트래커 업데이트 검토 필요"
    out_file: str       # 알림 본문 출력 파일, 예: "news_alert.txt"
    locale: str = "en"  # "en" 또는 "ko"
    label: str = "monitor"  # User-Agent 식별용


def _fetch_items(cfg):
    url = ("https://news.google.com/rss/search?q=" + quote(cfg.query) +
           "&" + LOCALES[cfg.locale])
    headers = {"User-Agent": f"Mozilla/5.0 (nvidia-screener {cfg.label})"}
    r = requests.get(url, headers=headers, timeout=20)
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


def _is_relevant(title, cfg):
    tl = title.lower()
    if not any(p in tl for p in cfg.positive):
        return False
    if any(n in tl for n in cfg.negative):
        return False
    return True


def _set_output(found):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"found={'true' if found else 'false'}\n")


def run_monitor(cfg):
    try:
        items = _fetch_items(cfg)
    except Exception as e:
        # 네트워크/파싱 오류 → 조용히 종료 (가짜 알람 방지)
        print(f"fetch error: {e}")
        _set_output(False)
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
        if not _is_relevant(it["title"], cfg):
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
        _set_output(False)
        return

    kst = (now + timedelta(hours=9)).strftime("%Y-%m-%d")
    lines = [cfg.header, "", f"⏰ {kst} KST", ""]
    for m in matches:
        h = html.escape(m["headline"])
        link = html.escape(m["link"], quote=True)
        d = m["dt"].strftime("%Y-%m-%d")
        meta = f"{html.escape(m['source'])} · {d}" if m["source"] else d
        lines.append(f'• <a href="{link}">{h}</a>')
        lines.append(f"   <i>{meta}</i>")
    lines += ["", cfg.footer]
    msg = "\n".join(lines)

    with open(cfg.out_file, "w", encoding="utf-8") as f:
        f.write(msg)

    _set_output(True)
