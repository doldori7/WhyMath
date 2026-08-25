# 28_MathLive 입력 — EOS 43절 설계안 델타 검토 (2026-08-26)

> **범위**: Kiki 제공 EOS 지향 설계안 『28_MathLive 입력』(43절)을 현 코드베이스와 대조한 기록.
> **전제 정본**: `math_engine_gap_review.md`(2026-08-03 · 2026-08-11 재검증) — 같은 근원 틀(외부 EOS
> 『07. 수식(Math Engine)』)의 기능 28을 **10항 요약본으로 이미 전수 대조해 "갭 0" 판정**을 낸 문서.
> 이번 43절 문서는 그 기능 28의 **확장본**이므로, 이 문서는 재대조가 아니라 **델타만 판정**한다.
> **형식**: `32_learning_history.md`·`48_eos_security_access_control.md`의 "판정 → 현행 매핑 → 갭 등재"
> 3부 구조 계승.
> **결론**: 43절 중 **37절은 기판정 재확인**(✅ 충족 · 🚫 의도적 미채택 · ⏸ 유보/승계). 진짜 갭은
> **1건** — 답 형태 계약(동치 ≠ 지시 준수 채점 변별, → `EOS-28`). 문서가 요구하는 원본 보존·단계
> 이벤트·버전 고정 3축은 **기등재 태스크 `EOS-32`·`EOS-46`·`EOS-47`이 이미 소유**(승계). 신규 공백
> 7종은 발화 조걧만 기록.

---

## §0. 착수 전 확인 — 세 번째 대조임을 먼저 확정

`math_engine_gap_review.md` §7.6(계열 C — 미병합 고립 4회차)이 *"같은 대조를 두 번 하게 만드는 것"*
을 반복 실수로 등재하고, 방어로 "착수 전 기존 리뷰 조회"를 착수 절차에 박았다. 이번 세션은 그 방어가
**두 번째로 작동한 사례**다 — 43절 확장본이 §1의 10항 요약본과 같은 틀임을 확인하고 전수 재대조를
걸렀다. 이 절차가 없었으면 D1~D5·MATH-01~05를 또 다시 설계할 뻔했다.

## §1. 43절 → 기판정 매핑 (재판정 없음 · 근거는 전부 선행 문서)

| 문서 절 | 내용 | 기판정 | 근거 |
|---|---|---|---|
| §1~3 · §7~9 · §42 | 어댑터 분리 · Raw→Parsed→Canonical→Semantic 계층 · **자체 Canonical Math AST** | 🚫 의도적 미채택 | `math_engine_gap_review.md` §2-②③ — 자체 CAS·AST 5계층은 `math_dsl_evolution.md:97,298`·`math_dsl_part4_ast_review.md:20,32`의 **명시 anti-goal**. 재론은 갭이 아니라 결정 번복 사안 |
| §4 입력 방식 | 키보드·터치·LaTeX ✅ / 필기 ⏸ / **음성** | ✅ / ⏸ / 공백 G-5 | 기능 28 표(10항). 필기는 `NLP-01` 소유. 음성은 이번 문서 신규 → §4 G-5 |
| §5 입력 데이터 모델 | input_id·learner·context 동봉 저장 | ⏸ 승계 | `EOS-32-answer-submission-entity`(attempt FK·sequence·grading_result·privacy 3종 배선이 acceptance에 이미 포함) |
| §6 원본 보존(raw/normalized/canonical 병기) | | ⏸ 승계 | **`EOS-32` acceptance가 `raw_response/latex` + `canonical_ast(JSONB)` 병기를 이미 수용.** 현행 실측: 백엔드 도달 값은 평문뿐(`chat_controller.dart:96-110` — 원문 LaTeX은 어느 경로도 요청에 안 실림, `ProblemAttempt.student_answer` TEXT 1필드 `db/models/activity.py:176`) → EOS-32 착수 시 모바일 페이로드 확장이 전제 |
| §10 검증 4종 | 문법·구조·도메인·수학 | 기판정 | 기능 30 표 — ①문법 D3(`MATH-03`) · ②의미 △(`AppliedUndef` 1건) · ③교육과정 D4(`MATH-04`, **생성물 전용**) · ④CAS ✅ 초과 |
| §11~12 형태 준수 · Answer Contract | | ⚠️ **진짜 갭 → §2 D-1** | 실측 §5-ⓐ |
| §13 입력 상태 모델(INCOMPLETE 등) | | 공백 G-1 | 실측: `_canSubmit => _latex.trim().isNotEmpty` 1개뿐(`mathlive_input_screen.dart:41-43`) |
| §14 · §36 · §37 | 실시간/제출 분리 · deterministic-first · LLM은 설명 담당 | ✅ 일치 | §2-⑩(입력 중 실시간 서버 검증 미채택) · SymPy 단일 권위 불변식. 문서가 정본과 **같은 결론**을 제안 |
| §15~16 입력 이벤트 · 행동 정보 | math_input.* 이벤트 | ⏸ 승계 + 공백 G-2 | step 수준은 **`EOS-46-solution-step-event` 소유**(attempt FK·sequence·expression·validation). 위젯 세션 수준(started/corrected)은 생산자 0 — `InteractionLogger`는 실재하나 사용처가 그래핑 계산기뿐(`interaction_logger.dart:31-43` vs `graphing_calculator_webview.dart:120`) |
| §17 오개념 AST signature | pattern→observed→misconception_id | ✅ **초과** | `l4/misconception/wrong_form_match.py`가 이미 **문서 제안보다 강한** 구현 — SymPy Wild 정합으로 변수명 무관 인스턴스화 탐지 + 거짓 등식 가드(RS2 낙인 차단) + `identity_status` 단일 권위 재사용. 단 문서의 "observed AST 저장"은 현행 프라이버시 규칙(레코드에 학생 풀이 원문을 담지 않음, `wrong_form_match.py:17`)과 충돌 — **현행이 정답** |
| §18 단계별 풀이 연결 | | ✅ done | `MOB-07`(`\displaylines` 단계 분배) · `NLP-03`(분해 계약) |
| §19 Transformation Validation | subtract_both_sides 등 변환 판정 | ✅ 초과 / ⏸ | 변환 **유효성**은 `verify_step` 3상태+분기로 초과 충족(기능 30 표). 변환 **이름 라벨링**은 D5(`ReasoningStep`) — 발화 조건 `math_engine_gap_review.md` §5-④ |
| §20 자연어+수식 혼합 블록 | Rich Educational Input | 공백 G-3 | 현 채팅은 텍스트+별도 수식 필드 |
| §21~23 키보드 프로필 · 입력 제한 | 학년/문제별 키보드 | 공백 G-4 + 🚫 부분 | 실측: `mf.mathVirtualKeyboardPolicy="manual"` 고정 1줄(`index.html:108`), 문제/학년 컨텍스트는 WebView에 미전달(`router.dart:199-205`). 문서의 `allowed_symbols`(의미적 금지)는 **§2-⑤ 계열 교수학 금기**(학생 입력 거부) — `visible`(표시 편의) 축만 채택 가능 |
| §24 undo/redo · 입력 이력 | | ✅ / 공백 | undo/redo는 MathLive 기본(명시 설정 0 — `index.html` grep 0건). 이력 분석은 G-2와 같은 축 |
| §25 paste 정규화 | | 공백(관측 없음) | 발화 조건 §4 |
| §26 보안(길이·깊이 상한) | | ✅ 기판정 | `math_engine_gap_review.md` §7.4 — `_MAX_EXPR_LEN=4000` + 인증 필수 이중 방어 확인, **태스크 신설 없음** 판정 유지. AST depth 상한은 자체 AST가 없으므로 해당 없음 |
| §27 접근성 | | 기록됨 | §4-① 정직한 공백(입력 위젯 a11y 미측정) |
| §28 국제화 | locale·소수점 구분자 | 공백 G-6 | KR K12 단일 시장 — Phase 5 발화 |
| §29~30 parse/normalize API | 클라 lightweight parse | 🚫 / ✅ | 클라이언트 수학 판정 0(`ARCH-10`) + §2-⑩. 정규화 권위는 `MATH-01`이 l3로 이관 완료. parse-only 엔드포인트는 미채택 확인 |
| §31~33 MathInput 추상화 · Resource Registry | | ✅ / 해당 없음 | `mathlive_input_screen`+webview가 이미 어댑터 계층(MOB-03/06/07). Registry는 렌더러 축(`VIZ-04` `render_contract.json`) — 입력 위젯은 그 관심사가 아님 |
| §34~35 버전 관리 · 감사 재현성 | parser_version 등 | ⏸ 승계 + 요구 1건 | **`EOS-47-attempt-version-pinning` 소유**(evaluation_context 스냅숏). 단 이 문서가 요구를 하나 추가 — evaluation_context에 **`notation_contract` 버전·정규화 파서 버전**을 포함해야 문서 §35의 "채점 이의 재현"이 닫힘. EOS-47 착수 시 반영할 것(§3) |
| §38~39 EOS 모듈 연결표 | | 매핑 확정 | WhyMath 계층으로: MathLive 어댑터 = **L5**(mobile/web) · 정규화·검증 = **L3**(SymPy 권위 계층) · 오개념 매칭 = **L4** · 행동 데이터 = **L2**. EOS 모듈 번호(23·204·206…)는 저장소 체계에 없음 — 위 계층 매핑이 정본 |
| §40 MVP 범위 | P0 10종 | ✅ 전부 기완료 | 기능 28 표 참조. P1은 이 문서 §2 D-1 + §4 공백 표로 대체 |
| §41 피해야 할 설계 5종 | | 4종 기존 불변식 일치 · 1종 갭 | ①LaTeX=canonical 금지 → canonical은 평문 계약+SymPy(`notation_contract.json`) · ②MathLive 종속 금지 → 어댑터 구조 · ③입력 즉시 LLM 채점 금지 → §2-⑩ · ⑤키스트로크 영구 저장 금지 → 미성년자 규칙 · **④ equivalent=correct 동일시 금지 → 이것만 실재 갭(§2)** |

### §1-보론. 문서 자체 결함 2건 (채택 판정과 무관하게 기록)

1. **자기모순**: §30의 parse 응답 예시가 `\frac{2x}{4}` → `canonical_ast: Divide(x,2)`로 **parse 단계에서
   약분을 수행** — §2.1(raw→parsed→canonical 분리)·§6(canonical≠expanded)을 문서가 스스로 위반.
   WhyMath 정본(파싱과 canonical 분리 · `symbolic_equivalence.py:257` docstring "canonical 정규화는
   이 함수 밖")이 이미 옳게 서 있으므로 영향 없음.
2. **"observed AST" 보존 제안**(§17)은 미성년자 프라이버시 현행(추상 id·개수만 기록)과 충돌 —
   `wrong_form_match.py:17`의 결정이 우선.

---

## §2. D-1 — 답 형태 계약(Answer Contract): 동치인데 지시를 어긴 답을 구분할 수 없다 (`EOS-28`)

**문제 (전건 실측 · §5-ⓐ).** 채점기 셋이 전부 **값·동치만** 본다:

- `l3/verify_answer.py:272-347` — 수치 잔차 검산(`|residual|<tol`)뿐. `AnswerVerdict`는
  `state/reason/samples_checked` 3필드(`:113-136`).
- `l3/verify_final_answer.py:246-284` — 값 해집합 비교 → 식 동치 폴짝. 형태 판정 없음.
- 형태 검사 코드 **0건** — `기약|인수분해.*요구|factored_form|simplest_form`을 `whymath_backend/`에
  grep하면 매칭은 전부 **코퍼스 생성기**(정답을 기약으로 *만드는* 쪽)뿐이다.

스키마에는 `answer_format`(enum 4종 — 자연수/분수/실수/식, `schema/enums.py:175-181`)이 있으나
**채점기가 읽지 않는 메타 라벨**이고, `answer_constraint`·`answer_transform`은 자유형 JSONB
(`schema/problem.py:706-713`)라 어떤 검증기도 소비하지 않는다.

**왜 갭인가.** 문서 §41④와 WhyMath 불변식이 같은 문장으로 합의한다 — *"수학적 동치와 문제 지시
준수는 다르다"*. 인수분해 지시에 전개형으로 답하면 현 채점기는 **correct를 돌려준다**(동치니까).
검증 권위 서열 ①(기계 판정)이 스스로 선언한 변별력을 못 내는 구멍이며, `math_engine_gap_review.md`
D3(묵별 실패)의 채점 축 사촌이다.

**경계 — 교수학 금기와의 선 긋기 (가장 먼저 못 박는다).** `math_engine_gap_review.md` §2-⑤는
*학생 입력 거부*를 영구 미채택했다. D-1은 거부가 아니라 **채점 변별 + 피드백**이다:

- 형태 불만족이 **제출 차단**이 되면 안 된다 — `incorrect`도 아니고 별도 verdict 축
  (`mathematically_equivalent: true` + `instruction_satisfied: false`).
- 표현은 "다시 입력하세요"가 아니라 지시 확인 유도(부정 강화 금기 준수). `scoring_type` enum에
  부분점수·루브릭이 이미 있다(`schema/enums.py:220-235`).
- 이 경계를 **테스트로 기계화**한다(선언만 두면 다음 세션이 제출 차단으로 배선한다 — D4가
  `curriculum_notation_gate`에 쓴 소스 스캔 거버넌스 패턴 준용).

**설계 제약.** deterministic-first(LLM 0 · SymPy 기반 — 예: factored 여부는 `factor()` 동치 +
구조 단언). `expected_form`은 폐쇄 어휘. 기존 `answer_format`/`answer_constraint`와의 관계는
신설 vs 확장을 ADR 1편으로 결정(자유형 JSONB의 검증기 미소비 상태를 그대로 두지 않는다).

**측정 없는 도입 없음 — 첫 스텝은 코퍼스 실측.** 형태 요구 문항(인수분해·기약분수 지시)이 현
코퍼스에 실재하는지 이 슬라이스에서는 재지 않았다. 태스크 acceptance 첫 항목을 이 실측으로 두고,
**0건이면 유보로 전환**한다(갭을 크게 부르지 않는다는 §7.3 선례와 같은 규율).

**태스크**: `EOS-28-answer-form-contract` (track math-completion · stage S3 · priority 2 ·
layer backend) — 등재 CLI 경유, ID 손편집 0.

---

## §3. 승계 표 — 문서가 요구했으나 기등재 태스크가 소유하는 축

| 문서 절 | 소유 태스크 | 이 문서의 행동 |
|---|---|---|
| §5~6 원본 보존 · 입력 데이터 모델 | `EOS-32-answer-submission-entity` (todo) | 승계. 착수 시 전제 1건 추가 — 현재 백엔드에 원문 LaTeX이 도달하지 않으므로(`chat_controller.dart:96-110`) 모바일 페이로드 확장이 선행 |
| §15~18 step 수준 입력 이벤트 | `EOS-46-solution-step-event` (todo) | 승계 |
| §34~35 버전 고정 · 채점 재현성 | `EOS-47-attempt-version-pinning` (todo · EOS-44 선행) | 승계 + 요구 추가 — evaluation_context에 `notation_contract` 버전·정규화 파서 버전 포함 |
| §10-① 검증 사유 변별 | `MATH-03-verify-reason-code-discrimination` | 승계 — D-1의 학생 대면 표현도 `reason_code` 패턴 준용 |
| §10-③ · §21 visible 축의 생성물 판 | `MATH-04-curriculum-notation-range-gate` | 승계(생성물 전용 불변) |
| §4 필기 | `NLP-01` | 승계 |
| §19 변환 이름 라벨 | D5(`ReasoningStep`) — 발화 조건 §5-④ | 유지 |

---

## §4. 신규 공백 7종 — 지금 만들지 않는 것 (발화 조걧만)

| # | 공백 | 실측 근거 | 발화 조건 |
|---|---|---|---|
| G-1 | 입력 상태 모델(INCOMPLETE 구분) | `mathlive_input_screen.dart:41-43` 비어있음 판정 1개뿐. MathLive 자체가 미완성 플레이스홀더를 표시 | `MATH-03`의 `parse_error` 실측 분포에서 "미완성 제출" 비중이 확인될 때 |
| G-2 | 수식 입력 위젯 세션 이벤트(started/corrected) | 생산자 0 — `InteractionLogger` 사용처는 그래핑 계산기뿐 | L2 행동 분석이 입력 *과정* 데이터를 소비하는 설계가 착수될 때. keystroke 수준은 영구 미채택(§41⑤·미성년자 규칙) |
| G-3 | 자연어+수식 혼합 블록 입력 | 현 채팅 = 텍스트 + 별도 수식 필드 | AI Tutor 질문 경로가 블록 구조를 요구할 때 |
| G-4 | 키보드 visible 프로필(학년·문제유형별 표시 구성) | `index.html:108` manual 고정 · 컨텍스트 미전달(`router.dart:199-205`) | 문제 유형별 입력 오류율 관측(G-1과 같은 데이터) — `allowed`(의미적 금지)는 영구 미채택(§2-⑤ 계열) |
| G-5 | 음성 수식 입력 | 0건 | 별도 착수 결정 시. `l3/speech`는 출력 축이라 재사용 불가 |
| G-6 | 국제화(소수점 구분자 등) | 0건 | Phase 5 글로벌 착수 시 |
| G-7 | paste 정규화(외부 LaTeX/유니코드 붙여넣기) | 설정 0건 — 붙여넣기 유입 자체가 미관측 | 유입 관측 시. 정규화 권위는 `MATH-01` 산출물을 소비 |

---

## §5. 부록 — 실측 근거 (2026-08-26 · 2개 탐색 에이전트 병렬 실측)

- **ⓐ 채점 형태 변별 부재**: `l3/verify_answer.py:113-136,272-347` · `l3/verify_final_answer.py:246-284`
  · `schema/enums.py:175-181,220-235` · `schema/problem.py:706-713` · grep 패턴
  `기약|인수분해.*요구|factored_form|simplest_form`(매칭 전부 생성기) · `answer_contract` 0건.
- **ⓑ 원본 미보존**: `db/models/activity.py:176`(student_answer TEXT 단일) · `api/me.py:664,744-754`
  · `api/coach.py:945-963` · 백엔드 grep `mathlive|raw_latex|original_latex` 0건.
- **ⓒ 이벤트 기반**: `db/models/activity.py:238-283`(attempt_event) · `schema/enums.py:1113-1133`
  (EventType 11종) · `schema/event_data_contract.py:237-244` · `api/interactions.py:59-80`.
- **ⓓ 버전 메타 부재**: `AnswerVerdict`·`VerifyStepResult`·`FinalAnswerResult`·`VerifiedSolution`
  (`db/models/verified_solution.py:82-106`) 전부 version 필드 0. `data/notation_contract.json:2`
  version은 결과에 미탑재.
- **ⓔ 모바일 입력층**: `index.html:51-55,108-129` · `mathlive_input_screen.dart:23-29,41-43,99-102,
  121-124` · `mathlive_input_webview.dart:3-5,68-73` · `chat_screen.dart:204-212,935-1012` ·
  `chat_controller.dart:96-122` · `interaction_logger.dart:31-43` · `router.dart:199-205`.
- **ⓕ 오개념 정합**: `l4/misconception/wrong_form_match.py:1-60`(SymPy Wild 정합·거짓 등식 가드·
  프라이버시 스코프 docstring).

**정직한 공백 — 이 슬라이스에서 재지 않은 것**: ①코퍼스 내 형태 요구 문항 비율(D-1의 첫 acceptance로
이관) ②MathLive 기본 키보드에 노출되는 기호 집합(G-4 발화 판단의 전제) ③`EOS-32` acceptance의
`canonical_ast(JSONB)` 좌석과 §2-③(AST 의도적 미구축)의 정합 — EOS-32 착수 시 대조 필요를 여기
기록한다.
