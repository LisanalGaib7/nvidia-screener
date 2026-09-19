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


def _already_sent(m, state, now):
    """보낸 적 있나. 엔티티가 겹치면 같은 사건의 다른 기사로 본다.

    엔티티 차단은 TTL을 둔다 — 같은 상대와의 *다른* 딜이 나중에 나올 수 있어서,
    무기한 막으면 진짜 새 소식을 놓친다.
    """
    title = m["headline"].strip().lower()
    for e in state.get("sent", []):
        try:
            ts = datetime.fromisoformat(e["ts"])
        except Exception:
            continue
        age = (now - ts).days
        if age <= TITLE_TTL_DAYS and e.get("title") == title:
            return True
        if age <= ENTITY_TTL_DAYS and m["dkey"] & set(e.get("key") or []):
            return True
    return False

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
    terms = set(prox.get("terms") or [])
    window = prox.get("window", 6)
    toks = _WORD_RE.findall(title.lower())
    for i, tok in enumerate(toks):
        if not any(sub in tok for sub in subjects):
            continue
        for w in toks[i + 1:i + 1 + window]:
            if w.strip(".,;:!?'’-") in terms:
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


def _token_key(headline):
    """기존 중복제거 키 — 제목 앞 4토큰."""
    tokens = "".join(c if c.isalnum() else " " for c in headline.lower()).split()
    return {"".join(tokens[:4])}


def _group_index(headline, cfg):
    """제목이 속할 섹션. 앞에서부터 보고 terms가 비어 있으면 catch-all.

    terms(인접 문구)만 보면 분류가 필터와 같은 편향을 갖는다 — 문장형 제목이
    전부 catch-all로 떨어져서 "Nvidia Mulls $10B Anthropic IPO Backing"이
    '포트폴리오사 동향'에 들어갔다. 그래서 그룹도 근접 규칙을 볼 수 있게 한다.
    """
    hl = headline.lower()
    for i, g in enumerate(cfg.groups):
        terms = g.get("terms") or []
        prox = g.get("proximity")
        if not terms and not prox:
            return i
        if terms and any(t in hl for t in terms):
            return i
        if prox and _near_after(hl, prox):
            return i
    return len(cfg.groups) - 1


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
        if not auth and _looks_truncated(headline):
            print(f"  (잘린 제목 제외) {headline}")
            continue
        if not auth and cfg.exclude_sources:
            sl = source.lower()
            if any(x in sl for x in cfg.exclude_sources):
                print(f"  (제외 매체 {source}) {headline}")
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
    matches.sort(key=lambda x: (not x["auth"], _source_tier(x["source"]),
                               -x["dt"].timestamp()))
    deduped = []
    for m in matches:
        if any(m["dkey"] & d["dkey"] for d in deduped):
            continue
        deduped.append(m)
    # 실행 간 차단 — 창이 겹치는 구간의 항목이 다음 회차에 다시 나가는 걸 막는다.
    state = _load_state(cfg)
    fresh = [m for m in deduped if not _already_sent(m, state, now)]
    if cfg.state_file and len(fresh) < len(deduped):
        print(f"  (이미 보낸 {len(deduped) - len(fresh)}건 제외)")
    deduped = fresh
    if cfg.groups:
        # 섹션별로 따로 쿼터를 준다. 한 덩어리에서 최신순으로 자르면 그날
        # 기사가 많은 쪽이 칸을 다 먹어 다른 섹션이 통째로 사라진다.
        buckets = [[] for _ in cfg.groups]
        for m in deduped:
            buckets[_group_index(m["headline"], cfg)].append(m)
        matches = []
        for g, b in zip(cfg.groups, buckets):
            b.sort(key=lambda x: x["dt"], reverse=True)
            for m in b[:g.get("max", cfg.max_items)]:
                m["grp"] = g["label"]
                matches.append(m)
    else:
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
    changed = _save_state(cfg, state)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"state_changed={'true' if changed else 'false'}\n")

    _set_output(True)
