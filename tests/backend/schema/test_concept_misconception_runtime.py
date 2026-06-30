"""정적 가드 — 개념 노드의 자유서술 `common_misconceptions`가 *런타임 경로에서 소비되지 않음*.

math_dsl_risk_register.md Q1/Q8·플레이북 §3.4("노드에 오개념 리스트 내장 금지"). 노드의
`common_misconceptions`(JSONB 자유서술·정답/수정 텍스트)는 *seed 메타*일 뿐이며, 런타임 오개념
프로브/진단은 오개념 *카탈로그*(검증된 kebab-id·`CATALOG_BY_ID`)와 *활성 가설*에서만 나와야 한다
(검증 불가 자유텍스트로 낙인·즉답·날조 차단 — CLAUDE.md 학생 안전 #1·교수학 #3).

`test_scene_generation.py::TestCommonMisconceptionsNotConsumed`가 *행동*(프로브가 그 필드를 안 읽음)
을 동결한다면, 본 테스트는 *소스 정적*으로 한 걸음 더 — 백엔드 어디에서도 `.common_misconceptions`
를 *속성 접근*하는 곳이 L1 seed 적재기 단 한 곳뿐임을 동결한다. 누군가 L4(코칭·진단)·하네스에서
이 필드를 읽기 시작하면 즉시 실패한다(조용한 결합 부채 차단).

hermetic: 외부 의존·DB 불요(소스 파일 텍스트 스캔만).
"""

from __future__ import annotations

import re
from pathlib import Path

import whymath_backend

# 백엔드 패키지 루트(설치 위치 무관·`__file__` 기준).
_PKG_ROOT = Path(whymath_backend.__file__).resolve().parent

# `.common_misconceptions` 속성 *접근*만 잡는다(필드 선언 `common_misconceptions:`·docstring의
# 백틱 언급 `\`common_misconceptions\``은 점(.)이 없어 매칭되지 않는다 — 접근만 거버넌스 대상).
_ATTR_ACCESS = re.compile(r"\.common_misconceptions\b")

# 이 필드에 *정당하게* 속성 접근하는 유일 좌석 — L1 seed 적재기(graph.json → concept 노드 upsert).
# 런타임(L4 코칭·진단)·하네스가 아니라 *적재(ingestion)*다. 이 동결 집합을 늘리려면 "왜 런타임이
# 자유서술 오개념을 읽어야 하는가"를 코드리뷰로 정당화해야 한다(Q1/Q8·낙인 방지).
_ALLOWED_ACCESS_RELPATHS = frozenset(
    {
        "l1/concept_graph/backend_concept.py",
    }
)


def _files_accessing_attr() -> set[str]:
    """`.common_misconceptions` 속성 접근이 있는 `.py`의 패키지 상대경로 집합."""
    hits: set[str] = set()
    for path in _PKG_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _ATTR_ACCESS.search(text):
            hits.add(path.relative_to(_PKG_ROOT).as_posix())
    return hits


def test_common_misconceptions_attr_access_frozen() -> None:
    """`.common_misconceptions` 속성 접근은 L1 seed 적재기 한 곳으로 동결(허용 목록).

    실패 시: 새 접근 파일이 *정당한 seed/적재*면 허용 목록에 추가하고, *런타임 진단/코칭/프로브*면
    제거하라 — 노드 자유서술은 런타임 근거가 아니다(카탈로그·활성 가설이 정본).
    """
    assert _files_accessing_attr() == _ALLOWED_ACCESS_RELPATHS


def test_no_l4_runtime_reads_common_misconceptions() -> None:
    """L4(교수학 런타임·코칭·진단)·하네스 어느 파일도 `.common_misconceptions`를 읽지 않는다.

    낙인·즉답·날조 차단의 핵심 불변 — 자유서술 오개념이 학생 대면 런타임에 절대 흐르지 않게 한다.
    """
    runtime_prefixes = ("l4/", "harness/")
    offenders = {rel for rel in _files_accessing_attr() if rel.startswith(runtime_prefixes)}
    assert offenders == set(), (
        f"L4/하네스 런타임이 노드 자유서술 오개념을 읽음 — {sorted(offenders)}. 런타임 오개념은 "
        "카탈로그(CATALOG_BY_ID)·활성 가설에서만 나와야 한다(Q1/Q8·낙인 금지)."
    )
