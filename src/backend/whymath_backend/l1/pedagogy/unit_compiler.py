"""소단원 DSL 컴파일러 v0.1 — `.unit.yaml` → `unit_spec`+`learning_objective` 행 + 발주서.

PED-01 후속 ②. `pack_loader`(교수법 팩 시더)의 *소단원* 짝이다. 사람이 저작한 소단원 DSL 한 편
(`schema/unit_dsl.py::UnitDSL`)을 받아:
  ① 형식 검증(Pydantic)  → ② 참조 검증(개념 노드·성취기준·교수법 팩 존재)  →
  ③ 목표별 전개(팩 슬롯·증거 병합)  → ④ `unit_spec`/`learning_objective` 행 dict + 발주서 산출.

산출물은 *행 dict*(ORM 직결)와 *발주서*(work order — 콘텐츠 생성 계층이 소비할 슬롯 주문서)다.
컴파일러는 콘텐츠 슬롯(`pedagogy_content_slot`) 행을 *만들지 않는다* — 발주서만 낸다(생성은 후속
계층 책임·역방향 의존 금지). YAML=소스, DB=산출물·단방향(ORM 모듈 docstring).

────────────────────────────────────────────────────────────────────────────
freeze discipline (v0.1 최소)
────────────────────────────────────────────────────────────────────────────
이차함수 소단원 1개를 E2E로 컴파일할 만큼만 만든다. 오개념 자동 채움·팩 페이딩 전개·게이트 승격
등은 후속으로 미룬다(각 지점에 deferred 주석). 참조 검증은 *전부* 모은 뒤 한 번에 실패한다
(첫 오류에서 멈추지 않음 — 저작자가 모든 누락을 한 번에 본다).

7계층: L1 데이터 기반의 소단원 명세 컴파일. 팩 로더(`_as_collection`)·sync 엔진 빌더를 재사용한다
(신규 seam 최소). `db`·`config`는 계층 밖 인프라라 import 가능(pack_loader 선례).

────────────────────────────────────────────────────────────────────────────
PED-16(2026-08-10) 판정 — unit_spec: 유지 + 컴파일 산출물↔DB 정합 감사 신설(제거 배제)
────────────────────────────────────────────────────────────────────────────
`unit_spec` 테이블 자체는 애플리케이션 코드에서 **한 번도 SELECT되지 않는다**(전수 grep 확인 —
`UnitSpec` 참조는 이 파일의 insert 구문·CLI(`compile.py`)·테스트뿐). `harness/objective_coverage.py`
는 이 테이블을 우회해 `.unit.yaml`을 직접 glob한다(그 모듈 자신이 "hermetic·DB 0"으로 명시하는
의도적 설계 — 커버리지 관측이 이 태스크 판정을 바꾸지 않는다).

**다만 pedagogy_pack(PED-16②)과 겉보기엔 같은 "reader 0" 패턴이지만 구조가 다르다**: `learning_
objective`가 복합 FK `(unit_id, unit_version)`로 `unit_spec`을 참조하고(ON DELETE CASCADE), 그
`learning_objective` 자체는 **live 테이블**이다 — `api/study.py`(`session.get(LearningObjective,
...)`)와 `l4/pedagogy/k_type_resolver.py`(`select(LearningObjective.k_type)...`)가 실제로 읽는다.
즉 `unit_spec`은 "아무도 안 읽는 고아 테이블"이 아니라 "그 자체는 안 읽히지만 live 테이블의 FK
부모"다 — 제거하려면 `learning_objective`의 FK·스키마·시더(`UnitSpecStore.seed`, 한 트랜잭션에서
unit_spec을 먼저 upsert해야 하는 순서 전제)까지 재설계해야 하는 훨씬 큰 리팩터가 된다.

**판정: 제거하지 않고 유지 + 정합 감사 신설**. blast radius 실측(읽은 파일):
  - `tests/backend/l1/test_unit_compiler.py::TestSeedSql`(2건)이 `UnitSpecStore.seed`가 만드는
    unit_spec/learning_objective 두 INSERT의 ON CONFLICT SQL을 직접 검증 — unit_spec 쪽만 걷어
    내려 해도 이 클래스의 절반이 무의미해진다(seed()가 두 테이블을 한 트랜잭션으로 묶어 쓰므로
    분리 자체가 리팩터).
  - `tests/backend/api/test_e2e_pedagogy_pilot_integration.py`가 `unit_spec.status`를 DRAFT→
    ACTIVE로 직접 갱신·재조회하는 릴리스 게이트 관통(step⑥)을 증명 대상으로 삼는다 — 테이블을
    없애면 이 파일럿 E2E 자체의 acceptance("5단계 전 구간 1회 관통")가 바뀐다.
  - `l1/pedagogy/compile.py` CLI는 `UnitSpecStore().seed(compiled)`로 `learning_objective`(live)
    를 채우는 **실 운영 진입점**이다 — unit_spec을 없애려면 이 CLI의 쓰기 순서 전제 자체를
    다시 설계해야 한다.
  이중 정본 위험(컴파일러 출력과 ORM 스키마가 조용히 갈라짐)은 제거 대신 **감시**로 상쇄한다 —
  `tests/backend/l1/test_unit_spec_yaml_db_parity.py`가 `compile_unit()`이 실제로 만드는 행 dict
  키 집합과 `UnitSpec`/`LearningObjective` ORM 컬럼셋을 상시 대조한다(하드코딩 스냅샷 없음 — 서로
  대조).
  재검토 조건: `learning_objective`의 FK 부모 축을 다른 방식(예: unit_id만·버전 없는 소단원 식별)
  으로 재설계하는 별도 스키마 변경이 착수되는 시점.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from whymath_backend.config import Settings, get_settings

# ORM 산출물 좌석(입력 DSL ≠ 산출물 ORM — 이름 구분).
from whymath_backend.db.models.pedagogy_dsl import LearningObjective, UnitSpec

# 슬3 sync 엔진 빌더·팩 입력 정규화 재사용(신규 seam 0 — pack_loader와 동일 규약).
from whymath_backend.l1.concept_graph.embedding import _build_sync_engine
from whymath_backend.l1.embedding_primitives import text_hash
from whymath_backend.l1.pedagogy.pack_loader import _as_collection
from whymath_backend.schema.pedagogy_pack import PedagogyPack, SlotSpec
from whymath_backend.schema.unit_dsl import UnitDSL

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


# 컴파일러 버전 — 산출물(unit_spec.compiler_ver)에 각인. 컴파일 규칙이 바뀌면 올린다.
DEFAULT_COMPILER_VER = "soraw-dsl/0.1"


# ──────────────────────────────────────────────────────────────────────────
# 산출물 컨테이너
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class CompiledUnit:
    """컴파일 산출물 — `unit_spec` 행 1개·`learning_objective` 행 n개·발주서(work order).

    `unit_spec_row`·`objective_rows`는 ORM 컬럼 키에 맞춘 행 dict라 시더(`UnitSpecStore`)가 그대로
    upsert한다. `work_order`는 콘텐츠 생성 계층이 소비할 *슬롯 주문서*(목표별 slot_manifest 평탄화한
    `{objective_id, slot_type, count}` 리스트)다 — 컴파일러는 슬롯 행을 만들지 않고 주문서만 낸다.
    """

    unit_spec_row: dict[str, Any]
    objective_rows: list[dict[str, Any]]
    work_order: list[dict[str, Any]]


class CompileError(ValueError):
    """참조 검증 실패 — 미존재 개념 노드·성취기준·교수법 팩을 *모두 모아* 한 번에 보고한다.

    형식 오류(Pydantic)와 달리 참조 오류는 코퍼스 대조 결과라, 첫 누락에서 멈추지 않고 전부 수집한
    뒤 하나의 메시지로 올린다(저작자가 모든 누락을 한 번에 고치도록).
    """


# ──────────────────────────────────────────────────────────────────────────
# 슬롯 병합 (팩 required_slots + 목표 slot_overrides)
# ──────────────────────────────────────────────────────────────────────────
def _merge_slots(
    base_slots: Sequence[SlotSpec],
    overrides: dict[str, int] | None,
) -> list[dict[str, Any]]:
    """팩 기본 슬롯에 목표 오버라이드를 얹어 slot_manifest(list[{type,count}])를 만든다.

    팩의 `required_slots`(SlotSpec 리스트)를 `[{type,count}]` dict 리스트로 시작한다. 각 오버라이드
    (슬롯 유형→개수)마다: 이미 있는 유형이면 *개수만 교체*하고, 없는 유형이면 *새 항목으로 append*
    한다(기존 항목 순서 보존·새 항목은 뒤에). 팩 원본은 건드리지 않는다(새 dict 생성).
    """
    merged: list[dict[str, Any]] = [{"type": s.type, "count": s.count} for s in base_slots]
    if not overrides:
        return merged
    index: dict[str, dict[str, Any]] = {d["type"]: d for d in merged}
    for slot_type, count in overrides.items():
        if slot_type in index:
            index[slot_type]["count"] = count  # 기존 슬롯 개수 교체
        else:
            new_slot: dict[str, Any] = {"type": slot_type, "count": count}
            merged.append(new_slot)  # 신규 슬롯 append(뒤에)
            index[slot_type] = new_slot
    return merged


# ──────────────────────────────────────────────────────────────────────────
# 핵심: compile_unit
# ──────────────────────────────────────────────────────────────────────────
def compile_unit(
    yaml_text: str,
    *,
    packs: dict[str, PedagogyPack],
    valid_atom_codes: set[str],
    statements_by_code: dict[str, str],
    compiler_ver: str = DEFAULT_COMPILER_VER,
) -> CompiledUnit:
    """소단원 DSL(YAML 문자열)을 컴파일해 `unit_spec`/`learning_objective` 행 + 발주서를 낸다.

    단계: ① `UnitDSL.model_validate`(형식 게이트) → ② 참조 검증(개념 노드·성취기준·팩 존재 — *전부*
    모아 실패) → ③ 목표별 전개(슬롯·증거 병합) → ④ unit_spec 행(yaml_sha256 각인·status='DRAFT') →
    ⑤ 발주서 평탄화. `packs`/`valid_atom_codes`/`statements_by_code`는 코퍼스에서 미리 로드해 주입
    (`load_packs`·`load_valid_atom_codes`·`load_statements_by_code` 헬퍼 — CLI가 결선).

    Raises:
        pydantic.ValidationError: DSL이 형식·불변식(extra=forbid·suffix 유일·부유형 구분)을 위반.
        CompileError: 미존재 개념 노드·성취기준·교수법 팩 참조(모두 모아 한 번에).
    """
    unit = UnitDSL.model_validate(yaml.safe_load(yaml_text))

    # ── ② 참조 검증(전부 모은 뒤 실패) ─────────────────────────────────
    errors: list[str] = []

    # 소단원 수준 개념 노드·성취기준 존재.
    for node in unit.concept_nodes:
        if node not in valid_atom_codes:
            errors.append(f"소단원 concept_node 미존재(원자 백본): {node}")
    for code in unit.standard_codes:
        if code not in statements_by_code:
            errors.append(f"소단원 standard_code 미존재(성취기준): {code}")

    # 목표 수준 개념 노드·성취기준·교수법 팩 존재.
    for obj in unit.objectives:
        for node in obj.concept_nodes:
            if node not in valid_atom_codes:
                errors.append(f"목표 {obj.suffix} concept_node 미존재(원자 백본): {node}")
        if obj.standard_code not in statements_by_code:
            errors.append(f"목표 {obj.suffix} standard_code 미존재(성취기준): {obj.standard_code}")
        # use_enum_values=True라 obj.k_type은 문자열 값("CONCEPT")·packs 키와 정합.
        if obj.k_type not in packs:
            errors.append(f"목표 {obj.suffix} k_type 교수법 팩 미존재: {obj.k_type}")
        if obj.k_type_secondary is not None and obj.k_type_secondary not in packs:
            errors.append(
                f"목표 {obj.suffix} k_type_secondary 교수법 팩 미존재: {obj.k_type_secondary}"
            )

    if errors:
        raise CompileError(
            f"소단원 '{unit.unit_id}' 컴파일 실패 — 미해결 참조 {len(errors)}건:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # ── ③ 목표별 전개 ────────────────────────────────────────────────
    objective_rows: list[dict[str, Any]] = []
    work_order: list[dict[str, Any]] = []
    for obj in unit.objectives:
        objective_id = f"{unit.unit_id}:{obj.suffix}"
        pack = packs[obj.k_type]
        slot_manifest = _merge_slots(pack.required_slots, obj.slot_overrides)
        # 팩 기본 증거에 목표 오버라이드를 얹는다(부분 덮어쓰기).
        exit_evidence = {**pack.default_evidence, **(obj.evidence_overrides or {})}

        objective_rows.append(
            {
                "id": objective_id,
                "unit_id": unit.unit_id,
                "unit_version": unit.unit_version,
                "statement": obj.statement,
                # 성취기준 코드→원문 해석(코드는 사실정보·원문은 NCIC 공공누리 자체 분해 전제).
                "achievement_std": statements_by_code[obj.standard_code],
                "source_verb": obj.source_verb,
                "k_type": obj.k_type,
                "k_type_secondary": obj.k_type_secondary,
                # AI 추정 정직 표기 — 사람 검수 전이라 기본 False(ORM server_default와 정합).
                "k_type_verified": False,
                "concept_nodes": obj.concept_nodes,
                # v0.1: 오개념 자동 채움 없음 — 미지정 시 None. (deferred) misconceptions_v1에서
                # 개념 노드 기반 top-3 자동 fetch는 후속 개선 항목.
                "misconception_ids": obj.misconception_ids,
                "slot_manifest": slot_manifest,
                "exit_evidence": exit_evidence,
                "phase_overrides": obj.phase_overrides,
            }
        )

        # ⑤ 발주서 — 목표 slot_manifest를 평탄화(콘텐츠 생성 계층이 소비할 슬롯 주문).
        for slot in slot_manifest:
            work_order.append(
                {
                    "objective_id": objective_id,
                    "slot_type": slot["type"],
                    "count": slot["count"],
                }
            )

    # ── ④ unit_spec 행(compiled_at은 server default라 생략) ─────────────
    unit_spec_row: dict[str, Any] = {
        "unit_id": unit.unit_id,
        "unit_version": unit.unit_version,
        "api_version": unit.api_version,
        "title": unit.title,
        "curriculum_rev": unit.curriculum_rev,
        "standard_codes": unit.standard_codes,
        "concept_nodes": unit.concept_nodes,
        # 소스 YAML 원문 해시 — 표현 변경(재컴파일 필요) 감지 신호(embedding_primitives.text_hash).
        "yaml_sha256": text_hash(yaml_text),
        "compiler_ver": compiler_ver,
        # M1 fail-closed — 게이트 통과 전에는 노출 안 됨(승격은 후속 게이트 책임).
        "status": "DRAFT",
    }

    return CompiledUnit(
        unit_spec_row=unit_spec_row,
        objective_rows=objective_rows,
        work_order=work_order,
    )


# ──────────────────────────────────────────────────────────────────────────
# 리졸버 헬퍼 (CLI·실사용 — 얇은 코퍼스 리더)
# ──────────────────────────────────────────────────────────────────────────
def load_valid_atom_codes(path: Path) -> set[str]:
    """원자 백본 그래프 JSON → 유효 개념 노드 code 집합(`concepts[*].code`)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {concept["code"] for concept in data["concepts"]}


def load_statements_by_code(path: Path) -> dict[str, str]:
    """성취기준 Collection JSON → {코드: 성취기준 원문}(`standards[*].code→statement`).

    성취기준 코드는 사실정보이고 원문(statement)은 NCIC 공공누리라 보유 허용된다(코드→원문 해석용).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return {std["code"]: std["statement"] for std in data["standards"]}


def load_packs(packs_dir: Path) -> dict[str, PedagogyPack]:
    """교수법 팩 디렉터리(팩당 1 YAML) → {k_type(문자열): PedagogyPack}.

    ⚠️ 이름 주의: `pack_loader.load_packs`(DB 시더·int 반환)와 *다른* 함수다 — 이쪽은 컴파일러가
    참조 검증·슬롯 병합에 쓸 팩을 메모리 dict로 읽는 순수 리더다(적재 부수효과 없음).
    `_as_collection`으로 디렉터리 정규화 후 schema 검증한다(use_enum_values=True라 k_type은 문자열).
    """
    raw_packs = _as_collection(packs_dir)
    packs = [PedagogyPack.model_validate(raw) for raw in raw_packs]
    return {pack.k_type: pack for pack in packs}


# ──────────────────────────────────────────────────────────────────────────
# 시더: UnitSpecStore (unit_spec → learning_objective, FK 순서·멱등 upsert)
# ──────────────────────────────────────────────────────────────────────────
class UnitSpecStore:
    """컴파일 산출물 → `unit_spec`+`learning_objective` 멱등 적재기(sync·`PedagogyPackStore` 미러).

    `seed`는 *한 트랜잭션*에서 unit_spec을 먼저 upsert(복합 PK `(unit_id,unit_version)` 충돌)한 뒤
    각 학습목표를 upsert(`id` 충돌)한다 — 복합 FK 순서상 소단원이 먼저 있어야 목표가 붙는다. PK는
    ON CONFLICT SET에서 제외해 보존한다(멱등). sync 엔진은 슬3 `_build_sync_engine`을 재사용한다.
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
        """설정 지연 해석 — 주입 우선, 없으면 캐시된 전역 Settings(pack_loader 패턴)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    def _get_engine(self) -> Engine:
        """sync 엔진 지연 해석 — 주입 우선, 없으면 슬3 빌더로 생성·캐시(신규 seam 0)."""
        if self._engine is None:
            self._engine = _build_sync_engine(self._resolved_settings)
        return self._engine

    def seed(self, compiled: CompiledUnit) -> tuple[int, int]:
        """컴파일 산출물을 unit_spec→learning_objective 순으로 멱등 upsert. 반환=(1, 목표 수).

        한 `engine.begin()` 안에서 소단원을 먼저(FK 순서), 그다음 목표들을 upsert한다. 각 행 dict의
        키만 바인딩하고 PK 컬럼은 SET에서 뺀다(unit_spec은 `unit_id,unit_version`·objective는
        `id`). JSONB 컬럼(slot_manifest·exit_evidence)은 list/dict 그대로 실린다.
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        unit_row = compiled.unit_spec_row
        unit_update_keys = set(unit_row) - {"unit_id", "unit_version"}

        with self._get_engine().begin() as conn:
            # ① 소단원 먼저(복합 FK 대상) — (unit_id, unit_version) 충돌 시 나머지 갱신.
            unit_stmt = pg_insert(UnitSpec).values(**unit_row)
            unit_stmt = unit_stmt.on_conflict_do_update(
                index_elements=[UnitSpec.unit_id, UnitSpec.unit_version],
                set_={key: unit_stmt.excluded[key] for key in unit_update_keys},
            )
            conn.execute(unit_stmt)

            # ② 학습목표들 — id 충돌 시 나머지 갱신(PK id는 SET에서 제외).
            for obj_row in compiled.objective_rows:
                obj_update_keys = set(obj_row) - {"id"}
                obj_stmt = pg_insert(LearningObjective).values(**obj_row)
                obj_stmt = obj_stmt.on_conflict_do_update(
                    index_elements=[LearningObjective.id],
                    set_={key: obj_stmt.excluded[key] for key in obj_update_keys},
                )
                conn.execute(obj_stmt)

        return (1, len(compiled.objective_rows))


__all__ = [
    "CompiledUnit",
    "CompileError",
    "compile_unit",
    "load_valid_atom_codes",
    "load_statements_by_code",
    "load_packs",
    "UnitSpecStore",
    "DEFAULT_COMPILER_VER",
]
