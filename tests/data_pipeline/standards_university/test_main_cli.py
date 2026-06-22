"""대학 성취기준 CLI 단위테스트 — 합성 xlsx로 extract→transform→validate→write 전 경로.

작은 합성 xlsx를 openpyxl로 즉석 생성한다(실 업로드 파일 불요). openpyxl은 `[xlsx]` extra라
미설치 환경에선 skip한다(방어 — atom test_main_cli는 무조건 import하나 여기선 importorskip).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from data_pipeline.standards_university.__main__ import main  # noqa: E402

_HEADER = [
    "키",
    "교육과정",
    "학교급",
    "구분",
    "학년군·과목",
    "영역(단원)",
    "소단원(개념)",
    "성취기준 코드",
    "성취기준 내용",
    "성취기준 요약(간결)",
    "개념ID",
    "개념명(개념그래프)",
    "매칭 CCSS",
    "개정",
    "과목약칭",
    "영역",
    "일련",
    "norm_id",
]


def _row(
    code: str,
    norm: str,
    subunit: str,
    *,
    school: str = "대학교",
    subject: str = "갈루아 이론",
):
    return [
        f"대학|{code}",
        "대학",
        school,
        "4학년",
        subject,
        "체확장 복습",
        "분해체",
        code,
        "f의 분해체는 최소 확장.",
        "분해체는 근을 담는 최소 체",
        subunit,
        "분해체",
        "-",
        "대학",
        "GALOIS",
        "01",
        "01",
        norm,
    ]


def _make_xlsx(path: Path) -> None:
    """합성 통합마스터 xlsx — 성취기준_목록(대학 2행 + 초중고 1행·필터 확인)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "성취기준_목록"
    ws.append(_HEADER)
    ws.append(_row("[GALOIS-01-01]", "대학_GALOIS_01_01", "GALOIS-U1-S1"))
    ws.append(_row("[GALOIS-01-02]", "대학_GALOIS_01_02", "GALOIS-U1-S2"))
    # 초중고 행 — 자체작성 파이프라인이 *읽지 않아야* 한다(NCIC 본문 라이선스 분리).
    k12 = [
        "초|[2수01-01]",
        "2022개정",
        "초등학교",
        "-",
        "1~2학년군",
        "수와 연산",
        "수",
        "[2수01-01]",
        "NCIC 본문(읽지 않음)",
        "요약",
        "N1",
        "수",
        "-",
        "2022개정",
        "2수",
        "01",
        "01",
        "2022_2수_01_01",
    ]
    ws.append(k12)
    wb.save(str(path))


def test_cli_builds_corpus(tmp_path: Path) -> None:
    xlsx = tmp_path / "master.xlsx"
    _make_xlsx(xlsx)
    out = tmp_path / "corpus"
    rc = main(["--input", str(xlsx), "--output-dir", str(out)])
    assert rc == 0

    std = json.loads((out / "standards.json").read_text(encoding="utf-8"))
    links = json.loads(
        (out / "concept_standard_links.json").read_text(encoding="utf-8")
    )
    prov = json.loads((out / "_provenance.json").read_text(encoding="utf-8"))

    # 대학 2행만(초중고 필터링)·1:1 링크.
    assert len(std["standards"]) == 2
    assert len(links["links"]) == 2
    codes = {s["code"] for s in std["standards"]}
    assert codes == {"[GALOIS-01-01]", "[GALOIS-01-02]"}
    # 초중고 본문이 섞이지 않았다(라이선스 분리).
    assert all("읽지 않음" not in s["statement"] for s in std["standards"])
    # 자체작성 표지 + sha256.
    assert "자체" in std["source_citation"]
    assert len(prov["source_sha256"]) == 64


def test_cli_missing_input_returns_2(tmp_path: Path) -> None:
    rc = main(
        ["--input", str(tmp_path / "nope.xlsx"), "--output-dir", str(tmp_path / "o")]
    )
    assert rc == 2
