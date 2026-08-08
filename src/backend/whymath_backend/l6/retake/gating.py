"""L6 재수전용(RT/N수) 트랙 게이팅 로직 — 적격성·우선순위·선별.

이 모듈은 페르소나 B·C(재수/N수)에게 *어떤* 기존 문항을 RT 트랙으로 노출할지 결정한다.
**HIGH 오버레이 모델**: 새 enum·concept 노드·Alembic 마이그레이션을 만들지 않고, 기존 L1
`Problem`의 필드(`persona_fit`·`question_format=재수전용형`·`distractor_map`)만 *재사용*하는
순수 결정 로직이다. 부수효과 없음(I/O·LLM 호출 없음)·결정적(deterministic).

공개 API 4종:
  - `is_retake_eligible(problem, persona, *, min_fit)` — 이 문항을 이 페르소나에게 RT로
    노출해도 되는가(불리언 게이트).
  - `retake_priority(problem)` — 노출 우선순위 가중치(높을수록 먼저). 교수학 근거 반영.
  - `select_retake_items(problems, persona, *, min_fit, limit)` — 적격 필터 → 우선순위
    내림차순 안정정렬 → limit 적용.
  - `RETAKE_PERSONAS`·`METADATA_ONLY_SOURCES` — 게이팅 상수(아래 docstring에 근거).

레이어 규칙(CLAUDE.md): L6→L1만 의존. L4를 import하지 않는다 — `distractor_map`은 *존재
여부*만 보므로(오답→오개념 *역추적 가능성*의 신호일 뿐) L4 카탈로그·검증자가 불필요하다.

use_enum_values=True 주의: `Problem`은 `ConfigDict(use_enum_values=True)`라 직렬화·구성
경로에 따라 `source_type`·`question_format`이 *문자열 값*일 수 있고 `persona_fit`의 *키*도
문자열일 수 있다. 따라서 enum 비교 시 항상 enum/문자열 양쪽을 정규화해 비교한다
(`schema/problem.py`의 `_enforce_copyright_no_body_for_metadata_sources` validator 패턴 답습).
정규화·저작권 게이트는 L6 공용 모듈 `l6/_shared.py`로 추출 완료(아래 Rule of three 메모).

Rule of three — 추출 완료(`l6/_shared.py`): `METADATA_ONLY_SOURCES`와 정규화 헬퍼
(`_source_value`·`_persona_fit`)는 본래 수능 모드(`l6/suneung/gating.py`)와 *의도적으로*
중복했다(서로의 파일을 건드리지 않아 무회귀를 보장하려는 선택). 학교진도가 *세 번째* L6
모드로 들어오면서 그 중복을 `l6/_shared.py`로 통합했다 — 이 모듈은 이제 `_shared.is_exposable`
(저작권 게이트)·`_shared.normalize_enum_value`(enum 정규화)·`_shared.persona_fit`을 호출한다.
`METADATA_ONLY_SOURCES`는 기존 import 경로(`l6.retake.gating.METADATA_ONLY_SOURCES`)와
테스트 호환을 위해 `_shared`에서 *재노출*한다(아래).
"""

from __future__ import annotations

from collections.abc import Iterable

from whymath_backend.l6 import _shared
from whymath_backend.l6._shared import METADATA_ONLY_SOURCES
from whymath_backend.schema.enums import Persona, QuestionFormat
from whymath_backend.schema.problem import Problem

# 저작권 노출 게이트 차단 집합(평가원·EBS·교과서)을 L6 공용 모듈에서 *재노출*한다 —
# 기존 import 경로(`l6.retake.gating.METADATA_ONLY_SOURCES`)·테스트 호환을 위해 이름을 유지.
# 정의 정본은 `l6/_shared.py`(Rule of three 추출 완료). `__all__`에도 그대로 둔다.
__all__ = [
    "METADATA_ONLY_SOURCES",
    "RETAKE_PERSONAS",
    "is_retake_eligible",
    "retake_priority",
    "select_retake_items",
]

# ──────────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────────
RETAKE_PERSONAS: frozenset[Persona] = frozenset({Persona.B_자사고N수, Persona.C_검정고시N수})
"""RT(재수전용) 트랙의 대상 페르소나 — 재수/N수 생.

PRD 5종 페르소나(`enums.Persona`) 중 *재수(N수)* 상황인 둘만 RT 트랙 대상이다:
  - `B_자사고N수` — 자사고 출신 N수생(결제 최대 세그먼트),
  - `C_검정고시N수` — 검정고시 N수생(수학 의존도 100%).
나머지 A(일반고 고3)·D(학종 고2)·E(홈스쿨링 영재)는 *재수 트랙이 아니므로* 제외한다
(`QuestionFormat.재수전용형` docstring: "재수(N수)전용 유형(retake-only). 페르소나 B·C 대상").
"""

# 저작권 노출 게이트 차단 집합 `METADATA_ONLY_SOURCES`(평가원·EBS·교과서)는 L6 공용
# 모듈 `l6/_shared.py`에 정본을 두고, 이 파일 상단에서 *재노출*한다(Rule of three 추출 완료).


def is_retake_eligible(problem: Problem, persona: Persona, *, min_fit: float = 0.5) -> bool:
    """이 문항을 이 페르소나에게 RT(재수전용) 트랙으로 노출해도 되는가(불리언 게이트).

    판정 순서(앞 게이트에서 막히면 즉시 False):
      ① 대상 페르소나 게이트 — `persona ∈ RETAKE_PERSONAS`(B·C)가 아니면 False(비대상).
      ② 저작권 노출 게이트 — `source_type`이 본문 미보유 출처(평가원/EBS/교과서)면 False.
         학생 노출 불가 본문이므로 *대상 페르소나라도* 막힌다(CLAUDE.md 우선순위 #2 — 법적).
      ③ RT 적합 신호 — 다음 중 *하나라도* 참이면 True, 아니면 False:
           (a) `question_format == 재수전용형`(RT 라벨이 명시된 문항), **또는**
           (b) `persona_fit[persona] >= min_fit`(이 페르소나 적합도가 임계 이상).

    Args:
      problem: 후보 문항(L1 `Problem`).
      persona: 노출 대상 페르소나.
      min_fit: persona_fit 임계값(기본 0.5 — "절반 이상 적합"). 0~1 척도.

    Returns:
      RT 트랙 노출 적격이면 True.

    use_enum_values=True 주의: source_type·question_format·persona_fit 키가 문자열일 수
    있어 L6 공용 헬퍼(`_shared.is_exposable`·`_shared.normalize_enum_value`·
    `_shared.persona_fit`)로 정규화해 비교한다.
    """
    # ① 대상 페르소나 게이트.
    if persona not in RETAKE_PERSONAS:
        return False

    # ② 저작권 노출 게이트 — 본문 미보유 출처는 노출 불가(대상 페르소나라도 차단).
    if not _shared.is_exposable(problem):
        return False

    # ②-b 검수 노출 게이트 — 저작권 축과 독립(합치지 않음, PB-03). review_status=approved만 통과.
    if not _shared.is_review_cleared(problem):
        return False

    # ③ RT 적합 신호 — 재수전용형 라벨 또는 페르소나 적합도 임계 이상.
    is_retake_format = (
        _shared.normalize_enum_value(problem.question_format) == QuestionFormat.재수전용형.value
    )
    meets_fit = _shared.persona_fit(problem, persona) >= min_fit
    return is_retake_format or meets_fit


def retake_priority(problem: Problem) -> float:
    """RT 트랙 노출 우선순위 가중치 — 높을수록 먼저 노출. 결정적(deterministic).

    교수학 근거(CLAUDE.md 우선순위 #3·#4): 재수생의 핵심 과제는 *고착된 오개념의
    재구조화*다(같은 실수를 반복하는 N수생에게 단순 반복은 무의미하고, 오답을 오개념으로
    역추적해 *왜 틀렸는지*를 메타인지적으로 다루는 문항이 가치가 높다). 이를 반영해:

      가중치 = (distractor_map 있으면 +2.0) + (재수전용형이면 +1.5) + (difficulty_overall|0.0)

      - `distractor_map` *존재* → +2.0(가장 큰 가중치). 오답 선지가 오개념에 매핑돼 있어
        오답→오개념 *역추적*이 가능한 문항이다 — 재수생 오개념 재구조화에 직결되므로 최우선.
        (존재 여부만 본다 — 매핑 내용·카탈로그 정합은 L4 소관이고 이 모듈은 보지 않는다.)
      - `question_format == 재수전용형` → +1.5. RT용으로 *설계된* 문항(고난도 변형)이라 가산.
      - `difficulty_overall`(1.0~5.0, None이면 0.0) → 그대로 가산. 재수 트랙은 변별·심화가
        목적이라 어려운 문항을 약하게 앞세운다(±5 범위라 위 두 신호를 압도하지 않는 보조 축).

    구체 가중치(2.0/1.5/난이도 그대로)는 *상대 순서*만 의미가 있다 — distractor_map 신호가
    재수전용형 신호보다 크고, 난이도는 동급 신호 사이의 타이브레이커로 약하게 작동하도록 정했다.
    합산이라 같은 점수(예: 둘 다 distractor_map 있고 같은 난이도)는 동률이며, 동률 처리는
    `select_retake_items`의 *안정정렬*(원래 순서 보존)에 맡긴다.

    Args:
      problem: 우선순위를 매길 문항.

    Returns:
      가중치(클수록 우선). 음수 없음(모든 항이 비음수).
    """
    weight = 0.0

    # distractor_map *존재* 신호 — 오답→오개념 역추적 가능(존재 여부만; L4 미import).
    if problem.distractor_map:  # None·빈 리스트면 거짓(존재하지 않음)
        weight += 2.0

    # 재수전용형 라벨 신호 — RT용으로 설계된 문항.
    if _shared.normalize_enum_value(problem.question_format) == QuestionFormat.재수전용형.value:
        weight += 1.5

    # 종합 난이도 보조 축(None이면 0.0) — 심화·변별을 약하게 앞세움.
    if problem.difficulty_overall is not None:
        weight += problem.difficulty_overall

    return weight


def select_retake_items(
    problems: Iterable[Problem],
    persona: Persona,
    *,
    min_fit: float = 0.5,
    limit: int | None = None,
) -> list[Problem]:
    """RT 트랙 노출 문항을 *선별·정렬*한다 — 적격 필터 → 우선순위 내림차순 → limit.

    파이프라인:
      1. `is_retake_eligible(p, persona, min_fit=min_fit)`로 적격 문항만 남긴다(비대상
         페르소나·본문 미보유 출처·적합 신호 부재는 탈락).
      2. `retake_priority(p)` *내림차순*으로 **안정정렬**한다(동률은 입력 순서 보존 —
         `retake_priority` docstring의 동률 처리 계약). 따라서 distractor_map이 있는 고난도
         문항이 앞으로 온다.
      3. `limit`이 주어지면 상위 `limit`개만 돌려준다(None이면 무제한·전부).

    Args:
      problems: 후보 문항들(임의 iterable — 한 번만 순회).
      persona: 노출 대상 페르소나.
      min_fit: persona_fit 임계값(기본 0.5). `is_retake_eligible`에 전달.
      limit: 최대 개수(None=무제한). 0이면 빈 리스트.

    Returns:
      우선순위 내림차순으로 정렬된 적격 문항 리스트(limit 적용).

    결정적(deterministic)·부수효과 없음. `sorted(reverse=True)`는 파이썬 안정정렬이라
    동률 간 입력 순서가 보존된다.
    """
    eligible = [p for p in problems if is_retake_eligible(p, persona, min_fit=min_fit)]
    # 안정정렬 — 동률(같은 priority)은 입력 순서 유지. reverse=True로 큰 가중치 우선.
    ranked = sorted(eligible, key=retake_priority, reverse=True)
    if limit is None:
        return ranked
    return ranked[:limit]
