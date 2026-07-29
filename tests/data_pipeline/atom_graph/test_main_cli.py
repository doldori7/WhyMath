"""atom_graph CLI 단위테스트 — transform-v1(작은 합성 xlsx). 실 xlsx 불요.

작은 합성 xlsx를 openpyxl로 즉석 생성해 추출→정형화→검증→저장 전 경로를 확인한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from data_pipeline.atom_graph.__main__ import app  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

runner = CliRunner()

_ATOM_HEADER = [
    "순번",
    "출처",
    "교육과정",
    "학교급",
    "학년/학년군",
    "영역/과목",
    "단원",
    "소단원",
    "소단원코드",
    "원자ID",
    "원자명",
    "원자명_표시",
    "인지축",
    "노드유형",
    "오개념유형",
    "난이도",
    "연결성취기준",
    "핵심명제/성취기준내용",
    "①오개념",
    "②진단문항",
    "②정답·통과기준",
    "②미통과·오답신호",
    "③소크라테스질문",
    "④전이",
    "④전이예시",
    "선수원자",
    "원자성a",
    "원자성b",
    "원자성c",
    "원자성d",
    "비고",
]
_EDGE_HEADER = [
    "출처",
    "관계유형",
    "from(선수)",
    "from_원자명",
    "from_학교급",
    "from_유형",
    "관계",
    "to(후행)",
    "to_원자명",
    "to_학교급",
    "학교급연계",
]


def _make_xlsx(path: Path) -> None:
    """합성 원자 백본 xlsx — 원자 2(초등) + 대학 1, 엣지 1(원자ID) + 1(서술형)."""
    wb = openpyxl.Workbook()
    ws_a = wb.active
    ws_a.title = "원자_통합마스터"
    ws_a.append(_ATOM_HEADER)

    def atom(num, code, name, school, linked, core, transfer, sub_code, sub, unit):  # type: ignore[no-untyped-def]
        row = [""] * len(_ATOM_HEADER)
        idx = {h: i for i, h in enumerate(_ATOM_HEADER)}
        row[idx["순번"]] = num
        row[idx["학교급"]] = school
        row[idx["영역/과목"]] = "수와 연산"
        row[idx["단원"]] = unit
        row[idx["소단원"]] = sub
        row[idx["소단원코드"]] = sub_code
        row[idx["원자ID"]] = code
        row[idx["원자명"]] = name
        row[idx["원자명_표시"]] = name
        row[idx["인지축"]] = "개념"
        row[idx["노드유형"]] = "구성"
        row[idx["난이도"]] = "3"
        row[idx["연결성취기준"]] = linked
        row[idx["핵심명제/성취기준내용"]] = core
        row[idx["④전이"]] = transfer
        row[idx["원자성a"]] = "예"
        ws_a.append(row)

    # 초등 2개(핵심명제=NCIC 본문 → redact), 미적 무하이픈 코드 정규화 대상.
    atom(
        "1",
        "2수01-01-1",
        "세기",
        "초등학교",
        "[2수01-01]",
        "NCIC 본문 A",
        "자리값 정리",
        "초수연-U1-S1",
        "세기",
        "수와 연산",
    )
    atom(
        "2",
        "2수01-01-2",
        "기수",
        "초등학교",
        "[2수01-01]",
        "NCIC 본문 B",
        "경계값 정리",
        "초수연-U1-S1",
        "세기",
        "수와 연산",
    )
    # 대학 1개(핵심명제=자체작성 보존), 연결성취기준 없음.
    atom(
        "3",
        "ODE-P07",
        "상미분방정식",
        "대학교",
        "",
        "자체작성 대학 명제",
        "전이",
        "ODE-U1-S1",
        "ODE",
        "미분방정식",
    )

    ws_e = wb.create_sheet("선수엣지_통합")
    ws_e.append(_EDGE_HEADER)
    eidx = {h: i for i, h in enumerate(_EDGE_HEADER)}

    def edge(frm, to, kind, subtype):  # type: ignore[no-untyped-def]
        row = [""] * len(_EDGE_HEADER)
        row[eidx["관계유형"]] = subtype
        row[eidx["from(선수)"]] = frm
        row[eidx["from_유형"]] = kind
        row[eidx["관계"]] = "선수"
        row[eidx["to(후행)"]] = to
        ws_e.append(row)

    edge("2수01-01-1", "2수01-01-2", "원자ID", "소단원내")
    edge("좌표평면", "2수01-01-2", "서술형", "참고(서술형)")

    wb.create_sheet("안내")
    wb.create_sheet("요약")
    wb.save(str(path))


def _standards_json(path: Path) -> Path:
    payload = {"standards": [{"code": "[2수01-01]"}]}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class TestHelp:
    def test_help_lists_transform_v1(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "transform-v1" in result.stdout.lower()


class TestTransformV1:
    def test_validates_synthetic(self, tmp_path: Path) -> None:
        xlsx = tmp_path / "atoms.xlsx"
        _make_xlsx(xlsx)
        std = _standards_json(tmp_path / "standards.json")
        result = runner.invoke(
            app, ["transform-v1", "--source", str(xlsx), "--standards", str(std)]
        )
        assert result.exit_code == 0, result.output
        assert "원자 3" in result.stdout
        assert "PASS" in result.stdout

    def test_writes_outputs_and_redaction(self, tmp_path: Path) -> None:
        xlsx = tmp_path / "atoms.xlsx"
        _make_xlsx(xlsx)
        std = _standards_json(tmp_path / "standards.json")
        out = tmp_path / "out"
        result = runner.invoke(
            app,
            [
                "transform-v1",
                "--source",
                str(xlsx),
                "--standards",
                str(std),
                "--output-dir",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        graph = out / "graph.json"
        prov = out / "_provenance.json"
        assert graph.exists()
        assert prov.exists()
        text = graph.read_text(encoding="utf-8")
        # redaction: K-12 핵심명제 본문·본문 키 없음
        assert "NCIC 본문 A" not in text
        assert "NCIC 본문 B" not in text
        assert '"description"' not in text
        assert "formal_definition" not in text
        # 대학 자체작성 핵심명제는 보존
        assert "자체작성 대학 명제" in text
        # provenance 카운트
        p = json.loads(prov.read_text(encoding="utf-8"))
        assert p["node_counts"]["atoms"] == 3
        assert p["edge_counts"]["atom_id_edges"] == 1
        assert p["edge_counts"]["narrative_edges_raw"] == 1
        assert p["school_level_university_atoms"] == 1
        assert p["normalization_counts"]["redacted_핵심명제"] == 2
        assert p["normalization_counts"]["자리값"] == 1
        assert p["normalization_counts"]["경계값"] == 1
        assert p["validation"]["success"] is True

    def test_missing_source_exits_2(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["transform-v1", "--source", str(tmp_path / "nope.xlsx")])
        assert result.exit_code == 2

    def test_source_required(self) -> None:
        result = runner.invoke(app, ["transform-v1"])
        assert result.exit_code == 2

    def test_detects_cycle_exits_1(self, tmp_path: Path) -> None:
        """순환 선수엣지 → 검증 error → 종료코드 1."""
        wb = openpyxl.Workbook()
        ws_a = wb.active
        ws_a.title = "원자_통합마스터"
        ws_a.append(_ATOM_HEADER)
        aidx = {h: i for i, h in enumerate(_ATOM_HEADER)}
        for _num, code in (("1", "X-1"), ("2", "X-2")):
            row = [""] * len(_ATOM_HEADER)
            row[aidx["학교급"]] = "초등학교"
            row[aidx["원자ID"]] = code
            row[aidx["원자명"]] = code
            row[aidx["소단원코드"]] = "초수연-U1-S1"
            row[aidx["소단원"]] = "세기"
            row[aidx["단원"]] = "수와 연산"
            ws_a.append(row)
        ws_e = wb.create_sheet("선수엣지_통합")
        ws_e.append(_EDGE_HEADER)
        eidx = {h: i for i, h in enumerate(_EDGE_HEADER)}
        for frm, to in (("X-1", "X-2"), ("X-2", "X-1")):
            row = [""] * len(_EDGE_HEADER)
            row[eidx["from(선수)"]] = frm
            row[eidx["from_유형"]] = "원자ID"
            row[eidx["to(후행)"]] = to
            ws_e.append(row)
        xlsx = tmp_path / "cycle.xlsx"
        wb.save(str(xlsx))
        result = runner.invoke(app, ["transform-v1", "--source", str(xlsx), "--standards", "none"])
        assert result.exit_code == 1
        assert "prerequisite_cycle" in result.stdout


@pytest.fixture(autouse=True)
def _no_real_xlsx_committed() -> None:
    """안전 가드: 실 업로드 xlsx가 코퍼스 디렉토리에 커밋되지 않았는지 단언.

    테스트 부수효과가 아니다.
    """
    corpus = Path(__file__).resolve().parents[3] / "data" / "corpus" / "atom_graph_v1"
    if corpus.exists():
        assert not list(corpus.glob("*.xlsx")), "xlsx는 커밋 금지(graph.json·_provenance만)"
