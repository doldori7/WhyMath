"""잔여 축 교차검증 게이트 강등전 — 실 결함 주입 검출률 측정 (S4-16 · S4-13 게이트 승격 조건).

정본: `docs/architecture/problem_bank_gap_review.md` §3 D7 ⑵(잔여 축은 K≥3 독립 다관점
LLM 교차검증) + `docs/standards/superhuman_verification_standard.md` §3.1-3.2(강등전
방법론 — 결함을 우리가 의도로 주입해 정답지를 100% 확보한 뒤, 그 시험지를 검출기에 태워
검출률·오검출률을 *측정*으로 낸다). `l3/equivalent/defect_seeder.py` +
`harness/defect_detection_eval.py`가 SymPy 결정론 검증기 도메인의 선례라면, 이 모듈은
**검출기 자체가 LLM**(결정론 대체 불가)인 D7 도메인의 판이다.

이 모듈이 재사용하는 것(재구현하지 않는다 — 단일 진실 원천 유지):
  - `residue_cross_verify_eval.py::PilotRecord`/`load_pilot_records`/`select_sample`
    — 코퍼스 로딩·결정론 표본 추출.
  - `l3.finite_probability::parse_finite_model`/`enumerate_model`/`describe_model_ko`
    — 기계 모델 조립(발문은 변조해도 조건식·정답은 원본 그대로 유지 — 결함은 "발문이 더 이상
    기계 모델을 정확히 지시하지 못한다"는 것이지 기계 모델 자체를 건드리는 게 아니다).
  - `l3.cross_verify::CrossVerifier`/`ResidueSubject`/`CrossVerificationResult`
    — K=3 교차검증기와 그 자체 집계 규칙(`aggregate` 필드 — 여기서 재구현하지 않는다).
  - `harness.wilson::wilson_lower_bound`/`wilson_upper_bound` — Wilson 단측 신뢰경계.

이 모듈이 새로 만드는 것: 결함 4종의 **결정론 발문 변조기**(정답지는 변조 함수 자체가 곧
증거 — 인간 라벨 0건) + 결함 주입 셋/무결함 대조군 배터리 조립 + K=3 검증기 배선(주입 가능) +
결함류별·전체 검출률 Wilson 하한 + 대조군 오검출 Wilson 상한 집계 + 리포트/게이트 CLI.

**정직한 불균등 커버리지**(설계 명시 — 균일 N을 위해 억지 변조를 만들지 않는다):
  - `missing_condition`(조건 결측·"서로 구별되는 " 제거) — A·C·D만 적용(코인 그룹 B의 문장은
    애초 구별성 어구를 담지 않는다 — **실측 재검증 결과 25/34**, 최초 설계 메모의 "전 34건"
    주장은 코퍼스 실측과 불일치해 이 구현이 실측값으로 정정한다).
  - `unstated_equiprobability`(등확률 미명시) — A·B만 20/34(C·D는 애초 이 어구를 서술하지
    않음).
  - `ambiguous_wording`(중의성) — A·B·C만 26/34(D는 "이상" 어구 제거가 중의성이 아니라 문제
    자체를 바꿔버리므로 깨끗한 단어 단위 변조가 없어 제외).
  - `multiple_valid_answers`(복수 정답) — C만 6/34("동시에" 제거가 표본공간 모델을 실제로
    바꾸는 것은 공 추출뿐 — 주사위 동시/순차 던지기는 같은 36경우 모델이라 변조가 무의미).

사용(라이브 LLM 필요 — hermetic 배선 검증은 fake verifier로 테스트에서 수행):
    python -m whymath_backend.harness.residue_gate_demotion_battle \\
        data/corpus/problem_bank_probability_finite_v0/problems.jsonl \\
        --sample-n 5 --audit-out battle_audit.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from whymath_backend.config import Settings, get_settings
from whymath_backend.harness.residue_cross_verify_eval import (
    PilotRecord,
    load_pilot_records,
    select_sample,
)
from whymath_backend.harness.wilson import wilson_lower_bound, wilson_upper_bound
from whymath_backend.l3.cross_verify import (
    MISSING_CONDITION_PERSPECTIVES,
    MULTIPLE_VALID_ANSWERS_PERSPECTIVES,
    PROBABILITY_PERSPECTIVES,
    CrossVerifier,
    PerspectiveVerdict,
    ResidueSubject,
)
from whymath_backend.l3.finite_probability import (
    FiniteProbabilityError,
    describe_model_ko,
    enumerate_model,
    parse_finite_model,
)
from whymath_backend.l3.interfaces import LLMProvider
from whymath_backend.l3.models import CostTier, GenerationResult, RoutingDecision, Usage
from whymath_backend.l3.providers.lemonade import LemonadeProvider
from whymath_backend.l3.providers.ollama import OllamaProvider, _OllamaClient

__all__ = [
    "RESIDUE_DEFECT_CLASSES",
    "ResidueDefectClass",
    "SeededResidueItem",
    "ResidueBattery",
    "ClassDetection",
    "ResidueBattleReport",
    "RepeatedResidueBattleReport",
    "build_residue_seeded_set",
    "run_residue_demotion_battle",
    "run_repeated_residue_demotion_battle",
    "render_report",
    "render_repeated_report",
    "report_to_json",
    "repeated_report_to_json",
    "write_audit_jsonl",
    "write_repeated_audit_jsonl",
]

_EXIT_OK = 0
_EXIT_GATE_FAIL = 1

# 결함 4종 — D7 명세(발문 조건 결측·중의성·등확률 미명시·복수 정답)와 1:1.
ResidueDefectClass = Literal[
    "missing_condition",
    "unstated_equiprobability",
    "ambiguous_wording",
    "multiple_valid_answers",
]
RESIDUE_DEFECT_CLASSES: tuple[ResidueDefectClass, ...] = (
    "missing_condition",
    "unstated_equiprobability",
    "ambiguous_wording",
    "multiple_valid_answers",
)


class _FixedModelOllamaProvider(OllamaProvider):
    """강등전 전용 — 라우터가 고른 모델 대신 고정 모델 ID로 호출하는 Ollama provider.

    S4-16은 "실 provider"로 게이트를 승격하되, 운영 모델(현재 qwen3.5:27b)이 로컬
    인프라에서 timeout으로 실측 불가일 때 더 가벼운 모델(예: qwen2.5:7b)로 측정할
    수 있게 한다. 이는 **측정 대상 모델의 대표성을 희생하는 대신 실행 가능성을 확보**
    하는 선택이며, 측정치는 하한 추정으로 해석한다.
    """

    def __init__(
        self,
        model_id: str,
        *,
        timeout: float | None = None,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        settings: Any = None,
    ) -> None:
        super().__init__(settings=settings)
        self._model_id = model_id
        self._timeout = timeout
        self._num_ctx = num_ctx
        self._num_predict = num_predict

    def _get_client(self) -> _OllamaClient:
        """클라이언트 지연 해석 — timeout 오버라이드 지원."""
        if self._client is None:
            settings = self._resolved_settings
            settings_timeout = settings.ollama_request_timeout_s
            timeout = self._timeout if self._timeout is not None else settings_timeout
            try:
                from ollama import AsyncClient
            except ImportError as exc:  # pragma: no cover — ollama 미설치 환경
                raise RuntimeError(
                    "ollama Python 클라이언트가 설치되지 않았습니다. "
                    "`pip install ollama` 후 다시 시도하세요."
                ) from exc
            client = AsyncClient(
                host=settings.ollama_host,
                timeout=timeout,
            )
            self._client = cast(_OllamaClient, client)
        return self._client

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        """고정 모델 ID로 생성한다 — `resolve_model`을 생략한다(그 외는 부모와 동일)."""
        if decision.cost_tier != CostTier.LOCAL.value:
            raise ValueError(
                "_FixedModelOllamaProvider는 로컬 결정만 처리한다"
                f"(받은 cost_tier={decision.cost_tier})."
            )
        call_kwargs: dict[str, Any] = {
            "model": self._model_id,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        if images is not None:
            call_kwargs["images"] = images
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if self._num_ctx is not None:
            options["num_ctx"] = self._num_ctx
        if self._num_predict is not None:
            options["num_predict"] = self._num_predict
        if options:
            call_kwargs["options"] = options
        if json_schema is not None:
            call_kwargs["format"] = dict(json_schema)
        client = self._get_client()
        start = time.monotonic()
        response = await client.generate(**call_kwargs)
        latency_ms = (time.monotonic() - start) * 1000.0
        text = ""
        if hasattr(response, "response"):
            text = response.response if isinstance(response.response, str) else ""
        elif isinstance(response, dict):
            text = response.get("response", "") if isinstance(response.get("response"), str) else ""
        input_tokens = None
        output_tokens = None
        if hasattr(response, "prompt_eval_count"):
            val = response.prompt_eval_count
            input_tokens = val if isinstance(val, int) and val >= 0 else None
        elif isinstance(response, dict):
            val = response.get("prompt_eval_count")
            input_tokens = val if isinstance(val, int) and val >= 0 else None
        if hasattr(response, "eval_count"):
            val = response.eval_count
            output_tokens = val if isinstance(val, int) and val >= 0 else None
        elif isinstance(response, dict):
            val = response.get("eval_count")
            output_tokens = val if isinstance(val, int) and val >= 0 else None
        return GenerationResult(
            text=text,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
            ),
        )


class _FixedModelOpenRouterProvider:
    """S4-16 강등전 전용 — OpenRouter(OpenAI-Compatible API)로 고정 모델을 호출하는 임시 provider.

    OpenRouter는 `/api/v1/models`로 300+ 모델을 노출하며, 특히 수학/추론 벤치에서 강한
    qwen/qwen3.8-max(intelligence 58.1·$2/$6)·deepseek/deepseek-v4-pro-0813(53.2·$0.4/$0.9)·
    google/gemini-3.7-flash(56.0·$0.4/$1.9) 등을 즉시 사용할 수 있다. S4-16은 K=3
    교차검증이 로컬 Ollama로 통과 불가(07-14 기록)하므로 *임시* 클라우드 후보를 태워
    강등전을 재개한다. 이 provider는 운영 라우터(CompositeProvider)에 연결되지 않고
    harness CLI의 `--openrouter-model`에서만 사용된다.

    인터페이스는 `interfaces.LLMProvider`와 동형이지만, 이 파일 내부에만 살며
    `cross_verify.CrossVerifier`의 `provider=` 인자로 주입된다.
    """

    def __init__(
        self,
        *,
        model_id: str | None = None,
        api_key: str | None = None,
        timeout_s: float | None = None,
        max_tokens: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._model_id = model_id or self._settings.openrouter_model_id
        self._api_key = api_key or self._settings.openrouter_api_key.get_secret_value()
        self._timeout_s = timeout_s or self._settings.openrouter_request_timeout_s
        self._max_tokens = max_tokens or self._settings.openrouter_max_tokens
        if not self._api_key:
            raise RuntimeError(
                "OpenRouter API 키가 설정되지 않았습니다. "
                "WHYMATH_OPENROUTER_API_KEY를 설정하거나 --openrouter-api-key를 지정하세요."
            )

    def _build_client(self) -> Any:
        """openai.AsyncOpenAI 클라이언트 생성 — 지연 import(CLAUDE.md lazy heavy deps)."""
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "openai Python 클라이언트가 설치되지 않았습니다. "
                "`pip install openai` 후 다시 시도하세요."
            ) from exc
        return AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self._api_key,
            timeout=self._timeout_s,
            default_headers={
                "HTTP-Referer": "https://whymath.ai",
                "X-Title": "WhyMath",
            },
        )

    @staticmethod
    def _extract_text(response: Any) -> str:
        """OpenAI-Compatible 응답에서 첫 번째 choice의 content를 추출한다."""
        choices: Any = None
        if hasattr(response, "choices"):
            choices = response.choices
        elif isinstance(response, dict):
            choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        message: Any = None
        if hasattr(first, "message"):
            message = first.message
        elif isinstance(first, dict):
            message = first.get("message")
        if message is None:
            return ""
        if hasattr(message, "content"):
            return message.content if isinstance(message.content, str) else ""
        if isinstance(message, dict):
            content = message.get("content")
            return content if isinstance(content, str) else ""
        return ""

    @staticmethod
    def _coerce_token_count(value: Any) -> int | None:
        """usage 토큰 값을 int|None으로 방어적 정규화 — 비정상 타입·음수는 None."""
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value if value >= 0 else None

    def _extract_usage(self, response: Any, latency_ms: float) -> Usage:
        """OpenAI-Compatible usage에서 prompt/completion 토큰을 추출한다."""
        raw_usage: Any = None
        if hasattr(response, "usage"):
            raw_usage = response.usage
        elif isinstance(response, dict):
            raw_usage = response.get("usage")
        input_tokens: int | None = None
        output_tokens: int | None = None
        if raw_usage is not None:
            if hasattr(raw_usage, "prompt_tokens"):
                input_tokens = self._coerce_token_count(raw_usage.prompt_tokens)
            elif isinstance(raw_usage, dict):
                input_tokens = self._coerce_token_count(raw_usage.get("prompt_tokens"))
            if hasattr(raw_usage, "completion_tokens"):
                output_tokens = self._coerce_token_count(raw_usage.completion_tokens)
            elif isinstance(raw_usage, dict):
                output_tokens = self._coerce_token_count(raw_usage.get("completion_tokens"))
        return Usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    async def generate(
        self,
        prompt: str,
        system: str,
        decision: RoutingDecision,
        *,
        images: Sequence[str] | None = None,
        temperature: float | None = None,
        json_schema: Mapping[str, object] | None = None,
    ) -> GenerationResult:
        """OpenRouter로 고정 모델 ID로 생성한다 — decision의 cost_tier는 무시(임시 경로)."""
        _ = decision  # S4-16은 fixed model override이므로 라우터 결정 무시
        if images is not None:
            raise NotImplementedError(
                "_FixedModelOpenRouterProvider는 멀티모달 이미지를 지원하지 않는다"
            )
        client = self._build_client()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        call_kwargs: dict[str, Any] = {
            "model": self._model_id,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "stream": False,
        }
        if temperature is not None:
            call_kwargs["temperature"] = temperature
        if json_schema is not None:
            call_kwargs["response_format"] = {"type": "json_object"}
        start = time.monotonic()
        response = await client.chat.completions.create(**call_kwargs)
        latency_ms = (time.monotonic() - start) * 1000.0
        text = self._extract_text(response)
        usage = self._extract_usage(response, latency_ms)
        return GenerationResult(text=text, usage=usage)


# ──────────────────────────────────────────────────────────────────────────
# 결정론 발문 변조기 — 각 (원본 텍스트) → (변조 텍스트, 변조 기록) | None(비적용).
# 적용 여부는 *부분 문자열 실재*로 판정한다(그룹 색인 하드코딩 금지 — 코퍼스가 같은 문체로
# 재생성돼 건수가 바뀌어도 이 판정은 그대로 성립한다). 실재하지 않으면 정직하게 None —
# 억지 변조로 정답지를 오염시키지 않는다.
# ──────────────────────────────────────────────────────────────────────────

_MISSING_CONDITION_TARGET = "서로 구별되는 "


def _mutate_missing_condition(text: str) -> tuple[str, str] | None:
    """① 조건 결측 — 구별성 어구 제거. 이 어구가 없는 문장(코인 그룹)은 비적용."""
    if _MISSING_CONDITION_TARGET not in text:
        return None
    mutated = text.replace(_MISSING_CONDITION_TARGET, "", 1)
    return mutated, f"조건 결측: {_MISSING_CONDITION_TARGET!r} 제거(구별 가능 전제 소실)"


_EQUIPROB_DICE = "각 주사위의 여섯 눈이 나올 가능성이 모두 같을 때, "
_EQUIPROB_COIN = "매번 앞면과 뒷면이 나올 가능성이 같을 때, "


def _mutate_unstated_equiprobability(text: str) -> tuple[str, str] | None:
    """② 등확률 미명시 — 명시적 등확률 절 제거. A(주사위)·B(동전)만 이 절을 서술한다."""
    for target in (_EQUIPROB_DICE, _EQUIPROB_COIN):
        if target in text:
            mutated = text.replace(target, "", 1)
            return mutated, f"등확률 미명시: {target!r} 제거(균등분포 가정 미서술)"
    return None


_AMBIG_SUM_RE = re.compile(r"두 눈의 수의 합이 (\d+)일")
_AMBIG_EXACT_COUNT = "앞면이 정확히 "
_AMBIG_ALL_RED = "꺼낸 공이 모두 빨간 공일"


def _mutate_ambiguous_wording(text: str) -> tuple[str, str] | None:
    """③ 중의성 — 그룹별 참조 범위 축소 단어 제거(그룹 D는 깨끗한 변조 없어 의도적 제외).

    - A: "…의 합이 N일" → "…가 N일"("합" 소실 — 두 눈의 합인지 한 눈의 수인지 모호해짐).
    - B: "정확히 " 제거("정확히 M번"→"M번" — 정확히 M번인지 M번 이상인지 모호해짐).
    - C: "모두 " 제거("모두 빨간 공"→"빨간 공" — 전부 빨간지 일부인지 모호해짐).
    - D: 비적용(설계 명시 — "이상" 제거는 중의성이 아니라 문제 자체의 변경).
    """
    match = _AMBIG_SUM_RE.search(text)
    if match is not None:
        mutated = _AMBIG_SUM_RE.sub(r"두 눈의 수가 \1일", text, count=1)
        return mutated, "중의성: '의 합' 소실(두 눈의 수의 합이 N일 → 두 눈의 수가 N일)"
    if _AMBIG_EXACT_COUNT in text:
        mutated = text.replace(_AMBIG_EXACT_COUNT, "앞면이 ", 1)
        return mutated, f"중의성: {_AMBIG_EXACT_COUNT!r} 제거(정확히 M번 vs M번 이상 모호)"
    if _AMBIG_ALL_RED in text:
        mutated = text.replace(_AMBIG_ALL_RED, "꺼낸 공이 빨간 공일", 1)
        return mutated, "중의성: '모두' 제거(전부 빨간지 일부인지 모호)"
    return None


_MULTI_ANSWER_TARGET = "동시에 꺼낼 때"


def _mutate_multiple_valid_answers(text: str) -> tuple[str, str] | None:
    """④ 복수 정답 — 공 추출 그룹(C)에서만 "동시에" 제거가 모델을 실제로 바꾼다.

    주사위(A·D)는 "동시에"를 지워도 두 주사위 36경우 모델이 그대로다(무의미 변조 — 정답지
    오염 방지를 위해 의도적으로 배제). 공 추출은 "동시에"가 "비복원·무순서 추출" 모델을
    지시하는 유일한 단서라, 제거하면 순차/복원 추출이라는 방어 가능한 대안 해석이 생겨
    수치적으로 다른 확률이 나온다 — 진짜 복수 정답 결함.
    """
    if _MULTI_ANSWER_TARGET in text:
        mutated = text.replace(_MULTI_ANSWER_TARGET, "꺼낼 때", 1)
        return mutated, "복수 정답: '동시에' 제거(비복원·무순서 추출 가정 소실 → 대안 해석 발생)"
    return None


_MUTATORS: dict[ResidueDefectClass, Callable[[str], tuple[str, str] | None]] = {
    "missing_condition": _mutate_missing_condition,
    "unstated_equiprobability": _mutate_unstated_equiprobability,
    "ambiguous_wording": _mutate_ambiguous_wording,
    "multiple_valid_answers": _mutate_multiple_valid_answers,
}


@dataclass(frozen=True, slots=True)
class SeededResidueItem:
    """결함 주입 시험지 1문 — 원본 레코드 + 결함류 + 변조된 발문 + 변조 기록(감사용)."""

    record: PilotRecord
    defect_class: ResidueDefectClass
    mutated_question_text: str
    mutation_note: str


@dataclass(frozen=True, slots=True)
class ResidueBattery:
    """강등전 시험지 배터리 — 결함 주입 셋(결함류 전 적용 가능 건) + 무결함 대조군.

    `coverage`는 *표본 추출 이전* 전체 코퍼스 기준 결함류별 적용 가능 건수 — 정직한 회계
    산출물이다(적용 불가 결함류는 0으로 명시, 침묵 생략이 아니다).
    """

    seeded: tuple[SeededResidueItem, ...]
    clean: tuple[PilotRecord, ...]
    coverage: dict[ResidueDefectClass, int]


def build_residue_seeded_set(records: Sequence[PilotRecord]) -> ResidueBattery:
    """로드된 파일럿 레코드 → 결함 주입 시험지 배터리(순수·결정론·LLM 0·발문만 변조).

    `answer`·`verify.conditions`는 절대 건드리지 않는다 — 기계가 검산한 "의도된" 정답은
    그대로 두고, 발문만 그 의도를 더 이상 정확히 지시하지 못하게 흐린다. 결함류마다 코퍼스
    전건을 스캔해 적용 가능한 레코드만 싣는다(부분 문자열 실재 판정 — 그룹 색인 하드코딩 0).
    """
    seeded: list[SeededResidueItem] = []
    coverage: dict[ResidueDefectClass, int] = {name: 0 for name in RESIDUE_DEFECT_CLASSES}
    for defect_class in RESIDUE_DEFECT_CLASSES:
        mutator = _MUTATORS[defect_class]
        for record in records:
            result = mutator(record.question_text)
            if result is None:
                continue
            mutated_text, note = result
            coverage[defect_class] += 1
            seeded.append(
                SeededResidueItem(
                    record=record,
                    defect_class=defect_class,
                    mutated_question_text=mutated_text,
                    mutation_note=note,
                )
            )
    return ResidueBattery(seeded=tuple(seeded), clean=tuple(records), coverage=coverage)


def _select_sample_items(
    items: Sequence[SeededResidueItem], *, sample_n: int, seed: str
) -> list[SeededResidueItem]:
    """결정론 표본 추출 — `residue_cross_verify_eval.select_sample`과 동형 해시 정렬 규칙.

    (defect_class, slug) 복합 키로 해시해, 같은 slug가 여러 결함류에 걸쳐 나와도 결함류별
    독립 표본이 된다.
    """
    if sample_n <= 0:
        return []
    ordered = sorted(
        items,
        key=lambda item: hashlib.sha256(
            f"{seed}:{item.defect_class}:{item.record.slug}".encode()
        ).hexdigest(),
    )
    return list(ordered[:sample_n])


def _build_subject(
    record: PilotRecord, *, question_text: str, authored_by: str
) -> ResidueSubject | str:
    """검증 대상 조립 — 기계 모델은 *원본* conditions에서(변조는 question_text에만 반영).

    모델 조립 실패는 사유 문자열(호출자가 측정 실패로 집계) — 파일럿 코퍼스는 이미 S4-13에서
    기계 축을 통과했으므로 실전에서는 발생하지 않을 것으로 예상되나, 방어적으로 처리한다.
    """
    try:
        model = parse_finite_model(record.conditions)
        result = enumerate_model(model)
    except FiniteProbabilityError as exc:
        return f"{record.slug}: 형식 모델 조립 실패({type(exc).__name__}) {exc}"
    return ResidueSubject(
        problem_id=record.slug,
        question_text=question_text,
        answer=record.answer,
        answer_explanation=record.answer_explanation,
        machine_model_ko=describe_model_ko(model, result),
        machine_total=result.total,
        machine_favorable=result.favorable,
        authored_by=authored_by,
    )


@dataclass(frozen=True, slots=True)
class ClassDetection:
    """결함류 1개의 검출 집계 — 표본·판정·검출·판정불가 + Wilson 하한."""

    defect_class: ResidueDefectClass
    sampled: int
    resolved: int
    detected: int
    unresolved: int
    model_failures: tuple[str, ...] = ()

    def detection_lower_bound(self, confidence: float = 0.95) -> float | None:
        """검출률 Wilson 단측 하한 — 판정 가능 표본 0이면 None(NO_DATA, 0.0으로 위장 금지)."""
        if self.resolved == 0:
            return None
        return wilson_lower_bound(self.detected, self.resolved, confidence)


@dataclass(frozen=True, slots=True)
class _AuditRow:
    """감사 JSONL 1행 — 문항·역할(seeded/clean)·결함류·변조기록·검증 결과.

    `aggregate_reason`은 K=3 관점의 집계 사유(보수적 판정의 근거)이고,
    `verdicts`는 개별 관점 판정(향후 오검출/판정불가 원인 추적용)이다.
    """

    problem_id: str
    role: Literal["seeded", "clean"]
    defect_class: str | None
    mutation_note: str
    aggregate: str
    aggregate_reason: str = ""
    verdicts: tuple[PerspectiveVerdict, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ResidueBattleReport:
    """강등전 결과 — 결함류별 검출 + 전체 검출 Wilson 하한 + 대조군 오검출 Wilson 상한.

    `coverage`(배터리에서 물려받음)는 표본 추출 *이전* 전체 코퍼스 기준 적용 가능 건수이고,
    `per_class`의 `sampled`는 실제로 검증기에 태운 건수(`--sample-n`으로 제한된 실측 표본)다
    — 이 둘을 섞지 않는다(적용 가능 모집단 vs 실측 표본은 다른 숫자).
    """

    per_class: dict[ResidueDefectClass, ClassDetection]
    coverage: dict[ResidueDefectClass, int]
    overall_detected: int
    overall_resolved: int
    overall_unresolved: int
    clean_false_alarms: int
    clean_resolved: int
    clean_unresolved: int
    clean_sampled: int
    audit_rows: tuple[_AuditRow, ...] = field(default_factory=tuple)

    def overall_detection_lower_bound(self, confidence: float = 0.95) -> float | None:
        if self.overall_resolved == 0:
            return None
        return wilson_lower_bound(self.overall_detected, self.overall_resolved, confidence)

    def false_alarm_upper_bound(self, confidence: float = 0.95) -> float | None:
        if self.clean_resolved == 0:
            return None
        return wilson_upper_bound(self.clean_false_alarms, self.clean_resolved, confidence)


@dataclass(frozen=True, slots=True)
class RepeatedResidueBattleReport:
    """반복 실행된 강등전 결과 — 평균/최악/표준편차/판정불가율을 함께 제공한다."""

    reports: tuple[ResidueBattleReport, ...]
    confidence: float
    corpus_size: int
    sample_n: int
    repeat_runs: int
    seed: str

    @property
    def per_class_reports(self) -> dict[ResidueDefectClass, tuple[ClassDetection, ...]]:
        """결함류별로 반복 실행의 ClassDetection을 모은다."""
        result: dict[ResidueDefectClass, list[ClassDetection]] = {
            name: [] for name in RESIDUE_DEFECT_CLASSES
        }
        for report in self.reports:
            for name in RESIDUE_DEFECT_CLASSES:
                detection = report.per_class.get(name)
                if detection is not None:
                    result[name].append(detection)
        return {name: tuple(items) for name, items in result.items()}


def run_residue_demotion_battle(
    battery: ResidueBattery,
    *,
    verifier: CrossVerifier | Mapping[ResidueDefectClass, CrossVerifier],
    clean_verifier: CrossVerifier | None = None,
    sample_n: int = 5,
    seed: str = "S4-16",
    authored_by: str | None = None,
) -> ResidueBattleReport:
    """배터리를 K=3 검증기에 태워 결함류별·전체 검출 + 대조군 오검출을 집계(순수 조합).

    `verifier`가 Mapping이면 결함류별로 서로 다른 관점 세트를 사용한다.
    `clean_verifier`가 지정되면 무결함 대조군은 이 verifier로 검증하며, None이면
    Mapping일 때는 `ambiguous_wording` verifier, 단일 verifier일 때는 그것을 사용한다.

    "검출"(seeded) = `verifier.verify(subject).aggregate == "defect"`.
    "오검출"(clean) = 무결함 대상인데도 `aggregate == "defect"`.
    "판정불가"(unresolved) = `aggregate == "unclear"` - 측정 실패로 분리 집계(0건 검출로
    위장하지 않는다). K=3 집계 규칙 자체는 `l3.cross_verify`가 이미 내린 결과를 그대로
    쓴다(여기서 재구현하지 않는다).
    """
    by_class: dict[ResidueDefectClass, list[SeededResidueItem]] = {
        name: [] for name in RESIDUE_DEFECT_CLASSES
    }
    for item in battery.seeded:
        by_class[item.defect_class].append(item)

    # 결함류별 verifier 해석 — Mapping이면 결함류별로, 아니면 단일 verifier를 모든 결함류에
    # 사용한다. Mapping이 아닌 대역 verifier(_ScriptedVerifier 등)도 단일처럼 처리.
    class_verifiers: Mapping[ResidueDefectClass, CrossVerifier]
    single_verifier: CrossVerifier | None = None
    if isinstance(verifier, Mapping):
        class_verifiers = verifier
        # clean 대조군용 기본 verifier: ambiguous_wording 관점이 v2/v3에서 가장 안정적이었음.
        single_verifier = verifier.get("ambiguous_wording") or next(iter(verifier.values()))
    else:
        class_verifiers = {name: verifier for name in RESIDUE_DEFECT_CLASSES}
        single_verifier = verifier
    clean_v = clean_verifier or single_verifier

    per_class: dict[ResidueDefectClass, ClassDetection] = {}
    audit_rows: list[_AuditRow] = []
    overall_detected = overall_resolved = overall_unresolved = 0

    for defect_class in RESIDUE_DEFECT_CLASSES:
        sample = _select_sample_items(by_class[defect_class], sample_n=sample_n, seed=seed)
        detected = unresolved = 0
        model_failures: list[str] = []
        class_verifier = class_verifiers.get(defect_class) or single_verifier
        for item in sample:
            subject = _build_subject(
                item.record,
                question_text=item.mutated_question_text,
                authored_by=authored_by or item.record.authored_by,
            )
            if isinstance(subject, str):
                model_failures.append(subject)
                continue
            result = class_verifier.verify(subject)
            audit_rows.append(
                _AuditRow(
                    problem_id=item.record.slug,
                    role="seeded",
                    defect_class=defect_class,
                    mutation_note=item.mutation_note,
                    aggregate=result.aggregate,
                    aggregate_reason=result.reason,
                    verdicts=result.verdicts,
                )
            )
            if result.aggregate == "unclear":
                unresolved += 1
            elif result.aggregate == "defect":
                detected += 1
        resolved = len(sample) - unresolved - len(model_failures)
        per_class[defect_class] = ClassDetection(
            defect_class=defect_class,
            sampled=len(sample),
            resolved=resolved,
            detected=detected,
            unresolved=unresolved,
            model_failures=tuple(model_failures),
        )
        overall_detected += detected
        overall_resolved += resolved
        overall_unresolved += unresolved

    clean_sample = select_sample(list(battery.clean), sample_n=sample_n, seed=seed)
    false_alarms = clean_unresolved = 0
    clean_model_failures: list[str] = []
    for record in clean_sample:
        subject = _build_subject(
            record,
            question_text=record.question_text,
            authored_by=authored_by or record.authored_by,
        )
        if isinstance(subject, str):
            clean_model_failures.append(subject)
            continue
        result = clean_v.verify(subject)
        audit_rows.append(
            _AuditRow(
                problem_id=record.slug,
                role="clean",
                defect_class=None,
                mutation_note="",
                aggregate=result.aggregate,
                aggregate_reason=result.reason,
                verdicts=result.verdicts,
            )
        )
        if result.aggregate == "unclear":
            clean_unresolved += 1
        elif result.aggregate == "defect":
            false_alarms += 1
    clean_resolved = len(clean_sample) - clean_unresolved - len(clean_model_failures)

    return ResidueBattleReport(
        per_class=per_class,
        coverage=dict(battery.coverage),
        overall_detected=overall_detected,
        overall_resolved=overall_resolved,
        overall_unresolved=overall_unresolved,
        clean_false_alarms=false_alarms,
        clean_resolved=clean_resolved,
        clean_unresolved=clean_unresolved,
        clean_sampled=len(clean_sample),
        audit_rows=tuple(audit_rows),
    )


def run_repeated_residue_demotion_battle(
    battery: ResidueBattery,
    *,
    verifier: CrossVerifier | Mapping[ResidueDefectClass, CrossVerifier],
    clean_verifier: CrossVerifier | None = None,
    sample_n: int = 5,
    seed: str = "S4-16",
    authored_by: str | None = None,
    repeat_runs: int = 1,
    corpus_size: int = 0,
    confidence: float = 0.95,
) -> RepeatedResidueBattleReport:
    """동일 배터리를 동일 조건으로 여러 번 실행해 평균/최악/변동성을 산출한다.

    OpenRouter 등 외부 provider의 추론이 비결정적일 수 있으므로, 단일 실행 결과가 아닌
    반복 실행의 통계량으로 모델/프롬프트의 안정성을 평가한다.
    """
    if repeat_runs < 1:
        raise ValueError(f"repeat_runs는 1 이상이어야 한다(받은 값={repeat_runs}).")
    reports: list[ResidueBattleReport] = []
    for _ in range(repeat_runs):
        report = run_residue_demotion_battle(
            battery,
            verifier=verifier,
            clean_verifier=clean_verifier,
            sample_n=sample_n,
            seed=seed,
            authored_by=authored_by,
        )
        reports.append(report)
    return RepeatedResidueBattleReport(
        reports=tuple(reports),
        confidence=confidence,
        corpus_size=corpus_size,
        sample_n=sample_n,
        repeat_runs=repeat_runs,
        seed=seed,
    )


def write_audit_jsonl(path: Path, report: ResidueBattleReport) -> int:
    """감사 JSONL — 문항별 판정 행 + as-found 병기 요약(§4.5 합격 로트 무결성 동형)."""

    def _verdict_payload(v: PerspectiveVerdict) -> dict[str, object]:
        return {
            "principle": v.principle,
            "verdict": v.verdict,
            "defect_class": v.defect_class,
            "reason": v.reason,
        }

    lines = [
        json.dumps(
            {
                "problem_id": row.problem_id,
                "role": row.role,
                "defect_class": row.defect_class,
                "mutation_note": row.mutation_note,
                "aggregate": row.aggregate,
                "aggregate_reason": row.aggregate_reason,
                "verdicts": [_verdict_payload(v) for v in row.verdicts],
            },
            ensure_ascii=False,
        )
        for row in report.audit_rows
    ]
    if report.audit_rows:
        lines.append(
            json.dumps(
                {
                    "as_found_overall_detected": report.overall_detected,
                    "as_found_overall_resolved": report.overall_resolved,
                    "as_found_clean_false_alarms": report.clean_false_alarms,
                    "as_found_clean_resolved": report.clean_resolved,
                },
                ensure_ascii=False,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
    return len(lines)


def write_repeated_audit_jsonl(path: Path, repeated: RepeatedResidueBattleReport) -> int:
    """반복 실행 감사 JSONL - run별 문항별 판정 행 + as-found 병기 요약."""

    def _verdict_payload(v: PerspectiveVerdict) -> dict[str, object]:
        return {
            "principle": v.principle,
            "verdict": v.verdict,
            "defect_class": v.defect_class,
            "reason": v.reason,
        }

    lines: list[str] = []
    for run_index, report in enumerate(repeated.reports, start=1):
        for row in report.audit_rows:
            lines.append(
                json.dumps(
                    {
                        "run": run_index,
                        "problem_id": row.problem_id,
                        "role": row.role,
                        "defect_class": row.defect_class,
                        "mutation_note": row.mutation_note,
                        "aggregate": row.aggregate,
                        "aggregate_reason": row.aggregate_reason,
                        "verdicts": [_verdict_payload(v) for v in row.verdicts],
                    },
                    ensure_ascii=False,
                )
            )
        if report.audit_rows:
            lines.append(
                json.dumps(
                    {
                        "run": run_index,
                        "as_found_overall_detected": report.overall_detected,
                        "as_found_overall_resolved": report.overall_resolved,
                        "as_found_clean_false_alarms": report.clean_false_alarms,
                        "as_found_clean_resolved": report.clean_resolved,
                    },
                    ensure_ascii=False,
                )
            )
    if not lines:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _mean(values: Sequence[float | int | None]) -> float | None:
    """None을 제외한 값의 산술평균 — 값이 없으면 None."""
    nums = [float(v) for v in values if v is not None]
    return statistics.mean(nums) if nums else None


def _stdev(values: Sequence[float | int | None]) -> float | None:
    """None을 제외한 값의 표본표준편차 — 2개 미만이면 None."""
    nums = [float(v) for v in values if v is not None]
    return statistics.stdev(nums) if len(nums) >= 2 else None


def _min_value(values: Sequence[float | int | None]) -> float | None:
    """None을 제외한 값의 최솟값 — 값이 없으면 None."""
    nums = [float(v) for v in values if v is not None]
    return min(nums) if nums else None


def _max_value(values: Sequence[float | int | None]) -> float | None:
    """None을 제외한 값의 최댓값 — 값이 없으면 None."""
    nums = [float(v) for v in values if v is not None]
    return max(nums) if nums else None


def render_report(
    report: ResidueBattleReport, *, confidence: float = 0.95, corpus_size: int
) -> str:
    """사람 가독 리포트 — 커버리지(모집단)·검출(표본)·전체·대조군·보정 제안을 분리해 보여준다."""
    pct = round(confidence * 100)
    lines = [
        "=" * 68,
        "잔여 축 교차검증 게이트 강등전 - 결함 주입 검출률 측정 (S4-16 - D7)",
        "=" * 68,
        f"[커버리지 — 코퍼스 전체({corpus_size}건) 기준 결함류별 적용 가능 건수]",
    ]
    for name in RESIDUE_DEFECT_CLASSES:
        n = report.coverage.get(name, 0)
        if n == 0:
            lines.append(f"  {name:26s} 표본 없음(N=0/{corpus_size}) — 이 결함류는 적용 불가")
        else:
            lines.append(f"  {name:26s} {n}/{corpus_size}건 적용 가능")
    lines.append(f"[결함류별 검출 — 실 표본({pct}% Wilson 하한)]")
    for name in RESIDUE_DEFECT_CLASSES:
        detection = report.per_class.get(name)
        if detection is None or detection.sampled == 0:
            lines.append(f"  {name:26s} 표본 없음(N=0)")
            continue
        lower = detection.detection_lower_bound(confidence)
        lines.append(
            f"  {name:26s} 표본 {detection.sampled}건 판정 {detection.resolved}건 "
            f"검출 {detection.detected}건  하한 {_fmt(lower)}  판정불가 {detection.unresolved}건"
        )
    overall = report.overall_detection_lower_bound(confidence)
    fau = report.false_alarm_upper_bound(confidence)
    lines.append("[전체]")
    lines.append(
        f"  결함 검출률   : {report.overall_detected}/{report.overall_resolved} "
        f"({pct}% 하한 {_fmt(overall)})  판정불가 {report.overall_unresolved}건"
    )
    lines.append(
        f"  무결함 오검출 : {report.clean_false_alarms}/{report.clean_resolved} "
        f"({pct}% 상한 {_fmt(fau)})  판정불가 {report.clean_unresolved}건"
    )
    lines.append("[보정 제안 — residue_cross_verify_eval.py --max-defect-upper]")
    if fau is not None:
        lines.append(
            f"  측정된 오검출 Wilson 상한이 {fau:.4f}이므로 --max-defect-upper는 최소 "
            f"{fau:.4f} 이상이어야 노이즈와 실결함을 구분 가능(현재 기본값 0.05는 이 실측 "
            "이전의 근거 없는 초기값 — 실측치가 0.05를 넘으면 그 기본값 자체가 상시 FAIL을 "
            "낳는 잘못 캘리브레이션된 임계다)."
        )
    else:
        lines.append("  대조군 판정 표본이 없어(clean_resolved=0) 보정 제안 불가 — 측정 부족.")
    lines.append("=" * 68)
    return "\n".join(lines)


def render_repeated_report(
    repeated: RepeatedResidueBattleReport, *, confidence: float | None = None
) -> str:
    """반복 실행 리포트 - 평균/최악/표준편차/판정불가율을 함께 보여준다."""
    confidence = confidence or repeated.confidence
    pct = round(confidence * 100)
    reports = repeated.reports
    per_class_reports = repeated.per_class_reports

    lines = [
        "=" * 68,
        "잔여 축 교차검증 게이트 강등전 - 결함 주입 검출률 측정 " "(S4-16 - D7 - 반복 실행)",
        "=" * 68,
        f"[실행 조건] 표본 {repeated.sample_n}건 - 반복 {repeated.repeat_runs}회 - "
        f"시드 {repeated.seed}",
        f"[커버리지 - 코퍼스 전체({repeated.corpus_size}건) 기준 결함류별 적용 가능 건수]",
    ]

    coverage = reports[0].coverage if reports else {}
    for name in RESIDUE_DEFECT_CLASSES:
        n = coverage.get(name, 0)
        if n == 0:
            lines.append(
                f"  {name:26s} 표본 없음(N=0/{repeated.corpus_size}) - 이 결함류는 적용 불가"
            )
        else:
            lines.append(f"  {name:26s} {n}/{repeated.corpus_size}건 적용 가능")

    lines.append(f"[결함류별 검출 - 반복 평균({pct}% Wilson 하한)]")
    for name in RESIDUE_DEFECT_CLASSES:
        detections = per_class_reports.get(name, ())
        if not detections:
            lines.append(f"  {name:26s} 표본 없음(N=0)")
            continue
        detection_rates = [d.detected / d.resolved if d.resolved > 0 else None for d in detections]
        lower_bounds = [d.detection_lower_bound(confidence) for d in detections]
        unresolved_rates = [d.unresolved / d.sampled if d.sampled > 0 else None for d in detections]
        lines.append(
            f"  {name:26s} 검출률 평균 {_fmt(_mean(detection_rates))} "
            f"하한 평균 {_fmt(_mean(lower_bounds))} "
            f"최악 {_fmt(_min_value(lower_bounds))} "
            f"표준편차 {_fmt(_stdev(lower_bounds))} "
            f"판정불가율 {_fmt(_mean(unresolved_rates))}"
        )

    overall_detection_rates = [
        r.overall_detected / r.overall_resolved if r.overall_resolved > 0 else None for r in reports
    ]
    overall_lower_bounds = [r.overall_detection_lower_bound(confidence) for r in reports]
    overall_unresolved_rates = [
        (
            r.overall_unresolved / sum(r.per_class[n].sampled for n in RESIDUE_DEFECT_CLASSES)
            if any(r.per_class[n].sampled > 0 for n in RESIDUE_DEFECT_CLASSES)
            else None
        )
        for r in reports
    ]
    lines.append("[전체]")
    lines.append(
        f"  결함 검출률   : 평균 {_fmt(_mean(overall_detection_rates))} "
        f"({pct}% 하한 평균 {_fmt(_mean(overall_lower_bounds))} "
        f"최악 {_fmt(_min_value(overall_lower_bounds))} "
        f"표준편차 {_fmt(_stdev(overall_lower_bounds))}) "
        f"판정불가율 {_fmt(_mean(overall_unresolved_rates))}"
    )

    false_alarm_rates = [
        r.clean_false_alarms / r.clean_resolved if r.clean_resolved > 0 else None for r in reports
    ]
    false_alarm_upper_bounds = [r.false_alarm_upper_bound(confidence) for r in reports]
    clean_unresolved_rates = [
        r.clean_unresolved / r.clean_sampled if r.clean_sampled > 0 else None for r in reports
    ]
    lines.append(
        f"  무결함 오검출 : 평균 {_fmt(_mean(false_alarm_rates))} "
        f"({pct}% 상한 평균 {_fmt(_mean(false_alarm_upper_bounds))} "
        f"최악 {_fmt(_max_value(false_alarm_upper_bounds))} "
        f"표준편차 {_fmt(_stdev(false_alarm_upper_bounds))}) "
        f"판정불가율 {_fmt(_mean(clean_unresolved_rates))}"
    )

    lines.append("[보정 제안 - residue_cross_verify_eval.py --max-defect-upper]")
    worst_fau = _max_value(false_alarm_upper_bounds)
    if worst_fau is not None:
        lines.append(
            f"  측정된 최악 오검출 Wilson 상한이 {worst_fau:.4f}이므로 "
            f"--max-defect-upper는 최소 {worst_fau:.4f} 이상이어야 "
            "노이즈와 실결함을 구분 가능."
        )
    else:
        lines.append("  대조군 판정 표본이 없어(clean_resolved=0) 보정 제안 불가 - 측정 부족.")
    lines.append("=" * 68)
    return "\n".join(lines)


def report_to_json(report: ResidueBattleReport, *, confidence: float = 0.95) -> dict[str, object]:
    """리포트 → JSON 직렬화 가능 dict(CLI --audit-out과 별개로 리포트 자체를 기계 판독하려는
    소비처를 위한 산출 — 필드는 render_report와 1:1 대응)."""
    return {
        "coverage": dict(report.coverage),
        "per_class": {
            name: {
                "sampled": d.sampled,
                "resolved": d.resolved,
                "detected": d.detected,
                "unresolved": d.unresolved,
                "detection_lower_bound": d.detection_lower_bound(confidence),
            }
            for name, d in report.per_class.items()
        },
        "overall": {
            "detected": report.overall_detected,
            "resolved": report.overall_resolved,
            "unresolved": report.overall_unresolved,
            "detection_lower_bound": report.overall_detection_lower_bound(confidence),
        },
        "clean_control": {
            "sampled": report.clean_sampled,
            "resolved": report.clean_resolved,
            "false_alarms": report.clean_false_alarms,
            "unresolved": report.clean_unresolved,
            "false_alarm_upper_bound": report.false_alarm_upper_bound(confidence),
        },
    }


def repeated_report_to_json(
    repeated: RepeatedResidueBattleReport, *, confidence: float | None = None
) -> dict[str, Any]:
    """반복 리포트 → JSON — 평균/최악/표준편차/판정불가율을 기계 판독 가능하게 낸다."""
    confidence = confidence or repeated.confidence
    reports = repeated.reports
    per_class_reports = repeated.per_class_reports
    per_class_stats: dict[str, object] = {}
    for name in RESIDUE_DEFECT_CLASSES:
        detections = per_class_reports.get(name, ())
        if not detections:
            continue
        detection_rates = [d.detected / d.resolved if d.resolved > 0 else None for d in detections]
        lower_bounds = [d.detection_lower_bound(confidence) for d in detections]
        unresolved_rates = [d.unresolved / d.sampled if d.sampled > 0 else None for d in detections]
        per_class_stats[name] = {
            "runs": len(detections),
            "detection_rate_mean": _mean(detection_rates),
            "detection_lower_bound_mean": _mean(lower_bounds),
            "detection_lower_bound_worst": _min_value(lower_bounds),
            "detection_lower_bound_stdev": _stdev(lower_bounds),
            "abstention_rate_mean": _mean(unresolved_rates),
        }

    overall_detection_rates = [
        r.overall_detected / r.overall_resolved if r.overall_resolved > 0 else None for r in reports
    ]
    overall_lower_bounds = [r.overall_detection_lower_bound(confidence) for r in reports]
    overall_unresolved_rates = [
        (
            r.overall_unresolved / sum(r.per_class[n].sampled for n in RESIDUE_DEFECT_CLASSES)
            if any(r.per_class[n].sampled > 0 for n in RESIDUE_DEFECT_CLASSES)
            else None
        )
        for r in reports
    ]
    false_alarm_rates = [
        r.clean_false_alarms / r.clean_resolved if r.clean_resolved > 0 else None for r in reports
    ]
    false_alarm_upper_bounds = [r.false_alarm_upper_bound(confidence) for r in reports]
    clean_unresolved_rates = [
        r.clean_unresolved / r.clean_sampled if r.clean_sampled > 0 else None for r in reports
    ]
    return {
        "repeat_runs": repeated.repeat_runs,
        "sample_n": repeated.sample_n,
        "seed": repeated.seed,
        "confidence": confidence,
        "coverage": dict(reports[0].coverage) if reports else {},
        "per_class": per_class_stats,
        "overall": {
            "detection_rate_mean": _mean(overall_detection_rates),
            "detection_lower_bound_mean": _mean(overall_lower_bounds),
            "detection_lower_bound_worst": _min_value(overall_lower_bounds),
            "detection_lower_bound_stdev": _stdev(overall_lower_bounds),
            "abstention_rate_mean": _mean(overall_unresolved_rates),
        },
        "clean_control": {
            "false_alarm_rate_mean": _mean(false_alarm_rates),
            "false_alarm_upper_bound_mean": _mean(false_alarm_upper_bounds),
            "false_alarm_upper_bound_worst": _max_value(false_alarm_upper_bounds),
            "false_alarm_upper_bound_stdev": _stdev(false_alarm_upper_bounds),
            "abstention_rate_mean": _mean(clean_unresolved_rates),
        },
    }


def main(argv: list[str] | None = None) -> int:
    """강등전 CLI — 실 코퍼스 로드 → 배터리 조립 → K=3 검증 → 리포트. 게이트는 opt-in."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.residue_gate_demotion_battle",
        description=(
            "잔여 축 교차검증 게이트 강등전 — 결함 주입 셋 + 무결함 대조군으로 검출률·"
            "오검출률을 실측하고 --max-defect-upper 보정 제안을 낸다."
        ),
    )
    parser.add_argument("corpus", type=Path, help="파일럿 코퍼스 JSONL 경로.")
    parser.add_argument(
        "--sample-n",
        type=int,
        default=5,
        help="결함류별·대조군 표본 수(기본 5 — 실 provider 비용 통제. 결함류 4종 + 대조군 "
        "1종 × K=3 관점이라 기본값도 최대 ~75회 LLM 호출).",
    )
    parser.add_argument("--seed", default="S4-16", help="결정론적 표본 추출 시드(재현성 확보용).")
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="Wilson 신뢰구간 수준(기본 0.95).",
    )
    parser.add_argument(
        "--repeat-runs",
        type=int,
        default=1,
        help="동일 조건 반복 실행 횟수(기본 1). 1보다 크면 평균/최악/표준편차/"
        "판정불가율을 함께 리포트한다.",
    )
    parser.add_argument(
        "--min-detection-lower",
        type=float,
        default=0.0,
        help="전체 검출률 Wilson 하한 임계 — 미만이면 exit 1(기본 0=off).",
    )
    parser.add_argument(
        "--max-false-alarm-upper",
        type=float,
        default=1.0,
        help="대조군 오검출률 Wilson 상한 임계 — 초과면 exit 1(기본 1.0=off).",
    )
    parser.add_argument("--audit-out", type=Path, default=None, help="감사 JSONL 산출 경로.")
    parser.add_argument(
        "--authored-by",
        default=None,
        help="생성자 서명 override(검증자와 충돌 시 IndependenceError 회피용).",
    )
    parser.add_argument(
        "--local-model",
        default=None,
        help=(
            "로컬 Ollama 모델 ID 오버라이드(예: qwen2.5:7b). 라우터가 고른 모델 대신 "
            "고정 모델로 강등전을 실측한다 — 운영 모델이 로컬에서 timeout으로 실행 불가일 "
            "때 측정 가능성을 확보하는 선택이며, 측정치는 하한 추정으로 해석한다."
        ),
    )
    parser.add_argument(
        "--ollama-timeout",
        type=float,
        default=None,
        help=(
            "로컬 Ollama 호출 타임아웃(초). 설정하지 않으면 Settings의 "
            "ollama_request_timeout_s(기본 30)을 사용한다. qwen3.5:27b 등 대형 모델에서 "
            "timeout이 발생할 때 늘려 사용."
        ),
    )
    parser.add_argument(
        "--ollama-num-ctx",
        type=int,
        default=None,
        help=(
            "Ollama generate options.num_ctx 오버라이드. 긴 prompt/context에서 KV cache "
            "부족으로 실패할 때 늘려 사용(예: 8192)."
        ),
    )
    parser.add_argument(
        "--ollama-num-predict",
        type=int,
        default=None,
        help=(
            "Ollama generate options.num_predict 오버라이드. 모델이 응답을 너무 짧게 끊을 때 "
            "늘려 사용(예: 2048)."
        ),
    )
    parser.add_argument(
        "--openrouter-model",
        default=None,
        help=(
            "OpenRouter 모델 ID 오버라이드(예: qwen/qwen3.8-max). 설정되면 OpenRouter "
            "OpenAI-Compatible API로 강등전을 실행한다 — 로컬 Ollama가 통과 불가할 때 "
            "임시 클라우드 후보를 태우는 S4-16 전용 경로. WHYMATH_OPENROUTER_API_KEY "
            "또는 --openrouter-api-key가 필요하다."
        ),
    )
    parser.add_argument(
        "--openrouter-api-key",
        default=None,
        help="OpenRouter API 키. 환경변수 WHYMATH_OPENROUTER_API_KEY 대신 쓸 수 있다.",
    )
    parser.add_argument(
        "--openrouter-timeout",
        type=float,
        default=None,
        help="OpenRouter 호출 타임아웃(초). 미지정 시 WHYMATH_OPENROUTER_REQUEST_TIMEOUT_S.",
    )
    parser.add_argument(
        "--openrouter-max-tokens",
        type=int,
        default=None,
        help="OpenRouter max_tokens. 미지정 시 WHYMATH_OPENROUTER_MAX_TOKENS.",
    )
    parser.add_argument(
        "--v4",
        action="store_true",
        help=(
            "v4 결함류별 전용 관점 사용. missing_condition과 multiple_valid_answers에 "
            "adversarial verifier 관점을 적용하고 나머지 결함류는 v2 관점을 사용한다."
        ),
    )
    parser.add_argument(
        "--lemonade-model",
        default=None,
        help=(
            "Lemonade Server 모델 ID 오버라이드(예: Qwen3.5-35B-A3B-GGUF). 설정되면 "
            "Lemonade Server(OpenAI 호환 API·Vulkan 백엔드)로 강등전을 실행한다 — "
            "Ollama가 Windows+AMD GPU에서 CPU 추론을 하는 문제를 우회한다. "
            "Lemonade Server가 localhost:8000에서 가동 중이어야 한다."
        ),
    )
    parser.add_argument(
        "--lemonade-base-url",
        default=None,
        help="Lemonade Server API base URL(기본 http://localhost:8000/api/v1).",
    )
    args = parser.parse_args(argv)

    records = load_pilot_records(args.corpus)
    battery = build_residue_seeded_set(records)
    # 실 provider는 지연 연결(구성만으로 네트워크 0) — 실제 호출은 verify() 시점에 일어난다.
    provider: LLMProvider | None = None
    if args.lemonade_model is not None:
        provider = LemonadeProvider(
            model_id=args.lemonade_model,
            base_url=args.lemonade_base_url,
        )
    elif args.openrouter_model is not None:
        provider = _FixedModelOpenRouterProvider(
            model_id=args.openrouter_model,
            api_key=args.openrouter_api_key,
            timeout_s=args.openrouter_timeout,
            max_tokens=args.openrouter_max_tokens,
        )
    elif args.local_model is not None:
        provider = _FixedModelOllamaProvider(
            args.local_model,
            timeout=args.ollama_timeout,
            num_ctx=args.ollama_num_ctx,
            num_predict=args.ollama_num_predict,
        )

    if args.v4:
        # v4: 결함류별 전용 관점. missing_condition / multiple_valid_answers 는 adversarial
        # verifier, unstated_equiprobability / ambiguous_wording 은 v2 기본 관점을 그대로 둔다.
        base_provider = provider
        verifier: CrossVerifier | Mapping[ResidueDefectClass, CrossVerifier] = {
            "missing_condition": CrossVerifier(
                provider=base_provider, perspectives=MISSING_CONDITION_PERSPECTIVES
            ),
            "multiple_valid_answers": CrossVerifier(
                provider=base_provider, perspectives=MULTIPLE_VALID_ANSWERS_PERSPECTIVES
            ),
            "unstated_equiprobability": CrossVerifier(
                provider=base_provider, perspectives=PROBABILITY_PERSPECTIVES
            ),
            "ambiguous_wording": CrossVerifier(
                provider=base_provider, perspectives=PROBABILITY_PERSPECTIVES
            ),
        }
    elif provider is not None:
        verifier = CrossVerifier(provider=provider)
    else:
        verifier = CrossVerifier()
    if args.repeat_runs > 1:
        repeated = run_repeated_residue_demotion_battle(
            battery,
            verifier=verifier,
            sample_n=args.sample_n,
            seed=args.seed,
            authored_by=args.authored_by,
            repeat_runs=args.repeat_runs,
            corpus_size=len(records),
            confidence=args.confidence,
        )
        if isinstance(verifier, CrossVerifier):
            verifier.flush_trace()
        else:
            for v in verifier.values():
                v.flush_trace()
        if args.audit_out is not None:
            write_repeated_audit_jsonl(args.audit_out, repeated)
        report_text = render_repeated_report(repeated, confidence=args.confidence)
        # Windows 기본 터미널(cp949)에서 한국어가 깨지지 않도록 UTF-8로 강제 출력.
        if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding.lower() not in {
            "utf-8",
            "utf_8",
        }:
            sys.stdout.reconfigure(encoding="utf-8")
        print(report_text)

        exit_code = _EXIT_OK
        repeated_json = repeated_report_to_json(repeated, confidence=args.confidence)
        overall_stats = repeated_json["overall"]
        clean_stats = repeated_json["clean_control"]
        mean_dlb = overall_stats["detection_lower_bound_mean"]
        worst_fau = clean_stats["false_alarm_upper_bound_worst"]
        if args.min_detection_lower > 0.0 and (
            mean_dlb is None or mean_dlb < args.min_detection_lower
        ):
            exit_code = _EXIT_GATE_FAIL
        if args.max_false_alarm_upper < 1.0 and (
            worst_fau is None or worst_fau > args.max_false_alarm_upper
        ):
            exit_code = _EXIT_GATE_FAIL
        return exit_code

    report = run_residue_demotion_battle(
        battery,
        verifier=verifier,
        sample_n=args.sample_n,
        seed=args.seed,
        authored_by=args.authored_by,
    )
    if isinstance(verifier, CrossVerifier):
        verifier.flush_trace()
    else:
        for v in verifier.values():
            v.flush_trace()
    if args.audit_out is not None:
        write_audit_jsonl(args.audit_out, report)
    report_text = render_report(report, confidence=args.confidence, corpus_size=len(records))
    # Windows 기본 터미널(cp949)에서 한국어가 깨지지 않도록 UTF-8로 강제 출력.
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding.lower() not in {"utf-8", "utf_8"}:
        sys.stdout.reconfigure(encoding="utf-8")
    print(report_text)

    exit_code = _EXIT_OK
    dlb = report.overall_detection_lower_bound(args.confidence)
    if args.min_detection_lower > 0.0 and (dlb is None or dlb < args.min_detection_lower):
        exit_code = _EXIT_GATE_FAIL
    fau = report.false_alarm_upper_bound(args.confidence)
    if args.max_false_alarm_upper < 1.0 and (fau is None or fau > args.max_false_alarm_upper):
        exit_code = _EXIT_GATE_FAIL
    return exit_code


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트
    sys.exit(main())
