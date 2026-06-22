import { describe, it, expect } from "vitest";
import * as math from "mathjs";
import {
  latexToMath,
  classify,
  extractVars,
  asciiToLatex,
  linearRegression,
  sameGraph,
  numDeriv,
  num2Deriv,
} from "../src/lib/mathExpr";

describe("latexToMath — LaTeX를 mathjs 식으로", () => {
  it("분수·루트·지수 변환", () => {
    expect(latexToMath("\\frac{1}{2}")).toBe("((1)/(2))");
    expect(latexToMath("\\sqrt{x}")).toBe("sqrt(x)");
    expect(latexToMath("x^{2}")).toBe("x^(2)");
  });
  it("암시적 곱셈을 명시적으로", () => {
    expect(latexToMath("2x")).toBe("2*x"); // 숫자-문자
    expect(latexToMath("a x")).toBe("a*x"); // 공백(MathLive 출력)
  });
  it("기호·부등호·곱셈기호", () => {
    expect(latexToMath("\\pi").trim()).toBe("pi");
    expect(latexToMath("x\\le 5")).toBe("x<=5");
    expect(latexToMath("2\\cdot 3")).toBe("2*3");
  });
});

describe("classify — 입력 식 타입 판별", () => {
  it("빈 식 → empty", () => expect(classify("").type).toBe("empty"));
  it("점 (1,3)", () => {
    const r = classify("(1,3)");
    expect(r.type).toBe("point");
    expect(r.points).toEqual([[1, 3]]);
  });
  it("다중 점", () => expect(classify("(1,3)(2,5)").points).toHaveLength(2));
  it("극좌표 r=...", () => expect(classify("r=2sin(theta)").type).toBe("polar"));
  it("매개변수 (x(t),y(t))", () => {
    const r = classify("(cos(t),sin(t))");
    expect(r.type).toBe("parametric");
    expect(r.xBody).toBe("cos(t)");
  });
  it("음함수 x^2+y^2=9", () => expect(classify("x^2+y^2=9").type).toBe("implicit"));
  it("함수 y=x^2 → body 추출", () => {
    const r = classify("y=x^2");
    expect(r.type).toBe("function");
    expect(r.body).toBe("x^2");
  });
  it("일반 함수 x^2", () => expect(classify("x^2").type).toBe("function"));
  it("부등식 y>x^2 → op", () => {
    const r = classify("y>x^2");
    expect(r.type).toBe("inequality");
    expect(r.op).toBe(">");
  });
});

describe("extractVars — 미지수(슬라이더) 자동 감지", () => {
  it("x·내장함수·상수 제외하고 미지수만", () => {
    expect(extractVars("a*x^2+b").sort()).toEqual(["a", "b"]);
    expect(extractVars("sin(x)+pi")).toEqual([]);
  });
  it("파싱 실패 → 빈 배열", () => expect(extractVars("x^")).toEqual([]));
});

describe("asciiToLatex — 텍스트 입력 모드 변환", () => {
  it("일반식은 TeX로", () => expect(asciiToLatex("x^2")).toContain("^"));
  it("등식·점은 원본 패스스루", () => {
    expect(asciiToLatex("x=1")).toBe("x=1");
    expect(asciiToLatex("(1,3)")).toBe("(1,3)");
  });
  it("빈 입력 → 빈 문자열", () => expect(asciiToLatex("")).toBe(""));
});

describe("linearRegression — 최소제곱 회귀", () => {
  it("완전 선형 데이터 → m,b,r2", () => {
    const r = linearRegression([[0, 0], [1, 2], [2, 4]]);
    expect(r.m).toBeCloseTo(2);
    expect(r.b).toBeCloseTo(0);
    expect(r.r2).toBeCloseTo(1);
  });
  it("점 2개 미만 → null", () => expect(linearRegression([[1, 1]])).toBeNull());
  it("모든 x가 같으면 → null", () => expect(linearRegression([[1, 1], [1, 2]])).toBeNull());
  it("빈 입력 → null", () => expect(linearRegression()).toBeNull());
});

describe("sameGraph — 두 식의 그래프 동치 채점", () => {
  it("같은 식 → true", () => expect(sameGraph("x^2", "x^2")).toBe(true));
  it("다른 식 → false", () => expect(sameGraph("x^2", "x^2+1")).toBe(false));
  it("동치 표현(전개) → true", () => expect(sameGraph("(x+1)^2", "x^2+2*x+1")).toBe(true));
  it("파싱 불가 → false", () => expect(sameGraph("x^", "x")).toBe(false));
});

describe("numDeriv / num2Deriv — 수치 미분", () => {
  it("x^2의 1계·2계도함수", () => {
    const node = math.compile("x^2");
    expect(numDeriv(node, 2)).toBeCloseTo(4, 3);
    expect(num2Deriv(node, 1)).toBeCloseTo(2, 2);
  });
  it("스코프 변수(슬라이더) 지원", () => {
    const node = math.compile("a*x");
    expect(numDeriv(node, 1, { a: 3 })).toBeCloseTo(3, 4);
  });
  it("평가 불가(미정의 심볼) → NaN", () => {
    const node = math.compile("y"); // scope에 y가 없으면 evaluate가 throw → NaN
    expect(Number.isNaN(numDeriv(node, 0))).toBe(true);
  });
});
