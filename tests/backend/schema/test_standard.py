"""Schema P1-2 AchievementStandard·ConceptStandardLink 모델 단위 테스트.

설계 정본: `whymath_backend/schema/standard.py`(data_pipeline NCIC 모델의 백엔드 계약 이식).
이 백엔드 계약은 NCIC가 이미 검증·정규화한 값을 받는 전제라 형식 정규식(norm_id/official_code)·
cross-dataset 정합은 *파이프라인 책임*이고 모델·테스트 대상이 아니다(curriculum_entry 방침 동형).

검증 대상: ① required 누락 거부, ② extra forbid, ③ link_type Literal 닫힘(미허용 값 거부),
④ parent_codes 기본 빈 리스트·선택 필드 None 기본, ⑤ official_code 필드명(코퍼스 `code` 아님)
존재 확인, ⑥ roundtrip(model_dump → 재생성).
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from whymath_backend.schema.standard import AchievementStandard, ConceptStandardLink


# ──────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — required를 채운 최소 유효 인자(테스트마다 override)
# ──────────────────────────────────────────────────────────────────────
def _standard_kwargs(**overrides: object) -> dict[str, object]:
    """AchievementStandard required(식별 3 + 분류 4 + statement + source_url)를 채운 기본 인자."""
    base: dict[str, object] = {
        "norm_id": "2022_12미적1_01_01",
        "official_code": "[12미적1-01-01]",
        "curriculum_revision": "2022 개정",
        "grade_band": "고등학교",
        "school_type": "고등학교",
        "subject": "미적분Ⅰ",
        "domain": "변화와 관계",
        "statement": "함수의 극한의 뜻을 알고 그 성질을 이해한다.",
        "source_url": "https://ncic.example/2022/12미적1",
    }
    base.update(overrides)
    return base


def _link_kwargs(**overrides: object) -> dict[str, object]:
    """ConceptStandardLink required(concept_code + norm_id + link_type)를 채운 기본 인자."""
    base: dict[str, object] = {
        "concept_code": "UC-CAL-LIM-DEF",
        "norm_id": "2022_12미적1_01_01",
        "link_type": "직접",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────
# AchievementStandard
# ──────────────────────────────────────────────────────────────────────
class TestAchievementStandard:
    def test_minimal_valid(self) -> None:
        """required만으로 생성되며 선택 필드는 기본값(None·빈 리스트)을 갖는다."""
        s = AchievementStandard(**_standard_kwargs())  # type: ignore[arg-type]
        assert s.norm_id == "2022_12미적1_01_01"
        assert s.official_code == "[12미적1-01-01]"
        assert s.parent_codes == []  # default_factory=list
        assert s.sub_domain is None
        assert s.commentary is None
        assert s.big_idea is None
        assert s.effective_from is None
        assert s.source_document is None

    def test_uses_official_code_field_not_code(self) -> None:
        """백엔드 계약은 `official_code` 필드를 쓴다(코퍼스의 `code` 키 아님 — 로더가 매핑)."""
        fields = set(AchievementStandard.model_fields)
        assert "official_code" in fields
        assert "code" not in fields

    @pytest.mark.parametrize(
        "missing",
        [
            "norm_id",
            "official_code",
            "curriculum_revision",
            "grade_band",
            "school_type",
            "subject",
            "domain",
            "statement",
            "source_url",
        ],
    )
    def test_required_missing_rejected(self, missing: str) -> None:
        """required 필드 누락은 ValidationError."""
        kwargs = _standard_kwargs()
        kwargs.pop(missing)
        with pytest.raises(ValidationError):
            AchievementStandard(**kwargs)  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """정의되지 않은 추가 필드는 거부된다(extra='forbid')."""
        with pytest.raises(ValidationError):
            AchievementStandard(**_standard_kwargs(unexpected="x"))  # type: ignore[arg-type]

    def test_roundtrip_full(self) -> None:
        """전 필드 채운 인스턴스가 model_dump → 재생성을 왕복한다."""
        s = AchievementStandard(
            **_standard_kwargs(
                sub_domain="극한",
                commentary="좌극한·우극한을 함께 다룬다.",
                big_idea="변화의 누적과 순간",
                effective_from=date(2025, 3, 1),
                parent_codes=["[9수01-01]"],
                source_document="2022-33호.pdf",
            )  # type: ignore[arg-type]
        )
        again = AchievementStandard(**s.model_dump())
        assert again == s
        assert again.effective_from == date(2025, 3, 1)
        assert again.parent_codes == ["[9수01-01]"]


# ──────────────────────────────────────────────────────────────────────
# ConceptStandardLink
# ──────────────────────────────────────────────────────────────────────
class TestConceptStandardLink:
    def test_minimal_valid(self) -> None:
        """required만으로 생성되며 note는 기본 None."""
        link = ConceptStandardLink(**_link_kwargs())  # type: ignore[arg-type]
        assert link.concept_code == "UC-CAL-LIM-DEF"
        assert link.norm_id == "2022_12미적1_01_01"
        assert link.link_type == "직접"
        assert link.note is None

    @pytest.mark.parametrize("link_type", ["직접", "재매핑", "준용"])
    def test_link_type_accepts_canonical_values(self, link_type: str) -> None:
        """한글 정본 3종은 허용된다."""
        link = ConceptStandardLink(**_link_kwargs(link_type=link_type))  # type: ignore[arg-type]
        assert link.link_type == link_type

    @pytest.mark.parametrize("bad", ["direct", "DIRECT", "연결", "재 매핑", ""])
    def test_link_type_rejects_non_canonical(self, bad: str) -> None:
        """Literal 밖의 link_type 값은 거부된다(닫힌 어휘)."""
        with pytest.raises(ValidationError):
            ConceptStandardLink(**_link_kwargs(link_type=bad))  # type: ignore[arg-type]

    def test_no_link_id_field(self) -> None:
        """schema에는 link_id가 없다(연결 의미키는 (concept_code, norm_id, link_type) — ORM 전용 PK)."""
        assert "link_id" not in set(ConceptStandardLink.model_fields)

    @pytest.mark.parametrize("missing", ["concept_code", "norm_id", "link_type"])
    def test_required_missing_rejected(self, missing: str) -> None:
        """required 필드 누락은 ValidationError."""
        kwargs = _link_kwargs()
        kwargs.pop(missing)
        with pytest.raises(ValidationError):
            ConceptStandardLink(**kwargs)  # type: ignore[arg-type]

    def test_extra_forbidden(self) -> None:
        """정의되지 않은 추가 필드는 거부된다(extra='forbid')."""
        with pytest.raises(ValidationError):
            ConceptStandardLink(**_link_kwargs(unexpected="x"))  # type: ignore[arg-type]

    def test_roundtrip(self) -> None:
        """note 포함 인스턴스가 model_dump → 재생성을 왕복한다."""
        link = ConceptStandardLink(**_link_kwargs(note="2022 개정 신설에 직접 대응"))  # type: ignore[arg-type]
        again = ConceptStandardLink(**link.model_dump())
        assert again == link
