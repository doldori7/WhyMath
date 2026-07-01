#!/usr/bin/env bash
# WhyMath — 병렬 Claude Code 세션용 격리 worktree 생성기
#
# 목적:
#   여러 Claude Code 세션을 동시에 열어 병렬 개발할 때, 세션마다 독립된 git worktree를
#   최신 main 기준으로 만들어 서로의 워킹트리·인덱스를 간섭하지 않게 한다.
#   (규칙: 1 세션 = 1 도메인 = 1 브랜치 = 1 worktree. docs/standards/parallel_sessions.md)
#
# 사용법:
#   scripts/new-session-worktree.sh <domain> <task-slug>
#   예) scripts/new-session-worktree.sh backend prm-verify
#       → 브랜치 claude/backend-prm-verify-<난수> 를
#         worktrees/backend-prm-verify-<난수>/ 에 생성
#
#   <domain> 은 아래 화이트리스트 중 하나 (src/ 최상위 폴더 = 7계층 도메인):
#     backend | data-pipeline | ml-models | mobile | web | docs | infra
#
# 정리:
#   작업 종료 후  git worktree remove worktrees/<name>  로 제거
#   (필요 시 브랜치도  git branch -D <branch>  또는 원격 머지 후 삭제)

set -euo pipefail

# ── 인자 검증 ──────────────────────────────────────────────────────
if [ "$#" -ne 2 ]; then
    echo "❌ 사용법: $0 <domain> <task-slug>" >&2
    echo "   예)   $0 backend prm-verify" >&2
    exit 1
fi

domain="$1"
task_slug="$2"

# 도메인 화이트리스트 — 세션끼리 폴더가 겹치지 않도록 강제
valid_domains="backend data-pipeline ml-models mobile web docs infra"
if ! printf '%s\n' $valid_domains | grep -qx "$domain"; then
    echo "❌ 알 수 없는 domain: '$domain'" >&2
    echo "   허용: $valid_domains" >&2
    exit 1
fi

# task-slug 위생 검사 (브랜치명·경로 안전 문자만)
if ! printf '%s' "$task_slug" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
    echo "❌ task-slug 는 소문자·숫자·하이픈만 허용: '$task_slug'" >&2
    exit 1
fi

# ── 저장소 루트로 이동 ─────────────────────────────────────────────
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# ── 짧은 난수 접미사 (동일 task 동시 진행 시 충돌 방지) ────────────
#   git rev-parse 로 재현 불가능한 값 생성 (Math.random 없이도 OS 엔트로피 사용)
suffix="$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-6)"

name="${domain}-${task_slug}-${suffix}"
branch="claude/${name}"
worktree_dir="worktrees/${name}"

# ── 최신 main 확보 ────────────────────────────────────────────────
echo "🔄 origin/main 최신화..."
git fetch origin main

if [ -e "$worktree_dir" ]; then
    echo "❌ 이미 존재: $worktree_dir" >&2
    exit 1
fi

# ── worktree 생성 (최신 origin/main 기준 새 브랜치) ────────────────
echo "🌿 worktree 생성: $worktree_dir  (브랜치 $branch)"
git worktree add -b "$branch" "$worktree_dir" origin/main

# ── 안내 ──────────────────────────────────────────────────────────
cat <<EOF

✅ 완료!

  브랜치   : $branch
  디렉토리 : $worktree_dir
  담당 도메인: src/$domain (겹치는 세션과 이 폴더 밖은 건드리지 말 것)

다음 단계 — 이 디렉토리에서 새 Claude Code 세션을 여세요:

  cd $worktree_dir && claude

작업 종료 후 정리:

  git worktree remove $worktree_dir
  git branch -D $branch     # 원격 머지 완료 후

병렬 세션 규칙: docs/standards/parallel_sessions.md
EOF
