"""
알람 주간 점검 — 일요일마다 지난 7일간 알람 워크플로가 실제로 일했는지 텔레그램 1통.

왜: 알람이 조용히 죽어도 Actions는 "성공"이었다. 매크로 CPI는 2026-05-31부터
다섯 달 동안 매번 조회에 실패했고(로그에만 남음), 한화 뉴스는 09-11~10-10 한 달간
발송 0건이었다. 둘 다 실행 결과만 봐서는 안 보인다 — 실행 횟수, 수집, 발송을
같이 봐야 한다.

임계값으로 경보를 내지 않는다(근거 없는 기준을 만들지 않으려고). 숫자를 보여주고
판단은 사람이 한다. ⚠️는 사실만 표시한다: 실패한 실행, 실행 0회, 수집 0, 한 주 매칭 0, 조회 실패.

데이터는 전부 GitHub Actions API(실행 목록, 단계 결과, 로그)에서 읽는다 — 레인
코드는 건드리지 않는다. 로그 문구는 각 스크립트의 print와 맞물려 있어, 못 읽으면
'?'로 표시하고 계속 간다.

실행: python scripts/weekly_health.py [--dry-run] [--end YYYY-MM-DD]
  GITHUB_TOKEN(actions:read), GITHUB_REPOSITORY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import io
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone

import requests

KST = timezone(timedelta(hours=9))
API = "https://api.github.com"
WF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".github", "workflows")

# (워크플로 파일, 종류). 종류가 로그에서 무엇을 읽을지 정한다.
LANES = [
    ("nvidia_news_monitor.yml", "news"),
    ("pltr_news_monitor.yml", "news"),
    ("hanwha_news_monitor.yml", "news"),
    ("hanwha_dart_monitor.yml", "dart"),
    ("macro_monitor.yml", "macro"),
    ("market_snapshot.yml", "snapshot"),
    ("market_check.yml", "check"),
]

NEWS_RE = re.compile(r"window=[\d.]+h\s+fetched=(\d+)\s+matched=(\d+)")
NO_ITEMS = "no items fetched"
DART_RE = re.compile(r"lookback=\d+d\s+fetched=(\d+)\s+new=(\d+)")
YIELD_RE = re.compile(r"10Y Yield : ([\d.]+|None)%")
CPI_RE = re.compile(r"Core Sticky CPI[^:]*: ([\d.]+|None)%\s+date: (\S+)")
SNAP_RE = re.compile(r"\s(\d+)/(\d+) ok\s")   # 뒤 환율 표기는 10-02에 바뀜
CHECK_RE = re.compile(r"(\d+)개 종목 중 (\d+)개 정상")


def _session():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                      "Accept": "application/vnd.github+json"})
    return s


def _field_match(v, spec, lo):
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, step = part.split("/")
            step = int(step)
        if part == "*":
            a, b = lo, 10 ** 6
        elif "-" in part:
            a, b = map(int, part.split("-"))
        else:
            a = b = int(part)
        if a <= v <= b and (v - a) % step == 0:
            return True
    return False


def expected_runs(wf_file, start, end):
    """워크플로 파일의 cron으로 [start, end) 사이 예약 횟수를 센다(분 단위 전수, UTC)."""
    with open(os.path.join(WF_DIR, wf_file), encoding="utf-8") as f:
        crons = re.findall(r"cron:\s*'([^']+)'", f.read())
    n, t = 0, start.astimezone(timezone.utc).replace(second=0, microsecond=0)
    end = end.astimezone(timezone.utc)
    while t < end:
        dow = (t.weekday() + 1) % 7   # cron: 일=0
        for c in crons:
            mi, h, dom, mo, wd = c.split()
            if (_field_match(t.minute, mi, 0) and _field_match(t.hour, h, 0)
                    and _field_match(t.day, dom, 1) and _field_match(t.month, mo, 1)
                    and _field_match(dow, wd, 0)):
                n += 1
                break
        t += timedelta(minutes=1)
    return n


def list_runs(s, repo, wf_file, start, end):
    runs, page = [], 1
    while True:
        r = s.get(f"{API}/repos/{repo}/actions/workflows/{wf_file}/runs",
                  params={"created": f"{start.isoformat()}..{end.isoformat()}",
                          "per_page": 100, "page": page}, timeout=30)
        r.raise_for_status()
        batch = r.json()["workflow_runs"]
        runs += batch
        if len(batch) < 100:
            return runs
        page += 1


def run_log(s, repo, run_id):
    """실행 로그 전체(텍스트). 못 받으면 ''."""
    try:
        r = s.get(f"{API}/repos/{repo}/actions/runs/{run_id}/logs", timeout=60)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        return "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist()
                         if "/" not in n)   # 최상위 = 잡 전체 로그(단계별 파일과 중복 제외)
    except Exception as e:
        print(f"  log {run_id}: {e}")
        return ""


def telegram_sent(s, repo, run_id):
    """Telegram 단계가 실제로 돌아 성공했나."""
    r = s.get(f"{API}/repos/{repo}/actions/runs/{run_id}/jobs", timeout=30)
    r.raise_for_status()
    for job in r.json()["jobs"]:
        for st in job["steps"]:
            if st["name"].startswith("Telegram") and st["conclusion"] == "success":
                return True
    return False


def _kst(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST)


def summarize(s, repo, wf_file, kind, start, end):
    runs = [r for r in list_runs(s, repo, wf_file, start, end) if r["status"] == "completed"]
    sched = [r for r in runs if r["event"] == "schedule"]
    bad = [r for r in runs if r["conclusion"] != "success"]
    exp = expected_runs(wf_file, start, end)
    warn = bool(bad) or not sched
    parts = [f"정기 {len(sched)}/{exp}회"]
    if bad:
        parts.append(f"실패 {len(bad)}")
    if len(sched) > 1:
        ts = sorted(_kst(r["created_at"]) for r in sched)
        gap = max((b - a).total_seconds() / 3600 for a, b in zip(ts, ts[1:]))
        if kind == "dart":
            parts.append(f"최대 간격 {gap:.0f}h")
    # 값은 정기 실행 로그에서 읽는다 — 수동 실행(test_mode 등)은 형식이 다르다.
    latest = max(sched or runs, key=lambda r: r["created_at"]) if runs else None

    if kind == "news":
        fetched, matched, unread, sends = [], [], 0, 0
        for r in sched:
            log = run_log(s, repo, r["id"])
            m = NEWS_RE.search(log)
            if m:
                fetched.append(int(m.group(1)))
                matched.append(int(m.group(2)))
            elif NO_ITEMS in log:
                fetched.append(0)
                matched.append(0)
            else:
                unread += 1
            sends += telegram_sent(s, repo, r["id"])
        if fetched:
            parts.append(f"수집 {min(fetched)}~{max(fetched)}")
            parts.append(f"매칭 {sum(matched)}")
            # 수집 0 또는 한 주 매칭 0 — 한화 뉴스가 한 달간 이 상태로 죽어 있었다.
            warn |= min(fetched) == 0 or sum(matched) == 0
        parts.append(f"발송 {sends}일")
        if unread:
            parts.append(f"로그 ? {unread}")
    elif kind == "dart":
        sends = sum(telegram_sent(s, repo, r["id"]) for r in runs)
        parts.append(f"발송 {sends}회")
    elif kind in ("macro", "snapshot", "check") and latest:
        log = run_log(s, repo, latest["id"])
        if kind == "macro":
            y, c = YIELD_RE.search(log), CPI_RE.search(log)
            yv = y.group(1) if y else "?"
            cv, cd = (c.group(1), c.group(2)[:7]) if c else ("?", "")
            parts.append(f"금리 {yv}%")
            parts.append(f"CPI {cv}%" + (f"({cd})" if cd and cd != "None" else ""))
            warn |= "None" in (yv, cv) or "?" in (yv, cv)
        elif kind == "snapshot":
            m = SNAP_RE.search(log)
            parts.append(f"종목 {m.group(1)}/{m.group(2)} 정상" if m else "종목 ?")
            warn |= not m or m.group(1) != m.group(2)
        else:
            m = CHECK_RE.search(log)
            parts.append(f"종목 {m.group(2)}/{m.group(1)} 정상" if m else "종목 ?")
            warn |= not m
    if latest:
        parts.append(f"마지막 {_kst(latest['created_at']):%m-%d %H:%M}")
    return warn, " · ".join(parts)


def build(repo, start, end):
    s = _session()
    names = {}
    r = s.get(f"{API}/repos/{repo}/actions/workflows", timeout=30)
    r.raise_for_status()
    for w in r.json()["workflows"]:
        names[os.path.basename(w["path"])] = (w["name"], w["state"])
    lines = [f"🩺 <b>알람 주간 점검</b>", "",
             f"⏰ {start.astimezone(KST):%m-%d} ~ {(end - timedelta(seconds=1)).astimezone(KST):%m-%d} KST", ""]
    nwarn = 0
    for wf, kind in LANES:
        name, state = names.get(wf, (wf, "missing"))
        if state != "active":
            warn, text = True, f"워크플로 상태 {state}"
        else:
            try:
                warn, text = summarize(s, repo, wf, kind, start, end)
            except Exception as e:   # 한 레인을 못 읽어도 보고는 나간다
                warn, text = True, f"점검 실패 ({type(e).__name__})"
        nwarn += warn
        lines.append(f"{'⚠️ ' if warn else ''}<b>{name}</b>")
        lines.append(f"   {text}")
    lines += ["", f"⚠️ {nwarn}개 — Actions 로그 확인" if nwarn else "✅ 실패, 실행 0회, 수집이나 매칭 0, 조회 실패 없음"]
    return "\n".join(lines)


def send(msg):
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": msg,
                            "parse_mode": "HTML", "disable_web_page_preview": True},
                      timeout=15)
    if not r.ok:
        print(f"telegram failed: {r.status_code} {r.text[:200]}")
        sys.exit(1)


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    end = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    if "--end" in args:
        end = datetime.fromisoformat(args[args.index("--end") + 1]).replace(tzinfo=KST)
    start = end - timedelta(days=7)
    msg = build(os.environ["GITHUB_REPOSITORY"], start, end)
    print(msg)
    if not dry:
        send(msg)


if __name__ == "__main__":
    main()
