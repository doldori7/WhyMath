# L5. 상호작용 (Interaction)

> 학생과 시스템 사이의 *유일한 접점*. 모바일 앱 + 서버 백엔드.

## 책임

### 모바일 (Flutter)
- 대화 UI
- 카메라 OCR
- 수식 입력
- 시각화 표시
- 학습 곡선
- 부모/교사 모드 (Phase 3+)

### 서버 (FastAPI)
- API 게이트웨이
- 인증·인가
- L1~L4 오케스트레이션
- 결제·구독
- 푸시·알림
- 로그·모니터링

## 핵심 UX 원칙

### 1. 모바일 우선
한국 학생 99% 스마트폰 사용. 데스크톱은 *부차적*.

### 2. 정서 안전 UI
- 빨강 ❌, 노랑 ✅
- 부정 표현 ❌
- 게이미피케이션 ❌ (정답률 랭킹·스트릭 금지)
- 학습 경로 시각화 ✅

### 3. Polya 단계 명시화
학생이 *지금 어디에 있는지* UI에서 항상 보임. 메타인지 강화.

### 4. 답 미루기 시각화
"지금 1단계 힌트 받음" 명시. 학생이 *왜 답을 안 주는지* 이해하게.

### 5. 접근성
- 텍스트 대비 4.5:1+
- 최소 탭 영역 44x44 dp
- TTS 통합
- 색맹 친화

## 핵심 흐름 — 학생 메시지 1건

```
[Student types]
    ↓
[Mobile: POST /chat]
    ↓
[Backend: auth + session]
    ↓
[Backend → L2: learner state]
    ↓
[Backend → L1: context]
    ↓
[Backend → L4: pedagogy decision]
    ↓
[Backend → L3: LLM generate]
    ↓
[Backend → L4: tone filter]
    ↓
[Backend → L2: update]
    ↓
[Mobile: display + Polya update]
```

## 기술 스택

### Mobile
- Flutter 3.x + Riverpod 2.x
- go_router · freezed · dio · retrofit
- flutter_math_fork (LaTeX)
- webview_flutter (Desmos·GeoGebra 임베드)
- mathlive (수식 키보드)

### Backend
- Python 3.12 + FastAPI
- SQLAlchemy 2.0 + asyncpg + alembic
- Redis (세션·캐시)
- Celery (백그라운드)

## 보안

- HTTPS only, certificate pinning
- JWT + refresh token
- 14세 미만 부모 동의 미들웨어
- 학생 PII 분리 저장 (암호화)
- 스크린샷 차단 옵션 (보호자 모드)

## 성능 목표

| 지표 | 목표 |
|---|---|
| 앱 시작 | < 2초 |
| 첫 토큰 응답 | < 2초 |
| API p50 | < 500ms |
| API p99 | < 3초 |
| 메모리 | < 200 MB |
| APK 크기 | < 50 MB |
| 가용성 | 99%+ |

## 성공 기준

### Phase 1
- ✅ 채팅·OCR·기본 진단 작동
- ✅ p50 < 2초
- ✅ 가용성 99%
- ✅ APK < 50MB

### Phase 2
- ✅ Manim 영상 플레이어
- ✅ Desmos·GeoGebra 임베드
- ✅ 결제 (토스페이먼츠)

### Phase 3+
- ✅ 부모 보고서 모드
- ✅ 교사 대시보드 (별도 앱 검토)
