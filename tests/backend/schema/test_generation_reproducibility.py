"""생성 Run 재현 계약(EOS-55 acceptance ②) — canonical 해시·복원·무결성 봉인 동결.

계약: **"동일 Run 레코드로 재실행 시 동일 입력이 복원된다"** —
  ① canonical 직렬화는 결정론(키 순서 무관·같은 내용=같은 문자열=같은 해시).
  ② `GenerationLog`는 스냅샷이 있으면 해시를 자동 보충하고, 불일치 주장은 적재 거부.
  ③ `restore_input_snapshot(레코드)`는 해시 재계산·대조 통과분만 돌려준다 — 미기록은
     빈 dict 위장 없이 ValueError, 변조는 ValueError(무결성 실패).
  ④ 골든 해시 동결 — canonical 직렬화 규약(정렬·compact·유니코드 원문)이 조용히 바뀌면
     기존 DB/JSONL 레코드 전부가 복원 불가가 되므로, 규약 자체를 상수로 못 박는다.

정본: `schema/provenance.py`(canonical_input_json·input_snapshot_sha256·text_sha256·
restore_input_snapshot + GenerationLog validator).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from pydantic import ValidationError

from whymath_backend.schema.provenance import (
    GenerationLog,
    canonical_input_json,
    input_snapshot_sha256,
    restore_input_snapshot,
    text_sha256,
)


def _snapshot(**overrides: Any) -> dict[str, Any]:
    """대표 스냅샷 — 중첩 dict·list·불리언·수치·유니코드 전형 포함(왕복 안정성 재료)."""
    base: dict[str, Any] = {
        "kind": "l3.pregenerate.prewarm",
        "prompt_sha256": text_sha256("이차방정식 x^2-5x+6=0"),
        "system_sha256": text_sha256(""),
        "request": {
            "task_type": "explain",
            "difficulty": "easy",
            "requires_reasoning": False,
            "student_subscription": "free",
            "sync": True,
        },
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────
# ① canonical 직렬화 — 결정론
# ──────────────────────────────────────────────────────────────────────
class TestCanonicalSerialization:
    def test_key_order_invariance(self) -> None:
        """같은 내용·다른 키 순서 → 같은 canonical 문자열·같은 해시(재현의 전제)."""
        a = {"b": 1, "a": {"y": 2, "x": [3, 1]}}
        b = {"a": {"x": [3, 1], "y": 2}, "b": 1}
        assert canonical_input_json(a) == canonical_input_json(b)
        assert input_snapshot_sha256(a) == input_snapshot_sha256(b)

    def test_list_order_is_significant(self) -> None:
        """리스트 순서는 내용이다 — 순서가 다르면 다른 입력(해시 상이)."""
        assert input_snapshot_sha256({"k": [1, 2]}) != input_snapshot_sha256({"k": [2, 1]})

    def test_compact_and_unicode_preserved(self) -> None:
        """compact separators + ensure_ascii=False — 유니코드 원문 그대로(이스케이프 없음)."""
        text = canonical_input_json({"힌트": "이차방정식", "n": 2.5})
        assert text == '{"n":2.5,"힌트":"이차방정식"}'

    def test_nan_rejected(self) -> None:
        """NaN/Infinity는 JSON 표준 밖(PG JSONB 왕복 불가) — 조용한 이식 불가 스냅샷 거부."""
        with pytest.raises(ValueError):
            canonical_input_json({"x": float("nan")})

    def test_non_json_value_rejected(self) -> None:
        """JSON 비직렬화 값(set 등)은 TypeError — 조립부가 원시형으로 정규화해야 한다."""
        with pytest.raises(TypeError):
            canonical_input_json({"x": {1, 2}})

    def test_golden_digest_frozen(self) -> None:
        """골든 해시 동결 — canonical 규약이 바뀌면 기존 레코드 전부 복원 불가(여기서 잡는다)."""
        assert (
            input_snapshot_sha256(_snapshot())
            == "0b3156a01eda4bf37dfe8e8939c72d2879147a184d1b375bff6c12b765578c09"
        )

    def test_text_sha256_matches_stdlib(self) -> None:
        """text_sha256 = utf-8 sha256 hex(정의 동결) — 빈 문자열 알려진 다이제스트 포함."""
        assert text_sha256("") == hashlib.sha256(b"").hexdigest()
        assert text_sha256("가") == hashlib.sha256("가".encode()).hexdigest()


# ──────────────────────────────────────────────────────────────────────
# ② GenerationLog 쓰기측 봉인 — 자동 보충·불일치 거부
# ──────────────────────────────────────────────────────────────────────
class TestWriteSideSeal:
    def test_hash_auto_filled_from_snapshot(self) -> None:
        """스냅샷만 주면 canonical 해시가 자동 보충된다(호출자 계산 드리프트 원천 제거)."""
        snap = _snapshot()
        log = GenerationLog(input_snapshot=snap)
        assert log.input_sha256 == input_snapshot_sha256(snap)

    def test_matching_hash_accepted(self) -> None:
        """해시를 직접 줘도 canonical 재계산과 일치하면 통과."""
        snap = _snapshot()
        log = GenerationLog(input_snapshot=snap, input_sha256=input_snapshot_sha256(snap))
        assert log.input_sha256 == input_snapshot_sha256(snap)

    def test_mismatching_hash_rejected(self) -> None:
        """불일치 해시 주장은 적재 거부(ValidationError) — 변조/파손된 재현 주장 차단."""
        with pytest.raises(ValidationError):
            GenerationLog(input_snapshot=_snapshot(), input_sha256="0" * 64)

    def test_both_absent_is_honest_unrecorded(self) -> None:
        """스냅샷·해시 둘 다 없음 = 미기록(구 레코드·미배선 경로) — 정상 적재."""
        log = GenerationLog()
        assert log.input_snapshot is None
        assert log.input_sha256 is None

    def test_hash_only_allowed(self) -> None:
        """해시만 있는 부분 기록(참조가 외부인 경로)은 허용 — 복원 시도만 정직 실패한다."""
        log = GenerationLog(input_sha256="a" * 64)
        assert log.input_snapshot is None


# ──────────────────────────────────────────────────────────────────────
# ③ 복원 계약 — 레코드만 보고 동일 입력 복원·해시 재계산 일치
# ──────────────────────────────────────────────────────────────────────
class TestRestoreContract:
    def test_restore_returns_equal_input(self) -> None:
        """레코드만으로 스냅샷을 복원 → 원 입력과 동일 + 해시 재계산 일치(계약 본체)."""
        snap = _snapshot()
        log = GenerationLog(input_snapshot=snap)
        restored = restore_input_snapshot(log)
        assert restored == snap
        assert input_snapshot_sha256(restored) == log.input_sha256

    def test_restore_survives_json_roundtrip(self) -> None:
        """직렬화 왕복(JSONL/DB 경로와 동형: model_dump→model_validate) 후에도 복원 성립."""
        log = GenerationLog(input_snapshot=_snapshot())
        revived = GenerationLog.model_validate(log.model_dump(mode="json"))
        assert restore_input_snapshot(revived) == _snapshot()

    def test_restore_is_deep_copy(self) -> None:
        """반환은 깊은 복사 — 호출자 수정이 레코드를 오염시키지 않는다."""
        log = GenerationLog(input_snapshot=_snapshot())
        restored = restore_input_snapshot(log)
        restored["request"]["task_type"] = "다른값"
        # 레코드 원본은 불변 — 재복원하면 원 입력 그대로.
        assert restore_input_snapshot(log) == _snapshot()

    def test_unrecorded_snapshot_raises(self) -> None:
        """스냅샷 미기록 레코드는 빈 dict 위장 없이 ValueError(복원 불가를 정직하게)."""
        with pytest.raises(ValueError, match="미기록"):
            restore_input_snapshot(GenerationLog())

    def test_hash_only_record_raises(self) -> None:
        """해시만 있는 레코드도 복원 불가 — ValueError(참조 없이 입력을 지어내지 않는다)."""
        with pytest.raises(ValueError, match="미기록"):
            restore_input_snapshot(GenerationLog(input_sha256="a" * 64))

    def test_tampered_snapshot_raises(self) -> None:
        """구성 후 스냅샷이 변조되면(해시 불일치) 복원 거부 — 무결성 실패를 조용히 안 넘긴다."""
        log = GenerationLog(input_snapshot=_snapshot())
        assert log.input_snapshot is not None
        log.input_snapshot["request"]["difficulty"] = "killer"  # 적재 후 in-place 변조 재현
        with pytest.raises(ValueError, match="불일치"):
            restore_input_snapshot(log)


# ──────────────────────────────────────────────────────────────────────
# ④ 재현 좌석 필드 계약 — NULL=미기록·형식 강제
# ──────────────────────────────────────────────────────────────────────
class TestReproducibilitySeats:
    def test_seats_default_none(self) -> None:
        """prompt_version·seed 기본 None=미기록 — 0/빈문자 날조 없음."""
        log = GenerationLog()
        assert log.prompt_version is None
        assert log.seed is None

    def test_seed_recorded_when_given(self) -> None:
        """seed는 *실제 쓰인 값*이 주어지면 그대로 기록된다(좌석 실재 계약)."""
        assert GenerationLog(seed=42).seed == 42

    def test_input_sha256_format_enforced(self) -> None:
        """input_sha256은 64자 소문자 hex만 — 형식 밖 주장은 적재 거부."""
        with pytest.raises(ValidationError):
            GenerationLog(input_sha256="XYZ")

    def test_prompt_version_recorded(self) -> None:
        """prompt_version 문자열 좌석 — 정본 자산 해시 식별자 형식이 그대로 보존된다."""
        version = "l3.equivalent@sha256:abc123def456"
        assert GenerationLog(prompt_version=version).prompt_version == version
