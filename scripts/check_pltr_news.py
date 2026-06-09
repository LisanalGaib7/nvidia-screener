"""
Palantir 계약·파트너십 뉴스 감지 — Google News RSS 기반
Palantir의 신규 계약(award), 파트너십, 주요 딜 뉴스를 감지해 Telegram 알림.
NVIDIA 전략 파트너(Sovereign AI OS)로서 계약 확장이 AI 사이클 선행지표.

소스: Google News RSS — FT·WSJ·Politico·NYT·Reuters·Bloomberg·Defense One 등
      investors.palantir.com 공식 PR은 Google News가 수분 내 인덱싱하므로 별도 스크래핑 불필요.
수집·필터·포맷 로직은 news_monitor.py 공용 코어에 있음 — 여기는 설정만.
"""
from news_monitor import MonitorConfig, run_monitor

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

CONFIG = MonitorConfig(
    query=QUERY, positive=POSITIVE, negative=NEGATIVE,
    header="🔵 <b>Palantir 계약·파트너십 감지</b>",
    footer="👉 NVIDIA 전략파트너 동향 확인",
    out_file="pltr_news_alert.txt",
    locale="en", label="pltr-news monitor",
)

if __name__ == "__main__":
    run_monitor(CONFIG)
