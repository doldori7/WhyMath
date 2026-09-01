"""결정론 재생성 프로브 — 같은 seed·같은 입력이 같은 출력을 내는가 (EOS-73 acceptance ③).

**이 프로브가 재는 것과 재지 못하는 것을 먼저 적는다**(성립하지 않는 계약을 통과로 위장 금지):

  잰다   — 기록된 `GenerationLog`의 `input_snapshot`(프롬프트/시스템 전문)과 `seed`, `model_name`
           을 **그대로 되먹여** 같은 모델을 2회 이상 호출하고, 출력이 바이트 동일한지 본다.
           즉 **"같은 좌표에서 이 배포의 모델이 결정론적인가"**를 잰다.
  못 잰다 — **원 기록의 출력과 같은지는 못 잰다.** `GenerationLog`는 *입력*을 저장하고 출력
           텍스트는 저장하지 않는다(설계상 — 코퍼스 산출물이 별도 파일에 있고, 로그를 응답
           사본으로 부풀리지 않는다). 또한 스냅샷에 없는 호출 인자(structured output 스키마
           등)는 복원되지 않는다. 그래서 이 프로브의 판정은 *재현(replay) 대 원본*이 아니라
           *재현 대 재현*이다.

**왜 "재현 불가"가 실패가 아닌가**: Ollama의 `options.seed`는 샘플링을 고정할 뿐, 배치 크기·
컨텍스트 길이·양자화 커널·서버 재시작에 따른 부동소수 누적 순서까지 고정하지 못한다. 즉
"같은 seed → 같은 출력"은 **가정이 아니라 측정 대상**이다. 성립하지 않으면 그 사실 자체가
결과이며(계약을 '재현 불가 자인'으로 축소한다), 이 프로브는 그 결과를 **기록**한다 — 머지를
막지 않는다. 따라서 exit는 **0=측정 완료(재현 여부 무관) / 2=측정 불가(입력·호출 오류)**다.
CI가 상시 돌리지 않는 이유도 같다 — 라이브 Ollama가 없으면 원리적으로 못 돈다(라이브 의존).

**측정 전 상태의 정직한 표기**: 라이브 측정을 돌리기 전까지 이 배포의 모델 결정성은
`DETERMINISM_CLAIM_UNMEASURED`("미측정")다. *미측정은 성립도 불성립도 아니다* — 어느 쪽으로도
반올림하지 않는다. CI에서 상시 검증되는 것은 이 모듈의 **판정 로직**(분류 변별력·입력 복원·
자인 렌더)이며, 그 동결 지점은 `tests/backend/harness/test_generation_seed_replay_probe.py`다.

**라우터 경유 원칙과의 관계**: 이 프로브는 라우터에게 *다시 결정하게 하지 않고* 기록된
`model_name`을 고정 호출한다(`FixedModelOllamaProvider` — 강등전과 같은 측정 전용 좌석).
재라우팅하면 그 사이 매트릭스가 바뀌었을 때 *다른 모델*을 재고 "재현 불가"라고 말하게 되기
때문이다. 학생 서빙 경로가 아니라 계측 경로이며, 프로덕션 생성은 여전히 라우터 경유다.

사용(라이브 Ollama 필요):
    python -m whymath_backend.harness.generation_seed_replay_probe out/specs.genlog.jsonl
    python -m whymath_backend.harness.generation_seed_replay_probe a.jsonl --limit 3 --repeat 3
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Final

from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.models import CostTier, LocalModelTier, ModelFamily, RoutingDecision
from whymath_backend.l3.pregenerate.provenance_bridge import load_generation_logs_jsonl
from whymath_backend.schema.provenance import GenerationLog

__all__ = [
    "DETERMINISM_CLAIM_UNMEASURED",
    "ReplayInput",
    "ReplayInputError",
    "ReplayOutcome",
    "ReplayVerdict",
    "classify_outputs",
    "fixed_local_decision",
    "main",
    "render_report",
    "replay_input_from_log",
    "replay_inputs_from_logs",
    "report_to_json",
]

DETERMINISM_CLAIM_UNMEASURED: Final[str] = "미측정(라이브 프로브 필요)"
"""라이브 측정 전 이 배포의 '같은 seed → 같은 출력' 성립 여부 표기.

성립도 불성립도 아닌 **제3의 값**이다. 문서·리포트가 이 값을 "성립"으로 바꾸려면 실제
측정 결과가 있어야 한다(측정 없는 승격 금지).
"""

_EXIT_OK = 0
_EXIT_INPUT_ERROR = 2


class ReplayVerdict(str, Enum):
    """재투입 판정 — 3값. `미측정`을 `재현 불가`로 뭉개지 않는다(못 재본 것 ≠ 안 되는 것)."""

    REPRODUCED = "재현"
    NOT_REPRODUCED = "재현 불가"
    UNMEASURED = "미측정"


class ReplayInputError(ValueError):
    """기록에서 재투입 좌표를 복원할 수 없음 — 사유를 문자열로 담는다(조용한 스킵 금지)."""


@dataclass(slots=True, frozen=True)
class ReplayInput:
    """기록 1건에서 복원한 재투입 좌표 — 이 넷이 같으면 '같은 호출'이라고 부른다.

    `temperature`가 포함되는 이유: 온도가 다르면 시드가 같아도 다른 분포에서 뽑는다. accumulate
    경로는 스냅샷에 온도를 남기므로 복원하고(0.9 저작 온도), pregenerate 경로는 온도를 쓰지
    않으므로 None이다 — **없는 값을 기본값으로 지어내지 않는다**(0.0으로 채우면 원 호출과
    다른 조건에서 재고 "재현 불가"라고 말하게 된다).
    """

    prompt: str
    system: str
    seed: int
    model_name: str
    temperature: float | None = None


@dataclass(slots=True, frozen=True)
class ReplayOutcome:
    """재투입 1건의 결과 — 판정 + 출력 지문(전문 대신 sha256)."""

    replay_input: ReplayInput
    digests: tuple[str, ...]
    verdict: ReplayVerdict
    error: str | None = None


def replay_input_from_log(log: GenerationLog) -> ReplayInput:
    """기록 → 재투입 좌표. 좌표가 불완전하면 **사유와 함께 거부**한다(조용히 건너뛰지 않는다).

    거부 사유는 셋뿐이며 서로 다른 뜻이다:
      - seed 미기록 → 애초에 재현 좌표가 없는 기록(클라우드·호출 없음·스레딩 이전 과거분).
      - 스냅샷 없음 → 구판 기록(EOS-55 이전).
      - 프롬프트/시스템 전문 없음 → 스냅샷이 해시만 담은 형태(자기완결 계약 위반).
    """
    if log.seed is None:
        raise ReplayInputError("seed 미기록 — 재현 좌표 없음(클라우드·호출 없음·스레딩 이전)")
    snapshot = log.input_snapshot
    if not isinstance(snapshot, dict):
        raise ReplayInputError("input_snapshot 없음 — 구판 기록(EOS-55 좌석 이전)")
    prompt = snapshot.get("prompt")
    system = snapshot.get("system")
    if not isinstance(prompt, str) or not isinstance(system, str):
        raise ReplayInputError("스냅샷에 프롬프트/시스템 전문 없음 — 재투입 바이트 복원 불가")
    if log.model_name is None:
        raise ReplayInputError("model_name 미기록 — 어느 모델로 되먹일지 알 수 없음")
    raw_temperature = snapshot.get("temperature")
    temperature = float(raw_temperature) if isinstance(raw_temperature, (int, float)) else None
    return ReplayInput(
        prompt=prompt,
        system=system,
        seed=log.seed,
        model_name=log.model_name,
        temperature=temperature,
    )


def replay_inputs_from_logs(
    logs: Sequence[GenerationLog],
) -> tuple[list[ReplayInput], list[str]]:
    """기록 목록 → (재투입 좌표, 거부 사유). 사유는 버리지 않는다 — 분모가 왜 줄었는지의 근거다."""
    inputs: list[ReplayInput] = []
    reasons: list[str] = []
    for index, log in enumerate(logs, start=1):
        try:
            inputs.append(replay_input_from_log(log))
        except ReplayInputError as exc:
            reasons.append(f"record {index}: {exc}")
    return inputs, reasons


def classify_outputs(texts: Sequence[str]) -> ReplayVerdict:
    """출력 목록 → 판정. 2건 미만이면 **미측정**(비교 대상이 없다 — 성립으로 반올림 금지)."""
    if len(texts) < 2:
        return ReplayVerdict.UNMEASURED
    first = texts[0]
    return (
        ReplayVerdict.REPRODUCED
        if all(text == first for text in texts[1:])
        else ReplayVerdict.NOT_REPRODUCED
    )


def _digest(text: str) -> str:
    """출력 지문 — sha256 앞 12hex. 전문을 리포트에 싣지 않는 이유는 길이·소음이다."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def fixed_local_decision() -> RoutingDecision:
    """고정 모델 호출용 최소 LOCAL 결정 — `FixedModelOllamaProvider`의 티어 가드만 충족한다.

    이 결정의 패밀리·크기는 **쓰이지 않는다**(고정 provider가 `resolve_model`을 건너뛴다).
    실제 모델은 기록된 `model_name`이며, 그것이 이 프로브의 요점이다(모듈 docstring 라우터 메모).
    """
    return RoutingDecision(
        cost_tier=CostTier.LOCAL,
        local_family=ModelFamily.GENERAL,
        local_model=LocalModelTier.FAST,
        mode="sync",
        reason="EOS-73 재현 프로브 — 기록된 model_name 고정 호출(라우팅 재결정 없음)",
        # 추정 지연은 라우터 결정의 필수 필드지만 이 경로에서는 쓰이지 않는다(호출 인자 아님).
        est_latency_ms=0,
    )


def _live_provider_factory(model_id: str) -> LLMProvider:  # pragma: no cover — 라이브 경로
    """기록된 모델 ID를 고정 호출하는 라이브 provider(지연 import — CI에 ollama 없음)."""
    from whymath_backend.l3.providers.ollama import FixedModelOllamaProvider

    return FixedModelOllamaProvider(model_id)


async def probe_one(
    replay_input: ReplayInput,
    *,
    repeat: int,
    provider_factory: Callable[[str], LLMProvider] | None = None,
) -> ReplayOutcome:
    """좌표 1건을 `repeat`회 재투입하고 판정한다 — 호출 실패는 흡수하되 **타입명을 남긴다**.

    `provider_factory(model_name)`는 provider를 만드는 시임이다(테스트가 가짜를 주입). None이면
    `FixedModelOllamaProvider`(라이브 Ollama). 실패 시 판정은 `미측정`이다 — 호출이 안 된 것을
    "재현 불가"로 적으면 인프라 장애가 모델 비결정성으로 위장된다(측정 실패 ≠ 측정 결과).
    """
    factory = provider_factory if provider_factory is not None else _live_provider_factory
    provider = factory(replay_input.model_name)
    decision = fixed_local_decision()
    texts: list[str] = []
    for _ in range(repeat):
        try:
            generated = await provider.generate(
                replay_input.prompt,
                replay_input.system,
                decision,
                temperature=replay_input.temperature,
                seed=replay_input.seed,
            )
        except Exception as exc:  # noqa: BLE001 — 측정 실패를 결과로 위장하지 않는다(타입명 보존)
            return ReplayOutcome(
                replay_input=replay_input,
                digests=tuple(_digest(text) for text in texts),
                verdict=ReplayVerdict.UNMEASURED,
                error=f"provider.generate failed: {type(exc).__name__}: {exc}",
            )
        texts.append(generated.text)
    return ReplayOutcome(
        replay_input=replay_input,
        digests=tuple(_digest(text) for text in texts),
        verdict=classify_outputs(texts),
    )


def render_report(
    outcomes: Sequence[ReplayOutcome],
    *,
    skipped: Sequence[str] = (),
    repeat: int = 2,
) -> str:
    """재투입 결과를 마크다운으로 렌더(순수). 측정 0건이면 **자인 문구**를 낸다."""
    reproduced = sum(1 for o in outcomes if o.verdict is ReplayVerdict.REPRODUCED)
    not_reproduced = sum(1 for o in outcomes if o.verdict is ReplayVerdict.NOT_REPRODUCED)
    unmeasured = sum(1 for o in outcomes if o.verdict is ReplayVerdict.UNMEASURED)
    measured = reproduced + not_reproduced
    lines: list[str] = [
        "# 결정론 재생성 프로브 (EOS-73 ③)",
        "",
        "> 관측 프로브다 — **exit 게이트가 아니다**. '재현 불가'는 실패가 아니라 *측정 결과*이며,",
        "> 그 경우 재현 계약은 '재현 불가 자인'으로 축소된다(통과 위장 금지).",
        "> 재는 것은 *재현 대 재현*이다 — 원 기록의 출력은 저장되지 않으므로 대조 대상이 아니다.",
        "",
        f"- 회당 반복 호출: **{repeat}회**",
        f"- 재투입 시도: **{len(outcomes)}건** (좌표 복원 실패 {len(skipped)}건은 아래 §3)",
        "",
        "## 1. 판정",
        "",
        f"- 재현(전 회차 바이트 동일): **{reproduced}**",
        f"- 재현 불가(회차 간 출력 상이): **{not_reproduced}**",
        f"- 미측정(호출 실패·비교 대상 부족): **{unmeasured}**",
        "",
    ]
    if measured == 0:
        lines += [
            f"> **이 배포의 '같은 seed → 같은 출력'은 {DETERMINISM_CLAIM_UNMEASURED}다.**",
            "> 측정 0건은 성립도 불성립도 아니다 — 라이브 Ollama에서 이 프로브를 돌려야"
            " 값이 생긴다.",
            "",
        ]
    elif not_reproduced > 0:
        lines += [
            "> ⚠ 재현 불가가 관측됐다 — 이 배포에서 seed 고정은 **출력 동일을 보증하지 않는다**.",
            "> 재현 계약은 '기록된 좌표로 같은 조건에서 재시도할 수 있다'까지로 축소된다"
            "(바이트 동일 재생성 아님).",
            "",
        ]
    lines += [
        "## 2. 기록별",
        "",
        "| 모델 | seed | 온도 | 판정 | 출력 지문(sha256 12hex) | 오류 |",
        "|---|---:|---|---|---|---|",
    ]
    for outcome in outcomes:
        temperature = outcome.replay_input.temperature
        temperature_label = "-" if temperature is None else f"{temperature}"
        digests = ", ".join(outcome.digests) or "-"
        lines.append(
            f"| `{outcome.replay_input.model_name}` | {outcome.replay_input.seed} | "
            f"{temperature_label} | {outcome.verdict.value} | {digests} | "
            f"{outcome.error or '-'} |"
        )
    lines += ["", "## 3. 좌표 복원 실패 (재투입 자체가 불가한 기록)", ""]
    if skipped:
        lines += [f"- {reason}" for reason in skipped]
    else:
        lines.append("- 없음")
    lines.append("")
    return "\n".join(lines)


def report_to_json(
    outcomes: Sequence[ReplayOutcome], *, skipped: Sequence[str] = (), repeat: int = 2
) -> dict[str, Any]:
    """결과 → JSON 직렬화 가능 dict."""
    measured = [o for o in outcomes if o.verdict is not ReplayVerdict.UNMEASURED]
    return {
        "repeat": repeat,
        "attempted": len(outcomes),
        "reproduced": sum(1 for o in outcomes if o.verdict is ReplayVerdict.REPRODUCED),
        "not_reproduced": sum(1 for o in outcomes if o.verdict is ReplayVerdict.NOT_REPRODUCED),
        "unmeasured": sum(1 for o in outcomes if o.verdict is ReplayVerdict.UNMEASURED),
        # 측정 0건은 비율이 아니라 자인 문구다(0%로 위장 금지).
        "determinism_claim": (
            DETERMINISM_CLAIM_UNMEASURED if not measured else f"측정 {len(measured)}건 기준"
        ),
        "skipped": list(skipped),
        "outcomes": [
            {
                "model_name": o.replay_input.model_name,
                "seed": o.replay_input.seed,
                "temperature": o.replay_input.temperature,
                "verdict": o.verdict.value,
                "digests": list(o.digests),
                "error": o.error,
            }
            for o in outcomes
        ],
    }


async def _run(  # pragma: no cover — 라이브 Ollama 왕복
    paths: Sequence[Path], *, limit: int, repeat: int
) -> tuple[list[ReplayOutcome], list[str]]:
    logs: list[GenerationLog] = []
    parse_errors: list[str] = []
    for path in paths:
        file_logs, file_errors = load_generation_logs_jsonl(path)
        logs.extend(file_logs)
        parse_errors.extend(f"{path}: {reason}" for reason in file_errors)
    inputs, skipped = replay_inputs_from_logs(logs)
    outcomes = [await probe_one(item, repeat=repeat) for item in inputs[:limit]]
    return outcomes, [*skipped, *parse_errors]


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — **0=측정 완료(재현 여부 무관) / 2=측정 불가(입력·파일 오류)**."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.generation_seed_replay_probe",
        description=(
            "결정론 재생성 프로브(EOS-73 ③) — 기록된 seed·입력 전문을 되먹여 회차 간 출력 동일성을"
            " 측정한다. 라이브 Ollama 필요. 게이트 아님(exit 0/2)."
        ),
    )
    parser.add_argument("genlog", nargs="+", type=Path, help="GenerationLog JSONL 경로(들)")
    parser.add_argument(
        "--limit", type=int, default=3, help="재투입할 기록 수 상한(기본 3 — 라이브 비용·시간 보호)"
    )
    parser.add_argument(
        "--repeat", type=int, default=2, help="좌표당 반복 호출 횟수(기본 2 — 최소 비교 단위)"
    )
    parser.add_argument(
        "--json", dest="json_path", type=Path, default=None, help="JSON 산출물 경로"
    )
    args = parser.parse_args(argv)

    if args.repeat < 2:
        print(
            "측정 불가 — --repeat은 2 이상이어야 한다(1회는 비교 대상이 없어 '미측정'만 난다).",
            file=sys.stderr,
        )
        return _EXIT_INPUT_ERROR
    try:
        outcomes, skipped = asyncio.run(_run(args.genlog, limit=args.limit, repeat=args.repeat))
    except Exception as exc:  # noqa: BLE001 — 입력 오류는 타입명과 함께 보고하고 exit 2
        print(f"측정 불가 — 재현 프로브 실패({type(exc).__name__}): {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    print(render_report(outcomes, skipped=skipped, repeat=args.repeat))
    if args.json_path is not None:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(
                report_to_json(outcomes, skipped=skipped, repeat=args.repeat),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"JSON 산출물: {args.json_path}")
    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
