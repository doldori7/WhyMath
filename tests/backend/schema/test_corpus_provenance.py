"""`CorpusProvenanceSidecar` 계약 단위테스트 — ARCH-20.

검증 대상: ① `pool` 필수(누락 거부) ② `pool` 폐쇄 3종 밖 값 거부 ③ 서지 정보(`source_citation`/
`license_notice`) 둘 다 비어야 거부(둘 중 하나만 있으면 통과 — 대칭 검증) ④ 공백 문자열은
"있음"으로 치지 않음(strip 후 검사) ⑤ `extra="allow"` — 코퍼스별 자유 필드가 거부되지 않고
round-trip 보존됨(19개 실 사이드카의 이질적 키 집합을 갈아엎지 않는다는 설계 전제의 실증).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.schema.corpus_provenance import CorpusProvenanceSidecar
from whymath_backend.schema.enums import ContentPool


class TestPoolRequired:
    def test_missing_pool_rejected(self) -> None:
        with pytest.raises(ValidationError, match="pool"):
            CorpusProvenanceSidecar.model_validate({"source_citation": "출처"})

    def test_invalid_pool_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CorpusProvenanceSidecar.model_validate(
                {"pool": "not-a-real-pool", "source_citation": "출처"}
            )

    @pytest.mark.parametrize(
        "value",
        ["whymath-original", "external-sharealike", "external-licensed"],
    )
    def test_all_three_pool_values_accepted(self, value: str) -> None:
        model = CorpusProvenanceSidecar.model_validate(
            {"pool": value, "source_citation": "출처"}
        )
        assert model.pool == ContentPool(value)


class TestBibliographicMinimum:
    def test_both_missing_rejected(self) -> None:
        with pytest.raises(ValidationError, match="source_citation"):
            CorpusProvenanceSidecar.model_validate({"pool": "whymath-original"})

    def test_only_source_citation_accepted(self) -> None:
        model = CorpusProvenanceSidecar.model_validate(
            {"pool": "whymath-original", "source_citation": "출처"}
        )
        assert model.license_notice is None

    def test_only_license_notice_accepted(self) -> None:
        model = CorpusProvenanceSidecar.model_validate(
            {"pool": "whymath-original", "license_notice": "라이선스 고지"}
        )
        assert model.source_citation is None

    def test_whitespace_only_not_counted_as_present(self) -> None:
        """공백뿐인 문자열은 '있음'이 아니다 — 침묵 실패 방지(빈 값 위장 차단)."""
        with pytest.raises(ValidationError, match="source_citation"):
            CorpusProvenanceSidecar.model_validate(
                {"pool": "whymath-original", "source_citation": "   ", "license_notice": "\t"}
            )


class TestExtraFieldsAllowed:
    def test_free_form_fields_round_trip(self) -> None:
        """19개 실 사이드카의 이질적 키(corpus_name·counts·copyright_rail 등)가 거부되지
        않고 그대로 보존된다 — extra='forbid'인 row-level ContentProvenance와 의도적으로
        다른 정책(모듈 docstring 근거)."""
        payload = {
            "pool": "whymath-original",
            "license_notice": "y",
            "corpus_name": "foo",
            "record_count": 42,
            "counts": {"a": 1, "b": 2},
            "copyright_rail": ["x", "y"],
        }
        model = CorpusProvenanceSidecar.model_validate(payload)
        dumped = model.model_dump(exclude_none=True)
        for key, value in payload.items():
            assert dumped[key] == value
