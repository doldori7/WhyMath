"""웜스타트 probe 힌트 조립 — 진단 시작 시 `plan_probe`가 겨냥할 outside_mids 공급 (S1-c).

설계 정본: `docs/architecture/s1_e2e_vertical_slice_design.md` §S1(웜스타트)·감사 Q5. 진단이 처음
시작될 때 하네스의 탐색(ε-탐색) probe(`probe_selection.plan_probe`)가 겨냥할 **외부 오개념 후보**
(`outside_mids`)를 *미리* 조립해 콜드스타트를 없앤다 — 아직 학생 증거가 없어 활성 가설이 비어 있을
때, 단원 고빈도 오개념 + 근접 원자의 오개념을 힌트로 공급해 첫 진단 문항이 겨냥할 표적을 준다
(`resolve_probe_target`이 활성 세트가 없으면 `outside_mids[0]`을 그대로 겨냥·`probe_selection.py`
:166).

────────────────────────────────────────────────────────────────────────────
경계 (감사 Q5 · CLAUDE.md 절대 금기 — 협상 불가)
────────────────────────────────────────────────────────────────────────────
이 모듈이 조립하는 힌트는 **진단 probe 타깃팅 전용**이다:

  - 반환은 **오직 `list[str]`(mis_id = outside_mids)뿐**이다. 오개념 본문·코칭 관련 필드·개입
    문구는 *구조적으로* 담기지 않는다(반환 타입이 `list[str]`이라 실을 자리가 없다). 소비처는
    `SelectProbeAction.outside_mids` → `plan_probe`(진단 문항 *선별*) 한 경로뿐이다.
  - **코칭 context·개입에 오개념을 preload하지 않는다.** CLAUDE.md "오개념을 초기 context에
    preload 금지 — reactive retrieval만(misconception contamination 방지)". 코칭(소크라테스
    개입·프롬프트 조립)은 학생 증거에 반응해 *reactive*로 오개념을 가져오는 기존 경로를
    그대로 유지한다 — 웜스타트 힌트는 그 경로에 결코 흐르지 않는다. outside_mids는 "진단이
    *구별*해볼 후보"이지 "학생이 가졌다고 *가정*하는 오개념"이 아니다(낙인·오염 방지).
  - 따라서 이 힌트는 진단 *다양성*(1위 고착 방지·R4)을 위한 탐색 표적 풀일 뿐, 학생에게
    노출되는 어떤 발화·context에도 실리지 않는다. 소비처(`harness/wh1_shadow.py`)는
    warmstart 리스트를 `LLMTutorPolicy`의 *사적 probe 컨텍스트*(outside_mids)로만 주입한다.

────────────────────────────────────────────────────────────────────────────
조립 재료 (2원천 — 고빈도 카탈로그 + atom search 확장)
────────────────────────────────────────────────────────────────────────────
ⓐ **단원 고빈도 오개념**: `misconception_catalog`에서 문제 도메인/성취기준(`domain`·
   `standard_code`)에 해당하는 오개념을 조회한다. 카탈로그엔 *발생빈도* 컬럼이 없으므로(행동
   로그 집계는 ClickHouse 후속) `mapping_score`(개념 매핑 신뢰도)를 *현저성 프록시*로 삼아
   내림차순 랭킹한다(동률·None은 mis_id 오름차순 결정론 tiebreak). "고빈도"의 진짜 신호(실
   오답 빈도)는 후속 슬라이스 몫이며, 지금은 매핑 신뢰도가 그 자리표시다(정직).
ⓑ **atom search 확장**(⑧ 첫 실소비): 약점/문제 개념 텍스트를 `l1.atom_graph.search_atoms`로
   근접 원자 top-k 검색(S0-4a) → 잡힌 원자 code로 카탈로그를 다시 조회(`concept_src_id`/
   `standard_code` 느슨참조 매칭) → 그 원자들의 오개념을 추가한다. provider가 없거나 개념
   텍스트가 없으면 이 확장은 *생략*(graceful·고빈도만)한다. memory 모드면 `search_atoms`가
   빈 결과를 돌려주므로(조용한 무동작 금지) 확장은 자연히 0이다.

두 원천을 이어붙여 *순서 보존* 중복 제거(고빈도 우선)하고 `limit`으로 자른다. 결과 순서는
결정론이라 `outside_mids[0]`(첫 탐색 표적)이 재현 가능하다.

7계층: L4 교수학(진단). L1(`atom_graph`·`misconception_catalog`)을 *조회*만 하며(하위 호출·
역방향 의존 0), L2/L3 로직은 건드리지 않는다. 학생-대면 결정론 코칭 경로는 무변경(웜스타트는
하네스 shadow 경로에만 배선).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from whymath_backend.config import Settings
from whymath_backend.db.models.misconception_catalog import (
    MisconceptionCatalog as MisconceptionCatalogORM,
)
from whymath_backend.db.models.problem import Problem as ProblemORM
from whymath_backend.l1.atom_graph.retrieval import AtomSearchHit, search_atoms

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from whymath_backend.l1.embedding_primitives import EmbeddingProvider

__all__ = ["assemble_warmstart_probe_hints"]

# 기본 outside_mids 상한 — 탐색 표적 풀은 *작게* 유지한다(plan_probe는 outside_mids[0]만 쓰고,
# ε-탐색 주기마다 앞에서부터 소비). 12는 Minimal Reasoning Subgraph max_nodes 하한(12~20·Part 8)
# 정신과 정합하는 보수 상한 — 힌트가 팽창해 진단이 산만해지지 않게 한다.
_DEFAULT_LIMIT = 12
# atom search 근접 원자 top-k 기본값 — 각 원자가 여러 오개념을 낳을 수 있어 작게 잡는다.
_DEFAULT_ATOM_TOP_K = 5

# atom search 좌석 타입(주입 가능·hermetic 테스트용). 기본은 실 `search_atoms`(S0-4a).
_AtomSearchFn = Callable[..., list[AtomSearchHit]]


def _high_frequency_sort_key(mis_id: str, score: Decimal | float | None) -> tuple[int, float, str]:
    """단원 고빈도(=현저성 프록시) 랭킹 키 — `mapping_score` 내림차순·None 후순·mis_id 오름차순.

    `mapping_score`가 있으면 (0, -score, mis_id)로 큰 점수 우선, 없으면 (1, 0, mis_id)로 뒤로
    민다. 동률은 mis_id 사전식 오름차순으로 결정론 tiebreak(입력 순서·행 순서 무관 재현).
    """
    if score is None:
        return (1, 0.0, mis_id)
    return (0, -float(score), mis_id)


async def _fetch_high_frequency_mids(
    session: AsyncSession,
    *,
    domain: str | None,
    standard_code: str | None,
) -> list[str]:
    """단원(도메인/성취기준) 고빈도 오개념 mis_id를 카탈로그에서 결정론 랭킹으로 조회.

    `domain`·`standard_code` 중 주어진 것으로 `OR` 필터한다(둘 다 None이면 조회 없이 빈 리스트 —
    단원 맥락이 없어 조립 불가). `mapping_score`를 현저성 프록시로 내림차순 정렬(`_high_frequency_
    sort_key`)한다. 반환은 mis_id 리스트뿐(본문·점수 미노출).
    """
    conditions = []
    if domain is not None:
        conditions.append(MisconceptionCatalogORM.domain == domain)
    if standard_code is not None:
        conditions.append(MisconceptionCatalogORM.standard_code == standard_code)
    if not conditions:
        return []

    stmt = select(MisconceptionCatalogORM.mis_id, MisconceptionCatalogORM.mapping_score).where(
        or_(*conditions)
    )
    result = await session.execute(stmt)
    rows = result.all()
    ranked = sorted(rows, key=lambda r: _high_frequency_sort_key(r[0], r[1]))
    return [r[0] for r in ranked]


async def _fetch_atom_expansion_mids(
    session: AsyncSession,
    atom_codes: Sequence[str],
) -> list[str]:
    """근접 원자 code들의 오개념 mis_id를 카탈로그에서 조회 — 원자 근접 순서 보존 랭킹.

    카탈로그의 `concept_src_id`/`standard_code`(느슨참조)가 원자 code와 일치하는 행을 IN 한 번에
    조회한 뒤, *가장 근접한 원자*(atom_codes 앞쪽)에 매칭된 오개념을 앞세운다(atom_index·mis_id
    결정론 정렬). atom_codes가 비면 빈 리스트(조회 없음).
    """
    if not atom_codes:
        return []
    code_rank = {code: i for i, code in enumerate(atom_codes)}
    stmt = select(
        MisconceptionCatalogORM.mis_id,
        MisconceptionCatalogORM.concept_src_id,
        MisconceptionCatalogORM.standard_code,
    ).where(
        or_(
            MisconceptionCatalogORM.concept_src_id.in_(atom_codes),
            MisconceptionCatalogORM.standard_code.in_(atom_codes),
        )
    )
    result = await session.execute(stmt)

    ranked: list[tuple[int, str]] = []
    for mis_id, concept_src_id, std_code in result.all():
        # 이 행이 매칭된 원자들 중 *가장 근접한*(rank 최소) 원자 인덱스로 정렬(없으면 skip 방어).
        candidate_ranks = [
            code_rank[c] for c in (concept_src_id, std_code) if c is not None and c in code_rank
        ]
        if not candidate_ranks:
            continue
        ranked.append((min(candidate_ranks), mis_id))
    ranked.sort(key=lambda t: (t[0], t[1]))
    return [mis_id for _rank, mis_id in ranked]


async def _resolve_problem_context(
    session: AsyncSession,
    problem_id: uuid.UUID,
) -> tuple[str | None, str | None]:
    """문제 id → (domain, concept_query) 해석 — 카탈로그 조회·atom search 질의 텍스트 소싱.

    문항의 `domain`을 단원 필터로, `subunit`(없으면 `domain`)을 atom search 질의 개념 텍스트로
    쓴다. 문항 부재/미매핑이면 (None, None)(graceful). *문항 본문·정답은 읽지 않는다* — 안전한
    구조 메타(domain·subunit)만 소싱한다(저작권·노출 계약).
    """
    problem = await session.get(ProblemORM, problem_id)
    if problem is None:
        return None, None
    domain = problem.domain
    concept_query = problem.subunit or problem.domain
    return domain, concept_query


async def assemble_warmstart_probe_hints(
    session: AsyncSession,
    *,
    problem_id: uuid.UUID | None = None,
    domain: str | None = None,
    standard_code: str | None = None,
    concept_query: str | None = None,
    user_id: uuid.UUID | None = None,
    provider: EmbeddingProvider | None = None,
    limit: int = _DEFAULT_LIMIT,
    atom_top_k: int = _DEFAULT_ATOM_TOP_K,
    settings: Settings | None = None,
    atom_search: _AtomSearchFn = search_atoms,
    exclude_mids: Sequence[str] = (),
) -> list[str]:
    """웜스타트 probe 힌트(=outside_mids) 조립 — 단원 고빈도 + atom 확장·결정론·중복 제거.

    **진단 probe 타깃팅 전용**이다(감사 Q5·CLAUDE.md). 반환은 오직 mis_id 리스트(outside_mids)이며
    `plan_probe`로만 흐른다 — **코칭 context·개입에 오개념을 preload하지 않는다**(reactive retrieval
    유지·misconception contamination 방지). 반환 타입이 `list[str]`이라 코칭 필드·본문을 실을 자리가
    구조적으로 없다.

    흐름:
      ⓐ 단원 맥락 해석: `domain`/`standard_code`가 주어지면 그대로, 아니면 `problem_id`로 문항의
         `domain`·`subunit`을 안전 메타로 조회(본문·정답 미조회).
      ⓑ 고빈도 오개념: `misconception_catalog`를 `domain`/`standard_code`로 조회, `mapping_score`
         현저성 프록시 내림차순(동률 mis_id asc) 랭킹.
      ⓒ atom search 확장(⑧ 첫 실소비): `provider`와 개념 텍스트(`concept_query`)가 있으면
         `search_atoms`로 근접 원자 top-k → 그 code들의 오개념을 카탈로그에서 조회해 뒤에 잇는다.
         provider/텍스트 없으면 생략(graceful). memory 모드면 search_atoms가 빈 결과(무동작).
      ⓓ 순서 보존 중복 제거(고빈도 우선) 후 `limit`으로 절단.

    Args:
        session: 카탈로그·문항 조회용 async 세션(읽기 전용·신규 테이블·쓰기 0).
        problem_id: 단원 맥락 소싱용 문항 id(domain/standard_code 미주입 시). 안전 메타만 읽는다.
        domain·standard_code: 단원 필터(명시 주입 시 problem 조회보다 우선).
        concept_query: atom search 질의 개념 텍스트(약점/문제 개념). 미주입+problem_id면 subunit.
        user_id: 호출 귀속·후속 per-student 약점 개념 소싱용 자리표시(현재 조립에 미사용).
        provider: atom search 임베딩 제공자. None이면 atom 확장 생략(고빈도만·graceful).
        limit: 반환 outside_mids 상한(기본 12·탐색 표적 풀은 작게).
        atom_top_k: atom search 근접 원자 top-k(기본 5).
        settings·atom_search: 테스트 주입 좌석(hermetic). atom_search 기본은 실 `search_atoms`.
        exclude_mids: 결과에서 뺄 mis_id(PED-04). 세션 회상이 넘기는 *이미 활성인 가설* 집합으로,
            outside_mids의 "활성 세트 밖" 정의를 실제로 충족시킨다. 기본 `()`면 기존 동작 불변.

    Returns:
        outside_mids(mis_id `list[str]`) — 결정론 순서·중복 제거·limit 이내. 단원 맥락이 없거나
        매칭이 없으면 빈 리스트(콜드스타트·조용한 무동작 금지).
    """
    del user_id  # 후속 per-student 약점 개념 소싱 자리표시 — 현재 조립 로직엔 미사용(정직).

    # ⓐ 단원 맥락 해석 — 명시 domain/standard_code 우선, 아니면 problem_id로 안전 메타 소싱.
    if domain is None and standard_code is None and problem_id is not None:
        domain, resolved_query = await _resolve_problem_context(session, problem_id)
        if concept_query is None:
            concept_query = resolved_query

    # ⓑ 단원 고빈도 오개념(현저성 프록시 랭킹).
    high_freq = await _fetch_high_frequency_mids(
        session, domain=domain, standard_code=standard_code
    )

    # ⓒ atom search 확장 — provider·개념 텍스트가 있을 때만(⑧ 첫 실소비). memory 모드/무매칭은
    #    빈 결과로 graceful. 블로킹 임베딩·sync DB이므로 워커 스레드로 돌려 이벤트 루프를 안 막는다.
    atom_expansion: list[str] = []
    if provider is not None and concept_query:
        hits = await asyncio.to_thread(
            atom_search,
            concept_query,
            top_k=atom_top_k,
            provider=provider,
            settings=settings,
        )
        atom_codes = [hit.atom_code for hit in hits]
        atom_expansion = await _fetch_atom_expansion_mids(session, atom_codes)

    # ⓓ 순서 보존 중복 제거(고빈도 우선) → limit 절단. 결정론이라 outside_mids[0] 재현 가능.
    # PED-04: `exclude_mids`를 seen에 미리 넣어 *이미 살아 있는 가설*을 탐색 표적에서 뺀다 —
    # outside_mids는 정의상 "활성 세트 *밖*"인데 그동안 활성 세트를 알 길이 없어 겹칠 수 있었다.
    seen: set[str] = set(exclude_mids)
    ordered: list[str] = []
    for mid in (*high_freq, *atom_expansion):
        if mid not in seen:
            seen.add(mid)
            ordered.append(mid)
        if len(ordered) >= limit:
            break
    return ordered
