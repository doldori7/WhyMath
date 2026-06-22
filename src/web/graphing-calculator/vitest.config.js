import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// 테스트는 jsdom 환경에서 실행한다.
// 커버리지 대상을 src/lib/** (순수 수학 코어)로 한정한다 — 캔버스·three.js·DOM에 의존하는
// 렌더 UI(~1500줄)는 단위 테스트 분모에서 제외하고, 교수학적으로 중요한 수학 로직에서
// 70%+ 게이트를 충족한다(CLAUDE.md 커버리지 표준).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.js"],
    coverage: {
      provider: "v8",
      include: ["src/lib/**"],
      thresholds: { lines: 70, functions: 70, branches: 70, statements: 70 },
    },
  },
});
