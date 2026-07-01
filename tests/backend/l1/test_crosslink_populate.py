"""오개념 crosswalk 적재 CLI(`l1.misconception.crosslink_populate`) 단위 + 승인 자산 무결성.

두 층을 검증한다:
1. **CLI**(hermetic·`load_crosslinks` monkeypatch) — 경로 결선·종료코드(0/2)·행수 보고. 실 적재
   라운드트립은 `test_misconception_crosslink.py`(fake 엔진)·실 PG 통합이 담당한다.
2. **승인 자산**(`data/corpus/misconception_crosslink_v1/crosslinks.json`) — 사람 검수 승인분(§2.3
   권장대로)이 스키마·FK·트리플 유일을 만족하는지 *커밋 시점 고정*. 틀린 매핑=오도된 리포트라
   (CLAUDE.md #1·#3) 적재 전 정적 게이트로 잡는다.

설계 정본: docs/data/misconception_crosslink_candidates.md §2.2~2.4 ·
math_dsl_remediation_design.md §1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from whymath_backend.l1.misconception import crosslink_populate
from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.schema.misconception_crosslink import MisconceptionCrosslink

# 레포 루트 기준 자산 경로(tests는 src/backend에서 실행 — CI working-directory).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CROSSLINKS = _REPO_ROOT / "data/corpus/misconception_crosslink_v1/crosslinks.json"
_CORPUS = _REPO_ROOT / "data/corpus/misconceptions_v1/misconceptions.json"


# ── ① CLI (hermetic) ─────────────────────────────────────────────────────────
class TestCrosslinkPopulateMain:
    def test_loads_crosslinks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """기본 흐름 — load_crosslinks를 경로대로 호출하고 행 수를 보고."""
        col = tmp_path / "crosslinks.json"
        col.write_text('{"crosslinks": []}', encoding="utf-8")
        calls: dict[str, Path] = {}

        def _fake(session: Any, path: Path) -> int:
            calls["path"] = path
            return 27

        monkeypatch.setattr(crosslink_populate, "load_crosslinks", _fake)

        rc = crosslink_populate.main(["--crosslinks", str(col)])
        assert rc == 0
        assert calls == {"path": col}
        assert "27" in capsys.readouterr().out

    def test_missing_file_returns_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """입력 파일 부재 → 종료코드 2·명확 보고(조용한 무동작 금지)."""
        rc = crosslink_populate.main(["--crosslinks", str(tmp_path / "nope.json")])
        assert rc == 2
        assert "없음" in capsys.readouterr().out


# ── ② 승인 자산 무결성(커밋된 crosslinks.json) ───────────────────────────────
class TestApprovedAssetIntegrity:
    @staticmethod
    def _rows() -> list[dict[str, Any]]:
        data = json.loads(_CROSSLINKS.read_text(encoding="utf-8"))
        return data["crosslinks"]

    def test_all_rows_schema_valid_and_direct(self) -> None:
        """27행 전부 스키마(extra=forbid) 통과·link_type '직접매핑'·method 'manual'."""
        rows = self._rows()
        objs = [MisconceptionCrosslink.model_validate(r) for r in rows]
        assert len(objs) == 27
        assert all(o.link_type == "직접매핑" for o in objs)
        assert all(o.method == "manual" for o in objs)

    def test_triples_unique(self) -> None:
        """(kebab_id, mis_id, link_type) 의미 유일키가 배치 내 중복 없음(멱등 upsert 전제)."""
        rows = self._rows()
        triples = {(r["kebab_id"], r["mis_id"], r["link_type"]) for r in rows}
        assert len(triples) == len(rows)

    def test_kebab_ids_exist_in_catalog(self) -> None:
        """kebab_id 전부 런타임 카탈로그(CATALOG_BY_ID)에 실재(느슨참조 사전 확인)."""
        rows = self._rows()
        missing = [r["kebab_id"] for r in rows if r["kebab_id"] not in CATALOG_BY_ID]
        assert missing == []

    def test_mis_ids_exist_in_corpus(self) -> None:
        """mis_id 전부 M-id 코퍼스에 실재(misconception_catalog FK 대상 사전 확인)."""
        corpus = {
            r["mis_id"] for r in json.loads(_CORPUS.read_text(encoding="utf-8"))["misconceptions"]
        }
        missing = [r["mis_id"] for r in self._rows() if r["mis_id"] not in corpus]
        assert missing == []

    def test_count_field_matches(self) -> None:
        """메타 count가 실제 행 수와 일치(자산 무결성)."""
        data = json.loads(_CROSSLINKS.read_text(encoding="utf-8"))
        assert data["count"] == len(data["crosslinks"]) == 27
