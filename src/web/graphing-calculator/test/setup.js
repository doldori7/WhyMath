import "@testing-library/jest-dom";
import { installStorageShim } from "../src/lib/storageShim";

// jsdom은 canvas 2D 컨텍스트를 구현하지 않는다. 스모크 렌더에서 그리기 호출이 터지지 않게
// no-op 메서드를 제공한다(프로퍼티 대입 fillStyle/lineWidth 등은 일반 객체라 자유롭게 허용).
const ctxStub = () => ({
  setTransform() {}, clearRect() {}, fillRect() {}, strokeRect() {},
  beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, fill() {},
  arc() {}, fillText() {}, measureText: () => ({ width: 0 }),
  setLineDash() {}, save() {}, restore() {}, scale() {}, translate() {},
  closePath() {}, rect() {}, clip() {},
  createLinearGradient: () => ({ addColorStop() {} }),
});

if (typeof HTMLCanvasElement !== "undefined") {
  HTMLCanvasElement.prototype.getContext = ctxStub;
  HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,";
}

if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = () => ({
    matches: false,
    addListener() {}, removeListener() {},
    addEventListener() {}, removeEventListener() {},
  });
}

installStorageShim();
