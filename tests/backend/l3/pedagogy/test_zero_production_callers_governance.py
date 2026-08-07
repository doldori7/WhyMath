"""콘텐츠 슬롯 파이프라인 '프로덕션 호출자 0' 동결 거버넌스 — PED-06 acceptance②.

`docs/architecture/ai_content_generation_gap_review_2.md` §2 G2/G3가 전수 grep으로 확인한
사실: `slot_generator.py`/`prescreen.py`/`review.py`를 `whymath_backend.l3.pedagogy` 밖에서
import하는 곳은 저장소 전체에 **0개**다(유일한 소비자는 자기 자신의 패키지 재-export와 E2E
파일럿 테스트뿐). 이 사실을 "언젠가 그렇다고 봤다"가 아니라 **매 CI 실행마다 재확인**하는
정적 스캐너다 — 새 프로덕션 소비자가 생기면(신규 저작 경로·신규 학생 대면 축을 여는 순간)
이 테스트가 **의도적으로 깨진다**. 그것이 "0 소비자"라는 계약이 바뀌었다는 신호다(§3 D6
acceptance②의 침묵 드리프트 금지 요구).

`whymath_backend.l3.pedagogy` 패키지 *자기 자신* 내부의 상호 참조(예: `review.py`가
`slot_generator.verify_slot_payload`를 재사용하는 것)는 위반이 아니다 — 이 스캐너는 그
디렉터리를 스캔 대상에서 제외한다(`exclude_dirs`).

`test_no_import_cycle.py`(AST 역방향-import 스캔)·`test_test_suite_wiring.py`(tmp_path
결함 주입 변별력 봉인) 두 선례의 결합형이다: 스캐너를 **root 디렉터리로 파라미터화된 재사용
함수**로 만들고(`scan_for_pedagogy_slot_pipeline_imports`), 실제 레포 판정과 가짜
tmp_path 레포 결함 주입 판정을 같은 함수로 돌려 "이 판정 장치가 실패 상태에서 실제로 실패
신호를 내는가"를 함께 봉인한다(변별력 없는 검증 스텝 금지).
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

# 이 파이프라인 3파일이 정의하는 프로덕션 API 표면 — 이 이름들의 import를 추적한다.
_TARGET_MODULE_NAMES: frozenset[str] = frozenset({"slot_generator", "prescreen", "review"})
# 파이프라인이 사는 패키지 접미사(`whymath_backend.l3.pedagogy` / 가짜 레포의 `l3.pedagogy`
# 둘 다 매치하도록 접두사가 아니라 **접미사**로 판정한다 — 스캐너가 최상위 패키지명에
# 의존하지 않아 tmp_path 가짜 레포(다른 최상위 이름)에도 그대로 재사용된다).
_PACKAGE_SUFFIX = ("l3", "pedagogy")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_REAL_SRC_ROOT = _REPO_ROOT / "src" / "backend" / "whymath_backend"
_REAL_PEDAGOGY_DIR = _REAL_SRC_ROOT / "l3" / "pedagogy"


@dataclass(frozen=True, slots=True)
class ForeignImportHit:
    """스캐너가 찾은 위반 1건 — 어느 파일 몇 번째 줄에서 무엇을 import했는지."""

    path: Path
    lineno: int
    statement: str


def _is_within(child: Path, ancestor: Path) -> bool:
    return child == ancestor or ancestor in child.parents


def _module_ends_with_package_suffix(module: str) -> bool:
    """`module`(점 표기 문자열)이 `_PACKAGE_SUFFIX`(예 `l3.pedagogy`)로 끝나는가."""
    parts = tuple(module.split("."))
    return len(parts) >= len(_PACKAGE_SUFFIX) and parts[-len(_PACKAGE_SUFFIX) :] == _PACKAGE_SUFFIX


def _module_ends_with_target_submodule(module: str) -> str | None:
    """`module`이 `...l3.pedagogy.<target>` 형태(접미사 매치)면 그 `<target>`을, 아니면 `None`.

    접두사 길이(패키지 앞에 뭐가 더 있는지)와 무관하게 **끝에서부터** 판정한다 — 실 레포의
    `whymath_backend.l3.pedagogy.slot_generator`(접두사 1단어)와 가짜 레포의
    `l3.pedagogy.slot_generator`(접두사 0단어) 양쪽 모두 접미사가 같으므로 매치한다.
    """
    needed = len(_PACKAGE_SUFFIX) + 1
    parts = tuple(module.split("."))
    if len(parts) < needed:
        return None
    prefix, tail = parts[-needed:-1], parts[-1]
    if prefix == _PACKAGE_SUFFIX and tail in _TARGET_MODULE_NAMES:
        return tail
    return None


def scan_for_pedagogy_slot_pipeline_imports(
    root: Path,
    *,
    exclude_dirs: Iterable[Path] = (),
) -> list[ForeignImportHit]:
    """`root` 하위 `.py` 전체를 AST로 훑어 슬롯 파이프라인 3모듈의 외부 import를 찾는다.

    다음 두 형태를 모두 잡는다:
      - `from <...>.l3.pedagogy import slot_generator` (패키지에서 서브모듈을 이름으로 import)
      - `from <...>.l3.pedagogy.slot_generator import build_slot_rows` (서브모듈 직접 import)
      - `import <...>.l3.pedagogy.slot_generator` (완전정규 import 문)

    `exclude_dirs`(절대경로) 하위 파일은 스캔하지 않는다 — 패키지 자기 자신의 내부 상호
    참조(예: `review.py`가 `slot_generator`를 재사용)는 위반이 아니다.

    토큰화 실패(구문 오류 `.py`)는 **예외로 올린다** — 조용히 건너뛰면 그 파일의 위반이
    영구히 안 보이게 된다(`test_test_suite_wiring.py`의 "위장 금지" 관례와 동형).
    """
    excluded = tuple(p.resolve() for p in exclude_dirs)
    hits: list[ForeignImportHit] = []
    for path in sorted(root.rglob("*.py")):
        resolved = path.resolve()
        if any(_is_within(resolved, ex) for ex in excluded):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise AssertionError(
                f"{path}: 파싱 실패(구문 오류) — 스캐너가 위장하지 않는다: {exc}"
            ) from exc

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                submodule_hit = _module_ends_with_target_submodule(module)
                if submodule_hit is not None:
                    hits.append(
                        ForeignImportHit(
                            path=path,
                            lineno=node.lineno,
                            statement=(
                                f"from {module} import "
                                + ", ".join(alias.name for alias in node.names)
                            ),
                        )
                    )
                    continue
                if _module_ends_with_package_suffix(module):
                    named = {alias.name for alias in node.names} & _TARGET_MODULE_NAMES
                    if named:
                        hits.append(
                            ForeignImportHit(
                                path=path,
                                lineno=node.lineno,
                                statement=(
                                    f"from {module} import "
                                    + ", ".join(alias.name for alias in node.names)
                                ),
                            )
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if _module_ends_with_target_submodule(alias.name) is not None:
                        hits.append(
                            ForeignImportHit(
                                path=path, lineno=node.lineno, statement=f"import {alias.name}"
                            )
                        )
    return hits


# ──────────────────────────────────────────────────────────────────────────
# 실제 레포 판정 — "동결" 그 자체(신규 외부 소비자가 생기면 이 테스트가 깨진다).
# ──────────────────────────────────────────────────────────────────────────
def test_no_production_caller_outside_l3_pedagogy_in_real_repo() -> None:
    """실측 — `l3/pedagogy/` 밖에서 slot_generator/prescreen/review를 import하는 곳이 0개다.

    `tests/backend/api/test_e2e_pedagogy_pilot_integration.py`(E2E 파일럿)는 `tests/` 밖
    (`src/backend/whymath_backend/`)만 스캔하므로 이 판정에 걸리지 않는다 — 그 파일이
    유일한 실행자라는 사실 자체가 이 태스크의 관측 대상이지, 이 게이트가 막아야 할 대상이
    아니다(§3 D6 — 테스트 소비는 프로덕션 소비가 아니다).
    """
    hits = scan_for_pedagogy_slot_pipeline_imports(
        _REAL_SRC_ROOT, exclude_dirs=[_REAL_PEDAGOGY_DIR]
    )
    assert not hits, (
        "slot_generator/prescreen/review에 새 프로덕션 호출자가 생겼다 — "
        "'프로덕션 호출자 0' 계약이 바뀌었다는 신호다(PED-06 §3 D6 acceptance②):\n"
        + "\n".join(f"  · {h.path}:{h.lineno} — {h.statement}" for h in hits)
    )


# ──────────────────────────────────────────────────────────────────────────
# 결함 주입 변별력 — tmp_path 가짜 미니 레포(양성 대조 + 결함 검출 양쪽 실측)
# ──────────────────────────────────────────────────────────────────────────
def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_fake_repo(root: Path) -> Path:
    """가짜 미니 레포 — `l3/pedagogy/` 패키지 자기 자신(정상) + 외부 소비자 없음(기본 양성 상태).

    `review.py`가 같은 패키지의 `slot_generator`를 import하는 것은 **정상**(같은 패키지
    내부 상호 참조 — 위반 아님). 이 상태가 "무차별 실패기가 아니다"를 보이는 기준점이다.
    """
    _write(
        root / "l3" / "pedagogy" / "__init__.py",
        "from l3.pedagogy import slot_generator, prescreen, review  # 패키지 재-export(정상)\n",
    )
    _write(root / "l3" / "pedagogy" / "slot_generator.py", "def build_slot_rows(): ...\n")
    _write(root / "l3" / "pedagogy" / "prescreen.py", "def prescreen_rows(): ...\n")
    _write(
        root / "l3" / "pedagogy" / "review.py",
        "from l3.pedagogy.slot_generator import build_slot_rows  # 패키지 내부 상호 참조(정상)\n",
    )
    _write(root / "l4" / "__init__.py", "")
    _write(root / "l4" / "unrelated.py", "x = 1  # 파이프라인과 무관한 정상 모듈\n")
    return root


def _pedagogy_dir(root: Path) -> Path:
    return root / "l3" / "pedagogy"


def test_control_fake_repo_with_only_internal_references_passes(tmp_path: Path) -> None:
    """양성 대조 — 패키지 내부 상호 참조만 있는 상태는 위반 0(무차별 실패기가 아님을 증명)."""
    root = _build_fake_repo(tmp_path)
    hits = scan_for_pedagogy_slot_pipeline_imports(root, exclude_dirs=[_pedagogy_dir(root)])
    assert hits == []


def test_defect_from_package_import_outside_pedagogy_is_detected(tmp_path: Path) -> None:
    """결함① — 패키지 밖 파일이 `from l3.pedagogy import slot_generator` 형태로 import하면 검출.

    이것이 이 태스크가 동결하려는 정확한 사고 형태다: 신규 저작 경로가 슬롯 생성기를
    끌어오는 import 1줄이 조용히 추가되는 것.
    """
    root = _build_fake_repo(tmp_path)
    _write(
        root / "l4" / "new_caller.py",
        "from l3.pedagogy import slot_generator  # 결함 — 프로덕션 신규 소비자\n",
    )
    hits = scan_for_pedagogy_slot_pipeline_imports(root, exclude_dirs=[_pedagogy_dir(root)])
    assert len(hits) == 1
    assert hits[0].path == root / "l4" / "new_caller.py"
    assert "slot_generator" in hits[0].statement


def test_defect_from_submodule_import_outside_pedagogy_is_detected(tmp_path: Path) -> None:
    """결함② — `from l3.pedagogy.prescreen import prescreen_rows`(서브모듈 직접 import)도 검출."""
    root = _build_fake_repo(tmp_path)
    _write(
        root / "l4" / "new_caller.py",
        "from l3.pedagogy.prescreen import prescreen_rows  # 결함\n",
    )
    hits = scan_for_pedagogy_slot_pipeline_imports(root, exclude_dirs=[_pedagogy_dir(root)])
    assert len(hits) == 1
    assert "prescreen" in hits[0].statement


def test_defect_bare_import_statement_outside_pedagogy_is_detected(tmp_path: Path) -> None:
    """결함③ — `import l3.pedagogy.review` 완전정규 import 문도 검출."""
    root = _build_fake_repo(tmp_path)
    _write(root / "l4" / "new_caller.py", "import l3.pedagogy.review  # 결함\n")
    hits = scan_for_pedagogy_slot_pipeline_imports(root, exclude_dirs=[_pedagogy_dir(root)])
    assert len(hits) == 1
    assert "review" in hits[0].statement


def test_same_package_shaped_path_import_is_not_flagged(tmp_path: Path) -> None:
    """acceptance②의 핵심 변별 축 — `l3/pedagogy/`-shaped 경로 안의 정상 import는 통과.

    `_build_fake_repo`가 이미 `review.py → slot_generator` 상호 참조를 담고 있으므로, 이
    기준 상태 자체가 "같은 패키지 import는 위반이 아님"의 양성 사례다(위 control 테스트와
    동일 대상을 이 테스트 이름으로 명시해 acceptance② 문구와 1:1 대응시킨다).
    """
    root = _build_fake_repo(tmp_path)
    hits = scan_for_pedagogy_slot_pipeline_imports(root, exclude_dirs=[_pedagogy_dir(root)])
    review_source = (root / "l3" / "pedagogy" / "review.py").read_text(encoding="utf-8")
    assert "slot_generator" in review_source  # 상호 참조가 실제로 존재함(전제 확인)
    assert hits == []  # 그런데도 위반 0 — 제외 디렉터리가 올바르게 작동


def test_syntax_error_file_fails_loudly_not_silently_skipped(tmp_path: Path) -> None:
    """계약 — 파싱 불가 파일은 조용히 건너뛰지 않고 예외로 실패한다(위장 금지)."""
    root = _build_fake_repo(tmp_path)
    _write(root / "l4" / "broken.py", "def broken(:\n    pass\n")

    with pytest.raises(AssertionError, match="파싱 실패"):
        scan_for_pedagogy_slot_pipeline_imports(root, exclude_dirs=[_pedagogy_dir(root)])
