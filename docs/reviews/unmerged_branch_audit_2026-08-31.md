# 미머지 브랜치 전수 감사 — 2026-08-31

> **시점 스냅샷 선언.** 이 문서는 2026-08-31 `origin/main = 0b9faf66` 시점의 원격 상태를 고정한 것이다.
> 이후 브랜치·PR·태스크 상태 변화는 반영하지 않는다. **선행 판정 문서(08-04·08-11·08-29)는 수정하지 않는다.**
> 직전 정본: `docs/reviews/unmerged_branch_audit_2026-08-29.md`.

## 0. 전제 복구 — shallow 해소

세션 시작 시 클론이 shallow였고(브리핑도 "장기 미머지 브랜치 조회 불가"로 판정 보류), 그 상태에서는
ahead 수치·포팅 근거가 전부 오염된다. 판정 전 복구했다.

```bash
git rev-parse --is-shallow-repository        # true → 판정 금지
git fetch --unshallow origin
git fetch --prune origin '+refs/heads/*:refs/remotes/origin/*'
git rev-parse --is-shallow-repository        # false (실측)
git rev-list --count origin/main             # 904 (트렁크 히스토리 완전)
```

## 1. 모집단 분리 (실측)

| 구분 | 건수 | 비고 |
|---|---|---|
| 원격 ref 전수 | 37 | |
| 제외: `main`·`harness-claims` | 2 | harness-claims는 하네스 claim 저장소·작업 브랜치 아님 |
| 열린 PR이 소유 | 18 | 각 PR 소유 — 감사 범위 밖 |
| **감사 대상(PR 미오픈)** | **17** | 아래 §2~§4 |

**유령 PR(head 브랜치가 원격에 없는 열린 PR): 0건** — 열린 PR 18건의 head가 전부 원격에 실재한다.

**원격 claim 활성 2건**(`git show origin/harness-claims:claims/`): `EOS-65`(jw5m4a·PR #924) ·
`HARN-24`(xu50yl·PR #916) — 둘 다 PR 소유라 감사 대상과 겹치지 않는다.

## 2. 직전 배치 집행 확인 (`.github/branch-cleanup-request.txt` 관례)

4·5·6차 배치 19건 + 허용 패턴 밖 수동 삭제 4건을 `git ls-remote --heads`로 재확인:
**잔존 0/19 · 수동 4건 전건 삭제 완료.** 직전 배치는 완전히 집행됐다.

## 3. 3축 측정 결과 (감사 대상 17건)

`git rev-list --left-right --count origin/main...origin/<b>` · `git diff --name-only` ·
done-less 사각 보완(HARN-31: `src|tests|data|scripts` 신규 파일 신호).

**diff 0파일 브랜치는 0건** — 전량 흡수로 즉시 삭제 가능한 브랜치는 없다.

## 4. 4분류 판정

### ④ 제외 — 없음(감사 대상 17건 전부 판정 완료)

### ② 이미 추적 중 — 15건 (조치 불요·삭제 금지)

각 브랜치의 소유 태스크가 main에 실재하고 **status=todo(살아 있음)** 이며, 그 태스크 본문이
해당 브랜치를 실제로 지목하는지까지 교차 확인했다(`언급` = 태스크 YAML 내 브랜치 접미사 출현 횟수).

| 브랜치 | 소유 태스크 | status | 브랜치 지목 |
|---|---|---|---|
| `backup/ai-content-a3ysut-pre-rebase` | OPS-41 | todo | 2 |
| `whymath-data-platform-design-t608mk` | OPS-41 | todo | 3 |
| `whymath-constitution-rules-check-azdnov` | OPS-41 | todo | 2 |
| `whymath-service-operations-review-5t5lmv` | OPS-40 | todo | 2 |
| `whymath-ai-recommendation-review-q8tvcx` | OPS-38 | todo | 3 |
| `openrouter-setup-guide-e98dw4` | S3-28 | todo | 1 |
| `remaining-track-34zvse` | CUR-07 | todo | 2 |
| `whymath-issues-review-k20m0w` | MOB-18 | todo | 2 |
| `whymath-coding-architecture-iws58k` | ARCH-30 | todo | 2 |
| `whymath-pedagogy-review-gdmwhk` | PED-26 | todo | 6 |
| `whymath-pedagogy-review-uqyg79` | PED-26 | todo | 2 |
| `whymath-curriculum-design-6eejrv` | PB-08 | todo | 1 |
| `subject-problems-theory-check-7n9n72` | HARN-37 | todo | 2 |
| `human-bottleneck-tasks-6dszy0` | MISC-01·MISC-03·PB-02 | todo | 각 1 |
| `merge/human-bottleneck-6dszy0` | 〃(동일 계보) | todo | 각 1 |

> `7n9n72`는 MISC-05/06이 브랜치명을 적지 않으나 **HARN-37이 브랜치 단위 소유자**로 지목한다(언급 2).
> 소유가 끊긴 것이 아니라 좌석이 상위 태스크에 있는 형태다.

### ① 회수 태스크 등재 — 1건

**`claude/whymath-ai-content-design-vafylb`(b1218739) → `S4-59` 신규 등재**

소유였던 `HARN-35`가 **done**(PR #900)이 되면서 좌석이 사라졌는데, 그 회수는 이 브랜치의
`OPS-24`(→`OPS-53`으로 재등재)만 가져가고 **잔여 diff를 남겼다**. stray-code §4의
"소유 태스크가 done이어도 끝이 아니다"가 그대로 발생한 사례다.

잔여 7파일 중 소유자 판정:

| 잔여 | 소유 | 판정 |
|---|---|---|
| `residue_gate_demotion_battle.py` cp949 가드 + em dash 치환 | `OPS-53`(todo) acceptance ② | 소유 있음 — 범위 밖 |
| `OPS-24` yaml | `OPS-53`으로 재등재 완료 | 흡수 |
| `CLAUDE.md`·`MEMORY.md`·`events.ndjson`·`S4-16` yaml | main 우세(후행 갱신) | 흡수 |
| **`docs/standards/residue_gate_demotion_battle_2026-08-10.md`(104줄)** | **없음** | **미추적 고립** |

**부재 이중 확인(태스크 status 대조가 아니라 코드/문서 grep 교차):**

```bash
git grep -l '0\.0568'   origin/main origin/s4-16-blocked-evidence   # 0건
git grep -l '승격 기각'  origin/main origin/s4-16-blocked-evidence   # 0건
git grep -l '11h 36m'   origin/main origin/s4-16-blocked-evidence   # 0건
git show origin/main:src/backend/whymath_backend/harness/residue_gate_demotion_battle.py \
  | grep -c 'reconfigure'                                           # 0 (cp949 가드도 main 부재)
```

인플라이트 대조도 실시했다 — 열린 PR #844(`s4-16-blocked-evidence`)·#865가 같은 파일들을
건드리지만 **1차 강등전 기록은 어느 쪽도 싣고 있지 않다**.

**왜 회수 가치가 있나(단순 중복이 아님):** main `MEMORY.md` 446-464는 **후행 08-14 라운드**를
기록하며 결론(게이트 미승격·S4-16 blocked)은 보존돼 있다. 그러나 08-10 1차 라운드만 담은 축이 둘 있다 —
⑴ **결함류별 검출 내역**(`missing_condition` 0/3 · `unstated_equiprobability` 0/3 = "조건 결측 계열 실명")
— 게이트가 *어느* 결함류에 눈이 머는지는 `residue_gate_v4` 설계 입력이다.
⑵ **비용 실측**(qwen3.5:27b·`num_ctx` 8192에서 45콜 11h36m·콜당 ≈15.5분).
CLAUDE.md 검증 권위 서열("측정이 증명하지 못한 게이트는 승격되지 않는다")에 직결되는 기록이라
유실 시 미래 세션의 게이트 승격 오판 위험이 있다.

### ③ 삭제 가능 — **0건**

이번 회차에 삭제 배치에 올릴 브랜치는 없다. 17건 전부가 살아 있는 소유 태스크(15) ·
신규 회수 태스크(1) · 사람 결정 대기(1)에 묶여 있다. `.github/branch-cleanup-request.txt`는
**수정하지 않았다**(빈 배치를 만들지 않는다).

## 5. 별건 발견 — 추적자 0인 사람 결정 (게이트 신설)

`claude/whymath-mvp-plan-architecture-trjg5x`(c8abbc17)는 **저장소 최대 고립분**이다 —
신규 코퍼스 30종 **11,446문**(main 코퍼스 2,647의 4.3배)·결정론 생성기 30파일·저작 태스크
**S4-19~51 32건**(main 백로그 미등재. 본 감사의 고립 done 스캔도 34건을 재확인).

소유로 지목된 `PB-06`은 **done**이지만, 그 acceptance ①이 스스로 이렇게 적었다:

> "회수·병합은 이 태스크가 하지 않는다(**Kiki 소유**)."

즉 PB-06은 *조건 확정*만 완료했고(차단 조건 3건·커버리지 델타 78→130/435 산출),
**회수 행위 자체의 소유자는 게이트 대장에도 백로그에도 등재된 적이 없다.**
`backlog/gates.yaml` 17건 어디에도 이 결정이 없음을 실측 확인했다 — done 이후 **20일간 추적자 0**.

이것은 CLAUDE.md **"만료 없는 유예·제외 금지"**(유예는 반드시 만료·재확인 지점을 동반한다)의
위반 상태다. 조치: **`G-authoring-expansion-merge-decision`**(kind=decision·assignee=kiki·
remind_after_days=7) 신설. 결정에 필요한 정량 입력은 PB-06이 이미 산출해 뒀으므로 게이트 notes에
그대로 실었다(사이드카 차단 조건·커버리지 델타·PB-11 상환 사실 포함).

## 5.1 브리핑 '이미 포팅됨' 오분류 — 3·4회차 실측 (HARN-37 증거 보강)

세션 재개 시 브리핑이 9건을 "이미 포팅됨 — 원본 정리만 필요, **결정 불요**"로 분류했고,
그중 **이 감사가 반증한 2건**이 들어 있다. `HARN-37`(todo)이 2회차로 등재한 결함의
3·4회차이며, 그 태스크 notes가 예고한 위험("브리핑의 '원본 정리만 필요' 문구가 미회수
고립 브랜치를 삭제로 유도한다")이 그대로 재현됐다.

| 브랜치 | 브리핑 근거 커밋 | 그 커밋의 실제 착지 | 판정 |
|---|---|---|---|
| `vafylb` | `e8717347`(#736) | 강등전 1차 기록 파일 포함 **0건** | 오분류 — 본 감사 §4가 `S4-59`로 회수 등재 |
| `trjg5x` | `e16b694f`(#776) | `data/corpus/` 변경 **0건**(MEMORY·backlog·docs 전용) | 오분류 — 11,446문 미회수·§5가 게이트화 |

`e16b694f`는 제목부터 "저작 11,446문 **고립 4회차 실측**"이다 — 고립을 *기록한* 커밋이
그 고립의 *해소 근거*로 재활용됐다. 08-11 `40xspg`(1회차)·08-30 `7n9n72`(2회차)와 동일한
"문서 커밋을 포팅 근거로 오인" 유형이고, **`trjg5x` 건이 지금까지 중 최대 규모**다
(11,446문이 "결정 불요"로 분류됐다).

재현:
```bash
git show e16b694f --name-only --format='' | grep -c '^data/corpus/'   # 0
git show e8717347 --name-only --format='' | grep -c 'residue_gate_demotion_battle_2026-08-10'   # 0
```

조치: 새 태스크를 만들지 않고 **`HARN-37` notes에 3·4회차 증거를 병기**했다(중복 등재 금지).
그 태스크의 acceptance ②(문서·백로그 전용 커밋을 포팅 근거에서 배제)가 이미 이 결함을 덮는다.

## 6. 정직한 공백

- **잔여 15건의 acceptance 본문 전수 정독은 하지 않았다.** 소유 태스크의 *실재·생존(status=todo)·
  브랜치 지목*까지는 기계 확인했으나, 각 태스크의 acceptance가 그 브랜치의 **모든** 잔여 파일을
  덮는지는 검증하지 않았다. vafylb에서 실제로 발생한 "done 후 잔여 고아" 유형이 todo 태스크에도
  잠재할 수 있다 — 다만 todo인 동안은 좌석이 살아 있어 삭제 위험은 없다.
- **S4-19·S4-22 ID 충돌은 재확인만 하고 해소하지 않았다.** 본 감사의 고립 done 스캔이
  `S4-22`를 두 브랜치에서 서로 다른 태스크로 재확인했다(trjg5x=`elementary-addsub-pilot-corpus` ·
  k20m0w=`attempt-event-signal-consumer-wiring`). PB-06 차단 조건 ⑵가 이미 소유하므로 재등재하지 않았다.
- **코드 이식은 수행하지 않았다** — 이 감사의 범위가 아니다(`S4-59`를 `/drive`가 실행한다).

## 7. 검증 (전건 exit code)

```bash
python3 scripts/harness/backlog.py validate
# EXIT=0 — 태스크 462건·게이트 18건·트랙 3건 (감사 시점 458건 → main 머지분 반영 후 462건)

python3 scripts/harness/backlog.py overlap S4-59-demotion-battle-first-round-record-recovery
# EXIT=0 · 경고 11건 — 전건 `세션: ?`(비활성). 상대측 태스크의 넓은 paths(`backlog/**`·`docs/**`)가
# 내 4파일을 포함해서 뜨는 것이며, 내 paths를 더 좁혀서 없앨 수 있는 종류가 아니다.

python3 scripts/harness/backlog.py overlap S4-59-demotion-battle-first-round-record-recovery --in-flight-only
# EXIT=0 · "in-flight 범위에서 겹침 없음 (2건 비교)" — 실제 병렬 충돌 0이라는 판정은 이쪽이다.

python3 scripts/harness/backlog.py next --n 60
# S4-59가 30위로 노출(배선 확인). `--n 3`으로는 보이지 않는다.
```

### ⚠ 이 절의 1차 기재는 틀렸다 — PR #927 Codex 리뷰(P2)가 잡아 정정

최초 기재는 `overlap`을 **인자 없이** 적고 "겹침 경고 0건", `next --n 3`에 "S4-59 노출 확인"이라고
적었다. 실측하면 둘 다 성립하지 않는다:

- `overlap`은 위치 인자 `id`가 **필수**라 인자 없이는 `EXIT=2`(usage 오류)로 죽는다. 당시 판정에
  쓴 것은 `overlap 2>&1 | grep -c 'S4-59'` → `0`이었는데, 이 `0`은 "겹침 없음"이 아니라
  **"명령이 실패해 아무것도 출력하지 않음"**이었다. 정상 상태와 실패 상태가 같은 값을 내므로
  **변별력이 없는 검증**이다 — CLAUDE.md "변별력 없는 검증 스텝 금지"·"검사 명령의 출력을
  억제하거나 잘라서 판정 금지(판정은 exit code로)"에 정면으로 걸린다. 이 감사 문서가 §4에서
  바로 그 원칙("성공/실패가 다른 값을 내는 검사")을 내세우면서 자기 검증에서 그것을 어겼다.
- `next --n 3`의 실제 출력은 EOS-60·HARN-38·CUR-12이고 **S4-59는 30위**다.

정정 후 사실관계: **겹침 경고는 11건이며 0건이 아니다.** 다만 전건 비활성 세션이고
`--in-flight-only`가 겹침 0을 내므로 **병렬 충돌은 없다**는 결론 자체는 유지된다 —
바뀐 것은 근거이지 판정이 아니다. `paths` 축소(19→11)의 효과도 실재하나 0이 되지는 않는다.

부기(별건 관찰, 이번 범위 밖): 경고 중 `OPS-19 ↔ docker-compose*.yml ⊇ docs/standards/…md`는
glob 포함 판정의 오탐으로 보인다(`docker-compose*.yml`이 `docs/…`를 포함할 수 없다).
`overlap`의 프리픽스 매칭이 `*`를 경로 구분자까지 삼키는 것으로 추정되며, 확인·수정은
이 감사의 범위가 아니라 별도 판단이 필요하다.

`S4-59`는 최초 `--id S4-53` 시도를 CLI가 **번호 충돌로 거부**(로컬 백로그 S4-53 선점)해
제안 번호 `S4-59`를 그대로 채택했다 — 우회하지 않았다(거부는 판정이지 장애물이 아니다).
최초 `paths`가 `docs/standards/**`·`backlog/tasks/**`로 넓어 겹침 경고 19건이 떴고,
REC-09 선례대로 **실제 touch set 4파일로 좁혀** 11건으로 줄였다.
