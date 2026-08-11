# 자연어 처리(NLP) 모듈 — 외부 EOS 틀 대조 **2차 재점검(r2)** (2026-08-04)

> 🔄 **회수·재검증됨 (2026-08-11) — §8을 함께 읽을 것.**
> 이 문서는 2026-08-04에 작성돼 **PR #697(open)에 7일간 머물렀고 main에 착륙하지 못했다.**
> 2026-08-11 세션이 같은 외부 틀을 다시 받아 착수했다가 이 문서를 발견하고, **새로 쓰지 않고
> 회수**했다(`math_engine_gap_review.md` §7 선례 — 재작성은 경쟁 문서 2개를 만든다).
> **본문 §0~§7은 한 글자도 고치지 않았다** — *무엇이 언제 참이었는지*가 이 문서의 기록 가치이며,
> 특히 §2-①(미머지 판정)은 "그때는 미머지였다"는 사실 자체가 근거다.
> 7일간의 변화는 **§8 재검증 절**에만 적고, 본문의 해당 지점에는 인라인 `[→ §8-Δn]` 표시만 단다.
> **요약**: 판정 뒤집기 1건(Δ2 — D2 잔여 ②가 "좁다"가 아니라 **구조적 0**), 상환 3건,
> 신규 갭 3건(Δ3~Δ5), D5는 **악화**(11개 → 12개 중 러너 1개).

> **범위**: v1(`nlp_module_gap_review.md`, 2026-07-31)과 **동일한 외부 참고 문서**
> (『16. 자연어 처리』 기능 66 질문 이해 · 67 풀이 과정 분석 · 68 학생 답안 분석 ·
> 69 OCR 수식 인식 / 세부 40개 — **WhyMath 전용이 아닌 일반적 틀**, Kiki 제공·재제출)를
> **v1 이후 4일간의 코드베이스 변화**와 다시 대조한 기록.
> **성격**: 처음부터의 재대조가 아니라 **델타 재점검**이다. v1의 판정 대부분은 유효하므로
> 승계하고, ⑴ **stale해진·오판이었던 판정 칸**과 ⑵ **v1의 설계(D2)가 구현된 뒤 드러난 실공백**만
> 다룬다.
>
> **v1 이후 상태**: `NLP-02`(D2·서버측 채점 shadow) **done·main 병합**(2026-08-03 · `9905fdc4`) /
> `NLP-01`(D1)·`NLP-03`(D3) **done·미머지**(브랜치 `claude/openrouter-setup-guide-e98dw4`,
> 2026-08-03 — §2-①). 즉 **v1이 설계한 D1~D3은 셋 다 구현됐고, 둘은 아직 trunk에 없다.**
>
> **결론 3줄**:
> 1. **최대 갭 = 관측 리포트를 만들고 실행하지 않는다.** 리포트 CLI **11개 중 10개가 러너 0건**
>    (CI·compose·스크립트·infra 전수 대조 — 미머지 브랜치 포함해 재확인). `NLP-02`가 낳은
>    `attempt_grading_shadow_report`도 포함이며 **실데이터 수치가 한 번도 산출된 적 없다**.
>    v1 §6이 정리한 "완비된 소비 경로 + 미도달 공급원" 계열이 **관측 계층 자신에서 재발**했다
>    → **D5**(유일한 신규 태스크).
> 2. **v1 판정 2건이 실측으로 반증된다** — §4-3 "`classify` 호출자 0"은 v1보다 **이틀 먼저**
>    머지된 `harness/wh1_llm_policy.py:337-346`이 반증하고, §4-1 "전략 토큰 19종"은 실측 20종이다.
>    v1 §정정이 고친 stale의 **자매 위치 1곳**(`config.py` `ocr_recognizer_backend` 설명)도 아직
>    남아 있다 → §1.
> 3. **이 재점검 자체가 하마터면 8번째 중복 설계가 될 뻔했다.** 작업 트리(= trunk)만 보면
>    `NLP-01`·`NLP-03`은 `status: todo`이고 OCR 코드는 v1 이후 **변경 0건**이라, 재설계를 정당화하는
>    모든 신호가 갖춰져 있었다. 실제로는 **하네스의 원격 claim 대장이 "이미 완료(미머지)"로
>    막아 준 것**이다. 이건 우연이 아니라 구조적 리스크다 → **§2-①·§6-b**.

관련 정본: `nlp_module_gap_review.md`(v1 — 이 문서의 모체·판정 근거 원본) ·
`operations_module_gap_review_r2.md`(같은 시리즈 r2 형식 선례) ·
`service_operations_gap_review.md`(§유보⑤ `/v1/speech` 도달 — 중복 등재 배제 근거) ·
`ai_tutor_module_gap_review.md`(`PED-04` 승계) · `MEMORY.md` 결정 로그(2026-07-31 v1 ·
2026-08-03 NLP-02 · 2026-08-04 본 문서).

---

## §0. 재점검 사유 — 왜 v1을 덮어쓰지 않고 r2를 새로 쓰는가

**v1을 in-place 수정하지 않는 이유**: v1은 `NLP-01`·`NLP-02`·`NLP-03` 세 태스크 YAML의 `notes`가
가리키는 **판정 근거 원본**이다. 이미 done 처리된 `NLP-02`의 근거를 소급 변조하면 "왜 그렇게
결정했는가"의 기록이 사라진다. `operations_module_gap_review_r2.md` §0과 동일한 처리를 따르고,
v1에는 이 문서로 오는 **배너 1줄**만 추가했다.

**재점검이 필요했던 실제 사유 3종** (전부 이 세션 실측):

1. **v1의 설계가 하나 착륙했는데(`NLP-02`), 그 산출물이 한 번도 실행되지 않았다.** 설계 문서는
   "관측을 붙였다"로 닫혔고 태스크는 done이지만, 실데이터 수치는 0회 산출이다. 착륙 *이후*를
   보지 않으면 이 상태가 영원히 "측정했다"로 읽힌다.
2. **v1이 근거로 든 코드 좌표가 4일 만에 밀렸고, 판정 2건은 작성 시점부터 틀렸다.** 갭 리뷰가
   다음 세션의 탐색을 줄이는 문서인 이상, 틀린 좌표는 그 자체가 비용이다.
3. **나머지 둘(`NLP-01`·`NLP-03`)은 이미 구현됐는데 trunk에서는 보이지 않는다.** 재점검을
   하지 않았다면 "미착수"로 단정했을 상태다(§2-①).

**용어**: 첨부 문서의 "EOS"는 외부 참고 프레임워크의 명칭이며 이 저장소가 스스로를 EOS로
선언하는 것과 무관하다(v1 §0 처리 승계). 새 계층도 만들지 않는다 — NLP는 v1 §0-①-b가 밝힌 대로
**독립 계층이 아니라 L4/L5로 분산 대체된 자리**다.

---

## §1. v1 판정 정정 (오판 2 · stale 4)

### ①-a 반증 — "`NLP_TASK_TYPES`의 `classify`는 호출자가 0이다"(v1 §4-3·부록)

v1은 이 상수를 "좌석은 있으나 쓰는 코드가 없다"로 적고 "**기록 없는 미사용 상수가 다음 세션에
'이미 되는 것'으로 오독되는 것이 이 프로젝트의 반복 실수**"라고까지 덧붙였다. 실측은 반대다.

| 항목 | 실측 |
|---|---|
| 실호출자 | `harness/wh1_llm_policy.py:337-346` `LLMTutorPolicy._routing_request()` — `RoutingRequest(task_type="classify", ...)` |
| 도달 경로 | `wh1_llm_policy` → `harness/wh1_primary.py:47` / `wh1_shadow.py:35` → `api/coach.py:68` import → `wh1_primary_enabled` 플래그 아래 **학생 대면** 호출 |
| 머지 시점 | `b2c94b14`(2026-07-29) — **v1(07-31)보다 이틀 앞선다** |

즉 v1은 "미사용 상수를 dead로 오독하는 실수"를 경계하다가, **반대 방향으로 같은 종류의 오독**을
저질렀다(실사용을 미사용으로). 정정: `classify`는 살아 있다. 여전히 실호출 0인 것은
`match`·`translate` 2종이며(`router.py:592-601`의 `call_site` 축으로만 분기), `extract`는
`l4/misconception/judge_seam.py:54`가 쓴다.

**교훈(계열 등재)**: v1의 "호출자 0" 판정은 `task_type=` 문자열 grep으로 얻었을 가능성이 높은데,
이 저장소는 라우팅 신호를 **`RoutingRequest` 생성자 인자**로 넘기므로 상수명 grep이 호출을
놓친다. dead 판정은 **상수명이 아니라 생성자·호출 지점**으로 확인한다.

### ①-b 정정 — 전략 토큰 개수

v1 §4-1 "전략 19종·정답 6종" → 실측 **`_STRATEGY_TOKENS` 20종**(`l4/polya/transitions.py:26-51`)·
`_ANSWER_TOKENS` 6종(`:56-65`). 정답 토큰은 일치.

### ② 신규 stale — v1 §정정이 고치다 만 자매 위치

v1 §정정이 지목한 3곳은 **전부 반영 완료**다:

| 위치 | 현재 |
|---|---|
| `CLAUDE.md:76` | "`qwen3-vl:8b`(VISION·**인식기 실배선**·라이브 정확도 미검증)" — 구현/정확도 구분까지 반영 |
| `l5/ocr/recognize.py:206-223` | "**비동기 경로 실배선**" + 정정 사실 자체를 docstring에 기록(:215-217) |
| `05_interaction.md:126` | "**PaddleOCR + Qwen3-VL** — … 2026-05-28 결정으로 Mathpix 대체" (Mathpix 잔재 0) |

**그런데 같은 사실을 기술하는 네 번째 자리가 남았다**:

| 위치 | 현재 기술 | 실측 |
|---|---|---|
| `config.py:1064-1069` (`ocr_recognizer_backend` description) | "`texteller`(Phase B **스텁**)…**미배선**. `qwen_vl`(Phase C **스텁**)…**미배선**" | `l5/ocr/factory.py:125-143`이 둘 다 **실배선** — `qwen_vl`은 provider/cache/trace 미주입 시 RuntimeError로 거부하고, `TexTellerRecognizer`(`recognize.py:143-203`)는 실제 `model.generate` 수행 |

**"실제보다 못하다고 말하는 stale" 4번째 사례**다. v1이 지적한 성질(조용하다·아무도 항의하지
않는다·다음 세션이 중복 구현한다)이 그대로 적용되며, 특히 이 문자열은 **운영자가 백엔드를
고를 때 읽는 곳**이라 "스텁"이라 적혀 있으면 선택지에서 배제된다. 이번에 정정한다.

### ③ 줄 드리프트 (내용 불변 · 좌표만)

| v1 인용 | 실측 |
|---|---|
| `config.py:1005`(`ocr_enabled`) | **`config.py:1046-1054`** |
| `ocr_controller.dart:70-74` | **`:70-76`** |
| `05_interaction.md:125` | **`:126`** |
| `api/me.py:585`·`:593`(v1 한계 자인·`student_answer` 슬롯) | **`:597`·`:604-605`** |

**이 문서의 대응**: 인용은 줄번호 **+ 심볼명**을 병기한다(예: `config.py:1046 ocr_enabled`).
줄은 밀려도 심볼은 남으므로 다음 세션의 재탐색 비용이 0에 수렴한다.

---

## §2. v1 D1~D4 상태 실측

### ① 먼저 — "미착수"가 아니라 "미머지"다 (이 재점검의 최대 정정)

**trunk(`de446ec3`) 기준 관측**: `NLP-01`·`NLP-03` YAML은 `status: todo`이고, OCR 경로 코드는
v1 이후 **변경 0건**이며(`git log --since=2026-07-31` 대상 파일 = `recognize.py` docstring 정정
1건뿐, 그마저 v1 자신의 커밋 `f277c403`), 분해 축도 변경 0건이다. 여기까지만 보면 "설계는
있는데 아무도 손대지 않았다"가 정확한 서술이다.

**실제**: 병렬 세션이 **2026-08-03에 둘 다 구현**했고 브랜치가 머지되지 않았을 뿐이다.

| 태스크 | 구현 커밋 | 실제 착륙물 |
|---|---|---|
| `NLP-01` | `bbfc8c41` (브랜치 `claude/openrouter-setup-guide-e98dw4`) | `api/_ocr_state.py`(+204) — `set_ocr_components`가 `unavailable_reason`(`"disabled"`\|`"load_failed"`)을 **요구하도록 계약 강제** · 503 detail을 `{"code","message"}` dict로 분리 · 적재 실패 로그에 **예외 타입명 직접 삽입** · `OcrReachCounters` 신설 → **`/health/ready`의 `ocr` 섹션** · 모바일 503 전용 문구 분기 · `tests/backend/api/test_ocr_reachability.py`(+416, 세 상태 변별력 동결) |
| `NLP-03` | `8a3f176b` (동 브랜치) | `data/segmentation_contract.json`(10케이스 — CRLF·`\displaylines` 2026-07-20 회귀·언더스플릿 ambiguous 포함) · 백엔드 정본 `l5/ocr/text_segmentation.py segment_solution_text` · `api/_segmentation_state.py`(0-전이 관측) · **`src/mobile/test/segmentation_contract_test.dart`** · `tests/backend/l5/ocr/test_text_segmentation.py` |

**두 가지가 동시에 확인된다.**

- **이 문서의 §3 D7이 지목하려던 좌표에 병렬 세션이 독립적으로 수렴했다.** `NLP-01`은 새
  리포트를 만드는 대신 **이미 존재하는 `api/_ocr_state.py`에 카운터를 두고 `/health/ready`에
  노출**했다 — `PED-06`(`api/_growth_evidence_state.py` → `/health/ready`)이 확립한 형태 그대로다.
  "미활성(측정 대상 아님)"과 "활성인데 트래픽 0"을 `enabled` 플래그로 가른 것도 None-vs-0 원칙
  준수다. **설계가 옳았다는 독립 검증**으로 읽는다.
- **`NLP-03`의 미확인 리스크는 실측으로 해소됐다.** v1 acceptance ②가 전제한 "모바일 테스트가
  계약 JSON을 읽는다"는 이 저장소에 전례가 없었는데(§3 D7-b), 실제 구현은
  `File('../../data/segmentation_contract.json')` + **조용한 skip 대신 명시적 fail**로 해결했다
  (`flutter test`의 cwd = `src/mobile`). 다만 그 골든은 Dart의 *기존 동작*을 동결하는 회귀
  테스트이고 `ambiguous` 신호는 백엔드 전용이므로, v1 ②가 요구한 **"클라의 계약 소비로 전환
  (이관)"까지 간 것은 아니다** — 머지 시 확인할 잔여 항목이다.

**이 문서가 하지 않는 것**: `NLP-01`·`NLP-03`의 acceptance를 지금 고치지 않는다. 이미 구현된
태스크의 판정 기준을 뒤늦게 손대는 것은 **완료 근거의 소급 변조**이고, 머지 시 YAML 충돌을
만든다. 아래 D1·D3 절은 **trunk 기준 상태 기록**이며, 미머지 구현분에 대한 확인 항목은 §7에
둔다.

### D1 (OCR 학생 도달 0회) — **trunk 기준 전면 유효 · 구현분은 미머지** [→ §8-Δ1]

trunk에서 v1의 7개 주장 전건 재확인(아래). 미머지 브랜치가 ②③④를 해소했으므로, **머지되면
trunk 상태도 함께 해소된다** — 머지 전까지는 학생 도달 경로가 v1 기술 그대로다:

| 주장 | 실측 |
|---|---|
| 기본 비활성 | `config.py:1046 ocr_enabled = False` · 유일 소비 `app.py:461`(참이면 `build_ocr_components`, 거짓이면 `set_ocr_components(_app, None)` `:478`) |
| 컨테이너 구조적 불가 | `Dockerfile:43-46` `[ocr]` extra 미설치 + `docker-compose.{prod,demo,pilot}.yml`에 `OCR` 문자열 **0건** |
| 파일럿 런처 OFF | `scripts/demo/run_demo.ps1` 전체 182줄에 `ocr` 대소문자 무시 매치 **0건** |
| 503 사유 무구분 | `api/_ocr_state.py:33-44 get_ocr_components` — 비활성과 적재 실패가 **똑같이 `None`**이라 응답만으로 원리적 구분 불가. detail은 자연어 1문장, 기계 판독 코드 없음 |
| 적재 실패의 관측 부재 | `app.py:474-476` — `logger.warning(..., exc_info=True)`로 예외 타입은 남지만 **응답·리포트 어디에도 전파 없음**(부팅 로그 1줄) |
| 클라 무변별 | `ocr_controller.dart:70-76` — `catch (e)`가 `e`를 검사하지 않고 503/401/422/네트워크를 한 문구로 흡수. 분기 능력 자체는 있음(`:39-45` 이미지 선택 실패는 다른 문구) |
| 도달 관측 0 | `api/ocr.py`·`_ocr_state.py`·`l5/ocr/pipeline.py`·`factory.py`에 카운터·이벤트 매치 0건. `ops/`·`harness/` 리포트 11개 중 OCR을 다루는 것 **0개** |

부품이 실구현임도 재확인(`l5/ocr/` 8파일 1,526줄 + `api/ocr_handoff.py` 97줄). **"못 만든" 게
아니라 "만들어 놓고 닿지 않는" 상태**라는 v1 결론은 trunk 기준으로 불변이며, 미머지 구현분이
해소하는 것은 **무변별(②③)과 관측(④)**이지 **도달 자체가 아니다** — 파일럿 OCR 활성화는
여전히 범위 밖(v1 §5-①)이므로 머지 후에도 학생 도달은 0회다. 달라지는 것은
**"0회임이 보인다"**는 점이다.

### D2 (서버측 채점 shadow) — **설계대로 착륙 · 잔여 3건**

`harness/attempt_grading_shadow_report.py`(412줄) + 테스트(488줄)가 v1 설계를 그대로 이행했다:
3상태 파생(`grade_attempt:133-150` → `l3/verify_answer.py:124`), `unverifiable`의 오답 강등 금지,
`client_grade_mismatch_count`(`:227`), **분모 없는 0 금지**(`:229-241` — 표본 0이면 `0%`가 아니라
`None`), `not_derivable`과 `unverifiable`의 **버킷 분리**(`:265-272`), 라이브 경로 불변을
소스 레벨로 동결(`tests/backend/harness/test_attempt_grading_shadow_report.py:310-330` —
`api/me.py`에 `verify_answer` 문자열이 없음을 assert).

남은 것 3건:

1. **실행이 없다** — §3 D5. 리포트가 실데이터에 대해 산출된 적 0회.
2. **실효 커버리지가 구조적으로 좁다** — `derive_verify_inputs:93-130`은 모든 조건의 `formal`
   자유기호 합집합이 **정확히 `{"x"}`**일 때만 파생한다(다중 미지수는 의도적 스코프 밖).
   이 좁음 자체는 옳은 보수 설계지만, **얼마나 좁은지는 리포트를 돌려야 알 수 있다** — D5 없이는
   `unverifiable_rate`도 `not_derivable`도 값이 없다. **[→ §8-Δ2 — 이 판정은 뒤집혔다.
   리포트를 돌리지 않아도 코퍼스 grep으로 즉답 가능하고, 답은 "좁다"가 아니라 `0/2,647`이다.]**
3. **권위 이관 임계가 정성 서술뿐** — §3 D6.

부수 위생: `NLP-02` YAML의 `paths`(`api/me.py`·`l3/verify_answer.py`·`tests/backend/api/...`)가
실제 착륙 파일과 어긋나 `scope_drift` 경고가 **10건** 쌓인 채 done 처리됐다
(`backlog/events.ndjson`, 2026-08-03). 기록을 실제와 일치시킨다(§4 실행).

### D3 (단계 분해 계약) — **trunk 기준 불변 · 구현분은 미머지** [→ §8-Δ1·Δ3]

trunk에서는 `chat_controller.dart:244-250 _splitSteps`가 여전히 `'\n'` split 단독이고, 백엔드에
텍스트 분해 함수는 **없다**(`def split_solution|segment` 전수 grep 0건). `latex_to_plain.dart:13-15`
의 백엔드 미러링 자인도 그대로이며 **동기화 장치는 0**(양쪽 테스트가 서로의 파일을 읽지 않는다).
0-전이 관측도 0건 — 오히려 `sendSolution` doc(`:88-89`)이 "전이 0개여도 그대로 전송"이라 적어
**0-전이가 정상 흐름으로 흡수돼 흔적을 남기지 않는다**(fail-silent).

미머지 구현분(`8a3f176b`)이 계약 JSON·백엔드 정본·양쪽 골든·0-전이 관측을 모두 착륙시켰다
(§2-①). 머지 시 확인할 잔여는 **"골든 동결"과 "계약 소비로의 이관"의 차이** 한 가지다 — v1 ②는
클라가 계약을 *소비*하도록 이관하라고 했는데, 현 구현은 Dart의 기존 동작을 *동결*하는 회귀
골든이다. 드리프트 재발은 막지만 규약의 단일 출처화는 절반이다.

### D4 (서술형·개념형 의미 계층) — **페이퍼 유지**

발화 조건(페르소나 C·D 로드맵 진입) 미도달. 상태 변화 없음.

---

## §3. 신규 설계 D5~D7 (v1의 D1~D4에 번호 연속)

### D5 — 관측 리포트를 만들고 실행하지 않는다 (신규 태스크 · 횡단) [→ §8-Δ6 — 11개→12개, 러너는 여전히 1개]

**측정**: 리포트 CLI(`*_report.py`) 전수 11개를 러너 후보 전체(`.github/`·`docker-compose*.yml`·
`scripts/`·`infra/`)와 대조했다.

| 리포트 | 위치 | 러너 |
|---|---|---|
| `cost_report` | `ops/` | ✅ `scripts/fill_live_cost_table.py` · `infra/phaiakes9/LIVE_LLM_ACTIVATION.md` |
| `attempt_grading_shadow_report` | `harness/` | ❌ |
| `concept_reach_report` | `harness/` | ❌ |
| `visualization_reach_report` | `harness/` | ❌ |
| `assessment_seat_reach_report` | `harness/` | ❌ |
| `learning_path_orderability_report` | `harness/` | ❌ |
| `curriculum_revision_crosswalk_report` | `harness/` | ❌ |
| `recommendation_outcome_report` | `harness/` | ❌ |
| `surrogate_baseline_report` | `harness/` | ❌ |
| `pedagogy_content_slot_reach_report` | `ops/` | ❌ |
| `recommendation_reach_report` | `ops/` | ❌ |

**10/11.** 운영 런북도 없다(`docs/` 전체에서 이 CLI들을 언급하는 것은 **그들을 만든 갭 리뷰
문서 3개뿐**). CI에서 도는 것은 리포트 *코어의 유닛 테스트*이지 리포트 *실행*이 아니다
(`ci.yml`의 `python -m` 스텝 6개는 전부 게이트 성격 — `qa_pipeline`·`defect_detection_eval`·
`coach_prose_leak_eval`·`pedagogy_pack_fidelity_eval`·`notation_coverage`·`provenance_audit`).

**왜 이것이 갭인가**: `ops/cost_probe`가 세운 이중 회계 원칙 — *"인프라가 죽으면 '측정 실패'가
보여야지 '0건 통과'로 위장되면 안 된다"* — 은 리포트를 **돌리지 않을 때도** 그대로 적용된다.
지금은 아무 값도 없으므로 **"미측정"이 "문제 없음"으로 읽힌다.** 게다가 각 모듈 갭 리뷰가
"관측을 붙였다"로 닫혔기 때문에, 문서 상태만 보면 이미 측정된 것처럼 보인다 — 이것이 이
갭의 진짜 위험이다.

**정합 설계** (신규 로직 0 · 신규 스키마 0)

- **진입점 1개**로 리포트군을 실행하고 산출물(JSON)을 남긴다. 기존 CLI를 **호출만** 한다
  (`SEC-12`의 `retention-purge` compose 서비스 = 앱 이미지 재사용·CLI 호출만 선례 그대로).
- **두 부류를 섞지 않는다**:
  - `harness/*` = 코퍼스 JSON만 읽는 **결정론 리포트** → CI에서 실행 가능(산출물 아티팩트).
  - `ops/*` = **실 DB 필요** → 운영 진입점(compose 서비스·런북). CI에서 돌리면 "DB 없으니 0건"이
    되어 이 태스크가 고치려는 바로 그 위장을 만든다.
- **관측 전용 · 게이트 아님** — 수치가 0이어도 exit 0, 실행 오류만 비-0(기존 리포트 3사 공통 원칙).
  단 **실행 실패와 0건은 산출물에서 반드시 구분**한다.
- **배선 실재성 동결** — `tests/infra/test_test_suite_wiring.py`의 `Wiring`/`_all_wirings`를
  **import 재사용**해 확인한다. 새 YAML 파서를 만들지 않는다
  (`tests/infra/test_pedagogy_content_slot_pipeline_ci_wiring.py:22-25`가 명시한 원칙).
- **범위 밖**: 리포트 *내용* 수정·신규 리포트 추가·게이트화. 이 태스크는 **"돌린다"만** 한다.

**측정 없는 도입 없음**: 이 태스크의 성공 판정은 "배선했다"가 아니라 **산출물 파일이 실제로
생기고, 그 안의 값이 실행 전/후로 달라지는지**다(변별력 — 리포트가 죽어 있으면 "실행 실패"가
보여야 한다).

**태스크**: 신규 1건 등재(§4). `track=infra-debt` · `subject=cross` · `layer=infra` ·
`stage=S4` · `priority=3` (SEC-12와 동형 — 배포 형태 확정에 일부 의존하므로 3).

### D6 — 채점 권위 이관 임계의 사전 등록 (문서 정본화 · 태스크 신설 0) [→ §8-Δ2 — 최소 표본 200건은 D5만으로 영구 미달]

v1 §5-②의 이관 조건은 *"불일치율이 유의하거나, `unverifiable` 비율이 충분히 낮아…"*라는
**정성 서술**이고 정량 기준이 없다. 데이터가 나온 *뒤에* 임계를 정하면 사후 합리화가 된다 —
검증 권위 서열이 "점추정·인상 판정 금지"를 못 박은 축(`superhuman_verification_standard.md`)에서
특히 위험하다.

**사전 등록 임계** (D5 착륙으로 수치가 생긴 뒤 적용 · 지금은 코드화하지 않는다):

| 축 | 기준 | 미달 시 |
|---|---|---|
| 최소 표본 | 검산 가능(`verifiable`) 시도 **200건 이상** | 이관 금지 — "표본 부족"으로 표시(0%가 아니다) |
| 불일치율 | `client_grade_mismatch`의 **Wilson 95% 단측 상한**이 기준선 미만 | 이관 금지 |
| 실효 커버리지 | `not_derivable` + `unverifiable`을 뺀 판정 가능 비율이 **충분**해 이관 후 숙달 갱신 건수가 줄지 않음 | 이관 금지 — 커버리지가 낮으면 서버 권위는 **학습을 멈춘다** |

셋 중 **하나라도 미달이면 현행 유지**(클라 보고가 BKT 입력). 판정은 점추정이 아니라 Wilson
단측 경계로 하고, CLI exit 0/1로 낸다(기계 게이트 승격은 그때 별도 태스크).

**지금 코드를 만들지 않는 이유**: 실데이터 0건 상태에서 임계만 코드화하면 dead code다
(v1 D4가 "지금 태스크를 만들면 dead task"라 한 것과 같은 판단). 임계는 **문서에 먼저 박아
두는 것만으로** 사후 합리화를 막는 목적을 달성한다.

### D7 — 착륙 형태의 사후 대조 (**설계가 아니라 검증** · 태스크 조작 0)

> **집필 중 반전**: 이 절은 원래 `NLP-01`·`NLP-03`의 acceptance를 보정하는 설계였다. 그런데
> 두 태스크가 이미 구현돼 있음이 확인돼(§2-①), 보정할 대상이 사라졌다. **그대로 지우지 않고
> 남기는 이유**는 아래 대조가 "그 구현이 이 저장소의 확립된 형태와 맞는가"를 판정하는 체크리스트
> 역할을 하기 때문이다 — 머지 리뷰에서 그대로 쓸 수 있다. **acceptance는 고치지 않는다**(완료
> 근거의 소급 변조 금지).

**a) `NLP-01` — 관측을 어디에 두는가**

v1 acceptance ④는 "리포트에 노출 + CI 잡이 실제로 실행하는지 확인"이라고만 적었다. v1 이후
착륙한 `OPS-18`(클라우드 승급 사슬 도달 관측)·`PED-06`(성장 증거 도달 관측)이 이 저장소의
**정답 형태**를 확정했다. 미머지 구현분은 이 표의 2·3·5행을 **독립적으로 충족**했고(카운터를
`api/_ocr_state.py`에 두고 `/health/ready` 노출·3상태 분리·세 상태 변별력 동결), 1·4행은
**리포트를 만들지 않는 쪽**을 택했다(런타임 카운터로 대체) — 머지 리뷰에서 그 선택이
`ops/` 리포트 없이도 관측이 보존되는지 확인하면 된다:

| 축 | 확립된 형태 | OCR 적용 |
|---|---|---|
| 축 | 확립된 형태 | 미머지 구현분(`bbfc8c41`)의 선택 |
|---|---|---|
| 리포트 위치 | 런타임·DB 축은 `ops/`, 코퍼스 결정론은 `harness/`(`ops/recommendation_reach_report.py:16-22`가 갈림 근거를 명문화) | **리포트를 만들지 않음** — 런타임 카운터로 대체. 관측 자체는 성립하나 **오프라인 집계 창구가 없다**(머지 리뷰 확인 항목) |
| 런타임 카운터 | 인프로세스 상태 객체(`api/_*_state.py`) → `/health/ready` 노출(PED-06: `api/_growth_evidence_state.py` → `app.py:582` → `:713,739`) | ✅ `OcrReachCounters`를 **기존 `api/_ocr_state.py`에** 두고 `/health/ready`의 `ocr` 섹션으로 노출(신규 파일 0) |
| 이중 회계 | 0을 "0건 통과"가 아니라 **미도달/무데이터/구조적 불가**로 분리 | ✅ `enabled` 플래그로 "미활성(측정 대상 아님)" ↔ "활성인데 트래픽 0"을 분리 + 503 사유 `disabled`/`load_failed` 코드 분리 |
| 침묵 실패 금지 | 예외 타입명을 로그 본문에 포함(`exc_info`만으로는 불충족) | ✅ 적재 실패 로그 메시지 본문에 예외 타입명 직접 삽입(`_degradation.py` 관례 답습) |
| 변별력 | 양방향 실측(주입 → 값 변화 → 되돌림 → 복귀) | ✅ `tests/backend/api/test_ocr_reachability.py`(+416)가 **세 상태(비활성/적재실패/성공)가 서로 다른 카운터 조합을 냄**을 동결 |

범위(파일럿 OCR 활성화 제외)는 **불변**이다 — v1 §5-①의 발화 조건 미도달.

**b) `NLP-03` — Dart의 계약 JSON 읽기: 미확인 리스크였고, 실측으로 해소됐다**

v1 acceptance ②는 "계약 JSON 1개를 백엔드·모바일 테스트가 동시에 읽어 동일 판정"이라 적고
`notation_contract` 선례를 그대로 따르라고 했다. **그 선례는 Dart를 포함하지 않는다**:

| 실측 | 내용 |
|---|---|
| `notation_contract` 교차 골든의 실제 참여자 | 백엔드 `tests/backend/l3/test_notation_contract.py` ↔ **웹 JS** `src/web/graphing-calculator/test/notation_contract.test.js` — **2자** |
| 권위 비대칭이 JSON에 박혀 있음 | `data/notation_contract.json`의 `"authority": "backend SymPy"` / `"render_only": "web mathjs"` → 웹은 `numeric_cases`만, 백엔드는 `equivalence_cases`까지 |
| Dart 쪽 전례(v1 시점·trunk) | `src/mobile/test/` 전수에서 **`data/*.json`을 읽는 테스트 0건**. 파일을 읽는 유일한 사례는 `governance/no_math_logic_governance_test.dart:100`의 **소스 스캔** |
| **해소** | 미머지 구현분 `src/mobile/test/segmentation_contract_test.dart`가 `File('../../data/segmentation_contract.json')`(cwd = `src/mobile`) + **조용한 skip 대신 명시적 fail**로 해결. private `_splitSteps`는 fake `CoachApi`로 `CoachRequest.solutionSteps`를 캡처해 공개 경로로 관찰 |

**머지 리뷰 잔여 1건**: 그 Dart 테스트는 계약을 *소비*하는 것이 아니라 **기존 동작을 동결하는
회귀 골든**이다(테스트 헤더가 "알고리즘 변경 없음"이라 자인). v1 ②가 요구한 **이관**(클라
`_splitSteps`·`latexToPlainSolution`을 계약 소비로 전환)은 절반만 이행됐다 — 드리프트 *재발*은
막지만 규약의 단일 출처화는 아직이다. 이 잔여를 **어디에 기록할지는 머지 시점의 판단**이며,
지금 새 태스크로 만들지 않는다(미머지 코드에 대한 선제 태스크는 dead task가 될 수 있다).

---

## §4. 정직한 공백 — v1 §4 갱신

v1의 7종 중 **⑥(음성 입력)만 판정 근거를 교체**하고, 나머지는 승계한다. 신규 2종을 추가한다.

**⑥ 교체 — 음성 입력(STT)**: v1은 *"정본의 `speech`는 출력이고 틀의 40개 세부에도 STT는 없다"*는
이유로 **대조 대상에서 제외**했다. 절반만 맞다 — 틀의 세부 40개에는 없지만, **틀의 아키텍처
다이어그램은 학생 입력을 "텍스트·음성·사진·손글씨"로 명시**한다. 따라서 제외가 아니라
**의도적 미채택**으로 판정을 바꾼다(결론은 동일, 근거가 다르다):

- 미채택 근거: `speech_to_text`·`flutter_tts` 의존은 `MOB-09`(2026-08-03)가 **실제로 제거**했다
  (`src/mobile/pubspec.yaml:45-49` — 사용처 0 + `speech_to_text` 7.4.0이 `flutter.compileSdkVersion`
  참조로 고정 툴체인 빌드를 깨뜨린 실측). 즉 재도입은 `MOB-01`이 고정한 툴체인 재교란이다.
- 발화 조건: §5-⑦.
- **주의**: "음성 관련 0건"이라고 쓰면 틀린다 — **출력**(Math-to-Speech)은 백엔드에 완비돼 있다
  (`api/speech.py` `/v1/speech` · `l3/speech.py` 결정론 규칙엔진 · LLM 0). 그 **클라 소비 0**은
  `service_operations_gap_review.md` §유보⑤가 이미 다루므로 **여기서 중복 등재하지 않는다**.

**신규 ⑧ — NLU 판정의 분포를 아무도 세지 않는다**: `should_advance`(`transitions.py:72-131`)의
stay/next 판정과 `select_category`(`socratic/select.py:115-122`)의 카테고리 선택은 **코치 응답
JSON으로 나가는 것이 전부**다. DB 미저장(`DialogueTurn`에 전이 컬럼 없음)·이벤트 미적재
(`EventType` 11종에 전이 계열 없음 — 적재되는 것은 `검산결과`·`힌트제공`뿐)·리포트 미집계
(`harness/`·`ops/` 전수에서 polya 언급은 `pedagogy_policy_eval.py:59-63` 고정 시나리오 라벨뿐).
이 사실이 §5-③의 순환을 만든다.

**신규 ⑨ — `student_intent` writer는 여전히 0** **[→ §8-Δ1 — `PED-04` 착지로 상환]**: `schema/enums.py:934-943`(5종)·
`db/models/dialogue.py:189-191` 컬럼 실재, 값을 넣는 곳은 테스트 3곳뿐
(`api/coach.py:1418-1435`·`:1620-1640`의 턴 생성이 채우지 않는다). v1 판정 유지 —
`PED-04` acceptance①이 이미 생산을 지정하므로 **재설계 금지**.

---

## §5. 유보 항목의 발화 조건 — v1 §5 갱신

v1의 ①②④⑤⑥은 그대로 승계한다. **③을 개정**하고 **⑦을 추가**한다.

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ③ **(개정)** | LLM 기반 의도 분류·LLM-judged Polya 전이 | v1은 "키워드 화이트리스트의 false-negative를 **실사용에서 측정**한 뒤"라 했다. 그런데 §4-⑧대로 **그 측정 수단 자체가 0**이므로 이 조건은 현재 **구조적으로 충족 불가**다. 측정 좌석을 채우는 것은 `PED-04` acceptance①(`DialogueTurn` 메타 컬럼 writer)이다 → **③은 사실상 `PED-04` 종속**임을 여기 명문화한다. 순서는 바뀌지 않는다(측정이 먼저) — 다만 "측정을 언제 할 수 있는가"의 답이 이제 백로그 상의 특정 태스크를 가리킨다 |
| ⑦ **(신규)** | 음성 입력(STT) | ⓐ 페르소나 요구가 관측되고(시각 약자·필기 곤란 등 구체적 접근성 요구) ⓑ `MOB-01` 툴체인 고정을 깨지 않는 의존 경로가 확인됐을 때. 그전에는 재도입하지 않는다(`MOB-09` 제거 사유 승계) |
| ② (승계·정량화) | 채점 권위 서버 이관 | v1 조건 + **§3 D6의 사전 등록 임계 3축 전부 충족**. 하나라도 미달이면 현행 유지 |

---

## §6. 반복 실수 — "완비돼 있는데 닿지 않는다" 계열 4회차

| 회차 | 사례 | 형태 |
|---|---|---|
| 1 | `tests/infra` 199건이 어떤 잡도 실행하지 않음(`OPS-03`) | 만들고 **CI에 배선 안 함** |
| 2 | 전 시각화 스택 학생 도달 0회(`VIZ-01`) | 만들고 **적재 안 함** |
| 3 | OCR 전 파이프라인이 배포 경로 양쪽에서 비활성(v1 D1) | 만들고 **배포에 넣지 않음** |
| **4** | **관측 리포트 11개 중 10개 러너 0건(D5)** | 만들고 **실행하지 않음** |

4회차가 앞의 셋과 다른 점: **피해자가 관측 계층 자신**이다. 1~3은 관측을 붙여서 발견했지만,
4는 그 관측이 돌지 않으므로 **다음 회차를 발견할 수단이 없다**. 이 계열이 자기 자신을 먹는
지점이다.

CLAUDE.md는 이미 *"검증 장치를 만들고 배선 확인 없이 완료 선언 금지"*를 담고 있고, v1 §6은 그
규칙을 **런타임 기능 일반으로 확장**하자고 제안했다. 이번 회차는 한 걸음 더 나간다 —
**판정 기준을 "배선됐는가"가 아니라 "산출물이 실제로 생겼는가"로 둔다.** `tests/infra` wiring
테스트가 "돌아감"을 동결하듯, D5의 산출물 존재가 "측정됨"을 동결한다.

### §6-b. 두 번째 위험 — 갭 리뷰가 미머지 구현을 보지 못한다

이 재점검은 **하마터면 이미 구현된 것을 다시 설계할 뻔했다**(§2-①). 작업 트리(= trunk)만 보면
`NLP-01`·`NLP-03`은 `status: todo`이고 관련 코드는 v1 이후 변경 0건이라, "미착수"라는 오판을
**모든 신호가 지지**했다. 실제로 막아 준 것은 코드도 문서도 아닌 **하네스의 원격 claim 대장**
(`backlog.py next`의 "이미 완료(미머지)" 제외)이다.

이 리스크는 커지고 있다 — 세션 브리핑 기준 **장기 미머지 브랜치가 60개 이상**이고, 그중 다수가
`trunk 대비 수백 커밋 앞섬` 상태다. 즉 **trunk는 이 프로젝트의 실제 진척을 점점 덜 대표한다.**
갭 리뷰는 정의상 "trunk에 무엇이 없는가"를 세는 작업이므로, 미머지 물량이 늘수록 **없다는
판정의 오류율이 올라간다**.

**갭 리뷰 착수 규약(제안)**: 갭을 "없다"로 판정하기 전에 **① `backlog.py next`의 제외 경고를
읽고 ② 해당 태스크 ID로 원격 브랜치를 실측**한다(`git log --all --grep=<TASK-ID>`). 코드 grep이
0건인 것은 **trunk에 없다는 뜻이지 만들어지지 않았다는 뜻이 아니다.** 이번 문서의 §2-①이 그
절차를 실제로 밟은 첫 기록이다.

**근본 대응은 이 문서의 범위 밖**이다 — 미머지 브랜치 60여 개의 회수·정리는 별도 축이며,
세션 브리핑이 이미 "Kiki 확인 필요"로 매일 띄우고 있다. 여기서는 **갭 판정의 절차**만 고친다.

---

## §7. 실행 — 백로그 등재·정정 대장

| # | 조작 | 대상 | 내용 |
|---|---|---|---|
| 1 | **신규 등재 1건** | D5 | `OPS-19-observability-report-runner-wiring`(infra-debt·cross·S4·p3). `backlog.py add` 경유로 ID 배정(번호 추론 금지·HARN-10), `--path` 겹침 검사 활성 |
| 2 | `paths` 정정 | `NLP-02` | 실제 착륙 파일(`harness/attempt_grading_shadow_report.py`·그 테스트)로 일치 — `scope_drift` 경고 10건이 쌓인 채 done 처리돼 있었다. **status 불변** |
| 3 | 코드 정정 | `config.py` `ocr_recognizer_backend` 설명 | `texteller`/`qwen_vl` "스텁·미배선" → 실배선(로직 0·설명 문자열만·§1-②) |
| 4 | 배너 | v1 문서 | r2로 오는 1줄. 본문 소급 수정 금지 |

**태스크를 만들지 *않은* 것 — 중복·소급 배제 대장**:

| 축 | 이유 |
|---|---|
| `NLP-01`·`NLP-03` acceptance 보정 | **이미 구현됨**(미머지·§2-①). 완료된 작업의 판정 기준을 뒤늦게 고치는 것은 소급 변조이고 머지 시 YAML 충돌을 만든다 → §3 D7을 **머지 리뷰 체크리스트**로 전환 |
| `NLP-03` 이관 잔여(골든 동결 ≠ 계약 소비) | 미머지 코드에 대한 선제 태스크는 dead task가 될 수 있다 — 머지 시점에 판단 |
| `/v1/speech` 클라 소비 0 | `service_operations_gap_review.md` §유보⑤가 이미 다룸 |
| `student_intent` writer | `PED-04` acceptance① |
| 다중 풀이·힌트 생성 | `S4-10`·`S4-11` |
| D6 임계 코드화 | 실데이터 0건 — D5 착륙 후 판단(지금 만들면 dead code) |
| 미머지 브랜치 60여 개 회수 | 이 문서 범위 밖(세션 브리핑이 매일 Kiki에게 띄우는 별도 축) — §6-b는 **갭 판정 절차**만 고친다 |

---

## 부록 — 실측 근거 (2026-08-04 · 브랜치 `claude/whymath-nlp-design-my18a1` · 기준 `de446ec3`)

**D1 재확인**
- `config.py:1046-1054 ocr_enabled`(기본 False) · `:1064-1069 ocr_recognizer_backend`(stale) ·
  `:1071-1078 ocr_detector`
- `app.py:461`(분기)·`:465-473`(적재)·`:474-476`(실패 경고)·`:478`(비활성 표시)·`:918`(라우터 무조건 등록)
- `api/_ocr_state.py:33-44 get_ocr_components` — 단일 503·자연어 detail
- `Dockerfile:43-46` · `scripts/demo/run_demo.ps1`(ocr 매치 0) ·
  `infra/phaiakes9/systemd/whymath.env.example:27-34`(대조군 ON)
- `src/mobile/lib/features/ocr/application/ocr_controller.dart:70-76`(무변별)·`:39-45`(분기 능력 존재)
- `l5/ocr/recognize.py:109-140`(RapidLatex)·`:143-203`(TexTeller 실구현)·`:206-293`(QwenVl 비동기 실배선)·
  `l5/ocr/factory.py:125-143`(둘 다 배선) · `l5/ocr/assemble.py:29+` · `api/ocr_handoff.py:31-97`

**D2 착륙 확인**
- `harness/attempt_grading_shadow_report.py:93-130 derive_verify_inputs`(단일 미지수 게이트)·
  `:133-150 grade_attempt`·`:227`(mismatch 카운터)·`:229-241`(분모 없는 0 금지)·`:265-272`(버킷 분리)·
  `:361-408 main`
- `tests/backend/harness/test_attempt_grading_shadow_report.py:310-330`(라이브 경로 불변 동결)
- `api/me.py:597`(v1 한계 자인)·`:604-605`(`student_answer` 슬롯)·`:682`(적재)·`:691-698`(숙달 전파 = 클라 보고)
- `backlog/events.ndjson`(2026-08-03 `scope_drift` 10건)

**D3 불변 확인**
- `chat_controller.dart:244-250 _splitSteps` · `:88-89`(0-전이 그대로 전송) · `:121-122 sendMathLiveSolution`
- `chat/domain/latex_to_plain.dart:13-15`(미러링 자인)·`:24,27,31-37,42-51,136`(미러 지점)
- `data/notation_contract.json` ↔ `tests/backend/l3/test_notation_contract.py:24-38` ↔
  `src/web/graphing-calculator/test/notation_contract.test.js:9,23,27`
- 백엔드 텍스트 분해 함수 grep 0건 · `api/verify.py:8-9`(책임 전가)

**D5 측정**
- 리포트 11개 × 러너 후보(`.github/`·`docker-compose*.yml`·`scripts/`·`infra/`) 전수 대조 — §3 표
- `ci.yml:187,265-296`(게이트 성격 `python -m` 6종) · `:247`(pytest) · `:684`(tests/infra)
- `docs/` 전체에서 리포트 CLI 언급 = 그들을 만든 갭 리뷰 3개뿐
- 미머지 브랜치 `claude/openrouter-setup-guide-e98dw4`도 러너를 추가하지 않음
  (`git diff f277c403..origin/claude/openrouter-setup-guide-e98dw4 -- .github/ scripts/ infra/`의
  `ci.yml` 추가분은 `qa_pipeline` 1행뿐) — D5는 미머지분을 포함해도 성립한다

**미머지 구현분(§2-①)**
- `bbfc8c41` NLP-01 — `api/_ocr_state.py`(+204) · `app.py`(+129) · `api/ocr.py`(+27) ·
  `ocr_controller.dart`(+17) · `ocr_controller_test.dart`(+49) · `tests/backend/api/test_ocr_reachability.py`(+416)
- `8a3f176b` NLP-03 — `data/segmentation_contract.json`(10케이스) ·
  `l5/ocr/text_segmentation.py`(신설) · `api/_segmentation_state.py`(신설·0-전이 관측) ·
  `api/coach.py`(+131) · `src/mobile/test/segmentation_contract_test.dart`(신설) ·
  `tests/backend/api/test_solution_segmentation_observability.py` · `tests/backend/l5/ocr/test_text_segmentation.py`
- `186b70c2`·`392913a2` 각 태스크 done 처리(그 브랜치의 백로그 YAML 기준)

**NLU 실체**
- `l4/polya/transitions.py:5-8`(비대칭 설계)·`:26-51`(전략 20종)·`:56-65`(정답 6종)·`:72-131 should_advance`
- `l4/socratic/select.py:48-57 _INPUT_SIGNAL_TOKENS`·`:115-122`(stay 한정 오버라이드)
- `schema/enums.py:934-943 StudentIntent`(writer 0) · `api/coach.py:1418-1435`·`:1620-1640`(미충전)
- `harness/wh1_llm_policy.py:337-346`(`classify` 실호출 — v1 §4-3 반증) · `l3/router.py:84`

---

## §8. 재검증 — 회수 시점 델타 (2026-08-11 · 브랜치 `claude/whymath-nlp-review-design-ufa2ax` · 기준 `d088ae77`)

> **왜 이 절이 있는가**: 이 문서는 2026-08-04에 완성됐으나 **PR #697(open)에 7일간 머물러
> main에 착륙하지 못했다.** 2026-08-11 세션이 같은 외부 틀(『16. 자연어 처리』)을 다시 받아
> 착수했다가 이 문서를 발견하고 **재작성 대신 회수**를 택했다(`math_engine_gap_review.md` §7
> 선례 — 새로 쓰면 경쟁 문서 2개가 생기고, 이미 내린 판단이 두 번 소비된다).
>
> **본문 §0~§7은 무수정이다.** 7일 사이 무엇이 참이 아니게 됐는지가 이 절의 내용이며, 본문의
> 해당 지점에는 `[→ §8-Δn]` 표시만 달았다.

### §8.0 회수 경위 — "미머지 고립" 계열 5회차 (설계 문서 형태 2번째)

| 축 | 실측 |
|---|---|
| 문서 | `docs/architecture/nlp_module_gap_review_r2.md`(499줄) — 2026-08-04 작성 |
| PR | **#697 open** (생성 2026-08-04 · 최종 갱신 2026-08-09 · **미머지 7일**) |
| 브랜치 | `origin/claude/whymath-nlp-design-my18a1` — main과 **공통 조상 존재**(`e93d36bc`), diff 8파일 `+631/-4` |
| main 부재물 | r2 문서 · `OPS-19` 태스크 · v1 배너 · `config.py` stale 정정 · `CLAUDE.md` 갭 판정 절차 규칙 · `NLP-02` paths 정정 |
| 세션 브리핑 탐지 | **미탐** — "미머지 브랜치의 신규 설계 문서" 목록에 이 문서가 없었다(목록은 08-11·07-29 3건만) |

`math_engine_gap_review.md` §6이 명명한 **계열 C(고립분이 *판단*이라 증상이 조용하다)**의
2번째 사례다. 코드 고립은 테스트가 red를 내지만, **이미 내린 판단은 없어도 아무 신호가 안 난다** —
이 세션도 착수 후 30분간 "NLP r2를 새로 쓴다"는 계획으로 진행했고, 발견한 것은 착수 절차의
`git log --all --diff-filter=A -- 'docs/architecture/nlp_module*'` 한 줄이었다.

**등재**: 회수 절차의 방어 장치가 두 개인데 **둘 다 이 건을 놓쳤다** — ⑴ 세션 브리핑의 신규
설계문서 목록(미탐) ⑵ `backlog.py next`의 "이미 완료(미머지)" 경고(이 건은 태스크가 아니라
*문서*라 대장에 없다). 실제로 막은 것은 세 번째, **`--diff-filter=A` 경로 스캔**이다. 이 절차가
갭 리뷰 착수의 필수 스텝임을 여기 못 박는다(본문 §6-b의 규약을 **문서 축까지** 확장).

### §8.1 Δ1 — §2-①의 "미머지"가 해소됐다 (상환 3건)

`NLP-04`(2026-08-08, MEMORY 결정 로그)가 `claude/openrouter-setup-guide-e98dw4`의 고립분을
main에 이식했다. 본문 §2-①의 판정은 **그 시점에는 정확했고, 지금은 상환됐다.**

| 본문 판정 | 2026-08-11 실측 |
|---|---|
| `NLP-01` done·미머지 | ✅ **main 착륙** — `api/_ocr_state.py`(`OcrUnavailableReason` = `"disabled"`\|`"load_failed"` · `OcrReachCounters`) → `app.py:455 _ocr_reach_body` → `/health/ready`의 `ocr` 필드(`app.py:428`) · `ocr_controller.dart:70-84` 문구 분기 · `tests/backend/api/test_ocr_reachability.py` |
| `NLP-03` done·미머지 | ✅ **main 착륙** — `data/segmentation_contract.json` · `l5/ocr/text_segmentation.py` · `api/_segmentation_state.py` → `/health/ready`의 `solution_segmentation` 필드(`app.py:431`) · `src/mobile/test/segmentation_contract_test.dart` |
| §4-⑨ "`student_intent` writer는 여전히 0" | ✅ **상환** — `PED-04` 착지. `l4/turn_meta.py:203 classify_student_intent`(결정론·LLM 0회·5종 우선순위) → `api/coach.py:1964`·`:2277` 호출 → `:1687 turn.student_intent = meta.student_intent` 적재 → `:1458` 컬럼 투영으로 **세션 내 회상까지 소비**(`turn_meta.py:272`) |

**따라서 본문 §3 D7(머지 리뷰 체크리스트)은 이제 "사후 대조"가 아니라 "대조 완료"다.** 본문
§2-①이 예측한 대로 미머지 구현분이 `_ocr_state.py` 카운터 → `/health/ready` 형태에 독립
수렴했음이 main에서 확인된다(`PED-06`·`OPS-18`이 확립한 형태). **acceptance는 여전히 고치지
않는다**(완료 근거의 소급 변조 금지 — 본문 판단 승계).

### §8.2 Δ2 — **판정 뒤집기**: D2 잔여 ②는 "좁다"가 아니라 **구조적 0**이다 (최대 발견)

본문 §2 D2 잔여 ②는 *"이 좁음 자체는 옳은 보수 설계지만, **얼마나 좁은지는 리포트를 돌려야 알 수
있다**"*라고 적었다. **틀렸다 — 리포트를 돌리지 않고도 답이 나오고, 답은 0이다.**

`derive_verify_inputs`(`harness/attempt_grading_shadow_report.py:93`)의 파생 조건은
`Problem.conditions_parsed[*].formal`이다. 코퍼스 전수 실측:

| 측정 축 | 값 |
|---|---|
| 문제은행 7뱅크 총 문항 | **2,647** |
| `conditions_parsed`가 비어있지 않은 문항 | **30** (1.13%) |
| 그중 `formal` 필드를 가진 문항 | **0** |
| 코퍼스 jsonl 전체의 `"formal"` 키 출현 | **0건** (7파일 전부 0) |
| 저장소 전체의 `Condition(formal=...)` writer | **0건** |

→ `derive_verify_inputs`는 **2,647건 전부에서 `None`을 반환한다.** `verdict_counts`는 영구히
전부 0이고 `not_derivable_count`만 100%다. **`client_grade_mismatch`는 단 한 번도 산출될 수 없다.**

**그런데 필요한 재료는 코퍼스에 100% 있다.** 문항 레코드의 `verify` 블록이 `answer_map` +
`conditions`를 **2,647/2,647 = 100%** 보유한다:

| `verify` 필드 조합 | 건수 |
|---|---|
| `{answer_map, conditions}` | 1,082 |
| `{answer_map, answer_selection, conditions, solution_steps}` | 1,049 |
| `{answer_kind, answer_map, conditions}` | 360 |
| `{answer_aggregate, answer_map, conditions}` | 120 |
| `{answer_kind, answer_map, conditions, verification_tier}` | 34 |
| `{answer_map, answer_selection, conditions}` | 2 |

오프라인 경로는 이미 이 블록을 쓴다(`whs/corpus_replay.py:104` — `verify.conditions`/
`verify.answer_map`을 그대로 `verify_answer`에 먹인다). **버리는 것은 L1 적재다** —
`l1/problem_bank/populate.py:296 data.pop("verify", None)` 후 `:214`가 자인한다:
*"적재 파이프라인은 `slug`·`problem`·`concept_tags`·`relations`만 소비한다"*. `schema.Problem`에도
`db/models/problem.py`에도 `verify` 컬럼은 없다.

**즉 `NLP-02`의 자기 진단은 DB에 대해서는 정확했고 결론이 틀렸다.** 그 모듈 docstring은
*"`Problem`에는 `answer_map` 필드가 없다(이 태스크의 제약 — 신규 컬럼 0). 있는 재료는
`Problem.conditions_parsed[*].formal` … 뿐이다"*라고 적었는데, 재료는 **상류에 100% 있고 적재가
버린 것**이며, 대신 고른 폴백은 **writer가 존재한 적 없는 필드**였다.

**본문 D6(사전 등록 임계)에 미치는 영향 — 여기가 진짜 손해다.** D6은 이관 조건으로
*"검산 가능 시도 **200건 이상**"*을 사전 등록했다. Δ2에 따라 이 값은 **`OPS-19`(D5 러너)가
착륙해도 영원히 0**이다. 즉 v1 §5-②의 "채점 권위 서버 이관" 유보는 **해제도 영구화도 불가한
상태** — CLAUDE.md *"만료 없는 유예·제외 금지"*(2026-08-03) 해당이며, `learning_path_module_
gap_review_r2.md` D6이 발견한 것과 같은 형태다(*산문 규칙이 다른 태스크를 막지 못한* 사례의
역: *다른 태스크가 산문 조건을 영구 미달로 만든* 사례).

**신규 태스크 등재**(§8.6) — 설계 요지:
- **1차 처방은 신규 채점기 0·신규 스키마 0**: 이미 100% 존재하는 코퍼스 `verify` 블록을
  리포트가 직접 읽는다(`whs/corpus_replay.py:104` 선례 그대로 — DB 컬럼 추가보다 저렴하고,
  `not_derivable`의 원인이 "DB에 없음"이지 "데이터가 없음"이 아님을 그대로 드러낸다).
  DB 적재로 되살리는 안은 **대안**으로 남기고 태스크가 판단한다.
- **`{"x"}` 단일 미지수 게이트는 유지**한다 — false pass 방어선이며 Δ2가 지적하는 것은
  게이트가 아니라 **게이트에 도달하기도 전에 입력이 0이라는 사실**이다.
- **탈락 사유를 분리 계수**한다: `no_conditions` / `no_formal` / `parse_error` / `multi_symbol` /
  `no_student_answer`. 지금은 이 다섯이 전부 `not_derivable` 한 통에 들어가 **"왜 0인가"가
  보이지 않는다** — 본문 D2가 칭찬한 "`not_derivable`과 `unverifiable`의 버킷 분리"를 한 겹 더
  내린 것이다.
- **교수학 계약 승계**: `unverifiable`을 오답으로 강등하지 않는다(v1 D2 · 본문 §2 D2).
- **범위 밖 명시**: BKT 입력 권위 이관 아님(관측만).

### §8.3 Δ3 — NLP-03의 교차 골든이 CI에서 **어느 방향으로도 강제되지 않는다** (신규 갭)

본문 §2 D3은 착륙물의 잔여를 *"골든 동결 ≠ 계약 소비"* 한 가지로 봤다. 회수 시점 실측은 그보다
앞선 층에서 문제를 찾는다 — **그 골든이 CI에서 돌지 않는다.**

`.github/workflows/ci.yml`의 경로 필터(`:74` backend · `:83` mobile) 실측 시뮬레이션:

| 변경 파일 | backend 잡 | mobile 잡 |
|---|---|---|
| `data/notation_contract.json` | ✅ | ❌ |
| **`data/segmentation_contract.json`** | ❌ | ❌ |
| `data/scene_contract.json` | ❌ | ❌ |

backend 필터는 `data/notation_contract.json`·`data/render_contract.json` **2개만 열거**하고,
mobile 필터는 `^(src/mobile/|schemas/|\.github/workflows/ci\.yml$)`뿐이라 `data/` 계약이 통째로
빠져 있다. 결과:

1. **계약 JSON만 고친 PR은 CI 잡이 0개 실행된다.** `data/segmentation_contract.json`은
   NLP-03이 만든 *정본*인데, 그 정본을 고치는 변경이 **자기를 지키는 두 테스트 어느 쪽도
   트리거하지 않는다**.
2. **백엔드 구현만 고친 PR은 Dart 미러를 검사하지 않는다**(mobile 필터에 backend 경로 없음).
   즉 v1 D3이 막으려던 **드리프트가 백엔드→클라 방향으로 여전히 열려 있다**.

`math_engine_gap_review.md` §7 Δ2가 "mobile 필터 구멍"을 지적하며 이 Dart 골든을 **라이브
미집행 대상 3건** 중 하나로 셌는데, `data/` 축(위 1번)은 그 관찰에도 없다. 판정 기준을 한 단계
더 밀면: *"게이트를 트리거하는 경로가 그 게이트가 지키는 파일을 실제로 덮는가"* → **덮지 않는다.**

**설계 요지**: `data/*_contract.json` 계열을 **backend·mobile·web 필터 모두에** 넣되, 파일을
하나씩 열거하는 현행 방식(누락이 조용하다)이 아니라 **디렉터리/글롭 축**으로 올린다. 그리고
`tests/infra`에 **계약 파일 ↔ 트리거 잡 대응을 동결**하는 배선 실재성 테스트를 둔다
(`test_test_suite_wiring.py`의 `Wiring`/`_all_wirings` **import 재사용** — 새 YAML 파서 금지,
`OPS-19` acceptance ⑤와 같은 원칙). 신규 계약 파일이 생겼는데 필터에 없으면 **exit 1**.

### §8.4 Δ4 — OCR 재확인 보류 축이 **상시 False**이고 소비자도 0 (신규 갭)

v1 §1 기능 69의 "OCR 오류 자동 보정"은 **✅ (더 엄격)**으로 판정됐다 — *"저신뢰는 `low_quality`
플래그로 **보류**"*. 실측하면 그 칭찬은 **다른 축**에 해당하고, 이름이 붙은 축은 죽어 있다.

| 축 | 임계 출처 | 상태 |
|---|---|---|
| 서버 영역 단위 `needs_review` → `needs_reconfirmation` | `config.py:1130 ocr_min_confidence` **기본 `0.0`** | `l5/ocr/assemble.py:60` `needs_review = review_threshold > 0.0 and …` → **상시 False**. `:91`의 페이지 OR도 따라서 상시 False |
| 코치 게이트 `match_low_quality` | `api/coach.py:347` **0.8 하드코딩** | 실동작 — **v1이 칭찬한 것은 이쪽** |
| 모바일 `_RecheckCue` | `ocr_models.dart:142 lowConfidenceThreshold` **자체 상수** | 실동작 — 단 서버의 `needs_reconfirmation`을 **읽지 않고**(`hasLowConfidenceRegion`이 `overallConfidence`/`region.confidence`로 자체 판정) 코치 임계를 미러링 |

두 가지가 겹쳐 있다.

- **기본값이 축을 끈다**: `needs_review`/`needs_reconfirmation`은 스키마(`schema/ocr.py:181`·
  `:249`)·조립·페이지 OR(`:282`)까지 완비됐는데 **기본 설정에서 값이 변하지 않는다**. 이는
  "opt-in"이 아니라 **상시 미작동**으로 회계해야 한다 — opt-in은 켜는 주체가 있을 때의 이름이고,
  이 좌석은 켜는 경로가 어느 배포 경로에도 없다(OCR 자체가 OFF이므로 이중으로).
- **소비자가 0이다**: 클라가 서버 신호 대신 **자체 임계로 재구현**했다. v1 D3이 지적한
  `latex_to_plain.dart`의 미러링 드리프트와 **같은 형태**가 신뢰도 축에서 반복된 것이며,
  결과적으로 저신뢰 임계가 **세 곳(0.0 / 0.8 / 0.8)** 에 흩어져 있고 그중 정본이 없다.

**왜 중요한가**: 이 축의 목적은 *오인식을 학생 오류로 거짓 지적하지 않는 것*이다 — 의사결정
우선순위 **1위(학생 안전·웰빙)** 이고, v1이 "더 엄격하다"고 칭찬한 바로 그 성질이다. 지금
그 엄격함은 **코치 0.8 게이트 하나**가 떠받치고 있고, 영역 단위 보류는 이름만 있다.

**설계 요지**(신규 임계 발명 0): 저신뢰 임계의 **단일 정본**을 정하고 세 지점이 그것을 참조하게
한다. `needs_reconfirmation`은 ⑴ 기본값을 살려 실제로 발화시키거나 ⑵ **정직하게 제거**하거나
둘 중 하나다 — 지금처럼 "있는데 항상 False"인 상태가 최악이다(존재가 작동으로 읽힌다).
**OCR 활성화는 범위 밖**(v1 §5-① 유보 유지).

### §8.5 Δ5 — 미채택 선언 축에 점수 계산기만 착지하고 호출자 0 (신규 갭·판정 정정)

v1 §1 기능 68 "부분점수 계산"은 *"`ScoringType.부분점수` enum·문항 메타 라벨만 실재. **점수 계산
로직 0**"* → §2-② **의도적 미채택**(교수학 금기 — "정답을 빠르게"를 KPI로 쓰지 않는다)이었다.

**실측**: `l6/blueprint/assembly.py:526 partial_credit(points, verification)`이 **실재**한다 —
`verify_solution.first_incorrect_index`를 부분 인정 근거로 재사용하는 fail-closed 5분기
(`no_points_declared` / `no_transitions` / `unverifiable_prefix` / `credited_full` /
`credited_partial`), 인정 구간에 `unverifiable`이 섞이면 허위 확언 금지로 점수를 만들지 않고,
비율→점수는 **내림**이다. 설계 자체는 이 저장소의 정직 회계 관례를 충실히 따른다.

**그런데 프로덕션 호출자가 0이다.** `l6/blueprint/__init__.py:34,40,50,57`이 export하지만
`api/me.py:155`는 `AssembledTestSet`·`ExamBlueprint`·`assemble_test_set` **3개만** import한다.
모바일 0건. 유일한 호출은 `tests/backend/l6/blueprint/test_assembly.py`다.

**두 층의 문제**:
1. **판정과 코드가 어긋났다** — "점수 계산 로직 0"이 더 이상 사실이 아니다. 미채택은 여전히
   유효할 수 있으나(학생 대면 KPI 축) **근거 문장은 갱신돼야 한다**: 불채택 대상은 "계산기의
   존재"가 아니라 **"학생에게 점수를 보여주는 것"** 이다.
2. **미채택 선언 축의 조용한 좌석은 다음 세션에 "이미 되는 것"으로 오독된다** — v1 §4-③이
   `NLP_TASK_TYPES`의 `classify`에 대해 정확히 이 이유로 기록을 남겼고, 본문 §1-①-a는 그
   기록이 **반대 방향으로 틀렸음**을 밝혔다. 같은 함정의 세 번째 자리다.

**설계 요지**: 좌석을 **처분한다** — ⑴ 시험지 조립 축의 소비처에 배선하고 그 노출이 학생 대면인지
교사·자기채점 대면인지 명시하거나, ⑵ 제거하거나. 어느 쪽이든 **v1 §2-② 미채택 근거 문장을
갱신**한다(문서 축). `ASM-02`(등급 노출 정책·owner=kiki)와 **같은 결정 축**이므로 정합을 맞춘다.

### §8.6 Δ6 — 본문 D5(관측 리포트 러너)는 유효하고 **악화**됐다

본문 §3 D5의 측정(리포트 11개 중 러너 1개)을 회수 시점에 재실행했다.

| 축 | 2026-08-04 (본문) | 2026-08-11 (재측정) |
|---|---|---|
| `*_report.py` 총수 | 11 | **12** (`harness/standard_attainment_report.py` 신설 — `ASM-05`/`S4-19`) |
| 러너 보유 | `cost_report` 1개 | **`cost_report` 1개** (변화 없음) |
| 러너 0건 비율 | 10/11 (90.9%) | **11/12 (91.7%)** |

`OPS-19`는 main에 **없다**(이 회수로 처음 착륙한다). CI의 리포트 언급을 재확인하면
`test_concept_reach_report`(OPS-23 가드 잡)가 걸리는데 이는 **리포트의 유닛 테스트**이지 리포트
실행이 아니다 — 본문 D5가 이미 구분한 그대로다. **판정 유지, 수치만 갱신.**

그리고 Δ2가 D5에 **새로운 의미**를 더한다: `OPS-19`가 착륙해 `attempt_grading_shadow_report`를
실제로 돌려도 **산출은 `not_derivable 100%`뿐**이다. 즉 D5(돌린다)와 Δ2(입력을 공급한다)는
**둘 다 있어야 한 값이 나온다** — 어느 하나만으로는 여전히 0이다. 착수 순서는 **Δ2가 먼저**여야
한다(돌릴 것이 없는 러너를 먼저 배선하면 "돌렸는데 0"이라는 가장 나쁜 화면이 만들어진다).

### §8.7 반복 실수 — 계열 명명: **"측정기구는 도는데 분모가 0"**

v1 §6은 3회차까지를 `만들고 **X하지 않음**`(배선/적재/배포)으로, 본문 §6은 4회차를
`만들고 **실행하지 않음**`으로, `learning_path_module_gap_review_r2.md`는 9회차를
`경계를 넘을 때 흘림`으로 명명했다. **Δ2·Δ4는 넷 다 아니다.**

| 이번 형태 | 실체 |
|---|---|
| Δ2 | 장치도 있고 배선도 있고 테스트도 초록인데 **입력이 구조적으로 0** — 존재한 적 없는 필드를 읽는다 |
| Δ4 | 좌석도 있고 스키마도 있고 페이지 OR까지 있는데 **기본값이 축을 끈다** + 소비자가 자체 재구현 |

남길 원칙(**CLAUDE.md 등재 후보 — 이번 커밋에서 헌법은 고치지 않는다**. 학습경로 r2 선례):

> **"관측 장치의 분모가 0이면 그것은 측정 실패가 아니라 침묵이다."**
> 측정기구를 만들 때는 그 기구의 **입력이 실제로 존재하는 비율을 먼저 실측**하고, 그 비율을
> 기구 자신이 보고하게 한다. `not_derivable: 100%`는 화면에서 "측정했더니 문제없음"과 구분되지
> 않는다 — *분모 없는 0 금지*가 **분자** 쪽 규칙이라면 이것은 **분모** 쪽 규칙이다.
> 그리고 **기본값이 축을 끄는 좌석은 "opt-in"이 아니라 "상시 미작동"으로 회계한다** — opt-in은
> 켜는 주체가 실재할 때의 이름이다.

이 원칙은 기존 세 금기의 빈칸이다: *침묵 실패 금지* = 예외를 삼킴 / *정본화≠집행* = 계약이 서빙
경로에 없음 / *정직 표기의 경계 소실* = 필드가 경계에서 떨어짐 / **이번** = 전부 제자리에 있는데
**읽을 것이 없다**.

### §8.8 §정정 — 이 회수에서 실측으로 바로잡는 것

| 위치 | 기존 기술 | 실측 |
|---|---|---|
| 본문 §2 D2 잔여 ② | "얼마나 좁은지는 리포트를 돌려야 알 수 있다" | **코퍼스 grep으로 즉답** — `formal` 0/2,647·writer 0건(Δ2) |
| 본문 §3 D6 임계 축 1 | "검산 가능 시도 200건 이상" | D5만으로는 **영구 미달**(Δ2) |
| 본문 §4-⑨ | "`student_intent` writer는 여전히 0" | `PED-04` 착지로 **상환**(Δ1) |
| 본문 §3 D5 표 | 리포트 11개 | **12개**(Δ6) |
| v1 §1 기능 68 "부분점수 계산 → 점수 계산 로직 0" | — | `partial_credit` 실재(Δ5) |
| v1 §1 기능 69 "OCR 오류 자동 보정 → ✅ 더 엄격" | — | 칭찬 대상 오지정 — `needs_review` 축은 상시 False(Δ4) |

**v1 본문과 r2 본문 모두 무수정**이다. 어느 판정이 언제 무엇 때문에 바뀌었는지가 이 절의 기록
가치이며, 소급 수정하면 그것이 사라진다.

### §8.9 실행 — 이 회수 커밋이 하는 것 / 하지 않는 것

**하는 것**
1. **회수**: r2 문서(499줄) · `OPS-19` 태스크 · v1 배너 · `config.py` `ocr_recognizer_backend`
   stale 정정 · `CLAUDE.md` "trunk 부재를 미구현으로 단정 금지" 규칙 · `NLP-02` paths 정정 ·
   MEMORY 2026-08-04 항목 — **원본 그대로**(git 경유·내용 재작성 0).
2. **§8 신설** + 본문 인라인 `[→ §8-Δn]` 표시 5곳.
3. **신규 태스크 등재 3건**(Δ2·Δ3·Δ4) + **Δ5는 결정 축**이라 태스크 1건. 전건 `backlog.py add`
   CLI 경유(ID 손편집 0 · 번호 추론 금지 — HARN-10/15).

**하지 않는 것 (정직 회계)**
- **Δ1~Δ6의 구현 0** — 이 세션은 회수·재검증·등재까지다(시리즈 관례 · Kiki 결정 2026-08-11).
- **`src/` 신규 변경 0** — `config.py` 델타는 **회수분**이지 이 세션이 저술한 코드가 아니다.
  따라서 백엔드 테스트 스위트를 돌리지 않았다. 이는 "전체를 확인하지 못했다"가 아니라
  **"이 세션이 만든 회귀 대상이 없다"**이며, 회수분 자체는 PR #697에서 이미 검증된 것이다.
- **PR #697 처리** — 이 브랜치가 #697의 내용을 **포함**하므로 #697은 중복이 된다. 닫을지
  이 브랜치를 닫고 #697을 머지할지는 **Kiki 결정**이며 이 세션이 하지 않는다.
- **v1·r2 본문 수정 0** · `NLP-01`~`NLP-03` acceptance 수정 0(승계) ·
  `S4-10`·`S4-11`·`ARCH-11`·`ASM-02`·`MATH-05` 재설계 0(타 축 소유).
- **OCR 활성화** — v1 §5-① 유보 유지. 배포 경로 3축 전부 재확인했고 변화 없다
  (`Dockerfile:43` `[ocr]` 미설치 · `run_demo.ps1` `WHYMATH_OCR_*` 0건 · `config.py:1067`
  `ocr_enabled=False` · `S3-01` 파일럿 todo).

### §8.10 부록 — 재검증 실측 근거 (2026-08-11)

**Δ2 (코퍼스 전수)**
```
# 2,647건 중 formal 보유 0 / verify 블록 보유 2,647
python3 - <<'EOF'
import json, glob, collections
tot=cp=formal=0; vk=collections.Counter()
for f in glob.glob('data/corpus/problem_bank_*/problems.jsonl'):
    for line in open(f, encoding='utf-8'):
        if not line.strip(): continue
        d=json.loads(line); tot+=1
        c=d.get('conditions_parsed') or []
        if c:
            cp+=1
            if any(isinstance(x,dict) and x.get('formal') for x in c): formal+=1
        v=d.get('verify')
        if isinstance(v,dict): vk[tuple(sorted(v.keys()))]+=1
print(tot, cp, formal, vk.most_common(6))
EOF
grep -c '"formal"' data/corpus/problem_bank_*/problems.jsonl   # 전 파일 0
```
- `harness/attempt_grading_shadow_report.py:93-130 derive_verify_inputs`(파생 게이트)
- `l1/problem_bank/populate.py:214`(적재 소비 범위 자인)·`:296 data.pop("verify", None)`
- `whs/corpus_replay.py:104-112`(코퍼스 `verify` 소비 선례 — 대조군)
- `schema/problem.py:70-89 Condition`(`formal: str | None = None`) · `db/models/problem.py`(verify 컬럼 없음)

**Δ3 (CI 필터)**
- `.github/workflows/ci.yml:74`(backend 필터 — `data/notation_contract.json`·`data/render_contract.json` 2개만)·
  `:83`(mobile 필터 — `data/` 없음)·`:86`(web 필터)
- 소비자 양측: `tests/backend/l5/ocr/test_text_segmentation.py:25 _FIXTURE` ↔
  `src/mobile/test/segmentation_contract_test.dart:96 relPath`

**Δ4 (OCR 신뢰도 3중 임계)**
- `config.py:1130-1134 ocr_min_confidence`(`default=0.0` + "기본 0.0=필터 비활성" 자인)
- `l5/ocr/factory.py:87 review_threshold=settings.ocr_min_confidence`
- `l5/ocr/assemble.py:60`(`> 0.0` 가드)·`:91`(페이지 OR) · `schema/ocr.py:181`·`:249`·`:282`
- `api/coach.py:347 match_low_quality`(0.8 하드코딩) ·
  `src/mobile/lib/features/ocr/data/ocr_models.dart:69-71 hasLowConfidenceRegion`·`:110`·`:142`
- `src/mobile/lib/features/ocr/presentation/ocr_capture_screen.dart:211`·`:278`(`_RecheckCue` 발화점)

**Δ5 (partial_credit)**
- `l6/blueprint/assembly.py:526 partial_credit` · `l6/blueprint/__init__.py:34,40,50,57`(export)
- `api/me.py:155-159`(3심볼만 import) · `grep -rn "partial_credit" src/backend src/mobile` →
  정의·export·테스트 외 0건

**Δ6 (리포트 러너)**
- `find src/backend -name "*_report.py"` → 12건(신규 `harness/standard_attainment_report.py`)
- `grep -rn "_report" .github/workflows/ docker-compose*.yml scripts/ infra/` →
  `cost_report`(러너) · `test_concept_reach_report`(유닛 테스트) · `atom_orphan_report`·`qa_report`(리포트 CLI 아님)

**Δ1 (상환)**
- `api/_ocr_state.py`(`OcrUnavailableReason`·`OcrReachCounters`) · `app.py:82-91`(import)·`:428`(`ocr` 필드)·
  `:431`(`solution_segmentation` 필드)·`:455 _ocr_reach_body`
- `l4/turn_meta.py:203 classify_student_intent`·`:272`(회상 맵) ·
  `api/coach.py:146`(import)·`:1458`(컬럼 투영)·`:1687`(적재)·`:1964`·`:2277`(호출)
- `data/segmentation_contract.json` · `l5/ocr/text_segmentation.py` · `api/_segmentation_state.py`

**회수 경위**
- `git log --all --diff-filter=A -- 'docs/architecture/nlp_module*'` → `74eec19b`(2026-08-04) 발견
- `git branch -a --contains 74eec19b` → `remotes/origin/claude/whymath-nlp-design-my18a1`
- `git merge-base origin/main origin/claude/whymath-nlp-design-my18a1` → `e93d36bc`(공통 조상 **존재** —
  `math_engine`·`S4-09` 사례와 달리 패치 적용이 가능했다)
- `git diff --stat origin/main...origin/claude/whymath-nlp-design-my18a1` → 8파일 `+631/-4`
- PR #697 `state=open` · `merged=false` · `updated_at=2026-08-09`

---

## §8.11 인접 태스크 대조 — 회수 커밋 이후 main 착륙분 (2026-08-11 병합 시점)

> §8을 쓴 시점(`aacef1ea`)과 main 병합 시점 사이에 **main이 5커밋 전진**했고, 그중 세 자매편
> (`ai_recommendation_module_gap_review_r3.md` · `ai_tutor_module_gap_review_r2.md` ·
> `curriculum_module_gap_review_r2.md`)이 **NLP 축과 겹치는 태스크**를 등재했다.
> 이 절은 그 관계를 기록한다 — **기록이 없으면 두 번 구현된다**. 이번 세션이 발견한 병(§8.0)의
> 예방적 적용이다.

### ① Δ2를 **다른 세션이 독립 발견**했다 (교차 검증 · NLP-05 범위 축소)

`REC-05`(추천 r2 §2 G1)가 **같은 사실에 독립 도달**했다. 고립본
(`origin/claude/whymath-ai-recommendation-review-tv1f08` · `attempt_grading_shadow_report.py`
638줄 = main 412줄 + 226) 본문 인용:

> *"파생 게이트(`derive_verify_inputs`)는 코퍼스 2,647문항 중 **0건**만 통과한다(조건 보유 30건
> 전부 `formal` 결측) — 이 경로만으로는 attempt가 아무리 쌓여도 채점 가능성 관측이 영구히 0건이다."*

**수치가 이 문서 §8.2와 정확히 일치한다**(2,647 / 30 / 0). 두 세션이 서로를 모른 채 같은 결론에
도달했으므로 Δ2는 **교차 검증된 사실**이다. 다만 **처방이 다르다**:

| 축 | `REC-05`(고립·회수는 `REC-09`) | `NLP-05`(이 문서) |
|---|---|---|
| 목표 | 0을 **정직하게** 만든다 | 0을 **0이 아니게** 만든다 |
| 수단 | `classify_gradability` 4버킷(A 선택형 정확일치 / B 수치 단답 후보 / C 조건 파생 / unclassified) + `verifiable_zero_reason`("attempt 0행" ↔ "코퍼스 `formal` 결측" 구분) | 코퍼스 `verify` 블록(`answer_map`+`conditions`·**100% 보유**)이 L1 적재에서 버려지는 것을 해소 |
| 입력 | **DB `Problem` 필드만** — `choices`·`answer`·`question_format`·`answer_format`·`derive_verify_inputs` | 코퍼스 jsonl의 `verify` 블록 |
| `verify` 블록 참조 | **0건**(전수 grep 확인) | 이것이 전부 |

**즉 겹치지 않고 보완한다** — `REC-05`는 상한을 *측정*하고 `NLP-05`는 상한을 *올린다*.
그러나 **같은 파일을 고친다**(`harness/attempt_grading_shadow_report.py`). 따라서:

- **`NLP-05`는 `REC-09`(회수)에 의존한다.** 회수 전에 착수하면 226줄을 모르는 채로 같은 파일을
  고쳐 두 번째 고립을 만든다.
- **`NLP-05`는 `REC-05`의 산출물을 재구현하지 않는다** — 버킷 분류·`verifiable_zero_reason`·
  상한 리포트는 **승계**다. `NLP-05`가 더하는 것은 C버킷(또는 신설 4번째 버킷)의 **공급원**뿐이다.
- **§8.2가 제안한 "탈락 사유 분리 계수"는 `REC-05`가 이미 절반 이행했다**(0 원인 2분). `NLP-05`의
  acceptance ④는 그 위에 `verify` 블록 축을 얹는 것으로 좁힌다.

> **기록 의무**: 이 문서 §8.2는 "판정 뒤집기(최대 발견)"라 썼는데, **최초 발견은 아니다.**
> 추천 r2가 먼저였고 그 판정이 고립돼 보이지 않았을 뿐이다. §8.0이 말한 문제가 **이 문서 자신의
> 발견 주장에도 적용**된다 — 고립된 판단은 다음 세션에 재발견 비용으로 청구된다.

### ② Δ1의 "상환"을 정밀화한다 (`PED-19`와의 경계)

`PED-19`(AI 튜터 r2 §2 G1·G2)는 *"`student_intent` '질문'의 **첫 교수 결정 reader**"* 가 없다고
본다. §8.1 Δ1은 `PED-04` 착지로 **"상환"** 이라 적었다. **둘 다 맞고, 답한 질문이 다르다**:

| 축 | 상태 |
|---|---|
| **writer** (r2 §4-⑨가 제기한 것) | ✅ **상환 확정** — `turn_meta.py:203` → `coach.py:1964`·`:2277` → `:1687` 적재 |
| **가드 reader** | ✅ 실재 — `turn_meta.py:272`가 `_OVERRIDE_SUSPECT_INTENTS`(`질문`/`막힘표현`/`포기`)로 회전 판정의 연속열을 **끊는다**. 추론을 *무효화*하는 보수적 절단이다 |
| **분기 reader**(의도 값이 교수 결정을 *라우팅*) | ❌ **여전히 0** — `PED-19` 소유 |

**따라서 Δ1의 "상환"은 writer 축에 한정된다.** 의도가 실제 교수 행동을 바꾸는 축은 미해결이며
그 소유자는 `PED-19`다 — **이 문서는 그 축을 재설계하지 않는다**(중복 등재 금지).
v1 §1 기능 66 "개념 질문 분류 △"의 후속도 `PED-19`가 가져간다(AI 튜터 r2가 v1 ✅ 1건을 오판정으로
정정한 축과 같다).

### ③ `OPS-19`(회수) ↔ `OPS-34`(main 신규) — 인접·비중복

| 태스크 | 축 |
|---|---|
| `OPS-19`(이 문서 §3 D5·회수) | 리포트 **러너 실배선** — 12개 중 11개가 실행된 적 없다 |
| `OPS-34`(추천 r3 §3 D8·main) | `declared_unwired_audit._OFFLINE_REPORT` **면제의 수취인·만료 선언** — 면제는 있는데 "누가 언제 돌리는가"가 0건 |

**순서는 `OPS-34`가 먼저다.** 면제가 정당한지(=이 리포트는 CI가 아니라 사람이 돌리는 것이 맞는지)
먼저 정해야 `OPS-19`가 배선할 러너의 범위가 정해진다. 거꾸로 하면 면제 대상까지 CI에 넣는다.

### ④ §8.7 원칙 ↔ `PED-18` — 같은 계열의 다른 평면

`PED-18`(AI 튜터 r2 §3 D8)의 *"WH-1 primary가 작동한 비율 좌석 0 — 전 턴이 정적 템플릿으로
폴백해도 16종 지표가 전부 정상값을 낸다"* 는 §8.7이 명명한 **"측정기구는 도는데 분모가 0"** 과
같은 계열이다(정확히는 그 쌍둥이 — 이쪽은 *분모는 있는데 분자가 무엇을 세는지 모른다*).
`PED-18`은 튜터 평면, §8.2·§8.4는 채점·OCR 평면이다. **원칙은 공유하고 태스크는 분리한다.**

### ⑤ 같은 날 고립 3건 — 5회차가 아니라 계열이 되었다

§8.0은 이 문서의 고립을 "5회차"로 셌다. 병합 시점에 보면 **2026-08-11 하루에만 고립 회수가 3건**
이다 — 이 문서(NLP r2·7일) · 추천 r2와 `REC-05`~`REC-08`(7일·`REC-09`) · 수식엔진 r1(8일).
추천 r3는 여기에 *대장 평면*을 하나 더 밝혔다: **`done`+`artifacts` 보유인데 그 커밋이 main
조상이 아닌 태스크를 `backlog validate`가 green으로 통과시킨다.** 이 문서 §8.0이 "방어 장치 2개가
놓쳤다"고 적은 것에 **세 번째**를 더한다 — `validate`도 못 잡는다.

**이 문서가 새 태스크를 만들지 않는 이유**: 대장 평면의 해소는 추천 r3가 이미 소유했고
(`REC-09` + 그 문서 §7), 하네스 축은 `HARN-22`(main 신규·ID 제안 경합)가 인접하다.
여기서는 **NLP 축의 사실만** 기록한다.
