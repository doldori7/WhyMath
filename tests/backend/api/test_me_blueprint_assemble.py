"""`POST /v1/me/assessments/assemble` 결선 테스트(ASM-04·hermetic).

조립 로직 자체는 L6 단위테스트(`tests/backend/l6/blueprint/test_assembly.py`)가 검증한다.
이 파일은 **api 결선**만 본다:
  ① 인증 필요(401).
  ② 충족 → `Assessment` 1행 적재(`AssessmentType.실전모의고사` 첫 발화)·commit 1회.
  ③ 미충족 → **적재 0**(commit 0·add 0). 부족한 세트를 조용히 남기지 않는다.
  ④ 게임화 금기 4필드 + `target_university_id`는 적재 행에서도 항상 None(ASM-02·03 승계).
  ⑤ 세트 좌석 — 새 테이블 없이 `pattern_diagnosis` JSONB(헤더 1 + 문항 N·id만)로 표현.
  ⑥ `completed_at`은 None — 조립은 *시행 전*이다(완료는 complete 좌석이 찍는다).

후보 조회(`_fetch_blueprint_candidates`)는 실 PG 조인이라 monkeypatch로 대체한다 — 실 조인
정확성은 통합 경로(`api/gating.py` 헬퍼)의 기존 테스트가 담당한다.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from whymath_backend.api._auth import get_consented_user
from whymath_backend.app import create_app
from whymath_backend.db.models.assessment import Assessment
from whymath_backend.db.models.user import UserProfile
from whymath_backend.db.session import get_session
from whymath_backend.schema.assessment import STUDENT_HIDDEN_PREDICTION_FIELDS
from whymath_backend.schema.enums import (
    AssessmentType,
    Curriculum,
    Persona,
    ReviewStatus,
    SourceType,
    Subject,
)
from whymath_backend.schema.problem import Problem
from whymath_backend.schema.user import UserProfile as UserProfileSchema

_UID = uuid.uuid4()
_ENDPOINT = "/v1/me/assessments/assemble"


def _user() -> UserProfile:
    return UserProfile.from_schema(
        UserProfileSchema(user_id=_UID, persona_primary=Persona.A_일반고고3)
    )


class _FakeSession:
    """add/commit만 세는 최소 세션 더블(실 쿼리는 monkeypatch가 우회한다)."""

    def __init__(self) -> None:
        self.commits = 0
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


def _client() -> tuple[TestClient, _FakeSession]:
    app = create_app()
    app.dependency_overrides[get_consented_user] = _user
    fake = _FakeSession()

    async def _sess() -> AsyncIterator[_FakeSession]:
        yield fake

    app.dependency_overrides[get_session] = _sess
    return TestClient(app), fake


def _problem(**over: object) -> Problem:
    """두 게이트를 통과하는 최소 자체생성 문항(합성 픽스처)."""
    kwargs: dict[str, object] = {
        "source_type": SourceType.자체생성,
        "review_status": ReviewStatus.approved,
        "curriculum_version": Curriculum.REVISION_2022,
        "valid_from_year": 2022,
        "subject": Subject.공통,
        "unit_codes": ["ALG-EQ-QUAD"],
        "difficulty_overall": 3.0,
    }
    kwargs.update(over)
    return Problem(**kwargs)  # type: ignore[arg-type]


def _patch_candidates(monkeypatch: pytest.MonkeyPatch, problems: list[Problem]) -> None:
    async def _fake_candidates(session: Any) -> list[Problem]:
        return problems

    monkeypatch.setattr("whymath_backend.api.me._fetch_blueprint_candidates", _fake_candidates)


_BLUEPRINT_2 = {
    "title": "1단원 마감 측정",
    "cells": [{"count": 2, "points_per_item": 4}],
    "time_limit_minutes": 45,
}


class TestBlueprintAssembleEndpoint:
    def test_requires_auth(self) -> None:
        """무토큰 401 — 학생 데이터 좌석이라 인증 없이는 접근 불가."""
        app = create_app()

        async def _sess() -> AsyncIterator[_FakeSession]:
            yield _FakeSession()

        app.dependency_overrides[get_session] = _sess
        assert TestClient(app).post(_ENDPOINT, json=_BLUEPRINT_2).status_code == 401

    def test_assembles_and_persists_one_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """충족 → Assessment 1행 적재(실전모의고사 첫 발화)·commit 1회."""
        problems = [_problem(), _problem()]
        _patch_candidates(monkeypatch, problems)
        client, fake = _client()

        resp = client.post(_ENDPOINT, json=_BLUEPRINT_2)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["written"] is True
        assert body["reason"] == "assembled"
        assert body["assembly"]["satisfied"] is True
        assert body["assembly"]["selected_item_count"] == 2
        assert body["candidate_pool_size"] == 2
        assert fake.commits == 1
        assert len(fake.added) == 1
        row = fake.added[0]
        assert isinstance(row, Assessment)
        assert row.assessment_type == AssessmentType.실전모의고사

    def test_completed_at_is_none_because_not_yet_taken(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """조립 시점은 *시행 전*이라 완료가 아니다 — completed_at은 None."""
        _patch_candidates(monkeypatch, [_problem(), _problem()])
        client, fake = _client()
        assert client.post(_ENDPOINT, json=_BLUEPRINT_2).status_code == 200
        assert fake.added[0].started_at is not None
        assert fake.added[0].completed_at is None

    def test_prediction_fields_never_populated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """등급·점수·백분위·합격예측(+대학 id)은 이 경로에서도 항상 None(게임화 금기 승계)."""
        _patch_candidates(monkeypatch, [_problem(), _problem()])
        client, fake = _client()
        resp = client.post(_ENDPOINT, json=_BLUEPRINT_2)
        assert resp.status_code == 200

        row = fake.added[0]
        for field in STUDENT_HIDDEN_PREDICTION_FIELDS:
            assert getattr(row, field) is None
        assert row.target_university_id is None
        # 학생 대면 응답에는 예측 필드 *키 자체가 없다*(ASM-07 봉인 승계).
        assert set(resp.json()["assessment"]) & STUDENT_HIDDEN_PREDICTION_FIELDS == set()

    def test_set_seat_is_pattern_diagnosis_jsonb_ids_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """세트는 새 테이블이 아니라 `pattern_diagnosis` JSONB(헤더 1 + 문항 N)로 앉는다.

        문항 항목은 **id 참조만** 담는다 — 발문·해설 본문을 복제하지 않는다(저작권 레일).
        """
        problems = [_problem(question_text="발문 본문"), _problem(question_text="발문 본문2")]
        _patch_candidates(monkeypatch, problems)
        client, fake = _client()
        assert client.post(_ENDPOINT, json=_BLUEPRINT_2).status_code == 200

        payload = fake.added[0].pattern_diagnosis
        assert payload[0]["kind"] == "blueprint_test_set"
        assert payload[0]["use_case"] == "unit_closure_measurement"
        items = payload[1:]
        assert [i["kind"] for i in items] == ["blueprint_item"] * 2
        assert {i["problem_id"] for i in items} == {str(p.problem_id) for p in problems}
        for item in items:
            assert "question_text" not in item
            assert "발문" not in str(item)
        # 다른 4개 JSONB는 이 경로가 건드리지 않는다(좌석 분리).
        assert fake.added[0].concept_diagnosis == []
        assert fake.added[0].weak_points == []

    def test_points_null_yields_none_total_with_missing_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """코퍼스 배점이 NULL이면 실측 총점 null + 미부여 건수 — 선언 총점은 별개 축으로 산출."""
        _patch_candidates(monkeypatch, [_problem(points=None), _problem(points=None)])
        client, _ = _client()
        assembly = client.post(_ENDPOINT, json=_BLUEPRINT_2).json()["assembly"]

        assert assembly["corpus_total_points"] is None
        assert assembly["points_missing_count"] == 2
        assert assembly["declared_total_points"] == 8
        assert assembly["time_limit_minutes"] == 45

    def test_unsatisfied_blueprint_is_not_persisted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """요구 문항 수 > 적격 후보 수 → 적재 0·명시 실패(조용한 부분 세트 금지)."""
        _patch_candidates(monkeypatch, [_problem()])
        client, fake = _client()

        resp = client.post(_ENDPOINT, json=_BLUEPRINT_2)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["written"] is False
        assert body["reason"] == "blueprint_unsatisfied"
        assert body["assessment"] is None
        assert body["assembly"]["satisfied"] is False
        assert body["assembly"]["cells"][0]["shortfall"] == 1
        assert body["assembly"]["unsatisfied_reasons"]
        # 실패는 적재로 이어지지 않는다.
        assert fake.commits == 0
        assert fake.added == []

    def test_copyright_blocked_candidates_cannot_fill_a_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """평가원·EBS 문항만 있는 풀에서는 세트가 조립되지 않는다(저작권 게이트 결선 확인)."""
        _patch_candidates(
            monkeypatch,
            [_problem(source_type=SourceType.평가원), _problem(source_type=SourceType.EBS)],
        )
        client, fake = _client()
        body = client.post(_ENDPOINT, json=_BLUEPRINT_2).json()

        assert body["written"] is False
        assert body["assembly"]["problem_ids"] == []
        assert body["candidate_pool_size"] == 2  # 후보는 있었지만 게이트가 전부 걸렀다.
        assert fake.added == []

    def test_standard_constrained_cell_uses_injected_codes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """성취기준 축은 주입된 코드로 판정된다 — 주입이 없으면 그 칸은 명시 실패한다.

        `achievement_standard_codes`는 ORM 비매핑(비영속)이라 조인 주입이 없으면 빈 리스트다.
        그 상태에서 조용히 아무 문항이나 채우지 않는다는 것이 이 테스트의 요지다.
        """
        blueprint = {
            "title": "성취기준 지정",
            "cells": [{"count": 1, "standard_code": "[10공수1-02-02]"}],
        }

        # ① 주입 없음(빈 리스트) → 후보 0 → 명시 실패.
        _patch_candidates(monkeypatch, [_problem()])
        client, fake = _client()
        body = client.post(_ENDPOINT, json=blueprint).json()
        assert body["written"] is False
        assert body["assembly"]["cells"][0]["eligible_count"] == 0
        assert fake.added == []

        # ② 주입 있음 → 같은 청사진이 충족된다(변별력 — 주입 유무가 결과를 가른다).
        _patch_candidates(monkeypatch, [_problem(achievement_standard_codes=["[10공수1-02-02]"])])
        client2, fake2 = _client()
        body2 = client2.post(_ENDPOINT, json=blueprint).json()
        assert body2["written"] is True
        assert len(fake2.added) == 1

    def test_invalid_blueprint_is_rejected_422(self) -> None:
        """빈 cells·count 0 같은 잘못된 선언은 422 — 조립기가 완화해 받아주지 않는다."""
        client, _ = _client()
        assert client.post(_ENDPOINT, json={"title": "빈", "cells": []}).status_code == 422
        assert (
            client.post(_ENDPOINT, json={"title": "0문항", "cells": [{"count": 0}]}).status_code
            == 422
        )


# ──────────────────────────────────────────────────────────────────────
# 후보 로더 결선 — 성취기준 코드 주입이 실제로 일어나는가
# ──────────────────────────────────────────────────────────────────────
class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)

    def all(self) -> list[Any]:
        return list(self._rows)


class _QueuedSession:
    """execute 호출 순서대로 미리 준비한 결과를 돌려주는 세션 더블.

    `_fetch_blueprint_candidates`는 쿼리를 정확히 2회 실행한다 — ①후보 조회(ORM Problem 행)
    ②성취기준 원자 축 조인(problem_id, standard_codes 튜플). 순서 자체가 계약이라 큐로 흉내낸다.
    """

    def __init__(self, results: list[_Result]) -> None:
        self._results = list(results)
        self.execute_count = 0

    async def execute(self, stmt: Any) -> _Result:
        self.execute_count += 1
        return self._results.pop(0)


class TestBlueprintCandidateLoader:
    async def test_injects_achievement_codes_deterministically(self) -> None:
        """후보 로더가 원자 축 조인 결과를 `achievement_standard_codes`에 정렬해 주입한다."""
        from whymath_backend.api import me as me_module
        from whymath_backend.db.models.problem import Problem as ProblemORM

        schema = _problem()
        row = ProblemORM.from_schema(schema)
        session = _QueuedSession(
            [
                _Result([row]),
                # 배열 컬럼은 정렬되지 않은 채 올 수 있다 — 주입은 sorted로 결정적이어야 한다.
                _Result([(schema.problem_id, ["[10공수1-03-01]", "[10공수1-02-02]"])]),
            ]
        )

        candidates = await me_module._fetch_blueprint_candidates(session)  # type: ignore[arg-type]

        assert session.execute_count == 2
        assert len(candidates) == 1
        assert candidates[0].achievement_standard_codes == [
            "[10공수1-02-02]",
            "[10공수1-03-01]",
        ]

    async def test_missing_codes_leave_empty_list_not_fabricated(self) -> None:
        """조인 결과가 없으면 빈 리스트 그대로 — 없는 성취기준을 지어내지 않는다."""
        from whymath_backend.api import me as me_module
        from whymath_backend.db.models.problem import Problem as ProblemORM

        row = ProblemORM.from_schema(_problem())
        session = _QueuedSession([_Result([row]), _Result([])])

        candidates = await me_module._fetch_blueprint_candidates(session)  # type: ignore[arg-type]

        assert candidates[0].achievement_standard_codes == []
