# 데이터 파이프라인 표준

## 6단계 표준 흐름

```
수집 → 정제 → 정형화 → 검증 → 저장 → 인덱싱
collect  clean  transform validate load    index
```

## 도구 표준

| 단계 | 도구 |
|---|---|
| 수집 (웹) | httpx + playwright (JS 필요 시) |
| 수집 (PDF) | pdfplumber + PaddleOCR+Qwen3-VL (수식 — 2026-05-28 Mathpix 대체·2026-08-10 통합점검 정정) |
| 수집 (이미지) | PaddleOCR + Qwen3-VL 하이브리드 (로컬 — Mathpix 대체) |
| 정제 | pandas / polars |
| 검증 | Pydantic + great_expectations |
| ETL | Prefect 또는 Airflow |
| 임베딩 | bge-m3(`BAAI/bge-m3`·기본 로컬) — 클라우드 옵션 te-3-large. `embedding_provider` 셀렉터, 정본 = CLAUDE.md 스택 표 (구 표기 KoSimCSE는 코드 미사용 — 2026-08-10 통합점검 정정) |
| 저장 (RDB) | PostgreSQL 16 + TimescaleDB |
| 저장 (벡터) | pgvector (PostgreSQL 16 확장·슬98) |
| 캐시 | Redis 7 |

## 데이터 카드 (의무)

모든 데이터셋은 `docs/data/[name].md`:

```markdown
# 데이터셋: [name]
- 소스·라이선스·날짜·크기
- 스키마
- 제약·전제
- 라이선스 요구사항
- 가공 단계
- 검증 결과
```

## 정중한 크롤링

```python
# 속도 제한
RATE_LIMIT_SECONDS = 1.0  # 1초/요청

# User-Agent 명시
HEADERS = {"User-Agent": "KoreanMathApp/0.1 (research; contact@example.com)"}

# robots.txt 준수
# 재시도 정책 (exponential backoff)
```

## 검증 (Great Expectations)

```python
suite = ge.dataset.PandasDataset(df)
suite.expect_column_values_to_not_be_null("code")
suite.expect_column_values_to_match_regex("code", r"^\[(\d+)수(\d{2})-(\d{2})\]$")
suite.validate()
```

## 익명화

```python
# 사용자 데이터는 *익명 ID*로
def anonymize(student_id: str) -> str:
    return hashlib.sha256(f"{student_id}:{SALT}".encode()).hexdigest()[:16]
```

## 출처 표시 자동화

```python
# 모든 콘텐츠에 메타데이터로 출처 첨부
class ContentMetadata:
    sources: list[Source]
    licenses: list[License]
    created_at: datetime

# 사용자 미노출이라도 *내부 로그* 유지
```
