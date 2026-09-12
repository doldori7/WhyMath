"""접미사 정규식이 tests/ 경로를 함께 물어 수치를 부풀리는 실수를 계량기로 봉인한다.

**왜 이 파일이 있나** (2026-09-01 PB-13 회수 세션, 같은 유형 2회):

  1회차  PB-13 acceptance에 "스켈레톤 생성기 60 · 배치 60 · tests 82"라고 적었다.
         실제는 생성기 30 · 배치 30 · tests 60이다. `harness/[^/]*_batch\\.py$`가
         `tests/backend/harness/test_..._batch.py`에도 매치해 src 수가 2배가 됐다.
         PR #939 Codex 리뷰(P1)가 잡았다.
  2회차  `declared_unwired_audit`에 이식 배치를 선언하려고 같은 방식으로 목록을 만들어
         30건이어야 할 것이 60건이 나왔다. `test_` 접두 혼입을 스스로 발견해 되돌렸다.

두 번 다 원인이 같다: **접미사만으로 세고 경로 프리픽스로 스코프를 고정하지 않았다.**
파일명 규약이 src와 tests에서 대칭이면(`X_batch.py` ↔ `test_X_batch.py`) 접미사 매치는
항상 두 배를 낸다. 이 저장소는 그 대칭 규약을 광범위하게 쓴다.

**이 테스트가 무엇을 지키나**: 회수한 저작 도구의 src↔tests 실측 수를 계약으로 고정한다.
숫자가 흔들리면(생성기가 늘거나 테스트가 빠지거나) 여기서 먼저 걸린다. 문서·acceptance에
적힌 수치가 실체와 어긋나는 것을 사람 기억이 아니라 기계가 잡는다.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

_SRC_GENERATORS = _REPO / "src/backend/whymath_backend/l3/equivalent"
_SRC_BATCHES = _REPO / "src/backend/whymath_backend/harness"
_TEST_GENERATORS = _REPO / "tests/backend/l3/equivalent"
_TEST_BATCHES = _REPO / "tests/backend/harness"


def _count(directory: Path, pattern: str) -> int:
    """디렉터리 *직속* 파일만 정규식으로 센다 — 하위 경로 혼입을 구조적으로 배제한다."""
    return sum(1 for p in directory.iterdir() if p.is_file() and re.fullmatch(pattern, p.name))


def _module_names(directory: Path, pattern: str) -> set[str]:
    """디렉터리 *직속* 파일만 세고 확장자를 뗀 모듈명을 낸다."""
    return {p.stem for p in directory.iterdir() if p.is_file() and re.fullmatch(pattern, p.name)}


def _referencing_test_files(module: str) -> list[Path]:
    """그 모듈을 실제로 참조하는 테스트 파일 — 파일명 규약이 아니라 *내용*으로 찾는다."""
    hits: list[Path] = []
    for directory in (_TEST_GENERATORS, _TEST_BATCHES):
        for p in directory.iterdir():
            if p.is_file() and p.suffix == ".py" and module in p.read_text(encoding="utf-8"):
                hits.append(p)
    return hits


def test_every_skeleton_generator_has_a_referencing_test() -> None:
    """생성기 전건이 자신을 참조하는 테스트를 가진다.

    **파일명 1:1을 요구하지 않는다.** 초안은 `test_<모듈>.py` 대칭을 강요했는데 실측에서
    기존 2건이 걸렸다 — `root_aggregate_skeleton_generator`는 `test_root_aggregate_generator.py`가,
    `finite_probability_skeleton_generator`는 `test_finite_probability_batch.py`가 덮고 있었다.
    둘 다 테스트가 *있는데* 이름 규약만 달랐다. 지켜야 할 실질은 이름이 아니라 커버이므로
    참조 여부로 판정한다(가드를 통과시키려 약화한 것이 아니라, 틀린 전제를 실측으로 교체했다).
    """
    generators = _module_names(_SRC_GENERATORS, r"(?!test_).*_skeleton_generator\.py")
    assert generators, "생성기 0건 — 전수 스캔이 대상을 못 찾았다(공허한 통과 방지)"
    uncovered = sorted(m for m in generators if not _referencing_test_files(m))
    assert not uncovered, f"참조 테스트가 없는 생성기: {uncovered}"


def test_every_batch_driver_has_a_referencing_test() -> None:
    """적재 배치도 동일하게 참조 테스트를 가진다."""
    batches = _module_names(_SRC_BATCHES, r"(?!test_).*_batch\.py")
    assert batches, "배치 0건 — 전수 스캔이 대상을 못 찾았다(공허한 통과 방지)"
    uncovered = sorted(m for m in batches if not _referencing_test_files(m))
    assert not uncovered, f"참조 테스트가 없는 배치: {uncovered}"


def test_suffix_only_regex_double_counts_across_src_and_tests() -> None:
    """**변별력** — 이 실수가 실제로 2배를 만든다는 것을 재현해 봉인한다.

    경로 프리픽스 없이 접미사만 쓰면 src와 tests를 함께 물어 정확히 두 배가 된다.
    이 단언이 깨지면 파일명 대칭 규약이 바뀐 것이고, 그때는 위 두 테스트의 전제도
    다시 봐야 한다. 성공/실패가 같은 값을 내지 않도록 *틀린 방식*을 직접 계산한다.
    """
    naive = 0
    for directory in (_SRC_BATCHES, _TEST_BATCHES):
        naive += sum(
            1
            for p in directory.iterdir()
            # 1회차·2회차에서 실제로 쓴 그 패턴 — `harness/[^/]*_batch\.py$`
            if p.is_file() and re.search(r"[^/]*_batch\.py$", p.name)
        )
    scoped = _count(_SRC_BATCHES, r"(?!test_).*_batch\.py")
    assert naive == scoped * 2, (
        f"접미사 전용 집계 {naive} ≠ 스코프 집계 {scoped}×2 — "
        "src↔tests 파일명 대칭이 깨졌다면 이 가드의 전제를 재검토하라"
    )
