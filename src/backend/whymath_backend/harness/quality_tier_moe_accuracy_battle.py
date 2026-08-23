"""QUALITY 티어 dense 27B ↔ MoE 정확도 축 강등전 (OPS-48).

`qwen3.5:27b`(dense·현 QUALITY)와 `qwen3:30b-a3b`(MoE·후보)를 **같은 결함 주입 시험지**로
대조한다. 시험지는 `l3/equivalent/defect_seeder`가 결정론으로 만들며, 정답지(defect_class)
는 우리가 100% 안다. 두 모델에게 각 문항의 결함 여부를 묻고, 검출률·오경보율을 Wilson 단측
경계로 계산한다.

판정 원칙:
  - 속도가 6배여도 검출률이 떨어지거나 오경보가 높아지면 채택하지 않는다.
  - "인상"이 아니라 Wilson 단측 경계 + CLI exit 0/1.
  - 20%p 미만 차이는 "유의하다"고 하지 않는다(이전 세션 재현성 8~18%).

사용(Phaiakes9):
    python -m whymath_backend.harness.quality_tier_moe_accuracy_battle \
        --baseline-model qwen3.5:27b --candidate-model qwen3:30b-a3b \
        --n-defective 70 --n-clean 70 --audit-out data/audit/ops-48

게이트:
    --min-detection-lower 0.75 --max-false-alarm-upper 0.10
    --require-candidate-not-worse-than-baseline
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.l3.equivalent.defect_seeder import (
    DEFECT_CLASSES,
    DefectClass,
    SeededItem,
    build_defect_seeded_set,
)
from whymath_backend.l3.models import (
    CostTier,
    GenerationResult,
    LocalModelTier,
    RoutingDecision,
)
from whymath_backend.l3.providers.ollama import FixedModelOllamaProvider, _OllamaClient

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1
_EXIT_INPUT_ERROR = 2


class _ParsedVerdict(BaseModel):
    """LLM이 낸 결함 판정 — has_defect는 필수, defect_class는 선택."""

    model_config = ConfigDict(extra="forbid")

    has_defect: bool = Field(..., description="결함이 있는가?")
    defect_class: str | None = Field(
        default=None,
        description=f"결함 유형 — {DEFECT_CLASSES} 중 하나 또는 null/unknown.",
    )
    reason: str | None = Field(default=None, description="판정 근거(진단용).")


class ModelOutcome(BaseModel):
    """한 모델이 한 문항에 대해 내 판정 + 정답지 + 측정값."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_id: str = Field(description="호출한 Ollama 모델 ID.")
    slug: str = Field(description="문항 slug.")
    ground_truth: DefectClass | None = Field(description="정답지(None=무결함).")
    detected: bool = Field(description="모델이 '결함 있음'이라고 했는가.")
    predicted_class: str | None = Field(description="모델이 말한 결함 유형(파싱된 경우).")
    parsed: bool = Field(description="응답 파싱 성공 여부.")
    parse_error: str | None = Field(default=None, description="파싱/호출 오류 기록.")
    latency_ms: float | None = Field(default=None, description="해당 호출 실측 지연(ms).")
    input_tokens: int | None = Field(default=None)
    output_tokens: int | None = Field(default=None)
    raw_response: str = Field(default="", description="모델 원시 응답(디버그·감사용).")


@dataclass(slots=True, frozen=True)
class DetectionMetrics:
    """이진 검출 메트릭 — Wilson 경계 포함."""

    true_positives: int
    false_negatives: int
    false_positives: int
    true_negatives: int
    unresolved: int

    @property
    def defective_total(self) -> int:
        return self.true_positives + self.false_negatives

    @property
    def clean_total(self) -> int:
        return self.false_positives + self.true_negatives

    @property
    def detection_rate(self) -> float | None:
        if self.defective_total == 0:
            return None
        return self.true_positives / self.defective_total

    @property
    def false_alarm_rate(self) -> float | None:
        if self.clean_total == 0:
            return None
        return self.false_positives / self.clean_total

    def detection_lower_bound(self, confidence: float = 0.95) -> float | None:
        if self.defective_total == 0:
            return None
        return wilson_lower_bound(self.true_positives, self.defective_total, confidence)

    def false_alarm_upper_bound(self, confidence: float = 0.95) -> float | None:
        if self.clean_total == 0:
            return None
        return wilson_upper_bound(self.false_positives, self.clean_total, confidence)


class ModelReport(BaseModel):
    """한 모델의 전체 리포트."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_id: str
    n_items: int
    metrics: DetectionMetrics
    latency_ms: dict[str, float | None]
    per_class: dict[str, tuple[int, int]]  # defect_class → (detected, total)


class BattleReport(BaseModel):
    """두 모델 대조 리포트."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline: ModelReport
    candidate: ModelReport
    n_defective: int
    n_clean: int
    seed: int
    confidence: float
    baseline_model_id: str
    candidate_model_id: str


# ──────────────────────────────────────────────────────────────────────────
# 프롬프트 / JSON schema
# ──────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """당신은 중·고등학생용 수학 학습 앱의 문항 품질 검수자입니다.
주어진 문항에 결함이 있는지 판정하고, 반드시 JSON 형식으로만 답하세요.

결함 유형:
- answer_error: 정답이 계산상 틀림
- explanation_slip: 해설에 거짓 수치/등식이 섞임
- condition_mismatch: 조건식이 변조되어 제시된 정답이 실제 해가 아님
- standard_tag_error: 성취기준 코드가 잘못 붙음
- distractor_misattribution: 객관식 오답 선지가 잘못된 오개념에 귀속됨
- statement_mismatch: 발문의 수식/문장과 검산 조건이 서로 다름
- broken_latex: LaTeX 수식 표기가 깨짐(중괄호 짝 불일치 등)

응답 형식(반드시 JSON만, 설명은 40자 이내 한 문장):
{"has_defect": true/false, "defect_class": "answer_error" 또는 null, "reason": "짧은 근거"}

- JSON 외 텍스트를 쓰지 마세요.
- reason은 40자 이내 한 문장으로만 쓰세요.
- has_defect가 false면 defect_class는 null로 하세요.
- "그러나" "따라서" 같은 접속어를 반복해 길게 설명하지 마세요."""


def _format_item(item: SeededItem) -> str:
    """SeededItem → LLM 프롬프트 본문."""
    problem = item.candidate.problem
    lines: list[str] = []
    lines.append(f"[문항 slug] {problem.slug}")
    lines.append(f"[발문] {problem.question_text}")
    if problem.choices:
        lines.append("[선택지]")
        for idx, choice in enumerate(problem.choices, start=1):
            lines.append(f"  {idx}. {choice}")
    lines.append(f"[정답] {problem.answer}")
    if problem.answer_explanation:
        lines.append(f"[해설] {problem.answer_explanation}")
    if problem.achievement_standard_codes:
        lines.append(f"[성취기준] {', '.join(problem.achievement_standard_codes)}")
    if problem.distractor_map:
        lines.append("[오답 오개념]")
        for entry in problem.distractor_map:
            lines.append(f"  choices[{entry.choice_index}]: {entry.misconception_id}")
    return "\n".join(lines)


_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "has_defect": {"type": "boolean"},
        "defect_class": {"type": ["string", "null"]},
        "reason": {"type": ["string", "null"], "maxLength": 80},
    },
    "required": ["has_defect"],
}


_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _parse_response(text: str) -> tuple[_ParsedVerdict, bool, str]:
    """원시 응답 → ParsedVerdict. (verdict, parsed_ok, parse_error)."""
    if not text:
        return _ParsedVerdict(has_defect=False), False, "empty response"

    # 1) JSON schema format 사용 시 응답 자체가 JSON.
    # 2) 자유 텍스트 + 코드펜스 fallback.
    candidates: list[str] = []
    candidates.append(text.strip())
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_match:
        candidates.append(code_match.group(1))
    for m in _JSON_RE.finditer(text):
        candidates.append(m.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        has_defect = data.get("has_defect")
        if not isinstance(has_defect, bool):
            # "true"/"false" 문자열이라도 받아들인다.
            if isinstance(has_defect, str):
                has_defect = has_defect.strip().lower() == "true"
            else:
                continue
        defect_class = data.get("defect_class")
        if defect_class is not None and not isinstance(defect_class, str):
            defect_class = None
        reason = data.get("reason")
        if reason is not None and not isinstance(reason, str):
            reason = None
        return (
            _ParsedVerdict(
                has_defect=has_defect,
                defect_class=defect_class or None,
                reason=reason,
            ),
            True,
            "",
        )

    # 최후의 fallback — 텍스트에 "결함" / "defect" / "오류"가 있으면 detected.
    lowered = text.lower()
    fallback_detected = any(k in lowered for k in ("결함", "defect", "오류", "잘못"))
    return (
        _ParsedVerdict(has_defect=fallback_detected, defect_class=None, reason=None),
        False,
        "json parse failed, heuristic fallback used",
    )


# ──────────────────────────────────────────────────────────────────────────
# 비동기 평가
# ──────────────────────────────────────────────────────────────────────────
def _quality_routing_decision() -> RoutingDecision:
    """QUALITY 티어 평가용 RoutingDecision — FixedModelOllamaProvider는 model_id만 본다."""
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_model=LocalModelTier.QUALITY,
        mode="async",
        reason="OPS-48 fixed-model quality battle",
        est_latency_ms=0,
    )


async def _evaluate_one(
    provider: FixedModelOllamaProvider,
    item: SeededItem,
    *,
    semaphore: asyncio.Semaphore,
    json_schema: dict[str, Any] | None,
) -> ModelOutcome:
    """한 문항에 대해 LLM 호출 → 파싱 → ModelOutcome."""
    prompt = "다음 문항을 검수하세요.\n\n" + _format_item(item)
    async with semaphore:
        try:
            result: GenerationResult = await provider.generate(
                prompt=prompt,
                system=_SYSTEM_PROMPT,
                decision=_quality_routing_decision(),
                temperature=0.0,
                json_schema=json_schema,
            )
        except Exception as exc:  # noqa: BLE001 — 네트워크·모델 오류는 unresolved로 기록
            return ModelOutcome(
                model_id=provider._model_id,  # noqa: SLF001 — 동일 클래스 내부 접근
                slug=item.candidate.problem.slug or "",
                ground_truth=item.defect_class,
                detected=False,
                predicted_class=None,
                parsed=False,
                parse_error=f"{type(exc).__name__}: {exc}",
            )

    text = result.text
    verdict, parsed, parse_error = _parse_response(text)
    return ModelOutcome(
        model_id=provider._model_id,  # noqa: SLF001
        slug=item.candidate.problem.slug or "",
        ground_truth=item.defect_class,
        detected=verdict.has_defect,
        predicted_class=verdict.defect_class,
        parsed=parsed,
        parse_error=parse_error or None,
        latency_ms=result.usage.latency_ms if result.usage else None,
        input_tokens=result.usage.input_tokens if result.usage else None,
        output_tokens=result.usage.output_tokens if result.usage else None,
        raw_response=text,
    )


async def evaluate_model(
    model_id: str,
    items: list[SeededItem],
    *,
    ollama_host: str | None = None,
    timeout: float = 600.0,
    num_ctx: int = 8192,
    num_predict: int | None = 512,
    concurrency: int = 1,
    json_schema: dict[str, Any] | None = None,
    client: _OllamaClient | None = None,
) -> list[ModelOutcome]:
    """주어진 모델로 전체 시험지를 평가한다."""
    from whymath_backend.config import get_settings

    settings = get_settings()
    if ollama_host is not None:
        settings = settings.model_copy(update={"ollama_host": ollama_host})
    provider = FixedModelOllamaProvider(
        model_id=model_id,
        client=client,
        settings=settings,
        timeout=timeout,
        num_ctx=num_ctx,
        num_predict=num_predict,
    )
    semaphore = asyncio.Semaphore(max(1, concurrency))
    coros = [
        _evaluate_one(provider, item, semaphore=semaphore, json_schema=json_schema)
        for item in items
    ]
    return await asyncio.gather(*coros)


# ──────────────────────────────────────────────────────────────────────────
# 집계 / 리포트
# ──────────────────────────────────────────────────────────────────────────
def _summarize(model_id: str, outcomes: list[ModelOutcome]) -> ModelReport:
    """ModelOutcome 리스트 → DetectionMetrics + per_class + latency."""
    tp = fn = fp = tn = unresolved = 0
    per_class: dict[str, list[int]] = {name: [0, 0] for name in DEFECT_CLASSES}
    latencies: list[float] = []
    for o in outcomes:
        if o.ground_truth is not None:
            per_class[o.ground_truth][1] += 1
        if o.detected and o.ground_truth is not None and o.ground_truth == o.predicted_class:
            per_class[o.ground_truth][0] += 1
        if not o.parsed:
            unresolved += 1
            continue
        if o.ground_truth is None:
            if o.detected:
                fp += 1
            else:
                tn += 1
        else:
            if o.detected:
                tp += 1
            else:
                fn += 1
        if o.latency_ms is not None:
            latencies.append(o.latency_ms)

    metrics = DetectionMetrics(
        true_positives=tp,
        false_negatives=fn,
        false_positives=fp,
        true_negatives=tn,
        unresolved=unresolved,
    )
    latency_report: dict[str, float | None] = {
        "mean": statistics.mean(latencies) if latencies else None,
        "median": statistics.median(latencies) if latencies else None,
        "min": min(latencies) if latencies else None,
        "max": max(latencies) if latencies else None,
        "p90": (statistics.quantiles(latencies, n=10)[8] if len(latencies) >= 10 else None),
    }
    return ModelReport(
        model_id=model_id,
        n_items=len(outcomes),
        metrics=metrics,
        latency_ms=latency_report,
        per_class={name: (v[0], v[1]) for name, v in per_class.items()},
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _render_model_report(report: ModelReport, *, confidence: float) -> list[str]:
    pct = round(confidence * 100)
    m = report.metrics
    lines: list[str] = []
    lines.append(f"  모델: {report.model_id}")
    lines.append(
        f"  처리 문항: {report.n_items} (결함 {m.defective_total} / 무결함 {m.clean_total})"
    )
    lines.append(f"  미분류/파싱실패: {m.unresolved}")
    dlb = _fmt(m.detection_lower_bound(confidence))
    lines.append(
        f"  결함 검출률: {m.true_positives}/{m.defective_total} "
        f"(점추정 {_fmt(m.detection_rate)} · {pct}% 하한 {dlb})"
    )
    fau = _fmt(m.false_alarm_upper_bound(confidence))
    lines.append(
        f"  무결함 오검출: {m.false_positives}/{m.clean_total} "
        f"(점추정 {_fmt(m.false_alarm_rate)} · {pct}% 상한 {fau})"
    )
    lat = report.latency_ms
    lines.append(
        f"  지연(ms): mean={_fmt(lat.get('mean'))} "
        f"median={_fmt(lat.get('median'))} max={_fmt(lat.get('max'))}"
    )
    lines.append("  [결함류별(클래스 일치)]")
    for name in DEFECT_CLASSES:
        detected, total = report.per_class[name]
        rate = _fmt(detected / total) if total else "n/a"
        lines.append(f"    {name:26s} {detected:>3d}/{total:<3d} ({rate})")
    return lines


def render_report(report: BattleReport) -> str:
    """사람 가독 대조 리포트."""
    pct = round(report.confidence * 100)
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("OPS-48 QUALITY 티어 dense ↔ MoE 정확도 축 강등전")
    lines.append("=" * 72)
    lines.append(
        f"설정: 결함 {report.n_defective} · 무결함 {report.n_clean} "
        f"· seed {report.seed} · 신뢰수준 {pct}%"
    )
    lines.append("")
    lines.append("[기준] " + report.baseline_model_id)
    lines.extend(_render_model_report(report.baseline, confidence=report.confidence))
    lines.append("")
    lines.append("[후보] " + report.candidate_model_id)
    lines.extend(_render_model_report(report.candidate, confidence=report.confidence))
    lines.append("")
    lines.append("[대조]")
    baseline_d = report.baseline.metrics.detection_rate
    candidate_d = report.candidate.metrics.detection_rate
    baseline_f = report.baseline.metrics.false_alarm_rate
    candidate_f = report.candidate.metrics.false_alarm_rate
    d_diff = _fmt((candidate_d or 0) - (baseline_d or 0))
    f_diff = _fmt((candidate_f or 0) - (baseline_f or 0))
    lines.append(
        f"  검출률 점추정: 기준 {_fmt(baseline_d)} → 후보 {_fmt(candidate_d)} (차이 {d_diff})"
    )
    lines.append(
        f"  오검출률 점추정: 기준 {_fmt(baseline_f)} → 후보 {_fmt(candidate_f)} (차이 {f_diff})"
    )
    lines.append("=" * 72)
    return "\n".join(lines)


def report_to_json(report: BattleReport) -> dict[str, object]:
    """리포트 → JSON 직렬화 가능 dict(감사·기계 판독용)."""

    def model_json(m: ModelReport) -> dict[str, object]:
        return {
            "model_id": m.model_id,
            "n_items": m.n_items,
            "metrics": {
                "true_positives": m.metrics.true_positives,
                "false_negatives": m.metrics.false_negatives,
                "false_positives": m.metrics.false_positives,
                "true_negatives": m.metrics.true_negatives,
                "unresolved": m.metrics.unresolved,
                "detection_rate": m.metrics.detection_rate,
                "false_alarm_rate": m.metrics.false_alarm_rate,
                "detection_lower_bound": m.metrics.detection_lower_bound(),
                "false_alarm_upper_bound": m.metrics.false_alarm_upper_bound(),
            },
            "latency_ms": m.latency_ms,
            "per_class": dict(m.per_class),
        }

    return {
        "baseline_model_id": report.baseline_model_id,
        "candidate_model_id": report.candidate_model_id,
        "n_defective": report.n_defective,
        "n_clean": report.n_clean,
        "seed": report.seed,
        "confidence": report.confidence,
        "baseline": model_json(report.baseline),
        "candidate": model_json(report.candidate),
    }


# ──────────────────────────────────────────────────────────────────────────
# 감사 JSONL
# ──────────────────────────────────────────────────────────────────────────
def _write_audit(
    audit_path: Path,
    baseline_outcomes: list[ModelOutcome],
    candidate_outcomes: list[ModelOutcome],
    report: BattleReport,
) -> None:
    """문항별 판정 + as-found 요약 JSONL 저장.

    PR #854 "측정 도구는 실패 경로부터 설계" — 상세 레코드와 as-found 요약은 다른
    스키마이므로 ``record_type`` 태그로 명시적으로 구분한다. 파서가 tail을 시간 필터
    없이 읽었을 때 요약 행을 오판정하지 않도록 한다.
    """
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("w", encoding="utf-8") as fh:
        for baseline, candidate in zip(baseline_outcomes, candidate_outcomes, strict=True):
            fh.write(
                json.dumps(
                    {
                        "record_type": "verdict",
                        "slug": baseline.slug,
                        "ground_truth": baseline.ground_truth,
                        "baseline": {
                            "model_id": baseline.model_id,
                            "detected": baseline.detected,
                            "predicted_class": baseline.predicted_class,
                            "parsed": baseline.parsed,
                            "parse_error": baseline.parse_error,
                            "latency_ms": baseline.latency_ms,
                            "input_tokens": baseline.input_tokens,
                            "output_tokens": baseline.output_tokens,
                            "raw_response": baseline.raw_response,
                        },
                        "candidate": {
                            "model_id": candidate.model_id,
                            "detected": candidate.detected,
                            "predicted_class": candidate.predicted_class,
                            "parsed": candidate.parsed,
                            "parse_error": candidate.parse_error,
                            "latency_ms": candidate.latency_ms,
                            "input_tokens": candidate.input_tokens,
                            "output_tokens": candidate.output_tokens,
                            "raw_response": candidate.raw_response,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        b = report.baseline.metrics
        c = report.candidate.metrics
        conf = report.confidence
        summary = {
            "record_type": "as_found_summary",
            "as_found_baseline_detection_rate": b.detection_rate,
            "as_found_baseline_false_alarm_rate": b.false_alarm_rate,
            "as_found_candidate_detection_rate": c.detection_rate,
            "as_found_candidate_false_alarm_rate": c.false_alarm_rate,
            "as_found_baseline_detection_lower_bound": b.detection_lower_bound(conf),
            "as_found_candidate_detection_lower_bound": c.detection_lower_bound(conf),
            "as_found_baseline_false_alarm_upper_bound": b.false_alarm_upper_bound(conf),
            "as_found_candidate_false_alarm_upper_bound": c.false_alarm_upper_bound(conf),
        }
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """OPS-48 QUALITY 티어 MoE 정확도 강등전 CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.quality_tier_moe_accuracy_battle",
        description="QUALITY 티어 dense 27B ↔ MoE 정확도 축 강등전 — Wilson 단측 경계 판정.",
    )
    parser.add_argument("--baseline-model", default="qwen3.5:27b", help="기준 dense 모델 ID.")
    parser.add_argument("--candidate-model", default="qwen3:30b-a3b", help="후보 MoE 모델 ID.")
    parser.add_argument("--n-defective", type=int, default=70, help="결함 문항 수(기본 70).")
    parser.add_argument("--n-clean", type=int, default=70, help="무결함 문항 수(기본 70).")
    parser.add_argument("--seed", type=int, default=20260708, help="셋 생성 시드(결정론).")
    parser.add_argument("--confidence", type=float, default=0.95, help="Wilson 신뢰수준(단측).")
    parser.add_argument("--ollama-host", default=None, help="Ollama 호스트(기본 설정값 사용).")
    parser.add_argument("--timeout", type=float, default=600.0, help="모델 호출 타임아웃(초).")
    parser.add_argument("--num-ctx", type=int, default=8192, help="Ollama num_ctx.")
    parser.add_argument("--num-predict", type=int, default=512, help="최대 출력 토큰.")
    parser.add_argument("--concurrency", type=int, default=1, help="동시 호출 수(기본 1).")
    parser.add_argument(
        "--no-json-schema",
        action="store_true",
        help="JSON schema 제약을 사용하지 않고 자유 텍스트 생성 후 파싱.",
    )
    parser.add_argument(
        "--min-detection-lower",
        type=float,
        default=0.0,
        help="후보 검출률 Wilson 하한 임계 — 미만이면 exit 1(기본 0=off).",
    )
    parser.add_argument(
        "--max-false-alarm-upper",
        type=float,
        default=1.0,
        help="후보 오경보율 Wilson 상한 임계 — 초과면 exit 1(기본 1.0=off).",
    )
    parser.add_argument(
        "--require-candidate-not-worse-than-baseline",
        action="store_true",
        help="후보가 기준 모델보다 검출률/오경보에서 열등하면 exit 1.",
    )
    parser.add_argument(
        "--not-worse-margin",
        type=float,
        default=0.0,
        help="'not worse' 판정 허용 마진(기본 0.0).",
    )
    parser.add_argument(
        "--audit-out",
        type=Path,
        default=None,
        help="감사 JSONL 저장 경로(예: data/audit/ops-48-battle.jsonl).",
    )
    args = parser.parse_args(argv)

    if args.n_defective <= 0 or args.n_clean <= 0:
        print("오류: --n-defective와 --n-clean은 1 이상이어야 합니다.", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    items = build_defect_seeded_set(
        n_defective=args.n_defective,
        n_clean=args.n_clean,
        seed=args.seed,
    )

    json_schema = None if args.no_json_schema else _JSON_SCHEMA

    print(
        f"[OPS-48] 시험지 생성 완료: "
        f"결함 {args.n_defective} · 무결함 {args.n_clean} · seed {args.seed}"
    )
    print(f"[OPS-48] 기준 모델 {args.baseline_model} 평가 시작...")
    baseline_outcomes = asyncio.run(
        evaluate_model(
            args.baseline_model,
            items,
            ollama_host=args.ollama_host,
            timeout=args.timeout,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            concurrency=args.concurrency,
            json_schema=json_schema,
        )
    )
    print(f"[OPS-48] 후보 모델 {args.candidate_model} 평가 시작...")
    candidate_outcomes = asyncio.run(
        evaluate_model(
            args.candidate_model,
            items,
            ollama_host=args.ollama_host,
            timeout=args.timeout,
            num_ctx=args.num_ctx,
            num_predict=args.num_predict,
            concurrency=args.concurrency,
            json_schema=json_schema,
        )
    )

    report = BattleReport(
        baseline=_summarize(args.baseline_model, baseline_outcomes),
        candidate=_summarize(args.candidate_model, candidate_outcomes),
        n_defective=args.n_defective,
        n_clean=args.n_clean,
        seed=args.seed,
        confidence=args.confidence,
        baseline_model_id=args.baseline_model,
        candidate_model_id=args.candidate_model,
    )

    print(render_report(report))

    if args.audit_out is not None:
        _write_audit(args.audit_out, baseline_outcomes, candidate_outcomes, report)
        print(f"[OPS-48] 감사 JSONL 저장: {args.audit_out}")

    # 게이트 판정
    exit_code = _EXIT_OK
    candidate_dlb = report.candidate.metrics.detection_lower_bound(args.confidence)
    if args.min_detection_lower > 0.0 and (
        candidate_dlb is None or candidate_dlb < args.min_detection_lower
    ):
        exit_code = _EXIT_GATE_FAIL
    candidate_fau = report.candidate.metrics.false_alarm_upper_bound(args.confidence)
    if args.max_false_alarm_upper < 1.0 and (
        candidate_fau is None or candidate_fau > args.max_false_alarm_upper
    ):
        exit_code = _EXIT_GATE_FAIL

    if args.require_candidate_not_worse_than_baseline:
        baseline_dlb = report.baseline.metrics.detection_lower_bound(args.confidence)
        baseline_fau = report.baseline.metrics.false_alarm_upper_bound(args.confidence)
        margin = args.not_worse_margin
        if candidate_dlb is None or (
            baseline_dlb is not None and candidate_dlb < baseline_dlb - margin
        ):
            d_msg = (
                f"후보 하한 {_fmt(candidate_dlb)} < "
                f"기준 하한 {_fmt(baseline_dlb)} - 마진 {_fmt(margin)}"
            )
            print(
                "[OPS-48] 후보가 기준보다 검출률이 열등합니다: " + d_msg,
                file=sys.stderr,
            )
            exit_code = _EXIT_GATE_FAIL
        if candidate_fau is None or (
            baseline_fau is not None and candidate_fau > baseline_fau + margin
        ):
            f_msg = (
                f"후보 상한 {_fmt(candidate_fau)} > "
                f"기준 상한 {_fmt(baseline_fau)} + 마진 {_fmt(margin)}"
            )
            print(
                "[OPS-48] 후보가 기준보다 오경보가 높습니다: " + f_msg,
                file=sys.stderr,
            )
            exit_code = _EXIT_GATE_FAIL

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
