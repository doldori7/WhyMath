"""개념→평가 재료 *참조* 뱅크 — 검증 통과 문항의 `ConceptAssessment` 상속 조회(LLM 0·저작 0).

`dsl.py::from_concept_content`이 `assessment=None`으로 남긴 자리를 채우는 **공급원**이다. 그 자리가
비어 있는 동안 `ProblemBasedAdapter.can_render()`가 전 개념에서 False였고(평가 재료가 유일한 조건),
숙달 판정 학생은 `/study`에서 404만 받았다 — 어댑터 5종 중 정확히 1종만 구조적으로 죽어 있었다.

────────────────────────────────────────────────────────────────────────────
왜 *참조*인가 (실체 저작이 아니라)
────────────────────────────────────────────────────────────────────────────
평가 재료를 새로 쓰지 않는다. 이미 **기계 검증을 통과한 자체 저작 문항**(`data/corpus/
problem_bank_*/problems.jsonl`)의 `verify{conditions, answer_map}`를 그대로 상속한다 — 그 재료가
`l3.verify_answer.verify_answer()`의 입력 형식과 *동일*하기 때문에 변환이 아니라 참조로 성립한다.
`concept_graph`의 `visualization_card_keys`(노드가 카드 실체가 아니라 키만 보유) 선례와 동형이다.

따라서 이 뱅크에는 **LLM 호출도, 새 저작도, 개념 설명 생성 폴백도 없다**. 매칭(개념 태그 →
문항)은 *빌드타임*에 끝나 있고(`harness/concept_assessment_index.py`), 런타임은 개념 code로 dict를
한 번 조회할 뿐이다 — 요청 경로에 매칭 비용이 0이고, 어떤 개념이 어떤 문항을 상속했는지가 코퍼스
산출물에 감사 가능하게 남는다.

────────────────────────────────────────────────────────────────────────────
정직한 실패 (침묵 실패 금지)
────────────────────────────────────────────────────────────────────────────
산출물 부재·손상은 **예외 타입명을 담은 경고 로그** 후 *빈 뱅크*로 강등한다(fail-soft). 강등의
결과는 "PROBLEM_BASED가 다시 렌더 불가"라는 *이 슬라이스 이전의 동작*이므로 학생 경로가 깨지지는
않는다. 다만 fail-open이 상시화되면 보호가 무력해지므로, 산출물의 실재성은 테스트가 동결한다
(`tests/backend/l3/render/test_assessment_bank.py`).

7계층: L3(렌더 재료). 빌드타임 코퍼스 산출물을 읽기만 하며 DB·ORM·LLM·네트워크를 건드리지 않는다
(`l3/notation_coverage.py`가 같은 계층에서 코퍼스를 읽는 선례). 어느 전략에 쓸지 *고르는* 책임은
L4에 있고, 주입 호출도 L4 공급 경로(`l4/content_supply.py`)가 한다.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from whymath_backend.l3.render.dsl import ConceptAssessment, ConceptDSL

logger = logging.getLogger("whymath.l3.render.assessment_bank")

# 코퍼스 산출물 경로 — 레포 루트 기준 고정(cwd 무관). 이 파일은
# src/backend/whymath_backend/l3/render/assessment_bank.py라 parents[5]가 레포 루트다
# (`l4/pedagogy/pack_registry.py`가 같은 관례로 코퍼스 디렉터리를 앵커한다).
_REPO_ROOT = Path(__file__).resolve().parents[5]
ASSESSMENT_INDEX_PATH = _REPO_ROOT / "data" / "corpus" / "concept_assessment_v1" / "index.json"

# 산출물 최상위 키 — 빌더(`harness/concept_assessment_index.py`)와 이 로더의 유일한 계약.
INDEX_ENTRIES_KEY = "entries"
INDEX_UNCOVERED_KEY = "uncovered_concept_codes"


def _entry_to_assessment(entry: Any) -> tuple[str, ConceptAssessment]:
    """산출물 항목 1건 → (개념 code, `ConceptAssessment`). 형식 위반은 예외(호출부가 타입명 로그).

    `conditions`는 문항 코퍼스가 str 또는 list 둘 다 쓰므로 여기서 튜플로 정규화한다. `prompt`는
    원천 문항의 발문을 그대로 상속하며(자체 저작·신규 저작 0), 없으면 None으로 두어 어댑터가
    기본 발문을 조립한다.
    """
    if not isinstance(entry, dict):
        raise TypeError(f"entries 항목이 dict가 아님: {type(entry).__name__}")
    code = str(entry["concept_code"]).strip()
    if not code:
        raise ValueError("concept_code가 빈 문자열")
    raw_conditions = entry["conditions"]
    conditions = (
        (str(raw_conditions),)
        if isinstance(raw_conditions, str)
        else tuple(str(c) for c in raw_conditions)
    )
    prompt_raw = entry.get("prompt")
    prompt = str(prompt_raw).strip() if isinstance(prompt_raw, str) and prompt_raw.strip() else None
    assessment = ConceptAssessment(
        conditions=conditions,
        answer_map={str(k): str(v) for k, v in dict(entry["answer_map"]).items()},
        prompt=prompt,
    )
    return code, assessment


@lru_cache(maxsize=1)
def get_assessment_bank() -> dict[str, ConceptAssessment]:
    """개념 code → `ConceptAssessment` 뱅크(1회 로드·인메모리·DB free).

    산출물이 없거나 최상위 형식이 깨졌으면 **예외 타입명을 담은 경고**를 남기고 빈 dict를 돌려준다
    (fail-soft — 강등 결과는 "PROBLEM_BASED 렌더 불가"로 이 슬라이스 이전 동작과 같다). 개별 항목이
    깨진 경우에도 그 항목만 건너뛰고 사유를 타입명과 함께 로그한다 — 조용히 삼키지 않는다.
    """
    try:
        payload = json.loads(ASSESSMENT_INDEX_PATH.read_text(encoding="utf-8"))
        entries = payload[INDEX_ENTRIES_KEY]
        if not isinstance(entries, list):
            raise TypeError(f"{INDEX_ENTRIES_KEY}가 list가 아님: {type(entries).__name__}")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        # 예외 *타입명*을 반드시 싣는다(무타입 경고 금지 — CLAUDE.md 침묵 실패 금지).
        logger.warning(
            "개념 평가 재료 참조 인덱스 로드 실패 — 빈 뱅크로 강등(PROBLEM_BASED 렌더 불가 유지). "
            "error_type=%s path=%s",
            type(exc).__name__,
            ASSESSMENT_INDEX_PATH,
        )
        return {}

    bank: dict[str, ConceptAssessment] = {}
    for position, entry in enumerate(entries):
        try:
            code, assessment = _entry_to_assessment(entry)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "개념 평가 재료 항목 건너뜀 — error_type=%s index=%d",
                type(exc).__name__,
                position,
            )
            continue
        bank[code] = assessment
    return bank


def uncovered_concept_codes() -> tuple[str, ...]:
    """참조 주입에 실패한(해당 검증 통과 문항 미보유) 개념 code 목록 — 침묵 통과 금지의 기록면.

    빌더가 산출물에 *명시적으로* 남긴 목록을 그대로 읽는다. "커버된 것만 세고 나머지를 안 세는"
    측정이 되지 않도록 미커버를 데이터로 보존하며, 감사·저작 우선순위 입력이 된다. 산출물이 없거나
    키가 없으면 빈 튜플이다(뱅크 로드 실패는 `get_assessment_bank`이 이미 경고했다).
    """
    try:
        payload = json.loads(ASSESSMENT_INDEX_PATH.read_text(encoding="utf-8"))
        codes = payload.get(INDEX_UNCOVERED_KEY, [])
        return tuple(str(c) for c in codes) if isinstance(codes, list) else ()
    except (OSError, ValueError) as exc:
        logger.warning(
            "미커버 개념 목록 조회 실패 — error_type=%s path=%s",
            type(exc).__name__,
            ASSESSMENT_INDEX_PATH,
        )
        return ()


def attach_assessment(dsl: ConceptDSL) -> ConceptDSL:
    """DSL에 평가 재료를 *참조 주입*한다 — 뱅크에 없으면 원본을 그대로 돌려준다(순수).

    이미 `assessment`를 가진 DSL은 건드리지 않는다(공급원이 여럿일 때 선주입을 덮어쓰지 않는다).
    반환은 항상 새 인스턴스거나 원본이며 입력을 변형하지 않는다 — 렌더 입력은 불변이어야 캐시
    자산으로 안전하다.
    """
    if dsl.assessment is not None:
        return dsl
    assessment = get_assessment_bank().get(dsl.code)
    if assessment is None:
        return dsl
    return dsl.model_copy(update={"assessment": assessment})


def reset_assessment_bank_cache() -> None:
    """뱅크 캐시 무효화 — 테스트 격리용(`pack_registry.reset_pack_cache` 동형).

    프로덕션 런타임은 산출물이 프로세스 수명 동안 고정이라 호출할 일이 없다(테스트 전용 seam).
    """
    get_assessment_bank.cache_clear()


__all__ = [
    "ASSESSMENT_INDEX_PATH",
    "INDEX_ENTRIES_KEY",
    "INDEX_UNCOVERED_KEY",
    "attach_assessment",
    "get_assessment_bank",
    "reset_assessment_bank_cache",
    "uncovered_concept_codes",
]
