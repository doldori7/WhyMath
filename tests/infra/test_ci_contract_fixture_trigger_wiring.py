r"""공유 계약 fixture(`data/*.json`) ↔ CI `changes` 경로 필터의 **트리거 배선** 동결.

왜 이 테스트가 있는가 (COLLAB-04 / `collaboration_module_gap_review_r3.md` §3 D5 — 2026-08-11)
-----------------------------------------------------------------------------------------
`ci.yml`의 `changes` 잡은 PR diff를 정규식에 걸어 하위 잡의 실행 여부를 정한다. backend 잡
필터에는 `data/notation_contract.json`·`data/render_contract.json` **두 계약만** 개별 나열돼
있었고, 나머지 6종(`access_matrix`·`visual_style_contract`·`scene_contract`·
`segmentation_contract`·`notation_support_manifest`·`notation_missing_baseline`)은 없었다.
즉 **계약 파일만 고치는 PR은 backend 잡이 skip돼 그 계약의 거버넌스 테스트가 돌지 않았다** —
그 게이트가 막으라고 만들어진 바로 그 드리프트 벡터다. 항상 도는 `infra-contracts` 잡은
`tests/infra`만 실행하므로 대체 경로가 아니다(계약 소비 테스트는 전부 `tests/backend/**`).

`tests/infra/test_test_suite_wiring.py`(OPS-10)가 *"테스트 디렉터리가 CI 실행 경로에
도달하는가"*를 동결한다면, 이 파일은 그 **한 단계 안쪽**을 동결한다 — *"그 테스트를 깨울
입력 경로(계약 파일)가 필터 안에 있는가"*. OPS-10 축은 정당하게 통과했는데도 사각이
남았던 이유가 정확히 이 층이다("돌긴 도는데 깨울 입력이 필터 밖").

분류 기준 (무엇을 '계약 fixture'로 보는가 — 추론 아님)
--------------------------------------------------
- **대상** = `data/` **최상위**(재귀 아님) `*.json` 전건. 실측(2026-08-11) 8종 전부가
  `tests/backend/**`의 골든/거버넌스 테스트가 읽는 공유 계약이다.
- **대상 밖** = `data/` 하위 디렉터리(`data/corpus/`·`data/ncic/` …). 코퍼스·원천 데이터는
  별도 축(`changes` 잡의 `corpus` 플래그)이 담당하며 변경 빈도가 전혀 다르다.
- **예외**는 `_NON_CONTRACT_ALLOWLIST`에 **사유를 명시**해야만 통과한다(무사유 예외 금지 —
  OPS-06·OPS-08 선례). 사라진 파일에 대한 죽은 예외도 실패시킨다.

검증 계약 (각 항목은 변별력이 확인된 것만 — CLAUDE.md "변별력 없는 검증 스텝 금지")
--------------------------------------------------------------------------------
① `data/` 최상위 계약 fixture 전건이 **backend 잡 필터**에 매치한다(= 계약 단독 수정 PR이
   backend 잡을 깨운다). 하나라도 안 걸리면 RED.
② 같은 전건이 **web 잡 필터**에도 매치한다(web 골든이 계약을 함께 읽는 축 — D5 "하지 말 것"이
   web 잡 사각을 같은 태스크에서 함께 보라고 지정).
③ **집행 정합** — 각 계약을 실제로 읽는 소비 테스트가 `tests/backend/**`에 1건 이상 있다.
   필터가 잡을 깨워도 그 계약을 보는 검사가 없으면 트리거는 무의미하다("존재함 ≠ 돌아감"의
   반대편 — "깨우긴 깨우는데 볼 사람이 없다"). 새 계약이 소비 테스트 없이 착지하면 RED.
④ 파서가 위장하지 않는다 — `ci.yml`을 못 읽거나, 필터 정규식을 못 찾거나, 플래그 변수 ↔ 잡
   output 매핑에 실패하면 "위반 0 통과"가 아니라 **예외로 실패**한다. "0건 통과"와 "측정
   실패"는 절대 같은 색이면 안 된다.
⑤ 판정 함수 자체의 변별력을 상시 봉인 — 계약 하나를 뺀 합성 필터를 넣으면 검출되고, 완전한
   필터는 통과한다(양성 대조 포함 = 무차별 실패가 아님).

의도적으로 검증하지 않는 것 (정직한 공백)
--------------------------------------
- **mobile·data-pipeline 잡 필터는 보지 않는다** — COLLAB-04 acceptance ⑥이 범위 밖으로
  지정했다. 실측상 `scene_contract`·`segmentation_contract`·`render_contract`는
  `src/mobile/test/*.dart`가 함께 읽으므로 **같은 사각이 mobile 축에 남아 있다**(후속 태스크
  대상). 여기서 조용히 확장하지 않고 공백으로 남긴다.
- **잡의 `if` 조건·required check 강제 여부**는 모델링하지 않는다(각각 OPS-10·
  `test_required_checks_doc.py` 담당). 이 파일은 필터 정규식과 계약 파일 목록만 대조한다.
- **정규식 방언** — CI 러너는 `grep -qE`(POSIX ERE), 이 테스트는 `re`로 판정한다. 현행 필터가
  쓰는 문법(`^`·`$`·`|`·`\.`·문자클래스)은 두 방언에서 동치이며, 그 범위를 벗어나는 문법이
  들어오면 이 전제가 깨진다(그 경우 실측 프로브로 재확인해야 한다).
- 계약 **내용**의 정합(예: `access_matrix.json` #8의 참조 무결성)은 이 파일의 축이 아니다
  (COLLAB-05 소관).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_YAML = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_DATA_DIR = _REPO_ROOT / "data"
_BACKEND_TESTS_DIR = _REPO_ROOT / "tests" / "backend"

# 계약 fixture로 보지 *않을* 최상위 data/*.json — 반드시 사유를 적는다(무사유 예외 금지).
# 형식: {"파일명.json": "왜 계약이 아닌가 + 누가 대신 검사하는가"}
# 2026-08-11 실측 기준 예외 0건(8종 전부가 tests/backend의 소비 테스트를 가진다).
_NON_CONTRACT_ALLOWLIST: dict[str, str] = {}

# `changes` 잡의 어느 잡 output을 이 파일이 강제하는가 — 잡 이름(=output 키) 기준.
# mobile/data_pipeline/docker/corpus는 의도적 제외(위 "정직한 공백" 참조).
_ENFORCED_OUTPUTS = ("backend", "web")

# `grep -qE '<정규식>'; then` 다음 줄의 `<변수>=true` → (정규식, 플래그 변수) 추출.
_FILTER_BLOCK_RE = re.compile(
    r"grep\s+-qE\s+'(?P<regex>[^']*)'\s*;\s*then\s*\n\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)=true"
)

# `echo "backend=$be" >> "$GITHUB_OUTPUT"` → (잡 output 이름, 플래그 변수) 추출.
# 상수 하드코딩 대신 스크립트에서 파생시켜 변수명이 바뀌어도 매핑이 따라가게 한다.
_OUTPUT_BIND_RE = re.compile(
    r'echo\s+"(?P<output>[A-Za-z_][A-Za-z0-9_]*)=\$(?P<var>[A-Za-z_][A-Za-z0-9_]*)"'
)


# ── ci.yml 파싱 (계약 ④: 실패는 예외로) ────────────────────────────────────────


def _extract_jobs(spec: Any, source: str) -> dict[str, Any]:
    """스펙에서 jobs 매핑을 꺼낸다 — 공백/비매핑이면 예외(파서 무력화 ≠ 통과)."""
    if not isinstance(spec, dict):
        raise AssertionError(f"{source}: 워크플로 YAML이 매핑으로 파싱되지 않았다.")
    jobs = spec.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise AssertionError(f"{source}: jobs 블록이 비었다 — 파서가 배선을 읽지 못하는 상태다.")
    return jobs


def _load_ci_jobs() -> dict[str, Any]:
    if not _CI_YAML.is_file():
        raise AssertionError(f"{_CI_YAML}: CI 워크플로 파일이 없다 — 배선을 읽을 수 없다.")
    spec = yaml.safe_load(_CI_YAML.read_text(encoding="utf-8"))
    return _extract_jobs(spec, str(_CI_YAML))


def _iter_run_steps(job: Mapping[str, Any]) -> Iterator[str]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("run"), str):
            yield step["run"]


def _changes_filter_script(jobs: Mapping[str, Any]) -> str:
    """`changes` 잡에서 경로 필터를 세팅하는 run 스크립트를 돌려준다(못 찾으면 예외)."""
    changes = jobs.get("changes")
    if not isinstance(changes, dict):
        raise AssertionError("ci.yml: `changes` 잡이 없다 — 경로 필터 정의를 읽을 수 없다.")
    scripts = [run for run in _iter_run_steps(changes) if "GITHUB_OUTPUT" in run]
    if not scripts:
        raise AssertionError(
            "ci.yml: `changes` 잡에서 GITHUB_OUTPUT을 쓰는 run 스텝을 찾지 못했다 — "
            "필터 정의를 읽지 못하는 상태다(측정 실패이지 통과가 아니다)."
        )
    return "\n".join(scripts)


def _filter_regex_by_output(script: str) -> dict[str, str]:
    """필터 스크립트 → {잡 output 이름: 경로 정규식}. 매핑 실패는 예외(계약 ④)."""
    var_to_regex = {m.group("var"): m.group("regex") for m in _FILTER_BLOCK_RE.finditer(script)}
    if not var_to_regex:
        raise AssertionError(
            "필터 스크립트에서 `grep -qE '...'; then <flag>=true` 블록을 하나도 찾지 못했다 — "
            "파서가 필터를 읽지 못하는 상태다."
        )
    output_to_var = {m.group("output"): m.group("var") for m in _OUTPUT_BIND_RE.finditer(script)}
    if not output_to_var:
        raise AssertionError(
            '필터 스크립트에서 `echo "<output>=$<flag>"` 바인딩을 하나도 찾지 못했다 — '
            "플래그 변수와 잡 output을 연결할 수 없다."
        )
    resolved: dict[str, str] = {}
    for output, var in output_to_var.items():
        if var in var_to_regex:
            resolved[output] = var_to_regex[var]
    missing = [o for o in _ENFORCED_OUTPUTS if o not in resolved]
    if missing:
        raise AssertionError(
            f"필터 정규식을 해석하지 못한 잡 output: {missing} — "
            f"발견한 플래그={sorted(var_to_regex)} · 바인딩={sorted(output_to_var)}. "
            "필터 문법이 바뀌었다면 이 파서를 함께 고쳐라(조용한 통과 금지)."
        )
    return resolved


# ── 계약 fixture 목록·소비처 ───────────────────────────────────────────────────


def _contract_fixture_paths() -> list[str]:
    """`data/` 최상위 *.json 중 허용목록을 뺀 계약 fixture의 레포 상대 경로(POSIX)."""
    if not _DATA_DIR.is_dir():
        raise AssertionError(f"{_DATA_DIR}: data 디렉터리가 없다 — 계약 목록을 읽을 수 없다.")
    names = sorted(p.name for p in _DATA_DIR.iterdir() if p.is_file() and p.suffix == ".json")
    if not names:
        raise AssertionError(
            f"{_DATA_DIR}: 최상위 *.json이 0건이다 — 스캔이 무력화된 상태다"
            "(빈 목록으로 '위반 0'을 만들지 않는다)."
        )
    return [f"data/{name}" for name in names if name not in _NON_CONTRACT_ALLOWLIST]


def _backend_test_consumers(fixture_name: str) -> list[str]:
    """`tests/backend/**`에서 이 계약 파일명을 언급하는 테스트 파일 목록(레포 상대 경로)."""
    hits: list[str] = []
    for path in sorted(_BACKEND_TESTS_DIR.rglob("*.py")):
        if fixture_name in path.read_text(encoding="utf-8", errors="replace"):
            hits.append(path.relative_to(_REPO_ROOT).as_posix())
    return hits


# ── 순수 판정 함수 (실 레포와 결함 주입이 같은 함수를 쓴다 — 중복 파서 금지) ──────


def _trigger_violations(regex_by_output: Mapping[str, str], contracts: list[str]) -> list[str]:
    """계약 × 강제 대상 잡에서 필터에 매치하지 않는 조합을 위반으로 모은다."""
    violations: list[str] = []
    for output in _ENFORCED_OUTPUTS:
        pattern = regex_by_output.get(output)
        if pattern is None:
            violations.append(f"[{output}] 필터 정규식을 찾지 못했다")
            continue
        compiled = re.compile(pattern)
        for path in contracts:
            if not compiled.search(path):
                violations.append(f"[{output}] {path} — 필터에 매치하지 않는다(잡 SKIP)")
    return violations


# ── 계약 ①·② : 실제 ci.yml 판정 ───────────────────────────────────────────────


def test_contract_fixtures_trigger_backend_and_web_jobs() -> None:
    """계약 ①② — `data/` 최상위 계약 fixture 전건이 backend·web 필터를 깨운다.

    계약 파일만 고치는 PR에서 그 계약의 거버넌스 테스트가 skip되면 게이트가 자기 계약을 지키지
    못한다(D5). 필터를 좁히면(예: `*_contract.json`만 매치) 이 단언이 RED가 된다.
    """
    jobs = _load_ci_jobs()
    regex_by_output = _filter_regex_by_output(_changes_filter_script(jobs))
    contracts = _contract_fixture_paths()

    violations = _trigger_violations(regex_by_output, contracts)
    listed = "\n".join(f"  · {v}" for v in violations)
    current = "\n".join(f"  · {out}: {regex_by_output.get(out)!r}" for out in _ENFORCED_OUTPUTS)
    assert not violations, (
        "계약 fixture가 CI 트리거 축 밖이다 — 그 파일만 수정하는 PR에서 소비 잡이 SKIP된다"
        f"(COLLAB-04 / r3 §3 D5 재발).\n{listed}\n필터 현황:\n{current}"
    )


# ── 계약 ③ : 집행 정합(깨운 잡에 그 계약을 보는 검사가 있는가) ─────────────────


def test_every_contract_fixture_has_a_backend_test_consumer() -> None:
    """계약 ③ — 각 계약 fixture를 읽는 소비 테스트가 `tests/backend/**`에 1건 이상 있다.

    트리거를 붙여도 그 계약을 검사하는 테스트가 없으면 잡을 깨우는 의미가 없다. 새 계약이
    소비 테스트 없이 착지하면 여기서 RED — 테스트를 붙이거나 사유 명시 허용목록에 넣어야 한다.
    (해당 테스트가 실제 CI 잡의 수집 범위에 드는지는 `test_test_suite_wiring.py`가 동결한다.)
    """
    contracts = _contract_fixture_paths()
    assert _BACKEND_TESTS_DIR.is_dir(), f"{_BACKEND_TESTS_DIR}: 백엔드 테스트 트리가 없다."

    orphans = [path for path in contracts if not _backend_test_consumers(Path(path).name)]
    assert not orphans, (
        "계약 fixture인데 `tests/backend/**`에 소비 테스트가 없다 — 트리거를 붙여도 볼 사람이 "
        "없다(계약을 검사하는 테스트를 붙이거나, 계약이 아니라면 사유와 함께 "
        "_NON_CONTRACT_ALLOWLIST에 등재하라).\n" + "\n".join(f"  · {p}" for p in orphans)
    )


def test_allowlist_entries_have_reasons_and_exist() -> None:
    """계약 ③ 보조 — 허용목록은 사유 필수이며, 사라진 파일에 대한 죽은 예외를 남기지 않는다."""
    for name, reason in _NON_CONTRACT_ALLOWLIST.items():
        assert reason.strip(), f"허용목록 '{name}'의 사유가 비었다 — 무사유 예외 금지."
        assert (_DATA_DIR / name).is_file(), (
            f"허용목록 '{name}'에 해당하는 파일이 data/에 없다 — 죽은 예외는 다음 동명 파일을 "
            "조용히 면제시킨다. 항목을 지워라."
        )


# ── 계약 ④ : 파서가 위장하지 않는지 ───────────────────────────────────────────


def test_parser_fails_loudly_on_broken_workflow() -> None:
    """계약 ④ — 워크플로/필터를 못 읽으면 '0건 통과'가 아니라 예외로 실패한다."""
    with pytest.raises(AssertionError, match="jobs 블록이 비었다"):
        _extract_jobs({"name": "empty", "on": ["push"]}, source="fake.yml")
    with pytest.raises(AssertionError, match="매핑으로 파싱되지 않았다"):
        _extract_jobs(None, source="fake.yml")
    with pytest.raises(AssertionError, match="`changes` 잡이 없다"):
        _changes_filter_script({"backend": {"steps": []}})
    with pytest.raises(AssertionError, match="GITHUB_OUTPUT을 쓰는 run 스텝"):
        _changes_filter_script({"changes": {"steps": [{"run": "echo hi"}]}})


def test_filter_parser_fails_loudly_on_unreadable_syntax() -> None:
    """계약 ④ — 필터 문법이 파서 밖으로 바뀌면 조용히 통과하지 않고 예외로 실패한다."""
    # grep 블록은 있으나 output 바인딩이 없는 경우
    with pytest.raises(AssertionError, match="바인딩을 하나도 찾지 못했다"):
        _filter_regex_by_output("if printf x | grep -qE '^src/'; then\n  be=true\nfi\n")
    # output 바인딩은 있으나 grep 블록이 없는 경우
    with pytest.raises(AssertionError, match="블록을 하나도 찾지 못했다"):
        _filter_regex_by_output('echo "backend=$be" >> "$GITHUB_OUTPUT"\n')
    # 강제 대상 잡 하나(web)의 필터를 해석하지 못하는 경우
    partial = (
        "if printf x | grep -qE '^src/backend/'; then\n  be=true\nfi\n"
        'echo "backend=$be" >> "$GITHUB_OUTPUT"\n'
        'echo "web=$web" >> "$GITHUB_OUTPUT"\n'
    )
    with pytest.raises(AssertionError, match="필터 정규식을 해석하지 못한 잡 output"):
        _filter_regex_by_output(partial)


# ── 계약 ⑤ : 판정 함수의 변별력 봉인 (결함 주입 + 양성 대조) ────────────────────


_COMPLETE_FILTER = {
    "backend": r"^(src/backend/|tests/backend/|data/[^/]+\.json$)",
    "web": r"^(src/web/|data/[^/]+\.json$)",
}
_LEGACY_INDIVIDUAL_FILTER = {
    # 사고 당시의 형태 — 개별 나열이라 새 계약(access_matrix)이 빠져 있다.
    "backend": r"^(src/backend/|tests/backend/|data/notation_contract\.json$)",
    "web": r"^(src/web/|data/notation_contract\.json$)",
}
_SAMPLE_CONTRACTS = ["data/access_matrix.json", "data/notation_contract.json"]


def test_judge_passes_on_complete_filter() -> None:
    """계약 ⑤ 양성 대조 — 계약 전건을 덮는 필터에서는 위반 0(무차별 실패가 아니다)."""
    assert _trigger_violations(_COMPLETE_FILTER, _SAMPLE_CONTRACTS) == []


def test_judge_detects_missing_contract_in_filter() -> None:
    """계약 ⑤ 결함 주입 — 개별 나열에서 한 계약이 빠지면 두 잡 모두에서 검출된다."""
    violations = _trigger_violations(_LEGACY_INDIVIDUAL_FILTER, _SAMPLE_CONTRACTS)
    assert len(violations) == 2, violations
    assert any(v.startswith("[backend] data/access_matrix.json") for v in violations)
    assert any(v.startswith("[web] data/access_matrix.json") for v in violations)


def test_judge_detects_narrowed_pattern() -> None:
    """계약 ⑤ 결함 주입 — 접두 패턴을 `*_contract.json`으로 좁히면 비-contract 계약이 검출된다.

    이 결함이 현실적인 이유: `access_matrix.json`·`notation_support_manifest.json`처럼 이름에
    `_contract`가 없는 계약이 실재한다. "계약 파일은 이름에 contract가 들어간다"는 추론이
    그대로 사각이 된다.
    """
    narrowed = {
        "backend": r"^(src/backend/|data/[a-z_]+_contract\.json$)",
        "web": r"^(src/web/|data/[a-z_]+_contract\.json$)",
    }
    violations = _trigger_violations(narrowed, ["data/access_matrix.json"])
    assert len(violations) == 2, violations


def test_judge_reports_missing_output_instead_of_passing() -> None:
    """계약 ⑤ — 필터 자체가 없는 잡은 '위반 0'이 아니라 위반으로 보고된다."""
    violations = _trigger_violations({"backend": r"^data/"}, _SAMPLE_CONTRACTS)
    assert any("[web] 필터 정규식을 찾지 못했다" in v for v in violations), violations
