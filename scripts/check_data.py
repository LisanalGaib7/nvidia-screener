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

MAX_STALE_DAYS = 4  # 미국 종목용. 최장 공백이 목요일 휴장 → 월요일 = 4일

# 해외 종목은 달력이 아니라 '자기 시장'과 비교한다. 도쿄가 09-19~23 닷새 휴장
# (실버위크)했을 때 FANUC의 마지막 데이터가 정직하게 5일 전이었는데 달력 기준
# 4일에 걸려 오탐 경보가 나갔다. 종목이 시장 대표 지수와 같은 날에 멈춰 있으면
# 시장이 쉰 것이지 피드가 고장난 게 아니다.
MARKET_REF = {".T": "^N225"}

# 시장 기준만 쓰면 한 가지가 안 보인다 — 그 나라 피드 전체가 멈추면 지수와
# 종목이 같이 멈춰 '시장과 같음'으로 통과한다. 그걸 막는 절대 상한. 정확한 최장
# 휴장일을 몰라도 되는 값으로 잡았다(어떤 연휴보다 길기만 하면 된다).
MARKET_MAX_DAYS = 14


def judge(last, market_last, today):
    """(정상 여부, 사유). market_last가 None이면 달력 규칙으로 후퇴한다."""
    days_old = (today - last).days
    if market_last is not None:
        market_age = (today - market_last).days
        if market_age > MARKET_MAX_DAYS:
            return False, f"시장 데이터 자체가 {market_age}일 전 — 피드 장애 의심"
        if last >= market_last:
            return True, ""
        # 시장보다 뒤처졌을 때 더 엄하게 하지 않는다 — 지수와 종목의 갱신 시점이
        # 어긋나는 날 새 오탐을 만들지 않으려고. 기존 달력 규칙을 그대로 쓴다.
        if days_old > MAX_STALE_DAYS:
            return False, f"{days_old}일 전 — 시장({market_last})보다 뒤처짐"
        return True, ""
    if days_old > MAX_STALE_DAYS:
        return False, f"{days_old}일 전 — 너무 오래됨"
    return True, ""


_market_cache = {}


def market_last_for(ticker):
    """종목이 속한 시장의 마지막 거래일. 해당 없거나 조회 실패면 None."""
    for suffix, index in MARKET_REF.items():
        if not ticker.endswith(suffix):
            continue
        if index not in _market_cache:
            try:
                h = yf.Ticker(index).history(period="1mo")
                _market_cache[index] = h.index[-1].date() if not h.empty else None
            except Exception as e:
                print(f"⚠️  {index}: 시장 기준 조회 실패 — 달력 규칙으로 후퇴 ({e})")
                _market_cache[index] = None
        return _market_cache[index]
    return None


def main():
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
            fresh, why = judge(last_date, market_last_for(ticker), today)

            if not fresh:
                issue_lines.append(
                    f"⚠️ **{ticker}** ({name}): 마지막 데이터 {last_date} ({why})"
                )
                print(f"⚠️  {ticker}: stale ({last_date}, {why})")
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


if __name__ == "__main__":
    main()
