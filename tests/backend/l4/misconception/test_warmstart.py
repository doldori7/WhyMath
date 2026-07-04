"""웜스타트 probe 힌트 조립 단위테스트 — S1-c (hermetic·PG 불요·fake session/catalog·FakeProvider).

`assemble_warmstart_probe_hints`를 fake async 세션(canned 카탈로그 행)·주입 atom_search 좌석으로
검증한다(실 네트워크·실 PG·라이브 임베딩 0). 검증 축:

  ① 단원 고빈도 — domain/standard_code 필터 + mapping_score 현저성 프록시 랭킹(동률 mis_id asc)
  ② atom search 확장(⑧ 첫 실소비) — 근접 원자 code → 카탈로그 오개념을 고빈도 뒤에 잇는다
  ③ 중복 제거·결정론 — 고빈도 우선 순서 보존 dedup·limit 절단·재현 가능한 outside_mids[0]
  ④ graceful — 단원 맥락 없음/memory 모드/문항 부재 → 빈 리스트(조용한 무동작 금지)
  ⑤ **경계(핵심)** — 반환은 outside_mids(mis_id `list[str]`)뿐·코칭 필드/본문 0(preload 금기 동결)
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from whymath_backend.l1.atom_graph.retrieval import AtomSearchHit
from whymath_backend.l4.misconception import warmstart as warmstart_mod
from whymath_backend.l4.misconception.warmstart import assemble_warmstart_probe_hints


# ──────────────────────────────────────────────────────────────────────────
# fake async 세션 — execute(select) 컬럼 수로 고빈도(2열)/atom(3열) 질의를 라우팅
# ──────────────────────────────────────────────────────────────────────────
class _FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[Any, ...]]:
        return self._rows


class _FakeProblem:
    def __init__(self, *, domain: str | None, subunit: str | None) -> None:
        self.domain = domain
        self.subunit = subunit


class _FakeSession:
    """AsyncSession 최소 흉내 — 카탈로그 execute + 문항 get. 질의를 컬럼 수로 라우팅한다.

    고빈도 질의는 (mis_id, mapping_score) 2열, atom 확장 질의는 (mis_id, concept_src_id,
    standard_code) 3열이라 `column_descriptions` 길이로 구분해 canned 행을 돌려준다(hermetic).
    """

    def __init__(
        self,
        *,
        high_freq_rows: list[tuple[str, Decimal | float | None]] | None = None,
        atom_rows: list[tuple[str, str | None, str | None]] | None = None,
        problem: _FakeProblem | None = None,
    ) -> None:
        self._high_freq_rows = high_freq_rows or []
        self._atom_rows = atom_rows or []
        self._problem = problem
        self.executed: list[object] = []
        self.got: list[uuid.UUID] = []

    async def execute(self, statement: Any) -> _FakeResult:
        self.executed.append(statement)
        ncols = len(statement.column_descriptions)
        if ncols == 2:
            return _FakeResult(list(self._high_freq_rows))
        return _FakeResult(list(self._atom_rows))

    async def get(self, _model: object, ident: uuid.UUID) -> _FakeProblem | None:
        self.got.append(ident)
        return self._problem


class _DummyProvider:
    """embed 좌석 충족 더미 — atom_search 좌석을 주입하므로 실제 embed는 호출되지 않는다."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def _run(coro: Any) -> list[str]:
    return asyncio.run(coro)


# ──────────────────────────────────────────────────────────────────────────
# ① 단원 고빈도 — domain/standard_code 필터 + mapping_score 랭킹
# ──────────────────────────────────────────────────────────────────────────
class TestHighFrequency:
    def test_ranks_by_mapping_score_desc_then_mis_id(self) -> None:
        # mapping_score 내림차순, 동률·None은 mis_id 오름차순 결정론 tiebreak.
        session = _FakeSession(
            high_freq_rows=[
                ("M0003", Decimal("0.40")),
                ("M0001", Decimal("0.90")),
                ("M0002", Decimal("0.90")),  # M0001과 동률 → mis_id asc
                ("M0004", None),  # None → 후순
            ]
        )
        result = _run(assemble_warmstart_probe_hints(session, domain="함수와 극한"))
        assert result == ["M0001", "M0002", "M0003", "M0004"]

    def test_standard_code_filter_path(self) -> None:
        session = _FakeSession(high_freq_rows=[("M0010", Decimal("0.5"))])
        result = _run(assemble_warmstart_probe_hints(session, standard_code="10공수1-01-02"))
        assert result == ["M0010"]

    def test_no_unit_context_returns_empty(self) -> None:
        # domain·standard_code·problem_id 모두 없으면 단원 맥락 부재 → 빈 리스트(조회 없음).
        session = _FakeSession(high_freq_rows=[("M0001", Decimal("0.9"))])
        result = _run(assemble_warmstart_probe_hints(session))
        assert result == []
        assert session.executed == []  # 조회 자체를 안 한다


# ──────────────────────────────────────────────────────────────────────────
# ② atom search 확장 — 근접 원자 → 카탈로그 오개념을 고빈도 뒤에 잇는다(⑧ 첫 실소비)
# ──────────────────────────────────────────────────────────────────────────
class TestAtomExpansion:
    def test_expansion_appended_after_high_frequency(self) -> None:
        session = _FakeSession(
            high_freq_rows=[("M0001", Decimal("0.9"))],
            atom_rows=[
                ("M0050", "2수01-01-2", None),  # concept_src_id 매칭(원자 rank 0)
                ("M0051", None, "2수01-02-1"),  # standard_code 매칭(원자 rank 1)
            ],
        )
        calls: list[tuple[str, int]] = []

        def _fake_atom_search(
            query_text: str, *, top_k: int, provider: Any, settings: Any = None
        ) -> list[AtomSearchHit]:
            calls.append((query_text, top_k))
            return [
                AtomSearchHit(atom_code="2수01-01-2", similarity=0.95),
                AtomSearchHit(atom_code="2수01-02-1", similarity=0.80),
            ]

        result = _run(
            assemble_warmstart_probe_hints(
                session,
                domain="함수와 극한",
                concept_query="극한의 정의",
                provider=_DummyProvider(),
                atom_search=_fake_atom_search,
            )
        )
        # 고빈도(M0001) 다음에 atom 확장(원자 근접 순서 M0050→M0051).
        assert result == ["M0001", "M0050", "M0051"]
        # atom_search가 개념 텍스트로 정확히 1회 호출됐다(⑧ 첫 실소비).
        assert calls == [("극한의 정의", 5)]

    def test_no_provider_skips_atom_search(self) -> None:
        session = _FakeSession(high_freq_rows=[("M0001", Decimal("0.9"))])
        called = False

        def _fake_atom_search(*_a: Any, **_kw: Any) -> list[AtomSearchHit]:
            nonlocal called
            called = True
            return []

        result = _run(
            assemble_warmstart_probe_hints(
                session,
                domain="함수와 극한",
                concept_query="극한",
                provider=None,  # provider 없음 → atom 확장 생략(graceful·고빈도만)
                atom_search=_fake_atom_search,
            )
        )
        assert result == ["M0001"]
        assert called is False  # atom_search 미호출

    def test_no_concept_query_skips_atom_search(self) -> None:
        session = _FakeSession(high_freq_rows=[("M0001", Decimal("0.9"))])
        called = False

        def _fake_atom_search(*_a: Any, **_kw: Any) -> list[AtomSearchHit]:
            nonlocal called
            called = True
            return []

        result = _run(
            assemble_warmstart_probe_hints(
                session,
                domain="함수와 극한",
                concept_query=None,  # 개념 텍스트 없음 → atom 확장 생략
                provider=_DummyProvider(),
                atom_search=_fake_atom_search,
            )
        )
        assert result == ["M0001"]
        assert called is False


# ──────────────────────────────────────────────────────────────────────────
# ③ 중복 제거·결정론·limit
# ──────────────────────────────────────────────────────────────────────────
class TestDedupDeterminismLimit:
    def test_dedup_preserves_high_frequency_first(self) -> None:
        # 같은 mis_id가 고빈도·atom 양쪽에 나오면 고빈도 위치(첫 등장)만 남긴다(순서 보존 dedup).
        session = _FakeSession(
            high_freq_rows=[("M0001", Decimal("0.9")), ("M0002", Decimal("0.8"))],
            atom_rows=[("M0001", "c1", None), ("M0099", "c2", None)],
        )

        def _fake_atom_search(*_a: Any, **_kw: Any) -> list[AtomSearchHit]:
            return [
                AtomSearchHit(atom_code="c1", similarity=0.9),
                AtomSearchHit(atom_code="c2", similarity=0.5),
            ]

        result = _run(
            assemble_warmstart_probe_hints(
                session,
                domain="d",
                concept_query="개념",
                provider=_DummyProvider(),
                atom_search=_fake_atom_search,
            )
        )
        # M0001은 고빈도에서 먼저 등장 → atom 재등장은 제거. M0099만 추가.
        assert result == ["M0001", "M0002", "M0099"]

    def test_limit_truncates(self) -> None:
        session = _FakeSession(high_freq_rows=[(f"M{i:04d}", Decimal("0.9")) for i in range(1, 21)])
        result = _run(assemble_warmstart_probe_hints(session, domain="d", limit=3))
        assert result == ["M0001", "M0002", "M0003"]

    def test_deterministic_across_row_order(self) -> None:
        # 입력 행 순서를 뒤집어도 같은 결과(결정론·outside_mids[0] 재현).
        rows = [("M0002", Decimal("0.9")), ("M0001", Decimal("0.9")), ("M0003", Decimal("0.5"))]
        a = _run(assemble_warmstart_probe_hints(_FakeSession(high_freq_rows=rows), domain="d"))
        b = _run(
            assemble_warmstart_probe_hints(
                _FakeSession(high_freq_rows=list(reversed(rows))), domain="d"
            )
        )
        assert a == b == ["M0001", "M0002", "M0003"]


# ──────────────────────────────────────────────────────────────────────────
# ④ graceful — 문항 해석·빈 결과
# ──────────────────────────────────────────────────────────────────────────
class TestGraceful:
    def test_problem_id_resolves_domain_and_subunit(self) -> None:
        # problem_id로 domain(단원 필터)·subunit(atom 질의)을 안전 메타로 해석한다.
        session = _FakeSession(
            high_freq_rows=[("M0001", Decimal("0.9"))],
            atom_rows=[("M0050", "atomA", None)],
            problem=_FakeProblem(domain="함수와 극한", subunit="극한의 성질"),
        )
        seen_query: list[str] = []

        def _fake_atom_search(
            query_text: str, *, top_k: int, provider: Any, settings: Any = None
        ) -> list[AtomSearchHit]:
            seen_query.append(query_text)
            return [AtomSearchHit(atom_code="atomA", similarity=0.9)]

        result = _run(
            assemble_warmstart_probe_hints(
                session,
                problem_id=uuid.uuid4(),
                provider=_DummyProvider(),
                atom_search=_fake_atom_search,
            )
        )
        assert result == ["M0001", "M0050"]
        assert seen_query == ["극한의 성질"]  # subunit이 atom 질의 개념 텍스트

    def test_problem_not_found_returns_empty(self) -> None:
        session = _FakeSession(problem=None)  # get → None
        result = _run(
            assemble_warmstart_probe_hints(
                session, problem_id=uuid.uuid4(), provider=_DummyProvider()
            )
        )
        assert result == []

    def test_empty_catalog_returns_empty(self) -> None:
        session = _FakeSession(high_freq_rows=[])
        result = _run(assemble_warmstart_probe_hints(session, domain="d"))
        assert result == []


# ──────────────────────────────────────────────────────────────────────────
# ⑤ 경계(핵심) — 반환은 outside_mids(mis_id list[str])뿐·코칭 preload 금기 구조 동결
# ──────────────────────────────────────────────────────────────────────────
class TestBoundaryProbeTargetingOnly:
    def test_return_is_plain_str_list_only(self) -> None:
        # 반환은 순수 mis_id 문자열 리스트 — 코칭 객체·본문·개입 필드를 실을 자리가 구조적으로 없다.
        session = _FakeSession(
            high_freq_rows=[("M0001", Decimal("0.9")), ("M0002", Decimal("0.8"))]
        )
        result = _run(assemble_warmstart_probe_hints(session, domain="d"))
        assert isinstance(result, list)
        assert all(isinstance(m, str) for m in result)
        # 반환 원소는 mis_id 문자열일 뿐 dict/모델(코칭 context 후보)이 아니다.
        assert result == ["M0001", "M0002"]

    def test_module_exports_only_assembly_fn(self) -> None:
        # 모듈은 조립 함수 하나만 공개한다 — 코칭 preload용 헬퍼·context 빌더를 노출하지 않는다.
        assert warmstart_mod.__all__ == ["assemble_warmstart_probe_hints"]
