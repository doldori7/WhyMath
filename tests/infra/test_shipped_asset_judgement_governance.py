"""[ARCH-27] 출하 자산(assets) 수학판정 로직 거버넌스 게이트 — Dart/웹 소스 게이트 사각 봉합.

왜 이 테스트가 있는가
--------------------
기존 두 무-수학판정 게이트는 *소스*만 본다:
  · Dart: src/mobile/test/governance/no_math_logic_governance_test.dart — `lib/**.dart`만
  · 웹:   src/web/graphing-calculator/test/no_math_judgement_governance.test.js — `src/**`만
어느 쪽도 **학생 실기기로 출하되는 최종 산출물**(`src/mobile/assets/**/*.js`)을 보지 않는다.
이 산출물은 웹 계산기를 `npm run build`한 뒤 `tool/sync_graphing_calculator.sh`로 vendored
커밋한 것이라, 소스 게이트가 green이어도 과거 빌드에 담겼던 판정 로직이 자산에 그대로 남을
수 있다 — 실제로 그랬다(ARCH-27 실측): QuizMode의 클라 채점 `sameGraph`·오개념 진단
`diagnose`·정답공개 `giveUp`·점수누적 `quiz_history`가 학생 실기기까지 도달했는데도 두 소스
게이트는 계속 green이었다(functional_security_audit_2026-08-08.md H3).

minification 함정(이 게이트의 설계를 결정한 제약)
------------------------------------------------
출하 자산은 Vite가 minify한다. `sameGraph`·`diagnose`·`checkAnswer` 같은 **식별자는 renaming
으로 사라진다**(실측: ARCH-27 제거 전 번들에서 이미 전부 0건이었다). 반면 **문자열 리터럴은
생존한다** — localStorage 키(`"quiz_history"`)·한국어 UI 문구(`"그래프 맞히기"` 등)는
minifier가 값을 보존해야 하므로 그대로 남는다. 그래서 이 게이트의 실효 판정 근거는
카테고리 A(문자열 리터럴)이고, 카테고리 B(식별자)는 향후 미압축/디버그 자산이 섞여 들어올
경우에 대비한 방어선 2일 뿐이다 — 실 출하 번들에 대해서는 카테고리 A만이 변별력을 갖는다
("성공/실패 양쪽에서 같은 값을 내는 검사는 검증이 아니다" — CLAUDE.md).

검증 계약
--------
① 실 저장소의 출하 자산(`src/mobile/assets/**/*.js`)에 판정 심볼이 없다(현재 0건 —
   ARCH-27이 QuizMode를 소스에서 제거하고 번들을 재빌드·재동기화해 상환)
② 스캔 대상이 비어 있지 않다(자산 이동·개명 시 공허한 green 차단)
③ 파서가 위장하지 않는다 — 자산 디렉터리 자체가 없으면 "위반 0 통과"가 아니라 실패
④ 변별력 — 결함주입으로 실제 검출되는지 확인(양성 대조 + minified 스타일로 위장한 식별자도
   문자열 앵커로는 여전히 검출됨을 실증 — 카테고리 A와 B의 차이를 자동화된 반증으로 고정)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ASSETS_DIR = _REPO_ROOT / "src" / "mobile" / "assets"

# 카테고리 A — minification 생존 문자열(주 판정 근거·실제 출하 번들에 유효).
# localStorage 키·QuizMode 고유 한국어 UI 문구만 앵커로 쓴다("문제"·"정답" 같은 흔한 단어는
# 오탐 위험이 커 제외 — 정밀 문구만 채택).
_STRING_LITERAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("localStorage 키: quiz_history(점수 이력)", re.compile(r"quiz_history")),
    ("UI 문구: 그래프 맞히기(QuizMode 헤더)", re.compile(r"그래프 맞히기")),
    ("UI 문구: 정답 보기(giveUp 버튼)", re.compile(r"정답 보기")),
    ("UI 문구: 채점하기(checkAnswer 버튼)", re.compile(r"채점하기")),
    ("UI 문구: 당신의 답(diagnose 오개념 진단 출력)", re.compile(r"당신의 답")),
)

# 카테고리 B — 식별자 패턴(방어선 2). 실 출하 번들은 minify돼 이 카테고리는 0건이 정상이다
# (renaming으로 사라짐) — 미압축/디버그 자산 유입에 대비한 것이지 이 게이트의 실효
# 방어선은 카테고리 A다. Dart/웹 소스 게이트의 금지 목록과 의도적으로 대응시켰다.
_IDENTIFIER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("식별자: sameGraph(채점)", re.compile(r"\bsameGraph\s*[(=]")),
    ("식별자: checkAnswer(", re.compile(r"\bcheckAnswer\w*\s*\(")),
    ("식별자: gradeAnswer(", re.compile(r"\bgradeAnswer\w*\s*\(")),
    ("식별자: diagnoseMisconception(", re.compile(r"\bdiagnoseMisconception\s*\(")),
)

_ALL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    _STRING_LITERAL_PATTERNS + _IDENTIFIER_PATTERNS
)


def _walk_js_files(root: Path) -> list[Path]:
    """`root` 하위 모든 `.js` 파일을 정렬해 돌려준다.

    디렉터리 자체가 없으면 조용히 빈 리스트(=위반 0 위장)가 아니라 예외로 실패한다.
    """
    if not root.is_dir():
        raise AssertionError(f"{root} 이(가) 없다 — 출하 자산을 스캔할 수 없다.")
    return sorted(root.rglob("*.js"))


def _scan_for_judgement_symbols(
    files: list[Path],
    patterns: tuple[tuple[str, re.Pattern[str]], ...] = _ALL_PATTERNS,
) -> dict[str, list[str]]:
    """파일별로 매치된 판정 패턴 이름 목록을 돌려준다(매치 0건인 파일은 결과에서 제외)."""
    violations: dict[str, list[str]] = {}
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = [name for name, pattern in patterns if pattern.search(text)]
        if hits:
            violations[str(path)] = hits
    return violations


def test_scan_target_is_not_empty() -> None:
    """계약 ② — 실 저장소 출하 자산 스캔 대상이 비어 있지 않다(게이트 무력화 방지)."""
    files = _walk_js_files(_ASSETS_DIR)
    assert len(files) > 3, (
        f"src/mobile/assets 하위 .js 파일이 {len(files)}건뿐 — 자산 경로가 바뀌었거나 "
        "게이트가 빈 디렉터리를 스캔하고 있다(공허한 green 위험)."
    )


def test_shipped_assets_have_no_judgement_symbols() -> None:
    """계약 ① — 실 저장소 출하 자산에 판정 심볼이 없다(ARCH-27 QuizMode 제거로 0건 상환)."""
    files = _walk_js_files(_ASSETS_DIR)
    violations = _scan_for_judgement_symbols(files)
    assert violations == {}, (
        "출하 자산(학생 실기기로 배포되는 .js)에 수학 판정 로직 심볼이 있다 — "
        "CLAUDE.md 슬89(수학 판정 단일 권위=백엔드 L3) 위반. "
        f"위반 파일: {violations}"
    )


def test_parser_fails_loudly_when_assets_dir_missing(tmp_path: Path) -> None:
    """계약 ③ — 자산 디렉터리 자체가 없으면 위반 0으로 위장하지 않고 예외."""
    missing = tmp_path / "does_not_exist"
    with pytest.raises(AssertionError, match="없다"):
        _walk_js_files(missing)


def test_control_clean_bundle_passes(tmp_path: Path) -> None:
    """계약 ④(양성 대조) — 판정 로직이 없는 정상 렌더 코드는 위반 0."""
    clean = tmp_path / "index-ABC123.js"
    clean.write_text(
        "function render(spec){var c=document.getElementById('c');c.width=spec.w;}",
        encoding="utf-8",
    )
    assert _scan_for_judgement_symbols([clean]) == {}


def test_defect_minified_localstorage_key_is_detected(tmp_path: Path) -> None:
    """계약 ④ — minify돼 식별자가 사라져도 localStorage 키 문자열은 검출된다.

    실측(ARCH-27): 제거 전 번들에서 `sameGraph`·`diagnose`·`checkAnswer` 식별자는 renaming
    으로 0건이었지만 `quiz_history` 문자열 리터럴은 생존했다. 이 테스트는 그 생존 앵커가
    실제로 변별력을 갖는지 재현한다 — 식별자를 한 글자로 압축한 minified 스타일 코드에서도
    문자열 앵커만으로 검출돼야 한다(카테고리 B는 이 케이스를 못 잡는다 — 아래 대비 확인).
    """
    minified = tmp_path / "index-XYZ789.js"
    minified.write_text(
        'function t(e,n){localStorage.setItem("quiz_history",JSON.stringify(n))}',
        encoding="utf-8",
    )
    all_violations = _scan_for_judgement_symbols([minified])
    assert all_violations, "minified 코드의 quiz_history 문자열 리터럴이 검출되지 않았다."
    assert any("quiz_history" in name for name in all_violations[str(minified)])
    # 카테고리 B(식별자)만으로는 이 minified 케이스를 못 잡는다 — 문자열 앵커(카테고리 A)가
    # 왜 필요한지의 직접 증거.
    identifier_only = _scan_for_judgement_symbols([minified], patterns=_IDENTIFIER_PATTERNS)
    assert identifier_only == {}, "식별자 renaming 후엔 카테고리 B가 무력함을 확인하는 대조군."


def test_defect_korean_ui_string_is_detected(tmp_path: Path) -> None:
    """계약 ④ — QuizMode 고유 한국어 UI 문구가 출하 자산에 재유입되면 검출된다."""
    reintroduced = tmp_path / "index-NEW999.js"
    reintroduced.write_text('React.createElement("span",null,"그래프 맞히기")', encoding="utf-8")
    violations = _scan_for_judgement_symbols([reintroduced])
    assert violations
    assert any("그래프 맞히기" in name for name in violations[str(reintroduced)])


def test_defect_raw_identifier_is_detected(tmp_path: Path) -> None:
    """계약 ④ — 방어선 2(카테고리 B) — 미압축 자산에 판정 함수가 섞이면 검출된다."""
    unminified = tmp_path / "debug.js"
    unminified.write_text(
        "function checkAnswer(expr1, expr2) { return sameGraph(expr1, expr2); }",
        encoding="utf-8",
    )
    violations = _scan_for_judgement_symbols([unminified])
    assert violations
    assert len(violations[str(unminified)]) >= 2  # checkAnswer( + sameGraph 둘 다 검출
