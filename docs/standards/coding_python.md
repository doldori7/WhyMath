# Python 코딩 표준

## 환경
- Python 3.12+
- 패키지 관리: `uv` (pip 대체)
- 가상환경: `uv venv`
- 의존성: `pyproject.toml`

## 포맷·린터
- 포맷: `black`
- 린터: `ruff` (rules: E, F, I, N, B, W)
- 타입: `mypy --strict`

## 스타일

```python
# 모든 주석은 한국어
# 함수·클래스·모듈 docstring 필수
# 타입 힌트 100%

from typing import Final
from pydantic import BaseModel

# 상수는 UPPER_SNAKE_CASE + Final
MAX_RETRY: Final[int] = 3

class Student(BaseModel):
    """학생 도메인 모델 — 모든 학생 데이터의 단일 정의"""
    id: str
    grade: int

async def get_student(student_id: str) -> Student | None:
    """학생 정보 조회. 없으면 None."""
    # 구현
    pass
```

## 비동기 우선
- I/O는 항상 `async`
- 동기/비동기 혼용 금지

## 에러 처리
- 도메인 예외는 명시적 클래스 (`StudentNotFoundError` 등)
- 외부 호출 (LLM·DB·HTTP)은 재시도 데코레이터
- `try/except`는 *최소 범위*

## 테스트
- `pytest` + `pytest-asyncio`
- 커버리지 70%+
- 핵심 도메인은 80%+
- LLM 호출은 *반드시* 모킹

## 의존성 주입
- FastAPI `Depends`
- 직접 import 대신 *주입*
- 테스트 가능성 최우선
