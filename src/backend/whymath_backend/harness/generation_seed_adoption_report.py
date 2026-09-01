"""생성 seed 적재율 리포트 — EOS-73 acceptance ②("작동한 비율" 상시 보고).

**존재 이유**: `GenerationLog.seed` 좌석(EOS-55)과 스레딩 코드(EOS-73 ①)를 만든 것만으로는
그것이 *작동한다*는 증거가 되지 않는다(CLAUDE.md 「작동 신호 없는 알고리즘 부착 금지」 —
배치가 정상 종료했다는 사실은 시드가 실려 나갔다는 증거가 아니다). 좌석 실재 ≠ 적재이며,
이 좌석은 실제로 **전 경로 NULL인 채로 착지 후 이틀을 보냈다**. 이 리포트가 그 비율을 말한다.

**3분류를 뭉개지 않는다** — 기록 1건은 다음 셋 중 하나이고, 셋의 대책이 서로 다르다:
  1. **지원 경로인데 미적재**(`SUPPORTED` + seed NULL) — 배선이 끊겼거나 스레딩 착지 이전의
     과거 기록이다. **회귀는 여기서만 보인다.**
  2. **구조적 불가**(`UNSUPPORTED` + seed NULL) — 클라우드(Anthropic Messages API에 seed
     파라미터 부재). NULL이 *정답*이며 대책이 없다. 1과 한 숫자로 뭉치면 "배선이 죽었다"와
     "원래 안 되는 경로다"가 같은 글자가 된다.
  3. **미상**(`UNKNOWN`) — 라우터 매트릭스에도 설정 클라우드 모델에도 없는 이름(강등전 고정
     모델·구판 기록·오배선). 지원/불가 어느 쪽으로도 반올림하지 않는다 — 미상을 지원으로
     반올림하면 분모가 부풀고, 불가로 반올림하면 진짜 회귀가 "원래 안 되는 경로"로 숨는다.
분류의 단일 좌석은 `l3/generation_seed.capability_for_model`이다(쓰기측과 같은 정의를 본다).

**경로별 분모**: `input_snapshot.kind`로 pregenerate·accumulate를 나눈다. 한쪽 경로에서만
스레딩이 끊기면 전체 평균에서는 절반의 감소로 희석되지만 경로별로는 0%로 즉시 드러난다.
기록이 0건인 경로도 **행을 지우지 않는다** — 한 경로가 통째로 멈추면 그 경로는 집계에서
*사라지므로*, 보강이 없으면 전멸이 화면에서 안 보인다.

**병리 행**: `UNSUPPORTED`인데 seed가 적재된 기록. 정상 배선에서는 0이며, 0이 아니면 모델에
전달된 적 없는 숫자가 기록됐다는 뜻이다(= 재현 가능하다고 거짓말하는 행·날조 금지 위반).

**게이트가 아니다**(`attempt_skill_event_reach_report` 동일 원칙) — 적재율이 0%여도 exit 1을
내지 않는다. 목표는 차단이 아니라 가시화이며, 판정 임계는 실측이 쌓인 뒤에 정한다(측정 없는
게이트 금지). exit는 **0=성공(0%여도) / 2=입력·파싱 오류**뿐이고, 실패는 예외 타입명과 함께
stderr로 보고한다(침묵 실패 금지 — 측정 실패가 "0% 미달"로 위장되면 안 된다).

**입력이 JSONL인 이유**: 두 생성 경로는 오프라인 배치라 DB 세션이 없다 — GenerationLog의 1차
매체가 `<out>.genlog.jsonl` 사이드카다(`l3/pregenerate/provenance_bridge` 적재 매체 메모).
파일 부재는 exit 2다 — "파일 없음"과 "레코드 0건"은 다른 실패이며 전자를 0%로 렌더하면
측정하지 않은 것을 측정한 것처럼 보이게 한다.

사용:
    python -m whymath_backend.harness.generation_seed_adoption_report out/specs.genlog.jsonl
    python -m whymath_backend.harness.generation_seed_adoption_report a.jsonl b.jsonl \\
        --json out/eos73.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from whymath_backend.l3.generation_seed import SeedCapability, capability_for_model
from whymath_backend.l3.pregenerate.provenance_bridge import load_generation_logs_jsonl
from whymath_backend.schema.provenance import GenerationLog

__all__ = [
    "ACCUMULATE_PATH",
    "PREGENERATE_PATH",
    "UNKNOWN_PATH",
    "PathBreakdown",
    "SeedAdoptionReport",
    "build_report",
    "dump_json",
    "main",
    "path_of",
    "render_report",
    "report_to_json",
]

# 경로 판별자 — 각 생성 경로가 `input_snapshot["kind"]`에 실제로 쓰는 값.
# 정본은 생산자 쪽(`provenance_bridge.input_snapshot_for_prewarm`·`llm_generator._input_snapshot`)
# 이고, 여기 사본이 그것과 어긋나지 않는지는 테스트가 실제 스냅샷을 만들어 동결한다
# (`tests/backend/harness/test_generation_seed_adoption_report.py`) — 문자열을 눈으로 맞추지 않는다.
PREGENERATE_PATH: Final[str] = "l3.pregenerate.prewarm"
ACCUMULATE_PATH: Final[str] = "l3.equivalent.llm_generate"
UNKNOWN_PATH: Final[str] = "(미상)"

# 화면·JSON에 항상 나타나야 하는 경로(기록 0건이어도 행을 지우지 않는다 — 전멸 가시화).
_KNOWN_PATHS: Final[tuple[str, ...]] = (PREGENERATE_PATH, ACCUMULATE_PATH)

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2


def path_of(log: GenerationLog) -> str:
    """기록 1건의 생성 경로 — `input_snapshot.kind`. 스냅샷·kind가 없으면 `(미상)`.

    구판 기록(스냅샷 좌석 이전)이나 다른 경로가 흘려 넣은 기록을 두 경로 중 하나로
    반올림하지 않는다 — 분모를 오염시키면 적재율이 "누구의 비율인지" 알 수 없게 된다.
    """
    snapshot = log.input_snapshot
    if not isinstance(snapshot, dict):
        return UNKNOWN_PATH
    kind = snapshot.get("kind")
    return kind if isinstance(kind, str) and kind else UNKNOWN_PATH


@dataclass(slots=True, frozen=True)
class PathBreakdown:
    """생성 경로 1개의 seed 적재 현황(3분류 + 병리).

    `supported_*`가 적재율의 분자·분모다 — 구조적 불가(클라우드)와 미상은 분모에서 **뺀다**.
    빼지 않으면 클라우드를 많이 쓴 배치가 "적재율이 떨어졌다"로 보여, 회귀와 라우팅 구성 변화가
    같은 숫자로 뭉개진다.
    """

    path: str
    total: int
    supported_total: int
    supported_with_seed: int
    unsupported_total: int
    unsupported_with_seed: int
    unknown_total: int
    unknown_with_seed: int

    @property
    def adoption_rate(self) -> float | None:
        """지원 경로 기록 중 seed 적재 비율. **지원 기록 0건이면 None**(분모 0의 0% 위장 금지)."""
        if self.supported_total == 0:
            return None
        return self.supported_with_seed / self.supported_total

    @property
    def supported_missing(self) -> int:
        """지원 경로인데 seed가 없는 기록 수 — 이 태스크가 해소한 '좌석 무작동'의 잔량."""
        return self.supported_total - self.supported_with_seed


@dataclass(slots=True, frozen=True)
class SeedAdoptionReport:
    """적재율 관측 결과 전량(불변·렌더/직렬화의 단일 입력)."""

    paths: tuple[PathBreakdown, ...]
    sources: tuple[Path, ...]
    parse_errors: tuple[str, ...]

    @property
    def total_records(self) -> int:
        return sum(p.total for p in self.paths)

    @property
    def supported_total(self) -> int:
        return sum(p.supported_total for p in self.paths)

    @property
    def supported_with_seed(self) -> int:
        return sum(p.supported_with_seed for p in self.paths)

    @property
    def fabrication_suspects(self) -> int:
        """구조적 불가 경로인데 seed가 적재된 기록 수 — **병리**(정상 배선에서는 0)."""
        return sum(p.unsupported_with_seed for p in self.paths)

    @property
    def overall_adoption_rate(self) -> float | None:
        """전 경로 합산 적재율. 지원 기록 0건이면 None(측정 불가)."""
        total = self.supported_total
        return None if total == 0 else self.supported_with_seed / total


def build_report(
    logs: Iterable[GenerationLog],
    *,
    sources: Sequence[Path] = (),
    parse_errors: Sequence[str] = (),
) -> SeedAdoptionReport:
    """기록 목록 → 리포트(순수·부작용 0·파일 I/O 불요).

    폐쇄 2경로(pregenerate·accumulate)를 **전부** 보강하고, 그 외 판별자(구판·오배선)는
    버리지 않고 뒤에 덧붙인다(조용한 생략 금지 — 모듈 docstring "경로별 분모").
    """
    buckets: dict[str, dict[str, int]] = {}

    def _bucket(path: str) -> dict[str, int]:
        return buckets.setdefault(
            path,
            {
                "total": 0,
                "supported_total": 0,
                "supported_with_seed": 0,
                "unsupported_total": 0,
                "unsupported_with_seed": 0,
                "unknown_total": 0,
                "unknown_with_seed": 0,
            },
        )

    for path in _KNOWN_PATHS:
        _bucket(path)

    for log in logs:
        bucket = _bucket(path_of(log))
        capability = capability_for_model(log.model_name)
        has_seed = log.seed is not None
        bucket["total"] += 1
        if capability is SeedCapability.SUPPORTED:
            bucket["supported_total"] += 1
            bucket["supported_with_seed"] += int(has_seed)
        elif capability is SeedCapability.UNSUPPORTED:
            bucket["unsupported_total"] += 1
            bucket["unsupported_with_seed"] += int(has_seed)
        else:
            bucket["unknown_total"] += 1
            bucket["unknown_with_seed"] += int(has_seed)

    extra = sorted(key for key in buckets if key not in _KNOWN_PATHS)
    ordered = [*_KNOWN_PATHS, *extra]
    return SeedAdoptionReport(
        paths=tuple(PathBreakdown(path=key, **buckets[key]) for key in ordered),
        sources=tuple(sources),
        parse_errors=tuple(parse_errors),
    )


def load_logs(paths: Sequence[Path]) -> tuple[list[GenerationLog], list[str]]:
    """여러 JSONL에서 기록을 모은다 — (기록, 실패 사유). 파일 부재는 예외를 그대로 올린다.

    파싱 실패 줄은 삼키지 않고 사유(예외 타입명 + 줄 번호 + 필드 위치)로 수집한다 —
    `load_generation_logs_jsonl` 계약 그대로이며, 리포트가 그 건수를 화면에 적는다(파싱 실패를
    "seed 없는 기록"으로 뭉개면 측정 실패가 적재 실패로 위장된다).
    """
    logs: list[GenerationLog] = []
    errors: list[str] = []
    for path in paths:
        file_logs, file_errors = load_generation_logs_jsonl(path)
        logs.extend(file_logs)
        errors.extend(f"{path}: {reason}" for reason in file_errors)
    return logs, errors


def _pct(value: float | None) -> str:
    """비율 렌더 — 분모 0(None)은 `측정 불가(분모 0)`로 말한다(0%로 위장 금지)."""
    return "측정 불가(분모 0)" if value is None else f"{value * 100:.1f}%"


def render_report(report: SeedAdoptionReport) -> str:
    """적재율 관측 결과를 마크다운으로 렌더(순수·입력 외 계산 없음)."""
    lines: list[str] = [
        "# 생성 seed 적재율 리포트 (EOS-73 ②)",
        "",
        "> 관측 리포트다 — **exit 게이트가 아니다**(적재율이 0%여도 실패시키지 않는다).",
        "> 측정 실패는 exit 2 + 예외 타입명으로 구분된다(0% 미달로 위장되지 않는다).",
        "",
        f"- 입력 JSONL: {', '.join(str(p) for p in report.sources) or '(직접 주입)'}",
        f"- 기록 총건수: **{report.total_records}**",
        f"- 파싱 실패 줄: **{len(report.parse_errors)}** (아래 §4 — 적재 실패와 다른 축)",
        "",
        "## 1. 종합 적재율 (분모 = seed를 실을 수 있는 경로의 기록만)",
        "",
        f"- **seed 적재율**: {_pct(report.overall_adoption_rate)} "
        f"({report.supported_with_seed}/{report.supported_total})",
        "- 분모에서 제외한 것: 구조적 불가(클라우드 — Messages API에 seed 파라미터 부재)와 미상."
        " 빼지 않으면 라우팅 구성 변화가 배선 회귀처럼 보인다.",
        "",
        "## 2. 경로별 (폐쇄 2경로 전부 — 기록 없는 경로도 0으로 명시)",
        "",
        "| 경로 | 기록 | 지원 | seed 적재 | 적재율 | 지원인데 미적재 | 구조적 불가 | 미상 |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for breakdown in report.paths:
        lines.append(
            f"| `{breakdown.path}` | {breakdown.total} | {breakdown.supported_total} | "
            f"{breakdown.supported_with_seed} | {_pct(breakdown.adoption_rate)} | "
            f"{breakdown.supported_missing} | {breakdown.unsupported_total} | "
            f"{breakdown.unknown_total} |"
        )
    lines += [
        "",
        "- **지원인데 미적재**가 이 태스크가 해소한 '좌석 무작동'의 잔량이다(배선 축 — 코드).",
        "- **구조적 불가**는 NULL이 정답인 기록이다(대책 없음 — 클라우드 API에 좌석 자체가 없다).",
        "- **미상**은 라우터 매트릭스에도 설정 클라우드 모델에도 없는 이름이다(강등전 고정 모델·"
        "구판 기록). 지원/불가로 반올림하지 않는다.",
        "",
        "## 3. 병리 — 실을 수 없는 경로에 seed가 적재됨",
        "",
        f"- 건수: **{report.fabrication_suspects}** (정상 배선에서는 0)",
        "- 0이 아니면 *모델에 전달된 적 없는 숫자*가 기록된 것이다 — 그 행은 재현 가능하다고"
        " 거짓말한다(날조 금지 위반). 조용히 넘기지 말고 어느 경로가 넣었는지 조사한다.",
        "",
        "## 4. 파싱 실패 줄 (측정 실패 — 적재 실패가 아니다)",
        "",
    ]
    if report.parse_errors:
        lines += [f"- {reason}" for reason in report.parse_errors]
    else:
        lines.append("- 없음")
    lines.append("")
    return "\n".join(lines)


def report_to_json(report: SeedAdoptionReport) -> dict[str, Any]:
    """리포트 → JSON 직렬화 가능 dict(키 정렬은 dump 시 `sort_keys=True`)."""
    return {
        "sources": [str(p) for p in report.sources],
        "total_records": report.total_records,
        "supported_total": report.supported_total,
        "supported_with_seed": report.supported_with_seed,
        "overall_adoption_rate": report.overall_adoption_rate,
        "fabrication_suspects": report.fabrication_suspects,
        "parse_errors": list(report.parse_errors),
        "paths": [
            {
                "path": b.path,
                "total": b.total,
                "supported_total": b.supported_total,
                "supported_with_seed": b.supported_with_seed,
                "supported_missing": b.supported_missing,
                "unsupported_total": b.unsupported_total,
                "unsupported_with_seed": b.unsupported_with_seed,
                "unknown_total": b.unknown_total,
                "unknown_with_seed": b.unknown_with_seed,
                "adoption_rate": b.adoption_rate,
            }
            for b in report.paths
        ],
    }


def dump_json(report: SeedAdoptionReport) -> str:
    return json.dumps(report_to_json(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# ──────────────────────────────────────────────────────────────────────────
# CLI (얇은 껍데기 — 파일 입출력만, 집계는 위 순수 코어)
# ──────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 적재율 리포트를 stdout에 출력. **0=성공(0%여도) / 2=입력·파싱 오류**."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.generation_seed_adoption_report",
        description=(
            "생성 seed 적재율 리포트(EOS-73 ②) — 경로별(pregenerate·accumulate) 적재율·"
            "구조적 불가·병리 분해. 게이트 아님(exit 0/2)."
        ),
    )
    parser.add_argument(
        "genlog",
        nargs="+",
        type=Path,
        help="GenerationLog JSONL 경로(들) — 기본 사이드카는 <out>.genlog.jsonl",
    )
    parser.add_argument(
        "--json", dest="json_path", type=Path, default=None, help="JSON 산출물 경로(선택)"
    )
    args = parser.parse_args(argv)

    try:
        logs, errors = load_logs(args.genlog)
    except Exception as exc:  # noqa: BLE001 — 입력 오류는 타입명과 함께 보고하고 exit 2
        print(
            f"입력 오류 — seed 적재율 집계 실패({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR

    report = build_report(logs, sources=args.genlog, parse_errors=errors)
    print(render_report(report))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(dump_json(report), encoding="utf-8")
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
