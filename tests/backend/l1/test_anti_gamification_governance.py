"""반게임화(anti-gamification) 헌법 불변식 — Python 소스 스캔 + 값·writer 동결 게이트.

배경: WhyMath는 "우열을 게임화(XP·배지·레벨업·퀘스트·streak·리더보드·콤보·코인 계열)로 매기지
않는다"가 헌법상 하드 제약이다(`CLAUDE.md:33`·`:106` 교수학 절대 금기,
`docs/design/ui/00_index.md:41` 전역 UI 불변식 #2). `gamification_module_gap_review.md`
§3 D2가 지적하듯 이 불변식은 20곳 넘게 인용되나 이를 집행하는 기계 테스트가 이전엔 0건이었다
(ARCH-26 acceptance ②③, Dart측 acceptance ①은 `src/mobile/test/governance/*.dart`가 별도 소유).

3부 구성:
  Part A — 학생 대면 표면(api/**·schema/** 최상위 응답 모델) 소스 스캔. 게임화 계열 "합성
    식별자"(compound identifier)가 유입되면 실패. `no_math_logic_governance_test.dart`
    (ARCH-10)의 4대 기법을 Python으로 재사용: ①정밀도 원칙(bare 단어 금지 — 아래 참조)
    ②\\b+합성어 경계 정규식 ③api/·schema/ 경로 스코프 ④게이트 무력화 방지(스캔 파일 수 하한).
  Part B1 — `UserBehaviorMetrics.metric_name`(`schema/timeseries.py`) open-set 문자열 필드에
    게임화 계열 값이 리터럴로 대입/비교되는지 소스 스캔으로 확인.
  Part B2 — `consecutive_active_days`(`db/models/user.py:324`) writer 0 동결 — 이 필드에
    값을 대입하는 프로덕션 코드가 없음을 확인.

정밀도 원칙(Part A·B1 공통, 이 파일 작성 중 실측으로 확인한 오탐 사례):
  - bare `quest`는 `question`/`request`를 전량 오탐한다(`\\bquest\\w*\\b`가 "question"에 매치 —
    `\\w*`가 탐욕적으로 "ion"까지 흡수).
  - bare `xp`(대소문자 무시)는 `expected`/`export`/`exponential` 등 흔한 영단어의 부분 문자열이라
    전량 오탐한다.
  - bare `streak`/`level`은 각각 misconception 코퍼스의 `gambler_streak`(도박사의 오류 오개념
    ID)·교육과정 서술의 "level" 등 정당 어휘와 충돌할 수 있다.
  → 그래서 이 게이트는 Dart 게이트와 동일하게 **복합 식별자만** 금지한다(`XpPoints`·`LevelUp`·
    `BadgeEarned`·`QuestUnlock`·`Leaderboard`·`StreakCounter`·`DailyStreak`·`ComboMultiplier`·
    `CoinReward` 계열). `Leaderboard` 하나만 예외적으로 단일어 금지인데, 이 단어 자체가 일반
    영단어가 아니라 게임화 UI 전용 신조어이기 때문이다(실측: api/·schema/ 어디에도 우연한
    서식이 없음 — 아래 회귀 테스트로 확인).

스캔 제외(정당 어휘 서식지 — 오탐 방지, 이 프로젝트에서 실제 확인된 사례):
  `whymath_backend.l3.*`·`l4.misconception.*`·`harness.*`·`data/corpus/**`에는
  `gambler_streak`(오개념 ID)·`achievement_standard`(교육과정 성취기준 테이블, 게임 업적
  아님) 등이 정당하게 서식한다(`harness/misconception_mc_batch.py`·
  `l1/standards/standard_loader.py` 등). Part A는 애초에 `api/`·`schema/` *트리 바깥*은
  스캔 대상에 넣지 않으므로("스캔 트리 자체를 좁힌다" 전략 —
  `tests/data_pipeline/test_subject_neutrality_gate.py:29` 선례) 이 경로들은 자연히 배제된다
  (별도 exclude 리스트 불요 — 애초에 대상이 아님).

게이트 자기회피: 이 파일은 스캔 루트(`src/backend/whymath_backend/api`·`schema`, Part B1·B2는
`src/backend/whymath_backend` 전체)의 *바깥*(`tests/`)에 있으므로 구조적으로 자기 자신을
스캔 대상에 넣을 수 없다. 그럼에도 금지 어근을 파일에 그대로 나열하지 않고 `_compose()`로
조립한다 — `tests/data_pipeline/test_subject_neutrality_gate.py:33`의
`_MATH_LABEL_LITERAL = "[" + "수학과 교육과정" + "]"` 관례를 그대로 답습(스캔 루트가 바뀌거나
이 패턴을 다른 파일이 복제할 때를 대비한 방어적 위생).

hermetic: DB 불요(순수 파일시스템 텍스트 스캔).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = _REPO_ROOT / "src" / "backend" / "whymath_backend"

# Part A 스캔 대상 — 학생 대면 표면만(api/** 전체 + schema/** 최상위 응답 모델).
_STUDENT_FACING_DIRS: tuple[Path, ...] = (
    _BACKEND_ROOT / "api",
    _BACKEND_ROOT / "schema",
)

_MIN_STUDENT_FACING_FILES = 10  # 게이트 무력화 방지 — 경로 오타로 0건 통과되는 사고 차단
_MIN_BACKEND_FILES = 50  # Part B(전체 backend 스캔) 동일 취지 하한


def _compose(*parts: str) -> str:
    """조각을 이어붙여 리터럴 문자열을 만든다 — 게이트 자기회피 조합 기법(모듈 docstring 참조)."""
    return "".join(parts)


# 게임화 어근 — bare 단어 오탐 실측(모듈 docstring)으로 인해 항상 접미어와 결합해서만 쓴다.
_ROOTS: dict[str, str] = {
    "xp": _compose("x", "p"),
    "streak": _compose("str", "eak"),
    "leaderboard": _compose("leader", "board"),
    "badge": _compose("bad", "ge"),
    "level": _compose("lev", "el"),
    "quest": _compose("qu", "est"),
    "combo": _compose("com", "bo"),
    "coin": _compose("co", "in"),
}


def _iter_py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _student_facing_py_files() -> list[Path]:
    files: list[Path] = []
    for d in _STUDENT_FACING_DIRS:
        files.extend(_iter_py_files(d))
    return files


# ──────────────────────────────────────────────────────────────────────────
# Part A — 학생 대면 표면 게임화 합성 식별자 소스 스캔 (acceptance②)
# ──────────────────────────────────────────────────────────────────────────
#
# 단어-토큰화 매칭(주의 — `\b` 정규식 단독 사용 금지): 최초 구현은 `\b{root}...\b` 형태의
# 정규식을 썼으나, 변별력 실측(아래 "실측 로그" 참조) 중 `award_badge_earned`·
# `leaderboard_rank`처럼 **밑줄로 다른 단어와 결합된** 식별자를 전량 통과(미탐지)시키는
# 결함이 실제로 드러났다. 원인: 정규식 `\b`는 밑줄(`_`)을 단어문자(`\w`)로 취급하므로
# `award_badge_earned` 전체가 하나의 `\w+` 토큰이 되어, 그 *내부* 밑줄 경계에서는 `\b`가
# 전혀 발생하지 않는다(파이썬 snake_case의 근본 특성 — Dart 게이트의 camelCase 함수호출
# 식별자에는 이 문제가 없어 선례를 그대로 재사용할 수 없었다). 그래서 이 게이트는 식별자를
# snake_case+camelCase 단어 단위로 **분해**한 뒤, 금지 "연속 단어열"이 그 단어 리스트에
# 부분열로 등장하는지 정확히 비교한다 — 부분 문자열 매칭이 아니라 완전한 단어 단위 매칭이라
# `question`≠`quest`, `expected`≠`xp`도 자동으로 안전하다(더 이상 `\b`에 의존하지 않음).
_IDENTIFIER_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL_WORD_PATTERN = re.compile(r"[A-Za-z][a-z0-9]*")


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
    return any(
        all(words[i + j] in sequence[j] for j in range(n)) for i in range(len(words) - n + 1)
    )


# 복합 식별자만 금지(bare 단어 오탐 방지 — 모듈 docstring 정밀도 원칙). 각 값은 "연속 단어
# 위치별 허용 집합" — 예: XpPoints는 1번째 단어가 xp, 2번째가 point/points여야 매치.
_FORBIDDEN_WORD_SEQUENCES: dict[str, tuple[frozenset[str], ...]] = {
    "XpPoints": (frozenset({_ROOTS["xp"]}), frozenset({"point", "points"})),
    "XpReward": (frozenset({_ROOTS["xp"]}), frozenset({"reward"})),
    "LevelUp": (frozenset({_ROOTS["level"]}), frozenset({"up"})),
    "BadgeEarned": (frozenset({_ROOTS["badge"]}), frozenset({"earned", "unlocked"})),
    "QuestUnlock": (frozenset({_ROOTS["quest"]}), frozenset({"unlock", "unlocked"})),
    "DailyQuest": (frozenset({"daily"}), frozenset({_ROOTS["quest"]})),
    # 'leaderboard'는 게임화 UI 전용 신조어라 예외적으로 단일 단어 금지(모듈 docstring 근거).
    "Leaderboard": (frozenset({_ROOTS["leaderboard"]}),),
    "StreakCounter": (frozenset({_ROOTS["streak"]}), frozenset({"counter"})),
    "DailyStreak": (frozenset({"daily"}), frozenset({_ROOTS["streak"]})),
    "ComboMultiplier": (
        frozenset({_ROOTS["combo"]}),
        frozenset({"multiplier", "bonus", "counter"}),
    ),
    "CoinReward": (frozenset({_ROOTS["coin"]}), frozenset({"reward", "balance"})),
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


# 정밀도 회귀 안전망 — 이 프로젝트에 실제 존재하는 벤치 식별자들이 오탐되지 않아야 한다
# (모듈 docstring에서 실측한 quest→question, xp→expected/export 충돌 사례 포함).
_BENIGN_IDENTIFIERS_MUST_NOT_MATCH: tuple[str, ...] = (
    "question_text",
    "question_format",
    "QuestionFormat",
    "expected_answer",
    "expected_solve_seconds",
    "exploration_turn",
    "level",  # bare "level"은 금지 대상 아님(교육과정 등에서 정당 서식)
    "achievement_standard",  # 성취기준 — 게임 업적 아님(l1/standards 정당 어휘, 방어적 이중 확인)
    "gambler_streak",  # 도박사의 오류 오개념 ID(l4/misconception 정당 어휘, 방어적 이중 확인)
)

# 실측 로그(변별력 확인 — acceptance④): 최초 `\b` 기반 구현으로
# `src/backend/whymath_backend/api/_zz_gamify_injection.py`에
# `leaderboard_rank = 1`·`def award_badge_earned(...)`를 주입했을 때 **거짓 통과**(미탐지)를
# 재현 확인 → 단어-토큰화로 재구현 후 동일 주입에서 정상 실패(FAILED)를 재확인했다(최종
# 보고서에 원본 pytest 출력 포함). 아래 두 식별자를 정밀도 실측에 상시 포함해 회귀를 고정한다.
_TRUE_POSITIVE_IDENTIFIERS_MUST_MATCH: dict[str, str] = {
    "leaderboard_rank": "Leaderboard",
    "award_badge_earned": "BadgeEarned",
}


class TestGamificationSymbolSourceScan:
    """Part A — api/**·schema/** 게임화 합성 식별자 유입 금지."""

    def test_scan_scope_not_empty(self) -> None:
        """게이트 무력화 방지 — 스캔 파일 수가 하한 이상(경로 오타로 0건 '통과' 위장 차단)."""
        files = _student_facing_py_files()
        assert len(files) >= _MIN_STUDENT_FACING_FILES, (
            f"스캔 대상 파일이 {len(files)}건뿐 — 경로 오타로 게이트가 무력화됐을 위험 "
            f"(scanned dirs: {[str(d) for d in _STUDENT_FACING_DIRS]})"
        )

    @pytest.mark.parametrize("label", sorted(_FORBIDDEN_WORD_SEQUENCES))
    def test_no_gamification_symbol_in_student_facing_surface(self, label: str) -> None:
        """게임화 합성 식별자가 api/**·schema/** 어디에도 리터럴로 등장하지 않는다."""
        offenders = [
            str(path.relative_to(_REPO_ROOT))
            for path in _student_facing_py_files()
            if label in _text_offending_labels(path.read_text(encoding="utf-8"))
        ]
        assert not offenders, (
            f"게임화 계열 심볼 '{label}' 유입: {offenders} — CLAUDE.md 교수학 절대 금기"
            "(우열 게임화 금지)·전역 UI 불변식 #2(docs/design/ui/00_index.md:41) 위반 의심."
        )

    @pytest.mark.parametrize("identifier", _BENIGN_IDENTIFIERS_MUST_NOT_MATCH)
    def test_precision_benign_identifiers_are_not_flagged(self, identifier: str) -> None:
        """정밀도 회귀 안전망 — 정당 식별자가 어떤 금지 패턴에도 걸리지 않는다(오탐 방지)."""
        offending_labels = _text_offending_labels(identifier)
        assert (
            not offending_labels
        ), f"'{identifier}'가 {offending_labels} 패턴에 오탐됨 — 정밀도 원칙 위반"

    @pytest.mark.parametrize("identifier", sorted(_TRUE_POSITIVE_IDENTIFIERS_MUST_MATCH))
    def test_variance_true_positive_identifiers_are_flagged(self, identifier: str) -> None:
        """변별력 회귀 고정핀 — 실제 위반 식별자는 반드시 걸린다(§실측 로그 재발 방지)."""
        expected_label = _TRUE_POSITIVE_IDENTIFIERS_MUST_MATCH[identifier]
        assert expected_label in _text_offending_labels(identifier), (
            f"'{identifier}'가 '{expected_label}'로 탐지되지 않음 — 변별력 회귀"
            "(과거 `\\b` 기반 구현이 이 케이스를 놓쳤던 결함의 재발)"
        )


# ──────────────────────────────────────────────────────────────────────────
# Part B1 — UserBehaviorMetrics.metric_name 금지값 소스 스캔 (acceptance③)
# ──────────────────────────────────────────────────────────────────────────
#
# `metric_name`은 `VARCHAR(50)` open-set 문자열 필드라 런타임 validator(닫힌 enum)로는 막을 수
# 없다(schema/timeseries.py 모듈 docstring이 명시 — 지표 종류가 운영 중 계속 늘어날 수 있어
# 의도적으로 str open set). 따라서 "프로덕션 코드에 게임화 계열 값이 리터럴로 하드코딩되지
# 않는다"를 소스 스캔으로 동결한다. 판단 근거: (a) open-set 필드는 Pydantic validator를 두면
# 지표 확장 유연성을 해치므로 헌법(우열 게임화 금지)이 요구하는 최소 개입은 "미래 하드코딩
# 유입 차단"이지 "현재 열거값 제한"이 아니다, (b) 변수를 통한 간접 대입(`metric_name=some_var`)은
# 정적 텍스트 스캔의 구조적 한계로 못 잡는다 — 이는 `test_subject_neutrality_gate.py`류 기존
# 리터럴 스캔 게이트와 동일한 알려진 맹점이며, 새 리터럴 유입을 막는 것만으로도 실질적 방어력이
# 있다(대부분의 하드코딩 사고는 리터럴 직접 대입 형태).
#
# 패턴은 "metric_name" 토큰 뒤에 곧바로(공백만 허용) `=`/`==`가 오고, 그 뒤 인용부호로 감싼
# 값이 게임화 어근(+선택적 `_단어`)과 *정확히* 일치할 때만 매치한다 — 인용부호로 양끝을 고정하는
# 방식이라 `\b` 없이도 오탐이 없다(실측: "session_length"/"churn_risk"/"expected_value" 전부
# 통과 — 아래 회귀 테스트로 확인). `schema/timeseries.py`의 docstring 예시(`'streak'`)는
# `description=` 값 안에 있어 "metric_name" 토큰과 직접 인접하지 않으므로 매치되지 않는다.
_METRIC_NAME_VALUE_ALTERNATION = "|".join(rf"{root}(?:_\w+)?" for root in _ROOTS.values())
_FORBIDDEN_METRIC_NAME_VALUE_PATTERN = re.compile(
    rf"metric_name\s*={{1,2}}\s*[\"'](?:{_METRIC_NAME_VALUE_ALTERNATION})[\"']",
    re.IGNORECASE,
)

_BENIGN_METRIC_NAME_VALUES_MUST_NOT_MATCH: tuple[str, ...] = (
    'metric_name="session_length"',
    'metric_name="churn_risk"',
    'metric_name="expected_value"',
)


class TestMetricNameForbiddenValueScan:
    """Part B1 — `UserBehaviorMetrics.metric_name`에 게임화 계열 값이 하드코딩되지 않는다."""

    def test_scan_scope_not_empty(self) -> None:
        files = _iter_py_files(_BACKEND_ROOT)
        assert len(files) >= _MIN_BACKEND_FILES, (
            f"스캔 대상 파일이 {len(files)}건뿐 — 경로 오타로 게이트가 무력화됐을 위험 "
            f"(scanned dir: {_BACKEND_ROOT})"
        )

    def test_no_gamification_value_assigned_to_metric_name(self) -> None:
        offenders: list[str] = []
        for path in _iter_py_files(_BACKEND_ROOT):
            text = path.read_text(encoding="utf-8")
            if _FORBIDDEN_METRIC_NAME_VALUE_PATTERN.search(text):
                offenders.append(str(path.relative_to(_REPO_ROOT)))
        assert not offenders, (
            f"metric_name에 게임화 계열 값 하드코딩 유입: {offenders} — "
            "CLAUDE.md 교수학 절대 금기(우열 게임화 금지) 위반 의심(schema/timeseries.py "
            "UserBehaviorMetrics.metric_name는 open-set VARCHAR(50)이라 값 자체를 소스 스캔으로 "
            "동결한다)."
        )

    def test_docstring_example_value_does_not_trip_the_gate(self) -> None:
        """schema/timeseries.py 자체가 오탐 없이 통과함을 명시적으로 재확인(회귀 고정핀).

        해당 파일 docstring이 'streak'을 metric_name 예시로 든다 — 값이 아니라 *설명*이므로
        통과해야 정상이다(정밀도 원칙 회귀 안전망).
        """
        timeseries_path = _BACKEND_ROOT / "schema" / "timeseries.py"
        assert timeseries_path.is_file(), f"경로 확인 실패: {timeseries_path}"
        text = timeseries_path.read_text(encoding="utf-8")
        assert not _FORBIDDEN_METRIC_NAME_VALUE_PATTERN.search(
            text
        ), "schema/timeseries.py가 자체 오탐됨 — docstring 예시와 실제 대입을 구분하지 못함"

    @pytest.mark.parametrize("benign_line", _BENIGN_METRIC_NAME_VALUES_MUST_NOT_MATCH)
    def test_precision_benign_metric_values_are_not_flagged(self, benign_line: str) -> None:
        assert not _FORBIDDEN_METRIC_NAME_VALUE_PATTERN.search(
            benign_line
        ), f"'{benign_line}'이 오탐됨 — 정밀도 원칙 위반"


# ──────────────────────────────────────────────────────────────────────────
# Part B2 — consecutive_active_days writer 0 동결 (acceptance③)
# ──────────────────────────────────────────────────────────────────────────
#
# 범위 제외(중요, 중복 등재 금지): `focus_score`/`engagement_score`
# (`db/models/activity.py:107-108`)는 `S3-16-behavior-telemetry-writers` 소유 — 이 게이트는
# 건드리지 않는다.
#
# `consecutive_active_days`(`db/models/user.py:324`)는 "연속 학습일" 필드로, 도박성 스트릭
# 게임화(연속 출석 보상 등)로 오용될 위험이 구조적으로 있는 필드다. 현재 이 필드에 값을 쓰는
# 프로덕션 코드가 0건임을 실측했다(스키마·ORM 선언 2곳뿐 — 아래 스캔이 검증). 이 상태를
# writer 0으로 동결해, 향후 누군가 "연속 출석 스트릭 보상" 류 로직을 이 필드에 몰래 연결하면
# 즉시 실패하게 한다.
#
# 패턴은 `consecutive_active_days` 토큰 뒤 공백만 두고 곧바로(선택적 산술 연산자 + ) `=`가
# 오되 `==`(비교)는 제외한다(negative lookahead) — "대입"만 writer로 본다. 필드 선언
# (`consecutive_active_days: int | None = Field(...)`·`consecutive_active_days: Mapped[...] =
# mapped_column(...)`)은 이름과 `=` 사이에 타입 애노테이션(`: ...`)이 끼어 있어 이 패턴과
# 구조적으로 겹치지 않는다(실측 확인 — 아래 회귀 테스트).
_CONSECUTIVE_ACTIVE_DAYS_WRITE_PATTERN = re.compile(r"consecutive_active_days\s*[+\-*/]?=(?!=)")

_KNOWN_DECLARATION_LINES: tuple[str, ...] = (
    "consecutive_active_days: int | None = Field(",
    "consecutive_active_days: Mapped[int | None] = mapped_column(sa.Integer)",
)


class TestConsecutiveActiveDaysWriterFreeze:
    """Part B2 — `consecutive_active_days`에 값을 쓰는 프로덕션 코드가 0건임을 동결."""

    def test_scan_scope_not_empty(self) -> None:
        files = _iter_py_files(_BACKEND_ROOT)
        assert len(files) >= _MIN_BACKEND_FILES, (
            f"스캔 대상 파일이 {len(files)}건뿐 — 경로 오타로 게이트가 무력화됐을 위험 "
            f"(scanned dir: {_BACKEND_ROOT})"
        )

    def test_no_writer_for_consecutive_active_days(self) -> None:
        offenders: list[str] = []
        for path in _iter_py_files(_BACKEND_ROOT):
            text = path.read_text(encoding="utf-8")
            if _CONSECUTIVE_ACTIVE_DAYS_WRITE_PATTERN.search(text):
                offenders.append(str(path.relative_to(_REPO_ROOT)))
        assert not offenders, (
            f"consecutive_active_days writer 유입: {offenders} — 죽은 좌석(writer 0) 동결 "
            "위반. 연속 출석 스트릭 보상형 게임화로 이어질 위험(CLAUDE.md 교수학 절대 금기 "
            "위반 의심) — 의도적 기능이면 이 게이트를 갱신하고 교수학 검토를 먼저 거쳐라."
        )

    @pytest.mark.parametrize("declaration_line", _KNOWN_DECLARATION_LINES)
    def test_precision_field_declarations_are_not_flagged(self, declaration_line: str) -> None:
        """정밀도 회귀 안전망 — 필드 선언 자체는 writer로 오탐되지 않는다."""
        assert not _CONSECUTIVE_ACTIVE_DAYS_WRITE_PATTERN.search(
            declaration_line
        ), f"필드 선언이 writer로 오탐됨: {declaration_line!r}"
