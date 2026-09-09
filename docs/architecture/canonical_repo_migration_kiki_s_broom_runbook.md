# 정본 저장소 전환 런북 — doldori7/WhyMath → kiki-s-broom/WhyMath

**작성일**: 2026-09-09 · **관련 태스크**: `HARN-96-canonical-repo-migration-kiki-s-broom` · **관련 게이트**: `G-canonical-repo-cutover-kiki-s-broom`(집행 대기), `G-canonical-repo-migrate-decision`(전환 결정 — cleared) · **선행 결정**: `G-merge-queue-or-strict-relax`(2026-09-07 cleared)

## 1. 무슨 일이 있었나 (쉬운 설명)

2026-09-07에 우리는 "PR 하나 머지하는 데 재동기화가 여러 번 필요한 문제"를 풀려고 GitHub의 **merge queue**(병합 대기열 — PR들을 줄 세워 자동으로 최신 상태 위에서 검증·머지해주는 기능)를 켜려고 했습니다. 그런데 이 기능은 **조직(Organization) 계정** 저장소에만 있고, `doldori7/WhyMath`는 **개인(User) 계정** 저장소라 설정 화면에 그 항목 자체가 없었습니다. 그래서 대신 "자동 재동기화 워크플로우"(`HARN-85`)라는 우회 방법을 만들어 썼습니다.

2026-09-09, Kiki가 `kiki-s-broom/WhyMath`라는 새 저장소의 main 브랜치에 merge queue 등록을 성공시켰다고 알려왔습니다. 이는 그 저장소가 조직 계정이라 원래 원했던 방법을 쓸 수 있게 됐다는 뜻으로 보입니다. 대화에서 Kiki가 **이 저장소를 앞으로의 정본(진짜 작업 대상)으로 삼기로** 결정했습니다.

## 2. 이 세션이 직접 확인한 사실 / 확인하지 못한 것

**확인함** (읽기 전용 git clone으로):
- `kiki-s-broom/whymath`는 실재하는 공개 저장소이며, `doldori7/WhyMath`와는 별개의 owner입니다(계정 이전이 아니라 별도 저장소).
- main 브랜치 최신 커밋(`94d1f28`)은 이 세션이 보는 `doldori7/WhyMath`의 최신 커밋(`3059936`) 위에 커밋 1개(#1074)를 더 얹은 상태 — 즉 같은 코드베이스입니다.
- `.github/workflows/`의 5개 워크플로(ci.yml·deploy.yml·branch-cleanup.yml·harness-audit.yml·pr-auto-resync.yml)가 그대로 복사되어 있습니다.

**확인하지 못함** (도구 제약 — 아래 4절 참고):
- `kiki-s-broom`이 정말로 Organization 계정인지를 GitHub API로 직접 확인하지 못했습니다. "merge queue 등록 성공"은 강한 정황 증거이지만, 우리 프로젝트 규칙(CLAUDE.md "가용성 확인 절차")은 설정 성공 보고만으로 환경 사실을 확정하지 말라고 합니다.
- 새 저장소에 시크릿(비밀 값)이 등록되어 있는지, 브랜치 보호 규칙이 얼마나 갖춰져 있는지, GitHub Actions가 켜져 있는지도 확인하지 못했습니다.

## 3. Kiki가 직접 할 일 — 6항목 브리핑

1. **과제 명칭**: kiki-s-broom/WhyMath 저장소를 실제로 쓸 수 있게 만들기 (계정 확인 + 시크릿 재등록 + 브랜치 보호 재설정)
2. **목적**: 지금 `kiki-s-broom/WhyMath`는 코드만 복사된 "껍데기" 상태입니다. 배포(deploy.yml)나 PR 자동 재동기화(pr-auto-resync.yml) 같은 워크플로는 **비밀 값(시크릿)이 없으면 그냥 실패**합니다. 이 작업을 해야 새 저장소가 실제로 돌아가는 정본이 됩니다.
3. **구체적 절차**:
   - ① `github.com/kiki-s-broom` 조직 설정 페이지에서 계정 유형이 Organization인지 확인 (이미 만드셨다면 아실 것이므로 참고만).
   - ② `kiki-s-broom/whymath` → Settings → Secrets and variables → Actions → New repository secret 에서 아래 6개를 등록:
     - `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_SSH_KNOWN_HOSTS`, `DEPLOY_PATH` (배포용)
     - `PR_AUTO_RESYNC_TOKEN` (PR 자동 재동기화용 — 발급 방법은 기존 게이트 `G-pr-auto-resync-token`의 evidence에 이미 기록되어 있습니다: Fine-grained PAT, Repository access = kiki-s-broom/whymath, 권한 Contents:Read and write + Pull requests:Read and write)
     - 값 자체는 `doldori7/WhyMath`에서 복사해올 수 없습니다(GitHub는 등록된 시크릿 값을 다시 보여주지 않습니다) — 새로 발급해야 합니다.
   - ③ `kiki-s-broom/whymath` → Settings → Rules → Rulesets → main 에서 `.github/branch-protection-setup.md`에 적힌 것과 같은 규칙(필수 상태 체크 목록, "Require branches to be up to date")을 다시 만들고, 이번엔 **Require merge queue** 항목이 실제로 보이는지 확인 후 켭니다.
   - ④ Actions 탭에서 아무 워크플로나(`pr-auto-resync`가 좋음) `workflow_dispatch`로 1회 수동 실행해 정상 동작하는지 확인합니다.
4. **성공 기준**: ②의 각 시크릿 등록 후 이름이 목록에 뜨는 것 / ③에서 merge queue 스위치가 켜진 상태로 저장되는 것 / ④의 수동 실행이 성공(success)으로 끝나는 것. 실패하면 그 단계에서 멈추고 오류 메시지를 그대로 알려주세요.
5. **실행 환경**: GitHub 웹사이트(브라우저)에서 직접 하는 작업입니다. PowerShell이나 터미널이 필요 없습니다.
6. **창 구분**: 해당 없음 (웹 브라우저 설정 화면 작업).

## 4. 왜 Claude 세션이 대신 못 하는가

이 세션은 시작할 때부터 `doldori7/WhyMath` 저장소에 고정되어 있습니다. 다른 소유자(owner)의 저장소를 추가로 붙이려 시도했더니 다음 오류가 났습니다:

> `cross-tier adds are not supported in v1: requested "kiki-s-broom/whymath" but session already has repos from owner(s) [doldori7]`

즉, **세션 하나는 한 저장소 소유자(owner)만 다룰 수 있습니다.** `kiki-s-broom/whymath`에 실제로 코드를 push하거나, PR을 만들거나, GitHub API로 설정을 확인하려면 **그 저장소를 시작점으로 하는 새 세션**이 필요합니다. 이번 세션은 조사와 이 문서·백로그 등록까지만 할 수 있었습니다.

## 5. 다음 단계

1. Kiki가 위 3절을 완료 (게이트 `G-canonical-repo-cutover-kiki-s-broom` clear 대상).
2. `kiki-s-broom/whymath`를 시작 저장소로 하는 새 세션에서 `HARN-96-canonical-repo-migration-kiki-s-broom`의 나머지 acceptance(계정 유형 API 확인·CI 배선 실측·병렬 세션 컷오버 절차·정본 참조 갱신)를 진행.
3. 컷오버 시점에 `doldori7/WhyMath`에서 진행 중인 다른 세션들의 작업이 두 저장소로 갈라지지 않도록 조율 (등재 시점 기준 claim 중: `EOS-63`·`HARN-56`·`HARN-82`·`HARN-86`·`HARN-87`·`MGMT-06`·`MP-02`).
