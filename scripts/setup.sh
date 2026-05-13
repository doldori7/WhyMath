#!/usr/bin/env bash
# 한국 중·고 수학 앱 하네스 셋업

set -euo pipefail

echo "🎯 한국 중·고 수학 앱 하네스 셋업 시작"

# 1. 필수 도구 확인
echo ""
echo "[1/5] 필수 도구 확인"
for cmd in git python3 docker; do
    if command -v $cmd >/dev/null 2>&1; then
        echo "  ✅ $cmd"
    else
        echo "  ❌ $cmd 가 필요합니다"
        exit 1
    fi
done

# Flutter는 선택 (모바일 개발 시)
if command -v flutter >/dev/null 2>&1; then
    echo "  ✅ flutter"
else
    echo "  ⚠️  flutter 가 없습니다 (모바일 개발 시 필요)"
fi

# 2. uv 설치 (Python 패키지 관리)
echo ""
echo "[2/5] uv (Python 패키지 관리) 확인"
if ! command -v uv >/dev/null 2>&1; then
    echo "  uv 설치 중..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
echo "  ✅ uv"

# 3. 디렉토리 점검
echo ""
echo "[3/5] 하네스 디렉토리 확인"
required_files=(
    "CLAUDE.md"
    "MEMORY.md"
    "ROADMAP.md"
    ".claude/settings.json"
)
for f in "${required_files[@]}"; do
    if [ -f "$f" ]; then
        echo "  ✅ $f"
    else
        echo "  ❌ $f 누락"
        exit 1
    fi
done

# 4. 환경변수 템플릿
echo ""
echo "[4/5] 환경변수 템플릿 생성"
if [ ! -f ".env.example" ]; then
    cat > .env.example <<'ENVEOF'
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/koreanmath
REDIS_URL=redis://localhost:6379

# LLM APIs
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_AI_API_KEY=

# Mathpix (OCR)
MATHPIX_APP_ID=
MATHPIX_APP_KEY=

# Observability
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# Phaiakes9 (로컬 LLM)
PHAIAKES9_OLLAMA_URL=http://phaiakes9.local:11434

# Auth
JWT_SECRET=change-me-please

# Payments
TOSS_CLIENT_KEY=
TOSS_SECRET_KEY=

# Firebase (FCM)
FCM_CREDENTIALS_PATH=
ENVEOF
    echo "  ✅ .env.example 생성됨"
fi

# 5. 다음 단계 안내
echo ""
echo "[5/5] 다음 단계"
echo ""
echo "  1. Claude Code 실행:"
echo "     $ claude"
echo ""
echo "  2. 첫 명령:"
echo "     > /status"
echo "     > /plan Phase1-MVP"
echo ""
echo "  3. 도메인 파트너 후보 접촉 (1순위):"
echo "     - KAIST 영재교육원"
echo "     - 한국수학교육학회"
echo "     - 대학 수학교육과"
echo ""
echo "✅ 셋업 완료!"
