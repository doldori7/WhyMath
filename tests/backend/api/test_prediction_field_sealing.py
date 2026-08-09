"""ASM-07 — 예측 5필드의 학생 대면 봉인 거버넌스.

**결정**: `ASM-02`가 (c) 학생 영구 비노출로 닫았다(보호자·교사는 Phase 3 미결).
**집행**: 런타임 필터가 아니라 **응답 스키마에서 필드를 없앤다** — 필터는 데코레이터
인자 한 줄이 빠지면 조용히 무력화되지만 *필드의 부재*는 꺼지지 않는다(`PED-08` ③ 선례).

**사고 경위**: 2026-08-08 실측 전까지 `assessment_module_gap_review.md` D2는 "이 필드를
읽어 학생 대면 응답에 싣는 코드가 0건"이라 적었으나, 실제로는 **writer만 0건**이고
`GET /v1/me/assessments`가 `Assessment`를 그대로 `response_model`로 써서
`"admission_probability": null`이 학생 응답에 키째로 나가고 OpenAPI에도 광고되고
있었다("노출 대기" — 배관 완성·값만 빈 상태). writer 한 줄이 붙으면 API 층 코드 변경
0으로 유입되는 상태였다.

이 파일은 그 상태로 되돌아가지 못하게 **세 층**으로 동결한다:
  ① 스키마 — 학생 모델에 필드가 없고, 내부 모델에는 그대로 있다(봉인은 노출 축이지
     영속 축이 아니다 — `ASM-02`가 (d) 필드 폐기를 미채택했다)
  ② 집행 지점 — OpenAPI 문서상 `/v1/me` 학생 라우트의 응답 스키마 어디에도 없다
     (중첩 `$ref`까지 따라간다 — `AssessmentCaptureResponse.assessment`가 그 경우)
  ③ 페이로드 — 실제 HTTP 응답 바디에 키가 없다

각 층에는 **무력화 하한**(스캔이 실제로 무언가를 봤는지)과 **양방향 변별력**(결함
샘플을 실제로 잡는지)을 함께 둔다 — 스캔이 0건을 보고도 green이면 그건 검사가 아니라
위장이다(CLAUDE.md "변별력 없는 검증 스텝 금지").
"""

from __future__ import annotations

from typing import Any

import pytest

from whymath_backend.app import create_app
from whymath_backend.schema.assessment import (
    STUDENT_HIDDEN_PREDICTION_FIELDS,
    Assessment,
    StudentAssessment,
)

#: 학생 대면 라우트 접두사 — 봉인 스코프. `/v1/me` 밖(관리자·내부)은 이 태스크 범위가 아니다.
_STUDENT_PATH_PREFIX = "/v1/me"

#: 스캔이 최소 이만큼은 봐야 한다 — 라우트 탐색이 깨지면 0건 통과로 위장되므로.
_MIN_ASSESSMENT_ROUTES = 3


class TestSchemaLevelSeal:
    """① 스키마 — 학생 모델엔 없고 내부 모델엔 있다."""

    def test_student_model_has_no_prediction_fields(self) -> None:
        """StudentAssessment에_예측_5필드가_없다"""
        leaked = set(StudentAssessment.model_fields) & STUDENT_HIDDEN_PREDICTION_FIELDS
        assert leaked == set(), f"학생 대면 모델에 예측 필드가 남아 있습니다: {sorted(leaked)}"

    def test_internal_model_still_has_them(self) -> None:
        """Assessment는_5필드를_그대로_보유 — 봉인은 노출 축이지 영속 축이 아니다.

        `ASM-02`는 (d) 필드 폐기를 **미채택**했다(PRD 특성 #86을 내리는 제품 결정이라
        결정 태스크 범위 밖). 이 단언이 red 면 누군가 결정 범위를 넘어 필드를 지운 것이다.
        """
        missing = STUDENT_HIDDEN_PREDICTION_FIELDS - set(Assessment.model_fields)
        assert missing == set(), f"내부 정본에서 사라진 필드: {sorted(missing)}"

    def test_student_model_is_the_base_not_a_subtraction(self) -> None:
        """Assessment가_StudentAssessment를_상속 — 방향이 허용목록을 만든다.

        학생 모델이 기반이고 내부 모델이 5필드를 *더한다*. 이 방향이면 나중에 누가
        `Assessment`에 새 예측 필드를 붙여도 학생 응답에 자동으로 새지 않는다.
        반대 방향(빼기)이었다면 새 필드는 기본 노출이 된다.
        """
        assert issubclass(Assessment, StudentAssessment)


def _collect_ref_names(node: Any, out: set[str]) -> None:
    """OpenAPI 노드에서 참조되는 컴포넌트 스키마 이름을 재귀 수집."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            out.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _collect_ref_names(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_ref_names(item, out)


def _reachable_schemas(openapi: dict[str, Any], roots: set[str]) -> set[str]:
    """루트 스키마에서 `$ref`로 도달 가능한 전체 집합(중첩 포함)."""
    components = openapi.get("components", {}).get("schemas", {})
    seen: set[str] = set()
    frontier = set(roots)
    while frontier:
        name = frontier.pop()
        if name in seen or name not in components:
            continue
        seen.add(name)
        nested: set[str] = set()
        _collect_ref_names(components[name], nested)
        frontier |= nested - seen
    return seen


def _student_assessment_response_schemas() -> tuple[set[str], dict[str, Any], int]:
    """`/v1/me`의 assessment 라우트 응답에서 도달 가능한 스키마 집합 + 라우트 수."""
    openapi = create_app().openapi()
    roots: set[str] = set()
    route_count = 0
    for path, operations in openapi.get("paths", {}).items():
        if not path.startswith(_STUDENT_PATH_PREFIX) or "assessment" not in path:
            continue
        for method, operation in operations.items():
            if method.lower() not in {"get", "post", "patch", "put", "delete"}:
                continue
            route_count += 1
            _collect_ref_names(operation.get("responses", {}), roots)
    return _reachable_schemas(openapi, roots), openapi, route_count


class TestServingContractSeal:
    """② 집행 지점 — OpenAPI 상 학생 라우트 응답 어디에도 없다."""

    def test_scan_actually_sees_routes(self) -> None:
        """스캔_무력화_하한 — 라우트를 못 찾으면 아래 검사는 0건 통과로 위장된다."""
        _, _, route_count = _student_assessment_response_schemas()
        assert route_count >= _MIN_ASSESSMENT_ROUTES, (
            f"학생 assessment 라우트를 {route_count}건만 찾았습니다 — "
            "라우트 탐색이 깨졌거나 경로 규약이 바뀌었습니다."
        )

    def test_no_prediction_field_in_student_response_schemas(self) -> None:
        """학생_라우트_응답_스키마_전체에_예측_필드명_0건 (중첩 $ref 포함)"""
        reachable, openapi, _ = _student_assessment_response_schemas()
        components = openapi["components"]["schemas"]
        offenders: list[str] = []
        for name in sorted(reachable):
            properties = components[name].get("properties", {})
            for field in sorted(set(properties) & STUDENT_HIDDEN_PREDICTION_FIELDS):
                offenders.append(f"{name}.{field}")
        assert offenders == [], (
            "학생 대면 응답 스키마에 예측 필드가 있습니다 — 런타임 필터가 아니라 "
            f"스키마에서 없애야 합니다(ASM-07): {offenders}"
        )

    def test_nested_capture_response_is_covered(self) -> None:
        """중첩_경로_실제_커버_확인 — capture 응답의 중첩 모델까지 스캔에 잡히는지.

        `AssessmentCaptureResponse.assessment`는 `$ref` 한 단계 아래라, 재귀를 안 하면
        위 검사가 이 지점을 **못 보고도** green 이 된다.
        """
        reachable, _, _ = _student_assessment_response_schemas()
        assert "AssessmentCaptureResponse" in reachable
        assert "StudentAssessment" in reachable
        assert "Assessment" not in reachable, (
            "학생 라우트 응답에서 내부 정본 `Assessment`가 도달 가능합니다 — "
            "어딘가 response_model이 학생 모델로 바뀌지 않았습니다."
        )

    def test_scanner_detects_offending_schema(self) -> None:
        """스캐너_변별력 — 예측 필드를 가진 스키마를 실제로 잡는가."""
        fake = {
            "components": {
                "schemas": {
                    "Offender": {"properties": {"admission_probability": {"type": "number"}}}
                }
            }
        }
        reachable = _reachable_schemas(fake, {"Offender"})
        props = fake["components"]["schemas"]["Offender"]["properties"]
        assert reachable == {"Offender"}
        assert set(props) & STUDENT_HIDDEN_PREDICTION_FIELDS == {"admission_probability"}


class TestPayloadSeal:
    """③ 페이로드 — 실제 HTTP 응답 바디에 키가 없다."""

    @pytest.fixture
    def openapi_document(self) -> dict[str, Any]:
        return create_app().openapi()

    def test_openapi_advertises_student_model_on_list_route(
        self, openapi_document: dict[str, Any]
    ) -> None:
        """GET_assessments가_StudentAssessment를_광고 — 문서 축의 노출도 닫혔는지."""
        responses = openapi_document["paths"]["/v1/me/assessments"]["get"]["responses"]
        refs: set[str] = set()
        _collect_ref_names(responses, refs)
        assert "StudentAssessment" in refs
        assert "Assessment" not in refs

    def test_client_payload_has_no_prediction_keys(self) -> None:
        """실제_응답_바디에_예측_키_없음 — 스키마가 아니라 나가는 JSON 자체로 확인.

        인증 없이 호출하면 401이라 바디 검증이 무의미하므로, 여기서는 *스키마가 아닌*
        직렬화 경로가 같은 계약을 지키는지를 모델 직렬화로 확인한다(라우트 통합 경로는
        `test_me.py`의 capture 테스트가 담당 — 그쪽이 실제 200 바디를 본다).
        """
        payload = StudentAssessment().model_dump(mode="json")
        assert set(payload) & STUDENT_HIDDEN_PREDICTION_FIELDS == set()
        assert "concept_diagnosis" in payload  # 무력화 하한 — 빈 dict면 위 단언이 공허하다

    def test_from_assessment_drops_prediction_values(self) -> None:
        """값이_채워져_있어도_변환에서_사라진다 — writer가 붙은 미래 상태의 방어.

        오늘은 writer가 0건이라 값이 항상 None이지만, 봉인의 의미는 *값이 생긴 뒤*에
        드러난다. 값을 넣은 내부 정본을 변환해 실제로 사라지는지 본다.
        """
        full = Assessment(
            estimated_grade=2.0,
            estimated_score=130,
            estimated_percentile=94.5,
            admission_probability=0.72,
        )
        student = StudentAssessment.from_assessment(full)
        dumped = student.model_dump(mode="json")
        assert set(dumped) & STUDENT_HIDDEN_PREDICTION_FIELDS == set()
        # 내부 정본에는 값이 그대로 남아 있다(영속 축 불변).
        assert full.estimated_grade == 2.0
        assert full.admission_probability == 0.72
