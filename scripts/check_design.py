"""DESIGN.md 규칙을 app.py에 대해 검사한다. 표준 라이브러리만 사용.

문서만으로는 규칙이 안 지켜진다 — 2026-08-17 전역 `p{color:#606060}`가 대비 3.18:1로
탭·토글 텍스트까지 덮어쓴 채 오래 살아남았던 게 그 증거. 이 스크립트는 그런 회귀를
커밋 전에 잡기 위한 것.

항상 통과하는 검사기는 무의미하다: 지금도 남은 부채(Group B 회색, 빨강 3종 중복 등)를
"미등록 색상"으로 그대로 보여준다. DESIGN.md의 "알려진 위반" 절과 이 출력을 대조해서
새로 생긴 게 아니면 넘어가도 된다 — 다만 새 hex가 뜨면 반드시 DESIGN.md를 먼저 고칠 것.

사용법: python scripts/check_design.py
"""

import io
import re
import sys
from pathlib import Path

# Windows 콘솔 기본 cp949는 —·⚠ 같은 유니코드를 못 뱉는다. stdout을 UTF-8로 강제.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

APP_PY = Path(__file__).resolve().parent.parent / "app.py"
PAGE_BG = "#080808"
AA_MIN_CONTRAST = 4.5

# ── DESIGN.md와 동기화할 것 ──────────────────────────────────────────────
NEUTRALS = {
    "#080808", "#0e0e0e", "#14161a", "#20242b",
    "#1a1a1a", "#2a2d33",
    "#828a94", "#9aa3b0", "#c3c9d1", "#f0f1ef",
}
SEMANTIC = {
    "#76b900", "#c87f00", "#5a9e3a", "#e05656",  # 상태
    "#4a90d9", "#9370d8", "#22c55e", "#6366f1", "#8b949e",  # 분류(배지·13F)
}
# 데이터 시각화 팔레트 — DESIGN.md 예외 조항: UI 크롬 유출만 아니면 허용
DATAVIZ = {
    "#a3e635", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899",
    "#14b8a6", "#a855f7", "#60a5fa",
}
# 배지 틴트 짝(badge tint pair) — SEMANTIC 색을 18% 알파 배경으로 쓸 때 그 위에서
# 읽히는 밝은 글자색. 중복이 아니라 SEMANTIC 각 항목의 필수 짝꿍(DESIGN.md 참고).
BADGE_TINTS = {"#4ade80", "#7ab8f5", "#f08a8a", "#a5a8f5", "#b0b8c2"}
ALLOWED_HEX = NEUTRALS | SEMANTIC | DATAVIZ | BADGE_TINTS

ALLOWED_RADII = {"3px", "6px", "10px"}
MAX_WEIGHT = 600


def to6(h: str) -> str:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.lower()


def _lin(c: int) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hexcolor: str) -> float:
    h = to6(hexcolor).lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg: str, bg: str = PAGE_BG) -> float:
    la, lb = _luminance(fg), _luminance(bg)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def main() -> int:
    src = APP_PY.read_text(encoding="utf-8")
    problems = []

    # 1) 미등록 색상 (표에 없는 hex)
    # &#9670; 같은 HTML 엔티티(◆ 등)는 CSS hex가 아니므로 '&' 뒤 매치는 제외
    all_hex = {to6(h) for h in re.findall(r"(?<!&)#[0-9a-fA-F]{3,6}\b", src)
               if len(h) - 1 in (3, 6)}
    unregistered = sorted(all_hex - ALLOWED_HEX)
    if unregistered:
        problems.append(
            f"[미등록 색상] {len(unregistered)}종 — DESIGN.md에 없음. "
            f"의도된 값이면 표를 먼저 고칠 것:\n    " + " ".join(unregistered)
        )

    # 2) 텍스트 대비 (color: 선언만, background-color/border-color 제외)
    text_colors = set(re.findall(r"(?<![-a-zA-Z])color:\s*(#[0-9a-fA-F]{3,6})\b", src))
    low_contrast = sorted(
        (h, contrast(h)) for h in text_colors if contrast(h) < AA_MIN_CONTRAST
    )
    if low_contrast:
        lines = "\n".join(f"    {h}  {r}:1" for h, r in low_contrast)
        problems.append(
            f"[대비 미달] {len(low_contrast)}건 — 페이지 배경(#080808) 기준 {AA_MIN_CONTRAST}:1 미만.\n"
            f"    밝은 배경 위 글자나 N/A 표시 관용구라면 DESIGN.md 예외 조항 확인 후 무시:\n{lines}"
        )

    # 3) font-weight 700 이상
    weights = re.findall(r"font-weight:\s*(\d+)", src)
    heavy = sorted({int(w) for w in weights if int(w) > MAX_WEIGHT})
    if heavy:
        problems.append(f"[굵기 위반] font-weight {heavy} 발견 — 최대 {MAX_WEIGHT}")

    # 4) 반경 스케일 밖 값
    radii = set(re.findall(r"border-radius:\s*(\d+px)", src))
    bad_radii = sorted(radii - ALLOWED_RADII)
    if bad_radii:
        problems.append(f"[반경 위반] {bad_radii} — 허용값 {sorted(ALLOWED_RADII)}만 사용")

    # 5) 캡슐(半-height) 힌트 — radius가 padding 높이의 절반 이상으로 보이는 큰 값
    capsule_like = re.findall(r"border-radius:\s*(1[2-9]\d?px|[2-9]\d\dpx)", src)
    if capsule_like:
        problems.append(f"[캡슐 의심] border-radius {sorted(set(capsule_like))} — 2차 이하 컨트롤 금지 대상인지 확인")

    if not problems:
        print("PASS — 위반 없음")
        return 0

    print(f"{len(problems)}개 항목 발견:\n")
    for p in problems:
        print(p, "\n")
    print("DESIGN.md의 '알려진 위반' 절과 대조: 이미 기록된 부채면 무시, 새 항목이면 먼저 문서화할 것.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
