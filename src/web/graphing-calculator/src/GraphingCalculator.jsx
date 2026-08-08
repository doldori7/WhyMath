import React, { useState, useRef, useEffect, useCallback } from "react";
import * as math from "mathjs";
import {
  latexToMath,
  classify,
  extractVars,
  asciiToLatex,
  linearRegression,
  numDeriv,
  num2Deriv,
} from "./lib/mathExpr";
import {
  graph2dSpecToState,
  parseSpecParam,
  unwrapSpecEnvelope,
  specToStateForType,
  calcStateToGraph2dSpec,
} from "./lib/graph2dSpec";
import { emitInteraction } from "./lib/interactionEmitter";
import { parseExperiment, runTrials, modelFromOutcomes } from "./lib/simulationExperiment";

// ====== [Phase 4] MathLive를 npm 번들에서 동적 로딩 (코드 분할·오프라인 자족) ======
// 과거엔 CDN <script>로 불러왔으나, WebView/오프라인 자족을 위해 npm 의존성으로 번들한다.
// 동적 import라 초기 번들에 포함되지 않고 입력칸이 처음 필요할 때만 로드된다(코드 분할).
// import 시 <math-field> 커스텀 엘리먼트가 자동 등록된다. 폰트는 public/mathlive/fonts에서 자족.
let mathliveLoadPromise = null;
const loadMathLive = () => {
  if (mathliveLoadPromise) return mathliveLoadPromise;
  if (typeof window !== "undefined" && window.customElements?.get("math-field")) {
    mathliveLoadPromise = Promise.resolve();
    return mathliveLoadPromise;
  }
  mathliveLoadPromise = import("mathlive").then((ml) => {
    // 폰트는 번들된 정적 자산(public/mathlive/fonts)에서 — CDN 의존 제거. 효과음은 비활성.
    if (ml.MathfieldElement) {
      ml.MathfieldElement.fontsDirectory = "./mathlive/fonts";
      ml.MathfieldElement.soundsDirectory = null;
    }
  });
  return mathliveLoadPromise;
};

const COLORS = ["#c74440", "#2d70b3", "#388c46", "#6042a6", "#fa7e19", "#000000"];

const makeRow = (id) => ({
  id, latex: "", expr: "",
  color: COLORS[(id - 1) % COLORS.length],
  visible: true, error: null,
  // [Phase 9] 미분 시각화 관련
  showTangent: false, // 접선 표시 on/off
  tangentX: 1,        // 접점의 x좌표 (슬라이더로 조절)
  showDeriv: false,   // 도함수 곡선 표시 on/off
  // [Phase 10] 적분 시각화 관련
  showIntegral: false, // 넓이 색칠 + 리만 합 표시 on/off
  intA: 0,             // 적분 구간 시작
  intB: 3,             // 적분 구간 끝
  intN: 10,            // 리만 합 직사각형 개수
});

// ====== MathLive 입력칸 컴포넌트 ======
function MathField({ value, onChange, color, error }) {
  const ref = useRef(null);
  const [ready, setReady] = useState(
    typeof window !== "undefined" && !!window.customElements?.get("math-field")
  );
  const [failed, setFailed] = useState(false);
  // [붙여넣기 대응] 텍스트 입력 모드 on/off
  const [textMode, setTextMode] = useState(false);
  // 텍스트 모드에서 사용자가 보는 ASCII 원본 (예: "x^2")
  const [text, setText] = useState("");

  useEffect(() => {
    let alive = true;
    loadMathLive().then(() => alive && setReady(true)).catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!ready || textMode) return; // 텍스트 모드일 땐 편집기 동기화 안 함
    const mf = ref.current;
    if (!mf) return;
    if (mf.value !== value) mf.value = value;
    const handler = () => onChange(mf.value);
    mf.addEventListener("input", handler);
    return () => mf.removeEventListener("input", handler);
  }, [ready, value, onChange, textMode]);

  // 텍스트 모드 입력 처리: ASCII → LaTeX 변환해서 부모로 전달
  const handleText = (v) => {
    setText(v);
    onChange(asciiToLatex(v)); // 부모는 LaTeX를 받아 기존 로직 그대로 사용
  };

  // 모드 전환 버튼 (편집기 ↔ 텍스트)
  const ModeBtn = (
    <button
      onClick={() => setTextMode((m) => !m)}
      title={textMode ? "수식 편집기로" : "텍스트로 입력 (붙여넣기 가능)"}
      style={{ border: "none", background: "none", cursor: "pointer", fontSize: 15, color: textMode ? "#2d70b3" : "#bbb", flexShrink: 0, padding: "0 2px" }}
    >
      {textMode ? "✎" : "⌨"}
    </button>
  );

  // 로드 실패 시: 일반 입력칸 (브라우저 기본 붙여넣기 사용)
  if (failed) {
    return (
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="예: x^2, (1,3), x^2+y^2=9"
        style={{ flex: 1, fontSize: 16, padding: "4px 2px", border: "none", borderBottom: error ? "2px solid #c74440" : "1px solid #ddd", outline: "none", fontFamily: "monospace", background: "transparent" }} />
    );
  }

  // 텍스트 입력 모드: 일반 input이라 붙여넣기가 항상 됨
  if (textMode) {
    return (
      <>
        <input
          value={text}
          onChange={(e) => handleText(e.target.value)}
          placeholder="붙여넣기 가능: x^2, sin(x), x^2+y^2=9"
          autoFocus
          style={{ flex: 1, fontSize: 16, padding: "4px 2px", border: "none", borderBottom: error ? "2px solid #c74440" : "1px solid #2d70b3", outline: "none", fontFamily: "monospace", background: "transparent" }}
        />
        {ModeBtn}
      </>
    );
  }

  if (!ready) return <span style={{ flex: 1, fontSize: 14, color: "#bbb" }}>수식 편집기 불러오는 중…</span>;

  return (
    <>
      <math-field ref={ref}
        style={{ flex: 1, fontSize: "18px", padding: "2px 4px", border: "none", borderBottom: error ? "2px solid #c74440" : "1px solid #ddd", outline: "none", background: "transparent", "--caret-color": color, "--selection-background-color": color + "33" }} />
      {ModeBtn}
    </>
  );
}

// ====== [Phase 11] three.js를 npm 번들에서 동적 로딩 (코드 분할·오프라인 자족) ======
// 과거엔 CDN <script>(r128)로 불러왔으나 오프라인 자족을 위해 npm 의존성으로 번들한다.
// 동적 import라 3D 모드 진입 시에만 로드된다(코드 분할). 기존 Surface3D가 window.THREE를
// 참조하므로, 모듈 네임스페이스를 window.THREE에 어댑터로 연결해 컴포넌트 본문은 무수정.
let threeLoadPromise = null;
const loadThree = () => {
  if (threeLoadPromise) return threeLoadPromise;
  if (typeof window !== "undefined" && window.THREE) {
    threeLoadPromise = Promise.resolve();
    return threeLoadPromise;
  }
  threeLoadPromise = import("three").then((THREE) => {
    if (typeof window !== "undefined") window.THREE = THREE;
  });
  return threeLoadPromise;
};

// ====== [Phase 11] 3D 곡면 뷰 컴포넌트 ======
// z = f(x, y) 식을 받아 3차원 곡면을 그리고, 마우스 드래그로 회전시킵니다.
function Surface3D({ expr, range }) {
  const mountRef = useRef(null);
  const [ready, setReady] = useState(typeof window !== "undefined" && !!window.THREE);
  const [failed, setFailed] = useState(false);
  // 회전 각도(가로 회전 az, 세로 회전 el)와 확대(zoom)를 보관
  const stateRef = useRef({ az: -0.6, el: 0.5, zoom: 1, dragging: false, lastX: 0, lastY: 0 });
  const sceneRef = useRef({}); // three 객체들 보관

  useEffect(() => {
    let alive = true;
    loadThree().then(() => alive && setReady(true)).catch(() => alive && setFailed(true));
    return () => { alive = false; };
  }, []);

  // three.js 장면 1회 초기화
  useEffect(() => {
    if (!ready || !mountRef.current) return;
    const THREE = window.THREE;
    const mount = mountRef.current;
    const w = mount.clientWidth, h = mount.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xfafafa);
    const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    mount.appendChild(renderer.domElement);

    // 조명 (곡면 입체감)
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.6);
    dir.position.set(5, 10, 7);
    scene.add(dir);

    // 좌표축 (빨강=x, 초록=y, 파랑=z)
    const axes = new THREE.AxesHelper(range * 1.3);
    scene.add(axes);

    sceneRef.current = { THREE, scene, camera, renderer, mesh: null };

    // 렌더 루프
    let raf;
    const animate = () => {
      const st = stateRef.current;
      // 구면 좌표로 카메라 위치 계산 (회전 각도 반영)
      const dist = range * 3.2 / st.zoom;
      camera.position.set(
        dist * Math.cos(st.el) * Math.sin(st.az),
        dist * Math.sin(st.el),
        dist * Math.cos(st.el) * Math.cos(st.az)
      );
      camera.up.set(0, 1, 0);
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    animate();

    // 정리
    return () => {
      cancelAnimationFrame(raf);
      renderer.dispose();
      if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
    };
  }, [ready, range]);

  // 식이 바뀌면 곡면(mesh)을 다시 생성
  useEffect(() => {
    const s = sceneRef.current;
    if (!s.scene || !ready) return;
    const THREE = s.THREE;

    // 이전 곡면 제거
    if (s.mesh) { s.scene.remove(s.mesh); s.mesh.geometry.dispose(); s.mesh.material.dispose(); s.mesh = null; }
    if (!expr || !expr.trim()) return;

    let node;
    try { node = math.compile(expr); } catch { return; }

    // 격자 정점 만들기 (N×N)
    const N = 60;
    const geo = new THREE.PlaneGeometry(range * 2, range * 2, N, N);
    const pos = geo.attributes.position;
    let minZ = Infinity, maxZ = -Infinity;
    const zVals = [];
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), yPlane = pos.getY(i); // PlaneGeometry는 xy평면
      let z;
      try { z = node.evaluate({ x, y: yPlane }); } catch { z = 0; }
      if (!isFinite(z)) z = 0;
      zVals.push(z);
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z;
    }
    // three는 y가 위쪽이므로, 계산한 z를 높이(y)로 올리고 평면 y는 깊이(z축)로
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), yPlane = pos.getY(i);
      pos.setXYZ(i, x, zVals[i], -yPlane);
    }
    geo.computeVertexNormals();

    // 높이에 따라 색이 변하는 재질 (낮으면 파랑, 높으면 빨강)
    const colors = [];
    const span = maxZ - minZ || 1;
    for (let i = 0; i < pos.count; i++) {
      const t = (zVals[i] - minZ) / span; // 0~1
      // 파랑(0)→청록→초록→노랑→빨강(1) 그라데이션
      const c = new THREE.Color();
      c.setHSL((1 - t) * 0.7, 0.7, 0.5); // HSL 색상환 이용
      colors.push(c.r, c.g, c.b);
    }
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));

    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true, side: THREE.DoubleSide,
      flatShading: false, roughness: 0.6, metalness: 0.1,
    });
    const mesh = new THREE.Mesh(geo, mat);
    s.scene.add(mesh);
    s.mesh = mesh;
  }, [expr, range, ready]);

  // 마우스 드래그로 회전, 휠로 확대 (OrbitControls 없이 직접 구현)
  const onMouseDown = (e) => { const st = stateRef.current; st.dragging = true; st.lastX = e.clientX; st.lastY = e.clientY; };
  const onMouseMove = (e) => {
    const st = stateRef.current;
    if (!st.dragging) return;
    st.az -= (e.clientX - st.lastX) * 0.01; // 좌우 → 가로 회전
    st.el += (e.clientY - st.lastY) * 0.01; // 상하 → 세로 회전
    st.el = Math.max(-1.5, Math.min(1.5, st.el)); // 뒤집힘 방지
    st.lastX = e.clientX; st.lastY = e.clientY;
  };
  const onMouseUp = () => { stateRef.current.dragging = false; };
  const onWheel = (e) => {
    e.preventDefault();
    const st = stateRef.current;
    st.zoom *= e.deltaY > 0 ? 0.92 : 1.08;
    st.zoom = Math.max(0.3, Math.min(5, st.zoom));
  };

  if (failed) return <div style={{ padding: 20, color: "#999" }}>3D 라이브러리를 불러오지 못했습니다 (인터넷 연결 확인).</div>;
  if (!ready) return <div style={{ padding: 20, color: "#bbb" }}>3D 엔진 불러오는 중…</div>;

  return (
    <div
      ref={mountRef}
      onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp} onMouseLeave={onMouseUp} onWheel={onWheel}
      style={{ width: "100%", height: "100%", cursor: "grab" }}
    />
  );
}

// [Phase 13] 확률 시뮬 뷰 — 동전·주사위 Monte Carlo 결과를 캔버스 막대그래프(개수+백분율)로 그린다.
// 미지원 실험(parseExperiment=null)은 안내 카드. 시행 로직은 부모가 runTrials로 돌려 counts로 내려준다.
function SimulationView({ experiment, setExperiment, trials, setTrials, counts, outcomes, onRun, onBack }) {
  const canvasRef = useRef(null);
  // 구조화 outcomes가 있으면 우선, 없으면 키워드 파싱(JSX 분기·라벨 표시용).
  const model = modelFromOutcomes(outcomes) || parseExperiment(experiment);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const W = cv.width;
    const H = cv.height;
    ctx.clearRect(0, 0, W, H);
    const m = modelFromOutcomes(outcomes) || parseExperiment(experiment);
    if (!m || !Array.isArray(counts)) return;
    const labels = m.labels;
    const n = labels.length;
    const total = counts.reduce((a, c) => a + c, 0) || 1;
    const maxC = Math.max(...counts, 1);
    const pad = 48;
    const baseY = H - pad;
    const plotW = W - pad * 2;
    const plotH = H - pad * 2;
    const gap = 14;
    const barW = (plotW - gap * (n - 1)) / n;
    // 기준선
    ctx.strokeStyle = "#ccc";
    ctx.beginPath();
    ctx.moveTo(pad, baseY);
    ctx.lineTo(W - pad, baseY);
    ctx.stroke();
    ctx.font = "13px Georgia";
    ctx.textAlign = "center";
    for (let i = 0; i < n; i++) {
      const x = pad + i * (barW + gap);
      const h = (counts[i] / maxC) * plotH;
      ctx.fillStyle = "#2d70b3";
      ctx.fillRect(x, baseY - h, barW, h);
      ctx.fillStyle = "#333";
      ctx.fillText(labels[i], x + barW / 2, baseY + 18);
      const pct = ((counts[i] / total) * 100).toFixed(1);
      ctx.fillStyle = "#555";
      ctx.fillText(`${counts[i]} (${pct}%)`, x + barW / 2, baseY - h - 8);
    }
  }, [counts, experiment, outcomes]);

  return (
    <div
      style={{
        position: "relative",
        height: "100vh",
        padding: 24,
        boxSizing: "border-box",
        fontFamily: "'Georgia', serif",
        background: "#fafafa",
      }}
    >
      <button
        onClick={onBack}
        style={{
          position: "absolute",
          top: 16,
          right: 16,
          zIndex: 10,
          padding: "8px 16px",
          background: "#fff",
          border: "1px solid #ddd",
          borderRadius: 8,
          cursor: "pointer",
          fontSize: 14,
          boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
        }}
      >
        ← 계산기로 돌아가기
      </button>
      <div style={{ fontSize: 20, fontWeight: "bold", marginBottom: 16 }}>확률 시뮬레이션</div>
      <div
        style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}
      >
        <label style={{ fontSize: 13, color: "#666" }}>실험</label>
        <input
          value={experiment}
          onChange={(e) => setExperiment(e.target.value)}
          placeholder="동전 던지기 / 주사위 던지기"
          style={{
            padding: "6px 10px",
            border: "1px solid #ccc",
            borderRadius: 6,
            fontSize: 14,
            width: 220,
          }}
        />
        <label style={{ fontSize: 13, color: "#666" }}>시행 {trials}회</label>
        <input
          type="range"
          min={1}
          max={2000}
          step={1}
          value={trials}
          onChange={(e) => setTrials(parseInt(e.target.value))}
          style={{ accentColor: "#2d70b3" }}
        />
        <button
          onClick={onRun}
          style={{
            padding: "6px 16px",
            border: "1px solid #2d70b3",
            borderRadius: 6,
            background: "#2d70b3",
            color: "#fff",
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          시작
        </button>
      </div>
      {model ? (
        <canvas
          ref={canvasRef}
          width={640}
          height={420}
          style={{
            border: "1px solid #eee",
            borderRadius: 8,
            background: "#fff",
            maxWidth: "100%",
          }}
        />
      ) : (
        <div
          style={{
            marginTop: 24,
            padding: 20,
            border: "1px dashed #ccc",
            borderRadius: 8,
            color: "#888",
            fontSize: 14,
          }}
        >
          이 실험은 아직 지원되지 않아요. 동전·주사위만 시뮬레이션할 수 있어요.
        </div>
      )}
    </div>
  );
}

export default function GraphingCalculator() {
  const [rows, setRows] = useState([makeRow(1)]);
  const nextId = useRef(2);
  const [sliders, setSliders] = useState({});
  const [view, setView] = useState({ xMin: -10, xMax: 10, yMin: -10, yMax: 10 });
  const [hover, setHover] = useState(null);
  // [Phase 6] 데이터 표: {x, y} 쌍의 목록 + 회귀선 표시 여부
  const [table, setTable] = useState([
    { x: "", y: "" },
  ]);
  const [showRegression, setShowRegression] = useState(true);
  // [Phase 7] 저장된 그래프 목록 (이름 목록)
  const [savedList, setSavedList] = useState([]);
  const [saveStatus, setSaveStatus] = useState(""); // 저장/불러오기 안내 메시지
  const [specText, setSpecText] = useState(""); // 코어 Graph2dSpec JSON 내보내기/붙여넣기 칸
  // [Phase 10] 적분 계산 결과 저장 {rowId: {riemannSum, exact}}
  const [integralResults, setIntegralResults] = useState({});
  // [Phase 11] 3D 모드 on/off, 3D 곡면 식, 정의역 범위
  const [mode3D, setMode3D] = useState(false);
  const [expr3D, setExpr3D] = useState("x^2 + y^2");
  const [range3D, setRange3D] = useState(3);
  // [Phase 13] 확률 시뮬 모드 on/off + 실험·시행수·결과 카운트(동전·주사위 MVP)
  const [simMode, setSimMode] = useState(false);
  const [simExperiment, setSimExperiment] = useState("동전 던지기");
  const [simTrials, setSimTrials] = useState(200);
  const [simCounts, setSimCounts] = useState(null); // null=미실행, 배열=라벨별 카운트
  const [simOutcomes, setSimOutcomes] = useState(null); // 구조화 outcomes(있으면 키워드보다 우선)
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const dragRef = useRef(null);
  const animRef = useRef(null);

  // [Phase 6] 표에서 숫자로 변환 가능한 (x,y) 쌍만 골라냄
  const tablePoints = useCallback(() => {
    return table
      .map((r) => [parseFloat(r.x), parseFloat(r.y)])
      .filter(([x, y]) => isFinite(x) && isFinite(y));
  }, [table]);

  // [Phase 6] 최소제곱 선형회귀: y = m*x + b 와 결정계수 R² 계산
  const regression = useCallback(() => linearRegression(tablePoints()), [tablePoints]);


  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setSize({ w: rect.width, h: rect.height });
      }
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  useEffect(() => {
    const needed = new Set();
    rows.forEach((r) => {
      if (r.expr.trim() && !r.error) extractVars(r.expr).forEach((v) => needed.add(v));
    });
    setSliders((prev) => {
      const next = {};
      needed.forEach((v) => { next[v] = prev[v] || { value: 1, min: -10, max: 10, step: 0.1, playing: false }; });
      const same = Object.keys(next).length === Object.keys(prev).length && Object.keys(next).every((k) => prev[k]);
      return same ? prev : next;
    });
  }, [rows]);

  const toPxX = useCallback((x) => ((x - view.xMin) / (view.xMax - view.xMin)) * size.w, [view, size]);
  const toPxY = useCallback((y) => size.h - ((y - view.yMin) / (view.yMax - view.yMin)) * size.h, [view, size]);
  const toMathX = useCallback((px) => view.xMin + (px / size.w) * (view.xMax - view.xMin), [view, size]);
  const toMathY = useCallback((py) => view.yMin + ((size.h - py) / size.h) * (view.yMax - view.yMin), [view, size]);

  const niceStep = (range, n) => {
    const rough = range / n, pow = Math.pow(10, Math.floor(Math.log10(rough))), frac = rough / pow;
    let nice; if (frac < 1.5) nice = 1; else if (frac < 3) nice = 2; else if (frac < 7) nice = 5; else nice = 10;
    return nice * pow;
  };
  const formatNum = (n) => (Math.abs(n) < 1e-10 ? "0" : parseFloat(n.toPrecision(4)).toString());

  const sliderValues = useCallback(() => {
    const obj = {};
    Object.entries(sliders).forEach(([k, s]) => (obj[k] = s.value));
    return obj;
  }, [sliders]);

  const findRoots = useCallback((node, scope) => {
    const roots = []; const samples = 400; const dx = (view.xMax - view.xMin) / samples;
    let prevX = view.xMin, prevY;
    try { prevY = node.evaluate({ ...scope, x: prevX }); } catch { prevY = NaN; }
    for (let i = 1; i <= samples; i++) {
      const curX = view.xMin + i * dx; let curY;
      try { curY = node.evaluate({ ...scope, x: curX }); } catch { curY = NaN; }
      if (isFinite(prevY) && isFinite(curY) && prevY * curY < 0 && Math.abs(curY - prevY) < view.yMax - view.yMin) {
        let a = prevX, b = curX, fa = prevY;
        for (let k = 0; k < 40; k++) {
          const mid = (a + b) / 2; let fm;
          try { fm = node.evaluate({ ...scope, x: mid }); } catch { fm = NaN; }
          if (fa * fm <= 0) b = mid; else { a = mid; fa = fm; }
        }
        roots.push((a + b) / 2);
      }
      prevX = curX; prevY = curY;
    }
    return roots;
  }, [view]);

  // ====== [Phase 5] 일반 함수 y=f(x) 그리기 ======
  const drawFunction = (ctx, body, color, scope) => {
    const node = math.compile(body);
    ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.beginPath();
    let started = false, prevY = null;
    for (let px = 0; px <= size.w; px++) {
      const xVal = toMathX(px); let yVal;
      try { yVal = node.evaluate({ ...scope, x: xVal }); } catch { yVal = NaN; }
      if (typeof yVal !== "number" || !isFinite(yVal)) { started = false; prevY = null; continue; }
      const py = toPxY(yVal);
      if (prevY !== null && Math.abs(py - prevY) > size.h * 1.5) started = false;
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
      prevY = py;
    }
    ctx.stroke();
    // 근 + y절편 표시
    ctx.fillStyle = "#777";
    findRoots(node, scope).forEach((rx) => { ctx.beginPath(); ctx.arc(toPxX(rx), toPxY(0), 4, 0, Math.PI * 2); ctx.fill(); });
    try {
      const yInt = node.evaluate({ ...scope, x: 0 });
      if (isFinite(yInt) && yInt >= view.yMin && yInt <= view.yMax) { ctx.beginPath(); ctx.arc(toPxX(0), toPxY(yInt), 4, 0, Math.PI * 2); ctx.fill(); }
    } catch {}
  };

  // ====== [Phase 9] 접선 + 접점 + 기울기 라벨 그리기 ======
  const drawTangent = (ctx, body, color, scope, tangentX) => {
    const node = math.compile(body);
    let y0, slope;
    try { y0 = node.evaluate({ ...scope, x: tangentX }); } catch { return; }
    if (!isFinite(y0)) return;
    slope = numDeriv(node, tangentX, scope); // 그 점의 순간 기울기
    if (!isFinite(slope)) return;

    // 접선의 식: y = slope·(x - tangentX) + y0
    // 화면 좌우 끝까지 직선을 그림
    ctx.strokeStyle = "#fa7e19"; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    ctx.beginPath();
    const yL = slope * (view.xMin - tangentX) + y0;
    const yR = slope * (view.xMax - tangentX) + y0;
    ctx.moveTo(toPxX(view.xMin), toPxY(yL));
    ctx.lineTo(toPxX(view.xMax), toPxY(yR));
    ctx.stroke();
    ctx.setLineDash([]);

    // 접점 (큰 점)
    const px = toPxX(tangentX), py = toPxY(y0);
    ctx.fillStyle = "#fa7e19";
    ctx.beginPath(); ctx.arc(px, py, 7, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.beginPath(); ctx.arc(px, py, 3, 0, Math.PI * 2); ctx.fill();

    // 기울기 라벨 (말풍선)
    const label = `기울기 = ${formatNum(slope)}`;
    ctx.font = "13px sans-serif";
    const tw = ctx.measureText(label).width;
    let bx = px + 12, by = py - 30;
    if (bx + tw + 14 > size.w) bx = px - tw - 26;
    if (by < 0) by = py + 12;
    ctx.fillStyle = "rgba(250,126,25,0.92)";
    ctx.fillRect(bx, by, tw + 14, 22);
    ctx.fillStyle = "#fff";
    ctx.fillText(label, bx + 7, by + 15);
  };

  // ====== [Phase 9] 도함수 곡선 그리기 (점선) ======
  // 모든 x에서 기울기를 구해 이으면 그게 도함수 f'(x)의 그래프
  const drawDerivative = (ctx, body, color, scope) => {
    const node = math.compile(body);
    ctx.strokeStyle = color; ctx.lineWidth = 1.8; ctx.setLineDash([2, 4]); // 가는 점선
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    let started = false, prevY = null;
    for (let px = 0; px <= size.w; px++) {
      const xVal = toMathX(px);
      const slope = numDeriv(node, xVal, scope);
      if (!isFinite(slope)) { started = false; prevY = null; continue; }
      const py = toPxY(slope);
      if (prevY !== null && Math.abs(py - prevY) > size.h * 1.5) started = false;
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
      prevY = py;
    }
    ctx.stroke();
    ctx.setLineDash([]); ctx.globalAlpha = 1;
  };

  // ====== [Phase 10] 적분 시각화: 넓이 색칠 + 리만 합 직사각형 ======
  // 구간 [a,b]에서 곡선 아래 넓이를 보여주고, n개의 직사각형으로 근사합니다.
  // n을 키울수록 직사각형 합(리만 합)이 실제 적분값에 가까워집니다.
  const drawIntegral = (ctx, body, color, scope, a, b, n) => {
    const node = math.compile(body);
    if (a >= b || n < 1) return null;
    const dx = (b - a) / n;
    let riemannSum = 0;

    // 1) 직사각형들 (중점법: 칸 중앙의 함수값을 높이로)
    for (let i = 0; i < n; i++) {
      const xLeft = a + i * dx;
      const xMid = xLeft + dx / 2;
      let h;
      try { h = node.evaluate({ ...scope, x: xMid }); } catch { continue; }
      if (!isFinite(h)) continue;
      riemannSum += h * dx;

      // 직사각형 그리기 (반투명 채움 + 테두리)
      const pxL = toPxX(xLeft), pxR = toPxX(xLeft + dx);
      const py0 = toPxY(0), pyH = toPxY(h);
      ctx.fillStyle = color + "33";   // 약 20% 투명
      ctx.fillRect(pxL, py0, pxR - pxL, pyH - py0);
      ctx.strokeStyle = color + "99"; // 테두리는 더 진하게
      ctx.lineWidth = 1;
      ctx.strokeRect(pxL, py0, pxR - pxL, pyH - py0);
    }

    // 2) 정확한 적분값 (아주 잘게 나눈 합으로 근사)
    let exact = 0;
    const fineN = 2000, fineDx = (b - a) / fineN;
    for (let i = 0; i < fineN; i++) {
      const xMid = a + (i + 0.5) * fineDx;
      try { const v = node.evaluate({ ...scope, x: xMid }); if (isFinite(v)) exact += v * fineDx; } catch {}
    }

    // 구간 경계선 (세로 점선)
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.setLineDash([4, 3]);
    [a, b].forEach((xv) => {
      ctx.beginPath(); ctx.moveTo(toPxX(xv), 0); ctx.lineTo(toPxX(xv), size.h); ctx.stroke();
    });
    ctx.setLineDash([]);

    return { riemannSum, exact }; // 패널에 표시하기 위해 반환
  };

  // ====== [Phase 5] 점 그리기 ======
  const drawPoints = (ctx, points, color) => {
    ctx.fillStyle = color;
    points.forEach(([x, y]) => {
      const px = toPxX(x), py = toPxY(y);
      ctx.beginPath(); ctx.arc(px, py, 6, 0, Math.PI * 2); ctx.fill();
      // 좌표 라벨
      ctx.font = "12px sans-serif"; ctx.fillStyle = "#333";
      ctx.fillText(`(${formatNum(x)}, ${formatNum(y)})`, px + 9, py - 6);
      ctx.fillStyle = color;
    });
  };

  // ====== [Phase 8] 극좌표 그리기: r = f(θ) ======
  // θ를 0부터 2π(또는 그 이상)까지 돌리며 각도마다 반지름 r을 구하고,
  // (r·cosθ, r·sinθ)로 화면 좌표로 바꿔 점을 이어 곡선을 그립니다.
  const drawPolar = (ctx, body, color, scope) => {
    const node = math.compile(body);
    ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.beginPath();
    const TWO_PI = Math.PI * 2;
    // 장미·나선 곡선은 한 바퀴로 안 닫힐 수 있어 넉넉히 4바퀴까지 그림
    const maxTheta = TWO_PI * 4;
    const stepsPerTurn = 360; // 한 바퀴를 360등분 (매끄럽게)
    const dTheta = TWO_PI / stepsPerTurn;
    let started = false;
    for (let theta = 0; theta <= maxTheta; theta += dTheta) {
      let r;
      try { r = node.evaluate({ ...scope, theta }); } catch { r = NaN; }
      if (!isFinite(r)) { started = false; continue; }
      // 극좌표 → 직교좌표 변환
      const x = r * Math.cos(theta), y = r * Math.sin(theta);
      const px = toPxX(x), py = toPxY(y);
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
    }
    ctx.stroke();
  };

  // ====== [Phase 8] 매개변수 그리기: (x(t), y(t)) ======
  // 매개변수 t를 일정 범위로 돌리며 x좌표와 y좌표를 각각 계산해 점을 잇습니다.
  const drawParametric = (ctx, xBody, yBody, color, scope) => {
    const xNode = math.compile(xBody), yNode = math.compile(yBody);
    ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.beginPath();
    const tMin = -Math.PI * 2, tMax = Math.PI * 2; // t 범위 (필요시 조정 가능)
    const steps = 1000;
    const dt = (tMax - tMin) / steps;
    let started = false, prevPx = null, prevPy = null;
    for (let t = tMin; t <= tMax; t += dt) {
      let x, y;
      try { x = xNode.evaluate({ ...scope, t }); y = yNode.evaluate({ ...scope, t }); }
      catch { started = false; continue; }
      if (!isFinite(x) || !isFinite(y)) { started = false; continue; }
      const px = toPxX(x), py = toPxY(y);
      // 화면 밖으로 크게 튀면 선을 끊음
      if (prevPx !== null && (Math.abs(px - prevPx) > size.w * 2 || Math.abs(py - prevPy) > size.h * 2)) started = false;
      if (!started) { ctx.moveTo(px, py); started = true; } else ctx.lineTo(px, py);
      prevPx = px; prevPy = py;
    }
    ctx.stroke();
  };

  // ====== [Phase 5] 음함수 그리기 (마칭 스퀘어) ======
  // F(x,y)=lhs-rhs 가 0이 되는 곡선을 격자를 훑어가며 찾습니다.
  const drawImplicit = (ctx, lhs, rhs, color, scope) => {
    const node = math.compile(`(${lhs})-(${rhs})`);
    const N = 150; // 격자 해상도 (높을수록 매끄럽지만 느려짐)
    const dx = (view.xMax - view.xMin) / N;
    const dy = (view.yMax - view.yMin) / N;

    // 모든 격자점에서 F값을 미리 계산해 2차원 배열에 저장
    const F = [];
    for (let j = 0; j <= N; j++) {
      F[j] = [];
      for (let i = 0; i <= N; i++) {
        const x = view.xMin + i * dx, y = view.yMin + j * dy;
        let v; try { v = node.evaluate({ ...scope, x, y }); } catch { v = NaN; }
        F[j][i] = v;
      }
    }

    ctx.strokeStyle = color; ctx.lineWidth = 2.5; ctx.beginPath();
    // 두 격자점 사이에서 F=0이 되는 위치를 비례로 추정(선형 보간)
    const interp = (xa, ya, va, xb, yb, vb) => {
      const t = va / (va - vb); // va와 vb 사이에서 0이 되는 비율
      return [xa + t * (xb - xa), ya + t * (yb - ya)];
    };

    for (let j = 0; j < N; j++) {
      for (let i = 0; i < N; i++) {
        const x0 = view.xMin + i * dx, x1 = x0 + dx;
        const y0 = view.yMin + j * dy, y1 = y0 + dy;
        const v00 = F[j][i], v10 = F[j][i + 1], v01 = F[j + 1][i], v11 = F[j + 1][i + 1];
        if (![v00, v10, v01, v11].every(isFinite)) continue;

        // 칸의 네 변 중 F부호가 바뀌는 변에서 교점을 구함
        const pts = [];
        if (v00 * v10 < 0) pts.push(interp(x0, y0, v00, x1, y0, v10)); // 아래변
        if (v10 * v11 < 0) pts.push(interp(x1, y0, v10, x1, y1, v11)); // 오른변
        if (v01 * v11 < 0) pts.push(interp(x0, y1, v01, x1, y1, v11)); // 위변
        if (v00 * v01 < 0) pts.push(interp(x0, y0, v00, x0, y1, v01)); // 왼변

        // 보통 교점은 2개 → 둘을 선분으로 이으면 곡선 조각이 됨
        if (pts.length >= 2) {
          ctx.moveTo(toPxX(pts[0][0]), toPxY(pts[0][1]));
          ctx.lineTo(toPxX(pts[1][0]), toPxY(pts[1][1]));
        }
      }
    }
    ctx.stroke();
  };

  // ====== [Phase 5] 부등식 영역 색칠 ======
  // 화면을 픽셀 블록 단위로 훑어 조건을 만족하는 칸을 반투명색으로 칠합니다.
  const drawInequality = (ctx, lhs, op, rhs, color, scope) => {
    const node = math.compile(`(${lhs})-(${rhs})`); // 부등식을 한쪽으로 모음
    const step = 4; // 4픽셀마다 검사 (성능 위해 약간 거칠게)
    ctx.fillStyle = color + "33"; // 끝의 33은 약 20% 투명도
    for (let px = 0; px < size.w; px += step) {
      for (let py = 0; py < size.h; py += step) {
        const x = toMathX(px + step / 2), y = toMathY(py + step / 2);
        let diff; try { diff = node.evaluate({ ...scope, x, y }); } catch { continue; }
        if (!isFinite(diff)) continue;
        // op에 따라 조건 만족 여부 판정 (lhs-rhs 부호로 비교)
        let ok = false;
        if (op === ">" || op === ">=") ok = diff > 0;
        else ok = diff < 0;
        if (ok) ctx.fillRect(px, py, step, step);
      }
    }
    // 경계선도 함께 그려 영역 테두리를 명확히
    drawImplicit(ctx, lhs, rhs, color, scope);
  };

  // ====== 전체 그리기 ======
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size.w * dpr; canvas.height = size.h * dpr;
    canvas.style.width = size.w + "px"; canvas.style.height = size.h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size.w, size.h);
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, size.w, size.h);

    const xStep = niceStep(view.xMax - view.xMin, 10);
    const yStep = niceStep(view.yMax - view.yMin, 10);
    const scope = sliderValues();

    // 격자
    ctx.lineWidth = 1; ctx.strokeStyle = "#e8e8e8"; ctx.font = "12px sans-serif";
    for (let x = Math.ceil(view.xMin / xStep) * xStep; x <= view.xMax; x += xStep) {
      const px = toPxX(x); ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, size.h); ctx.stroke();
    }
    for (let y = Math.ceil(view.yMin / yStep) * yStep; y <= view.yMax; y += yStep) {
      const py = toPxY(y); ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(size.w, py); ctx.stroke();
    }
    // 축
    ctx.strokeStyle = "#888"; ctx.lineWidth = 1.5;
    const x0 = toPxX(0), y0 = toPxY(0);
    ctx.beginPath(); ctx.moveTo(0, y0); ctx.lineTo(size.w, y0); ctx.moveTo(x0, 0); ctx.lineTo(x0, size.h); ctx.stroke();
    ctx.fillStyle = "#333";
    for (let x = Math.ceil(view.xMin / xStep) * xStep; x <= view.xMax; x += xStep) {
      if (Math.abs(x) < xStep / 2) continue; ctx.fillText(formatNum(x), toPxX(x) + 3, y0 - 4);
    }
    for (let y = Math.ceil(view.yMin / yStep) * yStep; y <= view.yMax; y += yStep) {
      if (Math.abs(y) < yStep / 2) continue; ctx.fillText(formatNum(y), x0 + 4, toPxY(y) - 3);
    }

    // [Phase 5] 타입별로 그리기
    const newIntegralResults = {}; // [Phase 10] 이번 그리기의 적분 결과 모음
    rows.forEach((row) => {
      if (!row.visible || !row.expr.trim() || row.error) return;
      const info = classify(row.expr);
      try {
        if (info.type === "function") {
          // [Phase 10] 적분 영역을 먼저 깔고(곡선 뒤), 그 위에 곡선을 그림
          if (row.showIntegral) {
            const res = drawIntegral(ctx, info.body, row.color, scope, row.intA, row.intB, row.intN);
            if (res) newIntegralResults[row.id] = res;
          }
          drawFunction(ctx, info.body, row.color, scope);
          // [Phase 9] 이 줄에 미분 옵션이 켜져 있으면 추가로 그림
          if (row.showDeriv) drawDerivative(ctx, info.body, row.color, scope);
          if (row.showTangent) drawTangent(ctx, info.body, row.color, scope, row.tangentX);
        }
        else if (info.type === "point") drawPoints(ctx, info.points, row.color);
        else if (info.type === "implicit") drawImplicit(ctx, info.lhs, info.rhs, row.color, scope);
        else if (info.type === "inequality") drawInequality(ctx, info.lhs, info.op, info.rhs, row.color, scope);
        else if (info.type === "polar") drawPolar(ctx, info.body, row.color, scope);
        else if (info.type === "parametric") drawParametric(ctx, info.xBody, info.yBody, row.color, scope);
      } catch {}
    });

    // [Phase 6] 데이터 표의 점들 그리기 (주황색 점)
    const tpts = tablePoints();
    const tableColor = "#fa7e19";
    tpts.forEach(([x, y]) => {
      ctx.fillStyle = tableColor;
      ctx.beginPath();
      ctx.arc(toPxX(x), toPxY(y), 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 1.5; ctx.stroke();
    });

    // [Phase 6] 회귀선 그리기 (점선)
    if (showRegression) {
      const reg = regression();
      if (reg) {
        ctx.strokeStyle = tableColor; ctx.lineWidth = 2;
        ctx.setLineDash([8, 5]); // 점선 패턴
        ctx.beginPath();
        // 화면 좌우 끝까지 직선 y=mx+b 를 그림
        const y1 = reg.m * view.xMin + reg.b;
        const y2 = reg.m * view.xMax + reg.b;
        ctx.moveTo(toPxX(view.xMin), toPxY(y1));
        ctx.lineTo(toPxX(view.xMax), toPxY(y2));
        ctx.stroke();
        ctx.setLineDash([]); // 점선 해제 (다른 그리기에 영향 없게)
      }
    }

    // 마우스 좌표 추적 (일반 함수에만 스냅)
    if (hover) {
      const mathX = toMathX(hover.x);
      let snapped = null;
      for (const row of rows) {
        if (!row.visible || !row.expr.trim() || row.error) continue;
        const info = classify(row.expr);
        if (info.type !== "function") continue;
        try {
          const y = math.compile(info.body).evaluate({ ...scope, x: mathX });
          if (isFinite(y)) {
            const py = toPxY(y);
            if (Math.abs(py - hover.y) < 30) { snapped = { x: mathX, y, color: row.color, px: toPxX(mathX), py }; break; }
          }
        } catch {}
      }
      const dotX = snapped ? snapped.px : hover.x, dotY = snapped ? snapped.py : hover.y;
      const labelX = snapped ? snapped.x : mathX, labelY = snapped ? snapped.y : toMathY(hover.y);
      ctx.fillStyle = snapped ? snapped.color : "#333";
      ctx.beginPath(); ctx.arc(dotX, dotY, snapped ? 6 : 4, 0, Math.PI * 2); ctx.fill();
      if (snapped) { ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2); ctx.fill(); }
      const label = `(${formatNum(labelX)}, ${formatNum(labelY)})`;
      ctx.font = "13px sans-serif";
      const tw = ctx.measureText(label).width;
      let bx = dotX + 10, by = dotY - 28;
      if (bx + tw + 12 > size.w) bx = dotX - tw - 22;
      if (by < 0) by = dotY + 10;
      ctx.fillStyle = "rgba(50,50,50,0.9)"; ctx.fillRect(bx, by, tw + 14, 22);
      ctx.fillStyle = "#fff"; ctx.fillText(label, bx + 7, by + 15);
    }

    // [Phase 10] 적분 결과가 바뀌었을 때만 상태 업데이트 (무한 루프 방지)
    setIntegralResults((prev) => {
      const keys = Object.keys(newIntegralResults);
      const prevKeys = Object.keys(prev);
      let changed = keys.length !== prevKeys.length;
      if (!changed) {
        for (const k of keys) {
          if (!prev[k] || Math.abs(prev[k].riemannSum - newIntegralResults[k].riemannSum) > 1e-9 || Math.abs(prev[k].exact - newIntegralResults[k].exact) > 1e-9) {
            changed = true; break;
          }
        }
      }
      return changed ? newIntegralResults : prev;
    });
  }, [rows, view, size, hover, sliders, sliderValues, toPxX, toPxY, toMathX, toMathY, findRoots, tablePoints, regression, showRegression]);

  useEffect(() => { draw(); }, [draw]);

  useEffect(() => {
    const anyPlaying = Object.values(sliders).some((s) => s.playing);
    if (!anyPlaying) { if (animRef.current) { cancelAnimationFrame(animRef.current); animRef.current = null; } return; }
    const dir = {}; Object.keys(sliders).forEach((k) => (dir[k] = 1));
    const tick = () => {
      setSliders((prev) => {
        const next = { ...prev };
        Object.entries(next).forEach(([k, s]) => {
          if (!s.playing) return;
          let v = s.value + dir[k] * s.step;
          if (v >= s.max) { v = s.max; dir[k] = -1; } else if (v <= s.min) { v = s.min; dir[k] = 1; }
          next[k] = { ...s, value: parseFloat(v.toFixed(4)) };
        });
        return next;
      });
      animRef.current = requestAnimationFrame(tick);
    };
    animRef.current = requestAnimationFrame(tick);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [sliders]);

  // ====== 수식 입력 처리 (타입별 검증) ======
  const updateLatex = useCallback((id, latex) => {
    setRows((prev) =>
      prev.map((r) => {
        if (r.id !== id) return r;
        const expr = latexToMath(latex);
        let error = null;
        if (expr.trim()) {
          const info = classify(expr);
          try {
            const scope = { x: 1, y: 1, t: 1, theta: 1 };
            if (info.type === "function") { extractVars(info.body).forEach((v) => (scope[v] = 1)); math.compile(info.body).evaluate(scope); }
            else if (info.type === "implicit") { math.compile(`(${info.lhs})-(${info.rhs})`).evaluate(scope); }
            else if (info.type === "inequality") { math.compile(`(${info.lhs})-(${info.rhs})`).evaluate(scope); }
            else if (info.type === "point") { if (!info.points.length) error = "수식 오류"; }
            else if (info.type === "polar") { math.compile(info.body).evaluate(scope); }
            else if (info.type === "parametric") { math.compile(info.xBody).evaluate(scope); math.compile(info.yBody).evaluate(scope); }
          } catch { error = "수식 오류"; }
        }
        return { ...r, latex, expr, error };
      })
    );
  }, []);

  const addRow = () => setRows((prev) => [...prev, makeRow(nextId.current++)]);
  const removeRow = (id) => setRows((prev) => prev.filter((r) => r.id !== id));
  const toggleVisible = (id) => setRows((prev) => prev.map((r) => (r.id === id ? { ...r, visible: !r.visible } : r)));
  // [Phase 9] 함수 줄의 미분 옵션 변경
  const updateRowField = (id, field, value) =>
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  const setSliderValue = (name, value) => {
    emitInteraction("param_change", { name, value }); // 학습 로그: 파라미터 탐구 신호
    setSliders((prev) => ({ ...prev, [name]: { ...prev[name], value } }));
  };
  const setSliderRange = (name, key, value) => setSliders((prev) => ({ ...prev, [name]: { ...prev[name], [key]: value } }));
  const togglePlay = (name) =>
    setSliders((prev) => {
      const playing = !prev[name].playing;
      emitInteraction("param_play", { name, playing }); // 학습 로그: 애니메이션 재생/정지
      return { ...prev, [name]: { ...prev[name], playing } };
    });

  // [Phase 6] 표 조작 함수들
  const updateCell = (idx, key, val) =>
    setTable((prev) => prev.map((r, i) => (i === idx ? { ...r, [key]: val } : r)));
  const addTableRow = () => setTable((prev) => [...prev, { x: "", y: "" }]);
  const removeTableRow = (idx) => setTable((prev) => prev.filter((_, i) => i !== idx));
  const clearTable = () => setTable([{ x: "", y: "" }]);

  const handleWheel = (e) => {
    e.preventDefault();
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const factor = e.deltaY > 0 ? 1.1 : 0.9;
    const cx = toMathX(mx), cy = toMathY(my);
    setView((v) => ({ xMin: cx + (v.xMin - cx) * factor, xMax: cx + (v.xMax - cx) * factor, yMin: cy + (v.yMin - cy) * factor, yMax: cy + (v.yMax - cy) * factor }));
  };
  const handleMouseDown = (e) => (dragRef.current = { startX: e.clientX, startY: e.clientY, view: { ...view } });
  const handleMouseMove = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    if (dragRef.current) {
      const d = dragRef.current;
      const dxMath = ((e.clientX - d.startX) / size.w) * (d.view.xMax - d.view.xMin);
      const dyMath = ((e.clientY - d.startY) / size.h) * (d.view.yMax - d.view.yMin);
      setView({ xMin: d.view.xMin - dxMath, xMax: d.view.xMax - dxMath, yMin: d.view.yMin + dyMath, yMax: d.view.yMax + dyMath });
      setHover(null);
    } else setHover({ x: mx, y: my });
  };
  const handleMouseUp = () => (dragRef.current = null);
  const handleMouseLeave = () => { dragRef.current = null; setHover(null); };
  const resetView = () => setView({ xMin: -10, xMax: 10, yMin: -10, yMax: 10 });
  const exportPNG = () => {
    setHover(null);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const url = canvasRef.current.toDataURL("image/png");
      const a = document.createElement("a"); a.href = url; a.download = "graph.png"; a.click();
    }));
  };

  // ====== [Phase 7] 현재 상태를 하나의 객체로 모으기 ======
  // 함수·슬라이더·표·화면범위를 묶어 저장 단위로 만듦
  const collectState = () => ({
    version: 1,
    rows: rows.map((r) => ({ latex: r.latex, expr: r.expr, color: r.color, visible: r.visible, showTangent: r.showTangent, tangentX: r.tangentX, showDeriv: r.showDeriv, showIntegral: r.showIntegral, intA: r.intA, intB: r.intB, intN: r.intN })),
    sliders,
    table,
    view,
    showRegression,
  });

  // 저장된 상태를 화면에 다시 적용
  const applyState = (st) => {
    if (!st) return false;
    // [Phase 13] 확률 시뮬 상태 — rows 없이 simExperiment/simTrials만 적용.
    if (st.simulationMode) {
      setSimMode(true);
      setMode3D(false);
      if (typeof st.experiment === "string" && st.experiment.trim()) setSimExperiment(st.experiment);
      if (typeof st.trials === "number") setSimTrials(st.trials);
      setSimOutcomes(Array.isArray(st.outcomes) ? st.outcomes : null); // 구조화 outcomes 통과
      setSimCounts(null); // 새 명세 적용 시 이전 결과 초기화
      return true;
    }
    // [Phase 11] 3D 곡면 상태(곡면식) — rows 없이 mode3D/expr3D/range3D만 적용.
    if (st.mode3D) {
      setMode3D(true);
      setSimMode(false);
      if (typeof st.expr3D === "string" && st.expr3D.trim()) setExpr3D(st.expr3D);
      if (typeof st.range3D === "number") setRange3D(st.range3D);
      return true;
    }
    if (!st.rows) return false;
    // 불러온 함수에 새 id를 부여하며 복원
    const restored = st.rows.map((r, i) => ({
      id: i + 1, latex: r.latex || "", expr: r.expr || "",
      color: r.color || COLORS[i % COLORS.length],
      visible: r.visible !== false, error: null,
      showTangent: r.showTangent || false, tangentX: r.tangentX ?? 1, showDeriv: r.showDeriv || false,
      showIntegral: r.showIntegral || false, intA: r.intA ?? 0, intB: r.intB ?? 3, intN: r.intN ?? 10,
    }));
    nextId.current = restored.length + 1;
    setRows(restored.length ? restored : [makeRow(1)]);
    setSliders(st.sliders || {});
    setTable(st.table || [{ x: "", y: "" }]);
    if (st.view) setView(st.view);
    if (typeof st.showRegression === "boolean") setShowRegression(st.showRegression);
    setMode3D(false); // 2D 명세 적용 시 3D 모드 해제(잔류 방지)
    setSimMode(false); // 2D 명세 적용 시 시뮬 모드 해제(잔류 방지)
    return true;
  };

  // ====== [코어 연동] Graph2dSpec 소비 — ?spec= URL + window.whymathApplySpec() 훅 ======
  // 코어(L1-L4)의 선언적 Graph2dSpec을 L5(이 도구)가 *소비*만 한다(표현≠의미: 구조를 받아 렌더).
  // 두 경로: (1) ?spec=<base64(JSON)> 진입 URL, (2) 전역 훅 window.whymathApplySpec(raw) —
  // Flutter WebView는 쿼리스트링을 못 싣는 loadFlutterAsset를 쓰므로 onPageFinished에서 이 훅을
  // runJavaScript로 호출해 명세를 주입한다. raw는 base64(JSON) 또는 raw JSON 모두 허용(parseSpecParam).
  useEffect(() => {
    // base64(JSON)/raw JSON 문자열을 받아 계산기 상태로 적용(잘못된 입력은 무시·false 반환).
    const apply = (raw) => {
      try {
        const parsed = parseSpecParam(raw);
        if (!parsed) return false;
        // 렌더 선택 단일 진실원(invariant ⑩): {type, spec} 봉투면 type을 우선 신뢰(코어 권위),
        // 레거시 spec-only(공개 ?spec= 공유 링크)면 type=null로 와서 기존 shape 폴백.
        const { type, spec } = unwrapSpecEnvelope(parsed);
        const st = specToStateForType(type, spec);
        if (!st) return false;
        applyState(st);
        return true;
      } catch {
        return false;
      }
    };
    // (2) 전역 훅 등록 — Flutter WebView/외부 호스트가 마운트 후 명세를 주입.
    if (typeof window !== "undefined") window.whymathApplySpec = apply;
    // (1) ?spec= 진입 URL 자동 소비.
    try {
      if (typeof window !== "undefined" && window.location) {
        apply(new URLSearchParams(window.location.search).get("spec"));
      }
    } catch {
      /* 잘못된 spec은 조용히 무시(기본 빈 계산기로 시작) */
    }
    return () => {
      // 언마운트 시 이 인스턴스가 등록한 훅만 해제(다른 인스턴스 덮어쓰지 않음).
      if (typeof window !== "undefined" && window.whymathApplySpec === apply) {
        delete window.whymathApplySpec;
      }
    };
    // 마운트 1회만 — URL은 진입 시점 고정
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ====== [Phase 7-A] JSON 파일로 내보내기 ======
  const exportJSON = () => {
    const data = JSON.stringify(collectState(), null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "graph-state.json"; a.click();
    URL.revokeObjectURL(url);
  };

  // ====== [Phase 7-A] JSON 파일 가져오기 ======
  const importJSON = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const st = JSON.parse(reader.result);
        if (applyState(st)) setSaveStatus("파일을 불러왔습니다");
        else setSaveStatus("올바른 형식이 아닙니다");
      } catch {
        setSaveStatus("파일을 읽을 수 없습니다");
      }
      setTimeout(() => setSaveStatus(""), 2500);
    };
    reader.readAsText(file);
    e.target.value = ""; // 같은 파일 다시 선택 가능하게 초기화
  };

  // ====== [Phase 7-B] 코어 Graph2dSpec 명세 내보내기/붙여넣기 ======
  // 계산기 상태 → 코어 선언적 명세(JSON). 백엔드·문항·공유 링크로 보낼 수 있다("표현≠의미" 양방향).
  const exportSpec = () => {
    const spec = calcStateToGraph2dSpec({ rows, sliders, view });
    if (!spec) {
      setSaveStatus("내보낼 함수가 없습니다");
      setTimeout(() => setSaveStatus(""), 2500);
      return;
    }
    const json = JSON.stringify(spec, null, 2);
    setSpecText(json);
    try { navigator.clipboard?.writeText(json); } catch { /* 클립보드 미지원 — 칸에는 채워짐 */ }
    setSaveStatus("명세를 복사했습니다");
    setTimeout(() => setSaveStatus(""), 2500);
  };

  // 붙여넣은 Graph2dSpec JSON을 파싱해 그래프로 적용(graph2dSpecToState 경유).
  const applySpec = () => {
    const spec = parseSpecParam(specText);
    const st = spec && graph2dSpecToState(spec);
    if (st && applyState(st)) setSaveStatus("명세를 적용했습니다");
    else setSaveStatus("올바른 Graph2dSpec JSON이 아닙니다");
    setTimeout(() => setSaveStatus(""), 2500);
  };

  // ====== [Phase 7-B] 영구 저장소에 이름 붙여 저장 (브라우저 닫아도 유지) ======
  const STORAGE_PREFIX = "graph:";
  // 저장된 목록 새로고침
  const refreshSavedList = useCallback(async () => {
    try {
      const res = await window.storage.list(STORAGE_PREFIX);
      const names = (res?.keys || []).map((k) => k.replace(STORAGE_PREFIX, ""));
      setSavedList(names);
    } catch {
      setSavedList([]); // storage 미지원 환경이면 빈 목록
    }
  }, []);

  // 컴포넌트 처음 뜰 때 저장 목록 한 번 불러옴
  useEffect(() => { refreshSavedList(); }, [refreshSavedList]);

  const saveNamed = async () => {
    const name = window.prompt("저장할 이름을 입력하세요", "내 그래프");
    if (!name) return;
    try {
      await window.storage.set(STORAGE_PREFIX + name, JSON.stringify(collectState()));
      await refreshSavedList();
      setSaveStatus(`"${name}" 저장됨`);
    } catch {
      setSaveStatus("저장 실패 (이 환경은 영구저장 미지원)");
    }
    setTimeout(() => setSaveStatus(""), 2500);
  };

  const loadNamed = async (name) => {
    try {
      const res = await window.storage.get(STORAGE_PREFIX + name);
      if (res?.value) {
        applyState(JSON.parse(res.value));
        setSaveStatus(`"${name}" 불러옴`);
      }
    } catch {
      setSaveStatus("불러오기 실패");
    }
    setTimeout(() => setSaveStatus(""), 2500);
  };

  const deleteNamed = async (name) => {
    try {
      await window.storage.delete(STORAGE_PREFIX + name);
      await refreshSavedList();
    } catch {}
  };

  const sliderNames = Object.keys(sliders).sort();

  // [Phase 13] 시뮬 모드면 확률 시뮬 화면 전체 표시 (동전·주사위 Monte Carlo)
  if (simMode) {
    return (
      <SimulationView
        experiment={simExperiment}
        setExperiment={setSimExperiment}
        trials={simTrials}
        setTrials={setSimTrials}
        counts={simCounts}
        outcomes={simOutcomes}
        onRun={() => {
          // 구조화 outcomes 우선, 없으면 키워드 파싱.
          const m = modelFromOutcomes(simOutcomes) || parseExperiment(simExperiment);
          setSimCounts(m ? runTrials(m, simTrials) : null);
          // 학습 로그(E 파이프라인) — 시뮬 실행도 조작 신호로 영속(F).
          emitInteraction("sim_run", {
            experiment: simExperiment,
            trials: simTrials,
            outcomes: !!simOutcomes,
          });
        }}
        onBack={() => setSimMode(false)}
      />
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "'Georgia', serif", background: "#fafafa" }}>
      <div style={{ width: 360, background: "#fff", borderRight: "1px solid #ddd", display: "flex", flexDirection: "column", boxShadow: "2px 0 8px rgba(0,0,0,0.04)" }}>
        <div style={{ padding: "18px 20px", borderBottom: "1px solid #eee", display: "flex", alignItems: "center" }}>
          <span style={{ fontSize: 20, fontWeight: "bold", letterSpacing: "-0.5px" }}>그래프 계산기</span>
          {/* [Phase 11] 2D/3D 전환 */}
          <div style={{ marginLeft: "auto", display: "flex", gap: 6, alignItems: "center" }}>
            <div style={{ display: "flex", border: "1px solid #ddd", borderRadius: 8, overflow: "hidden" }}>
              <button onClick={() => setMode3D(false)} style={{ padding: "5px 12px", border: "none", background: !mode3D ? "#2d70b3" : "#fff", color: !mode3D ? "#fff" : "#666", cursor: "pointer", fontSize: 13 }}>2D</button>
              <button onClick={() => setMode3D(true)} style={{ padding: "5px 12px", border: "none", background: mode3D ? "#2d70b3" : "#fff", color: mode3D ? "#fff" : "#666", cursor: "pointer", fontSize: 13 }}>3D</button>
            </div>
            <button onClick={() => setSimMode(true)} style={{ padding: "5px 12px", border: "1px solid #8456c9", borderRadius: 8, background: "#8456c9", color: "#fff", cursor: "pointer", fontSize: 13 }}>시뮬</button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {mode3D ? (
            /* [Phase 11] 3D 모드 입력 패널 */
            <div style={{ padding: "16px" }}>
              <div style={{ fontSize: 13, color: "#999", marginBottom: 8, fontWeight: "bold" }}>3D 곡면 z = f(x, y)</div>
              <input
                value={expr3D}
                onChange={(e) => {
                  emitInteraction("surface_change", { expr: e.target.value }); // 학습 로그: 3D 곡면식 변경
                  setExpr3D(e.target.value);
                }}
                placeholder="예: x^2 + y^2"
                style={{ width: "100%", fontSize: 16, padding: "8px 10px", border: "1px solid #ddd", borderRadius: 6, fontFamily: "monospace", boxSizing: "border-box" }}
              />
              <div style={{ marginTop: 12, fontSize: 13, color: "#666" }}>
                정의역 범위: ±{range3D}
                <input type="range" min={1} max={10} step={1} value={range3D} onChange={(e) => { const r = parseInt(e.target.value); emitInteraction("surface_range", { range: r }); setRange3D(r); }} style={{ width: "100%", accentColor: "#2d70b3", marginTop: 4 }} />
              </div>
              <div style={{ marginTop: 16, fontSize: 12, color: "#999", lineHeight: 1.7 }}>
                <b>조작:</b> 드래그=회전 · 휠=확대/축소
                <br /><b>예시 식:</b>
                <br />• x^2 + y^2 (그릇 모양)
                <br />• x^2 - y^2 (안장면)
                <br />• sin(x) * cos(y) (물결)
                <br />• sin(sqrt(x^2+y^2)) (잔물결)
                <br />• x * y / 4 (꼬인 면)
                <br /><br />색은 높이를 나타냅니다 (파랑=낮음, 빨강=높음).
              </div>
            </div>
          ) : (
          <>
          {rows.map((row, idx) => {
            const info = classify(row.expr);
            const isFunc = info.type === "function" && !row.error && row.expr.trim();
            return (
              <div key={row.id} style={{ borderBottom: "1px solid #f2f2f2" }}>
                <div style={{ display: "flex", alignItems: "center", padding: "10px 12px", gap: 8 }}>
                  <button onClick={() => toggleVisible(row.id)} title="보이기/숨기기" style={{ width: 22, height: 22, borderRadius: "50%", background: row.visible ? row.color : "#fff", border: `2px solid ${row.color}`, cursor: "pointer", flexShrink: 0 }} />
                  <span style={{ color: "#999", fontSize: 13, minWidth: 30 }}>f{idx + 1} =</span>
                  <MathField value={row.latex} onChange={(latex) => updateLatex(row.id, latex)} color={row.color} error={row.error} />
                  {rows.length > 1 && (<button onClick={() => removeRow(row.id)} style={{ border: "none", background: "none", color: "#bbb", cursor: "pointer", fontSize: 18, flexShrink: 0 }}>×</button>)}
                </div>

                {/* [Phase 9] 미분 시각화 컨트롤 (일반 함수일 때만) */}
                {isFunc && (
                  <div style={{ padding: "0 12px 10px 52px", display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#666" }}>
                      <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                        <input type="checkbox" checked={row.showTangent} onChange={(e) => updateRowField(row.id, "showTangent", e.target.checked)} style={{ accentColor: "#fa7e19" }} />
                        접선
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                        <input type="checkbox" checked={row.showDeriv} onChange={(e) => updateRowField(row.id, "showDeriv", e.target.checked)} style={{ accentColor: row.color }} />
                        도함수 f'(x)
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                        <input type="checkbox" checked={row.showIntegral} onChange={(e) => updateRowField(row.id, "showIntegral", e.target.checked)} style={{ accentColor: "#388c46" }} />
                        적분(넓이)
                      </label>
                    </div>
                    {/* 접선이 켜지면 접점 위치 슬라이더 표시 */}
                    {row.showTangent && (
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 12, color: "#888", minWidth: 60 }}>x = {formatNum(row.tangentX)}</span>
                        <input type="range" min={view.xMin} max={view.xMax} step={(view.xMax - view.xMin) / 200}
                          value={row.tangentX}
                          onChange={(e) => updateRowField(row.id, "tangentX", parseFloat(e.target.value))}
                          style={{ flex: 1, accentColor: "#fa7e19" }} />
                      </div>
                    )}
                    {/* [Phase 10] 적분이 켜지면 구간·직사각형 개수 컨트롤 */}
                    {row.showIntegral && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 5, marginTop: 2, padding: "8px 10px", background: "#f3f8f4", borderRadius: 6 }}>
                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                          <label style={{ fontSize: 12, color: "#666", display: "flex", alignItems: "center", gap: 4 }}>
                            a=<input type="number" value={row.intA} onChange={(e) => updateRowField(row.id, "intA", parseFloat(e.target.value))} style={{ width: 48, fontSize: 12, padding: "2px 4px", border: "1px solid #ccd", borderRadius: 4 }} />
                          </label>
                          <label style={{ fontSize: 12, color: "#666", display: "flex", alignItems: "center", gap: 4 }}>
                            b=<input type="number" value={row.intB} onChange={(e) => updateRowField(row.id, "intB", parseFloat(e.target.value))} style={{ width: 48, fontSize: 12, padding: "2px 4px", border: "1px solid #ccd", borderRadius: 4 }} />
                          </label>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 12, color: "#888", minWidth: 64 }}>직사각형 {row.intN}개</span>
                          <input type="range" min={1} max={100} step={1} value={row.intN}
                            onChange={(e) => updateRowField(row.id, "intN", parseInt(e.target.value))}
                            style={{ flex: 1, accentColor: "#388c46" }} />
                        </div>
                        {/* 리만 합 결과 vs 실제 적분값 */}
                        {integralResults[row.id] && (
                          <div style={{ fontSize: 12, fontFamily: "monospace", color: "#2e6b3a", lineHeight: 1.6 }}>
                            리만 합 ≈ {formatNum(integralResults[row.id].riemannSum)}
                            <br />
                            실제 적분값 = {formatNum(integralResults[row.id].exact)}
                            <br />
                            <span style={{ color: "#999", fontSize: 11 }}>오차 {formatNum(Math.abs(integralResults[row.id].riemannSum - integralResults[row.id].exact))} (개수 늘리면 줄어듦)</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          <button onClick={addRow} style={{ margin: "12px", padding: "10px", width: "calc(100% - 24px)", border: "1px dashed #bbb", borderRadius: 8, background: "#fafafa", cursor: "pointer", fontSize: 14, color: "#666" }}>+ 함수 추가</button>

          {sliderNames.length > 0 && (
            <div style={{ borderTop: "1px solid #eee", padding: "12px 16px" }}>
              <div style={{ fontSize: 13, color: "#999", marginBottom: 8, fontWeight: "bold" }}>슬라이더 (변수)</div>
              {sliderNames.map((name) => {
                const s = sliders[name];
                return (
                  <div key={name} style={{ marginBottom: 16, padding: "10px 12px", background: "#f9f9f9", borderRadius: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <span style={{ fontFamily: "monospace", fontSize: 16, fontWeight: "bold", minWidth: 20 }}>{name}</span>
                      <span style={{ fontFamily: "monospace", fontSize: 15, color: "#2d70b3" }}>= {formatNum(s.value)}</span>
                      <button onClick={() => togglePlay(name)} title="애니메이션" style={{ marginLeft: "auto", width: 28, height: 28, borderRadius: "50%", border: "1px solid #ccc", background: s.playing ? "#388c46" : "#fff", color: s.playing ? "#fff" : "#555", cursor: "pointer", fontSize: 12 }}>{s.playing ? "❚❚" : "▶"}</button>
                    </div>
                    <input type="range" min={s.min} max={s.max} step={s.step} value={s.value} onChange={(e) => setSliderValue(name, parseFloat(e.target.value))} style={{ width: "100%", accentColor: "#2d70b3" }} />
                    <div style={{ display: "flex", gap: 6, marginTop: 6, fontSize: 11, color: "#888" }}>
                      <label style={{ flex: 1 }}>최소<input type="number" value={s.min} onChange={(e) => setSliderRange(name, "min", parseFloat(e.target.value))} style={{ width: "100%", fontSize: 12, padding: 2, border: "1px solid #ddd", borderRadius: 4 }} /></label>
                      <label style={{ flex: 1 }}>최대<input type="number" value={s.max} onChange={(e) => setSliderRange(name, "max", parseFloat(e.target.value))} style={{ width: "100%", fontSize: 12, padding: 2, border: "1px solid #ddd", borderRadius: 4 }} /></label>
                      <label style={{ flex: 1 }}>간격<input type="number" value={s.step} onChange={(e) => setSliderRange(name, "step", parseFloat(e.target.value) || 0.1)} style={{ width: "100%", fontSize: 12, padding: 2, border: "1px solid #ddd", borderRadius: 4 }} /></label>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* [Phase 6] 데이터 표 + 회귀선 */}
          <div style={{ borderTop: "1px solid #eee", padding: "12px 16px" }}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
              <span style={{ fontSize: 13, color: "#999", fontWeight: "bold" }}>데이터 표 (점 + 회귀선)</span>
              <button onClick={clearTable} style={{ marginLeft: "auto", fontSize: 11, color: "#bbb", border: "none", background: "none", cursor: "pointer" }}>모두 지우기</button>
            </div>

            {/* 표 헤더 */}
            <div style={{ display: "flex", gap: 6, fontSize: 12, color: "#888", marginBottom: 4, paddingLeft: 4 }}>
              <span style={{ flex: 1 }}>x</span>
              <span style={{ flex: 1 }}>y</span>
              <span style={{ width: 20 }}></span>
            </div>

            {/* 표 행들 */}
            {table.map((row, idx) => (
              <div key={idx} style={{ display: "flex", gap: 6, marginBottom: 4, alignItems: "center" }}>
                <input type="number" value={row.x} onChange={(e) => updateCell(idx, "x", e.target.value)} placeholder="0"
                  style={{ flex: 1, fontSize: 14, padding: "4px 6px", border: "1px solid #ddd", borderRadius: 4, fontFamily: "monospace" }} />
                <input type="number" value={row.y} onChange={(e) => updateCell(idx, "y", e.target.value)} placeholder="0"
                  style={{ flex: 1, fontSize: 14, padding: "4px 6px", border: "1px solid #ddd", borderRadius: 4, fontFamily: "monospace" }} />
                <button onClick={() => removeTableRow(idx)} style={{ width: 20, border: "none", background: "none", color: "#ccc", cursor: "pointer", fontSize: 16 }}>×</button>
              </div>
            ))}

            <button onClick={addTableRow} style={{ marginTop: 6, padding: "6px", width: "100%", border: "1px dashed #ddd", borderRadius: 6, background: "#fafafa", cursor: "pointer", fontSize: 13, color: "#888" }}>+ 행 추가</button>

            {/* 회귀선 표시 토글 + 결과 */}
            <label style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10, fontSize: 13, color: "#555", cursor: "pointer" }}>
              <input type="checkbox" checked={showRegression} onChange={(e) => setShowRegression(e.target.checked)} style={{ accentColor: "#fa7e19" }} />
              회귀선 표시 (최적적합 직선)
            </label>

            {/* 회귀 결과 (기울기, 절편, R²) */}
            {(() => {
              const reg = regression();
              if (!reg) return <div style={{ marginTop: 8, fontSize: 12, color: "#bbb" }}>점이 2개 이상이면 회귀선이 계산됩니다.</div>;
              return (
                <div style={{ marginTop: 8, padding: "8px 10px", background: "#fff7ef", borderRadius: 6, fontSize: 13, fontFamily: "monospace", color: "#b8590b", lineHeight: 1.6 }}>
                  y = {formatNum(reg.m)}x {reg.b >= 0 ? "+ " + formatNum(reg.b) : "− " + formatNum(-reg.b)}
                  <br />
                  <span style={{ fontSize: 12 }}>R² = {reg.r2.toFixed(4)} (1에 가까울수록 잘 맞음)</span>
                </div>
              );
            })()}
          </div>

          {/* [Phase 7] 저장 & 불러오기 */}
          <div style={{ borderTop: "1px solid #eee", padding: "12px 16px" }}>
            <div style={{ fontSize: 13, color: "#999", marginBottom: 8, fontWeight: "bold" }}>저장 & 불러오기</div>

            {/* 영구 저장 (이름 붙여) */}
            <button onClick={saveNamed} style={{ width: "100%", padding: "8px", marginBottom: 6, border: "1px solid #2d70b3", borderRadius: 6, background: "#2d70b3", color: "#fff", cursor: "pointer", fontSize: 13 }}>
              현재 그래프 저장하기
            </button>

            {/* 저장된 목록 */}
            {savedList.length > 0 && (
              <div style={{ marginBottom: 8 }}>
                {savedList.map((name) => (
                  <div key={name} style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 0" }}>
                    <button onClick={() => loadNamed(name)} style={{ flex: 1, textAlign: "left", padding: "5px 8px", border: "1px solid #ddd", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 13, color: "#333" }}>
                      📈 {name}
                    </button>
                    <button onClick={() => deleteNamed(name)} title="삭제" style={{ width: 24, border: "none", background: "none", color: "#ccc", cursor: "pointer", fontSize: 15 }}>×</button>
                  </div>
                ))}
              </div>
            )}

            {/* JSON 파일 내보내기/가져오기 */}
            <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
              <button onClick={exportJSON} style={{ flex: 1, padding: "7px", border: "1px solid #ddd", borderRadius: 6, background: "#fafafa", cursor: "pointer", fontSize: 12, color: "#666" }}>
                파일로 내보내기
              </button>
              <label style={{ flex: 1, padding: "7px", border: "1px solid #ddd", borderRadius: 6, background: "#fafafa", cursor: "pointer", fontSize: 12, color: "#666", textAlign: "center" }}>
                파일 가져오기
                <input type="file" accept="application/json,.json" onChange={importJSON} style={{ display: "none" }} />
              </label>
            </div>

            {/* [Phase 7-B] 코어 Graph2dSpec 명세 내보내기/붙여넣기 */}
            <div style={{ marginTop: 10, borderTop: "1px dashed #eee", paddingTop: 8 }}>
              <div style={{ fontSize: 12, color: "#aaa", marginBottom: 6 }}>코어 명세 (Graph2dSpec JSON)</div>
              <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
                <button onClick={exportSpec} style={{ flex: 1, padding: "7px", border: "1px solid #ddd", borderRadius: 6, background: "#fafafa", cursor: "pointer", fontSize: 12, color: "#666" }}>
                  📋 명세 내보내기
                </button>
                <button onClick={applySpec} style={{ flex: 1, padding: "7px", border: "1px solid #ddd", borderRadius: 6, background: "#fafafa", cursor: "pointer", fontSize: 12, color: "#666" }}>
                  붙여넣기 적용
                </button>
              </div>
              <textarea
                value={specText}
                onChange={(e) => setSpecText(e.target.value)}
                rows={4}
                placeholder={'{ "function": "a*x**2", "domain": [-5, 5], "parameters": [...] }'}
                style={{ width: "100%", boxSizing: "border-box", fontFamily: "monospace", fontSize: 11, padding: 6, border: "1px solid #ddd", borderRadius: 6, resize: "vertical", color: "#333" }}
              />
            </div>

            {/* 상태 메시지 */}
            {saveStatus && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#388c46", textAlign: "center" }}>{saveStatus}</div>
            )}
          </div>
          </>
          )}
        </div>

        <div style={{ padding: "12px 20px", borderTop: "1px solid #eee", fontSize: 12, color: "#999", lineHeight: 1.6 }}>
          함수: x^2, sin(x) · 점: (1,3) · 원/음함수: x^2+y^2=9
          <br />부등식: y&gt;x^2 · 극좌표: r=2sin(theta)
          <br />매개변수: (cos(t), sin(t)) · x외 문자=슬라이더
          <br />함수 아래 "접선" 체크 → 슬라이더로 기울기 관찰
        </div>
      </div>

      <div ref={containerRef} style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        {mode3D ? (
          /* [Phase 11] 3D 곡면 뷰 */
          <Surface3D expr={expr3D} range={range3D} />
        ) : (
          <>
            <canvas ref={canvasRef} onWheel={handleWheel} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseLeave} style={{ display: "block", cursor: dragRef.current ? "grabbing" : "crosshair" }} />
            <div style={{ position: "absolute", top: 16, right: 16, display: "flex", gap: 8 }}>
              <button onClick={exportPNG} style={{ padding: "8px 16px", background: "#fff", border: "1px solid #ddd", borderRadius: 8, cursor: "pointer", fontSize: 14, boxShadow: "0 2px 6px rgba(0,0,0,0.1)" }}>PNG 저장</button>
              <button onClick={resetView} style={{ padding: "8px 16px", background: "#fff", border: "1px solid #ddd", borderRadius: 8, cursor: "pointer", fontSize: 14, boxShadow: "0 2px 6px rgba(0,0,0,0.1)" }}>화면 초기화</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
