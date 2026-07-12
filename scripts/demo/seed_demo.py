#!/usr/bin/env python3
"""S1 실기기 시연 시드 — 진단 문제 코퍼스를 backend에 멱등 적재한다.

`/v1/me/next-problem`이 시연에서 문제 카드를 띄우려면 `difficulty_overall`이 채워진 *미시도*
문제가 최소 1건 적재돼 있어야 한다. 이 스크립트는 `l1.problem_bank.populate`를 재사용해(재구현
금지) `data/corpus/problem_bank_v1/problems.jsonl`을 `problem`/`problem_concept`에 적재한다.

**데모 사용자는 시드하지 않는다(의도)**: 콜백(`POST /v1/auth/demo/callback`)이 처음 호출될 때
`resolve_user`가 고정 데모 계정을 lazy upsert하므로, run 스크립트가 콜백으로 토큰을 발급하는 순간
사용자 행이 생긴다(실 로그인 경로를 더 많이 태워 시연 신뢰도↑). 따라서 여기선 문제만 적재한다.

전제: backend 패키지 설치·`WHYMATH_DATABASE_URL` 도달 가능·`alembic upgrade head` 선행(run 스크립트 담당).
CWD 무관하게 동작하도록 코퍼스 경로를 리포 루트 기준으로 해석한다.
"""

from __future__ import annotations

from pathlib import Path

# 리포 루트 = scripts/demo/seed_demo.py에서 2단계 상위. 코퍼스 경로를 절대경로로 고정(CWD 무관).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBLEMS = _REPO_ROOT / "data" / "corpus" / "problem_bank_v1" / "problems.jsonl"


def main() -> int:
    """문제 코퍼스를 멱등 적재하고 종료 코드를 반환(0=성공·2=코퍼스 부재)."""
    from whymath_backend.l1.problem_bank.populate import main as populate_main

    print(f"[seed_demo] 문제 코퍼스 적재 시작: {_PROBLEMS}")
    code = populate_main(["--problems", str(_PROBLEMS)])
    if code == 0:
        print(
            "[seed_demo] 완료 — 데모 사용자는 콜백(/v1/auth/demo/callback) 최초 호출 시 "
            "lazy upsert된다(별도 시드 불필요)."
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
