"""오개념 카탈로그(MisconceptionCatalog) 백엔드 Pydantic 스키마 — M-id 콘텐츠 카탈로그 계약.

설계 정본: L1 데이터 파이프라인의 오개념 추출기(`data_pipeline/misconception/extract.py`의
`MisconceptionRecord` TypedDict 16필드)를 *백엔드 API/계약 모델*로 옮긴 것. #290에서 커밋한
코퍼스 `data/corpus/misconceptions_v1/misconceptions.json`(839 레코드·Collection JSON)을 적재할
영속 카탈로그의 계약이며, 이 슬라이스(Phase B.2)는 ORM·계약·마이그레이션만 세운다 — 코퍼스
로더는 후속 슬라이스 몫이다.

⚠️ 별개 체계 주의: 이 카탈로그는 **M-id(예 'M0425') 콘텐츠 카탈로그**다. 기존 L4 탐지 엔진
(`l4/misconception/catalog.py`의 30종 kebab-id)·런타임 테이블(`misconception_hypothesis`·
`evidence_links`·`misconception_embedding`의 kebab `misconception_id` 느슨참조)과는 *별개 체계*이며
**FK로 잇지 않는다**(두 체계 공존).

타입 매핑 판단(`MisconceptionRecord` TypedDict → 백엔드 Pydantic, `schema/standard.py`
AchievementStandard 선례 그대로):
  - `mis_id`(식별 필드·PK) → required `str`. 의미 문자열(예 'M0425' — UUID 아님).
  - `error_type`(8종) → `str | None`. 닫힌 enum 강제는 *파이프라인 책임*이라 `str`로 둔다
    (AchievementStandard subject/domain이 str인 것·slice8a country_code가 enum 날조를 회피한
    방침과 동일).
  - `difficulty`('상'/'중'/'하') → `str | None`. 동일하게 닫힌 어휘 강제는 파이프라인 책임.
  - `concept_src_id`·`standard_code`(느슨참조) → `str | None`. 개념·성취기준 해소는 *로더*
    책임이라 원천 코드를 그대로 보존(`concept_standard_link.concept_code` 느슨참조 선례 —
    FK 아님).
  - `mapping_score`(float·예 0.454~1.236) → `float | None`. 나머지 자유텍스트·코드 필드는
    `str | None`.

법적 메모: 본문(`canonical_statement`·`student_wrong_thinking`·`correction_point` 등)은
*와이매스 자체 저작*이라 보유가 허용된다(검정교과서·EBS 본문 금지와 대비 — AchievementStandard
`statement` 공공누리 1유형 보유 허용 선례와 동형의 보유 근거).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────────────────
# 핵심: MisconceptionCatalog (오개념 카탈로그 — mis_id PK·M-id 콘텐츠 카탈로그)
# ──────────────────────────────────────────────────────────────────────────
class MisconceptionCatalog(BaseModel):
    """오개념 카탈로그 1건 — 백엔드 API/계약 모델(`data_pipeline` MisconceptionRecord 대응).

    `mis_id`는 카탈로그 유일 식별자(PK·의미 문자열). 나머지 15필드는 소스 채우율이 52~100%라
    빈 값이면 None이다. 형식 검증(error_type 8종·difficulty 3종·코드 형식)은 *데이터 파이프라인
    책임*이며, 백엔드 계약은 파이프라인이 추출·정규화한 값을 받는 전제다(AchievementStandard가
    cross-dataset 검증을 파이프라인에 맡긴 방침과 동형).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 계약의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값 그대로(이 모델엔 enum 없음 — 일관성 위해 둠)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 식별 — mis_id(PK·의미 문자열·UUID 아님) =====
    mis_id: str = Field(
        ...,
        description="오개념 카탈로그 식별자(PK) — 의미 문자열(예 'M0425', gen_random_uuid 없음)",
    )

    # ===== 본문(와이매스 자체 저작 — 보유 허용) =====
    canonical_statement: str | None = Field(default=None, description="오개념 정규 서술 (선택)")
    student_wrong_thinking: str | None = Field(
        default=None, description="학생의 잘못된 사고 (선택)"
    )
    distractor_rule: str | None = Field(default=None, description="오답 보기 생성 규칙 (선택)")

    # ===== 분류 (닫힌 enum 강제는 파이프라인 책임 — str) =====
    error_type: str | None = Field(default=None, description="오류 유형(8종 — 강제는 파이프라인)")
    difficulty: str | None = Field(default=None, description="난이도('상'/'중'/'하', 선택)")
    correction_point: str | None = Field(default=None, description="교정 포인트 (선택)")

    # ===== 코드·매핑 (느슨참조 — 해소는 로더 책임) =====
    ccss_code: str | None = Field(default=None, description="매칭 CCSS 코드 (선택)")
    concept_src_id: str | None = Field(
        default=None,
        description="개념 식별자(느슨참조 — FK 아님, 해소는 로더 후속)",
    )
    standard_code: str | None = Field(
        default=None,
        description="성취기준 코드(느슨참조 — FK 아님, 해소는 로더 후속)",
    )
    school_level: str | None = Field(default=None, description="학교급 (선택)")
    domain: str | None = Field(default=None, description="2022 개정 영역 (선택)")
    subunit: str | None = Field(default=None, description="세부단원·개념 (선택)")
    mapping_confidence: str | None = Field(default=None, description="매핑 신뢰도 (선택)")
    mapping_score: float | None = Field(
        default=None,
        description="매핑 점수(float·예 0.454~1.236, 선택)",
    )
    provenance_note: str | None = Field(default=None, description="생성·검수 출처 메모 (선택)")


__all__ = ["MisconceptionCatalog"]
