"""`GET /v1/me/privacy-audit`의 감사 종류 표기 ↔ `AuditEventKind` 동기 동결.

왜 이 테스트가 있는가
--------------------
`ADMIN-01` 회수(PR #786)가 `AuditEventKind`에 4번째 값 `role_change`를 더하면서, 그 값을 *산문으로
복창하던* 자리들이 3종인 채 남았다 — 같은 엔드포인트 안에서 `event_kind` 파라미터 description은
4종인데 `summary`·operation description은 3종이라 **하나의 OpenAPI 문서가 자기모순**이었다.
그 PR 스스로 §정직한 공백에 *"`EventKindFilter` description 같은 OpenAPI 문자열은 기계가 안 본다.
이번엔 사람이 발견해 고쳤지만 다음에도 그러리란 보장이 없다"*고 적었고, 실제로 같은 PR 안에서
재발했다. 그러니 대응은 "다음에도 사람이 본다"가 아니라 **기계를 붙이는 것**이다.

동결하는 계약 2개 (`test_role_enum.py` 동결 스타일)
--------------------------------------------------
① **값을 열거하는 자리는 정확히 한 곳**(`event_kind` 파라미터 description)이고, 거기엔
   `AuditEventKind` **전 멤버가 빠짐없이** 나타난다. 멤버를 늘리고 description을 안 고치면 red.
② **그 밖의 산문(`summary`·operation description)은 값을 열거하지 않는다.** 열거 지점이 둘 이상이면
   드리프트는 필연이다 — 4종으로 고쳐 놔도 5번째 값에서 똑같이 어긋난다. 이 테스트는 열거 표면
   자체가 되살아나는 것을 막는다(단일 진실원천은 `schema/enums.py`의 `AuditEventKind`).

한국어 산문("반출·동의변경·관리자접근")은 이 테스트의 범위가 아니다 — 값 문자열이 아니라서 기계가
enum과 대조할 방법이 없다. 그 축은 코드 리뷰 소관으로 남긴다(정직한 경계).
"""

from __future__ import annotations

from typing import Any

from whymath_backend.app import create_app
from whymath_backend.schema.enums import AuditEventKind

_PATH = "/v1/me/privacy-audit"
_PARAM = "event_kind"


def _privacy_audit_get_operation() -> dict[str, Any]:
    """`GET /v1/me/privacy-audit`의 OpenAPI operation 객체."""
    openapi = create_app().openapi()
    paths: dict[str, Any] = openapi.get("paths", {})
    operations = paths.get(_PATH)
    assert operations is not None, (
        f"OpenAPI에서 {_PATH}를 찾지 못했습니다 — 경로가 바뀌었거나 라우터 수집이 깨졌습니다. "
        "이 상태로 두면 아래 검사가 '0건 통과'로 위장됩니다."
    )
    operation: dict[str, Any] | None = operations.get("get")
    assert operation is not None, f"{_PATH}에 GET operation이 없습니다."
    return operation


def _event_kind_description() -> str:
    """`event_kind` 쿼리 파라미터의 description — 값 열거가 허용된 **유일한** 자리."""
    operation = _privacy_audit_get_operation()
    for param in operation.get("parameters", []):
        if param.get("name") == _PARAM:
            description = param.get("description")
            assert description, (
                f"{_PATH}의 `{_PARAM}` 파라미터에 description이 없습니다 — "
                "빈 문자열이면 아래 멤버 포함 검사가 무의미해집니다."
            )
            return str(description)
    raise AssertionError(
        f"{_PATH}의 GET 파라미터에서 `{_PARAM}`을 찾지 못했습니다 — "
        "파라미터명이 바뀌었거나 필터가 제거됐습니다."
    )


class TestCollectorNotBroken:
    """수집기 파손 하한 — 이게 깨지면 아래 검사들이 조용히 전건 통과한다."""

    def test_audit_event_kind_has_members(self) -> None:
        assert (
            len(list(AuditEventKind)) >= 3
        ), "`AuditEventKind` 멤버가 3개 미만입니다 — enum import가 깨졌거나 값이 소실됐습니다."

    def test_operation_is_discoverable(self) -> None:
        operation = _privacy_audit_get_operation()
        assert operation.get("parameters"), f"{_PATH} GET에 쿼리 파라미터가 하나도 없습니다."


class TestEveryKindIsDocumented:
    """계약 ① — 값 열거 자리에 전 멤버가 나타난다."""

    def test_description_lists_every_audit_event_kind(self) -> None:
        description = _event_kind_description()
        missing = [kind.value for kind in AuditEventKind if kind.value not in description]
        assert not missing, (
            f"`{_PARAM}` 파라미터 description에 빠진 `AuditEventKind` 값: {missing}. "
            f"현재 description={description!r}. "
            "`AuditEventKind`에 멤버를 더하면 `api/me.py`의 `EventKindFilter` description도 "
            "함께 늘려야 합니다(단일 진실원천 = schema/enums.py)."
        )


class TestNoSecondEnumerationSurface:
    """계약 ② — summary·operation description은 값을 다시 열거하지 않는다."""

    def test_summary_does_not_enumerate_kind_values(self) -> None:
        summary = str(_privacy_audit_get_operation().get("summary", ""))
        leaked = [kind.value for kind in AuditEventKind if kind.value in summary]
        assert not leaked, (
            f"{_PATH}의 summary가 감사 종류 값을 열거합니다: {leaked}. "
            "열거 지점이 둘 이상이면 멤버가 늘 때마다 어긋납니다 — 값 열거는 "
            f"`{_PARAM}` 파라미터 description 한 곳으로 유지하세요."
        )

    def test_operation_description_does_not_enumerate_kind_values(self) -> None:
        description = str(_privacy_audit_get_operation().get("description", ""))
        leaked = [kind.value for kind in AuditEventKind if kind.value in description]
        assert not leaked, (
            f"{_PATH}의 operation description(=핸들러 docstring)이 감사 종류 값을 열거합니다: "
            f"{leaked}. 값 열거는 `{_PARAM}` 파라미터 description 한 곳으로 유지하세요 "
            "— ADMIN-01 회수에서 실제로 발생한 드리프트입니다."
        )
