---
description: 변경사항을 안전하게 배포 (개발→스테이징→프로덕션)
argument-hint: "[환경] 예: staging, production"
---

# /deploy — 배포

## 임무
변경사항을 *안전하고 추적 가능하게* 배포한다. 학습자(미성년자) 영향을 고려한 단계적 롤아웃.

## 환경 단계

```
[로컬 Phaiakes9]  →  [스테이징]  →  [프로덕션 카나리 5%]  →  [프로덕션 100%]
     ↑                  ↑                ↑                       ↑
   /implement       /deploy staging   /deploy canary         /deploy production
```

## 실행 절차

### Pre-deploy 체크리스트
```
[ ] /review 통과
[ ] 모든 테스트 통과 (CI 그린)
[ ] 마이그레이션 스크립트 작성 (DB 변경 시)
[ ] 롤백 계획 문서화
[ ] MEMORY.md에 배포 결정 기록
[ ] LLM 프롬프트 변경 시 → A/B 비율 명시
[ ] 학생 데이터 마이그레이션 시 → 백업 확인
[ ] 보안 점검 (시크릿 노출 없음)
```

### 환경별 절차

#### Staging
```bash
# 1. 브랜치 확인
git status
git log --oneline -5

# 2. 빌드
docker compose -f docker/staging.yml build

# 3. 배포
docker compose -f docker/staging.yml up -d

# 4. 헬스 체크
curl https://staging.example.com/health

# 5. 스모크 테스트
pytest tests/smoke/ --env=staging
```

#### Production Canary (5%)
```bash
# 1. 카나리 배포
kubectl apply -f k8s/canary.yml
kubectl set image deployment/api api=registry/api:v1.2.3

# 2. 트래픽 5%로 제한
kubectl annotate ingress api nginx.ingress.kubernetes.io/canary-weight=5

# 3. 30분 모니터링
# - 에러율 < 0.1%
# - 응답 지연 p95 < 3s
# - LLM 비용 정상
# - 사용자 이탈 없음

# 4. 통과 시 점진 확장 (5% → 25% → 50% → 100%)
```

#### Production Full
```bash
# 1. 모든 카나리 단계 통과 확인
# 2. 100% 트래픽 전환
# 3. 24시간 집중 모니터링
# 4. MEMORY.md에 배포 완료 기록
```

### 학습자(미성년자) 영향 평가

배포 전 반드시 답해야 할 질문:

```
[ ] 이 변경이 학생 학습 경험을 직접 바꾸는가?
[ ] LLM 응답 패턴이 변경되는가?
[ ] 데이터 수집·처리 방식이 변경되는가?
[ ] UX의 정서적 영향이 변경되는가?
[ ] 알림·푸시 빈도가 변경되는가?
[ ] 결제·과금이 변경되는가?
```

위 중 *하나라도 Yes*면:
- 부모 공지 검토 (해당 시)
- 14세 미만 동의 절차 재확인
- 점진 롤아웃 *필수* (즉시 100% 금지)

### LLM 프롬프트 배포 (특수 케이스)

프롬프트 변경은 *코드보다 위험할 수 있음*. 학생 경험을 직접 변경.

```
1. Langfuse에 신규 버전 등록 (기존 보존)
2. A/B 설정 (예: v1 90%, v2 10%)
3. 1주일 KPI 모니터링:
   - 답 미루기 단계 깊이
   - 학생 *스스로 도착* 비율
   - 부정적 응답 (좌절·이탈) 비율
   - 부적절한 답변 신고
4. 통계 유의 확인 후 점진 확대
```

### Rollback 계획

모든 배포는 *5분 안에 롤백 가능*해야 함.

```bash
# 코드 롤백
kubectl rollout undo deployment/api

# 프롬프트 롤백
# Langfuse에서 이전 버전을 active로 전환

# DB 마이그레이션 롤백
alembic downgrade -1

# 사용자 공지 (필요 시)
```

### 배포 후 보고

```
✅ 배포 완료

환경: [staging/canary/production]
버전: v1.2.3
변경 요약:
- [기능 1]
- [기능 2]

KPI 추적 (배포 후 24h):
- 에러율: 0.05% (목표: <0.1%) ✅
- 응답 지연 p50: 1.2s (목표: <2s) ✅
- 학생 답미루기 도달 깊이: 2.6 (목표: 2.5+) ✅

MEMORY.md 업데이트: ✅
```

## 원칙

### 카나리는 항상
- 5% → 25% → 50% → 100%
- 단계별 30분 이상 관찰
- 한 단계라도 이상 시 즉시 롤백

### 학생 영향 우선
- 비즈니스 메트릭보다 학생 경험 메트릭 우선
- 이탈·좌절 신호는 *비즈니스 중단 사유*

### 추적 가능성
- 모든 배포는 git tag
- 모든 프롬프트 변경은 Langfuse 버전
- 모든 결정은 MEMORY.md

### 즉시 롤백 가능
- 5분 안에 이전 상태로 복귀 가능
- 롤백 절차는 *사전 연습*

## 호출 예시

```
> /deploy staging
> /deploy canary
> /deploy production
```

## 금지

❌ 테스트 없이 production 직행  
❌ 카나리 단계 생략  
❌ 학생 데이터 *마이그레이션 없이* 스키마 변경  
❌ 롤백 계획 없는 배포  
❌ MEMORY.md 기록 없는 배포
