# L7. 커뮤니티·소셜 (Community & Social)

> 느리지만 *결정적* 자산. 데이터 누적 → 모델 개선 → 콘텐츠 풍부 의 선순환.

## 책임

학생·학부모·교사를 잇는 *사회적 학습* 인프라.

## 핵심 컴포넌트

### 1. 다중 풀이 갤러리
- 학생 본인 풀이 완료 *후* 다른 학생 익명 풀이 열람
- 다양성 우선 (같은 접근 중복 최소)
- 수준 다양성 (자기보다 우수 + 비슷)
- 랭킹·경쟁 **금지**

### 2. Live Problems (NRICH 모델)
- 풀이 미공개 문제 주 1회 신규
- 학생 풀이 익명 제출
- 마감 후 모범 풀이 큐레이션 공개
- 학생 *기여 경험* (수학 커뮤니티 의식)

### 3. 학부모 보고서
- 주 1회 푸시 (학생이 *동의 시*)
- 학생 약점·강점·메타인지 순간
- 5분 대화 주제 추천
- 비교·랭킹 ❌

### 4. 교사 대시보드 (Phase 3+, B2B)
- 학급 학습 상태
- 학생별 인사이트 (PII 최소)
- 콘텐츠 추천
- 학부모 보고서 발송

### 5. 학교·교사 콘텐츠 기여 (Phase 4+)
- NRICH 교사 기여 모델
- 검수 후 production
- 출처·인용 명시

## 안전선

### 학생 데이터 노출 안전선
- ❌ 학생 이름·학교 표시
- ❌ 다른 학생 풀이를 *본인 풀이 전에* 노출
- ❌ "최고 풀이" 랭킹
- ❌ 부모에게 *불필요한* 학생 PII
- ✅ 익명·집계만

### 표현 안전선
- ❌ 학생 비난·비교
- ❌ 과장된 칭찬
- ✅ 구체적·정직한 관찰
- ✅ 행동 제안

## 인터페이스

```python
class L7CommunityService:
    async def get_multi_solution_gallery(
        self, problem_id: str, viewer_id: str
    ) -> Gallery: ...
    
    async def submit_to_live_problem(
        self, problem_id: str,
        student_id: str, solution: str
    ) -> Submission: ...
    
    async def generate_parent_report(
        self, student_id: str, week: int
    ) -> ParentReport: ...
    
    async def teacher_dashboard(
        self, class_id: str, teacher_id: str
    ) -> Dashboard: ...
```

## Phase별 진입

### Phase 3
- 다중 풀이 갤러리
- 부모 보고서

### Phase 4
- 교사 대시보드 (B2B)
- Live Problems

### Phase 4+
- 학교 콘텐츠 기여

## 성공 기준

### Phase 3
- ✅ 갤러리 가동 (학생 80%가 풀이 후 열람)
- ✅ 부모 보고서 주간 발송 (opt-in 60%+)

### Phase 4+
- ✅ Live Problems 주 1회
- ✅ 교사 대시보드 학교 50곳
- ✅ 학교 콘텐츠 기여 월 10건
