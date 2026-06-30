// SymPy ↔ mathjs 수식 표기 계약 Golden Test (web·mathjs 측).
//
// 공유 fixture(`data/notation_contract.json`)를 읽어, backend SymPy 측(test_notation_contract.py)이
// 검증하는 것과 *같은 canonical 입력*(명시 `*`·caret `^`)을 mathjs가 *같은 수치*로 해석하는지
// 확인한다. 두 파서가 같은 입력을 같은 값으로 읽음을 교차 보증해 표기 drift를 막는다
// (math_dsl_remediation_design.md·docs/architecture/notation_contract.md).
//
// 권위 경계: mathjs는 *렌더·수치 평가 전용*이며 동치·정오 판정에 관여하지 않는다(권위=backend SymPy).
// 따라서 여기서는 numeric_cases(수치 해석)만 검증하고, equivalence_cases(동치 판정)는 backend 소관이다.

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import * as math from "mathjs";
import { describe, expect, it } from "vitest";

import { graph2dSpecToState } from "../src/lib/graph2dSpec";

const here = dirname(fileURLToPath(import.meta.url));
// test/ → graphing-calculator → web → src → 레포 루트(4단계 상위)/data.
const contract = JSON.parse(
  readFileSync(resolve(here, "../../../../data/notation_contract.json"), "utf-8"),
);

describe("notation contract — mathjs가 canonical 표기를 기대 수치로 해석(SymPy와 동일 입력·값)", () => {
  it.each(contract.numeric_cases)("$id: $expr", ({ expr, vars, value, tol }) => {
    const result = math.evaluate(expr, vars);
    expect(result).toBeCloseTo(value, Math.round(-Math.log10(tol ?? 1e-9)));
  });

  it("렌더 어댑터 경계: 파이썬식 ** → mathjs ^ 변환(graph2dSpecToState)", () => {
    // backend는 `**`/`^` 둘 다(convert_xor) 읽지만 mathjs는 `^`만 안다 — 어댑터가 변환을 책임진다.
    const state = graph2dSpecToState({ function: "x**2" });
    expect(state.rows[0].expr).toBe("x^2");
  });
});
