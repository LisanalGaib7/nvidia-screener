"""
NVIDIA Tracker — Macro Risk Monitor

AI 사이클 자본공급 붕괴 시그널 모니터링 (KB 하반기 전략 기준)
  ① 10년물 국채금리 5.0% 돌파
  ② Core Sticky CPI less shelter 3.3% 돌파

GitHub Actions 평일 08:00 KST 실행 — Telegram 알림 발송.
임계 돌파 시 1회만 알림, 기준선 아래 복귀 시 상태 리셋.
상태는 data/macro_state.json 에 저장.

FRED 시리즈: CORESTICKM159SFRBATL (Core Sticky Price CPI less Food & Energy, Atlanta Fed)
  ⚠️ KB 리포트의 "less shelter"와 완전 동일하지 않음 — 가장 근접한 공개 시리즈.
  FRED_API_KEY 환경변수가 있으면 사용, 없어도 소량 요청이라 작동함.
"""

import os
import json
import requests
import yfinance as yf
from datetime import datetime, timezone

# ── 임계값 (KB 하반기 전략 위험 시그널) ───────────────────────────────────────
YIELD_THRESHOLD = 5.0    # 10년물 국채금리 %
CPI_THRESHOLD   = 3.3    # Core Sticky CPI less shelter %

CPI_SERIES = "CORESTICKM159SFRBATL"

STATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "macro_state.json"
)


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_yield():
    """10년물 국채금리 (^TNX) via yfinance."""
    try:
        info = yf.Ticker("^TNX").info
        val = info.get("regularMarketPrice") or info.get("currentPrice")
        return float(val) if val else None
    except Exception as e:
        print(f"yield fetch error: {e}")
        return None


def fetch_cpi():
    """Core Sticky CPI (CORESTICKM159SFRBATL) via FRED API."""
    api_key = os.environ.get("FRED_API_KEY", "")
    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={CPI_SERIES}&sort_order=desc&limit=3&file_type=json"
    )
    if api_key:
        url += f"&api_key={api_key}"
    try:
        r = requests.get(url, timeout=15, headers={"Accept": "application/json"})
        r.raise_for_status()
        obs = r.json().get("observations", [])
        for o in obs:  # "." = missing value 건너뜀
            if o.get("value", ".") != ".":
                return float(o["value"]), o["date"]
    except Exception as e:
        print(f"CPI fetch error: {e}")
    return None, None


def send_telegram(msg):
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("[telegram] credentials missing — skipping")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return r.ok
    except Exception as e:
        print(f"telegram error: {e}")
        return False


def main():
    test_mode = os.environ.get("TEST_MODE", "").lower() == "true"
    if test_mode:
        print("🧪 TEST MODE — sending mock alerts")
        send_telegram(
            f"🧪 <b>[테스트] 매크로 위험 알림 포맷 미리보기</b>\n\n"
            f"🚨 <b>10년물 국채금리 5.0% 돌파</b>\n"
            f"현재: <b>5.03%</b>\n\n"
            f"AI 사이클 자본공급 위험 시그널 #1\n"
            f"출처: Yahoo Finance (^TNX)"
        )
        send_telegram(
            f"🧪 <b>[테스트] 매크로 위험 알림 포맷 미리보기</b>\n\n"
            f"🚨 <b>Core Sticky CPI 3.3% 돌파</b>\n"
            f"현재: <b>3.4%</b>  (2026-04-01)\n\n"
            f"AI 사이클 자본공급 위험 시그널 #2\n"
            f"출처: FRED · Atlanta Fed ({CPI_SERIES})"
        )
        print("test messages sent")
        return

    state  = load_state()
    alerts = []

    # ── ① 10년물 국채금리 ────────────────────────────────────────────────────
    yield_val = fetch_yield()
    print(f"10Y Yield : {yield_val}%  (threshold ≥ {YIELD_THRESHOLD}%)")

    if yield_val is not None:
        already = state.get("yield_above_5", False)
        if yield_val >= YIELD_THRESHOLD and not already:
            alerts.append(
                f"🚨 <b>10년물 국채금리 {YIELD_THRESHOLD}% 돌파</b>\n"
                f"현재: <b>{yield_val:.2f}%</b>\n\n"
                f"AI 사이클 자본공급 위험 시그널 #1\n"
                f"출처: Yahoo Finance (^TNX)"
            )
            state["yield_above_5"] = True
            print("ALERT: yield breached")
        elif yield_val < YIELD_THRESHOLD and already:
            state["yield_above_5"] = False
            print("yield back below threshold — state reset")
        else:
            print("yield: no change")

    # ── ② Core Sticky CPI ───────────────────────────────────────────────────
    cpi_val, cpi_date = fetch_cpi()
    print(f"Core Sticky CPI: {cpi_val}%  date: {cpi_date}  (threshold ≥ {CPI_THRESHOLD}%)")

    if cpi_val is not None:
        last_alert_date = state.get("cpi_last_alert_date", "")
        if cpi_val >= CPI_THRESHOLD and cpi_date != last_alert_date:
            alerts.append(
                f"🚨 <b>Core Sticky CPI {CPI_THRESHOLD}% 돌파</b>\n"
                f"현재: <b>{cpi_val:.1f}%</b>  ({cpi_date})\n\n"
                f"AI 사이클 자본공급 위험 시그널 #2\n"
                f"출처: FRED · Atlanta Fed ({CPI_SERIES})"
            )
            state["cpi_last_alert_date"] = cpi_date
            print(f"ALERT: CPI breached ({cpi_date})")
        elif cpi_val < CPI_THRESHOLD:
            if last_alert_date:
                state["cpi_last_alert_date"] = ""
                print("CPI back below threshold — state reset")
        else:
            print("CPI: no change")

    # ── 발송 ─────────────────────────────────────────────────────────────────
    if alerts:
        for msg in alerts:
            ok = send_telegram(msg)
            print(f"telegram sent: {ok}")
    else:
        print("✅ no threshold breach")

    save_state(state)
    print(f"state saved → {STATE_PATH}")


if __name__ == "__main__":
    main()
