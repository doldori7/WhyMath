"""성장 증거 학생 대면 표면 — 금지 식별자 소스 스캔 게이트 (hermetic) (PED-08 acceptance ⑧).

`tests/backend/l1/test_anti_gamification_governance.py`의 단어-토큰화 매칭 기법(모듈 docstring
§Part A)을 그대로 답습한다 — 이 파일은 그 파일의 헬퍼(`_identifier_words`·
`_contains_word_sequence`·정규식·`_compose()` 자기회피 조합)를 *재구현*한다(모듈-private이라
import 불가). 스캔 범위도 동일(`api/`·`schema/`) — 그 파일이 이미 검증한 스코프를 그대로
재사용한다(더 좁은 스코프를 새로 발명하지 않는다).

금지 대상 4종(PED-08 태스크 설계 명시):
  - `help_reduction_validated` — R15 결합 판정 원본 필드명. 서빙 층 응답 모델에 이 필드가
    있으면 학생이 원시 판정(GAMING_SUSPECT 포함)에 접근할 길이 열린다.
  - `GAMING_SUSPECT` — 낙인 라벨 리터럴. 계약 모듈의 `suppressed_reason` 원문에 등장하지만
    서빙 층(`api/me.py`)은 이를 절대 그대로 전달하지 않아야 한다(랜드마인 방어).
  - `diagnosis_agreement_rate`(②)·`tokens_per_turn`(④) — INTERNAL_ONLY 2종. 구조적 배제
    (스키마에 필드 자체가 없음)를 소스 스캔으로 동결한다.

양방향 변별력 실측(정밀도 회귀 + 진짜 위반 탐지)을 둘 다 갖춘다 — 특히
`help_reduction_slope`(⑤ — 학생 대면 정당 필드)는 금지 시퀀스 `help_reduction_validated`와
앞 두 단어("help"+"reduction")를 공유하고 세 번째 단어("slope" vs "validated")에서만
갈라지는 최고난도 정밀도 케이스라 전용 회귀 고정핀을 둔다(태스크 설계 명시).

hermetic: DB 불요(순수 파일시스템 텍스트 스캔).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = _REPO_ROOT / "src" / "backend" / "whymath_backend"

# `test_anti_gamification_governance.py`와 동일 스코프 재사용(§ 모듈 docstring) — api/** 전체 +
# schema/** 최상위 응답 모델.
_STUDENT_FACING_DIRS: tuple[Path, ...] = (
    _BACKEND_ROOT / "api",
    _BACKEND_ROOT / "schema",
)

# 게이트 무력화 방지 — 경로 오타로 0건 통과되는 사고 차단(참조 파일과 동일 하한 채택).
_MIN_STUDENT_FACING_FILES = 10


def _compose(*parts: str) -> str:
    """조각을 이어붙여 리터럴 문자열을 만든다 — 게이트 자기회피 조합 기법.

    이 파일 자체가 스캔 대상(`api/`·`schema/`) 바깥(`tests/`)에 있어 구조적으로 자기
    자신을 스캔하지 않지만, 금지 어근을 파일에 그대로 나열하지 않는 위생 관례를 따른다
    (`test_anti_gamification_governance.py`·`test_subject_neutrality_gate.py` 선례).
    """
    return "".join(parts)


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _student_facing_py_files() -> list[Path]:
    files: list[Path] = []
    for d in _STUDENT_FACING_DIRS:
        files.extend(_iter_py_files(d))
    return files


# ──────────────────────────────────────────────────────────────────────────
# 단어-토큰화 매칭 재구현 — `test_anti_gamification_governance.py` §Part A 기법 그대로.
# `\b`만으로는 snake_case 밑줄 내부 경계를 못 잡는다(그 파일의 실측 로그 참조) — 식별자를
# snake_case+camelCase 단어 단위로 분해한 뒤 "연속 단어열" 부분열 매칭으로 정밀 판정한다.
# ──────────────────────────────────────────────────────────────────────────
_IDENTIFIER_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# 참조 파일(`test_anti_gamification_governance.py`)의 `[A-Za-z][a-z0-9]*`는 camelCase/
# PascalCase만 겨냥해 만들어졌다 — `GAMING_SUSPECT`처럼 청크 자체가 전부 대문자인
# SCREAMING_SNAKE 토큰을 넣으면 대문자 하나하나가 개별 "단어"로 쪼개지는 결함이 있다(실측:
# 이 파일 작성 중 `_GAMING_SUSPECT_LABEL` 참양성 케이스가 이 결함으로 거짓 음성 처리됨 —
# 아래 세 대안 중 "전부 대문자 연속" 분기를 추가해 해결). `(?![a-z])` 부정 후읽기로 "다음이
# 소문자가 아니면 대문자런 전체를 한 단어로 묶는다"를 표현한다(`HTTPServer`류 안전장치 겸용
# — 이 파일 대상 토큰엔 해당 사례가 없지만 회귀 방지로 유지).
_CAMEL_WORD_PATTERN = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")


def _identifier_words(identifier: str) -> list[str]:
    """식별자를 snake_case로 우선 분해하고 각 조각을 camelCase로 추가 분해 → 소문자 단어열."""
    words: list[str] = []
    for chunk in identifier.split("_"):
        if not chunk:
            continue
        camel_words = _CAMEL_WORD_PATTERN.findall(chunk)
        if camel_words:
            words.extend(w.lower() for w in camel_words)
        else:
            words.append(chunk.lower())
    return words


def _contains_word_sequence(words: list[str], sequence: tuple[frozenset[str], ...]) -> bool:
    """`words`에 `sequence`(위치별 허용 단어 집합)가 연속 부분열로 등장하는지."""
    n = len(sequence)
    if n == 0 or len(words) < n:
        return False
    return any(
        all(words[i + j] in sequence[j] for j in range(n)) for i in range(len(words) - n + 1)
    )


# 금지 어근 — bare 단어가 아니라 항상 접미어와 결합해서만 매치되도록 위치별 시퀀스로 정의
# (PED-08 태스크 설계에 명시된 4종 그대로).
_GAMING = _compose("gaming")
_SUSPECT = _compose("sus", "pect")
_HELP = _compose("help")
_REDUCTION = _compose("reduc", "tion")
_VALIDATED = _compose("valid", "ated")
_DIAGNOSIS = _compose("diag", "nosis")
_AGREEMENT = _compose("agree", "ment")
_RATE = _compose("rate")
_TOKENS = _compose("to", "kens")
_PER = _compose("per")
_TURN = _compose("turn")

_FORBIDDEN_WORD_SEQUENCES: dict[str, tuple[frozenset[str], ...]] = {
    "help_reduction_validated": (
        frozenset({_HELP}),
        frozenset({_REDUCTION}),
        frozenset({_VALIDATED}),
    ),
    "GAMING_SUSPECT": (frozenset({_GAMING}), frozenset({_SUSPECT})),
    "diagnosis_agreement_rate": (
        frozenset({_DIAGNOSIS}),
        frozenset({_AGREEMENT}),
        frozenset({_RATE}),
    ),
    "tokens_per_turn": (frozenset({_TOKENS}), frozenset({_PER}), frozenset({_TURN})),
}


def _text_offending_labels(text: str) -> set[str]:
    """텍스트(파일 전체 또는 단일 식별자)에서 발견된 금지 라벨 집합."""
    found: set[str] = set()
    remaining = set(_FORBIDDEN_WORD_SEQUENCES) - found
    if not remaining:
        return found
    for token in _IDENTIFIER_TOKEN_PATTERN.findall(text):
        words = _identifier_words(token)
        if not words:
            continue
        for label in list(remaining):
            if _contains_word_sequence(words, _FORBIDDEN_WORD_SEQUENCES[label]):
                found.add(label)
                remaining.discard(label)
        if not remaining:
            break
    return found


# 정밀도 회귀 안전망 — 정당 식별자가 오탐되지 않아야 한다. `help_reduction_slope`가 핵심
# 케이스(태스크 설계 명시 — help_reduction_validated와 처음 두 단어를 공유).
_BENIGN_IDENTIFIERS_MUST_NOT_MATCH: tuple[str, ...] = (
    "help_reduction_slope",
    "growth_evidence",
    "GrowthEvidenceResponse",
    "exposable_now",
    "suppressed_reason",
    "narrate_calibration_brier",
    "classify_metric_exposure",
    "calibration_brier",
    "hint_depth_reached",
)

# 변별력 회귀 고정핀 — 실제 위반 식별자는 반드시 걸린다(태스크 설계에 명시된 주입 예시).
_TRUE_POSITIVE_IDENTIFIERS_MUST_MATCH: dict[str, str] = {
    "_leak_help_reduction_validated": "help_reduction_validated",
    "_GAMING_SUSPECT_LABEL": "GAMING_SUSPECT",
    "diagnosis_agreement_rate_field": "diagnosis_agreement_rate",
    "tokens_per_turn_value": "tokens_per_turn",
}


class TestForbiddenIdentifierSourceScan:
    """학생 대면 표면(api/**·schema/**)에 금지 식별자 4종이 유입되지 않는다."""

    def test_scan_scope_not_empty(self) -> None:
        """게이트 무력화 방지 — 스캔 파일 수가 하한 이상(경로 오타로 0건 '통과' 위장 차단)."""
        files = _student_facing_py_files()
        assert len(files) >= _MIN_STUDENT_FACING_FILES, (
            f"스캔 대상 파일이 {len(files)}건뿐 — 경로 오타로 게이트가 무력화됐을 위험 "
            f"(scanned dirs: {[str(d) for d in _STUDENT_FACING_DIRS]})"
        )

    @pytest.mark.parametrize("label", sorted(_FORBIDDEN_WORD_SEQUENCES))
    def test_no_forbidden_identifier_in_student_facing_surface(self, label: str) -> None:
        offenders = [
            str(path.relative_to(_REPO_ROOT))
            for path in _student_facing_py_files()
            if label in _text_offending_labels(path.read_text(encoding="utf-8"))
        ]
        assert not offenders, (
            f"금지 식별자 '{label}' 유입: {offenders} — PED-08 성장 증거 노출 계약 위반 의심"
            "(GAMING_SUSPECT는 어떤 형태로도 필드가 되지 않아야 하고, help_reduction_validated·"
            "diagnosis_agreement_rate·tokens_per_turn은 서빙 층 응답 모델 필드로 재등장하면 "
            "안 된다)."
        )

    @pytest.mark.parametrize("identifier", _BENIGN_IDENTIFIERS_MUST_NOT_MATCH)
    def test_precision_benign_identifiers_are_not_flagged(self, identifier: str) -> None:
        """정밀도 회귀 안전망 — 정당 식별자가 어떤 금지 패턴에도 걸리지 않는다(오탐 방지).

        `help_reduction_slope`가 핵심 케이스 — `help_reduction_validated`와 앞 두 단어를
        공유하지만 세 번째 단어에서 갈라지므로 위치별 매칭이 정확히 이를 구분해야 한다.
        """
        offending_labels = _text_offending_labels(identifier)
        assert (
            not offending_labels
        ), f"'{identifier}'가 {offending_labels} 패턴에 오탐됨 — 정밀도 원칙 위반"

    @pytest.mark.parametrize("identifier", sorted(_TRUE_POSITIVE_IDENTIFIERS_MUST_MATCH))
    def test_variance_true_positive_identifiers_are_flagged(self, identifier: str) -> None:
        """변별력 회귀 고정핀 — 실제 위반 식별자는 반드시 걸린다(함수 레벨 직접 호출)."""
        expected_label = _TRUE_POSITIVE_IDENTIFIERS_MUST_MATCH[identifier]
        assert expected_label in _text_offending_labels(identifier), (
            f"'{identifier}'가 '{expected_label}'로 탐지되지 않음 — 변별력 회귀"
        )

    def test_help_reduction_slope_precision_regression_pin(self) -> None:
        """전용 회귀 고정핀(태스크 설계 명시) — 최고난도 정밀도 케이스를 별도 단정으로 고정."""
        offending = _text_offending_labels("help_reduction_slope")
        assert "help_reduction_validated" not in offending, (
            "'help_reduction_slope'가 'help_reduction_validated'로 오탐됨 — 위치별 매칭이 "
            "3번째 단어(slope vs validated)에서 갈라지지 못했다."
        )
