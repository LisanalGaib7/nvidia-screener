"""
중복제거 키 정제용 흔한 단어 사전(data/common_words.json)을 만든다.

중복제거 키는 "대문자로 시작하는 단어 = 회사 이름"이라고 가정한다. 그런데 제목의
절반이 모든 단어를 대문자로 쓰는 Title Case라서 "Files", "Startup", "IPO" 같은
흔한 단어가 키에 들어가 서로 다른 사건을 합친다. 2026-09-24 실측: Nscale IPO 기록의
키에 "ipo"가 있어 이후 3일간 "IPO"가 든 제목이 전부 막혔고, 진짜 사건 두 개
(NVIDIA의 SB Energy $1.5B 추가 투자, Iambic IPO)가 조용히 사라졌다.

소문자로 쓰인 적이 있는 단어는 회사 이름이 아니다. 다만 그날 수집분만으로는 근거가
부족하다 — 한 레인의 2일치(112~153건)에선 흔한 단어 21개 중 10~17개가 근거가
없었다. 그래서 NVIDIA·팔란티어와 무관한 일반 비즈니스 기사에서 뽑아 레포에
고정한다(표본 밖에서 만든 사전이라 표본 안 채점도 피한다).

실행: python scripts/build_common_words.py   (분기에 한 번쯤 갱신)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from news_monitor import MonitorConfig, _fetch_one, _strip_source

# 10개로 시작했다가 30개로 늘렸다 — 10개(1,086단어)로는 "meets", "sovereign"이 빠져
# PLTR 레인에서 서로 다른 기사가 막히는 걸 차단 사유 로그로 확인했다(2026-09-25).
QUERIES = [
    "startup funding round", "files for IPO", "defense contract awarded",
    "data center investment", "acquisition deal agreed", "company hires chief executive",
    "quarterly revenue growth", "stock market valuation",
    "government regulation technology", "venture capital raises",
    "sovereign wealth fund", "company meets analyst expectations", "strategic alliance announced",
    "chief executive resigns", "lawsuit filed against company", "antitrust probe",
    "partnership expands", "earnings beat estimates", "bank lending loan",
    "energy transition investment", "semiconductor supply chain", "cloud computing deal",
    "cybersecurity breach", "healthcare startup", "robotics company",
    "electric vehicle maker", "retail sales slump", "central bank rates",
    "private equity buyout", "software company layoffs",
]
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "common_words.json")


def main():
    cfg = MonitorConfig(query="", positive=[], negative=[], header="", footer="",
                        out_file="", label="common-words builder")
    titles = set()
    for q in QUERIES:
        # 감시 대상 사명이 든 제목은 빼야 사전에 회사 이름이 섞이지 않는다
        for it in _fetch_one(f"{q} -nvidia -palantir when:7d", cfg):
            titles.add(_strip_source(it["title"], it["source"])[0])
    words = set()
    for h in titles:
        for tok in re.findall(r"[A-Za-z][A-Za-z0-9&.\-]{2,}", h):
            if tok[0].islower():
                words.add(tok.lower().strip("."))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(sorted(words), f, ensure_ascii=False, indent=0)
    print(f"원천 제목 {len(titles)}건 → 소문자 단어 {len(words)}개 → {OUT}")


if __name__ == "__main__":
    main()
