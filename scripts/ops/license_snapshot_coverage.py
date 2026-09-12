#!/usr/bin/env python3
"""라이선스 약관 스냅샷 커버리지 판정 — 게이트 clear의 기계 기준 (LIC-02 집행 축).

왜 이 스크립트가 있는가 (2026-08-30 · PR #915 리뷰 P1 수용)
----------------------------------------------------------
아카이버(`license_snapshot_archiver.py`)의 exit code는 **부분 성공을 3으로 뭉뚱그린다** —
20곳 중 1곳만 새로 받아도 3이고, 스냅샷 디렉터리 개수도 6→7로 늘어난다. 그래서 "exit이 3이고
개수가 늘었으니 성공"이라는 판정은 **13곳이 영구 미확보로 남은 상태를 통과시킨다**. 대상이
*소급 불가*(확인 시점 약관은 나중에 재구성 불가) 자산이므로 그 오판의 비용은 되돌릴 수 없다.

그래서 판정을 사람 눈이 아니라 **exit code**로 옮긴다(CLAUDE.md "게이트 판정은 항상 CLI
exit 0/1"·"변별력 없는 검증 스텝 금지"). 게이트 `G-license-snapshot-blocked-sources`는
이 스크립트가 **exit 0**을 낼 때만 clear한다.

판정 규약
---------
- **exit 0** — 카탈로그 전곳 확보. 감사로그가 성공으로 기록했고 *그 파일이 디스크에 실재*한다.
- **exit 1** — 미확보가 1곳이라도 있음(= 게이트 유지). 미확보 source_id를 전건 출력한다.
- **exit 2** — 판정 불가(카탈로그·감사로그를 못 읽음 등). "0건 통과"로 위장하지 않는다.

감사로그만 믿지 않는 이유: 로그에 성공이 적혀도 파일이 지워졌거나 커밋되지 않았으면 증거는
없는 것이다. 그래서 **로그 ∧ 파일 실재** 양쪽을 만족해야 확보로 센다.

의존성: 표준 라이브러리만 (Kiki 머신에서 backend 설치 없이 단독 실행 — 아카이버와 동일 제약).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[1]
_ARCHIVER = _THIS_DIR / "license_snapshot_archiver.py"


def _load_archiver():
    """아카이버 모듈을 경로로 로드한다 — 카탈로그의 단일 진실 원천은 그쪽이다.

    source_id 목록을 여기 복제하면 두 벌이 되어 한쪽만 바뀌는 순간 판정이 조용히 틀어진다
    (CLAUDE.md 파생 원칙). 로드 실패는 침묵하지 않고 exit 2로 올린다.
    """
    spec = importlib.util.spec_from_file_location("_license_archiver", _ARCHIVER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"아카이버 모듈 스펙 생성 실패: {_ARCHIVER}")
    module = importlib.util.module_from_spec(spec)
    # sys.modules 선등록 필수 — dataclass 데코레이터가 `sys.modules[cls.__module__]`을 조회한다.
    # 등록 없이 exec하면 AttributeError('NoneType' has no attribute '__dict__')로 죽는다(실측).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def captured_source_ids(archive_dir: Path, ok_events: frozenset[str]) -> set[str]:
    """감사로그가 성공으로 기록했고 **스냅샷 파일이 실재하는** source_id 집합."""
    audit_path = archive_dir / "audit_log.jsonl"
    if not audit_path.is_file():
        raise FileNotFoundError(f"감사로그 부재: {audit_path}")

    logged: set[str] = set()
    for lineno, line in enumerate(audit_path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:  # 예외 타입명 동반 — 침묵 실패 금지
            raise ValueError(
                f"{audit_path}:{lineno} 파싱 실패({type(exc).__name__}: {exc})"
            ) from exc
        if record.get("event") in ok_events and record.get("source_id"):
            logged.add(str(record["source_id"]))

    # 로그 ∧ 파일 실재 — 로그만 보고 "확보"로 세면 삭제·미커밋 상태를 놓친다.
    snapshots = archive_dir / "snapshots"
    return {sid for sid in logged if any((snapshots / sid).glob("*.meta.json"))}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "licenses",
        help="스냅샷 아카이브 루트 (기본: data/licenses)",
    )
    args = parser.parse_args(argv)

    try:
        archiver = _load_archiver()
        catalog = [s.source_id for s in archiver.TIER1_SOURCES]
        captured = captured_source_ids(args.archive_dir, archiver.OK_EVENTS)
    except Exception as exc:  # noqa: BLE001 — 판정 불가는 통과가 아니라 exit 2
        print(f"판정 불가 ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2

    if not catalog:
        print(
            "판정 불가: 카탈로그가 비어 있다 (빈 목록으로 '전곳 확보'를 만들지 않는다)",
            file=sys.stderr,
        )
        return 2

    missing = [sid for sid in catalog if sid not in captured]
    print(f"라이선스 약관 스냅샷 커버리지: {len(catalog) - len(missing)}/{len(catalog)} 확보")
    if missing:
        print(f"미확보 {len(missing)}곳:")
        for sid in missing:
            print(f"  · {sid}")
        print("\n→ 게이트 G-license-snapshot-blocked-sources 유지 (전곳 확보 시에만 clear)")
        return 1
    print("→ 전곳 확보 — 게이트 G-license-snapshot-blocked-sources clear 가능")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
