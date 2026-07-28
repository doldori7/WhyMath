# 와이매스 문제유형 그래프 v1 (`problem_type_graph`) — 데이터 카드

> **요약**: ProblemType을 `Problem` 스키마 속성에서 **1급 노드로 승격**하는 정본 문제유형 택소노미
> (리치 Part 2 Phase 3·2026-07-07). 문제유형은 문제가 *무슨 사고(cognitive action)를 요구하는가*를
> canonical 단위로 표현한다 — 표면 구조(`SignaturePattern`·"어떻게 보이는가")와 **직교하는 축**
> ("무엇을 사고하는가"). cognitive-action 축은 이미 `BehaviorArea`(Phase 2a)라 **신규 enum을 두지
> 않고**, 유형이 exercise하는 스킬(`behavior_skills`·skill_graph_v1 참조)로 표현한다. 6 family
> 아래 **17개 유형**(v1·compact·canonical). 전량 **와이매스 자체작성**(택소노미).
>
> **현황(Phase 3)**: data-pipeline `data_pipeline.problem_type_graph`(models·transform·validate·CLI)가
> 자체작성 `problem_types.jsonl`을 `graph.json`으로 정형화하고, backend `problem_type_node`(PG
> 프로젝션·problem_type_id 키·native enum 없음)에 멱등 투영한다. **Problem↔ProblemType 연결은
> Phase 3b**(생산자/소비처 확보 후·dead code 회피 — 문제는 L3 동적 생성이라 지금은 채울 좌석 없음).

---

## 1. 출처·프로비넌스

| 항목 | 값 |
|---|---|
| 형태 | 자체작성 `problem_types.jsonl`(유형 1행/줄) → `graph.json`(문제유형 노드 배열) |
| 저작 | **와이매스 자체작성**(cognitive-action 택소노미·검수필요) |
| 규모 | **17 유형** · 6 family · 25 참조 스킬(skill_graph_v1) |
| 산출 | `python -m data_pipeline.problem_type_graph transform-v1 -o data/corpus/problem_type_graph_v1` |
| 결정성 | 동일 `problem_types.jsonl`(sha256) 2회 transform → byte 동일 `graph.json` |

> 라이선스: 전량 자체작성이라 **redaction 대상 아님**(평가원 기출 *문항 본문* 미포함·cognitive-action
> 추상만). `standard_codes`(선택)는 연결 NCIC *코드*만 담고 본문은 담지 않는다(코드는 사실정보·공공).

---

## 2. 스키마 (`problem_types.jsonl` 키 → `problem_type_node` 컬럼)

| 키 | 컬럼 | 비고 |
|---|---|---|
| `problem_type_id` | **PK** `problem_type_id` | `ptype.<slug>` 의미론 id(교육과정·언어 무관·17 유일) |
| `name_ko` | `name_ko` | 유형 표시명(NOT NULL) |
| `family` | `family` | 문제유형 family 그룹(인덱스) |
| `behavior_skills` | `behavior_skills` | exercise하는 skill_id(TEXT[]·**≥1개**·skill_graph_v1 참조·엣지 타입 0) |
| `mastery_estimable` | `mastery_estimable` | 독립추정 게이트(BOOL·기본 true) |
| `description` | `description` | 짧은 설명(자체작성·선택) |
| `standard_codes` | `standard_codes` | 연결 NCIC 코드(TEXT[]·선택·본문 미포함) |
| — | `review_status` | 상수 `'ai_estimated'`(v1 자체작성이나 전문 검수 전·정직 표기) |
| — | `updated_at` | 마지막 upsert 시각 |

> **신규 enum 없음**(cognitive-action 축은 `BehaviorArea`·유형은 스킬 참조로 표현). **본문·표면
> (SignaturePattern) 슬롯 없음**(순수 cognitive-action 택소노미). 유형 연결은 참조 키(`behavior_skills`)
> 만 — 별도 엣지 테이블·prerequisite DAG 없음(**신규 엣지 타입 0**·anti-explosion).

---

## 3. family 6종 (v1·cognitive-action 그룹·자체작성)

| family | 뜻 | 유형 수 |
|---|---|---|
| 값_결정 | 특정 값·양을 구함 | 3 (미지수 값·식의 값·계수 결정) |
| 존재_판정 | 존재·성립 여부를 판정 | 2 (존재성·조건 성립) |
| 개수_세기 | 해·경우의 수를 셈 | 2 (해의 개수·경우의 수) |
| 최적화 | 최대·최소를 구함 | 2 (최댓값/최솟값·제약하 최적화) |
| 관계_추론 | 관계 추론·일반화·증명·모델링 | 4 (관계 추론·규칙 일반화·명제 증명·문장제 모델링) |
| 구성_검증 | 대상 구성·주장 검증 | 4 (대상 구성·주장 검증·그래프 개형·식 변형) |

> family는 폐쇄 enum이 아니라 자유 라벨(그룹핑용)이다 — cognitive-action 축의 진실은 `BehaviorArea`이며
> 유형은 `behavior_skills`로 그 축에 닿는다. 확장은 ADR `concept_node_layering_decision.md` 갱신 전제.

---

## 4. 검증 (그래프 레벨 invariant)

- **problem_type_id_unique**(error) — 유형 id 유일.
- **behavior_skills_nonempty**(error) — 각 유형 ≥1 스킬 참조(cognitive-action 표현 보장).
- **family_singleton**(warning) — family에 유형 1개뿐(그룹핑 의미 약함·v1).

v1 코퍼스: error 0·warning 0(모든 family ≥2 유형). **cross-corpus dangling**(behavior_skills가
skill_graph_v1 skill_id에 실재)은 **backend 거버넌스 테스트**가 skill_graph_v1을 로드해 동결(dangling 0·
실측 25 참조 전부 존재). **ProblemType≠SignaturePattern** 구별 불변식도 두 심볼을 import할 수 있는
backend 거버넌스가 authoritative(형식은 `ptype.<slug>` vs UPPER_SNAKE로 구조적 disjoint).
테스트: `tests/data_pipeline/problem_type_graph/`·`tests/backend/l1/problem_type_graph/`·
`tests/backend/l1/test_problemtype_governance.py`.

---

## 5. 계층·경계 (7계층 아키텍처)

- **L1 데이터 기반**: 이 코퍼스·프로젝션(`problem_type_node`)은 검색 enrichment·필터·(후속) 문제
  분류·추천 백킹. 소비(L2/L4·문제 생성 태깅)는 이 좌석을 쓰되 여기서 구현하지 않는다(역방향 의존 금지).
- **anti-explosion**: ProblemTypeNode는 canonical·독립추정 단위만(문제마다 유형 남발 금지). v1은
  compact(17)·명시적 확장 가능.
- **additive**: 기존 concept_node·atom_node·skill_node·검색과 무충돌(신규 테이블·신규 enum 0).
- **Phase 3b(미룸)**: Problem↔ProblemType 연결(`Problem.problem_type_codes` 참조 배열·`signature_patterns`
  동형)은 생산자/소비처가 생길 때 추가한다 — 지금 넣으면 채울 좌석이 없어 dead code(소비처 없는 추상 미도입).
  발화 조건 구체화(2026-07-28): `../architecture/problem_bank_gap_review.md` §5-③ — 커버리지
  리포트(ARCH-18) 유형 축 수요 또는 L6 유형별 추천 소비처 실재 시.
