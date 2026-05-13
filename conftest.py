"""프로젝트 루트 conftest.

목적:
  - pytest가 *어디서 실행되든* `data_pipeline` 등 소스 패키지를 import 가능하게.
  - 테스트 디렉토리(tests/data_pipeline)와 소스 패키지(src/data-pipeline/data_pipeline)의
    이름 충돌을 sys.path 우선순위로 회피.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.resolve()
_SRC_DATA_PIPELINE = _PROJECT_ROOT / "src" / "data-pipeline"

# 소스 패키지 경로를 sys.path 가장 앞에 두어 동명 디렉토리 충돌 회피
if str(_SRC_DATA_PIPELINE) not in sys.path:
    sys.path.insert(0, str(_SRC_DATA_PIPELINE))
