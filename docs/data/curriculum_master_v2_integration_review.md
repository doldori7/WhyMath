# 기반 DB v2 통합 검토 — 성취기준·개념그래프 마스터 + 문제뱅크 + 콘텐츠 명세

> **L1 데이터 기반 설계 문서.** 2026-06-16 Kiki가 업로드한 3종 기반 자료(성취기준·개념그래프
> 통합 마스터, 문제뱅크 확보범위 v2, 대상별 콘텐츠 설계 명세 v2)를 **기존 코드베이스와 대조**하여
> 무엇이 *추가/변경/수정*됐는지 정리하고, 정합을 위한 **단계별 시스템 변경**을 설계한다.
>
> 본 문서는 *검토·설계 단계* 산출물이다. 실제 스키마·코드 변경은 본 설계 승인 후 별도 슬라이스로
> 진행한다(아래 §5 단계). 근거 결정 로그: `MEMORY.md` 2026-06-16 "기반 DB v2 통합 검토".

---

## 0. 입력 자료와 확정 방향

### 0.1 업로드 3종
| # | 파일(약칭) | 정체 | 역할 |
|---|---|---|---|
| File A | `…20222015….xlsx` | 수학과 교육과정 성취기준 **통합 노드 + 개념그래프 마스터** (2022개정 기준 + 2015개정 병행) | L1 성취기준·개념·관계의 정본 데이터 |
| File B | `…260616…v2.xlsx` | **문제뱅크 확보범위 설계 보완본 v2** | 문항 수량 산정 + **5축 메타스키마**(문항 메타데이터 컬럼) |
| md | `…260616….md` | **대상별 이론 콘텐츠 완전 설계 명세 v2** | 7트랙·5계층 콘텐츠 설계 + 컴플라이언스 |

### 0.2 확정 방향 (2026-06-16 Kiki 결정)
1. **산출물** = 검토 리포트 + 단계별 실행계획(본 문서). 코드 변경은 승인 후 별도.
2. **concept_id 정본** = `ELEM-GEO-001` 계열(`{트랙}-{영역}-{3자리}`) **채택** → 기존 `UC.*`에서 마이그레이션.
3. **성취기준 범위** = 전체 **895**(2022:435 + 2015:460) 듀얼커리큘럼, `norm_id` 정규화키 도입.

---

## 1. 현황 대조 — "이미 반영" vs "신규"

**핵심 발견: File A의 개념그래프 부분은 이미 적재되어 있다.** 2026-06-12 슬라이스에서 File A의 수정본
xlsx로 `data/corpus/concept_graph_v1/*.jsonl` 5종이 생성됐고(데이터 카드 `concept_graph_dataset_v1.md`),
개념 403·선수엣지 541·CCSS 403·암기카드 113·국제트랙 13으로 **수량이 정확히 일치**한다.

| File A 시트 | 행수 | 코드베이스 현황 | 분류 |
|---|---|---|---|
| 개념 | 403 | `concepts.jsonl` (적재) — `src_id`(N1·HK42) → `idmap.py`로 `UC.*` 변환 | **이미 반영** |
| 선수엣지 | 541 | `prerequisite_edges.jsonl` (적재·DAG 비순환) | **이미 반영** |
| 개념-성취기준-CCSS | 403 | `standard_ccss_map.jsonl` (적재) | **이미 반영** |
| 암기카드(목록화) | 113 | `flashcards.jsonl` (적재) | **이미 반영** |
| 한국미수록_CCSS전용(국제트랙) | 13 | `ccss_only_intl.jsonl` (적재) | **이미 반영** |
| **성취기준_목록** | **895** | repo에 성취기준 **독립 테이블 없음** (현재 `concepts.jsonl`에 코드 문자열로만 임베드) | **신규** |
| **연결_개념-성취기준** | **443** | 관계테이블·`연결구분`(직접/재매핑/준용) 없음 | **신규** |
| **공식_성취기준_마스터** | **435** | `official_code`+`norm_id` 2층 키 구조 없음 | **신규** |
| 노드_트리구조 / 노드_계층표 / 개정_적용연도 | 1737 / 895 / — | 표시·참조용 (현재 없음) | **신규(보조)** |

> File A 품질 검증(시트 `품질_기준_검증`, 검증일 2026-06-12): 고유성·완전성·참조무결성·일관성·유효성·
> 추적성 6대 기준 전수 통과. 즉 **신규 적재 시 데이터 위험이 낮다**.

### 1.1 기존 자산 요약(대조 대상)
- **개념 스키마**: `schemas/v1.1/concept.schema.yaml` — PK `concept_id` = `UC.<domain>.<topic>.<slug>`,
  "한 번 발급하면 변경 금지". `name_ko/en/ja`·`prerequisite_concept_ids`(엣지 캐시)·`misconception_codes`·
  `standard_codes`(NCIC FK).
- **개념 엣지**: `schemas/v1.1/edge.schema.yaml` — 6관계(prerequisite·generalization·specialization·
  contrast·application·composition)·`evidence` 필수.
- **다국 매트릭스**: `schemas/v1.1/curriculum_entry.schema.yaml` — `(concept_id, country_code)` 복합키,
  30필드. **이미 CCSS(US)·IMO 열과 라이선스 매트릭스(KR-NCIC·US-CCSS·INT-IMO) 보유**. 한국 열 =
  NCIC 성취기준 파생.
- **성취기준 모델**: `src/data-pipeline/data_pipeline/ncic/models.py` — `AchievementStandard`,
  **PK=`code`**(`[9수01-01]`), `curriculum_revision` 기본 "2022 개정"(2015은 미적재), `STANDARD_CODE_PATTERN`.
- **개념그래프 파이프라인**: `src/data-pipeline/data_pipeline/concept_graph/{idmap,transform,validate,load}.py`,
  백엔드 투영 `src/backend/whymath_backend/l1/concept_graph/`.
- **문항 모델**: `src/backend/whymath_backend/schema/problem.py` — UUID PK, **난이도 5축**(계산·해석·
  케이스·시각·융합)·`irt_difficulty_b`·`signature_patterns`(10종)·`persona_fit`(5종)·저작권 `source_type`
  게이트(평가원·EBS·교과서는 본문 null). MEMORY.md엔 본 895/5668 자산 **미기록**.

---

## 2. 검토 — 추가 (신규 데이터·엔티티)

- **성취기준 마스터(895, 듀얼커리큘럼)**: 2022:435 + 2015:460. 현재 성취기준이 독립 1급 엔티티로
  존재하지 않음 → 신규 테이블. 2026년 현재 **고3·중3은 2015개정 적용 중**(File A `개정_적용연도`)이라
  2015 수록은 *실사용 필요*이지 참고용이 아님.
- **공식_성취기준_마스터(2층 키)**: `official_code`(고시 원문·화면/인용용·비유일) / `norm_id`(개정_과목_
  영역_일련, 예 `2022_2수_01_01`·DB 조인/중복검사용). File A는 이미 둘을 분리해 제공.
- **개념↔성취기준 관계(443, `연결구분`)**: `직접`/`재매핑`(고1 공통 `[10수학]`→`[10공수]` 41건)/
  `준용`(기본수학1·2 ← 공통수학 대응 개념). 현재는 개념에 코드 리스트로만 임베드 → 출처(직접/재매핑/준용)
  손실. 관계테이블화로 *왜 이 개념이 이 성취기준에 붙는지* 추적 가능.
- **CCSS·국제트랙 정합 연결**: corpus에 CCSS 매핑·국제트랙 13이 *적재돼 있으나*
  `curriculum_entry`(US/IMO 열)와 **연결되지 않음** → 매핑 작업으로 다국 매트릭스에 흡수.
- **재수 유형카드(`RT-…`)·영재 정리(`OLY-…`)**: File B/md의 별도 산정단위(시그니처 유형 101종·핵심
  정리 56개·루브릭 채점). 기존에 **없는 엔티티 유형**(개념·성취기준과 평행한 학습단위).
- **5계층 콘텐츠 모듈(L1 HOOK~L5 META)·암기카드 노출조건**: md가 정의하는 콘텐츠 흐름 단위. 현재
  콘텐츠 엔티티 미존재(`LearningScene` DSL은 별개 렌더 계층).

---

## 3. 검토 — 변경 (기존 구조 마이그레이션)

- **concept_id 체계 전환** `UC.<영역>.<주제>.<슬러그>` → `{트랙}-{영역}-{3자리}`.
  `concept.schema.yaml`의 "한 번 발급하면 변경 금지" 원칙을 **의도적으로 깨는 breaking change**.
  영향: `concept`·`edge`·`curriculum_entry`·`textbook_mapping` 스키마의 `concept_id` 키 공간, `idmap.py`,
  Neo4j 적재, pgvector 투영, `problem` FK. → **별칭 보존·재적재 필수**(§4-1).
- **성취기준 PK 전환** 단일 `code` → `norm_id`(또는 복합키 `(개정, code)`). **2015 추가 시 `code`가 두
  교육과정 간 153건 중복**되어 현 PK가 붕괴(File A `읽기_안내` 명시: "코드 단독…중복이므로 [PK로] 금지").
- **문항 `concept_id` FK**: 기존 UC 키 공간 → 신규 ELEM-GEO 키 공간으로 갱신.
- **개념의 `standard_codes`**: 임베드 리스트 → 관계테이블(§2)의 *캐시*로 역할 재정의
  (`prerequisite_concept_ids`가 엣지의 캐시인 것과 동일 패턴).

---

## 4. 검토 — 수정 (오류 정정)

File A `검수보고`·md `변경 요약`이 명시한 정정. **대부분 2026-06-12 적재 corpus에 이미 반영**으로 보이나,
적재 파이프라인에서 **전수 재검증** 항목으로 둔다.

- 성취기준 코드 정정: 일차함수 `[9수03-02]`(도형과 측정) → **`[9수02-XX]`(변화와 관계)** — 영역번호 오류.
- 곱셈 도입 학년 정합: `[4수01-04]`(3~4학년군) → 개념 도입은 **2학년 `[2수01-06/07]`** 계열.
- 행렬 신규 개념 **HK42(행렬의 뜻과 표현)·HK43(행렬의 연산)** — `정의출처=신규 작성·검수필요`(품질 한계 4건).
- 개념명 **어미복원 31건**(고등 선택과목 절단 문장 복원), **중복 엣지 1건 제거**(HK34→H:12경수04-01).
- 알려진 한계: 기본수학2 유리·무리함수 수식 2건 일반 표기로 복원(고시 원문 대조 권장).

---

## 5. 시스템 변경 설계 (정합)

### 5-1. concept_id 마이그레이션 — `{트랙}-{영역}-{3자리}` [최우선·breaking]
> **결정적 주의**: "ELEM-GEO-001 채택"은 **ID 포맷 채택**이지 *File B의 435개 빈 placeholder 채택이
> 아니다.* File B `개념노드_마스터`(435행)는 성취기준당 1개 자동생성이며 `소단원명·선수개념`이 공란이다.
> 반면 **기존 403 개념 그래프는 선수엣지·오개념·CCSS·암기카드를 갖춘 더 풍부한 자산**이다. 따라서 기존
> 그래프를 *재ID*하고 File B의 435는 *커버리지 체크리스트*로만 쓴다.

1. **정본 ID 포맷 확정**: `TRACK` + `AREA` + `NNN`(3자리). `TRACK`={`ELEM`,`MID`,`HIGH`(또는
   `HIGH-BASIC`/`HIGH-GENERAL`/`HIGH-CAREER`),`RT`(재수),`OLY`(영재)}. `AREA`=영역 코드표(§7 결정).
2. **기존 403 개념 재ID**: 각 개념의 학교급·영역·순서로 신규 ID **결정적 생성**. 기존 `UC.*`와 원본
   `src_id`(N1·HK42)는 `aliases`/`source_id`로 **보존**(추적성·롤백·idmap 역호환).
3. **File B 435 = 커버리지 체크리스트**: 2022 성취기준 전건이 ≥1 개념으로 연결되는지 검사(고아 성취기준
   0). File B 공란(소단원명·선수개념)은 기존 그래프에서 **채워** 역수출.
4. **연쇄 갱신**: `concept`·`edge`·`curriculum_entry`·`textbook_mapping` 스키마의 `concept_id` 패턴/정규식,
   `idmap.py`, Neo4j 재적재, pgvector 투영(`l1/concept_graph/node_projection.py`), `problem.concept_id` FK.

### 5-2. 성취기준 마스터 — 듀얼커리큘럼 + `norm_id` PK
- **신규 엔티티/테이블** `achievement_standard`(또는 `AchievementStandard` 확장): **PK=`norm_id`**
  (`2022_2수_01_01`), `official_code`(고시 원문·비유일), `curriculum_revision`(2022/2015 판별자) 분리 —
  File A 2층 키를 그대로 채택.
- `ncic/models.py` 확장: `GradeBand`·`subject` enum에 **2015개정 학년군·과목**(중학교 수학, 수학Ⅰ·Ⅱ,
  미적분, 확률과 통계 등) 추가, `STANDARD_CODE_PATTERN`에 2015 변형 수용, `code`→`official_code`로 의미
  전환(유일성 제약 제거).
- **적재 파이프라인**: File A `성취기준_목록`·`공식_성취기준_마스터` → 검증(품질 6기준 재현) → 저장.
  공공누리 1유형 `SOURCE_CITATION` 의무 유지(기존 패턴 재사용).

### 5-3. 개념↔성취기준 관계테이블 (`연결구분`)
- **신규 관계 엔티티**: `(concept_id, norm_id, link_type)`, `link_type ∈ {직접, 재매핑, 준용}`.
  재매핑·준용 출처를 보존해 2015→2022 이행 의미를 유지. `concept.standard_codes`는 이 관계의 캐시로 강등.

### 5-4. 문항 5축 메타 확장 (`problem.py`)
> **용어 충돌 주의(충돌 아님·병합)**: 기존 `problem.py`의 "5축"은 **난이도 5축**(계산·해석·케이스·시각·
> 융합)이고, File B의 "5축"은 **메타 5축**(계층·성격·내용·양적·질적)이다. 서로 다른 축이므로 *병합*한다.

| File B 메타필드 | 기존 problem.py | 조치 |
|---|---|---|
| `item_id` / `concept_id` / `achievement_std` | `problem_id` / `unit_codes`·N:M / 문자열 | FK를 신규 키 공간으로 정렬 |
| `bloom_level`(기억~창안 6단계) | 없음 | **신규**(계층축) |
| `difficulty`(1-5) / `irt_b` | `difficulty_overall` / `irt_difficulty_b` | 매핑(존재) |
| `irt_a` / `discrimination_D` | 없음 | **신규**(변별 모수·운영 변별도) |
| `item_type` 10종(MC/MC-D/SA/FB/MN/GR/ST/PF/EX/RT) | `question_format` 4종(객/단답/합답/서술) | **확대** |
| `distractor_map`(오답→오개념코드) | `choices`·`common_mistakes`(간접) | **신규**(§5-5 카탈로그 연동) |
| `domain` / `subunit` | `subject`·`unit_codes`만 | **신규/세분** |
| `target_seconds` / `session_position` | `expected_solve_seconds` / 없음 | 매핑 / **신규** |
| `scoring_type`(정오답/진단/부분점수/시간/루브릭) / `feedback_id` | `answer_format`·`points`(간접) / 없음 | **신규**(질적축) |
- **기존 강점 유지**: 난이도 5축·`signature_patterns`·`persona_fit`·저작권 `source_type` 게이트는 그대로.

### 5-5. 오개념 코드 카탈로그 형식화
- 현재 오개념은 `concepts.jsonl` 자유텍스트 + L4 카탈로그(30종·`l4/misconception`). md의 `M-LIN-xx` 류
  **안정 코드**를 부여해 `distractor_map`이 참조할 1급 카탈로그로 승격. `concept.misconception_codes`와 정합.
- 기존 L4 자산(슬108 `TRIGGERS_DISTRACTOR` 어휘·`distractor.py` op-code 카탈로그)과 연결 — distractor→
  misconception 진단 레일이 이미 일부 존재.

### 5-6. 로드맵 항목 (Phase 1 고1 이후 — 설계만)
- **재수 유형카드·영재 정리** 엔티티: 별도 ID 네임스페이스(`RT-…`/`OLY-…`)·루브릭 채점(CAT 대신 탐구풀).
- **5계층 콘텐츠 모듈** 스키마(`content_module`): L1 HOOK~L5 META, 트랙별 비중(md §1).
- **컴플라이언스**(md §10): 만14세 미만 보호자 동의(개인정보보호법 §22-2)·Apple Kids(제3자 분석 SDK 금지
  → **자체 학습분석**)·접근성(색약 안전·TTS·스크린리더). L5/auth·학습분석 파이프라인 영향.
- **7트랙 ↔ 5페르소나 축 정리**: 트랙=교육과정 레벨(초/중/고3트랙/재수/영재), 페르소나=시장 세그먼트
  (`problem.py persona_fit` A~E). **직교 축**이므로 둘 다 유지·혼동 금지.

---

## 6. 영향 받는 핵심 파일
- **스키마**: `schemas/v1.1/{concept,edge,curriculum_entry,problem,textbook_mapping}.schema.yaml`,
  `schemas/v1.0/schema_v1.0.md`
- **성취기준**: `src/data-pipeline/data_pipeline/ncic/models.py` (+신규 적재기)
- **개념그래프 파이프라인**: `src/data-pipeline/data_pipeline/concept_graph/{idmap,transform,validate,load}.py`
- **백엔드 L1**: `src/backend/whymath_backend/l1/concept_graph/{node_projection,embedding,retrieval}.py`
- **문항 모델**: `src/backend/whymath_backend/schema/{problem.py,enums.py}`
- **데이터·카드**: `data/corpus/concept_graph_v1/*`, `docs/data/{concept_graph_dataset_v1,curriculum_matrix,
  licensing_safety,ncic_scheme}.md`, `docs/architecture/01_data_foundation.md`
- **결정 로그**: `MEMORY.md`, `ROADMAP.md`

---

## 7. 단계 제안 + 결정 필요 잔여 사항

### 7.1 단계(우선순위)
| Phase | 내용 | 위험/근거 |
|---|---|---|
| **P0(본 문서)** | 검토·설계 문서 + MEMORY 결정로그 + 데이터카드 노트 | 코드 무변경 |
| **P1** | 성취기준 마스터(895 듀얼·`norm_id`) 적재 + 관계테이블(443) | 데이터 검증완료·공공누리 → 저위험 |
| **P2** | concept_id 마이그레이션(UC.*→ELEM-GEO·별칭보존·Neo4j 재적재) | **breaking**·테스트 동반 필수 |
| **P3** | `problem.py` 5축 메타 확장 + 오개념 코드 카탈로그 | 하위호환 필드 추가 |
| **P4(로드맵)** | 재수/영재 엔티티·5계층 콘텐츠·컴플라이언스 | Phase 1 이후 |

> Phase 1 운영 범위(고1)는 유지. 단 성취기준 마스터·개념 재ID는 **전 학년 공통 기반**이라 P1·P2에서
> 전건 처리(고1만 부분 적재 시 키 공간이 두 번 바뀌어 더 비쌈).

### 7.2 구현 단계에서 확정할 잔여 결정
- **AREA 코드 어휘**: File B는 광역 4영역(GEO/CHG/…), md는 토픽 단위(MUL/LINFUNC/LIMIT). **권장**=광역
  영역(결정적·충돌 없음) + 토픽은 `subunit`에. (불일치 surface — 구현 시 1택)
- **고등 3트랙 prefix**: `HIGH` 단일 vs `HIGH-BASIC/GENERAL/CAREER` 분리.
- **성취기준 PK**: `norm_id` 단일 vs 복합키 `(개정, code)`. **권장** `norm_id`(단일 컬럼 FK 편의).

---

## 8. 검증 방법
- **데이터 정합(P1/P2)**: ① 성취기준 895=2022:435+2015:460, `norm_id` 유일·`official_code` 153중복 허용,
  ② 모든 문항·관계의 `concept_id`가 신규 그래프에 실재(**고아 0**), ③ 선수엣지 DAG 비순환 유지(541),
  ④ File B 435 성취기준 전건이 ≥1 개념 커버 — pytest invariant(기존 `concept_graph/validate.py` 패턴 재사용).
- **마이그레이션 무손실**: `UC.*`↔신규ID 양방향 크로스워크 round-trip 동일성, Neo4j 노드/엣지 수 불변.
- **회귀**: 4게이트(ruff·black·mypy·pytest) green, 기존 `problem` 스키마 테스트 통과(필드 추가는 옵셔널·
  하위호환).

---

## 부록 — 출처·프로비넌스
- 입력: 2026-06-16 Kiki 업로드 3종(File A·B·md). File A 품질검증 6기준 전수통과(2026-06-12).
- 기존 적재: `concept_graph_dataset_v1.md`(corpus v1, 2026-06-12 수정본).
- 라이선스: NCIC 성취기준 = 공공누리 1유형(상업·가공 OK·출처표시). CCSS = CCSSO/NGA 조건부. 상세
  `docs/data/licensing_safety.md`.
- 결정 로그: `MEMORY.md` 2026-06-16.
