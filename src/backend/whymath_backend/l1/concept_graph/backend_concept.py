"""개념그래프 → backend 런타임 `Concept` ORM 적재 — UC↔UUID 브리지(개념그래프 소비 *브리지* 슬1).

L1 개념그래프 *소비* 트랙의 **브리지 슬라이스**다. 적재 아크(슬1~4)·소비 슬1(슬117)이 개념을
Neo4j(슬2)·pgvector `concept_embedding`(슬3)·`concept_node`(슬117) **세 투영에 UC 키**로 적재했지만,
*런타임 개념 엔티티* backend `concept` 테이블(UUID PK·`code` unique)은 **비어 있고 UC와 미연결**이다
(`concept_node` 모듈 docstring: "backend PG `concept` 테이블[UUID PK+code]과는 *여전히 별개*다").
런타임 소비처 — L2 `mastery_tracking`(concept_mastery_history.concept_id=UUID)·`problem_concept`
(concept_id=UUID FK)·L4 coach — 는 backend `concept` UUID를 참조하므로, 개념그래프가 런타임에서
보이지 않는다.

이 모듈이 그 다리를 놓는다(**결정 A**): `graph.json`의 개념을 backend `Concept` ORM 행으로 적재하되
**`code`=UC**(concept_id)로 둔다. 그러면 한 논리키 UC가 *사중 store*(Neo4j 그래프·pgvector 벡터·
`concept_node` 메타·backend `concept` 런타임 UUID)를 잇고, 런타임 경로가 닫힌다:
L2 mastery(UUID concept) → `concept.code`(UC) → `concept_node`/`concept_embedding`/Neo4j 도달.

────────────────────────────────────────────────────────────────────────────
redaction (CLAUDE.md 우선순위 #2 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
backend `Concept`의 `description`·`formal_definition`·`intuitive_explanation`은 **건드리지 않는다**
(NULL 유지). 셋 다 *검수 책임 자유 서술*(`schema.Concept` 법적 메모)이고, ① graph.json에 부재이며
(`_provenance.json` redacted: `concepts.description`·`concepts.formal_definition`) ② 이 적재기가
*읽지도 않고* ③ 채우지도 않는다(삼중 방어). `metaphor` 같은 안전 자체작성 필드도 `intuitive_
explanation`에 *욱여넣지 않는다* — 그 컬럼은 검수 통과한 직관 설명용이라 혼동·검수책임을 만들지
않게 보수적으로 비워 둔다(필요 시 후속 검수 슬라이스). `common_misconceptions`(JSONB)에 graph의
`misconception_text`(자유 텍스트·자체 작성)를 *선택적으로* 싣는다 — 이는 본문이 아니라 자유형
오개념 주석이며, 카탈로그 코드(`misconception_codes`)와 *별개*임을 형태로 명시한다.

────────────────────────────────────────────────────────────────────────────
필드 매핑 (graph.json Concept → backend Concept)
────────────────────────────────────────────────────────────────────────────
직결:
  - `concept_id`(UC) → **`code`**(브리지 키·UNIQUE). `name_ko` → `name_ko`.
  - `common_misconceptions` ← `misconception_text`(있으면 1원소 JSONB·자유형).
유도(소스 신호가 깔끔히 대응할 때만):
  - `subject` ← `domain` 매핑(고 4과목 + `[공통]…`→공통, 그 외는 NULL — 억지 매핑 0).
  - `intrinsic_difficulty`[1,5] ← `difficulty_tier`[0,24] 선형 스케일(0→1.0·24→5.0).
필수 NOT NULL인데 소스 부재 → 보수 유도:
  - `level`(NOT NULL `concept_level_enum`) ← **`세부개념`**(고정). graph 403개는 전부 세부 개념
    노드(단원·소단원 위계가 아니라 평면 개념 목록)라 *교수학적으로 정확한* 유도다(날조 아님).
    'unspecified' enum 값 추가·nullable화 같은 스키마 변경을 피한다(마이그레이션 0).
미매핑(NULL/기본 유지·교수학 내용 날조 금지):
  - `name_en`·`aliases`·`parent_concept_id`·`curriculum_version`·`grade_introduced`·
    `semester_introduced`·`is_signature_korean`(기본 False)·`cognitive_type`·
    `recommended_visual_styles`·`exam_frequency`·`weight_in_curriculum`·`embedding_id`·
    `description`·`formal_definition`·`intuitive_explanation` — 소스에 합당한 대응 없음 → 검수 대기.

graph의 `grade_band_hint`·`standard_codes`·`ccss_code`·`metaphor`·`accepted_expressions`·
`review_status`·`prerequisite_concept_ids`·`misconception_codes`·`visualization_card_keys`·`notes`는
backend `Concept` 스키마에 *대응 컬럼이 없다* — `concept_node`(슬117) 프로젝션이 그 메타를 UC 키로
이미 보관하므로, 이 런타임 엔티티엔 *런타임 결선에 필요한 최소 식별*(code=UC·name_ko·subject·
난이도·오개념)만 적재한다(이중 보관 회피·후속 consolidation 후보 — 보고 ⑥).

────────────────────────────────────────────────────────────────────────────
멱등 (UC 충돌 upsert·UUID PK 보존)
────────────────────────────────────────────────────────────────────────────
`code`(UC)가 UNIQUE라 `INSERT ... ON CONFLICT(code) DO UPDATE`로 멱등 적재한다 — 같은 UC 재적재는
*기존 행을 갱신*하고 **UUID PK를 보존**한다(신규 행만 `gen_random_uuid()` server_default로 발급).
이는 결정적이다: L2 mastery·problem_concept이 이미 그 UUID를 참조 중일 수 있으므로 재적재가
UUID를 바꾸면 안 된다. ON CONFLICT는 PK(concept_id)를 SET하지 않아 보존된다.

403 전량 적재(`review_status` 무관 — 게이팅은 조회 몫·슬2/3/117 동형). 본 적재기는 *런타임 엔티티*
존재를 보장할 뿐, 노출 게이팅은 소비처(검색 `reviewed_only`·L2/L4)가 건다.

────────────────────────────────────────────────────────────────────────────
sync 엔진 (벡터 store 좌석 규약 재사용·신규 seam 0)
────────────────────────────────────────────────────────────────────────────
슬3 `embedding._build_sync_engine`(sync psycopg·지연 import·`db_disable_pool` NullPool 가드)을
*그대로 재사용*한다(슬117 `node_projection`과 동일 — 같은 코드베이스 sync 좌석 규약·CLAUDE.md
신규 금지). 이 적재기는 벡터 컬럼을 만지지 않으나 pgvector 어댑터 등록은 무해(no-op)하다. sync URL은
`Settings.sync_database_url`(env 파생)·자격증명 0 하드코딩.

7계층: L1 데이터 기반의 *런타임 엔티티 적재*. 소비(L2 약개념 추천·L4 결선)는 이 행을 쓰되 여기서
구현하지 않는다(역방향 의존 금지·후속).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from whymath_backend.config import Settings, get_settings

# 슬3 sync 엔진 빌더 재사용(신규 seam 0) — 슬117 node_projection과 동일 규약.
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.schema.enums import ConceptLevel, Subject

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# ──────────────────────────────────────────────────────────────────────────
# 유도 상수·매핑
# ──────────────────────────────────────────────────────────────────────────
# graph 403개 노드는 전부 *세부개념*(평면 개념 목록·단원/소단원 위계 아님) → level 고정 유도.
# 'unspecified' enum 추가·nullable화(스키마 변경)를 피하는 교수학적으로 정확한 기본값.
_DEFAULT_LEVEL: ConceptLevel = ConceptLevel.세부개념

# difficulty_tier[0, 24] → intrinsic_difficulty[1.0, 5.0] 선형 스케일(0→1.0·24→5.0).
# Numeric(3,2) 정밀도(소수 2자리)로 반올림(컬럼 정합·재적재 결정론).
_DIFFICULTY_TIER_MAX: int = 24
_DIFFICULTY_MIN: float = 1.0
_DIFFICULTY_MAX: float = 5.0
_DIFFICULTY_DECIMALS: int = 2

# graph `domain`(category, 예 '[고]미적분') → backend Subject enum. 고 4과목만 직접 대응하고,
# '[공통]…'는 공통, 그 외(초·중 영역·기타 고 과목)는 *NULL*(억지 매핑 금지 — subject는 nullable).
_SUBJECT_BY_DOMAIN: dict[str, Subject] = {
    "[고]미적분": Subject.미적분,
    "[고]기하": Subject.기하,
    "[고]확률·통계": Subject.확통,
    "[고]인공지능 수학": Subject.인공지능수학,
}
_COMMON_DOMAIN_PREFIX: str = "[공통]"


def _opt_str(value: object) -> str | None:
    """빈 문자열·None → None, 그 외 strip한 str(transform `_opt`·node_projection 미러)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_int(value: object) -> int | None:
    """정수 옵션 파싱 — 빈/None/비정수는 None(transform `_int_opt`·node_projection 미러)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def map_subject(domain: str | None) -> Subject | None:
    """graph `domain`(category) → backend `Subject` enum 또는 None(미대응).

    고 4과목('[고]미적분'·'[고]기하'·'[고]확률·통계'·'[고]인공지능 수학')만 직접 대응하고,
    '[공통]…' 접두는 공통으로 본다. 그 외(초·중 영역·대수·경제 수학 등 enum에 없는 과목)는 None
    (subject는 nullable — 억지 매핑·날조 금지). 빈 domain도 None.
    """
    if not domain:
        return None
    if domain in _SUBJECT_BY_DOMAIN:
        return _SUBJECT_BY_DOMAIN[domain]
    if domain.startswith(_COMMON_DOMAIN_PREFIX):
        return Subject.공통
    return None


def scale_difficulty(difficulty_tier: int | None) -> float | None:
    """difficulty_tier[0, 24] → intrinsic_difficulty[1.0, 5.0] 선형 스케일(None→None).

    0→1.0·12→3.0·24→5.0. tier가 범위를 벗어나도(이론상 schema ge=0 le=24가 막음) clamp해
    Numeric(3,2)·schema ge=1 le=5 제약을 위반하지 않게 한다(방어). 소수 2자리 반올림.
    """
    if difficulty_tier is None:
        return None
    clamped = max(0, min(_DIFFICULTY_TIER_MAX, difficulty_tier))
    scaled = _DIFFICULTY_MIN + (clamped / _DIFFICULTY_TIER_MAX) * (
        _DIFFICULTY_MAX - _DIFFICULTY_MIN
    )
    return round(scaled, _DIFFICULTY_DECIMALS)


def _build_misconceptions(misconception_text: str | None) -> list[dict[str, Any]]:
    """graph `misconception_text`(자유 텍스트) → `common_misconceptions` JSONB(0/1 원소).

    빈/None이면 빈 리스트(컬럼 server_default '[]'와 정합). 값이 있으면 1원소 dict를 만들되,
    *자유형 오개념 주석*임을 형태로 명시한다(`misconception`만·`correction`은 검수 책임이라
    비움 — schema 예시 `{"misconception":"...","correction":"..."}` 호환·correction 날조 금지).
    이는 성취기준 *본문*이 아니라 자체 작성 자유 텍스트라 redaction 대상이 아니다(자유형
    오개념 카탈로그 코드 `misconception_codes`와는 별개 — 30-코드로 강제 매핑하지 않음).
    """
    text = _opt_str(misconception_text)
    if text is None:
        return []
    return [{"misconception": text}]


# ──────────────────────────────────────────────────────────────────────────
# 적재 레코드 (graph.json → backend Concept 컬럼 값)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class BackendConceptRecord:
    """backend `concept` 행으로 적재할 한 개념의 *런타임 식별* 값 — UC 브리지 키 + 유도 필드.

    `graph.json`의 `Concept.model_dump()`에서 backend 런타임 엔티티에 필요한 최소 식별만 추린
    값이다. **`description`·`formal_definition`·`intuitive_explanation` 슬롯이 *없다*** — graph
    부재·검수 책임 필드라 적재기가 채우지 않으므로 레코드에도 두지 않는다(redaction·구조적 차단).
    `code`가 UC(브리지 키)이고, 나머지는 backend Concept 컬럼에 직결/유도된다.
    """

    # 브리지 키·직결
    code: str  # = UC(concept_id) — UNIQUE 브리지 키
    name_ko: str
    # 유도
    level: ConceptLevel  # 세부개념 고정(NOT NULL 충족)
    subject: Subject | None  # domain 매핑(미대응 None)
    intrinsic_difficulty: float | None  # difficulty_tier 스케일
    common_misconceptions: list[dict[str, Any]] = field(default_factory=list)


def load_backend_concepts_from_graph_json(path: Path) -> list[BackendConceptRecord]:
    """슬1 산출 `graph.json` → backend `Concept` 적재 레코드 목록(UC 브리지·redaction 청결).

    `concepts` 배열의 각 항목에서 **`concept_id`(UC)·`name_ko`** 직결 + `domain`→subject·
    `difficulty_tier`→intrinsic_difficulty·`misconception_text`→common_misconceptions를 유도한다.
    `level`은 `세부개념` 고정(graph 노드는 전부 세부 개념). **`description`·`formal_definition`은
    읽지 않는다**(graph 부재이며, 오염돼 들어와도 레코드에 슬롯이 없어 차단).

    `name_ko`가 빈/None이면(이론상 graph.json은 name_ko 필수·min_length=1) 그 개념은 *건너뛴다*
    (NOT NULL 위반 방지·조용한 빈 적재 금지). `review_status` 무관 전량(403) — 게이팅은 조회 몫.

    Raises:
        FileNotFoundError: graph.json 부재.
        ValueError: concept_id 없는 항목(슬1 산출은 항상 UC를 갖는다 — 방어).
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[BackendConceptRecord] = []
    for record in payload.get("concepts", []):
        concept_id = str(record.get("concept_id", "")).strip()
        if not concept_id:
            raise ValueError(f"graph.json 개념에 concept_id가 없습니다: {record!r}")

        name_ko = _opt_str(record.get("name_ko"))
        if name_ko is None:
            # name_ko 누락(오염 입력) — NOT NULL 위반 대신 건너뛴다(정직). 정상 graph는 항상 보유.
            continue

        out.append(
            BackendConceptRecord(
                code=concept_id,
                name_ko=name_ko,
                level=_DEFAULT_LEVEL,
                subject=map_subject(_opt_str(record.get("domain"))),
                intrinsic_difficulty=scale_difficulty(_opt_int(record.get("difficulty_tier"))),
                common_misconceptions=_build_misconceptions(record.get("misconception_text")),
            )
        )
    return out


class BackendConceptStore:
    """개념그래프 → backend `concept` 런타임 ORM 적재기 — UC(`code`) 충돌 멱등 upsert(sync).

    슬117 `ConceptNodeStore`의 *런타임 엔티티* 짝이다(같은 sync 좌석·멱등 규약). `upsert`는
    `INSERT ... ON CONFLICT(code) DO UPDATE`로 멱등 적재한다 — 같은 UC 재적재는 기존 행을 갱신하고
    **UUID PK(concept_id)는 보존**한다(ON CONFLICT가 PK를 SET하지 않음 — L2 mastery·problem_concept
    FK 안정성에 결정적). 신규 행만 `gen_random_uuid()` server_default로 UUID 발급. sync 엔진은
    슬3 `_build_sync_engine`을 재사용해 지연 생성·캐시한다(신규 seam 0).

    redaction: INSERT 컬럼에 `description`·`formal_definition`·`intuitive_explanation`이 *없다*
    (레코드에 슬롯이 없어 구조적 차단 — 셋 다 NULL로 남아 검수 대기). ON CONFLICT SET에도 없으므로
    재적재가 검수 작성한 본문을 *덮어쓰지 않는다*(검수 결과 보존).
    """

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings

    @property
    def _resolved_settings(self) -> Settings:
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(슬117 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def upsert(self, record: BackendConceptRecord) -> None:
        """단일 개념을 backend `concept`에 upsert (멱등·UC `code` 충돌 갱신·UUID PK 보존).

        `INSERT ... ON CONFLICT(code) DO UPDATE` — 런타임 식별 필드(name_ko·level·subject·
        intrinsic_difficulty·common_misconceptions)를 갱신한다. **PK(concept_id)는 SET하지 않아
        보존**되고(재적재 시 기존 UUID 유지), 신규 행만 server_default로 발급한다.
        **description·formal_definition·intuitive_explanation은 INSERT/SET 컬럼에 없다**(redaction —
        레코드에 슬롯 부재·검수 본문 보존). `level`/`subject`는 enum 값(문자열)으로 바인딩한다
        (`use_enum_values` 직렬화 등가 — PG enum 컬럼에 한글 값).
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from whymath_backend.db.models.concept import Concept

        stmt = pg_insert(Concept).values(
            code=record.code,
            name_ko=record.name_ko,
            level=record.level.value,
            subject=record.subject.value if record.subject is not None else None,
            intrinsic_difficulty=record.intrinsic_difficulty,
            common_misconceptions=record.common_misconceptions,
        )
        # UC(code) 충돌 시 갱신 — concept_id(PK)·created_at·본문은 SET하지 않는다(보존·redaction).
        stmt = stmt.on_conflict_do_update(
            index_elements=[Concept.code],
            set_={
                "name_ko": stmt.excluded.name_ko,
                "level": stmt.excluded.level,
                "subject": stmt.excluded.subject,
                "intrinsic_difficulty": stmt.excluded.intrinsic_difficulty,
                "common_misconceptions": stmt.excluded.common_misconceptions,
            },
        )
        with self._get_engine().begin() as conn:
            conn.execute(stmt)


def populate_backend_concepts(
    records: Sequence[BackendConceptRecord],
    *,
    settings: Settings | None = None,
    store: BackendConceptStore | None = None,
) -> int:
    """개념그래프 개념을 backend `concept` 런타임 엔티티로 멱등 upsert 적재. 반환=적재 행 수.

    슬117 `populate_concept_nodes`의 *런타임 엔티티* 짝이다 — 각 레코드를 UC(`code`) 키로 upsert한다
    (403 전량·review_status 포함). 멱등(재실행 시 갱신·UUID 보존). store 미주입 시 슬3 sync 엔진
    재사용 `BackendConceptStore`를 만든다.
    """
    resolved = settings if settings is not None else get_settings()
    concept_store = store if store is not None else BackendConceptStore(settings=resolved)
    for record in records:
        concept_store.upsert(record)
    return len(records)


__all__ = [
    "BackendConceptRecord",
    "BackendConceptStore",
    "load_backend_concepts_from_graph_json",
    "map_subject",
    "populate_backend_concepts",
    "scale_difficulty",
]
