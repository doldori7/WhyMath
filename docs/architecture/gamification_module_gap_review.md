# 게임화(Gamification) 모듈 — 외부 EOS 틀 대조 갭 점검·설계 (2026-08-03)

> **범위**: 외부 참고 문서 『18. 게임화(Gamification)』(기능 75 레벨 시스템 · 76 경험치(XP) ·
> 77 배지 · 78 도전과제(퀘스트) · 79 학습 연속기록(Streak), 세부 기능 55개[75:6·76:12·77:14·
> 78:12·79:11] + 연계 구조 7단[문제풀이→XP→레벨→배지→퀘스트 해금→Streak→추가보상] —
> **WhyMath 전용이 아닌 일반적인 EOS 틀**, Kiki 제공)을 현 코드베이스와 대조해 빠진 부분을
> 점검하고, 진짜 갭을 WhyMath 불변식(반게임화 · 정서 안전 · 표현≠의미 · dead code 금지 ·
> 침묵 실패 금지 · 측정 없는 도입 없음 · 거부 우회 금지) 안에서 설계한 기록.
> **형식**: `ai_recommendation_module_gap_review.md`(같은 EOS 틀 시리즈 기능 80~83, 2026-08-01)
> 답습 — 시리즈 **11번째 자매편**.
> **결론**: 착수 가설이 **두 번 뒤집혔다**. ① "게임화가 빠졌다"가 아니라 게임화는 **헌법상
> 금기**(`CLAUDE.md:33/106`)이며 5모듈 전부 코드 0 — 이건 미구현이 아니라 결정이다. ② 그런데
> **더 큰 반전** — 금기의 반대편인 "성장의 증거"(대리지표 11종)는 이미 서버에서 계산되는데
> 학생 화면 도달이 **0회**다. 진짜 갭 2건을 설계(D1·D2, 각 태스크 1건)하고, 3번째 항목(동기
> 정본)은 새 태스크 대신 **기존 정본 3곳 직접 개정**으로 착지시켰다(시리즈 §정정 관례 승계).
> 의도적 미채택 11건 · 정직한 공백 6종 · 유보 발화조건 6건. 정본 stale 5곳을 실측으로 정정한다.

관련 정본: `05_interaction.md`(§2 정서 안전 UI) · `06_application_modes.md`(`gamification_level`) ·
`07_community.md`(랭킹 금지·과장된 칭찬 금지) · `02_learner_model.md`(정서 신호 v0 제외) ·
`04a_wh1_tutoring_harness.md`(§8.4 대리지표 11종·커버리지 맵) · `docs/design/ui/00_index.md`
(전역 UI 불변식 #2 반게임화) · `ai_tutor_module_gap_review.md`(§2-② 정서 신호 노출 경계·§2-③
게임화 선행 판결 승계) · `ai_recommendation_module_gap_review.md`(REC-01 입력 루프·§정정 관례) ·
`backlog/tasks/S3-16-behavior-telemetry-writers.yaml`(죽은 좌석 소유권 승계) ·
`src/mobile/test/governance/no_math_logic_governance_test.dart`(소스 스캔 게이트 선례) ·
`MEMORY.md` 결정 로그(2026-08-03).

---

## §0. 두 가지 전제 정리

### ① "게임화가 없다"가 아니다 — 게임화는 코드 0이되 그것은 헌법상 결정이다

전형적 게임화(XP·포인트·레벨업·배지·업적·퀘스트·코인·리더보드)는 코드·DB·API·Flutter
**어디에도 없다**. `NLP-01`·`VIZ-01` 같은 "만들었는데 배선 안 됨"과 달리, 이건 **20곳 이상에서
반복 인용되는 정체성 금기**의 결과다.

| 위치 | 내용 |
|---|---|
| `CLAUDE.md:33` | `❌ 무자비한 게임화·중독성 설계` |
| `CLAUDE.md:106` | `❌ 학습 시간·정답률만으로 우열을 매기는 게임화 금지` |
| `docs/design/ui/00_index.md:41` | 전역 UI 불변식 #2 — "정답률 랭킹·스트릭·카운트다운·보상 연출 금지. 학습 경로 시각화는 허용" |
| `docs/architecture/05_interaction.md:31-34` | "게이미피케이션 ❌ (정답률 랭킹·스트릭 금지) / 학습 경로 시각화 ✅" |
| `.claude/agents/flutter-engineer.md:294-301` | "게이미피케이션 금지" 전용 섹션 — ❌ 정답률 랭킹·❌ 연속 정답 스트릭(도파민 유발)·❌ 빨간 카운트다운 / **✅ 학습 경로 시각화(어디 와있는지)·✅ 오개념 해소 마커(성장 시각화)** |
| `.claude/agents/content-curator.md:193` | `❌ "최고 풀이" 랭킹 (경쟁 강화)` |
| `docs/architecture/07_community.md:14,29,53,57` | 다중 풀이 갤러리·학부모 보고서 "랭킹·경쟁 금지" · "❌ 과장된 칭찬" |
| Flutter 화면 상단 주석 5개 | `app_shell.dart:7`·`home_screen.dart:7`·`me_screen.dart:8`·`ocr_capture_screen.dart:7`·`onboarding_screen.dart:9` — "절대 금기(정서 안전): 배지·스트릭·카운트다운·보상 연출·랭킹을 두지 않는다" |
| `docs/design/ui/06_design_system.md:75` | "게이미피케이션 금지 — 랭킹·스트릭·카운트다운·보상 연출 없음" |
| `docs/architecture/03c_content_strategy_cache.md:74-75` | `GAME`(게임형) 콘텐츠 전략 **초기 제외** |
| `ai_tutor_module_gap_review.md:178-179` | §2-③ **이미 한 번 판결됨** — "학습습관 게임화(스트릭·랭킹·학습시간 리더보드·푸시 압박) + dead table 5종 소생" 불채택. 본 문서는 이 판결을 **승계**하며 재판정하지 않는다 |

**진짜 공백은 "게임화를 채우자"가 아니라 "그럼 무엇으로 동기를 지탱하는가"의 설계 정본이
0이라는 것**이다. `docs/strategy/risks.md:119-121`이 D7 retention ≥ 30%를 **최우선 검증 가설**로
지정했는데, 그것을 지탱할 설계는 `docs/design/ui/02_student_ui_master_plan.md:81-83`의
"목표→성취→다음 목표" **한 문단**뿐이다. PRD v1.2·ROADMAP·`dev_constitution.md` 전부 동기·
게임화 섹션이 **0건**이다(전수 검색 확인).

### ② 더 큰 반전 — "성장의 증거"는 이미 계산되는데 학생에게 0회 도달한다

`compute_wh1_surrogate_metrics`(`harness/wh1_evaluation.py:983`)가 대리지표 11종을 계산해
`GET /v1/me/harness-metrics`(`api/me.py:2190`)로 노출한다:

| 축 | 지표 | 학생 대면 성격 |
|---|---|---|
| ① verify 통과율 | 검산결과 미적발 비율 | 시스템(부호가 반직관) |
| ② 진단정확도 | 오프라인 라벨 프로브 recall | 시스템(전 user 동일값) |
| ③ 세션 완주율 | `LearningSession` 기반 | **구조적 불가**(아래) |
| ④ 턴당 토큰 | 비용 대리 | 시스템(비용 지표) |
| ⑤ 도움 감소 곡선 | 힌트 의존 기울기 | **성장 증거 후보** |
| ⑥ 보정 점수(Brier) | 확신도 vs 정오답 | **성장 증거 후보**(입력 UI 없음·아래) |
| ⑦ 전이 점수(근사) | 시그니처 패턴 초견 정답률 | 성장 증거 후보(근사) |
| R15 결합판정 | `help_reduction_validated`(GENUINE_IMPROVEMENT/**GAMING_SUSPECT**) | **낙인 위험** |
| ⑧ 답 미루기 도달 깊이 | 힌트 레벨 평균 | 성장 증거 후보(R15 동반 필수) |
| ⑨ BKT 숙달 증가율 | 개념별 숙달 첫→마지막 차 | **성장 증거 핵심** |
| ⑩ 오개념 해소율 | `MisconceptionHypothesisRecord` 비활성 비율 | **성장 증거 핵심** |
| ⑪ 스스로 풀이 도달율 | `Dialogue.resolution` | **성장 증거 핵심** |

`/me/mastery-history`·`/ability`·`/diagnosis/summary`·`/learning-path`도 전부 실재한다 —
`api/me.py:1247`의 주석이 소비자를 **이름으로 못 박는다**: `GET /v1/me/diagnosis/summary
(진단 집계 — 대시보드 헤더)`. **그런데 그 대시보드가 만들어진 적이 없다.**

Flutter가 실제로 호출하는 `/v1/` 엔드포인트는 **13종**뿐이고, 위 어느 것도 없다:
`/v1/auth/$provider/callback` · `/v1/coach` · `/v1/coach/sessions` ·
`/v1/coach/sessions/$dialogueId` · `/v1/coach/sessions/$dialogueId/turns` · `/v1/interactions` ·
`/v1/me/diagnosis/concepts` · `/v1/me/next-problem` · `/v1/ocr` · `/v1/problems/$problemId` ·
`/v1/scenes/weak-concept` · `/v1/users/me` · `/v1/verify-solution`.

`go_router` 4탭 셸(`core/shell/app_shell.dart`) 중 `/home`·`/explore`·`/me` 3개는 전부 "준비 중"
placeholder다(`_PlaceholderTile` × 3 — "학습 경로"/"진단 결과"/"설정"). `fl_chart: ^0.69.0`은
pubspec 선언만 있고 `lib/`·`test/` 사용처 **0건**. `l4/lthc/adapt.py:127` `mastery_to_level`의
숙달 라벨("초보"/"발전 중"/"숙달")도 `MasteryLevel` 심볼이 `src/mobile/lib/` 전체에 **0건**이다.

즉 **WhyMath판 "게임화"는 "성장의 증거(evidence of growth)"이고, 그것은 이미 계산되고 있으나
학생은 한 번도 본 적이 없다.**

---

## §1. 기능 75~79 전수 대조 (세부 55개)

판정 기호: ✅ 충족·초과 / △ 부분(부품은 있는데 *배선·정본* 없음) / ⚠️ 진짜 갭 → D /
⏸ 기존 태스크 승계 / 🚫 의도적 미채택 → §2

### 기능 75 — 레벨 시스템

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 학생 레벨(1~1000) | 없음. 서열 스칼라 자체가 금기 | 🚫 |
| 과목별 레벨 | 없음(과목 확장 축은 있으나 레벨 아님) | 🚫 |
| 단원별 숙련도(Level) | **있음** — `mastery_to_level`(`l4/lthc/adapt.py:127`) BKT 숙달→"초보"/"발전 중"/"숙달" 3라벨. 서열이 아니라 *상태 추정*. Flutter 소비 0 | △ → D1 |
| AI Tutor 레벨 | 없음. 코치는 단일 정책(교수법 선택은 있으나 "레벨"이 아님) | 🚫 |
| 학습 단계 자동 승급 | Polya 단계 전이(`should_advance`)로 대체 — 서열 승급이 아니라 *교수 전이* | ✅(다른 형태로 충족) |
| 레벨별 특전 제공 | 없음. 특전=보상 연출이라 금기 | 🚫 |

### 기능 76 — 경험치(XP)

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 문제풀이/오답수정/개념학습완료/질문/복습완료/연속학습/친구도움/프로젝트완료 XP | 전부 없음. 심볼 0 | 🚫(전건) |
| XP 배율 이벤트·일일 제한·보너스·주간 통계 | 전부 없음 | 🚫(전건) |
| (대체) 보정 피드백 | `calibration_coaching`(`l4/calibration_coaching.py:32`) — 확신도×정오답 → 메타인지 코칭. **즉시 피드백의 자리를 대신함** | △ → ⏸(REC-01 승계) |

### 기능 77 — 배지 시스템

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 첫 학습·연속학습·개념 마스터·계산왕·증명 전문가·문제 해결사·탐구왕·AI 활용왕·협업왕·이벤트 배지 | 전부 없음 | 🚫(전건) |
| 희귀도·시즌 배지·숨겨진 배지·컬렉션 | 전부 없음 | 🚫(전건) |
| (동음이의 주의) `_SocraticBadge` UI 칩 | `chat_message.dart:26,41`·`chat_screen.dart:415` — 소크라테스 **발화 카테고리 라벨**이지 보상 배지가 아님 | 해당없음(§2 아님·D2 allowlist 대상) |

### 기능 78 — 도전 과제(퀘스트)

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 일일/주간/월간/이벤트/난이도별/공동/AI추천 미션 | 전부 없음. `/me/objectives`(`api/study.py`)는 학습 목표 *공급*이지 게임 미션이 아님 | 🚫(전건) |
| XP·코인·배지·아이템·특별콘텐츠 보상 | 전부 없음 | 🚫(전건) |

### 기능 79 — 학습 연속 기록(Streak)

| 세부 기능 | WhyMath 현행 | 판정 |
|---|---|---|
| 연속 학습일수 | **좌석만 있음** — `consecutive_active_days`(`db/models/user.py:324`) writer 0 | ⚠️ → D2 |
| 최고 기록·달력·월별 통계 | 없음 | 🚫(전건) |
| Streak Freeze(보호권)·복구 기회 | 없음 — "끊기면 잃는다" 압박 설계 자체가 금기 | 🚫(전건) |
| 연속 목표 설정 | 없음 | 🚫 |
| 7일/30일/100일/365일 단계별 보상 | 없음 | 🚫(전건) |
| (대체) `Dialogue.resolution=학생자력해결` 재진입 | ⑪ 스스로 풀이 도달율의 재료 — "끊긴 것을 세지 않는 복귀" 방향과 정합 | △(D2 발화조건으로 언급) |

### 연계 구조(7단 루프) 대조

틀의 루프 `문제풀이→XP획득→레벨상승→배지획득→도전과제해금→Streak유지→추가보상`은
**외재 보상의 단방향 강화 루프**다. WhyMath에 대응하는 것은 없다 — 대신 D1이 설계하는
"성장의 증거" 루프(자기 행동 → 도움 감소/오개념 해소/숙달 증가라는 *관찰 가능한 변화* →
다음 목표)가 §3 D1에 있다. 두 루프는 **형태가 다르다**(보상 지급 vs 상태 반영)는 것이
이 대조의 핵심 결론이다.

---

## §2. 의도적 미채택 판정 (협상 불가 근거)

| # | 문서 제안 | 불채택 근거 (CLAUDE.md·정본) |
|---|---|---|
| ① | **XP·경험치 시스템 전체**(기능 76) | `CLAUDE.md:106` "학습 시간·정답률만으로 우열을 매기는 게임화 금지"의 직접 위반. 즉각 보상은 "정답을 빠르게" KPI화와 동형(`CLAUDE.md:105`) |
| ② | **학생 레벨(1~1000)·AI Tutor 레벨**(기능 75) | 단일 서열 스칼라는 "우열을 매기는" 것 그 자체. `mastery_to_level` 3라벨은 *상태 추정*이라 다르다 — 서열 재도입은 이 구분을 무너뜨린다 |
| ③ | **배지·업적 컬렉션**(기능 77) | `.claude/agents/content-curator.md:193` "최고 풀이 랭킹" 금지와 동일 계열 — 배지는 비교 신호의 시각적 형태다. `07_community.md:57` "과장된 칭찬 금지"와도 충돌(배지 획득 알림 자체가 과장 연출) |
| ④ | **도전 과제(퀘스트)·미션**(기능 78) | `ai_tutor_module_gap_review.md:179` §2-③에서 **이미 판결** — "학습습관 게임화(미션·리더보드·푸시 압박)" 불채택 승계. 본 문서에서 재판정하지 않는다 |
| ⑤ | **연속 학습일수 카운터·Freeze·복구권·달력**(기능 79) | 압박형 넛지 — "끊기면 잃는다"는 정서 안전(`CLAUDE.md:107` 부정 피드백 정서 강화 금지)과 정면 충돌. `.claude/agents/flutter-engineer.md:296` "연속 정답 스트릭(도파민 유발)" 명시 금지 |
| ⑥ | **랭킹·리더보드(전 형태)** | `07_community.md:14,53` "랭킹·경쟁 금지"·"최고 풀이 랭킹 금지" · `pipa_data_matrix.md:46` 또래 비교 최엄격 통제(부모조차 미공개) |
| ⑦ | **코인·아이템·특별콘텐츠 보상** | 결제·수익화 수단으로 게임화를 쓰지 않는다(`docs/strategy/business_model.md:20` "게이미피케이션 중독을 수익화 수단으로 삼지 않는다") |
| ⑧ | **빨간 카운트다운·긴급성 연출** | `05_interaction.md:31` "빨강 ❌, 노랑 ✅" · `06_design_system.md:28` M3 error 롤을 **앰버로 재정의**(`test/theme_test.dart` 회귀 게이트로 동결) — 색채 자체가 이미 반대 방향으로 고정됨 |
| ⑨ | **레벨업/배지 획득 등 보상형 알림 문구** | `07_community.md:57` "과장된 칭찬 금지" · `.claude/agents/flutter-engineer.md:290` "매일 푸시 → 부담" — 알림 인프라 자체가 pubspec 선언만(Firebase 초기화 0)이라 당장 발화하지 않지만, 향후 알림 도입 시에도 이 문구 계열은 금지 |
| ⑩ | **dead table 5종을 되살려 습관 대시보드로 활용** | `ai_tutor_module_gap_review.md:179` 승계 — "dead table을 되살려도 목적이 게임화라면 함께 불채택". `learning_session`·`daily_learning_metrics` 등은 여전히 영구 미신설(`S3-16` §3) |
| ⑪ | **자유학기제 외 모드로 `gamification_level` 확대** | `06_application_modes.md:135` 자체가 "4+ 금지" 상한을 명시. 확대는 그 상한의 취지(적정 수준의 예외 하나만)를 무너뜨림 — D3(페이퍼) 참조 |

---

## §3. 진짜 갭 설계

### D1 — 성장의 증거가 학생에게 도달 0회 (최우선 · `PED-06`)

**문제**: `compute_wh1_surrogate_metrics`(`harness/wh1_evaluation.py:983`)가 11지표를 계산하고
`GET /v1/me/harness-metrics`(`api/me.py:2190`)로 노출하는데, Flutter 13종 엔드포인트에 없다.
`api/me.py:1247` 주석은 `/diagnosis/summary`의 소비자를 "대시보드 헤더"로 명시하지만 그
대시보드가 만들어진 적이 없다. `mastery_to_level`의 숙달 라벨도 클라 도달 0.

**핵심 판단**: **활성화가 아니라 가시화**가 목표다(`NLP-01` 동형 — 승계). 그리고 이 갭은
단순 "화면이 없다"가 아니라 **"무엇을 보여줘도 되는지가 정해진 적이 없다"**이다. 11지표를
한 덩어리로 노출하면 그 자체가 새 위험이다 — 일부는 학생에게 보이면 **금기 위반**이 된다:

- `help_reduction_validated`의 `GAMING_SUSPECT` — 학생 대면 노출 시 **낙인**
  (`CLAUDE.md:107` 부정 피드백 정서 강화 금지 · `07_community.md:57-61` 학생 비난 금지). 이 신호는
  ⑧ 답 미루기 도달 깊이와 **단독 분리가 안 된다** — `wh1_evaluation.py:346` 자체가 "게이밍(힌트
  회피)은 R15가 교차 방어·단독 해석 금지"라고 명시한다. 즉 노출 계약은 **필드 단위 allowlist가
  아니라 조합 제약**이어야 한다 — ⑧을 보이려면 R15가 안전 판정(GENUINE_IMPROVEMENT)일 때만,
  또는 ⑧ 원값을 R15와 분리해 다르게 서술해야 한다.
- ② 진단정확도 — **시스템 지표**(진단엔진 품질)이지 학생 개인 지표가 아니다. 보여주면 오독
- ④ 턴당 토큰 — 비용 지표. 학생 대면 의미 0
- ⑥ 보정 점수(Brier) — 원 스칼라는 "낮을수록 좋음" **역방향**이라 그대로 보이면 오독. 게다가
  학생이 확신도를 *입력하는* UI가 `src/mobile/lib/` 전체에 **0건**이다(확신도 관련 히트는 전부
  OCR 기계 신뢰도 — `ocr_models.dart:53,56,92,110`). `l4/calibration_coaching`(REC-01 상류)이
  풀려도 확신도 자체를 수집할 표면이 없는 한 ⑥은 구조적으로 `NO_DATA`다

**정합 설계**(신규 테이블 0 · 마이그레이션 0 · 새 지표 계산 0):
- **①** 학생 대면 **노출 계약** 정본화 — 11지표를 `학생 노출 가능(자기 대비 서술) / 보호자 요약 /
  내부 전용` 3분류로 고정. 안전 축(⑧+R15 조합·⑨·⑩·⑪·⑤ 기울기 방향 서술)과 배제 축
  (`GAMING_SUSPECT` 라벨 원문·②·④·⑥ 원 스칼라)을 분리. **비교·서열·순위 파생 금지**를 계약에
  명문화(`07_community.md:53` "❌ 익명·집계만" 승계).
- **②** 도달 관측 리포트 — 성장 지표 요청 수 / 지표별 `MetricStatus` 분포 / 학생 도달 건수를
  산출. **표본 0이면 "0건 통과"가 아니라 "미도달"**로 표시(`VIZ-01`·`NLP-01` 이중 회계 승계).
- **③** **3상태** 구분 — `미도달`(계산은 되는데 학생에게 안 보여줌) / `무데이터`(입력 0) /
  **`구조적 불가`(생산자 자체가 없음)**. 셋째가 실재한다: `LearningSession`은 `src/` 전체에서
  **단 한 번도 생성되지 않는다**(`LearningSession(` 생성자 호출 0 · `api/me.py`는 GET/PATCH/
  DELETE만). **③ 세션 완주율**이 이를 읽으므로 영원히 `NO_DATA`이고, writer는 2026-07-29
  **영구 미신설** 결정(`S3-16`). ③을 `무데이터`와 같은 칸에 두면 다음 세션이 writer를 만들려
  든다 — 반드시 `구조적 불가`로 분리 표기한다(§정정 대상). (⑪은 `Dialogue.resolution` 기반이라
  클라가 실제로 쓰고 있고 **라이브 가능** — ③과 같이 묶지 않는다.)
- **④** 확신도 수집 표면 부재 기록 — ⑥·`calibration_coaching`이 영구 `NO_DATA`인 이유가
  "배선 안 됨"이 아니라 "입력받을 UI 자체가 없음"임을 리포트가 구분해 표기(REC-01의 "입력 루프
  안 이음"과는 다른 층 — REC-01은 attempt *제출*, 이것은 확신도 *필드* 미수집).

**dead code 금지 충족**: 신규 코드 0(설계 문서). 리포트·계약은 후속 태스크(`PED-06`)의 산출물.

**변별력**: attempt 1건 주입 시 "미도달"이 실제로 해제되고 되돌리면 다시 나오는지 양방향 실측.

**acceptance 후보**:
1. 노출 계약 정본(3분류 + 조합 제약 ⑧×R15 + 원값 역방향 서술 규칙)
2. 도달 리포트(3상태: 미도달/무데이터/구조적 불가)
3. 변별력 양방향 실측
4. CI 배선 실재 확인(`OPS-03`·`OPS-10`)
5. **범위 밖 동결**: 모바일 화면 신설·클라 attempt POST 배선(`REC-01` 상류)·확신도 수집 UI
   신설·푸시 알림.

**의존**: `REC-01`(입력 루프 상류) · `S3-16`(③ writer 결정 승계). **태스크**: 신설 — `PED-06`

### D2 — 반게임화 불변식의 기계 게이트가 0이다 (`ARCH-23`)

**문제**: 전역 UI 불변식 #2(`docs/design/ui/00_index.md:41`)가 문서·주석 20+ 곳에 인용되는데
**테스트는 0건**이다. `tests/`에 반게임화 관련 소스 스캔 심볼 0. 즉 **"규정하고 기계화 안 함"**
— 회귀를 막는 것이 사람의 기억뿐이다.

**대비가 논거다**: `CLAUDE.md:104-107` 교수학 금기 **4개 조항이 한 블록**인데 기계화가 갈린다 —
"바로 정답 제공 금지"는 `l4/hint_deferral.decide_hint_level`, "부정 피드백 정서 강화 금지"는
`l4/tone_filter.filter_tone`(+`ToneReport` violations · `polya/engine.py:141` 마지막 방어선),
"'정답을 빠르게' KPI 금지"는 `help_reduction_validated`의 `GAMING_SUSPECT` 교차 판정이 각각
게이트를 갖는다. **오직 "우열 게임화 금지"만 게이트가 0이다.**

**좌석 소유권 재확인(중복 회피)**: 죽은 좌석 후보 3개 중 `focus_score`·`engagement_score`
(`db/models/activity.py:107-108`)는 **`S3-16` acceptance ③이 이미 소유**한다("writer 미신설을
결정으로 명시 + NULL 유지 동결 테스트"). D2가 재등재하면 이중 소유이므로, **D2의 죽은 좌석
범위는 `consecutive_active_days`(`db/models/user.py:324`) 단독**으로 좁힌다 — 이것이 정확히
Streak(기능 79) 축이라 논지가 오히려 더 선명해진다.

**추가로 드러난 더 위험한 구멍**: `UserBehaviorMetrics.metric_name`(`schema/timeseries.py:216,240`)
은 **닫히지 않은 문자열**(open set, DDL VARCHAR(50))이고, 정본 docstring이 **`'streak'`을
예시로 명시**한다. `extra="forbid"`는 필드를 막을 뿐 *값*은 못 막는다 — 좌석 하나(컬럼)가 아니라
**임의의 게임화 지표명이 값으로 흘러들 수 있는 열린 통로**다.

**정합 설계**(마이그레이션 0 · 회귀 0 · 런타임 영향 0):
- **①** Dart 소스 스캔 — 선례는 `test/theme_test.dart`(색상 속성 검사)가 **아니라**
  `src/mobile/test/governance/no_math_logic_governance_test.dart`(`ARCH-10`)다. 이 파일의
  4대 기법을 그대로 재사용: (a) 정밀도 원칙 — 백엔드 판정 수신 필드는 로직이 아니므로 금지
  안 함, 여기선 "발화 카테고리 라벨"은 게임화가 아니므로 금지 안 함 (b) `\b`+합성어 경계
  정규식(`checkAnswer\w*\(` 스타일) — 바닥 단어가 아니라 `XpPoints?`·`LevelUp\w*`·
  `BadgeEarned\w*`·`QuestUnlock\w*`·`Leaderboard\w*`·`StreakCounter\w*`·`DailyStreak\w*`·
  `CoinReward\w*` 같은 **복합 식별자**로 좁혀 `_SocraticBadge`(소크라테스 UI 칩)를 자연히
  피한다 (c) 경로 스코프 `Directory('lib')` 한정 (d) 게이트 무력화 방지 —
  `expect(_libDartFiles().length, greaterThan(N))`로 스캔 자체가 죽지 않았는지 확인.
- **②** Python 소스 스캔 — **학생 대면 표면에 한정**한다(`api/**`·응답 `schema/**` 최상위
  모델만). `l3/`·`l4/misconception/`·`harness/`·`data/corpus/**`는 **스캔 제외**(`gambler_streak`
  오개념 ID·`achievement_standard` 성취기준 등 정당 어휘의 서식지 — `test_subject_neutrality_gate.py:29`
  가 테스트 트리를 제외한 것과 동형 논리). 게이트 파일 자신이 금지어에 걸리지 않도록 리터럴은
  문자열 조립 기법으로 우회(`test_subject_neutrality_gate.py:33` 선례).
- **③** 값 동결(스캔이 아니라 상수·동작 freeze — `test_edge_relation_governance.py` 스타일) —
  `UserBehaviorMetrics.metric_name` **금지값 집합**(게임화 계열 문자열이 실제로 INSERT되면 위반)
  + `consecutive_active_days` writer 0 동결.
- **④** 변별력 — 금지 심볼/값을 일부러 주입하면 실제로 red가 나는지 양방향 실측.

**dead code 금지 충족**: 게이트 자체는 새 런타임 동작을 추가하지 않음(테스트 전용).
**측정 없는 도입 없음**: "규정만 하고 안 지킨다"를 종료 — 채우려면 테스트를 의식적으로
수정해야만 가능해진다(`CLAUDE.md` "측정 없는 기계 게이트를 인간 검수 대체로 선언 금지"와 정합).

**acceptance 후보**:
1. Dart 게이트(①) — 복합 식별자 정규식·`lib/` 스코프·무력화 방지
2. Python 게이트(②) — 학생 대면 표면 한정·제외 경로 docstring 명시
3. 값 동결(③) — `metric_name` 금지값 + `consecutive_active_days` writer 0
4. 변별력 양방향(④)
5. CI 배선 실재 확인(`OPS-03`·`OPS-10`)
6. **범위 밖 동결**: `focus_score`/`engagement_score`(`S3-16` 소유) · 컬럼 제거 마이그레이션 ·
   `tone_filter` 라이브 배선(§4-② 참조).

**태스크**: 신설 — `ARCH-23`

### D3 — 동기 설계 정본 부재 (**페이퍼 → 정본 3곳 직접 개정 · 태스크 신설 없음**)

**문제**: 반게임화 금기는 20+ 인용인데 "그럼 무엇으로 동기를 지탱하는가"의 정본이 0.
`risks.md:119-121`의 최우선 검증 가설(D7 retention)을 지탱할 설계가
`02_student_ui_master_plan.md:81-83` 한 문단뿐.

**핵심 판단**: 시리즈 선례를 전수 확인한 결과 **"정본 신설" 태스크는 존재하지 않는다** —
시리즈가 실제로 하는 것은 **기존 정본 개정**이다(`nlp_module_gap_review.md §정정`·
`ai_recommendation_module_gap_review.md §정정`이 각각 기존 문서에 인라인 블록쿼트로 정정을
넣은 선례 — `docs/architecture/02_learner_model.md:196-202`의 "현행 정합(2026-08-01 실측 정정)"
패턴). 따라서 이 항목은 **별도 태스크·별도 파일이 아니라, 이 문서 자체가 설계를 확정하고
기존 정본 3곳을 같은 커밋에서 직접 개정**하는 형태로 착지한다(§정정 참조).

**정합 설계 — WhyMath판 동기 모델 "성장의 증거"(5원칙)**:

> 이 5원칙은 새 발명이 아니라 **이미 정본에 흩어져 있는 허용 목록의 통합**이다.
> `.claude/agents/flutter-engineer.md:299-301`이 게임화 금지 바로 옆에 허용 2종을 명시한다 —
> "✅ *학습 경로* 시각화(어디 와있는지)", "✅ *오개념 해소* 마커(성장 시각화)". 그 둘 모두
> **서버측 지표가 이미 있다**(`/me/weak-concepts/{id}/learning-path` · ⑩ 오개념 해소율).
> 정본이 없던 것은 허용 목록이 아니라 **그것을 하나의 동기 모델로 묶은 문서**다.

1. **보상이 아니라 증거** — 외재 보상(XP·배지·코인)을 주지 않는다. 학생이 보는 것은 *자기
   행동이 만든 변화의 증거*다: 도움 없이 간 거리(⑧), 줄어든 도움(⑤ 기울기), 해소된 오개념(⑩),
   스스로 도달한 풀이(⑪).
2. **비교가 아니라 자기 대비** — 모든 지표는 **본인 과거 대비**로만 제시. 타 학생·평균·순위
   파생 금지(`07_community.md:53` · `pipa_data_matrix.md:46` 승계).
3. **즉시 피드백의 자리는 보정(calibration)이다** — XP의 자리를 대체하는 것은
   `confidence_self_reported` × `is_correct` → Brier + `calibration_coaching`. "네 예측이
   맞았다"는 메타인지 피드백이 정답 보상보다 정체성에 부합한다(배선은 `REC-01` 상류).
4. **연속성은 압박이 아니라 복귀 지원** — Streak의 정당한 핵심은 "끊기면 잃는다"가 아니라
   "돌아오기 쉽다". 채택 형태는 **끊긴 것을 세지 않는 재진입 경로**(이어하기·마지막 목표
   복원)이며, 연속 일수 카운터·Freeze·복구권·달력은 전부 미채택(§2-⑤).
5. **정서 신호는 내부 결정 입력으로만** — `AffectState` 5분류의 학생 대면 라벨링 금지
   (`ai_tutor_module_gap_review.md:177` 승계). 생산자 먼저·분류기 나중(MEMORY 2026-07-29).

**개정 반영(이 커밋에서 직접 수행 — §정정 참조)**:
1. `docs/design/ui/02_student_ui_master_plan.md:83` 뒤에 5원칙 인라인 추가 + 본 문서 링크
2. `docs/standards/dev_constitution.md:21` 우선순위 문구에 "웰빙·정서·중독" 보강 주석
3. `docs/architecture/02_learner_model.md:230` Phase 2 "✅ 정서 분류기" 옆에 2026-07-29
   v0 제외 결정과의 불일치 주석

### D4 — 자유학기제 `gamification_level` (**페이퍼 — 코드 0 · 태스크 신설 없음**)

`06_application_modes.md:135-136`이 `gamification_level: int  # 0(없음) ~ 3(중간), 4+ 금지`를
정의하나 `ModeConfig` 심볼 자체가 코드 0(`grep -rn "ModeConfig" src/` 히트 전부 `docs/`)이고
자유학기제는 Phase 3~4다. `05_source_reconciliation.md:56`이 이미 이걸 원본-정본 충돌 해소
항목 #1로 등재해 조정을 마친 사안이다. **예외는 유지하되 코드 0임을 명시**하고, 발화 조건만
§5에 기록한다.

### 등재 요약

| 태스크 | 설계 | stage | priority | 근거 |
|---|---|---|---|---|
| `PED-06-growth-evidence-reach-observability` | D1 — 성장 증거 노출 계약 + 도달 리포트 | S3 | 2 | 대리지표 11종 계산 완비·클라 도달 0(§0-②) |
| `ARCH-23-anti-gamification-source-governance-gate` | D2 — 반게임화 소스 스캔 게이트 + 값·writer 동결 | S3 | 2 | 전역 UI 불변식 #2 인용 20+·집행 테스트 0 |
| D3(동기 정본) | 정본 3곳 직접 개정 — 새 태스크 없음 | — | — | **정본 개정(§정정) 관례 적용** — 시리즈에 "정본 신설" 태스크 선례 없음 |
| D4(`gamification_level`) | 페이퍼 — 태스크 없음 | — | — | **승계·재설계 금지**(`05_source_reconciliation.md:56` 이미 조정됨) |

태스크는 전건 `backlog.py add` CLI 경유로 등재했다(ID 손편집 0 · 번호 충돌은 CLI가 로컬+원격
양쪽 검사 — HARN-10). `--path` 선언으로 겹침 검사를 켰다. **`validate` green 155건**
(baseline 153건 + 신설 2건 — D3·D4는 태스크 미신설이라 REC/NLP 편보다 신설 수가 적다).

---

## §4. 정직한 공백 — 지금 하지 않는 것 (6종)

1. **`tone_filter`의 라이브 미배선** — `l4/tone_filter.py`(금지 6패턴 치환: "틀렸"→"다시 봐도
   좋아" 등)는 반게임화 인접 조항("부정 피드백 정서 강화 금지")의 유일한 집행기이나,
   `harness/pilot_kpi_baseline.py:511-514`가 스스로 "coach는 결정론 `decide()`로 응답하고 LLM
   생성이 0이라 톤 필터를 타지 않는다"고 자인한다. 배선(`polya/engine.py:141`)은 있으나 발화할
   LLM 자유생성 경로 자체가 없다. `S3-16` acceptance ②가 KPI3(정서안전) NO_DATA 해소를 힌트
   supply/demand 비율로 이미 소유하므로, 이것과 별개로 새 태스크를 열지 않는다 — LLM 자유생성
   활성화는 L3/L4 전체 아키텍처 질문이라 게임화 축 범위 밖이다.
2. **⑥ 확신도 수집 UI 신설** — D1이 그 부재를 *기록*하지만 UI 신설은 D1 범위 밖(사용자 확정
   ① 서버측 가시화만).
3. **`Dialogue.resolution` 기반 재진입 UX**(D3 원칙 4의 구체 화면) — 설계 원칙만 확정, 화면
   설계는 후속.
4. **알림(푸시) 기반 복귀 유도** — Firebase는 pubspec 선언만(초기화 0). 알림 인프라 자체가
   없어 "복귀 지원" 알림은 논할 재료가 없다.
5. **`gamification_level` 코드 실체화**(D4) — Phase 3~4·L6 축 소관. 지금 만들지 않는다.
6. **PRD·ROADMAP에 동기·게임화 섹션 신설** — 이 문서 + 3곳 정본 개정으로 충분하다고 판단.
   별도 PRD 섹션은 제품 축 결정이라 범위 밖.

---

## §5. 유보 항목의 발화 조건

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | `tone_filter` 라이브 배선(§4-①) | coach 경로에 LLM 자유생성이 도입되는 시점(별도 L3/L4 결정) |
| ② | 확신도 수집 UI(§4-②) | `REC-01` 도달 리포트에서 attempt 제출이 실제로 관측된 뒤 — 입력 루프부터 살아야 확신도 UI가 의미를 가짐 |
| ③ | 재진입 UX 화면(§4-③) | D1 노출 계약이 확정되고 `/me` 탭 placeholder 해소가 별도로 착수될 때 |
| ④ | 복귀 유도 알림(§4-④) | Firebase 초기화·백엔드 발송 인프라가 별도 태스크로 갖춰질 때(현재 태스크 0) |
| ⑤ | `gamification_level` 코드 실체화(D4) | 자유학기제 모드가 L6 게이팅에 실제 배선될 때(Phase 3~4). **동시에 D2(ARCH-23) 게이트가 이 값을 오탐하지 않도록 예외 경로를 그 시점에 함께 설계**해야 한다 — 안 그러면 정당한 `gamification_level>0` 배선이 반게임화 게이트와 충돌한다 |
| ⑥ | 협업 필터링·소셜 동기(다중 풀이 갤러리 확장) | `ai_recommendation_module_gap_review.md §5-③`과 동일 조건(파일럿 N 임계 + 동의 범위 갱신) 승계 |

---

## §6. 반복 실수 — 7~8회차 등재

`ai_recommendation_module_gap_review.md` §6이 6회차까지 채웠다. 이번 대조에서 **형태가 다른
두 가지**가 나온다 — 단, 1~6회차와 정확히 같은 결이 아니므로 구분을 명시한다.

| 회차 | 사례 | 형태 |
|---|---|---|
| **7** | 성장 지표 11종 계산되는데 클라가 **호출하기로 결정한 적조차 없음**(D1) | **결정 부재**(배선 부재 아님) |
| **8** | 반게임화 불변식 20+ 인용 · 집행 테스트 0건(D2) | **규정하고 기계화 안 함** |

1~6회차는 전부 "**배선 부재**"다 — 무엇을 이을지는 이미 정해져 있었고 잇지 않았다(적재
안 함·배포 안 함·입력 안 이음 등). 7회차는 다르다 — `harness-metrics`를 클라가 부르기로
**결정한 적 자체가 없다**. REC-01(D1, 5회차 "안 켬")과 겹쳐 보이지만 다르다: 5회차는 "켜는
스위치가 있는데 꺼둠"(`prioritize_weak_concepts` 기본 false)이고, 이번은 "스위치 자체가 없다"
— 무엇을 보여줄지 결정한 노출 계약이 없다. 8회차는 주어 자체가 다르다 — 앞 7회차의 주어는
**자산**(코드·데이터)인데, 8회차의 주어는 **규범**이다. "만들고 ○○ 안 함"이 아니라 "규정하고
○○ 안 함". `schema/timeseries.py:228`의 "가짜 validator를 두지 않는다(문서화만)"이 이 형태를
코드 스스로 자인한 문장이다. 이 형태가 반게임화 외 다른 불변식에도 해당하는지는 후속 점검 대상.

---

## §정정 — stale 정본 5곳 (이번 대조에서 실측으로 발견)

| 위치 | 현재 기술 | 실측 |
|---|---|---|
| `docs/standards/dev_constitution.md:21` | 우선순위 1번 "학생 안전·**정확성**" | `CLAUDE.md:287`는 "학생 안전·**웰빙**(정서·중독·부정확)". 웰빙·정서·중독이 누락 — 게임화 금기의 뿌리가 개발헌법에 명시돼 있지 않다 |
| `docs/design/ui/00_index.md:41` · `01_student_pipeline_to_menus.md:199` | "자유학기제 모드만 `gamification_level` 적정" | `ModeConfig`·`gamification_level` **코드 심볼 0**(전수 확인). 예외가 코드 계약으로 실재하는 것처럼 읽힌다 |
| `docs/architecture/02_learner_model.md:230` | Phase 2 성공 기준 "✅ 정서 분류기" | 2026-07-29 `affect` v0 제외·"생산자 먼저·분류기 나중" 결정과 불일치. 성공 기준이 미채택 결정보다 앞서 있다 |
| `docs/architecture/04a_wh1_tutoring_harness.md:595` | 커버리지 맵 "**🟢 ③ 세션 완주율**" = 계측 | `LearningSession`이 `src/` 전체에서 **한 번도 생성되지 않는다**(생성자 호출 0). ③은 구조적으로 영원히 NO_DATA이고 writer는 2026-07-29 **영구 미신설** 결정(`S3-16`). 🟢 표기가 "돌아감"으로 읽혀 다음 세션이 writer를 만들려 들 수 있다 |
| `docs/strategy/prd_v1.2.md:626` | 학습 효과 KPI "평균 학습 시간 30분/일" | `CLAUDE.md:106` "학습 시간…으로 우열을 매기는 게임화 금지"와 긴장. 제품 총계 KPI(운영 지표)와 개인 서열 신호(금지 대상)의 구분 표기가 필요 — 지금 수정하지 않고 관찰만 기록 |

첫 3곳(`dev_constitution.md`·`02_learner_model.md`)은 D3 개정 반영으로 **이 커밋에서 직접
수정**한다. 넷째(`04a_wh1_tutoring_harness.md`)는 커버리지 맵 원문에 정정 각주만 추가한다(3상태
분리는 `PED-06`이 리포트 자체에서 구현). 다섯째(`prd_v1.2.md`)는 제품 KPI 정의 변경이라 이
문서 범위 밖 — 기록만 남기고 수정하지 않는다.

---

## 부록 — 실측 근거 (2026-08-03 실측)

**성장 증거 미도달(D1)**
- `harness/wh1_evaluation.py:288-365` `SurrogateMetrics` 11필드 전체 선언
- `harness/wh1_evaluation.py:212-230` `R15Verdict`(GENUINE_IMPROVEMENT/GAMING_SUSPECT)
- `api/me.py:2190` `GET /v1/me/harness-metrics` · `:1247` `/diagnosis/summary` "대시보드 헤더" 주석
- `api/me.py:689-690,713` `calibration_coaching` 계산·응답 적재(REC-01 상류로 클라 미도달)
- `l4/lthc/adapt.py:127` `mastery_to_level` — `MasteryLevel` 클라 심볼 0
- `src/mobile/lib/`: `confidence` 히트 전부 OCR 기계 신뢰도(`ocr_models.dart:53,56,92,110`) ·
  학생 자기보고 확신도 입력 UI 0
- `LearningSession(` 생성자 호출 `src/` 전체 0건 · `api/me.py`는 GET/PATCH/DELETE만

**반게임화 게이트 부재(D2)**
- `docs/design/ui/00_index.md:41` 전역 UI 불변식 #2 원문
- `CLAUDE.md:104-107` 교수학 금기 4조항 블록 — 3개는 게이트 보유(`hint_deferral`·`tone_filter`·
  `help_reduction_validated`), 우열 게임화 금지만 게이트 0
- `db/models/user.py:324` `consecutive_active_days` writer 0(단독 남은 좌석)
- `backlog/tasks/S3-16-behavior-telemetry-writers.yaml:16` acceptance ③ — `focus_score`/
  `engagement_score` 소유권 선점 확인
- `schema/timeseries.py:216,240` `UserBehaviorMetrics.metric_name` open set, `'streak'` 예시 명시
- `src/mobile/test/governance/no_math_logic_governance_test.dart` — Dart 소스 스캔 게이트 선례
  (정밀도 원칙·`\b`+합성어 정규식·경로 스코프·무력화 방지 4대 기법)
- `tests/backend/l1/test_embedding_namespace_governance.py` §③ — allowlist 소스 스캔 선례
- `tests/data_pipeline/test_subject_neutrality_gate.py:29,33` — 경로 제외·자기회피 리터럴 조립 선례

**동기 정본(D3)**
- `.claude/agents/flutter-engineer.md:294-301` 게임화 금지 + 허용 2종("학습 경로 시각화"·
  "오개념 해소 마커")
- `docs/design/ui/02_student_ui_master_plan.md:81-83` "목표→성취→다음 목표" 유일한 긍정 프레임
- `docs/strategy/risks.md:119-121` D7 retention ≥ 30% 최우선 검증 가설
- `docs/architecture/02_learner_model.md:196-202` 정본 개정 인라인 블록쿼트 선례(REC 편)

**의도적 미채택(§2) 근거 원문**
- `ai_tutor_module_gap_review.md:178-179` §2-③ 게임화 선행 판결
- `07_community.md:14,29,53,57-61` 랭킹·과장된 칭찬 금지 4개 지점
- `docs/strategy/business_model.md:20` 게이미피케이션 중독 수익화 금지
- `docs/architecture/06_design_system.md:28` M3 error 롤 앰버 재정의(색채 방향 고정)
