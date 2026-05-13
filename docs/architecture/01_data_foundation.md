# L1. 데이터 기반 (Data Foundation)

> *진짜 해자*. 1~2년 누적되면 제품과 별도로 라이선싱 가능한 B2B 자산이 됨.

## 책임

이 계층은 한국 수학 교육 데이터의 *진실 원천*을 정의·수집·관리한다.

## 핵심 자산

### 1. 성취기준 (Truth Source)
- **소스**: 교육부 NCIC (https://www.ncic.go.kr)
- **라이선스**: 공공누리 1유형
- **규모**: 2022 개정 수학과 약 150~180개
- **형식**: `[학년대수영역-순번]` 예) `[9수01-01]`
- **왜 핵심**: 모든 출판사가 법적으로 이 코드를 따라야 함

### 2. 검정 교과서 목차 매핑
- **소스**: 출판사 공식 사이트·도서관 메타데이터
- **활용 범위**: 단원명·차시 목차·페이지 (사실정보)
- **금지**: 본문·예제·풀이 (저작권)
- **출판사 13종**: 천재교육·비상교육·미래엔·금성·동아·신사고·지학사·교학사 등

### 3. 학교별 채택 정보
- **소스**: 학교알리미 (https://www.schoolinfo.go.kr)
- **라이선스**: 공공
- **규모**: 전국 5,500+ 중·고
- **활용**: 학생 학교 → 사용 교과서 자동 매핑

### 4. 평가원 기출
- **소스**: 한국교육과정평가원 (수능·6월·9월 모평·EBS 수능특강)
- **활용 범위**: 본문 인용·해설 (교육적 인용)
- **규모**: 10년치 ≈ 1,000+ 문항

### 5. 글로벌 OER (Open Educational Resources)

| 자원 | 라이선스 | 활용 |
|---|---|---|
| CK-12 | CC BY-NC | 비상업 활용·해설 영감 |
| OpenStax | CC BY | 상업 활용 가능 |
| Siyavula | CC BY | 남아공 수학·과학 |
| LibreTexts | CC BY-SA | 광범위한 수학 자원 |
| NRICH | 비상업 무료 | *영감만* (상업 X) |
| Mathigon | 비상업 | 시각화 영감 |

### 6. LLM 학습 데이터셋

| 데이터셋 | 라이선스 | 규모 |
|---|---|---|
| NuminaMath-CoT | Apache 2.0 | 860k 문항 |
| MathNet (MIT 2026) | 확인 필요 | 30,000+ 47개국 17언어 |
| OmniMath | 공개 | 4,428 문항 |
| miniF2F | MIT | 488 Lean 형식화 |
| AoPS Wiki | CC BY-SA | 미국·국제경시 |

### 7. 오개념 카탈로그
- **출처**: 수학교육학 30년 연구 + 자체 누적
- **규모 목표**: Phase 1 30개 → Phase 2 100개 → Phase 3+ 300+

### 8. 사용자 자체 풀이 데이터
- **수집**: 명시적 동의 후
- **활용**: PRM 학습·오개념 발견·콘텐츠 개선
- **중요성**: *가장 큰 장기 자산* — 처음부터 수집 설계

## 데이터 모델 (SQL)

상세는 서브에이전트 `data-engineer.md` 참조.

## 파이프라인 표준

```
수집 → 정제 → 정형화 → 검증 → 저장 → 인덱싱
 ↓     ↓      ↓        ↓      ↓       ↓
httpx pandas pydantic  GE   PG+Chroma  ANN
```

## 데이터 카드 — 필수

모든 데이터셋은 `docs/data/[name].md`에 카드 작성:
- 메타데이터 (소스·라이선스·날짜·크기)
- 스키마
- 알려진 제약
- 라이선스 요구사항
- 가공 단계
- 검증 결과

## 절대 금기

- ❌ 검정 교과서 본문·예제 복제
- ❌ EBS 영상·교재 본문 수집
- ❌ 학원·인강 자료 (메가스터디·시대인재 등) 수집
- ❌ 사용자 데이터 동의 없이 활용
- ❌ 미성년자 PII 분석·마케팅 활용

## 인터페이스 (L2~L4 호출)

```python
class L1DataService:
    """L2~L4가 호출하는 표준 API"""
    
    async def get_standard_by_code(self, code: str) -> Standard: ...
    async def get_textbook_units(self, isbn: str) -> list[Unit]: ...
    async def get_school_textbook(self, school_code: str, grade: int) -> Textbook: ...
    async def get_problems_by_standard(self, code: str, limit: int) -> list[Problem]: ...
    async def get_misconceptions_for_standard(self, code: str) -> list[Misconception]: ...
    async def embedding_search(self, query: str, top_k: int) -> list[Result]: ...
```

## 성공 기준

### Phase 1
- ✅ 성취기준 100% 디지털화 (150~180개)
- ✅ 검정교과서 5종 매핑
- ✅ 평가원 기출 5년
- ✅ 오개념 30개
- ✅ 모든 데이터 카드

### Phase 2
- ✅ 검정교과서 13종
- ✅ 평가원 10년
- ✅ EBS 메타데이터
- ✅ 오개념 100개
