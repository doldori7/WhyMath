# 와이매스 개념그래프 데이터셋 v1 (자체작성) — 데이터 카드

> **요약**: 한국 2022 개정 교육과정 전 범위(초등~고교 선택)를 덮는 **자체작성 개념그래프**
> 시드. 403 개념 · 541 선수엣지 · 성취기준↔CCSS 코드 매핑 · 113 암기카드 · 13 국제트랙(CCSS전용).
> 본 슬라이스(101)에서는 그중 **오개념 114건을 L4 오개념 카탈로그(22종)와 교차검증**하는 데
> 사용했다(아래 §5). 전체 적재(L1 concept_graph 파이프라인)는 후속 슬라이스 결정 사항.
>
> **2026-06-12 수정본 교체**: 사용자가 원본 입력 오류(절단된 개념명·어미 등)를 바로잡은 수정본
> xlsx로 5개 jsonl + provenance를 *전량 재생성*했다(§1 버전 이력). 개념 401→403·선수엣지
> 540→541·오개념 114→116으로 소폭 증가. §5 교차검증 수치는 *초기 업로드(06-10)* 기준의
> 슬라이스 101 산출물이며 재계산하지 않았다(아래 §5 주석 참조).

---

## 1. 출처·프로비넌스

| 항목 | 값 |
|---|---|
| 형태 | 사용자 업로드 xlsx(수정본·13 시트 중 5종 사용) |
| 업로드일 | 2026-06-12 (수정본) |
| 원본 sha256 | `062695cef261386ec880313631aa349f624fcace1b7eb3d52bc031025536f90d` |
| 저작 | 와이매스 자체작성(교수학 주석) + 공공 표준 *코드* 참조 |
| 추출 산출물 | `data/corpus/concept_graph_v1/*.jsonl` (5종) + `_provenance.json` |

> 원본 xlsx는 **커밋하지 않는다**(§3 redaction 대상 자유텍스트를 포함하므로). 진실 원천은
> redaction을 적용한 jsonl이다. 재추출이 필요하면 동일 sha256 원본을 사용자에게 재요청한다.

### 버전 이력

| 일자 | sha256 | 개념 | 선수엣지 | 비고 |
|---|---|---|---|---|
| 2026-06-10 | `1274533c…8488d1` | 401 | 540 | 최초 업로드 |
| 2026-06-12 | `062695ce…36f90d` | 403 | 541 | **수정본 전량 교체** — 절단 개념명·어미 복원 등 입력 오류 정정(원본 검수보고 시트 기준). 동일 redaction 정책(§3) 적용·재생성 |

---

## 2. 스키마 (시트 → jsonl)

| jsonl | 레코드 | 핵심 필드 |
|---|---|---|
| `concepts.jsonl` | 403 | `src_id`(G01·N1·HK01·J0105·H:…), `name_ko`, `category`, `difficulty_tier`(0~24), `standard_codes`[], `ccss_code`, `metaphor`, **`misconception`**, `accepted_expressions`, `definition_provenance`, `flashcard_count` |
| `prerequisite_edges.jsonl` | 541 | `from_id`, `from_name`, `relation`(선수), `to_id`, `to_name` |
| `standard_ccss_map.jsonl` | 403 | `src_id`, `name_ko`, `standard_code_kr`, `ccss_code` |
| `flashcards.jsonl` | 113 | `grade`(A·…), `category`, `difficulty_tier`, `src_id`, `name_ko`, `front`, `back`, `mnemonic`, `exposure_condition` |
| `ccss_only_intl.jsonl` | 13 | `node_id`, `ccss_code`, `scope`, `kr_adjacent_area`, `kr_interpretation`, `kr_absence_reason` |

> **ID 체계 주의**: 본 데이터의 `src_id`(G01·N1·HK01·J0201·H:12대수01-01 등)는 기존
> concept_graph 파이프라인의 **UC 규약**(`UC.<domain>.<topic>.<slug>`)과 *다르다*. L1 전체
> 적재 시 ID 매핑/재발급이 선행되어야 한다.

---

## 3. 라이선스·안전 (CLAUDE.md 우선순위 #2)

자체작성 교수학 주석(오개념·은유·허용표현·암기카드)과 공공 표준 *코드*(NCIC 성취기준 코드·
CCSS 코드)는 **안전**(자체 코퍼스 + 사실정보). 단, 두 자유텍스트 컬럼은 NCIC/교과서 성취기준
*본문(statement)* 을 근접 복제했을 가능성이 있어 — `concept_graph.md` §1.1 "본문은 어느 필드에도
복제하지 않는다" — **추출 산출물에서 redact**했다:

| redact 필드 | 사유 |
|---|---|
| `concepts.description`(설명) | 성취기준 본문 근접 복제 가능성. `definition_provenance`가 "설명기반 자동파생"임을 명시 → 설명이 원천 텍스트 |
| `concepts.formal_definition`(정식정의) | 교과서 정의 근접 복제 가능성(내부·학생비노출 표기) |
| `intl.ccss_statement_en`(영문 원문) | CCSS 공식 statement — 코드만 보존, 자체 `kr_interpretation`은 유지 |

> redaction 마커: 각 레코드 `_redacted_fields`. policy-guard CI(검정교과서 출판사 패턴)는 통과하나,
> 본 redaction은 그 *너머의 정책*(성취기준 본문 비복제)을 선제 적용한 것이다.

`licensing_safety.md`(한국 자원 표)에 "와이매스 개념그래프 데이터셋 v1(자체작성)" 행으로 등록.

---

## 4. 검수 상태 (적재 전 게이트)

`definition_provenance` 분포 — **289/403이 자동생성·검수필요**(수정본 기준):

| 출처 | 개수 | 적재 가능성 |
|---|---|---|
| 수기 검수 | 114 | 검수 완료 — 우선 적재 후보 |
| 자동(설명기반)·검수필요 | 197 | 전문가 검수 후 |
| 자동 초안·검수필요 | 90 | 전문가 검수 후 |
| 신규 작성(2022 신설)·검수필요 | 2 | 전문가 검수 후 |

오개념(116건)이 채워진 개념은 대부분 "수기 검수"군과 겹쳐 신뢰도가 상대적으로 높다.

---

## 5. 교차검증 — 오개념 114 ↔ L4 카탈로그 22 (본 슬라이스 산출)

> **주석(2026-06-12)**: 이 절의 수치(오개념 114·대응 12종)는 *초기 업로드(2026-06-10)* 기준
> 슬라이스 101 산출물이다. 수정본 교체(§1 버전 이력)로 오개념은 116건으로 늘었으나, §5.2 대응은
> *성취기준 코드* 기준이라 코드가 보존된 한 결론은 유효하다. 전면 재계산은 카탈로그가 30종으로
> 확장된 시점에 별도 슬라이스로 수행한다.

### 5.1 결론
- 데이터셋 오개념은 **각 성취기준 코드에 정착**(curriculum-anchored)되어 있어, 카탈로그
  항목의 *교육과정 근거*를 독립적으로 입증한다.
- 카탈로그 22종 중 **12종이 데이터셋 오개념과 (거의) 정확히 대응** → 카탈로그 정당성 확인.
- 데이터셋에는 카탈로그 미수록의 **고가치 수능·공통 오개념 다수**가 있어 후속 확장 후보가 풍부.

### 5.2 대응(corroboration) — 카탈로그 항목 ↔ 데이터셋 오개념

| 카탈로그 id | 데이터셋(성취기준) 오개념 | 일치 |
|---|---|---|
| `distribution-over-power` | [H:12대수01-03] (a+b)ⁿ≠aⁿ+bⁿ | ◎ |
| `sign-flip-in-inequality` | [J0211] 음수 곱할 때 부등호 방향 그대로 | ◎ |
| `square-root-positivity` | [J0107]·[H:12대수01-01] √(a²)=a (실제 \|a\|) | ◎ |
| `log-distribution` | [H:12대수01-04] log(a+b)=log a+log b | ◎ |
| `gambler-fallacy` | [H:12확통02-01] 앞면 5번→다음 뒷면 차례 | ◎ |
| `prosecutor-fallacy` | [H:12확통02-04] P(A\|B)=P(B\|A) | ◎ |
| `limit-equals-function-value` | [H:12미적Ⅰ01-01] 극한값=함숫값 단정 | ◎ |
| `term-to-zero-implies-convergence` | [H:12미적Ⅱ01-04] 일반항→0 ⇒ 급수 수렴(조화급수) | ◎ |
| `sine-distributes-over-sum` | [H:12미적Ⅱ02-02] sin(a+b)=sin a+sin b | ◎ |
| `dot-product-is-vector` | [H:12기하03-03] 내적 결과를 벡터로(실제 스칼라) | ◎ |
| `period-of-scaled-sine` | [H:12대수02-02] 주기·진폭 혼동 | ○(부분) |
| `similarity-vs-congruence` | [J0312]·[J0304] 닮음비·합동 | ○(부분) |

(◎ 정확 대응 / ○ 부분 대응 — 미대응: division-by-zero·exponent-zero·fraction-cancellation·
area-perimeter-confusion·mean-vs-median·invertibility·chain-rule·product-rule·
geometric-series는 데이터셋 114에 직접 진술이 없음 — 추가 검증·향후 출처 보강 대상.)

### 5.3 신호(signal) 정밀도 평가 → 진단 매칭 정교화 근거
데이터셋의 학생 표기 변이를 보면 카탈로그 `signals`(substring AND)의 두 약점이 드러난다:

1. **거짓음성(공백/표기 변이)**: 학생은 `a²+b²`·`a² + b²`·`a^2+b^2`를 섞어 쓴다. v1 substring은
   공백·유니코드에 민감 → 본 슬라이스에서 `_match_one`에 **NFKC+공백 정규화** 도입(해소).
2. **거짓양성(짧은 공통 토큰)**: `"0"`·`"다음"`·`"모든"` 등은 정답 풀이에도 흔히 등장.
   특히 substring은 *오류의 부재*를 탐지할 수 없어(예: division-by-zero는 "분모≠0" 확인한
   *정답* 풀이도 매칭) 구조적 한계가 있다. → 정본 해법은 **임베딩/LLM-judged 매칭**(doc §매칭
   알고리즘 4단계). 본 슬라이스는 *명백한* 한 건만 정밀화(`invertibility` `"모든"→"모든 함수"`)하고
   나머지 재설계는 pedagogy-designer 검토로 이관(추측 수정 금지).

### 5.4 카탈로그 확장 후보 (미수록·수능/공통 고가치) — 후속 슬라이스
[HK07] 판별식 D<0⇒"해 없음"(허근 무시) · [HK08] 근과 계수 부호 · [HK11] 정의역 제한 최대·최소 ·
[HK14] 연립부등식 교집합↔합집합 · [HK22] 원의 방정식 반지름² · [HK24] 평행이동 부호 ·
[HK35] 합성함수 f∘g=g∘f · [HK41] 순열↔조합 · [HK39] 합·곱의 법칙 · [J0220] ax²=bx 양변 나눠 근 손실 ·
[J0106] 0.999…<1 · [J0315] 피타고라스 비직각 적용 · [H:12미적Ⅰ02-02] 연속⇒미분가능 ·
[H:12미적Ⅰ03-01] 적분상수 +C 누락 · [H:12미적Ⅰ02-07] f′=0⇒극값(변곡점) ·
[H:12확통02-05] 배반↔독립 혼동 · [H:12확통03-07] 신뢰구간 95% 해석 오류.

> 각 항목은 성취기준 코드·반례 구조가 명확해 doc-first(정본 상세화→인코딩) 확장에 적합.

---

## 5b. 정형화·검증 상태 (L1 적재 아크 슬라이스 1 — 2026-06-12)

> **무저장소 슬라이스**: 데이터셋 → 정본 `Concept`/`ConceptEdge` 정형화 + 그래프 검증까지.
> Neo4j/pgvector 적재·드라이버·임베딩은 **이번 범위 밖**(후속 슬라이스 2~3). 모듈:
> `data_pipeline/concept_graph/{idmap,transform,validate}.py`, CLI `transform-v1`.

### 5b.1 src_id → UC 매핑 (`idmap.py`)

- 데이터셋 `src_id`(N1·HK01·H:12대수01-01 …)는 UC 규약(`UC.<domain>.<topic>.<slug>`)과 다르다(§2 주의).
  **결정론적 매핑** 규칙: 도메인·토픽은 첫 `standard_code`에서 파생(`parse_standard_code`+과목약칭 —
  교육과정 의미 보존), **slug는 `src_id`에서 파생**(유일성 보장).
- **충돌 해소(핵심)**: 성취기준 코드만으로 UC를 만들면 **충돌 7건**이 난다 — 여러 개념이 *같은*
  성취기준을 공유한다(예 `F7`·`F8`·`F9` → 모두 `[6수01-06]`). slug에 `src_id`를 쓰므로
  **403 src_id → 403 유일 UC(충돌 0)**. 폴백 `UC.x.misc.<slug>`(코드 없음/파싱 실패 — 실데이터 0건).
- 전문가 재명명은 `overrides`(src_id→UC) 주입으로 가능(결정론이되 교체 가능). 산출 UC는 전부
  `CONCEPT_ID_PATTERN` 통과. 매핑 테이블은 `id_map.csv`(`src_id`,`concept_id`)로 검토·인계.
- **한계(슬2 인계)**: 한글 src_id(`H:12미적Ⅰ01-01`)는 slug에서 과목한글이 소실(`h-12-01-01`)된다 —
  유일성·결정론·규약은 보존되고 `src_id`는 매핑 테이블에 보존. 가독 UC 재명명은 적재 시 override로.

### 5b.2 정형화 (`transform.py`)

| 데이터셋 | → 모델 | 비고 |
|---|---|---|
| `concepts.jsonl`(403) | `Concept`(403) | `category`→`domain`·첫 코드 학년→`grade_band_hint`·풍부필드 직결 |
| `prerequisite_edges.jsonl`(541) | `ConceptEdge`(541) | relation `선수(prereq)`→`PREREQUISITE`·UC 변환 |
| `standard_ccss_map.jsonl`(403) | — | `concept.ccss_code`로 흡수(ccss 완전 일치 검증) |
| `flashcards.jsonl`(113) | raw 패스스루 | L6 — 억지 매핑 안 함(후속) |
| `ccss_only_intl.jsonl`(13) | raw 패스스루 | 국제트랙 — 후속 |

- **풍부 필드 모델 확장**(2026-06-12 결정): `metaphor`·`accepted_expressions`·`ccss_code`·
  `misconception_text`(자유텍스트 — 카탈로그 코드 `misconception_codes`와 *별개*·코드화 후속)·
  `difficulty_tier`(0~24)·`review_status`. `name_en/ja`는 Phase 1 KR이라 Optional(None 허용·빈 문자열 금지).
- **엣지 evidence 합성**: 데이터셋 엣지엔 evidence/strength가 없는데 모델은 `evidence` 비공백·
  `strength` 필수 → `evidence="전문가 작성 개념그래프 v1"`·`evidence_source=expert_review`·`strength=0.8` 합성.
- **prerequisite 캐시**: 엣지(src=선수→dst=후행)로 각 후행 개념의 `prerequisite_concept_ids` 역채움(§2.1 조회 캐시).
- **검수 게이팅 표식**(§4): `definition_provenance`='수기 검수' → `review_status=reviewed`(114건),
  그 외 자동·검수필요 → `pending`(289건). 적재 보류 게이팅 자체는 후속 적재 슬라이스 몫.

### 5b.3 redaction 불변 (우선순위 #2)

- `description`·`formal_definition`은 **`Concept` 모델에 슬롯이 없어 구조적으로 차단**(extra='forbid') —
  정형화 코드가 *읽지도 않는다*. 전체 개념 dump·`graph.json`에 두 키 0건(테스트 단언).
- 패스스루(flashcards·intl)는 각 레코드 `_redacted_fields` 마커를 읽어 동적 제외 → intl
  `ccss_statement_en` 누수 차단(테스트가 잡은 갭 보강).

### 5b.4 검증 리포트 (`validate.py` — §5 10 invariant, 실데이터)

`transform-v1`이 정형화 직후 그래프 검증을 돌린다. **실데이터(403노드·541엣지) 결과: PASS** —

| 항목 | 결과 |
|---|---|
| error(fail) | **0** (prerequisite 사이클 없음) |
| warning | **0** (dangling 끝점·고립 노드·역방향 쌍·prerequisite 캐시 dangling·학년 단조성 역전 모두 0) |
| 구조 invariant(UC 규약·relation enum·strength 범위·evidence 비공백) | 정형화 시점(Pydantic) 강제 |
| Neo4j 멱등성(§5 #9) | N/A — 슬라이스 2(적재) |

> Phase 1은 warning을 *통과 처리*한다(§3 — 그래프 구축을 다른 자산 일정에 막지 않음). 데이터셋이
> 매우 정제돼 실데이터엔 warning도 0이나, 각 invariant는 인위적 fail 픽스처로 *위반 탐지*를 단위 검증.

### 5b.5 산출물·게이트

- CLI: `python -m data_pipeline.concept_graph transform-v1 --corpus-dir data/corpus/concept_graph_v1 [--output-dir DIR]`.
  `--output-dir` 주면 `graph.json`(개념·엣지 + raw 패스스루·redaction 유지)·`id_map.csv`(src_id→UC) 저장.
- 4게이트 통과: `ruff check .`·`black --check .`·`mypy --strict data_pipeline`·`pytest --cov`(전체 89.38%·
  271 passed/1 skip). 테스트 `tests/data_pipeline/concept_graph/{test_idmap,test_transform,test_validate,test_models,test_main_cli}.py`.

---

## 5c. Neo4j 멱등 적재 상태 (L1 적재 아크 슬라이스 2 — 2026-06-12)

> **저장소 슬라이스**: 슬1 산출 `graph.json` → 실 **Neo4j 그래프 저장소에 멱등 MERGE 적재**.
> pgvector 좌석·임베딩은 **이번 범위 밖**(슬3). 모듈: `data_pipeline/concept_graph/load.py`,
> CLI `load`, 통합 `test_load_neo4j_integration.py`.

### 5c.1 적재 모델 (`load.py`)

- **순서**(멱등·`concept_graph.md` §4 단계7): ① 제약·인덱스 DDL(§2.3) ② 노드 전량 MERGE(403·pending
  포함) ③ 엣지 MERGE(541·양끝 MATCH 후). 모두 `MERGE`라 재실행해도 노드·엣지 수 불변(§5 #9).
- **노드**: `MERGE (c:Concept {concept_id}) SET c += $props` — `concept_id`는 MERGE 키(props 제외·중복
  SET 방지)·`review_status` 등 전 속성 SET. `use_enum_values=True`라 enum은 이미 문자열. None 속성은
  제거(Neo4j null 속성 미생성).
- **엣지**: `MATCH (src)…MATCH (dst)…MERGE (src)-[r:PREREQUISITE]->(dst) SET r += $props` —
  `strength`·`evidence`·`evidence_source` 적재. **reltype 주입 차단**: Cypher 관계타입은 파라미터화
  불가 → 닫힌 `Relation` enum(7종) allowlist에서만 대문자 reltype 포맷. 데이터셋은 전 엣지 `prerequisite`
  → 전부 `PREREQUISITE` 관계.
- **검수게이팅 = 403 전량 적재 + 플래그**: pending 289도 *적재*하되 `review_status='pending'` 속성으로
  표식한다(끝점이 pending인 엣지의 고아 방지). 적재 자체는 게이팅하지 않고 **조회/후속에서** 거른다.
- **드라이버 주입 seam**: `load_graph(result, driver=…)` — 단위테스트가 FAKE 드라이버를 주입해 *실 Neo4j
  없이* 발행 Cypher를 검증한다(미설치 환경에서도 import·테스트 가능). `[postgres]`처럼 `neo4j` import는
  `connect_driver` 안에서만(지연).

### 5c.2 접속·시크릿 (우선순위 #2)

- 접속 자격은 **env 전용**: `NEO4J_URI`·`NEO4J_USER`·`NEO4J_PASSWORD`. 소스는 *env 키 이름만* 참조하고
  **시크릿 리터럴은 0**(CLAUDE.md 보안). `connect_driver`가 env 누락 시 ValueError로 안내.
- `[neo4j]` optional extra(`neo4j>=5,<6`) — 메인 deps 미오염. CLI `load`는 `find_spec("neo4j")` 사전체크로
  미설치 시 `pip install -e '.[neo4j]'` 안내.

### 5c.3 redaction 불변

- `graph.json`은 슬1 정형화에서 이미 청결(description·formal_definition 슬롯 부재)이고, 로더는 *모델 dump
  키만* 적재하므로 본문이 **구조적으로 재유입 불가**. 단위테스트가 노드 props에 두 키 0건 단언.

### 5c.4 산출물·게이트

- CLI: `python -m data_pipeline.concept_graph load --graph data/concept_graph/graph.json [--database DB]`
  (접속은 NEO4J_* env). 적재 멱등(MERGE) — 재실행 안전.
- 4게이트 통과: `ruff`·`black --check`(17파일)·`mypy --strict`(17 src)·`pytest --cov`(전체 87.96%·
  **292 passed/2 skip**). 신규 테스트 `test_load.py`(20·FAKE 드라이버)·`test_load_neo4j_integration.py`.
- **통합테스트(실 Neo4j)는 기본 SKIP** — `@pytest.mark.integration`+`WHYMATH_RUN_INTEGRATION` 게이트 +
  `importorskip("neo4j")`. **CI `data-pipeline-neo4j` 잡**(`neo4j:5` 서비스 컨테이너)·**Phaiakes9**에서
  실행: 2회 적재 → 노드 403·엣지 541 불변(§5 #9)·제약 `concept_id_unique` 존재 단언.

---

## 5d. 개념 pgvector 임베딩 적재 상태 (L1 적재 아크 슬라이스 3 — 2026-06-12)

> **저장소 슬라이스(backend)**: 슬2가 개념을 Neo4j 그래프에 적재한 뒤, 개념의 *의미 임베딩*을
> **pgvector(`concept_embedding` 테이블)에 멱등 upsert**한다. 슬1·2(`data-pipeline` 패키지)와 달리
> **backend 패키지**(`src/backend`·`whymath_backend`) 소관이다(L5 서버가 다중 저장소 운영). 슬2
> Neo4j와 *동일 UC 키*라 그래프↔벡터가 한 키로 join된다(이중 store 단일 키). 슬98 결정(벡터
> DB=pgvector·Postgres 16 통합)을 개념 자산으로 확장한 두 번째 결선(첫 결선은 L4
> `misconception_embedding`·슬105 — 이 슬라이스가 그 ORM·마이그레이션·적재기를 *개념용으로 미러링*).
> 모듈: `whymath_backend/db/models/concept_embedding.py`, alembic
> `…_concept_embedding_pgvector.py`, `whymath_backend/l1/concept_graph/{embedding,populate}.py`.

### 5d.1 ORM·마이그레이션 (`concept_embedding`)

- **PK=`concept_id`(TEXT·UC)**: 슬1 idmap 발급 Universal Concept ID = 슬2 Neo4j 노드 키와 *동일
  키 공간* → 이중 store 단일 키 join. upsert가 PK 충돌로 멱등(`ON CONFLICT(concept_id) DO UPDATE`).
- **컬럼**: `embedding pgvector vector(1024)`(`config.embedding_dim` 기본·bge-m3)·`provider`·`model`·
  `dim`·`text_hash`·`updated_at`. **원문(source_text) 컬럼 부재** — 임베딩 원문은 저장하지 않고
  *표현 해시*(`text_hash`)만 둔다(redaction 방어·중복 제거·원문은 Neo4j 노드 속성에 이미 존재).
- **마이그레이션 체인**: `down_revision=d7e8f9a0b1c2`(슬105 misconception_embedding head 위). upgrade는
  `CREATE EXTENSION IF NOT EXISTS vector`(슬105가 이미 생성·재사용·자기완결 안전) + `concept_embedding`
  테이블. **downgrade는 `vector` 확장을 드롭하지 않는다** — 슬105 `misconception_embedding`이 여전히
  `vector` 컬럼을 소유하므로(확장 소유권은 *도입* 마이그레이션[슬105]에 있음). 오프라인 SQL 검증:
  `upgrade --sql`=CREATE EXTENSION+CREATE TABLE·`downgrade --sql`=DROP TABLE만·`heads`=단일 head.
- **HNSW/IVFFlat 인덱스 없음**: misconception_embedding과 동일 — 401+ 규모는 seq-scan 정합(스케일
  코퍼스는 fixed-dim + HNSW cosine 인덱스가 정석·후속·이 테이블은 *영속화 + 의미검색 groundwork*).

### 5d.2 임베딩 텍스트 — 안전 필드만 (redaction·우선순위 #2)

- **임베딩 입력 = `name_ko` + `metaphor` + `accepted_expressions`**(자체 작성 안전 필드·`". "` join).
  L4 `catalog_text`의 개념판. `concept_embedding_text(...)`는 **`description`·`formal_definition`을
  인자로 받지도 않는다**(시그니처 부재=구조적 차단). graph.json엔 본디 두 키가 없고(슬1 모델 슬롯
  부재·`_provenance.json` redacted), 있더라도 로더가 *읽지 않는다*(이중 방어). 교과서 본문 0.
- 안전 필드가 전부 빈 개념은 적재에서 제외(빈 벡터 방지).

### 5d.3 적재기·provider 재사용 (신규 seam 0)

- **입력 원천 = 슬1 산출 `graph.json`**(UC 키·정제). `load_concepts_from_graph_json`이 `concepts`
  배열에서 UC `concept_id` + 안전 필드만 읽어 `(concept_id, 표현)` 목록을 만든다(flashcards_raw·
  intl_raw 등 그래프 외 자산은 읽지 않음).
- **임베딩 provider seam 재사용**(신규 금지·CLAUDE.md 로컬 우선): L4 `misconception/semantic/provider`
  (`build_provider`·`FakeEmbeddingProvider`·local bge-m3·OpenAI)·`text_hash`·`_provider_model_identity`를
  그대로 import한다(같은 임베딩 공간 규약·Fake 주입·지연 로드). `ConceptEmbeddingIndex`(sync psycopg
  lazy 엔진·upsert/search)는 `PgVectorIndex`를 개념 테이블용으로 미러링.
- **멱등 upsert**: `populate_concept_embeddings`가 표현을 배치 1회 임베딩해 UC 키로 upsert(재실행 시
  갱신). **403 전량 적재**(review_status 무관 — 임베딩은 의미검색용·게이팅은 *조회* 몫).
- 자격증명 0 하드코딩(OpenAI 키 등 env 전용·SecretStr)·로컬 provider 우선(비용).

### 5d.4 산출물·게이트

- CLI: `WHYMATH_VECTOR_STORE=pgvector python -m whymath_backend.l1.concept_graph.populate
  --graph data/concept_graph/graph.json`(env 접속·pgvector 모드 전용). 적재 멱등 — 재실행 안전.
- 4게이트 통과(`cd src/backend`): `ruff check .`·`black --check .`(149파일)·`mypy --strict
  whymath_backend`(128 src)·`pytest --cov`(전체 **96.19%**·**2408 passed/85 skip**). 신규 테스트
  `test_concept_embedding.py`(24·Fake provider·가짜 엔진)·`test_concept_embedding_integration.py`(5).
- **통합테스트(실 PG+pgvector)는 기본 SKIP** — `@pytest.mark.integration`+`WHYMATH_RUN_INTEGRATION`
  게이트 + PG 미도달 graceful skip. **CI 신규 잡 불요** — 기존 **`backend — 마이그레이션·통합 (실 PG)`
  잡**(`pgvector/pgvector:pg16` 서비스)이 `alembic upgrade head`(→`concept_embedding` 생성)·
  `downgrade base→upgrade head` 왕복 후 `pytest -m integration --ignore=l3`로 이 통합테스트를 자동
  수집·실행한다(upsert→search 라운드트립·멱등·provider/model 필터·dim 일치·UC 키). **Phaiakes9**에서도 실행.

---

## 5e. 개념 의미검색 조회 좌석 + backend search API (L1 적재 아크 슬라이스 4 — 2026-06-12)

> **조회 슬라이스(backend)**: 슬3이 개념 임베딩을 pgvector(`concept_embedding`)에 *적재*한 뒤,
> 슬4는 그 적재 임베딩을 *조회 가능*하게 만든다 — 슬3 `ConceptEmbeddingIndex.search`를 백킹
> 프리미티브로 한 **검색 좌석 + HTTP 엔드포인트**. 슬3 `search` docstring이 예고한 "조회 좌석이
> 생기면 그 타입으로 흡수한다"의 그 좌석이다. 모듈: `whymath_backend/l1/concept_graph/retrieval.py`,
> `whymath_backend/api/concepts.py`(search 엔드포인트 추가).

### 5e.1 검색 좌석 (`search_concepts`·L1 데이터 서빙)

- **흐름**: `search_concepts(query_text, *, top_k, provider, index=None, settings=None)` → ① provider로
  query_text 임베딩(1건) ② `ConceptEmbeddingIndex.search(vector, top_k)`로 코사인 상위 top_k ③
  `ConceptSearchHit(concept_id, similarity)` 랭킹 반환(유사도 내림차순). 임계값 필터 없음(순수 랭킹·
  점수 컷은 소비처 몫).
- **반환 타입 = `concept_id + similarity`만**(name_ko 등 enrichment 미포함). 사유: `concept_embedding.
  concept_id`는 **UC 키**(슬2 Neo4j 노드 키와 동일 공간)인데 backend PG `concept` 테이블은 **UUID PK
  + `code`**라 *UC 컬럼이 없다*(다른 키 공간). UC↔PG/Neo4j 메타 브리지는 *별도 설계 결정*이라 풍부
  메타 enrichment는 **후속 슬라이스**(backend↔Neo4j 결합·무거운 프로젝션 금지).
- **provider seam 재사용**(신규 0): 적재(슬3)와 *같은* `_provider_model_identity`(provider→model 규약)·
  `ConceptEmbeddingIndex`를 쓴다 — 같은 임베딩 공간 행만 봐야 적재 결과가 잡힌다. provider·index 주입
  가능(테스트 격리·Fake).
- **memory 모드 graceful**(조용한 무동작 금지): `vector_store != pgvector`면 영속 store 부재로 적재가
  불가능했으므로 **빈 리스트**를 돌려준다(예외·None 아님·embed도 생략). 호출자가 명시 신호로 표면화.

### 5e.2 HTTP 엔드포인트 (`GET /v1/concepts/search`·L5 API 표면)

- **계약**: `GET /v1/concepts/search?q=<질의>&k=<1~50>` → `{query, results:[{concept_id, similarity}],
  vector_store_enabled}`. q 필수·비공백(min_length=1)·max_length=500·k 범위 → 위반 시 422(기존 list
  엔드포인트 Query 제약 패턴 미러). 라우트는 `/{concept_id}`(UUID)보다 *먼저* 선언해 "search"가 UUID로
  파싱되지 않게 한다.
- **블로킹 격리**: 검색 좌석은 sync(블로킹 임베딩 + sync psycopg)라 `asyncio.to_thread`로 워커
  스레드에서 돌린다(이벤트 루프 보호·coach `_compute_matches` 패턴 미러).
- **노출 계약**(CLAUDE.md): *학생 직접 노출 아닌* 조회 좌석 — L2(약개념 추천)·L4(오개념↔개념 연결)·
  교사 도구가 *소비*(그 소비 로직은 후속). 반환은 UC concept_id + 코사인 점수뿐(본문 0·우열 매기기·
  정답 빠르게 등 금기 표현 0). memory 모드면 `vector_store_enabled=false` + 빈 results로 *명시* 안내.
- provider는 `build_provider`(좌석 팩토리·신규 0) 의존성으로 주입 — 테스트는 `dependency_overrides`로
  Fake 주입(라이브 0·모델 로드 0).

### 5e.3 명시적 범위 밖 (후속 슬라이스)

- **enrichment**(name_ko 외 전체 속성·Neo4j traversal): backend 메타 접근 방식(Neo4j 연결 vs PG UC
  프로젝션)이 *별도 설계 결정*이라 후속(§5e.1 키 공간 차이).
- **검수 게이팅**(reviewed 우선 노출): `review_status`가 backend에서 조회되려면 위 메타 접근 결정
  선행. 적재는 전량+플래그 완료(§5d).
- **L2/L4 결선**(약개념 추천·오개념 자동 연결): 좌석만 제공·L2/L4가 *호출*하는 건 후속(7계층 — L1은
  조회 서빙·역방향 의존 금지).

### 5e.4 산출물·게이트

- 4게이트 통과(`cd src/backend`): `ruff check .`·`black --check .`·`mypy --strict whymath_backend`·
  `pytest --cov`(70%+). 신규 테스트: `test_concept_retrieval.py`(좌석 단위·11·Fake provider+엔진)·
  `test_concepts_search.py`(엔드포인트 단위·9·TestClient+DI override)·`test_concept_retrieval_
  integration.py`(populate→search 라운드트립·실 PG 게이트).
- **통합테스트(실 PG+pgvector)는 기본 SKIP** — `@pytest.mark.integration`+`WHYMATH_RUN_INTEGRATION`
  게이트 + PG 미도달 graceful skip. **CI 신규 잡 불요** — 기존 **`backend — 마이그레이션·통합 (실 PG)`
  잡**이 `pytest -m integration --ignore=l3`로 `tests/backend/l1/`를 자동 수집·실행. **Phaiakes9**에서도 실행.

---

## 6. 향후 활용

1. **L1 개념그래프 적재**(대형·진행 중): src_id→UC 매핑 · 스키마 확장(CCSS·은유·허용표현) ·
   541 선수엣지→`prerequisite` 엣지 · 검수 표식(reviewed 114·pending 289)은 **슬라이스 1에서
   완료**(§5b·무저장소 transform·검증) · **Neo4j 멱등 적재는 슬라이스 2에서 완료**(§5c·403 노드·541
   엣지·MERGE 멱등·env 접속) · **개념 pgvector 임베딩 적재는 슬라이스 3에서 완료**(§5d·UC 키 이중
   store·name_ko+metaphor+accepted 임베딩·멱등 upsert·backend 패키지) · **개념 의미검색 조회 좌석 +
   backend search API는 슬라이스 4에서 완료**(§5e·`search_concepts`·`GET /v1/concepts/search`·UC
   concept_id+similarity 반환). **후속(슬5+)**: 메타 enrichment(name_ko 외·Neo4j traversal·UC↔PG 브리지
   설계 결정 선행) · L2/L4 결선(약개념 추천·오개념↔개념 자동 연결) · 검수 게이팅 *조회* 정책(reviewed
   우선 노출·적재는 전량+플래그 완료).
2. **L4 오개념 확장**(후속): §5.4 후보를 doc-first로 카탈로그에 추가(30종+ 목표).
3. **암기카드**(L6): 113장 — `exposure_condition`("이해 마스터 후 노출")이 메타인지 정책과 정합.
