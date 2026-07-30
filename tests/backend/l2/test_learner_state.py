"""L2 `LearnerState` v0 조립기(`get_state`) 단위테스트 (hermetic·FakeSession).

PED-05: `docs/architecture/02_learner_model.md` §"출력 — LearnerState" v0 실체화. 기존
`test_concept_diagnosis.py`의 `_QueueSession`(execute() 호출 순서대로 결과를 반환) 관례를
확장해 `get_state()`의 4회 `execute()`(BKT→IRT abilities→theta→misconceptions) + 1회
`get()`(user_profile)를 hermetic으로 검증한다.

계층 가드(`test_no_import_cycle.py::test_l1_embedding_modules_have_no_l4_import`와 동일 AST
패턴)로 `l2/learner_state.py`가 `whymath_backend.l4.*`를 전혀 import하지 않음을 봉인한다
(CLAUDE.md "L_n은 L_{n+1}을 알지 못한다" — 역방향 의존 금지의 회귀 가드).
"""

from __future__ import annotations

import ast
import importlib
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from whymath_backend.l2.learner_state import get_state

_UID = uuid.uuid4()


# ──────────────────────────────────────────────────────────────────────────
# hermetic 좌석 — `test_concept_diagnosis.py::_QueueSession` 관례 확장(execute 큐 + get() 추가)
# ──────────────────────────────────────────────────────────────────────────
class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalars(self) -> _Scalars:
        return _Scalars(self._rows)


@dataclass
class _FakeProfile:
    """`UserProfile`의 `get_state()`가 실제로 읽는 필드만 흉내(hermetic — ORM 불요)."""

    grade: int | None = None
    target_grade: int | None = None
    target_score: int | None = None
    target_exam_date: date | None = None
    target_universities: list[dict[str, Any]] | None = None


class _QueueSession:
    """`execute()`가 호출 순서대로 미리 준 결과를 반환 — `get_state()` 내부 호출 순서:

    ①BKT 최신 숙달(`compute_concept_diagnoses` 1단계)
    ②IRT abilities(`compute_concept_diagnoses` → `compute_concept_abilities`)
    ③전과목 θ(`get_current_theta`)
    ④활성 오개념 id(`_get_active_misconception_ids`)
    그 뒤 `session.get(UserProfile, user_id)` 1회(execute 큐와 별개).
    """

    def __init__(self, results: list[list[Any]], profile: _FakeProfile | None) -> None:
        self._results = list(results)
        self._profile = profile

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(self._results.pop(0))

    async def get(self, _model: Any, _pk: Any) -> _FakeProfile | None:
        return self._profile


def _session(
    *,
    bkt_rows: list[Any] | None = None,
    ability_rows: list[Any] | None = None,
    theta_rows: list[Any] | None = None,
    misconception_rows: list[Any] | None = None,
    profile: _FakeProfile | None = None,
) -> AsyncSession:
    return cast(
        AsyncSession,
        _QueueSession(
            [
                bkt_rows or [],
                ability_rows or [],
                theta_rows or [],
                misconception_rows or [],
            ],
            profile,
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# 정상 조립 — 각 필드가 기존 좌석 재사용으로 올바르게 채워지는지
# ──────────────────────────────────────────────────────────────────────────
class TestGetState:
    async def test_mastery_and_domain_abilities_from_diagnoses(self) -> None:
        cid_a, cid_b = uuid.uuid4(), uuid.uuid4()
        session = _session(
            bkt_rows=[
                (cid_a, "MATH-A", "개념A", 0.9),  # 숙달(>=0.8)
                (cid_b, "MATH-B", "개념B", 0.2),  # 초보(<0.4)
            ],
            theta_rows=[0.5],  # 전과목 θ
            profile=_FakeProfile(grade=2),
        )
        state = await get_state(session, _UID)
        assert state.mastery == {"MATH-A": 0.9, "MATH-B": 0.2}
        assert state.general_ability == 0.5
        assert state.grade == 2

    async def test_domain_abilities_keyed_by_concept_code_irt_theta_source(
        self,
    ) -> None:
        cid = uuid.uuid4()
        session = _session(
            ability_rows=[(cid, "MATH-C", "개념C", True, 0.5, None)],  # 정답·난이도 0.5
            theta_rows=[None],
        )
        state = await get_state(session, _UID)
        # irt_theta 소스 — concept_code가 키, θ 자체가 값(도메인명 아님 — docstring 명시).
        assert "MATH-C" in state.domain_abilities
        assert isinstance(state.domain_abilities["MATH-C"], float)

    async def test_recent_struggles_and_successes_threshold_split(self) -> None:
        cid_a, cid_b, cid_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        session = _session(
            bkt_rows=[
                (cid_a, "LOW", "낮음", 0.3),  # < 0.4 → struggle
                (cid_b, "MID", "중간", 0.6),  # 0.4~0.8 → 어느 쪽도 아님
                (cid_c, "HIGH", "높음", 0.85),  # >= 0.8 → success
            ],
        )
        state = await get_state(session, _UID)
        assert state.recent_struggles == ["LOW"]
        assert state.recent_successes == ["HIGH"]

    async def test_active_misconceptions_from_own_select_not_l4(self) -> None:
        session = _session(misconception_rows=["MC-정의혼동", "MC-부호오류"])
        state = await get_state(session, _UID)
        assert state.active_misconceptions == ["MC-정의혼동", "MC-부호오류"]

    async def test_goals_assembled_from_target_fields_none_omitted(self) -> None:
        session = _session(
            profile=_FakeProfile(
                target_grade=2,
                target_score=None,
                target_exam_date=date(2027, 11, 18),
                target_universities=None,
            )
        )
        state = await get_state(session, _UID)
        assert state.goals == {"target_grade": "2", "target_exam_date": "2027-11-18"}
        assert "target_score" not in state.goals
        assert "target_universities" not in state.goals

    async def test_goals_empty_dict_when_all_targets_none(self) -> None:
        session = _session(profile=_FakeProfile())
        state = await get_state(session, _UID)
        assert state.goals == {}

    # ──────────────────────────────────────────────────────────────────
    # 빈 데이터(신규 학생) — NO_DATA 센티널이 아니라 그냥 빈 컬렉션(단순 조립기 계약)
    # ──────────────────────────────────────────────────────────────────
    async def test_no_diagnoses_no_misconceptions_yields_empty_collections(
        self,
    ) -> None:
        session = _session(profile=None)
        state = await get_state(session, _UID)
        assert state.mastery == {}
        assert state.domain_abilities == {}
        assert state.active_misconceptions == []
        assert state.recent_struggles == []
        assert state.recent_successes == []
        assert state.general_ability is None
        assert state.grade is None
        assert state.goals == {}

    async def test_student_id_and_timestamp_populated(self) -> None:
        session = _session()
        state = await get_state(session, _UID)
        assert state.student_id == str(_UID)
        assert state.timestamp is not None


# ──────────────────────────────────────────────────────────────────────────
# 계층 경계 가드 — l2/learner_state.py는 whymath_backend.l4.*를 전혀 import하지 않는다
# ──────────────────────────────────────────────────────────────────────────
def test_learner_state_module_has_no_l4_import() -> None:
    """AST로 실제 import 문(TYPE_CHECKING 포함)만 검사 — 주석·docstring의 'L4' 언급은 무방.

    `test_no_import_cycle.py::test_l1_embedding_modules_have_no_l4_import`와 동일 패턴(역방향
    의존 회귀 가드). CLAUDE.md "L_n은 L_{n+1}을 알지 못한다"의 기계 시행.
    """
    module = "whymath_backend.l2.learner_state"
    spec = importlib.util.find_spec(module)
    assert spec is not None and spec.origin is not None, f"모듈 경로 해석 실패: {module}"
    with open(spec.origin, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=spec.origin)

    offending: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "whymath_backend.l4"
        ):
            offending.append(f"from {node.module} import ... (line {node.lineno})")
        elif isinstance(node, ast.Import):
            offending.extend(
                f"import {alias.name} (line {node.lineno})"
                for alias in node.names
                if alias.name.startswith("whymath_backend.l4")
            )
    assert not offending, f"{module}에 L4 역방향 import 발견:\n" + "\n".join(offending)
