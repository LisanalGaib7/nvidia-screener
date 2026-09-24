"""
중복제거 키 회귀 테스트. 중복제거 오류는 눈에 안 보이는 종류라(잘못 합치면 사건이
조용히 사라진다) 키를 바꿀 때마다 돌린다.

사례는 2026-09-24 실측에서 가져왔다. 그날 수집분의 소문자 근거가 전혀 없는
최악의 실행(run_common 비움)을 가정한다 — 사전만으로 버텨야 한다.

실행: python scripts/test_dedupe.py
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from news_monitor import _dedupe_key, _sent_match, KEY_NOISE  # noqa: E402
import check_news as N          # noqa: E402
import check_pltr_news as P     # noqa: E402
import check_hanwha_news as H   # noqa: E402

NV, PL = N.CONFIG, P.CONFIG

# 서로 다른 사건 — 합쳐지면 안 된다 (합쳐지면 뒤엣것이 사라진다)
MUST_SPLIT = [
    (NV, "Nvidia-backed AI cloud firm Nscale reveals revenue surge in US IPO filing",
         "Nvidia-Backed AI Drugmaker Iambic Therapeutics Files for IPO"),
    (NV, "Nvidia-backed AI cloud firm Nscale reveals revenue surge in US IPO filing",
         "NVIDIA Invests Another $1.5 Billion in SB Energy Ahead of IPO"),
    (NV, "Nvidia-backed AI cloud firm Nscale reveals revenue surge in US IPO filing",
         "Nvidia-Backed AI Startup Seeks $10 Billion Before Australian IPO"),
    (NV, "Nvidia-Backed Startup Tests Investor Appetite",
         "Nvidia Backed This AI Drug Startup. AbbVie Just Became a Partner"),
    (NV, "Nebius Revenue Surges 454% as Nvidia-Backed Neocloud Rivals Reshape AI",
         "Nvidia-Backed Nscale Touts $103 Billion In Contracted Revenue"),
    # PLTR은 계약 뉴스가 핵심 — "Contract"가 키에 들어가면 다른 계약끼리 막는다
    (PL, "Palantir Wins $48M Army Contract To Modernize Ammunition Systems",
         "Palantir Secures NHS Contract Extension Worth $330 Million"),
]
# 같은 사건 — 묶여야 한다 (안 묶이면 중복 발송)
MUST_MERGE = [
    (NV, "Nvidia-backed AI cloud firm Nscale reveals revenue surge in US IPO filing",
         "Nvidia-Backed UK AI Cloud Firm Nscale Files for NYSE IPO"),
    (NV, "Nvidia-backed Zankore Indonesia secures US$3.1 billion loan",
         "Nvidia-backed Zankore raises a $3.1bn loan to buy Nvidia GPUs for Indonesia"),
    (NV, "Nvidia-Backed AI Drugmaker Iambic Therapeutics Files for IPO",
         "NVIDIA-backed Iambic Therapeutics files for IPO"),
    (PL, "Palantir taps ex-Labour deputy Tom Watson to steer UK push",
         "Palantir Hires Ex-Labour Deputy Tom Watson as It Aims to Expand U.K. Operations"),
]


def main():
    fail = 0
    for cfg, a, b in MUST_SPLIT:
        ka, kb = _dedupe_key(a, cfg), _dedupe_key(b, cfg)
        ok = not (ka & kb)
        fail += not ok
        print(f"{'OK  ' if ok else 'FAIL'} 분리  {a[:38]!r} / {b[:38]!r}  공유={sorted(ka & kb)}")
    for cfg, a, b in MUST_MERGE:
        ka, kb = _dedupe_key(a, cfg), _dedupe_key(b, cfg)
        ok = bool(ka & kb)
        fail += not ok
        print(f"{'OK  ' if ok else 'FAIL'} 병합  {a[:38]!r} / {b[:38]!r}  공유={sorted(ka & kb)}")

    # 교차 실행: 오염된 과거 키가 새 사건을 막지 않아야 한다 (실제 상태 파일에 있던 형태)
    now = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
    state = {"sent": [{"title": "nvidia-backed ai cloud firm nscale reveals revenue surge in us ipo filing",
                       "key": ["ipo", "nscale"], "ts": "2026-09-19T02:10:00+00:00"}]}
    for h, want_block in (("Nvidia-Backed AI Drugmaker Iambic Therapeutics Files for IPO", False),
                          ("Nvidia-Backed UK AI Cloud Firm Nscale Files for NYSE IPO", True)):
        m = {"headline": h, "dkey": _dedupe_key(h, NV)}
        blocked = _sent_match(m, state, now, KEY_NOISE) is not None
        ok = blocked == want_block
        fail += not ok
        print(f"{'OK  ' if ok else 'FAIL'} 교차  {h[:52]!r} → {'차단' if blocked else '통과'}")

    # 한글 레인은 키 방식이 달라 영향이 없어야 한다
    hk = _dedupe_key("한화엔진, 1조원 규모 선박엔진 공급계약 체결", H.CONFIG)
    ok = hk == {"한화엔진1조원규모선박엔진"}
    fail += not ok
    print(f"{'OK  ' if ok else 'FAIL'} 한글  키={hk}")

    print(f"\n실패 {fail}건")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
