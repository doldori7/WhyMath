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
| 새로 드러난 부수 결함 | `backlog/events.ndjson`의 `ts`가 **머신 로컬시각·오프셋 무표기** — 교차 머신 사건 순서 재구성이 원리적으로 불가 |
| ‘G-eos-g0 clear’ 커밋(3b7bab6f) | **실제 clear가 아니다** — GitHub에 존재하지 않는 커밋. 대장을 실제로 바꾼 것은 `ad7862ab`(§4) |

---

## 2. 실측 증거

### 2-1. 문제의 브랜치·커밋은 원격에 존재하지 않는다

```
$ git ls-remote --heads origin | grep -i cur-16
(0건)

$ mcp__github__get_commit(sha=3b7bab6f)
error: No commit found for SHA: 3b7bab6f
```

`backend/cur-16-concept-edge-prerequisite-meta-v2`는 GitHub에 **한 번도 push된 적이 없다**.
커밋 `3b7bab6f`도 GitHub 객체 그래프에 부재한다. 따라서 이 브랜치의 내용은
**kiki 머신의 로컬 디스크에만** 존재한다.

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

### 3-2. 두 가지 가능한 순서 — 어느 쪽이든 사각은 실재한다

kiki 측 add 시각을 모르므로 두 경우를 모두 판정한다.

**경우 A — kiki 측 add가 main보다 먼저 (2026-08-30T01:11 UTC 이전).**
그 시점 EOS-49/50/51 번호는 main 어디에도 없었으므로 kiki 측 add는 정당했다.
충돌을 *만든* 것은 main 측 add이고, 그 가드가 못 본 이유가 §2-2다 — **미push 브랜치 사각**.
CUR-16 브랜치가 08-25부터 in-flight였던 점(claim 대장)으로 보아 이쪽이 유력하다.

**경우 B — kiki 측 add가 main보다 나중.**
그러면 kiki 측 가드의 출처 ③이 main의 새 번호를 봤어야 한다. 못 본 이유는 별개의 사각인
**`fetch=False` 기본값**이다 — `scan_remote_task_files`는 이미 캐시된 remote-tracking ref만
읽고 네트워크를 타지 않는다(`remote_claims.py:1193` 명문). MEMORY 2026-08-30 기록의
"구버전 트리·pull 중단"이 사실이면 그 머신의 `origin/main` 캐시는 08-25 언저리에 멈춰 있어
08-30 01:11의 add를 원리적으로 볼 수 없다.

이 두 번째 사각은 **이미 기계로 동결된 계약**이다 —
`tests/harness/test_backlog_add_id_collision.py::test_branch_tracking_ref_removed_then_add_passes`
("remote-tracking ref가 없으면 add가 통과한다")와
`::test_default_call_never_invokes_git_fetch`가 그 동작을 의도로 못 박고 있다.
즉 경우 B는 버그가 아니라 **의도된 네트워크 비용 트레이드오프의 대가**이며, 대가를
치를 때 사람에게 알리지 않는 것(경고 부재)이 결함이다.

**어느 경우든 "가드가 fail-open으로 무력화됐다"는 가설은 기각된다** — 이번 세션 실측에서
출처 ②·③ 모두 `status=ok`였고, 403·예외·축소 경고는 한 건도 관측되지 않았다.

---

## 4. acceptance ② — ‘G-eos-g0 clear’ 커밋의 실체

kiki 머신 브랜치 커밋 `3b7bab6f`의 메시지는 `G-eos-g0 clear`지만,
**그 커밋은 게이트를 clear한 커밋이 아니다.**

| | kiki 머신 `3b7bab6f` | main `ad7862ab` |
|---|---|---|
| GitHub 존재 | ❌ `No commit found for SHA` | ✅ `ad7862ab9f1d8c91b7fe8bf49f89c39253917571` |
| 시각 | 불명(미push) | 2026-08-30T15:08:41Z |
| 변경 파일 | 불명 | `backlog/gates.yaml`(+2/−2) · `backlog/events.ndjson`(+21) — 대장 2건뿐 |
| 대장 반영 | 없음 | 있음 |

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

## 6. acceptance ① — 재번호는 왜 이 세션에서 실행할 수 없는가

재번호의 입력은 kiki 측 3건의 **YAML 본문**(title·acceptance·paths·notes)이다.
§2-1 실측대로 그 파일들은 GitHub에 없고 이 샌드박스에서 도달 경로가 **0**이다.
내용을 모른 채 `backlog.py add`를 돌리면 **태스크를 날조**하게 되므로 실행하지 않는다
(CLAUDE.md "환경 사실의 추론 등재 금지").

해소 경로 = 사람 게이트 `G-cur16-branch-push`(§8 브리핑) — Kiki가 그 브랜치를 push하면
이 세션(또는 후속)이 즉시 ①을 완결한다.

### 6-1. 미리 확정해 둔 판정 — EOS-50 중복 의심 대조

acceptance ①은 `EOS-50-generation-log-prompt-seed`가 main의
`EOS-55-generation-run-reproducibility`와 중복인지 판정하라고 요구한다. 본문 없이 확정할 수
없지만, **대조 기준선은 지금 전부 확정해 둔다** — 브랜치가 도착하면 판정이 기계적이 되도록.

EOS-55(**status: done** · PR #912 · 2026-08-30 착지)의 실측 착지 범위:

| EOS-55가 실제로 착지시킨 것 | 실측 근거 |
|---|---|
| `generation_log` 재현 좌석 5컬럼: `prompt_version`·`seed`·`input_sha256`·`input_snapshot`·`cu_slug` | `db/models/provenance.py:141,173-174` · alembic `f4b2d8c1a3e5` |
| 두 생성 경로(pregenerate·accumulate) 실적재 배선 | `l3/pregenerate/provenance_bridge.py` |
| 재현 계약 테스트(전문 복원 단언) | `tests/backend/schema/test_generation_reproducibility.py` |

**판정 규칙(브랜치 도착 시 그대로 적용)**:

- kiki 측 EOS-50의 acceptance가 **좌석·적재·재현 계약 범위 안**이면 → **중복**. 재등재하지 않고
  `EOS-55`에 흡수됐음을 notes에 기록한 뒤 구 YAML 삭제.
- **좌석 밖의 잔여**를 요구하면 → 그 잔여만 새 번호로 재등재. 현재 확인된 잔여 후보는 하나다:

  > **seed 값의 실제 스레딩.** 컬럼은 있으나 두 경로 모두 `seed=None`을 쓴다 —
  > `provenance_bridge.py:151-152` 주석 자인: *"사전적재 경로는 템플릿 체계·seed 스레딩이 없어
  > 기본 None=미기록(날조 금지)"*. MEMORY 2026-08-30도 *"seed=NULL 정직(라우터 스레딩 전무 실측
  > — 결정론 재생성은 별도 태스크)"*로 명시적 후속 이월을 기록했다.
  > 백로그 전수 검색 결과 **이 잔여를 소유한 태스크는 현재 없다.**

  즉 kiki 측 EOS-50이 "seed를 실제로 넣어 결정론 재생성을 가능하게 하라"는 요구를 담고 있다면
  그것은 **살아 있는 갭**이며 재등재 대상이다.
- `EOS-49-problem-quarantine-status`·`EOS-51-content-lifecycle-state-wiring`은 main 동번호와
  주제가 무관하므로(버전 계약·발행 게이트·검증설계 동결) 중복 판정 대상이 아니다 —
  **본문 확인 후 그대로 새 번호로 재등재**한다.

---

## 7. 재발방지대책 (CLAUDE.md 실수 관리 — 3회차 반복이라 등재 의무)

이 유형(동번호 이종 태스크)은 ARCH-13(2026-07-18/25)·OPS-15(2026-07-29)에 이어 **3회차**다.
앞 두 번의 대책(HARN-10 번호 가드 → HARN-15 원격 파일명 스캔)은 모두 **push된** 관측 표면을
넓히는 방향이었고, 이번 사고는 그 방향으로는 도달할 수 없는 지점에서 났다.

등재한 후속 2건(번호는 `backlog.py add`가 배정 — HARN-10 준수):

1. **`HARN-43-add-unpushed-branch-visibility-warning`** — `backlog.py add` 성공 직후,
   그 번호가 **아직 다른 세션에 보이지 않는다**는 사실을 경고로 알린다. 판정 축 2개:
   현재 브랜치의 원격 ref 부재(경우 A 사각) · remote-tracking ref의 신선도(경우 B 사각).
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

상대는 **push된 미머지 브랜치**였고 출처 ③이 정확히 잡았다. HARN-38 등재 당시
HARN-37 충돌을 거부했던 것(태스크 notes 기록)에 이은 두 번째 변별력 실증이다.
이 대비가 §2-2의 결론을 강화한다 — 문제는 가드의 판정력이 아니라 **관측 범위**다.

**대책의 성격 구분(정직한 한계)**: ①은 *탐지*가 아니라 *고지*다. 미push 브랜치를 실제로
관측하는 방법은 없으므로, 가드가 할 수 있는 최선은 **자기 관측 범위의 구멍을 사람에게
말하는 것**이다. "가드가 통과했다 ≠ 충돌이 없다"를 화면에 띄우는 것이 이 대책의 전부이며,
그 이상을 주장하지 않는다.

---

## 8. Kiki 실행 과제 브리핑 — CUR-16 브랜치 push (게이트 `G-cur16-branch-push`)

> CLAUDE.md "Kiki 직접 수행 과제의 사전 브리핑 템플릿 의무" 6항목.

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

push가 확인되면 게이트를 clear한다:

```powershell
# [실행 시스템] Windows PowerShell — 같은 창에서 이어서 실행 가능
python scripts\harness\backlog.py gates clear G-cur16-branch-push --evidence "④ git ls-remote 출력 1줄 확인 — 브랜치 원격 착지"
```

> ⚠ 이 CLI가 `UnicodeEncodeError`로 죽으면 **기등재 OPS-53의 알려진 cp949 결함**이다
> (MEMORY 2026-08-30 사고 ②). 그 경우 clear는 생략하고 ④의 출력만 전달하면 세션이 처리한다.

---

## 9. cross-ref

- `backlog/tasks/HARN-38-eos-number-collision-renumber.yaml` (본 태스크)
- `MEMORY.md` 2026-08-30 "EOS-54 HIT 검수 타이머 착지 + G0 조기 서명 + 사고 2건 기록" §사고 ①
- `scripts/harness/backlog.py:898-1022` (`_taken_id_numbers`·`cmd_add` 번호 가드)
- `scripts/harness/remote_claims.py:1179-1245` (`scan_remote_task_files` — fetch=False 명문)
- `scripts/harness/store.py:295-307` (`append_event` — 오프셋 없는 로컬 시각)
- `tests/harness/test_backlog_add_id_collision.py` (경우 B 사각의 기계 동결)
- 선례: ARCH-13(2026-07-18/25) · OPS-15(2026-07-29) · HARN-10 · HARN-15 · HARN-36 · HARN-07
- PR #902(main EOS-49/50 등재) · #908/#910(G0 서명) · #912(EOS-55) · 커밋 `ad7862ab`
