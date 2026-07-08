# 와이매스 전략 그래프 v1 — 데이터 카드

> **StrategyNode closed 택소노미 코퍼스**(리치 Part 2 Phase 6a). 문제 공략 전략(Polya 계획 단계
> heuristic) 8개 · 4 family · 전량 자체작성. 소비처 연동(참조 키·resolution)은 Phase 6b.

---

## 1. 출처·프로비넌스

- **출처**: 와이매스 **자체작성** 전략 택소노미. 표준 어휘는 Polya 『How to Solve It』(1945) 계획
  단계 heuristic을 **1차 정본**으로 하고, Schoenfeld·Engel(『Problem-Solving Strategies』)·
  Zeitz(『The Art and Craft of Problem Solving』)에서 **수렴하는 공통 어휘**를 골랐다. 표준 용어는
  저작권 대상이 아니며, **어느 책의 본문·예제도 복제하지 않는다** — 각 `description`은 인지행동
  기준으로 재서술한 자체 문장이다(`standard_codes`는 연결 코드만·전략은 특정 기준에 비종속).
- **입력**: `data/corpus/strategy_graph_v1/strategies.jsonl`(저작) → `graph.json`+`_provenance.json`
  (`python -m data_pipeline.strategy_graph transform-v1` 생성·sha256·결정론).
- **품질**: v1=`ai_estimated`(전문 검수 전·소비처 프로젝션 `review_status`에 정직 표기).

## 2. 스키마 (`StrategyNode`)

| 필드 | 타입 | 비고 |
|---|---|---|
| `strategy_id` | **PK** `str` | `strategy.<slug>`(예 `strategy.work_backward`). 교육과정·언어 무관·소문자·숫자·`_`·`-` |
| `name_ko` | `str` | 표시명(한국어·자체작성) |
| `family` | `str` | 전략 family(4종 화이트리스트: `reduction`·`transformation`·`exploration`·`indirect`) |
| `description` | `str` | **인지행동 기준** 자체작성 설명(표면 표현 아님·본문 미복제·비어있지 않음) |
| `standard_codes` | `list[str]` | 연결 NCIC 성취기준 코드(선택·**기본 []**·전략은 특정 기준에 비종속) |

**미도입(enum-free 순수 TEXT·anti-explosion)**: native enum 없음(family는 모듈 상수
`STRATEGY_FAMILIES` 화이트리스트로 검증) · `resolve.py` 없음(problem_type_graph/formula_graph
선례) · **엣지·선수 DAG 없음**(closed 8노드 canonical·연결은 소비처 참조 키가 Phase 6b에 담당·
신규 엣지 타입 0).

## 3. 8 전략 · 4 family

| slug | family | name_ko |
|---|---|---|
| `specialize` | reduction | 특수화 |
| `work_backward` | reduction | 역방향 공략 |
| `analogy` | reduction | 유추 |
| `reformulate` | transformation | 재표현 |
| `auxiliary_construction` | transformation | 보조요소 도입 |
| `pattern_seeking` | exploration | 규칙 발견 |
| `case_exhaustion` | exploration | 경우 나누기 |
| `contradiction` | indirect | 귀류법 |

family 분포: reduction(3)·transformation(2)·exploration(2)·indirect(1). = **8 전략**.

## 4. 축 구별 (필수 — StrategyNode ≠ ReasoningType ≠ approach_type)

StrategyNode는 인접한 두 축과 **다른 축**이다. 표면 표현이 아니라 *인지행동*으로 구별한다:

- **`ReasoningType`(스텝 추론 7종)** — 한 풀이 *스텝*이 무슨 추론인가(연역 한 걸음의 성격).
- **`approach_type`(풀이 전체 6종)** — *완성된 풀이 전체*가 어떤 접근으로 굴러갔는가.
- **`StrategyNode`(공략 전략 8종·본 자산)** — 문제를 만났을 때 *어떤 발상으로 계획을 세우는가*
  (**Polya 계획 단계**의 heuristic). 아직 스텝도 완성 풀이도 아닌, "어디서부터 손댈까"의 축.

세 축의 혼동을 구조적으로 막기 위해 slug를 두 인접 축 값과 **문자열 disjoint**하게 명명했다:
`work_backward`≠`backward` · `case_exhaustion`≠`case_split` · `pattern_seeking`≠`induction` ·
`reformulate`≠`transformation`. 같은 발상을 가리키더라도 축이 다르면 어휘를 겹치지 않는다(join·
검색 시 축 혼선 방지).

## 5. 불변식 (검증)

- `strategy_count`(error) — 정확히 **8개**(closed 택소노미·누락/증식 차단).
- `strategy_slug_unique`(error) — slug(=strategy_id) 중복 없음(join 붕괴 방지).
- `strategy_slug_set`(error) — slug 집합이 `STRATEGY_SLUGS`와 정확히 일치(누락·미승인 차단).
- `strategy_family_known`(error) — family ∈ `STRATEGY_FAMILIES`(모델도 보장·그래프 계약 명문화).
- **엣지 배열 부재** — 노드는 순수 canonical 단위(extra="forbid"·엣지 필드 없음).

성공 기준은 **error 0건**(warning 없음). 구조 invariant(id 형식·필수 필드·family 화이트리스트·
description 비어있지 않음)은 `StrategyNode` 생성 시 Pydantic이 강제한다.

## 6. 소비처·경계

- **적재**: 소비처 실재 시 `strategy_node` 테이블(PG 프로젝션·code 키 멱등 upsert·선례 미러).
- **경계(6b로 분리)**: 전략↔개념/문제유형 참조 매핑·런타임 resolution·Tutor(Polya 계획 단계 코칭)
  연동은 **소비처 실재 시 Phase 6b**(dead code 회피·formula 5a→5b 선례).

---

**버전**: v1 (Phase 6a·2026-07-08) · 관련: `formula_graph_v1.md`·`problem_type_graph_v1.md`·
`skill_graph_v1.md`·`concept_node_layering_decision.md`
