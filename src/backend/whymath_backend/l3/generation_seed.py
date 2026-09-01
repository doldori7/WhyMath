"""생성 재현 seed 정책 — *어느 경로가* seed를 실을 수 있고 *값을 어디서* 얻는가 (EOS-73).

**존재 이유**: `GenerationLog.seed`(EOS-55가 만든 BigInteger 좌석)는 착지 이후 **전 경로
NULL**이었다 — 좌석은 있는데 값이 전무한 *무작동* 상태다. 코드 자신이 그 사실을 세 곳에서
자인하고 있었다(`db/models/provenance.py` seed 컬럼 주석·`pregenerate/prewarmer._emit_
generation_log`·`pregenerate/provenance_bridge.generation_log_from_result` docstring).
좌석을 채우려면 두 가지를 정해야 한다 — ① 어떤 provider가 seed를 *물리적으로* 받는가
② 그 값을 어떻게 고르는가. 이 모듈이 그 둘의 **단일 좌석**이고, 쓰기측(생성 경로)과
읽기측(적재율 리포트 `harness/generation_seed_adoption_report`)이 같은 정의를 본다.

──────────────────────────────────────────────────────────────────────────
**① 경로별 지원 — 구조적 사실이지 정책 선택이 아니다(날조 금지)**

  | cost_tier        | provider          | seed        | 근거 |
  |------------------|-------------------|-------------|------|
  | LOCAL            | `OllamaProvider`  | **지원**    | ollama generate `options.seed`(llama.cpp 샘플러 시드) |
  | CLOUD_MID/HIGH   | `AnthropicProvider` | **구조적 불가** | Messages API에 seed 파라미터 자체가 없다(`messages.create(model,max_tokens,system,messages)`+temperature) |

클라우드 경로는 값을 **지어내지 않고 NULL(미기록)을 유지**한다. "우리가 뽑아 둔 숫자"를
seed 컬럼에 적으면 그 행은 *재현 가능하다고 거짓말하는 행*이 된다 — 모델에 전달된 적이
없는 숫자이므로 재투입해도 아무것도 재현하지 않는다. EOS-55가 세운 정직 원칙의 승계다.

**② 값의 출처 — 호출마다 새로 뽑고, 뽑은 값을 기록한다**

두 후보가 있었다:
  (a) 입력 스냅샷에서 결정론 유도(해시 → seed).
  (b) 호출마다 난수 추출 후 *기록*.
채택은 **(b)**다. 재현 계약("기록된 seed를 재투입하면 같은 출력")은 양쪽 모두 만족하지만,
(a)는 **같은 입력에 대해 항상 같은 출력**을 강제해 동등문제 저작 경로(temperature=0.9로
mode collapse를 방어하는 `l3/equivalent/llm_generator`)의 다양성을 구조적으로 죽인다 —
같은 스펙으로 n건을 뽑는 배치가 n개의 동일 문항을 내게 된다. 재현은 *기록된 seed를 되먹이는
쪽*(replay)이 담당하고, 생성은 매번 새 seed를 뽑는다. 되먹이는 좌석이 `SeedSource`
주입이다(테스트·재현 프로브가 고정 seed를 넣는다).

**범위**: `[SEED_MIN, SEED_MAX] = [0, 2**31-1]`. DB 좌석은 int64(BigInteger)지만 llama.cpp의
샘플러 시드는 uint32라 그 범위를 넘는 값은 *조용히 접힐* 수 있다(같은 seed를 기록해 두고
다른 seed로 호출되는 최악의 침묵 실패). 좌석보다 좁게 뽑아 그 창을 원천 차단한다.

**계층 메모**: 이 모듈은 L3 CORE다 — 라우터 결정(축1)만 읽고 수학 의미론을 모른다. 라우터
자체는 건드리지 않는다(`Router.route`는 순수·결정론이며, 거기에 난수를 심으면 결정 자체가
재현 불가가 된다). seed는 *결정*이 아니라 *호출 인자*이므로 호출부에서 뽑아 provider로 흐른다
— "모든 LLM 호출은 라우터 경유" 원칙은 그대로다(경유 지점은 여전히 `Router.route`).
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from enum import Enum
from typing import Final

from whymath_backend.config import Settings, get_settings
from whymath_backend.l3.models import CostTier, RoutingDecision
from whymath_backend.l3.router import LOCAL_MODEL_MATRIX, QUALITY_MODEL_ID, _as_cost_tier

__all__ = [
    "SEED_MAX",
    "SEED_MIN",
    "SeedCapability",
    "SeedSource",
    "capability_for_model",
    "default_seed_source",
    "draw_seed",
    "seed_for_decision",
    "seed_supported",
]

# 추출 범위 — 모듈 docstring "범위" 참조(int64 좌석보다 좁은 uint32 안전창).
SEED_MIN: Final[int] = 0
SEED_MAX: Final[int] = 2**31 - 1

# seed 공급자 계약 — 인자 없이 int 하나를 돌려준다. 기본은 난수(`default_seed_source`)이고,
# 재현 프로브·테스트는 기록된 seed를 그대로 돌려주는 고정 공급자를 주입한다.
SeedSource = Callable[[], int]


def draw_seed() -> int:
    """[SEED_MIN, SEED_MAX] 범위의 seed 1개 추출 (기본 공급자의 본체).

    `secrets`를 쓰는 이유는 보안이 아니라 **전역 난수 상태와의 분리**다 — `random` 전역을
    쓰면 테스트가 `random.seed()`로 고정한 상태를 이 추출이 소모해 *다른 테스트의* 난수열을
    밀어 버린다(순서 의존 오염). 여기서 재현이 필요한 쪽은 항상 `SeedSource` 주입으로 값을
    고정하므로, 기본 공급자가 재현 가능할 필요는 없다.
    """
    return SEED_MIN + secrets.randbelow(SEED_MAX - SEED_MIN + 1)


def default_seed_source() -> SeedSource:
    """기본 seed 공급자 — 호출마다 새 난수(`draw_seed`)."""
    return draw_seed


def seed_supported(decision: RoutingDecision) -> bool:
    """이 라우팅 결정이 seed를 *실제로 모델에 전달할 수 있는* 경로인가.

    LOCAL(Ollama `options.seed`)만 True다. CLOUD_MID/HIGH는 Anthropic Messages API에 seed
    파라미터가 없어 **구조적 불가**이며, 그 사실을 True로 반올림하지 않는다(모듈 docstring ①).
    """
    return _as_cost_tier(decision.cost_tier) is CostTier.LOCAL


def seed_for_decision(
    decision: RoutingDecision,
    *,
    source: SeedSource | None = None,
) -> int | None:
    """결정에 실어 보낼 seed — 지원 경로면 값 1개, 미지원 경로면 **None(미기록)**.

    `source=None`이면 기본 난수 공급자(`default_seed_source`)를 쓴다. 반환된 값은 호출부가
    ① provider에 전달하고 ② *같은 값을* GenerationLog.seed에 기록해야 한다 — 둘이 어긋나면
    기록이 재현을 보장하지 못한다(그 정합은 `tests/backend/l3/test_generation_seed.py`가 동결).
    """
    if not seed_supported(decision):
        return None
    drawn = (source if source is not None else default_seed_source())()
    if not SEED_MIN <= drawn <= SEED_MAX:
        # 주입 공급자가 범위를 벗어난 값을 주면 *조용히 자르지 않고* 거부한다 — 자르면 기록된
        # seed와 전달된 seed가 달라져 재현 계약이 무성의하게 깨진다(침묵 실패 금지).
        raise ValueError(
            f"seed는 [{SEED_MIN}, {SEED_MAX}] 범위여야 한다(받은 값 범위 밖) — "
            "llama.cpp 샘플러 시드는 uint32라 범위 밖 값은 조용히 접힐 수 있다."
        )
    return drawn


class SeedCapability(str, Enum):
    """읽기측(적재율 리포트) 분류 — 기록된 `model_name`으로 되짚는 seed 지원 여부.

    쓰기 시점의 `cost_tier`는 GenerationLog에 남지 않는다(모델명만 남는다). 그래서 읽기측은
    모델명을 라우터 매트릭스·설정에 대조해 되짚는다. 되짚지 못하는 이름은 `UNKNOWN`으로 두고
    지원/불가 어느 쪽으로도 반올림하지 않는다 — 미상을 지원으로 반올림하면 분모가 부풀어
    적재율이 실제보다 낮게 보이고, 불가로 반올림하면 진짜 회귀가 "원래 안 되는 경로"로 숨는다.
    """

    SUPPORTED = "지원"
    UNSUPPORTED = "구조적 불가"
    UNKNOWN = "미상"


def capability_for_model(
    model_name: str | None,
    *,
    settings: Settings | None = None,
) -> SeedCapability:
    """기록된 모델명 → seed 지원 분류(읽기측 단일 좌석).

    - 라우터 로컬 매트릭스(`LOCAL_MODEL_MATRIX` 값 + `QUALITY_MODEL_ID`) = **지원**.
      매트릭스에 모델이 추가되면 이 분류가 자동으로 따라간다(정본 1개).
    - 설정의 Anthropic 모델(`anthropic_model_mid`/`high`) = **구조적 불가**.
    - 그 외(강등전 고정 모델·구판 기록·오배선) = **미상**.
    """
    if model_name is None:
        return SeedCapability.UNKNOWN
    if model_name in set(LOCAL_MODEL_MATRIX.values()) or model_name == QUALITY_MODEL_ID:
        return SeedCapability.SUPPORTED
    resolved = settings if settings is not None else get_settings()
    if model_name in {resolved.anthropic_model_mid, resolved.anthropic_model_high}:
        return SeedCapability.UNSUPPORTED
    return SeedCapability.UNKNOWN
