"""L6 사고력(thinking) 모드 게이팅 로직 — 적격성·우선순위·선별.

이 모듈은 *고차 사고력*(상위 인지 수준·깊은 케이스 분석·단원 융합)을 요구하는 기존 문항을
사고력 모드로 노출할지 결정한다. **오버레이 모델**(RT 트랙·수능 모드·학교진도 모드 게이팅과
동형): 새 enum·concept 노드·Alembic 마이그레이션을 만들지 않고, 기존 L1 `Problem`의 필드
(`source_type`·`bloom_level`·`signature_patterns`·`diff_case_analysis`·`diff_integration`·
`difficulty_overall`·`persona_fit`)만 *재사용*하는 순수 결정 로직이다. 부수효과 없음(I/O·LLM
호출 없음)·결정적(deterministic).

공개 API 3종:
  - `is_thinking_eligible(problem, persona, *, min_fit)` — 이 문항을 이 페르소나에게 사고력
    모드로 노출해도 되는가(불리언 게이트).
  - `thinking_priority(problem)` — 노출 우선순위 가중치(높을수록 먼저). 교수학 근거(사고력
    위계 — 높은 Bloom 인지 수준 우선) 반영.
  - `select_thinking_items(problems, persona, *, min_fit, limit)` — 적격 필터 → 우선순위
    내림차순 안정정렬 → limit 적용.

대상 페르소나(중요 — 하드코딩 set으로 좁히지 않는다): 사고력 모드의 주 대상은 D(학종 고2 —
세특/자유연구로 고차 사고가 핵심)·E(홈스쿨링 영재 — 올림피아드·심화)이나, **대상 페르소나를
닫힌 집합(frozenset)으로 게이트하지 않는다**. RT·수능·학교진도가 트랙 본질상 비대상 페르소나를
원천 배제한 것과 달리(재수 트랙은 재학생을 막고, 학교진도는 N수생을 막는다), *사고력은
페르소나가 아니라 문항의 사고 수준*이 본질이다 — A(일반고 고3·MVP) 학생도 고차 사고 문항이
적합(`persona_fit` 충족)하면 노출돼야 하므로(MVP 페르소나 배제 금지), 페르소나 적합은 기존
`persona_fit >= min_fit` 메커니즘으로만 판정한다(학교진도의 persona_fit 폴백 분기와 동일한
메커니즘을 *주 게이트*로 쓴다). 사고력 *주신호*는 페르소나가 아니라 `bloom_level`(상위 3단계)다.

레이어 규칙(CLAUDE.md): L6→L1만 의존한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다 — 이 모듈은 기존 `Problem` 필드의 *존재·값*만 보므로 하위
카탈로그·검증자·모델이 불필요하다. L6은 아무도 import하지 않는 최상위 소비자다(역방향 의존
부재).

저작권 게이트(`METADATA_ONLY_SOURCES`)는 L6 공용 모듈 `l6/_shared.py`에 정본을 두고, 이
파일에서 `_shared.is_exposable`로 사용한다(RT·수능·학교진도와 공유 — Rule of three 추출 완료).
사고력 모드도 평가원/EBS/검정교과서 *본문*은 노출 불가(저작권법 §32 단서·MEMORY 2026-05-28) —
학생에게는 자체생성 동등문제만 노출한다.

use_enum_values=True 주의: `Problem`은 `ConfigDict(use_enum_values=True)`라 직렬화·구성
경로에 따라 `source_type`·`bloom_level`이 *문자열 값*일 수 있고 `persona_fit`의 *키*도 문자열일
수 있다. 따라서 enum 비교 시 항상 enum/문자열 양쪽을 정규화해 비교한다(L6 공용
`_shared.normalize_enum_value`·`_shared.persona_fit`·`_shared.is_exposable` 사용).
"""

from __future__ import annotations

from collections.abc import Iterable

from whymath_backend.l6 import _shared
from whymath_backend.schema.enums import BloomLevel, Persona, SignaturePattern
from whymath_backend.schema.problem import Problem

# ──────────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────────
THINKING_BLOOM_LEVELS: frozenset[BloomLevel] = frozenset(
    {BloomLevel.ANALYZE, BloomLevel.EVALUATE, BloomLevel.CREATE}
)
"""사고력 모드의 *주신호* — 개정 Bloom 인지 수준의 *상위 3단계*(분석·평가·창안).

Anderson·Krathwohl(2001) 개정 Bloom taxonomy 6단계(REMEMBER < UNDERSTAND < APPLY < ANALYZE
< EVALUATE < CREATE) 중 *고차 사고*에 해당하는 상위 셋이다. 사고력 모드는 단순 회상·이해·적용
(하위 3단계)이 아니라 *구조를 분해하고(ANALYZE)·기준으로 판단하며(EVALUATE)·새 해법을
만들어내는(CREATE)* 문항을 선별 노출하므로, 이 세 수준을 적격의 주신호로 본다.

`bloom_level`이 None(사고력 미표지)이면 부적격이다 — 인지 수준이 태그되지 않은 문항은 사고력
문항인지 판정할 수 없으므로 제외한다(`is_thinking_eligible` ③ 게이트).
"""

# Bloom 상위 3단계의 *우선순위 가중치* — CREATE > EVALUATE > ANALYZE(높은 인지 수준일수록
# 큰 가중). 사고력 우선순위의 주신호라 가장 큰 가중치를 둔다(`thinking_priority` ① 항).
# 하위 3단계·None은 적격 단계에서 이미 걸러지므로 이 표에 없다(우선순위 산정 대상이 아니다).
_BLOOM_PRIORITY_WEIGHT: dict[BloomLevel, float] = {
    BloomLevel.ANALYZE: 2.0,
    BloomLevel.EVALUATE: 3.0,
    BloomLevel.CREATE: 4.0,
}

# 사고력 *시그니처 패턴* — 고차 사고를 직접 드러내는 한국 수능 시그니처 패턴 3종(깊은 케이스
# 분류·그래프 개형 추론·단원 융합). 보유 *개수*만큼 우선순위에 가산한다(`thinking_priority`
# ② 항). 나머지 7종은 그 자체로 고차 사고 신호가 아니라 가산 대상이 아니다(존재 여부·내용은
# 보지 않고, 이 3종의 *개수*만 센다).
_THINKING_SIGNATURE_PATTERNS: frozenset[SignaturePattern] = frozenset(
    {
        SignaturePattern.CASE_ANALYSIS_DEEP,
        SignaturePattern.GRAPH_SHAPE_INFERENCE,
        SignaturePattern.CROSS_UNIT_FUSION,
    }
)


def is_thinking_eligible(
    problem: Problem,
    persona: Persona = Persona.D_학종고2,
    *,
    min_fit: float = 0.5,
) -> bool:
    """이 문항을 이 페르소나에게 사고력(thinking) 모드로 노출해도 되는가(불리언 게이트).

    판정 순서(앞 게이트에서 막히면 즉시 False):
      ① 저작권 노출 게이트 — `source_type`이 본문 미보유 출처(평가원/EBS/교과서)면 False.
         학생 노출 불가 본문이므로 *사고력 수준·적합도가 아무리 높아도* 막힌다(CLAUDE.md
         우선순위 #2 — 법적). 자체생성 동등문제만 노출한다.
      ② 페르소나 적합 게이트 — `persona_fit[persona] >= min_fit`. **닫힌 페르소나 집합으로
         좁히지 않는다**(모듈 docstring) — 사고력은 페르소나가 아니라 문항의 사고 수준이
         본질이라, 주 대상 D·E뿐 아니라 A(MVP 고3)도 적합도가 임계 이상이면 통과해야 한다
         (MVP 페르소나 배제 금지). 적합도 미달이면 False.
      ③ 사고력 주신호 — `bloom_level ∈ {ANALYZE, EVALUATE, CREATE}`(상위 3단계)면 True,
         아니면 False. `bloom_level`이 None(사고력 미표지)이거나 하위 3단계(REMEMBER·
         UNDERSTAND·APPLY)면 부적격이다(사고력 문항이 아님).

    Args:
      problem: 후보 문항(L1 `Problem`).
      persona: 노출 대상 페르소나(기본 D_학종고2 — 사고력 주 대상). 어떤 페르소나든
        `persona_fit` 충족이면 통과할 수 있다(닫힌 집합 게이트 없음).
      min_fit: persona_fit 임계값(기본 0.5 — "절반 이상 적합"). 0~1 척도.

    Returns:
      사고력 모드 노출 적격이면 True.

    use_enum_values=True 주의: source_type·bloom_level·persona_fit 키가 문자열일 수 있어
    L6 공용 헬퍼(`_shared.is_exposable`·`_shared.normalize_enum_value`·`_shared.persona_fit`)로
    정규화해 비교한다.
    """
    # ① 저작권 노출 게이트 — 본문 미보유 출처는 노출 불가(사고력 수준·적합도가 높아도 차단).
    if not _shared.is_exposable(problem):
        return False

    # ② 페르소나 적합 게이트 — 닫힌 집합으로 좁히지 않고 persona_fit 메커니즘만 쓴다
    #    (학교진도 폴백 분기와 같은 메커니즘을 주 게이트로 — A 고3도 fit 높으면 통과).
    if _shared.persona_fit(problem, persona) < min_fit:
        return False

    # ③ 사고력 주신호 — Bloom 상위 3단계(분석·평가·창안)만 적격. None·하위 단계는 부적격.
    thinking_bloom_values = {b.value for b in THINKING_BLOOM_LEVELS}
    return _shared.normalize_enum_value(problem.bloom_level) in thinking_bloom_values


def thinking_priority(problem: Problem) -> float:
    """사고력 모드 노출 우선순위 가중치 — 높을수록 먼저 노출. 결정적(deterministic).

    교수학 근거(CLAUDE.md "사고력 우선"·우선순위 #3·#4): 사고력 모드의 핵심은 *더 높은 인지
    수준*을 요구하는 문항을 앞세우는 것이다(창안 > 평가 > 분석 순으로 사고 부하가 크고, 깊은
    케이스 분류·단원 융합은 다단계 사고를 요구하는 전형이라 우선 노출 가치가 크다). 이를 반영해:

      가중치 = (Bloom 상위 단계 가중: CREATE 4.0 / EVALUATE 3.0 / ANALYZE 2.0)
               + (사고력 시그니처 패턴 보유 *개수* × 1.0)
               + (diff_case_analysis|0.0) + (diff_integration|0.0)
               + (difficulty_overall|0.0)

      - **Bloom 상위 단계 가중**(주신호·가장 큰 가중) — `bloom_level`이 CREATE면 4.0·
        EVALUATE면 3.0·ANALYZE면 2.0을 더한다(`_BLOOM_PRIORITY_WEIGHT`). 높은 인지 수준일수록
        큰 가중을 둬 *최우선*으로 앞세운다(사고력 모드의 본질 신호). 하위 단계·None은 적격
        단계에서 이미 걸러지므로 여기서는 항상 상위 3단계 중 하나다(가중 0이 될 일 없음).
      - **사고력 시그니처 패턴 보유 개수** × 1.0 — `signature_patterns` 중 사고력 3종
        (CASE_ANALYSIS_DEEP·GRAPH_SHAPE_INFERENCE·CROSS_UNIT_FUSION)에 드는 *원소 수*에 ×1.0.
        여러 개를 가질수록(예: 깊은 케이스 분류 + 단원 융합) 더 앞세운다(단조). 나머지 7종은
        가산하지 않는다(그 자체로 고차 사고 신호가 아님).
      - **diff_case_analysis**(케이스 분류 깊이 1.0~5.0, None이면 0.0) → 그대로 가산. 깊은
        케이스 분석이 요구되는 문항을 앞세우는 보조 축(사고력 특화 난이도 축).
      - **diff_integration**(단원 융합도 1.0~5.0, None이면 0.0) → 그대로 가산. 여러 단원을
        엮는 융합 문항을 앞세우는 보조 축(사고력 특화 난이도 축).
      - **difficulty_overall**(종합 난이도 1.0~5.0, None이면 0.0) → 그대로 가산. 심화·변별을
        약하게 앞세우는 보조 축(suneung_priority와 동형).

    구체 가중치(Bloom 4/3/2·시그니처 ×1.0·diff 그대로)는 *상대 순서*만 의미가 있다 — 주신호
    Bloom 가중(최대 4.0)이 시그니처 단일(1.0)보다 크게 설계했다(suneung의 권위 ×2.0/시그니처
    +1.0 톤 답습 — 주신호에 가장 큰 가중). 합산이라 같은 점수는 동률이며, 동률 처리는
    `select_thinking_items`의 *안정정렬*(원래 순서 보존)에 맡긴다.

    Args:
      problem: 우선순위를 매길 문항. (적격 문항만 들어온다는 전제는 아니나, 적격 단계를 거친
        문항은 항상 bloom_level이 상위 3단계라 Bloom 항이 0이 아니다.)

    Returns:
      가중치(클수록 우선). 음수 없음(모든 항이 비음수).
    """
    weight = 0.0

    # Bloom 상위 단계 가중(주신호·최대 가중) — CREATE 4.0 / EVALUATE 3.0 / ANALYZE 2.0.
    # 적격 문항은 항상 상위 3단계라 적중하지만, 방어적으로 상위 3단계가 아니면 0.0(가산 없음).
    bloom_value = _shared.normalize_enum_value(problem.bloom_level)
    for level, level_weight in _BLOOM_PRIORITY_WEIGHT.items():
        if bloom_value == level.value:
            weight += level_weight
            break

    # 사고력 시그니처 패턴 보유 *개수* × 1.0 — 고차 사고 시그니처(3종)에 드는 원소 수만큼 가산.
    # use_enum_values=True로 signature_patterns 원소가 문자열일 수 있어 정규화 후 대조한다.
    thinking_signature_values = {s.value for s in _THINKING_SIGNATURE_PATTERNS}
    thinking_signature_count = sum(
        1
        for pattern in problem.signature_patterns
        if _shared.normalize_enum_value(pattern) in thinking_signature_values
    )
    weight += thinking_signature_count * 1.0

    # 케이스 분류 깊이 보조 축(None이면 0.0) — 깊은 케이스 분석을 앞세움(사고력 특화 난이도).
    if problem.diff_case_analysis is not None:
        weight += problem.diff_case_analysis

    # 단원 융합도 보조 축(None이면 0.0) — 융합 문항을 앞세움(사고력 특화 난이도).
    if problem.diff_integration is not None:
        weight += problem.diff_integration

    # 종합 난이도 보조 축(None이면 0.0) — 심화·변별을 약하게 앞세움(suneung_priority와 동형).
    if problem.difficulty_overall is not None:
        weight += problem.difficulty_overall

    return weight


def select_thinking_items(
    problems: Iterable[Problem],
    persona: Persona = Persona.D_학종고2,
    *,
    min_fit: float = 0.5,
    limit: int | None = None,
) -> list[Problem]:
    """사고력 모드 노출 문항을 *선별·정렬*한다 — 적격 필터 → 우선순위 내림차순 → limit.

    파이프라인:
      1. `is_thinking_eligible(p, persona, min_fit=min_fit)`로 적격 문항만 남긴다(본문 미보유
         출처·페르소나 적합도 미달·사고력 미표지(bloom None)·하위 인지 수준은 탈락).
      2. `thinking_priority(p)` *내림차순*으로 **안정정렬**한다(동률은 입력 순서 보존 —
         `thinking_priority` docstring의 동률 처리 계약). 따라서 높은 인지 수준(CREATE >
         EVALUATE > ANALYZE)의 문항이 앞으로 온다.
      3. `limit`이 주어지면 상위 `limit`개만 돌려준다(None이면 무제한·전부).

    Args:
      problems: 후보 문항들(임의 iterable — 한 번만 순회).
      persona: 노출 대상 페르소나(기본 D_학종고2 — 사고력 주 대상). `is_thinking_eligible`에
        전달(닫힌 집합 게이트 없이 persona_fit으로만 판정).
      min_fit: persona_fit 임계값(기본 0.5). `is_thinking_eligible`에 전달.
      limit: 최대 개수(None=무제한). 0이면 빈 리스트.

    Returns:
      우선순위 내림차순으로 정렬된 적격 문항 리스트(limit 적용).

    결정적(deterministic)·부수효과 없음. `sorted(reverse=True)`는 파이썬 안정정렬이라
    동률 간 입력 순서가 보존된다.
    """
    eligible = [p for p in problems if is_thinking_eligible(p, persona, min_fit=min_fit)]
    # 안정정렬 — 동률(같은 priority)은 입력 순서 유지. reverse=True로 큰 가중치 우선.
    ranked = sorted(eligible, key=thinking_priority, reverse=True)
    if limit is None:
        return ranked
    return ranked[:limit]


__all__ = [
    "THINKING_BLOOM_LEVELS",
    "is_thinking_eligible",
    "select_thinking_items",
    "thinking_priority",
]
