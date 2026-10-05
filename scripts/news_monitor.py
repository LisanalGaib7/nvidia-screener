"""
공용 뉴스 모니터 코어 — Google News RSS 기반.

종목별 스크립트(check_news.py / check_pltr_news.py / check_hanwha_news.py)는
MonitorConfig만 정의해 run_monitor()를 호출한다. 수집·필터·중복제거·메시지
포맷 로직은 전부 여기 한 곳에만 둔다 (3중 복붙 제거).

설계: found=true 플래그(GITHUB_OUTPUT) 기반 — 네트워크/파싱 오류 시 조용히
종료해 '에러=가짜 알람' 버그를 구조적으로 차단.
"""
import json
import requests
import sys
import os
import time
import html
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import quote
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

WINDOW_HOURS = 25   # 매일 실행 + 25h 창 → 갭 방지, 중복 최소. 직전 실행 기록이 없을 때의 값이자 최소값
# GitHub 스케줄은 정시에 돌지 않는다 — 45일 실측에서 예약보다 2~6시간 늦었고, 지연이
# 하루 사이 커진 날엔 실행 간격이 25시간을 넘었다(최대 29.2h, 3회). 고정 창이면 그 틈의
# 기사가 조용히 빠진다. 그래서 창을 '직전 실행 이후 + 여유'로 잡는다. 겹친 구간의 재발송은
# 교차 실행 차단이 막는다. 상한은 몇 날 멈췄다 재개될 때 묵은 기사가 쏟아지지 않게.
WINDOW_MARGIN_HOURS = 1
WINDOW_MAX_HOURS = 72
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

# 같은 사건을 여러 매체가 쓸 때 어느 기사를 보낼지 정하는 기준. 중복제거 승자를
# 최신순으로 뽑으면 원 보도(0일차)가 아니라 받아쓰기(1~2일차)가 이긴다 — 실측
# 23개 클러스터 중 7개가 티어1을 두고 마이너 매체에 밀렸다(Zankore 건은
# Bloomberg를 두고 IDNFinancials가 나갔다).
#
# 티어를 둘이 아니라 셋으로 둔 이유: 페이월. Bloomberg/WSJ/FT는 구독이 없으면
# 링크를 눌러도 원문을 못 본다. 같은 와이어 기사를 무료로 재게재하는 쪽(Yahoo
# Finance 등)이 있으면 그쪽이 실제로 더 쓸모 있다. 그래서
#   1 = 신뢰할 만하고 원문을 볼 수 있는 곳
#   2 = 신뢰할 만하지만 페이월
#   3 = 그 외
# 로 두고, 1이 없을 때만 2가 나간다.
SOURCE_TIERS = {
    # 티어1 — 무료로 열리는 곳(와이어 원문 + 그 재게재)
    "reuters": 1, "associated press": 1, "ap news": 1, "cnbc": 1,
    "yahoo finance": 1, "yahoo": 1,
    # 티어2 — 페이월
    "bloomberg": 2, "bloomberg.com": 2,
    "wsj": 2, "the wall street journal": 2,
    "financial times": 2, "ft.com": 2,
    "barron's": 2, "barrons": 2, "the information": 2,
}


def _source_tier(source):
    """등재 브랜드의 지역판·계열지도 같은 티어로 본다.

    완전일치로 두면 "BNN Bloomberg"·"CNBC Africa"가 t3로 떨어진다 — 브랜드를
    등재해 놓고 못 잡는 건 그냥 누락이다. 단어 경계로 봐서 "Information Week"가
    "the information"에 걸리는 식의 오매칭은 막는다.
    """
    src = (source or "").strip().lower()
    if src in SOURCE_TIERS:
        return SOURCE_TIERS[src]
    padded = " " + "".join(c if c.isalnum() else " " for c in src).strip() + " "
    for key, tier in SOURCE_TIERS.items():
        k = " " + "".join(c if c.isalnum() else " " for c in key).strip() + " "
        if k in padded:
            return tier
    return 3


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
    # 실행 간 발송 이력 파일. 미설정이면 교차 실행 검사를 생략한다(기존 동작).
    state_file: str = ""
    # 알림을 주제별 섹션으로 나눈다. [{"label":..., "terms":[...], "max":n}] 꼴로
    # 순서대로 보고, terms가 비면 catch-all. 비워두면 단일 블록(기존 동작).
    # NVIDIA 레인은 '신규 투자'와 '포트폴리오사 동향'이 성격이 달라서 필요하다 —
    # 실측 23개 이벤트 중 10 대 13으로 섞여 들어와 구분이 안 됐다.
    groups: list = field(default_factory=list)
    # 출처 단위 제외. 제목이 아니라 매체로 거른다 — 영상 플랫폼처럼 형식 자체가
    # 알림 링크에 안 맞는 곳은 제목 키워드로 잡을 성질이 아니다. 소문자 부분일치.
    exclude_sources: list = field(default_factory=list)
    # POSITIVE 인접 문구를 못 맞추는 문장형 제목 구제용.
    # {"subjects": [...], "terms": [...], "window": n}. 비우면 검사 생략.
    proximity: dict = None
    # 일반 RSS 피드(회사 블로그·국제기구 뉴스룸 등). [{"url":..., "label":...,
    # "group": 섹션 label, "filter": 정규식}] 꼴. Google News가 아니라 발행처가
    # 직접 고른 목록이라 레인 필터(positive·subject 등)를 씌우지 않는다 — ir_feed와
    # 같은 이유. 대신 피드 범위가 레인보다 넓은 곳(국제기구 뉴스룸 등)은 filter
    # 정규식으로 제목+요약을 거른다. group을 주면 키워드 분류 없이 그 섹션에 둔다
    # (뉴스레터 제목에는 사명이 안 들어가서 키워드로는 회사 섹션에 못 온다).
    rss_feeds: list = field(default_factory=list)
    # 한글 제목 유사도 묶기 임계값. 0이면 끈다(기존 동작). 한글은 엔티티 키를 못
    # 써서(_dedupe_key) 같은 사건 기사가 그대로 여러 건 나갔다 — 한글 레인 30일
    # 실측에서 한 사건이 4건. 값은 레인별 실측으로 정한다(같은 사건 쌍과 다른
    # 사건 쌍의 분포가 겹치므로 '다른 사건을 하나도 안 묶는' 쪽으로).
    title_sim: float = 0.0
    # 중복제거 키에서 뺄 이름. 여러 사건에 반복 등장하는 허브 기업(대형 구매자 등)은
    # 한 단어만 겹쳐도 서로 다른 사건을 잇는다 — 실측: 'google' 하나로 다른 기업과의
    # 계약 기사 10여 건이 9/16 별건 기사에 묶여 사건째 사라졌다. 소문자.
    key_ignore: list = field(default_factory=list)
    # 대표 기사 옆에 묶인 기사 수를 붙인다("같은 사건 외 N건").
    show_dups: bool = False
    # 교차 실행 차단에서 '한 단어만 겹친' 경우의 제목 유사도 기준. 0이면 한 단어로도
    # 막는다(기존 동작). 상대가 매번 바뀌는 종목은 한 단어가 곧 상대 기업명이지만,
    # 고객이 정부·기관으로 반복되는 종목(PLTR: ICE·NHS·Army·Labour)은 그 단어가
    # 주제어라서 다른 사건을 잇는다 — 실측: 'ice' 하나로 ICE 시위자 DB 보도가 사흘간
    # 간호사 시위 기사에 막혀 끝내 미발송. 같은 회차 안의 묶기에는 쓰지 않는다
    # (거기선 주제당 하루 1건으로 묶는 게 원하는 동작이다).
    cross_run_sim: float = 0.0
    # 섹션 판정 규칙. [{"label": 섹션 label, "terms": [...], "word": bool}]을 앞에서부터
    # 보고 처음 맞는 섹션에 넣는다. 표시 순서·칸 수는 groups가 그대로 정한다. 비우면
    # groups 순서로 판정(기존 동작). 판정 순서와 표시 순서를 떼야 했다 — "NHS 계약을
    # 끝내라"가 'contract' 때문에 계약 섹션으로 갔는데, 그렇다고 논란을 계약보다 위에
    # 표시할 이유는 없다. 아무 규칙에도 안 맞으면 terms가 빈 섹션(catch-all)으로 간다.
    classify: list = field(default_factory=list)
    # 제외 매체가 낸 것과 같은 제목은 다른 매체 것도 뺀다. 주가 논평 매체 기사가
    # Yahoo 등에 같은 제목으로 재게재되면 매체 제외를 우회한다(실측: Motley Fool 원문은
    # 막혔는데 Yahoo 재게재본이 발송). 꺼짐이 기본 — 영상 플랫폼을 제외하는 레인에선
    # 뉴스 제목을 그대로 단 영상 때문에 진짜 기사가 막힐 수 있다.
    exclude_twins: bool = False
    # 섹션 칸을 최소 보장으로 쓰고, 그날 남는 칸은 넘치는 섹션에 넘긴다(전체는
    # max_items). 꺼짐이면 섹션 칸이 곧 상한(기존 동작).
    spill_over: bool = False
    # 실행 기록(jsonl). 실행마다 수집·통과·발송 건수와 오류를 한 줄 남긴다.
    # 알림이 하루 1건 안팎인 레인은 침묵이 정상이라, '조용한 날'과 '고장 난 날'을
    # 가르려면 따로 남겨야 한다. 비우면 기록하지 않는다(기존 동작).
    log_file: str = ""


# 실행 간 중복 차단. 창(WINDOW_HOURS)만으로는 "어제 보냈는지"를 알 수 없어서,
# 창이 겹치는 구간(정기 실행끼리는 1시간, 수동 실행을 끼면 그 이상)의 항목이
# 다음 회차에 그대로 다시 나간다. 실측: 9/10 발송 10건 중 8건이 9/11에 재발송.
ENTITY_TTL_DAYS = 3     # 한 딜의 보도 사이클이 보통 2~3일. 그 안의 재보도만 막는다.
TITLE_TTL_DAYS = 30     # 완전히 같은 제목은 재게시이므로 더 길게 막아도 안전하다.
KEEP_ENTRIES = 400


def _load_state(cfg):
    if not cfg.state_file:
        return {"sent": []}
    try:
        with open(cfg.state_file, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sent": []}


def _save_state(cfg, state):
    if not cfg.state_file:
        return False
    state["sent"] = state["sent"][-KEEP_ENTRIES:]
    os.makedirs(os.path.dirname(cfg.state_file), exist_ok=True)
    with open(cfg.state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    return True


def _bigrams(text):
    t = re.sub(r"[^0-9a-z가-힣]", "", text.lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _idf_table(titles):
    """그날 수집분 전체에서 글자쌍 희귀도. 레인 주제어는 흔해서
    가중치가 낮고, 기관명·금액 같은 사건 고유어가 유사도를 좌우하게 된다.
    가중치 없는 2-gram Jaccard로는 같은 주제의 다른 기관 사업(0.24)이 같은
    사건의 다른 기사(0.12)보다 높게 나와서 필요했다."""
    df = {}
    for t in titles:
        for g in _bigrams(t):
            df[g] = df.get(g, 0) + 1
    n = max(len(titles), 1)
    return {g: math.log(n / (1 + c)) for g, c in df.items()}, math.log(n)


def _title_sim(a, b, idf):
    table, default = idf
    A, B = _bigrams(a), _bigrams(b)
    union = sum(max(table.get(g, default), 0) for g in A | B)
    if not union:
        return 0.0
    return sum(max(table.get(g, default), 0) for g in A & B) / union


def _window_hours(state, now):
    """이번 실행의 수집 창(시간). 직전 실행 이후 + 여유, [WINDOW_HOURS, WINDOW_MAX_HOURS]."""
    hours = WINDOW_HOURS
    try:
        last = datetime.fromisoformat(state.get("last_run") or "")
        hours = max(hours, (now - last).total_seconds() / 3600 + WINDOW_MARGIN_HOURS)
    except (TypeError, ValueError):
        pass
    return min(hours, WINDOW_MAX_HOURS)


def _sent_match(m, state, now, drop=frozenset(), sim=None, single=None):
    """보낸 적 있나. 있으면 (저장 항목, 공유 토큰) — 없으면 None.

    엔티티가 겹치면 같은 사건의 다른 기사로 본다. 엔티티 차단은 TTL을 둔다 —
    같은 상대와의 *다른* 딜이 나중에 나올 수 있어서, 무기한 막으면 진짜 새 소식을
    놓친다.

    저장된 키에도 지금의 잡음 필터를 다시 건다. 예전에 오염된 키("ipo")가 상태
    파일에 남아 있어서, 새 키만 고치면 과거 기록이 3일간 계속 막는다.
    """
    title = m["headline"].strip().lower()
    for e in state.get("sent", []):
        try:
            ts = datetime.fromisoformat(e["ts"])
        except Exception:
            continue
        age = (now - ts).days
        if age <= TITLE_TTL_DAYS and e.get("title") == title:
            return e, {"(같은 제목)"}
        if age <= ENTITY_TTL_DAYS:
            shared = m["dkey"] & (set(e.get("key") or []) - drop)
            # 한 단어만 겹치면 single(제목 유사도)이 맞을 때만 같은 사건으로 본다.
            if shared and (len(shared) > 1 or single is None
                           or single(m["headline"], e.get("title", ""))):
                return e, shared
            if sim and sim(m["headline"], e.get("title", "")):
                return e, {"(유사 제목)"}
    return None


def _already_sent(m, state, now, drop=frozenset()):
    return _sent_match(m, state, now, drop) is not None

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


def _fetch_items(cfg, errors=None):
    """cfg.queries가 있으면 갈래별로 받아 제목 기준 합집합, 없으면 cfg.query 하나."""
    merged = {}
    for q in (cfg.queries or [cfg.query]):
        # 쿼리마다 따로 받는다. 예전엔 한 덩어리라 한 쿼리의 503이 나머지 결과까지
        # 버렸다(실측: 브랜치 테스트에서 첫 쿼리 503 → 수집 0). 일시 장애라 한 번 더 본다.
        for attempt in (1, 2):
            try:
                got = _fetch_one(q, cfg)
                break
            except Exception as e:
                print(f"  수집 실패({attempt}) {q}: {e}")
                got = []
                if attempt == 2 and errors is not None:
                    errors.append(f"news: {q}: {e}")
                if attempt == 1:
                    time.sleep(2)
        # 쿼리당 100건이 RSS 상한이다. 닿으면 넘친 기사가 조용히 사라지므로 표시한다.
        print(f"  수집 {len(got):3d}{' ⚠️ 상한' if len(got) >= 100 else ''}  {q}")
        for it in got:
            merged.setdefault(it["title"].lower(), it)
    return list(merged.values())


def _fetch_all(cfg, errors=None):
    """뉴스 레인과 IR 레인을 각각 격리해 수집 — 한쪽 장애가 다른 쪽을 침묵시키지 않게.

    둘 다 실패하면 빈 리스트라 알림이 안 나가고(가짜 알람 방지), 한쪽만 살아도
    그 몫은 발송된다. 예전엔 수집 전체가 하나의 try라 IR이 죽으면 뉴스도 죽었다.
    """
    errors = [] if errors is None else errors
    items = []
    try:
        items += _fetch_items(cfg, errors)
    except Exception as e:
        print(f"news fetch error: {e}")
        errors.append(f"news: {e}")
    items += _fetch_ir(cfg, errors)
    items += _fetch_rss(cfg, errors)
    return items


def _fetch_rss(cfg, errors):
    """일반 RSS. 피드별로 격리 — 한 곳이 죽어도 나머지와 뉴스 레인은 산다."""
    out = []
    for feed in cfg.rss_feeds:
        label = feed.get("label", "RSS")
        try:
            r = requests.get(feed["url"], timeout=20,
                             headers={"User-Agent": f"Mozilla/5.0 (nvidia-screener {cfg.label})"})
            r.raise_for_status()
            # 앞에 빈 줄을 두는 WordPress 피드가 있다 — 그대로면 파싱 실패.
            root = ET.fromstring(r.content.strip())
        except Exception as e:
            print(f"rss error ({label}): {e}")
            errors.append(f"{label}: {e}")
            continue
        pat = re.compile(feed["filter"], re.I) if feed.get("filter") else None
        for it in root.findall(".//item"):
            title = html.unescape((it.findtext("title") or "").strip())
            if not title:
                continue
            if pat and not pat.search(title + " " + (it.findtext("description") or "")):
                continue
            try:
                dt = parsedate_to_datetime((it.findtext("pubDate") or "").strip())
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            out.append({
                "title": title, "link": (it.findtext("link") or "").strip(),
                "source": label, "pub": "", "dt": dt, "authoritative": True,
                "pin": feed.get("group"),
            })
    return out


# IR 피드 타임스탬프는 미 동부시(ET)다. 실적 보도자료가 예외 없이 16:05:00,
# 즉 미국 장 마감 5분 뒤라 UTC일 수 없다(그랬다면 장중 12:05 PM ET).
try:
    from zoneinfo import ZoneInfo
    _IR_TZ = ZoneInfo("America/New_York")          # DST 자동 처리
except Exception:                                  # tzdata 없는 환경 폴백
    _IR_TZ = timezone(timedelta(hours=-5))         # EST. 25h 창에선 1시간 차가 무해


def _fetch_ir(cfg, errors=None):
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
            if errors is not None:
                errors.append(f"ir {y}: {e}")
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


# 와이어 서비스가 제목 앞에 붙이는 말머리. 기사 내용이 아니라 배급 메타데이터다.
# 안 떼면 중복제거 키에 "exclusive-nvidia" 같은 가짜 고유명사가 잡혀, 같은 사건인데
# 키가 안 겹쳐 중복 발송이 난다(실측: Anthropic IPO 건이 09-12·09-13 이틀 연속 발송).
WIRE_PREFIXES = ("exclusive-", "exclusive:", "breaking:", "corrected-", "refile-",
                 "update-", "update 1-", "update 2-", "update 3-", "analysis-",
                 "insight-", "factbox-", "timeline-")


def _strip_wire_prefix(headline):
    changed = True
    while changed:
        changed = False
        for p in WIRE_PREFIXES:
            if headline.lower().startswith(p):
                headline = headline[len(p):].lstrip(" -:").strip()
                changed = True
    return headline


_WORD_RE = re.compile(r"[a-z0-9$&.'’-]+")


_TRUNC_UNITS = ("billion", "million", "trillion")


def _looks_truncated(headline):
    """제목이 금액 단위 중간에서 잘렸나. 예: "... Invest up to $10 Bi"

    일부 매체(Moomoo 등)가 자체 길이 제한으로 제목을 자른 채 RSS에 싣는다.
    잘린 제목은 알림으로 쓸모가 없고(상대 기업명이 날아간다) 중복제거 키도
    못 만들어 같은 사건이 두 번 나간다 — 실측: Anthropic IPO 건이 09-12·09-13
    이틀 연속. 숫자 뒤 단위가 토막난 형태만 좁게 잡는다.
    """
    # 낱말 중간에서 잘린 형태도 있다: "... drives growth b". 끝이 소문자 한 글자면
    # 잘린 것이다(a·i는 낱말). 대문자는 "Plan B"처럼 정상 제목이라 대상이 아니다.
    if re.search(r"\s[b-hj-z]$", headline.strip()):
        return True
    toks = headline.lower().replace(",", " ").split()
    if len(toks) < 2:
        return False
    last = toks[-1].strip(".$")
    if not last or last in _TRUNC_UNITS:
        return False
    if not any(u.startswith(last) for u in _TRUNC_UNITS):
        return False
    prev = toks[-2].lstrip("$")
    return prev.replace(".", "").isdigit()


def _near_after(title, prox):
    """주체 토큰 뒤 window개 단어 안에 이벤트어가 오면 참.

    POSITIVE는 붙어 있는 문구만 본다("nvidia to invest"). 그런데 와이어 기사는
    문장형으로 쓴다 — "Nvidia in talks to invest", "Nvidia Mulls ... Backing".
    사이에 단어가 끼면 전부 탈락해서, 축약형 제목을 쓰는 어그리게이터만
    통과하는 편향이 생겼다(실측: 티어1·2 14건 중 통과 4건, 오탈락 3건이 전부
    같은 사건). 방향은 '뒤'로만 본다 — 이벤트어가 주체 앞에 있으면 보통
    나열 기사다("Zacks Investment Ideas ...: NVIDIA, Alphabet, AMD").
    """
    subjects = prox.get("subjects") or []
    terms = prox.get("terms") or []
    # 두 단어 이상짜리 근접어도 받는다. `investment`는 뒤 전치사로 뜻이 갈린다 —
    # "investment in SB Energy"는 NVIDIA의 투자고 "is a Good Investment"나
    # "$10,000 investment by 2027"은 NVDA 주식 얘기다. 6일간 `investment` 한
    # 단어로 통과한 확실한 신호는 0건, 잡음은 4건이었다.
    single = {t for t in terms if " " not in t}
    multi = [t.split() for t in terms if " " in t]
    window = prox.get("window", 6)
    toks = _WORD_RE.findall(title.lower())
    bare = [t.strip(".,;:!?'’-") for t in toks]
    for i, tok in enumerate(toks):
        if not any(sub in tok for sub in subjects):
            continue
        for j in range(i + 1, min(i + 1 + window, len(toks))):
            if bare[j] in single:
                return True
            for m in multi:
                if bare[j:j + len(m)] == m:
                    return True
    return False


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
    headline = _strip_wire_prefix(headline.rstrip(" .…").strip())
    return headline, source.strip()


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
    # POSITIVE(인접 문구) 또는 근접 규칙 중 하나만 맞으면 된다. 근접은 recall을
    # 더하기만 하므로 proximity를 안 쓰는 레인은 동작이 바뀌지 않는다.
    # positive가 비면 게이트를 걸지 않는다 — subject와 negative만으로 거르는
    # '해당 종목 뉴스 전부' 모드. PLTR 레인이 이 모드다(계약만이 아니라 논란·
    # 인사·경쟁 구도까지 받고 싶다는 요구). 비어 있을 때 any([])가 False라
    # 예전엔 전부 탈락했으므로 명시적으로 분기한다.
    if cfg.positive and not any(p in tl for p in cfg.positive):
        if not (cfg.proximity and _near_after(tl, cfg.proximity)):
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
portfolio
""".split())

# Title Case 제목에서는 흔한 단어도 대문자로 시작해 키에 들어온다(실측: 제목의 52%).
# 한 단어만 겹쳐도 다른 사건이 합쳐지고, 교차 실행 차단에선 3일간 사건을 통째로
# 삼킨다 — 2026-09-24에 NVIDIA의 SB Energy 추가 투자와 Iambic IPO가 "ipo" 하나로
# 사라진 걸 찾았다. 세 겹으로 거른다.
#   ① 약어: 항상 대문자라 소문자 근거로는 못 거른다. 닫힌 집합이라 목록이 맞다
#   ② 실측 목록: 2026-09-24 풀에서 키를 오염시킨 단어
#   ③ 흔한 단어 사전: 일반 비즈니스 기사에서 소문자로 쓰인 단어(build_common_words.py)
# 여기에 실행마다 그날 수집분에서 소문자로 쓰인 단어를 더한다(run_monitor).
# 틀릴 때는 '쪼개는' 쪽으로 틀리게 설계했다. 잘못 합치면 사건이 안 보이게
# 사라지지만, 잘못 쪼개면 중복 발송으로 눈에 보인다.
KEY_ACRONYMS = set("ipo ceo cfo cto ai us u.s uk eu nyse nasdaq gpu gpus etf spac "
                   "nvda pltr llm api".split())
KEY_MEASURED = set("""ipo files filing startup startups firm firms revenue valuation
infrastructure ahead just another push hit hits tests joins center centre wall street
drug president senior alliance alliances""".split())


def _load_common_words():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "common_words.json")
    try:
        with open(path, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception as e:
        print(f"  (흔한 단어 사전 로드 실패 — 약어·실측 목록만 사용: {e})")
        return set()


KEY_NOISE = KEY_ACRONYMS | KEY_MEASURED | _load_common_words()
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9&.\-]{2,}")


def _lowercase_words(headlines):
    """이번 실행 수집분에서 소문자로 쓰인 적 있는 단어. 회사 이름은 여기 안 걸린다."""
    out = set()
    for h in headlines:
        for tok in _TOKEN_RE.findall(h):
            if tok[0].islower():
                out.add(tok.lower().strip("."))
    return out


def _token_key(headline):
    """기존 중복제거 키 — 제목 앞 4토큰."""
    tokens = "".join(c if c.isalnum() else " " for c in headline.lower()).split()
    return {"".join(tokens[:4])}


def _term_hit(term, hl, word):
    if not word:
        return term in hl
    # 짧은 사명은 부분일치로 두면 남의 단어에 걸린다("rize" ⊂ prize·authorize).
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", hl) is not None


def _group_index(headline, cfg, pin=None):
    """제목이 속할 섹션. 앞에서부터 보고 terms가 비어 있으면 catch-all.

    terms(인접 문구)만 보면 분류가 필터와 같은 편향을 갖는다 — 문장형 제목이
    전부 catch-all로 떨어져서 "Nvidia Mulls $10B Anthropic IPO Backing"이
    '포트폴리오사 동향'에 들어갔다. 그래서 그룹도 근접 규칙을 볼 수 있게 한다.
    pin은 RSS 피드가 지정한 섹션 label — 있으면 키워드보다 우선한다.
    cfg.classify가 있으면 그 규칙 순서로 판정하고 groups는 표시용으로만 쓴다.
    """
    labels = [g["label"] for g in cfg.groups]
    if pin and pin in labels:
        return labels.index(pin)
    hl = headline.lower()
    if cfg.classify:
        for rule in cfg.classify:
            if any(_term_hit(t, hl, rule.get("word")) for t in rule["terms"]):
                return labels.index(rule["label"])
        return next((i for i, g in enumerate(cfg.groups)
                     if not g.get("terms") and not g.get("proximity")), len(labels) - 1)
    for i, g in enumerate(cfg.groups):
        terms = g.get("terms") or []
        prox = g.get("proximity")
        if not terms and not prox:
            return i
        if terms and any(_term_hit(t, hl, g.get("word")) for t in terms):
            return i
        if prox and _near_after(hl, prox):
            return i
    return len(cfg.groups) - 1


def _dedupe_key(headline, cfg, run_common=frozenset()):
    """같은 사건을 묶기 위한 키.

    1순위는 '상대 기업명' — 같은 딜을 여러 매체가 쓰면 상대 회사 이름이 겹친다.
    감시 대상 종목 자신(cfg.subject)과 필터 어휘는 모든 기사에 공통이라 제외한다.

    대문자 휴리스틱은 영문 전용이다. 한글 로케일에 쓰면 제목에 섞인 라틴 약어
    (DNV·IMO 등)가 기업명으로 잡혀 서로 다른 사건이 오병합되므로, 한글은
    기존 방식(앞 4토큰)을 그대로 쓴다. 영문도 엔티티가 안 나오면 같은 폴백.
    """
    if cfg.locale != "en":
        return _token_key(headline)
    hubs_all = set(cfg.key_ignore)
    drop = set(GENERIC) | KEY_NOISE | run_common | hubs_all
    for words in (cfg.subject, cfg.positive, cfg.negative):
        for w in words:
            drop.update(w.lower().split())
    out, hubs = set(), set()
    for tok in re.findall(r"[A-Z][A-Za-z0-9&.\-]{2,}", headline):
        t = tok.lower().strip(".")
        if t in hubs_all:
            hubs.add(t)
        elif t and t not in drop:
            out.add(t)
    # 허브(key_ignore)는 한 단어로는 사건을 잇지 못하게 뺐다. 그런데 제목에 허브만
    # 있으면 키가 비어 앞 4토큰 폴백으로 떨어지고, 그러면 "Singapore inks carbon
    # credit …"로 시작하는 베트남 협정과 태국 협정이 다시 묶인다. 허브 조합 전체를
    # 키 하나로 쓴다 — 조합이 같아야만 묶인다(싱가포르+베트남 ≠ 싱가포르+태국).
    if not out and hubs:
        out = {"+".join(sorted(hubs))}
    # 엔티티가 딱 하나인데 그게 감시 종목 자신이면 상대 기업명을 못 뽑은 것이다
    # (잘린 제목이 대표적: "Exclusive-Nvidia Plans to Invest up to $10 Bi"에서
    # Anthropic이 날아갔다). 이런 키로 엔티티 대조를 하면 같은 사건을 못 묶거나
    # 엉뚱한 기사를 묶는다. 엔티티가 없는 것으로 보고 폴백한다.
    if len(out) == 1 and any(s in next(iter(out)) for s in cfg.subject):
        out = set()
    return out or _token_key(headline)


def _set_output(found):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"found={'true' if found else 'false'}\n")


def _set_state_changed(changed):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"state_changed={'true' if changed else 'false'}\n")


def _write_log(cfg, now, fetched, matched, sent, errors):
    if not cfg.log_file:
        return
    row = {"ts": now.isoformat(), "label": cfg.label, "fetched": fetched,
           "matched": matched, "sent": len(sent), "errors": errors,
           "items": [{"group": m.get("grp", ""), "title": m["headline"],
                      "source": m["source"], "url": m["link"],
                      "date": m["dt"].strftime("%Y-%m-%d")} for m in sent]}
    d = os.path.dirname(cfg.log_file)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(cfg.log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_monitor(cfg):
    errors = []
    items = _fetch_all(cfg, errors)
    if not items:
        # 전 소스 실패 → 조용히 종료 (가짜 알람 방지)
        print("no items fetched")
        _write_log(cfg, datetime.now(timezone.utc), 0, 0, [], errors or ["no items"])
        _set_output(False)
        sys.exit(0)

    now = datetime.now(timezone.utc)
    state = _load_state(cfg)
    window = _window_hours(state, now)
    cutoff = now - timedelta(hours=window)
    # 수집이 일부라도 실패한 회차는 시작점을 옮기지 않는다 — 옮기면 그 쿼리가 놓친
    # 구간을 다음 회차도 안 본다. 그대로 두면 다음 창이 그만큼 넓어져 다시 훑는다.
    if not errors:
        state["last_run"] = now.isoformat()
    # 필터 통과 전 수집분 전체를 근거로 쓴다 — 통과분만 보면 근거가 더 얇아진다.
    run_common = _lowercase_words(
        _strip_source(it["title"], it.get("source", ""))[0] for it in items)
    sim = single = None
    if cfg.title_sim or cfg.cross_run_sim:
        idf = _idf_table([_strip_source(it["title"], it.get("source", ""))[0]
                          for it in items])
    if cfg.title_sim:
        sim = lambda a, b: _title_sim(a, b, idf) >= cfg.title_sim  # noqa: E731
    if cfg.cross_run_sim:
        single = lambda a, b: _title_sim(a, b, idf) >= cfg.cross_run_sim  # noqa: E731
    # 제외 매체가 낸 제목 — 다른 매체의 같은 제목(재게재본)도 뺄 때 쓴다.
    twins = set()
    if cfg.exclude_twins and cfg.exclude_sources:
        for it in items:
            h, src = _strip_source(it["title"], it.get("source", ""))
            if any(x in src.lower() for x in cfg.exclude_sources):
                twins.add(h.strip().lower())

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
            # 주가 문구로 걸렀는데 사건 단어도 있는 제목은 남긴다. "Japan weighs Palantir
            # AI defense system"처럼 뒤에 주가 표현이 붙은 진짜 뉴스가 여기서 사라지는지
            # 데이터로 보려고. 구제 규칙은 이 로그가 쌓인 뒤에 정한다.
            if not auth and cfg.groups:
                tl = headline.lower()
                neg = next((n for n in cfg.negative if n in tl), None)
                if (neg and (not cfg.subject or any(x in tl for x in cfg.subject))
                        and cfg.groups[_group_index(headline, cfg)].get("terms")):
                    print(f"  (주가 문구 '{neg}' 제외·사건어 있음) {headline}")
            continue
        if not auth and _looks_truncated(headline):
            print(f"  (잘린 제목 제외) {headline}")
            continue
        if not auth and cfg.exclude_sources:
            sl = source.lower()
            if any(x in sl for x in cfg.exclude_sources):
                print(f"  (제외 매체 {source}) {headline}")
                continue
        if not auth and headline.strip().lower() in twins:
            print(f"  (제외 매체 재게재 {source}) {headline}")
            continue

        matches.append({
            "headline": headline, "source": source,
            "link": it["link"], "dt": dt, "auth": auth, "pin": it.get("pin"),
            "dkey": _dedupe_key(headline, cfg, run_common),
        })

    # 중복 제거 — 같은 사건을 여러 매체가 쓰면 상대 기업명이 겹친다.
    # 앞 4토큰 키로는 "Palantir and Fujitsu renew…"와 "Fujitsu Signs New
    # Palantir…"가 안 묶여서 6칸짜리 알림이 한 사건으로 다 차버렸다.
    # 같은 사건이 공식 PR과 3자 기사 양쪽에 있으면 공식 쪽이 이긴다 — 정본
    # 제목·날짜·링크를 주므로. 정렬을 (정본 우선, 최신순)으로 두면 뒤에 오는
    # 3자 중복이 자연히 탈락한다.
    matches.sort(key=lambda x: (not x["auth"], _source_tier(x["source"]),
                               -x["dt"].timestamp()))
    deduped = []
    for m in matches:
        rep = next((d for d in deduped if m["dkey"] & d["dkey"]
                    or (sim and sim(m["headline"], d["headline"]))), None)
        if rep is not None:
            rep["dups"] = rep.get("dups", 0) + 1
            continue
        deduped.append(m)
    # 실행 간 차단 — 창이 겹치는 구간의 항목이 다음 회차에 다시 나가는 걸 막는다.
    # 무엇이 왜 막혔는지 남긴다. 예전엔 건수만 찍혀서 "ipo" 한 단어가 사건을
    # 삼켜도 2주간 아무도 몰랐다. 제목과 공유 토큰을 보면 오판인지 바로 보인다.
    drop = KEY_NOISE | run_common | set(cfg.key_ignore)
    fresh = []
    for m in deduped:
        hit = _sent_match(m, state, now, drop, sim, single)
        if hit is None:
            fresh.append(m)
            continue
        e, shared = hit
        print(f"  (이미 보냄) {m['headline'][:90]}")
        print(f"       ↳ 공유 {sorted(shared)} ← {e.get('title', '')[:80]}")
    if cfg.state_file and len(fresh) < len(deduped):
        print(f"  (이미 보낸 {len(deduped) - len(fresh)}건 제외)")
    deduped = fresh
    if cfg.groups:
        # 섹션별로 따로 쿼터를 준다. 한 덩어리에서 최신순으로 자르면 그날
        # 기사가 많은 쪽이 칸을 다 먹어 다른 섹션이 통째로 사라진다.
        buckets = [[] for _ in cfg.groups]
        for m in deduped:
            buckets[_group_index(m["headline"], cfg, m.get("pin"))].append(m)
        matches, over = [], []
        for g, b in zip(cfg.groups, buckets):
            b.sort(key=lambda x: x["dt"], reverse=True)
            cap = g.get("max", cfg.max_items)
            for m in b[:cap]:
                m["grp"] = g["label"]
                matches.append(m)
            for m in b[cap:]:
                m["grp"] = g["label"]
                over.append(m)
        # 남는 칸 넘기기 — 그날 빈 섹션의 칸을 넘치는 섹션에 준다. 섹션 칸은 '최소 보장'이
        # 되고 전체는 max_items가 막는다. 실측: 분류를 고치자 정책 기사 6건이 칸 3에
        # 걸려 ICE 소송 보도가 잘렸는데, 그날 계약 섹션 4칸은 비어 있었다.
        if cfg.spill_over:
            room = max(cfg.max_items - len(matches), 0)
            matches += over[:room]
            over = over[room:]
            order = [g["label"] for g in cfg.groups]
            matches.sort(key=lambda m: order.index(m["grp"]))   # 안정 정렬 — 섹션 안 순서 유지
        # 칸이 넘쳐 빠진 기사. 예전엔 흔적이 없어 칸 수가 맞는지 판단할 근거가 없었다.
        for m in over:
            print(f"  (섹션 칸 초과 {m['grp']}) {m['headline'][:90]}")
    else:
        deduped.sort(key=lambda x: x["dt"], reverse=True)
        matches = deduped[:cfg.max_items]

    print(f"window={window:.1f}h  fetched={len(items)}  matched={len(matches)}")
    for m in matches:
        print(f"  - {m['headline']}  [{m['source']}]")

    if not matches:
        # 보낼 게 없어도 실행 시각은 남긴다 — 다음 창이 여기서 시작해야 한다.
        _set_state_changed(_save_state(cfg, state))
        _write_log(cfg, now, len(items), 0, [], errors)
        _set_output(False)
        return

    kst = (now + timedelta(hours=9)).strftime("%Y-%m-%d")

    def build(items):
        lines = [cfg.header, "", f"⏰ {kst} KST", ""]
        cur = None
        for m in items:
            g = m.get("grp")
            if g and g != cur:
                if cur is not None:
                    lines.append("")
                lines.append(f"<b>{html.escape(g)}</b>")
                cur = g
            h = html.escape(m["headline"])
            link = html.escape(m["link"], quote=True)
            d = m["dt"].strftime("%Y-%m-%d")
            meta = f"{html.escape(m['source'])} · {d}" if m["source"] else d
            if cfg.show_dups and m.get("dups"):
                meta += f" · 같은 사건 외 {m['dups']}건"
            lines.append(f'• <a href="{link}">{h}</a>')
            lines.append(f"   <i>{meta}</i>")
        if len(items) < len(matches):
            lines.append(f"   <i>… 외 {len(matches) - len(items)}건</i>")
        lines += ["", cfg.footer]
        return "\n".join(lines)

    # 길이 초과 시 뒤에서부터 덜어낸다 — 전체가 거절당하느니 몇 건이라도.
    # 섹션은 우선순위 순으로 이어 붙어 있어서, 잘리는 건 낮은 섹션의 오래된
    # 항목부터다(포트폴리오사 잡담이 신규 투자 건을 밀어내지 않게).
    shown = list(matches)
    msg = build(shown)
    while len(msg) > TELEGRAM_LIMIT and len(shown) > 1:
        shown.pop()
        msg = build(shown)
    if len(shown) < len(matches):
        print(f"  (길이 제한: {len(matches)}건 중 {len(shown)}건만 전송)")

    with open(cfg.out_file, "w", encoding="utf-8") as f:
        f.write(msg)

    # 실제로 보낸 것만 기록한다 — 길이 제한으로 잘린 건 다음 회차에 다시 기회를 준다.
    for m in shown:
        state["sent"].append({"title": m["headline"].strip().lower(),
                              "key": sorted(m["dkey"]),
                              "ts": now.isoformat()})
    _set_state_changed(_save_state(cfg, state))
    _write_log(cfg, now, len(items), len(matches), shown, errors)

    _set_output(True)
