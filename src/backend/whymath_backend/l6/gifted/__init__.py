"""L6 영재(gifted) 트랙 게이팅 — 심화·창안 문항 선별 노출(페르소나 E 전용).

오버레이 모델(RT·수능·학교진도·사고력 게이팅과 동형): 새 concept 노드·Alembic 마이그레이션·
새 enum을 *만들지 않는다*. 기존 L1 `Problem` 필드만 재사용한다 —
  - `Problem.source_type` (저작권 노출 게이트 — 평가원/EBS/교과서 본문 미보유 차단),
  - `Problem.persona_fit` (페르소나 E 적합도 — 영재 신호·높은 임계 기본 0.7),
  - `Problem.difficulty_overall` (심화 하한 기본 4.0 — KMO 입문 수준),
  - `Problem.bloom_level` (창안 CREATE — 영재 주신호),
  - `Problem.is_cross_unit`·`Problem.diff_integration` (단원 융합 — 영재 고차 사고).

대상(닫힌 집합): 영재 트랙은 페르소나 **E(홈스쿨링 영재)** 전용이다 — RT 트랙이 재수(B·C)를
닫힌 집합으로 제한한 것과 같은 이유(학습 환경·목표가 근본). 사고력 thinking이 페르소나를 열어
둔 것과 대비된다(상세: `gating.py` 모듈 docstring).

데이터 현실: 영재 콘텐츠(KMO·올림피아드)는 아직 코퍼스에 없다 — 학교진도 성취기준 선례처럼
*게이팅만 선깔고 데이터가 차면 자동 활성*한다(콘텐츠 없으면 빈 결과·데이터0 안전).

레이어 규칙(CLAUDE.md): L6→L1 의존만 한다(`schema.problem`·`schema.enums`)·`l6._shared`.
L4/L2/L3를 import하지 않는다. L6은 아무도 import하지 않는 최상위 소비자다.

저작권(CLAUDE.md 우선순위 #2): 평가원·EBS·검정교과서의 *본문*은 L6 공용 게이트
(`_shared.is_exposable`)로 원천 차단하고, 학생에게는 자체생성 동등문제만 노출한다.
"""

from __future__ import annotations

from whymath_backend.l6.gifted.gating import (
    GIFTED_MIN_DIFFICULTY,
    GIFTED_PERSONAS,
    gifted_priority,
    is_gifted_eligible,
    select_gifted_items,
)

__all__ = [
    "GIFTED_MIN_DIFFICULTY",
    "GIFTED_PERSONAS",
    "gifted_priority",
    "is_gifted_eligible",
    "select_gifted_items",
]
