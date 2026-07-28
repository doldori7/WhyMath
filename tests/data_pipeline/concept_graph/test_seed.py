"""concept_graph seed 단위테스트 — 후보 노드·엣지 생성 + CSV 저장.

정본: docs/data/concept_graph.md §3.1·§6.2. 라이브 인프라 불요(순수 변환·파일).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from data_pipeline.concept_graph.models import CONCEPT_ID_PATTERN, Relation
from data_pipeline.concept_graph.seed import (
    build_concept_id,
    seed_concepts,
    seed_edges,
    write_concepts_csv,
    write_edges_csv,
)
from data_pipeline.ncic.models import AchievementStandard
from data_pipeline.ncic.transform import build_norm_id


def _std(
    code: str, *, subject: str, domain: str, parents: list[str] | None = None
) -> AchievementStandard:
    grade_band = "중학교 1~3학년군" if code.startswith("[9") else "고등학교"
    school_type = "중학교" if code.startswith("[9") else "고등학교"
    return AchievementStandard(
        norm_id=build_norm_id("2022 개정", code),
        code=code,
        grade_band=grade_band,
        school_type=school_type,
        subject=subject,
        domain=domain,
        statement="성취기준 본문(시드는 이 텍스트를 복제하지 않아야 함).",
        source_url="https://www.ncic.go.kr/x",
        parent_codes=parents or [],
    )


def _calc_samples() -> list[AchievementStandard]:
    return [
        _std("[12미적Ⅰ01-01]", subject="미적분Ⅰ", domain="함수의 극한"),
        _std(
            "[12미적Ⅰ01-02]",
            subject="미적분Ⅰ",
            domain="함수의 극한",
            parents=["[12미적Ⅰ01-01]"],
        ),
        _std("[10공수1-01-01]", subject="공통수학1", domain="다항식"),  # 미적분 아님(필터 대상)
    ]


class TestBuildConceptId:
    def test_deterministic_and_valid(self) -> None:
        """동일 코드 → 동일 잠정 seed ID(멱등) + canonical 규약 통과."""
        first = build_concept_id("[9수01-01]")
        assert first == build_concept_id("[9수01-01]")
        assert CONCEPT_ID_PATTERN.match(first)
        # [9수01-01] → 잠정 seed 네임스페이스·영역01=a01·순번01→001(Wall D)
        assert first == "math.seed.a01-001"

    def test_seed_namespace_regardless_of_grade(self) -> None:
        """Wall D — 시드는 name_ko가 없어 의미론 slug 불가라 학년 무관 잠정 seed 네임스페이스."""
        for code in ("[6수01-01]", "[9수01-01]", "[10공수1-01-01]", "[12미적Ⅰ01-01]"):
            cid = build_concept_id(code)
            assert cid.startswith("math.seed.")
            assert CONCEPT_ID_PATTERN.match(cid)

    def test_distinct_codes_distinct_ids(self) -> None:
        # 시드 ID는 (영역코드, 순번) 파생 — 학년 무관이라 (domain, seq)를 서로 다르게 선택.
        ids = {build_concept_id(c) for c in ("[9수01-01]", "[9수01-02]", "[9수03-01]")}
        assert len(ids) == 3

    def test_unmapped_subject_still_valid(self) -> None:
        """미수록 과목약칭이라도 코드가 파싱되면 잠정 seed ID 생성(영역코드→a<NN>)."""
        cid = build_concept_id("[12서양Ⅰ01-01]")  # '서양Ⅰ' 미수록이나 파싱 가능
        assert CONCEPT_ID_PATTERN.match(cid)
        assert cid == "math.seed.a01-001"


class TestSeedConcepts:
    def test_one_candidate_per_standard(self) -> None:
        rows = seed_concepts(_calc_samples())
        assert len(rows) == 3
        assert all(CONCEPT_ID_PATTERN.match(r["concept_id"]) for r in rows)

    def test_domain_filter_matches_subject(self) -> None:
        """'미적분' 필터 → 미적분Ⅰ 2건만(공통수학 제외)."""
        rows = seed_concepts(_calc_samples(), domain_filter="미적분")
        assert len(rows) == 2
        assert all("미적Ⅰ" in r["standard_codes"] for r in rows)

    def test_expert_fields_blank(self) -> None:
        """오개념·시각화는 빈칸(전문가 작성 대기). 표시이름은 노드 비내장이라 컬럼 자체가 없다."""
        row = seed_concepts([_std("[9수01-01]", subject="수학", domain="수와 연산")])[0]
        assert "name_ko" not in row  # P2d Concept Purity — 표시이름 컬럼 제거
        assert row["misconception_codes"] == ""
        assert row["visualization_card_keys"] == ""
        assert row["notes"].startswith("[seed]")

    def test_autofilled_fields(self) -> None:
        """concept_id·domain·grade_band_hint·standard_codes는 자동."""
        row = seed_concepts([_std("[9수01-01]", subject="수학", domain="수와 연산")])[0]
        assert row["domain"] == "수와 연산"
        assert row["grade_band_hint"] == "중학교 1~3학년군"
        assert row["standard_codes"] == "[9수01-01]"

    def test_parent_codes_become_prerequisite_ids(self) -> None:
        """parent_codes → prerequisite_concept_ids(;-구분, UC ID)."""
        rows = seed_concepts(_calc_samples(), domain_filter="미적분")
        child = next(r for r in rows if r["standard_codes"] == "[12미적Ⅰ01-02]")
        assert child["prerequisite_concept_ids"] == build_concept_id("[12미적Ⅰ01-01]")

    def test_statement_never_copied(self) -> None:
        """법적: 성취기준 본문이 어떤 컬럼에도 들어가지 않는다."""
        rows = seed_concepts(_calc_samples())
        for r in rows:
            assert "성취기준 본문" not in json.dumps(r, ensure_ascii=False)


class TestSeedEdges:
    def test_prerequisite_edge_from_parent(self) -> None:
        rows = seed_edges(_calc_samples(), domain_filter="미적분")
        assert len(rows) == 1
        edge = rows[0]
        assert edge["src_concept_id"] == build_concept_id("[12미적Ⅰ01-01]")
        assert edge["dst_concept_id"] == build_concept_id("[12미적Ⅰ01-02]")
        assert edge["relation"] == Relation.PREREQUISITE.value
        assert edge["evidence_source"] == "ncic"

    def test_strength_and_evidence_blank(self) -> None:
        """strength·evidence는 전문가 빈칸."""
        edge = seed_edges(_calc_samples(), domain_filter="미적분")[0]
        assert edge["strength"] == ""
        assert edge["evidence"] == ""

    def test_no_parents_no_edges(self) -> None:
        rows = seed_edges([_std("[9수01-01]", subject="수학", domain="수와 연산")])
        assert rows == []

    def test_dedup_duplicate_parent(self) -> None:
        """같은 부모 중복 → 엣지 1개."""
        std = _std(
            "[9수01-02]",
            subject="수학",
            domain="수와 연산",
            parents=["[9수01-01]", "[9수01-01]"],
        )
        assert len(seed_edges([std])) == 1


class TestWriteCsv:
    def test_concepts_csv_roundtrip(self, tmp_path: Path) -> None:
        rows = seed_concepts(_calc_samples())
        out = tmp_path / "concepts.csv"
        n = write_concepts_csv(rows, out)
        assert n == 3
        assert out.read_bytes().startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
        with out.open(encoding="utf-8-sig") as f:
            read = list(csv.DictReader(f))
        assert len(read) == 3
        assert "concept_id" in read[0]
        assert "name_ko" not in read[0]  # 표시이름 컬럼 제거(locale 분리)

    def test_edges_csv_and_sidecar(self, tmp_path: Path) -> None:
        rows = seed_edges(_calc_samples(), domain_filter="미적분")
        out = tmp_path / "edges.csv"
        write_edges_csv(rows, out)
        sidecar = out.with_suffix(".meta.json")
        assert sidecar.exists()
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "NCIC" in meta["source_citation"]  # 승계 출처 의무
        assert meta["rows"] == 1
