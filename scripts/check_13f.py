"""
NVIDIA 13F 공시 감지 스크립트
SEC EDGAR Atom 피드에서 최신 13F-HR 제출일을 확인하고,
마지막으로 app.py에 반영한 날짜보다 새로우면 알림을 트리거함.
"""
import requests
import xml.etree.ElementTree as ET
import sys

# app.py에 마지막으로 반영한 13F 날짜 — 업데이트 시 함께 수정
LAST_REFLECTED = "2026-05-15"

CIK = "0001045810"  # NVIDIA Corp
HEADERS = {"User-Agent": "nvidia-screener-monitor aaaehgus@naver.com"}

def get_latest_13f():
    # data.sec.gov JSON API 대신 www.sec.gov Atom 피드 사용 (클라우드 IP 차단 우회)
    url = (
        f"https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={CIK}&type=13F-HR"
        f"&dateb=&owner=include&count=5&output=atom"
    )
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for entry in root.findall("atom:entry", ns):
        updated = entry.find("atom:updated", ns)
        id_elem  = entry.find("atom:id", ns)

        if updated is not None:
            date   = updated.text[:10]  # YYYY-MM-DD
            acc_no = ""
            if id_elem is not None and "accession-number=" in (id_elem.text or ""):
                acc_no = id_elem.text.split("accession-number=")[-1]
            return date, acc_no

    return None, None

def main():
    print(f"마지막 반영일: {LAST_REFLECTED}")

    latest_date, acc_no = get_latest_13f()
    if not latest_date:
        print("13F 공시를 찾을 수 없음")
        sys.exit(0)

    print(f"SEC 최신 13F: {latest_date} ({acc_no})")

    if latest_date > LAST_REFLECTED:
        filing_url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar"
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
