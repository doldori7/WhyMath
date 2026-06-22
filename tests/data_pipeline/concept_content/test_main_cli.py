"""K-12 콘텐츠 CLI 단위테스트 — 합성 xlsx로 개념+암기카드 조인·대학 필터·NCIC 본문 미수록."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from data_pipeline.concept_content.__main__ import main  # noqa: E402

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


def _concept_row(
    code: str,
    school: str = "초등(1~2학년군)",
    linked: str = "[2수01-01]",
) -> list[object]:
    return [
        "1",
        school,
        "수학(초1~2)",
        "수와 연산",
        code,
        "수 감각",
        "NCIC 성취기준 본문 문장 — 미수록 대상",
        "NCIC 요약 — 미수록 대상",
        "분류",
        "28",
        linked,
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
    ws.append(_concept_row("N1", linked="[2수01-01]"))
    ws.append(_concept_row("T2", school="중학교", linked="[2수03-08]; [2수03-09]; [4수03-13]"))
    ws.append(_concept_row("GALOIS-U1-S1", school="대학교"))  # 대학 — 비추출
    cards = wb.create_sheet("암기카드(목록화)")
    cards.append(_CARD_HDR)
    cards.append(["A", "수", "1", "N1", "수 감각", "앞", "뒤", "암기", "마스터 후"])
    cards.append(
        ["B", "함수", "25", "GALOIS-U1-S1", "분해체", "앞", "뒤", None, "마스터 후"]
    )  # 대학 카드 — 무시
    wb.save(str(path))


def test_cli_builds_content_corpus(tmp_path: Path) -> None:
    xlsx = tmp_path / "m.xlsx"
    _make_xlsx(xlsx)
    out = tmp_path / "corpus"
    assert main(["--input", str(xlsx), "--output-dir", str(out)]) == 0

    data = json.loads((out / "content.json").read_text(encoding="utf-8"))
    content = data["content"]
    # K-12 2건만(대학 GALOIS 필터)·개념ID 조인된 카드.
    assert data["scope"] == "K-12"
    assert len(content) == 2
    codes = {c["code"] for c in content}
    assert codes == {"N1", "T2"}
    n1 = next(c for c in content if c["code"] == "N1")
    assert len(n1["flashcards"]) == 1  # 개념ID로 카드 조인
    assert n1["formal_definition_internal"] == "정식정의문"
    # 연결 성취기준 → 코드만(';'·',' 분할).
    assert n1["standard_codes"] == ["[2수01-01]"]
    t2 = next(c for c in content if c["code"] == "T2")
    assert t2["standard_codes"] == ["[2수03-08]", "[2수03-09]", "[4수03-13]"]
    assert "자체" in data["source_citation"]
    # 대학 카드(GALOIS)는 섞이지 않았다.
    assert all(not c["code"].startswith("GALOIS") for c in content)


def test_cli_redacts_ncic_body(tmp_path: Path) -> None:
    xlsx = tmp_path / "m.xlsx"
    _make_xlsx(xlsx)
    out = tmp_path / "corpus"
    assert main(["--input", str(xlsx), "--output-dir", str(out)]) == 0
    raw = (out / "content.json").read_text(encoding="utf-8")
    # NCIC 본문 키·본문 텍스트가 코퍼스에 일절 없어야 한다.
    for key in ("성취기준 문장", "성취기준 요약(간결)", "성취기준 요약", "핵심명제"):
        assert f'"{key}"' not in raw
    assert "NCIC 성취기준 본문 문장" not in raw
    assert "NCIC 요약" not in raw


def test_cli_missing_input(tmp_path: Path) -> None:
    assert main(["--input", str(tmp_path / "no.xlsx"), "--output-dir", str(tmp_path / "o")]) == 2
