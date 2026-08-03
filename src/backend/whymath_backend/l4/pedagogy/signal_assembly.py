"""학생 신호 조립 — `StudentSignals` 공용 생산자 (PED-08 — `api/study.py`에서 추출).

`api/study.py`의 `_build_signals`(PED-06 grade_band 배선)를 공용 좌석으로 추출한다. study·coach
양쪽이 같은 조립을 재사용하게 하는 것이 목적이다(coach.py 101KB 직수정 전 선행 슬라이스 — 04e §9
"study 신호 조립기 공용 추출 + decide() 소비" 중 전자). 동작은 원본과 바이트 동일 — study의 호출부는
이 함수를 import해 쓰는 것으로만 바뀐다(회귀 0).

────────────────────────────────────────────────────────────────────────────
정책 (원본 study.py docstring 그대로 승계)
────────────────────────────────────────────────────────────────────────────
L2 진단 + L5 프로필 → `StudentSignals` 조립 — **실재하는 신호만** 채운다. 진단이 없거나(신규 학생)
해당 개념이 진단 목록에 없으면 숙달 축은 비운 채로 둔다 — 없는 값을 기본치로 채우면 선택기가 근거
없는 판단을 하게 된다(PED-02가 세운 "가짜 통과 금지" 규약). Polya 단계·턴 수·힌트는 대화 세션
축이라 여기서는 기본값이다(공급 진입 = 시도 전).

`grade_band`(PED-06 — 04e §4 카탈로그 후보 필터 축)는 `UserProfile.grade`(10~14 — `schema/user.py`
계약)에서 `grade_to_band` 순수 변환으로 파생한다("생산자 먼저" — 04d §2.1). 프로필 미존재·grade
미기입이면 None으로 두어 필터의 학년 축이 조용히 스킵된다(필수화 금지).

7계층: L4가 L2(`compute_concept_diagnoses`)를 조회하고 db.models(`UserProfile`)를 읽는다
(L_n→L_{n-1} 허용).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.db.models.user import UserProfile
from whymath_backend.l2.concept_diagnosis import compute_concept_diagnoses
from whymath_backend.l4.lthc import mastery_to_level
from whymath_backend.l4.pedagogy.runtime_selector import StudentSignals, grade_to_band


async def build_student_signals(
    session: AsyncSession, user_id: uuid.UUID, concept_code: str
) -> StudentSignals:
    """L2 진단 + 프로필 → `StudentSignals`(모듈 docstring 정책 참조)."""
    profile = await session.get(UserProfile, user_id)
    grade_band = grade_to_band(profile.grade if profile is not None else None)

    diagnoses = await compute_concept_diagnoses(session, user_id)
    for diagnosis in diagnoses:
        if diagnosis.concept_code == concept_code:
            mastery = (
                diagnosis.bkt_mastery
                if diagnosis.bkt_mastery is not None
                else diagnosis.irt_mastery_proxy
            )
            return StudentSignals(
                mastery_level=mastery_to_level(mastery) if mastery is not None else None,
                bkt_mastery=diagnosis.bkt_mastery,
                irt_theta=diagnosis.irt_theta,
                grade_band=grade_band,
            )
    return StudentSignals(grade_band=grade_band)


__all__ = ["build_student_signals"]
