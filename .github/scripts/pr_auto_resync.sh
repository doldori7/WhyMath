#!/usr/bin/env bash
# PR 자동 재동기화 — merge queue 대체 (HARN-85)
#
# 배경: 브랜치 보호에 `Require branches to be up to date`가 켜져 있고 CI가 20~30분인데
# main은 15~30분마다 전진한다. 30분짜리 게이트는 15~30분 간격의 전진을 산술적으로 이길 수
# 없다(PR #935 재동기화 4회 · PR #952가 CI green 3회를 확보하고도 behind로 3라운드).
# GitHub merge queue가 이 문제를 풀지만 **조직 소유 저장소 전용**이라 이 저장소
# (owner.type=User)에서는 쓸 수 없다 — 근거·실패 경위는 .github/branch-protection-setup.md.
#
# 그래서 보호를 낮추는 대신(strict 해제 아님) **충족을 자동화**한다: auto-merge가 켜져 있고
# behind인 PR만 update-branch로 최신화한다. 사람이 누르던 "Update branch"를 기계가 누른다.
#
# 설계 원칙(CLAUDE.md):
#   · 실패해도 증거가 남는다 — 실패 PR 번호 + **HTTP 응답 본문**을 로그에 남긴다.
#   · 실패 원인이 남는다 — 409(충돌)/403·401(권한)/그 외를 구분해 처분이 다르다.
#   · 측정 실패가 "0건 통과"로 위장되지 않는다 — 목록 조회가 실패하면 exit 1.
#   · 모른다 ≠ 아니다 — mergeStateStatus가 UNKNOWN이면 건드리지 않고 그 사실을 출력한다.
#   · 0건도 읽히게 — 분모(스캔한 PR 수)와 분류별 개수를 항상 요약에 낸다.
#
# 환경변수: REPO(필수·owner/name) · GH_TOKEN(gh가 읽음) · DRY_RUN(1이면 쓰기 생략)

# -e는 의도적으로 쓰지 않는다 — 한 PR의 실패가 나머지 PR 처리를 막으면 안 된다.
set -uo pipefail

REPO="${REPO:?REPO 미설정 — owner/name 형식으로 넘겨야 한다}"
DRY_RUN="${DRY_RUN:-0}"

fatal=0
behind_am=0
updated=0
conflict=0
unknown=0
other_err=0

echo "── PR 자동 재동기화 (repo=$REPO · dry_run=$DRY_RUN)"

# ① 목록 조회. 실패는 "대상 0건"과 반드시 구분한다.
payload=$(gh pr list --repo "$REPO" --state open --limit 100 \
  --json number,mergeStateStatus,autoMergeRequest,headRefName 2>&1)
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "::error::PR 목록 조회 실패(exit=$rc) — 이것은 '대상 0건'이 아니라 측정 실패다."
  echo "응답: $payload"
  exit 1
fi

scanned=$(printf '%s' "$payload" | jq 'length' 2>/dev/null)
if [ -z "${scanned:-}" ]; then
  echo "::error::PR 목록 파싱 실패 — gh 출력이 JSON 배열이 아니다."
  echo "응답: $payload"
  exit 1
fi

# ② 후보 선별 + 처리
while IFS= read -r row; do
  [ -z "$row" ] && continue
  n=$(printf '%s' "$row" | jq -r '.number')
  head=$(printf '%s' "$row" | jq -r '.headRefName')
  state=$(printf '%s' "$row" | jq -r '.mergeStateStatus // "UNKNOWN"')
  automerge=$(printf '%s' "$row" | jq -r 'if .autoMergeRequest == null then "off" else "on" end')

  if [ "$state" = "UNKNOWN" ] || [ -z "$state" ] || [ "$state" = "null" ]; then
    # GitHub이 아직 머지 가능성을 계산하지 않은 상태. 모른다를 아니다로 접지 않는다.
    unknown=$((unknown + 1))
    echo "· #$n ($head): mergeStateStatus 미판정 — 이번 주기 건너뜀(모른다 ≠ 아니다)"
    continue
  fi

  # auto-merge를 켜지 않은 PR은 건드리지 않는다 — 리뷰 중인 diff를 임의로 전진시키지 않기 위함.
  [ "$automerge" != "on" ] && continue
  [ "$state" != "BEHIND" ] && continue

  behind_am=$((behind_am + 1))
  if [ "$DRY_RUN" = "1" ]; then
    echo "· #$n ($head): BEHIND + auto-merge — DRY_RUN이라 update-branch 생략"
    continue
  fi

  body=$(gh api --method PUT "repos/$REPO/pulls/$n/update-branch" 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    updated=$((updated + 1))
    echo "✔ #$n ($head): 최신화 완료"
    continue
  fi

  code=$(printf '%s' "$body" | grep -oE 'HTTP [0-9]{3}' | head -1 | awk '{print $2}')
  case "${code:-}" in
    409)
      # 내용 충돌 — 자동 해소 대상이 아니다. 건너뛰되 조용히 넘기지 않는다.
      conflict=$((conflict + 1))
      echo "::warning::#$n ($head) 재동기화 충돌(HTTP 409) — 사람이 해소해야 한다. 응답: $body"
      ;;
    401 | 403)
      # 토큰 권한 부족. 이것을 경고로 넘기면 자동화가 상시 무력인 채 초록으로 보인다.
      fatal=1
      echo "::error::#$n ($head) 권한 거부(HTTP $code) — 자동 재동기화가 무력 상태다. 응답: $body"
      ;;
    *)
      other_err=$((other_err + 1))
      echo "::warning::#$n ($head) 재동기화 실패(HTTP ${code:-미상}·exit=$rc). 응답: $body"
      ;;
  esac
done <<<"$(printf '%s' "$payload" | jq -c '.[]')"

# ③ 요약 — 분모를 항상 낸다. "0건"이 침묵이 아니라 값으로 보여야 한다.
echo "── 요약: 스캔 ${scanned}건 · BEHIND+auto-merge ${behind_am}건 · 최신화 ${updated}건 ·"
echo "        충돌 ${conflict}건 · 미판정 ${unknown}건 · 기타실패 ${other_err}건"

exit "$fatal"
