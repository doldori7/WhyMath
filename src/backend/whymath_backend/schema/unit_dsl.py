"""소단원 DSL(`.unit.yaml`) 입력 계약 — 사람이 저작하는 소단원 명세의 Pydantic 게이트.

`schema/pedagogy_pack.py::PedagogyPack`(교수법 팩 = 데이터)의 *소단원 DSL* 짝이다. 이 모듈은
컴파일러(`l1/pedagogy/unit_compiler.py`)가 소비하는 *입력 포맷*을 정의한다 — 사람이 저작한
`.unit.yaml` 한 파일이 소단원 1개(제목·성취기준·개념 노드)와 그 학습목표들을 담는다. 컴파일러는
이 계약을 통과한 DSL을 `unit_spec`+`learning_objective` DB 행과 콘텐츠 *발주서*(work order)로
변환한다(YAML=소스, DB=산출물·단방향).

────────────────────────────────────────────────────────────────────────────
이름 규약 (ORM 충돌 회피)
────────────────────────────────────────────────────────────────────────────
ORM `db/models/pedagogy_dsl.py`에는 `UnitSpec`·`LearningObjective`가 이미 있다. 이 *입력* 계약은
그 산출물 좌석과 이름이 겹치면 안 되므로 `UnitDSL`·`ObjectiveDSL`로 명명한다(입력 DSL ≠ 산출물
ORM). 필드명은 가능한 한 ORM 컬럼명과 맞추되(rename seam 최소화), DSL 고유 항목(`suffix`·
`slot_overrides`·`evidence_overrides`)은 컴파일러가 해석·전개한다.

────────────────────────────────────────────────────────────────────────────
enum 값 직렬화 (use_enum_values=True — pedagogy_pack 선례)
────────────────────────────────────────────────────────────────────────────
`ObjectiveDSL`은 `use_enum_values=True`라 검증 후 `k_type`은 문자열 값("CONCEPT")이 된다 —
컴파일러가 교수법 팩 dict(문자열 키)·PG native enum 컬럼과 그대로 정합한다(pedagogy_pack 모델과
동형). 따라서 `@model_validator`의 `k_type` 비교도 문자열끼리 이뤄진다.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import KnowledgeType


# ──────────────────────────────────────────────────────────────────────────
# ObjectiveDSL — 소단원 한 학습목표의 입력 계약
# ──────────────────────────────────────────────────────────────────────────
class ObjectiveDSL(BaseModel):
    """소단원 DSL의 한 학습목표 — 컴파일러가 `learning_objective` 행 1개로 전개한다.

    `suffix`는 소단원 안에서만 유일하면 되는 짧은 식별자(예 "OBJ-01")로, 컴파일러가
    `{unit_id}:{suffix}` 형태의 전역 `id`로 확장한다. `standard_code`는 성취기준 *코드*(본문 아님)를
    가리키고, 컴파일러가 코드→원문(`achievement_std`)을 해석한다. `k_type`(주 유형)은 교수법 팩
    바인딩 축이며, `k_type_secondary`(부 유형·기록만)는 주 유형과 달라야 한다(ORM CHECK 정합).

    오버라이드 3종은 팩 기본값을 목표 단위로 덮어쓰는 seam이다:
      - `slot_overrides` : 슬롯 유형→개수. 팩 기본 슬롯의 개수를 교체하거나 새 유형을 추가한다.
      - `evidence_overrides` : 팩 `default_evidence`에 얹는 부분 덮어쓰기.
      - `phase_overrides` : Polya 단계별 오버라이드(팩 기본을 목표 단위로 덮어씀).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — DSL 오타 키 차단(계약의 단일 진실).
        extra="forbid",
        # 검증 후 enum을 값으로(k_type이 "CONCEPT" 문자열 → 팩 dict 키·PG native enum 정합).
        use_enum_values=True,
        # 문자열 양끝 공백 제거(YAML 블록 스칼라 후행 개행 제거).
        str_strip_whitespace=True,
    )

    suffix: str = Field(
        ..., description="소단원 내 유일 식별자(예 'OBJ-01'·컴파일러가 전역 id로 확장)"
    )
    statement: str = Field(..., description="학습목표 서술(자체 분해 전제)")
    standard_code: str = Field(
        ..., description="성취기준 *코드*(본문 아님·컴파일러가 원문 achievement_std로 해석)"
    )
    source_verb: str | None = Field(
        default=None, description="성취기준 서술어(예 '구한다'·유형 추론 근거·nullable)"
    )
    k_type: KnowledgeType = Field(..., description="주 지식 유형(교수법 팩 바인딩 축)")
    k_type_secondary: KnowledgeType | None = Field(
        default=None, description="부 지식 유형(기록만·주 유형과 달라야 함·nullable)"
    )
    concept_nodes: list[str] = Field(
        ..., min_length=1, description="원자 백본 노드 code 배열(최소 1·컴파일러가 존재 검증)"
    )
    misconception_ids: list[str] | None = Field(
        default=None, description="연결 오개념 id(nullable — 미지정 시 자동 채움 없음·v0.1)"
    )
    slot_overrides: dict[str, int] | None = Field(
        default=None, description="슬롯 유형→개수(팩 기본 개수 교체 또는 새 유형 추가)"
    )
    evidence_overrides: dict[str, Any] | None = Field(
        default=None, description="팩 default_evidence에 얹는 부분 덮어쓰기(nullable)"
    )
    phase_overrides: dict[str, Any] | None = Field(
        default=None, description="Polya 단계별 오버라이드(팩 기본을 목표 단위로 덮어씀·nullable)"
    )

    @model_validator(mode="after")
    def _secondary_distinct(self) -> ObjectiveDSL:
        """부 유형은 주 유형과 달라야 한다 — ORM `secondary_distinct` CHECK와 정합.

        use_enum_values=True라 `self.k_type`/`self.k_type_secondary`는 이미 문자열 값이므로
        문자열끼리 비교한다(같으면 무의미한 중복 — 거부).
        """
        if self.k_type_secondary is not None and self.k_type_secondary == self.k_type:
            raise ValueError(
                f"suffix={self.suffix}: k_type_secondary가 k_type({self.k_type})와 같습니다 — "
                "부 유형은 주 유형과 달라야 합니다(같으면 무의미한 중복)."
            )
        return self


# ──────────────────────────────────────────────────────────────────────────
# UnitDSL — 소단원 1개의 입력 계약(제목·성취기준·개념·학습목표들)
# ──────────────────────────────────────────────────────────────────────────
class UnitDSL(BaseModel):
    """소단원 DSL 최상위 — `.unit.yaml` 한 파일 = 소단원 1개. 컴파일러가 `unit_spec` 행으로 전개.

    `standard_codes`·`concept_nodes`는 소단원 수준의 연결(성취기준 코드·원자 백본 code)로 최소 1개씩
    필요하다. `objectives`는 최소 1개이며 각 목표 `suffix`는 소단원 안에서 유일해야 한다(컴파일러가
    `{unit_id}:{suffix}` 전역 id로 확장하므로 충돌 방지).
    """

    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(..., description="소단원 식별자(복합 PK의 한 축)")
    unit_version: int = Field(default=1, description="소단원 버전(재컴파일 시 새 버전·기본 1)")
    api_version: str = Field(..., description="DSL API 버전(예 'unit/0.1')")
    title: str = Field(..., description="소단원 제목")
    curriculum_rev: str = Field(..., description="교육과정 개정판(예 '2022')")
    standard_codes: list[str] = Field(
        ..., min_length=1, description="연결 성취기준 코드 배열(최소 1·컴파일러가 존재 검증)"
    )
    concept_nodes: list[str] = Field(
        ..., min_length=1, description="원자 백본 노드 code 배열(최소 1·컴파일러가 존재 검증)"
    )
    objectives: list[ObjectiveDSL] = Field(
        ..., min_length=1, description="학습목표들(최소 1·suffix 유일)"
    )

    @model_validator(mode="after")
    def _unique_suffixes(self) -> UnitDSL:
        """목표 `suffix` 유일성 강제 — 중복이면 컴파일러가 같은 전역 id를 두 번 만들어 충돌한다."""
        suffixes = [obj.suffix for obj in self.objectives]
        duplicates = sorted({s for s in suffixes if suffixes.count(s) > 1})
        if duplicates:
            raise ValueError(
                f"unit_id={self.unit_id}: 목표 suffix가 중복됩니다: {duplicates} — "
                "각 목표의 suffix는 소단원 안에서 유일해야 합니다(전역 id 충돌 방지)."
            )
        return self


# ──────────────────────────────────────────────────────────────────────────
# DSL 스키마 동결 (PED-01 — 이차함수 파일럿 E2E 1회 완주로 검증)
# ──────────────────────────────────────────────────────────────────────────
# `UnitDSL`·`ObjectiveDSL`의 필드셋은 PED-01 파일럿 관통으로 "스키마가 5단계를 지탱함"이 증명돼
# 동결됐다. 필드 추가/개명/삭제는 *2번째 소단원의 실요구*가 있을 때만 한다(YAGNI·과공학 방지).
# 변경 시 `tests/backend/schema/test_pedagogy_dsl_schema_freeze.py`의 동결 리터럴을 함께 갱신해야
# CI가 통과한다(기계 lock).

__all__ = [
    "ObjectiveDSL",
    "UnitDSL",
]
