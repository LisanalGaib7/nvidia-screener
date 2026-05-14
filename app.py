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
  .main { background-color: #0a0a0a; }
  .stApp { background-color: #0d0d0d; }

  .metric-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #76b900;
    border-radius: 12px;
    padding: 16px 20px;
    text-align: center;
  }
  .metric-card h2 { color: #76b900; margin: 0; font-size: 1.8rem; }
  .metric-card p  { color: #aaa; margin: 4px 0 0; font-size: 0.85rem; }

  .company-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
  }
  .company-card:hover { border-color: #76b900; }

  .badge-hot   { background:#76b900; color:#000; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
  .badge-new   { background:#f59e0b; color:#000; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
  .badge-core  { background:#3b82f6; color:#fff; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }
  .badge-watch { background:#6b7280; color:#fff; border-radius:4px; padding:2px 8px; font-size:0.72rem; font-weight:700; }

  .positive { color: #22c55e; font-weight: 700; }
  .negative { color: #ef4444; font-weight: 700; }

  h1, h2, h3 { color: #f9fafb !important; }
  .stMarkdown p { color: #d1d5db; }
  div[data-testid="stMetricValue"] { color: #76b900 !important; font-size: 1.6rem !important; }
  div[data-testid="stMetricLabel"] { color: #9ca3af !important; }
</style>
""", unsafe_allow_html=True)

# ─── NVIDIA 투자 기업 데이터 ────────────────────────────────────────────────
# 출처: SEC 13F 공시, NVIDIA 공식 발표, IR 자료
NVIDIA_PORTFOLIO = [
    {
        "ticker": "SOUN",
        "name": "SoundHound AI",
        "sector": "AI/음성인식",
        "invest_year": 2023,
        "invest_amt_m": 3.99,
        "nvidia_thesis": "음성 AI 엣지 추론 — NVIDIA GPU 기반 실시간 음성인식 플랫폼",
        "badge": "hot",
        "exchange": "NASDAQ",
        "note": "2024 13F 공시 확인, 이후 일부 매도",
    },
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
    },
    {
        "ticker": "SERV",
        "name": "Serve Robotics",
        "sector": "자율주행 로봇",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "라스트마일 자율배달 로봇 — Jetson 플랫폼 레퍼런스 파트너",
        "badge": "hot",
        "exchange": "NASDAQ",
        "note": "주요 주주, Jetson Orin 탑재",
    },
    {
        "ticker": "NNOX",
        "name": "Nano-X Imaging",
        "sector": "AI 의료영상",
        "invest_year": 2023,
        "invest_amt_m": None,
        "nvidia_thesis": "디지털 X-ray + AI 진단 — NVIDIA Clara 파이프라인 연동",
        "badge": "watch",
        "exchange": "NASDAQ",
        "note": "13F 공시 확인",
    },
    {
        "ticker": "NBIS",
        "name": "Nebius Group",
        "sector": "클라우드 GPU",
        "invest_year": 2024,
        "invest_amt_m": 100.0,
        "nvidia_thesis": "유럽·이스라엘 AI 클라우드 인프라 — H100 기반 GPU 클라우드",
        "badge": "new",
        "exchange": "NASDAQ",
        "note": "$100M 투자 (2024.12), 전 Yandex NV",
    },
    {
        "ticker": "CRWV",
        "name": "CoreWeave",
        "sector": "클라우드 GPU",
        "invest_year": 2023,
        "invest_amt_m": None,
        "nvidia_thesis": "NVIDIA GPU 특화 하이퍼스케일러 — H100/B200 최대 보유 클라우드",
        "badge": "core",
        "exchange": "NASDAQ",
        "note": "2025.03 IPO, NVIDIA 전략적 주주",
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
        "note": "투자 관계 공개, 광학 공급망 전략",
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
        "note": "전략적 관계, 광학 공급망",
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
        "note": "2023.09 IPO, 전략적 파트너십",
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
        "note": "NVIDIA 공급 파트너십",
    },
    {
        "ticker": "6954.T",
        "name": "FANUC",
        "sector": "산업 로봇",
        "invest_year": 2024,
        "invest_amt_m": None,
        "nvidia_thesis": "산업용 로봇 + AI — Isaac 플랫폼 기반 로봇 제어 협력",
        "badge": "new",
        "exchange": "TSE",
        "note": "Isaac for Manipulators 파트너십 (일본 상장)",
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
    },
]

BADGE_MAP = {
    "hot":   ('<span class="badge-hot">🔥 HOT</span>', "핵심 투자"),
    "core":  ('<span class="badge-core">⭐ CORE</span>', "전략 파트너"),
    "new":   ('<span class="badge-new">🆕 NEW</span>', "신규 투자"),
    "watch": ('<span class="badge-watch">👁 WATCH</span>', "관찰 중"),
}

SECTOR_COLORS = {
    "AI/음성인식": "#76b900",
    "AI 신약개발": "#22d3ee",
    "자율주행 로봇": "#f59e0b",
    "AI 의료영상": "#a78bfa",
    "클라우드 GPU": "#3b82f6",
    "광학 트랜시버": "#ec4899",
    "광학 부품": "#fb7185",
    "반도체 IP": "#34d399",
    "AI 데이터센터": "#60a5fa",
    "산업 로봇": "#fbbf24",
    "eVTOL": "#c084fc",
}

# ─── 데이터 fetch ──────────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # 5분 캐시
def fetch_stock_data(tickers: list[str]) -> dict:
    result = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            hist = t.history(period="1y")

            price = info.get("currentPrice") or info.get("regularMarketPrice") or (
                hist["Close"].iloc[-1] if not hist.empty else None
            )
            prev  = info.get("regularMarketPreviousClose") or (
                hist["Close"].iloc[-2] if len(hist) > 1 else price
            )
            change_pct = ((price - prev) / prev * 100) if price and prev else None

            ytd_start = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
            ytd_pct = (
                (price - ytd_start.iloc[0]) / ytd_start.iloc[0] * 100
                if not ytd_start.empty and price else None
            )

            result[ticker] = {
                "price": price,
                "change_pct": change_pct,
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "week52_high": info.get("fiftyTwoWeekHigh"),
                "week52_low": info.get("fiftyTwoWeekLow"),
                "volume": info.get("regularMarketVolume"),
                "revenue_growth": info.get("revenueGrowth"),
                "ytd_pct": ytd_pct,
                "hist": hist,
                "currency": info.get("currency", "USD"),
                "short_name": info.get("shortName", ticker),
            }
        except Exception as e:
            result[ticker] = {"error": str(e)}
    return result


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


# ─── 사이드바 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🟢 NVIDIA 투자 필터")
    st.markdown("---")

    sectors = sorted({c["sector"] for c in NVIDIA_PORTFOLIO})
    sel_sectors = st.multiselect("섹터", sectors, default=sectors, key="sectors")

    badges = {"hot": "🔥 HOT", "core": "⭐ CORE", "new": "🆕 NEW", "watch": "👁 WATCH"}
    sel_badges = st.multiselect("투자 등급", list(badges.values()),
                                 default=list(badges.values()))
    sel_badge_keys = [k for k, v in badges.items() if v in sel_badges]

    exchanges = sorted({c["exchange"] for c in NVIDIA_PORTFOLIO})
    sel_exchanges = st.multiselect("거래소", exchanges, default=exchanges)

    st.markdown("---")
    sort_by = st.selectbox("정렬 기준",
        ["YTD 수익률", "시가총액", "일간 등락률", "P/E 비율", "회사명"])
    st.markdown("---")
    st.markdown("""
**⚠️ 면책조항**

본 대시보드는 SEC 13F 공시 및
NVIDIA 공식 발표를 기반으로 합니다.
투자 조언이 아니며, 지분 변동이
있을 수 있습니다.

**데이터:** Yahoo Finance (실시간 ~15분 지연)
""")
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─── 필터링 ───────────────────────────────────────────────────────────────
filtered = [
    c for c in NVIDIA_PORTFOLIO
    if c["sector"] in sel_sectors
    and c["badge"] in sel_badge_keys
    and c["exchange"] in sel_exchanges
]

tickers = [c["ticker"] for c in filtered]

# ─── 헤더 ─────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 8])
with col_title:
    st.markdown("# 🟢 NVIDIA 투자 기업 스크리너")
    st.markdown(
        "NVIDIA가 직접 투자·지분 보유한 상장사를 추적합니다. "
        "출처: SEC 13F 공시 · NVIDIA IR · 공식 파트너십 발표"
    )

st.markdown("---")

# ─── 데이터 로딩 ──────────────────────────────────────────────────────────
with st.spinner("실시간 주가 데이터 불러오는 중..."):
    stock_data = fetch_stock_data(tickers)

# ─── 요약 지표 ────────────────────────────────────────────────────────────
total_companies = len(filtered)
ytd_values = [
    stock_data[c["ticker"]].get("ytd_pct")
    for c in filtered
    if "ytd_pct" in stock_data.get(c["ticker"], {})
    and stock_data[c["ticker"]]["ytd_pct"] is not None
]
avg_ytd = sum(ytd_values) / len(ytd_values) if ytd_values else None
positive_count = sum(1 for v in ytd_values if v > 0)
total_invest = sum(
    c["invest_amt_m"] for c in filtered
    if c.get("invest_amt_m") is not None
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("추적 기업 수", f"{total_companies}개")
with c2:
    st.metric(
        "평균 YTD 수익률",
        f"{avg_ytd:+.1f}%" if avg_ytd is not None else "—",
        delta="포트폴리오 평균" if avg_ytd else None
    )
with c3:
    st.metric("YTD 플러스 기업", f"{positive_count} / {len(ytd_values)}개")
with c4:
    st.metric("공개 확인 투자액", f"${total_invest:.0f}M+" if total_invest else "—")

st.markdown("---")

# ─── 메인 탭 ──────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋 기업 목록", "📈 차트 비교", "🗺️ 섹터 분석"])

# ── Tab 1: 기업 목록 ────────────────────────────────────────────────────
with tab1:
    # 정렬
    def get_sort_val(c):
        sd = stock_data.get(c["ticker"], {})
        if sort_by == "YTD 수익률":    return sd.get("ytd_pct") or -9999
        if sort_by == "시가총액":       return sd.get("market_cap") or 0
        if sort_by == "일간 등락률":    return sd.get("change_pct") or -9999
        if sort_by == "P/E 비율":      return sd.get("pe_ratio") or 9999
        return c["name"]

    sorted_companies = sorted(filtered, key=get_sort_val,
                               reverse=(sort_by != "회사명" and sort_by != "P/E 비율"))

    # 테이블 헤더
    hcols = st.columns([2.5, 1.2, 1.3, 1.3, 1.2, 1.2, 1.2, 1.5, 2])
    headers = ["기업", "현재가", "일간등락", "YTD", "시총", "P/E", "P/S", "52주범위", "투자 근거"]
    for h, col in zip(headers, hcols):
        col.markdown(f"**{h}**")
    st.markdown('<hr style="margin:4px 0;border-color:#374151">', unsafe_allow_html=True)

    for company in sorted_companies:
        ticker = company["ticker"]
        sd = stock_data.get(ticker, {})
        badge_html, _ = BADGE_MAP[company["badge"]]

        if "error" in sd:
            st.warning(f"{ticker}: 데이터 로드 실패 — {sd['error']}")
            continue

        price     = sd.get("price")
        currency  = sd.get("currency", "USD")
        change    = sd.get("change_pct")
        ytd       = sd.get("ytd_pct")
        mcap      = sd.get("market_cap")
        pe        = sd.get("pe_ratio")
        ps        = sd.get("ps_ratio")
        w52h      = sd.get("week52_high")
        w52l      = sd.get("week52_low")

        # 52주 범위 바 계산
        if w52h and w52l and price:
            pct_pos = (price - w52l) / (w52h - w52l) * 100
            bar_html = f"""
            <div style="font-size:0.7rem;color:#6b7280">
              {fmt_price(w52l,currency)} ━━ {fmt_price(w52h,currency)}<br>
              <div style="background:#374151;border-radius:3px;height:4px;margin-top:2px">
                <div style="background:#76b900;width:{pct_pos:.0f}%;height:4px;border-radius:3px"></div>
              </div>
              <span style="color:#76b900">{pct_pos:.0f}% of range</span>
            </div>"""
        else:
            bar_html = "—"

        cols = st.columns([2.5, 1.2, 1.3, 1.3, 1.2, 1.2, 1.2, 1.5, 2])
        with cols[0]:
            invest_note = f"${company['invest_amt_m']:.0f}M" if company.get("invest_amt_m") else ""
            st.markdown(
                f"**{company['name']}** ({ticker})<br>"
                f"{badge_html} &nbsp; "
                f"<span style='color:#6b7280;font-size:0.75rem'>{company['sector']}</span>"
                f"{'&nbsp;·&nbsp;<span style=\"color:#76b900;font-size:0.75rem\">' + invest_note + '</span>' if invest_note else ''}",
                unsafe_allow_html=True
            )
        with cols[1]:
            st.markdown(fmt_price(price, currency), unsafe_allow_html=True)
        with cols[2]:
            st.markdown(fmt_pct(change), unsafe_allow_html=True)
        with cols[3]:
            st.markdown(fmt_pct(ytd), unsafe_allow_html=True)
        with cols[4]:
            st.markdown(fmt_cap(mcap))
        with cols[5]:
            st.markdown(fmt_ratio(pe))
        with cols[6]:
            st.markdown(fmt_ratio(ps))
        with cols[7]:
            st.markdown(bar_html, unsafe_allow_html=True)
        with cols[8]:
            with st.expander("📌"):
                st.markdown(f"**투자 근거:** {company['nvidia_thesis']}")
                st.markdown(f"**출처:** {company['note']}")
                st.markdown(f"**투자 시작:** {company['invest_year']}년")

        st.markdown('<hr style="margin:2px 0;border-color:#1f2937">', unsafe_allow_html=True)

# ── Tab 2: 차트 비교 ──────────────────────────────────────────────────
with tab2:
    st.markdown("### YTD 주가 성과 비교")

    chart_companies = [c for c in filtered if "error" not in stock_data.get(c["ticker"], {})]

    if chart_companies:
        fig = go.Figure()

        for company in chart_companies:
            sd = stock_data[company["ticker"]]
            hist = sd.get("hist")
            if hist is None or hist.empty:
                continue

            ytd_hist = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
            if ytd_hist.empty:
                continue

            norm = ytd_hist / ytd_hist.iloc[0] * 100  # 100 기준 정규화

            color = SECTOR_COLORS.get(company["sector"], "#76b900")
            fig.add_trace(go.Scatter(
                x=norm.index,
                y=norm.values,
                name=f"{company['name']} ({company['ticker']})",
                line=dict(color=color, width=2),
                hovertemplate=f"<b>{company['name']}</b><br>%{{y:.1f}} (100 = YTD 시작)<extra></extra>",
            ))

        # 기준선 100
        fig.add_hline(y=100, line_dash="dash", line_color="#6b7280",
                       annotation_text="YTD 시작점", annotation_position="bottom right")

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            legend=dict(bgcolor="#1f2937", bordercolor="#374151"),
            xaxis=dict(gridcolor="#1f2937"),
            yaxis=dict(gridcolor="#1f2937", title="정규화 주가 (100 = YTD 시작)"),
            height=520,
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # YTD 바 차트
    st.markdown("### YTD 수익률 순위")
    ytd_data = []
    for c in filtered:
        sd = stock_data.get(c["ticker"], {})
        ytd = sd.get("ytd_pct")
        if ytd is not None:
            ytd_data.append({
                "ticker": c["ticker"],
                "name": c["name"],
                "ytd": ytd,
                "sector": c["sector"],
            })

    if ytd_data:
        df_ytd = pd.DataFrame(ytd_data).sort_values("ytd", ascending=True)
        colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df_ytd["ytd"]]

        fig2 = go.Figure(go.Bar(
            x=df_ytd["ytd"],
            y=df_ytd["ticker"],
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.1f}%" for v in df_ytd["ytd"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>YTD: %{x:.2f}%<extra></extra>",
        ))
        fig2.update_layout(
            template="plotly_dark",
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            xaxis=dict(gridcolor="#1f2937", title="YTD 수익률 (%)"),
            yaxis=dict(gridcolor="#1f2937"),
            height=max(300, len(df_ytd) * 38),
            margin=dict(l=0, r=80, t=10, b=0),
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── Tab 3: 섹터 분석 ──────────────────────────────────────────────────
with tab3:
    st.markdown("### 섹터 분포")

    col_a, col_b = st.columns(2)

    with col_a:
        # 섹터별 기업 수
        sector_counts = {}
        for c in filtered:
            sector_counts[c["sector"]] = sector_counts.get(c["sector"], 0) + 1

        fig3 = go.Figure(go.Pie(
            labels=list(sector_counts.keys()),
            values=list(sector_counts.values()),
            marker_colors=[SECTOR_COLORS.get(s, "#6b7280") for s in sector_counts.keys()],
            hole=0.4,
            textfont=dict(size=12),
        ))
        fig3.update_layout(
            template="plotly_dark",
            paper_bgcolor="#111827",
            title="섹터별 기업 수",
            title_font_color="#f9fafb",
            legend=dict(bgcolor="#1f2937"),
            height=380,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        # 섹터별 시총
        sector_cap = {}
        for c in filtered:
            sd = stock_data.get(c["ticker"], {})
            cap = sd.get("market_cap") or 0
            sector_cap[c["sector"]] = sector_cap.get(c["sector"], 0) + cap

        sector_cap = {k: v for k, v in sector_cap.items() if v > 0}
        if sector_cap:
            fig4 = go.Figure(go.Pie(
                labels=list(sector_cap.keys()),
                values=list(sector_cap.values()),
                marker_colors=[SECTOR_COLORS.get(s, "#6b7280") for s in sector_cap.keys()],
                hole=0.4,
                textfont=dict(size=12),
                hovertemplate="%{label}<br>시총: %{value:,.0f}<extra></extra>",
            ))
            fig4.update_layout(
                template="plotly_dark",
                paper_bgcolor="#111827",
                title="섹터별 시가총액 합계",
                title_font_color="#f9fafb",
                legend=dict(bgcolor="#1f2937"),
                height=380,
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig4, use_container_width=True)

    # 섹터별 평균 YTD
    st.markdown("### 섹터별 평균 YTD 수익률")
    sector_ytd = {}
    for c in filtered:
        sd = stock_data.get(c["ticker"], {})
        ytd = sd.get("ytd_pct")
        if ytd is not None:
            sector_ytd.setdefault(c["sector"], []).append(ytd)

    if sector_ytd:
        avg_sector = {s: sum(v)/len(v) for s, v in sector_ytd.items()}
        df_s = pd.DataFrame(
            [(s, v) for s, v in avg_sector.items()],
            columns=["섹터", "평균 YTD (%)"]
        ).sort_values("평균 YTD (%)", ascending=False)

        fig5 = px.bar(
            df_s, x="섹터", y="평균 YTD (%)",
            color="평균 YTD (%)",
            color_continuous_scale=["#ef4444", "#374151", "#22c55e"],
            color_continuous_midpoint=0,
            template="plotly_dark",
        )
        fig5.update_layout(
            paper_bgcolor="#111827",
            plot_bgcolor="#111827",
            xaxis=dict(gridcolor="#1f2937"),
            yaxis=dict(gridcolor="#1f2937"),
            height=360,
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig5, use_container_width=True)

# ─── 푸터 ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#6b7280;font-size:0.8rem'>"
    "데이터 출처: Yahoo Finance (15분 지연) · SEC EDGAR 13F · NVIDIA IR<br>"
    f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    "</div>",
    unsafe_allow_html=True
)
