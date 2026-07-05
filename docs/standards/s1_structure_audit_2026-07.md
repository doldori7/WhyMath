# S1 구조 붕괴 감사 (§5 AI 질문 실코드 적용)

> **작성일**: 2026-07-04 | **방법**: status_roadmap §5의 S1 질문 8종을 실코드에 검문(AI를 "구조 붕괴 감지기"로) | **표기**: [실측]=파일:라인 직접 확인 · [추정]=코드 정황 추론
>
> `docs/architecture/s1_e2e_vertical_slice_design.md`(S1 설계)의 실패 모드를 사전 노출해 **S1 빌드 전 상환 목록**을 확정한다. 각 질문 → findings·리스크 등급·상환 필요 여부.

---

## S1 빌드 전 상환 Top 3 (가장 시급)

1. **[높음] 검증 게이트 미강제 (G3)** — stateless `/v1/coach` 경로는 verify 실패해도 코칭을 반환한다. "학생 응답은 검증 통과 후에만"(CLAUDE.md 금기)이 **coach 경로에 미강제**. 강제는 WH-1 하네스 `_exec_end_turn`("verify 없는 finalize 거부", `wh1_loop.py:20-21`)에만 존재 → **S1-b에서 coach를 하네스 경유로 전환**해야 게이트가 자동 적용.
2. **[높음] 미성년 대화 본문 앱-계층 평문 저장** — `DialogueTurn.content`·`image_uri`·`image_analysis`가 앱 계층에서 평문 저장(`dialogue.py:167`·`coach.py:1103,1113`). CLAUDE.md "미성년 채팅 평문 저장 금지"가 **인프라 at-rest 암호화에 전적 위임**돼 코드로 미확인. S1이 실사용자 데이터를 만들기 전 상환(또는 인프라 암호화 존재 문서 확인) 필요.
3. **[중간] LLM 도구 정책 부재 → 이중 결정 경로 위험 (G1)** — WH-1 `TutorPolicy`는 Protocol뿐·구현체는 `ScriptedTutorPolicy`(테스트용). coach.py 주경로는 결정론적. S1에서 LLM 정책을 신설할 때 **결정론 coach와 하네스가 이중 결정 경로**가 되지 않게 단일 경로 수렴 필요.

---

## Q1 [붕괴] 단계 간 계약 — 통합 시 처음 깨질 3곳

[실측] 6단계 엔진·좌석은 존재하나 글루 미배선(설계 §0의 G1~G5). 통합 시 처음 깨질 계약 3개:
1. **mobile OCR→coach (G4)** — `features/chat/chat_controller.dart`가 `ocr_api` 미import(`:9-13`). OCR 화면이 `OcrResult`를 만들지만 coach 제출로 안 이어짐. 서버측 `ocr_handoff.py` 계약은 정의·테스트됨 / mobile만 끊김. **리스크 중간**(S1은 평문 경로로 우회 가능).
2. **WH-1 하네스 HTTP 미노출 (G2)** — `run_tutoring_turn`이 harness+test 전용. coach 엔드포인트가 하네스 미경유 → 도구 8종·검증 의무·ε-탐색이 HTTP 표면에 미적용. **리스크 높음**(S1-b 핵심).
3. **verify 게이트 미강제 (G3)** — 위 Top 3 #1. **리스크 높음**.
- **상환**: G2·G3은 S1-b에서 동시 해소(coach→하네스 경유). G4는 S1-d.

## Q2 [경계] Minimal Reasoning Subgraph 예산 배선

[실측] **예산 상한 코드 부재**. `max_nodes`/`max_tokens`/depth 예산 grep 0(매치된 "budget"은 전부 LLM 비용 `budget_krw`·무관). Part 8 rev.2의 "소비처 대기" 상태 확정 — LLM에 subgraph를 주입하는 좌석이 아직 없어 예산이 박힐 곳이 없었다.
- **배선 지점**: S1의 LLM 도구 정책(G1)이 `query_curriculum`·`match_misconception` 도구로 컨텍스트를 모으는 좌석이 **첫 소비처**. 여기에 depth≤2·nodes≤12~20·tokens≤3000 상한 + visited set·timeout·token budget guard(CLAUDE.md 하드 게이트)를 코드로 박는다.
- **fail-closed** 판정(설계 §3): 초과 시 절단·"컨텍스트 제한" 정직 신호.
- **리스크 중간·상환 필요(S1-a/e)**: 지금 없는 건 정상(소비처 부재)이나, G1 빌드 시 반드시 동반. 주석 아닌 코드로.

## Q3 [붕괴] PRM/verify 우회 경로

[실측] **coach 경로는 verify를 게이트가 아니라 신호로 쓴다**. `l4/solution_coaching.py`는 OCR 저신뢰 시 step-incorrect 신호를 보류(`verification_ocr_gated`·`:227-247`)하나, **verify 통과 여부와 무관하게 코칭을 반환**한다. verify-before-finalize 강제는 하네스 `_exec_end_turn`("풀이 단계 제출 턴은 verify_step 호출 의무·미호출 end_turn 거부", `wh1_loop.py:20-21`)에만.
- **우회 경로**: stateless `/v1/coach`(`coach.py:995`)는 하네스 미경유 → verify 없이 발화 가능. unverifiable 상태에서 정답 흘림 방지가 **coach 경로엔 구조적 보장 없음**.
- **리스크 높음·상환 필요(S1-b)**: coach를 하네스 경유로 전환하면 verify 의무가 자동 강제. Top 3 #1.

## Q4 [붕괴] WH-1 루프 가드

[실측] **가드 존재·양호**. `run_tutoring_turn(max_tool_calls=16)`(`wh1_loop.py:469`)·루프 `while state.tool_calls < max_tool_calls and not state.ended`(`:491`)·초과 시 `budget_exhausted` 안전 종료(`:508`). `end_turn`만 학생 발화(`:17`)·중간 도구는 비발화. `max_tool_calls<1`이면 ValueError(`:483`).
- **리스크 낮음**: 루프 가드는 이미 견고. S1에서 LLM 정책이 도구를 무한 호출해도 16회 상한에서 안전 종료. timeout(벽시계)은 미확인 — [추정] 도구가 블로킹 LLM 호출 시 턴 timeout도 있으면 좋으나 tool_calls 상한으로 1차 방어됨.

## Q5 [분리] 오개념 preload 금지

[실측] **coach init에 오개념 preload 없음**(reactive retrieval 확인). coach.py·l4/misconception에 세션 시작 시 오개념을 초기 context로 preload하는 경로 grep 0(매치는 crosslink 적재 CLI·무관). 04c 7단계 분리·reactive 유지.
- **웜스타트(G5) 리스크**: 설계의 웜스타트("단원 고빈도 오개념 프리로드")가 이 금기를 깰 위험. **상환 규칙(S1-c)**: 웜스타트는 *진단 문항 선별 힌트*로만 쓰고 **코칭 context엔 preload 금지**·reactive 유지. contamination 방지.
- **리스크 중간·설계 제약으로 상환**: 현재 위반 0, S1-c 빌드 시 규칙 준수.

## Q6 [존재이유] OCR vs MathLive 필수성

[실측·중요 정정] **"MathLive 경로"는 오칭**. MathLive는 웹 그래핑 계산기의 수식 입력칸(시각화 렌더러)이지 풀이 제출기가 아니다(`GraphingCalculator.jsx:23-41`·`graphing_calculator_webview.dart`는 검증된 `Visualization.spec` 렌더). **실제 풀이입력 = 평문 `TextField`**(`chat_screen.dart:38`)→줄 분해→`CoachRequest(solution_steps)`(`chat_controller.dart:89-108`).
- **S1 필수 = 평문→solution_steps→coach→verify_solution 경로** (OCR 무관하게 완결). OCR은 mobile 브리지 끊김(G4)이라 시연 기여 불가·병행/선택.
- **MathLive만(=평문만) 넣을 때 잃는 것**: `ocr_confidence`가 None→dormant라 **OCR 특유 게이팅 브랜치 미시연** — ①`match_low_quality`(`match_gate.py:115`) ②손글씨 오인식 보호 `verification_ocr_gated`(verify가 낸 step-incorrect가 학생 오류인지 OCR 오독인지 모호할 때 거짓 지적 보류·`solution_coaching.py:227-247`) ③OCR 내부 인식 품질 검증(`l5/ocr/verify.py`). **단, verify_solution 단계별 정오 검증 자체는 손실 0**(동일 solution_steps면 검증 범위 동일). 잃는 건 "입력이 OCR일 때만 의미 있는" 신뢰도 게이팅 계층뿐.
- **라이브 키(Qwen3-VL) 의존 = OCR 크리티컬 패스 아님**: 기본 backend `rapid_latex`(`config.py:833`)·OCR 기본 비활성(`config.py:817`)·테스트 가짜 부품 주입. Qwen3-VL은 `backend=qwen_vl` 명시 시만·S1-f(Kiki) 후순위.
- **리스크 낮음·설계 정정 필요**: 설계 문서 §1④·§5의 "MathLive 경로" 명명을 "평문→solution_steps 경로(MathLive는 시각화 렌더러)"로 정정. → **본 감사와 함께 설계 문서 정정 커밋**.

## Q7 [경계] 미성년 PII

[실측] **트레이스·토큰 회계·shadow·라우팅은 잘 격리**:
- Langfuse: 결정 태그 12필드만·학생 원문/프롬프트 미포함·`student_id_hash`(해시)(`langfuse_sink.py:187-205`·`router.py:328-341`).
- 토큰 회계: 집계 수치만(`dialogue.py:98-101`)·캐시 키 SHA256(`router.py:272-276`).
- judge shadow: id·카운트만·`extra="forbid"`로 reason 필드 구조 차단(`shadow.py:180-241`).
- 라우팅: free 티어(기본 미성년 다수) **무조건 로컬**(`router.py:456-458`)·judge 항상 로컬(`judge_seam.py:43,59`) → 클라우드 전송 구조 차단.
- 최소 수집: birth_year만(월일 미수집·`config.py:329-343`).

[실측·상환 필요] **앱-계층 평문 저장 4종**:
- `DialogueTurn.content`(학생 원문·AI 코칭 원문·`dialogue.py:167`·`coach.py:1103,1113`)·`image_uri`·`image_analysis`(손글씨·`dialogue.py:187-188`)가 평문. CLAUDE.md 준수가 **DB at-rest 암호화에 전적 위임**(코드 미확인). `_crypto.py` AES-256-GCM은 device secret 전용·대화 본문 미배선.
- Redis 캐시 value(LLM 응답 평문·`redis_cache.py:145-164`) — 학생 발화 간접 인용 가능[추정].
- 유료 티어(premium/gifted) killer/prove·고난도 프롬프트는 Anthropic 처리 가능(`router.py:459-464`) — 미성년 유료 시 동의는 코드 범위 밖[추정].
- **리스크 높음·상환**: Top 3 #2. 권고 — `_crypto.py` 봉투 암호화를 `DialogueTurn.content`/`image_*`에 확장 **또는** DB at-rest 암호화 존재를 인프라 문서로 확인. S1 실사용자 전 필수.

## Q8 [붕괴] subject 하드코딩

[실측] **하드코딩 0·양호(S5 확장 대비)**. `subject == "math"` 류 grep 0. 매치는 전부 파라미터화: `Problem.subject == subject`(쿼리 필터 인자·`problems.py:115`)·`MisconceptionEmbedding.subject == self._subject`(네임스페이스 스코프 변수·`pgvector_index.py:187,223`). subject는 데이터/스코프 축이지 코드 분기 아님.
- **리스크 낮음**: S5 물리 확장 시 `physics.*` 병렬이 스키마 변경 0으로 수용 가능(S0-4b embedding namespace governance와 정합). S1 배선 시 이 상태 유지 — 도구 정책 프롬프트 템플릿의 과목 의존은 데이터에만.

---

## 심층: 이중 결정 경로 (설계 §6)

[실측] `api/coach.py` 주경로는 결정론적 `_build_response_payload`(Polya/hint/socratic/LTHC)이고 LLM 사실상 0(유일 시임 `LLMJudge` 오개념 게이트·기본 OFF). WH-1 하네스는 `TutorPolicy`(LLM 예정)로 도구 선택. **S1에서 LLM 정책을 신설하면 두 결정 주체(결정론 coach vs LLM 하네스)가 공존** → 이중 결정 경로 리스크.
- **상환(S1-b)**: coach 엔드포인트를 하네스 경유로 **단일 수렴**. 결정론 로직은 하네스 도구(polya·socratic)로 흡수·LLM 정책은 "다음 도구 선택"만. 두 경로가 같은 응답을 다르게 만들지 않게.

## 심층: 검증 게이트 unverifiable 처리

[실측] 하네스 `verify_step`은 3-state(correct/incorrect/**unverifiable**·`wh1_loop.py:32`). `_exec_end_turn`이 verify 미호출 시 거부하나, **unverifiable일 때 정답 흘림 방지**는 정책(TutorPolicy)이 unverifiable을 어떻게 처리하느냐에 달림.
- **상환(S1-a)**: LLM 도구 정책이 unverifiable에서 "정답 제시" 도구를 못 고르게 제약(CLAUDE.md "막혔을 때 바로 정답 금지"·Polya 우선). 하네스 불변식으로 동결 권고.

---

## 공통 메타 질문 — 7관점 인지행동 분석

**"이 S1 루프가 실서비스에서 실패하는 이유를 7대 붕괴 연쇄 관점에서, 인지행동 기준으로 분석"**:
- **AI 추론 실패**: Minimal Subgraph 예산 미배선(Q2) 상태로 LLM 정책을 붙이면 전체 그래프/과다 컨텍스트 주입 유혹 → "더 넣을수록 멍청" 발현. **가장 큰 인지행동 리스크**. → S1-a/e에서 예산 코드 강제가 방어.
- **교육 일관성 붕괴**: 검증 게이트 미강제(Q3)·이중 결정 경로로, 학생이 *틀린 풀이에 코칭*을 받거나 *정답을 조기 노출*받으면 "이유를 묻는 수학" 정체성 붕괴. → 하네스 단일 경로·verify 의무가 방어.
- **유지보수 지옥**: 결정론 coach와 LLM 하네스 이중 경로가 방치되면 두 곳을 이중 수정. → S1-b 수렴.
- 노드/관계 폭발·순환참조·성능: S1은 배선 위주라 신규 노드/엣지 0 → 이 4개는 낮음(S0에서 원자 백본·legacy_snapshot으로 이미 방어).
- **인지행동 기준 결론**: S1의 실패는 *구조(노드/관계)*가 아니라 *교수학적 행동의 게이트 부재*(검증·정답 억제·컨텍스트 절제)에서 온다. 상환 Top 3가 정확히 이 축.

---

**참조**: `docs/architecture/s1_e2e_vertical_slice_design.md`(설계) · `docs/architecture/04a_wh1_tutoring_harness.md`(WH-1 정본·불변식) · `docs/standards/part8_context_architecture_review.md` rev.2 · `docs/strategy/status_roadmap_2026-07.md` §5 · CLAUDE.md(금기·하드 게이트)
