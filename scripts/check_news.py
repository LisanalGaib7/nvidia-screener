"""
NVIDIA 투자 뉴스 감지 — Google News RSS 기반
NVIDIA가 다른 기업에 투자/지분참여한 뉴스와, 이미 투자한 포트폴리오사의
동향을 감지해 Telegram으로 알림. 13F가 놓치는 '분기 중 전략투자 발표'
(워런트/우선주/사모)를 커버.

수집·필터·포맷 로직은 news_monitor.py 공용 코어에 있음 — 여기는 설정만.
"""
from news_monitor import MonitorConfig, run_monitor

# Google News 검색 쿼리 — 갈래 분할.
#
# 두 가지를 실측해서 이 모양이 됐다.
# (1) 최상위가 따옴표 구의 OR 체인이면 when: 절이 통째로 무시된다. 구 쿼리에
#     when:2d/when:7d를 붙여도 100건 · 2026-07-26~09-10로 동일했다.
#     nvidia (A OR B) 괄호 그룹으로 바꾸면 먹는다.
# (2) 괄호 그룹이어도 쿼리가 넓어지면 Google이 날짜 제약을 버린다. 길이 문제가
#     아니다 — 12항 180자는 74건/1일치인데, 항을 늘리면 2019년 기사까지 온다
#     (더미 7항 추가 시 2730일치). 그래서 각 갈래를 좁게 유지하고 합집합을 쓴다.
#
# 실측(2026-09-12): 58 / 55 / 13 / 33건, 전부 최근 1일치, 합집합 148건.
_WHEN = " when:2d"
QUERIES = [q + _WHEN for q in [
    'nvidia (invests OR investing OR "to invest" OR investment OR backs)',
    'nvidia (acquires OR acquisition OR "takes stake" OR "buys stake" OR '
    '"sells stake" OR "trims stake" OR exits)',
    'nvidia ("nvidia-backed" OR "backed by nvidia" OR "nvidia-funded")',
    'nvidia ("leads round" OR "leads funding" OR "nvidia-led" OR 13F OR portfolio)',
]]

# NVIDIA가 '주체'인 사건 — 새 투자·인수·청산. 트래커 갱신이 필요한 쪽.
ACTOR = [
    # 매수·투자
    "nvidia invests", "nvidia is investing", "nvidia to invest", "nvidia plans to invest",
    "nvidia backs", "nvidia investment", "nvidia takes stake", "nvidia takes a stake",
    "nvidia buys stake", "nvidia acquires",
    # "nvidia-led" 단독은 "Qualcomm takes aim at Nvidia-led AI market"까지 먹는다
    "nvidia-led round", "nvidia-led funding", "nvidia-led investment",
    "nvidia bets", "nvidia commits", "nvidia pours", "nvidia stake in",
    "nvidia leads round", "nvidia leads investment", "nvidia leads funding",
    # 13F·포트폴리오 (쿼리가 nvidia로 스코프되므로 '13f' 단독 토큰도 안전)
    "13f", "nvidia portfolio", "nvidia's portfolio", "nvidia discloses", "nvidia reveals stake",
    # 매도·청산
    "nvidia exits", "nvidia sells stake", "nvidia trims", "nvidia dumps",
    "nvidia reduces", "nvidia dissolves", "nvidia cuts stake",
]
# NVIDIA가 '수식어'인 사건 — 이미 투자한 회사의 자체 소식. 신규 투자는 아니지만
# 포트폴리오 추적이 이 레인의 목적이라 버리지 않고 별도 섹션으로 보낸다.
EPITHET = [
    "nvidia-backed", "backed by nvidia", "nvidia backed", "nvidia-funded",
]

POSITIVE = ACTOR + EPITHET
NEGATIVE = [
    # NVIDIA가 '대상'인 잡음 — 남이 NVDA 주식을 매매
    "purchased by", "sold by", "shares of nvidia", "stake in nvidia",
    "position in nvidia", "stake by", "holdings in nvidia",
    "shares purchased", "shares sold", "has stake in nvidia",
    "in nvidia stock", "of nvidia stock",
    "boosts nvidia", "trims nvidia", "buys nvidia", "sells nvidia",
    "lowers nvidia", "raises nvidia", "cuts nvidia", "reduces nvidia",
    # 사건 보도가 아닌 의견·주식홍보 장르. 포트폴리오사 동향은 남기되 이건 뺀다.
    "screaming buy", "meet the", "could become", "next nvidia", "should you buy",
    "need to own", "here are the best", "takes aim at",
    # "NVDA에 얼마 넣었으면 지금 얼마" 류. 실제로 09-14에 한 건 나갔다.
    "would grow to", "would be worth", "years ago", "if you invested",
    "if you had invested", "turned $", "$1,000 in",
    # marketbeat류 기관 보유 기사. 근접 규칙을 켜면서 새로 들어왔다 —
    # 기존 NEGATIVE가 "shares purchased/sold"만 막고 "Shares Acquired by"와
    # "Largest Position"은 안 막고 있었다.
    "shares acquired", "largest position", "investment advisers",
    "investment advisory", "investment solutions", "advisory services",
    # 인물 발언. 근접 규칙의 `backs`는 '출자'와 '지지' 두 뜻인데, 주어가 사람이면
    # 후자다 — 이틀간 "Nvidia CEO backs Trump…" 계열 4건이 통과했고 1건은 발송까지
    # 갔다. `invests`·`acquires`·`stake`엔 이 모호함이 없어 `backs`만 문제다.
    # `ceo says`/`huang says`는 일부러 뺐다 — "Nvidia Stock Gains After $3.5B
    # MediaTek Investment - Jensen Huang Says"처럼 진짜 딜 기사에 붙는 꼬리다.
    "ceo backs", "huang backs", "chief backs", "ceo declares",
]

# 근접 규칙 — POSITIVE의 인접 문구를 못 맞추는 문장형 제목 구제.
# "Nvidia in talks to invest", "Nvidia Mulls $10B ... Backing"처럼 주체와 동사
# 사이에 단어가 끼는 건 와이어 기사의 기본 문체다. POSITIVE만 쓰면 축약형
# 제목(어그리게이터)만 통과해서, 메이저 매체가 구조적으로 탈락한다.
#
# terms는 어간이 아니라 정확한 토큰이다. `back`을 넣으면 "Jim Cramer Names
# NVIDIA the Main Portfolio Running Back"이 통과한다.
PROXIMITY = {
    "subjects": ["nvidia"],
    "terms": {
        "invest", "invests", "investing", "invested", "investment", "investments",
        "stake", "stakes", "acquire", "acquires", "acquired", "acquiring",
        "acquisition", "backs", "backing", "backed", "funds", "funding",
        "mulls", "weighs", "eyes", "bets", "commits", "pours", "injects",
        "buys", "13f",
    },
    "window": 6,
}

# 섹션 — 앞에서부터 보고 terms가 빈 항이 catch-all.
GROUPS = [
    {"label": "📈 신규 투자·인수", "terms": ACTOR, "proximity": PROXIMITY, "max": 5},
    {"label": "🏢 포트폴리오사 동향", "terms": [], "max": 4},
]

CONFIG = MonitorConfig(
    query=QUERIES[0], queries=QUERIES,
    positive=POSITIVE, negative=NEGATIVE,
    header="🟢 <b>NVIDIA 투자 뉴스 감지</b>",
    footer="👉 트래커 업데이트 검토 필요",
    state_file="data/nvidia_news_state.json",
    out_file="news_alert.txt",
    locale="en", label="news monitor",
    groups=GROUPS, max_items=9, proximity=PROXIMITY,
    # 영상은 알림 링크로 안 맞는다. 09-15에 유튜브 영상 한 건이 그날의
    # 유일한 알림으로 나갔다 — 근접 규칙의 `buys`에 걸렸다.
    # 출처 표기가 "YouTube"일 때와 "youtu.be"일 때가 다 관측돼 둘 다 넣는다.
    exclude_sources=["youtube", "youtu.be"],
)

if __name__ == "__main__":
    run_monitor(CONFIG)
