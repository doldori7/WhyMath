import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 정적 SPA 빌드 설정.
// base:'./' 는 산출물(dist)을 file:// 또는 Flutter WebView에서 *상대경로*로 로드하기 위한
// 핵심 설정 — 절대경로(기본값 '/')면 WebView 임베드 시 JS·CSS 자산 로드에 실패한다.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", sourcemap: true },
});
