"""437↔원자 크로스워크 프로그램적 유도 — 성취기준 교집합(1차) + 이름 자카드(2차).

손저작이 아니라 **결정론적 유도**다(동일 입력 2회 실행 시 byte 동일 산출):

  1. **1차 다리(standard_codes 교집합)**: 구 개념과 신 원자(level=='세부개념'만)가 공유하는
     성취기준 코드로 후보 집합을 만든다. 성취기준 코드는 양측 모두 NCIC truth source *코드*라
     의미론적으로 안전한 조인 축이다(본문 미사용).
  2. **2차 다리(이름 토큰 자카드)**: 후보가 복수면 이름 토큰(단어 run + 문자 bigram) 자카드
     유사도로 랭킹 → 최상위가 `primary_atom_code`. 외부 라이브러리 0(표준 re만).
  3. **후보 0 → unmapped**: 강제 매핑하지 않고 사유를 기록한다(#419 '미매핑 33 정직 표기' 선례).

결정론 보장: 동률 시 원자 code 사전순(먼저 오는 code 승). Date/random 미사용.
confidence 산식(결정론): 교집합 유일 후보 0.9 · 복수 후보 0.5+0.4×(최고 자카드) · 미매핑 0.0.

법적: 양측 코퍼스의 코드·이름(자체작성)만 읽는다 — 성취기준 본문·교과서 본문은 만지지 않는다.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from data_pipeline.concept_atom_crosswalk.models import CrosswalkEntry, MatchMethod

# 원자 레벨 상수 — atom_graph 코퍼스의 3단 계층(단원/소단원/세부개념) 중 원자만 매핑 대상.
ATOM_LEVEL: str = "세부개념"

# 이름 토큰화 — 한글·영숫자 run만 취한다(구두점·괄호·중점(·) 등은 구분자).
_TOKEN_RUN = re.compile(r"[0-9a-z가-힣]+")


@dataclass(slots=True, frozen=True)
class ConceptRecord:
    """구 437 그래프 개념 1건 — 유도에 필요한 최소 필드만(코드·이름·성취기준 코드)."""

    concept_id: str
    name_ko: str
    standard_codes: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class AtomRecord:
    """신 원자 백본 원자 1건(level=='세부개념') — 유도에 필요한 최소 필드만."""

    code: str
    name: str
    standard_codes: tuple[str, ...]


def load_concepts(graph_path: Path, concepts_jsonl_path: Path) -> list[ConceptRecord]:
    """구 437 코퍼스 로드 — graph.json(concept_id·standard_codes) ⨝ concepts.jsonl(name_ko).

    graph.json의 개념 노드에는 name_ko가 없고(redaction 구조), concepts.jsonl에는 concept_id가
    없다(원천 src_id 축) — `source_id`(graph) = `src_id`(jsonl)로 조인해 둘을 합친다.
    조인 실패는 즉시 오류(조용히 빠뜨리지 않음 — CLAUDE.md 신뢰 원칙).
    """
    name_by_src: dict[str, str] = {}
    for line in concepts_jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        name_by_src[str(row["src_id"])] = str(row["name_ko"])

    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    records: list[ConceptRecord] = []
    for node in payload["concepts"]:
        src_id = str(node["source_id"])
        if src_id not in name_by_src:
            raise ValueError(f"concepts.jsonl에 src_id {src_id!r} 없음 — 코퍼스 조인 실패")
        records.append(
            ConceptRecord(
                concept_id=str(node["concept_id"]),
                name_ko=name_by_src[src_id],
                standard_codes=tuple(node.get("standard_codes") or []),
            )
        )
    return records


def load_atoms(graph_path: Path) -> list[AtomRecord]:
    """신 원자 백본 로드 — level=='세부개념' 노드만(단원 217·소단원 643은 매핑 대상 아님)."""
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    return [
        AtomRecord(
            code=str(node["code"]),
            name=str(node.get("name") or ""),
            standard_codes=tuple(node.get("standard_codes") or []),
        )
        for node in payload["concepts"]
        if node.get("level") == ATOM_LEVEL
    ]


def name_tokens(name: str) -> frozenset[str]:
    """이름 → 토큰 집합(단어 run + 각 run의 문자 bigram) — 자카드 비교 축.

    문자 bigram을 섞는 이유: 한국어 복합어('자릿값·위치적 기수법' vs '자릿값 원리')는 단어 run
    만으로는 겹침이 거칠어서, run 내부 bigram으로 부분 겹침을 잡는다. 외부 lib 0·결정론.
    """
    runs = _TOKEN_RUN.findall(name.lower())
    tokens: set[str] = set(runs)
    for run in runs:
        tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    return frozenset(tokens)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """자카드 유사도 |A∩B|/|A∪B| — 양쪽 다 비면 0.0(정의 불능을 0으로 정직 처리)."""
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def derive_crosswalk(
    concepts: list[ConceptRecord], atoms: list[AtomRecord]
) -> list[CrosswalkEntry]:
    """크로스워크 유도 본체 — 437행 전량(미매핑 포함)·concept_id 사전순 반환.

    유도 규칙(모듈 docstring 1~3단계)·결정론(동률 시 code 사전순) 준수. 후보 목록
    `atom_codes`는 code 사전순으로 저장하고, `primary_atom_code`만 자카드 최상위로 뽑는다
    (후보 순서에 랭킹을 섞지 않음 — 목록은 '무엇이 후보였나', primary는 '어디에 귀속하나').
    """
    atoms_by_standard: dict[str, list[AtomRecord]] = defaultdict(list)
    for atom in atoms:
        for code in atom.standard_codes:
            atoms_by_standard[code].append(atom)

    atom_by_code = {atom.code: atom for atom in atoms}
    entries: list[CrosswalkEntry] = []

    for concept in sorted(concepts, key=lambda c: c.concept_id):
        # 1차 다리 — 성취기준 교집합 후보(코드 기준 dedup·사전순).
        candidate_codes: set[str] = set()
        shared_standards: set[str] = set()
        for standard in concept.standard_codes:
            matched = atoms_by_standard.get(standard, [])
            if matched:
                shared_standards.add(standard)
            candidate_codes.update(a.code for a in matched)
        candidates = sorted(candidate_codes)

        if not candidates:
            # 3단계 — 강제 매핑 금지: 사유를 기록하고 미매핑으로 정직 표기.
            entries.append(
                CrosswalkEntry(
                    concept_id=concept.concept_id,
                    atom_codes=[],
                    primary_atom_code=None,
                    match_method=MatchMethod.UNMAPPED,
                    confidence=0.0,
                    evidence=(
                        f"성취기준 {sorted(concept.standard_codes)} 어느 것도 "
                        "원자 standard_codes와 교집합 없음"
                    ),
                    unmapped_reason=(
                        "성취기준 교집합 원자 0개 — "
                        f"개념 standard_codes={sorted(concept.standard_codes)}"
                    ),
                )
            )
            continue

        if len(candidates) == 1:
            # 교집합 유일 — 이름 비교 불요, 그 원자가 primary.
            entries.append(
                CrosswalkEntry(
                    concept_id=concept.concept_id,
                    atom_codes=candidates,
                    primary_atom_code=candidates[0],
                    match_method=MatchMethod.STANDARD_CODE,
                    confidence=0.9,
                    evidence=(
                        f"성취기준 교집합 {sorted(shared_standards)} → 후보 1개(유일) "
                        f"{candidates[0]}"
                    ),
                )
            )
            continue

        # 2차 다리 — 후보 복수: 이름 토큰 자카드 랭킹. 동률 시 code 사전순(결정론).
        concept_tokens = name_tokens(concept.name_ko)
        ranked = sorted(
            candidates,
            key=lambda code: (-jaccard(concept_tokens, name_tokens(atom_by_code[code].name)), code),
        )
        primary = ranked[0]
        best_score = jaccard(concept_tokens, name_tokens(atom_by_code[primary].name))
        entries.append(
            CrosswalkEntry(
                concept_id=concept.concept_id,
                atom_codes=candidates,
                primary_atom_code=primary,
                match_method=MatchMethod.STANDARD_CODE_NAME,
                confidence=round(0.5 + 0.4 * best_score, 4),
                evidence=(
                    f"성취기준 교집합 {sorted(shared_standards)} → 후보 {len(candidates)}개; "
                    f"이름 자카드 최고 {best_score:.4f} → primary {primary}"
                    f"('{atom_by_code[primary].name}')"
                ),
            )
        )

    return entries
