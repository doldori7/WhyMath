# S1 E2E 수직 슬라이스 설계 (고3 수능 wedge 1루프)

> **작성일**: 2026-07-04 | **상태**: 설계안 (Kiki 승인 게이트 — 승인 전 구현 0) | **근거**: 실코드 매핑 실측 (파일:라인 앵커)
>
> 로드맵 S1(`docs/strategy/status_roadmap_2026-07.md` §S1)의 실행 설계. **핵심 발견: 6단계의 엔진·좌석은 대체로 이미 존재하나, E2E를 잇는 글루가 미배선.** S1의 임계 경로는 신규 알고리즘이 아니라 **① 기존 좌석 간 배선 + ② LLM 도구 정책 1종 신설 + ③ 검증 게이트 강제**다.

---

## 0. 요약 — S1은 "짓기"가 아니라 "잇기"다

실코드 매핑(2026-07-04) 결론: 6단계 각각의 엔진(L2 수치·L4 교수학·L3 검증·WH-1 하네스 8도구·OCR·atom search)은 **구현돼 있고 라이브 키 없이 hermetic 구동 가능**하다. 미비한 것은 단계를 잇는 **글루 4종**:

| # | 미배선 글루 | 위치 | S1 임계도 |
|---|---|---|---|
| G1 | **LLM 도구 정책** (WH-1 `TutorPolicy` 프로덕션 구현체) | `harness/wh1_loop.py:243` Protocol만·`ScriptedTutorPolicy`(테스트용)뿐 | ★★★ 최임계 |
| G2 | **WH-1 하네스 HTTP 노출** (`run_tutoring_turn`이 harness+test 전용) | `harness/wh1_session.py`·`api/coach.py`가 하네스 미경유 | ★★★ |
| G3 | **검증 게이트 강제** (coach는 verify 실패해도 응답) | verify-before-finalize는 `wh1_loop.py:346`에만·HTTP 미배선 | ★★★ |
| G4 | **mobile OCR→coach 글루** (앱에서 OCR 출력이 coach 제출로 안 이어짐) | `features/chat/`가 `ocr_api` 미import·서버측 `ocr_handoff.py`는 계약 정의됨 | ★★ |
| G5 | **웜스타트 시딩** (진단 시작점에 직전 가설·고빈도 오개념 프리로드) | 미구현 (`whs/harness.py:300`의 "웜스타트"는 WH-S 솔버·무관) | ★★ |

**S1 목표 재정의**: 위 글루를 채워 **고3 1명이 수능 미적분 1문제를 온보딩부터 검증응답까지 완주**하는 것을 실기기에서 실증. mock-우선(라이브 키 없이) 전 구간 구동 후, Kiki 라이브 키로 실 비용·guard_cloud 튜닝(S1 후반).

---

## 1. 루프 6단계 × 실코드 매핑 × 계약 상태

### ① 온보딩 → 학생 초기 상태
- **엔진/좌석**: OAuth `api/auth.py:198`(`POST /v1/auth/{provider}/callback`) · 초기 상태 저장 `api/users.py:103`(`PATCH /v1/users/me`, 화이트리스트에 `target_grade`·`target_score`·`target_exam_date`·`birth_year`·`is_minor`는 birth_year 서버 파생 `users.py:151`) · mobile `features/onboarding/presentation/onboarding_screen.dart`(3페이지 캐러셀).
- **계약 상태**: 🔴 **끊김**. 온보딩 화면이 데이터 수집 0(순수 인트로)·전용 초기화 엔드포인트 부재·`UserTrackHistory`(`db/models/__init__.py:119`) 쓰기 좌석 없음.
- **S1 배선**: 온보딩 화면에 학년·트랙 입력 추가 → `PATCH /me`로 저장 → ②의 웜스타트 시딩 훅 호출. (신규 알고리즘 0·기존 필드 재사용)

### ② CAT 진단 (웜스타트)
- **엔진/좌석**: 🟢 견고. `l2/irt.py::select_weighted_item`(`:243`)·SE 중단 규칙(`:217`)·`api/me.py:1439`(`GET /v1/me/next-problem` — θ 추정→정보량 최대 출제→중단 권고, BKT+IRT 융합 완성형). 진단 API 다수(`/diagnosis/concepts`·`/ability`·`/mastery`·`/weak-concepts`).
- **계약 상태**: 🟡 출제 루프는 완성 / 🔴 **웜스타트 미구현**. 오개념 가설 영속·큐레이션(coach `_apply_hypotheses` `api/coach.py:1068`)은 존재하나 진단 시작점에 미배선.
- **S1 배선(G5)**: 진단 시작 시 직전 세션 가설 + 단원 고빈도 오개념을 프리로드하는 얇은 시딩 함수. **오개념은 초기 context에 preload 금지**(CLAUDE.md) — 웜스타트는 *진단 문항 선별 힌트*로만 쓰고 코칭 context엔 reactive retrieval 유지.

### ③ 동등문제 제시
- **엔진/좌석**: `api/problems.py`(CRUD·필터) · `api/gating.py:305`(`GET /v1/gating/suneung`) · `l6/suneung/gating.py::select_suneung_items`.
- **계약 상태**: 🟡 **제시 좌석 존재 / 동등문제 생성은 S2**. 현 좌석은 기존 문제 풀 선별이지 진단 오개념→동등문제 라우팅 아님. S1은 **소수 시드 문제(수동 저작 or S2 선행분)로 제시만 실증**, 생성 스케일은 S2.
- **S1 배선**: 진단 약점 개념 → `search_atoms`(⑧) → 해당 원자 태그 문제 선별. (문제 풀이 얇아도 1루프 실증엔 충분)

### ④ 풀이입력 (평문 텍스트 / OCR)
> **정정(구조 감사 2026-07-04)**: 초안의 "MathLive 경로"는 오칭. **MathLive는 웹 그래핑 계산기의 수식 입력칸(시각화 렌더러)이지 풀이 제출기가 아니다**(`GraphingCalculator.jsx:23-41`·`graphing_calculator_webview.dart`는 검증된 `Visualization.spec` 렌더). **실제 풀이입력 = 평문 `TextField`**(`chat_screen.dart:38`)→줄 분해→`solution_steps`.
- **엔진/좌석**: 평문 풀이 `chat_controller.dart:89-108`(줄 단위→`CoachRequest(solution_steps)`·`ocr_confidence` 미설정) · OCR `api/ocr.py:40`(`POST /v1/ocr`)·서버측 글루 `api/ocr_handoff.py`(plain_latex→`student_solution`·계약 테스트 `test_ocr_handoff.py`).
- **계약 상태**: 🟢 **평문 경로 완결 / 🟡 OCR 서버 계약 정의·mobile 끊김(G4)**. `features/chat/`가 `ocr_api` 미import — OCR 화면 결과가 chat 제출로 안 이어짐. 음성 풀이입력(STT) HTTP 좌석 부재(speech는 TTS 낭독만).
- **S1 배선**: **평문→solution_steps→coach 경로만으로 완주 가능**(OCR 무관). OCR 브리지(G4·mobile OCR→coach)는 병행·후순위(실모델 Qwen3-VL은 Kiki). OCR 경로가 추가로 주는 것은 `ocr_confidence` 저신뢰 게이팅(손글씨 오인식 보호)뿐 — verify_solution 단계별 검증 자체는 두 경로 동일.

### ⑤ WH-1 코칭 (도구 루프)
- **엔진/좌석**: 🟢 **도구 8종 전부 구현** (`harness/wh1_loop.py::_exec` `:361` — read_student_state·verify_step·match_misconception·curate_hypothesis·query_curriculum·select_probe(ε-탐색 강제 `:409`)·log_evidence·end_turn `:454`). 멀티턴 `wh1_session.py`. L4 교수학(polya·socratic·misconception judge·lthc) 완비. coach 엔드포인트 `api/coach.py:995`(`/v1/coach`)·`:1029`(sessions).
- **계약 상태**: 🔴 **두 결정적 갭**. (G1) `TutorPolicy`는 Protocol뿐·구현체는 `ScriptedTutorPolicy`(테스트용)·**LLM 정책 없음**(`wh1_loop.py:243-244`). (G2) `run_tutoring_turn`은 harness+test 전용·**HTTP 미노출**. coach.py 주경로는 결정론적(`_build_response_payload`)·LLM 사실상 0(유일 시임 `LLMJudge` 오개념 게이트·기본 OFF `coach.py:564`).
- **S1 배선(G1·G2 — 최임계)**: **LLM 도구 정책 1종 신설** — `TutorPolicy` 구현체가 L3 라우터 경유로 "다음 교수학적 행동(도구 선택)"만 판단. mock: `ScriptedTutorPolicy`로 hermetic 검증 → 로컬 Ollama로 실 LLM → Kiki 클라우드 키로 튜닝. `run_tutoring_turn`을 coach sessions 엔드포인트에 배선(하네스 경유로 전환).

### ⑥ 3-tier 검증응답
- **엔진/좌석**: Tier1 수치 `l3/verify_answer.py`(`:240` SymPy 샘플링·3상태·단독 금지 `:41`) · Tier2 기호 `l3/verify_solution.py`·`l3/symbolic_equivalence.py`(`:132` 동치 단일 권위) · combiner `whs/verdict.py::final_verdict`(`:77`) · HTTP `api/verify.py:62`(`/v1/verify-step`)·`:107`(`/v1/verify-solution`).
- **계약 상태**: 🟡 **Tier1+2 실동작 / Tier3(Lean4) 미구현(로드맵)** · 🔴 **검증 게이트 미강제(G3)**. coach는 `solution_steps` 있으면 Tier2 `verify_solution` 실호출(`solution_coaching.py:48`)하나 **검증 실패해도 코칭 반환** — verify는 게이트가 아니라 신호. verify-before-finalize 강제는 `wh1_loop.py:346`(하네스)에만.
- **S1 배선(G3)**: WH-1 하네스 경유(G2)로 전환하면 `end_turn`이 verify 미통과 시 거부하는 강제가 자동 적용. "학생 응답은 PRM/도구 검증 통과 후에만"(CLAUDE.md)이 코드 게이트로 실현. Tier3는 S1 범위 밖(초기 능력 주장은 정직하게 Tier1+2).
  - **✅ 게이트 ③ 코드 증명 완료(2026-07-08)**: 전면 수렴 *없이도* 게이트 ③ 성립을 확정·봉인했다. coach 경로는 정적 결정론 템플릿만 방출(LLM 발화 0)하므로 미검증 발화가 학생에 닿을 표면이 없고, 정답은 shadow sink 전용이다. 4각도 거버넌스/계약 테스트(`tests/backend/harness/test_gate3_student_verification_governance.py`)로 회귀 차단. **coach→하네스 전면 수렴(G2 완전 상환)은 LLM 주도 코칭을 실제로 켤 때의 별도 미래 작업**이며 게이트 ③의 조건이 아니다(테스트 (A) allowlist가 그 미래 배선을 강제 심사).

### ⑦ LLM 라우터 mock (전 구간 hermetic 구동)
- `l3/router.py`(순수 결정)·`CompositeProvider`(`composite.py:27` — local Ollama 필수·cloud Anthropic **선택**`None` 허용). 라이브 키 없이: coach 결정론·verify SymPy·L2 수치·judge FakeJudge/로컬. **전 루프 hermetic 가능** → S1 빌드·통합 테스트는 mock-우선.

### ⑧ atom search 소비 (S0-4a)
- `l1/atom_graph/retrieval.py::search_atoms` · HTTP `api/concepts.py:161`. **현재 진단·코칭 어디에도 미배선**. S1에서 ②③의 약점 개념→원자 검색 지점으로 배선.

---

## 2. Mock 경계 (라이브 키 없이 vs Kiki 필요)

| 구간 | 라이브 키 없이 지금 가능 | Kiki 필요 (S1 후반) |
|---|---|---|
| ① 온보딩 | ✅ OAuth 테스트 provider·PATCH /me | 실 카카오/네이버 앱 등록 |
| ② 진단 | ✅ IRT/BKT 순수 수치 | — |
| ③ 문제 제시 | ✅ 시드 문제 선별 | 동등문제 생성 스케일(S2) |
| ④ 풀이입력 | ✅ MathLive·OCR fake 부품 | OCR Qwen3-VL 실모델 |
| ⑤ 코칭 | ✅ ScriptedPolicy→로컬 Ollama | **클라우드 튜닝·guard_cloud 임계값·실 비용** |
| ⑥ 검증 | ✅ SymPy Tier1+2 | — |
| 트레이스·비용 | ✅ Langfuse 로컬 | 토큰 실비용 회계 |

**S1 빌드 순서 원칙**: 전 글루를 **mock-우선으로 배선·hermetic 통합 테스트 green** → 로컬 Ollama로 실 LLM 도구 정책 검증 → **Kiki 라이브 키로 실 비용·튜닝만 마지막에**. 라이브 키가 크리티컬 패스에 있는 건 ⑤ 튜닝뿐 — 나머지는 전부 지금 자율 가능.

---

## 3. Minimal Reasoning Subgraph 예산 배선 (Part 8 rev.2 해제 트리거)

- **소비처가 이제 생김**: S1의 LLM 도구 정책(G1)이 subgraph를 LLM에 주입하는 **첫 좌석**. Part 8 rev.2가 "소비처 대기"로 보류했던 예산(depth≤2·nodes≤12~20·tokens≤3000)의 해제 트리거가 여기서 충족.
- **배선 지점**: LLM 도구 정책이 `query_curriculum`·`match_misconception` 도구로 컨텍스트를 모을 때, context builder에 **상한을 코드로 박음**. traversal에 visited set·timeout·token budget guard(CLAUDE.md 하드 게이트).
- **fail-open/closed 판정**: 상한 초과 시 **fail-closed**(초과분 절단·정직하게 "컨텍스트 제한" 신호) — 교육적으로 "더 많이 넣을수록 멍청해진다" 원칙상 과다 주입보다 절단이 안전.

---

## 4. 확장 대비 불변식 — subject 하드코딩 검사 지점 (S5 물리 확장 대비)

S1 배선 시 아래 지점에 `if subject == "math"` 류 분기가 스며들지 않는지 검사(status_roadmap §S1 불변식):
- LLM 도구 정책의 프롬프트 템플릿 — 과목 의존은 **템플릿 데이터**에만(코드 분기 0)
- ③ 문제 선별의 원자 태그 — subject는 원자 code 네임스페이스로(S5에서 `physics.*` 병렬)
- ⑥ 검증기 — SymPy는 "수학 커널 plugin"(S2 불변식)·물리는 단위·차원 검증기가 같은 자리
- ② 진단 지표 — 오개념 해소율·답 미루기 깊이는 과목 중립(S3 불변식)

---

## 5. S1 빌드 슬라이스 제안 (승인 후)

Kiki 승인 시 아래 순서(각 4~6게이트+커밋·mock-우선):
1. **S1-a**: LLM 도구 정책 1종 신설(G1) — `TutorPolicy` 구현체·L3 라우터 경유·ScriptedPolicy로 hermetic 검증
2. **S1-b**: WH-1 하네스 HTTP 배선(G2) — coach sessions를 `run_tutoring_turn` 경유로 전환·검증 게이트(G3) 자동 적용
3. **S1-c**: 웜스타트 시딩(G5) + 온보딩 학년·트랙 수집(①) + atom search 배선(⑧)
4. **S1-d**: mobile OCR→coach 글루(G4) + MathLive 완주 경로
5. **S1-e**: Minimal Reasoning Subgraph 예산 코드 배선(§3) + Langfuse 트레이스
6. **S1-f (Kiki)**: 로컬 Ollama→클라우드 전환·실 비용·guard_cloud 튜닝·OCR 실모델·실기기 완주 시연

**탈출 게이트**(status_roadmap §S1): ① 실기기 15분 내 1루프 완주 시연(Kiki 수동) + ② 루프당 비용 실측(**✅ §11 라이브 계측 체인 구조 완료**·수치 튜닝은 트래픽 대기) + ③ "학생 응답 전부 검증 통과 후" 코드 게이트 증명(**✅ 2026-07-08 완료** — `test_gate3_student_verification_governance.py` 4각도 봉인). → 잔여 = ①(Kiki 실기기 시연)뿐.

---

## 6. 리스크 (블록 B 구조 감사에서 심층 검문 예정)
- G1 LLM 도구 정책이 결정론적 coach 주경로와 **이중 결정 경로**가 되지 않게 — 하네스 단일 경로로 수렴
- 웜스타트가 오개념 preload 금기(CLAUDE.md)를 깨지 않게 — 진단 힌트로만·코칭은 reactive
- 검증 게이트 강제가 unverifiable(Tier 판정 불가) 케이스에서 정답 흘림 0 보장
- Minimal Subgraph 상한이 실제 context builder에 박혔는지(주석 아닌 코드)

---

**참조**: `docs/architecture/04a_wh1_tutoring_harness.md`(WH-1 설계 정본) · `docs/standards/part8_context_architecture_review.md` rev.2(예산 해제 트리거) · `docs/strategy/status_roadmap_2026-07.md` §S1·§5(AI 질문) · 실코드 매핑 2026-07-04
