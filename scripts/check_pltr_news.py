"""
Palantir 계약·파트너십 뉴스 감지 — Google News RSS 기반
Palantir의 신규 계약(award), 파트너십, 주요 딜 뉴스를 감지해 Telegram 알림.
NVIDIA 전략 파트너(Sovereign AI OS)로서 계약 확장이 AI 사이클 선행지표.

소스: Google News RSS — 공식 PR도 Yahoo Finance 등이 원문 제목 그대로 재게시하므로
      palantir.com 스크래핑 없이 같은 텍스트를 잡는다.
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
]]

# 제목에 Palantir가 주체로 있어야 함 — 쿼리를 넓히면 협력사 소식이 섞여 들어온다
# (Rackspace·CoreWeave 등이 실제로 통과했음).
SUBJECT = ["palantir", "pltr"]

# 사업 이벤트 판별 — 어순 무관 단일 토큰
POSITIVE = [
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

# 주가·투자·인물 잡음 — POSITIVE를 넓힌 만큼 여기가 정밀도를 책임진다
NEGATIVE = [
    "stock", "shares", "valuation", "undervalued", "overvalued",
    "price target", "fair value", "bull case", "bearish", "bullish",
    "rally", "rallied", "jump", "climbs", "falls", "fell", "surge", "plunge",
    "slips", "rises", "climbed", "sparks", "best day", "sell-off", "insider",
    "earnings", "guidance", "quarterly", "rating", "upgrade", "downgrade",
    "investor", "investors", "should you buy", "consolidates", "support as",
    "casts a shadow", "closer to owning",
]

CONFIG = MonitorConfig(
    query=QUERIES[0], queries=QUERIES,
    positive=POSITIVE, negative=NEGATIVE, subject=SUBJECT,
    header="🔵 <b>Palantir 계약·파트너십 감지</b>",
    footer="👉 NVIDIA 전략파트너 동향 확인",
    out_file="pltr_news_alert.txt",
    locale="en", label="pltr-news monitor",
    max_items=10,   # 갈래 합집합이라 하루 이벤트가 6개를 넘는다 (실측 9건)
)

if __name__ == "__main__":
    run_monitor(CONFIG)
