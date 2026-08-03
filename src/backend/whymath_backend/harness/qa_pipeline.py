"""QA 파이프라인 오케스트레이터 — 기존 검사 자산 조립·단일 판정 (ARCH-21).

정본: `docs/architecture/operations_module_gap_review.md` §3 D2(외부 EOS 틀 모듈 45
"품질검증 QA 엔진" 대조). `harness/`의 38개 검사 모듈이 각자 독립 CLI로 흩어져 있고
이들을 단일 판정으로 묶는 조립 층이 없었다(오케스트레이션 0). 이 모듈이 그 조립 층이다.

이 저장소의 관례(subprocess 0건) — 다른 harness CLI를 subprocess로 호출하는 코드는
이 저장소에 없다. 대신 각 harness 모듈이 자기보다 하위인 여러 모듈을 *직접 import해서
조립*하는 것이 유일한 관례다(예: `defect_detection_eval.py`가 `l3.equivalent.acceptance`+
`defect_seeder`+`retag`를 조립). 이 모듈은 그 관례를 한 계층 위에서 반복한다 — 전부
in-process import, subprocess 금지, **새 판정 로직 신설 0**(전부 기존 함수 재사용).

조립 대상 7개 축(+ wilson.py는 아래 참조):
    1. corpus_audit            — `corpus_audit_eval`(문항 감사, 커밋 스냅샷 재검산)
    2. equivalence_canonicalize — `l3/equivalent/canonicalize`(수식 동치 DSL 폐쇄성)
    3. concept_graph_reachability — `data_pipeline.atom_graph`(원자 백본 그래프)
    4. misconception_crosslink_demotion — `crosslink_demotion_eval`(오개념 crosswalk)
    5. coach_prose_leak        — `coach_prose_leak_eval`(AI 출력 누설)
    6. content_provenance      — `ops.provenance_audit`(저작권 축, ARCH-20)
    7. defect_injection_demotion — `defect_detection_eval`(결함주입 강등전)

**wilson.py는 별도 축이 아니다** — 위 1·4·5·7 네 축이 이미 각자 내부에서
`wilson_lower_bound`/`wilson_upper_bound`를 호출해 경계 판정을 한다(Wilson은 그 네 축이
공유하는 *경계 판정 메커니즘*이지, 독립적으로 실행 가능한 검사 대상이 아니다). 그래서
리포트의 `axes`에 8번째 키로 별도 노출하지 않는다 — 중복 신호 금지.

**cross-package import 경계** — `concept_graph_reachability` 축은 `whymath_backend`가
아니라 별도 pip 패키지(`whymath-data-pipeline`, import명 `data_pipeline`)의
`atom_graph.validate`를 직접 import한다. 이 축은 원래 구 437 개념그래프 코퍼스를
대상으로 설계됐으나, 그 코퍼스는 S0-4b로 `legacy_snapshot`
(readonly·non_runtime·audit_only)로 격하되어
`tests/backend/l1/test_legacy_snapshot_governance.py`가 audit 화이트리스트 밖
소비처를 red로 막는다(실측: 이 축을 최초 실행한 CI에서 그 게이트가 정확히
이 축을 위반으로 잡았다) — QA 오케스트레이터는 "학생에게 실제로 나가는" 그래프를
감사해야 하므로 런타임 진실원천인 원자 백본(`atom_graph_v1`)을 대상으로 한다.
그래프 정형화·검증 로직의 단일 진실 원천이 data-pipeline 쪽에만 있어(재구현 금지
원칙 — 새 판정 로직 신설 0), harness가 예외적으로 패키지 경계를 넘는다. 이게 문제없이
동작하는 이유: ① backend CI 잡이 이미 `pip install -e ../data-pipeline`을 실행한다
(교차계층 거버넌스 테스트 `test_five_node_connectivity_governance.py`가 같은 이유로
선례) ② mypy는 `ignore_missing_imports=true`라 스텁 부재를 문제삼지 않는다 ③
import-linter 7계층 계약(`[tool.importlinter]`)은 `root_package = "whymath_backend"`만
대상이고 `harness`/`ops`는 그 계약 밖(횡단 인프라)이라 이 방향의 import가 계약
위반이 아니다.

미측정 4축(UI 골든·통계 이상치·금칙어/PII·성능 연동)은 코드가 없음을 실측 확인했다 —
`not_measured_axes`에 "검사 안 함"으로 명시한다(침묵 통과 금지, CLAUDE.md).

각 축 실행은 개별 try/except로 격리된다 — 한 축의 예외가 나머지 축 실행을 막지 않고,
그 축은 `{"measured": false, "status": "error", "detail": {"error_type": ...}}`로
보고된다(CLAUDE.md "침묵 실패 금지" — 예외 타입명을 반드시 포함). "검사 안 함"(no_snapshot·
not_measured_axes)과 "에러로 못 함"(error)은 구분해서 보고하되, 게이트 판정(`overall.pass`)
에는 둘 다 실패로 집계한다(단 `no_snapshot`은 정당한 상태라 집계에서 제외).

사용:
    python -m whymath_backend.harness.qa_pipeline
    python -m whymath_backend.harness.qa_pipeline --corpus-root data/corpus --json report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

# cross-package import(모듈 docstring "cross-package import 경계" 참조) — data_pipeline은
# whymath_backend가 아니라 별도 pip 패키지(whymath-data-pipeline)다. 원자 백본 그래프
# 검증의 단일 진실 원천이 거기에만 있어 harness가 예외적으로 패키지 경계를 넘는다.
from data_pipeline.atom_graph.validate import AtomRelation, _find_prerequisite_cycle

from whymath_backend.config import get_settings
from whymath_backend.harness import (
    coach_prose_leak_eval,
    corpus_audit_eval,
    crosslink_demotion_eval,
    defect_detection_eval,
)
from whymath_backend.l3.equivalent.canonicalize import condition_dsl_violation
from whymath_backend.l3.equivalent.defect_seeder import build_defect_seeded_set
from whymath_backend.ops import provenance_audit

__all__ = ["build_report", "main"]

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1

# Wilson 신뢰수준 — 전 축 공용(각 하위 모듈의 CLI 기본값과 동일 0.95).
_CONFIDENCE = 0.95

AxisStatus = Literal["ok", "no_snapshot", "gate_fail", "error"]

# 프로즈 누설 축 — CI ci.yml 게이트 스텝과 정확히 일치시킨 파라미터(정합성 필수).
_PROSE_FLAG_ENV = "WHYMATH_WH1_PROSE_REPHRASE_ENABLED"
_PROSE_N_PER_CELL = 12
_PROSE_MAX_LEAK_UPPER = 0.05
_PROSE_MAX_FALSE_BLOCK_UPPER = 0.2

# 결함주입 강등전 축 — CI ci.yml 게이트 스텝과 정확히 일치시킨 파라미터(정합성 필수).
_DEFECT_N_DEFECTIVE = 120
_DEFECT_N_CLEAN = 120
_DEFECT_SEED = 20260708
_DEFECT_MIN_DETECTION_LOWER = 0.95
_DEFECT_MAX_FALSE_ALARM_UPPER = 0.05

# 오개념 crosswalk 축 — crosslink_demotion_eval CLI(main())의 argparse 기본값과 동일.
_CROSSLINK_CROSS_PER_POSITIVE = 60
_CROSSLINK_SAME_PER_POSITIVE = 60


@dataclass(slots=True, frozen=True)
class AxisResult:
    """축 1개의 실행 결과 — 측정 여부·상태·상세(경계값 등 정직 회계)."""

    measured: bool
    status: AxisStatus
    detail: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {"measured": self.measured, "status": self.status, "detail": self.detail}


@dataclass(slots=True, frozen=True)
class NotMeasuredAxis:
    """코드가 없어 이번 오케스트레이터가 재지 못하는 축 — "검사 안 함"을 명시(침묵 통과 금지)."""

    name: str
    reason: str


# 미측정 4축(2026-07-31 실측 확인 — 코드 0건):
#   · UI 골든 스크린샷 비교
#   · 통계 이상치(정답률/이탈)
#   · 금칙어/PII(코치 AI 출력 콘텐츠 대상 — log_scrubber.py는 로그 전송계층 시크릿
#     마스킹이라 *다른 축*, 여기 흡수 대상 아님)
#   · 성능 연동(ops/service_health.py는 CLI 없음)
_NOT_MEASURED_AXES: tuple[NotMeasuredAxis, ...] = (
    NotMeasuredAxis("ui_golden", "코드 미구현(실측)"),
    NotMeasuredAxis("statistical_outlier", "코드 미구현(실측)"),
    NotMeasuredAxis("banned_words_pii", "코드 미구현(실측·log_scrubber는 별도 축)"),
    NotMeasuredAxis("performance", "코드 미구현(실측)"),
)


@dataclass(slots=True, frozen=True)
class OverallResult:
    """전 축 집계 판정 — no_snapshot은 정당한 상태라 제외, gate_fail·error만 실패로 본다."""

    passed: bool
    failing_axes: list[str]

    def to_json(self) -> dict[str, Any]:
        return {"pass": self.passed, "failing_axes": self.failing_axes}


def _repo_root() -> Path:
    # src/backend/whymath_backend/harness/qa_pipeline.py → repo root 4단계
    # (harness/ops 공통 관용구 — crosslink_demotion_eval._repo_root·provenance_audit.
    # default_corpus_root와 동일 parents[4]).
    return Path(__file__).resolve().parents[4]


def _default_corpus_root(repo_root: Path) -> Path:
    return repo_root / "data" / "corpus"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """JSONL 파일 → dict 목록(빈 줄 무시) — concept_graph 테스트 conftest.py 로딩 관례 미러."""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


# ──────────────────────────────────────────────────────────────────────────
# 축 1 — corpus_audit: 문항 감사(커밋된 감사자 라벨 스냅샷 재검산)
# ──────────────────────────────────────────────────────────────────────────


def _axis_corpus_audit(repo_root: Path) -> AxisResult:
    """`docs/data/corpus_audit_*.jsonl` 스냅샷을 전수 발견해 결함율 상한을 재계산한다.

    이 입력은 코드가 자동 재생성하는 것이 아니라 *사람 감사자의 라벨링 산출물*이다.
    스냅샷 파일이 하나도 없으면 "no_snapshot"(정당한 상태 — 게이트 실패 아님)으로
    보고한다. 게이트는 이 축의 orchestrator 첫 도입에서 기존 CI를 갑자기 깨지 않도록
    `corpus_audit_eval` CLI 자체의 기본값(`--max-defect-upper` 기본 1.0 = off)과 동일한
    기준으로 두어 "ok"만 보고한다 — 결함율 상한 값 자체는 detail에 정직하게 노출하므로,
    후속 태스크에서 실측 기반 임계로 강화할 수 있다(이 축을 강하게 게이트하지 않는 근거).
    """
    snapshot_paths = sorted((repo_root / "docs" / "data").glob("corpus_audit_*.jsonl"))
    if not snapshot_paths:
        return AxisResult(
            measured=True, status="no_snapshot", detail={"snapshot_count": 0}
        )

    snapshots: dict[str, dict[str, float | int | None]] = {}
    for path in snapshot_paths:
        audit = corpus_audit_eval.load_audit(path.read_text(encoding="utf-8"))
        report = corpus_audit_eval.summarize(audit.labels)
        snapshots[path.name] = {
            "n": report.n,
            "defects": report.defects,
            "defect_rate_upper_bound": report.defect_rate_upper_bound(
                confidence=_CONFIDENCE
            ),
        }
    return AxisResult(
        measured=True,
        status="ok",
        detail={"snapshot_count": len(snapshot_paths), "snapshots": snapshots},
    )


# ──────────────────────────────────────────────────────────────────────────
# 축 2 — equivalence_canonicalize: 수식 동치(조건 DSL 폐쇄성)
# ──────────────────────────────────────────────────────────────────────────


# S3-28 — `condition_dsl_violation`은 *등식/부등식* 폐쇄 DSL(SymPy sympify로 파싱되는
# lhs op rhs)만 검증하도록 설계됐다(원 설계: `l3/equivalent/llm_generator.py`의 대수
# 조건 생성 축). 아래 answer_kind들은 각자 *독립된, 이미 닫힌* DSL을 쓴다 —
# `finite_probability`/`finite_count`는 `l3/finite_probability.py`의 정규식 기반
# `space=...; event=...` 문법(sympify 대상이 아님·전수 열거로 별도 검증), 나머지 넷은
# `l3/verify_answer.py`의 쉼표구분 숫자열 DSL(`verify_mean_equals_median` 등이
# `_parse_number_list`로 직접 파싱 — sympify하면 `sympy.Tuple`이 되어 `sympy.Expr`이
# 아니므로 필연적으로 위반 판정된다). 즉 코퍼스 결함이 아니라 이 축의 적용 범위가
# 넓었던 것(실측: 2647건 중 130건 전부 이 6종 — 나머지 2517건은 등식 DSL 그대로 통과).
# 새 판정 로직을 추가하는 게 아니라 이미 다른 파서로 닫힘이 보장된 answer_kind를
# *적용 대상에서 제외*한다(각자의 폐쇄성은 해당 verify_* 함수·전수 열거가 이미 보증).
_NON_EQUATION_DSL_ANSWER_KINDS = frozenset(
    {
        "finite_probability",
        "finite_count",
        "mean_equals_median",
        "events_independent",
        "conditional_equal",
        "dot_product_scalar",
    }
)


def _axis_equivalence_canonicalize(corpus_root: Path) -> AxisResult:
    """코퍼스 전 문제의 `conditions`에 폐쇄 검증 DSL 위반이 있는지 순회 검사한다.

    새 판정 로직이 아니라 기존 순수함수(`condition_dsl_violation`)를 코퍼스에 반복
    적용하는 것뿐이다(acceptance 위반 아님). `conditions` 필드는 스키마가 다양해
    레코드 최상위 또는 `verify.conditions`(실측 확인 — 현재 커밋 코퍼스는 전부
    `verify.conditions`에 있다) 양쪽을 방어적으로 읽고, 둘 다 없으면 스킵(에러로
    만들지 않는다). `answer_kind`가 `_NON_EQUATION_DSL_ANSWER_KINDS`에 속하면 이
    축의 검사 대상에서 제외한다(S3-28 — 등식 DSL 폐쇄성 검사이지 그 answer_kind의
    전용 DSL 폐쇄성은 각자의 파서가 이미 보증).
    """
    total = 0
    violations = 0
    for path in sorted(corpus_root.glob("problem_bank_*/problems.jsonl")):
        for problem in _load_jsonl(path):
            verify = problem.get("verify")
            verify = verify if isinstance(verify, dict) else {}
            answer_kind = verify.get("answer_kind") or problem.get("answer_kind")
            if answer_kind in _NON_EQUATION_DSL_ANSWER_KINDS:
                continue
            conditions = problem.get("conditions")
            if not isinstance(conditions, str):
                conditions = verify.get("conditions")
            if not isinstance(conditions, str) or not conditions.strip():
                continue
            total += 1
            if condition_dsl_violation(conditions) is not None:
                violations += 1
    status: AxisStatus = "ok" if violations == 0 else "gate_fail"
    return AxisResult(
        measured=True,
        status=status,
        detail={"total_conditions_checked": total, "violations": violations},
    )


# ──────────────────────────────────────────────────────────────────────────
# 축 3 — concept_graph_reachability: 원자 백본 그래프(atom_graph_v1)
# ──────────────────────────────────────────────────────────────────────────


def _axis_concept_graph_reachability(corpus_root: Path) -> AxisResult:
    """`atom_graph_v1` 커밋 코퍼스(런타임 진실원천)의 그래프 구조 무결성을 재검증한다.

    구 437 개념그래프는 S0-4b로 `legacy_snapshot`(non_runtime·audit_only)으로
    격하됐다(`tests/backend/l1/test_legacy_snapshot_governance.py`가 audit 화이트리스트
    밖 소비처를 막는다) — 이 축은 학생에게 실제로 나가는 원자 백본을 대상으로 한다.
    검증은 정본 함수 재사용(재구현 0) — `tests/data_pipeline/atom_graph/
    test_atom_corpus_governance.py`가 쓰는 것과 동일한 `_find_prerequisite_cycle` +
    dangling-endpoint 체크를 미러링한다(atom_graph_v1은 xlsx 원본 미커밋·이미 변환된
    `graph.json`만 커밋되어 `transform_dataset` 경로가 없다 — 위 테스트 선례와 동일하게
    `graph.json`을 직접 읽는다).
    """
    graph_path = corpus_root / "atom_graph_v1" / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    edges = [
        SimpleNamespace(
            relation=e["relation"], from_code=e["from_code"], to_code=e["to_code"]
        )
        for e in graph["edges"]
    ]
    cycle = _find_prerequisite_cycle(edges)

    codes = {c["code"] for c in graph["concepts"]}
    dangling: list[str] = []
    for e in graph["edges"]:
        if e["relation"] != AtomRelation.PREREQUISITE.value:
            continue
        if e["from_code"] not in codes:
            dangling.append(f"{e['from_code']}(from)")
        if e["to_code"] not in codes:
            dangling.append(f"{e['to_code']}(to)")

    success = cycle is None and not dangling
    status: AxisStatus = "ok" if success else "gate_fail"
    return AxisResult(
        measured=True,
        status=status,
        detail={
            "node_count": len(graph["concepts"]),
            "edge_count": len(graph["edges"]),
            "cycle": cycle,
            "dangling_count": len(dangling),
            "success": success,
        },
    )


# ──────────────────────────────────────────────────────────────────────────
# 축 4 — misconception_crosslink_demotion: 오개념 crosswalk
# ──────────────────────────────────────────────────────────────────────────


def _axis_misconception_crosslink_demotion() -> AxisResult:
    """crosswalk 강등전 셋(자체 라벨 불필요·self-contained)에 게이트를 돌려 측정한다.

    `crosslink_demotion_eval.main()`의 CLI 기본값과 동일한 조건으로 재현한다. 코퍼스·
    843 M-id 기본 경로는 그 값의 단일 진실 원천인 CLI 자신의 private 헬퍼
    (`_default_problem_corpora`/`_default_misconceptions`)를 그대로 재사용한다(경로
    구성 로직을 복제하면 CLI가 기본값을 바꿔도 이 오케스트레이터가 조용히 드리프트한다).
    게이트 판정도 CLI 소스의 `_CROSS_REJECT_FLOOR` 상수를 그대로 import해 하드코딩을
    피한다.
    """
    report, _trials = crosslink_demotion_eval.run(
        problem_corpora=crosslink_demotion_eval._default_problem_corpora(),
        misconceptions=crosslink_demotion_eval._default_misconceptions(),
        cross_per_positive=_CROSSLINK_CROSS_PER_POSITIVE,
        same_per_positive=_CROSSLINK_SAME_PER_POSITIVE,
    )
    cross_lower = report.cross_lower_bound(confidence=_CONFIDENCE)
    same_lower = report.same_lower_bound(confidence=_CONFIDENCE)
    gate_fail = (
        report.positive_false_reject > 0
        or cross_lower is None
        or cross_lower < crosslink_demotion_eval._CROSS_REJECT_FLOOR
    )
    status: AxisStatus = "gate_fail" if gate_fail else "ok"
    return AxisResult(
        measured=True,
        status=status,
        detail={
            "cross_lower_bound": cross_lower,
            "same_lower_bound": same_lower,
            "false_reject_count": report.positive_false_reject,
        },
    )


# ──────────────────────────────────────────────────────────────────────────
# 축 5 — coach_prose_leak: AI 출력 누설
# ──────────────────────────────────────────────────────────────────────────


def _axis_coach_prose_leak() -> AxisResult:
    """프로즈 플래그를 강제 ON한 뒤(CI와 동일 조건) 결함주입 시험지 노출률을 측정한다.

    `run_machine`은 내부에서 이미 `asyncio.run`을 호출하는 동기 함수라(코드 실측 확인)
    호출부에서 추가로 `asyncio.run`을 씌우지 않는다. `coach_prose_leak_eval.main()`이
    게이트 측정 전 `WHYMATH_WH1_PROSE_REPHRASE_ENABLED` 플래그를 강제하는 것과 동일한
    절차를 반복한다 — 그렇지 않으면 프로덕션 기본값(False·canary)에서 측정해 CI가
    검증하는 조건과 달라지는 사각이 생긴다. 종료 후 환경변수·설정 캐시를 원복한다
    (다른 축·테스트에 영향 없게).
    """
    previous = os.environ.get(_PROSE_FLAG_ENV)
    os.environ[_PROSE_FLAG_ENV] = "true"
    get_settings.cache_clear()
    try:
        cases = coach_prose_leak_eval.build_exam(_PROSE_N_PER_CELL)
        outcomes = coach_prose_leak_eval.run_machine(cases)
    finally:
        if previous is None:
            os.environ.pop(_PROSE_FLAG_ENV, None)
        else:
            os.environ[_PROSE_FLAG_ENV] = previous
        get_settings.cache_clear()

    report = coach_prose_leak_eval.summarize(outcomes)
    leak_upper = report.leak_upper_bound(confidence=_CONFIDENCE)
    false_block_upper = report.false_block_upper_bound(confidence=_CONFIDENCE)
    gate_fail = (
        leak_upper > _PROSE_MAX_LEAK_UPPER
        or false_block_upper > _PROSE_MAX_FALSE_BLOCK_UPPER
    )
    status: AxisStatus = "gate_fail" if gate_fail else "ok"
    return AxisResult(
        measured=True,
        status=status,
        detail={
            "leak_upper_bound": leak_upper,
            "false_block_upper_bound": false_block_upper,
        },
    )


# ──────────────────────────────────────────────────────────────────────────
# 축 6 — content_provenance: 저작권(ARCH-20)
# ──────────────────────────────────────────────────────────────────────────


def _axis_content_provenance(corpus_root: Path) -> AxisResult:
    """콘텐츠 출처·라이선스 집행 게이트(ARCH-20)의 `exit_code`를 그대로 게이트로 흡수한다."""
    report = provenance_audit.audit_corpus_root(corpus_root)
    status: AxisStatus = "ok" if report.exit_code == 0 else "gate_fail"
    return AxisResult(
        measured=True, status=status, detail={"exit_code": report.exit_code}
    )


# ──────────────────────────────────────────────────────────────────────────
# 축 7 — defect_injection_demotion: 결함주입 강등전
# ──────────────────────────────────────────────────────────────────────────


def _axis_defect_injection_demotion() -> AxisResult:
    """결함주입 강등전을 CI 게이트와 동일 파라미터(n=120/120·고정 시드·감사기 배선)로 재현한다.

    `with_auditor=True`가 필수다 — 없으면 검출 하한(0.95)을 넘지 못한다(발문-수식 정합
    감사기 없는 baseline은 statement_mismatch를 못 잡는다·`defect_detection_eval.py`
    모듈 docstring 정직성 원칙).
    """
    items = build_defect_seeded_set(
        n_defective=_DEFECT_N_DEFECTIVE, n_clean=_DEFECT_N_CLEAN, seed=_DEFECT_SEED
    )
    outcomes = defect_detection_eval._run_machine(items, with_auditor=True)
    report = defect_detection_eval.summarize(outcomes)
    detection_lower = report.detection_lower_bound(confidence=_CONFIDENCE)
    false_alarm_upper = report.false_alarm_upper_bound(confidence=_CONFIDENCE)
    gate_fail = (
        detection_lower is None
        or detection_lower < _DEFECT_MIN_DETECTION_LOWER
        or false_alarm_upper is None
        or false_alarm_upper > _DEFECT_MAX_FALSE_ALARM_UPPER
    )
    status: AxisStatus = "gate_fail" if gate_fail else "ok"
    return AxisResult(
        measured=True,
        status=status,
        detail={
            "detection_lower_bound": detection_lower,
            "false_alarm_upper_bound": false_alarm_upper,
        },
    )


# ──────────────────────────────────────────────────────────────────────────
# 조립 — 개별 격리 실행 + 집계 + 리포트
# ──────────────────────────────────────────────────────────────────────────


def _run_axis_safely(func: Callable[[], AxisResult], *, axis_name: str) -> AxisResult:
    """축 1개를 예외로부터 격리 실행 — 실패해도 나머지 축은 계속 실행된다.

    CLAUDE.md "침묵 실패 금지" — 예외를 삼키는 대신 타입명을 stderr 로그와 리포트
    detail 양쪽에 남긴다(시크릿·필드값은 노출하지 않음 — 타입명만).
    """
    try:
        return func()
    except (
        Exception
    ) as exc:  # noqa: BLE001 — 침묵 실패 금지(CLAUDE.md): 타입명을 반드시 로그.
        print(
            f"[qa_pipeline] 축 '{axis_name}' 실행 중 예외 — {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return AxisResult(
            measured=False, status="error", detail={"error_type": type(exc).__name__}
        )


def _aggregate_overall(axes: dict[str, AxisResult]) -> OverallResult:
    """전 축 상태 → 전체 판정(순수 함수 — 축 실행과 분리해 빠르게 단위테스트 가능하게).

    "no_snapshot"은 정당한 상태(스냅샷이 사람 감사 산출물이라 부재가 결함이 아님)라
    집계에서 제외한다. "gate_fail"·"error"만 실패로 집계한다.
    """
    failing = sorted(
        name for name, result in axes.items() if result.status in ("gate_fail", "error")
    )
    return OverallResult(passed=not failing, failing_axes=failing)


def build_report(corpus_root: Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    """8개(7 실행 + wilson.py는 그 내부 메커니즘) 기존 검사 자산을 조립해 QA JSON 리포트를 낸다.

    새 판정 로직 신설 0 — 전부 기존 함수 재사용. 각 축은 `_run_axis_safely`로 개별
    격리되어 한 축의 예외가 나머지 축 실행을 막지 않는다.
    """
    root = repo_root if repo_root is not None else _repo_root()

    axes: dict[str, AxisResult] = {
        "corpus_audit": _run_axis_safely(
            lambda: _axis_corpus_audit(root), axis_name="corpus_audit"
        ),
        "equivalence_canonicalize": _run_axis_safely(
            lambda: _axis_equivalence_canonicalize(corpus_root),
            axis_name="equivalence_canonicalize",
        ),
        "concept_graph_reachability": _run_axis_safely(
            lambda: _axis_concept_graph_reachability(corpus_root),
            axis_name="concept_graph_reachability",
        ),
        "misconception_crosslink_demotion": _run_axis_safely(
            _axis_misconception_crosslink_demotion,
            axis_name="misconception_crosslink_demotion",
        ),
        "coach_prose_leak": _run_axis_safely(
            _axis_coach_prose_leak, axis_name="coach_prose_leak"
        ),
        "content_provenance": _run_axis_safely(
            lambda: _axis_content_provenance(corpus_root),
            axis_name="content_provenance",
        ),
        "defect_injection_demotion": _run_axis_safely(
            _axis_defect_injection_demotion, axis_name="defect_injection_demotion"
        ),
    }
    overall = _aggregate_overall(axes)
    return {
        "corpus_root": str(corpus_root),
        "axes": {name: result.to_json() for name, result in axes.items()},
        "not_measured_axes": [dataclasses.asdict(axis) for axis in _NOT_MEASURED_AXES],
        "overall": overall.to_json(),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI — QA 리포트 조립 + Wilson 단측 경계 게이트. exit 0(전 축 통과)/1(하나라도 미달)."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.qa_pipeline",
        description=(
            "QA 파이프라인 오케스트레이터 — corpus_audit·수식동치·개념그래프·오개념crosswalk·"
            "코치프로즈누설·저작권·결함주입강등전 7개 기존 검사 자산을 조립해 단일 JSON "
            "리포트 + Wilson 단측 경계 게이트(exit 0/1)를 낸다(신규 검사기 신설 0)."
        ),
    )
    parser.add_argument(
        "--corpus-root",
        type=Path,
        default=None,
        help="코퍼스 루트 디렉터리(기본: 저장소 정본 data/corpus).",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="JSON 리포트 저장 경로(생략 시 stdout에 출력).",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    corpus_root = (
        args.corpus_root
        if args.corpus_root is not None
        else _default_corpus_root(repo_root)
    )

    report = build_report(corpus_root, repo_root=repo_root)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json is not None:
        args.json.write_text(text, encoding="utf-8")
        print(f"JSON 리포트 저장: {args.json}")
    else:
        print(text)

    overall_pass = bool(report["overall"]["pass"])
    return _EXIT_OK if overall_pass else _EXIT_GATE_FAIL


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
