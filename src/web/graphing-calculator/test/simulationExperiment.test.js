import { describe, it, expect } from "vitest";
import { parseExperiment, runTrials, clampTrials } from "../src/lib/simulationExperiment";

describe("parseExperiment — 실험 문자열 → 이산 확률 모델", () => {
  it("동전/coin → 앞·뒤 균등", () => {
    expect(parseExperiment("동전 던지기")).toEqual({
      kind: "coin",
      labels: ["앞", "뒤"],
      weights: [1, 1],
    });
    expect(parseExperiment("Coin flip").kind).toBe("coin");
  });

  it("주사위/dice → 1~6 균등", () => {
    const m = parseExperiment("주사위 던지기");
    expect(m.kind).toBe("dice");
    expect(m.labels).toEqual(["1", "2", "3", "4", "5", "6"]);
    expect(m.weights).toHaveLength(6);
    expect(parseExperiment("roll a die").kind).toBe("dice");
  });

  it("미지원 실험·빈 값 → null", () => {
    expect(parseExperiment("카드 뽑기")).toBeNull();
    expect(parseExperiment("")).toBeNull();
    expect(parseExperiment(null)).toBeNull();
  });
});

describe("clampTrials — 시행수 보정", () => {
  it("[1, 50000] 정수로 clamp", () => {
    expect(clampTrials(0)).toBe(1);
    expect(clampTrials(99999)).toBe(50000);
    expect(clampTrials(123.9)).toBe(123);
    expect(clampTrials("abc")).toBe(1);
  });
});

describe("runTrials — 가중치 시행 → 라벨별 카운트", () => {
  it("주입 rng로 결정적 카운트(앞·뒤)", () => {
    const model = parseExperiment("동전");
    // rng가 0.2(앞)·0.9(뒤)·0.1(앞) 순서로 → [2, 1]
    const seq = [0.2, 0.9, 0.1];
    let i = 0;
    const rng = () => seq[i++];
    expect(runTrials(model, 3, rng)).toEqual([2, 1]);
  });

  it("카운트 합 = 시행수", () => {
    const model = parseExperiment("주사위");
    const counts = runTrials(model, 600);
    expect(counts.reduce((a, c) => a + c, 0)).toBe(600);
    expect(counts).toHaveLength(6);
  });

  it("시행수는 clamp된다(0 → 1회)", () => {
    const counts = runTrials(parseExperiment("동전"), 0, () => 0.1);
    expect(counts.reduce((a, c) => a + c, 0)).toBe(1);
  });
});
