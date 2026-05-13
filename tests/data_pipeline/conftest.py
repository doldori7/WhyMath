"""tests/data_pipeline/conftest.py — 테스트 모듈 임포트 전에 sys.path 조정.

pytest는 conftest.py를 *해당 디렉토리의 테스트 모듈*보다 먼저 import한다.
이 파일은 `data_pipeline` 동명 디렉토리(tests/data_pipeline 자체)와
실제 소스 패키지(src/data-pipeline/data_pipeline) 충돌을 회피하기 위해
sys.path 우선순위를 명시적으로 설정.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_DATA_PIPELINE = _PROJECT_ROOT / "src" / "data-pipeline"

# 동명 충돌 회피: 소스 경로를 가장 앞으로
src_path_str = str(_SRC_DATA_PIPELINE)
if src_path_str in sys.path:
    sys.path.remove(src_path_str)
sys.path.insert(0, src_path_str)

# 이미 잘못 import된 data_pipeline 모듈이 있다면 강제로 비우고 재import 가능 상태
_to_purge = [m for m in list(sys.modules.keys()) if m == "data_pipeline" or m.startswith("data_pipeline.")]
for m in _to_purge:
    mod = sys.modules.get(m)
    # 실제 소스 위치가 아닌 경우만 purge (안전장치)
    if mod is not None and getattr(mod, "__file__", "") and not str(mod.__file__).startswith(str(_SRC_DATA_PIPELINE)):
        del sys.modules[m]
