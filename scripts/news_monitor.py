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
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import quote
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

WINDOW_HOURS = 25   # 매일 실행 + 25h 창 → 갭 방지, 중복 최소
MAX_ITEMS = 6
# Telegram sendMessage는 4096자를 넘으면 400으로 거절한다. 워크플로의 curl은
# -s라 그 실패가 로그에도 안 남아 '알림이 통째로 사라지는' 형태로 터진다.
# Google News 링크가 항목당 ~350자라 건수가 늘면 금방 닿는다(실측 9건=4042자).
TELEGRAM_LIMIT = 3900

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
    # 고빈도 종목용 — Google News RSS는 쿼리당 100건에서 잘린다. 한 쿼리가
    # 상한에 닿으면 넘친 만큼이 조용히 사라지므로, 주제를 갈래로 나눠 각각
    # 상한 아래로 만든 뒤 합집합을 쓴다. 비우면 query 하나만 쓴다.
    queries: list = field(default_factory=list)
    # 제목에 반드시 들어가야 할 토큰(OR). 쿼리를 넓히면 종목이 주체가 아닌
    # 기사(협력사 소식 등)가 섞여 들어와서 필요하다. 비우면 검사 생략.
    subject: list = field(default_factory=list)
    max_items: int = MAX_ITEMS
    # 공식 IR 보도자료 피드(Q4 Inc 플랫폼). {"url":..., "params":{...}} 형태.
    # Google News와 성격이 다르다 — 회사가 발표하기로 결정한 것만 들어오는
    # 이미 편집된 목록이라 키워드 필터를 적용하지 않는다. 필터는 무편집
    # 소방호스(Google News) 대응 장치이지 편집된 피드에 씌울 것이 아니다.
    ir_feed: dict = None


def _fetch_one(query, cfg):
    url = ("https://news.google.com/rss/search?q=" + quote(query) +
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


def _fetch_items(cfg):
    """cfg.queries가 있으면 갈래별로 받아 제목 기준 합집합, 없으면 cfg.query 하나."""
    merged = {}
    for q in (cfg.queries or [cfg.query]):
        for it in _fetch_one(q, cfg):
            merged.setdefault(it["title"].lower(), it)
    return list(merged.values())


def _fetch_all(cfg):
    """뉴스 레인과 IR 레인을 각각 격리해 수집 — 한쪽 장애가 다른 쪽을 침묵시키지 않게.

    둘 다 실패하면 빈 리스트라 알림이 안 나가고(가짜 알람 방지), 한쪽만 살아도
    그 몫은 발송된다. 예전엔 수집 전체가 하나의 try라 IR이 죽으면 뉴스도 죽었다.
    """
    items = []
    try:
        items += _fetch_items(cfg)
    except Exception as e:
        print(f"news fetch error: {e}")
    items += _fetch_ir(cfg)
    return items


# IR 피드 타임스탬프는 미 동부시(ET)다. 실적 보도자료가 예외 없이 16:05:00,
# 즉 미국 장 마감 5분 뒤라 UTC일 수 없다(그랬다면 장중 12:05 PM ET).
try:
    from zoneinfo import ZoneInfo
    _IR_TZ = ZoneInfo("America/New_York")          # DST 자동 처리
except Exception:                                  # tzdata 없는 환경 폴백
    _IR_TZ = timezone(timedelta(hours=-5))         # EST. 25h 창에선 1시간 차가 무해


def _fetch_ir(cfg):
    """공식 보도자료 피드. 실패해도 Google News 레인은 살아야 하므로 여기서 삼킨다."""
    if not cfg.ir_feed:
        return []
    now = datetime.now(_IR_TZ)
    # 1월엔 전년 12월 말 발표가 아직 25h 창에 들어올 수 있어 전년도도 본다.
    years = [now.year] + ([now.year - 1] if now.month == 1 else [])
    out = []
    for y in years:
        params = dict(cfg.ir_feed.get("params", {}))
        params["year"] = y
        try:
            r = requests.get(cfg.ir_feed["url"], params=params, timeout=20,
                             headers={"User-Agent": f"Mozilla/5.0 (nvidia-screener {cfg.label})"})
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"ir feed error ({y}): {e}")
            continue
        rows = data.get("GetPressReleaseListResult", data)
        if not isinstance(rows, list):
            continue
        for it in rows:
            head = (it.get("Headline") or "").strip()
            raw = (it.get("PressReleaseDate") or "").strip()
            if not head or not raw:
                continue
            try:
                dt = datetime.strptime(raw, "%m/%d/%Y %H:%M:%S").replace(tzinfo=_IR_TZ)
                dt = dt.astimezone(timezone.utc)
            except Exception:
                continue
            link = it.get("LinkToDetailPage") or it.get("LinkToUrl") or ""
            if link.startswith("/"):
                link = cfg.ir_feed.get("base", "") + link
            out.append({
                "title": head, "link": link, "source": cfg.ir_feed.get("label", "IR"),
                "pub": "", "dt": dt, "authoritative": True,
            })
    return out


def _strip_source(headline, source):
    """Google News가 붙이는 ' - 출처' 접미사 제거.

    필터보다 먼저 벗겨야 한다 — 출처명에 NEGATIVE 단어가 들어간 매체가 있어서
    ("Stock Titan", "Stocktwits", "Investing.com") 안 벗기면 멀쩡한 기사가
    출처명 때문에 탈락한다. 실제로 PLTR 모니터가 이걸로 계약 기사를 놓쳤음.
    """
    suffix = " - " + source
    if source and headline.endswith(suffix):
        headline = headline[:-len(suffix)]
    elif not source and " - " in headline:
        headline, source = headline.rsplit(" - ", 1)
    return headline.rstrip(" .…").strip(), source.strip()


def _is_relevant(title, cfg, authoritative=False):
    # 공식 보도자료는 회사가 발표하기로 판단한 것 자체가 관련성 신호다. 어떤
    # 필터도 걸지 않는다 — 키워드를 씌우면 경영진 영입·AIPCon 같은 게 탈락하고,
    # subject 가드를 씌우면 제목에 사명이 없는 제품·합작사 발표가 탈락한다
    # (2020~2026 공식 PR 296건 중 2건: Syntropy, Agora).
    if authoritative:
        return True
    tl = title.lower()
    if cfg.subject and not any(s in tl for s in cfg.subject):
        return False
    if not any(p in tl for p in cfg.positive):
        return False
    if any(n in tl for n in cfg.negative):
        return False
    return True


# 엔티티 후보에서 뺄 일반어. 대문자로 시작한다고 다 고유명사는 아니라서
# ("Contract", "Announces", "How") 이걸 안 빼면 서로 다른 사건이 오병합된다.
GENERIC = set("""
the a an and or for to with of in on by as from after amid over into its their this that
is are be new how why what when where more most best first next full
ai us uk eu inc ltd limited corp llc co group holdings technologies company
million billion ceo cto cfo former global strategic enterprise business platform software
system systems program data cloud customers customer supply chain chains
""".split())


def _token_key(headline):
    """기존 중복제거 키 — 제목 앞 4토큰."""
    tokens = "".join(c if c.isalnum() else " " for c in headline.lower()).split()
    return {"".join(tokens[:4])}


def _dedupe_key(headline, cfg):
    """같은 사건을 묶기 위한 키.

    1순위는 '상대 기업명' — 같은 딜을 여러 매체가 쓰면 상대 회사 이름이 겹친다.
    감시 대상 종목 자신(cfg.subject)과 필터 어휘는 모든 기사에 공통이라 제외한다.

    대문자 휴리스틱은 영문 전용이다. 한글 로케일에 쓰면 제목에 섞인 라틴 약어
    (DNV·IMO 등)가 기업명으로 잡혀 서로 다른 사건이 오병합되므로, 한글은
    기존 방식(앞 4토큰)을 그대로 쓴다. 영문도 엔티티가 안 나오면 같은 폴백.
    """
    if cfg.locale != "en":
        return _token_key(headline)
    drop = set(GENERIC)
    for words in (cfg.subject, cfg.positive, cfg.negative):
        for w in words:
            drop.update(w.lower().split())
    out = set()
    for tok in re.findall(r"[A-Z][A-Za-z0-9&.\-]{2,}", headline):
        t = tok.lower().strip(".")
        if t and t not in drop:
            out.add(t)
    return out or _token_key(headline)


def _set_output(found):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"found={'true' if found else 'false'}\n")


def run_monitor(cfg):
    items = _fetch_all(cfg)
    if not items:
        # 전 소스 실패 → 조용히 종료 (가짜 알람 방지)
        print("no items fetched")
        _set_output(False)
        sys.exit(0)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=WINDOW_HOURS)

    matches = []
    for it in items:
        dt = it.get("dt")
        if dt is None:
            try:
                dt = parsedate_to_datetime(it["pub"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        if dt < cutoff:
            continue
        auth = bool(it.get("authoritative"))
        headline, source = _strip_source(it["title"], it["source"])
        if not _is_relevant(headline, cfg, auth):
            continue

        matches.append({
            "headline": headline, "source": source,
            "link": it["link"], "dt": dt, "auth": auth,
            "dkey": _dedupe_key(headline, cfg),
        })

    # 중복 제거 — 같은 사건을 여러 매체가 쓰면 상대 기업명이 겹친다.
    # 앞 4토큰 키로는 "Palantir and Fujitsu renew…"와 "Fujitsu Signs New
    # Palantir…"가 안 묶여서 6칸짜리 알림이 한 사건으로 다 차버렸다.
    # 같은 사건이 공식 PR과 3자 기사 양쪽에 있으면 공식 쪽이 이긴다 — 정본
    # 제목·날짜·링크를 주므로. 정렬을 (정본 우선, 최신순)으로 두면 뒤에 오는
    # 3자 중복이 자연히 탈락한다.
    matches.sort(key=lambda x: (not x["auth"], -x["dt"].timestamp()))
    deduped = []
    for m in matches:
        if any(m["dkey"] & d["dkey"] for d in deduped):
            continue
        deduped.append(m)
    deduped.sort(key=lambda x: x["dt"], reverse=True)
    matches = deduped[:cfg.max_items]

    print(f"window={WINDOW_HOURS}h  fetched={len(items)}  matched={len(matches)}")
    for m in matches:
        print(f"  - {m['headline']}  [{m['source']}]")

    if not matches:
        _set_output(False)
        return

    kst = (now + timedelta(hours=9)).strftime("%Y-%m-%d")

    def build(items):
        lines = [cfg.header, "", f"⏰ {kst} KST", ""]
        for m in items:
            h = html.escape(m["headline"])
            link = html.escape(m["link"], quote=True)
            d = m["dt"].strftime("%Y-%m-%d")
            meta = f"{html.escape(m['source'])} · {d}" if m["source"] else d
            lines.append(f'• <a href="{link}">{h}</a>')
            lines.append(f"   <i>{meta}</i>")
        if len(items) < len(matches):
            lines.append(f"   <i>… 외 {len(matches) - len(items)}건</i>")
        lines += ["", cfg.footer]
        return "\n".join(lines)

    # 길이 초과 시 오래된 항목부터 덜어낸다 — 전체가 거절당하느니 최신 몇 건이라도.
    shown = list(matches)
    msg = build(shown)
    while len(msg) > TELEGRAM_LIMIT and len(shown) > 1:
        shown.pop()
        msg = build(shown)
    if len(shown) < len(matches):
        print(f"  (길이 제한: {len(matches)}건 중 {len(shown)}건만 전송)")

    with open(cfg.out_file, "w", encoding="utf-8") as f:
        f.write(msg)

    _set_output(True)
