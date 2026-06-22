import { describe, it, expect } from "vitest";
import { graph2dSpecToState, parseSpecParam } from "../src/lib/graph2dSpec";

describe("graph2dSpecToState — 코어 Graph2dSpec → 계산기 상태", () => {
  it("function의 파이썬식 ** → mathjs ^ 변환 + latex 생성", () => {
    const st = graph2dSpecToState({ function: "a*x**2+b*x+c" });
    expect(st.rows).toHaveLength(1);
    expect(st.rows[0].expr).toBe("a*x^2+b*x+c");
    expect(st.rows[0].latex).toContain("x");
  });

  it("parameters → sliders (이름·범위·기본값)", () => {
    const st = graph2dSpecToState({
      function: "a*x",
      parameters: [{ name: "a", min: 0, max: 5, step: 0.5, default: 2 }],
    });
    expect(st.sliders.a).toEqual({ value: 2, min: 0, max: 5, step: 0.5, playing: false });
  });

  it("parameter 누락 필드는 계산기 기본값으로 보정", () => {
    const st = graph2dSpecToState({ function: "a*x", parameters: [{ name: "a" }] });
    expect(st.sliders.a).toEqual({ value: 1, min: -10, max: 10, step: 0.1, playing: false });
  });

  it("이름 없는 parameter는 건너뜀", () => {
    const st = graph2dSpecToState({ parameters: [{ min: 0 }, { name: "k", default: 4 }] });
    expect(Object.keys(st.sliders)).toEqual(["k"]);
    expect(st.sliders.k.value).toBe(4);
  });

  it("domain [xMin,xMax] → view의 x 범위 (y는 기본 ±10)", () => {
    const st = graph2dSpecToState({ function: "x", domain: [-3, 3] });
    expect(st.view).toEqual({ xMin: -3, xMax: 3, yMin: -10, yMax: 10 });
  });

  it("잘못된 domain은 무시(view 없음)", () => {
    expect(graph2dSpecToState({ function: "x", domain: [3, 3] }).view).toBeUndefined();
    expect(graph2dSpecToState({ function: "x", domain: [1] }).view).toBeUndefined();
  });

  it("빈/잘못된 spec → null", () => {
    expect(graph2dSpecToState(null)).toBeNull();
    expect(graph2dSpecToState({})).toBeNull();
    expect(graph2dSpecToState("nope")).toBeNull();
    expect(graph2dSpecToState({ function: "   " })).toBeNull();
  });
});

describe("parseSpecParam — URL 파라미터 파싱", () => {
  const spec = { function: "x**2", domain: [-2, 2] };

  it("base64(JSON) 파싱", () => {
    const b64 = Buffer.from(JSON.stringify(spec)).toString("base64");
    expect(parseSpecParam(b64)).toEqual(spec);
  });

  it("URL 인코딩된 raw JSON 파싱", () => {
    expect(parseSpecParam(encodeURIComponent(JSON.stringify(spec)))).toEqual(spec);
  });

  it("빈/깨진 값 → null", () => {
    expect(parseSpecParam("")).toBeNull();
    expect(parseSpecParam(null)).toBeNull();
    expect(parseSpecParam("%%%not json%%%")).toBeNull();
  });
});

describe("graph2dSpecToState + parseSpecParam 결합 (URL → 상태)", () => {
  it("base64 URL → 함수·슬라이더·정의역 주입", () => {
    const spec = {
      function: "a*sin(x)",
      domain: [-6, 6],
      parameters: [{ name: "a", min: 1, max: 3, step: 0.1, default: 2 }],
    };
    const b64 = Buffer.from(JSON.stringify(spec)).toString("base64");
    const st = graph2dSpecToState(parseSpecParam(b64));
    expect(st.rows[0].expr).toBe("a*sin(x)");
    expect(st.sliders.a.value).toBe(2);
    expect(st.view.xMin).toBe(-6);
  });
});
