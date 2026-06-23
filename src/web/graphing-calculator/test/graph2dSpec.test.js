import { describe, it, expect } from "vitest";
import {
  graph2dSpecToState,
  parseSpecParam,
  calcStateToGraph2dSpec,
} from "../src/lib/graph2dSpec";

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

describe("calcStateToGraph2dSpec — 계산기 상태 → 코어 Graph2dSpec (내보내기)", () => {
  it("함수 행 → spec.function로 mathjs ^ → 파이썬 ** 변환", () => {
    const spec = calcStateToGraph2dSpec({ rows: [{ expr: "a*x^2+b*x+c" }] });
    expect(spec).toEqual({ function: "a*x**2+b*x+c" });
  });

  it("'y=' 접두 행은 본문만 추출", () => {
    const spec = calcStateToGraph2dSpec({ rows: [{ expr: "y=x^2" }] });
    expect(spec.function).toBe("x**2");
  });

  it("함수에 쓰인 슬라이더만 parameters로(미사용 슬라이더 제외), default=value", () => {
    const spec = calcStateToGraph2dSpec({
      rows: [{ expr: "a*x" }],
      sliders: {
        a: { value: 2, min: 0, max: 5, step: 0.5, playing: false },
        unused: { value: 9, min: -1, max: 1, step: 0.1, playing: false },
      },
    });
    expect(spec.parameters).toEqual([{ name: "a", min: 0, max: 5, step: 0.5, default: 2 }]);
  });

  it("view → domain [xMin,xMax] (y 범위는 명세에 안 실음)", () => {
    const spec = calcStateToGraph2dSpec({
      rows: [{ expr: "x" }],
      view: { xMin: -3, xMax: 3, yMin: -10, yMax: 10 },
    });
    expect(spec.domain).toEqual([-3, 3]);
  });

  it("유효하지 않은 view는 domain 생략", () => {
    const spec = calcStateToGraph2dSpec({
      rows: [{ expr: "x" }],
      view: { xMin: 3, xMax: 3 },
    });
    expect(spec.domain).toBeUndefined();
  });

  it("일반 함수 행이 없으면(점·음함수·빈 rows) null", () => {
    expect(calcStateToGraph2dSpec({ rows: [{ expr: "(1,2)" }] })).toBeNull();
    expect(calcStateToGraph2dSpec({ rows: [{ expr: "x^2+y^2=9" }] })).toBeNull();
    expect(calcStateToGraph2dSpec({ rows: [{ expr: "" }] })).toBeNull();
    expect(calcStateToGraph2dSpec({ rows: [] })).toBeNull();
    expect(calcStateToGraph2dSpec(null)).toBeNull();
  });

  it("첫 함수 행만 취하고 비함수 행은 건너뜀", () => {
    const spec = calcStateToGraph2dSpec({
      rows: [{ expr: "(1,2)" }, { expr: "2*x+1" }, { expr: "x^3" }],
    });
    expect(spec.function).toBe("2*x+1");
  });
});

describe("Graph2dSpec 라운드트립 (spec → state → spec 동치)", () => {
  it("function·parameters·domain이 왕복 후 보존된다", () => {
    const spec = {
      function: "a*sin(x)",
      domain: [-6, 6],
      parameters: [{ name: "a", min: 1, max: 3, step: 0.1, default: 2 }],
    };
    const st = graph2dSpecToState(spec);
    // graph2dSpecToState는 sliders/view를 부분 상태로 주므로 그대로 역변환에 투입.
    const back = calcStateToGraph2dSpec({
      rows: st.rows,
      sliders: st.sliders,
      view: st.view,
    });
    expect(back).toEqual(spec);
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
