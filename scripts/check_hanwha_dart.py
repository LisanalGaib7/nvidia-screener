"""
한화엔진 DART 공시 감지 — 수주(단일판매·공급계약)와 잠정실적을 Telegram 알림.

뉴스 모니터(check_hanwha_news.py)와 합치지 않은 이유: 출력이 헤드라인 목록이
아니라 수치 표라서 메시지 포맷이 근본적으로 다르다. 뉴스는 "무슨 얘기가 도는가",
공시는 "회사가 뭘 신고했는가" — 신뢰도도 즉시성도 다른 신호다.

소스 3개, 역할이 갈린다:
  - DART document.xml : 발표 분기 매출·영업익·순이익. 정본이고 즉시 나온다.
  - 네이버 finance/quarter : 직전 4개 분기 추이 + 컨센서스. 확정 발표 반영은 느리다.
  - 네이버 integration : 시가총액.

보고서명은 추측하지 말 것. 2024-01 ~ 2026-09 공시 181건을 전수로 세어서 정한
이름들이다. 수주는 `단일판매ㆍ공급계약체결`(가운뎃점이 U+318D, 일반 · 아님),
실적은 `영업(잠정)실적(공정공시)`과 `연결재무제표기준영업(잠정)실적(공정공시)`
두 이름으로 들어온다. 보고서명 뒤에 공백이 붙어 오므로 항상 strip 한다.
"""
import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))
CORP_CODE = "00361008"          # 한화엔진. 종목코드 082740과 다른 DART 고유번호
STOCK_CODE = "082740"
LOOKBACK_DAYS = 2               # 조회 범위. 실제 중복 차단은 발송 이력(rcept_no)이 한다.
                                # DART는 list.json에도 본문에도 접수 *시각*을 안 준다 —
                                # 날짜뿐이라 시간 창으로는 매시 실행 때 같은 공시가
                                # 하루 종일 재발송된다.
OUT_FILE = "hanwha_dart_alert.txt"
CONSENSUS_FILE = "data/hanwha_consensus.json"

DART_LIST = "https://opendart.fss.or.kr/api/list.json"
DART_DOC = "https://opendart.fss.or.kr/api/document.xml"
DART_VIEW = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="
NAVER = "https://m.stock.naver.com/api/stock/" + STOCK_CODE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"}

# 알림 대상 보고서명(공백 제거 후 부분일치). 실측 빈도: 공급계약 36, 실적 11, 손익변경 3.
EARNINGS = "영업(잠정)실적"
CONTRACT = "단일판매ㆍ공급계약체결"
STRUCTURE = "매출액또는손익구조"


def _key():
    """DART 키 — 환경변수 우선, 없으면 로컬 secrets.toml. Finnhub와 같은 방식."""
    k = os.environ.get("DART_API_KEY")
    if k:
        return k.strip()
    try:
        import tomllib
        with open(".streamlit/secrets.toml", "rb") as f:
            conf = tomllib.load(f)
        if conf.get("DART_API_KEY"):
            return str(conf["DART_API_KEY"]).strip()
        # 최상위에 없으면 섹션 안까지 — TOML에서 키가 섹션 아래로 밀려 들어가는
        # 배치 실수가 흔하다(FINNHUB_API_KEY로 실제 한 번 막혔음)
        for v in conf.values():
            if isinstance(v, dict) and v.get("DART_API_KEY"):
                return str(v["DART_API_KEY"]).strip()
    except Exception:
        pass
    return None


def _set_output(found):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"found={'true' if found else 'false'}\n")


def fetch_disclosures(key, now):
    """최근 LOOKBACK_DAYS 일 공시. 실패는 조용히 빈 목록 — 가짜 알람 방지."""
    day = now.strftime("%Y%m%d")
    prev = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
    try:
        r = requests.get(DART_LIST, timeout=20, params={
            "crtfc_key": key, "corp_code": CORP_CODE,
            "bgn_de": prev, "end_de": day, "page_count": 100})
        j = r.json()
    except Exception as e:
        print(f"dart list error: {e}")
        return []
    if j.get("status") != "000":
        # 013 = 조회 결과 없음. 정상 상황이라 경고할 일이 아니다.
        if j.get("status") != "013":
            print(f"dart list status {j.get('status')}: {j.get('message')}")
        return []
    return j.get("list", [])


def fetch_document(key, rcept_no):
    """공시 원문(ZIP 안 XML). 라벨 기준으로 값을 뽑기 위해 태그를 벗겨 평문화."""
    try:
        r = requests.get(DART_DOC, params={"crtfc_key": key, "rcept_no": rcept_no}, timeout=30)
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        raw = zf.read(zf.namelist()[0]).decode("utf-8", "replace")
    except Exception as e:
        print(f"dart document error ({rcept_no}): {e}")
        return ""
    raw = re.sub(r"<STYLE.*?</STYLE>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def naver_quarters():
    """분기 실적 추이와 컨센서스. 반환: (확정 [(라벨, 매출, 영업익, 순이익)], 컨센서스 dict)"""
    try:
        j = requests.get(NAVER + "/finance/quarter", headers=UA, timeout=15).json()
        fi = j["financeInfo"]
    except Exception as e:
        print(f"naver finance error: {e}")
        return [], {}
    rows = {r["title"]: r["columns"] for r in fi.get("rowList", [])}

    def val(metric, key):
        return (rows.get(metric, {}).get(key) or {}).get("value")

    actual, consensus = [], {}
    for col in fi.get("trTitleList", []):
        k = col["key"]                      # "202606"
        y, m = k[:4], int(k[4:6])
        label = f"{y}.{(m - 1) // 3 + 1}Q"
        trio = (val("매출액", k), val("영업이익", k), val("당기순이익", k))
        if col.get("isConsensus") == "Y":
            consensus[label] = trio
        else:
            actual.append((label, *trio))
    actual.reverse()                        # 최신 분기부터
    return actual, consensus


def naver_market_cap():
    try:
        j = requests.get(NAVER + "/integration", headers=UA, timeout=15).json()
        for t in j.get("totalInfos", []):
            if t.get("code") == "marketValue":
                return t.get("value")
    except Exception as e:
        print(f"naver integration error: {e}")
    return None


def save_consensus(consensus):
    """컨센서스는 확정 발표가 나오는 순간 네이버에서 실제값으로 덮어써진다.

    발표 시점에 '예상치 대비'를 계산하려면 발표 *전에* 받아둔 값이 있어야 해서
    레포에 보관한다(data/market_data.json을 매일 커밋하는 기존 패턴과 같다).
    값이 바뀔 때만 True를 반환해 호출부가 불필요한 커밋을 안 만들게 한다.
    """
    if not consensus:
        return False
    try:
        with open(CONSENSUS_FILE, encoding="utf-8") as f:
            stored = json.load(f)
    except Exception:
        stored = {}
    # JSON은 튜플을 리스트로 되돌려주므로 비교 전에 형을 맞춘다. 안 맞추면
    # 값이 그대로여도 매번 '변경'으로 잡혀 매시 실행이 하루 24커밋을 만든다.
    merged = dict(stored)
    merged.update({k: list(v) for k, v in consensus.items()})
    if merged == stored:
        return False
    os.makedirs(os.path.dirname(CONSENSUS_FILE), exist_ok=True)
    with open(CONSENSUS_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1, sort_keys=True)
    return True


STATE_FILE = "data/hanwha_dart_state.json"
KEEP_IDS = 300


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"alerted": []}


def save_state(state):
    state["alerted"] = state["alerted"][-KEEP_IDS:]
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)

def load_consensus(label):
    try:
        with open(CONSENSUS_FILE, encoding="utf-8") as f:
            return json.load(f).get(label)
    except Exception:
        return None


def _fmt_date(rcept_dt):
    """DART는 접수 *날짜*만 준다(list.json에도 본문에도 시각이 없음). 매시 실행이라
    감지 시점이 곧 공시 시점에 가깝지만, 없는 시각을 지어내지 않고 날짜만 쓴다."""
    try:
        return datetime.strptime(rcept_dt, "%Y%m%d").strftime("%Y.%m.%d")
    except Exception:
        return rcept_dt


def _num(s):
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return None


def _eok(million_won):
    """DART는 백만원 단위로 준다 → 억원."""
    return f"{million_won / 100:,.0f}억"


def parse_earnings(txt):
    """잠정실적 본문에서 당해 분기 3개 지표(백만원). 표가 '당해실적 값 ...' 순서다."""
    out = {}
    for label, key in (("매출액", "revenue"), ("영업이익", "operating"), ("당기순이익", "net")):
        m = re.search(re.escape(label) + r"\s*당해실적\s*([\-0-9,]+)", txt)
        if m:
            out[key] = _num(m.group(1))
    return out


def parse_contract(txt):
    """공급계약 본문. 태그를 벗기면 라벨과 값이 한 줄로 이어지므로, 다음 라벨이나
    항목 번호("2. ")를 종결자로 쓴다. 공백은 이미 단일화돼 있어 연속공백은 못 쓴다."""
    out = {}
    m = re.search(r"체결계약명\s*(.+?)\s*\d+\.\s", txt)
    if m:
        out["name"] = m.group(1).strip()
    m = re.search(r"계약금액\(원\)\s*([\d,]+)", txt)
    if m:
        out["amount"] = m.group(1)
    m = re.search(r"매출액대비\(%\)\s*([\d.]+)", txt)
    if m:
        out["ratio"] = m.group(1)
    m = re.search(r"계약상대\s*(.+?)\s*-\s*회사와의\s*관계\s*(\S+)", txt)
    if m:
        out["party"] = m.group(1).strip()
        out["relation"] = m.group(2).strip()
    m = re.search(r"계약기간\s*시작일\s*([\d\-]+)\s*종료일\s*([\d\-]+)", txt)
    if m:
        out["period"] = f"{m.group(1)} ~ {m.group(2)}"
    return out


def build_earnings_msg(item, txt, cap, actual):
    fig = parse_earnings(txt)
    if not fig:
        return None
    label = actual[0][0] if actual else ""
    cons = load_consensus(label)

    lines = [f"🟠 <b>한화엔진 공시</b>", "",
             _fmt_date(item["rcept_dt"]),
             f"기업명: 한화엔진(시가총액: {cap}) A{STOCK_CODE}" if cap
             else f"기업명: 한화엔진 A{STOCK_CODE}",
             f"보고서명: {item['report_nm'].strip()}", ""]

    for i, (ko, key) in enumerate((("매출액", "revenue"), ("영업익", "operating"), ("순이익", "net"))):
        v = fig.get(key)
        if v is None:
            continue
        cell = _eok(v)
        est = _num(cons[i]) if cons and i < len(cons) and cons[i] else None
        if est:
            # 컨센서스는 억원 단위로 저장돼 있다
            diff = (v / 100 - est) / est * 100
            cell += f"(예상치 : {est:,.0f}억/ {diff:+.0f}%)"
        lines.append(f"{ko} : {cell}")

    if actual:
        lines += ["", "<b>최근 실적 추이</b>"]
        for lab, rev, op, net in actual[:5]:
            lines.append(f"{lab} {rev}억/ {op}억/ {net}억")

    lines += ["", f"공시링크: {DART_VIEW}{item['rcept_no']}"]
    return "\n".join(lines)


def build_contract_msg(item, txt, cap):
    c = parse_contract(txt)
    lines = [f"🟠 <b>한화엔진 공시</b>", "",
             _fmt_date(item["rcept_dt"]),
             f"기업명: 한화엔진(시가총액: {cap}) A{STOCK_CODE}" if cap
             else f"기업명: 한화엔진 A{STOCK_CODE}",
             f"보고서명: {item['report_nm'].strip()}", ""]
    if c.get("name"):
        lines.append(f"계약명 : {c['name']}")
    if c.get("amount"):
        amt = _num(c["amount"])
        if amt:
            tail = f" (최근매출액 대비 {c['ratio']}%)" if c.get("ratio") else ""
            lines.append(f"계약금액 : {amt / 1e8:,.0f}억{tail}")
    if c.get("party"):
        rel = f" · {c['relation']}" if c.get("relation") else ""
        lines.append(f"계약상대 : {c['party']}{rel}")
    if c.get("period"):
        lines.append(f"계약기간 : {c['period']}")
    lines += ["", f"공시링크: {DART_VIEW}{item['rcept_no']}"]
    return "\n".join(lines)


def main():
    key = _key()
    if not key:
        print("DART_API_KEY not set")
        _set_output(False)
        return

    now = datetime.now(KST)
    actual, consensus = naver_quarters()
    changed = save_consensus(consensus)
    print(f"consensus: {len(consensus)}건 {'(갱신)' if changed else '(변화 없음)'}")

    state = load_state()
    seen = set(state.get("alerted", []))
    items = fetch_disclosures(key, now)

    cap = None
    msgs = []
    for it in items:
        nm = it["report_nm"].strip()
        if not (EARNINGS in nm or CONTRACT in nm or STRUCTURE in nm):
            continue
        if it["rcept_no"] in seen:
            continue
        txt = fetch_document(key, it["rcept_no"])
        if not txt:
            continue                      # 본문을 못 읽으면 이력에 안 남겨 다음 회차에 재시도
        if cap is None:
            cap = naver_market_cap()
        m = (build_earnings_msg(it, txt, cap, actual)
             if EARNINGS in nm else build_contract_msg(it, txt, cap))
        if m:
            msgs.append(m)
            state["alerted"].append(it["rcept_no"])

    print(f"lookback={LOOKBACK_DAYS}d  fetched={len(items)}  new={len(msgs)}")
    for m in msgs:
        print("  -", m.splitlines()[4] if len(m.splitlines()) > 4 else m[:60])

    if msgs:
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n\n".join(msgs))
        save_state(state)
    _set_output(bool(msgs))

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"data_changed={'true' if (changed or msgs) else 'false'}\n")


if __name__ == "__main__":
    main()
