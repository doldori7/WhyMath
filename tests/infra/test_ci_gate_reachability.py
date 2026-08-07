"""[OPS-19] CI 게이트의 **도달 가능성** 계약 — 스텝 `if`가 부모 잡 `if`보다 좁은 사각 차단.

왜 이 테스트가 있는가
--------------------
`tests/infra/test_qa_pipeline_wiring.py`는 `qa_pipeline` 스텝이 존재하고 `-m` 모듈 호출이며
`if: needs.changes.outputs.corpus == 'true'`를 갖는다는 것까지는 검증했지만, **그 스텝의
부모 잡(`data-pipeline`)의 `if`가 `needs.changes.outputs.data_pipeline == 'true'`를 요구한다는
사실은 아무도 보지 않았다**(2026-08-04 실측, `data_platform_module_gap_review_r2.md` A1).
`corpus`와 `data_pipeline`은 서로 다른 경로 패턴이라, **코퍼스만 바뀐 PR에서는 부모 잡이
통째로 skip되어 게이트가 시작조차 하지 않는다** — `continue-on-error: true`로 무음화되기
*이전* 단계의 결함이다. 기존 배선 동결 테스트 5건은 스텝 존재·조건 문자열만 보고 전부 green
이었다(CLAUDE.md "검증 장치를 만들고 배선 확인 없이 완료 선언 금지" 4회차 — 선례
`OPS-03`·`OPS-08`·`OPS-11`).

검증 계약
--------
① `changes` 잡의 `filter` 스텝 셸 스크립트에서 플래그별 path 정규식을 **손으로 옮기지 않고**
   파싱해 낸다(하드코딩하면 플래그가 늘어날 때 이 테스트가 조용히 뒤처진다).
② 합성한 대표 경로가 그 정규식에 실제로 매치하는지 **자기 자신을 재검증**한다.
③ 스텝 자체가 `needs.changes.outputs.*`를 참조하는 `if`를 가진 모든 스텝(=게이트성 스텝)에
   대해, 그 스텝의 트리거 플래그**만** 참인 변경셋에서 부모 잡의 `if`도 참이 되는지 판정한다
   — 레지스트리(하드코딩 표) 없이 구조 스캔이라 새 스텝이 추가돼도 자동으로 적용된다.
④ 평가기는 인식하지 못한 표현식 토큰을 만나면 조용히 통과시키지 않고 실패한다(위장 금지).
⑤ 평가기 자체의 판별력을 합성 픽스처(이번에 실제로 있었던 버그·수정 문자열)로 고정한다 —
   버그 상태에서 False, 수정 상태에서 True를 내지 않으면 검증이 아니라 위장이다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_PATH = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_CHANGES_JOB_KEY = "changes"
_CHANGES_STEP_ID = "filter"

# github.event_name을 pull_request로 고정한 뒤 남는 토큰만 허용한다 — 이 저장소의 job/step
# `if:`가 실제로 쓰는 어휘(&&·||·괄호·True/False·and/or/not)를 벗어나면 평가하지 않고 실패한다.
_ALLOWED_EXPR_CHARS = re.compile(r"^[\sTrueFalseandornot()]*$")


def _load_ci_spec() -> dict[str, Any]:
    if not _CI_PATH.is_file():
        raise AssertionError(f"{_CI_PATH} 이(가) 없다 — 게이트 배선을 확인할 수 없다.")
    spec: Any = yaml.safe_load(_CI_PATH.read_text(encoding="utf-8"))
    return dict(spec or {})


def _changes_filter_script() -> str:
    spec = _load_ci_spec()
    jobs = spec.get("jobs") or {}
    if _CHANGES_JOB_KEY not in jobs:
        raise AssertionError(f"ci.yml에 `{_CHANGES_JOB_KEY}` 잡이 없다.")
    steps = (jobs[_CHANGES_JOB_KEY] or {}).get("steps") or []
    for step in steps:
        if isinstance(step, dict) and step.get("id") == _CHANGES_STEP_ID:
            script = str(step.get("run", ""))
            if not script.strip():
                raise AssertionError(f"`{_CHANGES_STEP_ID}` 스텝의 run이 비어 있다.")
            return script
    raise AssertionError(
        f"`{_CHANGES_JOB_KEY}` 잡에 id=`{_CHANGES_STEP_ID}` 스텝이 없다 — "
        "changes 잡의 필터 스텝이 개명·삭제됐다면 이 테스트도 함께 고쳐라."
    )


def _changes_job_flag_patterns() -> dict[str, str]:
    """`changes` 잡의 필터 스크립트에서 플래그→path 정규식을 파싱한다.

    ①`if printf ... | grep -qE '<pattern>'; then\\n  <var>=true` 블록에서 var→pattern,
    ②`echo "<flag>=$<var>"` 블록에서 var→flag를 각각 추출해 조합한다. 6개 플래그 이름을
    하드코딩하지 않는다 — 스크립트 자체가 정본이다.
    """
    script = _changes_filter_script()

    var_to_pattern: dict[str, str] = {}
    for m in re.finditer(
        r"grep -qE '([^']*)'; then\s*\n\s*(\w+)=true",
        script,
    ):
        pattern, var = m.group(1), m.group(2)
        var_to_pattern[var] = pattern

    var_to_flag: dict[str, str] = {}
    for m in re.finditer(r'echo "(\w+)=\$(\w+)"', script):
        flag, var = m.group(1), m.group(2)
        var_to_flag[var] = flag

    if not var_to_pattern:
        raise AssertionError(
            "changes 필터 스크립트에서 `grep -qE '...'; then\\n <var>=true` 블록을 하나도 "
            "찾지 못했다 — 스크립트 형태가 바뀌었으면 이 파서를 함께 고쳐라."
        )
    if not var_to_flag:
        raise AssertionError(
            'changes 필터 스크립트에서 `echo "<flag>=$<var>"` 블록을 하나도 찾지 못했다.'
        )

    flag_patterns: dict[str, str] = {}
    for var, pattern in var_to_pattern.items():
        flag = var_to_flag.get(var)
        if flag is None:
            raise AssertionError(
                f"변수 `{var}`가 grep 블록에는 있으나 echo 출력 블록에 없다 — "
                "플래그 이름을 못 찾아 도달 가능성을 판정할 수 없다."
            )
        flag_patterns[flag] = pattern
    return flag_patterns


def _representative_path_for_pattern(pattern: str) -> str:
    """`^(alt1|alt2|...)` 형태 정규식에서 그 정규식에 실제로 매치하는 리터럴 경로 1개를 합성한다.

    합성 직후 자기 자신을 `re.match`로 재검증한다 — 실패하면 조용히 틀린 경로를 반환하지
    않고 즉시 실패한다(이 저장소의 "파서가 위장하지 않는다" 관행).
    """
    body = pattern
    if body.startswith("^("):
        body = body[2:]
    else:
        raise AssertionError(f"정규식이 예상 형태(`^(...)`)가 아니다: {pattern!r}")
    first_alt = body.split("|", 1)[0]

    is_anchored_end = first_alt.endswith("$")
    literal = first_alt[:-1] if is_anchored_end else first_alt
    literal = literal.replace("\\.", ".")
    if any(ch in literal for ch in "^$*+?[]{}()\\"):
        raise AssertionError(
            f"첫 대안 {first_alt!r}에 처리하지 못하는 정규식 메타문자가 남아 있다 — "
            "대표 경로 합성기를 확장해라(조용히 틀린 경로를 만들지 않는다)."
        )
    path = literal if is_anchored_end else literal + "__ops19_reachability_probe__.txt"

    if not re.match(pattern, path):
        raise AssertionError(
            f"합성한 대표 경로 {path!r}가 자기 자신의 정규식 {pattern!r}에 매치하지 않는다 "
            "— 합성 로직이 잘못됐다."
        )
    return path


def _flags_referenced(condition: str) -> set[str]:
    return set(re.findall(r"needs\.changes\.outputs\.(\w+)", condition))


def _job_reachable_under_flags(job_if: str, flags_true: set[str]) -> bool:
    """`job_if`를 `github.event_name == 'pull_request'` 고정 하에, `flags_true`만 참인
    변경셋에서 평가한다. 인식 못한 토큰이 남으면 조용히 통과시키지 않고 실패한다.
    """
    expr = job_if
    expr = expr.replace("github.event_name != 'pull_request'", "False")
    expr = expr.replace("github.event_name == 'pull_request'", "True")
    expr = expr.replace("github.event_name != 'schedule'", "True")
    expr = expr.replace("github.event_name == 'schedule'", "False")

    for flag in sorted(_flags_referenced(expr), key=len, reverse=True):
        token = f"needs.changes.outputs.{flag} == 'true'"
        expr = expr.replace(token, "True" if flag in flags_true else "False")

    expr = expr.replace("&&", " and ").replace("||", " or ")

    if not _ALLOWED_EXPR_CHARS.match(expr):
        raise AssertionError(
            f"job if {job_if!r}를 치환한 결과 {expr!r}에 인식하지 못한 토큰이 남았다 — "
            "이 평가기가 모르는 새 어휘가 ci.yml에 들어왔다. 평가기를 확장해라(조용히 "
            "통과시키지 않는다)."
        )
    # eval — 이 저장소 ruff 설정(select E/F/I/N/B/W)엔 bandit(S) 룰이 없어 별도 noqa 불필요.
    # 위 _ALLOWED_EXPR_CHARS 검사를 통과한 문자열만 여기 도달한다(True/False/and/or/not/괄호/공백뿐).
    return bool(eval(expr, {"__builtins__": {}}, {}))


def _gate_steps_with_own_flag_condition(
    jobs: dict[str, Any],
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """스텝 자체의 `if`가 `needs.changes.outputs.*`를 참조하는 (job_key, job, step) 전수."""
    found: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for job_key, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            step_if = str(step.get("if", ""))
            if _flags_referenced(step_if):
                found.append((job_key, job, step))
    return found


def test_representative_paths_match_their_own_patterns() -> None:
    """대표 경로 합성기가 실제 ci.yml의 6개 플래그 정규식 전부에 대해 스스로 검증을 통과한다."""
    flag_patterns = _changes_job_flag_patterns()
    assert len(flag_patterns) >= 6, (
        f"플래그가 {len(flag_patterns)}개만 파싱됐다 — changes 필터 스크립트 파서가 "
        f"일부를 놓쳤을 수 있다: {sorted(flag_patterns)}"
    )
    for flag, pattern in flag_patterns.items():
        path = _representative_path_for_pattern(pattern)
        assert re.match(pattern, path), f"[{flag}] {path!r}가 {pattern!r}에 매치하지 않는다."


def test_gate_steps_reachable_under_own_trigger() -> None:
    """계약 ③ — 게이트성 스텝마다, 그 스텝만의 트리거 플래그로는 부모 잡도 실행돼야 한다.

    이것이 실제로 잡은 결함(A1): `qa_pipeline` 스텝은 `corpus`로만 트리거되는데 부모
    `data-pipeline` 잡은 `data_pipeline`을 요구해, corpus-only PR에서 부모 잡이 skip되고
    스텝은 시작조차 하지 못했다.
    """
    spec = _load_ci_spec()
    jobs = spec.get("jobs") or {}
    assert jobs, "ci.yml에 jobs가 없다 — 배선을 확인할 수 없다."

    gates = _gate_steps_with_own_flag_condition(jobs)
    violations: list[str] = []
    for job_key, job, step in gates:
        step_if = str(step.get("if", ""))
        job_if = str(job.get("if", ""))
        step_flags = _flags_referenced(step_if)
        if not job_if:
            continue  # 부모 잡에 if가 없으면(=항상 실행) 도달 불가 문제가 성립하지 않는다.
        if not _job_reachable_under_flags(job_if, step_flags):
            step_name = step.get("name", "(이름 없음)")
            violations.append(
                f"[{job_key}] 스텝 '{step_name}' — 스텝 if={step_if!r}가 참조하는 플래그"
                f"({sorted(step_flags)})만 참인 변경셋에서는 부모 잡 if={job_if!r}가 거짓이라 "
                "스텝이 아예 실행되지 않는다(continue-on-error로 무음화되기 이전 단계의 결함)."
            )
    assert (
        not violations
    ), "CI 게이트 도달 불가 — 스텝은 존재하나 부모 잡이 skip된다:\n" + "\n".join(violations)


# ─────────────────────────────────────────────────────────────────────────
# 변별력 검증(양방향) — 평가기 자체를, 실제로 있었던 버그·수정 문자열로 고정한다.
# 합성 픽스처이며 실제 ci.yml을 건드리지 않는다 — 평가기의 판별력을 영구히 동결하는 것이
# 목적이라, 미래에 누가 평가기 로직을 바꿔도 이 두 값에 대해서는 계속 정답을 내야 한다.
# ─────────────────────────────────────────────────────────────────────────

_BUGGY_DATA_PIPELINE_JOB_IF = (
    "(github.event_name != 'pull_request' || needs.changes.outputs.data_pipeline == 'true') "
    "&& github.event_name != 'schedule'"
)
_FIXED_DATA_PIPELINE_JOB_IF = (
    "(github.event_name != 'pull_request' || needs.changes.outputs.data_pipeline == 'true' "
    "|| needs.changes.outputs.corpus == 'true') && github.event_name != 'schedule'"
)
_QA_PIPELINE_STEP_IF = "needs.changes.outputs.corpus == 'true'"


def test_evaluator_flags_the_known_bug_before_fix() -> None:
    step_flags = _flags_referenced(_QA_PIPELINE_STEP_IF)
    assert step_flags == {"corpus"}
    assert not _job_reachable_under_flags(
        _BUGGY_DATA_PIPELINE_JOB_IF, step_flags
    ), "평가기가 버그 상태(수정 전 job if)에서도 도달 가능하다고 판정했다 — 변별력이 없다."


def test_evaluator_clears_after_fix() -> None:
    step_flags = _flags_referenced(_QA_PIPELINE_STEP_IF)
    assert _job_reachable_under_flags(
        _FIXED_DATA_PIPELINE_JOB_IF, step_flags
    ), "평가기가 수정된 job if에서도 여전히 도달 불가라고 판정했다 — 변별력이 없다."


# ─────────────────────────────────────────────────────────────────────────
# 부록 — 미배선 CLI 목록 (가시화만·게이트 아님, OPS-19 acceptance 마지막 항목)
#
# __main__을 갖췄으나 워크플로 호출 0인 CLI 3종(2026-08-04 실측, 전수 grep):
#   · harness.problem_bank_coverage  — 소유: ARCH-18(done, 미배선인 채로 완료 처리됨)
#   · harness.visualization_reach_report — 소유: VIZ-04(done, acceptance ⑥이 CI 배선
#     확인을 요구했으나 실측상 워크플로 호출 0건 — 배선이 실제로 확인됐는지는 별건)
#   · ops.cost_report — 소유 태스크 없음
# 이 항목들의 배선 자체는 이 태스크의 범위 밖이다(OPS-19는 "게이트성 스텝이 도달 가능한가"
# 계약이지, 미배선 CLI 전수 처분이 아니다). 소유 태스크가 있는 2건은 그쪽에서 판단한다.
# ─────────────────────────────────────────────────────────────────────────
