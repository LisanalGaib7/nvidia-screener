"""
NVIDIA Portfolio Tracker — Daily market-close data check
Runs via GitHub Actions after US market close (weekdays).
Exits with code 1 if any ticker has stale or missing data.
"""
import yfinance as yf
import sys
from datetime import date

# Active holdings only (exited positions excluded)
TICKERS = [
    ("IREN",   "IREN Ltd"),
    ("GLW",    "Corning"),
    ("MRVL",   "Marvell Technology"),
    ("LITE",   "Lumentum Holdings"),
    ("COHR",   "Coherent Corp"),
    ("INTC",   "Intel"),
    ("SNPS",   "Synopsys"),
    ("NOK",    "Nokia"),
    ("CRWV",   "CoreWeave"),
    ("NBIS",   "Nebius Group"),
    ("6954.T", "FANUC"),   # Tokyo Stock Exchange — closes earlier, data still valid
]

MAX_STALE_DAYS = 4  # allow up to 4 days gap (covers long weekends / holidays)

ok_lines    = []
issue_lines = []
today       = date.today()

for ticker, name in TICKERS:
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            issue_lines.append(f"❌ **{ticker}** ({name}): 데이터 없음 (empty response)")
            print(f"❌ {ticker}: no data")
            continue

        last_date = hist.index[-1].date()
        price     = hist["Close"].iloc[-1]
        days_old  = (today - last_date).days

        if days_old > MAX_STALE_DAYS:
            issue_lines.append(
                f"⚠️ **{ticker}** ({name}): 마지막 데이터 {last_date} "
                f"({days_old}일 전 — 너무 오래됨)"
            )
            print(f"⚠️  {ticker}: stale ({last_date}, {days_old}d ago)")
        elif price <= 0:
            issue_lines.append(
                f"❌ **{ticker}** ({name}): 비정상 가격 (${price:.2f})"
            )
            print(f"❌ {ticker}: bad price {price}")
        else:
            ok_lines.append(f"✅ `{ticker}` {name} — **${price:.2f}** ({last_date})")
            print(f"✅ {ticker}: ${price:.2f} ({last_date})")

    except Exception as e:
        issue_lines.append(f"❌ **{ticker}** ({name}): 예외 발생 — {str(e)[:120]}")
        print(f"❌ {ticker}: exception — {e}")

# Summary
total = len(TICKERS)
print(f"\n{total}개 종목 중 {len(ok_lines)}개 정상 / {len(issue_lines)}개 이상")

if issue_lines:
    body  = f"### 이상 감지 ({len(issue_lines)}/{total})\n\n"
    body += "\n".join(issue_lines)
    body += "\n\n---\n\n### 정상 종목\n\n"
    body += "\n".join(ok_lines) if ok_lines else "_없음_"

    with open("check_result.txt", "w", encoding="utf-8") as f:
        f.write(body)

    sys.exit(1)

print("All clear ✅")
