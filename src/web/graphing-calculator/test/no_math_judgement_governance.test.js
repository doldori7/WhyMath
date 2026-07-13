// L5 웹 클라이언트 무-수학판정 거버넌스 게이트 (ARCH-10 · 감사 갭 A 상환)
//
// 불변식(CLAUDE.md 슬라이스 89): 정오 판정·채점·오개념 진단의 단일 권위는 백엔드(L3 SymPy).
// mathjs는 렌더·수치 평가 전용이다 (mathExpr.js 헤더의 권위 경계 선언).
//
// 동결 방식(backend test_legacy_snapshot_governance.py 화이트리스트 패턴):
// 채점/진단 심볼을 포함하는 파일 집합을 "알려진 기존 위반" 화이트리스트와 정확 일치로
// 동결한다. 새 파일이 채점 심볼을 들여오면 red, 화이트리스트 파일에서 심볼이 제거되면
// (상환 완료) 화이트리스트를 줄이는 방향으로만 이 테스트를 수정한다.
//
// 화이트리스트 2건은 QuizMode의 기존 위반(클라 채점 sameGraph·오개념 진단 diagnose·
// localStorage 점수 저장)이다 — **(a) 데모 전용 예외로 공식 존치** (ARCH-12 Kiki 결정
// 2026-07-13·MEMORY 결정 로그). 근거: QuizMode는 학생 미노출(Flutter 앱 도달 경로 0·
// 임베드는 spec 주입 렌더만). 강제 트리거: 화이트리스트 파일의 판정 로직이 학생 노출
// 경로에 진입하는 순간 (b) 백엔드 verify(/v1/verify-answer) 리팩터가 강제된다.
// 그 전까지 화이트리스트는 2건 동결 — 늘리는 방향의 수정은 금지(신규 유입 red 유지).

import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SRC_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src");

// 채점/진단 심볼 — 등장 자체가 판정 로직 신호
const FORBIDDEN_PATTERNS = [
  { name: "sameGraph 호출(채점)", re: /sameGraph\s*\(/ },
  { name: "sameGraph 정의", re: /sameGraph\s*=/ },
  { name: "diagnose 정의/호출(오개념 진단)", re: /\bdiagnose\s*[=(]/ },
  { name: "quiz_history(점수 저장)", re: /quiz_history/ },
  { name: "checkAnswer", re: /\bcheckAnswer\w*\s*\(/ },
  { name: "gradeAnswer", re: /\bgradeAnswer\w*\s*\(/ },
];

// 알려진 기존 위반 (ARCH-12 결정 대기) — 이 집합 밖의 등장은 전부 위반
const WHITELIST = new Set(["GraphingCalculator.jsx", "lib/mathExpr.js"]);

function walkSources(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkSources(full));
    else if (/\.(js|jsx|ts|tsx)$/.test(entry.name)) out.push(full);
  }
  return out.sort();
}

describe("L5 웹 무-수학판정 거버넌스 (ARCH-10)", () => {
  const files = walkSources(SRC_DIR);

  it("스캔 대상이 비어 있지 않다 (게이트 무력화 방지)", () => {
    expect(files.length).toBeGreaterThan(3);
  });

  it("채점/진단 심볼 포함 파일 = 화이트리스트와 정확 일치 (신규 유입 red)", () => {
    const offenders = new Set();
    for (const file of files) {
      const source = fs.readFileSync(file, "utf-8");
      const rel = path.relative(SRC_DIR, file).replaceAll(path.sep, "/");
      for (const { re } of FORBIDDEN_PATTERNS) {
        if (re.test(source)) offenders.add(rel);
      }
    }
    // 정확 일치: 신규 유입(집합 증가)도, 조용한 화이트리스트 부패(집합 감소를
    // 테스트 갱신 없이 방치)도 모두 red — 감소 시 이 테스트의 WHITELIST를 줄일 것.
    expect([...offenders].sort()).toEqual([...WHITELIST].sort());
  });

  it("화이트리스트 밖 파일에는 어떤 채점 심볼도 없다 (파일·패턴 단위 상세 보고)", () => {
    const violations = [];
    for (const file of files) {
      const rel = path.relative(SRC_DIR, file).replaceAll(path.sep, "/");
      if (WHITELIST.has(rel)) continue;
      const source = fs.readFileSync(file, "utf-8");
      for (const { name, re } of FORBIDDEN_PATTERNS) {
        if (re.test(source)) violations.push(`${rel}: ${name}`);
      }
    }
    expect(violations, "판정 권위는 백엔드 L3 — 클라 채점 유입 금지").toEqual([]);
  });
});
