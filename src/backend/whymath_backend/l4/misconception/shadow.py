"""오개념 의미 매칭 *shadow 관측* — 노출 없이 substring↔semantic 불일치만 로깅 (slice 111).

`l4/step_shadow.py`(단계-비보존 shadow)의 정본 패턴을 미러한다. coach가 `misconception_semantic_
mode == "shadow"`일 때, 의미 매처를 *라이브로 돌리되* 노출은 substring 그대로 두고(off와 동일),
substring이 안 잡은 semantic-only 후보(불일치)를 **로그로만** 남긴다 — 슬107 측정 하니스는 *합성
프로브*에서 방향맹 FP를 쟀는데, shadow는 *실 학생 트래픽 분포*에서 의미 매처가 무엇을 더하는지를
무노출로 수집해 게이트 플립(`off`→`on`) 근거를 보강한다.

비노출·비차단 불변(step_shadow 계승):
- **비노출**: 반환 `None`. 호출자(coach)가 신호를 받을 변수가 없어 student-facing 누출이 구조적으로
  차단된다. 노출 응답은 `off`와 비트동일(substring)이고, shadow 로그는 *서버 로그 sink에만* 흐른다.
- **비차단**: 검출·직렬화·로깅을 한 `try`로 감싸 어떤 예외도 본류(코칭 결정·반환)를 안 깬다
  (우선순위: 학생 경험 > 진단 관측).
- **프라이버시**: 학생 풀이 원문을 레코드에 *담지 않는다*(step_shadow 규약·미성년자). 담는 건
  추상화된 오개념 id·코사인 유사도·개수(비식별).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from whymath_backend.l4.misconception.models import MisconceptionMatch

logger = logging.getLogger("whymath.l4.misconception.shadow")  # step_shadow 네이밍 동형
# 구조화 레코드 JSON 한 줄(harvest 입력) — 평문 로그와 분리된 자식 로거(step_shadow.record 미러).
record_logger = logging.getLogger("whymath.l4.misconception.shadow.record")


class MisconceptionShadowObservation(BaseModel):
    """의미 매칭 shadow 관측 1건의 *구조화 레코드* — record_logger JSON emit (harvest).

    노출되는 substring 후보(`substr_ids`)와 의미 매처가 *추가할* semantic-only 후보
    (`semantic_only_ids`·substring 미포착)를 담아, 실 분포에서 의미 매칭이 무엇을 더하는지(불일치)를
    수집한다. **학생 풀이 원문을 담지 않는다**(step_shadow 규약·프라이버시) — 담는 건 오개념 id·
    코사인 유사도·개수(비식별·로그 sink 한정·비노출 불변).
    """

    model_config = ConfigDict(extra="forbid")

    substr_ids: list[str]
    """노출되는(off와 동일) substring 진단 후보 id — confidence 내림차순."""

    semantic_only_ids: list[str]
    """의미 매처가 *추가할* 후보 id(substring 미포착) = 불일치. on이면 노출될 semantic-only."""

    semantic_only_similarities: list[float]
    """`semantic_only_ids` 각각의 코사인 유사도(같은 순서·None은 -1.0으로 표기)."""

    substr_count: int
    semantic_count: int
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def observe_misconception_shadow(
    substr_matches: list[MisconceptionMatch],
    semantic_matches: list[MisconceptionMatch],
) -> None:
    """substring↔semantic 불일치를 *로그로만* 관측(shadow·비차단·비노출). 반환 `None`.

    반환이 `None`이라 호출자(coach)가 신호를 받을 변수가 없다 — student-facing 누출 구조적 차단.
    coach는 `mode == "shadow"`에서만 호출하므로 이 함수는 게이트를 재검사하지 않는다(호출 시점이
    곧 shadow). 노출(반환 matches)은 coach가 substring 그대로 둔다(off 비트동일) — 본 함수는
    *부수효과(로그)만* 낸다. 어떤 예외도 본류를 깨지 않게 `try`로 감싼다(비차단).

    `semantic_only` = 의미 매처 결과 중 substring이 *안 잡은* id(`combine_diagnoses`가 `on`에서
    substring 아래에 붙일 후보). 이게 실 분포에서 의미 매처의 *순기여*(+recall)와 *방향맹 FP*가
    뒤섞인 신호다 — 사람이 로그를 보고(또는 harvest) 플립 근거를 모은다.
    """
    try:
        substr_ids = [m.misconception.id for m in substr_matches]
        substr_set = set(substr_ids)
        semantic_only = [m for m in semantic_matches if m.misconception.id not in substr_set]
        semantic_only_ids = [m.misconception.id for m in semantic_only]
        # semantic_similarity None(이론상 의미 경로에선 항상 설정)은 -1.0로 표기(레코드 타입 고정).
        sims = [
            m.semantic_similarity if m.semantic_similarity is not None else -1.0
            for m in semantic_only
        ]
        logger.info(
            "의미 매칭 shadow(비노출) — substr=%s semantic_only=%s sims=%s "
            "(substr_count=%d semantic_count=%d)",
            substr_ids,
            semantic_only_ids,
            [round(s, 3) for s in sims],
            len(substr_matches),
            len(semantic_matches),
        )
        record_logger.info(
            MisconceptionShadowObservation(
                substr_ids=substr_ids,
                semantic_only_ids=semantic_only_ids,
                semantic_only_similarities=sims,
                substr_count=len(substr_matches),
                semantic_count=len(semantic_matches),
            ).model_dump_json()
        )
    except Exception:  # noqa: BLE001 — 관측은 본류를 안 깬다(비차단 방어선·테스트 커버)
        return
