#!/usr/bin/env python3
"""EOS-52 앵커 자산 실사 — 재현 스크립트 (2026-08-30 EOS 전환 선언 §3.2-② 지시).

12월 내부 검증 앵커 후보 8단원(A1~A8)의 저장소 자산 커버리지를 5축으로 실측한다:
  ① 원자 노드 수  ② 성취기준 코드(2022 개정) 수  ③ 오개념 항목 수
  ④ 기계판정형 detection_rule 수(리터럴 필드 + 실재 최근접 대응물 L4 탐지채널)
  ⑤ 기존 문항 코퍼스 문항 수

정본 원칙: 읽는 것은 저장소 파일뿐(YAML/JSON=소스, DB=산출물 단방향) — prod DB는 읽지 않는다.
DB 적재분 대조는 산출 문서(docs/reviews/eos_anchor_asset_audit_2026-09.md) 부록의 psql 명령으로.

실패 경로 설계(CLAUDE.md 2026-08-22 "측정·수집 도구를 성공 경로만 보고 설계 금지" 준수):
  ① 단계별 즉시 flush — 각 단계 종료마다 결과 JSON을 원자적으로(tmp→replace) 저장한다.
     중간 실패 시에도 그때까지의 부분 결과가 파일로 남는다.
  ② 실패 원인 기록 — 단계 예외는 예외 타입명+메시지를 결과 JSON `errors`에 남긴다(침묵 실패 금지).
  ③ 시간 필터 — 결과 JSON에 `measured_at_utc`를 기록해 이전 실행 산출물과의 혼동을 막는다.
  ④ 외부 프로세스 호출 없음 — subprocess 미사용(파일 I/O만)이므로 타임아웃 규칙 해당 없음.
  종료 코드: 전 단계 성공=0, 한 단계라도 실패=1 (측정 실패가 성공 화면으로 위장되면 안 된다).

실행(레포 루트 기준):
  python3 scripts/analysis/eos_anchor_asset_audit.py
  → 기본 산출: data/audit/eos_anchor_asset_audit_2026-09.json + stdout 마크다운 표

계층 경계: 본 스크립트는 분석 전용(scripts/analysis 격리)이며 src/backend 코드를 import하지
않는다 — L4 카탈로그(catalog.py·distractor.py)는 AST 파싱으로만 읽는다(무거운 패키지 의존
체인 회피 + 역방향 의존 신설 금지).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# 앵커 정의 (매핑 기준 동결)
#
# 매핑 축 = **성취기준 코드(2022 개정) 단일 축**. 근거:
#  - 원자(atom_graph)·오개념(misconceptions)·문항(problem_bank)이 모두 성취기준 코드 필드를
#    가져 세 자산을 같은 축으로 재현 가능하게 귀속시킬 수 있다.
#  - 대안이던 subunit(소단원명) 축은 구조 헤더 노드(level=소단원, standard_codes=[])와
#    교과서 단원 granularity 차이(예: '비와 비율' subunit이 비례식·비례배분 원자까지 포함)로
#    앵커 경계가 흐려진다. 성취기준 코드 축에서는 리프(세부개념)만 걸린다.
#  - 대학 앵커도 자체작성 성취기준([CALC1-*]·[LINA1-*])이 동일 메커니즘으로 존재한다.
# 포함/제외 경계는 각 앵커의 excluded에 사유와 함께 명시(재현 가능성).
# ---------------------------------------------------------------------------
ANCHOR_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "A1",
        "title": "초3 분수의 이해와 크기 비교",
        "codes": ["[4수01-09]", "[4수01-10]", "[4수01-11]"],
        "excluded": {
            "[4수01-12]": "소수 한 자리 수 — 별도 소단원(소수)",
            "[4수01-15]": "분모 같은 분수 덧뺄셈 — 별도 소단원(연산)",
        },
        "note": "2022 개정은 3~4학년군 단위(초3 구분 없음) — 도입·종류·크기비교 3코드",
    },
    {
        "id": "A2",
        "title": "초6 비와 비율",
        "codes": ["[6수02-02]", "[6수02-03]"],
        "excluded": {
            "[6수02-01]": "대응 관계 — 별도 단원",
            "[6수02-04]": "비례식 — 초6 별도 단원(비례식과 비례배분)",
            "[6수02-05]": "비례배분 — 초6 별도 단원(비례식과 비례배분)",
        },
        "note": "비([6수02-02])+비율과 백분율([6수02-03])만 — 앵커명 '비와 비율' 문언 준수",
    },
    {
        "id": "A3",
        "title": "중2 경우의 수와 확률",
        "codes": ["[9수04-05]", "[9수04-06]"],
        "excluded": {},
        "note": "2022 개정 '자료와 가능성' 코드 — 2015 개정 [9수05-04/05]는 미사용",
    },
    {
        "id": "A4",
        "title": "중3 이차방정식 (깊이 앵커)",
        "codes": ["[9수02-20]"],
        "excluded": {
            "[9수02-19]": "다항식의 곱셈과 인수분해 — 선수 소단원(별도 코드)",
            "[9수02-21]": "이차함수의 개념 — 이차함수 단원",
            "[9수02-22]": "이차함수의 그래프 — 이차함수 단원",
        },
        "note": "2022 개정 중3 이차방정식은 단일 코드",
    },
    {
        "id": "A5",
        "title": "고1 이차함수의 최대·최소",
        "codes": ["[10공수1-02-06]", "[10기수1-02-05]"],
        "excluded": {
            "[10공수1-02-04]": "이차방정식과 이차함수의 관계 — 인접 소단원",
            "[10공수1-02-05]": "이차함수의 그래프와 직선 — 인접 소단원",
            "[10공수1-02-11]": "이차부등식 — 별도 소단원",
        },
        "note": "공통수학1+기본수학1(병행과목) — sub_domain '이차함수의 최대, 최소' 전수",
    },
    {
        "id": "A6",
        "title": "고2 도함수의 활용",
        "codes": [
            "[12미적Ⅰ-02-05]",
            "[12미적Ⅰ-02-06]",
            "[12미적Ⅰ-02-07]",
            "[12미적Ⅰ-02-08]",
            "[12미적Ⅰ-02-09]",
            "[12미적Ⅰ-02-10]",
        ],
        "excluded": {
            "[12미적Ⅰ-02-01~04]": "미분계수·미분가능성·도함수 — '미분계수와 도함수' 소단원",
            "[12심수Ⅰ05-19]": "심화수학Ⅰ 도함수의 활용 — 진로선택 과목(앵커는 미적분Ⅰ)",
        },
        "note": "미적분Ⅰ '도함수의 활용' 6코드(접선·평균값·증감극값·개형·방부등식·속도)",
    },
    {
        "id": "A7",
        "title": "대학 미적분 ε-δ 극한·연속",
        "codes": ["[CALC1-01-02]", "[CALC1-01-03]"],
        "excluded": {
            "[CALC1-01-04]": "무한대 극한 — 앵커 문언(ε-δ 극한·연속) 밖",
            "해석학 I": "ε-δ 연속을 다루나 별도 과목 — 앵커는 미적분학",
        },
        "note": "standards_university_v1(와이매스 자체작성) 미적분학 I — ε-δ 극한 정의+연속 2코드",
    },
    {
        "id": "A8",
        "title": "대학 선형대수 일차독립과 기저",
        "codes": ["[LINA1-04-02]", "[LINA1-04-03]"],
        "excluded": {
            "[LINA1-04-01]": "부분공간 — 인접 소단원",
            "[LINA1-04-04]": "차원(dimension) — 인접 소단원(앵커 문언은 일차독립·기저)",
        },
        "note": "standards_university_v1 선형대수학 I — 일차독립+기저 2코드",
    },
)

# 문항 은행 디렉터리(전수) — data/corpus/problem_bank_*/problems.jsonl
PROBLEM_BANK_GLOB = "problem_bank_*"

# 리터럴 스캔 분류: 최상위 경로 → 코드/문서/데이터
CODE_TOP_DIRS = {"src", "scripts", "tests", "schemas", "infra", "conftest.py"}
DOC_TOP_DIRS = {"docs", "backlog"}
SKIP_DIRS = {
    ".git",
    "work",  # 병렬 세션 worktree 자리 — 본 체크아웃 콘텐츠가 아님
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".dart_tool",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
}
SCAN_EXTS = {
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".jsonl",
    ".dart",
    ".ts",
    ".js",
    ".sql",
    ".toml",
    ".txt",
    ".sh",
    ".ps1",
}
SCAN_MAX_BYTES = 30 * 1024 * 1024  # 30MB 초과 파일은 스캔 생략(warnings에 기록)


def _now_utc() -> str:
    """측정 시각(UTC ISO) — 결과 JSON의 시간 필터 축."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _flush(result: dict[str, Any], out_path: Path) -> None:
    """결과를 원자적으로 저장(tmp→replace) — 단계별 즉시 flush의 실체.

    실패해도 증거가 남게, 매 단계 호출된다. 쓰기 자체가 실패하면 stderr로 예외 타입명을
    낸다(침묵 실패 금지) — 단, 측정 루프는 계속한다(마지막 flush가 성공할 수 있다).
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(out_path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, out_path)
    except OSError as exc:
        print(f"[flush 실패] {type(exc).__name__}: {exc}", file=sys.stderr)


def _load_json(rel: str) -> Any:
    """저장소 상대 경로의 JSON 로드 — 실패는 호출부(단계 러너)가 타입명으로 기록."""
    return json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 측정 단계들 — 각 단계는 ctx(공유 데이터)와 result(산출 JSON)를 갱신한다
# ---------------------------------------------------------------------------


def step_standards(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """성취기준 로드 — 학교급(2022/2015 혼재 분리) + 대학(자체작성). 앵커 코드 실재 검증."""
    school = _load_json("data/corpus/standards_v1/standards.json")["standards"]
    univ = _load_json("data/corpus/standards_university_v1/standards.json")["standards"]
    s2022 = [x for x in school if x.get("curriculum_revision") == "2022 개정"]
    s2015 = [x for x in school if x.get("curriculum_revision") == "2015 개정"]
    ctx["std2022_by_code"] = {}
    for x in s2022:
        ctx["std2022_by_code"].setdefault(x["code"], []).append(x)
    ctx["stdu_by_code"] = {}
    for x in univ:
        ctx["stdu_by_code"].setdefault(x["code"], []).append(x)
    result["global"]["standards"] = {
        "school_rows_total": len(school),
        "school_rows_2022": len(s2022),
        "school_rows_2015": len(s2015),
        "school_unique_codes": len({x["code"] for x in school}),
        "university_rows": len(univ),
        "note": "학교급 895행은 2022·2015 개정 혼재 — 앵커 집계는 2022 개정 행만 사용",
    }
    # 앵커 코드 실재 검증(동결 코드셋 vs 데이터 드리프트 감지 — 변별력 있는 검사)
    for a in ANCHOR_DEFS:
        rows: list[dict[str, Any]] = []
        for code in a["codes"]:
            hits = ctx["std2022_by_code"].get(code, []) + ctx["stdu_by_code"].get(code, [])
            if not hits:
                result["warnings"].append(
                    f"{a['id']}: 동결 코드 {code}가 성취기준 데이터에 없음(드리프트 의심)"
                )
            for h in hits:
                rows.append(
                    {
                        "code": h["code"],
                        "sub_domain": h.get("sub_domain"),
                        "statement_head": (h.get("statement") or "")[:40],
                    }
                )
        result["anchors"][a["id"]]["standards"] = {"count": len(rows), "rows": rows}


def step_atoms(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """원자 백본 로드 — 전역(노드·엣지·레벨 분포) + 앵커별 원자 수(성취기준 코드 축)."""
    g = _load_json("data/corpus/atom_graph_v1/graph.json")
    atoms = g["concepts"]
    levels: dict[str, int] = {}
    schools: dict[str, int] = {}
    for x in atoms:
        lv = x.get("level") or "(없음)"
        levels[lv] = levels.get(lv, 0) + 1
        sc = x.get("school_level") or "(없음)"
        schools[sc] = schools.get(sc, 0) + 1
    result["global"]["atom_graph"] = {
        "concept_nodes_total": len(atoms),
        "edges": len(g.get("edges") or []),
        "narrative_edges_raw": len(g.get("narrative_edges_raw") or []),
        "level_split": dict(sorted(levels.items())),
        "school_level_split": dict(sorted(schools.items())),
        "note": "노드 총계는 구조 노드(단원·소단원) 포함 — 앵커 집계는 코드 보유 리프만",
    }
    for a in ANCHOR_DEFS:
        codes = set(a["codes"])
        hit = [x for x in atoms if codes & set(x.get("standard_codes") or [])]
        lv_split: dict[str, int] = {}
        for x in hit:
            lv = x.get("level") or "(없음)"
            lv_split[lv] = lv_split.get(lv, 0) + 1
        result["anchors"][a["id"]]["atoms"] = {
            "count": len(hit),
            "level_split": lv_split,
            "atom_codes": sorted(x.get("code") or "?" for x in hit)[:30],
        }


def step_misconceptions(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """오개념 DB(M-id) — 전역 건수 + 앵커별 귀속 + detection_rule 리터럴 필드 실재 검사."""
    doc = _load_json("data/corpus/misconceptions_v1/misconceptions.json")
    mis = doc["misconceptions"]
    declared = doc.get("count")
    if declared is not None and declared != len(mis):
        result["warnings"].append(
            f"misconceptions.json 자체 선언 count={declared} ≠ 실제 {len(mis)} (정합성 확인 필요)"
        )
    # detection_rule 리터럴 필드: 행 단위 실재 검사(가정 금지 — 키 존재를 직접 센다)
    field_rows = sum(1 for x in mis if "detection_rule" in x)
    levels: dict[str, int] = {}
    for x in mis:
        lv = x.get("school_level") or "(없음)"
        levels[lv] = levels.get(lv, 0) + 1
    result["global"]["misconceptions"] = {
        "rows_total": len(mis),
        "rows_with_detection_rule_field": field_rows,
        "school_level_split": dict(sorted(levels.items())),
        "collected_at": doc.get("collected_at"),
    }
    ctx["mis_by_id"] = {x["mis_id"]: x for x in mis}
    for a in ANCHOR_DEFS:
        codes = set(a["codes"])
        hit = [x for x in mis if (x.get("standard_code") or "") in codes]
        result["anchors"][a["id"]]["misconceptions"] = {
            "count": len(hit),
            "with_detection_rule_field": sum(1 for x in hit if "detection_rule" in x),
            "mis_ids": sorted(x["mis_id"] for x in hit),
        }


def step_problems(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """문항 코퍼스 — 은행별 전역 건수 + 앵커별 귀속(achievement_standard_codes 교집합)."""
    corpus_dir = REPO_ROOT / "data" / "corpus"
    banks = sorted(p.name for p in corpus_dir.glob(PROBLEM_BANK_GLOB) if p.is_dir())
    if not banks:
        # 은행 0개는 '문항 0건'이 아니라 측정 실패다(0건 위장 금지 — CLAUDE.md 이중 회계 원칙)
        raise FileNotFoundError(f"문항 은행 디렉터리 없음: {corpus_dir}/{PROBLEM_BANK_GLOB}")
    per_bank: dict[str, int] = {}
    problems: list[tuple[str, set[str]]] = []  # (은행, 성취기준 코드 집합)
    for bank in banks:
        path = corpus_dir / bank / "problems.jsonl"
        if not path.exists():
            result["warnings"].append(f"{bank}: problems.jsonl 없음")
            continue
        n = 0
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                p = json.loads(line)
                n += 1
                problems.append((bank, set(p.get("achievement_standard_codes") or [])))
        per_bank[bank] = n
    result["global"]["problem_corpus"] = {
        "rows_total": sum(per_bank.values()),
        "per_bank": per_bank,
    }
    for a in ANCHOR_DEFS:
        codes = set(a["codes"])
        bank_split: dict[str, int] = {}
        for bank, pcodes in problems:
            if codes & pcodes:
                bank_split[bank] = bank_split.get(bank, 0) + 1
        result["anchors"][a["id"]]["problems"] = {
            "count": sum(bank_split.values()),
            "per_bank": dict(sorted(bank_split.items())),
        }


def _ast_calls(py_rel: str, func_name: str) -> list[dict[str, ast.expr]]:
    """py 파일에서 `func_name(...)` 호출 전부의 키워드 인자 맵을 AST로 수집(임포트 없이)."""
    tree = ast.parse((REPO_ROOT / py_rel).read_text(encoding="utf-8"))
    out: list[dict[str, ast.expr]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == func_name
        ):
            out.append({k.arg: k.value for k in node.keywords if k.arg})
    return out


def step_l4_catalog(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """L4 오개념 카탈로그(kebab) — 탐지 채널 집계 + crosswalk 경유 앵커 귀속.

    '기계판정형 detection_rule'의 실재 최근접 대응물 판정 축:
      substring `signals`(규칙) < `regex_signals`(정규식) < `canonical_wrong_form`(SymPy 술어).
    """
    calls = _ast_calls("src/backend/whymath_backend/l4/misconception/catalog.py", "Misconception")
    entries = []
    for kw in calls:
        cwf = kw.get("canonical_wrong_form")
        rx = kw.get("regex_signals")
        entries.append(
            {
                "id": ast.literal_eval(kw["id"]),
                "has_sympy_wrong_form": cwf is not None
                and not (isinstance(cwf, ast.Constant) and cwf.value is None),
                "has_regex": rx is not None and bool(getattr(rx, "elts", [])),
            }
        )
    xl = _load_json("data/corpus/misconception_crosslinks_v1/crosslinks.json")["crosslinks"]
    kebab2mid = {r["kebab_id"]: r["mis_id"] for r in xl}
    result["global"]["l4_misconception_catalog"] = {
        "entries": len(entries),
        "with_sympy_wrong_form": sum(1 for e in entries if e["has_sympy_wrong_form"]),
        "with_regex_signals": sum(1 for e in entries if e["has_regex"]),
        "crosslink_rows": len(xl),
        "crosslinked_entries": sum(1 for e in entries if e["id"] in kebab2mid),
        "machine_channel_entries": [
            {
                "id": e["id"],
                "sympy": e["has_sympy_wrong_form"],
                "regex": e["has_regex"],
                "mis_id": kebab2mid.get(e["id"]),
                "standard_code": (ctx.get("mis_by_id", {}).get(kebab2mid.get(e["id"], ""), {})).get(
                    "standard_code"
                ),
            }
            for e in entries
            if e["has_sympy_wrong_form"] or e["has_regex"]
        ],
    }
    mis_by_id = ctx.get("mis_by_id", {})
    for a in ANCHOR_DEFS:
        codes = set(a["codes"])
        hit = []
        for e in entries:
            mid = kebab2mid.get(e["id"])
            if mid and (mis_by_id.get(mid, {}).get("standard_code") or "") in codes:
                hit.append(e)
        result["anchors"][a["id"]]["l4_detection"] = {
            "crosslinked_entries": len(hit),
            "machine_entries_sympy_or_regex": sum(
                1 for e in hit if e["has_sympy_wrong_form"] or e["has_regex"]
            ),
            "entry_ids": sorted(e["id"] for e in hit),
        }


def step_distractor_op_codes(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """L4 distractor op-code 카탈로그 — 'OP코드'의 실재 대응물. 앵커 귀속은 오개념 경유."""
    calls = _ast_calls(
        "src/backend/whymath_backend/l4/misconception/distractor.py", "DistractorOpCode"
    )
    ops = [
        {
            "id": ast.literal_eval(kw["id"]),
            "misconception_id": ast.literal_eval(kw["misconception_id"]),
        }
        for kw in calls
    ]
    result["global"]["distractor_op_codes"] = {
        "entries": len(ops),
        "ids": sorted(o["id"] for o in ops),
        "note": "kebab-case 추상 오류연산 op-code — 설계서 표기 OP_01~08과 명명 체계가 다름",
    }
    xl = _load_json("data/corpus/misconception_crosslinks_v1/crosslinks.json")["crosslinks"]
    kebab2mid = {r["kebab_id"]: r["mis_id"] for r in xl}
    mis_by_id = ctx.get("mis_by_id", {})
    for a in ANCHOR_DEFS:
        codes = set(a["codes"])
        hit = []
        for o in ops:
            mid = kebab2mid.get(o["misconception_id"])
            if mid and (mis_by_id.get(mid, {}).get("standard_code") or "") in codes:
                hit.append(o["id"])
        result["anchors"][a["id"]]["distractor_op_codes"] = {
            "count": len(hit),
            "ids": sorted(hit),
        }


def step_related_stores(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """전역 정정표 보조 수치 — 구 개념그래프·crosswalk(개념↔원자) 행수."""
    cg_path = REPO_ROOT / "data/corpus/concept_graph_v1/concepts.jsonl"
    n_cg = sum(1 for line in cg_path.read_text(encoding="utf-8").splitlines() if line.strip())
    xw_path = REPO_ROOT / "data/corpus/concept_atom_crosswalk_v1/crosswalk.jsonl"
    n_xw = sum(1 for line in xw_path.read_text(encoding="utf-8").splitlines() if line.strip())
    result["global"]["concept_graph_v1_concepts"] = n_cg
    result["global"]["concept_atom_crosswalk_rows"] = n_xw


def step_literal_scan(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """리터럴 스캔 — OP_01~08·detection_rule이 코드로 실재하는지 저장소 전수 판정.

    스캔 제외: 자기 자신(이 스크립트)·자기 산출 JSON — 패턴 문자열을 담고 있어 오염원이 된다.
    """
    pat_op = re.compile(r"\bOP_0[1-8]\b")
    pat_dr = re.compile(r"detection_rule")
    self_paths = {
        Path(__file__).resolve(),
        Path(result["out_path"]).resolve(),
        # 실사 문서 자신도 제외 — 판정 결과를 서술하며 패턴 문자열을 담으므로 재실행 시 오염원
        (REPO_ROOT / "docs/reviews/eos_anchor_asset_audit_2026-09.md").resolve(),
    }
    hits: dict[str, list[dict[str, Any]]] = {"OP_01~08": [], "detection_rule": []}
    skipped_large: list[str] = []
    n_scanned = 0
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in SCAN_EXTS or p.resolve() in self_paths:
                continue
            try:
                if p.stat().st_size > SCAN_MAX_BYTES:
                    skipped_large.append(str(p.relative_to(REPO_ROOT)))
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                result["warnings"].append(
                    f"스캔 실패 {p.relative_to(REPO_ROOT)}: {type(exc).__name__}"
                )
                continue
            n_scanned += 1
            rel = str(p.relative_to(REPO_ROOT))
            top = rel.split("/", 1)[0]
            kind = "code" if top in CODE_TOP_DIRS else ("doc" if top in DOC_TOP_DIRS else "other")
            n_op = len(pat_op.findall(text))
            n_dr = len(pat_dr.findall(text))
            if n_op:
                hits["OP_01~08"].append({"path": rel, "kind": kind, "n": n_op})
            if n_dr:
                hits["detection_rule"].append({"path": rel, "kind": kind, "n": n_dr})
    if skipped_large:
        result["warnings"].append(
            f"크기 초과 스캔 생략 {len(skipped_large)}건: {skipped_large[:5]}"
        )
    if n_scanned == 0:
        # 스캔 0파일은 '리터럴 없음'이 아니라 측정 실패다(0건 위장 금지)
        raise FileNotFoundError(f"스캔 대상 파일 0건: {REPO_ROOT} 아래에 대상 확장자 파일이 없음")
    scan: dict[str, Any] = {"files_scanned": n_scanned}
    scan["excluded_self"] = sorted(str(p) for p in self_paths)
    for key, rows in hits.items():
        rows.sort(key=lambda r: r["path"])
        scan[key] = {
            "files_total": len(rows),
            "code_dir_files": sum(1 for r in rows if r["kind"] == "code"),
            "doc_dir_files": sum(1 for r in rows if r["kind"] == "doc"),
            "other_files": sum(1 for r in rows if r["kind"] == "other"),
            "files": rows[:50],
        }
    result["literal_scan"] = scan


def step_summary_table(ctx: dict[str, Any], result: dict[str, Any]) -> None:
    """앵커×5축 마크다운 표 생성(문서 붙여넣기용) — JSON에도 동봉."""
    lines = [
        "| 앵커 | 단원 | 성취기준(2022) | 원자 노드 | 오개념 | detection_rule 필드 | "
        "L4 탐지항목(기계) | op-code | 문항 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for a in ANCHOR_DEFS:
        r = result["anchors"][a["id"]]
        std = r.get("standards", {}).get("count", "측정실패")
        atom = r.get("atoms", {}).get("count", "측정실패")
        mis = r.get("misconceptions", {}).get("count", "측정실패")
        drf = r.get("misconceptions", {}).get("with_detection_rule_field", "측정실패")
        l4 = r.get("l4_detection", {})
        l4n = l4.get("crosslinked_entries", "?")
        l4m = l4.get("machine_entries_sympy_or_regex", "?")
        l4s = f"{l4n}({l4m})"
        opc = r.get("distractor_op_codes", {}).get("count", "측정실패")
        prob = r.get("problems", {}).get("count", "측정실패")
        cells = [a["id"], a["title"], std, atom, mis, drf, l4s, opc, prob]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    result["table_markdown"] = "\n".join(lines)


STEPS: tuple[tuple[str, Any], ...] = (
    ("standards", step_standards),
    ("atoms", step_atoms),
    ("misconceptions", step_misconceptions),
    ("problems", step_problems),
    ("l4_catalog", step_l4_catalog),
    ("distractor_op_codes", step_distractor_op_codes),
    ("related_stores", step_related_stores),
    ("literal_scan", step_literal_scan),
    ("summary_table", step_summary_table),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="EOS-52 앵커 자산 실사(저장소 파일 실측)")
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "data/audit/eos_anchor_asset_audit_2026-09.json"),
        help="결과 JSON 경로(기본: data/audit/eos_anchor_asset_audit_2026-09.json)",
    )
    args = parser.parse_args()
    out_path = Path(args.out)

    result: dict[str, Any] = {
        "task": "EOS-52-anchor-asset-audit",
        "measured_at_utc": _now_utc(),
        "script": "scripts/analysis/eos_anchor_asset_audit.py",
        "repo_root": str(REPO_ROOT),
        "out_path": str(out_path),
        "mapping_axis": "성취기준 코드(2022 개정·대학 자체작성) 단일 축 — ANCHOR_DEFS 동결 코드셋",
        "anchor_defs": [
            {
                "id": a["id"],
                "title": a["title"],
                "codes": a["codes"],
                "excluded": a["excluded"],
                "note": a["note"],
            }
            for a in ANCHOR_DEFS
        ],
        "steps_completed": [],
        "errors": [],
        "warnings": [],
        "global": {},
        "anchors": {a["id"]: {} for a in ANCHOR_DEFS},
    }
    _flush(result, out_path)  # 시작 상태부터 저장 — 첫 단계 전 실패도 증거가 남는다

    ctx: dict[str, Any] = {}
    for name, fn in STEPS:
        try:
            fn(ctx, result)
            result["steps_completed"].append(name)
        except Exception as exc:  # 단계 실패를 타입명으로 기록하고 계속(부분 결과 보존)
            result["errors"].append(
                {"step": name, "error_type": type(exc).__name__, "error": str(exc)[:500]}
            )
        _flush(result, out_path)

    print(f"측정 시각(UTC): {result['measured_at_utc']}")
    print(f"결과 JSON: {out_path}")
    print(f"완료 단계: {len(result['steps_completed'])}/{len(STEPS)}")
    if result.get("table_markdown"):
        print()
        print(result["table_markdown"])
    if result["warnings"]:
        print(f"\n경고 {len(result['warnings'])}건:")
        for w in result["warnings"]:
            print(f"  - {w}")
    if result["errors"]:
        print(f"\n측정 실패 단계 {len(result['errors'])}건:", file=sys.stderr)
        for e in result["errors"]:
            print(f"  - {e['step']}: {e['error_type']}: {e['error']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
