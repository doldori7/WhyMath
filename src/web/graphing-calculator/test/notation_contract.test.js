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
import { latexToMath } from "../src/lib/mathExpr";

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

  // MATH-01 ③ — LaTeX→평문 3자 교차 골든의 웹 몫.
  //
  // 백엔드(l3 latex_to_plain)와 모바일(latexToPlainSolution)은 같은 fixture의 `plain`과 **문자열
  // 일치**를 단언한다. 웹은 그러지 않는다 — mathjs는 렌더·수치 평가 전용이고 자체 변환 규칙이
  // 의도적으로 다르기 때문이다(예: `\sqrt{x}`를 웹은 `sqrt(x)`, 백엔드는 `sqrt((x))`로 낸다.
  // 괄호 겹수는 달라도 값은 같다). 그래서 웹은 **자신의 latexToMath 산출이 계약의 value로
  // 평가되는지**를 본다. 이 단언이 py의 문자열 골든과 만나 "표기는 달라도 같은 수를 뜻한다"를
  // 보증한다(notation_contract.md §1 권위 경계 불변).
  //
  // `value`가 없는 케이스는 제외한다 — 웹 latexToMath가 아직 못 다루는 토큰(`\div`·`\leq`)이거나
  // 관계식이라 단일 수치로 평가되지 않는다. 그 목록은 부록 A 드리프트 대장이 소유한다.
  const numericLatexCases = contract.latex_cases.filter((c) => c.value !== undefined);
  it.each(numericLatexCases)("latex_case $id: $latex", ({ latex, vars, value, tol }) => {
    const result = math.evaluate(latexToMath(latex), vars ?? {});
    expect(result).toBeCloseTo(value, Math.round(-Math.log10(tol ?? 1e-9)));
  });

  it("계약에 latex_cases가 실재한다 — 블록이 사라지면 위 골든이 조용히 0건이 된다", () => {
    // it.each는 빈 배열이면 테스트를 0개 만들고 스위트는 green이다 — 침묵 통과 방지 단언.
    expect(Array.isArray(contract.latex_cases)).toBe(true);
    expect(numericLatexCases.length).toBeGreaterThan(0);
  });

  it("렌더 어댑터 경계: 파이썬식 ** → mathjs ^ 변환(graph2dSpecToState)", () => {
    // backend는 `**`/`^` 둘 다(convert_xor) 읽지만 mathjs는 `^`만 안다 — 어댑터가 변환을 책임진다.
    const state = graph2dSpecToState({ function: "x**2" });
    expect(state.rows[0].expr).toBe("x^2");
  });
});
