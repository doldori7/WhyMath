// ====== 코어 Graph2dSpec 소비 어댑터 (L5가 코어 선언적 명세를 읽어 렌더) ======
// 백엔드 코어(L1-L4)의 선언적 시각화 명세 Graph2dSpec(설계: docs/architecture/05_interaction.md §5.2,
// 구현: src/backend/whymath_backend/schema/visualization.py)을 *수정 없이* 웹 계산기 상태로 변환한다.
// "표현 ≠ 의미"(슬라이스 89) — 코어는 구조(JSON)를 주고, L5(이 웹 도구)는 그것을 받아 렌더만 한다.
//
// 권위 경계(docs/architecture/notation_contract.md): mathjs는 *렌더·수치 평가 전용*이며 수식 동치/정오
// 판정에 관여하지 않는다 — 동치·정오 판정 단일 권위는 백엔드 SymPy(L3 verify_step·verify_answer)다.
// 거듭제곱은 caret `^`가 표준이라 파이썬식 `**`는 여기서 `^`로 변환만 한다(SymPy는 convert_xor로 둘 다
// 읽음). 두 파서가 같은 canonical 표기를 같은 수치로 해석함은 공유 golden test로 교차검증한다
// (test/notation_contract.test.js ↔ backend·공유 data/notation_contract.json).
//
// Graph2dSpec 형태:
//   { function: "a*x**2+b*x+c", domain: [xMin, xMax], parameters: [{name,min,max,step,default}] }
//
// 백엔드·Flutter는 이 계산기를 `?spec=<base64(JSON)>` URL로 띄워 함수·슬라이더·정의역을 주입할 수 있다.
import * as math from "mathjs";
import { classify, extractVars } from "./mathExpr.js";

// Graph2dSpec → 계산기 applyState 호환 부분 상태({rows, sliders, view}). 변환할 게 없으면 null.
export const graph2dSpecToState = (spec) => {
  if (!spec || typeof spec !== "object") return null;

  // function: 파이썬식 '**' 지수를 mathjs '^'로 변환, latex는 toTex로 생성(MathField 표시용).
  const rows = [];
  if (typeof spec.function === "string" && spec.function.trim()) {
    const expr = spec.function.replace(/\*\*/g, "^").trim();
    let latex = expr;
    try {
      latex = math.parse(expr).toTex();
    } catch {
      /* 파싱 실패 시 원본 문자열을 latex로 사용(텍스트 모드 폴백) */
    }
    rows.push({ latex, expr });
  }

  // parameters → sliders (이름·범위·기본값). 누락 필드는 계산기 기본값으로 보정.
  const sliders = {};
  if (Array.isArray(spec.parameters)) {
    spec.parameters.forEach((p) => {
      if (!p || typeof p.name !== "string" || !p.name) return;
      sliders[p.name] = {
        value: Number.isFinite(p.default) ? p.default : 1,
        min: Number.isFinite(p.min) ? p.min : -10,
        max: Number.isFinite(p.max) ? p.max : 10,
        step: Number.isFinite(p.step) && p.step > 0 ? p.step : 0.1,
        playing: false,
      };
    });
  }

  // domain [xMin, xMax] → view의 x 범위(y는 기본 ±10 유지).
  let view;
  if (Array.isArray(spec.domain) && spec.domain.length === 2) {
    const [xMin, xMax] = spec.domain;
    if (Number.isFinite(xMin) && Number.isFinite(xMax) && xMin < xMax) {
      view = { xMin, xMax, yMin: -10, yMax: 10 };
    }
  }

  if (!rows.length && !Object.keys(sliders).length && !view) return null;
  return { rows, sliders, view };
};

// ====== 코어 Surface3dSpec 소비 어댑터 (3D 곡면) ======
// 백엔드 Surface3dSpec({ surface: "z = x**2 + y**2", rotatable }, schema/visualization.py)을
// 계산기 3D 상태({mode3D, expr3D, range3D})로 변환한다. graph2dSpecToState의 3D 짝.
// 웹 Surface3D 렌더러는 expr를 mathjs로 컴파일(node.evaluate({x,y}))하므로 좌변('z =')을 떼고
// 파이썬 '**'를 mathjs '^'로 바꾼 RHS만 expr3D로 넘긴다. 변환할 게 없으면 null.
export const surface3dSpecToState = (spec) => {
  if (!spec || typeof spec.surface !== "string" || !spec.surface.trim()) return null;
  let body = spec.surface.trim();
  const eq = body.indexOf("="); // "z = …"/"f(x,y) = …" 좌변 제거(우변 식만 평가)
  if (eq >= 0) body = body.slice(eq + 1).trim();
  body = body.replace(/\*\*/g, "^"); // 파이썬 '**' → mathjs '^'
  if (!body) return null;
  const st = { mode3D: true, expr3D: body };
  if (Number.isFinite(spec.range) && spec.range > 0) st.range3D = spec.range; // 선택(없으면 기본 유지)
  return st;
};

// ====== 코어 SimulationSpec 소비 어댑터 (확률 시뮬) ======
// 백엔드 SimulationSpec({ experiment: "동전 던지기", trials: 100 })을 계산기 시뮬 상태로 변환한다.
// 실제 실험 인식·시행은 simulationExperiment.js(parseExperiment·runTrials)가 담당하고, 여기선
// 상태(simulationMode·experiment·trials)로만 매핑한다. experiment 없으면 null.
export const simulationSpecToState = (spec) => {
  if (!spec || typeof spec.experiment !== "string" || !spec.experiment.trim()) return null;
  const st = { simulationMode: true, experiment: spec.experiment.trim() };
  if (Number.isFinite(spec.trials) && spec.trials > 0) st.trials = Math.floor(spec.trials);
  // 구조화 outcomes(label+weight)가 있으면 통과 — 웹이 키워드 파싱보다 우선 소비.
  if (Array.isArray(spec.outcomes) && spec.outcomes.length > 0) st.outcomes = spec.outcomes;
  return st;
};

// URL 파라미터 문자열에서 Graph2dSpec 파싱: base64(JSON) 우선, 실패 시 (URL 디코딩한) raw JSON.
export const parseSpecParam = (raw) => {
  if (!raw || typeof raw !== "string") return null;
  const tryParse = (s) => {
    try {
      const obj = JSON.parse(s);
      return obj && typeof obj === "object" ? obj : undefined;
    } catch {
      return undefined;
    }
  };
  // 1) base64(JSON) — UTF-8 디코드로 한국어 등 비-ASCII 보존(Flutter base64(utf8(json))의 역연산).
  //    atob는 바이트→Latin-1 문자열이라 그대로 JSON.parse하면 한글이 깨진다 → TextDecoder로 UTF-8 복원.
  try {
    if (typeof atob === "function") {
      const bin = atob(raw);
      let text = bin;
      try {
        const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
        text = new TextDecoder().decode(bytes);
      } catch {
        /* TextDecoder 미지원 환경이면 바이너리 문자열 폴백(ASCII는 동일) */
      }
      const obj = tryParse(text);
      if (obj) return obj;
    }
  } catch {
    /* base64 아님 — 다음 분기로 */
  }
  // 2) raw JSON (URL 인코딩 가능)
  try {
    return tryParse(decodeURIComponent(raw)) ?? tryParse(raw) ?? null;
  } catch {
    return tryParse(raw) ?? null;
  }
};

// ====== 역방향 어댑터: 계산기 상태 → 코어 Graph2dSpec (내보내기) ======
// graph2dSpecToState의 *역연산*. 계산기가 만든 그래프를 코어 선언적 명세(JSON)로 추출해
// 백엔드·문항·공유 링크로 보낼 수 있게 한다 — "표현 ≠ 의미"(슬라이스 89) 양방향 완성.
//
// 입력: 계산기 부분 상태 { rows, sliders, view }
//   - rows[i]: { expr, latex, ... }  (expr는 mathjs '^' 지수)
//   - sliders[name]: { value, min, max, step, playing }
//   - view: { xMin, xMax, yMin, yMax }
// 출력: Graph2dSpec { function?, domain?, parameters? } (정의된 키만) 또는 null(함수 행 없음).
//
// 규약(정방향과 대칭):
//   - Graph2dSpec는 단일 function만 표현 → rows에서 *첫 일반 함수 행*만 취하고 점/음함수/
//     부등식/극좌표/매개변수 행은 건너뛴다(classify 판별).
//   - mathjs '^' → 파이썬 '**' 치환(정방향 graph2dSpecToState의 '**'→'^' 역).
//   - 함수에 실제로 쓰인 슬라이더만 parameters로(정방향이 parameters에서만 슬라이더를 만들므로
//     클린 라운드트립). default = 현재 슬라이더 value.
//   - domain은 x 범위만(코어 규약: y는 ±10 고정, 명세에 안 실음).
export const calcStateToGraph2dSpec = (state) => {
  if (!state || typeof state !== "object") return null;
  const { rows, sliders, view } = state;

  // 1) 첫 일반 함수 행 탐색(점/음함수/부등식/극좌표/매개변수 제외).
  let body = null;
  if (Array.isArray(rows)) {
    for (const r of rows) {
      if (!r || typeof r.expr !== "string" || !r.expr.trim()) continue;
      const c = classify(r.expr);
      if (c.type === "function") {
        body = c.body; // 'y=' 접두 제거된 본문
        break;
      }
    }
  }
  if (!body) return null;

  // 2) function: '^' → '**' (파이썬식 지수).
  const fn = body.replace(/\^/g, "**");
  const spec = { function: fn };

  // 3) parameters: 함수에 쓰인 변수 중 슬라이더가 존재하는 것만.
  if (sliders && typeof sliders === "object") {
    const parameters = [];
    for (const name of extractVars(body)) {
      const s = sliders[name];
      if (!s || typeof s !== "object") continue;
      parameters.push({
        name,
        min: s.min,
        max: s.max,
        step: s.step,
        default: s.value,
      });
    }
    if (parameters.length) spec.parameters = parameters;
  }

  // 4) domain: 유효한 view의 x 범위만.
  if (view && Number.isFinite(view.xMin) && Number.isFinite(view.xMax) && view.xMin < view.xMax) {
    spec.domain = [view.xMin, view.xMax];
  }

  return spec;
};
