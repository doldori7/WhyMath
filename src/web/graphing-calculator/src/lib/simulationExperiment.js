// ====== 확률 시뮬레이션 엔진 (키워드 MVP — 동전·주사위) ======
// 백엔드 SimulationSpec({experiment, trials})의 experiment 문자열을 인식해 이산 확률 모델로 바꾸고
// Monte Carlo 시행을 돌린다. 차트 라이브러리가 없어 결과(카운트)는 캔버스로 손그림한다.
// 범위(MVP): 동전·주사위만. 미지원 실험은 parseExperiment가 null → 상위에서 안내 카드.
// 후속: 구조화 outcomes(label+weight) 명세 + 임의 분포.

// 한국어·영문 키워드를 매칭하기 위한 정규화(소문자·공백 제거).
const _norm = (s) => (typeof s === "string" ? s.toLowerCase().replace(/\s+/g, "") : "");

/**
 * experiment 문자열 → 이산 확률 모델 { kind, labels, weights } 또는 null(미지원).
 * @param {string} experiment - 예: "동전 던지기", "주사위 던지기", "coin flip".
 */
export const parseExperiment = (experiment) => {
  const e = _norm(experiment);
  if (!e) return null;
  if (e.includes("동전") || e.includes("coin")) {
    return { kind: "coin", labels: ["앞", "뒤"], weights: [1, 1] };
  }
  if (e.includes("주사위") || e.includes("dice") || e.includes("die") || e.includes("육면체")) {
    return {
      kind: "dice",
      labels: ["1", "2", "3", "4", "5", "6"],
      weights: [1, 1, 1, 1, 1, 1],
    };
  }
  return null;
};

// 시행 횟수 안전 범위(성능 가드).
const MIN_TRIALS = 1;
const MAX_TRIALS = 50000;

/** trials를 [MIN_TRIALS, MAX_TRIALS] 정수로 보정. */
export const clampTrials = (trials) => {
  const n = Math.floor(Number(trials));
  if (!Number.isFinite(n)) return MIN_TRIALS;
  return Math.max(MIN_TRIALS, Math.min(MAX_TRIALS, n));
};

/**
 * 모델의 가중치에 따라 trials번 시행해 라벨별 카운트 배열을 돌려준다.
 * @param {{labels:string[], weights:number[]}} model
 * @param {number} trials
 * @param {() => number} [rng] - [0,1) 난수 생성기(테스트 주입용·기본 Math.random).
 * @returns {number[]} labels와 같은 길이의 카운트 배열.
 */
export const runTrials = (model, trials, rng = Math.random) => {
  if (!model || !Array.isArray(model.weights) || !model.weights.length) return [];
  const weights = model.weights;
  const total = weights.reduce((a, w) => a + (w > 0 ? w : 0), 0);
  const counts = new Array(weights.length).fill(0);
  if (total <= 0) return counts;
  const n = clampTrials(trials);
  for (let t = 0; t < n; t++) {
    let r = rng() * total;
    let idx = weights.length - 1; // 부동소수 잔차 안전망
    for (let i = 0; i < weights.length; i++) {
      r -= weights[i] > 0 ? weights[i] : 0;
      if (r < 0) {
        idx = i;
        break;
      }
    }
    counts[idx] += 1;
  }
  return counts;
};
