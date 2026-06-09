"""
NVIDIA 투자 뉴스 감지 — Google News RSS 기반
NVIDIA가 다른 기업에 투자/지분참여한 뉴스를 감지해 Telegram으로 알림.
13F가 놓치는 '분기 중 전략투자 발표'(워런트/우선주/사모)를 커버.

수집·필터·포맷 로직은 news_monitor.py 공용 코어에 있음 — 여기는 설정만.
"""
from news_monitor import MonitorConfig, run_monitor

# Google News 검색 쿼리 — NVIDIA가 '주체'인 포트폴리오 변동(매수/13F/매도)만 좁힘
QUERY = (
    # 매수·투자
    '"nvidia invests" OR "nvidia-backed" OR "backed by nvidia" OR '
    '"nvidia investment" OR "nvidia takes stake" OR "nvidia leads" OR '
    '"nvidia buys stake" OR "nvidia acquires" OR "nvidia to invest" OR '
    # 13F·포트폴리오 변동
    '"nvidia 13f" OR "nvidia portfolio" OR "nvidia discloses" OR '
    # 매도·청산
    '"nvidia exits" OR "nvidia sells stake" OR "nvidia trims stake" OR '
    '"nvidia dumps" OR "nvidia reveals stake"'
)

# 제목 2차 필터 — NVIDIA가 주체(positive) / 남이 NVDA 주식을 사고파는 잡음(negative)
POSITIVE = [
    # 매수·투자
    "nvidia invests", "nvidia is investing", "nvidia to invest", "nvidia plans to invest",
    "nvidia-backed", "backed by nvidia", "nvidia backs",
    "nvidia investment", "nvidia takes stake", "nvidia takes a stake",
    "nvidia buys stake", "nvidia acquires", "nvidia-led",
    "nvidia bets", "nvidia commits", "nvidia pours", "nvidia stake in",
    "nvidia leads round", "nvidia leads investment", "nvidia leads funding",
    # 13F·포트폴리오 (쿼리가 nvidia로 스코프되므로 '13f' 단독 토큰도 안전)
    "13f", "nvidia portfolio", "nvidia's portfolio", "nvidia discloses", "nvidia reveals stake",
    # 매도·청산
    "nvidia exits", "nvidia sells stake", "nvidia trims", "nvidia dumps",
    "nvidia reduces", "nvidia dissolves", "nvidia cuts stake",
]
NEGATIVE = [
    # NVIDIA가 '대상'인 잡음 — 남이 NVDA 주식을 매매
    "purchased by", "sold by", "shares of nvidia", "stake in nvidia",
    "position in nvidia", "stake by", "holdings in nvidia",
    "shares purchased", "shares sold", "has stake in nvidia",
    "in nvidia stock", "of nvidia stock",
    "boosts nvidia", "trims nvidia", "buys nvidia", "sells nvidia",
    "lowers nvidia", "raises nvidia", "cuts nvidia", "reduces nvidia",
]

CONFIG = MonitorConfig(
    query=QUERY, positive=POSITIVE, negative=NEGATIVE,
    header="🟢 <b>NVIDIA 투자 뉴스 감지</b>",
    footer="👉 트래커 업데이트 검토 필요",
    out_file="news_alert.txt",
    locale="en", label="news monitor",
)

if __name__ == "__main__":
    run_monitor(CONFIG)
