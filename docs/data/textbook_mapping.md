# 데이터셋: 교과서 매핑 자산 (Textbook Mapping)

> **L1 구조화 레이어.** 검정 교과서의 *구조*를 다국 커리큘럼 매트릭스
> (`docs/data/curriculum_matrix.md`)의 개념과 NCIC 성취기준(`docs/data/ncic.md`)에
> 연결한다. **저작권 안전선이 이 카드의 핵심이다 — 구조 메타데이터만 사용,
> 본문·문제·풀이·그림 일절 미사용.**
>
> **상태: 미구축.** 이 카드는 *목표 명세*다. Phase 1은 미래엔·천재 2종 ×
> 고1 단원 파일럿만 착수한다.

---

## 1. 메타데이터

| 항목 | 값 |
|---|---|
| 정식 명칭 | WhyMath 교과서 매핑 자산 (Textbook Mapping) |
| PRD 출처 | MathScope PRD v1.1 신규 자산 11번 (`MEMORY.md` 2026-05-14 결정 로그) |
| 자산 성격 | **자체 구축 매핑 자산** — 교과서 *구조*만 수집, 본문 비수집 |
| 1차 입력 | 출판사 공식 목차(사실정보), 도서관 서지 메타데이터, NCIC 성취기준 코드 |
| 라이선스 | 구조 메타데이터 = **사실정보**(저작권 보호 대상 아님) / 매핑 구조 = **WhyMath 자체 자산** |
| 상업 활용 | 허용 — **단, 4절 저작권 정책 절대 준수 전제** |
| 저장소 | PostgreSQL 16 (교과서 메타 + 단원 트리 + 매핑) — Phase 2 배포 |
| 데이터 카드 작성일 | 2026-05-14 |
| 다음 검토일 | Phase 1 종료 시점 (2026-11) |
| 목표 규모 | **한국 9종 × 8과목 ≈ 5,000~7,000 매핑** (Phase 2~3 도달 목표) |
| Phase 1 범위 | **미래엔·천재교육 2종 × 고1 단원** 파일럿 (첫 진입 = 고1 내신 트랙 정렬) |
| 연관 안전선 | `CLAUDE.md` 절대 금기 "검정 교과서 본문·예제 복제 금지" / `docs/data/licensing_safety.md` |

### 1.1 이 자산이 위험한 이유 — 그래서 카드의 핵심이 4절

검정 교과서는 `licensing_safety.md` 매트릭스에서 **본문 = ❌ 절대 금지**,
**목차 = ✅ 사실정보**로 갈린다. 교과서 매핑은 *그 경계선 바로 위에서 작업*한다.
한 발만 잘못 디디면 `CLAUDE.md` 최상위 금기를 위반한다.

따라서 이 카드는 스키마(2절)보다 **저작권 정책(4절)이 사실상의 본체**다.
**4절을 어기는 매핑은 만들지 않는다 — 규모 목표보다 4절이 우선이다.**

---

## 2. 스키마

> 엔티티 필드 명세의 정본은 `schemas/v1.1/` (PRD v1.1 9개 엔티티 명세). 아래는
> 데이터 카드용 요약. **모든 필드는 4절 안전선을 통과한 "구조 메타데이터"만 담는다.**

### 2.1 `TextbookMapping` 엔티티 (Pydantic — Phase 1 운영 모델)

`src/data-pipeline/data_pipeline/textbook_mapping/models.py` (미구현 — 시그니처만):

```python
class TextbookMapping(BaseModel):
    # --- 교과서 메타데이터 (서지 = 사실정보) ---
    isbn: str                          # PK. 13자리 ISBN
    publisher: str                     # '미래엔' | '천재교육' | '비상교육' ...
    book_title: str                    # '고등학교 수학' (서명 = 사실정보)
    authors: list[str]                  # 저자 표시 (사실정보)
    subject: str                       # 8과목 중 하나 (NCIC 과목 체계와 정렬)
    grade: int                         # 10·11·12 (고1~3) | 7·8·9 (중1~3)
    revision_year: int                 # 교과서 개정 연도
    curriculum_revision: str = "2022 개정"

    # --- 단원 트리 (목차 = 사실정보) ---
    unit_tree: list["TextbookUnit"]    # 대단원→중단원→소단원 트리

    # --- 톤 프로필 (WhyMath 자체 분석물 — 4.4절) ---
    tone_profile: "TextbookToneProfile"

    # --- 출처·격리 메타 ---
    source_urls: list[str]             # 목차 출처 (출판사 사이트·도서관 메타데이터)
    isolation_tag: str                 # 4.5절 즉시 격리용 태그 (출판사+ISBN 단위)
    legal_review_status: Literal["not_required", "pending", "cleared"]


class TextbookUnit(BaseModel):
    unit_id: str
    parent_unit_id: str | None         # 트리 구조 (대→중→소단원)
    unit_number: str                   # '1-2' 등 (사실정보)
    unit_title: str                    # 단원명 — 사실정보, 본문 아님
    page_range: str | None             # '12-35' — 페이지 *번호*일 뿐, *내용* 아님
    standard_codes: list[str]          # 매핑된 NCIC 성취기준 코드 (truth source 연결)
    concept_ids: list[str]             # 매트릭스·그래프 Universal Concept ID — 다대다 (2.2절)
    learning_objective_text: str | None  # 4.3절 — 변호사 검토 전엔 None 고정


class TextbookToneProfile(BaseModel):
    formality_level: str               # 서술 격식 수준 (WhyMath 자체 라벨)
    notation_preferences: list[str]    # 선호 표기 경향 (라벨)
    sequencing_style: str              # 단원 배열 스타일 (라벨)
    # 본문 텍스트는 일절 담지 않음 — 분류 라벨·범주값만 (4.4절)
```

### 2.2 매트릭스 개념과의 다대다 매핑

```
TextbookUnit  ──< N:M >──  Universal Concept ID   (curriculum_matrix.md / concept_graph.md)
              ──< N:M >──  NCIC 성취기준 코드        (ncic.md — 매칭 타겟)
```

- 한 단원이 여러 개념을 다루고(N), 한 개념이 여러 교과서의 여러 단원에 흩어진다(M).
- `concept_ids`는 개념 그래프(`concept_graph.md`)·다국 매트릭스
  (`curriculum_matrix.md`)와 **같은 Universal Concept ID 키 공간**(`UC.<domain>.<topic>.<slug>`)을
  쓴다. 키가 어긋나면 join이 깨진다 — 키 공유는 강제 사항.
- `standard_codes`는 `ncic.md`의 성취기준 코드를 가리킨다 — **교과서 매핑의
  매칭 타겟이 NCIC 성취기준**이다(`01_data_foundation.md` 자산 연결도).

### 2.3 무엇이 들어가고 무엇이 안 들어가는가

| 필드 | 들어감? | 근거 |
|---|---|---|
| ISBN·출판사·서명·저자·개정연도 | ✅ | 서지 정보 = 사실정보 |
| 단원 번호·단원명·차시명 | ✅ | 목차 = 사실정보 (`licensing_safety.md` "단원명만") |
| 페이지 범위 | ✅ | 페이지 *번호*일 뿐, 페이지 *내용*이 아님 |
| 학습 순서 | ✅ | 단원 배열 = 사실정보 |
| NCIC 코드·개념 ID 매핑 | ✅ | WhyMath가 만든 연결 = 자체 자산 |
| 톤 프로필 (분류 라벨) | ✅ | 본문이 아닌 *분류 라벨* (4.4절) |
| 학습목표 텍스트 | ⚠️ 보류 | 4.3절 — 변호사 검토 전까지 `None` 고정 |
| 본문·개념 설명·서술 | ❌ | `CLAUDE.md` 절대 금기 |
| 예제·연습문제·단원평가 | ❌ | 자체 코퍼스 동등 문제로 대체 (4.2절) |
| 풀이·해설 | ❌ | 일절 복제 안 함 |
| 그림·그래프·도표·삽화 | ❌ | 일절 복제 안 함 |
| 폰트·디자인·레이아웃 | ❌ | 일절 복제 안 함 |

### 2.4 SQL DDL (Phase 2+ — 미배포)

```sql
CREATE TABLE textbook_mappings (
    isbn                 VARCHAR(20) PRIMARY KEY,
    publisher            VARCHAR(50)  NOT NULL,
    book_title           VARCHAR(200) NOT NULL,
    authors              VARCHAR(100)[],
    subject              VARCHAR(50)  NOT NULL,
    grade                INTEGER      NOT NULL,
    revision_year        INTEGER      NOT NULL,
    curriculum_revision  VARCHAR(20)  DEFAULT '2022 개정',
    tone_profile         JSONB,
    source_urls          TEXT[]       NOT NULL,
    isolation_tag        VARCHAR(80)  NOT NULL,   -- 4.5절 격리 단위
    legal_review_status  VARCHAR(20)  NOT NULL DEFAULT 'not_required',
    created_at           TIMESTAMPTZ  DEFAULT now()
);

CREATE TABLE textbook_units (
    unit_id              VARCHAR(40) PRIMARY KEY,
    isbn                 VARCHAR(20)  NOT NULL REFERENCES textbook_mappings(isbn)
                                      ON DELETE CASCADE,   -- 4.5절 격리 시 단원 동반 삭제
    parent_unit_id       VARCHAR(40)  REFERENCES textbook_units(unit_id),
    unit_number          VARCHAR(20)  NOT NULL,
    unit_title           VARCHAR(200) NOT NULL,
    page_range           VARCHAR(20),
    standard_codes       VARCHAR(20)[],
    concept_ids          VARCHAR(80)[],
    learning_objective_text TEXT       -- 4.3절 — 변호사 검토 전 NULL 강제
);
CREATE INDEX idx_units_isbn       ON textbook_units(isbn);
CREATE INDEX idx_units_standards  ON textbook_units USING GIN (standard_codes);
CREATE INDEX idx_units_concepts   ON textbook_units USING GIN (concept_ids);
CREATE INDEX idx_mappings_isolation ON textbook_mappings(isolation_tag);
```

`ON DELETE CASCADE` + `isolation_tag` 인덱스는 4.5절 "즉시 격리·삭제 가능한
구조"를 DB 레벨에서 보장하기 위한 설계다.

---

## 3. 대상 교과서 (시장 점유율 추정)

> 기존 스텁 카드의 13종 목록을 흡수. PRD v1.1 자산 11번은 **한국 9종 × 8과목**을
> 목표 규모로 명시 — 아래 목록에서 우선순위 9종을 추린다.

**중학교** (2022 개정 검정):
- 천재교육·비상교육·미래엔·금성·동아·신사고·지학사 등

**고등학교** (2022 개정 검정):
- 천재교육·비상교육·미래엔·금성·신사고·동아·지학사·교학사 등

| 단계 | 범위 |
|---|---|
| **Phase 1 파일럿** | **미래엔·천재교육 2종 × 고1 단원** (고1 내신 트랙 정렬) |
| Phase 2 | 상위 5종 × 고1~고3 주요 과목 |
| Phase 3 | 한국 9종 × 8과목 풀 매핑 (목표 규모 도달) |

8과목은 NCIC 2022 개정 고등학교 과목 체계(공통수학1·2, 대수, 미적분Ⅰ·Ⅱ,
확률과 통계, 기하 등)와 정렬 — `ncic.md` §2.3 과목 약칭 테이블 참조.

---

## 4. 저작권 정책 (이 카드의 본체 — 절대 준수)

### 4.1 사용 / 미사용 경계

**✅ 사용 — 구조 메타데이터만:**
- 목차·단원명·차시명·단원 번호
- 페이지 범위 (번호)
- 학습 순서
- 교육과정 코드 (NCIC 성취기준 — 애초에 공공누리 1유형)
- ISBN·출판사·서명·저자·개정연도 (서지 사실정보)

**❌ 미사용 — 일절 복제하지 않음:**
- 본문·개념 설명·서술 텍스트
- 예제·연습문제·단원평가 문제
- 풀이·해설
- 그림·그래프·도표·삽화·사진
- 폰트·디자인·레이아웃

이 경계는 `CLAUDE.md` 절대 금기("검정 교과서 본문·예제 *복제 절대 금지* —
단원명·목차만 사실정보로 인용")와 `licensing_safety.md`("검정 교과서 본문 ❌ /
목차 ✅ 사실정보")와 *완전히 동일선상*이다. 이 카드가 그 원칙을 교과서 매핑
작업 수준으로 구체화한 것이지, **새로운 예외를 만드는 게 아니다.**

### 4.2 교과서 문제는 "자체 코퍼스 동등 문제"로 대체

학생이 "우리 교과서 23쪽 3번 같은 문제"를 풀고 싶을 때:
- ❌ 교과서 23쪽 3번 문제 자체를 저장·노출하지 않는다.
- ✅ 그 단원의 `standard_codes`·`concept_ids`를 키로, **WhyMath 자체 문제
  코퍼스**(NuminaMath·OmniMath 등 Apache/공개 라이선스 + 자체 생성)에서 *동등한
  성취기준·개념을 다루는 문제*를 꺼내 준다.
- 즉 교과서 매핑은 "어떤 성취기준/개념인지"를 알려주는 *인덱스*일 뿐, 문제의
  *공급원*은 자체 코퍼스다. **12단계 파이프라인은 교과서 문제를 수집하는
  단계를 아예 갖지 않는다 — 그게 설계다.**

### 4.3 학습목표 텍스트 인용 — 변호사 검토 전제, 그 전엔 보류

`TextbookUnit.learning_objective_text`는 교과서가 단원 첫머리에 제시하는
"학습목표" 문장이다. PRD 본문은 이를 "페어유즈"로 단정했으나:
- `MEMORY.md` 2026-05-14 결정 로그 PRD 허점 ⑥: **"페어유즈" 단정은 위험** —
  한국 저작권법에 미국식 fair use 법리가 그대로 있지 않고, 분량·목적·시장
  영향 판단이 사안별이다.
- **결정: 변호사 검토(`legal_review_status = 'cleared'`)가 끝나기 전까지
  `learning_objective_text`는 `None`으로 고정.** 스키마 필드는 미리 두되
  *데이터는 비운다*. Phase 1 파일럿은 이 필드 없이 진행.
- 검토가 끝나면 그 결과를 `docs/legal/`에 기록하고 본 카드 4.3절을 갱신한다.

### 4.4 톤 프로필 — 본문이 아니라 "분류 라벨"

`TextbookToneProfile`은 교과서마다 다른 *서술 스타일*을 WhyMath가 학생 콘텐츠
톤 정렬에 쓰려는 자산이다. 핵심:
- 톤 프로필은 교과서 본문을 *담지 않는다*. `formality_level='높음'`,
  `sequencing_style='개념선행형'` 같은 **WhyMath가 부여한 분류 라벨**만 담는다.
- 라벨을 만드는 *분석 과정*에서 본문을 *읽을* 수는 있으나(사람이 교과서를 보는
  것 자체는 자유), 그 본문을 *저장·재배포하지 않는다*. 산출물은 라벨뿐.
- 이는 `licensing_safety.md` "EBS 메타데이터 = 분류" 항목과 같은 논리 —
  *분류·메타데이터는 되고 본문은 안 된다*.

### 4.5 출판사 클레임 시 즉시 격리·삭제 가능한 구조

만에 하나 출판사가 특정 교과서 매핑에 이의를 제기하면 *즉시* 그 자산만 떼어낼
수 있어야 한다.
- 모든 `TextbookMapping`에 `isolation_tag`(출판사+ISBN 단위) 부여.
- 격리 절차: `isolation_tag`로 PostgreSQL 행(`ON DELETE CASCADE`로 단원 동반)·
  JSON 레코드·인덱스에서 *해당 교과서만* soft-delete → 검증 후 hard-delete.
- 다른 교과서·매트릭스·그래프는 무영향 — 교과서 매핑은 매트릭스·그래프를
  *참조*할 뿐, 매트릭스·그래프가 교과서에 의존하지 않는 단방향 구조이기 때문.
- 격리 런북은 `docs/legal/`에 별도 문서화(Phase 1 후속).
- **이 격리 가능성은 사후 수습이 아니라 *설계 요구사항*이다** — 처음부터
  떼어낼 수 있게 짓는다.

### 4.6 라이선스 정리

| 구성요소 | 성격 | 라이선스 |
|---|---|---|
| ISBN·서명·저자·단원명·페이지·목차 | 사실정보 | 저작권 보호 대상 아님 (사실의 나열) |
| NCIC 성취기준 코드 | 공공 | 공공누리 1유형 (`ncic.md` §1.1 출처 표시 의무 승계) |
| 단원↔개념↔성취기준 매핑 | WhyMath 창작물 | WhyMath 자체 자산 |
| 톤 프로필 라벨 | WhyMath 분석물 | WhyMath 자체 자산 |
| 학습목표 텍스트 | 교과서 저작물 | **보류 — 변호사 검토 전 미수집** (4.3절) |

`standard_codes`가 NCIC에서 유래하므로, 매핑을 외부에 노출·라이선싱할 때
NCIC 출처 문구를 동봉한다 (`ncic.md` §1.1 — `data_pipeline.textbook_mapping.models.SOURCE_CITATION`
상수로 강제, NCIC 모듈과 동일 패턴).

---

## 5. 가공 단계 — 12단계 파이프라인

> `01_data_foundation.md` 자산 11번이 "12단계 파이프라인(부록 H)"을 명시. 아래는
> 그 12단계 요약 — data-engineer 9단계 워크플로우를 교과서 특수성으로 세분화한
> 형태다 (9단계의 "수집·정제·정형화"가 교과서 구조 추출 단계들로 확장).

| # | 단계 | 모듈 / 주체 | 책임 | 4절 안전선 체크포인트 |
|---|---|---|---|---|
| 1 | 라이선스 확인 | `licensing_safety.md` + 본 카드 4절 | 검정 교과서 본문 금지선 재확인 | — |
| 2 | 데이터 카드 | 이 문서 | 본 .md | — |
| 3 | 교과서 식별 | `collect.py` | ISBN·출판사·서명·저자·개정연도 (서지) | 서지 = 사실정보 OK |
| 4 | 목차 수집 | `collect.py` | 출판사 공식 사이트·도서관 메타데이터에서 *목차만* | **본문 페이지 접근 금지** |
| 5 | 단원 트리 추출 | `transform.py` | 대→중→소단원 트리 구조화 | 단원명만, 본문 X |
| 6 | 페이지 범위 정합 | `transform.py` | 단원별 페이지 *번호* 정합 | 페이지 번호 OK, 내용 X |
| 7 | 교육과정 코드 매핑 | `transform.py` | 단원 → NCIC 성취기준 코드 | NCIC = 공공누리 1유형 |
| 8 | 매트릭스 개념 매핑 | `transform.py` | 단원 → Universal Concept ID 다대다 | WhyMath 자체 연결 |
| 9 | 톤 프로필 추출 | `transform.py` | 서술 스타일 → *분류 라벨*화 | **라벨만, 본문 저장 금지** (4.4절) |
| 10 | 검증 | `validate.py` + great_expectations | 구조·참조·안전선 (6절) | **본문 혼입 스캔** (6.1절) |
| 11 | 격리 태그 부여 | `load.py` | `isolation_tag`·`legal_review_status` 설정 | 4.5절 격리 구조 |
| 12 | 저장·사람 검수 | `load.py` + 수동 | JSON/CSV 산출 + 5% 검수 (6.2절) | 검수 체크리스트에 4절 항목 |

### 5.1 수집 방법 (단계 3~4 상세)

> 기존 스텁 카드의 수집 방법을 흡수.

1. **출판사 공식 사이트** — 목차 PDF·HTML (본문 페이지는 접근하지 않음)
2. **도서관 서지 메타데이터** — 국립중앙도서관·국회도서관 (ISBN·서명·저자)
3. **학교알리미** — 학교별 채택 정보 (자산 3번 연동 — `StudentProfile`의
   "학교→교과서" 자동 채움 입력)

세 경로 모두 *목차·서지*만 취한다. 본문 PDF가 함께 제공돼도 단계 4는
*목차 영역만* 파싱하고 본문 영역은 버린다.

### 5.2 교과서 문제 대체 흐름 (4.2절 구현)

7·8단계에서 단원↔성취기준/개념을 매핑하고 나면, 학생에게 문제를 줄 때는 그
키로 **자체 코퍼스를 조회**한다. 파이프라인에 "교과서 문제 수집" 단계가
없는 것이 4.2절의 구조적 보장이다.

---

## 6. 검증 결과 (목표 invariants — 미구현)

> `tests/data_pipeline/textbook_mapping/` 스위트가 보장할 invariant.
> **아직 테스트 없음.**

### 6.1 기계 검증 — 구조 + 저작권 안전선

| Invariant | 테스트 (예정) |
|---|---|
| `isbn`이 13자리 형식 | `test_isbn_format` |
| `unit_tree`가 유효한 트리 (사이클·고아 노드 없음) | `test_unit_tree_integrity` |
| `standard_codes`가 NCIC `standards.json`에 실재 | `test_standard_codes_resolve` |
| `concept_ids`가 개념 그래프/매트릭스 키 공간에 실재 | `test_concept_ids_resolve` |
| **`learning_objective_text`가 모두 `None`** (변호사 검토 전) | `test_learning_objective_text_is_none` — 비-None 발견 시 적재 거부 |
| **본문 혼입 스캔**: `unit_title`·톤 프로필 필드 길이 상한 + 문장부호 패턴 | `test_no_body_text_leaked` (6.1절 상세) |
| `isolation_tag`가 모든 레코드에 존재 | `test_isolation_tag_present` |
| `legal_review_status`가 3종 enum 밖이면 거부 | `test_rejects_unknown_review_status` |
| `subject`가 8과목 enum | `test_subject_in_set` |
| Phase 1 산출물 출판사가 {미래엔, 천재교육} 뿐 | `test_phase1_publisher_scope` |

**본문 혼입 스캔 상세**: 단원명은 보통 명사구다("이차함수의 그래프"). 만약
`unit_title`이나 톤 프로필 라벨에 *여러 문장*·*과도한 길이*가 들어오면 본문이
잘못 섞여 들어온 신호다. 휴리스틱 경고 → 사람 검수로 확정. `CLAUDE.md` CI의
`policy-guard` job(검정교과서 본문 인용 패턴 차단)과 같은 정신.

### 6.2 사람 검수 (필수 — 단계 12)

매핑 5% 이상을 검수. 체크리스트:
- [ ] 단원명·페이지가 출판사 공식 목차와 일치하는가 (사실정보 정확성)
- [ ] **본문·예제·그림이 어떤 필드에도 섞여 들어오지 않았는가** (4.1절 — 최우선)
- [ ] `learning_objective_text`가 전부 `None`인가 (4.3절 — 변호사 검토 전)
- [ ] 톤 프로필이 *라벨*이지 *본문 발췌*가 아닌가 (4.4절)
- [ ] 단원↔NCIC 성취기준 매핑이 타당한가 — *학회·연구* 출처 확인
- [ ] `concept_ids`가 개념 그래프·매트릭스와 같은 ID 공간인가
- [ ] `isolation_tag`로 이 교과서만 떼어낼 수 있는 구조인가 (4.5절)

---

## 7. 구축 절차 (Kiki용 — Phase 1 파일럿)

> **선행 조건**: NCIC 성취기준 디지털화 완료(`data/ncic/standards.json`). 교과서
> 매핑은 그 산출물을 매칭 타겟으로 쓴다.

### 7.1 환경 구성 (1회)

```bash
cd src/data-pipeline
source .venv/bin/activate          # NCIC와 동일 가상환경
pip install -e ".[dev]"
```

### 7.2 빌드 (미래엔·천재교육 2종 × 고1)

```bash
# 프로젝트 루트에서 (Phase 1 파일럿 — 시그니처/시드 단계)
python -m data_pipeline.textbook_mapping build \
  --publishers 미래엔,천재교육 \
  --grade 10 \
  --ncic-standards data/ncic/standards.json \
  --output-dir data/textbook_mapping/
```

출력(예정):
- `data/textbook_mapping/mappings.json` — `TextbookMapping` 전체 (**본문 0건**)
- `data/textbook_mapping/units.csv` — 평탄화 단원 목록 (분석용)
- `data/textbook_mapping/mappings.meta.json` — 출처·라이선스·격리 태그 sidecar

### 7.3 사람 검수 (필수 — 단계 12)

```python
import json, random
data = json.loads(open("data/textbook_mapping/mappings.json", encoding="utf-8").read())
units = [u for m in data["mappings"] for u in m["unit_tree"]]
sample = random.sample(units, k=max(5, len(units) // 20))   # 5% or 최소 5개
for u in sample:
    print(u["unit_number"], u["unit_title"], "|", u["page_range"],
          "| 성취기준:", u["standard_codes"])
```

6.2절 체크리스트 수행. **검수 1순위는 "본문 혼입 0건" 확인이다** — 규모·매핑
정확도보다 4절 안전선 준수가 먼저다(`CLAUDE.md` 의사결정 우선순위: 법적·윤리적
준수 > 학습 효과 > UX).

---

## 8. Phase 2+ 후속 작업 (이번 작업 범위 외)

- [ ] 미래엔·천재교육 2종 → 상위 5종 → 한국 9종 × 8과목 풀 매핑 확장
- [ ] `learning_objective_text` 변호사 검토 → 결과를 `docs/legal/`에 기록 후
      4.3절 갱신 (검토 통과 시에만 필드 활성화)
- [ ] 출판사 클레임 격리 런북 작성 (`docs/legal/`) — 4.5절 절차 문서화
- [ ] PostgreSQL 스키마 + Alembic 마이그레이션 (2.4절 DDL 정식 생성)
- [ ] `concept_ids` ↔ 개념 그래프·매트릭스 키 공간 join 무결성 자동 검사 (cross-dataset CI)
- [ ] 학교알리미(자산 3번) ↔ 교과서 매핑 연결 — `StudentProfile`의 "학교→교과서"
      자동 채움 완성
- [ ] `licensing_safety.md` "회색 영역"의 "검정교과서 출판사 공식 제휴" 진행 시
      이 자산을 제휴 협상 테이블에 올림 (B2B)
