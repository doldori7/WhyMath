# 그래프 계산기 (Graphing Calculator) — WhyMath

> Desmos 스타일 인터랙티브 그래프 계산기. **격리된 독립 웹 앱**(Vite + React 19 정적 SPA).

"답이 아닌, 이유를 묻는 수학"을 위해 학생이 **직접 조작하며 직관을 얻는** 도구다. 함수
그래프부터 슬라이더, 미분·적분 시각화, 3D 곡면, 문제 출제·교육과정 진단까지 Phase 1~15를 담았다.

---

## 아키텍처 위치 (7계층)

이 앱은 CLAUDE.md 7계층의 **L5 상호작용 — "국소 비상구"**다(슬라이스 89, `docs/architecture/05_interaction.md`).

- WhyMath의 원칙은 **"표현 ≠ 의미"**: 수식·그래프는 코어(L1–L4)에 구조(JSON/AST)로 저장하고
  렌더는 클라이언트가 한다. 학생 그래프 계산기는 **MathLive·three.js와 함께 "2 비상구"** 중
  하나로, WebView에 임베드되는 *모듈 한정* 자족 도구다(전체 학생앱이 아님).
- 따라서 이 계산기는 **클라이언트에서 수학을 평가(mathjs)하는 국소 예외**다 — 비상구로서
  자족 SPA이기 때문이다. 코어 명세 경로(`Graph2dSpec` 등 `whymath_backend/schema/visualization.py`)와는
  별개 트랙이며, 향후 코어 명세를 소비하도록 연결하는 것은 후속 과제다.
- **정적 번들**(`vite build` → `dist/`, `base: './'`)이라 추후 **Flutter 학생앱 WebView**로
  그대로 임베드할 수 있다(`src/mobile`의 `webview_flutter`).

> 백엔드(`src/backend`)·모바일(`src/mobile`)을 **일절 수정하지 않는다** — 이 디렉토리에 격리.

---

## 실행

```bash
cd src/web/graphing-calculator
npm install

npm run dev        # 로컬 개발 서버 (브라우저에서 확인)
npm test           # Vitest — 수학 코어 + storage shim + 스모크 렌더
npm run coverage   # 커버리지 (src/lib/** 70%+ 게이트)
npm run build      # 정적 번들 → dist/  (WebView 임베드 산출물)
npm run preview    # 빌드 결과 미리보기
```

---

## 구조

```
src/
├── main.jsx              # 엔트리. installStorageShim() → <GraphingCalculator/> 렌더
├── GraphingCalculator.jsx# 메인 컴포넌트 (MathField·Surface3D·QuizMode 포함, Phase 1~15)
└── lib/
    ├── mathExpr.js       # 순수 수학 헬퍼 (테스트 대상): latexToMath·classify·extractVars·
    │                     #   asciiToLatex·linearRegression·sameGraph·numDeriv·num2Deriv
    └── storageShim.js    # window.storage(claude.ai 전용)를 localStorage로 재현
test/
├── setup.js              # canvas getContext·matchMedia stub + shim 주입
├── mathExpr.test.js      # 수학 코어 단위 테스트
├── storageShim.test.js   # 저장소 라운드트립·prefix 필터
└── GraphingCalculator.smoke.test.jsx  # jsdom 마운트 회귀 방지
```

`GraphingCalculator.jsx`는 claude.ai 아티팩트 원본을 충실히 이식하되, ① 순수 헬퍼를
`lib/mathExpr.js`로 추출해 import하고(테스트 가능성), ② 저장소는 shim으로 대체했다.

---

## window.storage shim

원본은 claude.ai 아티팩트 전용 *비동기* 저장 API를 쓴다. 실제 브라우저/WebView엔 없으므로
`lib/storageShim.js`가 localStorage로 동일 계약을 재현한다(컴포넌트 본문 무수정).

| 메서드 | 반환 | 비고 |
|---|---|---|
| `get(key)` | `Promise<{ value: string \| null }>` | 미존재 시 `value: null` |
| `set(key, value)` | `Promise<void>` | localStorage 저장 |
| `delete(key)` | `Promise<void>` | 예약어라 내부 함수명은 `del` |
| `list(prefix)` | `Promise<{ keys: string[] }>` | prefix로 시작하는 키 목록 |

저장 데이터: 이름 붙인 그래프(`graph:*`), 퀴즈 학습 기록(`quiz_history`). 브라우저 새로고침 후에도 유지된다.

---

## MathLive / three.js (npm 번들 · 오프라인 자족)

수식 편집기(MathLive)와 3D 곡면(three.js)은 **npm 의존성으로 번들**한다(CDN 의존 제거 →
오프라인 WebView 자족). 둘 다 **동적 import로 코드 분할**돼 초기 번들에 포함되지 않고,
입력칸이 처음 필요할 때(MathLive)·3D 모드 진입 시(three.js)에만 별도 청크로 로드된다.

- **MathLive 폰트**: KaTeX woff2 20종을 `public/mathlive/fonts/`에 두어 빌드 시 `dist/mathlive/fonts/`로
  복사한다(`MathfieldElement.fontsDirectory = "./mathlive/fonts"`, 효과음은 비활성). CDN 폰트 의존 없음.
- **로드 실패 폴백 유지**: MathLive 실패 → 일반 텍스트 입력칸(붙여넣기 지원), three.js 실패 → 3D 뷰 안내 메시지.
- **2D 그래프 코어는 mathjs(번들)만** 쓰므로 MathLive/three.js 없이도 완전 동작한다.

> 빌드 산출물(`dist/`)에 외부 CDN 스크립트 URL이 남지 않는다(완전 자족). Flutter WebView가 `file://`로
> 로드해도 `base: './'` 상대경로 + 동적 청크 + 번들 폰트로 그대로 동작한다.

---

## 기능 (Phase 1~15)

함수 그래프·다중 함수·확대/이동 · 좌표 추적·근·절편 · 슬라이더 자동 감지·애니메이션 ·
MathLive 수식 편집 · 점/음함수/부등식/극좌표/매개변수 · 데이터 표 + 선형 회귀(R²) ·
저장/불러오기(JSON·이름) · 접선·도함수 · 적분(리만 합) · 3D 곡면 · 그래프 맞히기 퀴즈 ·
단계별 진단 · 학습 분석 · 2022 개정 교육과정 성취기준 연계.
