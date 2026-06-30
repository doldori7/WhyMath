# Math DSL 부채 교정 — 설계(고위험 항목)

> **상태**: 설계(design) · **계층**: 횡단(L1·L3·L4) · **작성일**: 2026-06-30
> **정본 상위**: `math_dsl_risk_register.md`(부채 분석). 본 문서는 그 부채 중 *고위험·선행조건
> 미정* 항목의 **설계만** 담는다(구현은 별 슬라이스·별 `/plan`).
> **동반 구현(이미 반영)**: cycle 방어선(populate/load)·교육과정 grade/semester 노드 제거는
> 같은 변경분에서 *구현 완료*. 본 문서는 *남은* 고위험 항목의 청사진이다.

---

## 0. 이번에 구현된 것(맥락) vs 설계로 남긴 것

| 부채 | 처리 | 근거 |
|---|---|---|
| cycle 검출(populate/load 방어선) | **구현 완료** | 저위험·기존 탐지기 미러 |
| 교육과정 `grade_introduced`·`semester_introduced` 제거 | **구현 완료** | NULL·중복·소비처 0 |
| 교육과정 `curriculum_version`·`subject` 완전 Overlay 이관 | **구현 완료**(§3) — 두 필드 제거(PR #350) + `curriculum_entry` KR 적재기 완료 | 런타임 소비처 0 확인·Overlay 단일 진실 |
| 오개념 ID 통합(kebab 30 ↔ M-id 839) | **골격 구현**(§1) — M-id 로더·crosswalk 테이블·read-time resolver 완료. 잔여 = 매핑 큐레이션·게이트 배선 | rekey는 resolver로 불필요화(채택) |
| 파서(동치 권위) 일원화 | **구현 완료**(§2) — 경계 명문화 + golden test | `notation_contract.md`·`data/notation_contract.json` |

> **정정(2026-06-30)**: 초안(v0.1)은 M-id 로더를 "없음(스키마만)"이라 했으나 *오보*다 —
> `l1/misconception/catalog_loader.py`(+`populate` CLI·`atom_catalog`·단위/통합 테스트·alembic
> `c4d5e6f7a8b9`)로 **이미 구현·적재 가능**하다. 따라서 오개념 ID 통합의 "1단계 로더"는 완료 상태이며
> 잔여는 §1.3의 ②crosswalk·④학생데이터 rekey다. 파서 항목(§2)은 본 슬라이스로 *경계 명문화 +
> golden test*까지 구현 완료(`notation_contract.md`).

---

## 1. 오개념 ID 통합 (최고위험)

### 1.1 현재(부채)
- **kebab 30종**(`l4/misconception/catalog.py` 하드코딩) = *런타임 탐지·개입 정본*. 44+ 파일이
  `CATALOG_BY_ID`에 강결합(진단·judge·distractor·probe·learning_scene·wh1_loop 게이트).
- **M-id 839종**(`schema/misconception_catalog.py`·`data/corpus/misconceptions_v1/`) = *콘텐츠
  카탈로그*. **로더 구현 완료**(`l1/misconception/catalog_loader.py`·`populate` CLI·alembic
  `c4d5e6f7a8b9`·단위/통합 테스트) — `misconception_catalog` 테이블에 멱등 적재 가능. (API 노출은 후속.)
- 둘 사이 **crosswalk 부재·FK 없음**. 런타임 테이블(`misconception_hypothesis`·`evidence_link`·
  `misconception_embedding`)은 kebab `misconception_id`를 **TEXT 느슨참조**로 보유.
- 개념노드 `common_misconceptions`(JSONB 자유서술)는 또 다른 표현(런타임 경로 미사용·`05a` RS2).

### 1.2 목표 불변식 (math_dsl_risk_register.md Q10-⑥)
오개념 = **단일 canonical 정체성**·독립 그래프·reactive 로드. 표현 1개당 진실 id 1개.

### 1.3 단계 슬라이스 (제안)
1. ✅ **M-id 로더 + ORM 적재**(완료·저위험·런타임 무영향) — `misconceptions_v1` 839 →
   `misconception_catalog` 테이블(`l1/misconception/catalog_loader.py`). kebab 경로 불변.
2. 🟡 **crosswalk 골격**(완료) — kebab ↔ M-id 매핑 테이블 `misconception_crosslink`
   (`db/models/misconception_crosslink.py`·`concept_standard_link` 패턴·`link_id` UUID PK·`mis_id`
   실 FK·의미 유일키 `(kebab_id, mis_id, link_type)`)·로더(`l1/misconception/crosslink_loader.py`)·
   **read-time resolver**(`crosslink_resolve.py`·kebab→M-id 조회)·alembic `e2f3a4b5c6d7`. **실제 매핑
   데이터·게이트 배선은 잔여**(아래). `confidence`·`method`로 근거를 남기되 채택은 사람 검수.
   *(완료)* **검수 초안** `docs/data/misconception_crosslink_candidates.md`(30종 후보·근거·신뢰도).
   *(완료)* **후보 자동생성 도구** `l1/misconception/crosslink_candidates.py`
   (`propose_crosslink_candidates`·kebab×M-id 임베딩 코사인·검수 artifact 출력·자동 적재 차단).
   신호 정정: kebab엔 standard_code·error_type 부재 → 주신호 = 임베딩 코사인(domain은 메모만).
   *(잔여)* **매핑 채택·적재** — 검수자가 승인분만 `"crosslinks"` JSON으로 옮겨 `crosslink_loader`
   적재(자동 커밋 금지·오도 코칭 차단).
3. **canonical id 선정 + 게이트 공존**(잔여) — 신규 노출은 M-id canonical·kebab은 런타임 탐지 키로
   잔존(crosswalk로 항상 매핑). 게이트(`learning_scene.py`·`wh1_loop.py`·`evidence_store.py`)는
   **두 체계 공존 분기**로 확장 — *노출 전 측정*(`04b` shadow→canary).
4. **학생 데이터 마이그레이션** *(불필요화·결정)* — 런타임 테이블은 kebab `misconception_id`를
   TEXT(FK 아님)로 보존하므로 **read-time resolver로 rekey 없이** M-id 해석 가능(채택). 물리 일괄
   재키잉(option b)은 미성년 PII·되돌리기 위험으로 **비채택**(우선순위 #1·#2). 1:N 매핑 시 confidence
   상위 우선·다중 표시(리포트 계층 결정).

### 1.4 리스크
- 강결합 44+ 파일 → 점진·공존 전제(빅뱅 금지). 각 슬라이스는 *측정 후 노출*(`04b` shadow→canary 패턴 재사용).
- crosswalk 거짓매핑 = 오도된 코칭(우선순위 #1·#3) → 사람 승인·confidence 게이트 필수.

---

## 2. 파서(동치 권위) 일원화

### 2.1 현재(부채)
- **SymPy**(`l3/verify_step.py`·`l3/verify_answer.py`) = *동치·검산 판정 권위*(단계 동치·수치 검산).
- **mathjs**(`src/web/graphing-calculator/src/lib/graph2dSpec.js`) = 그래프 렌더용 표기 변환
  (`**`→`^`·`toTex`). **동치 판정은 하지 않음**(렌더 전용).
- 부채는 "엔진 중복"이 아니라 **표기 계약 부재** — 두 파서가 implicit multiplication·`^`/`**`·
  유니코드 기호를 다르게 해석하면 *같은 식이 다르게 보이는* drift가 가능.

### 2.2 목표 불변식 (Q10-⑦)
**동치 권위는 SymPy 단일**. mathjs는 *렌더 전용*이며 정오·동치 판정에 절대 관여하지 않는다.

### 2.3 설계
1. **경계 명문화**(문서·코드 주석) — `graph2dSpec.js`에 "동치/정오 판정 금지·표기 변환만" 불변
   주석. 동치가 필요한 어떤 흐름도 SymPy(L3)를 거친다.
2. **표기 계약(golden test)** — py(SymPy 정규화)↔js(mathjs 파싱) 동일 입력 집합(implicit mult,
   `^`/`**`, 음의 부호, 유니코드 `²`·`π`)에 대해 *동일 정규 표기*를 산출하는지 교차검증하는
   golden fixture. CI 양쪽 잡에서 같은 fixture를 읽어 drift를 잡는다.
3. **비목표** — 브라우저에서 SymPy 실행(불가·과설계)·mathjs를 SymPy로 대체(렌더 성능 손실).

---

## 3. 교육과정 `curriculum_version`·`subject` 완전 Overlay 이관 (구현 완료)

### 3.1 결과
`grade_introduced`·`semester_introduced`(rev d1e2f3a4b5c6)에 이어 `curriculum_version`·`subject`도
**제거 완료(PR #350·rev f3a4b5c6d7e8)**. 조사 결과 두 필드의 *런타임 READ/필터 소비처가 0*이었고
(교육과정 정합 게이팅은 전부 `Problem.curriculum_version` 사용·Concept과 독립), `idx_concept_level
(level, subject)`도 활용 쿼리가 없어 `(level)`로 축소했다. 즉 "소비 경로 재설계 동반"이라던 초안
가정은 *과대평가*였고 단순 제거가 안전했다(enum `subject_enum`·`curriculum_enum`은 Problem이 계속
사용하므로 타입만 보존·컬럼만 drop).

### 3.2 Overlay 적재기 (이번 슬라이스)
교육과정 분류의 단일 진실은 `curriculum_entry` Overlay다. 그 **KR 적재기를 구현**했다
(`l1/curriculum/curriculum_loader.py`·`populate.py` CLI):
- **소스**: `graph.json` 개념 중심 직접 매핑(개념당 1 KR 셀·concept_id 정합). `domain`→`domain_label`·
  `grade_band_hint`→`grade_band`/`introduced_grade`(밴드 하한)·`standard_codes`→
  `national_standard_codes`·`review_status`→`confidence`. KR 상수(country=KR·license=KR-NCIC·
  revision="2022 개정"·source_url=NCIC)는 graph.json `source_citation`에서 정직 도출(공공누리 1유형).
- **멱등**: `entry_id`(=`{concept_id}:KR`) PK 충돌 ON CONFLICT DO UPDATE — `created_at` 보존·
  `updated_at` 갱신. concept_id는 FK 아닌 느슨참조라 개념 선적재 비의존(독립 적재).
- **범위**: Phase 1 KR만(US는 ccss_code뿐 표준 코퍼스 없음·IMO 코퍼스 없음). `required_depth` 등
  소스에 신호 없는 필드는 None(날조 금지).
- **잔여(후속)**: US/IMO 열·`required_depth` 큐레이션·L6 자동 커리큘럼 정렬 소비 배선.

---

## 참고
- 정본 상위: `math_dsl_risk_register.md`·`math_dsl_principles_review.md`
- 구현 좌석: `l4/misconception/`(kebab)·`schema/misconception_catalog.py`(M-id)·`l3/verify_step.py`·
  `l3/verify_answer.py`·`src/web/graphing-calculator/src/lib/graph2dSpec.js`·`schema/curriculum_entry.py`·
  `l1/curriculum/curriculum_loader.py`(KR Overlay 적재기)
- 패턴: `04b_misconception_judge_graduation.md`(shadow→canary→full 점진 노출)
- 원칙: `CLAUDE.md`(의사결정 우선순위 1·2·3·미성년 PII)
- 변경 이력: v0.1 (2026-06-30 초안 — 설계만) · v0.2 (2026-06-30 — §3 구현 완료: 필드 제거 PR #350 +
  curriculum_entry KR 적재기)
