"""policy.yaml — 조율 정책 로드/저장/검증 테스트."""

from __future__ import annotations

from pathlib import Path

import store
from models import Policy


class TestPolicyDefaults:
    def test_missing_file_uses_all_defaults(self, tmp_path: Path):
        """test_파일_부재_시_전부_기본값"""
        policy, errors = store.load_policy(tmp_path)
        assert errors == []
        assert policy.path_overlap == "warn"
        assert policy.scope_drift == "warn"
        assert policy.adhoc_edit == "warn"
        assert policy.claim_ttl_hours == 72
        assert policy.remote_claims is True

    def test_defaults_pass_validation(self):
        """test_기본값은_검증_통과"""
        assert Policy().validate() == []


class TestPolicyValidation:
    def test_invalid_mode_rejected(self):
        """test_잘못된_모드_거부"""
        errors = Policy(path_overlap="strict").validate()
        assert any("path_overlap" in e for e in errors)

    def test_negative_ttl_rejected(self):
        """test_ttl_음수_거부"""
        errors = Policy(claim_ttl_hours=0).validate()
        assert any("claim_ttl_hours" in e for e in errors)

    def test_load_with_invalid_value_reports_error(self, tmp_path: Path):
        """test_로드_시_잘못된_값이_오류로_보고된다"""
        (tmp_path / "backlog").mkdir()
        (tmp_path / "backlog" / "policy.yaml").write_text(
            "path_overlap: aggressive\n", encoding="utf-8"
        )
        _, errors = store.load_policy(tmp_path)
        assert any("path_overlap" in e for e in errors)

    def test_unknown_field_is_error(self, tmp_path: Path):
        """test_미지_필드는_오류"""
        (tmp_path / "backlog").mkdir()
        (tmp_path / "backlog" / "policy.yaml").write_text("unknown_rule: warn\n", encoding="utf-8")
        _, errors = store.load_policy(tmp_path)
        assert any("미지 필드" in e for e in errors)


class TestPolicyRoundtrip:
    def test_save_then_load_is_identical(self, tmp_path: Path):
        """test_저장_후_로드_동일"""
        policy = Policy(path_overlap="block", claim_ttl_hours=24)
        store.save_policy(tmp_path, policy)
        loaded, errors = store.load_policy(tmp_path)
        assert errors == []
        assert loaded == policy

    def test_dump_is_deterministic(self):
        """test_dump_결정성"""
        # 같은 입력이면 항상 같은 출력 (diff 안정)
        a = store.dump_policy(Policy())
        b = store.dump_policy(Policy())
        assert a == b
        assert "path_overlap: warn" in a
        assert "remote_claims: true" in a
