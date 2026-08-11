"""backfill_rephrase_lineage_s4_18.py 무변화(no-op) 스킵 단위테스트 (hermetic · 실 코퍼스 미접촉).

QUAL-04(2026-08-11): rephrased_v0 429건 중 282건(65.7%)이 parent와 정규화 텍스트가 완전
동일한 "무변화 재서술"이었다는 QUAL-03 실측의 근본원인은 이 스크립트가 무변화 레코드에도
예외 없이 slug 재채번·identity_id·relations를 부여해 온 것이었다(모듈 docstring "QUAL-04
설계 변경" 문단 참고). 이 테스트는 그 수정의 핵심 계약을 실 DB·실 코퍼스 없이 검증한다:
  ① **변별력(핵심)** — 같은 픽스처 안에서 무변화 레코드는 slug·problem_id·identity_id·
     relations가 전부 미부여로 남고, 진짜 변형 레코드는 기존과 동일하게 재슬러그·identity·
     relation이 부여됨을 동시에 확인한다.
  ② 이미 identity_id가 있는 레코드(재실행 시) — 여전히 already_done으로 스킵(멱등 불변).
  ③ `--check` 드라이런 — 파일 미기록(기존 관례 재확인).
  ④ 카운터(`noop_skipped` 등)가 리포트 출력(stdout)에 정확히 반영됨.
  ⑤ 정규화 비교 — 공백 연속·NFC/NFD 유니코드 형태 차이만 있는 근접 무변화도 잡음(QUAL-03의
     `_normalize_for_comparison`/`normalize_question_text`와 동일 기준).

경로: `scripts/backfill_rephrase_lineage_s4_18.py`는 `src/backend/whymath_backend/` 밖의
독립 `scripts/` 파일이라 `tests/backend/`가 아니라 `tests/infra/`에 둔다(같은 성격의
`scripts/cleanup_atom_orphans.py` → `tests/infra/test_cleanup_atom_orphans.py` 선례를
그대로 따름 — importlib 모듈 로드도 그 파일의 관례를 재사용). lint는 harness-integrity 잡의
`ruff/black scripts`가, 실행은 infra-contracts 잡의 `pytest tests/infra`가 담당한다(두
CI 잡에 자연히 나뉘어 배선되는 것도 cleanup_atom_orphans와 동형).

모듈 전역 `_GENERATED`/`_REPHRASED`(레포 루트 기준 절대경로 상수)는 `monkeypatch`로 임시
경로를 가리키게 해 실제 `data/corpus/**`를 절대 읽거나 쓰지 않는다 — 이 파일의 모든 테스트가
끝난 뒤에도 `git status --porcelain -- data/corpus/`는 빈 출력이어야 한다.
"""

from __future__ import annotations

import importlib.util
import json
import unicodedata
from pathlib import Path
from typing import Any

import pytest

# ---- 대상 스크립트 로드 (sys.path 의존 없이·tests/infra 관례, test_cleanup_atom_orphans.py 동형) --
_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "backfill_rephrase_lineage_s4_18.py"
)
_spec = importlib.util.spec_from_file_location("backfill_rephrase_lineage_s4_18", _SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


_BASE_QUESTION = "이차방정식 x^2 - 5x = 0 의 두 근 중에서 더 큰 근의 값을 구하시오."


def _parent(
    slug: str,
    *,
    question_text: str = _BASE_QUESTION,
    answer: str = "5",
    conditions: str = "x**2 - 5*x = 0",
) -> dict[str, Any]:
    """generated_v0 원본 레코드 최소 픽스처 — `_math_key` 대상 필드만 채운다."""
    return {
        "slug": slug,
        "problem_id": f"pid-{slug}",
        "question_text": question_text,
        "answer": answer,
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": conditions, "answer_selection": "largest"},
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture()
def corpus_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """`_GENERATED`/`_REPHRASED` 전역을 임시 파일로 치환 — 실 data/corpus/** 절대 미접촉."""
    generated = tmp_path / "generated.jsonl"
    rephrased = tmp_path / "rephrased.jsonl"
    monkeypatch.setattr(mod, "_GENERATED", generated)
    monkeypatch.setattr(mod, "_REPHRASED", rephrased)
    return generated, rephrased


# ── ① 변별력(핵심) — 무변화는 전부 미부여, 진짜 변형은 기존과 동일하게 부여 ─────────────


def test_noop_and_real_change_distinguished_in_same_pass(
    corpus_paths: tuple[Path, Path],
) -> None:
    generated_path, rephrased_path = corpus_paths
    # 두 parent는 서로 다른 math key(answer 축)를 가져야 한다 — 같으면 함수가 "생성 수학키
    # 충돌"로 즉시 fail-closed(return 1)한다(무변화 판정 이전 단계의 기존 불변식).
    parent_noop = _parent("wm-skel-noop-parent", answer="5")
    parent_changed = _parent("wm-skel-changed-parent", answer="7")
    _write_jsonl(generated_path, [parent_noop, parent_changed])

    noop_child = {
        "slug": "wm-skel-noop-parent",  # parent와 slug 충돌(colliding)
        "problem_id": "pid-noop-original",
        "question_text": _BASE_QUESTION,  # parent와 바이트 완전 동일 — 무변화
        "answer": "5",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
    }
    changed_child = {
        "slug": "wm-skel-changed-parent",  # parent와 slug 충돌(colliding)
        "problem_id": "pid-changed-original",
        "question_text": "x^2 - 5x = 0을 만족하는 두 실근 중 큰 값은 얼마인가?",  # 진짜 변형
        "answer": "7",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
    }
    _write_jsonl(rephrased_path, [noop_child, changed_child])

    exit_code = mod.backfill(check=False)
    assert exit_code == 0

    out_rephrased = _read_jsonl(rephrased_path)
    noop_out = next(r for r in out_rephrased if r["problem_id"] == "pid-noop-original")
    changed_out = next(r for r in out_rephrased if r["question_text"] != _BASE_QUESTION)

    # (a) 무변화 — slug·problem_id·identity_id·relations 전부 원래 값 그대로(키 자체가 없음).
    assert noop_out["slug"] == "wm-skel-noop-parent"
    assert noop_out["problem_id"] == "pid-noop-original"
    assert "identity_id" not in noop_out
    assert "relations" not in noop_out

    # (b) 진짜 변형 — 기존과 동일하게 재슬러그·problem_id 파생·identity_id·relations 부여.
    assert changed_out["slug"] == "wm-skel-changed-parent-rephrased"
    assert changed_out["problem_id"] != "pid-changed-original"
    assert changed_out.get("identity_id") is not None
    assert changed_out["relations"] == [
        {"parent_slug": "wm-skel-changed-parent", "relation_type": "변형", "similarity_score": 1.0}
    ]

    # parent 쪽도 무변화 계열은 identity 미부여, 진짜 변형 계열은 자녀와 identity 공유.
    out_generated = {g["slug"]: g for g in _read_jsonl(generated_path)}
    assert out_generated["wm-skel-noop-parent"].get("identity_id") is None
    assert out_generated["wm-skel-changed-parent"]["identity_id"] == changed_out["identity_id"]


# ── ② 멱등성 — 이미 identity_id가 있으면 재실행해도 스킵(already_done) ────────────────


def test_already_identity_id_record_remains_skipped(corpus_paths: tuple[Path, Path]) -> None:
    generated_path, rephrased_path = corpus_paths
    parent = _parent("wm-skel-done-parent")
    _write_jsonl(generated_path, [parent])
    done_child = {
        "slug": "wm-skel-done-parent-rephrased",
        "problem_id": "pid-done-child",
        "question_text": "이미 계보가 부여된 변형 발문입니다.",
        "answer": "5",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
        "identity_id": "existing-identity-uuid",
        "relations": [
            {"parent_slug": "wm-skel-done-parent", "relation_type": "변형", "similarity_score": 1.0}
        ],
    }
    _write_jsonl(rephrased_path, [done_child])

    exit_code = mod.backfill(check=False)
    assert exit_code == 0

    out = _read_jsonl(rephrased_path)[0]
    assert out == done_child  # 완전 불변 — 재처리 없음(무변화 판정 로직에 도달조차 안 함)


# ── ③ `--check` 드라이런 — 파일 미기록 ──────────────────────────────────────────────


def test_check_dry_run_does_not_write(corpus_paths: tuple[Path, Path]) -> None:
    generated_path, rephrased_path = corpus_paths
    parent = _parent("wm-skel-dryrun-parent")
    _write_jsonl(generated_path, [parent])
    child = {
        "slug": "wm-skel-dryrun-parent",
        "problem_id": "pid-dryrun-child",
        "question_text": "실제로 표현이 바뀐 발문",
        "answer": "5",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
    }
    _write_jsonl(rephrased_path, [child])
    before_generated = generated_path.read_text(encoding="utf-8")
    before_rephrased = rephrased_path.read_text(encoding="utf-8")

    exit_code = mod.backfill(check=True)
    assert exit_code == 0

    assert generated_path.read_text(encoding="utf-8") == before_generated
    assert rephrased_path.read_text(encoding="utf-8") == before_rephrased


# ── ④ 카운터가 리포트 출력에 정확히 반영됨 ─────────────────────────────────────────


def test_counters_reflected_in_report_output(
    corpus_paths: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    generated_path, rephrased_path = corpus_paths
    parent_done = _parent("wm-skel-r-done", answer="1")
    parent_noop = _parent("wm-skel-r-noop", answer="2")
    parent_changed = _parent("wm-skel-r-changed", answer="3")
    _write_jsonl(generated_path, [parent_done, parent_noop, parent_changed])

    already_done_child = {
        "slug": "wm-skel-r-done-rephrased",
        "problem_id": "pid-r-done-child",
        "question_text": "이미 처리됨",
        "answer": "1",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
        "identity_id": "already-uuid",
        "relations": [
            {"parent_slug": "wm-skel-r-done", "relation_type": "변형", "similarity_score": 1.0}
        ],
    }
    noop_child = {
        "slug": "wm-skel-r-noop",
        "problem_id": "pid-r-noop-child",
        "question_text": _BASE_QUESTION,
        "answer": "2",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
    }
    changed_child = {
        "slug": "wm-skel-r-changed",
        "problem_id": "pid-r-changed-child",
        "question_text": "두 근 중 큰 값을 구해 보시오(다른 표현).",
        "answer": "3",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
    }
    _write_jsonl(rephrased_path, [already_done_child, noop_child, changed_child])

    exit_code = mod.backfill(check=False)
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "이미 처리됨(스킵) 1" in out
    assert "무변화 스킵(noop) 1" in out
    assert "slug 재채번 1" in out
    assert "identity_id 부여 1" in out
    assert "relation 부여 1" in out
    assert "(전체 3건)" in out


# ── ⑤ 정규화 비교 — 공백 연속·NFC/NFD 형태 차이만 있는 근접 무변화도 잡는다 ────────────


def test_normalization_catches_whitespace_and_nfc_near_noop(
    corpus_paths: tuple[Path, Path],
) -> None:
    generated_path, rephrased_path = corpus_paths
    parent_text = unicodedata.normalize("NFD", _BASE_QUESTION)  # 분해형(NFD)
    child_text = _BASE_QUESTION.replace(" ", "  ")  # 공백 연속(NFC는 유지)
    # 자가검증 — 정규화 없이 바이트 비교하면 서로 다른 문자열임을 먼저 확인(그렇지 않으면
    # 이 테스트가 정규화 로직이 아니라 우연한 일치를 검증하게 된다).
    assert parent_text != child_text
    assert parent_text != _BASE_QUESTION
    assert child_text != _BASE_QUESTION

    parent = _parent("wm-skel-nearnoop-parent", question_text=parent_text)
    _write_jsonl(generated_path, [parent])
    child = {
        "slug": "wm-skel-nearnoop-parent",
        "problem_id": "pid-nearnoop-child",
        "question_text": child_text,
        "answer": "5",
        "unit_codes": ["QUAD-EQ"],
        "verify": {"conditions": "x**2 - 5*x = 0", "answer_selection": "largest"},
    }
    _write_jsonl(rephrased_path, [child])

    exit_code = mod.backfill(check=False)
    assert exit_code == 0

    out = _read_jsonl(rephrased_path)[0]
    assert out["slug"] == "wm-skel-nearnoop-parent"  # 재채번 없음 — 정규화 비교가 무변화로 판정
    assert "identity_id" not in out
