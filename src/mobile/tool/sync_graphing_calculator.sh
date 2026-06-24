#!/usr/bin/env bash
# 그래프 계산기 웹 번들 → Flutter 자산 동기화 (vendoring).
#
# 모바일 CI엔 Node가 없어(Flutter 전용) 웹을 빌드할 수 없다 → 격리 웹 계산기
# (src/web/graphing-calculator)의 빌드 산출물 dist/를 Flutter 자산으로 *복사·커밋*해
# loadFlutterAsset로 오프라인 임베드한다(슬89 "국소 비상구"). 이 스크립트가 빌드→복사를
# 1커맨드로 재현해 vendored 번들이 웹 소스와 표류하지 않게 한다.
#
# 사용: bash src/mobile/tool/sync_graphing_calculator.sh   (레포 루트에서 실행)
# 결과: src/mobile/assets/graphing_calculator/ 가 최신 dist로 갱신된다(소스맵 제외).
set -euo pipefail

# 레포 루트(이 스크립트의 ../../.. = src/mobile/tool → 루트) 기준 절대경로.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
WEB="$ROOT/src/web/graphing-calculator"
DEST="$ROOT/src/mobile/assets/graphing_calculator"

echo "▶ 웹 번들 빌드: $WEB"
cd "$WEB"
npm ci
npm run build

echo "▶ 자산 동기화 → $DEST (소스맵 *.map 제외)"
rm -rf "$DEST"
mkdir -p "$DEST"
# dist 전체를 복사하되 .map(개발 전용·~9MB)은 제외 — 런타임은 html/js/woff2만 필요.
( cd "$WEB/dist" && find . -type f ! -name '*.map' -print0 \
  | while IFS= read -r -d '' f; do
      mkdir -p "$DEST/$(dirname "$f")"
      cp "$f" "$DEST/$f"
    done )

echo "✓ 동기화 완료. 복사된 파일:"
find "$DEST" -type f | sed "s|$ROOT/||" | sort
