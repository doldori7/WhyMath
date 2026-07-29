"""Schema v1.1 TextbookMapping 3모델 단위 테스트 — 생성·extra forbid·use_enum_values·
isbn 형식 validator·🚨법적 게이팅 validator·자기부모 금지·단원명 길이 상한·required 누락.

설계 정본: `schemas/v1.1/textbook_mapping.schema.yaml`(1)TextbookMapping·2)TextbookUnit·
3)TextbookToneProfile·validation_invariants·license·헤더 🚨저작권 안전선). v1.0 도메인 밖,
v1.1에서 이식하는 마지막 자산(검정 교과서 *구조*를 개념·NCIC 성취기준에 잇는 매핑). 신규
ENUM `LegalReviewStatus`(3종, 영어)를 함께 검증한다.

이 모델은 *모델 내부로 강제 가능한* invariant만 validator로 구현한다(트리 사이클·고아 노드·
standard_codes/concept_ids 실재·Phase1 출판사 범위 가드는 cross-dataset/파이프라인 책임이라
모델·테스트 대상 아님). 따라서 검증 대상은: ① 3모델 happy-path roundtrip, ② extra forbid,
③ use_enum_values(legal_review_status가 'not_required' 문자열로 직렬화), ④ isbn 13자리 형식
validator(12/14/하이픈/문자 거부, 13숫자 통과), ⑤ 🚨법적 게이팅 validator(cleared 아니면
learning_objective_text 모두 None 강제), ⑥ 자기부모 금지(unit_id==parent_unit_id), ⑦ 단원명
201자 거부, ⑧ required 누락 거부, ⑨ LegalReviewStatus 3종 값.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from whymath_backend.schema.enums import LegalReviewStatus
from whymath_backend.schema.textbook_mapping import (
    TextbookMapping,
    TextbookToneProfile,
    TextbookUnit,
)

# ──────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — required를 채운 최소 유효 인자(테스트마다 override)
# ──────────────────────────────────────────────────────────────────────


def _minimal_tone(**overrides: object) -> TextbookToneProfile:
    """TextbookToneProfile required 2종(formality_level·sequencing_style)을 채운 톤 프로필."""
    base: dict[str, object] = {
        "formality_level": "높음",
        "sequencing_style": "개념선행형",
    }
    base.update(overrides)
    return TextbookToneProfile(**base)  # type: ignore[arg-type]


def _minimal_unit(**overrides: object) -> TextbookUnit:
    """TextbookUnit required 3종(unit_id·unit_number·unit_title)을 채운 단원 노드."""
    base: dict[str, object] = {
        "unit_id": "UNIT-1",
        "unit_number": "1",
        "unit_title": "이차함수의 그래프",
    }
    base.update(overrides)
    return TextbookUnit(**base)  # type: ignore[arg-type]


def _minimal_mapping_kwargs(**overrides: object) -> dict[str, object]:
    """TextbookMapping required(isbn·publisher·book_title·subject·grade·revision_year·
    unit_tree·tone_profile·source_urls·isolation_tag)를 채운 기본 인자.
    legal_review_status는 default(not_required)라 미지정.
    """
    base: dict[str, object] = {
        "isbn": "9788900000001",
        "publisher": "미래엔",
        "book_title": "고등학교 수학",
        "subject": "공통수학1",
        "grade": 10,
        "revision_year": 2025,
        "unit_tree": [_minimal_unit()],
        "tone_profile": _minimal_tone(),
        "source_urls": ["https://text.moe.go.kr/"],
        "isolation_tag": "미래엔::9788900000001",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────
# 신규 ENUM — LegalReviewStatus 값 검증(YAML legal_review_status.enum 정본)
# ──────────────────────────────────────────────────────────────────────
class TestLegalReviewStatusEnum:
    def test_values_three_english(self) -> None:
        """LegalReviewStatus — YAML enum 영어 3종(not_required/pending/cleared)."""
        assert LegalReviewStatus.not_required.value == "not_required"
        assert LegalReviewStatus.pending.value == "pending"
        assert LegalReviewStatus.cleared.value == "cleared"
        assert {e.value for e in LegalReviewStatus} == {
            "not_required",
            "pending",
            "cleared",
        }

    def test_str_enum_equality(self) -> None:
        """str-Enum — 문자열 값과 동등 비교(라우터·필터 안정성)."""
        assert LegalReviewStatus.cleared == "cleared"
        assert LegalReviewStatus("not_required") is LegalReviewStatus.not_required

    def test_distinct_from_review_status(self) -> None:
        """⚠️ 기존 ReviewStatus(pending/approved/rejected)와 *다른* enum이다."""
        # LegalReviewStatus에는 approved/rejected가 없다
        assert {e.value for e in LegalReviewStatus} != {"pending", "approved", "rejected"}


# ──────────────────────────────────────────────────────────────────────
# TextbookToneProfile — happy-path·required·extra forbid
# ──────────────────────────────────────────────────────────────────────
class TestTextbookToneProfile:
    def test_full_roundtrip(self) -> None:
        """전 필드 채움 — formality_level·notation_preferences·sequencing_style 보존."""
        t = TextbookToneProfile(
            formality_level="높음",
            notation_preferences=["∫ 표기", "분수 우선"],
            sequencing_style="개념선행형",
        )
        assert t.formality_level == "높음"
        assert t.notation_preferences == ["∫ 표기", "분수 우선"]
        assert t.sequencing_style == "개념선행형"

    def test_notation_preferences_default_empty(self) -> None:
        """notation_preferences는 default_factory=list — 미지정 시 빈 리스트."""
        t = _minimal_tone()
        assert t.notation_preferences == []

    @pytest.mark.parametrize("missing", ["formality_level", "sequencing_style"])
    def test_required_missing_rejected(self, missing: str) -> None:
        """required 2종(formality_level·sequencing_style) 누락 시 거부."""
        kwargs: dict[str, object] = {
            "formality_level": "높음",
            "sequencing_style": "개념선행형",
        }
        del kwargs[missing]
        with pytest.raises(ValidationError):
            TextbookToneProfile(**kwargs)  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            TextbookToneProfile(
                formality_level="높음",
                sequencing_style="개념선행형",
                bogus="x",  # type: ignore[call-arg]
            )


# ──────────────────────────────────────────────────────────────────────
# TextbookUnit — happy-path·required·자기부모·단원명 길이·extra forbid
# ──────────────────────────────────────────────────────────────────────
class TestTextbookUnit:
    def test_full_roundtrip(self) -> None:
        """전 필드 채움(learning_objective_text는 단원 단독이라 None 아님 허용 — 게이팅은
        TextbookMapping 책임)."""
        u = TextbookUnit(
            unit_id="UNIT-1-2",
            parent_unit_id="UNIT-1",
            unit_number="1-2",
            unit_title="이차함수의 그래프",
            page_range="12-35",
            standard_codes=["[10공수1-02-01]"],
            concept_ids=["CONCEPT-QUAD-GRAPH"],
            learning_objective_text="이차함수의 그래프를 그릴 수 있다",
        )
        assert u.unit_id == "UNIT-1-2"
        assert u.parent_unit_id == "UNIT-1"
        assert u.unit_number == "1-2"
        assert u.unit_title == "이차함수의 그래프"
        assert u.page_range == "12-35"
        assert u.standard_codes == ["[10공수1-02-01]"]
        assert u.concept_ids == ["CONCEPT-QUAD-GRAPH"]
        assert u.learning_objective_text == "이차함수의 그래프를 그릴 수 있다"

    def test_minimal_defaults(self) -> None:
        """required 3종만 — parent None·page_range None·list 빈·learning_objective None."""
        u = _minimal_unit()
        assert u.parent_unit_id is None
        assert u.page_range is None
        assert u.standard_codes == []
        assert u.concept_ids == []
        assert u.learning_objective_text is None

    def test_root_unit_parent_none_ok(self) -> None:
        """대단원은 parent_unit_id=None — 자기부모 검사 비대상."""
        u = _minimal_unit(unit_id="UNIT-1", parent_unit_id=None)
        assert u.parent_unit_id is None

    def test_self_parent_rejected(self) -> None:
        """🔁 자기 자신을 부모로 둘 수 없다 — unit_id == parent_unit_id 거부."""
        with pytest.raises(ValidationError, match="parent_unit_id"):
            _minimal_unit(unit_id="UNIT-X", parent_unit_id="UNIT-X")

    def test_distinct_parent_ok(self) -> None:
        """parent_unit_id ≠ unit_id면 통과."""
        u = _minimal_unit(unit_id="UNIT-1-2", parent_unit_id="UNIT-1")
        assert u.unit_id != u.parent_unit_id

    def test_unit_title_max_length_200_ok(self) -> None:
        """unit_title 200자 경계 — 통과."""
        u = _minimal_unit(unit_title="가" * 200)
        assert len(u.unit_title) == 200

    def test_unit_title_201_rejected(self) -> None:
        """unit_title 201자 거부(max_length=200 — 본문 혼입 신호 모델 레벨 가드)."""
        with pytest.raises(ValidationError):
            _minimal_unit(unit_title="가" * 201)

    @pytest.mark.parametrize("missing", ["unit_id", "unit_number", "unit_title"])
    def test_required_missing_rejected(self, missing: str) -> None:
        """required 3종(unit_id·unit_number·unit_title) 누락 시 거부."""
        kwargs: dict[str, object] = {
            "unit_id": "UNIT-1",
            "unit_number": "1",
            "unit_title": "이차함수의 그래프",
        }
        del kwargs[missing]
        with pytest.raises(ValidationError):
            TextbookUnit(**kwargs)  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            _minimal_unit(bogus="x")


# ──────────────────────────────────────────────────────────────────────
# TextbookMapping — happy-path roundtrip
# ──────────────────────────────────────────────────────────────────────
class TestTextbookMappingHappyPath:
    def test_minimal_required_only(self) -> None:
        """required 10종만으로 생성 — authors 빈 리스트·curriculum_revision 기본·
        legal_review_status 기본 not_required."""
        m = TextbookMapping(**_minimal_mapping_kwargs())  # type: ignore[arg-type]
        assert m.isbn == "9788900000001"
        assert m.publisher == "미래엔"
        assert m.book_title == "고등학교 수학"
        assert m.subject == "공통수학1"
        assert m.grade == 10
        assert m.revision_year == 2025
        assert len(m.unit_tree) == 1
        assert isinstance(m.tone_profile, TextbookToneProfile)
        assert m.source_urls == ["https://text.moe.go.kr/"]
        assert m.isolation_tag == "미래엔::9788900000001"
        # 기본값
        assert m.authors == []
        assert m.curriculum_revision == "2022 개정"
        assert m.legal_review_status == LegalReviewStatus.not_required

    def test_full_fields_roundtrip(self) -> None:
        """전 필드 채움 — 서지·단원 트리·톤 프로필·출처·격리·검토 상태 보존(cleared이므로
        learning_objective_text 활성화)."""
        m = TextbookMapping(
            isbn="9791160000007",
            publisher="천재교육",
            book_title="고등학교 공통수학1",
            authors=["저자A", "저자B"],
            subject="공통수학1",
            grade=10,
            revision_year=2025,
            curriculum_revision="2022 개정",
            unit_tree=[
                _minimal_unit(unit_id="U1", parent_unit_id=None, unit_number="1"),
                _minimal_unit(
                    unit_id="U1-1",
                    parent_unit_id="U1",
                    unit_number="1-1",
                    unit_title="다항식의 연산",
                    page_range="8-20",
                    standard_codes=["[10공수1-01-01]"],
                    concept_ids=["CONCEPT-POLY-OP"],
                    learning_objective_text="다항식의 사칙연산을 할 수 있다",
                ),
            ],
            tone_profile=_minimal_tone(
                formality_level="중간",
                notation_preferences=["가로셈 우선"],
                sequencing_style="문제선행형",
            ),
            source_urls=[
                "https://text.moe.go.kr/",
                "https://www.nl.go.kr/",
            ],
            isolation_tag="천재교육::9791160000007",
            legal_review_status=LegalReviewStatus.cleared,
        )
        assert m.isbn == "9791160000007"
        assert m.publisher == "천재교육"
        assert m.authors == ["저자A", "저자B"]
        assert len(m.unit_tree) == 2
        assert m.unit_tree[1].learning_objective_text == "다항식의 사칙연산을 할 수 있다"
        assert m.tone_profile.sequencing_style == "문제선행형"
        assert m.source_urls == [
            "https://text.moe.go.kr/",
            "https://www.nl.go.kr/",
        ]
        assert m.legal_review_status == LegalReviewStatus.cleared

    def test_grade_middle_school_ok(self) -> None:
        """grade는 중1~고3 포괄(ge=1 le=12) — 중1(7)도 통과."""
        m = TextbookMapping(**_minimal_mapping_kwargs(grade=7))  # type: ignore[arg-type]
        assert m.grade == 7

    @pytest.mark.parametrize("bad_grade", [0, 13])
    def test_grade_out_of_range_rejected(self, bad_grade: int) -> None:
        """grade 범위 밖(0·13) 거부(ge=1 le=12)."""
        with pytest.raises(ValidationError):
            TextbookMapping(**_minimal_mapping_kwargs(grade=bad_grade))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# use_enum_values·str_strip_whitespace·extra forbid
# ──────────────────────────────────────────────────────────────────────
class TestTextbookMappingSerialization:
    def test_legal_review_status_serializes_value(self) -> None:
        """⚠️ use_enum_values → legal_review_status는 'not_required' 문자열로 직렬화."""
        m = TextbookMapping(**_minimal_mapping_kwargs())  # type: ignore[arg-type]
        dumped = m.model_dump()
        assert dumped["legal_review_status"] == "not_required"

    def test_legal_review_status_cleared_serializes_value(self) -> None:
        """use_enum_values → cleared도 'cleared' 문자열로 직렬화."""
        m = TextbookMapping(
            **_minimal_mapping_kwargs(legal_review_status=LegalReviewStatus.cleared)  # type: ignore[arg-type]
        )
        assert m.model_dump()["legal_review_status"] == "cleared"

    def test_str_strip_whitespace(self) -> None:
        """str_strip_whitespace → 문자열 필드 양끝 공백 제거(ConfigDict 공통)."""
        m = TextbookMapping(
            **_minimal_mapping_kwargs(book_title="  고등학교 수학  ")  # type: ignore[arg-type]
        )
        assert m.book_title == "고등학교 수학"

    def test_extra_forbidden(self) -> None:
        """extra='forbid' — 알 수 없는 필드 거부."""
        with pytest.raises(ValidationError):
            TextbookMapping(**_minimal_mapping_kwargs(bogus="x"))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# isbn 13자리 형식 validator
# ──────────────────────────────────────────────────────────────────────
class TestTextbookMappingIsbnFormat:
    def test_13_digits_ok(self) -> None:
        """정확히 숫자 13자리 → 통과."""
        m = TextbookMapping(**_minimal_mapping_kwargs(isbn="9788900000001"))  # type: ignore[arg-type]
        assert m.isbn == "9788900000001"

    @pytest.mark.parametrize(
        "bad_isbn",
        [
            "978890000000",  # 12자리
            "97889000000012",  # 14자리
            "978-89-0000-000-1",  # 하이픈 포함
            "97889000000X1",  # 문자 포함(13자 길이지만 숫자 아님)
            "",  # 빈 문자열
        ],
    )
    def test_invalid_isbn_rejected(self, bad_isbn: str) -> None:
        """12자리·14자리·하이픈포함·문자포함·빈값 → 거부(^\\d{13}$ 아님)."""
        with pytest.raises(ValidationError, match="isbn"):
            TextbookMapping(**_minimal_mapping_kwargs(isbn=bad_isbn))  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
# 🚨 법적 게이팅 validator — cleared 아니면 learning_objective_text 모두 None
# (이 슬라이스에서 가장 중요한 invariant)
# ──────────────────────────────────────────────────────────────────────
class TestLearningObjectiveGating:
    def test_not_required_all_none_ok(self) -> None:
        """not_required + 모든 단원 learning_objective_text=None → 통과."""
        m = TextbookMapping(
            **_minimal_mapping_kwargs(
                legal_review_status=LegalReviewStatus.not_required,
                unit_tree=[
                    _minimal_unit(unit_id="U1", learning_objective_text=None),
                    _minimal_unit(unit_id="U2", learning_objective_text=None),
                ],
            )  # type: ignore[arg-type]
        )
        assert all(u.learning_objective_text is None for u in m.unit_tree)

    def test_not_required_with_objective_rejected(self) -> None:
        """🚨 not_required인데 어떤 단원에 learning_objective_text 비-null → 거부."""
        with pytest.raises(ValidationError, match="learning_objective_text"):
            TextbookMapping(
                **_minimal_mapping_kwargs(
                    legal_review_status=LegalReviewStatus.not_required,
                    unit_tree=[
                        _minimal_unit(unit_id="U1", learning_objective_text=None),
                        _minimal_unit(
                            unit_id="U2",
                            learning_objective_text="학습목표 문장(교과서 저작물)",
                        ),
                    ],
                )  # type: ignore[arg-type]
            )

    def test_pending_with_objective_rejected(self) -> None:
        """🚨 pending(검토 진행 중)인데 비-null → 여전히 거부(cleared 전까지 null 고정)."""
        with pytest.raises(ValidationError, match="learning_objective_text"):
            TextbookMapping(
                **_minimal_mapping_kwargs(
                    legal_review_status=LegalReviewStatus.pending,
                    unit_tree=[
                        _minimal_unit(
                            unit_id="U1",
                            learning_objective_text="학습목표 문장",
                        ),
                    ],
                )  # type: ignore[arg-type]
            )

    def test_pending_all_none_ok(self) -> None:
        """pending + 모든 단원 None → 통과(검토 중에도 null이면 됨)."""
        m = TextbookMapping(
            **_minimal_mapping_kwargs(
                legal_review_status=LegalReviewStatus.pending,
                unit_tree=[_minimal_unit(unit_id="U1", learning_objective_text=None)],
            )  # type: ignore[arg-type]
        )
        assert m.legal_review_status == LegalReviewStatus.pending

    def test_cleared_with_objective_ok(self) -> None:
        """cleared(검토 통과)면 learning_objective_text 비-null 허용 → 통과."""
        m = TextbookMapping(
            **_minimal_mapping_kwargs(
                legal_review_status=LegalReviewStatus.cleared,
                unit_tree=[
                    _minimal_unit(
                        unit_id="U1",
                        learning_objective_text="이차함수의 그래프를 그릴 수 있다",
                    ),
                ],
            )  # type: ignore[arg-type]
        )
        assert m.unit_tree[0].learning_objective_text == "이차함수의 그래프를 그릴 수 있다"

    def test_cleared_all_none_ok(self) -> None:
        """cleared인데 모두 None이어도 통과(활성화 *가능*일 뿐 강제 아님)."""
        m = TextbookMapping(
            **_minimal_mapping_kwargs(
                legal_review_status=LegalReviewStatus.cleared,
                unit_tree=[_minimal_unit(unit_id="U1", learning_objective_text=None)],
            )  # type: ignore[arg-type]
        )
        assert m.unit_tree[0].learning_objective_text is None

    def test_string_cleared_with_objective_ok(self) -> None:
        """use_enum_values 대응 — 문자열 'cleared'로 줘도 게이팅 정규화 동작(비-null 허용)."""
        m = TextbookMapping(
            **_minimal_mapping_kwargs(
                legal_review_status="cleared",
                unit_tree=[
                    _minimal_unit(
                        unit_id="U1",
                        learning_objective_text="학습목표 문장",
                    ),
                ],
            )  # type: ignore[arg-type]
        )
        assert m.unit_tree[0].learning_objective_text == "학습목표 문장"

    def test_string_not_required_with_objective_rejected(self) -> None:
        """use_enum_values 대응 — 문자열 'not_required' + 비-null → 거부(정규화 비교)."""
        with pytest.raises(ValidationError, match="learning_objective_text"):
            TextbookMapping(
                **_minimal_mapping_kwargs(
                    legal_review_status="not_required",
                    unit_tree=[
                        _minimal_unit(
                            unit_id="U1",
                            learning_objective_text="학습목표 문장",
                        ),
                    ],
                )  # type: ignore[arg-type]
            )


# ──────────────────────────────────────────────────────────────────────
# required 누락·min_length·enum 거부
# ──────────────────────────────────────────────────────────────────────
class TestTextbookMappingRequired:
    @pytest.mark.parametrize(
        "missing",
        [
            "isbn",
            "publisher",
            "book_title",
            "subject",
            "grade",
            "revision_year",
            "unit_tree",
            "tone_profile",
            "source_urls",
            "isolation_tag",
        ],
    )
    def test_required_field_missing_rejected(self, missing: str) -> None:
        """required 10종 각각 누락 시 거부(legal_review_status는 default라 제외)."""
        kwargs = _minimal_mapping_kwargs()
        del kwargs[missing]
        with pytest.raises(ValidationError):
            TextbookMapping(**kwargs)  # type: ignore[arg-type]

    def test_empty_unit_tree_rejected(self) -> None:
        """unit_tree min_length=1 — 빈 리스트 거부."""
        with pytest.raises(ValidationError):
            TextbookMapping(**_minimal_mapping_kwargs(unit_tree=[]))  # type: ignore[arg-type]

    def test_empty_source_urls_rejected(self) -> None:
        """source_urls min_length=1 — 빈 리스트 거부."""
        with pytest.raises(ValidationError):
            TextbookMapping(**_minimal_mapping_kwargs(source_urls=[]))  # type: ignore[arg-type]

    def test_invalid_legal_review_status_rejected(self) -> None:
        """legal_review_status에 정의되지 않은 값 거부(3종 enum 밖)."""
        with pytest.raises(ValidationError):
            TextbookMapping(
                **_minimal_mapping_kwargs(legal_review_status="approved")  # type: ignore[arg-type]
            )
