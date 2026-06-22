// ====== 순수 수학 헬퍼 (UI·캔버스·React 비의존) ======
// GraphingCalculator/QuizMode가 import해 쓰는 순수 함수 모음. 캔버스·React state에 의존하지 않아
// 단위 테스트가 쉽다(커버리지 70%+ 게이트의 주 대상). 원본 graphingcalculator.jsx의 모듈 스코프
// 헬퍼 + 컴포넌트 내부 순수 로직을 이곳으로 추출했다(시그니처·동작 동일 — 시각적 회귀 0 목표).
import * as math from "mathjs";

// ====== LaTeX → mathjs 변환 ======
export const latexToMath = (latex) => {
  let s = latex || "";
  s = s.replace(/\\operatorname\{([^{}]*)\}/g, "$1");
  s = s.replace(/\\mathrm\{([^{}]*)\}/g, "$1"); // \mathrm{b} → b (붙여넣기 변환 대응)
  for (let i = 0; i < 6; i++) s = s.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, "(($1)/($2))");
  s = s.replace(/\\sqrt\{([^{}]*)\}/g, "sqrt($1)");
  s = s.replace(/\\cdot|\\times/g, "*");
  s = s.replace(/\\left|\\right/g, "");
  s = s.replace(/\\pi/g, " pi ");
  s = s.replace(/\\(sin|cos|tan|asin|acos|atan|log|ln|abs|exp)/g, "$1");
  s = s.replace(/\\le/g, "<=").replace(/\\ge/g, ">=");
  s = s.replace(/\^\{([^{}]*)\}/g, "^($1)");
  s = s.replace(/[{}]/g, "");
  s = s.replace(/([0-9a-zA-Z\)])\s+([0-9a-zA-Z\(])/g, "$1*$2");
  s = s.replace(/\s+/g, "");
  s = s.replace(/([0-9])([a-zA-Z])/g, "$1*$2");
  return s.trim();
};

// ====== [Phase 5] 입력 식의 타입 판별 ======
// 점 (1,3) / 부등식 y>x^2 / 음함수 x^2+y^2=9 / 일반함수 y=x^2 를 구분
export const classify = (expr) => {
  const s = (expr || "").trim();
  if (!s) return { type: "empty" };

  // [Phase 8] 극좌표: r = f(θ) 형태 (r= 로 시작)
  if (/^r\s*=/.test(s)) {
    let body = s.replace(/^r\s*=/, "").trim();
    body = body.replace(/theta|θ/g, "theta"); // θ 기호를 theta로 통일
    return { type: "polar", body };
  }

  // [Phase 8] 매개변수: (x(t), y(t)) 형태 — 괄호 안에 변수 t가 들어감
  // 점 (1,3)과 구분: 좌표 안에 t(또는 숫자가 아닌 식)가 있으면 매개변수
  const paramMatch = s.match(/^\(\s*(.+)\s*,\s*(.+)\s*\)$/);
  if (paramMatch && /t/.test(s)) {
    return { type: "parametric", xBody: paramMatch[1].trim(), yBody: paramMatch[2].trim() };
  }

  // 점: 좌표 쌍 (콤마 포함, 괄호로 시작, 숫자만)
  if (/^\(\s*-?[\d.]+\s*,\s*-?[\d.]+\s*\)/.test(s)) {
    const pts = [];
    const re = /\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)/g;
    let m;
    while ((m = re.exec(s))) pts.push([parseFloat(m[1]), parseFloat(m[2])]);
    return { type: "point", points: pts };
  }
  // 부등식
  const ineq = s.match(/(>=|<=|>|<)/);
  if (ineq) {
    const op = ineq[1];
    const parts = s.split(/>=|<=|>|</);
    return { type: "inequality", op, lhs: parts[0].trim(), rhs: parts[1].trim() };
  }
  // 등식
  if (s.includes("=")) {
    const [lhs, rhs] = s.split("=");
    if (lhs.trim() === "y") return { type: "function", body: rhs.trim() };
    if (rhs.trim() === "y") return { type: "function", body: lhs.trim() };
    return { type: "implicit", lhs: lhs.trim(), rhs: rhs.trim() };
  }
  // 일반 함수
  return { type: "function", body: s };
};

// 변수 추출 (y도 음함수/부등식에서 쓰이므로 BUILTINS에서 별도 관리)
const BUILTINS = new Set([
  "x", "y", "t", "theta", "e", "pi", "PI", "E",
  "sin", "cos", "tan", "asin", "acos", "atan",
  "sqrt", "log", "ln", "abs", "exp", "floor", "ceil", "round",
]);
export const extractVars = (expr) => {
  const vars = new Set();
  try {
    math.parse(expr).traverse((node) => {
      if (node.isSymbolNode && !BUILTINS.has(node.name)) vars.add(node.name);
    });
  } catch { return []; }
  return [...vars];
};

// ====== 텍스트 입력 모드용: ASCII 수식 → LaTeX 변환 ======
// 일반 입력칸에 붙여넣은 "x^2" 같은 텍스트를 MathLive가 쓰는 LaTeX로 바꿔줍니다.
export const asciiToLatex = (ascii) => {
  const s = (ascii || "").trim();
  if (!s) return "";
  // 등식/부등식/점은 mathjs가 파싱 못하므로 원본 그대로 (latexToMath가 처리)
  if (/[=<>]/.test(s) || /^\(/.test(s)) return s;
  try { return math.parse(s).toTex(); }
  catch { return s; }
};

// ====== 최소제곱 선형회귀: y = m*x + b 와 결정계수 R² (원본 컴포넌트 regression의 순수 코어) ======
export const linearRegression = (points) => {
  const pts = points || [];
  const n = pts.length;
  if (n < 2) return null;
  let sx = 0, sy = 0, sxy = 0, sxx = 0;
  pts.forEach(([x, y]) => { sx += x; sy += y; sxy += x * y; sxx += x * x; });
  const denom = n * sxx - sx * sx;
  if (denom === 0) return null; // 모든 x가 같으면 직선 못 구함
  const m = (n * sxy - sx * sy) / denom;
  const b = (sy - m * sx) / n;
  // R²: 1에 가까울수록 직선이 데이터를 잘 설명
  const meanY = sy / n;
  let ssRes = 0, ssTot = 0;
  pts.forEach(([x, y]) => { const pred = m * x + b; ssRes += (y - pred) ** 2; ssTot += (y - meanY) ** 2; });
  const r2 = ssTot === 0 ? 1 : 1 - ssRes / ssTot;
  return { m, b, r2 };
};

// ====== 두 식이 같은 그래프인지 채점 (여러 x 표본에서 y가 일치하는지) ======
export const sameGraph = (expr1, expr2) => {
  let n1, n2;
  try { n1 = math.compile(expr1); n2 = math.compile(expr2); } catch { return false; }
  const testXs = [-4.7, -3.1, -1.5, -0.3, 0.8, 2.2, 3.6, 4.9, 1.0, -2.0];
  let matches = 0, valid = 0;
  for (const x of testXs) {
    let y1, y2;
    try { y1 = n1.evaluate({ x }); y2 = n2.evaluate({ x }); } catch { continue; }
    if (!isFinite(y1) || !isFinite(y2)) continue;
    valid++;
    if (Math.abs(y1 - y2) < 1e-6 * (1 + Math.abs(y1))) matches++;
  }
  return valid >= 5 && matches === valid;
};

// ====== 수치 미분 (중앙차분법): f'(x) ≈ (f(x+h) - f(x-h)) / (2h) ======
// scope: 슬라이더 변수 등 추가 스코프(기본 {}). QuizMode는 scope 없이, GraphingCalculator는 scope와 함께 호출.
export const numDeriv = (node, x, scope = {}) => {
  const h = 1e-5;
  try {
    return (node.evaluate({ ...scope, x: x + h }) - node.evaluate({ ...scope, x: x - h })) / (2 * h);
  } catch { return NaN; }
};

// ====== 수치 2계도함수 (볼록성 판정용) ======
export const num2Deriv = (node, x, scope = {}) => {
  const h = 1e-4;
  try {
    return (node.evaluate({ ...scope, x: x + h }) - 2 * node.evaluate({ ...scope, x }) + node.evaluate({ ...scope, x: x - h })) / (h * h);
  } catch { return NaN; }
};
