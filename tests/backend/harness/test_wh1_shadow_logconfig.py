"""wh1_shadow_logconfig.json 회귀 동결 — ASCII 불변·cp949 안전·dictConfig 로드·캡처·상태 원복.

2026-07-17 라이브 사고의 재발 방지: uvicorn은 `--log-config` JSON을 **OS 로케일 인코딩**
(한국어 Windows=cp949)으로 읽는다 — 파일에 비ASCII 바이트가 하나라도 있으면 Kiki 머신에서
`UnicodeDecodeError`로 서버 기동 자체가 실패한다(실측). 이 테스트가 ASCII 불변을 동결해
한국어 주석이 다시 들어가는 회귀를 CI에서 잡는다.

2026-07-29 OPS-15 사고의 재발 방지: 이 파일의 dictConfig 테스트가 record 로거에
`propagate=False`를 남겼다(구 finally가 *핸들러만* 복원). pytest 8.x caplog은 캡처 핸들러를
root 로거에만 달아 전파에 의존하므로, 무작위 순서에서 이 테스트가 먼저 돌면 이후 WH-1
caplog 단언 테스트 13건(primary 5·shadow 7·mode_guard 1)이 "관측 레코드 0건"으로 깨졌다
(재현 시드 442243680). 이제 `_dictconfig_loaded`가 설정이 건드리는 로거 전부를 스냅샷→원복
하고, 그 원복 계약을 `test_logconfig_load_restores_logger_state`가 동결한다.
"""

from __future__ import annotations

import json
import logging
import logging.config
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOGCONFIG = _REPO_ROOT / "scripts" / "demo" / "wh1_shadow_logconfig.json"

# 수확기가 파싱 대상으로 삼는 로거 — wh1_shadow.record_logger와 동일해야 캡처가 성립.
_RECORD_LOGGER = "whymath.harness.wh1_shadow.record"

# 로거 1개의 원복 대상 상태: (level, propagate, disabled, handlers 리스트).
_LoggerState = tuple[int, bool, bool, list[logging.Handler]]


def _capture_states(names: list[str]) -> dict[str, _LoggerState]:
    """이름별 로거의 (level·propagate·disabled·handlers) 스냅샷."""
    states: dict[str, _LoggerState] = {}
    for name in names:
        lg = logging.getLogger(name)
        states[name] = (lg.level, lg.propagate, lg.disabled, list(lg.handlers))
    return states


@contextmanager
def _dictconfig_loaded(config: dict[str, object]) -> Iterator[None]:
    """dictConfig를 적용하고, 나갈 때 설정이 건드린 로거 상태를 *전부* 원복한다(OPS-15).

    구 정리는 record 로거의 핸들러만 제거해 `propagate=False`(+레벨·uvicorn 핸들러)를
    프로세스에 남겼다 — 같은 프로세스의 후속 caplog 테스트를 순서 의존으로 죽이는 오염.
    설정의 `loggers` 키에서 대상 로거를 파생하므로(하드코딩 0) JSON에 로거가 추가돼도
    자동으로 원복 범위에 든다. dictConfig가 새로 단 핸들러는 닫고(FileHandler 파일 반납),
    스냅샷의 level·propagate·disabled·기존 핸들러 리스트를 되돌린다.
    """
    loggers_section = config.get("loggers", {})
    assert isinstance(loggers_section, dict)
    saved = _capture_states([str(name) for name in loggers_section])
    logging.config.dictConfig(config)
    try:
        yield
    finally:
        for name, (level, propagate, disabled, handlers) in saved.items():
            lg = logging.getLogger(name)
            for handler in list(lg.handlers):
                if handler not in handlers:  # dictConfig가 새로 단 핸들러만 닫는다
                    lg.removeHandler(handler)
                    handler.close()
            for handler in handlers:  # 스냅샷에 있었는데 빠진 핸들러 복귀(방어적)
                if handler not in lg.handlers:
                    lg.addHandler(handler)
            lg.setLevel(level)
            lg.propagate = propagate
            lg.disabled = disabled


def _load_config(tmp_path: Path) -> dict[str, object]:
    """logconfig JSON을 읽고 캡처 파일만 tmp로 돌린 설정 dict."""
    config = json.loads(_LOGCONFIG.read_text(encoding="ascii"))
    assert isinstance(config, dict)
    handlers = config["handlers"]
    assert isinstance(handlers, dict)
    handlers["wh1_record_file"]["filename"] = str(tmp_path / "records.log")
    return config


def test_logconfig_is_ascii_only() -> None:
    """비ASCII 바이트 0 — cp949(한국어 Windows 로케일)로도 안전하게 디코드된다."""
    data = _LOGCONFIG.read_bytes()
    data.decode("ascii")  # 비ASCII가 있으면 UnicodeDecodeError로 실패
    data.decode("cp949")  # 사고 당시 실패 지점의 직접 재현 검사


def test_logconfig_captures_record_logger(tmp_path: Path) -> None:
    """dictConfig 로드 + record 로거 라인이 순수 메시지로 파일 캡처된다(e2e)."""
    config = _load_config(tmp_path)
    with _dictconfig_loaded(config):
        logging.getLogger(_RECORD_LOGGER).info('{"probe": "e2e"}')
        for handler in logging.getLogger(_RECORD_LOGGER).handlers:
            handler.flush()
        out = tmp_path / "records.log"
        assert out.read_text(encoding="utf-8").strip() == '{"probe": "e2e"}'


def test_logconfig_load_restores_logger_state(tmp_path: Path) -> None:
    """로드 컨텍스트가 나가며 로거 상태(propagate·레벨·핸들러·disabled)를 원복한다(OPS-15).

    사고 동결: 구 정리는 핸들러만 복원하고 `propagate=False`를 남겨, root 전파에 의존하는
    pytest 8.x caplog의 WH-1 테스트 13건이 무작위 순서에서 0건 관측으로 깨졌다(시드
    442243680 실측). 설정이 건드리는 로거 *전부*의 사전/사후 상태 동일성을 직접 단언한다.
    컨텍스트 안에서 propagate=False 적용을 먼저 확인해(변별력) '원래부터 아무 일도 없었다'
    는 위장 통과를 배제한다.
    """
    config = _load_config(tmp_path)
    loggers_section = config["loggers"]
    assert isinstance(loggers_section, dict)
    names = [str(name) for name in loggers_section]
    assert _RECORD_LOGGER in names  # 사고 로거가 원복 범위에 실제로 든다

    before = _capture_states(names)
    with _dictconfig_loaded(config):
        # 설정이 실제로 적용됐다 — 오염이 일어난 바로 그 상태(비전파)를 확인(변별력).
        assert logging.getLogger(_RECORD_LOGGER).propagate is False
        assert logging.getLogger(_RECORD_LOGGER).handlers != []
    after = _capture_states(names)

    assert after == before  # propagate·level·disabled·handlers 전부 원상 복귀


def test_logconfig_targets_real_record_logger_name() -> None:
    """설정의 로거 이름이 실물 wh1_shadow record 로거와 일치(재타이핑 드리프트 차단)."""
    from whymath_backend.harness import wh1_shadow

    config = json.loads(_LOGCONFIG.read_text(encoding="ascii"))
    assert _RECORD_LOGGER in config["loggers"]
    assert wh1_shadow.record_logger.name == _RECORD_LOGGER
