"""로거 상태 오염 가드 — 탐지·격리 로직 (OPS-15).

`tests/backend/conftest.py`의 autouse 픽스처 `_guard_logging_state_pollution`이 이 모듈을
소비한다. 로직을 모듈로 분리한 이유는 OPS-07(`_db_leak_guard`)과 동일 — **가드 자체의
변별력**을 별도 테스트(`test_logging_state_guard.py`)에서 오염 주입으로 직접 실측하기
위해서다(오염 주입 → 실제 실패 신호 확인).

배경 사고(2026-07-29 OPS-15): `test_wh1_shadow_logconfig.py`의 dictConfig 테스트가
`whymath.harness.wh1_shadow.record` 로거에 `propagate=False`를 남겼다(구 finally가 핸들러만
복원하고 propagate는 놓침). pytest 8.x의 caplog은 캡처 핸들러를 **root 로거에만** 달아
전파에 의존하므로, 전파가 꺼진 로거의 레코드는 caplog에 0건으로 관측된다 — 무작위 순서에서
그 테스트가 WH-1 caplog 단언 테스트들(13건: primary 5·shadow 7·mode_guard 1)보다 먼저
실행될 때만 터지는 순서 플레이크였다(재현 시드 442243680 실측). pytest 9.0+는 caplog이
비전파 로거에도 핸들러를 직접 달아 같은 오염이 *증상 없이* 지나간다 — 러너 버전에 따라
위장되는 오염이라, 이 가드가 오염을 남긴 테스트 자체를 결정론적 실패로 바꾼다(귀책) 후
상태를 되돌린다(격리). OPS-07(원인 지목)·OPS-09(무작위 순서로 존재 발견)와 상보다.

감시 범위(의도적 한정 — 오검출 0 우선):
  ① 테스트 시작 시점에 존재하던 로거의 `propagate` 플립
  ② 같은 로거들의 `disabled` 플립
  ③ 전역 `logging.disable()` 레벨(manager.disable) 변경
  ④ 테스트 중 *생성된* `whymath*` 네임스페이스 로거가 propagate=False/disabled=True로 잔존
이들이 caplog 캡처를 구조적으로 죽이는 상태다. 레벨·핸들러·필터 잔존은 감시하지 않는다
— 레벨은 caplog.at_level/set_level이 명시 재설정해 이 시그니처를 못 만들고, 핸들러는
pytest 로깅 플러그인 자신이 페이즈마다 착탈해 스냅샷 비교가 오검출을 낳는다. 테스트 중
새로 생긴 *외부* 로거는 제외한다 — 라이브러리가 import 시점에 비전파 로거를 만드는 것은
정상 설계다. 단 ④처럼 우리 네임스페이스(`whymath`/`whymath_backend`)는 앱·테스트 어디도
비전파 로거를 정당하게 만들지 않음을 실측 grep으로 확인했으므로(소스 전체 propagate 조작
0건), 신생이라도 판정한다 — 격리 실행(단독 파일)에서는 오염 로거가 dictConfig로 테스트 중
생성돼 스냅샷에 없기 때문에, 이 항이 없으면 원본 사고 코드를 단독 실행에서 놓친다(실측).
"""

from __future__ import annotations

import logging
from typing import NamedTuple

# 오염 실패 메시지의 고정 접두 — 테스트가 이 마커로 실패 신호를 판별한다(변별력 grep).
LOGGING_LEAK_MARKER: str = "[logging 상태 오염]"

# 신생 로거까지 판정하는 우리 네임스페이스 접두 — "whymath.…"(명시 로거명)와
# "whymath_backend.…"(`getLogger(__name__)`) 둘 다 startswith("whymath")로 덮는다.
_OWNED_LOGGER_PREFIX: str = "whymath"


class LoggingStateSnapshot(NamedTuple):
    """테스트 시작 시점의 로깅 전역 상태 — 종료 시 비교·복원의 기준."""

    global_disable: int  # logging.disable() 레벨 (logging.root.manager.disable)
    loggers: dict[str, tuple[bool, bool]]  # 로거명 → (propagate, disabled)


def snapshot_logging_state() -> LoggingStateSnapshot:
    """현존 로거들의 (propagate·disabled)와 전역 disable 레벨을 스냅샷한다.

    `loggerDict`에는 실제 Logger 외에 PlaceHolder(자식만 만들어진 조상 자리)도 있어
    isinstance로 거른다. root 로거는 loggerDict에 없으므로 **빈 문자열 키**로 별도 포함한다
    — `logging.getLogger("")`는 진짜 root를 돌려주지만 `getLogger("root")`는 'root'라는
    *이름의 새 로거를 만들어 버리므로*(표준 라이브러리 함정) root.name("root")을 키로 쓰면
    비교·복원이 엉뚱한 로거를 향한다. 빈 키는 loggerDict에 등장할 수 없어 충돌도 없다.
    (propagate는 root에 의미 없지만 disabled는 유효 — 전 로깅을 죽이는 상태.)
    """
    manager = logging.Logger.manager
    loggers: dict[str, tuple[bool, bool]] = {
        name: (lg.propagate, lg.disabled)
        for name, lg in manager.loggerDict.items()
        if isinstance(lg, logging.Logger)
    }
    root = logging.getLogger()
    loggers[""] = (root.propagate, root.disabled)
    return LoggingStateSnapshot(global_disable=manager.disable, loggers=loggers)


def _new_owned_offenders(snapshot: LoggingStateSnapshot) -> list[logging.Logger]:
    """테스트 중 생성된 whymath* 로거 중 비전파/비활성으로 남은 것들(감시 범위 ④)."""
    manager = logging.Logger.manager
    offenders: list[logging.Logger] = []
    for name, lg in manager.loggerDict.items():
        if not isinstance(lg, logging.Logger) or name in snapshot.loggers:
            continue
        if name.startswith(_OWNED_LOGGER_PREFIX) and (not lg.propagate or lg.disabled):
            offenders.append(lg)
    return offenders


def logging_state_leak_reason(snapshot: LoggingStateSnapshot) -> str | None:
    """스냅샷 대비 오염이 있으면 사유 문자열, 깨끗하면 None.

    기존 로거는 스냅샷과의 *변화*를 비교하고, 테스트 중 생성된 로거는 whymath* 네임스페이스
    한정으로 비전파/비활성 잔존을 판정한다 — 외부 라이브러리의 신생 비전파 로거는 정상
    설계일 수 있어 제외한다(오검출 방지·모듈 docstring 감시 범위 참조).
    """
    changed: list[str] = []
    manager = logging.Logger.manager
    if manager.disable != snapshot.global_disable:
        changed.append(f"전역 logging.disable {snapshot.global_disable}→{manager.disable}")
    for name, (propagate, disabled) in snapshot.loggers.items():
        lg = logging.getLogger(name)  # 빈 키("")는 진짜 root로 해석된다(스냅샷 규약)
        label = name or "root"
        if lg.propagate != propagate:
            changed.append(f"로거 '{label}' propagate {propagate}→{lg.propagate}")
        if lg.disabled != disabled:
            changed.append(f"로거 '{label}' disabled {disabled}→{lg.disabled}")
    for lg in _new_owned_offenders(snapshot):
        state = f"propagate={lg.propagate}, disabled={lg.disabled}"
        changed.append(f"테스트 중 생성된 whymath 로거 '{lg.name}' 가 {state} 로 잔존")
    if not changed:
        return None
    return ", ".join(changed)


def contain_logging_state_leak(snapshot: LoggingStateSnapshot) -> None:
    """오염된 상태를 스냅샷 값으로 되돌려 다음 테스트를 격리한다(귀책과 격리의 분리).

    신생 whymath* 오염 로거는 스냅샷에 기준값이 없으므로 기본값(propagate=True·
    disabled=False)으로 되돌린다 — 우리 네임스페이스의 정상 초기 상태다.
    """
    manager = logging.Logger.manager
    for lg in _new_owned_offenders(snapshot):  # 스냅샷 복원 전에 신생 오염부터 기본값으로
        lg.propagate = True
        lg.disabled = False
    manager.disable = snapshot.global_disable
    for name, (propagate, disabled) in snapshot.loggers.items():
        lg = logging.getLogger(name)  # 빈 키("")는 진짜 root로 해석된다(스냅샷 규약)
        lg.propagate = propagate
        lg.disabled = disabled


def format_logging_leak_failure(nodeid: str, reason: str) -> str:
    """오염 테스트에 붙일 실패 메시지 — 귀책 대상(nodeid)·정리 방법을 함께 안내한다."""
    return (
        f"{LOGGING_LEAK_MARKER} 테스트 '{nodeid}' 가 로거 전역 상태를 바꾸고 되돌리지 "
        f"않았다 — {reason}. propagate=False·disabled=True·logging.disable 잔존은 pytest "
        "8.x caplog(캡처 핸들러가 root 전용·전파 의존)을 조용히 죽여, 무작위 순서에서만 "
        "후속 caplog 테스트가 '관측 0건'으로 깨진다(OPS-15 — WH-1 13건·시드 442243680 "
        "실측. pytest 9+는 같은 오염을 위장하므로 러너 버전에 따라 안 보일 수 있다). "
        "dictConfig·propagate·disable을 만졌으면 try/finally 또는 fixture에서 이전 값을 "
        "복원하라(harness/test_wh1_shadow_logconfig.py::_dictconfig_loaded 선례)."
    )
