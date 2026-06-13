# CLAUDE.md — WhyMath (와이매스) 프로젝트 마스터 가이드

> **이 파일은 Claude가 모든 세션에서 자동 로드합니다. 프로젝트의 정체성·금기·표준이 여기에 있습니다.**

---

## 🎯 프로젝트 정체성

### 브랜드
- **앱명**: WhyMath (한글 표기: 와이매스)
- **슬로건 (KR)**: "답이 아닌, 이유를 묻는 수학"
- **슬로건 (EN)**: "The math that asks why."

### 한 줄 정의
> 한국 중·고등학생을 위한 **메타인지 중심·사고력 우선·단계별 진단** 기반 AI 수학 학습 앱.

### 타깃 페르소나 (PRD v1.2 §3, 5종)
> **A 일반고 고3**(MVP·시장최대) · C 검정고시 N수(v1.5) · D 학종 고2(v1.5·세특/자유연구) · B 자사고 N수(v2.0) · E 홈스쿨링 영재(v2.0). **공유 메타인지 코어 + 첫 노출 A(고3)**. 상세: `docs/strategy/prd_v1.2.md`.

### 우리가 만드는 것
- ✅ 학생이 *생각하는 법*을 배우게 하는 앱
- ✅ 성취기준 기반 정밀 진단 + 메타인지 코칭
- ✅ 손글씨 풀이 단계별 검증
- ✅ 학교 진도 + 수능 + 사고력 + 영재 통합
- ✅ 개념 연결 그래프 기반 학습 (개념 점화 지도)
- ✅ 다중 풀이의 *본질적 동치성* 체험
- ✅ 자동 커리큘럼 정렬 — 학생 교과서·진도에 표기·깊이·풀이 스타일 자동 맞춤

### 우리가 만들지 않는 것
- ❌ 단순 사진→답 풀이 앱 (콴다 영역)
- ❌ 강의 영상 플랫폼 (EBSi 영역)
- ❌ 객관식 문제 양산 앱
- ❌ 무자비한 게임화·중독성 설계
- ❌ 학생을 *수동적으로* 만드는 설계

---

## 🏛️ 7계층 아키텍처 (절대 원칙)

```
L7. 커뮤니티·소셜          [학생 풀이 공유, 학부모·교사 대시보드]
L6. 응용 모드             [학교진도/수능/사고력/영재/메타인지]
L5. 상호작용              [PaddleOCR+Qwen3-VL · Manim · Desmos · 대화]
L4. 교수학 엔진            [Polya 4단계 · 소크라테스 · LTHC · 오개념]
L3. 콘텐츠 생성·검증        [LLM 라우팅 · PRM · 도구호출 · 다중풀이]
L2. 학습자 모델            [BKT/DKT · IRT · 정서신호 · 오개념 매핑]
L1. 데이터 기반            [성취기준 · 검정교과서 · 평가원 · EBS · OER]
```

**경계 침범 금지**:
- L_n은 L_{n-1}을 *호출*할 수 있지만 *구현*하지 않는다
- L_n은 L_{n+1}을 *알지 못한다* (역방향 의존 금지)
- 횡단 관심사(로깅·모니터링·에러)는 별도 인프라
- **L1-L4 = 독립 수학 코어**(UI 밖 독립 플랫폼) — 클라이언트(L5: Flutter 학생앱·별도 웹·국소 임베드)는 API로만 소비, *수학 로직을 클라에 넣지 않는다* (슬라이스 89)
- **표현 ≠ 의미** — 문항·수식·해설은 화면 문자열이 아니라 항상 구조(AST/JSON)로 코어에 저장; 렌더는 클라(Flutter·웹·PDF·AI)가 각자 (문항 스키마·`figure.spec`·05 §5.2 선언적 명세)

각 계층 상세는 `docs/architecture/0{N}_*.md` 참조.

---

## 🛠️ 기술 스택 (확정)

| 계층 | 스택 | 비고 |
|---|---|---|
| 학생 클라이언트 | Flutter 3.x + Riverpod 2.x | 패드 중심 네이티브 태블릿·View Layer·패드+폰 한 코드·수학 로직 미포함(독립 코어 API). Atlas Odyssey·BeatBuddy 자산 (MEMORY 슬라이스 89) |
| 별도 웹 | React 19 + Next.js 15 (App Router) | 교사 대시보드·SEO·검색유입·공유 (Phase 3+)·학생 경험 아님 |
| 국소 임베드(2 비상구) | MathLive·three.js (WebView) | 수식 입력·3D 시각화만 모듈 한정·전체 앱 아님 |
| 수식 입력 | MathLive | 학생 수식 입력 표준 |
| 백엔드 | Python 3.12 + FastAPI + uvicorn | AVAC 자산 |
| RDB | PostgreSQL 16 + TimescaleDB (시계열) | AVAC 자산 |
| Graph DB | Neo4j 5.x (Community) | 개념 연결 그래프 (노드·엣지) |
| Vector DB | **pgvector** (PostgreSQL 16 확장) | 임베딩·의미 검색 — 메타 동거 하이브리드(단일 SQL)·6번째 store 회피. 대규모 시 Qdrant 이관 (MEMORY 슬98) |
| 행동 로그 | ClickHouse | 학습 행동 로그 분석 |
| 객체 저장소 | S3 / MinIO | 영상·이미지 |
| 캐시 | Redis 7 | 세션·핫 데이터 |
| 로컬 LLM | Ollama + Qwen3-Math, DeepSeek-Math, **Qwen3-VL**(멀티모달·그래프 개형) | Phaiakes9 |
| 클라우드 LLM | Claude Sonnet/Opus, GPT-5, Gemini 2.5 | 라우터 경유 |
| 임베딩 | OpenAI text-embedding-3-large | 의미 검색·클러스터링 |
| OCR | **PaddleOCR + Qwen3-VL 하이브리드** (로컬, PaddleOCR fallback) | 손글씨·그래프, Phaiakes9·미성년자 프라이버시. 2026-05-28 결정 (Mathpix 대체) |
| 시각화 | Manim (서버 렌더), Desmos/GeoGebra 임베드, D3.js·three.js·Plotly | 선언적 JSON 명세 |
| 클러스터링 | HDBSCAN + UMAP | 풀이 유형 클러스터링 |
| 도구 호출 | SymPy, Wolfram Alpha API | |
| 인증·결제 | 카카오/네이버 로그인, 토스페이먼츠 | |
| 모니터링 | Langfuse + OpenTelemetry | LLM 추적 표준 |
| CI/CD | GitHub Actions | |
| 인프라 | Phaiakes9 (개발), GCP/AWS (프로덕션) | |

**변경하려면 MEMORY.md에 결정 로그 필수.** Graph DB·행동 로그·객체 저장소·시각화 스택 추가는 `2026-05-14 MathScope PRD v1.1 채택`, OCR(Mathpix→PaddleOCR+Qwen3-VL)·Qwen3-VL 추가는 `2026-05-28`, 벡터 DB(ChromaDB→**pgvector** Postgres 통합)는 `2026-06-10 슬98` 결정 로그 참조.

---

## ⚖️ 절대 금기 (NEVER)

### 데이터·저작권
- ❌ 검정 교과서 *본문·문제·풀이·그림·도표* 복제 절대 금지 — *구조 메타데이터*(단원명·목차·페이지 번호·교육과정 코드)만 사실정보로 인용. 교과서 문제는 자체 코퍼스의 *동등 문제*로 대체 노출 (PRD §13.2 저작권 정책)
- ❌ 교과서 학습목표 텍스트 인용은 *변호사 검토 전제* — 교육과정 코드는 공공이나 교과서의 표현 자체는 출판사 저작물일 수 있음
- ❌ EBS 영상·교재 본문 무단 활용 금지 — *상업 영리금지*(저작권법 §32 단서), 단원 매핑 메타만
- ❌ 평가원 기출 *본문·문항* 상업적 복제·변형 금지 — 구조 메타데이터(단원·코드·문항번호)만, *자체 동등문제*로 대체 (저작권 가이드 v2.0, `docs/data/licensing_safety.md`)
- ❌ 학원·인강 자료(메가스터디·시대인재 등) 데이터화 금지
- ❌ 학생 풀이 데이터를 *명시적 동의 없이* 학습에 사용 금지
- ❌ 미성년자 개인정보를 분석·마케팅 외부 공유 금지

### 교수학
- ❌ 학생이 막혔을 때 *바로 정답 제공* 금지 — 항상 Polya 4단계 우선
- ❌ "정답을 빠르게"를 KPI로 사용 금지
- ❌ 학습 시간·정답률만으로 우열을 매기는 게임화 금지
- ❌ 부정적 피드백(틀렸다·못 한다)을 정서적으로 강화하는 표현 금지

### AI·신뢰
- ❌ LLM 응답을 검증 없이 학생에게 제공 금지 — PRM 또는 도구 검증 필수
- ❌ "확실하지 않을 때 자신 있게 말함" 패턴 금지 — 모르면 모른다고
- ❌ 환각 발견 시 *조용히* 넘어가지 말고 로그·수정

### 보안
- ❌ 미성년자 채팅 데이터를 평문으로 저장 금지
- ❌ API 키·시크릿을 코드에 하드코딩 금지
- ❌ 학교·학년 정보로 *개인 식별 가능한* 분석 결과 외부 노출 금지

---

## ✅ 절대 원칙 (ALWAYS)

### 코드
- 모든 PR에 테스트 동반 (커버리지 70%+)
- LLM 호출은 항상 라우터 경유 — 직접 호출 금지
- 모든 데이터베이스 접근은 ORM/쿼리 빌더 — 원시 SQL 최소화
- 한국어 주석을 코드에 직접 작성 (Kiki 선호)

### LLM 사용
- 모든 LLM 호출 → Langfuse 추적
- 모든 LLM 응답 → 응답 캐싱 검토 (비용 절감)
- 학생 응답 생성은 *반드시* PRM 또는 도구 검증 통과 후
- 클라우드 LLM 호출 전 *항상* 로컬 LLM 가능성 검토 (비용)

### 데이터
- 학생 데이터는 *민감 정보*로 분류 — 암호화 저장
- 콘텐츠 백본은 *법적 안전조합*만 — NCIC·공공누리 AI유형·AIHub + LLM 학습용 NuminaMath/PRM800K/PhET/Metamath. EBS·평가원·검정교과서 본문은 *자체 동등문제*로 대체 (상세: `docs/data/licensing_safety.md` §가이드 v2.0)
- 모든 데이터 소스의 라이선스를 `docs/data/licensing_safety.md`에 기록
- 학부모 동의·14세 미만 동의 절차 준수

### 교수학
- 모든 학습 경로는 Polya 4단계 매핑
- 모든 오답은 *오개념 후보* 분석 시도
- 모든 콘텐츠는 성취기준 코드 1개 이상 태그

---

## 🧠 워크플로우 표준

### 새 기능 개발 시
```
1. /plan [기능명]            ← 계획 수립, 7계층 어디에 속하는지 확인
2. /implement [영역]         ← 해당 서브에이전트 위임
3. /review                  ← 코드·테스트·문서 점검
4. MEMORY.md 업데이트         ← 주요 결정 기록
5. git commit               ← 의미 있는 커밋 메시지
```

### 데이터 작업 시
```
1. /dataset [소스명]         ← 라이선스·구조 분석
2. data-engineer 위임        ← 파이프라인 작성
3. 데이터 카드 작성           ← docs/data/ 에 명세
```

### 프롬프트 설계 시
```
1. /prompt-design [목적]     ← 템플릿 라이브러리 검토
2. pedagogy-designer 위임   ← 교수학 검증
3. Langfuse에 등록           ← 버전 관리
4. A/B 테스트                ← 효과 검증
```

---

## 🚦 의사결정 우선순위

여러 가치가 충돌할 때 다음 순서로 결정:

1. **학생 안전·웰빙** (정서·중독·부정확)
2. **법적·윤리적 준수** (저작권·개인정보·미성년자)
3. **교수학적 정확성** (Polya·메타인지·오개념)
4. **학습 효과** (장기 숙달 > 단기 점수)
5. **사용자 경험** (단순함·신속성)
6. **비용·효율** (LLM 호출비·인프라)
7. **개발 속도**

*이 순서는 협상 불가*. 6번 때문에 1번을 양보하지 않는다.

---

## 🎭 페르소나·서브에이전트

| 영역 | 서브에이전트 | 호출 방법 |
|---|---|---|
| L1 데이터 | `data-engineer` | `/implement data:*` |
| L2 모델 | `ml-engineer` | `/implement ml:*` |
| L3 LLM | `llm-architect` | `/implement llm:*` |
| L4 교수학 | `pedagogy-designer` | `/implement pedagogy:*` |
| L5 모바일 | `flutter-engineer` | `/implement mobile:*` |
| L5 서버 | `backend-engineer` | `/implement backend:*` |
| L6/L7 콘텐츠 | `content-curator` | `/implement content:*` |

상세는 `.claude/agents/*.md` 참조.

---

## 📚 핵심 문서 인덱스

### 즉시 참조 (자주 읽기)
- `MEMORY.md` — 결정 로그·현재 상태
- `ROADMAP.md` — Phase별 일정
- `docs/architecture/00_overview.md` — 7계층 요약
- `docs/standards/prompt_engineering.md` — 프롬프트 기준

### 상세 (필요 시 읽기)
- `docs/architecture/01-07_*.md` — 각 계층 상세 명세
- `docs/architecture/03b_wh_s_solver_harness.md`·`04a_wh1_tutoring_harness.md` — 하네스 설계안(WH-S 솔버·WH-1 튜터링·횡단 인프라)
- `docs/strategy/*.md` — 시장·차별화·리스크
- `docs/data/licensing_safety.md` — 데이터 라이선스 매트릭스
- `docs/prompts/*.md` — 프롬프트 템플릿 라이브러리

---

## 🔄 컨텍스트 위생 (Context Hygiene)

이 프로젝트는 *컨텍스트 오염*이 가장 큰 리스크입니다. 다음 규칙 준수:

1. **장기 작업은 서브에이전트로** — 메인 컨텍스트에 코드 토큰 누적 금지
2. **새 영역 진입 시 컨텍스트 비우기** — `/status` 후 새 세션
3. **MEMORY.md를 진실 원천으로** — 대화 휘발에 의존 금지
4. **결정은 항상 문서화** — "전에 말했잖아"가 통하지 않는 환경

---

## 🚀 시작하는 법 (첫 1주)

```bash
# Day 1: 방향성 확정
> 읽기: README.md, CLAUDE.md, ROADMAP.md
> /plan Phase1-MVP

# Day 2-3: L1 데이터 기반 시작
> /implement data:ncic-crawler
> /implement data:school-info-crawler

# Day 4-5: L4 교수학 프롬프트
> /prompt-design socratic-coaching
> /prompt-design polya-4step

# Day 6-7: 모바일 스캐폴딩
> /implement mobile:project-setup
> /implement backend:project-setup
```

---

## 📐 Kiki 개인 선호 (저장된 패턴)

- 모든 답변·문서·주석은 한국어
- 기술 용어는 영어 원어 병기 가능
- 구체적 숫자·제품명 선호
- 초보자 친화 설명 (단, 깊이는 유지)
- 건축/설비/AI/핀테크 도메인 활용 가능
- 로컬 LLM 우선 (Phaiakes9 적극 활용)
- CRAFT 프레임워크·AI 길들이기 4시스템 호환

---

**버전**: 0.1.0 | **최종 수정**: 2026-05  
**다음 검토일**: Phase 1 종료 시점
