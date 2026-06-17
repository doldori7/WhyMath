"""L6 수능(정시) 모드 게이팅 로직 — 적격성·우선순위·선별.

이 모듈은 정시(수능) 응시 페르소나에게 *어떤* 기존 문항을 수능 모드로 노출할지 결정한다.
**오버레이 모델**(RT 트랙 게이팅 `l6/retake/gating.py`와 동형): 새 enum·concept 노드·Alembic
마이그레이션을 만들지 않고, 기존 L1 `Problem`의 필드(`exam_type`·`exam_authority_weight`·
`signature_patterns`·`persona_fit`·`difficulty_overall`·`source_type`)만 *재사용*하는 순수
결정 로직이다. 부수효과 없음(I/O·LLM 호출 없음)·결정적(deterministic).

공개 API 4종:
  - `is_suneung_eligible(problem, persona, *, min_fit)` — 이 문항을 이 페르소나에게 수능
    모드로 노출해도 되는가(불리언 게이트).
  - `suneung_priority(problem)` — 노출 우선순위 가중치(높을수록 먼저). 교수학 근거 반영.
  - `select_suneung_items(problems, persona, *, min_fit, limit)` — 적격 필터 → 우선순위
    내림차순 안정정렬 → limit 적용.
  - `SUNEUNG_PERSONAS`·`METADATA_ONLY_SOURCES` — 게이팅 상수(아래 docstring에 근거).

레이어 규칙(CLAUDE.md): L6→L1만 의존(`schema.problem`·`schema.enums`). L4/L2/L3를 import하지
않는다 — 이 모듈은 기존 `Problem` 필드의 *존재·값*만 보므로 하위 카탈로그·검증자·모델이
불필요하다. L6은 아무도 import하지 않는 최상위 소비자다(역방향 의존 부재).

use_enum_values=True 주의: `Problem`은 `ConfigDict(use_enum_values=True)`라 직렬화·구성
경로에 따라 `source_type`·`exam_type`이 *문자열 값*일 수 있고 `persona_fit`의 *키*도 문자열일
수 있다. 따라서 enum 비교 시 항상 enum/문자열 양쪽을 정규화해 비교한다(`schema/problem.py`의
`_enforce_copyright_no_body_for_metadata_sources` validator·`l6/retake/gating.py` 패턴 답습).

Rule of three — 3번째 L6 모드 시 l6 공용 추출 검토: `METADATA_ONLY_SOURCES`와 정규화 헬퍼
(`_source_value`·`_persona_fit`)는 RT 트랙(`l6/retake/gating.py`)과 *의도적으로* 중복한다.
RT 파일을 수정하지 않아 무회귀를 보장하려는 선택이며(두 모드가 독립적으로 같은 L1 공개 계약을
재정의), L6에 *세 번째* 모드가 들어올 때 `l6` 공용 모듈로의 추출을 검토한다(Rule of three).
"""

from __future__ import annotations

from collections.abc import Iterable

from whymath_backend.schema.enums import ExamType, Persona, SourceType
from whymath_backend.schema.problem import Problem

# ──────────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────────
SUNEUNG_PERSONAS: frozenset[Persona] = frozenset(
    {Persona.A_일반고고3, Persona.B_자사고N수, Persona.C_검정고시N수}
)
"""수능(정시) 모드의 대상 페르소나 — 정시(수능)로 대학에 가는 응시생.

PRD 5종 페르소나(`enums.Persona`) 중 *정시(수능)* 트랙에 있는 셋만 수능 모드 대상이다:
  - `A_일반고고3` — 일반고 고3(MVP·시장 최대·수능 정면 대상),
  - `B_자사고N수` — 자사고 출신 N수생(정시 재도전·결제 최대 세그먼트),
  - `C_검정고시N수` — 검정고시 N수생(정시 의존도 높음·수학 의존 100%).
나머지 둘은 *정시(수능) 중심이 아니므로* 제외한다:
  - `D_학종고2` — 학생부종합(수시) 중심으로 세특·자유연구가 핵심이라 정시 모드 대상이 아니다
    (`Persona.D_학종고2` docstring: "v1.5·세특/자유연구"),
  - `E_홈스쿨링영재` — 영재(올림피아드·심화) 트랙으로 수능 기출 유형 숙달이 주목적이 아니다
    (`Persona.E_홈스쿨링영재` docstring: "v2.0·가치 최대").
"""

METADATA_ONLY_SOURCES: frozenset[SourceType] = frozenset(
    {SourceType.평가원, SourceType.EBS, SourceType.교과서}
)
"""학생에게 *본문 노출이 불가*한 출처 — 저작권 노출 게이트의 차단 집합.

평가원·EBS·검정교과서는 *본문·문항 미보유*(WhyMath는 구조 메타데이터만 보유). 이 출처의
레코드는 단원·코드·문항번호 같은 *구조 참조 전용*이며 실제 발문·해설·선지를 가지지 않으므로,
**학생에게 노출할 문항으로 쓸 수 없다**. 노출 가능한 본문을 가진 문항은 `자체생성`
(WHYMATH_GENERATED) 레코드뿐이다.

**수능 모드에서 특히 중요**: 수능 대비의 핵심 자원은 *평가원 기출*(수능·모평)이지만, 평가원
기출의 *본문·문항 복제·영리이용*은 저작권법 §32 단서·§136·§140(영리 비친고죄)로 금지된다
(저작권 가이드 v2.0, MEMORY 2026-05-28). 따라서 수능 모드는 평가원 기출 *본문*을 절대 노출하지
않고, *자체생성 동등문제*(WHYMATH_GENERATED)만 학생에게 보인다 — 평가원 출처 레코드는 어떤
수능 신호(exam_type·시그니처 패턴·적합도)를 가지더라도 이 게이트에서 원천 차단한다. EBS·검정
교과서도 같은 이유로 차단(EBS 영상·교재 본문 무단 활용 금지·검정 교과서 본문 복제 절대 금지).

설계 메모: `schema.problem._METADATA_ONLY_SOURCES`는 *private*이라 import하지 않고 L6에서
같은 집합을 명시적으로 재정의한다(레이어 경계 — L6는 L1의 *공개* 계약만 의존). 두 정의가
어긋나지 않게, 값은 L1 enum(`SourceType.평가원/EBS/교과서`)을 그대로 가리킨다.
Rule of three — 3번째 L6 모드 시 l6 공용 추출 검토(RT 트랙과 의도적 중복, 모듈 docstring 참조).
"""

# 수능 적합 신호로 인정하는 시험 유형(권위 있는 기출 유형) — 수능·모평·학평.
# 정시 대비의 핵심은 *평가원·교육청 기출 유형*에 대한 숙달이므로 이 셋을 적합 신호로 본다
# (EBS교재·N제·자체생성은 그 자체로는 "기출 유형" 신호가 아니라 다른 적합 신호로 판정).
_SUNEUNG_EXAM_TYPES: frozenset[ExamType] = frozenset({ExamType.수능, ExamType.모평, ExamType.학평})


def _source_value(problem: Problem) -> str:
    """`problem.source_type`을 *문자열 값*으로 정규화한다(use_enum_values=True 대응).

    `Problem`은 `use_enum_values=True`라 `source_type`이 `SourceType` enum일 수도, 그 문자열
    값일 수도 있다. 양쪽을 같은 척도(문자열)로 맞춰 비교 안정성을 확보한다
    (`problem.py` validator·`l6/retake/gating.py` 패턴 답습).
    """
    src = problem.source_type
    return src.value if isinstance(src, SourceType) else src


def _exam_type_value(problem: Problem) -> str | None:
    """`problem.exam_type`을 *문자열 값*으로 정규화한다(None 보존).

    `exam_type`은 Optional이며 use_enum_values=True 환경에서 enum/문자열 양쪽이 가능하다.
    None이면 None을 돌려준다(시험 유형 미지정 — 기출 유형 신호 부재).
    """
    et = problem.exam_type
    if et is None:
        return None
    return et.value if isinstance(et, ExamType) else et


def _persona_fit(problem: Problem, persona: Persona) -> float:
    """`persona_fit`에서 주어진 페르소나의 적합도를 꺼낸다(키 문자열화 대응·없으면 0.0).

    use_enum_values=True 환경에서 `persona_fit`의 *키*가 `Persona` enum일 수도, 그 문자열
    값일 수도 있으므로 각 키를 *문자열 값*으로 정규화해 대상 페르소나와 대조한다. 적중이 없으면
    0.0(미평가 = 부적합). 선언 타입은 `dict[Persona, float]`이나 런타임 키가 문자열일 수 있어
    `isinstance` 분기로 안전하게 정규화한다(call-overload·Any 회피).
    """
    target = persona.value
    for key, score in problem.persona_fit.items():
        key_value = key.value if isinstance(key, Persona) else key
        if key_value == target:
            return score
    return 0.0


def is_suneung_eligible(
    problem: Problem,
    persona: Persona = Persona.A_일반고고3,
    *,
    min_fit: float = 0.5,
) -> bool:
    """이 문항을 이 페르소나에게 수능(정시) 모드로 노출해도 되는가(불리언 게이트).

    판정 순서(앞 게이트에서 막히면 즉시 False):
      ① 대상 페르소나 게이트 — `persona ∈ SUNEUNG_PERSONAS`(A·B·C)가 아니면 False(비응시).
         D(학종·수시 중심)·E(영재)는 정시 모드 대상이 아니다.
      ② 저작권 노출 게이트 — `source_type`이 본문 미보유 출처(평가원/EBS/교과서)면 False.
         학생 노출 불가 본문이므로 *대상 페르소나라도* 막힌다(CLAUDE.md 우선순위 #2 — 법적).
         **수능 모드 특히 중요**: 평가원 기출 본문은 절대 노출 불가 → 자체생성 동등문제만.
      ③ 수능 적합 신호 — 다음 중 *하나라도* 참이면 True, 아니면 False:
           (a) `exam_type ∈ {수능, 모평, 학평}`(권위 있는 기출 유형 문항), **또는**
           (b) `signature_patterns`가 비어 있지 않음(한국 수능 시그니처 패턴 보유), **또는**
           (c) `persona_fit[persona] >= min_fit`(이 페르소나 적합도가 임계 이상).

    Args:
      problem: 후보 문항(L1 `Problem`).
      persona: 노출 대상 페르소나(기본 A_일반고고3 — MVP 정시 정면 대상).
      min_fit: persona_fit 임계값(기본 0.5 — "절반 이상 적합"). 0~1 척도.

    Returns:
      수능 모드 노출 적격이면 True.

    use_enum_values=True 주의: source_type·exam_type·persona_fit 키가 문자열일 수 있어
    헬퍼(`_source_value`·`_exam_type_value`·`_persona_fit`)로 정규화해 비교한다.
    """
    # ① 대상 페르소나 게이트.
    if persona not in SUNEUNG_PERSONAS:
        return False

    # ② 저작권 노출 게이트 — 본문 미보유 출처는 노출 불가(대상 페르소나라도 차단).
    #    수능 모드 핵심: 평가원 기출 본문은 절대 노출 불가 → 여기서 원천 차단.
    metadata_only_values = {s.value for s in METADATA_ONLY_SOURCES}
    if _source_value(problem) in metadata_only_values:
        return False

    # ③ 수능 적합 신호 — 기출 유형 / 시그니처 패턴 / 페르소나 적합도 중 하나라도.
    suneung_exam_values = {e.value for e in _SUNEUNG_EXAM_TYPES}
    is_exam_signal = _exam_type_value(problem) in suneung_exam_values
    has_signature = bool(problem.signature_patterns)
    meets_fit = _persona_fit(problem, persona) >= min_fit
    return is_exam_signal or has_signature or meets_fit


def suneung_priority(problem: Problem) -> float:
    """수능 모드 노출 우선순위 가중치 — 높을수록 먼저 노출. 결정적(deterministic).

    교수학 근거(CLAUDE.md 우선순위 #3·#4): 정시(수능) 대비의 핵심은 *권위 있는 기출 유형*의
    숙달과 *한국 수능 시그니처 패턴*의 체화다(수능>모평>학평 순으로 출제 권위가 높고, ㄱㄴㄷ
    합답형·조건 나열·그래프 개형 추론 같은 시그니처 패턴은 수능 고난도 문항의 전형이라 우선
    노출 가치가 크다). 이를 반영해:

      가중치 = (exam_authority_weight|0.0 × 2.0) + (signature_patterns 있으면 +1.0)
               + (difficulty_overall|0.0)

      - `exam_authority_weight`(수능1.0/모평0.8/학평0.5, None이면 0.0) × 2.0 → 가장 큰
        가중치. 출처 권위가 높은 기출 유형일수록(수능>모평>학평) 정시 대비 가치가 직결되므로
        *최우선*으로 앞세운다(×2.0이라 수능=2.0·모평=1.6·학평=1.0 기여).
      - `signature_patterns` *존재* → +1.0. 한국 수능 시그니처 패턴(10종 중 하나라도)을 가진
        문항은 수능 전형 유형이라 가산(존재 여부만 본다 — 패턴 내용·정합은 보지 않는다).
      - `difficulty_overall`(1.0~5.0, None이면 0.0) → 그대로 가산. 정시는 변별·심화가 목적이라
        어려운 문항을 약하게 앞세운다(보조 축 — 위 두 신호를 압도하지 않는다).

    구체 가중치(권위×2.0/시그니처+1.0/난이도 그대로)는 *상대 순서*만 의미가 있다 — 출처 권위
    신호(최대 2.0)가 시그니처 신호(1.0)보다 크고, 난이도는 동급 신호 사이의 타이브레이커로
    약하게 작동하도록 정했다. 합산이라 같은 점수(예: 권위·시그니처·난이도가 모두 같음)는
    동률이며, 동률 처리는 `select_suneung_items`의 *안정정렬*(원래 순서 보존)에 맡긴다.

    Args:
      problem: 우선순위를 매길 문항.

    Returns:
      가중치(클수록 우선). 음수 없음(모든 항이 비음수).
    """
    weight = 0.0

    # 출처 권위 신호(수능1.0/모평0.8/학평0.5, None이면 0.0) × 2.0 — 권위 최우선.
    if problem.exam_authority_weight is not None:
        weight += problem.exam_authority_weight * 2.0

    # 한국 수능 시그니처 패턴 *존재* 신호 — 수능 전형 유형(존재 여부만 본다).
    if problem.signature_patterns:  # 빈 리스트면 거짓(존재하지 않음)
        weight += 1.0

    # 종합 난이도 보조 축(None이면 0.0) — 심화·변별을 약하게 앞세움.
    if problem.difficulty_overall is not None:
        weight += problem.difficulty_overall

    return weight


def select_suneung_items(
    problems: Iterable[Problem],
    persona: Persona = Persona.A_일반고고3,
    *,
    min_fit: float = 0.5,
    limit: int | None = None,
) -> list[Problem]:
    """수능 모드 노출 문항을 *선별·정렬*한다 — 적격 필터 → 우선순위 내림차순 → limit.

    파이프라인:
      1. `is_suneung_eligible(p, persona, min_fit=min_fit)`로 적격 문항만 남긴다(비응시
         페르소나·본문 미보유 출처·적합 신호 부재는 탈락).
      2. `suneung_priority(p)` *내림차순*으로 **안정정렬**한다(동률은 입력 순서 보존 —
         `suneung_priority` docstring의 동률 처리 계약). 따라서 출처 권위가 높은(수능>모평>학평)
         문항이 앞으로 온다.
      3. `limit`이 주어지면 상위 `limit`개만 돌려준다(None이면 무제한·전부).

    Args:
      problems: 후보 문항들(임의 iterable — 한 번만 순회).
      persona: 노출 대상 페르소나(기본 A_일반고고3 — MVP 정시 정면 대상).
      min_fit: persona_fit 임계값(기본 0.5). `is_suneung_eligible`에 전달.
      limit: 최대 개수(None=무제한). 0이면 빈 리스트.

    Returns:
      우선순위 내림차순으로 정렬된 적격 문항 리스트(limit 적용).

    결정적(deterministic)·부수효과 없음. `sorted(reverse=True)`는 파이썬 안정정렬이라
    동률 간 입력 순서가 보존된다.
    """
    eligible = [p for p in problems if is_suneung_eligible(p, persona, min_fit=min_fit)]
    # 안정정렬 — 동률(같은 priority)은 입력 순서 유지. reverse=True로 큰 가중치 우선.
    ranked = sorted(eligible, key=suneung_priority, reverse=True)
    if limit is None:
        return ranked
    return ranked[:limit]


__all__ = [
    "METADATA_ONLY_SOURCES",
    "SUNEUNG_PERSONAS",
    "is_suneung_eligible",
    "select_suneung_items",
    "suneung_priority",
]
