import { describe, it, expect } from "vitest";
import {
  graph2dSpecToState,
  surface3dSpecToState,
  simulationSpecToState,
  parseSpecParam,
  unwrapSpecEnvelope,
  specToStateForType,
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

  it("y_range가 well-formed면 view의 y 범위로 반영", () => {
    const st = graph2dSpecToState({ function: "x", domain: [-3, 3], y_range: [-5, 5] });
    expect(st.view).toEqual({ xMin: -3, xMax: 3, yMin: -5, yMax: 5 });
  });

  it("잘못된/누락 y_range는 기본 ±10 폴백", () => {
    expect(graph2dSpecToState({ function: "x", domain: [-3, 3], y_range: [5, 5] }).view).toEqual({
      xMin: -3,
      xMax: 3,
      yMin: -10,
      yMax: 10,
    });
    expect(graph2dSpecToState({ function: "x", domain: [-3, 3], y_range: [1] }).view).toEqual({
      xMin: -3,
      xMax: 3,
      yMin: -10,
      yMax: 10,
    });
  });

  it("y_range만 있고 domain 없으면 view 없음(x 범위 날조 안 함)", () => {
    expect(graph2dSpecToState({ function: "x", y_range: [-5, 5] }).view).toBeUndefined();
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

  it("기본 y(±10)는 y_range를 명세에 안 실음(클린 라운드트립)", () => {
    const spec = calcStateToGraph2dSpec({
      rows: [{ expr: "x" }],
      view: { xMin: -3, xMax: 3, yMin: -10, yMax: 10 },
    });
    expect(spec.domain).toEqual([-3, 3]);
    expect(spec.y_range).toBeUndefined();
  });

  it("커스텀 y 범위는 y_range로 실음", () => {
    const spec = calcStateToGraph2dSpec({
      rows: [{ expr: "x" }],
      view: { xMin: -3, xMax: 3, yMin: -5, yMax: 5 },
    });
    expect(spec.domain).toEqual([-3, 3]);
    expect(spec.y_range).toEqual([-5, 5]);
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

  it("커스텀 y_range도 왕복 후 보존된다", () => {
    const spec = {
      function: "a*sin(x)",
      domain: [-6, 6],
      y_range: [-2, 2],
      parameters: [{ name: "a", min: 1, max: 3, step: 0.1, default: 2 }],
    };
    const st = graph2dSpecToState(spec);
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

describe("surface3dSpecToState — 코어 Surface3dSpec → 계산기 3D 상태", () => {
  it("'z = x**2 + y**2' → mode3D + expr3D(좌변 제거·**→^)", () => {
    const st = surface3dSpecToState({ surface: "z = x**2 + y**2" });
    expect(st).toEqual({ mode3D: true, expr3D: "x^2 + y^2" });
  });

  it("좌변 없는 곡면식도 그대로 변환('x**2*y' → 'x^2*y')", () => {
    expect(surface3dSpecToState({ surface: "x**2*y" })).toEqual({
      mode3D: true,
      expr3D: "x^2*y",
    });
  });

  it("range(숫자)가 있으면 range3D로 매핑", () => {
    const st = surface3dSpecToState({ surface: "z = sin(x)*cos(y)", range: 5 });
    expect(st.range3D).toBe(5);
    expect(st.expr3D).toBe("sin(x)*cos(y)");
  });

  it("surface가 없거나 빈 문자열이면 null", () => {
    expect(surface3dSpecToState({ rotatable: true })).toBeNull();
    expect(surface3dSpecToState({ surface: "   " })).toBeNull();
    expect(surface3dSpecToState(null)).toBeNull();
  });

  it("base64 URL(3D) → parseSpecParam → 3D 상태", () => {
    const spec = { surface: "z = x**2 - y**2" };
    const b64 = Buffer.from(JSON.stringify(spec)).toString("base64");
    expect(surface3dSpecToState(parseSpecParam(b64))).toEqual({
      mode3D: true,
      expr3D: "x^2 - y^2",
    });
  });
});

describe("simulationSpecToState — 코어 SimulationSpec → 계산기 시뮬 상태", () => {
  it("experiment+trials → simulationMode 상태", () => {
    expect(simulationSpecToState({ experiment: "동전 던지기", trials: 100 })).toEqual({
      simulationMode: true,
      experiment: "동전 던지기",
      trials: 100,
    });
  });

  it("trials 없으면 키 생략(기본값은 컴포넌트 몫)", () => {
    expect(simulationSpecToState({ experiment: "주사위 던지기" })).toEqual({
      simulationMode: true,
      experiment: "주사위 던지기",
    });
  });

  it("experiment 없거나 빈 문자열이면 null", () => {
    expect(simulationSpecToState({ trials: 100 })).toBeNull();
    expect(simulationSpecToState({ experiment: "   " })).toBeNull();
    expect(simulationSpecToState(null)).toBeNull();
  });

  it("base64 URL(시뮬) → parseSpecParam → 시뮬 상태", () => {
    const spec = { experiment: "동전 던지기", trials: 500 };
    const b64 = Buffer.from(JSON.stringify(spec)).toString("base64");
    expect(simulationSpecToState(parseSpecParam(b64))).toEqual({
      simulationMode: true,
      experiment: "동전 던지기",
      trials: 500,
    });
  });
});

describe("simulationSpecToState — outcomes 통과 (구조화 우선)", () => {
  it("outcomes 있으면 상태에 통과", () => {
    const spec = {
      experiment: "가위바위보",
      trials: 300,
      outcomes: [
        { label: "가위", weight: 1 },
        { label: "바위", weight: 1 },
        { label: "보", weight: 1 },
      ],
    };
    expect(simulationSpecToState(spec)).toEqual({
      simulationMode: true,
      experiment: "가위바위보",
      trials: 300,
      outcomes: spec.outcomes,
    });
  });

  it("outcomes 없거나 빈/비배열이면 키 생략(하위호환)", () => {
    expect(simulationSpecToState({ experiment: "동전 던지기" }).outcomes).toBeUndefined();
    expect(simulationSpecToState({ experiment: "x", outcomes: [] }).outcomes).toBeUndefined();
    expect(simulationSpecToState({ experiment: "x", outcomes: "no" }).outcomes).toBeUndefined();
  });

  it("base64 URL(outcomes) → parseSpecParam → 상태(한국어 보존)", () => {
    const spec = {
      experiment: "동전",
      outcomes: [
        { label: "앞면", weight: 1 },
        { label: "뒷면", weight: 1 },
      ],
    };
    const b64 = Buffer.from(JSON.stringify(spec)).toString("base64");
    expect(simulationSpecToState(parseSpecParam(b64)).outcomes).toEqual(spec.outcomes);
  });
});

describe("unwrapSpecEnvelope — {type, spec} 봉투 판별(invariant ⑩)", () => {
  it("봉투는 {type, spec}로 언랩", () => {
    const r = unwrapSpecEnvelope({ type: "interactive_graph_2d", spec: { function: "x" } });
    expect(r.type).toBe("interactive_graph_2d");
    expect(r.spec).toEqual({ function: "x" });
  });
  it("레거시 spec-only(function)는 type=null·spec=원본", () => {
    const bare = { function: "x^2" };
    const r = unwrapSpecEnvelope(bare);
    expect(r.type).toBeNull();
    expect(r.spec).toBe(bare);
  });
  it("spec-only에 우연히 type 필드가 있어도 spec(객체) 없으면 봉투 아님", () => {
    // bare spec은 최상위 `spec` 키를 갖지 않음 — 봉투 오판 방지.
    const r = unwrapSpecEnvelope({ type: "x", function: "x" });
    expect(r.type).toBeNull();
  });
});

describe("specToStateForType — type-first dispatch(레거시 shape 폴백)", () => {
  it("type=graph_2d → 2D 어댑터(rows)", () => {
    const st = specToStateForType("interactive_graph_2d", { function: "x" });
    expect(Array.isArray(st.rows)).toBe(true);
  });
  it("type=surface_3d → 3D 어댑터", () => {
    const st = specToStateForType("interactive_surface_3d", { surface: "x+y" });
    expect(st.mode3D).toBe(true);
  });
  it("type=simulation → sim 어댑터", () => {
    const st = specToStateForType("simulation_probabilistic", { experiment: "동전" });
    expect(st.simulationMode).toBe(true);
  });
  it("type=animation → null(웹 렌더 경로 없음)", () => {
    expect(specToStateForType("animation_prerendered", { asset_id: "a" })).toBeNull();
  });
  it("drift 수정 ②: graph_2d spec에 experiment 키 혼입돼도 type 우선 → 2D(sim 오라우팅 방지)", () => {
    const st = specToStateForType("interactive_graph_2d", { function: "x", experiment: "동전" });
    expect(Array.isArray(st.rows)).toBe(true);
    expect(st.simulationMode).toBeUndefined();
  });
  it("레거시 type=null: experiment 있으면 shape 폴백으로 sim", () => {
    const st = specToStateForType(null, { experiment: "동전" });
    expect(st.simulationMode).toBe(true);
  });
  it("레거시 type=null: surface 있으면 shape 폴백으로 3D", () => {
    const st = specToStateForType(null, { surface: "x+y" });
    expect(st.mode3D).toBe(true);
  });
  it("레거시 type=null: 그 외는 2D 폴백", () => {
    const st = specToStateForType(null, { function: "x" });
    expect(Array.isArray(st.rows)).toBe(true);
  });
});
