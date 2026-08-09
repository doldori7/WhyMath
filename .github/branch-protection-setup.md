# `main` 브랜치 보호 규칙 — 수동 설정 가이드

> GitHub REST API의 *Branch Protection* 엔드포인트에 현재 토큰으로 접근할 수 없어
> (`Resource not accessible by integration` — 2026-07-26 실측) 이 단계는
> **GitHub Settings UI에서 5분 수동 작업**이 필요합니다.
>
> 자동 가능한 부분(CODEOWNERS·CI status check)은 이미 코드로 표현되어 있습니다 —
> 이 가이드는 그것들을 *강제하는* 정책만 다룹니다.

---

## 📋 사전 브리핑 (Kiki 직접 수행 과제)

1. **과제 명칭** — `main` 브랜치 보호 규칙 설정 (특히 **required status checks 13종 등록**)
2. **목적** — CI가 실패한 코드가 `main`에 들어가지 못하게 막는다. 현재는 이 설정이
   불완전해 **전체 테스트·mypy·커버리지 잡(`backend — lint·type·test`)이 머지를 막지
   못한다** — 2026-07-26에 이 구멍으로 실제 red가 main에 들어갔다(아래 사고 기록).
3. **구체적 절차** — Settings → Branches → `main` 규칙 편집 → *Require status checks*
   섹션에서 아래 13개 이름을 하나씩 검색해 추가 → Save. 소요 약 5분(체크 13개 검색·추가가
   대부분). 나머지 항목(PR 필수·linear history 등)은 이미 설정돼 있으면 건드리지 않는다.
4. **성공 기준** — §저장 후 확인의 **자가검증 B**(가장 중요): 새 PR에서 `backend` 잡이
   *아직 돌고 있는 동안* 머지 버튼이 **비활성**이고 "Required statuses must pass"가
   보이면 성공. 머지가 가능하면 **실패**(= 등록이 안 된 것) → 검색 이름 오타를 의심하고
   §트러블슈팅 참조.
5. **실행 환경** — 웹 브라우저(GitHub). PowerShell·리포 클론 불요. 저장소 admin 권한 필요.
6. **창 구분** — 브라우저 탭 1개. 서버·프로세스 점유 없음, 이후 조작 제약 없음.

---

## 진입 경로

1. https://github.com/doldori7/WhyMath 접속
2. 우상단 **Settings** 탭 → 좌측 사이드바 **Branches**
3. *Branch protection rules* 섹션 → **Add branch protection rule** 또는 **Add rule** 클릭

---

## 적용할 설정 (체크 박스 그대로 따라가기)

### Branch name pattern
```
main
```

### Protect matching branches
- [x] **Require a pull request before merging**
  - [x] Require approvals — *최소 1명*
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [x] Require review from Code Owners *(CODEOWNERS 파일 활용)*

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - **Status checks that are required** — 아래 블록의 이름을 *그대로* 검색해 전부 추가:

<!-- REQUIRED_CHECKS_BEGIN — 이 블록은 tests/infra/test_required_checks_doc.py가 ci.yml과 대조해 동결한다. 잡 추가·개명 시 여기도 갱신해야 CI가 통과한다. -->
- `changes — 변경 경로 판별`
- `backend — lint·type·test`
- `backend — 마이그레이션·통합 (실 PG)`
- `data-pipeline — lint·type·test`
- `data-pipeline — 적재 통합 (실 PG)`
- `data-pipeline — 적재 통합 (실 Neo4j)`
- `mobile — flutter analyze·test`
- `web — graphing-calculator test·build`
- `infra-contracts — 운영 자산 계약 테스트 (tests/infra)`
- `docker-build — 이미지 빌드·기동 스모크(/health/live)`
- `infra/phaiakes9 — bash syntax`
- `policy-guard — CLAUDE.md 금기 가드`
- `harness-integrity — backlog 무결성·claim 교차 검증`
- `declared-unwired-audit — 선언≠배선 4축 정적 감사 (OPS-22)`
<!-- REQUIRED_CHECKS_END -->

  **제외 1종**: `e2e-nightly — 관통 슬라이스 (실 PG·야간)`는 `if: github.event_name == 'schedule'`
  라 PR에서 항상 skip된다. required로 걸어도 통과하지만(아래 참조) *야간 잡을 머지 게이트로
  선언*하는 것은 의미가 어긋나므로 넣지 않는다.

  **경로 필터로 skip되는 잡을 required로 걸어도 안전한 이유**: GitHub은 `skipped` 결론을
  required check 충족으로 센다. 이 레포는 이미 그 동작에 의존한다 — `ci.yml`의
  "doc-only PR이면 skip(비용 절감·**required check는 skipped=충족**)" 주석 3곳. 따라서
  `docker-build`(docker 경로 변경 시에만 실행)처럼 조건부 잡도 목록에 넣어야 한다. 빼면
  *실행됐을 때* 실패해도 머지를 막지 못한다.

  ⚠️ CI workflow가 *한 번이라도 실행*되어야 검색 결과에 등장합니다.
  → 먼저 이 PR을 만들거나 main에 한 번 push하여 CI를 가동한 후 등록하세요.

> ### 🔴 왜 이 목록이 중요한가 (2026-07-26 사고)
>
> 이 문서는 오랫동안 required check를 **3종만**(`data-pipeline`·`infra/phaiakes9`·
> `policy-guard`) 나열했고 **`backend — lint·type·test`가 빠져 있었다**. CI 잡이 3개에서
> 14개로 늘어나는 동안 목록이 따라가지 못한 것이다.
>
> **더 나아가 — 실측 결과 그 3종조차 등록돼 있지 않았다**(`enforcement_level=off`·
> `checks=[]`, 자가검증 C). `protected: true`(PR 필수·force-push 차단)는 켜져 있었으나
> **status check 강제 자체가 통째로 꺼져 있었다**. 즉 "backend만 빠진 것"이 아니라
> **어떤 CI 잡도 머지를 막지 못하는 상태**였다.
>
> 결과: 전체 테스트·mypy·커버리지를 보는 **가장 중요한 잡이 머지를 막지 못했다.**
> PR #603·#604·#605·#606·#607 **다섯 번 연속** 이 잡의 완주 전에 auto-merge가 발동했고,
> #606에서 실제로 `1 failed`가 나 **main이 red**가 됐다(테스트 전역 오염). 그 red를 고치는
> PR #607조차 같은 방식으로 머지됐다 — 수정이 맞는지는 머지 이후에야 알 수 있었다.
>
> 목록의 *정확성*은 코드로 지킬 수 있어 `tests/infra/test_required_checks_doc.py`로 동결했다
> (오타 하나면 UI 검색이 실패하고 그 체크는 조용히 미설정으로 남는다). 그러나 **설정 자체를
> 적용하는 것은 Kiki의 UI 작업**이다 — GitHub Branch Protection API는 이 토큰으로 접근
> 불가가 실측 확인됐다(`Resource not accessible by integration`).

- [x] **Require conversation resolution before merging**
  - 코드 리뷰 코멘트가 모두 해결되어야 머지 가능

- [x] **Require linear history**
  - merge commit 금지 → squash 또는 rebase만. 히스토리 깔끔.

- [ ] Require deployments to succeed before merging *(Phase 1에서는 X)*

- [ ] Require signed commits *(Phase 2+ 권장)*

### Rules applied to everyone including administrators
- [x] **Do not allow bypassing the above settings**
  - *주의*: 본인에게도 적용. 1인 단계에서는 약간 불편할 수 있으나
    *우발적 main 직접 push 방지* 효과가 큼.

- [x] **Restrict who can push to matching branches**
  - 비워두기 (PR만으로 머지)

- [x] **Allow force pushes** — **체크 해제** (force push 차단)
  - *Specify who can force push* 도 비워두기

- [x] **Allow deletions** — **체크 해제** (main 삭제 방지)

---

## 저장 후 확인

1. 페이지 하단 **Create** 또는 **Save changes** 클릭
2. Branches 탭에 *Branch protection rule applied to* `main` 확인

### 자가검증 C — API로 직접 읽는다 (**가장 확실·이것부터**)

브랜치 보호 *설정* 엔드포인트(`/protection`)는 admin 권한이 필요해 읽기 토큰으로 403이지만,
**`/branches/main`은 `metadata=read`로도 읽히고 그 안에 required check 요약이 들어 있다**
(2026-07-26 실측). 눈으로 세는 A보다 정확하고, 머지 타이밍을 지켜보는 B보다 즉시 나온다.

```bash
# 어디서든(claude 세션 포함) 실행 가능 — 토큰만 있으면 된다
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/repos/doldori7/WhyMath/branches/main" |
  python3 -c "import sys,json;p=json.load(sys.stdin)['protection']['required_status_checks'];print(p['enforcement_level'], len(p['checks']), sorted(c['context'] for c in p['checks']))"
```

| 출력 | 판정 |
|---|---|
| `off 0 []` | ❌ **required check가 하나도 없다** — 미설정 상태 |
| `non_admins 13 [...]` 또는 `everyone 13 [...]` | ✅ 13종 등록 완료 |
| 개수가 13 미만 | ⚠️ 일부 누락 — 목록 출력과 문서 블록을 1:1 대조 |

> **설정 전 실측값(2026-07-26)**: `enforcement_level=off · contexts=[] · checks=[]`.
> 즉 문서가 나열하던 3종조차 **실제로는 등록돼 있지 않았다** — `protected: true`(PR 필수·
> force-push 차단 등)는 켜져 있으나 **status check 강제만 통째로 꺼져 있던** 상태다.
> 이 검사는 미설정 상태에서 확실히 `off 0 []`를 내므로 변별력이 있다.

### 자가검증 A — 등록된 체크 *개수*를 눈으로 센다

규칙 편집 화면의 *Require status checks* 목록에 **13개**가 있는지 센다.
13개 미만이면 검색이 빈 이름이 있었다는 뜻이다(오타·개명). 위 목록과 1:1 대조하라.

> **왜 개수를 세나**: UI는 "검색 결과 없음"을 조용히 보여줄 뿐 실패를 만들지 않는다.
> 추가했다고 생각하고 넘어가면 그 체크는 **미설정으로 남는다** — 이것이 2026-07-26
> 사고에서 `backend` 잡이 required가 아니었던 경로다.

### 자가검증 B — 실패 상태에서 실제로 막히는지 (가장 중요)

**이 검증만이 "설정이 작동한다"를 증명한다.** A는 화면에 보이는 것을 셀 뿐이다.

1. 아무 PR이나 새로 연다(문서 한 줄 수정으로 충분).
2. CI가 시작되면 **`backend — lint·type·test`가 아직 `in_progress`인 동안** PR 화면을 본다.
3. **성공 판정**: Merge 버튼이 비활성이고 *"Required statuses must pass before merging"*
   또는 *"Waiting for status to be reported"*가 보인다.
   **실패 판정**: 그 잡이 도는 중인데 머지가 가능하다 → **등록 안 됨**. §트러블슈팅으로.

> **이 검증이 변별력을 갖는 이유**: 설정 전 상태(현재)에서는 실제로 머지가 **가능하다**.
> PR #603·#604·#605·#606·#607이 전부 이 잡의 완주 전에 머지됐다 — 즉 이 검사는 실패
> 상태에서 실패 신호를 낸다(성공/실패 양쪽에서 같은 값을 내는 검사가 아니다).

3. 다음 push 시도가 막히는지 검증:
   ```bash
   # 막혀야 함:
   git checkout main
   git commit --allow-empty -m "직접 push 시도"
   git push origin main
   # → ! [remote rejected] main -> main (protected branch hook declined)
   ```
4. PR 흐름이 정상 작동하는지 검증:
   ```bash
   git checkout -b test/protection-check
   git commit --allow-empty -m "PR 흐름 검증"
   git push -u origin test/protection-check
   # → GitHub에서 PR 생성 → CI 통과 → Code Owner 승인 → Merge
   ```

---

## 트러블슈팅

### Status check가 검색 결과에 안 보임
- CI workflow가 한 번도 실행되지 않은 상태. 임의 PR을 만들어 CI를 가동한 뒤 설정.

### Code Owners 검토가 자동 요청되지 않음
- `.github/CODEOWNERS` 파일의 사용자명이 GitHub 계정과 일치하는지 확인 (대소문자·@ 포함)
- 본인이 PR 작성자면 *Code Owner = 작성자* 충돌 → 별도 리뷰어 추가 (Phase 2 합류 시 자연 해소)

### Force push가 *여전히* 가능
- *Allow force pushes* 체크 해제 누락 가능. 위 체크리스트 다시 확인.

---

## 적용 후 MEMORY.md 업데이트

설정 완료 후 `MEMORY.md` *2026-05-14: GitHub 원격 저장소 연결* 결정 로그 마지막 줄
> "다음 단계는 GitHub Settings → Branches 에서 `main` 보호 규칙 ... 적용 예정."

을 다음으로 교체:

```
**상태**: 확정. main 브랜치 보호 규칙 적용 완료 (2026-MM-DD):
PR 1+승인·Code Owners·CI status check 3종·linear history·force-push 차단·deletion 차단.
```
