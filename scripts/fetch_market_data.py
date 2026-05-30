"""
NVIDIA Tracker — daily market data snapshot.

추적 종목의 시세 + 1년 종가 히스토리를 받아 data/market_data.json 으로 저장함.
GitHub Actions(러너마다 새 IP, 하루 1회 소량 요청)에서 실행 → Streamlit Cloud
공유 IP의 Yahoo rate-limit("Too Many Requests")을 회피. 앱은 Yahoo를 직접
호출하지 않고 이 JSON 파일만 읽음.

실패가 과반이면 스냅샷을 신뢰하지 않고 exit 1 → 워크플로가 기존 파일을 보존.
"""
import yfinance as yf
import json
import os
import time
import sys
from datetime import date, datetime, timezone

# 추적 종목 — app.py 의 NEW_2026 / CURRENT_HOLDINGS / PARTNERSHIPS / EXITED 와 동기화 유지.
# (GENB 는 비상장이라 시세 없음 → 제외)
TICKERS = [
    "IREN", "GLW", "MRVL", "LITE", "COHR",            # NEW_2026
    "INTC", "SNPS", "NOK", "CRWV", "NBIS",            # CURRENT_HOLDINGS
    "6954.T",                                          # PARTNERSHIPS (FANUC)
    "RXRX", "ARM", "APLD", "WRD", "SOUN", "SERV", "NNOX",  # EXITED
]


def fetch_one(ticker):
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
            prev = info.get("regularMarketPreviousClose") or (
                hist["Close"].iloc[-2] if len(hist) > 1 else price)
            change_pct = ((price - prev) / prev * 100) if price and prev else None
            ytd_h = hist[hist.index >= f"{date.today().year}-01-01"]["Close"]
            ytd_pct = ((price - ytd_h.iloc[0]) / ytd_h.iloc[0] * 100
                       if not ytd_h.empty and price else None)
            closes = [[d.strftime("%Y-%m-%d"), round(float(c), 4)]
                      for d, c in hist["Close"].items()]
            return {
                "price": float(price) if price is not None else None,
                "change_pct": change_pct,
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "week52_high": info.get("fiftyTwoWeekHigh"),
                "week52_low": info.get("fiftyTwoWeekLow"),
                "ytd_pct": ytd_pct,
                "currency": info.get("currency", "USD"),
                "hist": closes,
            }
        except Exception as e:
            last_err = str(e)
            if attempt < 2:
                time.sleep(2 * (attempt + 1))  # 2s, 4s 백오프
    return {"error": last_err}


def fetch_usdjpy():
    for attempt in range(3):
        try:
            info = yf.Ticker("USDJPY=X").info
            rate = info.get("regularMarketPrice") or info.get("currentPrice")
            if rate:
                return float(rate)
        except Exception:
            pass
        time.sleep(2)
    return 150.0


def main():
    quotes = {}
    ok = 0
    for tk in TICKERS:
        q = fetch_one(tk)
        quotes[tk] = q
        if "error" not in q:
            ok += 1
            print(f"OK  {tk}: {q['price']}")
        else:
            print(f"ERR {tk}: {q['error'][:60]}")
        time.sleep(0.4)  # gentle pacing — 러너 IP 보호

    usdjpy = fetch_usdjpy()
    print(f"\n{ok}/{len(TICKERS)} ok  usdjpy={usdjpy}")

    # 과반 실패 → 스냅샷 신뢰 불가, 쓰지 않고 종료 (기존 파일 보존)
    if ok < len(TICKERS) * 0.5:
        print("too many failures — aborting, keeping previous snapshot")
        sys.exit(1)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "usdjpy": usdjpy,
        "quotes": quotes,
    }
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "market_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote → {os.path.abspath(path)}")


if __name__ == "__main__":
    main()
