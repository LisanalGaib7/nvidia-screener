import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date
import time

st.set_page_config(
    page_title="NVIDIA 투자 기업 스크리너",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 스타일 ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .stApp { background-color: #0d0d0d; }

  .alert-banner {
    background: linear-gradient(135deg, #1a1a00 0%, #2d2000 100%);
    border: 2px solid #f59e0b;
    border-radius: 12px;
    padding: 14px 20px;
    margin-bottom: 16px;
    animation: pulse-border 2s infinite;
  }
  @keyframes pulse-border {
    0%, 100% { border-color: #f59e0b; }
    50%       { border-color: #fcd34d; box-shadow: 0 0 12px #f59e0b66; }
  }
  .alert-title { color: #f59e0b; font-size: 1rem; font-weight: 700; margin:0 0 6px; }
  .alert-item  { color: #fde68a; font-size: 0.88rem; margin: 3px 0; }

  .badge-hot     { background:#76b900; color:#000; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
  .badge-new     { background:#f59e0b; color:#000; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
  .badge-core    { background:#3b82f6; color:#fff; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
  .badge-watch   { background:#6b7280; color:#fff; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
  .badge-partner { background:#7c3aed; color:#fff; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }

  .positive { color: #22c55e; font-weight: 700; }
  .negative { color: #ef4444; font-weight: 700; }

  .news-card {
    background: #111827;
    border-left: 3px solid #76b900;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
  }
  .news-title { color: #f9fafb; font-size: 0.9rem; font-weight: 600; }
  .news-meta  { color: #6b7280; font-size: 0.75rem; margin-top: 3px; }

  .filing-row {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 6px;
  }
  .filing-new      { border-left: 4px solid #22c55e; }
  .filing-increase { border-left: 4px solid #76b900; }
  .filing-decrease { border-left: 4px solid #ef4444; }
  .filing-exit     { border-left: 4px solid #6b7280; }
  .filing-hold     { border-left: 4px solid #3b82f6; }

  h1, h2, h3 { color: #f9fafb !important; }
  .stMarkdown p { color: #d1d5db; }
  div[data-testid="stMetricValue"] { color: #76b900 !important; font-size: 1.6rem !important; }
  div[data-testid="stMetricLabel"] { color: #9ca3af !important; }
</style>
""", unsafe_allow_html=True)

# ─── NVIDIA 투자 기업 데이터 ────────────────────────────────────────────────
NVIDIA_PORTFOLIO = [
    # ── 신규 투자 알림 대상 (2024~2025) ──────────────────────────────
    {
        "ticker": "NBIS",
        "name": "Nebius Group",
        "sector": "클라우드 GPU",
        "invest_year": 2024,
        "invest_amt_m": 100.0,
        "nvidia_thesis": "유럽·이스라엘 AI 클라우드 인프라 — H100 기반 GPU 클라우드 구축",
        "badge": "new",
        "exchange": "NASDAQ",
        "note": "$100M 전략적 투자 (2024.12) | 전 Yandex NV",
        "is_new_alert": True,
        "alert_date": "2024-12-10",
    },
    {
        "ticker": "CRWV",
        "name": "CoreWeave",
        "sector": "클라우드 GPU",
        "invest_year": 2025,
        "invest_amt_m": None,
        "nvidia_thesis": "NVIDIA GPU 특화 하이퍼스케일러 — H100/B200 최대 보유 클라우드",
        "badge": "new",
        "exchange": "NASDAQ",
        "note": "2025.03 IPO | NVIDIA 전략적 주주·최대 고객",
        "is_new_alert": True,
        "alert_date": "2025-03-28",
    },
    {
        "ticker": "6954.T",
        "name": "FANUC",
        "sector": "산업 로봇",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "산업용 로봇 + AI — Isaac for Manipulators 플랫폼 파트너십",
        "badge": "new",
        "exchange": "TSE",
        "note": "Isaac Manipulators 파트너십 (2024) | 도쿄 상장",
        "is_new_alert": True,
        "alert_date": "2024-06-03",
    },
    # ── 핵심 전략 투자 ────────────────────────────────────────────────
    {
        "ticker": "RXRX",
        "name": "Recursion Pharmaceuticals",
        "sector": "AI 신약개발",
        "invest_year": 2023,
        "invest_amt_m": 50.0,
        "nvidia_thesis": "AI+생물학 융합 — BioNeMo 플랫폼 파트너십, 전략적 지분 투자",
        "badge": "core",
        "exchange": "NASDAQ",
        "note": "$50M 전략적 투자 공식 발표 (2023.07)",
        "is_new_alert": False,
    },
    {
        "ticker": "ARM",
        "name": "Arm Holdings",
        "sector": "반도체 IP",
        "invest_year": 2023,
        "invest_amt_m": None,
        "nvidia_thesis": "CPU·엣지 AI IP — NVIDIA Grace CPU의 기반 아키텍처",
        "badge": "core",
        "exchange": "NASDAQ",
        "note": "2023.09 IPO | 전략적 파트너십 (인수 시도 이력)",
        "is_new_alert": False,
    },
    # ── HOT 투자 ──────────────────────────────────────────────────────
    {
        "ticker": "SOUN",
        "name": "SoundHound AI",
        "sector": "AI/음성인식",
        "invest_year": 2023,
        "invest_amt_m": 3.99,
        "nvidia_thesis": "음성 AI 엣지 추론 — NVIDIA GPU 기반 실시간 음성인식 플랫폼",
        "badge": "hot",
        "exchange": "NASDAQ",
        "note": "2024 13F 공시 확인 | 이후 일부 매도",
        "is_new_alert": False,
    },
    {
        "ticker": "SERV",
        "name": "Serve Robotics",
        "sector": "자율주행 로봇",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "라스트마일 자율배달 로봇 — Jetson Orin 플랫폼 레퍼런스 파트너",
        "badge": "hot",
        "exchange": "NASDAQ",
        "note": "주요 주주 | Jetson Orin 탑재",
        "is_new_alert": False,
    },
    {
        "ticker": "COHR",
        "name": "Coherent Corp",
        "sector": "광학 트랜시버",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "800G/1.6T 광트랜시버 — AI 데이터센터 고속 인터커넥트 핵심",
        "badge": "hot",
        "exchange": "NYSE",
        "note": "전략적 공급망 투자 | 광학 인터커넥트",
        "is_new_alert": False,
    },
    # ── WATCH ─────────────────────────────────────────────────────────
    {
        "ticker": "NNOX",
        "name": "Nano-X Imaging",
        "sector": "AI 의료영상",
        "invest_year": 2023,
        "invest_amt_m": None,
        "nvidia_thesis": "디지털 X-ray + AI 진단 — NVIDIA Clara 파이프라인 연동",
        "badge": "watch",
        "exchange": "NASDAQ",
        "note": "13F 공시 확인 (2023)",
        "is_new_alert": False,
    },
    {
        "ticker": "LITE",
        "name": "Lumentum Holdings",
        "sector": "광학 부품",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "레이저·광학 부품 — AI 클러스터 광 네트워킹 인프라",
        "badge": "watch",
        "exchange": "NASDAQ",
        "note": "전략적 관계 | 광학 공급망",
        "is_new_alert": False,
    },
    {
        "ticker": "APLD",
        "name": "Applied Digital",
        "sector": "AI 데이터센터",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "NVIDIA GPU 기반 HPC/AI 클라우드 데이터센터 운영",
        "badge": "watch",
        "exchange": "NASDAQ",
        "note": "NVIDIA GPU 공급 파트너십",
        "is_new_alert": False,
    },
    {
        "ticker": "JOBY",
        "name": "Joby Aviation",
        "sector": "eVTOL",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "자율비행 eVTOL — NVIDIA Drive 플랫폼 적용",
        "badge": "watch",
        "exchange": "NYSE",
        "note": "NVIDIA Drive 파트너십",
        "is_new_alert": False,
    },
    # ── 전략적 파트너십 (지분투자 아님) ─────────────────────────────
    {
        "ticker": "INTC",
        "name": "Intel",
        "sector": "반도체/파운드리",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "Intel Foundry Services — Blackwell 일부 칩 위탁생산 협력. 지분투자 아닌 공급망 파트너십.",
        "badge": "partner",
        "exchange": "NASDAQ",
        "note": "⚠️ 직접 지분투자 아님 | IFS 파운드리 파트너십 (2024) | AI칩 시장 경쟁자이기도 함",
        "is_new_alert": False,
    },
]

# ─── 13F 공시 히스토리 데이터 ─────────────────────────────────────────────
# 출처: SEC EDGAR 13F 공시 (분기별 기관투자자 보유 내역)
FILINGS_HISTORY = [
    # SOUN
    {"ticker":"SOUN","company":"SoundHound AI","quarter":"Q4 2023","filed":"2024-02-14","shares":1726520,"value_m":3.99,"change":"신규","change_type":"new"},
    {"ticker":"SOUN","company":"SoundHound AI","quarter":"Q1 2024","filed":"2024-05-15","shares":1726520,"value_m":None,"change":"유지","change_type":"hold"},
    {"ticker":"SOUN","company":"SoundHound AI","quarter":"Q2 2024","filed":"2024-08-14","shares":None,"value_m":None,"change":"일부 매도","change_type":"decrease"},
    # RXRX
    {"ticker":"RXRX","company":"Recursion Pharma","quarter":"Q3 2023","filed":"2023-11-14","shares":None,"value_m":50.0,"change":"전략투자 ($50M)","change_type":"new"},
    {"ticker":"RXRX","company":"Recursion Pharma","quarter":"Q4 2023","filed":"2024-02-14","shares":None,"value_m":None,"change":"유지","change_type":"hold"},
    {"ticker":"RXRX","company":"Recursion Pharma","quarter":"Q1 2024","filed":"2024-05-15","shares":None,"value_m":None,"change":"유지","change_type":"hold"},
    # NNOX
    {"ticker":"NNOX","company":"Nano-X Imaging","quarter":"Q4 2023","filed":"2024-02-14","shares":None,"value_m":None,"change":"신규","change_type":"new"},
    {"ticker":"NNOX","company":"Nano-X Imaging","quarter":"Q1 2024","filed":"2024-05-15","shares":None,"value_m":None,"change":"유지","change_type":"hold"},
    # SERV
    {"ticker":"SERV","company":"Serve Robotics","quarter":"Q1 2024","filed":"2024-05-15","shares":None,"value_m":None,"change":"신규","change_type":"new"},
    {"ticker":"SERV","company":"Serve Robotics","quarter":"Q2 2024","filed":"2024-08-14","shares":None,"value_m":None,"change":"유지","change_type":"hold"},
    {"ticker":"SERV","company":"Serve Robotics","quarter":"Q3 2024","filed":"2024-11-14","shares":None,"value_m":None,"change":"증가","change_type":"increase"},
    # NBIS
    {"ticker":"NBIS","company":"Nebius Group","quarter":"Q4 2024","filed":"2024-12-10","shares":None,"value_m":100.0,"change":"전략투자 ($100M)","change_type":"new"},
    # CRWV
    {"ticker":"CRWV","company":"CoreWeave","quarter":"Q1 2025","filed":"2025-03-28","shares":None,"value_m":None,"change":"IPO 참여·전략 주주","change_type":"new"},
    # COHR
    {"ticker":"COHR","company":"Coherent Corp","quarter":"Q2 2024","filed":"2024-08-14","shares":None,"value_m":None,"change":"신규","change_type":"new"},
    {"ticker":"COHR","company":"Coherent Corp","quarter":"Q3 2024","filed":"2024-11-14","shares":None,"value_m":None,"change":"유지","change_type":"hold"},
    # ARM
    {"ticker":"ARM","company":"Arm Holdings","quarter":"Q3 2023","filed":"2023-09-14","shares":None,"value_m":None,"change":"IPO 참여","change_type":"new"},
    {"ticker":"ARM","company":"Arm Holdings","quarter":"Q4 2023","filed":"2024-02-14","shares":None,"value_m":None,"change":"유지","change_type":"hold"},
    # FANUC
    {"ticker":"6954.T","company":"FANUC","quarter":"Q2 2024","filed":"2024-06-03","shares":None,"value_m":None,"change":"파트너십 체결","change_type":"new"},
    # INTC
    {"ticker":"INTC","company":"Intel","quarter":"Q1 2024","filed":"2024-02-21","shares":None,"value_m":None,"change":"IFS 파운드리 계약","change_type":"new"},
]

CHANGE_STYLE = {
    "new":      ("filing-new",      "🟢 신규"),
    "increase": ("filing-increase", "📈 증가"),
    "decrease": ("filing-decrease", "📉 감소"),
    "exit":     ("filing-exit",     "⬛ 청산"),
    "hold":     ("filing-hold",     "🔵 유지"),
}

BADGE_MAP = {
    "hot":     '<span class="badge-hot">🔥 HOT</span>',
    "core":    '<span class="badge-core">⭐ CORE</span>',
    "new":     '<span class="badge-new">🆕 NEW</span>',
    "watch":   '<span class="badge-watch">👁 WATCH</span>',
    "partner": '<span class="badge-partner">🤝 PARTNER</span>',
}

SECTOR_COLORS = {
    "AI/음성인식": "#76b900", "AI 신약개발": "#22d3ee",
    "자율주행 로봇": "#f59e0b", "AI 의료영상": "#a78bfa",
    "클라우드 GPU": "#3b82f6", "광학 트랜시버": "#ec4899",
    "광학 부품": "#fb7185", "반도체 IP": "#34d399",
    "AI 데이터센터": "#60a5fa", "산업 로봇": "#fbbf24",
    "eVTOL": "#c084fc", "반도체/파운드리": "#94a3b8",
}

# ─── 데이터 fetch ──────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_stock_data(tickers):
    result = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            hist = t.history(period="1y")
            price = (info.get("currentPrice") or info.get("regularMarketPrice")
                     or (hist["Close"].iloc[-1] if not hist.empty else None))
            prev  = info.get("regularMarketPreviousClose") or (
                hist["Close"].iloc[-2] if len(hist) > 1 else price)
            change_pct = ((price - prev) / prev * 100) if price and prev else None
            ytd_start = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
            ytd_pct = ((price - ytd_start.iloc[0]) / ytd_start.iloc[0] * 100
                       if not ytd_start.empty and price else None)
            result[ticker] = {
                "price": price, "change_pct": change_pct,
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "week52_high": info.get("fiftyTwoWeekHigh"),
                "week52_low":  info.get("fiftyTwoWeekLow"),
                "ytd_pct": ytd_pct, "hist": hist,
                "currency": info.get("currency", "USD"),
            }
        except Exception as e:
            result[ticker] = {"error": str(e)}
    return result

@st.cache_data(ttl=600)
def fetch_news(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.news or []
    except:
        return []

def fmt_cap(v):
    if v is None: return "—"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    if v >= 1e6:  return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"

def fmt_price(v, currency="USD"):
    if v is None: return "—"
    sym = "¥" if currency == "JPY" else "$"
    return f"{sym}{v:,.2f}"

def fmt_pct(v):
    if v is None: return "—"
    color = "positive" if v >= 0 else "negative"
    arrow = "▲" if v >= 0 else "▼"
    return f'<span class="{color}">{arrow} {abs(v):.2f}%</span>'

def fmt_ratio(v):
    return f"{v:.1f}x" if v else "—"

def ts_to_str(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except:
        return ""

# ─── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🟢 NVIDIA 투자 필터")
    st.markdown("---")
    sectors = sorted({c["sector"] for c in NVIDIA_PORTFOLIO})
    sel_sectors = st.multiselect("섹터", sectors, default=sectors)
    badges = {"hot":"🔥 HOT","core":"⭐ CORE","new":"🆕 NEW","watch":"👁 WATCH","partner":"🤝 PARTNER"}
    sel_badges = st.multiselect("투자 등급", list(badges.values()), default=list(badges.values()))
    sel_badge_keys = [k for k,v in badges.items() if v in sel_badges]
    exchanges = sorted({c["exchange"] for c in NVIDIA_PORTFOLIO})
    sel_exchanges = st.multiselect("거래소", exchanges, default=exchanges)
    st.markdown("---")
    sort_by = st.selectbox("정렬 기준", ["YTD 수익률","시가총액","일간 등락률","P/E 비율","회사명"])
    st.markdown("---")
    st.markdown("""
**⚠️ 면책조항**

SEC 13F 공시 및 NVIDIA 공식 발표 기반.
투자 조언이 아니며 지분 변동 있을 수 있음.

**데이터:** Yahoo Finance (~15분 지연)
""")
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─── 필터링 & 데이터 로드 ─────────────────────────────────────────────────
filtered = [c for c in NVIDIA_PORTFOLIO
            if c["sector"] in sel_sectors
            and c["badge"] in sel_badge_keys
            and c["exchange"] in sel_exchanges]
tickers = [c["ticker"] for c in filtered]

with st.spinner("실시간 주가 데이터 불러오는 중..."):
    stock_data = fetch_stock_data(tickers)

# ─── 🚨 신규 투자 알림 배너 ───────────────────────────────────────────────
new_alerts = [c for c in NVIDIA_PORTFOLIO if c.get("is_new_alert")]
if new_alerts:
    alert_items = "".join([
        f'<div class="alert-item">▶ <b>{c["name"]} ({c["ticker"]})</b> — '
        f'{c["note"].split("|")[0].strip()} '
        f'<span style="color:#6b7280;font-size:0.8rem">{c.get("alert_date","")}</span></div>'
        for c in sorted(new_alerts, key=lambda x: x.get("alert_date",""), reverse=True)
    ])
    st.markdown(f"""
    <div class="alert-banner">
      <div class="alert-title">🚨 NVIDIA 신규 투자 알림 — {len(new_alerts)}건</div>
      {alert_items}
    </div>
    """, unsafe_allow_html=True)

# ─── 헤더 ─────────────────────────────────────────────────────────────────
st.markdown("# 🟢 NVIDIA 투자 기업 스크리너")
st.markdown("NVIDIA가 직접 투자·지분 보유한 상장사를 추적합니다. 출처: SEC 13F · NVIDIA IR · 공식 파트너십 발표")
st.markdown("---")

# ─── 요약 지표 ────────────────────────────────────────────────────────────
ytd_values = [stock_data[c["ticker"]].get("ytd_pct")
              for c in filtered
              if stock_data.get(c["ticker"], {}).get("ytd_pct") is not None]
avg_ytd = sum(ytd_values)/len(ytd_values) if ytd_values else None
positive_count = sum(1 for v in ytd_values if v > 0)
total_invest = sum(c["invest_amt_m"] for c in filtered if c.get("invest_amt_m"))

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("추적 기업 수", f"{len(filtered)}개")
with c2: st.metric("평균 YTD 수익률", f"{avg_ytd:+.1f}%" if avg_ytd else "—")
with c3: st.metric("YTD 플러스 기업", f"{positive_count} / {len(ytd_values)}개")
with c4: st.metric("공개 확인 투자액", f"${total_invest:.0f}M+" if total_invest else "—")

st.markdown("---")

# ─── 메인 탭 ──────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 기업 목록", "📈 차트 비교", "🗺️ 섹터 분석",
    "📰 뉴스 피드", "📊 13F 공시 히스토리"
])

# ══ Tab 1: 기업 목록 ════════════════════════════════════════════════════════
with tab1:
    def get_sort_val(c):
        sd = stock_data.get(c["ticker"], {})
        if sort_by == "YTD 수익률":  return sd.get("ytd_pct") or -9999
        if sort_by == "시가총액":     return sd.get("market_cap") or 0
        if sort_by == "일간 등락률":  return sd.get("change_pct") or -9999
        if sort_by == "P/E 비율":    return sd.get("pe_ratio") or 9999
        return c["name"]

    sorted_companies = sorted(filtered, key=get_sort_val,
                               reverse=(sort_by not in ["회사명","P/E 비율"]))

    hcols = st.columns([2.5, 1.2, 1.3, 1.3, 1.2, 1.2, 1.2, 1.5, 2])
    for h, col in zip(["기업","현재가","일간등락","YTD","시총","P/E","P/S","52주범위","투자 근거"], hcols):
        col.markdown(f"**{h}**")
    st.markdown('<hr style="margin:4px 0;border-color:#374151">', unsafe_allow_html=True)

    for company in sorted_companies:
        ticker = company["ticker"]
        sd = stock_data.get(ticker, {})
        if "error" in sd:
            st.warning(f"{ticker}: 데이터 로드 실패")
            continue

        price = sd.get("price"); currency = sd.get("currency","USD")
        w52h = sd.get("week52_high"); w52l = sd.get("week52_low")

        if w52h and w52l and price:
            pct_pos = max(0, min(100, (price - w52l) / (w52h - w52l) * 100))
            bar_html = (f'<div style="font-size:0.7rem;color:#6b7280">'
                        f'{fmt_price(w52l,currency)} ━ {fmt_price(w52h,currency)}<br>'
                        f'<div style="background:#374151;border-radius:3px;height:4px;margin-top:2px">'
                        f'<div style="background:#76b900;width:{pct_pos:.0f}%;height:4px;border-radius:3px"></div></div>'
                        f'<span style="color:#76b900">{pct_pos:.0f}% of range</span></div>')
        else:
            bar_html = "—"

        cols = st.columns([2.5, 1.2, 1.3, 1.3, 1.2, 1.2, 1.2, 1.5, 2])
        invest_note = f"${company['invest_amt_m']:.0f}M" if company.get("invest_amt_m") else ""
        with cols[0]:
            st.markdown(
                f"**{company['name']}** ({ticker})<br>"
                f"{BADGE_MAP[company['badge']]} "
                f"<span style='color:#6b7280;font-size:0.75rem'>{company['sector']}</span>"
                + (f"&nbsp;·&nbsp;<span style='color:#76b900;font-size:0.75rem'>{invest_note}</span>" if invest_note else ""),
                unsafe_allow_html=True)
        with cols[1]: st.markdown(fmt_price(price, currency), unsafe_allow_html=True)
        with cols[2]: st.markdown(fmt_pct(sd.get("change_pct")), unsafe_allow_html=True)
        with cols[3]: st.markdown(fmt_pct(sd.get("ytd_pct")), unsafe_allow_html=True)
        with cols[4]: st.markdown(fmt_cap(sd.get("market_cap")))
        with cols[5]: st.markdown(fmt_ratio(sd.get("pe_ratio")))
        with cols[6]: st.markdown(fmt_ratio(sd.get("ps_ratio")))
        with cols[7]: st.markdown(bar_html, unsafe_allow_html=True)
        with cols[8]:
            with st.expander("📌"):
                st.markdown(f"**투자 근거:** {company['nvidia_thesis']}")
                st.markdown(f"**출처:** {company['note']}")
                st.markdown(f"**투자 시작:** {company['invest_year']}년")

        st.markdown('<hr style="margin:2px 0;border-color:#1f2937">', unsafe_allow_html=True)

# ══ Tab 2: 차트 비교 ════════════════════════════════════════════════════════
with tab2:
    st.markdown("### YTD 주가 성과 비교")
    chart_companies = [c for c in filtered if "error" not in stock_data.get(c["ticker"],{})]

    if chart_companies:
        fig = go.Figure()
        for company in chart_companies:
            sd = stock_data[company["ticker"]]
            hist = sd.get("hist")
            if hist is None or hist.empty: continue
            ytd_hist = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
            if ytd_hist.empty: continue
            norm = ytd_hist / ytd_hist.iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=norm.index, y=norm.values,
                name=f"{company['name']} ({company['ticker']})",
                line=dict(color=SECTOR_COLORS.get(company["sector"],"#76b900"), width=2),
                hovertemplate=f"<b>{company['name']}</b><br>%{{y:.1f}}<extra></extra>",
            ))
        fig.add_hline(y=100, line_dash="dash", line_color="#6b7280",
                       annotation_text="YTD 시작점")
        fig.update_layout(template="plotly_dark", paper_bgcolor="#111827",
                           plot_bgcolor="#111827", height=520,
                           yaxis_title="정규화 주가 (100 = YTD 시작)",
                           legend=dict(bgcolor="#1f2937"),
                           margin=dict(l=0,r=0,t=20,b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### YTD 수익률 순위")
    ytd_data = [{"ticker":c["ticker"],"name":c["name"],"ytd":stock_data.get(c["ticker"],{}).get("ytd_pct")}
                for c in filtered if stock_data.get(c["ticker"],{}).get("ytd_pct") is not None]
    if ytd_data:
        df_ytd = pd.DataFrame(ytd_data).sort_values("ytd", ascending=True)
        fig2 = go.Figure(go.Bar(
            x=df_ytd["ytd"], y=df_ytd["ticker"], orientation="h",
            marker_color=["#22c55e" if v>=0 else "#ef4444" for v in df_ytd["ytd"]],
            text=[f"{v:+.1f}%" for v in df_ytd["ytd"]], textposition="outside",
            hovertemplate="<b>%{y}</b><br>YTD: %{x:.2f}%<extra></extra>",
        ))
        fig2.update_layout(template="plotly_dark", paper_bgcolor="#111827",
                            plot_bgcolor="#111827", height=max(300, len(df_ytd)*38),
                            xaxis_title="YTD 수익률 (%)",
                            margin=dict(l=0,r=80,t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True)

# ══ Tab 3: 섹터 분석 ════════════════════════════════════════════════════════
with tab3:
    col_a, col_b = st.columns(2)
    with col_a:
        sc = {}
        for c in filtered: sc[c["sector"]] = sc.get(c["sector"],0)+1
        fig3 = go.Figure(go.Pie(labels=list(sc.keys()), values=list(sc.values()),
            marker_colors=[SECTOR_COLORS.get(s,"#6b7280") for s in sc], hole=0.4))
        fig3.update_layout(template="plotly_dark", paper_bgcolor="#111827",
                            title="섹터별 기업 수", title_font_color="#f9fafb",
                            height=380, margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig3, use_container_width=True)
    with col_b:
        scap = {}
        for c in filtered:
            cap = stock_data.get(c["ticker"],{}).get("market_cap") or 0
            scap[c["sector"]] = scap.get(c["sector"],0) + cap
        scap = {k:v for k,v in scap.items() if v>0}
        if scap:
            fig4 = go.Figure(go.Pie(labels=list(scap.keys()), values=list(scap.values()),
                marker_colors=[SECTOR_COLORS.get(s,"#6b7280") for s in scap], hole=0.4))
            fig4.update_layout(template="plotly_dark", paper_bgcolor="#111827",
                                title="섹터별 시가총액", title_font_color="#f9fafb",
                                height=380, margin=dict(l=0,r=0,t=40,b=0))
            st.plotly_chart(fig4, use_container_width=True)

    sector_ytd = {}
    for c in filtered:
        ytd = stock_data.get(c["ticker"],{}).get("ytd_pct")
        if ytd is not None:
            sector_ytd.setdefault(c["sector"],[]).append(ytd)
    if sector_ytd:
        avg_s = {s: sum(v)/len(v) for s,v in sector_ytd.items()}
        df_s = pd.DataFrame([(s,v) for s,v in avg_s.items()],
                             columns=["섹터","평균 YTD (%)"]).sort_values("평균 YTD (%)",ascending=False)
        fig5 = px.bar(df_s, x="섹터", y="평균 YTD (%)",
                       color="평균 YTD (%)",
                       color_continuous_scale=["#ef4444","#374151","#22c55e"],
                       color_continuous_midpoint=0, template="plotly_dark")
        fig5.update_layout(paper_bgcolor="#111827", plot_bgcolor="#111827",
                            height=360, margin=dict(l=0,r=0,t=10,b=0),
                            coloraxis_showscale=False)
        st.plotly_chart(fig5, use_container_width=True)

# ══ Tab 4: 뉴스 피드 ════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 종목별 최신 뉴스")
    st.caption("Yahoo Finance 뉴스 기준 · 클릭 시 원문 이동")

    news_tickers = [c for c in filtered if "error" not in stock_data.get(c["ticker"],{})]

    # 종목 선택
    ticker_names = {c["ticker"]: f"{c['name']} ({c['ticker']})" for c in news_tickers}
    selected_ticker = st.selectbox("종목 선택", list(ticker_names.keys()),
                                    format_func=lambda x: ticker_names[x])

    selected_company = next((c for c in filtered if c["ticker"] == selected_ticker), None)
    if selected_company:
        sd = stock_data.get(selected_ticker, {})
        n1, n2, n3 = st.columns(3)
        with n1: st.metric("현재가", fmt_price(sd.get("price"), sd.get("currency","USD")))
        with n2: st.markdown(f"**일간등락:** {fmt_pct(sd.get('change_pct'))}", unsafe_allow_html=True)
        with n3: st.markdown(f"**YTD:** {fmt_pct(sd.get('ytd_pct'))}", unsafe_allow_html=True)

        st.markdown("---")
        with st.spinner(f"{selected_ticker} 뉴스 불러오는 중..."):
            news_items = fetch_news(selected_ticker)

        if news_items:
            shown = 0
            for item in news_items[:15]:
                content = item.get("content", {})
                title   = content.get("title") or item.get("title","")
                summary = content.get("summary","")
                pub_ts  = (content.get("pubDate") or
                           item.get("providerPublishTime") or
                           item.get("published",""))
                pub_str = ""
                if isinstance(pub_ts, (int, float)):
                    pub_str = ts_to_str(pub_ts)
                elif isinstance(pub_ts, str) and pub_ts:
                    pub_str = pub_ts[:10]
                url = (content.get("canonicalUrl",{}).get("url","") or
                       item.get("link","") or item.get("url",""))
                provider = (content.get("provider",{}).get("displayName","") or
                            item.get("publisher",""))
                if not title: continue
                shown += 1
                link_html = f'<a href="{url}" target="_blank" style="text-decoration:none;color:inherit">' if url else ""
                link_end  = "</a>" if url else ""
                st.markdown(f"""
                <div class="news-card">
                  <div class="news-title">{link_html}{title}{link_end}</div>
                  <div class="news-meta">{pub_str} &nbsp;·&nbsp; {provider}</div>
                  {"<div style='color:#9ca3af;font-size:0.8rem;margin-top:4px'>" + summary[:150] + "…</div>" if summary else ""}
                </div>""", unsafe_allow_html=True)
            if shown == 0:
                st.info("최근 뉴스가 없습니다.")
        else:
            st.info("뉴스를 불러올 수 없습니다.")

# ══ Tab 5: 13F 공시 히스토리 ════════════════════════════════════════════════
with tab5:
    st.markdown("### NVIDIA 13F 공시 히스토리")
    st.caption("SEC EDGAR 13F 기관투자자 공시 기반 · 분기별 지분 변동 추적")

    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        all_cos = sorted({f["company"] for f in FILINGS_HISTORY})
        sel_cos = st.multiselect("기업 필터", all_cos, default=all_cos, key="filing_filter")
        change_types = {"new":"🟢 신규","increase":"📈 증가","decrease":"📉 감소",
                        "exit":"⬛ 청산","hold":"🔵 유지"}
        sel_changes = st.multiselect("변동 유형", list(change_types.values()),
                                      default=list(change_types.values()), key="change_filter")
        sel_change_keys = [k for k,v in change_types.items() if v in sel_changes]

    with col_f2:
        filtered_filings = [f for f in FILINGS_HISTORY
                             if f["company"] in sel_cos
                             and f["change_type"] in sel_change_keys]
        filtered_filings = sorted(filtered_filings, key=lambda x: x["filed"], reverse=True)

        for f in filtered_filings:
            css, label = CHANGE_STYLE.get(f["change_type"], ("filing-hold","🔵 유지"))
            value_str  = f"${f['value_m']:.1f}M" if f.get("value_m") else ""
            shares_str = f"{f['shares']:,}주" if f.get("shares") else ""
            detail = " · ".join(filter(None, [value_str, shares_str]))

            st.markdown(f"""
            <div class="filing-row {css}">
              <span style="color:#f9fafb;font-weight:600">{f['company']} ({f['ticker']})</span>
              &nbsp;&nbsp;
              <span style="color:#9ca3af;font-size:0.82rem">{f['quarter']} · 공시일 {f['filed']}</span>
              <br>
              <span style="font-size:0.9rem">{label} — {f['change']}</span>
              {"&nbsp;&nbsp;<span style='color:#76b900;font-size:0.85rem'>" + detail + "</span>" if detail else ""}
            </div>""", unsafe_allow_html=True)

    # 타임라인 차트
    st.markdown("### 공시 타임라인")
    df_f = pd.DataFrame(FILINGS_HISTORY)
    color_map = {"new":"#22c55e","increase":"#76b900","decrease":"#ef4444",
                 "exit":"#6b7280","hold":"#3b82f6"}
    df_f["color"] = df_f["change_type"].map(color_map)
    df_f["label"] = df_f["change_type"].map(
        {"new":"신규","increase":"증가","decrease":"감소","exit":"청산","hold":"유지"})

    fig6 = go.Figure()
    for ct, grp in df_f.groupby("change_type"):
        fig6.add_trace(go.Scatter(
            x=grp["filed"], y=grp["company"],
            mode="markers+text",
            name={"new":"🟢 신규","increase":"📈 증가","decrease":"📉 감소",
                  "exit":"⬛ 청산","hold":"🔵 유지"}.get(ct, ct),
            marker=dict(color=color_map[ct], size=14, symbol="circle"),
            text=grp["quarter"],
            textposition="top center",
            textfont=dict(size=9, color="#9ca3af"),
            hovertemplate="<b>%{y}</b><br>%{x}<br>" + ct + "<extra></extra>",
        ))
    fig6.update_layout(
        template="plotly_dark", paper_bgcolor="#111827", plot_bgcolor="#111827",
        height=420, xaxis_title="공시일", yaxis_title="",
        legend=dict(bgcolor="#1f2937", orientation="h", y=1.12),
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(gridcolor="#1f2937"),
        yaxis=dict(gridcolor="#1f2937"),
    )
    st.plotly_chart(fig6, use_container_width=True)

# ─── 푸터 ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:#6b7280;font-size:0.8rem'>"
    f"데이터 출처: Yahoo Finance (15분 지연) · SEC EDGAR 13F · NVIDIA IR<br>"
    f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>",
    unsafe_allow_html=True)
