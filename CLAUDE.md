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

### 구조 붕괴 (구축 플레이북 2대 철칙 — 어기면 시스템은 반드시 무너진다)
- ❌ 수학 *전체*를 완벽 모델링 금지 — *교육적으로 압축된 인지 그래프*만 (개념 원자 단위, 핵심만 노드·나머지는 속성/AI 생성)
- ❌ LLM에 *전체 그래프*를 통째로 주기 금지 — Minimal Reasoning Subgraph만 (depth ≤ 2, max_nodes ≤ 12~20, max_tokens ≤ 3000). "더 많이 넣을수록 더 멍청해진다"
- ❌ 노드에 renderer·curriculum·prompt·misconception·UI·embedding *혼입* 금지 (Concept Purity — 노드는 순수 개념만)
- ❌ 관계 타입 *폭발* 금지 — 5~8개 핵심 관계만. `similar_to`/`related_to`를 traversal에 사용 금지
- ❌ 오개념을 초기 context에 *preload* 금지 — reactive retrieval만 (misconception contamination 방지)
- ❌ 노드 embedding *전체* 생성 금지 — chunk 단위(`limit.definition`/`limit.intuition`/`limit.example`, 150~500 tokens)로 분리, semantic vector 오염 방지

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

## 🧱 구축 플레이북 불변식 & AI 질문 프로토콜

> 출처: **WhyMath 구축 플레이북 v1.0**(55개 설계문서 통합) Part 8·11·12.
> 이 프로젝트의 최대 리스크는 *컨텍스트 오염*이므로, "매번 잘 질문하기"에 의존하지 않고 아래 규칙을 **모든 세션이 자동으로 강제**받는다. **AI에게 질문하는 법 = 이 프로토콜을 그대로 따르는 것.**

### 단 하나의 원칙
1. **"수학 전체를 모델링하지 말고, 교육적으로 압축된 인지 그래프만 만들어라."**
2. **"LLM에게 전체 그래프를 절대 통째로 보여주지 마라."**

> 이 문서의 거의 모든 규칙은 사실 이 두 문장의 구체적 실천법이다. 두 문장을 어기는 순간 시스템은 반드시 무너진다.

### 8대 구조 원칙 (12-2 요약)
1. **Concept Purity** — 노드는 순수 개념만 (renderer·UI·prompt·curriculum·misconception 금지)
2. **Layer Separation** — Concept/Relation/Pedagogy/Misconception/Renderer/Curriculum/AI 계층 분리
3. **Relation Typing 최소화** — 5~8개 핵심 관계만
4. **Renderer는 Plugin** — Concept → Visualization Intent → Renderer Adapter (구현체 이름을 노드에 넣지 않음)
5. **Curriculum은 Overlay** — 개념은 영속, 교육과정 매핑만 교체
6. **오개념은 독립 DB** — Reactive Retrieval
7. **AI Context Slimming** — 필요한 subgraph만 전달
8. **AST 중심** — 표현 통합의 기준축

### 7대 붕괴 연쇄 (12-1 — 이 순서로 무너진다)
`노드 폭발 → 관계 폭발 → 순환참조 → 유지보수 지옥 → 성능 병목 → AI 추론 실패 → 교육 일관성 붕괴`
- **노드 폭발** ← "모든 것을 노드화" · 방어: 개념 원자 단위, 핵심만 노드
- **관계 폭발** ← Edge ≈ N² · 방어: Edge 타입 5~8개 제한, `similar_to` 제거
- **순환참조** ← 교육 그래프는 본질적 순환 · 방어: `prerequisite`만 DAG 강제 + Reachability Check
- **유지보수 지옥** ← truth source가 하나가 아님 · 방어: 단일 진실 원천
- **성능 병목** ← context traversal 폭증 · 방어: depth·max_nodes·token budget guard
- **AI 추론 실패** ← attention dilution · 방어: Minimal Reasoning Subgraph
- **교육 일관성 붕괴** ← 위 6개의 최종 귀결

### AI 질문 프로토콜 (Part 11 — "어떻게 질문할까"의 답)
- **AI를 "답변기"가 아니라 "구조 붕괴 감지기"로 쓴다.** 코드 생성기 ❌ → 구조 비평가·boundary 검사기·explosion 탐지기·schema validator ⭕
- **4종 질문 축으로 묻는다**: ①존재 이유(왜 필요한가) ②경계(어디까지인가) ③붕괴(어디서 실패하는가) ④분리(무엇을 독립시켜야 하는가)
- **질문 골격을 강제한다**: `[역할] 당신은 OO 전문가 · [목표] OO 설계 · [환경] 기술·대상·제약(AST 기반·오개념 추적) · [출력] 아키텍처/핵심모듈/데이터흐름/예상난점/테스트전략 · [검증] 실패 가능성·예외 상황·테스트 방법`
  - ❌ "수학앱 만들어줘"(범위 무한·목표 없음 → 일반론만) · ❌ "한 번에 전부 구현해줘"(피상적·누락·구조 붕괴)
- **단계적 심화로 나눈다**: `생성 → 비판 → 반례 → 개선 → 테스트 → 자동화`. 각 노드 설계 끝에 반드시 묻는다 — *"이 구조가 실제 서비스에서 실패하는 이유를 분석해줘"*
- **노드 설계 시 공통 출력 형식을 강제한다**: `1.구조적 2.교육적 3.AI retrieval 4.scaling 5.maintenance 6.canonicalization 위험 7.mitigation 전략`으로 분리. 공통 문장: **"표면 표현이 아니라 인지 행동(cognitive action) 기준으로 설명하라."**

### 작업 전/후 하드 게이트 (12-3 — 통과 전 설계·구현 진행 금지)
**노드 추가 시**:
- [ ] 이 데이터는 "개념 자체"인가, "해석/투영/실행 정보"인가? (후자면 외부화)
- [ ] 노드 파일이 1~4KB 이내인가? (10KB 이상 금지)
- [ ] renderer·curriculum·prompt·misconception·UI·embedding을 노드에 넣지 않았는가?
- [ ] ID가 파일명·언어·교육과정과 독립적인가? (`math.calculus.limit` 형태)

**관계 추가 시**:
- [ ] 이 관계가 없으면 AI 튜터링에서 실제 어떤 오류가 발생하는가? (불명확하면 weak → 제거)
- [ ] `prerequisite`이면 DAG를 깨지 않는가? (Reachability Check 통과)
- [ ] `related_to`/`similar_to`를 traversal에 쓰고 있지 않은가?
- [ ] 단방향 canonical edge로 저장했는가?

**AI 연동 시**:
- [ ] LLM에 전체 그래프가 아니라 subgraph(depth ≤ 2, max_nodes ≤ 12~20)만 주는가?
- [ ] 오개념을 초기 context에 preload하지 않고 reactive로 가져오는가?
- [ ] concept/atom/misconception embedding이 물리(테이블)·논리(subject 스코프 + 거버넌스 테스트) 분리되어 있는가? (DB cross-table 코사인 금지 — `test_embedding_namespace_governance.py`)
- [ ] traversal에 visited set·timeout·token budget guard가 있는가?

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
- `docs/standards/build_checkpoint_questions.md` — 구축 플레이북 단계별 진행 점검 질문 세트 (`/review`·`/status` 시)
- `docs/standards/playbook_part_review_questions.md` — 구축 플레이북 Part 0~12 순차 설계-준수 점검 질문 세트

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
5. **여러 세션 병렬 개발 시** — `docs/standards/parallel_sessions.md` 준수 (1 세션 = 1 도메인 = 1 브랜치 = 1 worktree, `scripts/new-session-worktree.sh`)

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
- **"pr" 단축어** = *PR 생성 → CI 통과 대기 → 자동 머지(SQUASH)까지 일괄 진행*. 별도 "머지" 지시 불요(CI 실패 시 진단·수정·재시도 후 green일 때 머지). (2026-06-18 합의)

---

**버전**: 0.1.0 | **최종 수정**: 2026-05  
**다음 검토일**: Phase 1 종료 시점
