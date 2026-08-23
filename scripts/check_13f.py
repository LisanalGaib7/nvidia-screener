"""
NVIDIA 13F 공시 감지 스크립트
data.sec.gov submissions API에서 최신 13F-HR 제출일을 확인하고,
app.py의 FILINGS_HISTORY에 반영된 마지막 공시일보다 새로우면 알림을 트리거함.

마지막 반영일을 별도 상수로 하드코딩하지 않는 이유: app.py의 LAST_VERIFIED와
따로 관리하다 둘 다 갱신을 놓쳐, 이미 반영 완료된 공시에 알림이 계속 온 사고가
있었음(2026-08-23). app.py가 유일한 소스 — 여기선 그걸 파싱만 한다.
"""
import ast
import sys
from pathlib import Path

import requests

APP_PY = Path(__file__).resolve().parent.parent / "app.py"
CIK = "0001045810"  # NVIDIA Corp
HEADERS = {"User-Agent": "nvidia-screener-monitor aaaehgus@naver.com"}


def last_reflected_13f():
    """app.py의 FILINGS_HISTORY에서 최신 13F 공시일을 파생.
    quarter가 채워진 항목만 13F(PIPE·워런트·SC 13G 등은 quarter가 비어 자동 제외)."""
    src = APP_PY.read_text(encoding="utf-8")
    tree = ast.parse(src)
    node = next(
        (n.value for n in tree.body
         if isinstance(n, ast.Assign)
         and any(isinstance(t, ast.Name) and t.id == "FILINGS_HISTORY" for t in n.targets)),
        None,
    )
    if node is None:
        raise RuntimeError("app.py에서 FILINGS_HISTORY를 찾을 수 없음")
    rows = ast.literal_eval(node)
    thirteen_f = [r for r in rows if r.get("quarter")]
    if not thirteen_f:
        raise RuntimeError("FILINGS_HISTORY에 quarter가 있는 13F 항목이 없음")
    return max(thirteen_f, key=lambda r: r["filed"])["filed"]


def get_latest_13f():
    # data.sec.gov — EDGAR 공식 submissions API
    url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    forms   = data["filings"]["recent"]["form"]
    dates   = data["filings"]["recent"]["filingDate"]
    acc_nos = data["filings"]["recent"]["accessionNumber"]

    for i in range(len(forms)):
        if forms[i] == "13F-HR":
            return dates[i], acc_nos[i]

    return None, None


def main():
    try:
        last_reflected = last_reflected_13f()
    except (SyntaxError, ValueError, RuntimeError) as e:
        # 조용히 넘어가면 진짜 새 공시를 놓칠 수 있으니 크게 실패시킨다.
        print(f"app.py 파싱 실패: {e}")
        sys.exit(2)

    print(f"마지막 반영일: {last_reflected}")

    latest_date, acc_no = get_latest_13f()
    if not latest_date:
        print("13F 공시를 찾을 수 없음")
        sys.exit(0)

    print(f"SEC 최신 13F: {latest_date} ({acc_no})")

    if latest_date > last_reflected:
        filing_url = (
            "https://www.sec.gov/cgi-bin/browse-edgar"
            f"?action=getcompany&CIK={CIK}&type=13F&dateb=&owner=include&count=5"
        )
        with open("13f_alert.txt", "w", encoding="utf-8") as f:
            f.write(
                f"새 13F 공시 감지!\n"
                f"공시일: {latest_date}\n"
                f"접수번호: {acc_no}\n"
                f"SEC 링크: {filing_url}\n"
                f"마지막 반영일: {last_reflected}"
            )
        print(f"🚨 새 13F 감지: {latest_date} > {last_reflected}")
        sys.exit(1)
    else:
        print(f"✅ 변동 없음 (최신: {latest_date} = 마지막 반영일)")


if __name__ == "__main__":
    main()
