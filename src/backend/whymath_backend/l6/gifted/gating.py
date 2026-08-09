"""L6 영재(gifted) 트랙 게이팅 로직 — 적격성·우선순위·선별.

이 모듈은 페르소나 E(홈스쿨링 영재)에게 *심화·창안* 문항(KMO 입문·올림피아드 수준의 고난도
사고)을 영재 모드로 노출할지 결정한다. **오버레이 모델**(RT 트랙·수능 모드·학교진도·사고력
게이팅과 동형): 새 enum·concept 노드·Alembic 마이그레이션을 만들지 않고, 기존 L1 `Problem`의
필드(`source_type`·`persona_fit`·`difficulty_overall`·`bloom_level`·`is_cross_unit`·
`diff_integration`)만 *재사용*하는 순수 결정 로직이다. 부수효과 없음(I/O·LLM 호출 없음)·
결정적(deterministic).

데이터 현실(중요): 영재 트랙 콘텐츠(KMO·올림피아드 — `Subject` enum에 전용 과목이 없음)는 아직
코퍼스에 없다. 이 모듈은 학교진도 성취기준 선례처럼 **게이팅만 선깔고 데이터가 차오르면 자동
활성**한다 — 영재급 문항(고난도 + 창안/융합)이 코퍼스에 들어오고 `persona_fit[E]`가 태깅되면
코드 변경 없이 노출되기 시작한다. 콘텐츠가 없으면 빈 결과(데이터0 안전).

공개 API 3종:
  - `is_gifted_eligible(problem, persona, *, min_fit, min_difficulty)` — 이 문항을 이 페르소나에게
    영재 모드로 노출해도 되는가(불리언 게이트).
  - `gifted_priority(problem)` — 노출 우선순위 가중치(높을수록 먼저). 교수학 근거(창안능력·단원
    융합이 영재 트랙의 본질) 반영.
  - `select_gifted_items(problems, persona, *, min_fit, min_difficulty, limit)` — 적격 필터 →
    우선순위 내림차순 안정정렬 → limit 적용.
  - `GIFTED_PERSONAS`·`GIFTED_MIN_DIFFICULTY` — 게이팅 상수(아래 docstring에 근거).

대상 페르소나(닫힌 집합): 영재 트랙은 **페르소나 E(홈스쿨링 영재)** 전용이다 — RT 트랙이
B·C(재수)를 닫힌 집합으로 제한한 것과 같은 이유로, 영재는 *학습 환경·목표*(홈스쿨·KMO·대학
수학 선행)가 근본이라 닫힌 집합으로 좁힌다(사고력 thinking이 페르소나를 열어 둔 것과 대비 —
사고력은 *문항의 사고 수준*이 본질이라 A 고3도 받지만, 영재는 *대상*이 본질이라 E만 받는다).
PRD §3.5 페르소나 E·로드맵 Phase 3 프리미엄(영재 등급)과 정합.

영재 *신호*(기존 필드 근사): 전용 과목·필드가 없으므로 ⑴ `persona_fit[E]`가 높고(기본 0.7 —
RT·thinking의 0.5보다 빡빡), ⑵ `difficulty_overall`이 심화 하한 이상(기본 4.0 — KMO 입문 수준),
⑶ `bloom_level == CREATE`(창안) *또는* `is_cross_unit`(단원 융합) 중 하나로 영재급 사고를
근사한다. 데이터가 차면 이 근사를 KMO 태깅 등으로 정밀화하는 것은 후속(범위 밖).

레이어 규칙(CLAUDE.md): L6→L1만 의존한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다 — 기존 `Problem` 필드의 *존재·값*만 본다.

저작권 게이트(`_shared.is_exposable`)는 RT·수능·학교진도·사고력과 공유한다 — 영재 모드도
평가원/EBS/검정교과서 *본문*은 노출 불가(저작권법 §32 단서·MEMORY 2026-05-28), 자체생성
동등문제만 노출한다.

use_enum_values=True 주의: `source_type`·`bloom_level`이 문자열 값일 수 있고 `persona_fit`의
키도 문자열일 수 있어 L6 공용 헬퍼로 정규화해 비교한다.
"""

from __future__ import annotations

from collections.abc import Iterable

from whymath_backend.l6 import _shared
from whymath_backend.schema.enums import BloomLevel, Persona
from whymath_backend.schema.problem import Problem

# ──────────────────────────────────────────────────────────────────────────
# 게이팅 상수
# ──────────────────────────────────────────────────────────────────────────
GIFTED_PERSONAS: frozenset[Persona] = frozenset({Persona.E_홈스쿨링영재})
"""영재 트랙의 대상 페르소나 — 홈스쿨링 영재(E) 전용(닫힌 집합).

PRD 5종 페르소나(`enums.Persona`) 중 *영재 트랙*은 E(홈스쿨링 영재 — KMO 동상·대학 수학 선행·
로드맵 Phase 3 프리미엄 영재 등급)만 대상이다. RT 트랙이 재수(B·C)를 닫힌 집합으로 제한한 것과
같은 이유 — 영재는 *학습 환경·목표*가 근본이라 닫힌 집합으로 좁힌다(사고력 thinking이 페르소나를
열어 둔 것과 대비). A·B·C·D는 영재 트랙 대상이 아니므로 제외한다.
"""

GIFTED_MIN_DIFFICULTY: float = 4.0
"""영재 적격의 *종합 난이도 하한*(기본) — KMO 입문(중등 올림피아드) 수준의 심화.

`difficulty_overall`(1.0~5.0) 척도에서 4.0 이상을 영재급 심화로 본다. 영재 트랙은 *변별·심화*가
목적이라 일반 모드보다 높은 하한을 둔다(`is_gifted_eligible`의 `min_difficulty` 기본값). 호출자가
파라미터로 조정할 수 있다(데이터·정책 변화 대비 손잡이).
"""


def is_gifted_eligible(
    problem: Problem,
    persona: Persona = Persona.E_홈스쿨링영재,
    *,
    min_fit: float = 0.7,
    min_difficulty: float = GIFTED_MIN_DIFFICULTY,
) -> bool:
    """이 문항을 이 페르소나에게 영재 모드로 노출해도 되는가(불리언 게이트).

    판정 순서(앞 게이트에서 막히면 즉시 False):
      ① 대상 페르소나 게이트 — `persona ∈ GIFTED_PERSONAS`(E)가 아니면 False(비대상). 영재는
         학습 환경이 본질이라 닫힌 집합으로 좁힌다(RT 트랙과 동형).
      ② 저작권 노출 게이트 — `source_type`이 본문 미보유 출처(평가원/EBS/교과서)면 False.
         대상 페르소나라도 막힌다(CLAUDE.md 우선순위 #2 — 법적). 자체생성 동등문제만 노출.
      ③ 페르소나 적합 게이트 — `persona_fit[persona] >= min_fit`(기본 0.7 — 일반 모드보다 빡빡).
         영재 적합도가 높은 문항만 통과한다.
      ④ 영재급 사고 신호 — `difficulty_overall`이 심화 하한(`min_difficulty`·기본 4.0) 이상
         **이고**(AND), (`bloom_level == CREATE`(창안) **또는** `is_cross_unit`(단원 융합))이면
         True. 난이도가 None이거나 하한 미만이면, 또는 창안·융합 어느 쪽도 아니면 False.
         (심화 하한은 AND·창안/융합은 OR — 영재는 "어렵고 + 창안 또는 융합"이라야 한다.)

    Args:
      problem: 후보 문항(L1 `Problem`).
      persona: 노출 대상 페르소나(기본 E_홈스쿨링영재 — 영재 트랙 대상). E가 아니면 항상 False.
      min_fit: persona_fit 임계값(기본 0.7 — 영재는 높은 적합 요구). 0~1 척도.
      min_difficulty: 종합 난이도 하한(기본 `GIFTED_MIN_DIFFICULTY`=4.0). 1~5 척도.

    Returns:
      영재 모드 노출 적격이면 True.

    use_enum_values=True 주의: source_type·bloom_level·persona_fit 키가 문자열일 수 있어
    L6 공용 헬퍼로 정규화해 비교한다.
    """
    # ① 대상 페르소나 게이트 — E만(닫힌 집합·RT 동형).
    if persona not in GIFTED_PERSONAS:
        return False

    # ② 저작권 노출 게이트 — 본문 미보유 출처는 노출 불가(대상 페르소나라도 차단).
    if not _shared.is_exposable(problem):
        return False

    # ②-b 검수 노출 게이트 — 저작권 축과 독립(합치지 않음, PB-03). review_status=approved만 통과.
    if not _shared.is_review_cleared(problem):
        return False

    # ③ 페르소나 적합 게이트 — 영재는 높은 적합(기본 0.7)만 통과.
    if _shared.persona_fit(problem, persona) < min_fit:
        return False

    # ④ 영재급 사고 신호 — 심화 하한 이상(AND) + (창안 OR 단원 융합).
    if problem.difficulty_overall is None or problem.difficulty_overall < min_difficulty:
        return False
    is_creative = _shared.normalize_enum_value(problem.bloom_level) == BloomLevel.CREATE.value
    return is_creative or problem.is_cross_unit


def gifted_priority(problem: Problem) -> float:
    """영재 모드 노출 우선순위 가중치 — 높을수록 먼저 노출. 결정적(deterministic).

    교수학 근거(CLAUDE.md "사고력 우선"·우선순위 #3·#4): 영재 트랙의 핵심은 *창안능력*(새 해법을
    만들어내는 가장 높은 인지 수준)과 *단원 융합*(여러 영역을 엮는 고차 사고)이다. 이를 반영해:

      가중치 = (bloom CREATE 2.0 / EVALUATE 1.5)
               + (is_cross_unit이면 +1.0)
               + (diff_integration|0.0)
               + (difficulty_overall|0.0)

      - **bloom 상위 단계 가중**(주신호) — `bloom_level`이 CREATE면 2.0·EVALUATE면 1.5를 더한다.
        창안(CREATE)이 영재 트랙의 본질이라 가장 큰 가중을 둔다. 그 외(ANALYZE 이하·None)는 0.0
        (적격은 CREATE *또는* 융합이라, 융합으로 적격된 문항은 bloom 가중이 0일 수 있다).
      - **is_cross_unit** → +1.0 — 단원 융합 문항을 앞세운다(영재급 고차 사고).
      - **diff_integration**(단원 융합도 1.0~5.0, None이면 0.0) → 그대로 가산. 융합의 *깊이*를
        반영하는 보조 축(사고력 thinking과 동형).
      - **difficulty_overall**(1.0~5.0, None이면 0.0) → 그대로 가산. 심화·변별 타이브레이커.
        (적격 문항은 항상 difficulty_overall >= min_difficulty라 이 항이 0이 아니다.)

    구체 가중치(CREATE 2.0/EVALUATE 1.5·융합 1.0·diff 그대로)는 *상대 순서*만 의미가 있다 —
    창안 신호가 단원 융합 단일보다 크게 설계했다(thinking의 Bloom 4/3/2 톤을 영재용으로 축약).
    합산이라 같은 점수는 동률이며, 동률 처리는 `select_gifted_items`의 *안정정렬*에 맡긴다.

    Args:
      problem: 우선순위를 매길 문항.

    Returns:
      가중치(클수록 우선). 음수 없음(모든 항이 비음수).
    """
    weight = 0.0

    # bloom 상위 단계 가중(주신호) — CREATE 2.0 / EVALUATE 1.5. 그 외·None은 0.0.
    bloom_value = _shared.normalize_enum_value(problem.bloom_level)
    if bloom_value == BloomLevel.CREATE.value:
        weight += 2.0
    elif bloom_value == BloomLevel.EVALUATE.value:
        weight += 1.5

    # 단원 융합 신호 — 여러 영역을 엮는 고차 사고를 앞세움.
    if problem.is_cross_unit:
        weight += 1.0

    # 단원 융합도 보조 축(None이면 0.0) — 융합의 깊이(thinking과 동형).
    if problem.diff_integration is not None:
        weight += problem.diff_integration

    # 종합 난이도 보조 축(None이면 0.0) — 심화·변별 타이브레이커.
    if problem.difficulty_overall is not None:
        weight += problem.difficulty_overall

    return weight


def select_gifted_items(
    problems: Iterable[Problem],
    persona: Persona = Persona.E_홈스쿨링영재,
    *,
    min_fit: float = 0.7,
    min_difficulty: float = GIFTED_MIN_DIFFICULTY,
    limit: int | None = None,
) -> list[Problem]:
    """영재 모드 노출 문항을 *선별·정렬*한다 — 적격 필터 → 우선순위 내림차순 → limit.

    파이프라인:
      1. `is_gifted_eligible(p, persona, min_fit=min_fit, min_difficulty=min_difficulty)`로 적격
         문항만 남긴다(비대상·본문 미보유·적합도/난이도 미달·창안/융합 부재는 탈락).
      2. `gifted_priority(p)` *내림차순*으로 **안정정렬**한다(동률은 입력 순서 보존). 따라서 창안
         (CREATE)·융합 문항이 앞으로 온다.
      3. `limit`이 주어지면 상위 `limit`개만 돌려준다(None이면 무제한·전부).

    Args:
      problems: 후보 문항들(임의 iterable — 한 번만 순회).
      persona: 노출 대상 페르소나(기본 E_홈스쿨링영재). E가 아니면 전부 탈락(빈 리스트).
      min_fit: persona_fit 임계값(기본 0.7). `is_gifted_eligible`에 전달.
      min_difficulty: 종합 난이도 하한(기본 4.0). `is_gifted_eligible`에 전달.
      limit: 최대 개수(None=무제한). 0이면 빈 리스트.

    Returns:
      우선순위 내림차순으로 정렬된 적격 문항 리스트(limit 적용).

    결정적(deterministic)·부수효과 없음. `sorted(reverse=True)`는 파이썬 안정정렬이라
    동률 간 입력 순서가 보존된다.
    """
    eligible = [
        p
        for p in problems
        if is_gifted_eligible(p, persona, min_fit=min_fit, min_difficulty=min_difficulty)
    ]
    # 안정정렬 — 동률(같은 priority)은 입력 순서 유지. reverse=True로 큰 가중치 우선.
    ranked = sorted(eligible, key=gifted_priority, reverse=True)
    if limit is None:
        return ranked
    return ranked[:limit]


__all__ = [
    "GIFTED_MIN_DIFFICULTY",
    "GIFTED_PERSONAS",
    "gifted_priority",
    "is_gifted_eligible",
    "select_gifted_items",
]
