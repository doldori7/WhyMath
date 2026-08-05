"""`test_e2e_pedagogy_pilot_integration.py`가 CI에서 실제로 도는지 실측 동결 — PED-06 acceptance③.

배경 — 왜 별도 테스트가 필요한가
--------------------------------
`docs/architecture/ai_content_generation_gap_review_2.md` §3 D6 acceptance③은 "E2E 파일럿
테스트가 실제로 5단계를 관통하는지 CI 배선 재확인(`tests/infra/test_test_suite_wiring.py`
등록 여부 실측)"을 요구한다. `test_test_suite_wiring.py::test_every_test_directory_is_wired_to_
a_ci_job`가 이미 **일반형**으로 `tests/` 하위 모든 디렉터리(`tests/backend/api`를 포함)가
CI의 실제 pytest 실행에 도달함을 매 CI마다 재확인하므로, 이 파일이 있는 디렉터리가 미배선일
가능성은 그 일반 계약이 이미 배제한다.

그런데 "그 디렉터리가 어떤 pytest 실행에 도달한다"와 "그 실행이 이 파일이 필요로 하는
**실 PostgreSQL 통합 실행**이다"는 다른 주장이다 — 일반 계약은 배선의 *존재*만 보고, 그
배선이 `integration` 마커·실 PG 서비스를 갖춘 실행인지는 보지 않는다(`Wiring`은 애초에
`if:` 조건·env·services를 모델링하지 않는다 — 그 모듈 docstring "의도적으로 검증하지 않는
것" 참조). 이 파일은 그 간극을 메운다: `backend-migrations` 잡의 실제 pytest 스텝이
`-m integration`을 달고 있고 실 PG service를 갖췄음을 **워크플로 YAML에서 직접** 확인해,
"배선 존재"와 "그 배선이 실제로 이 파일을 관통시키는 통합 실행"을 별개 축으로 봉인한다.

재사용 원칙(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지"의 반대 방향 —
장치를 재발명하지 않는다): `Wiring`/`_all_wirings`/`_collect_workflow_wirings`는
`test_test_suite_wiring.py`에서 그대로 import해 재사용한다. 새 파서를 만들지 않는다.
"""

from __future__ import annotations

import yaml

from tests.infra.test_test_suite_wiring import _REPO_ROOT, _TESTS_ROOT, _all_wirings

_TARGET_TEST_FILE = _TESTS_ROOT / "backend" / "api" / "test_e2e_pedagogy_pilot_integration.py"
_TARGET_DIR = _TARGET_TEST_FILE.parent


def test_target_file_exists_at_expected_path() -> None:
    """전제 확인 — 이 테스트가 지목하는 파일이 실제로 그 경로에 있다(경로 드리프트 방지)."""
    assert _TARGET_TEST_FILE.is_file(), (
        f"{_TARGET_TEST_FILE}가 없다 — E2E 파일럿 테스트가 이동/삭제됐다면 이 파일의 경로도 "
        "함께 갱신해야 한다."
    )


def test_target_directory_is_covered_by_some_wiring() -> None:
    """acceptance③ 1단계 — `tests/backend/api/`가 어떤 CI pytest 실행에도 도달한다.

    `test_test_suite_wiring.py`의 일반 계약(`test_every_test_directory_is_wired_to_a_ci_job`)
    이 이미 이를 보장하지만, 이 파일이 그 사실에 **의존**한다는 것을 이 파일 자신의 실패
    메시지로도 드러나게 별도로 재확인한다(일반 계약이 나중에 완화돼도 이 특칭은 남는다 —
    `test_tests_infra_itself_is_wired`가 `tests/infra`를 특칭 봉인하는 것과 동형 패턴).
    """
    wirings = _all_wirings()
    covering = [w for w in wirings if w.covers(_TARGET_DIR)]
    assert covering, (
        f"{_TARGET_DIR}가 어떤 CI pytest 실행에도 도달하지 않는다 — "
        "test_e2e_pedagogy_pilot_integration.py가 CI에서 전혀 실행되지 않는다는 뜻이다."
    )


def test_covering_wiring_is_a_real_integration_run_with_live_postgres() -> None:
    """acceptance③ 2단계(핵심) — 그 배선이 **실 PG를 갖춘 `-m integration` 실행**인지 확인.

    `Wiring.covers()`는 디렉터리 도달성만 보고 `-m integration`·`services:` 같은 실행 조건은
    모델링하지 않는다(모듈 docstring의 정직한 공백) — 그래서 이 테스트가 그 간극을 워크플로
    YAML을 직접 읽어 메운다. 실패하면 두 형태 중 하나다:
      ① 이 디렉터리를 도달시키는 배선이 있으나 그중 어느 것도 `-m integration`을 달지 않음
         (파일럿이 매 CI에서 **항상 skip**된다는 뜻 — pytest.ini markers는 걸려도 실행되지
         않음)
      ② `-m integration` 실행은 있으나 실 PG 서비스가 없음(테스트가 self-skip하며 "통과"로
         위장될 위험)
    """
    wirings = _all_wirings()
    covering = [w for w in wirings if w.covers(_TARGET_DIR)]
    assert covering, "선행 테스트가 통과했다면 여기서 빈 목록일 수 없다(모순 — 재확인 실패)."

    workflow_dir = _REPO_ROOT / ".github" / "workflows"
    integration_sources: list[str] = []
    for path in sorted(p for p in workflow_dir.iterdir() if p.suffix in {".yml", ".yaml"}):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = spec.get("jobs", {}) if isinstance(spec, dict) else {}
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps")
            if not isinstance(steps, list):
                continue
            has_postgres_service = _job_has_postgres_service(job)
            for step_index, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                script = step.get("run")
                if not isinstance(script, str) or "pytest" not in script:
                    continue
                if "-m integration" not in script and "-m=integration" not in script:
                    continue
                source = f"{path.name}:{job_id}#{step_index}"
                if has_postgres_service:
                    integration_sources.append(source)

    covering_sources = {w.source for w in covering}
    matched = [s for s in integration_sources if s in covering_sources]
    assert matched, (
        f"{_TARGET_DIR}를 도달시키는 배선({sorted(covering_sources)})은 있으나, 그중 실 "
        f"PostgreSQL 서비스를 갖춘 `-m integration` pytest 스텝은 없다 — "
        f"test_e2e_pedagogy_pilot_integration.py가 self-skip 상태로만 '통과'하며 실제로는 "
        f"관통되지 않을 위험이 있다.\n"
        f"확인된 통합 실행 소스: {sorted(integration_sources) or '(없음)'}"
    )


def _job_has_postgres_service(job: dict[str, object]) -> bool:
    """잡 정의에 `services.postgres` 서비스 블록이 있는가(GitHub Actions 서비스 컨테이너).

    서비스 *키 이름*(`postgres`)으로 판정한다 — 이미지 문자열은 검사하지 않는다. 실제
    `backend-migrations` 잡의 이미지는 `pgvector/pgvector:pg16`(pgvector 프리설치 PG16
    슈퍼셋 — 슬105)이라 이미지명 자체에 "postgres" 문자열이 없다. 서비스 키를 `postgres`로
    맞추는 것은 이 워크플로의 기존 관례(`env: WHYMATH_DATABASE_URL`이 `127.0.0.1:5432`를
    가리키는 것과 짝)이므로, 키 이름 판정이 이 저장소 배선 실태를 정확히 반영한다.
    """
    services = job.get("services")
    return isinstance(services, dict) and "postgres" in services


# ──────────────────────────────────────────────────────────────────────────
# 변별력 봉인 — 이 판정이 실제로 실 PG 통합 실행이 사라지면 실패하는지(위장 방지).
# ──────────────────────────────────────────────────────────────────────────
def test_defect_missing_integration_marker_is_detected() -> None:
    """결함 주입 — `-m integration`이 빠진 워크플로를 읽으면 이 판정이 실패를 검출한다.

    실제 저장소를 훼손하지 않고, `_job_has_postgres_service`/워크플로 파싱 로직 자체를 가짜
    잡 정의로 직접 실행해 "PG 서비스가 없으면 False를 낸다"를 실측한다(무차별 통과 방지 —
    `test_test_suite_wiring.py`의 tmp_path 결함 주입 관례와 동형이나, 여기서는 파일시스템
    전체를 새로 짓지 않고 판정 함수 자체를 직접 결함 입력으로 호출하는 최소형을 쓴다).
    """
    job_without_postgres: dict[str, object] = {
        "services": {"redis": {"image": "redis:7"}},
        "steps": [{"run": "pytest -m integration"}],
    }
    assert _job_has_postgres_service(job_without_postgres) is False

    job_with_postgres: dict[str, object] = {
        "services": {"postgres": {"image": "pgvector/pgvector:pg16"}},
        "steps": [{"run": "pytest -m integration"}],
    }
    assert _job_has_postgres_service(job_with_postgres) is True
