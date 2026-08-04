"""개념 지식 자산 도달 관측 리포트 테스트 — 결정론·정직 표기·변별력 동결(hermetic).

대상: `whymath_backend.harness.concept_reach_report`(KG-01 acceptance②~⑤). 실 DB·LLM·네트워크
0 — `tmp_path`에 가짜 mobile/backend 디렉터리를 만들어 검증한다. 실 코퍼스 대상 스모크 테스트
1건만 실제 `src/mobile/lib`·`src/backend/whymath_backend/api`를 읽는다(회귀 감시용).

**변별력**(CLAUDE.md "변별력 없는 검증 스텝 금지" — acceptance④ 그대로):
  - 표면 하나를 참조하는 가짜 dart 호출을 주입하면 그 표면만 '도달'로 바뀌고, 제거하면 다시
    '미도달'로 돌아온다(양방향).
  - `concepts.py`의 경로 공유 그룹(`/v1/concepts` 등)은 리터럴 하나만 주입해도 그룹 전체가
    동시에 '도달'로 바뀐다 — 이는 버그가 아니라 정적 스캔의 원리적 한계이며, 이 동시 반응
    자체를 assert해 회귀를 감시한다(미래에 메서드 인식이 추가돼 분리되면 이 테스트가 깨져
    설계 변경을 알린다).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.harness import concept_reach_report as crr


def _make_roots(tmp_path: Path) -> tuple[Path, Path]:
    mobile_root = tmp_path / "mobile_lib"
    api_root = tmp_path / "api"
    mobile_root.mkdir()
    api_root.mkdir()
    return mobile_root, api_root


# ──────────────────────────────────────────────────────────────────────────
# 1. 로더 — 정상·정직 실패
# ──────────────────────────────────────────────────────────────────────────
def test_load_scan_root_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        crr.load_scan_root(tmp_path / "없음", label="x")


def test_load_scan_root_rejects_non_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "파일.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        crr.load_scan_root(file_path, label="x")


def test_load_scan_root_accepts_directory(tmp_path: Path) -> None:
    assert crr.load_scan_root(tmp_path, label="x") == tmp_path


# ──────────────────────────────────────────────────────────────────────────
# 2. 집계 — hermetic 0건 베이스라인
# ──────────────────────────────────────────────────────────────────────────
def test_build_report_all_unreached_on_empty_roots(tmp_path: Path) -> None:
    mobile_root, api_root = _make_roots(tmp_path)
    report = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)

    assert len(report.surfaces) == 10
    assert report.unreached_count == 10
    assert all(s.status == "미도달" for s in report.surfaces)
    assert all(s.reach_count == 0 for s in report.surfaces)
    assert all(s.matched_files == () for s in report.surfaces)
    assert report.total_v1_literal_callsites == 0
    assert report.total_v1_literal_callsites_detail == ()


def test_build_report_exposes_method_ambiguous_groups(tmp_path: Path) -> None:
    """경로 공유 그룹이 항상 노출된다(0건 상태에서도) — 한계를 숨기지 않는다."""
    mobile_root, api_root = _make_roots(tmp_path)
    report = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)

    groups = {frozenset(g) for g in report.method_ambiguous_groups}
    assert frozenset({"concepts_create", "concepts_list"}) in groups
    assert frozenset({"concepts_read", "concepts_patch", "concepts_delete"}) in groups
    # 단독 표면은 그룹에 없어야 한다
    singleton_keys = {
        "concepts_search",
        "concepts_edges",
        "concept_content_flashcards",
        "me_prerequisites",
        "me_learning_path",
    }
    for group in groups:
        assert not (group & singleton_keys)


def test_build_report_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        crr.build_report(mobile_root=tmp_path / "없음", backend_api_root=tmp_path)


# ──────────────────────────────────────────────────────────────────────────
# 3. 변별력(mutation) — 양방향, acceptance④ 핵심
# ──────────────────────────────────────────────────────────────────────────
def test_unique_surface_mutation_round_trips(tmp_path: Path) -> None:
    """고유 패턴 표면(concepts_search) — 주입→도달, 제거→미도달(양방향)."""
    mobile_root, api_root = _make_roots(tmp_path)
    fake_dart = mobile_root / "fake_caller.dart"

    baseline = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    baseline_search = next(s for s in baseline.surfaces if s.key == "concepts_search")
    assert baseline_search.status == "미도달"

    fake_dart.write_text("_dio.get('/v1/concepts/search');", encoding="utf-8")
    mutated = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    mutated_search = next(s for s in mutated.surfaces if s.key == "concepts_search")
    assert mutated_search.status == "도달"
    assert mutated_search.reach_count == 1
    assert mutated_search.matched_files == ("fake_caller.dart",)
    # 인접 단독 표면(concepts_edges)은 오염되지 않는다(오탐 방지 확인)
    mutated_edges = next(s for s in mutated.surfaces if s.key == "concepts_edges")
    assert mutated_edges.status == "미도달"

    fake_dart.unlink()
    restored = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    restored_search = next(s for s in restored.surfaces if s.key == "concepts_search")
    assert restored_search.status == "미도달"
    assert restored_search.reach_count == baseline_search.reach_count == 0


def test_shared_pattern_group_flips_together_not_a_bug(tmp_path: Path) -> None:
    """`/v1/concepts` 리터럴 하나만 주입해도 concepts_create·concepts_list 둘 다 도달로
    바뀐다 — 메서드 구분 불가라는 설계된 한계를 회귀 감시한다(분리되면 이 테스트가 깨진다)."""
    mobile_root, api_root = _make_roots(tmp_path)
    fake_dart = mobile_root / "fake_caller.dart"

    fake_dart.write_text("_dio.get('/v1/concepts');", encoding="utf-8")
    mutated = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    by_key = {s.key: s for s in mutated.surfaces}
    assert by_key["concepts_create"].status == "도달"
    assert by_key["concepts_list"].status == "도달"
    assert by_key["concepts_create"].matched_files == by_key["concepts_list"].matched_files
    # 겹치지 않는 그룹(read/patch/delete)은 여전히 미도달
    assert by_key["concepts_read"].status == "미도달"

    fake_dart.unlink()
    restored = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    restored_by_key = {s.key: s for s in restored.surfaces}
    assert restored_by_key["concepts_create"].status == "미도달"
    assert restored_by_key["concepts_list"].status == "미도달"


def test_flashcards_axis_scans_backend_api_not_mobile(tmp_path: Path) -> None:
    """flashcards 축은 mobile이 아니라 backend api/ 디렉터리를 스캔한다."""
    mobile_root, api_root = _make_roots(tmp_path)
    fake_py = api_root / "foo.py"

    baseline = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    assert next(s for s in baseline.surfaces if s.key == "concept_content_flashcards").status == (
        "미도달"
    )

    fake_py.write_text("def read_content():\n    return record.flashcards\n", encoding="utf-8")
    mutated = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    mutated_fc = next(s for s in mutated.surfaces if s.key == "concept_content_flashcards")
    assert mutated_fc.status == "도달"
    assert mutated_fc.matched_files == ("foo.py",)

    fake_py.unlink()
    restored = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    assert (
        next(s for s in restored.surfaces if s.key == "concept_content_flashcards").status
        == "미도달"
    )


def test_test_directory_excluded_from_scan(tmp_path: Path) -> None:
    """`test`/`tests` 이름의 하위 디렉터리는 스캔에서 제외된다(20 vs 13 재발 방지 가드)."""
    mobile_root, api_root = _make_roots(tmp_path)
    test_dir = mobile_root / "test"
    test_dir.mkdir()
    (test_dir / "mock.dart").write_text("_dio.get('/v1/concepts/search');", encoding="utf-8")

    report = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    assert next(s for s in report.surfaces if s.key == "concepts_search").status == "미도달"
    assert report.total_v1_literal_callsites == 0


# ──────────────────────────────────────────────────────────────────────────
# 4. 렌더/JSON — 결정론
# ──────────────────────────────────────────────────────────────────────────
def test_render_report_is_deterministic(tmp_path: Path) -> None:
    mobile_root, api_root = _make_roots(tmp_path)
    r1 = crr.render_report(crr.build_report(mobile_root=mobile_root, backend_api_root=api_root))
    r2 = crr.render_report(crr.build_report(mobile_root=mobile_root, backend_api_root=api_root))
    assert r1 == r2
    assert "미도달 표면: **10/10**" in r1
    assert "concepts_create" in r1 and "concepts_list" in r1


def test_render_report_truncates_callsite_detail_and_notes_remainder(tmp_path: Path) -> None:
    mobile_root, api_root = _make_roots(tmp_path)
    for i in range(5):
        (mobile_root / f"f{i}.dart").write_text(f"_dio.get('/v1/fake{i}');", encoding="utf-8")
    report = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)
    assert report.total_v1_literal_callsites == 5
    rendered = crr.render_report(report, max_listed=2)
    assert "…외 **3**건" in rendered


def test_report_to_json_round_trips(tmp_path: Path) -> None:
    mobile_root, api_root = _make_roots(tmp_path)
    (mobile_root / "f.dart").write_text("_dio.get('/v1/concepts/search');", encoding="utf-8")
    report = crr.build_report(mobile_root=mobile_root, backend_api_root=api_root)

    payload = crr.report_to_json(report)
    assert payload["unreached_count"] == 9
    assert payload["total_v1_literal_callsites"] == 1

    dumped = crr.dump_json(report)
    assert json.loads(dumped) == payload


# ──────────────────────────────────────────────────────────────────────────
# 5. CLI — exit 코드 규율(게이트 아님·입력 오류만 2)
# ──────────────────────────────────────────────────────────────────────────
def test_main_exit_0_even_when_all_surfaces_unreached(tmp_path: Path) -> None:
    mobile_root, api_root = _make_roots(tmp_path)
    exit_code = crr.main(["--mobile-root", str(mobile_root), "--backend-api-root", str(api_root)])
    assert exit_code == 0


def test_main_exit_2_on_missing_mobile_root(tmp_path: Path) -> None:
    exit_code = crr.main(["--mobile-root", str(tmp_path / "없음")])
    assert exit_code == 2


def test_main_writes_json_artifact(tmp_path: Path) -> None:
    mobile_root, api_root = _make_roots(tmp_path)
    out_path = tmp_path / "out" / "report.json"

    exit_code = crr.main(
        [
            "--mobile-root",
            str(mobile_root),
            "--backend-api-root",
            str(api_root),
            "--json",
            str(out_path),
        ]
    )
    assert exit_code == 0
    assert out_path.is_file()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["total_v1_literal_callsites"] == 0
    assert len(payload["surfaces"]) == 10


# ──────────────────────────────────────────────────────────────────────────
# 6. 실 코퍼스 스모크(회귀 감시 — 핵심 신호)
# ──────────────────────────────────────────────────────────────────────────
def test_real_corpus_smoke_all_ten_surfaces_unreached_and_thirteen_callsites() -> None:
    """실제 src/mobile/lib·src/backend/whymath_backend/api를 읽어 확인한다.

    `total_v1_literal_callsites`가 13이 아니게 되면(모바일이 실제로 이 표면들 중 하나를
    호출하기 시작하면) 이 테스트가 깨져서 "가시화 리포트가 낡았다"를 자동으로 신호한다 —
    의도된 동작(회귀 감시이지 임의 임계값이 아니다).
    """
    if not crr.DEFAULT_MOBILE_LIB_ROOT.is_dir() or not crr.DEFAULT_BACKEND_API_ROOT.is_dir():
        pytest.skip("실 mobile/backend 경로 미존재")

    report = crr.build_report()
    assert all(s.status == "미도달" for s in report.surfaces)
    assert all(s.reach_count == 0 for s in report.surfaces)
    assert report.total_v1_literal_callsites == 13
    assert isinstance(crr.render_report(report), str)
    assert isinstance(crr.dump_json(report), str)
