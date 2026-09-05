"""핵심 엔티티 19종 동결 — 정본 `docs/architecture/canonical_entity_model_v1.md`의 기계 집행.

이 파일이 **강제하는 것**(정본화≠집행 — CLAUDE.md):
  ① 78테이블 전수 귀속 — 새 테이블이 생기면 RED. 9월 스키마에 노드가 조용히 불어나는 것을 막는다.
  ② 좌석 실재 — 19종의 좌석 테이블이 사라지거나 개명되면 RED.
  ③ 좌석 부재 4종 — Subject·Hint·AssessmentResult·ContentVersion용 테이블이 생기면 RED.
  ④ 문서 정합 — 정본 문서가 78테이블을 전부 적지 않으면 RED(문서 드리프트 차단).

이 파일이 **강제하지 않는 것**(있는 척 금지):
  · 컬럼 수준 스키마(어떤 필드를 갖는지)는 각 모델의 기존 ORM 테스트 소관이다.
  · "이 테이블이 *올바른* 엔티티에 배정됐는가"는 사람 판단이다 — 기계는 배정의 *전수성*만 본다.
  · 코드 밖 저작 스키마(`schemas/v1.1/*.yaml`)와의 정합은 대조하지 않는다(정본 §7 드리프트 참조).
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import whymath_backend.db.models as models_pkg
from whymath_backend.db.base import Base

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CANON_DOC = _REPO_ROOT / "docs" / "architecture" / "canonical_entity_model_v1.md"
_CANON_HINT = f"정본 {_CANON_DOC.relative_to(_REPO_ROOT)} 를 갱신하고 이 상수를 함께 고쳐라."


def _load_all_models() -> None:
    """모든 모델 모듈을 적재해 `Base.metadata`를 완성한다(부분 적재면 측정이 새는다).

    `test_unit_structure_hypothesis_freeze.py` 선례 — `__init__` 수록 여부와 무관하게 pkgutil로
    전 모듈을 쓸어 담아, 새 모델 파일이 생겨도 측정 대상에 자동 포함되게 한다.
    """
    for module in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"whymath_backend.db.models.{module.name}")


# ──────────────────────────────────────────────────────────────────────────
# 동결 상수 — 정본 §1·§2 표와 1:1 (실측 2026-09-05·78테이블)
# ──────────────────────────────────────────────────────────────────────────

# 핵심 19종 → 좌석 테이블. 빈 tuple = **좌석 부재 동결**(정본 §3).
CANONICAL_ENTITY_SEATS: dict[str, tuple[str, ...]] = {
    "Subject": (),
    "Curriculum": ("curriculum_framework", "curriculum_version"),
    "CurriculumNode": (
        "curriculum_entry",
        "achievement_standard",
        "achievement_level_unit",
        "textbook_unit",
        "textbook_mapping",
    ),
    "LearningObjective": ("learning_objective", "unit_spec"),
    "Concept": ("concept", "concept_node", "atom_node"),
    "Skill": ("skill_node",),
    "Misconception": ("misconception_catalog",),
    "Problem": ("problem", "problem_step"),
    "Solution": ("solution_paths", "solution_nodes", "verified_solutions", "verified_lemmas"),
    "Hint": (),
    "Content": ("concept_content", "pedagogy_content_slot"),
    "Learner": ("user_profile",),
    "LearnerState": ("user_state_snapshot",),
    "MasteryState": ("concept_mastery_history", "skill_mastery_history", "ability_snapshot"),
    "Assessment": ("assessment",),
    "AssessmentResult": (),
    "LearningEvent": (
        "attempt_event",
        "evidence_event",
        "review_timer_event",
        "hint_usage",
        "answer_submission",
        "problem_attempt",
        "learning_session",
        "student_solution_step",
        "dead_end_log",
        "dialogue",
        "dialogue_turn",
    ),
    "PedagogyStrategy": ("strategy_node", "pedagogy_pack"),
    "ContentVersion": (),
}

# 핵심 19종에 배정하지 **않는** 테이블 → 배정 제외 사유(정본 §2-B).
# 사유를 값으로 강제해 "일단 여기에 던져 넣기"를 비싸게 만든다.
NON_CORE_TABLES: dict[str, str] = {
    # 임베딩 4종 — 개념/원자/오개념/문항 벡터. 노드 embedding 혼입 금지(플레이북 8대 원칙 ①).
    "atom_embedding": "임베딩(벡터) — 개념 노드에 혼입 금지",
    "concept_embedding": "임베딩(벡터) — 개념 노드에 혼입 금지",
    "misconception_embedding": "임베딩(벡터) — 오개념 노드에 혼입 금지",
    "problem_embedding": "임베딩(벡터) — 문항에 혼입 금지",
    # 관계·엣지 — 노드가 아니라 노드 사이. 관계 타입 폭발 방지 축.
    "concept_edge": "관계(엣지) — 개념↔개념",
    "concept_fusion": "관계(엣지) — 개념 융합",
    "concept_standard_link": "관계(엣지) — 개념↔성취기준",
    "problem_concept": "관계(엣지) — 문항↔개념",
    "problem_relation": "관계(엣지) — 문항↔문항",
    "misconception_relation": "관계(엣지) — 오개념↔오개념",
    "misconception_crosslink": "관계(엣지) — 오개념 kebab↔M-id 크로스워크",
    "evidence_links": "관계(엣지) — 증거↔대상",
    "derivation_edge": "관계(엣지) — 콘텐츠 파생 계보(권리 축)",
    # 부속 노드 — 핵심 19종의 하위 택소노미. 승격하려면 정본 갱신 경유.
    "formula_node": "부속 노드(공식 택소노미) — Concept 승격은 정본 갱신 경유",
    "problem_type_node": "부속 노드(문항유형 택소노미) — Problem 승격은 정본 갱신 경유",
    "atom_probe": "부속 노드(원자 프로브) — 원자 백본 진단 보조",
    # 렌더러 — 개념 노드에 renderer 혼입 금지(Concept Purity).
    "concept_visual_style": "렌더러(시각 스타일) — 개념 노드에 혼입 금지",
    "concept_visualization": "렌더러(시각화 인텐트) — 개념 노드에 혼입 금지",
    # 권리·출처 — 저작권 레일. 콘텐츠 본문이 아니라 그 출처·권리.
    "source_entity": "권리·출처(저작권 레일)",
    "rights_holder": "권리·출처(저작권 레일)",
    "rights_entity": "권리·출처(저작권 레일)",
    "content_source": "권리·출처(저작권 레일)",
    "content_rights": "권리·출처(저작권 레일)",
    "content_provenance": "권리·출처(생성 계보)",
    "generation_log": "권리·출처(LLM 생성 로그)",
    # 인증·법령 — 학습 도메인이 아니라 계정·동의.
    "refresh_token_session": "인증(세션 토큰)",
    "device_credential": "인증(기기 자격)",
    "parental_consent": "법령(법정대리인 동의) — 기계 대체 금지 축",
    # 감사·운영 — 횡단 관심사(7계층 밖).
    "deletion_audit": "감사(파기 이력)",
    "privacy_audit": "감사(개인정보 접근)",
    "defect_report": "운영(결함 신고)",
    # 집계 시계열 — 원시 이벤트의 파생. LearningEvent가 원천이고 이쪽은 롤업.
    "daily_learning_metrics": "집계(롤업) — LearningEvent 파생물",
    "problem_solve_time_distribution": "집계(롤업) — LearningEvent 파생물",
    "user_behavior_metrics": "집계(롤업) — LearningEvent 파생물",
    # 사용자 이력 — Learner의 변경 이력이지 상태(LearnerState)가 아니다.
    "user_track_history": "사용자 이력(트랙 변경) — LearnerState 아님",
    "user_persona_history": "사용자 이력(페르소나 변경) — LearnerState 아님",
    # 판정 보류 — 날조 금지(정본 §2-C). Misconception(카탈로그)도 LearningEvent(원시)도 아니다.
    "misconception_hypothesis": "판정 보류 — L2 오개념 추론 산출물. 카탈로그도 원시 이벤트도 아니다",
}

# 좌석 부재 4종이 테이블을 얻으려 할 때 쓸 법한 이름 — 하나라도 생기면 RED.
# 전수 귀속 검사(①)도 잡지만, 이쪽은 *어느 동결 결정을 깼는지*를 이름으로 지목한다.
RESERVED_ABSENT_TABLE_NAMES: dict[str, str] = {
    "subject": "Subject",
    "subjects": "Subject",
    "hint": "Hint",
    "hints": "Hint",
    "assessment_result": "AssessmentResult",
    "assessment_results": "AssessmentResult",
    "content_version": "ContentVersion",
    "content_versions": "ContentVersion",
    "entity_version": "ContentVersion",
}


def _seated_tables() -> set[str]:
    return {table for seats in CANONICAL_ENTITY_SEATS.values() for table in seats}


# ──────────────────────────────────────────────────────────────────────────
# ① 전수 귀속 — 새 테이블이 생기면 RED
# ──────────────────────────────────────────────────────────────────────────
def test_every_table_is_attributed() -> None:
    """실제 `Base.metadata` 전 테이블이 좌석 또는 핵심-외 중 정확히 한쪽에 배정돼 있다."""
    _load_all_models()
    actual = set(Base.metadata.tables)
    declared = _seated_tables() | set(NON_CORE_TABLES)

    unattributed = sorted(actual - declared)
    assert not unattributed, (
        f"귀속 없는 신규 테이블 {len(unattributed)}건: {unattributed}\n"
        f"9월 스키마 노드 폭발 방지 동결이다 — 자동 통과시키지 말고 {_CANON_HINT}"
    )

    vanished = sorted(declared - actual)
    assert (
        not vanished
    ), f"정본이 선언한 테이블이 코드에 없다 {len(vanished)}건: {vanished}\n{_CANON_HINT}"


def test_seat_and_non_core_do_not_overlap() -> None:
    """한 테이블이 좌석이면서 동시에 핵심-외일 수 없다(배정은 배타적)."""
    overlap = sorted(_seated_tables() & set(NON_CORE_TABLES))
    assert not overlap, f"이중 배정 {overlap} — 좌석과 핵심-외 중 하나만 골라라"


# ──────────────────────────────────────────────────────────────────────────
# ② 좌석 실재 — 좌석 삭제·개명이 무증상으로 지나가지 못한다
# ──────────────────────────────────────────────────────────────────────────
def test_canonical_entity_list_is_frozen_at_nineteen() -> None:
    """핵심 엔티티는 19종이다 — 늘리거나 줄이려면 정본 갱신을 경유한다."""
    assert (
        len(CANONICAL_ENTITY_SEATS) == 19
    ), f"핵심 엔티티가 {len(CANONICAL_ENTITY_SEATS)}종이 됐다 — {_CANON_HINT}"


def test_every_seat_table_exists_in_metadata() -> None:
    """19종의 좌석 테이블이 전부 실재한다(좌석 부재 4종은 검사 대상 아님)."""
    _load_all_models()
    actual = set(Base.metadata.tables)
    missing = {
        entity: sorted(set(seats) - actual)
        for entity, seats in CANONICAL_ENTITY_SEATS.items()
        if set(seats) - actual
    }
    assert not missing, f"좌석 테이블이 사라졌다(삭제·개명 추정): {missing}\n{_CANON_HINT}"


# ──────────────────────────────────────────────────────────────────────────
# ③ 좌석 부재 동결 — 4종이 몰래 좌석을 얻지 못한다
# ──────────────────────────────────────────────────────────────────────────
def test_absent_entities_have_no_seat_table() -> None:
    """정본 §3의 좌석 부재 4종에 예약된 테이블 이름이 등장하면 RED."""
    _load_all_models()
    actual = set(Base.metadata.tables)
    breached = {
        name: entity for name, entity in RESERVED_ABSENT_TABLE_NAMES.items() if name in actual
    }
    assert not breached, (
        f"좌석 부재 동결이 깨졌다: {breached}\n"
        f"부재는 실수가 아니라 결정이다(정본 §3) — 되돌리려면 {_CANON_HINT}"
    )


# ──────────────────────────────────────────────────────────────────────────
# ④ 문서 정합 — 정본이 78테이블을 전부 적고 있다
# ──────────────────────────────────────────────────────────────────────────
def test_canon_doc_lists_every_table() -> None:
    """정본 문서 본문이 전 테이블 이름을 담고 있다 — 표가 코드보다 뒤처지면 RED."""
    _load_all_models()
    assert _CANON_DOC.is_file(), f"정본 문서가 없다: {_CANON_DOC}"
    text = _CANON_DOC.read_text(encoding="utf-8")

    missing = sorted(name for name in Base.metadata.tables if f"`{name}`" not in text)
    assert not missing, (
        f"정본 §2 귀속표에서 빠진 테이블 {len(missing)}건: {missing}\n"
        "표는 백틱으로 감싼 테이블명을 포함해야 한다."
    )


def test_canon_doc_lists_every_canonical_entity() -> None:
    """정본 문서가 19종 이름을 전부 담고 있다."""
    assert _CANON_DOC.is_file(), f"정본 문서가 없다: {_CANON_DOC}"
    text = _CANON_DOC.read_text(encoding="utf-8")
    missing = sorted(e for e in CANONICAL_ENTITY_SEATS if f"**{e}**" not in text)
    assert not missing, f"정본에서 굵게 선언되지 않은 엔티티: {missing}"
