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
L6. 응용 모드             [학교진도/수능내신/사고력/메타인지/영재/자유학기/디버깅 — 7모드]
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
- **표현 ≠ 의미** — 문항·수식·해설은 화면 문자열이 아니라 항상 구조(AST/JSON)로 코어에 저장; 렌더는 클라(Flutter·웹·PDF·AI)가 각자 (문항 스키마·`figure.spec`·05 §5.2 선언적 명세). *현행 정밀*(2026-07-21 정합성 검토): 동치 판정(`l3/equivalent/canonicalize`)·시각화·검산 재료는 구조가 정본이고, 문항·풀이 *본문*은 렌더러-중립 LaTeX(+`reasoning_type` 등 구조 태그)로 저장한다 — 화면 문자열 금지 축은 충족, 본문 완전 AST화는 의도적 미채택(과공학 방지)

각 계층 상세는 `docs/architecture/0{N}_*.md` 참조.

---

## 🛠️ 기술 스택 (확정)

| 계층 | 스택 | 비고 |
|---|---|---|
| 학생 클라이언트 | Flutter 3.x + Riverpod 2.x | 패드 중심 네이티브 태블릿·View Layer·패드+폰 한 코드·수학 로직 미포함(독립 코어 API). Atlas Odyssey·BeatBuddy 자산 (MEMORY 슬라이스 89) |
| 별도 웹 | React 19 + Next.js 15 (App Router) | 교사 대시보드·공개 랜딩·SEO·검색유입·공유 — 학생 경험 아님·Phase 3+는 교사 웹 한정. 웹 전략 정본 `docs/architecture/web_strategy.md` (2026-08-10 결정 로그) |
| 국소 임베드(2 비상구) | MathLive·three.js (WebView) | 수식 입력·3D 시각화만 모듈 한정·전체 앱 아님 |
| 수식 입력 | MathLive | 학생 수식 입력 표준 |
| 백엔드 | Python 3.12 + FastAPI + uvicorn | AVAC 자산 |
| RDB | PostgreSQL 16 + TimescaleDB (시계열) | AVAC 자산 |
| Graph DB | ~~Neo4j 5.x (Community)~~ — **런타임 미도입**(2026-08-03 정정·확정) | 개념 연결 그래프의 정본은 **PG 단일 평면**(실측 원자 백본 2,683노드·2,210엣지). Neo4j는 data-pipeline 옵셔널 extra(적재 실험 경로)로만 존재 — backend 의존·docker 서비스 0건. 상세 = `00_overview.md` 5블록 DB·컴포넌트 표 |
| Vector DB | **pgvector** (PostgreSQL 16 확장) | 임베딩·의미 검색 — 메타 동거 하이브리드(단일 SQL)·6번째 store 회피. 대규모 시 Qdrant 이관 (MEMORY 슬98) |
| 행동 로그 | ClickHouse | 학습 행동 로그 분석 |
| 객체 저장소 | S3 / MinIO | 영상·이미지 |
| 캐시 | Redis 7 | 세션·핫 데이터 |
| 로컬 LLM | Ollama + Qwen3-Math, DeepSeek-Math, **Qwen3-VL**(멀티모달·그래프 개형) — *실제 핀(2026-07 코드)*: `qwen2-math:1.5b/7b`(MATH), `qwen2.5:3b/7b`(GENERAL), `qwen3.5:27b`(QUALITY·비동기), `qwen3-vl:8b`(VISION·인식기 실배선·라이브 정확도 미검증) | Phaiakes9. 정본 = `03a_l3_router_design.md`·`l3/router.py`(`LOCAL_MODEL_MATRIX`) |
| 클라우드 LLM | Claude Sonnet/Opus, GPT-5, Gemini 2.5 — *실제 배선(2026-07 코드)*: `claude-sonnet-4-6`(CLOUD_MID)·`claude-opus-4-7`(CLOUD_HIGH)만. **GPT-5·Gemini 2.5는 계획·라우터 미배선** | 라우터 경유. 정본 = `config.py`(`anthropic_model_mid/high`)·`l3/providers/anthropic.py` |
| 임베딩 | **기본(로컬)=bge-m3**(`BAAI/bge-m3`·1024) · 클라우드 옵션=OpenAI text-embedding-3-large(3072) | 의미 검색·클러스터링. `embedding_provider` 셀렉터(local 기본·openai·fake)·로컬 우선(비용·Phaiakes9). **최종 확정 미결**(bge-m3 vs te-3-large — MEMORY 슬105·SSM 2026-Q3 스캔 ③) |
| OCR | **PaddleOCR + Qwen3-VL 하이브리드** (로컬, PaddleOCR fallback) | 손글씨·그래프, Phaiakes9·미성년자 프라이버시. 2026-05-28 결정 (Mathpix 대체) |
| 시각화 | Manim (서버 렌더), Desmos/GeoGebra 임베드, D3.js·three.js·Plotly | 선언적 JSON 명세 |
| 클러스터링 | HDBSCAN + UMAP | 풀이 유형 클러스터링 |
| 도구 호출 | SymPy, Wolfram Alpha API | SymPy=동치·검증·해집합 단일 권위(실사용). **Wolfram Alpha API는 계획·코드 미구현**(2026-07 실측) |
| 인증·결제 | 카카오/네이버 로그인, 토스페이먼츠 | |
| 모니터링 | **Langfuse**(실배선) + ~~OpenTelemetry~~ — *현행 정밀*(2026-08-11 r3 실측): **OTel은 `pyproject.toml` 선언만·`import` 0건**(미배선) | LLM 추적 표준. 실집행은 Langfuse 단독 + 인프로세스 이중 회계(`ops/service_health`·`cost_probe`). OTel 의존 자체의 제거/배선 판정 = `OPS-32` |
| CI/CD | GitHub Actions | |
| 인프라 | Phaiakes9 (개발), GCP/AWS (프로덕션) | |

**변경하려면 MEMORY.md에 결정 로그 필수.** Graph DB·행동 로그·객체 저장소·시각화 스택 추가는 `2026-05-14 MathScope PRD v1.1 채택`, OCR(Mathpix→PaddleOCR+Qwen3-VL)·Qwen3-VL 추가는 `2026-05-28`, 벡터 DB(ChromaDB→**pgvector** Postgres 통합)는 `2026-06-10 슬98`, 스택 표 모델 표기 정합(패밀리명→실제 핀 ID 병기·AI/LLM 인벤토리 신설)은 `2026-07-24`, Graph DB 행 실측 단서 병기(Neo4j 런타임 미도입)는 `2026-08-10 통합점검`, 모니터링 행 실측 단서 병기(OpenTelemetry 선언만·import 0건)는 `2026-08-11 운영(EOS) r3` 결정 로그 참조.

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
- ❌ **침묵 실패(silent failure) 금지** — never-break로 예외를 삼키는 코드(관측성·best-effort)는 반드시 **예외 타입명을 로그에 포함**한다(시크릿·필드값은 제외). 무타입 경고는 금지 — langfuse v2 쓰기가 8일간 무증상 전멸한 원인(2026-07-16 실측 교훈)
- ❌ **외부 SDK 표면을 시임(가짜) 테스트만으로 정합 선언 금지** — 우리가 호출하는 메서드가 pin 허용 범위의 *실물* SDK에 존재하는지 실측 검증한다. 의존성 pin은 검증된 메이저 범위로 **상한을 건다**(`langfuse>=2.50,<5` 선례 — 무상한 pin이 v2/v4 혼재·표면 불일치를 낳음)
- ❌ 측정·게이트 도구가 판정치를 **외부 관측 인프라(SaaS)에만 의존 금지** — 핵심 판정치는 인프로세스에서도 산출하는 이중 회계(`ops/cost_probe` 로컬 비율 선례). 인프라가 죽으면 "측정 실패"가 보여야지 "0건 통과/미달"로 위장되면 안 된다
- ❌ *측정 없는* 기계 게이트를 인간 검수 대체로 선언 금지 — 대체는 결함 주입 강등전·Wilson 게이트 CLI PASS 경유 (`docs/standards/superhuman_verification_standard.md`)
- ❌ 법령 유래 절차(법정대리인 동의·변호사 검토·PII 보호)의 기계 대체 금지 — 검수가 아니라 법적 의사표시·법률 판단

### 보안
- ❌ 미성년자 채팅 데이터를 평문으로 저장 금지
- ❌ API 키·시크릿을 코드에 하드코딩 금지
- ❌ 학교·학년 정보로 *개인 식별 가능한* 분석 결과 외부 노출 금지

### 프로세스·안내 (2026-07-16 게이트② 측정 사고 일괄 등재)
- ❌ **거부(deny)의 우회 금지** — 하네스·권한 분류기·게이트의 거부는 장애물이 아니라 *판정*이다. 대장(YAML) 손편집·이벤트 수기 추가 등으로 우회하지 않는다. 처리 순서: ①거부 사유 확인 → ②사람 소유 액션이면 소유자에게 실행 명령으로 넘김 → ③CLI 경로 자체가 없는 설계 공백이면 태스크로 등재(HARN-06 선례). (사고 경위: S1-14 done을 claude가 YAML 직접 기입으로 우회 시도 → 분류기 차단 → 되돌리고 Kiki 본인 기입으로 정정)
- ❌ **검증 없는 실행 안내 금지** — Kiki에게 측정·실행 명령을 안내하기 전에, 그 명령이 기대 산출물(이벤트·파일·지표)을 실제로 내는 코드 경로인지 저장소에서 *먼저 확인*한다. 가정 기반 런북 금지. (사고 경위: `problem_corpus_accumulate`가 `l3_routing` 이벤트를 낸다고 가정하고 안내 → 파이프라인 우회 경로라 이벤트 0건 → 라이브 측정 2회 공전)
- ❌ **환경 사실의 추론 등재 금지** — 머신·DB·접속 경로 등 환경 규칙은 실측 증거(명령 출력·fingerprint)를 확보한 뒤에만 등재·정정한다. 부분 성공(읽기만 됨·한 번 됐음)을 전체 정상으로 해석하지 않는다. (사고 경위: "ssh→wsl 2단계 진입" 규칙을 추론으로 등재 → 자기 자신 SSH 접속으로 판명·정정 / 07-14 관측 33이벤트를 정상 작동으로 오인 → 실은 쓰기·읽기가 서로 다른 venv에서 절반씩 성립한 우연)
- ❌ **간접 신호를 성공 판정으로 쓰는 안내 금지** — 다단계 실행 안내의 각 단계에는 *그 단계 산출물 자체*를 확인하는 자가검증 스텝(파일 존재·포트 리스너·프로세스 생존)을 동봉하고, pid 파일·/health 응답처럼 **다른 프로세스가 대신 만족시킬 수 있는 간접 신호**를 성공 근거로 삼지 않는다. (사고 경위: 2026-07-17 좀비 uvicorn이 8000 점유 → 새 서버 즉사·pid 파일은 죽은 pid·/health는 좀비가 응답 → shadow OFF 서버에 트래픽 제출돼 기록 0건. 시크릿 자가검증 규칙의 일반화)
- ❌ **변별력 없는 검증 스텝 금지** — 자가검증 스텝은 *실패 상태에서 실제로 실패 신호를 내는지* 확인된 것만 동봉한다. 성공/실패 양쪽에서 같은 값을 내는 검사는 검증이 아니라 위장이다. (사고 경위: 2026-07-17 logconfig `delay:true` 때문에 캡처 파일이 첫 기록 전까지 미생성 → 사전 `Test-Path`가 정상 상태에서도 항상 False — 검증 스텝 자체가 무효였음 → delay 제거로 변별력 복원)
- ❌ **검사 명령의 출력을 억제하거나 잘라서 판정 금지 (2026-08-09 등재)** — 게이트·린트·테스트를 돌릴 때 `-q`/`--quiet`로 출력을 죽이거나 `| tail -N`으로 잘라 놓고 **눈에 보이는 문자열만으로 통과를 선언하지 않는다**. 판정은 **exit code**로 한다(`; echo "EXIT=${PIPESTATUS[0]}"` 병기). 조용한 도구는 실패해도 성공과 같은 화면을 낸다. 또한 **CI가 실제로 쓰는 명령을 그대로** 재현한다(대상 경로·플래그 포함) — 대상을 좁히면 CI가 보는 파일을 안 볼 수 있다. (사고 경위: 2026-08-09 PR #732에서 `black --check -q ... | tail -3`을 `&&`로 이어 붙여 돌린 결과, black이 6파일 실패로 exit 1을 냈는데 `-q`가 "would reformat" 출력을 억제해 앞 명령(ruff)의 "All checks passed!"만 보이는 상태로 통과 판정 → CI에서 backend 잡 red. 위 "변별력 없는 검증 스텝 금지"의 *도구 사용* 축 변형 — 검사 자체는 변별력이 있었는데 **호출 방식이 변별력을 없앴다**)
- ❌ **미커밋 작업분이 있는 트리에서 `git checkout --`·`git restore`·`git stash`로 뮤테이션 원복 금지 (2026-08-10 등재)** — 뮤테이션 검증(일부러 깨뜨렸다 되돌리기)의 원복 수단은 **뮤테이션 전에 `cp`로 뜬 백업을 `cp`로 되돌리는 것**뿐이다. git 계열 원복은 *뮤테이션*과 *아직 커밋되지 않은 구현분*을 구분하지 못하고 **둘 다** HEAD로 되돌린다 — 게다가 무증상이다(에러 없음·`git status`에서 파일이 조용히 사라질 뿐). 서브에이전트 산출물처럼 "작업 트리에만 있는" 변경을 검증할 때 특히 위험하다. 원복 직후에는 `git diff --stat`으로 **되돌린 규모가 뮤테이션 크기와 일치하는지** 확인한다. (사고 경위: 2026-08-10 OPS-24에서 `_check_exit_code`를 뮤테이션한 뒤 `git checkout -- problem_corpus_review_status_backfill.py`로 원복 → 미커밋 구현분 +59/-6이 통째 소실. 스크래치패드 백업으로 바이트 동일 복원했고, 신규 테스트 16건이 동작을 계약으로 고정하고 있어 복원 충실도를 기계가 판정할 수 있었다 — 백업도 테스트도 없었으면 재작성이었다)
- ❌ **서버 점유 창에 후속 명령 혼입 금지** — 장기 프로세스(서버 등)가 점유할 창의 안내 블록은 그 명령으로 *끝나야* 하며, "이 창은 이후 조작 금지·Ctrl+C는 복사가 아니라 중단 신호" 경고를 동봉하고 후속 명령은 반드시 별도 창 블록으로 분리한다. (사고 경위: 2026-07-17 창②용 명령이 서버 창에 붙여넣어지고 Ctrl+C로 프롬프트 복구 → 서버 우아 종료 → 프로브 전건 ConnectError)
- ❌ **부분 스위트 통과를 전체 통과의 근거로 보고 금지** — 백엔드 소스·테스트를 건드렸으면 **전체 스위트**를 돌린 뒤 "회귀 없음"을 말한다. 디렉터리·파일 단위 실행은 *순서 의존 오염을 구조적으로 볼 수 없다*(같은 프로세스에서 전역을 남기는 테스트가 뒤 테스트를 깨는 형태). 돌리지 못했으면 **"전체는 확인하지 못했다"를 명시**하고 CI를 최종 판정으로 넘긴다 — 침묵은 통과 주장으로 읽힌다. (사고 경위: 2026-07-26 OPS-06에서 `tests/backend/api/` 1077건 통과를 "회귀 없음"으로 보고 → 전체 스위트에서만 드러나는 `db.session._engine` 전역 오염이 머지 후 main CI red. 방어 장치는 OPS-07 가드(원인 지목)+OPS-09 순서 무작위화(존재 발견))
- ❌ **검증 장치를 만들고 배선 확인 없이 완료 선언 금지** — 테스트·게이트·계약을 새로 만들면 그것이 **실제로 CI에서 실행되는지** 확인한 뒤 완료로 친다. "저장소에 존재함"과 "돌아감"은 다르다. 이 부류는 이 프로젝트에서 **반복 발생**했다 — `tests/infra` 199건이 어떤 잡도 실행하지 않던 상태(OPS-03에서 발견), 브랜치 보호 required check가 `enforcement_level=off·checks=[]`로 통째 미강제였던 상태(OPS-08), `tests/infra`를 lint/format하는 잡이 여전히 없던 상태(OPS-11). 배선 실재성은 `tests/infra/test_test_suite_wiring.py`(OPS-10)가 기계로 동결한다.
- ❌ **상시 실패하는 fail-open 보호를 "보호 있음"으로 신뢰 금지** — fail-open 설계(실패 시 경고 후 진행)는 실패가 *예외적*일 때만 보호다. 같은 실패 경고가 **환경에서 반복 관측되면(2회+)** 그 보호는 상시 무력 상태이며, 경고는 습관화되어 소음이 된다. 그 시점에 경고를 넘기지 말고 ①실패 원인을 실측 규명 ②무력 상태를 태스크로 등재 ③가능하면 대체 경로(읽기측 폴백 등)를 배선한다. 병렬 세션 착수 시 원격 claim이 `error`면, 폴백이 착륙하기 전까지는 **원격 브랜치의 같은 태스크 `in_progress` 여부를 수동으로라도 확인**한다. (사고 경위: 2026-07-27 `refs/claims/*` push가 CCR git 프록시 403으로 **상시** 실패 → 모든 세션이 "⚠ 원격 claim 불가(error)" 경고를 보고 fail-open 진행 → 두 세션이 OPS-07을 병렬 구현, 한쪽 735줄 폐기. 읽기측 폴백 = HARN-07)

- ❌ **trunk 부재를 "미구현"으로 단정 금지 (갭 판정 절차)** — 갭 리뷰·현황 점검에서 어떤 기능을 "없다/미착수"로 판정하기 전에 ①`backlog.py next`가 출력하는 **"이미 완료(미머지)" 제외 경고**를 읽고 ②해당 태스크 ID로 원격을 실측한다(`git log --all --grep=<TASK-ID>`). **코드 grep 0건은 "trunk에 없다"는 뜻이지 "만들어지지 않았다"는 뜻이 아니다.** 장기 미머지 브랜치가 수십 개인 상태에서 trunk는 실제 진척을 점점 덜 대표하므로, "없다" 판정의 오류율은 구조적으로 상승한다. (사고 경위: 2026-08-04 NLP r2 재점검이 `NLP-01`·`NLP-03`을 "미착수"로 단정할 뻔했다 — 작업 트리의 `status: todo`·해당 코드 변경 0건이 전부 그 오판을 지지했고, 실제로는 병렬 세션이 전날 둘 다 구현해 미머지 상태였다. 막아 준 것은 코드도 문서도 아닌 하네스 원격 claim 대장이다)
- ❌ **태스크 ID 번호를 추론으로 배정 금지** — 새 태스크 등재는 항상 `backlog.py add`를 거친다(번호 충돌을 로컬 백로그 + 원격 claim 대장 양쪽에서 검사·HARN-10). 파일 목록만 보고 "다음 번호"를 눈으로 골라 YAML을 만들면 **병렬 세션의 인플라이트 번호를 볼 수 없다**. 거부되면 CLI가 제안한 번호를 쓴다. (사고 경위: 2026-07-18/25 ARCH-13, 2026-07-29 OPS-15가 각각 두 태스크에 중복 배정 — full-ID는 슬러그 덕에 달라 validate가 통과했고, 사람·문서·커밋의 번호 참조만 결정 불가가 됐다)

- ❌ **정본화를 집행으로 착각한 완료 선언 금지 (2026-08-04 등재)** — 노출·안전·억제 계약(무엇을 보여주고 무엇을 감출지 정하는 모듈)을 acceptance에 "정본화"라고만 적으면 그 모듈이 실제로 **서빙 경로에서 호출되는지 확인하지 않고도** 완료 처리된다. 계약을 만드는 태스크의 acceptance는 반드시 ①정본화(계약 자체)와 ②**집행 지점**(그 계약을 실제로 경유하는 서빙 코드 경로가 무엇인지)을 **별항으로 분리**해 적는다. 위 "검증 장치를 만들고 배선 확인 없이 완료 선언 금지"의 특수형이다 — 그 항목이 "테스트가 CI에서 도는가"를 묻는다면 이 항목은 "계약을 서빙 코드가 실제로 부르는가"를 묻는다. (사고 경위: `PED-06`이 `growth_evidence_exposure.py`에 3계층 노출 계약을 만들며 스스로 "이 함수가 유일한 노출 판정 경로가 되게 한다"고 선언했으나, acceptance ①이 "노출 계약 정본화"로만 적혀 있어 그대로 통과 → 실제로는 CLI 리포트와 자기 테스트만 그 함수를 부르고, 학생 토큰으로 호출되는 `GET /v1/me/harness-metrics`는 원시 11지표를 `GAMING_SUSPECT`까지 포함해 그대로 반환하는 상태로 1일간 방치됐다 — 게임화 모듈 2차 재점검(`gamification_module_gap_review_r2.md` §2 G1·§4-④·§7)에서 발견·`PED-08`로 재설계)

- ❌ **회수(recovery)로 태스크 done 선언 시 acceptance 전수 재대조 생략 금지 (2026-08-10 등재)** — 고립 브랜치·타 세션 산출물을 이식해 태스크를 done 처리하기 전에, **그 시점 main의 acceptance 전 항목**을 이행/미이행/의도적 제외로 재대조하고 미이행분은 승계 태스크로 분리 등재한다. 회수는 "브랜치에 있던 것"을 기준으로 완료를 선언하므로, 브랜치 분기 *이후* main에서 확장된 acceptance는 코드 대조에 **나타나지 않는다** — diff 전수 열거(NLP-04 등재 규칙)로도 안 보인다(존재하지 않는 코드는 대조 실패조차 내지 않는다). 위 "검증 장치를 만들고 배선 확인 없이 완료 선언 금지"(만든 것이 도는가)·"정본화를 집행으로 착각한 완료 선언 금지"(계약을 부르는가)에 이은 세 번째 축(**약속한 것이 다 있는가**)이다. (사고 경위: 2026-08-03 §7 2차 점검이 `VIZ-03` acceptance를 ①-b(수직선 1D 축·코퍼스 25건)·⑥(좌석 계약 갱신)으로 확장 → 08-08 `NLP-04` 회수가 확장 이전 고립 아티팩트만 이식하고 done 처리 — 극값처럼 코드에 *있는* 초과분은 분리 처리(`VIZ-06`)했으나 코드에 *없는* 미이행분은 대조에 안 나타났다 → 좌석 계약이 done 태스크를 seat_owner로 지목하는 결정 불가 상태로 이틀 방치, 시각화 R3(`visualization_module_gap_review.md` §8.1)에서 발견·`VIZ-07`로 승계)
- ❌ **작동 신호 없는 알고리즘 부착 금지 — "작동한 비율" 원칙 (2026-08-03 결정·2026-08-10 통합점검이 본문 등재)** — 알고리즘·전략을 붙였으면 **그 알고리즘이 실제로 작동한 비율**을 응답·리포트가 말해야 한다. 정상 응답 200은 알고리즘이 일했다는 증거가 아니다. 부수 원칙: docstring 속 계획은 백로그를 대신하지 못한다 — 추적하려면 태스크로 등재한다. (사고 경위: 학습경로 설계에서 알고리즘 부착 후 무작동을 정상 응답으로 오인 — 반복 실수 8회차·MEMORY 2026-08-03. 결정 로그에 "등재"로 선언됐으나 본문 반영이 누락됐던 것을 2026-08-10 통합점검이 발견해 정정)

- ❌ **만료 없는 유예·제외 금지 (2026-08-03 결정·2026-08-10 통합점검이 본문 등재)** — 미머지 완료분을 전제로 한 유예·제외(그랜드파더)는 반드시 **만료 또는 재확인 지점**을 동반한다. 1차 집행은 규칙 산문이 아니라 코드다(PB-02 그랜드파더 만료 계약 — 동일 유형 텍스트 규칙 2회 실패 후 코드 착지). (사고 경위: 미병합 고립 3회차 — MEMORY 2026-08-03 문제은행 R2. 코드 착지만 있고 CLAUDE.md만 읽는 세션은 원칙 자체를 모르는 상태를 통합점검이 발견해 등재)

- ❌ **완료 산출물을 PR 없이 브랜치에 남긴 채 세션 종료 금지 (2026-08-11 등재)** — "PR을 요청받지 않았다"는 보류 사유가 아니다. 예외 4종(조사·계획 전용 / 미완·게이트 대기 / CI red / Kiki 명시 보류)이 아니면 브랜치 push로 끝내지 않으며, 예외로 끝낼 때도 **어느 예외인지 1줄로 보고**한다. 정본은 위 "✅ 절대 원칙 → 완료·병합", 집행은 `backlog.py done`의 PR 증적 검사. (사고 경위: 미병합 고립 4회차 — 앞 3회는 *구현* 소실, 4회차는 *설계 문서* 소실. 실제 원인은 세션의 망각이 아니라 **워크플로 공백**이었다 — `/drive` 루프에 PR 단계 자체가 없었고 `done`이 커밋 해시만으로 통과했다)

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
- **사용자에게 보이는 모든 출력은 한국어로 표시한다** — 이미지·로그·리포트·CLI 메시지를 불문하고 한국어가 기본값이다. **한국어 Windows PowerShell/콘솔은 기본 인코딩이 cp949이므로, 터미널로 직접 출력하는 한국어 텍스트는 cp949에 없는 문자(예: em dash `—`, smart quote, 일부 유니코드 기호)를 쓰지 않거나, 출력 전 `errors="replace"`/`encode`로 안전하게 보낸다** — 그렇지 않으면 `UnicodeEncodeError`로 명령이 중단되고 사용자는 한국어 메시지를 못 본다(2026-08-15 S4-16 harness `print(render_report(...))` cp949 깨짐 실측). 파일 쓰기/읽기는 항상 `encoding="utf-8"`을 명시한다. (2026-08-15 등재)
- **외부 도구가 읽는 설정 파일은 그 도구의 읽기 인코딩을 확인하고 맞춘다** — 로케일 인코딩(한국어 Windows=cp949)으로 읽는 파일(uvicorn `--log-config` 등)은 **ASCII 전용** + 회귀 테스트 동결. 한국어 설명은 파일이 아니라 런북/문서에 둔다. **같은 원리로, 우리가 파싱하는 외부 서브프로세스 출력(git 등)의 디코딩도 인코딩을 명시한다** — Windows 로케일(cp949)에서 기본 인코딩 디코드는 붕괴한다(HARN-19 실측 2026-08-08 — 대책 코드 = `GitOutputDecodeError`·`tests/harness/test_subprocess_encoding.py` 동결). (2026-07-17 logconfig UnicodeDecodeError 기동 실패 실측 — `test_wh1_shadow_logconfig.py` 선례)

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

### 실수 관리 (2026-07-16 Kiki 지정 — 의무)
- **시스템 실수**(도구·인프라·프로세스 결함에서 비롯된 실수) 또는 **반복 실수**(동일 유형 2회 이상)는 **재발방지대책 등재가 의무**다. 절차: ①원인을 실측으로 규명 ②대책을 CLAUDE.md 규칙(행동 규칙) 또는 backlog 태스크(코드·설계 수정)로 등재 ③MEMORY 결정 로그에 사고 경위 기록 — 해당 세션이 끝나기 전에 완료한다
- "다음엔 조심한다"는 대책이 아니다 — 대책은 **규칙(자동 로드)·코드(테스트 동결)·태스크(추적)** 중 하나의 형태여야 한다
- 등재된 규칙에는 사고 경위를 1줄 병기한다(왜 생긴 규칙인지 미래 세션이 알 수 있게)

### 검증 권위 (초인간 검증 기준 v1 — 2026-07-08)
- 콘텐츠 안전의 정의 = "누가 봤는가"가 아니라 **"무엇이 측정으로 증명됐는가"** (`docs/standards/superhuman_verification_standard.md`)
- 검증 권위 서열: ① **기계 증명**(SymPy·도구) ② **측정 통과 기계 게이트**(6축: 전수성·적대성·독립 다관점·재현성·보증 상한·상시성 — 강등전 승리로 승격) ③ **인간 폴백**(측정 미달·undecidable 구간만)
- 인간 검수도 하나의 검출기다 — 오류율이 측정되지 않은 검출기를 "최종 권위"로 가정하지 않는다
- 게이트 판정은 항상 CLI exit 0/1(Wilson 단측 경계) — 점추정·인상 판정 금지

### 완료·병합 (2026-08-11 Kiki 지정)
- **산출물이 있으면 요청 없이 PR을 연다** — "PR을 요청받지 않았다"는 PR을 만들지 않을 사유가 아니다. 그 기본값의 취지는 *원치 않는 PR을 밀어붙이지 않는 것*인데, 이 저장소에서는 정반대로 굳어 **완료작업 고립**을 낳았다(미병합 고립 4회차 · 미해결 장기 미머지 브랜치 19건 · 2026-08-04 정리 당시 9개 브랜치가 완료작업 13건을 고립, 그 현상을 고치는 태스크 `HARN-12` 자신이 고립돼 있었다). 커밋이 있고 아래 예외에 해당하지 않으면 **PR 생성이 기본값**이다.
- **되돌리기 어려운 행위만 사람에게 남긴다** — PR 생성은 기본값, **main 머지는 `"pr"` 지시 또는 Kiki 판단**. 열린 PR은 닫으면 그만이지만 머지된 main은 그렇지 않다.
- **PR을 열지 않는 예외 4종** (이외의 사유로 보류 금지):
  ① 조사·계획 전용 세션(코드·문서 산출물 없음) ② 미완 또는 사람 게이트 대기 ③ CI red — 먼저 고친다 ④ Kiki의 명시적 보류 지시
  예외로 종료할 때는 **어느 예외인지 사용자에게 1줄로 말한다** — 침묵 보류는 예외가 아니라 구멍이다.
- **집행 지점**(정본화와 별항 — "정본화를 집행으로 착각한 완료 선언 금지" 준수) = `backlog.py done`의 PR 증적 검사. 증적에 PR 참조(`#12`·`.../pull/12`)가 없으면 **exit 1로 거부**하고, 예외는 `--no-pr {investigation|incomplete|ci-red|kiki-hold}`로만 통과한다(사유는 태스크 notes·이벤트 대장에 기록). 스쿼시 머지 커밋 메시지의 `(#758)` 관례를 그대로 수용하므로 기존 증적 표기는 손댈 필요가 없다. **한계(명시)**: PR의 *실재*는 확인하지 않는다 — 이 게이트가 막는 것은 *망각*이지 *위조*가 아니다(GitHub API 조회는 오프라인·프록시에서 fail-open이 되므로 의도적 미채택).

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

### 작업일정 정본 = 빌드 하네스 (`backlog/` + `scripts/harness/`)
- "다음 할 일"은 추론하지 말고 `python3 scripts/harness/backlog.py next`가 계산한다
- SessionStart 훅이 매 세션 브리핑(현재 스테이지·next·게이트 리마인드)을 자동 주입한다
- 상세 규약: `docs/standards/build_harness.md`

### 순차 진행 (기본 모드)
```
/drive                      ← 백로그의 다음 태스크를 순차 처리 (사람 게이트에서 정지)
/gates                      ← Kiki 행동 대기 게이트 점검·clear(evidence 필수)
```

### 새 기능 개발 시
```
1. /plan [기능명]            ← 계획 수립 + backlog 태스크 등록 (7계층 확인)
2. /implement [태스크 id]    ← start(claim) → 서브에이전트 위임 → done(증적 필수)
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

### 배포 시
```
/deploy                     ← 개발→스테이징→프로덕션 안전 배포 (.claude/commands/deploy.md)
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
- `docs/standards/dev_constitution.md` — 개발 헌법 v2 (초기 단계용 경량 요약 — 초보자 온보딩·일상 작업 규칙). **본 CLAUDE.md가 심화·법령·아키텍처·검증 정본이며 충돌 시 CLAUDE.md 우선**
- `MEMORY.md` — 결정 로그·현재 상태
- `ROADMAP.md` — Phase별 일정
- `docs/architecture/00_overview.md` — 7계층 요약
- `docs/standards/prompt_engineering.md` — 프롬프트 기준
- `docs/standards/build_harness.md` — 빌드 하네스 규약 (작업일정 정본 `backlog/`·순차 조율·게이트)
- `docs/standards/build_checkpoint_questions.md` — 구축 플레이북 단계별 진행 점검 질문 세트 (`/review`·`/status` 시)
- `docs/standards/playbook_part_review_questions.md` — 구축 플레이북 Part 0~12 순차 설계-준수 점검 질문 세트

### 상세 (필요 시 읽기)
- `docs/strategy/knowledge_fabric_vision_v1.md` — 장기 비전 북극성 (Education Knowledge Fabric / Metadata OS — 서사 정본, 실행 정본은 backlog)
- `docs/architecture/01-07_*.md` — 각 계층 상세 명세
- `docs/architecture/03b_wh_s_solver_harness.md`·`04a_wh1_tutoring_harness.md` — 하네스 설계안(WH-S 솔버·WH-1 튜터링·횡단 인프라)
- `docs/standards/system_superiority_maintenance.md` — 시스템 우월성 유지(SSM): 분기별 기술 트렌드 능동 스캔·도입 게이트(상시 붕괴 방어와 상보)
- `docs/strategy/*.md` — 시장·차별화·리스크
- `docs/data/licensing_safety.md` — 데이터 라이선스 매트릭스
- `docs/prompts/*.md` — 프롬프트 템플릿 라이브러리
- `docs/standards/testing.md` — 테스트 피라미드·**커버리지 게이트 정본**(집계 70% + 계층 floor l4=90%·l1/l2/api=80%·l3=70% — 수치의 단일 진실 원천은 `scripts/coverage/check_layer_coverage.py`의 `LAYER_FLOORS`)
- `docs/standards/security_privacy.md` — 미성년 PII·암호화·보존 파기 정본
- `docs/standards/incident_response_slo.md` — 인시던트 런북·최소 SLO 정본(`test_slo_contract.py` 기계 대조)
- `docs/standards/crosswalk_gate_contract.md` — 오개념 kebab↔M-id 승인·적재 게이트 계약 정본(코드 동결)
- `docs/standards/coding_python.md`·`coding_flutter.md` — 언어별 코딩 표준
- `docs/standards/data_pipeline.md` — 데이터 6단계 흐름·도구 표준
- `docs/standards/parallel_sessions.md` — 병렬 세션 규약(1 세션 = 1 도메인 = 1 브랜치 = 1 worktree)
- `docs/standards/current_phase_checklist.md` — Phase 1 완수 체크리스트

*(2026-08-10 통합점검: 위 8줄은 인덱스 누락 보강 — 규범 문서가 헌법 인덱스에서 안 보이던 상태 해소)*

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
- **"pr" 단축어** = *PR 생성 → CI 통과 대기 → 자동 머지(SQUASH)까지 일괄 진행*. 별도 "머지" 지시 불요(CI 실패 시 진단·수정·재시도 후 green일 때 머지). (2026-06-18 합의) **2026-08-11 보정**: PR *생성*은 이제 지시 없이도 기본값이므로(위 "✅ 절대 원칙 → 완료·병합"), 이 단축어가 추가로 지시하는 것은 **CI 대기 + 자동 머지** 구간이다.
- **Kiki 머신(Phaiakes9) 행동 요청 시 실행 명령 동봉 필수** — git pull·env 설정·CLI 실행 등 Kiki가 직접 실행할 작업을 안내할 때는 항상 복사-붙여넣기 가능한 명령 블록(PowerShell 기준·작업 디렉터리 명시)을 함께 제공한다. 특히 **미머지 브랜치의 신규 파일을 쓰는 명령이면 해당 브랜치 fetch/checkout(또는 pull) 명령을 반드시 선행 포함**한다(2026-07-14 `fill_live_cost_table.py` 부재 오류 재발 방지 합의). **재시작(force-push)됐거나 그럴 수 있는 브랜치는 `git fetch` + `git checkout -B <branch> origin/<branch>` 형태로만 안내한다** — pull은 diverged 상태에서 add/add 머지 충돌을 낸다(2026-07-17 HARN-06 yaml 충돌 실측).
- **시크릿 입력 안내 규칙 (2026-07-16 자리표시자 키 사고 재발 방지)**: ① 명령 블록·런북의 시크릿 예시에 생략 문자(`pk-lf-…`) 형태를 **복사-실행되는 위치에 두지 않는다** — 치환 자리는 `여기에_실제_키_전체`로 명시 ② 시크릿 등록 명령에는 **등록 직후 자가검증 스텝**(길이·`…` 문자 포함 여부 검사, 키 값 미출력)을 반드시 동봉 ③ 키를 소비하는 실행을 안내하기 전에 자가검증 통과를 선행 조건으로 명시한다. (사고 경위: S1-12 런북의 예시 `pk-lf-…`가 그대로 User 환경변수로 등록 → 관측이 무증상 0건 → 게이트 ② 측정 3회 공전)
- **Kiki 머신의 WhyMath 작업 장소(고정)**: `C:\Users\kiki\Desktop\__AI\WhyMath` — Kiki에게 안내하는 모든 명령 블록의 `cd`는 이 경로를 사용한다. 자리표시자("실제 경로에 맞게 조정") 금지 (2026-07-16 Kiki 지정).
- **Kiki 머신 안내 명령의 실행기 단독 호출 금지 (2026-07-27 등재)**: `pip`·`pytest`·`alembic` 등 실행기를 단독 명령으로 안내하지 않는다 — 항상 **`python -m pip` / `python -m pytest`** 형태로 `python`과 동일 인터프리터를 강제한다. Kiki 머신은 conda base + `.venv`가 동시 활성인 다중 환경이라 단독 실행기는 다른 인터프리터에 결합될 수 있다. (사고 경위: ARCH-16 캘리브레이션 런북에서 `pip install`이 miniconda 계열로 실행돼 유저 site의 sentence-transformers를 already-satisfied 판정 → `.venv`의 `python`은 유저 site 차단이라 import 실패 — "서로 다른 venv에서 절반씩 성립" 2026-07-16 유형의 재발. 런북의 설치 직후 자가검증 스텝이 실행 전 차단해 피해 0)
- **Kiki 직접 수행 과제의 사전 브리핑 템플릿 의무 (2026-07-17 Kiki 지정)**: Kiki가 직접 수행할 과제를 안내할 때는 명령 블록·조작 안내에 앞서 다음 **6항목 브리핑**을 반드시 제공한다 — 내용상·방법상 오해와 혼선을 사전에 제거하는 것이 목적:
  1. **과제 명칭** — 무엇을 하는 과제인지 한 줄 이름
  2. **목적** — 왜 하는가, 결과가 어디에 쓰이는가
  3. **구체적 절차** — 단계 순서·각 단계에서 무엇이 일어나는지·예상 출력(소요 시간 포함)
  4. **성공 기준** — 무엇이 보이면 성공이고 무엇이 보이면 실패인지(자가검증 스텝과 연동·실패 시 대처 1개 병기)
  5. **실행 환경** — 어느 머신·어느 시스템(PowerShell/WSL/패드 등)·작업 디렉터리·선행 조건(서버 가동·기기 연결 등)
  6. **창 구분** — 새 창인지 기존 창인지, 기존이면 *어느* 창인지(창 라벨 명시)·그 창의 이후 조작 가능 여부
  기존 규칙(진입 경로 완전 명시·자가검증 동봉·서버 점유 창 분리·시크릿 자가검증)과 결합 적용한다.
- **실행 시스템 진입 경로 완전 명시 (2026-07-16 Kiki 지정)**: Kiki에게 안내하는 모든 명령 블록은 첫 줄부터 ①실행 시스템 라벨(주석) ②그 시스템으로 들어가는 진입 명령 ③작업 디렉토리까지의 `cd`를 빠짐없이 포함한다. 시스템별 고정 진입 경로:
  - **Windows PowerShell**: `cd C:\Users\kiki\Desktop\__AI\WhyMath` (진입 명령 불요 — 기본 환경)
  - **Phaiakes9 (NucBox EVO-X2) = Kiki의 작업 PC 그 자체** — 별도 접속 불요. 평소 쓰는 Windows PowerShell이 곧 Phaiakes9이며, SSH를 안내하지 않는다(자기 자신 접속이 됨 — 2026-07-16 실측: `ssh kiki@192.168.0.3`의 host key가 known_hosts에 `localhost`로 기등록, `run_demo.ps1`도 "이 PC(Phaiakes9)" 명기). 리눅스가 꼭 필요한 작업만 `wsl` 한 줄로 진입하며, WSL에서 리포는 `/mnt/c/Users/kiki/Desktop/__AI/WhyMath`(Windows 클론 공유 마운트 — 별도 pull 불요)를 사용한다.
  - **로컬 DB 지도 (2026-07-16 실측)**: ① **prod DB = docker `whymath-pg`** (pgvector/pg16 · 호스트 포트 **5433** · trust · user/db=whymath) — 적재 데이터가 사는 곳, 진단·스캔은 여기: `postgresql://whymath@127.0.0.1:5433/whymath` ② **시연용 = docker `whymath-demo-db`** (호스트 55432 · 볼륨 없는 일회용 — stop_demo 시 데이터 소멸, `docker compose -f docker-compose.demo.yml up -d`로 재생성) ③ 5432는 타 프로젝트(AVAC 등) 점유 — WhyMath 안내에 사용 금지. systemd/네이티브 postgres는 없다 — sudo systemctl 안내 금지.
- **실기기 앱 실행 안내 = 백엔드 도달성·인증 선결 필수 (2026-07-20 "문제를 불러오지 못했어요" 사고 재발 방지)**: Flutter 앱을 *실기기*에서 구동하도록 안내할 때 bare `flutter run`만 주지 않는다 — 앱은 백엔드(문제·코치 API)에 닿아야 동작하므로 반드시 ①백엔드 기동(`.\scripts\demo\run_demo.ps1` — Docker Postgres·문제 시드·uvicorn `0.0.0.0`·데모 토큰·LAN IP 일괄) ②실기기 도달 주소+인증 주입(`flutter run --dart-define=API_URL=http://<PC의 LAN IP>:8000 --dart-define=DEMO_TOKEN=<발급토큰>`)을 선결·동봉한다. 근거: **실기기에서 `localhost`는 기기 자신**이라 PC 백엔드에 안 닿고(기본값 `http://localhost:8000`을 그대로 쓰면 실패·`core/env.dart`), 보호 엔드포인트(`/v1/me/*`)는 토큰 없이 401 → 진단(`diagnosis_controller`)이 "문제를 불러오지 못했어요"로 graceful 실패한다. dart-define 명령은 run_demo가 출력한 *값이 채워진 줄*을 통째로 복사하게 한다(자리표시 `<...>` 직접 타이핑 금지 — PowerShell `<` 예약어 거부 + 재실행 시 `WHYMATH_JWT_SECRET_KEY` 로테이션으로 이전 토큰 즉시 무효). 실기기 데모 트러블슈팅은 추측 전에 반드시 `/demo-doctor` 스킬 카탈로그(특히 D행)를 먼저 조회한다. 전제: 태블릿·PC 동일 WiFi + Docker Desktop 가동. (기존 "검증 없는 실행 안내 금지·가정 기반 런북 금지"의 실기기 구체화 — 사고 경위: MOB-06 실기기 확인 안내에서 백엔드 기동·두 dart-define을 빠뜨린 bare `flutter run`을 줌.)

---

**버전**: 0.2.2 | **최종 수정**: 2026-08-11 (PR 기본값 전환 — 완료·병합 원칙 신설 + `backlog.py done` PR 증적 게이트, `HARN-23`) · 이전: 2026-08-11 (운영(EOS) 3차 재점검 — 스택 표 모니터링 행 실측 정합: OTel 미배선 병기. `docs/architecture/operations_module_gap_review_r3.md` §정정) · 2026-08-10 (통합점검 — `docs/reviews/harness_constitution_rules_integrated_audit_2026-08-10.md`)  
**다음 검토일**: Phase 1 종료 시점 또는 다음 분기 SSM 스캔 중 먼저 오는 쪽 · **본문 규칙을 바꾸는 커밋은 이 버전·수정일 표기도 함께 갱신한다** (2026-08-10 통합점검: 표기가 실체보다 3개월 뒤처져 있던 상태 재발 방지)
