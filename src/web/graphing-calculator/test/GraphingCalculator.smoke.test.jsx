import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import GraphingCalculator from "../src/GraphingCalculator";

// 스모크 테스트: import 그래프(mathExpr 추출)·storage shim 주입·기본 마운트 회귀 방지.
// MathLive/three.js는 CDN 미로드 환경(jsdom)에서 폴백 분기를 타므로 크래시하지 않는다.
describe("GraphingCalculator 스모크", () => {
  it("크래시 없이 마운트되고 핵심 UI가 보인다", () => {
    render(<GraphingCalculator />);
    expect(screen.getByText("그래프 계산기")).toBeInTheDocument();
    expect(screen.getByText("+ 함수 추가")).toBeInTheDocument();
  });
});
