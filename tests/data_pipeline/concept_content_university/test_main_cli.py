"""대학 콘텐츠 CLI 단위테스트 — 합성 xlsx로 개념+암기카드 조인·초중고 필터·자체작성 표지."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from data_pipeline.concept_content_university.__main__ import main  # noqa: E402

_CONCEPT_HDR = [
    "순서",
    "학교급",
    "과목",
    "단원(영역)",
    "개념ID",
    "개념명",
    "성취기준 문장",
    "성취기준 요약(간결)",
    "분류",
    "난이도층",
    "연결 성취기준",
    "매칭 CCSS",
    "설명",
    "은유",
    "오개념",
    "정식정의(내부·학생비노출)",
    "허용표현(인정 표현)",
    "정의출처",
    "암기카드수",
    "비고",
    "연결 성취기준(원본·2015)",
]
_CARD_HDR = [
    "등급",
    "단원(분류)",
    "난이도층",
    "개념ID",
    "개념명",
    "앞면(front)",
    "뒷면(back)",
    "암기보조(mnemonic)",
    "노출조건",
]


def _concept_row(code: str, school: str = "대학교") -> list[object]:
    return [
        "1",
        school,
        "갈루아 이론",
        "체확장 복습",
        code,
        "분해체",
        "문장",
        "요약",
        "분류",
        "28",
        "[GALOIS-01-01]",
        "-",
        "정규확장→갈루아군",
        "은유문",
        "오개념문",
        "정식정의문",
        "허용표현문",
        "자체작성",
        "1",
        "비고",
        "-",
    ]


def _make_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "개념"
    ws.append(_CONCEPT_HDR)
    ws.append(_concept_row("GALOIS-U1-S1"))
    ws.append(_concept_row("GALOIS-U1-S2"))
    ws.append(_concept_row("N4", school="초등(1~2학년군)"))  # 초중고 — 비추출
    cards = wb.create_sheet("암기카드(목록화)")
    cards.append(_CARD_HDR)
    cards.append(["B", "함수", "25", "GALOIS-U1-S1", "분해체", "앞", "뒤", "암기", "마스터 후"])
    cards.append(
        ["A", "수", "1", "N4", "수감각", "앞", "뒤", None, "마스터 후"]
    )  # 초중고 카드 — 무시
    wb.save(str(path))


def test_cli_builds_content_corpus(tmp_path: Path) -> None:
    xlsx = tmp_path / "m.xlsx"
    _make_xlsx(xlsx)
    out = tmp_path / "corpus"
    assert main(["--input", str(xlsx), "--output-dir", str(out)]) == 0

    data = json.loads((out / "content.json").read_text(encoding="utf-8"))
    content = data["content"]
    # 대학 2건만(초중고 N4 필터)·소단원 코드 조인된 카드.
    assert len(content) == 2
    codes = {c["code"] for c in content}
    assert codes == {"GALOIS-U1-S1", "GALOIS-U1-S2"}
    s1 = next(c for c in content if c["code"] == "GALOIS-U1-S1")
    assert len(s1["flashcards"]) == 1  # 소단원 코드로 카드 조인
    assert s1["formal_definition_internal"] == "정식정의문"
    assert "자체" in data["source_citation"]
    # 초중고 카드(N4)는 섞이지 않았다.
    assert all(c["code"].startswith("GALOIS") for c in content)


def test_cli_missing_input(tmp_path: Path) -> None:
    assert main(["--input", str(tmp_path / "no.xlsx"), "--output-dir", str(tmp_path / "o")]) == 2
