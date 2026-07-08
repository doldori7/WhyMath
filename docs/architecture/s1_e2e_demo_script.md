# S1 1루프 15분 실기기 시연 대본 (탈출 게이트 ①)

> **목적**: S1 탈출 게이트 ①("실기기(패드)에서 1루프 15분 내 완주 시연 녹화") — 고3 1명이 **온보딩부터 검증응답까지**
> 앱 UI로 완주하는 것을 실기기에서 녹화한다. Kiki가 그대로 따라 하며 촬영할 단계별 대본.
> **근거**: PR #488("Flutter 학습 루프 관통 배선") 이후 실 코드 매핑(파일:라인) · `src/mobile/test/e2e_loop_flow_test.dart`(정본 시퀀스).
>
> **탈출 게이트 현황**: ②비용 실측 ✅(§11)·③검증 게이트 ✅(2026-07-08 봉인) → **잔여 = 본 시연(①)뿐.**

---

## 0. #488로 바뀐 것 — 이제 전 구간이 UI다

**PR #488이 온보딩→진단→문제→코치(영속)→검증 루프를 Flutter에 관통 배선했다.** 이전(API 보조노출 필요)과 달리:
- 온보딩 완료 → **`/problem`(진단→문제 카드)** 로 직행(`onboarding_screen.dart:85` `_goToLoop()`).
- 신규 `features/problems/`(진단 컨트롤러·문제 화면) · 코치가 **영속 세션**(`/v1/coach/sessions`)으로 전환 · MathLive 입력 정식 배선.

따라서 **②진단·③문제제시도 화면으로 보인다** — API 보조노출 불필요. `e2e_loop_flow_test.dart`가 앱 계층에서 관통을 증명한다.

**정직한 프레이밍(내레이션에 반드시)**:
- 코치 발문(`decision.prompt`)·문제 생성은 **서버 L4가 담당**(앱엔 LLM 없음) → 코치 품질은 백엔드 LLM 키 상태에 종속.
- **정답값·"틀렸다" 단정·θ/SE 수치는 화면에 안 뜬다**(`coach_signal_card.dart`는 요약 문구만) — 답 미루기·"이유를 묻는 수학" 정체성의 시각 증거.
- 진단은 반복 문항 루프가 아니라 **추천 문제 1장 제시**다(적응형 재출제는 "문제가 바뀌어 나온다"로만 시각화 가능).

---

## 1. ⚠️ 사전 세팅 — 하드 블로커 3종 (녹화 전 반드시 확인)

앱 UI 글루는 완주 배선 완료. 시연을 막는 건 **백엔드/설정 의존성 3가지**다:

1. **인증(최우선)** — 보호 엔드포인트(`/v1/me/next-problem`·코치 세션·`/v1/ocr`)는 토큰 없으면 **401** → 진단이 "문제를 불러오지 못했어요"로 빠져 루프가 안 돈다. 실 로그인 webview(c3)는 미배선(`router.dart:6-9`). **대응**: 사전 시딩된 토큰(`token_store` 복원, `main.dart:18`) 또는 인증 완화된 dev 백엔드.
2. **API_URL 도달성** — 기본 `http://localhost:8000`(`core/env.dart:10`). 실기기에서 localhost는 자기 자신 → 안 붙는다. **대응**: `flutter run --dart-define=API_URL=https://<도달 가능 호스트>`.
3. **백엔드 LLM 키** — 코치 발문·문제 생성이 서버 LLM. 키 없으면 degraded/canned. **대응**: 라이브 키 또는 로컬 Ollama 기동(코칭 자체는 결정론 경로로도 발문·검증 표시됨).

**세팅 순서**: dev 백엔드 기동(시드 문제 + 인증 토큰) → `--dart-define=API_URL` 로 앱 실행 → (선택) 문제 카드 1회 워밍업 → 녹화 시작.

---

## 2. 단계별 대본 (파일:라인 매핑)

| # | 단계 | 화면(파일) | 학생 조작 | 라우팅 | 엔드포인트 | 완주 판정(화면/필드) |
|---|---|---|---|---|---|---|
| ① | **온보딩** | `onboarding_screen.dart` | 철학 3페이지 스와이프 + 목표폼(등급/점수/시험일/출생연도·전부 선택) → **"시작하기"**(또는 "건너뛰기") | `/onboarding`(initial) → `_goToLoop()`:85 → `context.go('/problem')` | `PATCH /v1/users/me`(채워진 필드만·`is_minor` 미포함) | **`/problem`("오늘의 문제") 도착** |
| ② | **진단(자동 로드)** | `problem_screen.dart` | 조작 없음(진입 시 `load()` 자동, `:34`) | 이미 `/problem` | `GET /v1/me/next-problem` → `GET /v1/problems/{id}` + `GET /v1/me/diagnosis/concepts`(`diagnosis_controller.dart:35`) | 로딩 스피너 → **문제 카드 렌더**(`diag.problem!=null`). *중단권고 시*: `problem_id=null`→ **"추천할 문제가 없어요"** 팬(`:70`) |
| ③ | **문제제시** | `problem_screen.dart` `_ProblemView:124` | 과목칩·발문·(객관식)보기 읽기 → **"풀이 시작"** 탭(:167) | `activeProblem` 세팅(:82) → `context.go('/')` | 없음(로컬 전이) | 채팅(`/`) 도착·`activeProblem!=null` |
| ④ | **풀이입력** | `chat_screen.dart` | 하단 모드 토글 **"풀이 단계"**(:328) → 멀티라인 입력 → **"풀이 확인"**(:376). *또는* **"수식으로 입력"**(:344, MathLive) | MathLive: `push('/math-input')`→`pop(latex)`→`sendSolution`(:106) | (입력 수집만) | 학생 버블 즉시 표시 + `LinearProgressIndicator` |
| ⑤ | **코치(영속 세션)** | `chat_screen.dart` `_MessageBubble:201` | 코치 발문 읽고 후속 발화 입력→보내기(2~3턴 권장) | 인라인(`/`) | **첫 발화**: `POST /v1/coach/sessions`(problem_id 배선, `chat_controller.dart:176`) · **이후**: `POST /v1/coach/sessions/{id}/turns`(:181) | 코치 버블(`decision.prompt`) + 소크라테스 배지(:240) 누적·`dialogueId` 유지 |
| ⑥ | **검증 신호** | `coach_signal_card.dart` | 없음(자동) | 없음 | 코치 응답 내장 `solution_coaching.solution_verification`(독립 verify 화면 없음) | **CoachSignalCard**: "N단계 중 M단계 확인"(:139)·"다시 볼 단계가 있어요"(:75, `has_incorrect`)·"스스로 검산해볼까?"(:41, `arithmetic_error`) |

---

## 3. 정본 시퀀스 (e2e_loop_flow_test.dart · 대본 뼈대)

`test/e2e_loop_flow_test.dart`(231줄)가 실 API 클라이언트·컨트롤러로 박제한 7단계 — 대본은 여기에 UI 조작을 덧입힌 것:
1. 온보딩 `PATCH /me`(`is_minor` 미포함) → 2. `DiagnosisController.load()` → next-problem(problem_id·theta·measurement_sufficient) + 문제 로드 → 3. `activeProblem` 세팅 → 4. `sendSolution` → **`POST /coach/sessions`**(dialogueId 확보·problem_id 실림·검증 신호) → 5. `send` → **`/turns`**(dialogueId 유지) → 6. `getSession` → 턴 누적(totalTurns==4) → 7. (회귀 앵커) 독립 `verifySolution`이 코치의 `first_incorrect_index`와 일치.
> **불변식**: 서버가 정답(`answer`)을 보내도 재직렬화·화면에 **미진입**(테스트 :189·:210 봉인) — 게이트 ③과 정합.

---

## 4. "완주" 최종 판정 (한 줄)

> **온보딩 후 `/problem` 문제 카드가 뜨고 → "풀이 시작" → 채팅에서 풀이 전송 → 코치 버블(`decision.prompt`)이 나오며
> → 그 아래 CoachSignalCard 검증 신호("N단계 중 M단계 확인" 등)가 뜨면 1루프 완주.** 앱 UI 하드 블로커 없음(§1 백엔드 3종만 사전 충족).

---

## 5. 15분 예산 · 병목

| 단계 | 권장 | 좌우 요인 |
|---|---|---|
| ① 온보딩 | ~2분 | 스와이프 4페이지·"건너뛰기"로 폼 생략 가능 |
| ② 진단 로드 | ~1~2분 | GET 3연속 왕복·서버 문제생성이 LLM이면 콜드스타트 지연 |
| ③ 문제 읽기+시작 | ~1분 | 발문 길이·로컬 전이(즉시) |
| ④ 풀이입력 | ~2~3분 | MathLive WebView 초기 로드(~1~2s·오프라인)·타이핑 |
| **⑤ 코치 멀티턴** | **~5~6분** | **최대 병목** — 턴당 서버 LLM 1회(cloud면 5~30s). **2~3턴으로 제한** |
| ⑥ 검증 신호 | 즉시 | 코치 응답 내장·별도 대기 없음 |

**팁**: 코치 턴 지연이 전체를 좌우 → 턴 수 2~3개로 제한·문제 카드 사전 워밍업(진단 GET 콜드스타트 대비).

---

## 6. 소프트 경계 (graceful·블로커 아님)

- **OCR 실모델**: `/v1/ocr` 서버측(PaddleOCR+Qwen3-VL)·비활성 시 503·미인증 401 삼킴. **시연 필수 아님** — MathLive/평문으로 대체(오프라인·안정). OCR 시연하려면 서버 OCR 활성+인증.
- **독립 verify 화면 없음**: `features/verify/`는 `data/verify_api.dart`뿐(회귀 앵커용). 검증은 **코치 내장 신호로만** 시연.
- **θ/SE 수치 미렌더**: "적응형 진단"은 문제가 바뀌어 나오는 것으로만 시각화.
- **온보딩 1회-노출 미도입**: `shared_preferences` 미도입 → 매 진입마다 온보딩. 재시연 시 매번 온보딩부터.

---

**참조**: `docs/architecture/s1_e2e_vertical_slice_design.md`(6단계 정본) · `src/mobile/lib/features/{onboarding,problems,chat}` · `src/mobile/test/e2e_loop_flow_test.dart` · `src/backend/whymath_backend/api/{coach,me,users,problems,verify}.py` · `docs/strategy/status_roadmap_2026-07.md §S1`.
