"""
Palantir 계약·파트너십 뉴스 감지 — Google News RSS 기반
Palantir의 신규 계약(award), 파트너십, 주요 딜 뉴스를 감지해 Telegram 알림.
NVIDIA 전략 파트너(Sovereign AI OS)로서 계약 확장이 AI 사이클 선행지표.

소스 2종:
  1) Google News RSS — 3자 매체 커버리지. 계약 종료·논란처럼 PR로 안 나오는 것 담당.
     무편집 소방호스(하루 100건+)라 아래 POSITIVE/NEGATIVE 필터가 필요하다.
  2) Palantir IR 보도자료 피드 — 공식 발표의 정본 제목·날짜·링크 담당. 연 44건으로
     이미 편집된 목록이라 **필터를 걸지 않는다**(실적 발표 포함). 같은 사건이 양쪽에
     있으면 정본이 이긴다.
수집·필터·포맷 로직은 news_monitor.py 공용 코어에 있음 — 여기는 설정만.

쿼리를 4갈래로 나눈 이유: Palantir는 하루 100건 넘게 기사가 나와서 단일 쿼리로는
RSS 상한(100)에 걸려 뒷부분이 잘린다. 실측으로 단일 쿼리 100건 vs 4갈래 합집합
143건 — 43건이 조용히 사라지고 있었다.

어순을 쿼리에 박지 않는 이유: 예전엔 "palantir wins" 같은 2어절 구문으로 좁혔는데,
실제 헤드라인은 "NVIDIA and Palantir bring…", "Palantir and Nebius Partner",
"Palantir to Deliver…"처럼 상대 기업이 앞이나 중간에 온다. 2026-09-10 공식 PR 4건이
전부 이 이유로 안 잡혔다. 지금은 쿼리·POSITIVE 모두 어순 무관 단일 토큰이고,
대신 subject 가드와 NEGATIVE로 정밀도를 잡는다.
"""
from news_monitor import MonitorConfig, run_monitor

# 주제 갈래 — 각각 RSS 상한(100) 아래로 유지. 실측 when:2d 기준 57/39/49/50건.
#
# when:2d를 쿼리에 넣는 게 필수다. 빼면 Google이 기간 무제한 관련도순으로 주는데,
# 100건 상한을 옛 기사가 채워서 정작 어제 나온 계약 기사가 밀려난다(실측: when 없이
# 361건 받아 5건 매칭 → when:2d로 9건). WINDOW_HOURS=25 필터는 그 다음 단계라
# 애초에 안 실려온 기사는 살릴 수 없다.
_WHEN = " when:2d"
QUERIES = [q + _WHEN for q in [
    "Palantir (contract OR awarded OR award OR wins OR won OR secures)",
    "Palantir (partnership OR partners OR alliance OR collaborate OR teams)",
    "Palantir (selects OR selected OR names OR taps OR picks OR chooses OR adopts)",
    "Palantir (announces OR launches OR deploys OR deployment OR expands OR rollout)",
]] + [
    # 위 4갈래는 계약·제휴 어휘라 CEO 발언·논란 기사를 놓친다(실측 2일에 4~5건:
    # "Palantir CEO Says Businesses Are 'Unhappy'…", Engadget ICE 보도). 제목에 사명이
    # 있어야 한다는 건 subject 가드와 같은 조건이라 intitle이 정확히 맞는다.
    # 1일로 둔다 — 2일이면 평일에 100건 상한에 닿을 수 있다(일요일~월요일 1일 34건, 2일 55건).
    "intitle:palantir when:1d",
]

# 제목에 Palantir가 주체로 있어야 함 — 쿼리를 넓히면 협력사 소식이 섞여 들어온다
# (Rackspace·CoreWeave 등이 실제로 통과했음).
SUBJECT = ["palantir", "pltr"]

# 사업 이벤트 판별 — 어순 무관 단일 토큰
CONTRACT = [
    # 계약·수주
    "contract", "awarded", "award", "wins", "won", "secures", "secured",
    # 선정·채택
    "selects", "selected", "names", "taps", "picks", "chooses", "adopts",
    # 파트너십·협업
    "partner", "partners", "partnership", "alliance", "teams up",
    "collaborate", "signs", "agreement", "deal",
    # 발표·배포·확장
    "deploys", "deployment", "expands", "expand", "integrates", "launches",
    "announces", "announce", "deliver", "provide", "adds",
    "pilot", "rollout", "implementation",
    # 계약 종료도 사업 이벤트다 (Coles 사례)
    "to end", "ends", "drops", "terminates",
]


# POSITIVE 게이트는 해제했다. 계약·파트너십만 받던 레인이었는데, 실제로 걸러지던
# 것 중에 이란 학교 폭격 연루 보도·CHCI 이사회 지급 스쿠프·간호사노조 반대처럼
# 투자 판단에 더 중요한 게 많았다(실측: 이벤트 5 → 17, 티어1 1 → 3, 잃는 건 0).
# 이제 subject(palantir/pltr)와 NEGATIVE만으로 거른다.
POSITIVE = []
# 주가·투자·인물 잡음 — POSITIVE를 넓힌 만큼 여기가 정밀도를 책임진다
NEGATIVE = [
    "stock", "shares", "valuation", "undervalued", "overvalued",
    "price target", "fair value", "bull case", "bearish", "bullish",
    "rally", "rallied", "jump", "climbs", "falls", "fell", "surge", "plunge",
    "slips", "rises", "climbed", "sparks", "best day", "sell-off", "insider",
    "earnings", "guidance", "quarterly", "rating", "upgrade", "downgrade",
    "investor", "investors", "should you buy", "consolidates", "support as",
    "casts a shadow", "closer to owning",
    # 옵션·거래량 기사 — 예전 POSITIVE의 "contract"가 "Contracts Were Traded"에 걸렸다
    "options", "open interest", "contracts were traded",
    # POSITIVE 게이트를 푼 대신 주가·트레이딩 기사는 여기서 막는다. 포지션은
    # 트래커로 이미 보고 있어 중복이고, 양이 늘면 진짜 뉴스가 길이 제한에 밀린다.
    "priced in", "moat", "power ranking", "break above", "reversal",
    "nasdaq:pltr", "short-term", "buy now", "price prediction",
    "technical analysis", "resistance", "support level", "peers",
    "forecast", "target price", "analyst", "short interest",
    "all-time high", "52-week",
    # "Palantir Just Hit a One-Year High. Here's What's Driving It" — Yahoo가 실은
    # 주가 기사라 매체로 못 막았다. 30일간 이 표현이 든 제목 4건이 전부 주가·시황
    "year high",
    # 남이 PLTR을 사고판 기사 — 09-19~24 발송분에서 샘(Burry·Cathie Wood·트럼프)
    "trades in", "shorts", "sold palantir", "bought palantir",
    "buys palantir", "sells palantir",
    # Moomoo 종목 카드("$Palantir (PLTR.US)$"). 기사가 아니다. 매체는 막지 않는다 —
    # 같은 Moomoo가 진짜 뉴스도 싣는다. 형식만 막는다. 브랜치 테스트 발송에서 나왔다.
    ".us)$",
    # 제목에 티커를 괄호로 단 형식 — "(PLTR)", "(NASDAQ:PLTR)". 7일 29건 전부 주가
    # 논평·내부자 지분 공시였고 그것만 다룬 사건은 0건이었다.
    "(pltr)", "pltr)",
    # 남의 회사가 팔란티어 방식을 따라 한다는 기사("SAP Taps Palantir-Style Strike Teams")
    "palantir-style", "palantir-like",
    "jim cramer",
]

# 주가 논평이 본업인 매체. 이 레인은 POSITIVE 게이트가 없어 NEGATIVE 문구가
# 유일한 방어선인데, 09-19에 주가 어휘 19개를 넣고도 5일 만에 새 표현 6개가
# 샜다 — 문구로는 두더지 잡기다. 매체라는 구조적 특징으로 막는다.
# 7일 풀 기준 사건 손실 0. NVIDIA 레인엔 쓰지 않는다 — 거기선 TipRanks·
# Seeking Alpha가 진짜 딜(SharonAI, Einride)을 실어 날라 사건 2개를 잃었다.
# Seeking Alpha·GuruFocus는 같은 이유로 목록에서 뺐다.
STOCK_COMMENTARY = [
    "tipranks", "motley fool", "fool.com", "simplywall.st", "simply wall st",
    "benzinga", "trefis", "24/7 wall st", "marketbeat", "zacks",
    "investorplace", "stocktwits", "stockstotrade", "traders union",
    # 10-05 추가. 7일 풀에서 이 매체들만 다룬 사건 0건. tradersunion은 RSS 표기가
    # "tradersunion.com"이라 위의 "traders union"에 안 걸리고 있었다.
    "tradersunion", "insider monkey", "tradingkey", "pluang", "kalkine", "quiver",
]

# 섹션 — 앞에서부터 보고 terms가 빈 항이 catch-all.
# 분류 순서가 곧 표시·삭감 순서다. 길이 초과 시 뒤 섹션부터 잘리므로 중요한 걸
# 앞에 둔다. 계약 어휘에서 맨 "deal"은 뺐다 — "Hires … With NHS Deal in Limbo"
# 같은 인사 기사를 계약으로 끌어가기 때문이다.
DEAL = ["contract", "awarded", "award", "wins", "won", "secures", "secured",
        "partner", "partners", "partnership", "alliance", "teams up",
        "signs deal", "deal with", "agreement", "selects", "selected",
        "adopts", "pilot", "piloting", "deploys", "deployment", "rollout",
        "using palantir", "taps palantir", "expands", "integrates"]
POLICY = ["probe", "lawsuit", "sues", "sued", "investigation", "scrutiny",
          "protest", "purge", "union", "watchdog", "privacy", "surveillance",
          "backlash", "criticism", "controversy", "accountability", "ethics",
          "regulation", "guidelines", "urges", "warn", "warns", "scoop",
          "bombing", "senator", "congress", "hearing", "ban", "immigration"]
# 인사 기사는 동사가 제각각이다 — hires/appoints/joins 외에 "takes senior job",
# "takes a senior role"처럼 명사구로도 쓴다. 실측에서 이 형태가 catch-all로 샜다.
PEOPLE = ["hires", "hired", "hiring", "appoints", "appointed", "joins",
          "taps ex", "resigns", "steps down", "departs", "vice president",
          "senior vice", "names ex", "senior job", "senior role",
          "senior post", "top job", "takes senior", "new chief"]

# 경쟁 구도는 별도 섹션으로 뺀다. catch-all에 같이 두니 7건이 몰려 쿼터 2를
# 놓고 경쟁했고, 날짜순이라 클릭베이트("Putin DESTROYS…")가 Thales 경쟁사
# 기사를 밀어냈다. 관심 있는 갈래는 자기 칸을 가져야 한다.
RIVAL = ["alternative", "alternatives", "rival", "rivals", "competitor",
         "competitors", "counterweight", "challenger", "sovereign",
         "orchestration", "integration", "launches", "launch", "foundry",
         "ontology", "nvidia", "takes on palantir"]

# 섹션 판정 규칙 — 표시 순서(GROUPS)와 따로 둔다. 논란을 먼저 본다: "NHS 계약을
# 끝내라", "계약 취소 동의안"이 'contract' 때문에 계약 섹션으로 가고 있었다.
# 단어 경계로 맞춘다(word) — 부분일치면 'ban'이 bank에, 'ice'가 price에 걸린다.
# 그래서 복수형은 따로 적는다. 실측(사람이 정답을 매긴 52건): 25 → 47.
# 일부러 안 넣은 말: union(European Union 계약), march(3월), demand(AI demand).
POLICY_RULE = [t for t in POLICY if t != "union"] + """ice protests protester protesters campaign campaigners boycott petition
motion unions lawsuits sue probe inquiry regulator criticising critics scandal lobbyist lobbying
threatening fears concerns bans banned scrap scraps cancel cancels cancelled cancellation evict
evicting senators lawmakers mp mps questioned dhs deportation strike urge warned purge activists
object objections oppose opposition halt""".split() + [
    "day of action", "to end", "must end", "end its", "kick out", "tear up",
    "replace palantir", "trade union", "nurses union", "cut ties", "hands off"]
RIVAL_STRONG = ["answer to palantir", "alternative to palantir", "alternative", "alternatives",
                "rival", "rivals", "competitor", "competitors", "challenger", "counterweight",
                "takes on palantir", "differentiates"]
DEAL_RULE = DEAL + ["contracts", "partnerships", "deals", "use palantir", "uses palantir",
                    "now use", "go with palantir", "clients", "customers", "payment", "adopt"]
PEOPLE_RULE = PEOPLE + ["ceo", "executive", "founder", "co-founder", "karp", "thiel",
                        "move to palantir"]
CLASSIFY = [
    {"label": "🏛 정책·논란",     "terms": POLICY_RULE,  "word": True},
    {"label": "🤝 기술·제휴·경쟁", "terms": RIVAL_STRONG, "word": True},
    {"label": "📄 계약·파트너십",  "terms": DEAL_RULE,    "word": True},
    {"label": "🤝 기술·제휴·경쟁", "terms": RIVAL,        "word": True},
    {"label": "👤 회사·인사",     "terms": PEOPLE_RULE,  "word": True},
]

GROUPS = [
    {"label": "📄 계약·파트너십",  "terms": DEAL,   "max": 4},
    {"label": "🏛 정책·논란",     "terms": POLICY, "max": 3},
    {"label": "🤝 기술·제휴·경쟁", "terms": RIVAL,  "max": 2},
    {"label": "👤 회사·인사",     "terms": PEOPLE, "max": 1},
    {"label": "📰 그 외",         "terms": [],     "max": 1},
]

# 공식 보도자료 피드 — 뉴스룸 페이지가 실제로 호출하는 IR 플랫폼 API.
# 관행적인 /rss·/feed 경로로는 못 찾는 이름이라, 페이지의 네트워크 요청을
# 직접 관측해서 알아냈다(performance.getEntriesByType('resource')).
# bodyType=0은 본문 제외 — 제목·날짜·링크만 필요한데 본문까지 받으면 1MB다(80KB로 줄어듦).
IR_FEED = {
    "url": "https://investors.palantir.com/feed/PressRelease.svc/GetPressReleaseList",
    "params": {"languageId": 1, "bodyType": 0,
               "includeTags": "true", "pressReleaseDateFilter": 1},
    "base": "https://investors.palantir.com",
    "label": "Palantir IR",
}

CONFIG = MonitorConfig(
    query=QUERIES[0], queries=QUERIES,
    positive=POSITIVE, negative=NEGATIVE, subject=SUBJECT,
    header="🔵 <b>Palantir 뉴스</b>",
    footer="👉 NVIDIA 전략파트너 동향 확인",
    state_file="data/pltr_news_state.json",
    out_file="pltr_news_alert.txt",
    locale="en", label="pltr-news monitor",
    max_items=10,   # 갈래 합집합이라 하루 이벤트가 6개를 넘는다 (실측 9건)
    ir_feed=IR_FEED,
    groups=GROUPS,
    classify=CLASSIFY,
    exclude_sources=STOCK_COMMENTARY,
    exclude_twins=True,
    spill_over=True,   # 분류를 고치자 정책 기사가 칸 3을 넘는 날이 생겼다(10-05 실측 6건)
    # 한 단어만 겹친 과거 발송은 제목이 비슷할 때만 같은 사건으로 본다. 차단 27건을
    # 사람이 판정해 재봤다: 다른 사건인데 막힌 것 8 → 1, 진짜 중복 차단 10 → 8.
    # 같은 사건 쌍은 0.27 이상, 다른 사건은 0.22 이하(7일·1일 두 기준에서 같음).
    # 간격이 좁고 표본이 작아 차단 로그로 계속 본다.
    cross_run_sim=0.25,
)

if __name__ == "__main__":
    run_monitor(CONFIG)
