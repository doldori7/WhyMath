"""backup_whymath_pg.ps1 계약 동결 테스트 (hermetic — docker·실 DB 불요).

OPS-02-db-backup-dr: prod DB(docker `whymath-pg`, 호스트 5433) pg_dump 백업
스크립트의 핵심 안전 계약을 파일 텍스트 수준에서 동결한다:
  ① **ASCII 전용** — PowerShell 5.1은 .ps1을 OS 로케일 인코딩(한국어 Windows=cp949)으로
     읽는다. 비ASCII 1바이트가 Kiki 머신에서 스크립트를 깨뜨린다
     (2026-07-17 logconfig UnicodeDecodeError 실측 — `test_wh1_shadow_logconfig.py` 동형).
  ② **pg_restore --list 자가검증** — 호스트 회수(docker cp) *전* 컨테이너 안에서 덤프
     카탈로그 판독. 손상/절단 덤프에서 비0 종료로 실패 신호를 내는 *변별력 있는* 검사.
  ③ **-RetentionDays 보존 정책** — 파라미터 존재 + 기본 14일.
  ④ **대상 = prod whymath-pg** — 기본 컨테이너가 demo-db가 아니고,
     whymath-demo-db 지정 시 명시 거부(guard)한다.
  ⑤ **최소 1개 보존** — 만료 삭제가 최신 백업을 절대 지우지 못함(`Select-Object -Skip 1`).
  ⑥ **exit 1 실패 경로 / exit 0 성공 경로** — 에러를 삼키지 않는다.

스크립트 실행 자체(docker)는 hermetic 범위 밖 — 실행 검증은 런북
`docs/architecture/db_backup_dr_runbook.md`의 자가검증 스텝이 담당한다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup" / "backup_whymath_pg.ps1"


def _text() -> str:
    """ASCII로 읽는다 — ①이 깨지면 여기서도 즉시 실패(이중 방어)."""
    return _SCRIPT.read_text(encoding="ascii")


def test_script_exists() -> None:
    """스크립트 파일 존재 — 경로 이동/개명 시 계약 테스트가 유령이 되는 것 방지."""
    assert _SCRIPT.is_file(), f"백업 스크립트 부재: {_SCRIPT}"


def test_script_is_ascii_only() -> None:
    """① 비ASCII 바이트 0 — cp949(한국어 Windows 로케일)로도 안전하게 디코드된다."""
    data = _SCRIPT.read_bytes()
    try:
        data.decode("ascii")
    except UnicodeDecodeError as exc:
        pytest.fail(
            "backup_whymath_pg.ps1에 비ASCII 바이트 존재 "
            f"(offset {exc.start}: {data[exc.start:exc.start + 8]!r}) — "
            "PowerShell 5.1이 cp949로 읽다 깨진다(2026-07-17 선례). "
            "한국어 설명은 스크립트가 아니라 런북(db_backup_dr_runbook.md)에 둔다."
        )
    data.decode("cp949")  # 사고 당시 실패 지점의 직접 재현 검사


def test_pg_restore_list_selfcheck_before_copy() -> None:
    """② 회수 전 카탈로그 판독 — pg_restore --list가 docker cp보다 *앞에* 있다."""
    text = _text()
    assert "pg_restore --list" in text, "덤프 정합 자가검증(pg_restore --list) 단계가 사라짐"
    assert text.index("pg_restore --list") < text.index("docker cp"), (
        "pg_restore --list 검증이 docker cp(호스트 회수)보다 뒤로 밀림 — "
        "손상 덤프가 호스트에 회수된 뒤에야 발견되는 구조는 계약 위반"
    )


def test_retention_parameter_with_default_14() -> None:
    """③ -RetentionDays 파라미터 존재 + 기본값 14일."""
    text = _text()
    assert "$RetentionDays" in text, "-RetentionDays 보존 정책 파라미터가 사라짐"
    assert re.search(r"\$RetentionDays\s*=\s*14", text), "RetentionDays 기본값 14가 변경/삭제됨"


def test_targets_prod_container_not_demo() -> None:
    """④ 기본 대상 = whymath-pg(prod), whymath-demo-db는 명시 거부 가드로만 등장."""
    text = _text()
    assert re.search(
        r'\$ContainerName\s*=\s*"whymath-pg"', text
    ), "기본 컨테이너가 prod whymath-pg가 아님 — 시연용 demo-db(55432·일회용)와 혼동 금지"
    assert re.search(
        r'-eq\s+"whymath-demo-db"', text
    ), "whymath-demo-db 명시 거부 가드가 사라짐 — 일회용 DB를 prod 백업 대상으로 오인 가능"


def test_min_one_backup_always_kept() -> None:
    """⑤ 최소 1개 보존 — 최신 파일을 만료 대상에서 제외(Select-Object -Skip 1)."""
    text = _text()
    assert "Select-Object -Skip 1" in text, (
        "최소 1개 보존 로직(Select-Object -Skip 1)이 사라짐 — "
        "RetentionDays보다 오래 백업이 안 돌면 보존분 전멸 가능"
    )


def test_exit_paths_present() -> None:
    """⑥ exit 1 실패 경로 + exit 0 성공 경로 — 침묵 실패 금지."""
    text = _text()
    assert "exit 1" in text, "실패 exit 1 경로가 사라짐 — 스케줄러가 실패를 감지 못함"
    assert "exit 0" in text, "성공 exit 0 경로가 사라짐"


def test_dump_command_frozen() -> None:
    """pg_dump 대상·형식 동결 — user/db=whymath, custom format(-Fc)."""
    text = _text()
    assert "pg_dump -U whymath -d whymath -Fc" in text, (
        "pg_dump 명령 계약(-U whymath -d whymath -Fc) 변경 — "
        "런북의 복구 절차(pg_restore custom format)와 짝이 맞아야 한다"
    )
