"""WH-1 0단계 대리 지표 *코호트 베이스라인 리포트* — 설계 산출물 결선(CLI).

설계 정본: `docs/architecture/04a_wh1_tutoring_harness.md` §8.4. WH-1 0단계의 산출물은
**"커버리지 맵 + 베이스라인 수치"**(무엇을 *지금* 잴 수 있고, 무엇이 *아직* 못 재는지)다.
`wh1_evaluation.compute_wh1_surrogate_metrics`가 지표 11종(7 + S3 세션 4)을 계산하지만,
그 결과는 지금까지 per-user API(`GET /v1/me/harness-metrics`)로만 소비됐다 — 설계가 명시한
**코호트 전체 집계(`user_id=None`)를 ops/스크립트가 직접 호출**하는 진입점(그 산출물을 사람이
읽을 리포트로 렌더)이 비어 있었다. 본 모듈이 그 결선이다.

렌더 철학(계산 계층과 동일·CLAUDE.md "모르면 모른다"): "가짜 0 금지"를 그대로 표면화한다 —
MEASURED만 값을 보이고, NO_DATA/미계측은 값 대신 사유(note)를 그대로 옮긴다. 요약에 커버리지
카운트(MEASURED n / 전체)를 실어 *무엇이 아직 데이터 없이 비어 있는지*를 한 장으로 드러낸다.

실행: `python -m whymath_backend.harness.surrogate_baseline_report [--since ISO --until ISO
[--user-id UUID]]`. 기본은 코호트 전체(user 미지정)·전체 기간. DB 조회 전용(쓰기 0).

계층 메모(CLAUDE.md 7계층): `wh1_evaluation`(횡단 인프라)을 소비하는 *리포팅* 진입점이다 —
L1(활동)·L2(mastery)·L4(오개념)·Dialogue를 조회만 하는 계산 계층을 그대로 호출하고, 새 계산·
새 지표를 만들지 않는다(렌더 전용).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime

from whymath_backend.db.session import get_sessionmaker
from whymath_backend.harness.wh1_evaluation import (
    MetricStatus,
    SurrogateMetrics,
    compute_wh1_surrogate_metrics,
)

__all__ = ["render_baseline_report", "main"]


# 상태 → 아이콘(커버리지 맵 가독). MEASURED 실측·NO_DATA 좌석 있으나 표본 0·나머지는 미계측.
_STATUS_ICON: dict[MetricStatus, str] = {
    MetricStatus.MEASURED: "🟢",
    MetricStatus.NO_DATA: "🟡",
    MetricStatus.NOT_INSTRUMENTED: "🔴",
    MetricStatus.REQUIRES_DATA: "🔴",
    MetricStatus.REQUIRES_TOOL: "🔴",
}

# 렌더 순서·라벨·표본 필드 — (라벨, SurrogateMetrics 지표 attr, 표본 수 attr). 11 지표 정본 순서
# (7종 + S3 세션 4종). 표본 attr은 그 지표의 대표 표본 수(없으면 None).
_METRIC_ROWS: list[tuple[str, str, str | None]] = [
    ("① verify 통과율", "verify_pass_rate", "sample_verify_events"),
    ("② 진단정확도(오프라인)", "diagnosis_agreement_rate", "sample_diagnostic_probes"),
    ("③ 세션 완주율", "session_completion_rate", "sample_sessions"),
    ("④ 턴당 토큰", "tokens_per_turn", "sample_dialogues"),
    ("⑤ 도움 감소 곡선", "help_reduction_slope", "sample_hint_events"),
    ("⑥ 보정 점수(Brier)", "calibration_brier", "sample_calibration_pairs"),
    ("⑦ 전이 점수(근사)", "transfer_score", "sample_transfer_probes"),
    ("⑧ 답 미루기 도달 깊이", "hint_depth_reached", "sample_hint_events"),
    ("⑨ BKT 숙달 증가율", "mastery_gain_rate", "sample_mastery_groups"),
    ("⑩ 오개념 해소율", "misconception_resolution_rate", "sample_misconception_hypotheses"),
    ("⑪ 스스로 풀이 도달율", "self_solve_rate", "sample_resolved_dialogues"),
]


def _format_value(value: float | None) -> str:
    """지표 value 렌더 — None(미측정·표본 부족)은 값 대신 '—'(가짜 0 금지)."""
    return "—" if value is None else f"{value:.4f}"


def render_baseline_report(metrics: SurrogateMetrics) -> str:
    """대리 지표 11종 커버리지 맵 + 베이스라인을 사람이 읽을 마크다운으로 렌더(순수·DB 무관).

    헤더에 집계 범위(코호트/본인·시간창)와 커버리지 카운트(MEASURED n/전체)를, 이어 지표별로
    상태 아이콘·값·표본 수·사유(note)를, 끝에 R15 결합 판정을 낸다. "가짜 0 금지" — NO_DATA/
    미계측은 값 대신 note를 옮긴다(무엇이 아직 비어 있는지 정직 표면화). 입력 `SurrogateMetrics`
    외 어떤 계산도 하지 않는다(렌더 전용).
    """
    scope = "본인(user)" if metrics.user_scoped else "코호트 전체"
    win_start = metrics.window_start.isoformat() if metrics.window_start else "무한 과거"
    win_end = metrics.window_end.isoformat() if metrics.window_end else "무한 미래"
    measured = sum(
        1 for _, attr, _ in _METRIC_ROWS if getattr(metrics, attr).status is MetricStatus.MEASURED
    )
    total = len(_METRIC_ROWS)

    lines: list[str] = [
        "# WH-1 0단계 대리 지표 베이스라인 (커버리지 맵)",
        "",
        f"- 집계 범위: {scope} · 시간창 {win_start} ~ {win_end}",
        f"- 커버리지: MEASURED {measured}/{total} · NO_DATA/미계측 {total - measured}/{total}",
        "  (가짜 0 금지 — 미측정은 값 대신 사유를 표기)",
        "",
    ]
    for label, attr, sample_attr in _METRIC_ROWS:
        metric = getattr(metrics, attr)
        icon = _STATUS_ICON.get(metric.status, "🔴")
        sample = f"표본 {getattr(metrics, sample_attr)}" if sample_attr is not None else "표본 —"
        lines.append(f"## {icon} {label}")
        lines.append(f"- 상태 {metric.status.value} · 값 {_format_value(metric.value)} · {sample}")
        lines.append(f"- {metric.note}")
        lines.append("")

    r15 = metrics.help_reduction_validated
    lines.append("## R15 결합 판정 (⑤ 도움 감소 × 정답률 × 난이도)")
    lines.append(f"- 판정 {r15.verdict.value}")
    lines.append(f"- {r15.note}")
    lines.append("")
    return "\n".join(lines)


def _resolve_params(
    user_id: str | None,
    since: str | None,
    until: str | None,
) -> tuple[uuid.UUID | None, datetime | None, datetime | None]:
    """CLI 문자열 인자를 타입으로 해석(순수·검증). user_id는 UUID, since/until은 ISO8601.

    TZ-aware/naive·since>until 등 세부 검증은 계산 계층(`compute_wh1_surrogate_metrics`가 받은
    경계를 그대로 비교)·API 계층(time_window)이 담당한다 — 여기선 파싱만 한다(잘못된 형식은
    ValueError로 즉시 실패·조용한 폴백 없음).
    """
    resolved_user = uuid.UUID(user_id) if user_id is not None else None
    resolved_since = datetime.fromisoformat(since) if since is not None else None
    resolved_until = datetime.fromisoformat(until) if until is not None else None
    return resolved_user, resolved_since, resolved_until


async def _run(  # pragma: no cover — 라이브 PG 연결 glue(단위테스트 아닌 실 PG 검증)
    *,
    user_id: uuid.UUID | None,
    since: datetime | None,
    until: datetime | None,
) -> str:
    """세션을 열어 대리 지표를 계산하고 리포트를 렌더한다(DB 조회 전용·쓰기 0)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        metrics = await compute_wh1_surrogate_metrics(
            session, user_id=user_id, since=since, until=until
        )
    return render_baseline_report(metrics)


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 대리 지표 코호트 베이스라인 리포트를 stdout에 출력. 0=성공."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.surrogate_baseline_report",
        description=(
            "WH-1 0단계 대리 지표 11종의 커버리지 맵 + 베이스라인 리포트를 낸다(기본 코호트 "
            "전체·가짜 0 금지 — 미측정은 사유 표기). DB 조회 전용."
        ),
    )
    parser.add_argument("--since", type=str, default=None, help="집계 시작 ISO8601(선택).")
    parser.add_argument("--until", type=str, default=None, help="집계 끝 ISO8601(선택).")
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="특정 user UUID(선택·기본은 코호트 전체 집계).",
    )
    args = parser.parse_args(argv)
    user_id, since, until = _resolve_params(args.user_id, args.since, args.until)
    report = asyncio.run(  # pragma: no cover — 라이브 PG 연결 glue
        _run(user_id=user_id, since=since, until=until)
    )
    print(report)  # pragma: no cover
    return 0  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
