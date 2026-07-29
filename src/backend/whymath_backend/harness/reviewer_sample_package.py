"""검수자용 샘플 문항 패키지 생성기 — 자체생성 동등문제 코퍼스의 *대표 표본* 검수 산출물.

수학 교육 검수 자문 1인이 자체 생성 동등문제 코퍼스(`data/corpus/problem_bank_generated_v0/
problems.jsonl` — 513문, S2-a 4종 게이트를 이미 통과해 적재됨) 전량을 볼 수는 없다. 이 CLI는
**결정론 층화 샘플링**으로 N(기본 30)문을 뽑아, 검수자가 한 화면에서 판단하도록 마크다운으로
렌더한다. `crosslink_review_aid`의 정본 패턴을 미러한다 — **근거를 모으기만 하고 판정하지 않는다**:
기계가 이미 통과시킨 항목은 ✓ 목록으로 *사실*을 보여주고, 교수학·저작권 최종 판단은 사람이 채울
*빈 체크박스*로 둔다(AI 자기승인 금지·검수 서명은 사람 몫).

**층화 축(결정론)**:
  ① `unit_codes` 도메인 비례배분(D'Hondt 최고평균·정수 교차곱 비교라 부동소수 모호성 0),
     **모든 도메인 최소 1문 강제**(저빈도 TRIG-VAL 13·LOG-EQ 20 등도 반드시 포함).
  ② **객관식 오개념 4종 각 ≥1문**(factor-sign-flip·opposite-root-selected·
     extremum-value-vs-point-confused·extremum-max-min-confused) — 해당 오개념을 실은 문제를
     소속 도메인 선택에 seed로 강제 포함.
  ③ 도메인 내 나머지는 난이도·발문형식에 걸쳐 균등 stride로 분산.

**결정론 필수(바이트 재현)**: `random`/시각/환경 의존 0. `problem_id` 정렬 기반 안정 선택 —
같은 코퍼스·같은 N이면 산출 마크다운이 바이트까지 같다(테스트 봉인). 순수 함수·DB 0·LLM 0.

**저작권 안전선**: 코퍼스는 전건 자체생성(`source_type=자체생성`·`license=WHYMATH_GENERATED`·
`generation_type=FULLY_GENERATED`)이라 평가원/EBS/교과서 본문을 애초에 보유하지 않는다. 렌더는
코퍼스에 실린 자체 저작 텍스트만 옮기며 외부 원문을 인용하지 않는다(licensing_safety §109-112·125).

사용법:
    python -m whymath_backend.harness.reviewer_sample_package --n 30 \\
        [--corpus <jsonl>] [--out docs/data/reviewer_sample_30_v0.md]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

__all__ = [
    "REQUIRED_MISCONCEPTIONS",
    "DistractorEntry",
    "SampleCoverage",
    "SampleProblem",
    "allocate_quota",
    "load_sample_corpus",
    "main",
    "render_markdown",
    "select_sample",
    "summarize_sample",
]

# 객관식 distractor에 태깅되는 오개념 4종(kebab) — 표본이 각 ≥1문 포함해야 하는 강제 대상.
# 코퍼스 실측: QUAD-EQ 객관식 1문이 (factor-sign-flip·opposite-root-selected) 2종을 동시에,
# CALC-EXTREMUM-MC 1문이 (extremum-max-min-confused·extremum-value-vs-point-confused) 2종을
# 동시에 실는다 — 따라서 두 도메인에서 각 1문만 골라도 4종 전부 커버된다.
REQUIRED_MISCONCEPTIONS: tuple[str, ...] = (
    "extremum-max-min-confused",
    "extremum-value-vs-point-confused",
    "factor-sign-flip",
    "opposite-root-selected",
)

# CLI 기본값 — 레포 루트 기준(ops가 루트에서 무경로 실행·problem_corpus_batch 규약 미러).
_DEFAULT_N = 30
_DEFAULT_CORPUS_REL = "data/corpus/problem_bank_generated_v0/problems.jsonl"
_DEFAULT_OUT_REL = "docs/data/reviewer_sample_30_v0.md"


class DistractorEntry(BaseModel):
    """객관식 오답 선지 1개의 오개념 태깅 — `choice_index`(0-기준·choices 인덱스)·오개념·op-code.

    `op_code`는 정본 `schema.problem.DistractorEntry`와 동일하게 *선택*이다(None=op-code 미상·
    오개념만 매핑). 필수로 두면 op_code 없는 코퍼스(misconception_mc·conceptual_v0)에서 표본
    생성이 통째로 죽는다 — 2026-07-29 S3-09 실측 결함의 교정.
    """

    model_config = ConfigDict(extra="ignore")

    choice_index: int
    misconception_id: str
    op_code: str | None = None


class SampleProblem(BaseModel):
    """코퍼스 1행의 *검수 유의미* 부분집합 — 표본 선택·렌더에 쓰는 필드만(`extra="ignore"`).

    코퍼스 레코드는 34~36필드지만 검수자가 판단할 것만 담는다(스키마 결합 최소화·
    crosslink_review_aid의 `MisconceptionCorpusEntry` 선례). `problem_id`가 안정 정렬 키다.
    """

    model_config = ConfigDict(extra="ignore")

    problem_id: str
    slug: str
    unit_codes: list[str]
    question_format: str
    answer_format: str
    question_text: str
    answer: str
    answer_explanation: str | None = None
    difficulty_overall: float
    achievement_standard_codes: list[str] = []
    license: str
    source_type: str
    generation_type: str
    choices: list[str] | None = None
    distractor_map: list[DistractorEntry] = []
    verify: dict[str, object] | None = None

    @property
    def domain(self) -> str:
        """층화 축 — `unit_codes` 정렬 결합(현 코퍼스는 전건 단일 코드지만 다중도 안정 처리)."""
        return "+".join(sorted(self.unit_codes)) if self.unit_codes else "(미분류)"

    @property
    def misconception_ids(self) -> frozenset[str]:
        """이 문제의 distractor에 태깅된 오개념 집합(단답형은 공집합)."""
        return frozenset(d.misconception_id for d in self.distractor_map)


class SampleCoverage(BaseModel):
    """표본 커버리지 요약 — 도메인·발문형식·오개념·난이도 분포(검수 착수 전 규모 파악·테스트 단언).

    판정이 아니라 표본이 *무엇을 담았는지*의 사실 집계다(문서 머리말·마지막 줄 요약에 쓰인다).
    """

    model_config = ConfigDict(extra="forbid")

    n: int
    corpus_size: int
    domain_counts: dict[str, int]
    format_counts: dict[str, int]
    misconception_counts: dict[str, int]
    difficulty_min: float
    difficulty_max: float
    missing_required_misconceptions: list[str]
    """강제 오개념 4종 중 표본에 없는 것(정렬) — 비어야 정상(층화 위반 검출 신호)."""


# ──────────────────────────────────────────────────────────────────────────
# 로드 (JSONL → 검증된 SampleProblem — 순수·저작권 위생 재확인)
# ──────────────────────────────────────────────────────────────────────────
def load_sample_corpus(text: str) -> list[SampleProblem]:
    """코퍼스 JSONL 텍스트 → `SampleProblem` 목록(빈 줄 관대·행별 검증).

    저작권 위생 재확인: 자체생성이 아닌 행(`source_type != 자체생성` 또는 `license !=
    WHYMATH_GENERATED`)은 `ValueError`로 거부한다 — 렌더가 외부 원문을 실을 통로를 원천 차단
    (조용한 통과 금지·populate 위생 규약 미러). `problem_id` 중복도 `ValueError`(정렬 키 무결성).
    """
    import json

    problems: list[SampleProblem] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        problem = SampleProblem.model_validate(json.loads(stripped))
        if problem.source_type != "자체생성" or problem.license != "WHYMATH_GENERATED":
            raise ValueError(
                f"저작권 위생 위반: slug={problem.slug} source_type={problem.source_type!r} "
                f"license={problem.license!r} — 자체생성 코퍼스만 검수 표본 대상이다."
            )
        if problem.problem_id in seen:
            raise ValueError(f"코퍼스 중복 problem_id: {problem.problem_id}(안정 정렬 키 위반)")
        seen.add(problem.problem_id)
        problems.append(problem)
    return problems


# ──────────────────────────────────────────────────────────────────────────
# 층화 샘플링 (결정론 — 도메인 비례 + 오개념 강제 + 난이도·형식 분산)
# ──────────────────────────────────────────────────────────────────────────
def _rotation_key(problem_id: str, rotation: int) -> str:
    """표본 회전(S2-11)의 안정 선택 키 — rotation=0이면 항등(기존 산출물 바이트 불변).

    rotation>0이면 problem_id를 salt와 함께 해시해 *선택 순서*만 결정론적으로 재배열한다.
    verdict-blind(이전 검수 결과와 무관)·같은 rotation이면 바이트 재현. 결함 교정 후 같은
    표본 재채점 금지 규약(초인간 검증 표준 §S5 재채점 금지)의 재추출 메커니즘이다 —
    disjoint 보장은 아니나 선택이 이전 판정에 오염되지 않는 독립 추출이다.
    """
    if rotation == 0:
        return problem_id
    return hashlib.sha256(f"rot{rotation}:{problem_id}".encode()).hexdigest()


def allocate_quota(counts: Mapping[str, int], n: int) -> dict[str, int]:
    """도메인별 표본 쿼터 — 모든 도메인 최소 1 + 나머지 D'Hondt 최고평균 비례배분(순수·결정론).

    ① 모든 도메인에 1을 선지급(저빈도 도메인 강제 포함). ② 남은 슬롯은 D'Hondt로 한 자리씩,
    다음 몫 `count/(quota+1)`이 최대인 도메인에 준다 — **정수 교차곱**으로 비교해 부동소수 모호성을
    제거하고, 동점은 도메인명 오름차순(먼저가 이김)으로 깨 완전 결정론이다. 쿼터는 도메인 가용
    문항 수를 넘지 못한다(cap). `n`이 도메인 수보다 작으면 `ValueError`(모든 도메인 1 보장 불가).
    """
    domains = sorted(counts)
    if n < len(domains):
        raise ValueError(f"N({n})이 도메인 수({len(domains)})보다 작아 도메인당 1문 보장 불가")
    quota: dict[str, int] = {d: 1 for d in domains}
    remaining = n - len(domains)
    for _ in range(remaining):
        best: str | None = None
        for d in domains:
            if quota[d] >= counts[d]:  # cap — 가용 문항 초과 배정 금지
                continue
            # count_d/(quota_d+1) > count_best/(quota_best+1) ⇔ 교차곱(정수·정확)
            if best is None or counts[d] * (quota[best] + 1) > counts[best] * (quota[d] + 1):
                best = d
        if best is None:  # 전 도메인 cap 도달(가용 < n) — 더 배정 불가
            break
        quota[best] += 1
    return quota


def _even_stride_indices(length: int, k: int) -> list[int]:
    """길이 `length` 리스트에서 `k`개를 균등 간격으로 뽑는 인덱스(정수·결정론·중복 없음).

    idx = ((2i+1)·length)//(2k) — 각 구간 중앙점. k ≤ length면 순증가·상이하다(난이도 정렬 위에
    적용하면 난이도 전 구간 분산). k ≥ length면 전체 인덱스를 반환한다.
    """
    if k <= 0:
        return []
    if k >= length:
        return list(range(length))
    return [((2 * i + 1) * length) // (2 * k) for i in range(k)]


def _select_within_domain(
    problems: Sequence[SampleProblem], quota: int, seeds: frozenset[str], rotation: int = 0
) -> list[SampleProblem]:
    """도메인 1개에서 `quota`문 선택 — 오개념 seed 강제 포함 + 나머지 난이도·형식 stride 분산.

    seed(오개념 커버용 problem_id)를 먼저 확정하고, 나머지는 (난이도·발문형식·선택키) 정렬
    위에서 균등 stride로 뽑는다. seed가 쿼터보다 많으면 선택키 순 앞에서 자른다(안전).
    rotation은 선택키만 재배열(S2-11 표본 회전) — 0이면 기존과 바이트 동일.
    """
    by_id = sorted(problems, key=lambda p: _rotation_key(p.problem_id, rotation))
    seeded = [p for p in by_id if p.problem_id in seeds]
    if len(seeded) >= quota:
        return seeded[:quota]
    rest = [p for p in by_id if p.problem_id not in seeds]
    rest.sort(
        key=lambda p: (
            p.difficulty_overall,
            p.question_format,
            _rotation_key(p.problem_id, rotation),
        )
    )
    picks = _even_stride_indices(len(rest), quota - len(seeded))
    chosen = seeded + [rest[i] for i in picks]
    return sorted(chosen, key=lambda p: p.problem_id)


def _misconception_seeds(
    problems: Iterable[SampleProblem], rotation: int = 0
) -> dict[str, set[str]]:
    """강제 오개념 4종 → 소속 도메인의 seed problem_id 집합(결정론).

    각 오개념에 대해 그것을 실은 첫 문제(선택키 최소·rotation 반영)를 골라 그 도메인의 seed로
    등록한다 — 한 문제가 2종을 동시에 실으면 seed 1건이 2종을 커버한다(코퍼스 실측 구조).
    """
    seeds: dict[str, set[str]] = collections.defaultdict(set)
    for mis_id in REQUIRED_MISCONCEPTIONS:
        carriers = sorted(
            (p for p in problems if mis_id in p.misconception_ids),
            key=lambda p: _rotation_key(p.problem_id, rotation),
        )
        if carriers:
            first = carriers[0]
            seeds[first.domain].add(first.problem_id)
    return seeds


def select_sample(
    problems: Sequence[SampleProblem], n: int, *, rotation: int = 0
) -> list[SampleProblem]:
    """코퍼스 → N문 결정론 층화 표본(도메인 비례 + 오개념 강제 + 난이도·형식 분산).

    반환 순서: 도메인 랭크(빈도 내림차순·동빈도는 도메인명) → problem_id. 같은 (코퍼스·N·
    rotation)이면 바이트까지 재현된다(정렬만 사용·난수 0). rotation>0은 S2-11 표본 회전 —
    결함 교정 후 같은 표본 재채점 대신 신규 독립 표본을 재추출한다(선택키 salt 재배열·
    verdict-blind·rotation=0은 기존 산출물 바이트 불변). `n`이 전체 이상이면 전건 반환.
    """
    if n >= len(problems):
        return sorted(problems, key=lambda p: p.problem_id)
    by_domain: dict[str, list[SampleProblem]] = collections.defaultdict(list)
    for p in problems:
        by_domain[p.domain].append(p)
    counts = {d: len(ps) for d, ps in by_domain.items()}
    quota = allocate_quota(counts, n)
    seeds = _misconception_seeds(problems, rotation)

    selected: list[SampleProblem] = []
    for domain in by_domain:
        selected.extend(
            _select_within_domain(
                by_domain[domain], quota[domain], frozenset(seeds.get(domain, set())), rotation
            )
        )
    domain_rank = {d: (-counts[d], d) for d in counts}
    selected.sort(key=lambda p: (domain_rank[p.domain], p.problem_id))
    return selected


def summarize_sample(sample: Sequence[SampleProblem], *, corpus_size: int) -> SampleCoverage:
    """표본 → 커버리지 요약(도메인·형식·오개념·난이도 분포·강제 오개념 누락 검출)."""
    domain_counts = collections.Counter(p.domain for p in sample)
    format_counts = collections.Counter(p.question_format for p in sample)
    misconception_counts: collections.Counter[str] = collections.Counter()
    for p in sample:
        misconception_counts.update(p.misconception_ids)
    difficulties = [p.difficulty_overall for p in sample] or [0.0]
    present = set(misconception_counts)
    missing = sorted(m for m in REQUIRED_MISCONCEPTIONS if m not in present)
    return SampleCoverage(
        n=len(sample),
        corpus_size=corpus_size,
        domain_counts=dict(sorted(domain_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        format_counts=dict(sorted(format_counts.items())),
        misconception_counts=dict(sorted(misconception_counts.items())),
        difficulty_min=min(difficulties),
        difficulty_max=max(difficulties),
        missing_required_misconceptions=missing,
    )


# ──────────────────────────────────────────────────────────────────────────
# 렌더 (마크다운 — 기계 ✓ 사실 + 사람 판단 공란·판정 없음)
# ──────────────────────────────────────────────────────────────────────────
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"


def _circled(idx: int) -> str:
    """0-기준 인덱스 → 원문자(표시용 1-기준). 범위 밖이면 `(n)` 형태."""
    return _CIRCLED[idx] if 0 <= idx < len(_CIRCLED) else f"({idx + 1})"


def _format_verify(verify: Mapping[str, object] | None) -> str:
    """verify(SymPy 입력) 요약 한 줄 — conditions·answer_map·answer_selection."""
    if not verify:
        return "(verify 없음)"
    conditions = verify.get("conditions", "")
    answer_map = verify.get("answer_map", {})
    parts = [f"conditions: `{conditions}`"]
    if isinstance(answer_map, Mapping) and answer_map:
        pairs = ", ".join(f"{k}={v}" for k, v in answer_map.items())
        parts.append(f"answer_map: {{{pairs}}}")
    selection = verify.get("answer_selection")
    if selection:
        parts.append(f"근 선택: {selection}")
    return " · ".join(parts)


def _format_choices(problem: SampleProblem) -> list[str]:
    """객관식 선지 + 오답↔오개념(op-code) 표시. 단답형이면 빈 리스트."""
    if problem.question_format != "객관식" or not problem.choices:
        return []
    distractor_by_idx = {d.choice_index: d for d in problem.distractor_map}
    lines = ["", "**선지**:"]
    for i, choice in enumerate(problem.choices):
        marker = _circled(i)
        entry = distractor_by_idx.get(i)
        if entry is None:
            lines.append(f"- {marker} `{choice}` ← 정답")
        else:
            op_suffix = f" (op: `{entry.op_code}`)" if entry.op_code else ""
            lines.append(
                f"- {marker} `{choice}` ← 오답 · 오개념 `{entry.misconception_id}`{op_suffix}"
            )
    return lines


def _machine_checklist(problem: SampleProblem) -> list[str]:
    """기계가 이미 통과시킨 항목(✓·사실). 코퍼스 적재=S2-a 4종 게이트 통과라 전건 ✓.

    **명시적 `verify_status` 필드는 없다** — "코퍼스에 실려 있음 = 게이트 통과"가 곧 상태다
    (머리말 정직성 주의와 정합). 판정이 아니라 기계가 무엇을 검증했는지의 사실 목록이다.
    """
    tier2 = (
        "solution_steps 有"
        if (problem.verify and problem.verify.get("solution_steps"))
        else "단일 답 동치"
    )
    return [
        "",
        "**기계 검증 완료** (코퍼스 적재 = S2-a 4종 게이트 통과 · 별도 `verify_status` 필드 없음):",
        "- ✓ 정확성 Tier1 — SymPy 답 검산 (verify.answer_map 대조)",
        f"- ✓ 정확성 Tier2 — SymPy 단계 동치 ({tier2})",
        "- ✓ 위생 — 거짓 수치등식 부재",
        "- ✓ 동등성 — 분류 게이트 통과",
        "- ✓ 과유사 dedup — 코사인 0.97 + 구조 signature 미충돌",
        "- ✓ 저작권 불변식 — source_type=자체생성 · license=WHYMATH_GENERATED",
    ]


def _human_checklist(problem: SampleProblem) -> list[str]:
    """사람(검수 자문)이 채울 빈 체크박스 6항 — 기계가 판정 못 하는 교수학·귀속·저작권 최종 판단.

    ⑤ 오답↔오개념 귀속은 객관식만 유효(단답형은 오개념 태그 자체가 없다·머리말 정직성 주의).
    """
    item5 = (
        "[ ] ⑤ 오답↔오개념 귀속 타당(선지별 오개념·op-code)"
        if problem.question_format == "객관식"
        else "해당없음 ⑤ (단답형 — 오개념 태그 없음)"
    )
    return [
        "",
        "**사람 판단** (검수 자문 — 아래 공란을 채운다·이 도구는 판정하지 않음):",
        "- [ ] ① 발문 자연스러움(한국어·수학 표기)",
        "- [ ] ② 풀이 타당성(answer_explanation 논리)",
        "- [ ] ③ 난이도 체감이 표기 난이도와 정합",
        "- [ ] ④ 성취기준 귀속 타당",
        f"- {item5}",
        "- [ ] ⑥ 평가원/교과서와의 우연 유사 없음(저작권)",
    ]


def _format_problem(problem: SampleProblem, ordinal: int) -> list[str]:
    """표본 1문 블록 — 메타 + 문항 + 정답/풀이 + verify + (객관식)선지 + 기계 ✓ + 사람 공란."""
    standards = ", ".join(problem.achievement_standard_codes) or "(없음)"
    lines = [
        f"## 표본 {ordinal:02d} · `{problem.slug}`",
        "",
        f"- 도메인: `{problem.domain}` · 발문형식: {problem.question_format} "
        f"· 정답형식: {problem.answer_format} · 난이도: {problem.difficulty_overall:g}",
        f"- 성취기준: {standards}",
        "",
        f"**문항**: {problem.question_text}",
        "",
        f"**정답**: `{problem.answer}`",
    ]
    if problem.answer_explanation:
        lines += ["", f"**풀이**: {problem.answer_explanation}"]
    lines += ["", f"**verify(SymPy 입력)**: {_format_verify(problem.verify)}"]
    lines += _format_choices(problem)
    lines += _machine_checklist(problem)
    lines += _human_checklist(problem)
    lines += ["", "---"]
    return lines


def _format_header(coverage: SampleCoverage) -> list[str]:
    """문서 머리말 — 저작권 보증 + 정직성 주의 + 검수 서명란 + 커버리지 요약."""
    domain_line = " · ".join(f"{d} {c}" for d, c in coverage.domain_counts.items())
    format_line = " · ".join(f"{f} {c}" for f, c in coverage.format_counts.items())
    mis_line = " · ".join(f"{m} {c}" for m, c in coverage.misconception_counts.items())
    return [
        "# 검수자용 샘플 문항 패키지 (자체생성 동등문제 코퍼스 v0)",
        "",
        f"> 전체 코퍼스 {coverage.corpus_size}문에서 결정론 층화 샘플링으로 뽑은 대표 표본 "
        f"{coverage.n}문. 같은 코퍼스·N이면 바이트까지 재현된다(난수 0·정렬 기반).",
        "",
        "## 저작권 보증",
        "",
        "이 표본의 전건은 **자체생성**(`source_type=자체생성` · `license=WHYMATH_GENERATED` · "
        "`generation_type=FULLY_GENERATED`)이다. 코퍼스는 성취기준 + 구조 signature만으로 "
        "결정론 생성됐으며 **평가원·EBS·검정 교과서 본문을 애초에 보유하지 않는다**(본문 미보유). "
        "사실·구조 정보는 저작권 대상이 아니라는 근거"
        "(`docs/data/licensing_safety.md` §109-112·§125) 위에 선다.",
        "",
        "## 정직성 주의 (검수자 유의)",
        "",
        "- **단답형에는 오개념 태그가 없다** — 오답↔오개념 귀속 검수(사람 판단 ⑤)는 "
        "객관식에만 유효.",
        "- **외부 저작물 대비 유사도 검사 산출물은 부재하다** — 저작권 보증은 유사도 스캔이 아니라 "
        "*생성 방식*(본문 미보유·성취기준+시그니처 결정론 생성) 근거다. 사람 판단 ⑥(우연 유사)이 "
        "이 공백을 메운다.",
        '- **명시적 `verify_status` 필드는 없다** — 기계 검증 ✓는 "코퍼스에 적재됨 = S2-a 게이트 '
        '통과"라는 사실을 표시할 뿐, 별도 상태 필드를 읽은 것이 아니다.',
        "",
        "## 검수 서명란",
        "",
        "검수자는 각 표본의 사람 판단 공란을 채운 뒤 아래에 서명한다.",
        "",
        "- 상태(택1): `pending` / `approved` / `rejected` / `deferred`",
        "- 서명: `검수:{reviewer} {reviewed_on}` (예 `검수:홍길동 2026-07-08`)",
        "",
        "## 표본 커버리지",
        "",
        f"- 도메인: {domain_line}",
        f"- 발문형식: {format_line}",
        f"- 객관식 오개념: {mis_line or '(없음)'}",
        f"- 난이도 범위: {coverage.difficulty_min:g} ~ {coverage.difficulty_max:g}",
        f"- 강제 오개념 누락: {coverage.missing_required_misconceptions or '없음(4종 전부 포함)'}",
        "",
        "---",
    ]


def render_markdown(sample: Sequence[SampleProblem], *, corpus_size: int) -> str:
    """표본 → 검수자용 마크다운 문서(머리말 + 문항 블록 + 마지막 줄 JSON 커버리지 요약).

    **판정하지 않는다**: 기계 ✓는 사실, 교수학·저작권 판단은 사람 공란(crosslink_review_aid 동형).
    마지막 줄은 파싱 가능한 커버리지 JSON(스냅샷·회귀).
    """
    coverage = summarize_sample(sample, corpus_size=corpus_size)
    lines = _format_header(coverage)
    for ordinal, problem in enumerate(sample, start=1):
        lines.append("")
        lines.extend(_format_problem(problem, ordinal))
    lines += ["", "<!-- coverage: " + coverage.model_dump_json() + " -->"]
    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
def _repo_root() -> Path:
    """레포 루트 — harness→whymath_backend→backend→src→repo(problem_corpus_batch와 동일 규약)."""
    return Path(__file__).resolve().parents[4]


def _run(corpus_path: Path, out_path: Path, n: int, rotation: int = 0) -> int:
    """코퍼스 읽어 표본 마크다운 기록. 파일 부재는 exit 2(조용한 무동작 금지)."""
    if not corpus_path.exists():
        print(f"코퍼스 없음: {corpus_path}")
        return 2
    problems = load_sample_corpus(corpus_path.read_text(encoding="utf-8"))
    sample = select_sample(problems, n, rotation=rotation)
    markdown = render_markdown(sample, corpus_size=len(problems))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    coverage = summarize_sample(sample, corpus_size=len(problems))
    print(
        f"표본 {coverage.n}/{coverage.corpus_size}문 기록 → {out_path} · "
        f"도메인 {len(coverage.domain_counts)}종 · 오개념 {len(coverage.misconception_counts)}종 · "
        f"누락 {coverage.missing_required_misconceptions or '없음'}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 코퍼스 → 검수자용 표본 마크다운. 0=성공·2=코퍼스 부재."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.reviewer_sample_package",
        description=(
            "자체생성 동등문제 코퍼스에서 결정론 층화 표본을 뽑아 검수자용 마크다운을 만든다 "
            "(도메인 비례 + 저빈도 강제 + 오개념 4종 강제 + 난이도·형식 분산·판정 없음)."
        ),
    )
    parser.add_argument(
        "--n", type=int, default=_DEFAULT_N, help=f"표본 문항 수(기본 {_DEFAULT_N})."
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=None,
        help=f"코퍼스 JSONL 경로(기본 {_DEFAULT_CORPUS_REL}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"산출 마크다운 경로(기본 {_DEFAULT_OUT_REL}).",
    )
    parser.add_argument(
        "--rotation",
        type=int,
        default=0,
        help="표본 회전 인덱스(S2-11 — 교정 후 재판정은 신규 회전으로 독립 재추출. 기본 0=초판).",
    )
    args = parser.parse_args(argv)
    corpus_path = args.corpus if args.corpus is not None else _repo_root() / _DEFAULT_CORPUS_REL
    out_path = args.out if args.out is not None else _repo_root() / _DEFAULT_OUT_REL
    return _run(corpus_path, out_path, args.n, rotation=args.rotation)


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
