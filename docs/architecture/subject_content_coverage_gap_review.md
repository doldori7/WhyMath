# 과목별 콘텐츠 커버리지(문제·이론) 갭 점검·설계 (2026-08-10 · 2026-08-11 회수·증보)

> **📌 회수·증보 안내 (2026-08-11)**: 이 문서의 §0~§6·§정정·부록 ㉮~㉳은 **2026-08-10 1차본
> 원문**이며, 당시 main에 착지하지 못하고 브랜치 `claude/subject-problems-theory-check-7n9n72`에
> 고립돼 있었다(미병합 고립 5회차). 2026-08-11에 파일 단위 재적용으로 **회수**하면서
> 두 절을 증보했다:
> - **§7 현행 재검증** — HEAD `833f46af` 기준 Δ 7건(총계 2,647→2,638 등). **커버 판정은 불변**.
>   본문의 stale 수치에는 인라인 `[→ §7-Δn]`을 달았고, 1차 본문 자체는 이력 보존을 위해 고치지 않는다.
> - **§8 대학 콘텐츠 축 증보** — 1차본 §2-⑤가 "범위 밖"으로 유보했던 대학 32과목 축을,
>   Kiki 요청("초에서 대학교까지 학교급별·과목별 이론·문제 완비 체크")에 따라 해제·실측했다.
>   부록 ㉴~㉸ 추가.
>
> **목차**: §0 전제 · §1 전수 대조(K-12) · §2 의도적 미채택 · §3 갭 설계 D1~D3 · §4 정직한 공백 ·
> §5 발화 조건 · §6 재발방지 · §정정 · 부록 ㉮~㉳ · **§7 현행 재검증** · **§8 대학 축 증보** ·
> **부록 ㉴~㉸**

> **범위**: 문제 코퍼스 7종 2,647문 [→ §7-Δ1: 현행 2,638](`data/corpus/problem_bank_*/problems.jsonl`) × 이론 자산
> 전량(`atom_graph_v1` 2,683노드 · `concept_content_v1` 437 · `concept_content_university_v1`
> 409 · 암기카드 · chunk · 성취수준)을 **과목(2022 개정 19 subject + 초·중 학교급 + 대학
> 32과목) 축으로 전수 대조**한다. Kiki 요청("문제와 이론 파트 각 과목별 빠진 부분 점검과 대책").
> **형식**: 기존 22건 시리즈(외부 EOS 틀 대조)와 달리 외부 문서 없이 **저장소 실측 × 과목 축
> 자체 대조** — 시리즈 첫 사례. 절 구성은 `problem_bank_gap_review_r2.md`·
> `curriculum_module_gap_review.md` 관례를 답습한다.
> **결론**: 착수 가설("과목별로 빠진 부분이 있을 것")은 두 파트에서 **다르게** 성립한다 —
> 문제 파트는 *과목 자체가 비어 있고*(0문 4과목·수능 선택 3과목 박약·성취기준 커버 17.9%),
> 이론 파트는 *과목은 다 있는데 본문 축이 통째로 비어 있다*(K-12 정의 원문 redaction 1,311 ·
> 검수 0 · chunk 0 · 성취수준 0). 신규 등재 **2건**(ARCH-28 실행 완료·KG-02) · 승계 **5건** ·
> 페이퍼 **1건**(저작 우선순위 v2) · stale 정정 **3곳**.

관련 정본: `docs/data/problem_bank_coverage_2026-08.md`(ARCH-28 산출물·이 문서의 문제 축 수치
원천) · `docs/architecture/problem_bank_gap_review.md`+`_r2.md` · `knowledge_module_gap_review.md`
· `curriculum_module_gap_review.md` · MEMORY.md 결정 로그 2026-06-21(원자 백본 전면 교체)·
2026-07-10(AI 검수 전환)·2026-08-03(교육과정 D1~D3). 측정 HEAD: `b3e3708c`.

---

## §0. 네 가지 전제 정리

### ①  과목 축의 정본은 성취기준 대장의 `subject` 필드다 — `Problem.subject`는 무효

`Problem.subject`(ORM NOT NULL·enum 공통/미적분/확통/기하/인공지능수학)는 **2,647건 전량 [→ §7-Δ1]
`"공통"`**(카디널리티 1)이다. 생성기 전군이 기본값을 하드코딩하기 때문이며, 유일 소비처인
`api/problems.py:121`의 `where(Problem.subject == subject)` 필터도 무변별이다(전부 또는 0건).
어휘 자체가 2015 수능 선택과목 축이라 2022 개정 과목(대수·미적분Ⅰ/Ⅱ·기본수학 등)을 표현할
수 없다. 반면 `standards_v1/standards.json`은 **2022 개정 435건 전량에 `subject`(19종)**,
2015 개정 460건 전량에 13종이 채워져 있다 — 이 필드가 과목 축의 유일한 원천이다(§3 D1이
도구로 정본화·코드 prefix 파싱 신설 금지).

### ②  원자 진단문항은 전 과목 100% — 공백은 "연습·평가 문제은행"과 "이론 본문" 축에 국한

`atom_probe`(원자 진단문항·소크라테스) 1,823건은 세부개념 전량에 채워져 있고 2022 개정 고등
15과목·초·중 4영역·대학 32과목을 전부 덮는다(부록 ㉯). 따라서 "과목별 빠진 부분"은 ⑴ 연습·
평가용 문제은행(§1 표1) ⑵ 이론 *본문*(정의 원문·검수·chunk·성취수준 — §1 표2)의 문제다.
진단 축을 공백으로 오인하지 않는다.

### ③  미병합 완료분 선확인 — CUR-03 실물은 HEAD 조상이 아니다 (HARN-11 유형)

`CUR-03-achievement-level-data-intake`(성취수준 A~E·평가기준 상/중/하 반입, owner=kiki)는
status=done·artifact `98a34695`인데, **그 커밋은 HEAD 조상이 아니다**(`git merge-base
--is-ancestor` 실측 — `origin/claude/human-bottleneck-tasks-6dszy0`·`origin/merge/
human-bottleneck-6dszy0`에만 존재). 즉 성취수준 축은 "0건"이 아니라 "**미병합 회수 대기 +
HEAD 기준 0건**"이 정확한 상태다(§4·게이트성 안내). 또 미병합 `math_engine_gap_review.md`
(`claude/whymath-math-engine-design-4qbaru`)는 수학 엔진 모듈 축(MathLive·검증·그래프)이라
이 문서와 겹치지 않음을 확인했다 — 단 그 브랜치가 MATH-01~04 ID를 선점 중이라 이번 신규
등재는 MATH- 접두를 회피했다.

### ④  수치 정본 위치 선언 — 이중 회계 차단

문제 축 수치의 정본 = **`docs/data/problem_bank_coverage_2026-08.json`**(ARCH-28 도구 산출물·
결정론·재현 명령 그 문서 §0). 이론 축 수치의 정본 = **부록 ㉮~㉳의 재현 명령**(이 세션에서
전건 실행·구조 검증 완료). 본문 표는 이 두 원천의 전사이며, 어긋나면 원천이 이긴다.

---

## §1. 전수 대조 — 과목 × 콘텐츠 축

### 표1. 문제 파트 5축 (2022 개정 19과목 — 정본: coverage_2026-08.json)

"주과목"=첫 성취기준 코드 귀속(합계 2,647 [→ §7-Δ1: 현행 2,638]·문항 단위 속성의 분모), "참조"=해당 과목 코드를 가진
문항 태그 수(중복 가산·도구 `problems_per_subject`). 밴드=6밴드 중 실존 종수(주과목 기준).

| 과목 | 주과목 문항 | 참조 | 성취기준 커버 | 커버율 | 밴드 | 유형 태깅 | 판정 |
|---|---:|---:|---:|---:|---:|---:|---|
| 9수 (중학) | 955 | 1,267 [→ §7-Δ7: 1,266] | 23/60 | 38.3% | 2종 | 809/955 | 최다 — 그러나 사다리 2밴드 |
| 12대수 | 513 | 537 | 9/18 | 50.0% | 3종 | 375/513 | 상대 최선 |
| 12미적Ⅰ | 445 | 517 [→ §7-Δ7: 509] | 5/20 | 25.0% | 3종 | 300/445 | 코드 편중(2코드 445참조) |
| 10공수1 | 220 | 220 | 6/19 | 31.6% | 3종 | 220/220 | killer 120 포함 |
| 6수 (초5~6) | 144 | 192 | 8/45 | 17.8% | 2종 | 144/144 | |
| 10공수2 | 120 | 120 | 5/20 | 25.0% | 2종 | 120/120 | |
| **12확통** | **82** | **154** | 4/16 | 25.0% | 2종 | 82/82 | **34문은 S4-16 승격 대기** |
| 12직수 | 72 | 96 | 3/18 | 16.7% | 2종 | 72/72 | |
| **12미적Ⅱ** | **24** | **96** | 5/23 | 21.7% | 2종 | 24/24 | 수능 선택인데 상징적 |
| **12기하** | **24** | **48** | 2/14 | 14.3% | 2종 | 24/24 | 수능 선택인데 상징적 |
| 4수 (초3~4) | 24 | 24 | 1/47 | **2.1%** | 2종 | 24/24 | 사실상 미커버 |
| 12수문 | 24 | 24 | 1/16 | 6.2% | 2종 | 24/24 | |
| 10기수1 | 0 | 24 | 1/17 | 5.9% | — | — | 부태그-only |
| 10기수2 | 0 | 96 | 4/17 | 23.5% | — | — | 부태그-only |
| 12인수 | 0 | 24 | 1/15 | 6.7% | — | — | 부태그-only |
| **2수 (초1~2)** | **0** | **0** | **0/29** | **0.0%** | — | — | **0문** |
| **12경수** | **0** | **0** | **0/18** | **0.0%** | — | — | **0문** |
| **12실통** | **0** | **0** | **0/13** | **0.0%** | — | — | **0문** |
| **12수과** | **0** | **0** | **0/10** | **0.0%** | — | — | **0문** |

**전 과목 공통 결함 3종**(과목별 표와 별개로 축 전체가 깨져 있음):
- **질문형식 2/10종** — 전 과목이 객관식·단답형뿐. **합답형(ㄱㄴㄷ) 0건**은 페르소나 A(일반고
  고3)의 실제 수능 형식 부재다.
- **난이도 사다리 부재** — 인지~숙달 4밴드를 모두 가진 과목이 **0개**(최다 3종). 단원 기준으로도
  60개 단원이 24문 균일·1~2밴드다.
- **인지행동 유형 8/17종** — 0커버 9종(`prove-statement`·`construct-object`·`infer-relationship`
  등 사고력·증명 계열). `rephrased_v0` 429문은 유형 미태깅.

### 표2. 이론 파트 6축 (원자 = `atom_graph_v1` 세부개념 1,823)

| 축 | 초등 | 중학 | 고등(2022 15과목) | 대학(32과목) | 판정 |
|---|---:|---:|---:|---:|---|
| ⑴ 원자 노드 | 382 (4영역) | 180 (4영역) | 749 — 전 과목 존재(미적Ⅱ 67~수과탐 30) | 512 | **빈 과목 없음** |
| ⑵ 이론 본문(핵심명제/정의 원문) | **0** | **0** | **0** | 512 | K-12 1,311 전량 redaction(§2-③) |
| ⑶ 개념 콘텐츠(은유·정식정의·설명 등 5종) | 119 | 60 | 258 (17라벨) | 409 | 437 레거시 개념 단위 — 원자 대비 **1/3 해상도**(크로스워크 fanout 3.1로 도달 100%) |
| ⑷ definition/intuition/example chunk | 0 | 0 | 0 | 0 | **전 축 0** — S4-05 todo 승계 |
| ⑸ 성취수준(A~E)·평가기준(상/중/하) | 0 | 0 | 0 | — | HEAD 기준 0 — CUR-03 실물 미병합(§0-③) [→ §7-Δ3: CUR-05가 추적] |
| ⑹ 암기카드(보유 개념) | 22 | 20 | 63 | 409(1:1) | 고등은 **기하 1개념**·경수/직수/기본수1·2/인수/수문/실통/수과탐 **0** |
| (참고) 검수 상태 | — | — | — | — | K-12 437 전량 `ai_estimated`·**reviewed 0** / 대학 409 전량 **`review_status=None`(필드 부재)** |
| (참고) 학습목표 분해 | 0 | 0 | 1 소단원 | 0 | 895 성취기준 대비 소단원 DSL 1건(`quadratic_maxmin`) — CUR-02 관측 완료 |

고등 과목별 세부: 원자는 15과목 모두 30~67개로 고르게 존재하는 반면, 개념 콘텐츠는 미적Ⅱ 23·
공수2 22·공수1 21·미적Ⅰ 20·대수 18·경수 18·직수 18·기본수1 17·기본수2 17·**확통 16·수문 16·
인수 15·기하 14·실통 13·수과탐 10**으로 원자의 1/3 수준이고, 진로·융합선택군은 카드 0이다.

**이론 파트의 진짜 공백은 "과목"이 아니라 "본문 신뢰 축"이다**: 노드·진단·소크라테스는 전 과목
100%인데 ⑵정의 원문 0(저작권 설계) ⑶해상도 1/3 ⑷chunk 0 ⑸성취수준 0 (참고)검수 0이 겹쳐,
**학생에게 내보낼 수 있는(검수·저작권 안전) 이론 서술이 사실상 0건**이다.

### 2015 개정 축 (참고 — §2-④)

2015 개정 성취기준 460건 중 원자 매핑 **153건**(초·중 4과목+확통 — 전부 2022와 코드 공유분).
2015 **고등 전용 8과목**(10수학·12수학Ⅰ/Ⅱ·12미적·12고수Ⅰ/Ⅱ·12심수Ⅰ/Ⅱ)은 원자 0이고,
2015 기하·경제수학·실용수학·수학과제탐구·인공지능수학은 성취기준 레코드 자체가 대장에 없다.

---

## §2. 의도적 미채택 판정 (5건 — 공백이 아니라 결정)

| # | 항목 | 판정 근거 (협상 불가 축) |
|---|---|---|
| ① | `Problem.subject` enum 정정·백필 | **E1-02 승계**(`subject_expansion_readiness.md` §7 보류 대장). 과목 관측은 대장 `subject` 유도(ARCH-28)로 이미 충분하고, 소비처는 무변별 필터 1건뿐이라 지금 enum 확장+2,647 백필은 스키마 변경 비용만 낳는다. E1-02 notes에 승계 부기 완료(§3 승계 표) |
| ② | 이론 커버리지 **상시** 관측 도구 신설 | 소비처 0(문제 축은 저작 큐 S4-01·R7이 소비자 — 이론 축은 아직 없음). 부록 ㉮~㉳ 재현 명령으로 충분. 발화 조건 §5-① |
| ③ | K-12 원자 1,311 핵심명제 redaction | 공백이 아니라 **저작권 설계**(2026-06-21 결정 로그: NCIC 성취기준 본문 근접 복제 차단·"연결성취기준 코드로 다리·대학은 자체작성 보존"). 해소 경로는 원문 복원이 아니라 **자체 저작 정의 레지스터(S4-05)**다 — 이 축을 "빠졌다"고 등재하면 저작권 금기 위반 |
| ④ | 2015 개정 고등 전용 과목 원자·문항 0 | 원자 백본은 2022 체계 마스터에서 생성(2026-06-21 결정·2015는 standards 대장 병존 보존). 제품 Phase 1 우선 코호트가 **고1 공통수학·고2 일반선택**(`docs/data/ncic.md` §Phase 1) = 2022 개정 학년이고, 2015 잔존 코호트는 중3·고3뿐(2027 전면 2022 — `curriculum_2022_revision.md`). 2015 전용 저작은 하지 않는다. 발화 조건 §5-④ |
| ⑤ | 대학 콘텐츠 축(32과목 1,069노드·콘텐츠 409) 심화 점검 | 이번 범위 밖 — K-12 학생 노출 경로가 먼저다. 대학 `review_status=None`(필드 부재)은 §정정-ⓒ에 사실만 기록 |

---

## §3. 진짜 갭 설계 (D1~D3)

### D1. 커버리지 도구에 과목 축이 없다 → **ARCH-28 (신규 등재·본 세션 실행 완료)**

- **문제**: "과목별 빠진 부분"을 관측하는 정본 축이 없었다 — ARCH-18 도구(`problem_bank_
  coverage.py`)는 성취기준 코드·학교급·영역·단원×난이도·유형 축만 냈고, 과목별 집계는 매번
  수기 파싱이었다. 리포트 자체도 2026-07-29 이후 stale(6종 2,667 기준·`probability_finite_v0`
  미반영·구 최다 코드 `[10공수1-02-02]` 517→실측 27로 재태깅까지 일어났는데 문서는 옛 수치).
- **왜 지금까지 안 드러났는가**: 기존 갭 리뷰가 전부 *모듈* 축(문제은행·교육과정·지식…)이라
  *과목* 축 질문("확통 문항 몇 개인가")을 던진 문서가 없었다. `Problem.subject`가 있으니 과목
  축이 있는 줄 알기 쉬운데 실측 카디널리티 1이라 무효였다(§0-①).
- **정합 설계**: 대장 `subject` 투영으로 `coverage_by_subject`(커버/분모)·`problems_per_subject`
  (참조)·`zero_problem_subjects`(분모>0·커버 0 기계 판별) 3축 추가. 렌더 §1.3·JSON 하위호환.
  코드 prefix 파싱 신설 금지(hermetic — 대장 필드가 유일 원천).
- **변별력**: fixture에서 특정 과목 문항을 제거하면 `zero_problem_subjects`에 나타나고 복원하면
  사라지는 **양방향** 테스트(`test_zero_problem_subject_detection_is_bidirectional`).
- **집행 지점**: 리포트 재생성 `coverage_2026-08.{md,json}` + 구본 supersede 주기. CI 재생성
  배선은 **PB-02 acceptance ③ 소관 — 여기서 하지 않는다**(중복 등재 금지).
- **태스크**: `ARCH-28-coverage-subject-axis` — 이 세션에서 add→start→구현→done. (제안 ID
  ARCH-27은 CLI가 번호 충돌로 거부 — `ARCH-27-comparison-derivative-sealing-gate` 선점 —
  제안 번호 ARCH-28 수용, HARN-10 준수.)

### D2. 이론 콘텐츠 검수 승격 경로가 무주공산이다 → **KG-02 (신규 등재·실행은 후속)**

- **문제**: 학생 대면 이론 텍스트의 유일 원천인 `concept_content_v1` 437건이 **전량
  `ai_estimated`·reviewed 0**인데, ai_estimated→reviewed **승격 배치는 어느 태스크도 추적하지
  않는다**(backlog 224건 전수 확인 — S3-26 ③은 review_status *축 도입*까지, S2-05는 *문항*
  30문 AI 검수 전환까지). KG-01이 만든 관측(`/concepts/search?reviewed_only=true` 결과 0)은
  분모만 세고 있고, 채우는 실행이 없다 — "완비된 소비 경로 + 미도달 공급원" 계열의 이론판.
- **왜 지금까지 안 드러났는가**: 검수 축이 세 태스크(S3-26 축 도입·S2-05 문항 검수·KG-01
  관측)에 걸쳐 각자 "자기 조각은 done"이라, 사이의 승격 실행이 어디에도 속하지 않았다.
- **정합 설계(acceptance 4항)**: ① 437건 표본 검수 배치 — S2-05 ①~⑥ 판정 축·Wilson min-n
  샘플링(`superhuman_verification_standard.md` 게이트 CLI 관례) ② **AI 자기승인 금지**
  (`knowledge_module_gap_review.md` §2-③ 협상 불가) — 승격 권위는 사람 검수 경유 또는 결함
  주입 강등전을 통과한 기계 게이트만. 문항 선례(2026-07-10 Kiki 결정·S4-16 강등전)와 동형으로
  실 LLM 필요 시 Kiki 머신 동반 ③ PASS 스코프만 `review_status` 결정론 각인(사람 인상 입력
  경로 0 — PB-03 축② 선례) 후 `reviewed_only=true` 재측정 N>0(KG-01 ③ 축 소비) ④ 미통과분
  ai_estimated 유지 + 결함 목록 산출(침묵 승격 금지).
- **변별력**: 결함 주입 표본(오류 정의 삽입)이 검수 배치에서 실제로 FAIL로 나오는지 — 성공/
  실패 양쪽 같은 값이면 위장.
- **태스크**: `KG-02-concept-content-review-promotion` (아래 등재 요약).

### D3. 저작 우선순위에 과목 축이 없다 → **페이퍼 — R7 v2 증보 (태스크 신설 없음)**

R2 §3 R7(저작 우선순위 v1)이 페이퍼로 남긴 우선순위에 **과목 축을 증보**한다. 실행 태스크를
신설하지 않는 이유: 저작 실행의 소비처인 `S4-01`이 여전히 `S3-01-pilot-cohort`에 잠겨 있고
(R7 v1의 잠금 사유 불변), S4-01 acceptance가 "초·중·**고**+대학 4축"이라 고등 선택과목 확충도
그 범위 안이다 — 신규 등재는 중복이 된다(S4-01 notes에 승계 부기로 갈음).

**저작 우선순위 v2 (과목 축·관측 근거 = coverage_2026-08.json)**:
1. **0문 4과목 최소 저작** — 2수(29코드)·12경수(18)·12실통(13)·12수과(10). 과목당 1문이면
   "0문 과목"이 사라지는 저비용·고가시성. 선결 분류: 12실통·12수과(통계·탐구 계열)는 S4-13
   개통 경로(유한 표본공간 전수검증 — `probability_finite_v0` 선례) 또는 후속 경로 필요,
   2수·12경수는 산술·함수 계열이라 기존 SymPy 경로로 가능.
2. **수능 선택 3과목 하한** — 12확통(공개 120+대기 34)·12기하(48)·12미적Ⅱ(96 참조). 페르소나
   A의 선택 축인데 대수·미적Ⅰ의 1/4~1/10. 12확통은 **S4-16 강등전 승격이 저작보다 먼저**다
   (34문이 이미 만들어져 게이트 대기 중 — 새로 만들 것부터 승격할 것). 12기하는 SymPy 검증
   경로 미개통(S4-13 후속)·시각화 연계(S4-03 발화 조건 "확률과통계·수열 커버리지 착수 시").
3. **부태그-only 3과목 주태그 저작** — 10기수1/2·12인수: 참조만 있고 주과목 문항 0.
4. (v1 승계) 영역 0% 블록·난이도 사다리 계열화·합답형(ㄱㄴㄷ)·유형 0커버 9종(증명·구성 계열은
   S4-02 선결)·`[9수02-20]` 379문에 추가 저작 금지(신 최다 코드 — v1의 `[10공수1-02-02]` 자리).

### §3 등재·승계 요약

| 구분 | 항목 | track / stage / priority | 근거 |
|---|---|---|---|
| 신규 (완료) | `ARCH-28-coverage-subject-axis` | infra-debt / S4 / 3 | D1 — 본 세션 add→done |
| 신규 | `KG-02-concept-content-review-promotion` | math-completion / S4 / 4 | D2 |
| 승계 | `PB-02`(CI 3/7→7/7·리포트 재생성 CI) | 기존 todo | acceptance ①·③이 문자 그대로 커버. 단 acceptance ①의 `ci.yml:1044-1048`은 현재 **1112-1116**으로 라인 드리프트(내용 동일) |
| 승계 | `S4-01`(K-12 완성 — 저작 실행) | 기존 todo·S3-01 잠금 | D3 페이퍼의 소비처. notes에 본 문서 참조 부기 |
| 승계 | `E1-02`(Problem.subject_area) | 기존 todo·E축 | §2-① — notes에 카디널리티 1 실측 부기 |
| 승계 | `S4-05`(정의 레지스터)·`CUR-03`(성취수준 회수) | 기존 | 표2 ⑷·⑸ — chunk·성취수준 축의 기존 추적. CUR-03은 §0-③ 미병합 회수가 실 잔여 |
| 페이퍼 | 저작 우선순위 v2 | — | D3 (**페이퍼 — 코드 0 · 태스크 신설 없음**) |

---

## §4. 정직한 공백 — 지금 하지 않는 것 (6종)

| # | 항목 | 이 세션에서 안 하는 이유 | 해소 시점 |
|---|---|---|---|
| 1 | 문항 대량 저작(0문 4과목·선택 3과목·초등) | LLM 생성 파이프라인+검증 게이트 필요·S4-01이 S3-01에 잠김 | S4-01 착수 시(D3 v2가 입력) |
| 2 | 이론 텍스트 저작(원자 해상도 1,311·chunk) | S4-05가 정의 레지스터 스키마 선결 | S4-05 착수 시 |
| 3 | KG-02 검수 배치 *실행* | 실 LLM(Kiki 머신) 또는 사람 검수 필요 — 등재만 | KG-02 착수 시 |
| 4 | CI 재검증 3/7→7/7·리포트 재생성 CI | PB-02 소관(중복 금지) | PB-02 착수 시 |
| 5 | CUR-03 실물(성취수준) 회수 병합 | 미병합 브랜치 처분은 Kiki 결정 대기 축(세션 브리핑의 "장기 미머지" 대장) | Kiki 회수 결정 시 |
| 6 | 12확통 34문 승격 | S4-16이 별도 세션 in_progress(파일 겹침 경고 실측) — 착수 금지 | S4-16 완료 시 |

---

## §5. 유보 항목의 발화 조건

| # | 유보 항목 | 발화 트리거 |
|---|---|---|
| ① | 이론 커버리지 상시 관측 도구(표2의 기계화) | S4-05 chunk 착지 **또는** S4-01 착수로 이론 저작 큐 소비처가 생길 때 — 그 전에는 부록 명령으로 충분 |
| ② | 저작 우선순위 v2의 실행 승격 | `S3-01-pilot-cohort` clear(S4-01 잠금 해제) **또는** Kiki가 파일럿 전 선행 저작을 결정할 때 |
| ③ | `Problem.subject` 정정(subject_area 도입) | E1-02 착수 시(트리거: 물리 문항 첫 적재 — `subject_expansion_readiness.md` §7) |
| ④ | 2015 개정 전용 콘텐츠(고등 8과목) | 2015 잔존 코호트(현 고3 — 페르소나 A)를 런칭 타깃으로 삼는 제품 결정이 내려질 때. 현 Phase 1 우선은 2022 학년(고1·고2)이라 미발화 |

---

## §6. 반복 실수 — 재발방지 점검 (CLAUDE.md 의무)

**"정본 산출물 stale 방치" 계열의 재확인(신규 등재 없음)**: 커버리지 리포트 stale은 R2 §0-②-바
가 이미 지적했고 구조 대책(재생성 CI)은 **PB-02가 정본**이다 — 이번에 데이터 카드 2곳
(§정정-ⓐⓑ)을 추가 발견했지만 같은 계열이므로 규칙 신설 없이 PB-02 승계로 갈음한다(중복 등재
금지). 이번 세션 자체 실수 중 재발방지 등재 요건(시스템 결함·동일 유형 2회+)에 해당하는 것은
없었다 — 태스크 ID 충돌(ARCH-27)은 HARN-10 가드가 설계대로 차단·제안 번호 수용으로 처리됐다
(가드 정상 작동 사례·사고 아님).

---

## §정정 — stale 정본 3곳 + 사전 조사 정정 2건

| # | 위치 | 기재 | 실측 (2026-08-10) | 처리 |
|---|---|---|---|---|
| ⓐ | `docs/data/problem_bank_corpus_v1.md` | 6종 2,613문 | **7종 2,647문**(`probability_finite_v0` 34 누락) | ~~본 커밋에서 정정~~ **[→ §7-Δ2: 철회]** — main R3(#776)가 선행 수행. 회수 커밋은 대신 2,638로 **재**정정 |
| ⓑ | `docs/data/atom_graph_v1.md` | 노드 2,697·원자 1,837 | **2,683·1,823**(2026-07-28 dedup 병합 14) | 본 커밋에서 정정 |
| ⓒ | `docs/data/problem_bank_coverage_2026-07.md` | 72/435(16.6%)·최다 `[10공수1-02-02]` 517 | 78/435(17.9%)·최다 `[9수02-20]` 379 | supersede 주기 완료(본문 불변·이력 보존) — 현행 정본은 2026-08판 |
| ⓓ | (사전 조사 정정) CUR-03 "todo·0건" | status=**done**·실물 미병합(§0-③) | 본 문서에 정정 기록 |
| ⓔ | (사전 조사 정정) 암기카드 "113건" 단위 | 카드 **113장** / 보유 개념 **105개**(대학은 409·1:1) — 두 단위 구분 | 본 문서 표2에 구분 표기 |

(참고) 대학 콘텐츠 409건은 `review_status` 필드 자체가 없다(None 409) — K-12의 `ai_estimated`
표기와 다른 상태임을 KG-02 설계 시 반영(스코프는 K-12 437 우선).

---

## 부록 — 실측 재현 명령 (HEAD `b3e3708c` · 2026-08-10 전건 실행 검증)

**㉮ 문제 축 전체(정본)**: `docs/data/problem_bank_coverage_2026-08.md` §0 참조 —
```bash
cd src/backend
python -m whymath_backend.harness.problem_bank_coverage \
    --json ../../docs/data/problem_bank_coverage_2026-08.json
```

**㉯ 원자 노드·핵심명제 redaction·진단 100%** (표2 ⑴⑵·§0-②):
```bash
python3 - <<'EOF'
import json
from collections import Counter
g = json.load(open('data/corpus/atom_graph_v1/graph.json'))
nodes = g['concepts'] if 'concepts' in g else g['nodes']
atoms = [n for n in nodes if n['level'] == '세부개념']
print('노드', len(nodes), '| 레벨', dict(Counter(n['level'] for n in nodes)))
print('세부개념 학교급', dict(Counter(n['school_level'] for n in atoms)))
hs = [n for n in atoms if n['school_level'] == '고등']
print('고등 과목별', dict(sorted(Counter(n['subject_area'] for n in hs).items(), key=lambda kv: -kv[1])))
print('핵심명제 채움', dict(Counter(bool((n.get('core_proposition') or '').strip()) for n in atoms)))
for f in ('misconception', 'diagnostic_item', 'socratic', 'transfer'):
    print(f, sum(1 for n in atoms if (n.get(f) or '').strip()), '/', len(atoms))
EOF
```
→ 노드 2,683(세부개념 1,823·소단원 643·단원 217) · 학교급 초 382/중 180/고 749/대 512 ·
고등 15과목(미적Ⅱ 67 ~ 수과탐 30) · 핵심명제 False 1,311/True 512 · 4요소 1,823/1,823.

**㉰ 개념 콘텐츠·검수·암기카드** (표2 ⑶⑹·검수 축):
```bash
python3 - <<'EOF'
import json
from collections import Counter
c = json.load(open('data/corpus/concept_content_v1/content.json'))['content']
print(len(c), dict(Counter(i.get('review_status') for i in c)))
print(dict(sorted(Counter(i.get('subject') for i in c).items(), key=lambda kv: -kv[1])))
fc = [i for i in c if i.get('flashcards')]
print('카드 보유 개념', len(fc), '| 장수', sum(len(i['flashcards']) for i in fc),
      '|', dict(sorted(Counter(i.get('subject') for i in fc).items(), key=lambda kv: -kv[1])))
u = json.load(open('data/corpus/concept_content_university_v1/content.json'))['content']
print('대학', len(u), dict(Counter(i.get('review_status') for i in u)))
EOF
```
→ 437 전량 ai_estimated · 과목 분포(§1 세부) · 카드 보유 105/장수 113(기하 1) · 대학 409
전량 None.

**㉱ 2015 개정 원자 매핑** (§1 참고 절):
```bash
python3 - <<'EOF'
import json
from collections import Counter
g = json.load(open('data/corpus/atom_graph_v1/graph.json'))
nodes = g['concepts'] if 'concepts' in g else g['nodes']
atom_std = {c for n in nodes for c in (n.get('standard_codes') or [])}
s = json.load(open('data/corpus/standards_v1/standards.json'))['standards']
sub = [x for x in s if x['curriculum_revision'] == '2015 개정']
mapped = [x for x in sub if x['code'] in atom_std]
print(len(mapped), '/', len(sub), '| 매핑 0 과목:',
      sorted({x['subject'] for x in sub} - {x['subject'] for x in mapped}))
EOF
```
→ 153/460 · 매핑 0 과목 8종(10수학·12고수Ⅰ/Ⅱ·12미적·12수학Ⅰ/Ⅱ·12심수Ⅰ/Ⅱ).

**㉲ chunk·학습목표·성취수준·시각화·평가 인덱스** (표2 ⑷⑤·참고):
```bash
ls data/corpus/units_v1/*.unit.yaml            # → 1건 (quadratic_maxmin)
ls data/corpus/*criteria* 2>/dev/null          # → 없음 (성취수준 코퍼스 HEAD 부재)
python3 -c "import json; print(len(json.load(open('data/corpus/concept_assessment_v1/index.json'))['entries']))"   # → 61
git merge-base --is-ancestor 98a34695 HEAD; echo $?   # → 1 (CUR-03 artifact 미병합)
```
chunk 축은 `knowledge_module_gap_review.md` §4 실측 판정("`chunk_type` 필드 0건") 승계 —
DB 축이라 이 세션 재실측 불가·문서 정본 인용.

**㉳ 크로스워크 도달** (표2 ⑶ 각주):
```bash
python3 -c "
import json
cw = [json.loads(l) for l in open('data/corpus/concept_atom_crosswalk_v1/crosswalk.jsonl') if l.strip()]
un = [c for c in cw if not c.get('atom_codes')]
print(len(cw), 'unmapped', len(un), 'fanout', round(sum(len(c.get('atom_codes') or []) for c in cw)/len(cw), 1))"
```
→ 437건 · unmapped 0 · fanout 평균 3.1.

---

## §7. 현행 재검증 (2026-08-11 · HEAD `833f46af` · 회수 시점)

이 문서는 2026-08-10에 작성됐으나 **main에 착지하지 못한 채 고립**돼 있었다(브랜치
`claude/subject-problems-theory-check-7n9n72` — 미병합 고립 5회차). 2026-08-11에 파일 단위
재적용으로 회수하면서 §0~§6 본문은 **보존**하고(1차 판정의 이력 가치), 그 사이 main에서
일어난 변화만 아래 Δ로 정정한다. 본문의 stale 수치에는 인라인 `[→ §7-Δn]`을 달았다.

> **회수 범위**: 원 브랜치는 단독 커밋 34건이지만 이번에 회수한 것은 **2커밋**(`98fb462b`
> ARCH-28 · `19944820` 본 문서)뿐이다. 나머지 32건(MISC-01~06 · ASM-06 · S3-32/33/34 ·
> PED-14/15 · CUR-03 · PB-02)은 **각자 다른 태스크의 인플라이트 작업**이라 범위 밖이며,
> 원 브랜치는 삭제 대상이 아니다.

| Δ | 항목 | 1차(2026-08-10 · `b3e3708c`) | 현행(2026-08-11 · `833f46af`) | 처리 |
|---|---|---|---|---|
| **Δ1** | 문항 총계 | 7종 **2,647** | 7종 **2,638** | `QUAL-02`(PR #777·`50b43b6e`)가 실중복 9쌍을 판정해 **9레코드 은퇴**. `git show --numstat 50b43b6e -- data/corpus/`: `generated_v0` net −1 · `rephrased_v0` −8 → 2,647−9=2,638(잔차 0). 1차 수치는 *그 시점 기준으로 정확*했다 — 오류가 아니라 시점 차 |
| **Δ2** | §정정-ⓐ(`problem_bank_corpus_v1.md` 6종 2,613→7종 2,647) | 이 문서가 정정 예정으로 등재 | **철회** — main R3(PR #776)가 2026-08-11에 **선행 수행** | 중복 정정 회피. 단 그 배너의 "2,647"이 Δ1로 다시 stale이 돼, 회수 커밋에서 **2,638로 재정정**하고 2단계 인과(S4-13 +34 → QUAL-02 −9)를 명기 |
| **Δ3** | §0-③ CUR-03 실물 미병합 | "회수 대기 + HEAD 0건" | 상태 동일하나 **추적 좌석 신설** — main에 `CUR-05-achievement-criteria-corpus-recovery` 등재 | §4-5의 "해소 시점: Kiki 회수 결정 시"를 **`CUR-05` 소관**으로 갱신 |
| **Δ4** | §정정-ⓑ(`atom_graph_v1.md` 2,697/1,837→2,683/1,823) | 이 문서가 수행 | main 미변경 → **원문 그대로 유효** | 회수분 그대로 착지 |
| **Δ5** | 커버 판정 | 78/435(17.9%) · 0문 4과목 · 0커버 영역 24 | **78/435(17.9%) · 0문 4과목 · 24** | **판정 뒤집기 0.** 은퇴 9건이 전부 *이미 커버된 코드의 중복분*이라 커버 집합을 바꾸지 않았다. §1 표1의 갭 판정과 §3 D1~D3 설계는 **전량 유효** |
| **Δ6** | `KG-02` 상태 | 신규 등재(`todo`) | **`blocked`** | 원 브랜치 후속 커밋 `c17b7f1d`가 차단 전환(실 LLM provider 부재 + `S4-16`의 `agreement_gate*.py` 점유). 2026-08-11 재확인 결과 S4-16은 여전히 in_progress → **차단 사유 승계**. 동시에 스코프를 437→**846**으로 확대(§8-③ 근거) |
| **Δ7** | §1 표1의 과목별 "참조" 2곳 | 9수 1,267 · 12미적Ⅰ 517 | 9수 **1,266** · 12미적Ⅰ **509** | Δ1의 −1/−8이 정확히 이 두 과목에 떨어졌다(`generated_v0`→9수, `rephrased_v0`→12미적Ⅰ). 커버율·밴드·유형 태깅 판정은 불변 |

**§0-④ 수치 정본 선언은 그대로 유효하다** — 문제 축의 정본은
`docs/data/problem_bank_coverage_2026-08.json`이며, 회수 시 HEAD에서 **재생성**했다(체크아웃하지
않았다). 본문 표와 어긋나면 원천이 이긴다.

---

## §8. 대학 콘텐츠 축 증보 — §2-⑤ 유보 해제 (2026-08-11)

§2-⑤는 대학 축(32과목·1,069노드·콘텐츠 409) 심화 점검을 "이번 범위 밖 — K-12 학생 노출 경로가
먼저다"로 유보했다. **Kiki 요청("초에서 대학교까지 학교별 과목별 이론·문제 완비 체크")이 그 유보
근거를 명시적으로 뒤집었으므로** 이 절에서 해제한다. 측정 HEAD `833f46af`, 재현 명령은 부록 ㉴~㉷
(전건 실행 검증 완료).

### §8-① 전제 — 대학 과목 축의 정본

K-12에서 과목 축의 정본이 성취기준 대장 `subject`였던 것(§0-①)과 동형으로, 대학 축의 정본은
`data/corpus/standards_university_v1/standards.json`의 `subject`(**32종·409레코드 전량 채움**)이며
원자 노드의 `subject_area`(대학 32종)와 **완전 일치**한다.

K-12와 결정적으로 다른 점: **`Problem` 축과의 교차가 아예 0이다.** 대학 성취기준 코드
409종(`CALC`·`ANAL`·`LINA`·`AALG`·`TOPO`… 26 접두) 중 하나라도 참조하는 문항은
**0 / 2,638**이다(㉷). K-12는 "커버율이 낮다"였지만 대학은 "**축이 연결된 적이 없다**"이다.

### §8-② 표3. 대학 32과목 × 6축 전수 대조 (부록 ㉴ 산출)

| 과목 | 단원 | 소단원 | 세부개념 | 콘텐츠 | 성취기준 | 링크 |
|---|---:|---:|---:|---:|---:|---:|
| 미적분학 I | 7 | 32 | 61 | 32 | 32 | 32 |
| 미적분학 II | 6 | 30 | 45 | 30 | 30 | 30 |
| 해석학 I | 5 | 19 | 26 | 19 | 19 | 19 |
| 집합과 논리 | 5 | 18 | 36 | 18 | 18 | 18 |
| 선형대수학 I | 5 | 17 | 33 | 17 | 17 | 17 |
| 해석학 II | 5 | 15 | 16 | 15 | 15 | 15 |
| 미분방정식 | 5 | 14 | 16 | 14 | 14 | 14 |
| 선형대수학 II | 5 | 14 | 15 | 14 | 14 | 14 |
| 복소해석학 | 5 | 14 | 15 | 14 | 14 | 14 |
| 수치해석 | 5 | 14 | 15 | 14 | 14 | 14 |
| 현대대수학 I | 5 | 14 | 18 | 14 | 14 | 14 |
| 미분기하학 | 5 | 13 | 13 | 13 | 13 | 13 |
| 위상수학 I | 5 | 13 | 14 | 13 | 13 | 13 |
| 현대대수학 II | 5 | 13 | 13 | 13 | 13 | 13 |
| 실해석학(측도론) | 5 | 13 | 13 | 13 | 13 | 13 |
| 조합론그래프이론 | 4 | 13 | 15 | 13 | 13 | 13 |
| 함수해석학 | 5 | 12 | 12 | 12 | 12 | 12 |
| 확률론 | 5 | 11 | 13 | 11 | 11 | 11 |
| 미분다양체리만기하 | 5 | 11 | 11 | 11 | 11 | 11 |
| 암호론코딩이론 | 4 | 11 | 11 | 11 | 11 | 11 |
| 편미분방정식 | 5 | 11 | 11 | 11 | 11 | 11 |
| 정수론 입문 | 4 | 10 | 11 | 10 | 10 | 10 |
| 집합론 | 4 | 9 | 9 | 9 | 9 | 9 |
| 수리통계학 | 4 | 9 | 9 | 9 | 9 | 9 |
| 위상수학 II | 4 | 8 | 8 | 8 | 8 | 8 |
| 갈루아 이론 | 4 | 8 | 9 | 8 | 8 | 8 |
| 금융수학 | 4 | 8 | 8 | 8 | 8 | 8 |
| 대수적 위상수학 | 4 | 8 | 9 | 8 | 8 | 8 |
| 수리논리 | 4 | 8 | 8 | 8 | 8 | 8 |
| 정수론(심화) | 4 | 8 | 8 | 8 | 8 | 8 |
| 대수기하 입문 | 4 | 7 | 7 | 7 | 7 | 7 |
| 졸업세미나학사논문 | 2 | 4 | 4 | 4 | 4 | 4 |
| **합계 (32과목)** | **148** | **409** | **512** | **409** | **409** | **409** |

**문항 열은 표에 넣지 않았다 — 32과목 전부 0이기 때문이다**(0을 32번 적는 것은 정보가 아니다).

판정 ①: **빈 과목이 하나도 없다.** 32과목 전부 단원·소단원·세부개념·콘텐츠·성취기준·링크를
갖는다. K-12에서 나온 "0문 4과목" 같은 *구멍 뚫린 과목*은 대학 축에 없다.

판정 ②: **소단원 = 콘텐츠 = 성취기준 = 링크가 전 과목에서 1:1:1:1이다**(409 네 번). 이는 세
자산이 **같은 생성 배치에서 한꺼번에 만들어졌다**는 뜻이지, 서로를 독립적으로 검증한다는
뜻이 아니다 — K-12의 crosswalk(437↔1,311·fanout 3.1·confidence 절반이 0.5~0.8)와 달리
대학은 대조로 검출할 불일치가 **구조적으로 존재할 수 없다**. 상호 검증력 0.

판정 ③: 콘텐츠 해상도는 **소단원 단위**(409)이고 세부개념은 512다. K-12의 1:3 희석(§1 표2 ⑶)
보다는 낫지만, **세부개념 103건은 자기 콘텐츠 없이 소단원 설명을 공유**한다.

### §8-③ 표4. 대학 이론 신뢰 축 — 코퍼스층과 소비층이 어긋나 있다

| 축 | 대학 409/512 실측 | K-12 대조 | 판정 |
|---|---|---|---|
| `review_status`(코퍼스) | **키 자체 부재 0/409** | 437 전량 `ai_estimated` | 대학은 "미검수"조차 표기되지 않음 |
| `review_status`(DB 투영) | **`ai_estimated` 상수 각인** | 동일 | `l1/concept_content/projection.py:196` |
| `standard_codes`(콘텐츠) | **0/409**(키 부재) | 437 전량 채움 | 콘텐츠→성취기준 역참조 불가 |
| `core_proposition`(노드) | **512/512 (100%)** | **0/1,311**(redaction) | **상보** |
| `transfer_example`(노드) | **0/512** | 1,311/1,311 (100%) | **상보** |
| `misconception`·`diagnostic_item`·`socratic`·`transfer` | 512/512 (100%) | 100% | 동일 |
| `redacted_fields` | 전량 빈 값 | K-12는 핵심명제 redaction | 대학은 자체작성이라 저작권 제약 없음 |

**핵심 발견 — 층위 불일치**: 코퍼스에는 `review_status` 필드가 *없는데*,
`projection.py:196`이 K-12·대학을 **구분 없이** `CONTENT_REVIEW_STATUS_AI_ESTIMATED` 상수로
각인한다. 그래서 `/concepts/search?reviewed_only=true` 같은 소비 경로에서 대학 409는 K-12 437과
**동일 취급**된다. 1차 문서(§정정 참고)가 "대학은 필드 부재라 별도 판단"이라 적은 것은
*코퍼스층*에서는 옳지만 *소비층*에서는 성립하지 않는다 — 이 발견으로 `KG-02` 스코프를
437→**846**으로 확대했다(Δ6·§8-⑦).

또한 대학 성취기준 provenance는 **스스로** "와이매스 자체작성 … AI 추정 초안으로 수학 전문가
검수가 필요"라고 고지한다(`standards_university_v1/_provenance.json`). K-12의 NCIC 공공누리
대장과 달리 **외부 권위가 전혀 없는 자체 생성물**이라, 검수 필요성은 K-12보다 오히려 높다.

### §8-④ 표5. 대학 위상 — 32개 고립 사슬 (부록 ㉶)

| 항목 | 실측 |
|---|---:|
| 대학 내부 엣지 | **481** (전량 `prerequisite`) |
| ├ 같은 과목 안 | **479** |
| └ 과목 간 | **2** |
| **고등 ↔ 대학 경계 엣지** | **0** |
| 차수 0 노드 | 소단원 409 · 단원 148 (= 컨테이너 557) |

- **고→대 0**은 전 그래프의 학교급 경계 실태(중→고 11 · 초→중 9 · 경계 통과 20/2,210 = 0.90%)의
  극단이다. "초등에서 대학까지"를 **하나의 선수 경로로 traverse하는 것은 성립하지 않는다** —
  대학 512개 세부개념은 K-12 어디에서도 도달 불가능한 별도 섬이다.
- **과목 간 2건**은 32과목이 서로를 선수로 거의 참조하지 않는다는 뜻이다(예: 해석학 I → 해석학 II
  같은 명백한 계열조차 대부분 미연결). 대학 축은 하나의 그래프가 아니라 **32개의 독립 사슬**이다.
- 컨테이너 557의 차수 0은 결함이 아니다 — 계층은 엣지가 아니라 `parent_code`로 매달린다
  (정직 표기: 이 557을 "고립 노드"로 세면 안 된다).

### §8-⑤ 대학 축의 의도적 미채택 (§2 ①~⑤에 이어 ⑥~⑨ 증보)

| # | 항목 | 판정 근거 |
|---|---|---|
| ⑥ | `transfer_example` 0/512 (K-12는 100%) | **소비처 0**. 노드→DB 투영은 되지만 API·L4에 독자가 없다. 비대칭 자체는 사실이나, 채우는 것은 "소비처 없는 추상 미도입"에 걸린다 — 대학 학생 노출 경로가 생길 때 발화 |
| ⑦ | 크로스워크가 대학과 무교차(437↔K-12 1,311만) | **테스트로 동결된 결정**이다 — `tests/backend/l1/concept_atom_crosswalk/test_crosswalk_transfer_governance.py` ④가 "대학 행 무변경 축 분리"를 계약으로 고정. 갭이 아니라 설계 |
| ⑧ | 대학 오개념 독립 카탈로그 0 | `misconceptions_v1` 843건은 **전량 초·중·고**(㉷). 다만 노드 내장 `misconception`은 512/512 채움이라 진단 축은 성립한다. 독립 카탈로그의 소비처는 L4 런타임 탐지(64종)인데 대학 학생 노출 경로 자체가 0 |
| ⑨ | 대학 `grade_band`가 학년이 아닌 트랙 값 | 세부개념만 1학년 175·2학년 93·3학년 118·4학년 126이고 컨테이너 557은 None. K-12의 "1~2학년군" 같은 교육과정 학년군과 **의미가 다르다**. API 소비처 0이라 지금 정규화하지 않고 관측만 기록 |

### §8-⑥ ARCH-28 관측 사각의 자인 (정직 회계)

이 문서 §3 D1이 만든 커버리지 과목 축(`ARCH-28`)은 `DEFAULT_STANDARDS_PATH =
standards_v1/standards.json`만 읽는다. 따라서:

- 리포트의 "**0문 과목 4종**"은 **K-12 19과목 한정**의 4종이다.
- **대학 32과목은 분모에 아예 없다** — 리포트상 "0건"이 아니라 **미관측**이다.

도구에 대학 대장을 얹으면 32행이 전부 `0/N` 으로 나올 뿐이고, 그 관측을 소비할 저작 큐가
존재하지 않는다(대학 문항 0·대학 저작 태스크 0) → **"소비처 없는 추상 미도입"에 의해 미채택**.
대신 **범위 자인을 코드와 리포트 양쪽에 각인**했다(집행 지점 — 정본화와 별항):

1. `problem_bank_coverage.py` §1.3 렌더 머리말 — 분모가 `--standards` 대장 하나뿐이며 대학은
   분모 밖임을 출력물 자체가 말한다.
2. `docs/data/problem_bank_coverage_2026-08.md` 머리말 + §2.1 주석 + §5 "축 자체의 누락".

### §8-⑦ 판정 요약 — 신규 등재 0건

backlog 전수 확인 결과 대학 축의 관측은 **전부 기존 좌석이 있다**:

| 대학 축 관측 | 좌석 | 처리 |
|---|---|---|
| 고→대 0 · 32 고립 사슬 | `CUR-06`(경계 밀도 계측기) + `S4-01`(엣지 저작) | **승계 부기** |
| 대학 문항 0/2,638 · 전용 생성기 0 | `S4-01` acceptance "초·중·고+**대학** 4축" | **승계 부기** (저작 순서는 §3 D3 페이퍼) |
| 대학 이론 검수 무주공산 · 층위 불일치 | `KG-02` | **스코프 437→846 확대**(신설 아님) |
| ARCH-28이 대학을 분모 누락 | 무주공산 | **소비처 0 → 자인으로 갈음**(§8-⑥) |
| `transfer_example` 0 · 크로스워크 무교차 | 거버넌스 테스트가 동결 | **의도적 미채택**(§8-⑤ ⑥⑦) |
| provenance "전문가 검수 필요" | 게이트 `G-domain-partner` | **게이트 승계** |

→ **신규 태스크 등재 0 · 회수 등재 2(ARCH-28 done · KG-02 blocked) · 승계 부기 3(S4-01·E1-02·CUR-06)
· 스코프 확대 1(KG-02) · 페이퍼 1(저작 우선순위 v2).**

### §8-⑧ 한 줄 결론 — "초에서 대학까지 완비인가"

**뼈대는 완비, 살은 K-12에 편중, 대학은 뼈대만 있고 연결·문항·검수가 전부 0이다.**
초·중·고·대 4개 학교급 모두 노드가 있고 빈 과목이 없다는 점에서 *구조*는 완비에 가깝다.
그러나 ⑴ 문항은 대학 0 · 초1~2 0 · K-12 19과목 중 4과목 0 ⑵ 학생에게 내보낼 수 있는(검수 통과)
이론 서술은 전 학교급 0 ⑶ 고→대 엣지 0으로 학교급을 관통하는 경로가 성립하지 않는다.
"완비"라고 부를 수 있는 축은 **원자 노드와 그 교수학 4요소(진단·오개념·소크라테스·전이)뿐**이다.

---

## 부록(증보) — 대학 축 실측 재현 명령 (HEAD `833f46af` · 2026-08-11 전건 실행 검증)

**㉴ 대학 32과목 6축 전수 분해** (표3 정본):
```bash
python3 - <<'EOF'
import json
from collections import Counter
g = json.load(open('data/corpus/atom_graph_v1/graph.json'))
by = {n['code']: n for n in g['concepts']}
uni = [n for n in g['concepts'] if n['school_level'] == '대학']
cont = json.load(open('data/corpus/concept_content_university_v1/content.json'))['content']
std = json.load(open('data/corpus/standards_university_v1/standards.json'))['standards']
lk = json.load(open('data/corpus/standards_university_v1/concept_standard_links.json'))['links']
lvl = lambda L: Counter(n['subject_area'] for n in uni if n['level'] == L)
unit, sub, atom = lvl('단원'), lvl('소단원'), lvl('세부개념')
ncont, nstd = Counter(i['subject'] for i in cont), Counter(s['subject'] for s in std)
nlink = Counter(by[l['concept_src_id']]['subject_area'] for l in lk)
for s in sorted(sub, key=lambda k: -sub[k]):
    print(f"{s:20}{unit[s]:4}{sub[s]:5}{atom[s]:5} | {ncont[s]:4}{nstd[s]:5}{nlink[s]:5}")
print('합계', sum(unit.values()), sum(sub.values()), sum(atom.values()),
      len(cont), len(std), len(lk), '| 과목수', len(sub))
EOF
```
→ 32과목 · 단원 148 · 소단원 409 · 세부개념 512(합 1,069) · 콘텐츠 409 · 성취기준 409 · 링크 409 ·
전 과목에서 소단원=콘텐츠=성취기준=링크 1:1:1:1. 최대 미적분학 I(7/32/61) ~ 최소 졸업세미나(2/4/4).

**㉵ 대학 이론 신뢰 축 — 코퍼스층 vs 노드층** (표4):
```bash
python3 - <<'EOF'
import json
from collections import Counter
u = json.load(open('data/corpus/concept_content_university_v1/content.json'))['content']
print('키 집합', sorted(u[0]))
print('review_status 키 보유', sum(1 for i in u if 'review_status' in i), '/', len(u))
print('standard_codes 키 보유', sum(1 for i in u if 'standard_codes' in i), '/', len(u))
g = json.load(open('data/corpus/atom_graph_v1/graph.json'))
a = [n for n in g['concepts'] if n['school_level'] == '대학' and n['level'] == '세부개념']
for f in ('core_proposition','misconception','diagnostic_item','socratic','transfer','transfer_example'):
    print(f, sum(1 for n in a if (n.get(f) or '').strip()), '/', len(a))
print('redacted_fields', Counter(tuple(n.get('redacted_fields') or []) for n in a))
EOF
```
→ 키 집합에 `review_status`·`standard_codes` **부재**(0/409) · 세부개념 512:
`core_proposition` 512 · `misconception`/`diagnostic_item`/`socratic`/`transfer` 512 ·
**`transfer_example` 0** · `redacted_fields` 전량 빈 값.
대조(코드): `grep -n "review_status=CONTENT_REVIEW_STATUS_AI_ESTIMATED"
src/backend/whymath_backend/l1/concept_content/projection.py` → `196` (K-12·대학 무구분 상수 각인).

**㉶ 대학 엣지 위상 — 32 고립 사슬** (표5):
```bash
python3 - <<'EOF'
import json
from collections import Counter
g = json.load(open('data/corpus/atom_graph_v1/graph.json'))
by = {n['code']: n for n in g['concepts']}
U = {c for c, n in by.items() if n['school_level'] == '대학'}
same = cross = 0; rel = Counter(); deg = Counter()
for e in g['edges']:
    f, t = e['from_code'], e['to_code']; deg[f] += 1; deg[t] += 1
    if f in U and t in U:
        rel[e['relation']] += 1
        same += by[f]['subject_area'] == by[t]['subject_area']
        cross += by[f]['subject_area'] != by[t]['subject_area']
print('대학내', same + cross, '| 같은과목', same, '| 과목간', cross, '| relation', dict(rel))
print('학교급 경계(고↔대)', sum(1 for e in g['edges'] if (e['from_code'] in U) != (e['to_code'] in U)))
print('차수0', Counter(by[c]['level'] for c in U if deg[c] == 0))
EOF
```
→ 대학내 **481** · 같은과목 **479** · 과목간 **2** · `{'prerequisite': 481}` ·
**고↔대 0** · 차수0 = 소단원 409·단원 148(컨테이너 — `parent_code` 계층이라 정상).

**㉷ 대학 문항·오개념·grade_band 축** (§8-①·⑤):
```bash
python3 - <<'EOF'
import json, glob
from collections import Counter
U = {s['code'] for s in json.load(open('data/corpus/standards_university_v1/standards.json'))['standards']}
hit = tot = 0
for f in glob.glob('data/corpus/problem_bank_*/problems.jsonl'):
    for l in open(f):
        if l.strip():
            tot += 1
            hit += bool(set(json.loads(l).get('achievement_standard_codes') or []) & U)
print('대학 코드 참조 문항', hit, '/', tot)
m = json.load(open('data/corpus/misconceptions_v1/misconceptions.json'))['misconceptions']
print('오개념 카탈로그', len(m), dict(Counter(x['school_level'] for x in m)))
g = json.load(open('data/corpus/atom_graph_v1/graph.json'))
print({L: dict(Counter(n['grade_band'] for n in g['concepts']
       if n['school_level'] == '대학' and n['level'] == L)) for L in ('단원','소단원','세부개념')})
EOF
```
→ **대학 코드 참조 문항 0 / 2,638** · 오개념 843건 전량 초·중·고(**대학 0**) ·
`grade_band`는 세부개념만 1학년 175·2학년 93·3학년 118·4학년 126, 컨테이너 557은 None.

**㉸ Δ1 원인 증적** (§7-Δ1):
```bash
git show --numstat 50b43b6e -- data/corpus/ | grep problems.jsonl
wc -l data/corpus/problem_bank_*/problems.jsonl | tail -1
```
→ `generated_v0` +3/−4(net −1) · `rephrased_v0` 0/−8 → 합 −9 · 현행 총계 **2638**.
