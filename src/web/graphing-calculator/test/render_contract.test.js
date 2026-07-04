// 렌더 선택 단일 진실원(invariant ⑩) Golden Test — 웹 dispatch 측.
//
// 공유 계약(`data/render_contract.json`)의 각 Visualization.type이 웹의 type-first dispatch
// (`specToStateForType`)에서 계약이 지정한 web_adapter 계열로 라우팅되는지 교차검증한다. 백엔드
// (test_render_contract.py)는 이 파일의 renderers 키가 VisualizationType enum과 일치하는지 검증 —
// 둘이 합쳐 "코어 type ↔ 웹 렌더러" drift를 막는다(notation_contract 선례).

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { specToStateForType } from "../src/lib/graph2dSpec";

const here = dirname(fileURLToPath(import.meta.url));
const contract = JSON.parse(
  readFileSync(resolve(here, "../../../../data/render_contract.json"), "utf-8"),
);

// 각 type을 그 web_adapter가 *수용하는 최소 유효 spec*으로 태워 라우팅을 실증.
// (2D=function·3D=surface·sim=experiment — 각 SpecToState의 필수 필드.)
const MIN_SPEC = {
  interactive_graph_2d: { function: "x" },
  interactive_surface_3d: { surface: "x+y" },
  simulation_probabilistic: { experiment: "동전" },
  animation_prerendered: { asset_id: "anim-1" },
};
// web_adapter가 만드는 상태의 식별 플래그(라우팅 확인용).
const ADAPTER_MARK = {
  graph2dSpecToState: (st) => Array.isArray(st.rows),
  surface3dSpecToState: (st) => st.mode3D === true,
  simulationSpecToState: (st) => st.simulationMode === true,
};

describe("render_contract — type-first dispatch가 계약 web_adapter로 라우팅", () => {
  it("계약 renderers는 정확히 4종(코어 VisualizationType 대응)", () => {
    expect(Object.keys(contract.renderers).sort()).toEqual(
      [
        "animation_prerendered",
        "interactive_graph_2d",
        "interactive_surface_3d",
        "simulation_probabilistic",
      ].sort(),
    );
  });

  for (const [type, def] of Object.entries(contract.renderers)) {
    it(`${type} → ${def.web_adapter ?? "미렌더(null)"}`, () => {
      const st = specToStateForType(type, MIN_SPEC[type]);
      if (def.web_adapter === null) {
        // animation_prerendered: 웹 렌더 경로 없음 — null(조용히 미렌더).
        expect(st).toBeNull();
        return;
      }
      expect(st).not.toBeNull();
      const mark = ADAPTER_MARK[def.web_adapter];
      expect(mark, `계약 web_adapter '${def.web_adapter}' 미지원`).toBeTypeOf("function");
      expect(mark(st)).toBe(true);
    });
  }
});
