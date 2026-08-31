"""콘텐츠 생명주기 상태의 **단일 진실원천** 동결 (EOS-72).

`l3/dsl/models.py`에 `ContentLifecycleState`(idea→…→deprecated 11단계)가 선언돼 있었고
소비처는 0건이었다. EOS-72는 "배선 또는 폐기" 중 **폐기**를 택했다. 이유는 안 쓰여서가 아니라
**정본이 이미 다른 곳에 있어서**다:

  · 노출 판정의 정본 = `schema/enums.py`의 `ReviewStatus`(pending/approved/rejected)와
    값 수준 단일 권위 `is_review_status_cleared`(approved만 True·fail-closed, CONT-01).
    실제 소비처는 `l6/_shared.is_review_cleared` → L6 6모드 gating이다.
    (`problem.is_published`/`publish_at`은 *별개의 게시 축*이고 현재 소비처 0건 — 선언만 있다.
     이 PR 초판이 그것을 검수 축의 소비처로 잘못 적었고, 리뷰 P2 지적으로 정정했다.
     그 dead 선언 자체의 처분은 `ADMIN-12`로 분리 등재했다 — 이 태스크의 범위가 아니다.)
  · 버전 생명주기의 정본 = `docs/architecture/44_eos_version_management.md` §7
    (DRAFT→IN_REVIEW→APPROVED→PUBLISHED→DEPRECATED→RETIRED · PUBLISHED→DRAFT 금지, EOS-44 확정).

11단계를 배선했다면 같은 대상에 상태 머신이 둘 생긴다 — 단계 수도, 이름도, 전이도 다르다.

이 파일이 동결하는 것:
  ① 그 심볼이 되살아나지 않는다(정의·재export 둘 다).
  ② **일반화 가드** — `l3/dsl` 어디에도 *출판 거버넌스 어휘*를 멤버로 갖는 Enum이 없다.
     ①만으로는 이름만 바꿔 되살리면 통과한다. 재발은 대개 같은 이름으로 오지 않는다.
  ③ 정본이 실제로 그 자리에 있다 — `ReviewStatus` 3값 + fail-closed 판정.
  ④ 폐기 판단의 전제(EOS-44 §7 상태 머신)가 문서에 살아 있다. 그 전제가 바뀌면 이 결정도
     재검토 대상이므로, 전제가 사라지는 것을 침묵으로 넘기지 않는다.

한계(명시): ②는 `l3/dsl` 패키지 안만 본다. 다른 계층이 자기 생명주기 enum을 갖는 것까지
막지는 않는다 — 그건 이 태스크의 범위가 아니고, 실제로 `ReviewStatus`·`AchievementStandard`
lifecycle처럼 축이 다른 정당한 enum이 존재한다.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from whymath_backend.schema.enums import ReviewStatus, is_review_status_cleared

_DSL_DIR = (
    Path(__file__).resolve().parents[4] / "src" / "backend" / "whymath_backend" / "l3" / "dsl"
)
_CANONICAL_DOC = (
    Path(__file__).resolve().parents[4] / "docs" / "architecture" / "44_eos_version_management.md"
)

# 출판 거버넌스 어휘 — 이 값들을 멤버로 갖는 enum은 "무엇을 노출할지"를 정하는 상태 머신이다.
# 컴파일러 단계(parsed·validated·verified)는 일부러 뺐다: 그건 처리 순서지 거버넌스가 아니고,
# 넣으면 정당한 파이프라인 enum까지 잡는 거짓 양성이 된다.
_GOVERNANCE_VOCAB = frozenset({"published", "deprecated", "retired", "approved", "in_review"})


def _dsl_sources() -> list[Path]:
    """패키지 *전체*를 재귀로 훑는다 — `glob("*.py")`는 최상위만 봐서 `l3/dsl/publishing/models.py`
    같은 평범한 서브패키지 분리만으로 가드가 조용히 우회된다(PR #935 리뷰 P2 지적)."""
    files = sorted(p for p in _DSL_DIR.rglob("*.py") if "__pycache__" not in p.parts)
    assert files, f"l3/dsl 소스를 찾지 못했습니다: {_DSL_DIR}"
    return files


def _enum_members(path: Path) -> list[tuple[str, list[str]]]:
    """파일 안 Enum 클래스를 (클래스명, 멤버 문자열값 목록)으로 뽑는다(AST — import 불요)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
        bases |= {b.attr for b in node.bases if isinstance(b, ast.Attribute)}
        if "Enum" not in bases and "StrEnum" not in bases:
            continue
        values: list[str] = []
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    values.append(stmt.value.value)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.value, ast.Constant):
                if isinstance(stmt.value.value, str):
                    values.append(stmt.value.value)
        found.append((node.name, values))
    return found


# ===========================================================================
# ① 그 심볼이 되살아나지 않는다
# ===========================================================================


def test_content_lifecycle_state_is_not_importable() -> None:
    """패키지에서도 모듈에서도 노출되지 않는다(재export만 지우고 정의를 남기는 실수 차단)."""
    import whymath_backend.l3.dsl as dsl
    import whymath_backend.l3.dsl.models as models

    assert not hasattr(dsl, "ContentLifecycleState")
    assert not hasattr(models, "ContentLifecycleState")
    assert "ContentLifecycleState" not in getattr(dsl, "__all__", [])
    assert "ContentLifecycleState" not in getattr(models, "__all__", [])


def test_content_lifecycle_state_class_is_gone_from_sources() -> None:
    """정의 자체가 없다 — `__all__`에서만 빼고 클래스를 남기면 여기서 실패한다."""
    for path in _dsl_sources():
        names = [name for name, _values in _enum_members(path)]
        assert "ContentLifecycleState" not in names, f"{path.name}에 정의가 되살아났습니다"


# ===========================================================================
# ② 일반화 가드 — 이름을 바꿔도 잡는다
# ===========================================================================


def test_no_publication_governance_enum_in_dsl_package() -> None:
    """`l3/dsl`에 출판 거버넌스 상태 머신을 두지 않는다(이름 무관).

    ①은 옛 이름만 막는다. 재발은 `ContentState`·`PublishState` 같은 새 이름으로 오기 쉬우므로,
    *무엇을 노출할지 정하는 어휘*를 가진 enum 자체를 이 패키지에서 금지한다. 그런 판정이
    필요하면 `schema/enums.ReviewStatus`를 쓴다(단일 진실원천).
    """
    offenders: list[str] = []
    for path in _dsl_sources():
        for name, values in _enum_members(path):
            hits = _GOVERNANCE_VOCAB.intersection(v.lower() for v in values)
            if hits:
                offenders.append(f"{path.name}::{name} → {sorted(hits)}")
    assert not offenders, (
        "l3/dsl에 출판 거버넌스 enum이 생겼습니다 — 노출 판정의 정본은 "
        f"schema/enums.ReviewStatus입니다: {offenders}"
    )


# ===========================================================================
# ③ 정본이 실제로 그 자리에 있다
# ===========================================================================


def test_review_status_is_the_single_source() -> None:
    assert {s.value for s in ReviewStatus} == {"pending", "approved", "rejected"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (ReviewStatus.approved, True),
        (ReviewStatus.pending, False),
        (ReviewStatus.rejected, False),
        ("approved", True),
        ("pending", False),
        (None, False),
        ("published", False),
    ],
)
def test_review_gate_is_fail_closed(value: object, expected: bool) -> None:
    """approved만 통과 — 특히 `None`과 옛 어휘(`published`)가 열리지 않는다."""
    assert is_review_status_cleared(value) is expected  # type: ignore[arg-type]


# ===========================================================================
# ④ 폐기 판단의 전제가 살아 있다
# ===========================================================================


def test_canonical_version_lifecycle_doc_still_defines_the_state_machine() -> None:
    """EOS-44 §7이 정본 상태 머신을 갖고 있다 — 이 전제 위에서 11단계를 폐기했다.

    문서가 바뀌어 상태 머신이 사라지면 폐기 결정의 근거도 사라지므로, 조용히 지나가지 않는다.
    """
    assert _CANONICAL_DOC.is_file(), f"정본 문서 부재: {_CANONICAL_DOC}"
    text = _CANONICAL_DOC.read_text(encoding="utf-8")
    for state in ("DRAFT", "IN_REVIEW", "APPROVED", "PUBLISHED", "DEPRECATED", "RETIRED"):
        assert state in text, f"정본 문서에서 상태 {state}가 사라졌습니다"
    assert "PUBLISHED → DRAFT 금지" in text, "불가역 전이 규칙이 정본 문서에서 사라졌습니다"
