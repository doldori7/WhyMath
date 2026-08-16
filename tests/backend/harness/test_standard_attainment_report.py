"""성취기준 도달 관측 리포트 테스트 — 결정론·정직 회계·경계값 변별(hermetic).

대상: `whymath_backend.harness.standard_attainment_report`(ASM-05 수요측 관측 — ARCH-18 공급측
커버리지의 짝). `build_report`는 순수 함수라 실 DB 없이 합성 `AttainmentInputs`로 검증한다.
DB를 실제로 여는 통합테스트는 `tests/backend/db/test_standard_attainment_report_integration.py`
(acceptance ⑤ 델타 변별력)에 별도로 있다.

**변별력**(CLAUDE.md "변별력 없는 검증 스텝 금지"): 각 테스트는 *그 규약이 깨진 구현에서 실제로
실패하는지*를 기준으로 짰다 —
  - 도달 경계(0.8 vs 0.79)를 ±ε 옮기면 경계값 테스트가 실패한다(도달/미도달이 실제로 갈린다).
  - 측정 사용자 0에서 0.0%를 내면 "데이터없음" 테스트가 실패한다(가짜 비율 위장 차단).
  - 매핑 없는 측정(concept 미해소/원자 축 밖/빈 standard_codes)을 조용히 버리면 결손 계상
    테스트가 실패한다 — 세 상태는 서로 다른 카운터다.
  - 다른 개정/대장 밖 코드를 대상 개정에 뭉개면 3분류 테스트가 실패한다.
  - 집계가 입력 순서에 의존하면 역순 입력 동일성 테스트가 실패한다.
  - 0도달 목록을 조용히 자르면 절단 고지 테스트가 실패한다.
  - user_id를 렌더/JSON에 실으면 개인 식별자 미노출 테스트가 실패한다.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from whymath_backend.harness import standard_attainment_report as sar
from whymath_backend.harness.problem_bank_coverage import StandardsCatalog, load_standards
from whymath_backend.l4.lthc.adapt import _MASTERED_THRESHOLD
from whymath_backend.schema.enums import Role

# tests/backend/harness/ → tests/backend → tests → repo root → src/backend
_BACKEND_DIR = Path(__file__).resolve().parents[3] / "src" / "backend"

_REV_2022 = "2022 개정"
_REV_2015 = "2015 개정"


# ──────────────────────────────────────────────────────────────────────────
# 픽스처 헬퍼
# ──────────────────────────────────────────────────────────────────────────
def _standard(code: str, revision: str = _REV_2022) -> dict[str, object]:
    return {
        "norm_id": f"{revision[:4]}_{code}",
        "code": code,
        "curriculum_revision": revision,
        "school_type": "고등학교",
        "domain": "대수",
    }


def _catalog(*entries: dict[str, object]) -> StandardsCatalog:
    return load_standards({"standards": list(entries)})


def _m(
    *,
    user_id: uuid.UUID | None = None,
    concept_id: uuid.UUID | None = None,
    mastery: float | None = 0.9,
    concept_code: str | None = "math.algebra.quadratic",
    atom_code: str | None = "math.algebra.quadratic",
    standard_codes: tuple[str, ...] = ("[10공수1-02-02]",),
    profile_role: Role | None = Role.STUDENT,
) -> sar.LatestMeasurement:
    return sar.LatestMeasurement(
        user_id=user_id if user_id is not None else uuid.uuid4(),
        concept_id=concept_id if concept_id is not None else uuid.uuid4(),
        mastery=mastery,
        concept_code=concept_code,
        atom_code=atom_code,
        standard_codes=standard_codes,
        profile_role=profile_role,
    )


def _inputs(
    *,
    students: int = 1,
    measurements: tuple[sar.LatestMeasurement, ...] = (),
    mapped: tuple[str, ...] = (),
) -> sar.AttainmentInputs:
    return sar.AttainmentInputs(
        student_profile_count=students,
        latest_measurements=measurements,
        atom_mapped_codes=mapped,
    )


# ──────────────────────────────────────────────────────────────────────────
# 1. 도달 경계 — 0.8은 도달, 0.79는 미도달(±ε이 결과를 실제로 가른다)
# ──────────────────────────────────────────────────────────────────────────
def test_boundary_mastery_at_threshold_attains_and_below_does_not() -> None:
    """경계 포함(≥ 0.8)은 L4 정본("경계 포함은 상위 라벨")과 동일해야 한다."""
    code = "[10공수1-02-02]"
    catalog = _catalog(_standard(code))
    at = sar.build_report(
        _inputs(measurements=(_m(mastery=0.8, standard_codes=(code,)),), mapped=(code,)),
        catalog,
        revision=_REV_2022,
    )
    below = sar.build_report(
        _inputs(measurements=(_m(mastery=0.79, standard_codes=(code,)),), mapped=(code,)),
        catalog,
        revision=_REV_2022,
    )
    assert at.attained_measurement_count == 1
    assert at.attained_users_per_code == {code: 1}
    assert at.zero_attainment_codes == ()
    assert below.attained_measurement_count == 0
    assert below.attained_users_per_code == {}
    assert below.zero_attainment_codes == (code,)


def test_threshold_is_l4_canonical_value_not_a_new_knob() -> None:
    """임계 신설 금지 — 도달 경계는 `l4/lthc/adapt.py::_MASTERED_THRESHOLD`의 재사용이어야 한다."""
    assert sar._ATTAINMENT_MASTERY_THRESHOLD == pytest.approx(_MASTERED_THRESHOLD)
    report = sar.build_report(_inputs(), _catalog(_standard("[10공수1-02-02]")), revision=_REV_2022)
    assert report.threshold == pytest.approx(_MASTERED_THRESHOLD)


# ──────────────────────────────────────────────────────────────────────────
# 2. NO_DATA 정직 — 측정 사용자 0이면 비율 None·렌더 "데이터없음"(0.0% 위장 금지)
# ──────────────────────────────────────────────────────────────────────────
def test_zero_measured_users_yield_none_rates_and_data_missing_render() -> None:
    code = "[10공수1-02-02]"
    report = sar.build_report(
        _inputs(students=5, mapped=(code,)), _catalog(_standard(code)), revision=_REV_2022
    )
    assert report.measured_user_count == 0
    assert report.per_user_attained_mean is None
    assert report.per_user_attained_min is None
    assert report.per_user_attained_max is None
    assert report.code_attainment_rate is None
    rendered = sar.render_report(report)
    assert "데이터없음" in rendered
    assert "0.0%" not in rendered  # 측정 없음을 0.0%로 위장하지 않는다.
    # 학생 분모(①)는 별개 축으로 살아 있다 — 이중 회계(측정 0이 등록 0을 뜻하지 않는다).
    assert report.student_profile_count == 5


# ──────────────────────────────────────────────────────────────────────────
# 3. 결손 계상 — 매핑 없는 측정 3상태가 조용히 사라지지 않고 각각 계상된다
# ──────────────────────────────────────────────────────────────────────────
def test_unmapped_measurement_states_counted_separately_not_dropped() -> None:
    """concept 미해소 / 원자 축 밖 / 빈 standard_codes — 서로 다른 상태·서로 다른 카운터."""
    uid = uuid.UUID(int=1)
    ms = (
        _m(
            user_id=uid,
            concept_id=uuid.UUID(int=11),
            concept_code=None,
            atom_code=None,
            standard_codes=(),
        ),
        _m(user_id=uid, concept_id=uuid.UUID(int=12), atom_code=None, standard_codes=()),
        _m(user_id=uid, concept_id=uuid.UUID(int=13), standard_codes=()),
    )
    report = sar.build_report(
        _inputs(measurements=ms), _catalog(_standard("[10공수1-02-02]")), revision=_REV_2022
    )
    assert report.latest_measurement_count == 3
    assert report.measurements_concept_unresolved == 1
    assert report.measurements_outside_atom_axis == 1
    assert report.measurements_with_empty_standard_codes == 1
    # 셋 다 mastery 0.9(도달 측정)이지만 코드로는 번역되지 않는다 — 도달 쌍 0이 정직한 값.
    assert report.attained_measurement_count == 3
    assert report.attained_user_code_pair_count == 0


def test_mastery_none_is_neither_attained_nor_silently_dropped() -> None:
    report = sar.build_report(
        _inputs(measurements=(_m(mastery=None),), mapped=("[10공수1-02-02]",)),
        _catalog(_standard("[10공수1-02-02]")),
        revision=_REV_2022,
    )
    assert report.latest_measurement_count == 1
    assert report.measurements_without_mastery == 1
    assert report.attained_measurement_count == 0
    assert report.measured_user_count == 1  # 측정 사용자로는 계상된다(값 없음 ≠ 측정 없음).


# ──────────────────────────────────────────────────────────────────────────
# 4. 코드 3분류 — 대상 개정 / 다른 개정 / 대장 밖(공급 축·수요 축 모두)
# ──────────────────────────────────────────────────────────────────────────
def test_other_revision_and_unknown_codes_accounted_separately() -> None:
    target = "[10공수1-02-02]"
    other = "[2수01-01]"
    unknown = "[9수99-99]"
    catalog = _catalog(_standard(target), _standard(other, _REV_2015))
    m = _m(mastery=0.95, standard_codes=(target, other, unknown))
    report = sar.build_report(
        _inputs(measurements=(m,), mapped=(target, other, unknown)),
        catalog,
        revision=_REV_2022,
    )
    # 공급 축 3분류 — 매핑 코드가 개정 축에서 조용히 유실되지 않는다.
    assert report.observable_codes == (target,)
    assert report.mapped_other_revision_code_count == 1
    assert report.mapped_unknown_code_count == 1
    # 수요 축 3분류 — 대상 개정만 도달 쌍이 되고, 나머지는 각각 정직 회계로 남는다.
    assert report.attained_users_per_code == {target: 1}
    assert report.attained_other_revision_codes == {other: 1}
    assert report.attained_unknown_codes == {unknown: 1}


def test_unobservable_target_codes_are_not_listed_as_zero_attainment() -> None:
    """원자 매핑 밖 대상 개정 코드는 '관측 불가'다 — 0도달(관측 가능인데 아무도 도달하지 못함)과
    다른 상태이며, 0도달 목록에 섞이면 안 된다."""
    mapped = "[10공수1-02-02]"
    unmapped = "[10공수1-03-01]"
    catalog = _catalog(_standard(mapped), _standard(unmapped))
    m = _m(mastery=0.5, standard_codes=(mapped,))  # 측정은 있으나 도달은 없다.
    report = sar.build_report(
        _inputs(measurements=(m,), mapped=(mapped,)), catalog, revision=_REV_2022
    )
    assert report.unobservable_codes == (unmapped,)
    assert report.zero_attainment_codes == (mapped,)
    assert unmapped not in report.zero_attainment_codes


# ──────────────────────────────────────────────────────────────────────────
# 5. 분모 이중 회계 — 등록 학생 수 vs 측정 사용자 수 + 느슨참조 불일치
# ──────────────────────────────────────────────────────────────────────────
def test_denominator_dual_accounting_and_loose_reference_mismatch() -> None:
    code = "[10공수1-02-02]"
    ms = (
        _m(user_id=uuid.UUID(int=1), concept_id=uuid.UUID(int=11), profile_role=Role.STUDENT),
        _m(user_id=uuid.UUID(int=2), concept_id=uuid.UUID(int=12), profile_role=None),
        _m(
            user_id=uuid.UUID(int=3),
            concept_id=uuid.UUID(int=13),
            profile_role=Role.CONTENT_ADMIN,
        ),
    )
    report = sar.build_report(
        _inputs(students=7, measurements=ms, mapped=(code,)),
        _catalog(_standard(code)),
        revision=_REV_2022,
    )
    assert report.student_profile_count == 7  # ① 등록 학생 — 측정과 무관한 분모.
    assert report.measured_user_count == 3  # ② 측정 사용자 — ①과 다른 수로 공존(혼동 금지).
    assert report.measured_users_outside_profile == 1  # 느슨참조 불일치도 계상.
    assert report.measured_users_non_student == 1


# ──────────────────────────────────────────────────────────────────────────
# 6. 사용자별 분포 — 도달 0인 측정 사용자도 분포에 들어간다
# ──────────────────────────────────────────────────────────────────────────
def test_per_user_distribution_includes_zero_attainment_users() -> None:
    code_a, code_b = "[10공수1-02-02]", "[10공수1-03-01]"
    catalog = _catalog(_standard(code_a), _standard(code_b))
    ms = (
        _m(
            user_id=uuid.UUID(int=1),
            concept_id=uuid.UUID(int=11),
            mastery=0.9,
            standard_codes=(code_a, code_b),
        ),
        _m(
            user_id=uuid.UUID(int=2),
            concept_id=uuid.UUID(int=12),
            mastery=0.3,
            standard_codes=(code_a,),
        ),
    )
    report = sar.build_report(
        _inputs(measurements=ms, mapped=(code_a, code_b)), catalog, revision=_REV_2022
    )
    assert report.attained_user_code_pair_count == 2
    assert report.users_with_any_attainment == 1
    assert report.per_user_attained_min == 0  # 측정만 있고 도달 0인 사용자도 분포의 일부다.
    assert report.per_user_attained_max == 2
    assert report.per_user_attained_mean == pytest.approx(1.0)


# ──────────────────────────────────────────────────────────────────────────
# 7. 결정론 — 같은 입력 2회 + 입력 순서 역전 → 동일 바이트
# ──────────────────────────────────────────────────────────────────────────
def test_render_and_json_deterministic_and_input_order_independent() -> None:
    code_a, code_b = "[10공수1-02-02]", "[2수01-01]"
    catalog = _catalog(_standard(code_a), _standard(code_b, _REV_2015))
    ms = (
        _m(user_id=uuid.UUID(int=1), concept_id=uuid.UUID(int=11), standard_codes=(code_a,)),
        _m(
            user_id=uuid.UUID(int=2),
            concept_id=uuid.UUID(int=12),
            mastery=0.85,
            standard_codes=(code_a, code_b),
        ),
        _m(user_id=uuid.UUID(int=3), concept_id=uuid.UUID(int=13), mastery=None),
    )
    mapped = (code_a, code_b, "[9수99-99]")
    forward = sar.build_report(_inputs(measurements=ms, mapped=mapped), catalog, revision=_REV_2022)
    again = sar.build_report(_inputs(measurements=ms, mapped=mapped), catalog, revision=_REV_2022)
    shuffled = sar.build_report(
        _inputs(measurements=tuple(reversed(ms)), mapped=tuple(reversed(mapped))),
        catalog,
        revision=_REV_2022,
    )
    assert sar.render_report(forward) == sar.render_report(again)
    assert sar.dump_json(forward) == sar.dump_json(again)
    assert sar.render_report(forward) == sar.render_report(shuffled)
    assert sar.dump_json(forward) == sar.dump_json(shuffled)


# ──────────────────────────────────────────────────────────────────────────
# 8. 절단 고지 — 0도달 목록을 잘랐으면 잘랐다고 쓴다(조용한 절단 금지)
# ──────────────────────────────────────────────────────────────────────────
def test_zero_attainment_truncation_is_announced() -> None:
    codes = ("[10공수1-01-01]", "[10공수1-01-02]", "[10공수1-01-03]")
    catalog = _catalog(*(_standard(c) for c in codes))
    m = _m(mastery=0.9, standard_codes=(codes[0],))
    report = sar.build_report(_inputs(measurements=(m,), mapped=codes), catalog, revision=_REV_2022)
    assert report.zero_attainment_codes == (codes[1], codes[2])
    text = sar.render_report(report, max_listed=1)
    assert "…외 **1**건" in text
    assert codes[1] in text  # 사전순 첫 코드만 실린다.
    assert codes[2] not in text
    # 전량은 JSON 산출물에 있다.
    payload = json.loads(sar.dump_json(report))
    assert payload["attainment"]["zero_attainment_codes"] == [codes[1], codes[2]]


# ──────────────────────────────────────────────────────────────────────────
# 9. 개인 식별자 미노출 — user_id는 렌더/JSON 어디에도 나열되지 않는다
# ──────────────────────────────────────────────────────────────────────────
def test_user_ids_never_listed_in_render_or_json() -> None:
    uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    code = "[10공수1-02-02]"
    report = sar.build_report(
        _inputs(
            measurements=(_m(user_id=uid, mastery=0.9, standard_codes=(code,)),), mapped=(code,)
        ),
        _catalog(_standard(code)),
        revision=_REV_2022,
    )
    assert str(uid) not in sar.render_report(report)
    assert str(uid) not in sar.dump_json(report)


# ──────────────────────────────────────────────────────────────────────────
# 10. 순수성·게이트 아님 — build_report는 세션 없이 호출되는 동기 순수 함수
# ──────────────────────────────────────────────────────────────────────────
def test_build_report_is_pure_sync_function_no_session() -> None:
    """hermetic 검증 가능성의 근거 — DB 세션 인자 없이 호출되는 동기 함수여야 한다."""
    assert not inspect.iscoroutinefunction(sar.build_report)
    report = sar.build_report(_inputs(), _catalog(_standard("[10공수1-02-02]")), revision=_REV_2022)
    assert isinstance(report, sar.StandardAttainmentReport)


def test_exit_codes_are_observation_not_gate() -> None:
    """게이트 아님 동결 — 종료 코드 어휘는 0(성공)/2(입력·DB 오류)뿐, 실패용 1이 없다."""
    assert sar._EXIT_OK == 0
    assert sar._EXIT_INPUT_ERROR == 2


# ──────────────────────────────────────────────────────────────────────────
# 11. CLI — --help exit 0 / DB·입력 오류 exit 2 + 예외 타입명 stderr(침묵 실패 금지)
# ──────────────────────────────────────────────────────────────────────────
def test_main_cli_smoke_help_exits_zero_without_db() -> None:
    """`--help`는 DB 접속 없이 exit 0이어야 한다(argparse 표준 동작 회귀 감시)."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "whymath_backend.harness.standard_attainment_report",
            "--help",
        ],
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
        # [OPS-44 사고 경위] 자식 --help 출력의 UTF-8 한국어를 부모가 로케일(cp949)로 디코드해
        # reader thread가 UnicodeDecodeError로 죽고 stdout=None이 됐다 — UTF-8 명시로 고정.
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0
    assert "attainment" in result.stdout.lower() or "도달" in result.stdout


def test_main_returns_exit_2_and_logs_exception_type_on_db_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    standards = tmp_path / "standards.json"
    standards.write_text(
        json.dumps({"standards": [_standard("[10공수1-02-02]")]}, ensure_ascii=False),
        encoding="utf-8",
    )
    with patch.object(sar, "_run", new=AsyncMock(side_effect=RuntimeError("접속 실패"))):
        exit_code = sar.main(["--standards", str(standards)])
    assert exit_code == sar._EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err  # 무타입 경고 금지 — 예외 타입명이 로그에 있어야 한다.


def test_main_returns_exit_2_when_standards_file_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = sar.main(["--standards", str(tmp_path / "missing.json")])
    assert exit_code == sar._EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert "FileNotFoundError" in captured.err


def test_main_returns_exit_2_on_unknown_revision(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    standards = tmp_path / "standards.json"
    standards.write_text(
        json.dumps({"standards": [_standard("[10공수1-02-02]")]}, ensure_ascii=False),
        encoding="utf-8",
    )
    exit_code = sar.main(["--standards", str(standards), "--revision", "1997 개정"])
    assert exit_code == sar._EXIT_INPUT_ERROR
    captured = capsys.readouterr()
    assert "대장에 없는 개정" in captured.err
