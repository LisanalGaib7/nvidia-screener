import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date

st.set_page_config(
    page_title="NVIDIA Portfolio Tracker",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "lang" not in st.session_state:
    st.session_state.lang = "KOR"

TRANSLATIONS = {
    # 헤더
    "last_verified":        {"KOR": "마지막 검증 2026-05-14",       "ENG": "Last verified 2026-05-14"},
    # 메트릭
    "metric_holdings":      {"KOR": "현재 13F 보유",                "ENG": "13F Holdings"},
    "metric_invested":      {"KOR": "확인된 투자액",                 "ENG": "Total Invested"},
    "metric_avg_ytd":       {"KOR": "평균 YTD",                     "ENG": "Avg YTD"},
    "metric_ytd_plus":      {"KOR": "YTD 플러스",                   "ENG": "YTD Positive"},
    "tooltip_13f":          {"KOR": "SEC 13F 공시 확인",             "ENG": "SEC 13F Confirmed"},
    "tooltip_invest_rank":  {"KOR": "투자금액 순",                   "ENG": "By Investment Size"},
    "tooltip_ytd_rank":     {"KOR": "YTD 수익률 순",                 "ENG": "By YTD Return"},
    # 섹션 헤더
    "group_new":            {"KOR": "2026 신규 투자",                "ENG": "2026 New Investments"},
    "group_hold":           {"KOR": "기존 보유  ·  Q4 2025",         "ENG": "Current Holdings  ·  Q4 2025"},
    "group_partner":        {"KOR": "전략 파트너십",                  "ENG": "Strategic Partnership"},
    "group_exited":         {"KOR": "청산 완료",                     "ENG": "Exited"},
    # 테이블 컬럼
    "col_company":          {"KOR": "기업",                          "ENG": "Company"},
    "col_price":            {"KOR": "현재가",                        "ENG": "Price"},
    "col_daily":            {"KOR": "일간등락",                      "ENG": "Daily"},
    "col_ytd":              {"KOR": "YTD",                          "ENG": "YTD"},
    "col_cap":              {"KOR": "시총",                          "ENG": "Mkt Cap"},
    "col_pe":               {"KOR": "P/E",                          "ENG": "P/E"},
    "col_52w":              {"KOR": "52주범위",                      "ENG": "52W Range"},
    # 사이드바
    "sb_show":              {"KOR": "표시 항목",                     "ENG": "Show"},
    "sb_holdings":          {"KOR": "현재 보유 (13F)",               "ENG": "Current Holdings (13F)"},
    "sb_partner":           {"KOR": "전략 파트너십",                  "ENG": "Strategic Partnership"},
    "sb_exited":            {"KOR": "청산 완료",                     "ENG": "Exited"},
    "sb_sort":              {"KOR": "정렬 기준",                     "ENG": "Sort By"},
    "sb_tag_guide":         {"KOR": "태그 가이드",                   "ENG": "Tag Guide"},
    "sb_share":             {"KOR": "공유하기",                      "ENG": "Share"},
    "sb_feedback":          {"KOR": "Feedback",                     "ENG": "Feedback"},
    "sb_sort_invest":       {"KOR": "투자금액",                      "ENG": "Investment"},
    "sb_sort_ytd":          {"KOR": "YTD 수익률",                    "ENG": "YTD Return"},
    "sb_sort_cap":          {"KOR": "시가총액",                      "ENG": "Market Cap"},
    "sb_sort_daily":        {"KOR": "일간 등락률",                   "ENG": "Daily Change"},
    "sb_sort_date":         {"KOR": "투자 날짜",                     "ENG": "Invest Date"},
    # 뉴스탭
    "news_price":           {"KOR": "현재가",                        "ENG": "Price"},
    "news_daily":           {"KOR": "일간등락",                      "ENG": "Daily"},
    "news_title":           {"KOR": "종목별 최신 뉴스",               "ENG": "Latest News by Stock"},
    "news_caption":         {"KOR": "Yahoo Finance 기준",            "ENG": "Source: Yahoo Finance"},
    "news_stock":           {"KOR": "종목",                          "ENG": "Stock"},
    "news_loading":         {"KOR": "뉴스 로드 중...",                "ENG": "Loading news..."},
    "news_none":            {"KOR": "뉴스 없음",                     "ENG": "No news found"},
    # 알림 배너
    "alert_title":          {"KOR": "최신 투자 알림",                 "ENG": "Latest Investment Alerts"},
    # 13F 탭
    "filings_title":        {"KOR": "NVIDIA 13F 공시 히스토리",       "ENG": "NVIDIA 13F Filing History"},
    "filings_caption":      {"KOR": "SEC EDGAR 13F 기반 · 글로벌 주요 언론 교차검증 · 미확인 항목은 별도 표기",
                             "ENG": "Based on SEC EDGAR 13F · Cross-verified with global media · Unconfirmed items marked separately"},
    "timeline_title":       {"KOR": "공시 타임라인",                  "ENG": "Filing Timeline"},
    "filings_company":      {"KOR": "기업",                          "ENG": "Company"},
    "filings_type":         {"KOR": "변동 유형",                     "ENG": "Change Type"},
    "filings_xaxis":        {"KOR": "공시일",                        "ENG": "Filing Date"},
    # 퍼포먼스 탭
    "perf_ytd_start":       {"KOR": "YTD 시작",                     "ENG": "YTD Start"},
    "perf_yaxis":           {"KOR": "정규화 주가 (100=YTD시작)",      "ENG": "Normalized Price (100=YTD Start)"},
    # 섹터 탭
    "sector_count":         {"KOR": "현재 보유 — 섹터별 기업 수",     "ENG": "Holdings by Sector"},
    "sector_invest":        {"KOR": "확인된 투자액 비중",              "ENG": "Investment Allocation"},
    # 사이드바 데이터
    "sb_data_sources":      {"KOR": "데이터 출처",                   "ENG": "Data Sources"},
    "sb_media":             {"KOR": "글로벌 주요 언론 교차검증",       "ENG": "Global Media Cross-verification"},
    "sb_disclaimer":        {"KOR": "⚠️ 투자 조언 아님",              "ENG": "⚠️ Not Financial Advice"},
    "sb_delay":             {"KOR": "Data: Yahoo Finance (~15분 지연)", "ENG": "Data: Yahoo Finance (~15min delay)"},
    "sb_refresh":           {"KOR": "🔄 새로고침",                    "ENG": "🔄 Refresh"},
    # 피드백
    "fb_type":              {"KOR": "유형",                          "ENG": "Type"},
    "fb_rating":            {"KOR": "만족도",                        "ENG": "Rating"},
    "fb_content":           {"KOR": "내용",                          "ENG": "Content"},
    "fb_content_ph":        {"KOR": "예) INTC 투자금액이 다릅니다 / OO 기업도 추가해주세요",
                             "ENG": "e.g. INTC investment amount is incorrect / Please add XX company"},
    "fb_name":              {"KOR": "닉네임 (선택)",                  "ENG": "Nickname (optional)"},
    "fb_name_ph":           {"KOR": "익명",                          "ENG": "Anonymous"},
    "fb_submit":            {"KOR": "제출하기",                       "ENG": "Submit"},
    "fb_empty":             {"KOR": "내용을 입력해주세요.",            "ENG": "Please enter your feedback."},
    "fb_ok":                {"KOR": "피드백 감사합니다!",              "ENG": "Thank you for your feedback!"},
    "fb_cat_data":          {"KOR": "데이터 오류 제보",               "ENG": "Data Error Report"},
    "fb_cat_new":           {"KOR": "신규 투자 제보",                 "ENG": "New Investment Tip"},
    "fb_cat_feat":          {"KOR": "기능 요청",                     "ENG": "Feature Request"},
    "fb_cat_bug":           {"KOR": "버그 신고",                     "ENG": "Bug Report"},
    "fb_cat_etc":           {"KOR": "기타 의견",                     "ENG": "Other"},
    # 로딩
    "loading":              {"KOR": "실시간 주가 데이터 로드 중...",   "ENG": "Loading live market data..."},
    # 변동 유형
    "change_new":           {"KOR": "신규",  "ENG": "New"},
    "change_increase":      {"KOR": "증가",  "ENG": "Increase"},
    "change_decrease":      {"KOR": "감소",  "ENG": "Decrease"},
    "change_exit":          {"KOR": "청산",  "ENG": "Exit"},
    "change_hold":          {"KOR": "유지",  "ENG": "Hold"},
    # 퍼포먼스 탭 제목
    "perf_title":           {"KOR": "YTD 주가 성과 비교",             "ENG": "YTD Price Performance Comparison"},
    # 태그 가이드
    "tag_core_desc":        {"KOR": "$1B 이상 직접 지분투자<br>SEC 13F 공시 확인",
                             "ENG": "Direct equity investment $1B+<br>SEC 13F filing confirmed"},
    "tag_new_desc":         {"KOR": "투자 발표 후 12개월 이내<br>신규 진입 종목",
                             "ENG": "Within 12 months of announcement<br>New entry"},
    "tag_seed_desc":        {"KOR": "$1B 미만 소규모 전략투자<br>또는 IPO 참여",
                             "ENG": "Strategic investment under $1B<br>or IPO participation"},
    "tag_partner_desc":     {"KOR": "지분투자 없는<br>공식 전략 파트너십",
                             "ENG": "Official strategic partnership<br>without equity investment"},
    "tag_exited_desc":      {"KOR": "과거 보유 후<br>완전 청산 완료",
                             "ENG": "Fully liquidated<br>from prior holdings"},
    # 기타
    "no_news":              {"KOR": "최근 뉴스가 없습니다.",           "ENG": "No recent news found."},
    "footer_delay":         {"KOR": "Yahoo Finance 15분 지연",        "ENG": "Yahoo Finance ~15min delay"},
    "detail_basis":         {"KOR": "투자 근거",                      "ENG": "Investment Basis"},
}

def t(key):
    lang = st.session_state.get("lang", "KOR")
    return TRANSLATIONS.get(key, {}).get(lang, key)

st.markdown("""
<style>
  /* ── 기본 배경 ── */
  .stApp, .main, section[data-testid="stSidebar"] > div:first-child {
    background-color: #080808;
  }
  section[data-testid="stSidebar"] { background-color: #0c0c0c; border-right: 1px solid #1a1a1a; }

  /* ── 타이포그래피 ── */
  html, body, [class*="css"] { font-family: 'Inter', 'SF Pro Display', system-ui, sans-serif; }
  h1 { color: #f0f0f0 !important; font-size: 1.7rem !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
  h2 { color: #d0d0d0 !important; font-size: 1.1rem !important; font-weight: 500 !important; letter-spacing: 0.3px !important; }
  h3 { color: #a0a0a0 !important; font-size: 0.8rem !important; font-weight: 600 !important;
       text-transform: uppercase; letter-spacing: 1.4px !important; }
  p, .stMarkdown p { color: #606060 !important; font-size: 0.88rem; line-height: 1.6; }

  /* ── 강조 텍스트 ── */
  .txt-primary   { color: #e8e8e8; }
  .txt-secondary { color: #686868; }
  .txt-accent    { color: #76b900; font-weight: 600; }
  .txt-gold      { color: #c87f00; font-weight: 600; }
  .txt-dim       { color: #383838; font-size: 0.75rem; letter-spacing: 0.3px; }

  /* ── 신규 투자 알림 배너 ── */
  @keyframes banner-snap {
    0%   { opacity: 0; transform: translateY(-8px); }
    60%  { opacity: 1; transform: translateY(2px); }
    100% { opacity: 1; transform: translateY(0); }
  }
  .alert-banner {
    background: #0e0e0e;
    border: 1px solid #2a2200;
    border-left: 3px solid #c87f00;
    border-radius: 4px;
    padding: 14px 20px;
    margin-bottom: 20px;
    animation: banner-snap 0.25s cubic-bezier(0.22, 1, 0.36, 1) both;
  }
  .alert-title { color: #c87f00; font-size: 0.7rem; font-weight: 600;
                 letter-spacing: 1.8px; text-transform: uppercase; margin: 0 0 10px; }
  .alert-item  { color: #a0a0a0; font-size: 0.84rem; margin: 5px 0; line-height: 1.5; }
  .alert-item b { color: #e0e0e0; font-weight: 500; }
  .alert-date  { color: #444; font-size: 0.75rem; }

  /* ── 배지 ── */
  .badge-core    { background: transparent; color: #4a90d9; border: 1px solid #1e3a5f;
                   border-radius: 2px; padding: 1px 7px; font-size: 0.65rem; font-weight: 600;
                   letter-spacing: 1px; text-transform: uppercase; }
  .badge-new     { background: transparent; color: #c87f00; border: 1px solid #3d2600;
                   border-radius: 2px; padding: 1px 7px; font-size: 0.65rem; font-weight: 600;
                   letter-spacing: 1px; text-transform: uppercase; }
  .badge-seed    { background: transparent; color: #76b900; border: 1px solid #2a3f00;
                   border-radius: 2px; padding: 1px 7px; font-size: 0.65rem; font-weight: 600;
                   letter-spacing: 1px; text-transform: uppercase; }
  .badge-watch   { background: transparent; color: #555; border: 1px solid #222;
                   border-radius: 2px; padding: 1px 7px; font-size: 0.65rem; font-weight: 600;
                   letter-spacing: 1px; text-transform: uppercase; }
  .badge-partner { background: transparent; color: #7c5cbf; border: 1px solid #2a1a4a;
                   border-radius: 2px; padding: 1px 7px; font-size: 0.65rem; font-weight: 600;
                   letter-spacing: 1px; text-transform: uppercase; }
  .badge-exited  { background: transparent; color: #333; border: 1px solid #1a1a1a;
                   border-radius: 2px; padding: 1px 7px; font-size: 0.65rem; font-weight: 600;
                   letter-spacing: 1px; text-transform: uppercase; text-decoration: line-through; }

  /* ── 수익률 색상 ── */
  .positive { color: #5a9e3a; font-weight: 600; }
  .negative { color: #a03030; font-weight: 600; }

  /* ── 뉴스 카드 ── */
  .news-card {
    background: #0e0e0e;
    border: 1px solid #1a1a1a;
    border-left: 2px solid #76b900;
    border-radius: 3px;
    padding: 12px 16px;
    margin-bottom: 6px;
  }
  .news-title { color: #d0d0d0; font-size: 0.88rem; font-weight: 500; line-height: 1.4; }
  .news-meta  { color: #3a3a3a; font-size: 0.72rem; margin-top: 4px; letter-spacing: 0.3px; }

  /* ── 13F 공시 카드 ── */
  .filing-row {
    background: #0e0e0e;
    border: 1px solid #181818;
    border-radius: 3px;
    padding: 10px 16px;
    margin-bottom: 4px;
  }
  .filing-new      { border-left: 3px solid #5a9e3a !important; }
  .filing-increase { border-left: 3px solid #76b900 !important; }
  .filing-decrease { border-left: 3px solid #a03030 !important; }
  .filing-exit     { border-left: 3px solid #2a2a2a !important; }
  .filing-hold     { border-left: 3px solid #1e3a5f !important; }

  /* ── 지표 카드 ── */
  div[data-testid="stMetricValue"] { color: #76b900 !important; font-size: 1.6rem !important; font-weight: 600 !important; letter-spacing: -0.5px; }
  div[data-testid="stMetricLabel"] { color: #404040 !important; font-size: 0.68rem !important;
                                     text-transform: uppercase; letter-spacing: 1px; }
  div[data-testid="stMetric"] {
    background: linear-gradient(160deg, #0f0f0f, #0b0b0b) !important;
    border: 1px solid #1e1e1e !important;
    border-top: 1px solid #2a2a2a !important;
    border-radius: 4px; padding: 18px !important;
  }

  /* ── 팝오버 ── */
  div[data-testid="stPopover"] button {
    background: transparent !important;
    border: 1px solid #2e2e2e !important;
    color: #707070 !important;
    border-radius: 2px !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.8px;
    padding: 2px 8px !important;
    text-transform: uppercase;
    transition: all 0.15s;
  }
  div[data-testid="stPopover"] button:hover {
    border-color: #76b900 !important;
    color: #76b900 !important;
  }
  div[data-testid="stPopoverBody"] {
    background: #101010 !important;
    border: 1px solid #242424 !important;
    border-radius: 4px !important;
    padding: 16px !important;
    min-width: 320px !important;
    max-width: 400px !important;
  }

  /* ── 탭 ── */
  div[data-baseweb="tab-list"] {
    border-bottom: 1px solid #1e1e1e !important;
    gap: 0px;
    background: transparent !important;
  }
  button[data-baseweb="tab"] {
    color: #383838 !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 1.6px !important;
    text-transform: uppercase !important;
    padding: 12px 24px !important;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    transition: color 0.2s ease, border-color 0.2s ease !important;
  }
  button[data-baseweb="tab"]:hover {
    color: #909090 !important;
    background: transparent !important;
  }
  button[data-baseweb="tab"][aria-selected="true"] {
    color: #e8e8e8 !important;
    border-bottom: 2px solid #76b900 !important;
    background: transparent !important;
  }

  /* ── 사이드바 텍스트 ── */
  .stSidebar h2, .stSidebar h3 { color: #e0e0e0 !important; }
  .stSidebar p, .stSidebar label { color: #909090 !important; }
  .stSidebar li { color: #909090 !important; }
  .stSidebar .stSelectbox label, .stSidebar .stMultiSelect label { color: #909090 !important; font-size:0.72rem !important; letter-spacing:0.8px; text-transform:uppercase; }

  /* ── 버튼 ── */
  .stButton > button { background: transparent !important; border: 1px solid #242424 !important;
                       color: #505050 !important; border-radius: 3px !important; font-size: 0.75rem !important;
                       letter-spacing: 0.5px; transition: all 0.2s; }
  .stButton > button:hover { border-color: #76b900 !important; color: #76b900 !important; }

  /* ── 언어 토글 st.pills — 선택 = 오렌지 ── */
  [data-testid="stSidebar"] [data-testid="stPills"] {
    gap: 6px !important;
  }
  [data-testid="stSidebar"] [data-testid="stPills"] button {
    border-radius: 20px !important;
    font-size: 0.7rem !important;
    font-weight: 800 !important;
    letter-spacing: 2px !important;
    padding: 5px 18px !important;
    transition: all 0.18s ease !important;
    border: 1px solid #2a2a2a !important;
    background: transparent !important;
    color: #404040 !important;
  }
  [data-testid="stSidebar"] [data-testid="stPills"] button:hover {
    border-color: #c87f00 !important;
    color: #c87f00 !important;
  }
  /* 선택된 pill — aria-pressed="true" or data-selected */
  [data-testid="stSidebar"] [data-testid="stPills"] button[aria-pressed="true"],
  [data-testid="stSidebar"] [data-testid="stPills"] button[data-selected="true"],
  [data-testid="stSidebar"] [data-testid="stPills"] button.selected,
  [data-testid="stSidebar"] [data-testid="stPills"] [data-active="true"] button {
    background: linear-gradient(135deg, #d4920a, #b87000) !important;
    border-color: #c87f00 !important;
    color: #060606 !important;
    box-shadow: 0 0 14px rgba(200,127,0,0.45) !important;
  }

  /* ── 입력 필드 ── */
  .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] {
    background: #0e0e0e !important; border: 1px solid #1e1e1e !important;
    border-radius: 3px !important; color: #c0c0c0 !important; font-size: 0.85rem !important; }

  /* ── 구분선 ── */
  hr { border-color: #181818 !important; margin: 20px 0 !important; }

  /* ── 요약 배지 칩 ── */
  .ticker-chip {
    background: #0e0e0e;
    border: 1px solid #1e1e1e;
    border-radius: 3px;
    padding: 10px 12px;
    text-align: center;
  }
  .ticker-chip .t  { font-size: 0.9rem; font-weight: 600; letter-spacing: 0.5px; }
  .ticker-chip .amt { font-size: 0.7rem; color: #404040; margin-top: 3px; letter-spacing: 0.3px; }

  /* ── 스크롤바 ── */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #080808; }
  ::-webkit-scrollbar-thumb { background: #222; border-radius: 2px; }

  /* ── 모바일 반응형 ─────────────────────────────────────── */
  @media screen and (max-width: 768px) {
    /* 전체 패딩 축소 */
    .main .block-container { padding: 1rem 0.8rem !important; }

    /* 헤더 축소 */
    .nv-title  { font-size: 0.68rem !important; letter-spacing: 0.5px !important; }
    .nv-cursor { font-size: 0.68rem !important; }
    .nv-logo   { font-size: 0.95rem !important; top: -5px !important; }

    /* 알림 배너 — 더 촘촘하게 */
    .alert-banner { padding: 10px 12px; margin-bottom: 14px; }
    .alert-title  { font-size: 0.62rem; }
    .alert-item   { font-size: 0.76rem; }
    .alert-date   { font-size: 0.65rem; }

    /* 탭 레이블 — 좁은 화면에 맞게 */
    button[data-baseweb="tab"] {
      font-size: 0.56rem !important;
      padding: 10px 9px !important;
      letter-spacing: 0.5px !important;
    }

    /* 메트릭 카드 4개 → 2×2 */
    [data-testid="stHorizontalBlock"]:has(.metric-box) {
      flex-wrap: wrap !important;
      gap: 6px !important;
    }
    [data-testid="stHorizontalBlock"]:has(.metric-box) > [data-testid="stColumn"] {
      flex: 0 0 calc(50% - 3px) !important;
      min-width: calc(50% - 3px) !important;
      width: calc(50% - 3px) !important;
    }

    /* 포트폴리오 테이블 — 가로 스크롤 */
    .main .block-container { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    [data-testid="stTabsContent"] [data-testid="stHorizontalBlock"] { min-width: 680px; }

    /* 팝오버 — 화면 넘침 방지 */
    div[data-testid="stPopoverBody"] {
      min-width: 240px !important;
      max-width: calc(100vw - 32px) !important;
    }

    /* 뉴스·공시 카드 패딩 축소 */
    .news-card  { padding: 10px 12px; }
    .filing-row { padding: 8px 12px; }
  }

  @media screen and (max-width: 480px) {
    .nv-title, .nv-cursor { font-size: 0.55rem !important; }
    button[data-baseweb="tab"] {
      font-size: 0.5rem !important;
      padding: 9px 7px !important;
    }
    [data-testid="stHorizontalBlock"]:has(.metric-box) > [data-testid="stColumn"] {
      flex: 0 0 calc(50% - 3px) !important;
      min-width: calc(50% - 3px) !important;
    }
  }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# 데이터 — 출처: SEC 13F, NVIDIA 공식 보도자료, Bloomberg/CNBC 교차검증
# 마지막 검증일: 2026-05-14
# ══════════════════════════════════════════════════════════════════════════════

# ── 2026년 신규 투자 (검증 완료) ─────────────────────────────────────────────
NEW_2026 = [
    {
        "ticker": "IREN",
        "name": "IREN Ltd",
        "sector": "AI 데이터센터",
        "invest_year": 2026,
        "invest_amt_m": 2100.0,
        "invest_date": "2026-05-07",
        "badge": "new",
        "exchange": "NASDAQ",
        "is_new_alert": True,
        "alert_date": "2026-05-07",
        "nvidia_thesis": "AI 데이터센터 5GW 구축 — 워런트 방식 최대 $2.1B (30M주 @$70). 5년 $3.4B GPU 클라우드 서비스 계약 병행",
        "nvidia_thesis_eng": "5GW AI Data Center buildout — warrant-based up to $2.1B (30M shares @$70). Paired with 5-year $3.4B GPU cloud services agreement",
        "note": "최대 $2.1B 워런트 (2026.05.07) | 5GW AI 인프라 배포 | $3.4B 클라우드 서비스 계약",
        "note_eng": "Up to $2.1B warrants (2026.05.07) | 5GW AI infrastructure deployment | $3.4B cloud services contract",
        "source": "NVIDIA Newsroom, Bloomberg (2026.05.07)",
    },
    {
        "ticker": "GLW",
        "name": "Corning",
        "sector": "광학 소재/제조",
        "invest_year": 2026,
        "invest_amt_m": 3200.0,
        "invest_date": "2026-05-06",
        "badge": "new",
        "exchange": "NYSE",
        "is_new_alert": True,
        "alert_date": "2026-05-06",
        "nvidia_thesis": "AI 광섬유·광학 소재 미국 내 제조 — 신규 공장 3곳(NC·TX), 미국 광학 생산 10배 확대. $500M 선불 워런트 @$180, 최대 $3.2B",
        "nvidia_thesis_eng": "AI fiber optic & optical materials domestic manufacturing — 3 new factories (NC·TX), 10x US optical production. $500M upfront warrants @$180, up to $3.2B",
        "note": "최대 $3.2B 워런트 ($500M 선불, 2026.05.06) | 미국 내 광학 공장 3곳 신설 | 3,000개 일자리",
        "note_eng": "Up to $3.2B warrants ($500M upfront, 2026.05.06) | 3 new US optical factories | 3,000 jobs",
        "source": "NVIDIA Newsroom, CNBC (2026.05.06)",
    },
    {
        "ticker": "MRVL",
        "name": "Marvell Technology",
        "sector": "반도체/광연결",
        "invest_year": 2026,
        "invest_amt_m": 2000.0,
        "invest_date": "2026-03-31",
        "badge": "new",
        "exchange": "NASDAQ",
        "is_new_alert": True,
        "alert_date": "2026-03-31",
        "nvidia_thesis": "NVLink Fusion — Marvell XPU를 NVIDIA Rubin GPU·Vera CPU와 동일 랙에서 1.8TB/s로 통합. 실리콘 포토닉스 공동 R&D",
        "nvidia_thesis_eng": "NVLink Fusion — Marvell XPU integrated with NVIDIA Rubin GPU & Vera CPU in the same rack at 1.8TB/s. Silicon photonics co-R&D",
        "note": "$2B 투자 (2026.03.31) | NVLink Fusion 파트너십 | 실리콘 포토닉스·5G/6G 공동 R&D",
        "note_eng": "$2B investment (2026.03.31) | NVLink Fusion partnership | Silicon photonics & 5G/6G co-R&D",
        "source": "NVIDIA Newsroom, CNBC (2026.03.31)",
    },
    {
        "ticker": "LITE",
        "name": "Lumentum Holdings",
        "sector": "광학 부품",
        "invest_year": 2026,
        "invest_amt_m": 2000.0,
        "invest_date": "2026-03-02",
        "badge": "new",
        "exchange": "NASDAQ",
        "is_new_alert": True,
        "alert_date": "2026-03-02",
        "nvidia_thesis": "AI 광학 레이저·포토닉스 — 미국 내 신규 fab 구축, 고급 레이저 부품 독점 공급권. 우선주 2,876,415주 @$695.31",
        "nvidia_thesis_eng": "AI optical lasers & photonics — new US fab construction, exclusive supply of advanced laser components. 2,876,415 preferred shares @$695.31",
        "note": "$2B 우선주 사모 (2026.03.02) | 2,876,415주 @$695.31 | 멀티빌리언 구매 약정 포함",
        "note_eng": "$2B preferred stock private placement (2026.03.02) | 2,876,415 shares @$695.31 | Multi-billion purchase commitment",
        "source": "NVIDIA Newsroom, CNBC (2026.03.02)",
    },
    {
        "ticker": "COHR",
        "name": "Coherent Corp",
        "sector": "광학 트랜시버",
        "invest_year": 2026,
        "invest_amt_m": 2000.0,
        "invest_date": "2026-03-02",
        "badge": "new",
        "exchange": "NYSE",
        "is_new_alert": True,
        "alert_date": "2026-03-02",
        "nvidia_thesis": "차세대 AI 데이터센터 광트랜시버 — 800G/1.6T 광연결 인프라. 미국 내 제조 확대, 멀티빌리언 구매 약정",
        "nvidia_thesis_eng": "Next-gen AI datacenter optical transceivers — 800G/1.6T optical interconnect infrastructure. US manufacturing expansion, multi-billion purchase commitment",
        "note": "$2B 투자 (2026.03.02) | 광학 네트워킹 제품 구매 약정 포함",
        "note_eng": "$2B investment (2026.03.02) | Optical networking product purchase commitment included",
        "source": "NVIDIA Newsroom, CNBC (2026.03.02)",
    },
]

# ── 현재 보유 중인 13F 상장 주식 (Q4 2025 기준 + 2026 신규) ──────────────────
CURRENT_HOLDINGS = [
    {
        "ticker": "INTC",
        "name": "Intel",
        "sector": "반도체/파운드리",
        "invest_year": 2025,
        "invest_amt_m": 5000.0,
        "invest_date": "2025-12-29",
        "badge": "core",
        "exchange": "NASDAQ",
        "is_new_alert": True,
        "alert_date": "2025-12-29",
        "nvidia_thesis": "AI 인프라·PC 칩 공동 개발 — x86 CPU+NVIDIA GPU 칩렛 통합 제품 개발. $5B 직접 지분투자(4%), 214.7M주 @$23.28",
        "nvidia_thesis_eng": "AI infrastructure & PC chip co-development — x86 CPU + NVIDIA GPU chiplet integrated products. $5B direct equity investment (4%), 214.7M shares @$23.28",
        "note": "$5B 지분투자 (2025.09 계약 → 2025.12.29 완료) | 4% 지분 | AI 데이터센터 및 PC 칩 공동개발",
        "note_eng": "$5B equity investment (2025.09 signed → 2025.12.29 closed) | 4% stake | AI datacenter & PC chip co-development",
        "source": "CNBC, NVIDIA Newsroom (2025.12.29)",
    },
    {
        "ticker": "SNPS",
        "name": "Synopsys",
        "sector": "EDA/칩 설계",
        "invest_year": 2025,
        "invest_amt_m": 2000.0,
        "invest_date": "2025-12-01",
        "badge": "core",
        "exchange": "NASDAQ",
        "is_new_alert": True,
        "alert_date": "2025-12-01",
        "nvidia_thesis": "EDA + 에이전틱 AI 엔지니어링 — 칩 설계 자동화·클라우드 가속. $2B 사모 발행 @$414.79/주",
        "nvidia_thesis_eng": "EDA + Agentic AI Engineering — chip design automation & cloud acceleration. $2B private placement @$414.79/share",
        "note": "$2B 사모 투자 (2025.12.01) | 칩 설계 AI 자동화 파트너십",
        "note_eng": "$2B private investment (2025.12.01) | Chip design AI automation partnership",
        "source": "NVIDIA Newsroom, CNBC (2025.12.01)",
    },
    {
        "ticker": "NOK",
        "name": "Nokia",
        "sector": "통신 인프라",
        "invest_year": 2025,
        "invest_amt_m": 1000.0,
        "invest_date": "2025-10-28",
        "badge": "core",
        "exchange": "NYSE",
        "is_new_alert": True,
        "alert_date": "2025-10-28",
        "nvidia_thesis": "5G/6G AI 네트워크 — Nokia RAN에 NVIDIA GPU 통합, AI 기반 이동통신 인프라 개발. $1B, 2.9% 지분 @$6.01/주",
        "nvidia_thesis_eng": "5G/6G AI Network — NVIDIA GPU integration into Nokia RAN, AI-driven mobile telecom infrastructure. $1B, 2.9% stake @$6.01/share",
        "note": "$1B 투자 (2025.10.28) | 2.9% 지분 | 5G RAN AI 통합 파트너십",
        "note_eng": "$1B investment (2025.10.28) | 2.9% stake | 5G RAN AI integration partnership",
        "source": "Bloomberg, CNBC (2025.10.28)",
    },
    {
        "ticker": "CRWV",
        "name": "CoreWeave",
        "sector": "클라우드 GPU",
        "invest_year": 2025,
        "invest_amt_m": None,
        "invest_date": "2025-03-28",
        "badge": "core",
        "exchange": "NASDAQ",
        "is_new_alert": False,
        "nvidia_thesis": "NVIDIA GPU 특화 하이퍼스케일러 — H100/B200 최대 보유 AI 클라우드. NVIDIA 전략적 주주·최대 고객",
        "nvidia_thesis_eng": "NVIDIA GPU-specialized hyperscaler — largest H100/B200 AI cloud. NVIDIA strategic shareholder & top customer",
        "note": "2025.03 IPO | NVIDIA 전략적 주주·최대 고객",
        "note_eng": "2025.03 IPO | NVIDIA strategic shareholder & top customer",
        "source": "CoreWeave IPO Filing (2025.03)",
    },
    {
        "ticker": "NBIS",
        "name": "Nebius Group",
        "sector": "클라우드 GPU",
        "invest_year": 2024,
        "invest_amt_m": 100.0,
        "invest_date": "2024-12-10",
        "badge": "hot",
        "exchange": "NASDAQ",
        "is_new_alert": False,
        "nvidia_thesis": "유럽·이스라엘 AI GPU 클라우드 — H100 기반 인프라 구축. $100M 전략적 투자",
        "nvidia_thesis_eng": "European & Israeli AI GPU cloud — H100-based infrastructure buildout. $100M strategic investment",
        "note": "$100M 전략적 투자 (2024.12) | 전 Yandex NV",
        "note_eng": "$100M strategic investment (2024.12) | Formerly Yandex NV",
        "source": "NVIDIA IR (2024.12.10)",
    },
]

# ── 전략 파트너십 (지분투자 아님) ────────────────────────────────────────────
PARTNERSHIPS = [
    {
        "ticker": "6954.T",
        "name": "FANUC",
        "sector": "산업 로봇",
        "invest_year": 2025,
        "invest_amt_m": None,
        "invest_date": "2025-12-01",
        "badge": "partner",
        "exchange": "TSE",
        "is_new_alert": False,
        "alert_date": "2025-12-01",
        "nvidia_thesis": "Physical AI 산업 로봇 — Isaac Sim 디지털 트윈, Jetson 온로봇 컴퓨터 탑재. FANUC 주가 +9.4% 급등",
        "nvidia_thesis_eng": "Physical AI industrial robots — Isaac Sim digital twin, Jetson on-robot computer integration. FANUC stock +9.4% surge on announcement",
        "note": "⚠️ 지분투자 아님 | Physical AI 파트너십 (2025.12.01) | Isaac Sim + Jetson 통합",
        "note_eng": "⚠️ No equity investment | Physical AI partnership (2025.12.01) | Isaac Sim + Jetson integration",
        "source": "NVIDIA Newsroom, Bloomberg (2025.12.01)",
    },
]

# ── 청산 완료 (과거 13F 보유 후 매도) ────────────────────────────────────────
EXITED = [
    {"ticker":"RXRX","name":"Recursion Pharma",   "sector":"AI 신약개발",  "invest_date":"2023-07-01","exit_date":"2025-Q4","invest_amt_m":50.0,  "note":"$50M 전략투자 → 2025 Q4 13F 청산"},
    {"ticker":"ARM", "name":"Arm Holdings",        "sector":"반도체 IP",   "invest_date":"2023-09-14","exit_date":"2026-02","invest_amt_m":None,  "note":"2023 IPO 참여 → Q4 2025 지분 감소 → 2026.02 완전 청산 ($140M, 1.1M주)"},
    {"ticker":"APLD","name":"Applied Digital",     "sector":"AI 데이터센터","invest_date":"2024-01-01","exit_date":"2025-Q4","invest_amt_m":None,  "note":"GPU 클라우드 파트너 → 2025 Q4 청산"},
    {"ticker":"WRD", "name":"WeRide",              "sector":"자율주행",    "invest_date":"2024-Q4",  "exit_date":"2025-Q4","invest_amt_m":24.0,  "note":"Q4 2024 신규 매수 ($24M, 1.7M주) → 2025 Q4 청산"},
    {"ticker":"SOUN","name":"SoundHound AI",       "sector":"AI/음성인식", "invest_date":"2023-Q4",  "exit_date":"2024-Q4","invest_amt_m":3.99,  "note":"2023 Q4 13F 신규 → 2024 Q4 완전 청산"},
    {"ticker":"SERV","name":"Serve Robotics",      "sector":"자율주행 로봇","invest_date":"2024-Q1",  "exit_date":"2024-Q4","invest_amt_m":None,  "note":"2024 Q1 13F 신규 → 2024 Q4 완전 청산"},
    {"ticker":"NNOX","name":"Nano-X Imaging",      "sector":"AI 의료영상", "invest_date":"2023-Q4",  "exit_date":"2024-Q4","invest_amt_m":None,  "note":"2023 Q4 13F 신규 → 2024 Q4 완전 청산"},
]

# ── 13F 공시 히스토리 (검증된 것만) ─────────────────────────────────────────
FILINGS_HISTORY = [
    # 2026 신규
    {"ticker":"IREN", "company":"IREN Ltd",         "quarter":"Q2 2026","filed":"2026-05-07","change":"신규 워런트 (최대 $2.1B @$70)",        "change_eng":"New warrants (up to $2.1B @$70)",          "change_type":"new",      "value_m":2100.0},
    {"ticker":"GLW",  "company":"Corning",          "quarter":"Q2 2026","filed":"2026-05-06","change":"신규 워런트 (최대 $3.2B, $500M 선불)",  "change_eng":"New warrants (up to $3.2B, $500M upfront)","change_type":"new",      "value_m":3200.0},
    {"ticker":"MRVL", "company":"Marvell Technology","quarter":"Q1 2026","filed":"2026-03-31","change":"신규 ($2B, NVLink Fusion)",           "change_eng":"New ($2B, NVLink Fusion)",                 "change_type":"new",      "value_m":2000.0},
    {"ticker":"LITE", "company":"Lumentum",         "quarter":"Q1 2026","filed":"2026-03-02","change":"신규 우선주 ($2B @$695.31)",           "change_eng":"New preferred stock ($2B @$695.31)",       "change_type":"new",      "value_m":2000.0},
    {"ticker":"COHR", "company":"Coherent Corp",    "quarter":"Q1 2026","filed":"2026-03-02","change":"신규 ($2B)",                          "change_eng":"New ($2B)",                                "change_type":"new",      "value_m":2000.0},
    # 2025 보유
    {"ticker":"INTC", "company":"Intel",            "quarter":"Q3 2025","filed":"2025-09-18","change":"전략투자 계약 ($5B)",                  "change_eng":"Strategic investment agreement ($5B)",     "change_type":"new",      "value_m":5000.0},
    {"ticker":"INTC", "company":"Intel",            "quarter":"Q4 2025","filed":"2025-12-29","change":"지분 취득 완료 (214.7M주)",            "change_eng":"Stake acquisition closed (214.7M shares)", "change_type":"increase", "value_m":5000.0},
    {"ticker":"SNPS", "company":"Synopsys",         "quarter":"Q4 2025","filed":"2025-12-01","change":"신규 ($2B 사모)",                     "change_eng":"New ($2B private placement)",              "change_type":"new",      "value_m":2000.0},
    {"ticker":"NOK",  "company":"Nokia",            "quarter":"Q3 2025","filed":"2025-10-28","change":"신규 ($1B, 2.9%)",                    "change_eng":"New ($1B, 2.9% stake)",                    "change_type":"new",      "value_m":1000.0},
    {"ticker":"NBIS", "company":"Nebius Group",     "quarter":"Q4 2024","filed":"2024-12-10","change":"신규 ($100M)",                        "change_eng":"New ($100M)",                              "change_type":"new",      "value_m":100.0},
    {"ticker":"CRWV", "company":"CoreWeave",        "quarter":"Q1 2025","filed":"2025-03-28","change":"IPO 참여·전략 주주",                   "change_eng":"IPO · Strategic Shareholder",              "change_type":"new",      "value_m":None},
    # 청산
    {"ticker":"RXRX", "company":"Recursion Pharma", "quarter":"Q3 2023","filed":"2023-11-14","change":"전략투자 ($50M)",                     "change_eng":"Strategic investment ($50M)",              "change_type":"new",      "value_m":50.0},
    {"ticker":"RXRX", "company":"Recursion Pharma", "quarter":"Q4 2025","filed":"2025-11-14","change":"완전 청산",                           "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"ARM",  "company":"Arm Holdings",     "quarter":"Q3 2023","filed":"2023-09-14","change":"IPO 참여",                            "change_eng":"IPO participation",                        "change_type":"new",      "value_m":None},
    {"ticker":"ARM",  "company":"Arm Holdings",     "quarter":"Q1 2026","filed":"2026-02-17","change":"완전 청산 (1.1M주, $140M)",           "change_eng":"Full exit (1.1M shares, $140M)",           "change_type":"exit",     "value_m":140.0},
    {"ticker":"WRD",  "company":"WeRide",           "quarter":"Q4 2024","filed":"2025-02-14","change":"신규 ($24M, 1.7M주)",                 "change_eng":"New ($24M, 1.7M shares)",                  "change_type":"new",      "value_m":24.0},
    {"ticker":"WRD",  "company":"WeRide",           "quarter":"Q4 2025","filed":"2025-11-14","change":"완전 청산",                           "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"SOUN", "company":"SoundHound AI",    "quarter":"Q4 2023","filed":"2024-02-14","change":"신규 ($3.99M)",                       "change_eng":"New ($3.99M)",                             "change_type":"new",      "value_m":3.99},
    {"ticker":"SOUN", "company":"SoundHound AI",    "quarter":"Q4 2024","filed":"2024-11-14","change":"완전 청산",                           "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"SERV", "company":"Serve Robotics",   "quarter":"Q1 2024","filed":"2024-05-15","change":"신규",                                "change_eng":"New position",                             "change_type":"new",      "value_m":None},
    {"ticker":"SERV", "company":"Serve Robotics",   "quarter":"Q4 2024","filed":"2024-11-14","change":"완전 청산",                           "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"APLD", "company":"Applied Digital",  "quarter":"Q2 2024","filed":"2024-08-14","change":"신규",                                "change_eng":"New position",                             "change_type":"new",      "value_m":None},
    {"ticker":"APLD", "company":"Applied Digital",  "quarter":"Q4 2025","filed":"2025-11-14","change":"완전 청산",                           "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"NNOX", "company":"Nano-X Imaging",   "quarter":"Q4 2023","filed":"2024-02-14","change":"신규",                                "change_eng":"New position",                             "change_type":"new",      "value_m":None},
    {"ticker":"NNOX", "company":"Nano-X Imaging",   "quarter":"Q4 2024","filed":"2024-11-14","change":"완전 청산",                           "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
]

BADGE_MAP = {
    "core":    '<span class="badge-core">CORE</span>',
    "new":     '<span class="badge-new">NEW</span>',
    "hot":     '<span class="badge-seed">SEED</span>',
    "watch":   '<span class="badge-watch">WATCH</span>',
    "partner": '<span class="badge-partner">PARTNER</span>',
    "exited":  '<span class="badge-exited">EXITED</span>',
}

SECTOR_COLORS = {
    "반도체/파운드리":"#94a3b8","EDA/칩 설계":"#34d399","통신 인프라":"#60a5fa",
    "클라우드 GPU":"#3b82f6","산업 로봇":"#fbbf24","광학 트랜시버":"#ec4899",
    "광학 부품":"#fb7185","AI 신약개발":"#22d3ee","반도체 IP":"#a78bfa",
    "AI 데이터센터":"#60a5fa","자율주행":"#f59e0b","자율주행 로봇":"#f97316",
    "AI/음성인식":"#76b900","AI 의료영상":"#c084fc",
}

SECTOR_NAMES = {
    "반도체/파운드리":  {"KOR": "반도체/파운드리",   "ENG": "Semiconductor/Foundry"},
    "EDA/칩 설계":     {"KOR": "EDA/칩 설계",       "ENG": "EDA/Chip Design"},
    "통신 인프라":      {"KOR": "통신 인프라",        "ENG": "Telecom Infrastructure"},
    "클라우드 GPU":    {"KOR": "클라우드 GPU",       "ENG": "Cloud GPU"},
    "산업 로봇":        {"KOR": "산업 로봇",          "ENG": "Industrial Robot"},
    "광학 트랜시버":    {"KOR": "광학 트랜시버",      "ENG": "Optical Transceiver"},
    "광학 부품":        {"KOR": "광학 부품",          "ENG": "Optical Components"},
    "광학 소재/제조":   {"KOR": "광학 소재/제조",     "ENG": "Optical Materials/Mfg"},
    "반도체/광연결":    {"KOR": "반도체/광연결",      "ENG": "Semi/Optical Interconnect"},
    "AI 신약개발":      {"KOR": "AI 신약개발",        "ENG": "AI Drug Discovery"},
    "반도체 IP":        {"KOR": "반도체 IP",          "ENG": "Semiconductor IP"},
    "AI 데이터센터":    {"KOR": "AI 데이터센터",      "ENG": "AI Data Center"},
    "자율주행":         {"KOR": "자율주행",           "ENG": "Autonomous Driving"},
    "자율주행 로봇":    {"KOR": "자율주행 로봇",      "ENG": "Autonomous Robot"},
    "AI/음성인식":      {"KOR": "AI/음성인식",        "ENG": "AI/Speech Recognition"},
    "AI 의료영상":      {"KOR": "AI 의료영상",        "ENG": "AI Medical Imaging"},
}

def sector_name(s):
    lang = st.session_state.get("lang", "KOR")
    return SECTOR_NAMES.get(s, {}).get(lang, s)

def get_change_style():
    return {
        "new":      ("filing-new",      "🟢 " + t("change_new")),
        "increase": ("filing-increase", "📈 " + t("change_increase")),
        "decrease": ("filing-decrease", "📉 " + t("change_decrease")),
        "exit":     ("filing-exit",     "⬛ " + t("change_exit")),
        "hold":     ("filing-hold",     "🔵 " + t("change_hold")),
    }

# ── fetch ────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_usdjpy():
    try:
        t = yf.Ticker("USDJPY=X")
        info = t.info
        rate = info.get("regularMarketPrice") or info.get("currentPrice")
        return rate if rate else 150.0
    except:
        return 150.0

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
            ytd_h = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
            ytd_pct = ((price - ytd_h.iloc[0]) / ytd_h.iloc[0] * 100
                       if not ytd_h.empty and price else None)
            result[ticker] = {
                "price": price, "change_pct": change_pct,
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "week52_high": info.get("fiftyTwoWeekHigh"),
                "week52_low":  info.get("fiftyTwoWeekLow"),
                "ytd_pct": ytd_pct, "hist": hist,
                "currency": info.get("currency","USD"),
            }
        except Exception as e:
            result[ticker] = {"error": str(e)}
    return result

@st.cache_data(ttl=600)
def fetch_news(ticker):
    try:
        return yf.Ticker(ticker).news or []
    except:
        return []

def fmt_cap(v, currency="USD", usdjpy=150.0):
    if v is None: return "—"
    if currency == "JPY":
        usd = v / usdjpy
        if usd >= 1e12: return f"${usd/1e12:.2f}T"
        if usd >= 1e9:  return f"${usd/1e9:.1f}B"
        return f"${usd/1e6:.0f}M"
    if v >= 1e12: return f"${v/1e12:.2f}T"
    if v >= 1e9:  return f"${v/1e9:.1f}B"
    if v >= 1e6:  return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"

def fmt_price(v, currency="USD"):
    if v is None: return "—"
    return f"{'¥' if currency=='JPY' else '$'}{v:,.2f}"

def fmt_pct(v):
    if v is None: return "—"
    c = "positive" if v >= 0 else "negative"
    a = "▲" if v >= 0 else "▼"
    return f'<span class="{c}">{a} {abs(v):.2f}%</span>'

def fmt_ratio(v): return f"{v:.1f}x" if v else "—"

def ts_to_str(ts):
    try: return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except: return ""

# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # KOR/ENG 토글 — st.pills (Streamlit 1.36+)
    _lang_pick = st.pills(
        "language", ["KOR", "ENG"],
        default=st.session_state.lang,
        key="lang_pills",
        label_visibility="collapsed",
    )
    if _lang_pick and _lang_pick != st.session_state.lang:
        st.session_state.lang = _lang_pick
        st.rerun()

    st.markdown("## NVIDIA Portfolio Tracker")
    st.markdown("---")
    show_current  = st.checkbox(t("sb_holdings"), value=True)
    show_partner  = st.checkbox(t("sb_partner"),  value=True)
    show_exited   = st.checkbox(t("sb_exited"),   value=False)
    st.markdown("---")
    sort_options = [t("sb_sort_invest"), t("sb_sort_ytd"), t("sb_sort_cap"), t("sb_sort_daily"), t("sb_sort_date")]
    sort_by = st.selectbox(t("sb_sort"), sort_options)

    st.markdown("---")

    with st.expander(t("sb_tag_guide")):
        st.markdown(f"""
<style>
.tag-guide-row {{ margin: 10px 0; }}
.tag-guide-name {{ font-size: 0.72rem; font-weight: 700; letter-spacing: 1px; margin-bottom: 3px; }}
.tag-guide-desc {{ font-size: 0.75rem; color: #686868 !important; line-height: 1.5; }}
</style>
<div class="tag-guide-row">
  <div class="tag-guide-name" style="color:#4a90d9">CORE</div>
  <div class="tag-guide-desc">{t("tag_core_desc")}</div>
</div>
<div class="tag-guide-row">
  <div class="tag-guide-name" style="color:#c87f00">NEW</div>
  <div class="tag-guide-desc">{t("tag_new_desc")}</div>
</div>
<div class="tag-guide-row">
  <div class="tag-guide-name" style="color:#76b900">SEED</div>
  <div class="tag-guide-desc">{t("tag_seed_desc")}</div>
</div>
<div class="tag-guide-row">
  <div class="tag-guide-name" style="color:#7c5cbf">PARTNER</div>
  <div class="tag-guide-desc">{t("tag_partner_desc")}</div>
</div>
<div class="tag-guide-row">
  <div class="tag-guide-name" style="color:#333">EXITED</div>
  <div class="tag-guide-desc">{t("tag_exited_desc")}</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        f"{t('sb_data_sources')}\n"
        f"- SEC EDGAR 13F\n"
        f"- NVIDIA IR\n"
        f"- {t('sb_media')}\n"
        f"  Bloomberg · Reuters · CNBC\n"
        f"  FT · WSJ · Economist {'외' if st.session_state.lang=='KOR' else 'etc.'}\n\n"
        f"---\n{t('sb_disclaimer')}\n\n{t('sb_delay')}"
    )
    if st.button(t("sb_refresh"), use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown(f"### {t('sb_share')}")
    _url = "https%3A%2F%2Fnvidiascreener.streamlit.app%2F"
    _text = "엔비디아가+직접+투자한+기업을+실시간으로+트래킹하는+포트폴리오+트래커"
    st.markdown(
        f'<div style="display:flex;gap:8px;margin-top:8px">'
        f'<a href="https://twitter.com/intent/tweet?url={_url}&text={_text}" target="_blank" '
        f'style="flex:1;display:flex;align-items:center;justify-content:center;gap:6px;'
        f'background:#0e0e0e;border:1px solid #2a2a2a;border-radius:4px;padding:8px;'
        f'color:#909090;font-size:0.72rem;font-weight:600;letter-spacing:0.8px;text-decoration:none;'
        f'transition:all 0.15s" onmouseover="this.style.borderColor=\'#e7e7e7\';this.style.color=\'#e7e7e7\'" '
        f'onmouseout="this.style.borderColor=\'#2a2a2a\';this.style.color=\'#909090\'">'
        f'𝕏 &nbsp;SHARE</a>'
        f'<a href="https://t.me/share/url?url={_url}&text={_text}" target="_blank" '
        f'style="flex:1;display:flex;align-items:center;justify-content:center;gap:6px;'
        f'background:#0e0e0e;border:1px solid #2a2a2a;border-radius:4px;padding:8px;'
        f'color:#909090;font-size:0.72rem;font-weight:600;letter-spacing:0.8px;text-decoration:none;'
        f'transition:all 0.15s" onmouseover="this.style.borderColor=\'#2aabee\';this.style.color=\'#2aabee\'" '
        f'onmouseout="this.style.borderColor=\'#2a2a2a\';this.style.color=\'#909090\'">'
        f'✈ &nbsp;TELEGRAM</a>'
        f'</div>',
        unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"### {t('sb_feedback')}")
    with st.form("feedback_form", clear_on_submit=True):
        fb_category = st.selectbox(t("fb_type"), [
            t("fb_cat_data"), t("fb_cat_new"), t("fb_cat_feat"), t("fb_cat_bug"), t("fb_cat_etc"),
        ])
        fb_rating = st.select_slider(t("fb_rating"), ["⭐","⭐⭐","⭐⭐⭐","⭐⭐⭐⭐","⭐⭐⭐⭐⭐"],
                                     value="⭐⭐⭐⭐⭐")
        fb_text = st.text_area(t("fb_content"), placeholder=t("fb_content_ph"), height=80)
        fb_name = st.text_input(t("fb_name"), placeholder=t("fb_name_ph"))
        submitted = st.form_submit_button(t("fb_submit"), use_container_width=True)

        if submitted:
            if fb_text.strip():
                import json, os
                entry = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "category": fb_category,
                    "rating": len(fb_rating),
                    "text": fb_text.strip(),
                    "name": fb_name.strip() or "익명",
                }
                path = "feedback.json"
                data = []
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except:
                        data = []
                data.append(entry)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                st.success(t("fb_ok"))
            else:
                st.warning(t("fb_empty"))

# ── 데이터 로드 ───────────────────────────────────────────────────────────────
all_display = []
if show_current: all_display += NEW_2026 + CURRENT_HOLDINGS
if show_partner: all_display += PARTNERSHIPS
if show_exited:  all_display += [
    {**e, "badge":"exited", "nvidia_thesis":e["note"],
     "is_new_alert":False, "invest_year":int(e["invest_date"][:4]) if len(e["invest_date"])>=4 else 0}
    for e in EXITED
]

tickers = [c["ticker"] for c in all_display]
with st.spinner(t("loading")):
    stock_data = fetch_stock_data(tickers)
    usdjpy = fetch_usdjpy()

# ── 🚨 신규 투자 알림 배너 — 최근 5건 ────────────────────────────────────────
all_investments = NEW_2026 + CURRENT_HOLDINGS + PARTNERSHIPS
recent_5 = sorted(
    [c for c in all_investments if c.get("alert_date")],
    key=lambda x: x.get("alert_date",""), reverse=True
)[:5]

_cur_lang = st.session_state.lang

if recent_5:
    latest_year = recent_5[0].get("alert_date","")[:4]
    items_html = "".join([
        f'<div class="alert-item">'
        f'<span class="alert-date">{c.get("alert_date","")}&nbsp;&nbsp;</span>'
        f'<b>{c["name"]} ({c["ticker"]})</b>'
        f'&nbsp;—&nbsp;{(c.get("note_eng") or c["note"]).split("|")[0].strip() if _cur_lang=="ENG" else c["note"].split("|")[0].strip()}'
        f'</div>'
        for c in recent_5
    ])
    st.markdown(
        f'<div class="alert-banner">'
        f'<div class="alert-title">{"Recent Investments" if _cur_lang=="ENG" else "최신 투자 알림"}&nbsp;·&nbsp;{latest_year}</div>'
        f'{items_html}'
        f'</div>',
        unsafe_allow_html=True)

# ── 헤더 ─────────────────────────────────────────────────────────────────────
if True:
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap" rel="stylesheet">
<style>
@keyframes nvlogo-spin {
  0%   { transform: perspective(400px) rotateY(0deg);   opacity:1; }
  40%  { transform: perspective(400px) rotateY(160deg); opacity:0.3; }
  50%  { transform: perspective(400px) rotateY(180deg); opacity:0.3; }
  90%  { transform: perspective(400px) rotateY(340deg); opacity:1; }
  100% { transform: perspective(400px) rotateY(360deg); opacity:1; }
}
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
@keyframes typewriter {
  from { width: 0; }
  to   { width: 100%; }
}
.nv-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 4px 0 2px;
}
.nv-logo-wrap {
  display: flex;
  align-items: center;
  animation: nvlogo-spin 3.2s ease-in-out infinite;
  transform-style: preserve-3d;
}
.nv-logo {
  font-size: 1.3rem;
  font-weight: 900;
  font-family: 'Inter', system-ui, sans-serif;
  color: #76b900;
  text-shadow: 0 0 24px rgba(118,185,0,0.5), 0 0 8px rgba(118,185,0,0.3);
  user-select: none;
  line-height: 1;
  position: relative;
  top: -7px;
}
.nv-title-wrap {
  overflow: hidden;
  display: inline-block;
}
.nv-title {
  font-family: 'Press Start 2P', monospace;
  font-size: 1.05rem;
  color: #76b900;
  letter-spacing: 1px;
  line-height: 1.3;
  text-shadow: 0 0 18px rgba(118,185,0,0.35);
  white-space: nowrap;
  display: inline;
}
.nv-cursor {
  font-family: 'Press Start 2P', monospace;
  font-size: 1.05rem;
  color: #76b900;
  animation: cursor-blink 1s step-end infinite;
  margin-left: 2px;
}
</style>
<div class="nv-header">
  <div class="nv-logo-wrap">
    <span class="nv-logo">&#9670;</span>
  </div>
  <div>
    <div class="nv-title-wrap">
      <span class="nv-title">NVIDIA Portfolio Tracker</span><span class="nv-cursor">_</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
    st.markdown(
        f'<p style="color:#383838;font-size:0.75rem;letter-spacing:0.5px;margin-top:2px">'
        f'{t("last_verified")}'
        f'</p>', unsafe_allow_html=True
    )

# ── 요약 지표 ─────────────────────────────────────────────────────────────────
ytd_vals = [stock_data[c["ticker"]].get("ytd_pct")
            for c in all_display
            if stock_data.get(c["ticker"],{}).get("ytd_pct") is not None]
avg_ytd = sum(ytd_vals)/len(ytd_vals) if ytd_vals else None
total_invest = sum(c["invest_amt_m"] for c in all_display if c.get("invest_amt_m"))

avg_ytd_str   = f"{avg_ytd:+.1f}%" if avg_ytd else "—"
_ytd_plus_cnt = sum(1 for v in ytd_vals if v>0)
ytd_plus_str  = f"{_ytd_plus_cnt}/{len(ytd_vals)}" + ("개" if st.session_state.lang == "KOR" else "")
invest_str    = f"${total_invest/1000:.1f}B+"

m1,m2,m3,m4 = st.columns(4)

# 13F 호버 툴팁용 CSS
st.markdown("""
<style>
.metric-box { position: relative; }
.metric-tooltip {
  display: none;
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 999;
  background: #141414;
  border: 1px solid #2a2a2a;
  border-top: 2px solid #76b900;
  border-radius: 4px;
  padding: 12px 16px;
  min-width: 200px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
}
.metric-box:hover .metric-tooltip { display: block; }
.tooltip-title {
  color: #484848;
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 1.4px;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.tooltip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid #1a1a1a;
}
.tooltip-row:last-child { border-bottom: none; }
.tooltip-ticker { color: #76b900; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.5px; }
.tooltip-name   { color: #686868; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

for col, label, value, color, extra_html in [
    (m1, t("metric_holdings"), "5개 종목" if st.session_state.lang=="KOR" else "5 stocks", "#76b900",
     '<div class="metric-tooltip">'
     f'<div class="tooltip-title">{t("tooltip_13f")}</div>'
     '<div class="tooltip-row"><span class="tooltip-ticker">INTC</span><span class="tooltip-name">Intel</span></div>'
     '<div class="tooltip-row"><span class="tooltip-ticker">SNPS</span><span class="tooltip-name">Synopsys</span></div>'
     '<div class="tooltip-row"><span class="tooltip-ticker">NOK</span><span class="tooltip-name">Nokia</span></div>'
     '<div class="tooltip-row"><span class="tooltip-ticker">CRWV</span><span class="tooltip-name">CoreWeave</span></div>'
     '<div class="tooltip-row"><span class="tooltip-ticker">NBIS</span><span class="tooltip-name">Nebius Group</span></div>'
     '</div>'),
    (m2, t("metric_invested"), invest_str,   "#c87f00",
     '<div class="metric-tooltip" style="border-top-color:#c87f00;min-width:220px">'
     f'<div class="tooltip-title" style="color:#c87f00">{t("tooltip_invest_rank")}</div>'
     + "".join(
         f'<div class="tooltip-row">'
         f'<span class="tooltip-ticker">{c["ticker"]}</span>'
         f'<span class="tooltip-name">'
         f'{"$"+str(int(c["invest_amt_m"]/1000))+"B" if c["invest_amt_m"]>=1000 else "$"+str(int(c["invest_amt_m"]))+"M"}'
         f'</span></div>'
         for c in sorted(
             [c for c in all_display if c.get("invest_amt_m") and c["badge"] != "exited"],
             key=lambda x: x["invest_amt_m"], reverse=True
         )
     )
     + '</div>'),
    (m3, t("metric_avg_ytd"), avg_ytd_str,  "#76b900",
     '<div class="metric-tooltip" style="min-width:220px">'
     f'<div class="tooltip-title">{t("tooltip_ytd_rank")}</div>'
     + "".join(
         f'<div class="tooltip-row">'
         f'<span class="tooltip-ticker">{c["ticker"]}</span>'
         f'<span class="tooltip-name" style="color:{"#76b900" if ytd>=0 else "#e05050"}">'
         f'{"▲" if ytd>=0 else "▼"}{abs(ytd):.1f}%</span></div>'
         for c, ytd in sorted(
             [(c, stock_data[c["ticker"]].get("ytd_pct"))
              for c in all_display
              if stock_data.get(c["ticker"],{}).get("ytd_pct") is not None
              and c["badge"] != "exited"],
             key=lambda x: x[1], reverse=True
         )
     )
     + '</div>'),
    (m4, t("metric_ytd_plus"), ytd_plus_str, "#76b900", ""),
]:
    col.markdown(
        f'<div class="metric-box" style="background:#0e0e0e;border:1px solid #2a2a2a;border-top:2px solid {color};'
        f'border-radius:4px;padding:18px 20px;margin-bottom:4px">'
        f'<div style="color:#484848;font-size:0.72rem;font-weight:500;letter-spacing:1.2px;'
        f'text-transform:uppercase;margin-bottom:8px">{label}</div>'
        f'<div style="color:{color};font-size:1.6rem;font-weight:600;letter-spacing:-0.5px;line-height:1">'
        f'{value}</div>'
        f'{extra_html}'
        f'</div>',
        unsafe_allow_html=True)

st.markdown("---")

# ── 탭 ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Portfolio", "Performance", "Sectors",
    "News", "13F History"
])

# ══ Tab 1 ════════════════════════════════════════════════════════════════════
with tab1:
    def sort_key(c):
        sd = stock_data.get(c["ticker"],{})
        if sort_by == t("sb_sort_invest"): return c.get("invest_amt_m") or 0
        if sort_by == t("sb_sort_ytd"):    return sd.get("ytd_pct") or -9999
        if sort_by == t("sb_sort_cap"):    return sd.get("market_cap") or 0
        if sort_by == t("sb_sort_daily"):  return sd.get("change_pct") or -9999
        if sort_by == t("sb_sort_date"):   return c.get("invest_date","")
        return 0

    groups = [
        (t("group_new"),    [c for c in all_display if c.get("invest_year")==2026],            True),
        (t("group_hold"),   [c for c in all_display if c["badge"] not in ["partner","exited"] and c.get("invest_year")!=2026], True),
        (t("group_partner"), [c for c in all_display if c["badge"] == "partner"],               True),
        (t("group_exited"),  [c for c in all_display if c["badge"] == "exited"],                False),
    ]

    for group_title, group_items, reverse in groups:
        if not group_items: continue
        if group_title == t("group_new"):     accent = "#76b900"
        elif group_title == t("group_partner"): accent = "#c87f00"
        elif group_title == t("group_exited"):  accent = "#484848"
        else:                                   accent = "#4a90d9"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;margin:32px 0 18px">'
            f'<div style="width:3px;height:22px;background:{accent};border-radius:2px;flex-shrink:0"></div>'
            f'<span style="color:#d0d0d0;font-size:0.95rem;font-weight:600;letter-spacing:0.4px">{group_title}</span>'
            f'<div style="flex:1;height:1px;background:#1a1a1a"></div>'
            f'</div>',
            unsafe_allow_html=True)
        sorted_items = sorted(group_items, key=sort_key, reverse=reverse)

        hcols = st.columns([2.5, 1.2, 1.3, 1.3, 1.2, 1.2, 1.5, 1.2])
        for h, col in zip([t("col_company"), t("col_price"), t("col_daily"), t("col_ytd"), t("col_cap"), t("col_pe"), t("col_52w"), ""], hcols):
            col.markdown(
                f'<span style="color:#c0c0c0;font-size:0.85rem;font-weight:500;'
                f'letter-spacing:0.3px">{h}</span>',
                unsafe_allow_html=True)
        st.markdown('<hr style="margin:4px 0;border-color:#1e1e1e">', unsafe_allow_html=True)

        for c in sorted_items:
            ticker = c["ticker"]
            sd = stock_data.get(ticker,{})
            if "error" in sd:
                st.warning(f"{ticker}: 데이터 로드 실패")
                continue

            price = sd.get("price"); currency = sd.get("currency","USD")
            w52h = sd.get("week52_high"); w52l = sd.get("week52_low")
            if w52h and w52l and price:
                pp = max(0, min(100, (price - w52l) / (w52h - w52l) * 100))
                bar = (
                    f'<div style="font-size:0.7rem;color:#686868">'
                    f'{fmt_price(w52l,currency)} <span style="color:#484848">━</span> {fmt_price(w52h,currency)}<br>'
                    f'<div style="background:#1a1a1a;border-radius:2px;height:3px;margin-top:3px">'
                    f'<div style="background:#76b900;width:{pp:.0f}%;height:3px;border-radius:2px"></div>'
                    f'</div>'
                    f'<span style="color:#76b900;font-size:0.68rem">{pp:.0f}%</span></div>'
                )
            else:
                bar = '<span style="color:#2a2a2a">—</span>'

            cols = st.columns([2.5, 1.2, 1.3, 1.3, 1.2, 1.2, 1.5, 1.2])
            amt = (f"${c['invest_amt_m']/1000:.1f}B" if (c.get("invest_amt_m") or 0) >= 1000
                   else f"${c['invest_amt_m']:.0f}M" if c.get("invest_amt_m") else "")

            with cols[0]:
                st.markdown(
                    f'<span style="color:#e8e8e8;font-weight:500">{c["name"]}</span>'
                    f'<span style="color:#686868;font-size:0.78rem;margin-left:6px">{ticker}</span><br>'
                    f'{BADGE_MAP[c["badge"]]}'
                    f'<span style="color:#686868;font-size:0.72rem;margin-left:6px">{sector_name(c["sector"])}</span>'
                    + (f'<span style="color:#c87f00;font-size:0.78rem;font-weight:600;margin-left:8px">{amt}</span>' if amt else ""),
                    unsafe_allow_html=True)
            with cols[1]:
                st.markdown(
                    f'<span style="color:#c0c0c0;font-weight:500">{fmt_price(price, currency)}</span>',
                    unsafe_allow_html=True)
            with cols[2]: st.markdown(fmt_pct(sd.get("change_pct")), unsafe_allow_html=True)
            with cols[3]: st.markdown(fmt_pct(sd.get("ytd_pct")),    unsafe_allow_html=True)
            with cols[4]:
                st.markdown(f'<span style="color:#a0a0a0">{fmt_cap(sd.get("market_cap"), sd.get("currency","USD"), usdjpy)}</span>', unsafe_allow_html=True)
            with cols[5]:
                st.markdown(f'<span style="color:#a0a0a0">{fmt_ratio(sd.get("pe_ratio"))}</span>', unsafe_allow_html=True)
            with cols[6]: st.markdown(bar, unsafe_allow_html=True)
            with cols[7]:
                with st.popover("Detail"):
                    st.markdown(
                        f'<div style="color:#505050;font-size:0.68rem;letter-spacing:1.2px;'
                        f'text-transform:uppercase;margin-bottom:12px">'
                        f'{c["ticker"]} &nbsp;·&nbsp; {c.get("invest_date","—")}</div>',
                        unsafe_allow_html=True)
                    if amt:
                        st.markdown(
                            f'<div style="color:#c87f00;font-size:1.1rem;font-weight:600;margin-bottom:12px">'
                            f'{amt}</div>',
                            unsafe_allow_html=True)
                    _thesis = (c.get("nvidia_thesis_eng") or c["nvidia_thesis"]) if st.session_state.lang == "ENG" else c["nvidia_thesis"]
                    st.markdown(
                        f'<div style="color:#a0a0a0;font-size:0.84rem;line-height:1.8;margin-bottom:14px">'
                        f'{_thesis}</div>',
                        unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="color:#383838;font-size:0.72rem;border-top:1px solid #1e1e1e;'
                        f'padding-top:10px">{c.get("source","—")}</div>',
                        unsafe_allow_html=True)

            st.markdown('<hr style="margin:3px 0;border-color:#141414">', unsafe_allow_html=True)

# ══ Tab 2 ════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown(f"### {t('perf_title')}")
    chart_items = [c for c in all_display if "error" not in stock_data.get(c["ticker"],{})]
    fig = go.Figure()
    for c in chart_items:
        hist = stock_data[c["ticker"]].get("hist")
        if hist is None or hist.empty: continue
        ytd_h = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
        if ytd_h.empty: continue
        pct = (ytd_h / ytd_h.iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(
            x=pct.index, y=pct.values,
            name=f"{c['name']} ({c['ticker']})",
            line=dict(color=SECTOR_COLORS.get(c["sector"],"#76b900"), width=2),
            hovertemplate=f"<b>{c['name']}</b><br>%{{y:+.1f}}%<extra></extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="#6b7280", annotation_text="0%")
    fig.update_layout(template="plotly_dark", paper_bgcolor="#111827", plot_bgcolor="#111827",
                      height=500, yaxis_title="YTD Return (%)" if st.session_state.lang=="ENG" else "YTD 수익률 (%)",
                      yaxis_ticksuffix="%",
                      legend=dict(bgcolor="#1f2937"), margin=dict(l=0,r=0,t=20,b=0))
    st.plotly_chart(fig, use_container_width=True)

    ytd_data = [{"ticker":c["ticker"],"name":c["name"],"ytd":stock_data.get(c["ticker"],{}).get("ytd_pct")}
                for c in all_display if stock_data.get(c["ticker"],{}).get("ytd_pct") is not None]
    if ytd_data:
        df_ytd = pd.DataFrame(ytd_data).sort_values("ytd", ascending=True)
        fig2 = go.Figure(go.Bar(
            x=df_ytd["ytd"], y=df_ytd["ticker"], orientation="h",
            marker_color=["#22c55e" if v>=0 else "#ef4444" for v in df_ytd["ytd"]],
            text=[f"{v:+.1f}%" for v in df_ytd["ytd"]], textposition="outside",
        ))
        fig2.update_layout(template="plotly_dark", paper_bgcolor="#111827", plot_bgcolor="#111827",
                            height=max(300,len(df_ytd)*38), xaxis_title="YTD (%)",
                            margin=dict(l=0,r=80,t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True)

# ══ Tab 3 ════════════════════════════════════════════════════════════════════
with tab3:
    current_only = CURRENT_HOLDINGS
    ca, cb = st.columns(2)
    with ca:
        sc_raw = {}
        for c in current_only: sc_raw[c["sector"]] = sc_raw.get(c["sector"],0)+1
        sc_labels = [sector_name(s) for s in sc_raw]
        fig3 = go.Figure(go.Pie(labels=sc_labels, values=list(sc_raw.values()),
            marker_colors=[SECTOR_COLORS.get(s,"#6b7280") for s in sc_raw], hole=0.4))
        fig3.update_layout(template="plotly_dark",paper_bgcolor="#111827",
            title=t("sector_count"),title_font_color="#f9fafb",height=380,margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig3, use_container_width=True)
    with cb:
        invest_data = [(c["name"], c["invest_amt_m"]) for c in current_only if c.get("invest_amt_m")]
        if invest_data:
            names, amts = zip(*invest_data)
            fig4 = go.Figure(go.Pie(labels=list(names), values=list(amts),
                marker_colors=[SECTOR_COLORS.get(c["sector"],"#6b7280") for c in current_only if c.get("invest_amt_m")],
                hole=0.4, texttemplate="%{label}<br>$%{value:,.0f}M"))
            fig4.update_layout(template="plotly_dark",paper_bgcolor="#111827",
                title=t("sector_invest"),title_font_color="#f9fafb",height=380,margin=dict(l=0,r=0,t=40,b=0))
            st.plotly_chart(fig4, use_container_width=True)

# ══ Tab 4: 뉴스 ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown(f"### {t('news_title')}")
    st.caption(t("news_caption"))
    news_map = {c["ticker"]: f"{c['name']} ({c['ticker']})" for c in all_display
                if "error" not in stock_data.get(c["ticker"],{})}
    sel_t = st.selectbox(t("news_stock"), list(news_map.keys()), format_func=lambda x: news_map[x])
    sel_c = next((c for c in all_display if c["ticker"]==sel_t), None)
    if sel_c:
        sd = stock_data.get(sel_t,{})
        n1,n2,n3 = st.columns([1.2, 1, 1])
        with n1:
            st.markdown(
                f'<div style="background:#0e0e0e;border:1px solid #2a2a2a;border-top:2px solid #76b900;'
                f'border-radius:4px;padding:16px 20px">'
                f'<div style="color:#484848;font-size:0.7rem;font-weight:600;letter-spacing:1.2px;'
                f'text-transform:uppercase;margin-bottom:8px">{t("news_price")}</div>'
                f'<div style="color:#e8e8e8;font-size:1.8rem;font-weight:600;letter-spacing:-0.5px;line-height:1">'
                f'{fmt_price(sd.get("price"), sd.get("currency","USD"))}</div>'
                f'</div>',
                unsafe_allow_html=True)
        with n2:
            st.markdown(
                f'<div style="padding:16px 4px">'
                f'<div style="color:#484848;font-size:0.7rem;font-weight:600;letter-spacing:1.2px;'
                f'text-transform:uppercase;margin-bottom:8px">{t("news_daily")}</div>'
                f'<div style="font-size:1.3rem;font-weight:600">{fmt_pct(sd.get("change_pct"))}</div>'
                f'</div>',
                unsafe_allow_html=True)
        with n3:
            st.markdown(
                f'<div style="padding:16px 4px">'
                f'<div style="color:#484848;font-size:0.7rem;font-weight:600;letter-spacing:1.2px;'
                f'text-transform:uppercase;margin-bottom:8px">YTD</div>'
                f'<div style="font-size:1.3rem;font-weight:600">{fmt_pct(sd.get("ytd_pct"))}</div>'
                f'</div>',
                unsafe_allow_html=True)
        st.markdown("---")
        with st.spinner(t("news_loading")):
            news_items = fetch_news(sel_t)
        shown = 0
        for item in news_items[:15]:
            content = item.get("content",{})
            title   = content.get("title") or item.get("title","")
            summary = content.get("summary","")
            pub_ts  = content.get("pubDate") or item.get("providerPublishTime") or ""
            pub_str = ts_to_str(pub_ts) if isinstance(pub_ts,(int,float)) else (pub_ts[:10] if pub_ts else "")
            url     = content.get("canonicalUrl",{}).get("url","") or item.get("link","")
            provider= content.get("provider",{}).get("displayName","") or item.get("publisher","")
            if not title: continue
            shown += 1
            lk = f'<a href="{url}" target="_blank" style="text-decoration:none;color:inherit">' if url else ""
            lke = "</a>" if url else ""
            st.markdown(f"""<div class="news-card">
              <div class="news-title">{lk}{title}{lke}</div>
              <div class="news-meta">{pub_str} · {provider}</div>
              {"<div style='color:#9ca3af;font-size:0.8rem;margin-top:4px'>" + summary[:160] + "…</div>" if summary else ""}
            </div>""", unsafe_allow_html=True)
        if shown == 0: st.info(t("no_news"))

# ══ Tab 5: 13F 히스토리 ══════════════════════════════════════════════════════
with tab5:
    st.markdown(f"### {t('filings_title')}")
    st.caption(t("filings_caption"))

    cf1, cf2 = st.columns([1,3])
    with cf1:
        all_cos = sorted({f["company"] for f in FILINGS_HISTORY})
        sel_cos = st.multiselect(t("filings_company"), all_cos, default=all_cos)
        ct_map = {
            "new":      "🟢 " + t("change_new"),
            "increase": "📈 " + t("change_increase"),
            "decrease": "📉 " + t("change_decrease"),
            "exit":     "⬛ " + t("change_exit"),
            "hold":     "🔵 " + t("change_hold"),
        }
        sel_ct = st.multiselect(t("filings_type"), list(ct_map.values()), default=list(ct_map.values()))
        sel_ct_keys = [k for k,v in ct_map.items() if v in sel_ct]

    with cf2:
        filtered_f = sorted(
            [f for f in FILINGS_HISTORY if f["company"] in sel_cos and f["change_type"] in sel_ct_keys],
            key=lambda x: x["filed"], reverse=True
        )
        _cs = get_change_style()
        for f in filtered_f:
            css, label = _cs.get(f["change_type"],("filing-hold","🔵 " + t("change_hold")))
            val = f"${f['value_m']:,.0f}M" if f.get("value_m") else ""
            val_html = f"&nbsp;&nbsp;<span style='color:#76b900;font-size:0.85rem;font-weight:700'>{val}</span>" if val else ""
            _change_txt = (f.get("change_eng") or f["change"]) if st.session_state.lang == "ENG" else f["change"]
            st.markdown(
                f'<div class="filing-row {css}">'
                f'<span style="color:#f9fafb;font-weight:600">{f["company"]} ({f["ticker"]})</span>'
                f'&nbsp;<span style="color:#9ca3af;font-size:0.82rem">{f["quarter"]} · {f["filed"]}</span><br>'
                f'<span style="font-size:0.9rem">{label} — {_change_txt}</span>'
                f'{val_html}'
                f'</div>',
                unsafe_allow_html=True)

    st.markdown(f"### {t('timeline_title')}")
    df_f = pd.DataFrame(FILINGS_HISTORY)
    color_map  = {"new":"#22c55e","increase":"#4a90d9","decrease":"#ef4444","exit":"#6b7280","hold":"#3b82f6"}
    label_map  = {
        "new":      t("change_new"),
        "increase": t("change_increase"),
        "decrease": t("change_decrease"),
        "exit":     t("change_exit"),
        "hold":     t("change_hold"),
    }
    fig6 = go.Figure()
    for ct, grp in df_f.groupby("change_type"):
        fig6.add_trace(go.Scatter(
            x=grp["filed"], y=grp["company"], mode="markers",
            name=label_map.get(ct, ct),
            marker=dict(color=color_map.get(ct, "#9ca3af"), size=14, symbol="circle"),
            customdata=grp["quarter"],
            hovertemplate="<b>%{y}</b><br>%{x}<br>%{customdata}<extra></extra>",
        ))
    fig6.update_layout(
        template="plotly_dark", paper_bgcolor="#111827", plot_bgcolor="#111827",
        height=500, xaxis_title=t("filings_xaxis"),
        legend=dict(bgcolor="#1f2937", orientation="h", y=1.12,
                    itemsizing="constant", traceorder="normal"),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig6, use_container_width=True)

# ── 어드민 피드백 뷰 (비밀번호 보호) ─────────────────────────────────────────
import json, os

st.markdown("---")
with st.expander("Admin", expanded=False):
    pw = st.text_input("비밀번호", type="password", key="admin_pw")
    ADMIN_PW = st.secrets.get("admin", {}).get("password", "엔비디아레츠고")

    if pw == ADMIN_PW:
        path = "feedback.json"
        data = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = []

        if not data:
            st.info("아직 접수된 피드백이 없습니다.")
        else:
            total = len(data)
            avg_rating = sum(d["rating"] for d in data) / total
            category_counts = {}
            for d in data:
                category_counts[d["category"]] = category_counts.get(d["category"], 0) + 1

            m1, m2, m3 = st.columns(3)
            with m1: st.metric("총 피드백", f"{total}건")
            with m2: st.metric("평균 만족도", f"{avg_rating:.1f} / 5.0")
            with m3: st.metric("가장 많은 유형", max(category_counts, key=category_counts.get).split(" ",1)[-1])

            st.markdown("---")
            sel_cat = st.selectbox("유형 필터", ["전체"] + list(category_counts.keys()), key="admin_cat")
            filtered_fb = data if sel_cat == "전체" else [d for d in data if d["category"] == sel_cat]

            for d in reversed(filtered_fb):
                stars = "⭐" * d["rating"]
                st.markdown(f"""
                <div class="news-card">
                  <div style="display:flex;justify-content:space-between">
                    <span style="color:#f9fafb;font-weight:600">{d['category']}</span>
                    <span style="color:#9ca3af;font-size:0.78rem">{d['time']} · {d['name']}</span>
                  </div>
                  <div style="color:#fbbf24;font-size:0.85rem;margin:4px 0">{stars}</div>
                  <div style="color:#d1d5db;font-size:0.88rem">{d['text']}</div>
                </div>""", unsafe_allow_html=True)
    elif pw:
        st.error("비밀번호가 틀렸습니다.")

# ── 푸터 ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:#2a2a2a;font-size:0.72rem;letter-spacing:0.5px'>"
    f"SEC EDGAR 13F &nbsp;·&nbsp; NVIDIA IR &nbsp;·&nbsp; Bloomberg &nbsp;·&nbsp; Reuters &nbsp;·&nbsp; FT &nbsp;·&nbsp; WSJ"
    f"&nbsp;&nbsp;|&nbsp;&nbsp;{t('footer_delay')}"
    f"&nbsp;&nbsp;|&nbsp;&nbsp;{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    f"</div>", unsafe_allow_html=True)
