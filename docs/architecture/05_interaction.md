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

## 자동 커리큘럼 정렬 — UI 레이어

> MathScope PRD v1.1을 정본으로 흡수하며 들여온 정렬. 채택 근거는 `MEMORY.md` 2026-05-14 결정 로그 참조.

PRD의 핵심 자산인 **자동 커리큘럼 정렬 엔진** — 학생의 국가·학년·학교·교과서·진도에 맞춰 콘텐츠를 자동 정렬하는 엔진 — 은 **엔진 자체가 L1(데이터 기반)+L6(응용 모드) 책임**이다. L5는 그 엔진의 *입력을 받는 화면*과 *출력을 보여주는 화면*만 담당한다.

### L5가 담당하는 것 — 엔진의 입출력 UI

**입력 UI — 온보딩 흐름 (3분 무마찰)**

학생이 처음 앱에 들어오면 다음을 순서대로 묻는다. 목표는 *3분 안에, 마찰 없이* 정렬 엔진이 필요로 하는 `StudentProfile` 입력을 모으는 것:

```
국가 → 학년 → 학교 → 교과서(출판사) → 현재 진도 → 학습 목표
```

- 각 단계는 *드롭다운·검색·탭* 위주 — 자유 입력 최소화. 학교는 학교알리미 연동 검색, 교과서는 출판사 리스트.
- 첫 진입(고1 내신)에서는 한국·고1로 국가·학년이 사실상 고정 — 무마찰 원칙에 맞게 기본값을 미리 채워 단계를 건너뛴다.
- 온보딩 산출물은 L2의 `StudentProfile`로 넘어가고, 자동 커리큘럼 정렬 엔진(L1+L6)이 이를 소비한다 — L5는 *수집·전달*만 한다.

**출력 UI — 학생 교과서에 맞춘 메인 화면**

정렬 엔진의 결과로, 메인 화면은 학생 *본인의 교과서 좌표*로 콘텐츠를 표시한다:

```
미래엔 수학II · p.156~162
도함수의 정의
```

- 단원·페이지·개념명이 학생이 실제 들고 다니는 교과서와 같은 표현으로 보인다 — "어느 교과서든 추상적 단원명"이 아니라 *내 책의 그 페이지*.
- 이 표시 문자열·페이지 범위·개념명은 모두 정렬 엔진(L1+L6)이 만들어 L5에 내려준 값이다. L5는 *렌더링*만 한다.

### 경계 (7계층)

- **엔진 = L1+L6**: 다국 커리큘럼 매트릭스·교과서 매핑 파이프라인·7차원 자동 조정 로직은 L1·L6 책임 (`01_data_foundation.md`·`06_application_modes.md` 참조).
- **UI = L5**: 온보딩 화면, 메인 화면의 교과서 좌표 표시는 L5 책임.
- L5는 L1·L6을 *호출*해 입력을 전달하고 출력을 받지만, 정렬 로직을 *구현하지 않는다*.

## 시각화 스택

> MathScope PRD v1.1을 정본으로 흡수하며 확장한 계층. 채택 근거는 `MEMORY.md` 2026-05-14 결정 로그 참조.

### 기존 스택 (유지)

- **Mathpix OCR** — 손글씨·인쇄 수식 인식 표준
- **Manim** — 서버 렌더 사고 과정 애니메이션
- **Desmos · GeoGebra** — webview 임베드 그래핑·동역학

### PRD 신규 — 선언적 시각화 (`Visualization` 엔티티)

PRD는 시각화를 *영상 파일*이 아니라 **선언적 JSON 명세**로 정의한다. 이 명세 한 벌이 클라이언트에서 렌더되며, 핵심 성질은:

- **영상이 아님** — 렌더 파라미터·데이터·축·상호작용 규칙을 담은 JSON. 용량이 작고 버전 관리가 쉽다.
- **학생이 파라미터를 조작 가능** — 슬라이더·드래그로 변수를 바꾸면 즉시 다시 그려진다. 수동 시청이 아니라 *능동 탐구*.
- **다국어 자유** — 라벨·캡션이 명세 안의 텍스트 필드라서, 같은 명세에 언어 레이어만 갈아끼우면 된다.

`Visualization.type` 4종:

| 타입 | 의미 | 렌더 도구 |
|---|---|---|
| `interactive_graph_2d` | 학생이 파라미터를 조작하는 2D 함수·관계 그래프 | D3.js / Plotly / Desmos |
| `interactive_surface_3d` | 회전·단면이 가능한 3D 곡면·입체 | three.js |
| `simulation_probabilistic` | 시행을 반복·누적하는 확률 시뮬레이션 | D3.js / Plotly |
| `animation_prerendered` | 미리 렌더된 사고 과정 애니메이션 (조작 불가) | Manim |

- `animation_prerendered`만 기존 Manim 산출물에 대응하고, 나머지 3종이 PRD 신규 선언적 명세다.
- 선언적 명세는 기존 Manim·Desmos·GeoGebra와 **공존**한다 — 어느 하나가 다른 것을 대체하지 않는다. L5는 `Visualization.type`을 보고 렌더 도구를 고른다.
- **MathLive** — 수식 *입력* 키보드. 학생이 LaTeX를 직접 치지 않고도 분수·근호·적분 기호를 입력한다. (기존 `mathlive` 의존성을 시각화 스택 차원에서 명시.)
- 명세의 *생성·검증*은 L3(콘텐츠 생성·검증) 책임이고, L5는 받은 명세를 *렌더·조작 처리*만 한다 — 7계층 경계.

## 기술 스택

### Mobile
- Flutter 3.x + Riverpod 2.x
- go_router · freezed · dio · retrofit
- flutter_math_fork (LaTeX)
- webview_flutter (Desmos·GeoGebra 임베드, D3.js·three.js·Plotly 선언적 명세 렌더)
- mathlive (수식 키보드)

### 시각화 렌더 (webview 내)
- D3.js — `interactive_graph_2d` · `simulation_probabilistic`
- three.js — `interactive_surface_3d`
- Plotly — `interactive_graph_2d` · `simulation_probabilistic` (고수준 차트)
- MathLive — 수식 입력 키보드

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
