# MEMORY.md — 결정 로그·현재 상태

> **이 파일은 *대화의 휘발성*에 대한 방어선입니다.**  
> 새로운 결정, 폐기된 접근, 핵심 인사이트를 누적 기록.  
> Claude 세션이 끝나도 *진실*은 여기 남습니다.

---

## 🏷️ 브랜드 (확정)

- **앱명**: WhyMath (와이매스)
- **슬로건 (KR)**: 답이 아닌, 이유를 묻는 수학
- **슬로건 (EN)**: The math that asks why.
- *상세는 아래 "2026-05-14: 브랜드명 확정" 결정 로그 참조*

---

## 📍 현재 상태 (2026-05 시점)

### Phase
- [x] Phase 0: 청사진 수립 완료 (CLAUDE.md, ROADMAP.md, 7계층 아키텍처)
- [~] **Phase 1: MVP 개발 (0~6개월) — *착수*** (2026-05-13)
- [ ] Phase 2: 풀 K-12 (6~12개월)
- [ ] Phase 3: 영재·B2B (12~24개월)

### 활성 작업
- 🔄 **MathScope PRD v1.1 정합성 정렬** — 5단계 문서 정렬 (단계1 MEMORY 결정 로그 → 단계2 CLAUDE·ROADMAP → 단계3 architecture 00~07 → 단계4 agents·data·strategy·legal → 단계5 schemas/v1.1)
- 🔄 **M1.0a Phaiakes9 머신 셋업** — Kiki 수동 (Ubuntu·SSH·드라이버, 가이드 `infra/phaiakes9/SETUP_GUIDE.md`)
- ⏸️ **M1.1 Qwen 벤치마크** — M1.0a 완료 후 자동 (스크립트 준비 완료, 커밋 `b75730b`)
- ✅ 완료: NCIC 성취기준 크롤러(`e41e487`) / `main` 보호 자동 부분 CODEOWNERS·CI(`1207760`)

### 완료된 마일스톤
- 2026-05: 7계층 아키텍처 확정
- 2026-05: 기술 스택 확정 (Flutter + FastAPI + PostgreSQL + Phaiakes9)
- 2026-05: Phase 진입 순서 확정 (메타인지 사고력 → 학교 진도 → 수능 → 영재 → B2B)
- 2026-05-14: GitHub 레포 `doldori7/WhyMath` (Private) 생성 및 첫 푸시 완료

### 미해결 의사결정
- [ ] 수학 교육 도메인 파트너 영입 (M1.3 게이트로 *지연 확정* — 트랙 미정)
- [x] ~~첫 진입 학년~~ → **고1 내신** 확정 (2026-05-13, PRD v1.1 채택 후에도 유지)
- [ ] 벡터 DB: ChromaDB 유지 vs Qdrant 전환 (PRD v1.1 채택으로 발생 — 정렬 단계3 L1/L5에서 결정)
- [ ] 사단법인·재단·법인 형태
- [ ] Cambridge MMP/NRICH 라이선스 협상 시작 시점

---

## 🧭 핵심 결정 로그 (시간 역순)

### 2026-05-14: MathScope PRD v1.1 채택 — 비전·기능 흡수, 구조 골격 WhyMath 유지
**컨텍스트**: Kiki가 별도로 발전시킨 *MathScope PRD v1.1*(1,410줄)이 도착. WhyMath 하네스 문서군(CLAUDE.md·MEMORY.md·ROADMAP.md·docs/architecture/01~07·.claude/agents/)과 같은 프로젝트 비전(메타인지·답 안 주기·Socratic·다중 풀이·Polya·Flutter+FastAPI·Phaiakes9 로컬 LLM)을 공유하나, 두 사고 라인이 갈라져 브랜드·아키텍처·DB 스택·로드맵·데이터 모델·첫 진입 전략이 곳곳에서 충돌. 그대로 두면 *진실의 원천*이 둘이 되어 컨텍스트 오염. PRD는 시장·사업·법률·UX·데이터 모델 면에서 하네스보다 풍부하나, 하네스는 7계층 책임 규율·교수학 깊이가 강함.
**결정**: PRD의 *비전·신규 기능*을 정본으로 흡수하되, 3대 구조 결정은 *WhyMath 골격 유지*.
- **브랜드 = WhyMath 유지**. PRD의 "MathScope (가칭)"는 미확정 가칭 — PRD가 브랜드를 정한 게 아님. WhyMath는 2026-05-14 브랜드 결정 로그에 근거와 함께 확정, GitHub 레포도 `doldori7/WhyMath`. PRD 인용 시 "MathScope" → "WhyMath" 치환.
- **7계층 책임 모델 유지 + PRD 5블록 흡수**. 7계층=책임 레이어(.claude/agents 7개와 직결), PRD 5블록(Client/Backend/DB/ML/Pipeline)=배포 토폴로지 — 직교하는 두 축. 7계층 유지하고 PRD 5블록은 `00_overview.md`에 배포 관점 섹션으로 추가.
- **첫 진입 = 고1 내신 유지**. PRD의 "미분 단원 파일럿"을 "고1 단원 중 하나"로 재해석. 2026-05-13 결정 로그 유지.
- **DB 스택 변경** (CLAUDE.md 기술 스택 표 갱신 대상): Neo4j(개념 그래프)·Qdrant(벡터, 기존 ChromaDB 대체 검토)·ClickHouse(학습 행동 로그)·S3/MinIO(영상·이미지) 추가. 추가 스택: MathLive·D3.js·three.js·Plotly·HDBSCAN·UMAP·OpenAI text-embedding-3-large.
- **PRD 신규 자산 → 7계층 매핑**: 개념 그래프·다국 커리큘럼 매트릭스·교과서 매핑 12단계 파이프라인·자동 커리큘럼 정렬 → L1; `SolutionPath.concept_sequence` → L3; `MasteryState`·`StudentProfile` → L2; 시각화 스택(선언적 `Visualization`) → L5; Socratic 흐름·graded `Hint`·개념 점화 지도 → L4; PIPA 데이터 권한 매트릭스 → 횡단; 사업·법률·5개 핵심 가정 → docs/strategy·docs/legal.
**PRD 논리적 허점 8건과 보정 입장**: ①Phase 1 3개월 과부하 → WhyMath 6개월 Phase 1 유지 ②다국 매트릭스 9~12개국 Phase 1 과욕(본문 §1.6 vs §15.1 불일치) → Phase 3 재배치 ③3개 앱 동시 개발 부담 → 단일 앱 모드 분기 + 대시보드 Phase 3+ 유지 ④BKT 제거 위험 → BKT(P1)→IRT(P2)→DKT(P3) 단계 도입 유지 ⑤개념 시퀀스 동치성 판정 난이도 과소평가 → 휴리스틱+사람 검수 단서 ⑥교과서 학습목표 "페어유즈" 단정 위험 → 변호사 검토 전제 ⑦AWS Seoul 확정 vs Phaiakes9 하이브리드 지연·동기화 비용 미언급 → 기존 하이브리드 인식 유지 ⑧부록 E "별책 9"는 오타 — 수학과 교육과정은 *별책 8*.
**근거**:
- PRD가 "정본"인 것은 *비전·기능·시장·법률 사고의 깊이*에서이지 *구조 결정*에서가 아님. 브랜드·7계층·진입학년은 하네스에 이미 근거와 함께 확정된 사항 — PRD가 그것을 *논박한 게 아니라 모른 채로 작성*된 것.
- 7계층은 서브에이전트 위임 워크플로의 단위 — 폐기하면 워크플로 전체가 흔들림. PRD 5블록과는 축이 달라 양립 가능.
- PRD의 진짜 가치는 자동 커리큘럼 정렬·교과서 매핑 파이프라인·다국 매트릭스·개념 그래프·9개 데이터 엔티티·PIPA 매트릭스·5개 핵심 가정 검증법 — 하네스에 *없던* 자산이며 7계층 안에 깔끔히 들어감.
**대안**:
- *PRD를 완전 정본으로(브랜드·5블록·고2 미분까지)* — 폐기: 이미 확정된 결정 3건을 근거 없이 뒤집음, 서브에이전트 구조 재작성 부담
- *PRD를 독립 문서로 방치* — 폐기: 진실의 원천 이중화, 컨텍스트 오염
- *단일 통합본 신규 작성* — 폐기: 작업량 최대, 하네스의 검증된 구조를 버릴 이유 없음
**적용 범위**: 정렬 실행 계획 5단계 — 단계1 본 결정 로그(MEMORY.md), 단계2 CLAUDE.md+ROADMAP.md, 단계3 docs/architecture/00~07, 단계4 .claude/agents+docs/data+docs/strategy+docs/legal, 단계5 schemas/v1.1/*.yaml 9개 엔티티. 범위 밖: PRD 와이어프레임 구현·엔티티 코드 구현·실제 DB 배포.
**상태**: 확정. 단계별 진행 — 본 로그가 후속 모든 문서의 근거.

### 2026-05-14: `main` 보호 — CODEOWNERS + CI status check 자동화, UI 단계는 별도 가이드
**컨텍스트**: 2026-05-14 GitHub 연결 결정 로그의 후속 작업 "main 보호 규칙(force-push 금지·PR 리뷰 필수) 적용 예정"을 자동 처리하려 했으나, Claude의 GitHub MCP 도구셋에 *Branch Protection* / *Repository Ruleset* 엔드포인트 도구가 부재. 원격이 로컬 MCP 게이트웨이(`http://127.0.0.1:36037/git/doldori7/WhyMath`)라 토큰을 직접 쓸 수도 없음(MCP 도구 외 경로로 REST API 호출 불가). 따라서 *완전 자동*은 불가능, 정책의 *실효성 부분*만 코드로 강제하고 GitHub Settings UI 단계는 5분 수동 가이드로 분리.
**결정**:
- 자동(코드 표현):
  - `.github/CODEOWNERS` — 영역별 자동 리뷰어. 디폴트 `@doldori7`, L1 데이터·L3/L5 인프라·문서·정책·`.github/` 등 영역별 매핑. Phase 2+ 합류 시 분기 가능한 구조
  - `.github/workflows/ci.yml` — push/PR마다 3 job 실행:
    - `data-pipeline — lint·type·test`: ruff·black·mypy-strict·pytest+coverage(fail-under=70)
    - `infra/phaiakes9 — bash syntax`: 모든 infra `.sh` 파일 `bash -n` + shellcheck(non-blocking)
    - `policy-guard — CLAUDE.md 금기 가드`: 검정교과서 본문 인용 패턴·하드코딩 시크릿(sk-/sk-ant-/ghp_/AKIA) 사전 차단
  - concurrency group으로 비용 절감 (동일 ref 재푸시 시 이전 실행 취소)
- 수동(GitHub Settings UI):
  - `.github/branch-protection-setup.md` — 1페이지 체크리스트: PR 1+승인·Code Owners·필수 status check 3종·linear history·force-push 차단·deletion 차단·administrators 포함
  - Kiki가 5분 작업, 완료 시 이 MEMORY 항목 *상태*를 갱신
**근거**:
- **CODEOWNERS 가치**: 보호 규칙 없이도 *PR 자동 리뷰어 지정* 자체 동작. 향후 영역별 도메인 파트너 합류 시 영역만 갱신하면 자동 라우팅
- **CI workflow가 보호의 80%**: "필수 상태 검사 통과" 정책은 *워크플로 자체가 존재*해야 GitHub Settings에서 등록 가능. 즉 보호 규칙은 워크플로의 *적용 정책*이지 *내용*이 아님 — 내용을 미리 갖춰두면 UI 단계는 5분
- **policy-guard job**: CLAUDE.md 절대 금기(검정교과서 본문·하드코딩 시크릿)를 사후 사람 리뷰가 아닌 *기계적 사전 차단*으로 강제. 1인 단계 휴먼 에러 방지
- **MCP 도구 부재의 한계 인정**: 시도조차 안 한 게 아니라 *시도→불가→대안* 흐름을 명시. 향후 GitHub MCP가 branch_protection 도구를 추가하면 그때 자동화. 또는 GitHub App 토큰을 secret으로 받아 workflow 안에서 GH API 호출하는 자기참조 자동화도 가능 (Phase 2 검토)
**대안**:
- *GitHub Actions 워크플로 안에서 GH API로 보호 규칙 셀프 적용* — 자기 워크플로가 자기 보호 규칙을 만드는 *부트스트랩 문제* + Personal Access Token 필요. Phase 2에서 GitHub App 도입 시 검토
- *Pre-receive hook* — GitHub 자체 호스팅 아닌 한 불가
- *완전 수동* — CODEOWNERS·CI 없이 UI만으로는 *어떤 status check가 있는지 모름*. 폐기 이유: 자동화 가능한 80%를 굳이 미룰 이유 없음
**적용 범위 (이번 작업)**:
- 신규: `.github/CODEOWNERS` (27 lines), `.github/workflows/ci.yml` (3 jobs), `.github/branch-protection-setup.md` (UI 단계별 + 트러블슈팅)
- 미적용 (이번 작업 범위 외): UI 보호 규칙 자체 — Kiki가 위 가이드 따라 5분 작업 후 이 항목 *상태* 갱신
**상태**: 부분 확정. 자동 부분(CODEOWNERS·CI·policy-guard) 적용 완료, UI 보호 규칙은 *Kiki 수동 작업 대기*. 완료 시 본 항목 갱신 + 2026-05-14 GitHub 연결 로그의 마지막 줄도 동기 갱신.

### 2026-05-13: M1.1 게이트를 *M1.0a 머신 셋업 + M1.1 벤치마크*로 분리
**컨텍스트**: `/implement backend:phaiakes9-qwen3-math` 위임으로 Ollama 설치·systemd unit·헬스체크·벤치마크 스크립트(`infra/phaiakes9/`, 커밋 `b75730b`, 11 files +1725) 완성 후 Kiki에게 Phaiakes9 콘솔 실행 안내. 그러나 Phaiakes9 머신 자체가 *아직 셋업 안 된 상태*(OS 미설치·전원 OFF·미조립 중 하나)임이 확인됨. 기존 ROADMAP·MEMORY는 *기술 스택 결정*으로 Phaiakes9를 명시했을 뿐, *물리 머신의 부팅·SSH·드라이버 상태*는 별도 추적되지 않았음. 결과적으로 M1.1 게이트("Phaiakes9 Qwen3-Math p50<2s 측정")가 *두 가지 다른 단계*를 한 줄에 묶고 있었음 — (a) 물리·OS·드라이버 셋업, (b) Ollama 운영·벤치마크. 둘은 의존하지만 *책임 주체·자동화 가능성*이 다름.
**결정**:
- M1.1 게이트를 두 단계로 분리:
  - **M1.0a — Phaiakes9 머신 셋업** (수동 + `bootstrap.sh`): Ubuntu 24.04 설치·계정·SSH 키·sshd 하드닝·ufw 방화벽·시간 동기·ROCm(또는 CPU 폴백)
  - **M1.1 — Qwen 벤치마크 게이트**: 기존 README §2 빠른 시작 + `benchmark/run_bench.sh` → `gate_p50_under_2s == true` 판정
- M1.0a 산출물: `infra/phaiakes9/SETUP_GUIDE.md`(약 200 lines, 6 Phase 체크리스트 + 트러블슈팅) + `infra/phaiakes9/bootstrap.sh`(8단계 멱등 부트스트랩, `WHYMATH_SKIP_ROCM`·`WHYMATH_LAN_CIDR` 환경변수)
- M1.0a Phase는 Kiki 수동 작업 의존(하드웨어 상태). 그동안 *블로킹 없는* 독립 작업 진행 가능: NCIC 크롤러·main 보호 규칙·L4 프롬프트 작성·FastAPI 스캐폴딩
**근거**:
- **머신 셋업과 운영 분리의 책임 명확화**: bootstrap은 *재현 가능한 자동화*이지만 BIOS·파티션·SSH 키 등록은 *Kiki만 할 수 있는 결정*. 한 게이트에 묶이면 게이트 통과 정의가 모호해짐
- **Strix Halo APU 특수성**: AMD Ryzen AI Max+ 395는 ROCm 정식 지원 목록에 *아직 미포함*(gfx1151). `HSA_OVERRIDE_GFX_VERSION=11.5.1` 강제 또는 CPU 폴백 결정이 필요한데, 이 판단은 *벤치마크 결과를 보고* 내려야 함. 즉 M1.0a → 1차 벤치마크 → 재조정 루프가 자연스러움
- **컨텍스트 위생**(CLAUDE.md): M1.1 게이트가 *두 가지 다른 진실*을 가지면 진행 보고가 모호해짐. 분리하면 각각 binary pass/fail
- **병렬 작업 금지 원칙과 양립**: M1.0a가 Kiki 수동 작업이므로 Claude/AI 측에서는 *다른 독립 작업* 진행이 정당함(같은 AI가 두 코드 영역 병행이 아님)
**대안**:
- *분리하지 않고 게이트 텍스트만 보강* — "Phaiakes9 머신 셋업 + 벤치마크 p50<2s"로 두 줄. 폐기 이유: 셋업 자체에 1~2주 소요 가능성, 별도 추적 필요
- *Phaiakes9 셋업을 Phase 0 청사진 단계로 소급* — 청사진은 이미 종료. ROADMAP 재작성 부담 큼
- *클라우드 GPU 인스턴스로 임시 우회* — Ryzen AI Max+ 395의 *실제 비용·지연*을 못 잡으므로 게이트 신뢰도 손상. CLAUDE.md "비용 구조를 로컬 LLM 우선" 결정의 검증 무력화
**적용 범위 (이번 작업)**:
- 신규 파일: `infra/phaiakes9/SETUP_GUIDE.md`, `infra/phaiakes9/bootstrap.sh`
- 수정: `infra/phaiakes9/README.md` (M1.0a 안내 섹션 + 디렉토리 트리 갱신 + 자리표시자 `<whymath-root>` 명시화)
- 후속 (이번 작업 범위 외): `ROADMAP.md` 90일 Day 1~14 항목에 *M1.0a 머신 셋업* 한 줄 추가 (별도 PR)
**상태**: 확정. M1.0a 완료 시점에 *별도 결정 로그*로 결과 기록 예정.

### 2026-05-13: Phase 1 MVP 진입 학년 = *고1 내신*, 도메인 파트너 영입은 *M1.3까지 지연*
**컨텍스트**: `/plan Phase1-MVP` 세션에서 두 가지 미해결 의사결정을 동시에 처리해야 했음 — (1) 첫 진입 학년 선택(중2 자유학기제 vs 고1 내신), (2) 도메인 파트너 영입 트랙(KAIST 영재교육원 / 한국수학교육학회 / 대학 수교과 개별 / 셋 다 동시). Phase 1은 *1개 학년·2개 모드*에 깊게 집중한다는 원칙(`docs/architecture/06_application_modes.md` Phase 1 진입점) 하에 결정 필요.
**결정**:
- **첫 진입 학년 = 고1 내신** 단일 트랙. 중2 자유학기제는 Phase 3~4 자유학기제 모드로 미룸(`06_application_modes.md` 모드 6)
- **도메인 파트너 영입 = 명시적 지연**. Day 1~14 핵심 행동 목록에서 제외하고 M1.3(월 3) 이전까지 1명 확보를 후행 게이트로 재배치. Phase 1 종료 게이트(M1.6)의 *도메인 파트너 검수 통과*는 유지
- 게이트 재조정: M1.1 게이트에서 "파트너 구두 동의" 항목 *삭제*, 대신 "Phaiakes9 Qwen3-Math 응답 속도 p50<2s 측정 완료 + NCIC 크롤러 가동"으로 교체
**근거**:
- **고1 내신 선택**: 학부모 결제 의지가 가장 강함 → Phase 1.5~2 결제 시스템 출시 시 전환율 최대화. 내신 점수는 정량 효과 검증이 가능(메타인지·사고력 효과를 단순 수치로 입증). Phase 2 수능·내신 모드(`06_application_modes.md` 모드 2)와 자연스러운 콘텐츠 연결. 반면 중2 자유학기제는 B2B 학교 진입로 매력은 크나 Phase 1의 *β 100명 무료* 단계에서는 매출 신호가 약하고, 학교 단위 진입은 영업 사이클이 6개월 이상이라 Phase 4 B2B 단계에서 다루는 게 시기 적합
- **도메인 파트너 지연**: 영입 자체는 1순위 미해결 의사결정이나, Day 1~14에 *동시 접촉*하면 비기술 작업이 기술 토대 작업(LLM 배포·크롤러·데이터 카드)을 블로킹할 위험. CLAUDE.md "병렬 작업 금지" 원칙(게이트 미달 대응 액션 3)과도 충돌. 사람 수학자 1명의 단발 검수(M1.2)는 도메인 파트너 없이도 확보 가능 → 영입은 *기술 토대가 보여줄 자산이 생긴 후* M1.2~M1.3 사이 진행이 협상력 측면에서 유리
- **고1 내신의 리스크**: 사고력 모드와 내신 압박이 정서적으로 충돌할 수 있음 → L4 정서 안전 필터·프롬프트 설계에서 *내신 점수를 KPI로 강화하지 않는* 톤 유지 필요(CLAUDE.md "정답을 빠르게 KPI 금지")
**대안**:
- *중2 자유학기제* — B2B 진입로·게이미피케이션 절제 용이성 매력. 폐기 이유: Phase 1 β 매출 신호 약함, 학교 영업 사이클 길음
- *둘 다 동시* — 콘텐츠·범위 폭발, MEMORY.md 폐기 패턴 "처음부터 풀 K-12" 위반
- *도메인 파트너 셋 다 동시 접촉* — 리스크 분산은 매력이나 비기술 작업이 기술 토대를 블로킹할 위험·"병렬 작업 금지" 위반
**적용 범위 (이번 작업)**:
- MEMORY.md 미해결 의사결정 섹션 갱신 (첫 진입 학년 항목 *확정으로 이동*, 도메인 파트너 항목 *M1.3 게이트로 재태깅*)
- 후속 작업: ROADMAP.md M1.1 게이트 텍스트 조정, `docs/architecture/06_application_modes.md` "Phase 1 진입점" 주석에 *고1 내신 트랙* 명시 — 별도 PR
**상태**: 확정. 다음 단일 행동은 Phaiakes9에 Qwen3-Math 배포 + NCIC 크롤러 작성 + GitHub `main` 보호 규칙 적용 3건의 *서로 블로킹 없는* 병렬 작업.

### 2026-05-14: GitHub 원격 저장소 연결 (Private)
**컨텍스트**: Phase 0 청사진(7계층·기술 스택·브랜드명)이 모두 확정된 시점. 로컬 git 저장소만 존재했고, 클라우드 백업·미래 협업·CI/CD 기반·코드 리뷰 워크플로의 인프라가 필요한 상태였음. 또한 `WhyMath_harness.zip`·`files.zip` 두 개의 대용량 아카이브가 git에 추적되어 있어 푸시 시 누적 부담이 됨.
**결정**:
- 호스팅: **GitHub**, 레포 URL `https://github.com/doldori7/WhyMath` (Private)
- 기본 브랜치: `main` (GitHub 표준, 기존 `master`에서 변경)
- 사전 정리: `files.zip`·`WhyMath_harness.zip` 추적 해제(working tree는 보존), 사업계획서 docx/pdf는 사용자가 별도 위치로 이동
- `.gitignore` 보강: `*.zip`·`*사업계획*`·`*business_plan*`·`internal/`·`private/`·`.env.*`·`config/secrets.*`·`.openai_cache/`·`.anthropic_cache/`·`.langfuse_cache/`·`data/cache/` 등 약 25개 패턴 추가 (멱등 마커 `# WhyMath 추가 보안 패턴 (자동 생성)`로 중복 추가 방지)
- 자동화: `scripts/01_git_local_setup.ps1`(로컬 정리)·`scripts/02_github_connect.ps1`(GitHub 연결) 두 PowerShell 스크립트로 재현 가능
**근거**:
- **Private 필수**: CLAUDE.md 절대 금기 — "미성년자 개인정보를 분석·마케팅 외부 공유 금지" 및 "학교·학년 정보로 개인 식별 가능한 분석 결과 외부 노출 금지" → 코드 자체에는 학생 데이터가 없지만 향후 시드 데이터·테스트 픽스처에서 실수 노출 가능. Public은 위험 비대칭
- **`main` 브랜치 표준화**: GitHub Actions·외부 도구·튜토리얼 거의 모두 `main` 가정. Phase 1에서 CI/CD 구축 시 마찰 최소화
- **zip 추적 해제**: 1.12 MiB 초기 푸시도 아카이브 없이 진행. 추후 LFS 도입 부담 사전 차단
- **`.gitignore` 사전 보강**: 시크릿·민감 문서가 한 번 푸시되면 git history에 영구 박힘. 사전 패턴 차단이 사후 BFG/filter-repo 대응보다 압도적으로 저렴
**대안**:
- GitLab — 프라이빗 무료 한도가 크지만, 한국 시장에서 GitHub가 인재 풀·생태계 압도. 협업자 합류 시 추가 학습 비용
- 자체 Gitea — Phaiakes9에 호스팅 가능하나 백업·가용성을 직접 관리해야 함. 1인 단계에서 비효율
- 공개(Public) 레포 — 부분 오픈소스 전략은 매력적이나 *현 단계*에서는 도메인 노하우 누출 리스크가 더 큼. Phase 2 이후 *선별적* 공개 검토
**적용 범위 (이번 작업)**:
- 커밋 `0625cf5`: `.claude/settings.json`·`.gitignore`·zip 2개 삭제·사업계획서 docx/pdf 2개 삭제·스크립트 2개 추가
- 푸시: 104 objects, 1.12 MiB, `main → origin/main` upstream 설정 완료
**상태**: 확정. 다음 단계는 GitHub Settings → Branches 에서 `main` 보호 규칙(force-push 금지·PR 리뷰 필수) 적용 예정.

### 2026-05-14: 브랜드명 "WhyMath (와이매스)" 확정
**컨텍스트**: Phase 0 종료 직전, 모든 외부·내부 문서가 일관된 브랜드명을 사용해야 함. 그동안 "한국 중·고 수학 앱"이라는 서술적 가칭 사용
**결정**:
- 정식 앱명: **WhyMath** (한글 표기: **와이매스**)
- 메인 슬로건 (KR): **"답이 아닌, 이유를 묻는 수학"**
- 메인 슬로건 (EN): **"The math that asks why."**
**근거**:
- 핵심 가치 제안(답 미루기·Polya·소크라테스)을 한 단어로 압축
- "Why"는 메타인지·사고력 시장 진입점과 직결, 영문 확장(Phase 5) 시 그대로 사용 가능
- 콴다·EBSi 등 한국 경쟁자와 *이름 단계*에서부터 차별화
**적용 범위 (이번 작업)**: CLAUDE.md / README.md / MEMORY.md / ROADMAP.md / docs/strategy/{market_positioning,differentiation}.md / scripts/setup.sh / .claude/agents/data-engineer.md / .claude/commands/status.md / src/backend/pyproject.toml
**미적용 (별도 작업 예정)**: Python 패키지명 `korean-math-backend`, DB명 `koreanmath`, 모바일 앱 ID 등 *코드 식별자*는 마이그레이션 영향 검토 후 일괄 변경
**상태**: 확정

### 2026-05-13: 시장 진입점을 *메타인지 사고력*으로 결정
**컨텍스트**: 콴다(사진 풀이)·EBSi(강의)·메가스터디(콘텐츠)와 정면 경쟁 불가  
**결정**: "수능 답 풀이"가 아닌 *메타인지·소크라테스·NRICH-style 사고력*에서 시작  
**근거**: Kiki의 메타인지 튜터 자산 직결, 한국 경쟁자 거의 없음, Phase 2에서 수능 시장 진입할 발판  
**대안**: 영재 트랙 우선 — 객단가 높지만 시장 작음, 도메인 파트너 부족  
**상태**: 확정

### 2026-05-13: 데이터 truth source를 *성취기준 코드*로 결정
**컨텍스트**: 검정 교과서 13종·평가원·EBS·학원 등 다층 구조에서 무엇이 진실 원천인가  
**결정**: 교육부 NCIC 성취기준 코드(예: `[9수01-01]`)가 모든 매핑의 root  
**근거**: 모든 출판사가 법적으로 이 코드를 따라야 함, 공공누리 라이선스, 변하지 않음  
**상태**: 확정

### 2026-05-13: 7계층 아키텍처 확정
**결정**: L1 데이터 → L2 학습자 모델 → L3 LLM → L4 교수학 → L5 상호작용 → L6 응용 → L7 커뮤니티  
**근거**: 책임 분리, 유지보수성, 서브에이전트 위임 단위와 일치  
**상태**: 확정. *경계 침범 금지*가 절대 원칙

### 2026-05-13: 비용 구조를 *로컬 LLM 우선*으로 결정
**결정**: Phaiakes9 (Ryzen AI Max+ 395, 128GB) + Qwen3-Math로 80% 처리, 18% Claude/GPT 중급, 2% 최고급  
**근거**: 학생 1인당 일 50~100회 LLM 호출 가정 시 클라우드만 사용하면 객단가 폭발  
**상태**: 확정. 동적 라우터 구현 필요

### 2026-05-13: LLM 답변 패턴을 *답 미루기*로 결정
**결정**: 학생 질문에 *바로 답하지 않음*. Polya 4단계로 진행. 답 제공은 4단계(방향→의사코드→부분→전체) 중 가능한 빠른 단계에서 멈춤  
**근거**: NRICH·Khanmigo가 수렴하는 방향. 한국 학생의 *답 즉시 의존* 패턴이 학습 저해  
**상태**: 확정. 모든 프롬프트 템플릿이 이를 반영해야 함

### 2026-05-13: 데이터 활용 안전선 확정
**결정**: 
- ✅ 가능: 성취기준·기출·학교 정보·OER(CK-12·OpenStax·Siyavula CC), Mathlib(Apache 2.0), 사용자 자기 자료
- ⚠️ 협상 후: NRICH(Cambridge MMP), EBS, AoPS Wiki(CC BY-SA)
- ❌ 절대 금지: 검정 교과서 본문, 학원·인강 콘텐츠, 출판사 풀이집  
**상태**: 확정. `docs/data/licensing_safety.md` 참조

---

## 📚 폐기된 접근 (Anti-Patterns)

### "단순 사진→답 풀이 앱"
**왜 폐기**: 콴다와 정면 충돌. 자본 게임에서 밀림. 그리고 *교육적으로 해롭다* (의존성 강화).

### "AI가 모든 걸 한다" 일체형 LLM 접근
**왜 폐기**: LLM 단독으로는 학습자 모델링·장기 추적·정확도 보장 불가. BKT/IRT 통계 모델 분리 필수.

### "수능 직접 진입"
**왜 폐기**: 입시 검증에 1~2년 걸림. 학부모 신뢰 형성 시간 필요. 메타인지로 신뢰 누적 후 진입이 안전.

### "처음부터 풀 K-12"
**왜 폐기**: 범위 폭발. 1개 학년 검증 후 확장이 위험 관리.

---

## 💡 핵심 인사이트 (장기 보존)

### 1. AI의 진짜 강점은 *답*이 아니라 *질문*
LLM은 답을 빠르게 주는 도구가 아니라, *학생이 스스로 도착하게 만드는* 도구로 쓸 때 가장 강력. 모든 프롬프트 설계의 출발점.

### 2. 한국 시장의 *진짜* 빈자리
- 사고력·메타인지 자원 (NRICH·YouCubed 한국어로 없음)
- 단계별 진단 (콴다는 사진 풀이만, 단계 분석 없음)
- 부모용 인사이트 (학원이 못 채움)
- 사고 과정 *시각화* (3Blue1Brown 한국화 빈약)

### 3. 데이터 자산 = 1~2년 누적 후 *제품과 별도로* 라이선싱 가능
NCIC + 학교알리미 + 검정교과서 매핑 + KMO 디지털화 = B2B 라이선싱 가능한 자산.

### 4. 로컬 LLM은 *비용*이 아니라 *전략*
Phaiakes9를 단순 비용 절감이 아닌 *경쟁자가 못 가진 인프라*로 인식. 클라우드 비용 폭발기에 *유일한 흑자 모델*.

### 5. *부족한 한 자리*: 수학 교육 도메인 파트너
한국에서 Kiki의 자산 조합이 거의 유일하나, *수학 교육 도메인 전문가*가 결정적 빈자리. 1순위 영입 과제.

---

## 🔗 외부 의존성 모니터링

### 라이선스 변경 가능성
- **NuminaMath**: Apache 2.0, 안정
- **MathNet (MIT 2026)**: 막 공개됨, 라이선스 정확 확인 필요
- **NRICH**: 비상업 무료, 상업 라이선스 협상 필요
- **AoPS Wiki**: CC BY-SA, Share-Alike 의무
- **Mathlib**: Apache 2.0, 안정

### 정책 변동 모니터링
- AI 디지털교과서 정책 (정권 영향 큼)
- 2022 개정 교육과정 시행 일정 (2025~2027 단계적)
- 영재교육원 예산·체계 변화
- 사교육비 경감 대책 (시장 영향)

---

## 🧪 실험 로그 (착수 후 누적)

*아직 실험 없음. Phase 1 착수 시 누적 시작.*

| 날짜 | 실험 | 가설 | 결과 | 결정 |
|---|---|---|---|---|
| | | | | |

---

## 🎯 KPI 베이스라인 (정의만 — 측정 시작 후 채움)

### 학습 효과
- 개념 숙달도 (BKT 확률 증가율)
- 오개념 해소율
- 다중 풀이 노출 후 *대안 풀이 시도율*

### 사용자 행동
- 일일 활성 사용자 (DAU)
- 세션당 *답 미루기 단계* 평균 도달 깊이 (1~4)
- 학생이 *스스로* 풀이 도달한 비율

### 비용·기술
- LLM 호출당 평균 비용
- 로컬 LLM 처리 비율 (목표: 80%)
- 응답 지연 (목표: p50 < 2s)

### 사업
- MAU·결제 전환율·이탈률
- B2B 학교 수·교육청 수
- 데이터셋 라이선싱 매출

---

## 📝 다음 업데이트 시점

- 각 결정 발생 시 *즉시*
- 각 Phase 시작·종료 시
- 매월 첫째 주 (정기 리뷰)

---

**최종 수정**: 2026-05-14  
**다음 정기 리뷰**: Phase 1 착수 후 첫 월
