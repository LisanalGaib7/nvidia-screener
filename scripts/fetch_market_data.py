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
import re
import time
import sys
from datetime import date, datetime, timezone

# 비상장 종목 — app.py 에 등장하지만 시세가 없어 스냅샷에서 제외.
UNLISTED = {"GENB"}


def load_tickers():
    """app.py 종목 데이터에서 티커를 직접 추출 = 단일 진실 원천(SSOT).

    예전엔 이 목록을 손으로 app.py 와 동기화해야 했고, 빠뜨리면 신규 종목이
    '데이터 안 뜸'으로 나타났음(PLTR 사고). 이제 app.py 에 종목을 추가하면
    fetch 가 자동 반영 → 수동 동기화 footgun 제거.
    중복은 첫 등장 순서로 정리, 비상장(UNLISTED)은 제외.
    """
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        src = f.read()
    seen, tickers = set(), []
    for m in re.finditer(r'"ticker"\s*:\s*"([^"]+)"', src):
        tk = m.group(1)
        if tk in UNLISTED or tk in seen:
            continue
        seen.add(tk)
        tickers.append(tk)
    if not tickers:
        # app.py 포맷이 바뀌어 추출 실패 → 빈 스냅샷 방지 위해 즉시 중단
        raise RuntimeError("app.py 에서 티커를 추출하지 못함 — 데이터 포맷 변경 의심")
    return tickers


# 추적 종목 — app.py 에서 자동 추출(SSOT). 종목 추가/삭제는 app.py 한 곳만 수정.
TICKERS = load_tickers()

# 벤치마크 — 포트폴리오 카드/카운트엔 안 섞이고 YTD 차트 비교선으로만 사용
BENCHMARKS = [
    "NVDA",   # NVIDIA 본주
    "SOXX",   # iShares 반도체 ETF
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

    # 벤치마크 (차트 비교선용 — 본 종목 ok 집계엔 미포함)
    benchmarks = {}
    for tk in BENCHMARKS:
        q = fetch_one(tk)
        benchmarks[tk] = q
        print(f"{'OK ' if 'error' not in q else 'ERR'} [bench] {tk}: "
              f"{q.get('price', q.get('error', ''))}")
        time.sleep(0.4)

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
        "benchmarks": benchmarks,
    }
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "market_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote → {os.path.abspath(path)}")


if __name__ == "__main__":
    main()
