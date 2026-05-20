"""tests/backend/conftest.py — 백엔드 테스트 임포트 경로 보장.

`whymath_backend`는 `pip install -e ".[dev]"`로 editable 설치되므로 보통은
import 경로 조정이 불필요하다. 다만 editable 설치 없이(예: 로컬에서 venv 미설치)
테스트를 돌릴 때도 동작하도록 소스 경로를 sys.path 앞에 둔다.

data-pipeline(tests/data_pipeline/conftest.py)과 달리 *동명 충돌이 없다*:
테스트 디렉토리는 `tests/backend`, 패키지는 `whymath_backend`로 이름이 다르다.
따라서 모듈 purge 로직은 불필요하고, 경로 보장만 한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC_BACKEND = _PROJECT_ROOT / "src" / "backend"

# editable 설치가 없을 때를 대비한 안전장치: 소스 경로를 가장 앞으로
_src_path_str = str(_SRC_BACKEND)
if _src_path_str in sys.path:
    sys.path.remove(_src_path_str)
sys.path.insert(0, _src_path_str)
