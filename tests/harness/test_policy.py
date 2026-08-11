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
        assert policy.claim_branch_grace_hours == 24
        assert policy.remote_claims is True

    def test_branch_grace_is_shorter_than_ttl(self):
        """test_브랜치_유예는_TTL보다_짧다 — 같거나 길면 branch_gone의 변별력이 0이 된다

        실측(events.ndjson 199건): 72h 초과 세션 0건. grace를 TTL(72h)로 두면
        branch_gone이 잡는 집합이 ttl이 잡는 집합의 부분집합이 되어, 새 기준이
        탐지력을 단 1건도 추가하지 못한다(CLAUDE.md 변별력 없는 검증 스텝 금지).
        """
        policy = Policy()
        assert policy.claim_branch_grace_hours < policy.claim_ttl_hours

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

    def test_non_positive_branch_grace_rejected(self):
        """test_브랜치_유예_0이하_거부 — 유예 0은 첫 push 전 세션의 claim을 즉시 지운다"""
        errors = Policy(claim_branch_grace_hours=0).validate()
        assert any("claim_branch_grace_hours" in e for e in errors)

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
