# 게임화(Gamification) 모듈 — 외부 EOS 틀 대조 **2차 재점검(r2)** (2026-08-04)

> **범위**: v1(`gamification_module_gap_review.md`, 2026-08-03)과 **동일한 외부 참고 문서**
> (『18. 게임화(Gamification)』 기능 75 레벨 · 76 경험치(XP) · 77 배지 · 78 도전과제(퀘스트) ·
> 79 학습 연속기록(Streak) — WhyMath 전용이 아닌 일반적 틀, Kiki 제공)을 **v1 이후 착지분이
> 만든 새 지형**과 다시 대조한 기록.
> **성격**: 처음부터의 재대조가 아니라 **델타 재점검**이다. v1의 판정 — 특히 §2 의도적
> 미채택 11건 — 은 전건 유효하므로 **승계하고 재판정하지 않는다**. 다루는 것은 ⑴ v1의 설계가
> 구현된 뒤 **남은 실공백**과 ⑵ v1 이후 변화로 **stale해진 칸**뿐이다.
> **v1 이후 상태**: v1이 설계한 4건이 모두 착지했다 — `PED-06`(done, PR #691) ·
> `ARCH-26`(done, PR #688) · D3 동기 정본 3곳 개정(착지 확인) · D4 페이퍼(태스크 없음).
> 그 사이 `MOB-08`(#694) · `MOB-09`(#695)가 모바일 의존 7종을 제거했다.
>
> **결론 3줄**:
> 1. **최대 갭 = 노출 계약이 서빙 경계에서 미집행**. `growth_evidence_exposure.py`가 스스로
>    **"이 함수가 유일한 노출 판정 경로가 되게 한다"**(:122)고 선언했는데, 학생 토큰으로 부를 수
>    있는 유일한 라우트 `GET /v1/me/harness-metrics`는 그 함수를 **호출하지 않고** 원시 11지표를
>    반환한다. `api/me.py:2412-2414`가 노출을 "클라이언트가 소비할 때의 몫"으로 넘기는데,
>    **전역 UI 불변식 #1**은 바로 그 클라에 판정을 두는 것을 금지한다 → **D5**.
> 2. **두 번째 갭 = 성장의 증거가 클라 메모리까지 도달했는데 렌더 0**. v1 §6 7회차 판정
>    ("호출하기로 결정한 적조차 없음")은 개념 진단 축에서 **정밀화돼야 한다** — 호출은 이미
>    매 문제 로드마다 일어나고 `DiagnosisState`에 담기며, 화면이 그 필드를 안 읽을 뿐이다.
>    네트워크 갭이 아니라 **렌더 갭** → **D6**.
> 3. **세 번째 갭 = 5원칙 원칙 4(복귀 지원)가 정본인데 현행이 역행**. 기능 79에서 유일하게
>    채택된 축인데, 온보딩이 매 실행마다 뜨고 마지막 대화 복원이 0이라 복귀 학생과 신규
>    학생이 같은 화면을 본다. 백로그에 관련 열린 태스크 **0건** → **D7**.
> 4. **v1 stale 4곳 정정** — `fl_chart`·Firebase 제거로 근거가 바뀐 칸 2개, 7회차 판정 정밀화,
>    그리고 **v1 자신의 acceptance 문구 느슨함**(①이 집행 없이도 충족 가능했다).

관련 정본: `gamification_module_gap_review.md`(v1 — 이 문서의 모체, 판정 근거의 원본) ·
`docs/design/ui/02_student_ui_master_plan.md:87-95`("성장의 증거" 5원칙 — D3 착지분) ·
`docs/design/ui/00_index.md:41`(전역 UI 불변식 #1 표현≠의미 · #2 반게임화) ·
`src/backend/whymath_backend/harness/growth_evidence_exposure.py`(노출 계약 정본 — `PED-06` 산출) ·
`operations_module_gap_review_r2.md`(동일 문서 재제출 → r2 전환 선례) ·
`MEMORY.md` 결정 로그(2026-08-03 v1 · 2026-08-03 `PED-06`·`ARCH-26` · 2026-08-04 본 문서).

---

## §0. 재점검 사유 — 왜 v1을 덮어쓰지 않고 r2를 새로 쓰는가

### ① 동일 문서 재제출임을 수치로 확정한다 (추론 아님)

제출 문서와 v1 §범위가 기술한 구성이 **세부 개수까지 일치**한다:

| 기능 | 제출 문서 세부 항목 수 | v1 §범위 기록 |
|---|---|---|
| 75 레벨 시스템 | 6 (학생 레벨·과목별·단원별 숙련도·AI Tutor 레벨·자동 승급·레벨별 특전) | 75:6 |
| 76 경험치(XP) | 12 (획득 8 + 추가기능 4) | 76:12 |
| 77 배지 | 14 (종류 10 + 관리 4) | 77:14 |
| 78 도전과제 | 12 (종류 7 + 보상 5) | 78:12 |
| 79 Streak | 11 (기능 7 + 보상 4) | 79:11 |
| **합계** | **55** | **55** |

연계 구조 7단(`문제풀이→XP→레벨→배지→퀘스트 해금→Streak→추가보상`)도 동일하다. 따라서
이것은 새 요구가 아니라 **재제출**이며, 새 판정이 아니라 **델타**가 답이다.

### ② v1을 in-place 수정하지 않는 이유

`operations_module_gap_review_r2.md` §0이 확립한 처리를 그대로 승계한다. v1은 이미 완료된
태스크 `PED-06`·`ARCH-26`의 `notes`가 **판정 근거로 지목하는 원본**이다
(`PED-06.notes`: "`gamification_module_gap_review.md` §3 D1" · `ARCH-26.notes`: "§3 D2").
완료된 태스크의 근거 문서를 소급 변조하면 "왜 그렇게 결정했는가"의 기록이 사라진다.
따라서 **v1은 그대로 두고, 정정은 이 문서 §4가 보유**한다.

### ③ 승계 선언 — 재판정하지 않는 것

v1 §2의 **의도적 미채택 11건**(XP 전체·학생 레벨·배지·퀘스트·연속일수 카운터·랭킹·코인·
카운트다운·보상형 알림·dead table 소생·`gamification_level` 확대)은 근거가 CLAUDE.md·정본
20+ 인용이고 그 근거가 하나도 바뀌지 않았다. **전건 승계하며 이 문서는 재판정하지 않는다.**
v1 §3 D4(`gamification_level` 페이퍼)·§4 정직한 공백 6종도 §5 갱신분 외에는 승계한다.

---

## §1. v1 판정의 변경분 — 바뀐 칸만

v1 §1의 전수 대조표(세부 55개)에서 **판정이 바뀐 칸은 3개**다. 나머지는 불변이다.

| 기능 | 세부 | v1 판정 | r2 판정 | 사유 |
|---|---|---|---|---|
| 79 | 연속 학습일수(`consecutive_active_days`) | ⚠️ → D2 | ✅ **해소** | `ARCH-26`이 writer 0을 기계 동결(`test_anti_gamification_governance.py:349-376`). 좌석은 남아 있으나 값이 흘러들면 red |
| 75 | 단원별 숙련도(`mastery_to_level`) | △ → D1 | ⚠️ → **D6** | `PED-06`은 *서버측 관측*만 다뤘다. 라벨의 학생 도달은 여전히 0이고, 원인이 "호출 없음"이 아니라 "렌더 없음"으로 **정밀화**됐다(§2 G2) |
| 79 | (대체) 재진입 경로 | △(발화조건 언급) | ⚠️ → **D7** | D3가 원칙 4를 정본화하면서 이 축이 "언급"에서 **정본 미이행**으로 성격이 바뀌었다 |

**게임화 5모듈 코드 0은 불변**이다 — `ARCH-26`이 이제 그것을 기계로 지킨다(Dart 8정규식 ·
Python 11어열 · `metric_name` 금지값 · writer 0 동결). v1이 "규정하고 기계화 안 함"으로
지목한 8회차 결함은 **이 축에서는 상환됐다**.

---

## §2. 잔여 갭 — 실측

### G1 — 노출 계약이 서빙 경계에서 미집행 (최대 갭 · 안전 축) → D5

`PED-06`이 만든 `harness/growth_evidence_exposure.py`는 계약으로서 **완비돼 있다**:

| 계약 요소 | 위치 | 내용 |
|---|---|---|
| 3계층 | `:44-54` | `STUDENT_VISIBLE` · `GUARDIAN_SUMMARY` · `INTERNAL_ONLY` |
| 내부 전용 2종 | `:62,64` | ②`diagnosis_agreement_rate`(시스템 품질) · ④`tokens_per_turn`(비용) |
| ⑧×R15 조합 제약 | `:115-150` | R15가 `GAMING_SUSPECT`면 `hint_depth_reached`를 `exposable_now=False` |
| `GAMING_SUSPECT` 은폐 | `:120-123` | 라벨 자체를 **반환값의 필드로 두지 않는다** |
| ⑥ 서술 변환 | `:81-93` | Brier 역방향 스칼라 → 3버킷 서술(원값 미반환) |
| 비교·서열 금지 | `:15-17` | 백분위·랭킹·평균대비 함수를 **의도적으로 두지 않음**(부재가 계약) |

그리고 이 모듈은 스스로 자기 지위를 선언한다 — `:120-123`:

> "…호출자가 `metrics.help_reduction_validated`를 직접 읽지 않도록 **이 함수가 유일한 노출
> 판정 경로가 되게 한다**."

**그런데 그 유일한 경로를 아무 라우트도 지나지 않는다.** 저장소 전체에서 이 모듈의 importer는
`harness/surrogate_baseline_report.py:39-41,206`(CLI 리포트)와 자기 테스트뿐이다.

학생이 실제로 닿을 수 있는 표면은 `GET /v1/me/harness-metrics`(`api/me.py:2380-2392`)이고,
게이트는 `ConsentedUser`(`:2387`) — 즉 **학생 본인 토큰으로 호출된다**. 반환은
`response_model=SurrogateMetrics`(`:2382`) 원시 11지표 그대로(`:2424-2426`)이며 여기엔
내부 전용 2종도, Brier 원 스칼라도, `help_reduction_validated`의 `GAMING_SUSPECT`도 들어 있다.
계약이 억제하기로 한 것이 **하나도 억제되지 않는다.**

`api/me.py:2412-2414`가 이를 자인한다:

> "응답 필드 자체는 이번 태스크로 변경하지 않는다(11지표 학생 노출 허용 여부는
> `harness/growth_evidence_exposure.py` 계약을 **클라이언트가 소비할 때의 몫** — 이
> 엔드포인트는 여전히 내부·집계 전용 원시 계측 표면이다)."

**이 위임이 정확한 결함이다.** 전역 UI 불변식 #1(`docs/design/ui/00_index.md:41` 1행)은
"수학 로직·정답·검증은 서버(독립 코어 L1-L4). 클라(Flutter·웹·admin)는 View Layer —
**수학 판정을 담지 않는다**"이다. 노출 판정은 정서 안전 판정이고 곧 판정이다. 계약이
**하필 그것을 가질 수 없다고 명시된 계층에 위임**됐다.

**형태 판정 — 8회차의 재발이되 주체가 다르다**: v1 §6이 8회차로 등재한 "규정하고 기계화
안 함"에서, 그때 규정 주체는 CLAUDE.md·정본이었다. 이번엔 **직전 슬라이스 자신**이다 —
계약을 만든 바로 그 태스크가 집행을 잇지 않았다. 자기가 만든 규범을 자기가 집행하지 않은
형태라 **더 짧은 시간에 재발**했다(v1 → 구현 → r2까지 1일).

**왜 통과했는가**(재발방지 관점): v1 D1 acceptance ①의 문구가 "노출 계약 **정본화**"였다.
정본화는 집행 없이도 충족된다. 문구가 결과를 정했다 — §4-④에 정정으로 등재한다.

### G2 — 성장의 증거가 클라 메모리까지 도달했는데 렌더 0 (신규 형태) → D6

v1 §6 7회차는 "클라가 `harness-metrics`를 호출하기로 **결정한 적조차 없다**"였다.
`harness-metrics` 축에서는 지금도 맞다. 그러나 **개념 진단 축에서는 판정이 정밀화돼야 한다** —
호출은 이미 일어나고 있다:

- `DiagnosisController.load()`는 문제 로드 1회마다 **3콜**을 한다 —
  `GET /v1/me/next-problem` → `GET /v1/problems/{id}` → `GET /v1/me/diagnosis/concepts`
  (`application/diagnosis_controller.dart:7-8,32,59`).
- 결과가 `DiagnosisState`에 **전량 담긴다**(`application/diagnosis_state.dart:14-23`):
  `nextProblem`(θ · standard_error · measurement_sufficient) + `diagnoses`(개념별
  `conceptName` · `bktMastery` · `irtTheta` · `irtMasteryProxy` · `responseCount` ·
  BKT↔IRT `agreement` 라벨 · `coaching` 트리거 — `data/problem_models.dart:63-91`).
- `problem_screen.dart`의 `_buildBody`는 `isLoading` · `error` · `noCandidate` · `problem`
  **4개만** 읽는다(`presentation/problem_screen.dart:60-83`). θ·표준오차·개념 진단 목록은
  **한 글자도 렌더되지 않는다**.
- `me_screen.dart:29-38`의 "학습 경로"·"진단 결과" 타일은 리터럴 `'준비 중'`(`:82`).

즉 **네트워크 갭이 아니라 렌더 갭**이다. 서버 신규 계산 0·신규 엔드포인트 0으로 착지 가능한
유일한 성장 증거 축이며, 5원칙 #1("보상이 아니라 증거")의 가장 값싼 최초 착지점이다.

**9회차 신규 형태**: 1~6회차는 "배선 부재", 7회차는 "결정 부재", 8회차는 "규정하고 기계화
안 함". 이번은 **"도달했는데 렌더 0"** — 자산이 클라 프로세스 메모리까지 왔고 결정도 배선도
끝났는데 마지막 한 겹(위젯)이 없다. 앞 회차들과 달리 **남은 거리가 가장 짧은데 가장 오래
방치된** 형태다.

### G3 — 5원칙 원칙 4(복귀 지원)가 정본인데 현행이 역행 → D7

D3가 `02_student_ui_master_plan.md:92-94`에 정본화한 원칙 4:

> "**연속성은 압박이 아니라 복귀 지원** — Streak의 핵심은 '돌아오기 쉽다'이지 '끊기면 잃는다'가
> 아니다. 연속 일수 카운터·Freeze·복구권은 미채택."

이것이 기능 79(Streak) 11개 세부 중 **유일하게 채택된 축**이다. 그런데 현행 구현은 반대다:

- **온보딩이 매 실행마다 노출된다** — `core/router.dart:96`이 `initialLocation`을
  온보딩으로 고정하고, `onboarding_screen.dart:12-14`가 자인한다: "온보딩 1회-노출 영속은
  후속(shared_preferences 미도입)이라 **현재는 매 진입마다 노출된다**".
- **마지막 대화 복원 0** — `dialogueId`는 인메모리 `ChatState`(`chat_state.dart:24`)에만 살고
  영속되지 않는다. `GET /v1/coach/sessions/{id}`는 클라 API에 **구현돼 있으나 호출처가 0**
  (`coach_api.dart:82` — 주석이 "턴 영속 확인용"이라 명시).
- `lib/` 전체에 "이어하기" 문자열 **0**. 영속 저장소는 인증 토큰용
  `flutter_secure_storage`(`core/token_store.dart:26-45`)뿐.

**결과**: 복귀 학생과 신규 학생이 **동일 화면**을 본다. "돌아오기 쉽다"의 반대다.
그리고 백로그 176건 전수에서 streak·retention·재진입·복귀·대시보드를 언급하는 **열린 태스크가
0건**이다 — 정본은 있는데 추적이 없다.

---

## §3. 정직한 공백 — 지금 하지 않는 것

v1 §4의 6종을 승계하고, r2에서 새로 확인된 2종을 더한다.

1. **`GUARDIAN_SUMMARY` 계층이 멤버십 0 · 소비자 0** — `_STATIC_TIER`(`:60-72`)가 이 계층에
   배정한 지표가 **하나도 없다**. 모듈 docstring(`:20-22`)이 "현재 범위에서는
   `STUDENT_VISIBLE`과 동일 소속을 상속"이라고 정직하게 밝히고 **과공학 방지를 이유로 명시**
   했으므로 이는 결함이 아니라 **의도된 미정의**다. 보호자 리포트 표면 자체가 `api/`에 0건
   (법정대리인 *동의* 절차만 존재 — `api/users.py:9`)이라 채울 소비자도 없다. 계층을 지금
   벌리지 않는다. **발화조건**: 보호자 대시보드가 별도 태스크로 착수될 때.
2. **확신도 수집 UI 0 재확인** — v1 §4-②를 승계한다. `lib/` 전체에서 학생 자기보고 확신도
   입력 위젯 0(`confidence` 히트는 전부 OCR·오개념 매칭의 기계 신뢰도). 따라서 ⑥ Brier는
   구조적으로 `NO_DATA`이고, D5가 만드는 서술도 당분간 "아직 예측 확신도 데이터가 없어요."
   (`growth_evidence_exposure.py:87`) 한 줄이다. **이것을 D5의 실패로 읽지 않는다** — 계약이
   무데이터를 정직하게 말하는 것이 설계 의도다.
3. **알림 기반 복귀 유도** — v1 §4-④는 "Firebase는 pubspec 선언만(초기화 0)"이었으나
   `MOB-08`(#694)이 **firebase 2종을 제거**했다. 전제가 사라졌으므로 D7은 **알림을 쓰지 않는
   복귀 지원**(온보딩 영속·이어하기)만 다룬다. §5에서 발화조건을 갱신한다.
4. v1 §4의 나머지(①`tone_filter` 라이브 미배선 · ③재진입 UX 화면설계 · ⑤`gamification_level`
   코드 실체화 · ⑥PRD 동기 섹션 신설)는 **그대로 승계**한다. 단 ③은 D7이 최소 착지분을
   가져가므로 "화면 설계 전반"만 공백으로 남는다.

---

## §4. 정정 — v1 stale 4곳 (v1을 수정하지 않고 여기 기록)

| # | v1 기술 | r2 실측 | 처리 |
|---|---|---|---|
| ① | §0-② · 부록: `fl_chart: ^0.69.0`은 pubspec 선언만 있고 사용처 0 | **`MOB-09`(#695)가 제거**했다. 남은 것은 `pubspec.yaml:49`의 주석("기능 착수 시 재도입")뿐이고, 재도입은 `pubspec_dependency_usage_governance_test.dart:134` 게이트가 **선언↔사용 동시 착지**를 강제한다 | D6 acceptance에 반영 — v0은 차트 없이 텍스트·라벨로 착지 |
| ② | §4-④ · §5-④: "Firebase는 pubspec 선언만(초기화 0)"이라 복귀 알림은 재료가 없다 | **`MOB-08`(#694)가 firebase 2종을 제거**했다. 발화조건이 충족 쪽이 아니라 **후퇴** 쪽으로 움직였다(전제 소멸) | §5-④ 갱신 |
| ③ | §6 7회차: "클라가 호출하기로 **결정한 적조차 없음**" | `harness-metrics` 축은 유효하나, **개념 진단 축은 호출이 이미 있고 렌더가 0**이다(G2). 두 축을 한 판정으로 묶으면 D6이 "엔드포인트 배선"으로 오독된다 | **9회차 "도달했는데 렌더 0"** 신규 등재(§2 G2) |
| ④ | §3 D1 acceptance ①: "학생 대면 노출 계약 **정본화**" | 정본화는 **집행 없이도 충족된다**. 실제로 `PED-06`은 계약 모듈을 만들고 acceptance를 정당하게 통과했으나 서빙 경계는 그대로 남았다(G1) | **규칙화**: 노출·안전 계약의 acceptance는 "정본화"와 "**집행 지점 명시**"를 별도 항으로 쪼갠다. D5 acceptance가 이 형식을 처음 적용한다 |

**오탐 방지 — 정정 대상이 아닌 것**: v1 §0-②의 "Flutter가 실제로 호출하는 `/v1/` 엔드포인트는
**13종**"은 **여전히 정확하다**. `/v1/verify-solution`이
`features/verify/data/verify_api.dart:30`에 살아 있다(전수 재확인). 의존 7종 제거는 *패키지*
제거이지 *엔드포인트* 제거가 아니다.

---

## §5. 유보 항목의 발화 조건 (v1 §5 갱신)

v1 §5의 6건 중 ②③④가 움직였다. ①⑤⑥은 불변 승계.

| # | 유보 항목 | 발화 트리거 (r2 갱신) |
|---|---|---|
| ② | 확신도 수집 UI | **불변** — `REC-01` 도달 리포트에서 attempt 제출이 실제로 관측된 뒤. 단 D5가 착지하면 "확신도가 없어 ⑥이 서술 불가"가 **학생 화면에서 보이므로** 수요가 가시화된다 |
| ③ | 재진입 UX 화면 | **부분 발화** — D7이 최소 착지(온보딩 영속·이어하기)를 가져간다. 잔여(경로 복원·마지막 목표 복원 화면)는 D6의 `/me` 타일 해소 이후 |
| ④ | 복귀 유도 알림 | **후퇴** — `MOB-08`로 firebase가 제거돼 전제가 사라졌다. FCM 실기능 태스크가 별도로 서고 `pubspec` 게이트를 통과해 재도입될 때로 미룬다 |
| ⑤ | `gamification_level` 코드 실체화 | **불변**(v1 §5-⑤ 승계) — 자유학기제 모드가 L6 게이팅에 실배선될 때. 그 시점에 `ARCH-26` 게이트 오탐 회피 경로를 함께 설계해야 한다는 조건도 승계 |

---

## §6. 잔여 갭 설계 (D5~D7)

번호는 v1의 D1~D4에 이어 붙인다(충돌 회피).

### D5 — 성장 증거 노출 계약의 서빙 경계 집행 (G1)

**핵심 판단**: 계약을 다시 만들지 않는다. **이미 완비된 계약에 소비자를 붙이는 일**이다
(`NLP-01`·`PED-06`의 "활성화가 아니라 가시화" 계열 — 이번엔 "정본화가 아니라 집행").

**채택 형태(Kiki 확정)**: 기존 `/harness-metrics`를 고치는 것이 아니라 **학생 안전
엔드포인트를 신설**한다. 이유: `/harness-metrics`는 ops·리포트가 원시값으로 소비하는 표면이라
응답을 축소하면 그 경로가 깨지고, "내부 집계"와 "학생 노출"이 한 라우트에 겹쳐 다시 모호해진다.

**정합 설계**(신규 테이블 0 · 마이그레이션 0 · 신규 지표 계산 0):
- **①** `GET /v1/me/growth-evidence` 신설. `classify_metric_exposure` ·
  `narrate_calibration_brier`(`growth_evidence_exposure.py:115,81`)를 **경유해서만** 응답을
  만든다. 계약 로직 재구현 금지 — 재구현하는 순간 "유일한 판정 경로"(`:122`)가 깨진다.
- **②** 내부 전용 2종(②`diagnosis_agreement_rate`·④`tokens_per_turn`)은 런타임 필터가 아니라
  **응답 스키마에 필드 자체를 두지 않는다**(구조적 배제 — 필터는 실수로 꺼지지만 부재는 안 꺼진다).
- **③** `help_reduction_validated`/`GAMING_SUSPECT`는 **어떤 형태로도 필드가 되지 않는다**.
  ⑧ `hint_depth_reached`는 `exposable_now=False`면 값 대신 `suppressed_reason` 서술만 싣는다.
- **④** ⑥ Brier는 원 스칼라 대신 3버킷 서술만(`narrate_calibration_brier`).
- **⑤** **비교·서열·순위 파생 0** — 백분위·평균대비·타 학생 필드를 두지 않는다(5원칙 #2 ·
  계약 모듈 `:15-17`의 "부재가 계약"을 API 층에서도 유지).
- **⑥** 도달 관측 — `api/_growth_evidence_state.py`의 카운터를 신 라우트에도 배선해
  `PED-06`의 3상태 리포트(`surrogate_baseline_report.py:146-181`)가 계속 성립하게 한다.
  두 라우트를 **구분해 센다**(원시 표면 호출과 학생 표면 호출이 섞이면 도달 판정이 위장된다).
- **⑦** **거버넌스 테스트** — 학생 대면 라우트의 응답 모델에 금지 필드명이 재등장하면 red.
  `test_anti_gamification_governance.py`의 기법 답습(경로 스코프 · 무력화 하한 assert ·
  금지 필드 주입 시 실제로 red가 나는 **변별력 양방향 실측**).

**acceptance는 "정본화"와 "집행 지점"을 분리 기술한다**(§4-④ 규칙의 첫 적용).

**범위 밖 동결**: `/harness-metrics` 응답 변경(원시 표면 유지) · 모바일 화면 신설(D6 소관) ·
보호자 대시보드(§3-①) · 확신도 수집 UI(§5-②).

### D6 — 이미 도달한 진단의 렌더 착지 (G2)

**핵심 판단**: 서버 신규 계산 0. 이미 클라 메모리에 있는 것을 **보여주기만** 한다.

- **①** 서버 — `GET /v1/me/diagnosis/concepts` 응답에 **숙달 상태 라벨** 필드 추가.
  `mastery_to_level`(`l4/lthc/adapt.py:127` — "초보"/"발전 중"/"숙달") **재사용**.
  **클라가 임계값(0.4·0.8)을 계산하면 불변식 #1 위반**이므로 라벨은 반드시 서버 산출이다.
- **②** 클라 — `me_screen.dart:34-38` "진단 결과" 타일의 placeholder 해소.
  `DiagnosisState.diagnoses`(이미 적재됨)를 개념명 + 상태 라벨로 렌더.
- **③** **원시 BKT 확률·θ 숫자 노출 금지** — 상태 라벨과 자기 대비 서술만. 숫자는 서열
  신호로 읽히고(5원칙 #2), θ는 학생에게 의미가 전달되지 않는다.
- **④** 정렬을 **순위로 제시하지 않는다** — "약한 개념부터"는 학습 순서이지 등수가 아니므로
  번호·등급·상위 N% 표기를 붙이지 않는다.
- **⑤** `anti_gamification_governance_test.dart`(금지 8정규식) 통과 필수.
- **⑥** **차트 금지(v0)** — `fl_chart`는 `MOB-09`로 제거됐고 재도입은 선언↔사용 동시 착지를
  요구한다(§4-①). v0은 텍스트·라벨로 착지하고 차트는 별도 슬라이스.

**범위 밖 동결**: "학습 경로" 타일(`PATH-02` 소관 — 정렬 근거 정직 표기가 선행) ·
`/harness-metrics` 또는 `/growth-evidence` 클라 배선(D5 선행) · `problem_screen` 재설계.

### D7 — 복귀 지원 최소 착지 (G3 · 기능 79의 유일 채택 축)

- **①** 온보딩 1회 노출 영속 — `router.dart:96` `initialLocation` 재설계 + 영속 저장소 도입.
  `onboarding_screen.dart:12-14`가 자인한 "후속"을 회수한다.
- **②** 마지막 대화 이어하기 — `dialogueId` 영속 + 기존
  `GET /v1/coach/sessions/{id}`(`coach_api.dart:82`, 현재 호출처 0)로 재수화.
- **③** **금지 명문화**(v1 §2-⑤ 승계) — 연속 일수 카운터 · Streak Freeze · 복구권 · 달력 ·
  연속 목표 설정 · 단계별 보상. 채택하는 것은 **"끊긴 것을 세지 않는 재진입"뿐**이다.
  화면에 "며칠 만이에요" 류의 공백 환기 문구를 두지 않는다(압박 = 원칙 4 위반).
- **④** 저장소 선택 시 `MOB-08` 게이트 준수 — 의존 선언과 사용이 **같은 슬라이스**에 착지.
- **⑤** 알림 미사용(§3-③ — firebase 제거로 전제 소멸).

### 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| `PED-08-growth-evidence-serving-contract` | D5 — 학생 안전 엔드포인트 + 계약 집행 게이트 | S3 | 2 | 계약이 스스로 "유일 판정 경로"를 선언했으나 라우트 소비 0(§2 G1) |
| `MOB-10-diagnosis-evidence-render` | D6 — 이미 도달한 진단의 렌더 착지 | S3 | 2 | 클라 메모리 적재 완료·렌더 0(§2 G2) |
| `MOB-11-return-support-minimal` | D7 — 복귀 지원 최소 착지 | S3 | 3 | 5원칙 원칙 4 정본 미이행·열린 태스크 0건(§2 G3) |

태스크는 전건 `backlog.py add` CLI 경유로 등재했다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격
양쪽 검사 — HARN-10). `--path` 선언으로 겹침 검사를 켰다.

**중복 소유권 회피 실측**(등재 전 열린 태스크 전수 확인):
`S3-16`이 `focus_score`/`engagement_score`를, `PATH-02`가 학습 경로 정렬 근거를,
`ASM-02`가 등급·백분위 노출 정책을, `REC-01`이 attempt 입력 루프를 이미 소유한다.
D5~D7은 이들과 경계가 겹치지 않는다 — D5는 *대리지표 11종의 노출 판정*, D6은 *개념 진단
렌더*, D7은 *재진입*이다.

---

## §7. 반복 실수 — 9회차 등재

v1 §6이 8회차까지 채웠다. r2에서 **9회차**가 나온다.

| 회차 | 사례 | 형태 |
|---|---|---|
| 1~6 | (v1 승계) | **배선 부재** |
| 7 | 성장 지표 11종을 클라가 호출하기로 결정한 적 없음 | **결정 부재** |
| 8 | 반게임화 불변식 20+ 인용 · 집행 테스트 0 | **규정하고 기계화 안 함** |
| **9** | 진단 데이터가 클라 메모리까지 왔는데 위젯이 안 읽음(D6) | **도달했는데 렌더 0** |

9회차는 앞 회차 중 **남은 거리가 가장 짧다** — 서버도 API도 클라 호출도 상태 적재도 끝났고
위젯 한 겹이 없다. 그런데 가장 오래 방치됐다. 이유는 "누가 봐도 남은 일이 큰" 갭(엔드포인트
신설·파이프라인)과 달리, **완료율이 높은 갭일수록 완료로 착시된다**는 데 있다. `me_screen`이
`'준비 중'`을 성실히 표시하고 있어서 더 그렇다 — 정직한 placeholder가 역설적으로 갭을 가린다.

**그리고 G1은 8회차의 재발이되 주체가 바뀐 변종이다** — 규정 주체가 CLAUDE.md(외부 규범)가
아니라 **직전 슬라이스 자신**(자기가 만든 계약)이었다. 자기 규범의 자기 미집행은 외부 규범
미집행보다 빨리 재발한다(v1 → 구현 → r2까지 **1일**). 계약 모듈을 만드는 태스크는
acceptance에 **집행 지점**을 반드시 별항으로 쓴다(§4-④ 규칙).

---

## 부록 — 실측 근거 (2026-08-04 실측)

**노출 계약 미집행(G1/D5)**
- `harness/growth_evidence_exposure.py:44-54`(3계층) · `:60-72`(`_STATIC_TIER`) ·
  `:62,64`(내부 전용 2종) · `:81-93`(Brier 서술) · `:115-150`(⑧×R15 조합 제약) ·
  `:120-123`("이 함수가 유일한 노출 판정 경로") · `:15-17`(비교·서열 함수 부재가 계약) ·
  `:20-22`(GUARDIAN_SUMMARY 상속 — 과공학 방지 명시)
- importer 전수: `harness/surrogate_baseline_report.py:39-41,206` + 자기 테스트뿐
- `api/me.py:2380-2392`(`GET /harness-metrics`·`ConsentedUser`·`response_model=SurrogateMetrics`) ·
  `:2412-2414`(노출을 "클라이언트가 소비할 때의 몫"으로 위임하는 자인) · `:2424-2426`(원시 반환)
- `harness/wh1_evaluation.py:230`(`GAMING_SUSPECT`) · `:288`(`SurrogateMetrics`)
- `docs/design/ui/00_index.md:41` 전역 UI 불변식 #1(클라는 판정을 담지 않는다)
- `api/_growth_evidence_state.py:36-55`(요청 카운터) · `app.py:582`(설치) · `:693,713,739`(/health/ready)

**렌더 0(G2/D6)**
- `features/problems/application/diagnosis_controller.dart:7-8,32,59`(3콜 흐름)
- `features/problems/application/diagnosis_state.dart:14-23`(nextProblem·diagnoses 적재)
- `features/problems/data/problem_models.dart:63-91`(`ConceptDiagnosisItem` 9필드)
- `features/problems/presentation/problem_screen.dart:60-83`(state 4개만 읽음 — 진단 전량 미렌더)
- `features/profile/presentation/me_screen.dart:29-38`(학습 경로·진단 결과 타일) · `:82`(`'준비 중'`)
- `l4/lthc/adapt.py:127-143`(`mastery_to_level` 3라벨·임계 0.4/0.8)
- `src/mobile/pubspec.yaml:49`(fl_chart 제거 주석) ·
  `test/pubspec_dependency_usage_governance_test.dart:134`(선언↔사용 게이트)

**복귀 지원 역행(G3/D7)**
- `core/router.dart:96`(`initialLocation: AppRoutes.onboardingPath`)
- `features/onboarding/presentation/onboarding_screen.dart:12-14`("매 진입마다 노출" 자인)
- `features/chat/application/chat_state.dart:24`(dialogueId 인메모리) ·
  `features/chat/data/coach_api.dart:82`(`GET /coach/sessions/{id}` 호출처 0)
- `core/token_store.dart:26-45`(영속은 인증 토큰뿐) · `lib/` "이어하기" 0건
- `docs/design/ui/02_student_ui_master_plan.md:92-94`(원칙 4 정본)
- 백로그 176건 전수 — streak·retention·재진입·대시보드 열린 태스크 0건

**v1 착지 확인**
- `backlog/tasks/PED-06-growth-evidence-reach-observability.yaml`(status: done · artifacts 14a0b46b)
- `backlog/tasks/ARCH-26-anti-gamification-source-governance-gate.yaml`(status: done · artifacts 672be224)
- `docs/design/ui/02_student_ui_master_plan.md:87-95`(D3 5원칙 착지)
- 커밋 `f26518a9`(v1 #666) · `89602578`(PED-06 #691) · `4bc20954`(ARCH-26 #688) ·
  `b0ad24a6`(MOB-08 #694) · `de446ec3`(MOB-09 #695)
- `tests/backend/l1/test_anti_gamification_governance.py:349-376`(`consecutive_active_days` writer 0 동결)
- `src/mobile/test/governance/anti_gamification_governance_test.dart:29-38`(금지 8정규식)
- `features/verify/data/verify_api.dart:30`(§4 오탐 방지 — 13종 카운트 유효)
