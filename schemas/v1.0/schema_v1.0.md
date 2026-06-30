# WhyMath 데이터 스키마 설계 문서 v1.0

## 한국 수학 입시 시장 100가지 특성 기반

**문서 버전**: v1.0
**작성일**: 2026-05-28
**기반 문서**: WhyMath PRD v1.2
**대상**: 백엔드·데이터 엔지니어, AI 엔진 개발자
**범위**: PostgreSQL 16 (+ TimescaleDB·pgvector) 통합 스키마

---

## 📋 목차

1. [설계 원칙](#1-설계-원칙)
2. [8개 데이터 도메인 개요](#2-8개-데이터-도메인-개요)
3. [도메인 1: 콘텐츠 (Problem)](#3-도메인-1-콘텐츠-problem)
4. [도메인 2: 개념 그래프 (Concept Graph)](#4-도메인-2-개념-그래프-concept-graph)
5. [도메인 3: 학생 (User)](#5-도메인-3-학생-user)
6. [도메인 4: 학습 활동 (Activity)](#6-도메인-4-학습-활동-activity)
7. [도메인 5: Socratic 대화 (Dialogue)](#7-도메인-5-socratic-대화-dialogue)
8. [도메인 6: 학습 진단 (Assessment)](#8-도메인-6-학습-진단-assessment)
9. [도메인 7: 시간 시계열 (Time Series)](#9-도메인-7-시간-시계열-time-series)
10. [도메인 8: 콘텐츠 변형·생성 이력 (Provenance)](#10-도메인-8-콘텐츠-변형생성-이력-provenance)
11. [DB 분산 전략](#11-db-분산-전략)
12. [인덱스·성능 전략](#12-인덱스성능-전략)
13. [데이터 거버넌스](#13-데이터-거버넌스)
14. [마이그레이션·확장성](#14-마이그레이션확장성)

---

## 1. 설계 원칙

### 1.1 핵심 원칙 7가지

#### 원칙 1: 메타데이터 풍부성(Rich Metadata)
한 문제(`problem`)에 50개 이상의 메타데이터 필드를 부여한다. 외산 데이터셋(GSM8K)이 라벨링하지 못한 한국 수능 특유의 정보를 모두 구조화한다.

#### 원칙 2: 다차원 난이도(Multidimensional Difficulty)
"난이도 4점"같은 단일 척도가 아니라, **5개 독립 축**으로 난이도를 표현한다.
- 계산 복잡도, 조건 해석 난이도, 케이스 분류 깊이, 시각자료 복잡도, 단원 융합도

#### 원칙 3: 개념 그래프 우선(Concept Graph First)
모든 콘텐츠는 **개념 그래프의 노드와 연결**된다. 단원·소단원·세부 개념까지 3계층으로 분해한다.

#### 원칙 4: 시간 인지(Time-Aware)
모든 학습 활동은 TimescaleDB에 시계열로 저장된다. "언제, 얼마나 오래 막혔는가"가 추천의 핵심 신호.

#### 원칙 5: 페르소나 친화(Persona-Aware)
콘텐츠는 5종 페르소나에 대한 적합도(`persona_fit_score`)를 갖는다. 동일 문제도 페르소나마다 다르게 전달.

#### 원칙 6: 출처 추적(Provenance)
모든 콘텐츠는 출처(평가원/EBS/AIHub/자체 생성)와 검수 이력이 추적된다. 저작권·신뢰성·법적 안전성 확보.

#### 원칙 7: 변경 가능성 흡수(Versioning)
2028 수능 개편 같은 정책 변화에 대응 가능하도록 **연도별 교육과정 버전 관리**가 모든 메타데이터에 포함된다.

### 1.2 스키마 작성 표기법

```
표기법:
- PK: Primary Key
- FK: Foreign Key
- IDX: Index
- ENUM: 열거형 (PostgreSQL 14+ 또는 CHECK 제약)
- JSONB: PostgreSQL JSONB 타입
- VECTOR: 벡터 임베딩 (pgvector·Postgres 동거·슬98)
- TS: 시계열 (TimescaleDB hypertable)
```

---

## 2. 8개 데이터 도메인 개요

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ① Problem    ② Concept Graph    ③ User                 │
│  (문제·콘텐츠) ↔ (개념 노드)      ↔ (학생)              │
│      │              │                  │                │
│      ├──────────────┴──────────────────┤                │
│      ▼                                  ▼                │
│  ④ Activity (학습 활동) ── ⑤ Dialogue (Socratic 대화)   │
│      │                          │                       │
│      ▼                          ▼                       │
│  ⑥ Assessment (진단·평가)  ⑦ Time Series (시계열)       │
│                                                         │
│  ⑧ Provenance (출처·생성 이력) ─── 모든 도메인 추적     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 도메인 책임 분리

| 도메인 | 책임 | 저장소 | 데이터 크기 |
|---|---|---|---|
| ① Problem | 문제·정답·풀이 + 50+ 메타데이터 | PostgreSQL | 약 100만 행 (5년) |
| ② Concept Graph | 단원/개념 노드와 관계 (DAG) | PostgreSQL + pgvector | 약 2,000 노드 |
| ③ User | 학생·페르소나·학습 목표 | PostgreSQL | 약 50만 행 (5년) |
| ④ Activity | 풀이·시도·결과 이벤트 | PostgreSQL (요약) + TimescaleDB (raw) | 수억 행 |
| ⑤ Dialogue | Socratic 대화 이력 | PostgreSQL + JSONB | 수십억 행 |
| ⑥ Assessment | 진단 결과·등급 예측 | PostgreSQL | 수백만 행 |
| ⑦ Time Series | 풀이 시간·집중도 시계열 | TimescaleDB | 수십억 포인트 |
| ⑧ Provenance | 데이터 출처·생성 이력 | PostgreSQL + 감사 로그 | 콘텐츠 행과 1:N |

---

## 3. 도메인 1: 콘텐츠 (Problem)

### 3.1 핵심 테이블: `problem`

100가지 특성 중 **약 40개가 이 테이블에 직접 반영**된다. WhyMath의 가장 중요한 단일 테이블.

```sql
CREATE TABLE problem (
    -- ===== 기본 식별 =====
    problem_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id         VARCHAR(64) UNIQUE,         -- 평가원/EBS 원본 ID
    slug                VARCHAR(128) UNIQUE,        -- 사람이 읽는 식별자

    -- ===== 출처 (특성 #11, #12, #41, #100) =====
    source_type         source_type_enum NOT NULL,  -- 평가원/EBS/AIHub/자체생성
    source_detail       JSONB,                      -- {publisher, year, edition, page}
    -- 예: {"publisher": "평가원", "exam": "2026학년도_수능", "subject": "미적분", "number": 30}

    -- ===== 시험 컨텍스트 (특성 #12, #41) =====
    exam_type           exam_type_enum,             -- 수능/모평/학평/EBS교재/N제/자체생성
    exam_year           INTEGER,                    -- 학년도 (2026)
    exam_month          INTEGER,                    -- 6/9/11/-
    problem_number      INTEGER,                    -- 22/30 (문항 번호)
    exam_authority_weight DECIMAL(3,2),             -- 학평0.5/모평0.8/수능1.0

    -- ===== 교육과정 버전 (특성 #20, #30, #80) =====
    curriculum_version  curriculum_enum NOT NULL,   -- 2015개정/2022개정
    valid_from_year     INTEGER NOT NULL,           -- 2014 (2015개정 첫 적용)
    valid_to_year       INTEGER,                    -- NULL이면 현재까지

    -- ===== 과목·단원 (특성 #1, #26, #79) =====
    subject             subject_enum NOT NULL,      -- 공통/미적분/확통/기하/인공지능수학
    unit_codes          TEXT[] NOT NULL,            -- ['CAL-INT-DEF', 'FUN-COMPOSITE']
    -- 단원 코드 예: CAL(미적분)-INT(적분)-DEF(정적분)

    -- ===== 문항 형식 (특성 #2, #3, #7, #13, #25) =====
    question_format     question_format_enum,       -- 객관식/단답형/합답형/서술형
    points              INTEGER,                    -- 2/3/4점
    answer_format       answer_format_enum,         -- 자연수/분수/실수/식
    answer_constraint   JSONB,                      -- {"min":1, "max":999, "is_natural": true}
    -- 단답형 자연수 답 변환 패턴 추적 (특성 #25)
    answer_transform    JSONB,                      -- {"type":"p_plus_q", "p":3, "q":5} → 답 8

    -- ===== 본문·풀이·정답 =====
    question_text       TEXT NOT NULL,              -- 발문 원문
    question_text_md    TEXT,                       -- 마크다운+LaTeX
    question_image_uri  TEXT,                       -- 도형/그래프 (MinIO URI)
    choices             JSONB,                      -- 객관식 보기 5개
    answer              TEXT NOT NULL,              -- 정답 (예: "16")
    answer_explanation  TEXT,                       -- 평가원 공식 해설
    multiple_answers    JSONB,                      -- 복수해 가능성 (특성 #33)

    -- ===== 한국 시그니처 패턴 (특성 #21, #22, #23, #24) =====
    signature_patterns  signature_pattern_enum[],
    -- ['COMPOSITE_DIFFERENTIABILITY', 'INDUCTIVE_SEQUENCE',
    --  'DEFINED_INTEGRAL_FUNCTION', 'FUNCTION_COUNT', ...]

    -- ===== 발문 구조 (특성 #18) =====
    has_condition_list  BOOLEAN DEFAULT FALSE,      -- (가)(나)(다) 조건 나열형 여부
    condition_count     INTEGER,                    -- 조건 개수
    conditions_parsed   JSONB,
    -- [{"label":"가", "text":"f(x)는 실수 전체에서 미분가능", "formal":"differentiable(f, R)"},
    --  {"label":"나", "text":"f(0)=1, f(1)=3", "formal":"f(0)=1 AND f(1)=3"}]

    -- ===== 시각자료 (특성 #9, #17) =====
    has_visual          BOOLEAN DEFAULT FALSE,
    visual_type         visual_type_enum[],         -- 그래프/도형/표/좌표평면
    visual_complexity   INTEGER,                    -- 1-5

    -- ===== 다차원 난이도 (원칙 2) =====
    difficulty_overall  DECIMAL(3,2),               -- 1.0-5.0 종합
    diff_calculation    DECIMAL(3,2),               -- 계산 복잡도
    diff_interpretation DECIMAL(3,2),               -- 조건 해석 난이도
    diff_case_analysis  DECIMAL(3,2),               -- 케이스 분류 깊이
    diff_visual         DECIMAL(3,2),               -- 시각자료 복잡도
    diff_integration    DECIMAL(3,2),               -- 단원 융합도

    -- ===== 정답률·통계 (특성 #29) =====
    historical_correct_rate DECIMAL(5,4),           -- 0.0822 (8.22%)
    rate_top_grade      DECIMAL(5,4),               -- 1등급 학생 정답률
    rate_mid_grade      DECIMAL(5,4),               -- 3-4등급
    rate_low_grade      DECIMAL(5,4),               -- 6등급 이하

    -- ===== 시간 예상치 (특성 #2, #42) =====
    expected_solve_seconds INTEGER,                 -- 평균 풀이 시간 (초)
    expected_solve_seconds_p90 INTEGER,             -- 상위 10% 학생 기준

    -- ===== 페르소나 적합도 (원칙 5) =====
    persona_fit         JSONB,
    -- {"A_일반고고3": 0.9, "B_자사고N수": 0.7, "C_검정고시": 0.85, ...}

    -- ===== EBS 연계 (특성 #11) =====
    ebs_linked          BOOLEAN DEFAULT FALSE,
    ebs_source          JSONB,                      -- {"book":"수능특강", "chapter":3, "page":47}

    -- ===== 단원 융합 (특성 #16) =====
    is_cross_unit       BOOLEAN DEFAULT FALSE,
    cross_unit_pairs    JSONB,                      -- [["수열","극한"],["미분","함수"]]

    -- ===== 그래프 개형 추론 (특성 #9, #22) =====
    requires_graph_sketch BOOLEAN DEFAULT FALSE,    -- 학생이 그래프를 그려야 풀리는가
    sketch_step_count   INTEGER,                    -- 보통 5-6개

    -- ===== 라벨링 (검색·필터) =====
    tags                TEXT[],                     -- ['킬러','22번고정','평가원2025']
    keywords            TEXT[],                     -- ['합성함수','미분가능성','케이스분류']

    -- ===== 사용자 노출 정책 =====
    is_premium          BOOLEAN DEFAULT FALSE,
    is_published        BOOLEAN DEFAULT FALSE,
    publish_at          TIMESTAMPTZ,

    -- ===== 운영 메타 =====
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    created_by          UUID,                       -- 인간 검수자 또는 AI 에이전트
    review_status       review_status_enum,         -- pending/approved/rejected
    review_score        DECIMAL(3,2)                -- 검수 점수 0-5
);

-- 인덱스
CREATE INDEX idx_problem_exam ON problem(exam_type, exam_year, exam_month);
CREATE INDEX idx_problem_subject_unit ON problem(subject, unit_codes);
CREATE INDEX idx_problem_signature ON problem USING GIN(signature_patterns);
CREATE INDEX idx_problem_difficulty ON problem(difficulty_overall);
CREATE INDEX idx_problem_persona_fit ON problem USING GIN(persona_fit);
CREATE INDEX idx_problem_curriculum ON problem(curriculum_version, valid_from_year);
CREATE INDEX idx_problem_tags ON problem USING GIN(tags);
CREATE INDEX idx_problem_keywords ON problem USING GIN(keywords);
```

### 3.2 보조 테이블

```sql
-- 문항 풀이 단계 (Socratic 코칭 시 사용)
CREATE TABLE problem_step (
    step_id             UUID PRIMARY KEY,
    problem_id          UUID REFERENCES problem,
    step_order          INTEGER NOT NULL,
    step_type           step_type_enum,
    -- 조건해석/케이스분류/그래프스케치/계산/검산
    step_title          VARCHAR(200),
    socratic_prompt     TEXT,                       -- "조건 (가)를 수식으로 표현해보세요"
    expected_answer     TEXT,
    common_mistakes     JSONB,                      -- [{"error":"...", "hint":"..."}]
    UNIQUE(problem_id, step_order)
);

-- 문항 간 관계 (전형성·유사도)
CREATE TABLE problem_relation (
    parent_problem_id   UUID REFERENCES problem,
    related_problem_id  UUID REFERENCES problem,
    relation_type       relation_type_enum,
    -- 변형/유사/선수/심화/대조
    similarity_score    DECIMAL(3,2),
    PRIMARY KEY (parent_problem_id, related_problem_id, relation_type)
);
```

### 3.3 매핑된 100가지 특성

| 특성 # | 필드명 |
|---|---|
| #1, #26 | `subject` |
| #2 | `expected_solve_seconds` |
| #3 | `points` |
| #4 | `problem_number` |
| #9, #17 | `has_visual`, `visual_type`, `visual_complexity`, `requires_graph_sketch` |
| #11 | `ebs_linked`, `ebs_source` |
| #12 | `exam_authority_weight` |
| #13, #25 | `answer_constraint`, `answer_transform` |
| #16 | `is_cross_unit`, `cross_unit_pairs` |
| #18 | `has_condition_list`, `conditions_parsed` |
| #20, #30, #80 | `curriculum_version`, `valid_from_year` |
| #21~24 | `signature_patterns` |
| #29 | `historical_correct_rate`, `rate_top/mid/low_grade` |
| #33 | `multiple_answers` |
| #36, #37 | `source_type` (자체생성·변형) |


---

## 4. 도메인 2: 개념 그래프 (Concept Graph)

### 4.1 설계 의도

**특성 #16 (단원 융합 출제)**와 **PRD FR-006**의 핵심 구현체. 개념 간 선후관계·포함관계·유사관계를 DAG로 표현해서, "이 학생이 막힌 진짜 이유는 그 개념의 선수 개념을 모르기 때문이다"를 진단할 수 있게 한다.

### 4.2 핵심 테이블

```sql
-- 개념 노드 (3계층: 단원 > 소단원 > 세부개념)
CREATE TABLE concept (
    concept_id          UUID PRIMARY KEY,
    code                VARCHAR(64) UNIQUE NOT NULL,
    -- 'CAL-INT-DEF-FUNDAMENTAL' (미적분-적분-정적분-미적분학 기본정리)
    name_ko             VARCHAR(200) NOT NULL,      -- "미적분학의 기본정리"
    name_en             VARCHAR(200),
    aliases             TEXT[],                     -- ["FTC","Fundamental Theorem of Calculus"]

    -- 계층 정보
    level               concept_level_enum NOT NULL, -- 단원/소단원/세부개념
    parent_concept_id   UUID REFERENCES concept,    -- 상위 개념
    subject             subject_enum,
    curriculum_version  curriculum_enum,

    -- 교육과정 매핑
    -- grade_introduced·semester_introduced는 제거됨(2026-06-30·rev d1e2f3a4b5c6) —
    -- 교육과정 도입정보는 노드 내장이 아니라 curriculum_entry(Overlay·국가별 introduced_grade·
    -- required_depth)가 단일 진실이다(math_dsl_risk_register.md Q5·Q8 "노드는 의미만").

    -- 개념의 특성
    is_signature_korean BOOLEAN DEFAULT FALSE,      -- 한국 수능 특유 개념 여부
    cognitive_type      cognitive_type_enum[],
    -- ['DEFINITION','THEOREM','TECHNIQUE','PATTERN','VISUAL_REASONING']

    -- 난이도·중요도
    intrinsic_difficulty DECIMAL(3,2),              -- 개념 자체 난이도 1-5
    exam_frequency      DECIMAL(3,2),               -- 시험 출제 빈도 0-1
    weight_in_curriculum DECIMAL(3,2),              -- 교육과정 가중치

    -- 설명·예제
    description         TEXT,
    formal_definition   TEXT,                       -- 엄밀한 수학적 정의
    intuitive_explanation TEXT,                     -- 직관적 설명 (Socratic용)
    common_misconceptions JSONB,                    -- [{"misconception":"...", "correction":"..."}]

    -- 벡터 임베딩 (pgvector·Postgres 동거·슬98; embedding_id는 ChromaDB 잔재→통합 시 embedding 컬럼)
    embedding_id        UUID,                       -- §4.3 참조 (pgvector 통합 시 정리)

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 개념 관계 (DAG 엣지)
CREATE TABLE concept_edge (
    edge_id             UUID PRIMARY KEY,
    from_concept_id     UUID REFERENCES concept NOT NULL,
    to_concept_id       UUID REFERENCES concept NOT NULL,
    edge_type           edge_type_enum NOT NULL,
    -- PREREQUISITE: 선수 (A를 알아야 B를 안다)
    -- COMPOSED_OF: 구성 (A는 B,C,D로 이루어진다)
    -- ANALOGOUS_TO: 유사 (A와 B는 비슷한 사고)
    -- EXTENDS: 확장 (A를 일반화하면 B)
    -- CONTRASTS: 대조 (A와 B는 혼동하기 쉬움)

    edge_strength       DECIMAL(3,2),               -- 0-1 (관계의 강도)
    typical_gap_signal  TEXT,                       -- 이 엣지의 부재를 진단하는 신호
    -- "학생이 B를 이해 못한 가장 흔한 이유는 A를 모르는 것"

    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_concept_id, to_concept_id, edge_type)
);

-- 문제 ↔ 개념 매핑 (N:M)
CREATE TABLE problem_concept (
    problem_id          UUID REFERENCES problem,
    concept_id          UUID REFERENCES concept,
    relevance           DECIMAL(3,2),               -- 0-1 (개념과의 관련도)
    role                concept_role_enum,
    -- PRIMARY: 핵심 개념
    -- SUPPORTING: 보조 개념 (계산에 필요)
    -- IMPLICIT: 암묵적 사용 (학생이 의식하지 못해도 사용)
    -- TESTED: 평가 대상 개념 (이 문제로 학생의 이해도를 측정)

    PRIMARY KEY (problem_id, concept_id, role)
);

-- 단원 융합 패턴 (특성 #16)
CREATE TABLE concept_fusion (
    fusion_id           UUID PRIMARY KEY,
    name                VARCHAR(200),
    -- 예: "수열의 극한 + 부등식", "정적분 + 함수의 개형"
    concept_ids         UUID[] NOT NULL,            -- 융합되는 개념들
    fusion_difficulty   DECIMAL(3,2),               -- 융합 자체의 난이도
    typical_question_pattern TEXT,                  -- 이 융합이 출제되는 전형적 패턴
    exemplar_problem_ids UUID[]                     -- 대표 예제 문제
);

CREATE INDEX idx_concept_code ON concept(code);
CREATE INDEX idx_concept_parent ON concept(parent_concept_id);
CREATE INDEX idx_concept_level ON concept(level, subject);
CREATE INDEX idx_concept_edge_from ON concept_edge(from_concept_id, edge_type);
CREATE INDEX idx_concept_edge_to ON concept_edge(to_concept_id, edge_type);
CREATE INDEX idx_problem_concept_pc ON problem_concept(problem_id, concept_id);
```

### 4.3 pgvector 통합 (벡터 임베딩 — 슬98 결정)

벡터는 **별도 store가 아니라 PostgreSQL 16의 `pgvector` 확장**으로 *해당 테이블에 동거*한다 —
메타데이터(subject·exam_year·difficulty·level)가 이미 같은 행의 컬럼이라 *하이브리드 검색이
단일 SQL*이 된다(메타 중복·동기화 0). 6번째 store 회피·미성년 PII 통제 DB 유지. 대규모/고QPS
시 Qdrant 이관(지연 트리거). ChromaDB는 개발용(SQLite)이라 비채택.

```sql
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector (1회)

-- ① 개념 임베딩 (~2천 노드) — concept 테이블 동거 컬럼
ALTER TABLE concept ADD COLUMN embedding halfvec(3072);   -- text-embedding-3-large(3072)
CREATE INDEX ON concept USING hnsw (embedding halfvec_cosine_ops);

-- ② 문제 임베딩 (~100만) — problem 테이블 동거 (메타는 이미 컬럼)
ALTER TABLE problem ADD COLUMN embedding halfvec(3072);
CREATE INDEX ON problem USING hnsw (embedding halfvec_cosine_ops);
-- 하이브리드(메타 필터 + k-NN)를 *단일 쿼리*로:
--   SELECT problem_id FROM problem
--   WHERE subject = '미적분' AND exam_year >= 2022
--   ORDER BY embedding <=> :q LIMIT :k;

-- ③ 학생 상태 임베딩 (~100만 스냅샷) — user_state_snapshot 동거
ALTER TABLE user_state_snapshot ADD COLUMN embedding halfvec(1024);
CREATE INDEX ON user_state_snapshot USING hnsw (embedding halfvec_cosine_ops);
```

메모:
- **차원**: `vector`는 인덱스 ≤2000차원 → 3072/4096은 `halfvec`(반정밀·≤4000) 또는
  text-embedding-3-large `dimensions=1536` 축소. 임베딩 *모델* 확정(OpenAI 3072 vs BGE-M3
  1024 vs Qwen3-Embedding-8B 4096)은 *별개 결정*(차원만 위 호환 경로 따름).
- **`embedding_id` 필드**: 현 schema/ORM의 `embedding_id`(외부참조 UUID)는 ChromaDB 전제의
  잔재 — pgvector 동거에선 벡터 컬럼이 *같은 행*이라 외부 ID 불필요. 통합 슬라이스에서
  `embedding` 컬럼으로 대체·`embedding_id` 정리(후속).
- **거리/인덱스**: cosine(`<=>`)·HNSW(m·ef_construction 튜닝은 실측 후).

### 4.4 매핑된 특성

| 특성 # | 구현 위치 |
|---|---|
| #16 (단원 융합) | `concept_fusion`, `problem.is_cross_unit` |
| #21~24 (한국 시그니처) | `concept.is_signature_korean`, `signature_patterns` |
| #78 (고교학점제 진로 추천) | `concept` 그래프 탐색 |
| #79 (인공지능 수학) | `concept.subject = '인공지능수학'` |

---

## 5. 도메인 3: 학생 (User)

### 5.1 핵심 테이블: `user_profile`

```sql
CREATE TABLE user_profile (
    user_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ===== 기본 정보 (개인정보 보호) =====
    email_hash          VARCHAR(64) UNIQUE,         -- 해시 저장
    nickname            VARCHAR(50),
    birth_year          INTEGER,                    -- 연 단위만 (월일 X)
    gender              gender_enum,                -- 선택 입력

    -- ===== 학적 정보 (특성 #71~77) =====
    school_type         school_type_enum,
    -- 일반고/자사고/외고/국제고/영재고/과학고/대안학교/홈스쿨링/검정고시
    school_region       region_enum,                -- 강남/대치/지방/...
    school_id           UUID,                       -- 학교 ID (있는 경우만)
    grade               INTEGER,                    -- 10/11/12/13(N수1)/14(N수2)

    -- ===== 입시 트랙 (특성 #51~70) =====
    track_type          track_type_enum[],
    -- 정시/수시학종/수시교과/수시논술/MMI/특기자/농어촌/특례
    target_universities JSONB,
    -- [{"univ":"서울대","major":"의예","priority":1}, ...]
    target_major_category major_category_enum,
    -- 의대/약대/치대/한의대/이공계/인문계/경상계/예체능

    -- ===== 학습 목표 (특성 #28, #48) =====
    target_grade        INTEGER,                    -- 목표 등급 (1~9)
    target_score        INTEGER,                    -- 목표 표준점수
    target_exam_date    DATE,                       -- 목표 수능일

    -- ===== 페르소나 분류 (PRD 페르소나 5종) =====
    persona_primary     persona_enum NOT NULL,
    -- A_일반고고3 / B_자사고N수 / C_검정고시N수 / D_학종고2 / E_홈스쿨링영재
    persona_secondary   persona_enum,
    persona_confidence  DECIMAL(3,2),               -- 분류 신뢰도

    -- ===== 학습 환경 =====
    primary_device      device_enum,                -- 아이패드/iPhone/안드로이드폰/PC
    has_apple_pencil    BOOLEAN,
    note_app            note_app_enum,              -- 굿노트/노타빌리티/플렉슬/없음

    -- ===== 현재 학력 진단 (초기 + 갱신) =====
    current_grade_estimate DECIMAL(3,2),            -- 현재 등급 추정 (1.0-9.0)
    current_grade_updated_at TIMESTAMPTZ,
    diagnostic_completed BOOLEAN DEFAULT FALSE,
    diagnostic_completed_at TIMESTAMPTZ,

    -- ===== 사교육 사용 현황 =====
    uses_inkang         BOOLEAN,                    -- 인강 사용 여부
    inkang_provider     TEXT[],                     -- ['메가스터디','이투스']
    uses_offline_academy BOOLEAN,                   -- 오프라인 학원
    monthly_education_spend INTEGER,                -- 월 사교육비 (원)

    -- ===== 결제·구독 =====
    subscription_tier   subscription_tier_enum,     -- free/basic/premium
    subscription_started_at TIMESTAMPTZ,
    subscription_renewed_at TIMESTAMPTZ,

    -- ===== 보호자 정보 (특성 #94, 미성년자 보호) =====
    is_minor            BOOLEAN,
    parent_consent_at   TIMESTAMPTZ,
    parent_email_hash   VARCHAR(64),

    -- ===== 접근성 (특성 #47) =====
    accessibility_needs accessibility_enum[],
    -- 시각약자/색약/큰글씨/음성안내/시간연장

    -- ===== 운영 메타 =====
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    last_active_at      TIMESTAMPTZ,
    is_active           BOOLEAN DEFAULT TRUE,
    is_deleted          BOOLEAN DEFAULT FALSE,      -- GDPR/개인정보 삭제 요청 대응
    deleted_at          TIMESTAMPTZ
);

-- 학생 진로 변경 이력 (입시 1년 사이클에서 자주 바뀜)
CREATE TABLE user_track_history (
    history_id          UUID PRIMARY KEY,
    user_id             UUID REFERENCES user_profile,
    changed_at          TIMESTAMPTZ DEFAULT NOW(),
    track_before        JSONB,
    track_after         JSONB,
    reason              TEXT
);

-- 페르소나 분류 이력 (페르소나는 시간에 따라 변할 수 있음)
CREATE TABLE user_persona_history (
    user_id             UUID,
    detected_at         TIMESTAMPTZ,
    persona             persona_enum,
    confidence          DECIMAL(3,2),
    signals             JSONB,                      -- 어떤 행동 신호로 판정했는지
    PRIMARY KEY (user_id, detected_at)
);

CREATE INDEX idx_user_persona ON user_profile(persona_primary);
CREATE INDEX idx_user_school ON user_profile(school_type, grade);
CREATE INDEX idx_user_target ON user_profile(target_major_category);
CREATE INDEX idx_user_active ON user_profile(is_active, last_active_at);
```

### 5.2 학생 학습 상태 스냅샷

```sql
-- 학생의 시점별 학습 상태 (페르소나 임베딩 + 진단 결과)
CREATE TABLE user_state_snapshot (
    snapshot_id         UUID PRIMARY KEY,
    user_id             UUID REFERENCES user_profile,
    snapshot_at         TIMESTAMPTZ DEFAULT NOW(),

    -- 종합 학력
    estimated_grade     DECIMAL(3,2),               -- 추정 등급
    estimated_score     INTEGER,                    -- 추정 표준점수
    estimated_percentile DECIMAL(5,2),              -- 추정 백분위

    -- 단원별 숙련도 (특성 #16, #44)
    concept_mastery     JSONB,
    -- {"CAL-INT-DEF": 0.8, "FUN-COMPOSITE": 0.5, ...}

    -- 시그니처 패턴별 숙련도
    pattern_mastery     JSONB,
    -- {"COMPOSITE_DIFFERENTIABILITY": 0.6, "INDUCTIVE_SEQUENCE": 0.3, ...}

    -- 시간 관리 능력
    avg_solve_time_by_difficulty JSONB,
    -- {"easy": 60, "medium": 180, "hard": 600} (초)
    time_management_score DECIMAL(3,2),             -- 0-1

    -- 멘탈·컨디션 신호
    consecutive_active_days INTEGER,                -- 연속 학습일
    avg_session_quality DECIMAL(3,2),               -- 집중도 평균

    -- 임베딩 (pgvector·Postgres 동거·슬98; 통합 시 embedding halfvec 컬럼·embedding_id는 잔재)
    embedding_id        UUID
);

CREATE INDEX idx_snapshot_user_time ON user_state_snapshot(user_id, snapshot_at DESC);
```

### 5.3 매핑된 특성

| 특성 # | 필드 |
|---|---|
| #27, #61 | `grade` (재학생/N수생) |
| #28, #48 | `target_major_category`, `target_universities` |
| #47 | `accessibility_needs` |
| #71~77 | `school_type` |
| #87 | `school_region` (지방·도시 격차 분석) |
| #94 | `parent_consent_at` |
| #95 | `primary_device`, `has_apple_pencil` |

---

## 6. 도메인 4: 학습 활동 (Activity)

### 6.1 핵심 테이블

```sql
-- 학습 세션 (한 번 앱 열고 닫을 때까지)
CREATE TABLE learning_session (
    session_id          UUID PRIMARY KEY,
    user_id             UUID REFERENCES user_profile,
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    duration_seconds    INTEGER,

    session_type        session_type_enum,
    -- 자유학습/실전모의고사/단원집중/약점보완/AI추천

    target_concept_id   UUID,                       -- 이번 세션의 학습 목표
    problems_attempted  INTEGER,
    problems_completed  INTEGER,
    problems_correct    INTEGER,

    -- 세션 품질 신호
    focus_score         DECIMAL(3,2),               -- 집중도 (앱 전환·지연 분석)
    engagement_score    DECIMAL(3,2),               -- Socratic 응답 적극성

    device_used         device_enum,
    network_type        VARCHAR(20)
);

-- 문항 풀이 시도 (한 문제 풀이 시작 ~ 종료)
CREATE TABLE problem_attempt (
    attempt_id          UUID PRIMARY KEY,
    user_id             UUID REFERENCES user_profile,
    session_id          UUID REFERENCES learning_session,
    problem_id          UUID REFERENCES problem,

    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    duration_seconds    INTEGER,                    -- 실제 풀이 시간

    -- 결과
    is_correct          BOOLEAN,
    student_answer      TEXT,                       -- 학생이 제출한 답
    confidence_self_reported DECIMAL(3,2),          -- 학생 자기 평가

    -- 풀이 방식
    attempt_mode        attempt_mode_enum,
    -- 자유풀이/Socratic대화/힌트제공/풀이공개
    used_socratic       BOOLEAN,
    used_hint           BOOLEAN,
    used_solution_view  BOOLEAN,                    -- 풀이 보기 사용 여부

    -- 풀이 이미지/PDF (특성 #95)
    handwriting_uri     TEXT,                       -- 손글씨 풀이 (MinIO URI)
    ocr_result          JSONB,                      -- OCR 인식 결과

    -- 막힌 지점 분석
    stuck_at_step       INTEGER,                    -- 어느 단계에서 막혔는지
    stuck_at_concept_id UUID,                       -- 막힌 개념

    -- 시간 관리
    time_vs_expected    DECIMAL(4,2),               -- 예상 시간 대비 비율
    -- 1.0 = 평균, 2.0 = 평균의 2배 (느림), 0.5 = 빠름

    -- 풀이 단계별 시간 (특성 #42)
    step_times          JSONB,
    -- [{"step":1, "seconds":30}, {"step":2, "seconds":120}, ...]

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 학생 풀이 단계 이벤트 (실시간 분석용, TimescaleDB)
CREATE TABLE attempt_event (
    event_id            BIGSERIAL,                  -- 시계열용
    attempt_id          UUID,
    user_id             UUID,
    problem_id          UUID,
    event_at            TIMESTAMPTZ NOT NULL,
    event_type          event_type_enum,
    -- 문제읽기/조건분석/그래프그리기/계산/지움/막힘/힌트요청/답입력
    event_data          JSONB,
    PRIMARY KEY (event_id, event_at)
);

-- TimescaleDB hypertable 변환
SELECT create_hypertable('attempt_event', 'event_at',
                         chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_session_user ON learning_session(user_id, started_at DESC);
CREATE INDEX idx_attempt_user ON problem_attempt(user_id, started_at DESC);
CREATE INDEX idx_attempt_problem ON problem_attempt(problem_id);
CREATE INDEX idx_attempt_stuck ON problem_attempt(stuck_at_concept_id) WHERE stuck_at_concept_id IS NOT NULL;
```

### 6.2 매핑된 특성

| 특성 # | 필드 |
|---|---|
| #2, #42 | `duration_seconds`, `step_times`, `time_vs_expected` |
| #39 | `handwriting_uri`, `ocr_result` |
| #91 | `attempt_mode = '실전모의고사'` (시뮬레이션) |
| #95 | `handwriting_uri`, OCR 처리 |
| #96 | `used_socratic` vs `used_solution_view` (콴다 vs WhyMath 차별 측정) |

---

## 7. 도메인 5: Socratic 대화 (Dialogue)

### 7.1 핵심 테이블

```sql
-- Socratic 대화 세션 (한 문제 풀이 중의 대화)
CREATE TABLE dialogue (
    dialogue_id         UUID PRIMARY KEY,
    user_id             UUID REFERENCES user_profile,
    attempt_id          UUID REFERENCES problem_attempt,
    problem_id          UUID REFERENCES problem,
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,

    -- 대화 결과
    resolution          resolution_enum,
    -- 학생자력해결/Socratic유도성공/힌트필요/풀이공개로종결/포기

    total_turns         INTEGER,
    student_turns       INTEGER,
    assistant_turns     INTEGER,

    -- LLM 사용량
    model_used          VARCHAR(50),                -- 'claude-opus-4-7' / 'qwen3-32b-local'
    total_tokens        INTEGER,
    estimated_cost_usd  DECIMAL(8,4),

    -- 품질 평가
    student_rating      INTEGER,                    -- 1-5 (학생 평가)
    auto_quality_score  DECIMAL(3,2),               -- 자동 평가 점수
    flagged_for_review  BOOLEAN DEFAULT FALSE       -- 검수 필요 플래그
);

-- 대화 턴 (한 번의 학생↔AI 교환)
CREATE TABLE dialogue_turn (
    turn_id             UUID PRIMARY KEY,
    dialogue_id         UUID REFERENCES dialogue,
    turn_order          INTEGER NOT NULL,
    spoken_at           TIMESTAMPTZ DEFAULT NOW(),

    role                turn_role_enum,             -- student / assistant / system
    content             TEXT,
    content_type        content_type_enum,          -- 텍스트/수식/이미지/혼합

    -- AI 응답인 경우의 메타데이터
    socratic_strategy   socratic_strategy_enum,
    -- 조건확인/예시제시/반례제시/단계분해/유사문제/그래프그리기제안

    targeted_step       INTEGER,                    -- 어느 풀이 단계를 향한 응답인지
    targeted_concept_id UUID,                       -- 어느 개념을 다루는지

    -- 학생 응답 분석
    student_intent      student_intent_enum,
    -- 답시도/질문/막힘표현/포기/이해확인
    student_understanding_signal DECIMAL(3,2),      -- 이해 수준 신호

    -- 멀티모달
    image_uri           TEXT,                       -- 손글씨 풀이 이미지
    image_analysis      JSONB,                      -- Qwen3-VL 분석 결과

    UNIQUE(dialogue_id, turn_order)
);

CREATE INDEX idx_dialogue_user ON dialogue(user_id, started_at DESC);
CREATE INDEX idx_dialogue_problem ON dialogue(problem_id);
CREATE INDEX idx_turn_dialogue ON dialogue_turn(dialogue_id, turn_order);
```

### 7.2 매핑된 특성

| 특성 # | 구현 |
|---|---|
| #8, #18 | `socratic_strategy = '조건확인'` (조건 나열형 발문 파서) |
| #21 | `socratic_strategy = '단계분해'` (합성함수 케이스 분류) |
| #23 | 귀납적 수열 추적 시 다회 턴 사용 |
| #96 | `dialogue.resolution`이 콴다와의 차별화 핵심 지표 |

---

## 8. 도메인 6: 학습 진단 (Assessment)

### 8.1 핵심 테이블

```sql
-- 진단 평가 (초기 진단 + 주기적 재진단)
CREATE TABLE assessment (
    assessment_id       UUID PRIMARY KEY,
    user_id             UUID REFERENCES user_profile,
    assessment_type     assessment_type_enum,
    -- 초기진단/주간진단/단원진단/실전모의고사/D-100예측

    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,

    -- 종합 결과
    estimated_grade     DECIMAL(3,2),
    estimated_score     INTEGER,
    estimated_percentile DECIMAL(5,2),

    -- 합격 예측 (특성 #86)
    target_university_id UUID,
    admission_probability DECIMAL(3,2),             -- 0-1

    -- 단원·패턴별 진단
    concept_diagnosis   JSONB,
    -- [{"concept_id":"...", "mastery":0.7, "trend":"+0.1"}, ...]
    pattern_diagnosis   JSONB,
    weak_points         JSONB,                      -- 약점 단원/개념 TOP 5
    strong_points       JSONB,                      -- 강점

    -- 권장 학습 경로 (특성 #78)
    recommended_path    JSONB,
    -- [{"week":1, "concept":"...", "estimated_hours":5}, ...]

    -- 멘탈·시간 관리 (특성 #50)
    mental_phase        mental_phase_enum,
    -- D_100_PLUS / D_100_50 / D_50_30 / D_30_7 / D_7_0 / 평상시

    notes               TEXT
);

-- 단원별 숙련도 변화 추적
CREATE TABLE concept_mastery_history (
    user_id             UUID,
    concept_id          UUID,
    measured_at         TIMESTAMPTZ,
    mastery             DECIMAL(3,2),               -- 0-1
    confidence          DECIMAL(3,2),               -- 측정 신뢰도
    sample_size         INTEGER,                    -- 이 측정의 근거가 된 문제 수
    PRIMARY KEY (user_id, concept_id, measured_at)
);

SELECT create_hypertable('concept_mastery_history', 'measured_at',
                         chunk_time_interval => INTERVAL '7 days');
```

### 8.2 매핑된 특성

| 특성 # | 필드 |
|---|---|
| #14, #15, #45 | `estimated_grade`, `estimated_score`, `estimated_percentile` |
| #29 | 만점자 수 / 등급 추정 |
| #50 | `mental_phase` (D-100 코칭) |
| #86 | `admission_probability` (합격 예측) |

---

## 9. 도메인 7: 시간 시계열 (Time Series)

### 9.1 TimescaleDB 전용 테이블

```sql
-- 일별 학습 활동 집계 (자동 집계)
CREATE TABLE daily_learning_metrics (
    user_id             UUID,
    metric_date         DATE,
    minutes_active      INTEGER,
    problems_attempted  INTEGER,
    problems_correct    INTEGER,
    socratic_turns      INTEGER,
    concepts_practiced  TEXT[],                     -- 단원 코드 배열
    avg_focus_score     DECIMAL(3,2),
    PRIMARY KEY (user_id, metric_date)
);

SELECT create_hypertable('daily_learning_metrics', 'metric_date',
                         chunk_time_interval => INTERVAL '30 days');

-- 풀이 시간 분포 (문항별, 페르소나별)
CREATE TABLE problem_solve_time_distribution (
    problem_id          UUID,
    persona             persona_enum,
    measured_at         TIMESTAMPTZ,
    p10_seconds         INTEGER,                    -- 상위 10% 학생
    p50_seconds         INTEGER,                    -- 중앙값
    p90_seconds         INTEGER,                    -- 하위 10%
    sample_size         INTEGER,
    PRIMARY KEY (problem_id, persona, measured_at)
);

SELECT create_hypertable('problem_solve_time_distribution', 'measured_at',
                         chunk_time_interval => INTERVAL '7 days');

-- 학생 학습 행동 시계열 (페르소나 변화·이탈 예측)
CREATE TABLE user_behavior_metrics (
    user_id             UUID,
    measured_at         TIMESTAMPTZ,
    metric_name         VARCHAR(50),                -- session_length / streak / churn_risk
    metric_value        DECIMAL(10,4),
    PRIMARY KEY (user_id, metric_name, measured_at)
);

SELECT create_hypertable('user_behavior_metrics', 'measured_at',
                         chunk_time_interval => INTERVAL '7 days');
```

### 9.2 매핑된 특성

| 특성 # | 활용 |
|---|---|
| #40 (1년 사이클) | 3-6-9-11월 패턴 분석 |
| #42 (시간 배분) | `problem_solve_time_distribution` |
| #50 (D-100 멘탈) | 시계열 행동 변화 감지 |

---

## 10. 도메인 8: 콘텐츠 변형·생성 이력 (Provenance)

### 10.1 핵심 테이블 (특성 #36, #37, #11 핵심)

```sql
-- 콘텐츠 생성·변형 이력 (감사 추적)
CREATE TABLE content_provenance (
    provenance_id       UUID PRIMARY KEY,
    problem_id          UUID REFERENCES problem,

    -- 원본 출처
    original_source     source_type_enum,           -- 평가원/EBS/AIHub
    original_reference  JSONB,                      -- {"year":2025, "exam":"수능", "number":30}

    -- 변형·생성 단계
    generation_type     generation_type_enum,
    -- ORIGINAL: 원본 그대로
    -- VARIANT_NUMBER: 숫자만 변형
    -- VARIANT_STRUCTURE: 구조 변형
    -- VARIANT_CONTEXT: 맥락 변형 (조건 변경)
    -- COMPOSED: 여러 문제 결합
    -- FULLY_GENERATED: AI 완전 생성

    -- 변형 메타데이터
    transformation      JSONB,
    -- {"operations": [{"type":"swap_numbers", "from":3, "to":5}, ...]}
    parent_problem_id   UUID REFERENCES problem,    -- 원본 문제 (변형의 경우)
    transformation_pipeline JSONB,
    -- {"steps": ["Qwen3-32B 초안", "Claude 검증", "사람 검수"]}

    -- 검증·승인
    auto_validation     JSONB,                      -- 자동 검증 결과
    human_review        JSONB,                      -- 사람 검수 결과
    -- {"reviewer_id":"...", "score":4.5, "comments":"..."}
    approved_at         TIMESTAMPTZ,
    approved_by         UUID,

    -- 저작권·법적 메타데이터
    license             license_enum,
    -- PUBLIC_DOMAIN / EBS_LICENSED / AIHUB_OPEN / WHYMATH_GENERATED
    copyright_notice    TEXT,
    usage_restrictions  JSONB,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 생성 이력 (LLM 호출 추적, 비용·품질 분석)
CREATE TABLE generation_log (
    log_id              UUID PRIMARY KEY,
    problem_id          UUID REFERENCES problem,
    provenance_id       UUID REFERENCES content_provenance,

    model_name          VARCHAR(64),                -- 'qwen3-32b' / 'claude-opus-4-7'
    prompt_template_id  UUID,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cost_usd            DECIMAL(8,4),
    latency_ms          INTEGER,
    success             BOOLEAN,
    error_detail        TEXT,
    generated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_provenance_problem ON content_provenance(problem_id);
CREATE INDEX idx_provenance_parent ON content_provenance(parent_problem_id);
CREATE INDEX idx_provenance_source ON content_provenance(original_source);
CREATE INDEX idx_generation_problem ON generation_log(problem_id);
```

### 10.2 매핑된 특성

| 특성 # | 구현 |
|---|---|
| #11 | `license = 'EBS_LICENSED'`, EBS 저작권 준수 |
| #33 | `human_review` (출제오류 검증) |
| #36 | `generation_type = 'FULLY_GENERATED'` (AI 모의고사 무한 생성) |
| #37 | `parent_problem_id` (자작·변형 문화 디지털화) |


---

## 11. DB 분산 전략

### 11.1 DB 역할 분담 (TimescaleDB·pgvector는 Postgres 16 확장·슬98)

| DB | 역할 | 데이터 |
|---|---|---|
| **PostgreSQL** | 트랜잭션·관계 데이터의 진실 원천 | Problem, Concept, User, Assessment, Dialogue (요약), Provenance |
| **TimescaleDB** (PG 확장) | 고빈도 시계열 데이터 | attempt_event, daily_metrics, mastery_history, behavior_metrics |
| **pgvector** (PG 확장) | 벡터 임베딩 의미 검색 — 메타 동거 하이브리드(단일 SQL) | concept·problem·user_state_snapshot의 `embedding` 컬럼 |

### 11.2 데이터 흐름

```
[학생 풀이 시작]
    │
    ▼
[Postgres: problem_attempt INSERT]
    │
    ▼
[학생 풀이 진행 (15분)]
    │
    └─► [TimescaleDB: attempt_event 초당 1-10건]
    │
    ▼
[학생 막힘 → Socratic 호출]
    │
    └─► [pgvector(Postgres 동거): problem.embedding 유사 문제 검색 — 메타 필터 단일 SQL]
    │
    └─► [Postgres: dialogue + dialogue_turn INSERT]
    │
    ▼
[학생 풀이 완료]
    │
    └─► [Postgres: problem_attempt UPDATE (결과)]
    │
    └─► [TimescaleDB: daily_learning_metrics 배치 집계 (자정)]
    │
    └─► [Postgres: concept_mastery_history UPDATE]
    │
    └─► [pgvector(Postgres 동거): user_state_snapshot.embedding UPDATE (시간당 배치)]
```

### 11.3 트랜잭션·일관성 전략

- **Postgres 내부**: ACID 트랜잭션 (예: `problem_attempt` + `dialogue` 동시 INSERT)
- **Postgres ↔ TimescaleDB**: TimescaleDB는 Postgres 확장이므로 같은 트랜잭션 사용 가능
- **Postgres ↔ pgvector**: pgvector도 Postgres 확장(벡터 동거)이라 같은 트랜잭션 가능 — 단 임베딩 *생성*(모델 호출)은 비동기 → `embedding` 컬럼 지연 채움 허용(Eventual Consistency)
  - 5분 이내 일관성 보장이면 충분
  - 임베딩 생성 실패해도 메인 트랜잭션은 성공 (`embedding` NULL→후속 배치 채움)

### 11.4 백업·복구

| DB | 백업 주기 | 복구 시간 목표 (RTO) | 복구 시점 목표 (RPO) |
|---|---|---|---|
| PostgreSQL | 일 1회 풀백업 + 시간당 WAL | 1시간 | 1시간 |
| TimescaleDB | 일 1회 (오래된 청크 압축) | 4시간 | 1일 |
| pgvector (Postgres 동거) | PostgreSQL 백업에 포함 (별도 불필요) | — | — (`embedding`은 재생성 가능) |

---

## 12. 인덱스·성능 전략

### 12.1 핵심 쿼리 패턴

```sql
-- 패턴 1: 페르소나 + 약점 단원 기반 문제 추천
-- (가장 빈번한 쿼리, 1초 이내 응답 필수)
SELECT p.*
FROM problem p
WHERE
    -- 페르소나 적합도 0.7 이상
    (p.persona_fit->>'A_일반고고3')::DECIMAL >= 0.7
    -- 학생 약점 단원 포함
    AND p.unit_codes && ARRAY['CAL-INT-DEF', 'FUN-COMPOSITE']
    -- 난이도 학생 수준 + 0.5
    AND p.difficulty_overall BETWEEN 3.0 AND 4.0
    -- 한국 시그니처 패턴 포함
    AND 'COMPOSITE_DIFFERENTIABILITY' = ANY(p.signature_patterns)
    AND p.is_published = TRUE
ORDER BY
    -- 평가원 가중치 우선
    p.exam_authority_weight DESC,
    -- 학생이 안 푼 문제 우선
    NOT EXISTS (SELECT 1 FROM problem_attempt pa
                WHERE pa.user_id = ? AND pa.problem_id = p.problem_id)
LIMIT 20;
```

**필요 인덱스**:
- `idx_problem_persona_fit` (GIN on JSONB)
- `idx_problem_signature` (GIN on enum array)
- `idx_problem_subject_unit` (GIN on text array)
- `idx_problem_difficulty` (B-tree)

### 12.2 파티셔닝 전략

```sql
-- problem 테이블: 교육과정 버전별 파티션
CREATE TABLE problem_2015 PARTITION OF problem
    FOR VALUES IN ('2015_REVISION');
CREATE TABLE problem_2022 PARTITION OF problem
    FOR VALUES IN ('2022_REVISION');

-- problem_attempt: 월별 파티션
-- (수능 직전 11월 데이터가 가장 큼)
CREATE TABLE problem_attempt_y2026m11 PARTITION OF problem_attempt
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

-- TimescaleDB 자동 청크 (이미 hypertable로 처리)
```

### 12.3 캐싱 전략 (Redis)

| 캐시 키 | 데이터 | TTL |
|---|---|---|
| `user:{uid}:state` | 학생 학습 상태 스냅샷 | 5분 |
| `user:{uid}:weakness` | 약점 단원 TOP 5 | 30분 |
| `concept:graph` | 전체 개념 그래프 (DAG) | 1일 |
| `problem:{pid}:full` | 문제 + 풀이 + 메타데이터 | 1시간 |
| `recommendation:{uid}` | 다음 추천 문제 20개 | 10분 |

---

## 13. 데이터 거버넌스

### 13.1 개인정보 보호 (특성 #94)

- **PII 분리**: `email_hash`, `parent_email_hash` 등 해시 저장
- **연 단위 출생년도**만 저장 (월일 X)
- **삭제 요청 대응**: `is_deleted = TRUE` 플래그 + 90일 후 물리 삭제
- **미성년자 보호**: `is_minor = TRUE`인 경우 `parent_consent_at` 필수

### 13.2 저작권 관리

```sql
-- 콘텐츠 저작권 정책
CREATE TYPE license_enum AS ENUM (
    'PUBLIC_DOMAIN',          -- 평가원 공개 자료
    'EBS_LICENSED',           -- EBS 라이선스 (사용 협의 필요)
    'AIHUB_OPEN',             -- AIHub 공개 데이터셋
    'WHYMATH_GENERATED',      -- 자체 생성 (저작권 WhyMath)
    'USER_GENERATED',         -- 사용자 자작 (특성 #37)
    'THIRD_PARTY_LICENSED'    -- 사설 모의고사 협업
);
```

### 13.3 데이터 품질 (특성 #33)

- 모든 `problem`은 `review_status = 'approved'` 후 노출
- 정답 검증 시 `multiple_answers` 존재 확인 (복수해 가능성)
- 분기 1회 인간 검수자가 전체 문제 5% 무작위 샘플 재검수

### 13.4 감사 추적

```sql
-- 모든 critical 테이블의 변경 이력
CREATE TABLE audit_log (
    audit_id            BIGSERIAL PRIMARY KEY,
    table_name          VARCHAR(64),
    record_id           UUID,
    action              VARCHAR(20),                -- INSERT/UPDATE/DELETE
    changed_by          UUID,
    changed_at          TIMESTAMPTZ DEFAULT NOW(),
    diff                JSONB                       -- 변경 전후 차이
);
```

---

## 14. 마이그레이션·확장성

### 14.1 2028 수능 대개편 대응 (특성 #30, #80)

스키마 자체는 `curriculum_version` 필드로 이미 대응 가능. 추가 작업:

1. **2022 개정 콘텐츠 신규 INSERT** (기존 데이터 유지)
2. **`concept` 테이블 확장**: 행렬·복소수 단원 노드 추가
3. **`signature_patterns` ENUM 확장**: 새 시그니처 패턴 추가
4. **`problem.valid_to_year` 설정**: 2027 수능 마지막 적용 콘텐츠

### 14.2 확장성 시나리오

| 시나리오 | 대응 전략 |
|---|---|
| 사용자 100만 명 돌파 | `user_profile` 샤딩 (region 기준) |
| 풀이 이벤트 100억 건 | TimescaleDB 압축 + 1년 이전 데이터 콜드 스토리지 |
| 새로운 페르소나 추가 | `persona_enum` 확장 (예: 페르소나 F) |
| 글로벌 확장 (v3.0) | `country` 필드 추가, 다국어 콘텐츠 |
| 대학 입시 외 시장 (PSAT, CPA) | `exam_type_enum` 확장 |

### 14.3 ENUM 정의 (참고)

```sql
-- 주요 ENUM 타입 정의 (생성 시 실행)
CREATE TYPE source_type_enum AS ENUM (
    '평가원', 'EBS', 'AIHub', '교육청학평', '사설모의고사',
    '자체생성', '사용자자작', '교과서'
);

CREATE TYPE persona_enum AS ENUM (
    'A_일반고고3', 'B_자사고N수', 'C_검정고시N수',
    'D_학종고2', 'E_홈스쿨링영재'
);

CREATE TYPE signature_pattern_enum AS ENUM (
    'CONDITION_LIST',                   -- (가)(나)(다) 조건 나열
    'COMPOSITE_DIFFERENTIABILITY',      -- 합성함수 미분가능성
    'INDUCTIVE_SEQUENCE',               -- 귀납적 수열
    'DEFINED_INTEGRAL_FUNCTION',        -- 정적분 정의 함수
    'FUNCTION_COUNT',                   -- 함수 개수 문제
    'GRAPH_SHAPE_INFERENCE',            -- 그래프 개형 추론
    'CASE_ANALYSIS_DEEP',               -- 깊은 케이스 분류
    'CROSS_UNIT_FUSION',                -- 단원 융합
    'NATURAL_NUMBER_TRANSFORM',         -- 자연수 답 변환
    'COMPOUND_CHOICES'                  -- 합답형 ㄱㄴㄷ
);

CREATE TYPE curriculum_enum AS ENUM (
    '2009_REVISION',
    '2015_REVISION',
    '2022_REVISION'
);

CREATE TYPE school_type_enum AS ENUM (
    '일반고', '자사고_전국', '자사고_광역', '외고', '국제고',
    '영재고', '과학고', '특성화고', '대안학교_인가',
    '대안학교_비인가', '홈스쿨링', '검정고시'
);
```

---

## 부록 A: 페르소나별 데이터 활용 시나리오

### 페르소나 A: 일반고 고3 김민준

```python
# 시나리오: 30번 문항 막힘 → 약점 진단 → 추천
def diagnose_and_recommend(user_id):
    # 1. 학생 페르소나 + 학습 상태 조회 (Postgres)
    state = postgres.query("""
        SELECT persona_primary, current_grade_estimate
        FROM user_profile WHERE user_id = ?
    """, user_id)
    # → persona_primary='A_일반고고3', grade_estimate=3.2

    # 2. 최근 30번 풀이 패턴 분석 (Postgres + TimescaleDB)
    recent_struggles = postgres.query("""
        SELECT problem_id, stuck_at_concept_id, duration_seconds
        FROM problem_attempt
        WHERE user_id = ? AND problem_number = 30
        AND is_correct = FALSE
        ORDER BY started_at DESC LIMIT 10
    """, user_id)

    # 3. 약점 개념 추출
    weak_concepts = aggregate(recent_struggles, key='stuck_at_concept_id')
    # → {'COMPOSITE_DIFFERENTIABILITY': 8회 막힘}

    # 4. 개념 그래프에서 선수 개념 탐색 (Postgres)
    prerequisites = postgres.query("""
        SELECT c.concept_id, c.name_ko
        FROM concept c
        JOIN concept_edge ce ON c.concept_id = ce.from_concept_id
        WHERE ce.to_concept_id = ? AND ce.edge_type = 'PREREQUISITE'
    """, weak_concept_id)

    # 5. pgvector로 유사한 학생들의 회복 경로 탐색 (메타 필터+k-NN 단일 SQL·Postgres 동거)
    similar_students = postgres.query("""
        SELECT snapshot_id, user_id
        FROM user_state_snapshot
        WHERE persona = 'A_일반고고3' AND recovered_from = 'COMPOSITE_DIFF'
        ORDER BY embedding <=> ?   -- cosine 거리(동일 행 메타 필터와 한 쿼리)
        LIMIT 100
    """, user_embedding)

    # 6. 추천 문제 생성
    recommended = postgres.query("""
        SELECT * FROM problem
        WHERE persona_fit->>'A_일반고고3' >= '0.7'
        AND signature_patterns && ARRAY['COMPOSITE_DIFFERENTIABILITY']
        AND difficulty_overall BETWEEN 2.5 AND 3.5
        ORDER BY exam_authority_weight DESC LIMIT 5
    """)

    return {
        'diagnosis': weak_concepts,
        'recommended_concepts_to_review': prerequisites,
        'next_problems': recommended,
        'similar_student_paths': similar_students
    }
```

### 페르소나 D: 학종 고2 최예린 — 자유연구 추천

```python
def recommend_research_topic(user_id):
    # 1. 학생의 강점 단원 + 진로 조회
    profile = postgres.query("""
        SELECT
            target_major_category,
            (SELECT jsonb_object_agg(key, value)
             FROM jsonb_each_text((SELECT concept_mastery FROM user_state_snapshot
                                    WHERE user_id = ? ORDER BY snapshot_at DESC LIMIT 1))
             WHERE value::DECIMAL > 0.7) AS strong_concepts
        FROM user_profile WHERE user_id = ?
    """, user_id, user_id)
    # → target_major: AI, strong_concepts: ['PROB-BAYES', 'STAT-DIST']

    # 2. 자유연구 주제 생성 (개념 + 진로 결합)
    topics = generate_research_topics(
        strong_concepts=profile.strong_concepts,
        target_major=profile.target_major_category
    )
    # → ["베이즈 정리의 의료 진단 응용",
    #    "확률 분포로 본 SNS 인플루언서 영향력",
    #    ...]

    return topics
```

---

## 부록 B: 100가지 특성 ↔ 스키마 매핑 매트릭스

| 특성 # | 도메인 | 핵심 필드 |
|---|---|---|
| #1 공통+선택 | Problem | `subject` |
| #2 30문항/100분 | Problem, Activity | `expected_solve_seconds`, `duration_seconds` |
| #3 차등 배점 | Problem | `points` |
| #4 15·22·30번 | Problem | `problem_number`, `tags=['킬러']` |
| #7 합답형 | Problem | `question_format='합답형'` |
| #8 조건해석 변별 | Problem | `signature_patterns='CONDITION_LIST'` |
| #9 그래프+케이스 | Problem | `has_visual`, `requires_graph_sketch` |
| #11 EBS 50% | Problem, Provenance | `ebs_linked`, `ebs_source` |
| #12 6·9월 모평 | Problem | `exam_authority_weight` |
| #13 단답형 자연수 | Problem | `answer_constraint`, `answer_transform` |
| #14 표준점수 | Assessment | `estimated_score`, `estimated_percentile` |
| #16 단원 융합 | Concept | `concept_fusion`, `is_cross_unit` |
| #18 조건 나열형 | Problem | `has_condition_list`, `conditions_parsed` |
| #20 2015→2022 개정 | Problem, Concept | `curriculum_version` |
| #21~24 시그니처 | Problem, Concept | `signature_patterns`, `is_signature_korean` |
| #25 자연수 변환 | Problem | `answer_transform` |
| #27 N수생 | User | `grade=13/14` |
| #28 의대 쏠림 | User | `target_major_category='의대'` |
| #29 만점자 = 난이도 | Problem | `historical_correct_rate` |
| #33 출제오류 | Problem, Provenance | `multiple_answers`, `human_review` |
| #36 사설 모의고사 | Provenance | `generation_type='FULLY_GENERATED'` |
| #37 자작 문화 | Problem, Provenance | `license='USER_GENERATED'` |
| #39 OCR 분석 | Activity | `handwriting_uri`, `ocr_result` |
| #40 1년 사이클 | Time Series | `daily_learning_metrics` |
| #42 시간 배분 | Activity | `step_times`, `time_vs_expected` |
| #47 접근성 | User | `accessibility_needs` |
| #48 의대 정원 | User | `target_major_category` |
| #49 내신 + 수능 | User, Problem | `track_type`, `exam_type` |
| #50 D-100 멘탈 | Assessment | `mental_phase` |
| #61~62 학종·세특 | User, Activity | `track_type='수시학종'` |
| #71~77 고교 유형 | User | `school_type` |
| #78 고교학점제 | User, Concept | `track_type`, 진로별 개념 추천 |
| #79 인공지능 수학 | Concept | `subject='인공지능수학'` |
| #80 2028 개편 | All | `curriculum_version='2022_REVISION'` |
| #86 모의지원 | Assessment | `admission_probability` |
| #91 시험장 환경 | Activity | `session_type='실전모의고사'` |
| #94 학부모 | User | `parent_consent_at` |
| #95 아이패드 환경 | User, Activity | `primary_device`, `handwriting_uri` |
| #96 콴다 차별 | Dialogue | `resolution` (Socratic vs 풀이공개) |
| #98 자유연구 | Concept, User | 강점 단원 + 진로 매칭 |
| #100 진로 시장 | User | `target_major_category` |

---

## 부록 C: 구현 우선순위

### Phase 1: MVP (v1.0, 3개월)
- [ ] PostgreSQL 스키마 전체 생성
- [ ] `problem`, `concept`, `user_profile`, `problem_attempt`, `dialogue` 5개 핵심 테이블 작동
- [ ] pgvector 확장 설치 + `concept`·`problem` `embedding` 컬럼·HNSW 인덱스(cosine) 구축
- [ ] TimescaleDB `attempt_event` hypertable 운영
- [ ] 평가원 30년치 데이터 ETL

### Phase 2: v1.5 (6개월)
- [ ] `assessment`, `concept_mastery_history` 시계열 분석
- [ ] `content_provenance` 저작권·생성 이력 관리
- [ ] 페르소나 자동 분류 (`user_persona_history`)
- [ ] 세특·자유연구 추천 모듈

### Phase 3: v2.0 (12개월)
- [ ] 2022 개정 교육과정 콘텐츠 마이그레이션
- [ ] 수리논술 풀이 평가 (`dialogue_turn.image_analysis` 확장)
- [ ] 합격 예측 모델 (`assessment.admission_probability`)

### Phase 4: v3.0 (24개월)
- [ ] 글로벌 확장 (다국어 콘텐츠)
- [ ] 음성 Socratic (`dialogue_turn.content_type='audio'`)
- [ ] 대학 미적분학 보충

---

## 문서 끝

이 스키마는 한국 수학 입시 시장의 100가지 특성을 모두 흡수할 수 있도록 설계되었다.
8개 도메인, 약 25개 핵심 테이블, 3개 DB로 분산되며, 5년 운영 후에도 확장성을 유지한다.

핵심 통찰:
1. **`problem` 테이블의 50+ 메타데이터**가 외산 데이터셋과의 차별화 본질
2. **개념 그래프 (`concept_edge`)**가 단원 융합·약점 진단의 토대
3. **`persona_fit` JSONB**가 5종 페르소나별 맞춤 추천의 핵심
4. **`content_provenance`** 추적이 저작권·법적 안전성 + 자체 모트 확보
5. **TimescaleDB의 행동 시계열**이 D-100 멘탈 코칭과 이탈 예측의 데이터 자산

*"답이 아닌, 이유를 묻는 수학" — WhyMath Schema v1.0*

