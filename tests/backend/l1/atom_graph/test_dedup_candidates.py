"""원자 중복 후보 리포트 *단위테스트* — ARCH-16 (hermetic·PG 불요·Fake provider).

DB·pgvector 없이 검증 가능한 계약을 못 박는다:

  ① pairwise 계약 — 자기쌍 없음·대칭 중복 없음(code_a < code_b 정규화)·임계 필터
  ② 결정론 정렬 — similarity 내림차순 → (code_a, code_b) 사전순 → max_candidates 절단
  ③ 분포 통계 — pair_count = nC2·threshold_hits·최대값·상위 밴드 카운트
  ④ 출력 계약 — top key "dedup_candidates"(crosswalk 3형식과 비호환·자동 적재 차단)·notice 동봉
  ⑤ CLI — graph.json 부재 exit 2·정상 exit 0·JSON 산출
  ⑥ redaction 승계 — 임베딩 입력이 안전 필드 경로(load_atoms_from_graph_json)만 탄다는 것은
     기존 `test_atom_embedding.py`가 동결하므로 여기서 재검증하지 않는다(중복 금지)

in-memory 코사인만 쓰므로(`.cosine_distance` 미사용) pgvector allowlist 거버넌스
(`test_embedding_namespace_governance.py`)는 기존 테스트가 자동으로 지킨다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from whymath_backend.config import get_settings
from whymath_backend.l1.atom_graph.dedup_candidates import (
    DedupCandidate,
    SimilarityStats,
    main,
    propose_dedup_candidates,
    render_report,
)
from whymath_backend.l1.atom_graph.embedding import AtomText, load_atoms_from_graph_json
from whymath_backend.l1.embedding_provider import FakeEmbeddingProvider


def _write_graph(path: Path, concepts: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"concepts": concepts}, ensure_ascii=False), encoding="utf-8")
    return path


def _atoms(*pairs: tuple[str, str]) -> list[AtomText]:
    return [AtomText(code=code, text=text) for code, text in pairs]


class TestProposeDedupCandidates:
    def test_identical_texts_pair_above_threshold(self) -> None:
        """동일 표현 두 원자 → cosine 1.0 후보 1건, 자기쌍·대칭 중복 없음."""
        provider = FakeEmbeddingProvider()
        atoms = _atoms(("B1", "일차함수의 기울기"), ("A1", "일차함수의 기울기"), ("C1", "지수법칙"))
        names = {"A1": "기울기", "B1": "기울기(중복)", "C1": "지수법칙"}
        candidates, stats = propose_dedup_candidates(
            provider=provider, atoms=atoms, names=names, threshold=0.99
        )
        assert len(candidates) == 1
        c = candidates[0]
        # code 사전순 정규화(code_a < code_b) — 입력 순서(B1 먼저)와 무관.
        assert (c.code_a, c.code_b) == ("A1", "B1")
        assert c.similarity == 1.0
        assert c.method == "embedding"
        assert "이름 상이" in c.rationale  # names가 다르므로
        # 자기쌍 없음: nC2 = 3.
        assert stats.pair_count == 3
        assert stats.threshold_hits == 1

    def test_threshold_filters_dissimilar(self) -> None:
        """상이 표현은 높은 임계에서 후보로 올라오지 않는다."""
        provider = FakeEmbeddingProvider()
        atoms = _atoms(("A1", "일차함수의 기울기"), ("B1", "확률의 덧셈정리"))
        candidates, stats = propose_dedup_candidates(
            provider=provider, atoms=atoms, names={}, threshold=0.99
        )
        assert candidates == []
        assert stats.pair_count == 1
        assert stats.threshold_hits == 0
        assert 0.0 <= stats.max_similarity < 0.99

    def test_deterministic_sort_and_truncation(self) -> None:
        """similarity 내림차순 → code 사전순 정렬 후 max_candidates 절단."""
        provider = FakeEmbeddingProvider()
        # 동일 텍스트 3개 → 세 쌍 모두 1.0(동률) — code 사전순이 tiebreak.
        same = "일차함수의 기울기"
        atoms = _atoms(("C1", same), ("A1", same), ("B1", same))
        candidates, stats = propose_dedup_candidates(
            provider=provider, atoms=atoms, names={}, threshold=0.99, max_candidates=2
        )
        assert [(c.code_a, c.code_b) for c in candidates] == [("A1", "B1"), ("A1", "C1")]
        assert stats.threshold_hits == 3  # 절단 전 실제 임계 이상 쌍 수는 보존

    def test_empty_and_single_inputs(self) -> None:
        provider = FakeEmbeddingProvider()
        for atoms in ([], _atoms(("A1", "혼자"))):
            candidates, stats = propose_dedup_candidates(provider=provider, atoms=atoms, names={})
            assert candidates == []
            assert stats.pair_count == 0

    def test_band_counts_cover_high_range(self) -> None:
        """상위 밴드(0.80~1.00) 카운트가 임계 이상 쌍을 포착한다."""
        provider = FakeEmbeddingProvider()
        atoms = _atoms(("A1", "일차함수의 기울기"), ("B1", "일차함수의 기울기"))
        _, stats = propose_dedup_candidates(provider=provider, atoms=atoms, names={})
        assert sum(stats.band_counts.values()) >= 1
        assert stats.band_counts["[0.95,1.00)"] == 1  # cosine 1.0은 최상단 밴드로 클립


class TestRenderReport:
    def test_report_contains_calibration_material(self) -> None:
        stats = SimilarityStats(
            pair_count=10,
            max_similarity=1.0,
            threshold_hits=3,
            percentiles={"p50": 0.35},
            band_counts={"[0.95,1.00)": 3},
        )
        candidate = DedupCandidate(
            code_a="A1",
            code_b="B1",
            name_a="기울기",
            name_b="기울기(중복)",
            similarity=1.0,
            method="embedding",
            rationale="cosine=1.000 · 이름 상이",
        )
        text = render_report([candidate], stats, threshold=0.9, truncated=2)
        assert "검수용·자동 병합 아님" in text
        assert "[0.95,1.00): 3" in text
        assert "절단" in text
        assert "A1 ↔ B1" in text


class TestCli:
    def test_missing_graph_exits_2(self, tmp_path: Path) -> None:
        rc = main(["--graph", str(tmp_path / "없는파일.json"), "--out", str(tmp_path / "out.json")])
        assert rc == 2

    def test_end_to_end_json_contract(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI 완주 — fake provider·top key/notice 계약·후보 내용."""
        monkeypatch.setenv("WHYMATH_EMBEDDING_PROVIDER", "fake")
        get_settings.cache_clear()  # setenv 반영(정착 패턴: setenv → clear → try/finally clear)
        graph = _write_graph(
            tmp_path / "graph.json",
            [
                {"code": "A1", "level": "세부개념", "name": "기울기", "transfer": "변화율"},
                {"code": "B1", "level": "세부개념", "name": "기울기", "transfer": "변화율"},
                {"code": "U1", "level": "단원", "name": "함수"},  # 원자 아님 — 제외
            ],
        )
        out = tmp_path / "candidates.json"
        try:
            rc = main(["--graph", str(graph), "--out", str(out), "--threshold", "0.99"])
        finally:
            get_settings.cache_clear()  # fake 설정이 타 테스트로 새지 않게 복원
        assert rc == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        # crosswalk 3형식(candidates/review_queue/crosslinks)과 비호환 top key — 자동 적재 차단.
        assert "dedup_candidates" in payload
        for forbidden in ("candidates", "review_queue", "crosslinks"):
            assert forbidden not in payload
        assert "사람 검수" in payload["notice"]
        assert payload["atom_count"] == 2  # 단원 노드 제외
        assert len(payload["dedup_candidates"]) == 1
        row = payload["dedup_candidates"][0]
        assert (row["code_a"], row["code_b"]) == ("A1", "B1")
        assert row["name_a"] == "기울기"

    def test_loader_reuses_safe_field_path(self, tmp_path: Path) -> None:
        """CLI가 쓰는 로더가 기존 안전 필드 경로임을 배선 수준에서 확인(원자만·표현 합성)."""
        graph = _write_graph(
            tmp_path / "graph.json",
            [{"code": "A1", "level": "세부개념", "name": "기울기", "transfer": "변화율"}],
        )
        atoms = load_atoms_from_graph_json(graph)
        assert [a.code for a in atoms] == ["A1"]
        assert atoms[0].text == "기울기. 변화율"
