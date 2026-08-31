# EOS-49/50/51 번호 충돌 규명 — 원인·재등재·재발 조건 (HARN-38)

> **작성일**: 2026-08-31 | **태스크**: `HARN-38-eos-number-collision-renumber`
> **대상**: kiki 머신 브랜치 `backend/cur-16-concept-edge-prerequisite-meta-v2` 커밋 `3b7bab6f`

---

## 1. 무엇이 충돌했나 (실측)

커밋 `3b7bab6f`("G-eos-g0 clear — 검증설계서 v1 서명", 08-31 00:06)가 태스크 3건을 신규 등재했는데,
그 세 번호가 **이미 main에서 다른 태스크가 쓰고 있는 번호**였다.

| 브랜치가 등재한 것 | main의 동번호 점유자 | 판정 |
|---|---|---|
| `EOS-49-problem-quarantine-status` | `EOS-49-concept-version-contract` (todo) | 이종 → **재등재** |
| `EOS-50-generation-log-prompt-seed` | `EOS-50-publish-gate-pipeline` (todo) | **내용 중복** → 재등재 불요 |
| `EOS-51-content-lifecycle-state-wiring` | `EOS-51-verification-design-freeze` (**done**) | 이종 → **재등재** |

full-ID는 슬러그가 달라 `validate`가 통과한다 — 깨지는 것은 **사람·문서·커밋의 번호 참조**다
("EOS-51 봐줘"가 두 태스크를 가리켜 결정 불가가 된다). HARN-10이 기록한 실패 유형의 3회차.

## 2. EOS-50은 왜 재등재하지 않았나 (중복 판정 근거)

브랜치의 `EOS-50-generation-log-prompt-seed`가 요구한 것을 main의 **`EOS-55`(done)**가 이미
충족한다. 요구 대 실측 대조:

| 브랜치 EOS-50 요구 | main 실측 (`schema/provenance.py` `GenerationLog`) |
|---|---|
| ① prompt 본문(또는 해시+참조)·seed 컬럼 + alembic | `prompt_version` · `seed` · `input_sha256` · `input_snapshot` 실재 |
| ② 생성 경로가 실제 prompt·seed를 적재함을 테스트 동결 | EOS-55 acceptance ③이 두 경로(problem_corpus_accumulate·pregenerate) 통합 테스트를 요구하며 done |
| ③ 백필 정책 명시 — 복원 불가분은 null 자인, 침묵 미기입 금지 | `restore_input_snapshot`이 미기록 시 복원 불가를 명시 반환(침묵 금지) |

**결론**: 같은 사안을 다른 이름으로 두 번 추적하지 않는다. 재등재하면 EOS-55와 이중 추적이 된다.

## 3. 재등재 결과

CLI(`backlog.py add`)가 번호를 배정했다 — **수기 배정 금지 규칙(HARN-10) 준수**. 첫 시도에서
`EOS-67`을 요청했으나 가드가 원격 인플라이트(`claude/review-status-differences-jw5m4a`의
`EOS-67-core-adapter-import-contract`)를 잡아 거부하고 `EOS-71`을 제안했다 — 가드가 실제로 일했다.

| 신규 ID | 원본 | 내용 |
|---|---|---|
| `EOS-71-problem-quarantine-status` | 구 EOS-49 | 결함 문항의 비파괴 격리(quarantined 상태·서빙 fail-closed) |
| `EOS-72-content-lifecycle-state-wiring` | 구 EOS-51 | ContentLifecycleState 11단계 배선 또는 폐기 결정 |

acceptance·paths·depends_on·notes를 원본에서 그대로 이관했고, notes에 이관 경위를 부기했다.

**구 YAML은 삭제하지 않았다** — 그 파일들은 kiki 머신 브랜치에만 존재하고 main에 착지한 적이
없다. 삭제할 대상이 이 트리에 없으며, **그 브랜치가 머지되면 충돌이 재발**하므로 정리는 브랜치
소유 세션의 몫이다(§5 조치 요청).

## 4. "G-eos-g0 clear" 커밋 제목은 실제 clear가 아니다 (acceptance ②)

`3b7bab6f`의 제목은 "G-eos-g0 clear — 검증설계서 v1 서명"이지만, **그 커밋은 `backlog/gates.yaml`을
전혀 건드리지 않았다**(변경 파일 5건 중 gates.yaml 0건 — 실측). 변경분은 events.ndjson·CUR-16.yaml·
신규 태스크 3건뿐이다.

게이트의 실제 clear는 **main 계보**에 있다:
- `ad7862ab` — G-eos-g0 clear(2026-08-30, #909 스택)
- 최종 문안은 `d52d9a62`(#910)에서 병렬 두 세션 기록을 병합해 확정

즉 그 브랜치 커밋 제목을 근거로 "서명이 그 브랜치에 있다"고 읽으면 안 된다. 서명 실체는 main이다.

## 5. 충돌 경위 규명 — 가드는 왜 못 막았나 (acceptance ③)

**타이밍 실측**:

| 시각 | 사건 |
|---|---|
| 08-28 15:26 | 브랜치 분기점(`e6f5e966`) |
| 08-30 11:38 | main에 `EOS-49`·`EOS-50` 등재(`dabbc271`) |
| 08-31 00:06 | 브랜치가 같은 번호로 등재(`3b7bab6f`) |

`3b7bab6f` 시점의 **브랜치 tree에는 main의 EOS-49/50/51이 하나도 없었다**(실측: 3건 모두 부재).
분기 후 이틀간 main이 앞서갔고, 그 브랜치는 그 사실을 자기 tree만으로는 알 수 없었다.

**가드의 3중 출처가 왜 전부 비껴갔나** (`backlog.py` `_taken_id_numbers`):

1. **로컬 백로그** — 브랜치 tree 기준이라 main 신규분이 없었다. 통과.
2. **원격 claim 대장**(`refs/claims/*`) — **현재 원격에 claims ref가 0건**이다(`git ls-remote` 실측).
   대장이 비어 있으니 참조할 근거 자체가 없다. 이는 2026-07-27에 등재된 기존 문제
   (CCR git 프록시가 `refs/claims/*` push를 403으로 차단 → 상시 fail-open)의 연장선이며,
   HARN-07 폴백이 아직 이 축을 메우지 못했음을 보여준다.
3. **원격 브랜치 파일명 스캔**(HARN-15 `scan_remote_task_files`) — 기본이 `fetch=False`라
   **이미 로컬에 있는 remote-tracking ref만** 본다(네트워크 0 설계). kiki 머신에서 main을
   최근 fetch하지 않았다면 `origin/main`의 신규 태스크 파일이 로컬에 없고, 스캔은 그것을
   존재하지 않는 것으로 본다.

**즉 3중 방어가 모두 "브랜치 로컬이 낡았다"는 하나의 조건에서 동시에 무력해진다.** 세 출처가
독립적으로 보이지만 ②는 인프라 문제로 상시 비어 있고, ①③은 같은 로컬 tree 신선도에 의존한다.

## 6. 남은 조치

- **[브랜치 소유 세션]** `backend/cur-16-concept-edge-prerequisite-meta-v2`를 머지하기 전에
  `backlog/tasks/EOS-49-problem-quarantine-status.yaml`·`EOS-50-generation-log-prompt-seed.yaml`·
  `EOS-51-content-lifecycle-state-wiring.yaml` 3건을 **삭제**해야 한다. 내용은 이미
  `EOS-71`·`EOS-72`로 이관됐고 EOS-50은 EOS-55 중복이라 되살릴 것이 없다. 그대로 머지하면
  main의 동번호 3건과 파일이 공존해 충돌이 확정된다.
- **[가드 개선 후보]** `add` 실행 시 원격 스캔 전에 `origin/main`을 fetch하거나, 최소한
  "remote-tracking ref가 N일 이상 낡았다"를 경고로 띄우는 축. 현재는 낡은 로컬이
  **조용히** 통과한다 — 실패가 신호를 내지 않는 형태다. (별도 태스크 등재는 이 조사의
  범위 밖 — 가드 설계 변경이므로 HARN 축에서 판단할 사안으로 남긴다.)

---

**방법 한계(정직)**: kiki 머신에서 `add`가 실행될 당시의 로컬 fetch 상태는 사후 재구성이
불가능하다(그 시점 `.git/refs/remotes` 스냅샷이 없다). §5-3은 코드 경로상 **가능한 설명**이며,
§5의 타이밍·tree 부재·claims 0건은 전부 실측이다.
