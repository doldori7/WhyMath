"""L1 적재 모듈의 *콜드 임포트* 회귀 가드 — 순환 임포트 재발 방지.

`concept_graph/embedding.py`가 L4(`pgvector_index`)를 *모듈 최상단*에서 import하면
`embedding(L1) → l4 → l2 → l1.node_projection → embedding._build_sync_engine(미정의)` 순환이
생겨, 신선한 인터프리터에서 적재 모듈을 import할 때(예: `python -m ...populate` CLI 콜드런)
ImportError가 난다. 이 순환은 *pytest 하네스 안에서는 안 잡힌다* — 다른 테스트가 먼저 embedding을
import해 sys.modules에 캐시해 두기 때문이다(웜 상태). 따라서 이 가드는 **별도 서브프로세스**(fresh
interpreter)로 import를 돌려 콜드 경로를 직접 검증한다(embedding의 L4 import가 지연으로 유지되는지
회귀 감시 — 재발 시 import가 0이 아닌 코드로 실패).
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# 콜드 import가 성공해야 하는 L1 적재 진입점들. embedding은 순환의 진앙, 나머지는 그를 경유해
# `_build_sync_engine`을 끌어오는 적재기/패키지(콜드런 시 동일 순환에 걸렸던 대상들).
_COLD_IMPORT_TARGETS: tuple[str, ...] = (
    "whymath_backend.l1.concept_graph.embedding",
    "whymath_backend.l1.concept_graph.node_projection",
    "whymath_backend.l1.curriculum",
    "whymath_backend.l1.curriculum.populate",
    "whymath_backend.l1.standards",
    "whymath_backend.l1.standards.populate",
)


@pytest.mark.parametrize("module", _COLD_IMPORT_TARGETS)
def test_module_imports_cold_without_cycle(module: str) -> None:
    """신선한 인터프리터에서 `import <module>`이 순환 없이 성공한다(returncode 0).

    같은 프로세스가 아니라 `sys.executable -c "import ..."` 서브프로세스로 돌려 *콜드* 경로를
    검증한다 — 웜 캐시가 가리던 순환을 드러낸다. 실패 시 stderr(ImportError 트레이스)를 그대로
    노출해 진단을 돕는다(조용한 실패 금지).
    """
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"콜드 import 실패(순환 의심): {module}\n" f"--- stderr ---\n{result.stderr}"
    )
