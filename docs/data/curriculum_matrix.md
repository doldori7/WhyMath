# 데이터셋: 다국 커리큘럼 매트릭스 (Multi-Curriculum Matrix)

> **L1 구조화 자산.** 같은 수학 개념이 나라마다 *몇 학년에·어떤 깊이로* 다뤄지는지
> 교차표로 정리. **기존 NCIC 성취기준(`ncic.md`)이 이 매트릭스의 "한국 열"이다** —
> 매트릭스는 NCIC를 버리는 게 아니라 국제 비교 축에 끼워 넣는 구조.

---

## 1. 메타데이터

| 항목 | 값 |
|---|---|
| 정식 명칭 | WhyMath 다국 커리큘럼 매트릭스 (Multi-Curriculum Matrix) |
| 자산 성격 | **자체 구축 자산** — 국가별 공개 교육과정 표준의 구조화·교차표화 |
| 라이선스 | **WhyMath 자체 자산** (국가별 원천 자원 라이선스는 §3 참조) |
| 상업 활용 | 허용 — 단, 국가별 원천 자원의 출처 표시 의무 전이 (§3) |
| 저장소 | PostgreSQL (3차원을 정규화 테이블로) / Phase 2+ 결정 |
| 데이터 카드 작성일 | 2026-05-14 |
| 다음 검토일 | Phase 1 종료 시점 (2026-11) |
| 목표 규모 | **5,000~6,000셀** (개념 × 국가 × CurriculumEntry) |
| Phase 1 범위 | **한국 + 참고용 미국·IMO만** (3개 축) |
| Phase 3 범위 | **9~12개국 풀스케일** — Phase 1 과욕 판단으로 재배치 |
| 근거 결정 로그 | `MEMORY.md` 2026-05-14 "MathScope PRD v1.1 채택" — 신규 자산 10번, PRD 허점 ② |

### 1.1 Phase 배치 — 왜 Phase 1은 3개 축뿐인가

PRD 본문은 §1.6과 §15.1에서 국가 수가 불일치했다(`MEMORY.md` PRD 허점 ②).
9~12개국 풀스케일을 Phase 1에 넣으면:
- 각 국가 교육과정 원문 확보·해석·라이선스 검토가 9~12배.
- 첫 진입이 *고1 내신*인데(`MEMORY.md` 2026-05-13) 9개국 비교는 MVP에 불필요.

→ **Phase 1 = 한국(주축) + 미국 Common Core·IMO 신택터스(참고 열) 2개.**
9~12개국은 Phase 3 영재·B2B 단계에서 본격화. 이 카드의 스키마는 풀스케일을
미리 수용하도록 설계하되, *데이터*는 Phase 1 범위만 채운다.

---

## 2. 스키마

> 3차원: **개념(Universal Concept ID) × 국가 × `CurriculumEntry`(30필드)**.
> 엔티티 필드 명세의 정본은 `schemas/v1.1/`. 아래는 데이터 카드 관점 요약.

### 2.1 3차원 구조

```
Universal Concept ID  ─┐
                       ├─→  CurriculumEntry (한 (개념, 국가) 쌍의 셀)
국가 코드 (ISO 3166-1) ─┘
```

- **Universal Concept ID**: 개념 그래프(`concept_graph.md`)의 `concept_id`와
  **동일 키 공간**. 두 자산이 같은 개념을 다른 ID로 부르면 정합 붕괴 — 키
  공유가 강제 사항. 형식 `WM-C-<domain약칭>-<순번4자리>`.
- **국가 코드**: ISO 3166-1 alpha-2 (`KR`·`US`·`JP`·`GB` 등). IMO는 국가가
  아니므로 의사 코드 `IMO` 사용 (국제 올림피아드 신택터스).
- **CurriculumEntry**: (개념, 국가) 한 쌍에 대한 30필드 레코드. 셀이 비어 있을
  수 있다(그 나라 교육과정에 그 개념이 없음) — `is_present: false`로 표시.

### 2.2 `CurriculumEntry` 30필드 (그룹별 요약)

| 그룹 | 대표 필드 | 설명 |
|---|---|---|
| 식별 | `concept_id`, `country_code`, `entry_id` | 셀 PK는 (`concept_id`,`country_code`) |
| 출처 | `source_name`, `source_code`, `source_url`, `source_document`, `license_id` | 국가별 교육과정 표준 출처 (§3) |
| 시점 | `introduced_grade`, `grade_band`, `effective_from`, `curriculum_revision` | 도입 학년·학년군·시행 |
| 맥락 | `introduced_context`, `domain_label`, `sub_domain_label` | 어떤 맥락/단원에서 처음 등장 |
| 깊이 | `required_depth`, `cognitive_level`, `is_assessed`, `assessment_format` | 요구 깊이·인지 수준·평가 형식 |
| 표기 | `notation_local`, `terminology_local`, `notation_variants` | 그 나라의 표기·용어 |
| 위계 | `prerequisite_concept_ids`, `followup_concept_ids` | 그 나라 교육과정 내 선수·후속 |
| 매핑 | `national_standard_codes`, `textbook_unit_refs` | 국가 표준 코드·교과서 단원 참조 |
| 상태 | `is_present`, `confidence`, `verified_by`, `created_at`, `updated_at` | 셀 존재 여부·신뢰도·검수자 |

> 정확히 30개 필드의 1:1 명세는 `schemas/v1.1/curriculum_entry.yaml`이 정본.
> 위는 *그룹 단위 요약* — 카드는 구조를 설명하고, 스키마는 필드를 확정한다.

### 2.3 한국 열 = NCIC 성취기준

```
KR 국가의 CurriculumEntry  ←─  ncic.md 의 AchievementStandard 에서 파생
```

- `national_standard_codes` ← NCIC 성취기준 코드(`[10공수1-01-01]` 등)
- `source_name` = "2022 개정 교육과정 — 수학과 교육과정"
- `source_code` = "교육부 고시 제2022-33호 [별책 8]"
- `license_id` = `KR-NCIC` (§3 라이선스 매트릭스)
- `domain_label`·`grade_band`·`introduced_grade` ← NCIC 데이터에서 직접 매핑

**기존 NCIC 크롤러가 출발점이다.** `src/data-pipeline/data_pipeline/ncic/`가
산출하는 `standards.json`을 입력으로 한국 열의 `CurriculumEntry`를 생성하는
변환기를 추가하는 것 — *새 한국 크롤러를 만드는 게 아니다*
(`01_data_foundation.md` "기존 크롤러가 출발점").

### 2.4 셀 데이터 모델 (Pydantic — Phase 1 시그니처)

`src/data-pipeline/data_pipeline/curriculum_matrix/models.py` (미구현):

```python
class CurriculumEntry(BaseModel):
    concept_id: str                          # Universal Concept ID
    country_code: str                        # ISO 3166-1 alpha-2 또는 'IMO'
    is_present: bool                         # 그 나라 교육과정에 존재하는가
    source_name: str
    source_url: str                          # 출처 의무 — 비면 ValidationError
    license_id: str                          # §3 매트릭스 키
    introduced_grade: int | None
    grade_band: str | None
    required_depth: str | None               # enum: 'awareness'|'procedural'|'conceptual'|'mastery'
    national_standard_codes: list[str] = []
    confidence: float                        # 0.0~1.0
    # ... schemas/v1.1/curriculum_entry.yaml 의 30필드 전체
```

`is_present=True`인데 `source_url`이 비면 검증 실패 — 존재한다고 주장하려면
근거 출처가 있어야 한다(§5).

---

## 3. 국가별 원천 자원 라이선스

> `licensing_safety.md` 매트릭스를 *국가 축으로 확장*. NCIC만 기존 매트릭스에
> 있었으므로, 미국·일본·영국 등은 이 카드가 1차 기록처다 — 추후
> `licensing_safety.md`에 "다국 커리큘럼" 절로 역반영 필요(§7).

| `license_id` | 국가 | 원천 | 라이선스 성격 | 상업 OK | 가공 OK | 출처 표시 | Phase |
|---|---|---|---|---|---|---|---|
| `KR-NCIC` | 한국 | 2022 개정 교육과정 (교육부 고시 제2022-33호 별책 8) | 공공누리 1유형 | ✅ | ✅ | ✅ 필수 | **P1 주축** |
| `US-CCSS` | 미국 | Common Core State Standards (수학) | 정부 표준 — CCSSO/NGA, 출처 표시·비변형 배포 조건 | ⚠️ 조건부 | ⚠️ | ✅ 필수 | **P1 참고** |
| `INT-IMO` | 국제 | IMO 신택터스(출제 범위 관례) | 공식 표준 문서 부재 — *관례의 정리* | ✅ (자체 정리물) | ✅ | 출처 명시 | **P1 참고** |
| `JP-MEXT` | 일본 | 学習指導要領 (文部科学省) | 정부 고시 — 사실정보, 본문 인용은 범위 준수 | ⚠️ | ⚠️ | ✅ 필수 | P3 |
| `GB-NC` | 영국 | National Curriculum (mathematics) | Open Government Licence (OGL) v3.0 — CC BY 호환 | ✅ | ✅ | ✅ 필수 | P3 |
| (이하 P3 국가) | 싱가포르·핀란드·독일·프랑스·호주·중국 등 | 각국 교육과정 표준 | **국가별 확인 필요** — Phase 3 착수 시 개별 카드 갱신 | — | — | — | P3 |

### 3.1 라이선스 처리 원칙

- **각 셀(`CurriculumEntry`)에 `license_id`를 박는다.** 매트릭스를 노출·라이선싱할
  때 어느 셀이 어떤 의무를 지는지 셀 단위로 추적 가능해야 한다.
- 미국 CCSS는 "정부 표준"이나 *무제한 자유*가 아니다 — CCSSO/NGA의 사용 조건
  (출처 표시, 표준 문구 비변형 재배포 등)을 따른다. Phase 1에서 미국 열을
  채우기 전 조건 재확인이 가공 단계 1번(§4).
- **국가 교육과정의 "본문"과 "구조"를 구분한다.** 매트릭스가 담는 건 *구조*
  (몇 학년에·어떤 깊이로)와 *표준 코드*이지, 교육과정 해설 본문 전체가 아니다.
  `ncic.md`가 성취기준 본문(`statement`)을 담는 건 공공누리 1유형이 *변형·상업
  허용*이기 때문 — 다른 나라는 라이선스가 다르므로 `statement` 상당 텍스트의
  수집 범위를 `license_id`별로 다르게 잡는다.
- 라이선스 미확인 국가는 **셀을 만들지 않는다** (`licensing_safety.md` 결정
  트리 "명시 X → 사용 안 함이 기본").

### 3.2 IMO 열의 특수성

IMO는 정부도 아니고 공식 "교육과정"도 없다. `INT-IMO` 열은 *올림피아드 출제
관례를 WhyMath가 정리한 자체 정리물*이다. 따라서:
- 출처는 특정 문서가 아니라 "IMO 기출 분석 + 통용 신택터스"로 기록.
- 이 열의 셀은 `confidence`를 보수적으로(≤0.7) — 관례는 표준만큼 확정적이지 않다.

---

## 4. 가공 단계 (data-engineer 9단계 워크플로우 적용)

| 단계 | 모듈 / 산출 | 책임 |
|---|---|---|
| 1. 라이선스 확인 | 본 카드 §3 + `licensing_safety.md` | 국가별 `license_id` 확정, 미국 CCSS 조건 재확인 |
| 2. 데이터 카드 | 이 문서 | 본 .md |
| 3. 수집 | 한국: NCIC `standards.json` 재사용 / 미국·IMO: 공개 표준 문서 | 국가별 원천 확보 |
| 4. 정제 | `clean.py` | 학년 표기 통일(국가별 학제 차이 → `introduced_grade` 정수 정규화), 표기 정규화 |
| 5. 정형화 | `transform.py` | 원천 → `CurriculumEntry`(30필드). 한국은 `AchievementStandard`→`CurriculumEntry` 변환기 |
| 6. 검증 | `validate.py` + great_expectations | 키 공간 정합·출처 의무·`is_present` 일관성 (§5) |
| 7. 저장 | `load.py` | JSON(개념×국가 중첩) + CSV(평탄화 셀 목록) + sidecar (Phase 1) |
| 8. 사람 검수 | 수동 | 셀 5% 이상 — 학년·깊이 매핑이 원천과 일치하는가 (§5) |
| 9. MEMORY.md | 수동 | Phase 1 3개 축 채움 결과 기록 |

### 4.1 학제 차이 정규화

국가마다 학제가 다르다(미국 K-12, 한국 초6·중3·고3, 일본 6·3·3). `introduced_grade`를
*국가 내 학년 정수*로 저장하되, 비교를 위해 `grade_band`에 WhyMath 공통
학년대(개념 그래프 `grade_band_hint`와 정렬)를 병기한다. 비교 축의 통일은
clean 단계의 핵심 책임 — 매핑 테이블은 `curriculum_matrix/transform.py`의
`_GRADE_NORMALIZER` dict, 국가 추가 시 *이 dict만* 갱신.

---

## 5. 검증 (great_expectations + 사람 검수)

### 5.1 기계 검증

| Invariant | 검증 방법 |
|---|---|
| `concept_id`가 개념 그래프 노드에 실재 (키 공간 정합) | cross-dataset 참조 검사 |
| `country_code`가 ISO 3166-1 또는 `IMO` | `expect_column_values_to_be_in_set` |
| (`concept_id`,`country_code`) 셀 중복 없음 | 복합키 유일성 검사 |
| `is_present=True`이면 `source_url` 비어있지 않음 | 커스텀 expectation |
| `license_id`가 §3 매트릭스에 정의된 값 | `expect_column_values_to_be_in_set` |
| `confidence` ∈ [0.0, 1.0] | `expect_column_values_to_be_between` |
| `INT-IMO` 열의 `confidence` ≤ 0.7 | 커스텀 expectation (§3.2) |
| `required_depth`가 4종 enum | `expect_column_values_to_be_in_set` |
| 한국 열 `national_standard_codes`가 NCIC `standards.json`에 실재 | cross-dataset 참조 검사 |
| Phase 1 산출물에 `KR`·`US`·`IMO` 외 국가 코드 없음 | 범위 가드 (§1.1) |

### 5.2 사람 검수

- 셀 5% 이상을 검수 — `introduced_grade`·`required_depth`가 그 나라 교육과정
  원문과 *실제로* 일치하는가. 기계는 형식만 본다.
- 한국 열은 NCIC 카드(`ncic.md`)의 검수와 *중복 검수하지 않되*, NCIC→
  `CurriculumEntry` *변환의 정확성*만 표본 확인.
- 미국 CCSS 열은 표준 코드↔학년 매핑이 CCSS 원문과 일치하는지 검수.

---

## 6. 실행 절차 (Phase 1)

### 6.1 환경 구성

`ncic.md` §6.1 가상환경 재사용. 추가 의존성 없음(표준 라이브러리 + pandas +
great_expectations).

### 6.2 빌드

```bash
# 프로젝트 루트에서 — 한국 열은 NCIC 산출물을 입력으로 받음 (Phase 1 시그니처)
python -m data_pipeline.curriculum_matrix build \
  --ncic-standards data/ncic/standards.json \
  --countries KR,US,IMO \
  --output-dir data/curriculum_matrix/
```

출력(예정):
- `data/curriculum_matrix/matrix.json` — 개념×국가 중첩 구조
- `data/curriculum_matrix/cells.csv` — 평탄화한 셀 목록 (분석용)
- `data/curriculum_matrix/matrix.meta.json` — 국가별 `license_id`·출처 sidecar

### 6.3 사람 검수 (필수 — 단계 8)

체크리스트:
- [ ] 한국 열 셀이 NCIC 성취기준에서 정확히 파생됐는가 (학년·영역·코드)
- [ ] 미국 CCSS 열의 학년 매핑이 CCSS 원문과 일치하는가
- [ ] `concept_id`가 개념 그래프와 같은 ID를 쓰는가 (키 공간 정합)
- [ ] `is_present=False` 셀이 "정말 없음"인지 "아직 안 채움"인지 명확한가
- [ ] Phase 1 산출물에 P3 국가가 섞여 들어오지 않았는가

---

## 7. Phase 2+ 후속 작업 (이번 작업 범위 외)

- [ ] `licensing_safety.md`에 "다국 커리큘럼" 절 신설 — 본 카드 §3 매트릭스 역반영
- [ ] Phase 3: 일본·영국·싱가포르 등으로 9~12개국 풀스케일 확장 (국가별 라이선스
      개별 카드 갱신 선행)
- [ ] PostgreSQL 정규화 스키마 확정 + Alembic 마이그레이션 (3차원 → 테이블)
- [ ] 개념 그래프 `concept_id` ↔ 매트릭스 Universal Concept ID 자동 정합 CI
- [ ] L6 자동 커리큘럼 정렬 엔진이 매트릭스를 소비하는 인터페이스 정의
- [ ] 국가 간 "깊이 격차" 분석 뷰 (영재 트랙·B2B 라이선싱 자산화)
