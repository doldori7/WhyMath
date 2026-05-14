# `main` 브랜치 보호 규칙 — 수동 설정 가이드

> GitHub REST API의 *Branch Protection* 엔드포인트가 현재 Claude의 MCP 도구셋에 없어
> 이 단계는 **GitHub Settings UI에서 5분 수동 작업**이 필요합니다.
>
> 자동 가능한 부분(CODEOWNERS·CI status check)은 이미 코드로 표현되어 있습니다 —
> 이 가이드는 그것들을 *강제하는* 정책만 다룹니다.

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
  - **Status checks that are required** (검색 후 추가):
    - `data-pipeline — lint·type·test`
    - `infra/phaiakes9 — bash syntax`
    - `policy-guard — CLAUDE.md 금기 가드`

  ⚠️ CI workflow가 *한 번이라도 실행*되어야 검색 결과에 등장합니다.
  → 먼저 이 PR을 만들거나 main에 한 번 push하여 CI를 가동한 후 등록하세요.

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
