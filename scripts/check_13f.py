"""
NVIDIA 13F 공시 감지 스크립트
SEC EDGAR EFTS 검색 API에서 최신 13F-HR 제출일을 확인하고,
마지막으로 app.py에 반영한 날짜보다 새로우면 알림을 트리거함.
"""
import requests
import sys

# app.py에 마지막으로 반영한 13F 날짜 — 업데이트 시 함께 수정
LAST_REFLECTED = "2026-05-15"

CIK = "0001045810"  # NVIDIA Corp
HEADERS = {"User-Agent": "nvidia-screener-monitor aaaehgus@naver.com"}

def get_latest_13f():
    # efts.sec.gov — EDGAR Elasticsearch 검색 인프라 (별도 서버)
    url = (
        "https://efts.sec.gov/LATEST/search-index"
        f"?q=%22{CIK}%22&forms=13F-HR"
        "&dateRange=custom&startdt=2024-01-01"
        "&_source=file_date,period_of_report,accession_no,entity_name"
        "&hits.hits.total.relation=eq&hits.hits._source=file_date,accession_no"
    )
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        return None, None

    # 가장 최근 공시 (첫 번째 결과)
    source = hits[0].get("_source", {})
    file_date = source.get("file_date", "")
    acc_no = source.get("accession_no", "")
    return file_date, acc_no

def main():
    print(f"마지막 반영일: {LAST_REFLECTED}")

    latest_date, acc_no = get_latest_13f()
    if not latest_date:
        print("13F 공시를 찾을 수 없음")
        sys.exit(0)

    print(f"SEC 최신 13F: {latest_date} ({acc_no})")

    if latest_date > LAST_REFLECTED:
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
                f"마지막 반영일: {LAST_REFLECTED}"
            )
        print(f"🚨 새 13F 감지: {latest_date} > {LAST_REFLECTED}")
        sys.exit(1)
    else:
        print(f"✅ 변동 없음 (최신: {latest_date} = 마지막 반영일)")

if __name__ == "__main__":
    main()
