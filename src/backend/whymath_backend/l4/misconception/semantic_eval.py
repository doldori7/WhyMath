"""오개념 *의미 매칭* 측정 하니스 — 프로브셋 대비 recall·방향맹 FP를 측정(오프라인·비노출).

slice 107: 의미(임베딩) 매처(`semantic_matches`/`SemanticMatcher`)가 substring `diagnose`의
거짓음성(패러프레이즈·동의어)을 *얼마나* 메우는지, 그리고 임베딩 방향맹이 *올바른* 진술을
오개념으로 *얼마나* 잘못 끌어올리는지(거짓양성)를 **수치로** 잰다. 본 모듈은 게이트를 켜지
않는다 — `combined.py`의 플립 decision(coach가 의미 매처를 결합할지)을 *Kiki가 측정 후 확정*할
근거를 만드는 측정 도구다(`config.misconception_semantic_mode`는 무변경·기본 off 유지).

**비노출·오프라인**: 런타임/HTTP/DB 경로와 무관한 측정 도구다. L4 `semantic_matches`(의미 매칭)
+ `diagnose`(substring 기준선)를 *소비*만 한다(재구현 0·게이트·coach 무변경). 입력은 프로브셋
(프로덕션 패키지 데이터 `probes_v1.jsonl` — `probes.probes_path()`로 로드. 단일 source of
truth로 패키지 안에 둔다)이며, recall 프로브(틀린 진술·expected_id 설정·substring 회피)와
FP 프로브(*올바른* 진술·expected_id null·near_id 설정)를 한 파일에 담는다.

────────────────────────────────────────────────────────────────────────────
정직 스코프 (CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지")
────────────────────────────────────────────────────────────────────────────
의미 매처는 *후보를 넓힐* 뿐 *방향·부정·등치*를 못 가린다(matcher.py 모듈 docstring의 방향맹).
따라서 이 하니스는 두 축을 *분리해* 잰다: ① recall(틀린 진술을 의미로 잡는가·높을수록 좋음)과
② false-positive-rate(올바른 진술을 오개념으로 잘못 끌어올리는가·낮을수록 좋음). recall은 Wilson
**하한**(recall ≥ X 정직), FP는 Wilson **상한**(FP ≤ Y 보수)으로 보고해 작은 표본의 과신을 막는다.
플립 decision은 student-facing 틀린 개입이 #1 리스크(CLAUDE.md 의사결정 우선순위 1≫6)이므로 FP
상한을 *보수적으로* 본다 — 구체 임계(R·F)는 Kiki가 Phaiakes9 라이브 bge-m3로 측정 후 확정한다.

사용법:
    python -m whymath_backend.l4.misconception.semantic_eval <probes.jsonl> \
        [--threshold 0.55] [--sweep 0.4,0.5,0.55,0.6] [--min-recall X] [--max-fp Y]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.config import Settings, get_settings
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.diagnose import diagnose
from whymath_backend.l4.misconception.judge import (
    JudgeProtocol,
    JudgeVerdict,
    judge_verdicts,
)
from whymath_backend.l4.misconception.models import MisconceptionDomain
from whymath_backend.l4.misconception.semantic.matcher import SemanticMatcher
from whymath_backend.l4.misconception.semantic.provider import (
    EmbeddingProvider,
    build_provider,
)

_DEFAULT_TOP_K = 5
# 측정 임계값 — 기본은 Settings.misconception_semantic_threshold(보수적 0.55). 하니스는 임계값을
# *명시적으로* 받아(스윕·고정) recall/FP의 임계값 의존을 드러낸다(운영점 곡선).
_DEFAULT_THRESHOLD = 0.55


# ──────────────────────────────────────────────────────────────────────────
# 프로브 — 측정 하니스 입력(StepBreakLabel 미러)
# ──────────────────────────────────────────────────────────────────────────
class MisconceptionProbe(BaseModel):
    """의미 매칭 측정 프로브 1건 — recall 또는 FP(JSONL 한 줄·`StepBreakLabel` 미러).

    두 종류를 *expected_id/near_id*로 구분한다:
      - **recall 프로브**: `expected_id` 설정(잡혀야 할 오개념 id), `near_id` null. *틀린* 진술을
        substring signals를 피해(임베딩만 잡게) 패러프레이즈한 것 → 의미 매처가 `expected_id`를
        끌어올리면 성공(`caught_by_semantic`).
      - **FP 프로브**: `expected_id` null, `near_id` 설정(겨냥한 방향맹 대상 id). *올바른* 진술
        (해당 오개념과 주제만 가까움)이라 *아무 오개념이나* 매칭되면 거짓양성
        (`semantic_false_positive`), 그중 `near_id`가 끌리면 *겨냥한* 방향맹(`near_false_positive`).

    `kind`는 프로브 유형 라벨(paraphrase/direction-reverse/negation/correct-near) — 분해 집계용.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    statement: str = Field(..., description="학생 진술(recall=틀림·FP=올바름)")
    expected_id: str | None = Field(
        default=None, description="recall 프로브에서 잡혀야 할 misconception.id(FP면 null)"
    )
    near_id: str | None = Field(
        default=None, description="FP 프로브에서 겨냥한 방향맹 대상 id(recall이면 null)"
    )
    kind: str = Field(
        ..., description="프로브 유형(paraphrase/direction-reverse/negation/correct-near)"
    )
    note: str = Field(default="", description="프로브 근거 메모(평가 미사용)")

    @property
    def is_recall_probe(self) -> bool:
        """recall 프로브 여부 — expected_id가 있으면 recall(틀린 진술을 잡아야 함)."""
        return self.expected_id is not None

    @property
    def is_fp_probe(self) -> bool:
        """FP 프로브 여부 — expected_id가 없으면 FP(올바른 진술·매칭되면 거짓양성)."""
        return self.expected_id is None


def load_probes(path: Path) -> list[MisconceptionProbe]:
    """JSONL 파일(한 줄당 MisconceptionProbe JSON) → 리스트. 빈 줄·`#` 주석 무시.

    파싱 오류는 line 번호와 함께 ValueError로 던진다(`step_shadow_eval.load_labels` 동형).
    UTF-8 고정(한국어 진술).
    """
    text = path.read_text(encoding="utf-8")
    probes: list[MisconceptionProbe] = []
    for line_num, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            probes.append(MisconceptionProbe.model_validate_json(stripped))
        except Exception as exc:  # noqa: BLE001 — 줄 번호 컨텍스트와 함께 재던짐
            raise ValueError(f"line {line_num}: {exc}") from exc
    return probes


# ──────────────────────────────────────────────────────────────────────────
# 프로브 1건 평가 결과(LabeledOutcome 미러)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class JudgeDecision:
    """프로브 1건의 후보 1개에 대한 judge 판정 기록 — 감사·리포트용(불변).

    `misconception_id`(판정 대상 후보)·`verdict`(expresses/not_expresses/uncertain)·
    `reason`(judge가 낸 한 줄 근거·학생 비노출). 어떤 후보를 *왜* 유지/제거했는지 사람이 눈으로
    확인하는 단위 — JSON 리포트에 후보별로 실린다(판정근거 캐처).
    """

    misconception_id: str
    verdict: str
    reason: str


@dataclass(slots=True, frozen=True)
class ProbeOutcome:
    """프로브 1건 평가 결과 — 의미 매처·substring 기준선의 매칭 id + 파생 판정. 불변.

    `semantic_ids`는 의미 매처가 threshold↑로 낸 id들(유사도 내림차순), `substring_ids`는 `diagnose`
    기준선이 낸 id들(보통 ~0이라 의미 매처의 *순기여*를 드러낸다). 파생 판정은 프로브 종류별:
      - recall 프로브: `caught_by_semantic` = expected_id ∈ semantic_ids.
      - FP 프로브: `semantic_false_positive` = bool(semantic_ids)(*아무* 오개념이나 끌어올림)·
        `near_false_positive` = near_id ∈ semantic_ids(*겨냥한* 방향맹).

    **judge 필드(슬108)**: `judge_kept_ids`/`judge_removed_ids`는 LLM-judge가 `semantic_ids` 중
    *유지*(예·불확실)/*제거*(아니오)한 것이다(judge 미적용 시 기본 빈 튜플 — 슬107 동작 불변).
    judge가 적용됐으면 `judge_kept_ids ⊕ judge_removed_ids = semantic_ids`(분할). 파생 judge 판정:
      - FP 프로브: `judge_false_positive` = judge 통과(kept)한 semantic_ids가 *남았나*(judge 후 FP).
      - recall 프로브: `judge_kept_expected` = expected_id가 *judge를 통과*했나(judge 후 recall TP).
    """

    probe: MisconceptionProbe
    semantic_ids: tuple[str, ...]
    substring_ids: tuple[str, ...]
    # judge 적용 결과(슬108·미적용 시 기본 빈 튜플=슬107 동작 불변). judge가 semantic_ids를
    # 유지/제거로 분할한 것. `run_probes_with_judge`만 채우고 sync `run_probes`는 비운다.
    judge_kept_ids: tuple[str, ...] = ()
    judge_removed_ids: tuple[str, ...] = ()
    # judge 판정 근거(판정근거 캐처) — semantic_ids 각 후보의 (id, verdict, reason). judge 미적용
    # 시 빈 튜플(슬107 동작 불변). `run_probes_with_judge`만 채운다(sync `run_probes`는 비움).
    judge_decisions: tuple[JudgeDecision, ...] = ()

    @property
    def caught_by_semantic(self) -> bool:
        """recall 프로브: 기대 오개념을 의미 매처가 잡았는가(FP 프로브면 항상 False)."""
        eid = self.probe.expected_id
        return eid is not None and eid in self.semantic_ids

    @property
    def caught_by_substring(self) -> bool:
        """recall 프로브: 기대 오개념을 substring 기준선이 잡았는가(순기여 대조용)."""
        eid = self.probe.expected_id
        return eid is not None and eid in self.substring_ids

    @property
    def semantic_false_positive(self) -> bool:
        """FP 프로브: 올바른 진술에 *아무* 오개념이나 끌려 올라왔는가(recall 프로브면 False)."""
        return self.probe.is_fp_probe and bool(self.semantic_ids)

    @property
    def near_false_positive(self) -> bool:
        """FP 프로브: *겨냥한* 방향맹 대상(near_id)이 끌려 올라왔는가(recall 프로브면 False)."""
        nid = self.probe.near_id
        return self.probe.is_fp_probe and nid is not None and nid in self.semantic_ids

    @property
    def substring_false_positive(self) -> bool:
        """FP 프로브: substring 기준선이 올바른 진술을 오개념으로 잘못 잡았는가(기준선 대조)."""
        return self.probe.is_fp_probe and bool(self.substring_ids)

    # ── judge 파생(슬108·judge 적용 시만 유의미) ──────────────────────────────
    @property
    def judge_false_positive(self) -> bool:
        """FP 프로브: judge 후에도 *남은*(kept) semantic_ids가 있는가(judge 후 거짓양성).

        judge가 `아니오`로 거른 뒤에도 통과한 후보가 있으면 judge 후 FP다. judge 미적용이면
        kept가 비어 항상 False(슬107 경로엔 영향 0 — judge 지표는 judge 적용 시만 읽는다).
        """
        return self.probe.is_fp_probe and bool(self.judge_kept_ids)

    @property
    def judge_kept_expected(self) -> bool:
        """recall 프로브: expected_id가 *judge를 통과*(kept)했는가(judge 후 recall TP).

        의미 매처가 expected_id를 끌어올린(`caught_by_semantic`) 뒤 judge가 그것을 *유지*해야
        judge 후 recall로 인정된다. judge가 expected_id를 `아니오`로 잘못 거르면 recall 손실
        (`judge_recall_loss`의 단위). judge 미적용이면 kept가 비어 항상 False.
        """
        eid = self.probe.expected_id
        return eid is not None and eid in self.judge_kept_ids


def _div(numer: int, denom: int) -> float | None:
    """0 나눗셈 보수 — 분모 0이면 None(비율 미정). step_shadow_eval._div 동형."""
    return numer / denom if denom else None


def _wilson_lower_bound(successes: int, trials: int, confidence: float) -> float:
    """이항비율의 **Wilson score 단측 신뢰하한**(confidence 수준).

    `step_shadow_eval._wilson_lower_bound`와 동일 공식(중심−마진·[0,1] 하한 클램프). recall ≥ X를
    정직하게 보고할 때 쓴다(작은 표본일수록 점추정보다 크게 깎임). successes=0이면 0.0 자연 도출.
    trials>0은 호출자가 보장. `statistics.NormalDist`(stdlib)로 z 산출·외부 의존성 0.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    z = statistics.NormalDist().inv_cdf(confidence)
    n = float(trials)
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(phat * (1.0 - phat) / n + z2 / (4.0 * n * n))
    return max(0.0, center - margin)


def _wilson_upper_bound(successes: int, trials: int, confidence: float) -> float:
    """이항비율의 **Wilson score 단측 신뢰상한**(confidence 수준) — slice 107 신규.

    `_wilson_lower_bound`와 *같은 Wilson 공식*(같은 center·margin)에서 `center + margin`(상측)을
    취하고 [0,1]로 상한 클램프한다(step_shadow엔 하한만 있었음). **FP ≤ Y를 보수적으로** 보고할
    때 쓴다 — 작은 표본에서 관측 FP가 0이어도 상한은 0보다 커(예: 0/10·95% → ≈0.21) "FP가 낮다"를
    과신하지 않게 한다(student-facing 틀린 개입 #1 리스크·CLAUDE.md). successes=trials면 대수상
    center+margin=1.0(부동소수 잔차로 ≈1.0)이라 클램프가 1.0 상한을 보장한다.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")
    z = statistics.NormalDist().inv_cdf(confidence)
    n = float(trials)
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(phat * (1.0 - phat) / n + z2 / (4.0 * n * n))
    return min(1.0, center + margin)


# ──────────────────────────────────────────────────────────────────────────
# 측정 리포트(PrecisionReport 미러 — items source-of-truth, 파생 프로퍼티)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class SemanticEvalReport:
    """의미 매칭 측정 배치 결과 — outcome 리스트 + 파생 지표. 불변(PrecisionReport 미러).

    `items`가 *원천*이고 모든 카운트·비율은 파생 프로퍼티다(PrecisionReport와 동형). recall(틀린
    진술을 의미로 잡음·높을수록 좋음)과 false_positive_rate(올바른 진술을 끌어올림·낮을수록 좋음)를
    *분리*해 잰다 — recall은 Wilson 하한, FP는 Wilson 상한으로 보고(정직·보수). substring 기준선
    지표를 함께 내 의미 매처의 *순기여*(substring이 못 잡던 recall)와 *추가 FP*를 대조한다.
    """

    items: tuple[ProbeOutcome, ...]

    @property
    def total(self) -> int:
        return len(self.items)

    # ── recall 프로브 집계(틀린 진술을 의미로 잡는가) ────────────────────────
    @property
    def recall_probes(self) -> tuple[ProbeOutcome, ...]:
        return tuple(o for o in self.items if o.probe.is_recall_probe)

    @property
    def total_recall(self) -> int:
        return len(self.recall_probes)

    @property
    def caught_recall(self) -> int:
        """의미 매처가 잡은 recall 프로브 수(TP-유사)."""
        return sum(1 for o in self.recall_probes if o.caught_by_semantic)

    @property
    def recall(self) -> float | None:
        """의미 recall = 잡은 recall 프로브 / 전체 recall 프로브. recall 프로브 0이면 None."""
        return _div(self.caught_recall, self.total_recall)

    def recall_lower_bound(self, confidence: float = 0.95) -> float | None:
        """의미 recall의 Wilson 단측 신뢰하한(기본 95%) — recall ≥ X 정직. recall 프로브 0이면 None.

        점추정(`recall`)이 아니라 이 하한으로 플립을 판정해야 작은 표본에서 정직하다
        (`_wilson_lower_bound` 재사용). 예: 55/60=0.917이라도 하한은 그보다 낮다.
        """
        n = self.total_recall
        if n == 0:
            return None
        return _wilson_lower_bound(self.caught_recall, n, confidence)

    @property
    def substring_recall(self) -> float | None:
        """substring 기준선 recall — 보통 ~0(프로브가 signals를 회피하게 설계). 순기여 대조용."""
        caught = sum(1 for o in self.recall_probes if o.caught_by_substring)
        return _div(caught, self.total_recall)

    # ── FP 프로브 집계(올바른 진술을 오개념으로 끌어올리는가) ─────────────────
    @property
    def fp_probes(self) -> tuple[ProbeOutcome, ...]:
        return tuple(o for o in self.items if o.probe.is_fp_probe)

    @property
    def total_fp(self) -> int:
        return len(self.fp_probes)

    @property
    def semantic_false_positives(self) -> int:
        """올바른 진술에 *아무* 오개념이나 끌어올린 FP 프로브 수."""
        return sum(1 for o in self.fp_probes if o.semantic_false_positive)

    @property
    def false_positive_rate(self) -> float | None:
        """의미 FP율 = 거짓양성 FP 프로브 / 전체 FP 프로브. FP 프로브 0이면 None."""
        return _div(self.semantic_false_positives, self.total_fp)

    def fp_rate_upper_bound(self, confidence: float = 0.95) -> float | None:
        """의미 FP율의 Wilson 단측 신뢰상한(기본 95%) — FP ≤ Y 보수. FP 프로브 0이면 None.

        점추정(`false_positive_rate`)이 아니라 이 *상한*으로 플립을 판정해야 작은 표본에서
        보수적이다(`_wilson_upper_bound`). 관측 FP가 0이어도 상한>0이라 "FP가 낮다"를 과신하지
        않는다 — student-facing 틀린 개입이 #1 리스크(CLAUDE.md)라 FP는 보수적으로 본다.
        """
        n = self.total_fp
        if n == 0:
            return None
        return _wilson_upper_bound(self.semantic_false_positives, n, confidence)

    @property
    def near_false_positives(self) -> int:
        """*겨냥한* 방향맹 대상(near_id)이 끌려 올라온 FP 프로브 수."""
        return sum(1 for o in self.fp_probes if o.near_false_positive)

    @property
    def near_false_positive_rate(self) -> float | None:
        """겨냥 FP율 = near_id 끌림 FP 프로브 / 전체 FP 프로브. FP 프로브 0이면 None."""
        return _div(self.near_false_positives, self.total_fp)

    @property
    def substring_false_positive_rate(self) -> float | None:
        """substring 기준선 FP율 — 보통 ~0. 의미 매처가 *추가하는* FP 대조용."""
        fp = sum(1 for o in self.fp_probes if o.substring_false_positive)
        return _div(fp, self.total_fp)

    # ── judge 후 지표(슬108·judge 적용 시만 유의미·미적용이면 의미 매처와 동일/0) ────
    @property
    def judge_false_positives(self) -> int:
        """judge 후에도 거짓양성이 남은 FP 프로브 수(judge가 못 거른 FP)."""
        return sum(1 for o in self.fp_probes if o.judge_false_positive)

    @property
    def judge_fp_rate(self) -> float | None:
        """judge 후 FP율 = judge 후 거짓양성 FP 프로브 / 전체 FP 프로브. FP 프로브 0이면 None.

        의미 FP율(`false_positive_rate`)에 judge 필터를 *추가로* 건 뒤의 FP율이다. judge가
        방향·부정·등치를 제대로 거르면 이 값이 의미 FP율보다 낮아진다(judge 효과의 핵심 지표).
        """
        return _div(self.judge_false_positives, self.total_fp)

    def judge_fp_rate_upper_bound(self, confidence: float = 0.95) -> float | None:
        """judge 후 FP율의 Wilson 단측 신뢰상한(기본 95%) — judge FP ≤ Y 보수. FP 프로브 0이면 None.

        의미 FP와 같은 이유로 *상한*으로 본다(`_wilson_upper_bound`) — student-facing 틀린 개입이
        #1 리스크라 judge 후 FP도 과신하지 않는다(작은 표본 보정). 후속 coach 배선 판단의 근거.
        """
        n = self.total_fp
        if n == 0:
            return None
        return _wilson_upper_bound(self.judge_false_positives, n, confidence)

    @property
    def judge_fp_reduction(self) -> float | None:
        """judge가 줄인 FP 비율 = (의미 FP − judge 후 FP) / 의미 FP. 의미 FP 0이면 None.

        judge가 의미 매처의 거짓양성을 *얼마나* 걷어냈는지의 상대 감소율. 1.0=의미 FP를 전부
        제거, 0.0=하나도 못 줄임, 음수=judge가 *오히려* 늘림(불가능 — judge는 제거만 하므로
        judge 후 FP ≤ 의미 FP, 따라서 [0,1]). 의미 FP가 0이면(거를 게 없으면) None(미정).
        """
        sem_fp = self.semantic_false_positives
        if sem_fp == 0:
            return None
        return (sem_fp - self.judge_false_positives) / sem_fp

    @property
    def judge_caught_recall(self) -> int:
        """judge 후에도 잡힌 recall 프로브 수 — 의미가 잡고 judge가 유지(예·불확실)한 것."""
        return sum(1 for o in self.recall_probes if o.judge_kept_expected)

    @property
    def judge_recall(self) -> float | None:
        """judge 후 recall = judge 통과 recall / 전체 recall 프로브. recall 프로브 0이면 None.

        의미 recall(`recall`)에 judge 필터를 건 뒤의 recall. judge는 *제거만* 하므로 judge 후
        recall ≤ 의미 recall(judge가 잘못 거르면 recall 손실). 이상적으로 judge는 FP만 줄이고
        recall은 보존(예·불확실 유지)해야 한다.
        """
        return _div(self.judge_caught_recall, self.total_recall)

    def judge_recall_lower_bound(self, confidence: float = 0.95) -> float | None:
        """judge 후 recall의 Wilson 단측 신뢰하한(기본 95%) — judge recall ≥ X 정직. 0이면 None."""
        n = self.total_recall
        if n == 0:
            return None
        return _wilson_lower_bound(self.judge_caught_recall, n, confidence)

    @property
    def judge_recall_loss(self) -> float | None:
        """judge가 *잘못 제거한* recall TP 비율 = (의미가 잡은 − judge가 유지한) / 의미가 잡은.

        의미 매처가 끌어올린 진짜 오개념(recall TP) 중 judge가 `아니오`로 *잘못 거른* 비율.
        0.0=judge가 recall을 온전히 보존(이상), 1.0=judge가 잡힌 것을 전부 제거(최악). 분모는
        *의미가 잡은* recall(`caught_recall`)이다(judge가 손댈 수 있는 모수). 의미가 하나도 못
        잡았으면(분모 0) None. judge의 *부작용*(recall 침해)을 FP 감소와 대조해 본다.
        """
        sem_caught = self.caught_recall
        if sem_caught == 0:
            return None
        return (sem_caught - self.judge_caught_recall) / sem_caught

    # ── 분해(kind별·도메인별) ────────────────────────────────────────────────
    @property
    def recall_by_kind(self) -> dict[str, tuple[int, int]]:
        """kind → (잡힘, 전체) — recall 프로브만. 어떤 패러프레이즈 유형이 약한지 드러낸다."""
        caught: Counter[str] = Counter()
        total: Counter[str] = Counter()
        for o in self.recall_probes:
            total[o.probe.kind] += 1
            if o.caught_by_semantic:
                caught[o.probe.kind] += 1
        return {k: (caught[k], total[k]) for k in sorted(total)}

    @property
    def fp_by_kind(self) -> dict[str, tuple[int, int]]:
        """kind → (거짓양성, 전체) — FP 프로브만. correct-near/negation/direction-reverse별 FP."""
        fp: Counter[str] = Counter()
        total: Counter[str] = Counter()
        for o in self.fp_probes:
            total[o.probe.kind] += 1
            if o.semantic_false_positive:
                fp[o.probe.kind] += 1
        return {k: (fp[k], total[k]) for k in sorted(total)}

    @property
    def recall_by_domain(self) -> dict[str, tuple[int, int]]:
        """도메인(MisconceptionDomain) → (잡힘, 전체) — recall 프로브만. 영역별 약점 진단."""
        caught: Counter[str] = Counter()
        total: Counter[str] = Counter()
        for o in self.recall_probes:
            domain = _probe_domain(o.probe)
            if domain is None:
                continue
            total[domain] += 1
            if o.caught_by_semantic:
                caught[domain] += 1
        return {k: (caught[k], total[k]) for k in sorted(total)}

    @property
    def fp_by_domain(self) -> dict[str, tuple[int, int]]:
        """도메인 → (거짓양성, 전체) — FP 프로브만(near_id 기준 도메인). 영역별 방향맹 FP."""
        fp: Counter[str] = Counter()
        total: Counter[str] = Counter()
        for o in self.fp_probes:
            domain = _probe_domain(o.probe)
            if domain is None:
                continue
            total[domain] += 1
            if o.semantic_false_positive:
                fp[domain] += 1
        return {k: (fp[k], total[k]) for k in sorted(total)}


def _probe_domain(probe: MisconceptionProbe) -> MisconceptionDomain | None:
    """프로브가 겨냥한 오개념(expected_id 또는 near_id)의 도메인 — 도메인별 분해용.

    recall 프로브는 expected_id, FP 프로브는 near_id로 카탈로그를 역참조한다. id가 카탈로그에
    없으면 None(분해에서 제외) — 구조 검증 테스트가 모든 id∈CATALOG_BY_ID를 보장하므로 실파일엔
    None이 안 난다(방어).
    """
    target = probe.expected_id if probe.is_recall_probe else probe.near_id
    if target is None:
        return None
    m = CATALOG_BY_ID.get(target)
    return m.domain if m is not None else None


# ──────────────────────────────────────────────────────────────────────────
# 실행(라이브 의미 매처 + substring 기준선) → 집계
# ──────────────────────────────────────────────────────────────────────────
def run_probes(
    probes: Iterable[MisconceptionProbe],
    *,
    provider: EmbeddingProvider,
    matcher: SemanticMatcher | None = None,
    threshold: float = _DEFAULT_THRESHOLD,
    top_k: int = _DEFAULT_TOP_K,
) -> list[ProbeOutcome]:
    """각 프로브에 의미 매처(`.match`)와 substring 기준선(`diagnose`)을 돌려 ProbeOutcome 조립.

    의미 매처는 `matcher`가 주어지면 그것을(사전 임베딩 캐시 재사용 — 카탈로그 30종 재임베딩 회피),
    없으면 주입 provider로 `SemanticMatcher`를 *한 번* 만들어 전 프로브에 재사용한다. substring
    기준선은 `diagnose`(불변)로 같은 텍스트를 진단해 *순기여*(substring이 못 잡던 recall)와
    *추가 FP*를 대조할 기준을 만든다. 게이트·coach·`semantic_matches` 시그니처는 건드리지 않는다.

    threshold는 측정의 *운영점*이다(스윕이면 호출자가 임계값별로 반복 호출). top_k는 매처/diagnose
    후보 컷(측정엔 넉넉히 5).
    """
    resolved_matcher = matcher if matcher is not None else SemanticMatcher(provider=provider)
    outcomes: list[ProbeOutcome] = []
    for probe in probes:
        sem_matches = resolved_matcher.match(probe.statement, top_k=top_k, threshold=threshold)
        substr_matches = diagnose(probe.statement, top_k=top_k)
        outcomes.append(
            ProbeOutcome(
                probe=probe,
                semantic_ids=tuple(m.misconception.id for m in sem_matches),
                substring_ids=tuple(m.misconception.id for m in substr_matches),
            )
        )
    return outcomes


async def run_probes_with_judge(
    probes: Iterable[MisconceptionProbe],
    *,
    provider: EmbeddingProvider,
    judge: JudgeProtocol,
    matcher: SemanticMatcher | None = None,
    threshold: float = _DEFAULT_THRESHOLD,
    top_k: int = _DEFAULT_TOP_K,
) -> list[ProbeOutcome]:
    """`run_probes`의 **judge 변형**(async) — 의미 매칭 후 `judge_filter`로 후보를 거른다.

    슬108: 슬107 sync `run_probes`(judge None)는 *불변*으로 두고, judge 경로는 *별도 async
    함수*로 분리한다(`judge_filter`가 async라 sync 시그니처를 깨지 않기 위함). 각 프로브에:
      ① 의미 매처(`.match`)로 `MisconceptionMatch` 후보를 뽑고(substring 기준선도 함께),
      ② 그 후보를 `judge_verdicts`로 판정(verdict·reason 보존)해 `아니오`만 제거·나머지 유지,
      ③ `judge_kept_ids`(유지)·`judge_removed_ids`(제거)를 *의미 매처 순서 그대로* 기록하고,
         후보별 `judge_decisions`(id·verdict·reason)로 판정 근거를 보존한다(판정근거 캐처).

    `semantic_ids`/`substring_ids`는 슬107과 동일하게 채운다(judge 적용 *이전* 의미 매칭 결과를
    보존 — judge 전후 대조의 기준선). 따라서 한 outcome에서 `recall`/`fp_rate`(judge 전)와
    `judge_recall`/`judge_fp_rate`(judge 후)를 *모두* 계산할 수 있다(before/after 한 줄 대조).
    게이트·coach·`semantic_matches`·sync `run_probes`는 무변경.
    """
    resolved_matcher = matcher if matcher is not None else SemanticMatcher(provider=provider)
    outcomes: list[ProbeOutcome] = []
    for probe in probes:
        sem_matches = resolved_matcher.match(probe.statement, top_k=top_k, threshold=threshold)
        substr_matches = diagnose(probe.statement, top_k=top_k)
        semantic_ids = tuple(m.misconception.id for m in sem_matches)
        # 각 의미 후보를 judge로 판정 — verdict·reason까지 보존(판정근거 캐처).
        decided = await judge_verdicts(sem_matches, probe.statement, judge=judge)
        # 유지 = `아니오`(NOT_EXPRESSES) 아닌 것(예·불확실). judge_filter와 동일 규칙·순서 보존.
        kept_ids = tuple(
            m.misconception.id for m, r in decided if r.verdict is not JudgeVerdict.NOT_EXPRESSES
        )
        kept_set = set(kept_ids)
        # 제거 = 의미 후보 중 유지되지 않은 것(의미 매처 순서 그대로 — 분할 보존).
        removed_ids = tuple(mid for mid in semantic_ids if mid not in kept_set)
        # 후보별 판정 근거(의미 매처 순서) — JSON 리포트에 실려 "왜 걸렀나"를 감사 가능하게 한다.
        judge_decisions = tuple(
            JudgeDecision(
                misconception_id=m.misconception.id, verdict=r.verdict.value, reason=r.reason
            )
            for m, r in decided
        )
        outcomes.append(
            ProbeOutcome(
                probe=probe,
                semantic_ids=semantic_ids,
                substring_ids=tuple(m.misconception.id for m in substr_matches),
                judge_kept_ids=kept_ids,
                judge_removed_ids=removed_ids,
                judge_decisions=judge_decisions,
            )
        )
    return outcomes


def evaluate(outcomes: Iterable[ProbeOutcome]) -> SemanticEvalReport:
    """ProbeOutcome 리스트를 SemanticEvalReport로 집계(순수·결정론).

    `run_probes`(라이브 매칭)와 `evaluate`(순수 집계)를 분리해 — 합성 outcome으로 스코어링을
    hermetic하게 검증할 수 있게 한다(step_shadow_eval.evaluate와 같은 분리는 아니나, 측정 도구라
    *매칭*과 *집계*를 떼어 두는 게 테스트·스윕에 유리하다).
    """
    return SemanticEvalReport(items=tuple(outcomes))


# ──────────────────────────────────────────────────────────────────────────
# 리포트 포맷(format_report 미러 — 요약 + FP 상세)
# ──────────────────────────────────────────────────────────────────────────
def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _judge_applied(report: SemanticEvalReport) -> bool:
    """judge가 적용됐는지 — 어떤 outcome이라도 judge가 후보를 *유지/제거*한 흔적이 있으면 True.

    judge 미적용(슬107 sync `run_probes`) outcome은 judge_kept/removed가 모두 빈 튜플이라 False
    → judge 줄을 *생략*(슬107 출력 불변). `run_probes_with_judge`로 만든 outcome은 의미 매처가
    낸 후보가 *하나라도* 있으면(유지 또는 제거) True. 의미 매처가 *아무것도 안 낸* 극단(전부
    빈 semantic_ids)에선 False가 될 수 있으나, 그 경우 judge 지표가 전부 0/None이라 무의미해
    생략이 합당하다(실 프로브셋은 매칭이 다수라 정상적으로 True).
    """
    return any(o.judge_kept_ids or o.judge_removed_ids for o in report.items)


def _fmt_breakdown(breakdown: dict[str, tuple[int, int]]) -> str:
    """{key: (hit, total)} → "key=hit/total(비율)" 나열."""
    parts = []
    for key, (hit, total) in breakdown.items():
        rate = _fmt(_div(hit, total))
        parts.append(f"{key}={hit}/{total}({rate})")
    return " ".join(parts) if parts else "(없음)"


def format_report(report: SemanticEvalReport, confidence: float = 0.95) -> str:
    """사람읽는 요약 — recall(+하한)·FP율(+상한)·kind/도메인 분해 + **FP 상세**.

    FP 상세(어떤 *올바른* statement가 어떤 near_id로 잘못 끌렸는지)는 플립 판단·LLM-judge 후속의
    핵심 근거다 — 방향맹이 *실제로 어디서* 터지는지 사람이 눈으로 확인하게 둔다.
    """
    pct = round(confidence * 100)
    lines: list[str] = [
        (
            f"total={report.total} "
            f"recall={_fmt(report.recall)} "
            f"({pct}%하한={_fmt(report.recall_lower_bound(confidence))} "
            f"n={report.total_recall} caught={report.caught_recall}) "
            f"substr_recall={_fmt(report.substring_recall)}"
        ),
        (
            f"fp_rate={_fmt(report.false_positive_rate)} "
            f"({pct}%상한={_fmt(report.fp_rate_upper_bound(confidence))} "
            f"n={report.total_fp} fp={report.semantic_false_positives}) "
            f"near_fp_rate={_fmt(report.near_false_positive_rate)} "
            f"substr_fp_rate={_fmt(report.substring_false_positive_rate)}"
        ),
    ]
    # judge 적용 시(슬108)만 before/after 대조 줄 추가 — judge 미적용이면 슬107과 동일 출력.
    if _judge_applied(report):
        lines.append(
            f"judge_fp_rate={_fmt(report.judge_fp_rate)} "
            f"({pct}%상한={_fmt(report.judge_fp_rate_upper_bound(confidence))} "
            f"judge_fp={report.judge_false_positives}) "
            f"fp_reduction={_fmt(report.judge_fp_reduction)} "
            f"[before={_fmt(report.false_positive_rate)} -> after={_fmt(report.judge_fp_rate)}]"
        )
        lines.append(
            f"judge_recall={_fmt(report.judge_recall)} "
            f"({pct}%하한={_fmt(report.judge_recall_lower_bound(confidence))} "
            f"judge_caught={report.judge_caught_recall}) "
            f"recall_loss={_fmt(report.judge_recall_loss)} "
            f"[before={_fmt(report.recall)} -> after={_fmt(report.judge_recall)}]"
        )
    lines += [
        f"recall by kind:   {_fmt_breakdown(report.recall_by_kind)}",
        f"recall by domain: {_fmt_breakdown(report.recall_by_domain)}",
        f"fp by kind:       {_fmt_breakdown(report.fp_by_kind)}",
        f"fp by domain:     {_fmt_breakdown(report.fp_by_domain)}",
    ]
    # recall miss 상세 — 의미 매처가 *놓친* 틀린 진술(어떤 expected_id를 못 잡았는지·약점 진단).
    recall_misses = [o for o in report.recall_probes if not o.caught_by_semantic]
    if recall_misses:
        lines.append(f"recall miss ({len(recall_misses)}):")
        for o in recall_misses:
            lines.append(
                f"  [MISS] expected={o.probe.expected_id} kind={o.probe.kind} "
                f"got={list(o.semantic_ids)} :: {o.probe.statement}"
            )
    # FP 상세 — *올바른* 진술이 어떤 오개념으로 잘못 끌렸는지(near 끌림은 [NEAR-FP]로 표시).
    fp_hits = [o for o in report.fp_probes if o.semantic_false_positive]
    if fp_hits:
        lines.append(f"false positives ({len(fp_hits)}):")
        for o in fp_hits:
            tag = "NEAR-FP" if o.near_false_positive else "FP"
            lines.append(
                f"  [{tag}] near={o.probe.near_id} kind={o.probe.kind} "
                f"got={list(o.semantic_ids)} :: {o.probe.statement}"
            )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────
def _parse_sweep(raw: str) -> list[float]:
    """`--sweep` 인자("0.4,0.5,0.55") → 임계값 리스트. 빈/형식오류는 ValueError."""
    values: list[float] = []
    for token in raw.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        values.append(float(stripped))
    if not values:
        raise ValueError(f"--sweep에 임계값이 없습니다: {raw!r}")
    return values


def _resolved_threshold(threshold: float | None, settings: Settings | None = None) -> float:
    """임계값 해석 — 명시 우선, 없으면 Settings.misconception_semantic_threshold(보수적 0.55)."""
    if threshold is not None:
        return threshold
    resolved = settings if settings is not None else get_settings()
    return resolved.misconception_semantic_threshold


def report_to_dict(
    report: SemanticEvalReport, *, threshold: float, confidence: float = 0.95
) -> dict[str, Any]:
    """SemanticEvalReport → 기계가독 dict(JSON 직렬화용·아카이브·추세추적·diff).

    `summary`는 요약 지표(카운트·비율·Wilson 경계·judge 전후), `probes`는 프로브별 행(매칭 id +
    후보별 `judge_decisions`)이다. judge 미적용(`--judge` 없이)이면 `judge_applied=false`이고
    judge_* 요약 키는 생략·`judge_decisions`는 빈 리스트(슬107 반영). `format_report`(사람읽기)와
    *같은 원천*(report)에서 파생하되 형태만 기계가독 — 모델 업그레이드 간 judge 효과 diff·추적.
    """
    judge_applied = _judge_applied(report)
    summary: dict[str, Any] = {
        "total": report.total,
        "total_recall": report.total_recall,
        "total_fp": report.total_fp,
        "recall": report.recall,
        "recall_lower_bound": report.recall_lower_bound(confidence),
        "false_positive_rate": report.false_positive_rate,
        "fp_rate_upper_bound": report.fp_rate_upper_bound(confidence),
        "near_false_positive_rate": report.near_false_positive_rate,
        "substring_recall": report.substring_recall,
        "substring_false_positive_rate": report.substring_false_positive_rate,
        "judge_applied": judge_applied,
    }
    if judge_applied:
        summary["judge_fp_rate"] = report.judge_fp_rate
        summary["judge_fp_rate_upper_bound"] = report.judge_fp_rate_upper_bound(confidence)
        summary["judge_fp_reduction"] = report.judge_fp_reduction
        summary["judge_recall"] = report.judge_recall
        summary["judge_recall_lower_bound"] = report.judge_recall_lower_bound(confidence)
        summary["judge_recall_loss"] = report.judge_recall_loss
    probes_rows: list[dict[str, Any]] = [
        {
            "statement": o.probe.statement,
            "expected_id": o.probe.expected_id,
            "near_id": o.probe.near_id,
            "kind": o.probe.kind,
            "semantic_ids": list(o.semantic_ids),
            "substring_ids": list(o.substring_ids),
            "judge_kept_ids": list(o.judge_kept_ids),
            "judge_removed_ids": list(o.judge_removed_ids),
            "judge_decisions": [
                {"misconception_id": d.misconception_id, "verdict": d.verdict, "reason": d.reason}
                for d in o.judge_decisions
            ],
        }
        for o in report.items
    ]
    return {
        "threshold": threshold,
        "confidence": confidence,
        "summary": summary,
        "probes": probes_rows,
    }


def _run(
    probes_path: Path,
    *,
    threshold: float | None,
    sweep: list[float] | None,
    min_recall: float,
    max_fp: float,
    top_k: int,
    confidence: float,
    provider: EmbeddingProvider | None = None,
    judge: JudgeProtocol | None = None,
    report_format: str = "text",
) -> int:
    """프로브셋 로드 → 라이브 측정 → 리포트(또는 스윕) → 게이트 판정.

    provider 미주입 시 `build_provider`(기본 local=bge-m3)로 라이브 측정한다. 스윕이면 임계값별
    recall/FP 한 줄씩(운영점 곡선) 출력하고, 게이트(min-recall/max-fp)는 *고정 threshold*에 적용한다
    (스윕은 곡선 관찰용·게이트와 분리). 게이트: recall_lower_bound ≥ min-recall AND
    fp_rate_upper_bound ≤ max-fp면 exit 0, 아니면 1(step_shadow 게이트 미러·둘 다 opt-in).

    `judge` 주입 시(슬108·`--judge`) *고정 threshold* 리포트를 `run_probes_with_judge`(async)로
    측정해 judge 후 FP 감소·recall 손실을 함께 낸다(format_report가 before/after 줄 추가). 스윕은
    의미 매처만(judge 미적용·threshold 곡선이 목적) 유지한다 — judge는 운영점 곡선이 아니라
    *고정점에서의 추가 필터 효과* 측정이다(judge 호출이 임계값마다 N배 늘면 측정 비용 과다).
    """
    probes = load_probes(probes_path)
    resolved_provider = provider if provider is not None else build_provider()
    # 매처를 1회 만들어(사전 임베딩 캐시) 스윕·고정 측정에 재사용한다.
    matcher = SemanticMatcher(provider=resolved_provider)

    if sweep is not None and report_format == "text":
        print(
            f"sweep (n={len(probes)} recall={sum(1 for p in probes if p.is_recall_probe)} "
            f"fp={sum(1 for p in probes if p.is_fp_probe)}):"
        )
        for thr in sweep:
            outcomes = run_probes(
                probes, provider=resolved_provider, matcher=matcher, threshold=thr, top_k=top_k
            )
            report = evaluate(outcomes)
            print(
                f"  threshold={thr:.3f} recall={_fmt(report.recall)} "
                f"(하한={_fmt(report.recall_lower_bound(confidence))}) "
                f"fp_rate={_fmt(report.false_positive_rate)} "
                f"(상한={_fmt(report.fp_rate_upper_bound(confidence))}) "
                f"near_fp={_fmt(report.near_false_positive_rate)}"
            )

    resolved_threshold = _resolved_threshold(threshold)
    if judge is not None:
        # judge 경로(async) — 의미 매칭 후 judge 필터 적용. asyncio.run으로 동기 CLI에서 구동.
        import asyncio

        outcomes = asyncio.run(
            run_probes_with_judge(
                probes,
                provider=resolved_provider,
                judge=judge,
                matcher=matcher,
                threshold=resolved_threshold,
                top_k=top_k,
            )
        )
    else:
        outcomes = run_probes(
            probes,
            provider=resolved_provider,
            matcher=matcher,
            threshold=resolved_threshold,
            top_k=top_k,
        )
    report = evaluate(outcomes)
    if report_format == "json":
        print(
            json.dumps(
                report_to_dict(report, threshold=resolved_threshold, confidence=confidence),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"\n=== threshold={resolved_threshold:.3f} ===")
        print(format_report(report, confidence=confidence))

    # 게이트(둘 다 opt-in·기본 0.0=off): recall은 하한이 min-recall 이상·FP는 상한이 max-fp 이하면
    # 통과(exit 0). None(프로브 0)은 임계>0일 때 미달로 본다(증거 없음=통과 불가). step_shadow의
    # min-lower-bound 게이트 미러 — recall은 하한(높아야)·FP는 상한(낮아야)으로 *양방향* 본다.
    passed = True
    if min_recall > 0.0:
        rlb = report.recall_lower_bound(confidence)
        if rlb is None or rlb < min_recall:
            passed = False
    if max_fp > 0.0:
        fub = report.fp_rate_upper_bound(confidence)
        if fub is None or fub > max_fp:
            passed = False
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 프로브셋 JSONL → 의미 매칭 recall/FP 측정. 종료 0(통과)/1(게이트 미달).

    게이트(min-recall/max-fp)는 *측정 도구의 옵션*일 뿐 coach 게이트
    (`misconception_semantic_mode`)와 무관하다 — 본 CLI는 플립 *근거*를 내고, 실제 플립은
    Kiki가 측정 후 별도 슬라이스로 한다.
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.misconception.semantic_eval",
        description=(
            "오개념 의미 매칭 측정 하니스 — 프로브셋으로 결합 recall(Wilson 하한)·방향맹 "
            "false-positive-rate(Wilson 상한)를 측정(오프라인·비노출·게이트 off 유지)."
        ),
    )
    parser.add_argument("probes_path", type=str, help="프로브셋 JSONL(한 줄당 MisconceptionProbe)")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="의미 매칭 임계값(미지정 시 Settings 기본 0.55). 고정 측정·게이트의 운영점.",
    )
    parser.add_argument(
        "--sweep",
        type=str,
        default=None,
        help="임계값 스윕(콤마 구분·예: 0.4,0.5,0.6) — 각 임계값 recall/FP 한 줄(운영점 곡선).",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.0,
        help="recall Wilson 하한 게이트 — 미만이면 exit 1(기본 0.0=off).",
    )
    parser.add_argument(
        "--max-fp",
        type=float,
        default=0.0,
        help="FP율 Wilson 상한 게이트 — 초과면 exit 1(기본 0.0=off·보수적).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=_DEFAULT_TOP_K,
        help="매처/diagnose 후보 컷(측정엔 넉넉히·기본 5).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="Wilson 하한/상한 신뢰수준(단측·기본 0.95).",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help=(
            "라이브 LLM-judge 활성(슬108) — 의미 매칭 후보에 방향 판별 judge를 걸어 judge 후 "
            "FP 감소·recall 손실을 측정한다. L3 백킹(로컬 FAST·라우터 경유). 미지정 시 슬107 "
            "동작(의미 매칭만)."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="출력 형식 — text(사람읽기·기본)/json(기계가독 리포트·아카이브·후보별 판정근거).",
    )
    args = parser.parse_args(argv)
    probes_path: str = args.probes_path
    threshold: float | None = args.threshold
    sweep_raw: str | None = args.sweep
    sweep = _parse_sweep(sweep_raw) if sweep_raw else None
    min_recall: float = args.min_recall
    max_fp: float = args.max_fp
    top_k: int = args.top_k
    confidence: float = args.confidence
    use_judge: bool = args.judge
    report_format: str = args.format
    judge: JudgeProtocol | None = None
    if use_judge:
        # L3 백킹 judge(로컬 FAST·라우터 경유) 구성 — L3 import는 judge_seam에 격리.
        # 지연 import: judge 미사용 시 L3 의존성 로드 0(슬107 경로 비결합).
        from whymath_backend.l4.misconception.judge import LLMJudge
        from whymath_backend.l4.misconception.judge_seam import L3JudgeSeam

        judge = LLMJudge(seam=L3JudgeSeam())
    return _run(
        Path(probes_path),
        threshold=threshold,
        sweep=sweep,
        min_recall=min_recall,
        max_fp=max_fp,
        top_k=top_k,
        confidence=confidence,
        judge=judge,
        report_format=report_format,
    )


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "MisconceptionProbe",
    "ProbeOutcome",
    "SemanticEvalReport",
    "evaluate",
    "format_report",
    "load_probes",
    "main",
    "run_probes",
    "run_probes_with_judge",
]
