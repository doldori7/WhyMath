"""데이터셋 v1 `src_id` → **canonical concept_id**(`math.<area>.<slug>`) 결정론적 매핑.

정본: docs/data/concept_graph.md §2.4(ID 규약)·§3.5(ID 안정성) +
docs/data/concept_graph_dataset_v1.md §2(주의)·§5b.1(매핑) +
docs/standards/part9_id_policy_review.md(P2d 마이그레이션 설계).

배경(2026-07-02 P2d·Part 9 엄격 시정·`MEMORY.md`): concept_id 정본을 옛 `{TRACK}-{AREA}-{NNN}`
(P2a·학년대=교육과정 배치가 key에 결합된 안티패턴)에서 **교육과정·언어·렌더러 무관 의미론 ID**
`math.<area>.<slug>`로 *전환*한다(P2a를 되돌리는 breaking change). 추적성은 **별칭(aliases)**·
**source_id**·**ids.yaml registry**로 보존한다(롤백·하위호환). 옛 `{TRACK}-{AREA}-{NNN}`은 폐기가
아니라 **교육과정축 코드(curriculum-axis code)** 오버레이/별칭으로 살려 matrix '개념 축' 조인을
떠받친다(curriculum overlay 원칙).

canonical ID 포맷(P2d 확정):

    concept_id = math.<area>.<slug>
      math   = 고정 subject(Phase 1 전건 수학)
      <area> = 교육과정-독립 영역어(_AREA_SLUG_MAP: GEO→geometry·CALC→calculus…·소문자·하이픈 허용)
      <slug> = name_ko의 결정론적 로마자화(hangul_romanize.romanize·외부 lib 0)

  - **area**: `_area_for_record`가 돌려주는 AREA 코드(GEO·CALC…·학년-독립)를 `_AREA_SLUG_MAP`으로
    교육과정-독립 영역어에 사상. 미매핑 category는 `_area_for_record`가 KeyError(taxonomy 가드).
  - **slug**: name_ko를 국립국어원 표기 간이 로마자화(결정론·멱등). 해독 불가면 romanize가 실패.
  - **충돌 접미**: grade 제거로 `[중]지수법칙`·`[고]지수법칙`이 같은 `math.algebra.…`로 충돌한다.
    `(area, slug)` 그룹 내 `(int(difficulty_tier), src_id)` 정렬(옛 NNN 정렬키 재사용)로 첫 항목은
    무접미·이후 `-2`/`-3`… 접미. 결정론·멱등. 접미 사실은 `ids.yaml`에 기록한다.

추적성(P2d 핵심):
  - 각 개념의 **source_id = src_id**(원천 보존).
  - 각 개념의 **aliases = [교육과정축 코드, old_UC, src_id]** — 교육과정축 코드는 옛 P2a 알고리즘
    (`build_curriculum_axis_map`)의 `{TRACK}-{AREA}-{NNN}`, old_UC는 옛 UC(`_build_legacy_uc`).
    새 canonical ID로 전환한 뒤에도 옛 키·원천 키로 찾을 수 있게 보존한다.
  - `build_id_map`은 `{src_id: canonical_id}`(정본·적재 입력), `build_curriculum_axis_map`은
    `{src_id: TRACK-AREA-NNN}`(오버레이), `build_legacy_uc_map`은 `{src_id: UC…}`,
    `build_alias_map`은 `{src_id: [axis, uc, src_id]}`를 반환한다.

법적: 여기서는 성취기준 *코드*와 name_ko만 읽어 area/slug를 만든다 — 성취기준 본문은 만지지 않는다.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Mapping, Sequence

from data_pipeline.concept_graph.hangul_romanize import romanize
from data_pipeline.concept_graph.models import (
    CONCEPT_ID_PATTERN,
    CURRICULUM_AXIS_PATTERN,
    LEGACY_UC_PATTERN,
)
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
    # --- 고1 기본수학(별책8·공통수학 대체 기본과목) ---
    # ★독립 AREA 네임스페이스(B-접두): 기본수학 어간은 `[기본]`을 *벗기지 않고* full key로 매핑한다.
    # 공통수학 AREA(EQN·FUN·COUNT…)에 합치면 (TRACK,AREA) 그룹이 섞여 NNN 재정렬→기존 공통
    # 개념의 `{TRACK}-{AREA}-{NNN}` concept_id(영구 브리지키)가 흔들린다. 분리하면 기존 ID 불변.
    "[기본]다항식": "BPOLY",
    "[기본]방정식과 부등식": "BEQN",
    "[기본]집합과 명제": "BLOGIC",
    "[기본]함수와 그래프": "BFUN",
    "[기본]도형의 방정식": "BCOORD",
    "[기본]경우의 수": "BCOUNT",
    "[기본]행렬": "BMATRIX",
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

# ──────────────────────────────────────────────────────────────────────
# AREA 코드(GEO·CALC…) → 교육과정-독립 영역어(canonical `<area>` 세그먼트·P2d).
# `_TOPIC_AREA_MAP` 값(41종)과 1:1 — import 시점에 전수 커버리지·형식을 단언한다.
# 기본수학 B*접두 코드(BEQN·BFUN…)는 대응 공통수학 영역어(equation·function…)로 합류한다 —
# canonical은 교육과정-독립이라 track 구분(옛 BEQN vs EQN)을 area에 담지 않고, 같은 name_ko가
# 두 트랙에 겹치면 결정론적 충돌 접미(-2)로 가른다(기본↔공통 22군 예상).
# ──────────────────────────────────────────────────────────────────────
_AREA_SLUG_MAP: dict[str, str] = {
    "ADDSUB": "addition",
    "ALG": "algebra",
    "ARITH": "arithmetic",
    "AIM": "ai-math",
    "BCOORD": "coordinate",
    "BCOUNT": "combinatorics",
    "BEQN": "equation",
    "BFUN": "function",
    "BLOGIC": "logic",
    "BMATRIX": "matrix",
    "BPOLY": "polynomial",
    "CALC": "calculus",
    "CHANCE": "chance",
    "COORD": "coordinate",
    "COUNT": "combinatorics",
    "CULT": "culture",
    "DATA": "data",
    "DECIMAL": "decimal",
    "DIV": "division",
    "ECON": "economics",
    "EQN": "equation",
    "FRAC": "fraction",
    "FUN": "function",
    "GEO": "geometry",
    "GRAPH": "graph",
    "INQ": "inquiry",
    "LOGIC": "logic",
    "MATRIX": "matrix",
    "MEAS": "measurement",
    "MUL": "multiplication",
    "NPLACE": "place-value",
    "NUMPROP": "number-property",
    "PATTERN": "pattern",
    "PROB": "probability",
    "RATIO": "ratio",
    "SHAPE": "shape",
    "SHELEM": "shape-element",
    "STAT": "statistics",
    "TRANSF": "transformation",
    "UNIT": "unit",
    "VOCA": "vocational-math",
}

# 전수 커버리지·형식 가드(import 시 1회) — _TOPIC_AREA_MAP 값 전건에 영역어가 있고, 영역어는
# 소문자로 시작하는 [a-z0-9-] 토큰(canonical <area> 세그먼트 규약)인지 단언한다.
_AREA_SLUG_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9-]*$")
if set(_AREA_SLUG_MAP) != set(_TOPIC_AREA_MAP.values()):  # pragma: no cover - 상수 가드
    _missing = set(_TOPIC_AREA_MAP.values()) - set(_AREA_SLUG_MAP)
    _extra = set(_AREA_SLUG_MAP) - set(_TOPIC_AREA_MAP.values())
    raise ValueError(
        f"_AREA_SLUG_MAP이 _TOPIC_AREA_MAP AREA 코드와 불일치 — 누락 {_missing}·잉여 {_extra}"
    )
for _area_code, _area_slug in _AREA_SLUG_MAP.items():
    if not _AREA_SLUG_TOKEN_PATTERN.match(_area_slug):  # pragma: no cover - 상수 가드
        raise ValueError(f"_AREA_SLUG_MAP 영역어 규약 위반: {_area_code!r} → {_area_slug!r}")
del _area_code, _area_slug

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


def _validate_overrides(
    override_map: Mapping[str, str], pattern: re.Pattern[str], label: str
) -> None:
    """override id들이 주어진 규약(pattern)을 지키고 서로 충돌하지 않는지 선검증."""
    seen: dict[str, str] = {}
    for src_id, cid in override_map.items():
        if not pattern.match(cid):
            raise ValueError(f"override {label} 규약 위반: {src_id!r} → {cid!r}")
        if cid in seen:
            raise ValueError(f"override {label} 충돌: {cid!r}를 {seen[cid]!r}·{src_id!r}가 공유")
        seen[cid] = src_id


# tier 결측 정렬키(맨 뒤로) — 어떤 실제 tier(≤24)보다 큼. 충돌 접미·옛 NNN 공용.
_TIER_LAST_SORT_KEY: int = 1 << 30


def _order_and_group(
    concepts: Iterable[Mapping[str, object]],
    key_of: Callable[[Mapping[str, object]], tuple[str, str]],
) -> tuple[list[str], dict[str, int | None], dict[tuple[str, str], list[str]]]:
    """1-pass 공용 헬퍼 — src_id 순서 보존 + tier 계산 + `key_of(record)` 그룹 버킷.

    `key_of`는 레코드 → (grp_a, grp_b) 그룹키 함수(canonical=(area_slug, slug)·axis=(track, area)).
    반환: (입력순 src_id 목록, {src_id: tier}, {그룹키: [src_id…]}).
    """
    order: list[str] = []
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

        tier_of[src_id] = _coerce_tier(record.get("difficulty_tier"))
        groups.setdefault(key_of(record), []).append(src_id)
    return order, tier_of, groups


def _sort_members(members: Sequence[str], tier_of: Mapping[str, int | None]) -> list[str]:
    """그룹 멤버를 `(tier, src_id)`로 정렬(tier 결측은 맨 뒤). 멱등 순번/접미 보장."""

    def _key(src_id: str) -> tuple[int, str]:
        tier = tier_of[src_id]
        return (tier if tier is not None else _TIER_LAST_SORT_KEY, src_id)

    return sorted(members, key=_key)


def _assemble_result(
    order: Sequence[str],
    auto_id: Mapping[str, str],
    override_map: Mapping[str, str],
    label: str,
) -> dict[str, str]:
    """입력 순서로 {src_id: id}. override 우선·충돌 검사(override 교차 가드)."""
    result: dict[str, str] = {}
    id_to_src: dict[str, str] = {}
    for src_id in order:
        cid = override_map.get(src_id, auto_id[src_id])
        if cid in id_to_src and id_to_src[cid] != src_id:
            raise ValueError(
                f"{label} 충돌: {cid!r}를 {id_to_src[cid]!r}·{src_id!r}가 공유 "
                "(override가 자동 ID와 겹쳤을 가능성 — override 값을 확인하세요)"
            )
        id_to_src[cid] = src_id
        result[src_id] = cid
    return result


def build_id_map(
    concepts: Iterable[Mapping[str, object]],
    *,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """concepts 레코드들 → `{src_id: canonical_id}` 매핑(정본·transform 입력).

    canonical ID(`math.<area>.<slug>`)는 *전역 2-pass*로 결정한다 — 충돌 접미가 (area, slug) 그룹
    안의 상대 순번이라 단건 함수로는 못 만들고 전체를 봐야 한다:

      1. **1-pass(그룹화)**: 각 src_id의 (area 영역어, slug, tier)를 (area, slug) 그룹에 모은다.
      2. **2-pass(접미부여)**: 그룹 안 `(tier, src_id)` 정렬 → 첫 항목 무접미·이후 `-2`/`-3`…(멱등).
         override가 있으면 그 src_id는 자동 접미 대신 override canonical_id를 쓴다.

    Args:
        concepts: 각 레코드는 최소 'src_id'·'category'·'name_ko'를 가진 매핑(+ standard_codes·tier).
        overrides: 전문가 재명명 {src_id: canonical_id}. 주입 시 그 src_id는 자동 발급 대신 override
            (단, override도 CONCEPT_ID_PATTERN 통과·매핑 내 유일해야 함).

    Returns:
        {src_id: canonical_id}. 입력 순서 보존(dict 삽입 순서).

    Raises:
        ValueError: src_id 중복/빈 src_id, override 위반·충돌, romanize 실패, 또는 canonical 충돌.
        KeyError: category가 _TOPIC_AREA_MAP에 없음(침묵 폴백 금지).
    """
    override_map = dict(overrides or {})
    _validate_overrides(override_map, CONCEPT_ID_PATTERN, "canonical_id")

    # ── (area 영역어, slug)로 계산·그룹. name_ko 로마자화 실패는 romanize가 ValueError.
    slug_of: dict[str, str] = {}
    area_slug_of: dict[str, str] = {}

    def _key(record: Mapping[str, object]) -> tuple[str, str]:
        src_id = str(record.get("src_id", "")).strip()
        area_slug = _AREA_SLUG_MAP[_area_for_record(record)]
        slug = romanize(str(record.get("name_ko", "")))
        area_slug_of[src_id] = area_slug
        slug_of[src_id] = slug
        return (area_slug, slug)

    order, tier_of, groups = _order_and_group(concepts, _key)

    # ── 2-pass: 그룹 안 (tier, src_id) 정렬 → 첫 무접미·이후 -N 접미.
    auto_id: dict[str, str] = {}
    for (area_slug, slug), members in groups.items():
        for seq, src_id in enumerate(_sort_members(members, tier_of), start=1):
            suffix = "" if seq == 1 else f"-{seq}"
            auto_id[src_id] = f"math.{area_slug}.{slug}{suffix}"

    result = _assemble_result(order, auto_id, override_map, "canonical_id")
    logger.info(
        "canonical_id 매핑 생성: %d개 src_id → %d개 유일 ID((area,slug) 그룹 %d개)",
        len(result),
        len(set(result.values())),
        len(groups),
    )
    return result


def build_curriculum_axis_map(
    concepts: Iterable[Mapping[str, object]],
    *,
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """concepts 레코드들 → `{src_id: 교육과정축 코드}`(옛 P2a `{TRACK}-{AREA}-{NNN}`) 매핑.

    **이 값은 이제 정본이 아니라 오버레이/별칭("curriculum-axis code")** — canonical(build_id_map)로
    이관하기 전 P2a ID를 그대로 산출해 `aliases`·`ids.yaml`에 보존한다(matrix '개념 축' 조인·롤백).
    산출 로직은 P2a와 동일: (TRACK, AREA) 그룹 안 `(tier, src_id)` 정렬 → NNN 부여(멱등).

    Args:
        concepts: 각 레코드는 최소 'src_id'·'category'를 가진 매핑(+ standard_codes·tier).
        overrides: {src_id: 교육과정축 코드}. override도 CURRICULUM_AXIS_PATTERN 통과·유일해야 함.

    Returns:
        {src_id: TRACK-AREA-NNN}. 입력 순서 보존.
    """
    override_map = dict(overrides or {})
    _validate_overrides(override_map, CURRICULUM_AXIS_PATTERN, "curriculum_axis_code")

    def _key(record: Mapping[str, object]) -> tuple[str, str]:
        codes = _normalized_codes(record)
        tier = _coerce_tier(record.get("difficulty_tier"))
        return (track_for_record(codes, tier), _area_for_record(record))

    order, tier_of, groups = _order_and_group(concepts, _key)

    auto_id: dict[str, str] = {}
    for (track, area), members in groups.items():
        for seq, src_id in enumerate(_sort_members(members, tier_of), start=1):
            auto_id[src_id] = f"{track}-{area}-{seq:03d}"

    return _assemble_result(order, auto_id, override_map, "curriculum_axis_code")


def build_legacy_uc_map(concepts: Iterable[Mapping[str, object]]) -> dict[str, str]:
    """concepts 레코드들 → `{src_id: 레거시 UC}`(옛 `UC.<domain>.<topic>.<slug>`) 매핑.

    옛 UC 알고리즘(`_build_legacy_uc`)을 재현한다 — canonical 전환 뒤에도 옛 UC 키로 개념을 찾을 수
    있게 `aliases`·`ids.yaml`에 보존한다(롤백·하위호환 join).
    """
    uc_map: dict[str, str] = {}
    for record in concepts:
        src_id = str(record.get("src_id", "")).strip()
        if not src_id:
            raise ValueError(f"src_id가 빈 레코드: {record!r}")
        uc_map[src_id] = _build_legacy_uc(src_id, _normalized_codes(record))
    return uc_map


def build_alias_map(concepts: Iterable[Mapping[str, object]]) -> dict[str, list[str]]:
    """concepts 레코드들 → `{src_id: [교육과정축 코드, old_UC, src_id]}` 별칭 테이블(추적성·롤백).

    별칭 순서는 [교육과정축 코드(P2a), 레거시 UC, src_id]다 — canonical 전환 뒤에도 옛 키·원천 키로
    개념을 찾도록 보존한다(matrix 개념축 조인·롤백·하위호환). transform이 각 `Concept.aliases`에
    그대로 싣는다. records를 세 번 순회하지 않도록 axis/uc 맵을 합성한다.
    """
    records = list(concepts)
    axis_map = build_curriculum_axis_map(records)
    uc_map = build_legacy_uc_map(records)
    return {src_id: [axis_map[src_id], uc_map[src_id], src_id] for src_id in axis_map}


def to_csv_rows(id_map: Mapping[str, str]) -> list[dict[str, str]]:
    """매핑 테이블 → CSV 행(검토용). 컬럼: src_id, concept_id(canonical ID)."""
    return [{"src_id": src_id, "concept_id": cid} for src_id, cid in id_map.items()]


__all__ = [
    "build_alias_map",
    "build_curriculum_axis_map",
    "build_id_map",
    "build_legacy_uc_map",
    "strip_level_prefix",
    "to_csv_rows",
    "track_for_record",
]
