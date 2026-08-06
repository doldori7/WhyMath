# 병렬 세션 개발 표준 (Parallel Claude Code Sessions)

> 여러 Claude Code 세션을 **동시에** 열어 앱을 개발할 때 git 충돌·상호 간섭을 최소화하는 규칙.
> 이 저장소는 도메인이 물리적으로 분리(`src/*`)되어 있고 CI가 경로 기반이라 병렬 개발에
> 유리하다. 아래 규칙만 지키면 충돌은 예외적 상황으로 줄어든다.

---

## 핵심 원칙 (한 줄)

> **1 세션 = 1 도메인 = 1 브랜치 = 1 worktree**

세션마다 건드리는 최상위 도메인 폴더가 겹치지 않게 배정한다. 이것만으로 충돌 대부분이 사라진다.

---

## 1. 도메인 소유 지도

| 도메인 슬러그 | 폴더 | 담당 서브에이전트 | 계층 |
|---|---|---|---|
| `backend` | `src/backend/` | backend-engineer · llm-architect | L3·L5 |
| `data-pipeline` | `src/data-pipeline/`, `data/`, `docs/data/` | data-engineer | L1 |
| `ml-models` | `src/ml-models/` | ml-engineer | L2 |
| `mobile` | `src/mobile/` | flutter-engineer | L5 |
| `web` | `src/web/` | (프론트) | L5 |
| `docs` | `docs/` (아래 hot-file 제외) | 전원 | 횡단 |
| `infra` | `infra/`, `.github/` | backend-engineer | 횡단 |

- 한 세션은 **자기 도메인 폴더 밖을 수정하지 않는다.** 다른 도메인 변경이 필요하면 그
  도메인 세션에 맡기거나, 그 작업만 별도 브랜치로 분리한다.
- `.github/CODEOWNERS` 의 영역 구분과 정합한다(현재 Phase 1은 전부 `@doldori7`).

---

## 2. 동시 편집 금지 — 공유 hot files

아래 파일들은 여러 세션이 동시에 만지면 충돌이 잘 난다. **원칙적으로 한 번에 한 세션만** 수정:

| 파일/경로 | 이유 | 규칙 |
|---|---|---|
| `MEMORY.md` | 대형 append 로그 | `.gitattributes` **union-merge** 로 자동 병합됨. 단 **새 항목은 항상 파일 끝에 append**(같은 줄 동시 수정 금지) |
| `src/backend/.../schema/` | 공유 스키마·계약 | 스키마 변경은 **전용 단독 세션에서 먼저 머지** 후 다른 세션이 rebase |
| `src/backend/pyproject.toml`, `src/data-pipeline/pyproject.toml` | 의존성 | 의존성 bump는 전용 세션·전용 PR로 분리, 먼저 머지 |
| `src/mobile/pubspec.yaml` | Flutter 의존성 | 동상 |
| `src/web/graphing-calculator/package-lock.json` | 13만 줄 lock | 의존성 변경 세션에서만 재생성 |
| `CLAUDE.md`, `ROADMAP.md` | 구조화 문서(union 부적합) | 동시 편집 금지 — 필요 시 짧게 한 세션이 처리 |

> **왜 `CLAUDE.md`/`ROADMAP.md`는 union-merge를 안 쓰나?**
> union merge는 append-only 로그에만 안전하다. 구조화된 문서에 쓰면 논리적으로 깨진 병합이
> 생기므로 `MEMORY.md`에만 적용한다.

---

## 3. 브랜치 네이밍

```
claude/<domain>-<task-slug>-<짧은난수>
예) claude/backend-prm-verify-a1b2c3
    claude/mobile-ocr-overlay-7f9e21
```

- `main` 직접 push 금지 (`.github/branch-protection-setup.md` 참조). 항상 PR 경유.
- Linear history(squash/rebase)만. merge commit 금지.
- **현실 반영 (2026-07-16)**: Claude Code 웹 세션은 자동 생성 브랜치명
  (`claude/dazzling-ramanujan-4aalh8` 등)을 쓰므로 도메인 프리픽스를 강제할 수 없다.
  **도메인 소속의 정본은 브랜치명이 아니라 claim한 태스크의 `layer` 필드다** —
  하네스가 태스크 단위로 소유권을 추적하므로 브랜치명 규약은 로컬 worktree
  (`new-session-worktree.sh`) 사용 시의 권장 관례로 유지된다.

---

## 4. worktree 워크플로우 (권장)

단일 워킹트리에서 브랜치를 오가면 세션끼리 인덱스가 충돌한다. 세션마다 **독립 worktree**를 쓴다.

### 헬퍼 스크립트 (권장)
```bash
scripts/new-session-worktree.sh <domain> <task-slug>
# 예)
scripts/new-session-worktree.sh backend prm-verify
#  → worktrees/backend-prm-verify-<난수>/ 에 새 브랜치로 체크아웃
#  → 그 디렉토리에서 `claude` 실행
```

### 수동 (동일 동작)
```bash
git fetch origin main
git worktree add -b claude/backend-prm-verify worktrees/backend-prm-verify origin/main
cd worktrees/backend-prm-verify && claude
```

### 정리
```bash
git worktree remove worktrees/backend-prm-verify
git branch -D claude/backend-prm-verify   # 로컬 브랜치 — 원격 머지 완료 후
```

`worktrees/` 는 `.gitignore` 에 있어 추적되지 않는다.

> **⚠️ 컨테이너(Claude Code 웹) 세션은 *원격* 브랜치를 삭제할 수 없다 — HTTP 403 (HARN-16)**
>
> 위 `git branch -D`는 *로컬* 삭제라 컨테이너에서도 된다. 그러나 **원격** 브랜치 삭제
> (`git push origin --delete <branch>` = zero-SHA push)는 이 실행 환경의 git 프록시가
> **HTTP 403으로 거부**한다. 이건 "권한 없음"이 아니라 **삭제 연산 자체의 차단**이다 —
> 근거: 일반 push·PR 생성·머지·브랜치 *생성* push는 정상(exit 0)이고, **세션이 방금 만든
> 브랜치조차** 삭제 push만 403이며(2026-08-06 `tmp-delete-probe-ignore-hn16` 변별 실측:
> create-push `* [new branch]` exit 0 → delete-push `error: RPC failed; HTTP 403`), 동일 삭제
> 명령이 Kiki 로컬(Windows·비프록시)에서는 41건 전건 성공했다(2026-08-04). 즉 릴레이가
> *삭제 refspec만* 막는다.
>
> **그래서 이 하네스는 "1 태스크 = 1 브랜치"가 아니라 "1 세션 = 1 브랜치"다** — 태스크마다
> 브랜치를 파면 컨테이너 세션이 해제(삭제)할 수 없어 브랜치가 영구 누적되기 때문이다
> (`build_harness.md` §CAS·원격 claim 참조). 병합된 브랜치·probe 브랜치(`tmp-*`) 정리가 필요하면
> **컨테이너에서 시도하지 말고**(40회 403을 받는 길) Kiki에게 실행 명령으로 위임한다:
>
> ```powershell
> # Windows PowerShell (= Phaiakes9). 원격 브랜치 삭제는 비프록시 로컬에서만 된다.
> cd C:\Users\kiki\Desktop\__AI\WhyMath
> git push origin --delete <삭제할_원격_브랜치명>
> # 예(이번 세션 probe 잔여): git push origin --delete tmp-delete-probe-ignore-hn16
> ```
>
> **우회 금지(CLAUDE.md 「거부의 우회 금지」·프록시 README "403은 재시도·우회 말고 보고")**:
> 프록시 정책 변경 시도·직접 `github.com` push·API 삭제 등 우회 경로를 탐색하지 않는다. 403은
> 장애가 아니라 *판정*이다 — 삭제는 소유자(Kiki) 액션으로 넘긴다.

---

## 5. 머지 순서 (충돌 최소화)

1. **작고 공유되는 변경 먼저**: 스키마·의존성·`docs` 공용 변경을 먼저 머지한다.
2. 큰 도메인 브랜치는 자주 최신 `main` 을 rebase 한다:
   ```bash
   git fetch origin main && git rebase origin/main
   ```
3. CI는 경로 기반(`ci.yml`)이라 도메인 브랜치는 자기 영역 테스트만 돌아 빠르다.
4. PR별 이전 CI 실행은 자동 취소되므로 재푸시 부담이 낮다.

---

## 6. 충돌이 났을 때

- **`MEMORY.md`**: union-merge라 대개 자동 병합됨. 중복 라인이 보이면 수동 정리.
- **의존성 파일**: 충돌 시 한쪽 기준으로 재생성(`uv lock` / `flutter pub get` / `npm install`) 후 커밋.
- **스키마**: 절대 임의 병합하지 말 것 — 스키마 소유 세션이 조정.

---

## 7. 하네스 강제 장치 (v1.1 — 관례가 코드로 집행되는 지점)

이 문서의 규칙 중 상당수는 빌드 하네스가 기계적으로 집행한다
(`docs/standards/build_harness.md` §3b·§3c 상세):

| 관례 (이 문서) | 집행 코드 | 강제 수준 |
|---|---|---|
| 같은 태스크 동시 착수 금지 | `start`의 **원격 claim** (`harness-claims` 브랜치 CAS push — 한쪽만 성공) | 즉시 차단 |
| 다른 세션 작업 확인 | SessionStart 브리핑·`next`가 원격 claim 노출·후보 제외 | 자동 |
| 도메인/파일 범위 밖 수정 금지 | 태스크 `paths` 선언 + `start` 프리플라이트·check-edit 훅 (`scope_drift`) | warn→block |
| 타 세션 작업 범위 침범 금지 | check-edit 훅 (`path_overlap`) — 편집 파일 vs in-flight paths | warn→block |
| 작업은 태스크로 등록 후 착수 | check-edit 훅 (`adhoc_edit`) — claim 없이 `src/*` 편집 감지 | warn |
| 죽은 세션의 claim 잔존 | `claims reap` (TTL·done·미존재 3중 기준) + CI harness-integrity | 자동 청소 |
| backlog 무결성 | PostToolUse 훅 + CI `harness-integrity` job | 차단 |

- 정책 수준은 `backlog/policy.yaml`이 정본 — 전 rule warn으로 시작, 측정
  (`policy report`) 후 rule별 block 승격.
- 훅은 판정이 불확실하면 무조건 통과한다(fail-open) — 조율 장치가 개발을
  볼모로 잡지 않는다. 유일한 예외는 원격 claim **conflict**(확정 신호)의 즉시 차단.

---

## 요약 체크리스트

- [ ] 세션마다 도메인을 하나씩 배정했는가?
- [ ] `scripts/new-session-worktree.sh` 로 격리 worktree를 만들었는가?
- [ ] 자기 도메인 폴더 밖(특히 hot files)을 건드리지 않는가?
- [ ] `MEMORY.md` 새 항목을 **파일 끝에** append 했는가?
- [ ] 의존성·스키마 변경을 전용 세션·전용 PR로 분리했는가?
- [ ] 큰 브랜치를 자주 `main` 에 rebase 하는가?
