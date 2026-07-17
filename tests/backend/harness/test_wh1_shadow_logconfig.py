"""wh1_shadow_logconfig.json 회귀 동결 — ASCII 불변·cp949 안전·dictConfig 로드·캡처.

2026-07-17 라이브 사고의 재발 방지: uvicorn은 `--log-config` JSON을 **OS 로케일 인코딩**
(한국어 Windows=cp949)으로 읽는다 — 파일에 비ASCII 바이트가 하나라도 있으면 Kiki 머신에서
`UnicodeDecodeError`로 서버 기동 자체가 실패한다(실측). 이 테스트가 ASCII 불변을 동결해
한국어 주석이 다시 들어가는 회귀를 CI에서 잡는다.
"""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOGCONFIG = _REPO_ROOT / "scripts" / "demo" / "wh1_shadow_logconfig.json"

# 수확기가 파싱 대상으로 삼는 로거 — wh1_shadow.record_logger와 동일해야 캡처가 성립.
_RECORD_LOGGER = "whymath.harness.wh1_shadow.record"


def test_logconfig_is_ascii_only() -> None:
    """비ASCII 바이트 0 — cp949(한국어 Windows 로케일)로도 안전하게 디코드된다."""
    data = _LOGCONFIG.read_bytes()
    data.decode("ascii")  # 비ASCII가 있으면 UnicodeDecodeError로 실패
    data.decode("cp949")  # 사고 당시 실패 지점의 직접 재현 검사


def test_logconfig_captures_record_logger(tmp_path: Path) -> None:
    """dictConfig 로드 + record 로거 라인이 순수 메시지로 파일 캡처된다(e2e)."""
    config = json.loads(_LOGCONFIG.read_text(encoding="ascii"))
    out = tmp_path / "records.log"
    config["handlers"]["wh1_record_file"]["filename"] = str(out)
    logging.config.dictConfig(config)
    try:
        logging.getLogger(_RECORD_LOGGER).info('{"probe": "e2e"}')
        for handler in logging.getLogger(_RECORD_LOGGER).handlers:
            handler.flush()
        assert out.read_text(encoding="utf-8").strip() == '{"probe": "e2e"}'
    finally:
        # 전역 로깅 상태 복원 — 다른 테스트의 로거 구성 오염 방지.
        for handler in list(logging.getLogger(_RECORD_LOGGER).handlers):
            logging.getLogger(_RECORD_LOGGER).removeHandler(handler)
            handler.close()


def test_logconfig_targets_real_record_logger_name() -> None:
    """설정의 로거 이름이 실물 wh1_shadow record 로거와 일치(재타이핑 드리프트 차단)."""
    from whymath_backend.harness import wh1_shadow

    config = json.loads(_LOGCONFIG.read_text(encoding="ascii"))
    assert _RECORD_LOGGER in config["loggers"]
    assert wh1_shadow.record_logger.name == _RECORD_LOGGER
