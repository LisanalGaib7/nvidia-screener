# NVIDIA Portfolio Tracker – What NVIDIA Invests In, in Real Time

**NVIDIA Portfolio Tracker** is a Streamlit dashboard that tracks the publicly listed companies NVIDIA holds or has invested in — sourced from SEC 13F filings — and prices them with real-time quotes. One place to see NVIDIA's strategic bets across semis, optical, cloud GPU, and robotics, with per-quarter filing history and YTD performance against benchmarks.

English | [한국어](#nvidia-portfolio-tracker-한국어)

![Python](https://img.shields.io/badge/Python-3.11-3776AB)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B)
![Plotly](https://img.shields.io/badge/Plotly-5.22+-3F4F75)

**Live at:** https://nvidiascreener.streamlit.app

## Demo

A dark, terminal-styled dashboard with a typed-scramble header intro, live metric cards (13F holdings, invested capital, average YTD, 52-week proximity), and lazy-loaded tabs for Portfolio, Performance, Sectors, News, and 13F History.

## Features

- **13F-based portfolio** — companies NVIDIA holds or invested in, classified by badge (new / core / partner / exited), with hover thesis (why NVIDIA invested, deal structure).
- **Real-time quotes** — Finnhub live prices overlaid on a daily fundamentals snapshot; a `LIVE` / `CLOSED` badge reflects market state, with graceful fallback to previous close.
- **Performance & sectors** — YTD return chart benchmarked against NVDA and the SOXX semiconductor ETF, plus sector-allocation pie charts.
- **13F filing history** — per-quarter position timeline (new / added / reduced / exited), with dates normalized to SEC filing schedules.
- **News & alerts** — investment-news feed, with Telegram automation for 13F filings, deal news, and macro-risk thresholds.
- **Bilingual & responsive** — Korean / English toggle, mobile layout, and a live visitor badge (concurrent sessions + cumulative users).

## How it works

Data is served in **two layers** to stay fresh without getting rate-limited:

- **Fast layer (real-time):** Finnhub `/quote` supplies live price, day change, and YTD for US tickers, cached in-app (TTL 90s, key-authenticated so shared-IP limits don't apply).
- **Slow layer (daily snapshot):** a GitHub Actions job runs `scripts/fetch_market_data.py` once a day to commit `data/market_data.json` — 1-year price history, market cap, P/E, 52-week range, FANUC (Tokyo), and USD/JPY. The app reads this file instead of calling Yahoo directly.

Filing data (dates, share counts, stakes) is sourced from **SEC 13F filings** and cross-checked against structured aggregators. SEC blocks cloud IPs, so the 13F monitor runs locally via n8n; news and snapshot monitors run on GitHub Actions.

## Tech Stack

- **App & charts** — Streamlit, Plotly
- **Data** — pandas, yfinance (daily snapshot), Finnhub API (real-time)
- **Automation** — GitHub Actions (snapshot, news, macro), n8n (SEC 13F monitor), Telegram Bot
- **Analytics** — Google Analytics 4 (Data API for the cumulative-users badge)
- **Deploy** — Streamlit Community Cloud

## Getting Started

### Environment variables

Create `.streamlit/secrets.toml`. Only `FINNHUB_API_KEY` is needed to run; the rest are optional.

| Key | Description |
| --- | --- |
| `FINNHUB_API_KEY` | Real-time US quotes. Omit → app falls back to previous-close snapshot. |
| `GA4_PROPERTY_ID` + `[gcp_service_account]` | Cumulative-users badge via GA4 Data API. Optional. |
| `[admin] password` | Password-gated feedback viewer. Optional. |
| `[telegram] bot_token`, `chat_id` | Telegram alerts for feedback / monitors. Optional. |

> Note: top-level keys (e.g. `FINNHUB_API_KEY`) must appear **before** any `[section]` header in TOML, or they get nested into that section.

### Install and run

```bash
pip install -r requirements.txt
streamlit run app.py
```

To refresh the market snapshot locally (otherwise handled by GitHub Actions):

```bash
python scripts/fetch_market_data.py
```

## Deployment

Deployed on **Streamlit Community Cloud**, auto-deploying from the `main` branch. The daily market snapshot is committed by a scheduled GitHub Actions workflow (`market_snapshot.yml`); secrets are configured in the Streamlit Cloud dashboard rather than committed.

Source is public for portfolio purposes. Not investment advice.

* * *

# NVIDIA Portfolio Tracker (한국어)

**NVIDIA Portfolio Tracker**는 엔비디아가 지분을 보유하거나 투자한 상장 기업을 SEC 13F 공시 기준으로 추적하고, 실시간 시세로 가격을 매기는 Streamlit 대시보드입니다. 반도체, 광학, 클라우드 GPU, 로보틱스에 걸친 엔비디아의 전략적 베팅을 한 화면에서, 분기별 공시 히스토리와 벤치마크 대비 YTD 성과와 함께 볼 수 있습니다.

[English](#nvidia-portfolio-tracker--what-nvidia-invests-in-in-real-time) | 한국어

![Python](https://img.shields.io/badge/Python-3.11-3776AB)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B)
![Plotly](https://img.shields.io/badge/Plotly-5.22+-3F4F75)

**배포 주소:** https://nvidiascreener.streamlit.app

## 데모

터미널 무드의 다크 대시보드. 타이핑 스크램블 헤더 인트로, 실시간 지표 카드(13F 보유·확인된 투자액·평균 YTD·52주 신고가 근접), 그리고 Portfolio·Performance·Sectors·News·13F History 탭(선택 탭만 렌더).

## 주요 기능

- **13F 기반 포트폴리오** — 엔비디아가 보유/투자한 기업을 배지(신규·코어·파트너·청산)로 분류하고, 호버 시 투자 논리(왜 투자했는지·투자 구조)를 표시.
- **실시간 시세** — 일일 펀더멘털 스냅샷 위에 Finnhub 실시간 가격을 오버레이. 장중/마감을 `LIVE`·`CLOSED` 배지로 표시하고, 실패 시 전일 종가로 폴백.
- **성과·섹터 분석** — NVDA·SOXX(반도체 ETF) 벤치마크와 비교하는 YTD 수익률 차트, 섹터별 배분 파이 차트.
- **13F 공시 히스토리** — 분기별 지분 변동(신규·증가·감소·청산) 타임라인, SEC 제출 스케줄에 맞춘 날짜 정규화.
- **뉴스·알림** — 투자 뉴스 피드, 13F 공시·딜 뉴스·매크로 위험 임계값에 대한 텔레그램 자동 알림.
- **한/영·반응형** — 한국어/영어 토글, 모바일 레이아웃, 실시간 방문자 배지(동시 접속 + 누적 사용자).

## 동작 방식

시세 데이터는 rate-limit 없이 신선함을 유지하기 위해 **2개 레이어**로 제공됩니다.

- **빠른 레이어(실시간):** Finnhub `/quote`가 US 종목의 현재가·일간 등락·YTD를 제공. 앱 내 캐시(TTL 90초, 키 인증이라 공유 IP 제한과 무관).
- **느린 레이어(일일 스냅샷):** GitHub Actions가 하루 1회 `scripts/fetch_market_data.py`를 실행해 `data/market_data.json`을 커밋 — 1년 종가 히스토리, 시총, PER, 52주 범위, FANUC(도쿄), USD/JPY. 앱은 Yahoo를 직접 호출하지 않고 이 파일을 읽습니다.

공시 데이터(날짜·주식수·지분율)는 **SEC 13F 공시**에서 가져와 구조화 애그리게이터와 교차 검증합니다. SEC는 클라우드 IP를 차단하므로 13F 모니터는 로컬 n8n에서, 뉴스·스냅샷 모니터는 GitHub Actions에서 돕니다.

## 기술 스택

- **앱·차트** — Streamlit, Plotly
- **데이터** — pandas, yfinance(일일 스냅샷), Finnhub API(실시간)
- **자동화** — GitHub Actions(스냅샷·뉴스·매크로), n8n(SEC 13F 모니터), 텔레그램 봇
- **분석** — Google Analytics 4(누적 사용자 배지용 Data API)
- **배포** — Streamlit Community Cloud

## 시작하기

### 환경 변수

`.streamlit/secrets.toml`을 만드세요. 실행에 필요한 건 `FINNHUB_API_KEY`뿐이고 나머지는 선택입니다.

| 키 | 설명 |
| --- | --- |
| `FINNHUB_API_KEY` | US 실시간 시세. 없으면 전일 종가 스냅샷으로 폴백. |
| `GA4_PROPERTY_ID` + `[gcp_service_account]` | GA4 Data API 기반 누적 사용자 배지. 선택. |
| `[admin] password` | 비밀번호로 보호되는 피드백 열람. 선택. |
| `[telegram] bot_token`, `chat_id` | 피드백·모니터 텔레그램 알림. 선택. |

> 참고: TOML에서 최상위 키(`FINNHUB_API_KEY` 등)는 반드시 `[section]` 헤더보다 **위**에 둬야 합니다. 아래에 두면 그 섹션에 nested 됩니다.

### 설치·실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

시장 스냅샷을 로컬에서 갱신하려면(평소엔 GitHub Actions가 처리):

```bash
python scripts/fetch_market_data.py
```

## 배포

**Streamlit Community Cloud**에 배포되며 `main` 브랜치에서 자동 배포됩니다. 일일 시장 스냅샷은 예약된 GitHub Actions 워크플로(`market_snapshot.yml`)가 커밋합니다. 시크릿은 커밋하지 않고 Streamlit Cloud 대시보드에서 설정합니다.

포트폴리오 목적의 공개 소스입니다. 투자 조언이 아닙니다.
