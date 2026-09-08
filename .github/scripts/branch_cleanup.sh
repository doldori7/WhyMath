#!/usr/bin/env bash
# 브랜치 정리 — 원격 삭제 집행 (HARN-16 경로 · HARN-01 수정)
#
# 배경: 컨테이너(Claude Code 웹) 세션은 원격 브랜치를 삭제할 수 없다 — CCR git 프록시가
# ref 삭제 연산 자체를 HTTP 403으로 차단한다. 이 스크립트를 GitHub Actions 러너가 저장소
# 토큰으로 실행해 그 경로를 연다.
#
# ── HARN-01이 고친 것: "이미 삭제된 브랜치"가 실패로 계상돼 잡이 상시 red였다 ──
#
# 요청 파일(.github/branch-cleanup-request.txt)은 **append-only 이력**이라, main에 푸시될
# 때마다 과거 배치의 브랜치가 전부 다시 대상이 된다. 그것들은 이미 삭제됐으므로 조회가
# 404를 낸다. 그 404가 "삭제 실패"로 계상돼 잡이 red로 끝났다(run #7·#8·#9 연속 실패).
#
# 원래 코드에는 부재 가드가 **있었다**:
#
#     sha=$(gh api "repos/$REPO/git/refs/heads/$b" --jq .object.sha 2>/dev/null || true)
#     if [ -z "$sha" ]; then echo "부재(이미 삭제됨?)"; continue; fi
#
# 그런데 한 번도 발화하지 못했다. `gh api`는 **오류 응답의 본문을 stdout으로** 뱉고,
# `2>/dev/null`은 stderr만 죽이며, `--jq`는 그 오류 본문에 적용되지 않는다. 그래서 `sha`에
# 빈 문자열이 아니라 `{"message":"Not Found",...,"status":"404"}`가 통째로 들어갔다
# (run #9 로그에 `삭제 전 스냅샷: {"message":"Not Found"...}` 줄이 실제로 찍혔다).
# 가드는 존재하지만 무력했다 — 소스만 읽으면 보호가 있는 것으로 보이므로 PR #1031 리뷰가
# 그렇게 읽은 것도 자연스럽다. CLAUDE.md "변별력 없는 검증 스텝 금지"가 말하는 위장 상태다.
#
# 그래서 이 스크립트는 **문자열이 아니라 명령의 종료 코드**로 부재를 판정한다.
#
# 왜 red를 없애는 것이 중요한가: 3회+ 연속 red는 신호를 습관화시킨다. 그 상태에서는 진짜
# 삭제 실패(권한·보호 브랜치·오타)가 같은 색에 묻힌다. 게다가 이력 파일이 자랄수록 404
# 재시도가 단조 증가해 red는 **영구화**된다(시간이 지날수록 나빠지는 방향).
#
# 설계 원칙(CLAUDE.md):
#   · exit code는 **실제 실패에만** 반응한다 — 이미 부재는 성공 계상이다(멱등).
#   · 0건도 값으로 읽힌다 — 대상·삭제·부재·거부·실패를 항상 요약에 낸다.
#   · 측정 실패가 성공으로 위장되지 않는다 — 스냅샷을 못 얻으면 **삭제하지 않는다**(아래 ②).
#   · 한 브랜치의 실패가 나머지를 막지 않되, 실패가 하나라도 있으면 잡은 red로 끝난다.
#
# 안전장치(협상 불가):
#   · `main` 및 허용 패턴(claude/*, tmp-*, worktree-agent-*) 밖 브랜치는 거부한다.
#   · 삭제 직전 각 브랜치의 head SHA를 로그에 남긴다 — 삭제 후에도 그 SHA로
#     `commits/<sha>`·`contents?ref=<sha>` API 접근이 가능하다(섀도 브랜치 회수로 실증).
#
# 환경변수:
#   REPO      (필수) owner/name
#   GH_TOKEN  (필수) gh가 읽는 토큰
#   BRANCHES  (선택) 쉼표 구분 목록. 비면 요청 파일에서 읽는다.
#   REQUEST_FILE (선택) 요청 파일 경로. 기본 .github/branch-cleanup-request.txt

# -e는 의도적으로 쓰지 않는다 — 한 브랜치의 실패가 나머지 처리를 막으면 안 된다.
set -uo pipefail

REPO="${REPO:?REPO 미설정 — owner/name 형식으로 넘겨야 한다}"
REQUEST_FILE="${REQUEST_FILE:-.github/branch-cleanup-request.txt}"

targets=0
deleted=0
absent=0
rejected=0
failed=0

# 목록 확보: dispatch면 입력에서, push면 요청 파일에서.
if [ -z "${BRANCHES:-}" ] && [ -f "$REQUEST_FILE" ]; then
  # 파일 형식: 브랜치 1줄 1개 · '#' 시작 줄은 주석.
  BRANCHES=$(grep -v '^#' "$REQUEST_FILE" | tr '\n' ',')
fi
if [ -z "${BRANCHES:-}" ]; then
  echo "── 브랜치 정리 (repo=$REPO): 삭제 목록이 비어 있음 — 종료(no-op)"
  exit 0
fi

echo "── 브랜치 정리 (repo=$REPO)"

IFS=',' read -ra list <<<"$BRANCHES"
for raw in "${list[@]}"; do
  b="$(echo "$raw" | xargs)" # 공백 트림
  if [ -z "$b" ]; then
    continue
  fi
  targets=$((targets + 1))

  case "$b" in
    main)
      echo "::error::거부 — 'main'은 삭제 대상이 될 수 없다"
      rejected=$((rejected + 1))
      continue
      ;;
    claude/* | tmp-* | worktree-agent-*) : ;;
    *)
      echo "::error::거부 — 허용 패턴(claude/*, tmp-*, worktree-agent-*) 밖: $b"
      rejected=$((rejected + 1))
      continue
      ;;
  esac

  # ① 부재 판정은 **종료 코드**로 한다.
  #
  # 출력 문자열로 판정하면 안 되는 이유가 이 태스크의 본체다(파일 상단 참조). 또한
  # 복수형 `git/refs/heads/<b>`는 **접두 일치**로 배열을 돌려줄 수 있어(`claude/foo`가
  # `claude/foobar`에 걸린다) "그 브랜치가 있다"는 판정이 흐려진다. 단수형
  # `git/ref/heads/<b>`는 정확히 하나이거나 404라 부재 의미가 모호하지 않다.
  if ! sha=$(gh api "repos/$REPO/git/ref/heads/$b" --jq .object.sha 2>/dev/null); then
    echo "· 이미 부재(삭제됨): $b"
    absent=$((absent + 1))
    continue
  fi

  # ② 스냅샷이 SHA 형식이 아니면 **삭제하지 않는다**(fail-closed).
  #
  # gh가 exit 0으로 비-SHA를 뱉는 상태(인증 안내 배너 등)에서 그대로 진행하면, 이 잡이
  # 내건 유일한 복구 보장 — "삭제 직전 head SHA를 로그에 남긴다" — 이 조용히 사라진 채
  # 삭제만 집행된다. 복구 경로 없는 삭제는 되돌릴 수 없으므로, 모르는 상태에서는 지운다가
  # 아니라 멈춘다. 부재(①)와 달리 이것은 성공이 아니라 **측정 실패**다.
  if ! printf '%s' "$sha" | grep -qE '^[0-9a-f]{7,40}$'; then
    echo "::error::스냅샷 조회 결과가 SHA가 아니다 — 복구 경로를 확보하지 못해 삭제를 건너뛴다: $b"
    echo "  응답: $sha"
    failed=$((failed + 1))
    continue
  fi

  echo "삭제 전 스냅샷: $sha  $b"
  if body=$(gh api -X DELETE "repos/$REPO/git/refs/heads/$b" 2>&1); then
    echo "삭제 완료: $b"
    deleted=$((deleted + 1))
  else
    # 실패 원인이 남아야 한다 — 예외 타입명만으론 서로 다른 실패가 같아 보인다.
    echo "::error::삭제 실패: $b"
    echo "  응답: $body"
    failed=$((failed + 1))
  fi
done

# 요약 — 분모를 항상 낸다. "이미 부재"가 몇 건인지 보여야 red 없이도 무슨 일이 있었는지 읽힌다.
echo "── 요약: 대상 ${targets}건 · 삭제 ${deleted}건 · 이미 부재 ${absent}건 ·"
echo "        거부 ${rejected}건 · 실패 ${failed}건"

# 이미 부재(absent)는 실패가 아니다 — 이 한 줄이 HARN-01의 본체다.
if [ "$((rejected + failed))" -gt 0 ]; then
  exit 1
fi
exit 0
