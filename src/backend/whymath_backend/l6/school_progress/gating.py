"""L6 학교진도 모드 게이팅 로직 — 적격성·우선순위·선별.

이 모듈은 학교 *재학생* 페르소나에게 *어떤* 기존 문항을 학교진도 모드로 노출할지 결정한다.
**오버레이 모델**(RT 트랙·수능 모드 게이팅과 동형): 새 enum·concept 노드·Alembic
마이그레이션을 만들지 않고, 기존 L1 `Problem`의 필드(`source_type`·`curriculum_version`·
`unit_codes`·`persona_fit`·`difficulty_overall`)만 *재사용*하는 순수 결정 로직이다.
부수효과 없음(I/O·LLM 호출 없음)·결정적(deterministic).

공개 API 4종:
  - `is_school_progress_eligible(problem, persona, *, target_unit_codes, curriculum_version,
    min_fit)` — 이 문항을 이 페르소나에게 학교진도 모드로 노출해도 되는가(불리언 게이트).
  - `school_progress_priority(problem, *, target_unit_codes)` — 노출 우선순위 가중치(높을수록
    먼저). 교수학 근거(자동 커리큘럼 정렬 — 현재 진도 단원 정합 우선) 반영.
  - `select_school_progress_items(problems, persona, *, target_unit_codes, curriculum_version,
    min_fit, limit)` — 적격 필터 → 우선순위 내림차순 안정정렬 → limit 적용.
  - `SCHOOL_PROGRESS_PERSONAS` — 게이팅 상수(아래 docstring에 근거).

저작권 게이트(`METADATA_ONLY_SOURCES`)는 L6 공용 모듈 `l6/_shared.py`에 정본을 두고, 이
파일에서 `_shared.is_exposable`로 사용한다(RT·수능과 공유 — Rule of three 추출 완료).

레이어 규칙(CLAUDE.md): L6→L1만 의존한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다 — 이 모듈은 기존 `Problem` 필드의 *존재·값*만 보므로 하위
카탈로그·검증자·모델이 불필요하다. L6은 아무도 import하지 않는 최상위 소비자다(역방향 의존
부재).

**성취기준(AchievementStandard) 매칭 심화(이 슬라이스)**: 진도 정합을 단원(`unit_codes`)
하나로만 보던 데서, *단원보다 세밀한* 성취기준 코드 정합을 **추가 축**으로 더한다. 이 모듈은
성취기준 마스터 테이블·4단계 조인을 *직접 수행하지 않는다* — `Problem.achievement_standard_codes`
(비영속 필드·L5 api 조인이 주입)의 *값만* 읽어 순수성(부수효과 0)을 유지한다(DB 조인은 전부 L5
소관·retake·suneung·thinking과 동형 계약). 성취기준은 *더 세밀한 추가 신호*이므로 단원과
**OR(또는)**로 결합한다 — 성취기준 불일치가 단원 적합을 덮지 않고, 데이터가 없어(빈 리스트)도
단원·persona_fit 폴백이 그대로 동작한다(하위호환·데이터0 안전). 우선순위에서는 성취기준 겹침이
단원 겹침보다 *세밀하므로 더 높은 가중치*를 준다.

use_enum_values=True 주의: `Problem`은 `ConfigDict(use_enum_values=True)`라 직렬화·구성
경로에 따라 `source_type`·`curriculum_version`이 *문자열 값*일 수 있고 `persona_fit`의 *키*도
문자열일 수 있다. 따라서 enum 비교 시 항상 enum/문자열 양쪽을 정규화해 비교한다(L6 공용
`_shared.normalize_enum_value`·`_shared.persona_fit`·`_shared.is_exposable` 사용).
"""

from __future__ import annotations

from collections.abc import Iterable

from whymath_backend.l6 import _shared
from whymath_backend.schema.enums import Curriculum, Persona
from whymath_backend.schema.problem import Problem

# ──────────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────────
SCHOOL_PROGRESS_PERSONAS: frozenset[Persona] = frozenset({Persona.A_일반고고3, Persona.D_학종고2})
"""학교진도 모드의 대상 페르소나 — 학교에 *재학 중*인 학생.

PRD 5종 페르소나(`enums.Persona`) 중 *학교 재학생*인 둘만 학교진도 모드 대상이다 — 학교진도
모드는 "학생이 다니는 학교의 현재 진도(단원·교육과정)에 맞춰 문항을 노출"하는 모드이므로,
*다닐 학교가 있는* 재학생에게만 의미가 있다:
  - `A_일반고고3` — 일반고 고3(MVP·시장 최대·학교 재학),
  - `D_학종고2` — 학종 고2(학생부종합·세특/자유연구도 *학교 진도*를 따라간다).
나머지 셋은 *학교 진도를 따라가는 재학생이 아니므로* 제외한다:
  - `B_자사고N수`·`C_검정고시N수` — N수(재수)생으로 *비재학*(학교 진도 개념이 없다. 정시
    중심 — 수능 모드 `l6/suneung` 대상),
  - `E_홈스쿨링영재` — 홈스쿨링(학교 미재학)으로 학교 진도 정합이 성립하지 않는다(심화·영재
    트랙 — 후속 영재 모드 대상).
"""


def is_school_progress_eligible(
    problem: Problem,
    persona: Persona = Persona.A_일반고고3,
    *,
    target_unit_codes: set[str] | None = None,
    target_achievement_codes: set[str] | None = None,
    curriculum_version: Curriculum | None = None,
    min_fit: float = 0.5,
) -> bool:
    """이 문항을 이 페르소나에게 학교진도 모드로 노출해도 되는가(불리언 게이트).

    판정 순서(앞 게이트에서 막히면 즉시 False):
      ① 대상 페르소나 게이트 — `persona ∈ SCHOOL_PROGRESS_PERSONAS`(A·D)가 아니면 False
         (비재학·홈스쿨). N수(B·C)·영재(E)는 학교진도 모드 대상이 아니다.
      ② 저작권 노출 게이트 — `source_type`이 본문 미보유 출처(평가원/EBS/교과서)면 False.
         학생 노출 불가 본문이므로 *재학생·진도 정합이어도* 막힌다(CLAUDE.md 우선순위 #2 — 법적).
      ③ 교육과정 버전 정합 — `curriculum_version` 인자가 주어지면 `problem.curriculum_version`과
         일치해야 한다(정규화 비교). 불일치면 False. 진도는 교육과정 버전 정합이 필수다(예:
         2022 개정 진도에 2015 개정 문항을 섞지 않는다). 인자가 None이면 이 게이트는 건너뛴다.
      ④ 진도 적합 신호 — 성취기준(더 세밀)과 단원을 **OR(또는)**로 결합한다:
           - 성취기준 겹침: `target_achievement_codes`가 주어지고 문항의
             `achievement_standard_codes`와 *하나라도 겹치면* 적합(집합 교집합 비공집합).
           - 단원 겹침: `target_unit_codes`가 주어지면
             `set(problem.unit_codes) & target_unit_codes`가 비지 않으면 적합.
           - 두 타깃 중 *하나라도* 주어지면 위 둘 중 **하나라도 겹치면** True(OR), 둘 다 안 겹치면
             False. ★ **OR(AND 아님)이 핵심** — 성취기준은 단원보다 세밀한 *추가* 신호일 뿐이라,
             성취기준 불일치가 단원 적합을 덮으면 안 된다. 빈 `achievement_standard_codes`
             (데이터0) 문항도 단원이 맞으면 통과한다(하위호환·데이터0 안전).
           - 두 타깃 *모두 None*이면 `persona_fit[persona] >= min_fit`로 폴백한다(진도 정보 부재 시
             페르소나 적합도로 대신 판정 — 기존 동작 그대로).

    Args:
      problem: 후보 문항(L1 `Problem`).
      persona: 노출 대상 페르소나(기본 A_일반고고3 — MVP 재학생 정면 대상).
      target_unit_codes: 현재 진도 단원 코드 집합(선택). 주어지면 단원 겹침으로 진도 적합을
        판정한다. target_achievement_codes와 OR로 결합되며, 둘 다 None이면 persona_fit 폴백.
      target_achievement_codes: 현재 진도 성취기준 고시코드(official_code) 집합(선택). 단원보다
        세밀한 추가 정합 신호로, `problem.achievement_standard_codes`(비영속·L5 조인 주입)와의
        겹침을 본다. 단원과 OR로 결합. 데이터(태깅)가 없으면 문항 코드가 빈 리스트라 단원으로 폴백.
      curriculum_version: 교육과정 버전 정합 기준(선택). 주어지면 problem과 일치해야 한다.
      min_fit: persona_fit 임계값(기본 0.5 — "절반 이상 적합"). 두 타깃이 모두 None일 때만 쓰인다.
        0~1 척도.

    Returns:
      학교진도 모드 노출 적격이면 True.

    use_enum_values=True 주의: source_type·curriculum_version·persona_fit 키가 문자열일 수
    있어 L6 공용 헬퍼(`_shared.is_exposable`·`_shared.normalize_enum_value`·
    `_shared.persona_fit`)로 정규화해 비교한다.
    """
    # ① 대상 페르소나 게이트 — 재학생(A·D)만.
    if persona not in SCHOOL_PROGRESS_PERSONAS:
        return False

    # ② 저작권 노출 게이트 — 본문 미보유 출처는 노출 불가(재학생·진도 정합이어도 차단).
    if not _shared.is_exposable(problem):
        return False

    # ③ 교육과정 버전 정합 — 인자가 주어지면 일치해야 한다(진도는 교육과정 버전 정합 필수).
    if curriculum_version is not None:
        target_curriculum = _shared.normalize_enum_value(curriculum_version)
        problem_curriculum = _shared.normalize_enum_value(problem.curriculum_version)
        if problem_curriculum != target_curriculum:
            return False

    # ④ 진도 적합 신호 — 성취기준(세밀)·단원을 OR로 결합, 둘 다 None이면 persona_fit 폴백.
    if target_achievement_codes is not None or target_unit_codes is not None:
        # 성취기준 겹침(더 세밀한 추가 신호) — 타깃이 주어지고 문항 코드와 하나라도 겹치면 적합.
        ach_hit = target_achievement_codes is not None and bool(
            set(problem.achievement_standard_codes) & target_achievement_codes
        )
        # 단원 겹침(기존 신호) — 타깃이 주어지고 문항 단원과 하나라도 겹치면 적합.
        unit_hit = target_unit_codes is not None and bool(
            set(problem.unit_codes) & target_unit_codes
        )
        # ★ OR — 성취기준 '또는' 단원이 맞으면 통과(성취기준 불일치가 단원 적합을 덮지 않음).
        return ach_hit or unit_hit
    # 진도 정보(성취기준·단원)가 모두 없으면 페르소나 적합도로 폴백 판정(기존 동작 그대로).
    return _shared.persona_fit(problem, persona) >= min_fit


def school_progress_priority(
    problem: Problem,
    *,
    target_unit_codes: set[str] | None = None,
    target_achievement_codes: set[str] | None = None,
) -> float:
    """학교진도 모드 노출 우선순위 가중치 — 높을수록 먼저 노출. 결정적(deterministic).

    교수학 근거(CLAUDE.md "자동 커리큘럼 정렬" — 학생 교과서·진도에 맞춤): 학교진도 모드의
    핵심은 *학생이 지금 배우는 진도*와의 정합이다. 같은 적격 문항이라도 현재 진도와 *더 세밀하게·더
    많이* 겹치는 문항이 지금 학습에 직결되므로 우선 노출 가치가 크다. 이를 반영해:

      가중치 = (성취기준 겹침 *개수* × 3.0)         # 신규 — 가장 세밀 = 최우선
             + (단원      겹침 *개수* × 2.0)         # 기존 불변
             + (difficulty_overall|0.0)              # 기존 불변(타이브레이커)

      - 성취기준 겹침 *개수* × 3.0 → **가장 세밀한 신호라 가장 큰 단위 가중치**(성취기준 1개=3.0 >
        단원 1개=2.0). `target_achievement_codes`가 주어지면
        `set(problem.achievement_standard_codes) & target_achievement_codes`의 *원소 수*에
        ×3.0을 곱한다 — 성취기준은 단원보다 세밀하므로, 같은 단원이라도 *현재 진도 성취기준에
        직결되는* 문항을 더 앞세운다. `target_achievement_codes`가 None이거나 문항 코드가 빈
        리스트(데이터0)면 이 항은 0.0 → **기존 가중치(단원×2.0+난이도)와 완전 동일**(하위호환).
      - 단원 겹침 *개수* × 2.0 → 기존 신호. `target_unit_codes`가 주어지면
        `set(problem.unit_codes) & target_unit_codes`의 *원소 수*에 ×2.0을 곱한다(단조).
        `target_unit_codes`가 None이면 이 항은 0.0.
      - `difficulty_overall`(1.0~5.0, None이면 0.0) → 그대로 가산. 같은 진도 정합 안에서
        약하게 심화 문항을 앞세우는 보조 축(겹침 신호를 압도하지 않는다 — 진도 정합은 *겹침 개수
        단조*가 1차 의도이고 난이도는 동급 정합 내 타이브레이커다).

    구체 가중치(성취기준×3.0/단원×2.0/난이도 그대로)는 *상대 순서*만 의미가 있다. 합산이라 같은
    점수(예: 겹침 개수·난이도가 모두 같음)는 동률이며, 동률 처리는 `select_school_progress_items`의
    *안정정렬*(원래 순서 보존)에 맡긴다.

    Args:
      problem: 우선순위를 매길 문항.
      target_unit_codes: 현재 진도 단원 코드 집합(선택). None이면 단원 항 0.0.
      target_achievement_codes: 현재 진도 성취기준 고시코드 집합(선택). None이면 성취기준 항 0.0
        (→ 기존 단원×2.0+난이도 가중치와 동일·하위호환).

    Returns:
      가중치(클수록 우선). 음수 없음(모든 항이 비음수).
    """
    weight = 0.0

    # 현재 진도 성취기준과 겹치는 *개수* × 3.0 — 가장 세밀한 신호라 최우선(None이면 0.0·하위호환).
    if target_achievement_codes is not None:
        ach_overlap = len(set(problem.achievement_standard_codes) & target_achievement_codes)
        weight += ach_overlap * 3.0

    # 현재 진도 단원과 겹치는 단원 *개수* × 2.0 — 기존 신호(겹침 개수 단조).
    if target_unit_codes is not None:
        overlap_count = len(set(problem.unit_codes) & target_unit_codes)
        weight += overlap_count * 2.0

    # 종합 난이도 보조 축(None이면 0.0) — 같은 진도 정합 안에서 심화를 약하게 앞세움.
    if problem.difficulty_overall is not None:
        weight += problem.difficulty_overall

    return weight


def select_school_progress_items(
    problems: Iterable[Problem],
    persona: Persona = Persona.A_일반고고3,
    *,
    target_unit_codes: set[str] | None = None,
    target_achievement_codes: set[str] | None = None,
    curriculum_version: Curriculum | None = None,
    min_fit: float = 0.5,
    limit: int | None = None,
) -> list[Problem]:
    """학교진도 모드 노출 문항을 *선별·정렬*한다 — 적격 필터 → 우선순위 내림차순 → limit.

    파이프라인:
      1. `is_school_progress_eligible(p, persona, target_unit_codes=...,
         target_achievement_codes=..., curriculum_version=..., min_fit=...)`로 적격 문항만 남긴다
         (비재학 페르소나·본문 미보유 출처·교육과정 불일치·진도 부정합은 탈락). 성취기준·단원은
         OR로 결합(둘 다 None이면 persona_fit 폴백).
      2. `school_progress_priority(p, target_unit_codes=..., target_achievement_codes=...)`
         *내림차순*으로 **안정정렬**한다(동률은 입력 순서 보존 — `school_progress_priority`
         docstring의 동률 처리 계약). 따라서 현재 진도 성취기준·단원과 세밀하게·많이 겹치는 문항이
         앞으로 온다.
      3. `limit`이 주어지면 상위 `limit`개만 돌려준다(None이면 무제한·전부).

    Args:
      problems: 후보 문항들(임의 iterable — 한 번만 순회).
      persona: 노출 대상 페르소나(기본 A_일반고고3 — MVP 재학생 정면 대상).
      target_unit_codes: 현재 진도 단원 코드 집합(선택). 적격성·우선순위 양쪽에 전달.
      target_achievement_codes: 현재 진도 성취기준 고시코드 집합(선택). 적격성·우선순위 양쪽에
        전달(단원보다 세밀한 추가 신호·단원과 OR). None이면 기존 단원·persona_fit 경로와 동일.
      curriculum_version: 교육과정 버전 정합 기준(선택). 적격성에 전달.
      min_fit: persona_fit 임계값(기본 0.5). `is_school_progress_eligible`에 전달.
      limit: 최대 개수(None=무제한). 0이면 빈 리스트.

    Returns:
      우선순위 내림차순으로 정렬된 적격 문항 리스트(limit 적용).

    결정적(deterministic)·부수효과 없음. `sorted(reverse=True)`는 파이썬 안정정렬이라
    동률 간 입력 순서가 보존된다.
    """
    eligible = [
        p
        for p in problems
        if is_school_progress_eligible(
            p,
            persona,
            target_unit_codes=target_unit_codes,
            target_achievement_codes=target_achievement_codes,
            curriculum_version=curriculum_version,
            min_fit=min_fit,
        )
    ]
    # 안정정렬 — 동률(같은 priority)은 입력 순서 유지. reverse=True로 큰 가중치 우선.
    ranked = sorted(
        eligible,
        key=lambda p: school_progress_priority(
            p,
            target_unit_codes=target_unit_codes,
            target_achievement_codes=target_achievement_codes,
        ),
        reverse=True,
    )
    if limit is None:
        return ranked
    return ranked[:limit]


__all__ = [
    "SCHOOL_PROGRESS_PERSONAS",
    "is_school_progress_eligible",
    "school_progress_priority",
    "select_school_progress_items",
]
