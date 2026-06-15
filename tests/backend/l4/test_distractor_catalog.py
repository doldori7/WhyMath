"""distractor op-code 카탈로그 단위테스트 — 무결성·모델 검증(슬108 그라운드워크).

검증: ① 모든 op-code의 `misconception_id`가 정본 카탈로그(`CATALOG_BY_ID`)에 실재, ② op-code
`domain`이 연결 오개념 domain과 정합, ③ id 유일·kebab-case, ④ `DISTRACTOR_BY_ID` 정합,
⑤ 모델 검증(미등록 id 거부·frozen·extra forbid). 라이브 의존 0.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.distractor import (
    DISTRACTOR_BY_ID,
    DISTRACTOR_CATALOG,
    DistractorOpCode,
)

_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class TestCatalogIntegrity:
    def test_catalog_nonempty(self) -> None:
        assert len(DISTRACTOR_CATALOG) >= 5  # 시드 5종 이상(도메인 교차)

    def test_all_misconception_ids_known(self) -> None:
        # 각 op-code는 정본 오개념 카탈로그의 실재 키를 가리켜야 한다(생성 검증의 사후 확인).
        for d in DISTRACTOR_CATALOG:
            assert d.misconception_id in CATALOG_BY_ID, d.id

    def test_domain_matches_linked_misconception(self) -> None:
        # op-code domain은 연결된 오개념의 domain과 일치해야 한다(정합·조직화 무결성).
        for d in DISTRACTOR_CATALOG:
            assert d.domain == CATALOG_BY_ID[d.misconception_id].domain, d.id

    def test_ids_unique_and_kebab(self) -> None:
        ids = [d.id for d in DISTRACTOR_CATALOG]
        assert len(ids) == len(set(ids))  # 유일
        for op_id in ids:
            assert _KEBAB.match(op_id), op_id  # kebab-case

    def test_domains_cross_at_least_three(self) -> None:
        # 시드는 단일 도메인 편중이 아니라 교차여야 한다(스캐폴드 대표성).
        assert len({d.domain for d in DISTRACTOR_CATALOG}) >= 3

    def test_by_id_consistent(self) -> None:
        assert len(DISTRACTOR_BY_ID) == len(DISTRACTOR_CATALOG)
        for d in DISTRACTOR_CATALOG:
            assert DISTRACTOR_BY_ID[d.id] is d


class TestModelValidation:
    def test_unknown_misconception_id_rejected(self) -> None:
        # 미등록 misconception_id는 *생성 시점*에 거부(fail-fast·정본 참조 보장).
        with pytest.raises(ValidationError):
            DistractorOpCode(
                id="bogus-op",
                name_kr="가짜",
                domain="대수",
                operation="존재하지 않는 오개념을 가리킴.",
                misconception_id="this-id-does-not-exist",
            )

    def test_valid_construction(self) -> None:
        d = DistractorOpCode(
            id="valid-op",
            name_kr="유효",
            domain="대수",
            operation="distribution-over-power를 가리키는 유효 op-code.",
            misconception_id="distribution-over-power",
        )
        assert d.misconception_id == "distribution-over-power"

    def test_frozen(self) -> None:
        d = DISTRACTOR_CATALOG[0]
        with pytest.raises(ValidationError):
            d.id = "mutated"  # type: ignore[misc]

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            DistractorOpCode(
                id="extra-op",
                name_kr="추가필드",
                domain="대수",
                operation="extra 필드 금지 검증.",
                misconception_id="distribution-over-power",
                surprise="not allowed",  # type: ignore[call-arg]
            )
