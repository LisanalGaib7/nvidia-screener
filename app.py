import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import re
import time
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(
    page_title="NVIDIA Portfolio Tracker",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="auto",  # 데스크탑 펼침 / 모바일 접힘 (자동)
)

if "lang" not in st.session_state:
    st.session_state.lang = "KOR"

# 마지막 13F 검증일 — 분기 업데이트 시 여기 한 곳만 수정 (앱 표시용 단일 소스)
# ⚠️ scripts/check_13f.py 의 LAST_REFLECTED 는 별도 프로세스 — 함께 갱신 필요
LAST_VERIFIED = "2026-05-15"

TRANSLATIONS = {
    # 헤더
    "last_verified":        {"KOR": f"마지막 검증 {LAST_VERIFIED}",  "ENG": f"Last verified {LAST_VERIFIED}"},
    # 메트릭
    "metric_holdings":      {"KOR": "현재 13F 보유",                "ENG": "13F Holdings"},
    "metric_invested":      {"KOR": "확인된 투자액",                 "ENG": "Total Invested"},
    "metric_avg_ytd":       {"KOR": "평균 YTD",                     "ENG": "Avg YTD"},
    "metric_near_high":     {"KOR": "52주 신고가 근접",             "ENG": "Near 52W High"},
    "tooltip_13f":          {"KOR": "SEC 13F 공시 확인",             "ENG": "SEC 13F Confirmed"},
    "tooltip_invest_rank":  {"KOR": "투자금액 순",                   "ENG": "By Investment Size"},
    "tooltip_ytd_rank":     {"KOR": "YTD 수익률 순",                 "ENG": "By YTD Return"},
    "tooltip_near_high":    {"KOR": "52주 고가 대비 (5% 이내 강조)",  "ENG": "vs 52W High (≤5% highlighted)"},
    # 섹션 헤더
    "group_new":            {"KOR": "2026 신규 투자",                "ENG": "2026 New Investments"},
    "group_hold":           {"KOR": "기존 보유  ·  Q1 2026",         "ENG": "Current Holdings  ·  Q1 2026"},
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
    "sector_count":         {"KOR": "섹터별 투자액 비중", "ENG": "Investment by Sector"},
    "sector_invest":        {"KOR": "종목별 투자액 비중", "ENG": "Investment by Holding"},
    # 사이드바 데이터
    "sb_data_sources":      {"KOR": "데이터 출처",                   "ENG": "Data Sources"},
    "sb_media":             {"KOR": "글로벌 주요 언론 교차검증",       "ENG": "Global Media Cross-verification"},
    "sb_disclaimer":        {"KOR": "⚠️ 투자 조언 아님",              "ENG": "⚠️ Not Financial Advice"},
    "sb_delay":             {"KOR": "Data: Yahoo Finance", "ENG": "Data: Yahoo Finance"},
    "sb_asof":              {"KOR": "전일 종가 기준", "ENG": "Prev. close"},
    "sb_refresh":           {"KOR": "↻ 새로고침",                    "ENG": "↻ Refresh"},
    "csv_export":           {"KOR": "⬇ CSV 내보내기",                 "ENG": "⬇ Export CSV"},
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
    "footer_delay":         {"KOR": "Yahoo Finance · 전일 종가 기준",   "ENG": "Yahoo Finance · Prev. close"},
    "detail_basis":         {"KOR": "투자 근거",                      "ENG": "Investment Basis"},
}

def t(key):
    lang = st.session_state.get("lang", "KOR")
    return TRANSLATIONS.get(key, {}).get(lang, key)

# ── Google Analytics 4 ───────────────────────────────────────────────────────
# components.html srcdoc iframe은 null-origin → GA4 히트가 Google에 안 나감.
# window.parent(앱 iframe, same-origin)에 스크립트를 직접 주입.
import streamlit.components.v1 as components
components.html("""
<script>
(function() {
  var p = window.parent;
  if (!p || p.gaInjected) return;
  p.gaInjected = true;
  var s = p.document.createElement('script');
  s.async = true;
  s.src = 'https://www.googletagmanager.com/gtag/js?id=G-BEQNGDCDKC';
  p.document.head.appendChild(s);
  p.dataLayer = p.dataLayer || [];
  p.gtag = function(){ p.dataLayer.push(arguments); };
  p.gtag('js', new Date());
  p.gtag('config', 'G-BEQNGDCDKC', {
    'page_location': 'https://nvidiascreener.streamlit.app/',
    'page_title': 'NVIDIA Portfolio Tracker'
  });
})();
</script>
""", height=0)

st.markdown("""
<style>
  /* ── 기본 배경 ── */
  .stApp, .main, section[data-testid="stSidebar"] > div:first-child {
    background-color: #080808;
  }
  section[data-testid="stSidebar"] { background-color: #0c0c0c; border-right: 1px solid #1a1a1a; }

  /* ── 사이드바 펼침 토글 (접힘 상태에서만 노출 = 주로 모바일) ── */
  /* Streamlit 1.57: 컨트롤은 button[data-testid="stExpandSidebarButton"] 자체,
     아이콘은 머티리얼 폰트(stIconMaterial). 구버전 testid도 함께 커버. */
  button[data-testid="stExpandSidebarButton"],
  [data-testid="stSidebarCollapsedControl"] button,
  [data-testid="collapsedControl"] button {
    width: 40px !important;
    height: 40px !important;
    border-radius: 9px !important;
    background: #0e0e0e !important;
    border: 1.5px solid #76b900 !important;
    animation: sb-pulse 1.6s ease-in-out infinite;
    position: relative !important;
    overflow: hidden;
  }
  /* 기본 화살표 아이콘(머티리얼 폰트 / svg) 숨김 */
  button[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
  button[data-testid="stExpandSidebarButton"] svg,
  [data-testid="stSidebarCollapsedControl"] button [data-testid="stIconMaterial"],
  [data-testid="collapsedControl"] button [data-testid="stIconMaterial"],
  [data-testid="stSidebarCollapsedControl"] button svg,
  [data-testid="collapsedControl"] button svg { display: none !important; }
  /* ☰ 햄버거로 교체 */
  button[data-testid="stExpandSidebarButton"]::after,
  [data-testid="stSidebarCollapsedControl"] button::after,
  [data-testid="collapsedControl"] button::after {
    content: "☰";
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    color: #76b900 !important;
    font-size: 20px;
    line-height: 1;
  }
  @keyframes sb-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(118,185,0,0.5); }
    50%      { box-shadow: 0 0 0 8px rgba(118,185,0,0); }
  }

  /* ── 상단 툴바: Share(라벨)만 남기고 아이콘 액션(편집·GitHub·⋮ 등) 숨김 ── */
  /* Share는 stToolbarActionButtonLabel, 나머지는 stToolbarActionButtonIcon 보유 → :has로 구분 */
  [data-testid="stToolbarActionButton"]:has([data-testid="stToolbarActionButtonIcon"]) {
    display: none !important;
  }

  /* ── 타이포그래피 ── */
  html, body, [class*="css"] { font-family: 'Inter', 'SF Pro Display', system-ui, sans-serif; }
  h1 { color: #f0f0f0 !important; font-size: 1.7rem !important; font-weight: 600 !important; letter-spacing: -0.5px !important; }
  h2 { color: #d0d0d0 !important; font-size: 1.1rem !important; font-weight: 500 !important; letter-spacing: 0.3px !important; }
  h3 { color: #a0a0a0 !important; font-size: 0.8rem !important; font-weight: 600 !important;
       text-transform: uppercase; letter-spacing: 1.4px !important; }
  p, .stMarkdown p { color: #606060 !important; font-size: 0.88rem; line-height: 1.6; }

  /* ── 강조 텍스트 ── */
  .txt-primary   { color: #e8e8e8; }
  .txt-secondary { color: #9aa3b0; }
  .txt-accent    { color: #76b900; font-weight: 600; }
  .txt-gold      { color: #c87f00; font-weight: 600; }
  .txt-dim       { color: #6b7280; font-size: 0.75rem; letter-spacing: 0.3px; }

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
  .alert-item  { display: flex; align-items: baseline; gap: 10px; padding: 7px 0; font-size: 0.84rem; line-height: 1.5; }
  .alert-item + .alert-item { border-top: 1px solid #1c1c1c; }
  .alert-date  { color: #7a8290; font-size: 0.72rem; min-width: 82px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .alert-co    { color: #e0e0e0; font-weight: 600; }
  .alert-desc  { color: #9aa3b0; }

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
  .filing-new      { border-left: 3px solid #22c55e !important; }
  .filing-increase { border-left: 3px solid #4a90d9 !important; }
  .filing-decrease { border-left: 3px solid #e05656 !important; }
  .filing-exit     { border-left: 3px solid #8b949e !important; }
  .filing-hold     { border-left: 3px solid #6366f1 !important; }

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


  /* segmented_control(lazy 탭) — 선택탭 '채운 박스' + 모바일 1줄 가로 스크롤. 실제 DOM: stButtonGroup + stBaseButton-segmented_control(Active) */
  .st-key-main_tabs div[data-testid="stButtonGroup"] { position: relative !important; }
  .st-key-main_tabs div[data-testid="stButtonGroup"] > div[data-baseweb="button-group"] {
    border: 1px solid rgba(255,255,255,0.06) !important; border-radius: 10px !important;
    background: rgba(255,255,255,0.025) !important;  /* 미세 배경 — 탭 그룹을 하나로 묶어 또렷하게 */
    gap: 6px !important; padding: 5px !important;
    flex-wrap: nowrap !important; overflow-x: auto !important;
    scrollbar-width: none !important;
  }
  .st-key-main_tabs div[data-testid="stButtonGroup"] > div[data-baseweb="button-group"]::-webkit-scrollbar { display: none !important; }
  button[data-testid="stBaseButton-segmented_control"],
  button[data-testid="stBaseButton-segmented_controlActive"] {
    color: #6b7280 !important;
    font-size: 0.72rem !important; font-weight: 600 !important;
    letter-spacing: 1.6px !important; text-transform: uppercase !important;
    padding: 9px 18px !important;
    background: transparent !important; border: 1px solid transparent !important;
    border-radius: 6px !important; box-shadow: none !important; white-space: nowrap !important;
    flex-shrink: 0 !important;  /* 자연 폭 유지 → 압축(글자 잘림) 대신 넘치면 가로 스크롤 */
    transition: color 0.2s ease, background 0.2s ease, border-color 0.2s ease !important;
  }
  button[data-testid="stBaseButton-segmented_control"]:hover { color: #909090 !important; background: transparent !important; }
  button[data-testid="stBaseButton-segmented_controlActive"] {
    color: #cfe99a !important;
    background: rgba(118,185,0,0.14) !important;
    border: 1px solid #76b900 !important;
  }
  /* 모바일: 탭 가로 스크롤 시 우측 그라데이션으로 '더 있음' 암시 */
  @media (max-width: 640px) {
    .st-key-main_tabs div[data-testid="stButtonGroup"]::after {
      content: "\\203A"; position: absolute; top: 0; right: 0; bottom: 8px;
      width: 46px; pointer-events: none; z-index: 1;
      display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;
      color: #76b900; font-size: 22px; font-weight: 700; line-height: 1;
      background: linear-gradient(to right, rgba(8,8,8,0), #080808 70%) !important;
    }
  }

  /* ── 사이드바 텍스트 ── */
  .stSidebar h2, .stSidebar h3 { color: #e0e0e0 !important; }
  .stSidebar p, .stSidebar label { color: #909090 !important; }
  .stSidebar li { color: #909090 !important; }
  .stSidebar .stSelectbox label, .stSidebar .stMultiSelect label { color: #909090 !important; font-size:0.72rem !important; letter-spacing:0.8px; text-transform:uppercase; }

  /* ── 버튼 (일반 + 다운로드 통일) ── */
  .stButton > button, .stDownloadButton > button {
                       background: transparent !important; border: 1px solid #242424 !important;
                       color: #505050 !important; border-radius: 3px !important; font-size: 0.75rem !important;
                       letter-spacing: 0.5px; transition: all 0.2s; font-weight: 400 !important; }
  .stButton > button:hover, .stDownloadButton > button:hover {
                       border-color: #76b900 !important; color: #76b900 !important; }

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

  /* ── 포트폴리오 테이블 (데스크탑 그리드) ── */
  .ptable-header {
    display: grid;
    grid-template-columns: 2.8fr 1fr 1.1fr 1.1fr 1.1fr 0.8fr 1.4fr;
    padding: 0 4px 8px;
    border-bottom: 1px solid #1e1e1e;
    gap: 6px;
  }
  .ptable-header > span { color: #909090; font-size: 0.8rem; font-weight: 500; }
  .ptable-row {
    display: grid;
    grid-template-columns: 2.8fr 1fr 1.1fr 1.1fr 1.1fr 0.8fr 1.4fr;
    align-items: center;
    padding: 10px 4px;
    border-bottom: 1px solid #141414;
    gap: 6px;
  }
  .ptable-row:hover { background: #0d0d0d; border-radius: 3px; }

  /* detail 펼치기 버튼 */
  .pt-detail details > summary {
    color: #505050; font-size: 0.68rem; letter-spacing: 0.8px;
    text-transform: uppercase; border: 1px solid #2e2e2e;
    border-radius: 2px; padding: 2px 8px; cursor: pointer;
    list-style: none; display: inline-block; transition: all 0.15s; user-select: none;
  }
  .pt-detail details > summary::-webkit-details-marker { display: none; }
  .pt-detail details > summary::marker { display: none; }
  .pt-detail details > summary:hover { border-color: #76b900; color: #76b900; }
  .pt-detail details[open] > summary { border-color: #76b900; color: #76b900; }
  /* pt-detail-body: 기본 숨김 */
  .pt-detail-body {
    display: none;
    background: #101010; border: 1px solid #242424;
    border-radius: 4px; padding: 16px 18px;
    min-width: 300px; max-width: 360px;
  }
  /* detail body 내부 구조 */
  .ptd-header {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 10px; padding-bottom: 10px;
    border-bottom: 1px solid #1e1e1e;
  }
  .ptd-ticker { color: #76b900; font-size: 0.85rem; font-weight: 700; letter-spacing: 0.8px; }
  .ptd-sector { color: #8b949e; font-size: 0.68rem; }
  .ptd-label  { color: #3a3a3a; font-size: 0.58rem; font-weight: 600;
                letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 4px; }
  .ptd-amount { color: #c87f00; font-size: 1.05rem; font-weight: 600; margin-bottom: 10px; }
  .ptd-thesis { color: #b0b0b0; font-size: 0.8rem; line-height: 1.7; margin-bottom: 10px; }
  .ptd-summary { color: #e8e8e8; font-size: 0.85rem; font-weight: 500; line-height: 1.6; margin-bottom: 12px; }
  .ptd-footer { display: flex; justify-content: space-between; align-items: flex-start;
                padding-top: 8px; border-top: 1px solid #1e1e1e; gap: 8px; flex-wrap: wrap; }
  .ptd-date   { color: #505050; font-size: 0.65rem; white-space: nowrap; }
  .ptd-src    { color: #3a3a3a; font-size: 0.62rem; text-align: right; }

  /* ── 데스크탑 전용: hover 팝업 ───────────────────────────── */
  @media screen and (min-width: 769px) {
    .pt-detail { position: relative; }
    /* 클릭 토글 비활성화 */
    .pt-detail details > summary { pointer-events: none; cursor: default; }
    /* hover 시 절대위치 팝업 */
    .pt-detail:hover .pt-detail-body {
      display: block;
      position: absolute;
      z-index: 200;
      right: 0;
      bottom: calc(100% + 6px);
      min-width: 280px;
      max-width: 340px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.7);
    }
    /* hover 시 summary 강조 */
    .pt-detail:hover details > summary { border-color: #76b900; color: #76b900; }
  }

  /* 모바일 전용 요소 — 데스크탑에서 숨김 */
  .pt-stats, .pt-meta { display: none; }
  .pt-stat-label {
    color: #404040; font-size: 0.6rem; letter-spacing: 0.8px;
    text-transform: uppercase; display: block; margin-bottom: 3px;
  }

  /* ── 모바일 반응형 ─────────────────────────────────────── */
  @media screen and (max-width: 768px) {
    /* 모바일: 상단 툴바 액션 전부 숨김 (viewer의 Fork·GitHub·⋮ 포함).
       모바일에서 공유는 사이드바 '공유하기' 섹션으로. ☰ 토글은 별도라 유지됨 */
    [data-testid="stToolbarActions"] { display: none !important; }

    /* 전체 패딩 축소 */
    .main .block-container { padding: 1rem 0.8rem !important; }

    /* 헤더 — vw 비례(기종 무관 동일 비율로 채움, 한 줄 유지) */
    .nv-title  { font-size: 3.1vw !important; letter-spacing: 0.5px !important; }
    .nv-cursor { font-size: 3.1vw !important; }
    .nv-logo   { font-size: 4.3vw !important; top: -5px !important; }

    /* 알림 배너 — 더 촘촘하게 */
    .alert-banner { padding: 10px 12px; margin-bottom: 14px; }
    .alert-title  { font-size: 0.62rem; }
    .alert-item   { font-size: 0.76rem; gap: 8px; }
    .alert-date   { font-size: 0.65rem; min-width: 66px; }


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

    /* 뉴스·공시 카드 패딩 축소 */
    .news-card  { padding: 10px 12px; }
    .filing-row { padding: 8px 12px; }

    /* ── 포트폴리오 카드 레이아웃 (모바일) ── */
    .ptable-header { display: none; }
    .ptable-row {
      display: block !important;
      background: #0e0e0e;
      border: 1px solid #1e1e1e;
      border-left: 3px solid var(--accent, #333);
      border-radius: 4px;
      padding: 12px 14px;
      margin-bottom: 8px;
    }
    /* 데스크탑 전용 셀 숨김 */
    .pt-price, .pt-daily, .pt-ytd, .pt-cap, .pt-pe { display: none !important; }
    /* 모바일 통계 표시 */
    .pt-stats {
      display: grid !important;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 10px;
      margin: 10px 0 8px;
    }
    .pt-meta {
      display: flex !important;
      gap: 14px;
      flex-wrap: wrap;
      padding-top: 8px;
      border-top: 1px solid #1a1a1a;
      margin-bottom: 10px;
    }
    /* detail 버튼 — 전체 너비 */
    .pt-detail { display: block !important; }
    .pt-detail details > summary {
      display: block;
      text-align: center;
      padding: 6px 8px;
      width: 100%;
      box-sizing: border-box;
      pointer-events: auto;
      cursor: pointer;
    }
    /* 클릭해서 <details open> 되면 형제 body 표시 */
    .pt-detail details[open] ~ .pt-detail-body {
      display: block;
      max-width: 100%;
      margin-top: 8px;
    }
  }

  @media screen and (max-width: 480px) {
    .nv-title, .nv-cursor { font-size: 3.1vw !important; }
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
        "invest_amt_m": 1855.0,
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
        "invest_amt_m": 3660.0,
        "invest_date": "2025-03-28",
        "badge": "core",
        "exchange": "NASDAQ",
        "is_new_alert": True,
        "alert_date": "2026-05-15",
        "nvidia_thesis": "NVIDIA GPU 특화 하이퍼스케일러 — H100/B200 최대 보유 AI 클라우드. Q1 2026 13F: 47.2M주 ($3.66B), +95% 증가",
        "nvidia_thesis_eng": "NVIDIA GPU-specialized hyperscaler — largest H100/B200 AI cloud. Q1 2026 13F: 47.2M shares ($3.66B), +95% increase",
        "note": "13F 지분 +95% 증가 → $3.66B | 47.2M주, 2025.03 IPO 참여 | NVIDIA 전략적 주주·최대 고객",
        "note_eng": "13F stake +95% → $3.66B | 47.2M shares, 2025.03 IPO | NVIDIA strategic shareholder & top customer",
        "source": "CoreWeave IPO Filing (2025.03) · SEC 13F Q1 2026 (2026.05.15)",
    },
    {
        "ticker": "NBIS",
        "name": "Nebius Group",
        "sector": "클라우드 GPU",
        "invest_year": 2024,
        "invest_amt_m": 2100.0,
        "invest_date": "2026-03-11",
        "badge": "core",
        "exchange": "NASDAQ",
        "is_new_alert": True,
        "alert_date": "2026-03-11",
        "nvidia_thesis": "풀스택 AI 클라우드 파트너 — NVIDIA 시스템 2030년까지 5GW 배포. $2B 추가 투자 (2026.03) + $100M (2024.12), 누적 $2.1B",
        "nvidia_thesis_eng": "Full-stack AI cloud partner — 5GW NVIDIA systems deployment by 2030. $2B follow-on (2026.03) + $100M (2024.12), total $2.1B",
        "note": "$2B 추가 투자 (2026.03.11) + $100M (2024.12) = 누적 $2.1B | 5GW AI 인프라 2030",
        "note_eng": "$2B follow-on (2026.03.11) + $100M (2024.12) = $2.1B total | 5GW AI infra by 2030",
        "source": "NVIDIA Newsroom (2026.03.11) · NVIDIA IR (2024.12.10)",
    },
]

# ── 전략 파트너십 (지분투자 아님) ────────────────────────────────────────────
PARTNERSHIPS = [
    {
        "ticker": "PLTR",
        "name": "Palantir",
        "sector": "AI 소프트웨어",
        "invest_year": 2025,
        "invest_amt_m": None,
        "invest_date": "2025-10-01",
        "badge": "partner",
        "exchange": "NYSE",
        "is_new_alert": False,
        "alert_date": "2025-10-01",
        "nvidia_thesis": "Sovereign AI OS — NVIDIA Blackwell Ultra 하드웨어 + Palantir AIP·Ontology 풀스택. Jensen: \"세계에서 가장 중요한 엔터프라이즈 스택\"",
        "nvidia_thesis_eng": "Sovereign AI OS — NVIDIA Blackwell Ultra hardware + Palantir AIP·Ontology full-stack. Jensen: \"The single most important enterprise stack in the world\"",
        "note": "⚠️ 지분투자 아님 | Sovereign AI OS 공동 제품 (온프레미스·에어갭 AI 배포) | NVIDIA 모델 → AIP 제공",
        "note_eng": "⚠️ No equity investment | Sovereign AI OS joint product (on-prem & air-gapped AI deployment) | NVIDIA models via AIP",
        "source": "NVIDIA Newsroom, Palantir IR",
    },
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

# ── 현재 13F 보유 (메트릭 카운트 + 툴팁 단일 소스) ────────────────────────────
# 분기 업데이트 시 이 목록만 수정하면 "N개 종목" 카운트와 13F 툴팁이 자동 반영됨.
# 주의: 워런트/우선주(IREN·GLW·MRVL·LITE)는 13F 미포함이라 제외. GENB는 비상장이라
# 시세 카드는 없지만 13F 지분 보유분이라 포함.
THIRTEEN_F = [
    {"ticker": "INTC", "name": "Intel",              "is_new": False},
    {"ticker": "CRWV", "name": "CoreWeave",          "is_new": False},
    {"ticker": "SNPS", "name": "Synopsys",           "is_new": False},
    {"ticker": "COHR", "name": "Coherent Corp",      "is_new": True},
    {"ticker": "NOK",  "name": "Nokia",              "is_new": False},
    {"ticker": "NBIS", "name": "Nebius Group",       "is_new": False},
    {"ticker": "GENB", "name": "Generate Bio",       "is_new": True},
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

# ── 포트폴리오 호버 설명(한국어) — 3섹션 구조: (한 줄 요약, 왜 투자했나, 투자 구조) ──
# 수치는 데이터(nvidia_thesis)와 동일, 표현만 쉽게 재작성. 없는 종목은 기존 thesis fallback.
THESIS_KO = {
    "IREN": (
        "엔비디아 GPU로 돌아가는 5GW급 AI 데이터센터를 짓는 회사",
        "늘어나는 AI 연산 수요를 감당할 대형 데이터센터 파트너가 필요했고, IREN이 그 인프라를 맡습니다. GPU 클라우드 서비스도 5년간 함께 제공합니다.",
        "워런트 방식 최대 $2.1B (30M주 @$70) · 5년 $3.4B GPU 클라우드 계약 병행",
    ),
    "GLW": (
        "엔비디아 AI 데이터센터에 들어가는 광섬유를 미국에서 생산하는 회사",
        "데이터센터 간 광연결 수요가 폭증하는데, 코닝이 미국 내 생산을 책임집니다. 새 공장 3곳(노스캐롤라이나·텍사스)으로 미국 광학 생산을 10배 늘립니다.",
        "$500M 선불 워런트 (행사가 $180) · 최대 $3.2B · 일자리 3,000개",
    ),
    "MRVL": (
        "엔비디아 GPU와 한 랙에서 초고속으로 연결되는 맞춤형 AI 칩을 만드는 회사",
        "엔비디아 차세대 GPU(Rubin)·CPU(Vera)와 마벨 칩을 같은 랙에서 1.8TB/s로 묶는 'NVLink Fusion' 기술을 함께 만듭니다. 빛으로 데이터를 나르는 실리콘 포토닉스도 공동 개발합니다.",
        "$2B 투자 · NVLink Fusion 파트너십 · 실리콘 포토닉스·5G/6G 공동 R&D",
    ),
    "LITE": (
        "AI 데이터센터 광통신에 쓰는 레이저·포토닉스 부품을 만드는 회사",
        "광연결의 핵심인 고급 레이저 부품을 루멘텀이 독점 공급합니다. 미국 내 새 생산시설(fab)도 짓습니다.",
        "$2B 우선주 사모 (2,876,415주 @$695.31) · 멀티빌리언 구매 약정 포함",
    ),
    "COHR": (
        "AI 데이터센터의 초고속 광신호 송수신 장치(트랜시버)를 만드는 회사",
        "데이터센터 광연결 속도가 800G·1.6T로 빨라지는데, 코히런트가 그 트랜시버를 공급합니다. 미국 내 제조도 늘립니다.",
        "$2B 투자 · 광학 네트워킹 제품 구매 약정 포함",
    ),
    "INTC": (
        "엔비디아 GPU와 인텔 CPU를 한 칩에 합친 제품을 함께 만드는 회사",
        "인텔 x86 CPU와 엔비디아 GPU를 '칩렛'으로 묶어 AI 데이터센터·PC용 통합 칩을 개발합니다. 엔비디아가 직접 지분 4%를 사들인 몇 안 되는 사례입니다.",
        "$5B 직접 지분투자 (4%, 214.7M주 @$23.28)",
    ),
    "SNPS": (
        "반도체 설계를 자동화하는 소프트웨어(EDA)를 만드는 회사",
        "칩 설계 과정을 AI로 자동화하고 클라우드로 가속합니다. 엔비디아 칩을 더 빠르게 설계하는 데 핵심입니다.",
        "$2B 사모 발행 (@$414.79/주)",
    ),
    "NOK": (
        "엔비디아 GPU를 통신 기지국에 넣어 AI 이동통신망을 만드는 회사",
        "노키아 5G/6G 기지국(RAN)에 엔비디아 GPU를 통합해, AI가 돌아가는 차세대 통신 인프라를 개발합니다.",
        "$1B 투자 · 2.9% 지분 (@$6.01/주)",
    ),
    "CRWV": (
        "엔비디아 최신 GPU를 가장 많이 보유한 AI 전용 클라우드 회사",
        "엔비디아 H100·B200을 대규모로 굴리는 AI 클라우드로, 엔비디아의 전략적 주주이자 최대 고객입니다.",
        "Q1 2026 13F: 47.2M주 $3.66B (+95% 증가) · 2025.03 IPO 참여",
    ),
    "NBIS": (
        "엔비디아 시스템을 대규모로 배포하는 풀스택 AI 클라우드 회사",
        "2030년까지 5GW 규모의 엔비디아 시스템을 깔기로 했습니다. 엔비디아가 2024년부터 두 차례 투자한 핵심 파트너입니다.",
        "$2B 추가 투자 (2026.03) + $100M (2024.12) = 누적 $2.1B",
    ),
    "PLTR": (
        "기업·정부용 'Sovereign AI 운영체제'를 엔비디아와 함께 만드는 회사",
        "엔비디아 Blackwell Ultra 하드웨어 위에 팔란티어 AIP·온톨로지를 얹어, 외부망과 분리된(온프레미스·에어갭) AI를 통째로 제공합니다. 젠슨 황이 '세계에서 가장 중요한 엔터프라이즈 스택'이라 부른 협력입니다.",
        "⚠️ 지분투자 아님 · 공동 제품 파트너십 (엔비디아 모델 → AIP 제공)",
    ),
    "6954.T": (
        "엔비디아 AI를 산업용 로봇에 넣는 일본 로봇 회사",
        "엔비디아 Isaac Sim으로 로봇을 가상에서 훈련(디지털 트윈)하고, Jetson 컴퓨터를 로봇에 탑재해 'Physical AI'를 구현합니다. 발표 당일 주가가 +9.4% 뛰었습니다.",
        "⚠️ 지분투자 아님 · Physical AI 파트너십 · Isaac Sim + Jetson 통합",
    ),
}

# 영어판 — 동일 3섹션 구조 (In a nutshell / Why NVIDIA invested / Deal structure)
THESIS_EN = {
    "IREN": (
        "A company building a 5GW AI data center powered by NVIDIA GPUs",
        "NVIDIA needed a large data-center partner to handle surging AI compute demand, and IREN provides that infrastructure — paired with a 5-year GPU cloud services agreement.",
        "Warrant-based up to $2.1B (30M shares @$70) · 5-yr $3.4B GPU cloud deal",
    ),
    "GLW": (
        "Makes the optical fiber for NVIDIA AI data centers, manufactured in the US",
        "Data-center optical interconnect demand is exploding, and Corning handles US production — 3 new factories (NC·TX) lift US optical output 10x.",
        "$500M upfront warrants (strike $180) · up to $3.2B · 3,000 jobs",
    ),
    "MRVL": (
        "Makes custom AI chips that link to NVIDIA GPUs at ultra-high speed in the same rack",
        "Co-develops 'NVLink Fusion' — binding Marvell's XPU with NVIDIA's next-gen Rubin GPU & Vera CPU in one rack at 1.8TB/s. Also co-developing silicon photonics (moving data with light).",
        "$2B investment · NVLink Fusion partnership · silicon photonics & 5G/6G co-R&D",
    ),
    "LITE": (
        "Makes the laser & photonics components used in AI data-center optical networking",
        "Lumentum is the exclusive supplier of the high-end laser components central to optical interconnects, and is building a new US fab.",
        "$2B preferred-stock placement (2,876,415 shares @$695.31) · multi-billion purchase commitment",
    ),
    "COHR": (
        "Makes the high-speed optical transceivers that send/receive signals in AI data centers",
        "As data-center optical links jump to 800G·1.6T, Coherent supplies those transceivers and is expanding US manufacturing.",
        "$2B investment · optical networking purchase commitment included",
    ),
    "INTC": (
        "Co-develops products that fuse NVIDIA GPUs with Intel CPUs on a single chip",
        "Pairs Intel x86 CPUs with NVIDIA GPUs as 'chiplets' for integrated AI data-center & PC chips. One of the rare cases where NVIDIA took a direct 4% stake.",
        "$5B direct equity stake (4%, 214.7M shares @$23.28)",
    ),
    "SNPS": (
        "Makes the software (EDA) that automates chip design",
        "Automates chip design with AI and accelerates it on the cloud — key to designing NVIDIA's own chips faster.",
        "$2B private placement (@$414.79/share)",
    ),
    "NOK": (
        "Puts NVIDIA GPUs into telecom base stations to build AI mobile networks",
        "Integrates NVIDIA GPUs into Nokia's 5G/6G base stations (RAN) to develop AI-driven next-gen telecom infrastructure.",
        "$1B investment · 2.9% stake (@$6.01/share)",
    ),
    "CRWV": (
        "The AI-dedicated cloud holding the most of NVIDIA's latest GPUs",
        "An AI cloud running NVIDIA H100·B200 at massive scale — NVIDIA's strategic shareholder and top customer.",
        "Q1 2026 13F: 47.2M shares $3.66B (+95%) · joined 2025.03 IPO",
    ),
    "NBIS": (
        "A full-stack AI cloud deploying NVIDIA systems at scale",
        "Committed to deploying 5GW of NVIDIA systems by 2030. A core partner NVIDIA has invested in twice since 2024.",
        "$2B follow-on (2026.03) + $100M (2024.12) = $2.1B total",
    ),
    "PLTR": (
        "Co-builds a 'Sovereign AI operating system' for enterprises & governments with NVIDIA",
        "Stacks Palantir AIP·Ontology on NVIDIA Blackwell Ultra hardware to deliver fully self-contained (on-prem & air-gapped) AI. Jensen Huang called it 'the single most important enterprise stack in the world.'",
        "⚠️ Not an equity investment · joint product partnership (NVIDIA models via AIP)",
    ),
    "6954.T": (
        "A Japanese robotics company putting NVIDIA AI into industrial robots",
        "Trains robots virtually with NVIDIA Isaac Sim (digital twin) and embeds Jetson on-robot computers to realize 'Physical AI.' FANUC stock jumped +9.4% on the announcement.",
        "⚠️ Not an equity investment · Physical AI partnership · Isaac Sim + Jetson integration",
    ),
}

# ── 13F 공시 히스토리 (검증된 것만) ─────────────────────────────────────────
FILINGS_HISTORY = [
    # 2026 Q2 신규  —  change/change_eng = 상태어·중복금액 제거한 '상세'만 (배지·우측금액이 상태·총액 담당)
    {"ticker":"IREN", "company":"IREN Ltd",          "quarter":"Q2 2026","filed":"2026-05-07","change":"워런트 · 행사가 $70",                "change_eng":"Warrant · strike $70",                     "change_type":"new",      "value_m":2100.0},
    {"ticker":"GLW",  "company":"Corning",           "quarter":"Q2 2026","filed":"2026-05-06","change":"워런트 · 선불 $500M",                "change_eng":"Warrant · $500M upfront",                  "change_type":"new",      "value_m":3200.0},
    # 2026 Q1 — 13F 공시 (2026-05-15)
    {"ticker":"CRWV", "company":"CoreWeave",         "quarter":"Q1 2026","filed":"2026-05-15","change":"24.3M → 47.2M주 (+95%)",            "change_eng":"24.3M → 47.2M shares (+95%)",              "change_type":"increase", "value_m":3660.0},
    {"ticker":"COHR", "company":"Coherent Corp",     "quarter":"Q1 2026","filed":"2026-05-15","change":"보통주 13F · 7.8M주",               "change_eng":"13F common · 7.8M shares",                 "change_type":"new",      "value_m":1855.0},
    {"ticker":"GENB", "company":"Generate Biomedicines","quarter":"Q1 2026","filed":"2026-05-15","change":"비상장 지분",                    "change_eng":"Private stake",                            "change_type":"new",      "value_m":10.4},
    {"ticker":"MRVL", "company":"Marvell Technology","quarter":"Q1 2026","filed":"2026-03-31","change":"전환우선주 · 전환 시 최대 21.78M주",  "change_eng":"Convertible preferred · up to 21.78M shares","change_type":"new",    "value_m":2000.0},
    {"ticker":"LITE", "company":"Lumentum",          "quarter":"Q1 2026","filed":"2026-03-02","change":"전환우선주 · 전환 시 2.88M주",        "change_eng":"Convertible preferred · 2.88M shares",     "change_type":"new",      "value_m":2000.0},
    # 2025 보유
    {"ticker":"INTC", "company":"Intel",             "quarter":"Q3 2025","filed":"2025-09-18","change":"사모(PIPE) · @$23.28",              "change_eng":"PIPE · @$23.28",                           "change_type":"new",      "value_m":5000.0},
    {"ticker":"INTC", "company":"Intel",             "quarter":"Q4 2025","filed":"2025-12-29","change":"214.7M주 취득 완료 (~4%)",           "change_eng":"214.7M shares acquired (~4%)",             "change_type":"increase", "value_m":5000.0},
    {"ticker":"SNPS", "company":"Synopsys",          "quarter":"Q4 2025","filed":"2025-12-01","change":"사모(PIPE)",                        "change_eng":"PIPE",                                     "change_type":"new",      "value_m":2000.0},
    {"ticker":"NOK",  "company":"Nokia",             "quarter":"Q3 2025","filed":"2025-10-28","change":"보통주 · 2.9% 지분",                "change_eng":"Common · 2.9% stake",                      "change_type":"new",      "value_m":1000.0},
    {"ticker":"NBIS", "company":"Nebius Group",      "quarter":"Q1 2026","filed":"2026-03-11","change":"사모(PIPE) · 추가 투자",            "change_eng":"PIPE · follow-on",                         "change_type":"increase","value_m":2000.0},
    {"ticker":"NBIS", "company":"Nebius Group",      "quarter":"Q4 2024","filed":"2024-12-10","change":"사모(PIPE)",                        "change_eng":"PIPE",                                     "change_type":"new",      "value_m":100.0},
    {"ticker":"CRWV", "company":"CoreWeave",         "quarter":"Q1 2025","filed":"2025-03-28","change":"IPO 참여",                          "change_eng":"IPO participation",                        "change_type":"new",      "value_m":None},
    # 청산
    {"ticker":"RXRX", "company":"Recursion Pharma", "quarter":"Q3 2023","filed":"2023-07-12","change":"사모(PIPE)",                         "change_eng":"PIPE",                                     "change_type":"new",      "value_m":50.0},
    {"ticker":"RXRX", "company":"Recursion Pharma", "quarter":"Q4 2025","filed":"2026-02-17","change":"전량 청산",                          "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"ARM",  "company":"Arm Holdings",     "quarter":"Q3 2023","filed":"2023-09-14","change":"IPO 참여",                            "change_eng":"IPO participation",                        "change_type":"new",      "value_m":None},
    {"ticker":"ARM",  "company":"Arm Holdings",     "quarter":"Q4 2025","filed":"2026-02-17","change":"전량 청산 · 1.1M주",                "change_eng":"Full exit · 1.1M shares",                  "change_type":"exit",     "value_m":140.0},
    {"ticker":"WRD",  "company":"WeRide",           "quarter":"Q4 2024","filed":"2025-02-14","change":"보통주 13F · 1.7M주",               "change_eng":"13F common · 1.7M shares",                 "change_type":"new",      "value_m":24.0},
    {"ticker":"WRD",  "company":"WeRide",           "quarter":"Q4 2025","filed":"2026-02-17","change":"전량 청산",                          "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"SOUN", "company":"SoundHound AI",    "quarter":"Q4 2023","filed":"2024-02-14","change":"보통주 13F · 1.73M주",              "change_eng":"13F common · 1.73M shares",                "change_type":"new",      "value_m":3.99},
    {"ticker":"SOUN", "company":"SoundHound AI",    "quarter":"Q4 2024","filed":"2025-02-14","change":"전량 청산",                          "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"SERV", "company":"Serve Robotics",   "quarter":"Q2 2024","filed":"2024-08-14","change":"보통주 13F · 3.73M주",              "change_eng":"13F common · 3.73M shares",                "change_type":"new",      "value_m":None},
    {"ticker":"SERV", "company":"Serve Robotics",   "quarter":"Q4 2024","filed":"2025-02-14","change":"전량 청산",                          "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"APLD", "company":"Applied Digital",  "quarter":"Q3 2024","filed":"2024-11-14","change":"보통주 13F · 7.72M주 (3.6%)",        "change_eng":"13F common · 7.72M shares (3.6%)",         "change_type":"new",      "value_m":None},
    {"ticker":"APLD", "company":"Applied Digital",  "quarter":"Q4 2025","filed":"2026-02-17","change":"전량 청산",                          "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
    {"ticker":"NNOX", "company":"Nano-X Imaging",   "quarter":"Q4 2023","filed":"2024-02-14","change":"보통주 13F · 59.6K주 (0.16%)",       "change_eng":"13F common · 59.6K shares (0.16%)",        "change_type":"new",      "value_m":None},
    {"ticker":"NNOX", "company":"Nano-X Imaging",   "quarter":"Q4 2024","filed":"2025-02-14","change":"전량 청산",                          "change_eng":"Full exit",                                "change_type":"exit",     "value_m":None},
]

BADGE_MAP = {
    "core":    '<span class="badge-core">CORE</span>',
    "new":     '<span class="badge-new">NEW</span>',
    "seed":    '<span class="badge-seed">SEED</span>',
    "watch":   '<span class="badge-watch">WATCH</span>',
    "partner": '<span class="badge-partner">PARTNER</span>',
    "exited":  '<span class="badge-exited">EXITED</span>',
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

# ── 섹터 → 상위 카테고리 통합 (파이 그래프용; 세부 섹터는 카드 호버에 그대로 유지) ──
SECTOR_GROUP = {
    "클라우드 GPU": "AI 인프라·클라우드", "AI 데이터센터": "AI 인프라·클라우드",
    "광학 소재/제조": "광학·광연결", "광학 부품": "광학·광연결",
    "광학 트랜시버": "광학·광연결", "반도체/광연결": "광학·광연결",
    "반도체/파운드리": "반도체·설계", "EDA/칩 설계": "반도체·설계", "반도체 IP": "반도체·설계",
    "통신 인프라": "통신", "AI 소프트웨어": "AI 소프트웨어",
    "산업 로봇": "로봇·피지컬AI", "자율주행": "로봇·피지컬AI", "자율주행 로봇": "로봇·피지컬AI",
    "AI 신약개발": "헬스·바이오 AI", "AI 의료영상": "헬스·바이오 AI", "AI/음성인식": "기타 AI",
}
CAT_COLORS = {
    "AI 인프라·클라우드": "#3b82f6", "광학·광연결": "#f59e0b", "반도체·설계": "#8b5cf6",
    "통신": "#06b6d4", "AI 소프트웨어": "#ec4899", "로봇·피지컬AI": "#22c55e",
    "헬스·바이오 AI": "#14b8a6", "기타 AI": "#a855f7",
}
CAT_NAMES = {
    "AI 인프라·클라우드": {"KOR": "AI 인프라·클라우드", "ENG": "AI Infra·Cloud"},
    "광학·광연결":       {"KOR": "광학·광연결",        "ENG": "Optics·Interconnect"},
    "반도체·설계":       {"KOR": "반도체·설계",        "ENG": "Semiconductor·Design"},
    "통신":             {"KOR": "통신",              "ENG": "Telecom"},
    "AI 소프트웨어":     {"KOR": "AI 소프트웨어",      "ENG": "AI Software"},
    "로봇·피지컬AI":     {"KOR": "로봇·피지컬AI",      "ENG": "Robotics·Physical AI"},
    "헬스·바이오 AI":    {"KOR": "헬스·바이오 AI",     "ENG": "Health·Bio AI"},
    "기타 AI":          {"KOR": "기타 AI",           "ENG": "Other AI"},
}
def cat_name(g):
    lang = st.session_state.get("lang", "KOR")
    return CAT_NAMES.get(g, {}).get(lang, g)

def get_change_style():
    # (좌측 컬러바 class, 배지 배경, 배지 글자) — 색은 타임라인 color_map과 일치
    return {
        "new":      ("filing-new",      "rgba(34,197,94,.16)",   "#4ade80", t("change_new")),
        "increase": ("filing-increase", "rgba(74,144,217,.18)",  "#7ab8f5", t("change_increase")),
        "decrease": ("filing-decrease", "rgba(224,86,86,.18)",   "#f08a8a", t("change_decrease")),
        "exit":     ("filing-exit",     "rgba(139,148,158,.18)", "#b0b8c2", t("change_exit")),
        "hold":     ("filing-hold",     "rgba(99,102,241,.18)",  "#a5a8f5", t("change_hold")),
    }

# ── fetch ────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_usdjpy():
    try:
        t = yf.Ticker("USDJPY=X")
        info = t.info
        rate = info.get("regularMarketPrice") or info.get("currentPrice")
        return rate if rate else 150.0
    except Exception:
        return 150.0

def _fetch_one(ticker):
    # Yahoo rate-limit(특히 클라우드 IP) 대응 — 실패 시 백오프 후 재시도
    last_err = "unknown"
    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            info = t.info
            hist = t.history(period="1y")
            price = (info.get("currentPrice") or info.get("regularMarketPrice")
                     or (hist["Close"].iloc[-1] if not hist.empty else None))
            if price is None and (hist is None or hist.empty):
                raise ValueError("empty response (rate-limit?)")
            prev  = info.get("regularMarketPreviousClose") or (
                hist["Close"].iloc[-2] if len(hist) > 1 else price)
            change_pct = ((price - prev) / prev * 100) if price and prev else None
            ytd_h = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
            ytd_pct = ((price - ytd_h.iloc[0]) / ytd_h.iloc[0] * 100
                       if not ytd_h.empty and price else None)
            return {
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
            last_err = str(e)
            if attempt < 2:
                time.sleep(1.2 * (attempt + 1))  # 1.2s, 2.4s 백오프
    return {"error": last_err}

@st.cache_data(ttl=300)
def fetch_stock_data(tickers):
    # 종목별 yfinance 호출을 병렬화 — 콜드 로드 20~40s → ~6s
    # max_workers는 Yahoo rate-limit(클라우드 IP burst 차단) 완화를 위해 3으로 제한
    tickers = list(tickers)
    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(_fetch_one, tickers))
    return dict(zip(tickers, results))

def _revive_hist(closes):
    # JSON 의 [["YYYY-MM-DD", close], ...] → 기존 코드가 기대하는 DataFrame 으로 복원
    # (hist.index / hist["Close"] / hist.empty 그대로 동작)
    if not closes:
        return pd.DataFrame()
    idx = pd.to_datetime([d for d, _ in closes])
    return pd.DataFrame({"Close": [c for _, c in closes]}, index=idx)

@st.cache_data(ttl=300)
def load_market_data():
    # data/market_data.json 스냅샷을 읽음 (GitHub Actions 가 매일 갱신 — 전일 종가 기준).
    # Streamlit Cloud 공유 IP 의 Yahoo rate-limit("Too Many Requests") 회피:
    # 앱은 Yahoo 를 직접 호출하지 않고 이 파일만 읽음.
    # 파일이 없거나 깨졌으면 None 반환 → 호출부에서 live fetch 로 fallback.
    import json, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "market_data.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return None
    def _revive_dict(d):
        out = {}
        for tk, q in d.items():
            if "error" in q:
                out[tk] = q
                continue
            q = dict(q)
            q["hist"] = _revive_hist(q.get("hist") or [])
            out[tk] = q
        return out
    return {
        "quotes": _revive_dict(raw.get("quotes", {})),
        "benchmarks": _revive_dict(raw.get("benchmarks", {})),
        "usdjpy": raw.get("usdjpy", 150.0),
        "generated_at": raw.get("generated_at", ""),
    }

@st.cache_data(ttl=600)
def fetch_news(ticker):
    try:
        return yf.Ticker(ticker).news or []
    except Exception:
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
    except Exception: return ""

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
.tag-guide-desc {{ font-size: 0.75rem; color: #9aa3b0 !important; line-height: 1.5; }}
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
    _md_meta = load_market_data()
    _asof_date = f" ({_md_meta['generated_at'][:10]})" if _md_meta and _md_meta.get("generated_at") else ""
    # 소스(고정)와 기준일(자동 갱신)을 2줄로 분리 — 줄바꿈은 마크다운 hard break(공백 2칸)
    _asof_line = f"  \n{t('sb_asof')}{_asof_date}"
    st.markdown(
        f"{t('sb_data_sources')}\n"
        f"- SEC EDGAR 13F\n"
        f"- NVIDIA IR\n"
        f"- {t('sb_media')}\n"
        f"  Bloomberg · Reuters · CNBC ·\n"
        f"  FT · WSJ · Economist {'외' if st.session_state.lang=='KOR' else 'etc.'}\n\n"
        f"---\n{t('sb_disclaimer')}\n\n{t('sb_delay')}{_asof_line}"
    )
    if st.button(t("sb_refresh"), use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # CSV 내보내기 placeholder — 데이터 로드 후 채움 (공유하기 섹션 위)
    _csv_slot = st.container()

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
                # 1) 로컬 파일 저장 (best-effort — 어드민 뷰 호환용, Cloud 재부팅 시 휘발)
                try:
                    path = "feedback.json"
                    data = []
                    if os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    data.append(entry)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                # 2) Telegram 전송 (durable — 유실 방지). 토큰 미설정 시 조용히 스킵.
                try:
                    import requests, html
                    _tg = st.secrets.get("telegram", {})
                    _tok, _chat = _tg.get("bot_token"), _tg.get("chat_id")
                    if _tok and _chat:
                        _stars = "⭐" * entry["rating"]
                        _msg = (
                            "📮 <b>트래커 피드백</b>\n\n"
                            f"<b>유형</b>: {html.escape(entry['category'])}\n"
                            f"<b>만족도</b>: {_stars}\n"
                            f"<b>작성자</b>: {html.escape(entry['name'])}\n"
                            f"<b>시각</b>: {entry['time']}\n\n"
                            f"{html.escape(entry['text'])}"
                        )
                        requests.post(
                            f"https://api.telegram.org/bot{_tok}/sendMessage",
                            data={"chat_id": _chat, "text": _msg, "parse_mode": "HTML"},
                            timeout=8,
                        )
                except Exception:
                    pass
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
    # 1순위: 일일 스냅샷(JSON) — Yahoo rate-limit 회피. 없으면 live fetch 로 fallback.
    _snapshot = load_market_data()
    if _snapshot and _snapshot.get("quotes"):
        stock_data = {tk: _snapshot["quotes"].get(tk, {"error": "no data"}) for tk in tickers}
        usdjpy = _snapshot.get("usdjpy", 150.0)
        benchmarks = _snapshot.get("benchmarks", {})
    else:
        stock_data = fetch_stock_data(tickers)
        usdjpy = fetch_usdjpy()
        benchmarks = {}

# ── CSV 내보내기 (사이드바 placeholder 채우기 — 공유하기 섹션 위) ──────────────
_csv_rows = []
for c in all_display:
    sd = stock_data.get(c["ticker"], {})
    _csv_rows.append({
        "name": c["name"], "ticker": c["ticker"],
        "sector": sector_name(c["sector"]), "badge": c["badge"],
        "price": sd.get("price"), "currency": sd.get("currency", "USD"),
        "daily_pct": sd.get("change_pct"), "ytd_pct": sd.get("ytd_pct"),
        "market_cap": sd.get("market_cap"), "pe_ratio": sd.get("pe_ratio"),
        "invest_amt_m": c.get("invest_amt_m"), "invest_date": c.get("invest_date", ""),
    })
if _csv_rows:
    _csv = pd.DataFrame(_csv_rows).to_csv(index=False).encode("utf-8-sig")
    _csv_asof = (_snapshot.get("generated_at", "")[:10] if _snapshot else "") or date.today().isoformat()
    with _csv_slot:
        st.download_button(t("csv_export"), _csv,
                           file_name=f"nvidia_portfolio_{_csv_asof}.csv",
                           mime="text/csv", use_container_width=True)
        st.markdown("---")

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
  margin: 4px 0 18px;
}
.nv-logo-wrap {
  display: flex;
  align-items: center;
  animation: nvlogo-spin 3.2s ease-in-out infinite;
  transform-style: preserve-3d;
}
.nv-header {
  max-width: 100%;
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
  max-width: 100%;
}
/* 데스크탑 고정 크기. 모바일은 아래 @media에서 vw 비례로 키움(한 줄 유지하며 화면 채움) */
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
/* 인트로 FOUC 방지 + 타이핑 캐럿: scramble 시작(nv-head) 전엔 타이틀을 레이아웃에서
   빼서(display:none) ① 완성 텍스트 번뜩임(FOUC) 차단 ② 폭 0이라 커서 _ 가 ◆ 바로
   옆에 옴(◆_). nv-head는 run() 시작·4초 failsafe에서 부여 → 타이핑 시작/재런 시 노출.
   재런(스크램블 가드로 run 미실행)에도 nv-head 영속이라 정적 타이틀 'NVIDIA Portfolio
   Tracker_' 정상 표시. */
body:not(.nv-head) #nv-title { display: none; }
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
      <span class="nv-title" id="nv-title">NVIDIA Portfolio Tracker</span><span class="nv-cursor">_</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 인트로 콘텐츠 게이트(A안) ─────────────────────────────────────────────────
#   헤더가 먼저 등장(scramble) → 헤더 아래 콘텐츠 전체를 opacity:0 + 살짝 아래(8px)로
#   숨겨 두었다가 scramble 정착 직후 fade-in(+떠오름)으로 드러냄 → Streamlit 초기
#   reflow(출렁임)를 페이드로 가림. transform/opacity만 써서 GPU 컴포지트(추가 reflow 0).
#   • 롤백: 아래 INTRO_GATE = False 한 줄이면 즉시 무력화(기존 동작 복귀).
#   • CSS는 헤더 직후 정적 <style>로 주입 → 콘텐츠보다 먼저 적용돼 "보였다 숨는" 플래시 차단.
#   • 드러내기/안전판은 아래 scramble 스크립트의 revealContent()(nv-ready 클래스 토글)가 담당.
#   • 셀렉터는 selenium 실측: 헤더(stElementContainer:has(.nv-header)) 이후 형제 div 30개
#     = 콘텐츠 전체와 정확히 일치. :has() 미지원 브라우저는 규칙이 무시돼 콘텐츠 그대로 노출.
INTRO_GATE = True
if INTRO_GATE:
    # FOUC(잔상) 방지 핵심:
    #  ① 첫 페인트부터 visibility:hidden 으로 메인 전체 숨김 — :has() 비의존, 콘텐츠보다 먼저
    #     존재하는 stMainBlockContainer에 걸어 "삽입 프레임 지각" 없이 즉시 적용(reflow 0).
    #     (이전 opacity+:has 방식은 새 요소가 한 프레임 opacity:1로 그려진 뒤 규칙이 먹어,
    #      숨김에 걸린 transition이 그 1→0을 0.5s 페이드아웃 잔상으로 노출시켰음 — selenium 곡선 확인)
    #  ② 헤더(로고+scramble)만 visibility:visible 로 예외 노출.
    #  ③ transition 은 reveal(nv-ready) 방향에만 → 숨김은 즉시(스냅), 등장만 부드럽게 fade-in.
    st.markdown("""
<style id="nv-intro-gate">
/* ① 부팅 전: 메인 전체 숨김 (즉시·reflow 없음) */
body:not(.nv-ready) [data-testid="stMainBlockContainer"] {
  visibility: hidden;
}
/* ② 헤더만 예외 노출 (로고 + scramble 타이틀) */
body:not(.nv-ready) [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(.nv-header) {
  visibility: visible;
}
/* ③ 콘텐츠(헤더 이후 형제) 숨김 상태값 — transition 없음(스냅), reveal 대비 opacity/translateY */
body:not(.nv-ready) [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.nv-header) ~ div {
  opacity: 0;
  transform: translateY(8px);
}
/* ④ reveal: 메인 visible 복귀 + 콘텐츠만 부드럽게 fade-in (transition은 여기서만).
   transform은 translateY(0)이 아니라 none 으로 끝냄 — translateY(0)도 transform이라
   stacking context/containing block을 영구 생성해 카드 툴팁(z-index)이 뒤 형제 블록에
   가려지는 버그가 났음. none 으로 끝내면 8px→0 lift는 애니메이트되고 잔여 컨텍스트는 없음. */
body.nv-ready [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.nv-header) ~ div {
  transition: opacity 0.5s ease, transform 0.5s ease;
  opacity: 1;
  transform: none;
}
@media (prefers-reduced-motion: reduce) {
  body:not(.nv-ready) [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.nv-header) ~ div,
  body.nv-ready [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.nv-header) ~ div {
    transform: none;
  }
}
</style>
""", unsafe_allow_html=True)

# 헤더 타이틀 인트로 효과 — 타이핑+순차 언스크램블 (왼쪽→오른쪽, 약 1.3초).
# 커서 _ 가 타이핑 캐럿처럼 프런티어를 따라가며 한 글자씩 찍히고, 각 글자는 찍힌 직후 잠깐
# 코드기호로 스크램블됐다가 정착. 부팅엔 ◆_ (커서만 깜빡) → 타이핑 → 완성 'Tracker_'.
# st.markdown은 <script> 미실행 + components.html(srcdoc)은 null-origin이라
# window.parent(앱 iframe, same-origin)의 #nv-title에 직접 주입 (GA4와 동일 패턴).
# __nvScrambled 가드 → Streamlit 재렌더 시 재실행 안 함(세션 1회만).
# 로딩 출렁임에 안 섞이도록: 로딩 중엔 타이틀 숨김 → 페이지 완료+폰트+텀 후 등장.
# 인트로 게이트(위 nv-intro-gate <style>) 연동: scramble 정착 직후 revealContent()로
# body에 nv-ready 부여 → 콘텐츠 fade-in. scramble 실패 대비 4초 failsafe 동시 가동.
components.html("""
<script>
(function() {
  var p = window.parent;

  // 인트로 콘텐츠 게이트 드러내기: body.nv-ready 부여 → CSS가 콘텐츠 fade-in (세션 1회)
  function revealContent() {
    if (!p || p.__nvRevealed) return;
    p.__nvRevealed = true;
    p.document.body.classList.add('nv-head');   // 타이틀 노출(스크램블 실패해도 텍스트는 보이게)
    p.document.body.classList.add('nv-ready');
  }
  if (p) p.setTimeout(revealContent, 4000);  // failsafe: scramble 실패해도 4초 뒤 무조건 노출

  if (!p || p.__nvScrambled) return;
  var TEXT = 'NVIDIA Portfolio Tracker';
  var GLYPHS = '<>/{}[]()=+*#%&|;:!?';  // 코드 기호 글리치 (Press Start 2P 지원 글리프)
  var INTRO_DELAY = 800;  // 페이지 로딩 완료 후 텀 (사람이 화면 인지할 시간)
  function rand() { return GLYPHS[Math.floor(Math.random() * GLYPHS.length)]; }
  var tries = 0;
  function waitEl() {
    var el = p.document.getElementById('nv-title');
    if (!el) { if (tries++ < 40) p.setTimeout(waitEl, 50); return; }  // DOM 미생성 시 재시도
    if (p.__nvScrambled) return;
    p.__nvScrambled = true;
    el.style.opacity = '0';  // 로딩 중 숨김(폭/레이아웃은 유지) → 출렁임에 안 끼어듦
    whenReady(function(){ p.setTimeout(function(){ run(el); }, INTRO_DELAY); });
  }
  // 페이지 load 완료 + 폰트 로드 완료를 모두 기다림
  function whenReady(cb) {
    var d = p.document;
    var fontsReady = (d.fonts && d.fonts.ready) ? d.fonts.ready : Promise.resolve();
    function afterLoad() { fontsReady.then(cb); }
    if (d.readyState === 'complete') afterLoad();
    else p.addEventListener('load', afterLoad, { once: true });
  }
  function run(el) {
    p.document.body.classList.add('nv-head');  // 타이틀 노출 게이트 해제(재런에도 영속) → 타이핑 시작
    el.style.opacity = '1';  // 깨끗한 화면에서 등장
    // 타이핑 중엔 glow(text-shadow blur) 끔 → 모바일 GPU의 매 프레임 재페인트 부담 제거.
    // 정착 후 transition으로 부드럽게 켬.
    el.style.transition = 'text-shadow 0.35s ease';
    el.style.textShadow = 'none';
    var chars = TEXT.split('');
    el.textContent = '';
    // 타이핑+순차 언스크램블: 안 찍힌 글자는 폭 0 → 커서(.nv-cursor)가 타이핑 프런티어를 따라옴.
    // 찍힌 글자는 width:1em 고정(폰트크기 상대) → 글자 교체 시 폭 변동 reflow 차단(모바일 축소도 추종).
    var spans = chars.map(function() {
      var s = p.document.createElement('span');
      s.style.display = 'inline-block';
      s.style.width = '0';
      s.style.overflow = 'hidden';
      s.style.textAlign = 'center';
      el.appendChild(s);
      return s;
    });
    var isMobile = (p.innerWidth <= 640);
    var TYPE_MS = 45;               // 글자당 타이핑 간격 (B안 — 총 ~1.3초)
    var SCRAMBLE_MS = TYPE_MS * 3;  // 찍힌 직후 스크램블 지속(~135ms, 동시에 ~3글자가 풀림)
    var settled = new Array(chars.length).fill(false);  // 정착 글자 재기록 방지
    var start = p.performance.now();
    // 랜덤 교체 throttle → 모바일은 늘려 교체(=페인트) 횟수 ↓ (동시 스크램블 글자 적어 부담은 작음)
    var lastSwap = 0, SWAP_MS = isMobile ? 90 : 40;
    function tick(now) {
      var t = now - start, done = true;
      var swap = (now - lastSwap) >= SWAP_MS;
      for (var i = 0; i < chars.length; i++) {
        if (settled[i]) continue;
        var rt = i * TYPE_MS;                       // 이 글자가 '찍히는' 시각
        if (t < rt) { done = false; continue; }     // 아직 안 찍힘 → 폭 0 유지(커서 왼쪽)
        spans[i].style.width = '1em';               // 찍힘 → 폭 확보(커서 오른쪽으로 이동)
        if (chars[i] === ' ') { spans[i].textContent = '\\u00A0'; settled[i] = true; continue; }
        if (t < rt + SCRAMBLE_MS) { if (swap) spans[i].textContent = rand(); done = false; }  // 찍힌 직후 스크램블
        else { spans[i].textContent = chars[i]; settled[i] = true; }  // 정착
      }
      if (swap) lastSwap = now;
      if (!done) { p.requestAnimationFrame(tick); }
      else {
        el.style.textShadow = '';  // 정착 완료 → CSS glow 복원(transition으로 페이드인)
        p.setTimeout(revealContent, 250);  // 헤더 완성 직후 콘텐츠 fade-in(+떠오름)
      }
    }
    p.requestAnimationFrame(tick);
  }
  waitEl();
})();
</script>
""", height=0)

# ── 요약 지표 ─────────────────────────────────────────────────────────────────
# 파트너십(지분 없음)은 수익률 집계에서 제외 — NVIDIA 실제 보유분 성과만 반영
ytd_vals = [stock_data[c["ticker"]].get("ytd_pct")
            for c in all_display
            if c["badge"] != "partner"
            and stock_data.get(c["ticker"],{}).get("ytd_pct") is not None]
avg_ytd = sum(ytd_vals)/len(ytd_vals) if ytd_vals else None
total_invest = sum(c["invest_amt_m"] for c in all_display if c.get("invest_amt_m"))

avg_ytd_str   = f"{avg_ytd:+.1f}%" if avg_ytd else "—"
invest_str    = f"${total_invest/1000:.1f}B+"

# 52주 신고가 근접 — 보유분 모멘텀 (파트너·청산 제외, gap = 고가 대비 하락폭 %)
_near_high = []
for c in all_display:
    if c["badge"] in ("partner", "exited"):
        continue
    _sd = stock_data.get(c["ticker"], {})
    _price, _hi = _sd.get("price"), _sd.get("week52_high")
    if _price and _hi and _hi > 0:
        _near_high.append((c, (_hi - _price) / _hi * 100))
_near_high.sort(key=lambda x: x[1])  # 고가에 가까운 순
_near5_cnt    = sum(1 for _, g in _near_high if g <= 5)
near_high_str = f"{_near5_cnt}/{len(_near_high)}" + ("개" if st.session_state.lang == "KOR" else "")

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
  max-width: calc(100vw - 24px);  /* 모바일 viewport 초과 방지 안전판 */
  box-sizing: border-box;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
}
.metric-box.active .metric-tooltip { display: block; }  /* 모바일·공통: 탭 토글 */
@media (hover: hover) {  /* 데스크톱(마우스)만 hover — 모바일 iOS sticky hover 방지 */
  .metric-box:hover .metric-tooltip { display: block; }
}
.tooltip-title {
  color: #8b949e;
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
.tooltip-name   { color: #9aa3b0; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

# 모바일: metric 카드 탭 토글 — 같은 카드 다시 탭하면 툴팁 닫힘. 다른 카드/바깥 탭하면 닫힘.
# 이벤트 위임(parent document)이라 Streamlit 재렌더에도 한 번만 바인딩.
components.html("""
<script>
(function(){
  var p = window.parent;
  if (p.__metricTapBound) return;
  p.__metricTapBound = true;
  p.document.addEventListener('click', function(e){
    var box = e.target.closest('.metric-box');
    p.document.querySelectorAll('.metric-box.active').forEach(function(b){
      if (b !== box) b.classList.remove('active');
    });
    if (box) box.classList.toggle('active');
  });
})();
</script>
""", height=0)

for col, label, value, color, extra_html in [
    (m1, t("metric_holdings"),
     (f"{len(THIRTEEN_F)}개 종목" if st.session_state.lang=="KOR" else f"{len(THIRTEEN_F)} stocks"), "#76b900",
     '<div class="metric-tooltip">'
     f'<div class="tooltip-title">{t("tooltip_13f")}</div>'
     + "".join(
         f'<div class="tooltip-row"><span class="tooltip-ticker">{h["ticker"]}</span>'
         f'<span class="tooltip-name">'
         + ('<span style="color:#c87f00;font-size:0.6rem;font-weight:700;margin-right:5px">NEW</span>' if h["is_new"] else '')
         + f'{h["name"]}</span></div>'
         for h in THIRTEEN_F
       )
     + '</div>'),
    (m2, t("metric_invested"), invest_str,   "#c87f00",
     '<div class="metric-tooltip" style="border-top-color:#c87f00;min-width:220px;left:auto;right:0">'
     f'<div class="tooltip-title" style="color:#c87f00">{t("tooltip_invest_rank")}</div>'
     + "".join(
         f'<div class="tooltip-row">'
         f'<span class="tooltip-ticker">{c["ticker"]}</span>'
         f'<span class="tooltip-name">'
         f'{"$%.1fB" % (c["invest_amt_m"]/1000) if c["invest_amt_m"]>=1000 else "$%.0fM" % c["invest_amt_m"]}'
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
              and c["badge"] not in ("exited", "partner")],
             key=lambda x: x[1], reverse=True
         )
     )
     + '</div>'),
    (m4, t("metric_near_high"), near_high_str, "#76b900",
     '<div class="metric-tooltip" style="min-width:230px;left:auto;right:0">'
     f'<div class="tooltip-title">{t("tooltip_near_high")}</div>'
     + "".join(
         f'<div class="tooltip-row">'
         f'<span class="tooltip-ticker">{c["ticker"]}</span>'
         f'<span class="tooltip-name" style="color:{"#76b900" if gap<=5 else "#9aa3b0"}">'
         f'{"신고가" if gap<0.05 else f"-{gap:.1f}%"}</span></div>'
         for c, gap in _near_high
       )
     + '</div>'),
]:
    col.markdown(
        f'<div class="metric-box" style="background:#0e0e0e;border:1px solid #2a2a2a;border-top:2px solid {color};'
        f'border-radius:4px;padding:18px 20px;margin-bottom:4px">'
        f'<div style="color:#8b949e;font-size:0.72rem;font-weight:500;letter-spacing:1.2px;'
        f'text-transform:uppercase;margin-bottom:8px">{label}</div>'
        f'<div style="color:{color};font-size:1.6rem;font-weight:600;letter-spacing:-0.5px;line-height:1">'
        f'{value}</div>'
        f'{extra_html}'
        f'</div>',
        unsafe_allow_html=True)

st.markdown("---")

# ── 🚨 신규 투자 알림 배너 — 최근 5건 (첫 화면 위계: 헤더→요약 카드→알림 순으로 배치) ──
all_investments = NEW_2026 + CURRENT_HOLDINGS + PARTNERSHIPS
recent_5 = sorted(
    [c for c in all_investments if c.get("alert_date")],
    key=lambda x: x.get("alert_date",""), reverse=True
)[:5]
_cur_lang = st.session_state.lang
if recent_5:
    latest_year = recent_5[0].get("alert_date","")[:4]
    _alert_items = []
    for c in recent_5:
        _raw = (c.get("note_eng") or c["note"]) if _cur_lang == "ENG" else c["note"]
        # note 첫 조각에서 날짜 든 괄호 통째 제거 (비날짜 괄호 '(+95% 증가)'는 유지)
        _desc = re.sub(r'\s*\([^)]*20\d{2}[.\-]\d[^)]*\)', '', _raw.split("|")[0].strip()).strip()
        _alert_items.append(
            f'<div class="alert-item">'
            f'<span class="alert-date">{c.get("alert_date","")}</span>'
            f'<span><b class="alert-co">{c["name"]} ({c["ticker"]})</b>&nbsp; '
            f'<span class="alert-desc">{_desc}</span></span>'
            f'</div>')
    items_html = "".join(_alert_items)
    st.markdown(
        f'<div class="alert-banner">'
        f'<div class="alert-title">{"Recent Investments" if _cur_lang=="ENG" else "최신 투자 알림"}&nbsp;·&nbsp;{latest_year}</div>'
        f'{items_html}'
        f'</div>',
        unsafe_allow_html=True)

st.markdown("---")  # 알림 배너 ↔ 탭 구분

# ── 탭 ───────────────────────────────────────────────────────────────────────
# st.tabs는 모든 탭을 한 번에 렌더(차트 5개 동시) → 모바일 로딩 출렁임.
# segmented_control + 조건부 렌더(lazy)로 선택 탭만 그림(초기 차트 5→0개).
TAB_LABELS = ["Portfolio", "Performance", "Sectors", "News", "13F History"]
active_tab = st.segmented_control(
    "탭", TAB_LABELS, default="Portfolio", label_visibility="collapsed", key="main_tabs"
) or "Portfolio"  # None(선택 해제) 가드 → 항상 한 탭 활성

PLOTLY_CFG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}  # 툴바·줌 비활성(터치 시 의도치 않은 zoom 방지)
# 모바일/데스크톱 분기(서버측 user-agent → 깜빡임 없음). 범례 위치 등에 사용.
try:
    _ua = st.context.headers.get("User-Agent", "")
except Exception:
    _ua = ""
is_mobile = any(k in _ua for k in ["Mobile", "Android", "iPhone", "iPad"])

# ══ Tab 1 ════════════════════════════════════════════════════════════════════
if active_tab == "Portfolio":
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
        elif group_title == t("group_exited"):  accent = "#3a3a3a"
        else:                                   accent = "#4a90d9"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;margin:32px 0 18px">'
            f'<div style="width:3px;height:22px;background:{accent};border-radius:2px;flex-shrink:0"></div>'
            f'<span style="color:#d0d0d0;font-size:0.95rem;font-weight:600;letter-spacing:0.4px">{group_title}</span>'
            f'<div style="flex:1;height:1px;background:#1a1a1a"></div>'
            f'</div>',
            unsafe_allow_html=True)
        sorted_items = sorted(group_items, key=sort_key, reverse=reverse)

        lang       = st.session_state.lang
        detail_lbl = "Details"

        # 테이블 헤더 (데스크탑 전용 — 모바일에서는 CSS로 숨김)
        st.markdown(
            f'<div class="ptable-header">'
            f'<span>{t("col_company")}</span><span>{t("col_price")}</span>'
            f'<span>{t("col_daily")}</span><span>YTD</span>'
            f'<span>{t("col_cap")}</span><span>P/E</span><span></span>'
            f'</div>',
            unsafe_allow_html=True)

        for c in sorted_items:
            ticker   = c["ticker"]
            sd       = stock_data.get(ticker, {})
            if "error" in sd:
                _err = str(sd.get("error", ""))[:70]
                st.warning(f"{ticker}: 데이터 로드 실패  ({_err})")
                continue

            price    = sd.get("price")
            currency = sd.get("currency", "USD")
            amt      = (f"${c['invest_amt_m']/1000:.1f}B"
                        if (c.get("invest_amt_m") or 0) >= 1000
                        else f"${c['invest_amt_m']:.0f}M"
                        if c.get("invest_amt_m") else "")

            # 52W 바 (데스크탑용 전체 / 모바일용 축약)
            w52h = sd.get("week52_high"); w52l = sd.get("week52_low")
            if w52h and w52l and price:
                pp = max(0, min(100, (price - w52l) / (w52h - w52l) * 100))
                bar52_desk = (
                    f'<div style="font-size:0.68rem;color:#9aa3b0">'
                    f'{fmt_price(w52l,currency)}'
                    f'<span style="color:#2a2a2a"> – </span>'
                    f'{fmt_price(w52h,currency)}<br>'
                    f'<div style="background:#1a1a1a;border-radius:2px;height:3px;margin-top:3px">'
                    f'<div style="background:#76b900;width:{pp:.0f}%;height:3px;border-radius:2px"></div>'
                    f'</div></div>'
                )
                bar52_mob = (f'<span style="color:#76b900;font-size:0.82rem;font-weight:500">'
                             f'{pp:.0f}%</span>'
                             )
            else:
                bar52_desk = bar52_mob = '<span style="color:#2a2a2a">—</span>'

            _thesis  = ((c.get("nvidia_thesis_eng") or c["nvidia_thesis"])
                        if lang == "ENG" else c["nvidia_thesis"])
            # 한국어 + 재작성된 종목이면 3섹션 구조, 아니면 기존 한 덩어리 fallback
            _tk3 = (THESIS_EN.get(ticker) if lang == "ENG" else THESIS_KO.get(ticker))
            if _tk3:
                _L = (("In a nutshell", "Why NVIDIA invested", "Deal structure") if lang == "ENG"
                      else ("한 줄 요약", "왜 NVIDIA가 투자했나", "투자 구조"))
                _thesis_html = (
                    f'<div class="ptd-label">{_L[0]}</div>'
                    f'<div class="ptd-summary">{_tk3[0]}</div>'
                    f'<div class="ptd-label">{_L[1]}</div>'
                    f'<div class="ptd-thesis">{_tk3[1]}</div>'
                    f'<div class="ptd-label">{_L[2]}</div>'
                    f'<div class="ptd-thesis">{_tk3[2]}</div>'
                )
            else:
                _thesis_html = ('<div class="ptd-label">WHY NVIDIA</div>'
                                f'<div class="ptd-thesis">{_thesis}</div>')
            price_h  = f'<span style="color:#c0c0c0;font-weight:500">{fmt_price(price,currency)}</span>'
            daily_h  = fmt_pct(sd.get("change_pct"))
            ytd_h    = fmt_pct(sd.get("ytd_pct"))
            cap_h    = f'<span style="color:#a0a0a0">{fmt_cap(sd.get("market_cap"),currency,usdjpy)}</span>'
            pe_h     = f'<span style="color:#a0a0a0">{fmt_ratio(sd.get("pe_ratio"))}</span>'
            amt_h    = (f'<span style="color:#c87f00;font-size:0.75rem;font-weight:600">{amt}</span>'
                        if amt else "")
            amt_big  = (f'<div style="color:#c87f00;font-size:1rem;font-weight:600;margin-bottom:10px">{amt}</div>'
                        if amt else "")

            _src = re.sub(r'\s*\(\d{4}\.\d{2}(?:\.\d{2})?\)', '', c.get("source", "—")).strip()
            _date = c.get("invest_date", "—")
            _badge = BADGE_MAP[c["badge"]]
            _sector = sector_name(c["sector"])
            _col_price = t("col_price"); _col_daily = t("col_daily"); _col_cap = t("col_cap")
            row_html = (
                f'<div class="ptable-row" style="--accent:{accent}">'
                f'<div class="pt-company">'
                f'<div><span style="color:#e8e8e8;font-weight:500">{c["name"]}</span>'
                f'<span style="color:#9aa3b0;font-size:0.75rem;margin-left:6px">{ticker}</span></div>'
                f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:5px;margin-top:4px">'
                f'{_badge}<span style="color:#9aa3b0;font-size:0.7rem">{_sector}</span>{amt_h}</div>'
                f'<div class="pt-stats">'
                f'<div><span class="pt-stat-label">{_col_price}</span>{price_h}</div>'
                f'<div><span class="pt-stat-label">{_col_daily}</span>{daily_h}</div>'
                f'<div><span class="pt-stat-label">YTD</span>{ytd_h}</div>'
                f'</div>'
                f'<div class="pt-meta">'
                f'<div><span class="pt-stat-label">{_col_cap}</span>{cap_h}</div>'
                f'<div><span class="pt-stat-label">P/E</span>{pe_h}</div>'
                f'<div><span class="pt-stat-label">52W</span>{bar52_mob}</div>'
                f'</div></div>'
                f'<div class="pt-price">{price_h}</div>'
                f'<div class="pt-daily">{daily_h}</div>'
                f'<div class="pt-ytd">{ytd_h}</div>'
                f'<div class="pt-cap">{cap_h}</div>'
                f'<div class="pt-pe">{pe_h}</div>'
                f'<div class="pt-detail">'
                f'<details><summary>{detail_lbl}</summary></details>'
                f'<div class="pt-detail-body">'
                f'<div class="ptd-header"><span class="ptd-ticker">{ticker}</span><span class="ptd-sector">{_sector}</span></div>'
                + (f'<div class="ptd-label">NVIDIA INVEST</div><div class="ptd-amount">{amt}</div>' if amt else '')
                + _thesis_html
                + f'<div class="ptd-footer"><span class="ptd-date">{_date}</span><span class="ptd-src">{_src}</span></div>'
                + f'</div></div>'
                f'</div>'
            )
            st.markdown(row_html, unsafe_allow_html=True)

# ══ Tab 2 ════════════════════════════════════════════════════════════════════
elif active_tab == "Performance":
    st.markdown(f"### {t('perf_title')}")
    if st.session_state.lang == "KOR":
        _hint = ("💡 주요 종목만 표시 중 — 범례에서 종목을 탭해 추가/제거, 더블탭하면 그 종목만 볼 수 있어요." if is_mobile
                 else "💡 범례에서 종목을 탭하면 켜고 끌 수 있고, 더블클릭하면 그 종목만 볼 수 있어요.")
    else:
        _hint = ("💡 Showing key holdings — tap a legend item to add/remove; double-tap to isolate one." if is_mobile
                 else "💡 Tap a legend item to show/hide it; double-click to view only that one.")
    st.markdown(
        f'<div style="color:#e5e7eb;font-size:0.85rem;margin:-6px 0 10px">{_hint}</div>',
        unsafe_allow_html=True)
    # 파트너십(지분 없음)은 수익률 차트에서 제외 — NVIDIA 실제 보유분만
    chart_items = [c for c in all_display
                   if c["badge"] != "partner"
                   and "error" not in stock_data.get(c["ticker"],{})]
    fig = go.Figure()
    _palette = px.colors.qualitative.Light24  # 종목별 고유색 → 라인 구분성 ↑(섹터색 중복 해소)
    # 모바일: 14개 스파게티 완화 — 기본은 YTD 상위 3종목만 표시, 나머지는 legendonly(범례 탭하면 추가)
    _top_tk = set()
    if is_mobile:
        _ranked = sorted(chart_items,
                         key=lambda c: stock_data.get(c["ticker"], {}).get("ytd_pct") or -9999,
                         reverse=True)
        _top_tk = {c["ticker"] for c in _ranked[:3]}
    _ci = 0
    for c in chart_items:
        hist = stock_data[c["ticker"]].get("hist")
        if hist is None or hist.empty: continue
        ytd_h = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
        if ytd_h.empty: continue
        pct = ((ytd_h / ytd_h.iloc[0] - 1) * 100).round(0)
        fig.add_trace(go.Scatter(
            x=pct.index, y=pct.values,
            name=c["ticker"],  # 범례는 티커만(컴팩트) — 풀네임은 hover로
            line=dict(color=_palette[_ci % len(_palette)], width=2),
            visible=(True if (not is_mobile or c["ticker"] in _top_tk) else "legendonly"),
            hovertemplate=f"<b>{c['name']}</b><br>%{{y:+.0f}}%<extra></extra>",
        ))
        _ci += 1
    # 벤치마크 비교선 (NVDA 본주 · SOXX 반도체 ETF) — 점선으로 구분
    _bench_style = {
        "NVDA": ("NVDA", "#76b900"),
        "SOXX": ("SOXX 반도체 ETF" if st.session_state.lang=="KOR" else "SOXX (Semis ETF)", "#888888"),
    }
    for _btk, (_blabel, _bcolor) in _bench_style.items():
        _bq = benchmarks.get(_btk)
        if not _bq or "error" in _bq:
            continue
        _bhist = _bq.get("hist")
        if _bhist is None or _bhist.empty:
            continue
        _bytd = _bhist[_bhist.index >= f"{date.today().year}-01-01"]["Close"]
        if _bytd.empty:
            continue
        _bpct = ((_bytd / _bytd.iloc[0] - 1) * 100).round(0)
        fig.add_trace(go.Scatter(
            x=_bpct.index, y=_bpct.values, name=_blabel,
            line=dict(color=_bcolor, width=2, dash="dot"),
            hovertemplate=f"<b>{_blabel}</b><br>%{{y:+.0f}}%<extra></extra>",
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="#6b7280", annotation_text="0%")
    # 범례: 데스크톱=우측 세로 / 모바일=하단 가로(티커라 자동 여러 열)
    _legend = (dict(bgcolor="rgba(31,41,55,0.5)", orientation="h", yanchor="top", y=-0.12, x=0, font=dict(size=10))
               if is_mobile else
               dict(bgcolor="rgba(31,41,55,0.3)", orientation="v", yanchor="top", y=1, xanchor="left", x=1.01, font=dict(size=11)))
    fig.update_layout(template="plotly_dark", paper_bgcolor="#111827", plot_bgcolor="#111827",
                      height=520, yaxis_title="YTD Return (%)" if st.session_state.lang=="ENG" else "YTD 수익률 (%)",
                      yaxis_ticksuffix="%", yaxis_hoverformat="+.0f",
                      legend=_legend, dragmode=False,
                      margin=dict(l=0, r=(16 if is_mobile else 12), t=20, b=0))
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CFG)

    ytd_data = [{"ticker":c["ticker"],"name":c["name"],"ytd":stock_data.get(c["ticker"],{}).get("ytd_pct")}
                for c in all_display
                if c["badge"] != "partner"
                and stock_data.get(c["ticker"],{}).get("ytd_pct") is not None]
    if ytd_data:
        df_ytd = pd.DataFrame(ytd_data).sort_values("ytd", ascending=True)
        fig2 = go.Figure(go.Bar(
            x=df_ytd["ytd"], y=df_ytd["ticker"], orientation="h",
            marker_color=["#22c55e" if v>=0 else "#ef4444" for v in df_ytd["ytd"]],
            text=[f"{v:+.0f}%" for v in df_ytd["ytd"]], textposition="outside", cliponaxis=False,
            textfont=dict(color="#ffffff"),
            hoverinfo="skip",  # 막대 끝 라벨로 값이 이미 보임 → 호버 제거(소수점 버그도 해소)
        ))
        fig2.update_layout(template="plotly_dark", paper_bgcolor="#111827", plot_bgcolor="#111827",
                            height=max(300,len(df_ytd)*38), xaxis_title="YTD (%)",
                            xaxis_hoverformat="+.0f", dragmode=False,
                            margin=dict(l=0,r=60,t=10,b=0))
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CFG)

# ══ Tab 3 ════════════════════════════════════════════════════════════════════
elif active_tab == "Sectors":
    current_only = NEW_2026 + CURRENT_HOLDINGS
    ca, cb = st.columns(2)
    with ca:
        sc_raw = {}; sc_cnt = {}  # 카테고리별 투자액 합 + 종목 수
        for c in current_only:
            if not c.get("invest_amt_m"): continue
            grp = SECTOR_GROUP.get(c["sector"], c["sector"])
            sc_raw[grp] = sc_raw.get(grp, 0) + c["invest_amt_m"]
            sc_cnt[grp] = sc_cnt.get(grp, 0) + 1
        grps = list(sc_raw.keys())
        sc_labels = [cat_name(g) for g in grps]
        fig3 = go.Figure(go.Pie(labels=sc_labels, values=[sc_raw[g] for g in grps],
            marker_colors=[CAT_COLORS.get(g,"#6b7280") for g in grps], hole=0.4,
            textposition="inside", textinfo="percent",
            customdata=[[sc_raw[g]/1000, sc_cnt[g]] for g in grps],
            hovertemplate="%{label}<br>$%{customdata[0]:.1f}B · %{customdata[1]}개 종목<extra></extra>"))
        fig3.update_layout(template="plotly_dark",paper_bgcolor="#111827",
            title=t("sector_count"),title_font_color="#f9fafb",height=420, dragmode=False,
            legend=dict(orientation="h",y=-0.05,x=0.5,xanchor="center",font=dict(size=10)),
            margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig3, use_container_width=True, config=PLOTLY_CFG)
    with cb:
        invest_data = [(c["name"], c["invest_amt_m"]) for c in current_only if c.get("invest_amt_m")]
        if invest_data:
            names, amts = zip(*invest_data)
            fig4 = go.Figure(go.Pie(labels=list(names), values=list(amts),
                marker_colors=px.colors.qualitative.Light24,  # 종목별 고유색(ⓑ) — 조각마다 구분
                hole=0.4, textposition="inside", textinfo="percent",
                customdata=[a/1000 for a in amts],
                hovertemplate="%{label}<br>$%{customdata:.1f}B<extra></extra>"))
            fig4.update_layout(template="plotly_dark",paper_bgcolor="#111827",
                title=t("sector_invest"),title_font_color="#f9fafb",height=420, dragmode=False,
                legend=dict(orientation="h",y=-0.05,x=0.5,xanchor="center",font=dict(size=10)),
                margin=dict(l=0,r=0,t=40,b=0))
            st.plotly_chart(fig4, use_container_width=True, config=PLOTLY_CFG)

# ══ Tab 4: 뉴스 ══════════════════════════════════════════════════════════════
elif active_tab == "News":
    st.markdown(f"### {t('news_title')}")
    st.caption(t("news_caption"))
    news_map = {c["ticker"]: f"{c['name']} ({c['ticker']})" for c in all_display
                if "error" not in stock_data.get(c["ticker"],{})}
    sel_t = st.selectbox(t("news_stock"), list(news_map.keys()), format_func=lambda x: news_map[x])
    sel_c = next((c for c in all_display if c["ticker"]==sel_t), None)
    if sel_c:
        sd = stock_data.get(sel_t,{})
        _chg = sd.get("change_pct"); _ytd = sd.get("ytd_pct")
        _chg_c = "#22c55e" if (_chg or 0) >= 0 else "#ef4444"
        _ytd_c = "#22c55e" if (_ytd or 0) >= 0 else "#ef4444"
        def _metric_card(label, value_html, top_color):
            return (f'<div style="background:#0e0e0e;border:1px solid #2a2a2a;border-top:2px solid {top_color};'
                    f'border-radius:4px;padding:16px 20px;height:100%">'
                    f'<div style="color:#8b949e;font-size:0.7rem;font-weight:600;letter-spacing:1.2px;'
                    f'text-transform:uppercase;margin-bottom:8px">{label}</div>'
                    f'<div style="font-size:1.7rem;font-weight:600;letter-spacing:-0.5px;line-height:1">{value_html}</div>'
                    f'</div>')
        n1,n2,n3 = st.columns(3)
        with n1:
            st.markdown(_metric_card(t("news_price"),
                f'<span style="color:#e8e8e8">{fmt_price(sd.get("price"), sd.get("currency","USD"))}</span>',
                "#76b900"), unsafe_allow_html=True)
        with n2:
            st.markdown(_metric_card(t("news_daily"), fmt_pct(_chg), _chg_c), unsafe_allow_html=True)
        with n3:
            st.markdown(_metric_card("YTD", fmt_pct(_ytd), _ytd_c), unsafe_allow_html=True)
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
elif active_tab == "13F History":
    st.markdown(f"### {t('filings_title')}")
    st.caption(t("filings_caption"))
    # 필터 강조 + (데스크톱) 좌측 필터 열 sticky + 카드 폭 캡
    st.markdown("""<style>
      /* 모바일 필터 expander 강조 */
      [data-testid="stExpander"] details {
        border: 1px solid rgba(118,185,0,0.28) !important;
        border-radius: 10px !important;
        background: rgba(255,255,255,0.025) !important;
      }
      [data-testid="stExpander"] [data-testid="stWidgetLabel"] p { color: #e5e7eb !important; font-weight: 500 !important; }
      [data-testid="stExpander"] button[data-testid="stBaseButton-secondary"] p { color: #e5e7eb !important; font-weight: 500 !important; }
      .f13-filter-title { color:#e5e7eb; font-weight:600; font-size:0.95rem; margin:0 0 8px; }
      [data-testid="stWidgetLabel"] p { color:#cbd5e1 !important; }
      @media (min-width: 769px) {
        /* 필터 열(=제목 칩 보유 열)만 sticky — 긴 카드 리스트 스크롤 시 따라옴. 다른 컬럼 비영향 */
        div[data-testid="stColumn"]:has(.f13-filter-title) {
          position: sticky; top: 0.75rem; align-self: flex-start;
          background: rgba(255,255,255,0.025);
          border: 1px solid rgba(118,185,0,0.22);
          border-radius: 10px; padding: 12px 14px;
        }
        /* 카드 폭 캡 — 회사↔금액 간격 축소(휑한 전폭 방지) */
        .filing-row { max-width: 860px; }
      }
    </style>""", unsafe_allow_html=True)

    all_cos = sorted({f["company"] for f in FILINGS_HISTORY})
    if "f13_cos" not in st.session_state:
        st.session_state.f13_cos = all_cos
    _kor = st.session_state.lang == "KOR"
    _tk_map = {f["company"]: f["ticker"] for f in FILINGS_HISTORY}
    ct_map = {
        "new":      t("change_new"),
        "increase": t("change_increase"),
        "decrease": t("change_decrease"),
        "exit":     t("change_exit"),
        "hold":     t("change_hold"),
    }
    # 변동 유형 토글 색(켜짐) — 카드 배지와 매칭. 데이터에 있는 유형만 노출(감소/유지는 자동)
    _CT_PILL = {
        "new":      ("rgba(34,197,94,.16)",   "#4ade80", "rgba(34,197,94,.55)"),
        "increase": ("rgba(74,144,217,.18)",  "#7ab8f5", "rgba(74,144,217,.55)"),
        "decrease": ("rgba(239,68,68,.18)",   "#f08a8a", "rgba(239,68,68,.55)"),
        "exit":     ("rgba(139,148,158,.18)", "#b0b8c2", "rgba(139,148,158,.5)"),
        "hold":     ("rgba(99,102,241,.18)",  "#a5a8f5", "rgba(99,102,241,.5)"),
    }
    # 변동 유형 노출: 유지(hold)는 불필요해 제외, 감소는 데이터 없어도 향후 대비 노출(붉은색)
    _ct_show = ["new", "increase", "decrease", "exit"]
    # 변동 유형 필 색상 동적 주입: key 기반 .st-key-f13_types 스코프, 모양=카드 배지와 동일(4px), 위치(nth)별 켜짐색·공통 꺼짐색
    _pill_css = ("<style>"
        ".st-key-f13_types [data-testid='stButtonGroup'] button{border-radius:4px !important;}"
        # 좁은 필터 열: 줄바꿈 허용 + 자연폭(라벨 truncation 방지)
        ".st-key-f13_types [data-testid='stButtonGroup']>div[class]{flex-wrap:wrap !important;gap:6px !important;}"
        ".st-key-f13_types [data-testid='stButtonGroup'] button{flex:0 0 auto !important;max-width:none !important;}"
        ".st-key-f13_types [data-testid='stButtonGroup'] button p{white-space:nowrap !important;overflow:visible !important;text-overflow:clip !important;}"
        ".st-key-f13_types button[data-testid='stBaseButton-pills']{"
        "background:#0c0c0c !important;border-color:#1f1f1f !important;opacity:.55 !important;}"
        ".st-key-f13_types button[data-testid='stBaseButton-pills'] p{color:#3f4651 !important;}")
    for _i, _k in enumerate(_ct_show, start=1):
        _bg, _tx, _bd = _CT_PILL[_k]
        _sel = (f".st-key-f13_types [data-testid='stButtonGroup']>div>"
                f"button:nth-of-type({_i})[data-testid='stBaseButton-pillsActive']")
        _pill_css += (f"{_sel}{{background:{_bg} !important;border-color:{_bd} !important;}}"
                      f"{_sel} p{{color:{_tx} !important;}}")
    _pill_css += "</style>"
    st.markdown(_pill_css, unsafe_allow_html=True)
    def _f13_filters():
        # 버튼은 좁은 필터 열에 맞춰 세로 스택. multiselect는 타이핑으로 기업 검색 가능.
        if st.button(("전체 선택" if _kor else "Select all"), use_container_width=True, key="f13_all"):
            st.session_state.f13_cos = all_cos; st.rerun()
        if st.button(("전체 해제" if _kor else "Clear all"), use_container_width=True, key="f13_none"):
            st.session_state.f13_cos = []; st.rerun()
        _sc = st.multiselect(
            t("filings_company"), all_cos, key="f13_cos",
            format_func=lambda c: f"{c} ({_tk_map.get(c, '')})",
            placeholder=("기업 검색·선택" if _kor else "Search companies"))
        # 변동 유형: 색 매칭 토글 필(있는 유형만). 켜짐=배지색 / 꺼짐=무채색
        _lbls = [ct_map[k] for k in _ct_show]
        _sel = st.pills(t("filings_type"), _lbls, selection_mode="multi", default=_lbls, key="f13_types") or []
        return _sc, [k for k in _ct_show if ct_map[k] in _sel]

    # 데스크톱: 필터 좌(sticky) / 카드 우 2단 · 모바일: 접이식 + 전폭
    if is_mobile:
        with st.expander("🔍 " + ("필터" if _kor else "Filter"), expanded=False):
            sel_cos, sel_ct_keys = _f13_filters()
        _list = st.container()
    else:
        _cf, _cl = st.columns([1, 1.9], gap="large")
        with _cf:
            st.markdown(f'<div class="f13-filter-title">🔍 {"필터" if _kor else "Filter"}</div>', unsafe_allow_html=True)
            sel_cos, sel_ct_keys = _f13_filters()
        _list = _cl

    filtered_f = sorted(
        [f for f in FILINGS_HISTORY if f["company"] in sel_cos and f["change_type"] in sel_ct_keys],
        key=lambda x: x["filed"], reverse=True
    )
    _cs = get_change_style()
    for f in filtered_f:
        ctype = f["change_type"]
        css, pill_bg, pill_tx, badge = _cs.get(ctype, ("filing-hold", "rgba(99,102,241,.18)", "#a5a8f5", t("change_hold")))
        # 우측 금액: ≥$1B → B(소수 2자리), 미만 → M (단위 통일, 본문 중복 $ 제거)
        v = f.get("value_m")
        if not v:        amt = ""
        elif v >= 1000:  amt = f"${round(v/10)/100:.2f}B"   # float 절삭 방지(1855→$1.86B)
        elif v == int(v):amt = f"${v:,.0f}M"
        else:            amt = f"${v:g}M"
        amt_color = "#8b949e" if ctype == "exit" else "#76b900"
        amt_html = (f'<span style="margin-left:auto;flex-shrink:0;color:{amt_color};'
                    f'font-weight:700;font-size:0.95rem">{amt}</span>') if amt else ""
        detail = (f.get("change_eng") or f["change"]) if st.session_state.lang == "ENG" else f["change"]
        detail_html = (f'<span style="color:#c4ccd6;font-size:0.82rem">{detail}</span>'
                       if detail else "<span></span>")
        _list.markdown(
            f'<div class="filing-row {css}">'
            # 1줄: 배지 · 회사(티커) ······ 금액
            f'<div style="display:flex;align-items:baseline;gap:10px">'
            f'<span style="flex-shrink:0;background:{pill_bg};color:{pill_tx};font-size:0.7rem;'
            f'font-weight:600;padding:2px 8px;border-radius:4px">{badge}</span>'
            f'<span style="color:#f9fafb;font-weight:600;font-size:0.95rem">{f["company"]} ({f["ticker"]})</span>'
            f'{amt_html}'
            f'</div>'
            # 2줄: 설명(좌) ····· 분기·날짜(우)
            f'<div style="display:flex;align-items:baseline;justify-content:space-between;'
            f'gap:12px;flex-wrap:wrap;margin-top:6px">'
            f'{detail_html}'
            f'<span style="flex-shrink:0;color:#6b7280;font-size:0.74rem">{f["quarter"]} · {f["filed"]}</span>'
            f'</div>'
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
        height=500, xaxis_title=t("filings_xaxis"), dragmode=False,
        legend=dict(bgcolor="#1f2937", orientation="h", y=1.12,
                    itemsizing="constant", traceorder="normal"),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig6, use_container_width=True, config=PLOTLY_CFG)

# ── 어드민 피드백 뷰 (비밀번호 보호) ─────────────────────────────────────────
import json, os, html

st.markdown("---")
with st.expander("Admin", expanded=False):
    # secret 미설정 시 어드민 비활성화 — 공개 레포에 fallback 비번을 두지 않음
    ADMIN_PW = st.secrets.get("admin", {}).get("password")
    if not ADMIN_PW:
        st.caption("관리자 기능이 비활성화되어 있습니다.")
    else:
        if "admin_auth" not in st.session_state:
            st.session_state.admin_auth = False

        if not st.session_state.admin_auth:
            with st.form("admin_login_form"):
                pw = st.text_input("비밀번호", type="password")
                submitted = st.form_submit_button("로그인")
                if submitted:
                    if pw == ADMIN_PW:
                        st.session_state.admin_auth = True
                        st.rerun()
                    else:
                        st.error("비밀번호가 틀렸습니다.")

        if st.session_state.admin_auth:
            path = "feedback.json"
            data = []
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
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

                # 피드백은 익명 사용자 입력 → 저장형 XSS 방지 위해 모든 필드 이스케이프 후 렌더
                for d in reversed(filtered_fb):
                    stars = "⭐" * d["rating"]
                    _cat = html.escape(str(d.get("category", "")))
                    _time = html.escape(str(d.get("time", "")))
                    _name = html.escape(str(d.get("name", "")))
                    _text = html.escape(str(d.get("text", "")))
                    st.markdown(f"""
                    <div class="news-card">
                      <div style="display:flex;justify-content:space-between">
                        <span style="color:#f9fafb;font-weight:600">{_cat}</span>
                        <span style="color:#9ca3af;font-size:0.78rem">{_time} · {_name}</span>
                      </div>
                      <div style="color:#fbbf24;font-size:0.85rem;margin:4px 0">{stars}</div>
                      <div style="color:#d1d5db;font-size:0.88rem">{_text}</div>
                    </div>""", unsafe_allow_html=True)

# ── 푸터 ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align:center;color:#2a2a2a;font-size:0.72rem;letter-spacing:0.5px'>"
    f"SEC EDGAR 13F &nbsp;·&nbsp; NVIDIA IR &nbsp;·&nbsp; Bloomberg &nbsp;·&nbsp; Reuters &nbsp;·&nbsp; FT &nbsp;·&nbsp; WSJ"
    f"&nbsp;&nbsp;|&nbsp;&nbsp;{t('footer_delay')}"
    f"&nbsp;&nbsp;|&nbsp;&nbsp;{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    f"</div>", unsafe_allow_html=True)
