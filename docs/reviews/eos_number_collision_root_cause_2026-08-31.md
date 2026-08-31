# EOS-49/50/51 번호 충돌 — 경위 규명 실측 보고서 (HARN-38)

- **작성**: 2026-08-31 · 세션 `claude/harn-38-tyyh3i`
- **대상 태스크**: `HARN-38-eos-number-collision-renumber`
- **다루는 acceptance**: ②(‘G-eos-g0 clear’ 커밋의 실체 기록) · ③(충돌 경위 실측 규명) · ①의 **선결 준비**(재번호 자체는 사람 게이트 대기 — §6)
- **성격**: 사고 조사. 재번호(①)는 이 문서에서 **실행하지 않는다** — 실행 불가 사유와 해소 경로를 §6에 명시한다.

---

## 1. 결론 요약

| 항목 | 판정 |
|---|---|
| 충돌의 실체 | kiki 머신의 **push되지 않은 로컬 브랜치**에 main과 이종 내용의 동번호 3건이 존재 |
| 번호 충돌 가드(HARN-10+HARN-15)가 못 잡은 이유 | **fail-open(403)이 아니다.** 가드의 관측 표면 3종 중 **어느 것도 미push 브랜치를 원리적으로 볼 수 없다** — 구조적 사각 |
| HARN-07(fail-open 폴백 미착륙)과의 관계 | **이번 건은 재현 사례가 아니다.** 이번 세션 실측에서 원격 claim 조회는 `status=ok`로 정상 작동 |
| 선후 판정 | **경우 A 확정**(2026-08-31 브랜치 회수 후 실측) — kiki 측이 **4일 먼저**였고, 충돌을 만든 것은 main 측 add다 |
| 새로 드러난 부수 결함 | `backlog/events.ndjson`의 `ts`가 **머신 로컬시각·오프셋 무표기** — 교차 머신 사건 순서 재구성이 원리적으로 불가 |
| **조사 중 동종 재발** | 병렬 세션이 같은 원본을 다른 번호로 **이중 등재**(§6-1a) — 원인은 `block`의 claim 반납(§7-A·`HARN-45`). 상대 번호로 통일해 해소 |
| ‘G-eos-g0 clear’ 커밋(3b7bab6f) | **실제 clear가 아니다** — 그 커밋의 diff에 `gates.yaml`이 **아예 없다**(§4). 대장을 실제로 바꾼 것은 `ad7862ab` |

---

## 2. 실측 증거

### 2-1. 문제의 브랜치·커밋은 원격에 존재하지 않는다

```
$ git ls-remote --heads origin | grep -i cur-16
(0건)

$ mcp__github__get_commit(sha=3b7bab6f)
error: No commit found for SHA: 3b7bab6f
```

`backend/cur-16-concept-edge-prerequisite-meta-v2`는 GitHub에 **한 번도 push된 적이 없었다**.
커밋 `3b7bab6f`도 GitHub 객체 그래프에 부재했다. 따라서 사고 발생 시점부터 조사 시점까지
이 브랜치의 내용은 **kiki 머신의 로컬 디스크에만** 존재했다.

> **[2026-08-31 갱신]** Kiki가 게이트 `G-cur16-branch-push`를 실행해 브랜치를 push했다
> (`git ls-remote` 출력 1줄 · head = `3b7bab6f7cf29519feb4aba4c7068bbbe9e1d2f0` — 태스크가
> 지목한 커밋과 일치). 위 측정은 **push 이전 상태의 기록**이며, 그 시점 사고의 원인 판정이다.
> 회수 후 확정된 사실은 §3-2·§4·§6에 반영했다.

### 2-2. 번호 충돌 가드의 관측 표면 3종 — 전수 측정

`backlog.py::_taken_id_numbers`가 보는 출처는 정확히 3개다(코드 실측 —
`scripts/harness/backlog.py:925-944`). 2026-08-31 현행 저장소에서 각각을 직접 호출했다:

| # | 출처 | 측정 결과 | cur-16 브랜치 관측 여부 |
|---|---|---|---|
| ① | 로컬 백로그 (`backlog.tasks`) | main 사본 — EOS-49/50/51은 main 슬러그만 | ❌ (다른 머신) |
| ② | 원격 claim 대장 (`remote_claims.list_claims`) | `status=ok` · 3건 | ❌ (아래 2-3) |
| ③ | 원격 브랜치 `backlog/tasks/` 파일명 스캔 (`scan_remote_task_files`) | `status=ok` · **36 브랜치 · 11,975 파일** | ❌ (미push라 ref 자체가 없음) |

출처 ③의 전수 스캔 결과에서 EOS-49/50/51로 시작하는 파일은 **36개 브랜치 전부에서
main 슬러그 3종뿐**이었다:

```
EOS-49-concept-version-contract      × 8 브랜치 (main 포함)
EOS-50-publish-gate-pipeline         × 8 브랜치 (main 포함)
EOS-51-verification-design-freeze    × 8 브랜치 (main 포함)
cur-16 포함 브랜치: []
```

즉 **가드가 볼 수 있는 우주 전체(11,975 파일)에 충돌 상대가 없었다.**
가드는 실패한 것이 아니라, 관측 대상 밖의 사실을 판정할 수 없었다.

### 2-3. claim 대장에 EOS-49/50/51이 없는 이유 — `add`는 claim하지 않는다

claim 대장(`harness-claims` 브랜치, 722 커밋 전수 grep):

```
$ git log --oneline <harness-claims> | grep -E "EOS-(49|50|51)-"
4b73c709 release EOS-51-verification-design-freeze
49af37e7 claim   EOS-51-verification-design-freeze (claude/mvp-eos-transition-plan-ghcajm)
```

main 슬러그의 EOS-51만 있고, kiki 측 3건은 **한 건도 없다**. `backlog.py add`는
claim을 쓰지 않기 때문이다(claim은 `start`에서만 발생). 이 맹점은 **HARN-15가 이미
식별하고 출처 ③을 신설해 메운 것**인데, 출처 ③ 역시 *push된* 브랜치만 본다.

같은 브랜치가 claim 대장에 남긴 흔적은 CUR-16 두 건뿐이다:

```
fc943cd8 2026-08-25 23:56:12 +0900  claim CUR-16 (backend/cur-16-concept-edge-prerequisite-meta-v2)
33831813 2026-08-25 17:09:44 +0900  claim CUR-16 (backend/cur-16-concept-edge-prerequisite-meta)
```

부수 관측: 이 두 커밋이 만든 파일 경로는 `"claims\r/CUR-16.json\r"` — **CRLF 오염**이다.
HARN-36(2026-08-30 00:50 release)이 고친 바로 그 결함의 실사례가 대장에 화석으로 남아 있다.
다만 이번 충돌과는 **인과가 없다** — EOS-49/50/51 claim은 애초에 존재하지 않으므로
경로가 깨끗했더라도 관측되지 않았다.

---

## 3. 시각선(timeline) — 그리고 그것을 신뢰하면 안 되는 이유

`backlog/events.ndjson` 실측:

| ts (원문) | actor | action | id |
|---|---|---|---|
| 2026-08-25T23:56:15 | `backend/cur-16-...-v2` | start | CUR-16 |
| 2026-08-29T23:55:03 | `claude/uncommitted-changes-qjhp6f` | add | HARN-36 |
| 2026-08-30T00:50:38 | `claude/uncommitted-changes-qjhp6f` | done | HARN-36 |
| **2026-08-30T01:11:47** | `claude/uncommitted-changes-qjhp6f` | **add** | **EOS-49-concept-version-contract** |
| **2026-08-30T01:11:49** | `claude/uncommitted-changes-qjhp6f` | **add** | **EOS-50-publish-gate-pipeline** |
| **2026-08-30T06:37:55** | `claude/mvp-eos-transition-plan-ghcajm` | **add** | **EOS-51-verification-design-freeze** |
| 2026-08-30T12:06:30 | `claude/mvp-eos-transition-plan-ghcajm` | add | EOS-55-generation-run-reproducibility |
| 2026-08-30T15:09:48 | `claude/mvp-eos-transition-plan-ghcajm` | add | HARN-38 (본 태스크) |

**kiki 측 3건의 add 시각은 이 대장에 없다** — 그 이벤트는 미push 브랜치의
`events.ndjson`에 적혔기 때문이다.

### 3-1. 부수 결함 — 이벤트 대장의 시각이 교차 머신에서 비교 불가

`store.append_event`는 `datetime.now().strftime("%Y-%m-%dT%H:%M:%S")`를 쓴다
(`scripts/harness/store.py:300`) — **오프셋 없는 머신 로컬 시각**이다. 교차 검증:

- `done HARN-36 @ 2026-08-30T00:50:38` ↔ claim 대장 `1ca71b02 2026-08-30 00:50:39 +0000` → 이 세션은 **UTC**
- `start CUR-16 @ 2026-08-25T23:56:15` ↔ claim 대장 `fc943cd8 2026-08-25 23:56:12 +0900` → 이 세션은 **KST**

같은 파일의 두 줄이 **9시간 어긋난 척도**로 적혀 있고, 그 사실을 알려주는 필드가 없다.
사고 재구성에서 "어느 쪽 add가 먼저였나"는 책임 소재가 아니라 **어느 가드를 고쳐야 하는지**를
가르는 질문인데, 대장만으로는 그 질문에 답할 수 없다. 후속 태스크로 등재했다(§7).

### 3-2. 선후 판정 — **경우 A 확정** (2026-08-31 브랜치 회수 후)

조사 시점에는 kiki 측 add 시각을 알 수 없어 두 경우를 모두 판정했다. 브랜치가 push된 뒤
그 브랜치의 `events.ndjson`을 직접 읽어 **선후가 결정됐다**:

| 측 | add 시각 (원문) | 척도 | UTC 환산 |
|---|---|---|---|
| **kiki** `EOS-49-problem-quarantine-status` | 2026-08-26T08:39:47 | KST(+0900) | 2026-08-25T23:39:47Z |
| **kiki** `EOS-50-generation-log-prompt-seed` | 2026-08-26T08:39:52 | KST | 2026-08-25T23:39:52Z |
| **kiki** `EOS-51-content-lifecycle-state-wiring` | 2026-08-26T08:39:56 | KST | 2026-08-25T23:39:56Z |
| main `EOS-49-concept-version-contract` | 2026-08-30T01:11:47 | UTC | 2026-08-30T01:11:47Z |
| main `EOS-50-publish-gate-pipeline` | 2026-08-30T01:11:49 | UTC | 2026-08-30T01:11:49Z |
| main `EOS-51-verification-design-freeze` | 2026-08-30T06:37:55 | UTC | 2026-08-30T06:37:55Z |

**kiki 측이 4일 이상 먼저다.** 척도 불명(§3-1)이 판정을 흐릴 여지도 없다 — 9시간 오차를
어느 방향으로 적용해도 4일 간격은 뒤집히지 않는다. kiki 측 브랜치의 척도는 claim 커밋
`fc943cd8(+0900)`와의 3초 차로 KST임이 독립 확인된다.

따라서:

- **확정 = 경우 A(미push 브랜치 사각).** kiki 측 add는 그 시점 번호가 실제로 비어 있었으므로
  **정당했다**. 충돌을 *만든* 것은 4일 뒤의 **main 측 add**이고, 그 가드가 못 본 이유가
  §2-2다 — 미push 브랜치는 세 출처 어디에도 나타나지 않는다.
- **경우 B(`fetch=False` 낡은 캐시)는 이번 사고에서 발생하지 않았다.** kiki 측 add 시점에는
  main에 그 번호가 아예 없었으므로 캐시가 아무리 신선했어도 볼 것이 없었다.
  다만 이 사각 자체는 실재하며 `test_branch_tracking_ref_removed_then_add_passes`가
  계약으로 동결하고 있다 — 이번 사고의 원인은 아니지만 **다음 사고의 후보**다.

> **대책 우선순위에 미치는 영향**: `HARN-43`의 acceptance ①(미push 고지)이 **실증된 원인**에
> 대한 대책이고, ②(ref 신선도 고지)는 **예방적 추가**다. 둘을 같은 무게로 적지 않는다 —
> 실증된 것과 가정된 것을 구분하지 않으면 대책의 조준이 흐려진다.

부수 관측: 그 브랜치의 add 이벤트 앞에는 `policy_warn`(파일 범위 겹침)이 EOS-49에 33건,
EOS-50에 31건, EOS-51에 14건 붙어 있다. 즉 **가드는 그날 정상 작동했고 경고도 냈다** —
번호 충돌만 관측 범위 밖이었다.

## 4. acceptance ② — ‘G-eos-g0 clear’ 커밋의 실체

kiki 머신 브랜치 커밋 `3b7bab6f`의 메시지는 `G-eos-g0 clear`지만,
**그 커밋은 게이트를 clear한 커밋이 아니다.**

| | kiki 머신 `3b7bab6f` | main `ad7862ab` |
|---|---|---|
| GitHub 존재(조사 시점) | ❌ `No commit found for SHA` | ✅ `ad7862ab9f1d8c91b7fe8bf49f89c39253917571` |
| 시각 | 미push(회수 후 확인 가능) | 2026-08-30T15:08:41Z |
| **`gates.yaml` 변경** | **❌ 없음** | ✅ `+2/−2` |
| 그 밖의 변경 | `events.ndjson`(+82) · `CUR-16.yaml` · 신규 태스크 3건 | `events.ndjson`(+21) |
| 대장 반영 | **없음** | 있음 |

**결정적 증거(2026-08-31 회수 후 실측)**: `git show --stat 3b7bab6f`의 변경 파일 5건에
**`backlog/gates.yaml`이 없다.** 게이트를 clear했다면 반드시 그 파일이 바뀐다. 즉 이 커밋은
자기 메시지를 자기 diff로 반증한다 — clear가 "게이트 없음"으로 거부됐으니 기록될 변경이
애초에 없었던 것이다.

**clear의 실체는 `ad7862ab`다.** MEMORY 2026-08-30 기록대로, kiki 머신에서의 clear 실행은
구버전 대장 때문에 "게이트 없음"으로 **거부**됐고, 세션이 선례(G-crosswalk-approval)에 따라
Kiki 본인의 서명 의사를 완료분으로 반영한 것이 `ad7862ab`다. 이후 PR #910에서 Kiki 본인
서명분이 착지하며 그것이 정본으로 상위 대체됐다(MEMORY 2026-08-30 "G0 서명은 #910의
Kiki 본인 서명이 정본").

현행 main의 게이트 상태 실측 — `G-eos-g0-verification-design-freeze: status=cleared`,
evidence에 서명 주체·차단 3조건·§5 정규화 sha256(`a9ad9f6a…`)이 전문 기록돼 있다.

> **기록 의의**: 미push 브랜치에 "clear"라는 단어를 담은 커밋이 남아 있으면, 훗날 그 브랜치를
> 회수하는 세션이 **그것을 clear의 근거로 오독**할 수 있다. 이 절이 그 오독을 차단한다.
> 커밋 메시지는 의사 표시일 뿐 대장 변경이 아니며, **게이트의 진실 원천은 `backlog/gates.yaml`**이다.

---

## 5. HARN-07(fail-open 폴백 미착륙)과의 교차 판정

HARN-38 acceptance ③은 "fail-open(403)이면 HARN-07 재현 사례로 교차 기록"을 조건부로 요구한다.
**조건이 성립하지 않으므로 교차 기록하지 않는다.** 근거:

- 이번 세션의 `list_claims` → `status=ok`(3건 반환)
- 이번 세션의 `scan_remote_task_files` → `status=ok`(36 브랜치·11,975 파일)
- `backlog.py start HARN-38` 실행 로그 → `원격 claim: ok`
- HARN-09가 claim을 `harness-claims` **브랜치**로 옮긴 뒤 `refs/claims/*` push 403 경로 자체가 소멸

허위 교차 기록은 대책의 조준을 흐린다 — HARN-07이 고치려는 것(fail-open 폴백)은 이 사고를
막지 못했을 것이고, 이 사고의 대책(§7)도 HARN-07이 아니다.

---

## 6. acceptance ① — 재번호 실행 결과 (2026-08-31 완료)

조사 시점에는 입력(3건의 YAML 본문)에 도달할 수 없어 실행하지 않았다 — 내용을 모른 채
`add`를 돌리면 태스크를 날조하게 되기 때문이다(CLAUDE.md "환경 사실의 추론 등재 금지").
게이트 `G-cur16-branch-push`가 해소되어 본문을 확보한 뒤 실행했다.

### 6-1. 재번호 결과

| 원 ID (kiki 브랜치) | 처분 | 새 ID |
|---|---|---|
| `EOS-49-problem-quarantine-status` | 재등재(본문 무변경) | **`EOS-71-problem-quarantine-status`** |
| `EOS-50-generation-log-prompt-seed` | **중복 — 재등재 안 함**(§6-2) · 잔여만 승계 | **`EOS-73-generation-seed-threading`** |
| `EOS-51-content-lifecycle-state-wiring` | 재등재(본문 무변경) | **`EOS-72-content-lifecycle-state-wiring`** |

번호는 전부 `backlog.py add`가 배정했다(HARN-10 준수). 최종 번호에 이르기까지 CLI가
**연속 4회 실거부**했다 — `EOS-67`(`…core-adapter-import-contract` 선점) ·
`EOS-71`·`EOS-72`(아래 §6-1a의 병렬 세션 선점) — 매번 제안 번호를 채택했다.

재등재는 제목·acceptance 전항·paths·원 notes를 **바이트 수준에서 그대로 옮겼고**, 각 태스크
notes에 원 ID·원 등재 시각·충돌 경위를 병기했다. 번호만 바뀌고 내용은 바뀌지 않았음을
추적할 수 있게 하기 위함이다.

### 6-1a. 같은 사고가 이 조사 중에 **재발했다** — 병렬 이중 등재

재번호를 실행하는 동안 다른 세션(`claude/failure-definition-signature-scmzdu`)이 **같은
HARN-38을 병렬 수행**해, 같은 원본 3건을 **다른 번호로 이중 등재**했다:

| 원 ID | 본 세션 최초 배정 | 병렬 세션 배정 | 최종 |
|---|---|---|---|
| `EOS-49-problem-quarantine-status` | `EOS-69` | **`EOS-71`**(05:11:47Z claim) | **`EOS-71`** |
| `EOS-51-content-lifecycle-state-wiring` | `EOS-70` | **`EOS-72`** | **`EOS-72`** |
| (EOS-50 잔여) | `EOS-71` | *(미등재 — 본 세션 고유분)* | **`EOS-73`** |

즉 **"같은 일을 두 번호로 등재"** — HARN-38이 고치려던 바로 그 질병이 그 조사 도중에
한 번 더 발생했다. 원인은 §7-A(`HARN-45`)의 claim 반납 사각이다.

**해소 방식 — 본 세션이 양보하고 상대 번호로 통일**했다(`EOS-69`·`EOS-70` 철회):

- 상대가 **원격 claim 대장에 먼저 등재**했다(`EOS-71` 05:11:47Z). 대장은 교차 세션의 유일한
  공유 신호이므로, 거기에 먼저 오른 쪽이 기준이 되는 것이 일관된 규칙이다.
- 결정적으로 — **같은 full ID면 두 브랜치가 다 머지돼도 번호 충돌이 아니다.**
  `cmd_add`의 "같은 full ID 재등재는 충돌이 아니다" 규칙(`backlog.py:1001-1003`)이 그 상태를
  정상으로 정의한다. 반대로 `EOS-69`/`EOS-71`을 각자 유지하면 **양쪽이 머지되는 순간
  내용이 같은 태스크가 4개**가 되고, 슬러그가 달라 `validate`는 통과한다 — **이 사고의 원형
  그대로**다. 즉 양보는 예의가 아니라 **재발 차단 조치**다.
- 두 세션의 이관본은 title·acceptance 전항·paths가 **동일**했다(둘 다 같은 원본을 충실히
  옮겼다) — 양보로 잃는 내용이 없음을 대조로 확인했다.

**본 세션 고유분**(상대 브랜치에 없음): `EOS-73`(EOS-50 잔여) · `HARN-43`·`HARN-44`·`HARN-45` ·
이 보고서 · 게이트 2건 · CLAUDE.md 규칙 개정.

### 6-2. EOS-50 중복 판정 — acceptance 3항 전수 대조

원 `EOS-50-generation-log-prompt-seed`의 acceptance 3항을 main `EOS-55`(done · PR #912) 착지분과
**항목별로** 대조했다. "중복 같다"는 인상이 아니라 항목 단위 판정이어야 실제 잔여를 놓치지 않는다.

| 원 EOS-50 acceptance | 판정 | 실측 근거 |
|---|---|---|
| ① GenerationLog에 **prompt 본문**(또는 해시+저장소 참조)·**seed 컬럼** 추가(alembic) | ✅ **흡수 — 오히려 더 강하게** | `input_snapshot_for_prewarm`이 `prompt`·`system` **전문(verbatim)** + 각 sha256을 담는다(`provenance_bridge.py:90-119`). EOS-50이 허용한 "해시+참조"보다 강한 전문 저장. `seed` 컬럼도 착지(`provenance.py:174` BigInteger · alembic `f4b2d8c1a3e5`) |
| ①의 목적절 — 모델·`generator_version` 단위 **영향 생성분 전수 조회** 성립 | ✅ **실질 성립** | `model_name` 실적재 · **`prompt_version` 실값 적재**(`llm_generator.py:585` → `_prompt_version()` = 정본 프롬프트 자산 내용 해시). `generator_version`이라는 *이름*의 컬럼은 저장소 전체 grep 0건이나, 그 축의 역할을 `prompt_version`이 수행한다 |
| ② pregenerate·**DSL 생성 경로**가 실제 prompt·seed를 적재 | ⚠️ **부분 미이행** | **prompt 축 = 이행**(pregenerate·accumulate 두 경로 실적재 — #912 집행 별항). **seed 축 = 미이행**(두 경로 전부 `seed=None` — `provenance_bridge.py:151-152`·`prewarmer.py:117`·`provenance.py:173` 자인 3중). **DSL 경로 = 전제 무효**(아래) |
| ③ 기존 행 백필 정책 명시 — 복원 불가분은 null 자인, 침묵 미기입 금지 | ✅ **흡수** | 재현 좌석 5컬럼 전부 nullable·`server_default` 없음 = "구 행 NULL=미기록"(`provenance.py:170` 주석). `seed=NULL 정직`도 MEMORY 2026-08-30에 명문 |

**"DSL 생성 경로" 전제 무효 판정**: `l3/dsl/`에는 라우터·프로바이더 import가 **0건**이다
(`compiler.py`·`variable_engine.py`·`validators.py`·`math_verifier.py`·`quality_gate.py`·`repair.py`).
이 계층은 **결정론 컴파일러**이고 LLM 호출 자체가 없으므로 `GenerationLog` 적재 대상이 아니다.
`variable_engine.generate(seed=…)`의 `seed`는 **변수 바인딩 난수 시드**로 LLM 시드와 다른 축이다
(`compiler.py:28`이 `seed=0` 하드코딩) — 이름이 같아서 같은 것으로 읽히기 쉬운 지점이라 명시한다.

**결론**: `EOS-50`은 **중복이므로 재등재하지 않는다.** 미이행 잔여는 **seed 축 하나**이며
`EOS-71-generation-seed-threading`으로 승계 등재했다(백로그 전수 검색 결과 이 잔여를 소유한
태스크가 없었음 — MEMORY 2026-08-30의 "결정론 재생성은 별도 태스크" 이월이 좌석 없이 떠 있던 상태).

### 6-3. 구 YAML 처분 — **완료** (2026-08-31 Kiki 실행)

원 YAML 3건은 여전히 `backend/cur-16-...-v2` 브랜치에 있다. 이 세션은 **자신의 지정 브랜치
외에는 push할 수 없어** 그 브랜치에서 삭제 커밋을 올리지 못했다.

처분 판단의 재료(실측):

- 그 브랜치의 **코드 내용은 이미 main에 전부 있다** — `required_strength` 등 CUR-16 기능이
  main `schema/concept.py:275,320`에 실재하고, `CUR-16`은 `status: done`·PR #892(`a92a887f`) 머지.
- 브랜치 고유분은 **태스크 YAML 3건 + 위 false-clear 커밋**뿐이었고, 3건은 §6-1에서 회수 완료.
- 즉 이 브랜치는 **머지 가치가 0**이며, 남겨 두면 "언젠가 머지되어 동번호 YAML이 main에 재진입"
  하는 경로만 남는다(그때도 슬러그가 달라 `validate`는 통과한다 — 이 사고의 원형 그대로).

**권고 = 브랜치 삭제**(YAML 삭제를 포함하는 상위 처분). 되돌리려면 SHA
`3b7bab6f7cf29519feb4aba4c7068bbbe9e1d2f0`로 재생성하면 되므로 **가역**이다.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 · 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath

# ① 원격 브랜치 삭제 (복구 SHA = 3b7bab6f7cf29519feb4aba4c7068bbbe9e1d2f0)
git push origin --delete backend/cur-16-concept-edge-prerequisite-meta-v2

# ② 로컬 브랜치 삭제 — 현재 이 브랜치에 있으면 먼저 다른 브랜치로 이동해야 한다
git branch -D backend/cur-16-concept-edge-prerequisite-meta-v2

# ③ 자가검증 — 이 출력이 판정이다. **무출력이면 성공**, 1줄 보이면 삭제 실패
git ls-remote --heads origin backend/cur-16-concept-edge-prerequisite-meta-v2
```

> ③의 성공/실패 방향이 §8의 push 검증과 **반대**임에 주의한다(그때는 1줄=성공, 여기서는
> 무출력=성공). 같은 명령이라도 무엇을 확인하는지에 따라 판정이 뒤집히므로 명시한다.

**[실행 결과 — 게이트 `G-cur16-branch-disposal` cleared]** Kiki가 2026-08-31 실행:
`git push origin --delete` → `[deleted] backend/cur-16-concept-edge-prerequisite-meta-v2` ·
`git branch -D` → `Deleted branch … (was 3b7bab6f)` · **③ 자가검증 `git ls-remote` 무출력**(=성공 방향).
구 YAML 3건이 원격·로컬 양쪽에서 소멸해 **동번호 재진입 경로가 차단**됐다. 복구 SHA는
`3b7bab6f7cf29519feb4aba4c7068bbbe9e1d2f0`으로 이 문서·MEMORY·게이트 evidence 3곳에 보존된다.

⇒ **acceptance ① 전항 완료** (재등재 + 구 YAML 삭제).

## 7. 재발방지대책 (CLAUDE.md 실수 관리 — 3회차 반복이라 등재 의무)

이 유형(동번호 이종 태스크)은 ARCH-13(2026-07-18/25)·OPS-15(2026-07-29)에 이어 **3회차**다.
앞 두 번의 대책(HARN-10 번호 가드 → HARN-15 원격 파일명 스캔)은 모두 **push된** 관측 표면을
넓히는 방향이었고, 이번 사고는 그 방향으로는 도달할 수 없는 지점에서 났다.

등재한 후속 2건(번호는 `backlog.py add`가 배정 — HARN-10 준수):

1. **`HARN-43-add-unpushed-branch-visibility-warning`** — `backlog.py add` 성공 직후,
   그 번호가 **아직 다른 세션에 보이지 않는다**는 사실을 경고로 알린다. 판정 축 2개이나
   **무게가 다르다**(§3-2 확정 반영):
   - acceptance ① 현재 브랜치의 원격 ref 부재(**경우 A** 사각) — **이번 사고의 실증된 원인**
   - acceptance ② remote-tracking ref 신선도(**경우 B** 사각) — 이번엔 발생하지 않은 **예방적 추가**

   실증된 것과 가정된 것을 같은 무게로 적으면 대책의 조준이 흐려지므로 구분해 둔다.
   "측정 실패와 통과가 같은 색이면 안 된다"의 등재 경로 적용 — 지금은 **둘 다 조용히 통과**한다.
2. **`HARN-44-event-ledger-timezone-offset`** — `store.append_event`의 `ts`에 오프셋을 넣어
   교차 머신 순서 재구성을 가능하게 한다(§3-1). 기존 행은 소급 정정 불가이므로
   **표기 전환 시점만 명시**하고 과거 구간은 "머신 로컬·척도 불명"으로 남긴다(날조 금지).

**등재 중 얻은 부수 실측 — 가드는 *보이는* 표면에서는 확실히 작동한다.**
위 ①을 `HARN-42`로 등재하려 하자 CLI가 실거부했다:

```
❌ 태스크 ID 번호 충돌: 'HARN-42' 는 이미 HARN-42-open-pr-eos-reclassification
   (원격 브랜치 backlog/tasks/(claude/review-status-differences-jw5m4a)) 가 쓰고 있다.
   다음 빈 번호 제안: HARN-43.
EXIT=1
```

상대는 **push된 미머지 브랜치**였고 출처 ③이 정확히 잡았다. §6-1의 재번호에서도
`EOS-67` 요청이 같은 방식으로 실거부됐다(`EOS-67-core-adapter-import-contract` 선점).
HARN-38 등재 당시 HARN-37 충돌 거부까지 합치면 **변별력 실증 3회차**다.
이 대비가 §2-2의 결론을 강화한다 — 문제는 가드의 판정력이 아니라 **관측 범위**다.
그리고 §3-2 부수 관측대로, kiki 측 add 그날에도 가드는 `policy_warn`을 78건 냈다 —
**작동은 했고, 번호 충돌만 관측 범위 밖이었다.**

**대책의 성격 구분(정직한 한계)**: ①은 *탐지*가 아니라 *고지*다. 미push 브랜치를 실제로
관측하는 방법은 없으므로, 가드가 할 수 있는 최선은 **자기 관측 범위의 구멍을 사람에게
말하는 것**이다. "가드가 통과했다 ≠ 충돌이 없다"를 화면에 띄우는 것이 이 대책의 전부이며,
그 이상을 주장하지 않는다.

---

## 7-A. 조사 중 발생한 사고 — 게이트 대기가 claim을 반납한다 (`HARN-45`)

이 조사 자체가 네 번째 사각을 노출했다. 기록해 둔다 — 조사가 만든 사고를 조사 보고서가
빠뜨리면 그 사고는 다음 세션에 다시 난다.

**경위**: acceptance ①이 입력 부재로 막혀 게이트 `G-cur16-branch-push`를 신설하고 HARN-38을
`block`으로 전이했다. `cmd_block`은 `_release_remote_claim`으로 **원격 claim을 반납**한다
(`backlog.py:711`). 그 창에 다른 세션이 태스크를 집어갔다:

```
2026-08-31T05:00:05Z  claim HARN-38-eos-number-collision-renumber
                      (claude/failure-definition-signature-scmzdu)
```

게이트 해소 후 원 세션이 재claim을 시도하자 CAS 충돌로 거부됐다. **`--force`로 우회하지
않았다** — CAS claim conflict는 확정 신호이지 장애물이 아니다(CLAUDE.md "거부의 우회 금지").
크로스세션 메시지도 도달하지 않아(`ListAgents` 0건) 사람 보고로 에스컬레이션했다.

**구조적 원인**: **‘게이트 대기’와 ‘차단’은 의미가 다른데 같은 전이를 쓴다.**
게이트 대기는 *자리를 지켜야* 하고(같은 세션이 해소 후 이어받는다), 차단은 *인계 가능해야*
한다(다른 세션이 맡을 수 있다). 게다가 `requires_gates`가 걸린 태스크는 `start`가 거부되므로
`todo`로 남겨도 재claim이 안 된다 — 즉 **현행 설계에 "게이트 대기 중 자리 보전"을 표현할
수단 자체가 없다.**

`HARN-45-gate-wait-vs-blocked-state-split`로 등재했다. 이 사고는 §7의 세 사각과 성격이
다르다 — 앞의 것들은 *관측*의 사각이고, 이것은 *상태 표현*의 사각이다.

**그리고 이 사각은 곧바로 실해를 냈다** — 그 세션이 같은 재번호를 병렬로 수행해 §6-1a의
**이중 등재**가 발생했다. 즉 `HARN-45`는 가설적 위험이 아니라 **같은 세션 안에서 원인→결과가
모두 관측된** 결함이다. 우선순위 1로 등재한 근거다.

## 8. Kiki 실행 과제 브리핑 — CUR-16 브랜치 push (게이트 `G-cur16-branch-push` · **2026-08-31 해소 완료**)

> CLAUDE.md "Kiki 직접 수행 과제의 사전 브리핑 템플릿 의무" 6항목.
> **[해소 기록]** Kiki가 2026-08-31 실행 완료 — ④ 자가검증에서 `refs/heads/backend/cur-16-…-v2`
> 1줄·head `3b7bab6f7cf29519feb4aba4c7068bbbe9e1d2f0` 확인. 아래 브리핑은 **집행 기록**으로
> 보존한다(다음 유사 과제의 서식 선례). 남은 사람 행동은 §6-3의 브랜치 처분이다.

1. **과제 명칭** — kiki 머신 로컬 브랜치 `backend/cur-16-concept-edge-prerequisite-meta-v2`를
   GitHub에 push (내용 변경 없음 · 순수 업로드)
2. **목적** — 그 브랜치에만 존재하는 태스크 YAML 3건(EOS-49/50/51 동번호 이종)의 **본문을
   확보**하기 위함. 확보되면 세션이 즉시 새 번호로 재등재하고 구 YAML을 삭제해
   HARN-38 ①을 완결한다. push하지 않으면 그 3건은 kiki 머신이 초기화되는 순간 영구 소실된다.
   (부수: main으로 머지하지 않는다 — 업로드만 한다.)
3. **구체적 절차** — 4단계. 예상 소요 1분 이내.
   - ① 작업 디렉터리 이동 → ② 브랜치 존재 확인(있어야 정상) → ③ push →
     ④ 자가검증(GitHub에 브랜치가 실제로 생겼는지 `git ls-remote`로 직접 확인)
   - ②에서 브랜치가 **없다고 나오면 그 자체가 결론**이다(이미 소실) — 그 출력을 그대로 전달.
4. **성공 기준** —
   - 성공: ④의 출력에 `refs/heads/backend/cur-16-concept-edge-prerequisite-meta-v2` 줄이
     **1줄 보인다**.
   - 실패: ④가 **아무것도 출력하지 않는다**(push가 조용히 실패한 것 — ③의 출력 전문을 전달).
   - ※ ③의 화면 메시지만 보고 성공으로 판정하지 않는다 — ④가 판정이다.
     (CLAUDE.md "간접 신호를 성공 판정으로 쓰는 안내 금지")
   - 실패 시 대처: ③을 `git push -u origin HEAD:backend/cur-16-concept-edge-prerequisite-meta-v2`
     형태로 바꿔 재시도하고, 그래도 실패하면 출력 전문을 전달.
5. **실행 환경** — Phaiakes9 = 평소 쓰는 **Windows PowerShell**(별도 접속·WSL 진입 불요).
   작업 디렉터리 `C:\Users\kiki\Desktop\__AI\WhyMath`.
   선행 조건 없음(Docker·서버·DB 전부 불요 · 네트워크만 필요).
   ⚠ **머신 주의**: 이 브랜치는 `C:\Users\kiki\...` 머신에 있다. MEMORY 2026-08-30이 기록한
   또 다른 머신(`C:\Users\rollrock\...`)에서 실행하면 브랜치가 없다고 나온다.
6. **창 구분** — **새 PowerShell 창** 1개. 장기 점유 프로세스가 없으므로 이 창은
   끝난 뒤 자유롭게 계속 써도 된다.

```powershell
# [실행 시스템] Windows PowerShell (= Phaiakes9 · 진입 명령 불요)
cd C:\Users\kiki\Desktop\__AI\WhyMath

# ② 브랜치 존재 확인 — 1줄 나오면 정상, 아무것도 안 나오면 이미 소실(그 사실을 전달)
git branch --list backend/cur-16-concept-edge-prerequisite-meta-v2

# ③ push (main 머지 아님 — 업로드만)
git push -u origin backend/cur-16-concept-edge-prerequisite-meta-v2

# ④ 자가검증 — 이 출력이 판정이다. 1줄 보이면 성공, 무출력이면 실패
git ls-remote --heads origin backend/cur-16-concept-edge-prerequisite-meta-v2
```

**게이트 clear는 Kiki가 하지 않는다 — ④의 출력만 전달하면 세션이 처리한다.**

> ### ⚠️ 초안의 결함과 정정 (Codex P2 · 2026-08-31 · PR #930 리뷰 수용)
>
> 이 블록의 **초안에는 `backlog.py gates clear G-cur16-branch-push` 명령이 들어 있었다.**
> 그 명령은 **반드시 실패한다** — 실측:
>
> ```
> $ git show origin/main:backlog/gates.yaml | grep -c "G-cur16-branch-push"                 → 0
> $ git show origin/backend/cur-16-…-v2:backlog/gates.yaml | grep -c "G-cur16-branch-push"  → 0
> ```
>
> 이 게이트는 **미머지 브랜치 `claude/harn-38-tyyh3i`에만** 있다. CLI는 *현재 체크아웃의*
> `backlog/gates.yaml`을 읽으므로 kiki 머신 어느 브랜치에서 실행해도 `게이트 없음`으로 거부된다
> — **이 사고를 촉발한 2026-08-30 실패(구버전 대장에서 G0 clear 시도 → "게이트 없음" 거부)와
> 글자 그대로 같은 실패**를, 그 사고를 조사하는 문서가 재생산할 뻔했다.
>
> **어긴 규칙**: CLAUDE.md "Kiki 머신 행동 요청 시 실행 명령 동봉 필수" —
> *"미머지 브랜치의 신규 파일을 쓰는 명령이면 해당 브랜치 fetch/checkout을 반드시 선행 포함"*.
> 규칙은 이미 있었고 지키지 않았다. 원인 추정: "신규 **파일**"이라는 문언을 읽고
> **대장의 신규 *항목*(gates.yaml의 게이트 1줄)** 을 그 범주로 매핑하지 못했다 —
> 파일은 이미 존재하고 그 안의 항목만 새것이라 "신규 파일 없음"으로 통과시킨 것이다.
> 상환 = CLAUDE.md 규칙 문언에 **대장 항목**을 명시적으로 편입(2026-08-31 개정).
>
> **실제 피해 0** — Kiki는 ②③④만 실행했고 clear는 세션이 자기 체크아웃에서 수행했다.
> 다만 이는 **설계가 아니라 운이었다**. 정정된 형태가 위 문장이다: 게이트가 미머지 상태인
> 동안 clear는 **그 브랜치를 가진 쪽**(= 세션)이 한다.
>
> **일반화한 판정 규칙**: Kiki에게 `backlog.py`(또는 임의의 대장 조작 CLI) 명령을 안내하기
> 전에, **그 명령이 읽을 대장 항목이 kiki 머신의 체크아웃에 실재하는지** 확인한다.
> 없으면 ①브랜치 fetch/checkout을 선행 포함하거나 ②그 단계를 세션이 가져간다.
> 셋 중 어느 것도 하지 않은 안내는 "가정 기반 런북"이다.

---

## 9. cross-ref

- `backlog/tasks/HARN-38-eos-number-collision-renumber.yaml` (본 태스크)
- `MEMORY.md` 2026-08-30 "EOS-54 HIT 검수 타이머 착지 + G0 조기 서명 + 사고 2건 기록" §사고 ①
- `scripts/harness/backlog.py:898-1022` (`_taken_id_numbers`·`cmd_add` 번호 가드)
- `scripts/harness/remote_claims.py:1179-1245` (`scan_remote_task_files` — fetch=False 명문)
- `scripts/harness/store.py:295-307` (`append_event` — 오프셋 없는 로컬 시각)
- `tests/harness/test_backlog_add_id_collision.py` (경우 B 사각의 기계 동결)
- `HARN-45`(조사 중 발생한 사고 — §7-A) · 병렬 claim 충돌 상대 세션 `claude/failure-definition-signature-scmzdu`
- 선례: ARCH-13(2026-07-18/25) · OPS-15(2026-07-29) · HARN-10 · HARN-15 · HARN-36 · HARN-07
- PR #902(main EOS-49/50 등재) · #908/#910(G0 서명) · #912(EOS-55) · 커밋 `ad7862ab`
