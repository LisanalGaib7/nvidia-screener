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

    fail += pltr_cases()
    print(f"\n실패 {fail}건")
    sys.exit(1 if fail else 0)


# 2026-10-05 PLTR 실행 하루치 제목 일부 — 제목 유사도의 희귀도 기준(idf). 운영은 그날
# 수집분 전체로 계산한다. 같은 사건 0.27 이상 / 다른 사건 0.22 이하는 7일·1일 두 기준에서
# 같았지만, 이 고정 표본에서도 가르는지 함께 본다.
PLTR_DAY = [
    "ICE observer lawsuit shows how Palantir records can feed border screening, analytics",
    "Justin Bieber Faces Fierce Backlash Over Private Performance for Palantir Executives",
    "Could Palantir be banned from working in the NHS?",
    "Palantir's UK Reckoning: A £330 Million NHS Contract Hangs on a December Deadline",
    "Thousands back demand for Coventry council to end £1.25m Palantir contract",
    "Government Contract Update: $92M payment to PALANTIR USG INC",
    "Pressure grows on UK government to end Palantir NHS contract",
    "Palantir's Two-Front Test: Arcadia in Europe, Armada at Home",
    "Palantir calls on Stephen Conroy for reputation rehabilitation",
    "NHS may not be able to replace Palantir before £330m deal deadline",
    "UK fears grow over AI giant Palantir's health service deal",
    "Inklings | German government questioned on WFP and Palantir",
    "Palantir Weds Sovereign AI to Modular Data Centers as Washington Demand and European Doubts Pull in",
    "Palantir (PLTR) Defense Momentum Strengthens the Bullish Case",
    "Palantir stock gets a sovereign AI infrastructure deal",
    "What Is Driving Palantir Technologies (NASDAQ:PLTR) After Its Armada Tie-Up?",
    "Michael Burry Says He's Still Short Palantir After Stock Sees Recovery Following Trump's Endorsement",
    "Palantir Grew Revenue 85% and Raised Full-Year Guidance by 10 Points — So Why Is PLTR Down 26% YTD?",
]


def pltr_cases():
    """PLTR 레인 — 2026-10-05 리뷰에서 실측한 오판 사례. 상태 파일에 실제로 있던 키를 쓴다."""
    from news_monitor import (_idf_table, _title_sim, _window_hours, _group_index,
                              _looks_truncated)
    fail = 0
    now = datetime(2026, 10, 4, 6, tzinfo=timezone.utc)
    stored = {
        "nurses": ("san francisco nurses protest ice connection with palantir",
                   ["francisco", "ice", "san"], "2026-10-01T05:40:37+00:00"),
        "drone": ("french drone maker partners with european answer to palantir",
                  ["european", "french"], "2026-10-02T04:47:58+00:00"),
        "nhs": ("local campaigners call for nhs to tear up £330m palantir contract",
                ["nhs"], "2026-10-02T15:35:41+00:00"),
        "armada": ("palantir and armada partner to accelerate sovereign ai infrastructure",
                   ["armada"], "2026-10-02T05:25:36+00:00"),
        "watson": ("palantir hires ex-labour deputy tom watson as it aims to expand u.k. operations",
                   ["aims", "deputy", "ex-labour", "expand", "hires", "operations", "tom",
                    "u.k", "watson"], "2026-10-02T04:36:36+00:00"),
    }
    cases = [  # (새 제목, 과거 발송, 막혀야 하나)
        ("ICE Put Protester Photos Into Palantir's Surveillance Database", "nurses", False),
        ("ICE Is Reportedly Putting ICE Observers, Protesters in a Palantir Database", "nurses", False),
        ("European unions urge governments to scrap all Palantir deals", "drone", False),
        ("Louise Haigh hints at NHS ban on Palantir", "nhs", False),
        ("Palantir Technologies, Armada Partner on Sovereign Data Infrastructure Offering", "armada", True),
        ("Tom Watson's move to Palantir is the latest sign of how far the rot has spread in UK politics",
         "watson", True),
    ]
    idf = _idf_table(PLTR_DAY + [c[0] for c in cases])
    single = lambda a, b: _title_sim(a, b, idf) >= PL.cross_run_sim  # noqa: E731
    for h, which, want in cases:
        t, k, ts = stored[which]
        state = {"sent": [{"title": t, "key": k, "ts": ts}]}
        m = {"headline": h, "dkey": _dedupe_key(h, PL)}
        blocked = _sent_match(m, state, now, KEY_NOISE, None, single) is not None
        ok = blocked == want
        fail += not ok
        print(f"{'OK  ' if ok else 'FAIL'} PLTR교차  {h[:50]!r} → {'차단' if blocked else '통과'}"
              f"  (유사도 {_title_sim(h, t, idf):.2f})")

    # 수집 창 — 직전 실행 이후 + 1h, [25h, 72h]
    for last, want in ((None, 25), ("2026-10-03T00:00:00+00:00", 31), ("2026-09-20T00:00:00+00:00", 72)):
        got = _window_hours({"last_run": last} if last else {}, now)
        ok = abs(got - want) < 1e-6
        fail += not ok
        print(f"{'OK  ' if ok else 'FAIL'} 창  직전={last} → {got:.1f}h (기대 {want}h)")

    # 섹션 판정 — 논란이 'contract'보다 먼저, 단어 경계
    for h, want in (("NHS England must end its £330 million Palantir contract", "🏛"),
                    ("Palantir wins European Union contract for data platform", "📄"),
                    ("Palantir partners with Bank of America on AI", "📄"),
                    ("French drone maker partners with European answer to Palantir", "🤝")):
        got = PL.groups[_group_index(h, PL)]["label"][0]
        ok = got == want
        fail += not ok
        print(f"{'OK  ' if ok else 'FAIL'} 섹션  {h[:50]!r} → {got} (기대 {want})")

    # 잘린 제목 — 낱말 중간에서 잘린 것만
    for h, want in (("Palantir's software integration drives growth b", True),
                    ("Palantir backs Plan B", False), ("Palantir wins a", False)):
        ok = _looks_truncated(h) == want
        fail += not ok
        print(f"{'OK  ' if ok else 'FAIL'} 잘림  {h!r} → {_looks_truncated(h)}")
    return fail


if __name__ == "__main__":
    main()
