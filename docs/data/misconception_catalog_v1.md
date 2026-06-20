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

**버전**: v1 (설계 전용) | **최종 수정**: 2026-06-20 | 관련: `external_corpus_ingestion_v1.md`·
`concept_graph_dataset_v1.md`·`l4/misconception/catalog.py`
