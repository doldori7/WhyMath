# 와이매스 오개념 카탈로그 v1 — 데이터 카드

> **요약**: 2022 개정 전 범위 수학 **오개념 839종**(고유 `mis_id`)을 *DB 적재 가능한 1급 카탈로그*로
> 승격하기 위한 데이터 카드. 출처는 2026-06-20 업로드 **7계층 본문 JSON**(개념 437·`fac16e6f…`). 각
> 오개념은 개념·성취기준·CCSS·distractor 규칙·교정포인트를 갖춘 **진단·피드백 1급 자산**이다. 현행
> `l4/misconception/catalog.py`(Python 상수·kebab-case ~30종·DB 비영속)의 **DB 승격 대상**.
>
> **현황(2026-06-20)**: 오개념 839 DB 승격 **B 아크 완료**(B.1 추출·B.2 테이블·B.3 로더).
> `whymath-misconception`로 839종을 `data/corpus/misconceptions_v1/`에 커밋 → `misconception_catalog`
> 테이블(mis_id PK·Alembic `c4d5e6f7a8b9`) → `l1.misconception.populate` CLI로 멱등 적재(실 PG 통합
> 839 검증). 30종 kebab 탐지 엔진·런타임 테이블과 **별개 체계**(FK 0). `concept_src_id`/`standard_code`는
> 원천 보존(개념/성취기준 해소는 후속).
>
> **추가(2026-06-23 · Phase 3 Slice 2)**: 같은 `misconception_catalog` 테이블에 **원자 백본
> ①오개념 1,837행**을 *additive* 승격(신규 테이블·마이그레이션 0·head `a8b9c0d1e2f3` 유지). 출처는
> `data/corpus/atom_graph_v1/graph.json`의 세부개념 원자(전량 `misconception` 보유). 로더
> `l1.misconception.atom_catalog`(투영) → 기존 `load_misconceptions`/`MisconceptionCatalogStore`
> 재사용(멱등 upsert)·CLI `l1.misconception.populate_atom`. 구 839와 **mis_id 네임스페이스(`ATOM:`
> 접두)·`provenance_note`('atom_graph_v1')로 분리·병존**. 상세 §6.

---

## 1. 출처·프로비넌스

| 항목 | 값 |
|---|---|
| 형태 | 7계층 본문 JSON(437개념·25MB) 내 오개념 레코드 집합 |
| 원본 sha256(앞 16) | `fcf6d333a419a222` (JSON 전체) |
| 저작 | **와이매스 자체 저작**(교수학 오개념 분석·distractor 규칙) |
| 규모 | **839**(고유 `mis_id`·예 `M0425`) |
| 추출 산출물 | `data/corpus/misconceptions_v1/{misconceptions.json, _provenance.json}` (**커밋됨** — `whymath-misconception`·Collection JSON 839) |

> 원본 JSON은 커밋하지 않는다. 진실 원천은 추출 Collection JSON(`_provenance.json`의 `source_sha256`으로 재현).

---

## 2. 스키마 (소스 키 → 모델 필드)

| 소스 키(JSON) | 모델 필드(제안) | 비고 |
|---|---|---|
| `mis_id` | **PK** `mis_id` | `M0425` 형식·839 유일 |
| `오개념` | `canonical_statement` | 오개념 서술(자체저작) |
| `학생의_잘못된_사고` | `student_wrong_thinking` | 진단 단서 |
| `distractor_규칙` | `distractor_rule` | 5축 `distractor_map`이 참조 |
| `error_type` | `error_type` | enum 후보(유형화) |
| `난이도` | `difficulty` | |
| `교정포인트` | `correction_point` | L4 코칭 피드백 |
| `매핑신뢰도`·`매핑점수`·`코드정밀도` | `mapping_confidence`·`mapping_score`·`code_precision` | 품질 메타 |
| `개념ID` | → `misconception_concept_link.concept_code` | 개념 안정키(N1·HK42·canonical) |
| `성취기준코드` | → `misconception_standard_link.norm_id` | (2022, code) 파생 |
| `매칭_CCSS` | `ccss_code` | 예 `1.NBT.A.1` |
| `학교급`·`2022_영역`·`원본_영역`·`세부단원_개념` | `school_level`·`domain`·`origin_domain`·`subunit` | 분류 메타 |
| `생성·검수` | `provenance_note` | 검수 추적성 |

**링크 2종**: `misconception_concept_link`(`mis_id`↔`concept_code`)·`misconception_standard_link`
(`mis_id`↔`norm_id`). **기존 카탈로그 정합**: `l4/misconception/catalog.py` ~30 kebab-id에 `mis_id`
별칭(또는 매핑표) 부여 — DB 승격 후에도 코드 상수 참조가 깨지지 않게(이중 id 크로스워크).

---

## 3. 라이선스·안전

| 대상 | 분류 | 처리 |
|---|---|---|
| 오개념 서술·distractor 규칙·교정포인트 | **와이매스 자체 저작** | 보존·redaction 불요 |
| `성취기준코드`·`개념ID`·`매칭_CCSS` | 공공·사실 구조 메타 | 보존(코드만·본문 X) |

> 미성년자 PII 무관(오개념은 교수학 콘텐츠·학생 데이터 아님). `licensing_safety.md` "외부 큐레이션
> 코퍼스 v3"(자체 저작) 행에 포섭.

---

## 4. 불변식 (적재 검증)
- `mis_id` **839 유일**(PK).
- 모든 오개념의 `개념ID`가 개념그래프에 실재(고아 0·`idmap` 해소) — 또는 명시적 미해소 집계(정직).
- 모든 `성취기준코드`가 norm_id로 해소(고아 0).
- 기존 kebab 카탈로그 ~30종이 839 안에 매핑(누락 surface).
- `error_type` 값 집합이 유한 enum으로 수렴(자유텍스트 잔차 0).

---

## 5. 소비처 (적재 후)
- **5축 문항 `distractor_map`**(`external_corpus_ingestion_v1.md` §5): 오답 선택지→`mis_id` 참조.
- **L4 라이브 coach**(슬108 `TRIGGERS_DISTRACTOR`·`distractor.py` op-code): distractor→오개념 진단 레일과 결선.
- **L2 오개념 매핑**(BKT/오개념 후보): 진단 증거→`mis_id` 귀속.

---

## 6. 원자 백본 출처 행 (Phase 3 Slice 2 — additive·`ATOM:` 네임스페이스)

> 로드맵 Phase 3 결정 ③("4요소→정식 콘텐츠 소스 승격")의 ①오개념 조각. 원자 백본
> (`atom_graph_v1`)의 메타 프로젝션(`atom_node`)은 ①②③ 4요소 *본문을 의도적으로 미적재*했고
> (redaction·이중 보관 금지), 이 슬라이스가 ①오개념의 **유일 승격 좌석**이다.

| 항목 | 값 |
|---|---|
| 출처 | `data/corpus/atom_graph_v1/graph.json` 세부개념 원자(level=='세부개념') |
| 규모 | **1,837**(원자 전량이 `misconception` 보유 — 초등382·중학180·고등762·대학513) |
| 적재 | `l1.misconception.atom_catalog`(투영) → 기존 `load_misconceptions` 위임·CLI `populate_atom` |
| 마이그레이션 | **무추가**(기존 테이블 재사용·head `a8b9c0d1e2f3` 유지) |

**매핑(자체 작성 필드만·날조 0)**: `mis_id`=`"ATOM:"+code`(합성·결정론·구 M-series 무충돌) ·
`canonical_statement`←`misconception` · `error_type`←`misconception_type`(6종: 개념혼동·절차오류·
정의·표기오류·과잉일반화·직관오류·역방향오류) · `concept_src_id`←원자 `code`(느슨참조·`atom_node.code`
공간) · `standard_code`←`standard_codes[0]` · `school_level`·`domain`(←`subject_area`)·`subunit` 그대로 ·
`provenance_note`=`'atom_graph_v1'`. 나머지(student_wrong_thinking·distractor_rule·correction_point·
difficulty·ccss_code·mapping_*)는 원천 미보유라 **None**(날조하지 않음).

**구 839과의 관계**: mis_id 접두(`ATOM:` vs `M####`)·`provenance_note`로 네임스페이스 분리·**additive
병존**(Phase 1이 원자를 기존 `concept`/`concept_edge`에 additive 적재한 것과 동형). 구 839
(misconceptions_v1·개념-grain)는 **Phase 5에서 폐기 예정**. K-12 437↔원자 크로스워크(concept_src_id
연결)는 Phase 4.

---

## 7. Phase 4a enrichment — `severity`·`behavior_skills` (2026-07-07·리치 Part 2)

정본 카탈로그(`misconceptions_v1`·843)에 2필드 **additive** 추가(마이그레이션 `a2b3c4d5e6f0`·
`add_column` ×2·독립 DB·preload 금지 무변경). Misconception은 이미 완성 노드라 노드 승격·거버넌스
반전 없음 — enrichment만.

| 필드 | 타입 | 의미 | 저작 방법(전량 **ai_estimated**·검수 전) |
|---|---|---|---|
| `severity` | `String(16)` nullable | 후속 학습 **손상도**(blocking/local/cosmetic·`SEVERITY_VALUES`) — 문항 난이도 `difficulty`('상/중/하')와 **별개 축·어휘 disjoint** | `error_type`→severity 교수학 규칙(coarse v1): 해석오류·조건무시·차원혼동·극값/극대극소/값좌표혼동=blocking·공식혼동·분배누락·순서오류=local·부호오류=cosmetic. error_type 없음→None |
| `behavior_skills` | `ARRAY(Text)` NOT NULL `'{}'` | **arises-in**(진단 방향) — 이 오개념이 튀어나오는 skill_id 참조 배열(skill_graph_v1·**신규 엣지 타입 0**) | 대응 개념(`concept_src_id`)의 `behavior_skills`(2b-1)를 **승계**한 시드 |

**§승계 규칙(behavior_skills·투명 문서화)**: "개념 C에 대한 오개념은 C가 exercise하는 skill 수행
중 튀어나온다"는 명시적 모델링 가정으로, 오개념의 `concept_src_id`(843/843 개념 코퍼스 조인)가 가진
2b-1 ai_estimated `behavior_skills`를 arises-in 시드로 승계한다(**자동 유도 아님** — 이미 저작된
교수학 판단의 원리적 승계). 검수로 오개념별 재판단·override된다. 커버리지: **806/843**(≥1 skill),
37은 대응 개념이 미매핑이라 `[]`(정직). cross-corpus dangling **0**(`test_misconception_enrichment_
governance`).

**분포(v1)**: severity blocking 344·local 319·cosmetic 71·None 109. behavior_skills 806/843.

**재임베딩 0**: `misconception_embedding`은 kebab 탐지 카탈로그를 `catalog_text = name_kr + canonical_
statement`로 임베딩 — 신규 2필드는 그 텍스트 밖이라 text_hash 불변(별개 체계·decoupled).

**범위 밖(각 분리·차단 사유)**: crosswalk 완주(canonical 수렴)=**Phase 4b**(AI 자기승인 금지·사람 검수
선결)·`frequency` 제외(경험적 학생 로그 필요·날조 회피)·`visual_repair` 제외(저장 viz 소비처 부재·
dead ref). **소비처 미배선**: `behavior_skills`의 런타임 진단 라우팅 소비(diagnose/distractor)는 후속
슬라이스(2b-1→2b-2 선례) — 이번은 저작·투영만.

---

**버전**: v1 (설계 전용) | **최종 수정**: 2026-07-07(Phase 4a enrichment) | 관련:
`external_corpus_ingestion_v1.md`·`concept_graph_dataset_v1.md`·`atom_graph_v1.md`·
`l4/misconception/catalog.py`
