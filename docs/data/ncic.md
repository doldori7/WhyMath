# 데이터셋: NCIC 성취기준 (2022 개정 교육과정)

> **L1 truth source.** 모든 콘텐츠·문항·매핑의 root.

---

## 1. 메타데이터

| 항목 | 값 |
|---|---|
| 정식 명칭 | 2022 개정 교육과정 — 수학과 교육과정 |
| 고시 번호 | 교육부 고시 제2022-33호 [별책 8] |
| 출처 사이트 | https://www.ncic.go.kr (국가교육과정정보센터) |
| 라이선스 | **공공누리 제1유형 (출처 표시 필수)** |
| 상업 활용 | 허용 |
| 변경·가공 | 허용 (2차적 저작물 작성 가능) |
| 데이터 카드 작성일 | 2026-05-13 |
| 다음 검토일 | Phase 1 종료 시점 (2026-11) |
| 예상 규모 | ~150-180개 성취기준 (초·중·고 합산) |
| Phase 1 우선 | 고1 공통수학·고2 일반선택(대수·미적분Ⅰ·확률과 통계) |

### 라이선스 출처 표시 (의무)

모든 저장·노출 시 다음 문구를 동봉:

```
출처: 교육부 고시 제2022-33호 [수학과 교육과정],
      국가교육과정정보센터(NCIC, https://www.ncic.go.kr)
```

`data_pipeline.ncic.models.SOURCE_CITATION` 상수로 모듈 차원에서 강제.

---

## 2. 스키마

### 2.1 Pydantic 모델 (Phase 1 — 운영 모델)

`src/data-pipeline/data_pipeline/ncic/models.py`:

```python
class AchievementStandard(BaseModel):
    code: str                       # PK. '[9수01-01]', '[10공수1-01-01]' 등
    grade_band: Literal[...]        # 학년군 enum
    school_type: Literal[...]       # '초등학교' | '중학교' | '고등학교'
    subject: str                    # '수학' | '공통수학1' | '대수' | '미적분Ⅰ' 등
    domain: str                     # '수와 연산' | '변화와 관계' 등
    sub_domain: str | None
    statement: str                  # 성취기준 본문
    commentary: str | None
    big_idea: str | None
    curriculum_revision: str = "2022 개정"
    effective_from: date | None
    parent_codes: list[str]         # 선수 성취기준 (분석 결과로 후처리)
    source_url: str                 # 공공누리 1유형 출처 의무
    source_document: str | None     # PDF 식별자
```

### 2.2 백엔드 ORM (구현 완료 — P1·2026-06-16)

성취기준은 백엔드 L1 코어의 **1급 테이블**이다(Alembic `a6b7c8d9e0f1`·단일 head). PK는
**`norm_id`**(2022·2015 교육과정 간 유일) — 원본 `code`는 두 교육과정 **153건 충돌**로 PK 불가하여
`official_code`(비유일)로 강등하고, 개념↔성취기준 관계 테이블(`연결구분`)을 동반한다. 듀얼커리큘럼·
`norm_id` 설계 배경은 `achievement_standards_v1.md`·`curriculum_master_v2_integration_review.md` 참조.

```sql
CREATE TABLE achievement_standard (
    norm_id                 VARCHAR(32) PRIMARY KEY,          -- 예: 2022_2수_01_01
    official_code           VARCHAR(32) NOT NULL,             -- 예: [9수01-01] (교육과정 간 비유일)
    curriculum_revision     VARCHAR(16) NOT NULL,             -- '2022 개정' | '2015 개정'
    grade_band              VARCHAR     NOT NULL,
    school_type             VARCHAR     NOT NULL,
    subject                 VARCHAR     NOT NULL,
    domain                  VARCHAR     NOT NULL,
    sub_domain              VARCHAR,
    statement               TEXT        NOT NULL,
    commentary              TEXT,
    big_idea                TEXT,
    effective_from          DATE,
    parent_codes            TEXT[]      NOT NULL DEFAULT '{}',
    source_url              TEXT        NOT NULL,
    source_document         TEXT,
    UNIQUE (curriculum_revision, official_code)              -- 교육과정 내 유일·간 충돌 허용
);
CREATE INDEX ix_achievement_standard_official_code   ON achievement_standard(official_code);
CREATE INDEX ix_achievement_standard_revision_domain ON achievement_standard(curriculum_revision, domain);

CREATE TABLE concept_standard_link (
    link_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_code   VARCHAR(64) NOT NULL,                      -- 개념 identity(UC.*/추후 ELEM-GEO) 느슨참조
    norm_id        VARCHAR(32) NOT NULL REFERENCES achievement_standard(norm_id) ON DELETE CASCADE,
    link_type      VARCHAR(8)  NOT NULL,                      -- 직접 | 재매핑 | 준용
    note           TEXT,
    UNIQUE (concept_code, norm_id, link_type)
);
```

정의: `src/backend/whymath_backend/db/models/{achievement_standard,concept_standard_link}.py` +
`schema/standard.py`. data-pipeline `load_to_postgres`는 여전히 *staging* 보조이며, **authoritative
영속은 위 백엔드 ORM**이다 — data-pipeline 추출물(Collection JSON)을 백엔드 `l1/` 로더가 멱등 적재한다
(corpus `code`→ORM `official_code`·`concept_src_id`→`concept_code`). 실 PG upgrade/downgrade·통합테스트는
CI `backend-migrations`·`data-pipeline — 적재 통합 (실 PG)` 잡으로 검증한다.

### 2.3 코드 패턴

```
[<학년대수><과목약칭><영역2자리>-<순번2자리>]
```

| 학년 대수 | 학교급/학년군 |
|---|---|
| 2 | 초등 1~2학년군 |
| 4 | 초등 3~4학년군 |
| 6 | 초등 5~6학년군 |
| 9 | 중학교 1~3학년군 |
| 10 | 고등학교 공통과목 (공통수학1·2) |
| 12 | 고등학교 일반선택·진로선택 |

| 과목 약칭 | 풀네임 |
|---|---|
| 수 | 수학 (초·중) |
| 공수1, 공수2 | 공통수학1, 공통수학2 |
| 대수 | 대수 |
| 미적Ⅰ, 미적Ⅱ | 미적분Ⅰ, 미적분Ⅱ |
| 확통 | 확률과 통계 |
| 기하 | 기하 |
| 경수, 인수, 실통 | 경제 수학, 인공지능 수학, 실용 통계 |

사례:
- `[9수01-01]` — 중학교 수와 연산 첫 번째
- `[10공수1-01-01]` — 고1 공통수학1 영역1 첫 번째 (NCIC 실제 표기는 `[10공수1-01]`도 가능)
- `[12대수01-01]` — 고2 대수 첫 번째
- `[12미적Ⅰ01-01]` — 고2 미적분Ⅰ 첫 번째

정규식 (Pydantic 검증):
```
^\[(\d{1,2})([ㄱ-ㆎ가-힣Ⅰ-ⅿ]{1,6})(\d{2})-(\d{2})\]$
```

매핑 테이블은 `data_pipeline/ncic/transform.py`의 `_GRADE_BAND_MAP`·`_SUBJECT_MAP`. NCIC 변경 시 *이 두 dict만* 갱신.

---

## 3. 알려진 제약

### 3.1 사이트 접근성

- **WebFetch 차단 확인** (2026-05-13): `https://www.ncic.go.kr`·`https://www.ncic.re.kr` 모두 403. 한국 정부 사이트는 일반 자동화 봇 UA를 차단하는 경향.
- **Claude Code on web 환경 추가 제약** (2026-05-14 재확인): 이 개발 환경은 네트워크 allowlist 기반 — PyPI 등 등록 호스트만 허용하고 `ncic.go.kr`은 인프라 레벨에서 차단(`403 Host not in allowlist`). `curl`(sandbox·sandbox 우회)·`WebFetch` 3경로 모두 차단 확인. NCIC PDF는 *반드시 사람이 다른 환경에서 받아* 레포에 반입해야 한다 (`data/ncic/raw/`).
- 대응: 
  - 정중한 UA(`WhyMath/0.1 (research; contact: ...)`) + Accept-Language 헤더
  - rate-limit 1초/요청 + exponential backoff
  - 폴백: NCIC에서 *수동 다운로드한 PDF*를 로컬에서 `--pdf` 옵션으로 파싱

### 3.2 페이지 구조 가정

- 메인 페이지는 ASP·JSP 기반 동적 렌더 가능 (POST·세션 의존 페이지 다수)
- 검정 데이터(교육과정 원문)는 *HWP/PDF 첨부* 형태가 표준 — HTML 본문에 성취기준 전체가 노출되지 않을 수 있음
- 따라서 **PDF 폴백 경로가 1차 권장** — `pdfplumber`로 추출

### 3.3 HWP 미지원

- 교육부 고시 원본은 HWP/HWPX 형태도 동시 제공
- 본 모듈은 *PDF만* 처리 (HWP는 별도 변환 의존성 필요 — `hwp5`·`pyhwp` 또는 한컴 변환)
- HWP만 있는 경우: 한컴오피스 또는 LibreOffice로 PDF 변환 후 `--pdf` 사용

### 3.4 코드 표기 변형

- PDF 추출 시 dash 문자(–·—·−) 변형 가능 — `clean.normalize_code`에서 ASCII `-`로 통일
- 공백 삽입 가능 (`[ 9수 01-01 ]`) — 동일 함수에서 제거
- 로마숫자(Ⅰ·Ⅱ) vs ASCII(I·II) 변형 — 검증 단계에서 양쪽 허용

### 3.5 영역 코드 학교급별 상이

- 중학교: 01 수와 연산 / 02 변화와 관계 / 03 도형과 측정 / 04 자료와 가능성
- 고등학교 공통과목·선택과목별로 영역 구성 다름 (NCIC 원문 참조)
- 본 모듈은 *코드 패턴*만 검증하고 *영역명 자체*는 수집된 그대로 저장 (보수적 — 잘못된 매핑보다 누락이 낫다)

---

## 4. 가공 단계 (data-engineer 9단계 워크플로우)

| 단계 | 모듈 | 책임 |
|---|---|---|
| 1. 라이선스 확인 | `docs/data/licensing_safety.md` | 공공누리 1유형 매트릭스 확인 |
| 2. 데이터 카드 | 이 문서 | 본 .md |
| 3. 수집 | `collect.py` | httpx + BeautifulSoup4 + pdfplumber |
| 4. 정제 | `clean.py` | 공백·zero-width·HTML 엔티티·dash 정규화 |
| 5. 정형화 | `transform.py` | `RawStandardRecord` → `AchievementStandard` |
| 6. 검증 | `validate.py` | 코드 패턴·enum·중복·source_url 의무 |
| 7. 저장 | `load.py` | JSON + CSV + sidecar (Phase 1) / PostgreSQL (Phase 2) |
| 8. 사람 검수 | 수동 | 무작위 5% 샘플 — Kiki가 직접 |
| 9. MEMORY.md | 수동 | 결과 기록 + 후속 데이터 소스 차단 해제 |

---

## 5. 검증 결과 (모킹 단위테스트 + 실 PG 통합테스트)

`tests/data_pipeline/ncic/` 테스트 스위트가 다음을 보장:

| Invariant | 테스트 |
|---|---|
| 합성 HTML에서 코드 패턴 추출 | `test_collect_html_synthetic_fixture` |
| dash 변형 정규화 (`–` `—` `−` → `-`) | `test_normalize_code_dash_variants` |
| 코드 정규식 위반 시 ValidationError | `test_model_rejects_invalid_code` |
| 학교급-학년군 정합성 검증 | `test_model_rejects_inconsistent_grade_band` |
| 중복 코드 탐지 | `test_validate_detects_duplicate_codes` |
| `source_url` 누락 시 변환 실패 | `test_transform_requires_source_url` |
| JSON 출력에 SOURCE_CITATION·LICENSE_NOTICE 포함 | `test_write_json_includes_license_notice` |
| CSV sidecar 메타데이터 생성 | `test_write_csv_creates_sidecar` |
| PDF 합성 픽스처에서 e2e | `test_collect_pdf_synthetic_fixture` |
| respx로 HTTP 모킹 (실 호출 없음) | `test_crawler_http_mocked` |
| 실 PG 적재 왕복 (신규 INSERT·upsert UPDATE·DO NOTHING) | `test_load_postgres_integration` (슬99·실 PG CI 잡) |

테스트 실행:
```bash
cd src/data-pipeline
pytest --cov=data_pipeline.ncic --cov-report=term
```

---

## 6. 실 크롤링 절차 (Kiki용)

> **실행 위치 주의**: 환경 구성은 `src/data-pipeline/`(pyproject 위치)에서,
> 크롤러 *실행*은 **프로젝트 루트**에서 한다. editable 설치 후에는 어디서든
> `data_pipeline` import 가능하므로, 루트에서 실행하면 `--output-dir data/ncic/`
> 가 루트의 `data/ncic/`를 정확히 가리킨다.

### 6.1 환경 구성 (1회)

**Linux / macOS (bash)**
```bash
cd src/data-pipeline
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Windows (PowerShell) — conda 사용 시**
```powershell
conda create -y -n whymath python=3.12
conda activate whymath
cd src\data-pipeline
pip install -e ".[dev]"
```
PowerShell 5.x는 `&&`·`\` 줄 연속·`source`를 지원하지 않으므로 *한 줄씩* 실행한다.

설치 확인: `python -m data_pipeline.ncic --help`

### 6.2 크롤링 실행 (프로젝트 루트에서)

**옵션 A — NCIC HTML 크롤링 시도** (사이트가 봇 차단할 수 있음)
```bash
# bash
python -m data_pipeline.ncic crawl --url "https://www.ncic.go.kr/<실제경로>" --output-dir data/ncic/
```
```powershell
# PowerShell
python -m data_pipeline.ncic crawl --url "https://www.ncic.go.kr/<실제경로>" --output-dir data\ncic\
```

**옵션 B (권장) — NCIC에서 PDF 수동 다운로드 후 파싱**
1. https://www.ncic.go.kr 접속 → 교육과정 자료실 → 2022 개정 교육과정 → 수학과
2. **교육부 고시 제2022-33호 [별책 8] 수학과 교육과정** PDF 다운로드 (HWP만 있으면 한컴/LibreOffice로 PDF 변환)
3. `data/ncic/raw/curriculum_math_2022.pdf` 로 저장 (`data/ncic/raw/` 디렉토리 없으면 생성)

```bash
# bash — 프로젝트 루트에서
python -m data_pipeline.ncic crawl --pdf data/ncic/raw/curriculum_math_2022.pdf --pdf-source-document "교육부고시_2022-33호_별책8_수학과교육과정" --output-dir data/ncic/
```
```powershell
# PowerShell — 프로젝트 루트에서 (한 줄)
python -m data_pipeline.ncic crawl --pdf data\ncic\raw\curriculum_math_2022.pdf --pdf-source-document "교육부고시_2022-33호_별책8_수학과교육과정" --output-dir data\ncic\
```

출력:
- `data/ncic/standards.json` — 메타데이터 + 성취기준 전체
- `data/ncic/standards.csv` — 표 분석용
- `data/ncic/standards.meta.json` — CSV sidecar (출처·라이선스)

### 사람 검수 (필수 — 단계 8)

```python
import json, random
data = json.loads(open("data/ncic/standards.json", encoding="utf-8").read())
n = len(data["standards"])
sample = random.sample(data["standards"], k=max(5, n // 20))   # 5% or 최소 5개
for std in sample:
    print(std["code"], "—", std["statement"][:80])
```

체크리스트:
- [ ] 코드 형식이 NCIC 원문과 일치 (특히 고교 선택과목 약칭)
- [ ] 본문에 단어 잘림·중복·공백 이상 없음
- [ ] 학교급·학년군 추론이 옳음
- [ ] 영역명이 NCIC 원문과 일치

---

## 7. Phase 2 후속 작업 (이번 작업 범위 외)

- [ ] PostgreSQL *프로덕션* 배포 + Alembic 정식 마이그레이션 (현재 로더는 `create_all` 멱등)
- [x] `load_to_postgres` 구현 + 실 PG 통합테스트 CI 검증 (슬99)
- [ ] pgvector 임베딩 (statement 한국어 SBERT — `BM-K/KoSimCSE-roberta`)
- [ ] 선수 성취기준(`parent_codes`) 자동 추출 (학년·영역 그래프 기반)
- [ ] 교육과정 해설서(별책 8 부속)도 수집 → `big_idea`·`commentary` 보강
- [ ] HWP 직접 지원 (한컴 변환 의존 또는 `pyhwp`)
