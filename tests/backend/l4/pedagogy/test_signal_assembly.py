"""`build_student_signals` 단위테스트 — grade_band 생산자 배선(PED-06, PED-08로 이관).

정본: `docs/architecture/04e_pedagogy_strategy_catalog.md` §4 — "신호 추가는 생산자 먼저"
(04d §2.1). `build_student_signals`가 `UserProfile.grade`(10~14 — `schema/user.py` 계약)를
`grade_to_band`로 파생해 `StudentSignals.grade_band`에 싣는 배선을 검증한다(필드만 만들고
항상 None이면 04d §2.1 위반 — 이 파일이 생산자 실배선의 증거다).

PED-08(coach 실행용 축 수렴)이 `api/study.py::_build_signals`를 study·coach 공용 좌석
(`l4/pedagogy/signal_assembly.py`)으로 추출하며 이 파일도 함께 이관됐다 — 원본
`tests/backend/api/test_study_signals.py::TestBuildSignalsGradeBand`와 동일 관심사·동일
어서션(회귀 0), import 경로만 바뀐다.

hermetic: DB 0 — 세션 대역 + `compute_concept_diagnoses` monkeypatch(모듈 네임스페이스).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from whymath_backend.db.models.user import UserProfile
from whymath_backend.l4.pedagogy import signal_assembly

_UID = uuid.uuid4()


@dataclass
class _FakeProfile:
    """`UserProfile` 최소 대역 — `build_student_signals`는 `.grade`만 읽는다."""

    grade: int | None = 12


@dataclass
class _FakeDiagnosis:
    """`ConceptDiagnosis` 최소 대역 — `build_student_signals`가 읽는 4속성만."""

    concept_code: str = "A1"
    bkt_mastery: float | None = 0.9
    irt_mastery_proxy: float | None = None
    irt_theta: float | None = 0.4


class _FakeSession:
    """`session.get(UserProfile, pk)`만 흉내 — 진단은 monkeypatch로 대체된다."""

    def __init__(self, profile: _FakeProfile | None) -> None:
        self._profile = profile
        self.get_models: list[object] = []

    async def get(self, model: object, _pk: object) -> _FakeProfile | None:
        self.get_models.append(model)
        return self._profile if model is UserProfile else None


def _patch_diagnoses(monkeypatch: pytest.MonkeyPatch, diagnoses: list[_FakeDiagnosis]) -> None:
    """signal_assembly 모듈 네임스페이스의 `compute_concept_diagnoses`를 대역으로 교체."""

    async def _fake(_session: Any, _user_id: uuid.UUID) -> list[_FakeDiagnosis]:
        return diagnoses

    monkeypatch.setattr(signal_assembly, "compute_concept_diagnoses", _fake)


class TestBuildStudentSignalsGradeBand:
    """grade_band 생산자 — UserProfile.grade → grade_to_band → StudentSignals 배선."""

    @pytest.mark.asyncio
    async def test_profile_grade_flows_into_grade_band(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_diagnoses(monkeypatch, [])
        session = _FakeSession(_FakeProfile(grade=12))  # 고3
        signals = await signal_assembly.build_student_signals(
            session, _UID, "A1"  # type: ignore[arg-type]
        )
        assert signals.grade_band == "고등"
        assert UserProfile in session.get_models  # 프로필을 실제로 조회했다(생산자 실배선).

    @pytest.mark.asyncio
    async def test_nsu_grade_maps_to_high_band(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # N수(13) — 고교 과정 재학습이므로 고등 밴드(schema/user.py 10~14 계약).
        _patch_diagnoses(monkeypatch, [])
        signals = await signal_assembly.build_student_signals(
            _FakeSession(_FakeProfile(grade=13)), _UID, "A1"  # type: ignore[arg-type]
        )
        assert signals.grade_band == "고등"

    @pytest.mark.asyncio
    async def test_missing_profile_leaves_band_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 프로필 미존재 — 없는 값을 기본치로 채우지 않는다(가짜 통과 금지·축 스킵).
        _patch_diagnoses(monkeypatch, [])
        signals = await signal_assembly.build_student_signals(
            _FakeSession(None), _UID, "A1"  # type: ignore[arg-type]
        )
        assert signals.grade_band is None

    @pytest.mark.asyncio
    async def test_null_grade_leaves_band_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_diagnoses(monkeypatch, [])
        signals = await signal_assembly.build_student_signals(
            _FakeSession(_FakeProfile(grade=None)), _UID, "A1"  # type: ignore[arg-type]
        )
        assert signals.grade_band is None

    @pytest.mark.asyncio
    async def test_diagnosis_hit_path_also_carries_grade_band(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 숙달 진단이 있는 분기에서도 grade_band가 함께 실린다(두 반환 경로 모두 배선).
        _patch_diagnoses(monkeypatch, [_FakeDiagnosis(concept_code="A1", bkt_mastery=0.9)])
        signals = await signal_assembly.build_student_signals(
            _FakeSession(_FakeProfile(grade=8)), _UID, "A1"  # type: ignore[arg-type]
        )
        assert signals.grade_band == "중학"
        assert signals.bkt_mastery == 0.9  # 기존 숙달 축 무변경.
