"""데이터셋 v1 `src_id` → **새 concept_id**(`{TRACK}-{AREA}-{NNN}`) 결정론적 매핑.

정본: docs/data/concept_graph.md §2.4(ID 규약)·§3.5(ID 안정성) +
docs/data/concept_graph_dataset_v1.md §2(주의)·§5b.1(매핑) +
docs/data/curriculum_master_v2_integration_review.md(P2 마이그레이션 설계).

배경(2026-06-16 결정·`MEMORY.md`): concept_id 정본을 기존 `UC.<domain>.<topic>.<slug>`에서
**`{TRACK}-{AREA}-{NNN}`**(예 `ELEM-GEO-001`)로 *전환*한다. 이는 의도적 breaking change다 —
`concept.schema.yaml`의 "발급 후 변경금지"를 깨되, 추적성은 **별칭(aliases)**과 **source_id**로
보존한다(롤백·하위호환). 커밋된 코퍼스는 `src_id` 기반이고 UC/새 ID는 *파생*이라, 재ID는
대부분 *파생 규칙 교체 + 하위 변경*으로 끝난다.

ID 포맷(Kiki 확정):

    concept_id = {TRACK}-{AREA}-{NNN}
      TRACK ∈ {ELEM, MID, HIGH, RT, OLY}   # 코퍼스엔 ELEM/MID/HIGH만·RT/OLY는 regex 예약
      AREA  = 토픽 ascii 코드(2~8 대문자/숫자) — `category`에서 파생
      NNN   = (TRACK, AREA) 안 3자리 zero-pad 순번

  - **TRACK**: 첫 `standard_code` 학년대수 → 2/4/6=`ELEM`·9=`MID`·10/12=`HIGH`
    (`parse_standard_code`+`_GRADE_TRACK_MAP`). standard_codes가 없거나 모두 파싱 실패면
    `difficulty_tier` 밴드로 폴백(0~8=ELEM·9~16=MID·17~24=HIGH). tier도 없으면 최종 `MID`.
    실데이터 403건은 전부 standard_codes를 가져 폴백은 이론 경로지만 구현·문서화한다.
  - **AREA**: `category`의 레벨 접두사(`[고]`/`[중]`/`[공통]`)를 *먼저 제거*한 뒤 토픽 한글을
    짧은 ascii 니모닉으로 매핑(`_TOPIC_AREA_MAP`·37개 category 전수). 같은 토픽 어간이 레벨만
    다르면(예 `[중]기하`·`[고]기하`) **AREA를 공유**하고 TRACK이 구분한다. 미수록 category는
    *침묵 폴백 금지* — `KeyError`로 시끄럽게 실패한다(taxonomy 누수 가드).
  - **NNN**: (TRACK, AREA) 그룹 안에서 `(int(difficulty_tier), src_id)`로 정렬해 001·002…
    부여. 재실행 시 동일 ID 재현(멱등). difficulty_tier 결측은 큰 값(맨 뒤)으로 취급.

추적성(P2 핵심):
  - 각 개념의 **source_id = src_id**(원천 보존).
  - 각 개념의 **aliases = [old_UC, src_id]** — old_UC는 *이전 알고리즘*(`_build_legacy_uc`)이
    만들던 UC다(롤백·하위호환 join용). 새 ID로의 전환 후에도 옛 키로 찾을 수 있게 보존한다.
  - `build_id_map`은 `{src_id: new_id}`를 반환(검토·적재 입력), `build_alias_map`은
    `{src_id: [old_UC, src_id]}`를 반환한다.

법적: 여기서는 성취기준 *코드*만 읽어 TRACK/AREA를 만든다 — 본문은 일절 만지지 않는다.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Mapping, Sequence

from data_pipeline.concept_graph.models import CONCEPT_ID_PATTERN, LEGACY_UC_PATTERN
from data_pipeline.concept_graph.seed import _subject_abbr
from data_pipeline.ncic.transform import TransformError, parse_standard_code

logger = logging.getLogger("data_pipeline.concept_graph.idmap")

# ──────────────────────────────────────────────────────────────────────
# TRACK — 첫 standard_code 학년대수 → 트랙. 코퍼스 학년 집합 {2,4,6,9,10,12}와 1:1.
# (RT 재수·OLY 영재는 후속 트랙 — regex엔 예약돼 있으나 코퍼스엔 없다.)
# ──────────────────────────────────────────────────────────────────────
_GRADE_TRACK_MAP: dict[str, str] = {
    "2": "ELEM",
    "4": "ELEM",
    "6": "ELEM",
    "9": "MID",
    "10": "HIGH",
    "12": "HIGH",
}

# difficulty_tier 폴백 밴드(standard_codes 없음/파싱 실패 시). 코퍼스 tier 범위 [0,24]를 3등분.
# 실데이터 403건은 전부 코드를 가져 이 경로는 이론적이지만, RT/OLY 등 미래 무코드 개념 대비.
_TIER_TRACK_BANDS: tuple[tuple[int, str], ...] = (
    (8, "ELEM"),  # tier 0~8
    (16, "MID"),  # tier 9~16
    (24, "HIGH"),  # tier 17~24
)
# tier도 standard_code도 없을 때 최종 폴백(가장 중립적인 중간 트랙).
_TRACK_LAST_RESORT: str = "MID"

# ──────────────────────────────────────────────────────────────────────
# AREA — `category`(레벨 접두사 제거 후 토픽 어간) → ascii 니모닉(2~8 대문자/숫자).
# 데이터셋 v1의 37개 category 전수 매핑(어간 35종 — `기하`·`함수`는 레벨만 달라 어간 공유).
# 같은 어간이 여러 레벨에 나오면 AREA를 공유하고 TRACK이 구분한다(예 [중]기하·[고]기하 → GEO).
# 미수록 어간은 침묵 폴백 없이 KeyError(시끄러운 실패 — taxonomy 누수 즉시 발견).
# ──────────────────────────────────────────────────────────────────────
_TOPIC_AREA_MAP: dict[str, str] = {
    # --- 고등(선택·진로) ---
    "경제 수학": "ECON",
    "기하": "GEO",  # [중]기하·[고]기하 공유(TRACK 구분)
    "대수": "ALG",
    "미적분": "CALC",
    "수학과 문화": "CULT",
    "수학과제 탐구": "INQ",
    "실용 통계": "STAT",
    "인공지능 수학": "AIM",
    "직무 수학": "VOCA",
    "확률·통계": "PROB",
    # --- 공통(고1 공통수학) ---
    "경우의 수": "COUNT",
    "도형의 방정식": "COORD",
    "식·방정식·부등식": "EQN",  # [중]문자·식·방정식과 다른 어간이나 같은 AREA(EQN)·TRACK 구분
    "집합과 명제": "LOGIC",
    "함수": "FUN",  # [중]함수·[공통]함수 공유(TRACK 구분)
    "행렬": "MATRIX",
    # --- 중학교 ---
    "문자·식·방정식": "EQN",
    "수와 연산": "ARITH",
    "자료와 가능성": "DATA",
    # --- 초등 ---
    "가능성": "CHANCE",
    "곱셈": "MUL",
    "규칙·대응": "PATTERN",
    "나눗셈": "DIV",
    "덧셈·뺄셈": "ADDSUB",
    "도형(평면·입체)": "SHAPE",
    "도형의 요소": "SHELEM",
    "둘레·넓이·부피": "MEAS",
    "분수": "FRAC",
    "비와 비율": "RATIO",
    "소수": "DECIMAL",
    "수의 성질·어림": "NUMPROP",
    "자료·그래프": "GRAPH",
    "자연수·자릿값": "NPLACE",
    "측정(단위)": "UNIT",
    "합동·대칭·이동": "TRANSF",
}

# AREA 코드가 모두 형식(2~8 대문자/숫자)을 지키는지 import 시점 1회 단언(오타·길이 가드).
_AREA_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"^[A-Z0-9]{2,8}$")
for _stem, _area in _TOPIC_AREA_MAP.items():
    if not _AREA_TOKEN_PATTERN.match(_area):  # pragma: no cover - 상수 가드(개발 중 오타 차단)
        raise ValueError(f"_TOPIC_AREA_MAP AREA 코드 규약 위반: {_stem!r} → {_area!r}")
del _stem, _area

# category 레벨 접두사 — AREA 매핑 전에 제거. (없으면 그대로 — 초등 category엔 접두사 없음.)
_LEVEL_PREFIXES: tuple[str, ...] = ("[고]", "[중]", "[공통]")

# 레거시 UC slug 안전화 치환(이전 알고리즘 재현용 — 별칭 생성에만 쓴다).
_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9-]+")
_SLUG_MULTI_DASH = re.compile(r"-+")

# 레거시 폴백 도메인·토픽(이전 알고리즘 — standard_codes 없음/파싱 실패 시).
_LEGACY_FALLBACK_DOMAIN: str = "x"
_LEGACY_FALLBACK_TOPIC: str = "misc"


def strip_level_prefix(category: str) -> str:
    """`category`에서 레벨 접두사(`[고]`/`[중]`/`[공통]`)를 제거한 토픽 어간.

    '[고]미적분'→'미적분', '[중]기하'→'기하', '[공통]함수'→'함수', '분수'→'분수'(접두사 없음).
    """
    text = category.strip()
    for prefix in _LEVEL_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _track_for_grade(grade: str) -> str | None:
    """학년대수(parse_standard_code의 group1) → TRACK. 미수록 학년은 None(폴백 유도)."""
    return _GRADE_TRACK_MAP.get(grade)


def _track_from_codes(standard_codes: Sequence[str]) -> str | None:
    """첫 파싱 가능한 standard_code의 학년 → TRACK. 코드 없음/모두 실패면 None."""
    for code in standard_codes:
        try:
            grade, _subject, _domain, _seq = parse_standard_code(code)
        except TransformError:
            continue
        track = _track_for_grade(grade)
        if track is not None:
            return track
    return None


def _track_from_tier(difficulty_tier: int | None) -> str:
    """difficulty_tier → TRACK(폴백). 밴드: 0~8 ELEM·9~16 MID·17~24 HIGH. None이면 최종 폴백."""
    if difficulty_tier is None:
        return _TRACK_LAST_RESORT
    for ceiling, track in _TIER_TRACK_BANDS:
        if difficulty_tier <= ceiling:
            return track
    return "HIGH"  # tier가 24 초과(이론상 불가 — 모델 ge/le가 막음)면 최상위 트랙


def _coerce_tier(value: object) -> int | None:
    """difficulty_tier raw 값 → int|None(빈/None/비정수는 None). NNN 정렬·폴백 공용."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def track_for_record(standard_codes: Sequence[str], difficulty_tier: int | None) -> str:
    """단일 개념의 TRACK 결정 — standard_code 우선, 없으면 tier 밴드, 그것도 없으면 최종 폴백.

    실데이터는 모두 standard_codes를 가져 코드 경로로 끝나지만(폴백 0건), 규칙은 결정론적이고
    무코드(미래 RT/OLY 등) 개념도 안전하게 분류한다.
    """
    track = _track_from_codes(standard_codes)
    if track is not None:
        return track
    logger.debug("standard_code TRACK 결정 실패 — tier 폴백(tier=%r)", difficulty_tier)
    return _track_from_tier(difficulty_tier)


def _area_for_category(category: str) -> str:
    """`category`(레벨 접두사 제거 후) → AREA 코드. 미수록 어간은 KeyError(시끄러운 실패).

    침묵 폴백을 두지 않는다 — 새 category가 들어오면 즉시 깨져 taxonomy 누수를 막는다(요구사항).
    """
    stem = strip_level_prefix(category)
    try:
        return _TOPIC_AREA_MAP[stem]
    except KeyError as exc:
        raise KeyError(
            f"미매핑 category 어간: {stem!r}(원본 {category!r}). "
            "_TOPIC_AREA_MAP에 AREA 코드를 추가하세요(침묵 폴백 금지 — taxonomy 누수 가드)."
        ) from exc


def _area_for_record(record: Mapping[str, object]) -> str:
    """레코드의 category → AREA. category 결측/공백도 KeyError(필수 필드 누수 가드)."""
    category = str(record.get("category", "")).strip()
    return _area_for_category(category)


# ──────────────────────────────────────────────────────────────────────
# 레거시 UC 생성(이전 알고리즘) — 별칭(aliases) 보존 전용. 새 ID와 무관하게 재현.
# ──────────────────────────────────────────────────────────────────────
def _slugify_src_id(src_id: str) -> str:
    """`src_id` → 레거시 UC slug(이전 `slugify_src_id`와 동일). 별칭 생성에만 쓴다."""
    lowered = src_id.lower().replace(":", "-")
    cleaned = _SLUG_NON_ALNUM.sub("-", lowered)
    collapsed = _SLUG_MULTI_DASH.sub("-", cleaned).strip("-")
    if not collapsed:
        raise ValueError(f"src_id에서 레거시 UC slug를 만들 수 없음(영숫자 없음): {src_id!r}")
    return collapsed


def _legacy_domain_topic(standard_codes: Sequence[str]) -> tuple[str, str]:
    """이전 알고리즘의 (도메인약칭, 토픽) — 첫 파싱 가능한 코드 기반·폴백 UC.x.misc."""
    for code in standard_codes:
        try:
            _grade, subject_token, domain_code, _seq = parse_standard_code(code)
        except TransformError:
            continue
        return _subject_abbr(subject_token), f"a{domain_code}"
    return _LEGACY_FALLBACK_DOMAIN, _LEGACY_FALLBACK_TOPIC


def _build_legacy_uc(src_id: str, standard_codes: Sequence[str]) -> str:
    """이전 알고리즘이 만들던 UC(`UC.<domain>.<topic>.<slug>`) 재현 — 별칭 보존용.

    새 ID 체계와 독립적으로 결정론적이며 `LEGACY_UC_PATTERN`을 통과한다. 롤백·하위호환 join에서
    옛 키로 개념을 찾을 수 있도록 `aliases`에 싣는다.
    """
    domain, topic = _legacy_domain_topic(standard_codes)
    slug = _slugify_src_id(src_id)
    uc = f"UC.{domain}.{topic}.{slug}"
    if not LEGACY_UC_PATTERN.match(uc):  # pragma: no cover - 슬러그화가 규약 보장하나 방어
        raise ValueError(f"레거시 UC 규약 위반: {uc!r} (src_id={src_id!r})")
    return uc


def _normalized_codes(record: Mapping[str, object]) -> list[str]:
    """레코드의 standard_codes → list[str](비-시퀀스/None은 빈 목록)."""
    raw = record.get("standard_codes") or []
    if isinstance(raw, Sequence) and not isinstance(raw, str):
        return [str(c) for c in raw]
    return []


def _validate_overrides(override_map: Mapping[str, str]) -> None:
    """override concept_id들이 새 규약을 지키고 서로 충돌하지 않는지 선검증."""
    seen: dict[str, str] = {}
    for src_id, cid in override_map.items():
        if not CONCEPT_ID_PATTERN.match(cid):
            raise ValueError(f"override concept_id 규약 위반: {src_id!r} → {cid!r}")
        if cid in seen:
            raise ValueError(f"override concept_id 충돌: {cid!r}를 {seen[cid]!r}·{src_id!r}가 공유")
        seen[cid] = src_id


def build_id_map(
    concepts: Iterable[Mapping[str, object]],
    *,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """concepts 레코드들 → `{src_id: concept_id}` 매핑(검토용·transform 입력).

    새 ID(`{TRACK}-{AREA}-{NNN}`)는 *전역 2-pass*로 결정한다 — NNN이 (TRACK, AREA) 그룹 안의
    상대 순번이라 단건 함수로는 못 만들고 전체를 봐야 한다:

      1. **1-pass(그룹화)**: 각 src_id의 (TRACK, AREA, tier)를 계산해 그룹 버킷에 모은다.
      2. **2-pass(번호부여)**: 그룹 안에서 `(tier, src_id)` 정렬 → 001·002… 부여(멱등).
         override가 있으면 그 src_id는 자동 번호 대신 override concept_id를 쓴다.

    Args:
        concepts: 각 레코드는 최소 'src_id'·'category'를 가진 매핑(+ standard_codes·tier).
        overrides: 전문가 재명명 {src_id: concept_id}. 주입 시 그 src_id는 자동 번호 대신 override를
            쓴다(단, override도 CONCEPT_ID_PATTERN 통과·매핑 내 유일해야 함).

    Returns:
        {src_id: concept_id}. 입력 순서 보존(dict 삽입 순서).

    Raises:
        ValueError: src_id 중복/빈 src_id, override 규약 위반·충돌, 또는 (이론상) 새 ID 충돌.
        KeyError: category가 _TOPIC_AREA_MAP에 없음(침묵 폴백 금지).
    """
    override_map = dict(overrides or {})
    _validate_overrides(override_map)

    # ── 1-pass: src_id 순서 보존 + (TRACK, AREA, tier) 계산 + 그룹 버킷.
    order: list[str] = []
    track_area_of: dict[str, tuple[str, str]] = {}
    tier_of: dict[str, int | None] = {}
    seen_src: set[str] = set()
    groups: dict[tuple[str, str], list[str]] = {}

    for record in concepts:
        src_id = str(record.get("src_id", "")).strip()
        if not src_id:
            raise ValueError(f"src_id가 빈 레코드: {record!r}")
        if src_id in seen_src:
            raise ValueError(f"src_id 중복: {src_id!r}")
        seen_src.add(src_id)
        order.append(src_id)

        codes = _normalized_codes(record)
        tier = _coerce_tier(record.get("difficulty_tier"))
        track = track_for_record(codes, tier)
        area = _area_for_record(record)
        track_area_of[src_id] = (track, area)
        tier_of[src_id] = tier
        groups.setdefault((track, area), []).append(src_id)

    # ── 2-pass: 그룹 안 (tier, src_id) 정렬 → 자동 NNN. tier 결측은 맨 뒤(큰 값 대용).
    _tier_last = 1 << 30  # tier 결측 정렬키(맨 뒤로) — 어떤 실제 tier(≤24)보다 큼.

    def _sort_key(src_id: str) -> tuple[int, str]:
        """(tier, src_id) 정렬키 — tier 결측은 맨 뒤. 멱등 NNN 보장."""
        tier = tier_of[src_id]
        return (tier if tier is not None else _tier_last, src_id)

    auto_id: dict[str, str] = {}
    for (track, area), members in groups.items():
        for seq, src_id in enumerate(sorted(members, key=_sort_key), start=1):
            auto_id[src_id] = f"{track}-{area}-{seq:03d}"

    # ── 산출: 입력 순서로 {src_id: concept_id}. override 우선. 충돌 검사(override 교차 가드).
    result: dict[str, str] = {}
    id_to_src: dict[str, str] = {}
    for src_id in order:
        cid = override_map.get(src_id, auto_id[src_id])
        if cid in id_to_src and id_to_src[cid] != src_id:
            raise ValueError(
                f"concept_id 충돌: {cid!r}를 {id_to_src[cid]!r}·{src_id!r}가 공유 "
                "(override가 자동 ID와 겹쳤을 가능성 — override 값을 확인하세요)"
            )
        id_to_src[cid] = src_id
        result[src_id] = cid

    logger.info(
        "concept_id 매핑 생성: %d개 src_id → %d개 유일 ID(그룹 %d개)",
        len(result),
        len(id_to_src),
        len(groups),
    )
    return result


def build_alias_map(concepts: Iterable[Mapping[str, object]]) -> dict[str, list[str]]:
    """concepts 레코드들 → `{src_id: [old_UC, src_id]}` 별칭 테이블(추적성·롤백).

    old_UC는 이전 알고리즘(`_build_legacy_uc`)이 만들던 UC다. 새 ID로 전환한 뒤에도 옛 키·원천
    키로 개념을 찾을 수 있도록 보존한다. transform이 각 `Concept.aliases`에 그대로 싣는다.
    """
    aliases: dict[str, list[str]] = {}
    for record in concepts:
        src_id = str(record.get("src_id", "")).strip()
        if not src_id:
            raise ValueError(f"src_id가 빈 레코드: {record!r}")
        codes = _normalized_codes(record)
        old_uc = _build_legacy_uc(src_id, codes)
        aliases[src_id] = [old_uc, src_id]
    return aliases


def to_csv_rows(id_map: Mapping[str, str]) -> list[dict[str, str]]:
    """매핑 테이블 → CSV 행(검토용). 컬럼: src_id, concept_id(새 ID)."""
    return [{"src_id": src_id, "concept_id": cid} for src_id, cid in id_map.items()]


__all__ = [
    "build_alias_map",
    "build_id_map",
    "strip_level_prefix",
    "to_csv_rows",
    "track_for_record",
]
