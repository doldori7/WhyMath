# Backend — Python FastAPI

## 셋업

```bash
cd src/backend

# uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# DB 초기화
docker compose up -d postgres redis chromadb
alembic upgrade head

# 개발 서버
uvicorn src.main:app --reload
```

## 구조

```
src/backend/src/
├── main.py                    # FastAPI 진입점
├── config.py
├── api/v1/                   # 엔드포인트
├── domain/                   # 도메인 로직
├── services/
│   ├── l1_data/             # data-engineer 결과
│   ├── l2_learner/          # ml-engineer 결과
│   ├── l3_llm/              # llm-architect 결과
│   └── l4_pedagogy/         # pedagogy-designer 결과
├── db/
├── auth/
├── payment/
└── observability/
```

## 환경변수

`.env`:
```
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
MATHPIX_APP_ID=...
MATHPIX_APP_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
PHAIAKES9_OLLAMA_URL=http://phaiakes9.local:11434
JWT_SECRET=...
```

## 명령

```bash
# 테스트
pytest

# 린터·포맷
ruff check src
black src
mypy src

# 마이그레이션
alembic revision --autogenerate -m "..."
alembic upgrade head

# 시드 데이터
python scripts/seed_data.py
```
